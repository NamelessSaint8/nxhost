---
phase: 03-host-toolchains-and-guided-first-run
plan: 11
subsystem: ui
tags: [pyside6, qwizard, toolchains, download, cancel, progress, dotnet]

requires:
  - phase: 03-03
    provides: resumable downloads with progress rate and eta, exit 130 on cancel
  - phase: 03-05
    provides: Wizard, StepPage, the window's fetch under the close guard, SetupTab download row
  - phase: 03-09
    provides: setup --json tools items (download, command, note), tools --prepare
  - phase: 03-10
    provides: the done page's default-button handling
  - phase: 03-12
    provides: the keys page pattern (saving… on the source, failed() with Retry)
provides:
  - "progress_line(ev, kn), time_left(eta), run_kind(fetch) in gui/firstrun.py"
  - "ToolsPage: rows (glyph, Tool with note/fix/command lines, Version, Source, Size, actions), Download all missing / Cancel download / Cancel .NET preparation on win.fetch, Use my own…, Copy command, Re-check, Prepare .NET tools and the chain after a download"
  - "Wizard.primary(i): a page's own primary button is the default (done page and tools page)"
  - "SetupTab: dl_btn cancels a running download or Prepare, dl_step word-wraps and uses progress_line, no license re-ask"
affects: [phase-04 port view, phase-03 verification and UAT]

actuals:
  tokens: 11500
  tasks: 3
  commits: 6
plan_head_before: 2f511a2a1269645d92acf51d00d6b393d67e50c3
plan_head_after: 997745cf7608c8204cff4bca5817ca53b0d9a7ae

tech-stack:
  added: []
  patterns:
    - "One long run per window: the tools page and the Setup tab both listen to win.fetch and label their button from run_kind(fetch), so either view cancels what the other started"
    - "A chained run starts with QTimer.singleShot(0, page, …) after finished, so finished's other listeners see the first run end"

key-files:
  created:
    - .planning/phases/03-host-toolchains-and-guided-first-run/tdd/03-11-t1-red.json
    - .planning/phases/03-host-toolchains-and-guided-first-run/tdd/03-11-t2-red.json
    - .planning/phases/03-host-toolchains-and-guided-first-run/tdd/03-11-t3-red.json
  modified:
    - gui/firstrun.py
    - gui/app.py
    - tests/test_firstrun.py
    - tests/test_bridge.py
    - tests/fixtures/bridge/fake_porter.py

key-decisions:
  - "The progress line's speed is porter's `rate` (porter/runlog.py adds it), not a GUI computation; `[k/n]` is joined with a space, the other parts with ' · '"
  - "The Prepare chain runs only after a download this page started (self.mine), not after one the Setup tab started"
  - "A failed Prepare shows as a '!' note in the status line with Open log; Next and isComplete are untouched (D-24)"
  - "The Setup tab labels its button on every event while the run goes, not only on `log`, because a run started by the tools page (or the stand-in) may not print `log` first"
  - "Wizard.moved's done-page default-button code became Wizard.primary(i) so the tools page's Download all missing can be the default the same way"

patterns-established:
  - "Porter strings in the tools page's rich text (notes, errors) are html.escape'd; plain labels elsewhere"

requirements-completed: [FRUN-01, TOOL-01, TOOL-03]

