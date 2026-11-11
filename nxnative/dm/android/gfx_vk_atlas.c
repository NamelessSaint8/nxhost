// Opt-in, read-only compressed NVN sparse atlases. Logical page tables address
// packed native-compressed cells. Cells are immutable while any submitted table
// can read them; changed mappings publish new tables and reuse only retired cells.
#include "gfx_vk.h"
#include "nvn_tex.h"
#include "nvn_dirty.h"
#include "nvn_hmap.h"
#include "../gfx/tex/nvn_deswizzle.h"
#include <CommonCrypto/CommonDigest.h>
#include <string.h>

#define VA_GRID 8u
#define VA_HEADER 96u
#define VA_LEVELS 16u
#define VA_STAGE (8u << 20)
#define VA_MISSING UINT32_MAX
#define VA_PENDING (UINT32_MAX-1u)
extern pthread_mutex_t g_vk_queue_mu;
int nvn_sparse_pool(const void *pool);
uint64_t nvn_sparse_gen(void), nvn_sparse_mapped_bytes(const void *, uint64_t, uint64_t), nvn_sparse_copy(const void *, void *, uint64_t, uint64_t);
int nvn_sparse_since(const void *, uint64_t, uint64_t, uint64_t, uint64_t);
int nvn_sparse_cpu_readable(const void *,uint64_t,uint64_t);
void nvn_sparse_protect(const void *, uint64_t, uint64_t);
extern uint64_t g_tex_frame;

