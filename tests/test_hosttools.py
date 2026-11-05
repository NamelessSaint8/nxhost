# porter/hosttools.py and porter/childenv.py: the known places a bare PATH hides (D-16) and their place in the lookup order (D-13), a bare-PATH `porter doctor`,
# the env every dotnet child gets (D-18, HARD-06), adb's version as numbers (D-12) and where a found tool came from. Standard library only.
import json, os, subprocess, sys, tempfile, types, unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
os.environ['NX2A_HOME'] = tempfile.mkdtemp()

from porter import childenv, hosttools, paths, toolchain   # noqa: E402


def exe(p, text=''):   # an "executable": the finders only check that the file is there
    p = Path(p); p.parent.mkdir(parents=True, exist_ok=True); p.write_text(text); p.chmod(0o755); return p


def host(name, platform):   # os and sys as another OS shows them to porter, without changing what pathlib builds here
    return types.SimpleNamespace(name=name, environ=os.environ, path=os.path), types.SimpleNamespace(platform=platform)


class Known(unittest.TestCase):   # the machine's own toolchains out of reach, as tests/test_toolchain.py's Detection does
    def setUp(self):
        self.t = Path(tempfile.mkdtemp())
        env = mock.patch.dict(os.environ); env.start(); self.addCleanup(env.stop)
        for k in ('ANDROID_NDK_HOME', 'ANDROID_NDK_ROOT', 'ANDROID_HOME', 'ANDROID_SDK_ROOT', 'DOTNET_ROOT', 'ProgramFiles', 'ProgramW6432'): os.environ.pop(k, None)
        for k in ('HOME', 'USERPROFILE', 'LOCALAPPDATA'): os.environ[k] = str(self.t / 'home')
        self.player = self.t / 'player'
        for name, v in (('LOCAL_TOOLS', self.t / 'local'), ('player_tools', lambda: self.player)):
            p = mock.patch.object(toolchain, name, v); p.start(); self.addCleanup(p.stop)

    def known(self, *paths): return mock.patch.object(hosttools, 'known', lambda name: [str(p) for p in paths])

    def test_per_os(self):
        home = str(Path.home() / '.dotnet')
        cases = (('posix', 'darwin', ['/opt/homebrew/bin', '/usr/local/bin', home, '/usr/local/share/dotnet']),
                 ('posix', 'linux', ['/usr/bin', '/usr/local/bin', '/snap/bin', home, '/usr/lib/dotnet', '/usr/lib64/dotnet', '/usr/share/dotnet']), ('nt', 'win32', []))
        for name, platform, dirs in cases:
            o, s = host(name, platform)
            with self.subTest(platform), mock.patch.object(hosttools, 'os', o), mock.patch.object(hosttools, 'sys', s):
                self.assertEqual(hosttools.known('adb'), [f'{d}/adb' for d in dirs])

    def test_adb_order(self):
        a = f'adb{toolchain.EXE}'
        cfg, path, stub, sdk = exe(self.t / 'cfg' / a), exe(self.t / 'path' / a), exe(self.t / 'known' / a), exe(self.t / 'sdk' / 'platform-tools' / a)
        os.environ['ANDROID_HOME'] = str(self.t / 'sdk')
        with self.known(stub):
            with mock.patch.object(toolchain.shutil, 'which', return_value=None): self.assertEqual(toolchain.find_adb({}), stub)   # before the Android SDK's
            with mock.patch.object(toolchain.shutil, 'which', return_value=str(path)):
                self.assertEqual(toolchain.find_adb({}), path)   # PATH before the known places
                self.assertEqual(toolchain.find_adb({'adb': str(cfg)}), cfg)   # the configured one before both

    def test_dotnet_from_known_place(self):
        stub = exe(self.t / 'known' / f'dotnet{toolchain.EXE}')
        with self.known(stub), mock.patch.object(toolchain.shutil, 'which', return_value=None), mock.patch.object(toolchain, 'dotnet_sdks', lambda d: ['10.0.403']):
            self.assertEqual(toolchain.find_dotnet({}), stub)

    @unittest.skipIf(os.name == 'nt', 'symlinks')
    def test_listed_once(self):   # one file through PATH, a known place and a link to it (Homebrew's /opt/homebrew/bin/dotnet): asked once, the earliest spelling kept
        real = exe(self.t / 'real' / 'dotnet'); link = self.t / 'link' / 'dotnet'; link.parent.mkdir(); link.symlink_to(real)
        asked = []
        with self.known(real, link), mock.patch.object(toolchain.shutil, 'which', return_value=str(real)), mock.patch.object(toolchain, 'dotnet_sdks', lambda d: asked.append(d) or []):
            self.assertEqual(toolchain.find_dotnet({}), real)
        self.assertEqual([a for a in asked if a.resolve() == real.resolve()], [real])   # the machine's own /usr/local/share/dotnet may be asked too


