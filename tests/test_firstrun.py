# The first-run gate (gui/firstrun.py) over today's window, headless: porter's `setup --json` drawn on every launch as the Setup tab's checklist, a banner that
# names what is missing, and the wizard that opens while the legal notice is not accepted. A stand-in call_json (patched on gui.app and gui.firstrun) answers
# from tests/fixtures/bridge/setup_*.json on the next event-loop turn; the subprocess path is tests/test_bridge.py's.
import copy, json, os, re, sys, tempfile, time, unittest
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
    from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QScrollArea, QWidget, QWizard
    from gui import app, firstrun, runner, shell
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


class Calls:   # stands in for gui.runner.call_json: answers each command from self.queue's next answer, else self.answers (or self.fail), on the next turn;
    # a command in self.hold never answers; every args list is recorded
    def __init__(self, test, setup):
        self.args, self.fail, self.hold, self.queue = [], {}, set(), {}
        self.answers = {'setup': setup, 'devices': [], 'profiles': []}
        for m in (app, firstrun, shell):
            p = mock.patch.object(m, 'call_json', self); p.start(); test.addCleanup(p.stop)

    def __call__(self, parent, args, done, timeout=None):
        self.args.append(list(args)); cmd = args[0]
        if cmd in self.hold: return
        fail = self.fail.get(cmd)
        q = self.queue.get(cmd)
        obj = None if fail else {'key': args[1], 'value': args[2]} if cmd == 'config' else copy.deepcopy(q.pop(0) if q else self.answers.get(cmd))
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


HEX32 = re.compile('[0-9A-Fa-f]{32}')   # a key value's shape: no text on the keys page may carry one


