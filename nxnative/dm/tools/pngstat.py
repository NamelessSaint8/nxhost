#!/usr/bin/env python3
"""Measure a screenshot: is there a picture, and where is it?

The hunt for MKW's world has twice turned on "the frame is black" and once on a reading taken from the wrong bytes,
so a capture should be answered with numbers rather than a look. This decodes an 8-bit PNG (grey, RGB or RGBA, not
interlaced -- what the host's shot writes), then reports the mean luminance, the share of pixels that are not
essentially black, the colour histogram's spread, and a coarse grid of mean colours so a sky, a title card and a
black frame are told apart without opening the file.

Usage: pngstat.py <file.png> [--grid WxH] [--thresh N]
  --grid WxH    the occupancy grid (default 32x18); each cell prints as a hex colour, '..' when the cell is black
  --thresh N    a pixel counts as lit above this luminance 0-255 (default 8)
"""
import struct
import sys
import zlib


def read_png(path):
    data = open(path, 'rb').read()
    if data[:8] != b'\x89PNG\r\n\x1a\n':
        sys.exit('%s is not a PNG' % path)
    pos, idat, w = 8, [], None
    while pos < len(data):
        ln, typ = struct.unpack('>I4s', data[pos:pos + 8])
        body = data[pos + 8:pos + 8 + ln]
        if typ == b'IHDR':
            w, h, depth, ctype, _, _, interlace = struct.unpack('>IIBBBBB', body)
            if depth != 8 or interlace:
                sys.exit('only 8-bit non-interlaced PNGs are read (depth %d, interlace %d)' % (depth, interlace))
            nch = {0: 1, 2: 3, 4: 2, 6: 4}[ctype]
        elif typ == b'IDAT':
            idat.append(body)
        elif typ == b'IEND':
            break
        pos += 12 + ln
    if w is None:
        sys.exit('no IHDR')
    raw = zlib.decompress(b''.join(idat))
    stride = w * nch
    out = bytearray(h * stride)
    prev = bytearray(stride)
    for y in range(h):
        f = raw[y * (stride + 1)]
        line = bytearray(raw[y * (stride + 1) + 1:(y + 1) * (stride + 1)])
        if f == 1:
            for i in range(nch, stride):
                line[i] = (line[i] + line[i - nch]) & 0xff
        elif f == 2:
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 0xff
        elif f == 3:
            for i in range(stride):
                a = line[i - nch] if i >= nch else 0
                line[i] = (line[i] + ((a + prev[i]) >> 1)) & 0xff
        elif f == 4:
            for i in range(stride):
                a = line[i - nch] if i >= nch else 0
                b = prev[i]
                c = prev[i - nch] if i >= nch else 0
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                pr = a if pa <= pb and pa <= pc else (b if pb <= pc else c)
                line[i] = (line[i] + pr) & 0xff
        out[y * stride:(y + 1) * stride] = line
        prev = line
    return w, h, nch, out


def main():
    args = sys.argv[1:]
    if not args:
        sys.exit(__doc__)
    path = args[0]
    gw, gh = (int(x) for x in (args[args.index('--grid') + 1].split('x') if '--grid' in args else ('32', '18')))
    thresh = int(args[args.index('--thresh') + 1]) if '--thresh' in args else 8
    w, h, nch, px = read_png(path)

    def rgb(x, y):
        i = (y * w + x) * nch
        if nch >= 3:
            return px[i], px[i + 1], px[i + 2]
        v = px[i]
        return v, v, v

    lit = 0
    tot = 0
    lum_sum = 0
    colours = {}
    for y in range(0, h, 3):
        for x in range(0, w, 3):
            r, g, b = rgb(x, y)
            lum = (r * 299 + g * 587 + b * 114) // 1000
            lum_sum += lum
            tot += 1
            if lum > thresh:
                lit += 1
                k = (r >> 4, g >> 4, b >> 4)
                colours[k] = colours.get(k, 0) + 1
    print('%s: %dx%d, %d channels' % (path, w, h, nch))
    print('  mean luminance %d/255, lit %d of %d sampled pixels (%.1f%%)' % (lum_sum // max(1, tot), lit, tot, 100.0 * lit / max(1, tot)))
    top = sorted(colours.items(), key=lambda kv: -kv[1])[:6]
    print('  %d distinct coarse colours among lit pixels; top: %s'
          % (len(colours), ', '.join('#%02x%02x%02x x%d' % (r * 17, g * 17, b * 17, n) for (r, g, b), n in top)))
    print('  grid %dx%d (mean colour per cell, .. for black):' % (gw, gh))
    for gy in range(gh):
        row = []
        for gx in range(gw):
            r = g = b = cnt = 0
            for y in range(gy * h // gh, (gy + 1) * h // gh, 4):
                for x in range(gx * w // gw, (gx + 1) * w // gw, 4):
                    rr, gg, bb = rgb(x, y)
                    r += rr; g += gg; b += bb; cnt += 1
            cnt = max(1, cnt)
            r //= cnt; g //= cnt; b //= cnt
            row.append('..' if (r * 299 + g * 587 + b * 114) // 1000 <= thresh else '%02x%02x%02x' % (r, g, b))
        print('    ' + ' '.join(row))


if __name__ == '__main__':
    main()
