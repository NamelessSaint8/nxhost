# The new shell (gui/shell.py), headless: it hosts gui/firstrun.py's gate unchanged (D-01), draws porter's `setup --json` in its Setup view and keeps a tool
# download from being orphaned when it closes. A stand-in call_json (patched on gui.shell and gui.firstrun) answers from tests/fixtures/bridge/setup_*.json on the
# next event-loop turn, as tests/test_firstrun.py's; the Close tests run a real Porter on tests/fixtures/bridge/fake_porter.py --tree.
import copy, json, os, sys, tempfile, time, unittest
from pathlib import Path
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
REPO = Path(__file__).resolve().parent.parent
FIXTURES = REPO / 'tests/fixtures/bridge'
FAKE = str(FIXTURES / 'fake_porter.py')
sys.path.insert(0, str(REPO))

# a declared floor, not a missing module, so it skips in CI too: PySide6 6.12's refcount bug on True aborts 3.11
OLD = sys.version_info < (3, 12)
MISSING = None
for _m in () if OLD else ('PySide6.QtWidgets',):
    try: __import__(_m)
    except ModuleNotFoundError:
        if os.environ.get('CI'): raise   # CI installs the lock: a missing module there is a failure
        MISSING = MISSING or _m.split('.')[0]

HOME = tempfile.mkdtemp()
shell = None
if not (OLD or MISSING):
    from PySide6.QtCore import QTimer
    from PySide6.QtTest import QSignalSpy, QTest
    from PySide6.QtWidgets import QApplication
    from gui import firstrun, runner
    try: from gui import shell
    except ImportError: pass   # RED: each test then fails on the missing module, not on loading
APP = None


def setUpModule():
    global APP
    if OLD: raise unittest.SkipTest('the GUI needs Python 3.12+ (PySide6 6.12 refcount bug on 3.11)')
    if MISSING: raise unittest.SkipTest(f'{MISSING} is not installed (python -m pip install -r requirements.txt)')
    os.environ['NX2A_HOME'] = HOME   # here, not at import: discovery imports other test modules that set their own
    APP = QApplication.instance() or QApplication([])
    APP.setQuitOnLastWindowClosed(False)


def until(pred, ms):   # spin the event loop until pred() holds
    end = time.time() + ms / 1000
    while not pred() and time.time() < end: QTest.qWait(20)
    return pred()


def doc(name='setup_ready.json'): return json.loads((FIXTURES / name).read_text(encoding='utf-8'))


class Calls:   # stands in for gui.runner.call_json: answers each command from self.answers (or self.fail) on the next turn, records every args list
    def __init__(self, test, setup):
        self.args, self.fail = [], {}
        self.answers = {'setup': setup}
        for m in (shell, firstrun):
            p = mock.patch.object(m, 'call_json', self); p.start(); test.addCleanup(p.stop)

    def __call__(self, parent, args, done, timeout=None):
        self.args.append(list(args)); cmd = args[0]; fail = self.fail.get(cmd)
        obj = None if fail else {'key': args[1], 'value': args[2]} if cmd == 'config' else copy.deepcopy(self.answers.get(cmd))
        QTimer.singleShot(0, parent, lambda: done(obj, 1 if fail else 0, fail))   # never into a destroyed owner, as call_json

    def sent(self, cmd): return [a for a in self.args if a[0] == cmd]


def launch(test, setup=None, fail=None):   # a Shell whose first setup --json has answered (or failed); its stand-in
    test.assertIsNotNone(shell, 'gui/shell.py does not exist')
    calls = Calls(test, setup or doc())
    if fail: calls.fail['setup'] = fail
    w = shell.Shell(); test.addCleanup(w.deleteLater)
    until(lambda: w.first_run.doc is not None or 'Retry' in w.setup.check_msg.text(), 3000)
    return w, calls


def banner(w): g = w.first_run; return g.text.text() if g.banner.isVisibleTo(w) else None   # the banner's text when it shows, else None


class Gate(unittest.TestCase):
    def test_banner_in_shell(self):
        w, calls = launch(self, doc('setup_missing.json'))
        self.assertEqual(calls.sent('setup'), [['setup', '--json']])
        self.assertEqual(banner(w), 'Setup is not finished: missing prod.keys, Android NDK.')
        self.assertIsNone(w.first_run.wizard)

    def test_wizard_in_shell(self):   # the same module's Wizard over the shell, not a copy
        w, _ = launch(self, doc('setup_first.json')); z = w.first_run.wizard
        self.assertIsNotNone(z, 'no wizard opened'); self.assertIs(type(z), firstrun.Wizard)
        self.assertTrue(z.isVisible()); self.assertIs(z.parentWidget(), w)
        self.assertEqual(z.currentId(), firstrun.PAGES.index('legal'))

    def test_failed_no_gate(self):
        w, calls = launch(self, fail={'timeout': 45, 'error': '', 'stderr': ''})
        self.assertIn('Retry', w.setup.check_msg.text()); self.assertIn("didn't answer in 45 s", w.setup.check_msg.text())
        self.assertIsNone(w.first_run.doc); self.assertIsNone(banner(w)); self.assertIsNone(w.first_run.wizard)
        with mock.patch.object(w, 'set_ready') as ready:
            w.setup.check_msg.linkActivated.emit('retry'); self.assertTrue(until(lambda: ready.called, 3000))
        ready.assert_called_with(False)
        self.assertEqual(len(calls.sent('setup')), 2)

    def test_ready_quiet(self):
        w, _ = launch(self)
        self.assertIsNotNone(w.first_run.doc); self.assertIsNone(banner(w)); self.assertIsNone(w.first_run.wizard)
        self.assertEqual(w.windowTitle(), 'nx2android')
        self.assertEqual([w.nav.item(i).text() for i in range(w.nav.count())], ['Setup'])


if __name__ == '__main__': unittest.main()
