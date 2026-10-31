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

Filled in by the planner per task. Requirement → test map from 03-RESEARCH.md §Validation Architecture:

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| TBD | TBD | TBD | TOOL-01 | — | linux-arm64 `plan()` picks the community NDK row; a hash mismatch names both hashes; no x86 platform-tools planned on arm64 | unit | `.venv/bin/python -m unittest tests.test_fetch -v` | ✅ extend | ⬜ pending |
| TBD | TBD | TBD | TOOL-01 | — | Compile probe: ok / ENOEXEC / no exec bit / cached by clang path+mtime; runs with a timeout, no shell | unit | `.venv/bin/python -m unittest tests.test_hosttools -v` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | TOOL-01 | — | `build.py` picks `linux-arm64` on aarch64 | integration (Linux aarch64 only) | `python -m unittest tests.test_hosttools.BuildHost` on `ubuntu-24.04-arm` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | TOOL-02 | — | `_dotnet_rid()` → linux-arm64; DOTNET_ROOT from the `--list-sdks` path; dotnet children get `DOTNET_SYSTEM_GLOBALIZATION_INVARIANT=1` | unit | `.venv/bin/python -m unittest tests.test_toolchain tests.test_stages -v` | ✅ extend | ⬜ pending |
| TBD | TBD | TBD | TOOL-03 | — | `adb version` parse (36.0.0, 29.0.6-debian, 1:10.0.0+r36, garbage); push argv with and without `-Z` | unit | `.venv/bin/python -m unittest tests.test_adb -v` | ✅ extend | ⬜ pending |
| TBD | TBD | TBD | TOOL-03 | — | Distro family and fix commands from stub os-release dicts | unit | `.venv/bin/python -m unittest tests.test_hosttools -v` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | TOOL-04 | — | Bare-env `doctor/setup --json` finds stub tools in known places (POSIX) | unit (subprocess) | `.venv/bin/python -m unittest tests.test_hosttools.BarePath -v` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | TOOL-04 | — | Frozen bundle bare-env smoke | CI | `python packaging/smoke_bundle.py dist/nx2android` | ✅ extend | ⬜ pending |
| TBD | TBD | TBD | FRUN-01 | — | Wizard pages in order; keys page lists candidates; tools Cancel calls `stop`; device page polls and stops on leave | GUI (fake_porter) | `QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest tests.test_firstrun -v` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | FRUN-01 | — | Range resume accepts 206 only with `Content-Range: bytes <have>-`; a server ignoring Range restarts; 416 on a whole `.part`; a final mismatch deletes the `.part` and names both hashes | unit | `.venv/bin/python -m unittest tests.test_fetch -v` | ✅ extend | ⬜ pending |
| TBD | TBD | TBD | FRUN-01 | — | prod.keys check outputs key names and generation only, never a hex value; 1 MB cap | unit | `.venv/bin/python -m unittest tests.test_keys -v` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | FRUN-02 | — | Not-ready doc → banner naming what is missing; Continue setup opens the wizard at the first not-ok step | GUI | `QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest tests.test_firstrun -v` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | FRUN-03 | — | `gui/firstrun.py` imports only `gui.runner` and PySide6, no `porter.config`, no file writes | arch rule | `.venv/bin/python tests/arch_rules.py` | ✅ extend | ⬜ pending |
| TBD | TBD | TBD | FRUN-03 | — | `setup --json` shape and `ready` per D-03 (legal, keys, NDK, .NET, signing key) | unit | `.venv/bin/python -m unittest tests.test_setup -v` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | DEV-01 | — | `devices()` parses every state, including `no permissions (…); see [...]` and `(no serial number)`; `devices --json` carries `fix` | unit | `.venv/bin/python -m unittest tests.test_adb tests.test_cli -v` | ✅ extend | ⬜ pending |

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
