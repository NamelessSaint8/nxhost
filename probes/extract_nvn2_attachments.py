#!/usr/bin/env python3
"""Join native mesh draws to Mac pass attachments and export compile fixtures.

All outputs, including shader keys and trace excerpts, belong beside the game.
Metal collapses both NVN depth/stencil precisions to format 260: check both.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path


def extract(text):
    attachments, state, contexts = {}, {}, {}
    count = 0
    for line_number, line in enumerate(text.splitlines(), 1):
        match = re.search(r'\[pass\] F\d+ ([Pdn])\s+(\d+)\s+(.*)', line)
        if not match:
            continue
        tag, pid, body = match.groups()
        if tag == 'P':
            target = body.split()[0]
            attachments.setdefault(pid, {})[target] = body
        elif tag == 'd':
            state[pid] = dict(re.findall(r'(\w+)=([^ ]+)', body))
        elif tag == 'n' and 'NVN2 mesh' in body:
            count += 1
            s = state[pid]
            a = attachments[pid]
            if set(a) - {'c0', 'd'}:
                raise ValueError('fixture supports one color target and optional depth')
            color = re.search(r'fmt=(\d+) (\d+)x(\d+) ms(\d+)', a['c0'])
            depth = re.search(r'fmt=(\d+)', a.get('d', ''))
            keys = dict(re.findall(r'(task|mesh)=([^ ]+)', body))
            keys['pixel'] = s['fs']
            keys = {k: v.removesuffix('_b') if v != '-' else '0' for k, v in keys.items()}
            if s['vs'].removesuffix('_b') != keys['mesh']:
                raise ValueError('mesh draw and latest draw state disagree')
            if not color or s['st'] != '0' or s['po'] != '0/0,0,0' or s['dc'] != '0':
                raise ValueError('unsupported attachment or raster state')
            row = dict(keys, metal_color=int(color[1]), width=int(color[2]), height=int(color[3]), samples=int(color[4]), metal_depth=int(depth[1]) if depth else 0,
                       state={k: s[k] for k in ('blend', 'b0', 'dt', 'dw', 'df', 'cull', 'cmask')})
            signature = json.dumps(row, sort_keys=True)
            if signature not in contexts:
                contexts[signature] = dict(row, source_line=line_number, pass_id=int(pid), sampled_draws=0)
            contexts[signature]['sampled_draws'] += 1
    return {'sampled_native_draws': count, 'contexts': list(contexts.values())}


def fixture_rows(report):
    colors = {13: 0x03, 70: 0x25, 110: 0x2a, 115: 0x29}
    rows = []
    for row in report['contexts']:
        if row['metal_depth'] not in (0, 260):
            raise ValueError('unmapped depth format')
        s = row['state']
        packed = int(s['b0'], 0)
        if packed >> 37:
            raise ValueError('advanced blend state is not represented')
        blend = [(packed >> shift) & ((1 << width)-1) for shift, width in ((3, 7), (10, 7), (17, 7), (24, 7), (31, 3), (34, 3))]
        for depth in (0x35, 0x36) if row['metal_depth'] else (0,):
            fields = [row['task'], row['mesh'], row['pixel'], f'{colors[row["metal_color"]]:x}', f'{depth:x}', row['samples'],
                      int(s['dt']), int(s['dw']), int(s['df']), int(s['cull']), int(s['blend'], 0) & 1,
                      *blend, int(s['cmask'], 0) & 15]
            rows.append(' '.join(map(str, fields)))
    return sorted(set(rows))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('log', type=Path)
    parser.add_argument('out', type=Path, help='external game work directory')
    args = parser.parse_args()
    raw = args.log.read_bytes()
    report = extract(raw.decode(errors='replace'))
    rows = fixture_rows(report)
    report.update(source=str(args.log.resolve()), source_sha256=hashlib.sha256(raw).hexdigest(), compile_cases=len(rows),
                  depth_precision='Metal 260 is ambiguous; both D24S8 and D32S8 are checked',
                  integer_color='Metal R8Uint is represented by NVN R8UI to preserve the observed attachment numeric type')
    args.out.mkdir(exist_ok=True)
    (args.out/'observed-attachments.json').write_text(json.dumps(report, indent=2)+'\n')
    (args.out/'observed-attachments.tsv').write_text('# task mesh pixel color_nvn depth_nvn samples dt dw compare cull blend src dst srca dsta eq eqa mask\n'+'\n'.join(rows)+'\n')
    print(f'{report["sampled_native_draws"]} native draws, {len(report["contexts"])} contexts, {len(rows)} compile cases')
    return 0 if rows else 1


if __name__ == '__main__':
    raise SystemExit(main())
