# packaging/build_bundle.py and packaging/glibc_floor.py: the asset names of the four bundles (D-10), the host-to-target mapping, which nxnative files
# a bundle carries, the engine id porter/paths.py keys its copy by, the glibc floor of a Linux bundle, and smoke_bundle.py's bare-PATH tool check (D-19),
# run here on the dev porter so fork-ci catches a regression on every push. Stdlib only: nothing here runs PyInstaller.
import contextlib, importlib.util, io, os, shutil, sys, tempfile, unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / 'packaging'))
import build_bundle, glibc_floor, smoke_bundle   # noqa: E402
from porter import pins   # noqa: E402
_spec = importlib.util.spec_from_file_location('ndk_pin', REPO / 'devtools' / 'ndk_pin.py'); ndk_pin = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ndk_pin)


class Names(unittest.TestCase):
    def test_asset_names(self):
        a = build_bundle.asset_name
        self.assertEqual(a('0.1.2-ns.1', 'macos', 'arm64'), 'nx2android-0.1.2-ns.1-macos-arm64.dmg')
        self.assertEqual(a('0.1.2-ns.1', 'windows', 'x64'), 'nx2android-0.1.2-ns.1-windows-x64.zip')
        self.assertEqual(a('0.1.2-ns.1', 'linux', 'x64'), 'nx2android-0.1.2-ns.1-linux-x64.tar.gz')
        self.assertEqual(a('0.1.2-ns.1', 'linux', 'arm64'), 'nx2android-0.1.2-ns.1-linux-arm64.tar.gz')

    def test_target_mapping(self):
        t = build_bundle.target
        self.assertEqual(t('darwin', 'arm64'), ('macos', 'arm64'))
        self.assertEqual(t('win32', 'AMD64'), ('windows', 'x64'))
        self.assertEqual(t('linux', 'x86_64'), ('linux', 'x64'))
        self.assertEqual(t('linux', 'aarch64'), ('linux', 'arm64'))


class Bundle(unittest.TestCase):
    def test_dmsh_xlate_bin_excluded(self):
        keep = 'nxnative/dm/games/010015100B514000/game.tsv'
        self.assertEqual(build_bundle.bundled(['nxnative/dm/gfx/tools/dmsh_xlate_bin/Gommon.dll', keep]), [keep])

    def test_engine_id_stable(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / 'a').write_bytes(b'one'); (Path(d) / 'b').write_bytes(b'two')
            first = build_bundle.engine_id(d, ['a', 'b'])
            self.assertEqual(first, build_bundle.engine_id(d, ['b', 'a']))
            self.assertRegex(first, r'^[0-9a-f]{16}$')   # porter/paths.py _engine() takes only an alphanumeric id
            (Path(d) / 'b').write_bytes(b'twO')
            self.assertNotEqual(first, build_bundle.engine_id(d, ['a', 'b']))


OBJDUMP = {
    'libQt6Gui.so.6': '0000000000000000      DF *UND*  0000000000000000 (GLIBC_2.17) memcpy\n0000000000000000      DF *UND*  0000000000000000 (GLIBC_2.34) pthread_create\n',
    'nx2android': '0000000000000000      DF *UND*  0000000000000000 (GLIBC_2.28) fcntl64\n',
}


class Glibc(unittest.TestCase):
    def test_floor_parse(self):
        need = glibc_floor.need(OBJDUMP)
        self.assertEqual(max(need, default=None), (2, 34))
        self.assertEqual(need.get((2, 34)), {'libQt6Gui.so.6'})
        with contextlib.redirect_stdout(io.StringIO()) as out:   # its "[RED] above" line would read as a real failure in a CI log
            self.assertEqual(glibc_floor.main(['glibc_floor.py', 'dist/nx2android', '2.34'], OBJDUMP), 0)
            self.assertEqual(glibc_floor.main(['glibc_floor.py', 'dist/nx2android', '2.33'], OBJDUMP), 1)
        self.assertIn('glibc floor 2.34: libQt6Gui.so.6', out.getvalue())


class BareEnv(unittest.TestCase):   # a Finder or app-menu launch: PATH=/usr/bin:/bin, so every tool must come from a known place (D-19, TOOL-04)
    def setUp(self): smoke_bundle.FAILS.clear(); self.tmp = Path(tempfile.mkdtemp()); self.addCleanup(shutil.rmtree, self.tmp, True)

    def run_check(self, porter=None):
        with contextlib.redirect_stdout(io.StringIO()) as out, mock.patch.object(smoke_bundle, 'porter', porter or smoke_bundle.porter):
            smoke_bundle.bare_env_check(sys.executable, self.tmp, extra_env={'PYTHONPATH': str(REPO)})
        return out.getvalue()

    @unittest.skipIf(os.name == 'nt', 'POSIX only: Windows has no bare-PATH launch to stand in for')
    def test_dev_porter(self):
        out = self.run_check()
        self.assertEqual(smoke_bundle.FAILS, [], out)
        for w in ('doctor', 'setup'): self.assertIn(f'PASS bare PATH: every tool row found ({w})', out)

    @unittest.skipIf(os.name == 'nt', 'POSIX only')
    def test_missing_tool_fails(self):
        # the .NET row stood in as not found: removing the stand-in alone is not enough where the host has its own dotnet in a known place
        # (/usr/share/dotnet on the GitHub runners, /opt/homebrew/bin on a dev Mac)
        real = smoke_bundle.porter
        def porter(exe, env, *args):
            doc, code, err = real(exe, env, *args)
            rows = doc if isinstance(doc, list) else next(s for s in doc['steps'] if s['id'] == 'tools')['items']
            for r in rows:
                if r['name'] == '.NET SDK': r['path'] = ''
            return doc, code, err
        out = self.run_check(porter)
        self.assertEqual(len(smoke_bundle.FAILS), 2, out)
        self.assertIn('.NET SDK', out)

    def test_windows_skipped(self):
        ran = mock.Mock()
        with mock.patch.object(smoke_bundle.os, 'name', 'nt'): out = self.run_check(ran)
        ran.assert_not_called(); self.assertEqual(smoke_bundle.FAILS, [])
        self.assertIn('SKIP bare PATH', out)


class NdkPin(unittest.TestCase):   # devtools/ndk_pin.py: the community asset is re-uploaded in place at times (RESEARCH Pitfall 1)
    row = pins.NDK['files']['linux-arm64']
    def release(self, size=None, digest=None): return {'assets': [{'name': ndk_pin.ASSET, 'size': size or self.row[1], 'digest': digest or 'sha256:' + self.row[3]}]}

    def test_match(self): self.assertEqual(ndk_pin.compare(self.release(), self.row), [])

    def test_drift(self):
        d = ndk_pin.compare(self.release(size=1, digest='sha256:' + 'ab' * 32), self.row)
        self.assertEqual(len(d), 2, d)
        self.assertIn(str(self.row[1]), d[0]); self.assertIn('1', d[0])
        self.assertIn(self.row[3], d[1]); self.assertIn('ab' * 32, d[1])

    def test_missing_asset(self):
        d = ndk_pin.compare({'assets': [{'name': 'other.tar.xz', 'size': 1, 'digest': 'sha256:00'}]}, self.row)
        self.assertEqual(len(d), 1); self.assertIn(ndk_pin.ASSET, d[0])


if __name__ == '__main__':
    unittest.main()
