---
phase: 03-host-toolchains-and-guided-first-run
plan: 15
subsystem: gui
tags: [pyside6, qprocess, setup-tab, config, gap-closure]

requires:
  - phase: 03-13
    provides: probe.TIMEOUT (60 s per probe step), the porter half of WR-03
  - phase: 03-14
    provides: firstrun.PREPARED, quitting(win), colour(None, key) for firstrun.failed()
provides:
  - SetupTab.loaded snapshot; load() refreshes untouched fields, save() writes changed fields only (CR-01)
  - Window.recheck reloads the Setup tab before the check
  - Porter.started signal; Porter.start refuses a second run and returns False (WR-04, T-03-35)
  - SetupTab.show_run on fetch.started; confirm_download opens no dialog while a run goes; ToolsPage syncs on started
  - SetupTab.check asks setup --json one at a time (WR-03 GUI half)
  - TIMEOUTS['setup'] 150 s (WR-02)
  - nx2android wording on the Setup check line, the download-list failure and the device list; PREPARED on the Setup tab
  - 03-REVIEW-DISPOSITION.md with every finding fixed or deferred
affects: [phase-04 port view, phase-06 shell default and copy pass, gsd-secure-phase T-03-35 re-audit]

actuals:
  tokens: 14322
  tasks: 3
  commits: 6
plan_head_before: 992c212602a8f34a56c62fabe9d68943565f4222
plan_head_after: a30f4b66fec2472a3b55eb28f0c93e5285b2afa6

tech-stack:
  added: []
  patterns:
    - "A loaded-values snapshot per form: refresh a field only while its text still equals what was loaded; save only fields that differ from it"
    - "A shared runner refuses a second start and announces each start (Porter.started), so every view of it shows the run from its first moment"
    - "One outstanding one-shot per view: a busy flag plus an 'again' flag that re-asks once after the answer"

key-files:
  created:
    - .planning/phases/03-host-toolchains-and-guided-first-run/tdd/03-15-t1-red.json
    - .planning/phases/03-host-toolchains-and-guided-first-run/tdd/03-15-t2-red.json
    - .planning/phases/03-host-toolchains-and-guided-first-run/tdd/03-15-t3-red.json
  modified:
    - gui/app.py
    - gui/runner.py
    - gui/firstrun.py
    - tests/test_firstrun.py
    - tests/test_bridge.py
    - docs/ARCHITECTURE.md
    - .planning/phases/03-host-toolchains-and-guided-first-run/03-REVIEW-DISPOSITION.md

key-decisions:
  - "Save and check writes only the fields changed since the last load; an emptied field counts as a change and is written as ''"
  - "Porter.started is emitted just before QProcess.start, so a failure to start (finished -1) always comes after started"
  - "confirm_download checks fetch.running() after Yes, before resetting the download row, instead of relying on start()'s False, so a wizard run's collected errors and log path are not cleared"
  - "The Port tab's device tooltip keeps app.cause(fail); only the visible item text uses firstrun.cause (hook-line rule)"

patterns-established:
  - "loaded snapshot: SetupTab.loaded is the only record of what the edits were filled with"

requirements-completed: [FRUN-01, FRUN-03, TOOL-01]

coverage:
  - id: D1
    description: "What the wizard saves through porter config survives a re-check and the Setup tab's Save and check (CR-01, 03-VERIFICATION gap 1)"
    requirement: FRUN-01
    verification:
      - kind: automated_ui
        ref: "tests/test_firstrun.py#SetupTab.test_wizard_save_kept"
        status: pass
      - kind: automated_ui
        ref: "tests/test_firstrun.py#SetupTab.test_unsaved_edit_kept"
        status: pass
      - kind: automated_ui
        ref: "tests/test_firstrun.py#SetupTab.test_save_writes_changed_only"
        status: pass
    human_judgment: false
  - id: D2
    description: "A second start on a running runner is refused and the first run stays the one Cancel, finished and the close guard track (WR-04, T-03-35)"
    requirement: FRUN-01
    verification:
      - kind: integration
        ref: "tests/test_bridge.py#Stop.test_second_start_refused"
        status: pass
      - kind: integration
        ref: "tests/test_bridge.py#Close.test_confirm_while_running"
        status: pass
    human_judgment: false
  - id: D3
    description: "Both download buttons read Cancel from the run's start, whichever view started it"
    requirement: FRUN-01
    verification:
      - kind: integration
        ref: "tests/test_firstrun.py#Tools.test_label_from_start"
        status: pass
      - kind: integration
        ref: "tests/test_bridge.py#Close.test_confirm_while_running"
        status: pass
    human_judgment: false
  - id: D4
    description: "The Setup tab asks setup --json one at a time; a download's end re-checks once at a time (WR-03 GUI half)"
    requirement: FRUN-03
    verification:
      - kind: automated_ui
        ref: "tests/test_firstrun.py#SetupTab.test_one_check_at_a_time"
        status: pass
      - kind: automated_ui
        ref: "tests/test_firstrun.py#SetupTab.test_fetch_end_checks_in_turn"
        status: pass
    human_judgment: false
  - id: D5
    description: "The GUI waits 150 s for setup --json, above the NDK probe's two 60 s steps plus adb version (WR-02)"
    requirement: TOOL-01
    verification:
      - kind: unit
        ref: "tests/test_bridge.py#Timeout.test_default_limits"
        status: pass
    human_judgment: false
  - id: D6
    description: "The Setup check line, its download-list failure and the Port tab's device list name nx2android; a Prepare finished from the Setup tab reads '.NET tools are ready.'"
    requirement: FRUN-01
    verification:
      - kind: integration
        ref: "tests/test_bridge.py#Errors.test_doctor_crash_shows_stderr"
        status: pass
      - kind: integration
        ref: "tests/test_bridge.py#Errors.test_devices_and_games"
        status: pass
      - kind: integration
        ref: "tests/test_bridge.py#Close.test_setup_finish_copy"
        status: pass
    human_judgment: false
  - id: D7
    description: "03-REVIEW-DISPOSITION.md records every finding as fixed or deferred, each deferral with its reason, plus the UI review's items"
    verification:
      - kind: other
        ref: "grep -c 'disposition: open' 03-REVIEW-DISPOSITION.md = 0; grep -c '^open: 0' = 1"
        status: pass
    human_judgment: true
    rationale: "Whether each deferral reason is acceptable is a judgment for the developer; the counts only prove nothing was left open"

