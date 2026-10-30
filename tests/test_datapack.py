# The data pack's swap (porter/datapack.py, HARD-07): the old pack is renamed aside before the new one goes in, and a crash between the two is put back by
# the next build or install; the pushed pack names no host path (D-14); install hashes modules in pieces (porter/adb.py). Own NX2A_HOME; no device or toolchains.
import hashlib, json, os, shutil, subprocess, sys, tempfile, unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
os.environ['NX2A_HOME'] = tempfile.mkdtemp(prefix='nx2a_test_home_')

MISSING = None
for _m in ('lz4.block', 'capstone'):
    try: __import__(_m)
    except ModuleNotFoundError:
        if os.environ.get('CI'): raise   # CI installs the lock: a missing module there is a failure
        MISSING = MISSING or _m


def setUpModule():   # not a module-level SkipTest: `python -m unittest tests.test_datapack` crashes on one
    if MISSING: raise unittest.SkipTest(f'{MISSING} is not installed (python -m pip install -r requirements.txt)')


NEO = '010043B013C5C000'


def porter(*args, home, env=None, **kw):
    e = dict(os.environ, NX2A_HOME=str(home), PYTHONIOENCODING='utf-8'); e.pop('NX2A_GUI', None); e.update(env or {})
    return subprocess.run([sys.executable, '-m', 'porter', *map(str, args)], cwd=REPO, env=e, capture_output=True, text=True, encoding='utf-8', timeout=120, **kw)


def events(out): return [json.loads(ln) for ln in out.splitlines() if ln.startswith('{')]


class Swap(unittest.TestCase):
    def setUp(self):
        self.t = Path(tempfile.mkdtemp(prefix='nx2a_test_swap_')); self.addCleanup(shutil.rmtree, self.t, True)
        self.dst = self.t / 'out' / 'X-data'; self.dst.parent.mkdir()

    def build(self, content=b'x' * 10, **kw):   # a small pack: one module, a RomFS file, one DLC, the shaders
        from porter import datapack, profiles
        src = self.t / 'src'; shutil.rmtree(src, ignore_errors=True)
        (src / 'patched').mkdir(parents=True); (src / 'patched/main.patched.bin').write_bytes(content)
        (src / 'romfs/Data').mkdir(parents=True); (src / 'romfs/Data/a.bin').write_bytes(b'y' * 20)
        (src / 'aoc/1').mkdir(parents=True); (src / 'aoc/1/d.bin').write_bytes(b'z')
        (src / 'shaders.dmsv').write_bytes(b'DMSV')
        return datapack.build(self.dst, profile=profiles.load(NEO), version='v196608', display='1.03', patched=src / 'patched', romfs=src / 'romfs',
                              shaders=src / 'shaders.dmsv', aoc=src / 'aoc', **kw)

    def sibling(self, suffix): return self.dst.with_name(self.dst.name + suffix)

    def test_rebuild_leaves_one_pack(self):
        self.build(b'first'); self.build(b'second')
        self.assertEqual((self.dst / 'mods/main.patched.bin').read_bytes(), b'second')
        self.assertFalse(self.sibling('.old').exists()); self.assertFalse(self.sibling('.partial').exists())

    def test_crash_mid_swap_keeps_old_pack(self):
        from porter import datapack
        from porter.upstream import nsp
        self.build(b'first'); made = datapack.read_manifest(self.dst)['made']
        with mock.patch.object(nsp, 'swap_in', side_effect=KeyboardInterrupt), self.assertRaises(KeyboardInterrupt): self.build(b'second')
        self.assertFalse(self.dst.exists())
        self.assertEqual(datapack.read_manifest(self.sibling('.old'))['made'], made)
        datapack.recover(self.dst)
        self.assertEqual((self.dst / 'mods/main.patched.bin').read_bytes(), b'first'); self.assertFalse(self.sibling('.old').exists())
        self.build(b'third')
        self.assertEqual((self.dst / 'mods/main.patched.bin').read_bytes(), b'third'); self.assertFalse(self.sibling('.old').exists())

    def test_install_recovers_first(self):
        self.build(); self.dst.rename(self.sibling('.old'))
        r = porter('install', self.dst, '--progress', 'json', home=Path(tempfile.mkdtemp()))
        self.assertTrue((self.dst / 'nx2a-data.json').is_file(), r.stdout + r.stderr)
        err = [e for e in events(r.stdout) if e['ev'] == 'error']
        self.assertEqual(len(err), 1, r.stdout)
        self.assertIn('no APK', err[0]['msg']); self.assertNotIn('not a data pack', err[0]['msg'])

    def test_no_host_path_in_pack(self):   # D-14: the build folder is named only beside the pack, on the host
        from porter import datapack
        work = self.t / '0100000000AAA000_build'; work.mkdir()
        self.build(build=work)
        self.assertEqual(self.sibling('.build').read_text(encoding='utf-8'), str(work.resolve()))
        self.assertEqual(datapack.build_dir(self.dst), work.resolve())
        self.assertNotIn('build', datapack.read_manifest(self.dst))
        needle = str(work.resolve()).encode('utf-8')
        for p in self.dst.rglob('*'):
            if p.is_file(): self.assertNotIn(needle, p.read_bytes(), p)

    def test_md5_in_pieces(self):
        from porter import adb
        for data in (os.urandom(3 << 20), b''):
            p = self.t / 'm.bin'; p.write_bytes(data)
            self.assertEqual(adb.md5(p), hashlib.md5(data).hexdigest())


if __name__ == '__main__':
    unittest.main()
