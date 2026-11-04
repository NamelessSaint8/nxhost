# Phase 11: Compile the C host in CI - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-11-04
**Phase:** 11-compile-the-c-host-in-ci
**Areas discussed:** Target choice, Failing target, UI control, Profile without android.tsv, CI policy, Non-Mac hosts, Run order, Shared work, Result view

---

## Target choice

| Option | Description | Selected |
|--------|-------------|----------|
| CI compiles both; the UI choice filed for Phase 9/4 | Phase 11 stays CI-only; the GUI choice lands later | |
| Deliver one-or-both end to end in this phase | `--platform both` in porter plus the GUI checkboxes, on top of the CI job | ✓ |
| Split it: CI now, a new phase for the UI choice | Insert a separate phase after 11 | |

**User's choice:** Deliver one-or-both end to end in this phase
**Notes:** The user's framing was "choose one or both from the UI and base the compilation off of those choices" — the choice drives the work rather than the CI job defining scope. This absorbs Phase 9's GUI half (QUAL-07) and adds QUAL-13.

---

## Failing target

| Option | Description | Selected |
|--------|-------------|----------|
| Report per target, exit non-zero if any failed | Other target still runs; per-target results; non-zero exit on any failure | ✓ |
| Abort on the first failing target | Stop at first failure | |
| Succeed if either target built | Exit 0 if one package exists | |

**User's choice:** Report per target, exit non-zero if any failed
**Notes:** A working APK must not be discarded because the Metal chain failed; a green run must not hide a broken target.

---

## UI control

| Option | Description | Selected |
|--------|-------------|----------|
| Two checkboxes, host-appropriate default | Android / Mac app, both allowed; macOS defaults to Mac app, else Android | ✓ |
| Three-way radio: Android, Mac app, Both | Single control, three states | |
| CLI only this phase | No GUI change | |

**User's choice:** Two checkboxes, host-appropriate default

---

## Profile without android.tsv

| Option | Description | Selected |
|--------|-------------|----------|
| Skip Android with the reason | Mac app still built; reason named | ✓ |
| Refuse both, offer Mac app only | Strictest | |
| Port Android experimentally too | Provisional/derived profile | |

**User's choice:** Skip Android with the reason
**Notes:** 52 of 54 upstream profiles have no `android.tsv`, so "refuse" would break "both" for nearly every game.

---

## CI policy

| Option | Description | Selected |
|--------|-------------|----------|
| Blocking, per-target jobs, path-filtered | apple and android jobs, `nxnative/**` and `.github/**` | ✓ |
| Blocking on every push | No path filters | |
| Informational first, then blocking | Advisory for a while | |

**User's choice:** Blocking, per-target jobs, path-filtered

---

## Non-Mac hosts

| Option | Description | Selected |
|--------|-------------|----------|
| Disable it with the reason | Mac checkbox greyed off darwin | ✓ |
| Allow it, let it fail as a target | Runs and reports failure | |
| CLI skips it, GUI greys it | Split rule | |

**User's choice:** Disable it with the reason
**Notes:** `pipeline.py` already refuses a Mac app off darwin; the GUI should not offer what cannot be built.

---

## Run order

| Option | Description | Selected |
|--------|-------------|----------|
| Android first, then Mac | Cheap chain first, so environment failures surface fast | ✓ |
| Mac first, then Android | Warms the Metal cache early | |
| Both at once | Concurrent | |

**User's choice:** Android first, then Mac

---

## Shared work

| Option | Description | Selected |
|--------|-------------|----------|
| Share extract and split, split only target stages | One extraction, one shader split, per-target stages | ✓ |
| Each target fully independent | Duplicate extraction per target | |

**User's choice:** Share extract and split, split only the target stages

---

## Result view

| Option | Description | Selected |
|--------|-------------|----------|
| Per-target rows in one result | Additive `result` list; one row per target with Reveal | ✓ |
| Queue two ordinary runs | Two runs, two results, two logs | |

**User's choice:** Per-target rows in one result

---

## Agent's Discretion

- Warnings strictness (`-Werror=implicit-function-declaration` on host/gfx; not full `-Werror`).
- CI's profile (`GAME=01000A10041EA000`, the committed Skyrim profile).
- Apple compile depth (per-file `-c` first, link if cheap).
- The `SRC` drift guard as a test comparing the Makefile list against the directory.
- The `dmsh_chain.lock` refusal test with a synthetic mismatch.
- Off-Mac CLI treatment of a Mac target: skipped, never failed.

## Deferred Ideas

- Per-game remembered target choice — Phase 4 (library settings).
- Concurrent two-target run.
- A `porter doctor` row for Xcode/Metal against `dmsh_chain.lock`.
- The device smoke loop over both packages — Phase 12.
