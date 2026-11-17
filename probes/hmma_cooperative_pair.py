#!/usr/bin/env python3
"""Diagnostic paired HMMA tiles for four logical warps in a 128-thread group.

The caller must independently establish the selected cross-warp sharing. The
verification build checks that condition for every invocation and call at binding
31. Native half arithmetic remains different from the production FMA helper.
This tool does not modify production translation or change the workgroup size.
"""
import argparse
import json
from pathlib import Path
import re
import subprocess

import hmma_cooperative
import hmma_shuffle

DECLARATIONS = '''
shared float16_t dm_pair_a[1024],dm_pair_b[256],dm_pair_c[1024],dm_pair_d[1024];
#ifdef VERIFY_PAIR_SHARING
layout(set=0,binding=31,std430) buffer PairFaults { uint words[]; } dm_pair_faults;
shared uvec4 dm_pair_check[128];
uint dm_pair_sequence=0;
#endif
'''


def helper(mode, scope='workgroup'):
    if mode not in 'ab' or len(mode) != 1:
        raise ValueError('sharing must be a or b')
    common = '''
void dm_paired_MODE(int a0,int a1,int a2,int a3,
    int b00,int b01,int b10,int b11,int c00,int c01,int c10,int c11,
    out int d00,out int d01,out int d10,out int d11) {
    uint index=gl_LocalInvocationIndex,warp=index/32,g=(index%32)/4,t=index%4;
    int ar[4]=int[4](a0,a1,a2,a3);
    int br[4]=int[4](b00,b01,b10,b11),cr[4]=int[4](c00,c01,c10,c11);
#ifdef VERIFY_PAIR_SHARING
    dm_pair_check[index]=CHECK;
    barrier();
    if(any(notEqual(dm_pair_check[index],dm_pair_check[index%32])))
        atomicOr(dm_pair_faults.words[dm_pair_sequence],1);
    if(index==0)atomicAdd(dm_pair_faults.words[64+dm_pair_sequence],1);
    dm_pair_sequence++;
    barrier();
#endif
PACK
    barrier();
    if(gl_SubgroupID==0) {
        coopmat<float16_t,gl_ScopeSubgroup,64,16,gl_MatrixUseA> a;
        coopmat<float16_t,gl_ScopeSubgroup,16,16,gl_MatrixUseB> b;
        coopmat<float16_t,gl_ScopeSubgroup,64,16,gl_MatrixUseAccumulator> c,d;
        coopMatLoad(a,dm_pair_a,0,16,gl_CooperativeMatrixLayoutRowMajor);
        coopMatLoad(b,dm_pair_b,0,16,gl_CooperativeMatrixLayoutRowMajor);
        coopMatLoad(c,dm_pair_c,0,16,gl_CooperativeMatrixLayoutRowMajor);
        d=coopMatMulAdd(a,b,c);
        coopMatStore(d,dm_pair_d,0,16,gl_CooperativeMatrixLayoutRowMajor);
    }
    barrier();
    int result[4];
    for(uint j=0;j<2;j++)for(uint word=0;word<2;word++) {
        uint offset=OFFSET;
        result[j*2+word]=int(packHalf2x16(vec2(dm_pair_d[offset],dm_pair_d[offset+STEP])));
    }
    d00=result[0];d01=result[1];d10=result[2];d11=result[3];
    barrier();
}
'''
    if mode == 'a':
        pack = '''
    for(uint j=0;j<2;j++)for(uint word=0;word<2;word++) {
        vec2 bv=unpackHalf2x16(uint(br[j*2+word])),cv=unpackHalf2x16(uint(cr[j*2+word]));
        uint row=warp*16+j*8+g,k=t*2+word*8;
        dm_pair_a[row*16+k]=float16_t(bv.x);dm_pair_a[row*16+k+1]=float16_t(bv.y);
        row=warp*16+j*8+t*2;uint col=g+word*8;
        dm_pair_c[row*16+col]=float16_t(cv.x);dm_pair_c[(row+1)*16+col]=float16_t(cv.y);
    }
    if(warp==0)for(uint word=0;word<4;word++) {
        vec2 av=unpackHalf2x16(uint(ar[word]));
        uint col=g+(word%2)*8,k=t*2+(word/2)*8;
        dm_pair_b[k*16+col]=float16_t(av.x);dm_pair_b[(k+1)*16+col]=float16_t(av.y);
    }
'''
        check = 'uvec4(a0,a1,a2,a3)'
        offset, step = '(warp*16+j*8+t*2)*16+g+word*8', '16'
    else:
        pack = '''
    for(uint word=0;word<4;word++) {
        vec2 av=unpackHalf2x16(uint(ar[word]));
        uint row=warp*16+g+(word%2)*8,k=t*2+(word/2)*8;
        dm_pair_a[row*16+k]=float16_t(av.x);dm_pair_a[row*16+k+1]=float16_t(av.y);
    }
    for(uint j=0;j<2;j++)for(uint word=0;word<2;word++) {
        vec2 bv=unpackHalf2x16(uint(br[j*2+word])),cv=unpackHalf2x16(uint(cr[j*2+word]));
        uint row=warp*16+g+word*8,col=j*8+t*2;
        dm_pair_c[row*16+col]=float16_t(cv.x);dm_pair_c[row*16+col+1]=float16_t(cv.y);
        if(warp==0) {
            uint k=t*2+word*8;col=j*8+g;
            dm_pair_b[k*16+col]=float16_t(bv.x);dm_pair_b[(k+1)*16+col]=float16_t(bv.y);
        }
    }
'''
        check = 'uvec4(b00,b01,b10,b11)'
        offset, step = '(warp*16+g+word*8)*16+j*8+t*2', '1'
    source = common.replace('MODE', mode).replace('CHECK', check).replace('PACK', pack).replace('OFFSET', offset).replace('STEP', step)
    if scope == 'subgroup':
        source = source.replace('index=gl_LocalInvocationIndex,warp=index/32,g=(index%32)/4,t=index%4;',
                                'index=gl_LocalInvocationIndex,physical=gl_SubgroupInvocationID,warp=physical/32,g=(physical%32)/4,t=physical%4;\n'
                                '    uint abase=gl_SubgroupID*1024,bbase=gl_SubgroupID*256;')
        source = source.replace('dm_pair_check[index%32]', 'dm_pair_check[(index&~63u)+(index%32)]')
        source = source.replace('if(index==0)', 'if(physical==0)')
        source = source.replace('#endif', '#endif\n    for(uint i=512+physical;i<1024;i+=64){dm_pair_a[i]=float16_t(0);dm_pair_c[i]=float16_t(0);}')
        for name in ('a', 'b', 'c', 'd'):
            base = 'bbase' if name == 'b' else 'abase'
            source = source.replace(f'dm_pair_{name}[', f'dm_pair_{name}[{base}+')
            source = source.replace(f'dm_pair_{name},0,16,', f'dm_pair_{name},{base},16,')
        source = source.replace('if(gl_SubgroupID==0)', '')
        source = source.replace('barrier();', 'subgroupMemoryBarrierShared();subgroupBarrier();')
    elif scope != 'workgroup':
        raise ValueError('scope must be workgroup or subgroup')
    return source


