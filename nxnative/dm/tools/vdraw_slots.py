#!/usr/bin/env python3
"""Read vertex uniform blocks out of a DM_VDRAW_ROWS log and judge whether a slot holds a transform.

A DM_VDRAW_ROWS=1 run prints, per pass, a 'vubo slot K addr A size S rows R:' summary followed by every row of that
block; the rows of all slots share one stream and their numbering restarts at 0 per slot, so a row belongs to the
nearest slot header above it. This groups them that way and answers the one question a first-four-rows read could
not: does any slot hold a plausible 4x4 (a row of 0,0,0,1, finite moderate entries, a small translation) or is every
slot integer bit patterns printed as floats? Values are '%.6g' of the float view, so a bit pattern is recognisable
(|v| < 1e-30 and not zero) but not recoverable exactly -- this tool classifies, it does not decode.

Usage: vdraw_slots.py <log> [--pass N] [--slots 0,1,2,3] [--fullmask] [--matrix] [--size S] [--distinct] [--pairs]
                      [--rows A-B]
  --pass N     print the first four rows of the given pass's slots
  --fullmask   only passes whose target is a full-mask 2048x1152 world pass
  --matrix     census: the passes where some slot holds a matrix-shaped 4x4, with one example each
  --size S     only slot blocks of exactly S bytes
  --distinct   how many distinct addresses and first rows a slot has: a per-draw block varies, a stale bind does not
  --pairs      print a block as 8-byte elements (two floats) as well as 4-float rows
  --rows A-B   with --pass, print rows A..B of each selected slot instead of rows 0-3"""
import re
import sys

# The header gained a "vs <shader key>" field and "ser <serial>" fields, so both spellings are accepted:
#   vdraw: pass 1278 target 2048x1152 fmt 63 | depth 2048x1152 fmt 53 | ds dt1 dw0 df3 st0 | chmask 0xffffffff ...
#   vdraw: pass 1297 vs 7a1585ef822af63c_b target 2048x1152 fmt 63 ser 34472 | depth 2048x1152 fmt 53 ser 34471 | ds dt1 dw1 df2 st0 | chmask 0 ...
PASS_RE = re.compile(r'vdraw: pass (\d+)(?: vs \S+)? target (\d+)x(\d+) fmt (\d+)(?: ser \d+)? \| depth [^|]*\| ds (dt\d dw\d df\d st\d) \| chmask (0x[0-9a-f]+)')
SLOT_RE = re.compile(r'vdraw:   vubo slot (\d+) addr (0x[0-9a-f]+) size (\d+) rows (\d+): '
                     r'nonzero (\d+), real-number floats (\d+), first real row (-?\d+)')
ROW_RE = re.compile(r'vdraw:     row (\d+):(.*)')

AFFINE_BOTTOM = ((0.0, 0.0, 0.0, 1.0), (0.0, 0.0, 0.0, 0.0))
MODERATE = 1e6


def parse(path):
    """Yield (pass header dict, [slot blocks]) in file order; a slot block is a dict with its rows."""
    cur, slots, slot = None, [], None
    with open(path, 'r', errors='replace') as f:
        for line in f:
            m = PASS_RE.search(line)
            if m:
                if cur:
                    yield cur, slots
                cur = {'pass': int(m.group(1)), 'w': int(m.group(2)), 'h': int(m.group(3)),
                       'fmt': int(m.group(4)), 'ds': m.group(5), 'chmask': int(m.group(6), 16)}
                slots, slot = [], None
                continue
            m = SLOT_RE.search(line)
            if m:
                slot = {'k': int(m.group(1)), 'addr': m.group(2), 'size': int(m.group(3)),
                        'rows': int(m.group(4)), 'nz': int(m.group(5)), 'sane': int(m.group(6)),
                        'first': int(m.group(7)), 'vals': {}}
                slots.append(slot)
                continue
            m = ROW_RE.search(line)
            if m and slot is not None:
                slot['vals'][int(m.group(1))] = [float(x) for x in m.group(2).split()][:4]
    if cur:
        yield cur, slots


def row(blk, r):
    return blk['vals'].get(r)


def bit_pattern(v):
    return v != 0.0 and -1e-30 < v < 1e-30


def matrix_at(blk, r):
    """A 4x4 at rows r..r+3: finite, moderate, and its last row an affine or degenerate bottom row."""
    rows = [row(blk, r + i) for i in range(4)]
    if any(x is None or len(x) != 4 for x in rows):
        return None
    if any(not (-MODERATE <= v <= MODERATE) for x in rows for v in x):
        return None
    if any(bit_pattern(v) for x in rows for v in x):
        return None
    if tuple(rows[3]) not in AFFINE_BOTTOM:
        return None
    return rows


def find_matrix(blk, span=16):
    for r in range(min(span, blk['rows'] - 3)):
        m = matrix_at(blk, r)
        if m:
            return r, m
    return None


