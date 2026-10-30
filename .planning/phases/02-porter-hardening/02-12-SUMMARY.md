---
phase: 02-porter-hardening
plan: 12
subsystem: porter
tags: [lock, translator, dmsh_xlate, windows, unittest]
status: complete

requires:
  - phase: 02-porter-hardening
    provides: "02-01's porter/lock.py take() and 02-10's shared tools lock in porter/nuget.py restored()"
provides:
  - "porter/pipeline.py Port.translator: each key builds into <user dir>/tools/dmsh_xlate-<key[:12]> with its .key file beside it"
  - "porter/pipeline.py Port.translator: the reuse check repeated as the first line inside nuget.restored()"
  - "porter/lock.py take(): lock file opened with buffering=0, so the holder read is one OS read of at most AT bytes on every OS"
  - "tests/test_lock.py: BUILT holder program, class Spy, test_new_translator_key_keeps_old, test_holder_read_stays_below_lock, test_waiting_port_reuses_translator"
  - "docs/ARCHITECTURE.md tools-lock bullet names the key-named translator folders"
affects: [porter, lock, translator, HARD-04, CR-02, CR-03]

actuals:
  tokens: 3595
  tasks: 3
  commits: 6
plan_head_before: dc9dffe8a7863ad713dfb66c81bc544e66d74008
plan_head_after: ac525a06136626ce6fddba041404c3ede747a4c6

tech-stack:
  added: []
  patterns:
    - "Shared cache keyed by input hash goes into a key-named folder, so a rebuild for another key never replaces one in use"
    - "Under a wait lock, repeat the reuse check once the lock is held"
    - "A lock file whose byte range is locked on Windows is opened unbuffered, so reads stay below the locked byte"

key-files:
  created: []
  modified:
    - porter/pipeline.py
    - porter/lock.py
    - tests/test_lock.py
    - docs/ARCHITECTURE.md

key-decisions:
  - "CR-03 part b: key-named translator folders (dmsh_xlate-<key[:12]>) instead of holding the tools lock around the shaders stage, which deadlocks on POSIX flock (a second take in one process) and would queue every game's tool builds behind shader translation"
  - "CR-02: buffering=0 on the lock file, one code path on every OS, instead of the review's os.lseek/os.read variant; the existing f.seek(0); f.read(AT) line is unchanged"

patterns-established:
  - "Spy (io.FileIO subclass) refuses any read past lock.AT, so the Windows locked-byte bound is tested on POSIX"

requirements-completed: [HARD-04]

coverage:
  - id: D1
    description: "A translator rebuilt for a new key lands in its own folder and leaves the one another port uses in place"
    requirement: HARD-04
    verification:
      - kind: unit
        ref: "tests/test_lock.py#test_new_translator_key_keeps_old"
        status: pass
    human_judgment: false
  - id: D2
    description: "A port that waited on the tools lock reuses the translator the first port just built: only restore runs, no build, no swap"
    requirement: HARD-04
    verification:
      - kind: integration
        ref: "tests/test_lock.py#test_waiting_port_reuses_translator"
        status: pass
    human_judgment: false
  - id: D3
    description: "The holder lookup never asks the OS for more than AT bytes from offset 0, so on Windows a second porter says already running or waits instead of crashing"
    requirement: HARD-04
    verification:
      - kind: unit
        ref: "tests/test_lock.py#test_holder_read_stays_below_lock"
        status: pass
      - kind: manual_procedural
        ref: "fork-ci.yml windows-2025 job runs tests.test_lock against a real Windows byte-range lock"
        status: unknown
    human_judgment: true
    rationale: "Only the windows-2025 CI job can prove the unbuffered ReadFile below a locked byte succeeds on Windows (planner assumption A6); the POSIX Spy test pins the read bound only"

duration: 4min
completed: 2026-10-30
---

# Phase 2 Plan 12: Tools-lock translator reuse and unbuffered lock read Summary

**Each translator key builds into its own `dmsh_xlate-<key[:12]>` folder, a port that waited on the tools lock re-checks reuse before building, and the lock file is unbuffered so the holder read never reaches the byte Windows locks (CR-02, CR-03)**

## Performance

- **Duration:** 4 min (execution; plan and context reads before the clock started)
- **Started:** 2026-10-30T20:10:33Z
- **Completed:** 2026-10-30T20:14:01Z
- **Tasks:** 3
- **Files modified:** 4

