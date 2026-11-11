// Reproducible offscreen measurements. These jobs are not gameplay frames.
#include <time.h>
#include <CommonCrypto/CommonDigest.h>
extern uint64_t vk_atlas_peak_bytes(void);
static uint64_t measure_ns(clockid_t clock) { struct timespec t;if(clock_gettime(clock,&t))abort();return (uint64_t)t.tv_sec*1000000000ull+(uint64_t)t.tv_nsec; }
static long measure_proc(const char *file,const char *field) {
    FILE *fp=fopen(file,"r");if(!fp)return -1;char line[256];long value=-1;
    while(fgets(line,sizeof line,fp))if(!strncmp(line,field,strlen(field))){if(sscanf(line+strlen(field),"%ld",&value)!=1)value=-1;break;}fclose(fp);return value;
}
static void measure_sample(uint8_t *job,const tex_t *t,AtlasQuery *q,const char *phase,unsigned iteration,VkQueryPool query,uint64_t mask) {
    uint64_t before_alloc,before_up,before_re,before_meta;vk_atlas_stats(&before_alloc,&before_up,&before_re,&before_meta);
    uint64_t begin=measure_ns(CLOCK_MONOTONIC),cpu=measure_ns(CLOCK_THREAD_CPUTIME_ID);mtl_sub_begin();uint64_t opened=measure_ns(CLOCK_MONOTONIC);
    VkCommandBuffer cb=vk_cmd();vkCmdResetQueryPool(cb,query,0,2);vkCmdWriteTimestamp(cb,VK_PIPELINE_STAGE_TOP_OF_PIPE_BIT,query,0);
    atlas_record(job,t,NULL,0,q,4);vkCmdWriteTimestamp(vk_cmd(),VK_PIPELINE_STAGE_BOTTOM_OF_PIPE_BIT,query,1);
    uint64_t prepared=measure_ns(CLOCK_MONOTONIC),cpu_prepared=measure_ns(CLOCK_THREAD_CPUTIME_ID),fence=mtl_sub_commit(),submitted=measure_ns(CLOCK_MONOTONIC);
    if(!mtl_wait(fence,10000000000ull))abort();uint64_t finished=measure_ns(CLOCK_MONOTONIC),ticks[2];
    VkResult result=vkGetQueryPoolResults(V.dev,query,0,2,sizeof ticks,ticks,8,VK_QUERY_RESULT_64_BIT);if(result!=VK_SUCCESS)die("[RED] completed measurement timestamps unavailable: %d",result);double gpu_ns=(double)((ticks[1]-ticks[0])&mask)*V.props.limits.timestampPeriod;
    uint64_t allocated,uploaded,reused,metadata;vk_atlas_stats(&allocated,&uploaded,&reused,&metadata);
    float *actual=(float*)(job+4096);int correct=fabsf(actual[0]-2)<.03f && actual[3]==1 && fabsf(actual[8+2]-1)<.03f && actual[11]==1 && actual[12]==8192 && actual[13]==8192 && actual[14]==68 && actual[15]==12;
    if(!correct)die("[RED] measured workload sampled incorrect atlas data");
    printf("%s,%u,%llu,%llu,%llu,%llu,%llu,%.0f,%ld,%ld,%ld,%ld,%llu,%llu,%llu,%llu,%llu\n",phase,iteration,(unsigned long long)(opened-begin),(unsigned long long)(prepared-opened),(unsigned long long)(cpu_prepared-cpu),(unsigned long long)(submitted-prepared),(unsigned long long)(finished-submitted),gpu_ns,measure_proc("/proc/self/status","VmRSS:"),measure_proc("/proc/self/status","VmHWM:"),measure_proc("/proc/self/smaps_rollup","Pss:"),measure_proc("/proc/self/smaps_rollup","SwapPss:"),(unsigned long long)allocated,(unsigned long long)(uploaded-before_up),(unsigned long long)(metadata-before_meta),(unsigned long long)(reused-before_re),(unsigned long long)vk_atlas_peak_bytes());fflush(stdout);
}
static void measure_atlas(void) {
    unsigned count=512,frames=60,changes=30;const char *e=getenv("DM_MEASURE_CELLS");if(e)count=(unsigned)strtoul(e,NULL,10);e=getenv("DM_MEASURE_FRAMES");if(e)frames=(unsigned)strtoul(e,NULL,10);
    if(!count || count>1024 || frames<10 || frames>1000)die("[RED] invalid measurement workload size");
    atlas_format=0;atlas_width=atlas_height=8192;atlas_layers=68;nvn_gob_switch2=1;
    tex_t t={.magic=MAGIC('T','E','X',0),.serial=25001,.d={.target=NVN_TEXTURE_TARGET_2D_ARRAY,.format=NVN_FORMAT_BPTC_UFLOAT,.flags=NVN_TEXTURE_FLAGS_SPARSE,.width=8192,.height=8192,.depth=68,.levels=12,.samples=1}};
    nvn_tex_layout(&t.d,&t.L);uint32_t td;atlas_tail=nvn_tex_sparse_tiles(&t.d,&atlas_tw,&atlas_th,&td);
    size_t bytes=(size_t)(count+changes)*65536;uint8_t *source=mmap(NULL,bytes,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0),*job=mmap(NULL,65536,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0);if(source==MAP_FAILED || job==MAP_FAILED)abort();
    uint64_t fill_begin=measure_ns(CLOCK_MONOTONIC);for(unsigned i=0;i<count+changes;i++){atlas_nonce=i+1;atlas_fill(&t,source+(size_t)i*65536,4,0);}atlas_nonce=0;
    NVNT_nvnMemoryPoolInitialize init=atlas_api("nvnMemoryPoolInitialize");NVNT_nvnMemoryPoolFinalize finalize=atlas_api("nvnMemoryPoolFinalize");NVNT_nvnMemoryPoolMapVirtual map=atlas_api("nvnMemoryPoolMapVirtual");
    pool_t physical={0},virtual={0};pool_builder_t pb={.mem=source,.size=bytes,.flags=0x24};if(!init((NVNmemoryPool*)&physical,(NVNmemoryPoolBuilder*)&pb))abort();t.off=0x800000000ll;pb=(pool_builder_t){.size=t.off+t.L.size+65536,.flags=0x200};if(!init((NVNmemoryPool*)&virtual,(NVNmemoryPoolBuilder*)&pb))abort();t.pool=&virtual;t.mem=virtual.mem+t.off;
    AtlasMapping *mapping=calloc(count,sizeof *mapping);for(unsigned i=0;i<count;i++)mapping[i]=(AtlasMapping){(NVNmemoryPool*)&physical,(int64_t)i*65536,t.off+(int64_t)i*65536,65536,0,0};if(!map((NVNmemoryPool*)&virtual,(int)count,(NVNmappingRequest*)mapping))abort();free(mapping);mtl_pool_add(job,65536);
    samp_par sampler={.minf=5,.magf=1,.aniso=1,.lod_max=1000};mtl_reg_samp(1,&sampler);AtlasQuery *q=(AtlasQuery*)(job+16384);q[0]=(AtlasQuery){.x=16,.y=16};q[1]=(AtlasQuery){.x=32,.y=32};q[2]=(AtlasQuery){.x=40,.y=32};q[3]=(AtlasQuery){.mode=2};
    uint32_t nq=0;vkGetPhysicalDeviceQueueFamilyProperties(V.pd,&nq,NULL);VkQueueFamilyProperties *families=calloc(nq,sizeof*families);vkGetPhysicalDeviceQueueFamilyProperties(V.pd,&nq,families);unsigned bits=families[V.qf].timestampValidBits;free(families);if(!bits || !V.props.limits.timestampComputeAndGraphics)die("[RED] measurement queue lacks timestamp support");uint64_t mask=bits==64?UINT64_MAX:(1ull<<bits)-1;
    VkQueryPool query;VkQueryPoolCreateInfo ci={VK_STRUCTURE_TYPE_QUERY_POOL_CREATE_INFO,NULL,0,VK_QUERY_TYPE_TIMESTAMP,2};VKCHK(vkCreateQueryPool(V.dev,&ci,NULL,&query));
    printf("# device=%s timestamp_bits=%u period_ns=%g logical_bytes=%llu mapped_cells=%u source_bytes=%zu setup_ns=%llu\n",V.props.deviceName,bits,V.props.limits.timestampPeriod,(unsigned long long)t.L.size,count,bytes,(unsigned long long)(measure_ns(CLOCK_MONOTONIC)-fill_begin));
    printf("phase,iteration,begin_ns,prepare_wall_ns,prepare_thread_cpu_ns,submit_ns,wait_ns,gpu_main_ns,rss_kib,hwm_kib,pss_kib,swap_pss_kib,atlas_allocated_bytes,uploaded_bytes,metadata_bytes,cell_reuses,atlas_peak_bytes\n");
    measure_sample(job,&t,q,"first_use",0,query,mask);
    for(unsigned i=0;i<frames;i++)measure_sample(job,&t,q,"unchanged",i,query,mask);
    for(unsigned phase=0;phase<2;phase++)for(unsigned i=0;i<changes;i++){
        AtlasMapping change={(NVNmemoryPool*)&physical,(int64_t)(phase?count+i:1+i%(count>1?count-1:1))*65536,t.off,65536,0,0};if(!map((NVNmemoryPool*)&virtual,1,(NVNmappingRequest*)&change))abort();measure_sample(job,&t,q,phase?"new_content":"remap_existing",i,query,mask);
    }
    uint8_t expected_digest[32],actual_digest[32],job_digest[32];CC_SHA256(source,(CC_LONG)bytes,expected_digest);CC_SHA256(job,65536,job_digest);
    uint64_t cleanup=measure_ns(CLOCK_MONOTONIC);finalize((NVNmemoryPool*)&virtual);finalize((NVNmemoryPool*)&physical);mtl_pool_del(job);uint64_t allocated,up,re,meta;vk_atlas_stats(&allocated,&up,&re,&meta);printf("# cleanup_ns=%llu atlas_remaining_bytes=%llu rss_kib=%ld pss_kib=%ld\n",(unsigned long long)(measure_ns(CLOCK_MONOTONIC)-cleanup),(unsigned long long)allocated,measure_proc("/proc/self/status","VmRSS:"),measure_proc("/proc/self/smaps_rollup","Pss:"));if(allocated)abort();CC_SHA256(source,(CC_LONG)bytes,actual_digest);if(memcmp(expected_digest,actual_digest,32))die("[RED] pool restoration corrupted measured source bytes");CC_SHA256(job,65536,actual_digest);if(memcmp(job_digest,actual_digest,32))die("[RED] pool restoration corrupted measured GPU output bytes");printf("# source_bytes_preserved=%zu output_bytes_preserved=65536\n",bytes);
    PFN_vkDestroyQueryPool destroy=(PFN_vkDestroyQueryPool)vkGetDeviceProcAddr(V.dev,"vkDestroyQueryPool");destroy(V.dev,query,NULL);munmap(source,bytes);munmap(job,65536);printf("# released_workload rss_kib=%ld pss_kib=%ld hwm_kib=%ld atlas_peak_bytes=%llu\n",measure_proc("/proc/self/status","VmRSS:"),measure_proc("/proc/self/smaps_rollup","Pss:"),measure_proc("/proc/self/status","VmHWM:"),(unsigned long long)vk_atlas_peak_bytes());
}

