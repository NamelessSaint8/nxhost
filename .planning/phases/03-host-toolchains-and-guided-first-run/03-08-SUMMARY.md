---
phase: 03-host-toolchains-and-guided-first-run
plan: 08
subsystem: packaging
tags: [packaging, ci, release, smoke-test, ndk, docs]
status: complete

requires:
  - phase: 03-01
    provides: "setup --json: steps[id=tools].items check rows"
  - phase: 03-02
    provides: "hosttools known places (~/.dotnet, <sdk>/platform-tools, <sdk>/ndk/*) searched without PATH"
  - phase: 03-03
    provides: "pins.NDK['files']['linux-arm64'] (community r27c, sha256) and tools --download --only ndk"
  - phase: 03-04
    provides: "the compile probe and the community note on the NDK row"
provides:
  - "packaging/smoke_bundle.py: bare_env_check(exe, tmp, extra_env=None, home_nx=None), community_ndk(exe, env), the --community-ndk flag"
  - ".github/workflows/fork-release.yml: build step 'Community NDK download and probe (linux-arm64)'"
  - "devtools/ndk_pin.py: RELEASE, ASSET, compare(release, row), main()"
  - "docs/RELEASE_CHECK.md: Phase 3 host-check rows (TOOL-04, TOOL-01, DEV-01, TOOL-03, ndk_pin.py)"
  - "packaging/INSTALL.md: the first-run wizard, Linux distro adb and udev, the community arm64 NDK and the D-10 fallback recipe"
affects: [03-10 (TOOL-04 GUI half), 03-09 and 03-11 (TOOL-01), Phase 6 release]

actuals:
  tokens: 6150
  tasks: 3
  commits: 5
plan_head_before: adcbd24ca9f6638c20fb71e78d44b67fb7203d15
plan_head_after: b9b0207abd428346bb26939a47c2de17c94b1653

tech-stack:
  added: []
  patterns:
    - "A smoke check that runs both frozen (release workflow) and unfrozen (sys.executable + PYTHONPATH in the suite), so fork-ci catches the regression on every push"
    - "A pin watcher that reads GitHub's per-asset digest instead of downloading the asset"

key-files:
  created:
    - devtools/ndk_pin.py
  modified:
    - packaging/smoke_bundle.py
    - .github/workflows/fork-release.yml
    - tests/test_packaging.py
    - tests/test_workflows.py
    - docs/RELEASE_CHECK.md
    - packaging/INSTALL.md

key-decisions:
  - "BareEnv.test_missing_tool_fails stands in a not-found .NET row by wrapping porter(); removing the stand-in alone cannot work where the host has dotnet in a known place (/opt/homebrew/bin here, /usr/share/dotnet on GitHub runners)"
  - "--community-ndk runs the download without capturing output, so the CI log shows the progress lines and any [RED] cause; then it returns before the other smoke checks (they ran in the step before)"
  - "The D-10 fallback recipe uses a wrapper script for bin/clang (-resource-dir and --sysroot from the NDK folder) in a linux-arm64 host folder, not a plain link: a linked distro clang resolves its own runtime, which has no Android builtins"
  - "TOOL-04 and TOOL-01 are not marked complete: 03-10 lists TOOL-04 and 03-09/03-11 list TOOL-01"

requirements-completed: []

metrics:
  duration: 25min
  completed: 2026-10-31
---

# Phase 3 Plan 08: Bare-PATH and community NDK proofs in CI Summary

**The release smoke test now fails unless the frozen app finds the NDK, .NET and adb with only `PATH=/usr/bin:/bin`. The same check runs unfrozen in the suite. The linux-arm64 release job downloads the pinned community NDK and requires its probe to pass. `devtools/ndk_pin.py` compares the GitHub asset's digest with the pin.**

## Performance

- Duration: about 25 min
- Started: 2026-10-31T16:08Z
- Completed: 2026-10-31T16:33Z
- Tasks: 3
- Files: 7 (1 created, 6 modified)

## Accomplishments