class Keys(unittest.TestCase):   # the prod.keys page (03-12, D-05/D-06): porter's found files with its verdict, Browse…, a save through config keys
    OK = {'path': '~/.switch/prod.keys', 'ok': True, 'detail': 'keys up to generation 19', 'generation': 19, 'missing': []}
    BAD = {'path': '/opt/nx2a-test/old/prod.keys', 'ok': False, 'detail': 'missing header_key', 'generation': None, 'missing': ['header_key']}

    def open(self, found, **st):   # the wizard at the keys page over setup_missing.json with the keys step's found entries (and any step fields) replaced
        d = doc('setup_missing.json'); s = firstrun.step(d, 'keys'); s['found'] = copy.deepcopy(found); s.update(st)
        w, calls = launch(self, d); z = firstrun.open_setup(w, 'keys'); p = z.page(firstrun.PAGES.index('keys'))
        self.assertEqual(z.currentId(), firstrun.PAGES.index('keys'))
        for a in ('list', 'result'): self.assertIsNotNone(getattr(p, a, None), f'the keys page has no {a}')
        return w, calls, z, p

    def row(self, p, i):
        r = p.list.itemWidget(p.list.item(i)); self.assertIsNotNone(r, f'list row {i} has no row widget'); return r

    def test_candidates(self):
        w, _, z, p = self.open([self.OK, self.BAD])
        self.assertEqual(p.list.count(), 2)
        for i, e, mark, role in ((0, self.OK, '✓', 'ok'), (1, self.BAD, '✗', 'bad')):
            with self.subTest(e['path']):
                r = self.row(p, i)
                self.assertEqual(r.glyph.text(), mark); self.assertIn(firstrun.colour(r.glyph, role), r.glyph.styleSheet())
                self.assertEqual(r.path.toolTip(), e['path']); self.assertEqual(r.path.font().family(), firstrun.mono().family())
                self.assertEqual(r.detail.text(), e['detail'])
        long = '/opt/nx2a-test/' + 'deep/' * 80 + 'prod.keys'
        w, _, z, p = self.open([dict(self.OK, path=long)]); r = self.row(p, 0)
        self.assertTrue(until(lambda: '…' in r.path.text(), 1000), r.path.text())   # elided in the middle: both ends kept
        self.assertTrue(r.path.text().startswith('/opt/')); self.assertTrue(r.path.text().endswith('prod.keys')); self.assertEqual(r.path.toolTip(), long)

    def test_pick_saves(self):
        w, calls, z, p = self.open([self.OK, self.BAD])
        with mock.patch.object(w, 'recheck') as again:
            p.list.setCurrentRow(1); QTest.qWait(50)
            self.assertEqual(calls.sent('config'), [])   # a not-ok row is not saved
            p.list.setCurrentRow(0)
            self.assertEqual(calls.sent('config'), [['config', 'keys', self.OK['path'], '--json']])
            r = self.row(p, 0); self.assertEqual(r.detail.text(), 'saving…'); self.assertFalse(r.isEnabled())
            self.assertTrue(until(lambda: again.called, 3000))

    def test_bad_file_line(self):
        fix = 'Pick a prod.keys dumped from your own Switch.'
        w, _, z, p = self.open([], ok=False, path=self.BAD['path'], detail='missing header_key', fix=fix)
        self.assertEqual(p.result.text(), f"{self.BAD['path']}: missing header_key. {fix}"); self.assertEqual(p.result.textFormat(), Qt.PlainText)
        w, _, z, p = self.open([], ok=True, path=self.OK['path'], detail='keys up to generation 19', fix='')
        self.assertEqual(p.result.text(), f"{self.OK['path']}: keys up to generation 19")

    def test_no_values(self):   # porter never sends a value; even if a doc carried one in another field, the page shows only path, glyph, detail and fix
        v = 'ab' * 16   # built here: no 32-digit hex literal in this file
        w, _, z, p = self.open([dict(self.OK, value=v, header_key=v)], ok=True, path=self.OK['path'], detail='keys up to generation 19', value=v, header_key=v)
        self.assertEqual(p.list.count(), 1)
        texts = [x.text() for x in p.findChildren(QLabel)] + [x.toolTip() for x in p.findChildren(QWidget)]
        texts += [t for i in range(p.list.count()) for t in (p.list.item(i).text(), p.list.item(i).toolTip())]
        for t in texts: self.assertNotRegex(t, HEX32)

    def browse(self, p):
        b = getattr(p, 'browse', None); self.assertIsNotNone(b, 'the keys page has no Browse… button'); return b

    def test_empty(self):
        w, _, z, p = self.open([])
        empty = getattr(p, 'empty', None); self.assertIsNotNone(empty, 'the keys page has no empty-state line')
        self.assertTrue(empty.isVisibleTo(p)); self.assertEqual(empty.text(), 'No prod.keys found in the usual emulator folders. Choose your file with Browse….')
        self.assertTrue(p.list.count() == 0 or not p.list.isVisibleTo(p))
        b = self.browse(p); self.assertTrue(b.isVisibleTo(p)); self.assertTrue(b.isEnabled())
        w, _, z, p = self.open([self.OK]); self.assertFalse(p.empty.isVisibleTo(p)); self.assertTrue(p.list.isVisibleTo(p))

    def test_browse_saves(self):
        w, calls, z, p = self.open([self.OK]); b = self.browse(p); mine = '/opt/nx2a-test/mine/prod.keys'
        with mock.patch.object(firstrun.QFileDialog, 'getOpenFileName', return_value=('', '')): b.click()
        QTest.qWait(50); self.assertEqual(calls.sent('config'), [])   # cancelled: nothing sent
        with mock.patch.object(firstrun.QFileDialog, 'getOpenFileName', return_value=(mine, 'prod.keys (*.keys)')), mock.patch.object(w, 'recheck') as again:
            b.click()
            self.assertEqual(calls.sent('config'), [['config', 'keys', mine, '--json']])
            self.assertEqual(b.text(), 'saving…'); self.assertFalse(b.isEnabled())
            self.assertTrue(until(lambda: again.called, 3000))
        self.assertEqual(b.text(), 'Browse…'); self.assertTrue(b.isEnabled())

    def test_save_fails(self):
        w, calls, z, p = self.open([self.OK]); calls.fail['config'] = {'timeout': 0, 'error': 'cannot <save>', 'stderr': ''}
        with mock.patch.object(w, 'recheck') as again:
            p.list.setCurrentRow(0)
            err = lambda: getattr(p, 'error', None)
            self.assertTrue(until(lambda: err() is not None and 'Retry' in err().text(), 3000), 'no failure line with Retry under the list')
            self.assertIn('cannot &lt;save&gt;', p.error.text())
            r = self.row(p, 0); self.assertTrue(r.isEnabled()); self.assertEqual(r.detail.text(), self.OK['detail'])
            self.assertEqual(z.currentId(), firstrun.PAGES.index('keys')); again.assert_not_called()
            p.error.linkActivated.emit('retry')
            self.assertEqual(calls.sent('config'), [['config', 'keys', self.OK['path'], '--json']] * 2)
            b = self.browse(p)
            with mock.patch.object(firstrun.QFileDialog, 'getOpenFileName', return_value=('/opt/nx2a-test/mine/prod.keys', '')): b.click()
            self.assertTrue(until(lambda: b.isEnabled() and b.text() == 'Browse…', 3000)); again.assert_not_called()

    def test_next_enabled(self):   # never blocking: whatever porter says of the keys, and while a save is pending
        for st in ({'ok': False, 'detail': 'missing header_key', 'path': self.BAD['path']}, {'ok': True, 'detail': 'keys up to generation 19', 'path': self.OK['path']}):
            with self.subTest(st['ok']):
                w, calls, z, p = self.open([self.OK, self.BAD], **st); calls.hold.add('config')
                self.assertTrue(z.button(QWizard.NextButton).isEnabled())
                p.list.setCurrentRow(0); self.assertEqual(len(calls.sent('config')), 1)
                self.assertTrue(z.button(QWizard.NextButton).isEnabled())
                b = self.browse(p)
                with mock.patch.object(firstrun.QFileDialog, 'getOpenFileName', return_value=('/opt/nx2a-test/mine/prod.keys', '')): b.click()
                self.assertTrue(z.button(QWizard.NextButton).isEnabled()); self.assertTrue(p.isComplete())


STEPS = ('1. On the device, open Settings › About and tap Build number seven times. 2. Open Settings › System › Developer options and turn on USB debugging. '
         '3. Connect it by USB and tap Allow on the "Allow USB debugging?" prompt.')


