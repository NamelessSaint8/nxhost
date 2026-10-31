# prod.keys for the setup document (porter setup). Only whether the configured file is there; the key-name check comes next.
from pathlib import Path


def step(cfg):
    k = cfg.get('keys') or ''; ok = bool(k) and Path(k).is_file()
    return {'id': 'keys', 'ok': ok, 'detail': k if ok else (f'no such file: {k}' if k else 'not set'), 'fix': '' if ok else 'Choose your prod.keys (dumped from your own Switch).',
            'path': k, 'generation': None, 'missing': [], 'found': []}
def check(path): return {}
def candidates(): return []
