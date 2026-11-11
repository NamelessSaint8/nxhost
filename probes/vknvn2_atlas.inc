// Real NVN mapping APIs -> production shader rewrite/descriptors/cache -> pixels.
#include "nvn_count.h"
#include "nvn_protos.h"
#include "../nxnative/dm/gfx/tex/nvn_deswizzle.h"
#include <math.h>
static void *atlas_api(const char *name) {
    extern const char *nvn_names[NVN_NFUNC];extern void *nvn_big_real[NVN_NFUNC];
    extern struct { _Atomic uint64_t count; void *fn; } nvn_slot[NVN_NFUNC];
    for(unsigned i=0;i<NVN_NFUNC;i++)if(!strcmp(name,nvn_names[i]))return nvn_big_real[i]?nvn_big_real[i]:nvn_slot[i].fn;
    abort();
}
typedef struct { NVNmemoryPool *physical; int64_t source,target; uint64_t size; int32_t storage,pad; } AtlasMapping;
typedef struct { float u,v,lod,layer; int32_t x,y,mode,mip; } AtlasQuery;
static unsigned atlas_width=8192,atlas_height=4096,atlas_layers=68;
static unsigned atlas_tw,atlas_th,atlas_tail,atlas_format;
static unsigned atlas_physical_flags=0x24;
static int atlas_phase,atlas_expanded,atlas_wrap,atlas_nearest,atlas_no_mips,atlas_negative,atlas_first_seed=-1;
static float atlas_min_lod,atlas_max_lod=1000;
static unsigned atlas_nonce,atlas_expanded_count;
static unsigned atlas_shader_key=11;
static float atlas_colors[4][4];
static void atlas_check(int condition,const char *name) { checks++;failed+=!condition;printf("mapped atlas %s %s\n",name,condition?"PASS":"FAIL"); }
static void atlas_block(uint8_t block[16],unsigned color) {
    memset(block,0,16);
    if(atlas_format==0){block[0]=3;for(unsigned endpoint=0;endpoint<2;endpoint++)for(unsigned c=0;c<3;c++){unsigned value=c==color?(c==0?528:495):0;for(unsigned bit=0;bit<10;bit++)if(value>>bit&1){unsigned pos=5+(endpoint*3+c)*10+bit;block[pos/8]|=(uint8_t)(1u<<(pos%8));}}memcpy(block+12,&atlas_nonce,4);}
    else {const uint8_t header[16]={0xfc,0xfd,0xff,0xff,0xff,0xff,0xff,0xff,0,0,0,0,0,0,255,255};memcpy(block,header,16);if(color<3)block[8+2*color]=block[9+2*color]=255;else for(unsigned c=8;c<14;c++)block[c]=128;block[8]^=(uint8_t)atlas_nonce;}
}
static unsigned atlas_pattern(unsigned x,unsigned y,unsigned seed,unsigned mip) { unsigned block=atlas_format==2?8:4;return ((x/block)*3+(y/block)*5+seed+mip)%4; }
static void atlas_fill(const tex_t *t,uint8_t *destination,unsigned seed,int tail) {
    uint8_t *linear=malloc(65536);memset(destination,0,65536);
    for(unsigned mip=tail?atlas_tail:0;mip<(tail?t->d.levels:1);mip++){
        uint32_t w=tail?atlas_width>>mip:atlas_tw,h=tail?atlas_height>>mip:atlas_th;if(!w)w=1;if(!h)h=1;
        unsigned block=atlas_format==2?8:4;size_t pitch=((w+block-1)/block)*16;
        for(unsigned by=0;by<(h+block-1)/block;by++)for(unsigned bx=0;bx<(w+block-1)/block;bx++)atlas_block(linear+by*pitch+bx*16,atlas_pattern(bx*block,by*block,seed,mip));
        unsigned sh,sd;nvn_tex_level_tiles(&t->d,mip,&sh,&sd);nvn_texdesc local=t->d;local.target=NVN_TEXTURE_TARGET_2D;local.flags=0;local.width=w;local.height=h;local.depth=local.levels=1;local.pkg_block_h=(int)sh+1;
        uint64_t offset=tail?nvn_tex_level_offset(&t->d,mip)-nvn_tex_level_offset(&t->d,atlas_tail):0;
        if(nvn_swizzle(&local,0,0,linear,pitch,destination+offset))abort();
    }free(linear);
}
static void atlas_reference_fetch(int x,int y,int layer,int mip,const view_t *v,float out[4]) {
    unsigned first=v && v->set_levels?v->base_level:0;unsigned base_layer=v && v->set_layers?v->min_layer:0;
    unsigned original_mip=(unsigned)mip+first,original_layer=(unsigned)layer+base_layer;
    unsigned w=atlas_width>>original_mip,h=atlas_height>>original_mip;if(!w)w=1;if(!h)h=1;
    if(atlas_wrap){x=(x%(int)w+(int)w)%(int)w;y=(y%(int)h+(int)h)%(int)h;}
    if(x<0)x=0;if(y<0)y=0;if(x>=(int)w)x=(int)w-1;if(y>=(int)h)y=(int)h-1;
    int seed=-1;
    if(original_mip>=atlas_tail && original_layer==67)seed=2;
    else if(original_mip==0 && y<(int)atlas_th){if(original_layer==1 && x<(int)atlas_tw)seed=0;
        if(original_layer==0 && x<(int)atlas_tw)seed=atlas_phase==0 || atlas_phase==4?0:atlas_phase==1?3:atlas_phase==3?-1:4;
        if(original_layer==0 && x>=(int)atlas_tw && x<(int)atlas_tw*2)seed=1;}
    if(atlas_expanded && original_mip==0 && original_layer==0 && ((unsigned)y/atlas_th)*(atlas_width/atlas_tw)+(unsigned)x/atlas_tw<atlas_expanded_count)seed=x>=(int)atlas_tw && x<2*(int)atlas_tw?1:4;
    if(atlas_expanded && atlas_first_seed>=0 && original_mip==0 && original_layer==0 && x<(int)atlas_tw && y<(int)atlas_th)seed=atlas_first_seed;
    if(seed<0){memset(out,0,16);if(!atlas_format)out[3]=1;}
    else memcpy(out,atlas_colors[atlas_pattern((unsigned)x%atlas_tw,(unsigned)y%atlas_th,(unsigned)seed,original_mip)],16);
    if(v && v->set_swizzle){float old[4];memcpy(old,out,16);for(unsigned c=0;c<4;c++)out[c]=v->swz[c]==0?0:v->swz[c]==1?1:old[v->swz[c]-2];}
}
static void atlas_reference(AtlasQuery q,const view_t *v,float out[4]) {
    unsigned first=v && v->set_levels?v->base_level:0,levels=v && v->set_levels?v->nlevels:12-first,layers=v && v->set_layers?v->nlayers:atlas_layers;
    if(q.mode==2){out[0]=(float)(atlas_width>>(q.mip+first));out[1]=(float)(atlas_height>>(q.mip+first));if(!out[0])out[0]=1;if(!out[1])out[1]=1;out[2]=(float)layers;out[3]=(float)levels;return;}
    if(q.mode==0){atlas_reference_fetch(q.x,q.y,(int)q.layer,q.mip,v,out);return;}
    memset(out,0,16);float lod=fminf(fmaxf(q.lod,atlas_min_lod),atlas_max_lod);lod=fminf(fmaxf(lod,0),levels-1);if(atlas_no_mips)lod=0;
    if(atlas_nearest){int mip=(int)floorf(lod+.5f);unsigned w=atlas_width>>(mip+first),h=atlas_height>>(mip+first);if(!w)w=1;if(!h)h=1;atlas_reference_fetch((int)floorf(q.u*w),(int)floorf(q.v*h),(int)floorf(q.layer+.5f),mip,v,out);return;}unsigned lo=(unsigned)floorf(lod);float t=lod-lo;
    for(unsigned part=0;part<2;part++){unsigned mip=lo+part;if(mip>=levels)mip=levels-1;unsigned w=atlas_width>>(mip+first),h=atlas_height>>(mip+first);if(!w)w=1;if(!h)h=1;
        float px=q.u*w-.5f,py=q.v*h-.5f,fx=px-floorf(px),fy=py-floorf(py);int x=(int)floorf(px),y=(int)floorf(py);
        for(int dy=0;dy<2;dy++)for(int dx=0;dx<2;dx++){float value[4];atlas_reference_fetch(x+dx,y+dy,(int)floorf(q.layer+.5f),(int)mip,v,value);float weight=(part?t:1-t)*(dx?fx:1-fx)*(dy?fy:1-fy);for(unsigned c=0;c<4;c++)out[c]+=weight*value[c];}}
}
static void atlas_record(uint8_t *job,const tex_t *t,const view_t *v,unsigned phase,AtlasQuery *query,unsigned n) {
    mtl_reg_tex(101,t,v);prog_t program={.nstage=1,.serial=9000+phase};program.sd[0].data=atlas_shader_key;
    size_t used=0;
#define PUT(OP,X) do { size_t bytes=(8+sizeof(X)+7)&~7ull;op_hdr h={OP,(uint32_t)bytes};memcpy(job+used,&h,8);memcpy(job+used+8,&(X),sizeof(X));used+=bytes; } while(0)
    p_bind_program bind={&program,0xff};PUT(OP_BIND_PROGRAM,bind);
    p_bind_handles texture={.stage=5,.n=atlas_shader_key==28?2:1};texture.h[0]=101u|(1u<<20);texture.h[1]=102u|(1u<<20);PUT(OP_BIND_TEX,texture);
    p_bind_buf out={.stage=5,.index=0,.addr=atlas_negative==3?(uint64_t)(uintptr_t)t->mem:(uint64_t)(job+4096+phase*512),.size=n*16*(atlas_shader_key==28?2:1)};PUT(OP_BIND_SSBO,out);
    p_bind_buf input={.stage=5,.index=1,.addr=(uint64_t)query,.size=n*sizeof *query};PUT(OP_BIND_SSBO,input);
    p_dispatch dispatch={.x=(int)(n+31)/32,.y=1,.z=1};PUT(OP_DISPATCH,dispatch);
    op_hdr end={OP_END,8};memcpy(job+used,&end,8);
#undef PUT
    mtl_exec(job);
}
static void atlas_verify(uint8_t *job,unsigned phase,const AtlasQuery *query,unsigned n,const view_t *view) {
    const float *actual=(const float*)(job+4096+phase*512);for(unsigned i=0;i<n;i++){float expected[4];atlas_reference(query[i],view,expected);int ok=1;for(unsigned c=0;c<4;c++)ok&=fabsf(actual[4*i+c]-expected[c])<.03f;
        checks++;failed+=!ok;printf("mapped atlas format=%u gob=%d phase=%u query=%u %s rgba=%.4f,%.4f,%.4f,%.4f expected=%.4f,%.4f,%.4f,%.4f\n",atlas_format,nvn_gob_switch2,phase,i,ok?"PASS":"FAIL",actual[4*i],actual[4*i+1],actual[4*i+2],actual[4*i+3],expected[0],expected[1],expected[2],expected[3]);}
}
static void atlas_case(unsigned format,int gob) {
    atlas_format=format;atlas_expanded=atlas_wrap=atlas_nearest=atlas_no_mips=0;atlas_first_seed=-1;atlas_min_lod=0;atlas_max_lod=1000;atlas_nonce=0;atlas_height=format==0?8192:4096;nvn_gob_switch2=gob;memset(atlas_colors,0,sizeof atlas_colors);for(unsigned c=0;c<4;c++)atlas_colors[c][3]=1;
    atlas_colors[0][0]=format?1:2;atlas_colors[1][1]=atlas_colors[2][2]=1;if(format)for(unsigned c=0;c<3;c++)atlas_colors[3][c]=format==2?powf((128.f/255+.055f)/1.055f,2.4f):128.f/255;
    tex_t t={.magic=MAGIC('T','E','X',0),.serial=15000+format*10+(unsigned)gob};
    t.d=(nvn_texdesc){.target=NVN_TEXTURE_TARGET_2D_ARRAY,.format=format==0?NVN_FORMAT_BPTC_UFLOAT:format==1?NVN_FORMAT_RGBA_ASTC_4x4:NVN_FORMAT_RGBA_ASTC_8x8_SRGB,.flags=NVN_TEXTURE_FLAGS_SPARSE,.width=atlas_width,.height=atlas_height,.depth=atlas_layers,.levels=12,.samples=1};
    nvn_tex_layout(&t.d,&t.L);uint32_t td;atlas_tail=nvn_tex_sparse_tiles(&t.d,&atlas_tw,&atlas_th,&td);
    uint8_t *source=mmap(NULL,164*65536,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0),*job=mmap(NULL,65536,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0);if(source==MAP_FAILED || job==MAP_FAILED)abort();
    for(unsigned page=0;page<4;page++)atlas_fill(&t,source+page*65536,page,page==2);
    for(unsigned page=4;page<164;page++){atlas_nonce=page;atlas_fill(&t,source+page*65536,(page-4)%(atlas_width/atlas_tw)==1?1:4,0);}
    atlas_nonce=0;
    NVNT_nvnMemoryPoolInitialize init=atlas_api("nvnMemoryPoolInitialize");NVNT_nvnMemoryPoolFinalize finalize=atlas_api("nvnMemoryPoolFinalize");NVNT_nvnMemoryPoolMapVirtual map=atlas_api("nvnMemoryPoolMapVirtual");
    uint64_t memory_before,peak_before,count_before;vk_memory_stats(&memory_before,&peak_before,&count_before);
    pool_t physical,virtual;pool_builder_t pb={.mem=source,.size=164*65536,.flags=atlas_physical_flags};if(!init((NVNmemoryPool*)&physical,(NVNmemoryPoolBuilder*)&pb))abort();
    if(atlas_physical_flags&NVN_MEMORY_POOL_FLAGS_GPU_NO_ACCESS){uint64_t after,peak,count;vk_memory_stats(&after,&peak,&count);vkpool_t *registered=vk_pool_of((uint64_t)source,164*65536);
        atlas_check(after==memory_before && count==count_before,"GPU_NO_ACCESS physical storage adds no Vulkan allocation");
        atlas_check(registered && !registered->buf && physical.mem==source,"CPU physical storage preserves canonical bytes and identity");}
    t.off=0x800000000ll;pb=(pool_builder_t){.size=t.off+t.L.size+65536,.flags=0x200};if(!init((NVNmemoryPool*)&virtual,(NVNmemoryPoolBuilder*)&pb))abort();t.pool=&virtual;t.mem=(uint8_t*)((uintptr_t)virtual.mem+t.off);
    uint64_t tail=67*t.L.layer_size+nvn_tex_level_offset(&t.d,atlas_tail);
    AtlasMapping mappings[4]={{(NVNmemoryPool*)&physical,0,t.off,65536,0,0},{(NVNmemoryPool*)&physical,65536,t.off+65536,65536,0,0},{(NVNmemoryPool*)&physical,0,t.off+(int64_t)t.L.layer_size,65536,0,0},{(NVNmemoryPool*)&physical,2*65536,t.off+(int64_t)tail,65536,0,0}};
    if(atlas_negative==1)mappings[0].size=4096;
    atlas_check(map((NVNmemoryPool*)&virtual,4,(NVNmappingRequest*)mappings),"real NVN virtual mappings accepted");mtl_pool_add(job,65536);
    samp_par sampler={.minf=5,.magf=1,.aniso=2,.lod_max=1000};mtl_reg_samp(1,&sampler);
    AtlasQuery *q=(AtlasQuery*)(job+16384);unsigned n=0;
    q[n++]=(AtlasQuery){.x=17,.y=29};q[n++]=(AtlasQuery){.x=(int)atlas_tw+23,.y=37};q[n++]=(AtlasQuery){.layer=1,.x=17,.y=29};q[n++]=(AtlasQuery){.x=3*(int)atlas_tw,.y=29};
    q[n++]=(AtlasQuery){.u=(float)atlas_tw/atlas_width,.v=32.5f/atlas_height,.mode=1};q[n++]=(AtlasQuery){.u=(float)atlas_tw/atlas_width,.v=32.5f/atlas_height,.lod=.5f,.mode=1};
    q[n++]=(AtlasQuery){.layer=67,.x=5,.y=7,.mip=(int)atlas_tail};q[n++]=(AtlasQuery){.layer=67,.x=0,.y=0,.mip=11};q[n++]=(AtlasQuery){.layer=66,.mip=(int)atlas_tail};
    q[n++]=(AtlasQuery){.u=.61f,.v=.22f,.layer=67,.lod=(float)atlas_tail+.4f,.mode=1};q[n++]=(AtlasQuery){.mode=2,.mip=2};q[n++]=(AtlasQuery){.u=-1,.v=-1,.mode=1};
    q[n++]=(AtlasQuery){.x=(int)(atlas_width-atlas_tw+17),.y=(int)(4*atlas_th+29)};
    mtl_sub_begin();
    for(unsigned phase=0;phase<5;phase++){
        if(phase){AtlasMapping change={(NVNmemoryPool*)&physical,phase==4?0:3*65536,t.off,65536,0,0};if(phase==3)change.physical=NULL;
            if(phase==2){atlas_nonce=17;dm_guest_write_prepare(source+3*65536,65536);atlas_fill(&t,source+3*65536,4,0);}
            if(!map((NVNmemoryPool*)&virtual,1,(NVNmappingRequest*)&change))abort();}
        atlas_record(job,&t,NULL,phase,q,n);
    }
    // A production texture-copy record must update the physical BC/ASTC bytes,
    // including an aliased layer, without making the giant logical image.
    tex_t copy_source=t;copy_source.serial=24000+format*10+(unsigned)gob;copy_source.pool=&physical;copy_source.off=3*65536;copy_source.mem=source+copy_source.off;
    unsigned copy_sh,copy_sd;nvn_tex_level_tiles(&t.d,0,&copy_sh,&copy_sd);copy_source.d.target=NVN_TEXTURE_TARGET_2D;copy_source.d.width=atlas_tw;copy_source.d.height=atlas_th;copy_source.d.depth=copy_source.d.levels=1;copy_source.d.flags=0;copy_source.d.pkg_block_h=(int)copy_sh+1;nvn_tex_layout(&copy_source.d,&copy_source.L);
    p_copy_t2t copy={.src=&copy_source,.dst=&t,.sr={0,0,0,(int)atlas_tw,(int)atlas_th,1},.dr={0,0,0,(int)atlas_tw,(int)atlas_th,1}};
    uint8_t copy_job[sizeof copy+32]={0};size_t copy_size=(8+sizeof copy+7)&~7ull;op_hdr copy_header={OP_COPY_T2T,(uint32_t)copy_size};memcpy(copy_job,&copy_header,8);memcpy(copy_job+8,&copy,sizeof copy);copy_header=(op_hdr){OP_END,8};memcpy(copy_job+copy_size,&copy_header,8);mtl_exec(copy_job);
    atlas_record(job,&t,NULL,15,q,n);
    // The copy version remains live until this batch's fence even though its
    // native physical bytes are restored before later draws are encoded.
    dm_guest_write_prepare(source,65536);atlas_fill(&t,source,0,0);
    atlas_expanded_count=(atlas_width/atlas_tw)*(atlas_height/atlas_th);if(atlas_expanded_count>160)atlas_expanded_count=160;
    AtlasMapping expanded[160];for(unsigned i=0;i<atlas_expanded_count;i++)expanded[i]=(AtlasMapping){(NVNmemoryPool*)&physical,(int64_t)(i+4)*65536,t.off+(int64_t)i*65536,65536,0,0};
    if(!map((NVNmemoryPool*)&virtual,(int)atlas_expanded_count,(NVNmappingRequest*)expanded))abort();
    atlas_record(job,&t,NULL,6,q,n);
    // Multiple revisions in one unsubmitted batch must protect newly added
    // cells even when the packed image has spare capacity and does not grow.
    for(unsigned seed=1;seed<=2;seed++){
        atlas_nonce=seed+20;dm_guest_write_prepare(source+3*65536,65536);atlas_fill(&t,source+3*65536,seed,0);
        AtlasMapping change={(NVNmemoryPool*)&physical,3*65536,t.off,65536,0,0};if(!map((NVNmemoryPool*)&virtual,1,(NVNmappingRequest*)&change))abort();atlas_record(job,&t,NULL,12+seed,q,n);
    }atlas_nonce=0;
    uint64_t fence=mtl_sub_commit();if(!mtl_wait(fence,10000000000ull))abort();
    for(unsigned phase=0;phase<5;phase++){atlas_phase=(int)phase;atlas_verify(job,phase,q,n,NULL);}
    for(unsigned i=0;i<2;i++){unsigned qi=i?2:0;const float *actual=(const float*)(job+4096+15*512)+qi*4;const float *want=atlas_colors[atlas_pattern((unsigned)q[qi].x,(unsigned)q[qi].y,4,0)];int ok=1;for(unsigned c=0;c<4;c++)ok&=fabsf(actual[c]-want[c])<.03f;atlas_check(ok,i?"compressed copy updates physical alias":"compressed copy preserves prior GPU versions");}
    atlas_expanded=1;atlas_phase=6;atlas_verify(job,6,q,n,NULL);
    for(unsigned seed=1;seed<=2;seed++){atlas_first_seed=(int)seed;atlas_verify(job,12+seed,q,n,NULL);}atlas_first_seed=-1;
    AtlasMapping restore={(NVNmemoryPool*)&physical,4*65536,t.off,65536,0,0};if(!map((NVNmemoryPool*)&virtual,1,(NVNmappingRequest*)&restore))abort();
    if(format==0 && gob==1){uint64_t before,up,re,meta;vk_atlas_stats(&before,&up,&re,&meta);
        for(unsigned i=0;i<80;i++){atlas_nonce=40+i;dm_guest_write_prepare(source+3*65536,65536);atlas_fill(&t,source+3*65536,4,0);AtlasMapping update={(NVNmemoryPool*)&physical,3*65536,t.off,65536,0,0};if(!map((NVNmemoryPool*)&virtual,1,(NVNmappingRequest*)&update))abort();
            mtl_sub_begin();atlas_record(job,&t,NULL,7,q,1);fence=mtl_sub_commit();if(!mtl_wait(fence,10000000000ull))abort();atlas_phase=2;atlas_verify(job,7,q,1,NULL);}
        uint64_t after;vk_atlas_stats(&after,&up,&re,&meta);atlas_check(after==before,"retired cells bound backing across eighty distinct updates");}
    // After completion old cells can be recycled; view-relative mips/layers and
    // swizzles still refer to the original atlas, not packed physical dimensions.
    view_t view={.set_levels=1,.set_layers=1,.set_swizzle=1,.base_level=(uint8_t)atlas_tail,.nlevels=(uint8_t)(12-atlas_tail),.min_layer=67,.nlayers=1,.swz={4,3,2,5}};
    q[0]=(AtlasQuery){.x=5,.y=7};q[1]=(AtlasQuery){.mip=(int)(11-atlas_tail)};q[2]=(AtlasQuery){.mode=2};q[3]=(AtlasQuery){.u=.61f,.v=.22f,.lod=.4f,.mode=1};
    mtl_sub_begin();atlas_record(job,&t,&view,5,q,4);fence=mtl_sub_commit();if(!mtl_wait(fence,10000000000ull))abort();atlas_phase=4;atlas_verify(job,5,q,4,&view);
    q[0]=(AtlasQuery){.u=-.01f,.v=.01f,.lod=.4f,.mode=1};q[1]=(AtlasQuery){.u=1.01f,.v=-.01f,.lod=.75f,.mode=1};q[2]=(AtlasQuery){.u=-.5f,.v=-.5f,.lod=20,.mode=1};q[3]=(AtlasQuery){.mode=2};
    for(unsigned mode=0;mode<4;mode++){
        atlas_wrap=1;atlas_nearest=mode==1;atlas_no_mips=mode==3;atlas_min_lod=mode==2?1.25f:0;atlas_max_lod=mode==2?2.5f:1000;
        sampler.ws=sampler.wt=1;sampler.minf=mode==1?2:mode==3?1:5;sampler.magf=mode==1?0:1;sampler.lod_min=atlas_min_lod;sampler.lod_max=atlas_max_lod;mtl_reg_samp(1,&sampler);
        mtl_sub_begin();atlas_record(job,&t,&view,8+mode,q,4);fence=mtl_sub_commit();if(!mtl_wait(fence,10000000000ull))abort();atlas_verify(job,8+mode,q,4,&view);
    }
    if(format==0 && gob==1){uint64_t bytes,up,re,meta;vk_atlas_sweep(180);vk_atlas_stats(&bytes,&up,&re,&meta);atlas_check(bytes==0,"idle atlas eviction releases cache and transfer staging");
        mtl_sub_begin();atlas_record(job,&t,&view,12,q,4);fence=mtl_sub_commit();if(!mtl_wait(fence,10000000000ull))abort();atlas_verify(job,12,q,4,&view);}
    uint64_t allocated,uploaded,reused,metadata;vk_atlas_stats(&allocated,&uploaded,&reused,&metadata);printf("mapped atlas allocation=%llu uploaded=%llu cell-reuses=%llu metadata=%llu logical=%llu\n",(unsigned long long)allocated,(unsigned long long)uploaded,(unsigned long long)reused,(unsigned long long)metadata,(unsigned long long)t.L.size);
    atlas_check(allocated<32u*1024*1024,"multi-GiB atlas allocates mapped compressed cells only");atlas_check(reused>0,"unchanged/aliased content reuses cells");
    finalize((NVNmemoryPool*)&virtual);finalize((NVNmemoryPool*)&physical);mtl_pool_del(job);munmap(job,65536);munmap(source,164*65536);
    vk_atlas_stats(&allocated,&uploaded,&reused,&metadata);atlas_check(allocated==0,"pool finalization releases atlas backing");
}
static void atlas_dense(void) {
    uint8_t *source=mmap(NULL,65536,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0),*job=mmap(NULL,65536,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0);if(source==MAP_FAILED || job==MAP_FAILED)abort();
    for(unsigned i=0;i<65536;i+=4){source[i]=0;source[i+1]=255;source[i+2]=0;source[i+3]=255;}
    pool_t physical;pool_builder_t pb={.mem=source,.size=65536,.flags=0x24};NVNT_nvnMemoryPoolInitialize init=atlas_api("nvnMemoryPoolInitialize");NVNT_nvnMemoryPoolFinalize finalize=atlas_api("nvnMemoryPoolFinalize");if(!init((NVNmemoryPool*)&physical,(NVNmemoryPoolBuilder*)&pb))abort();
    tex_t t={.magic=MAGIC('T','E','X',0),.serial=20000,.has_layout=1,.pool=&physical,.mem=source};t.d=(nvn_texdesc){.target=NVN_TEXTURE_TARGET_2D_ARRAY,.format=NVN_FORMAT_RGBA8,.width=8,.height=4,.depth=2,.levels=1,.samples=1};nvn_tex_layout(&t.d,&t.L);
    mtl_pool_add(job,65536);AtlasQuery *q=(AtlasQuery*)(job+16384);q[0]=(AtlasQuery){.u=.5f,.v=.5f,.layer=1,.mode=1};q[1]=(AtlasQuery){.mode=2};
    samp_par sampler={.minf=5,.magf=1,.aniso=4,.ws=6,.wt=6,.lod_max=1000};mtl_reg_samp(1,&sampler);
    mtl_sub_begin();atlas_record(job,&t,NULL,0,q,2);uint64_t fence=mtl_sub_commit();if(!mtl_wait(fence,10000000000ull))abort();
    float *result=(float*)(job+4096);atlas_check(result[0]==0 && result[1]==1 && result[2]==0 && result[3]==1,"ordinary dense sampling keeps native sampler modes");atlas_check(result[4]==8 && result[5]==4 && result[6]==2 && result[7]==1,"ordinary dense size queries keep logical dimensions");
    finalize((NVNmemoryPool*)&physical);mtl_pool_del(job);munmap(job,65536);munmap(source,65536);
}
static void atlas_tests(void){for(unsigned format=0;format<3;format++)for(int gob=0;gob<2;gob++)atlas_case(format,gob);atlas_dense();}
