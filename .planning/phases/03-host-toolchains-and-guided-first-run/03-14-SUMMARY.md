---
phase: 03-host-toolchains-and-guided-first-run
plan: 14
subsystem: gui
tags: [firstrun, wizard, quit-guard, layout, palette, dark-mode, gap-closure]
status: complete

requires:
  - phase: 03-host-toolchains-and-guided-first-run (03-10)
    provides: "DevicePage (devices --json poll, DeviceRow, empty line), DonePage"
  - phase: 03-host-toolchains-and-guided-first-run (03-11)
    provides: "ToolsPage on the window's fetch run, the Prepare chain after a download (D-24)"
  - phase: 03-host-toolchains-and-guided-first-run (03-05)
    provides: "Gate, attach() banner, fill_checks, failed(), the COLOUR table"
provides:
  - "PREPARED = '.NET tools are ready.' (Copywriting 'Prepare .NET tools done'), for 03-15's Setup tab"
  - "quitting(win); ToolsPage.on_finished and ToolsPage.start start no Prepare on a quitting window (WR-05)"
  - "DevicePage: trailing stretch toggled against the list in draw(), the steps on three lines, redraw() hides an ok step's detail"
  - "colour(None, key) from the application palette; failed() and fill_checks() through colour()"
  - "Gate.mark, Gate.paint(), Gate.eventFilter (PaletteChange restyles the banner and its '!'); Gate's unused start attribute dropped (IN-01)"
  - "tests: Tools.test_no_prepare_while_quitting, Device.test_layout_without_device, Device.test_ok_detail_hidden, Banner.test_failed_colour, Banner.test_follows_palette, SetupTab.test_check_colours"
affects: [03-15 Setup tab copy (PREPARED), 03-VERIFICATION re-run, 03-UI-REVIEW top fixes 1 and 3, 03-REVIEW WR-05 and IN-01]

actuals:
  tokens: 4800
  tasks: 3
  commits: 6
plan_head_before: a5285764515a2255d2376696223907f77066e588
plan_head_after: 3b5d7c3e2016feafc61dcce2970f6c7930911edb

tech-stack:
  added: []
  patterns:
    - "A host-window flag read with getattr(win, 'quitting', False), so any QMainWindow can host the wizard without declaring it"
    - "A QObject event filter on the host window that re-applies palette-derived stylesheets on QEvent.PaletteChange and lets the event go on"
    - "A trailing layout stretch whose factor is toggled with setStretch(count - 1, …) against a list that hides and shows"

key-files:
  created:
    - .planning/phases/03-host-toolchains-and-guided-first-run/tdd/03-14-t1-red.json
    - .planning/phases/03-host-toolchains-and-guided-first-run/tdd/03-14-t2-red.json
    - .planning/phases/03-host-toolchains-and-guided-first-run/tdd/03-14-t3-red.json
  modified:
    - gui/firstrun.py
    - tests/test_firstrun.py

key-decisions:
  - "03-14: the Prepare guard lives in ToolsPage.start as well as in the chain, so neither the automatic chain nor the Prepare .NET tools button can start a run on a window that is quitting"
  - "03-14: colour(None, key) reads QGuiApplication.palette(), so failed() keeps its one-argument signature for gui/shell.py and gui/app.py"
  - "03-14: the banner restyles on the host window's PaletteChange through an event filter (Gate.paint), not in on_ready, so a theme switch shows at once without a setup --json answer"

patterns-established:
  - "Offscreen layout tests compare each visible QLabel's height with heightForWidth(width) (sizeHint for a non-wrapping or empty label) plus 8 px"

requirements-completed: [FRUN-01, FRUN-02, DEV-01, TOOL-02]

