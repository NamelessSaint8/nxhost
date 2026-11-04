---
phase: 11-compile-the-c-host-in-ci
plan: 01
subsystem: cli
tags: [porter, pipeline, json-protocol, runlog, mac-app, android]

# Dependency graph
requires:
  - phase: 09-one-port-entry-point-for-android-and-mac
    provides: --platform mac-app and Port.run_mac (the Mac chain the driver calls second)
  - phase: 02-...
    provides: the one-port-at-a-time lock (porter/lock.py) taken per build folder
provides:
  - "--platform both: one run builds the APK and the Mac app, Android first (Port.run_both)"
  - "Port.begin(): one folder scan and one lock per run, inherited by both target children"
  - "TargetSkipped: a target a host or a profile cannot build is skipped, never failed"
  - "result.targets[] ({platform, status, out, reason}) beside the unchanged flat apk/data/app keys"
  - "platform on stage / step / progress / stage_end (runlog.set_platform), never on result"
  - "exit 1 iff any targets[].status == 'failed' (cli._with_progress returns the callback's code)"
affects: [11-02, 11-03, 12, gui PortTab]

# Actuals (#2632, chars/4 over the realized diff, not a harness token count)
actuals:
  tokens: 5800
  tasks: 3
  commits: 6

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "A driver over two Port objects, each requiring its own toolchain (one target's tools never gate the other)"
    - "Skips are raised (TargetSkipped extends BuildError) at the one place that already decides them"
    - "The target is stamped on events in porter/runlog.py's wrapper, never in the upstream engine subtree"

key-files:
  created: []
  modified:
    - porter/pipeline.py
    - porter/cli.py
    - porter/runlog.py
    - tests/test_porter.py
    - docs/ARCHITECTURE.md

key-decisions:
  - "The result is additive: targets[] sits beside the flat apk/data/app keys, because gui/app.py install_now() reads those (D-08, RESEARCH Pitfall 7)"
  - "Both is a driver over two Ports, and each child requires its own toolchain, so a host without the NDK still builds the Mac app (D-04/D-06)"
  - "MAC_NEEDS_MAC is one sentence used by run_mac()'s refusal and the both run's skip reason, so the two cannot drift (D-03)"
  - "A game with no game profile at all is skipped for the Mac target too, so a both run does not exit 1 for a game nobody supports yet"

patterns-established:
  - "One scan and one lock per run: Port.begin() owns them, inputs() asks for it only when the driver has not (QUAL-13)"
  - "Only BuildError is a target failure; anything else propagates as the crash it is"

requirements-completed: [QUAL-13]

coverage:
  - id: D1
    description: "--platform both drives Android then the Mac app from one command, one scan, one lock and one result"
    requirement: QUAL-13
    verification:
      - kind: unit
        ref: "tests/test_porter.py#Both.test_both_runs_android_then_mac"
        status: pass
      - kind: unit
        ref: "tests/test_porter.py#Both.test_run_dispatches_both_to_the_driver"
        status: pass
      - kind: unit
        ref: "tests/test_porter.py#Both.test_the_driver_takes_the_lock_and_a_child_does_not"
        status: pass
    human_judgment: false
  - id: D2
    description: "A target a host or a profile cannot build is reported skipped with its reason, and the other target still builds"
    requirement: QUAL-13
    verification:
      - kind: unit
        ref: "tests/test_porter.py#Both.test_no_android_tsv_is_a_skip_in_a_both_run"
        status: pass
      - kind: unit
        ref: "tests/test_porter.py#test_mac_target_is_skipped_off_macos"
        status: pass
      - kind: unit
        ref: "tests/test_porter.py#test_a_failed_target_does_not_stop_the_other"
        status: pass
    human_judgment: false
  - id: D3
    description: "The exit code carries the failure: 1 iff any target failed, 0 when both built or one was skipped"
    requirement: QUAL-13
    verification:
      - kind: unit
        ref: "tests/test_porter.py#test_exit_code_one_when_a_target_failed"
        status: pass
      - kind: unit
        ref: "tests/test_porter.py#test_exit_code_zero_when_none_failed"
        status: pass
    human_judgment: false
  - id: D4
    description: "The protocol grew additively: platform on the stage events, targets[] only for a multi-target run, the single-target goldens untouched"
    requirement: QUAL-13
    verification:
      - kind: unit
        ref: "tests/test_porter.py#test_runlog_platform_reaches_the_event_not_the_result"
        status: pass
      - kind: integration
        ref: "tests.test_bridge (goldens replay unchanged; port_ok.jsonl not regenerated)"
        status: pass
    human_judgment: false
  - id: D5
    description: "A partial run reads as the user wants in UAT: `done: the APK built (<apk>) / the Mac app failed (<reason>)` and exit 1 is the right outcome for a working APK"
    verification: []
    human_judgment: true
    rationale: "The plan's QUAL-13 unclassified edge: whether a green package beside a failed target should read as a failure is a product judgement the user makes in UAT; the machine-readable contract (exit code + targets[]) is asserted by unit tests, the wording is not."
  - id: D6
    description: "A real `porter port <folder> --platform both` on this Mac produces both packages and two rows"
    verification:
      - kind: manual_procedural
        ref: "deferred to Phase 12's device smoke: needs a game folder, the NDK and the Metal chain"
        status: unknown
    human_judgment: true
    rationale: "No game files or toolchains in this environment; the plan defers the end-to-end run to Phase 12's smoke."

