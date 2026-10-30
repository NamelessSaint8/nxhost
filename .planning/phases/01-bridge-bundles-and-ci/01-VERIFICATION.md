---
phase: 01-bridge-bundles-and-ci
verified: 2026-10-30T08:20:00Z
status: passed
score: 4/5 roadmap success criteria verified (SC1 waits on post-fix Linux host checks); plan must-haves 68/70 verified (1 by override), 2 wait on host checks
covered_files: [".github/workflows/fork-ci.yml", ".github/workflows/fork-release.yml", ".planning/phases/01-bridge-bundles-and-ci/01-01-PLAN.md", ".planning/phases/01-bridge-bundles-and-ci/01-01-SUMMARY.md", ".planning/phases/01-bridge-bundles-and-ci/01-02-PLAN.md", ".planning/phases/01-bridge-bundles-and-ci/01-02-SUMMARY.md", ".planning/phases/01-bridge-bundles-and-ci/01-03-PLAN.md", ".planning/phases/01-bridge-bundles-and-ci/01-03-SUMMARY.md", ".planning/phases/01-bridge-bundles-and-ci/01-04-PLAN.md", ".planning/phases/01-bridge-bundles-and-ci/01-04-SUMMARY.md", ".planning/phases/01-bridge-bundles-and-ci/01-05-PLAN.md", ".planning/phases/01-bridge-bundles-and-ci/01-05-SUMMARY.md", ".planning/phases/01-bridge-bundles-and-ci/01-06-PLAN.md", ".planning/phases/01-bridge-bundles-and-ci/01-06-SUMMARY.md", ".planning/phases/01-bridge-bundles-and-ci/01-07-PLAN.md", ".planning/phases/01-bridge-bundles-and-ci/01-07-SUMMARY.md", ".planning/phases/01-bridge-bundles-and-ci/01-08-PLAN.md", ".planning/phases/01-bridge-bundles-and-ci/01-08-SUMMARY.md", ".planning/phases/01-bridge-bundles-and-ci/01-09-PLAN.md", ".planning/phases/01-bridge-bundles-and-ci/01-09-SUMMARY.md", ".planning/phases/01-bridge-bundles-and-ci/01-10-PLAN.md", ".planning/phases/01-bridge-bundles-and-ci/01-10-SUMMARY.md", "docs/ARCHITECTURE.md", "docs/RELEASE_CHECK.md", "gui/__init__.py", "gui/__main__.py", "gui/app.py", "gui/runner.py", "packaging/INSTALL.md", "packaging/build_bundle.py", "packaging/glibc_floor.py", "packaging/hooks/hook-PySide6.QtGui.py", "packaging/hooks/hook-PySide6.QtNetwork.py", "packaging/nx2android.py", "packaging/nx2android.spec", "packaging/smoke_bundle.py", "packaging/smoke_gui.py", "porter/cli.py", "porter/fetch.py", "porter/fpslocker.py", "porter/paths.py", "porter/pipeline.py", "porter/procs.py", "porter/runlog.py", "porter/tls.py", "requirements-build.in", "requirements-build.txt", "requirements-dev.in", "requirements-dev.txt", "requirements.in", "requirements.txt", "tests/fixtures/bridge/fake_porter.py", "tests/fixtures/bridge/record.py", "tests/fixtures/tls/test-ca.pem", "tests/test_bridge.py", "tests/test_packaging.py", "tests/test_paths.py", "tests/test_porter.py", "tests/test_porter_guard.py", "tests/test_runlog.py", "tests/test_tls.py", "tests/test_workflows.py"]
covered_digest: "v4:sha256:3fb7c7f935ad4fac8a76cff8fb802a2f356fb8776491e040839f716ea95da8f1"
behavior_unverified: 0
overrides_applied: 1
overrides:
  - must_have: "Each Linux build job reports the bundle's GLIBC_ symbol floor in the step summary and fails above 2.34 (x64) or 2.39 (arm64)"
    reason: "The ubuntu-22.04 runner's own libpython3.14, libgcc_s, cairo, tcl and tk need GLIBC_2.35. The developer chose to raise the x64 gate to 2.35 (option B at the 01-08 Task 3 checkpoint) over a container build or trimming those libraries. PKG-03 in REQUIREMENTS.md now says glibc 2.35+, and fork-release.yml, glibc_floor.py, INSTALL.md and the Release test say the same. The arm64 gate stays 2.39 (measured 2.38)."
    accepted_by: "NamelessSaint8 (developer, 01-08 Task 3 checkpoint)"
    accepted_at: "2026-10-29T19:23:05Z"
