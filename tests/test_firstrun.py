# The first-run gate (gui/firstrun.py) over today's window, headless: porter's `setup --json` drawn on every launch as the Setup tab's checklist, a banner that
# names what is missing, and the wizard that opens while the legal notice is not accepted. A stand-in call_json (patched on gui.app and gui.firstrun) answers
# from tests/fixtures/bridge/setup_*.json on the next event-loop turn; the subprocess path is tests/test_bridge.py's.
import copy, json, os, sys, tempfile, time, unittest
from pathlib import Path
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
REPO = Path(__file__).resolve().parent.parent
FIXTURES = REPO / 'tests/fixtures/bridge'
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
if not (OLD or MISSING):
    from PySide6.QtCore import QSize, Qt, QTimer
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QLabel, QScrollArea, QWizard
    from gui import app, firstrun
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
        self.args, self.fail, self.hold = [], {}, set()
        self.answers = {'setup': setup, 'devices': [], 'profiles': []}
        for m in (app, firstrun):
            p = mock.patch.object(m, 'call_json', self); p.start(); test.addCleanup(p.stop)

    def __call__(self, parent, args, done, timeout=None):
        self.args.append(list(args)); cmd = args[0]
        if cmd in self.hold: return
        fail = self.fail.get(cmd)
        obj = None if fail else {'key': args[1], 'value': args[2]} if cmd == 'config' else copy.deepcopy(self.answers.get(cmd))
        QTimer.singleShot(0, parent, lambda: done(obj, 1 if fail else 0, fail))   # never into a destroyed owner, as call_json

    def sent(self, cmd): return [a for a in self.args if a[0] == cmd]


def launch(test, setup=None, fail=None):   # a Window whose first setup --json has answered (or failed); its stand-in
    calls = Calls(test, setup or doc())
    if fail: calls.fail['setup'] = fail
    w = app.Window(); test.addCleanup(w.deleteLater)
    g = lambda: getattr(w, 'first_run', None)
    until(lambda: (g() and g().doc is not None) or 'Retry' in w.setup.check_msg.text(), 3000)
    return w, calls


def gate(test, w):
    g = getattr(w, 'first_run', None); test.assertIsNotNone(g, 'the window has no first-run gate (firstrun.attach)')
    return g


def banner(test, w):   # the banner's text when it shows, else None
    g = gate(test, w); return g.text.text() if g.banner.isVisibleTo(w) else None


class Launch(unittest.TestCase):
    def test_ready_no_banner(self):
        w, calls = launch(self)
        self.assertEqual(calls.sent('setup'), [['setup', '--json']])
        self.assertEqual(calls.sent('doctor'), [])
        g = gate(self, w); self.assertIsNotNone(g.doc)
        self.assertIsNone(banner(self, w)); self.assertIsNone(g.wizard)

    def test_first_opens_wizard(self):
        with mock.patch.object(firstrun, 'open_setup') as op: w, _ = launch(self, doc('setup_first.json'))
        op.assert_called_once_with(w, 'legal')

    def test_second_doc_never_opens(self):   # D-02: only the launch's first answer can open the wizard
        w, calls = launch(self, doc('setup_first.json'))
        with mock.patch.object(firstrun, 'open_setup') as op:
            w.recheck(); self.assertTrue(until(lambda: len(calls.sent('setup')) == 2, 3000)); QTest.qWait(50)
        op.assert_not_called()

    def test_nothing_written(self):   # FRUN-03: readiness lives in porter; the GUI writes no file and sends no config on a launch
        before = sorted(p.name for p in Path(HOME).iterdir())
        w, calls = launch(self, doc('setup_missing.json'))
        self.assertEqual(calls.sent('config'), [])
        self.assertEqual(sorted(p.name for p in Path(HOME).iterdir()), before)


class Banner(unittest.TestCase):
    def test_names_missing(self):
        with mock.patch.object(firstrun, 'open_setup') as op: w, _ = launch(self, doc('setup_missing.json'))
        self.assertEqual(banner(self, w), 'Setup is not finished: missing prod.keys, Android NDK.')
        op.assert_not_called()

    def test_one_name(self):
        d = doc('setup_missing.json'); d['missing'] = ['prod.keys']
        w, _ = launch(self, d)
        self.assertEqual(banner(self, w), 'Setup is not finished: missing prod.keys.')

    def test_plain_text(self):
        d = doc('setup_missing.json'); d['missing'] = ['<b>x</b>']
        w, _ = launch(self, d)
        self.assertEqual(banner(self, w), 'Setup is not finished: missing <b>x</b>.')
        self.assertEqual(gate(self, w).text.textFormat(), Qt.PlainText)

    def test_soft_notes_no_banner(self):   # ready with only a soft note (no adb): no banner
        d = doc(); d['notes'] = ['No adb yet: port now, install later.']
        w, _ = launch(self, d)
        self.assertIsNone(banner(self, w))

    def test_failed_setup(self):
        w, calls = launch(self, fail={'timeout': 45, 'error': '', 'stderr': ''})
        self.assertIn('Retry', w.setup.check_msg.text())
        self.assertIn("didn't answer in 45 s", w.setup.check_msg.text())
        self.assertIs(w.tabs.currentWidget(), w.setup)   # today's jump, so Retry is in view
        g = gate(self, w); self.assertIsNone(g.doc); self.assertIsNone(banner(self, w)); self.assertIsNone(g.wizard)
        with mock.patch.object(w, 'set_ready') as ready:
            w.setup.check(); self.assertTrue(until(lambda: ready.called, 3000))
        ready.assert_called_with(False)


