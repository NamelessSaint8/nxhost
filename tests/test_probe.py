# porter/probe.py and the tool rows it feeds: the compile probe every found NDK gets (D-11) with subprocess.run answered from a table, its cache in <user dir>/probe.json,
# the community arm64 NDK's note (D-09, D-10) and the source / version / note fields of the NDK row (D-13). Standard library only; one test runs a real garbage file.
import errno, os, subprocess, sys, tempfile, types, unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
os.environ['NX2A_HOME'] = tempfile.mkdtemp()   # before porter is imported: no test touches the developer's settings or probe cache

from porter import distro, probe, toolchain   # noqa: E402

VERSION = 'Android (12470979, +pgo, +bolt, +lto, +mlgo, based on r522817c) clang version 18.0.3 (https://android.googlesource.com/toolchain/llvm-project)\nTarget: x86_64\n'


def ndk(d, rev=toolchain.NDK_REVISION):   # a folder that reads as an NDK of that revision, with an empty clang where probe looks for it
    d = Path(d); d.mkdir(parents=True, exist_ok=True); (d / 'source.properties').write_text(f'Pkg.Desc = Android NDK\nPkg.Revision = {rev}\n')
    c = probe.clang(d); c.parent.mkdir(parents=True, exist_ok=True); c.write_bytes(b''); c.chmod(0o755); return d


def fake(calls, link=(0, '', ''), version=VERSION):
    """A stand-in for subprocess.run: records (argv, kwargs); `--version` prints version, the link answers link (returncode, stdout, stderr) or raises it"""
    def run(argv, **kw):
        calls.append(([str(x) for x in argv], kw))
        if '--version' in argv: return subprocess.CompletedProcess(argv, 0, version, '')
        if isinstance(link, BaseException): raise link
        return subprocess.CompletedProcess(argv, *link)
    return run


class Probe(unittest.TestCase):
    def setUp(self):
        env = mock.patch.dict(os.environ); env.start(); self.addCleanup(env.stop)
        self.t = Path(tempfile.mkdtemp()); os.environ['NX2A_HOME'] = str(self.t / 'home')

    def run_probe(self, d, **kw):
        calls = []
        with mock.patch.object(probe.subprocess, 'run', fake(calls, **kw)): return probe.probe(d), calls

    def test_ok(self):
        d = ndk(self.t / 'ndk'); r, calls = self.run_probe(d)
        self.assertTrue(r['ok']); self.assertEqual(r['version'], 'clang 18.0.3'); self.assertTrue(r['detail'])
        argv, kw = next(c for c in calls if '-fuse-ld=lld' in c[0])
        self.assertIn('--target=aarch64-linux-android29', argv); self.assertNotIn('shell', kw); self.assertEqual(kw.get('timeout'), probe.TIMEOUT)
        cwd = Path(kw['cwd']).resolve()   # a temp folder: never the NDK, the repo or the bundle
        self.assertTrue(cwd.is_relative_to(Path(tempfile.gettempdir()).resolve())); self.assertFalse(cwd.is_relative_to(d.resolve())); self.assertFalse(cwd.is_relative_to(REPO))

    def test_link_fails(self):
        r, _ = self.run_probe(ndk(self.t / 'ndk'), link=(1, '', 'clang: warning: argument unused\nld.lld: error: cannot open crtbegin_dynamic.o\n'))
        self.assertFalse(r['ok']); self.assertTrue(r['detail'].endswith('ld.lld: error: cannot open crtbegin_dynamic.o'), r['detail'])

    def test_exec_format(self):
        r, _ = self.run_probe(ndk(self.t / 'ndk'), link=OSError(errno.ENOEXEC, 'Exec format error'))
        self.assertFalse(r['ok']); self.assertIn('Exec format error', r['detail']); self.assertIn('NDK built for this', r['fix'])

    def test_not_executable(self):
        for platform, xattr in (('darwin', True), ('linux', False)):
            with self.subTest(platform), mock.patch.object(probe, 'sys', types.SimpleNamespace(platform=platform)):
                d = ndk(self.t / platform); r, _ = self.run_probe(d, link=PermissionError(errno.EACCES, 'Permission denied'))
                self.assertFalse(r['ok']); self.assertIn('not executable', r['detail']); self.assertIn('chmod +x', r['fix'])
                self.assertEqual(f'xattr -dr com.apple.quarantine {d}' in r['fix'], xattr)

    def test_timeout(self):
        r, _ = self.run_probe(ndk(self.t / 'ndk'), link=subprocess.TimeoutExpired('clang', probe.TIMEOUT))
        self.assertFalse(r['ok']); self.assertIn('timed out after 60 s', r['detail'])

    def test_no_clang(self):
        d = ndk(self.t / 'ndk'); probe.clang(d).unlink()
        r, calls = self.run_probe(d)
        self.assertFalse(r['ok']); self.assertIn('no clang at', r['detail']); self.assertEqual(calls, [])

    def test_cached(self):
        d = ndk(self.t / 'ndk'); _, calls = self.run_probe(d); self.assertTrue(calls)
        cache = self.t / 'home' / 'probe.json'; self.assertTrue(cache.is_file())
        r, calls = self.run_probe(d); self.assertTrue(r['ok']); self.assertEqual(r['version'], 'clang 18.0.3'); self.assertEqual(calls, [])   # the same clang: no process
        c = probe.clang(d); st = c.stat(); os.utime(c, ns=(st.st_atime_ns, st.st_mtime_ns + 10**9))
        _, calls = self.run_probe(d); self.assertTrue(calls)   # a touched clang is probed again
        before = cache.read_text()
        r, _ = self.run_probe(ndk(self.t / 'bad'), link=(1, '', 'ld.lld: error: x'))
        self.assertFalse(r['ok']); self.assertEqual(cache.read_text(), before)   # a failure is never cached: a fixed NDK passes on the next check
        r, calls = self.run_probe(self.t / 'bad', link=(1, '', 'ld.lld: error: x')); self.assertTrue(calls)

    def test_corrupt_cache(self):
        d = ndk(self.t / 'ndk'); (self.t / 'home').mkdir(parents=True, exist_ok=True); (self.t / 'home' / 'probe.json').write_text('{not json')
        r, calls = self.run_probe(d); self.assertTrue(r['ok']); self.assertTrue(calls)

    @unittest.skipIf(os.name == 'nt', 'POSIX exec format')
    def test_real_enoexec(self):   # a real file the kernel cannot run, as an NDK built for another CPU is
        d = ndk(self.t / 'ndk'); c = probe.clang(d); c.write_bytes(b'\x00\x01\x02garbage\xff' * 64); c.chmod(0o755)
        r = probe.probe(d)
        self.assertFalse(r['ok']); self.assertIn('Exec format error', r['detail'])


