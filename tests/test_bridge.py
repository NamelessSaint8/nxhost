# The GUI side of the bridge (gui/runner.py, gui/app.py), headless (QT_QPA_PLATFORM=offscreen): a failed run shows its cause and opens its log,
# Cancel stops the whole tree and says "cancelled" only once it is gone, closing the window mid-run asks first. A stand-in porter
# (tests/fixtures/bridge/fake_porter.py, via runner.PORTER) plays the long runs; the Errors tests run the real porter on an empty folder.
import json, os, re, subprocess, sys, tempfile, time, unittest
from pathlib import Path
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
REPO = Path(__file__).resolve().parent.parent
FAKE = str(REPO / 'tests/fixtures/bridge/fake_porter.py')
sys.path.insert(0, str(REPO))

# a declared floor, not a missing module, so it skips in CI too: PySide6 6.12's refcount bug on True aborts 3.11
OLD = sys.version_info < (3, 12)
MISSING = None
for _m in () if OLD else ('PySide6.QtWidgets', 'lz4.block', 'capstone'):
    try: __import__(_m)
    except ModuleNotFoundError:
        if os.environ.get('CI'): raise   # CI installs the lock: a missing module there is a failure
        MISSING = MISSING or _m.split('.')[0]

HOME = tempfile.mkdtemp()
if not (OLD or MISSING):
    from PySide6.QtTest import QSignalSpy, QTest
    from PySide6.QtCore import QProcess
    from PySide6.QtWidgets import QApplication, QMessageBox
    from gui import app, firstrun, runner
    from porter import paths
APP = None


def setUpModule():
    global APP
    if OLD: raise unittest.SkipTest('the GUI needs Python 3.12+ (PySide6 6.12 refcount bug on 3.11)')
    if MISSING: raise unittest.SkipTest(f'{MISSING} is not installed (python -m pip install -r requirements.txt)')
    os.environ['NX2A_HOME'] = HOME   # here, not at import: discovery imports other test modules that set their own
    APP = QApplication.instance() or QApplication([])
    APP.setQuitOnLastWindowClosed(False)   # the Close tests close windows; the module's loop goes on


def wait(signal, ms):   # the first emission's arguments, or None
    spy = QSignalSpy(signal)
    return spy.at(0) if spy.count() or spy.wait(ms) else None


def until(pred, ms):   # spin the event loop until pred() holds
    end = time.time() + ms / 1000
    while not pred() and time.time() < end: QTest.qWait(20)
    return pred()


def window(test):   # a Window whose start-up one-shots (doctor, devices, profiles) have answered: one destroyed mid-call is noise
    w = app.Window(); test.addCleanup(w.deleteLater)
    settled = lambda: until(lambda: all(p.state() == QProcess.NotRunning for p in w.findChildren(QProcess)), 30000)
    settled(); test.addCleanup(settled)   # and again before it goes (a failed download re-runs doctor)
    return w


def reap(pid):   # a test's leftover process (the detached one)
    try: os.kill(pid, 9)
    except OSError: pass


def alive(pid):
    if os.name == 'nt': return str(pid) in subprocess.run(['tasklist', '/FI', f'PID eq {pid}', '/NH'], capture_output=True, text=True).stdout
    try: os.kill(pid, 0); return True
    except ProcessLookupError: return False
    except PermissionError: return True


def gone(pid, s=5):
    end = time.time() + s
    while time.time() < end:
        if not alive(pid): return True
        time.sleep(0.1)
    return False


