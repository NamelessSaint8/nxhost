# The first-run wizard, the "setup is not finished" banner and the Setup tab's checklist rows, drawn from porter's `setup --json` on every launch (FRUN-03):
# the answer is kept in memory only; this module writes no file, keeps no "done" flag and reaches porter only through gui/runner.py (D-01).
# Any QMainWindow that gives it `fetch` (the Porter for tool downloads, under the window's close guard), `recheck()` (setup --json again, its answer to
# on_ready) and optionally `port_a_game()` can host it: today's gui/app.py Window and the new shell (gui/shell.py).
import html

from PySide6.QtCore import QObject, Qt, QTimer, QUrl
from PySide6.QtGui import QColor, QDesktopServices, QFontDatabase
from PySide6.QtWidgets import (QFileDialog, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QPushButton, QScrollArea, QSizePolicy, QTableWidgetItem, QToolBar, QVBoxLayout,
                               QWidget, QWizard, QWizardPage)

from gui.runner import call_json

# (light, dark) per role, UI-SPEC Color: note #9a5b00 replaces #ef6c00 (3.08:1 on white); each pair measured at 4.99:1 or more on its background
COLOUR = {'ok': ('#2e7d32', '#81c784'), 'bad': ('#c62828', '#ef9a9a'), 'note': ('#9a5b00', '#ffb74d'), 'banner': ('#fff4e5', '#3d2e12')}
PAGES = ('legal', 'keys', 'tools', 'device', 'done')
POLL_MS = 2500   # D-15: devices --json again this long after each answer, never on a fixed interval, so a stalled adb cannot stack calls
STATE_GLYPH = {'device': ('✓', 'ok'), 'unauthorized': ('✗', 'bad'), 'offline': ('✗', 'bad'), 'no permissions': ('✗', 'bad'), 'authorizing': ('▶', 'note'), 'connecting': ('▶', 'note')}


def colour(widget, key): return COLOUR[key][widget.palette().window().color().lightness() < 128]


# cause/failed/size are gui/app.py's with "nx2android" for "porter" (players never see the word porter, UI-SPEC Copywriting); copies, not imports,
# because this module may import only gui.runner and PySide6 (03-07's arch rule) and gui/app.py is upstream's file, edited at hook lines only
def cause(fail):
    if fail.get('timeout'): return f"nx2android didn't answer in {fail['timeout']} s"
    return fail.get('error') or (fail.get('stderr') or '').strip().rpartition('\n')[2] or 'nx2android gave no answer'


def failed(fail):   # red rich text: the cause, the last lines of stderr, and a Retry link (href "retry"); porter's text is escaped
    head = cause(fail) if fail.get('timeout') or fail.get('error') or not fail.get('stderr') else 'nx2android failed'
    tail = html.escape(fail.get('stderr') or '', quote=False).replace('\n', '<br>')
    return f'<span style="color:#c62828">{html.escape(head, quote=False)}' + (f'<br>{tail}' if tail else '') + '</span> &nbsp;<a href="retry">Retry</a>'


def size(b):
    for u, d in (('GB', 2**30), ('MB', 2**20), ('KB', 2**10)):
        if b >= d: return f'{b / d:.1f} {u}'
    return f'{b} B'


def mono():   # commands, paths and hashes: the platform's fixed font at 9 pt, as the Port log
    f = QFontDatabase.systemFont(QFontDatabase.FixedFont); f.setPointSize(9); return f


def first_open(doc): return doc['legal']['accepted'] != doc['legal']['version']   # D-02: only an unaccepted notice opens the wizard by itself


class Gate(QObject):   # one per window: porter's last answer, the banner, the open wizard, and whether a launch answer has come yet
    def __init__(self, win):
        super().__init__(win); self.win, self.doc, self.wizard, self.seen, self.start = win, None, None, False, None


def attach(win):
    g = win.first_run = Gate(win)
    bar = g.banner = QToolBar('Setup', win); bar.setMovable(False); bar.setFloatable(False); bar.toggleViewAction().setVisible(False)
    bar.setStyleSheet(f'QToolBar {{ background: {colour(win, "banner")}; border: 0; }}')
    w = QWidget(); h = QHBoxLayout(w); h.setContentsMargins(16, 8, 16, 8); h.setSpacing(8)
    mark = QLabel('!'); f = mark.font(); f.setBold(True); mark.setFont(f); mark.setStyleSheet(f'color: {colour(win, "note")}')
    g.text = QLabel(); g.text.setTextFormat(Qt.PlainText); g.text.setWordWrap(True)   # porter's names are text, not markup
    g.button = QPushButton('Continue setup'); g.button.clicked.connect(lambda: open_setup(win))
    h.addWidget(mark); h.addWidget(g.text, 1); h.addWidget(g.button)
    bar.addWidget(w); win.addToolBar(Qt.TopToolBarArea, bar); bar.hide()
    return g


