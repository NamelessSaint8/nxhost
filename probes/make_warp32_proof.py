#!/usr/bin/env python3
"""Translate synthetic Ampere warp operations for vk_warp32.c; no game inputs.

make_warp32_proof.py OUT [--xlate TRANSLATOR]
Writes Vulkan shaders, CPU reference words, and a manifest. Safe legacy wave32
controls must disagree on a wider physical subgroup; legacy HMMA is not run.
"""
import argparse
import json
from pathlib import Path
import re
import struct
import subprocess

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / 'nxnative/dm/gfx/tools'
HALF_PATTERNS = (0x1400,0x2c00,0x0400,0x3555,0x3801,0x3c01,0xbc01,0x4bff,0xbbff,0x9000,0x0000,0x3bff)
DENORM_PATTERNS = (0x0001,0x03ff,0x0400,0x3555,0x3801,0x3c01,0xbc01,0x4bff,0xbbff,0x8001,0x0000,0x3bff)


def inst(hi, lo):
    return struct.pack('<QQ', lo, hi)


def sreg(rd, sr):
    return inst(0x000fe20000000000 | sr << 8, 0x7919 | rd << 16)


def mov(rd, value):
    return inst(0x000fc60000000f00, value << 32 | rd << 16 | 0x7802)


def store(offset, rb):
    return inst(0x000fe80000000800, offset << 40 | rb << 32 | 255 << 24 | 0x7388)


def varied_matrix_reference(fractional=False,denormal=False):
    """Independent matrix product; fractional halves accumulate through CPU fmaf."""
    if fractional:
        import ctypes
        import ctypes.util
        fma = ctypes.CDLL(ctypes.util.find_library('m') or None).fmaf
        fma.argtypes = [ctypes.c_float]*3
        fma.restype = ctypes.c_float
    result = [0] * 128
    patterns=DENORM_PATTERNS if denormal else HALF_PATTERNS
    for warp in range(2):
        a = [[0] * 16 for _ in range(16)]
        b = [[0] * 8 for _ in range(16)]
        c = [[0] * 8 for _ in range(16)]
        for lane in range(32):
            g, t = lane // 4, lane % 4
            def value(word, half):
                if fractional:
                    bits=patterns[((warp*32+lane)*3+word*5+half*7)%len(patterns)]
                    return struct.unpack('<e',struct.pack('<H',bits))[0]
                return ((warp * 32 + lane) * 3 + word * 5 + half * 7) % 11 - 5
            for word in range(4):
                for half in range(2):
                    a[g + 8 * (word & 1)][2 * t + 8 * (word >> 1) + half] = value(word, half)
            for word in range(2):
                for half in range(2):
                    b[2 * t + 8 * word + half][g] = value(4 + word, half)
                    c[g + 8 * word][2 * t + half] = value(6 + word, half)
        for lane in range(32):
            g, t = lane // 4, lane % 4
            for word in range(2):
                row = g + 8 * word
                if fractional:
                    pair=[]
                    for half in range(2):
                        acc=c[row][2*t+half]
                        for k in range(16):
                            acc=fma(a[row][k],b[k][2*t+half],acc)
                        pair.append(acc)
                else:
                    pair = [c[row][2 * t + half] + sum(a[row][k] * b[k][2 * t + half] for k in range(16)) for half in range(2)]
                result[word * 64 + warp * 32 + lane] = struct.unpack('<I', struct.pack('<2e', *pair))[0]
    return result


