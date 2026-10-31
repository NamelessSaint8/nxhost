---
phase: 03-host-toolchains-and-guided-first-run
plan: 07
subsystem: gui
tags: [gui, shell, first-run, arch-rules, close-guard]
status: complete

requires:
  - phase: 03-05
    provides: "gui/firstrun.py attach / on_ready / open_setup / fill_checks / failed, the window protocol (fetch, recheck, set_ready)"
  - phase: 01
    provides: "gui/runner.py Porter.stop (whole tree) and call_json"
provides:
  - "gui/shell.py: Shell(QMainWindow) with nav, views, fetch, recheck(), set_ready(ok, doc), runs(), run_ended(), ask_stop(), closeEvent; SetupView (Run setup, checklist table, check_msg with Retry); main(argv); `python -m gui.shell`"
  - "tests/arch_rules.py 5b: gui/firstrun.py and gui/shell.py import only gui.runner (+ gui.firstrun for the shell), PySide6 and the standard library, and have no open( / .write_text( / .write_bytes( / QSettings"
  - "tests/arch_rules.py rule 6: hyphenated subcommands, and call_json(<owner>, ['<cmd>' calls across gui/"
affects: [03-10 done page (no port_a_game on the shell), 03-11 tools page downloads on the shell's fetch, Phase 4 library view, Phase 6 bundle default]

actuals:
  tokens: 5900
  tasks: 2
  commits: 5
plan_head_before: dd83001ea4bab47ca86533d5dd1ec51c998b7bdc
plan_head_after: f200d18e3191ea87ca5cff9d30af07f517ef88ce

tech-stack:
  added: []
  patterns:
    - "A second QMainWindow implements firstrun's window protocol; the gate is attached, never copied"
    - "Import purity rule by AST: top-level name in sys.stdlib_module_names or PySide6, or an exact allowed dotted name (`from gui import x` read as gui.x)"

key-files:
  created:
    - gui/shell.py
    - tests/test_shell.py
  modified:
    - tests/arch_rules.py
    - docs/ARCHITECTURE.md

key-decisions:
  - "The shell's ask_stop() takes no argument (only a download can run in Phase 3); its text is 'A tool download is still running. Stop it and quit?'"
  - "The write check uses \\bopen\\( so firstrun's first_open( does not trip it; both first-run views get the import and the write check"
  - "The shell rule's name also says 'and writes no file'; it still begins 'gui/shell.py imports only' as the plan's grep needs"
  - "Rule 6 keeps its old fixed-name and owner-less call_json patterns and adds the owner form; nothing removed"

patterns-established:
  - "RED tests import a not-yet-written GUI module behind try/except so each test fails on an assertion, not on loading"

requirements-completed: [FRUN-02, FRUN-03]

coverage:
  - id: D1
    description: "`python -m gui.shell` opens a window with left navigation (Setup) that asks setup --json on launch and runs firstrun's banner and wizard unchanged"
    requirement: FRUN-02
    verification:
      - kind: unit
        ref: "tests/test_shell.py#Gate.test_banner_in_shell"
        status: pass
      - kind: unit
        ref: "tests/test_shell.py#Gate.test_wizard_in_shell"
        status: pass
      - kind: unit
        ref: "tests/test_shell.py#Gate.test_failed_no_gate"
        status: pass
      - kind: unit
        ref: "tests/test_shell.py#Gate.test_ready_quiet"
        status: pass
    human_judgment: false
  - id: D2
    description: "Setup view draws the checklist with firstrun.fill_checks; Run setup opens the wizard at the first step not ok"
    requirement: FRUN-02
    verification:
      - kind: unit
        ref: "tests/test_shell.py#SetupView.test_checklist"
        status: pass
      - kind: unit
        ref: "tests/test_shell.py#SetupView.test_run_setup"
        status: pass
    human_judgment: false
  - id: D3
    description: "Close guard: idle closes at once; during a download it asks once, stops the tree and closes after finished; Keep running keeps it"
    verification:
      - kind: unit
        ref: "tests/test_shell.py#Close.test_idle_close"
        status: pass
      - kind: unit
        ref: "tests/test_shell.py#Close.test_running_asks"
        status: pass
      - kind: unit
        ref: "tests/test_shell.py#Close.test_keep_running"
        status: pass
    human_judgment: false
  - id: D4
    description: "Arch rules keep gui/firstrun.py and gui/shell.py pure views (FRUN-03) and rule 6 covers hyphenated subcommands and call_json(<owner>, [...]) calls"
    requirement: FRUN-03
    verification:
      - kind: command
        ref: ".venv/bin/python tests/arch_rules.py"
        status: pass
      - kind: unit
        ref: "tests/test_architecture.py#Architecture.test_rules"
        status: pass
    human_judgment: false
  - id: D5
    description: "On a real macOS desktop with a fresh NX2A_HOME the shell opens with the Setup entry, the wizard opens over it at the legal page, and closing during a download asks first"
    human_judgment: true
    rationale: "The plan's human-check; offscreen tests cover the logic, not the real window manager and dialog"

duration: 3 min
completed: 2026-10-31
---

# Phase 3 Plan 07: The new GUI shell beside today's window Summary

**`python -m gui.shell` opens a second nx2android window (left navigation, a Setup view) that hosts gui/firstrun.py's gate unchanged, guards its tool download on close, and two new arch rules keep both first-run views free of porter imports and file writes.**

## Performance

- **Duration:** about 3 min of executor wall time (start 2026-10-31T16:22Z, end 2026-10-31T16:25Z)
- **Tasks:** 2
- **Files:** 2 created, 2 modified

## Accomplishments

- `gui/shell.py`: `Shell` sets up `fetch = Porter(self)`, a `SetupView`, `firstrun.attach(self)`, then `recheck()` (`call_json(self, ['setup', '--json'], …)` then `set_ready`, then `firstrun.on_ready`). It imports nothing from `gui.app`, and `gui/__main__.py` and `packaging/nx2android.py` are unchanged, so the bundle still opens today's window.
- `SetupView`: the Requirements group with **Run setup** (`firstrun.open_setup(win)`), the 3-column table set up as in `gui/app.py`'s SetupTab, and `check_msg`, whose Retry link calls `win.recheck()`. A failed call clears the table.
- Close guard in the shape of `gui/app.py`'s Window: `runs()`, `run_ended()`, `ask_stop()` ('Stop and quit' destructive, 'Keep running' default), and `closeEvent`, which asks once, stops through `Porter.stop` and closes from `finished`.
- `tests/arch_rules.py`: rule 5b for both views, and rule 6 widened (`add_parser\('([a-z-]+)'` plus `call_json(<owner>, ['<cmd>'`).
- `docs/ARCHITECTURE.md` names the shell and the new rules.

## Task Commits

1. **Task 1 RED:** `ebb4947` test(03-07): add failing tests for the new shell hosting the first-run gate
2. **Task 1 GREEN:** `070fefb` feat(03-07): python -m gui.shell opens the new window with the first-run gate
3. **Task 2 RED:** `1b5630d` test(03-07): add failing tests for the shell's Setup view and close guard
4. **Task 2 GREEN:** `c007d18` feat(03-07): the shell's Setup view, its close guard and the first-run view-purity rules
5. **Docs:** `f200d18` docs(03-07): name the new shell and the first-run view-purity rules in ARCHITECTURE.md

## TDD Gate Compliance

- **Task 1 RED:** `tests.test_shell.Gate.test_banner_in_shell` failed, and so did all 4 Gate tests, with `AssertionError: gui/shell.py does not exist`. The classifier returned `RED_EVIDENCE_OK` (unittest format). Semantic assessment: the target ran and failed on an assertion, not on a load error, because the import is guarded. The failure is that the whole feature is missing, which is the planned behaviour's absence for a new module.
- **Task 2 RED:** `tests.test_shell.Close.test_running_asks` failed with `AssertionError: True is not false`: the shell closed with a download running. `test_keep_running` failed the same way, and SetupView raised AttributeError on `table` / `run_btn`. The classifier returned `RED_EVIDENCE_OK`. Semantic assessment: the target failed on the planned assertion for the intended reason (no close guard yet). `test_idle_close` passed in RED as expected, since Qt accepts a close by default, and it stays as a guard.
- **GREEN:** after each GREEN commit, 9/9 test_shell tests pass and `discover tests` is green (363 tests).
- **Mutation check of the arch rules (by hand, reverted):** appending `import porter.config` to gui/firstrun.py made the firstrun rule FAIL (`porter.config`). Adding `from gui import app`, `open(`, `QSettings` and `call_json(self, ['no-such-cmd', …])` to gui/shell.py made the shell rule FAIL (`gui.app, QSettings, open(`) and rule 6 FAIL (`no-such-cmd`). Both files were restored before the commit.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - CLAUDE.md docs rule] Documented the new shell and rules in docs/ARCHITECTURE.md**
- **Found during:** after Task 2
- **Issue:** CLAUDE.md says a change's docs go with it when a layer's rules change. ARCHITECTURE.md described gui/firstrun.py's import limit as prose but not the second window or the checked rule.
- **Fix:** I added one sentence after the firstrun paragraph and a note in the layout listing (`python -m gui.shell`).
- **Files modified:** docs/ARCHITECTURE.md
- **Commit:** f200d18

**Total deviations:** 1 auto-fixed (Rule 2). **Impact:** a docs-only addition. No code scope changed.

## Known Stubs

None. The shell has a single navigation entry (Setup) by design in Phase 3: Phase 4 adds the library and Phase 5 the device manager.

## Issues Encountered

None.

## Next Phase Readiness

The 03-10 done page and the 03-11 tools page can run on the shell: it gives `fetch` and `recheck()` and leaves out `port_a_game`. The human check (a real macOS window with a fresh NX2A_HOME) is left for the end-of-phase UAT.

## Self-Check: PASSED

- FOUND: gui/shell.py, tests/test_shell.py
- FOUND: ebb4947, 070fefb, 1b5630d, c007d18, f200d18 (all ancestors of HEAD)
- Acceptance: `firstrun.attach(self)` count 1; `from gui.app` count 0; `gui/__main__.py` and `packaging/nx2android.py` unchanged; the PASS lines for the shell and firstrun rules each print once; `QSettings` in gui/shell.py count 0; `[a-z-]+` in arch_rules.py count 2
- Verification: `unittest tests.test_shell tests.test_firstrun tests.test_architecture` ran 33 tests OK; `unittest discover tests` ran 363 tests OK; `tests/arch_rules.py` reported all checks passed
