---
phase: 03-host-toolchains-and-guided-first-run
plan: 12
subsystem: ui
tags: [pyside6, first-run, wizard, prod.keys, qlistwidget, qfiledialog]

requires:
  - phase: 03-host-toolchains-and-guided-first-run (03-01)
    provides: "setup --json keys step with found candidates (path, ok, detail), and `config keys <path> --json`"
  - phase: 03-host-toolchains-and-guided-first-run (03-05)
    provides: "gui/firstrun.py wizard, Page, colour/failed/mono/body helpers, win.recheck(); tests/test_firstrun.py Calls stand-in"
provides:
  - "KeysPage: the found prod.keys list (glyph, mono path elided in the middle with tooltip, porter's detail), Browse…, the result line, the empty state"
  - "KeysPage.save(path, src, txt, idle): the one place that sends config keys; saving… while pending, win.recheck() on an answer, failed() with Retry on a failure"
  - "tests/test_firstrun.py class Keys (8 tests)"
affects: [03-09, 03-10, 03-11, phase-04 port preflight, phase-06 shell]

actuals:
  tokens: 6400
  tasks: 2
  commits: 4
plan_head_before: c596a7928e57db49155d027119b64da750783a7f
plan_head_after: 2c7b0b7d4000abb5723a0a76463ad09dcd39b9b8

tech-stack:
  added: []
  patterns:
    - "Elided(QLabel): a path in the fixed font that re-elides with Qt.ElideMiddle on every resize, full path as tooltip"
    - "List rows as setItemWidget row widgets; save triggered by itemSelectionChanged (not currentItemChanged, which focus-in can set without a click)"
    - "A one-shot's source widget is restored through state(), which swallows RuntimeError when a redraw has replaced the row meanwhile"

key-files:
  created:
    - .planning/phases/03-host-toolchains-and-guided-first-run/tdd/03-12-t1-red.json
    - .planning/phases/03-host-toolchains-and-guided-first-run/tdd/03-12-t2-red.json
  modified:
    - gui/firstrun.py
    - tests/test_firstrun.py

key-decisions:
  - "KeysPage derives from Page, not StepPage: its result line replaces 03-05's detail/fix labels (planner assumption kept)"
  - "The result line drops the `<path>: ` prefix when no file is configured, so the unset state reads `not set. Choose your prod.keys …`"
  - "A selected not-ok row is not saved; Browse… saves any file and porter's verdict shows on the result line"

patterns-established:
  - "Keys page strings are built only from path, ok, detail and fix; tests walk every QLabel, tooltip and list item for a 32-hex-digit run"

requirements-completed: [FRUN-01]

coverage:
  - id: D1
    description: "The keys page lists porter's found prod.keys, one row each with ✓/✗ in colour, the path in the fixed font elided in the middle (tooltip: full path) and porter's detail"
    requirement: FRUN-01
    verification:
      - kind: automated_ui
        ref: "tests/test_firstrun.py#Keys.test_candidates"
        status: pass
    human_judgment: false
  - id: D2
    description: "Selecting an ok row saves it with `config keys <path> --json` (row reads saving… and is disabled), then re-checks; a not-ok row sends nothing"
    requirement: FRUN-01
    verification:
      - kind: automated_ui
        ref: "tests/test_firstrun.py#Keys.test_pick_saves"
        status: pass
    human_judgment: false
  - id: D3
    description: "The result line shows `<path>: <detail>. <fix>` (bad) or `<path>: <detail>` (ok), plain text; no key value appears anywhere on the page"
    requirement: FRUN-01
    verification:
      - kind: automated_ui
        ref: "tests/test_firstrun.py#Keys.test_bad_file_line"
        status: pass
      - kind: automated_ui
        ref: "tests/test_firstrun.py#Keys.test_no_values"
        status: pass
    human_judgment: false
  - id: D4
    description: "Browse… saves any picked file through the same save(); cancel sends nothing; the empty state shows with no candidates; a failed save shows the cause with Retry; Next is never disabled"
    requirement: FRUN-01
    verification:
      - kind: automated_ui
        ref: "tests/test_firstrun.py#Keys.test_browse_saves"
        status: pass
      - kind: automated_ui
        ref: "tests/test_firstrun.py#Keys.test_empty"
        status: pass
      - kind: automated_ui
        ref: "tests/test_firstrun.py#Keys.test_save_fails"
        status: pass
      - kind: automated_ui
        ref: "tests/test_firstrun.py#Keys.test_next_enabled"
        status: pass
    human_judgment: false
  - id: D5
    description: "Many candidates scroll inside the list with the button row visible at 720x560; long paths elide in the middle with the tooltip, in light and dark themes on macOS and Linux"
    requirement: FRUN-01
    verification: []
    human_judgment: true
    rationale: "Backstop visual check from the plan's human-check: layout at the minimum size and theme colours need eyes on a real desktop"

duration: 6min
completed: 2026-10-31
status: complete
---

# Phase 3 Plan 12: The prod.keys wizard page Summary

**The first-run wizard's prod.keys page lists the key files porter found with porter's verdict, saves a picked row or a Browse… file through `porter config keys` and re-checks, and shows nothing of the file's contents**

## Performance