class Errors(unittest.TestCase):
    def setUp(self):
        keep = runner.PORTER; self.addCleanup(setattr, runner, 'PORTER', keep)

    def test_failed_port_shows_cause_and_log(self):
        real = runner.PORTER; runner.PORTER = [FAKE, '--']   # WR-06: the stand-in answers the start-up devices call, so no real adb server starts
        w = window(self); runner.PORTER = real
        port = w.port; game = tempfile.mkdtemp()
        port.run(['port', game, '--progress', 'json'])
        got = wait(port.porter.finished, 60000)
        self.assertEqual(got, [1])
        self.assertIn('prod.keys', port.step.text())
        self.assertNotIn('the log says why', port.step.text())
        self.assertTrue(port.log_btn.isEnabled())
        with mock.patch.object(app, 'QDesktopServices') as ds:
            port.log_btn.click()
        url = ds.openUrl.call_args[0][0]
        p = Path(url.toLocalFile())
        self.assertTrue(p.is_file(), p)
        self.assertEqual(p.parent, Path(HOME) / 'logs')

    def stand_in(self, *opts):   # a Window whose start-up one-shots the stand-in answers; then runner.PORTER is fake_porter.py with opts
        runner.PORTER = [FAKE, '--']; w = window(self)
        runner.PORTER = [FAKE, *opts, '--']
        return w

    def card(self, w):   # inspect an empty folder; the card once the call has answered
        w.port.folder.setText(tempfile.mkdtemp()); w.port.inspect()
        self.assertTrue(until(lambda: 'Reading' not in w.port.card.text(), 10000), w.port.card.text())
        return w.port.card.text()

    def test_doctor_crash_shows_stderr(self):
        w = self.stand_in('--stderr', 'Traceback (most recent call last):\\nValueError: <boom>', '--exit', '1')
        self.assertTrue(hasattr(w.setup, 'check_msg'), 'SetupTab has no check_msg')
        with mock.patch.object(w, 'set_ready') as ready:
            w.setup.check()
            self.assertTrue(until(lambda: 'Retry' in w.setup.check_msg.text(), 10000))
        self.assertIn('ValueError: &lt;boom&gt;', w.setup.check_msg.text())
        self.assertIn('nx2android failed', w.setup.check_msg.text()); self.assertNotIn('porter failed', w.setup.check_msg.text())   # UI-REVIEW top fix 2
        self.assertIn('href="retry"', w.setup.check_msg.text())
        ready.assert_called_with(False)

    def test_error_document(self):
        fixture = REPO / 'tests/fixtures/bridge/inspect_error.json'
        w = self.stand_in('--fixture', str(fixture), '--exit', '2')
        msg = json.loads(fixture.read_text())['error'].replace('<', '&lt;').replace('>', '&gt;')
        self.assertIn(msg, self.card(w))

    def test_empty_answer(self):
        w = self.stand_in(); runner.PORTER = ['-c', '']
        text = self.card(w)
        self.assertIn('porter gave no answer', text)
        self.assertIn('href="retry"', text)

    def test_undecodable_stderr(self):
        w = self.stand_in('--stderr', '\\xff<b>', '--exit', '1')
        with mock.patch.object(sys, 'excepthook') as hook:
            text = self.card(w)
        hook.assert_not_called()
        self.assertIn('&lt;b&gt;', text)

    def test_failed_to_start(self):
        got = []
        with mock.patch.object(runner.sys, 'executable', str(Path(tempfile.mkdtemp()) / 'no-python')):
            runner.call_json(None, ['doctor', '--json'], lambda *a: got.append(a))
        self.assertTrue(until(lambda: got, 5000)); QTest.qWait(200)
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0][:2], (None, -1))
        self.assertTrue(got[0][2])

    def test_concurrent_calls(self):   # each call has its own timer: a hung one does not hold up a quick one
        pf = Path(tempfile.mkdtemp()) / 'pids.json'; seq = []
        runner.PORTER = [FAKE, '--hang', '--pid-file', str(pf), '--']
        runner.call_json(None, ['devices', '--json'], lambda o, c, f: seq.append(('hung', o, f)), timeout=1)
        runner.PORTER = [FAKE, '--']
        runner.call_json(None, ['devices', '--json'], lambda o, c, f: seq.append(('quick', o, f)))
        self.assertTrue(until(lambda: len(seq) == 2, 6000), seq)
        if pf.is_file(): pids = json.loads(pf.read_text()); self.addCleanup(reap, pids['detached']); self.addCleanup(reap, pids['child'])
        self.assertEqual(seq[0], ('quick', [], None))
        self.assertEqual((seq[1][0], seq[1][1], seq[1][2]['timeout']), ('hung', None, 1))

    def test_devices_and_games(self):
        w = self.stand_in('--stderr', 'adb: <bad> cable', '--exit', '1')
        w.port.refresh_devices()
        self.assertTrue(until(lambda: 'adb: <bad> cable' in w.port.device.itemText(0), 10000), w.port.device.itemText(0))
        self.assertNotIn('porter', w.port.device.itemText(0))   # UI-REVIEW top fix 2: players never see the word porter
        self.assertIn('adb: <bad> cable', w.port.device.itemData(0, app.Qt.ToolTipRole) or '')
        self.assertEqual(w.port.device.itemData(0), '')
        self.assertTrue(hasattr(w.games, 'note'), 'GamesTab has no note')
        w.games.load()
        self.assertTrue(until(lambda: 'Retry' in w.games.note.text(), 10000))
        self.assertIn('adb: &lt;bad&gt; cable', w.games.note.text())
        with mock.patch.object(QMessageBox, 'warning', side_effect=AssertionError('a dialog')) as warn:
            w.setup.download()
            self.assertTrue(until(lambda: 'Retry' in w.setup.dl_step.text(), 10000), w.setup.dl_step.text())
        warn.assert_not_called()
        self.assertIn('adb: &lt;bad&gt; cable', w.setup.dl_step.text()); self.assertNotIn('porter', w.setup.dl_step.text())
        with mock.patch.object(app, 'call_json') as call:
            w.setup.dl_step.linkActivated.emit('retry')
        self.assertEqual(call.call_count, 1)

    def test_process_env(self):
        runner.PORTER = ['-c', "import json, os; print(json.dumps({'ev': 'say', 'msg': json.dumps([os.getcwd(), os.environ.get('NX2A_GUI')])}))"]
        p = runner.Porter(); evs = []; p.event.connect(evs.append)
        p.start([])
        self.assertEqual(wait(p.finished, 20000), [0])
        cwd, gui = json.loads(evs[0]['msg'])
        self.assertEqual(os.path.realpath(cwd), os.path.realpath(paths.user_dir()))
        self.assertEqual(gui, '1')


class Fake(unittest.TestCase):   # runner.PORTER points at the stand-in; GRACE_MS is restored
    def setUp(self):
        keep = runner.PORTER, getattr(runner, 'GRACE_MS', 5000)
        self.addCleanup(lambda: (setattr(runner, 'PORTER', keep[0]), setattr(runner, 'GRACE_MS', keep[1])))
        runner.PORTER = [FAKE, '--tree', '--']

    def tree(self, porter, log=None):   # start a --tree port; its pids once they are printed
        evs = log if log is not None else []; porter.event.connect(evs.append)
        porter.start(['port', 'x', '--progress', 'json'])
        self.assertTrue(until(lambda: any(e.get('ev') == 'pids' for e in evs), 10000), evs)
        pids = next(e for e in evs if e.get('ev') == 'pids')
        self.addCleanup(reap, pids['detached']); self.addCleanup(reap, pids['child'])
        return pids


