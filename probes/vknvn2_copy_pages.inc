// Wide sparse writes must prepare physical host pages once per copy, including
// collisions in the 64-entry hot cache, without dirtying untouched tiles.
#include "nvn_dirty.h"
#include <time.h>
static uint64_t copy_pages_ns(void){struct timespec t;clock_gettime(CLOCK_MONOTONIC,&t);return (uint64_t)t.tv_sec*1000000000+t.tv_nsec;}
static void copy_pages_tests(void) {
    setenv("DM_NVN_SPARSE_COPY_TIMING","1",1);
    NVNT_nvnMemoryPoolInitialize init=atlas_api("nvnMemoryPoolInitialize");
    NVNT_nvnMemoryPoolFinalize finalize=atlas_api("nvnMemoryPoolFinalize");
    NVNT_nvnMemoryPoolMapVirtual map=atlas_api("nvnMemoryPoolMapVirtual");
    size_t pg=(size_t)getpagesize(),dummy_size=4096*pg;
    uint8_t *dummy=mmap(NULL,dummy_size,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0);
    for(unsigned i=0;i<4096;i++)nvn_dirty_add_range(dummy+i*pg,pg);
    for(int gob=0;gob<2;gob++){
        nvn_gob_switch2=gob;
        tex_t source={.magic=MAGIC('T','E','X',0),.serial=91000+(unsigned)gob};
        source.d=(nvn_texdesc){.target=NVN_TEXTURE_TARGET_2D,.format=NVN_FORMAT_RGBA_ASTC_4x4,.width=8192,.height=2048,.depth=1,.levels=1,.samples=1};nvn_tex_layout(&source.d,&source.L);
        tex_t target=source;target.serial+=10;target.d.flags=NVN_TEXTURE_FLAGS_SPARSE;target.d.height=4096;nvn_tex_layout(&target.d,&target.L);
        size_t length=(target.L.size+65535)&~65535ull;
        uint8_t *src=mmap(NULL,length,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0),*dst=mmap(NULL,length,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0);
        for(size_t i=0;i<length;i++)src[i]=(uint8_t)(i*13+(i>>12));memset(dst,0x55,length);
        pool_t pools[3];pool_builder_t pb={.mem=src,.size=length,.flags=0x18c};if(!init((NVNmemoryPool*)&pools[0],(NVNmemoryPoolBuilder*)&pb))abort();
        pb.mem=dst;if(!init((NVNmemoryPool*)&pools[1],(NVNmemoryPoolBuilder*)&pb))abort();
        target.off=0x800000000ll;pb=(pool_builder_t){.size=target.off+length+65536,.flags=0x200};if(!init((NVNmemoryPool*)&pools[2],(NVNmemoryPoolBuilder*)&pb))abort();
        AtlasMapping mapping={(NVNmemoryPool*)&pools[1],0,target.off,length,0,0};if(!map((NVNmemoryPool*)&pools[2],1,(NVNmappingRequest*)&mapping))abort();
        source.pool=&pools[0];source.mem=src;target.pool=&pools[2];target.mem=pools[2].mem+target.off;
        size_t row=8192/4*16,rows=4096/4,linear_size=row*rows;
        uint8_t *expected=malloc(linear_size),*actual=malloc(linear_size);memset(expected,0x55,linear_size);
        if(nvn_deswizzle(&source.d,0,0,src,expected,row))abort();
        uint64_t stamp=nvn_dirty_now();nvn_dirty_protect(dst,length);
        NVNcopyRegion region={0,0,0,8192,2048,1};uint64_t begin=copy_pages_ns();
        int rc=nvn_tex_mirror_t2t(&source,0,0,&region,&target,0,0,&region);
        double ms=(copy_pages_ns()-begin)/1e6;
        atlas_check(rc==0,"wide sparse compressed copy completes");
        if(nvn_deswizzle(&target.d,0,0,dst,actual,row))abort();
        atlas_check(!memcmp(actual,expected,linear_size),"wide copy preserves every source and untouched byte");
        atlas_check(!nvn_dirty_since(dst+length-65536,65536,stamp),"wide copy retains untouched physical tile stamps");
        printf("wide sparse copy gob=%d bytes=%zu ms=%.3f tracked-dummy-ranges=4096\n",gob,row*(2048/4),ms);
        free(expected);free(actual);for(unsigned i=0;i<3;i++)finalize((NVNmemoryPool*)&pools[2-i]);munmap(src,length);munmap(dst,length);
    }
    for(unsigned i=0;i<4096;i++)nvn_dirty_remove_range(dummy+i*pg);munmap(dummy,dummy_size);
}
