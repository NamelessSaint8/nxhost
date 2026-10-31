---
phase: "3"
slug: "host-toolchains-and-guided-first-run"
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: draft
nyquist_compliant: false
wave_0_complete: false
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
| 03-03-T1 | 03-03 | 2 | TOOL-01 | T-03-09 | linux-arm64 `plan()` picks the community NDK row; a hash mismatch names both hashes; no x86 platform-tools planned on arm64 | unit | `.venv/bin/python -m unittest tests.test_fetch.Pins tests.test_tls -v` | ✅ extend | ⬜ pending |
| 03-04-T1 | 03-04 | 2 | TOOL-01 | T-03-14, T-03-15 | Compile probe: ok / ENOEXEC / no exec bit / cached by clang path+mtime; runs with a timeout, no shell | unit | `.venv/bin/python -m unittest tests.test_probe tests.test_toolchain tests.test_hosttools -v` | ❌ created by the task | ⬜ pending |
| 03-04-T3 | 03-04 | 2 | TOOL-01 | — | `build.py` picks `linux-arm64` on aarch64 (rule parity with probe.host_folder; the real arm64 host build is VER-02) | unit | `.venv/bin/python -m unittest tests.test_probe -v` | ❌ created by 03-04-T1 | ⬜ pending |
| 03-08-T2 | 03-08 | 3 | TOOL-01 | T-03-25 | Real community NDK download + probe on the arm64 release runner | CI | `python packaging/smoke_bundle.py --community-ndk dist/nx2android` (fork-release.yml, linux-arm64) | ✅ extend | ⬜ pending |
| 03-02-T2 | 03-02 | 1 | TOOL-02 | T-03-07 | DOTNET_ROOT from the `--list-sdks` path; dotnet children get `DOTNET_SYSTEM_GLOBALIZATION_INVARIANT=1` and a UTF-8 LANG; arm64 dotnet places | unit | `.venv/bin/python -m unittest tests.test_hosttools tests.test_porter.Env tests.test_stages -v` | ❌ created by 03-02-T1 | ⬜ pending |
| 03-03-T1 | 03-03 | 2 | TOOL-02 | — | `.NET` on linux-arm64 planned from its pin | unit | `.venv/bin/python -m unittest tests.test_fetch.Pins -v` | ✅ extend | ⬜ pending |
| 03-02-T3 | 03-02 | 1 | TOOL-03 | — | `adb version` parse (36.0.0, 29.0.6-debian, 1:10.0.0+r36, garbage) and push flags | unit | `.venv/bin/python -m unittest tests.test_hosttools -v` | ❌ created by 03-02-T1 | ⬜ pending |
| 03-06-T2 | 03-06 | 3 | TOOL-03 | — | push argv with and without `-Z` by adb version | unit | `.venv/bin/python -m unittest tests.test_adb -v` | ✅ extend | ⬜ pending |
| 03-04-T2, 03-06-T1 | 03-04, 03-06 | 2, 3 | TOOL-03 | T-03-16, T-03-21 | Distro family and fix commands from stub os-release dicts; nothing is run | unit | `.venv/bin/python -m unittest tests.test_distro -v` | ❌ created by 03-04-T2 | ⬜ pending |
| 03-02-T1 | 03-02 | 1 | TOOL-04 | T-03-06 | Bare-env `doctor --json` finds stub tools in known places (POSIX) | unit (subprocess) | `.venv/bin/python -m unittest tests.test_hosttools.BarePath -v` | ❌ created by the task | ⬜ pending |
| 03-08-T1 | 03-08 | 3 | TOOL-04 | — | Bare-env `doctor/setup --json` on the dev porter and the frozen bundle | unit + CI | `.venv/bin/python -m unittest tests.test_packaging -v`; `python packaging/smoke_bundle.py dist/nx2android` | ✅ extend | ⬜ pending |
| 03-05-T2, 03-05-T3, 03-10-T1, 03-10-T2, 03-11-T1, 03-11-T2 | 03-05, 03-10, 03-11 | 2, 4, 5 | FRUN-01 | T-03-17, T-03-18, T-03-32, T-03-35 | Wizard pages in order; keys page lists candidates; tools Cancel calls `stop`; device page polls and stops on leave | GUI (stand-in call_json, fake_porter) | `QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest tests.test_firstrun -v` | ❌ created by 03-05-T1 | ⬜ pending |
| 03-03-T2 | 03-03 | 2 | FRUN-01 | T-03-10, T-03-13 | Range resume accepts 206 only with `Content-Range: bytes <have>-`; a server ignoring Range restarts; 416 on a whole `.part`; a final mismatch deletes the `.part` and names both hashes | unit | `.venv/bin/python -m unittest tests.test_fetch -v` | ✅ extend | ⬜ pending |
| 03-01-T2 | 03-01 | 1 | FRUN-01 | T-03-01, T-03-02 | prod.keys check outputs key names and generation only, never a hex value; 1 MB cap | unit | `.venv/bin/python -m unittest tests.test_keys -v` | ❌ created by the task | ⬜ pending |
| 03-05-T1, 03-07-T1 | 03-05, 03-07 | 2, 3 | FRUN-02 | — | Not-ready doc → banner naming what is missing; Continue setup opens the wizard at the first not-ok step; both windows | GUI | `QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest tests.test_firstrun tests.test_shell -v` | ❌ created by 03-05-T1 / 03-07-T1 | ⬜ pending |
| 03-05-T3, 03-07-T2 | 03-05, 03-07 | 2, 3 | FRUN-03 | — | `gui/firstrun.py` and `gui/shell.py` import only gui.runner (and gui.firstrun), PySide6 and the standard library; no file writes | arch rule | `.venv/bin/python tests/arch_rules.py` | ✅ extend | ⬜ pending |
| 03-01-T1 | 03-01 | 1 | FRUN-03 | T-03-05 | `setup --json` shape and `ready` per D-03 (legal, keys, NDK, .NET, signing key) | unit | `.venv/bin/python -m unittest tests.test_setup -v` | ❌ created by the task | ⬜ pending |
| 03-06-T1 | 03-06 | 3 | DEV-01 | T-03-20 | `devices()` parses every state, including `no permissions (…); see [...]` and `(no serial number)`; `devices --json` carries `detail` and `fix` | unit | `.venv/bin/python -m unittest tests.test_adb tests.test_distro tests.test_cli -v` | ✅ extend | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_setup.py`, `tests/test_keys.py`, `tests/test_hosttools.py`, `tests/test_firstrun.py`
- [ ] `tests/fixtures/bridge/fake_porter.py`: add `setup` (and `config … --json`) to `ONE_SHOT`; fixtures `setup_ready.json`, `setup_first.json`, `setup_missing.json`
- [ ] `tests/fixtures/keys/`: synthetic prod.keys files with fake hex (never real keys): complete, no header_key, only master keys, junk
- [ ] An `arch_rules.py` rule for `gui/firstrun.py` imports

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Community NDK download and compile probe on a real arm64 host | TOOL-01 | Needs a Linux arm64 machine and a 128 MB download | On `ubuntu-24.04-arm` or a tester's machine: `porter tools --download --only ndk && porter setup --json`; the NDK row is ok with the community note |
| Full port launched from Finder and from a desktop-menu entry | TOOL-04 | CI has no game files | `docs/RELEASE_CHECK.md` rows: launch the bundle from Finder (macOS) and from the `.desktop` entry (Linux), port a title, confirm every tool was found by absolute path |
| `unauthorized` → `device` live transition, Linux `no permissions` | DEV-01 | Needs a real tablet and USB | Plug a device with debugging not yet authorized; the wizard's device step shows the fix, then flips to `device` after accepting the prompt; on Linux without udev rules, the distro command is shown |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