duration: 8min
completed: 2026-10-31
status: complete
---

# Phase 3 Plan 15: Setup tab keeps wizard saves, one run per runner, one check at a time Summary

**The Setup tab now reloads untouched fields from config.json on every re-check and saves only the fields the player changed. The shared `Porter` refuses a second start and emits `started`, so both views read Cancel from the first moment. `setup --json` runs one at a time under a 150 s limit, and the Setup tab no longer says "porter".**

## Performance

- **Duration:** 8 min
- **Started:** 2026-10-31T18:59:37Z
- **Completed:** 2026-10-31T19:07:37Z
- **Tasks:** 3
- **Files modified:** 10 (7 source/doc files plus 3 RED evidence records)

## Accomplishments
- CR-01 / 03-VERIFICATION gap 1 closed. The verifier's reproduction is now a test: prod.keys is saved through `porter config`, then `recheck()`, then Save and check, and the path survives. Before the fix it was overwritten with ''.
- WR-04 / T-03-35 fixed:
  - `Porter.start` returns False and changes nothing while a run is going.
  - `confirm_download` opens no dialog and starts nothing while the wizard's run is going.
  - Both buttons sync on `Porter.started`.
- WR-03's GUI half fixed: `SetupTab.check` keeps one `setup --json` out at a time and re-asks once after the answer. The two re-checks that come in together when a download ends now run in turn, not side by side.
- WR-02 fixed: `TIMEOUTS['setup']` is 150 s, pinned above `2 * probe.TIMEOUT + 15`.
- UI-REVIEW top fix 2 is partly done. The Setup check line, the download-list failure and the device list now go through `firstrun.failed`/`firstrun.cause`, and a Prepare finished from the Setup tab shows `firstrun.PREPARED`.
- `03-REVIEW-DISPOSITION.md` now marks all 15 findings fixed (8) or deferred (7) with their reasons (`open: 0`). The UI review's items are listed under the table.

## Task Commits

1. **Task 1: CR-01, wizard saves survive Save and check** (tracer)
   - `2315fd3` (test, RED)
   - `8072c7e` (fix, GREEN)
2. **Task 2: one run per runner, one check at a time, Cancel from the start**
   - `620a344` (test, RED)
   - `e96c002` (feat, GREEN)
3. **Task 3: setup limit, nx2android wording, docs, ledger**
   - `e4d79fd` (test, RED)
   - `a30f4b6` (feat, GREEN)

## Files Created/Modified
- `gui/app.py`:
  - SetupTab gains `loaded`, `checking`/`again`, `show_run()` and an updated `load`/`save`/`check`/`confirm_download`/`on_fetch`/`fetched`.
  - `Window.recheck` now calls `self.setup.load()`.
  - The device-list failure item uses `firstrun.cause`.
- `gui/runner.py`: `Porter.started` and the refused second start; `TIMEOUTS['setup']` is 150 with its reason.
- `gui/firstrun.py`: ToolsPage's one-time hook also connects `fetch().started` to `sync`.
- `tests/test_firstrun.py`: new SetupTab tests `test_wizard_save_kept`, `test_unsaved_edit_kept`, `test_save_writes_changed_only`, `test_one_check_at_a_time` and `test_fetch_end_checks_in_turn`, plus `Tools.test_label_from_start`.
- `tests/test_bridge.py`:
  - New tests: `Stop.test_second_start_refused`, `Close.test_confirm_while_running`, `Close.test_setup_finish_copy`.
  - Updated: `Timeout.test_default_limits`, `Errors.test_doctor_crash_shows_stderr`, `Errors.test_devices_and_games`.
