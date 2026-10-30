---
phase: 02-porter-hardening
plan: 04
subsystem: porter
tags: [toolchain, downloads, pins, zip-slip, tarfile, cve-2025-4517, gui]

requires:
  - phase: 02-porter-hardening
    provides: "02-01 lock/data-pack swap and 02-02 doctor Signing key row in porter/toolchain.py (checks() this plan edits)"
provides:
  - "porter/pins.py: NDK r27c, platform-tools 37.0.1, .NET SDK 10.0.403 pinned per host (URL, size, algo, hash)"
  - "fetch.plan() pinned-first with a 404/410 vendor fallback marked untested; the NDK never falls back"
  - "Item.untested (additive key in tools --json); [RED] untested line in the download log; (untested) in the Setup dialog"
  - "hash mismatch names the file, the algorithm and both hashes"
  - "safe _unzip/_untar (names checked first, links last and confined, tar filter='data'); _install removes the partial .unpack"
  - "toolchain.FLOORS and python_ok(); runlog.run refuses every command but doctor on a Python without the CVE-2025-4517 fix (PythonError)"
affects: [02-08 FPSLOCKER pin, 02-10 NUGET pin, phase 03 community linux-arm64 NDK row]

actuals:
  tokens: 18650
  tasks: 3
  commits: 6
plan_head_before: bdc7fa4d3a2c9a20ea47fe58be151f722481ac96
plan_head_after: 5b177177f98213e721976e7d168a2573cecc646b

tech-stack:
  added: []
  patterns:
    - "One data-only manifest (porter/pins.py) of {'version', 'files': {host: (url, size, algo, hash)}}; values copied from the vendor indexes by script"
    - "Archive members validated before anything is written; zip links created after every file and resolved on both sides against the unpack root"
    - "Python capability floor checked once in runlog.run before procs.setup, doctor exempt"

key-files:
  created:
    - porter/pins.py
    - tests/test_fetch.py
    - tests/test_toolchain.py
  modified:
    - porter/fetch.py
    - porter/toolchain.py
    - porter/runlog.py
    - gui/app.py
    - tests/test_bridge.py
    - docs/ARCHITECTURE.md

key-decisions:
  - "Pins re-read from Google's repository2-3.xml and Microsoft's 10.0 releases.json on 2026-10-30 by script; every value matched RESEARCH Pattern 3 (10.0.403 is still latest-sdk, 37.0.1 still in the index)"
  - "Tar archives also get the member-name check, not only filter='data': the data filter strips a leading / and goes on, but the plan's truth is that /abs refuses the whole archive"
  - "A long command refused for its Python also prints [RED] on stderr when --progress is not json, so a CLI user sees why"
  - "PythonError documented beside BuildError in ARCHITECTURE.md's protocol line"

patterns-established:
  - "Pinned download, visibly untested fallback: Item.untested travels tools --json -> GUI dialog and download log"

requirements-completed: [HARD-01, PKG-07]

coverage:
  - id: D1
    description: "Each toolchain download is the pinned file for this host, checked against its pinned hash; a mismatch stops naming the file and both hashes"
    requirement: PKG-07
    verification:
      - kind: unit
        ref: "tests/test_fetch.py#Pins.test_rows_complete"
        status: pass
      - kind: unit
        ref: "tests/test_fetch.py#Pins.test_pinned_row_used"
        status: pass
      - kind: unit
        ref: "tests/test_fetch.py#Pins.test_mismatch_names_both_hashes"
        status: pass
      - kind: other
        ref: "NX2A_HOME=<tmp> python -m porter tools --download --only adb (real 37.0.1 darwin zip, hash checked, unpacked, adb runs)"
        status: pass
    human_judgment: false
  - id: D2
    description: "Pinned URL gone (404/410): platform-tools and .NET fall back to the vendor's newest marked untested; NDK stops with how to install r27c; a host with no row is untested"
    requirement: PKG-07
    verification:
      - kind: unit
        ref: "tests/test_fetch.py#Pins.test_adb_gone_falls_back"
        status: pass
      - kind: unit
        ref: "tests/test_fetch.py#Pins.test_dotnet_gone_falls_back"
        status: pass
      - kind: unit
        ref: "tests/test_fetch.py#Pins.test_ndk_gone_stops"
        status: pass
      - kind: unit
        ref: "tests/test_fetch.py#Pins.test_no_row_is_untested"
        status: pass
    human_judgment: false
  - id: D3
    description: "The Setup tab's download dialog shows (untested) and html-escapes every item field, href included"
    requirement: PKG-07
    verification:
      - kind: automated_ui
        ref: "tests/test_bridge.py#Downloads.test_untested_and_escaped"
        status: pass
    human_judgment: false
  - id: D4
    description: "Crafted zip and tar archives (.., absolute, backslash, drive, escaping links, tar hard links) are refused whole, nothing is written outside the unpack folder and no .unpack is left; valid internal links and modes are kept"
    requirement: HARD-01
    verification:
      - kind: unit
        ref: "tests/test_fetch.py#Unpack"
        status: pass
    human_judgment: false
  - id: D5
    description: "Every porter command but doctor refuses a Python without the CVE-2025-4517 fix (floors or ALLOW_MISSING); doctor shows a red Python row naming the floors"
    requirement: HARD-01
    verification:
      - kind: unit
        ref: "tests/test_toolchain.py#PythonFloor"
        status: pass
      - kind: other
        ref: ".venv/bin/python -m porter doctor --json (Python row ok on 3.14.5)"
        status: pass
    human_judgment: false

