// Descriptor CPU cost with a large mostly empty logical array. GPU reads also
// verify CPU-write/remap/hole versions retained within one unsubmitted batch.
static void atlas_checks_tests(void) {
    tex_t t={.magic=MAGIC('T','E','X',0),.serial=48001,.d={.width=8192,.height=8192,.depth=4,.levels=1,.samples=1,.target=NVN_TEXTURE_TARGET_2D_ARRAY,.format=NVN_FORMAT_RGBA8,.flags=NVN_TEXTURE_FLAGS_SPARSE}};
    nvn_tex_layout(&t.d,&t.L);nvn_gob_switch2=1;
    uint8_t *source=mmap(NULL,131072,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0),*job=mmap(NULL,65536,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0);
    if(source==MAP_FAILED || job==MAP_FAILED)abort();memset(source,255,65536);memset(source+65536,127,65536);
    NVNT_nvnMemoryPoolInitialize init=atlas_api("nvnMemoryPoolInitialize");NVNT_nvnMemoryPoolFinalize fini=atlas_api("nvnMemoryPoolFinalize");NVNT_nvnMemoryPoolMapVirtual map=atlas_api("nvnMemoryPoolMapVirtual");
    pool_t physical,virtual;pool_builder_t pb={.mem=source,.size=131072,.flags=0x24};if(!init((NVNmemoryPool*)&physical,(NVNmemoryPoolBuilder*)&pb))abort();
    t.off=65536;pb=(pool_builder_t){.size=t.off+t.L.size+65536,.flags=0x200};if(!init((NVNmemoryPool*)&virtual,(NVNmemoryPoolBuilder*)&pb))abort();t.pool=&virtual;t.mem=virtual.mem+t.off;
    AtlasMapping mapping={(NVNmemoryPool*)&physical,0,t.off,65536,0,0};if(!map((NVNmemoryPool*)&virtual,1,(NVNmappingRequest*)&mapping))abort();mtl_pool_add(job,65536);
    samp_par sampler={.minf=0,.magf=0,.aniso=1,.lod_max=1000};mtl_reg_samp(1,&sampler);VkSampler handle=vk_samp_by_id(1);
    VkDescriptorImageInfo image={0};VkDescriptorBufferInfo meta={0};mtl_sub_begin();
    atlas_check(vk_atlas_descriptor(&t,NULL,handle,&image,&meta,0),"large uncompressed array descriptor accepted");
    VkImageView original=image.imageView;VkBuffer original_buffer=meta.buffer;VkDeviceSize original_offset=meta.offset;int stable=1;
    // A global dirty version changes without changing this texture. Negative
    // checks must be remembered instead of rescanning on all later draws.
    dm_guest_write_prepare(job+32768,4096);memset(job+32768,1,4096);
    uint64_t begin=measure_ns(CLOCK_THREAD_CPUTIME_ID);
    for(unsigned i=0;i<1000;i++)stable&=vk_atlas_descriptor(&t,NULL,handle,&image,&meta,0) && image.imageView==original && meta.buffer==original_buffer && meta.offset==original_offset;
    uint64_t elapsed=measure_ns(CLOCK_THREAD_CPUTIME_ID)-begin;
    atlas_check(stable,"1000 unchanged descriptors retain identical bindings");
    printf("atlas descriptor checks: logical_bytes=%llu calls=1000 thread_cpu_ns=%llu cache=%s\n",(unsigned long long)t.L.size,(unsigned long long)elapsed,getenv("DM_VK_ATLAS_CHECK_CACHE")?getenv("DM_VK_ATLAS_CHECK_CACHE"):"default");
    AtlasQuery *q=(AtlasQuery*)(job+16384);q[0]=(AtlasQuery){.x=0,.y=0};atlas_record(job,&t,NULL,0,q,1);
    dm_guest_write_prepare(source,65536);memset(source,0,65536);atlas_record(job,&t,NULL,1,q,1);
    mapping.source=65536;if(!map((NVNmemoryPool*)&virtual,1,(NVNmappingRequest*)&mapping))abort();atlas_record(job,&t,NULL,2,q,1);
    mapping.physical=NULL;if(!map((NVNmemoryPool*)&virtual,1,(NVNmappingRequest*)&mapping))abort();atlas_record(job,&t,NULL,3,q,1);
    if(!mtl_wait(mtl_sub_commit(),10000000000ull))abort();
    float expected[]={1,0,127.f/255,0};
    for(unsigned phase=0;phase<4;phase++){float *actual=(float*)(job+4096+phase*512);int ok=1;for(unsigned c=0;c<4;c++)ok&=fabsf(actual[c]-expected[phase])<.0001f;atlas_check(ok,"GPU sees each CPU-write/remap/hole version before one fence");}
    mapping.physical=(NVNmemoryPool*)&physical;if(!map((NVNmemoryPool*)&virtual,1,(NVNmappingRequest*)&mapping))abort();
    mtl_sub_begin();atlas_check(vk_atlas_descriptor(&t,NULL,handle,&image,&meta,0),"physical storage readable before retirement");if(!mtl_wait(mtl_sub_commit(),10000000000ull))abort();
    fini((NVNmemoryPool*)&physical);mtl_sub_begin();atlas_check(!vk_atlas_descriptor(&t,NULL,handle,&image,&meta,0),"physical retirement invalidates readability at next submission");if(!mtl_wait(mtl_sub_commit(),10000000000ull))abort();
    // An unreadable page after many wholly absent leaves must still be seen,
    // including an unaligned query that ends partway into the last page.
    mapping=(AtlasMapping){NULL,0,t.off,65536,0,0};if(!map((NVNmemoryPool*)&virtual,1,(NVNmappingRequest*)&mapping))abort();
    uint8_t *blocked=mmap(NULL,65536,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0);if(blocked==MAP_FAILED)abort();pool_t unreadable;
    pb=(pool_builder_t){.mem=blocked,.size=65536,.flags=NVN_MEMORY_POOL_FLAGS_CPU_NO_ACCESS|NVN_MEMORY_POOL_FLAGS_GPU_CACHED};if(!init((NVNmemoryPool*)&unreadable,(NVNmemoryPoolBuilder*)&pb))abort();
    mapping=(AtlasMapping){(NVNmemoryPool*)&unreadable,0,t.off+(int64_t)t.L.size-65536,4096,0,0};if(!map((NVNmemoryPool*)&virtual,1,(NVNmappingRequest*)&mapping))abort();
    extern int nvn_sparse_cpu_readable(const void *,uint64_t,uint64_t);
    uint64_t address=(uint64_t)(uintptr_t)t.mem;
    atlas_check(nvn_sparse_cpu_readable(t.pool,address+17,t.L.size-65536-17),"absent leaves and unmapped pages remain readable holes");
    atlas_check(!nvn_sparse_cpu_readable(t.pool,address+17,t.L.size-65536+19-17),"leaf skipping still finds an unreadable far page");
    fini((NVNmemoryPool*)&virtual);fini((NVNmemoryPool*)&unreadable);mtl_pool_del(job);munmap(blocked,65536);munmap(source,131072);munmap(job,65536);
}

