#version 450
layout(binding=0) uniform sampler2DArray fp_t_tcb_8;
layout(binding=1) uniform sampler2DArray fp_t_tcb_A;
layout(binding=2,std140) uniform fp_c3 { vec4 derivatives; vec4 origin; vec4 options; } params;
layout(location=0) out vec4 result;
float difference(float a,float b){return a==b?0.0:abs(a-b);}
void main(){
    vec2 p=params.origin.xy+params.derivatives.xy*gl_FragCoord.x+params.derivatives.zw*gl_FragCoord.y;
    vec3 coordinate=vec3(p,params.origin.z);
    vec4 actual,expected;
    if(params.options.x==0.0){actual=texture(fp_t_tcb_8,coordinate);expected=texture(fp_t_tcb_A,coordinate);}
    else{actual=texture(fp_t_tcb_8,coordinate,params.options.y);expected=texture(fp_t_tcb_A,coordinate,params.options.y);}
    vec2 aq=textureQueryLod(fp_t_tcb_8,p),eq=textureQueryLod(fp_t_tcb_A,p);
    vec4 delta=abs(actual-expected);
    result=vec4(max(max(delta.x,delta.y),max(delta.z,delta.w)),difference(aq.x,eq.x),difference(aq.y,eq.y),actual.r+actual.g+actual.b);
}
