---
phase: 03-host-toolchains-and-guided-first-run
plan: 02
subsystem: porter
tags: [porter, toolchain, dotnet, adb, bare-path, linux-arm64]
status: complete

requires: []
provides:
  - "porter/hosttools.py: known(name), source_of(path, cfg, key, sdk_roots=()), dotnet_root(dotnet), linux_arm64(), adb_version(exe), push_flags(exe), ADB_Z_MAJOR=30, ADB_MIN_PROTOCOL=39"
  - "porter/childenv.py: dotnet(dotnet, jobs, base=None), the env every dotnet child gets"
  - "toolchain.find_adb / find_dotnet search the known places right after PATH"
affects: [03-03 Linux arm64 .NET download, 03-04 setup rows and source labels, 03-06 push -Z gate, 03-08 bundle smoke test, 03-09 Prepare .NET tools]

actuals:
  tokens: 5900
  tasks: 3
  commits: 6
plan_head_before: f0f2e8871b126f333edc126c79f2d1c356cf0dce
plan_head_after: 28155c1dcbdb284923683a1600e46ed3c449ca53

tech-stack:
  added: []
  patterns:
    - "Known places are a fixed per-OS list inserted after PATH in the finders, never saved to config.json"
    - "One env builder (childenv.dotnet) for every dotnet child; os.environ is never written"

key-files:
  created:
    - porter/hosttools.py
    - porter/childenv.py
    - tests/test_hosttools.py
  modified:
    - porter/toolchain.py
    - porter/pipeline.py
    - tests/test_toolchain.py

key-decisions:
  - "find_dotnet dedupes candidates by resolved path and keeps the earliest spelling, so Homebrew's /opt/homebrew/bin/dotnet link and /usr/local/share/dotnet/dotnet are asked once"
  - "source_of falls back to 'known place' for LOCAL_TOOLS and find_dotnet's other fixed folders (Program Files, ~/.dotnet on Windows)"
  - "adb_version's 'version' keeps the Debian epoch as printed (1:10.0.0+r36-7); only 'major' drops it"
  - "find_dotnet's existing ~/.dotnet and /usr/local/share/dotnet entries are kept (Windows needs ~/.dotnet; hook-only edit), the dedupe makes them harmless"

patterns-established:
  - "TDD RED with interface stubs committed beside the test; RED records in the phase's tdd/ folder"

duration: 15min
completed: 2026-10-31
---

# Phase 3 Plan 02: Host tool discovery, dotnet child env and adb version Summary

Porter now finds adb and dotnet by absolute path with a bare `PATH=/usr/bin:/bin` (Homebrew, /usr/local, ~/.dotnet, distro .NET folders), gives every dotnet child dotnet's real root plus invariant globalization and a UTF-8 LANG, and reads `adb version` as numbers for the `-Z` decision.

## What was built

- **Task 1 (tracer):** `hosttools.known(name)` lists the per-OS places a Finder or desktop-menu launch cannot see; `find_dotnet` and `find_adb` search them right after PATH (D-13 order: configured, PATH, known places, Android SDK, LOCAL_TOOLS, player_tools). Verified end to end: `env -i PATH=/usr/bin:/bin ... porter doctor --json` on the developer's Mac answers `/opt/homebrew/bin/dotnet` and `/opt/homebrew/bin/adb`.
- **Task 2:** `hosttools.dotnet_root()` takes the folder above `--list-sdks`' `[.../sdk]` (else the resolved executable's folder); `childenv.dotnet()` builds the env; `Port.run` uses it in place of its own block. On this Mac the root is now `/usr/local/share/dotnet`, where the old code would have given `/opt/homebrew/bin`.
- **Task 3:** `adb_version()` (`36.0.0-13206524` gives major 36, protocol 41 on the real Homebrew adb), `push_flags()`, `linux_arm64()`, `source_of()`.

## TDD Gate Compliance

| Task | RED commit | RED record | GREEN commit |
|------|-----------|-----------|--------------|
| 1 | 4c02e23 | tdd/03-02-t1-red.json (test_per_os, RED_EVIDENCE_OK) | 5b326ae |
| 2 | 3fbc99a | tdd/03-02-t2-red.json (test_root_from_list_sdks, RED_EVIDENCE_OK) | bf1bb3e |
| 3 | 97274a1 | tdd/03-02-t3-red.json (test_labels, RED_EVIDENCE_OK) | 28155c1 |

Semantic assessment: each target failed on its planned assertion against a stub (empty known list, the link's own folder as root, an empty source label), not on import. BarePath passed at RED as well, because the old finders already searched `~/.dotnet` and the SDK folder; it stays as the end-to-end tracer check.

## Commits

- 4c02e23 test(03-02): add failing test for the known places a bare PATH hides
- 5b326ae feat(03-02): find adb and dotnet in the known places a bare PATH hides
- 3fbc99a test(03-02): add failing test for the dotnet child env
- bf1bb3e feat(03-02): one env for every dotnet child with its real root and no libicu
- 97274a1 test(03-02): add failing test for adb versions, push flags and tool sources
- 28155c1 feat(03-02): read adb's version as numbers, push flags, Linux arm64 and tool sources

## Deviations from Plan

**1. [Rule 1 - Bug] Symlink-equal dotnet listed once**
- **Found during:** Task 1
- **Issue:** `dict.fromkeys(Path(...))` keeps `/opt/homebrew/bin/dotnet` and `/usr/local/share/dotnet/dotnet` as two entries (the plan's must-have says a symlink-equal path is listed once).
- **Fix:** find_dotnet keys its candidates by `Path.resolve()` and keeps the first spelling.
- **Files modified:** porter/toolchain.py
- **Commit:** 5b326ae

**2. test_listed_once filters to the test's own file**: the machine's real `/usr/local/share/dotnet/dotnet` is still in find_dotnet's fixed list, so the test asserts that its own file was asked exactly once instead of comparing the whole call list.

## Verification

- `QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover tests`: 279 tests OK (263 at base + 16 new)
- `.venv/bin/python tests/arch_rules.py`: all checks passed
- Acceptance greps: `hosttools.known(` x2 in toolchain.py; `childenv.dotnet(` x1 and `DOTNET_ROOT=dn` x0 in pipeline.py; no `zsh -l`/`bash -l`/`-lc ` in hosttools.py; constants print `30 39`

## Known Stubs

None.

## Self-Check: PASSED
