---
phase: 02-porter-hardening
plan: 01
subsystem: porter
tags: [flock, msvcrt, file-lock, atomic-rename, hashlib, datapack]

requires: []
provides:
  - "porter/lock.py take(work, cmd): the OS lock on <tid>_build/.porter.lock naming the holder's command, PID and start time"
  - "Port.lock, taken in Port.inputs right after self.work is set"
  - "porter install takes the same lock through the host-only sidecar <App>-data.build (D-14)"
  - "datapack.recover(dst), datapack.build_dir(dst), datapack.build(..., build=) and the aside swap via <App>-data.old"
  - "adb.md5(p): MD5 through hashlib.file_digest, used by push_tree"
affects: [02-porter-hardening, gui, install]

actuals:
  tokens: 6750
  tasks: 2
  commits: 4
plan_head_before: 74523e2c03decd90f11cb7f6a253a06bdccf2ef5
plan_head_after: d09dae6673e9abf3dbac8b9be20c50ca136c653e

tech-stack:
  added: []
  patterns:
    - "Build-folder lock: an OS lock on a never-deleted file, the locked byte at offset 4096 so Windows readers still see the holder's text"
    - "Aside swap: rename the old output to .old, rename the new one in, then delete .old; recover() renames .old back when the output is missing"
    - "Host-only sidecar beside a pushed folder for host paths (D-14)"

key-files:
  created:
    - porter/lock.py
    - tests/test_lock.py
    - tests/test_datapack.py
  modified:
    - porter/pipeline.py
    - porter/cli.py
    - porter/datapack.py
    - porter/adb.py
    - docs/ARCHITECTURE.md

key-decisions:
  - "The old data pack is renamed directly to <App>-data.old (no retry); only the new pack's rename goes through upstream's nsp.swap_in, for its Windows virus-scanner retry"
  - "porter install holds the lock in a local of cli.py go(); install.install never takes it, because Port.install calls it in the process that already holds the flock"
  - "A drive without file locks (ENOLCK, EOPNOTSUPP, ENOTSUP) runs unlocked with a [RED] line instead of refusing every port there"

patterns-established:
  - "Holder subprocess tests: a child takes the lock, prints 'held', and the test kills it as cleanup"

requirements-completed: [HARD-04, HARD-07]

coverage:
  - id: D1
    description: "A second port or install of a held build folder stops at once with 'already running' naming the holder's command, PID and start time"
    requirement: HARD-04
    verification:
      - kind: unit
        ref: "tests/test_lock.py#Lock.test_second_take_names_holder"
        status: pass
      - kind: unit
        ref: "tests/test_lock.py#Lock.test_port_inputs_takes_lock"
        status: pass
      - kind: integration
        ref: "tests/test_lock.py#Lock.test_install_cli_already_running"
        status: pass
    human_judgment: false
  - id: D2
    description: "A dead holder frees the lock; an empty lock file names 'another porter'; a symlinked spelling of the folder conflicts; take creates the folder"
    requirement: HARD-04
    verification:
      - kind: unit
        ref: "tests/test_lock.py#Lock.test_freed_when_holder_dies"
        status: pass
      - kind: unit
        ref: "tests/test_lock.py#Lock.test_empty_lock_file"
        status: pass
      - kind: unit
        ref: "tests/test_lock.py#Lock.test_symlink_spelling"
        status: pass
      - kind: unit
        ref: "tests/test_lock.py#Lock.test_creates_folder"
        status: pass
    human_judgment: false
  - id: D3
    description: "The data pack is swapped aside; a crash mid-swap leaves <App>-data.old, which the next build or porter install renames back"
    requirement: HARD-07
    verification:
      - kind: unit
        ref: "tests/test_datapack.py#Swap.test_rebuild_leaves_one_pack"
        status: pass
      - kind: unit
        ref: "tests/test_datapack.py#Swap.test_crash_mid_swap_keeps_old_pack"
        status: pass
      - kind: integration
        ref: "tests/test_datapack.py#Swap.test_install_recovers_first"
        status: pass
    human_judgment: false
  - id: D4
    description: "No host path in the pushed pack: the build folder lives only in the sidecar <App>-data.build (D-14)"
    requirement: HARD-04
    verification:
      - kind: unit
        ref: "tests/test_datapack.py#Swap.test_no_host_path_in_pack"
        status: pass
    human_judgment: false
  - id: D5
    description: "Install hashes modules in pieces with hashlib.file_digest"
    requirement: HARD-07
    verification:
      - kind: unit
        ref: "tests/test_datapack.py#Swap.test_md5_in_pieces"
        status: pass
    human_judgment: false
  - id: D6
    description: "Windows byte locks and the rename retry behave on the windows-2025 CI job"
    requirement: HARD-04
    verification: []
    human_judgment: true
    rationale: "Ran on macOS only; the plan's human-check is the windows-2025 job of fork-ci.yml after the phase is pushed"

duration: 10min
completed: 2026-10-30
status: complete
---

# Phase 02 Plan 01: Build-folder lock and data-pack swap Summary

