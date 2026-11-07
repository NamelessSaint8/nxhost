#!/usr/bin/env python3
"""Which shaders carry a translator note, by key.

The build prints a note's count and nothing else ("translator 2838 in 2838 shaders Attribute offset 0x5C is not valid."), which
says how many shaders are affected but not which -- so an affected shader cannot be opened, rebuilt alone, or compared against
another game. Every note is already in the reflection JSON of each shader it applies to, so this reads a built chain directory and
groups keys by note. It does not touch the translation chain, so listing notes never costs a retranslation.

Usage: shader_notes.py <chain dir, e.g. .../metal_shader_cache/b-<chain>> [substring of a note] [--keys N] [--stage vs|ps|cs]
"""
import glob, json, collections, sys


def main(argv):
    if not argv:
        sys.exit(__doc__.split('\n')[0] + '\nusage: shader_notes.py <chain dir> [note substring] [--keys N] [--stage vs|ps|cs]')
    d = argv[0]
    want, nkeys, stage = '', 8, ''
    i = 1
    while i < len(argv):
        if argv[i] == '--keys' and i + 1 < len(argv): nkeys = int(argv[i + 1]); i += 2
        elif argv[i] == '--stage' and i + 1 < len(argv): stage = argv[i + 1]; i += 2
        else: want = argv[i]; i += 1
    by = collections.defaultdict(list)
    files = sorted(glob.glob(d.rstrip('/') + '/*_b.json'))
    for f in files:
        try: j = json.load(open(f))
        except (OSError, ValueError): continue
        if stage and j.get('stage') != stage: continue
        for n in j.get('notes', ()):
            if not n.startswith('translator: '): continue
            msg = n[len('translator: '):]
            if want and want.lower() not in msg.lower(): continue
            by[msg].append(j.get('key') or f)
    print(f'{len(files)} shaders in {d}')
    for msg, ks in sorted(by.items(), key=lambda kv: -len(kv[1])):
        print(f'{len(ks):6d}  {msg}')
        print('        keys: ' + ' '.join(ks[:nkeys]) + (f' (+{len(ks) - nkeys} more)' if len(ks) > nkeys else ''))
    if not by: print('no note matched')

main(sys.argv[1:])
