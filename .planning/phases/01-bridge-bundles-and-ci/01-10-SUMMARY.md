---
phase: 01-bridge-bundles-and-ci
plan: 10
subsystem: infra
tags: [pyinstaller, pyside6, gtk3, gio, linux-bundle, release, notarization]

requires:
  - phase: 01-bridge-bundles-and-ci
    provides: porter/tls.py (plan 01-09, G-01-6) and the fork-release workflow with the signed and notarized macOS job (plan 01-08)
provides:
  - packaging/hooks/ overrides of PyInstaller's PySide6 QtGui and QtNetwork hooks, without platformthemes/libqgtk3.so and networkinformation/libqglib.so
  - a build-time [RED] refusal in packaging/nx2android.spec when libgio-2.0 or libgtk-3 is collected
  - a green fork-ci and fork-release run for 1ce9643 whose Linux tarballs carry no GTK3/GIO stack
affects: [01 UAT re-run (tests 6 and 7), PySide6 or PyInstaller upgrades]

actuals:
  tokens: 1078
  tasks: 3
  commits: 1
plan_head_before: 51f0fcbe78c686255cebd5b1c247b5a843dc701d
plan_head_after: 1ce9643c60f1fbf0e15815e75e2cd4db8e5baf49

tech-stack:
  added: []
  patterns:
    - "PyInstaller user hooks in packaging/hooks/ (hookspath, priority 1000) leave plugins out before binary dependency analysis, so the plugin's dependencies are never collected"
    - "The spec refuses known-bad libraries after Analysis with a [RED] line, on every host (the filter matches nothing off Linux)"

key-files:
  created: [packaging/hooks/hook-PySide6.QtGui.py, packaging/hooks/hook-PySide6.QtNetwork.py]
  modified: [packaging/nx2android.spec, docs/ARCHITECTURE.md]

key-decisions:
  - "G-01-7 fixed by what the bundle ships (fix direction A): the gtk3 platform theme and the glib network-information plugin are left out by hook overrides; no GIO_MODULE_DIR or QT_QPA_PLATFORMTHEME is set, so nothing leaks into the children the app starts"
  - "The Linux bundles now use Qt's built-in gnome theme and Qt's own file dialog on GTK-family desktops; only platformthemes/libqxdgdesktopportal.so remains"

patterns-established:
  - "Hook overrides are copies of the pinned PyInstaller 6.22.3 stock hooks less one file; copy the stock hook again on a PyInstaller upgrade"

requirements-completed: [PKG-02, PKG-03, PKG-04]

coverage:
  - id: D1
    description: "The Linux x64 and arm64 tarballs contain no libgio-2.0, libgtk-3, libqgtk3.so or libqglib.so"
    requirement: PKG-03
    verification:
      - kind: integration
        ref: "tar tzf on both fork-release 41017737613 tarballs | grep -cE 'libgio-2\\.0|libgtk-3|libqgtk3\\.so|libqglib\\.so' -> 0 and 0"
        status: pass
    human_judgment: false
  - id: D2
    description: "The macOS build uses both hook overrides from packaging/hooks and the DMG passes the frozen smoke test"
    requirement: PKG-02
    verification:
      - kind: integration
        ref: "packaging/build_bundle.py log (both hooks processed from packaging/hooks); packaging/smoke_bundle.py on the local DMG"
        status: pass
    human_judgment: false
  - id: D3
    description: "fork-ci green on all four OSes and fork-release dispatch green for HEAD; the release DMG is notarized and stapled"
    requirement: PKG-02
    verification:
      - kind: integration
        ref: "fork-ci 41017724428 success; fork-release 41017737613 success; xcrun stapler validate OK; spctl: accepted, source=Notarized Developer ID"
        status: pass
    human_judgment: false
  - id: D4
    description: "G-01-6 frozen-bundle checks: the notarized DMG and the Linux bundles on Fedora 44 load the download lists and download platform-tools"
    requirement: PKG-02
    verification: []
    human_judgment: true
    rationale: "Needs the DMG mounted on a Mac, Docker runs on Fedora 44 and a browser download from Finder (UAT test 6); commands in 01-10-PLAN.md Task 3 <human-check>"
  - id: D5
    description: "G-01-7 checks: on Debian trixie with XDG_CURRENT_DESKTOP=GNOME the new bundles print no gvfs 'undefined symbol' line and the folder picker opens; UAT test 7 on the Debian-family x64 GNOME host"
    requirement: PKG-04
    verification: []
    human_judgment: true
    rationale: "Old-against-new container runs and a real GNOME session; commands in 01-10-PLAN.md Task 3 <human-check>"

duration: 77min
completed: 2026-10-30
status: complete
---

# Phase 01 Plan 10: Linux bundles without the GTK3/GIO stack, proven on the release artifacts Summary

**Two PyInstaller hook overrides keep PySide6's gtk3 theme and glib network plugin (and the 26 GTK/GIO libraries they pull in) out of the Linux bundles, the spec refuses libgio-2.0 and libgtk-3 with a [RED] line, and fork-release 41017737613 built all four bundles green with both gap fixes (G-01-6, G-01-7) in them**

## Performance

- **Duration:** about 77 min, from the plan's base commit to the end of the run (includes the push checkpoint wait and a 30-minute release run)
- **Started:** 2026-10-30T06:24:18Z
- **Completed:** 2026-10-30T07:41:17Z
- **Tasks:** 3 (one code task, one human-action checkpoint, one CI proof task)
- **Files modified:** 4

## Accomplishments

