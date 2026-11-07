#!/usr/bin/env python3
"""Judge whether the vertex uniform slots a shader actually reads hold a float transform.

`DM_VDRAW_DRAWS=n DM_VDRAW_SLOTS=11,12 DM_VDRAW_KEYS=<keys> DM_VDRAW_WORDS=256` prints one line per changed binding:

    vdraw: draw vs <key> slot <k> addr <hex> size <n> rows <r> w: <word> <word> ... [ .. <n> words .. ] <tail words>

The words are the binding's bytes as printed at encode time, so this tool answers the question the slot probe left
open: the blocks a shader consumes (c14 -> slot 11, c15 -> slot 12) -- are they a float4x4 the GPU can transform by,
or integer bit patterns like the blocks in slots 0-3?

Three tests per block, all on the words the log actually holds:
  zero     every printed word zero -- the binding exists but nothing was written through it
  affine   the shader's own read window (words 4-19, i.e. bytes 16-79 = _m0[1..4]) as a 4x4 with a 0,0,0,1 bottom row
  ortho    any 3x3 at any 1-float offset with unit rows and zero dot products, which a rotation-stage matrix has

Usage: vdraw_blocks.py <log> [--key K] [--slot N] [--target WxH] [--raw N] [--floats]
  --key K     only this shader key (a prefix matches, so a key without the _b suffix works)
  --slot N    only this slot
  --target WH only draws into a target of that size, e.g. 2048x1152 -- a key is used by more than one pass, and the
              world pass is 2048x1152 while the same program's shadow pass is 128x128
  --raw N     print the first N words of one example block per (key, slot) instead of the summary table
  --floats    with --raw, print the words as floats and as int32 rather than hex
"""
import re
import struct
import sys

LINE_RE = re.compile(r'vdraw: draw vs (\S+) target (\d+x\d+) chmask (0x[0-9a-f]+) slot (\d+) addr (0x[0-9a-f]+) size (\d+) rows (\d+) w:(.*)$')
# The first form of this line had no target or mask; keep parsing it so an older log still reads.
OLD_RE = re.compile(r'vdraw: draw vs (\S+) slot (\d+) addr (0x[0-9a-f]+) size (\d+) rows (\d+) w:(.*)$')
GAP_RE = re.compile(r'\.\. (\d+) words \.\.')
ORTHO_TOL = 0.02


def words_of(text):
    """The printed words, with the omitted middle filled with None so offsets stay truthful."""
    m = GAP_RE.search(text)
    if m:
        head, tail = text.split(m.group(0))
        return [int(x, 16) for x in head.split()] + [None] * int(m.group(1)) + [int(x, 16) for x in tail.split()]
    return [int(x, 16) for x in text.split()]


def f32(w):
    return struct.unpack('<f', struct.pack('<I', w))[0]


def affine(fl, at=4):
    """The shader's read _m0[1..4] as a 4x4: finite, moderate, and a 0,0,0,1 bottom row."""
    rows = [fl[at + 4 * i:at + 4 * i + 4] for i in range(4)]
    if any(len(r) < 4 for r in rows):
        return None
    if any(not (-1e6 <= v <= 1e6) for r in rows for v in r):
        return None
    if any(abs(v) < 1e-30 and v != 0.0 for r in rows for v in r):
        return None
    if any(abs(rows[3][i] - t) > 1e-3 for i, t in enumerate((0, 0, 0, 1))):
        return None
    return rows


def basis(fl):
    """Two consecutive rows of 3 that are each unit length and perpendicular: the rotation stage of a transform, which a
    matrix in a row array has even when its third row is a scale or a translation."""
    for at in range(0, max(0, len(fl) - 10)):
        r = [fl[at + 4 * i:at + 4 * i + 3] for i in range(2)]
        if any(len(x) < 3 or any(not (-1e6 <= v <= 1e6) for v in x) for x in r):
            continue
        n = [sum(v * v for v in x) ** 0.5 for x in r]
        if any(abs(x - 1.0) > ORTHO_TOL for x in n):
            continue
        d = sum(r[0][k] * r[1][k] for k in range(3))
        if abs(d) < ORTHO_TOL:
            return at, r
    return None


def ortho(fl):
    """The first 3x3 at any 1-float offset whose rows are unit length and mutually perpendicular."""
    for at in range(0, max(0, len(fl) - 10)):
        r = [fl[at + 4 * i:at + 4 * i + 3] for i in range(3)]
        if any(len(x) < 3 or any(not (-1e6 <= v <= 1e6) for v in x) for x in r):
            continue
        n = [sum(v * v for v in x) ** 0.5 for x in r]
        if any(abs(x - 1.0) > ORTHO_TOL for x in n):
            continue
        d = [sum(r[i][k] * r[j][k] for k in range(3)) for i, j in ((0, 1), (0, 2), (1, 2))]
        if all(abs(x) < ORTHO_TOL for x in d):
            return at, r
    return None


