// Host-side CLI for the exact Android distance-interface transform.
#include <stdio.h>
#include "../nxnative/dm/android/gfx_vk_spv_limits.inc"
int main(int argc,char **argv){if(argc!=3 && argc!=2)return 2;FILE *f=fopen(argv[1],"rb");if(!f)return 2;fseek(f,0,SEEK_END);long bytes=ftell(f);rewind(f);uint32_t *w=malloc(bytes);if(bytes<20 || bytes%4 || fread(w,1,bytes,f)!=(size_t)bytes)return 2;fclose(f);if(argc==2){printf("%llu\n",(unsigned long long)spv_workgroup_bytes(w,bytes/4));free(w);return 0;}uint32_t n=0,*out=spv_prune_distances(w,bytes/4,&n);if(!out){out=w;n=bytes/4;}f=fopen(argv[2],"wb");if(!f)return 2;int ok=fwrite(out,4,n,f)==n && !fclose(f);if(out!=w)free(out);free(w);return !ok;}
