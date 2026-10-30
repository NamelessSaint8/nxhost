# porter/toolchain.py: toolchain detection and the Python floor (D-13: the CVE-2025-4517 tarfile fix, by version or by its os.path.ALLOW_MISSING marker),
# and porter/runlog.py's refusal of every command but doctor on a Python without it. Standard library only, so it runs without the engine modules.
import argparse, contextlib, io, json, os, sys, tempfile, types, unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
os.environ['NX2A_HOME'] = tempfile.mkdtemp()

from porter import runlog, toolchain   # noqa: E402


def call(ns):   # runlog.run on a Namespace with python_ok() False: (exit code, stdout, the command's fn)
    fn = mock.Mock(return_value=0); out = io.StringIO()
    with mock.patch.object(toolchain, 'python_ok', return_value=False, create=True), contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()): code = runlog.run(ns, fn)
    return code, out.getvalue(), fn


class PythonFloor(unittest.TestCase):
    def setUp(self):
        keep = dict(os.environ); self.addCleanup(lambda: (os.environ.clear(), os.environ.update(keep)))
        os.environ.pop('NX2A_GUI', None); os.environ['NX2A_HOME'] = tempfile.mkdtemp()

    def test_floors(self):
        for v in ((3, 10, 99), (3, 11, 12), (3, 12, 10), (3, 13, 3)):
            with self.subTest(v=v): self.assertFalse(toolchain.python_ok(v, marker=False))
        for v in ((3, 11, 13), (3, 12, 11), (3, 13, 4), (3, 14, 0), (3, 15, 0)):
            with self.subTest(v=v): self.assertTrue(toolchain.python_ok(v, marker=False))
        self.assertTrue(toolchain.python_ok((3, 12, 3), marker=True)); self.assertFalse(toolchain.python_ok((3, 12, 3), marker=False))
        self.assertFalse(toolchain.python_ok((3, 10, 99), marker=True))

    def test_doctor_row(self):
        with mock.patch.object(toolchain, 'python_ok', return_value=False, create=True): row = next(r for r in toolchain.checks() if r.name == 'Python')
        self.assertFalse(row.ok)
        for v in ('3.11.13', '3.12.11', '3.13.4'): self.assertIn(v, row.fix)

    def test_refusal_one_shot(self):
        code, out, fn = call(argparse.Namespace(cmd='inspect', json=True))
        self.assertEqual(code, 1); fn.assert_not_called()
        self.assertIn('CVE-2025-4517', json.loads(out)['error'])

    def test_refusal_long(self):
        code, out, fn = call(argparse.Namespace(cmd='port', progress='json', json=False, install=False))
        self.assertEqual(code, 1); fn.assert_not_called()
        evs = [json.loads(ln) for ln in out.splitlines() if ln.startswith('{')]
        self.assertEqual(evs[0]['ev'], 'log')
        err = [e for e in evs if e['ev'] == 'error']
        self.assertEqual([e['type'] for e in err], ['PythonError']); self.assertIn('CVE-2025-4517', err[0]['msg'])
        self.assertIn('[RED] ', Path(evs[0]['path']).read_text(encoding='utf-8'))

    def test_doctor_still_runs(self):
        code, _, fn = call(argparse.Namespace(cmd='doctor', json=True))
        fn.assert_called_once(); self.assertEqual(code, 0)


def ndk(d, rev):   # a folder that reads as an NDK of that revision
    d = Path(d); d.mkdir(parents=True, exist_ok=True); (d / 'source.properties').write_text(f'Pkg.Desc = Android NDK\nPkg.Revision = {rev}\n'); return d


def exe(p):   # an empty "executable": the finders only check that the file is there
    p = Path(p); p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(b''); p.chmod(0o755); return p


def host(name, platform):   # os and sys as another OS shows them to porter, without changing what pathlib builds here
    return types.SimpleNamespace(name=name, environ=os.environ, path=os.path), types.SimpleNamespace(platform=platform)


