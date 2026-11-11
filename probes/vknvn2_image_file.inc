// GPU contents deliberately differ from canonical guest memory. Independent
// whole-mip transfers verify the file cache's per-layer/slice/row serialization.
extern void vk_tex_sweep(void);
extern void vk_image_file_stats(uint64_t *,uint64_t *,uint64_t *);
static unsigned file_proof_bpp(const tex_t *t,VkImageAspectFlags aspect){return aspect==VK_IMAGE_ASPECT_STENCIL_BIT?1:aspect==VK_IMAGE_ASPECT_DEPTH_BIT?(t->d.format==NVN_FORMAT_DEPTH16?2:4):vk_fmt(t->d.format)->bpb;}
static void file_proof_pixels(tex_t *t,unsigned seed,uint8_t digest[32],int upload){
    CC_SHA256_CTX hash;CC_SHA256_Init(&hash);
    for(unsigned mip=0;mip<t->d.levels;mip++){
        mtl_sub_begin();vkimg_t *im=vk_tex(t);if(!im)abort();uint32_t w=im->w>>mip,h=im->h>>mip,d=im->d>>mip;if(!w)w=1;if(!h)h=1;if(!d)d=1;
        for(unsigned aspect=1;aspect<=VK_IMAGE_ASPECT_STENCIL_BIT;aspect<<=1)if(im->aspect&aspect){
            unsigned bpp=file_proof_bpp(t,aspect);size_t bytes=(size_t)w*h*d*im->layers*bpp;VkBuffer buffer;VkDeviceSize offset;uint8_t *pixels=vk_scratch(bytes,16,&buffer,&offset);
            if(upload)for(size_t i=0;i<bytes/bpp;i++){
                uint32_t value=(uint32_t)(i*719+seed*997+mip*31);
                if(aspect==VK_IMAGE_ASPECT_DEPTH_BIT && t->d.format==NVN_FORMAT_DEPTH32F){float depth=(value%4096)/4096.f;memcpy(pixels+i*bpp,&depth,4);}
                else if(aspect==VK_IMAGE_ASPECT_DEPTH_BIT && t->d.format==NVN_FORMAT_DEPTH24_STENCIL8){value&=0xffffff;memcpy(pixels+i*bpp,&value,4);}
                else if(t->d.format==NVN_FORMAT_RGBA16F){for(unsigned c=0;c<4;c++){uint16_t half=(uint16_t)(0x3000+((value+c*137)&2047));memcpy(pixels+i*bpp+c*2,&half,2);}}
                else for(unsigned c=0;c<bpp;c++)pixels[i*bpp+c]=(uint8_t)(value+c*41);
            }
            VkBufferImageCopy region={.bufferOffset=offset,.imageSubresource={aspect,mip,0,im->layers},.imageExtent={w,h,d}};vk_tex_prepare(vk_cmd(),im);vk_img_barrier_all(vk_cmd());
            if(upload){vkCmdCopyBufferToImage(vk_cmd(),buffer,im->img,VK_IMAGE_LAYOUT_GENERAL,1,&region);vk_tex_mark_gpu_write(im);}
            else{vkCmdCopyImageToBuffer(vk_cmd(),im->img,VK_IMAGE_LAYOUT_GENERAL,buffer,1,&region);memory_host_read_barrier();}
            if(!mtl_wait(mtl_sub_commit(),10000000000ull))abort();
            if(!upload){if(aspect==VK_IMAGE_ASPECT_DEPTH_BIT && t->d.format==NVN_FORMAT_DEPTH24_STENCIL8)for(size_t i=0;i<bytes;i+=4)pixels[i+3]=0;CC_SHA256_Update(&hash,pixels,(CC_LONG)bytes);}
            // Each aspect gets independent whole-mip staging, unlike the pager.
            if(im->aspect&~((aspect<<1)-1u))mtl_sub_begin();
        }
    }
    CC_SHA256_Final(digest,&hash);
}
static void file_proof_pending_read(tex_t *t){
    PFN_vkCreateSemaphore create=(PFN_vkCreateSemaphore)vkGetDeviceProcAddr(V.dev,"vkCreateSemaphore");PFN_vkDestroySemaphore destroy=(PFN_vkDestroySemaphore)vkGetDeviceProcAddr(V.dev,"vkDestroySemaphore");
    copied_gate gate={.signal=(PFN_vkSignalSemaphore)vkGetDeviceProcAddr(V.dev,"vkSignalSemaphore")};VkSemaphoreTypeCreateInfo type={.sType=VK_STRUCTURE_TYPE_SEMAPHORE_TYPE_CREATE_INFO,.semaphoreType=VK_SEMAPHORE_TYPE_TIMELINE};VkSemaphoreCreateInfo info={.sType=VK_STRUCTURE_TYPE_SEMAPHORE_CREATE_INFO,.pNext=&type};VKCHK(create(V.dev,&info,NULL,&gate.semaphore));
    uint64_t value=1;VkTimelineSemaphoreSubmitInfo timeline={.sType=VK_STRUCTURE_TYPE_TIMELINE_SEMAPHORE_SUBMIT_INFO,.waitSemaphoreValueCount=1,.pWaitSemaphoreValues=&value};VkPipelineStageFlags stage=VK_PIPELINE_STAGE_ALL_COMMANDS_BIT;VkSubmitInfo queued={.sType=VK_STRUCTURE_TYPE_SUBMIT_INFO,.pNext=&timeline,.waitSemaphoreCount=1,.pWaitSemaphores=&gate.semaphore,.pWaitDstStageMask=&stage};extern pthread_mutex_t g_vk_queue_mu;pthread_mutex_lock(&g_vk_queue_mu);VKCHK(vkQueueSubmit(V.q,1,&queued,VK_NULL_HANDLE));pthread_mutex_unlock(&g_vk_queue_mu);
    mtl_sub_begin();vkimg_t *im=vk_tex(t);VkBuffer buffer;VkDeviceSize offset;size_t bytes=(size_t)im->w*im->h*4;uint8_t *pixels=vk_scratch(bytes,16,&buffer,&offset);VkBufferImageCopy region={.bufferOffset=offset,.imageSubresource={VK_IMAGE_ASPECT_COLOR_BIT,0,0,1},.imageExtent={im->w,im->h,1}};vkCmdCopyImageToBuffer(vk_cmd(),im->img,VK_IMAGE_LAYOUT_GENERAL,buffer,1,&region);memory_host_read_barrier();uint64_t pending=mtl_sub_commit();pthread_t thread;if(pthread_create(&thread,NULL,copied_gate_release,&gate))abort();
    uint64_t before,after,peak,count;vk_memory_stats(&before,&peak,&count);for(unsigned i=0;i<65;i++)vk_tex_sweep();vk_memory_stats(&after,&peak,&count);
    memory_check(vk_fence_done()<pending && before==after,"idle cleanup retains images referenced by actual pending GPU reads without draining them");
    pthread_join(thread,NULL);if(!mtl_wait(pending,10000000000ull))abort();destroy(V.dev,gate.semaphore,NULL);int ok=1;for(size_t i=0;i<bytes;i++)ok&=pixels[i]==0x61;memory_check(ok,"pending GPU reads keep every pixel while image cleanup is attempted");
    // New work references no image. A completed image must retire without
    // waiting for this unrelated queue gate or destroying a pending resource.
    VKCHK(create(V.dev,&info,NULL,&gate.semaphore));pthread_mutex_lock(&g_vk_queue_mu);VKCHK(vkQueueSubmit(V.q,1,&queued,VK_NULL_HANDLE));pthread_mutex_unlock(&g_vk_queue_mu);mtl_sub_begin();pending=mtl_sub_commit();if(pthread_create(&thread,NULL,copied_gate_release,&gate))abort();
    vk_memory_stats(&before,&peak,&count);for(unsigned i=0;i<65;i++)vk_tex_sweep();vk_memory_stats(&after,&peak,&count);memory_check(vk_fence_done()<pending && after<before,"completed inactive images release storage without draining unrelated GPU work");
    pthread_join(thread,NULL);if(!mtl_wait(pending,10000000000ull))abort();destroy(V.dev,gate.semaphore,NULL);
}
static void image_file_tests(void){
    setenv("DM_VK_IMAGE_BUDGET_MB","1",1);if(!getenv("DM_TEMP"))setenv("DM_TEMP",".",1);
    enum{N=5};tex_t t[N];uint8_t expected[N][32],actual[32],unused[32];size_t stride=64u<<20,size=N*stride;uint8_t *source=mmap(NULL,size,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0);if(source==MAP_FAILED)abort();memset(source,0xcc,size);
    NVNT_nvnMemoryPoolInitialize init=atlas_api("nvnMemoryPoolInitialize");NVNT_nvnMemoryPoolFinalize fini=atlas_api("nvnMemoryPoolFinalize");pool_t pool;pool_builder_t builder={.mem=source,.size=size,.flags=0x18c};if(!init((NVNmemoryPool*)&pool,(NVNmemoryPoolBuilder*)&builder))abort();
    unsigned formats[]={NVN_FORMAT_RGBA8,NVN_FORMAT_DEPTH32F,NVN_FORMAT_DEPTH24_STENCIL8,NVN_FORMAT_RGBA16F,NVN_FORMAT_R8};
    for(unsigned i=0;i<N;i++){t[i]=(tex_t){.magic=MAGIC('T','E','X',0),.serial=56000+i,.pool=&pool,.off=(int64_t)(i*stride),.mem=source+i*stride,.d={.width=512,.height=512,.depth=3,.levels=3,.samples=1,.target=NVN_TEXTURE_TARGET_2D_ARRAY,.format=formats[i],.flags=NVN_TEXTURE_FLAGS_MINIMAL_LAYOUT}};
        if(i==3){t[i].d.target=NVN_TEXTURE_TARGET_3D;t[i].d.width=1024;t[i].d.height=2048;t[i].d.depth=2;}
        if(i==4){t[i].d.target=NVN_TEXTURE_TARGET_1D_ARRAY;t[i].d.width=2048;t[i].d.height=512;t[i].d.depth=1;t[i].d.levels=2;}
        nvn_tex_layout(&t[i].d,&t[i].L);if(t[i].L.size>stride)abort();file_proof_pixels(t+i,i+1,unused,1);file_proof_pixels(t+i,0,expected[i],0);
    }
    uint64_t before,after,peak,count,paged,saved,loaded;vk_memory_stats(&before,&peak,&count);
    for(unsigned i=0;i<60;i++)vk_tex_sweep();vk_image_file_stats(&paged,&saved,&loaded);
    memory_check(paged>0 && paged<(50u<<20),"retention spreads a large transition over multiple presents");
    for(unsigned i=0;i<N;i++)vk_tex_sweep();vk_image_file_stats(&paged,&saved,&loaded);vk_memory_stats(&after,&peak,&count);
    memory_check(paged>(50u<<20),"all test images including the large 3D texture reach file-backed storage");
    memory_check(paged>0 && saved>=paged && loaded==0,"inactive GPU images retain actual pixels in private file storage");memory_check(after<before,"file retention releases real Vulkan allocations despite bounded transfer staging");
    for(unsigned i=0;i<N;i++){file_proof_pixels(t+i,0,actual,0);memory_check(!memcmp(actual,expected[i],32),"every GPU byte survives file retention and restoration across subresources");}
    vk_image_file_stats(&paged,&saved,&loaded);memory_check(!paged && loaded>0,"all evicted images restore before their next GPU lookup");
    file_proof_pixels(t,91,unused,1);file_proof_pixels(t,0,expected[0],0);uint64_t prior=saved;
    for(unsigned i=0;i<60+N;i++)vk_tex_sweep();vk_image_file_stats(&paged,&saved,&loaded);memory_check(paged>0 && saved>prior,"restored images may be evicted again after newer GPU writes");
    for(unsigned i=0;i<N;i++){file_proof_pixels(t+i,0,actual,0);memory_check(!memcmp(actual,expected[i],32),"second restoration keeps changed and unchanged GPU pixels");}
    int canonical=1;for(size_t i=0;i<size;i++)canonical&=source[i]==0xcc;memory_check(canonical,"GPU file retention does not replace canonical guest bytes with a pixel dump");
    usleep(5100000);vk_tex_sweep();vk_image_file_stats(&paged,&saved,&loaded);memory_check(paged>0,"wall-time idle images can retire during cold loading without sixty presents");
    for(unsigned i=0;i<60+N;i++)vk_tex_sweep();vk_image_file_stats(&paged,&saved,&loaded);memory_check(paged>0,"pool retirement begins with inactive GPU pixels still file-backed");
    fini((NVNmemoryPool*)&pool);vk_image_file_stats(&paged,&saved,&loaded);memory_check(!paged,"pool retirement releases every retained file image");
    for(unsigned mode=0;mode<2;mode++){
    dm_guest_write_prepare(source,stride);memset(source,0x61,stride);builder.size=stride;if(!init((NVNmemoryPool*)&pool,(NVNmemoryPoolBuilder*)&builder))abort();
    tex_t cpu={.magic=MAGIC('T','E','X',0),.serial=57000,.pool=&pool,.mem=source,.has_layout=1,.d={.width=1024,.height=1024,.depth=1,.levels=1,.samples=1,.target=NVN_TEXTURE_TARGET_2D,.format=NVN_FORMAT_RGBA8,.flags=NVN_TEXTURE_FLAGS_MINIMAL_LAYOUT}};if(mode){cpu.d.width=cpu.d.height=2048;cpu.d.format=NVN_FORMAT_DEPTH16;}nvn_tex_layout(&cpu.d,&cpu.L);
    file_proof_pixels(&cpu,0,expected[0],0);if(!mode){file_proof_pending_read(&cpu);file_proof_pixels(&cpu,0,actual,0);memory_check(!memcmp(actual,expected[0],32),"recreation after nonblocking retirement preserves completed image pixels");}vk_memory_stats(&before,&peak,&count);uint64_t file_saved=saved;
    for(unsigned i=0;i<60+N;i++)vk_tex_sweep();vk_memory_stats(&after,&peak,&count);vk_image_file_stats(&paged,&saved,&loaded);
    memory_check(after<before && saved==file_saved,"inactive CPU image copies release storage without saving redundant pixels");
    file_proof_pixels(&cpu,0,actual,0);memory_check(!memcmp(actual,expected[0],32),"CPU image recreation preserves every original pixel from canonical storage");
    for(unsigned i=0;i<60+N;i++)vk_tex_sweep();dm_guest_write_prepare(source,cpu.L.size);memset(source,0x73,cpu.L.size);CC_SHA256(source,cpu.d.width*cpu.d.height*(mode?2u:4u),expected[0]);file_proof_pixels(&cpu,0,actual,0);
    memory_check(!memcmp(actual,expected[0],32),"CPU image recreation observes every later canonical source byte");
    fini((NVNmemoryPool*)&pool);}
    munmap(source,size);
}
