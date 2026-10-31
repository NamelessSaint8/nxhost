---
phase: 03-host-toolchains-and-guided-first-run
verified: 2026-10-31T20:10:00Z
status: human_needed
score: 3/5 must-haves verified
covered_files: [".github/workflows/fork-release.yml",".planning/phases/03-host-toolchains-and-guided-first-run/03-01-PLAN.md",".planning/phases/03-host-toolchains-and-guided-first-run/03-01-SUMMARY.md",".planning/phases/03-host-toolchains-and-guided-first-run/03-02-PLAN.md",".planning/phases/03-host-toolchains-and-guided-first-run/03-02-SUMMARY.md",".planning/phases/03-host-toolchains-and-guided-first-run/03-03-PLAN.md",".planning/phases/03-host-toolchains-and-guided-first-run/03-03-SUMMARY.md",".planning/phases/03-host-toolchains-and-guided-first-run/03-04-PLAN.md",".planning/phases/03-host-toolchains-and-guided-first-run/03-04-SUMMARY.md",".planning/phases/03-host-toolchains-and-guided-first-run/03-05-PLAN.md",".planning/phases/03-host-toolchains-and-guided-first-run/03-05-SUMMARY.md",".planning/phases/03-host-toolchains-and-guided-first-run/03-06-PLAN.md",".planning/phases/03-host-toolchains-and-guided-first-run/03-06-SUMMARY.md",".planning/phases/03-host-toolchains-and-guided-first-run/03-07-PLAN.md",".planning/phases/03-host-toolchains-and-guided-first-run/03-07-SUMMARY.md",".planning/phases/03-host-toolchains-and-guided-first-run/03-08-PLAN.md",".planning/phases/03-host-toolchains-and-guided-first-run/03-08-SUMMARY.md",".planning/phases/03-host-toolchains-and-guided-first-run/03-09-PLAN.md",".planning/phases/03-host-toolchains-and-guided-first-run/03-09-SUMMARY.md",".planning/phases/03-host-toolchains-and-guided-first-run/03-10-PLAN.md",".planning/phases/03-host-toolchains-and-guided-first-run/03-10-SUMMARY.md",".planning/phases/03-host-toolchains-and-guided-first-run/03-11-PLAN.md",".planning/phases/03-host-toolchains-and-guided-first-run/03-11-SUMMARY.md",".planning/phases/03-host-toolchains-and-guided-first-run/03-12-PLAN.md",".planning/phases/03-host-toolchains-and-guided-first-run/03-12-SUMMARY.md",".planning/phases/03-host-toolchains-and-guided-first-run/03-13-PLAN.md",".planning/phases/03-host-toolchains-and-guided-first-run/03-13-SUMMARY.md",".planning/phases/03-host-toolchains-and-guided-first-run/03-14-PLAN.md",".planning/phases/03-host-toolchains-and-guided-first-run/03-14-SUMMARY.md",".planning/phases/03-host-toolchains-and-guided-first-run/03-15-PLAN.md",".planning/phases/03-host-toolchains-and-guided-first-run/03-15-SUMMARY.md","devtools/ndk_pin.py","docs/ARCHITECTURE.md","docs/RELEASE_CHECK.md","gui/app.py","gui/firstrun.py","gui/runner.py","gui/shell.py","nxnative/dm/android/build.py","packaging/INSTALL.md","packaging/smoke_bundle.py","porter/adb.py","porter/childenv.py","porter/cli.py","porter/config.py","porter/desktop.py","porter/distro.py","porter/fetch.py","porter/hosttools.py","porter/keys.py","porter/pins.py","porter/pipeline.py","porter/prepare.py","porter/probe.py","porter/runlog.py","porter/setup.py","porter/toolchain.py","tests/arch_rules.py","tests/fixtures/bridge/fake_porter.py","tests/fixtures/bridge/setup_first.json","tests/fixtures/bridge/setup_missing.json","tests/fixtures/bridge/setup_ready.json","tests/test_adb.py","tests/test_bridge.py","tests/test_desktop.py","tests/test_distro.py","tests/test_fetch.py","tests/test_firstrun.py","tests/test_hosttools.py","tests/test_keys.py","tests/test_packaging.py","tests/test_prepare.py","tests/test_probe.py","tests/test_runlog.py","tests/test_setup.py","tests/test_shell.py","tests/test_toolchain.py","tests/test_workflows.py"]
covered_digest: "v4:sha256:94bc0a39f3bcbbeb9c571027657808e91177a053ffc43d081f51c2da280e1bb3"
behavior_unverified: 0
overrides_applied: 0
re_verification:
  previous_status: gaps_found
  previous_score: 2/5
  gaps_closed:
    - "SC1 / FRUN-01: what the wizard saves through porter (prod.keys, NDK, .NET, adb, device) stays saved (CR-01)"
    - "SC1 / 03-03: a download resumes its .part with an HTTP Range request after a dropped connection, including a clean early close and a cut chunked body (WR-01)"
  gaps_remaining: []
  regressions: []