re_verification:
  previous_status: human_needed
  previous_score: 3/5
  gaps_closed:
    - "G-01-6: Download missing tools loads the download lists and fetches the missing tools from the signed macOS app (code fixed in porter/tls.py; proven here from the read-only mounted 1ce9643 DMG: its default store holds 0 CAs, yet the three lists load and the FPSLocker fetch gets a verified 404)"
    - "G-01-7: the Linux bundles stop shipping the runner's GTK3/GLib/GIO stack (both 1ce9643 tarballs list 0 libgio-2.0, libgobject, libgtk-3, libgdk-3, libqgtk3.so or libqglib.so entries; the spec refuses libgio-2.0 and libgtk-3)"
    - "SC2 / BRDG-01: real cancel mid-port on each host passed in UAT test 5"
  gaps_remaining: []
  regressions: []
human_verification:
  - test: "UAT test 6 again: download the 1ce9643 DMG (fork-release run 41017737613) in a browser, open it from Finder, start the app, and press Download missing tools on the Setup tab on a Mac that lacks a tool"
    expected: "The download lists load and the missing tool downloads into the nx2android folder, with no CERTIFICATE_VERIFY_FAILED"
    why_human: "The verifier ran the frozen porter CLI from the mounted DMG (lists load, fpslocker gets a 404), which is the code the button runs. The button press in a Finder-started, quarantined app is a GUI interaction"
  - test: "G-01-6 on Linux: in fedora:44 containers (linux/amd64 and linux/arm64), unpack the 1ce9643 linux-x64 and linux-arm64 tarballs and run NX2A_HOME=/tmp/h ./nx2android -m porter tools --only ndk,dotnet,adb --json (exact command in 01-10-PLAN.md Task 3 <human-check>)"
    expected: "Three items and exit 0 on both (the d2ec054 arm64 bundle loaded 0 CAs on Fedora 44 and failed)"
    why_human: "Needs Docker and a non-Debian host layout. The fallback order including /etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem is unit-tested, but the frozen Linux bundle was not run on Fedora"
  - test: "G-01-7 old against new: in debian:trixie containers with XDG_CURRENT_DESKTOP=GNOME and QT_QPA_PLATFORM=xcb under xvfb, start the d2ec054 and 1ce9643 tarballs and the folder-picker probe (exact command in 01-10-PLAN.md Task 3 <human-check>; the d2ec054 artifacts expire about 2026-11-05)"
    expected: "The d2ec054 rows print the gvfs 'undefined symbol' lines (proving the container loads the gtk3 theme); the 1ce9643 rows print 'start: no GIO module errors' and \"picker closed: ''\""
    why_human: "The tarballs no longer hold libgio or the gtk3 theme, which removes the cause, but the clean start and a working folder picker on a GTK-family desktop are runtime behaviour on a host"
  - test: "UAT test 7 again: on the Debian-family x64 GNOME host where the gvfs lines first appeared, unpack the 1ce9643 linux-x64 tarball and run QT_QPA_PLATFORM=xcb ./nx2android from a terminal in the GNOME session, then use the Port tab's folder button"
    expected: "No 'undefined symbol' or 'Failed to load module' line; the folder picker (now Qt's own dialog) opens and fills in the chosen folder"
    why_human: "Real GNOME session; the folder dialog changed from GTK's to Qt's with this fix"
  - test: "PKG-04 / SC1: on a Linux arm64 host (glibc 2.39+), unpack the 1ce9643 linux-arm64 tarball and start ./nx2android with QT_QPA_PLATFORM=xcb and with QT_QPA_PLATFORM=wayland"
    expected: "The window appears under both with no Fontconfig, platform-plugin or GIO module errors"
    why_human: "UAT test 3 passed on Linux x64 only; its note says the arm64 tarball was not shown. The Linux bundles were also rebuilt without the GTK stack since then"
