// Page-table sampling also covers native uncompressed CPU arrays. The shader
// samples mapped pages, aliases, whole holes and holes inside a 64 KiB cell.
extern uint64_t nvn_sparse_copy(const void *,void *,uint64_t,uint64_t);
static void uncompressed_case(unsigned format,int gob,int arrayed){
    nvn_gob_switch2=gob;tex_t t={.magic=MAGIC('T','E','X',0),.serial=41000+format*10+(unsigned)gob};t.d=(nvn_texdesc){.width=4096,.height=4096,.depth=arrayed?3:1,.levels=1,.samples=1,.target=arrayed?NVN_TEXTURE_TARGET_2D_ARRAY:NVN_TEXTURE_TARGET_2D,.format=format,.flags=NVN_TEXTURE_FLAGS_SPARSE};nvn_tex_layout(&t.d,&t.L);
    uint32_t tw,th,td;nvn_tex_sparse_tiles(&t.d,&tw,&th,&td);const vkfmt_t *f=vk_fmt(format);unsigned bpp=f->bpb;
    uint8_t *source=mmap(NULL,2*65536,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0),*job=mmap(NULL,65536,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0);if(source==MAP_FAILED || job==MAP_FAILED)abort();
    NVNT_nvnMemoryPoolInitialize init=atlas_api("nvnMemoryPoolInitialize");NVNT_nvnMemoryPoolFinalize fini=atlas_api("nvnMemoryPoolFinalize");NVNT_nvnMemoryPoolMapVirtual map=atlas_api("nvnMemoryPoolMapVirtual");
    pool_t physical,virtual;pool_builder_t pb={.mem=source,.size=2*65536,.flags=0x18c};if(!init((NVNmemoryPool*)&physical,(NVNmemoryPoolBuilder*)&pb))abort();t.off=65536;pb=(pool_builder_t){.size=t.off+t.L.size+65536,.flags=0x200};if(!init((NVNmemoryPool*)&virtual,(NVNmemoryPoolBuilder*)&pb))abort();t.pool=&virtual;t.mem=virtual.mem+t.off;
    AtlasMapping mappings[3]={{(NVNmemoryPool*)&physical,0,t.off,65536,0,0},{(NVNmemoryPool*)&physical,65536,t.off+65536,65536,0,0},{(NVNmemoryPool*)&physical,0,t.off+(int64_t)t.L.layer_size,65536,0,0}};
    unsigned sh,sd;nvn_tex_level_tiles(&t.d,0,&sh,&sd);nvn_texdesc local=t.d;local.target=NVN_TEXTURE_TARGET_2D;local.flags=0;local.width=tw;local.height=th;local.depth=local.levels=1;local.pkg_block_h=(int)sh+1;
    uint8_t *linear=malloc(65536),*expected=malloc(65536),*gathered=malloc(65536);mtl_pool_add(job,65536);samp_par sampler={.minf=0,.magf=0,.aniso=1,.ws=NVN_WRAP_MODE_CLAMP_TO_EDGE,.wt=NVN_WRAP_MODE_CLAMP_TO_EDGE,.lod_max=1000};mtl_reg_samp(1,&sampler);
    AtlasQuery *q=(AtlasQuery*)(job+16384);unsigned n=0;q[n++]=(AtlasQuery){.x=0,.y=0};q[n++]=(AtlasQuery){.x=(int)tw-1,.y=(int)th-1};q[n++]=(AtlasQuery){.x=(int)tw+3,.y=7};q[n++]=(AtlasQuery){.x=(int)tw*3,.y=7};q[n++]=(AtlasQuery){.x=17,.y=29,.layer=1};q[n++]=(AtlasQuery){.x=17,.y=29,.layer=2};q[n++]=(AtlasQuery){.u=-1,.v=-1,.mode=1};q[n++]=(AtlasQuery){.mode=2};
    if(!arrayed){q[4].layer=0;q[5].layer=0;q[5].x=(int)tw*3;}atlas_shader_key=arrayed?11:27;
    for(unsigned phase=0;phase<3;phase++){
        for(unsigned page=0;page<2;page++){
            unsigned seed=7+page*31+phase*13;for(unsigned y=0;y<th;y++)for(unsigned x=0;x<tw;x++){
                uint8_t *p=linear+((size_t)y*tw+x)*bpp;
                if(format==NVN_FORMAT_R16 || format==NVN_FORMAT_RG16){for(unsigned c=0;c<bpp/2;c++){uint16_t v=(uint16_t)(x*31+y*79+seed+c*997);memcpy(p+c*2,&v,2);}}
                else for(unsigned c=0;c<4;c++)p[c]=format==NVN_FORMAT_RGBA8SN?(uint8_t)(int8_t)((int)((x*3+y*5+seed+c*37)%255)-127):(uint8_t)(x*3+y*5+seed+c*37);
            }
            dm_guest_write_prepare(source+page*65536,65536);memset(source+page*65536,0,65536);if(nvn_swizzle(&local,0,0,linear,(size_t)tw*bpp,source+page*65536))abort();
        }
        if(!map((NVNmemoryPool*)&virtual,3,(NVNmappingRequest*)mappings))abort();
        if(phase==2){AtlasMapping hole={NULL,0,t.off+4096,65536-4096,0,0};if(!map((NVNmemoryPool*)&virtual,1,(NVNmappingRequest*)&hole))abort();}
        mtl_sub_begin();atlas_record(job,&t,NULL,phase,q,n);if(!mtl_wait(mtl_sub_commit(),10000000000ull))abort();float *actual=(float*)(job+4096+phase*512);
        for(unsigned i=0;i<n;i++){
            float want[4]={0,0,0,0};if(format==NVN_FORMAT_R16 || format==NVN_FORMAT_RG16)want[3]=1;
            if(q[i].mode==2){want[0]=4096;want[1]=4096;want[2]=arrayed?3:0;want[3]=1;}
            else{unsigned x=q[i].mode==1?0:(unsigned)q[i].x,y=q[i].mode==1?0:(unsigned)q[i].y,layer=(unsigned)q[i].layer;uint64_t tile=(uint64_t)layer*t.L.layer_size+((uint64_t)(y/th)*(4096/tw)+x/tw)*65536;
                nvn_sparse_copy(t.pool,gathered,(uint64_t)(uintptr_t)t.mem+tile,65536);if(nvn_deswizzle(&local,0,0,gathered,expected,(size_t)tw*bpp))abort();uint8_t *p=expected+((size_t)(y%th)*tw+x%tw)*bpp;
                if(format==NVN_FORMAT_R16 || format==NVN_FORMAT_RG16){for(unsigned c=0;c<bpp/2;c++){uint16_t v;memcpy(&v,p+c*2,2);want[c]=v/65535.f;}}
                else for(unsigned c=0;c<4;c++)want[c]=format==NVN_FORMAT_RGBA8SN?fmaxf(-1,((int8_t*)p)[c]/127.f):p[c]/255.f;
            }
            int ok=1;for(unsigned c=0;c<4;c++)ok&=fabsf(actual[i*4+c]-want[c])<.0001f;checks++;failed+=!ok;printf("uncompressed atlas format=%u gob=%d phase=%u query=%u %s\n",format,gob,phase,i,ok?"PASS":"FAIL");
        }
    }
    uint64_t bytes,up,re,meta;vk_atlas_stats(&bytes,&up,&re,&meta);atlas_check(bytes<t.L.size,"uncompressed array backing stays below logical size");
    atlas_shader_key=11;fini((NVNmemoryPool*)&virtual);fini((NVNmemoryPool*)&physical);mtl_pool_del(job);munmap(source,2*65536);munmap(job,65536);free(linear);free(expected);free(gathered);
}
static void uncompressed_tests(void){unsigned formats[]={NVN_FORMAT_RGBA8,NVN_FORMAT_RGBA8SN,NVN_FORMAT_R16,NVN_FORMAT_RG16};for(unsigned f=0;f<4;f++)for(int gob=0;gob<2;gob++)for(int arrayed=0;arrayed<2;arrayed++)uncompressed_case(formats[f],gob,arrayed);}
