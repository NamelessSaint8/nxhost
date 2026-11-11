// Explicit LOD sets derivatives to zero even with an anisotropic sampler.
// Compare mapped storage with the actual dense Vulkan operation and switch
// their binding positions to exercise both specialization modes in one shader.
static void explicit_case(unsigned format,int gob){
    nvn_gob_switch2=gob;tex_t logical={.magic=MAGIC('T','E','X',0),.serial=45000+format*10+(unsigned)gob};logical.d=(nvn_texdesc){.width=256,.height=128,.depth=2,.levels=6,.samples=1,.target=NVN_TEXTURE_TARGET_2D_ARRAY,.format=format==0?NVN_FORMAT_BPTC_UFLOAT:format==1?NVN_FORMAT_RGBA_ASTC_4x4:NVN_FORMAT_RGBA_ASTC_8x8_SRGB,.flags=NVN_TEXTURE_FLAGS_SPARSE};nvn_tex_layout(&logical.d,&logical.L);
    uint8_t *mem=mmap(NULL,4*1048576,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0),*job=mmap(NULL,65536,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0);if(mem==MAP_FAILED || job==MAP_FAILED)abort();
    pool_t physical,virtual;pool_builder_t pb={.mem=mem,.size=4*1048576,.flags=0x24};NVNT_nvnMemoryPoolInitialize init=atlas_api("nvnMemoryPoolInitialize");NVNT_nvnMemoryPoolFinalize fini=atlas_api("nvnMemoryPoolFinalize");NVNT_nvnMemoryPoolMapVirtual map=atlas_api("nvnMemoryPoolMapVirtual");if(!init((NVNmemoryPool*)&physical,(NVNmemoryPoolBuilder*)&pb))abort();
    implicit_fill(&logical,mem,format);logical.off=65536;pb=(pool_builder_t){.size=logical.off+logical.L.size+65536,.flags=0x200};if(!init((NVNmemoryPool*)&virtual,(NVNmemoryPoolBuilder*)&pb))abort();logical.pool=&virtual;logical.mem=virtual.mem+logical.off;
    AtlasMapping mapped={(NVNmemoryPool*)&physical,0,logical.off,logical.L.size,0,0};if(!map((NVNmemoryPool*)&virtual,1,(NVNmappingRequest*)&mapped))abort();
    tex_t dense=logical;dense.serial+=100;dense.pool=&physical;dense.off=1048576;dense.mem=mem+dense.off;dense.d.flags=0;dense.has_layout=1;nvn_tex_layout(&dense.d,&dense.L);dm_guest_write_prepare(dense.mem,dense.L.size);implicit_fill(&dense,dense.mem,format);mtl_pool_add(job,65536);
    AtlasQuery *q=(AtlasQuery*)(job+16384);for(unsigned i=0;i<16;i++)q[i]=(AtlasQuery){.u=(float)i*.173f-.4f,.v=(float)i*.217f-.3f,.lod=(float)(i%8)*.8f-1,.layer=(float)(i%2)};
    atlas_shader_key=28;
    for(unsigned phase=0;phase<4;phase++){
        samp_par sampler={.minf=5,.magf=1,.ws=1,.wt=1,.aniso=(float)(1u<<phase),.lod_max=1000};mtl_reg_samp(1,&sampler);mtl_reg_tex(102,phase%2?&logical:&dense,NULL);
        mtl_sub_begin();atlas_record(job,phase%2?&dense:&logical,NULL,phase,q,16);if(!mtl_wait(mtl_sub_commit(),10000000000ull))abort();float *out=(float*)(job+4096+phase*512);
        for(unsigned i=0;i<16;i++){float delta=0;for(unsigned c=0;c<4;c++)delta=fmaxf(delta,fabsf(out[i*8+c]-out[i*8+4+c]));int ok=delta<.03f && fabsf(out[i*8+3]-1)<.0001f && fabsf(out[i*8+7]-1)<.0001f;checks++;failed+=!ok;printf("explicit LOD format=%u gob=%d aniso=%g query=%u %s delta=%g\n",format,gob,sampler.aniso,i,ok?"PASS":"FAIL",delta);}
    }
    atlas_shader_key=11;fini((NVNmemoryPool*)&virtual);fini((NVNmemoryPool*)&physical);mtl_pool_del(job);munmap(mem,4*1048576);munmap(job,65536);
}
static void explicit_tests(void){for(unsigned format=0;format<3;format++)for(int gob=0;gob<2;gob++)explicit_case(format,gob);}
