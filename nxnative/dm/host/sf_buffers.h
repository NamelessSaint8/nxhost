// HIPC output descriptors, decoded before the in-process server overwrites the
// request with its reply. Layout: switchbrew/libnx nx/include/switch/sf/hipc.h.
#pragma once
#include <stdint.h>
#include <stddef.h>
#include <string.h>
typedef struct { uint64_t address, size; } sf_out_buffer;
static int sf_output_buffers(const void *message,size_t bytes,sf_out_buffer out[28]) {
    if(!message || bytes<8)return -1;
    const uint32_t *w=message;uint32_t h=w[0],flags=w[1];size_t words=bytes/4,pos=2;
    if(flags>>31){if(pos>=words)return -1;uint32_t s=w[pos++];size_t extra=(s&1?2:0)+((s>>1)&15)+((s>>5)&15);if(extra>words-pos)return -1;pos+=extra;}
    unsigned x=(h>>16)&15,a=(h>>20)&15,b=(h>>24)&15,exchange=(h>>28)&15;
    size_t descriptors=2*x+3*(a+b+exchange);if(descriptors>words-pos)return -1;
    size_t recv=pos+2*x+3*a,data=pos+descriptors;int count=0;
    for(unsigned i=0;i<b;i++) {
        const uint32_t *d=w+recv+3*i;
        uint64_t address=d[1]|((uint64_t)(d[2]>>28)<<32)|((uint64_t)((d[2]>>2)&0x3fffff)<<36);
        uint64_t size=d[0]|((uint64_t)((d[2]>>24)&15)<<32);
        if(!address && !size)continue;
        if(!address || !size || size-1>UINT64_MAX-address)return -1;
        out[count++]=(sf_out_buffer){address,size};
    }
    size_t raw=flags&1023;if(raw>words-data)return -1;
    unsigned mode=(flags>>10)&15;if(mode==1 || mode==2)return -1; // server auto-receive modes are not client output lists
    unsigned c=mode?mode-2:0;
    size_t list=(flags>>20)&2047;if(!list)list=data+raw;
    if(list<data+raw || list>words || 2*c>words-list)return -1;
    uint64_t pointer_bytes=0;
    for(unsigned i=0;i<c;i++) {
        const uint32_t *d=w+list+2*i;uint64_t address=d[0]|((uint64_t)(d[1]&65535)<<32),size=d[1]>>16;
        if(!address && !size)continue;
        if(!address || !size || size-1>UINT64_MAX-address)return -1;
        pointer_bytes+=(size+15)&~15ull;if(pointer_bytes>4096)return -1;
        out[count++]=(sf_out_buffer){address,size};
    }
    return count;
}
static int sf_zero_outputs(const sf_out_buffer *buffers,int count,int (*valid)(uint64_t,uint64_t,void *),void *context) {
    for(int i=0;i<count;i++)if(!valid(buffers[i].address,buffers[i].size,context))return 0;
    for(int i=0;i<count;i++)memset((void *)(uintptr_t)buffers[i].address,0,(size_t)buffers[i].size);
    return 1;
}
