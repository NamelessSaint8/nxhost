// Queue commits enumerate attached residency sets. Concurrent removal must not free an allocation during that read (Metal validation catches a dangling debug buffer).
#include "../nvn/nvn_mtl.m"
void *front_metal_layer(void) { return NULL; }
module_t *module_of(const void *p) { (void)p; return NULL; }
module_t *g_mod; int g_nmod;
void svc_thread_dump(void) {}
uint64_t now_ns(void) { return bp_now(); }
int main(void) { @autoreleasepool {
    mtl_init();
    dispatch_group_t writers = dispatch_group_create();
    dispatch_group_async(writers, dispatch_get_global_queue(QOS_CLASS_USER_INITIATED, 0), ^{
        for (int i = 0; i < 12000; i++) { @autoreleasepool {
            id<MTLBuffer> b = [g_dev newBufferWithLength:4096 options:MTLResourceStorageModeShared];
            res_add(b); res_commit(); res_remove(b); res_commit();
        } }
    });
    id<MTLSharedEvent> event = [g_dev newSharedEvent];
    for (uint64_t i = 1; i <= 12000; i++) { @autoreleasepool {
        id<MTL4CommandAllocator> a = [g_dev newCommandAllocator];
        id<MTL4CommandBuffer> cb = [g_dev newCommandBuffer];
        [cb beginCommandBufferWithAllocator:a]; [cb endCommandBuffer];
        queue4_commit(cb, nil); [g_q4 signalEvent:event value:i];
        if (![event waitUntilSignaledValue:i timeoutMS:5000]) { fprintf(stderr,"FAIL: residency stress submission %llu did not complete\n",i); return 1; }
        if (i % 100 == 0) {
            id<MTLCommandBuffer> classic = [g_q commandBuffer]; queue3_commit(classic); [classic waitUntilCompleted];
            if (classic.status != MTLCommandBufferStatusCompleted) return 1;
        }
    } }
    dispatch_group_wait(writers, DISPATCH_TIME_FOREVER);
    puts("residency commits: 12000 Metal 4 and 120 classic commits complete during 12000 allocation replacements");
    return 0;
} }
