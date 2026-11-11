#version 450
layout(binding=0) uniform sampler2DArray fp_t_tcb_8;
layout(binding=1) uniform sampler2DArray fp_t_tcb_A;
layout(binding=2,std140) uniform fp_c3 { vec4 derivatives; vec4 origin; vec4 options; } params;
layout(location=0) out vec4 result;
void main(){
    vec2 uv=params.origin.xy+params.derivatives.xy*gl_FragCoord.x+params.derivatives.zw*gl_FragCoord.y;
    vec3 p=vec3(uv,params.origin.z);
    const ivec2 offset=ivec2(3,-2);
    const ivec2 offsets[4]=ivec2[4](ivec2(-2,-1),ivec2(2,-1),ivec2(-1,2),ivec2(2,1));
    const int component=2;
    int mode=int(params.options.x);vec4 a,b;
    if(mode==0){a=textureLodOffset(fp_t_tcb_8,p,params.options.y,offset);b=textureLodOffset(fp_t_tcb_A,p,params.options.y,offset);}
    else if(mode==1){a=textureOffset(fp_t_tcb_8,p,ivec2(-3,2));b=textureOffset(fp_t_tcb_A,p,ivec2(-3,2));}
    else if(mode==2){a=textureOffset(fp_t_tcb_8,p,offset,params.options.z);b=textureOffset(fp_t_tcb_A,p,offset,params.options.z);}
    else if(mode==3){
        ivec2 extent=textureSize(fp_t_tcb_A,0).xy;
        ivec3 q=ivec3(clamp(extent/2+ivec2(gl_FragCoord.xy)-16,ivec2(8),extent-9),int(p.z));
        a=texelFetchOffset(fp_t_tcb_8,q,0,offset);b=texelFetchOffset(fp_t_tcb_A,q,0,offset);
    }
    else if(mode==4){a=textureGather(fp_t_tcb_8,p);b=textureGather(fp_t_tcb_A,p);}
    else if(mode==5){a=textureGather(fp_t_tcb_8,p,1);b=textureGather(fp_t_tcb_A,p,1);}
    else if(mode==6){a=textureGather(fp_t_tcb_8,p,component);b=textureGather(fp_t_tcb_A,p,component);}
    else if(mode==7){a=textureGather(fp_t_tcb_8,p,3);b=textureGather(fp_t_tcb_A,p,3);}
    else if(mode==8){a=textureGatherOffset(fp_t_tcb_8,p,offset);b=textureGatherOffset(fp_t_tcb_A,p,offset);}
    else if(mode==9){a=textureGatherOffset(fp_t_tcb_8,p,offset,component);b=textureGatherOffset(fp_t_tcb_A,p,offset,component);}
    else if(mode==10){a=textureGatherOffsets(fp_t_tcb_8,p,offsets,1);b=textureGatherOffsets(fp_t_tcb_A,p,offsets,1);}
    else{a=textureGatherOffsets(fp_t_tcb_8,p,offsets);b=textureGatherOffsets(fp_t_tcb_A,p,offsets);}
    vec4 delta=abs(a-b);result=vec4(max(max(delta.x,delta.y),max(delta.z,delta.w)),a.x,b.x,1);
}
