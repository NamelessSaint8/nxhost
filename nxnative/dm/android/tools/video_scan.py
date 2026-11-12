#!/usr/bin/env python3
"""Scan a screen recording for spatial/temporal artifacts, frame by frame.

Reads raw rgb24 frames of one size from stdin (ffmpeg) and reports, over the
whole clip: per-frame colour metrics, an 8x5 tile grid of mean luma per frame,
per-tile temporal variation, and frame-to-frame tile jumps.  A plane or a wrong
texture is a coherent region that differs from the rest; a pop is a large
one-frame jump in a region while its neighbours stay still; shimmer is a tile
with high temporal variation next to quiet ones.
"""
import sys
import numpy as np

W, H, TX, TY = 320, 200, 8, 5
FS = W * H * 3


def tiles(a):
    """(N,H,W,3) -> (N,TY,TX) mean luma per tile."""
    l = a.astype(np.float32) @ np.array([0.299, 0.587, 0.114], np.float32)
    th, tw = H // TY, W // TX
    return l[:, :TY * th, :TX * tw].reshape(l.shape[0], TY, th, TX, tw).mean(axis=(2, 4))


def main():
    buf = sys.stdin.buffer.read()
    n = len(buf) // FS
    a = np.frombuffer(buf[:n * FS], np.uint8).reshape(n, H, W, 3)
    lum = a.astype(np.float32) @ np.array([0.299, 0.587, 0.114], np.float32)
    r, g, b = (a[:, :, :, i].astype(np.int16) for i in range(3))
    blue = (b > 90) & (b > r + 40) & (b > g + 25)
    green = (g > 90) & (g > r + 30) & (g > b + 30)
    t = tiles(a)

    print(f'frames {n}  {W}x{H}  tiles {TY}x{TX}')
    print(f'luma   mean {lum.mean():6.2f}  min {lum.mean(axis=(1, 2)).min():6.2f}  max {lum.mean(axis=(1, 2)).max():6.2f}')
    print(f'blue   mean {100 * blue.mean():6.3f}%  max {100 * blue.mean(axis=(1, 2)).max():6.3f}%')
    print(f'green  mean {100 * green.mean():6.3f}%  max {100 * green.mean(axis=(1, 2)).max():6.3f}%')

    # per-tile temporal variation (shimmer)
    var = t.std(axis=0)
    med = float(np.median(var))
    print(f'\nper-tile luma std over the clip: median {med:.2f}, max {var.max():.2f}')
    for ty, tx in zip(*np.where(var > max(6 * med, 6))):
        print(f'  tile (row {ty}, col {tx}) std {var[ty, tx]:.2f}  (centre px ~{tx * W // TX + W // TX // 2},{ty * H // TY + H // TY // 2})')

    # frame-to-frame jumps
    d = np.abs(np.diff(t, axis=0))                       # (N-1,TY,TX)
    peak = d.reshape(d.shape[0], -1).max(axis=1)         # worst tile per transition
    print(f'\nframe-to-frame: peak tile jump median {np.median(peak):.2f}, p99 {np.percentile(peak, 99):.2f}')
    order = np.argsort(peak)[::-1][:12]
    for i in sorted(order):
        f = i + 2                                        # 1-based index of the post-transition frame
        big = d[i].max()
        quiet = float(np.median(d[i]))
        ty, tx = np.unravel_index(d[i].argmax(), d[i].shape)
        print(f'  frame {f:4d}: peak tile {big:6.2f} at (row {ty}, col {tx}), median tile {quiet:5.2f}, '
              f'blue {100 * blue[f - 1].mean():5.2f}%')

    # localised pop: a tile jumps while most of the frame is still
    hot = []
    for i in range(len(d)):
        big, quiet = d[i].max(), float(np.median(d[i]))
        if big > 25 and quiet < 4:
            ty, tx = np.unravel_index(d[i].argmax(), d[i].shape)
            hot.append((i + 2, big, quiet, ty, tx))
    print(f'\nlocalised pops (one tile > 25 while median < 4): {len(hot)}')
    for f, big, quiet, ty, tx in hot[:15]:
        print(f'  frame {f}: tile (row {ty}, col {tx}) jump {big:.1f}, median {quiet:.1f}')

    # blue over time, as a series, to see it appear and clear
    bs = 100 * blue.mean(axis=(1, 2))
    print('\nblue fraction per 50-frame block: ' + ' '.join(f'{bs[i:i + 50].max():.1f}' for i in range(0, n, 50)))
    with open('video-scan.txt', 'w') as fh:
        fh.write('peak_tile_jump_per_transition\n')
        fh.write(' '.join(f'{v:.1f}' for v in peak) + '\n')


if __name__ == '__main__':
    main()