human_verification:
  - test: "Run fork-release.yml: the bare-PATH smoke step on macOS and both Linux bundles, and 'Community NDK download and probe (linux-arm64)' on ubuntu-24.04-arm"
    expected: "Every tool row (Android NDK, .NET SDK, adb) found by absolute path; the arm64 NDK row ok with the community note"
    why_human: "Nothing has been pushed; the workflow has not run for these changes (SC3, SC5, TOOL-01, TOOL-04)"
  - test: "On a real Linux arm64 host: Download all missing, then setup --json and a host build"
    expected: "Community NDK r27c downloaded, hash-checked, probe passes, .NET 10 found or downloaded, build.py uses toolchains/llvm/prebuilt/linux-arm64"
    why_human: "Only mocked platform.machine() in tests; no arm64 machine was used (SC3, TOOL-01, TOOL-02)"
  - test: "Launch the bundle from Finder (macOS) and from the Add to app menu entry (Linux x64 and arm64), then port a playable title"
    expected: "Every tool found by absolute path and the port completes"
    why_human: "Bare-PATH lookup re-checked here (env -i PATH=/usr/bin:/bin finds dotnet and adb as 'known place'), but a full port from a Finder or menu launch needs the bundle, game files and the desktop (SC5, TOOL-04)"
  - test: "Plug a device with USB debugging not yet allowed into the wizard's device page; on Linux without udev rules, plug one in"
    expected: "unauthorized with its one-line fix, turning live to device after Allow; no permissions with the distro udev package command"
    why_human: "Needs a real device and USB; parsing and fix text are unit-tested from captured adb output only (SC4, DEV-01)"
  - test: "On Ubuntu 22.04 / Debian 12 with distro adb 29.0.6, install a port"
    expected: "The adb row shows 29.0.6 and the no -Z note; the install succeeds"
    why_human: "Needs a distro adb and a device (SC4, TOOL-03)"
  - test: "On a slow host (SD-card arm64 board), first launch right after downloading both the NDK and .NET"
    expected: "setup --json answers within the GUI's 150 s limit; if not, Retry answers (the probe pass was cached before the dotnet checks)"
    why_human: "Timing depends on real hardware; the 150 s bound covers the probe's two 60 s steps but not find_dotnet's and checks()'s dotnet --list-sdks 60 s limits (03-REVIEW WR-02, open)"
  - test: "Judgment-tier prohibition (03-05): the wizard links to no keys or firmware source, offers no firmware step, shows no key value"
    expected: "Confirmed by reading the pages"
    why_human: "unverified-prohibition — human review recommended. Non-authoritative LLM-judge verdict: holds (gui/firstrun.py has no firmware/key links; legal links are the vendor license pages from porter/setup.py LINKS)"
---

# Phase 3: Host Toolchains and Guided First Run Verification Report

**Phase Goal:** A tester on any of the four hosts goes from a fresh download to a ready setup (keys, toolchains, a connected device) by following the GUI
**Verified:** 2026-10-31T20:10:00Z
**Status:** human_needed
**Re-verification:** Yes, after gap closure (plans 03-13, 03-14, 03-15)

## Goal Achievement

Both gaps from the previous report are closed, and both were checked by re-running the reproductions that found them, not by reading the summaries. What is left can only be proven on hardware this run did not have: a Linux arm64 host, a Finder or app-menu launch with a full port, a real device, and the CI workflow.

### Gap re-checks

