// Real shared Vulkan allocation: two buffer aliases count once. GPU fill is
// visible through the mapped allocation; destroying either alias adds no bytes.
#include "nvn_dirty.h"
static void memory_check(int ok, const char *name) {
    checks++; failed += !ok; printf("memory accounting %s %s\n", name, ok ? "PASS" : "FAIL");
}
static void memory_host_read_barrier(void){VkMemoryBarrier barrier={.sType=VK_STRUCTURE_TYPE_MEMORY_BARRIER,.srcAccessMask=VK_ACCESS_TRANSFER_WRITE_BIT,.dstAccessMask=VK_ACCESS_HOST_READ_BIT};vkCmdPipelineBarrier(vk_cmd(),VK_PIPELINE_STAGE_TRANSFER_BIT,VK_PIPELINE_STAGE_HOST_BIT,0,1,&barrier,0,NULL,0,NULL);}
static void memory_tests(void) {
    mtl_sub_begin();
    VkBufferCreateInfo info = {.sType=VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO,.size=8192,.usage=VK_BUFFER_USAGE_TRANSFER_DST_BIT,.sharingMode=VK_SHARING_MODE_EXCLUSIVE};
    VkBuffer buffers[2];
    for (unsigned i=0;i<2;i++) VKCHK(vkCreateBuffer(V.dev,&info,NULL,&buffers[i]));
    VkMemoryRequirements req; vkGetBufferMemoryRequirements(V.dev,buffers[0],&req);
    uint64_t before, peak, count, live, now_count; vk_memory_stats(&before,&peak,&count);
    VkMemoryAllocateInfo alloc = {.sType=VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO,.allocationSize=req.size,.memoryTypeIndex=vk_mem_type(req.memoryTypeBits,VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT|VK_MEMORY_PROPERTY_HOST_COHERENT_BIT,0)};
    VkDeviceMemory memory; VKCHK(vk_memory_allocate(V.dev,&alloc,NULL,&memory));
    vk_memory_stats(&live,&peak,&now_count);
    memory_check(live==before+req.size && now_count==count+1,"allocation bytes and count");
    memory_check(peak>=live,"peak includes new allocation");
    for (unsigned i=0;i<2;i++) VKCHK(vkBindBufferMemory(V.dev,buffers[i],memory,0));
    vk_memory_stats(&live,&peak,&now_count);
    memory_check(live==before+req.size && now_count==count+1,"two aliases count once");
    vkCmdFillBuffer(vk_cmd(),buffers[0],0,8192,0x5a6b7c8d);
    uint64_t fence=mtl_sub_commit(); if(!mtl_wait(fence,10000000000ull))abort();
    uint32_t *mapped; VKCHK(vkMapMemory(V.dev,memory,0,req.size,0,(void **)&mapped));
    int ok=1;for(unsigned i=0;i<8192/4;i++)ok&=mapped[i]==0x5a6b7c8d;
    memory_check(ok,"GPU writes survive shared storage"); vkUnmapMemory(V.dev,memory);
    for(unsigned i=0;i<2;i++)vkDestroyBuffer(V.dev,buffers[i],NULL);
    vk_memory_stats(&live,&peak,&now_count);memory_check(live==before+req.size,"resource aliases do not free memory");
    vk_memory_free(V.dev,memory,NULL);vk_memory_stats(&live,&peak,&now_count);
    memory_check(live==before && now_count==count,"free restores allocation baseline");
    vk_memory_free(V.dev,VK_NULL_HANDLE,NULL);uint64_t after;vk_memory_stats(&after,&peak,&now_count);
    memory_check(after==live && now_count==count,"null free leaves counters unchanged");
}
static unsigned memory_map_count(void) {
    FILE *file=fopen("/proc/self/maps","r");if(!file)abort();unsigned count=0;char line[2048];while(fgets(line,sizeof line,file))count++;fclose(file);return count;
}
static void fragmentation_tests(void) {
    void crash_install(void);crash_install();
    size_t page=(size_t)getpagesize(),size=page*16384;
    uint8_t *memory=mmap(NULL,size,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0);if(memory==MAP_FAILED)abort();
    for(size_t i=0;i<size/page;i++)*(uint32_t*)(memory+i*page)=0x5a000000u+(uint32_t)i;
    NVNT_nvnMemoryPoolInitialize init=atlas_api("nvnMemoryPoolInitialize");NVNT_nvnMemoryPoolFinalize finalize=atlas_api("nvnMemoryPoolFinalize");
    pool_t physical;pool_builder_t builder={.mem=memory,.size=size,.flags=0x28};if(!init((NVNmemoryPool*)&physical,(NVNmemoryPoolBuilder*)&builder))abort();
    vkpool_t *pool=vk_pool_of((uint64_t)memory,size);memory_check(pool && pool->zero_copy,"fragmentation fixture uses real dma-buf");
    unsigned initial=memory_map_count();
    for(size_t i=0;i<size/page;i+=2)nvn_dirty_protect(memory+i*page,page);
    nvn_dirty_protect(memory,size); // adjacent protections do not merge these dma-buf mappings
    unsigned fragmented=memory_map_count();memory_check(fragmented>initial+8000,"fragmented thousands of adjacent read-only ranges");
    mtl_sub_begin(); // production maintenance must run before any presented frames
    unsigned compacted=memory_map_count();memory_check(compacted+8000<fragmented,"submission maintenance compacts mappings");
    VkBuffer buffer;VkDeviceSize offset;if(!vk_buf_at((uint64_t)memory,size,&buffer,&offset))abort();
    vkCmdFillBuffer(vk_cmd(),buffer,offset+16,4,0x1234abcd);if(!mtl_wait(mtl_sub_commit(),10000000000ull))abort();
    int ok=1;for(size_t i=0;i<size/page;i++)ok&=*(uint32_t*)(memory+i*page)==0x5a000000u+(uint32_t)i;
    memory_check(ok,"every source page preserved after remapping");
    memory_check(*(uint32_t*)(memory+16)==0x1234abcd,"GPU writes use the same remapped storage");
    uint64_t stamp=nvn_dirty_now();memory[0]=0x71;
    memory_check(nvn_dirty_since(memory,1,stamp),"CPU write still faults and invalidates after compaction");
    memory_check(!nvn_dirty_since(memory+page,page,stamp),"untouched protected page stays clean");
    nvn_dirty_protect(memory,page);stamp=nvn_dirty_now();dm_guest_write_prepare(memory,page);memory[1]=0x72;
    memory_check(nvn_dirty_since(memory,2,stamp),"host writes remain visible after compaction");
    printf("fragmentation mappings: initial=%u fragmented=%u compacted=%u\n",initial,fragmented,compacted);
    finalize((NVNmemoryPool*)&physical);munmap(memory,size);
}
static void pool_registry_tests(void) {
    enum { N=5120 };size_t page=(size_t)getpagesize(),size=N*page;
    uint8_t *memory=mmap(NULL,size,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0);if(memory==MAP_FAILED)abort();
    void vk_pool_add_flags(const void *,uint64_t,int);
    // One real buffer remains cached while the index crosses its old ceiling.
    mtl_pool_add(memory,page);vkpool_t *first=vk_pool_of((uint64_t)memory,page);uint64_t serial=first->serial;
    for(unsigned i=1;i<N;i++)vk_pool_add_flags(memory+(N-i)*page,page,NVN_MEMORY_POOL_FLAGS_CPU_CACHED|NVN_MEMORY_POOL_FLAGS_GPU_NO_ACCESS);
    vkpool_t *again=vk_pool_of((uint64_t)memory,page);
    memory_check(again==first && again->serial==serial && again->buf,"cached real-buffer record survives registry growth");
    int ok=1;for(unsigned i=0;i<N;i++){vkpool_t *p=vk_pool_of((uint64_t)(memory+i*page),page);ok&=p && p->lo==(uint64_t)(memory+i*page) && p->hi==p->lo+page;}
    memory_check(ok,"all 5120 live pool records remain addressable");
    struct timespec begin,end;clock_gettime(CLOCK_MONOTONIC,&begin);uint64_t identities=0;
    for(unsigned i=0;i<100000;i++){unsigned at=(uint32_t)(i*2654435761u)%N;vkpool_t *p=vk_pool_of((uint64_t)(memory+at*page),page);if(!p)abort();identities+=p->serial;}
    clock_gettime(CLOCK_MONOTONIC,&end);
    printf("pool registry 100000 lookups: %.3f ms, identity checksum %llu\n",(end.tv_sec-begin.tv_sec)*1000.0+(end.tv_nsec-begin.tv_nsec)/1e6,(unsigned long long)identities);
    vk_pool_add_flags(memory+2*page+16,4*page,NVN_MEMORY_POOL_FLAGS_CPU_CACHED|NVN_MEMORY_POOL_FLAGS_GPU_NO_ACCESS);
    vkpool_t *parent=vk_pool_of((uint64_t)(memory+3*page+8),2*page);
    memory_check(parent && parent->lo==(uint64_t)(memory+2*page+16),"overlapping wider pool remains visible behind the nearest start address");
    mtl_pool_del(memory+2*page+16);
    memory_check(!vk_pool_of(UINT64_MAX-15,32),"overflowing address ranges never match a cached pool");
    for(unsigned i=1;i<N;i+=2)mtl_pool_del(memory+i*page);
    ok=1;for(unsigned i=1;i<N;i+=2)ok&=!vk_pool_of((uint64_t)(memory+i*page),page);
    memory_check(ok,"removal invalidates cached entries without losing live records");
    for(unsigned i=1;i<N;i+=2)vk_pool_add_flags(memory+i*page,page,NVN_MEMORY_POOL_FLAGS_CPU_CACHED|NVN_MEMORY_POOL_FLAGS_GPU_NO_ACCESS);
    again=vk_pool_of((uint64_t)memory,page);memory_check(again==first && again->serial==serial,"recycling retired records preserves another pool's identity");
    mtl_sub_begin();VkBuffer buffer;VkDeviceSize offset;if(!vk_buf_at((uint64_t)memory,page,&buffer,&offset))abort();
    vkCmdFillBuffer(vk_cmd(),buffer,offset,page,0x7391abcd);memory_host_read_barrier();if(!mtl_wait(mtl_sub_commit(),10000000000ull))abort();
    ok=1;for(size_t i=0;i<page/4;i++)ok&=((uint32_t*)memory)[i]==0x7391abcd;
    memory_check(ok,"GPU writes still use the original buffer after growth and recycling");
    for(unsigned i=0;i<N;i++)mtl_pool_del(memory+i*page);
    ok=1;for(unsigned i=0;i<N;i++)ok&=!vk_pool_of((uint64_t)(memory+i*page),page);
    memory_check(ok,"finalization removes every pool including reused slots");munmap(memory,size);
}
static void scratch_retirement_tests(void) {
    const size_t size=64u<<20;uint32_t *destination=mmap(NULL,size,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0);if(destination==MAP_FAILED)abort();
    mtl_pool_add(destination,size);VkBuffer target;VkDeviceSize target_offset;if(!vk_buf_at((uint64_t)destination,size,&target,&target_offset))abort();
    mtl_sub_begin();VkBuffer source;VkDeviceSize offset;uint32_t *words=vk_scratch(size,16,&source,&offset);
    for(size_t i=0;i<size/4;i++)words[i]=(uint32_t)i^0x91a2b3c4u;
    VkBufferCopy copy={offset,target_offset,size};vkCmdCopyBuffer(vk_cmd(),source,target,1,&copy);
    uint64_t live,peak,released;vk_scratch_stats(&live,&peak,&released);memory_check(live>=size && released==0,"large scratch remains allocated while GPU work uses it");
    uint64_t fence=mtl_sub_commit();
    for(unsigned i=0;i<36;i++){
        mtl_sub_begin();uint32_t *value=vk_scratch(4,16,&source,&offset);*value=0x7abc0000u+i;
        copy=(VkBufferCopy){offset,target_offset+size-4*(i+1),4};vkCmdCopyBuffer(vk_cmd(),source,target,1,&copy);memory_host_read_barrier();fence=mtl_sub_commit();
    }
    if(!mtl_wait(fence,10000000000ull))abort();
    int ok=1;for(size_t i=0;i<size/4;i++){uint32_t expected=i<size/4-36?((uint32_t)i^0x91a2b3c4u):0x7abc0000u+(uint32_t)(size/4-i-1);ok&=destination[i]==expected;}
    memory_check(ok,"GPU copies preserve all 64 MiB across slot recycling");
    vk_scratch_stats(&live,&peak,&released);memory_check(released>=size,"idle loading-sized scratch is reclaimed");
    memory_check(live<=6u*(8u<<20),"small uniforms do not retain the large upload block");
    printf("scratch bytes: live=%llu peak=%llu released=%llu\n",(unsigned long long)live,(unsigned long long)peak,(unsigned long long)released);
    mtl_pool_del(destination);munmap(destination,size);
}
static void image_heap_tests(void) {
    enum{N=12,W=512};VkImage images[N];void *subs[N];size_t bytes=(size_t)W*W*4;
    VkImageSubresourceRange range={VK_IMAGE_ASPECT_COLOR_BIT,0,1,0,1};
    uint64_t reserved,occupied,empty;mtl_sub_begin();VkBuffer output;VkDeviceSize offset;
    uint8_t *pixels=vk_scratch(N*bytes,16,&output,&offset);
    for(unsigned i=0;i<N;i++){
        VkImageCreateInfo info={.sType=VK_STRUCTURE_TYPE_IMAGE_CREATE_INFO,.imageType=VK_IMAGE_TYPE_2D,.format=VK_FORMAT_R8G8B8A8_UNORM,.extent={W,W,1},.mipLevels=1,.arrayLayers=1,.samples=VK_SAMPLE_COUNT_1_BIT,.tiling=VK_IMAGE_TILING_OPTIMAL,.usage=VK_IMAGE_USAGE_TRANSFER_SRC_BIT|VK_IMAGE_USAGE_TRANSFER_DST_BIT};
        VKCHK(vkCreateImage(V.dev,&info,NULL,&images[i]));VkMemoryRequirements req;vkGetImageMemoryRequirements(V.dev,images[i],&req);VkDeviceSize image_offset;
        VkDeviceMemory memory=vk_image_memory(&req,vk_mem_type(req.memoryTypeBits,VK_MEMORY_PROPERTY_DEVICE_LOCAL_BIT,0),&image_offset,&subs[i]);if(!memory || !subs[i])abort();VKCHK(vkBindImageMemory(V.dev,images[i],memory,image_offset));
        if(!i){vk_image_heap_stats(&reserved,&occupied,&empty);memory_check(reserved<=8u<<20,"one render target starts with a small image block");}
        VkImageMemoryBarrier barrier={.sType=VK_STRUCTURE_TYPE_IMAGE_MEMORY_BARRIER,.dstAccessMask=VK_ACCESS_TRANSFER_WRITE_BIT,.oldLayout=VK_IMAGE_LAYOUT_UNDEFINED,.newLayout=VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL,.srcQueueFamilyIndex=VK_QUEUE_FAMILY_IGNORED,.dstQueueFamilyIndex=VK_QUEUE_FAMILY_IGNORED,.image=images[i],.subresourceRange=range};
        vkCmdPipelineBarrier(vk_cmd(),VK_PIPELINE_STAGE_TOP_OF_PIPE_BIT,VK_PIPELINE_STAGE_TRANSFER_BIT,0,0,NULL,0,NULL,1,&barrier);
        VkClearColorValue color={.float32={i/255.0f,(i+32)/255.0f,(i+96)/255.0f,1}};vkCmdClearColorImage(vk_cmd(),images[i],VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL,&color,1,&range);
        barrier.srcAccessMask=VK_ACCESS_TRANSFER_WRITE_BIT;barrier.dstAccessMask=VK_ACCESS_TRANSFER_READ_BIT;barrier.oldLayout=VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL;barrier.newLayout=VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL;
        vkCmdPipelineBarrier(vk_cmd(),VK_PIPELINE_STAGE_TRANSFER_BIT,VK_PIPELINE_STAGE_TRANSFER_BIT,0,0,NULL,0,NULL,1,&barrier);
        VkBufferImageCopy copy={.bufferOffset=offset+i*bytes,.imageSubresource={VK_IMAGE_ASPECT_COLOR_BIT,0,0,1},.imageExtent={W,W,1}};vkCmdCopyImageToBuffer(vk_cmd(),images[i],VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL,output,1,&copy);
        vk_defer_free_image_sub(images[i],subs[i]);
    }
    vk_image_heap_stats(&reserved,&occupied,&empty);memory_check(occupied>=N*bytes,"queued images retain their storage until the fence");
    memory_host_read_barrier();uint64_t fence=mtl_sub_commit();if(!mtl_wait(fence,10000000000ull))abort();
    int ok=1;for(unsigned i=0;i<N;i++)for(size_t p=0;p<bytes;p+=4){uint8_t *pixel=pixels+i*bytes+p;ok&=pixel[0]==i && pixel[1]==i+32 && pixel[2]==i+96 && pixel[3]==255;}
    memory_check(ok,"all pixels of twelve shared images remain independent");
    uint64_t high=reserved;for(unsigned i=0;i<8;i++){mtl_sub_begin();fence=mtl_sub_commit();}if(!mtl_wait(fence,10000000000ull))abort();
    vk_image_heap_stats(&reserved,&occupied,&empty);memory_check(occupied==0,"retired image slots return after GPU completion");
    memory_check(reserved==empty && reserved<=8u<<20,"only one small empty block remains cached");
    memory_check(reserved<high,"surplus empty image blocks are released");
    printf("image heap bytes: before_retirement=%llu reserved=%llu occupied=%llu empty=%llu\n",(unsigned long long)high,(unsigned long long)reserved,(unsigned long long)occupied,(unsigned long long)empty);
}
static void cpu_file_tests(void) {
    setenv("DM_VK_CPU_BACKING","file",1);if(!getenv("DM_TEMP"))setenv("DM_TEMP",".",1);
    NVNT_nvnMemoryPoolInitialize init=atlas_api("nvnMemoryPoolInitialize");NVNT_nvnMemoryPoolFinalize finalize=atlas_api("nvnMemoryPoolFinalize");
    const size_t sizes[]={1u<<20,(3u<<20)+(size_t)getpagesize(),64u<<20};
    for(unsigned test=0;test<3;test++){
        size_t size=sizes[test];uint8_t *memory=mmap(NULL,size,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0);if(memory==MAP_FAILED)abort();
        for(size_t i=0;i<size;i++)memory[i]=(uint8_t)(i*19+(i>>12));
        uint64_t before,peak,count;vk_memory_stats(&before,&peak,&count);
        pool_t pool;pool_builder_t b={.mem=memory,.size=size,.flags=0x18c};if(!init((NVNmemoryPool*)&pool,(NVNmemoryPoolBuilder*)&b))abort();
        vkpool_t *p=vk_pool_of((uint64_t)memory,size);uint64_t after,c2;vk_memory_stats(&after,&peak,&c2);
        memory_check(p && p->cpu_file && !p->buf && pool.mem==memory && before==after && count==c2,"file-backed CPU pool keeps its address without GPU allocation");
        int ok=1;for(size_t i=0;i<size;i++)ok&=memory[i]==(uint8_t)(i*19+(i>>12));memory_check(ok,"every original canonical byte survives file mapping");
        nvn_dirty_protect(memory,size);uint64_t stamp=nvn_dirty_now();dm_guest_write_prepare(memory,1);memory[0]=0x72;
        memory_check(nvn_dirty_since(memory,1,stamp),"file-backed host writes retain dirty tracking");
        if(msync(memory,size,MS_SYNC) || madvise(memory,size,MADV_DONTNEED))abort();
        ok=1;for(size_t i=0;i<size;i++)ok&=memory[i]==(i?(uint8_t)(i*19+(i>>12)):0x72);memory_check(ok,"kernel eviction and reload preserve all changed and untouched bytes");
        finalize((NVNmemoryPool*)&pool);memory[size-1]=0x39;
        if(msync(memory,size,MS_SYNC) || madvise(memory,size,MADV_DONTNEED))abort();
        memory_check(memory[0]==0x72 && memory[size-1]==0x39,"canonical storage stays writable after pool finalization");
        munmap(memory,size);
    }
}
static unsigned lazy_pool_flags=0x24;
static void lazy_pool_tests(void) {
    void crash_install(void);crash_install();setenv("DM_VK_LAZY_CACHED_POOLS","1",1);setenv("DM_VK_CPU_BACKING","file",1);if(!getenv("DM_TEMP"))setenv("DM_TEMP",".",1);
    NVNT_nvnMemoryPoolInitialize init=atlas_api("nvnMemoryPoolInitialize");NVNT_nvnMemoryPoolFinalize finalize=atlas_api("nvnMemoryPoolFinalize");
    size_t size=16u<<20;uint32_t *source=mmap(NULL,size,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0),*output=NULL;if(source==MAP_FAILED)abort();
    for(size_t i=0;i<size/4;i++)source[i]=(uint32_t)i^0x6a3c981bu;
    uint64_t before,peak,count;vk_memory_stats(&before,&peak,&count);
    int file_backed=(lazy_pool_flags&7)==NVN_MEMORY_POOL_FLAGS_CPU_CACHED;
    pool_t pool;pool_builder_t builder={.mem=source,.size=size,.flags=lazy_pool_flags};if(!init((NVNmemoryPool*)&pool,(NVNmemoryPoolBuilder*)&builder))abort();
    vkpool_t *p=vk_pool_of((uint64_t)source,size);uint64_t after,c2;vk_memory_stats(&after,&peak,&c2);
    memory_check(p && p->lazy && p->cpu_file==file_backed && !p->buf && before==after && count==c2,"CPU pool allocates no GPU buffer before a binding");
    nvn_dirty_protect(source,size);source[0]=0x19d3a74b;
    if(file_backed && (msync(source,size,MS_SYNC) || madvise(source,size,MADV_DONTNEED)))abort();
    mtl_sub_begin();VkBuffer staging,input;VkDeviceSize staging_offset,input_offset;output=vk_scratch(size,16,&staging,&staging_offset);if(!vk_buf_at((uint64_t)source,size,&input,&input_offset))abort();VkBufferCopy copy={input_offset,staging_offset,size};vkCmdCopyBuffer(vk_cmd(),input,staging,1,&copy);vk_img_barrier_all(vk_cmd());mtl_sub_fill((uint64_t)source+64,16,0x72ad183b);memory_host_read_barrier();if(!mtl_wait(mtl_sub_commit(),10000000000ull))abort();
    memory_check(p->buf && !p->lazy && p->gpu_used,"first buffer copy materializes the cached source");
    int ok=1;for(size_t i=0;i<size/4;i++)ok&=output[i]==(i?((uint32_t)i^0x6a3c981bu):0x19d3a74b);memory_check(ok,"first GPU binding sees every original and changed source word");
    memory_check(source[16]==0x72ad183b && source[19]==0x72ad183b,"GPU writes in the first materialized submission reach canonical bytes");
    nvn_dirty_protect(source,size);uint64_t stamp=nvn_dirty_now();source[7]=0x84b912c3;
    memory_check(nvn_dirty_since(source+7,4,stamp),"CPU writes remain tracked after GPU materialization");
    mtl_sub_begin();output=vk_scratch(size,16,&staging,&staging_offset);if(!vk_buf_at((uint64_t)source,size,&input,&input_offset))abort();copy=(VkBufferCopy){input_offset,staging_offset,size};vkCmdCopyBuffer(vk_cmd(),input,staging,1,&copy);memory_host_read_barrier();if(!mtl_wait(mtl_sub_commit(),10000000000ull))abort();
    memory_check(output[7]==0x84b912c3 && output[0]==0x19d3a74b,"later CPU writes reach the GPU buffer");
    mtl_sub_begin();mtl_sub_fill((uint64_t)source+64,16,0x72ad183b);memory_host_read_barrier();if(!mtl_wait(mtl_sub_commit(),10000000000ull))abort();
    ok=1;for(size_t i=16;i<20;i++)ok&=source[i]==0x72ad183b;memory_check(ok,"GPU writes return to the canonical CPU storage");
    finalize((NVNmemoryPool*)&pool);memory_check(source[7]==0x84b912c3 && source[16]==0x72ad183b,"finalization preserves materialized CPU and GPU writes");
    builder=(pool_builder_t){.mem=source,.size=size,.flags=lazy_pool_flags};if(!init((NVNmemoryPool*)&pool,(NVNmemoryPoolBuilder*)&builder))abort();p=vk_pool_of((uint64_t)source,size);
    memory_check(p && p->lazy && !p->buf,"reused canonical storage may remain a CPU-only texture source");
    pool_t overlap;pool_builder_t alias={.mem=(uint8_t *)source+getpagesize(),.size=1u<<20,.flags=lazy_pool_flags};if(!init((NVNmemoryPool*)&overlap,(NVNmemoryPoolBuilder*)&alias))abort();
    memory_check(!p->lazy && p->buf,"a later overlapping pool first materializes deferred backing");
    vkpool_t *other=vk_pool_of((uint64_t)alias.mem,alias.size);memory_check(other && other->buf && !other->lazy,"overlapping registration retains the eager buffer path");
    finalize((NVNmemoryPool*)&overlap);finalize((NVNmemoryPool*)&pool);
    if(!init((NVNmemoryPool*)&pool,(NVNmemoryPoolBuilder*)&builder))abort();p=vk_pool_of((uint64_t)source,size);
    memory_check(p && p->lazy && !p->buf,"a fresh nonoverlapping pool defers GPU allocation again");
    finalize((NVNmemoryPool*)&pool);source[9]=0x183b72ad;if(file_backed && (msync(source,size,MS_SYNC) || madvise(source,size,MADV_DONTNEED)))abort();
    memory_check(source[9]==0x183b72ad && source[16]==0x72ad183b,"unmaterialized finalization retains writable canonical bytes");
    munmap(source,size);
}
static void lazy_all_pool_tests(void){setenv("DM_VK_LAZY_POOLS","1",1);unsigned flags[]={0x24,0x22,0x12,0x21,0xa1,0x62,0x64};for(unsigned i=0;i<sizeof flags/sizeof*flags;i++){lazy_pool_flags=flags[i];printf("lazy pool flags %#x\n",lazy_pool_flags);lazy_pool_tests();}}