def on_ready(win, doc):   # each setup --json answer: the banner names what porter says is missing; the launch's first answer may open the wizard
    g = win.first_run
    if doc is None: return   # a failed call: the Setup tab shows it with Retry, nothing else changes
    first, g.doc, g.seen = not g.seen, doc, True
    g.text.setText('Setup is not finished: missing ' + ', '.join(doc['missing']) + '.')
    g.banner.setVisible(not doc['ready'] and bool(doc['missing']))
    if g.wizard: g.wizard.redraw(doc)
    if first and first_open(doc): open_setup(win, 'legal')


def open_setup(win, start=None):   # the wizard at `start`, else at the first step porter reports not ok (the done page when all are); one wizard at most (D-04)
    g = win.first_run
    if g.wizard: g.wizard.show(); g.wizard.raise_(); g.wizard.activateWindow(); return g.wizard
    if g.doc is None: win.recheck(); return None   # no answer yet (the last call failed): ask again, the Setup tab shows the outcome
    g.wizard = z = Wizard(win, g)
    z.go(start or next((st['id'] for st in g.doc['steps'] if not st['ok']), 'done')); z.show()
    return z


def step(doc, sid): return next((st for st in doc['steps'] if st['id'] == sid), {'ok': True, 'detail': '', 'fix': ''})


def body(text=''):   # a body label: plain text, word-wrapped
    lab = QLabel(text); lab.setTextFormat(Qt.PlainText); lab.setWordWrap(True); return lab


class Wizard(QWizard):   # non-modal, shown with show() and never exec(); Skip setup, the close box and Esc all just close it: no confirmation, no write
    def __init__(self, win, gate):
        super().__init__(win, Qt.Window); self.win, self.gate, self.jumping = win, gate, False
        self.setWindowTitle('nx2android setup'); self.setWizardStyle(QWizard.ClassicStyle)   # Classic on every host: no Mac watermark, follows the palette
        self.setOptions(QWizard.NoBackButtonOnStartPage | QWizard.HaveCustomButton1 | QWizard.NoCancelButton)
        self.setButtonText(QWizard.CustomButton1, 'Skip setup'); self.setButtonText(QWizard.FinishButton, 'Close setup')
        self.setButtonLayout([QWizard.CustomButton1, QWizard.Stretch, QWizard.BackButton, QWizard.NextButton, QWizard.FinishButton])
        self.customButtonClicked.connect(lambda _which: self.close())
        self.currentIdChanged.connect(lambda i: self.pages['device'].moved(i == PAGES.index('device')))   # Back, Next or a jump: polling only while it shows
        self.setMinimumSize(720, 560); self.resize(760, 600)
        self.pages = {k: cls() for k, cls in zip(PAGES, (LegalPage, KeysPage, ToolsPage, DevicePage, DonePage))}
        for i, k in enumerate(PAGES): self.setPage(i, self.pages[k])
        self.redraw(gate.doc)

    def go(self, start):   # QWizard's Back walks the visited pages, so reach `start` from the legal page through each one before it (D-04)
        self.restart(); self.jumping = True
        try:
            for _ in range(PAGES.index(start)): self.next()
        finally: self.jumping = False

    def redraw(self, doc):
        for pg in self.pages.values(): pg.redraw(doc)

    def done(self, r):   # every way out (Skip setup, close box, Esc, Close setup) comes here
        self.pages['device'].stop(); super().done(r)
        if self.gate.wizard is self: self.gate.wizard = None
        self.deleteLater()


