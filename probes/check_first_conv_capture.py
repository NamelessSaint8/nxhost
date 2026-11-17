#!/usr/bin/env python3
"""Independent sampled CPU reference for the RGBA 2x2-unshuffle convolution.

Four row-major RGBA pixels form sixteen HWC channels. Input halves use RNE;
the measured native model rounds products and sums separately. The FMA/K16
alternative remains a separate model. Both use zero padding, bias/ReLU and
toward-zero final packing. This does not establish original Ampere semantics.
"""
import argparse
import json
from pathlib import Path

import numpy as np

from check_conv_capture import round_half


def check(base, output=None, samples=4096, arithmetic='half-mul-add'):
    rows = [r.split() for r in Path(str(base)+'.tsv').read_text().splitlines()]
    image = next(r for r in rows if r[0]=='image' and r[1]=='2')
    width, height, fmt, view = map(int, image[3:7])
    if width % 2 or height % 2 or fmt != 37 or view != 37 or samples < 0:
        raise ValueError('requires even RGBA8 UNORM dimensions and nonnegative samples')
    if arithmetic not in ('half-mul-add', 'fma-k16'):
        raise ValueError('unknown arithmetic model')
    source = np.fromfile(f'{base}.b2.before.bin', np.uint8).reshape(height, width, 4).astype(np.float32)/np.float32(255)
    weights = np.fromfile(f'{base}.b3.before.bin', '<f2').astype(np.float32).reshape(9, 16, 16)
    bias = np.fromfile(f'{base}.b4.before.bin', '<f2').astype(np.float32)
    if len(bias) != 16:
        raise ValueError('requires sixteen output channels')
    driver = np.fromfile(f'{base}.b1.before.bin', '<u4')
    address = int(driver[196]) | int(driver[197]) << 32
    pool, guest, size = next((int(r[1]), int(r[2]), int(r[3])) for r in rows
                            if r[0]=='pool' and int(r[2]) <= address < int(r[2])+int(r[3]))
    oh, ow = height//2, width//2
    if oh*ow*32 > size-(address-guest):
        raise ValueError('output tensor exceeds pool')
    with Path(output or f'{base}.p{pool}.after.bin').open('rb') as stream:
        stream.seek(address-guest)
        actual = np.fromfile(stream, '<f2', oh*ow*16).astype(np.float32).reshape(oh, ow, 16)
    if not all(np.isfinite(v).all() for v in (source, weights, bias, actual)):
        raise ValueError('nonfinite values require a separate reference')
    rng = np.random.default_rng(1117)
    ys = np.r_[0, 0, oh-1, oh-1, oh//2, rng.integers(0, oh, samples)]
    xs = np.r_[0, ow-1, 0, ow-1, ow//2, rng.integers(0, ow, samples)]
    acc = np.zeros((len(ys), 16), np.float32)
    for tap in range(9):
        y, x = ys+tap//3-1, xs+tap%3-1
        valid = (y>=0)&(y<oh)&(x>=0)&(x<ow)
        for k in range(16):
            value = source[np.clip(y*2+k//8, 0, height-1), np.clip(x*2+(k//4)%2, 0, width-1), k%4]*valid
            value = round_half(value)
            product = value[:, None].astype(np.float64)*weights[tap, k].astype(np.float64)
            if arithmetic == 'half-mul-add':
                product = round_half(product)
            acc = (product+acc.astype(np.float64)).astype(np.float32)
            if arithmetic == 'half-mul-add':
                acc = round_half(acc)
        acc = round_half(acc)
    expected = round_half(np.maximum(acc+bias, 0), 'rtz')
    error = np.abs(expected-actual[ys, xs])
    return dict(pixels=len(ys), values=int(error.size), max_absolute_error=float(error.max()),
                mean_absolute_error=float(error.mean()), values_over_001=int((error>.01).sum()))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('capture', type=Path)
    p.add_argument('--output', type=Path)
    p.add_argument('--samples', type=int, default=4096)
    p.add_argument('--arithmetic', choices=('half-mul-add', 'fma-k16'), default='half-mul-add')
    a = p.parse_args()
    print(json.dumps(check(a.capture, a.output, a.samples, a.arithmetic), indent=2))
