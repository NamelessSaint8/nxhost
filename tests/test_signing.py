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
    return subprocess.Popen([sys.executable, str(MKAPK), str(so or Key.so), str(out), str(key)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)


def run(key, out):
    p = mk(key, out); o = p.communicate(timeout=300)[0]; return p.returncode, o


def signer(o):
    m = SIGNER.search(o); return m and m.group(1)


class Key(unittest.TestCase):
    @classmethod
    def setUpClass(cls):   # one key made once (pure-Python RSA takes seconds); later tests copy it
        cls.tmp = Path(tempfile.mkdtemp(prefix='nx2a_sign_'))
        cls.so = cls.tmp / 'libprobe.so'; cls.so.write_bytes(b'\x7fELF' + bytes(60))
        cls.key = cls.tmp / 'base' / 'signing-key.json'; cls.key.parent.mkdir()
        cls.rc, cls.out = run(cls.key, cls.tmp / 'base' / 'a.apk')

    @classmethod
    def tearDownClass(cls): shutil.rmtree(cls.tmp, ignore_errors=True)

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


if __name__ == '__main__': unittest.main()
