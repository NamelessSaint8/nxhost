// Reserved write-log operations have no guest-visible result. Remove them only
// for an immutable map containing exclusively coherent zero-copy allocations.
// Unknown pointer uses reject the transform; the tracked module stays available.
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
static uint32_t *spv_gmem_unlogged(const uint32_t *w,uint32_t nw,const uint32_t *bindings,unsigned nb,uint32_t *onw) {
    *onw=nw;if(nw<5 || !w[3] || !nb)return NULL;
    uint32_t bound=w[3],ut=0,zero=0,changes=0;
    uint8_t *log=calloc(bound,1),*type=calloc(bound,1),*drop=calloc(nw,1);
    if(!log || !type || !drop)goto fail;
    for(uint32_t i=5;i<nw;){uint32_t n=w[i]>>16,op=w[i]&65535;if(!n || n>nw-i)goto fail;
        if(op==21 && n==4 && w[i+2]==32 && !w[i+3]){ut=w[i+1];if(ut>=bound)goto fail;type[ut]=1;}
        if(op==71 && n==4 && w[i+2]==33){if(w[i+1]>=bound)goto fail;for(unsigned b=0;b<nb;b++)if(w[i+3]==bindings[b])log[w[i+1]]=1;}
        i+=n;
    }
    if(!ut)goto fail;
    for(uint32_t i=5;i<nw;){uint32_t n=w[i]>>16,op=w[i]&65535;
        if(((op==43 && n==4 && !w[i+3]) || (op==46 && n==3)) && w[i+1]==ut)zero=w[i+2];
        if((op==65 || op==66 || op==67 || op==70 || op==83) && n>=4){
            if(w[i+2]>=bound || w[i+3]>=bound)goto fail;
            if(log[w[i+3]])log[w[i+2]]=1;
        }
        i+=n;
    }
    for(uint32_t i=5;i<nw;){uint32_t n=w[i]>>16,op=w[i]&65535;
        if((op==230 || op==241) && n>=6 && w[i+3]<bound && log[w[i+3]]){
            if(w[i+1]!=ut)goto fail;drop[i]=2;changes++;
        }else if(op==62 && n>=3 && w[i+1]<bound && log[w[i+1]]){drop[i]=1;changes++;}
        else if(op==59 || op==65 || op==66 || op==67 || op==70 || op==71 || op==72 || op==83 || op<54 || op==317){/* declarations / pointer derivation / debug */}
        else {
            // This includes loads, copies, pointer parameters and unsupported
            // atomics. False negatives cost only an optimization opportunity.
            for(uint32_t j=1;j<n;j++)if(w[i+j]<bound && log[w[i+j]])goto fail;
        }
        i+=n;
    }
    if(!changes)goto fail;
    uint32_t *out=malloc(((size_t)nw+4)*4);if(!out)goto fail;
    memcpy(out,w,20);uint32_t no=5,newzero=zero?zero:bound++;int declared=zero!=0;
    for(uint32_t i=5;i<nw;){uint32_t n=w[i]>>16,op=w[i]&65535;
        if(!declared && op==54){out[no++]=4u<<16|43;out[no++]=ut;out[no++]=newzero;out[no++]=0;declared=1;}
        if(drop[i]==2){out[no++]=4u<<16|83;out[no++]=w[i+1];out[no++]=w[i+2];out[no++]=newzero;}
        else if(!drop[i]){memcpy(out+no,w+i,n*4);no+=n;}
        i+=n;
    }
    if(!declared){free(out);goto fail;}out[3]=bound;*onw=no;free(log);free(type);free(drop);return out;
fail:
    free(log);free(type);free(drop);return NULL;
}
