// Compare real NVN reports, through their public conversion API, with Vulkan
// elapsed timestamps around the same GPU work and the current guest epoch.
static void timestamp_tests(void){
    NVNT_nvnDeviceGetTimestampInNanoseconds convert=atlas_api("nvnDeviceGetTimestampInNanoseconds");
    uint64_t *reports=mmap(NULL,65536,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0);if(reports==MAP_FAILED)abort();mtl_pool_add(reports,65536);
    VkQueryPool query;VkQueryPoolCreateInfo ci={.sType=VK_STRUCTURE_TYPE_QUERY_POOL_CREATE_INFO,.queryType=VK_QUERY_TYPE_TIMESTAMP,.queryCount=2};VKCHK(vkCreateQueryPool(V.dev,&ci,NULL,&query));
    for(unsigned iteration=0;iteration<3;iteration++){
        dm_guest_write_prepare(reports,32);memset(reports,0xcc,32);uint64_t before=guest_ns();if(!before)before=measure_ns(CLOCK_MONOTONIC);
        mtl_sub_begin();VkBuffer buffer;VkDeviceSize offset;size_t bytes=(8u<<20)<<iteration;vk_scratch(bytes,16,&buffer,&offset);vkCmdResetQueryPool(vk_cmd(),query,0,2);vkCmdWriteTimestamp(vk_cmd(),VK_PIPELINE_STAGE_BOTTOM_OF_PIPE_BIT,query,0);mtl_sub_counter((uint64_t)reports,0);
        for(unsigned i=0;i<64;i++){vkCmdFillBuffer(vk_cmd(),buffer,offset,bytes,i);VkMemoryBarrier barrier={.sType=VK_STRUCTURE_TYPE_MEMORY_BARRIER,.srcAccessMask=VK_ACCESS_TRANSFER_WRITE_BIT,.dstAccessMask=VK_ACCESS_TRANSFER_WRITE_BIT};vkCmdPipelineBarrier(vk_cmd(),VK_PIPELINE_STAGE_TRANSFER_BIT,VK_PIPELINE_STAGE_TRANSFER_BIT,0,1,&barrier,0,NULL,0,NULL);}
        mtl_sub_counter((uint64_t)(reports+2),0);vkCmdWriteTimestamp(vk_cmd(),VK_PIPELINE_STAGE_BOTTOM_OF_PIPE_BIT,query,1);if(!mtl_wait(mtl_sub_commit(),10000000000ull))abort();uint64_t after=guest_ns();if(!after)after=measure_ns(CLOCK_MONOTONIC);
        uint64_t ticks[2];VKCHK(vkGetQueryPoolResults(V.dev,query,0,2,sizeof ticks,ticks,8,VK_QUERY_RESULT_64_BIT));uint64_t gpu=(uint64_t)((double)(ticks[1]-ticks[0])*V.props.limits.timestampPeriod);
        uint64_t start=convert(NULL,(NVNcounterData*)reports),end=convert(NULL,(NVNcounterData*)(reports+2));uint64_t elapsed=end>=start?end-start:0;
        memory_check(reports[0]==0 && reports[2]==0,"timestamp reports preserve the separate zero counter field");
        memory_check(start>=before && start<=end && end<=after+1000000ull,"converted NVN timestamps share the current guest-clock epoch");
        memory_check(gpu>500000 && elapsed+200000>gpu*7/10 && elapsed<gpu*13/10+200000,"NVN elapsed nanoseconds agree with independent Vulkan GPU timestamps");
        printf("timestamp workload=%zu MiB GPU_ns=%llu NVN_ns=%llu ratio=%.5f\n",bytes*64/1048576,(unsigned long long)gpu,(unsigned long long)elapsed,gpu?(double)elapsed/gpu:0);
    }
    PFN_vkDestroyQueryPool destroy=(PFN_vkDestroyQueryPool)vkGetDeviceProcAddr(V.dev,"vkDestroyQueryPool");destroy(V.dev,query,NULL);mtl_pool_del(reports);munmap(reports,65536);
}