coverage:
  - id: D1
    description: "Stop and quit as a wizard download ends 0: no tools --prepare starts, neither from the chain nor from the Prepare button; without a quit the chain and the button still start it"
    requirement: TOOL-02
    verification:
      - kind: automated
        ref: "tests/test_firstrun.py#Tools.test_no_prepare_while_quitting"
        status: pass
      - kind: automated
        ref: "tests/test_firstrun.py#Tools.test_prepare_chain"
        status: pass
      - kind: automated
        ref: "tests/test_firstrun.py#Tools.test_prepare_button"
        status: pass
    human_judgment: false
  - id: D2
    description: "With no device the device page's heading sits at the top margin, every label keeps its natural height, the spare height goes below them, and to the list once devices show; the steps read as three numbered lines"
    requirement: DEV-01
    verification:
      - kind: automated
        ref: "tests/test_firstrun.py#Device.test_layout_without_device"
        status: pass
      - kind: automated
        ref: "tests/test_firstrun.py#Device.test_instructions"
        status: pass
    human_judgment: false
  - id: D3
    description: "An ok device step hides porter's detail (the adb path); a not-ok step still shows its detail and fix"
    requirement: DEV-01
    verification:
      - kind: automated
        ref: "tests/test_firstrun.py#Device.test_ok_detail_hidden"
        status: pass
      - kind: automated
        ref: "tests/test_firstrun.py#Wizard.test_page_text"
        status: pass
    human_judgment: false
  - id: D4
    description: "The Setup checklist glyphs and failed() take their colours from the COLOUR table for the current light or dark palette"
    requirement: FRUN-01
    verification:
      - kind: automated
        ref: "tests/test_firstrun.py#SetupTab.test_check_colours"
        status: pass
      - kind: automated
        ref: "tests/test_firstrun.py#Banner.test_failed_colour"
        status: pass
    human_judgment: false
  - id: D5
    description: "A palette change while the app runs restyles the banner and its '!'"
    requirement: FRUN-02
    verification:
      - kind: automated
        ref: "tests/test_firstrun.py#Banner.test_follows_palette"
        status: pass
    human_judgment: false
  - id: D6
    description: "A real macOS light/dark switch (system appearance change) restyles the banner; the test drives it by setting the window palette"
    requirement: FRUN-02
    human_judgment: true
    rationale: "The test sets a palette on the window; whether each host's system theme switch reaches the window as a PaletteChange was not run on a desktop session"

duration: 10 min
completed: 2026-10-31
---

# Phase 3 Plan 14: Wizard quit guard, device page layout and palette colours Summary

**The wizard starts no .NET Prepare on a window that is quitting (WR-05), the device page with no device keeps its labels together under the heading with the steps on three lines, and the checklist, error text and banner take their colours from the COLOUR table and follow a light or dark switch while the app runs.**

## Performance

- **Duration:** about 10 min
- **Started:** 2026-10-31T18:48:36Z
- **Completed:** 2026-10-31
- **Tasks:** 3 of 3
- **Files modified:** 2 source/test files, plus 3 RED evidence records

## Accomplishments

- WR-05: `ToolsPage.on_finished` chains the Prepare after a download only while `quitting(win)` is false, and `ToolsPage.start` refuses on a quitting window, so the Prepare .NET tools button cannot start one either. `PREPARED` holds the done line for 03-15.
- UI-REVIEW top fix 1: `DevicePage` ends with a stretch whose factor `draw()` sets to 1 while the list is hidden and 0 once rows show. The steps are three lines. `DevicePage.redraw` hides an ok step's detail, which is only the adb path. A re-render at 760x600 (`scratchpad/ui-shots-14/wiz-device.png`) shows the heading at the top margin, the three steps, then the empty line, with the free space below.
- UI-REVIEW top fix 3: `colour(None, key)` reads the application palette. `failed()` and `fill_checks()` use `colour()`, and the retired `#ef6c00` is gone. `Gate.paint()` styles the banner and `Gate.mark`; `Gate.eventFilter` repaints on the window's `PaletteChange`. Outside the COLOUR table and its comment, the file has no hex colour literal.
- IN-01: Gate's unused `start` attribute is dropped.

## Task Commits

1. **Task 1: no Prepare on a quitting window (WR-05)**: `daaf65a` (test, RED), `86f0a24` (fix, GREEN)
2. **Task 2: device page layout, three-line steps, ok detail hidden**: `a1e4156` (test, RED), `70a9cc3` (feat, GREEN)
3. **Task 3: COLOUR table everywhere, banner follows the palette, IN-01**: `5c1cc96` (test, RED), `3b5d7c3` (feat, GREEN)

## TDD Gate Compliance

