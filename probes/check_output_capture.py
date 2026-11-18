#!/usr/bin/env python3
"""Independent 3x3 convolution, RG/BA phase shuffle and RGB10A2 packing model."""
import argparse
import json
from pathlib import Path
import struct

import numpy as np

from check_conv_capture import round_half


def unpack_color(words):
    return np.stack([words&1023, (words>>10)&1023, (words>>20)&1023, (words>>30)&3], axis=-1)


def pack_color(value):
    q = np.rint(np.clip(value, 0, 1)*np.array([1023, 1023, 1023, 3], np.float32)).astype(np.uint32)
    return q[..., 0] | q[..., 1]<<10 | q[..., 2]<<20 | q[..., 3]<<30


def load(base, shape):
    h, w, ci = shape
    if min(h, w, ci) <= 0 or ci%16:
        raise ValueError('positive dimensions and whole K16 channels required')
    rows = [r.split() for r in Path(str(base)+'.tsv').read_text().splitlines()]
    images = {int(r[1]): r for r in rows if r[0]=='image'}
    for binding, kind, fmt in ((2, 1, 37), (3, 3, 64)):
        r = images.get(binding)
        if not r or list(map(int, r[2:8])) != [kind, w*2, h*2, fmt, fmt, 4] or any(map(int, r[8:])):
            raise ValueError('requires identity RGBA8 input and RGB10A2 output at double feature dimensions')
    driver = np.fromfile(f'{base}.b1.before.bin', '<u4')
    if len(driver) < 211:
        raise ValueError('truncated driver pointer table')
    support = Path(f'{base}.b0.before.bin')
    if support.exists():
        # The translator's std140 support block places texture scale[1] at
        # byte 208. The captured image helper applies it to both coordinates.
        raw = support.read_bytes()
        if len(raw) < 212 or struct.unpack_from('<f', raw, 208)[0] != 1:
            raise ValueError('scaled source texture coordinates are unsupported')
    tensors = []
    for binding, word, count in ((5, 200, h*w*ci), (4, 204, 9*ci*16), (6, 208, 16)):
        if int(driver[word])%4 or int(driver[word+2]) < count*2:
            raise ValueError('unaligned or undersized tensor')
        offset = int(driver[word]&255)//2
        values = np.fromfile(f'{base}.b{binding}.before.bin', '<f2')[offset:offset+count].astype(np.float32)
        if len(values) != count or not np.isfinite(values).all():
            raise ValueError('truncated or nonfinite tensor')
        tensors.append(values)
    image = np.fromfile(f'{base}.b2.before.bin', np.uint8).reshape(h*2, w*2, 4).astype(np.float32)/np.float32(255)
    return tensors[0].reshape(h, w, ci), tensors[1].reshape(9, ci, 16), tensors[2], image


def convolution(source, weights, ys, xs, arithmetic='half-mul-add'):
    if arithmetic not in ('half-mul-add', 'fma-k16-rne', 'fma-k16-rtz'):
        raise ValueError('unknown arithmetic model')
    h, w, ci = source.shape
    acc = np.zeros((len(ys), 16), np.float32)
    for tap in range(9):
        y, x = ys+tap//3-1, xs+tap%3-1
        valid = (y>=0)&(y<h)&(x>=0)&(x<w)
        v = source[np.clip(y, 0, h-1), np.clip(x, 0, w-1)]*valid[:, None]
        for k in range(ci):
            product = v[:, k, None].astype(np.float64)*weights[tap, k].astype(np.float64)
            if arithmetic == 'half-mul-add':
                product = round_half(product)
            acc = (product+acc.astype(np.float64)).astype(np.float32)
            if arithmetic == 'half-mul-add' or k%16 == 15:
                acc = round_half(acc, 'rtz' if arithmetic=='fma-k16-rtz' else 'rne')
    return acc


def combine(image, residual, bias, ys, xs):
    phase = (ys%2)*2+xs%2
    columns = phase[:, None]*2+np.array([0, 1, 8, 9])
    return (image[ys, xs]+np.take_along_axis(residual, columns, axis=1)).astype(np.float32)+bias[columns]


def check(base, shape, output=None, trace=None, samples=4096, arithmetic='half-mul-add'):
    if samples < 0:
        raise ValueError('nonnegative sample count required')
    source, weights, bias, image = load(base, shape)
    h, w, ci = shape
    rng = np.random.default_rng(1117)
    ys = np.r_[0, 0, h*2-1, h*2-1, h, rng.integers(0, h*2, samples)]
    xs = np.r_[0, w*2-1, 0, w*2-1, w, rng.integers(0, w*2, samples)]
    acc = convolution(source, weights, ys//2, xs//2, arithmetic)
    value = combine(image, acc, bias, ys, xs)
    expected = unpack_color(pack_color(value))
    actual = unpack_color(np.fromfile(output or f'{base}.b3.after.bin', '<u4').reshape(h*2, w*2)[ys, xs])
    error = np.abs(expected.astype(np.int32)-actual.astype(np.int32))
    result = dict(pixels=len(ys), components=int(error.size), max_quantization_units=int(error.max()),
                  mean_quantization_units=float(error.mean()), components_over_one=int((error>1).sum()))
    if trace:
        raw = Path(trace).read_bytes()
        if len(raw) != h*w*32+128 or raw[:64] != bytes([0xa5])*64 or raw[-64:] != bytes([0x5a])*64:
            raise ValueError('trace size or canary changed')
        recorded = np.frombuffer(raw[64:-64], '<f2').astype(np.float32).reshape(h, w, 16)[ys//2, xs//2]
        if not np.isfinite(recorded).all():
            raise ValueError('nonfinite trace')
        delta = np.abs(recorded-acc)
        result['trace_values'] = int(delta.size)
        result['trace_max_absolute_error'] = float(delta.max())
    return result


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('capture', type=Path)
    p.add_argument('--shape', type=int, nargs=3, required=True)
    p.add_argument('--output', type=Path)
    p.add_argument('--trace', type=Path)
    p.add_argument('--samples', type=int, default=4096)
    p.add_argument('--arithmetic', choices=('half-mul-add', 'fma-k16-rne', 'fma-k16-rtz'), default='half-mul-add')
    a = p.parse_args()
    print(json.dumps(check(a.capture, a.shape, a.output, a.trace, a.samples, a.arithmetic), indent=2))
