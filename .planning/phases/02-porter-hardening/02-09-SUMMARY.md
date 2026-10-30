---
phase: 02-porter-hardening
plan: 09
subsystem: gui
tags: [porter, inspect, nacp, pyside6, html-escape, fonts]

requires:
  - phase: 02-porter-hardening
    provides: "02-04 download dialog escaping pattern (gui/app.py, tests/test_bridge.py); 02-07 tests/test_cli.py helpers and guard"
provides:
  - "porter inspect --json key `languages`: list of {code, name} from upstream nacp.LANGUAGES, narrowed by an existing extraction's control.nacp"
  - "GUI language box filled from porter inspect, no language list in gui/"
  - "Game card html-escapes every interpolated string; log pane uses the system fixed font"
affects: [gui-rework, porter-json-protocol]

actuals:
  tokens: 3431    # chars/4 over the realized diff (13724 chars)
  tasks: 2
  commits: 4
plan_head_before: 39114daa12d2fe7e12ac410909507c36adb84149
plan_head_after: 2b54ea406ad8a62504860262ce8f6262d5cf4cc3

tech-stack:
  added: []
  patterns:
    - "GUI lists that porter decides arrive as fields of the inspect JSON and are refilled per inspect"
    - "Rich-text labels escape every interpolated value with a local `e = lambda x: html.escape(str(x), quote=True)`"

key-files:
  created: []
  modified:
    - porter/cli.py
    - gui/app.py
    - tests/test_cli.py
    - tests/test_bridge.py

key-decisions:
  - "inspect reads supported-language flags only from <tid>_build/extract/<version>/control.nacp a port already made (packed version first, then sorted); no extraction or no flags gives all 16 nacp.LANGUAGES"
  - "The GUI combo always starts with 'English (default)' (no --language flag) and keeps the chosen code across inspects when still offered"

patterns-established:
  - "One language list: upstream nacp.LANGUAGES via porter inspect; gui/app.py holds none"

requirements-completed: [HARD-08, HARD-10]

coverage:
  - id: D1
    description: "porter inspect --json carries `languages` from nacp.LANGUAGES, narrowed by an extraction's control flags (packed version first), full list otherwise"
    requirement: HARD-10
    verification:
      - kind: unit
        ref: "tests/test_cli.py#Languages"
        status: pass
    human_judgment: false
  - id: D2
    description: "GUI language box holds the default plus porter's languages, keeps the selection, and gui/app.py has no own list"
    requirement: HARD-10
    verification:
      - kind: automated_ui
        ref: "tests/test_bridge.py#Escaping.test_language_box, Escaping.test_one_language_source"
        status: pass
    human_judgment: false
  - id: D3
    description: "Game card escapes name, title ID, update versions, pack, tested, reason and the folder path; no name shows the title ID, empty reason adds no row"
    requirement: HARD-08
    verification:
      - kind: automated_ui
        ref: "tests/test_bridge.py#Escaping.test_card_escapes, test_folder_path_escaped, test_empty_name_and_reason"
        status: pass
    human_judgment: false
  - id: D4
    description: "Log pane uses QFontDatabase.systemFont(FixedFont) at 9 pt"
    requirement: HARD-08
    verification:
      - kind: automated_ui
        ref: "tests/test_bridge.py#Escaping.test_log_font"
        status: pass
    human_judgment: false

duration: 4min
completed: 2026-10-30
status: complete
---

# Phase 02 Plan 09: Language list from porter, escaped game card, system fixed font Summary

**`porter inspect --json` now reports the game's languages from upstream's `nacp.LANGUAGES`, using the control.nacp flags when a port has already extracted the game. The GUI's language box shows only that list. The game card html-escapes every string it gets from the game, the profile or porter, and the log pane uses the platform's fixed-width font.**

## Performance

- **Duration:** 4 min
- **Started:** 2026-10-30T18:30:41Z
- **Completed:** 2026-10-30T18:34:15Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- `cmd_inspect` adds `languages` with 4 added lines in `porter/cli.py`, which is under the plan's limit of 6. It reads `<folder>/<tid>_build/extract/<pack>/control.nacp` first, then any `extract/*/control.nacp` in sorted order. It never extracts anything.
- `gui/app.py` no longer has a module-level `LANGUAGES`. The combo refills after each successful inspect and keeps the chosen code when the new list still offers it.
- The card escapes every interpolated value with `html.escape(..., quote=True)`, so a name such as `<b>&x</b>` shows as literal text.
- The log font comes from `QFontDatabase.systemFont(FixedFont)` at 9 pt. Before, the code picked Consolas or Menlo by OS name, and Linux has neither. The `os` import became unused and was removed.

## Task Commits

1. **Task 1 (tracer): languages from the control data to the language box**
   - RED `85cf187` (test). Valid RED: the classifier returned `RED_EVIDENCE_OK` for both targets.
     - CLI target `Languages.test_from_extraction` failed with `KeyError: 'languages'` because the inspect JSON had no such key. That is the planned behavior missing, not a fixture or import fault.
     - Bridge target `Escaping.test_language_box` failed with an AssertionError: the combo held the GUI's own 12-entry list.
   - GREEN `5a4e304` (feat). Tracer gate: the `<verify>` commands re-ran green end-to-end before Task 2 started.
2. **Task 2: escaped card and system fixed font**
   - RED `0d4d816` (test). Valid RED: `RED_EVIDENCE_OK` for target `Escaping.test_card_escapes`, which failed because the card text held the raw `<b>&x</b>`.
     - `test_folder_path_escaped` failed on its assertion: the path was not escaped.
     - `test_log_font` failed on its assertion: it got Menlo, not the system monospace font.
     - `test_empty_name_and_reason` passed at RED because the existing code already handles that edge case. It stays as a regression guard.
   - GREEN `2b54ea4` (fix).

No REFACTOR commits were needed.

## Files Created/Modified
- `porter/cli.py`: `cmd_inspect` adds `languages` (imports `nacp` beside `BuildError`).
- `gui/app.py`: language combo from inspect, escaped card, system fixed font, `os` import dropped.
- `tests/test_cli.py`: class `Languages` (4 tests, run in-process with `pipeline.inspect` patched).
- `tests/test_bridge.py`: class `Escaping` (6 tests).

## Decisions Made
- The combo is refilled only on a successful inspect answer. A failed inspect leaves it as it was.
- I added `test_packed_version_first`, which the plan did not list as a behavior, to pin the must-have "the packed version's first".

## Deviations from Plan

None. The plan ran as written. Removing the now-unused `os` import is cleanup inside Task 2's file.

## Issues Encountered
None.

## Verification
- `QT_QPA_PLATFORM=offscreen python3 -m unittest discover tests` (Python 3.14.5): 211 tests, OK. The same run with `.venv/bin/python` is also OK.
- `python3 tests/arch_rules.py`: all checks passed.
- Acceptance greps:
  - `^LANGUAGES` in gui/app.py: 0
  - `nacp.LANGUAGES` in porter/cli.py: 1
  - `languages` in gui/app.py: 3
  - `Consolas` (non-comment lines): 0
  - `systemFont`: 1
  - `html.escape`: 5
  - porter/cli.py numstat: 4 added, 1 deleted

## Next Phase Readiness
Ready for 02-10, the last plan without a SUMMARY in phase 02.

## Self-Check: PASSED
- All four modified files are present.
- Commits 85cf187, 5a4e304, 0d4d816 and 2b54ea4 are ancestors of HEAD (`git rev-list --count 39114da..HEAD` = 4).
