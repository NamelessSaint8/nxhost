---
phase: 03-host-toolchains-and-guided-first-run
plan: 03
subsystem: infra
tags: [toolchains, downloads, http-range, ndk, linux-arm64, progress-protocol, macos-privacy]

requires:
  - phase: 03-02
    provides: hosttools.linux_arm64()
  - phase: 02
    provides: porter/pins.py pinned downloads, fetch._install archive checks, tls.context()
provides:
  - pins.NDK['files']['linux-arm64'] (community r27c, sha256)
  - fetch._ndk_host(); arm64 hosts never plan adb
  - fetch._download(it, dest, retries=3) with Range resume, logged retries, Cancel keeps .part
  - stale .part cleanup and a disk refusal that names the toolchains folder
  - runlog adds `rate` to byte progress events; runlog._explain(e) for macOS privacy denials
affects: [03-04 probe, 03-05 setup wizard downloads, 03-08 ndk_pin watcher, gui download progress]

actuals:
  tokens: 14857
  tasks: 3
  commits: 6
plan_head_before: 551dfce74e8a41ecd4fd5eb5489e6ff2dd176833
plan_head_after: 10bd74a30986686690012f8360879ddddae10ae1

tech-stack:
  added: []
  patterns:
    - "Resume only on a 206 whose Content-Range starts at the .part size; any other 206 discards the part and asks again whole"
    - "Additive protocol fields are added in porter's log wrapper (runlog._wrap), never in the engine subtree"

key-files:
  created: []
  modified:
    - porter/pins.py
    - porter/fetch.py
    - porter/runlog.py
    - tests/test_fetch.py
    - tests/test_runlog.py
    - docs/ARCHITECTURE.md

key-decisions:
  - "A 206 for another offset deletes the .part and re-requests without Range (not spliced, not counted as a retry), so a whole file still arrives in one run"
  - "Retries count only dropped links (URLError/OSError/TimeoutError); a 416 with a .part ends the loop and the hash decides; a 416 with no .part raises"
  - "rate = round((total - done) / eta) only for unit B with truthy eta and total and a done value; every other event passes unchanged"

patterns-established:
  - "Pins tests patch porter.hosttools.linux_arm64 to False in setUp so the arm64 CI runner reads the same rows as every host"

requirements-completed: [TOOL-01, TOOL-02, FRUN-01]

coverage:
  - id: D1
    description: "Linux arm64 plans the pinned community NDK r27c (sha256) and never falls back; a mismatch names both hashes and the pin bump / own-NDK fix"
    requirement: TOOL-01
    verification:
      - kind: unit
        ref: "tests/test_fetch.py#Pins.test_arm64_ndk_row, test_arm64_ndk_gone_stops, test_ndk_mismatch_fix_text, test_rows_complete"
        status: pass
    human_judgment: false
  - id: D2
    description: "Linux arm64 plans .NET from its linux-arm64 pin and never plans adb (missing() leaves it out, --only adb names the distribution's adb)"
    requirement: TOOL-02
    verification:
      - kind: unit
        ref: "tests/test_fetch.py#Pins.test_arm64_dotnet, test_arm64_no_adb"
        status: pass
    human_judgment: false
  - id: D3
    description: "Downloads resume their .part with Range within a run (3 logged retries) and across runs; Cancel keeps it; mismatches delete it; stale parts are cleared; disk refusal names the folder"
    requirement: FRUN-01
    verification:
      - kind: unit
        ref: "tests/test_fetch.py#Resume (10 tests)"
        status: pass
    human_judgment: false
  - id: D4
    description: "Byte progress events carry rate; a macOS EPERM names the path and Privacy & Security in one-shot and long-run errors"
    requirement: FRUN-01
    verification:
      - kind: unit
        ref: "tests/test_runlog.py#Rate, Privacy"
        status: pass
    human_judgment: false
  - id: D5
    description: "A real resume against the GitHub/Google/Microsoft servers and a real community NDK unpack on a Linux arm64 host"
    verification: []
    human_judgment: true
    rationale: "Tests fake urlopen; the server measurements are RESEARCH's. A real arm64 download needs the arm64 host (phase UAT)."

duration: 8min
completed: 2026-10-31
status: complete
---

# Phase 3 Plan 03: Community arm64 NDK pin, resumable downloads, progress rate and macOS privacy message Summary

**Linux arm64 now downloads the pinned community NDK r27c (sha256, no fallback) and is never offered x86 platform-tools. Every toolchain download resumes its `.part` with HTTP Range after a dropped link, a Cancel or a restart. Byte progress events carry `rate`, and a macOS privacy denial names the path and System Settings › Privacy & Security.**

## Performance

- **Duration:** 8 min
- **Started:** 2026-10-31T15:41:34Z
- **Completed:** 2026-10-31T15:49:31Z
- **Tasks:** 3
- **Files modified:** 6 (plus 3 RED evidence records)

