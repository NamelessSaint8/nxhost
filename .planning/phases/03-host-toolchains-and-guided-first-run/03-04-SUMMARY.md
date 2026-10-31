---
phase: 03-host-toolchains-and-guided-first-run
plan: 04
subsystem: infra
tags: [toolchains, ndk, compile-probe, linux-arm64, adb, distro, doctor-json]
status: complete

requires:
  - phase: 03-02
    provides: hosttools.linux_arm64(), source_of(), adb_version(), ADB_Z_MAJOR, ADB_MIN_PROTOCOL
  - phase: 03-03
    provides: the pinned community arm64 NDK r27c download under <user dir>/toolchains
provides:
  - porter/probe.py host_folder(ndk), clang(ndk), probe(ndk), note(ndk, version); probe.json cache
  - porter/distro.py ADB, family(osr=None), adb_install(osr=None), adb_hint()
  - Check.source / version / note on every row (filled for the Android NDK, .NET SDK and adb rows)
  - toolchain.require() result key 'notes', said in every port's log
  - nxnative/dm/android/build.py uses the NDK's own linux-arm64 / linux-aarch64 folder on Linux arm64, and the system glslc when the NDK has none
affects: [03-05 setup wizard tool rows, 03-06 udev and device fix (distro.py UDEV), 03-08 arm64 CI probe, gui setup tables]

actuals:
  tokens: 13600
  tasks: 3
  commits: 7
plan_head_before: 8c5d4a182a1ccc79eb1ed482276557da5b4a52b6
plan_head_after: 470ac174cfbbb30f64f49622aaebce4825b84f19

tech-stack:
  added: []
  patterns:
    - "A toolchain row is green only after the tool has run on this machine (compile probe), and only passes are cached, so a fixed tool turns green on the next check"
    - "build.py runs standalone, so its host-folder rule is a copy of probe.host_folder held equal by a source-text test (HostFolder.test_build_py_same_rule)"
    - "Fix text names distro commands from porter's own literals; os-release values are only dict keys and nothing is executed"

key-files:
  created:
    - porter/probe.py
    - porter/distro.py
    - tests/test_probe.py
    - tests/test_distro.py
    - .planning/phases/03-host-toolchains-and-guided-first-run/tdd/03-04-t1-red.json
    - .planning/phases/03-host-toolchains-and-guided-first-run/tdd/03-04-t2-red.json
    - .planning/phases/03-host-toolchains-and-guided-first-run/tdd/03-04-t3-red.json
  modified:
    - porter/toolchain.py
    - porter/pipeline.py
    - nxnative/dm/android/build.py
    - docs/ARCHITECTURE.md

key-decisions:
  - "probe() always returns a 'fix' key next to ok/detail/version, so the NDK row takes the probe's fix as is when the probe fails"
  - "A failing probe makes the NDK row required even for another NDK major: an NDK that cannot link cannot build the host"
  - "probe.json is keyed by clang's resolved path and holds mtime_ns and size; a touched or replaced clang is probed again, a corrupt file reads as empty"
  - "The adb -Z note and the community NDK note both reach the port log through require()['notes'] (every passing row's note)"
  - "TOOL-03 is left pending: its 'no permissions points to the udev package' half is plan 03-06's"

patterns-established:
  - "Host stand-ins for probe.host_folder patch probe.os / probe.sys and hosttools.sys / hosttools.platform, so hosttools.linux_arm64 is exercised rather than mocked"

requirements-completed: [TOOL-01]

duration: 8min
completed: 2026-10-31
---

# Phase 3 Plan 04: NDK compile probe, arm64 host folder and the adb row Summary

**Every NDK porter finds must compile and link an aarch64-linux-android29 program before its row turns green. On Linux arm64 the host build uses the NDK's own linux-arm64 folder, and the adb row shows its version, its -Z behaviour, where it came from and the distro install command.**

## Performance

- **Duration:** about 8 min
- **Started:** 2026-10-31T15:52:20Z
- **Completed:** 2026-10-31T16:00:30Z
- **Tasks:** 3 (one tracer)
- **Files modified:** 11 (7 created, 4 modified)

## Accomplishments

- `porter/probe.py`: runs `clang --version`, then links `int main(void) { return 0; }` with `--target=aarch64-linux-android29 -fuse-ld=lld` in a temp folder, using argv lists, no shell and a 60 s limit. Each failure gets its own detail and fix: Exec format error ("use an NDK built for this computer"), missing exec bit (`chmod +x`, plus `xattr -dr com.apple.quarantine <ndk>` on macOS), timeout, a link error (its last stderr line) and a missing clang. Only passes are cached in `<user dir>/probe.json`. On the developer's Mac, `doctor --json` takes 0.11 s with a cold cache and 0.05 s with a warm one, and the official r27c row stays green (`source: Android SDK`, `version: 27.2.12479018`).
- `Check` gains `source`, `version` and `note`, and `doctor --json` / `setup --json` get them as additive fields. The NDK row needs r27c and a passing probe. The .NET row shows its newest good SDK and where dotnet came from (`PATH`, `10.0.403` here).
- `porter/distro.py` maps the os-release ID, then each ID_LIKE word, to debian / fedora / arch. It produces `sudo apt install adb`, `sudo dnf install android-tools` or `sudo pacman -S android-tools`, and the generic list for an unknown distro. It never starts a process.
- The adb row shows its version and source. An adb before 30.0.0 is noted as pushing without `-Z`. One below protocol 1.0.39 is refused with "install a newer adb from your distribution" (adding ", or Download missing tools" off Linux arm64). With no adb on Linux arm64, the fix is the distro command.
- `build.py` gets a platform-guarded, 5-insertion / 1-deletion edit: the `linux-arm64` / `linux-aarch64` host folder on Linux aarch64/arm64, and the system glslc with a `[RED] ` line when the NDK lacks one. `require()` returns `notes`, and `Port.run` says each of them in the port log.

