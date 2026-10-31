# The first-run wizard, the "setup is not finished" banner and the Setup tab's checklist rows, drawn from porter's `setup --json` on every launch (FRUN-03):
# the answer is kept in memory only; this module writes no file, keeps no "done" flag and reaches porter only through gui/runner.py (D-01).
# Any QMainWindow that gives it `fetch` (the Porter for tool downloads, under the window's close guard), `recheck()` (setup --json again, its answer to
# on_ready) and optionally `port_a_game()` can host it: today's gui/app.py Window and the new shell (gui/shell.py).
import html

from PySide6.QtCore import QObject, Qt, QTimer, QUrl
from PySide6.QtGui import QColor, QDesktopServices, QFontDatabase, QGuiApplication
from PySide6.QtWidgets import (QFileDialog, QHBoxLayout, QHeaderView, QLabel, QListWidget, QListWidgetItem, QProgressBar, QPushButton, QScrollArea, QSizePolicy,
                               QTableWidget, QTableWidgetItem, QToolBar, QVBoxLayout, QWidget, QWizard, QWizardPage)

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


def time_left(eta):   # D-26: porter's eta in s, rounded to whole minutes
    if eta is None: return ''
    if eta < 60: return 'less than a minute left'
    m = round(eta / 60); return f'{m} min left' if m < 60 else f'{m // 60} h {m % 60} min left'


def progress_line(ev, kn=''):   # `[k/n] <name> · <step> · <done> / <total> · <speed>/s · <time left>`, the parts porter did not send dropped; the tools page and the Setup tab
    b, done, total = ev.get('unit') == 'B', ev.get('done'), ev.get('total')
    line = ' · '.join(filter(None, (ev.get('name'), ev.get('step'), f'{size(done)} / {size(total)}' if b and done is not None and total else '',
                                    f'{size(ev["rate"])}/s' if b and ev.get('rate') else '', time_left(ev.get('eta')))))
    return ' '.join(filter(None, (kn, line)))


def run_kind(fetch):   # what the window's fetch run does: 'prepare', 'download', or None when nothing runs
    if not fetch.running() or fetch.p is None: return None
    a = fetch.p.arguments(); return 'prepare' if '--prepare' in a else 'download' if '--download' in a else None


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
        self.seen_device = None   # whether the device page's last answer had a ready device (None: it never answered); in memory only, for the done page
        self.setWindowTitle('nx2android setup'); self.setWizardStyle(QWizard.ClassicStyle)   # Classic on every host: no Mac watermark, follows the palette
        self.setOptions(QWizard.NoBackButtonOnStartPage | QWizard.HaveCustomButton1 | QWizard.NoCancelButton)
        self.setButtonText(QWizard.CustomButton1, 'Skip setup'); self.setButtonText(QWizard.FinishButton, 'Close setup')
        self.setButtonLayout([QWizard.CustomButton1, QWizard.Stretch, QWizard.BackButton, QWizard.NextButton, QWizard.FinishButton])
        self.customButtonClicked.connect(lambda _which: self.close())
        self.currentIdChanged.connect(self.moved)
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

    def moved(self, i):   # Back, Next or a jump: the device page polls only while it shows
        self.pages['device'].moved(i == PAGES.index('device')); self.primary(i)

    def primary(self, i):   # a page's own primary button (Port a game, Download all missing), when it shows one, is the default rather than Next or Close setup
        b = getattr(self.page(i), 'primary', lambda: None)()
        self.setOption(QWizard.NoDefaultButton, b is not None)   # else QWizard makes its own button the default again on every page switch
        if b: b.setDefault(True)

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


DOTNET_GUESS = 200 * 2**20   # .NET has no pinned size (porter/pins.py sends 0): about 200 MB
TOOL_KEYS = {'Android NDK': 'ndk', '.NET SDK': 'dotnet', 'adb': 'adb'}   # each tools row's config key, for Use my own…