def dev(serial, state, fix='', model=None):   # one devices --json row as porter prints it
    return {'serial': serial, 'state': state, 'info': f'model:{model} device:x' if model else '', 'detail': state, 'fix': fix}


class Device(unittest.TestCase):   # the device page (D-15, DEV-01): devices --json asked again from each answer while the page shows; each row's adb state and porter's fix
    MS = 300

    def setUp(self): p = mock.patch.object(firstrun, 'POLL_MS', self.MS, create=True); p.start(); self.addCleanup(p.stop)

    def open(self, *answers, hold=False):   # the wizard at the device page; devices --json answers each of `answers` in turn, then []
        w, calls = launch(self); calls.queue['devices'] = [copy.deepcopy(a) for a in answers]
        if hold: calls.hold.add('devices')
        self.base = len(calls.sent('devices'))   # today's Port tab asks once on its own
        z = firstrun.open_setup(w, 'device'); p = z.page(firstrun.PAGES.index('device'))
        self.assertEqual(z.currentId(), firstrun.PAGES.index('device'))
        return w, calls, z, p

    def polls(self, calls): return len(calls.sent('devices')) - self.base

    def row(self, p, i):
        r = p.list.itemWidget(p.list.item(i)); self.assertIsNotNone(r, f'list row {i} has no row widget'); return r

    def test_polls_while_current(self):
        w, calls, z, p = self.open([], [], [])
        self.assertTrue(until(lambda: self.polls(calls) >= 1, 1000)); self.assertEqual(calls.sent('devices')[-1], ['devices', '--json'])
        QTest.qWait(self.MS // 3); self.assertEqual(self.polls(calls), 1)   # the next one waits POLL_MS after the answer
        self.assertTrue(until(lambda: self.polls(calls) >= 2, 3000))
        z.back(); n = self.polls(calls); QTest.qWait(self.MS * 3)
        self.assertLessEqual(self.polls(calls), n + 1)   # at most the one already scheduled when Back was pressed... and then nothing
        n = self.polls(calls); QTest.qWait(self.MS * 3); self.assertEqual(self.polls(calls), n)
        z.next(); self.assertTrue(until(lambda: self.polls(calls) > n, 1000))   # back on the page: polling again
        z.next(); self.assertEqual(z.currentId(), firstrun.PAGES.index('done'))
        QTest.qWait(self.MS); n = self.polls(calls); QTest.qWait(self.MS * 3); self.assertEqual(self.polls(calls), n)
        w, calls, z, p = self.open([], [])
        self.assertTrue(until(lambda: self.polls(calls) >= 1, 1000)); z.close()
        QTest.qWait(self.MS); n = self.polls(calls); QTest.qWait(self.MS * 3); self.assertEqual(self.polls(calls), n)

    def test_no_stacking(self):   # a stalled adb: one call outstanding, never another on top
        w, calls, z, p = self.open(hold=True)
        self.assertTrue(until(lambda: self.polls(calls) >= 1, 1000)); QTest.qWait(self.MS * 4)
        self.assertEqual(self.polls(calls), 1)
        self.assertEqual(p.empty.text(), 'Looking again every few seconds…'); self.assertTrue(p.empty.isVisibleTo(p))

    def test_rows(self):
        rows = [dev('R5CT1', 'device', model='Lenovo_TB320FC'), dev('R5CT2', 'unauthorized', 'Unlock the device and tap Allow on the USB debugging prompt.'),
                dev('R5CT3', 'offline', 'Unplug the cable and plug it in again, or try another cable or USB port.'),
                dict(dev('R5CT4', 'no permissions', 'Run sudo apt install android-sdk-platform-tools-common, then unplug the device and plug it in again.'),
                     detail='no permissions (user in plugdev group; are your udev rules wrong?)'),
                dev('R5CT5', 'authorizing', 'Wait a moment.')]
        w, calls, z, p = self.open(rows)
        self.assertTrue(until(lambda: p.list.count() == 5, 2000))
        for i, (r, mark, name) in enumerate(zip(rows, '✓✗✗✗▶', ('Lenovo TB320FC', 'R5CT2', 'R5CT3', 'R5CT4', 'R5CT5'))):
            with self.subTest(r['state']):
                x = self.row(p, i)
                self.assertEqual(x.glyph.text(), mark); self.assertEqual(x.name.text(), name)
                self.assertEqual(x.detail.text(), r['detail']); self.assertEqual(x.detail.font().family(), firstrun.mono().family())
                self.assertEqual(x.fix.text(), r['fix']); self.assertTrue(x.fix.wordWrap()); self.assertTrue(x.fix.textInteractionFlags() & Qt.TextSelectableByMouse)
                for lab in (x.name, x.detail, x.fix): self.assertEqual(lab.textFormat(), Qt.PlainText)   # text a USB device controls (T-03-31)
        self.assertFalse(p.empty.isVisibleTo(p))

    def test_live_change(self):
        w, calls, z, p = self.open([dev('R5CT1', 'unauthorized', 'Unlock the device and tap Allow on the USB debugging prompt.')], [dev('R5CT1', 'device')])
        self.assertTrue(until(lambda: p.list.count() == 1 and self.row(p, 0).glyph.text() == '✗', 2000))
        self.assertTrue(until(lambda: self.row(p, 0).glyph.text() == '✓', 3000))

    def test_empty_and_skip(self):
        w, calls, z, p = self.open([])
        self.assertTrue(until(lambda: p.empty.text() == 'No device found yet. Looking again every few seconds…', 2000))
        self.assertTrue(p.empty.isVisibleTo(p)); self.assertEqual(z.button(QWizard.NextButton).text(), 'Skip: install later')
        self.assertTrue(z.button(QWizard.NextButton).isEnabled())
        w, calls, z, p = self.open([dev('R5CT1', 'device')])
        self.assertTrue(until(lambda: z.button(QWizard.NextButton).text() == 'Next', 2000))

    def test_failure_keeps_polling(self):
        w, calls, z, p = self.open(); calls.fail['devices'] = {'timeout': 0, 'error': 'adb not found: install <adb>', 'stderr': ''}
        self.assertTrue(until(lambda: 'adb not found: install <adb>' in p.empty.text(), 2000)); self.assertTrue(p.empty.isVisibleTo(p))
        n = self.polls(calls); self.assertTrue(until(lambda: self.polls(calls) > n, 3000))

    def test_instructions(self):
        w, calls, z, p = self.open()
        self.assertIn(STEPS, shown(p)); self.assertIn('Connect your Android device', shown(p))

    def test_pick_saves(self):   # several devices ready: the selected one is saved; one: nothing to pick
        two = [dev('R5CT1', 'device'), dev('R5CT2', 'device'), dev('R5CT3', 'unauthorized', 'Unlock the device and tap Allow on the USB debugging prompt.')]
        w, calls, z, p = self.open(); calls.answers['devices'] = two
        self.assertTrue(until(lambda: p.list.count() == 3, 2000))
        p.list.setCurrentRow(2); QTest.qWait(50); self.assertEqual(calls.sent('config'), [])   # not in device state: not saved
        p.list.setCurrentRow(1); self.assertEqual(calls.sent('config'), [['config', 'device', 'R5CT2', '--json']])
        calls.answers['devices'] = two + [dev('R5CT4', 'offline')]   # a redraw keeps the choice and saves nothing again
        self.assertTrue(until(lambda: p.list.count() == 4, 3000)); QTest.qWait(50)
        self.assertEqual([p.list.itemWidget(it).r['serial'] for it in p.list.selectedItems()], ['R5CT2']); self.assertEqual(len(calls.sent('config')), 1)
        w, calls, z, p = self.open(); calls.answers['devices'] = [dev('R5CT1', 'device'), dev('R5CT3', 'offline')]
        self.assertTrue(until(lambda: p.list.count() == 2, 2000))
        p.list.setCurrentRow(0); QTest.qWait(50); self.assertEqual(calls.sent('config'), [])

    def test_pick_fails(self):
        w, calls, z, p = self.open(); calls.answers['devices'] = [dev('R5CT1', 'device'), dev('R5CT2', 'device')]
        calls.fail['config'] = {'timeout': 0, 'error': 'cannot <save>', 'stderr': ''}
        self.assertTrue(until(lambda: p.list.count() == 2, 2000)); p.list.setCurrentRow(0)
        self.assertTrue(until(lambda: 'cannot <save>' in p.error.text(), 2000)); self.assertEqual(p.error.textFormat(), Qt.PlainText)


class Done(unittest.TestCase):   # the last page (D-20, D-28): a summary per step, porter's notes, the games that play today, Add to app menu, Port a game
    PROFILES = [{'id': '0100A', 'name': 'Zeta Quest', 'status': 'playable'}, {'id': '0100B', 'name': 'Alpha Run', 'status': 'playable'},
                {'id': '0100C', 'name': 'Work In Progress', 'status': 'wip'}]

    def open(self, d=None, profiles=(), win=None):   # the wizard at the done page over `d`; profiles --json answers `profiles`
        w, calls = (win or launch)(self, d or doc()); calls.answers['profiles'] = copy.deepcopy(list(profiles)); self.base = len(calls.sent('profiles'))   # today's Games tab asks too
        z = firstrun.open_setup(w, 'done'); p = z.page(firstrun.PAGES.index('done'))
        self.assertEqual(z.currentId(), firstrun.PAGES.index('done'))
        return w, calls, z, p

    def lines(self, p): return [(x.glyph.text(), x.text.text()) for x in p.lines]

    def test_summary(self):
        d = doc('setup_missing.json'); d['notes'] = ['No adb yet: port now, install later.']
        w, calls, z, p = self.open(d); got = self.lines(p)
        self.assertEqual(len(got), len(d['steps']) + 1)
        for (mark, text), st in zip(got, d['steps']):
            with self.subTest(st['id']): self.assertEqual(mark, '✓' if st['ok'] else '✗'); self.assertIn(st['detail'], text)
        self.assertEqual(got[-1], ('!', 'No adb yet: port now, install later.'))
        self.assertIn(firstrun.colour(p, 'note'), p.lines[-1].glyph.styleSheet())
        for x in p.lines: self.assertTrue(x.text.wordWrap()); self.assertEqual(x.text.textFormat(), Qt.PlainText)
        self.assertEqual(p.head.text(), 'Setup is not finished')
        w, calls, z, p = self.open(); self.assertEqual(p.head.text(), 'Setup is ready')

    def test_no_device_note(self):   # what the device page last saw in this wizard; a wizard that never polled says nothing of devices
        note = 'No device yet: port now, install later.'
        w, calls, z, p = self.open(); self.assertNotIn(note, [t for _, t in self.lines(p)])
        for rows, want in (([], True), ([dev('R5CT1', 'unauthorized')], True), ([dev('R5CT1', 'device')], False)):
            with self.subTest(rows=rows):
                w, calls = launch(self); calls.answers['devices'] = rows
                z = firstrun.open_setup(w, 'device'); dp = z.page(firstrun.PAGES.index('device'))
                self.assertTrue(until(lambda: dp.rows is not None, 2000)); z.next()
                p = z.page(firstrun.PAGES.index('done')); self.assertEqual(note in [t for _, t in self.lines(p)], want)

    def test_playable(self):
        w, calls, z, p = self.open(profiles=self.PROFILES)
        self.assertEqual(calls.sent('profiles')[self.base:], [['profiles', '--json']])
        self.assertTrue(until(lambda: p.playable.isVisibleTo(p), 2000))
        self.assertEqual(p.playable.text(), 'Alpha Run\nZeta Quest'); self.assertEqual(p.playable.textFormat(), Qt.PlainText)
        self.assertTrue(p.games.isVisibleTo(p)); self.assertEqual(p.games.text(), 'Games that play today')
        for profiles, fail in (([], None), (self.PROFILES[2:], None), (self.PROFILES, {'timeout': 20, 'error': '', 'stderr': ''})):
            with self.subTest(profiles=profiles, fail=fail):
                w, calls = launch(self)
                if fail: calls.fail['profiles'] = fail
                w, calls, z, p = self.open(win=lambda _t, _d: (w, calls), profiles=profiles)
                self.assertTrue(until(lambda: len(calls.sent('profiles')) == self.base + 1, 1000)); QTest.qWait(50)
                self.assertFalse(p.playable.isVisibleTo(p)); self.assertFalse(p.games.isVisibleTo(p))
                self.assertIn('Setup is ready', shown(p)); self.assertTrue(p.port.isVisibleTo(p))   # the summary and Port a game still show

    def test_add_to_menu_offer(self):
        w, calls, z, p = self.open(); self.assertFalse(p.menu.isVisibleTo(p))
        d = doc(); d['desktop']['offer'] = True
        w, calls, z, p = self.open(d); self.assertTrue(p.menu.isVisibleTo(p)); self.assertEqual(p.menu.text(), 'Add to app menu')
        QTest.qWait(50); self.assertEqual(calls.sent('desktop-entry'), [])   # nothing written before the press (T-03-33)
        calls.answers['desktop-entry'] = {'path': '/home/t/.local/share/applications/nx2android.desktop', 'icon': '/x.png', 'exec': '/opt/nx2android/nx2android'}
        calls.hold.add('desktop-entry'); p.menu.click()
        self.assertEqual(calls.sent('desktop-entry'), [['desktop-entry', '--install', '--json']])
        self.assertEqual(p.menu.text(), 'saving…'); self.assertFalse(p.menu.isEnabled())
        w, calls, z, p = self.open(d); calls.answers['desktop-entry'] = {'path': '/x.desktop', 'icon': '/x.png', 'exec': '/x'}; p.menu.click()
        self.assertTrue(until(lambda: p.menu_result.text() == 'Added to the app menu.', 2000)); self.assertTrue(p.menu.isEnabled())
        w, calls, z, p = self.open(d); calls.fail['desktop-entry'] = {'timeout': 0, 'error': 'cannot write <dir>', 'stderr': ''}; p.menu.click()
        self.assertTrue(until(lambda: 'cannot write <dir>' in p.menu_result.text(), 2000)); self.assertEqual(p.menu_result.textFormat(), Qt.PlainText)
        self.assertEqual(p.menu.text(), 'Add to app menu'); self.assertTrue(p.menu.isEnabled())

    def test_port_a_game(self):
        w, calls, z, p = self.open(); self.assertTrue(p.port.isVisibleTo(p)); self.assertEqual(p.port.text(), 'Port a game')
        self.assertTrue(p.port.isDefault()); self.assertGreaterEqual(p.port.minimumHeight(), 36); self.assertTrue(p.port.font().bold())
        with mock.patch.object(w, 'port_a_game') as go:
            p.port.click(); go.assert_called_once_with()
        self.assertTrue(until(lambda: not z.isVisible(), 1000)); self.assertIsNone(gate(self, w).wizard)
        def on_shell(test, d):
            c = Calls(test, d); s = shell.Shell(); test.addCleanup(s.deleteLater); until(lambda: s.first_run.doc is not None, 3000); return s, c
        w, calls, z, p = self.open(win=on_shell)
        self.assertFalse(hasattr(w, 'port_a_game')); self.assertFalse(p.port.isVisibleTo(p))

    def test_close_setup(self):
        w, calls, z, p = self.open(); b = z.button(QWizard.FinishButton)
        self.assertEqual(b.text(), 'Close setup'); b.click()
        self.assertTrue(until(lambda: not z.isVisible(), 1000)); self.assertIsNone(gate(self, w).wizard)


MB = 2**20
FAKE = str(FIXTURES / 'fake_porter.py')


def gone(pid, s=5):   # the process has exited (tests/test_bridge.py's check)
    end = time.time() + s
    while time.time() < end:
        if os.name == 'nt': here = str(pid) in __import__('subprocess').run(['tasklist', '/FI', f'PID eq {pid}', '/NH'], capture_output=True, text=True).stdout
        else:
            try: os.kill(pid, 0); here = True
            except ProcessLookupError: here = False
            except PermissionError: here = True
        if not here: return True
        time.sleep(0.1)
    return False


def reap(pid):
    try: os.kill(pid, 9)
    except OSError: pass


class Progress(unittest.TestCase):   # D-26: the progress line both views show
    EV = {'ev': 'progress', 'name': 'Android NDK r27c', 'step': 'downloading', 'done': 412 * MB, 'total': 781 * MB, 'unit': 'B', 'frac': 0.53, 'rate': int(6.1 * MB), 'eta': 61}

    def test_line(self):
        self.assertEqual(firstrun.progress_line(self.EV, '[2/3]'), '[2/3] Android NDK r27c · downloading · 412.0 MB / 781.0 MB · 6.1 MB/s · 1 min left')

    def test_drops_empty(self):
        ev = {k: v for k, v in self.EV.items() if k not in ('rate', 'eta')}
        self.assertEqual(firstrun.progress_line(ev), 'Android NDK r27c · downloading · 412.0 MB / 781.0 MB')
        self.assertEqual(firstrun.progress_line({'ev': 'progress', 'name': 'x', 'step': ''}, '[1/1]'), '[1/1] x')

    def test_time_left(self):
        for eta, want in ((None, ''), (30, 'less than a minute left'), (600, '10 min left'), (7500, '2 h 5 min left')):
            with self.subTest(eta=eta): self.assertEqual(firstrun.time_left(eta), want)


def tools_doc(**over):   # setup_missing.json with the NDK and .NET not found and porter offering both (a pinned NDK size, .NET's 0)
    d = doc('setup_missing.json'); st = next(x for x in d['steps'] if x['id'] == 'tools'); ndk, net, adb = st['items']
    ndk['download'] = {'version': 'r27c', 'size': 700 * MB}
    net.update(ok=False, detail='not found', fix='Download missing tools, or set dotnet', path='', source='', version='', download={'version': '10.0', 'size': 0})
    st['downloadable'] = ['Android NDK', '.NET SDK']
    for k, v in over.items(): st[k] = v
    return d


def item(d, name): return next(it for it in next(x for x in d['steps'] if x['id'] == 'tools')['items'] if it['name'] == name)


class Tools(unittest.TestCase):   # the tools page (D-07, D-21, D-23..D-26): Download all missing / Cancel on the window's own fetch run, Use my own…, Prepare .NET tools
    def open(self, d=None):   # the wizard at the tools page over `d`
        w, calls = launch(self, d or tools_doc()); z = firstrun.open_setup(w, 'tools'); p = z.page(firstrun.PAGES.index('tools'))
        self.assertEqual(z.currentId(), firstrun.PAGES.index('tools'))
        return w, calls, z, p

    def stand_in(self, *opts):   # the window's long runs go to the stand-in porter
        keep = runner.PORTER; self.addCleanup(setattr, runner, 'PORTER', keep); runner.PORTER = [FAKE, *opts, '--']

    def finish(self, w):   # a run a test left going
        if w.fetch.running(): w.fetch.stop(); until(lambda: not w.fetch.running(), 10000)

    def test_download_starts_run(self):
        w, calls, z, p = self.open()
        self.assertTrue(p.dl.isVisibleTo(p)); self.assertRegex(p.dl.text(), r'^Download all missing \(about \d+\.\d (MB|GB)\)$')
        self.assertTrue(p.dl.isDefault()); self.assertGreaterEqual(p.dl.minimumHeight(), 36); self.assertTrue(p.dl.font().bold())
        with mock.patch.object(w.fetch, 'start') as start, mock.patch.object(app, 'QMessageBox', side_effect=AssertionError('a dialog')):
            p.dl.click()
        start.assert_called_once_with(['tools', '--download', '--progress', 'json'])
        t = p.table; self.assertEqual(t.columnCount(), 6); self.assertEqual(t.rowCount(), 3)
        self.assertEqual([t.item(i, 0).text() for i in range(3)], ['✗', '✗', '✓'])
        self.assertEqual((t.item(0, 4).text(), t.item(1, 4).text(), t.item(2, 4).text()), ('700.0 MB', 'about 200 MB', ''))
        self.assertEqual((t.item(2, 2).text(), t.item(2, 3).text()), ('36.0.0', 'PATH'))

    def test_hidden_when_nothing(self):
        w, calls, z, p = self.open(doc())
        self.assertFalse(p.dl.isVisibleTo(p)); self.assertIn('Every tool is here.', shown(p))
        w, calls, z, p = self.open(); self.assertNotIn('Every tool is here.', shown(p))

    def test_cancel(self):   # a real stand-in run: Cancel stops its whole tree, "cancelled" only once it is gone
        self.stand_in('--tree'); w, calls, z, p = self.open(); self.addCleanup(self.finish, w)
        evs = []; w.fetch.event.connect(evs.append); p.dl.click()
        self.assertTrue(until(lambda: any(e.get('ev') == 'pids' for e in evs), 10000))
        pids = next(e for e in evs if e.get('ev') == 'pids'); self.addCleanup(reap, pids['detached']); self.addCleanup(reap, pids['child'])
        self.assertEqual(p.dl.text(), 'Cancel download'); self.assertFalse(p.dl.isDefault())
        self.assertIn('[1/1] waiting', p.status.text())
        p.dl.click(); self.assertEqual(p.status.text(), 'stopping…')
        self.assertTrue(until(lambda: not w.fetch.running(), 10000))
        self.assertEqual(p.status.text(), 'cancelled. Download all missing resumes where it stopped.')
        self.assertTrue(gone(pids['child'])); self.assertTrue(p.dl.text().startswith('Download all missing'))

    def test_failure_inline(self):
        w, calls, z, p = self.open(); log = os.path.join(HOME, 'tools.log')
        with mock.patch.object(w.fetch, 'start'): p.dl.click()
        w.fetch.event.emit({'ev': 'log', 'path': log}); w.fetch.event.emit({'ev': 'error', 'msg': 'bad <thing> & co', 'type': 'FetchError', 'log': log})
        w.fetch.finished.emit(1); t = p.status.text()
        self.assertIn('bad &lt;thing&gt; &amp; co', t); self.assertNotIn('<thing>', t); self.assertIn('<a href="log">Open log</a>', t)
        self.assertIn(firstrun.colour(p, 'bad'), t); self.assertTrue(p.status.wordWrap())
        self.assertNotEqual(p.status.font().family(), firstrun.mono().family())
        with mock.patch.object(firstrun, 'QDesktopServices') as ds: p.status.linkActivated.emit('log')
        self.assertEqual(Path(ds.openUrl.call_args[0][0].toLocalFile()), Path(log))
        a, b = 'a' * 64, 'b' * 64; msg = f'android-ndk-r27c.zip: its sha256 is {a}, not the expected {b}'
        with mock.patch.object(w.fetch, 'start'): p.dl.click()
        w.fetch.event.emit({'ev': 'error', 'msg': msg, 'type': 'FetchError', 'log': log}); w.fetch.finished.emit(1)
        self.assertIn(a, p.status.text()); self.assertIn(b, p.status.text()); self.assertEqual(p.status.font().family(), firstrun.mono().family())


    def buttons(self, p, row): w = p.table.cellWidget(row, 5); return {b.text(): b for b in w.findChildren(QPushButton)} if w else {}

    def test_second_lines(self):
        d = tools_doc(); note = 'community r27c build (HomuHomu833), clang 18.0.3: not the build the titles were tested with'; item(d, 'Android NDK')['note'] = note
        w, calls, z, p = self.open(d); ndk, net = p.table.cellWidget(0, 1), p.table.cellWidget(1, 1)
        self.assertIsNotNone(ndk, 'the Tool column has no cell widget')
        self.assertIn(note, ndk.note.text()); self.assertIn('!', ndk.note.text()); self.assertIn(firstrun.colour(p, 'note'), ndk.note.text())
        self.assertTrue(ndk.note.isVisibleTo(p)); self.assertTrue(ndk.note.wordWrap())
        self.assertEqual(net.fix.text(), item(d, '.NET SDK')['fix']); self.assertTrue(net.fix.isVisibleTo(p))
        self.assertTrue(net.fix.textInteractionFlags() & Qt.TextSelectableByMouse); self.assertFalse(net.note.isVisibleTo(p))
        self.assertFalse(p.table.cellWidget(2, 1).fix.isVisibleTo(p))   # an ok row shows no fix

    def test_use_own_ndk(self):
        w, calls, z, p = self.open(); calls.hold.add('config'); b = self.buttons(p, 0)['Use my own…']
        with mock.patch.object(firstrun.QFileDialog, 'getExistingDirectory', return_value='/opt/my-ndk'): b.click()
        self.assertEqual(calls.sent('config'), [['config', 'ndk', '/opt/my-ndk', '--json']])
        self.assertEqual(b.text(), 'saving…'); self.assertFalse(b.isEnabled())
        w, calls, z, p = self.open(); n = len(calls.sent('setup'))
        with mock.patch.object(firstrun.QFileDialog, 'getExistingDirectory', return_value='/opt/my-ndk'): self.buttons(p, 0)['Use my own…'].click()
        self.assertTrue(until(lambda: len(calls.sent('setup')) > n, 2000))   # porter's verdict redraws the row
        w, calls, z, p = self.open(); calls.fail['config'] = {'timeout': 0, 'error': 'no NDK in <dir>', 'stderr': ''}
        with mock.patch.object(firstrun.QFileDialog, 'getExistingDirectory', return_value='/x'): self.buttons(p, 0)['Use my own…'].click()
        self.assertTrue(until(lambda: 'no NDK in &lt;dir&gt;' in p.status.text(), 2000))
        with mock.patch.object(firstrun.QFileDialog, 'getExistingDirectory', return_value=''): self.buttons(p, 0)['Use my own…'].click()   # cancelled: nothing sent
        self.assertEqual(len(calls.sent('config')), 1)

    def test_use_own_dotnet_adb(self):
        d = tools_doc(); item(d, 'adb').update(ok=False, detail='not found', fix='Download missing tools, or set adb', path='')
        for row, key in ((1, 'dotnet'), (2, 'adb')):
            with self.subTest(key):
                w, calls, z, p = self.open(copy.deepcopy(d)); calls.hold.add('config')
                with mock.patch.object(firstrun.QFileDialog, 'getOpenFileName', return_value=(f'/opt/{key}', '')): self.buttons(p, row)['Use my own…'].click()
                self.assertEqual(calls.sent('config'), [['config', key, f'/opt/{key}', '--json']])

    def test_arm64_adb(self):   # D-25: no adb build for Linux arm64; porter sends the distribution's command
        d = doc(); item(d, 'adb').update(ok=False, detail='not found', fix='Install adb from your distribution:', path='', command='sudo apt install adb')
        w, calls, z, p = self.open(d); bs = self.buttons(p, 2)
        self.assertEqual(set(bs), {'Copy command', 'Re-check', 'Use my own…'}); self.assertFalse(p.dl.isVisibleTo(p))
        cell = p.table.cellWidget(2, 1); self.assertEqual(cell.command.text(), 'sudo apt install adb'); self.assertEqual(cell.command.font().family(), firstrun.mono().family())
        bs['Copy command'].click(); self.assertEqual(QApplication.clipboard().text(), 'sudo apt install adb')
        n = len(calls.sent('setup')); bs['Re-check'].click(); self.assertTrue(until(lambda: len(calls.sent('setup')) > n, 2000))

    def test_prepare_chain(self):   # D-24: a download this page started ends 0, then Prepare .NET tools runs on the same fetch
        w, calls, z, p = self.open()
        with mock.patch.object(w.fetch, 'start') as start:
            p.dl.click(); w.fetch.finished.emit(0)
            self.assertEqual(start.call_args_list, [mock.call(['tools', '--download', '--progress', 'json'])])   # the next turn, not inside finished
            self.assertTrue(until(lambda: start.call_count == 2, 1000))
            self.assertEqual(start.call_args, mock.call(['tools', '--prepare', '--progress', 'json']))
            w.fetch.finished.emit(0)
        self.assertEqual(firstrun.PREPARED, '.NET tools are ready.'); self.assertEqual(p.status.text(), firstrun.PREPARED)
        QTest.qWait(50); self.assertEqual(start.call_count, 2)   # no chain after a Prepare
        self.stand_in('--tree'); self.addCleanup(self.finish, w); evs = []; w.fetch.event.connect(evs.append); p.prepare()
        self.assertTrue(until(lambda: any(e.get('ev') == 'pids' for e in evs), 10000))
        pids = next(e for e in evs if e.get('ev') == 'pids'); self.addCleanup(reap, pids['detached']); self.addCleanup(reap, pids['child'])
        self.assertEqual(p.dl.text(), 'Cancel .NET preparation'); p.dl.click()
        self.assertTrue(until(lambda: not w.fetch.running(), 10000)); self.assertTrue(gone(pids['child']))

    def test_no_prepare_while_quitting(self):   # WR-05: Stop and quit as the download ends 0: no Prepare starts on the closing window
        w, calls, z, p = self.open()
        with mock.patch.object(w.fetch, 'start') as start:
            p.dl.click(); w.quitting = True; w.fetch.finished.emit(0); QTest.qWait(50)
            self.assertEqual(start.call_args_list, [mock.call(['tools', '--download', '--progress', 'json'])])
            p.prepare(); QTest.qWait(50); self.assertEqual(start.call_count, 1)   # nor from the button

    def test_prepare_button(self):   # .NET already here and nothing running: its row offers Prepare .NET tools
        w, calls, z, p = self.open(doc()); b = self.buttons(p, 1).get('Prepare .NET tools'); self.assertIsNotNone(b)
        self.assertNotIn('Prepare .NET tools', self.buttons(p, 0))
        with mock.patch.object(w.fetch, 'start') as start: b.click()
        start.assert_called_once_with(['tools', '--prepare', '--progress', 'json'])

    def test_prepare_failure_is_note(self):
        w, calls, z, p = self.open(doc()); log = os.path.join(HOME, 'prepare.log')
        with mock.patch.object(w.fetch, 'start'): p.prepare()
        w.fetch.event.emit({'ev': 'error', 'msg': 'NuGet restore failed: <offline>', 'type': 'ToolError', 'log': log}); w.fetch.finished.emit(1)
        t = p.status.text()
        self.assertIn('!', t); self.assertIn(firstrun.colour(p, 'note'), t); self.assertNotIn(firstrun.colour(p, 'bad'), t)
        self.assertIn('NuGet restore failed: &lt;offline&gt;', t); self.assertIn('<a href="log">Open log</a>', t)
        self.assertTrue(z.button(QWizard.NextButton).isEnabled()); self.assertTrue(p.isComplete())


if __name__ == '__main__': unittest.main()