**An OS file lock on `<tid>_build/.porter.lock` (flock, or a msvcrt byte lock at offset 4096) that makes a second port or install say "already running" with the holder's PID, plus a data-pack swap that renames the old pack aside, so a crash can never leave the game without one.**

## Performance

- **Duration:** about 10 min
- **Started:** 2026-10-30T17:24Z
- **Completed:** 2026-10-30T17:34Z
- **Tasks:** 2
- **Files modified:** 8 (3 created, 5 modified)

## Accomplishments

- `porter/lock.py` `take(work, cmd)`: locks the build folder, writes `porter <cmd>, PID <pid>, started <time>`, and raises `BuildError('already running: … is using <work>: …')` when another porter holds it. The file is never deleted, so a dead holder's lock is freed by the OS.
- `Port.inputs` takes the lock right after `self.work` is set, before anything is written there. `porter install` takes it on the folder named by the sidecar `<App>-data.build`. A pack without a sidecar installs unlocked.
- `datapack.build` writes the sidecar beside the pack, never inside it (D-14). It also calls `recover()` first and swaps through `<App>-data.old`.
- `porter install` calls `datapack.recover(data)` before it reads the manifest.
- `adb.md5` hashes in pieces with `hashlib.file_digest`, and `push_tree` uses it. No other whole-file hash exists in `porter/`.
- `docs/ARCHITECTURE.md` now covers the lock bullet, the shared iOS/Android `<tid>_build/` rule and the swap sentence.

## Task Commits

1. **Task 1: A held build folder makes a second port or install say "already running"** (tracer, TDD)
   - RED `e2debfb` test(02-01): add failing tests for the build-folder lock
   - GREEN `504a5db` feat(02-01): one port or install of a build folder at a time
2. **Task 2: The data pack is swapped aside, recovered after a crash, and install hashes in pieces** (TDD)
   - RED `7148b13` test(02-01): add failing tests for the data-pack swap and chunked MD5
   - GREEN `d09dae6` feat(02-01): swap the data pack aside and hash modules in pieces

No REFACTOR commits were needed.

## TDD Gate Compliance

- **Task 1 RED:** `.venv/bin/python -m unittest tests.test_lock` exited 1 with 7 of 7 tests failing. The classifier returned `RED_EVIDENCE_OK` (target `Lock.test_second_take_names_holder`). Semantic assessment: every test failed because `porter.lock` did not exist. The holder subprocess could not import it, and the in-process imports raised. That is the missing behaviour itself, not a fixture or syntax fault in the test file. GREEN: 7/7 OK.
- **Task 2 RED:** `.venv/bin/python -m unittest tests.test_datapack` exited 1 with 2 failures and 1 error. The classifier returned `RED_EVIDENCE_OK` (target `Swap.test_crash_mid_swap_keeps_old_pack`). Semantic assessment: the crash test failed with "KeyboardInterrupt not raised", because the old build never called `swap_in`. The install test failed because the aside pack was not restored. The md5 test raised AttributeError because there was no `adb.md5` yet. `test_rebuild_leaves_one_pack` and `test_no_host_path_in_pack` already passed: Task 1 added the sidecar, and the old remove-then-rename never left a `.old`. They act as regression guards. GREEN: 5/5 OK.
- **Tracer gate (Task 1):** human_verify_mode is end-of-phase and the verify block is automated only, so the verify was re-run: tests.test_lock passed 7/7 and arch_rules passed. Tracer verified end-to-end, then expanded to Task 2.

## Verification

- `.venv/bin/python -m unittest tests.test_lock tests.test_datapack -v`: 12 tests OK.
- `QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest tests.test_porter tests.test_runlog tests.test_architecture tests.test_datapack tests.test_lock`: 49 tests OK.
- `QT_QPA_PLATFORM=offscreen python3 -m unittest discover tests`: 127 tests OK. The same run under `.venv/bin/python` is also 127 OK.
- `.venv/bin/python tests/arch_rules.py`: all checks passed.
- All acceptance criteria were re-run and pass. `git diff --numstat 74523e2` shows cli.py with 3 added lines (limit 6) and pipeline.py with 2 added lines (limit 3). `grep -c lock porter/install.py` returns 0.

## Decisions Made

- The old pack is renamed straight to `.old` and only the new pack's rename goes through `nsp.swap_in`, as the plan specified. The crash test patches `swap_in`, so routing the first rename through it as well would hide the aside state the test checks.
- The lock file stays open in a local variable (`held`) for the whole of `go()`, and on `Port.lock` for the port.

## Deviations from Plan

None. The plan was executed exactly as written.

## Issues Encountered

None.

## Known Stubs

None.

## Next Phase Readiness

- Windows behaviour (the msvcrt byte lock and the swap_in retry) is covered by the same tests but has run only on macOS so far. The windows-2025 job of fork-ci.yml must run green after the push (the plan's human-check).
- Ready for the next plan of phase 02.

## Self-Check: PASSED

- FOUND porter/lock.py, tests/test_lock.py, tests/test_datapack.py
- FOUND commits e2debfb, 504a5db, 7148b13, d09dae6 (ancestors of HEAD); 4 commits measured from 74523e2..HEAD
