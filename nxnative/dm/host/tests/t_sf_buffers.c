#include "../sf_buffers.h"
#include <stdio.h>
#include <stdlib.h>
static unsigned checks,failed;
#define CHECK(c) do{checks++;if(!(c)){failed++;fprintf(stderr,"FAIL line %d\n",__LINE__);}}while(0)
typedef struct{uintptr_t start;size_t size;} region;
static int valid(uint64_t address,uint64_t bytes,void *context){region *r=context;return address>=r->start && address-r->start<=r->size && bytes<=r->size-(address-r->start);}
static void buffer(uint32_t *d,void *p,uint64_t size){uint64_t a=(uintptr_t)p;d[0]=(uint32_t)size;d[1]=(uint32_t)a;d[2]=(uint32_t)((a>>32)&15)<<28|(uint32_t)((a>>36)&0x3fffff)<<2|(uint32_t)(size>>32)<<24;}
static void receive(uint32_t *d,void *p,unsigned size){uint64_t a=(uintptr_t)p;d[0]=(uint32_t)a;d[1]=(uint32_t)((a>>32)&65535)|(size<<16);}
int main(void){
    uint8_t storage[512];region r={(uintptr_t)storage,sizeof storage};uint32_t message[64]={0};sf_out_buffer out[28];
    // PID, copy/move handles, an X pointer and an A input precede B outputs.
    message[0]=6|(1u<<16)|(1u<<20)|(1u<<24);message[1]=8|(3u<<10)|(1u<<31);message[2]=1|(1u<<1)|(1u<<5);
    buffer(message+12,storage+16,32);receive(message+23,storage+64,248);
    memset(storage,0xa5,sizeof storage);int n=sf_output_buffers(message,sizeof message,out);
    CHECK(n==2);CHECK(out[0].address==(uintptr_t)(storage+16));CHECK(out[0].size==32);CHECK(out[1].address==(uintptr_t)(storage+64));CHECK(out[1].size==248);
    CHECK(sf_zero_outputs(out,n,valid,&r));
    for(unsigned i=0;i<sizeof storage;i++)CHECK(storage[i]==((i>=16 && i<48)||(i>=64 && i<312)?0:0xa5));
    // Validate every output before writing any of them.
    memset(storage,0xa5,sizeof storage);out[1].address=r.start+r.size+1;
    CHECK(!sf_zero_outputs(out,n,valid,&r));CHECK(storage[16]==0xa5);
    CHECK(sf_output_buffers(message,23*4+4,out)==-1); // truncated receive-list entry
    CHECK(sf_output_buffers(message,8,out)==-1); // truncated special header
    CHECK(sf_output_buffers(NULL,0,out)==-1);
    // An explicit list offset and a null auto-selected B buffer.
    buffer(message+12,NULL,0);message[1]=8|(3u<<10)|(1u<<31)|(30u<<20);receive(message+30,storage+64,248);
    CHECK(sf_output_buffers(message,sizeof message,out)==1);CHECK(out[0].size==248);
    // A pointer reply must fit the advertised 4 KiB transfer budget.
    receive(message+30,storage+64,4097);CHECK(sf_output_buffers(message,sizeof message,out)==-1);
    printf("SF output buffers: %u checks, %u failed\n",checks,failed);return failed!=0;
}