def build(out, xlate, lower_hmma=False, reference_hmma=False, *, split_rows=False):
    lower_hmma = lower_hmma or split_rows
    out.mkdir(parents=True, exist_ok=True)
    end = inst(0x000fea0003800000, 0x794d)
    matrix = b''.join(mov(r, 0x3c003c00 if r < 12 else 0x40004000 if r < 14 else 0) for r in range(8, 16))
    # Rc occupies bits 64..71, size m16n8k16 is bit 75; accumulator F16.
    matrix += inst(0x000fe20000000800 | 14, 0x723c | 8 << 24 | 12 << 32)
    fixtures = {
        'lane': (sreg(0, 0) + store(0, 0), [i & 31 for i in range(64)]),
        'ldsm': (sreg(2, 33) + inst(0x000fe20000000000, 0x783b | 2 << 24) + store(0, 0),
                 [i | ((i + 1000) << 16) for i in range(64)]),
        'ldsm-transpose': (sreg(2, 33) + inst(0x000fe20000004000, 0x783b | 2 << 24) + store(0, 0),
                           [((i // 32) * 32 + (i % 4) * 8 + (i % 32) // 8 + (1000 if (i % 32) // 4 % 2 else 0))
                            | (((i // 32) * 32 + (i % 4) * 8 + 4 + (i % 32) // 8 + (1000 if (i % 32) // 4 % 2 else 0)) << 16)
                            for i in range(64)]),
        'movm': (sreg(2, 33) + inst(0x000fe20000000000, 0x723a | 2 << 24) + store(0, 0),
                 [(0 if (i & 31) // 4 & 1 else ((i // 32) * 32 + 4 * (2 * (i & 3)) + (i & 31) // 8)
                   | (((i // 32) * 32 + 4 * (2 * (i & 3) + 1) + (i & 31) // 8) << 16)) for i in range(64)]),
        'match': (sreg(2, 33) + inst(0x000fe200000e8000, 0x73a1 | 2 << 24) + store(0, 0),
                  [1 << (i & 31) for i in range(64)]),
        'redux': (sreg(2, 33) + inst(0x000fe2000000c000, 0x73c4 | 2 << 24)
                  + inst(0x000fe20000000000, 0x7c02 | 63 << 24) + store(0, 0),
                  [496 + (i // 32) * 1024 for i in range(64)]),
        'hmma': (matrix + store(0, 0) + store(256, 1), [0x50005000] * 128),
        'hmma-low': (matrix + store(0, 0), [0x50005000] * 64),
        'hmma-high': (matrix + store(0, 1), [0x50005000] * 64),
        'hmma-out-first': (matrix + store(0, 1) + store(256, 0), [0x50005000] * 128),
        'hmma-varied': (matrix + store(0, 0) + store(256, 1), varied_matrix_reference()),
    }
    if lower_hmma or reference_hmma:
        fixtures['hmma-fractional'] = (matrix + store(0,0) + store(256,1),varied_matrix_reference(True))
        fixtures['hmma-denorm'] = (matrix + store(0,0) + store(256,1),varied_matrix_reference(True,True))
        # Reuse and eviction across dependent matrix calls. Exact f16 integers
        # make the expected matrix product independent of the lowering.
        def hmma(rd, ra, rb, rc):
            return inst(0x000fe20000000800 | rc, 0x723c | rd << 16 | ra << 24 | rb << 32)
        init = b''.join(mov(r, 0x3c003c00 if r < 14 else 0x40004000) for r in range(8, 16))
        extra = b''.join(mov(r, 0x40004000) for r in range(16, 22))
        calls = [(8,12),(16,12),(8,12),(16,20),(8,20),(8,12)]
        product = 2 + 16 * (1 + 2 + 1 + 4 + 2 + 1)
        packed = struct.unpack('<I',struct.pack('<2e',product,product))[0]
        fixtures['hmma-reuse'] = (init + extra + b''.join(hmma(0,ra,rb,14 if i==0 else 0) for i,(ra,rb) in enumerate(calls)) + store(0,0) + store(256,1),[packed]*128)
        packed = struct.unpack('<I',struct.pack('<2e',154,154))[0]
        fixtures['hmma-alias'] = (init + hmma(8,8,12,14) + hmma(0,8,12,14) + store(0,0) + store(256,1),[packed]*128)
    jobs = []
    for name, (code, _) in fixtures.items():
        binary = out / (name + '.bin')
        binary.write_bytes(code + end)
        # The legacy HMMA path has out-of-range scratch accesses on wave64;
        # negative controls use only the safe lane/shuffle/reduction fixtures.
        for width in ((128,) if name.startswith(('hmma', 'ldsm-transpose')) else (32, 128)):
            jobs.append(dict(key=f'{name}-{width}', stage='cs', arch='sm86', code=str(binary),
                             debug=False, reduced=True, tex={}, img={}, attr={}, fout={},
                             local=[32, 2, 1], shared=512, nvn2_cs=[0, 0, 0, 0x40, 0], subgroup_size=width))
    (out / 'jobs.json').write_text(json.dumps(jobs))
    subprocess.run([str(xlate), str(out / 'jobs.json'), str(out)], check=True)
    manifest = []
    for job in jobs:
        name = job['key']
        spv = out / (name + '.spv')
        if lower_hmma and name.startswith('hmma'):
            import sys
            sys.path.insert(0,str(ROOT/'nxnative/dm/android/tools'))
            import hmma_spv
            binary, calls = hmma_spv.lower(spv.read_bytes(), split_rows=split_rows)
            assert calls == (6 if name.startswith('hmma-reuse') else 2 if name.startswith('hmma-alias') else 1)
            spv = out / (name + '.lowered.spv')
            spv.write_bytes(binary)
            subprocess.run(['spirv-val','--target-env','vulkan1.2',str(spv)],check=True)
        source = subprocess.run([str(TOOLS / 'spirv_cross_bin/spirv-cross'), str(spv),
                                 '--vulkan-semantics', '--version', '460'], check=True, capture_output=True, text=True).stdout
        # Capture STS results per invocation; the translated warp operation and
        # its scratch accesses remain untouched. The fixture's STS offsets are
        # constants 0 and (HMMA's second result) 64 words.
        shared = re.search(r'shared uint (\w+)\[128\];', source).group(1)
        if name in ('hmma-varied-128','hmma-fractional-128','hmma-denorm-128'):
            start = source.index('void main()')
            index = 0
            def fragment(match):
                nonlocal index
                word = index
                index += 1
                if name in ('hmma-fractional-128','hmma-denorm-128'):
                    patterns=DENORM_PATTERNS if name=='hmma-denorm-128' else HALF_PATTERNS
                    lo=f'dm_half_patterns[(gl_LocalInvocationIndex*3u+{word*5}u)%{len(patterns)}u]'
                    hi=f'dm_half_patterns[(gl_LocalInvocationIndex*3u+{word*5+7}u)%{len(patterns)}u]'
                    return f'    int {match[1]} = int({lo} | ({hi} << 16u));'
                halves = [f'float(int((gl_LocalInvocationIndex * 3u + {word * 5 + half * 7}u) % 11u) - 5)' for half in range(2)]
                return f'    int {match[1]} = int(packHalf2x16(vec2({halves[0]}, {halves[1]})));'
            main = re.sub(r'^    int (_\d+) = (?:1006648320|1073758208|0);$', fragment, source[start:], flags=re.M)
            assert index == 8, index
            source = source[:start] + main
            if name in ('hmma-fractional-128','hmma-denorm-128'):
                patterns=DENORM_PATTERNS if name=='hmma-denorm-128' else HALF_PATTERNS
                source=source.replace('void main()',f'const uint dm_half_patterns[{len(patterns)}] = uint[]('+','.join(f'{v}u' for v in patterns)+');\nvoid main()')
        if name.startswith('ldsm-'):
            source = source.replace('gl_LocalInvocationID.x', '((gl_LocalInvocationIndex & 7u) * 16u + (gl_LocalInvocationIndex >> 5u) * 128u)')
        elif not name.startswith('hmma-'):
            # Distinct input words across rows as well as across physical lanes.
            source = source.replace('gl_LocalInvocationID.x', 'gl_LocalInvocationIndex')
        source, stores = re.subn(r'\b' + shared + r'\[(0|64)\] =', lambda m: f'result.words[{m[1]} + gl_LocalInvocationIndex] =', source)
        assert stores == (2 if name in ('hmma-128', 'hmma-out-first-128', 'hmma-varied-128', 'hmma-reuse-128', 'hmma-alias-128','hmma-fractional-128','hmma-denorm-128') else 1), (name, stores)
        setup = ''
        if name.startswith('ldsm-'):
            # Each logical warp owns a separate 8x8 half matrix. Its first eight
            # lanes supply row addresses, just as LDSM requires.
            setup = f'for(uint j=gl_LocalInvocationIndex;j<128;j+=64) {shared}[j]=j|((j+1000u)<<16); barrier();\n'
        source = source.replace('void main()', 'layout(std430, binding=31) buffer Results { uint words[]; } result;\nvoid main()')
        source = source.replace('void main()', 'void translated_main()')
        expected = fixtures[name.rsplit('-', 1)[0]][1]
        source += '\nvoid main() { ' + setup + 'translated_main(); }\n'
        glsl = out / (name + '.comp')
        glsl.write_text(source)
        target = out / (name + '.vk.spv')
        subprocess.run(['glslangValidator', '-V', '--target-env', 'vulkan1.2', '-Os', '-S', 'comp', str(glsl), '-o', str(target)], check=True, capture_output=True)
        subprocess.run(['spirv-val', '--target-env', 'vulkan1.2', str(target)], check=True)
        (out / (name + '.expected')).write_bytes(struct.pack('<' + str(len(expected)) + 'I', *expected))
        mode=2 if name=='hmma-denorm-128' else 3 if name=='hmma-fractional-128' else int(job['subgroup_size']==32)
        manifest.append(f'{name} {len(expected)} {mode}')
    if lower_hmma or reference_hmma:
        import shutil
        reference=out
        if lower_hmma:
            reference=out/'scalar-reference'
            build(reference,xlate,False,True)
        for name in ('hmma-denorm-128','hmma-fractional-128'):
            shutil.copyfile(reference/(name+'.vk.spv'),out/(name+'.reference.vk.spv'))
    (out / 'manifest.tsv').write_text('\n'.join(manifest) + '\n')
    return len(manifest)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('out', type=Path)
    parser.add_argument('--xlate', type=Path, default=TOOLS / 'dmsh_xlate_bin/dmsh_xlate')
    parser.add_argument('--hmma-lds', action='store_true', help='exercise the Android vector-gather lowering, tile reuse and aliased fragments')
    parser.add_argument('--hmma-reference', action='store_true', help='generate the additional matrix cases with the original scalar helper')
    parser.add_argument('--split-rows', action='store_true', help='exercise the diagnostic split-row HMMA scratch layout')
    args = parser.parse_args()
    print('validated fixtures:', build(args.out.resolve(), args.xlate.resolve(), args.hmma_lds, args.hmma_reference,
                                      split_rows=args.split_rows))
