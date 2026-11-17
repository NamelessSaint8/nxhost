// Real descriptor and pool lifecycle proof; destination is never bound directly.
#define GMEM_EMIT(OP,X) driver_emit(OP,&(X),sizeof(X))
static void gmem_tests(int cooperative) {
    enum { PAGES=2048, BYTES=PAGES*4096 };
    uint8_t *mem=mmap(NULL,1048576,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0);
    uint8_t *target=mmap(NULL,BYTES,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0);
    if(mem==MAP_FAILED || target==MAP_FAILED)abort();
    vk_pool_add_flags(mem,1048576,NVN_MEMORY_POOL_FLAGS_CPU_CACHED|NVN_MEMORY_POOL_FLAGS_GPU_CACHED);
    // CPU_UNCACHED forces the copied-pool path to rely on logged ranges rather
    // than the completion thread's default whole cached-pool copy-back.
    vk_pool_add_flags(target,BYTES,NVN_MEMORY_POOL_FLAGS_CPU_UNCACHED|NVN_MEMORY_POOL_FLAGS_GPU_CACHED);
    memset(target,0x3c,BYTES);
    uint64_t *pointers=(uint64_t *)(mem+65536);pointers[0]=(uint64_t)target;
    uint32_t *result=(uint32_t *)(mem+131072);
    for(unsigned phase=0;phase<4;phase++){
        unsigned groups=phase==2?64:1, count=groups*32;
        pointers[0]=phase==3?0:(uint64_t)target;
        memset(result,0,16384);
        mtl_sub_begin();driver_begin(mem);driver_bind(cooperative?35:34);
        p_bind_buf input={.stage=5,.index=0,.addr=(uint64_t)pointers,.size=8};GMEM_EMIT(OP_BIND_SSBO,input);
        p_bind_buf output={.stage=5,.index=1,.addr=(uint64_t)result,.size=(2048+count)*4};GMEM_EMIT(OP_BIND_SSBO,output);
        p_dispatch dispatch={.x=(int)groups,.y=1,.z=1};GMEM_EMIT(OP_DISPATCH,dispatch);driver_end();
        int ok=1,canary=1;
        for(unsigned i=0;i<count;i++){
            uint32_t initial=0x3c3c3c3c,delta=17+i,previous=initial;
            if(phase>=1 && i<32)previous+=delta;
            if(phase>=2 && i<32)previous+=delta;
            if(phase==3)ok&=result[i]==0xfeedbad0;
            else {uint32_t actual;memcpy(&actual,target+i*4096,4);ok&=result[i]==previous && actual==previous+delta;}
            for(unsigned j=4;j<4096;j++)canary&=target[i*4096+j]==0x3c;
        }
        driver_check(ok,"indirect atomic results and unbound destinations visible before NVN completion",phase);
        driver_check(canary,"raw writes preserve every byte outside their four-byte destinations",phase);
        if(phase!=3){vkpool_t *pool=vk_pool_of((uint64_t)target,1);int flags_ok=pool!=NULL;
            uint32_t expected=pool&&pool->zero_copy?DMSH_GMEM_MAP_NO_WRITE_LOG:0;
            for(unsigned i=0;i<count;i++)flags_ok&=result[2048+i]==expected;
            driver_check(flags_ok,"write-log suppression is advertised only for actual zero-copy destinations",phase);}
        vkpool_t *mp=vk_pool_of((uint64_t)mem,1),*tp=vk_pool_of((uint64_t)target,1);
        driver_check(vk_gmem_coherent()==(mp->zero_copy && tp->zero_copy),"coherent module selection covers every advertised pool",phase);
        if(!mtl_wait(mtl_sub_commit(),10000000000ull))abort();
    }
    mtl_pool_del(target);munmap(target,BYTES);
    // Removing a pool and reusing its address must not leave an old device delta.
    target=mmap(target,BYTES,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS|MAP_FIXED,-1,0);
    if(target==MAP_FAILED)abort();memset(target,0x3c,BYTES);
    vk_pool_add_flags(target,BYTES,NVN_MEMORY_POOL_FLAGS_CPU_UNCACHED|NVN_MEMORY_POOL_FLAGS_GPU_CACHED);
    pointers[0]=(uint64_t)target;
    mtl_sub_begin();driver_begin(mem);driver_bind(cooperative?35:34);
    p_bind_buf input={.stage=5,.index=0,.addr=(uint64_t)pointers,.size=8};GMEM_EMIT(OP_BIND_SSBO,input);
    p_bind_buf output={.stage=5,.index=1,.addr=(uint64_t)result,.size=(2048+32)*4};GMEM_EMIT(OP_BIND_SSBO,output);
    p_dispatch dispatch={.x=1,.y=1,.z=1};GMEM_EMIT(OP_DISPATCH,dispatch);driver_end();
    int ok=1;for(unsigned i=0;i<32;i++){uint32_t word;memcpy(&word,target+i*4096,4);ok&=word==0x3c3c3c3c+17+i;}
    driver_check(ok,"re-registered guest range receives the new Vulkan device address",4);
    if(!mtl_wait(mtl_sub_commit(),10000000000ull))abort();
    // Reuse the shader and guest address while toggling the destination's
    // backing. A cached coherent pipeline must never suppress copied writes.
    const char *old=getenv("DM_VK_NO_ZEROCOPY");char *saved=old?strdup(old):NULL;
    for(unsigned mode=0;mode<2;mode++){
        mtl_pool_del(target);munmap(target,BYTES);
        target=mmap(target,BYTES,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS|MAP_FIXED,-1,0);
        if(target==MAP_FAILED)abort();memset(target,0x3c,BYTES);
        if(!mode)setenv("DM_VK_NO_ZEROCOPY","1",1);
        else if(saved)setenv("DM_VK_NO_ZEROCOPY",saved,1);else unsetenv("DM_VK_NO_ZEROCOPY");
        vk_pool_add_flags(target,BYTES,NVN_MEMORY_POOL_FLAGS_CPU_UNCACHED|NVN_MEMORY_POOL_FLAGS_GPU_CACHED);
        pointers[0]=(uint64_t)target;memset(result,0,16384);
        mtl_sub_begin();driver_begin(mem);driver_bind(cooperative?35:34);
        GMEM_EMIT(OP_BIND_SSBO,input);GMEM_EMIT(OP_BIND_SSBO,output);GMEM_EMIT(OP_DISPATCH,dispatch);driver_end();
        ok=1;for(unsigned i=0;i<32;i++){uint32_t word;memcpy(&word,target+i*4096,4);ok&=word==0x3c3c3c3c+17+i && result[i]==0x3c3c3c3c;}
        driver_check(ok,"copied/coherent transition publishes indirect writes before completion",5+mode);
        vkpool_t *mp=vk_pool_of((uint64_t)mem,1),*tp=vk_pool_of((uint64_t)target,1);
        driver_check(vk_gmem_coherent()==(mp->zero_copy && tp->zero_copy),"pool replacement changes coherent pipeline selection",5+mode);
        if(!mtl_wait(mtl_sub_commit(),10000000000ull))abort();
    }
    if(saved){setenv("DM_VK_NO_ZEROCOPY",saved,1);free(saved);}else unsetenv("DM_VK_NO_ZEROCOPY");
    mtl_pool_del(target);mtl_pool_del(mem);munmap(target,BYTES);munmap(mem,1048576);
}
#undef GMEM_EMIT