class Stop(Fake):
    def test_stop_kills_tree_keeps_detached(self):
        p = runner.Porter(); fin = QSignalSpy(p.finished)
        pids = self.tree(p)
        p.stop()
        self.assertTrue(fin.wait(10000))
        self.assertEqual(fin.at(0), [130])
        self.assertTrue(gone(pids['child']))
        self.assertTrue(alive(pids['detached']))

    def test_force_after_grace(self):
        runner.GRACE_MS = 1000; runner.PORTER = [FAKE, '--tree', '--ignore-stop', '--']
        p = runner.Porter(); fin = QSignalSpy(p.finished)
        pids = self.tree(p)
        t = time.time(); p.stop()
        self.assertTrue(until(lambda: fin.count(), 6000))
        self.assertLess(time.time() - t, 6)
        self.assertEqual(fin.at(0), [130])
        self.assertTrue(gone(pids['child']))

    def test_events_before_finished(self):
        p = runner.Porter(); seq = []
        p.finished.connect(lambda c: seq.append(('finished', c)))
        self.tree(p, seq)
        p.stop()
        self.assertTrue(until(lambda: any(isinstance(x, tuple) for x in seq), 10000))
        QTest.qWait(500)
        self.assertEqual(seq[-1], ('finished', 130))
        self.assertIn({'ev': 'say', 'msg': '[RED] interrupted'}, seq[:-1])
        self.assertEqual(sum(isinstance(x, tuple) for x in seq), 1)

    def test_second_start_refused(self):   # WR-04 / T-03-35: a second start replaced the run, and the first one's tree was left outside Cancel and the close guard
        p = runner.Porter(); fin = QSignalSpy(p.finished)
        pids = self.tree(p); first = p.p
        self.assertIs(p.start(['tools', '--download', '--progress', 'json']), False)
        self.assertIs(p.p, first); self.assertTrue(p.running())
        p.stop(); self.assertTrue(fin.wait(10000)); QTest.qWait(300)
        self.assertEqual([fin.at(i) for i in range(fin.count())], [[130]])
        self.assertTrue(gone(pids['child']))

    def test_stop_when_idle_is_noop(self):
        p = runner.Porter(); fin, ev = QSignalSpy(p.finished), QSignalSpy(p.event)
        p.stop(); QTest.qWait(200)
        self.assertEqual((fin.count(), ev.count()), (0, 0))

    def test_stop_after_exit_is_noop(self):
        runner.PORTER = [FAKE, '--exit', '0', '--']
        p = runner.Porter(); fin = QSignalSpy(p.finished)
        p.start(['port', 'x'])
        self.assertTrue(fin.wait(10000))
        self.assertEqual(fin.at(0), [0])
        p.stop(); QTest.qWait(500)
        self.assertEqual(fin.count(), 1)

    def test_port_tab_status(self):
        w = window(self)
        port = w.port; fin = QSignalSpy(port.porter.finished); evs = []
        port.porter.event.connect(evs.append)
        port.run(['port', 'x', '--progress', 'json'])
        self.assertTrue(until(lambda: any(e.get('ev') == 'pids' for e in evs), 10000))
        pids = next(e for e in evs if e.get('ev') == 'pids'); self.addCleanup(reap, pids['detached'])
        port.cancel()
        self.assertEqual(port.step.text(), 'stopping…')
        self.assertFalse(port.cancel_btn.isEnabled())
        self.assertNotIn('cancelled', port.log.toPlainText())
        self.assertTrue(fin.wait(10000))
        self.assertEqual(port.step.text(), 'cancelled')
        self.assertEqual(port.log.toPlainText().splitlines()[-1], 'cancelled')



