#!/usr/bin/env python3
"""Measure one native K16 matrix operation against explicit accumulation models."""
import argparse
import json
from pathlib import Path
import subprocess

import numpy as np


def build(out):
    out.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(710)
    count = 128
    a = rng.uniform(-1, 1, (count, 64, 16)).astype('<f2')
    b = rng.uniform(-1, 1, (count, 16, 16)).astype('<f2')
    c = rng.uniform(-1, 1, (count, 64, 16)).astype('<f2')
    # Separate zero-accumulator, one-product, tiny increment and cancellation
    # groups from the random matrix population.
    c[:32] = 0
    a[32:48, :, 1:] = 0
    a[48:64] = 0
    a[48:64, :, 0] = 1
    b[48:64] = 0
    b[48:64, 0] = np.float16(2**-12)
    c[48:64] = 1
    a[64:80, :, 1::2] = -a[64:80, :, ::2]
    b[64:80, 1::2] = b[64:80, ::2]
    values = (a.tobytes(), b.tobytes(), c.tobytes(), bytes([0xa5])*64+bytes(count*2048)+bytes([0x5a])*64)
    rows = ['capture 1', f'dispatch native-arithmetic {count} 1 1']
    for i, value in enumerate(values):
        (out/f'fixture.b{i}.before.bin').write_bytes(value)
        rows.append(f'buffer {i} 7 {len(value)}')
    (out/'fixture.tsv').write_text('\n'.join(rows)+'\n')
    source = Path(__file__).parent/'shaders/cooperative-arithmetic.comp'
    for name, flags in [('native', []), ('scalar', ['-DSCALAR=1']),
                        ('scalar-pack', ['-DSCALAR=1', '-DPACK_DIRECT=1'])]:
        subprocess.run(['glslangValidator', '-V', '--target-env', 'vulkan1.2', *flags,
                        str(source), '-o', str(out/f'{name}.spv')], check=True)
        subprocess.run(['spirv-val', '--target-env', 'vulkan1.2', str(out/f'{name}.spv')], check=True)


def half(value, mode):
    nearest = value.astype(np.float16)
    if mode == 'rtz':
        away = np.abs(nearest.astype(np.float64)) > np.abs(value)
        nearest = np.where(away, np.nextafter(nearest, np.float16(0)), nearest)
    return nearest.astype(np.float32)


def analyze(out, native_prefix, scalar_prefix):
    a = np.fromfile(out/'fixture.b0.before.bin', '<f2').reshape(-1, 64, 16).astype(np.float32)
    b = np.fromfile(out/'fixture.b1.before.bin', '<f2').reshape(-1, 16, 16).astype(np.float32)
    c = np.fromfile(out/'fixture.b2.before.bin', '<f2').reshape(-1, 64, 16).astype(np.float32)
    def result(prefix):
        for i in range(3):
            if Path(f'{prefix}.b{i}.after.bin').read_bytes() != (out/f'fixture.b{i}.before.bin').read_bytes():
                raise ValueError('input changed')
        raw = Path(f'{prefix}.b3.after.bin').read_bytes()
        if len(raw) != c.size*2+128 or raw[:64] != bytes([0xa5])*64 or raw[-64:] != bytes([0x5a])*64:
            raise ValueError('output canary changed')
        return np.frombuffer(raw[64:-64], '<f2').reshape(c.shape).astype(np.float32)
    native, scalar = result(native_prefix), result(scalar_prefix)
    groups = dict(zero_c=slice(0, 32), one_product=slice(32, 48), tiny_increment=slice(48, 64),
                  cancellation=slice(64, 80), random=slice(80, 128))
    def compare(value):
        return {name: dict(different=int(np.count_nonzero(value[s] != native[s])),
                           max_error=float(np.max(np.abs(value[s]-native[s])))) for name, s in groups.items()}
    models = {}
    for mode in ('rne', 'rtz'):
        for chunk in (1, 2, 4, 8, 16):
            accumulator = c.copy()
            for k in range(16):
                accumulator = (a[:, :, k, None].astype(np.float64)*b[:, None, k, :].astype(np.float64)
                               + accumulator.astype(np.float64)).astype(np.float32)
                if (k+1) % chunk == 0:
                    accumulator = half(accumulator, mode)
            models[f'{mode}_chunk{chunk}'] = compare(accumulator)
    products = a[:, :, :, None]*b[:, None, :, :]
    for mode in ('rne', 'rtz'):
        rounded_products = half(products, mode)
        for chunk in (1, 2, 4, 8, 16):
            accumulator = c.copy()
            for k in range(16):
                accumulator = accumulator+rounded_products[:, :, k]
                if (k+1) % chunk == 0:
                    accumulator = half(accumulator, mode)
            models[f'half_products_{mode}_chunk{chunk}'] = compare(accumulator)
        for product_kind, terms in [('full', products), ('half', rounded_products)]:
            for partial_rounding in (False, True):
                sums = terms.copy()
                while sums.shape[2] > 1:
                    sums = sums[:, :, ::2]+sums[:, :, 1::2]
                    if partial_rounding:
                        sums = half(sums, mode)
                value = half(sums[:, :, 0]+c, mode)
                models[f'tree_{product_kind}_{mode}_partials{int(partial_rounding)}'] = compare(value)
    reference = c.copy()
    for k in range(16):
        reference = (a[:, :, k, None].astype(np.float64)*b[:, None, k, :].astype(np.float64)
                     + reference.astype(np.float64)).astype(np.float32)
    reference = half(reference, 'rne')
    report = dict(canaries=True, inputs_unchanged=True, values=int(c.size), scalar_cpu_differences=int(np.count_nonzero(scalar != reference)),
                  native_vs_scalar=compare(scalar), models=models)
    packed_path = Path(scalar_prefix).parent/'scalar-pack.b3.after.bin'
    if packed_path.exists():
        raw = packed_path.read_bytes()
        if len(raw) != c.size*2+128 or raw[:64] != bytes([0xa5])*64 or raw[-64:] != bytes([0x5a])*64:
            raise ValueError('packed output canary changed')
        packed = np.frombuffer(raw[64:-64], '<f2').reshape(c.shape)
        unrounded = c.copy()
        for k in range(16):
            unrounded = (a[:, :, k, None].astype(np.float64)*b[:, None, k, :].astype(np.float64)
                         + unrounded.astype(np.float64)).astype(np.float32)
        report['direct_pack'] = {mode: int(np.count_nonzero(packed != half(unrounded, mode)))
                                 for mode in ('rne', 'rtz')}
    return report


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('out', type=Path)
    p.add_argument('--native', type=Path)
    p.add_argument('--scalar', type=Path)
    args = p.parse_args()
    if args.native and args.scalar:
        print(json.dumps(analyze(args.out, args.native, args.scalar), indent=2))
    else:
        build(args.out)