class Rows(unittest.TestCase):   # the rows `doctor --json` and the setup screen show
    def setUp(self):
        env = mock.patch.dict(os.environ); env.start(); self.addCleanup(env.stop)
        self.t = Path(tempfile.mkdtemp()); os.environ['NX2A_HOME'] = str(self.t / 'home')

    def row(self, name, cfg=None): return next(r for r in toolchain.checks(cfg or {}) if r.name == name)

    def test_fields(self):
        self.assertEqual(sorted(toolchain.Check('x', True, '').as_dict()), ['detail', 'fix', 'name', 'note', 'ok', 'path', 'required', 'source', 'version'])

    def test_ndk_row(self):
        d = ndk(self.t / 'ndk')
        good = {'ok': True, 'detail': 'links an Android program', 'version': 'clang 18.0.3', 'fix': ''}
        bad = {'ok': False, 'detail': 'cannot run clang: Exec format error (built for another CPU)', 'version': '', 'fix': 'use an NDK built for this computer'}
        with mock.patch.object(toolchain, 'find_ndk', return_value=(d, toolchain.NDK_REVISION)):
            with mock.patch.object(probe, 'probe', return_value=good): r = self.row('Android NDK', {'ndk': str(d)})
            self.assertTrue(r.ok); self.assertEqual(r.version, toolchain.NDK_REVISION); self.assertEqual(r.source, 'configured'); self.assertEqual(r.note, '')
            with mock.patch.object(probe, 'probe', return_value=bad): r = self.row('Android NDK', {'ndk': str(d)})
            self.assertFalse(r.ok); self.assertTrue(r.required); self.assertTrue(r.detail.endswith(bad['detail'])); self.assertEqual(r.fix, bad['fix'])

    def test_adb_version_row(self):
        a = self.t / 'adb'; a.write_bytes(b''); a.chmod(0o755)
        def row(v, arm=False, found=True):
            with mock.patch.object(toolchain, 'find_adb', return_value=a if found else None), mock.patch.object(toolchain.hosttools, 'adb_version', return_value=v), \
                 mock.patch.object(toolchain.hosttools, 'linux_arm64', return_value=arm), mock.patch.object(distro.platform, 'freedesktop_os_release', return_value={'ID': 'ubuntu'}):
                return self.row('adb'), distro.adb_hint()
        r, _ = row({'version': '36.0.0-13206524', 'major': 36, 'protocol': 41})
        self.assertTrue(r.ok); self.assertEqual(r.version, '36.0.0-13206524'); self.assertEqual(r.note, ''); self.assertTrue(r.source); self.assertFalse(r.required)
        r, _ = row({'version': '29.0.6', 'major': 29, 'protocol': 41})
        self.assertTrue(r.ok); self.assertEqual(r.note, 'adb 29.0.6: pushes without -Z (it has no push compression to turn off)')
        for arm in (False, True):
            r, _ = row({'version': '28.0.2', 'major': 28, 'protocol': 38}, arm)
            self.assertFalse(r.ok); self.assertIn('too old', r.detail); self.assertIn('newer adb from your distribution', r.fix); self.assertEqual('Download missing tools' in r.fix, not arm)
        r, hint = row(None, True, found=False)
        self.assertFalse(r.ok); self.assertEqual(r.fix, hint); self.assertEqual(hint, 'Run sudo apt install adb, then press Re-check.')


if __name__ == '__main__':
    unittest.main()
