#!/usr/bin/env python3
"""Synthetic residual upsampling, including phase order and partial pixel tiles."""
import argparse
from pathlib import Path

import numpy as np

from check_conv_capture import round_half
from make_cooperative_upsample import build


def fixture(out, fractional=False, inputs=32, channels=16):
    if min(inputs, channels) <= 0 or inputs%16 or channels%16:
        raise ValueError('positive whole K16/N16 channels required')
    h, w, ci, co = 9, 13, inputs, channels
    rng = np.random.default_rng(1118)
    if fractional:
        source = rng.uniform(-1, 1, (h, w, ci)).astype('<f2')
        weights = rng.uniform(-.2, .2, (4, ci, co)).astype('<f2')
        residual = rng.uniform(-1, 1, (h*2, w*2, co)).astype('<f2')
    else:
        source = rng.integers(-1, 2, (h, w, ci)).astype('<f2')
        weights = rng.integers(-1, 2, (4, ci, co)).astype('<f2')
        residual = (rng.integers(-4, 5, (h*2, w*2, co))*.5).astype('<f2')
    bias = (rng.integers(-4, 5, co)*.5).astype('<f2')
    # Dense oracle uses strided output phases rather than sampled output-index
    # arithmetic. Every product and sum is rounded separately for native half.
    expected = np.empty_like(residual)
    for py in range(2):
        for px in range(2):
            acc = residual[py::2, px::2].astype(np.float32)
            for k in range(ci):
                product = (source[:, :, k, None].astype(np.float32)*weights[py*2+px, k].astype(np.float32)).astype(np.float16).astype(np.float32)
                acc = (acc+product).astype(np.float16).astype(np.float32)
            expected[py::2, px::2] = round_half(np.maximum(acc+bias.astype(np.float32), 0), 'rtz')
    out.mkdir(parents=True, exist_ok=True)
    data = bytearray(bytes([0xa5])*64)
    driver = np.zeros(1024, '<u4')
    output_at = None
    for word, value in ((200, source), (204, weights), (208, bias),
                        (212, residual), (196, np.zeros_like(expected))):
        at = len(data)
        driver[word:word+3] = [at, 1, value.nbytes]
        data.extend(value.tobytes())
        data.extend(bytes([0x5a])*64)
        if word == 196:
            output_at = at
    after = bytearray(data)
    after[output_at:output_at+expected.nbytes] = expected.tobytes()
    base = out/'fixture'
    base.with_suffix('.tsv').write_text(f'capture 2\npool 0 {1<<32} {len(data)}\n')
    Path(f'{base}.b1.before.bin').write_bytes(driver.tobytes())
    Path(f'{base}.p0.before.bin').write_bytes(data)
    Path(f'{base}.p0.after.bin').write_bytes(after)
    for tile_n in (16, 32, 64):
        build(base, out/f'n{tile_n}', (h, w, ci), co, tile_n)
    return base


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('out', type=Path)
    p.add_argument('--inputs', type=int, default=32)
    p.add_argument('--channels', type=int, default=16)
    a = p.parse_args()
    fixture(a.out/'integer', inputs=a.inputs, channels=a.channels)
    fixture(a.out/'fractional', True, a.inputs, a.channels)