- `packaging/hooks/hook-PySide6.QtGui.py` and `hook-PySide6.QtNetwork.py` replace the stock hooks (the build log shows both processed from `packaging/hooks`), leaving out `platformthemes/libqgtk3.so` and `networkinformation/libqglib.so`.
- `packaging/nx2android.spec` passes `hookspath` and stops the build with a `[RED]` line if a `libgio-2.0.` or `libgtk-3.` binary is collected again.
- After the push of main (d2ec054..1ce9643), fork-ci and the fork-release dispatch for 1ce9643 were green on the first attempt. No fix round was needed.

## Release evidence (Task 3)

| Item | Value |
|------|-------|
| fork-ci run | 41017724428: success. Jobs: ubuntu-22.04 3.14, ubuntu-22.04 3.11, ubuntu-24.04-arm 3.14, windows-2025 3.14, macos-15 3.14 |
| fork-release run (workflow_dispatch, 1ce9643) | 41017737613: success. Jobs: build linux-x64, linux-arm64, windows-x64; build macos-arm64 (signed and notarized); upstream-diff; release skipped (not a tag) |
| Artifacts | nx2android-1ce9643-linux-x64.tar.gz, nx2android-1ce9643-linux-arm64.tar.gz, nx2android-1ce9643-macos-arm64.dmg, nx2android-1ce9643-windows-x64.zip (in build/release-check/new/<name>/<name>) |
| linux-x64 tarball | 2532 entries, 0 matching libgio-2.0, libgtk-3, libqgtk3.so or libqglib.so; platformthemes holds only libqxdgdesktopportal.so |
| linux-arm64 tarball | 2529 entries, 0 matches; platformthemes holds only libqxdgdesktopportal.so |
| glibc floor, x64 | `glibc floor 2.35: _internal/libgcc_s.so.1, _internal/libpython3.14.so.1.0, _internal/libtcl8.6.so, _internal/libtk8.6.so, _internal/python3.14/lib-dynload/cmath.cpython-314-x86_64-linux-gnu.so` |
| glibc floor, arm64 | `glibc floor 2.38: _internal/PySide6/Qt/lib/libQt6EglFsKmsSupport.so.6, _internal/PySide6/Qt/lib/libQt6Gui.so.6, _internal/PySide6/Qt/lib/libQt6Network.so.6, _internal/PySide6/Qt/lib/libicui18n.so.73, _internal/PySide6/Qt/lib/libicuuc.so.73` |
| macOS DMG | `xcrun stapler validate`: "The validate action worked!"; `spctl -a -t open --context context:primary-signature`: accepted, source=Notarized Developer ID |

The spec's `[RED]` refusal ran on both Linux runners and matched nothing, which is consistent with the 0-match listings.

## Task Commits

1. **Task 1: hook overrides and the build-time GTK3/GIO refusal** - `1ce9643` (fix)
2. **Task 2: authorize the push** - checkpoint, no commit (the developer typed "push")
3. **Task 3: release run for HEAD** - no commit. The run was green on the first attempt, so no fix round was needed.

## Files Created/Modified

- `packaging/hooks/hook-PySide6.QtGui.py` - the stock QtGui hook without libqgtk3.so
- `packaging/hooks/hook-PySide6.QtNetwork.py` - the stock QtNetwork hook without libqglib.so
- `packaging/nx2android.spec` - hookspath and the [RED] check after Analysis
- `docs/ARCHITECTURE.md` - `hooks/` added to the packaging/ layout line

## Decisions Made

- Fix direction A from `.planning/debug/linux-bundle-gio-module-mismatch.md`: change what ships, set no environment variable.
- Task 1 commit verified to touch only the four task files, so gui/, porter/ and the launcher are unchanged (T-1-33).

## Deviations from Plan

None. The plan ran as written. Two notes:
- fork-release was dispatched while fork-ci was still running, not after it finished. Both ran on the same commit, so the result is the same.
- The first `gh run download` of all artifacts timed out on the local network (linux-x64). The fix was to download per artifact with `-n <name>`, which puts each file in its own subfolder. The plan's `find` commands still work.

## Human checks pending (for /gsd-verify-work)

The exact commands are in `01-10-PLAN.md` Task 3 `<human-check>`. Setup: `R=41017737613`; the new artifacts are already in `build/release-check/new`. The old positive-control build is run 40971470754 (kept until about 2026-11-05).
1. G-01-6, notarized DMG: (a) `tools --only ndk,dotnet,adb --json` prints three items, (b) the platform-tools download unpacks adb, (c) `fpslocker.fetch` prints `fpslocker None`, (d) `codesign --verify --deep --strict` passes, then UAT test 6 by hand from Finder.
2. G-01-6, Linux bundles on fedora:44 (arm64 and amd64): `tools --only ndk,dotnet,adb --json` prints three items with exit 0.
3. G-01-7, debian:trixie with XDG_CURRENT_DESKTOP=GNOME, old against new: the old rows print the gvfs lines and the new rows print "start: no GIO module errors" and "picker closed: ''".
4. G-01-7, UAT test 7 on the Debian-family x64 GNOME host.

## Issues Encountered

None besides the artifact download timeout above.

## Next Phase Readiness

Both gap fixes are in release-built, notarized (macOS) bundles. Phase 01 can go to /gsd-verify-work for the UAT re-run of tests 6 and 7.

## Self-Check: PASSED

- FOUND: packaging/hooks/hook-PySide6.QtGui.py, packaging/hooks/hook-PySide6.QtNetwork.py
- FOUND: 1ce9643 is an ancestor of HEAD and equals origin/main
