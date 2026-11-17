#!/usr/bin/env python3
"""Translate read/overwrite/use fixtures for vk_warp32; no game inputs.

Each invocation owns one shared word. Its first read must retain the old value
after the word is overwritten, including through arithmetic and a barrier.
The reference is the integer 17, independently of the translated expression.
"""
import argparse
import json
from pathlib import Path
import re
import struct
import subprocess

from make_warp32_proof import TOOLS, inst, mov, sreg, store


def build(out, xlate):
    out.mkdir(parents=True, exist_ok=True)
    jobs = []
    for barrier in (False, True):
        name = 'snapshot-barrier' if barrier else 'snapshot'
        # R2 is the invocation's byte address. LDS R4 must execute before STS
        # overwrites it with 99; its single use is the final output store.
        code = (sreg(2, 33) + mov(3, 17)
                + inst(0x000fe80000000800, 3 << 32 | 2 << 24 | 0x7388)
                + inst(0x000fe20000000800, 4 << 16 | 2 << 24 | 0x7984)
                + mov(3, 99)
                + inst(0x000fe80000000800, 3 << 32 | 2 << 24 | 0x7388))
        if barrier:
            code += inst(0x000fec0000000000, 0x0000000000007b1d)
        code += store(256, 4) + inst(0x000fea0003800000, 0x794d)
        binary = out / (name + '.bin')
        binary.write_bytes(code)
        jobs.append(dict(key=name, stage='cs', arch='sm86', code=str(binary),
                         debug=False, reduced=True, tex={}, img={}, attr={}, fout={},
                         local=[32, 2, 1], shared=512,
                         nvn2_cs=[0, 0, 0, 0x40, 0], subgroup_size=128))
    (out / 'jobs.json').write_text(json.dumps(jobs))
    subprocess.run([str(xlate), str(out / 'jobs.json'), str(out)], check=True)
    for job in jobs:
        name = job['key']
        source = subprocess.run([str(TOOLS / 'spirv_cross_bin/spirv-cross'),
                                 str(out / (name + '.spv')), '--vulkan-semantics'],
                                capture_output=True, text=True, check=True).stdout
        shared = re.search(r'shared uint (\w+)\[128\];', source).group(1)
        source = source.replace('gl_LocalInvocationID.x', '(gl_LocalInvocationIndex * 4u)')
        source, count = re.subn(r'\b' + shared + r'\[64\] =',
                               'result.words[gl_LocalInvocationIndex] =', source)
        if count != 1:
            raise ValueError('fixture must have exactly one result store')
        source = source.replace('void main()',
                                'layout(std430, binding=31) buffer Results { uint words[]; } result;\nvoid main()')
        glsl = out / (name + '.comp')
        glsl.write_text(source)
        target = out / (name + '.vk.spv')
        subprocess.run(['glslangValidator', '-V', '--target-env', 'vulkan1.2',
                        str(glsl), '-o', str(target)], check=True, capture_output=True)
        subprocess.run(['spirv-val', '--target-env', 'vulkan1.2', str(target)], check=True)
        (out / (name + '.expected')).write_bytes(struct.pack('<64I', *([17] * 64)))
    (out / 'manifest.tsv').write_text(''.join(f'{j["key"]} 64 0\n' for j in jobs))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('out', type=Path)
    parser.add_argument('--xlate', type=Path, default=TOOLS / 'dmsh_xlate_bin/dmsh_xlate')
    args = parser.parse_args()
    build(args.out.resolve(), args.xlate.resolve())
