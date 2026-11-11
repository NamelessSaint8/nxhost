#!/usr/bin/env python3
"""Audit actual DMSV image instructions and observed mesh/fragment interfaces.

Reports facts from the bundle; no game programs are dispatched. Outputs derived
from game shaders belong in the external game work folder.
"""
import argparse
import collections
import concurrent.futures
import json
from pathlib import Path
import struct
import subprocess

OPERATIONS = {87: 'implicit', 88: 'explicit', 89: 'dref_implicit',
              90: 'dref_explicit', 91: 'projected_implicit', 92: 'projected_explicit',
              93: 'projected_dref_implicit', 94: 'projected_dref_explicit',
              95: 'fetch', 96: 'gather', 97: 'dref_gather', 98: 'read',
              103: 'size_lod', 104: 'size', 105: 'query_lod',
              106: 'levels', 107: 'samples'}


def instructions(binary):
    if len(binary) < 20 or len(binary) % 4:
        raise ValueError('malformed SPIR-V length')
    words = struct.unpack(f'<{len(binary)//4}I', binary)
    if words[0] != 0x07230203:
        raise ValueError('malformed SPIR-V magic')
    result = []
    i = 5
    while i < len(words):
        n, op = words[i] >> 16, words[i] & 0xffff
        if not n or i+n > len(words):
            raise ValueError('malformed SPIR-V instruction')
        result.append((op, words[i:i+n]))
        i += n
    return result


def inspect(binary):
    code = instructions(binary)
    types, values, decorations, variables = {}, {}, collections.defaultdict(dict), []
    for op, w in code:
        if 19 <= op <= 39:
            types[w[1]] = (op, w[2:])
        if op in (45, 46, 55, 57, 61, 65, 66, 67, 70, 83, 86, 100, 169, 245, 400):
            values[w[2]] = w[1]
        if op == 71:
            decorations[w[1]][w[2]] = list(w[3:])
        if op == 59:
            variables.append((w[1], w[2], w[3]))

    def image_type(ident):
        op, args = types[ident]
        if op == 27:
            op, args = types[args[0]]
        return args if op == 25 else None

    counts, unresolved = collections.Counter(), collections.Counter()
    for op, w in code:
        if op not in OPERATIONS:
            continue
        if w[3] not in values:
            unresolved[OPERATIONS[op]] += 1
            continue
        image = image_type(values[w[3]])
        if not image or image[1] != 1 or not image[3]:
            continue
        scalar = types[image[0]]
        kind = 'shadow' if image[2] == 1 else 'float' if scalar[0] == 22 else 'int' if scalar[1][1] else 'uint'
        if image[5] == 2:
            kind = 'storage_'+kind
        operand = 6 if op in (89, 90, 93, 94, 96, 97) else 5
        mask = w[operand] if 87 <= op <= 98 and len(w) > operand else 0
        counts[f'{kind}:{OPERATIONS[op]}:mask={mask}'] += 1

    def scalar_type(ident):
        op, args = types[ident]
        if op in (28, 29, 32):
            return scalar_type(args[-1] if op == 32 else args[0])
        if op == 23:
            return scalar_type(args[0])+f'x{args[1]}'
        if op in (21, 22):
            return ('float' if op == 22 else 'int' if args[1] else 'uint')+str(args[0])
        return f'unsupported_type_{op}'

    io = {'input': {}, 'output': {}}
    for ty, var, storage in variables:
        if storage not in (1, 3) or 30 not in decorations[var]:
            continue
        loc = str(decorations[var][30][0])
        io['input' if storage == 1 else 'output'][loc] = {
            'type': scalar_type(ty), 'flat': 14 in decorations[var],
            'perprimitive': 5271 in decorations[var]}
    return {'array_operations': dict(counts), 'unresolved_image_values': dict(unresolved), 'io': io}


def entries(data):
    magic, version, count = struct.unpack_from('<4sII', data)
    if magic != b'DMSV' or version != 1 or 12+32*count > len(data):
        raise ValueError('invalid DMSV header')
    for i in range(count):
        key, stage, off, size, roff, rsize, flags = struct.unpack_from('<Q6I', data, 12+32*i)
        if off+size > len(data) or roff+rsize > len(data):
            raise ValueError('invalid DMSV entry range')
        yield f'{key:016x}', stage, data[off:off+size], flags


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('bundle', type=Path)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--pipelines', type=Path, help='observed-pipelines.json from actual run evidence')
    parser.add_argument('--validate', type=Path, help='external directory for SPIR-V validation inputs/results')
    args = parser.parse_args()
    modules, counts, unresolved = {}, collections.Counter(), collections.Counter()
    pending = []
    if args.validate:
        args.validate.mkdir(parents=True, exist_ok=True)
    for key, stage, binary, flags in entries(args.bundle.read_bytes()):
        result = inspect(binary)
        modules[key] = dict(stage=stage, flags=flags, **result)
        counts.update(result['array_operations'])
        unresolved.update(result['unresolved_image_values'])
        if args.validate:
            path = args.validate/(key+'.spv')
            path.write_bytes(binary)
            pending.append(path)

    pipelines = []
    if args.pipelines:
        for row in json.loads(args.pipelines.read_text())['pipelines']:
            mesh, pixel = modules[row['mesh']], modules[row['fragment']]
            mismatches, missing = [], []
            for loc, wanted in pixel['io']['input'].items():
                output = mesh['io']['output'].get(loc)
                if not output:
                    missing.append(loc)
                elif output['type'].split('x')[0] != wanted['type'].split('x')[0]:
                    mismatches.append(loc)
            pipelines.append(dict(row, missing_locations=missing, type_mismatches=mismatches))

    validations = []
    if pending:
        def validate(path):
            r = subprocess.run(['spirv-val', '--target-env', 'vulkan1.2', str(path)], capture_output=True, text=True)
            return {'key': path.stem, 'exit': r.returncode, 'error': r.stderr}
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            validations = list(pool.map(validate, pending))
        (args.validate/'results.json').write_text(json.dumps(validations, indent=2)+'\n')
    report = {'modules': len(modules), 'array_operations': dict(counts),
              'unresolved_image_values': dict(unresolved), 'observed_pipelines': pipelines,
              'spirv_modules_validated': len(validations),
              'spirv_validation_failures': sum(v['exit'] != 0 for v in validations) if pending else None,
              'programs': modules}
    args.out.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({k: v for k, v in report.items() if k != 'programs'}, indent=2))
    return int(bool(report['spirv_validation_failures'] or unresolved))


if __name__ == '__main__':
    raise SystemExit(main())
