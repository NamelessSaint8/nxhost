# porter/toolchain.py: toolchain detection and the Python floor (D-13: the CVE-2025-4517 tarfile fix, by version or by its os.path.ALLOW_MISSING marker),
# and porter/runlog.py's refusal of every command but doctor on a Python without it. Standard library only, so it runs without the engine modules.
import argparse, contextlib, io, json, os, sys, tempfile, unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
os.environ['NX2A_HOME'] = tempfile.mkdtemp()

from porter import runlog, toolchain   # noqa: E402


def call(ns):   # runlog.run on a Namespace with python_ok() False: (exit code, stdout, the command's fn)
    fn = mock.Mock(return_value=0); out = io.StringIO()
    with mock.patch.object(toolchain, 'python_ok', return_value=False, create=True), contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()): code = runlog.run(ns, fn)
    return code, out.getvalue(), fn


class PythonFloor(unittest.TestCase):
    def setUp(self):
        keep = dict(os.environ); self.addCleanup(lambda: (os.environ.clear(), os.environ.update(keep)))
        os.environ.pop('NX2A_GUI', None); os.environ['NX2A_HOME'] = tempfile.mkdtemp()

    def test_floors(self):
        for v in ((3, 10, 99), (3, 11, 12), (3, 12, 10), (3, 13, 3)):
            with self.subTest(v=v): self.assertFalse(toolchain.python_ok(v, marker=False))
        for v in ((3, 11, 13), (3, 12, 11), (3, 13, 4), (3, 14, 0), (3, 15, 0)):
            with self.subTest(v=v): self.assertTrue(toolchain.python_ok(v, marker=False))
        self.assertTrue(toolchain.python_ok((3, 12, 3), marker=True)); self.assertFalse(toolchain.python_ok((3, 12, 3), marker=False))
        self.assertFalse(toolchain.python_ok((3, 10, 99), marker=True))

    def test_doctor_row(self):
        with mock.patch.object(toolchain, 'python_ok', return_value=False, create=True): row = next(r for r in toolchain.checks() if r.name == 'Python')
        self.assertFalse(row.ok)
        for v in ('3.11.13', '3.12.11', '3.13.4'): self.assertIn(v, row.fix)

    def test_refusal_one_shot(self):
        code, out, fn = call(argparse.Namespace(cmd='inspect', json=True))
        self.assertEqual(code, 1); fn.assert_not_called()
        self.assertIn('CVE-2025-4517', json.loads(out)['error'])

    def test_refusal_long(self):
        code, out, fn = call(argparse.Namespace(cmd='port', progress='json', json=False, install=False))
        self.assertEqual(code, 1); fn.assert_not_called()
        evs = [json.loads(ln) for ln in out.splitlines() if ln.startswith('{')]
        self.assertEqual(evs[0]['ev'], 'log')
        err = [e for e in evs if e['ev'] == 'error']
        self.assertEqual([e['type'] for e in err], ['PythonError']); self.assertIn('CVE-2025-4517', err[0]['msg'])
        self.assertIn('[RED] ', Path(evs[0]['path']).read_text(encoding='utf-8'))

    def test_doctor_still_runs(self):
        code, _, fn = call(argparse.Namespace(cmd='doctor', json=True))
        fn.assert_called_once(); self.assertEqual(code, 0)


if __name__ == '__main__': unittest.main()