---

# Phase 1: Bridge, Bundles and CI Verification Report

**Phase Goal:** Today's GUI controls runs reliably and reaches testers as a CI-built bundle on Windows x64, macOS Apple Silicon, Linux x64 and Linux arm64
**Verified:** 2026-10-30T08:20:00Z
**Status:** human_needed
**Re-verification:** Yes, after gap closure (plans 01-09 for G-01-6 and 01-10 for G-01-7)

## Goal Achievement

Both UAT gaps are closed in code, and both fixes are in release-built bundles: fork-ci 41017724428 and fork-release 41017737613 are green for 1ce9643, which is origin/main. Local main is ahead only by `.planning/` commits; `git diff --name-only 1ce9643..HEAD` lists nothing outside `.planning/`. The verifier did not take the SUMMARY claims on trust. It re-ran the suite (114 tests, OK), listed both Linux tarballs itself, ran the frozen porter from the read-only mounted notarized DMG, and checked the DMG's staple and Gatekeeper result locally. What remains is host behaviour that needs Docker containers or real Linux desktops: G-01-6 on Fedora, G-01-7 on a GNOME desktop, and the arm64 X11/Wayland start that UAT test 3 did not show.

### Observable Truths (Roadmap Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | A tester on each host starts the GUI without Python: the Windows zip runs, the notarized DMG opens from Finder with no Gatekeeper warning, the Linux tarballs run under X11 and Wayland, and a full port from a read-only location leaves the bundle unchanged with codesign still passing | ? UNCERTAIN (human) | UAT tests 1, 2 and 4 passed (Windows without Python, Finder open, full port from the mounted DMG with codesign). Test 3 passed on Linux x64 only; the arm64 tarball was not shown. Both Linux bundles were rebuilt without GTK in 1ce9643, and nobody has started them on a desktop since. For 1ce9643 the verifier checked the DMG locally: `stapler validate` worked, `spctl` gave "accepted, source=Notarized Developer ID", and `codesign --verify --deep --strict` passed after running porter from the read-only mount |
| 2 | Cancel leaves no dotnet/MSBuild/clang/shader-tool process while the adb server keeps running; "cancelled" only once the run stopped; closing mid-port asks and stops the same way | ✓ VERIFIED | UAT test 5 (real cancel mid-port on each host) passed. The mechanism tests still pass in fork-ci 41017724428 on all four OSes. Since d2ec054 nothing in the cancel path changed: the only non-planning changes are tls/fetch/fpslocker, the hooks, the spec and an ARCHITECTURE.md line |
| 3 | A failing, crashing or hanging porter command shows the real cause or a timeout with Retry; the saved log opens from the GUI | ✓ VERIFIED | Regression only. The code is unchanged since the last verification, and the RunLog, OneShot, Timeout and Errors tests pass in the local run and in fork-ci 41017724428 |
| 4 | Every push runs the suite on four OSes from the hashed lock, with headless replay tests; a missing lz4 is a clear skip | ✓ VERIFIED | fork-ci 41017724428 succeeded in all five jobs. 114 tests ran on ubuntu-22.04, ubuntu-24.04-arm, windows-2025 and macos-15, and 83 ran on the 3.11 job. test_tls appears in the Windows log, all ok |
| 5 | The release workflow builds all four bundles, signs and notarizes macOS, smoke-tests each, reports the glibc floor and the nxnative/ diff; secrets are protected; actions are SHA-pinned | ✓ VERIFIED | fork-release 41017737613 (workflow_dispatch, 1ce9643) succeeded: the build jobs for linux-x64, linux-arm64 and windows-x64, the signed and notarized macos-arm64 build, and upstream-diff. The release job was skipped because this was not a tag. Glibc floors were 2.35 on x64 and 2.38 on arm64. The workflow files are unchanged since the last verification |