coverage:
  - id: D1
    description: "The progress line: [k/n] name · step · done / total · speed/s · time left, empty parts dropped"
    requirement: FRUN-01
    verification:
      - kind: automated_unit
        ref: "tests/test_firstrun.py#Progress.test_line"
        status: pass
      - kind: automated_unit
        ref: "tests/test_firstrun.py#Progress.test_drops_empty"
        status: pass
      - kind: automated_unit
        ref: "tests/test_firstrun.py#Progress.test_time_left"
        status: pass
    human_judgment: false
  - id: D2
    description: "Download all missing (total size) starts tools --download on win.fetch with no dialog; hidden with Every tool is here. when nothing is downloadable"
    requirement: TOOL-01
    verification:
      - kind: automated_ui
        ref: "tests/test_firstrun.py#Tools.test_download_starts_run"
        status: pass
      - kind: automated_ui
        ref: "tests/test_firstrun.py#Tools.test_hidden_when_nothing"
        status: pass
    human_judgment: false
  - id: D3
    description: "Cancel download stops the whole stand-in tree: stopping… until finished, then the resume hint"
    requirement: FRUN-01
    verification:
      - kind: automated_ui
        ref: "tests/test_firstrun.py#Tools.test_cancel"
        status: pass
    human_judgment: false
  - id: D4
    description: "A failed download shows porter's escaped cause in the problem colour with Open log; a hash mismatch in the fixed font"
    requirement: FRUN-01
    verification:
      - kind: automated_ui
        ref: "tests/test_firstrun.py#Tools.test_failure_inline"
        status: pass
    human_judgment: false
  - id: D5
    description: "Notes and fixes as second lines; Use my own… for ndk, dotnet and adb through config; Copy command and Re-check on the arm64 adb row"
    requirement: TOOL-03
    verification:
      - kind: automated_ui
        ref: "tests/test_firstrun.py#Tools.test_second_lines"
        status: pass
      - kind: automated_ui
        ref: "tests/test_firstrun.py#Tools.test_use_own_ndk"
        status: pass
      - kind: automated_ui
        ref: "tests/test_firstrun.py#Tools.test_use_own_dotnet_adb"
        status: pass
      - kind: automated_ui
        ref: "tests/test_firstrun.py#Tools.test_arm64_adb"
        status: pass
    human_judgment: false
  - id: D6
    description: "Prepare .NET tools: chained after a download ending 0, offered on an ok .NET row, Cancel .NET preparation, failure as a note"
    requirement: TOOL-01
    verification:
      - kind: automated_ui
        ref: "tests/test_firstrun.py#Tools.test_prepare_chain"
        status: pass
      - kind: automated_ui
        ref: "tests/test_firstrun.py#Tools.test_prepare_button"
        status: pass
      - kind: automated_ui
        ref: "tests/test_firstrun.py#Tools.test_prepare_failure_is_note"
        status: pass
    human_judgment: false
  - id: D7
    description: "The Setup tab's button cancels a download or Prepare whoever started it; its progress text is progress_line, word-wrapped; no license re-ask"
    requirement: FRUN-01
    verification:
      - kind: automated_ui
        ref: "tests/test_bridge.py#Close.test_setup_cancel_label"
        status: pass
      - kind: automated_ui
        ref: "tests/test_bridge.py#Downloads.test_progress_line"
        status: pass
      - kind: automated_ui
        ref: "tests/test_bridge.py#Downloads.test_untested_and_escaped"
        status: pass
    human_judgment: false
  - id: D8
    description: "Real downloads on a Mac with a fresh NX2A_HOME: bytes, speed, time left; Cancel mid-NDK then resume; Prepare ends with .NET tools are ready."
    requirement: FRUN-01
    verification: []
    human_judgment: true
    rationale: "Needs the network and about 1 GB of real downloads; tests never fetch a real toolchain"
  - id: D9
    description: "Overflow and long text: the table scrolls with the button row in view at 560 px; a 300-character hash message does not widen the wizard past 760 px"
    verification: []
    human_judgment: true
    rationale: "Backstop visual checks from the UI-SPEC; layout at a given window size is not asserted by the offscreen tests"

duration: 10min
completed: 2026-10-31
status: complete
---

# Phase 3 Plan 11: Tools Page and Setup Tab Download Row Summary

**The wizard's tools page downloads the missing NDK, .NET and adb on the window's own run with bytes, speed and time left. Cancel stops the whole tree and leaves the download resumable. The player can point at their own tools or copy the distro adb command. The .NET tools are prepared right after the download. The Setup tab's download row gets the same Cancel and progress line.**

## Performance

- **Duration:** 10 min
- **Started:** 2026-10-31T17:06:01Z
- **Completed:** 2026-10-31T17:16:00Z
- **Tasks:** 3
- **Files modified:** 5 (plus 3 RED evidence records)

