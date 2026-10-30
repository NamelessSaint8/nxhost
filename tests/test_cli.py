# porter's command line answers every error with a named message, never a bare traceback: each case runs `python -m porter` as a subprocess with its own NX2A_HOME
# (no game files, toolchains or device), and devtools/device.py takes its device and app from the environment before devtools/device.json.
import contextlib, io, json, os, struct, subprocess, sys, tempfile, unittest
from argparse import Namespace
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
os.environ['NX2A_HOME'] = tempfile.mkdtemp()   # this process too, though porter runs only in the subprocesses, each with its own

MISSING = None
for _m in ('lz4.block', 'capstone'):   # port and install import porter.upstream
    try: __import__(_m)
    except ModuleNotFoundError:
        if os.environ.get('CI'): raise   # CI installs the lock: a missing module there is a failure
        MISSING = MISSING or _m


def setUpModule():   # not a module-level SkipTest: `python -m unittest tests.test_cli` crashes on one
    if MISSING: raise unittest.SkipTest(f'{MISSING} is not installed (python -m pip install -r requirements.txt)')


def _env(home, extra=None):
    e = dict(os.environ, NX2A_HOME=str(home), PYTHONIOENCODING='utf-8'); e.pop('NX2A_GUI', None); e.update(extra or {})
    return e


def porter(*args, home, env=None):
    return subprocess.run([sys.executable, '-m', 'porter', *map(str, args)], cwd=REPO, env=_env(home, env), capture_output=True, text=True, encoding='utf-8', timeout=120)


def events(out): return [json.loads(ln) for ln in out.splitlines() if ln.startswith('{')]


class ErrorPaths(unittest.TestCase):
    def setUp(self): self.home, self.dir = Path(tempfile.mkdtemp()), Path(tempfile.mkdtemp())

    def no_traceback(self, r): self.assertNotIn('Traceback', r.stderr)

    def error_event(self, r):
        err = [e for e in events(r.stdout) if e['ev'] == 'error']
        self.assertEqual(len(err), 1, r.stdout); return err[0]['msg']

    def test_tools_unknown(self):
        r = porter('tools', '--only', 'bogus', '--json', home=self.home)
        self.assertEqual(r.returncode, 2, r.stderr); self.no_traceback(r)
        msg = json.loads(r.stdout)['error']
        self.assertIn('bogus', msg); self.assertIn('ndk, dotnet, adb', msg)
        r = porter('tools', '--only', 'ndk,bogus', home=self.home)
        self.assertEqual(r.returncode, 2, r.stderr); self.no_traceback(r)
        self.assertIn('bogus', r.stderr); self.assertIn('ndk, dotnet, adb', r.stderr)

    def test_inspect_empty(self):
        r = porter('inspect', self.dir, '--json', home=self.home)
        self.assertEqual(r.returncode, 2, r.stderr); self.no_traceback(r)
        self.assertIn('error', json.loads(r.stdout))

    def test_inspect_nsz_only(self):
        (self.dir / 'game.nsz').write_bytes(b'')
        r = porter('inspect', self.dir, '--json', home=self.home)
        self.assertEqual(r.returncode, 2, r.stderr); self.no_traceback(r)
        self.assertIn('NSZ', json.loads(r.stdout)['error'])

    def test_port_without_keys(self):
        r = porter('port', self.dir, '--progress', 'json', home=self.home)
        self.assertEqual(r.returncode, 1, r.stderr); self.no_traceback(r)
        self.assertIn('prod.keys', self.error_event(r))

    def test_install_not_a_pack(self):
        r = porter('install', self.dir, '--progress', 'json', home=self.home)
        self.assertEqual(r.returncode, 1, r.stderr); self.no_traceback(r)
        self.assertTrue(self.error_event(r).startswith('not a data pack'), r.stdout)

    def test_config_unknown_key(self):
        r = porter('config', 'nope', 'x', home=self.home)
        self.assertEqual(r.returncode, 1, r.stderr); self.no_traceback(r)
        self.assertIn('nope', r.stderr)


class Languages(unittest.TestCase):   # D-12: inspect's languages are upstream's nacp.LANGUAGES, narrowed by the control.nacp of an extraction a port made
    TID = '0100000000AAA000'

    def setUp(self): self.dir = Path(tempfile.mkdtemp())

    def languages(self, pack='v0'):   # cmd_inspect in process, pipeline.inspect stood in for (no game files)
        from unittest import mock
        from porter import cli
        out = io.StringIO()
        with mock.patch('porter.pipeline.inspect', return_value={'title_id': self.TID, 'pack': pack, 'supported': True}), contextlib.redirect_stdout(out):
            self.assertEqual(cli.cmd_inspect(Namespace(folder=str(self.dir), json=True)), 0)
        return json.loads(out.getvalue())['languages']

    def nacp(self, flags, version='v0'):
        b = bytearray(0x4000); struct.pack_into('<I', b, 0x302C, flags)
        d = self.dir / f'{self.TID}_build/extract/{version}'; d.mkdir(parents=True); (d / 'control.nacp').write_bytes(b)

    def full(self):
        from porter.upstream import nacp
        return [{'code': c, 'name': n} for c, n in nacp.LANGUAGES]

    def test_from_extraction(self):
        self.nacp(1 << 2 | 1 << 3)
        self.assertEqual(self.languages(), [{'code': 'ja', 'name': 'Japanese'}, {'code': 'fr', 'name': 'French'}])

    def test_packed_version_first(self):
        self.nacp(1 << 2); self.nacp(1 << 3, 'v65536')
        self.assertEqual([x['code'] for x in self.languages('v65536')], ['fr'])

    def test_no_extraction_full_list(self):
        got = self.languages()
        self.assertEqual(len(got), 16); self.assertEqual(got, self.full())
        self.assertEqual(len({x['code'] for x in got}), 16)

    def test_no_flags_full_list(self):
        self.nacp(0)
        self.assertEqual(self.languages(), self.full())


class DeviceTool(unittest.TestCase):
    def test_env_wins(self):   # over any local devtools/device.json
        r = subprocess.run([sys.executable, 'devtools/device.py', '--sh'], cwd=REPO, capture_output=True, text=True, encoding='utf-8', timeout=120,
                           env=_env(tempfile.mkdtemp(), {'NX2A_DEVICE': 'serial-1', 'NX2A_PACKAGE': 'org.example.app'}))
        self.assertEqual(r.returncode, 0, r.stderr)
        for want in ("SERIAL='serial-1'", "PKG='org.example.app'", "F='/sdcard/Android/data/org.example.app/files'"): self.assertIn(want, r.stdout)


if __name__ == '__main__': unittest.main()