typedef struct {VkSemaphore semaphore;PFN_vkSignalSemaphore signal;} copied_gate;
static void *copied_gate_release(void *opaque){copied_gate *gate=opaque;usleep(500000);VkSemaphoreSignalInfo info={.sType=VK_STRUCTURE_TYPE_SEMAPHORE_SIGNAL_INFO,.semaphore=gate->semaphore,.value=1};VKCHK(gate->signal(V.dev,&info));return NULL;}
static void copied_binding_tests(void) {
    void crash_install(void);crash_install();setenv("DM_VK_NO_ZEROCOPY","1",1);setenv("DM_VK_LAZY_CACHED_POOLS","0",1);setenv("DM_VK_LAZY_POOLS","0",1);
    size_t size=65536;uint32_t *source=mmap(NULL,size,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0);if(source==MAP_FAILED)abort();
    for(size_t i=0;i<size/4;i++)source[i]=(uint32_t)i^0x61e29ba4;
    NVNT_nvnMemoryPoolInitialize init=atlas_api("nvnMemoryPoolInitialize");NVNT_nvnMemoryPoolFinalize fini=atlas_api("nvnMemoryPoolFinalize");
    pool_t pool;pool_builder_t builder={.mem=source,.size=size,.flags=0x24};if(!init((NVNmemoryPool*)&pool,(NVNmemoryPoolBuilder*)&builder))abort();
    vkpool_t *registered=vk_pool_of((uint64_t)source,size);memory_check(registered && registered->shadow && !registered->gpu_used,"eager copied pool starts with no GPU reference");
    PFN_vkCreateSemaphore create=(PFN_vkCreateSemaphore)vkGetDeviceProcAddr(V.dev,"vkCreateSemaphore");PFN_vkDestroySemaphore destroy=(PFN_vkDestroySemaphore)vkGetDeviceProcAddr(V.dev,"vkDestroySemaphore");
    copied_gate gate={.signal=(PFN_vkSignalSemaphore)vkGetDeviceProcAddr(V.dev,"vkSignalSemaphore")};VkSemaphoreTypeCreateInfo type={.sType=VK_STRUCTURE_TYPE_SEMAPHORE_TYPE_CREATE_INFO,.semaphoreType=VK_SEMAPHORE_TYPE_TIMELINE};VkSemaphoreCreateInfo info={.sType=VK_STRUCTURE_TYPE_SEMAPHORE_CREATE_INFO,.pNext=&type};VKCHK(create(V.dev,&info,NULL,&gate.semaphore));
    uint64_t value=1;VkTimelineSemaphoreSubmitInfo timeline={.sType=VK_STRUCTURE_TYPE_TIMELINE_SEMAPHORE_SUBMIT_INFO,.waitSemaphoreValueCount=1,.pWaitSemaphoreValues=&value};VkPipelineStageFlags stage=VK_PIPELINE_STAGE_ALL_COMMANDS_BIT;VkSubmitInfo queued={.sType=VK_STRUCTURE_TYPE_SUBMIT_INFO,.pNext=&timeline,.waitSemaphoreCount=1,.pWaitSemaphores=&gate.semaphore,.pWaitDstStageMask=&stage};extern pthread_mutex_t g_vk_queue_mu;pthread_mutex_lock(&g_vk_queue_mu);VkResult submitted=vkQueueSubmit(V.q,1,&queued,VK_NULL_HANDLE);pthread_mutex_unlock(&g_vk_queue_mu);VKCHK(submitted);
    mtl_sub_begin();uint64_t pending=mtl_sub_commit();pthread_t thread;if(pthread_create(&thread,NULL,copied_gate_release,&gate))abort();
    mtl_sub_begin();memory_check(vk_fence_done()<pending,"unbound copied storage does not drain unrelated GPU work");source[0]=0x5ab31d72;uint64_t fence=mtl_sub_commit();pthread_join(thread,NULL);if(!mtl_wait(fence,10000000000ull))abort();destroy(V.dev,gate.semaphore,NULL);
    memory_check(source[0]==0x5ab31d72 && !registered->synced,"unused storage keeps CPU writes without upload or copyback");
    mtl_sub_begin();VkBuffer output,input;VkDeviceSize out_offset,in_offset;uint32_t *actual=vk_scratch(size,16,&output,&out_offset);if(!vk_buf_at((uint64_t)source,size,&input,&in_offset))abort();VkBufferCopy copy={in_offset,out_offset,size};vkCmdCopyBuffer(vk_cmd(),input,output,1,&copy);vk_img_barrier_all(vk_cmd());mtl_sub_fill((uint64_t)source+64,16,0x19ce834b);memory_host_read_barrier();if(!mtl_wait(mtl_sub_commit(),10000000000ull))abort();
    int ok=1;for(size_t i=0;i<size/4;i++)ok&=actual[i]==(i?((uint32_t)i^0x61e29ba4):0x5ab31d72);memory_check(ok,"first binding uploads every canonical word before GPU reads");
    memory_check(source[16]==0x19ce834b && source[19]==0x19ce834b,"first used submission copies GPU writes back to the CPU");
    fini((NVNmemoryPool*)&pool);memory_check(source[0]==0x5ab31d72 && source[16]==0x19ce834b,"copied pool finalization preserves CPU and GPU writes");munmap(source,size);
}