static void measure_restore_check(void) {
    size_t page=(size_t)getpagesize(),sizes[]={page,65536-page,65536,65536+page,131072+page};
    for(unsigned k=0;k<sizeof sizes/sizeof*sizes;k++){
        size_t bytes=sizes[k];if(!bytes)continue;uint8_t *mem=mmap(NULL,bytes,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0);if(mem==MAP_FAILED)abort();
        for(size_t i=0;i<bytes;i++)mem[i]=(uint8_t)(i*13+k);mtl_pool_add(mem,bytes);
        mtl_sub_begin();mtl_sub_fill((uint64_t)(mem+page/2),256,0x1a2b3c4d);if(!mtl_wait(mtl_sub_commit(),10000000000ull))abort();
        for(unsigned i=0;i<64;i++){uint32_t value;memcpy(&value,mem+page/2+i*4,4);if(value!=0x1a2b3c4d)die("[RED] pool restore check did not see GPU writes");}
        uint8_t expected[32],actual[32];CC_SHA256(mem,(CC_LONG)bytes,expected);mtl_pool_del(mem);CC_SHA256(mem,(CC_LONG)bytes,actual);if(memcmp(expected,actual,32))die("[RED] pool restore check lost CPU/GPU bytes");
        printf("pool restore %zu bytes PASS\n",bytes);munmap(mem,bytes);
    }
}
