#!/usr/bin/env python3
"""Probe the Port view's two-target report headlessly, at the UI-SPEC's 980 px width.

Turns the three held-out visual checks in 11-UI-SPEC.md into numbers instead of eyeballing:

  1. the prefixed step line wraps instead of widening the window
  2. the Stage column stays readable with `Mac app · <long stage>` in it
  3. a long porter reason wraps and does not widen the window

It also prints the partial-success status line, so the wording can be read without a run.
Usage: .venv/bin/python probe_both.py [-v]
Exit status 1 when a check fails. Nothing is written; no porter process is started.
"""
import os, sys, tempfile
from pathlib import Path

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('NX2A_HOME', tempfile.mkdtemp(prefix='nx2a-probe-'))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget

import gui.app as A

WIDTH = 980   # UI-SPEC: the window width the held-out checks name
LONG_STEP = ('NDK android-ndk-r27c and then the whole Metal chain for the Mac app, a step long '
             'enough that it cannot sit on one line inside a 980 px window')
LONG_REASON = ('the Mac app could not be built: ' + 'the translation chain is locked to a Metal '
               'the build host does not carry, so pack_app.py refused before writing the bundle ' * 3).strip()


class Win(QWidget):
    """The little of the main window PortTab touches outside a run."""

    def set_ready(self, *_a, **_k):
        pass


def lines(label):
    fm = label.fontMetrics()
    return max(1, round(label.height() / max(1, fm.lineSpacing())))


def main():
    app = QApplication.instance() or QApplication([])
    win = Win()
    box = QVBoxLayout(win)
    tab = A.PortTab(win)
    box.addWidget(tab)
    win.resize(WIDTH, 820)
    win.show()
    app.processEvents()

    # A two-target run: both chains number their stages from k=1, so the stage keys must not collide.
    for platform in ('android', 'mac-app'):
        for k, name in ((1, 'extract 1.0.0'), (2, 'rewrite'), (3, 'host' if platform == 'mac-app' else 'Vulkan shaders')):
            tab.on_event({'ev': 'stage', 'k': k, 'n': 3, 'name': name, 'platform': platform})
    tab.on_event({'ev': 'stage', 'k': 3, 'n': 3, 'name': 'host', 'step': LONG_STEP, 'platform': 'mac-app'})
    app.processEvents()

    step, fm = tab.step, tab.step.fontMetrics()
    col = tab.stages.columnWidth(1)
    checks = [
        ('1. prefixed step line wraps', lines(step) >= 2 and step.sizeHint().width() <= step.width(),
         f'label {step.width()}x{step.height()} px, {lines(step)} line(s)'),
        ('2. window stayed at 980 px', win.width() <= WIDTH, f'window {win.width()} px'),
        ('3. Stage column readable', col < tab.stages.width() - 120,
         f'Stage column {col} px of {tab.stages.width()} px'),
        ('4. two chains kept apart', len(tab.items) == 6, f'{len(tab.items)} stage rows (expect 6)'),
    ]

    tab.on_event({'ev': 'result', 'log': None, 'targets': [
        {'platform': 'android', 'status': 'ok', 'out': '/tmp/Skyrim.apk', 'reason': ''},
        {'platform': 'mac-app', 'status': 'failed', 'out': '', 'reason': LONG_REASON},
    ]})
    app.processEvents()

    rows = tab.rows
    reason = rows[-1].reason if rows else None
    checks += [
        ('5. one row per target', len(rows) == 2, f'{len(rows)} rows'),
        ('6. long reason wraps', bool(reason) and reason.height() >= 2 * max(1, reason.fontMetrics().lineSpacing()),
         f'reason {getattr(reason, "width", lambda: 0)()}x{getattr(reason, "height", lambda: 0)()} px, {lines(reason) if reason else 0} line(s)'),
        ('7. result block fits 980 px', tab.results.width() <= WIDTH and win.width() <= WIDTH,
         f'results {tab.results.width()} px, window {win.width()} px'),
    ]

    tab.t0 = __import__('time').time() - 12   # a run sets this in run(); the probe fakes a 12 s run so hms() reads plausibly
    tab.on_finished(1)   # Android built, the Mac app failed: porter's exit is 1, something was produced
    app.processEvents()
    line = tab.step.text()
    checks.append(('8. partial-success line', line.startswith('finished in') and 'Mac app' in line and tab.prog.value() == 1000,
                   repr(line)))

    bad = [c for c in checks if not c[1]]
    for name, ok, detail in checks:
        print(f'{"PASS" if ok else "FAIL"}  {name}: {detail}')
    print(f'\n{len(checks) - len(bad)}/{len(checks)} checks passed')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
