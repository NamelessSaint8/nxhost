# What setup still needs (`porter setup --json`): the readiness document the first-run wizard and the Setup tab draw on every launch (FRUN-03: the GUI stores none of it).
# One toolchain.checks() call, no network, no device listing (`adb devices` starts a server and can stall), and it never writes config.json: the legal notice is
# accepted only through `porter config legal <VERSION>`. Fields are added, never renamed (gui/firstrun.py, the shell and the bundle smoke test read them); no version field.
import json, sys

from porter import config, distro, hosttools, keys, paths, toolchain

VERSION = 1   # bump it whenever TEXT changes: an older accepted version counts as not accepted, so the wizard asks again (D-07)
TEXT = ('Use nx2android only with game dumps and prod.keys from a Switch you own. Nothing is uploaded: your games and keys stay on this computer and go only to your own '
        'Android device. The Android NDK, the .NET SDK and Android platform-tools are downloaded from Google and Microsoft and come under their makers\' licenses:')
# fetch.LICENSES' URLs, written out here: porter.fetch needs lz4, and a dev checkout without it must still get this document (with the red Python modules row)
LINKS = {'Android NDK': 'https://developer.android.com/studio/terms', 'adb': 'https://developer.android.com/studio/terms', '.NET SDK': 'https://github.com/dotnet/core/blob/main/license-information.md'}
TOOLS = ('Android NDK', '.NET SDK', 'adb')


def accepted(cfg):   # the notice version the player accepted, 0 for none or junk
    try: return int(cfg.get('legal') or 0)
    except ValueError: return 0


def tool_items(tools):
    """The tools step's items: each check row, plus `download` {version, size} from porter/pins.py for a missing tool porter can fetch on this host (size 0 for .NET:
    not pinned, the GUI shows about 200 MB), and on Linux arm64 the distribution's adb command for a Copy command button (D-23, D-25). No network: pins and rows only"""
    arm64 = hosttools.linux_arm64(); can = [r.name for r in tools if not r.ok and not (r.name == 'adb' and arm64)]   # fetch.missing agrees: no platform-tools for arm64
    try: import porter.fetch as fetch
    except ImportError: fetch = None   # porter.fetch needs lz4 (through porter.upstream): no sizes in a dev checkout without it
    out = []
    for r in tools:
        d = r.as_dict()
        if fetch and r.name in can and (p := fetch._pinned(r.name)): d['download'] = {'version': p[0], 'size': p[2]}
        if arm64 and r.name == 'adb' and not r.ok: d.update(fix=distro.adb_hint(), command=distro.adb_install())   # '' for an unknown distribution: no Copy button
        out.append(d)
    return out, can


def report(cfg=None):
    cfg = cfg if cfg is not None else config.load()
    rows = toolchain.checks(cfg); by = {r.name: r for r in rows}
    acc = accepted(cfg); legal_ok = acc == VERSION
    legal = {'id': 'legal', 'ok': legal_ok, 'detail': 'accepted' if legal_ok else ('the notice changed since you accepted it' if acc else 'not accepted yet'), 'fix': '' if legal_ok else 'read and accept the notice'}
    ks = keys.step(cfg)
    tools = [by[n] for n in TOOLS]; need = [r.name for r in tools if r.required and not r.ok]; items, can = tool_items(tools)
    tstep = {'id': 'tools', 'ok': not need, 'detail': 'missing: ' + ', '.join(need) if need else 'every tool is here', 'fix': 'Download missing tools, or choose your own' if need else '',
             'items': items, 'downloadable': can}
    adb = by['adb']   # D-12, D-13: which adb a tester's report names, and whether it pushes with -Z
    device = {'id': 'device', 'ok': adb.ok, 'soft': True, 'detail': adb.detail, 'fix': adb.fix, 'path': adb.path, 'version': adb.version, 'source': adb.source, 'note': adb.note}
    missing = (['the legal notice'] if not legal_ok else []) + (['prod.keys'] if not ks['ok'] else []) + [r.name for r in rows if r.required and not r.ok and r.name != 'prod.keys']
    return {'ready': not missing, 'legal': {'version': VERSION, 'accepted': acc, 'text': TEXT, 'links': LINKS}, 'steps': [legal, ks, tstep, device], 'missing': missing,
            'notes': ['No adb yet: port now, install later.'] if not adb.ok else [], 'desktop': {'offer': paths.FROZEN and sys.platform.startswith('linux')},   # D-20: the Linux bundle only
            'checks': [r.as_dict() for r in rows]}


def main(a):
    d = report()
    if a.json: print(json.dumps(d, ensure_ascii=False, indent=2))
    else:
        for s in d['steps']: print(f'{"ok " if s["ok"] else "!! "} {s["id"]:7} {s["detail"]}' + (f'\n{"":11}→ {s["fix"]}' if s['fix'] and not s['ok'] else ''))
        print('ready' if d['ready'] else 'missing: ' + ', '.join(d['missing']))
    return 0 if d['ready'] else 1
