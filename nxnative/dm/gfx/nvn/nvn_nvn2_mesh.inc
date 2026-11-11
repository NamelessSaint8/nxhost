// Native NVN2 task/mesh draws. The ordinary draw path supplies raster state;
// these stages have independent bindings and no vertex-fetch layout.
static struct { int on; p_draw_mesh draw; NvShader *task,*mesh; } g_nvn2_mesh;
static nvn_hmap g_nvn2_mesh_pipelines;
static uint64_t g_nvn2_mesh_draws;
static void nvn2_mesh_tables(void) {
    if(g_nvn2_mesh_args)return;
    MTL4ArgumentTableDescriptor *d=[MTL4ArgumentTableDescriptor new];d.maxBufferBindCount=31;
    NSError *e=nil;g_nvn2_mesh_args=rec_table([g_dev newArgumentTableWithDescriptor:d error:&e]);
    g_nvn2_object_args=rec_table([g_dev newArgumentTableWithDescriptor:d error:&e]);
    if(!g_nvn2_mesh_args || !g_nvn2_object_args)MDIE("NVN2 mesh argument tables: %s",e.localizedDescription.UTF8String);
}
static id<MTLRenderPipelineState> nvn2_mesh_pso(NvProg *raster) {
    struct { pso_key raster; const void *task; } key;memset(&key,0,sizeof key);
    pso_key_fill(&key.raster,g_nvn2_mesh.mesh,raster->sh[1],g_pass.cfmt,g_pass.dfmt,g_pass.sfmt,g_pass.samples,0);
    memset(key.raster.attr,0,sizeof key.raster.attr);memset(key.raster.stream,0,sizeof key.raster.stream);
    key.task=(__bridge const void*)g_nvn2_mesh.task;
    if(!g_nvn2_mesh_pipelines.klen)g_nvn2_mesh_pipelines.klen=sizeof key;
    id cached=hm_get_id(&g_nvn2_mesh_pipelines,&key);if(cached)return cached==NSNull.null?nil:cached;
    MTLRenderPipelineDescriptor *state=pso_desc(&key.raster,g_nvn2_mesh.mesh,raster->sh[1],nil,0);
    MTLMeshRenderPipelineDescriptor *d=[MTLMeshRenderPipelineDescriptor new];
    d.meshFunction=fn_dev(g_nvn2_mesh.mesh->fn);d.objectFunction=g_nvn2_mesh.task?fn_dev(g_nvn2_mesh.task->fn):nil;
    d.fragmentFunction=fn_dev(state.fragmentFunction);d.rasterSampleCount=state.rasterSampleCount;
    d.alphaToCoverageEnabled=state.alphaToCoverageEnabled;d.alphaToOneEnabled=state.alphaToOneEnabled;
    d.depthAttachmentPixelFormat=state.depthAttachmentPixelFormat;d.stencilAttachmentPixelFormat=state.stencilAttachmentPixelFormat;
    for(unsigned i=0;i<8;i++)d.colorAttachments[i]=state.colorAttachments[i];
    d.maxTotalThreadsPerMeshThreadgroup=g_nvn2_mesh.mesh->nvn2_threads;
    if(g_nvn2_mesh.task){d.maxTotalThreadsPerObjectThreadgroup=g_nvn2_mesh.task->nvn2_threads;d.payloadMemoryLength=16384;}
    NSError *e=nil;uint64_t start=bp_now();id<MTLRenderPipelineState> p=[g_dev newRenderPipelineStateWithMeshDescriptor:d options:MTLPipelineOptionNone reflection:nil error:&e];
    MLOG("%sNVN2 mesh pipeline: task %s mesh %s fragment %s, %.1f ms%s%s",p?"":"[RED] ",g_nvn2_mesh.task?g_nvn2_mesh.task->key:"-",g_nvn2_mesh.mesh->key,raster->sh[1]?raster->sh[1]->key:"-",(bp_now()-start)/1e6,p?"":": ",p?"":e.localizedDescription.UTF8String);
    hm_put_id(&g_nvn2_mesh_pipelines,&key,(id)p?:(id)NSNull.null);return p;
}
static void nvn2_mesh_encode(id<MTLRenderCommandEncoder> en_) {
    id<MTL4RenderCommandEncoder> en=(id<MTL4RenderCommandEncoder>)en_;
    id<MTLBuffer>b;size_t off=arena_alloc(16,&b);uint32_t *v=(uint32_t*)((uint8_t*)b.contents+off);
    v[0]=g_nvn2_mesh.draw.first;v[1]=g_nvn2_mesh.draw.count;v[2]=v[3]=0;
    [g_nvn2_mesh_args setAddress:b.gpuAddress+off atIndex:12];
    [en setArgumentTable:g_nvn2_mesh_args atStages:MTLRenderStageMesh];
    if(g_nvn2_mesh.task){[g_nvn2_object_args setAddress:b.gpuAddress+off atIndex:12];[en setArgumentTable:g_nvn2_object_args atStages:MTLRenderStageObject];}
    [en drawMeshThreadgroups:MTLSizeMake(g_nvn2_mesh.draw.count,1,1)
      threadsPerObjectThreadgroup:MTLSizeMake(g_nvn2_mesh.task?g_nvn2_mesh.task->nvn2_threads:1,1,1)
      threadsPerMeshThreadgroup:MTLSizeMake(g_nvn2_mesh.mesh->nvn2_threads,1,1)];
    g_nvn2_mesh_draws++;PD("n %llu NVN2 mesh first=%u groups=%u task=%s mesh=%s",g_stat_pass,g_nvn2_mesh.draw.first,g_nvn2_mesh.draw.count,g_nvn2_mesh.task?g_nvn2_mesh.task->key:"-",g_nvn2_mesh.mesh->key);
}
static void nvn2_mesh_draw(const p_draw_mesh *a) {
    if(!a->count)return;
    NvProg *actual=S.prog?prog_get(S.prog):nil;
    NvShader *mesh=actual?actual->sh[7]:nil,*task=actual?actual->sh[6]:nil;
    if(!mesh || mesh->nvn2_kind!=7){RED_ONCE(171,"NVN2 mesh draw has no translated mesh stage");return;}
    nvn2_mesh_tables();image_prepare(actual,0xdf);
    if(g_nubd){rp_end();ubd_land();}
    if(!actual->nvn2_raster){NvProg *r=[NvProg new];r->sh[0]=mesh;r->sh[1]=actual->sh[1];r->sh[6]=task;r->sh[7]=mesh;actual->nvn2_raster=r;}
    g_nvn2_mesh.on=1;g_nvn2_mesh.draw=*a;g_nvn2_mesh.task=task;g_nvn2_mesh.mesh=mesh;
    NvProg *saved=g_geo_program;g_geo_program=actual->nvn2_raster;
    p_draw raster={.prim=4,.count=3,.instances=1};draw(&raster,NULL);
    g_geo_program=saved;g_nvn2_mesh.on=0;g_nvn2_mesh.task=g_nvn2_mesh.mesh=nil;
    g_pso_dirty=1;args_dirty_all();
}