duration: 8min
completed: 2026-10-30
status: complete
---

# Phase 2 Plan 04: Pinned toolchain downloads, safe unpacking and the Python floor Summary

**porter/pins.py pins NDK r27c, platform-tools 37.0.1 and .NET SDK 10.0.403 per host; fetch checks downloads against those hashes and falls back to a vendor's newest only when the pin is gone, marked untested up to the GUI dialog; hostile zip/tar archives are refused whole; porter refuses a Python whose tarfile filter can be bypassed.**

## Performance

- **Duration:** 8 min
- **Started:** 2026-10-30T17:52:57Z
- **Completed:** 2026-10-30T18:00:36Z
- **Tasks:** 3
- **Files modified:** 12 (9 code/docs/tests, 3 RED evidence records)

## Accomplishments

- One manifest, `porter/pins.py`, generated from the vendor indexes by a scratchpad script (no hand-copied hashes). `tools --json` on this Mac now lists the pinned 37.0.1 and 10.0.403 files with `"untested": false`.
- `fetch.plan()` HEADs the pinned URL; 404/410 is a fallback, not a mismatch; the NDK stops with `NDK r27c is no longer served at <url>: install it yourself ...`.
- A hash mismatch reads `<file>: its <algo> is <got>, not the expected <pinned> (from <url>): try again, and report it if it repeats`, with the `.part` deleted.
- Zip members are checked before anything is written. Links are created after every file and resolved against the unpack root on both sides. Tar uses `filter='data'` plus the same name check. Any failure removes `.<folder>.unpack`.
- `toolchain.python_ok()` covers the floors and the ALLOW_MISSING marker. `runlog.run` refuses before `procs.setup`, and doctor still runs.
- An end-to-end real download of platform-tools 37.0.1 into a temporary NX2A_HOME passed: hash check, safe unpack, and `adb version` runs.

## Task Commits

1. **Task 1: One manifest pins every toolchain download (tracer)**: RED `7760b57` (test), GREEN `81b2c74` (feat). The tracer gate (interactive, end-of-phase, automated-only verify) was re-run and passed before expansion.
2. **Task 2: Crafted zip and tar archives refused whole**: RED `8bd9094` (test), GREEN `d6edd3a` (fix)
3. **Task 3: Python tarfile-fix floor and refusal**: RED `6b4ffbd` (test), GREEN `5b17717` (feat)

## TDD Gate Compliance

Each task's RED run was classified `RED_EVIDENCE_OK` by `gsd-tools check tdd-red-evidence`. The records are in `.planning/phases/02-porter-hardening/.red-02-04-t{1,2,3}.json`.
- T1 target `Pins.test_pinned_row_used` failed on its planned assertion: plan() fetched Google's index instead of using the pin. The other errors were the missing `untested` attribute and the fallbacks, which is the expected missing behaviour. `test_rows_complete` passed in RED because pins.py (data only) was committed with the tests.
- T2 target `Unpack.test_bad_names_refused` failed because `_install` did not refuse. The tar cases raised a raw `OutsideDestinationError` rather than BuildError, which is expected before the change.
- T3 target `PythonFloor.test_refusal_one_shot` failed because runlog ran the command. `create=True` on the patch kept the target a real assertion failure rather than a patch error.
- Task 2's GREEN commit uses type `fix` (closing the zip-slip hole) rather than `feat`. RED still precedes GREEN for every task, and the plan's feat commits are 81b2c74 and 5b17717.

