# prod.keys for the setup document (porter setup): read only for the key *names* extraction needs and the highest key generation (D-05). No value is ever
# printed, logged or returned, and the file is never copied: the emulator folders are only searched, and the one the player picks is saved as a path (D-06). No network.
import glob, os, re, sys
from pathlib import Path

LINE = re.compile(r'^\s*([A-Za-z0-9_]+)\s*=\s*([0-9A-Fa-f]+)\s*$')
IDX = re.compile(r'(master_key|titlekek|key_area_key_application)_([0-9a-f]{2})')   # key names read from LibHac 0.19.0, which nx_extract uses
MAX_BYTES = 1 << 20   # a Lockpick dump is a few KB: anything over 1 MB is another file, and is not read (T-03-02)
FAMILY = ('yuzu', 'eden', 'citron', 'sudachi', 'suyu')   # the yuzu forks' folder names: guesses, harmless when wrong (RESEARCH A6)


def check(path):
    """{'ok', 'detail', 'generation', 'missing'}: the names extraction needs, never the values. A generation is usable with master_key_XX (LibHac derives the rest)
    or with both titlekek_XX and key_area_key_application_XX; generation is the highest usable index (master_key_13 → 19), kept as an int for Phase 4 to compare"""
    p = Path(path); bad = lambda d: {'ok': False, 'detail': d, 'generation': None, 'missing': []}
    try:
        if not p.is_file(): return bad(f'no such file: {p}')
        if p.stat().st_size > MAX_BYTES: return bad(f'{p} is not a prod.keys file (over 1 MB)')
        text = p.read_text(encoding='utf-8', errors='replace')
    except OSError as e: return bad(f'cannot read {p}: {e.strerror or e}')
    names = {m[1].lower(): len(m[2]) for ln in text.splitlines() if (m := LINE.match(ln))}   # name → hex length: the value itself is dropped here
    by = {}
    for k in names:
        if m := IDX.fullmatch(k): by.setdefault(int(m[2], 16), set()).add(m[1])
    usable = [g for g, s in by.items() if 'master_key' in s or {'titlekek', 'key_area_key_application'} <= s]
    missing = ([] if names.get('header_key') == 64 else ['header_key']) + ([] if usable else ['master_key_00'])
    gen = max(usable) if usable else None
    return {'ok': not missing, 'generation': gen, 'missing': missing, 'detail': 'missing ' + ', '.join(missing) if missing else f'keys up to generation {gen}'}   # no colon: the GUI shows `<path>: <detail>`


def candidates():
    """The prod.keys in the usual emulator folders for this OS, in order: Ryujinx (and Ryubing, which keeps the folder name), the yuzu family, then ~/.switch"""
    h = Path.home()
    if os.name == 'nt':
        ad = Path(os.environ.get('APPDATA') or h / 'AppData/Roaming'); dirs = [ad / 'Ryujinx/system', *[ad / f / 'keys' for f in FAMILY]]
    elif sys.platform == 'darwin':
        sup = h / 'Library/Application Support'; dirs = [sup / 'Ryujinx/system', *[sup / f / 'keys' for f in FAMILY]]
    else:
        cfg = Path(os.environ.get('XDG_CONFIG_HOME') or h / '.config'); data = Path(os.environ.get('XDG_DATA_HOME') or h / '.local/share')
        dirs = [cfg / 'Ryujinx/system', *[d / f / 'keys' for d in (data, cfg) for f in FAMILY],
                *map(Path, sorted(glob.glob(str(h / '.var/app/*/config/Ryujinx/system')))), *map(Path, sorted(glob.glob(str(h / '.var/app/*/data/*/keys'))))]   # Flatpak
    dirs.append(h / '.switch')   # Ryujinx's and hactool's per-user folder (AppDataManager.cs KeysDirPathUser)
    return list(dict.fromkeys(str(d / 'prod.keys') for d in dirs if (d / 'prod.keys').is_file()))


def step(cfg):
    k = cfg.get('keys') or ''
    r = check(k) if k else {'ok': False, 'detail': 'not set', 'generation': None, 'missing': []}
    fix = '' if r['ok'] else ('Pick a prod.keys dumped from your own Switch.' if k else 'Choose your prod.keys (dumped from your own Switch).')
    return {'id': 'keys', **r, 'fix': fix, 'path': k, 'found': [{'path': p, **check(p)} for p in candidates()]}
