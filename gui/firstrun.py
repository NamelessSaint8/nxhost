# The first-run wizard, the "setup is not finished" banner and the Setup tab's checklist rows, drawn from porter's `setup --json` on every launch (FRUN-03):
# the answer is kept in memory only; this module writes no file, keeps no "done" flag and reaches porter only through gui/runner.py (D-01).
# Any QMainWindow that gives it `fetch` (the Porter for tool downloads, under the window's close guard), `recheck()` (setup --json again, its answer to
# on_ready) and optionally `port_a_game()` can host it: today's gui/app.py Window and the new shell (gui/shell.py).
import html

from PySide6.QtCore import QObject, Qt
from PySide6.QtGui import QColor, QFontDatabase
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QTableWidgetItem, QToolBar, QWidget

from gui.runner import call_json

# (light, dark) per role, UI-SPEC Color: note #9a5b00 replaces #ef6c00 (3.08:1 on white); each pair measured at 4.99:1 or more on its background
COLOUR = {'ok': ('#2e7d32', '#81c784'), 'bad': ('#c62828', '#ef9a9a'), 'note': ('#9a5b00', '#ffb74d'), 'banner': ('#fff4e5', '#3d2e12')}
PAGES = ('legal', 'keys', 'tools', 'device', 'done')


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


def open_setup(win, start=None):
    win.first_run.start = start


def fill_checks(table, doc):   # the Setup tab's checklist: porter's check rows drawn as before (✓ / ✗ / –), then each soft note as a '!' row
    table.setRowCount(0)
    rows = [(('✓', '#2e7d32') if r['ok'] else ('✗', '#c62828') if r['required'] else ('–', '#ef6c00'), r['name'],
             r['detail'] + (f'  →  {r["fix"]}' if r['fix'] and not r['ok'] else '')) for r in doc.get('checks') or []]
    rows += [(('!', colour(table, 'note')), 'Note', n) for n in doc.get('notes') or []]
    for (glyph, col), name, text in rows:
        i = table.rowCount(); table.insertRow(i)
        mark = QTableWidgetItem(glyph); mark.setForeground(QColor(col))
        table.setItem(i, 0, mark); table.setItem(i, 1, QTableWidgetItem(name)); table.setItem(i, 2, QTableWidgetItem(text))
