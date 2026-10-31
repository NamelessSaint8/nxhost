# The first-run wizard, the "setup is not finished" banner and the Setup tab's checklist rows, drawn from porter's `setup --json` on every launch (FRUN-03).
# Interface stub (TDD RED): the bodies land with the tests that need them.
from gui.runner import call_json

PAGES = ('legal', 'keys', 'tools', 'device', 'done')


def attach(win): pass


def on_ready(win, doc): pass


def open_setup(win, start=None): pass


def fill_checks(table, doc): pass