**Score:** 4/5 roadmap truths verified; 1 waits on host checks (0 present-but-behavior-unverified).

### Gap closure truths (UAT)

| Gap | Truth | Status | Evidence |
|-----|-------|--------|----------|
| G-01-6 | Download missing tools loads the download lists and fetches the missing tools from the signed macOS app | ✓ VERIFIED (macOS frozen CLI); Linux and GUI press → human | **Frozen DMG, run by the verifier.** The 1ce9643 DMG was mounted read-only on this Mac, which has no python.org framework. Its own `ssl.create_default_context()` holds **0 CAs**, with openssl_cafile `/Library/Frameworks/Python.framework/Versions/3.14/etc/openssl/cert.pem`, which is the exact root cause. Even so, `nx2android -m porter tools --only ndk,dotnet,adb --json` exited 0 with `['.NET SDK', 'Android NDK', 'adb']`, `fpslocker.fetch` printed `None` (a verified 404), and codesign still passed. **Dev Python:** with `SSL_CERT_FILE=/nonexistent SSL_CERT_DIR=/nonexistent`, the default store holds 0 CAs and `tls.context()` holds 128. The three items come back with sizes, including the .NET HEAD size 230759804, and the fpslocker call returns None |
| G-01-7 | The Linux bundle starts without GLib or GIO module errors on a host whose GLib is newer | ✓ VERIFIED (cause removed from the artifacts); runtime → human | The verifier ran its own `tar tzf` on both 1ce9643 tarballs: linux-x64 has 2532 entries and linux-arm64 has 2529. Neither has an entry matching `libgio-2.0`, `libgobject`, `libgtk-3`, `libgdk-3`, `libqgtk3.so` or `libqglib.so`. `platformthemes/` holds only `libqxdgdesktopportal.so`. The clean start on a GNOME desktop has not been observed (human items 3 and 4) |

### Plan must-haves (70 truths across 10 plans)

| Plan | Truths | Result | Notes |
|------|--------|--------|-------|
| 01-01 to 01-08 | 59 | ✓ 59/59 (1 override) | Regression check. These plans' files are unchanged since d2ec054, apart from 01-06's spec and ARCHITECTURE.md, which 01-10 edits. The suite and both CI runs are green. The 01-02 truth that waited on a host ("adb server survives the stop") is now confirmed by UAT test 5. The 01-08 glibc override is carried forward |
| 01-09 TLS context | 6 | ✓ 5/6, 1 human | `porter/tls.py` (25 lines): `context()` returns the default when `x509_ca` > 0. Otherwise it loads the first existing file from CA_FILES and never touches `verify_mode` or `check_hostname`. All 4 urlopen calls in porter/ pass `context=tls.context()`: fetch.py:37 (`_get`), :89 (HEAD), :95 (`_download`), and fpslocker.py:31. `tests/test_tls.py` passes 5/5 locally and on windows-2025. No `SSL_CERT_FILE`, `SSL_CERT_DIR` or `GIO_*` is set anywhere in porter/, gui/, packaging/ or .github/. The fixture is a public CA:TRUE certificate with no private key. Truth 1 also names "the Linux bundle on Fedora, Arch or openSUSE", and that half was not run on the frozen Linux bundle (human item 2) |
| 01-10 hooks + spec | 5 | ✓ 4/5, 1 human | Both hook overrides match PyInstaller 6.22.3's stock hooks (locked in requirements-build.txt, and the version installed in the .venv) except for a single basename filter. The spec passes `hookspath=[str(ROOT / 'packaging/hooks')]`, and after Analysis it calls `sys.exit("[RED] …")` when a `libgio-2.0.` or `libgtk-3.` binary is collected. Commit 1ce9643 touches only the 4 task files, so there is no environment-variable route. The macOS DMG is still stapled and notarized, and the Windows build is green. Truth 1's runtime clause ("Qt falls back to its built-in gnome theme and the bundled GLib never scans the host's GIO module folder") needs a GNOME host (human items 3 and 4) |

