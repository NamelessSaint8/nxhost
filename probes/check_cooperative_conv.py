#!/usr/bin/env python3
"""Check native layer canaries, immutable inputs and sampled CPU K16 results."""
import argparse
import json
from pathlib import Path

import numpy as np

from check_conv_capture import check


def inspect(experiment, replay, samples=4096):
    metadata = json.loads((experiment/'experiment.json').read_text())
    binary = Path(f'{replay}.b3.after.bin').read_bytes()
    if len(binary) != metadata['output_bytes']+128:
        raise ValueError('truncated output')
    if binary[:64] != bytes([0xa5])*64 or binary[-64:] != bytes([0x5a])*64:
        raise ValueError('output canary changed')
    for i in range(3):
        if (experiment/f'layer.b{i}.before.bin').read_bytes() != Path(f'{replay}.b{i}.after.bin').read_bytes():
            raise ValueError(f'input binding {i} changed')
    native = np.frombuffer(binary[64:-64], '<f2').astype(np.float32)
    captured = np.fromfile(experiment/'captured-output.bin', '<f2').astype(np.float32)
    if not np.isfinite(native).all() or not np.count_nonzero(native):
        raise ValueError('nonfinite or entirely zero output')
    delta = np.abs(native-captured)
    args = (metadata['capture'], metadata['shape'], metadata['channels'])
    return dict(canaries=True, inputs_unchanged=True, nonzero_values=int(np.count_nonzero(native)),
                vs_capture=dict(max_absolute_error=float(delta.max()), mean_absolute_error=float(delta.mean()),
                                values_over_001=int((delta>.01).sum()), exact_fraction=float((delta==0).mean())),
                captured_vs_cpu=check(*args, samples=samples),
                captured_vs_rtz_cpu=check(*args, samples=samples, packing='rtz'),
                native_vs_cpu=check(*args, samples=samples, actual_tensor=native),
                native_vs_half_model=check(*args, samples=samples, actual_tensor=native,
                                          arithmetic='half-mul-add', packing='rtz'))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('experiment', type=Path)
    p.add_argument('replay', type=Path)
    p.add_argument('--samples', type=int, default=4096)
    a = p.parse_args()
    print(json.dumps(inspect(a.experiment, a.replay, a.samples), indent=2))