- `bare_env_check` builds stand-ins in a fresh HOME (`~/.dotnet/dotnet`, `<sdk>/platform-tools/adb`, `<sdk>/ndk/27.2.12479018/source.properties`). It runs `doctor --json` and `setup --json` with only `PATH`, `HOME` and `NX2A_HOME` (plus `PYTHONPATH` in the suite), and fails naming each tool row that has no path. `main()` runs it on every POSIX bundle and reuses its own NX2A_HOME. Windows prints a SKIP line.
- `smoke_bundle.py --community-ndk dist/nx2android`: the frozen bundle runs `tools --download --only ndk --progress lines` (30 min limit). Then `setup --json`'s Android NDK row must be ok and its note must contain "community". The new fork-release step runs this only when `matrix.target == 'linux-arm64'`, with no expressions in the script.
- `devtools/ndk_pin.py`: compared with the live GitHub API on 2026-10-31, the result was `PASS android-ndk-r27c-aarch64-linux-gnu.tar.xz matches porter/pins.py`.
- RELEASE_CHECK.md has eight new "not run" host rows. INSTALL.md replaces the old Setup-tab section with the wizard and adds a Linux adb/NDK subsection.

## Task Commits

1. Task 1, bare-PATH check (tracer, TDD): `63cf0e0` (test, RED), `e9c4fb8` (feat, GREEN). Tracer gate: the verify was re-run end to end and passed before expanding.
2. Task 2, community NDK step and pin watcher (TDD): `5468248` (test, RED), `93f275f` (feat, GREEN)
3. Task 3, manual rows and install text: `b9b0207` (docs)

## Decisions Made

See key-decisions in the frontmatter.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] The fallback NDK recipe as first worded would not compile**
- **Found during:** Task 3
- **Issue:** linking a distro clang into an NDK's `bin/` makes clang resolve its resource dir and sysroot from the distro install, so the Android sysroot and the `libclang_rt.builtins-aarch64-android` runtime are not found. A folder named `linux-x86_64` would also make `build.py` look for `shader-tools/linux-x86_64/glslc`, an x86_64 program.
- **Fix:** the recipe copies the host folder to `linux-arm64` (porter's probe and `build.py` prefer it on arm64). `bin/clang` becomes a wrapper that passes `-resource-dir` and `--sysroot` from the NDK folder, `llvm-strip` is linked, and the distro `glslc` is installed (`build.py` falls back to it).
- **Files modified:** packaging/INSTALL.md
- **Commit:** b9b0207

**2. [Test design] test_missing_tool_fails replaces the tool's row instead of removing the stand-in**
- **Found during:** Task 1
- **Issue:** the plan's "with the .NET stand-in removed" cannot fail on a host whose own dotnet sits in a known place.
- **Fix:** the test wraps `smoke_bundle.porter` and blanks the `.NET SDK` row's path in both answers. It asserts two failures that name `.NET SDK`.
- **Commit:** 63cf0e0

## Manual / UAT checks (not run here)

- A real `fork-release.yml` run (all three build targets plus the macOS job) proves the frozen bare-PATH check and the arm64 community download and probe. I did not push or run any CI. Record the run in docs/RELEASE_CHECK.md (the Linux arm64 community NDK row).
- The D-10 fallback recipe has not been tried on an arm64 machine.
- The new RELEASE_CHECK rows are all "not run": Finder and app-menu ports, `unauthorized`→`device`, `no permissions`, distro adb 29.0.6, and ndk_pin.py before a release.

## Known Stubs

None.

## Verification

- `.venv/bin/python -m unittest tests.test_packaging tests.test_workflows -v`: 29 tests OK
- `QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover tests`: 370 tests OK (363 at base + 7 new)
- `.venv/bin/python tests/arch_rules.py`: all checks passed
- Acceptance greps: `def bare_env_check` 1, `/usr/bin:/bin` 3, `smoke_bundle.py --community-ndk` in the workflow 1, `def compare` 1, `TOOL-04` 3, `ndk_pin.py` 1, `DEV-01` 2, `HomuHomu833` 1, `Add to app menu` 1