class Close(Fake):
    def window(self):
        w = window(self); w.show()
        for porter in (w.port.porter, w.setup.fetch): self.addCleanup(self.finish, porter)
        return w

    def finish(self, porter):   # a run a test left going
        if porter.running():
            fin = QSignalSpy(porter.finished); porter.stop(); fin.wait(10000)

    def ask(self, w, answer):
        m = mock.patch.object(w, 'ask_stop', create=True, return_value=answer); self.addCleanup(m.stop); return m.start()

    def running_port(self, w, args):
        evs = []; w.port.porter.event.connect(evs.append)
        w.port.run(args)
        self.assertTrue(until(lambda: any(e.get('ev') == 'pids' for e in evs), 10000))
        pids = next(e for e in evs if e.get('ev') == 'pids'); self.addCleanup(reap, pids['detached'])
        return pids

    def test_idle_close_quits(self):
        w = self.window(); ask = self.ask(w, True)
        self.assertTrue(w.close())
        ask.assert_not_called()

    def test_keep_running(self):
        w = self.window(); self.ask(w, False)
        self.running_port(w, ['port', 'x', '--progress', 'json'])
        self.assertFalse(w.close())
        self.assertTrue(w.port.porter.running())
        self.assertTrue(w.isVisible())

    def test_stop_and_quit(self):
        w = self.window(); self.ask(w, True)
        pids = self.running_port(w, ['port', 'x', '--progress', 'json'])
        fin = QSignalSpy(w.port.porter.finished)
        self.assertFalse(w.close())
        self.assertEqual(w.port.step.text(), 'stopping…')
        self.assertTrue(w.isVisible())
        self.assertTrue(fin.wait(10000))
        self.assertTrue(until(lambda: not w.isVisible(), 3000))
        self.assertTrue(gone(pids['child']))

    def test_install_wording(self):
        for args, installing in ((['install', 'd', '--apk', 'a.apk', '--progress', 'json'], True), (['port', 'x', '--progress', 'json', '--install'], True),
                                 (['port', 'x', '--progress', 'json'], False)):
            with self.subTest(args=args):
                w = self.window(); ask = self.ask(w, False)
                self.running_port(w, args)
                self.assertFalse(w.close())
                ask.assert_called_once_with(installing)
                self.finish(w.port.porter)

    def test_download_counts(self):
        w = self.window(); ask = self.ask(w, False)
        w.setup.fetch.start(['tools', '--download', '--progress', 'json'])
        self.assertTrue(until(lambda: w.setup.fetch.pgid, 10000))
        self.assertFalse(w.close())
        ask.assert_called_once_with(False)

    def test_setup_cancel_label(self):   # D-21: the Setup tab's button cancels a download or a Prepare, whoever started it
        w = self.window(); s = w.setup
        for args, label in ((['tools', '--download', '--progress', 'json'], 'Cancel download'), (['tools', '--prepare', '--progress', 'json'], 'Cancel .NET preparation')):
            with self.subTest(label):
                evs = []; s.fetch.event.connect(evs.append); s.fetch.start(args)
                self.assertTrue(until(lambda: any(e.get('ev') == 'pids' for e in evs), 10000))
                pids = next(e for e in evs if e.get('ev') == 'pids'); self.addCleanup(reap, pids['detached']); self.addCleanup(reap, pids['child'])
                s.fetch.event.disconnect(evs.append)
                self.assertEqual(s.dl_btn.text(), label); self.assertTrue(s.dl_btn.isEnabled())
                fin = QSignalSpy(s.fetch.finished); s.dl_btn.click(); self.assertEqual(s.dl_step.text(), 'stopping…')
                self.assertTrue(fin.wait(10000)); self.assertEqual(fin.at(0), [130]); self.assertTrue(gone(pids['child']))
                self.assertEqual(s.dl_btn.text(), 'Download missing tools'); self.assertEqual(s.dl_step.text(), 'cancelled')

    def test_confirm_while_running(self):   # the wizard starts a run while the Setup tab's tools --json is out: Cancel from the start, and no dialog or second run
        w = self.window(); s = w.setup; evs = []; s.fetch.event.connect(evs.append)
        s.fetch.start(['tools', '--download', '--progress', 'json']); label = s.dl_btn.text(), s.dl_btn.isEnabled()
        self.assertTrue(until(lambda: any(e.get('ev') == 'pids' for e in evs), 10000))
        pids = next(e for e in evs if e.get('ev') == 'pids'); self.addCleanup(reap, pids['detached']); self.addCleanup(reap, pids['child'])
        self.assertEqual(label, ('Cancel download', True))
        first = s.fetch.p; it = {'name': 'x', 'version': '1', 'size': 1, 'url': 'https://h/a', 'license': 'https://h/l'}
        with mock.patch.object(app, 'QMessageBox', side_effect=AssertionError('a dialog')): s.confirm_download([it], 0, None)
        self.assertIs(s.fetch.p, first); self.assertTrue(s.fetch.running()); self.assertEqual(s.dl_btn.text(), 'Cancel download')

    def test_setup_finish_copy(self):   # UI-REVIEW top fix 2: a Prepare finished from the Setup tab reads the wizard's words; neither line says porter
        w = self.window(); s = w.setup; runner.PORTER = ['-c', 'import sys; sys.exit(0)']
        for args, line in ((['tools', '--prepare', '--progress', 'json'], firstrun.PREPARED), (['tools', '--download', '--progress', 'json'], 'the tools are ready')):
            with self.subTest(line):
                fin = QSignalSpy(s.fetch.finished); s.fetch.start(args); self.assertTrue(fin.wait(10000)); QTest.qWait(50)
                self.assertEqual(s.dl_step.text(), line); self.assertNotIn('porter', s.dl_step.text())

    def test_download_failure_inline(self):
        runner.PORTER = [FAKE, '--']   # the Window's own one-shots
        w = self.window()
        runner.PORTER = ['-c', "import json, os, sys; d = os.path.join(os.environ['NX2A_HOME'], 'logs'); os.makedirs(d, exist_ok=True); "
                               "p = os.path.join(d, 'replay-tools.log'); open(p, 'w').close(); print(json.dumps({'ev': 'log', 'path': p})); "
                               "print(json.dumps({'ev': 'error', 'msg': 'bad <thing> & co', 'type': 'FetchError', 'log': p})); sys.exit(1)"]
        fin = QSignalSpy(w.setup.fetch.finished)
        with mock.patch.object(QMessageBox, 'warning', side_effect=AssertionError('a dialog')) as warn:
            w.setup.fetch.start(['tools', '--download', '--progress', 'json'])
            self.assertTrue(fin.wait(10000))
            QTest.qWait(50)
        warn.assert_not_called()
        text = w.setup.dl_step.text()
        self.assertIn('bad &lt;thing> &amp; co', text)
        self.assertIn('<a href="log">Open log</a>', text)
        with mock.patch.object(app, 'QDesktopServices') as ds:
            w.setup.dl_step.linkActivated.emit('log')
        self.assertEqual(Path(ds.openUrl.call_args[0][0].toLocalFile()), Path(HOME) / 'logs/replay-tools.log')