# Metrics
duration: 20min
completed: 2026-11-04
status: complete
---

# Phase 11 Plan 01: A one-run, two-target port driver Summary

**`porter port --platform both` builds the APK and the Mac app from one command, one scan and one lock, reporting each target's outcome in `targets[]` and exiting 1 only when one of them failed.**

## Performance

- **Duration:** 20 min
- **Started:** 2026-11-04T10:47Z
- **Completed:** 2026-11-04T11:07Z
- **Tasks:** 3
- **Files modified:** 5

## Accomplishments
- `Port.run_both()` drives two `Port` children (Android first), each on its own target, each requiring its own toolchain, so a host without the NDK still builds the Mac app (D-04/D-06).
- `Port.begin()` keeps the folder scan and the one-port-at-a-time lock at one call per run; a child inherits `work`/`app`/`fam` and never asks for the lock again (QUAL-13).
- `TargetSkipped` (a `BuildError`) reports a profile without `android.tsv` and a non-Mac host as `skipped` with a named reason, and `MAC_NEEDS_MAC` is shared with `run_mac()`'s refusal so the two cannot drift (D-03/D-07).
- One `result` per run: `targets[]` in run order beside today's flat `apk`/`data`/`app` keys, so `install_now()` and single-target readers keep working (D-08/Pitfall 7).
- `runlog.set_platform()` stamps `platform` on `stage`/`step`/`progress`/`stage_end` and never on `result`; `_with_progress` now returns the callback's code, and `cmd_port` returns 1 iff a row is `failed` (T-11-01/Pitfall 6).
- `docs/ARCHITECTURE.md` documents the both run, the extended events and the `targets`-only-on-multi-target rule.

## Task Commits

Each task was committed atomically (tasks 1 and 2 followed RED → GREEN):

1. **Task 1: One run, two targets** — `27fb6792` (test), `e9bb2656` (feat)
2. **Task 2: Skips are not failures** — `25ea49dc` (test), `1f4c21fb` (feat)
3. **Task 3: Exit code, log, protocol docs** — `55bb9af1` (feat)

**Plan metadata:** the commit after this file (`docs(11-01): complete ...`)


## Files Created/Changes
- `porter/pipeline.py` — `BOTH`, `TargetSkipped`, `MAC_NEEDS_MAC`, `Port.work`/`multi_target`, `_preflight()`, `begin()`, `run_both()`; `run()` dispatches `both` before any target's toolchain is required; `inputs()` skips `begin()` when a driver already ran it; the Android and Mac profile checks raise `TargetSkipped` only for a multi-target child.
- `porter/cli.py` — `--platform` takes `both`; `_with_progress` returns `fn() or 0`; `cmd_port`'s `go()` emits the one `result` and returns 1 iff a target failed.
- `porter/runlog.py` — `S['platform']`, `set_platform()`, and the additive `platform` stamp on the four stage events.
- `tests/test_porter.py` — the `Both` class: 13 tests covering order, inheritance, lock, skips, failure isolation, crash propagation, both-outcome logging and the exit code.
- `docs/ARCHITECTURE.md` — the both run's stages and sharing, `platform` on events, `targets[]` only for a multi-target result, and the Port pipeline row now names both targets.

