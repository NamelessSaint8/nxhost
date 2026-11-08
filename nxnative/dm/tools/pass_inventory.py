#!/usr/bin/env python3
"""List what each stage of one frame actually produced, by pass, decoding every format it uses.

A `DM_VDRAW_PASSSHOT=<path %d>` run with `DM_VDRAW_ALLPASS=1` writes one dump per draw pass and one `vdraw2:` line per
pass carrying the vertex program, whether depth was attached, the colour mask and the target. This joins the two and
measures each dump, so "what is in this frame and what is missing" is a table instead of an impression.

The dump holds each texel in a 16-byte slot and names its Metal pixel format in the header, so the format decides how
to read the bytes. A BGRA8 target read as packed floats (or the reverse) produces a full-looking frame out of noise --
that mistake is why this tool decodes explicitly and reports the format it used. Formats handled:

    70 RGBA8Unorm      71 RGBA8Unorm_sRGB     80 BGRA8Unorm      81 BGRA8Unorm_sRGB
    92 RG11B10Float   115 RGBA16Float        125 RGBA32Float     55 R32Float
    30 RG8Unorm        65 RG16Float          110 RGBA16Unorm    112 RGBA16Snorm
   250 Depth16Unorm   252 Depth32Float       260 Depth32Float_Stencil8   (reported as depth, not colour)

Anything else is listed with its format number and marked undecodable rather than measured. Values are mapped to 0..255
by a plain linear scale with a clamp, which is enough to tell "content" from "empty"; it is not a tonemap.

Usage: pass_inventory.py <log> <dump-glob> [--min-lit N] [--all-formats]
"""
import collections
import glob
import os
import re
import struct
import sys

PASS_RE = re.compile(r'vdraw2: pass (\d+) vs (\S+) depth (\w+) n(\d+) targets(.*?) chmask (0x[0-9a-f]+)')
DEPTH = {250, 252, 253, 260}


def ufloat(v, ebits, mbits):
    """An unsigned mini-float as Metal packs one: e exponent bits above m mantissa bits."""
    e = (v >> mbits) & ((1 << ebits) - 1)
    m = v & ((1 << mbits) - 1)
    bias = (1 << (ebits - 1)) - 1
    if e == 0:
        return (m / float(1 << mbits)) * 2.0 ** (1 - bias) if m else 0.0
    if e == (1 << ebits) - 1:
        return float('inf')
    return (1.0 + m / float(1 << mbits)) * 2.0 ** (e - bias)


def pixel(fmt, b):
    """(r, g, b) in 0..255 from the first bytes of one texel slot."""
    if fmt in (80, 81):                       # BGRA8
        return b[2], b[1], b[0]
    if fmt in (70, 71):                       # RGBA8
        return b[0], b[1], b[2]
    if fmt == 92:                             # RG11B10Float: r 0..10, g 11..21, b 22..31
        w = struct.unpack('<I', b[:4])[0]
        r, g, bl = w & 0x7ff, (w >> 11) & 0x7ff, (w >> 22) & 0x3ff
        return (min(255, int(ufloat(r, 5, 6) * 255)), min(255, int(ufloat(g, 5, 6) * 255)),
                min(255, int(ufloat(bl, 5, 5) * 255)))
    if fmt == 115:                            # RGBA16Float
        h = struct.unpack('<4e', b[:8])
        return tuple(min(255, max(0, int(v * 255))) for v in h[:3])
    if fmt == 125:                            # RGBA32Float
        f = struct.unpack('<4f', b[:16])
        return tuple(min(255, max(0, int(v * 255))) for v in f[:3])
    if fmt == 55:                             # R32Float: grey
        v = min(255, max(0, int(struct.unpack('<f', b[:4])[0] * 255)))
        return v, v, v
    if fmt in (65,):                          # RG16Float
        h = struct.unpack('<2e', b[:4])
        v = min(255, max(0, int(h[0] * 255)))
        return v, v, v
    if fmt in (110, 112):                     # RGBA16Unorm / Snorm
        u = struct.unpack('<4H', b[:8])
        return tuple(min(255, u[i] >> 8) for i in range(3))
    if fmt == 30:                             # RG8Unorm
        return b[0], b[1], 0
    return None


def read_dump(path):
    data = open(path, 'rb').read()
    nl = data.index(b'\n')
    w, h, fmt, bpr = (int(x) for x in data[:nl].split())
    body = data[nl + 1:]
    return w, h, fmt, bpr, body


def measure(path):
    w, h, fmt, bpr, body = read_dump(path)
    if fmt in DEPTH:
        return None
    lit = tot = 0
    colours = set()
    for y in range(0, h, 9):
        row = y * bpr
        for x in range(0, w, 9):
            c = pixel(fmt, body[row + x * 16:row + x * 16 + 16])
            if c is None:
                return None
            tot += 1
            if c[0] or c[1] or c[2]:
                lit += 1
                colours.add((c[0] >> 4, c[1] >> 4, c[2] >> 4))
    return (100.0 * lit / max(1, tot), len(colours), w, h, fmt)


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

    rows, formats, skipped = [], collections.Counter(), collections.Counter()
    for path in sorted(glob.glob(pattern)):
        m = re.search(r'pass-(\d+)\.\w+$', path)
        if not m:
            continue
        n = int(m.group(1))
        w, h, fmt, bpr, _ = read_dump(path)
        formats[fmt] += 1
        got = measure(path)
        if got is None:
            skipped[fmt] += 1
            if all_formats:
                rows.append((-1.0, -1, w, h, fmt, n, passes.get(n, ('?', '?', '0', '?'))))
            continue
        lit, cols, w, h, fmt = got
        rows.append((lit, cols, w, h, fmt, n, passes.get(n, ('?', '?', '0', '?'))))

    rows.sort(key=lambda r: -r[0])
    print('%-6s %5s %9s %4s %6s %-5s %-24s %s' % ('lit%', 'cols', 'size', 'fmt', 'pass', 'nv', 'vertex program', 'chmask'))
    for lit, cols, w, h, fmt, n, (key, depth, nview, mask) in rows:
        if lit < min_lit:
            continue
        print('%-6s %5s %9s %4d %6d %-5s %-24s %s'
              % ('n/a' if lit < 0 else '%.1f' % lit, '-' if cols < 0 else cols, '%dx%d' % (w, h), fmt, n, nview, key, mask))
    print('passes in the log: %d; dumps: %d; formats: %s' % (len(passes), sum(formats.values()), dict(sorted(formats.items()))))
    if skipped:
        print('undecodable or depth here: %s' % dict(sorted(skipped.items())))


if __name__ == '__main__':
    main()