class Page(QWizardPage):   # its own heading label (no setTitle/setSubTitle: UI-SPEC Typography), 16 px margins; isComplete stays true (never blocking)
    def __init__(self, heading):
        super().__init__(); self.v = QVBoxLayout(self); self.v.setContentsMargins(16, 16, 16, 16); self.v.setSpacing(16)
        self.head = QLabel(heading); self.head.setTextFormat(Qt.PlainText); f = self.head.font(); f.setPointSizeF(f.pointSizeF() + 4); f.setBold(True); self.head.setFont(f)
        self.v.addWidget(self.head); self.v.addSpacing(8)   # 16 + 8: the 24 px gap under the heading

    def redraw(self, doc): pass


class LegalPage(Page):   # D-07: porter's notice and links; the GUI holds no notice text or version of its own
    def __init__(self):
        super().__init__('Before you start'); self.ok = False; self.doc = None
        inner = QWidget(); iv = QVBoxLayout(inner); iv.setContentsMargins(0, 0, 0, 0); iv.setSpacing(8)
        self.notice = body(); self.notice.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.links = QLabel(); self.links.setTextFormat(Qt.RichText); self.links.setWordWrap(True)
        self.links.linkActivated.connect(lambda url: QDesktopServices.openUrl(QUrl(url)))
        self.footer = body('Skip setup closes this window. It opens again next time until you accept.')
        for x in (self.notice, self.links, self.footer): iv.addWidget(x)
        iv.addStretch(1)
        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setFrameShape(QScrollArea.NoFrame); scroll.setWidget(inner)
        self.error = QLabel(); self.error.setTextFormat(Qt.RichText); self.error.setWordWrap(True); self.error.linkActivated.connect(lambda _link: self.save())
        self.v.addWidget(scroll, 1); self.v.addWidget(self.error)

    def redraw(self, doc):
        self.doc = doc; lg = doc['legal']; e = lambda x: html.escape(str(x), quote=True)   # porter's names and URLs are text, not markup
        self.notice.setText(lg['text'])
        self.links.setText('<br>'.join(f'<a href="{e(url)}">{e(name)}</a>' for name, url in lg['links'].items()))
        self.ok = step(doc, 'legal')['ok']; self.label()

    def label(self): self.setButtonText(QWizard.NextButton, 'Next' if self.ok else 'Accept and continue')

    def validatePage(self):   # Accept and continue: save first, move on once porter has it
        if self.ok or self.wizard().jumping: return True
        self.save(); return False

    def save(self):
        b = self.wizard().button(QWizard.NextButton); b.setEnabled(False); b.setText('saving…'); self.error.setText('')
        call_json(self, ['config', 'legal', str(self.doc['legal']['version']), '--json'], self.saved)

    def saved(self, obj, code, fail):
        z = self.wizard(); b = z.button(QWizard.NextButton); b.setEnabled(True)
        if fail: self.label(); self.error.setText(failed(fail)); return
        self.ok = True; self.label(); z.win.recheck(); z.next()


class StepPage(Page):   # porter's detail for its step, and the fix while it is not ok; 03-12, 03-11 and 03-10 add the controls
    SID = ''

    def __init__(self, heading, stretch=True):
        super().__init__(heading); self.detail = body(); self.fix = body()
        self.v.addWidget(self.detail); self.v.addWidget(self.fix)
        if stretch: self.v.addStretch(1)

    def redraw(self, doc):
        st = step(doc, self.SID); self.detail.setText(st.get('detail') or ''); self.fix.setText(st.get('fix') or ''); self.fix.setVisible(not st['ok'] and bool(st.get('fix')))


class Elided(QLabel):   # a path in the fixed font, elided in the middle to the width it gets, the full path in the tooltip
    def __init__(self, full):
        super().__init__(full); self.full = full; self.setFont(mono()); self.setTextFormat(Qt.PlainText); self.setToolTip(full)
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred); self.setMinimumWidth(80)

    def resizeEvent(self, e): super().resizeEvent(e); self.setText(self.fontMetrics().elidedText(self.full, Qt.ElideMiddle, self.width()))


class KeyRow(QWidget):   # one found file: ✓/✗ in its colour, the path, porter's detail; nothing else of the entry is read (D-06: never a key value)
    def __init__(self, e):
        super().__init__(); h = QHBoxLayout(self); h.setContentsMargins(8, 4, 8, 4); h.setSpacing(8); self.e = e
        self.glyph = QLabel('✓' if e['ok'] else '✗'); self.glyph.setStyleSheet(f"color: {colour(self, 'ok' if e['ok'] else 'bad')}")
        self.path = Elided(str(e['path'])); self.detail = QLabel(e.get('detail') or ''); self.detail.setTextFormat(Qt.PlainText)
        h.addWidget(self.glyph); h.addWidget(self.path, 1); h.addWidget(self.detail)