| Gap | Previous result | Now | Evidence |
|-----|-----------------|-----|----------|
| CR-01: wizard saves undone by the Setup tab | keys `<path>` → `''` | ✓ CLOSED | Independent end-to-end run (scratch script, offscreen `Window`, the real wizard `KeysPage.save` → real `porter config keys <path> --json` subprocess → `win.recheck()`, then the output folder typed on the Setup tab and `win.setup.save()`): config.json kept `keys=<path>` and gained `out=<path>`, PASS. Code: `Window.recheck` now calls `SetupTab.load()` (gui/app.py:444); `load()` refreshes fields still equal to the loaded snapshot (357-361); `save()` writes only fields that differ from it (363-367). A save with no reload in between (DevicePage.pick saves without a recheck) is also safe, because untouched fields are not written: tests SetupTab.test_save_writes_changed_only, test_wizard_save_kept, test_unsaved_edit_kept |
| WR-01: clean early close loses the download | 1 request, hash BuildError, .part deleted | ✓ CLOSED | Independent loopback socket server (announces 1000 bytes, sends 300, closes): requests `[None, 'bytes=300-']`, file whole, `.part` gone, say line `x.zip: the server closed the link at 300 of 1000 bytes, retry 1`. Three short answers: `ConnectionResetError`, `.part` kept (300 bytes), no hash message. Code: porter/fetch.py:140 raises `ConnectionResetError` when `have < end`; :145 catches `http.client.HTTPException`. Tests EarlyClose.test_clean_close_resumed, test_chunked_cut_resumed, test_short_answers_keep_part |

### Observable Truths (roadmap success criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | First launch walks through the legal notice, prod.keys (validated, generation shown), toolchain downloads (progress, cancel, resume, hash check) and connecting a device | ✓ VERIFIED | Walk-through present and wired (PAGES legal/keys/tools/device/done, opened by firstrun.on_ready from both windows). CR-01 and WR-01 closed (above). Cancel and quit are tighter too: a second start on a running fetch is refused (runner.py:58, Stop.test_second_start_refused), no Prepare starts on a quitting window (firstrun.py:379, :404, Tools.test_no_prepare_while_quitting) |
| 2 | Skipping shows a banner naming what is missing; setup can be reopened; readiness comes from `porter setup --json` on every launch and the GUI stores none of it | ✓ VERIFIED | Regression check: arch_rules pass (firstrun.py/shell.py purity); bare-PATH `setup --json` re-run returned steps `['legal','keys','tools','device']`, ready false, wrote no config.json. Banner now follows the palette (Banner.test_follows_palette) |
| 3 | Linux arm64: community NDK r27c detected or downloaded, hash- and probe-checked; .NET 10; host build uses `linux-arm64` | ? UNCERTAIN | Code unchanged since the last run except probe.py (best-effort cache through mkstemp, quoted fix paths; Probe.test_cache_write_fails, test_quoted_fix). Still proven only with mocked `platform.machine()`; the CI arm64 step has not run |
| 4 | Linux: distro adb version shown, no-`-Z` adb handled or refused with fix text; device states with one-line fixes | ✓ VERIFIED (code level) | adb.py, hosttools.py, distro.py, cli.py unchanged in gap closure; their tests pass. Live device transition is a human item |
| 5 | Launched from Finder or a desktop menu with a minimal PATH, every tool found by absolute path and a port runs | ? UNCERTAIN | Bare-PATH lookup re-checked: `.NET SDK` and `adb` both `known place`. "A port runs" from Finder or a menu is not proven |

**Score:** 3/5 roadmap truths verified (2 need a real host or CI; 0 present-but-behavior-unverified)

Plan-level truths of 03-13..03-15 were checked through their named tests (all present in tests/, all in the green suite) and by reading the changed code. Regression check on 03-01..03-12: nothing in porter/ other than fetch.py and probe.py changed, and the full suite passes.

### Required Artifacts (gap-closure plans)

| Artifact | Status | Details |
|----------|--------|---------|
| porter/fetch.py | ✓ VERIFIED | short-body check before hashing; `http.client.HTTPException` retried; T-03-10 206/Content-Range rule unchanged (line 132) |
| porter/probe.py | ✓ VERIFIED | `tempfile.mkstemp` + `os.replace`, `except OSError` swallowed; `shlex.quote` on both fix paths, glob outside the quotes |
| gui/app.py | ✓ VERIFIED | `loaded` snapshot, `load()`/`save()`, `check()` one at a time, `show_run()`, `confirm_download` guards, `recheck` reloads; diff limited to the Setup tab, `recheck` and the device-list failure line (hook-line prohibition holds) |
| gui/runner.py | ✓ VERIFIED | `started = Signal()`, `start()` returns False on a second run, `TIMEOUTS['setup'] = 150` |
| gui/firstrun.py | ✓ VERIFIED | `PREPARED`, `quitting()`, `started.connect(self.sync)`, `PaletteChange` event filter, device page stretch |
| tests (test_fetch, test_probe, test_firstrun, test_bridge) | ✓ VERIFIED | EarlyClose/Loopback, Probe, SetupTab, Tools, Device, Banner, Stop, Close cases present and passing |

