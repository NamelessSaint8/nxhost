#!/usr/bin/env python3
"""Extract bounded captured HWC tensors for a native F16 convolution experiment.

This diagnostic changes the execution layout and arithmetic implementation. It
must not be installed as a replacement guest shader based on timing alone.
Output has 64-byte canaries on each side; all inputs are checked after replay.
"""
import argparse
import json
from pathlib import Path
import subprocess

import numpy as np


def tensors(capture, height, width, ci, co):
    rows = [r.split() for r in capture.with_suffix('.tsv').read_text().splitlines()]
    pools = [(int(r[1]), int(r[2]), int(r[3])) for r in rows if r[0] == 'pool']
    driver = np.fromfile(f'{capture}.b1.before.bin', '<u4')
    result = []
    for word, count, phase in ((200, height*width*ci, 'before'),
                               (204, 9*ci*co, 'before'), (208, co, 'before'),
                               (196, height*width*co, 'after')):
        address = int(driver[word]) | int(driver[word+1]) << 32
        index, base, size = next(p for p in pools if p[1] <= address < p[1]+p[2])
        offset = address-base
        if count*2 > size-offset:
            raise ValueError('tensor exceeds captured pool')
        with Path(f'{capture}.p{index}.{phase}.bin').open('rb') as stream:
            stream.seek(offset)
            data = stream.read(count*2)
        if len(data) != count*2 or not np.isfinite(np.frombuffer(data, '<f2')).all():
            raise ValueError('truncated or nonfinite tensor')
        result.append(data)
    if not any(result[3]):
        raise ValueError('captured output is entirely zero')
    return result


def build(capture, out, shape, co, tile_n=16, paired=False):
    h, w, ci = shape
    if min(h, w, ci, co) <= 0 or ci % 16 or co % 16:
        raise ValueError('positive H/W and whole K16/N16 channels required')
    if tile_n not in (16, 32, 64) or co % tile_n:
        raise ValueError('output channels must contain whole supported native N tiles')
    values = tensors(capture, h, w, ci, co)
    out.mkdir(parents=True, exist_ok=True)
    manifest = ['capture 1', f'dispatch native-conv {(h*w+63)//64} {co//tile_n} 1']
    for binding, data in enumerate(values):
        if binding == 3:
            (out/'captured-output.bin').write_bytes(data)
            data = bytes([0xa5])*64 + bytes(len(data)) + bytes([0x5a])*64
        (out/f'layer.b{binding}.before.bin').write_bytes(data)
        manifest.append(f'buffer {binding} 7 {len(data)}')
    (out/'layer.tsv').write_text('\n'.join(manifest)+'\n')
    source = Path(__file__).parent/'shaders/cooperative-conv.comp'
    defines = ['-DPAIRED_LOADS=1'] if paired else []
    subprocess.run(['glslangValidator', '-V', '--target-env', 'vulkan1.2',
                    f'-DHEIGHT={h}', f'-DWIDTH={w}', f'-DCI={ci}', f'-DCO={co}', f'-DTILE_N={tile_n}',
                    *defines, str(source), '-o', str(out/'native.spv')], check=True)
    subprocess.run(['spirv-val', '--target-env', 'vulkan1.2', str(out/'native.spv')], check=True)
    subprocess.run(['glslangValidator', '-V', '--target-env', 'vulkan1.2',
                    f'-DHEIGHT={h}', f'-DWIDTH={w}', f'-DCI={ci}', f'-DCO={co}', f'-DTILE_N={tile_n}', '-DRAW_LAYOUT=1',
                    *defines, str(source), '-o', str(out/'native.raw.spv')], check=True)
    subprocess.run(['spirv-val', '--target-env', 'vulkan1.2', str(out/'native.raw.spv')], check=True)
    (out/'experiment.json').write_text(json.dumps(dict(capture=str(capture), shape=shape,
        channels=co, tile_n=tile_n, paired_loads=paired, output_bytes=len(values[3]), kernel=3, stride=1), indent=2)+'\n')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('capture', type=Path)
    p.add_argument('out', type=Path)
    p.add_argument('--shape', nargs=3, type=int, required=True)
    p.add_argument('--channels', type=int, required=True)
    p.add_argument('--tile-n', type=int, choices=(16, 32, 64), default=16)
    p.add_argument('--paired-loads', action='store_true')
    a = p.parse_args()
    build(a.capture, a.out, a.shape, a.channels, a.tile_n, a.paired_loads)