class Timeout(Fake):   # a one-shot that never answers is killed at its own limit, with its children, and the view offers Retry
    def hung(self, args, done, timeout=1, parent=None):   # a one-shot that holds a --tree; its pids once the stand-in wrote them
        pf = Path(tempfile.mkdtemp()) / 'pids.json'
        runner.PORTER = [FAKE, '--hang', '--pid-file', str(pf), '--']
        runner.call_json(parent, args, done, timeout=timeout)
        self.assertTrue(until(pf.is_file, 10000))
        until(lambda: pf.read_text(), 2000); pids = json.loads(pf.read_text())
        self.addCleanup(reap, pids['detached']); self.addCleanup(reap, pids['child'])
        return pids

    def test_kills_tree_at_limit(self):
        got = []
        pids = self.hung(['inspect', 'x', '--json'], lambda *a: got.append(a))
        self.assertTrue(until(lambda: got, 4000))
        self.assertEqual(len(got), 1)
        obj, _code, fail = got[0]
        self.assertIsNone(obj)
        self.assertEqual(fail['timeout'], 1)
        self.assertTrue(gone(pids['child']))

    def test_inspect_card_retry(self):
        runner.PORTER = [FAKE, '--']   # the Window's own one-shots
        w = window(self); port = w.port
        port.on_inspect(None, -1, {'timeout': 60, 'error': '', 'stderr': ''})
        self.assertIn("didn't answer in 60 s", port.card.text())
        self.assertIn('href="retry"', port.card.text())
        self.assertNotIn('No game found', port.card.text())
        port.folder.setText(tempfile.mkdtemp())
        with mock.patch.object(app, 'call_json') as call:
            port.card.linkActivated.emit('retry')
        self.assertEqual(call.call_count, 1)
        self.assertNotIn('href="retry"', port.card.text())

    def test_owner_gone_mid_call(self):   # the app quits while a one-shot runs: no callback into destroyed views, no RuntimeError, no leftover child
        import shiboken6
        from PySide6.QtWidgets import QWidget
        owner = QWidget(); got = []
        pids = self.hung(['doctor', '--json'], lambda *a: got.append(a), timeout=30, parent=owner)
        with mock.patch.object(sys, 'excepthook') as hook:
            shiboken6.delete(owner); QTest.qWait(300)
        hook.assert_not_called()
        self.assertEqual(got, [])
        self.assertTrue(gone(pids['child']))

    def test_fatal_shows_start_failure(self):   # WR-03: the bundle's launcher shows a failed engine copy in a window
        import gui
        with mock.patch.object(QMessageBox, 'critical') as box: gui.fatal('[RED] could not copy the engine')
        self.assertEqual(box.call_args[0][1:], ('nx2android', 'could not copy the engine'))

    def test_default_limits(self):   # WR-02: setup runs the NDK probe's two steps (probe.TIMEOUT each) and adb version (15 s); a run killed at the limit caches nothing
        from porter import probe
        self.assertEqual(runner.TIMEOUTS, {'devices': 45, 'doctor': 30, 'inspect': 60, 'profiles': 20, 'setup': 150, 'tools': 60})
        self.assertGreater(runner.TIMEOUTS['setup'], 2 * probe.TIMEOUT + 15)


class Downloads(unittest.TestCase):   # the Setup tab's confirm dialog: an untested fallback says so, and index strings are text, not markup
    def test_untested_and_escaped(self):
        w = window(self)
        it = {'name': '<b>x</b>', 'version': '1', 'size': 1, 'url': 'https://h/a', 'license': '"onclick=', 'untested': True}
        with mock.patch.object(app, 'QMessageBox') as box: w.setup.confirm_download([it], 0, None)
        text = box.call_args[0][2]
        for s in ('(untested)', '&lt;b&gt;x&lt;/b&gt;', '&quot;onclick='): self.assertIn(s, text)
        self.assertNotIn('<b>x</b>', text)
        self.assertNotIn('downloading them means you accept those', text)   # D-07: the legal notice covers the vendors' licenses

    def test_progress_line(self):   # D-26: the tools page's line, word-wrapped
        w = window(self); s = w.setup
        ev = {'ev': 'progress', 'name': 'Android NDK r27c', 'step': 'downloading', 'done': 412 * 2**20, 'total': 781 * 2**20, 'unit': 'B', 'frac': 0.53, 'eta': 61, 'rate': 6396314}
        s.on_fetch({'ev': 'stage', 'k': 2, 'n': 3, 'name': 'Android NDK r27c'}); s.on_fetch(ev)
        self.assertEqual(s.dl_step.text(), firstrun.progress_line(ev, '[2/3]')); self.assertIn('/s · 1 min left', s.dl_step.text())
        self.assertTrue(s.dl_step.wordWrap())


