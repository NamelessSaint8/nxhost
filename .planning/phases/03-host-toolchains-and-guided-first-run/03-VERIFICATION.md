---
phase: 03-host-toolchains-and-guided-first-run
verified: 2026-10-31T18:05:00Z
status: gaps_found
score: 2/5 must-haves verified
covered_files: [".github/workflows/fork-release.yml",".planning/phases/03-host-toolchains-and-guided-first-run/03-01-PLAN.md",".planning/phases/03-host-toolchains-and-guided-first-run/03-01-SUMMARY.md",".planning/phases/03-host-toolchains-and-guided-first-run/03-02-PLAN.md",".planning/phases/03-host-toolchains-and-guided-first-run/03-02-SUMMARY.md",".planning/phases/03-host-toolchains-and-guided-first-run/03-03-PLAN.md",".planning/phases/03-host-toolchains-and-guided-first-run/03-03-SUMMARY.md",".planning/phases/03-host-toolchains-and-guided-first-run/03-04-PLAN.md",".planning/phases/03-host-toolchains-and-guided-first-run/03-04-SUMMARY.md",".planning/phases/03-host-toolchains-and-guided-first-run/03-05-PLAN.md",".planning/phases/03-host-toolchains-and-guided-first-run/03-05-SUMMARY.md",".planning/phases/03-host-toolchains-and-guided-first-run/03-06-PLAN.md",".planning/phases/03-host-toolchains-and-guided-first-run/03-06-SUMMARY.md",".planning/phases/03-host-toolchains-and-guided-first-run/03-07-PLAN.md",".planning/phases/03-host-toolchains-and-guided-first-run/03-07-SUMMARY.md",".planning/phases/03-host-toolchains-and-guided-first-run/03-08-PLAN.md",".planning/phases/03-host-toolchains-and-guided-first-run/03-08-SUMMARY.md",".planning/phases/03-host-toolchains-and-guided-first-run/03-09-PLAN.md",".planning/phases/03-host-toolchains-and-guided-first-run/03-09-SUMMARY.md",".planning/phases/03-host-toolchains-and-guided-first-run/03-10-PLAN.md",".planning/phases/03-host-toolchains-and-guided-first-run/03-10-SUMMARY.md",".planning/phases/03-host-toolchains-and-guided-first-run/03-11-PLAN.md",".planning/phases/03-host-toolchains-and-guided-first-run/03-11-SUMMARY.md",".planning/phases/03-host-toolchains-and-guided-first-run/03-12-PLAN.md",".planning/phases/03-host-toolchains-and-guided-first-run/03-12-SUMMARY.md","devtools/ndk_pin.py","docs/ARCHITECTURE.md","docs/RELEASE_CHECK.md","gui/app.py","gui/firstrun.py","gui/runner.py","gui/shell.py","nxnative/dm/android/build.py","packaging/INSTALL.md","packaging/smoke_bundle.py","porter/adb.py","porter/childenv.py","porter/cli.py","porter/config.py","porter/desktop.py","porter/distro.py","porter/fetch.py","porter/hosttools.py","porter/keys.py","porter/pins.py","porter/pipeline.py","porter/prepare.py","porter/probe.py","porter/runlog.py","porter/setup.py","porter/toolchain.py","tests/arch_rules.py","tests/fixtures/bridge/fake_porter.py","tests/fixtures/bridge/setup_first.json","tests/fixtures/bridge/setup_missing.json","tests/fixtures/bridge/setup_ready.json","tests/test_adb.py","tests/test_bridge.py","tests/test_desktop.py","tests/test_distro.py","tests/test_fetch.py","tests/test_firstrun.py","tests/test_hosttools.py","tests/test_keys.py","tests/test_packaging.py","tests/test_prepare.py","tests/test_probe.py","tests/test_runlog.py","tests/test_setup.py","tests/test_shell.py","tests/test_toolchain.py","tests/test_workflows.py"]
covered_digest: "v4:sha256:8ff95b50f5e80ae4096fffa6054a02c1b34d545a351ce8928d41a66094c53876"
behavior_unverified: 0
overrides_applied: 0
gaps:
  - truth: "SC1 / FRUN-01: what the wizard saves through porter (prod.keys, NDK, .NET, adb, device) stays saved, so the ready setup the wizard reached holds"
    status: failed
    reason: "CR-01, reproduced. The Setup tab copies config.json into its line edits only at startup and after a fetch run ends. Window.recheck() (called by every wizard save) runs SetupTab.check() but never SetupTab.load(). SetupTab.save() ('Save and check') then writes every stale edit back over config.json. Reproduction (scratch script, offscreen Window, real `porter config keys <path> --json`, then win.recheck(), then win.setup.save()): config keys went from the saved path to ''. A tester who sets prod.keys in the wizard and then changes the output folder on the Setup tab loses prod.keys, and the next port fails with 'prod.keys: not set'."
    artifacts:
      - path: "gui/app.py"
        issue: "Window.recheck (line 430) calls self.setup.check() only; SetupTab.save (lines 353-356) writes every edit, including keys/ndk/dotnet/adb/device the wizard saved after launch"
      - path: "gui/firstrun.py"
        issue: "KeysPage (line 265), ToolsPage Use my own…, DevicePage.pick (line 467) save through porter config, then win.recheck(), which does not refresh the Setup tab's edits"
    missing:
      - "Window.recheck refreshes the Setup tab's edits from config.json before checking (e.g. call SetupTab.load())"
      - "Optionally: SetupTab.save writes only the fields the player changed since the last load"
      - "A GUI test: wizard saves keys through config, Setup tab Save and check keeps them"
  - truth: "SC1 / 03-03: a download resumes its .part with an HTTP Range request after a dropped connection (up to 3 attempts, each retry logged)"
    status: partial
    reason: "WR-01, reproduced. When the server closes the connection cleanly before Content-Length is reached, HTTPResponse.read() returns b'' without raising, the loop ends as if complete, the hash fails, the .part is deleted and a BuildError says the hash differs (for the NDK: 'wait for a pin bump'). Reproduction (local socket server announcing 1000 bytes, sending 300): one request only, no retry, no Range request, .part gone. Resume works for Cancel, restart, connection resets and timeouts (tests/test_fetch.py Resume), not for a clean early close. A chunked response cut short raises http.client.IncompleteRead, which the retry except does not catch either."
    artifacts:
      - path: "porter/fetch.py"
        issue: "_download (lines 117-150): no check that the bytes received match Content-Length before hashing; http.client.HTTPException not in the retried exceptions"
    missing:
      - "Treat received < announced length as a dropped link (raise a retried error, keep the .part) before hashing"
      - "Add http.client.HTTPException to the retried exceptions"
      - "A Resume test with a server that closes cleanly mid-body"
