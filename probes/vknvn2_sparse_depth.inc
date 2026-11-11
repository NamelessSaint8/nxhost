// Sparse CPU-backed depth arrays: real NVN mappings, GPU copies, CPU updates and
// remaps before a submission completes. No game data and no native sparse depth.
static void depth_check(int ok,const char *what){checks++;failed+=!ok;printf("sparse depth %s %s\n",what,ok?"PASS":"FAIL");}
static void depth_fill(tex_t *t,uint8_t *dst,unsigned seed){
    memset(dst,0,t->L.size);unsigned bytes=t->d.format==NVN_FORMAT_DEPTH16?2:4;
    for(unsigned layer=0;layer<t->d.depth;layer++)for(unsigned mip=0;mip<t->d.levels;mip++){
        unsigned w=t->d.width>>mip,h=t->d.height>>mip;if(!w)w=1;if(!h)h=1;
        uint8_t *linear=malloc((size_t)w*h*bytes);
        for(unsigned y=0;y<h;y++)for(unsigned x=0;x<w;x++){unsigned v=(x*17+y*29+layer*997+mip*133+seed)%65536;
            if(bytes==2){uint16_t d=(uint16_t)v;memcpy(linear+((size_t)y*w+x)*bytes,&d,2);}else{float d=v/65535.f;memcpy(linear+((size_t)y*w+x)*bytes,&d,4);}}
        if(nvn_swizzle(&t->d,mip,layer,linear,(size_t)w*bytes,dst))abort();free(linear);
    }
}
static void depth_read_check(tex_t *t,unsigned seed){
    unsigned bytes=t->d.format==NVN_FORMAT_DEPTH16?2:4;
    for(unsigned layer=0;layer<t->d.depth;layer++)for(unsigned mip=0;mip<t->d.levels;mip++){
        unsigned w=t->d.width>>mip,h=t->d.height>>mip;if(!w)w=1;if(!h)h=1;
        uint8_t *out=malloc((size_t)w*h*bytes);NVNcopyRegion region={0,0,0,(int)w,(int)h,1};
        mtl_read_texels(t,mip,layer,&region,out,(size_t)w*bytes,(size_t)w*h*bytes);
        int ok=1;for(unsigned y=0;y<h;y++)for(unsigned x=0;x<w;x++){unsigned want=(x*17+y*29+layer*997+mip*133+seed)%65536;
            if(bytes==2){uint16_t v;memcpy(&v,out+((size_t)y*w+x)*bytes,2);ok&=v==want;}else{float v;memcpy(&v,out+((size_t)y*w+x)*bytes,4);ok&=fabsf(v-want/65535.f)<0.000001f;}}
        char name[128];snprintf(name,sizeof name,"format=%u gob=%d seed=%u layer=%u mip=%u all pixels",t->d.format,nvn_gob_switch2,seed,layer,mip);depth_check(ok,name);free(out);
    }
}
static void sparse_depth_case(unsigned format,int gob){
    nvn_gob_switch2=gob;tex_t t={.magic=MAGIC('T','E','X',0),.serial=19000+format*10+(unsigned)gob};
    t.d=(nvn_texdesc){.format=format,.target=NVN_TEXTURE_TARGET_2D_ARRAY,.flags=NVN_TEXTURE_FLAGS_SPARSE,.width=256,.height=256,.depth=3,.levels=4,.samples=1};nvn_tex_layout(&t.d,&t.L);
    size_t size=(t.L.size+65535)&~65535ull;uint8_t *source=mmap(NULL,size*2,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0);if(source==MAP_FAILED)abort();
    depth_fill(&t,source,7);depth_fill(&t,source+size,71);
    NVNT_nvnMemoryPoolInitialize init=atlas_api("nvnMemoryPoolInitialize");NVNT_nvnMemoryPoolFinalize fini=atlas_api("nvnMemoryPoolFinalize");NVNT_nvnMemoryPoolMapVirtual map=atlas_api("nvnMemoryPoolMapVirtual");
    pool_t physical,virtual;pool_builder_t pb={.mem=source,.size=size*2,.flags=0x18c};if(!init((NVNmemoryPool*)&physical,(NVNmemoryPoolBuilder*)&pb))abort();
    t.off=65536;pb=(pool_builder_t){.size=size+t.off,.flags=0x200};if(!init((NVNmemoryPool*)&virtual,(NVNmemoryPoolBuilder*)&pb))abort();t.pool=&virtual;t.mem=virtual.mem+t.off;
    // Reverse two page positions and restore them: the texture cannot collapse
    // to one physical interval, while its final bytes still match the pattern.
    unsigned pages=(unsigned)(size/65536);AtlasMapping *mapping=calloc(pages,sizeof *mapping);
    for(unsigned i=0;i<pages;i++)mapping[i]=(AtlasMapping){(NVNmemoryPool*)&physical,(int64_t)i*65536,t.off+(int64_t)i*65536,65536,0,0};
    // A hole in the unused final virtual page keeps the pool virtual, even when
    // this texture interval is contiguous. Use a repeated mapping outside L.
    mapping[pages-1].source=0;
    depth_check(map((NVNmemoryPool*)&virtual,(int)pages,(NVNmappingRequest*)mapping),"page mappings accepted");
    // This last page is part of the texture: form a noncontiguous physical span
    // without changing its bytes by copying the final page to an extra slot.
    dm_guest_write_prepare(source+size,65536);memcpy(source+size,source+(pages-1)*65536,65536);mapping[pages-1].source=(int64_t)size;
    if(!map((NVNmemoryPool*)&virtual,1,(NVNmappingRequest*)&mapping[pages-1]))abort();
    depth_read_check(&t,7);
    dm_guest_write_prepare(source,size);depth_fill(&t,source,23);dm_guest_write_prepare(source+size,65536);memcpy(source+size,source+(pages-1)*65536,65536);
    vk_sparse_cpu_poll();depth_read_check(&t,23);
    // Swap only one physical page, leaving every other page's content intact.
    dm_guest_write_prepare(source+size,65536);memcpy(source+size,source+(pages-1)*65536,65536);
    mapping[pages-1].physical=NULL;if(!map((NVNmemoryPool*)&virtual,1,(NVNmappingRequest*)&mapping[pages-1]))abort();
    mtl_sub_begin();vkimg_t *hole=vk_tex(&t);depth_check(hole && hole->packaged,"unmapped depth pages use safe zero snapshot");uint64_t fence=mtl_sub_commit();if(!mtl_wait(fence,10000000000ull))abort();
    mapping[pages-1].physical=(NVNmemoryPool*)&physical;if(!map((NVNmemoryPool*)&virtual,1,(NVNmappingRequest*)&mapping[pages-1]))abort();depth_read_check(&t,23);
    // Two source versions used before the same fence must retain separate GPU
    // contents even though the old CPU storage was modified and retired.
    mtl_sub_begin();VkBuffer rb[2];VkDeviceSize ro[2];uint8_t *pixels[2];
    for(unsigned version=0;version<2;version++){
        if(version){dm_guest_write_prepare(source,size);depth_fill(&t,source,31);dm_guest_write_prepare(source+size,65536);memcpy(source+size,source+(pages-1)*65536,65536);vk_sparse_cpu_poll();}
        vkimg_t *im=vk_tex(&t);pixels[version]=vk_scratch(4,4,&rb[version],&ro[version]);VkCommandBuffer cb=vk_cmd();vk_tex_prepare(cb,im);vk_img_barrier_all(cb);
        VkBufferImageCopy copy={.bufferOffset=ro[version],.imageSubresource={im->aspect,0,0,1},.imageExtent={1,1,1}};vkCmdCopyImageToBuffer(cb,im->img,VK_IMAGE_LAYOUT_GENERAL,rb[version],1,&copy);
    }
    if(!mtl_wait(mtl_sub_commit(),10000000000ull))abort();
    for(unsigned version=0;version<2;version++){unsigned want=version?31:23;int ok;if(format==NVN_FORMAT_DEPTH16){uint16_t v;memcpy(&v,pixels[version],2);ok=v==want;}else{float v;memcpy(&v,pixels[version],4);ok=fabsf(v-want/65535.f)<0.000001f;}depth_check(ok,"versions retain contents until the same GPU fence");}
    terrain_clear(&t);uint8_t cleared[256*256*4];NVNcopyRegion region={0,0,0,256,256,1};unsigned bytes=format==NVN_FORMAT_DEPTH16?2:4;
    mtl_read_texels(&t,0,0,&region,cleared,256*bytes,256*256*bytes);int ok=1;
    for(unsigned i=0;i<256*256;i++)if(format==NVN_FORMAT_DEPTH16){uint16_t v;memcpy(&v,cleared+i*2,2);ok&=v==16384 || v==16383;}else if(format==NVN_FORMAT_DEPTH32F){float v;memcpy(&v,cleared+i*4,4);ok&=v==.25f;}else{const int8_t *v=(const int8_t*)(cleared+i*4);ok&=v[0]==32 && v[1]==64 && v[2]==0 && v[3]==127;}
    depth_check(ok,"actual GPU clear survives repeated storage lookup");
    fini((NVNmemoryPool*)&virtual);fini((NVNmemoryPool*)&physical);free(mapping);munmap(source,size*2);
}
static void sparse_depth_tests(void){for(unsigned i=0;i<3;i++)for(int gob=0;gob<2;gob++)sparse_depth_case(i==0?NVN_FORMAT_DEPTH16:i==1?NVN_FORMAT_DEPTH32F:NVN_FORMAT_RGBA8SN,gob);}