- **Duration:** about 6 min (ledger to last task commit)
- **Started:** 2026-10-31T12:31Z
- **Completed:** 2026-10-31T12:40Z
- **Tasks:** 2 (Task 1 tracer, Task 2 auto; both TDD)
- **Files modified:** 2 source files, plus 2 RED evidence records

## Accomplishments

- `KeysPage` in `gui/firstrun.py`: body copy, a `QListWidget` of `KeyRow` widgets (glyph in `colour()`, `Elided` mono path with tooltip, porter's `detail`), `Browse…` beside the list, the empty-state line, the result line and an error line with Retry.
- `save(path, src, txt, idle)` is the only `config keys` call; picked rows and Browse… share it. While pending, the source reads `saving…` and is disabled. A good answer calls `win.recheck()`, and a failure shows `failed(fail)` with Retry and restores the source.
- `tests/test_firstrun.py` class `Keys`: 8 tests over 03-05's `Calls` stand-in. They cover the rows, the pick-and-save path, the result line, the no-key-values sweep, the empty state, Browse… (including cancel), a failed save with Retry, and Next staying enabled.

## Task Commits

1. **Task 1 RED:** `0b4a5bd` test(03-12): add failing tests for the keys page's found list, save and result line
2. **Task 1 GREEN:** `da36098` feat(03-12): list porter's found prod.keys and save a picked one through config keys
3. **Task 2 RED:** `4618c19` test(03-12): add failing tests for Browse…, the empty state and a failed key save
4. **Task 2 GREEN:** `2c7b0b7` feat(03-12): Browse… for any prod.keys, the empty state and Retry on a failed save

Tracer gate (end-of-phase mode, automated-only verify): re-ran `tests.test_firstrun` after Task 1, 27 tests OK. Then went on to Task 2.

## TDD Gate Compliance

- Task 1 RED: `tdd/03-12-t1-red.json`, classifier `RED_EVIDENCE_OK` (target `Keys.test_pick_saves`). Semantic check: all 4 Keys tests ran and failed on the planned "the keys page has no list" assertion. There were no load or fixture faults.
- Task 2 RED: `tdd/03-12-t2-red.json`, classifier `RED_EVIDENCE_OK` (target `Keys.test_save_fails`). Semantic check: the 4 new tests (5 failures counting subTests) failed on their planned assertions: no Retry line, no empty line, no Browse…. Task 1's tests still passed.
- GREEN: both feat commits pass `tests.test_firstrun` (31 tests). REFACTOR: none needed.

## Files Created/Modified

- `gui/firstrun.py`: `Elided`, `KeyRow`, `state()`, and `KeysPage` rebuilt on `Page` (list, Browse…, empty, result, error, `redraw`, `pick`, `choose`, `save`).
- `tests/test_firstrun.py`: the `Keys` class, `HEX32`, and the `re`/`QWidget` imports.
- `.planning/phases/03-host-toolchains-and-guided-first-run/tdd/03-12-t1-red.json`, `03-12-t2-red.json`: the RED evidence records.

## Decisions Made

- The page saves on `itemSelectionChanged`, not `currentItemChanged`. Focusing an item view can set its current index without a click, and that would save the first row by accident.
- With no configured file the result line drops the `<path>: ` prefix. 03-05's `Wizard.test_page_text` still sees the keys step's detail and fix.
- The tooltip uses the raw path. QLabel tooltips are rich text when the string looks like markup, but Qt tooltips run no script, and the path comes from porter's own search or the player's file dialog.

## Deviations from Plan

**1. [Acceptance criterion defect] The `open(` grep gate counts 2, not 0**
- **Found during:** Task 1 acceptance check
- **Issue:** `grep -v '^\s*#' gui/firstrun.py | grep -c "open("` counts the substring inside 03-05's `first_open(` helper (its definition and one call). The count was already 2 before this plan.
- **Fix:** none needed. This plan adds no `open(` call. 03-07's arch rule uses `\bopen\(` for this exact reason, and it passes. `first_open` was left as is, since renaming it is outside this plan's scope.
- **Commit:** n/a

**Total deviations:** 1 (a gate wording defect, no code change). **Impact:** none. The intent (no file read or write in gui/firstrun.py) is enforced by `tests/arch_rules.py` and holds.

## Issues Encountered

None.

## User Setup Required

None.

## Verification

- `QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest tests.test_firstrun tests.test_bridge`: OK
- `QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover tests`: 378 tests OK (370 at base, plus 8)
- `.venv/bin/python tests/arch_rules.py`: all checks passed, including the gui/firstrun.py import and no-write rule
- Acceptance greps: `'config', 'keys'` = 1, `ElideMiddle` = 1, porter imports = 0, `getOpenFileName` = 1, the empty-state copy = 1

## Next Phase Readiness

FRUN-01 is also listed by 03-09, 03-10 and 03-11. It reads complete in REQUIREMENTS.md only once those plans finish. The tools page (03-11) and the device page (03-10) still have 03-05's step text only.

The backstop visual check (D5) is left for the end-of-phase human verify.

## Self-Check: PASSED

- FOUND: gui/firstrun.py, tests/test_firstrun.py, tdd/03-12-t1-red.json, tdd/03-12-t2-red.json
- FOUND commits: 0b4a5bd, da36098, 4618c19, 2c7b0b7 (all ancestors of HEAD)
