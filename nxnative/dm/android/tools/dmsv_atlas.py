#!/usr/bin/env python3
"""Upgrade native 2D sampling in a validated DMSV without retranslating guest code.

Existing array wrappers, constant banks, stage metadata and native mesh trailers
are retained. Every changed module is independently validated by compile_atlas.
Failures leave the destination untouched and are recorded beside the build.
"""
import argparse
import concurrent.futures
import hashlib
import json
import struct
from pathlib import Path

import shader_vk

STAGE = {value: key for key, value in shader_vk.STAGES.items()}


def reflect_2d(reflection, bindings):
    """Change sampled-image dimensionality and append matching atlas metadata."""
    header = list(struct.unpack_from('<5I', reflection))
    end = 20 + header[0] * 20
    if end + header[1] > len(reflection): raise ValueError('truncated reflection')
    records = [bytearray(reflection[20+i*20:40+i*20]) for i in range(header[0])]
    for binding in bindings:
        matched = [r for r in records if struct.unpack_from('<H', r, 4)[0] == binding]
        if len(matched) != 1 or matched[0][1] != 2 or matched[0][2] != 1:
            raise ValueError(f'binding {binding}: no unique sampled 2D reflection')
        if any(struct.unpack_from('<H', r, 4)[0] == 2048+binding for r in records):
            raise ValueError('atlas metadata binding collision')
        matched[0][3] |= 17
        records.append(bytearray(struct.pack('<BBBBHHhBBii', 15, 1, 255, 0,
                                            2048+binding, 1, -1, 0, 0, binding, 0)))
    header[0] = len(records)
    return struct.pack('<5I', *header) + b''.join(records) + reflection[end:]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('destination', type=Path)
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--jobs', type=int, default=4)
    parser.add_argument('--reuse',action='store_true',help='reuse independently validated outputs with identical generated GLSL in this work folder')
    args = parser.parse_args()
    args.work.mkdir(parents=True, exist_ok=True)
    data = args.source.read_bytes()
    magic, version, count = struct.unpack_from('<4sII', data)
    if magic != b'DMSV' or version != 1 or 12+count*32 > len(data):
        raise ValueError('invalid DMSV header')
    entries = []
    for index in range(count):
        key, stage, offset, size, roffset, rsize, flags = struct.unpack_from('<Q6I', data, 12+index*32)
        if offset+size > len(data) or roffset+rsize > len(data): raise ValueError('truncated entry')
        entries.append((key, stage, data[offset:offset+size], data[roffset:roffset+rsize], flags))
    failures, changed, converted = [], 0, 0

    def upgrade(entry):
        key, stage, binary, reflection, flags = entry
        images = shader_vk.spirv_bindings(binary)[0]
        if not any(b['type'] == 'sampled' and b['dim'] == 1 and not b['arrayed'] and not b.get('ms') for b in images):
            return entry, []
        output = args.work/f'{key:016x}.spv'
        new, bindings = shader_vk.compile_atlas(binary, STAGE[stage], output, reuse=args.reuse)
        if not bindings: return entry, []
        return (key, stage, new, reflect_2d(reflection, bindings), flags | (4 if stage == 1 else 0)), bindings

    output = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as pool:
        futures = {pool.submit(upgrade, entry): entry for entry in entries}
        for completed, future in enumerate(concurrent.futures.as_completed(futures), 1):
            original = futures[future]
            try:
                entry, bindings = future.result()
                changed += bool(bindings)
                converted += len(bindings)
                output.append(entry)
            except Exception as error:
                detail=getattr(error,'stderr',None) or getattr(error,'stdout',None) or str(error)
                if isinstance(detail,bytes):detail=detail.decode(errors='replace')
                failure={'key': f'{original[0]:016x}', 'stage': original[1], 'error': detail}
                failures.append(failure)
                if len(failures)<=8:print(json.dumps(failure),flush=True)
            if completed % 250 == 0: print(f'{completed}/{count}, {changed} changed, {len(failures)} failures', flush=True)
    report = {'input_sha256': hashlib.sha256(data).hexdigest(), 'programs': count,
              'changed': changed, 'bindings': converted, 'failures': failures}
    (args.work/'upgrade.json').write_text(json.dumps(report, indent=2)+'\n')
    if failures:
        print(json.dumps(failures[:12], indent=2))
        raise SystemExit(f'{len(failures)} conversions failed; destination unchanged')
    offset = 12+count*32
    table, blobs = [], []
    for key, stage, binary, reflection, flags in sorted(output):
        table.append(struct.pack('<Q6I', key, stage, offset, len(binary), offset+len(binary), len(reflection), flags))
        blobs.extend((binary, reflection))
        offset += len(binary)+len(reflection)
    args.destination.write_bytes(struct.pack('<4sII', b'DMSV', 1, count)+b''.join(table)+b''.join(blobs))
    print(f'{count} programs, {changed} upgraded, {converted} bindings; {offset/1048576:.2f} MiB')


if __name__ == '__main__': main()
