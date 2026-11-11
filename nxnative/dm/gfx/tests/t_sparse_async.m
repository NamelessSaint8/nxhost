// An event-gated classic queue proves upload/replay overlap without relying on a fast GPU or a wall-time threshold.
#define main sparse_content_main
#include "t_sparse_upload.m"
#undef main
static size_t pending(void){pthread_mutex_lock(&g_sparse_transfer_mu);size_t n=g_sparse_transfer_bytes;pthread_mutex_unlock(&g_sparse_transfer_mu);return n;}
static _Atomic int budget_done;
static void *budget_worker(void *arg){size_t n=(size_t)(uintptr_t)arg;sparse_transfer_begin(n);atomic_store(&budget_done,1);sparse_transfer_end(n);return NULL;}
static void budget_blocked(size_t reserve){
    sparse_transfer_begin(reserve);atomic_store(&budget_done,0);pthread_t thread;
    int rc=pthread_create(&thread,NULL,budget_worker,(void *)(uintptr_t)65536);CHECK(!rc,"budget waiter starts");if(rc){sparse_transfer_end(reserve);return;}
    pthread_mutex_lock(&g_sparse_transfer_mu);while(!g_sparse_transfer_waiters)pthread_cond_wait(&g_sparse_transfer_cv,&g_sparse_transfer_mu);
    CHECK(!atomic_load(&budget_done),"backpressure blocks another transfer at the budget boundary");pthread_mutex_unlock(&g_sparse_transfer_mu);
    sparse_transfer_end(reserve);pthread_join(thread,NULL);CHECK(atomic_load(&budget_done),"releasing completed transfer bytes wakes the waiter");
}
int main(int argc,char **argv){@autoreleasepool{
    int lost=argc>1 && !strcmp(argv[1],"lost");if(lost)setenv("DM_TEST_SPARSE_LOST","1",1);
    setenv("DM_NVN_NATIVE_SPARSE","1",1);setenv("DM_NVN_SPARSE_ASYNC","1",1);mtl_init();mtl_sub_begin();nvn_gob_switch2=1;
    const size_t bytes=2*65536;uint8_t *mem=mmap(NULL,bytes,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANON,-1,0);
    for(size_t i=0;i<bytes;i+=4){mem[i]=255;mem[i+1]=mem[i+2]=0;mem[i+3]=255;}
    pool_t physical,virtual;pool_builder_t b={.mem=mem,.size=bytes,.flags=0x24};
    CHECK(h_nvnMemoryPoolInitialize((NVNmemoryPool *)&physical,(NVNmemoryPoolBuilder *)&b),"async physical pool initializes");
    b=(pool_builder_t){.size=DM_GAME_APP_POOL+65536,.flags=0x200};CHECK(h_nvnMemoryPoolInitialize((NVNmemoryPool *)&virtual,(NVNmemoryPoolBuilder *)&b),"async virtual pool initializes");
    map_req mapping={.phys=(NVNmemoryPool *)&physical,.size=bytes};CHECK(h_nvnMemoryPoolMapVirtual((NVNmemoryPool *)&virtual,1,(NVNmappingRequest *)&mapping),"two async source tiles map");
    tex_t t={.magic=MAGIC('T','E','X',0),.serial=98001,.pool=&virtual,.mem=virtual.mem,.has_layout=1};
    t.d=(nvn_texdesc){.target=NVN_TEXTURE_TARGET_2D_ARRAY,.format=NVN_FORMAT_RGBA8,.flags=NVN_TEXTURE_FLAGS_SPARSE,.width=1024,.height=1024,.depth=1,.levels=1,.samples=1};nvn_tex_layout(&t.d,&t.L);mtl_tex_init(&t);mtl_reg_tex(981,&t,NULL);
    id<MTLSharedEvent> gate=[g_dev newSharedEvent];id<MTLCommandBuffer> blocker=[g_q commandBuffer];[blocker encodeWaitForEvent:gate value:1];queue3_commit(blocker);
    dispatch_semaphore_t returned=dispatch_semaphore_create(0);dispatch_group_t rescue=dispatch_group_create();
    dispatch_group_async(rescue,dispatch_get_global_queue(QOS_CLASS_USER_INITIATED,0),^{if(dispatch_semaphore_wait(returned,dispatch_time(DISPATCH_TIME_NOW,3*NSEC_PER_SEC)))gate.signaledValue=1;});
    id<MTLTexture> first=tex_by_id(981);CHECK(first.isSparse && gate.signaledValue==0,"upload returns while the GPU upload queue is held");
    CHECK(pending()==bytes,"only the submitted staging bytes are reserved");
    uint64_t unchanged_stamp;id<MTLTexture> unchanged=pkg_upload(&t,&unchanged_stamp,first,0);
    CHECK(unchanged==first && gate.signaledValue==0,"an unchanged pending version keeps its original completion dependency without waiting");
    CHECK(pending()==bytes,"an unchanged pending version releases its unused transfer reservation");
    int share=getenv("DM_NVN_SPARSE_RO_SHARE") && atoi(getenv("DM_NVN_SPARSE_RO_SHARE"));id<MTLTexture> early_alias=nil;
    if(share){tex_t alias=t;alias.serial++;uint64_t stamp;early_alias=pkg_upload(&alias,&stamp,nil,0);
        NvSparseHeap *a=objc_getAssociatedObject(first,&g_sparse_heap_owner_key),*b=objc_getAssociatedObject(early_alias,&g_sparse_heap_owner_key);
        CHECK(a->pages[0]!=b->pages[0] && a->pages[1]!=b->pages[1],"a different descriptor never shares uncompleted immutable uploads");
    }
    dm_guest_write_prepare(mem,4096);for(size_t i=0;i<4096;i+=4){mem[i]=0;mem[i+1]=255;}
    id<MTLTexture> second=tex_by_id(981);CHECK(second!=first && gate.signaledValue==0,"a second texture version is prepared before the first upload completes");
    CHECK(pending()==(3u+2u*share)*65536,"in-flight versions account for only their changed tiles");
    dispatch_semaphore_signal(returned);gate.signaledValue=1;dispatch_group_wait(rescue,DISPATCH_TIME_FOREVER);
    uint32_t tw,th,td;nvn_tex_sparse_tiles(&t.d,&tw,&th,&td);const uint32_t points[][4]={{0,0,0,0},{tw,0,0,0},{0,th,0,0}};
    const float old_pixels[][4]={{1,0,0,1},{1,0,0,1},{0,0,0,0}},new_pixels[][4]={{0,1,0,1},{1,0,0,1},{0,0,0,0}};
    // The production cache retired the old metadata on this fence. Rebinding that deliberately retained snapshot needs residency again after retirement.
    finish();retired_pixels(first,points,old_pixels,3);pixels(second,points,new_pixels,3);CHECK(!pending(),"finish drains all asynchronous upload callbacks");
    if(lost){uint64_t before=g_sparse_backed,stamp=nvn_dirty_now();id<MTLTexture> retry=tex_by_id(981);
        CHECK(retry!=second,"a dropped upload invalidates cached descriptor versions");CHECK(g_sparse_backed==before+bytes,"retry rebuilds every page rather than sharing possibly unwritten tiles");
        CHECK(nvn_dirty_now()==stamp,"recovery needs no new guest write");pixels(retry,points,new_pixels,3);defer_obj_release(retry);
    }
    if(share && !lost){tex_t alias=t;alias.serial+=2;uint64_t stamp,before=g_sparse_backed;id<MTLTexture> late_alias=pkg_upload(&alias,&stamp,nil,0);
        CHECK(g_sparse_backed==before,"completed immutable pages share across async descriptors without another upload");
        pixels(late_alias,points,new_pixels,3);defer_obj_release(late_alias);
    }
    sparse_upload_wait();budget_blocked(SPARSE_TRANSFER_BYTES);budget_blocked(SPARSE_TRANSFER_BYTES+65536);CHECK(!pending(),"bounded and oversized transfers release their budgets");
    if(early_alias)defer_obj_release(early_alias);defer_obj_release(first);defer_obj_release(second);first=second=nil;mtl_tex_release(&t);
    h_nvnMemoryPoolFinalize((NVNmemoryPool *)&virtual);h_nvnMemoryPoolFinalize((NVNmemoryPool *)&physical);finish();finish();munmap(mem,bytes);
    mtl_sub_commit();mtl_drain();printf("sparse async uploads%s: %d checks, %d failed\n",lost?" with dropped-batch recovery":"",checks,failed);return failed!=0;
}}