def compose(source, local, sharing, verify=False, scope='workgroup'):
    # Reuse the conservative top-level call/early-exit admission check.
    hmma_cooperative.compose(source, local)
    if list(local) != [128, 1, 1] or not sharing or any(m not in 'ab' for m in sharing):
        raise ValueError('requires local 128x1x1 and explicit a/b sharing per pair')
    if verify and re.search(r'\bbinding\s*=\s*31\b', source):
        raise ValueError('verification binding already used')
    main = source.index('void main()')
    lines = source[main:].splitlines()
    call = re.compile(r'    int (\w+) = dmsh_hmma16816_f16\(([^;]*)\);$')
    positions = [i for i, line in enumerate(lines) if call.fullmatch(line)]
    if len(positions) < len(sharing)*2 or len(sharing) > 64:
        raise ValueError('not enough adjacent calls or too many pairs')
    # Resolve only immutable scalar aliases/bitcasts. This is deliberately not
    # an expression optimizer; mutable source is outside the admitted contract.
    aliases = {}
    mutable = {m[1] for line in lines
               if (m := re.match(r'\s*(\w+)\s*(?:[+*/&|^-]?=|\+\+|--)', line))}

    def value(text):
        while text in aliases and aliases[text] != text:
            text = aliases[text]
        return text

    snapshots = {}
    for i, line in enumerate(lines):
        m = call.fullmatch(line)
        if m:
            args = m[2].split(', ')
            snapshots[i] = (m[1], args, tuple(value(a) for a in args[2:6]))
        else:
            m = re.fullmatch(r'    (?:int|uint|float) (\w+) = (.*);', line)
            if m:
                if m[1] in aliases:
                    raise ValueError('reassigned scalar outside immutable alias contract')
                cast = re.fullmatch(r'(?:floatBitsToInt|intBitsToFloat|floatBitsToUint|uintBitsToFloat)\((\w+)\)', m[2])
                expression = cast[1] if cast else m[2]
                if m[1] not in mutable and not set(re.findall(r'\b\w+\b', expression)) & mutable:
                    aliases[m[1]] = value(expression)
    for pair, mode in enumerate(sharing):
        first, second = positions[pair*2:pair*2+2]
        low, a, av = snapshots[first]
        high, b, bv = snapshots[second]
        if av != bv:
            raise ValueError('paired calls must use the same four A fragments')
        if len({low, high, a[10], b[10]}) != 4:
            raise ValueError('paired output variables must be distinct')
        # Moving the first call past intervening scalar setup is permitted only
        # when its results are untouched until the pair. Defer direct aliases.
        deferred = []
        results = {low, a[10]}
        for i in range(first+1, second):
            used = set(re.findall(r'\b\w+\b', lines[i])) & results
            if used:
                alias = re.fullmatch(r'    int (\w+) = (\w+);', lines[i])
                if not alias or alias[2] not in results:
                    raise ValueError('first result used before second call')
                deferred.append(lines[i])
                results.add(alias[1])
                lines[i] = ''
            elif not re.fullmatch(r'    (?:int|uint|float) \w+(?: = [^;{}]+)?;', lines[i]):
                raise ValueError('side effect or control flow between paired calls')
            else:
                pure = {'int', 'uint', 'float', 'floatBitsToInt', 'intBitsToFloat',
                        'floatBitsToUint', 'uintBitsToFloat', 'bitfieldExtract'}
                functions = set(re.findall(r'\b(\w+)\s*\(', lines[i]))
                if functions - pure:
                    raise ValueError('unknown function between paired calls')
        if set(b) & results:
            raise ValueError('second call depends on first result')
        lines[first] = f'    int {low};'
        args = a[2:6]+a[6:8]+b[6:8]+a[8:10]+b[8:10]+[low, a[10], high, b[10]]
        lines[second] = f'    int {high};\n    dm_paired_{mode}('+','.join(args)+');\n'+'\n'.join(deferred)
    declarations = DECLARATIONS
    if scope == 'subgroup':
        declarations = declarations.replace('[1024]', '[2048]').replace('[256]', '[512]')
    declarations += ''.join(helper(mode, scope) for mode in sorted(set(sharing)))
    source = source[:main]+declarations+'\n'.join(lines)+'\n'
    extensions = ('GL_KHR_cooperative_matrix', 'GL_EXT_shader_explicit_arithmetic_types_float16',
                  'GL_KHR_memory_scope_semantics', 'GL_KHR_shader_subgroup_basic')
    for ext in extensions:
        source = source.replace('#version 460', f'#version 460\n#extension {ext} : require', 1)
    if verify:
        source = source.replace('#version 460', '#version 460\n#define VERIFY_PAIR_SHARING 1', 1)
    return source


def build(binary, output, sharing, verify=False, scope='workgroup'):
    m = hmma_shuffle.hmma_spv.Module(Path(binary).read_bytes())
    if hmma_shuffle.hmma_spv.hmma_helper(m) is None:
        raise ValueError('requires the original scalar helper contract')
    local = next(x[3:6] for x in m.ins if x[0]&65535 == 16 and x[2] == 17)
    source = subprocess.check_output([str(hmma_shuffle.CROSS), str(binary), '--vulkan-semantics', '--version', '460'], text=True)
    source = compose(source, local, sharing, verify, scope)
    result = hmma_shuffle.compile_source(source, output, compact=False)
    result.update(pairs=len(sharing), sharing=sharing, verified_build=verify, local=local, scope=scope,
                  arithmetic='native half-product/half-add; remaining calls retain scalar arithmetic', diagnostic_only=True)
    return result


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('input', type=Path)
    p.add_argument('output', type=Path)
    p.add_argument('--sharing', required=True)
    p.add_argument('--verify', action='store_true')
    p.add_argument('--scope', choices=('workgroup', 'subgroup'), default='workgroup')
    a = p.parse_args()
    print(json.dumps(build(a.input, a.output, a.sharing, a.verify, a.scope), indent=2))