human_verification:
  - test: "Run fork-release.yml: the bare-PATH smoke step on macOS and both Linux bundles, and 'Community NDK download and probe (linux-arm64)' on ubuntu-24.04-arm"
    expected: "Every tool row (Android NDK, .NET SDK, adb) found by absolute path; the arm64 NDK row ok with the community note"
    why_human: "Nothing has been pushed; the workflow has not run for these changes (SC3, SC5, TOOL-01, TOOL-04)"
  - test: "On a real Linux arm64 host: Download all missing, then setup --json and a host build"
    expected: "Community NDK r27c downloaded, hash-checked, probe passes, .NET 10 found or downloaded, build.py uses toolchains/llvm/prebuilt/linux-arm64"
    why_human: "Only mocked platform.machine() in tests; no arm64 machine was used (SC3, TOOL-01, TOOL-02)"
  - test: "Launch the bundle from Finder (macOS) and from the Add to app menu entry (Linux x64 and arm64), then port a playable title"
    expected: "Every tool found by absolute path and the port completes"
    why_human: "Bare-PATH lookup was checked here (env -i PATH=/usr/bin:/bin finds dotnet and adb as 'known place'), but a full port from a Finder or menu launch needs the bundle, game files and the desktop (SC5, TOOL-04)"
  - test: "Plug a device with USB debugging not yet allowed into the wizard's device page; on Linux without udev rules, plug one in"
    expected: "unauthorized with its one-line fix, turning live to device after Allow; no permissions with the distro udev package command"
    why_human: "Needs a real device and USB; parsing and fix text are unit-tested from captured adb output only (SC4, DEV-01)"
  - test: "On Ubuntu 22.04 / Debian 12 with distro adb 29.0.6, install a port"
    expected: "The adb row shows 29.0.6 and the no -Z note; the install succeeds"
    why_human: "Needs a distro adb and a device (SC4, TOOL-03)"
  - test: "On a slow host (SD-card arm64 board), first launch after an NDK download"
    expected: "setup --json answers within the GUI's 45 s limit (WR-02: the probe's own limits are 60 s per step, so a slow first probe can be killed and never cached)"
    why_human: "Timing depends on real hardware"
  - test: "Judgment-tier prohibition (03-05): the wizard links to no keys or firmware source, offers no firmware step, shows no key value"
    expected: "Confirmed by reading the pages"
    why_human: "unverified-prohibition — human review recommended. Non-authoritative LLM-judge verdict: holds (gui/firstrun.py has no firmware/key links; legal links are the three vendor license pages from porter/setup.py LINKS)"