- `docs/ARCHITECTURE.md`:
  - The one-shot limits line now gives setup 150 s and why, with nx2android wording per view.
  - The `setup --json` GUI paragraph now covers reload, changed-only save, one check at a time and one run per runner.
- `.planning/phases/03-host-toolchains-and-guided-first-run/03-REVIEW-DISPOSITION.md`: the dispositions and the UI review's list.
- `.planning/phases/03-host-toolchains-and-guided-first-run/tdd/03-15-t{1,2,3}-red.json`: the RED evidence records.

## Decisions Made
- An emptied field counts as a change and is written. Any other untouched field is never written, so a value another writer saved stays.
- `started` is emitted just before `QProcess.start()`, so a failed start's `finished(-1)` always follows it.
- After Yes in the download dialog, the code checks `fetch.running()` before it resets the download row's state. The plan wanted the reset first and a test of `start()`'s False after it. Checking first means a wizard run's collected `[RED]` lines and log path are not cleared. `Porter.start` still refuses on its own.

## Deviations from Plan

**1. [Minor - ordering] confirm_download checks `fetch.running()` after Yes, before the starting state is reset, instead of testing `start()`'s return value**
- **Found during:** Task 2
- **Issue:** Following the plan literally would clear the running wizard run's `dl_errors`/`dl_log`/`dl_error` before `start()` refused.
- **Fix:** `if self.fetch.running(): self.show_run(); return` comes before the reset. The behaviour the plan asks for is the same: no second run, and the button shows the running run.
- **Files modified:** gui/app.py
- **Commit:** e96c002

**2. [Process] Task 1's GREEN commit uses `fix(03-15)`, not `feat(03-15)`**
- Commit `8072c7e`. It closes a bug (CR-01), so `fix` is the accurate Conventional Commits type. Tasks 2 and 3 use `feat`, so the RED→GREEN gate pairs exist (see TDD Gate Compliance).

**Total deviations:** 2 minor (no scope change). **Impact:** none on behaviour.

## TDD Gate Compliance
- RED commits: `2315fd3`, `620a344`, `e4d79fd` (`test(03-15)`). Each was classified `RED_EVIDENCE_OK` by `gsd_run check tdd-red-evidence`; the records are in `tdd/03-15-t{1,2,3}-red.json`.
  - T1: the keys edit stays '' after `recheck`.
  - T2: `start()` returns None, not False; the labels stay Download until the first event; 3 and 2 `setup --json` calls go out in one turn.
  - T3: the setup limit is 45; the Setup tab's lines say porter; a Prepare reads "the tools are ready".
  - The semantic check for all three: every target test failed on its planned assertion, with no load or fixture errors.
- GREEN commits: `8072c7e` (fix), `e96c002` (feat), `a30f4b6` (feat). Each follows its RED commit.
- Tracer gate (Task 1): end-of-phase mode with an automated-only verify. The verify was re-run and passed (test_firstrun 69 OK, test_bridge 40 OK) before expanding.

## Issues Encountered
None.

## Verification
- `QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest tests.test_bridge tests.test_firstrun tests.test_shell`: 123 tests OK
- `QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover tests`: 439 tests OK (430 at base plus 9 new)
- `.venv/bin/python tests/arch_rules.py`: all checks passed
- Every task's acceptance greps pass:
  - `recheck(self): self.setup.load()` 1, `self.setup.check()` 0, `self.loaded` 4
  - `started = Signal()` 1, `fetch.started.connect` 1, `started.connect(self.sync)` 1, `self.again` 3
  - `'setup': 150` 1, `firstrun.failed(` 2, `firstrun.cause(` 1, `'porter: '` 0, `firstrun.PREPARED` 1
  - `disposition: open` 0, `^open: 0` 1
- No stand-in porter process was left running after the suites.
- `03-SECURITY.md` and `.planning/REQUIREMENTS.md` were not edited.

## Threat Flags
None. No new surface. T-03-41, T-03-42 and T-03-43 are mitigated as planned, and T-03-35 is resolved in code (left for `/gsd-secure-phase` to re-audit).

## User Setup Required
None.

## Next Phase Readiness
Phase 3 is complete (the last plan). The orchestrator re-runs the verifier (gap 1) and `/gsd-secure-phase` (T-03-35).

## Self-Check: PASSED
- All modified and created files listed above exist on disk.
- All six commits (2315fd3, 8072c7e, 620a344, e96c002, e4d79fd, a30f4b6) are ancestors of HEAD.
- `gsd_run check evaluation-scope --plan 03-15 --commits-only` resolved the plan's commits.