class Escaping(unittest.TestCase):   # the game card shows porter's strings as text, the language box offers porter's list, the log takes the system fixed font
    def info(self, **kw): return dict({'title_id': '0100000000AAA000', 'updates': [], 'dlc': [], 'android': None, 'supported': True, 'reason': ''}, **kw)

    def test_language_box(self):
        w = window(self); port = w.port; box = port.language
        langs = lambda *cs: [{'code': c, 'name': n} for c, n in cs]
        port.on_inspect(self.info(languages=langs(('ja', 'Japanese'), ('fr', 'French'))), 0, None)
        self.assertEqual([box.itemData(i) for i in range(box.count())], ['', 'ja', 'fr']); self.assertEqual(box.itemText(0), 'English (default)')
        box.setCurrentIndex(box.findData('fr'))
        port.on_inspect(self.info(languages=langs(('fr', 'French'), ('de', 'German'))), 0, None)
        self.assertEqual(box.currentData(), 'fr')
        port.on_inspect(self.info(), 0, None)
        self.assertEqual(box.count(), 1); self.assertEqual(box.currentData(), '')

    def test_card_escapes(self):   # a game's strings are text: html.escape(..., quote=True) on each
        w = window(self); port = w.port
        port.on_inspect(self.info(name='<b>&x</b>', updates=[{'version': '<v>'}], pack='<i>p</i>', android={'status': 'playable', 'tested': '<u>t</u>'},
                                  reason='<script>r</script>'), 0, None)
        t = port.card.text()
        for s in ('&lt;b&gt;&amp;x&lt;/b&gt;', '&lt;v&gt;', '&lt;i&gt;p&lt;/i&gt;', '&lt;u&gt;t&lt;/u&gt;', '&lt;script&gt;'): self.assertIn(s, t)
        for s in ('<b>&x</b>', '<v>', '<i>p</i>', '<u>t</u>', '<script>'): self.assertNotIn(s, t)

    def test_folder_path_escaped(self):
        w = window(self); port = w.port
        port.folder.setText('/no/such/<b>dir'); port.inspect()
        t = port.card.text()
        self.assertIn('Not a folder', t); self.assertIn('&lt;b&gt;', t); self.assertNotIn('<b>dir', t)

    def test_empty_name_and_reason(self):   # no name: the title ID in bold; an empty reason adds no row
        w = window(self); port = w.port
        port.on_inspect(self.info(), 0, None)
        t = port.card.text()
        self.assertIn('<b>0100000000AAA000</b>', t); self.assertEqual(t.count('<br>'), 1, t)

    def test_log_font(self):   # the platform's own fixed-width font, not one picked by OS name
        from PySide6.QtGui import QFontDatabase
        w = window(self); f = w.port.log.font()
        self.assertEqual(f.family(), QFontDatabase.systemFont(QFontDatabase.FixedFont).family()); self.assertEqual(f.pointSize(), 9)

    def test_one_language_source(self):   # upstream's nacp.LANGUAGES through porter inspect, no copy in the GUI
        self.assertIsNone(re.search(r'^LANGUAGES\b', (REPO / 'gui/app.py').read_text(encoding='utf-8'), re.M))


class Targets(unittest.TestCase):   # D-02 / UI-SPEC rules 1-11: two target boxes, the host's own default, one note, one --platform token
    def setUp(self):
        keep = runner.PORTER; self.addCleanup(setattr, runner, 'PORTER', keep); runner.PORTER = [FAKE, '--']   # the stand-in answers the start-up one-shots

    def port(self, mac):   # a PortTab built as if on macOS (mac=True) or on Windows/Linux; MAC_HOST stays patched for the test
        m = mock.patch.object(app, 'MAC_HOST', mac); m.start(); self.addCleanup(m.stop)
        return window(self).port

    def test_default_is_the_hosts_own_target(self):   # rule 4, option-a: the Mac app alone on macOS, the APK everywhere else
        for mac in (True, False):
            with self.subTest(mac=mac):
                p = self.port(mac)
                self.assertEqual((p.android_box.isChecked(), p.mac_box.isChecked()), (not mac, mac))
                self.assertTrue(p.android_box.isEnabled()); self.assertEqual(p.mac_box.isEnabled(), mac)
                self.assertTrue(p.platform_arg() in ('android', 'mac-app', 'both'))

    def test_one_helper_names_the_target(self):   # rule 8, QUAL-07: the three reachable box states, nothing else
        p = self.port(False)
        self.assertEqual(p.platform_arg(), 'android')
        p.mac_box.setChecked(True); self.assertEqual(p.platform_arg(), 'both')
        p.android_box.setChecked(False); self.assertEqual(p.platform_arg(), 'mac-app')

    def test_the_last_box_cannot_be_unticked(self):   # rule 5, 6.1: no zero-target state, and the refusal says so
        p = self.port(False)
        p.android_box.setChecked(False)
        self.assertTrue(p.android_box.isChecked())
        self.assertEqual(p.platform_arg(), 'android')
        self.assertEqual(p.targets_note.text(), 'Keep at least one target ticked.')
        self.assertFalse(p.targets_note.isHidden())

    def test_off_macos_the_mac_box_says_why(self):   # D-03, rule 7: disabled with the reason, and the note names it
        p = self.port(False)
        self.assertFalse(p.mac_box.isEnabled())
        self.assertEqual(p.mac_box.toolTip(), 'A Mac app is built on a Mac: this host builds the Android APK')
        self.assertEqual(p.targets_note.text(), 'A Mac app is built on a Mac. This host builds the Android APK.')
        self.assertFalse(p.targets_note.isHidden())

    def test_on_macos_the_mac_box_is_offered(self):   # rules 4, 6.3, 10: the APK is one tick away and the Install row follows it
        p = self.port(True)
        self.assertTrue(p.mac_box.isEnabled())
        self.assertEqual(p.mac_box.toolTip(), 'A double-clickable Mac app, built on this Mac with Xcode')
        self.assertFalse(p.install_row.isEnabled())   # a Mac-only run installs nothing
        self.assertEqual(p.targets_note.text(), 'Install on the device and the device list apply to the Android APK.')
        p.android_box.setChecked(True)
        self.assertTrue(p.install_row.isEnabled())
        self.assertEqual(p.targets_note.text(), ''); self.assertTrue(p.targets_note.isHidden())

    def test_start_asks_for_the_ticked_targets(self):   # rules 8-9: one --platform always, --install only while the APK is ticked
        p = self.port(False); p.install.setChecked(True)
        for android, mac, token, install in ((True, False, 'android', True), (True, True, 'both', True), (False, True, 'mac-app', False)):
            with self.subTest(token=token):
                p.mac_box.setChecked(mac); p.android_box.setChecked(android)
                with mock.patch.object(app.config, 'load', return_value={'keys': 'prod.keys'}), mock.patch.object(p, 'run') as run:
                    p.start()
                args = run.call_args[0][0]
                self.assertEqual(args[args.index('--platform') + 1], token)
                self.assertEqual('--install' in args, install)

    def test_the_boxes_wait_for_the_run(self):   # rule 11: both boxes off while a run goes, back afterwards, the Mac box only where it is offered
        p = self.port(False); runner.PORTER = [FAKE, '--tree', '--']
        evs = []; p.porter.event.connect(evs.append)
        p.run(['port', 'x', '--progress', 'json', '--platform', 'android'])
        self.assertTrue(until(lambda: any(e.get('ev') == 'pids' for e in evs), 10000), evs)
        pids = next(e for e in evs if e.get('ev') == 'pids'); self.addCleanup(reap, pids['detached'])
        self.assertFalse(p.android_box.isEnabled()); self.assertFalse(p.mac_box.isEnabled()); self.assertFalse(p.install_row.isEnabled())
        fin = QSignalSpy(p.porter.finished); p.cancel(); self.assertTrue(fin.wait(10000))
        self.assertTrue(until(lambda: p.android_box.isEnabled(), 3000))
        self.assertFalse(p.mac_box.isEnabled()); self.assertTrue(p.install_row.isEnabled())


