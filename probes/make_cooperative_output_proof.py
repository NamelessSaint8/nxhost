#!/usr/bin/env python3
"""Dense packed-image and half-trace oracles for residual image convolution."""
import argparse
from pathlib import Path
import struct

import numpy as np

from check_conv_capture import round_half
from check_output_capture import pack_color
from make_cooperative_output import build


def fixture(out, fractional=False):
    h, w, ci = 9, 13, 32
    rng = np.random.default_rng(1119)
    if fractional:
        features = rng.uniform(-.25, .25, (h, w, ci)).astype('<f2')
        weights = rng.uniform(-.01, .01, (9, ci, 16)).astype('<f2')
    else:
        features = (rng.integers(-1, 2, (h, w, ci))*.25).astype('<f2')
        weights = (rng.integers(-1, 2, (9, ci, 16))/32).astype('<f2')
    bias = (rng.integers(-4, 5, 16)/32).astype('<f2')
    image = rng.integers(0, 256, (h*2, w*2, 4), dtype=np.uint8)
    out.mkdir(parents=True, exist_ok=True)
    base = out/'fixture'
    driver = np.zeros(1024, '<u4')
    manifest = ['capture 1', 'buffer 1 6 4096']
    for binding, word, offset, values in ((5, 200, 32, features), (4, 204, 64, weights), (6, 208, 16, bias)):
        raw = bytes([0xa5])*offset+values.tobytes()+bytes([0x5a])*64
        Path(f'{base}.b{binding}.before.bin').write_bytes(raw)
        driver[word:word+3] = [binding*4096+offset, 0, values.nbytes]
        manifest.append(f'buffer {binding} 7 {len(raw)}')
    Path(f'{base}.b1.before.bin').write_bytes(driver.tobytes())
    manifest += [f'image 2 1 {w*2} {h*2} 37 37 4 0 0 0 0', f'image 3 3 {w*2} {h*2} 64 64 4 0 0 0 0']
    base.with_suffix('.tsv').write_text('\n'.join(manifest)+'\n')
    Path(f'{base}.b2.before.bin').write_bytes(image.tobytes())
    Path(f'{base}.b2.sampler.bin').write_bytes(struct.pack('<8B8f', *([0]*8), 0, 0, 0, 1, 0, 0, 0, 0))
    Path(f'{base}.b3.before.bin').write_bytes(np.full((h*2, w*2), 0x55555555, '<u4').tobytes())
    padded = np.pad(features.astype(np.float32), ((1, 1), (1, 1), (0, 0)))
    for arithmetic in ('native', 'float32'):
        acc = np.zeros((h, w, 16), np.float32)
        for ky in range(3):
            for kx in range(3):
                for k in range(ci):
                    product = padded[ky:ky+h, kx:kx+w, k, None].astype(np.float64)*weights[ky*3+kx, k].astype(np.float64)
                    if arithmetic == 'native':
                        product = product.astype(np.float16).astype(np.float32)
                    acc = (acc.astype(np.float64)+product).astype(np.float32)
                    if arithmetic == 'native' or k%16 == 15:
                        acc = round_half(acc, 'rtz' if arithmetic=='float32' else 'rne')
        output = np.empty((h*2, w*2, 4), np.float32)
        for phase in range(4):
            columns = [phase*2, phase*2+1, phase*2+8, phase*2+9]
            ys, xs = slice(phase//2, None, 2), slice(phase%2, None, 2)
            output[ys, xs] = (image[ys, xs].astype(np.float32)/np.float32(255)+acc[:, :, columns]).astype(np.float32)+bias[columns]
        Path(f'{base}.{arithmetic}.color.bin').write_bytes(pack_color(output).astype('<u4').tobytes())
        Path(f'{base}.{arithmetic}.trace.bin').write_bytes(bytes([0xa5])*64+acc.astype('<f2').tobytes()+bytes([0x5a])*64)
        build(base, out/arithmetic, (h, w, ci), arithmetic, trace=True)
    return base


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('out', type=Path)
    a = p.parse_args()
    fixture(a.out/'integer')
    fixture(a.out/'fractional', True)
