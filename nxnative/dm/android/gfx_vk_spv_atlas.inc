// Atlas header word zero is owned by the backend: 0 = native, 1 = mapped.
// Specialize that word per pipeline so the driver can discard unused sampling
// paths before optimizing a material. Other metadata words stay dynamic. The
// transform works for both retained GLSL helpers and inlined SPIR-V accesses.
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#define VK_ATLAS_SPEC_BASE 20000u
// Explicit LOD/fetches have no directional footprint. Track sampled-image
// origins for implicit/gradient operations; unresolved origins conservatively
// require directional filtering for every binding.
static uint64_t spv_atlas_directional(const uint32_t *w,uint32_t nw) {
    if(nw<5 || !w[3])return UINT64_MAX;uint32_t bound=w[3];uint64_t *owner=calloc(bound,8);if(!owner)return UINT64_MAX;
    for(uint32_t i=5;i<nw;){uint32_t n=w[i]>>16,op=w[i]&65535;if(!n || n>nw-i){free(owner);return UINT64_MAX;}
        if(op==71 && n==4 && w[i+2]==33 && w[i+1]<bound && w[i+3]<64)owner[w[i+1]]=1ull<<w[i+3];i+=n;}
    for(unsigned pass=0;pass<4;pass++){int changed=0;
        for(uint32_t i=5;i<nw;){uint32_t n=w[i]>>16,op=w[i]&65535;uint64_t bits=0;uint32_t result=n>=3?w[i+2]:bound;
            if((op==61 || op==65 || op==66 || op==83 || op==86 || op==100) && n>=4 && w[i+3]<bound)bits=owner[w[i+3]];
            if(op==169 && n==6 && w[i+4]<bound && w[i+5]<bound)bits=owner[w[i+4]]|owner[w[i+5]];
            if(op==245)for(uint32_t a=3;a+1<n;a+=2)if(w[i+a]<bound)bits|=owner[w[i+a]];
            if(bits && result<bound && (bits&~owner[result])){owner[result]|=bits;changed=1;}i+=n;
        }
        if(!changed)break;
    }
    uint64_t mask=0;
    for(uint32_t i=5;i<nw;){uint32_t n=w[i]>>16,op=w[i]&65535;int directional=op==87 || op==89 || op==91 || op==93;
        if((op==88 || op==92) && n>5 && (w[i+5]&4))directional=1;
        if((op==90 || op==94) && n>6 && (w[i+6]&4))directional=1;
        if(directional){if(n<4 || w[i+3]>=bound || !owner[w[i+3]]){mask=UINT64_MAX;break;}mask|=owner[w[i+3]];}
        i+=n;
    }
    free(owner);return mask;
}
static uint32_t *spv_atlas_headers(const uint32_t *w,uint32_t nw,const uint32_t *bindings,const uint32_t *slots,unsigned nb,uint32_t *onw,uint64_t *mask) {
    *mask=0;*onw=nw;if(!nb || nw<5 || !w[3])return NULL;
    uint32_t bound=w[3],next=bound,ut=0,it=0,bt=0,uz=0,iz=0;
    uint8_t *vars=calloc(bound,1),*ptrs=calloc(bound,1);uint32_t *indices=calloc(bound,4),*types=calloc(bound,4);
    uint8_t *zero=calloc(bound,1),*value_slot=calloc(bound,1),*fn_slot=calloc(bound,1),*simple=calloc(bound,1),*param_count=calloc(bound,1);
    uint32_t *loaded_from=calloc(bound,4),*value_index=calloc(bound,4),*parameter=calloc(bound,4);
    uint32_t *patch=calloc(nw,sizeof *patch),loads=0;uint64_t found=0,blocked=0;
    if(!vars || !ptrs || !indices || !types || !patch || !zero || !value_slot || !fn_slot || !simple || !param_count || !loaded_from || !value_index || !parameter)goto fail;
    for(uint32_t i=5;i<nw;){uint32_t n=w[i]>>16,op=w[i]&65535;if(!n || n>nw-i)goto fail;
        if(op==21 && n==4 && w[i+2]==32){if(w[i+3])it=w[i+1];else ut=w[i+1];}
        if(op==20 && n==2)bt=w[i+1];
        if(op==71 && n==4 && w[i+2]==1 && w[i+3]>=VK_ATLAS_SPEC_BASE && w[i+3]<VK_ATLAS_SPEC_BASE+64)blocked|=1ull<<(w[i+3]-VK_ATLAS_SPEC_BASE);
        if(op==71 && n==4 && w[i+2]==33 && w[i+1]<bound)for(unsigned b=0;b<nb;b++)if(w[i+3]==bindings[b] && slots[b]<64)vars[w[i+1]]=(uint8_t)(slots[b]+1);
        i+=n;}
    if(!ut)goto fail;
    for(uint32_t i=0;i<bound;i++)if(vars[i] && (blocked>>(vars[i]-1)&1))vars[i]=0;
    for(uint32_t i=5;i<nw;){uint32_t n=w[i]>>16,op=w[i]&65535;
        if(n>=3 && (w[i+1]==ut || (it && w[i+1]==it)) && w[i+2]<bound)types[w[i+2]]=w[i+1];
        if(op==43 && n==4 && !w[i+3]){if(w[i+1]==ut)uz=w[i+2];if(w[i+1]==it)iz=w[i+2];if(w[i+2]<bound && types[w[i+2]])zero[w[i+2]]=1;}
        if(op==46 && n==3 && w[i+2]<bound && types[w[i+2]])zero[w[i+2]]=1;
        i+=n;}
    for(uint32_t i=5;i<nw;){uint32_t n=w[i]>>16,op=w[i]&65535;
        if((op==65 || op==66) && n==6 && w[i+2]<bound && w[i+3]<bound && vars[w[i+3]]){ptrs[w[i+2]]=vars[w[i+3]];indices[w[i+2]]=w[i+5];}
        if(op==61 && n>=4 && w[i+1]==ut && w[i+3]<bound && ptrs[w[i+3]]){uint32_t index=indices[w[i+3]];
            if(index<bound && (types[index]==ut || (it && types[index]==it))){patch[i]=ptrs[w[i+3]];found|=1ull<<(patch[i]-1);loads++;}}
        i+=n;}
    // Retained fragment helpers take their index by pointer. Resolve the tiny
    // pure word accessor and bypass calls immediately preceded by argument=0.
    // This exposes the specialization constant in the caller, before driver
    // inlining; a generic select inside the accessor was too late to prune its
    // callers' virtual sampling trees during real material compilation.
    uint32_t function=0;
    for(uint32_t i=5;i<nw;){uint32_t n=w[i]>>16,op=w[i]&65535;
        if(op==54 && n==5){function=w[i+2];if(function>=bound)goto fail;simple[function]=w[i+1]==ut;}
        if(op==55 && function){if(param_count[function]<255)param_count[function]++;parameter[function]=w[i+2];}
        if(function && op!=54 && op!=55 && op!=248 && op!=61 && op!=65 && op!=66 && op!=83 && op!=254 && op!=56 && op!=8 && op!=317)simple[function]=0;
        if(op==61 && n>=4 && w[i+2]<bound && w[i+3]<bound){loaded_from[w[i+2]]=w[i+3];if(ptrs[w[i+3]]){value_slot[w[i+2]]=ptrs[w[i+3]];value_index[w[i+2]]=indices[w[i+3]];}}
        if(op==83 && n==4 && w[i+2]<bound && w[i+3]<bound){loaded_from[w[i+2]]=loaded_from[w[i+3]];value_slot[w[i+2]]=value_slot[w[i+3]];value_index[w[i+2]]=value_index[w[i+3]];zero[w[i+2]]=zero[w[i+3]];}
        if(op==254 && n==2 && function){uint32_t value=w[i+1];if(value<bound && value_slot[value] && value_index[value]<bound && (value_index[value]==parameter[function] || loaded_from[value_index[value]]==parameter[function]))fn_slot[function]=value_slot[value];else simple[function]=0;}
        if(op==56)function=0;i+=n;
    }
    uint32_t previous=0;
    for(uint32_t i=5;i<nw;){uint32_t n=w[i]>>16,op=w[i]&65535;
        if(op==57 && n==5 && w[i+1]==ut && w[i+3]<bound && w[i+4]<bound){uint32_t fn=w[i+3],arg=w[i+4];int literal_zero=zero[arg];
            if(previous && (w[previous]&65535)==62 && w[previous]>>16==3 && w[previous+1]==arg && w[previous+2]<bound && zero[w[previous+2]])literal_zero=1;
            if(simple[fn] && param_count[fn]==1 && fn_slot[fn] && literal_zero){patch[i]=256u|fn_slot[fn];found|=1ull<<(fn_slot[fn]-1);loads++;}}
        if(op!=8 && op!=317)previous=i;i+=n;
    }
    if(!loads)goto fail;
    uint32_t specs[64]={0};for(unsigned b=0;b<64;b++)if(found>>b&1)specs[b]=next++;
    int new_bool=!bt,new_uz=!uz,new_iz=it && !iz;if(new_bool)bt=next++;if(new_uz)uz=next++;if(new_iz)iz=next++;
    uint64_t capacity=(uint64_t)nw+16+8*64+(uint64_t)loads*11;if(capacity>SIZE_MAX/4)goto fail;
    uint32_t *out=malloc((size_t)capacity*4);if(!out)goto fail;memcpy(out,w,20);uint32_t no=5;int annotations=0,globals=0;
    for(uint32_t i=5;i<nw;){uint32_t n=w[i]>>16,op=w[i]&65535;
        if(!annotations && op>=19 && op<=39){for(unsigned b=0;b<64;b++)if(specs[b]){out[no++]=4u<<16|71;out[no++]=specs[b];out[no++]=1;out[no++]=VK_ATLAS_SPEC_BASE+b;}annotations=1;}
        if(!globals && op==54){
            if(new_bool){out[no++]=2u<<16|20;out[no++]=bt;}
            if(new_uz){out[no++]=4u<<16|43;out[no++]=ut;out[no++]=uz;out[no++]=0;}
            if(new_iz){out[no++]=4u<<16|43;out[no++]=it;out[no++]=iz;out[no++]=0;}
            for(unsigned b=0;b<64;b++)if(specs[b]){out[no++]=4u<<16|50;out[no++]=ut;out[no++]=specs[b];out[no++]=0;}globals=1;
        }
        if(patch[i]){
            // Adreno 840 rejects an OpCopyObject whose source is a pipeline
            // specialization constant in these retained fragment helpers.
            // Integer addition of zero preserves the exact uint value and
            // exposes the same constant without that compiler failure.
            if(patch[i]&256){out[no++]=5u<<16|128;out[no++]=ut;out[no++]=w[i+2];out[no++]=specs[(patch[i]&255)-1];out[no++]=uz;i+=n;continue;}
            uint32_t original=w[i+2],index=indices[w[i+3]],loaded=next++,test=next++;
            memcpy(out+no,w+i,n*4);out[no+2]=loaded;no+=n;
            out[no++]=5u<<16|170;out[no++]=bt;out[no++]=test;out[no++]=index;out[no++]=types[index]==ut?uz:iz;
            out[no++]=6u<<16|169;out[no++]=ut;out[no++]=original;out[no++]=test;out[no++]=specs[patch[i]-1];out[no++]=loaded;
        }else{memcpy(out+no,w+i,n*4);no+=n;}
        i+=n;
    }
    if(!globals || !annotations){free(out);goto fail;}
    out[3]=next;*onw=no;*mask=found;free(vars);free(ptrs);free(indices);free(types);free(patch);free(zero);free(value_slot);free(fn_slot);free(simple);free(param_count);free(loaded_from);free(value_index);free(parameter);return out;
fail:
    free(vars);free(ptrs);free(indices);free(types);free(patch);free(zero);free(value_slot);free(fn_slot);free(simple);free(param_count);free(loaded_from);free(value_index);free(parameter);return NULL;
}