class ToolCell(QWidget):   # the Tool column: the name, porter's note with '!' in the note colour (D-09), and for a row that is not ok its fix and command, selectable (D-25)
    def __init__(self, it):
        super().__init__(); v = QVBoxLayout(self); v.setContentsMargins(4, 4, 4, 4); v.setSpacing(2); bad = not it['ok']
        self.name = body(it['name']); self.fix = body(it.get('fix') or ''); self.command = body(it.get('command') or ''); self.command.setFont(mono())
        self.note = QLabel(f'<span style="color:{colour(self, "note")}">!</span> ' + html.escape(it.get('note') or '', quote=False))   # porter's text, escaped
        self.note.setTextFormat(Qt.RichText); self.note.setWordWrap(True)
        for x in (self.fix, self.command): x.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.note.setVisible(bool(it.get('note'))); self.fix.setVisible(bad and bool(it.get('fix'))); self.command.setVisible(bad and bool(it.get('command')))
        for x in (self.name, self.note, self.fix, self.command): v.addWidget(x)


class ToolsPage(StepPage):   # D-07, D-21, D-23..D-26: porter's tools rows; Download all missing and Cancel on the window's own fetch run, so its close guard covers it
    SID = 'tools'

    def __init__(self):
        super().__init__('Tools for building the app', stretch=False)
        self.doc, self.hooked, self.mine, self.kn, self.errors, self.log, self.error, self.prep, self.retry = None, False, None, '', [], None, None, None, None
        self.v.insertWidget(2, body('A port needs the Android NDK and the .NET SDK. adb is only needed to install on your device. Downloads go to your nx2android folder.'))
        t = self.table = QTableWidget(0, 6); t.setHorizontalHeaderLabels(['', 'Tool', 'Version', 'Source', 'Size or note', '']); t.verticalHeader().setVisible(False)
        t.setEditTriggers(QTableWidget.NoEditTriggers); t.setSelectionMode(QTableWidget.NoSelection)
        for i in range(6): t.horizontalHeader().setSectionResizeMode(i, QHeaderView.Stretch if i == 1 else QHeaderView.ResizeToContents)
        self.status = QLabel(); self.status.setWordWrap(True); self.plain = self.status.font(); self.status.linkActivated.connect(self.link)
        self.bar = QProgressBar(); self.bar.setRange(0, 1000); self.bar.hide()
        self.all_here = body('Every tool is here.')
        self.dl = QPushButton(); self.dl.setMinimumHeight(36); f = self.dl.font(); f.setBold(True); self.dl.setFont(f); self.dl.clicked.connect(self.press)
        row = QHBoxLayout(); row.setSpacing(8); row.addWidget(self.all_here, 1); row.addWidget(self.dl)
        self.v.addWidget(t, 1); self.v.addWidget(self.status); self.v.addWidget(self.bar); self.v.addLayout(row)   # the table scrolls; the button row stays in view

    def fetch(self): return self.wizard().win.fetch

    def redraw(self, doc):
        super().redraw(doc); self.doc = doc
        if not self.hooked:   # once; a closed wizard's page is a deleted QObject, which Qt disconnects
            self.hooked = True; self.fetch().event.connect(self.on_event); self.fetch().finished.connect(self.on_finished)
        items = step(doc, 'tools').get('items') or []; t = self.table; t.setRowCount(len(items)); self.prep = None
        for i, it in enumerate(items):
            mark, role = ('✓', 'ok') if it['ok'] else ('✗', 'bad') if it.get('required') else ('–', 'note')
            d = it.get('download')
            cells = (mark, '', it.get('version') or '', it.get('source') or '', (size(d['size']) if d['size'] else 'about 200 MB') if d and not it['ok'] else '')
            for c, text in enumerate(cells): t.setItem(i, c, QTableWidgetItem(text))
            t.item(i, 0).setForeground(QColor(colour(self, role))); t.setCellWidget(i, 1, ToolCell(it)); t.setCellWidget(i, 5, self.actions(it))
        t.resizeRowsToContents(); self.sync()

    def actions(self, it):   # D-23, D-25: Use my own… on a row that is not ok (with Copy command and Re-check when porter sends a command); Prepare .NET tools on an ok .NET row
        w = QWidget(); h = QHBoxLayout(w); h.setContentsMargins(4, 2, 4, 2); h.setSpacing(8); key = TOOL_KEYS.get(it['name'])

        def add(text, fn): b = QPushButton(text); b.clicked.connect(lambda _=False: fn(b)); h.addWidget(b); return b
        if not it['ok']:
            if it.get('command'): add('Copy command', lambda _b: self.copy_command(it)); add('Re-check', lambda _b: self.wizard().win.recheck())
            if key: add('Use my own…', lambda b: self.use_own(it, b))
        elif key == 'dotnet': self.prep = add('Prepare .NET tools', lambda _b: self.prepare())
        h.addStretch(1); return w

    def copy_command(self, it): QGuiApplication.clipboard().setText(it['command'])   # porter's literal command only (T-03-36)

    def use_own(self, it, b):   # the player's own tool: a folder for the NDK, a file for dotnet and adb; porter checks it on the next setup --json
        key = TOOL_KEYS[it['name']]
        path = QFileDialog.getExistingDirectory(self, 'Choose the Android NDK folder') if key == 'ndk' else QFileDialog.getOpenFileName(self, f'Choose {key}')[0]
        if path: self.save(key, path, b)

    def save(self, key, path, b):   # Use my own… reads saving… and is disabled until porter answers
        state(b, b, 'saving…', False); self.say('')

        def saved(_obj, _code, fail):
            state(b, b, 'Use my own…', True)
            if fail: self.retry = lambda: self.save(key, path, b); self.say(failed(fail), True); return
            self.wizard().win.recheck()   # the next setup answer redraws the row with porter's verdict
        call_json(self, ['config', key, path, '--json'], saved)

    def total(self):   # the pinned sizes of what porter can download, .NET's 0 counted as about 200 MB
        st = step(self.doc, 'tools'); can = st.get('downloadable') or []
        sizes = [(it.get('download') or {}).get('size') or 0 for it in st.get('items') or [] if it['name'] in can]
        guess = sum(not b for b in sizes); return ('about ' if guess else '') + size(sum(sizes) + guess * DOTNET_GUESS)

    def sync(self):   # the primary button: Cancel while the window's fetch runs (whoever started it), else Download all missing while porter offers a download
        f = self.fetch(); run, can = f.running(), self.doc and step(self.doc, 'tools').get('downloadable')
        self.dl.setText(('Cancel .NET preparation' if run_kind(f) == 'prepare' else 'Cancel download') if run else f'Download all missing ({self.total()})')
        self.dl.setVisible(bool(run or can)); self.all_here.setVisible(not run and not can); self.dl.setDefault(False)
        if self.prep: self.prep.setVisible(not run)
        z = self.wizard()
        if z.currentPage() is self: z.primary(z.currentId())

    def primary(self): return self.dl if self.dl.isVisibleTo(self) and not self.fetch().running() else None

    def say(self, text, rich=False, font=None):
        self.status.setTextFormat(Qt.RichText if rich else Qt.PlainText); self.status.setFont(font or self.plain); self.status.setText(text)

    def press(self): (self.cancel if self.fetch().running() else self.download)()

    def download(self): self.start(['tools', '--download', '--progress', 'json'], 'download')   # D-07: no license dialog, the legal notice covers them

    def prepare(self): self.start(['tools', '--prepare', '--progress', 'json'], 'prepare')   # D-24: restore and build the .NET tools once, so the first port finds them

    def start(self, args, kind):
        f = self.fetch()
        if f.running(): return   # one run on the window's fetch at a time
        self.mine, self.kn, self.errors, self.log, self.error = kind, '', [], None, None
        self.say(''); self.bar.setRange(0, 0); self.bar.show(); f.start(args); self.sync()

    def cancel(self): self.fetch().stop(); self.say('stopping…')   # "cancelled" only once finished says the tree is gone (Phase 1 D-05/D-09)

    def on_event(self, ev):
        e, f = ev.get('ev'), self.fetch(); self.sync()
        if e in ('stage', 'progress'):
            if e == 'stage': self.kn = f'[{ev["k"]}/{ev["n"]}]'
            if f.stopping: return   # stopping… stays until finished
            self.say(progress_line(ev, self.kn)); self.bar.show()
            if e == 'progress' and ev.get('frac') is not None: self.bar.setRange(0, 1000); self.bar.setValue(int(ev['frac'] * 1000))
            else: self.bar.setRange(0, 0)
        elif e == 'say' and ev.get('msg', '').startswith('[RED] '): self.errors.append(ev['msg'].removeprefix('[RED] '))
        elif e == 'log': self.log = ev.get('path')
        elif e == 'error': self.error = ev; self.log = ev.get('log') or self.log

    def on_finished(self, code):
        kind, self.mine = self.mine, None; self.bar.hide(); self.sync()
        if code == 130: self.say('cancelled. Download all missing resumes where it stopped.')
        elif code == 0:
            self.say('.NET tools are ready.' if kind == 'prepare' else '')
            if kind == 'download': QTimer.singleShot(0, self, self.prepare)   # a turn later: finished's other listeners see the download end first
        else: self.failure(kind)
        self.wizard().win.recheck()   # porter's verdict on each tool: what finished in a cancelled run shows ✓

    def failure(self, kind):   # porter's cause, escaped, with Open log: a download's in the problem colour (a hash mismatch in the fixed font so both hashes read
        # cleanly), a Prepare's as a '!' note, never a blocker (D-24): the first port prepares the tools itself
        msg = (self.error or {}).get('msg') or '\n'.join(self.errors) or ('the .NET preparation failed' if kind == 'prepare' else 'the download failed')
        text = html.escape(msg, quote=False).replace('\n', '<br>'); link = ' &nbsp;<a href="log">Open log</a>' if self.log else ''
        if kind == 'prepare': self.say(f'<span style="color:{colour(self, "note")}">!</span> {text}{link}', True)
        else: self.say(f'<span style="color:{colour(self, "bad")}">{text}</span>{link}', True, mono() if 'not the expected' in msg else None)

    def link(self, href):   # the status line's links: the failed run's log, or Retry of a failed Use my own… save
        if href == 'log' and self.log: QDesktopServices.openUrl(QUrl.fromLocalFile(self.log))
        elif href == 'retry' and self.retry: self.retry()


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
        self.list = QListWidget(); self.list.itemSelectionChanged.connect(self.pick); self.empty = body('Looking again every few seconds…'); self.error = body()
        self.v.addWidget(self.list, 1); self.v.addWidget(self.empty); self.v.addWidget(self.error); self.list.hide()   # the list scrolls on its own, so the button row stays in view
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
        rows = rows or []; self.wizard().seen_device = any(r['state'] == 'device' for r in rows)
        if rows != self.rows:   # rebuilt only when adb's answer changed, keeping the selected serial
            keep = {self.list.itemWidget(it).r['serial'] for it in self.list.selectedItems()}; self.rows = rows
            self.list.blockSignals(True); self.list.clear()
            for r in rows:
                it = QListWidgetItem(self.list); w = DeviceRow(r); it.setSizeHint(w.sizeHint()); self.list.setItemWidget(it, w); it.setSelected(r['serial'] in keep)
            self.list.blockSignals(False)
        self.list.setVisible(bool(rows)); self.empty.setText('No device found yet. Looking again every few seconds…'); self.empty.setVisible(not rows)
        self.setButtonText(QWizard.NextButton, 'Next' if self.wizard().seen_device else 'Skip: install later')

    def pick(self):   # D-15: with several ready devices the selected one is saved for installs; with one there is nothing to choose
        r = next((self.list.itemWidget(it).r for it in self.list.selectedItems()), None)
        if not r or r['state'] != 'device' or sum(x['state'] == 'device' for x in self.rows) < 2: return
        self.error.setText('')
        call_json(self, ['config', 'device', r['serial'], '--json'], lambda _obj, _code, fail: self.error.setText(cause(fail) if fail else ''))


