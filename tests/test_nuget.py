# The NuGet pin check (porter/nuget.py, D-05 as amended 2026-10-30): every package a restore resolved must carry the content hash porter/pins.py NUGET pins,
# else the port stops naming it and its folder goes. A temp project.assets.json and package folder stand in for a real restore; no .NET, network or game files.
import base64, json, os, sys, tempfile, unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
os.environ['NX2A_HOME'] = tempfile.mkdtemp(prefix='nx2a_test_home_')

MISSING = None
try:
    from porter import nuget, pins                  # noqa: E402
    from porter.upstream import BuildError, nsp     # noqa: E402
except ModuleNotFoundError as e:   # CI installs the lock, so there a missing engine module fails; locally it is a named skip
    if (MISSING := (e.name or '').split('.')[0]) not in ('lz4', 'capstone', 'PIL', 'yaml', 'backports') or os.environ.get('CI'): raise


def setUpModule():   # not a module-level SkipTest: `python -m unittest tests.test_nuget` crashes on one
    if MISSING: raise unittest.SkipTest(f'{MISSING} is not installed (python -m pip install -r requirements.txt): the engine modules need it')


def make_project(libs, signed=None):
    """A project folder whose obj/project.assets.json lists libs {'<id>/<version>': content hash or None} as packages (plus one project reference), each with
    its folder in a temp NuGet packages folder; signed {'<id>/<version>': whole-file hash} writes that package's .nupkg.sha512. Returns (project, packages)"""
    t = Path(tempfile.mkdtemp(prefix='nx2a_test_nuget_')); proj, pkgs = t / 'proj', t / 'nuget'; (proj / 'obj').mkdir(parents=True)
    lib = {'Ryujinx.Common/1.0.0': {'type': 'project', 'path': '../Ryujinx.Common/Ryujinx.Common.csproj'}}
    for k, h in libs.items():
        i, v = k.lower().split('/'); (pkgs / i / v).mkdir(parents=True)
        lib[k] = {'type': 'package', 'path': f'{i}/{v}', **({'sha512': h} if h else {})}
    for k, h in (signed or {}).items():
        i, v = k.lower().split('/'); (pkgs / i / v / f'{i}.{v}.nupkg.sha512').write_text(h, encoding='utf-8')
    (proj / 'obj/project.assets.json').write_text(json.dumps({'version': 3, 'libraries': lib, 'packageFolders': {str(pkgs) + os.sep: {}}}), encoding='utf-8')
    return proj, pkgs


class Check(unittest.TestCase):
    PIN = {'LibHac/0.19.0': 'AAA='}

    def test_pinned_passes(self):
        proj, pkgs = make_project({'LibHac/0.19.0': 'AAA='})
        with mock.patch.dict(pins.NUGET, self.PIN, clear=True): nuget.check(proj)   # the project-type entry is not a package
        self.assertTrue((pkgs / 'libhac/0.19.0').is_dir())

    def test_mismatch_stops_and_removes(self):
        proj, pkgs = make_project({'LibHac/0.19.0': 'BBB='})
        with mock.patch.dict(pins.NUGET, self.PIN, clear=True), self.assertRaises(BuildError) as c: nuget.check(proj)
        for s in ('LibHac/0.19.0', 'BBB=', 'AAA='): self.assertIn(s, str(c.exception))
        self.assertFalse((pkgs / 'libhac/0.19.0').exists())   # the next restore fetches it again

    def test_resigned_package_passes(self):   # nuget.org re-signs: the whole-file hash changes, the content hash does not
        proj, _ = make_project({'LibHac/0.19.0': 'AAA='}, signed={'LibHac/0.19.0': 'hWsrphNcxDIFFERENT=='})
        with mock.patch.dict(pins.NUGET, self.PIN, clear=True): nuget.check(proj)

    def test_unpinned_stops(self):
        proj, pkgs = make_project({'LibHac/0.19.0': 'AAA=', 'Evil/6.6.6': 'CCC='})
        with mock.patch.dict(pins.NUGET, self.PIN, clear=True), self.assertRaises(BuildError) as c: nuget.check(proj)
        self.assertIn('Evil/6.6.6', str(c.exception)); self.assertNotIn('LibHac', str(c.exception))
        self.assertFalse((pkgs / 'evil/6.6.6').exists()); self.assertTrue((pkgs / 'libhac/0.19.0').is_dir())

    def test_missing_content_hash_stops(self):
        proj, _ = make_project({'LibHac/0.19.0': None})
        with mock.patch.dict(pins.NUGET, self.PIN, clear=True), self.assertRaises(BuildError) as c: nuget.check(proj)
        self.assertIn('LibHac/0.19.0', str(c.exception))

    def test_restored_runs_restore_then_check(self):
        proj, _ = make_project({'LibHac/0.19.0': 'BBB='})
        log = Path(tempfile.mkdtemp()) / 'logs/nuget_restore.log'; env = {'NUGET_PACKAGES': 'x'}; ran = []
        with mock.patch.dict(pins.NUGET, self.PIN, clear=True), mock.patch.object(nsp, 'run', lambda cmd, lg, env=None, **kw: ran.append((cmd, lg, env))):
            with self.assertRaises(BuildError):
                with nuget.restored(proj, Path('/sdk/dotnet'), env, log): ran.append('body')
        self.assertEqual(len(ran), 1, ran)   # the restore ran, the body did not
        cmd, lg, e = ran[0]
        self.assertEqual(cmd[:3], [str(Path('/sdk/dotnet')), 'restore', str(proj)]); self.assertEqual((lg, e), (log, env))
        self.assertTrue(log.parent.is_dir())


class Pins(unittest.TestCase):
    def test_nuget_pins(self):
        self.assertIn('LibHac/0.19.0', pins.NUGET)
        for k, v in pins.NUGET.items():
            self.assertRegex(k, r'^[A-Za-z0-9_.-]+/[0-9][A-Za-z0-9.+-]*$')
            self.assertEqual(len(base64.b64decode(v, validate=True)), 64, k)
        self.assertTrue(pins.NUGET['LibHac/0.19.0'].startswith('7uMUGFpO2V0'))   # 'hWsrphNcx…' would be the signed file's hash: the wrong field


if __name__ == '__main__':
    unittest.main()
