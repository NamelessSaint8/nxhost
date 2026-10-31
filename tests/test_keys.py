# porter/keys.py: prod.keys judged by the key names extraction needs and the highest key generation (D-05), the emulator folders searched per OS (D-06),
# and no key value ever in its answers (T-03-01). The key files are written at run time into temp folders with made-up hex: nothing named *.keys is committed
# (tests/arch_rules.py), and no hex run is written here as a literal.
import hashlib, json, os, sys, tempfile, types, unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
os.environ['NX2A_HOME'] = tempfile.mkdtemp()

from porter import keys, setup   # noqa: E402
from porter.toolchain import Check as Row   # noqa: E402


def fake(name, n=32): return hashlib.sha256(name.encode()).hexdigest()[:n]   # made-up hex, distinct per key name


def keyfile(names, folder=None, header=True):   # a prod.keys-like file: `name = hex` lines; header_key is 64 hex digits (32 bytes)
    d = Path(folder or tempfile.mkdtemp()); d.mkdir(parents=True, exist_ok=True); p = d / 'prod.keys'
    lines = ([f'header_key = {fake("header_key", 64)}'] if header else []) + [f'{n} = {fake(n)}' for n in names]
    p.write_text('\n'.join(lines) + '\n', encoding='utf-8'); return p


def masters(top): return [f'master_key_{i:02x}' for i in range(top + 1)]


def pick(r): return {k: r.get(k) for k in ('ok', 'generation', 'missing', 'detail')}


class Check(unittest.TestCase):
    def test_complete(self):
        self.assertEqual(pick(keys.check(keyfile(masters(0x13)))), {'ok': True, 'generation': 19, 'missing': [], 'detail': 'keys up to generation 19'})

    def test_no_header_key(self):
        r = pick(keys.check(keyfile(masters(0x13), header=False)))
        self.assertEqual((r['ok'], r['missing'], r['detail']), (False, ['header_key'], 'missing header_key'))

    def test_key_area_pair(self):
        r = pick(keys.check(keyfile(['titlekek_05', 'key_area_key_application_05'])))
        self.assertEqual((r['ok'], r['generation']), (True, 5))
        self.assertFalse(keys.check(keyfile(['titlekek_05']))['ok'])   # half a pair is no usable generation

    def test_junk(self):
        p = Path(tempfile.mkdtemp()) / 'prod.keys'; p.write_text('not a keys file\njust words = here\n', encoding='utf-8')
        r = pick(keys.check(p)); self.assertEqual((r['ok'], r['missing']), (False, ['header_key', 'master_key_00']))

    def test_too_big(self):
        p = keyfile(masters(3)); p.write_text(p.read_text() + 'x' * ((1 << 20) + 1))
        r = pick(keys.check(p)); self.assertFalse(r['ok']); self.assertIn('1 MB', r['detail'] or ''); self.assertIsNone(r['generation'])

    def test_missing_file(self):
        r = pick(keys.check(Path(tempfile.mkdtemp()) / 'prod.keys')); self.assertFalse(r['ok']); self.assertIn('no such file', r['detail'] or '')

    def test_no_values_out(self):
        names = masters(0x13) + ['titlekek_00', 'key_area_key_application_00']; p = keyfile(names)
        values = [fake('header_key', 64)] + [fake(n) for n in names]
        rows = [Row(n, True, n, required=n != 'adb') for n in ('Android NDK', '.NET SDK', 'adb', 'Signing key')]
        with mock.patch.object(setup.toolchain, 'checks', return_value=rows), mock.patch.object(keys, 'candidates', return_value=[str(p)]):
            out = json.dumps(keys.check(p)) + json.dumps(setup.report({'keys': str(p), 'legal': ''}))
        for v in values: self.assertNotIn(v, out); self.assertNotIn(v.upper(), out)


def host(name, platform):   # os and sys as another OS shows them to porter.keys (tests/test_toolchain.py's stand-in)
    return types.SimpleNamespace(name=name, environ=os.environ, path=os.path), types.SimpleNamespace(platform=platform)


class Candidates(unittest.TestCase):
    def setUp(self):
        self.h = Path(tempfile.mkdtemp())
        env = mock.patch.dict(os.environ); env.start(); self.addCleanup(env.stop)
        for k in ('APPDATA', 'XDG_CONFIG_HOME', 'XDG_DATA_HOME'): os.environ.pop(k, None)
        p = mock.patch.object(keys.Path, 'home', return_value=self.h); p.start(); self.addCleanup(p.stop)

    def found(self, osname, platform):
        o, s = host(osname, platform)
        with mock.patch.object(keys, 'os', o), mock.patch.object(keys, 'sys', s): return keys.candidates()

    def put(self, *dirs): return [str(keyfile([], self.h / d)) for d in dirs]

    def test_per_os(self):
        os.environ['APPDATA'] = str(self.h / 'Roaming')
        (self.h / 'Roaming/yuzu/keys').mkdir(parents=True)   # a folder without a prod.keys is not listed
        want = self.put('Roaming/Ryujinx/system', 'Roaming/sudachi/keys', '.switch')
        self.assertEqual(self.found('nt', 'win32'), want)
        sup = 'Library/Application Support'
        want = self.put(f'{sup}/Ryujinx/system', f'{sup}/suyu/keys') + [want[-1]]
        self.assertEqual(self.found('posix', 'darwin'), want)
        os.environ['XDG_CONFIG_HOME'] = str(self.h / 'cfg'); os.environ['XDG_DATA_HOME'] = str(self.h / 'data')
        want = self.put('cfg/Ryujinx/system', 'data/eden/keys', 'cfg/citron/keys', '.var/app/io.github.ryubing.Ryujinx/config/Ryujinx/system', '.var/app/org.yuzu_emu.yuzu/data/yuzu/keys') + [want[-1]]
        self.assertEqual(self.found('posix', 'linux'), want)

    def test_step_lists_found(self):
        good, bad = keyfile(masters(4), self.h / 'a'), keyfile([], self.h / 'b'); mine = keyfile(masters(0x13), self.h / 'mine')
        with mock.patch.object(keys, 'candidates', return_value=[str(good), str(bad)]): s = keys.step({'keys': str(mine)})
        self.assertEqual((s['id'], s['ok'], s['path'], s['generation']), ('keys', True, str(mine), 19))
        self.assertEqual([(f['path'], f['ok'], f['generation']) for f in s['found']], [(str(good), True, 4), (str(bad), False, None)])
        self.assertEqual(s['found'][1]['detail'], 'missing master_key_00')

    def test_step_bad_and_unset(self):
        with mock.patch.object(keys, 'candidates', return_value=[]):
            s = keys.step({'keys': str(keyfile(masters(2), header=False))}); u = keys.step({'keys': ''})
        self.assertEqual((s['ok'], s['detail'], s['fix'], s['missing']), (False, 'missing header_key', 'Pick a prod.keys dumped from your own Switch.', ['header_key']))
        self.assertEqual((u['ok'], u['detail'], u['fix']), (False, 'not set', 'Choose your prod.keys (dumped from your own Switch).'))



if __name__ == '__main__': unittest.main()