@unittest.skipIf(os.name == 'nt', 'an Explorer launch keeps the user\'s PATH; the stubs are /bin/sh scripts')
class BarePath(unittest.TestCase):   # a Finder or desktop-menu launch: PATH=/usr/bin:/bin and nothing else of the user's shell
    def test_doctor_finds_tools(self):
        t = Path(tempfile.mkdtemp()); home = t / 'home'
        exe(home / '.dotnet' / 'dotnet', f'#!/bin/sh\necho "10.0.403 [{home}/.dotnet/sdk]"\n')
        exe(home / ('Library/Android/sdk' if sys.platform == 'darwin' else 'Android/Sdk') / 'platform-tools' / 'adb', '#!/bin/sh\n')
        env = {'PATH': '/usr/bin:/bin', 'HOME': str(home), 'NX2A_HOME': str(t / 'nx2a'), 'PYTHONPATH': str(REPO)}
        r = subprocess.run([sys.executable, '-m', 'porter', 'doctor', '--json'], cwd=REPO, env=env, capture_output=True, text=True, encoding='utf-8', timeout=120)
        rows = {c['name']: c for c in json.loads(r.stdout)}
        for name in ('.NET SDK', 'adb'):
            with self.subTest(name): self.assertTrue(rows[name]['path'], rows[name])


def listed(out='', err=None):   # subprocess.run as `dotnet --list-sdks` answers, or raising err
    def run(*a, **k):
        if err: raise err
        return subprocess.CompletedProcess(a[0], 0, out, '')
    return mock.patch.object(hosttools.subprocess, 'run', run)


class ChildEnv(unittest.TestCase):   # D-18: the real DOTNET_ROOT, invariant globalization and a UTF-8 LANG; HARD-06: os.environ is never written
    def test_root_from_list_sdks(self):   # Homebrew's /opt/homebrew/bin/dotnet is a link: the SDK list names the real root
        with listed('9.0.100 [/opt/x/dotnet/sdk]\n10.0.403 [/opt/x/dotnet/sdk]\n'): self.assertEqual(hosttools.dotnet_root('/opt/homebrew/bin/dotnet'), Path('/opt/x/dotnet'))

    def test_root_fallback(self):
        t = Path(tempfile.mkdtemp()); p = exe(t / 'real' / 'dotnet')
        for err in (OSError('no such file'), subprocess.TimeoutExpired('dotnet', 60)):
            with self.subTest(err=type(err).__name__), listed(err=err): self.assertEqual(hosttools.dotnet_root(p), p.resolve().parent)
        with listed('garbage'): self.assertEqual(hosttools.dotnet_root(p), p.resolve().parent)

    def test_vars(self):
        with listed('10.0.403 [/opt/x/dotnet/sdk]'): e = childenv.dotnet('/opt/homebrew/bin/dotnet', 4, base={'PATH': '/usr/bin'})
        want = dict(DOTNET_ROOT=str(Path('/opt/x/dotnet')), J='4', PYTHONIOENCODING='utf-8', PYTHONUTF8='1', DOTNET_CLI_TELEMETRY_OPTOUT='1',
                    NUGET_PACKAGES=str(paths.user_dir() / 'nuget'), DOTNET_SYSTEM_GLOBALIZATION_INVARIANT='1', LANG='C.UTF-8')
        self.assertEqual({k: e.get(k) for k in want}, want)
        self.assertEqual(e['PATH'], os.pathsep.join([str(Path('/opt/x/dotnet')), '/usr/bin']))   # upstream's build_nx_extract finds dotnet through this PATH

    def test_keeps_lang(self):
        with listed('10.0.403 [/opt/x/dotnet/sdk]'): self.assertEqual(childenv.dotnet('/x/dotnet', 1, base={'LANG': 'de_DE.UTF-8'})['LANG'], 'de_DE.UTF-8')

    def test_no_environ_write(self):
        before = dict(os.environ)
        with listed('10.0.403 [/opt/x/dotnet/sdk]'): e = childenv.dotnet('/x/dotnet', 2)
        self.assertEqual(dict(os.environ), before); self.assertEqual(e['DOTNET_SYSTEM_GLOBALIZATION_INVARIANT'], '1')

    def test_linux_arm64_dotnet_places(self):   # TOOL-02: a distro or user .NET 10 on Linux arm64
        o, s = host('posix', 'linux')
        with mock.patch.object(hosttools, 'os', o), mock.patch.object(hosttools, 'sys', s):
            k = hosttools.known('dotnet')
        for p in ('/usr/lib/dotnet/dotnet', '/usr/share/dotnet/dotnet', f'{Path.home() / ".dotnet"}/dotnet'): self.assertIn(p, k)   # known() joins with '/'


