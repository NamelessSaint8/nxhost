# Cut-off stages redo themselves (HARD-05, D-08): a stage's reuse key goes first and is written last and whole, after its outputs are swapped in.
# The children here are killed with os._exit, which skips finally blocks and atexit like SIGKILL does, on every OS. No game files, toolchains or device.
import os, subprocess, sys, tempfile, unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
HOME = tempfile.mkdtemp(prefix='nx2a_test_home_'); os.environ['NX2A_HOME'] = HOME

MISSING = None
for _m in ('lz4.block', 'capstone'):
    try: __import__(_m)
    except ModuleNotFoundError:
        if os.environ.get('CI'): raise   # CI installs the lock: a missing module there is a failure
        MISSING = MISSING or _m


def setUpModule():   # not a module-level SkipTest: `python -m unittest tests.test_stages` crashes on one
    if MISSING: raise unittest.SkipTest(f'{MISSING} is not installed (python -m pip install -r requirements.txt)')


# extract_aoc on one DLC, nx_extract replaced by a stub that writes half its output and, when kill is set, dies there
CHILD = '''
import sys; sys.path.insert(0, {repo!r})
from pathlib import Path
from porter.upstream import nsp
def run(cmd, log, env=None, **kw):
    open({calls!r}, 'a').write('run\\n')
    out = Path(str(cmd[-1])); out.mkdir(parents=True, exist_ok=True); (out / 'half').write_text('x')
    if {kill}: import os; os._exit(9)
    (out / 'whole').write_text('x')
nsp.run = run
nsp.extract_aoc(Path('nx'), Path('k'), Path({nxnative!r}), Path({work!r}), 0x0100000000AAA000, {{'dlc': [(0x0100000000AAB001, 0, Path({dlc!r}))]}}, Path({work!r}) / 'logs')
'''


class CutOff(unittest.TestCase):
    def setUp(self):
        self.t = Path(tempfile.mkdtemp(prefix='nx2a_test_stages_')); self.work = self.t / '0100000000AAA000_build'; self.work.mkdir()
        self.dlc = self.t / 'dlc.nsp'; self.dlc.write_bytes(b'\0'); self.calls = self.t / 'calls'

    def tearDown(self):
        import shutil; shutil.rmtree(self.t, ignore_errors=True)

    def child(self, kill):
        code = CHILD.format(repo=str(REPO), calls=str(self.calls), kill=kill, nxnative=str(REPO / 'nxnative'), work=str(self.work), dlc=str(self.dlc))
        return subprocess.run([sys.executable, '-c', code], cwd=REPO, env=dict(os.environ, NX2A_HOME=HOME), capture_output=True, text=True, timeout=120)

    def ran(self): return self.calls.read_text().count('run') if self.calls.exists() else 0

    def test_killed_dlc_stage_redone(self):
        kf, aoc = self.work / 'aoc.key', self.work / 'aoc'
        r = self.child(True)
        self.assertEqual(r.returncode, 9, r.stderr)
        self.assertFalse(kf.exists()); self.assertFalse(aoc.exists())   # cut off before the swap: no stamp, no output
        r = self.child(False)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue((aoc / '1/whole').is_file())
        key, note = kf.read_text().splitlines()[:2]
        self.assertRegex(key, r'^[0-9a-f]+$'); self.assertEqual(note, '1 DLC')
        self.assertEqual(sorted(p.name for p in self.work.iterdir()), ['aoc', 'aoc.key'])   # no temp file left beside the key
        n = self.ran(); r = self.child(False)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.ran(), n)   # reused: nx_extract not run again

    def test_write_whole_never_half(self):
        from porter.upstream import nsp
        self.assertTrue(hasattr(nsp, 'write_whole'), 'build_ipa_from_nsp.py has no write_whole')
        p = self.t / 'stage.key'
        nsp.write_whole(p, 'abc\n2 DLC\n')
        self.assertEqual(p.read_text(encoding='utf-8'), 'abc\n2 DLC\n')
        self.assertEqual([q.name for q in self.t.iterdir() if q.name.startswith('stage.key')], ['stage.key'])
        with mock.patch.object(nsp.os, 'replace', side_effect=OSError('cut off')), self.assertRaises(OSError): nsp.write_whole(p, 'new\n')
        self.assertEqual(p.read_text(encoding='utf-8'), 'abc\n2 DLC\n')


if __name__ == '__main__': unittest.main()
