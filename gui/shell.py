# The new nx2android window, started in Phase 3 beside gui/app.py (`python -m gui.shell`; the bundle opens it by default from Phase 6): navigation on the
# left, a stack of views on the right, and the first-run gate from gui/firstrun.py, which today's window uses too (D-01).
# It keeps nothing on disk and reaches porter only through gui/runner.py: readiness is porter's `setup --json`, asked on every launch (FRUN-03).
import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QHBoxLayout, QLabel, QListWidget, QMainWindow, QStackedWidget, QVBoxLayout, QWidget

from gui import firstrun
from gui.runner import Porter, call_json


class SetupView(QWidget):   # porter's setup checklist
    def __init__(self, win):
        super().__init__(); self.win = win; v = QVBoxLayout(self)
        self.check_msg = QLabel(''); self.check_msg.setWordWrap(True); self.check_msg.setTextFormat(Qt.RichText)   # a failed check, with Retry
        self.check_msg.linkActivated.connect(lambda _link: self.win.recheck()); v.addWidget(self.check_msg); v.addStretch(1)


class Shell(QMainWindow):   # the window protocol gui/firstrun.py draws on: fetch, recheck(), set_ready(); no port view yet, so no port_a_game (Phase 4)
    def __init__(self):
        super().__init__(); self.setWindowTitle('nx2android'); self.resize(980, 820)
        self.nav = QListWidget(); self.nav.setMaximumWidth(200); self.views = QStackedWidget()
        self.fetch = Porter(self); self.setup = SetupView(self)
        for name, view in (('Setup', self.setup),): self.nav.addItem(name); self.views.addWidget(view)
        self.nav.currentRowChanged.connect(self.views.setCurrentIndex); self.nav.setCurrentRow(0)
        body = QWidget(); h = QHBoxLayout(body); h.addWidget(self.nav); h.addWidget(self.views, 1); self.setCentralWidget(body)
        firstrun.attach(self)
        self.recheck()

    def recheck(self):   # setup --json again; its answer goes to the Setup view and firstrun.on_ready
        self.setup.check_msg.setText('')   # a Retry link is gone before the new call
        def got(doc, code, fail):   # setup --json exits 1 when not ready: its document is still the answer
            self.setup.check_msg.setText(firstrun.failed(fail) if fail else '')
            if fail: self.set_ready(False); return
            self.set_ready(bool(doc.get('ready')), doc)
        call_json(self, ['setup', '--json'], got)

    def set_ready(self, ok, doc=None): firstrun.on_ready(self, doc)


def main(argv):
    app = QApplication(argv); app.setApplicationName('nx2android'); app.setStyle('Fusion')
    w = Shell(); w.show()
    return app.exec()


if __name__ == '__main__':
    # PySide6 6.12 drops a reference to True on each signal emit; on 3.11 that aborts the process (bool_dealloc)
    if sys.version_info < (3, 12): sys.exit(f'[RED] the GUI needs Python 3.12 or later (this is {sys.version.split()[0]}); the CLI, python -m porter, runs on 3.11')
    sys.exit(main(sys.argv))