static void ownership_checks_tests(void) {
    enum{N=1024};size_t bytes=(size_t)N*65536;uint8_t *source=mmap(NULL,bytes,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0);if(source==MAP_FAILED)abort();
    NVNT_nvnMemoryPoolInitialize init=atlas_api("nvnMemoryPoolInitialize");NVNT_nvnMemoryPoolFinalize fini=atlas_api("nvnMemoryPoolFinalize");NVNT_nvnMemoryPoolMapVirtual map=atlas_api("nvnMemoryPoolMapVirtual");
    pool_t physical,virtual;pool_builder_t pb={.mem=source,.size=bytes,.flags=0x18c};if(!init((NVNmemoryPool*)&physical,(NVNmemoryPoolBuilder*)&pb))abort();tex_t *t=calloc(N,sizeof*t);if(!t)abort();
    for(unsigned i=0;i<N;i++){t[i]=(tex_t){.magic=MAGIC('T','E','X',0),.serial=49000+i,.pool=&physical,.off=(int64_t)i*65536,.mem=source+(size_t)i*65536,.d={.width=8,.height=8,.depth=1,.levels=1,.samples=1,.target=NVN_TEXTURE_TARGET_2D,.format=NVN_FORMAT_RGBA8,.flags=NVN_TEXTURE_FLAGS_MINIMAL_LAYOUT}};nvn_tex_layout(&t[i].d,&t[i].L);vk_tex(&t[i]);}
    atlas_check(!vk_tex_gpu_content(t),"new CPU-backed images have no GPU owner");uint64_t begin=measure_ns(CLOCK_THREAD_CPUTIME_ID);int clean=1;
    for(unsigned i=0;i<100000;i++)clean&=!vk_tex_gpu_content(t);
    uint64_t elapsed=measure_ns(CLOCK_THREAD_CPUTIME_ID)-begin;atlas_check(clean,"100000 repeated negative ownership queries agree");printf("ownership checks: images=%u calls=100000 thread_cpu_ns=%llu cache=%s\n",N,(unsigned long long)elapsed,getenv("DM_VK_OWNERSHIP_CACHE")?getenv("DM_VK_OWNERSHIP_CACHE"):"default");
    begin=measure_ns(CLOCK_THREAD_CPUTIME_ID);clean=1;for(unsigned i=0;i<100000;i++)clean&=!vk_tex_gpu_content(t+(i&15)*64);elapsed=measure_ns(CLOCK_THREAD_CPUTIME_ID)-begin;atlas_check(clean,"alternating sixteen aligned image spans keep correct ownership");printf("ownership alternating checks: calls=100000 thread_cpu_ns=%llu\n",(unsigned long long)elapsed);
    tex_t overlap=t[0];overlap.off+=(int64_t)t[0].L.size/2;overlap.mem+=t[0].L.size/2;atlas_check(!vk_tex_gpu_content(&overlap),"overlapping alias begins without GPU content");
    mtl_sub_begin();p_clear_tex clear={.tex=t,.r={0,0,0,8,8,1},.mask=15,.c.f={.25f,.5f,1,1}};size_t length=(8+sizeof clear+7)&~7ull;uint8_t command[sizeof clear+32]={0};op_hdr h={OP_CLEAR_TEX,(uint32_t)length};memcpy(command,&h,8);memcpy(command+8,&clear,sizeof clear);h=(op_hdr){OP_END,8};memcpy(command+length,&h,8);mtl_exec(command);
    atlas_check(vk_tex_gpu_content(t),"a clear invalidates negative ownership before the fence");atlas_check(vk_tex_gpu_content(&overlap),"an overlapping alias sees the new GPU owner");atlas_check(!vk_tex_gpu_content(t+1),"adjacent nonoverlapping storage stays CPU-owned");
    tex_t storage=t[1];storage.d.flags|=NVN_TEXTURE_FLAGS_IMAGE;vk_tex(&storage);atlas_check(vk_tex_gpu_content(t+1),"creating shader-writable storage invalidates an older negative query");
    // As in the game's virtual texture arrays, high addresses are resolved by
    // the NVN page table rather than Linux's unsupported private VM aliasing.
    int64_t virtual_offset=0x800000000ll;pb=(pool_builder_t){.size=(uint64_t)virtual_offset+3*65536,.flags=0x200};if(!init((NVNmemoryPool*)&virtual,(NVNmemoryPoolBuilder*)&pb))abort();AtlasMapping mapping={(NVNmemoryPool*)&physical,0,virtual_offset,65536,0,0};if(!map((NVNmemoryPool*)&virtual,1,(NVNmappingRequest*)&mapping))abort();tex_t sparse=t[0];sparse.pool=&virtual;sparse.off=virtual_offset;sparse.mem=virtual.mem+sparse.off;sparse.d.flags|=NVN_TEXTURE_FLAGS_SPARSE;nvn_tex_layout(&sparse.d,&sparse.L);
    atlas_check(vk_tex_gpu_content(&sparse),"sparse physical alias resolves GPU ownership");mapping.source=2*65536;if(!map((NVNmemoryPool*)&virtual,1,(NVNmappingRequest*)&mapping))abort();atlas_check(!vk_tex_gpu_content(&sparse),"remapping to CPU storage invalidates cached GPU ownership");mapping.source=0;if(!map((NVNmemoryPool*)&virtual,1,(NVNmappingRequest*)&mapping))abort();atlas_check(vk_tex_gpu_content(&sparse),"remapping back restores GPU ownership before the same fence");
    if(!mtl_wait(mtl_sub_commit(),10000000000ull))abort();uint8_t pixels[256];NVNcopyRegion region={0,0,0,8,8,1};mtl_read_texels(t,0,0,&region,pixels,32,sizeof pixels);int ok=1;for(unsigned i=0;i<sizeof pixels;i+=4)ok&=pixels[i]==64 && pixels[i+1]==128 && pixels[i+2]==255 && pixels[i+3]==255;atlas_check(ok,"actual cleared GPU pixels survive ownership queries and remaps");
    fini((NVNmemoryPool*)&virtual);fini((NVNmemoryPool*)&physical);atlas_check(!vk_tex_gpu_content(t),"pool retirement invalidates cached ownership");free(t);munmap(source,bytes);
}
