#!/usr/bin/env python3
"""Diagnostic native K16 packing for two complete logical warps on wave64.

Retains the caller's texture, weight and output code. Two 16x8 guest products
occupy diagonal blocks of one 64x16 native product; unused rows are padded.
Native half arithmetic differs from the production FMA helper. Only converged
top-level calls in workgroups made of complete 64-lane subgroups are accepted.
"""
import argparse
import json
from pathlib import Path
import re
import subprocess

import hmma_shuffle


def helper(groups):
    return f'''
shared float16_t dm_native_a[{groups*1024}],dm_native_b[{groups*256}];
shared float16_t dm_native_c[{groups*1024}],dm_native_d[{groups*1024}];
int dmsh_hmma16816_f16(int logical_lane,int scratch_base,
    int a0,int a1,int a2,int a3,int b0,int b1,int c0,int c1,out int d1) {{
    uint physical=gl_SubgroupInvocationID,warp=physical/32;
    uint g=uint(logical_lane)/4,t=uint(logical_lane)%4;
    uint abase=gl_SubgroupID*1024,bbase=gl_SubgroupID*256;
    for(uint i=physical;i<1024;i+=64){{dm_native_a[abase+i]=float16_t(0);dm_native_c[abase+i]=float16_t(0);}}
    subgroupMemoryBarrierShared();subgroupBarrier();
    int ar[4]=int[4](a0,a1,a2,a3);
    int br[2]=int[2](b0,b1),cr[2]=int[2](c0,c1);
    for(uint word=0;word<4;word++){{
        vec2 v=unpackHalf2x16(uint(ar[word]));
        uint row=warp*16+g+(word%2)*8,k=t*2+(word/2)*8;
        dm_native_a[abase+row*16+k]=float16_t(v.x);
        dm_native_a[abase+row*16+k+1]=float16_t(v.y);
    }}
    for(uint word=0;word<2;word++){{
        vec2 bv=unpackHalf2x16(uint(br[word])),cv=unpackHalf2x16(uint(cr[word]));
        uint k=t*2+word*8,col=warp*8+g;
        dm_native_b[bbase+k*16+col]=float16_t(bv.x);
        dm_native_b[bbase+(k+1)*16+col]=float16_t(bv.y);
        uint row=warp*16+g+word*8;col=warp*8+t*2;
        dm_native_c[abase+row*16+col]=float16_t(cv.x);
        dm_native_c[abase+row*16+col+1]=float16_t(cv.y);
    }}
    subgroupMemoryBarrierShared();subgroupBarrier();
    coopmat<float16_t,gl_ScopeSubgroup,64,16,gl_MatrixUseA> a;
    coopmat<float16_t,gl_ScopeSubgroup,16,16,gl_MatrixUseB> b;
    coopmat<float16_t,gl_ScopeSubgroup,64,16,gl_MatrixUseAccumulator> c,d;
    coopMatLoad(a,dm_native_a,abase,16,gl_CooperativeMatrixLayoutRowMajor);
    coopMatLoad(b,dm_native_b,bbase,16,gl_CooperativeMatrixLayoutRowMajor);
    coopMatLoad(c,dm_native_c,abase,16,gl_CooperativeMatrixLayoutRowMajor);
    d=coopMatMulAdd(a,b,c);
    coopMatStore(d,dm_native_d,abase,16,gl_CooperativeMatrixLayoutRowMajor);
    subgroupMemoryBarrierShared();subgroupBarrier();
    uint low=abase+(warp*16+g)*16+warp*8+t*2,high=low+8*16;
    vec2 lo=vec2(dm_native_d[low],dm_native_d[low+1]);
    vec2 hi=vec2(dm_native_d[high],dm_native_d[high+1]);
    subgroupMemoryBarrierShared();subgroupBarrier();
    d1=int(packHalf2x16(hi));return int(packHalf2x16(lo));
}}
'''


def compose(source, local):
    threads = local[0]*local[1]*local[2]
    if not threads or threads % 64 or threads > 128:
        raise ValueError('requires one or two complete wave64 subgroups')
    match = re.search(r'\bint dmsh_hmma16816_f16\([^;]*?\)\s*\{', source)
    if not match:
        raise ValueError('original matrix helper required')
    end = match.end()
    depth = 1
    while depth:
        if end >= len(source):
            raise ValueError('unterminated matrix helper')
        depth += (source[end]=='{')-(source[end]=='}')
        end += 1
    main = source.index('void main()')
    # A top-level call can still be divergent after an early return. Reject
    # termination conservatively rather than attempting control-flow analysis.
    if re.search(r'\b(return|discard|demote|terminateInvocation)\b', source[main:]):
        raise ValueError('native helper rejects early exits from main')
    if 'dmsh_hmma16816_f16(' in source[end:main]:
        raise ValueError('matrix calls outside main are unsupported')
    level = 0
    calls = 0
    for line in source[main:].splitlines():
        if 'dmsh_hmma16816_f16(' in line:
            if level != 1:
                raise ValueError('native helper requires top-level converged calls')
            calls += 1
        level += line.count('{')-line.count('}')
    if not calls:
        raise ValueError('no top-level matrix calls')
    source = source[:match.start()]+helper(threads//64)+source[end:]
    for ext in ('GL_KHR_cooperative_matrix', 'GL_EXT_shader_explicit_arithmetic_types_float16',
                'GL_KHR_memory_scope_semantics', 'GL_KHR_shader_subgroup_basic'):
        source = source.replace('#version 460', f'#version 460\n#extension {ext} : require', 1)
    return source, calls


def build(binary, output):
    m = hmma_shuffle.hmma_spv.Module(Path(binary).read_bytes())
    if hmma_shuffle.hmma_spv.hmma_helper(m) is None:
        raise ValueError('input is outside the original scalar helper contract')
    local = next(x[3:6] for x in m.ins if x[0]&65535==16 and x[2]==17)
    source = subprocess.check_output([str(hmma_shuffle.CROSS), str(binary), '--vulkan-semantics', '--version', '460'], text=True)
    source, calls = compose(source, local)
    result = hmma_shuffle.compile_source(source, output, compact=False)
    result.update(local=local, source_calls=calls, arithmetic='native half-product/half-add', diagnostic_only=True)
    return result


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('input', type=Path)
    p.add_argument('output', type=Path)
    a = p.parse_args()
    print(json.dumps(build(a.input, a.output), indent=2))
