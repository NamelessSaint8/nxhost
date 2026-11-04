---
phase: 11-compile-the-c-host-in-ci
plan: 02
subsystem: ui
tags: [pyside6, gui, porttab, targets, platform-arg, mac-app, android]

# Dependency graph
requires:
  - phase: 11-compile-the-c-host-in-ci
    plan: 01
    provides: "--platform both|android|mac-app and the per-target result contract the row now feeds"
  - phase: 03-host-toolchains-and-guided-first-run
    provides: gui/firstrun.py's colour(palette) helper and the plain-text rule for porter's strings
provides:
  - "gui.app.MAC_HOST = sys.platform == 'darwin' — the view's only host fact"
  - "gui.app.TargetChoice: the Targets row (two boxes, host default, refusal, one note)"
  - "PortTab.platform_arg(): the single mapping from the boxes to porter's --platform token"
  - "PortTab.android_box / .mac_box / .targets_note / .install_row for plan 11-03's result rows"
affects: [11-03, 04-library, gui PortTab, Phase 12 smoke]

# Actuals (#2632, chars/4 over the realized diff, not a harness token count)
actuals:
  tokens: 2400
  tasks: 2
  commits: 4

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "A small QWidget owns one form row, its note and its refusal, and calls back to the tab only for the row it gates"
    - "One helper, one argv token: the view's whole contribution to a run is two booleans and a --platform string"

key-files:
  created: []
  modified:
    - gui/app.py
    - tests/test_bridge.py

key-decisions:
  - "The macOS default ticks `Mac app` only (option-a, D-02's literal reading and UI-SPEC rule 4): every default run on the Mac skips the twenty-minute Metal chain, and asking for both is a deliberate second tick"
  - "Refusal is reverted inside the toggled slot with signals blocked, so no zero-target state is reachable and no recursion is possible"
  - "The note is one QLabel serving all three notes (refusal, off macOS, Android unticked), so they can never stack; the Install row's enable state mirrors the Android box"

patterns-established:
  - "Rule 11's disable/re-enable lives in TargetChoice.boxes_enabled(on), which re-offers the Mac box only where MAC_HOST allows"

requirements-completed: [QUAL-07]

coverage:
  - id: D1
    description: "The Options form's first row is `Targets` with `Android APK` and `Mac app` 8 px apart; on macOS the Mac box starts ticked and the APK does not, elsewhere the reverse, and the Mac box is disabled with its reason (D-02, D-03, rules 1-4, 7)"
    requirement: QUAL-07
    verification:
      - kind: unit
        ref: "tests/test_bridge.py#Targets.test_default_is_the_hosts_own_target"
        status: pass
      - kind: unit
        ref: "tests/test_bridge.py#Targets.test_off_macos_the_mac_box_says_why"
        status: pass
      - kind: unit
        ref: "tests/test_bridge.py#Targets.test_on_macos_the_mac_box_is_offered"
        status: pass
    human_judgment: false
  - id: D2
    description: "No zero-target state: unticking the last ticked box re-ticks it and shows `Keep at least one target ticked.` (rule 5, 6.1)"
    requirement: QUAL-07
    verification:
      - kind: unit
        ref: "tests/test_bridge.py#Targets.test_the_last_box_cannot_be_unticked"
        status: pass
    human_judgment: false
  - id: D3
    description: "One helper maps the boxes to exactly one `--platform` token (`both`/`android`/`mac-app`); `start()` always passes it and passes `--install`/`--device` only while the APK is ticked (rules 8-9, QUAL-07's 'no second code path')"
    requirement: QUAL-07
    verification:
      - kind: unit
        ref: "tests/test_bridge.py#Targets.test_one_helper_names_the_target"
        status: pass
      - kind: unit
        ref: "tests/test_bridge.py#Targets.test_start_asks_for_the_ticked_targets"
        status: pass
    human_judgment: false
  - id: D4
    description: "Both boxes and the Install row wait out a run and come back afterwards; the Install row exists only for the Android target (rules 10-11)"
    requirement: QUAL-07
    verification:
      - kind: unit
        ref: "tests/test_bridge.py#Targets.test_the_boxes_wait_for_the_run"
        status: pass
    human_judgment: false
  - id: D5
    description: "The row fits the 980 px window with both boxes and the note on one line, and a long note wraps instead of widening the window"
    verification: []
    human_judgment: true
    rationale: "Held-out visual check the plan defers to $gsd-verify-work; the note is asserted plain-text and word-wrapped in source and in `test_on_macos_the_mac_box_is_offered` (text), not measured on screen."

# Metrics
duration: 15min
completed: 2026-11-04
status: complete
---

# Phase 11 Plan 02: The Port view offers Android, the Mac app or both Summary

**The Port view's first Options row is two target checkboxes with the host's own default, a reason for the Mac box off macOS, no reachable zero-target state, and one helper that turns them into the single `--platform` token porter parses.**

## Performance

- **Duration:** ~15 min
- **Completed:** 2026-11-04T16:34Z
- **Tasks:** 2 (the blocking decision, answered as `option-a`, and the tracer task)
- **Files modified:** 2

