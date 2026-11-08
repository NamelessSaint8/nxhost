#!/usr/bin/env python3
"""Read one translated program in one place: its reflection, its notes, and the MSL it became.

The chain directory holds three things per program -- `<key>.json` (reflection: bindings, vertex inputs,
threadgroup, notes), `<key>.metal` (the generated source) and `<key>.metallib` -- and a hunt ends up grepping
them one at a time. This prints them joined: who the program is, what it is given, what the translator said
about it, and the lines of MSL that matter.

Usage:
  shader_view.py <chain-dir> <key> [--metal N] [--facts TSV] [--reflect]
  shader_view.py <chain-dir> --notes [PATTERN]      every program carrying a translator note
  shader_view.py <chain-dir> --list [PATTERN]       keys with stage and note count

  --metal N   also print the first N lines of <key>.metal (0 = all)
  --facts T   the profile's answer table, to say whether this key has query answers
  --reflect   print the whole reflection JSON instead of the summary
"""
import json
import os
import sys


def load_chain(d):
    keys = []
    for name in sorted(os.listdir(d)):
        if name.endswith('.json') and not name.endswith('.metallib'):
            keys.append(name[:-5])
    return keys


def summary(chain, key, facts_path=None, metal_lines=0, reflect=False):
    jp = os.path.join(chain, key + '.json')
    if not os.path.exists(jp):
        sys.exit('%s: no reflection for %s' % (chain, key))
    j = json.load(open(jp))
    if reflect:
        print(json.dumps(j, indent=2))
        return
    stage = j.get('stage', '?')
    print('%s  stage %s  route %s  entry %s (%s)' % (key, stage, j.get('route', '?'), j.get('entry', '?'),
                                                     j.get('msl_entry_kind', '?')))
    if j.get('chain'):
        print('  chain %s   compiler %s' % (j['chain'], j.get('chain_compiler', '?')))
    tg = j.get('threadgroup_size') or j.get('local')
    if tg:
        print('  threadgroup %s   shared %s' % (tg, j.get('shared', 0)))
    if 'c1' in j:
        print('  c1 bytes %d' % (len(j['c1']) // 2))

    notes = j.get('notes') or []
    if facts_path:
        known = False
        with open(facts_path, errors='replace') as f:
            for line in f:
                if line.startswith('#') or '\t' not in line:
                    continue
                k = line.split('\t', 1)[0].strip()
                if k == key:
                    known = True
                    break
        print('  answer table: %s' % ('entry present' if known else 'NO ENTRY -- every query uses defaults'))
    if notes:
        for n in notes:
            print('  note: %s' % n)
    else:
        print('  notes: none')

    b = j.get('bindings') or []
    if b:
        print('  %d binding(s):' % len(b))
        for e in b:
            reg = e.get('reg', e.get('bank', '-'))
            print('    id %-3s %-14s %-18s kind %-8s reg %-3s%s'
                  % (e.get('arg_id', '?'), e.get('msl_name', '?'), e.get('msl_type', '?'), e.get('kind', '?'), reg,
                     '  rw' if e.get('rw') else ''))
    vi = j.get('vertex_inputs') or []
    if vi:
        print('  %d vertex input(s): %s' % (len(vi), vi if len(str(vi)) < 200 else '(see --reflect)'))
    for f in ('raster', 'vs_pad', 'pull', 'drv_reads', 'drv_unfillable', 'pc_paired'):
        v = j.get(f)
        if v:
            print('  %s: %s' % (f, v if len(str(v)) < 200 else '(see --reflect)'))

    mp = os.path.join(chain, key + '.metal')
    if metal_lines and os.path.exists(mp):
        print('  --- %s ---' % os.path.basename(mp))
        with open(mp, errors='replace') as f:
            for i, line in enumerate(f):
                if metal_lines and i >= metal_lines:
                    print('  ... (%d more lines)' % (sum(1 for _ in f)))
                    break
                print('  ' + line.rstrip())


def main():
    args = sys.argv[1:]
    if len(args) < 2:
        sys.exit(__doc__)
    chain, key = args[0], args[1]
    facts = args[args.index('--facts') + 1] if '--facts' in args else None
    metal = int(args[args.index('--metal') + 1]) if '--metal' in args else 0
    reflect = '--reflect' in args
    if key == '--list' or key == '--notes':
        pattern = args[2] if len(args) > 2 and not args[2].startswith('--') else ''
        for k in load_chain(chain):
            if pattern and pattern not in k:
                continue
            try:
                j = json.load(open(os.path.join(chain, k + '.json')))
            except Exception:
                continue
            notes = j.get('notes') or []
            if key == '--notes' and not notes:
                continue
            print('%-24s %-3s %s' % (k, j.get('stage', '?'), '; '.join(notes) if notes else ''))
        return
    summary(chain, key, facts, metal, reflect)


if __name__ == '__main__':
    main()
