#!/usr/bin/env python3
"""Replace one explicitly selected compute module in a diagnostic DMSV copy.

The native raw convolution uses the captured driver's ABI. This is a measured
experiment with numerical differences, never an automatic production lowering.
All other shaders, flags and reflection records are retained byte for byte.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess


def replace(source, shader, destination, key, *, preserve_local_size=False):
    if source.resolve() == destination.resolve():
        raise ValueError('diagnostic destination must differ from source')
    subprocess.run(['spirv-val', '--target-env', 'vulkan1.2', str(shader)], check=True)
    data = source.read_bytes()
    magic, version, count = struct.unpack_from('<4sII', data)
    if magic != b'DMSV' or version != 1 or 12+32*count > len(data):
        raise ValueError('invalid bundle')
    entries, blobs, changed = [], [], 0
    offset = 12+32*count
    for i in range(count):
        k, stage, at, size, rat, rsize, flags = struct.unpack_from('<Q6I', data, 12+32*i)
        if at+size > len(data) or rat+rsize > len(data) or rsize < 20:
            raise ValueError('truncated module/reflection')
        binary, reflection = data[at:at+size], data[rat:rat+rsize]
        if k == key:
            if stage != 5:
                raise ValueError('selected shader is not compute')
            binary = shader.read_bytes()
            if not preserve_local_size:
                header = list(struct.unpack_from('<5I', reflection))
                header[2:] = [64, 1, 1]
                reflection = struct.pack('<5I', *header)+reflection[20:]
            changed += 1
        entries.append(struct.pack('<Q6I', k, stage, offset, len(binary), offset+len(binary), len(reflection), flags))
        blobs.extend((binary, reflection))
        offset += len(binary)+len(reflection)
    if changed != 1:
        raise ValueError('requires exactly one matching shader key')
    destination.write_bytes(struct.pack('<4sII', magic, version, count)+b''.join(entries)+b''.join(blobs))
    report = dict(modules=count, changed=changed, key=f'{key:016x}',
                  source_sha256=hashlib.sha256(data).hexdigest(),
                  native_sha256=hashlib.sha256(shader.read_bytes()).hexdigest(),
                  diagnostic_only=True, numerical_equivalence=False)
    destination.with_suffix('.json').write_text(json.dumps(report, indent=2)+'\n')
    return report


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('source', type=Path)
    p.add_argument('shader', type=Path)
    p.add_argument('destination', type=Path)
    p.add_argument('--key', required=True, type=lambda s: int(s, 16))
    p.add_argument('--preserve-local-size', action='store_true')
    a = p.parse_args()
    print(json.dumps(replace(a.source, a.shader, a.destination, a.key,
                             preserve_local_size=a.preserve_local_size), indent=2))