- **t1 RED** (`tdd/03-14-t1-red.json`, RED_EVIDENCE_OK): `Tools.test_no_prepare_while_quitting` failed on the start-call list. `fetch.start` was called again with `['tools', '--prepare', '--progress', 'json']` on the next turn even though the window was quitting.
- **t2 RED** (`tdd/03-14-t2-red.json`, RED_EVIDENCE_OK): `Device.test_layout_without_device` failed because every visible label was 85 px tall (natural height 7 to 38 px) and the last item's stretch was 0. `test_ok_detail_hidden` failed because the adb path showed, and `test_instructions` failed on the one-line steps. The heading-top check passed at HEAD, because a stretched heading keeps its geometry top at 16 px and centres its text. The label-height check is the one that catches the bug.
- **t3 RED** (`tdd/03-14-t3-red.json`, RED_EVIDENCE_OK): `Banner.test_follows_palette` failed because the banner kept `#fff4e5` under a dark palette and the gate kept no `!` label. `test_failed_colour` failed because `#c62828` stayed under a dark palette, and `test_check_colours` failed because the optional glyph was `#ef6c00`. The light-palette subtests passed at HEAD as expected, since those hex values equal the light COLOUR entries.
- Every RED record was written and classified before its GREEN commit. Task 1's GREEN commit is typed `fix`, because WR-05 is a bug. Tasks 2 and 3 use `feat`.

## Files Created/Modified

- `gui/firstrun.py`: PREPARED, quitting(), the ToolsPage guards, the DevicePage stretch, steps and redraw, colour(None, …), failed() and fill_checks() through colour(), Gate.mark/paint/eventFilter, and the QEvent import
- `tests/test_firstrun.py`: six new tests, STEPS on three lines, test_prepare_chain checks PREPARED, a palette() helper, and the QColor/QPalette/QTableWidget imports
- `.planning/phases/03-host-toolchains-and-guided-first-run/tdd/03-14-t{1,2,3}-red.json`: RED evidence

## Decisions Made

- The quit guard sits in both `start()` and the chain (see key-decisions). The plan asked for both, and `start()` alone would also have covered the chain. The chain check stays so that the WR-05 comment sits where the chain is scheduled.
- The banner repaints on `PaletteChange` of the host window, not in `on_ready`, so the repaint does not wait for a porter answer.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug, test measurement] An empty label's natural height**
- **Found during:** Task 2 GREEN
- **Issue:** `QLabel.heightForWidth()` returns -1 for the empty, word-wrapped error label. The layout test then compared 15 px against -1 + 8 and failed with the fix in place.
- **Fix:** when heightForWidth is negative, the test falls back to `sizeHint().height()`. The 8 px tolerance is unchanged. The measured offscreen geometry fits within it: every label sits at or below its natural height once the stretch is in place.
- **Files modified:** tests/test_firstrun.py
- **Commit:** 70a9cc3

**Total deviations:** 1 auto-fixed (a test measurement). **Impact:** none on the product code. The tolerance the planner flagged did not need changing.

## Issues Encountered

None.

## Verification

- `QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest tests.test_firstrun tests.test_shell -v`: 75 tests OK
- `QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover tests`: 430 tests OK (424 at base + 6)
- `.venv/bin/python tests/arch_rules.py`: all checks passed, including "gui/firstrun.py imports only gui.runner, PySide6 and the standard library, and writes no file"
- Acceptance greps: `quitting` 4 (≥2), `^PREPARED = ` 1, `test_no_prepare_while_quitting` 1; the two device tests 2, `setStretch(self.v.count() - 1` 1, `seven times.\n` 1 in each file; hex literals outside COLOUR 0, `PaletteChange` 1, `self.seen, self.start` 0, the three colour tests 3
- REQUIREMENTS.md not edited (the re-verification marks FRUN-01)

## Threat Flags

None. The plan adds no new surface. failed() still escapes porter's text (T-03-17), and the device rows and steps label stay plain text (T-03-31).

## Next Phase Readiness

Ready for 03-15, which can show `firstrun.PREPARED` on the Setup tab.

## Self-Check: PASSED

- FOUND: gui/firstrun.py, tests/test_firstrun.py, tdd/03-14-t1-red.json, tdd/03-14-t2-red.json, tdd/03-14-t3-red.json
- FOUND commits: daaf65a, 86f0a24, a1e4156, 70a9cc3, 5c1cc96, 3b5d7c3
