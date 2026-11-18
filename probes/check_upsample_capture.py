#!/usr/bin/env python3
"""Independent sampled residual upsampling model for captured half tensors.

One source pixel produces four row-major subpixels. Weights are phase/CI/CO;
the residual initializes C before K16 accumulation. Bias/ReLU and final RTZ
packing follow. Native half-product/half-add is separate from FMA/K16 arithmetic;
neither CPU model establishes original Ampere numerical equivalence.
"""
import argparse
import json
from pathlib import Path

import numpy as np

from check_conv_capture import round_half


def load_tensors(base, shape, channels, output=None):
    h, w, ci = shape
    if min(h, w, ci, channels) <= 0 or ci % 16 or channels % 16:
        raise ValueError('positive dimensions and whole K16/N16 channels required')
    rows = [r.split() for r in Path(str(base)+'.tsv').read_text().splitlines()]
    pools = [(int(r[1]), int(r[2]), int(r[3])) for r in rows if r[0]=='pool']
    driver = np.fromfile(f'{base}.b1.before.bin', '<u4')
    if len(driver) < 215:
        raise ValueError('truncated driver pointer table')
    result = []
    for word, count, phase in ((200, h*w*ci, 'before'), (204, 4*ci*channels, 'before'),
                               (208, channels, 'before'), (212, h*w*4*channels, 'before'),
                               (196, h*w*4*channels, 'after')):
        address = int(driver[word]) | int(driver[word+1]) << 32
        if address % 4:
            raise ValueError('word-aligned half tensors required')
        pool = next((p for p in pools if p[1] <= address < p[1]+p[2]), None)
        if pool is None:
            raise ValueError('tensor is outside captured pools')
        index, guest, size = pool
        offset = address-guest
        if count*2 > size-offset or int(driver[word+2]) < count*2:
            raise ValueError('tensor exceeds declared driver range or captured pool')
        path = Path(output) if output and phase=='after' else Path(f'{base}.p{index}.{phase}.bin')
        with path.open('rb') as stream:
            stream.seek(offset)
            value = np.fromfile(stream, '<f2', count).astype(np.float32)
        if len(value) != count or not np.isfinite(value).all():
            raise ValueError('truncated or nonfinite tensor')
        result.append(value)
    return result


def reference(source, weights, bias, residual, ys, xs, arithmetic='half-mul-add'):
    if arithmetic not in ('half-mul-add', 'fma-k16'):
        raise ValueError('unknown arithmetic model')
    values = source[ys//2, xs//2]
    phase = (ys%2)*2+xs%2
    acc = residual[ys, xs].copy()
    for k in range(source.shape[2]):
        product = values[:, k, None].astype(np.float64)*weights[phase, k].astype(np.float64)
        if arithmetic == 'half-mul-add':
            product = round_half(product)
        acc = (product+acc.astype(np.float64)).astype(np.float32)
        if arithmetic == 'half-mul-add' or k%16 == 15:
            acc = round_half(acc)
    return round_half(np.maximum(acc+bias, 0), 'rtz')


def check(base, shape, channels, output=None, samples=4096, arithmetic='half-mul-add'):
    if samples < 0:
        raise ValueError('nonnegative sample count required')
    h, w, ci = shape
    source, weights, bias, residual, actual = load_tensors(base, shape, channels, output)
    source = source.reshape(h, w, ci)
    weights = weights.reshape(4, ci, channels)
    residual = residual.reshape(h*2, w*2, channels)
    actual = actual.reshape(h*2, w*2, channels)
    rng = np.random.default_rng(1117)
    ys = np.r_[0, 0, h*2-1, h*2-1, h, rng.integers(0, h*2, samples)]
    xs = np.r_[0, w*2-1, 0, w*2-1, w, rng.integers(0, w*2, samples)]
    expected = reference(source, weights, bias, residual, ys, xs, arithmetic)
    error = np.abs(expected-actual[ys, xs])
    return dict(pixels=len(ys), values=int(error.size), max_absolute_error=float(error.max()),
                mean_absolute_error=float(error.mean()), values_over_001=int((error>.01).sum()))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('capture', type=Path)
    p.add_argument('--shape', type=int, nargs=3, required=True)
    p.add_argument('--channels', type=int, required=True)
    p.add_argument('--output', type=Path)
    p.add_argument('--samples', type=int, default=4096)
    p.add_argument('--arithmetic', choices=('half-mul-add', 'fma-k16'), default='half-mul-add')
    a = p.parse_args()
    print(json.dumps(check(a.capture, a.shape, a.channels, a.output, a.samples, a.arithmetic), indent=2))