## Files Created/Modified

- `porter/pins.py`: NDK, PLATFORM_TOOLS, DOTNET rows and the bump procedure
- `porter/fetch.py`: `FOLDERS`, `_head`, `_pinned`, pinned-first `plan()`, `Item.untested`, the mismatch message, `_bad_name`/`_refuse_names`, the safe `_unzip`/`_untar`, the `_install` cleanup
- `porter/toolchain.py`: `FLOORS`, `python_ok()`, the Python row's fix text
- `porter/runlog.py`: `_refuse()` and the guard in `run()`
- `gui/app.py`: `confirm_download` escapes every field and shows `(untested)`
- `tests/test_fetch.py`: Pins (7) and Unpack (5)
- `tests/test_toolchain.py`: PythonFloor (5)
- `tests/test_bridge.py`: Downloads (1)
- `docs/ARCHITECTURE.md`: pinned downloads, the untested fallback, confined unpacking, the Python floors, `PythonError` in the protocol line

## Decisions Made

See key-decisions in the frontmatter.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] The member-name check also applies to tar archives**
- **Found during:** Task 2
- **Issue:** `filter='data'` strips a leading `/` and extracts `/abs` as `abs`, but the plan's behaviour (Unpack.test_tar_refused) requires `/abs` to refuse the whole archive.
- **Fix:** `_untar` runs `_refuse_names(arc, t.getnames())` before `extractall(filter='data')`.
- **Files modified:** porter/fetch.py
- **Verification:** tests/test_fetch.py Unpack.test_tar_refused, Unpack.test_valid_tar_kept
- **Committed in:** d6edd3a

**2. [Rule 2 - Missing Critical] A refused long command also says why on stderr outside JSON mode**
- **Found during:** Task 3
- **Issue:** The planned refusal for long commands only wrote the log and JSON events, so `porter port <folder>` in lines mode would exit 1 silently.
- **Fix:** `_refuse` prints `[RED] <msg>` on stderr unless `--progress json`.
- **Files modified:** porter/runlog.py
- **Committed in:** 5b17717

---

**Total deviations:** 2 auto-fixed (2 missing critical). **Impact:** both keep the plan's stated truths; no scope creep.

## Issues Encountered

None.

## Verification

- `.venv/bin/python -m unittest tests.test_fetch tests.test_toolchain tests.test_tls -v`: OK
- `QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover tests`: 163 tests OK (145 before this plan). `python3 -m unittest discover tests` (3.14.5): 163 OK.
- `python3 tests/arch_rules.py`: all checks passed
- `.venv/bin/python -m porter doctor --json`: Python row ok on 3.14.5, with the new fix text
- Acceptance greps: pins rows `3 3 4`; `untested` in fetch.py 6 and in app.py 1; `pins.` in fetch.py 3; `hasattr(tarfile` 0; `filter='data'` 1; `def _bad_name` 1; `def python_ok` 1; `python_ok()` in runlog 1; `PythonError` 1; `pins.py` and `3.11.13` in ARCHITECTURE.md 1 each

## Known Limitations

- NDK and platform-tools rows are keyed by `_google_os()`, as the plan specifies. On Linux arm64, that still selects the x86-64 `linux` NDK row, the same as before this plan. Phase 3 adds the community arm64 NDK row and needs an arch-aware key there.

## User Setup Required

None.

## Next Phase Readiness

- 02-08 (FPSLOCKER) and 02-10 (NUGET) add their pins to `porter/pins.py`.
- Phase 3 adds a linux-arm64 NDK row (sha256) and must make `_pinned` pick it by architecture.

## Self-Check: PASSED

- FOUND: porter/pins.py, tests/test_fetch.py, tests/test_toolchain.py
- FOUND commits: 7760b57, 81b2c74, 8bd9094, d6edd3a, 6b4ffbd, 5b17717
- evaluation-scope --plan 02-04 --commits-only: resolved, 6 commits

---
*Phase: 02-porter-hardening*
*Completed: 2026-10-30*
