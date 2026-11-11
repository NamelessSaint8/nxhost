// Explicit Vulkan device-memory allocations. Resource aliases/suballocations
// share one record; CPU mappings do not add another allocation. These bytes
// overlap process RSS/PSS and exclude driver-internal shader/pipeline memory.
#include "gfx_vk.h"
#include "nvn_hmap.h"
#include <malloc.h>
typedef struct { VkDeviceMemory memory; uint64_t bytes;const char *site;int line; } memory_record;
static nvn_hmap records = {.klen = sizeof(VkDeviceMemory)};
static pthread_mutex_t memory_mu = PTHREAD_MUTEX_INITIALIZER;
static uint64_t live_bytes, peak_bytes, live_allocations;
VkResult vk_memory_allocate_at(VkDevice device, const VkMemoryAllocateInfo *info, const VkAllocationCallbacks *callbacks, VkDeviceMemory *memory,const char *site,int line) {
    memory_record *record = malloc(sizeof *record);
    if (!record) return VK_ERROR_OUT_OF_HOST_MEMORY;
    VkResult result = vkAllocateMemory(device, info, callbacks, memory);
    if (result != VK_SUCCESS) { free(record); return result; }
    record->memory = *memory; record->bytes = info->allocationSize;record->site=site;record->line=line;
    pthread_mutex_lock(&memory_mu);
    nvn_hm_put(&records, memory, record);
    live_bytes += record->bytes; live_allocations++;
    int report = (live_bytes >> 27) > (peak_bytes >> 27);
    if (live_bytes > peak_bytes) peak_bytes = live_bytes;
    uint64_t live = live_bytes, peak = peak_bytes, count = live_allocations;
    pthread_mutex_unlock(&memory_mu);
    if (report) {
        VKLOG("Vulkan allocation peak: live %.2f MiB, peak %.2f MiB, count %llu (overlap process RAM; exclude driver internals)", live / 1048576.0, peak / 1048576.0, (unsigned long long)count);
        vk_memory_census_request();   // snapshot on the replay thread's next boundary, outside allocation/image locks
    }
    return result;
}
uint64_t vk_memory_size(VkDeviceMemory memory){
    pthread_mutex_lock(&memory_mu);memory_record *record=nvn_hm_get(&records,&memory);uint64_t bytes=record?record->bytes:0;pthread_mutex_unlock(&memory_mu);return bytes;
}
typedef struct {const char *site;int line;uint64_t bytes,count;} memory_bucket;
static int census_pending;
void vk_memory_census_request(void){__atomic_store_n(&census_pending,1,__ATOMIC_RELEASE);}
static int bucket_order(const void *a,const void *b){uint64_t x=((const memory_bucket*)a)->bytes,y=((const memory_bucket*)b)->bytes;return x<y?1:x>y?-1:0;}
void vk_memory_census(void) {
    const char *option=getenv("DM_VK_MEMORY_CENSUS");if(!option || !atoi(option))return;
    if(!__atomic_exchange_n(&census_pending,0,__ATOMIC_ACQ_REL))return;
    memory_bucket buckets[64]={0};unsigned count=0;pthread_mutex_lock(&memory_mu);
    for(uint32_t i=0;i<records.cap;i++){memory_record *record=records.vals[i];if(!record)continue;unsigned b=0;
        for(;b<count;b++)if(buckets[b].site==record->site && buckets[b].line==record->line)break;
        if(b==count){if(count==64)continue;buckets[count++]=(memory_bucket){.site=record->site,.line=record->line};}
        buckets[b].bytes+=record->bytes;buckets[b].count++;
    }
    uint64_t total=live_bytes;pthread_mutex_unlock(&memory_mu);qsort(buckets,count,sizeof *buckets,bucket_order);
    VKLOG("allocation census: %.2f MiB explicit Vulkan bytes (overlap RSS/PSS; exclude driver internals)",total/1048576.0);
    for(unsigned i=0;i<count;i++)VKLOG("allocation census: %s:%d %.2f MiB / %llu allocations",buckets[i].site,buckets[i].line,buckets[i].bytes/1048576.0,(unsigned long long)buckets[i].count);
    uint64_t ready,pending,objects;vk_deferred_memory_stats(&ready,&pending,&objects);
    VKLOG("allocation census: dedicated deferred frees %.2f MiB completed / %.2f MiB pending, %llu objects (suballocated image bytes excluded)",ready/1048576.0,pending/1048576.0,(unsigned long long)objects);
    uint64_t reserved,occupied,empty;vk_image_heap_stats(&reserved,&occupied,&empty);
    VKLOG("allocation census: image blocks reserved %.2f MiB, occupied slots %.2f MiB, entirely empty %.2f MiB",reserved/1048576.0,occupied/1048576.0,empty/1048576.0);
    VKLOG("allocation census: descriptor pools %llu",(unsigned long long)vk_descriptor_pool_count());vk_tex_memory_census();vk_pool_memory_census();
}
void vk_memory_free(VkDevice device, VkDeviceMemory memory, const VkAllocationCallbacks *callbacks) {
    if (memory) {
        pthread_mutex_lock(&memory_mu);
        memory_record *record = nvn_hm_get(&records, &memory);
        if (record) { live_bytes -= record->bytes; live_allocations--; nvn_hm_del(&records, &memory); free(record); }
        pthread_mutex_unlock(&memory_mu);
    }
    vkFreeMemory(device, memory, callbacks);
}
void vk_memory_stats(uint64_t *live, uint64_t *peak, uint64_t *allocations) {
    pthread_mutex_lock(&memory_mu);
    *live = live_bytes; *peak = peak_bytes; *allocations = live_allocations;
    pthread_mutex_unlock(&memory_mu);
}
static uint64_t allocator_rss(void) {
    FILE *file=fopen("/proc/self/status","r");if(!file)return 0;char line[256];unsigned long long kb=0;
    while(fgets(line,sizeof line,file))if(sscanf(line,"VmRSS: %llu kB",&kb)==1)break;
    fclose(file);return (uint64_t)kb*1024;
}
void vk_compiler_memory_release(void) {
    const char *option=getenv("DM_VK_COMPILER_PURGE");if(!option || !atoi(option))return;
    // Driver compilers use the process allocator too. After a compilation batch
    // and cache serialization, reclaim only free allocator pages; live shaders,
    // game allocations and Vulkan resources remain owned by their callers.
    uint64_t before=allocator_rss();struct mallinfo heap=mallinfo();struct timespec a,b;clock_gettime(CLOCK_MONOTONIC,&a);
    int result=mallopt(M_PURGE_ALL,0);if(!result)result=mallopt(M_PURGE,0);
    clock_gettime(CLOCK_MONOTONIC,&b);uint64_t after=allocator_rss();
    VKLOG("compiler allocator reclaim: result %d, RSS %.2f -> %.2f MiB, heap allocated %.2f MiB free %.2f MiB (approximate concurrent allocator counters), %.2f ms",result,before/1048576.0,after/1048576.0,heap.uordblks/1048576.0,heap.fordblks/1048576.0,(b.tv_sec-a.tv_sec)*1000.0+(b.tv_nsec-a.tv_nsec)/1e6);
}
