// Host-side entry to the exact Android atlas-header specialization transform.
#include <stdio.h>
#include "../nxnative/dm/android/gfx_vk_spv_atlas.inc"
int main(int argc,char **argv){
    if(argc<5 || (argc-3)%2 || argc>131)return 2;
    uint32_t bindings[64],slots[64];unsigned count=(unsigned)(argc-3)/2;
    for(unsigned i=0;i<count;i++){bindings[i]=(uint32_t)strtoul(argv[3+2*i],NULL,0);slots[i]=(uint32_t)strtoul(argv[4+2*i],NULL,0);if(slots[i]>=64)return 2;}
    FILE *f=fopen(argv[1],"rb");if(!f)return 2;if(fseek(f,0,SEEK_END))return 2;long bytes=ftell(f);rewind(f);if(bytes<20 || bytes%4)return 2;
    uint32_t *w=malloc((size_t)bytes),nw=0;uint64_t mask=0;if(!w || fread(w,1,(size_t)bytes,f)!=(size_t)bytes)return 2;fclose(f);
    uint64_t directional=spv_atlas_directional(w,(uint32_t)bytes/4);uint32_t *out=spv_atlas_headers(w,(uint32_t)bytes/4,bindings,slots,count,&nw,&mask);if(!out){free(w);return 3;}free(w);
    f=fopen(argv[2],"wb");if(!f){free(out);return 2;}int ok=fwrite(out,4,nw,f)==nw;if(fclose(f))ok=0;free(out);printf("atlas specialization mask=%#llx directional=%#llx words=%u\n",(unsigned long long)mask,(unsigned long long)directional,nw);return ok?0:2;
}
