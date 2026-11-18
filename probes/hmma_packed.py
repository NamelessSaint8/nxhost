#!/usr/bin/env python3
"""Diagnostic HMMA helper with packed operands and bounded lifetimes.

The default retains FMA32 order, both results and direct half packing. Explicit
FMA16 and separate half-product/add models change arithmetic. No production
translation rule changes. GPU bit and independent model comparisons are required.
"""
import argparse
import json
from pathlib import Path
import re
import subprocess

import hmma_shuffle


def helper(words, mode='packed', unroll=False, arithmetic='fma32'):
    if mode not in ('packed', 'stream') or words < 256 or words%4:
        raise ValueError('requires packed/stream mode and whole scratch vectors')
    if arithmetic not in ('fma32', 'fma16', 'muladd16'):
        raise ValueError('unknown arithmetic model')
    preload = ''
    if mode == 'packed':
        for name, row in (('a', 'g'), ('b', 'g+8u'), ('c', '16u+t*2u'), ('d', '17u+t*2u')):
            preload += f'    uvec4 w_{name}0=dm_packed_rows[base+({row})*2u],w_{name}1=dm_packed_rows[base+({row})*2u+1u];\n'
        preload += '    subgroupMemoryBarrierShared();subgroupBarrier();\n'
        values = '\n'.join(f'        vec2 {name}v=unpackHalf2x16((pair<4u?w_{name}0:w_{name}1)[pair&3u]);' for name in 'abcd')
        finish = ''
    else:
        values = '\n'.join(f'        vec2 {name}v=unpackHalf2x16(dm_packed_rows[base+({row})*2u+pair/4u][pair&3u]);'
                           for name, row in (('a', 'g'), ('b', 'g+8u'), ('c', '16u+t*2u'), ('d', '17u+t*2u')))
        finish = '    subgroupMemoryBarrierShared();subgroupBarrier();\n'
    source = f'''
shared uvec4 dm_packed_rows[{words//4}];
int dmsh_hmma16816_f16(int lane,int scratch,int a0,int a1,int a2,int a3,
    int b0,int b1,int c0,int c1,out int d1) {{
    uint g=uint(lane)>>2u,t=uint(lane)&3u,base=uint(scratch)>>2u;
    precise vec4 acc=vec4(unpackHalf2x16(uint(c0)),unpackHalf2x16(uint(c1)));
    dm_packed_rows[base+g*2u][t]=uint(a0);
    dm_packed_rows[base+(g+8u)*2u][t]=uint(a1);
    dm_packed_rows[base+g*2u+1u][t]=uint(a2);
    dm_packed_rows[base+(g+8u)*2u+1u][t]=uint(a3);
    dm_packed_rows[base+(16u+g)*2u][t]=uint(b0);
    dm_packed_rows[base+(16u+g)*2u+1u][t]=uint(b1);
    subgroupMemoryBarrierShared();subgroupBarrier();
{preload}
    [[{'unroll' if unroll else 'dont_unroll'}]]
    for(uint pair=0;pair<8u;pair++) {{
{values}
        acc=fma(vec4(av.x,av.x,bv.x,bv.x),vec4(cv.x,dv.x,cv.x,dv.x),acc);
        acc=fma(vec4(av.y,av.y,bv.y,bv.y),vec4(cv.y,dv.y,cv.y,dv.y),acc);
    }}
{finish}
    d1=int(packHalf2x16(acc.zw));
    return int(packHalf2x16(acc.xy));
}}
'''
    if arithmetic != 'fma32':
        source = source.replace('precise vec4 acc=vec4(', 'precise f16vec4 acc=f16vec4(')
        source = re.sub(r'vec2 ([abcd]v)=unpackHalf2x16\(([^;]*)\);', r'f16vec2 \1=f16vec2(unpackHalf2x16(\2));', source)
        source = source.replace('fma(vec4(', 'fma(f16vec4(').replace('),vec4(', '),f16vec4(')
        source = source.replace('packHalf2x16(acc.zw)', 'packHalf2x16(vec2(acc.zw))').replace('packHalf2x16(acc.xy)', 'packHalf2x16(vec2(acc.xy))')
        if arithmetic == 'muladd16':
            source = source.replace('acc=fma(', 'precise f16vec4 product=')
            source = source.replace('),f16vec4(', ')*f16vec4(').replace('),acc);', ');acc=acc+product;')
            source = source.replace('        precise f16vec4 product=', '        { precise f16vec4 product=').replace('acc=acc+product;', 'acc=acc+product; }')
    return source


def compose(source, words, mode='packed', unroll=False, arithmetic='fma32'):
    matches = list(re.finditer(r'\bint dmsh_hmma16816_f16\([^;]*?\)\s*\{', source))
    if len(matches) != 1 or re.search(r'\bdm_packed_rows\b', source):
        raise ValueError('requires one helper and an unused packed scratch name')
    start = matches[0].start()
    end = matches[0].end()
    depth = 1
    while depth:
        if end >= len(source):
            raise ValueError('unterminated helper')
        depth += (source[end]=='{')-(source[end]=='}')
        end += 1
    source = source[:start]+helper(words, mode, unroll, arithmetic)+source[end:]
    for ext in ('GL_KHR_shader_subgroup_basic', 'GL_EXT_control_flow_attributes',
                *(['GL_EXT_shader_explicit_arithmetic_types_float16'] if arithmetic!='fma32' else [])):
        if f'#extension {ext} :' not in source:
            source = source.replace('#version 460', f'#version 460\n#extension {ext} : require', 1)
    return source


def build(binary, output, mode='packed', unroll=False, arithmetic='fma32'):
    if Path(binary).resolve()==Path(output).resolve():
        raise ValueError('refusing to overwrite source module')
    module = hmma_shuffle.hmma_spv.Module(Path(binary).read_bytes())
    if not module.entry or module.entry[1]!=5:
        raise ValueError('requires a compute module')
    contract = hmma_shuffle.hmma_spv.hmma_helper(module)
    if contract is None:
        raise ValueError('requires the original scalar matrix helper contract')
    array = module.pointee(module.vars[contract['scratch']][0])[1]
    words = module.consts[module.types[array][3]][1][0]
    source = subprocess.check_output([str(hmma_shuffle.CROSS), str(binary), '--vulkan-semantics', '--version', '460'], text=True)
    result = hmma_shuffle.compile_source(compose(source, words, mode, unroll, arithmetic), output)
    result.update(mode=mode, unroll=unroll, scratch_words=words, diagnostic_only=True,
                  arithmetic=arithmetic, changes_arithmetic=arithmetic!='fma32')
    return result


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('input', type=Path)
    p.add_argument('output', type=Path)
    p.add_argument('--mode', choices=('packed', 'stream'), default='packed')
    p.add_argument('--unroll', action='store_true')
    p.add_argument('--arithmetic', choices=('fma32', 'fma16', 'muladd16'), default='fma32')
    a = p.parse_args()
    print(json.dumps(build(a.input, a.output, a.mode, a.unroll, a.arithmetic), indent=2))