## Decision recorded (the plan's blocking checkpoint)

**`option-a` — `Mac app` only on macOS.** On macOS `mac.setChecked(True)` and `android.setChecked(False)`, both enabled; on Windows/Linux `android.setChecked(True)` and `mac.setChecked(False)` with the Mac box disabled. The unchosen box stays tickable wherever the host permits it, no zero-target state exists, the rejected variant (both ticked on macOS) is not the default, and no test asserts it.

## Accomplishments
- `MAC_HOST = sys.platform == 'darwin'` — the view's one host fact, read at construction, deciding only whether the Mac box is *offered* (rules 4, 7, 26-28).
- `TargetChoice`: an 8 px `QHBoxLayout` with `Android APK` and `Mac app`, the host's default under `option-a`, tooltips byte-exact per the Copywriting table, and one plain-text word-wrapped note label that shows the refusal (`Keep at least one target ticked.`), the off-macOS reason, or the Android-unticked note — first match wins, never stacked.
- The refusal reverts inside the `toggled` slot with signals blocked, so unticking the last box re-ticks it and the run can never be targetless (rule 5).
- `PortTab.platform_arg()` is the only mapping: both → `both`, APK only → `android`, Mac only → `mac-app`; `start()` always appends `--platform <token>` and keeps `--install`/`--device` inside the Android guard (rules 8-9, T-11-05).
- The Install row (checkbox, device combo, Refresh) is enabled only while the APK is ticked and nothing runs; both boxes are disabled for the run and restored with the Mac box only where it is offered (rules 10-11).
- `tests/test_bridge.Targets`: seven headless cases, `MAC_HOST` patched either way so the suite is deterministic on macOS and on the Linux CI leg.

## Task Commits

Each task was committed atomically; task 1 followed RED → GREEN (plus one later guard test):

1. **Task 1 RED: the failing target-box cases** — `bc93c463` (test)
2. **Task 1 GREEN: the row, the refusal and the one token** — `78dacce3` (feat)
3. **Task 1 guard: the boxes wait for the run** — `7dcaffa6` (test)

**Plan metadata:** the commit after this file (`docs(11-02): complete ...`)

## Files Created/Changes
- `gui/app.py` — `MAC_HOST`; `TargetChoice` (boxes, tooltips, default, refusal, note, `boxes_enabled`); `PortTab.__init__`'s `insertRow(0, 'Targets', …)`, `install_row` and the three aliases; `platform_arg()`; `on_targets_changed()`; `start()`'s `--platform` and the Android-gated install block; `run()`/`on_finished()`'s disable and restore. The results area, the game card, `STATUS_COLOUR` and every other option row are untouched (plan 11-03's ground).
- `tests/test_bridge.py` — the `Targets` class (7 tests).

## Decisions Made
- **`option-a`** (above): the row's default and the note's first match now encode D-02's literal reading.
- **The Install row is disabled through its parent widget**: Qt propagates the parent's disabled state to the checkbox, the combo and Refresh, so one `setEnabled` covers the whole row without three handles.
- **The aliases exist for plan 11-03:** `PortTab.android_box`, `.mac_box`, `.targets_note` and `.install_row` are the handles 11-03's result rows and tests read, even though the widgets live in `TargetChoice`.

## Deviations from Plan

None - plan executed exactly as written.

## TDD Gate Compliance
- RED `bc93c463` (5 cases failing on the missing `MAC_HOST`), GREEN `78dacce3` (all green), so the gate sequence holds.
- `7dcaffa6` adds rule 11's must-have assertion **after** the implementation and therefore had no RED phase; it is a guard on a truth the implementation already carried, documented in its commit message.

## Issues Encountered
- The tracer feedback gate (non-interactive run, no `AUTO_*` chain captured): the tracer's `<verify>` was re-run end to end after the commit — `tests.test_bridge.Targets` 7/7 green — before the guard test was added.
- The `QProcess: Destroyed while process is still running.` line in the suite output is pre-existing noise: it appears with the `Targets` class excluded from the run.

## User Setup Required
None.

## Known Stubs
None.

## Threat Flags
None — no new surface beyond the plan's register: the token is one of three literals (`argparse`'s `choices` rejects anything else, T-11-05), `MAC_HOST` cannot talk a non-Mac host into a Mac build (T-11-06), and all copy is literal `Qt.PlainText` (T-11-07).

## Next Phase Readiness
- 11-03 can build on `platform_arg()`, `android_box`, `mac_box`, `targets_note` and `MAC_HOST` exactly as its Interface Context expects.
- Deferred: the held-out visual check (row width with both boxes and the note) belongs to `$gsd-verify-work`; a real two-target run needs Phase 12's smoke.

---
*Phase: 11-compile-the-c-host-in-ci*
*Completed: 2026-11-04*

## Self-Check: PASSED

- Commits bc93c463, 78dacce3, 7dcaffa6 and b3a7d300 all present.
- `11-02-SUMMARY.md`, `gui/app.py` and `tests/test_bridge.py` present.
- `python -m unittest tests.test_bridge` 50/50 green; `python tests/arch_rules.py` all checks passed.