def fmt_rows(rows):
    return ' | '.join(' '.join('%9.5g' % v for v in x) for x in rows)


def flat(blk, n):
    """The block's first n floats as a flat stream. A row the logger left unprinted (all zero) counts as four zeros,
    so the stream keeps its alignment -- row numbering, not row order, is what the log guarantees."""
    out = []
    for r in range((n + 3) // 4):
        out.extend(blk['vals'].get(r, [0.0, 0.0, 0.0, 0.0]))
    return out[:n]


def main():
    args = sys.argv[1:]
    if not args:
        sys.exit(__doc__)
    path = args[0]
    want_pass = int(args[args.index('--pass') + 1]) if '--pass' in args else None
    want_slots = {int(s) for s in args[args.index('--slots') + 1].split(',')} if '--slots' in args else {0, 1, 2, 3}
    fullmask = '--fullmask' in args
    size = int(args[args.index('--size') + 1]) if '--size' in args else None
    census = '--matrix' in args
    distinct = '--distinct' in args
    pairs = '--pairs' in args
    lo, hi = 0, 4
    if '--rows' in args:
        lo, hi = (int(x) for x in args[args.index('--rows') + 1].split('-'))

    sizes, matrices, passes, split, seen = {}, {}, 0, {}, {}
    for hdr, slots in parse(path):
        if fullmask and not (hdr['w'] == 2048 and hdr['h'] == 1152 and hdr['chmask'] & 0xffffffff == 0xffffffff):
            continue
        passes += 1
        for blk in slots:
            if blk['k'] not in want_slots:
                continue
            if size is not None and blk['size'] != size:
                continue
            sizes.setdefault(blk['k'], {}).setdefault(blk['size'], 0)
            sizes[blk['k']][blk['size']] += 1
            split.setdefault(blk['k'], {}).setdefault(blk['sane'], 0)
            split[blk['k']][blk['sane']] += 1
            d = seen.setdefault(blk['k'], {'addr': set(), 'head': {}, 'last': []})
            d['addr'].add(blk['addr'])
            key = tuple(flat(blk, 8))
            d['head'][key] = d['head'].get(key, 0) + 1
            d['last'] = (hdr['pass'], blk['size'], key)
            hit = find_matrix(blk)
            if hit:
                matrices.setdefault(blk['k'], []).append((hdr['pass'], blk['size'], hit))
        if want_pass is not None and hdr['pass'] == want_pass:
            print('pass %d %dx%d fmt %d chmask %#x' % (hdr['pass'], hdr['w'], hdr['h'], hdr['fmt'], hdr['chmask']))
            for blk in slots:
                if blk['k'] not in want_slots:
                    continue
                print('  slot %d addr %s size %d rows %d nonzero %d real %d first real row %d'
                      % (blk['k'], blk['addr'], blk['size'], blk['rows'], blk['nz'], blk['sane'], blk['first']))
                for r in range(lo, min(hi + 1, blk['rows'])):
                    if row(blk, r) is not None:
                        print('    %2d: %s' % (r, fmt_rows([row(blk, r)])))
                if pairs and blk['sane'] >= 12:
                    q = flat(blk, 8)
                    print('    pairs: %s' % ' | '.join('%.6g,%.6g' % (q[i], q[i + 1]) for i in range(0, 8, 2)))
                hit = find_matrix(blk)
                print('    matrix 4x4: %s' % ('none' if not hit else 'rows %d-3: %s' % (hit[0], fmt_rows(hit[1]))))

    print('passes scanned: %d%s' % (passes, ' (full-mask 2048x1152)' if fullmask else ''))
    for k in sorted(sizes):
        tot = sum(sizes[k].values())
        hist = ', '.join('%d B x%d' % (s, n) for s, n in sorted(sizes[k].items()))
        real = ', '.join('%d x%d' % (s, n) for s, n in sorted(split[k].items()))
        print('slot %d: %d blocks -- sizes %s; real-number floats %s' % (k, tot, hist, real))
    if census:
        for k in sorted(want_slots):
            hits = matrices.get(k, [])
            print('slot %d matrix-shaped 4x4 in first 16 rows: %d/%d passes'
                  % (k, len(hits), sum(sizes[k].values()) if k in sizes else 0))
            for p, s, (r, m) in hits[:3]:
                print('  pass %d size %d rows %d-3: %s' % (p, s, r, fmt_rows(m)))
    if distinct:
        for k in sorted(want_slots):
            d = seen.get(k)
            if not d:
                continue
            heads = sorted(d['head'].items(), key=lambda kv: -kv[1])
            print('slot %d: %d blocks over %d addresses, %d distinct first-8-floats'
                  % (k, sum(d['head'].values()), len(d['addr']), len(heads)))
            for key, n in heads[:4]:
                print('  x%-4d %s' % (n, ' '.join('%.6g' % v for v in key)))
            print('  last seen: pass %d size %d' % (d['last'][0], d['last'][1]))


if __name__ == '__main__':
    main()
