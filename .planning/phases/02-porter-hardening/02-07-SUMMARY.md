---
phase: 02-porter-hardening
plan: 07
subsystem: testing
tags: [unittest, adb, toolchain, cli, mock, subprocess]

requires:
  - phase: 02-01
    provides: build-folder lock and chunked MD5 in porter/adb.py; cmd_install's sidecar lock
  - phase: 02-04
    provides: pins and the Python floor in porter/toolchain.py; tests/test_toolchain.py PythonFloor
provides:
  - "porter tools --only <unknown> answers a named error with exit 2"
  - "tests/test_cli.py: ErrorPaths (six CLI error paths as subprocesses), DeviceTool"
  - "tests/test_adb.py: fake(table, calls) subprocess.run stand-in; Sizes, Push, Install"
  - "tests/test_toolchain.py: Detection (finder order, per-OS SDK roots and user_dir)"
affects: [ci, porter, devtools, phase-02-verification]

actuals:
  tokens: 4356
  tasks: 3
  commits: 5
plan_head_before: 4b9f6203c23ef50af2be027b72dcdeb1626de97d
plan_head_after: 3041fe4f99902a64456c725d315c6dbf5d5b4397

tech-stack:
  added: []
  patterns:
    - "adb tests patch subprocess.run through mock.patch.object(adb.subprocess, 'run', fake(table, calls)): first table key found in the joined argv answers"
    - "per-OS tests swap the module's os and sys for SimpleNamespace stand-ins (name, environ, path / platform), so pathlib keeps building the host's own paths"

key-files:
  created:
    - tests/test_cli.py
    - tests/test_adb.py
  modified:
    - porter/cli.py
    - tests/test_toolchain.py

key-decisions:
  - "An unknown --only tool is a usage error: exit 2, {\"error\"} on stdout with --json, stderr otherwise"
  - "Per-OS detection tests replace toolchain.os / paths.os with a stand-in instead of patching os.name, which would make pathlib build WindowsPath on a POSIX host"

patterns-established:
  - "fake(table, calls): a table-driven subprocess.run stand-in for adb, portable to Windows"
  - "Detection setUp points LOCAL_TOOLS, player_tools, HOME, USERPROFILE, LOCALAPPDATA and the Android/.NET variables at temp folders so a developer's real toolchains never leak in"

requirements-completed: [TEST-01]

coverage:
  - id: D1
    description: "porter tools --only of an unknown tool stops with a named error (exit 2) instead of a KeyError traceback"
    requirement: TEST-01
    verification:
      - kind: integration
        ref: "tests/test_cli.py#ErrorPaths.test_tools_unknown"
        status: pass
    human_judgment: false
  - id: D2
    description: "CLI error paths answer named errors: inspect empty / NSZ-only, port without prod.keys, install of a non-pack, config of an unknown key"
    requirement: TEST-01
    verification:
      - kind: integration
        ref: "tests/test_cli.py#ErrorPaths"
        status: pass
    human_judgment: false
  - id: D3
    description: "devtools/device.py takes serial and package from NX2A_DEVICE / NX2A_PACKAGE first"
    verification:
      - kind: integration
        ref: "tests/test_cli.py#DeviceTool.test_env_wins"
        status: pass
    human_judgment: false
  - id: D4
    description: "adb and install covered without a device: remote_sizes, push_file resume and size check, push_tree skips and MD5, stale removal in batches of 64 within mods/RomFS/aoc, --replace-signer"
    requirement: TEST-01
    verification:
      - kind: unit
        ref: "tests/test_adb.py (Sizes, Push, Install; 6 tests)"
        status: pass
    human_judgment: false
  - id: D5
    description: "Toolchain detection per OS: find_ndk, find_dotnet, find_adb order, _sdk_roots and paths.user_dir for Windows, macOS, Linux"
    requirement: TEST-01
    verification:
      - kind: unit
        ref: "tests/test_toolchain.py#Detection (6 tests)"
        status: pass
    human_judgment: false
  - id: D6
    description: "Detection runs green on all four CI hosts (windows-2025, macos-15, ubuntu-22.04, ubuntu-24.04-arm)"
    verification: []
    human_judgment: true
    rationale: "Run here on macOS only; the plan's human-check is fork-ci.yml green on every host after the phase is pushed"

duration: 5min
completed: 2026-10-30
status: complete
---

