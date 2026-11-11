// Compare rewritten virtual sampling with actual dense Vulkan sampling, per pixel.
// Both textures contain the same native compressed bytes, including every mip.
static void offset_render_cases(uint8_t *job,const tex_t *logical,const tex_t *dense,const tex_t *target,const prog_t *program,unsigned format,int gob);
static void implicit_fill(const tex_t *t,uint8_t *memory,unsigned format) {
    atlas_format=format;atlas_nonce=0;unsigned block=format==2?8:4;
    for(unsigned layer=0;layer<t->L.layers;layer++)for(unsigned mip=0;mip<t->d.levels;mip++){
        unsigned w=t->d.width>>mip,h=t->d.height>>mip;if(!w)w=1;if(!h)h=1;
        size_t pitch=((w+block-1)/block)*16;uint8_t *linear=malloc(pitch*((h+block-1)/block));if(!linear)abort();
        for(unsigned y=0;y<(h+block-1)/block;y++)for(unsigned x=0;x<(w+block-1)/block;x++)atlas_block(linear+y*pitch+x*16,(x/2+3*(y/3)+mip+layer)%4);
        if(nvn_swizzle(&t->d,mip,layer,linear,pitch,memory))abort();free(linear);
    }
}
static void implicit_record(uint8_t *job,const tex_t *target,const prog_t *program) {
    size_t used=0;
#define IPUT(OP,X) do{size_t n=(8+sizeof(X)+7)&~7ull;op_hdr h={OP,(uint32_t)n};memcpy(job+used,&h,8);memcpy(job+used+8,&(X),sizeof(X));used+=n;}while(0)
    p_set_rt rt={.n=1};rt.color[0]=target;IPUT(OP_SET_RT,rt);
    p_viewports vp={.n=1};vp.v[0][2]=vp.v[0][3]=32;IPUT(OP_VIEWPORTS,vp);p_scissor sc={0,0,32,32};IPUT(OP_SCISSOR,sc);
    p_clear_color clear={.index=0,.mask=15,.rgba={17,17,17,17}};IPUT(OP_CLEAR_COLOR,clear);
    p_bind_program bind={program,0xff};IPUT(OP_BIND_PROGRAM,bind);
    p_bind_handles textures={.stage=1,.n=2};textures.h[0]=201u|(1u<<20);textures.h[1]=202u|(1u<<20);IPUT(OP_BIND_TEX,textures);
    p_bind_buf params={.stage=1,.index=0,.addr=(uint64_t)(job+4096),.size=48};IPUT(OP_BIND_UBO,params);
    p_draw draw={.prim=4,.count=3,.instances=1};IPUT(OP_DRAW,draw);op_hdr end={OP_END,8};memcpy(job+used,&end,8);
#undef IPUT
    mtl_exec(job);
}
static void implicit_dense_bytes(const tex_t *dense,unsigned format){
    unsigned block=format==2?8:4;
    for(unsigned layer=0;layer<dense->L.layers;layer++)for(unsigned mip=0;mip<dense->d.levels;mip++){
        unsigned w=dense->d.width>>mip,h=dense->d.height>>mip;if(!w)w=1;if(!h)h=1;
        size_t pitch=((w+block-1)/block)*16,bytes=pitch*((h+block-1)/block);uint8_t *actual=malloc(bytes),*expected=malloc(bytes);if(!actual || !expected)abort();
        for(unsigned y=0;y<(h+block-1)/block;y++)for(unsigned x=0;x<(w+block-1)/block;x++)atlas_block(expected+y*pitch+x*16,(x/2+3*(y/3)+mip+layer)%4);
        NVNcopyRegion region={.width=(int)w,.height=(int)h,.depth=1};mtl_read_texels(dense,mip,layer,&region,actual,pitch,bytes);
        int ok=!memcmp(actual,expected,bytes);checks++;failed+=!ok;free(actual);free(expected);
        if(!ok){printf("implicit dense reference bytes FAIL format=%u layer=%u mip=%u\n",format,layer,mip);abort();}
    }
}
static void implicit_case(unsigned format,int gob,int offsets) {
    nvn_gob_switch2=gob;
    tex_t logical={.magic=MAGIC('T','E','X',0),.has_layout=1,.serial=50000+format*10+(unsigned)gob+offsets*1000};
    logical.d=(nvn_texdesc){.target=NVN_TEXTURE_TARGET_2D_ARRAY,.format=format==0?NVN_FORMAT_BPTC_UFLOAT:format==1?NVN_FORMAT_RGBA_ASTC_4x4:NVN_FORMAT_RGBA_ASTC_8x8_SRGB,.flags=NVN_TEXTURE_FLAGS_SPARSE,.width=1024,.height=512,.depth=3,.levels=11,.samples=1};nvn_tex_layout(&logical.d,&logical.L);
    size_t size=(logical.L.size+65535)&~65535ull;uint8_t *source=mmap(NULL,size,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0),*job=mmap(NULL,65536,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0);if(source==MAP_FAILED || job==MAP_FAILED)abort();implicit_fill(&logical,source,format);
    NVNT_nvnMemoryPoolInitialize init=atlas_api("nvnMemoryPoolInitialize");NVNT_nvnMemoryPoolFinalize finalize=atlas_api("nvnMemoryPoolFinalize");NVNT_nvnMemoryPoolMapVirtual map=atlas_api("nvnMemoryPoolMapVirtual");
    pool_t physical,virtual;pool_builder_t pb={.mem=source,.size=size,.flags=0x24};if(!init((NVNmemoryPool*)&physical,(NVNmemoryPoolBuilder*)&pb))abort();logical.off=0x800000000ll;pb=(pool_builder_t){.size=logical.off+size,.flags=0x200};if(!init((NVNmemoryPool*)&virtual,(NVNmemoryPoolBuilder*)&pb))abort();logical.pool=&virtual;logical.mem=(uint8_t*)((uintptr_t)virtual.mem+logical.off);
    AtlasMapping mapping={(NVNmemoryPool*)&physical,0,logical.off,size,0,0};if(!map((NVNmemoryPool*)&virtual,1,(NVNmappingRequest*)&mapping))abort();
    tex_t dense=logical;dense.serial+=100;dense.pool=&physical;dense.mem=source;dense.off=0;mtl_pool_add(job,65536);
    implicit_dense_bytes(&dense,format);
    tex_t target={.magic=MAGIC('T','E','X',0),.serial=logical.serial+200};target.d=(nvn_texdesc){.target=NVN_TEXTURE_TARGET_2D,.format=NVN_FORMAT_RGBA32F,.width=32,.height=32,.depth=1,.levels=1,.samples=1};
    prog_t program={.serial=60000+format*10+(unsigned)gob+offsets*1000,.nstage=2};program.sd[0].data=23;program.sd[1].data=offsets?25:24;
    if(offsets){offset_render_cases(job,&logical,&dense,&target,&program,format,gob);finalize((NVNmemoryPool*)&virtual);finalize((NVNmemoryPool*)&physical);mtl_pool_del(job);munmap(job,65536);munmap(source,size);return;}
    static const float lambdas[]={-2.25f,-.25f,.25f,1.25f,3.25f,10.25f,.25f,4.25f,-.25f,2.25f,1.25f,4.25f,0};
    float pixels[32*32*4];unsigned reported=0;float worst_color=0,worst_query=0;double energy=0;
    for(unsigned minf=0;minf<6;minf++)for(unsigned mag=0;mag<2;mag++)for(unsigned wrap=0;wrap<2;wrap++)for(unsigned scenario=0;scenario<14;scenario++){
        if(scenario==6 && minf<2)continue; // a positive minLod cannot exceed the no-mipmap maxLod=.25
        view_t view={0};if(scenario==4){view.set_levels=view.set_layers=1;view.base_level=2;view.nlevels=5;view.min_layer=1;view.nlayers=2;}
        mtl_reg_tex(201,scenario==13?&dense:&logical,&view);mtl_reg_tex(202,&dense,&view);
        samp_par sampler={.minf=minf,.magf=mag,.ws=wrap,.wt=wrap,.aniso=atlas_negative==2?2:1,.lod_max=scenario==7?1.3f:1000,.lod_min=scenario==6?2.3f:0};mtl_reg_samp(1,&sampler);
        float rho=scenario==12?0:exp2f(lambdas[scenario==13?3:scenario]);float w=(float)(1024u>>view.base_level),h=(float)(512u>>view.base_level);
        float params[12]={rho/w,0,.18f*rho/w,rho/h,wrap?-.013f:.237f,wrap?1.002f:.319f,scenario==4?1.2f:(float)(scenario%3),0,scenario>=8 && scenario<=11?1:0,scenario==8?1.25f:scenario==9?-1.3f:scenario==10?100:scenario==11?-100:0,0,0};
        if(scenario==2){params[0]=params[3]=0;params[1]=rho/h;params[2]=-rho/w;}
        dm_guest_write_prepare(job+4096,sizeof params);memcpy(job+4096,params,sizeof params);
        mtl_sub_begin();implicit_record(job,&target,&program);if(!mtl_wait(mtl_sub_commit(),10000000000ull))abort();
        NVNcopyRegion region={.width=32,.height=32,.depth=1};mtl_read_texels(&target,0,0,&region,(uint8_t*)pixels,32*16,sizeof pixels);
        int ok=1;float color=0,query=0;
        for(unsigned i=0;i<32*32;i++){float *p=pixels+4*i;ok&=isfinite(p[0]) && isfinite(p[1]) && isfinite(p[2]) && p[0]<.025f && p[1]<.01f && p[2]<.01f;color=fmaxf(color,p[0]);query=fmaxf(query,fmaxf(p[1],p[2]));energy+=p[3];}
        checks++;failed+=!ok;worst_color=fmaxf(worst_color,color);worst_query=fmaxf(worst_query,query);
        if(!ok && reported++<12)printf("implicit FAIL format=%u gob=%d min=%u mag=%u wrap=%u case=%u color_error=%g query_error=%g first=%g,%g,%g,%g\n",format,gob,minf,mag,wrap,scenario,color,query,pixels[0],pixels[1],pixels[2],pixels[3]);
    }
    printf("implicit format=%u gob=%d color_max=%g query_max=%g energy=%g mismatched_cases=%u\n",format,gob,worst_color,worst_query,energy,reported);
    finalize((NVNmemoryPool*)&virtual);finalize((NVNmemoryPool*)&physical);mtl_pool_del(job);munmap(job,65536);munmap(source,size);
}
static void implicit_tests(void){for(unsigned format=0;format<3;format++)for(int gob=0;gob<2;gob++)implicit_case(format,gob,0);}