def state(src, txt, text, on):   # a saving source's look; a row may have been redrawn away meanwhile, and then there is nothing left to mark
    try: txt.setText(text); src.setEnabled(on)
    except RuntimeError: pass


class KeysPage(Page):   # D-05/D-06: the files porter found with its verdict, and the result line for the configured file; porter reads the file, this page never does
    def __init__(self):
        super().__init__('Your prod.keys')
        self.v.addWidget(body('nx2android reads your games with the keys from your own Switch. The file stays where it is; only its location is saved.'))
        self.list = QListWidget(); self.list.itemSelectionChanged.connect(self.pick)   # selection, not current item: focusing the list must not save its first row
        self.empty = body('No prod.keys found in the usual emulator folders. Choose your file with Browse….')
        self.browse = QPushButton('Browse…'); self.browse.clicked.connect(self.choose)   # D-06: always there, whatever porter found
        self.result = body(); self.retry = None
        self.error = QLabel(); self.error.setTextFormat(Qt.RichText); self.error.setWordWrap(True); self.error.linkActivated.connect(lambda _link: self.retry and self.retry())
        col = QVBoxLayout(); col.setSpacing(8); col.addWidget(self.list, 1); col.addWidget(self.empty); col.addWidget(self.error)
        h = QHBoxLayout(); h.setSpacing(8); h.addLayout(col, 1); h.addWidget(self.browse, 0, Qt.AlignTop)
        self.v.addLayout(h, 1); self.v.addWidget(self.result)   # the list scrolls on its own, so the button row stays in view

    def redraw(self, doc):
        st = step(doc, 'keys'); found = st.get('found') or []
        self.list.blockSignals(True); self.list.clear()
        for e in found:
            it = QListWidgetItem(self.list); r = KeyRow(e); it.setSizeHint(r.sizeHint()); self.list.setItemWidget(it, r)
        self.list.blockSignals(False); self.list.setVisible(bool(found)); self.empty.setVisible(not found)
        p = st.get('path') or ''; fix = st.get('fix') if not st['ok'] else ''
        self.result.setText((f'{p}: ' if p else '') + (st.get('detail') or '') + (f'. {fix}' if fix else ''))   # Copywriting "Keys bad file": `<path>: <detail>. <fix>`

    def pick(self):   # an ok row saves itself; a not-ok one only stays selected
        r = next((self.list.itemWidget(it) for it in self.list.selectedItems()), None)
        if r and r.e['ok']: self.save(str(r.e['path']), r, r.detail, r.e.get('detail') or '')

    def choose(self):   # any file, saved as a path for porter to check; a cancelled dialog does nothing
        path, _ = QFileDialog.getOpenFileName(self, 'Choose your prod.keys', '', 'prod.keys (*.keys);;All files (*)')
        if path: self.save(path, self.browse, self.browse, 'Browse…')

    def save(self, path, src, txt, idle):   # the one place that sends config keys: its source (a row or Browse…) reads saving… and is disabled until porter answers
        state(src, txt, 'saving…', False); self.error.setText('')

        def saved(_obj, _code, fail):
            state(src, txt, idle, True)
            if fail: self.retry = lambda: self.save(path, src, txt, idle); self.error.setText(failed(fail)); return   # stay here; Next is never disabled
            self.wizard().win.recheck()   # the next setup answer redraws this page with porter's verdict
        call_json(self, ['config', 'keys', path, '--json'], saved)


class ToolsPage(StepPage):
    SID = 'tools'
    def __init__(self): super().__init__('Tools for building the app')


def model(r):   # adb's `model:Lenovo_TB320FC device:…` as `Lenovo TB320FC`, else the serial
    m = next((kv[6:] for kv in (r.get('info') or '').split() if kv.startswith('model:')), '')
    return m.replace('_', ' ') or r['serial']


