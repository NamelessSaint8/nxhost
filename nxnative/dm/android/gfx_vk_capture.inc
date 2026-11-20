// Opt-in, bounded compute capture. Raw GPU copies preserve packed texel
// bits; no colour conversion or substitution. Included by gfx_vk_exec.c.
// DM_VK_CAPTURE_CS=<key>#<minimum-present>, once per request, under DM_ROOT.
// DM_VK_CAPTURE_FRAME=N captures each dispatch of one frame. FRAME_KEY limits
// that frame to one shader. POOLS=1 adds v2 full pools and descriptor aliases;
// POOL_ADDRS supplies extra indirect destinations.
// Both versions deliberately refuse arrays, mip chains, compressed/depth images,
// atlas bindings and indirect dispatches rather than writing an incomplete replay.
static struct {
    FILE *file; char base[1024]; unsigned n, version, npool;
    struct {vkpool_t *pool;VkBuffer staging;VkDeviceSize offset;void *data;} pools[16];
    struct {
        unsigned binding, type, image, bytes_per_pixel;
        VkDescriptorBufferInfo buffer;
        vkimg_t *im; VkImageViewCreateInfo view;
        VkDeviceSize size, offset; VkBuffer staging; void *data;
    } item[32];
} g_cscap;
static void cscap_write(const char *suffix, const void *data, size_t size) {
    char path[1200]; snprintf(path,sizeof path,"%s.%s",g_cscap.base,suffix);
    FILE *f=fopen(path,"wb"); if(!f)die("[RED] compute capture cannot write %s",path);
    if(fwrite(data,1,size,f)!=size)die("[RED] short compute capture write: %s",path);
    if(fclose(f))die("[RED] compute capture close failed: %s",path);
}
static int cscap_begin(const vkshader_t *cs, const p_dispatch *d) {
    const char *e=getenv("DM_VK_CAPTURE_CS"); static char done[128];
    const char *frame=getenv("DM_VK_CAPTURE_FRAME");int all=frame&&*frame;static unsigned sequence;
    uint64_t key=cs->key,present=0;
    if(all){
        char *end;present=strtoull(frame,&end,10);
        if(end==frame || *end || present!=g_tex_frame)return 0;
        const char *filter=getenv("DM_VK_CAPTURE_FRAME_KEY");
        if(filter && *filter){
            key=strtoull(filter,&end,16);
            if(end==filter || *end || key!=cs->key)return 0;
        }
    }
    else{
        if(!e || !*e || !strcmp(e,done))return 0;
        char *end;key=strtoull(e,&end,16);
        if(end==e)return 0;
        if(*end=='#'){char *last;present=strtoull(end+1,&last,10);if(last==end+1 || *last)return 0;}
        else if(*end)return 0;
    }
    if(key!=cs->key || g_tex_frame<present)return 0;
    if((!all&&strlen(e)>=sizeof done) || d->ind || cs->atlas_specs)die("[RED] unsupported compute capture request");
    const char *root=getenv("DM_ROOT");if(!root)die("[RED] compute capture needs DM_ROOT");
    memset(&g_cscap,0,sizeof g_cscap);if(!all)snprintf(done,sizeof done,"%s",e);
    snprintf(g_cscap.base,sizeof g_cscap.base,"%s/capture_%016llx_%llu",root,(unsigned long long)key,(unsigned long long)g_tex_frame);
    if(all){size_t len=strlen(g_cscap.base);snprintf(g_cscap.base+len,sizeof g_cscap.base-len,"_%u",sequence++);}
    char path[1100];snprintf(path,sizeof path,"%s.tsv",g_cscap.base);g_cscap.file=fopen(path,"w");
    if(!g_cscap.file)die("[RED] cannot create compute capture manifest");
    g_cscap.version=getenv("DM_VK_CAPTURE_POOLS") && atoi(getenv("DM_VK_CAPTURE_POOLS"))?2:1;
    fprintf(g_cscap.file,"capture %u\ndispatch %016llx %u %u %u\n",g_cscap.version,(unsigned long long)key,d->x,d->y,d->z);
    for(int i=0;i<cs->nbind;i++)if(cs->b[i].kind==RK_GMEM_MAP || cs->b[i].kind==RK_GMEM_LOG)
        fprintf(g_cscap.file,"global_memory %u %s\n",cs->b[i].binding,cs->b[i].kind==RK_GMEM_MAP?"map":"log"); // old replay tools reject unrelocated device pointers
    cscap_write("push.bin",S.push[1],DMSH_PUSH_SIZE);
    VKLOG("compute capture begin: %s",g_cscap.base);return 1;
}
static void cscap_buffer(unsigned binding, unsigned type, const VkDescriptorBufferInfo *info) {
    if(!g_cscap.file)return;
    if(g_cscap.n==32 || !info->range || info->range>64*1024*1024 || info->range%4)die("[RED] unsupported compute capture buffer");
    unsigned i=g_cscap.n++;g_cscap.item[i].binding=binding;g_cscap.item[i].type=type;g_cscap.item[i].buffer=*info;g_cscap.item[i].size=info->range;
    fprintf(g_cscap.file,"buffer %u %u %llu\n",binding,type,(unsigned long long)info->range);
}
static void cscap_cpu(unsigned binding, uint64_t address, uint64_t size) {
    if(!g_cscap.file || !address || !size || size>64*1024*1024)return;
    char suffix[64];snprintf(suffix,sizeof suffix,"b%u.cpu.bin",binding);cscap_write(suffix,(const void *)(uintptr_t)address,(size_t)size);
}
static void cscap_image(const dmsv_bind *b, vkimg_t *im, VkImageView view, VkSampler sampler, int storage) {
    if(!g_cscap.file)return;
    if(g_cscap.n==32 || b->count!=1 || !im || im->samples!=1 || im->layers!=1 || im->d!=1 || im->levels!=1 || im->aspect!=VK_IMAGE_ASPECT_COLOR_BIT)
        die("[RED] unsupported compute capture image shape");
    unsigned i=g_cscap.n++;typeof(g_cscap.item[0]) *x=&g_cscap.item[i];
    if(!vk_tex_view_description(im,view,&x->view) || x->view.viewType!=VK_IMAGE_VIEW_TYPE_2D || x->view.subresourceRange.baseMipLevel || x->view.subresourceRange.baseArrayLayer)
        die("[RED] unsupported compute capture view");
    const vkfmt_t *f=vk_fmt(im->nvn_format);
    if(!f || f->compressed || f->vk!=im->fmt || !f->bpb)die("[RED] unsupported compute capture texel encoding");
    x->binding=b->binding;x->image=1;x->im=im;x->bytes_per_pixel=f->bpb;x->size=(uint64_t)im->w*im->h*f->bpb;
    x->type=storage?VK_DESCRIPTOR_TYPE_STORAGE_IMAGE:VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER;
    if(x->size>64*1024*1024)die("[RED] compute capture image exceeds limit");
    VkComponentMapping s=x->view.components;
    fprintf(g_cscap.file,"image %u %u %u %u %u %u %u %u %u %u %u\n",b->binding,x->type,im->w,im->h,im->fmt,x->view.format,f->bpb,s.r,s.g,s.b,s.a);
    if(!storage){samp_par p;if(!vk_samp_parameters(sampler,&p))die("[RED] compute capture sampler unknown");
        char suffix[64];snprintf(suffix,sizeof suffix,"b%u.sampler.bin",b->binding);cscap_write(suffix,&p,sizeof p);}
}
static void cscap_add_pool(vkpool_t *pool){
    if(!pool)die("[RED] raw capture references an unregistered pool");
    for(unsigned i=0;i<g_cscap.npool;i++)if(g_cscap.pools[i].pool==pool)return;
    uint64_t bytes=pool->hi-pool->lo,total=bytes;
    for(unsigned i=0;i<g_cscap.npool;i++)total+=g_cscap.pools[i].pool->hi-g_cscap.pools[i].pool->lo;
    if(g_cscap.npool==16 || bytes>64*1024*1024 || total>256*1024*1024)die("[RED] raw capture exceeds bounded pool limits");
    vk_pool_buffer(pool);unsigned i=g_cscap.npool++;g_cscap.pools[i].pool=pool;
    fprintf(g_cscap.file,"pool %u %llu %llu\n",i,(unsigned long long)pool->lo,(unsigned long long)bytes);
}
static void cscap_prepare_pools(void){
    if(g_cscap.version!=2)return;
    // Include the bound output slots even if the translator emitted raw stores
    // instead of an explicit storage descriptor. Full pools preserve aliases.
    for(int i=0;i<16;i++)if(S.ssbo[5][i].addr)cscap_add_pool(vk_pool_of(S.ssbo[5][i].addr,1));
    for(unsigned i=0;i<g_cscap.n;i++)if(!g_cscap.item[i].image){
        vkpool_t *pool=vk_pool_of_buffer(g_cscap.item[i].buffer.buffer);if(pool)cscap_add_pool(pool);
    }
    const char *extra=getenv("DM_VK_CAPTURE_POOL_ADDRS");
    while(extra && *extra){char *end;uint64_t address=strtoull(extra,&end,16);if(end==extra)die("[RED] invalid extra raw capture pool address");cscap_add_pool(vk_pool_of(address,1));if(!*end)break;if(*end!=',')die("[RED] invalid extra raw capture pool separator");extra=end+1;}
    for(unsigned i=0;i<g_cscap.n;i++)if(!g_cscap.item[i].image){
        for(unsigned j=0;j<g_cscap.npool;j++)if(g_cscap.item[i].buffer.buffer==g_cscap.pools[j].pool->buf)
            fprintf(g_cscap.file,"alias %u %u %llu\n",g_cscap.item[i].binding,j,(unsigned long long)g_cscap.item[i].buffer.offset);
    }
}
static void cscap_copy(int after) {
    VkCommandBuffer cb=vk_cmd();vk_img_barrier_all(cb);
    for(unsigned i=0;i<g_cscap.npool;i++){
        typeof(g_cscap.pools[0]) *p=&g_cscap.pools[i];uint64_t bytes=p->pool->hi-p->pool->lo;
        p->data=vk_scratch(bytes,16,&p->staging,&p->offset);
        VkBufferCopy copy={0,p->offset,bytes};vkCmdCopyBuffer(cb,p->pool->buf,p->staging,1,&copy);
    }
    for(unsigned i=0;i<g_cscap.n;i++){
        typeof(g_cscap.item[0]) *x=&g_cscap.item[i];
        if(after && x->type!=VK_DESCRIPTOR_TYPE_STORAGE_IMAGE && x->type!=VK_DESCRIPTOR_TYPE_STORAGE_BUFFER)continue;
        x->data=vk_scratch(x->size,16,&x->staging,&x->offset);
        if(x->image){VkBufferImageCopy copy={.bufferOffset=x->offset,.imageSubresource={VK_IMAGE_ASPECT_COLOR_BIT,0,0,1},.imageExtent={x->im->w,x->im->h,1}};
            vkCmdCopyImageToBuffer(cb,x->im->img,VK_IMAGE_LAYOUT_GENERAL,x->staging,1,&copy);
        }else{VkBufferCopy copy={x->buffer.offset,x->offset,x->size};vkCmdCopyBuffer(cb,x->buffer.buffer,x->staging,1,&copy);}
    }
    vk_img_barrier_all(cb);vk_cmd_sync_host();
    for(unsigned i=0;i<g_cscap.npool;i++){
        char suffix[64];snprintf(suffix,sizeof suffix,"p%u.%s.bin",i,after?"after":"before");
        cscap_write(suffix,g_cscap.pools[i].data,(size_t)(g_cscap.pools[i].pool->hi-g_cscap.pools[i].pool->lo));
    }
    for(unsigned i=0;i<g_cscap.n;i++){
        typeof(g_cscap.item[0]) *x=&g_cscap.item[i];
        if(after && x->type!=VK_DESCRIPTOR_TYPE_STORAGE_IMAGE && x->type!=VK_DESCRIPTOR_TYPE_STORAGE_BUFFER)continue;
        char suffix[64];snprintf(suffix,sizeof suffix,"b%u.%s.bin",x->binding,after?"after":"before");cscap_write(suffix,x->data,(size_t)x->size);
    }
    if(after){if(fclose(g_cscap.file))die("[RED] compute capture manifest close failed");g_cscap.file=NULL;VKLOG("compute capture complete: %s",g_cscap.base);}
}