### Key Link Verification

| From | To | Status |
|------|----|--------|
| wizard KeysPage/ToolsPage/LegalPage saves | `win.recheck()` → `SetupTab.load()` | ✓ WIRED (firstrun.py:203, 275, 350; app.py:444); proven end to end above |
| fetch._download short body | retry branch | ✓ WIRED (fetch.py:140 → :145); proven over a real socket |
| toolchain.checks | probe.probe() never raising on cache write | ✓ WIRED (test_cache_write_fails) |
| SetupTab / ToolsPage | `Porter.started` | ✓ WIRED (app.py:281 `started.connect(self.show_run)`; firstrun `started.connect(self.sync)`, Tools.test_label_from_start) |
| runner TIMEOUTS['setup'] | probe.TIMEOUT | ✓ WIRED (150 > 2×60+15, Timeout.test_default_limits); bound incomplete, see WR-02 below |

### Data-Flow Trace (Level 4)

| Artifact | Data | Source | Real data | Status |
|----------|------|--------|-----------|--------|
| Banner / wizard pages | setup --json doc | porter subprocess via call_json | yes | ✓ FLOWING |
| Device page | devices --json rows | `adb devices -l` parsing | yes | ✓ FLOWING |
| Setup tab line edits | config.json | `config.load()` on every recheck, after a fetch and after Save | yes | ✓ FLOWING (was STALE) |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Full suite (run once) | `QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover tests` | 439 tests OK, 0 skipped | ✓ PASS |
| Arch rules | `.venv/bin/python tests/arch_rules.py` | all checks passed | ✓ PASS |
| CR-01 end to end | scratch script: real KeysPage.save → porter config → recheck → Setup tab edit → Save and check | keys kept, out written | ✓ PASS |
| WR-01 clean close | scratch loopback server, 300 of 1000 bytes then a 206 | 2 requests, second `bytes=300-`, file whole | ✓ PASS |
| WR-01 three short answers | same server, short ×3 | ConnectionResetError, .part kept, no hash message | ✓ PASS |
| Bare-PATH setup | `env -i PATH=/usr/bin:/bin HOME=<tmp> NX2A_HOME=<tmp> porter setup --json` | exit 1 (not ready), steps in order, dotnet/adb `known place`, no config.json | ✓ PASS |

### Probe Execution

No `scripts/*/tests/probe-*.sh` exist and no plan declares one. The release-workflow probe (`smoke_bundle.py --community-ndk`) runs only in CI and has not run: human item.

### Requirements Coverage

| Requirement | Source Plans | Status | Evidence |
|-------------|--------------|--------|----------|
| TOOL-01 | 03-03, 03-04, 03-08, 03-09, 03-11, 03-13, 03-15 | ? NEEDS HUMAN | pin, probe, host folder present and unit-tested; real arm64 run pending |
| TOOL-02 | 03-02, 03-03, 03-09, 03-14 | ✓ SATISFIED (arm64 run pending) | known .NET places, linux-arm64 .NET pin, Prepare (now quit-guarded) |
| TOOL-03 | 03-02, 03-04, 03-06, 03-09, 03-11 | ✓ SATISFIED | adb version, -Z by major, protocol floor, distro commands, udev fix |
| TOOL-04 | 03-01, 03-02, 03-08, 03-10 | ✓ SATISFIED (Finder/menu port pending) | bare-PATH lookup re-proven locally |
| FRUN-01 | 03-01, 03-03, 03-05, 03-09..03-15 | ✓ SATISFIED | both gaps closed and reproduced as fixed |
| FRUN-02 | 03-01, 03-05, 03-07, 03-14 | ✓ SATISFIED | banner, Continue setup, Run setup, Skip |
| FRUN-03 | 03-01, 03-05, 03-07, 03-15 | ✓ SATISFIED | setup --json on every launch; arch rules enforce no storage |
| DEV-01 | 03-06, 03-10, 03-14 | ✓ SATISFIED (live device pending) | detail/fix rows, live polling page |

All 8 IDs appear in plan frontmatter, and REQUIREMENTS.md maps exactly these 8 to Phase 3, so none is orphaned. REQUIREMENTS.md currently shows all 8 as `[ ]` / "Gaps Found" (reverted in 0d4982e). The orchestrator should update them once the human items are settled. 03-15's judgment prohibition held: no gap-closure commit touched REQUIREMENTS.md or 03-SECURITY.md.