class DeviceRow(QWidget):   # glyph, model or serial, adb's own state text in the fixed font (testers quote it), porter's fix under it; all plain text (T-03-31)
    def __init__(self, r):
        super().__init__(); self.r = r; g = QHBoxLayout(self); g.setContentsMargins(8, 4, 8, 4); g.setSpacing(8)
        mark, role = STATE_GLYPH.get(r['state'], ('–', 'note'))
        self.glyph = QLabel(mark); self.glyph.setStyleSheet(f'color: {colour(self, role)}'); g.addWidget(self.glyph, 0, Qt.AlignTop)
        col = QVBoxLayout(); col.setSpacing(4); top = QHBoxLayout(); top.setSpacing(8)
        self.name = body(model(r)); self.detail = body(r.get('detail') or r['state']); self.detail.setFont(mono())
        self.fix = body(r.get('fix') or ''); self.fix.setTextInteractionFlags(Qt.TextSelectableByMouse); self.fix.setVisible(bool(r.get('fix')))
        top.addWidget(self.name); top.addWidget(self.detail, 1); col.addLayout(top); col.addWidget(self.fix); g.addLayout(col, 1)


class DevicePage(StepPage):   # D-15, DEV-01: devices --json while this page shows, one call at a time; porter's adb step text above the steps
    SID = 'device'

    def __init__(self):
        super().__init__('Connect your Android device', stretch=False); self.gen, self.busy, self.rows = 0, False, None
        self.v.addWidget(body('1. On the device, open Settings › About and tap Build number seven times. 2. Open Settings › System › Developer options and turn on '
                              'USB debugging. 3. Connect it by USB and tap Allow on the "Allow USB debugging?" prompt.'))
        self.list = QListWidget(); self.empty = body('Looking again every few seconds…')
        self.v.addWidget(self.list, 1); self.v.addWidget(self.empty); self.list.hide()   # the list scrolls on its own, so the button row stays in view
        self.setButtonText(QWizard.NextButton, 'Skip: install later')

    def here(self): z = self.wizard(); return z is not None and z.isVisible() and z.currentPage() is self

    def moved(self, here):   # a turn later, so go() walking past this page to a later one sends nothing
        self.stop()
        if here: QTimer.singleShot(0, self, self.poll)

    def stop(self): self.gen += 1   # late answers and timers of an earlier visit do nothing

    def poll(self):   # the next call is scheduled from this one's answer: at most one outstanding (T-03-32)
        if self.busy or not self.here(): return
        self.busy, gen = True, self.gen

        def got(rows, _code, fail):
            self.busy = False
            if gen != self.gen: self.poll(); return   # left meanwhile (and maybe back): only the current visit's chain goes on
            self.draw(rows, fail); QTimer.singleShot(POLL_MS, self, lambda: gen == self.gen and self.poll())
        call_json(self, ['devices', '--json'], got)

    def draw(self, rows, fail):   # a failure keeps the last list and shows its cause in the empty row; polling goes on
        if fail: self.empty.setText(cause(fail)); self.empty.show(); return
        if rows != self.rows:
            self.rows = rows; self.list.clear()
            for r in rows:
                it = QListWidgetItem(self.list); w = DeviceRow(r); it.setSizeHint(w.sizeHint()); self.list.setItemWidget(it, w)
        self.list.setVisible(bool(rows)); self.empty.setText('No device found yet. Looking again every few seconds…'); self.empty.setVisible(not rows)
        self.setButtonText(QWizard.NextButton, 'Next' if any(r['state'] == 'device' for r in rows) else 'Skip: install later')


class DonePage(Page):
    def __init__(self): super().__init__('Setup is ready'); self.v.addStretch(1)

    def redraw(self, doc): self.head.setText('Setup is ready' if doc['ready'] else 'Setup is not finished')


def fill_checks(table, doc):   # the Setup tab's checklist: porter's check rows drawn as before (✓ / ✗ / –), then each soft note as a '!' row
    table.setRowCount(0)
    rows = [(('✓', '#2e7d32') if r['ok'] else ('✗', '#c62828') if r['required'] else ('–', '#ef6c00'), r['name'],
             r['detail'] + (f'  →  {r["fix"]}' if r['fix'] and not r['ok'] else '')) for r in doc.get('checks') or []]
    rows += [(('!', colour(table, 'note')), 'Note', n) for n in doc.get('notes') or []]
    for (glyph, col), name, text in rows:
        i = table.rowCount(); table.insertRow(i)
        mark = QTableWidgetItem(glyph); mark.setForeground(QColor(col))
        table.setItem(i, 0, mark); table.setItem(i, 1, QTableWidgetItem(name)); table.setItem(i, 2, QTableWidgetItem(text))
