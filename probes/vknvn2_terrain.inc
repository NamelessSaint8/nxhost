// CPU-streamed terrain through real NVN registration and Vulkan image readback.
extern void nvn_ft_poll(void);
extern uint64_t vk_tex_tracking_count(void);
#define TERRAIN_API(name) ((NVNT_##name)atlas_api(#name))
static void terrain_check(int ok,const char *name) { checks++;failed+=!ok;printf("terrain gob=%d %s %s\n",nvn_gob_switch2,name,ok?"PASS":"FAIL"); }
static void terrain_fill(const nvn_texdesc *d,uint8_t *mem,unsigned bytes,unsigned seed) {
    nvn_texlayout layout;nvn_tex_layout(d,&layout);uint8_t *linear=malloc((size_t)d->width*d->height*bytes);
    for(unsigned y=0;y<d->height;y++)for(unsigned x=0;x<d->width;x++)for(unsigned c=0;c<bytes;c++)linear[((size_t)y*d->width+x)*bytes+c]=(uint8_t)(1+(x*3+y*5+c*7+seed)%251);
    dm_guest_write_prepare(mem,layout.size);memset(mem,0,layout.size);
    if(nvn_swizzle(d,0,0,linear,(size_t)d->width*bytes,mem))abort();free(linear);
}
static void terrain_pixels(const tex_t *t,unsigned bytes,unsigned seed,const char *name) {
    size_t len=(size_t)t->d.width*t->d.height*bytes;uint8_t *actual=malloc(len);memset(actual,0xa5,len);
    NVNcopyRegion region={.width=(int)t->d.width,.height=(int)t->d.height,.depth=1};
    mtl_read_texels(t,0,0,&region,actual,(size_t)t->d.width*bytes,len);
    size_t wrong=0;for(unsigned y=0;y<t->d.height;y++)for(unsigned x=0;x<t->d.width;x++)for(unsigned c=0;c<bytes;c++)wrong+=actual[((size_t)y*t->d.width+x)*bytes+c]!=(uint8_t)(1+(x*3+y*5+c*7+seed)%251);
    terrain_check(wrong==0,name);if(wrong)printf("terrain mismatched bytes=%zu/%zu format=%u\n",wrong,len,t->d.format);free(actual);
}
static void terrain_resolve(const tex_t *t) {
    mtl_sub_begin();vkimg_t *im=vk_tex(t);if(!im)abort();vk_tex_prepare(vk_upload_cmd(),im);
    if(!mtl_wait(mtl_sub_commit(),10000000000ull))abort();
}
static void terrain_clear(const tex_t *t) {
    uint8_t job[sizeof(op_hdr)+sizeof(p_clear_tex)+24]={0};p_clear_tex clear={.tex=t,.r={0,0,0,(int)t->d.width,(int)t->d.height,1},.mask=15,.c.f={.25f,.5f,0,1}};
    size_t len=(8+sizeof clear+7)&~7ull;op_hdr h={OP_CLEAR_TEX,(uint32_t)len};memcpy(job,&h,8);memcpy(job+8,&clear,sizeof clear);h=(op_hdr){OP_END,8};memcpy(job+len,&h,8);
    mtl_sub_begin();mtl_exec(job);if(!mtl_wait(mtl_sub_commit(),10000000000ull))abort();
}
static void terrain_clear_pixels(const tex_t *t,unsigned bytes,const char *name) {
    size_t len=(size_t)t->d.width*t->d.height*bytes;uint8_t *actual=malloc(len);NVNcopyRegion region={0,0,0,(int)t->d.width,(int)t->d.height,1};mtl_read_texels(t,0,0,&region,actual,(size_t)t->d.width*bytes,len);
    int ok=1;for(size_t i=0;i<(size_t)t->d.width*t->d.height;i++){
        if(bytes==1)ok&=actual[i]==64;
        else for(unsigned c=0;c<bytes/2;c++){uint16_t value;memcpy(&value,actual+i*bytes+c*2,2);unsigned expected=c?32768:16384;ok&=value==expected || value+1==expected;}
    }terrain_check(ok,name);free(actual);
}
static void terrain_case(int format,unsigned bytes,int gob) {
    nvn_gob_switch2=gob;const size_t len=8*1024*1024;uint8_t *mem=mmap(NULL,len,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0);if(mem==MAP_FAILED)abort();
    NVNmemoryPool pool={0};pool_builder_t pb={.mem=mem,.size=len,.flags=NVN_MEMORY_POOL_FLAGS_CPU_CACHED|NVN_MEMORY_POOL_FLAGS_GPU_CACHED};
    if(!TERRAIN_API(nvnMemoryPoolInitialize)(&pool,(const NVNmemoryPoolBuilder*)&pb))abort();
    NVNtextureBuilder builder;TERRAIN_API(nvnTextureBuilderSetDefaults)(&builder);TERRAIN_API(nvnTextureBuilderSetWidth)(&builder,260);TERRAIN_API(nvnTextureBuilderSetHeight)(&builder,260);TERRAIN_API(nvnTextureBuilderSetFormat)(&builder,format);TERRAIN_API(nvnTextureBuilderSetFlags)(&builder,NVN_TEXTURE_FLAGS_MINIMAL_LAYOUT);
    NVNtexture textures[6]={{0}};tex_t *t[6];
    for(unsigned i=0;i<6;i++){
        TERRAIN_API(nvnTextureBuilderSetStorage)(&builder,&pool,(ptrdiff_t)((i+1)*1048576));
        if(i==0)terrain_fill(&((tex_builder_t*)&builder)->d,mem+(i+1)*1048576,bytes,11);
        if(i==5)TERRAIN_API(nvnTextureBuilderSetFlags)(&builder,NVN_TEXTURE_FLAGS_MINIMAL_LAYOUT|NVN_TEXTURE_FLAGS_IMAGE);
        if(!TERRAIN_API(nvnTextureInitialize)(&textures[i],&builder))abort();t[i]=(tex_t*)&textures[i];
    }
    terrain_pixels(t[0],bytes,11,"content filled before initialize reaches GPU");
    terrain_fill(&t[1]->d,t[1]->mem,bytes,22);terrain_pixels(t[1],bytes,22,"unflushed first-use fill reaches GPU without polling");
    terrain_resolve(t[2]);terrain_check(!mtl_tex_gpu_owned(t[2]->serial),"render capability alone does not claim ownership");
    terrain_fill(&t[2]->d,t[2]->mem,bytes,33);nvn_ft_poll();terrain_pixels(t[2],bytes,33,"late CPU fill after empty resolution reaches GPU");
    terrain_fill(&t[2]->d,t[2]->mem,bytes,44);nvn_ft_poll();terrain_pixels(t[2],bytes,44,"second CPU fill refreshes every GPU texel");
    terrain_resolve(t[3]);terrain_clear(t[3]);terrain_check(mtl_tex_gpu_owned(t[3]->serial),"actual GPU clear claims ownership");
    terrain_fill(&t[3]->d,t[3]->mem,bytes,55);nvn_ft_poll();terrain_clear_pixels(t[3],bytes,"late CPU writes preserve GPU-owned content");
    // A compatible view/object over the same allocation must see that ownership.
    TERRAIN_API(nvnTextureBuilderSetStorage)(&builder,&pool,t[3]->off);TERRAIN_API(nvnTextureBuilderSetFlags)(&builder,NVN_TEXTURE_FLAGS_MINIMAL_LAYOUT);NVNtexture alias={0};if(!TERRAIN_API(nvnTextureInitialize)(&alias,&builder))abort();
    terrain_check(mtl_tex_gpu_owned(((tex_t*)&alias)->serial),"same-storage object observes GPU ownership");terrain_clear_pixels((tex_t*)&alias,bytes,"same-storage sampling preserves GPU contents");
    terrain_fill(&t[4]->d,t[4]->mem,bytes,66);terrain_pixels(t[4],bytes,66,"CPU stream begins before GPU target use");terrain_clear(t[4]);terrain_fill(&t[4]->d,t[4]->mem,bytes,77);nvn_ft_poll();terrain_clear_pixels(t[4],bytes,"CPU-backed image retains later GPU writes");
    terrain_resolve(t[5]);terrain_clear(t[5]);terrain_fill(&t[5]->d,t[5]->mem,bytes,88);nvn_ft_poll();terrain_check(mtl_tex_gpu_owned(t[5]->serial),"shader-writable image owns GPU storage");terrain_clear_pixels(t[5],bytes,"dirty polling preserves shader-writable storage");
    tex_t snapshot=*t[2];TERRAIN_API(nvnTextureFinalize)(&textures[2]);memset(&textures[2],0xa5,sizeof textures[2]);terrain_fill(&snapshot.d,snapshot.mem,bytes,99);mtl_tex_cpu_written(&snapshot);terrain_pixels(&snapshot,bytes,99,"finalized command snapshot retains CPU classification");
    uint64_t tracked=vk_tex_tracking_count();NVNtexture transient={0};
    for(unsigned i=0;i<2000;i++){if(!TERRAIN_API(nvnTextureInitialize)(&transient,&builder))abort();TERRAIN_API(nvnTextureFinalize)(&transient);}
    terrain_check(vk_tex_tracking_count()==tracked,"repeated unfilled texture finalization releases live identity records");
    for(unsigned i=0;i<6;i++)if(i!=2)TERRAIN_API(nvnTextureFinalize)(&textures[i]);TERRAIN_API(nvnTextureFinalize)(&alias);TERRAIN_API(nvnMemoryPoolFinalize)(&pool);
    terrain_check(!mtl_tex_gpu_owned(snapshot.serial),"pool cleanup retires ownership metadata");terrain_check(vk_tex_tracking_count()==0,"pool cleanup releases texture tracking records");munmap(mem,len);
}
static void terrain_real_captures(void) {
    const char *dir=getenv("DM_TERRAIN_CAPTURE_DIR");if(!dir){printf("terrain: real captured tiles not requested\n");return;}
    nvn_gob_switch2=1;const size_t len=2*1024*1024;uint8_t *mem=mmap(NULL,len,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0);if(mem==MAP_FAILED)abort();
    NVNmemoryPool pool={0};pool_builder_t pb={.mem=mem,.size=len,.flags=NVN_MEMORY_POOL_FLAGS_CPU_CACHED|NVN_MEMORY_POOL_FLAGS_GPU_CACHED};if(!TERRAIN_API(nvnMemoryPoolInitialize)(&pool,(const NVNmemoryPoolBuilder*)&pb))abort();
    for(unsigned i=0;i<8;i++){
        char path[1024],header[128],name[128];snprintf(path,sizeof path,"%s/height-%u.bin",dir,i);FILE *fp=fopen(path,"rb");if(!fp || !fgets(header,sizeof header,fp))abort();
        // Capture header stores MTLPixelFormatR16Unorm (20), not NVN_FORMAT_R16.
        unsigned w,h,format,row;if(sscanf(header,"%u %u %u %u",&w,&h,&format,&row)!=4 || w!=260 || h!=260 || format!=20 || row<w*2)abort();
        uint8_t *expected=malloc((size_t)row*h),*actual=malloc((size_t)w*h*2);if(fread(expected,row,h,fp)!=h)abort();fclose(fp);
        NVNtextureBuilder builder;TERRAIN_API(nvnTextureBuilderSetDefaults)(&builder);TERRAIN_API(nvnTextureBuilderSetWidth)(&builder,(int)w);TERRAIN_API(nvnTextureBuilderSetHeight)(&builder,(int)h);TERRAIN_API(nvnTextureBuilderSetFormat)(&builder,NVN_FORMAT_R16);TERRAIN_API(nvnTextureBuilderSetFlags)(&builder,NVN_TEXTURE_FLAGS_MINIMAL_LAYOUT);TERRAIN_API(nvnTextureBuilderSetStorage)(&builder,&pool,1048576);
        nvn_texlayout layout;nvn_tex_layout(&((tex_builder_t*)&builder)->d,&layout);if(layout.size!=152064)abort();
        snprintf(path,sizeof path,"%s/height-%u-source.bin",dir,i);fp=fopen(path,"rb");if(!fp)abort();dm_guest_write_prepare(mem+1048576,layout.size);if(fread(mem+1048576,1,layout.size,fp)!=layout.size || fgetc(fp)!=EOF)abort();fclose(fp);
        NVNtexture texture={0};if(!TERRAIN_API(nvnTextureInitialize)(&texture,&builder))abort();NVNcopyRegion region={0,0,0,(int)w,(int)h,1};mtl_read_texels((tex_t*)&texture,0,0,&region,actual,w*2,(size_t)w*h*2);
        int ok=1;for(unsigned y=0;y<h;y++)ok&=!memcmp(actual+(size_t)y*w*2,expected+(size_t)y*row,w*2);snprintf(name,sizeof name,"captured Mac height tile %u matches all 67600 Vulkan texels",i);terrain_check(ok,name);
        // The production texture descriptor and sampling shader must see the
        // same heights, including an array view of the game's ordinary 2D tile.
        uint8_t *job=mem+65536;AtlasQuery *query=(AtlasQuery*)(mem+262144);
        static const unsigned points[8][2]={{0,0},{259,259},{259,0},{0,259},{130,130},{17,251},{251,17},{31,32}};
        for(unsigned j=0;j<8;j++)query[j]=(AtlasQuery){.x=(int)points[j][0],.y=(int)points[j][1]};
        mtl_sub_begin();atlas_record(job,(tex_t*)&texture,NULL,0,query,8);if(!mtl_wait(mtl_sub_commit(),10000000000ull))abort();
        float *sampled=(float*)(job+4096);ok=1;for(unsigned j=0;j<8;j++){uint16_t value;memcpy(&value,expected+(size_t)points[j][1]*row+points[j][0]*2,2);ok&=fabsf(sampled[j*4]-value/65535.0f)<0.00001f && sampled[j*4+1]==0 && sampled[j*4+2]==0 && sampled[j*4+3]==1;}
        snprintf(name,sizeof name,"captured Mac height tile %u shader samples match reference",i);terrain_check(ok,name);
        TERRAIN_API(nvnTextureFinalize)(&texture);free(expected);free(actual);
    }
    TERRAIN_API(nvnMemoryPoolFinalize)(&pool);terrain_check(vk_tex_tracking_count()==0,"captured tile pool releases tracking records");munmap(mem,len);
}
static void terrain_tests(void) {
    terrain_check(DM_GAME_TEX_FLUSH_UPLOAD && DM_GAME_TEX_DIRTY_UPLOAD,"CPU-stream profile enabled");
    for(int gob=0;gob<2;gob++){terrain_case(NVN_FORMAT_R16,2,gob);terrain_case(NVN_FORMAT_RG16,4,gob);terrain_case(NVN_FORMAT_R8,1,gob);}
    terrain_real_captures();
}
#undef TERRAIN_API
