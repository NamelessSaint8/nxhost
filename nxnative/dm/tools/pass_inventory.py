#!/usr/bin/env python3
"""List what each stage of one frame actually produced, by pass.

A `DM_VDRAW_PASSSHOT=<path %d>` run with `DM_VDRAW_ALLPASS=1` writes one dump per draw pass and one `vdraw2:` line per
pass carrying the vertex program, whether depth was attached, the colour mask and the target. This joins the two and
measures each dump, so "what is in this frame and what is missing" is a table instead of an impression.

Two limits that make a reading wrong if ignored:
  * the dump holds the target's bytes with the Metal pixel format in its header. Only format 92 (BGRA8) decodes as the
    4-byte texels read here; a half-float or depth target reads as noise and is reported as undecodable rather than
    measured.
  * DM_VDRAW_SHOT_MAX caps the number of dumps, so a frame contributes only as many passes as the cap allows. The
    pass count in the summary says how many of the frame's passes the table covers.

Usage: pass_inventory.py <log> <dump-glob> [--min-lit N] [--all-formats]
  --min-lit N     only passes at or above N % lit (default 0)
  --all-formats   also print passes whose target format cannot be decoded here, marked as such
"""
import collections
import glob
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pngstat  # the shared reader: raw header + PNG, same shape either way

PASS_RE = re.compile(r'vdraw2: pass (\d+) vs (\S+) depth (\w+) n(\d+) targets(.*?) chmask (0x[0-9a-f]+)')
DECODABLE = {92}   # BGRA8Unorm: the only format whose first four bytes are the colour as read here


def measure(path):
    w, h, nch, px = pngstat.read_image(path)
    lit = tot = 0
    colours = set()
    for y in range(0, h, 9):
        for x in range(0, w, 9):
            i = (y * w + x) * nch
            if px[i] or px[i + 1] or px[i + 2]:
                lit += 1
                colours.add((px[i] >> 4, px[i + 1] >> 4, px[i + 2] >> 4))
            tot += 1
    return (100.0 * lit / max(1, tot), len(colours), w, h)


def main():
    args = sys.argv[1:]
    if len(args) < 2:
        sys.exit(__doc__)
    log, pattern = args[0], args[1]
    min_lit = float(args[args.index('--min-lit') + 1]) if '--min-lit' in args else 0.0
    all_formats = '--all-formats' in args

    passes = {}
    for line in open(log, errors='replace'):
        m = PASS_RE.search(line)
        if m:
            passes[int(m.group(1))] = (m.group(2), m.group(3), m.group(4), m.group(5).strip())
    if not passes:
        sys.exit('no vdraw2 lines in %s: run with DM_VDRAW_ALLPASS=1' % log)

    rows, formats, undecodable = [], collections.Counter(), 0
    for path in sorted(glob.glob(pattern)):
        m = re.search(r'pass-(\d+)\.\w+$', path)
        if not m:
            continue
        n = int(m.group(1))
        hdr = open(path, 'rb').read(64).split(b'\n')[0].split()
        if len(hdr) != 4:
            continue
        fmt = int(hdr[2])
        formats[fmt] += 1
        if fmt not in DECODABLE:
            undecodable += 1
            if all_formats:
                rows.append((-1.0, -1, int(hdr[0]), int(hdr[1]), n, passes.get(n, ('?', '?', '0', '?'))))
            continue
        lit, cols, w, h = measure(path)
        rows.append((lit, cols, w, h, n, passes.get(n, ('?', '?', '0', '?'))))

    rows.sort(key=lambda r: -r[0])
    print('%-6s %5s %9s %6s %-5s %-24s %s' % ('lit%', 'cols', 'size', 'pass', 'nv', 'vertex program', 'chmask'))
    for lit, cols, w, h, n, (key, depth, nview, mask) in rows:
        if lit < min_lit:
            continue
        lit_s = 'n/a' if lit < 0 else '%.1f' % lit
        cols_s = '-' if cols < 0 else str(cols)
        print('%-6s %5s %9s %6d %-5s %-24s %s' % (lit_s, cols_s, '%dx%d' % (w, h), n, nview, key, mask))
    print('passes in the log: %d; dumps: %d over %d format(s); undecodable here: %d'
          % (len(passes), sum(formats.values()), len(formats), undecodable))
    if undecodable:
        print('formats seen: %s (only %s decode as colour bytes here)' % (dict(sorted(formats.items())), sorted(DECODABLE)))


if __name__ == '__main__':
    main()
