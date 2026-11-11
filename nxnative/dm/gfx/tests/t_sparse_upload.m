// Sparse uploads preserve mapped texels, zero reads in holes, mip tails and array slices without dense backing. Reads go through Metal 4's resource IDs.
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
static int checks, failed;
static int test_upgrade, test_copy, test_gpu_copy, test_share, test_ro;
#define CHECK(c, label) do { checks++; if (!(c)) { failed++; fprintf(stderr,"FAIL: %s\n",label); } } while (0)
static void finish(void) { mtl_sub_commit(); mtl_drain(); CHECK(!mtl_last_commit_error(),"sparse GPU submission completes"); mtl_sub_begin(); }
static void pixels_mode(id<MTLTexture> t, const uint32_t (*points)[4], const float (*want)[4], unsigned n,int mode) {
    NSError *error=nil;
    id<MTLLibrary> lib=[g_dev newLibraryWithSource:@"#include <metal_stdlib>\nusing namespace metal;\n"
        "kernel void read_sparse(texture2d_array<float,access::read> t [[texture(0)]], device const uint4 *p [[buffer(0)]], device float4 *o [[buffer(1)]], uint i [[thread_position_in_grid]]) { uint4 q=p[i]; o[i]=t.read(q.xy,q.z,q.w); }\n"
        "float4 sample_tex(texture2d_array<float> t,uint4 q){constexpr sampler s(coord::normalized,address::clamp_to_edge,filter::nearest,mip_filter::linear);return t.sample(s,(float2(q.xy)+.5f)/float2(t.get_width(min(q.w,t.get_num_mip_levels()-1)),t.get_height(min(q.w,t.get_num_mip_levels()-1))),q.z,level(q.w));}\n"
        "kernel void sample_sparse(texture2d_array<float> t [[texture(0)]], device const uint4 *p [[buffer(0)]], device float4 *o [[buffer(1)]], uint i [[thread_position_in_grid]]){o[i]=sample_tex(t,p[i]);}\n"
        "struct A{texture2d_array<float> t[[id(0)]];};kernel void indirect_sparse(constant A&a[[buffer(2)]], device const uint4 *p[[buffer(0)]],device float4 *o[[buffer(1)]],uint i[[thread_position_in_grid]]){o[i]=sample_tex(a.t,p[i]);}\n" options:nil error:&error];
    NSString *names[] = {@"read_sparse",@"sample_sparse",@"indirect_sparse"};
    if(!lib)fprintf(stderr,"%s\n",error.localizedDescription.UTF8String);
    id<MTLComputePipelineState> ps=[g_dev newComputePipelineStateWithFunction:[lib newFunctionWithName:names[mode]] error:&error];
    CHECK(ps!=nil,"sparse Metal 4 reader compiles"); if(!ps)return;
    id<MTLBuffer> p=[g_dev newBufferWithBytes:points length:n*16 options:MTLResourceStorageModeShared];
    id<MTLBuffer> o=[g_dev newBufferWithLength:n*16 options:MTLResourceStorageModeShared]; res_add(p);res_add(o);
    uint64_t rid=t.gpuResourceID._impl;id<MTLBuffer> handles=[g_dev newBufferWithBytes:&rid length:sizeof rid options:MTLResourceStorageModeShared];res_add(handles);
    MTL4ArgumentTableDescriptor *d=[MTL4ArgumentTableDescriptor new];d.maxBufferBindCount=3;d.maxTextureBindCount=1;
    id<MTL4ArgumentTable> a=rec_table([g_dev newArgumentTableWithDescriptor:d error:&error]);
    [a setTexture:t.gpuResourceID atIndex:0];[a setAddress:p.gpuAddress atIndex:0];[a setAddress:o.gpuAddress atIndex:1];
    [a setAddress:handles.gpuAddress atIndex:2];
    id<MTL4ComputeCommandEncoder> e=enc_c_begin(nil);[e setArgumentTable:a];enc_c_pso(e,ps);
    enc_c_dispatch(e,MTLSizeMake(n,1,1),MTLSizeMake(1,1,1));enc_c_end(e);finish();
    float *v=o.contents;
    for(unsigned i=0;i<n;i++){int ok=1;for(int c=0;c<4;c++)ok &= fabsf(v[i*4+c]-want[i][c])<.006f;CHECK(ok,"mapped pixels, holes and mip tails have the expected colour");if(!ok)fprintf(stderr,"pixel %u: %g %g %g %g\n",i,v[i*4],v[i*4+1],v[i*4+2],v[i*4+3]);}
    res_remove(p);res_remove(o);res_remove(handles);
}
static void fragment_pixels(id<MTLTexture> t,const uint32_t (*points)[4],const float (*want)[4],unsigned n) {
    NSError *error=nil;
    id<MTLLibrary> lib=[g_dev newLibraryWithSource:@"#include <metal_stdlib>\nusing namespace metal;\n"
        "vertex float4 vs(uint i[[vertex_id]]){float2 p[3]={float2(-1,-1),float2(3,-1),float2(-1,3)};return float4(p[i],0,1);}\n"
        "struct A{texture2d_array<float> t[[id(0)]];device const uint4*p[[id(1)]];sampler s[[id(2)]];};\n"
        "fragment float4 fs(float4 pos[[position]],constant A&a[[buffer(0)]]){uint4 q=a.p[uint(pos.x)];return a.t.sample(a.s,(float2(q.xy)+.5f)/float2(a.t.get_width(min(q.w,a.t.get_num_mip_levels()-1)),a.t.get_height(min(q.w,a.t.get_num_mip_levels()-1))),q.z,level(q.w));}\n" options:nil error:&error];
    MTLRenderPipelineDescriptor *pd=[MTLRenderPipelineDescriptor new];pd.vertexFunction=[lib newFunctionWithName:@"vs"];pd.fragmentFunction=[lib newFunctionWithName:@"fs"];pd.colorAttachments[0].pixelFormat=MTLPixelFormatRGBA32Float;
    id<MTLRenderPipelineState> ps=[g_dev newRenderPipelineStateWithDescriptor:pd error:&error];CHECK(ps!=nil,"sparse fragment sampler compiles");if(!ps)return;
    id<MTLBuffer> p=[g_dev newBufferWithBytes:points length:n*16 options:MTLResourceStorageModeShared];
    MTLSamplerDescriptor *sampler_desc=[MTLSamplerDescriptor new];sampler_desc.minFilter=MTLSamplerMinMagFilterLinear;sampler_desc.magFilter=MTLSamplerMinMagFilterLinear;sampler_desc.mipFilter=MTLSamplerMipFilterLinear;sampler_desc.sAddressMode=sampler_desc.tAddressMode=MTLSamplerAddressModeClampToEdge;sampler_desc.maxAnisotropy=16;sampler_desc.lodMaxClamp=1000;sampler_desc.supportArgumentBuffers=YES;
    id<MTLSamplerState> sampler=[g_dev newSamplerStateWithDescriptor:sampler_desc];
    uint64_t handles[3]={t.gpuResourceID._impl,p.gpuAddress,sampler.gpuResourceID._impl};id<MTLBuffer> args=[g_dev newBufferWithBytes:handles length:sizeof handles options:MTLResourceStorageModeShared];
    NSUInteger row=(n*16+255)&~255u;id<MTLBuffer> out=[g_dev newBufferWithLength:row options:MTLResourceStorageModeShared];
    MTLTextureDescriptor *td=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatRGBA32Float width:n height:1 mipmapped:NO];td.storageMode=MTLStorageModePrivate;td.usage=MTLTextureUsageRenderTarget;
    id<MTLTexture> target=[g_dev newTextureWithDescriptor:td];res_add(p);res_add(args);res_add(out);res_add(target);
    MTL4ArgumentTableDescriptor *ad=[MTL4ArgumentTableDescriptor new];ad.maxBufferBindCount=1;id<MTL4ArgumentTable> a=rec_table([g_dev newArgumentTableWithDescriptor:ad error:&error]);[a setAddress:args.gpuAddress atIndex:0];
    MTL4RenderPassDescriptor *rp=[MTL4RenderPassDescriptor new];rp.colorAttachments[0].texture=target;rp.colorAttachments[0].loadAction=MTLLoadActionDontCare;rp.colorAttachments[0].storeAction=MTLStoreActionStore;
    id<MTL4RenderCommandEncoder> e=enc_r_begin(rp);[e setArgumentTable:a atStages:MTLRenderStageFragment];enc_r_pso(e,ps);[e setViewport:(MTLViewport){0,0,n,1,0,1}];enc_r_draw(e,MTLPrimitiveTypeTriangle,0,3);enc_r_end(e);
    enc_b_copy_texture_buffer(blit(),target,0,0,MTLOriginMake(0,0,0),MTLSizeMake(n,1,1),out,0,row,row);finish();
    const float *v=out.contents;for(unsigned i=0;i<n;i++){int ok=1;for(int c=0;c<4;c++)ok &= fabsf(v[4*i+c]-want[i][c])<.006f;CHECK(ok,"indirect fragment sampling preserves sparse pixels and holes");if(!ok)fprintf(stderr,"fragment pixel %u: %g %g %g %g\n",i,v[4*i],v[4*i+1],v[4*i+2],v[4*i+3]);}
    res_remove(p);res_remove(args);res_remove(out);res_remove(target);
}
static void pixels(id<MTLTexture> t,const uint32_t (*p)[4],const float (*want)[4],unsigned n){for(int mode=0;mode<3;mode++)pixels_mode(t,p,want,n,mode);fragment_pixels(t,p,want,n);}
// These probes deliberately rebind old versions after production has retired them. Their original submissions have completed; make the retained snapshot resident again for this new read.
static void retired_pixels(id<MTLTexture> t, const uint32_t (*points)[4], const float (*want)[4], unsigned n) {
    id<MTLTexture> root=t; while(root.parentTexture) root=root.parentTexture;
    res_add(root); pixels(t,points,want,n); res_remove(root);
}
static void run(int astc,int gob2) {
    nvn_gob_switch2=gob2;
    tex_t t={.magic=MAGIC('T','E','X',0),.serial=64000+(uint64_t)astc*10+gob2};
    t.d=(nvn_texdesc){.target=NVN_TEXTURE_TARGET_2D_ARRAY,.format=astc?NVN_FORMAT_RGBA_ASTC_8x8_SRGB:NVN_FORMAT_RGBA8,
        .flags=NVN_TEXTURE_FLAGS_SPARSE,.width=1024,.height=1024,.depth=2,.levels=11,.samples=1};
    nvn_tex_layout(&t.d,&t.L);uint32_t tw,th,td;unsigned tail=nvn_tex_sparse_tiles(&t.d,&tw,&th,&td);uint64_t to=nvn_tex_level_offset(&t.d,tail);
    const size_t size=4*65536;uint8_t *mem=mmap(NULL,size,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANON,-1,0);
    const uint8_t red[16]={0xfc,0xfd,0xff,0xff,0xff,0xff,0xff,0xff,255,255,0,0,0,0,255,255};
    const uint8_t green[16]={0xfc,0xfd,0xff,0xff,0xff,0xff,0xff,0xff,0,0,255,255,0,0,255,255};
    const uint8_t blue[16]={0xfc,0xfd,0xff,0xff,0xff,0xff,0xff,0xff,0,0,0,0,255,255,255,255};
    for(size_t i=0;i<size;i+=astc?16:4){unsigned page=(unsigned)(i/65536);if(astc)memcpy(mem+i,page==1?green:page==2?blue:red,16);else{mem[i]=page==1?0:page==2?0:255;mem[i+1]=page==1?255:0;mem[i+2]=page==2?255:0;mem[i+3]=255;}}
    pool_t physical,sparse;pool_builder_t pb={.mem=mem,.size=size,.flags=0x24};
    CHECK(h_nvnMemoryPoolInitialize((NVNmemoryPool*)&physical,(NVNmemoryPoolBuilder*)&pb),"sparse source pool initializes");
    pb=(pool_builder_t){.size=MAX(DM_GAME_APP_POOL,t.L.size)+65536,.flags=0x200};
    CHECK(h_nvnMemoryPoolInitialize((NVNmemoryPool*)&sparse,(NVNmemoryPoolBuilder*)&pb),"sparse virtual pool initializes");
    map_req maps[]={{.phys=(NVNmemoryPool*)&physical,.size=65536},{.phys=(NVNmemoryPool*)&physical,.poff=65536,.voff=65536,.size=4096},
        {.phys=(NVNmemoryPool*)&physical,.poff=2*65536,.voff=to,.size=65536},{.phys=(NVNmemoryPool*)&physical,.poff=3*65536,.voff=t.L.layer_size,.size=65536}};
    CHECK(h_nvnMemoryPoolMapVirtual((NVNmemoryPool*)&sparse,4,(NVNmappingRequest*)maps),"selected tiles and partial pages map");
    t.pool=&sparse;t.mem=sparse.mem;if(test_copy)t.has_layout=1;mtl_tex_init(&t);uint64_t stamp=nvn_dirty_now();
    id<MTLTexture> x=test_copy ? tex_mtl(&t) : pkg_upload(&t,&stamp,nil,0);
    CHECK(x.isSparse,"upload creates a genuinely sparse texture");CHECK(((NvSparseHeap *)objc_getAssociatedObject(x,&g_sparse_heap_owner_key))->heap.size==4*65536,"physical heap holds only four mapped tiles");
    CHECK([g_res_objects containsObject:x],"placement sparse metadata is resident alongside the physical heaps");
    const uint32_t points[][4]={{0,0,0,0},{tw,0,0,0},{tw+tw/2,0,0,0},{0,th,0,0},{0,0,0,tail},{0,0,1,0},{0,0,1,tail}};
    const float want[][4]={{1,0,0,1},{0,1,0,1},{0,0,0,0},{0,0,0,0},{0,0,1,1},{1,0,0,1},{0,0,0,0}};
    fragment_pixels(x,points,want,7);
    pixels(x,points,want,7);
    if(test_share) {
        tex_t other=t;other.serial+=1000;uint64_t before=g_sparse_backed;
        id<MTLTexture> alias=pkg_upload(&other,&stamp,nil,0);
        NvSparseHeap *a=objc_getAssociatedObject(x,&g_sparse_heap_owner_key),*b=objc_getAssociatedObject(alias,&g_sparse_heap_owner_key);
        CHECK(alias.isSparse && alias!=x,"another descriptor gets its own sparse metadata");
        unsigned shared=0;for(size_t i=0;i<a->count;i++)shared+=a->pages[i]==b->pages[i];
        CHECK(a->pages[0]==a->pages[3],"identical contents from distinct physical source pages share within a texture");
        CHECK(shared==4,"immutable contents share across descriptors, including partial physical tiles");
        CHECK(g_sparse_backed==before,"identical descriptor contents need no additional tile uploads");
        pixels(alias,points,want,7);
        // Dirty notifications do not imply different content. An identical write must keep
        // the same metadata and residency, rather than mapping every unchanged tile again.
        uint8_t identical=mem[0];dm_guest_write_prepare(mem,4096);*(volatile uint8_t *)mem=identical;
        id<MTLTexture> unchanged=pkg_upload(&other,&stamp,alias,0);
        CHECK(unchanged==alias,"an identical sparse refresh retains its metadata allocation");
        CHECK(g_sparse_backed==before,"an identical sparse refresh uploads no physical pages");
        pixels(unchanged,points,want,7);
        if(unchanged!=alias)defer_obj_release(unchanged);
        // A different tail shape may read the same bytes but has another hardware mip layout.
        tex_t shorter=other;shorter.serial++;shorter.d.levels--;nvn_tex_layout(&shorter.d,&shorter.L);
        id<MTLTexture> short_tex=pkg_upload(&shorter,&stamp,nil,0);
        NvSparseHeap *short_owner=objc_getAssociatedObject(short_tex,&g_sparse_heap_owner_key);int separate=0;
        for(size_t i=0;i<a->count;i++)if(a->tiles[i].level==tail && !a->tiles[i].layer)
            for(size_t j=0;j<short_owner->count;j++)if(short_owner->tiles[j].level==tail && !short_owner->tiles[j].layer)separate=a->pages[i]!=short_owner->pages[j];
        CHECK(separate,"different mip-tail shapes never share physical GPU pages");
        dm_guest_write_prepare(mem,65536);
        for(size_t i=0;i<65536;i+=astc?16:4)if(astc)memcpy(mem+i,green,16);else{mem[i]=0;mem[i+1]=255;mem[i+2]=0;mem[i+3]=255;}
        before=g_sparse_backed;id<MTLTexture> changed=pkg_upload(&other,&stamp,alias,0);
        NvSparseHeap *c=objc_getAssociatedObject(changed,&g_sparse_heap_owner_key);
        CHECK(changed!=alias,"a changed tile mapping gets a new metadata version");
        CHECK(c->pages[0]!=a->pages[0],"a source write forks the shared immutable tile");
        CHECK(g_sparse_backed-before==65536,"a source write uploads only its changed contents");
        float now[7][4];memcpy(now,want,sizeof now);now[0][0]=0;now[0][1]=1;
        pixels(changed,points,now,7);retired_pixels(x,points,want,7);retired_pixels(alias,points,want,7);
        // A changed mapping of completed pages needs no upload on the classic
        // queue. Hold that queue to prove this path does not wait for it.
        id<MTLSharedEvent> gate=[g_dev newSharedEvent];id<MTLCommandBuffer> blocker=[g_q commandBuffer];
        [blocker encodeWaitForEvent:gate value:1];queue3_commit(blocker);
        dispatch_semaphore_t returned=dispatch_semaphore_create(0);dispatch_group_t rescue=dispatch_group_create();
        dispatch_group_async(rescue,dispatch_get_global_queue(QOS_CLASS_USER_INITIATED,0),^{if(dispatch_semaphore_wait(returned,dispatch_time(DISPATCH_TIME_NOW,3*NSEC_PER_SEC)))gate.signaledValue=1;});
        before=g_sparse_backed;id<MTLTexture> rebound=pkg_upload(&other,&stamp,alias,0);
        CHECK(gate.signaledValue==0,"mapping completed pages does not wait for the held upload queue");
        dispatch_semaphore_signal(returned);gate.signaledValue=1;dispatch_group_wait(rescue,DISPATCH_TIME_FOREVER);
        CHECK(g_sparse_backed==before,"a changed mapping can reuse cached contents without uploading bytes");
        CHECK(rebound!=alias,"zero uploaded bytes do not make a changed mapping a no-op");
        pixels(rebound,points,now,7);
        dm_guest_write_prepare(mem,65536);
        for(size_t i=0;i<65536;i+=astc?16:4)if(astc)memcpy(mem+i,red,16);else{mem[i]=255;mem[i+1]=0;mem[i+2]=0;mem[i+3]=255;}
        defer_obj_release(alias);defer_obj_release(changed);defer_obj_release(rebound);defer_obj_release(short_tex);
    }
    if(test_copy){
        tex_t source={.magic=MAGIC('T','E','X',0),.serial=66000};source.d=t.d;source.d.target=NVN_TEXTURE_TARGET_2D;source.d.width=773;source.d.height=1020;source.d.depth=source.d.levels=1;source.d.flags=0;nvn_tex_layout(&source.d,&source.L);
        size_t bytes=(source.L.size+16383)&~(size_t)16383;uint8_t *sm=mmap(NULL,bytes,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANON,-1,0);for(size_t i=0;i<bytes;i+=16)memcpy(sm+i,test_gpu_copy?red:green,16);
        pool_t sp;pool_builder_t sb={.mem=sm,.size=bytes,.flags=0x24};CHECK(h_nvnMemoryPoolInitialize((NVNmemoryPool*)&sp,(NVNmemoryPoolBuilder*)&sb),"odd-sized ASTC copy source initializes");source.pool=&sp;source.mem=sm;if(test_gpu_copy){source.has_layout=1;source.d.flags=NVN_TEXTURE_FLAGS_IMAGE;}mtl_tex_init(&source);
        if(test_gpu_copy){
            id<MTLTexture> gpu_source=tex_mtl(&source);size_t row=((source.d.width+7)/8)*16,img=row*((source.d.height+7)/8);
            id<MTLBuffer> blocks=[g_dev newBufferWithLength:img options:MTLResourceStorageModeShared];for(size_t i=0;i<img;i+=16)memcpy((uint8_t*)blocks.contents+i,green,16);res_add(blocks);
            enc_b_copy_buffer_texture(blit(),blocks,0,row,img,MTLSizeMake(773,1020,1),gpu_source,0,0,MTLOriginMake(0,0,0));defer_obj_release(blocks);
        }
        p_copy_t2t copy={.src=&source,.dst=&t,.sr={0,0,0,773,1020,1},.dr={0,0,0,773,1020,1}};copy_t2t(&copy);
        mtl_reg_tex(73000,&t,NULL);id<MTLTexture> copied_texture=tex_by_id(73000);CHECK(copied_texture.isSparse,"copied sparse texture remains sparse");
        NvSparseHeap *before_copy=objc_getAssociatedObject(x,&g_sparse_heap_owner_key), *after_copy=objc_getAssociatedObject(copied_texture,&g_sparse_heap_owner_key);
        unsigned shared=0; for(size_t i=0;i<before_copy->count;i++)shared += before_copy->pages[i]==after_copy->pages[i];
        CHECK(shared==(test_ro?3u:2u),"copy forks changed bytes while content sharing preserves an unchanged written tile");
        CHECK(before_copy->pages[0]!=after_copy->pages[0],"the copied tile whose colour changes gets new immutable backing");
        CHECK(!memcmp(mem,green,16),"sparse copy changes its physical backing before first sampling");
        const float copied[][4]={{0,1,0,1},{0,1,0,1},{0,0,0,0},{0,0,0,0},{0,0,1,1},{1,0,0,1},{0,0,0,0}};
        pixels(copied_texture,points,copied,7);retired_pixels(x,points,want,7);
        // A small upload must not dirty every mapped tile of its mip level.
        p_copy_t2t small=copy;small.sr.width=small.dr.width=16;small.sr.height=small.dr.height=16;
        copy_t2t(&small);id<MTLTexture> small_texture=(__bridge id)tex_fast(73000);
        NvSparseHeap *small_owner=objc_getAssociatedObject(small_texture,&g_sparse_heap_owner_key);
        shared=0;for(size_t i=0;i<after_copy->count;i++)shared += after_copy->pages[i]==small_owner->pages[i];
        CHECK(shared==(test_ro?4u:3u),"a small copy preserves other tiles and identical written contents can reuse the current version");
        if(test_ro)CHECK(small_texture==copied_texture,"an identical copy keeps the current sparse metadata");
        pixels(small_texture,points,copied,7);
        if(test_ro){finish();finish();CHECK([g_res_objects containsObject:small_texture],"an unchanged live texture stays resident after deferred releases drain");}
        p_copy_t2t second={.src=&t,.dst=&t,.sr={0,0,0,773,1020,1},.dr={0,0,1,773,1020,1}};copy_t2t(&second);
        CHECK(!memcmp(mem+3*65536,green,16),"copying from sparse storage preserves source bytes in another layer");
        float copied_again[7][4];memcpy(copied_again,copied,sizeof copied_again);copied_again[5][0]=0;copied_again[5][1]=1;
        id<MTLTexture> second_texture=(__bridge id)tex_fast(73000);pixels(second_texture,points,copied_again,7);retired_pixels(copied_texture,points,copied,7);
        if(test_gpu_copy){
            id<MTLTexture> gpu_source=tex_mtl(&source);size_t row=((source.d.width+7)/8)*16,img=row*((source.d.height+7)/8);
            id<MTLBuffer> blocks=[g_dev newBufferWithLength:img options:MTLResourceStorageModeShared];for(size_t i=0;i<img;i+=16)memcpy((uint8_t*)blocks.contents+i,blue,16);res_add(blocks);
            enc_b_copy_buffer_texture(blit(),blocks,0,row,img,MTLSizeMake(773,1020,1),gpu_source,0,0,MTLOriginMake(0,0,0));defer_obj_release(blocks);
            copy_t2t(&copy);copy.dr.zoffset=1;copy_t2t(&copy);
            CHECK(mrb_pending(t.serial),"multiple GPU copies remain batched before sampling");
            id<MTLTexture> newest=(__bridge id)tex_fast(73000);CHECK(!mrb_pending(t.serial),"cached descriptor waits for all pending GPU copies");
            float batch[7][4];memcpy(batch,copied_again,sizeof batch);batch[0][1]=batch[1][1]=batch[5][1]=0;batch[0][2]=batch[1][2]=batch[5][2]=1;
            pixels(newest,points,batch,7);retired_pixels(second_texture,points,copied_again,7);
        }
        mtl_tex_release(&source);h_nvnMemoryPoolFinalize((NVNmemoryPool*)&sp);munmap(sm,bytes);
        defer_obj_release(x);x=nil;mtl_tex_release(&t);h_nvnMemoryPoolFinalize((NVNmemoryPool*)&sparse);h_nvnMemoryPoolFinalize((NVNmemoryPool*)&physical);finish();finish();munmap(mem,size);return;
    }
    if(test_upgrade){
        id<MTLTexture> upgraded=tex_upgrade(&t,x,MTLTextureUsageRenderTarget,x.pixelFormat);
        finish();if(mtl_last_commit_error())exit(1);
        pixels(upgraded,points,want,7);
        x=nil;mtl_tex_release(&t);h_nvnMemoryPoolFinalize((NVNmemoryPool*)&sparse);h_nvnMemoryPoolFinalize((NVNmemoryPool*)&physical);finish();finish();munmap(mem,size);return;
    }
    // A remap rebuilds the native texture from the new backing, without preserving stale tiles.
    map_req unmap={.voff=0,.size=65536};CHECK(h_nvnMemoryPoolMapVirtual((NVNmemoryPool*)&sparse,1,(NVNmappingRequest*)&unmap),"a tile unmaps");
    uint64_t before=g_sparse_backed;
    id<MTLTexture> y=pkg_upload(&t,&stamp,x,0);
    CHECK(y!=x,"unmapping a tile creates new metadata even without uploads");
    CHECK(g_sparse_backed==before,"unmapping one tile shares all surviving physical pages without uploads");
    const float zero[][4]={{0,0,0,0}};pixels(y,points,zero,1);
    map_req empty={.size=t.L.size};CHECK(h_nvnMemoryPoolMapVirtual((NVNmemoryPool*)&sparse,1,(NVNmappingRequest*)&empty),"all sparse tiles unmap");
    id<MTLTexture> holes=pkg_upload(&t,&stamp,y,0);
    CHECK(holes.isSparse && !((NvSparseHeap *)objc_getAssociatedObject(holes,&g_sparse_heap_owner_key))->count,"an empty mapping keeps sparse metadata without physical pages");
    const float black[7][4]={{0}};pixels_mode(holes,points,black,7,0);
    defer_obj_release(x);defer_obj_release(y);defer_obj_release(holes);x=nil;y=nil;mtl_tex_release(&t);
    h_nvnMemoryPoolFinalize((NVNmemoryPool*)&sparse);h_nvnMemoryPoolFinalize((NVNmemoryPool*)&physical);finish();finish();
    munmap(mem,size);
}
// Mutate guest storage at the real event-creation seam, after hashing/staging but before upload encoding.
@interface SparseSnapshotDevice : NSObject { @public id<MTLDevice> device; uint8_t *memory; } @end
@implementation SparseSnapshotDevice
- (id)forwardingTargetForSelector:(SEL)selector { return device; }
- (id<MTLSharedEvent>)newSharedEvent {
    if(memory){dm_guest_write_prepare(memory,65536);for(size_t i=0;i<65536;i+=4){memory[i]=203;memory[i+1]=67;memory[i+2]=19;memory[i+3]=255;}memory=NULL;}
    return [device newSharedEvent];
}
@end
static void snapshot_content(void) {
    nvn_gob_switch2=1;size_t bytes=2*65536;uint8_t *mem=mmap(NULL,bytes,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANON,-1,0);
    for(size_t i=0;i<bytes;i+=4){mem[i]=37;mem[i+1]=91;mem[i+2]=143;mem[i+3]=255;}
    pool_t physical,virtual;pool_builder_t b={.mem=mem,.size=bytes,.flags=0x24};
    CHECK(h_nvnMemoryPoolInitialize((NVNmemoryPool*)&physical,(NVNmemoryPoolBuilder*)&b),"snapshot physical pool initializes");
    b=(pool_builder_t){.size=DM_GAME_APP_POOL+65536,.flags=0x200};CHECK(h_nvnMemoryPoolInitialize((NVNmemoryPool*)&virtual,(NVNmemoryPoolBuilder*)&b),"snapshot virtual pool initializes");
    map_req mapping={.phys=(NVNmemoryPool*)&physical,.size=bytes};CHECK(h_nvnMemoryPoolMapVirtual((NVNmemoryPool*)&virtual,1,(NVNmappingRequest*)&mapping),"snapshot source maps");
    tex_t t={.magic=MAGIC('T','E','X',0),.serial=99000,.pool=&virtual,.mem=virtual.mem};
    t.d=(nvn_texdesc){.target=NVN_TEXTURE_TARGET_2D_ARRAY,.format=NVN_FORMAT_RGBA8,.flags=NVN_TEXTURE_FLAGS_SPARSE,.width=1024,.height=1024,.depth=1,.levels=1,.samples=1};nvn_tex_layout(&t.d,&t.L);mtl_tex_init(&t);
    SparseSnapshotDevice *proxy=[SparseSnapshotDevice new];proxy->device=g_dev;proxy->memory=mem;g_dev=(id)proxy;
    uint64_t stamp;id<MTLTexture> first=pkg_upload(&t,&stamp,nil,0);g_dev=proxy->device;
    CHECK(mem[0]==203 && mem[1]==67,"guest write occurs after the captured upload snapshot");
    uint32_t tw,th,td;nvn_tex_sparse_tiles(&t.d,&tw,&th,&td);const uint32_t points[][4]={{0,0,0,0},{tw,0,0,0}};
    const float original[][4]={{37/255.f,91/255.f,143/255.f,1},{37/255.f,91/255.f,143/255.f,1}};
    pixels(first,points,original,2);
    id<MTLTexture> second=pkg_upload(&t,&stamp,nil,0);
    const float updated[][4]={{203/255.f,67/255.f,19/255.f,1},{37/255.f,91/255.f,143/255.f,1}};pixels(second,points,updated,2);
    dm_guest_write_prepare(mem,65536);for(size_t i=0;i<65536;i+=4){mem[i]=37;mem[i+1]=91;mem[i+2]=143;mem[i+3]=255;}
    uint64_t before=g_sparse_backed;id<MTLTexture> third=pkg_upload(&t,&stamp,nil,0);
    CHECK(g_sparse_backed==before,"restoring bytes reuses their original immutable content without upload");pixels(third,points,original,2);
    // Both CPU-backed and GPU-written buffer copies must fork immutable sparse storage.
    size_t stream_bytes=(size_t)tw*th*4;uint8_t *stream=mmap(NULL,stream_bytes,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANON,-1,0);
    for(size_t i=0;i<stream_bytes;i+=4){stream[i]=203;stream[i+1]=67;stream[i+2]=19;stream[i+3]=255;}
    pool_t source_pool;b=(pool_builder_t){.mem=stream,.size=stream_bytes,.flags=0x24};CHECK(h_nvnMemoryPoolInitialize((NVNmemoryPool*)&source_pool,(NVNmemoryPoolBuilder*)&b),"buffer-copy source initializes");
    mtl_reg_tex(997,&t,NULL);S.copy_stride=S.copy_img_stride=0;
    p_copy_b2t copy={.src=(uint64_t)(uintptr_t)stream,.tex=&t,.r={0,0,0,(int)tw,(int)th,1}};copy_b2t(&copy);
    id<MTLTexture> cpu_copy=tex_by_id(997);finish();pixels(cpu_copy,points,updated,2);retired_pixels(first,points,original,2);
    mtl_sub_fill((uint64_t)(uintptr_t)stream,stream_bytes,0xffe73711u);copy_b2t(&copy);
    CHECK(mrb_pending(t.serial),"GPU-written buffer copy waits for ordered canonical-storage readback");
    id<MTLTexture> gpu_copy=tex_by_id(997);CHECK(!mrb_pending(t.serial),"resolving the destination lands its pending buffer copy");finish();
    const float filled[][4]={{17/255.f,55/255.f,231/255.f,1},{37/255.f,91/255.f,143/255.f,1}};
    pixels(gpu_copy,points,filled,2);retired_pixels(second,points,updated,2);
    h_nvnMemoryPoolFinalize((NVNmemoryPool*)&source_pool);finish();finish();munmap(stream,stream_bytes);
    defer_obj_release(first);defer_obj_release(second);defer_obj_release(third);first=second=third=nil;mtl_tex_release(&t);
    h_nvnMemoryPoolFinalize((NVNmemoryPool*)&virtual);h_nvnMemoryPoolFinalize((NVNmemoryPool*)&physical);finish();finish();munmap(mem,bytes);
}
static void large_bc6(int gob2) {
    nvn_gob_switch2=gob2;
    tex_t t={.magic=MAGIC('T','E','X',0),.serial=65000+(uint64_t)gob2};
    t.d=(nvn_texdesc){.target=NVN_TEXTURE_TARGET_2D_ARRAY,.format=NVN_FORMAT_BPTC_UFLOAT,
        .flags=NVN_TEXTURE_FLAGS_SPARSE,.width=8192,.height=8192,.depth=68,.levels=12,.samples=1};
    nvn_tex_layout(&t.d,&t.L);uint32_t tw,th,td;unsigned tail=nvn_tex_sparse_tiles(&t.d,&tw,&th,&td);
    uint64_t to=67*t.L.layer_size+nvn_tex_level_offset(&t.d,tail);
    const size_t size=2*65536;uint8_t *mem=mmap(NULL,size,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANON,-1,0);
    memset(mem,0,size);   // valid BC6H black blocks; decoded alpha is one in backed tiles
    pool_t physical,sparse;pool_builder_t pb={.mem=mem,.size=size,.flags=0x24};
    CHECK(h_nvnMemoryPoolInitialize((NVNmemoryPool*)&physical,(NVNmemoryPoolBuilder*)&pb),"large BC6H source pool initializes");
    pb=(pool_builder_t){.size=MAX(DM_GAME_APP_POOL,t.L.size)+65536,.flags=0x200};
    CHECK(h_nvnMemoryPoolInitialize((NVNmemoryPool*)&sparse,(NVNmemoryPoolBuilder*)&pb),"large BC6H virtual pool initializes");
    map_req maps[]={{.phys=(NVNmemoryPool*)&physical,.size=65536},
        {.phys=(NVNmemoryPool*)&physical,.poff=65536,.voff=to,.size=65536}};
    CHECK(h_nvnMemoryPoolMapVirtual((NVNmemoryPool*)&sparse,2,(NVNmappingRequest*)maps),"first tile and final-layer tail map");
    t.pool=&sparse;t.mem=sparse.mem;mtl_tex_init(&t);uint64_t stamp;
    id<MTLTexture> x=pkg_upload(&t,&stamp,nil,0);
    CHECK(x.isSparse && x.arrayLength==68,"full course-array dimensions use native sparse backing");
    CHECK(t.L.size>(1ull<<30) && ((NvSparseHeap *)objc_getAssociatedObject(x,&g_sparse_heap_owner_key))->count==2 && x.allocatedSize<(4u<<20),"multi-gigabyte BC6H array uses two mapped tiles plus small metadata");
    const uint32_t points[][4]={{0,0,0,0},{tw,0,0,0},{0,0,67,tail},{0,0,67,11},{0,0,66,tail}};
    // BC6H has no alpha component: Metal supplies one even for an unmapped texel's zero RGB.
    const float want[][4]={{0,0,0,1},{0,0,0,1},{0,0,0,1},{0,0,0,1},{0,0,0,1}};
    id<MTLTexture> viewed=[x newTextureViewWithPixelFormat:x.pixelFormat textureType:x.textureType levels:NSMakeRange(0,x.mipmapLevelCount) slices:NSMakeRange(0,x.arrayLength) swizzle:MTLTextureSwizzleChannelsMake(MTLTextureSwizzleRed,MTLTextureSwizzleGreen,MTLTextureSwizzleBlue,MTLTextureSwizzleOne)];
    fragment_pixels(viewed,points,want,5);
    id<MTLTexture> tail_view=[x newTextureViewWithPixelFormat:x.pixelFormat textureType:x.textureType levels:NSMakeRange(tail,x.mipmapLevelCount-tail) slices:NSMakeRange(67,1)];
    const uint32_t view_points[][4]={{0,0,0,0},{0,0,0,11-tail}};const float view_want[][4]={{0,0,0,1},{0,0,0,1}};fragment_pixels(tail_view,view_points,view_want,2);
    fragment_pixels(x,points,want,5);
    pixels(x,points,want,5);
    const uint32_t lod_points[][4]={{0,0,67,12},{0,0,67,13},{0,0,67,10000},{0,0,66,10000}};
    const float lod_want[][4]={{0,0,0,1},{0,0,0,1},{0,0,0,1},{0,0,0,1}};
    for(int mode=1;mode<3;mode++)pixels_mode(x,lod_points,lod_want,4,mode);fragment_pixels(x,lod_points,lod_want,4);
defer_obj_release(x);x=nil;mtl_tex_release(&t);
    h_nvnMemoryPoolFinalize((NVNmemoryPool*)&sparse);h_nvnMemoryPoolFinalize((NVNmemoryPool*)&physical);finish();finish();munmap(mem,size);
}
int main(int argc,char **argv){@autoreleasepool{test_share=argc>1&&!strcmp(argv[1],"share");if(test_share)setenv("DM_NVN_SPARSE_RO_SHARE","1",1);test_ro=getenv("DM_NVN_SPARSE_RO_SHARE") && atoi(getenv("DM_NVN_SPARSE_RO_SHARE"));test_upgrade=argc>1&&!strcmp(argv[1],"upgrade");test_gpu_copy=argc>1&&!strcmp(argv[1],"gpu-copy");test_copy=test_gpu_copy||(argc>1&&!strcmp(argv[1],"copy"));setenv("DM_NVN_NATIVE_SPARSE","1",1);mtl_init();mtl_sub_begin();if(test_upgrade)run(0,1);else if(test_copy)run(1,1);else for(int gob=0;gob<2;gob++){for(int astc=0;astc<2;astc++)run(astc,gob);large_bc6(gob);}
    if(test_share)snapshot_content();
    mtl_sub_commit();mtl_drain();printf("native sparse uploads: %d checks, %d failed\n",checks,failed);return failed!=0;}}