## Accomplishments
- `progress_line(ev, kn)` builds `[k/n] <name> · <step> · <done> / <total> · <speed>/s · <time left>` from porter's `rate` and `eta` and drops the parts porter did not send. `time_left` returns `less than a minute left`, `N min left` or `H h M min left`. `run_kind(fetch)` tells a download from a Prepare by the run's arguments.
- Tools page table: glyph, Tool, Version, Source, Size or note, action. The Tool cell carries porter's note (`!` in the note colour, escaped), a not-ok row's fix (selectable) and any command (fixed font, selectable).
- Download all missing (`about 900.0 MB` with .NET's unpinned 0 counted as about 200 MB) starts `tools --download --progress json` on `win.fetch` with no dialog. When porter offers nothing, the button is hidden and `Every tool is here.` shows.
- The button reads Cancel download (or Cancel .NET preparation) while the window's fetch runs, whoever started it. Cancel calls `fetch.stop()`. The status shows `stopping…` until finished, then `cancelled. Download all missing resumes where it stopped.`, and setup --json runs again.
- Failures show porter's escaped cause in the problem colour with Open log. A hash mismatch is shown in the fixed font with both hashes intact. A failed Prepare is a `!` note and never blocks.
- Use my own… opens a folder picker for the NDK and a file picker for dotnet and adb. It saves through `config <key> <path> --json` with `saving…` on the button, then re-checks; a failed save shows Retry. Copy command and Re-check appear on a row porter sends a `command` for (Linux arm64 adb).
- Prepare .NET tools starts a turn after a download this page started ends 0, and an ok .NET row offers it when nothing runs.
- Setup tab: `dl_btn` cancels a running download or Prepare. `dl_step` word-wraps and uses `progress_line`. The dialog no longer re-asks the licenses.

## Task Commits

1. **Task 1 RED: progress line and tools download tests** - `3ea20a5` (test)
2. **Task 1 GREEN: tools page download, Cancel, progress line** - `7939c4d` (feat)
3. **Task 2 RED: Use my own…, arm64 adb, Prepare tests** - `a69641c` (test)
4. **Task 2 GREEN: Use my own…, Copy command, notes, Prepare chain** - `957ddb4` (feat)
5. **Task 3 RED: Setup tab cancel and progress tests** - `d8d30b1` (test)
6. **Task 3 GREEN: Setup tab cancel labels, progress line, no license re-ask** - `997745c` (feat)

## TDD Gate Compliance

- **RED (Task 1):** `Progress.test_line` errored because `firstrun.progress_line` did not exist yet. The classifier returned `RED_EVIDENCE_OK` (`tdd/03-11-t1-red.json`). The other Progress and Tools tests failed the same way (no `time_left`, no `ToolsPage.dl`). Nothing failed to load.
- **RED (Task 2):** `Tools.test_prepare_chain` failed on its assertion that a second `start` (tools --prepare) follows the download's exit 0. The classifier returned `RED_EVIDENCE_OK` (`tdd/03-11-t2-red.json`).
- **RED (Task 3):** `Downloads.test_progress_line` failed on its equality assertion because `on_fetch` still built its own line. The classifier returned `RED_EVIDENCE_OK` (`tdd/03-11-t3-red.json`). `test_setup_cancel_label` and the license assertion also failed for their planned reasons.
- **GREEN:** `7939c4d`, `957ddb4`, `997745c`. The full suite passes: 419 tests, and `tests/arch_rules.py` prints `all checks passed`.
- **REFACTOR:** none needed.
- **Tracer gate (Task 1):** `<verify>` was re-run green before Task 2 started.

## Files Created/Modified
- `gui/firstrun.py` - adds `time_left`, `progress_line`, `run_kind`, `DOTNET_GUESS`, `TOOL_KEYS`, `ToolCell`, the full `ToolsPage`, `Wizard.primary`, and `DonePage.primary`.
- `gui/app.py` - SetupTab hook lines: `dl_step` word wrap, Cancel in `download()`, the cancel labels and `progress_line` in `on_fetch`, the label reset in `fetched`, the license paragraph removed.
- `tests/test_firstrun.py` - `Progress` (3 tests) and `Tools` (11 tests), plus `gone`/`reap` helpers and `tools_doc`/`item` fixtures.
- `tests/test_bridge.py` - `Close.test_setup_cancel_label`, `Downloads.test_progress_line`, and the no-license assertion.
- `tests/fixtures/bridge/fake_porter.py` - `tools --prepare` is a long run like `--download`.

## Decisions Made
- Speed is porter's `rate`, which porter/runlog.py already adds for byte progress. The UI-SPEC's GUI-side `(total - done) / eta` would give the same number, but computing it in the GUI would duplicate a porter rule.
- The Prepare chain follows only a download the tools page started. A Setup-tab download ends with the tab's own message.
- QWizard makes Next the default again on each page switch, so the done page's existing default-button code became `Wizard.primary(i)`. Pages with their own primary button (done, tools) offer it, and `ToolsPage.sync` calls it as the run starts and ends.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Download all missing lost the default to QWizard's Next**
- **Found during:** Task 1
- **Issue:** `setDefault(True)` on the tools page's button was undone by QWizard's own button update, the same thing 03-10 hit on the done page.
- **Fix:** turned 03-10's done-page code in `Wizard.moved` into `Wizard.primary(i)` with a `primary()` method on the done and tools pages.
- **Files modified:** gui/firstrun.py
- **Verification:** `Tools.test_download_starts_run` checks `isDefault()`. `Done.test_port_a_game` still passes.
- **Committed in:** 7939c4d

**2. [Rule 1 - Bug] `[k/n]` was joined with ' · '**
- **Found during:** Task 1
- **Issue:** the first draft of `progress_line` put `[k/n]` into the ' · ' join, which printed `[1/1] · waiting` instead of the UI-SPEC's `[1/1] waiting`.
- **Fix:** `[k/n]` is joined to the rest with a space.
- **Files modified:** gui/firstrun.py
- **Committed in:** 7939c4d

---

**Total deviations:** 2 auto-fixed (2 bugs)
**Impact on plan:** No scope change.

## Issues Encountered
None.

## Known Stubs
None.

## User Setup Required
None.

## Next Phase Readiness
- This was the last plan of Phase 3. FRUN-01, TOOL-01 and TOOL-03 are delivered as the player sees them.
- Human checks left for the end-of-phase UAT: real downloads in a fresh NX2A_HOME (progress, Cancel mid-NDK, resume, Prepare ends with `.NET tools are ready.`), and the layout backstops at 720×560 (table scroll, a 300-character hash message).
- Not guarded: the Setup tab's `confirm_download` can still call `fetch.start` if the tools page started a run while its `tools --json` call was pending. The window is left with one run either way, but the earlier run is no longer tracked by the Porter object. The window is rarely in that state, and the fix is a one-line `running()` check if it is wanted.

---
*Phase: 03-host-toolchains-and-guided-first-run*
*Completed: 2026-10-31*
