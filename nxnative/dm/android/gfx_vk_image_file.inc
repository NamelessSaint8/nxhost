// Optional lossless retention of inactive GPU images. Keep ownership and image
// metadata, but save every mip/layer/aspect before releasing completed storage.
// The next lookup restores GPU bytes before any new command can use the image.
#include <fcntl.h>
#define IF_STAGE (8u<<20)
typedef struct image_file_span {uint64_t offset,bytes;struct image_file_span *next;} image_file_span;
static image_file_span *g_if_free;
static int g_if_fd=-1;static uint64_t g_if_end,g_if_slots,g_if_paged,g_if_saved,g_if_loaded;
static uint64_t g_if_restored_count,g_if_restored_bytes,g_if_restore_ns;
static uint64_t image_file_clock(void){struct timespec t;clock_gettime(CLOCK_MONOTONIC,&t);return (uint64_t)t.tv_sec*1000000000ull+t.tv_nsec;}
static VkCommandPool g_if_pool;static VkCommandBuffer g_if_cmd;static VkFence g_if_fence;
static VkBuffer g_if_buffer;static VkDeviceMemory g_if_memory;static uint8_t *g_if_map;
extern pthread_mutex_t g_vk_queue_mu;
static uint64_t image_file_budget(void){
    static uint64_t value=UINT64_MAX;
    if(value==UINT64_MAX){const char *e=getenv("DM_VK_IMAGE_BUDGET_MB");value=e && strtoull(e,NULL,10)>0?strtoull(e,NULL,10)<<20:0;}
    return value;
}
static void image_file_init(void){
    if(g_if_fd>=0)return;const char *directory=getenv("DM_TEMP");if(!directory || !*directory)die("[RED] GPU image backing requires private DM_TEMP");
    char path[1200];if(snprintf(path,sizeof path,"%s/nvn-images-XXXXXX",directory)>=(int)sizeof path)die("[RED] GPU image backing path is too long");
    g_if_fd=mkstemp(path);if(g_if_fd<0)die("[RED] create GPU image backing: %s",strerror(errno));if(unlink(path))die("[RED] unlink private GPU image backing: %s",strerror(errno));fcntl(g_if_fd,F_SETFD,FD_CLOEXEC);
    VkCommandPoolCreateInfo pool={.sType=VK_STRUCTURE_TYPE_COMMAND_POOL_CREATE_INFO,.flags=VK_COMMAND_POOL_CREATE_RESET_COMMAND_BUFFER_BIT,.queueFamilyIndex=V.qf};VKCHK(vkCreateCommandPool(V.dev,&pool,NULL,&g_if_pool));
    VkCommandBufferAllocateInfo command={.sType=VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO,.commandPool=g_if_pool,.level=VK_COMMAND_BUFFER_LEVEL_PRIMARY,.commandBufferCount=1};VKCHK(vkAllocateCommandBuffers(V.dev,&command,&g_if_cmd));
    VkFenceCreateInfo fence={.sType=VK_STRUCTURE_TYPE_FENCE_CREATE_INFO};VKCHK(vkCreateFence(V.dev,&fence,NULL,&g_if_fence));
    VkBufferCreateInfo buffer={.sType=VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO,.size=IF_STAGE,.usage=VK_BUFFER_USAGE_TRANSFER_SRC_BIT|VK_BUFFER_USAGE_TRANSFER_DST_BIT,.sharingMode=VK_SHARING_MODE_EXCLUSIVE};VKCHK(vkCreateBuffer(V.dev,&buffer,NULL,&g_if_buffer));
    VkMemoryRequirements req;vkGetBufferMemoryRequirements(V.dev,g_if_buffer,&req);VkMemoryAllocateInfo memory={.sType=VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO,.allocationSize=req.size,.memoryTypeIndex=vk_mem_type(req.memoryTypeBits,VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT|VK_MEMORY_PROPERTY_HOST_COHERENT_BIT,0)};VKCHK(vk_memory_allocate(V.dev,&memory,NULL,&g_if_memory));VKCHK(vkBindBufferMemory(V.dev,g_if_buffer,g_if_memory,0));VKCHK(vkMapMemory(V.dev,g_if_memory,0,IF_STAGE,0,(void**)&g_if_map));
}
static uint64_t image_file_allocate(uint64_t bytes){
    uint64_t rounded=(bytes+4095)&~4095ull;image_file_span **at=&g_if_free;
    while(*at){image_file_span *span=*at;if(span->bytes>=rounded){uint64_t offset=span->offset;span->offset+=rounded;span->bytes-=rounded;if(!span->bytes){*at=span->next;free(span);}g_if_slots++;return offset;}at=&span->next;}
    if(rounded>INT64_MAX-g_if_end)die("[RED] GPU image backing size overflow");uint64_t offset=g_if_end;g_if_end+=rounded;g_if_slots++;return offset;
}
static void image_file_release(vkimg_t *im){
    if(!im->file_bytes)return;if(im->file_paged)g_if_paged-=im->file_bytes;
    image_file_span *span=malloc(sizeof*span);if(!span)die("[RED] GPU image backing free-list allocation failed");*span=(image_file_span){im->file_offset,(im->file_bytes+4095)&~4095ull,g_if_free};g_if_free=span;im->file_bytes=0;
    if(!--g_if_slots){close(g_if_fd);g_if_fd=-1;g_if_end=0;while(g_if_free){span=g_if_free;g_if_free=span->next;free(span);}
        vkUnmapMemory(V.dev,g_if_memory);vkDestroyBuffer(V.dev,g_if_buffer,NULL);vk_memory_free(V.dev,g_if_memory,NULL);vkDestroyFence(V.dev,g_if_fence,NULL);
        PFN_vkDestroyCommandPool destroy=(PFN_vkDestroyCommandPool)vkGetDeviceProcAddr(V.dev,"vkDestroyCommandPool");destroy(V.dev,g_if_pool,NULL);g_if_pool=VK_NULL_HANDLE;g_if_map=NULL;
    }
}
static void image_file_io(uint64_t offset,size_t bytes,int restore){
    for(size_t done=0;done<bytes;){ssize_t n=restore?pread(g_if_fd,g_if_map+done,bytes-done,(off_t)(offset+done)):pwrite(g_if_fd,g_if_map+done,bytes-done,(off_t)(offset+done));
        if(n<0 && errno==EINTR)continue;if(n<=0)die("[RED] %s GPU image backing: %s",restore?"read":"write",n<0?strerror(errno):"short file");done+=(size_t)n;}
}
static unsigned image_file_bpp(const vkimg_t *im,VkImageAspectFlags aspect){
    if(aspect==VK_IMAGE_ASPECT_STENCIL_BIT)return 1;
    if(aspect==VK_IMAGE_ASPECT_DEPTH_BIT)return im->fmt==VK_FORMAT_D16_UNORM?2:4;
    const vkfmt_t *f=vk_fmt(im->nvn_format);return f && !f->compressed && !f->bc?f->bpb:0;
}
static uint64_t image_file_size(const vkimg_t *im){
    if(im->samples!=1 || !im->levels || !im->layers)return 0;uint64_t bytes=0;unsigned bpp=0;
    for(unsigned aspect=1;aspect<=VK_IMAGE_ASPECT_STENCIL_BIT;aspect<<=1)if(im->aspect&aspect){unsigned n=image_file_bpp(im,aspect);if(!n)return 0;bpp+=n;}
    if((uint64_t)im->w*bpp>IF_STAGE)return 0;
    for(unsigned mip=0;mip<im->levels;mip++){uint64_t w=im->w>>mip,h=im->h>>mip,d=im->d>>mip;if(!w)w=1;if(!h)h=1;if(!d)d=1;uint64_t n=w*h*d*im->layers*bpp;if(n>INT64_MAX-bytes)return 0;bytes+=n;}
    return bytes;
}
static void image_file_transfer(vkimg_t *im,VkBufferImageCopy *region,int restore){
    VKCHK(vkResetCommandBuffer(g_if_cmd,0));VKCHK(vkResetFences(V.dev,1,&g_if_fence));VkCommandBufferBeginInfo begin={.sType=VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO,.flags=VK_COMMAND_BUFFER_USAGE_ONE_TIME_SUBMIT_BIT};VKCHK(vkBeginCommandBuffer(g_if_cmd,&begin));
    VkImageMemoryBarrier image={.sType=VK_STRUCTURE_TYPE_IMAGE_MEMORY_BARRIER,.srcAccessMask=im->layout==VK_IMAGE_LAYOUT_UNDEFINED?0:VK_ACCESS_MEMORY_READ_BIT|VK_ACCESS_MEMORY_WRITE_BIT,.dstAccessMask=restore?VK_ACCESS_TRANSFER_WRITE_BIT:VK_ACCESS_TRANSFER_READ_BIT,.oldLayout=im->layout,.newLayout=VK_IMAGE_LAYOUT_GENERAL,.srcQueueFamilyIndex=VK_QUEUE_FAMILY_IGNORED,.dstQueueFamilyIndex=VK_QUEUE_FAMILY_IGNORED,.image=im->img,.subresourceRange={im->aspect,0,im->levels,0,im->layers}};
    vkCmdPipelineBarrier(g_if_cmd,VK_PIPELINE_STAGE_ALL_COMMANDS_BIT,VK_PIPELINE_STAGE_TRANSFER_BIT,0,0,NULL,0,NULL,1,&image);im->layout=VK_IMAGE_LAYOUT_GENERAL;
    VkMemoryBarrier host={.sType=VK_STRUCTURE_TYPE_MEMORY_BARRIER,.srcAccessMask=restore?VK_ACCESS_HOST_WRITE_BIT:VK_ACCESS_TRANSFER_WRITE_BIT,.dstAccessMask=restore?VK_ACCESS_TRANSFER_READ_BIT:VK_ACCESS_HOST_READ_BIT};
    if(restore){vkCmdPipelineBarrier(g_if_cmd,VK_PIPELINE_STAGE_HOST_BIT,VK_PIPELINE_STAGE_TRANSFER_BIT,0,1,&host,0,NULL,0,NULL);vkCmdCopyBufferToImage(g_if_cmd,g_if_buffer,im->img,VK_IMAGE_LAYOUT_GENERAL,1,region);vk_img_barrier_all(g_if_cmd);}
    else{vkCmdCopyImageToBuffer(g_if_cmd,im->img,VK_IMAGE_LAYOUT_GENERAL,g_if_buffer,1,region);vkCmdPipelineBarrier(g_if_cmd,VK_PIPELINE_STAGE_TRANSFER_BIT,VK_PIPELINE_STAGE_HOST_BIT,0,1,&host,0,NULL,0,NULL);}
    VKCHK(vkEndCommandBuffer(g_if_cmd));VkSubmitInfo submit={.sType=VK_STRUCTURE_TYPE_SUBMIT_INFO,.commandBufferCount=1,.pCommandBuffers=&g_if_cmd};pthread_mutex_lock(&g_vk_queue_mu);VkResult result=vkQueueSubmit(V.q,1,&submit,g_if_fence);pthread_mutex_unlock(&g_vk_queue_mu);VKCHK(result);result=vkWaitForFences(V.dev,1,&g_if_fence,VK_TRUE,10000000000ull);if(result!=VK_SUCCESS)die("[RED] GPU image backing transfer did not finish: %d",result);
}
static void image_file_pixels(vkimg_t *im,int restore){
    uint64_t offset=im->file_offset;
    for(unsigned mip=0;mip<im->levels;mip++){uint32_t w=im->w>>mip,h=im->h>>mip,d=im->d>>mip;if(!w)w=1;if(!h)h=1;if(!d)d=1;
        for(unsigned layer=0;layer<im->layers;layer++)for(unsigned aspect=1;aspect<=VK_IMAGE_ASPECT_STENCIL_BIT;aspect<<=1)if(im->aspect&aspect){unsigned bpp=image_file_bpp(im,aspect);size_t row=(size_t)w*bpp;uint32_t rows=(uint32_t)(IF_STAGE/row);
            for(unsigned z=0;z<d;z++)for(unsigned y=0;y<h;){uint32_t n=h-y<rows?h-y:rows;size_t bytes=row*n;VkBufferImageCopy region={.imageSubresource={aspect,mip,layer,1},.imageOffset={0,(int32_t)y,(int32_t)z},.imageExtent={w,n,1}};
                if(restore)image_file_io(offset,bytes,1);image_file_transfer(im,&region,restore);if(!restore)image_file_io(offset,bytes,0);offset+=bytes;y+=n;
            }
        }
    }
    if(offset-im->file_offset!=im->file_bytes)die("[RED] GPU image backing layout mismatch");
}
static void image_file_restore(vkimg_t *im){
    uint64_t start=image_file_clock();
    tex_t t={.d={.width=im->w,.height=im->h,.depth=im->target==NVN_TEXTURE_TARGET_3D?im->d:im->layers,.levels=im->levels,.samples=im->samples,.target=im->target,.format=im->nvn_format,.flags=im->flags}};
    if(im->target==NVN_TEXTURE_TARGET_1D_ARRAY)t.d.height=im->layers;
    vkimg_t *fresh=img_new(&t,vk_fmt(im->nvn_format));if(!fresh)die("[RED] restore GPU image allocation failed");
    if(fresh->w!=im->w || fresh->h!=im->h || fresh->d!=im->d || fresh->layers!=im->layers || fresh->fmt!=im->fmt)die("[RED] restored GPU image layout differs");
    im->img=fresh->img;im->mem=fresh->mem;im->sub=fresh->sub;im->device_bytes=fresh->device_bytes;im->layout=fresh->layout;im->usage=fresh->usage;im->cflags=fresh->cflags;im->fixed_fmt=fresh->fixed_fmt;im->fmt2=fresh->fmt2;free(fresh);
    image_file_pixels(im,1);im->file_paged=0;g_if_paged-=im->file_bytes;g_if_loaded+=im->file_bytes;g_if_restored_bytes+=im->file_bytes;g_if_restored_count++;g_if_restore_ns+=image_file_clock()-start;
}
static void image_file_trim(void){
    uint64_t budget=image_file_budget(),resident=0,done=vk_fence_done();if(!budget)return;
    for(int table=0;table<2;table++){nvn_hmap *map=table?&g_by_serial:&g_by_key;for(uint32_t i=0;i<map->cap;i++){vkimg_t *im=map->vals[i];if(im && im->img)resident+=im->device_bytes;}}
    uint64_t before=resident,start=image_file_clock(),written=0;unsigned evicted=0,rebuild=0;
    while(resident>budget){vkimg_t *old=NULL;uint64_t bytes=0;nvn_hmap *old_map=NULL;uint32_t old_index=0;
        for(int table=0;table<2;table++){nvn_hmap *map=table?&g_by_serial:&g_by_key;for(uint32_t i=0;i<map->cap;i++){vkimg_t *im=map->vals[i];
            if(!im || !im->img || im->layout!=VK_IMAGE_LAYOUT_GENERAL || im->last_use>done || im->used==g_tex_frame || im->device_bytes<(1u<<20))continue;
            if(g_tex_frame<im->used+60 && (!im->touch_ns || start<im->touch_ns || start-im->touch_ns<5000000000ull))continue;
            uint64_t n=im->gpu_w?image_file_size(im):0;
            // Packaged CPU images can be reconstructed from their live pool's
            // canonical bytes. GPU-written images always require a pixel save.
            if(n || (!table && !im->gpu_w && im->packaged && im->samples==1)){
                if(old && (im->gpu_w>old->gpu_w || (im->gpu_w==old->gpu_w && im->used>=old->used)))continue;
                old=im;bytes=n;old_map=map;old_index=i;}
        }}
        if(!old)break;
        if(!old->gpu_w){akey key;memcpy(&key,old_map->keys+(size_t)old_index*old_map->klen,sizeof key);nvn_hm_del(old_map,&key);resident-=old->device_bytes;img_drop_completed(old);rebuild++;if(rebuild+evicted>=8 || image_file_clock()-start>=8000000ull)break;continue;}
        image_file_init();if(!old->file_bytes){old->file_offset=image_file_allocate(bytes);old->file_bytes=bytes;}else if(old->file_bytes!=bytes)die("[RED] GPU image backing size changed");
        image_file_pixels(old,0);if(fdatasync(g_if_fd))die("[RED] sync GPU image backing: %s",strerror(errno));posix_fadvise(g_if_fd,(off_t)old->file_offset,(off_t)old->file_bytes,POSIX_FADV_DONTNEED);
        vk_lrz_forget(old);vk_tex_view_drop_all_mode(old,1);if(old->full){vkDestroyImageView(V.dev,old->full,NULL);old->full=VK_NULL_HANDLE;}vk_free_completed_image(old->img,old->mem,old->sub);
        old->img=VK_NULL_HANDLE;old->mem=VK_NULL_HANDLE;old->sub=NULL;old->file_paged=1;g_if_paged+=bytes;g_if_saved+=bytes;resident-=old->device_bytes;written+=bytes;evicted++;
        // Spread transitions across presents instead of saving gigabytes in a
        // single sweep. An image remains atomic; its pixels cannot be dropped.
        if(written>=(32u<<20) || evicted+rebuild>=8 || image_file_clock()-start>=8000000ull)break;
    }
    if(evicted)VKLOG("GPU image file cache: saved %u inactive images, resident %.2f -> %.2f MiB, retained file pixels %.2f MiB, save %.2f ms",evicted,before/1048576.0,resident/1048576.0,g_if_paged/1048576.0,(image_file_clock()-start)/1e6);
    if(rebuild)VKLOG("CPU image cache: released %u inactive copies, resident %.2f -> %.2f MiB (canonical source retained)",rebuild,before/1048576.0,resident/1048576.0);
    if(g_if_restored_count){VKLOG("GPU image file cache: restored %llu images, %.2f MiB in %.2f ms since last sweep",(unsigned long long)g_if_restored_count,g_if_restored_bytes/1048576.0,g_if_restore_ns/1e6);g_if_restored_count=g_if_restored_bytes=g_if_restore_ns=0;}
}
void vk_image_file_stats(uint64_t *paged,uint64_t *saved,uint64_t *loaded){pthread_mutex_lock(&g_img_mu);*paged=g_if_paged;*saved=g_if_saved;*loaded=g_if_loaded;pthread_mutex_unlock(&g_img_mu);}