class Detection(unittest.TestCase):   # the finders' order and the per-OS folders, with the machine's own toolchains out of reach
    def setUp(self):
        self.t = Path(tempfile.mkdtemp())
        env = mock.patch.dict(os.environ); env.start(); self.addCleanup(env.stop)
        for k in ('ANDROID_NDK_HOME', 'ANDROID_NDK_ROOT', 'ANDROID_HOME', 'ANDROID_SDK_ROOT', 'DOTNET_ROOT', 'ProgramFiles', 'ProgramW6432', 'XDG_CONFIG_HOME', 'APPDATA'): os.environ.pop(k, None)
        for k in ('HOME', 'USERPROFILE', 'LOCALAPPDATA'): os.environ[k] = str(self.t / 'home')
        self.player = self.t / 'player'
        for name, v in (('LOCAL_TOOLS', self.t / 'local'), ('player_tools', lambda: self.player)):
            p = mock.patch.object(toolchain, name, v); p.start(); self.addCleanup(p.stop)

    def test_ndk_config_wins(self):
        os.environ['ANDROID_NDK_HOME'] = str(ndk(self.t / 'r27c', toolchain.NDK_REVISION))
        d26 = ndk(self.t / 'r26', '26.1.10909125')
        self.assertEqual(toolchain.find_ndk({'ndk': str(d26)}), (d26, '26.1.10909125'))

    def test_ndk_env_then_found(self):
        os.environ['ANDROID_NDK_HOME'] = str(ndk(self.t / 'env', '26.1.10909125'))
        self.assertEqual(toolchain.find_ndk({}), (self.t / 'env', '26.1.10909125'))
        del os.environ['ANDROID_NDK_HOME']
        self.assertEqual(toolchain.find_ndk({}), (None, None))
        ndk(self.player / 'android-ndk-r26d', '26.3.11579264'); r27 = ndk(self.player / 'android-ndk-r27c', toolchain.NDK_REVISION)
        os.environ['ANDROID_HOME'] = str(self.t / 'sdk'); ndk(self.t / 'sdk' / 'ndk' / '28.0.13004108', '28.0.13004108')   # the last one found: not r27c
        self.assertEqual(toolchain.find_ndk({}), (r27, toolchain.NDK_REVISION))

    def test_dotnet_prefers_sdk10(self):
        old = exe(self.t / 'root' / f'dotnet{toolchain.EXE}'); new = exe(self.player / 'dotnet' / f'dotnet{toolchain.EXE}')
        os.environ['DOTNET_ROOT'] = str(old.parent)   # found first, but only SDK 8
        sdks = {old: ['8.0.404'], new: ['9.0.100', '10.0.403']}
        with mock.patch.object(toolchain.shutil, 'which', return_value=None), mock.patch.object(toolchain, 'dotnet_sdks', lambda d: sdks.get(Path(d), [])):
            self.assertEqual(toolchain.find_dotnet({}), new)
            self.assertEqual(toolchain.find_dotnet({'dotnet': str(old)}), old)

    def test_adb_order(self):
        a = f'adb{toolchain.EXE}'
        cfg, path, sdk, mine = exe(self.t / 'cfg' / a), exe(self.t / 'path' / a), exe(self.t / 'sdk' / 'platform-tools' / a), exe(self.player / 'platform-tools' / a)
        os.environ['ANDROID_HOME'] = str(self.t / 'sdk')
        with mock.patch.object(toolchain.shutil, 'which', return_value=str(path)):
            self.assertEqual(toolchain.find_adb({'adb': str(cfg)}), cfg)
            self.assertEqual(toolchain.find_adb({}), path)
        with mock.patch.object(toolchain.shutil, 'which', return_value=None):
            self.assertEqual(toolchain.find_adb({}), sdk)
            del os.environ['ANDROID_HOME']
            self.assertEqual(toolchain.find_adb({}), mine)

    def test_sdk_roots_per_os(self):
        os.environ.update(ANDROID_HOME=str(self.t / 'ah'), ANDROID_SDK_ROOT=str(self.t / 'asr'), LOCALAPPDATA=str(self.t / 'la'))
        for name, platform, last in (('nt', 'win32', self.t / 'la' / 'Android' / 'Sdk'), ('posix', 'darwin', Path(os.path.expanduser('~/Library/Android/sdk'))),
                                     ('posix', 'linux', Path(os.path.expanduser('~/Android/Sdk')))):
            o, s = host(name, platform)
            with self.subTest(platform), mock.patch.object(toolchain, 'os', o), mock.patch.object(toolchain, 'sys', s):
                self.assertEqual(toolchain._sdk_roots(), [self.t / 'ah', self.t / 'asr', last])

    def test_user_dir_per_os(self):
        from porter import paths
        os.environ.pop('NX2A_HOME', None)   # the module's own is back after the test (setUp's patch.dict)
        home = self.t / 'h'; os.environ['APPDATA'] = str(self.t / 'appdata')
        cases = (('nt', 'win32', {}, self.t / 'appdata' / 'nx2android'), ('posix', 'darwin', {}, home / 'Library' / 'Application Support' / 'nx2android'),
                 ('posix', 'linux', {'XDG_CONFIG_HOME': str(self.t / 'xdg')}, self.t / 'xdg' / 'nx2android'), ('posix', 'linux', {}, home / '.config' / 'nx2android'))
        for name, platform, extra, want in cases:
            o, s = host(name, platform)
            with self.subTest(platform, **extra), mock.patch.dict(os.environ, extra), mock.patch.object(paths, 'os', o), mock.patch.object(paths, 'sys', s), \
                 mock.patch.object(paths.Path, 'home', return_value=home):
                self.assertEqual(paths.user_dir(), want); self.assertTrue(want.is_dir())


if __name__ == '__main__': unittest.main()
