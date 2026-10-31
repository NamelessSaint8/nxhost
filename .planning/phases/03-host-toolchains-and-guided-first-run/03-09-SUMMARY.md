---
phase: 03-host-toolchains-and-guided-first-run
plan: 09
subsystem: porter
tags: [setup, toolchains, pins, dotnet, nuget, linux-arm64, adb]
status: complete

requires:
  - phase: 03-host-toolchains-and-guided-first-run (03-01)
    provides: "porter/setup.py report() and the setup --json document"
  - phase: 03-host-toolchains-and-guided-first-run (03-02)
    provides: "porter/childenv.py dotnet(dotnet, jobs)"
  - phase: 03-host-toolchains-and-guided-first-run (03-03)
    provides: "porter/pins.py rows and fetch._pinned(name) per host"
  - phase: 03-host-toolchains-and-guided-first-run (03-04)
    provides: "check rows with source, version and note; the adb -Z note"
  - phase: 03-host-toolchains-and-guided-first-run (03-06)
    provides: "porter/distro.py adb_install() and adb_hint()"
provides:
  - "setup --json tools items: `download` {version, size} for a missing tool this host can fetch; on Linux arm64 a missing adb's distro `fix` and `command`"
  - "setup --json `downloadable`: never adb on Linux arm64 (the community NDK is offered)"
  - "setup --json device step: the chosen adb's `version`, `source` and `note`"
  - "porter/prepare.py run() and STAGES; `porter tools --prepare` as a long command with its own log"
affects: [03-10, 03-11, phase-04 port preflight]

actuals:
  tokens: 7800
  tasks: 2
  commits: 4
plan_head_before: aa32ad808490b672c072c6c8b344fe23a8abd4ee
plan_head_after: 95daf68c4c66364f1ea6d9fdeb25c9cc22564633

tech-stack:
  added: []
  patterns:
    - "porter.fetch imported lazily inside a try (`import porter.fetch as fetch`) so setup answers without lz4; the test blocks it with sys.modules['porter.fetch'] = None"
    - "Prepare calls the pipeline's Port.translator unbound with a SimpleNamespace(tools, env, logs), so the translator folder and key are the port's own"

key-files:
  created:
    - porter/prepare.py
    - tests/test_prepare.py
    - .planning/phases/03-host-toolchains-and-guided-first-run/tdd/03-09-t1-red.json
    - .planning/phases/03-host-toolchains-and-guided-first-run/tdd/03-09-t2-red.json
  modified:
    - porter/setup.py
    - porter/cli.py
    - porter/runlog.py
    - tests/test_setup.py
    - docs/ARCHITECTURE.md

key-decisions:
  - "A tool's `download` is only added for a name in `downloadable`, so Linux arm64 adb never shows Google's x86-64 platform-tools size"
  - "On Linux arm64 a not-ok adb (missing or too old) gets fix = distro.adb_hint() and command = distro.adb_install(); the command is '' for an unknown distribution"
  - "Prepare's per-tool logs go to <user dir>/logs/prepare/; the run log stays <user dir>/logs/<time>-tools.log (retention globs *.log, so the folder is never pruned)"
  - "Prepare's .NET check is find_dotnet() plus an SDK >= DOTNET_MAJOR, the same rule as the .NET check row"

patterns-established:
  - "A long `tools` subcommand is marked in runlog.run by its flag (download or prepare)"

requirements-completed: [TOOL-02]

duration: 15min
completed: 2026-10-31
---

# Phase 3 Plan 09: Tools page data and Prepare .NET tools Summary

**`setup --json` now carries each tool's pinned download version and size, the Linux arm64 distro adb command and the chosen adb's version, source and `-Z` note. `porter tools --prepare` builds the shader translator through `Port.translator` and nx_extract once, under the port's NuGet pin check and dotnet env.**

## Performance

- **Duration:** about 15 min
- **Completed:** 2026-10-31
- **Tasks:** 2 (each RED then GREEN)
- **Files modified:** 7, plus 2 TDD evidence files

## Accomplishments

- Tools items: `download` {version, size} comes from `porter/pins.py` with no network (size 0 for .NET). `downloadable` matches `fetch.missing` (no adb on Linux arm64). A missing arm64 adb carries `command` for a Copy command button.
- Device step: `version`, `source` and `note` from the adb row, so a tester's report names the adb in use.
- `porter tools --prepare --progress json` runs as a long command: two stages (`shader translator`, `nx_extract`), its own log, the stop channel. Without .NET SDK 10 it raises a BuildError naming "Download missing tools".
- Checked for real on this Mac in a scratch NX2A_HOME: both stages passed in 9 s, and `tools/dmsh_xlate-943621355c41` was created.

## Task Commits

1. **Task 1 RED:** `c1ad8fd` (test): failing ToolFacts and Arm64 tests
2. **Task 1 GREEN:** `eab4b5a` (feat): tools items carry the download sizes, the arm64 adb command and the device's adb facts
3. **Task 2 RED:** `b24d0a9` (test): failing tests for `tools --prepare`
4. **Task 2 GREEN:** `95daf68` (feat): `porter/prepare.py`, the `--prepare` flag, runlog's long command, ARCHITECTURE.md

## TDD Gate Compliance

Each task was RED and then GREEN. The evidence is in `tdd/03-09-t1-red.json` and `tdd/03-09-t2-red.json`, replayed from scratch copies of the RED commits. Task 1's RED run had 2 FAIL and 3 ERROR, all caused by the missing feature. In Task 2, the CLI test failed with exit code 2 (an unknown flag), and the Prepare tests hit ImportError because the new `porter.prepare` module did not exist yet.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Test kept green] Report.test_tools_step compared items to the bare rows**
- **Found during:** Task 1
- **Issue:** the existing test expected `items == as_dict()` rows. The new additive `download` key would break it for the not-ok .NET row.
- **Fix:** the test now compares the items without `download`. ToolFacts pins the new key.
- **Files modified:** tests/test_setup.py
- **Commit:** c1ad8fd

**2. [Test approach] test_cli_long uses a configured stub dotnet instead of "no .NET"**
- **Issue:** the dev machine's Homebrew dotnet is found through known places even with a fresh NX2A_HOME.
- **Fix:** the test writes `config.json` with `dotnet` set to a plain file that lists no SDK. The configured path wins, so Prepare sees no SDK 10.
- **Commit:** b24d0a9

Everything else ran as written.

## Issues Encountered

None.

## Next Phase Readiness

- 03-10 and 03-11 can draw the tools page from `setup --json` alone and start Prepare with `tools --prepare --progress json`.
- FRUN-01, TOOL-01 and TOOL-03 are also listed in 03-10 and 03-11, so they stay open. Only TOOL-02 is marked complete.

## Self-Check: PASSED

- FOUND: porter/prepare.py, tests/test_prepare.py, tdd/03-09-t1-red.json, tdd/03-09-t2-red.json
- FOUND commits: c1ad8fd, eab4b5a, b24d0a9, 95daf68
- Full suite: 388 tests OK (`QT_QPA_PLATFORM=offscreen`); `tests/arch_rules.py`: all checks passed
