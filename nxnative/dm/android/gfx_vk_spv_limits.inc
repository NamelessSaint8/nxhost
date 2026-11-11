// Remove unused ClipDistance/CullDistance members from output interface blocks.
// Declaring eight unused clip distances plus one unused cull distance exceeds
// Vulkan's combined limit on mobile GPUs, even when only Position is accessed.
// Unknown pointer uses retain the entire block. Written distances stay intact.
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
// Logical storage is a lower bound when explicit layout adds padding. Unknown
// types return zero; validation remains responsible for those layouts.
static uint64_t spv_storage_size(const uint32_t *w,const uint32_t *at,const uint32_t *cv,uint32_t bound,uint32_t id,unsigned depth) {
    if(id>=bound || !at[id] || depth>32)return 0;
    uint32_t i=at[id],n=w[i]>>16,op=w[i]&0xffff;uint64_t size=0,count=1;
    if(op==20)return 4;
    if((op==21 || op==22) && n>=3)return w[i+2]/8;
    if((op==23 || op==24 || op==28) && n==4){
        size=spv_storage_size(w,at,cv,bound,w[i+2],depth+1);
        count=op==28?(w[i+3]<bound?cv[w[i+3]]:0):w[i+3];
    }else if(op==32 && n==4)return spv_storage_size(w,at,cv,bound,w[i+3],depth+1);
    else if(op==30){
        for(uint32_t j=2;j<n;j++){uint64_t member=spv_storage_size(w,at,cv,bound,w[i+j],depth+1);if(!member)return 0;if(UINT64_MAX-size<member)return UINT64_MAX;size+=member;}return size;
    }
    return count && size>UINT64_MAX/count?UINT64_MAX:size*count;
}
static uint64_t spv_workgroup_bytes(const uint32_t *w,uint32_t nw) {
    if(nw<5 || w[0]!=0x07230203 || !w[3] || w[3]>(1u<<24))return 0;
    uint32_t bound=w[3],*at=calloc(bound,4),*cv=calloc(bound,4);uint64_t bytes=0;
    if(!at || !cv)goto done;
    for(uint32_t i=5;i<nw;){uint32_t n=w[i]>>16,op=w[i]&0xffff;if(!n || n>nw-i){bytes=0;goto done;}
        if(op>=19 && op<=39 && n>=2 && w[i+1]<bound)at[w[i+1]]=i;
        if(op==43 && n==4 && w[i+2]<bound)cv[w[i+2]]=w[i+3];i+=n;
    }
    for(uint32_t i=5;i<nw;i+=w[i]>>16)if((w[i]&0xffff)==59 && w[i]>>16>=4 && w[i+3]==4){
        uint64_t size=spv_storage_size(w,at,cv,bound,w[i+1],0);if(UINT64_MAX-bytes<size){bytes=UINT64_MAX;break;}bytes+=size;
    }
done:free(at);free(cv);return bytes;
}
static uint32_t *spv_prune_distances(const uint32_t *w,uint32_t nw,uint32_t *onw) {
    *onw=0;
    if(nw<5 || w[0]!=0x07230203 || !w[3] || w[3]>(1u<<24))return NULL;
    struct {uint32_t id;uint64_t distances,used,drop;} blocks[32]={0};unsigned nb=0;uint32_t base=w[3],fn=nw;
    uint32_t *at=calloc(base,4),*ct=calloc(base,4),*cv=calloc(base,4),*fix=calloc(nw,4),*extra=malloc((size_t)nw*4);
    uint8_t *root=calloc(base,1),seen[32]={0};uint32_t *out=NULL,ne=0,bound=base;
    if(!at || !ct || !cv || !fix || !extra || !root)goto done;
    for(uint32_t i=5;i<nw;){uint32_t n=w[i]>>16,op=w[i]&0xffff;if(!n || n>nw-i)goto done;
        if(op==54 && fn==nw)fn=i;
        if(op>=19 && op<=39 && n>=2 && w[i+1]<base)at[w[i+1]]=i;
        if(op==43 && n==4 && w[i+2]<base){ct[w[i+2]]=w[i+1];cv[w[i+2]]=w[i+3];}
        if(op==72 && n==5 && w[i+3]==11 && (w[i+4]==3 || w[i+4]==4) && w[i+2]<64){
            unsigned b=0;while(b<nb && blocks[b].id!=w[i+1])b++;
            if(b==nb){if(nb==32)goto done;blocks[nb++].id=w[i+1];}blocks[b].distances|=1ull<<w[i+2];
        }i+=n;
    }
    if(!nb)goto done;
    for(uint32_t i=5;i<fn;i+=w[i]>>16){uint32_t n=w[i]>>16,op=w[i]&0xffff;
        if(op==59 && n>=4 && w[i+1]<base && w[i+2]<base){uint32_t p=at[w[i+1]];
            if(p && (w[p]&0xffff)==32 && w[p]>>16==4)for(unsigned b=0;b<nb;b++)if(w[p+3]==blocks[b].id){
                if(w[i+3]==3){root[w[i+2]]=(uint8_t)(b+1);seen[b]=1;}else blocks[b].used=UINT64_MAX;
            }
        }
        if(op==75)for(uint32_t j=2;j+1<n;j+=2)for(unsigned b=0;b<nb;b++)if(w[i+j]==blocks[b].id)blocks[b].used=UINT64_MAX;
    }
    for(unsigned b=0;b<nb;b++)if(!seen[b])blocks[b].used=UINT64_MAX;
    for(uint32_t i=fn;i<nw;i+=w[i]>>16){uint32_t n=w[i]>>16,op=w[i]&0xffff;
        if((op==65 || op==66) && n>=5 && w[i+3]<base && root[w[i+3]]){
            unsigned b=root[w[i+3]]-1;uint32_t index=w[i+4];
            if(index<base && ct[index] && cv[index]<64)blocks[b].used|=1ull<<cv[index];else blocks[b].used=UINT64_MAX;
        }else for(uint32_t j=1;j<n;j++){
            // OpExtInst's instruction number is a literal, not an ID. FMin's
            // number 37 can equal an output variable ID without using it.
            if(op==12 && j==4)continue;
            if(w[i+j]<base && root[w[i+j]])blocks[root[w[i+j]]-1].used=UINT64_MAX;
        }
    }
    int changed=0;for(unsigned b=0;b<nb;b++){
        uint32_t t=blocks[b].id<base?at[blocks[b].id]:0;
        if(!t || (w[t]&0xffff)!=30 || w[t]>>16>66)continue;
        blocks[b].drop=blocks[b].distances&~blocks[b].used;changed|=blocks[b].drop!=0;
    }
    if(!changed)goto done;
    for(uint32_t i=fn;i<nw;i+=w[i]>>16){uint32_t n=w[i]>>16,op=w[i]&0xffff;
        if((op==65 || op==66) && n>=5 && w[i+3]<base && root[w[i+3]]){
            unsigned b=root[w[i+3]]-1;uint32_t id=w[i+4];if(!blocks[b].drop || id>=base || !ct[id] || cv[id]>=64)continue;
            uint32_t old=cv[id],value=old-(uint32_t)__builtin_popcountll(blocks[b].drop&((1ull<<old)-1));if(old==value)continue;
            uint32_t found=0;for(uint32_t k=1;k<base;k++)if(ct[k]==ct[id] && cv[k]==value){found=k;break;}
            for(uint32_t k=0;!found && k<ne;k+=4)if(extra[k+1]==ct[id] && extra[k+3]==value)found=extra[k+2];
            if(!found){if(ne+4>nw)goto done;found=bound++;extra[ne++]=4u<<16|43;extra[ne++]=ct[id];extra[ne++]=found;extra[ne++]=value;}
            fix[i+4]=found;
        }
    }
    out=malloc(((size_t)nw+ne)*4);if(!out)goto done;memcpy(out,w,20);out[3]=bound;uint32_t no=5;
    for(uint32_t i=5;i<nw;){uint32_t n=w[i]>>16,op=w[i]&0xffff;
        if(i==fn){memcpy(out+no,extra,ne*4);no+=ne;}
        unsigned b=0;if((op==30 || op==72 || op==6) && n>=3)while(b<nb && blocks[b].id!=w[i+1])b++;else b=nb;
        if(b<nb && blocks[b].drop && op==30){uint32_t start=no;out[no++]=0;out[no++]=w[i+1];
            for(uint32_t j=2;j<n;j++)if(!(blocks[b].drop>>(j-2)&1))out[no++]=w[i+j];out[start]=(no-start)<<16|30;
        }else if(b<nb && blocks[b].drop && (op==72 || op==6)){
            uint32_t member=w[i+2];if(member>=64)goto invalid;if(!(blocks[b].drop>>member&1)){
                memcpy(out+no,w+i,n*4);out[no+2]=member-(uint32_t)__builtin_popcountll(blocks[b].drop&((1ull<<member)-1));no+=n;
            }
        }else{memcpy(out+no,w+i,n*4);for(uint32_t j=1;j<n;j++)if(fix[i+j])out[no+j]=fix[i+j];no+=n;}
        i+=n;
    }*onw=no;goto done;
invalid:free(out);out=NULL;
done:free(at);free(ct);free(cv);free(fix);free(extra);free(root);return out;
}