typedef struct { uint8_t digest[32]; uint32_t w,h; } va_key;
typedef struct { va_key key; uint32_t refs; uint64_t fence; int valid; } va_cell;
typedef struct va_view { VkComponentMapping swz; VkImageView view; struct va_view *next; } va_view;
typedef struct va_context {
    struct va_context *next;
    pool_t *pool; uint32_t pool_generation; int64_t off; nvn_texdesc desc; nvn_texlayout layout;
    uint32_t tw,th,tail,count,slots,capacity,layers; va_cell *cell; nvn_hmap by_content;
    uint32_t *table; uint64_t gen,stamp,used_fence,used_frame,revision,referenced_revision,reported_revision;
    uint64_t mapped_entries,mapped_native_pages,total_native_pages;
    uint64_t checked_gen,checked_stamp,cpu_gen,cpu_epoch; int cpu_readable,filter_linear;
    VkImage image; VkDeviceMemory memory; VkDeviceSize allocated; va_view *views;
    struct { view_t view; samp_par sampler; uint64_t epoch,revision; VkImageView image; VkDescriptorBufferInfo meta; } binding;
} va_context;
static va_context *g_context;
static uint64_t g_atlas_gen=1;   // bumped when any context's table revision changes or its image is retired: a memoized descriptor set (gfx_vk_exec.c) cannot outlive the view or metadata it names
static pthread_mutex_t g_atlas_mu=PTHREAD_MUTEX_INITIALIZER;
static VkCommandPool g_pool;
static VkCommandBuffer g_cmd;
static VkFence g_fence;
static VkBuffer g_stage;
static VkDeviceMemory g_stage_memory;
static uint8_t *g_stage_map;static VkDeviceSize g_stage_allocated;
typedef struct va_retired { VkImage image; VkDeviceMemory memory; va_view *views; uint64_t fence; VkDeviceSize bytes; struct va_retired *next; } va_retired;
static va_retired *g_retired;
static VkBufferImageCopy g_copy[256];
static uint32_t g_ncopy; static VkDeviceSize g_stage_used;
static uint64_t g_uploaded,g_allocated,g_metadata,g_reused,g_peak_allocated;
static void allocation_add(uint64_t bytes) { g_allocated+=bytes;if(g_allocated>g_peak_allocated)g_peak_allocated=g_allocated; }
static void resource_free(va_retired *r) {
    va_view *v=r->views;while(v){va_view *next=v->next;vkDestroyImageView(V.dev,v->view,NULL);free(v);v=next;}
    vkDestroyImage(V.dev,r->image,NULL);vk_memory_free(V.dev,r->memory,NULL);g_allocated-=r->bytes;free(r);
}
static void collect(void) {
    uint64_t done=vk_fence_done();va_retired **link=&g_retired;
    while(*link){va_retired *r=*link;if(r->fence>done){link=&r->next;continue;}*link=r->next;resource_free(r);}
    if(!g_context && !g_retired && g_pool){vkUnmapMemory(V.dev,g_stage_memory);vkDestroyBuffer(V.dev,g_stage,NULL);vk_memory_free(V.dev,g_stage_memory,NULL);vkDestroyFence(V.dev,g_fence,NULL);
        PFN_vkDestroyCommandPool destroy=(PFN_vkDestroyCommandPool)vkGetDeviceProcAddr(V.dev,"vkDestroyCommandPool");destroy(V.dev,g_pool,NULL);g_allocated-=g_stage_allocated;g_pool=VK_NULL_HANDLE;g_stage_map=NULL;g_stage_allocated=0;}
}
static void retire(va_context *c) {
    if(c->image){va_retired *r=calloc(1,sizeof*r);r->image=c->image;r->memory=c->memory;r->views=c->views;r->bytes=c->allocated;r->fence=c->used_fence;
        if(r->fence<=vk_fence_done())resource_free(r);else{r->next=g_retired;g_retired=r;}}
    c->views=NULL;c->image=VK_NULL_HANDLE;c->memory=VK_NULL_HANDLE;c->allocated=0;c->binding.epoch=0;__atomic_add_fetch(&g_atlas_gen,1,__ATOMIC_RELEASE);
}
int vk_atlas_enabled(void) { static int enabled=-1;int value=__atomic_load_n(&enabled,__ATOMIC_ACQUIRE);if(value<0){const char *p=getenv("DM_VK_ATLAS");value=p && atoi(p);__atomic_store_n(&enabled,value,__ATOMIC_RELEASE);}return value; }
static int check_cache_enabled(void) {
    static int enabled=-1;int value=__atomic_load_n(&enabled,__ATOMIC_ACQUIRE);
    if(value<0){const char *p=getenv("DM_VK_ATLAS_CHECK_CACHE");value=!p || atoi(p);__atomic_store_n(&enabled,value,__ATOMIC_RELEASE);}return value;
}
int vk_atlas_candidate(const tex_t *t) {
    if(!vk_atlas_enabled() || !t)return 0;
    const vkfmt_t *f=vk_fmt(t->d.format);
    return t && t->pool && t->mem && (t->d.flags&NVN_TEXTURE_FLAGS_SPARSE) && nvn_sparse_pool(t->pool) && f && f->compressed;
}
static void transfer_init(void) {
    if(g_pool)return;
    VkCommandPoolCreateInfo pi={VK_STRUCTURE_TYPE_COMMAND_POOL_CREATE_INFO,NULL,VK_COMMAND_POOL_CREATE_RESET_COMMAND_BUFFER_BIT,V.qf};VKCHK(vkCreateCommandPool(V.dev,&pi,NULL,&g_pool));
    VkCommandBufferAllocateInfo ai={VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO,NULL,g_pool,VK_COMMAND_BUFFER_LEVEL_PRIMARY,1};VKCHK(vkAllocateCommandBuffers(V.dev,&ai,&g_cmd));
    VkFenceCreateInfo fi={VK_STRUCTURE_TYPE_FENCE_CREATE_INFO};VKCHK(vkCreateFence(V.dev,&fi,NULL,&g_fence));
    VkBufferCreateInfo bi={VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO,NULL,0,VA_STAGE,VK_BUFFER_USAGE_TRANSFER_SRC_BIT,VK_SHARING_MODE_EXCLUSIVE};VKCHK(vkCreateBuffer(V.dev,&bi,NULL,&g_stage));
    VkMemoryRequirements req;vkGetBufferMemoryRequirements(V.dev,g_stage,&req);
    VkMemoryAllocateInfo mi={VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO,NULL,req.size,vk_mem_type(req.memoryTypeBits,VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT|VK_MEMORY_PROPERTY_HOST_COHERENT_BIT,0)};
    VKCHK(vk_memory_allocate(V.dev,&mi,NULL,&g_stage_memory));VKCHK(vkBindBufferMemory(V.dev,g_stage,g_stage_memory,0));VKCHK(vkMapMemory(V.dev,g_stage_memory,0,VA_STAGE,0,(void**)&g_stage_map));g_stage_allocated=req.size;allocation_add(req.size);
}
static void transfer_begin(void) {
    transfer_init();VKCHK(vkResetCommandBuffer(g_cmd,0));VKCHK(vkResetFences(V.dev,1,&g_fence));
    VkCommandBufferBeginInfo bi={VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO,NULL,VK_COMMAND_BUFFER_USAGE_ONE_TIME_SUBMIT_BIT};VKCHK(vkBeginCommandBuffer(g_cmd,&bi));
}
static void image_barrier(VkImage image,uint32_t layers,VkImageLayout old) {
    VkImageMemoryBarrier b={VK_STRUCTURE_TYPE_IMAGE_MEMORY_BARRIER,NULL,old==VK_IMAGE_LAYOUT_UNDEFINED?0:VK_ACCESS_MEMORY_READ_BIT|VK_ACCESS_MEMORY_WRITE_BIT,VK_ACCESS_TRANSFER_READ_BIT|VK_ACCESS_TRANSFER_WRITE_BIT,old,VK_IMAGE_LAYOUT_GENERAL,VK_QUEUE_FAMILY_IGNORED,VK_QUEUE_FAMILY_IGNORED,image,{VK_IMAGE_ASPECT_COLOR_BIT,0,1,0,layers}};
    vkCmdPipelineBarrier(g_cmd,VK_PIPELINE_STAGE_ALL_COMMANDS_BIT,VK_PIPELINE_STAGE_TRANSFER_BIT,0,0,NULL,0,NULL,1,&b);
}
static void transfer_finish(void) {
    VkMemoryBarrier b={VK_STRUCTURE_TYPE_MEMORY_BARRIER,NULL,VK_ACCESS_TRANSFER_WRITE_BIT,VK_ACCESS_MEMORY_READ_BIT};vkCmdPipelineBarrier(g_cmd,VK_PIPELINE_STAGE_TRANSFER_BIT,VK_PIPELINE_STAGE_ALL_COMMANDS_BIT,0,1,&b,0,NULL,0,NULL);
    VKCHK(vkEndCommandBuffer(g_cmd));VkSubmitInfo si={VK_STRUCTURE_TYPE_SUBMIT_INFO,NULL,0,NULL,NULL,1,&g_cmd};
    pthread_mutex_lock(&g_vk_queue_mu);VkResult result=vkQueueSubmit(V.q,1,&si,g_fence);pthread_mutex_unlock(&g_vk_queue_mu);VKCHK(result);
    VkResult wait=vkWaitForFences(V.dev,1,&g_fence,VK_TRUE,10000000000ull);if(wait!=VK_SUCCESS)die("[RED] [vk] atlas transfer did not finish: %d",wait);
}
static void upload_flush(va_context *c) {
    if(!g_ncopy)return;
    transfer_begin();image_barrier(c->image,c->layers,VK_IMAGE_LAYOUT_GENERAL);
    vkCmdCopyBufferToImage(g_cmd,g_stage,c->image,VK_IMAGE_LAYOUT_GENERAL,g_ncopy,g_copy);transfer_finish();g_uploaded+=g_stage_used;g_ncopy=0;g_stage_used=0;
}
static void cache_size(va_context *c,uint32_t cells,const vkfmt_t *f) {
    uint32_t layers=(cells+VA_GRID*VA_GRID-1)/(VA_GRID*VA_GRID);if(!layers)layers=1;
    if(layers==c->layers)return;
    if(layers>V.props.limits.maxImageArrayLayers || c->tw*VA_GRID>V.props.limits.maxImageDimension2D || c->th*VA_GRID>V.props.limits.maxImageDimension2D)die("[RED] [vk] atlas working set exceeds packed image limits");
    upload_flush(c);
    VkImage image;VkDeviceMemory memory;
    VkImageCreateInfo ci={VK_STRUCTURE_TYPE_IMAGE_CREATE_INFO,NULL,0,VK_IMAGE_TYPE_2D,f->vk,{c->tw*VA_GRID,c->th*VA_GRID,1},1,layers,VK_SAMPLE_COUNT_1_BIT,VK_IMAGE_TILING_OPTIMAL,VK_IMAGE_USAGE_SAMPLED_BIT|VK_IMAGE_USAGE_TRANSFER_SRC_BIT|VK_IMAGE_USAGE_TRANSFER_DST_BIT,VK_SHARING_MODE_EXCLUSIVE};VKCHK(vkCreateImage(V.dev,&ci,NULL,&image));
    VkMemoryRequirements req;vkGetImageMemoryRequirements(V.dev,image,&req);VkMemoryAllocateInfo ai={VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO,NULL,req.size,vk_mem_type(req.memoryTypeBits,VK_MEMORY_PROPERTY_DEVICE_LOCAL_BIT,0)};VKCHK(vk_memory_allocate(V.dev,&ai,NULL,&memory));allocation_add(req.size);VKCHK(vkBindImageMemory(V.dev,image,memory,0));
    transfer_begin();image_barrier(image,layers,VK_IMAGE_LAYOUT_UNDEFINED);
    if(c->image){image_barrier(c->image,c->layers,VK_IMAGE_LAYOUT_GENERAL);VkImageCopy copy={{VK_IMAGE_ASPECT_COLOR_BIT,0,0,layers<c->layers?layers:c->layers},{0,0,0},{VK_IMAGE_ASPECT_COLOR_BIT,0,0,layers<c->layers?layers:c->layers},{0,0,0},{c->tw*VA_GRID,c->th*VA_GRID,1}};vkCmdCopyImage(g_cmd,c->image,VK_IMAGE_LAYOUT_GENERAL,image,VK_IMAGE_LAYOUT_GENERAL,1,&copy);}
    transfer_finish();
    retire(c);c->allocated=req.size;c->image=image;c->memory=memory;c->layers=layers;
}
static void plan_release(va_context *c) { if(c->table){for(uint32_t i=VA_HEADER;i<c->count;i++)if(c->table[i]!=VA_MISSING)c->cell[c->table[i]].refs--;free(c->table);c->table=NULL;} }
static va_context *context(const tex_t *t) {
    for(va_context *c=g_context;c;c=c->next)if(c->pool==t->pool && c->pool_generation==t->pool->generation && c->off==t->off && !memcmp(&c->desc,&t->d,sizeof t->d))return c;
    va_context *c=calloc(1,sizeof*c);c->pool=t->pool;c->pool_generation=t->pool->generation;c->off=t->off;c->desc=t->d;c->layout=t->L;c->by_content.klen=sizeof(va_key);
    c->tail=nvn_tex_sparse_tiles(&t->d,&c->tw,&c->th,&(uint32_t){0});
    if(!c->tw || !c->th || t->d.levels>VA_LEVELS || (t->d.target!=NVN_TEXTURE_TARGET_2D_ARRAY && t->d.target!=NVN_TEXTURE_TARGET_2D) || t->d.samples>1 || (c->tail<t->d.levels && t->L.layer_size-nvn_tex_level_offset(&t->d,c->tail)>65536))die("[RED] [vk] unsupported atlas layout");
    // Once per context (its format never changes): this query used to run for every descriptor.
    VkFormatProperties properties;vkGetPhysicalDeviceFormatProperties(V.pd,vk_fmt(t->d.format)->vk,&properties);c->filter_linear=!!(properties.optimalTilingFeatures&VK_FORMAT_FEATURE_SAMPLED_IMAGE_FILTER_LINEAR_BIT);
    c->count=VA_HEADER;
    for(uint32_t mip=0;mip<t->d.levels;mip++){uint32_t w=t->d.width>>mip,h=t->d.height>>mip;if(!w)w=1;if(!h)h=1;uint64_t entries=(uint64_t)((w+c->tw-1)/c->tw)*((h+c->th-1)/c->th)*t->L.layers;if(entries>UINT32_MAX-c->count)die("[RED] [vk] atlas table too large");c->count+=(uint32_t)entries;}
    c->next=g_context;g_context=c;return c;
}
static uint32_t cell_get(va_context *c,const va_key *key,int *fresh) {
    void *found=nvn_hm_get(&c->by_content,key);if(found){*fresh=0;g_reused++;return (uint32_t)(uintptr_t)found-1;}
    uint64_t done=vk_fence_done();uint32_t id=0;
    while(id<c->slots && (c->cell[id].refs || c->cell[id].fence>done))id++;
    if(id==c->slots){if(c->slots==c->capacity){c->capacity=c->capacity?c->capacity*2:64;c->cell=realloc(c->cell,c->capacity*sizeof*c->cell);memset(c->cell+c->slots,0,(c->capacity-c->slots)*sizeof*c->cell);}c->slots++;}
    va_cell *cell=&c->cell[id];if(cell->valid)nvn_hm_del(&c->by_content,&cell->key);cell->key=*key;cell->valid=1;cell->fence=0;cell->refs=0;nvn_hm_put(&c->by_content,key,(void*)(uintptr_t)(id+1));*fresh=1;return id;
}
static void plan_build(va_context *c,const tex_t *t,const vkfmt_t *f) {
    uint64_t gen=nvn_sparse_gen(),stamp=nvn_dirty_now();
    nvn_sparse_protect(t->pool,(uint64_t)(uintptr_t)t->mem,t->L.size);
    uint32_t *table=malloc((size_t)c->count*4);for(uint32_t i=0;i<c->count;i++)table[i]=VA_MISSING;memset(table,0,VA_HEADER*4);
    // Only changed mapped cells can require new storage. Unchanged references
    // keep their cells; holes have no storage. Startup deduplication can shrink
    // this conservative bound to the unique compressed content.
    uint32_t mapped=0,base=VA_HEADER;uint64_t mapped_entries=0,mapped_pages=0,total_pages=0;
    for(uint32_t mip=0;mip<t->d.levels;mip++){
        uint32_t w=t->d.width>>mip,h=t->d.height>>mip;if(!w)w=1;if(!h)h=1;uint32_t nx=(w+c->tw-1)/c->tw,ny=(h+c->th-1)/c->th;
        uint64_t level=nvn_tex_level_offset(&t->d,mip<c->tail?mip:c->tail);
        table[32+4*mip]=w;table[33+4*mip]=h;table[34+4*mip]=nx;table[35+4*mip]=base;
        for(uint32_t layer=0;layer<t->L.layers;layer++)for(uint32_t y=0;y<ny;y++)for(uint32_t x=0;x<nx;x++){
            uint64_t off=(uint64_t)layer*t->L.layer_size+level+(mip<c->tail?((uint64_t)y*nx+x)*65536:0);
            uint64_t bytes=nvn_sparse_mapped_bytes(t->pool,(uint64_t)(uintptr_t)t->mem+off,65536);
            if(f->compressed && bytes && bytes!=65536)die("[RED] [vk] partially mapped compressed atlas cells need subpage coverage support (offset %#llx, %llu/65536 bytes)",(unsigned long long)off,(unsigned long long)bytes);
            uint32_t index=base+(layer*ny+y)*nx+x;
            // All levels from tail onward share one native page per layer.
            int native_page=mip<c->tail || (mip==c->tail && !x && !y);total_pages+=native_page;
            if(bytes){
                mapped_entries++;mapped_pages+=native_page;
                if(c->table && c->table[index]!=VA_MISSING && !nvn_sparse_since(t->pool,(uint64_t)(uintptr_t)t->mem+off,65536,c->gen,c->stamp)){
                    table[index]=c->table[index];c->cell[table[index]].refs++;g_reused++;
                }else{table[index]=VA_PENDING;mapped++;}
            }
        }
        base+=nx*ny*t->L.layers;
    }
    if(mapped>UINT32_MAX-c->slots)die("[RED] [vk] atlas cache cell count overflow");
    // The replacement table already owns its unchanged references. Release the
    // old CPU plan now; cells still used by encoded GPU work remain fence-held.
    // Reusable completed cells do not require another packed image layer.
    plan_release(c);uint64_t done=vk_fence_done();uint32_t available=0;
    for(uint32_t i=0;i<c->slots;i++)if(!c->cell[i].refs && c->cell[i].fence<=done)available++;
    uint32_t extra=mapped>available?mapped-available:0;
    if(c->slots+extra)cache_size(c,c->slots+extra,f);
    uint8_t *source=malloc(65536),*linear=malloc(65536);uint64_t previous=UINT64_MAX;
    for(uint32_t mip=0;mip<t->d.levels;mip++){
        uint32_t w=table[32+4*mip],h=table[33+4*mip],nx=table[34+4*mip],ny=(h+c->th-1)/c->th;uint32_t start=table[35+4*mip];
        uint64_t level=nvn_tex_level_offset(&t->d,mip<c->tail?mip:c->tail);
        for(uint32_t layer=0;layer<t->L.layers;layer++)for(uint32_t y=0;y<ny;y++)for(uint32_t x=0;x<nx;x++){
            uint32_t index=start+(layer*ny+y)*nx+x;
            if(table[index]!=VA_PENDING)continue;
            uint64_t native=(uint64_t)layer*t->L.layer_size+level+(mip<c->tail?((uint64_t)y*nx+x)*65536:0);
            if(previous!=native){uint64_t missing=nvn_sparse_copy(t->pool,source,(uint64_t)(uintptr_t)t->mem+native,65536);if(f->compressed && missing)die("[RED] [vk] atlas mapping changed during snapshot");previous=native;}
            uint32_t cw=mip<c->tail?c->tw:w,ch=mip<c->tail?c->th:h;size_t pitch=((cw+f->bw-1)/f->bw)*f->bpb,bytes=pitch*((ch+f->bh-1)/f->bh);
            if(bytes>65536)die("[RED] [vk] atlas cell upload size exceeds native page");
            unsigned sh,sd;nvn_tex_level_tiles(&t->d,mip,&sh,&sd);nvn_texdesc local=t->d;local.target=NVN_TEXTURE_TARGET_2D;local.flags=0;local.width=cw;local.height=ch;local.depth=local.levels=1;local.pkg_block_h=(int)sh+1;
            uint64_t so=mip<c->tail?0:nvn_tex_level_offset(&t->d,mip)-nvn_tex_level_offset(&t->d,c->tail);
            if(nvn_deswizzle(&local,0,0,source+so,linear,pitch))die("[RED] [vk] atlas native deswizzle failed");
            va_key key={.w=cw,.h=ch};CC_SHA256(linear,(CC_LONG)bytes,key.digest);int fresh;uint32_t id=cell_get(c,&key,&fresh);c->cell[id].refs++;table[index]=id;
            if(fresh){if(g_stage_used+bytes>VA_STAGE || g_ncopy==256)upload_flush(c);transfer_init();memcpy(g_stage_map+g_stage_used,linear,bytes);
                // A small logical mip occupies complete compressed blocks in
                // an interior cache cell; the copy extent must cover those blocks.
                uint32_t upload_w=(cw+f->bw-1)/f->bw*f->bw,upload_h=(ch+f->bh-1)/f->bh*f->bh;
                g_copy[g_ncopy++]=(VkBufferImageCopy){g_stage_used,0,0,{VK_IMAGE_ASPECT_COLOR_BIT,0,id/(VA_GRID*VA_GRID),1},{(int32_t)((id%VA_GRID)*c->tw),(int32_t)(((id/VA_GRID)%VA_GRID)*c->th),0},{upload_w,upload_h,1}};g_stage_used+=bytes;}
        }
    }
    upload_flush(c);free(source);free(linear);c->table=table;c->gen=gen;c->stamp=stamp;c->revision++;__atomic_add_fetch(&g_atlas_gen,1,__ATOMIC_RELEASE);
    c->mapped_entries=mapped_entries;c->mapped_native_pages=mapped_pages;c->total_native_pages=total_pages;
    if(!c->used_fence && c->slots)cache_size(c,c->slots,f);   // startup deduplication can release the conservative allocation immediately
}
static VkComponentSwizzle channel(uint32_t x){return x==0?VK_COMPONENT_SWIZZLE_ZERO:x==1?VK_COMPONENT_SWIZZLE_ONE:(VkComponentSwizzle)(VK_COMPONENT_SWIZZLE_R+x-2);}
static VkComponentMapping view_swizzle(const tex_t *t,const view_t *v,const vkfmt_t *f) {
    VkComponentSwizzle cur[4]={f->swz.r,f->swz.g,f->swz.b,f->swz.a};for(unsigned i=0;i<4;i++)if(!cur[i])cur[i]=(VkComponentSwizzle)(VK_COMPONENT_SWIZZLE_R+i);
    if(t->set_swz){VkComponentSwizzle old[4];memcpy(old,cur,sizeof old);for(unsigned i=0;i<4;i++){uint32_t x=t->swz>>(3*i)&7;if(x>5)die("[RED] [vk] invalid atlas channel swizzle");cur[i]=x<2?channel(x):old[x-2];}}
    if(v && v->set_swizzle){VkComponentSwizzle old[4];memcpy(old,cur,sizeof old);for(unsigned i=0;i<4;i++){uint32_t x=v->swz[i];if(x>5)die("[RED] [vk] invalid atlas channel swizzle");cur[i]=x<2?channel(x):old[x-2];}}
    return (VkComponentMapping){cur[0],cur[1],cur[2],cur[3]};
}
// Physical atlas images have one mip. Guest filter/LOD rules remain in metadata;
// this sampler is used only by the shader's same-tile bilinear fast path.
static int atlas_native_filter(int usable,VkDescriptorImageInfo *image){
    static VkSampler sampler;
    // Live A/B from the diagnostic console; descriptor metadata is rebuilt for
    // each submission, so the hardware bilinear fast path can be priced there.
    // The caller reads DM_VK_ATLAS_NATIVE_FILTER once per submission and passes
    // it with the context's linear-filter support.
    if(!usable)return 0;
    if(!sampler){VkSamplerCreateInfo ci={.sType=VK_STRUCTURE_TYPE_SAMPLER_CREATE_INFO,.magFilter=VK_FILTER_LINEAR,.minFilter=VK_FILTER_LINEAR,.mipmapMode=VK_SAMPLER_MIPMAP_MODE_NEAREST,.addressModeU=VK_SAMPLER_ADDRESS_MODE_CLAMP_TO_EDGE,.addressModeV=VK_SAMPLER_ADDRESS_MODE_CLAMP_TO_EDGE,.addressModeW=VK_SAMPLER_ADDRESS_MODE_CLAMP_TO_EDGE,.maxAnisotropy=1};VKCHK(vkCreateSampler(V.dev,&ci,NULL,&sampler));}
    image->sampler=sampler;return 1;
}
int vk_atlas_descriptor(const tex_t *t,const view_t *view,VkSampler sampler,VkDescriptorImageInfo *image,VkDescriptorBufferInfo *meta,int directional) {
    if(!t || !vk_atlas_enabled())return 0;
    const vkfmt_t *f=vk_fmt(t->d.format);int compressed=vk_atlas_candidate(t);
    // The same sampler represents CPU-streamed uncompressed arrays. Render and
    // storage destinations must retain their writable compatibility images.
    if(!compressed && !(t->pool && t->mem && nvn_sparse_pool(t->pool) && (t->d.flags&NVN_TEXTURE_FLAGS_SPARSE) && !(t->d.flags&NVN_TEXTURE_FLAGS_IMAGE)
        && (t->d.target==NVN_TEXTURE_TARGET_2D_ARRAY || t->d.target==NVN_TEXTURE_TARGET_2D) && t->d.samples<=1 && f && !f->compressed && !f->depth && !f->stencil && !f->is_int && f->bw==1 && f->bh==1
        && !vk_tex_gpu_content(t)))return 0;
    pthread_mutex_lock(&g_atlas_mu);collect();
    samp_par sp;if(!vk_samp_parameters(sampler,&sp))die("[RED] [vk] atlas sampler parameters unavailable");
    if(sp.minf>5 || sp.cmp_mode || sp.reduction || (sp.aniso>1 && directional) || sp.lod_bias!=0 || (sp.ws>1 && sp.ws!=NVN_WRAP_MODE_CLAMP_TO_EDGE) || (sp.wt>1 && sp.wt!=NVN_WRAP_MODE_CLAMP_TO_EDGE) || (view && view->set_format && (!vk_fmt(view->format) || vk_fmt(view->format)->vk!=f->vk)) || (view && view->set_target && view->target!=NVN_TEXTURE_TARGET_2D_ARRAY && view->target!=NVN_TEXTURE_TARGET_2D)){
        if(!compressed){pthread_mutex_unlock(&g_atlas_mu);return 0;}
        die("[RED] [vk] atlas sampler/view mode is not implemented (filter %u/%u wrap %u/%u bias %g aniso %g compare %u reduction %u)",sp.minf,sp.magf,sp.ws,sp.wt,sp.lod_bias,sp.aniso,sp.cmp_mode,sp.reduction);}
    va_context *c=context(t);uint64_t epoch=mtl_last_fence()+1,gen=nvn_sparse_gen(),stamp=nvn_dirty_now();int cached=check_cache_enabled();
    // Live switches, read once per submission instead of per descriptor (under g_atlas_mu); this also keeps the sampler and data[15] consistent within it.
    static uint64_t env_epoch;static int native_on,residency_big;if(env_epoch!=epoch){const char *e=getenv("DM_VK_ATLAS_NATIVE_FILTER");native_on=e && atoi(e);e=getenv("DM_VK_ATLAS_RESIDENCY");residency_big=e && !strcmp(e,"big");env_epoch=epoch;}
    // Finalizing physical storage drains replay but does not bump the mapping
    // generation. Recheck readability each submission as well as each remap.
    // GPU ownership above is always checked, including within a submission.
    if(!compressed){
        if(!cached || c->cpu_epoch!=epoch || c->cpu_gen!=gen){c->cpu_readable=nvn_sparse_cpu_readable(t->pool,(uint64_t)(uintptr_t)t->mem,t->L.size);c->cpu_epoch=epoch;c->cpu_gen=gen;}
        if(!c->cpu_readable){pthread_mutex_unlock(&g_atlas_mu);return 0;}
    }
    // Remember negative content checks too. Unrelated pool writes/remaps used
    // to make every descriptor walk the same gigabytes of unchanged pages.
    // Capture versions before walking: a concurrent later change must still
    // invalidate the next lookup, even if it occurs during this check/build.
    if(!c->table || !cached || c->checked_gen!=gen || c->checked_stamp!=stamp){
        if(!c->table || nvn_sparse_since(t->pool,(uint64_t)(uintptr_t)t->mem,t->L.size,c->gen,c->stamp))plan_build(c,t,f);
        c->checked_gen=gen;c->checked_stamp=stamp;
    }
    // DM_VK_ATLAS_RESIDENCY=big (live): census large virtual textures after
    // their current page tables are built; distinct cells reflect deduplication.
    if(residency_big && t->d.width>=8192 && t->d.height>=8192 && t->L.layers>=64 && c->reported_revision!=c->revision){
        uint32_t active=0;for(uint32_t i=0;i<c->slots;i++)if(c->cell[i].refs)active++;
        VKLOG("atlas residency: serial %llu format %#x %ux%ux%u levels %u mapped-pages %llu/%llu mapped-entries %llu/%u unique-cells %u packed-bytes %llu revision %llu",
            (unsigned long long)t->serial,t->d.format,t->d.width,t->d.height,t->L.layers,t->d.levels,
            (unsigned long long)c->mapped_native_pages,(unsigned long long)c->total_native_pages,
            (unsigned long long)c->mapped_entries,c->count-VA_HEADER,active,(unsigned long long)c->allocated,(unsigned long long)c->revision);
        c->reported_revision=c->revision;
    }
    if(c->used_fence!=epoch || c->referenced_revision!=c->revision){for(uint32_t i=VA_HEADER;i<c->count;i++)if(c->table[i]!=VA_MISSING)c->cell[c->table[i]].fence=epoch;c->used_fence=epoch;c->referenced_revision=c->revision;}
    int native_filter=atlas_native_filter(native_on && c->filter_linear,image);
    c->used_frame=g_tex_frame;view_t v={0};if(view)v=*view;
    if(c->binding.epoch==epoch && c->binding.revision==c->revision && !memcmp(&c->binding.view,&v,sizeof v) && !memcmp(&c->binding.sampler,&sp,sizeof sp)){image->imageView=c->binding.image;image->imageLayout=VK_IMAGE_LAYOUT_GENERAL;*meta=c->binding.meta;pthread_mutex_unlock(&g_atlas_mu);return 1;}
    VkComponentMapping swz=view_swizzle(t,view,f);va_view *vv=c->views;while(vv && memcmp(&vv->swz,&swz,sizeof swz))vv=vv->next;
    va_view empty={.view=VK_NULL_HANDLE};
    if(!c->image){empty.view=vk_dummy_view(1,1,0,0,0);vv=&empty;}
    if(!vv){vv=calloc(1,sizeof*vv);vv->swz=swz;VkImageViewCreateInfo ci={VK_STRUCTURE_TYPE_IMAGE_VIEW_CREATE_INFO,NULL,0,c->image,VK_IMAGE_VIEW_TYPE_2D_ARRAY,f->vk,swz,{VK_IMAGE_ASPECT_COLOR_BIT,0,1,0,c->layers}};VKCHK(vkCreateImageView(V.dev,&ci,NULL,&vv->view));vv->next=c->views;c->views=vv;}
    VkBuffer buffer;VkDeviceSize offset;size_t bytes=(size_t)c->count*4;uint32_t *data=vk_scratch(bytes,V.props.limits.minStorageBufferOffsetAlignment,&buffer,&offset);memcpy(data,c->table,bytes);
    uint32_t first=v.set_levels?v.base_level:0,levels=v.set_levels?v.nlevels:t->d.levels-first,layer=v.set_layers?v.min_layer:0,layers=v.set_layers?v.nlayers:t->L.layers-layer;
    if(first>=t->d.levels || !levels || first+levels>t->d.levels || layer>=t->L.layers || !layers || layer+layers>t->L.layers)die("[RED] [vk] invalid atlas view range");
    data[0]=1;data[1]=levels;data[2]=first;data[3]=layer;data[4]=layers;data[5]=c->tw;data[6]=c->th;data[7]=VA_GRID;data[8]=sp.minf;data[9]=sp.magf;data[10]=sp.ws;data[11]=sp.wt;
    memcpy(data+12,&sp.lod_min,4);float maximum=sp.minf<=1?.25f:sp.lod_max;memcpy(data+13,&maximum,4);
    memcpy(data+14,&V.props.limits.maxSamplerLodBias,4);
    data[15]=(uint32_t)native_filter;
    float raw[4]={0,0,0,0};if((!f->compressed && t->d.format<0x25) || f->vk==VK_FORMAT_BC6H_UFLOAT_BLOCK || f->vk==VK_FORMAT_BC6H_SFLOAT_BLOCK || f->vk==VK_FORMAT_BC1_RGB_UNORM_BLOCK || f->vk==VK_FORMAT_BC1_RGB_SRGB_BLOCK || (f->vk>=VK_FORMAT_BC4_UNORM_BLOCK && f->vk<=VK_FORMAT_BC5_SNORM_BLOCK))raw[3]=1;
    const VkComponentSwizzle *map=&swz.r;float hole[4];for(unsigned i=0;i<4;i++)hole[i]=map[i]==VK_COMPONENT_SWIZZLE_ZERO?0:map[i]==VK_COMPONENT_SWIZZLE_ONE?1:raw[map[i]-VK_COMPONENT_SWIZZLE_R];memcpy(data+16,hole,16);
    *meta=(VkDescriptorBufferInfo){buffer,offset,bytes};image->imageView=vv->view;image->imageLayout=VK_IMAGE_LAYOUT_GENERAL;
    c->binding.view=v;c->binding.sampler=sp;c->binding.epoch=epoch;c->binding.revision=c->revision;c->binding.image=vv->view;c->binding.meta=*meta;g_metadata+=bytes;pthread_mutex_unlock(&g_atlas_mu);return 1;
}
static void context_free(va_context *c) {
    retire(c);plan_release(c);free(c->cell);nvn_hm_clear(&c->by_content,NULL);free(c->by_content.keys);free(c->by_content.vals);free(c);
}
void vk_atlas_drop_pool(const void *pool) {
    pthread_mutex_lock(&g_atlas_mu);va_context **link=&g_context;
    while(*link){va_context *c=*link;if(c->pool!=pool){link=&c->next;continue;}*link=c->next;context_free(c);}
    collect();pthread_mutex_unlock(&g_atlas_mu);
}
void vk_atlas_sweep(uint64_t frame) {
    if(!vk_atlas_enabled() || frame%60)return;
    pthread_mutex_lock(&g_atlas_mu);uint64_t done=vk_fence_done();va_context **link=&g_context;
    while(*link){va_context *c=*link;if(frame<=c->used_frame+60 || c->used_fence>done){link=&c->next;continue;}*link=c->next;context_free(c);}
    collect();pthread_mutex_unlock(&g_atlas_mu);
}
void vk_atlas_stats(uint64_t *allocated,uint64_t *uploaded,uint64_t *reused,uint64_t *metadata){pthread_mutex_lock(&g_atlas_mu);collect();*allocated=g_allocated;*uploaded=g_uploaded;*reused=g_reused;*metadata=g_metadata;pthread_mutex_unlock(&g_atlas_mu);}

uint64_t vk_atlas_peak_bytes(void){pthread_mutex_lock(&g_atlas_mu);uint64_t peak=g_peak_allocated;pthread_mutex_unlock(&g_atlas_mu);return peak;}
// What vk_atlas_descriptor rechecks per call besides the texture, view, sampler and submission: tables and images, GPU ownership, sparse remaps and
// first CPU writes to protected pages. Every term only increases, so the sum is unchanged only if each term is (gfx_vk_exec.c set_memo_get, setmemo 3).
uint64_t vk_atlas_version(void){return __atomic_load_n(&g_atlas_gen,__ATOMIC_ACQUIRE)+nvn_sparse_gen()+nvn_dirty_now()+vk_image_ownership_gen();}
