# porter/setup.py: the readiness document the first-run wizard and the Setup tab draw on every launch (`porter setup --json`). Pinned here: its shape and step order,
# the `ready` rules (D-03: legal, keys, NDK, .NET, signing key; adb and the device never block), `missing` in step order, the legal version match (D-07),
# and `config <key> <value> --json`. Report runs in-process on stand-in check rows; Cli runs `python -m porter` as a subprocess with its own NX2A_HOME.
import json, os, subprocess, sys, tempfile, unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
os.environ['NX2A_HOME'] = tempfile.mkdtemp()

from porter import keys, setup   # noqa: E402
from porter.toolchain import Check   # noqa: E402

NAMES = ('Python', 'Python modules', 'Pillow', 'Android NDK', '.NET SDK', 'adb', 'prod.keys', 'Signing key', 'Disk space')
OPTIONAL = ('Pillow', 'adb', 'Disk space')


def rows(bad=()):   # stand-in toolchain.checks() rows, every one ok but those named
    return [Check(n, n not in bad, f'{n} detail', required=n not in OPTIONAL, path=f'/x/{n}', fix='' if n not in bad else f'fix {n}') for n in NAMES]


def keystep(ok=True): return {'id': 'keys', 'ok': ok, 'detail': 'keys up to generation 19' if ok else 'not set', 'fix': '' if ok else 'choose', 'path': '', 'generation': 19 if ok else None, 'missing': [], 'found': []}


def report(bad=(), legal=None, keys_ok=True):
    cfg = {'legal': str(setup.VERSION) if legal is None else legal, 'keys': ''}
    with mock.patch.object(setup.toolchain, 'checks', return_value=rows(bad)), mock.patch.object(setup.keys, 'step', return_value=keystep(keys_ok)): return setup.report(cfg)


class Report(unittest.TestCase):
    def test_shape(self):
        d = report()
        self.assertEqual(set(d), {'ready', 'legal', 'steps', 'missing', 'notes', 'desktop', 'checks'})
        self.assertEqual([s['id'] for s in d['steps']], ['legal', 'keys', 'tools', 'device'])
        self.assertEqual(d['checks'], [r.as_dict() for r in rows()])
        self.assertEqual(set(d['legal']), {'version', 'accepted', 'text', 'links'})
        self.assertEqual(d['legal']['version'], setup.VERSION); self.assertEqual(set(d['legal']['links']), {'Android NDK', 'adb', '.NET SDK'})
        json.dumps(d)

    def test_ready_rules(self):
        d = report(); self.assertTrue(d['ready']); self.assertEqual(d['missing'], [])
        for legal in ('', '0', 'abc', str(setup.VERSION - 1)):
            with self.subTest(legal=legal): self.assertFalse(report(legal=legal)['ready'])
        self.assertFalse(report(keys_ok=False)['ready'])
        for n in ('Android NDK', '.NET SDK', 'Signing key'):
            with self.subTest(row=n): self.assertFalse(report(bad=(n,))['ready'])
        d = report(bad=('adb',))
        self.assertTrue(d['ready']); self.assertIn('No adb yet: port now, install later.', d['notes'])

    def test_missing_order(self):
        d = report(bad=('Android NDK', 'Signing key'), legal='', keys_ok=False)
        self.assertEqual(d['missing'], ['the legal notice', 'prod.keys', 'Android NDK', 'Signing key']); self.assertFalse(d['ready'])

    def test_tools_step(self):
        d = report(bad=('.NET SDK', 'adb')); by = {s['id']: s for s in d['steps']}; all_rows = {r.name: r.as_dict() for r in rows(('.NET SDK', 'adb'))}
        t = by['tools']
        self.assertEqual(t['items'], [all_rows[n] for n in ('Android NDK', '.NET SDK', 'adb')]); self.assertEqual(t['downloadable'], ['.NET SDK', 'adb'])
        self.assertFalse(t['ok'])
        dv = by['device']; adb = all_rows['adb']
        self.assertTrue(dv['soft']); self.assertEqual((dv['ok'], dv['detail'], dv['fix'], dv['path']), (adb['ok'], adb['detail'], adb['fix'], adb['path']))


def porter(*args, home):
    e = dict(os.environ, NX2A_HOME=str(home), PYTHONIOENCODING='utf-8'); e.pop('NX2A_GUI', None)
    return subprocess.run([sys.executable, '-m', 'porter', *map(str, args)], cwd=REPO, env=e, capture_output=True, text=True, encoding='utf-8', timeout=120)


class Cli(unittest.TestCase):
    def setUp(self): self.home = Path(tempfile.mkdtemp())

    def doc(self, r):
        self.assertNotIn('Traceback', r.stderr); return json.loads(r.stdout)

    def step(self, d, i): return next(s for s in d['steps'] if s['id'] == i)

    def test_no_config(self):
        r = porter('setup', '--json', home=self.home); d = self.doc(r)
        self.assertFalse((self.home / 'config.json').exists())
        self.assertEqual(r.returncode, 1); self.assertFalse(d['ready']); self.assertFalse(self.step(d, 'legal')['ok'])
        self.assertEqual(d['missing'][:2], ['the legal notice', 'prod.keys'])

    def test_legal_round_trip(self):
        v = str(setup.VERSION)
        r = porter('config', 'legal', v, '--json', home=self.home)
        self.assertEqual(r.returncode, 0, r.stderr); self.assertEqual(self.doc(r), {'key': 'legal', 'value': v})
        self.assertTrue(self.step(self.doc(porter('setup', '--json', home=self.home)), 'legal')['ok'])
        r = porter('config', 'legal', '999', '--json', home=self.home)
        self.assertEqual(r.returncode, 1); self.assertIn(v, self.doc(r)['error'])
        self.assertTrue(self.step(self.doc(porter('setup', '--json', home=self.home)), 'legal')['ok'])   # the refused value was not saved

    def test_config_json_any_key(self):
        r = porter('config', 'out', '/tmp/x', '--json', home=self.home)
        self.assertEqual(r.returncode, 0, r.stderr); self.assertEqual(self.doc(r), {'key': 'out', 'value': '/tmp/x'})
        self.assertEqual(self.doc(porter('config', 'out', '--json', home=self.home)), {'key': 'out', 'value': '/tmp/x'})
        r = porter('config', 'nosuch', '1', '--json', home=self.home)
        self.assertEqual(r.returncode, 1); self.assertIn('nosuch', self.doc(r)['error'])

    def test_checks_match_doctor(self):
        d = self.doc(porter('setup', '--json', home=self.home)); doc = self.doc(porter('doctor', '--json', home=self.home))
        self.assertEqual([c['name'] for c in d['checks']], [c['name'] for c in doc])


if __name__ == '__main__': unittest.main()