class Results(unittest.TestCase):   # D-06, rules 15-20: one row per target, porter's own reason on the second line, its own Reveal; the single output button is gone
    def setUp(self):
        keep = runner.PORTER; self.addCleanup(setattr, runner, 'PORTER', keep); runner.PORTER = [FAKE, '--']
        m = mock.patch.object(app, 'MAC_HOST', False); m.start(); self.addCleanup(m.stop)   # the APK ticked, so the bar's Install button has a target to follow

    def port(self):
        return window(self).port

    def draw(self, port, **res):   # the result event as porter sends it (runlog adds the log path; the view only needs it to exist)
        port.on_event(dict({'ev': 'result', 'log': ''}, **res))

    def rows(self, port):
        return port.results.findChildren(app.TargetRow)

    def test_one_row_per_target_in_the_runs_order(self):
        p = self.port()
        self.assertTrue(p.results.isHidden())   # rule 15: hidden until a result arrives, no heading, no placeholder
        self.draw(p, platform='both', apk='/out/Game.apk', data='/out/Game-data', app='/out/Game.app',
                  targets=[{'platform': 'android', 'status': 'ok', 'out': '/out/Game.apk', 'reason': ''},
                           {'platform': 'mac-app', 'status': 'ok', 'out': '/out/Game.app', 'reason': ''}])
        rows = self.rows(p)
        self.assertEqual([r.name.text() for r in rows], ['Android APK · built', 'Mac app · built'])
        self.assertEqual([r.glyph.text() for r in rows], ['✓', '✓'])
        self.assertEqual([r.path.full for r in rows], ['/out/Game.apk', '/out/Game.app'])
        self.assertFalse(p.results.isHidden())
        self.assertEqual(p.results_layout.count(), 2)   # the block holds the rows and nothing else

    def test_a_failed_row_shows_porters_reason_as_plain_text(self):
        p = self.port(); reason = '<b>dmsh_chain.lock</b> is held: close the other port & try again'
        self.draw(p, platform='both', targets=[{'platform': 'android', 'status': 'ok', 'out': '/out/Game.apk', 'reason': ''},
                                               {'platform': 'mac-app', 'status': 'failed', 'out': '', 'reason': reason}])
        row = self.rows(p)[1]
        self.assertEqual((row.name.text(), row.glyph.text()), ('Mac app · failed', '✗'))
        self.assertEqual(row.reason.text(), reason)   # T-11-09: porter's sentence verbatim, markup and all
        self.assertEqual(row.reason.textFormat(), app.Qt.PlainText)
        self.assertTrue(row.reason.wordWrap()); self.assertFalse(row.reason.isHidden())
        self.assertFalse(row.reveal.isEnabled()); self.assertTrue(row.path.isHidden())   # no package: no path, nothing to open

    def test_a_skipped_row_and_a_built_rows_reveal(self):
        p = self.port()
        self.draw(p, platform='both', targets=[{'platform': 'android', 'status': 'skipped', 'out': '', 'reason': 'no android.tsv for this game'},
                                               {'platform': 'mac-app', 'status': 'ok', 'out': '/out/Game.app', 'reason': ''}])
        a, m = self.rows(p)
        self.assertEqual((a.name.text(), a.glyph.text(), a.reason.text()), ('Android APK · skipped', '–', 'no android.tsv for this game'))
        self.assertFalse(a.reveal.isEnabled())
        self.assertTrue(m.reveal.isEnabled()); self.assertEqual(m.reveal.text(), 'Reveal')
        self.assertEqual(m.reveal.toolTip(), 'Show the Mac app in your file manager'); self.assertEqual(m.reveal.accessibleName(), 'Reveal the Mac app')
        self.assertNotEqual(a.reveal.accessibleName(), m.reveal.accessibleName())   # rule 19: two identical labels, two names
        with mock.patch.object(app, 'QDesktopServices') as ds:
            m.reveal.click()
        self.assertEqual(Path(ds.openUrl.call_args[0][0].toLocalFile()), Path('/out'))

    def test_a_single_target_result_draws_one_row_and_a_run_clears_it(self):   # rule 16: one shape, so today's goldens stay valid
        p = self.port()
        self.draw(p, apk='/out/Game.apk', data='/out/Game-data')   # today's result: no targets[], no platform
        rows = self.rows(p)
        self.assertEqual([r.name.text() for r in rows], ['Android APK · built']); self.assertTrue(rows[0].reveal.isEnabled())
        self.draw(p, platform='mac-app', app='/out/Game.app')
        self.assertEqual([r.name.text() for r in self.rows(p)], ['Mac app · built'])   # replaced, never stacked
        with mock.patch.object(p.porter, 'start'):
            p.run(['port', 'x', '--progress', 'json'])
        self.assertEqual(self.rows(p), []); self.assertTrue(p.results.isHidden()); self.assertEqual(p.results_layout.count(), 0)

    def test_install_follows_a_built_android_row(self):
        p = self.port()
        self.draw(p, platform='both', apk='/out/Game.apk', data='/out/Game-data',
                  targets=[{'platform': 'android', 'status': 'ok', 'out': '/out/Game.apk', 'reason': ''},
                           {'platform': 'mac-app', 'status': 'failed', 'out': '', 'reason': 'the translator did not build'}])
        p.on_finished(1)
        self.assertTrue(p.inst_btn.isEnabled())   # rule 20: the APK exists, so it can be installed
        self.draw(p, platform='both', app='/out/Game.app',
                  targets=[{'platform': 'android', 'status': 'skipped', 'out': '', 'reason': 'no android.tsv for this game'},
                           {'platform': 'mac-app', 'status': 'ok', 'out': '/out/Game.app', 'reason': ''}])
        p.on_finished(0)
        self.assertFalse(p.inst_btn.isEnabled())   # a Mac app is never installed from here

    def test_the_single_output_button_is_gone(self):
        p = self.port()
        self.assertFalse(hasattr(p, 'open_btn')); self.assertFalse(hasattr(p, 'open_out'))
        labels = [b.text() for b in p.findChildren(app.QPushButton)]
        self.assertIn('Open log', labels); self.assertIn('Install on device', labels); self.assertNotIn('Open output folder', labels)