---

# Phase 3: Host Toolchains and Guided First Run Verification Report

**Phase Goal:** A tester on any of the four hosts goes from a fresh download to a ready setup (keys, toolchains, a connected device) by following the GUI
**Verified:** 2026-10-31T18:05:00Z
**Status:** gaps_found
**Re-verification:** No, initial verification

## Goal Achievement

The porter side and the wizard are real, wired and well tested: `setup --json`, the prod.keys check, bare-PATH discovery, the community NDK pin, the probe, adb state parsing and the five wizard pages all exist and do what the plans say. Two defects stand in the way of the goal, and both were reproduced here: settings the wizard saves can be wiped by the Setup tab, and a download cut off cleanly by the server loses its progress instead of resuming.

### Observable Truths (roadmap success criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | First launch walks through the legal notice, prod.keys (validated, generation shown), toolchain downloads (progress, cancel, resume, hash check) and connecting a device | ✗ FAILED (partial) | Walk-through present and wired: PAGES legal/keys/tools/device/done in gui/firstrun.py, opened by firstrun.on_ready from both windows; tests Launch/Legal/Keys/Tools/Device/Done pass. Fails on: CR-01 (wizard-saved settings reverted by the Setup tab's Save and check, reproduced) and WR-01 (clean early close is not resumed, .part deleted, reproduced) |
| 2 | Skipping shows a banner naming what is missing; setup can be reopened; readiness comes from `porter setup --json` on every launch and the GUI stores none of it | ✓ VERIFIED | Banner/Run setup/Continue setup in firstrun.py; arch_rules: firstrun.py and shell.py import only gui.runner/PySide6/stdlib and write no file; `env -i PATH=/usr/bin:/bin porter setup --json` returned the documented shape with fixed step order and wrote no config.json; tests Banner, Wizard.test_skip_closes_no_write, Launch.test_second_doc_never_opens pass |
| 3 | Linux arm64: community NDK r27c detected or downloaded, hash- and probe-checked; .NET 10; host build uses `linux-arm64` | ? UNCERTAIN | Code present: pins.NDK linux-arm64 row, fetch._ndk_host, probe.host_folder, build.py lines 28-29, hosttools.known adds /usr/lib/dotnet etc.; `devtools/ndk_pin.py` printed PASS against the live GitHub asset. Proven only with mocked platform.machine(); the CI arm64 step has not run |
| 4 | Linux: distro adb version shown, no-`-Z` adb handled or refused with fix text; device states with one-line fixes (udev package for `no permissions`) | ✓ VERIFIED (code level) | toolchain.py adb row (version, -Z note, protocol 1.0.39 floor), hosttools.push_flags, adb.py ROW and `*self.nz` at both push sites, cli.py cmd_devices adds detail/fix via distro.device_fix; tests test_adb/test_distro/test_hosttools pass. Live device transition is a human item |
| 5 | Launched from Finder or a desktop menu with a minimal PATH, every tool found by absolute path and a port runs | ? UNCERTAIN | Lookup proven here: bare-PATH `setup --json` found `/opt/homebrew/bin/dotnet` and `/opt/homebrew/bin/adb` with source `known place`; tests BarePath and test_packaging pass; childenv.dotnet wired in pipeline.py:98 and prepare.py:19. "A port runs" from Finder/menu not proven |