def fmt(rows):
    return '  ' + '\n  '.join(' '.join('%12.6g' % v for v in r) for r in rows)


def main():
    args = sys.argv[1:]
    if not args:
        sys.exit(__doc__)
    path = args[0]
    key_want = args[args.index('--key') + 1] if '--key' in args else None
    slot_want = int(args[args.index('--slot') + 1]) if '--slot' in args else None
    target_want = args[args.index('--target') + 1] if '--target' in args else None
    raw = int(args[args.index('--raw') + 1]) if '--raw' in args else 0
    as_floats = '--floats' in args

    stats, examples = {}, {}
    with open(path, 'r', errors='replace') as f:
        for line in f:
            m = LINE_RE.search(line)
            if m:
                key, target, slot, addr, size, wtxt = (m.group(1), m.group(2), int(m.group(4)), m.group(5),
                                                       int(m.group(6)), m.group(8))
            else:
                m = OLD_RE.search(line)
                if not m:
                    continue
                key, target, slot, addr, size, wtxt = (m.group(1), '-', int(m.group(2)), m.group(3),
                                                       int(m.group(4)), m.group(6))
            if key_want and not key.startswith(key_want):
                continue
            if slot_want is not None and slot != slot_want:
                continue
            if target_want and target != target_want:
                continue
            w = words_of(wtxt)
            st = stats.setdefault((key, target, slot, size), {'n': 0, 'addr': set(), 'zero': 0, 'head': {}, 'aff': 0,
                                                              'ort': 0, 'bas': 0, 'sample': None, 'ort_at': None, 'bas_at': None})
            st['n'] += 1
            st['addr'].add(addr)
            head = tuple(w[:8])
            st['head'][head] = st['head'].get(head, 0) + 1
            if all(x == 0 for x in w):
                st['zero'] += 1
            fl = [f32(x) if x is not None else 0.0 for x in w]
            if affine(fl):
                st['aff'] += 1
                if st['sample'] is None:
                    st['sample'] = affine(fl)
            o = ortho(fl)
            if o:
                st['ort'] += 1
                if st['ort_at'] is None:
                    st['ort_at'] = o
            b = basis(fl)
            if b:
                st['bas'] += 1
                if st['bas_at'] is None:
                    st['bas_at'] = b
            if st['sample'] is None and len(w) > 20:
                st['sample'] = [fl[4 + 4 * i:8 + 4 * i] for i in range(4)]
            examples.setdefault((key, target, slot, size), w)

    if raw:
        for (key, target, slot, size), w in sorted(examples.items()):
            print('%s target %s slot %d size %d: %d words printed' % (key, target, slot, size, len(w)))
            sel = w[:raw]
            if as_floats:
                print('  float: ' + ' '.join('%12.6g' % f32(x) for x in sel))
                print('  int32: ' + ' '.join('%12d' % x for x in sel))
            else:
                print('  hex:   ' + ' '.join('%08x' % x for x in sel))
            print()
        return

    print('%-22s %-11s %5s %7s %6s %6s %5s %6s %5s'
          % ('shader', 'target', 'slot', 'size', 'lines', 'addrs', 'zero', 'affine', 'basis'))
    for (key, target, slot, size), st in sorted(stats.items(), key=lambda kv: (kv[0][0], kv[0][1], kv[0][2], -kv[0][3])):
        print('%-22s %-11s %5d %7d %6d %6d %5d %6d %5d'
              % (key, target, slot, size, st['n'], len(st['addr']), st['zero'], st['aff'], st['bas']))
        if st['aff']:
            print('  affine rows 1-4 (first example):\n' + fmt(st['sample']))
        if st['ort_at']:
            at, rows = st['ort_at']
            print('  orthonormal 3x3 at word %d:\n' % at + fmt(rows))
        elif st['bas_at']:
            at, rows = st['bas_at']
            print('  unit, perpendicular row pair at word %d:\n' % at + fmt(rows))
        heads = sorted(st['head'].items(), key=lambda kv: -kv[1])
        print('  %d distinct first-8-words; most common x%d' % (len(heads), heads[0][1]))
        if st['zero'] == st['n']:
            print('  ** every line reads all zero **')
    if not stats:
        print('no matching draw lines')


if __name__ == '__main__':
    main()