# Phase 2 Plan 07: CLI, adb and toolchain test coverage Summary

**`porter tools --only bogus` now answers a named error with exit 2, and 19 new tests pin porter's CLI error paths, adb pushes and device install over a table-driven fake subprocess.run, and per-OS toolchain detection**

## Performance

- **Duration:** about 5 min of commits (reading and planning before that)
- **Started:** 2026-10-30T18:18:36Z
- **Completed:** 2026-10-30T18:23:20Z
- **Tasks:** 3
- **Files modified:** 4

## Accomplishments
- `cmd_tools` checks `--only` names against ndk, dotnet, adb and answers `unknown tool <names>: --only takes ndk, dotnet, adb` (JSON with `--json`, stderr otherwise), exit 2. Before this, it crashed with a KeyError traceback and exit 1. The diff is 5 lines added and 1 removed.
- tests/test_cli.py runs porter as a subprocess with its own NX2A_HOME for six error paths, plus the devtools device resolver.
- tests/test_adb.py pins resume, size parsing, the push_tree skip and MD5 rules, stale-file removal (batches 64/64/2, never settings.txt or logs/) and replace-signer. No device is needed.
- tests/test_toolchain.py Detection pins the finder order and the per-OS folders, with the machine's own toolchains kept out of reach.

## Task Commits

1. **Task 1: CLI error paths, unknown --only tool** - `bd99cbc` (test, RED), `3bb77ab` (fix, GREEN), `3041fe4` (test: the process's own NX2A_HOME)
2. **Task 2: adb and install without a device** - `c9d8390` (test)
3. **Task 3: toolchain detection per OS** - `9e62d0c` (test)

## Files Created/Modified
- `porter/cli.py` - the named error for an unknown `--only` tool in `cmd_tools`
- `tests/test_cli.py` - ErrorPaths (7 cases including tools) and DeviceTool, run as subprocesses
- `tests/test_adb.py` - `fake(table, calls)`, Sizes, Push, Install
- `tests/test_toolchain.py` - Detection beside PythonFloor; helpers `ndk`, `exe`, `host`

## TDD Gate Compliance
- RED: `test_tools_unknown` failed on its exit-code assertion (1 != 2, KeyError traceback). `gsd-tools check tdd-red-evidence` returned RED_EVIDENCE_OK (unittest format, 7 run, 1 failing, target matched). My check: the target ran and failed for the planned reason, and the other six pin behaviour that already works.
- GREEN: commit `3bb77ab` is typed `fix(02-07)`, not `feat`, because it fixes a crash. This plan is `type: execute`, so the gate is advisory.
- Tasks 2 and 3 pin behaviour that already works, so their tests passed on first run and there is no RED step. As a mutation check, I widened `datapack.OWNED` to include `logs`, and test_stale_removed_in_batches failed as it should.

## Decisions Made
- An unknown tool counts as a usage error (exit 2), the same code as cmd_inspect's named errors.
- The per-OS tests replace `toolchain.os`/`toolchain.sys` and `paths.os`/`paths.sys` with SimpleNamespace stand-ins. Patching `os.name` globally would make `Path()` build WindowsPath on POSIX hosts.

## Deviations from Plan

None in production code. In tests, one small addition: tests/test_cli.py also sets NX2A_HOME in its own process at import. Porter runs only in its subprocesses, but the must-have says every new module does this (`3041fe4`).

**Total deviations:** 0 auto-fixed. **Impact:** none.

## Issues Encountered
None. No test turned up a bug in porter/adb.py or porter/install.py.

## Verification
- `.venv/bin/python -m unittest tests.test_cli tests.test_adb tests.test_toolchain`: 24 tests OK
- `QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover tests`: 195 tests OK (176 before this plan)
- `.venv/bin/python tests/arch_rules.py`: all checks passed
- Acceptance: `grep -c "unknown tool" porter/cli.py` = 1. `porter tools --only bogus --json` exits 2 with `{"error"}`. numstat 5/1. There are 6 `patch.object(adb.subprocess, 'run'` uses, and `class Detection` appears once.

## User Setup Required
None.

## Next Phase Readiness
- CI should run tests.test_toolchain, tests.test_adb and tests.test_cli on all four hosts once the phase is pushed (D6, human check).

---
*Phase: 02-porter-hardening*
*Completed: 2026-10-30*

## Self-Check: PASSED
