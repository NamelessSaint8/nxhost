// Exercise actual HIPC dispatch, not just descriptor helpers. Local caller-stack
// output storage is valid for the initial guest main, before guest threads exist.
#include "../hle_sf.c"
static uintptr_t guest_lo,guest_hi;
int dm_guest_as_contains(uintptr_t a){return a>=guest_lo && a<guest_hi;}
module_t *module_of(const void *p){(void)p;return NULL;}
static unsigned checks,failed;
#define CHECK(x) do{checks++;if(!(x)){failed++;fprintf(stderr,"FAIL line %d: %s\n",__LINE__,#x);}}while(0)
static void request(uint32_t m[256],uint32_t cmd,void *out,unsigned bytes,int domain){
    memset(m,0,1024);m[0]=4;m[1]=16|(out?3u<<10:0);
    unsigned cm=4;if(domain){m[cm]=1|(16u<<16);m[cm+1]=1;cm+=4;}
    m[cm]=0x49434653;m[cm+2]=cmd;
    if(out){uint64_t p=(uint64_t)(uintptr_t)out;m[18]=(uint32_t)p;m[19]=(uint32_t)(p>>32)|(bytes<<16);}
}
int main(void){
    uint32_t h=0;uint16_t budget=0;uint32_t message[256];uint8_t out[512];
    CHECK(h_sf_Connect(&h,"chat:u")==RES_OK);
    CHECK(h_sf_PtrBuf(&budget,h)==RES_OK && budget==4096);
    uint32_t object;CHECK(h_sf_ToDomain(&object,h)==RES_OK && object==1);
    memset(out,0xa5,sizeof out);request(message,11,out,240,1);
    CHECK(dm_sf_send(h,message,sizeof message)==RES_OK);
    CHECK(message[8]==0x4f434653 && message[10]==RES_OK);
    int zeros=1;for(unsigned i=0;i<240;i++)zeros&=out[i]==0;CHECK(zeros && out[240]==0xa5);
    // Invalid destinations reject the complete request before any valid output
    // is modified, including the reply message itself.
    request(message,11,(void *)(uintptr_t)1,16,1);uint32_t original=message[4];
    CHECK(dm_sf_send(h,message,sizeof message)!=RES_OK && message[4]==original);
    CHECK(h_sf_Connect(&h,"auddmg:u")==RES_OK);request(message,0,NULL,0,0);
    CHECK(dm_sf_send(h,message,sizeof message)==RES_OK);
    uint32_t manager=message[3];CHECK(manager>=SF_OBJ_H0 && manager<SF_OBJ_H0+0x1000);
    CHECK(h_sf_PtrBuf(&budget,manager)==RES_OK && budget==4096);
    memset(out,0xa5,sizeof out);request(message,0,out,sizeof out,0);
    CHECK(dm_sf_send(manager,message,sizeof message)==RES_OK);
    CHECK(!strcmp((char*)out,"AudioVirtualOutput0") && message[8]==1);
    uint32_t close_message[2]={2,0};CHECK(dm_sf_send(manager,close_message,sizeof close_message)==RES_OK);
    uint32_t short_message[2]={4,0};CHECK(dm_sf_send(manager,short_message,sizeof short_message)!=RES_OK);
    CHECK(h_sf_PtrBuf(&budget,0xdeadbeef)!=RES_OK);
    printf("HIPC dispatch: %u checks, %u failed\n",checks,failed);return failed!=0;
}
