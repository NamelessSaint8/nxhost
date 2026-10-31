---
phase: "3"
slug: "host-toolchains-and-guided-first-run"
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: validated
nyquist_compliant: true
wave_0_complete: true
created: "2026-10-31"
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Python `unittest` (stdlib); PySide6 QtTest for GUI checks (offscreen, `fake_porter` bridge fixture) |
| **Config file** | none (discover over `tests/`); CI `.github/workflows/fork-ci.yml` |
| **Quick run command** | `.venv/bin/python -m unittest tests.test_setup tests.test_keys tests.test_hosttools tests.test_fetch tests.test_adb -v` |
| **Full suite command** | `QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover tests && .venv/bin/python tests/arch_rules.py` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run the touched test module(s), e.g. `.venv/bin/python -m unittest tests.test_adb -v`
- **After every plan wave:** Run the full suite command above
- **Before `/gsd-verify-work`:** Full suite green locally and on the `fork-ci.yml` matrix (four hosts and Python 3.11)
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

Filled in by the planner (2026-10-31). Each test module marked "created by" is written by the TDD task that first needs it, so the Wave 0 gaps below are closed inside the plans, not by a separate wave:

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 03-03-T1 | 03-03 | 2 | TOOL-01 | T-03-09 | linux-arm64 `plan()` picks the community NDK row; a hash mismatch names both hashes; no x86 platform-tools planned on arm64 | unit | `.venv/bin/python -m unittest tests.test_fetch.Pins tests.test_tls -v` | ✅ | ✅ green |
| 03-04-T1 | 03-04 | 2 | TOOL-01 | T-03-14, T-03-15 | Compile probe: ok / ENOEXEC / no exec bit / cached by clang path+mtime; runs with a timeout, no shell | unit | `.venv/bin/python -m unittest tests.test_probe tests.test_toolchain tests.test_hosttools -v` | ✅ | ✅ green |
| 03-04-T3 | 03-04 | 2 | TOOL-01 | — | `build.py` picks `linux-arm64` on aarch64 (rule parity with probe.host_folder; the real arm64 host build is VER-02) | unit | `.venv/bin/python -m unittest tests.test_probe -v` | ✅ | ✅ green |
| 03-08-T2 | 03-08 | 3 | TOOL-01 | T-03-25 | Real community NDK download + probe on the arm64 release runner | CI | `python packaging/smoke_bundle.py --community-ndk dist/nx2android` (fork-release.yml, linux-arm64) | ✅ | ⬜ CI run pending (local tests green) |
| 03-02-T2 | 03-02 | 1 | TOOL-02 | T-03-07 | DOTNET_ROOT from the `--list-sdks` path; dotnet children get `DOTNET_SYSTEM_GLOBALIZATION_INVARIANT=1` and a UTF-8 LANG; arm64 dotnet places | unit | `.venv/bin/python -m unittest tests.test_hosttools tests.test_porter.Env tests.test_stages -v` | ✅ | ✅ green |
| 03-03-T1 | 03-03 | 2 | TOOL-02 | — | `.NET` on linux-arm64 planned from its pin | unit | `.venv/bin/python -m unittest tests.test_fetch.Pins -v` | ✅ | ✅ green |
| 03-02-T3 | 03-02 | 1 | TOOL-03 | — | `adb version` parse (36.0.0, 29.0.6-debian, 1:10.0.0+r36, garbage) and push flags | unit | `.venv/bin/python -m unittest tests.test_hosttools -v` | ✅ | ✅ green |
| 03-06-T2 | 03-06 | 3 | TOOL-03 | — | push argv with and without `-Z` by adb version | unit | `.venv/bin/python -m unittest tests.test_adb -v` | ✅ | ✅ green |
| 03-04-T2, 03-06-T1 | 03-04, 03-06 | 2, 3 | TOOL-03 | T-03-16, T-03-21 | Distro family and fix commands from stub os-release dicts; nothing is run | unit | `.venv/bin/python -m unittest tests.test_distro -v` | ✅ | ✅ green |
| 03-02-T1 | 03-02 | 1 | TOOL-04 | T-03-06 | Bare-env `doctor --json` finds stub tools in known places (POSIX) | unit (subprocess) | `.venv/bin/python -m unittest tests.test_hosttools.BarePath -v` | ✅ | ✅ green |
| 03-08-T1 | 03-08 | 3 | TOOL-04 | — | Bare-env `doctor/setup --json` on the dev porter and the frozen bundle | unit + CI | `.venv/bin/python -m unittest tests.test_packaging -v`; `python packaging/smoke_bundle.py dist/nx2android` | ✅ | ✅ green (unit; CI half pending) |
| 03-05-T2, 03-12-T1, 03-12-T2, 03-10-T1, 03-10-T2, 03-11-T1, 03-11-T2 | 03-05, 03-12, 03-10, 03-11 | 2, 3, 4, 5 | FRUN-01 | T-03-17, T-03-18, T-03-19, T-03-32, T-03-35 | Wizard pages in order; keys page lists candidates; tools Cancel calls `stop`; device page polls and stops on leave | GUI (stand-in call_json, fake_porter) | `QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest tests.test_firstrun -v` | ✅ | ✅ green |
| 03-03-T2 | 03-03 | 2 | FRUN-01 | T-03-10, T-03-13 | Range resume accepts 206 only with `Content-Range: bytes <have>-`; a server ignoring Range restarts; 416 on a whole `.part`; a final mismatch deletes the `.part` and names both hashes | unit | `.venv/bin/python -m unittest tests.test_fetch -v` | ✅ | ✅ green |
| 03-01-T2 | 03-01 | 1 | FRUN-01 | T-03-01, T-03-02 | prod.keys check outputs key names and generation only, never a hex value; 1 MB cap | unit | `.venv/bin/python -m unittest tests.test_keys -v` | ✅ | ✅ green |
| 03-05-T1, 03-07-T1 | 03-05, 03-07 | 2, 3 | FRUN-02 | — | Not-ready doc → banner naming what is missing; Continue setup opens the wizard at the first not-ok step; both windows | GUI | `QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest tests.test_firstrun tests.test_shell -v` | ✅ | ✅ green |
| 03-05-T1, 03-07-T2 | 03-05, 03-07 | 2, 3 | FRUN-03 | — | `gui/firstrun.py` and `gui/shell.py` import only gui.runner (and gui.firstrun), PySide6 and the standard library; no file writes (03-05-T1 grep gate in wave 2, both arch rules in 03-07-T2) | arch rule | `.venv/bin/python tests/arch_rules.py` | ✅ | ✅ green |
| 03-01-T1 | 03-01 | 1 | FRUN-03 | T-03-05 | `setup --json` shape and `ready` per D-03 (legal, keys, NDK, .NET, signing key) | unit | `.venv/bin/python -m unittest tests.test_setup -v` | ✅ | ✅ green |
| 03-06-T1 | 03-06 | 3 | DEV-01 | T-03-20 | `devices()` parses every state, including `no permissions (…); see [...]` and `(no serial number)`; `devices --json` carries `detail` and `fix` | unit | `.venv/bin/python -m unittest tests.test_adb tests.test_distro tests.test_cli -v` | ✅ | ✅ green |
| 03-01-T3 | 03-01 | 1 | FRUN-01 | — | `desktop-entry --install` writes the Linux menu entry only from the Linux bundle; refuses symlinks and line breaks in the path | unit | `.venv/bin/python -m unittest tests.test_desktop -v` | ✅ | ✅ green |
| 03-09-T1 | 03-09 | 4 | TOOL-01, TOOL-03 | — | tools items carry pinned `download` {version, size} offline; no adb download on linux-arm64; device step carries adb facts | unit | `.venv/bin/python -m unittest tests.test_setup.ToolFacts tests.test_setup.Arm64 -v` | ✅ | ✅ green |
| 03-09-T2 | 03-09 | 4 | TOOL-02 | — | `tools --prepare` builds the translator and nx_extract once; without .NET SDK 10 it stops naming "Download missing tools" | unit | `.venv/bin/python -m unittest tests.test_prepare -v` | ✅ | ✅ green |
| 03-11-T3 | 03-11 | 5 | FRUN-01 | — | Setup tab cancel labels stop whichever view started the run; progress line; no license dialog | GUI | `QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest tests.test_bridge -v` | ✅ | ✅ green |
| 03-13-T1 | 03-13 (gap) | 1 | FRUN-01 | T-03-37 | A body that ends before its Content-Length (a clean close) is retried and resumed with Range, never hashed; real loopback socket (WR-01) | unit (loopback socket) | `.venv/bin/python -m unittest tests.test_fetch.EarlyClose -v` | ✅ (class created by the task) | ⬜ pending |
| 03-13-T2 | 03-13 (gap) | 1 | FRUN-01 | T-03-37 | A cut chunked answer (IncompleteRead) is retried; three short answers stop with the `.part` kept and no hash message (WR-01) | unit (loopback socket) | `.venv/bin/python -m unittest tests.test_fetch -v` | ✅ | ⬜ pending |
| 03-13-T3 | 03-13 (gap) | 1 | TOOL-01 | T-03-38, T-03-39 | Probe cache written through a per-process temp file, an unwritable cache never fails a check; fix text paths quoted (WR-03, WR-06) | unit | `.venv/bin/python -m unittest tests.test_probe tests.test_toolchain tests.test_hosttools -v` | ✅ | ⬜ pending |
| 03-14-T1 | 03-14 (gap) | 1 | TOOL-02, FRUN-01 | T-03-40 | No Prepare starts on a window that is quitting (WR-05); PREPARED constant | GUI (stand-in call_json) | `QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest tests.test_firstrun.Tools -v` | ✅ | ⬜ pending |
| 03-14-T2 | 03-14 (gap) | 1 | DEV-01 | — | Device page with no device keeps labels at natural height, steps on three lines, ok adb path hidden (UI top fix 1) | GUI | `QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest tests.test_firstrun.Device tests.test_firstrun.Wizard tests.test_firstrun.Done -v` | ✅ | ⬜ pending |
| 03-14-T3 | 03-14 (gap) | 1 | FRUN-02 | — | Checklist, failed() and banner colours from COLOUR; banner follows a palette change (UI top fix 3, IN-01) | GUI | `QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest tests.test_firstrun tests.test_shell -v` | ✅ | ⬜ pending |
| 03-15-T1 | 03-15 (gap) | 2 | FRUN-01 | T-03-41 | Wizard saves through porter config survive the Setup tab's Save and check; re-check reloads untouched fields; Save writes changed fields only (CR-01) | GUI (stand-in call_json) | `QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest tests.test_firstrun -v` | ✅ | ⬜ pending |
| 03-15-T2 | 03-15 (gap) | 2 | FRUN-01 | T-03-43 (and 03-11's T-03-35) | A second start on a running runner is refused; both buttons read Cancel from the start; one setup --json at a time (WR-04, WR-03) | GUI (fake_porter, stand-in call_json) | `QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest tests.test_bridge tests.test_firstrun tests.test_shell -v` | ✅ | ⬜ pending |
| 03-15-T3 | 03-15 (gap) | 2 | FRUN-03, TOOL-01 | T-03-42 | setup limit 150 s above the probe's two 60 s steps (WR-02); nx2android wording on the Setup tab and device list (UI top fix 2, in part); ledger recorded | GUI + suite | `QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover tests && .venv/bin/python tests/arch_rules.py` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [x] `tests/test_setup.py`, `tests/test_keys.py`, `tests/test_hosttools.py`, `tests/test_firstrun.py`
- [x] `tests/fixtures/bridge/fake_porter.py`: add `setup` (and `config … --json`) to `ONE_SHOT`; fixtures `setup_ready.json`, `setup_first.json`, `setup_missing.json`
- [x] synthetic prod.keys files with fake hex (never real keys), generated per test in temp folders by `tests/test_keys.py` `keyfile()` instead of a `tests/fixtures/keys/` folder
- [x] An `arch_rules.py` rule for `gui/firstrun.py` imports

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Community NDK download and compile probe on a real arm64 host | TOOL-01 | Needs a Linux arm64 machine and a 128 MB download | On `ubuntu-24.04-arm` or a tester's machine: `porter tools --download --only ndk && porter setup --json`; the NDK row is ok with the community note |
| Full port launched from Finder and from a desktop-menu entry | TOOL-04 | CI has no game files | `docs/RELEASE_CHECK.md` rows: launch the bundle from Finder (macOS) and from the `.desktop` entry (Linux), port a title, confirm every tool was found by absolute path |
| Frozen bundle bare-PATH smoke and community NDK step in `fork-release.yml` | TOOL-01, TOOL-04 | Needs a real release run (nothing pushed during execution) | Push and run `fork-release.yml`; the smoke step passes on every POSIX target and the linux-arm64 community NDK step passes |
| `unauthorized` → `device` live transition, Linux `no permissions` | DEV-01 | Needs a real tablet and USB | Plug a device with debugging not yet authorized; the wizard's device step shows the fix, then flips to `device` after accepting the prompt; on Linux without udev rules, the distro command is shown |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 30s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** validated 2026-10-31 by /gsd-validate-phase 03 (every automated command run green on macOS; CI-only commands await a fork-release.yml run)

## Validation Audit 2026-10-31

| Metric | Count |
|---|---|
| Gaps found | 0 |
| Resolved | 0 |
| Escalated | 0 |