## Task Commits

1. **Task 1 (tracer): the NDK row proven by a compile probe**: `591513d` (test, RED), `03cb2f5` (feat, GREEN). Tracer gate: `<verify>` re-run end to end (unit tests plus `doctor --json`) passed, then expanded.
2. **Task 2: the adb row's version, -Z note, floor and distro command**: `68f03e6` (test, RED), `3d345a7` (feat, GREEN)
3. **Task 3: the arm64 host folder in build.py and the port log note**: `0e99b5b` (test, RED), `6442909` (feat, GREEN)

Docs: `470ac17` (docs/ARCHITECTURE.md: the probe, the arm64 host folder, the adb row, the new row fields)

## TDD Gate Compliance

- **RED (t1):** `tdd/03-04-t1-red.json`, `RED_EVIDENCE_OK`. Target `test_ok` failed on `assertTrue(ok)` against a stub `porter/probe.py`. Every Probe test failed on its planned assertion. `Rows.test_ndk_row` errored on the missing `Check.version`, which is the planned gap.
- **RED (t2):** `tdd/03-04-t2-red.json`, `RED_EVIDENCE_OK`. Target `test_adb_version_row` failed on the missing version (`'' != '36.0.0-13206524'`), and the Family and AdbCommand tests failed against a stub `porter/distro.py`. `test_runs_nothing` passed against the stub, which is the expected result for that test.
- **RED (t3):** `tdd/03-04-t3-red.json`, `RED_EVIDENCE_OK`. Target `test_build_py_same_rule` failed on each missing rule string, and `test_require_notes` errored with `KeyError: 'notes'`. `HostFolder.test_per_host` and `test_note` passed in RED because Task 1 had already built `host_folder` and `note`. In this task they pin the rule that build.py copies.
- **GREEN:** each feat commit passes its task's tests and the full suite (320 tests, `QT_QPA_PLATFORM=offscreen`), and `tests/arch_rules.py` reports "all checks passed".
- **REFACTOR:** none needed.

## Files Created/Modified

- `porter/probe.py`: the compile probe, its cache and the community note
- `porter/distro.py`: the distro family and adb install fix text
- `porter/toolchain.py`: Check fields; the NDK, .NET and adb rows; `require()['notes']`
- `porter/pipeline.py`: one hook line that says each note in the port log
- `nxnative/dm/android/build.py`: the arm64 host folder and the glslc fallback (platform-guarded)
- `tests/test_probe.py`: Probe, HostFolder, Rows (19 tests)
- `tests/test_distro.py`: Family, AdbCommand
- `docs/ARCHITECTURE.md`: the doctor checks paragraph

## Decisions Made

See `key-decisions` in the frontmatter. TOOL-03 is not marked complete: its udev half ("no permissions" points to the udev package) belongs to 03-06, which also lists TOOL-03.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing critical] docs/ARCHITECTURE.md updated**
- **Found during:** after Task 3
- **Issue:** CLAUDE.md requires `docs/ARCHITECTURE.md` to change when a layer, key or stage changes. Two new porter modules and three new `doctor --json` fields were otherwise undocumented.
- **Fix:** documented the probe, the arm64 host folder, the glslc fallback, the adb row rules and the new fields. This went in a separate `docs(03-04)` commit, because the task commits were already made and amending is not allowed.
- **Commit:** 470ac17

**2. [Rule 2 - Missing critical] extra probe tests**
- Added `Probe.test_corrupt_cache` (threat T-03-15: a corrupt cache is ignored), `Rows.test_fields` and `HostFolder.test_note`, which pins the D-09/D-10 prohibition that a community NDK is never shown as the tested build.

Otherwise the plan was executed as written.

## Issues Encountered

None.

## Known Stubs

None. The stubs committed in the RED commits were replaced in their GREEN commits.

## User Setup Required

None.

## Next Phase Readiness

- 03-05 (setup wizard) can show `source`, `version` and `note` on the tool rows.
- 03-06 adds `UDEV` and `device_fix` to `porter/distro.py`.
- 03-08 must run the probe against the community NDK on a real arm64 runner. This plan's tests use a stand-in subprocess (RESEARCH A7: the clang version string on arm64 has not been observed here).
- The real arm64 host build with build.py's new folder rule is Phase 6's parity check (VER-02).

## Self-Check: PASSED

- FOUND: porter/probe.py, porter/distro.py, tests/test_probe.py, tests/test_distro.py
- FOUND commits: 591513d, 03cb2f5, 68f03e6, 3d345a7, 0e99b5b, 6442909, 470ac17
- Measured commits: `git rev-list --count 8c5d4a1..HEAD` = 7
