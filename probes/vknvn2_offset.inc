// Native dense sampling is the reference for every offset/gather overload.
static void offset_render_cases(uint8_t *job,const tex_t *logical,const tex_t *dense,const tex_t *target,const prog_t *program,unsigned format,int gob){
    unsigned mismatches=0;float maximum=0;double energy=0;float pixels[32*32*4];
    for(unsigned minf=0;minf<6;minf++)for(unsigned mag=0;mag<2;mag++)for(unsigned wrap=0;wrap<2;wrap++)for(unsigned view_mode=0;view_mode<3;view_mode++)for(unsigned lod_case=0;lod_case<3;lod_case++)for(unsigned operation=0;operation<12;operation++){
        view_t view={0};
        if(view_mode==1){view.set_levels=view.set_layers=1;view.base_level=2;view.nlevels=5;view.min_layer=1;view.nlayers=2;}
        if(view_mode==2){view.set_swizzle=1;view.swz[0]=4;view.swz[1]=2;view.swz[2]=3;view.swz[3]=5;}
        mtl_reg_tex(201,logical,&view);mtl_reg_tex(202,dense,&view);
        samp_par sampler={.minf=minf,.magf=mag,.ws=wrap,.wt=wrap,.aniso=1,.lod_min=operation>=4 && minf>=2?2.3f:0,.lod_max=operation>=4 && minf>=2?3.2f:1000};mtl_reg_samp(1,&sampler);
        const float lods[3]={.25f,1.3f,9.2f},derivative_lods[3]={-1.25f,1.25f,3.25f},biases[3]={1.2f,-2.3f,100};float rho=exp2f(derivative_lods[lod_case]);float w=(float)(1024u>>view.base_level),h=(float)(512u>>view.base_level);
        float params[12]={rho/w,0,.18f*rho/w,rho/h,wrap?-.013f:.25f,wrap?1.002f:.5f,view_mode==1?1.2f:2,0,(float)operation,lods[lod_case],biases[lod_case],0};
        dm_guest_write_prepare(job+4096,sizeof params);memcpy(job+4096,params,sizeof params);mtl_sub_begin();implicit_record(job,target,program);if(!mtl_wait(mtl_sub_commit(),10000000000ull))abort();
        NVNcopyRegion region={.width=32,.height=32,.depth=1};mtl_read_texels(target,0,0,&region,(uint8_t*)pixels,32*16,sizeof pixels);
        int ok=1;float error=0;
        for(unsigned i=0;i<32*32;i++){float *p=pixels+4*i;ok&=isfinite(p[0]) && p[0]<.025f && p[3]==1;error=fmaxf(error,p[0]);energy+=p[1];}
        checks++;failed+=!ok;maximum=fmaxf(maximum,error);
        if(!ok && mismatches++<16)printf("offset FAIL format=%u gob=%d min=%u mag=%u wrap=%u view=%u lod=%u operation=%u error=%g first=%g,%g,%g,%g\n",format,gob,minf,mag,wrap,view_mode,lod_case,operation,error,pixels[0],pixels[1],pixels[2],pixels[3]);
    }
    printf("offset format=%u gob=%d max_error=%g energy=%g mismatched_cases=%u\n",format,gob,maximum,energy,mismatches);
}
static void offset_tests(void){for(unsigned format=0;format<3;format++)for(int gob=0;gob<2;gob++)implicit_case(format,gob,1);}
