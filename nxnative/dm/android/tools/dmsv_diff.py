#!/usr/bin/env python3
"""Diff two DMSV bundles entry by entry, and characterise the changed SPIR-V.

A rebuild that recompiles a subset of a game's programs (the atlas extent hoist,
a helper rewrite, a lowering pass) claims its keys, reflection records and flags
are unchanged and only those binaries differ.  This checks that claim against
the files, and reports how the changed SPIR-V differs in instruction mix, so
"no behaviour change" can be argued from the binaries rather than the generator
source.

Usage: dmsv_diff.py ORIGINAL.dmsv OTHER.dmsv [--json out] [--show N]
"""
import argparse, json, mmap, struct, sys

OPNAMES = {
    43: 'OpConstant', 50: 'OpSpecConstant', 61: 'OpLoad', 62: 'OpStore', 65: 'OpAccessChain',
    66: 'OpInBoundsAccessChain', 77: 'OpVectorShuffle', 86: 'OpImageSampleImplicitLod',
    87: 'OpImageSampleExplicitLod', 94: 'OpImageFetch', 95: 'OpImageGather', 97: 'OpImageRead',
    98: 'OpImageWrite', 109: 'OpConvertFToU', 112: 'OpConvertUToF', 126: 'OpBitcast',
    128: 'OpSNegate', 129: 'OpFNegate', 130: 'OpIAdd', 132: 'OpFAdd', 133: 'OpISub',
    134: 'OpFSub', 135: 'OpIMul', 136: 'OpFMul', 141: 'OpSMod', 149: 'OpAny', 150: 'OpAll',
    154: 'OpSelect', 157: 'OpLessThan', 164: 'OpFOrdLessThan', 168: 'OpFOrdGreaterThan',
    169: 'OpFOrdLessThanEqual', 170: 'OpFOrdGreaterThanEqual', 177: 'OpFRem',
    179: 'OpIEqual', 180: 'OpINotEqual', 184: 'OpFOrdEqual', 190: 'OpLogicalAnd',
    191: 'OpLogicalOr', 194: 'OpShiftRightLogical', 195: 'OpShiftLeftLogical',
    199: 'OpBitwiseAnd', 200: 'OpBitwiseOr', 205: 'OpCompositeConstruct', 81: 'OpCompositeExtract',
    46: 'OpFunction', 248: 'OpFunctionCall',
}
INTERESTING = set(OPNAMES) | {81, 82}


def index(path):
    """key -> (stage, flags, spv bytes, reflection bytes), memory-mapped."""
    f = open(path, 'rb')
    mm = mmap.mmap(f.fileno(), 0, prot=mmap.PROT_READ)
    magic, version, count = struct.unpack_from('<4sII', mm)
    if magic != b'DMSV' or version != 1 or 12 + count * 32 > len(mm):
        raise ValueError(f'{path}: invalid DMSV header')
    out = {}
    for i in range(count):
        key, stage, off, size, roff, rsize, flags = struct.unpack_from('<Q6I', mm, 12 + i * 32)
        if off + size > len(mm) or roff + rsize > len(mm):
            raise ValueError(f'{path}: truncated entry {key:016x}')
        out[key] = (stage, flags, mm[off:off + size], mm[roff:roff + rsize])
    return mm, out


def hist(spv):
    """opcode -> count, and the total instruction count."""
    if len(spv) % 4 or len(spv) < 20:
        return None, None
    words = memoryview(spv).cast('I')
    h, i, total = {}, 5, 0
    while i < len(words):
        w = words[i]
        wc, op = w >> 16, w & 0xffff
        h[op] = h.get(op, 0) + 1
        total += 1
        i += wc if wc else 1
    return h, total


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('original'); ap.add_argument('extent'); ap.add_argument('--json')
    ap.add_argument('--show', type=int, default=8, help='how many changed entries to spell out')
    a = ap.parse_args()
    ma, A = index(a.original)
    mb, B = index(a.extent)
    res = {'original': a.original, 'extent': a.extent, 'entries': [len(A), len(B)],
           'same_keys': sorted(A) == sorted(B)}

    differ, refl_diff, flag_diff, stage_diff = [], [], [], []
    for key in sorted(A):
        sa, fa, spva, ra = A[key]
        if key not in B:
            continue
        sb, fb, spvb, rb = B[key]
        if sa != sb: stage_diff.append(key)
        if fa != fb: flag_diff.append(key)
        if ra != rb: refl_diff.append(key)
        if spva != spvb: differ.append((key, sa, len(spva), len(spvb)))

    res.update({'differ': len(differ), 'stage_changed': len(stage_diff),
                'flags_changed': len(flag_diff), 'reflection_changed': len(refl_diff),
                'differ_by_stage': {}, 'unmatched': len(set(A) ^ set(B))})
    for _, stage, _, _ in differ:
        res['differ_by_stage'][str(stage)] = res['differ_by_stage'].get(str(stage), 0) + 1

    # Instruction mix over every changed program, summed.
    tot_a = tot_b = 0
    mix = {}
    per = []
    for key, stage, sa, sb in differ:
        ha, na = hist(A[key][2]); hb, nb = hist(B[key][2])
        if ha is None or hb is None:
            per.append({'key': f'{key:016x}', 'error': 'unparsable'})
            continue
        tot_a += na; tot_b += nb
        for op in INTERESTING:
            da, db = ha.get(op, 0), hb.get(op, 0)
            if da != db:
                m = mix.setdefault(OPNAMES.get(op, f'op{op}'), [0, 0])
                m[0] += da; m[1] += db
        per.append({'key': f'{key:016x}', 'stage': stage,
                    'spv_bytes': [sa, sb], 'instructions': [na, nb],
                    'delta': na - nb})
    res['instructions'] = {'before': tot_a, 'after': tot_b, 'delta': tot_a - tot_b,
                           'mean_delta': round((tot_a - tot_b) / max(len(per), 1), 2)}
    res['opcode_delta'] = {k: v for k, v in sorted(mix.items(), key=lambda kv: kv[1][1] - kv[1][0])}
    per.sort(key=lambda p: p.get('delta', 0))
    res['changed_programs'] = per[:a.show]
    print(json.dumps({k: v for k, v in res.items() if k != 'changed_programs'}, indent=1))
    print('smallest-delta changed programs:')
    for p in per[:a.show]:
        print(' ', p)
    if a.json:
        with open(a.json, 'w') as f:
            json.dump(res, f, indent=1)
        print('wrote', a.json)


if __name__ == '__main__':
    sys.exit(main())