## Accomplishments
- CR-03 part b: `Port.translator` builds into `<user dir>/tools/dmsh_xlate-<key[:12]>/` with `dmsh_xlate-<key[:12]>.key` beside it, so a rebuild for another key never removes a dll a running port's `shader_vk.py --xlate` uses. The shared `dmsh_xlate.partial` is unchanged (only touched under the lock).
- CR-03 part a: the reuse check runs again as the first line inside `nuget.restored()`, so the second of two ports that both need a new translator returns the first one's build.
- CR-02: `lock.take` opens `.porter.lock` with `buffering=0`. The test measured the old buffered `read(4096)` asking for 131072 bytes at offset 0 on Python 3.14; the unbuffered read stays within 4096.
- Full suite: 225 tests OK (`QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover tests`), `tests/arch_rules.py` all passed.

## Task Commits

1. **Task 1: A translator rebuilt for a new key lands beside the one another port is using** - RED `5acfd1a` (test), GREEN `193f6ea` (fix)
2. **Task 2: A second porter reads who holds the lock without touching the locked byte** - RED `5b2f4f6` (test), GREEN `a5b5fd0` (fix)
3. **Task 3: A port that waited on the tools lock reuses the translator the first port just built** - RED `cad95dc` (test), GREEN `ac525a0` (fix)

## Files Created/Modified
- `porter/pipeline.py` - `Port.translator`: key-named `out`/`kf`, CR-03 and shortcut comments, the reuse re-check inside the lock, docstring path
- `porter/lock.py` - `take`: `open(..., 'a+b', buffering=0)` with the CR-02 comment; AT comment updated
- `tests/test_lock.py` - `BUILT`, `Spy`, `Lock.translator_port`, and the three tests; header names the tools lock and translator reuse
- `docs/ARCHITECTURE.md` - tools-lock bullet: `<user dir>/tools/dmsh_xlate-<key>` and the per-key folder sentence

## TDD Gate Compliance

Each task ran RED then GREEN. Each RED record passed `gsd-tools check tdd-red-evidence` with `RED_EVIDENCE_OK`. The GREEN commits use `fix(porter): ...`, as the plan says, not `feat(02-12): ...`.
- Task 1 RED: `assertNotEqual(d1, d2)` failed. Both keys returned `tools/dmsh_xlate/dmsh_xlate.dll`. That is the planned assertion failing for the CR-03 reason.
- Task 2 RED: the test errored with `PermissionError: read of 131072 bytes at 0 crosses the byte locked at 4096`, raised by Spy out of `take()`. This is the error the plan expected, and it matches the CR-02 measurement.
- Task 3 RED: `ran` was `['restore', 'build']` where `['restore']` was expected. The port that waited rebuilt the translator (CR-03 part a).
- Tracer gate (Task 1): the mode is interactive with end-of-phase verification, and the verify is automated only. `tests.test_lock` was run again on the committed tree, and all 10 tests passed before Task 2 started.

## Decisions Made
- I kept the plan's choice of key-named folders over holding the lock (see key-decisions).
- I used `buffering=0` rather than the review's `os.lseek`/`os.read` with an `except OSError` fallback. The plan specifies it, and the unchanged read line stays one code path on every OS.

## Deviations from Plan

None. The plan was executed as written.

## Issues Encountered
None

## User Setup Required

None, no configuration needed. Release notes should say:
- The first port after this update builds the shader translator once more, into the new key-named folder.
- `<user dir>/tools/dmsh_xlate/` and `<user dir>/tools/dmsh_xlate.key` are no longer used and can be deleted by hand.
- Each translator source change or .NET change from now on leaves one older folder of about 5 MB (T-02-35, accepted).

## Next Phase Readiness
- Gap 3 (CR-03) and human-verification item 1 (CR-02) are closed in code and in the POSIX tests.
- Still manual: push HEAD and check that the fork-ci.yml windows-2025 job runs `tests.test_lock` and `tests.test_datapack` green against a real Windows byte-range lock. The other four jobs must also run `tests.test_lock` green.
- HARD-04 can then be re-verified by `/gsd-verify-work`. The plan leaves the REQUIREMENTS.md marks to the verifier, so `requirements.mark-complete` was not run.

## Self-Check: PASSED
- FOUND: porter/pipeline.py, porter/lock.py, tests/test_lock.py, docs/ARCHITECTURE.md
- FOUND commits on HEAD: 5acfd1a, 193f6ea, 5b2f4f6, a5b5fd0, cad95dc, ac525a0 (`git rev-list --count dc9dffe..HEAD` = 6)
- All acceptance criteria re-run: PASS

---
*Phase: 02-porter-hardening*
*Completed: 2026-10-30*
