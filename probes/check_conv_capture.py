#!/usr/bin/env python3
"""Independent sampled CPU convolution for captured NVN2 half tensors.

The driver buffer at binding 1 holds output/input/weights/bias pointers in
words 196/200/204/208. Tensors are HWC, weights are KY,KX,CI,CO. A stride-2
layer uses a 2x2 kernel; stride-1 uses zero-padded 3x3. Accumulation uses float32
FMA and rounds to half after each K16 fragment. The GPU's half packing can use
different rounding, so report absolute error rather than requiring bit identity.
"""
import argparse
import json
from pathlib import Path

import numpy as np


def round_half(value, mode='rne'):
    """Round finite float values to half, including an explicit toward-zero model."""
    if mode not in ('rne', 'rtz'):
        raise ValueError('unknown half rounding mode')
    result = value.astype(np.float16)
    if mode == 'rtz':
        away = np.abs(result.astype(np.float64)) > np.abs(value)
        result = np.where(away, np.nextafter(result, np.float16(0)), result)
    return result.astype(np.float32)


def check(base, shape, channels, stride=1, samples=512, output=None, *, actual_tensor=None,
          arithmetic='fma-k16', packing='rne'):
    rows = [line.split() for line in Path(str(base) + '.tsv').read_text().splitlines()]
    pools = [(int(r[1]), int(r[2]), int(r[3])) for r in rows if r[0] == 'pool']
    driver = np.fromfile(f'{base}.b1.before.bin', '<u4')

    def pointer(word):
        return int(driver[word]) | (int(driver[word + 1]) << 32)

    def tensor(word, phase, count, override=None):
        address = pointer(word)
        index, guest, size = next(p for p in pools if p[1] <= address < p[1] + p[2])
        offset = address - guest
        if count * 2 > size - offset:
            raise ValueError('tensor extends outside captured pool')
        path = override or Path(f'{base}.p{index}.{phase}.bin')
        with path.open('rb') as stream:
            stream.seek(offset)
            result = np.fromfile(stream, '<f2', count=count)
        if len(result) != count:
            raise ValueError('truncated tensor')
        return result.astype(np.float32)

    height, width, inputs = shape
    if min(height, width, inputs, channels) <= 0 or samples < 0:
        raise ValueError('requires positive dimensions and a nonnegative sample count')
    if stride not in (1, 2) or inputs % 16 or height % stride or width % stride:
        raise ValueError('requires a whole K16 tensor and supported stride')
    if arithmetic not in ('fma-k16', 'half-mul-add'):
        raise ValueError('unknown convolution arithmetic model')
    if packing not in ('rne', 'rtz'):
        raise ValueError('unknown half packing mode')
    kernel = 3 if stride == 1 else 2
    oh, ow = height // stride, width // stride
    source = tensor(200, 'before', height * width * inputs).reshape(height, width, inputs)
    weights = tensor(204, 'before', kernel * kernel * inputs * channels).reshape(kernel * kernel, inputs, channels)
    bias = tensor(208, 'before', channels)
    actual = (tensor(196, 'after', oh * ow * channels, output) if actual_tensor is None
              else np.asarray(actual_tensor, dtype=np.float32)).reshape(oh, ow, channels)
    if not all(np.isfinite(value).all() for value in (source, weights, bias, actual)):
        raise ValueError('nonfinite tensor values require a separate numerical reference')
    rng = np.random.default_rng(42)
    # Include all corners, the center and deterministic random positions.
    ys = np.r_[0, 0, oh - 1, oh - 1, oh // 2, rng.integers(0, oh, samples)]
    xs = np.r_[0, ow - 1, 0, ow - 1, ow // 2, rng.integers(0, ow, samples)]
    accumulator = np.zeros((len(ys), channels), np.float32)
    padding = int(stride == 1)
    for tap in range(kernel * kernel):
        y = ys * stride + tap // kernel - padding
        x = xs * stride + tap % kernel - padding
        valid = (y >= 0) & (y < height) & (x >= 0) & (x < width)
        values = source[np.clip(y, 0, height - 1), np.clip(x, 0, width - 1)] * valid[:, None]
        for k in range(inputs):
            product = values[:, k, None].astype(np.float64) * weights[tap, k].astype(np.float64)
            if arithmetic == 'half-mul-add':
                product = product.astype(np.float16).astype(np.float32)
            accumulator = (product + accumulator.astype(np.float64)).astype(np.float32)
            if arithmetic == 'half-mul-add' or k % 16 == 15:
                accumulator = round_half(accumulator)
    expected = round_half(np.maximum(accumulator + bias, 0), packing)
    error = np.abs(expected - actual[ys, xs])
    return dict(pixels=len(ys), values=error.size, max_absolute_error=float(error.max()),
                mean_absolute_error=float(error.mean()), values_over_001=int((error > .01).sum()))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('capture', type=Path)
    parser.add_argument('--shape', type=int, nargs=3, required=True, metavar=('H', 'W', 'CI'))
    parser.add_argument('--channels', type=int, required=True)
    parser.add_argument('--stride', type=int, default=1)
    parser.add_argument('--samples', type=int, default=512)
    parser.add_argument('--output', type=Path, help='replacement full-pool after file')
    parser.add_argument('--arithmetic', choices=('fma-k16', 'half-mul-add'), default='fma-k16')
    parser.add_argument('--packing', choices=('rne', 'rtz'), default='rne')
    args = parser.parse_args()
    print(json.dumps(check(args.capture, args.shape, args.channels, args.stride,
                           args.samples, args.output, arithmetic=args.arithmetic, packing=args.packing), indent=2))