### Prohibitions

| Prohibition | Tier | Disposition |
|-------------|------|-------------|
| 03-13: never hash, delete or rename a `.part` whose body ended early | test | ✓ EarlyClose.test_short_answers_keep_part; reproduced here |
| 03-13: T-03-10 kept (append only on a 206 starting at the part's size; final hash decides) | test | ✓ fetch.py:132-134 unchanged; Resume tests pass |
| 03-14: `failed()`/`cause()` signatures unchanged; firstrun.py imports only PySide6/stdlib, no file write | test | ✓ arch_rules pass; shell.py and app.py one-argument calls unchanged |
| 03-15: never write a Setup tab field the player did not change | test | ✓ test_save_writes_changed_only; reproduced here |
| 03-15: app.py edits limited to the Setup tab, recheck and the device-list failure line | test | ✓ git diff 85ca723..HEAD -- gui/app.py |
| 03-15: no edit to REQUIREMENTS.md or 03-SECURITY.md | judgment | ✓ git log over the gap-closure range: none |
| Earlier prohibitions (keys values, legal version, .desktop writes, login-shell PATH, mismatched hash, community label, adb restart, wizard never traps) | test | ✓ unchanged; their tests pass |
| 03-05: no keys/firmware links, no firmware step, no key values in the wizard | judgment | flagged: non-authoritative pass, human review recommended |

### Anti-Patterns Found

No TBD/FIXME/XXX markers in the 10 files the gap closure touched. Open findings from the incremental review (03-REVIEW.md, 03-REVIEW-DISPOSITION.md: 5 open):

| File | Line | Finding | Severity | Impact |
|------|------|---------|----------|--------|
| gui/firstrun.py | 449-451 | new WR-01: `DevicePage.redraw` (added by 03-14) resets the Next button to "Skip: install later" on every setup --json answer, even with a ready device; `draw()` fixes it at the next 2.5 s poll, and not at all while `devices --json` keeps failing. Confirmed by reading the code | ⚠️ Warning | Button text only: Next still advances, and the done page uses `seen_device`. Does not block reaching a ready setup. One-line fix: move the `setButtonText` line back into `__init__` |
| gui/runner.py, tests/test_bridge.py, docs/ARCHITECTURE.md | 19 | WR-02: the 150 s `setup` limit leaves out the dotnet `--list-sdks` 60 s limits (find_dotnet and checks()), so the worst case is about 255 s | ⚠️ Warning | One spurious "didn't answer in 150 s" on a cold slow host; Retry succeeds because the probe pass was cached first. Kept as a human timing item |
| gui/app.py | 360, 366 | IN-03: a config value with leading/trailing whitespace counts as typed forever and is saved stripped | ℹ️ Info | a narrow CR-01 variant for such paths |
| gui/app.py | Port tab tooltip | IN-01: the device combo tooltip still says porter | ℹ️ Info | copy |
| gui/app.py | 343 | IN-02: hard-coded `#c62828` on the download-failure line | ℹ️ Info | theme |
| gui/firstrun.py | 487 | `DevicePage.pick` saves the device without a recheck, so the Setup tab's device field shows the old value until the next load | ℹ️ Info | display only: `save()` no longer writes an untouched field, so the saved device is never overwritten |

03-REVIEW-DISPOSITION.md reused the id WR-01 for the new device-page finding, so the row recording the old fetch.py WR-01 as fixed was dropped. The old finding is closed (reproduced above); this is a bookkeeping note only.

### Human Verification Required

See the `human_verification` frontmatter. These are the same items as last time, with the timing item updated to the 150 s limit: the fork-release.yml run (bare-PATH smoke, arm64 community NDK step), a real Linux arm64 host, a Finder and app-menu launch with a full port, a live `unauthorized` → `device` and `no permissions` device, distro adb 29.x, setup timing on a slow host, and the judgment-tier wizard prohibition.

### Gaps Summary

No gaps remain. CR-01 and WR-01 are fixed and their reproductions now pass. WR-03..WR-06 and T-03-35 are fixed too. The new device-page label regression (review WR-01) and the incomplete 150 s bound (WR-02) are warnings that do not stop a tester reaching a ready setup. They are worth a quick task before Phase 4. SC3 and SC5, and the live-device parts of SC4, can only be closed by the human items above.

---

_Verified: 2026-10-31T20:10:00Z_
_Verifier: Claude (gsd-verifier)_