NAMES = {'legal': 'Notice', 'keys': 'prod.keys', 'tools': 'Tools', 'device': 'adb'}   # the summary's name for each of porter's step ids


class Line(QWidget):   # a summary row: the glyph in its colour, then plain, word-wrapped text
    def __init__(self, mark, role, text):
        super().__init__(); h = QHBoxLayout(self); h.setContentsMargins(0, 0, 0, 0); h.setSpacing(8)
        self.glyph = QLabel(mark); self.glyph.setStyleSheet(f'color: {colour(self, role)}'); self.text = body(text)
        h.addWidget(self.glyph, 0, Qt.AlignTop); h.addWidget(self.text, 1)


class DonePage(Page):   # D-28: what is ready, porter's notes, the games that play today, the Linux menu entry (D-20) and the first port
    def __init__(self):
        super().__init__('Setup is ready'); self.doc, self.lines = None, []
        inner = QWidget(); iv = QVBoxLayout(inner); iv.setContentsMargins(0, 0, 0, 0); iv.setSpacing(8)
        self.summary = QVBoxLayout(); self.summary.setSpacing(8); iv.addLayout(self.summary); iv.addSpacing(8)
        self.games = QLabel('Games that play today'); f = self.games.font(); f.setBold(True); self.games.setFont(f); self.playable = body()
        self.menu_result = body()
        for x in (self.games, self.playable, self.menu_result): iv.addWidget(x)
        iv.addStretch(1); self.games.hide(); self.playable.hide()
        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setFrameShape(QScrollArea.NoFrame); scroll.setWidget(inner)   # many titles scroll; the buttons stay
        self.menu = QPushButton('Add to app menu'); self.menu.clicked.connect(self.add_to_menu); self.menu.hide()
        self.port = QPushButton('Port a game'); self.port.setDefault(True); self.port.setMinimumHeight(36); self.port.clicked.connect(self.port_a_game)
        f = self.port.font(); f.setBold(True); f.setPointSizeF(f.pointSizeF() + 2); self.port.setFont(f)
        row = QHBoxLayout(); row.setSpacing(8); row.addWidget(self.menu); row.addStretch(1); row.addWidget(self.port)
        self.v.addWidget(scroll, 1); self.v.addSpacing(16); self.v.addLayout(row)   # 16 + 16: UI-SPEC xl, 32 px above the primary row

    def redraw(self, doc):
        self.doc = doc; self.head.setText('Setup is ready' if doc['ready'] else 'Setup is not finished')
        self.menu.setVisible(bool((doc.get('desktop') or {}).get('offer')))
        self.port.setVisible(callable(getattr(self.wizard().win, 'port_a_game', None)))   # the new shell has no port view yet (Phase 4)
        self.draw_summary(doc)

    def initializePage(self): self.draw_summary(self.doc); self.load_playable()   # the device page may have answered since the last redraw

    def draw_summary(self, doc):   # one row per step, then each note with '!'; "No device yet" only when the device page asked and saw no ready device
        for x in self.lines: x.setParent(None)
        no_device = ['No device yet: port now, install later.'] if self.wizard().seen_device is False else []
        rows = [(('✓', 'ok') if st['ok'] else ('!', 'note') if st.get('soft') else ('✗', 'bad'), f"{NAMES.get(st['id'], st['id'])}: {st.get('detail') or ''}")
                for st in doc['steps']] + [(('!', 'note'), n) for n in list(doc.get('notes') or []) + no_device]
        self.lines = [Line(mark, role, text) for (mark, role), text in rows]
        for x in self.lines: self.summary.addWidget(x)

    def load_playable(self):   # porter's profiles whose status is playable, sorted; the section stays hidden while there are none or the call failed
        def got(obj, _code, _fail):
            names = sorted(e['name'] for e in obj or [] if e.get('status') == 'playable')
            self.playable.setText('\n'.join(names)); self.games.setVisible(bool(names)); self.playable.setVisible(bool(names))
        call_json(self, ['profiles', '--json'], got)

    def add_to_menu(self):   # D-20: the menu entry is written on this press only, and porter offers it only in the Linux bundle (T-03-33)
        state(self.menu, self.menu, 'saving…', False); self.menu_result.setText('')

        def got(_obj, _code, fail):
            state(self.menu, self.menu, 'Add to app menu', True); self.menu_result.setText(cause(fail) if fail else 'Added to the app menu.')
        call_json(self, ['desktop-entry', '--install', '--json'], got)

    def primary(self): return self.port if self.port.isVisibleTo(self) else None

    def port_a_game(self): z = self.wizard(); win = z.win; z.close(); win.port_a_game()


def fill_checks(table, doc):   # the Setup tab's checklist: porter's check rows drawn as before (✓ / ✗ / –), then each soft note as a '!' row
    table.setRowCount(0)
    rows = [(('✓', '#2e7d32') if r['ok'] else ('✗', '#c62828') if r['required'] else ('–', '#ef6c00'), r['name'],
             r['detail'] + (f'  →  {r["fix"]}' if r['fix'] and not r['ok'] else '')) for r in doc.get('checks') or []]
    rows += [(('!', colour(table, 'note')), 'Note', n) for n in doc.get('notes') or []]
    for (glyph, col), name, text in rows:
        i = table.rowCount(); table.insertRow(i)
        mark = QTableWidgetItem(glyph); mark.setForeground(QColor(col))
        table.setItem(i, 0, mark); table.setItem(i, 1, QTableWidgetItem(name)); table.setItem(i, 2, QTableWidgetItem(text))