FIXTURES = REPO / 'tests/fixtures/bridge'


class Replay(unittest.TestCase):   # golden JSON-lines streams (tests/fixtures/bridge/record.py) through runner.Porter: the protocol the GUI parses
    def setUp(self):
        keep = runner.PORTER; self.addCleanup(setattr, runner, 'PORTER', keep)

    def replay(self, name, code=0):   # the events and the exit code runner.Porter gives for the fixture
        runner.PORTER = [FAKE, '--fixture', str(FIXTURES / name), '--exit', str(code), '--']
        p = runner.Porter(); evs = []; p.event.connect(evs.append); fin = QSignalSpy(p.finished)
        p.start(['port'])
        self.assertTrue(fin.wait(10000))
        return evs, fin.at(0)[0]

    def golden(self, name):   # every non-blank line is one JSON object
        rows = [json.loads(ln) for ln in (FIXTURES / name).read_text(encoding='utf-8').splitlines() if ln.strip()]
        self.assertTrue(rows and all(isinstance(r, dict) for r in rows), name)
        return rows

    def test_port_ok(self):
        evs, code = self.replay('port_ok.jsonl')
        self.assertEqual((evs, code), (self.golden('port_ok.jsonl'), 0))
        self.assertEqual(evs[0]['ev'], 'log')
        self.assertEqual(evs[-1]['ev'], 'result')
        self.assertTrue({'apk', 'data', 'log'} <= evs[-1].keys())

    def test_port_build_error(self):
        evs, code = self.replay('port_build_error.jsonl', 1)
        self.assertEqual((evs, code), (self.golden('port_build_error.jsonl'), 1))
        self.assertEqual((evs[-1]['ev'], evs[-1]['type']), ('error', 'BuildError'))

    def test_install_ok(self):
        evs, code = self.replay('install_ok.jsonl')
        self.assertEqual((evs, code), (self.golden('install_ok.jsonl'), 0))
        kinds = [e['ev'] for e in evs if e['ev'] in ('stage', 'step', 'stage_end')]
        self.assertEqual((kinds[0], kinds[-1]), ('stage', 'stage_end'))
        self.assertIn('step', kinds)
        self.assertTrue(all(e['name'] == 'install' for e in evs if e['ev'] in ('stage', 'step', 'stage_end')))

    def test_edge_lines(self):   # a non-JSON line and a JSON array become say, a blank line nothing, a last line with no newline still arrives
        evs, code = self.replay('edge.jsonl')
        self.assertEqual(evs, [{'ev': 'say', 'msg': 'porter 1.2 starting'}, {'ev': 'say', 'msg': '["not", "an", "event"]'}, {'ev': 'say', 'msg': 'last'}])
        self.assertEqual(code, 0)

    def test_fixtures_are_scrubbed(self):   # the fixtures are public: no user paths, no key material
        bad = re.compile(r'/Users/|/home/|C:\\\\Users|C:\\Users|AppData|prod\.keys\s*[=:]\s*[0-9a-fA-F]{16}|\b[0-9a-fA-F]{32}\b')
        for f in sorted(FIXTURES.iterdir()):
            if f.is_file():
                with self.subTest(f.name): self.assertIsNone(bad.search(f.read_text(encoding='utf-8', errors='replace')), f.name)


if __name__ == '__main__': unittest.main()
