# porter/hosttools.py and porter/childenv.py: the known places a bare PATH hides (D-16) and their place in the lookup order (D-13), a bare-PATH `porter doctor`,
# the env every dotnet child gets (D-18, HARD-06), adb's version as numbers (D-12) and where a found tool came from. Standard library only.
import json, os, subprocess, sys, tempfile, types, unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
os.environ['NX2A_HOME'] = tempfile.mkdtemp()

from porter import hosttools, toolchain   # noqa: E402


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


if __name__ == '__main__': unittest.main()
