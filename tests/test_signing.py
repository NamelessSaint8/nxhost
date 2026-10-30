# The player's APK signing key: mkapk.py's key and APK writes, and porter's early check of the key (porter doctor's Signing key row).
# Every test uses its own temp paths and NX2A_HOME, never the developer's key (a test that wrote the real one would fork the signer of every port).
import os, re, shutil, stat, subprocess, sys, tempfile, unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
os.environ['NX2A_HOME'] = tempfile.mkdtemp(prefix='nx2a_test_home_')
MKAPK = REPO / 'nxnative/dm/android/apk/mkapk.py'
SIGNER = re.compile(r'signer SHA-256 ([0-9a-f]{16})')
POSIX = os.name != 'nt'


def mk(key, out, so=None):
    return subprocess.Popen([sys.executable, str(MKAPK), str(so or K.so), str(out), str(key)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)


def run(key, out):
    p = mk(key, out); o = p.communicate(timeout=300)[0]; return p.returncode, o


def signer(o):
    m = SIGNER.search(o); return m and m.group(1)


def setUpModule():   # one key made once (pure-Python RSA takes seconds); later tests copy it
    K.tmp = Path(tempfile.mkdtemp(prefix='nx2a_sign_'))
    K.so = K.tmp / 'libprobe.so'; K.so.write_bytes(b'\x7fELF' + bytes(60))
    K.key = K.tmp / 'base' / 'signing-key.json'; K.key.parent.mkdir()
    K.rc, K.out = run(K.key, K.tmp / 'base' / 'a.apk')


def tearDownModule(): shutil.rmtree(K.tmp, ignore_errors=True)


class K: pass   # the module's shared fake library and first key


class Key(unittest.TestCase):
    tmp = property(lambda s: K.tmp); key = property(lambda s: K.key); rc = property(lambda s: K.rc); out = property(lambda s: K.out)

    def setUp(self): self.d = Path(tempfile.mkdtemp(dir=self.tmp))

    def copy(self): k = self.d / 'signing-key.json'; shutil.copyfile(self.key, k); os.chmod(k, 0o600); return k

    def test_new_key_whole_and_private(self):
        self.assertEqual(self.rc, 0, self.out); self.assertIn('new signing key', self.out)
        if POSIX: self.assertEqual(self.key.stat().st_mode & 0o777, 0o600)
        import json; self.assertIn('cert', json.loads(self.key.read_text()))
        self.assertEqual([p.name for p in self.key.parent.iterdir() if p.name.startswith('.signing-key-')], [])
        apk = self.tmp / 'base' / 'a.apk'; self.assertTrue(apk.is_file()); self.assertFalse(Path(str(apk) + '.partial').exists())

    def test_reuse_keeps_signer(self):
        k = self.copy(); rc, o = run(k, self.d / 'b.apk')
        self.assertEqual(rc, 0, o); self.assertNotIn('new signing key', o); self.assertEqual(signer(o), signer(self.out)); self.assertIsNotNone(signer(o))

    def test_garbage_key_refused(self):
        k = self.d / 'signing-key.json'; k.write_bytes(b'{"n": '); apk = self.d / 'c.apk'
        rc, o = run(k, apk)
        self.assertNotEqual(rc, 0); self.assertIn(str(k), o); self.assertIn('Restore it from a backup', o); self.assertIn('--replace-signer', o)
        self.assertEqual(k.read_bytes(), b'{"n": '); self.assertFalse(apk.exists())

    @unittest.skipIf(not POSIX or (hasattr(os, 'geteuid') and os.geteuid() == 0), 'POSIX mode bits; root reads any file')
    def test_unreadable_key_refused(self):
        k = self.copy(); os.chmod(k, 0); apk = self.d / 'd.apk'
        try:
            rc, o = run(k, apk)
            self.assertNotEqual(rc, 0); self.assertIn(str(k), o); self.assertIn('--replace-signer', o)
            self.assertEqual(k.stat().st_mode & 0o777, 0); self.assertFalse(apk.exists())
        finally: os.chmod(k, 0o600)

    @unittest.skipIf(not POSIX, 'POSIX mode bits')
    def test_world_readable_tightened(self):
        k = self.copy(); os.chmod(k, 0o644); rc, o = run(k, self.d / 'e.apk')
        self.assertEqual(rc, 0, o); self.assertEqual(k.stat().st_mode & 0o777, 0o600)

    def test_two_first_ports_one_signer(self):
        k = self.d / 'signing-key.json'; ps = [mk(k, self.d / f'{i}.apk') for i in range(2)]
        outs = [p.communicate(timeout=300)[0] for p in ps]
        for p, o in zip(ps, outs): self.assertEqual(p.returncode, 0, o)
        self.assertIsNotNone(signer(outs[0])); self.assertEqual(signer(outs[0]), signer(outs[1]), outs)


class Preflight(unittest.TestCase):   # porter doctor's Signing key row: a broken key stops a port before its first stage
    def setUp(self):
        self.old = os.environ.get('NX2A_HOME'); os.environ['NX2A_HOME'] = tempfile.mkdtemp(prefix='nx2a_test_home_')
        from porter import paths, toolchain; self.paths, self.toolchain = paths, toolchain

    def tearDown(self):
        shutil.rmtree(os.environ['NX2A_HOME'], ignore_errors=True)
        if self.old is None: os.environ.pop('NX2A_HOME', None)
        else: os.environ['NX2A_HOME'] = self.old

    def row(self): by = {r.name: r for r in self.toolchain.checks()}; self.assertIn('Signing key', by); return by['Signing key']

    def broken(self): k = self.paths.signing_key(); k.parent.mkdir(parents=True, exist_ok=True); k.write_bytes(b'{"n": '); return k

    def test_no_key_is_fine(self):
        r = self.row(); self.assertTrue(r.ok); self.assertIn('made on the first port', r.detail)

    def test_valid_key_is_fine(self):
        k = self.paths.signing_key(); k.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(K.key, k)
        r = self.row(); self.assertTrue(r.ok, r.detail)

    def test_broken_key_is_red(self):
        k = self.broken(); r = self.row()
        self.assertFalse(r.ok); self.assertTrue(r.required); self.assertIn(str(k), r.detail); self.assertIn('--replace-signer', r.fix)

    def test_require_stops(self):
        k = self.broken()
        with self.assertRaises(self.toolchain.ToolError) as c: self.toolchain.require()
        self.assertIn('Signing key', str(c.exception)); self.assertIn(str(k), str(c.exception))



class Probe(unittest.TestCase):   # one signer in the repository (D-10): the probe app has no copy of its own
    def test_one_signer(self):
        self.assertFalse((REPO / 'probes' / 'app' / 'mkapk.py').exists())   # built from parts: the joined path is what the git grep gate looks for
        self.assertIn('nxnative/dm/android/apk/mkapk.py', (REPO / 'probes/app/probeapp.c').read_text(encoding='utf-8'))


if __name__ == '__main__': unittest.main()