**Score:** 2/5 roadmap truths verified (1 failed, 2 need a real host; 0 present-but-behavior-unverified)

Plan-level truths (about 140 across 12 plans) were checked through their named tests in the full suite (419 tests, all pass) and by reading the code for the key ones. Only the 03-03 dropped-connection resume truth fails (gap 2). CR-01 is an integration gap no single plan truth covered: the wizard plans save through porter, and the old Setup tab was not taught to reload.

### Required Artifacts

`gsd-tools verify.artifacts` on all 12 plans: 43/44 passed. The one miss (03-10 `contains: singleShot(2500`) is a literal-pattern miss only: the code uses `POLL_MS = 2500` (firstrun.py:17) in `QTimer.singleShot(POLL_MS, ...)` (line 448). All artifacts are substantive (porter modules 15-276 lines with real logic, firstrun.py 538 lines).

| Artifact | Status | Details |
|----------|--------|---------|
| porter/setup.py | ✓ VERIFIED | report(): one toolchain.checks() call, legal/keys/tools/device steps, missing, notes, desktop |
| porter/keys.py | ✓ VERIFIED | 1 MB cap, header_key and generation checks, candidates() |
| porter/desktop.py | ✓ VERIFIED | Exec quoting, symlink refusal (TryExec/Icon unescaped, IN-03) |
| porter/hosttools.py, porter/childenv.py | ✓ VERIFIED | known places per OS, dotnet_root, adb_version, push_flags; env dict with DOTNET_ROOT, invariant globalization, LANG |
| porter/pins.py, porter/fetch.py | ⚠️ PARTIAL | pin and Range resume present; short-body handling missing (gap 2) |
| porter/probe.py, porter/distro.py | ✓ VERIFIED | compile probe with cache; distro commands (fix text unquoted paths, WR-06) |
| porter/prepare.py | ✓ VERIFIED | calls pipeline.Port.translator unbound, childenv env |
| nxnative/dm/android/build.py | ✓ VERIFIED | linux-arm64/linux-aarch64 on aarch64; glslc fallback unguarded (IN-08) |
| gui/firstrun.py, gui/shell.py | ✓ VERIFIED | five pages, banner, gate shared by both windows |
| gui/app.py | ✗ (integration) | hook lines present; recheck does not reload SetupTab edits (gap 1) |
| packaging/smoke_bundle.py, .github/workflows/fork-release.yml, devtools/ndk_pin.py | ✓ VERIFIED (CI pending) | bare_env_check, `--community-ndk` step gated to `matrix.target == 'linux-arm64'` |

### Key Link Verification

The gsd-tools key-link verb could not parse these plans' `from:` fields (symbol names after the path), so every link was checked by grep:

| From | To | Status |
|------|----|--------|
| cli.py dispatch | `'setup': cmd_setup`, `'desktop-entry': cmd_desktop` | ✓ WIRED (cli.py:197) |
| setup.report | toolchain.checks( | ✓ WIRED (setup.py:38) |
| cli.cmd_config | setup.VERSION | ✓ WIRED (cli.py:189) |
| toolchain find_adb/find_dotnet | hosttools.known( | ✓ WIRED (toolchain.py:72, :89) |
| pipeline Port.run | childenv.dotnet(, tools['notes'] | ✓ WIRED (pipeline.py:90, :98) |
| fetch._pinned | _ndk_host() | ✓ WIRED (fetch.py:51, :85) |
| runlog | 'rate', _explain | ✓ WIRED (runlog.py:118, :125) |
| toolchain NDK row | probe.probe(, probe.note( | ✓ WIRED (toolchain.py:132-135) |
| cli.cmd_devices | distro.device_fix / state_kind | ✓ WIRED (cli.py:143) |
| adb push sites | *self.nz | ✓ WIRED (adb.py:180, :200) |
| prepare.run | Port.translator( | ✓ WIRED (prepare.py:23); cli.py:158 prepare.run |
| app SetupTab.check / shell.recheck | 'setup', '--json' | ✓ WIRED |
| app/shell | firstrun.attach(self), firstrun.on_ready( | ✓ WIRED (app.py:404, :436; shell.py:38, :51) |
| firstrun pages | config legal/keys/device, devices --json, desktop-entry --install, tools --download/--prepare | ✓ WIRED (firstrun.py:187, 265, 467, 449, 523, 361, 363) |
| app SetupTab.on_fetch | firstrun.progress_line( | ✓ WIRED (app.py:322) |
| fork-release.yml | smoke_bundle.py --community-ndk | ✓ WIRED (line 62) |

### Data-Flow Trace (Level 4)

| Artifact | Data | Source | Real data | Status |
|----------|------|--------|-----------|--------|
| Banner / wizard pages | setup --json doc | porter subprocess via call_json | yes (live run returned real rows) | ✓ FLOWING |
| Device page | devices --json rows | Adb.devices() parsing `adb devices -l` | yes | ✓ FLOWING |
| Setup tab line edits | config.json | config.load() at startup and after fetch only | stale after wizard saves | ✗ STALE (gap 1) |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Full suite | `QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover tests` | 419 tests OK | ✓ PASS |
| Arch rules | `.venv/bin/python tests/arch_rules.py` | all checks passed (firstrun/shell purity, hyphenated subcommands) | ✓ PASS |
| Bare-PATH setup | `env -i PATH=/usr/bin:/bin HOME=<tmp> NX2A_HOME=<tmp> porter setup --json` | exit 1 (not ready), shape correct, dotnet and adb from `known place`, steps in order, no config.json written | ✓ PASS |
| Pin vs live asset | `.venv/bin/python devtools/ndk_pin.py` | PASS android-ndk-r27c-aarch64-linux-gnu.tar.xz matches porter/pins.py | ✓ PASS |
| CR-01 reproduction | scratch script: porter config keys, win.recheck(), win.setup.save() | keys `<path>` → `''` | ✗ FAIL |
| WR-01 reproduction | scratch script: server sends 300 of 1000 bytes and closes | 1 request, BuildError hash mismatch, .part deleted | ✗ FAIL |

### Probe Execution

No `scripts/*/tests/probe-*.sh` exist and no plan declares one. The release-workflow probe (`smoke_bundle.py --community-ndk`) runs only in CI and has not run: human item.

### Requirements Coverage

| Requirement | Source Plan | Status | Evidence |
|-------------|-------------|--------|----------|
| TOOL-01 | 03-03, 03-04, 03-08, 03-09, 03-11 | ? NEEDS HUMAN | pin, probe, host folder, community note all present and unit-tested; real arm64 run pending |
| TOOL-02 | 03-02, 03-03, 03-09 | ✓ SATISFIED (arm64 run pending) | known .NET places on Linux, linux-arm64 .NET pin, Prepare |
| TOOL-03 | 03-02, 03-04, 03-06, 03-09, 03-11 | ✓ SATISFIED | adb version, -Z by major, protocol floor, distro commands, udev fix |
| TOOL-04 | 03-01, 03-02, 03-08, 03-10 | ✓ SATISFIED (Finder/menu port pending) | bare-PATH lookup proven locally |
| FRUN-01 | 03-01, 03-03, 03-05, 03-09..03-12 | ✗ BLOCKED | gaps 1 and 2 |
| FRUN-02 | 03-01, 03-05, 03-07 | ✓ SATISFIED | banner, Continue setup, Run setup, Skip |
| FRUN-03 | 03-01, 03-05, 03-07 | ✓ SATISFIED | setup --json on every launch; arch rules enforce no storage |
| DEV-01 | 03-06, 03-10 | ✓ SATISFIED (live device pending) | detail/fix rows, live polling page |

All 8 IDs appear in plan frontmatter; REQUIREMENTS.md maps exactly these 8 to Phase 3, so none is orphaned. REQUIREMENTS.md already marks all 8 `[x]` Complete; FRUN-01 should not be complete yet.

### Prohibitions

| Prohibition | Tier | Disposition |
|-------------|------|-------------|
| No prod.keys value printed, logged, returned or copied | test | ✓ tests test_keys.test_no_values_out, test_firstrun Keys.test_no_values |
| Legal accepted only through `config legal <VERSION>`; setup never writes config.json | test | ✓ test_setup.test_legal_round_trip; observed: bare run wrote no config.json (the plain non-JSON `config legal` skips the guard, IN-05) |
| No .desktop write unless `desktop-entry --install` | test | ✓ test_desktop.test_setup_writes_nothing |
| No login-shell PATH or startup files | test | ✓ no such read in porter/ (grep), BarePath tests |
| No install of a mismatched hash, no fallback NDK, no silent re-download | test | ✓ test_mismatch_deletes_part, Pins tests |
| Community NDK always labelled | test | ✓ probe.note, test_probe Rows |
| Never restart adb or run commands for the player | test | ✓ test_adb.test_never_restarts_server |
| Wizard never traps the player | test | ✓ test_non_modal_classic, test_skip_closes_no_write |
| No keys/firmware links, no firmware step, no key values in the wizard | judgment | flagged: non-authoritative pass, human review recommended |

### Anti-Patterns Found

No TBD/FIXME/XXX/TODO/HACK markers in the 48 phase-modified files. Open code-review findings (03-REVIEW-DISPOSITION.md, all 15 still `open`):

| File | Line | Finding | Severity | Impact |
|------|------|---------|----------|--------|
| gui/app.py | 353-356, 430 | CR-01 stale Setup tab edits overwrite wizard saves | 🛑 Blocker | gap 1 |
| porter/fetch.py | 138-150 | WR-01 clean early close not retried; .part deleted | 🛑 Blocker (partial) | gap 2 |
| gui/runner.py / porter/probe.py | 18 / 12 | WR-02 45 s GUI limit under the probe's 60 s limits | ⚠️ Warning | slow hosts may never get a setup answer (human item) |
| porter/probe.py | 57-58 | WR-03 fixed temp name, unhandled OSError, two concurrent setup runs after a fetch | ⚠️ Warning | a failed cache write crashes doctor/setup/port |
| gui/app.py / gui/runner.py | 300-313 / 53 | WR-04 second start on the shared fetch orphans the first run (also T-03-35, open) | ⚠️ Warning | two downloads on the same .part; Cancel misses one |
| gui/firstrun.py | 390 | WR-05 auto Prepare ignores a quit in progress | ⚠️ Warning | orphaned dotnet builds after Stop and quit |
| porter/probe.py | 49 | WR-06 unquoted paths in the chmod/xattr fix | ⚠️ Warning | the pasted fix fails under "Application Support" |
| various | - | IN-01..IN-08 | ℹ️ Info | see 03-REVIEW.md |

UI review (03-UI-REVIEW.md, 15/24): the word "porter" still shows on the Setup tab's failure path, hard-coded colours bypass the theme table, and the device page layout spreads out when empty. None blocks the goal; all are warnings.

### Human Verification Required

See the `human_verification` frontmatter: the fork-release.yml run (bare-PATH smoke, arm64 community NDK step), a real Linux arm64 host, a Finder and app-menu launch with a full port, a live `unauthorized` → `device` and `no permissions` device, distro adb 29.x, setup timing on a slow host, and the judgment-tier wizard prohibition.

### Gaps Summary

Both gaps sit under SC1 (FRUN-01), the part of the goal that says the tester reaches a ready setup and it holds:

1. **Wizard saves are undone by the Setup tab (CR-01).** The fix is one line in `Window.recheck` (reload the Setup tab's edits) plus a test. Without it, a tester who uses both views can lose prod.keys or a chosen NDK/dotnet/adb/device with no warning.
2. **A clean early close loses the download (WR-01).** Resume works for Cancel, restarts, resets and timeouts, but a server or proxy that closes cleanly mid-body makes porter hash a short file, delete the `.part` and show a misleading hash error. The fix is a length check before hashing and catching `http.client.HTTPException`.

Neither gap is covered by a later phase. The warnings (WR-02..WR-06) are worth fixing in the same gap-closure plan, WR-04 and WR-05 especially, since they leave runs the close guard cannot see.

---

_Verified: 2026-10-31T18:05:00Z_
_Verifier: Claude (gsd-verifier)_