### Prohibitions

| Plan | Prohibition | Tier | Status | Evidence |
|------|-------------|------|--------|----------|
| 01-02 | MUST NOT write prod.keys contents into a run log or event | test | ✓ VERIFIED | RunLogInProcess.test_no_key_material passes |
| 01-03 | MUST NOT signal or kill any process outside the run's session or Job Object | test | ✓ VERIFIED (main path) | test_stop_kills_tree_keeps_detached passes on three OSes |
| 01-04 | MUST NOT commit fixtures holding local paths, homes, keys or game data | test | ✓ VERIFIED | Replay.test_fixtures_are_scrubbed passes |

### Required Artifacts (gap plans; earlier artifacts regression-checked)

| Artifact | Status | Details |
|----------|--------|---------|
| `porter/tls.py` | ✓ VERIFIED | Has CA_FILES and context(), which uses cert_store_stats. Imported by fetch.py and fpslocker.py |
| `porter/fetch.py`, `porter/fpslocker.py` | ✓ VERIFIED | The only changes from upstream are the import line and the `context=` arguments |
| `tests/test_tls.py`, `tests/fixtures/tls/test-ca.pem` | ✓ VERIFIED | class Context, 5 tests. The fixture is CA:TRUE, CN "nx2android test CA", with no PRIVATE block |
| `packaging/hooks/hook-PySide6.QtGui.py` | ✓ VERIFIED | Drops `libqgtk3.so` |
| `packaging/hooks/hook-PySide6.QtNetwork.py` | ✓ VERIFIED | Drops `libqglib.so` and keeps `collect_qtnetwork_files()` |
| `packaging/nx2android.spec` | ✓ VERIFIED | Has hookspath and the GTK/GIO refusal at lines 20-24 |
| `docs/ARCHITECTURE.md` | ✓ VERIFIED | The packaging/ line names `hooks/` (line 113) |
| Earlier artifacts (runlog, procs, paths, runner, app, packaging/*, workflows, locks, tests) | ✓ VERIFIED | Regression: unchanged since d2ec054, suite green |

### Key Link Verification

| From | To | Via | Status |
|------|----|-----|--------|
| fetch.py `_get`, plan HEAD, `_download` | tls.context() | `context=tls.context()` on each urlopen | ✓ WIRED |
| fpslocker.fetch | tls.context() | `context=tls.context()` | ✓ WIRED |
| nx2android.spec Analysis | packaging/hooks overrides | `hookspath`; the build log in 01-10 shows both processed from packaging/hooks. The tarballs confirm the result: no libqgtk3/libqglib | ✓ WIRED |
| nx2android.spec | a.binaries | `GTK = …startswith(('libgio-2.0.', 'libgtk-3.'))` → `sys.exit('[RED] …')` | ✓ WIRED (never fired: nothing matched on either Linux runner) |
| Earlier links (cli→runlog, runlog→procs, Porter.stop, call_json, Retry, paths→ENGINE, smoke, locks, release env) | | | ✓ WIRED (regression, code unchanged) |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Full suite (run once) | `QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover tests` | Ran 114 tests, OK | ✓ PASS |
| test_tls | `.venv/bin/python -m unittest tests.test_tls -v` | 5/5 ok | ✓ PASS |
| Arch rules | `.venv/bin/python tests/arch_rules.py` | all checks passed | ✓ PASS |
| Empty store, dev Python | `SSL_CERT_FILE=/nonexistent SSL_CERT_DIR=/nonexistent porter tools --only ndk,dotnet,adb --json` | 3 items, exit 0; fpslocker.fetch → None | ✓ PASS |
| Frozen DMG, empty store | mounted 1ce9643 DMG read-only; `nx2android -m porter tools … --json`; script printing default CAs and fpslocker.fetch | default CAs 0; 3 items, exit 0; `fpslocker None`; codesign --deep --strict OK | ✓ PASS |
| DMG notarization | `xcrun stapler validate`; `spctl -a -t open --context context:primary-signature` | worked; accepted, source=Notarized Developer ID | ✓ PASS |
| Linux tarballs | `tar tzf` both 1ce9643 tarballs, grep GTK/GIO | 0 and 0; platformthemes = libqxdgdesktopportal.so | ✓ PASS |
| CI for 1ce9643 | `gh run view 41017724428 / 41017737613 -R NamelessSaint8/nx2android` | ci: 5/5 success; release: 5 success + release skipped | ✓ PASS |
| Fedora / trixie containers | — | not run (Docker, minutes-long installs) | ? SKIP → human |

### Probe Execution

Step 7c: no `scripts/*/tests/probe-*.sh` exist and no plan declares one. The runnable checks are smoke_bundle.py and glibc_floor.py, both inside fork-release 41017737613 (green), plus the frozen-DMG run above.

### Requirements Coverage

All 18 phase IDs are claimed by at least one plan. REQUIREMENTS.md maps exactly 18 IDs to Phase 1, so none is orphaned.

| Requirement | Source Plan | Status | Evidence |
|-------------|-------------|--------|----------|
| BRDG-01 | 01-02, 01-03 | ✓ SATISFIED | UAT test 5 passed on each host, and the mechanism tests are green. REQUIREMENTS.md still shows `[ ]` / Pending (Info) |
| BRDG-02..06 | 01-02..01-04 | ✓ SATISFIED | Regression: tests green, code unchanged |
| PKG-01 | 01-06 | ✓ SATISFIED | UAT test 1 passed. The 1ce9643 Windows build is green |
| PKG-02 | 01-06, 01-08, 01-09, 01-10 | ✓ SATISFIED (Setup-button re-test → human) | UAT 2 and 4 passed. The 1ce9643 DMG is notarized and stapled, and its frozen porter downloads with 0 default CAs |
| PKG-03 | 01-06, 01-09, 01-10 | ? NEEDS HUMAN | x64 X11/Wayland passed on d2ec054. The rebuilt tarball has no GTK/GIO stack. The clean GNOME start (G-01-7) and Fedora downloads (G-01-6) are not yet observed |
| PKG-04 | 01-06, 01-09, 01-10 | ? NEEDS HUMAN | The arm64 tarball was never started on a desktop (UAT 3 note). Its glibc floor is 2.38, below the 2.39 gate, and the tarball has no GTK/GIO stack |
| PKG-05 | 01-05, 01-06 | ✓ SATISFIED | UAT test 4 passed. The verifier also ran porter from the read-only 1ce9643 mount, and codesign still passes |
| PKG-06 | 01-01 | ✓ SATISFIED | Hashed locks, unchanged |
| CI-01..04 | 01-07, 01-08 | ✓ SATISFIED | Runs 41017724428 and 41017737613 |
| TEST-02, TEST-03 | 01-07, 01-04 | ✓ SATISFIED | Regression, green |

### Anti-Patterns Found

The files changed by 01-09 and 01-10 have no TBD, FIXME, XXX, TODO or HACK markers. The `shortcut:` comment on CA_FILES uses the project's form.

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| porter/tls.py | 19-24 | Review WR-01: the CA-file fallback is not limited to POSIX. On Windows, `/etc/ssl/...` resolves against the current drive, so if the Windows stores ever enumerate 0 CAs, a file planted at `X:\etc\ssl\cert.pem` would be trusted | ⚠️ Warning (security hardening) | Rare precondition (empty Windows ROOT/CA stores). The fix is one condition: `or os.name == 'nt'`. Worth doing before the first `v*-ns.*` tag, because the archive hashes arrive over the same TLS |
| tests/test_tls.py | 46 | Review WR-02: the scan accepts any `context=`, not `context=tls.context()` | ⚠️ Warning | A future `context=ssl._create_unverified_context()` would pass the guard |
| packaging/hooks/*.py | — | Review WR-03: the hooks are copies of PyInstaller 6.22.3's stock hooks, and nothing fails if PyInstaller changes | ⚠️ Warning | Partly mitigated: the spec's GTK/GIO refusal catches the stack coming back, and the frozen smoke test catches a dropped plugin. The pin is in requirements-build.txt |
| porter/tls.py | — | Review IN-01..IN-03: only the first existing CA file is tried; `x509_ca` does not count a capath store; one test asserts the mock's own defaults | ℹ️ Info | Advisory |
| packaging/build_bootloader.py | 33, 35 | urlopen without the context | ℹ️ Info | A dev-time build tool outside porter/, not in the player path. It is outside test_tls's scan by design |
| .planning/REQUIREMENTS.md | 12, 170 | BRDG-01 still `[ ]` / Pending although UAT test 5 passed | ℹ️ Info | Tracking drift. Tick it when the phase closes |

All open review findings are recorded `open` in 01-REVIEW-DISPOSITION.md (3 warnings, 3 info from the 01-09/01-10 review, plus IN-04). None stops a must-have from holding, so none is a gap.

### Human Verification Required

Use the artifacts of fork-release run 41017737613; they are already in `build/release-check/new`. The exact commands are in 01-10-PLAN.md Task 3 `<human-check>`. The d2ec054 positive-control build (run 40971470754) expires about 2026-11-05.

1. **UAT test 6 again (G-01-6, PKG-02).** Download the DMG in a browser, open it from Finder, and press Download missing tools on the Setup tab. Expected: the lists load and the tool downloads. Why by hand: the verifier proved the frozen CLI path from the mounted DMG, but not the button in a quarantined, Finder-started app.
2. **G-01-6 on Fedora 44 (PKG-03, PKG-04).** In the amd64 and arm64 containers, run `porter tools --only ndk,dotnet,adb --json` from each Linux tarball. Expected: three items and exit 0. Why by hand: needs Docker and a non-Debian CA layout.
3. **G-01-7 in Debian trixie containers with a GNOME desktop name, old build against new.** Expected: the d2ec054 rows show the gvfs lines and the 1ce9643 rows show "start: no GIO module errors" and "picker closed: ''". Why by hand: runtime behaviour, and Docker with xvfb.
4. **UAT test 7 again (G-01-7, PKG-03).** On the real Debian-family GNOME host, start the x64 tarball with xcb. Expected: no gvfs line, and the Qt folder picker fills in the folder. Why by hand: needs a real desktop session.
5. **Linux arm64 under X11 and Wayland (PKG-04, SC1).** Expected: the window appears under both with no errors. Why by hand: UAT test 3 never showed the arm64 tarball.

### Gaps Summary

No blocking gaps. G-01-6 is closed in code: every porter HTTPS call goes through a verifying context that falls back to the host's CA file only when the bundled OpenSSL has none. The verifier confirmed the fix in the notarized 1ce9643 DMG on a Mac without the runner's CA path: the default store held 0 CAs and the downloads still worked. G-01-7 is closed in the artifacts: both 1ce9643 Linux tarballs ship no GTK3/GIO libraries, and the spec refuses them at build time. The status stays human_needed, for two reasons. The roadmap promises host behaviour on Linux that nobody has watched since the rebuild: a GNOME start with a working folder picker, Fedora downloads, and the arm64 X11/Wayland start that UAT test 3 skipped. The Setup-tab button also needs a re-test (UAT test 6). Review warning WR-01 (a drive-relative CA path on Windows) is a one-line hardening fix that is worth making before the first tag.

---

_Verified: 2026-10-30T08:20:00Z_
_Verifier: Claude (gsd-verifier)_
