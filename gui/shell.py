# The new nx2android window, started in Phase 3 beside gui/app.py (`python -m gui.shell`; the bundle opens it by default from Phase 6): navigation on the
# left, a stack of views on the right, and the first-run gate from gui/firstrun.py, which today's window uses too (D-01).
# It keeps nothing on disk and reaches porter only through gui/runner.py: readiness is porter's `setup --json`, asked on every launch (FRUN-03).
import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QApplication, QGroupBox, QHBoxLayout, QHeaderView, QLabel, QListWidget, QMainWindow, QMessageBox, QPushButton, QStackedWidget,
                               QTableWidget, QVBoxLayout, QWidget)

from gui import firstrun
from gui.runner import Porter, call_json


class SetupView(QWidget):   # porter's setup checklist and Run setup; downloads, Cancel and Use my own… live in the wizard's tools page, on the shell's fetch
    def __init__(self, win):
        super().__init__(); self.win = win; v = QVBoxLayout(self)
        g = QGroupBox('Requirements'); gl = QVBoxLayout(g)
        top = QHBoxLayout(); self.run_btn = QPushButton('Run setup'); self.run_btn.clicked.connect(lambda: firstrun.open_setup(self.win)); top.addStretch(1); top.addWidget(self.run_btn); gl.addLayout(top)
        self.table = QTableWidget(0, 3); self.table.setHorizontalHeaderLabels(['', 'Requirement', 'Found']); self.table.verticalHeader().setVisible(False)   # as gui/app.py's SetupTab
        self.table.setEditTriggers(QTableWidget.NoEditTriggers); self.table.setSelectionMode(QTableWidget.NoSelection)
        hh = self.table.horizontalHeader(); hh.setSectionResizeMode(0, QHeaderView.ResizeToContents); hh.setSectionResizeMode(1, QHeaderView.ResizeToContents); hh.setSectionResizeMode(2, QHeaderView.Stretch)
        gl.addWidget(self.table)
        self.check_msg = QLabel(''); self.check_msg.setWordWrap(True); self.check_msg.setTextFormat(Qt.RichText)   # a failed check, with Retry
        self.check_msg.linkActivated.connect(lambda _link: self.win.recheck()); gl.addWidget(self.check_msg)
        v.addWidget(g); v.addStretch(1)

    def draw(self, doc): firstrun.fill_checks(self.table, doc); self.table.resizeRowsToContents()


class Shell(QMainWindow):   # the window protocol gui/firstrun.py draws on: fetch, recheck(), set_ready(); no port view yet, so no port_a_game (Phase 4)
    def __init__(self):
        super().__init__(); self.setWindowTitle('nx2android'); self.resize(980, 820); self.quitting = False
        self.nav = QListWidget(); self.nav.setMaximumWidth(200); self.views = QStackedWidget()
        self.fetch = Porter(self); self.setup = SetupView(self)
        for name, view in (('Setup', self.setup),): self.nav.addItem(name); self.views.addWidget(view)
        self.nav.currentRowChanged.connect(self.views.setCurrentIndex); self.nav.setCurrentRow(0)
        body = QWidget(); h = QHBoxLayout(body); h.addWidget(self.nav); h.addWidget(self.views, 1); self.setCentralWidget(body)
        firstrun.attach(self); self.fetch.finished.connect(self.run_ended)
        self.recheck()

    def recheck(self):   # setup --json again; its answer goes to the Setup view and firstrun.on_ready
        self.setup.check_msg.setText('')   # a Retry link is gone before the new call
        def got(doc, code, fail):   # setup --json exits 1 when not ready: its document is still the answer
            self.setup.check_msg.setText(firstrun.failed(fail) if fail else '')
            if fail: self.setup.table.setRowCount(0); self.set_ready(False); return
            self.set_ready(bool(doc.get('ready')), doc)
        call_json(self, ['setup', '--json'], got)

    def set_ready(self, ok, doc=None):
        if doc is not None: self.setup.draw(doc)
        firstrun.on_ready(self, doc)

    # the close guard, gui/app.py Window's shape: never orphan a download (Phase 1 D-05/D-09: the window goes only once the whole tree is gone)
    def runs(self): return [p for p in (self.fetch,) if p.running()]

    def run_ended(self, _code):   # Stop and quit: the window closes itself once nothing runs
        if self.quitting and not self.runs(): self.close()

    def ask_stop(self):
        box = QMessageBox(QMessageBox.Warning, 'nx2android', 'A tool download is still running. Stop it and quit?', parent=self)
        stop = box.addButton('Stop and quit', QMessageBox.DestructiveRole); keep = box.addButton('Keep running', QMessageBox.RejectRole)
        box.setDefaultButton(keep); box.exec()
        return box.clickedButton() is stop

    def closeEvent(self, e):
        runs = self.runs()
        if not runs: e.accept(); return
        e.ignore()
        if self.quitting or not self.ask_stop(): return   # already stopping, or Keep running
        self.quitting = True
        for p in runs: p.stop()


def main(argv):
    app = QApplication(argv); app.setApplicationName('nx2android'); app.setStyle('Fusion')
    w = Shell(); w.show()
    return app.exec()


if __name__ == '__main__':
    # PySide6 6.12 drops a reference to True on each signal emit; on 3.11 that aborts the process (bool_dealloc)
    if sys.version_info < (3, 12): sys.exit(f'[RED] the GUI needs Python 3.12 or later (this is {sys.version.split()[0]}); the CLI, python -m porter, runs on 3.11')
    sys.exit(main(sys.argv))
