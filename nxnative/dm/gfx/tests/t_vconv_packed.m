// Packed signed vertex conversion: every ten-bit value and alpha pattern, unaligned/strided inputs, vector tails and literal float32 register bits.
#include "../nvn/nvn_mtl.m"
void *front_metal_layer(void){return NULL;}
module_t *module_of(const void *p){(void)p;return NULL;}
module_t *g_mod;int g_nmod;
void svc_thread_dump(void){}
uint64_t now_ns(void){return bp_now();}
static int checks,failed;
#define CHECK(c,label) do{checks++;if(!(c)){failed++;fprintf(stderr,"FAIL: %s\n",label);}}while(0)
static __attribute__((noinline)) void scalar(int format,uint64_t src,uint32_t stride,uint64_t n,float *out){for(uint64_t i=0;i<n;i++)vconv_elem(format,(const uint8_t *)(uintptr_t)src+i*stride,out+4*i);}
static void test(void){
    enum{N=4099};uint8_t *source=malloc(N*39+16);float *got=malloc((N*4+8)*4),*want=malloc(N*16);
    const unsigned strides[]={0,4,7,12,28,39},counts[]={0,1,2,3,4,5,9,17,N};
    for(int format=0x69;format<=0x6a;format++)for(unsigned j=0;j<sizeof strides/sizeof *strides;j++)for(unsigned off=0;off<4;off++){
        unsigned stride=strides[j];for(unsigned i=0;i<N;i++){uint32_t v=(i&1023)|(((i*37+511)&1023)<<10)|(((i*111+512)&1023)<<20)|((i%4)<<30);memcpy(source+off+(size_t)i*stride,&v,4);}
        for(unsigned k=0;k<sizeof counts/sizeof *counts;k++){
            unsigned count=counts[k];memset(got,0x5a,(N*4+8)*4);scalar(format,(uint64_t)(uintptr_t)(source+off),stride,count,want);vconv_fill(format,(uint64_t)(uintptr_t)(source+off),stride,count,got);
            CHECK(!memcmp(got,want,count*16),"packed conversion is bit-exact for all components");
            uint32_t guard;memcpy(&guard,got+count*4,4);CHECK(guard==0x5a5a5a5a,"conversion does not write beyond its vertex range");
        }
    }
    free(source);free(got);free(want);
}
static void benchmark(void){
    enum{N=180000,REPS=20};uint32_t *data=malloc(N*28);float *out=malloc(N*16);uint32_t seed=1;
    for(unsigned i=0;i<N*7;i++){seed=seed*1664525+1013904223;data[i]=seed;}
    void(*volatile old)(int,uint64_t,uint32_t,uint64_t,float *)=scalar;
    void(*volatile fast)(int,uint64_t,uint32_t,uint64_t,float *)=vconv_fill;
    uint64_t start=bp_now();for(int i=0;i<REPS;i++)old(0x69,(uint64_t)(uintptr_t)data,28,N,out);double baseline=(bp_now()-start)/1e6;
    volatile float keep=out[17];start=bp_now();for(int i=0;i<REPS;i++)fast(0x69,(uint64_t)(uintptr_t)data,28,N,out);double optimized=(bp_now()-start)/1e6;keep+=out[17];(void)keep;
    printf("packed conversion benchmark: scalar %.2f ms, optimized %.2f ms, %.2fx (%d vertices x %d)\n",baseline,optimized,baseline/optimized,N,REPS);free(data);free(out);
}
int main(void){@autoreleasepool{test();benchmark();printf("packed vertex conversion: %d checks, %d failed\n",checks,failed);return failed!=0;}}
