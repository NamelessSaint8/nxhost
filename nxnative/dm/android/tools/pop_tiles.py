#!/usr/bin/env python3
"""Compare where on screen two screen recordings pop, tile by tile.

A single-tile colour flip that lasts a frame or two is what a wrong draw or a
wrong texture looks like at 20 fps; camera motion moves a band of tiles
together instead. This counts, per tile, the transitions where one tile jumps
while the median tile of that transition stays put, so two clips can be compared
by where and how often it happens rather than by eye.

Usage: pop_tiles.py CLIP.mp4 [OTHER.mp4 ...]
"""
import argparse
import subprocess
import sys

import numpy as np

W, H, TX, TY = 320, 200, 8, 5
JUMP, QUIET = 25.0, 4.0


def frames(path):
    """Decode a clip to (n, H, W, 3) at the analysis size, through ffmpeg."""
    cmd = ['ffmpeg', '-v', 'error', '-i', path, '-vf', f'scale={W}:{H}',
           '-fps_mode', 'passthrough', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-']
    out = subprocess.run(cmd, capture_output=True, check=True).stdout
    n = len(out) // (W * H * 3)
    return np.frombuffer(out[:n * W * H * 3], np.uint8).reshape(n, H, W, 3)


def duration(path):
    """Clip length in seconds, so a rate does not assume one frame rate."""
    out = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0',
                          '-show_entries', 'format=duration', '-of', 'default=nw=1:nk=1', path],
                         capture_output=True, text=True, check=True).stdout.strip()
    return float(out)


def analyse(path):
    a = frames(path).astype(np.float32)
    lum = a @ np.array([0.299, 0.587, 0.114], np.float32)
    th, tw = H // TY, W // TX
    t = lum[:, :TY * th, :TX * tw].reshape(len(a), TY, th, TX, tw).mean(axis=(2, 4))
    d = np.abs(np.diff(t, axis=0))
    peak = d.reshape(len(d), -1).max(axis=1)
    quiet = np.median(d.reshape(len(d), -1), axis=1)
    pop = (peak > JUMP) & (quiet < QUIET)
    count = np.zeros((TY, TX))
    first = np.full((TY, TX), -1)
    for i in np.where(pop)[0]:
        ty, tx = np.unravel_index(d[i].argmax(), d[i].shape)
        count[ty, tx] += 1
        if first[ty, tx] < 0:
            first[ty, tx] = int(i + 2)
    return {'path': path, 'frames': len(a), 'secs': duration(path), 'pops': int(pop.sum()),
            'count': count, 'first': first, 'peak': peak, 'pop': pop}


def show(r):
    print(f"\n=== {r['path']}  ({r['frames']} frames, {r['secs']:.1f} s, {r['frames'] / r['secs']:.1f} fps, {r['pops']} pops)")
    print('pops per tile (top row first):')
    for ty in range(TY):
        print('  ' + ' '.join(f'{int(r["count"][ty, tx]):3d}' for tx in range(TX)))
    print(f'  tiles touched {int((r["count"] > 0).sum())} of {TY * TX}, '
          f'first pop frame {int(r["first"][r["first"] > 0].min()) if (r["first"] > 0).any() else "-"}')
    print(f'  rate {r["pops"] / (r["secs"] / 60):.1f} pops per 60 s of clip')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('clips', nargs='+')
    a = ap.parse_args()
    results = [analyse(p) for p in a.clips]
    for r in results:
        show(r)
    if len(results) == 2:
        delta = results[1]['count'] - results[0]['count']
        print('\n=== delta (second minus first), per tile')
        for ty in range(TY):
            print('  ' + ' '.join(f'{int(delta[ty, tx]):+4d}' for tx in range(TX)))
        print(f"  totals {results[0]['pops']} -> {results[1]['pops']}")


if __name__ == '__main__':
    sys.exit(main())