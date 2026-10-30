---
phase: "2"
slug: "porter-hardening"
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: "2026-10-30"
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Python `unittest` (stdlib); PySide6 QtTest for GUI checks (offscreen) |
| **Config file** | none (discover over `tests/`); CI `.github/workflows/fork-ci.yml` |
| **Quick run command** | `.venv/bin/python -m unittest tests.test_fetch tests.test_lock tests.test_stages -v` |
| **Full suite command** | `QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover -v tests && .venv/bin/python tests/arch_rules.py` |
| **Estimated runtime** | ~20 seconds (baseline 115 tests in 13.4 s, before this phase's new modules) |

---

## Sampling Rate

- **After every task commit:** Run the touched test module(s), e.g. `.venv/bin/python -m unittest tests.test_fetch -v`
- **After every plan wave:** Run `{full suite command}` above
- **Before `/gsd-verify-work`:** Full suite green locally and on `fork-ci.yml`'s five jobs (the Windows lock and env tests matter most)
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

Filled in by the planner per task. Requirement → test map from RESEARCH.md:

Task IDs are `<plan>-<task>`. Every test file marked "created by the task" is written by that task itself (tdd="true"), so no task waits on a separate Wave 0 scaffold.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 02-01-01 | 02-01 | 1 | HARD-04 | T-02-01 | Second port/install of the same build folder raises "already running" naming the holder; a dead holder frees the lock | integration | `.venv/bin/python -m unittest tests.test_lock -v` | created by the task | ⬜ pending |
| 02-01-02 | 02-01 | 1 | HARD-07 | T-02-02, T-02-03, T-02-04 | Crash mid data-pack swap leaves a working pack, recovered by the next build or install; the pushed pack holds no host path (build folder in the host-only `<App>-data.build` sidecar, D-14); MD5 in pieces | unit + subprocess | `.venv/bin/python -m unittest tests.test_datapack -v` | created by the task | ⬜ pending |
| 02-02-01 | 02-02 | 1 | HARD-02 | T-02-05, T-02-06, T-02-07 | New key 0600 and written whole; unreadable key refused, file untouched; two first ports one signer; APK via .partial | subprocess | `.venv/bin/python -m unittest tests.test_signing.Key -v` | created by the task | ⬜ pending |
| 02-02-02 | 02-02 | 1 | HARD-02 | T-02-06 | Broken key is a red required doctor row; port stops in require() | unit | `.venv/bin/python -m unittest tests.test_signing.Preflight -v` | extends 02-02-01's file | ⬜ pending |
| 02-02-03 | 02-02 | 1 | HARD-10 | — | One signer: the probe copy is gone, probeapp.c calls the committed mkapk.py | static | `.venv/bin/python -m unittest tests.test_signing.Probe -v` | extends 02-02-01's file | ⬜ pending |
| 02-03-01 | 02-03 | 1 | HARD-10 | T-02-08 | Hook bootstrap script (idempotent), README step, `*.code-workspace` ignored | unit | `.venv/bin/python -m unittest tests.test_housekeeping.Hooks -v` | created by the task | ⬜ pending |
| 02-03-02 | 02-03 | 1 | HARD-10 | T-02-10 | FLIP version recorded; arch_rules joins split literals; upstream output parsers pinned | unit/static | `.venv/bin/python -m unittest tests.test_housekeeping -v && .venv/bin/python tests/arch_rules.py` | extends 02-03-01's file | ⬜ pending |
| 02-03-03 | 02-03 | 1 | HARD-10 | T-02-09 | Ryujinx patch against Canary-1.3.351 reproduces the vendored tree | unit/static | `.venv/bin/python -m unittest tests.test_housekeeping.Records -v` | extends 02-03-01's file | ⬜ pending |
| 02-04-01 | 02-04 | 2 | PKG-07, HARD-08 | T-02-13, T-02-14, T-02-15 | Pinned URL + hash used; mismatch names both hashes and deletes the file; 404 → untested fallback (NDK stops); dialog shows (untested), escaped | unit + GUI offscreen | `.venv/bin/python -m unittest tests.test_fetch.Pins -v && QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest tests.test_bridge.Downloads -v` | created by the task | ⬜ pending |
| 02-04-02 | 02-04 | 2 | HARD-01 | T-02-11, T-02-12 | Crafted zip/tar (`..`, absolute, backslash, drive, escaping link, link-through-link, hardlink outside) refused, nothing written outside, partial unpack removed | unit | `.venv/bin/python -m unittest tests.test_fetch.Unpack -v` | extends 02-04-01's file | ⬜ pending |
| 02-04-03 | 02-04 | 2 | HARD-01 | T-02-12 | Python below 3.11.13 / 3.12.11 / 3.13.4 without the `ALLOW_MISSING` marker is refused by every command but doctor (D-13) | unit | `.venv/bin/python -m unittest tests.test_toolchain.PythonFloor -v` | created by the task | ⬜ pending |
| 02-05-01 | 02-05 | 2 | HARD-06 | T-02-16 | `os.environ` unchanged; absolute dotnet; env reaches nx_extract; `game.load` by path | unit | `.venv/bin/python -m unittest tests.test_porter.Env tests.test_porter.Experimental -v` | ✅ extend | ⬜ pending |
| 02-05-02 | 02-05 | 2 | HARD-06 | T-02-17 | Overrides named; a missing upstream attribute raises AssertionError naming it | unit | `.venv/bin/python -m unittest tests.test_porter.Overrides -v` | ✅ extend | ⬜ pending |
| 02-05-03 | 02-05 | 2 | HARD-09 | T-02-18 | Disk space counts base+updates+DLC (D-15), re-checked after extraction (other-volume output too) | unit | `.venv/bin/python -m unittest tests.test_porter.Misc -v` | ✅ extend | ⬜ pending |
| 02-06-01 | 02-06 | 3 | HARD-05 | T-02-19 | A stage killed mid-run (os._exit) is redone next run; keys written whole | integration | `.venv/bin/python -m unittest tests.test_stages -v` | created by the task | ⬜ pending |
| 02-06-02 | 02-06 | 3 | HARD-05 | T-02-19 | Every key via write_whole; cut-off profile copy recopied | integration | `.venv/bin/python -m unittest tests.test_stages tests.test_porter -v` | extends 02-06-01's file | ⬜ pending |
| 02-06-03 | 02-06 | 3 | HARD-05 | — | Marker names the stage and keeps the keys (D-09) | unit | `.venv/bin/python -m unittest tests.test_runlog -v` | ✅ extend | ⬜ pending |
| 02-07-01 | 02-07 | 3 | TEST-01 | T-02-22 | CLI error paths return named errors, not tracebacks (incl. tools --only bogus); devtools device precedence | subprocess | `.venv/bin/python -m unittest tests.test_cli -v` | created by the task | ⬜ pending |
| 02-07-02 | 02-07 | 3 | TEST-01 | T-02-21 | adb sizes, push resume, stale cleanup in batches of 64 inside the pack's folders, replace-signer | unit | `.venv/bin/python -m unittest tests.test_adb -v` | created by the task | ⬜ pending |
| 02-07-03 | 02-07 | 3 | TEST-01 | — | Per-OS toolchain detection order, SDK roots, user_dir | unit | `.venv/bin/python -m unittest tests.test_toolchain -v` | extends 02-04-03's file | ⬜ pending |
| 02-08-01 | 02-08 | 4 | HARD-03, PKG-07 | T-02-23, T-02-24 | FPSLocker config at the pinned commit, head fallback flagged; commit + sha256 in log and `fpslock.tsv`; cache written whole | unit | `.venv/bin/python -m unittest tests.test_porter.FpsLocker tests.test_tls -v` | ✅ extend | ⬜ pending |
| 02-08-02 | 02-08 | 4 | HARD-03 | — | ARCHITECTURE.md documents the pin | static | `grep -c "FPSLOCKER" docs/ARCHITECTURE.md` | n/a | ⬜ pending |
| 02-09-01 | 02-09 | 4 | HARD-10 | — | One language list: inspect `languages` from nacp; GUI box filled from it | unit + GUI offscreen | `.venv/bin/python -m unittest tests.test_cli.Languages -v && QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest tests.test_bridge.Escaping -v` | ✅ extend | ⬜ pending |
| 02-09-02 | 02-09 | 4 | HARD-08 | T-02-26 | Game card strings escaped in rich text; system fixed font | GUI offscreen | `QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest tests.test_bridge -v` | ✅ extend | ⬜ pending |
| 02-10-01 | 02-10 | 5 | PKG-07 | T-02-28, T-02-SC | NuGet content hash (`obj/project.assets.json` `sha512`, D-05 as amended) of every restored package checked against pins before the build; a re-signed package still passes; bad package removed | unit | `.venv/bin/python -m unittest tests.test_nuget -v` | created by the task | ⬜ pending |
| 02-10-02 | 02-10 | 5 | PKG-07, HARD-04 | T-02-29 | Shared tool builds wait on one lock; translator and survey builds checked | integration | `.venv/bin/python -m unittest tests.test_lock tests.test_nuget -v` | ✅ extend | ⬜ pending |
| 02-10-03 | 02-10 | 5 | (SC 5) | — | CONCERNS.md closure table, one row per concern | static | `grep -c "## Closure (Phase 2)" .planning/codebase/CONCERNS.md` | n/a | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Each new test file is created by the first task that needs it (no separate scaffold wave):

- [ ] `tests/test_fetch.py` — Pins, Unpack (02-04-01, 02-04-02); NuGet moved to `tests/test_nuget.py` (02-10-01, temp project.assets.json built in the test, no fixture file)
- [ ] `tests/test_lock.py` (02-01-01; wait mode 02-10-02)
- [ ] `tests/test_datapack.py` — Swap (with the no-host-path check, D-14), chunked MD5 (02-01-02)
- [ ] `tests/test_stages.py` — CutOff (02-06-01)
- [ ] `tests/test_signing.py` — tiny `.so` fixture; one key generated in `setUpClass` (02-02-01)
- [ ] `tests/test_housekeeping.py` (02-03-01)
- [ ] `tests/test_adb.py` (02-07-02)
- [ ] `tests/test_toolchain.py` — PythonFloor (02-04-03), Detection (02-07-03)
- [ ] `tests/test_cli.py` (02-07-01; Languages 02-09-01)
- [ ] Every new module sets `NX2A_HOME` to a temp dir at import and follows `tests/test_porter.py`'s lz4/CI skip guard (stdlib-only modules: test_toolchain, test_housekeeping, test_signing need no guard)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Windows byte-range lock blocks a second porter but lets it read the holder | HARD-04 | Needs a Windows host; covered by the `windows-2025` CI job, not local macOS runs | Check `tests.test_lock` passes on the Windows job of `fork-ci.yml` |
| Windows `env` cannot override PATH lookup; absolute tool paths used | HARD-06 | Windows-only behaviour | Check `tests.test_porter.Env` passes on the Windows job of `fork-ci.yml` |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
