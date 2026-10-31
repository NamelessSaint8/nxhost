# porter/setup.py: the readiness document the first-run wizard and the Setup tab draw on every launch (`porter setup --json`). Pinned here: its shape and step order,
# the `ready` rules (D-03: legal, keys, NDK, .NET, signing key; adb and the device never block), `missing` in step order, the legal version match (D-07),
# and `config <key> <value> --json`. Report runs in-process on stand-in check rows; Cli runs `python -m porter` as a subprocess with its own NX2A_HOME.
import json, os, subprocess, sys, tempfile, unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
os.environ['NX2A_HOME'] = tempfile.mkdtemp()

from porter import keys, pins, setup   # noqa: E402
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
        self.assertEqual([{k: v for k, v in i.items() if k != 'download'} for i in t['items']], [all_rows[n] for n in ('Android NDK', '.NET SDK', 'adb')])
        self.assertEqual(t['downloadable'], ['.NET SDK', 'adb'])
        self.assertFalse(t['ok'])
        dv = by['device']; adb = all_rows['adb']
        self.assertTrue(dv['soft']); self.assertEqual((dv['ok'], dv['detail'], dv['fix'], dv['path']), (adb['ok'], adb['detail'], adb['fix'], adb['path']))


def items(d): return {i['name']: i for i in next(s for s in d['steps'] if s['id'] == 'tools')['items']}


PINS = {'Android NDK': ('r27c', 'https://x/ndk.zip', 836128272, 'sha1', 'h'), '.NET SDK': ('10.0.403', 'https://x/dotnet.tar.gz', 0, 'sha512', 'h'), 'adb': ('37.0.1', 'https://x/pt.zip', 9, 'sha1', 'h')}


class ToolFacts(unittest.TestCase):   # D-23: every fact the tools page draws, from pins and the check rows only
    def test_download_sizes(self):
        with mock.patch('porter.fetch._pinned', side_effect=PINS.get): it = items(report(bad=('Android NDK', '.NET SDK')))
        self.assertEqual(it['Android NDK']['download'], {'version': 'r27c', 'size': 836128272})
        self.assertEqual(it['.NET SDK']['download'], {'version': '10.0.403', 'size': 0})   # not pinned: the GUI shows about 200 MB
        self.assertNotIn('download', it['adb'])

    def test_no_lz4(self):   # porter.fetch imports porter.upstream, which needs lz4: setup answers without it
        with mock.patch.dict(sys.modules, {'porter.fetch': None}): d = report(bad=('Android NDK', '.NET SDK'))
        self.assertTrue(all('download' not in i for i in items(d).values())); json.dumps(d)

    def test_device_facts(self):
        r = [Check(n, True, f'{n} detail', required=n not in OPTIONAL, path=f'/x/{n}') for n in NAMES]
        r[NAMES.index('adb')] = Check('adb', True, '/usr/bin/adb', required=False, path='/usr/bin/adb', source='PATH', version='1:29.0.6-28', note='adb 1:29.0.6-28: pushes without -Z')
        with mock.patch.object(setup.toolchain, 'checks', return_value=r), mock.patch.object(setup.keys, 'step', return_value=keystep()): d = setup.report({'legal': str(setup.VERSION)})
        dv = next(s for s in d['steps'] if s['id'] == 'device')
        self.assertEqual((dv['path'], dv['version'], dv['source'], dv['note']), ('/usr/bin/adb', '1:29.0.6-28', 'PATH', 'adb 1:29.0.6-28: pushes without -Z'))

    def test_no_network(self):
        with mock.patch('urllib.request.urlopen', side_effect=AssertionError('setup must not touch the network')): d = report(bad=('Android NDK', '.NET SDK', 'adb'))
        self.assertIn('download', items(d)['Android NDK'])


class Arm64(unittest.TestCase):   # D-25: Google ships no Linux arm64 platform-tools; the community NDK is offered
    def setUp(self):
        for p in (mock.patch('porter.hosttools.linux_arm64', return_value=True), mock.patch('porter.distro.family', return_value='debian')): p.start(); self.addCleanup(p.stop)

    def test_no_adb_download(self):
        d = report(bad=('adb',)); t = next(s for s in d['steps'] if s['id'] == 'tools'); a = items(d)['adb']
        self.assertNotIn('adb', t['downloadable']); self.assertNotIn('download', a)
        self.assertEqual((a['fix'], a['command']), ('Run sudo apt install adb, then press Re-check.', 'sudo apt install adb'))

    def test_ndk_offered(self):
        d = report(bad=('Android NDK',)); t = next(s for s in d['steps'] if s['id'] == 'tools')
        self.assertIn('Android NDK', t['downloadable'])
        self.assertEqual(items(d)['Android NDK']['download'], {'version': 'r27c', 'size': pins.NDK['files']['linux-arm64'][1]})


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