## Accomplishments
- `pins.NDK['files']['linux-arm64']`: the HomuHomu833 r27 asset, 127731408 bytes, sha256 `9c6214a6…fdc00c`. `fetch._ndk_host()` picks it on Linux arm64. A 404 stops naming the URL, and a hash mismatch says `wait for a pin bump of porter/pins.py, or point Setup at your own NDK (Use my own…)`.
- On Linux arm64, `missing()` leaves adb out, and `plan(['adb'])` raises `Google ships no Android platform-tools for Linux arm64: install your distribution's adb package…`. .NET comes from its existing `linux-arm64` pin.
- `_download(it, dest, retries=3)`:
  - It re-hashes the bytes already on disk, then asks for the rest with `Range: bytes=<size>-`.
  - It appends only on a 206 whose `Content-Range` starts at the size of the `.part`.
  - A 200 rewrites the file from zero. A 206 for another offset discards the part and asks again for the whole file.
  - A 416 lets the hash decide.
  - It retries a dropped link up to 3 times, with a logged `<file>: <error>, retry N` line.
  - A KeyboardInterrupt (Cancel) is never caught, so the `.part` stays.
  - A final mismatch deletes the `.part`.
- `download()` deletes other archives' `*.part` files in `player_tools()`. Its disk refusal names the toolchains folder, its drive, and the `NX2A_HOME` / Use my own… way out.
- `runlog._wrap._json` adds `rate` to `unit: B` progress events, without editing the engine subtree. `runlog._explain(e)` maps a macOS `PermissionError` with errno EPERM to the Privacy & Security message, in both the one-shot `{"error"}` and the long-run `error` event and log.
- `docs/ARCHITECTURE.md` now documents `rate`, the resume rules, the privacy message, the community arm64 NDK pin and its fail-closed rule, and the fact that arm64 hosts get no adb download.

## Task Commits

1. **Task 1: community linux-arm64 NDK pin, arm64 adb refusal** - `4a2b50f` (test, RED), `e65c397` (feat, GREEN)
2. **Task 2: Range resume, retries, Cancel, stale parts** - `8fd8d2c` (test, RED), `907cd88` (feat, GREEN)
3. **Task 3: rate, macOS privacy message, protocol docs** - `1725d53` (test, RED), `10bd74a` (feat, GREEN)

No refactor commits were needed.

## TDD Gate Compliance

- **Task 1 RED:** `tests.test_fetch.Pins`, target `test_rows_complete`, failed on the missing `linux-arm64` row (classifier: RED_EVIDENCE_OK). The arm64 plan, gone, adb and fix-text tests also failed on their planned assertions. `test_arm64_dotnet` already passed, because the .NET arm64 pin predates this plan. Evidence: `tdd/03-03-t1-red.json`.
- **Task 2 RED:** `tests.test_fetch.Resume`, target `test_across_runs`, failed with no Range header sent (RED_EVIDENCE_OK). `test_cancel_keeps_part` already passed and pins today's behaviour. Evidence: `tdd/03-03-t2-red.json`.
- **Task 3 RED:** `tests.test_runlog.Rate` and `Privacy`, target `test_one_shot`, failed on the missing Privacy & Security text (RED_EVIDENCE_OK). The unchanged-path tests already passed. Evidence: `tdd/03-03-t3-red.json`.
- **GREEN:** all of them pass. Full suite: 299 tests OK, and `tests/arch_rules.py` passes all checks.

## Files Created/Modified
- `porter/pins.py`: adds the community `linux-arm64` NDK row, with a header comment on why a re-upload stops.
- `porter/fetch.py`: adds `_ndk_host`, the arm64 adb rules, the NDK fix text, the resumable `_download`, stale part cleanup and the new disk message.
- `porter/runlog.py`: adds the `rate` field and `_explain`.
- `tests/test_fetch.py`: adds the Pins arm64 cases, plus `Part`, `Server` and the `Resume` class.
- `tests/test_runlog.py`: adds the `Stand`, `Rate` and `Privacy` classes.
- `docs/ARCHITECTURE.md`: adds the protocol bullets and the NDK/adb install lines.

## Decisions Made
- When a 206 comes back for the wrong offset, the code deletes the `.part` and loops without Range instead of writing that body from zero, because writing it would have produced a guaranteed hash mismatch. This does not count against the 3 retries, and it cannot loop, because a request without Range is never checked against Content-Range.
- The arm64 tests patch `porter.hosttools.linux_arm64` instead of `_ndk_host`. This runs the real `_ndk_host`, and it means one patch also covers the adb rules.

## Deviations from Plan

None. The plan was executed as written. One choice inside the plan's rules: "treated as no-Range (start over)" is implemented as "discard the part and request again without Range", as described under Decisions Made.

## Issues Encountered
None.

## Known Stubs
None.

## User Setup Required
None. No external service configuration is required.

## Next Phase Readiness
- 03-04 (probe) can rely on `_ndk_host()` and the `android-ndk-r27c` folder for the community build.
- 03-08's `devtools/ndk_pin.py` is referenced from the `pins.py` header and does not exist yet.
- The GUI can show `rate` from byte progress events.
- Not checked: a real download and resume against the live servers, and unpacking the real community tarball on a Linux arm64 host. These belong to phase UAT.

---
*Phase: 03-host-toolchains-and-guided-first-run*
*Completed: 2026-10-31*

## Self-Check: PASSED
- Files exist: porter/pins.py, porter/fetch.py, porter/runlog.py, tests/test_fetch.py, tests/test_runlog.py, docs/ARCHITECTURE.md
- Commits on this branch: 4a2b50f, e65c397, 8fd8d2c, 907cd88, 1725d53, 10bd74a
- Acceptance criteria re-run: pin row `(127731408, 'sha256')`, `def _ndk_host` 1, `pin bump` 1, `Range` 4, `'ab'` 1, `'rate'` 1, `Privacy & Security` 1, `rate` in ARCHITECTURE.md 6, engine emitter untouched
