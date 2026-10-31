---
phase: 03-host-toolchains-and-guided-first-run
plan: 10
subsystem: ui
tags: [pyside6, qwizard, adb, devices, first-run, desktop-entry]

requires:
  - phase: 03-05
    provides: Wizard, Gate, Page/StepPage, colour/cause/failed/mono, the window protocol (fetch, recheck, port_a_game)
  - phase: 03-06
    provides: devices --json rows with state, detail (adb's own text) and fix
  - phase: 03-07
    provides: the shell (no port_a_game) and the firstrun view-purity arch rule
  - phase: 03-12
    provides: the keys page pattern (rows as item widgets, saving through config)
provides:
  - "DevicePage: devices --json polled from each answer (POLL_MS = 2500), one call outstanding, stops when left or closed"
  - "DeviceRow: STATE_GLYPH glyph, model or serial, adb's state text in the fixed font, porter's fix (plain, selectable, word-wrapped)"
  - "Choosing one of several ready devices saves it with config device <serial> --json"
  - "Wizard.seen_device (in memory): None until the device page answers, then whether a ready device was seen"
  - "DonePage: summary per step and note, No device yet note, Games that play today, Add to app menu (desktop-entry --install), Port a game"
affects: [03-11 tools page, phase-04 port view (port_a_game on the shell), phase-05 device manager]

actuals:
  tokens: 8900
  tasks: 2
  commits: 4
plan_head_before: 73113ad5e558fb2caf8e7c668e0fce7d06175d74
plan_head_after: 1301b29b0eff785aa1b0a4221ab91dfb73cff4c3

tech-stack:
  added: []
  patterns:
    - "Polling chained from each answer with QTimer.singleShot(POLL_MS, owner, …) and a generation counter, never setInterval"
    - "Polling starts a turn after currentIdChanged reaches the page, so go() jumping past it sends nothing"
    - "QWizard.NoDefaultButton set only on the done page so the page's own primary button stays the default"

key-files:
  created:
    - .planning/phases/03-host-toolchains-and-guided-first-run/tdd/03-10-t1-red.json
    - .planning/phases/03-host-toolchains-and-guided-first-run/tdd/03-10-t2-red.json
  modified:
    - gui/firstrun.py
    - tests/test_firstrun.py

key-decisions:
  - "Polling is driven by the wizard's currentIdChanged (Back, Next and jumps) rather than initializePage, because QWizard does not call initializePage when Back returns to a page"
  - "The No device yet note shows only when the device page answered in this wizard and saw no ready device; a wizard opened straight at the done page says nothing about devices rather than guess"
  - "A soft step that is not ok (the device step without adb) shows '!' in the note colour on the done page, not the blocking ✗"
  - "A failed devices --json shows cause(fail) as plain text in the empty row with no Retry link, because the next poll is the retry"

patterns-established:
  - "Device-reported text (serial, model, adb state) only ever goes into Qt.PlainText labels"

requirements-completed: [DEV-01, FRUN-01, TOOL-04]

coverage:
  - id: D1
    description: "The device page polls devices --json from each answer while it shows, one call at a time, and stops when left or closed"
    requirement: DEV-01
    verification:
      - kind: automated_ui
        ref: "tests/test_firstrun.py#Device.test_polls_while_current"
        status: pass
      - kind: automated_ui
        ref: "tests/test_firstrun.py#Device.test_no_stacking"
        status: pass
      - kind: automated_ui
        ref: "tests/test_firstrun.py#Device.test_failure_keeps_polling"
        status: pass
    human_judgment: false
  - id: D2
    description: "Each device row shows its glyph, model or serial, adb's state in the fixed font and porter's fix; unauthorized turns into device live; Next reads Skip: install later without a device"
    requirement: DEV-01
    verification:
      - kind: automated_ui
        ref: "tests/test_firstrun.py#Device.test_rows"
        status: pass
      - kind: automated_ui
        ref: "tests/test_firstrun.py#Device.test_live_change"
        status: pass
      - kind: automated_ui
        ref: "tests/test_firstrun.py#Device.test_empty_and_skip"
        status: pass
      - kind: automated_ui
        ref: "tests/test_firstrun.py#Device.test_instructions"
        status: pass
    human_judgment: false
  - id: D3
    description: "With several ready devices, selecting one saves it with config device; failures show their cause"
    requirement: FRUN-01
    verification:
      - kind: automated_ui
        ref: "tests/test_firstrun.py#Device.test_pick_saves"
        status: pass
      - kind: automated_ui
        ref: "tests/test_firstrun.py#Device.test_pick_fails"
        status: pass
    human_judgment: false
  - id: D4
    description: "The done page: summary per step and note, No device yet, playable titles, Port a game, Close setup"
    requirement: FRUN-01
    verification:
      - kind: automated_ui
        ref: "tests/test_firstrun.py#Done.test_summary"
        status: pass
      - kind: automated_ui
        ref: "tests/test_firstrun.py#Done.test_no_device_note"
        status: pass
      - kind: automated_ui
        ref: "tests/test_firstrun.py#Done.test_playable"
        status: pass
      - kind: automated_ui
        ref: "tests/test_firstrun.py#Done.test_port_a_game"
        status: pass
      - kind: automated_ui
        ref: "tests/test_firstrun.py#Done.test_close_setup"
        status: pass
    human_judgment: false
  - id: D5
    description: "Add to app menu shows only when porter offers it and runs desktop-entry --install only on the press"
    requirement: TOOL-04
    verification:
      - kind: automated_ui
        ref: "tests/test_firstrun.py#Done.test_add_to_menu_offer"
        status: pass
    human_judgment: false
  - id: D6
    description: "On a real Linux x64 bundle the entry appears in the desktop's app menu and starts the app; a real tablet turns unauthorized into device after Allow; Linux no permissions shows the distro fix"
    requirement: TOOL-04
    verification: []
    human_judgment: true
    rationale: "Needs a Linux desktop session and a physical Android device; CI has neither (release checks in 03-08)"
  - id: D7
    description: "Overflow and long text: many devices and 11+ playable titles scroll with the button row in view at 560 px; fixes, notes and details word-wrap at 720 px"
    verification: []
    human_judgment: true
    rationale: "Backstop visual checks from the UI-SPEC; layout at a given window size is not asserted by the offscreen tests"

duration: 8min
completed: 2026-10-31
status: complete
---

# Phase 3 Plan 10: Device and Done Pages Summary

**The wizard's device page polls `devices --json` once per answer and shows each device's adb state with porter's fix, live. The done page sums up setup, lists the games that play today, offers the Linux app-menu entry, and starts the first port.**

## Performance

- **Duration:** 8 min
- **Started:** 2026-10-31T16:54:41Z
- **Completed:** 2026-10-31T17:02:25Z
- **Tasks:** 2
- **Files modified:** 2 (plus 2 RED evidence records)

## Accomplishments
- Device page (DEV-01, D-15): three numbered steps, then one row per device: a glyph (✓ device; ✗ unauthorized, offline, no permissions; ▶ authorizing, connecting), the model or serial, adb's state text in the fixed font, and porter's fix as a selectable, word-wrapped second line. Everything a device reports is plain text.
- Polling: `devices --json` runs a turn after the page shows. The next call is scheduled `POLL_MS` (2500 ms) after each answer, so at most one call is outstanding. A generation counter stops it on Back, Next, a jump past the page, or closing the wizard.
- Empty and failure states: the page shows `Looking again every few seconds…` until the first answer, then `No device found yet. Looking again every few seconds…`, or the call's cause. Next reads `Skip: install later` until a device is ready.
- With several ready devices, selecting one saves it with `config device <serial> --json`. A redraw keeps the selection and saves nothing again.
- Done page (D-28): one row per step (Notice, prod.keys, Tools, adb) with its glyph and detail, then each note with `!`, plus `No device yet: port now, install later.` when the device page saw no ready device. It also has the `Games that play today` list from `profiles --json` (hidden when none or on failure), `Add to app menu` (D-20, only when `desktop.offer`), and `Port a game` (the default, bold, 36 px; hidden on the shell).

## Task Commits

1. **Task 1 RED: device page tests** - `251f817` (test)
2. **Task 1 GREEN: device page polling and rows** - `672f87c` (feat)
3. **Task 2 RED: device choice and done page tests** - `7cd1207` (test)
4. **Task 2 GREEN: device choice and done page** - `1301b29` (feat)

## TDD Gate Compliance

- **RED (Task 1):** `Device.test_no_stacking` failed on its assertion (no `devices --json` call within 1 s). The classifier returned `RED_EVIDENCE_OK` (`tdd/03-10-t1-red.json`). Semantic check: the planned behaviour was absent and nothing failed to load.
- **RED (Task 2):** `Device.test_pick_saves` failed on `[] != [['config', 'device', 'R5CT2', '--json']]`. The classifier returned `RED_EVIDENCE_OK` (`tdd/03-10-t2-red.json`). The Done tests errored on the 03-05 stub's missing widgets. `test_close_setup` already passed because 03-05 had already labelled Finish.
- **GREEN:** `672f87c` and `1301b29`. The full suite passes: 403 tests, and `tests/arch_rules.py` reports no FAIL.
- **REFACTOR:** none needed.

## Files Created/Modified
- `gui/firstrun.py` - adds `POLL_MS`, `STATE_GLYPH`, `model()`, `DeviceRow`, `DevicePage` (here/moved/stop/poll/draw/pick), `NAMES`, `Line`, `DonePage` (redraw/draw_summary/load_playable/add_to_menu/port_a_game), `Wizard.moved` and `Wizard.seen_device`. `StepPage` takes `stretch=`.
- `tests/test_firstrun.py` - the `Calls` stand-in gains a per-command answer queue and also patches `gui.shell`. New `Device` class (9 tests) and `Done` class (6 tests).

## Decisions Made
- Polling follows `currentIdChanged`, not `initializePage`. QWizard does not call `initializePage` when Back returns to a page, and a deferred start means `go('done')` passes the device page without calling adb.
- `seen_device` has three states. A wizard opened straight at the done page has not asked adb, so it shows no device note instead of a possibly wrong "No device yet".
- On the done page a soft step that is not ok shows `!`, not ✗, so "never blocking" holds visually too.
- A failed poll shows its plain cause with no Retry link, because the next poll is the retry.
- QWizard makes its Finish button the default again on every page switch. The wizard sets `QWizard.NoDefaultButton` only while the done page shows Port a game, so Port a game stays the default and Enter on other pages still means Next.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] QWizard took the default button away from Port a game**
- **Found during:** Task 2
- **Issue:** `setDefault(True)` on Port a game was undone because QWizard's button update makes Finish (Close setup) the default after each page switch.
- **Fix:** `Wizard.moved` sets `QWizard.NoDefaultButton` only on the done page when Port a game shows, then sets Port a game as the default.
- **Files modified:** gui/firstrun.py
- **Verification:** `Done.test_port_a_game` checks `isDefault()`. The other pages keep Next as their default.
- **Committed in:** 1301b29

