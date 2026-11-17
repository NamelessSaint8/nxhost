// Host entry to the exact runtime coherent-write-log transform.
#include <stdio.h>
#include "../nxnative/dm/android/gfx_vk_spv_gmem.inc"
int main(int argc,char **argv){
    if(argc!=4)return 2;uint32_t binding=(uint32_t)strtoul(argv[3],NULL,0),nw=0;
    FILE *f=fopen(argv[1],"rb");if(!f)return 2;if(fseek(f,0,SEEK_END))return 2;long bytes=ftell(f);rewind(f);if(bytes<20 || bytes%4)return 2;
    uint32_t *w=malloc((size_t)bytes);if(!w || fread(w,1,(size_t)bytes,f)!=(size_t)bytes)return 2;fclose(f);
    uint32_t *out=spv_gmem_unlogged(w,(uint32_t)bytes/4,&binding,1,&nw);free(w);if(!out)return 3;
    f=fopen(argv[2],"wb");if(!f){free(out);return 2;}int ok=fwrite(out,4,nw,f)==nw;if(fclose(f))ok=0;free(out);return ok?0:2;
}