class AdbVersion(unittest.TestCase):   # D-12: `adb version` as numbers; an unread version keeps -Z (today's behaviour)
    def test_parse(self):
        cases = (('Android Debug Bridge version 1.0.41\nVersion 36.0.0-13206524\nInstalled as /x/adb\n', '36.0.0-13206524', 36, 41),
                 ('Android Debug Bridge version 1.0.41\nVersion 29.0.6-debian\n', '29.0.6-debian', 29, 41),   # Debian 12, Ubuntu 22.04
                 ('Android Debug Bridge version 1.0.41\nVersion 1:10.0.0+r36-7\n', '1:10.0.0+r36-7', 10, 41),   # a Debian epoch
                 ('', None, None, None), ('garbage', None, None, None))
        for out, version, major, protocol in cases:
            with self.subTest(out), listed(out): self.assertEqual(hosttools.adb_version('adb'), {'version': version, 'major': major, 'protocol': protocol})
        for err in (OSError('gone'), subprocess.TimeoutExpired('adb', 15)):
            with self.subTest(err=type(err).__name__), listed(err=err): self.assertIsNone(hosttools.adb_version('adb'))

    def test_push_flags(self):
        for v, want in (({'major': 29}, []), ({'major': 36}, ['-Z']), ({'major': None}, ['-Z']), (None, ['-Z'])):
            with self.subTest(v=v), mock.patch.object(hosttools, 'adb_version', return_value=v): self.assertEqual(hosttools.push_flags('adb'), want)

    def test_numeric(self):   # as strings '9' > '30'
        with listed('Version 9.0.0-1\n'): self.assertEqual(hosttools.adb_version('adb')['major'], 9)
        with listed('Version 9.0.0-1\n'): self.assertEqual(hosttools.push_flags('adb'), [])


class Source(unittest.TestCase):   # D-13: where a found tool came from
    def setUp(self):
        self.t = Path(tempfile.mkdtemp())
        env = mock.patch.dict(os.environ); env.start(); self.addCleanup(env.stop)
        for k in ('DOTNET_ROOT', 'ANDROID_NDK_HOME', 'ANDROID_NDK_ROOT'): os.environ.pop(k, None)
        for p in (mock.patch.object(hosttools, 'player_tools', lambda: self.t / 'player'), mock.patch.object(hosttools, 'LOCAL_TOOLS', self.t / 'local'),
                  mock.patch.object(hosttools.shutil, 'which', lambda n: str(self.t / 'path' / n)), mock.patch.object(hosttools, 'known', lambda n: [str(self.t / 'known' / n)])):
            p.start(); self.addCleanup(p.stop)

    def test_labels(self):
        t = self.t; mine = t / 'player' / 'platform-tools' / 'adb'
        self.assertEqual(hosttools.source_of(mine, {}, 'adb'), 'downloaded')
        self.assertEqual(hosttools.source_of(mine, {'adb': str(mine)}, 'adb'), 'downloaded')   # a downloaded tool the settings point at (RESEARCH Open Question 3)
        self.assertEqual(hosttools.source_of(t / 'cfg' / 'adb', {'adb': str(t / 'cfg' / 'adb')}, 'adb'), 'configured')
        for k in ('DOTNET_ROOT', 'ANDROID_NDK_HOME', 'ANDROID_NDK_ROOT'):
            with self.subTest(k), mock.patch.dict(os.environ, {k: str(t / 'env')}): self.assertEqual(hosttools.source_of(t / 'env' / 'dotnet', {}, 'dotnet'), 'env')
        self.assertEqual(hosttools.source_of(t / 'path' / 'adb', {}, 'adb'), 'PATH')
        self.assertEqual(hosttools.source_of(t / 'known' / 'adb', {}, 'adb'), 'known place')
        self.assertEqual(hosttools.source_of(t / 'sdk' / 'platform-tools' / 'adb', {}, 'adb', sdk_roots=[t / 'sdk']), 'Android SDK')
        self.assertEqual(hosttools.source_of(t / 'local' / 'platform-tools' / 'adb', {}, 'adb'), 'known place')

    def test_linux_arm64(self):
        for platform, machine, want in (('linux', 'aarch64', True), ('linux', 'arm64', True), ('linux', 'x86_64', False), ('darwin', 'arm64', False)):
            with self.subTest(platform=platform, machine=machine), mock.patch.object(hosttools, 'sys', types.SimpleNamespace(platform=platform)), \
                 mock.patch.object(hosttools.platform, 'machine', return_value=machine):
                self.assertEqual(hosttools.linux_arm64(), want)


if __name__ == '__main__': unittest.main()
