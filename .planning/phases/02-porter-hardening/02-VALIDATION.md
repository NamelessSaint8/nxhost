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

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| TBD | TBD | TBD | HARD-01 | zip-slip | Crafted zip/tar (`..`, absolute, backslash, drive, escaping link, link-through-link, hardlink outside) refused, nothing written outside, partial unpack removed | unit | `.venv/bin/python -m unittest tests.test_fetch.Unpack -v` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | HARD-01 | tar filter bypass | Python below 3.11.13 / 3.12.11 / 3.13.4 without the `ALLOW_MISSING` marker is refused | unit + subprocess | `.venv/bin/python -m unittest tests.test_toolchain.PythonFloor -v` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | HARD-02 | key disclosure / key loss | New key 0600 and written whole; unreadable key stops porter, file untouched | subprocess | `.venv/bin/python -m unittest tests.test_signing -v` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | HARD-03 | moving-branch config | FPSLocker config pinned to a commit; sha256 in log and `fpslock.tsv` | unit | `.venv/bin/python -m unittest tests.test_porter.FpsLocker -v` | ✅ extend | ⬜ pending |
| TBD | TBD | TBD | HARD-04 | concurrent writers | Second port/install of the same folder raises "already running" | integration | `.venv/bin/python -m unittest tests.test_lock -v` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | HARD-05 | — | Stage cut off mid-write is redone next run | integration | `.venv/bin/python -m unittest tests.test_stages -v` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | HARD-06 | — | `os.environ` unchanged; `game.load` by path; overrides asserted at import | unit | `.venv/bin/python -m unittest tests.test_porter.Env -v` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | HARD-07 | — | Crash during data-pack swap leaves a working pack | unit | `.venv/bin/python -m unittest tests.test_stages.DataPack tests.test_adb -v` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | HARD-08 | markup injection | Game names and network strings escaped in rich text; system fixed font | GUI offscreen | `QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest tests.test_bridge.Escaping -v` | ✅ extend | ⬜ pending |
| TBD | TBD | TBD | HARD-09 | — | Disk space counts base+updates+DLC, re-checked after extraction | unit | `.venv/bin/python -m unittest tests.test_porter.Misc.test_disk_space -v` | ✅ extend | ⬜ pending |
| TBD | TBD | TBD | HARD-10 | — | Repo housekeeping items closed | unit/static | `.venv/bin/python -m unittest tests.test_porter.Housekeeping -v` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | PKG-07 | supply chain | Pinned URL + hash used; mismatch names both hashes and deletes the file; NuGet contentHash checked before build | unit | `.venv/bin/python -m unittest tests.test_fetch.Pins tests.test_fetch.NuGet -v` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | TEST-01 | — | adb push/resume, stale cleanup, replace-signer | unit | `.venv/bin/python -m unittest tests.test_adb -v` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | TEST-01 | — | Per-OS toolchain detection order | unit | `.venv/bin/python -m unittest tests.test_toolchain -v` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | TEST-01 | — | CLI error paths return named errors, not tracebacks | subprocess | `.venv/bin/python -m unittest tests.test_cli -v` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_fetch.py` — Unpack, Pins, NuGet (+ fixture `tests/fixtures/nuget/project.assets.json`)
- [ ] `tests/test_lock.py`
- [ ] `tests/test_stages.py` — cut-off, DataPack
- [ ] `tests/test_signing.py` — tiny `.so` fixture; one key generated in `setUpClass`
- [ ] `tests/test_adb.py`
- [ ] `tests/test_toolchain.py`
- [ ] `tests/test_cli.py`
- [ ] Every new module sets `NX2A_HOME` to a temp dir at import and follows `tests/test_porter.py`'s lz4/CI skip guard

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