class SetupTab(unittest.TestCase):
    def test_checks_and_notes(self):
        d = doc(); d['notes'] = ['No adb yet: port now, install later.']
        w, _ = launch(self, d); t = w.setup.table
        self.assertEqual(t.rowCount(), len(d['checks']) + 1)
        self.assertEqual([t.item(i, 1).text() for i in range(len(d['checks']))], [r['name'] for r in d['checks']])
        self.assertEqual(t.item(0, 0).text(), '✓')
        last = t.rowCount() - 1
        self.assertEqual((t.item(last, 0).text(), t.item(last, 1).text(), t.item(last, 2).text()), ('!', 'Note', 'No adb yet: port now, install later.'))

    def test_failed_check_marks(self):   # today's rendering: ✗ for a required row, with its fix after an arrow
        w, _ = launch(self, doc('setup_missing.json')); t = w.setup.table
        i = [t.item(r, 1).text() for r in range(t.rowCount())].index('Android NDK')
        self.assertEqual(t.item(i, 0).text(), '✗')
        self.assertIn('→  Download missing tools', t.item(i, 2).text())

    def test_run_setup_button(self):
        w, _ = launch(self)
        self.assertEqual(w.setup.run_btn.text(), 'Run setup')

    def test_run_setup_opens_done(self):   # every step ok: Run setup opens the wizard at the done page
        w, _ = launch(self); w.setup.run_btn.click()
        z = wiz(self, w); self.assertTrue(z.isVisible()); self.assertEqual(z.currentId(), firstrun.PAGES.index('done'))


def wiz(test, w):
    z = gate(test, w).wizard; test.assertIsNotNone(z, 'no wizard is open'); return z


def shown(page): return '\n'.join(l.text() for l in page.findChildren(QLabel) if l.isVisibleTo(page))   # the page's text as the player sees it