## Decisions Made
- **Additive result (D-08):** `targets[]` is added, never substituted — `gui/app.py`'s `install_now()` reads `result['apk']`/`['data']`, and the bridge goldens pin the single-target shape.
- **Driver, not a phase list:** two `Port` instances rather than a parameterised one, because `mac`, `aw`, `ap`, `patched`, `host_bin` are all per-target instance state.
- **Skips near their owner:** the "has an `android.tsv`" rule stays in `profiles.by_title()`; the driver never re-derives it.
- **No Mac child off macOS:** the row is appended before construction, so the refusal cannot be caught as a failure.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing critical functionality] A both run's Mac row is a skip when the game has no profile at all**
- **Found during:** Task 2
- **Issue:** the plan named only the Android branch for `TargetSkipped`; with `--platform both` a game nobody supports yet would have raised `BuildError` for the Mac child and made the run exit 1, while the Android row was `skipped` for the same missing profile.
- **Fix:** the Mac branch's `g is None` refusal raises `TargetSkipped` when `self.multi_target`, keeping the single-target refusal byte-identical.
- **Files modified:** `porter/pipeline.py`
- **Verification:** `tests.test_porter.Both.test_no_game_profile_is_a_skip_for_a_mac_target_too`
- **Committed in:** `1f4c21fb` (Task 2 feat)

**2. [Rule 3 - Blocking issue] `_preflight()` extracted, and `begin()` owns the prologue `run_both()` needs**
- **Found during:** Task 1
- **Issue:** dispatching `both` before the prologue (as the plan's line 92 note implies, and as D-06 requires — the Android NDK must not gate the Mac app) left `run_both()` without a resolved folder/keys/env for the shared scan.
- **Fix:** the folder/keys/out checks moved into `_preflight()` (shared by `run()` and `run_both()`), and `run_both()` builds the child env from `toolchain.find_dotnet()` for the one scan. `both` still never sets `self.mac` and never calls `toolchain.require`, so each target's toolchain is its own.
- **Files modified:** `porter/pipeline.py`
- **Verification:** `tests.test_porter.Both.test_run_dispatches_both_to_the_driver`, `test_both_runs_android_then_mac`; full suite green
- **Committed in:** `e9bb2656` (Task 1 feat)

**3. [Rule 1 - Bug] The skip sentence reconciles the plan's two phrasings**
- **Found during:** Task 2
- **Issue:** the plan's action text wanted the existing sentence minus the `--experimental` clause, while its acceptance criteria require `no android.tsv for this game`. The two cannot both be the literal string.
- **Fix:** the skip reason reads `<name> (<id>) has a game profile but is not ported to Android yet: no android.tsv for this game` — the acceptance criteria's phrase, no `--experimental`, the same fact as before.
- **Files modified:** `porter/pipeline.py`
- **Verification:** `tests.test_porter.Both.test_no_android_tsv_is_a_skip_in_a_both_run`
- **Committed in:** `1f4c21fb` (Task 2 feat)

---

**Total deviations:** 3 auto-fixed (1 Rule 1, 1 Rule 2, 1 Rule 3)
**Impact on plan:** All three keep the plan's contract intact; no scope creep. The only shape change is `_preflight()`, which is the prologue `run()` already ran, moved so both entry points share it.

## Issues Encountered
None. The tracer gate was satisfied by re-running its automated `<verify>` after the commit (all green); this run is non-interactive, so no human checkpoint was raised for it.

## User Setup Required
None — no external service configuration required.

## Known Stubs
None.

## Next Phase Readiness
- Ready for plan 11-02/11-03: the protocol now carries `platform` on the stage events and `targets[]` on `result`, which is what the Port view keys its rows by.
- Deferred and documented: a real `porter port --platform both` end-to-end run (needs a game folder plus the NDK and Metal chain) belongs to Phase 12's smoke; the `port_both.jsonl` golden belongs to plan 11-03.

---
*Phase: 11-compile-the-c-host-in-ci*
*Completed: 2026-11-04*

## Self-Check: PASSED

- Commits 27fb6792, e9bb2656, 25ea49dc, 1f4c21fb, 55bb9af1 all present.
- `.planning/phases/11-compile-the-c-host-in-ci/11-01-SUMMARY.md`, `porter/pipeline.py`, `tests/test_porter.py` present.
- `tests/fixtures/bridge/` untouched (goldens byte-identical).