**2. [Rule 1 - Bug] Test baselines for today's Port and Games tabs**
- **Found during:** Tasks 1 and 2
- **Issue:** today's Window asks `devices --json` (Port tab) and `profiles --json` (Games tab) at launch, which made the raw call counts wrong.
- **Fix:** the tests count calls from a baseline taken after launch.
- **Files modified:** tests/test_firstrun.py
- **Committed in:** 251f817, 1301b29

---

**Total deviations:** 2 auto-fixed (2 bugs)
**Impact on plan:** No scope change.

## Issues Encountered
None.

## Known Stubs
None. The tools page is still 03-05's step text, and 03-11 replaces it.

## User Setup Required
None.

## Next Phase Readiness
- 03-11 (tools page) is the last plan in Phase 3. FRUN-01 reads complete only after it finishes.
- Human checks left for the end-of-phase UAT and the 03-08 release checks: on a real tablet, `unauthorized` turns into `device` after Allow; Linux shows the `no permissions` fix; the Linux x64 bundle's Add to app menu entry starts the app; the layout at 720×560 with many devices or 11+ titles.

---
*Phase: 03-host-toolchains-and-guided-first-run*
*Completed: 2026-10-31*

## Self-Check: PASSED
- Files: gui/firstrun.py, tests/test_firstrun.py, tdd/03-10-t1-red.json, tdd/03-10-t2-red.json found
- Commits: 251f817, 672f87c, 7cd1207, 1301b29 are ancestors of HEAD
- Acceptance: POLL_MS prints 2500; the `'devices', '--json'`, `'desktop-entry', '--install', '--json'`, `'profiles', '--json'` and No device yet greps each count 1; Device.test_no_stacking passes
- Plan verification: `unittest discover tests` OK (403), `tests/arch_rules.py` has no FAIL line
