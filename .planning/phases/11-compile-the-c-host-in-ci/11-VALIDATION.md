---
phase: 11
slug: compile-the-c-host-in-ci
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: "2026-11-04"
---

# Phase 11 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Derived from `11-RESEARCH.md` § "Validation Architecture".

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Python `unittest` (stdlib). No pytest, no config file |
| **Config file** | none — "discovery is controlled by the command line" (`.planning/codebase/TESTING.md:15`) |
| **Quick run command** | `python -m unittest tests.test_porter tests.test_bridge tests.test_architecture` |
| **Full suite command** | `python -m unittest discover -v tests`, then `python tests/arch_rules.py` for the per-check PASS/FAIL list |
| **Estimated runtime** | ~60 s quick; ~2 min full suite on the four-host matrix |

---

## Sampling Rate

- **After every task commit:** Run the quick run command, < 60 s.
- **After every plan wave:** Run the full suite.
- **Before `$gsd-verify-work`:** Full suite green **and** both `host-build.yml` jobs green on a push that touches `nxnative/**`.
- **Max feedback latency:** 60 seconds per task.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 11-01-01 | 01 | 1 | QUAL-13 | — | N/A | unit (argv + driver with fakes) | `python -m unittest tests.test_porter.Both` | ❌ W0 | ⬜ pending |
| 11-01-02 | 01 | 1 | QUAL-13 | — | N/A | unit (`run_both` with a child raising `BuildError`) | `python -m unittest tests.test_porter.Both` | ❌ W0 | ⬜ pending |
| 11-01-03 | 01 | 1 | QUAL-13 | — | N/A | unit (fake profile dir) | `python -m unittest tests.test_porter.Both` | ❌ W0 | ⬜ pending |
| 11-01-04 | 01 | 1 | QUAL-13 | — | N/A | unit (`mock.patch('sys.platform', ...)`) | `python -m unittest tests.test_porter.Both` | ❌ W0 | ⬜ pending |
| 11-02-01 | 02 | 2 | QUAL-07 | — | N/A | unit (construct `PortTab`, click) | `python -m unittest tests.test_bridge` | ⚠️ extend | ⬜ pending |
| 11-02-02 | 02 | 2 | QUAL-07 | — | N/A | replay | `python -m unittest tests.test_bridge.Replay.test_port_both` | ❌ W0 | ⬜ pending |
| 11-03-01 | 03 | 1 | QUAL-09 | — | N/A | static | `python tests/arch_rules.py` (via `tests.test_architecture`) | ❌ W0 | ⬜ pending |
| 11-03-02 | 03 | 1 | QUAL-09 | — | N/A | unit (patched `LOCK` + `tools_now`) | `python -m unittest tests.test_tool_lock` | ❌ W0 | ⬜ pending |
| 11-03-03 | 03 | 1 | QUAL-09 | — | N/A | CI job | `host-build.yml` (no local command needed) | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_porter.py` — a `Both` class (order, skip-on-no-android.tsv, skip-off-darwin, failure isolation, exit code); the file already boots `pipeline.Port(pipeline.Options(...))` with no game files (`MacTarget.test_platform_option_reaches_the_port`)
- [ ] `tests/test_bridge.py` — `Replay.test_port_both` + a `PortTab` Targets-row test; `tests/fixtures/bridge/port_both.jsonl` generated from `record.py` (add a `BOTH` stage list and an `emit_result` with `targets[]`)
- [ ] `tests/test_tool_lock.py` — synthetic lock mismatch; needs `tool_lock.main(argv)` to exist
- [ ] `tests/arch_rules.py` — the `SRC` drift `check()` (no new file)
- [ ] `.github/workflows/host-build.yml` — the two jobs
- [ ] Framework install: none (stdlib `unittest`, already in `requirements.txt`'s environment)

*If none: "Existing infrastructure covers all phase requirements."*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| GUI shows two checkboxes, Mac disabled off macOS | QUAL-07 | Platform-dependent widget state; the headless suite can't exercise the real display on all four hosts | Run the GUI on each host, confirm the Targets row's default and the Mac box's disabled state and reason note |
| `host-build.yml` jobs are actually "blocking" | QUAL-09 | Branch protection lives in GitHub settings, not the repo | List the two jobs as required checks on `main`; confirm a matching push fails the PR |
| Two-target run on a real Mac produces both packages | QUAL-13 | Needs Xcode and a real game folder | `porter port "<folder>" --platform both` on macOS; expect the APK and the `.app`, two result rows |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
