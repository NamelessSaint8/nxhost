// Writable sparse images retain GPU pixels across map changes and physical-page aliases. Unmapped hardware tiles discard writes and read zero.
#define nvn_game_fps nvn_game_fps_mtl_default
#include "../nvn/nvn_mtl.m"
#undef nvn_game_fps
#define g_ft g_ft_hle
#include "../nvn/hle_nvn.c"
#undef g_ft
uint64_t g_t0_ns;
void *front_metal_layer(void) { return NULL; }
module_t *module_of(const void *p) { (void)p; return NULL; }
module_t *g_mod; int g_nmod;
void svc_thread_dump(void) {}
uint64_t now_ns(void) { return bp_now(); }
static int checks,failed;
#define CHECK(c,label) do{checks++;if(!(c)){failed++;fprintf(stderr,"FAIL: %s\n",label);}}while(0)
static void finish(void){mtl_sub_commit();mtl_drain();CHECK(!mtl_last_commit_error(),"submission completes");mtl_sub_begin();}
static void clear_image(id<MTLTexture> t,double red,unsigned level){
    MTL4RenderPassDescriptor *p=[MTL4RenderPassDescriptor new];p.colorAttachments[0].texture=t;p.colorAttachments[0].level=level;
    p.colorAttachments[0].loadAction=MTLLoadActionClear;p.colorAttachments[0].storeAction=MTLStoreActionStore;p.colorAttachments[0].clearColor=MTLClearColorMake(red,0,0,1);
    enc_r_end(enc_r_begin(p));
}
static void pixels(id<MTLTexture> t,const uint32_t points[][3],const float *expected,unsigned n){
    NSError *error=nil;id<MTLLibrary> lib=[g_dev newLibraryWithSource:@"#include <metal_stdlib>\nusing namespace metal;\nkernel void read_image(texture2d<float,access::read> t[[texture(0)]],device const uint4*p[[buffer(0)]],device float4*out[[buffer(1)]],uint i[[thread_position_in_grid]]){out[i]=t.read(p[i].xy,p[i].z);}" options:nil error:&error];
    id<MTLComputePipelineState> ps=[g_dev newComputePipelineStateWithFunction:[lib newFunctionWithName:@"read_image"] error:&error];CHECK(ps!=nil,"GPU reader compiles");
    uint32_t packed[n][4];for(unsigned i=0;i<n;i++)memcpy(packed[i],points[i],12);
    id<MTLBuffer> input=[g_dev newBufferWithBytes:packed length:n*16 options:MTLResourceStorageModeShared],output=[g_dev newBufferWithLength:n*16 options:MTLResourceStorageModeShared];res_add(input);res_add(output);
    MTL4ArgumentTableDescriptor *d=[MTL4ArgumentTableDescriptor new];d.maxBufferBindCount=2;d.maxTextureBindCount=1;
    id<MTL4ArgumentTable> args=rec_table([g_dev newArgumentTableWithDescriptor:d error:&error]);[args setTexture:t.gpuResourceID atIndex:0];[args setAddress:input.gpuAddress atIndex:0];[args setAddress:output.gpuAddress atIndex:1];
    if(g_blit){enc_b_end(g_blit);g_blit=nil;}
    id<MTL4ComputeCommandEncoder> e=enc_c_begin(nil);[e setArgumentTable:args];enc_c_pso(e,ps);enc_c_dispatch(e,MTLSizeMake(n,1,1),MTLSizeMake(1,1,1));enc_c_end(e);finish();
    for(unsigned i=0;i<n;i++){float got=((float *)output.contents)[4*i];CHECK(fabsf(got-expected[i])<.006f,"mapped GPU pixels survive; holes stay zero");if(fabsf(got-expected[i])>=.006f)fprintf(stderr,"point %u: %g expected %g\n",i,got,expected[i]);}
    res_remove(input);res_remove(output);
}
static void virtual_pool(pool_t *p){pool_builder_t b={.size=MAX(DM_GAME_APP_POOL,16u<<20)+65536,.flags=0x201};CHECK(h_nvnMemoryPoolInitialize((NVNmemoryPool *)p,(NVNmemoryPoolBuilder *)&b),"virtual image pool initializes");}
static tex_t image(pool_t *p,uint64_t serial,int format){tex_t t={.magic=MAGIC('T','E','X',0),.serial=serial,.pool=p,.mem=p->mem};t.d=(nvn_texdesc){.target=NVN_TEXTURE_TARGET_2D,.format=format,.flags=NVN_TEXTURE_FLAGS_SPARSE|NVN_TEXTURE_FLAGS_COMPRESSIBLE,.width=1024,.height=1024,.depth=1,.levels=3,.samples=1};nvn_tex_layout(&t.d,&t.L);mtl_tex_init(&t);return t;}
static void map(pool_t *v,pool_t *p,uint64_t physical,uint64_t virtual_off,uint64_t size){map_req r={.phys=(NVNmemoryPool *)p,.poff=physical,.voff=virtual_off,.size=size};CHECK(h_nvnMemoryPoolMapVirtual((NVNmemoryPool *)v,1,(NVNmappingRequest *)&r),"image page mapping changes");}
static void run(int format){
    const size_t size=4*65536;void *mem=mmap(NULL,size,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANON,-1,0);pool_t physical,first,second;
    pool_builder_t pb={.mem=mem,.size=size,.flags=0x21};CHECK(h_nvnMemoryPoolInitialize((NVNmemoryPool *)&physical,(NVNmemoryPoolBuilder *)&pb),"GPU physical pool initializes");virtual_pool(&first);map(&first,&physical,0,0,65536);
    tex_t t=image(&first,91000+(unsigned)format*100,format);uint32_t tw,th,td;nvn_tex_sparse_tiles(&t.d,&tw,&th,&td);unsigned test_level=1;
    id<MTLTexture> original=tex_mtl(&t);CHECK(original.isSparse && (original.usage&MTLTextureUsageRenderTarget),"writable image uses native sparse backing");
    CHECK(((NvSparseHeap *)objc_getAssociatedObject(original,&g_sparse_heap_owner_key))->pages.count==1,"image backs one mapped tile");
    mtl_reg_tex(711,&t,NULL);CHECK(tex_by_id(711)==original,"sampled descriptor names original metadata");
    clear_image(original,1,0); // deliberately still encoded when the mapping and descriptor change
    map(&first,&physical,65536,65536,65536);id<MTLTexture> current=(__bridge id)tex_fast(711);
    CHECK(current!=original && current.isSparse,"cached descriptor follows a new sparse mapping version");
    const uint32_t q[][3]={{0,0,0},{tw,0,0},{2*tw,0,0},{0,0,test_level}};pixels(current,q,(float[]){1,0,0,0},4);
    tex_t alias=t;alias.serial++;mtl_tex_init(&alias);CHECK(tex_mtl(&alias)==current,"all serial aliases follow current metadata");
    virtual_pool(&second);map(&second,&physical,0,65536,65536);tex_t other=image(&second,t.serial+2,format);id<MTLTexture> shared=tex_mtl(&other);
    const uint32_t other_q[][3]={{tw,0,0},{0,0,0}};pixels(shared,other_q,(float[]){1,0},2);
    clear_image(shared,.25,0);pixels(current,q,(float[]){.25,0,0,0},4);
    map(&first,&physical,2*65536,0,65536);current=tex_mtl(&t);pixels(current,q,(float[]){0,0,0,0},4);pixels(shared,other_q,(float[]){.25,0},2);
    map(&first,&physical,0,0,65536);current=tex_mtl(&t);pixels(current,q,(float[]){.25,0,0,0},4);
    uint64_t leveloff=nvn_tex_level_offset(&t.d,test_level);map(&first,&physical,3*65536,leveloff,65536);current=tex_mtl(&t);clear_image(current,.75,test_level);finish();
    pixels(current,q,(float[]){.25,0,0,.75},4);
    tex_t short_mips=t;short_mips.serial+=10;short_mips.d.levels=2;nvn_tex_layout(&short_mips.d,&short_mips.L);mtl_tex_init(&short_mips);
    id<MTLTexture> short_texture=tex_mtl(&short_mips);id<MTLTexture> writable=tex_upgrade(&short_mips,short_texture,MTLTextureUsageShaderWrite,short_texture.pixelFormat);
    CHECK(writable.isSparse && (writable.usage&MTLTextureUsageShaderWrite),"non-tail image usage upgrade retains native sparse backing");
    NSError *error=nil;id<MTLLibrary> lib=[g_dev newLibraryWithSource:@"#include <metal_stdlib>\nusing namespace metal;\nkernel void put(texture2d<float,access::write> t[[texture(0)]]){t.write(float4(1),uint2(2));}" options:nil error:&error];
    id<MTLComputePipelineState> ps=[g_dev newComputePipelineStateWithFunction:[lib newFunctionWithName:@"put"] error:&error];CHECK(ps!=nil,"sparse image writer compiles");
    MTL4ArgumentTableDescriptor *ad=[MTL4ArgumentTableDescriptor new];ad.maxTextureBindCount=1;id<MTL4ArgumentTable> args=rec_table([g_dev newArgumentTableWithDescriptor:ad error:&error]);[args setTexture:writable.gpuResourceID atIndex:0];
    id<MTL4ComputeCommandEncoder> ce=enc_c_begin(nil);[ce setArgumentTable:args];enc_c_pso(ce,ps);enc_c_dispatch(ce,MTLSizeMake(1,1,1),MTLSizeMake(1,1,1));enc_c_end(ce);
    const uint32_t written[][3]={{2,2,0}};pixels(writable,written,(float[]){1},1);
    const uint32_t alias_written[][3]={{tw+2,2,0}};pixels(shared,alias_written,(float[]){1},1);mtl_tex_release(&short_mips);
    id<MTLTexture> upgraded=tex_upgrade(&t,current,MTLTextureUsageShaderWrite,current.pixelFormat);CHECK(upgraded.usage&MTLTextureUsageShaderWrite,"image usage upgrade preserves writable storage");pixels(upgraded,q,(float[]){.25,0,0,.75},4);
    map(&first,&physical,2*65536,2*65536,4096);id<MTLTexture> dense=tex_mtl(&t);CHECK(!dense.isSparse,"partial hardware tile takes dense compatibility storage");pixels(dense,q,(float[]){.25,0,0,.75},4);
    mtl_tex_release(&t);mtl_tex_release(&alias);mtl_tex_release(&other);h_nvnMemoryPoolFinalize((NVNmemoryPool *)&first);h_nvnMemoryPoolFinalize((NVNmemoryPool *)&second);h_nvnMemoryPoolFinalize((NVNmemoryPool *)&physical);finish();finish();munmap(mem,size);
}
static void reused_physical_address(void){
    const size_t size=65536;void *mem=mmap(NULL,size,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANON,-1,0);pool_t physical,virt;
    pool_builder_t pb={.mem=mem,.size=size,.flags=0x21};h_nvnMemoryPoolInitialize((NVNmemoryPool *)&physical,(NVNmemoryPoolBuilder *)&pb);virtual_pool(&virt);map(&virt,&physical,0,0,size);
    tex_t first=image(&virt,95000,NVN_FORMAT_R8);id<MTLTexture> old=tex_mtl(&first);clear_image(old,1,0);finish();
    NvSparseHeap *retained=objc_getAssociatedObject(old,&g_sparse_heap_owner_key);
    mtl_tex_release(&first);h_nvnMemoryPoolFinalize((NVNmemoryPool *)&virt);h_nvnMemoryPoolFinalize((NVNmemoryPool *)&physical);finish();finish();
    CHECK(mmap(mem,size,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANON|MAP_FIXED,-1,0)==mem,"a fresh allocation reuses the physical CPU address");
    h_nvnMemoryPoolInitialize((NVNmemoryPool *)&physical,(NVNmemoryPoolBuilder *)&pb);virtual_pool(&virt);map(&virt,&physical,0,0,size);
    tex_t next=image(&virt,95001,NVN_FORMAT_R8);id<MTLTexture> fresh=tex_mtl(&next);const uint32_t q[][3]={{0,0,0}};pixels(fresh,q,(float[]){0},1);
    NvSparseHeap *new_owner=objc_getAssociatedObject(fresh,&g_sparse_heap_owner_key);CHECK(retained->pages[0]!=new_owner->pages[0],"a new physical pool incarnation never inherits stale GPU pixels");
    MTLTextureDescriptor *descriptor=tex_desc(&next,0);id<MTLTexture> probe=sparse_upload(&next,descriptor,NULL,fresh,1);CHECK(probe!=nil && descriptor.placementSparsePageSize==0,"sparse creation leaves the dense fallback descriptor unchanged");defer_obj_release(probe);
    mtl_tex_release(&next);h_nvnMemoryPoolFinalize((NVNmemoryPool *)&virt);h_nvnMemoryPoolFinalize((NVNmemoryPool *)&physical);finish();finish();munmap(mem,size);
}
static void sampled_target(void){
    size_t size=2*65536;uint8_t *mem=mmap(NULL,size,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANON,-1,0);
    for(size_t i=0;i<size;i+=4){mem[i]=i<65536?64:128;mem[i+3]=255;}
    pool_t physical,virt;pool_builder_t pb={.mem=mem,.size=size,.flags=0x21};CHECK(h_nvnMemoryPoolInitialize((NVNmemoryPool*)&physical,(NVNmemoryPoolBuilder*)&pb),"sampled target physical pool initializes");virtual_pool(&virt);map(&virt,&physical,0,0,65536);
    tex_t t=image(&virt,99700,NVN_FORMAT_RGBA8);t.d.flags=NVN_TEXTURE_FLAGS_SPARSE;nvn_tex_layout(&t.d,&t.L);
    id<MTLTexture> first=tex_mtl(&t);CHECK(first.isSparse && (first.usage&MTLTextureUsageRenderTarget),"GPU-only sampled storage is writable sparse from first use");
    CHECK(mtl_tex_gpu_owned(t.serial),"a packaged sparse GPU target has GPU ownership");
    uint32_t tw,th,td;nvn_tex_sparse_tiles(&t.d,&tw,&th,&td);const uint32_t q[][3]={{0,0,0},{tw,0,0}};pixels(first,q,(float[]){64/255.f,0},2);
    clear_image(first,.75,0);pixels(first,q,(float[]){.75,0},2);
    uint8_t out[4]={0};NVNcopyRegion r={0,0,0,1,1,1};mtl_read_texels(&t,0,0,&r,out,4,4);CHECK(out[0]==191,"ReadTexels returns GPU content rather than the original CPU mirror");
    mtl_reg_tex(777,&t,NULL);tex_by_id(777);map(&virt,&physical,65536,65536,65536);id<MTLTexture> current=(__bridge id)tex_fast(777);
    CHECK(current.isSparse && current!=first,"cached packaged descriptor refreshes sparse mappings");pixels(current,q,(float[]){.75,128/255.f},2);
    tex_t alias=t;alias.serial++;mtl_tex_init(&alias);id<MTLTexture> other=tex_mtl(&alias);pixels(other,q,(float[]){.75,128/255.f},2);
    clear_image(other,.25,0);pixels(tex_mtl(&t),q,(float[]){.25,.25},2);
    map(&virt,&physical,0,2*65536,4096);id<MTLTexture> dense=tex_mtl(&t);
    CHECK(!dense.isSparse && mtl_tex_gpu_owned(t.serial),"a partial-tile fallback retains packaged GPU ownership");
    pixels(dense,q,(float[]){.25,.25},2);CHECK(tex_mtl(&t)==dense,"resolving the dense fallback does not restore stale CPU bytes");
    mtl_tex_release(&alias);mtl_tex_release(&t);h_nvnMemoryPoolFinalize((NVNmemoryPool*)&virt);h_nvnMemoryPoolFinalize((NVNmemoryPool*)&physical);finish();finish();munmap(mem,size);
}
int main(void){@autoreleasepool{setenv("DM_NVN_SPARSE_GPU_SAMPLED","1",1);nvn_gob_switch2=1;mtl_init();mtl_sub_begin();run(NVN_FORMAT_R8);run(NVN_FORMAT_R16);run(NVN_FORMAT_RG16);reused_physical_address();sampled_target();mtl_sub_commit();mtl_drain();printf("sparse writable images: %d checks, %d failed\n",checks,failed);return failed!=0;}}