class Wizard(unittest.TestCase):
    def test_non_modal_classic(self):
        w, _ = launch(self, doc('setup_first.json')); z = wiz(self, w)
        self.assertIsInstance(z, QWizard); self.assertTrue(z.isVisible()); self.assertFalse(z.isModal())
        self.assertIs(z.parentWidget(), w); self.assertTrue(z.windowFlags() & Qt.Window)
        self.assertEqual(z.wizardStyle(), QWizard.ClassicStyle); self.assertEqual(z.windowTitle(), 'nx2android setup')
        self.assertEqual(z.minimumSize(), QSize(720, 560))
        self.assertEqual(z.currentId(), firstrun.PAGES.index('legal'))
        self.assertEqual(z.button(QWizard.CustomButton1).text(), 'Skip setup')

    def test_start_first_not_ok(self):   # legal ok, keys not: the keys page, and Back still reaches legal (D-04)
        w, _ = launch(self, doc('setup_missing.json')); gate(self, w).button.click()
        z = wiz(self, w); self.assertEqual(z.currentId(), firstrun.PAGES.index('keys'))
        z.back(); self.assertEqual(z.currentId(), firstrun.PAGES.index('legal'))
        w2, _ = launch(self); firstrun.open_setup(w2)
        self.assertEqual(wiz(self, w2).currentId(), firstrun.PAGES.index('done'))

    def test_single_instance(self):
        w, _ = launch(self, doc('setup_missing.json')); g = gate(self, w)
        g.button.click(); z = wiz(self, w); g.button.click()
        self.assertIs(wiz(self, w), z); self.assertEqual(len([x for x in w.findChildren(QWizard) if x.isVisible()]), 1)

    def test_skip_closes_no_write(self):
        w, calls = launch(self, doc('setup_first.json')); g = gate(self, w); z = wiz(self, w)
        z.button(QWizard.CustomButton1).click()
        self.assertTrue(until(lambda: not z.isVisible(), 1000)); self.assertIsNone(g.wizard)
        w.recheck(); self.assertTrue(until(lambda: len(calls.sent('setup')) == 2, 3000)); QTest.qWait(50)
        self.assertIsNone(g.wizard)   # the next answer does not reopen it
        self.assertEqual(calls.sent('config'), [])
        g.button.click(); z = wiz(self, w); QTest.keyClick(z, Qt.Key_Escape)   # Esc does the same
        self.assertTrue(until(lambda: not z.isVisible(), 1000)); self.assertIsNone(g.wizard)

    def test_page_text(self):
        d = doc('setup_missing.json'); d['steps'][3].update(ok=False, detail='no adb found', fix='Download missing tools')
        w, _ = launch(self, d); gate(self, w).button.click(); z = wiz(self, w)
        for k, head in (('keys', 'Your prod.keys'), ('tools', 'Tools for building the app'), ('device', 'Connect your Android device')):
            s = next(x for x in d['steps'] if x['id'] == k); text = shown(z.page(firstrun.PAGES.index(k)))
            with self.subTest(k):
                for want in (head, s['detail'], s['fix']): self.assertIn(want, text)
        self.assertIn('Setup is not finished', shown(z.page(firstrun.PAGES.index('done'))))
        d = doc(); d['steps'][2]['fix'] = 'a fix for an ok step'
        w, _ = launch(self, d); firstrun.open_setup(w); z = wiz(self, w); text = shown(z.page(firstrun.PAGES.index('tools')))
        self.assertIn('every tool is here', text); self.assertNotIn('a fix for an ok step', text)
        self.assertIn('Setup is ready', shown(z.page(firstrun.PAGES.index('done'))))

    def test_next_never_disabled(self):   # never blocking: Next (Finish on the done page) stays enabled while a call is pending
        w, calls = launch(self); firstrun.open_setup(w, 'legal'); z = wiz(self, w)
        calls.hold.add('setup'); w.recheck()
        for i in range(len(firstrun.PAGES)):
            with self.subTest(firstrun.PAGES[i]):
                self.assertEqual(z.currentId(), i)
                self.assertTrue(z.button(QWizard.FinishButton if i == len(firstrun.PAGES) - 1 else QWizard.NextButton).isEnabled())
            z.next()
        self.assertEqual(z.button(QWizard.FinishButton).text(), 'Close setup')


class Legal(unittest.TestCase):
    def page(self, w): return wiz(self, w).page(firstrun.PAGES.index('legal'))

    def test_text_and_links(self):
        d = doc('setup_first.json'); d['legal']['links']['A <b>"x"'] = 'https://e/"onclick='
        w, _ = launch(self, d); p = self.page(w)
        self.assertEqual(p.notice.text(), d['legal']['text']); self.assertEqual(p.notice.textFormat(), Qt.PlainText); self.assertTrue(p.notice.wordWrap())
        self.assertTrue(p.findChild(QScrollArea).widget().isAncestorOf(p.notice))   # a long notice scrolls; the button row stays
        links = p.links.text()
        self.assertEqual(links.count('<a href'), len(d['legal']['links']))
        for x in ('A &lt;b&gt;&quot;x&quot;', 'https://e/&quot;onclick=', '>Android NDK</a>'): self.assertIn(x, links)
        self.assertNotIn('<b>"x"', links)

    def test_accept_saves_version(self):
        d = doc('setup_first.json'); d['legal']['version'] = 3
        w, calls = launch(self, d); z = wiz(self, w); b = z.button(QWizard.NextButton)
        self.assertEqual(b.text(), 'Accept and continue')
        with mock.patch.object(w, 'recheck') as again:
            b.click()
            self.assertEqual(calls.sent('config'), [['config', 'legal', '3', '--json']])
            self.assertEqual(b.text(), 'saving…'); self.assertFalse(b.isEnabled())
            self.assertTrue(until(lambda: again.called, 3000))
        self.assertTrue(until(lambda: z.currentId() == firstrun.PAGES.index('keys'), 1000))

    def test_save_fails(self):
        w, calls = launch(self, doc('setup_first.json')); calls.fail['config'] = {'timeout': 0, 'error': 'bad <version>', 'stderr': ''}
        z = wiz(self, w); p = self.page(w); b = z.button(QWizard.NextButton); b.click()
        self.assertTrue(until(lambda: 'Retry' in p.error.text(), 3000))
        self.assertIn('bad &lt;version&gt;', p.error.text())
        self.assertEqual(z.currentId(), firstrun.PAGES.index('legal')); self.assertTrue(b.isEnabled()); self.assertEqual(b.text(), 'Accept and continue')
        p.error.linkActivated.emit('retry'); self.assertEqual(len(calls.sent('config')), 2)

    def test_footer(self):
        w, _ = launch(self, doc('setup_first.json'))
        self.assertEqual(self.page(w).footer.text(), 'Skip setup closes this window. It opens again next time until you accept.')


if __name__ == '__main__': unittest.main()
