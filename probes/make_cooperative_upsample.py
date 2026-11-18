#!/usr/bin/env python3
"""Build an owned-pool diagnostic of K16 residual upsampling from a capture.

Requires all five bounded tensors in one captured pool. Keeps the tracked raw
module for runtime specialization; the owned map marks its allocation coherent.
"""
import argparse
import json
from pathlib import Path
import subprocess

from check_upsample_capture import load_tensors


def build(base, out, shape, channels, tile_n=16, load_width=1):
    h, w, ci = shape
    if tile_n not in (16, 32, 64) or 4*channels % tile_n:
        raise ValueError('requires whole supported native output tiles')
    if load_width not in (1, 2, 4):
        raise ValueError('load width must be one, two or four half channels')
    load_tensors(base, shape, channels)
    rows = [r.split() for r in Path(str(base)+'.tsv').read_text().splitlines()]
    pools = [r for r in rows if r[0]=='pool']
    if len(pools) != 1 or pools[0][1] != '0':
        raise ValueError('owned experiment requires exactly one captured pool')
    guest, size = map(int, pools[0][2:])
    before = Path(f'{base}.p0.before.bin').read_bytes()
    driver = Path(f'{base}.b1.before.bin').read_bytes()
    if len(before) != size or len(driver) < 4096:
        raise ValueError('truncated full pool or driver')
    grid = next((list(map(int, r[2:5])) for r in rows if r[0]=='dispatch'), [(h*w+63)//64, 4*channels//tile_n, 1])
    if len(grid) != 3 or min(grid) <= 0 or grid[2] != 1:
        raise ValueError('requires a positive two-dimensional launch grid')
    out.mkdir(parents=True, exist_ok=True)
    for binding, data in ((0, before), (1, driver[:4096]), (4, bytes(131072)), (6, bytes(4100))):
        (out/f'owned.b{binding}.before.bin').write_bytes(data)
    (out/'owned.tsv').write_text('capture 1\ndispatch upsample '+' '.join(map(str, grid))+
        f'\nowned_pool 4 0 {guest} 1\nbuffer 0 7 {size}\nbuffer 1 6 4096\nbuffer 4 7 131072\nbuffer 6 7 4100\n')
    source = Path(__file__).parent/'shaders/cooperative-upsample.comp'
    target = out/'native.raw.spv'
    subprocess.run(['glslangValidator', '-V', '--target-env', 'vulkan1.2',
                    f'-DHEIGHT={h}', f'-DWIDTH={w}', f'-DCI={ci}', f'-DCO={channels}', f'-DTILE_N={tile_n}', f'-DLOAD_WIDTH={load_width}',
                    str(source), '-o', str(target)], check=True)
    subprocess.run(['spirv-val', '--target-env', 'vulkan1.2', str(target)], check=True)
    result = dict(capture=str(base), shape=list(shape), channels=channels, tile_n=tile_n, load_width=load_width,
                  grid=grid, residual='initial accumulator', diagnostic_only=True)
    (out/'experiment.json').write_text(json.dumps(result, indent=2)+'\n')
    return result


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('capture', type=Path)
    p.add_argument('out', type=Path)
    p.add_argument('--shape', type=int, nargs=3, required=True)
    p.add_argument('--channels', type=int, required=True)
    p.add_argument('--tile-n', type=int, choices=(16, 32, 64), default=16)
    p.add_argument('--load-width', type=int, choices=(1, 2, 4), default=1)
    a = p.parse_args()
    print(json.dumps(build(a.capture, a.out, a.shape, a.channels, a.tile_n, a.load_width), indent=2))
