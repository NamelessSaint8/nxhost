#!/usr/bin/env python3
"""Build a separate bounded residual-image convolution diagnostic from capture."""
import argparse
import json
from pathlib import Path
import subprocess

from check_output_capture import load


def build(base, out, shape, arithmetic='native', trace=False, paired=False, *, quad=False):
    h, w, ci = shape
    if arithmetic not in ('native', 'float32'):
        raise ValueError('requires native or float32 arithmetic')
    if paired and quad:
        raise ValueError('choose either paired or quad loads')
    load(base, shape)
    rows = [r.split() for r in Path(str(base)+'.tsv').read_text().splitlines()]
    grid = next((list(map(int, r[2:5])) for r in rows if r[0]=='dispatch'), [(h*w+63)//64, 1, 1])
    if len(grid) != 3 or min(grid) <= 0 or grid[2] != 1:
        raise ValueError('requires a positive two-dimensional launch grid')
    data = {}
    driver = Path(f'{base}.b1.before.bin').read_bytes()
    if len(driver) < 4096:
        raise ValueError('truncated driver')
    data['b1.before.bin'] = driver[:4096]
    manifest = ['capture 1', 'dispatch output-conv '+' '.join(map(str, grid)), 'buffer 1 6 4096']
    support = Path(f'{base}.b0.before.bin')
    if support.exists():
        value = support.read_bytes()
        data['b0.before.bin'] = value
        manifest.append(f'buffer 0 6 {len(value)}')
    for binding in (4, 5, 6):
        row = next((r for r in rows if r[0]=='buffer' and int(r[1])==binding), None)
        value = Path(f'{base}.b{binding}.before.bin').read_bytes()
        if not row or row[2] != '7' or int(row[3]) != len(value) or len(value)%4:
            raise ValueError('invalid captured storage buffer')
        data[f'b{binding}.before.bin'] = value
        manifest.append(' '.join(row))
    for binding in (2, 3):
        manifest.append(next(' '.join(r) for r in rows if r[0]=='image' and int(r[1])==binding))
        value = Path(f'{base}.b{binding}.before.bin').read_bytes()
        if len(value) != h*w*16:
            raise ValueError('truncated image')
        data[f'b{binding}.before.bin'] = value
    data['b2.sampler.bin'] = Path(f'{base}.b2.sampler.bin').read_bytes()
    if trace:
        size = h*w*32+128
        manifest.append(f'buffer 7 7 {size}')
        data['b7.before.bin'] = bytes([0xa5])*64+bytes(size-128)+bytes([0x5a])*64
    out.mkdir(parents=True, exist_ok=True)
    for suffix, value in data.items():
        (out/('layer.'+suffix)).write_bytes(value)
    (out/'layer.tsv').write_text('\n'.join(manifest)+'\n')
    defines = (['-DFLOAT32_K16=1'] if arithmetic=='float32' else [])+(['-DTRACE_RESIDUAL=1'] if trace else [])
    if paired:
        defines.append('-DPAIRED_LOADS=1')
    if quad:
        defines.append('-DQUAD_LOADS=1')
    source = Path(__file__).parent/'shaders/cooperative-output.comp'
    target = out/'output.spv'
    subprocess.run(['glslangValidator', '-V', '--target-env', 'vulkan1.2',
                    f'-DHEIGHT={h}', f'-DWIDTH={w}', f'-DCI={ci}', *defines, str(source), '-o', str(target)], check=True)
    subprocess.run(['spirv-val', '--target-env', 'vulkan1.2', str(target)], check=True)
    result = dict(capture=str(base), shape=list(shape), arithmetic=arithmetic, trace=trace, paired_loads=paired,
                  quad_loads=quad, grid=grid, diagnostic_only=True)
    (out/'experiment.json').write_text(json.dumps(result, indent=2)+'\n')
    return result


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('capture', type=Path)
    p.add_argument('out', type=Path)
    p.add_argument('--shape', type=int, nargs=3, required=True)
    p.add_argument('--arithmetic', choices=('native', 'float32'), default='native')
    p.add_argument('--trace', action='store_true')
    packing = p.add_mutually_exclusive_group()
    packing.add_argument('--paired-loads', action='store_true')
    packing.add_argument('--quad-loads', action='store_true')
    a = p.parse_args()
    print(json.dumps(build(a.capture, a.out, a.shape, a.arithmetic, a.trace, a.paired_loads,
                           quad=a.quad_loads), indent=2))
