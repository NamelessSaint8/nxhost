#!/usr/bin/env python3
"""Non-game convolution fixtures: exact integers, fractional halves and tile tails."""
import argparse
from pathlib import Path

import numpy as np

from make_cooperative_conv import build


def fixture(out, fractional=False, channels=32, stride=1):
    if channels <= 0 or channels % 16:
        raise ValueError('requires positive whole N16 output channels')
    if stride not in (1, 2):
        raise ValueError('requires stride one or two')
    oh, ow, ci, co = 9, 13, 32, channels
    h, w = oh*stride, ow*stride
    kernel = 3 if stride==1 else 2
    rng = np.random.default_rng(709)
    if fractional:
        x = rng.uniform(-1, 1, (h, w, ci)).astype('<f2')
        weights = rng.uniform(-.2, .2, (kernel, kernel, ci, co)).astype('<f2')
    else:
        x = rng.integers(-1, 2, (h, w, ci)).astype('<f2')
        weights = rng.integers(-1, 2, (kernel, kernel, ci, co)).astype('<f2')
    bias = rng.integers(-2, 3, co).astype('<f2')*.5
    acc = np.zeros((oh, ow, co), np.float32)
    padding = int(stride==1)
    padded = np.pad(x.astype(np.float32), ((padding, padding), (padding, padding), (0, 0)))
    for ky in range(kernel):
        for kx in range(kernel):
            for k in range(ci):
                # Exact half products plus float32 accumulator, one rounding
                # after each term, then half rounding at each K16 boundary.
                acc = (padded[ky:ky+oh*stride:stride, kx:kx+ow*stride:stride, k, None].astype(np.float64)
                       * weights[ky, kx, k].astype(np.float64)+acc.astype(np.float64)).astype(np.float32)
                if k % 16 == 15:
                    acc = acc.astype(np.float16).astype(np.float32)
    expected = np.maximum(acc+bias, 0).astype('<f2')
    out.mkdir(parents=True, exist_ok=True)
    before = bytearray(bytes([0x3c])*64)
    offsets = []
    for data in (x, weights, bias, np.zeros_like(expected)):
        offsets.append(len(before))
        before.extend(data.tobytes())
        before.extend(bytes([0x5a])*64)
    after = bytearray(before)
    after[offsets[3]:offsets[3]+expected.nbytes] = expected.tobytes()
    driver = np.zeros(1024, '<u4')
    guest = 1 << 32
    for word, offset, size in zip((200, 204, 208, 196), offsets,
                                  (x.nbytes, weights.nbytes, bias.nbytes, expected.nbytes)):
        driver[word:word+3] = [offset, 1, size]
    capture = out/'fixture'
    capture.with_suffix('.tsv').write_text(f'capture 2\npool 0 {guest} {len(before)}\n')
    Path(f'{capture}.p0.before.bin').write_bytes(before)
    Path(f'{capture}.p0.after.bin').write_bytes(after)
    Path(f'{capture}.b1.before.bin').write_bytes(driver.tobytes())
    build(capture, out/'experiment', (h, w, ci), co, stride=stride)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('out', type=Path)
    p.add_argument('--channels', type=int, default=32)
    p.add_argument('--stride', type=int, choices=(1, 2), default=1)
    a = p.parse_args()
    fixture(a.out/'integer', channels=a.channels, stride=a.stride)
    fixture(a.out/'fractional', True, channels=a.channels, stride=a.stride)
