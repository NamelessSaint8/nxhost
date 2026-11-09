// Distinct NVN descriptors over one allocation observe the same GPU writes.
#include "../nvn/nvn_mtl.m"
void *front_metal_layer(void) { return NULL; }
module_t *module_of(const void *p) { (void)p; return NULL; }
module_t *g_mod; int g_nmod;
void svc_thread_dump(void) {}
uint64_t now_ns(void) { return bp_now(); }
static int checks, failed;
#define CHECK(c, label) do { checks++; if (!(c)) { failed++; fprintf(stderr, "FAIL: %s\n", label); } } while (0)

static tex_t texture_sized(pool_t *pool, uint64_t serial, int format, int flags, int64_t off, unsigned size) {
    tex_t t = {.magic=MAGIC('T','E','X',0), .serial=serial, .pool=pool, .off=off, .mem=pool->mem+off};
    t.d = (nvn_texdesc){.target=NVN_TEXTURE_TARGET_2D, .format=format, .flags=flags,
                       .width=size, .height=size, .depth=1, .levels=1, .samples=1};
    nvn_tex_layout(&t.d, &t.L); mtl_tex_init(&t); return t;
}
static tex_t texture(pool_t *pool, uint64_t serial, int format, int flags, int64_t off) {
    return texture_sized(pool,serial,format,flags,off,8);
}
static id<MTLTexture> root(id<MTLTexture> t) { while (t.parentTexture) t=t.parentTexture; return t; }
static void clear_half(id<MTLTexture> t) {
    mtl_sub_commit(); mtl_drain();
    id<MTLCommandBuffer> cb=q_cb();
    MTLRenderPassDescriptor *rp=[MTLRenderPassDescriptor renderPassDescriptor];
    rp.colorAttachments[0].texture=t; rp.colorAttachments[0].loadAction=MTLLoadActionClear;
    rp.colorAttachments[0].storeAction=MTLStoreActionStore;
    rp.colorAttachments[0].clearColor=MTLClearColorMake(.5,.25,.75,1);
    id<MTLRenderCommandEncoder> e=[cb renderCommandEncoderWithDescriptor:rp]; [e endEncoding];
    [cb commit]; [cb waitUntilCompleted]; CHECK(cb.status==MTLCommandBufferStatusCompleted,"alias writer completes");
    mtl_sub_begin();
}
static void sample(id<MTLTexture> t, int srgb) {
    static id<MTLComputePipelineState> ps;
    if (!ps) {
        NSError *error=nil;
        id<MTLLibrary> lib=[g_dev newLibraryWithSource:@"#include <metal_stdlib>\nusing namespace metal;\n"
            "kernel void sample_alias(texture2d<float,access::read> t [[texture(0)]], device float4 *o [[buffer(0)]]) { o[0]=t.read(uint2(0,0)); }\n" options:nil error:&error];
        ps=[g_dev newComputePipelineStateWithFunction:[lib newFunctionWithName:@"sample_alias"] error:&error];
        CHECK(ps!=nil,"alias sampler compiles");
    }
    if (!ps) return;
    mtl_sub_commit(); mtl_drain();
    id<MTLBuffer> out=[g_dev newBufferWithLength:16 options:MTLResourceStorageModeShared];
    id<MTLCommandBuffer> cb=q_cb(); id<MTLComputeCommandEncoder> e=[cb computeCommandEncoder];
    [e setComputePipelineState:ps]; [e setTexture:t atIndex:0]; [e setBuffer:out offset:0 atIndex:0];
    [e dispatchThreadgroups:MTLSizeMake(1,1,1) threadsPerThreadgroup:MTLSizeMake(1,1,1)]; [e endEncoding];
    [cb commit]; [cb waitUntilCompleted];
    CHECK(cb.status==MTLCommandBufferStatusCompleted,"alias reader completes");
    float *v=out.contents;
    CHECK(fabsf(v[0]-(srgb?.21586f:.50196f))<.006f && fabsf(v[3]-1)<.001f,
          "reader sees GPU-written colour with its own transfer function");
    mtl_sub_begin();
}
static void pair(pool_t *pool, uint64_t serial, int flags, int reader_first, int64_t off) {
    tex_t a=texture(pool,serial,NVN_FORMAT_RGBA8,NVN_TEXTURE_FLAGS_COMPRESSIBLE,off);
    tex_t b=texture(pool,serial+1,NVN_FORMAT_RGBA8_SRGB,flags,off);
    id<MTLTexture> reader=nil, writer=nil;
    if (reader_first) reader=tex_mtl(&b);
    writer=tex_mtl(&a); if (!reader) reader=tex_mtl(&b);
    CHECK(writer.pixelFormat==MTLPixelFormatRGBA8Unorm,"writer retains linear format");
    CHECK(reader.pixelFormat==MTLPixelFormatRGBA8Unorm_sRGB,"reader retains sRGB format");
    CHECK(root(writer)==root(reader),"linear and sRGB descriptors share one allocation");
    clear_half(writer); sample(reader,1);
    mtl_reg_tex((int)serial,&b,NULL);
    os_unfair_lock_lock(&g_rmu); id<MTLTexture> bound=tex_by_id((int)serial); os_unfair_lock_unlock(&g_rmu);
    CHECK(bound.pixelFormat==MTLPixelFormatRGBA8Unorm_sRGB,"descriptor-pool sampling keeps sRGB decoding");
    sample(bound,1);
    id<MTLTexture> asked=reader_first?writer:reader;
    id<MTLTexture> upgraded=tex_upgrade(reader_first?&a:&b,asked,MTLTextureUsagePixelFormatView,MTLPixelFormatR32Uint);
    CHECK(root(upgraded)!=root(writer),"usage upgrade replaces the allocation");
    CHECK(upgraded.pixelFormat==asked.pixelFormat,"upgrading through a format view keeps its interpretation");
    reader=tex_mtl(&b); writer=tex_mtl(&a);
    CHECK(root(reader)==root(writer),"format aliases follow an allocation upgrade");
    sample(reader,1);
    mtl_tex_release(&b); reader=tex_mtl(&b); sample(reader,1);
    CHECK([g_res_objects containsObject:root(writer)],"finalizing a descriptor keeps shared storage resident");
    mtl_tex_release(&a);
}
static void resolution_family(pool_t *pool) {
    tex_t t[3];
    for (int i=0;i<3;i++) t[i]=texture_sized(pool,65040+i,i==2?NVN_FORMAT_RGBA8:NVN_FORMAT_RGBA8_SRGB,
        NVN_TEXTURE_FLAGS_COMPRESSIBLE|NVN_TEXTURE_FLAGS_IMAGE,393216,16u<<(i*2));
    id<MTLTexture> first=tex_mtl(&t[0]);
    CHECK(first.heap!=nil,"sRGB resolution family uses shared physical storage");
    for (int i=0;i<3;i++) {
        id<MTLTexture> v=tex_mtl(&t[i]);
        CHECK(v.heap==first.heap,"linear and sRGB resolution variants reuse the same heap");
        clear_half(v); sample(v,0);
    }
    for (int i=0;i<3;i++) mtl_tex_release(&t[i]);
}
int main(void) { @autoreleasepool {
    mtl_init(); mtl_sub_begin(); void *mem=NULL; posix_memalign(&mem,16384,1<<20); memset(mem,0,1<<20);
    pool_t pool={.magic=MAGIC('P','O','O','L'),.mem=mem,.size=1<<20,
        .flags=NVN_MEMORY_POOL_FLAGS_CPU_NO_ACCESS|NVN_MEMORY_POOL_FLAGS_GPU_CACHED|NVN_MEMORY_POOL_FLAGS_COMPRESSIBLE};
    pair(&pool,65000,NVN_TEXTURE_FLAGS_COMPRESSIBLE,0,0);
    pair(&pool,65010,NVN_TEXTURE_FLAGS_COMPRESSIBLE,1,65536);
    pair(&pool,65020,0,0,131072);
    tex_t a=texture(&pool,65030,NVN_FORMAT_RGBA8,NVN_TEXTURE_FLAGS_COMPRESSIBLE,196608);
    tex_t b=texture(&pool,65031,NVN_FORMAT_RGBA8,0,196608);
    CHECK(tex_mtl(&a)==tex_mtl(&b),"compression eligibility does not split identical texel storage");
    clear_half(tex_mtl(&a)); sample(tex_mtl(&b),0);
    tex_t c=texture(&pool,65032,NVN_FORMAT_RGBA8_SRGB,0,262144);
    CHECK(root(tex_mtl(&c))!=root(tex_mtl(&a)),"different offsets retain separate allocations");
    resolution_family(&pool);
    mtl_tex_release(&a); mtl_tex_release(&b); mtl_tex_release(&c); mtl_alias_drop_pool(&pool);
    mtl_sub_commit(); mtl_drain(); mtl_sub_begin(); mtl_sub_commit(); mtl_drain();
    printf("texture storage aliases: %d checks, %d failed\n",checks,failed); return failed!=0;
} }
