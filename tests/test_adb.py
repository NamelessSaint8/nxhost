# porter/adb.py and porter/install.py with subprocess.run answered from a table: no device, no fake executable, so it runs the same on Windows.
# Pinned: remote_sizes parsing, push_file resume and its size check, push_tree skips and MD5 re-pushes, stale-file removal limited to the pack's own folders, --replace-signer.
import hashlib, os, shlex, subprocess, sys, tempfile, types, unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
os.environ['NX2A_HOME'] = tempfile.mkdtemp()   # before porter is imported: no test touches the developer's settings or signing key

MISSING = None
for _m in ('lz4.block', 'capstone'):   # porter.install imports porter.upstream
    try: __import__(_m)
    except ModuleNotFoundError:
        if os.environ.get('CI'): raise   # CI installs the lock: a missing module there is a failure
        MISSING = MISSING or _m


def setUpModule():   # not a module-level SkipTest: `python -m unittest tests.test_adb` crashes on one
    if MISSING: raise unittest.SkipTest(f'{MISSING} is not installed (python -m pip install -r requirements.txt)')


from porter import adb   # noqa: E402


def fake(table, calls):
    """A stand-in for subprocess.run: records argv[1:] in calls and answers with the first table value whose key is in the joined argv
    (a string for stdout, or (returncode, stdout, stderr)); anything else succeeds with no output"""
    def run(argv, **kw):
        calls.append([str(x) for x in argv[1:]]); joined = ' '.join(map(str, argv))
        v = next((v for k, v in table.items() if k in joined), '')
        rc, out, err = v if isinstance(v, tuple) else (0, v, '')
        return subprocess.CompletedProcess(argv, rc, out, err)
    return run


def shells(calls): return [c[c.index('shell') + 1] for c in calls if 'shell' in c]


def pushes(calls): return [c[c.index('push'):] for c in calls if 'push' in c]


def tree(root, files):   # {relative path: bytes} → root
    for rel, b in files.items(): p = Path(root) / rel; p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(b)
    return Path(root)


class Sizes(unittest.TestCase):
    def test_remote_sizes(self):
        calls = []
        with mock.patch.object(adb.subprocess, 'run', fake({'find . -type f': '12 ./mods/main\n5 ./RomFS/a b.bin\nx junk\n\n'}, calls)):
            self.assertEqual(adb.Adb('adb', log=lambda m: None).remote_sizes('/sdcard/x'), {'mods/main': 12, 'RomFS/a b.bin': 5})


class Push(unittest.TestCase):
    def push(self, final):
        f = Path(tempfile.mkdtemp()) / 'big.bin'; f.write_bytes(b'0123456789'); calls = []
        table = {'find . -type f': '4 ./00000\n', 'stat -c %s': final}
        with mock.patch.object(adb.subprocess, 'run', fake(table, calls)): adb.Adb('adb', log=lambda m: None).push_file(f, '/sdcard/x/big.bin', chunk=4)
        return calls

    def test_resume_skips_pieces_at_size(self):
        calls = self.push('10\n')
        self.assertEqual([p[-1].rsplit('/', 1)[1] for p in pushes(calls)], ['00001', '00002'])
        self.assertEqual(len([s for s in shells(calls) if 'for x in $(ls' in s]), 1)

    def test_size_mismatch_raises(self):
        with self.assertRaises(adb.AdbError) as e: self.push('9\n')
        for want in ('big.bin', '9', '10'): self.assertIn(want, str(e.exception))

    def test_push_tree_skips_and_md5(self):
        local = tree(tempfile.mkdtemp(), {'a.bin': b'aaaaa', 'mods/m': b'mmmmmm', 'mods/same': b'ssssss', 'settings.txt': b'mine', 'new.bin': b'n'})
        same = hashlib.md5(b'ssssss').hexdigest()
        table = {'find . -type f': '5 ./a.bin\n6 ./mods/m\n6 ./mods/same\n99 ./settings.txt\n', 'md5sum': f'{"0" * 32}  mods/m\n{same}  mods/same\n'}
        calls = []
        with mock.patch.object(adb.subprocess, 'run', fake(table, calls)):
            adb.Adb('adb', log=lambda m: None).push_tree(local, '/sdcard/x', keep=('settings.txt',), verify=lambda rel: rel.startswith('mods/'))
        self.assertEqual(sorted(Path(x).name for p in pushes(calls) for x in p[2:-1]), ['m', 'new.bin'])


class Install(unittest.TestCase):
    def setUp(self):
        from porter import install
        for name, v in (('PROG', mock.Mock()), ('say', lambda m: None)):
            p = mock.patch.object(install, name, v); p.start(); self.addCleanup(p.stop)

    def test_stale_removed_in_batches(self):
        from porter import datapack, install
        src = Path(tempfile.mkdtemp())
        shaders = src / 'shaders.dmsv'; shaders.write_bytes(b'sh')
        prof = types.SimpleNamespace(package='org.example.test', name='Test', id='0100000000AAA000', env=[], settings={}, requires=[])
        data = src / 'Test-data'
        datapack.build(data, profile=prof, version='v0', display='1.0', patched=tree(src / 'mods', {'main': b'm'}), romfs=tree(src / 'romfs', {'a.bin': b'a'}), shaders=shaders)
        apk = src / 'Test.apk'; apk.write_bytes(b'apk')
        stale = [f'mods/old/f{i:03d}.bin' for i in range(130)]
        listing = ''.join(f'1 ./{r}\n' for r in stale + ['settings.txt', 'logs/x.txt'])
        table = {'devices -l': 'List of devices attached\nserial-1 device model:Test\n', 'getprop': 'Test\n', 'dumpsys': 'GLES: Qualcomm, Adreno (TM) 830\n',
                 'df -k': '/dev/fuse 100000000 0 90000000 0% /sdcard\n', 'find . -type f': listing, '[ -d': 'yes\n',
                 'stat -c %s': f'{(data / datapack.MANIFEST).stat().st_size}\n'}
        calls = []
        with mock.patch.object(adb.subprocess, 'run', fake(table, calls)): install.install(apk, data, 'adb')
        rms = [s for s in shells(calls) if s.startswith('cd ') and ' && rm -f ' in s]
        gone = [shlex.split(s.partition(' && rm -f ')[2]) for s in rms]
        self.assertEqual([len(g) for g in gone], [64, 64, 2])
        self.assertEqual(sorted(r for g in gone for r in g), stale)
        for s in rms: self.assertNotIn('settings.txt', s); self.assertNotIn('logs/', s)

    def test_replace_signer(self):
        table = {'install -r': (1, '', 'Failure [INSTALL_FAILED_UPDATE_INCOMPATIBLE: signatures do not match]'), 'uninstall': '', 'install': ''}
        calls = []
        with mock.patch.object(adb.subprocess, 'run', fake(table, calls)): adb.Adb('adb', log=lambda m: None).install('a.apk', 'org.example.test', replace_signer=True)
        self.assertEqual(calls, [['install', '-r', 'a.apk'], ['uninstall', 'org.example.test'], ['install', 'a.apk']])
        calls.clear()
        with mock.patch.object(adb.subprocess, 'run', fake(table, calls)), self.assertRaises(adb.AdbError) as e:
            adb.Adb('adb', log=lambda m: None).install('a.apk', 'org.example.test')
        self.assertIn('--replace-signer', str(e.exception)); self.assertEqual(calls, [['install', '-r', 'a.apk']])


if __name__ == '__main__': unittest.main()
