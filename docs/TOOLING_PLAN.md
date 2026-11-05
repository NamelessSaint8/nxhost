# Tooling and code quality — implementation plan

Status: draft (2026-11-03). Companion to the GUI milestone in `.planning/ROADMAP.md` and to
`docs/UNIVERSAL_SUPPORT_PLAN.md`. That plan covers *which games* port; the roadmap covers *the
GUI testers use*; this one covers **the cost of a port, the parity between its targets, the loop
that catches regressions, and the guards that stop classes of bug from returning.**

Written after the 2026-11-03 Rust assessment: the language is not the problem, so none of this
plan is a rewrite. Every item is either measurement, a missing guard, or glue between things that
already work.

**In GSD (2026-11-04):** T0–T7 are roadmap Phases 7–14, one phase per milestone T, with
requirements `QUAL-01`…`QUAL-12` in `.planning/REQUIREMENTS.md`. This document stays the plan of
record for *why* each phase exists; `.planning/ROADMAP.md` holds the goal, dependencies and
success criteria that `/gsd-plan-phase` consumes.

## What this plan owns

| Axis | Owner | Question it answers |
|---|---|---|
| Which games port | `docs/UNIVERSAL_SUPPORT_PLAN.md` (M0–M6) | "Does my title work?" |
| The tester's window | `.planning/ROADMAP.md` (Phases 3–6) | "Can a non-developer drive it?" |
| **The port itself** | **this plan (T0–T7)** | **"How long, on how many platforms, and why did it break?"** |

Explicitly not here: Rust, a packaging rewrite, notarization (personal use only), guest
Vulkan/GL replay (other plan), Switch 2 (deferred in the other plan).

## Evidence base (measured on this tree, 2026-11-03)

| Fact | Source | Consequence |
|---|---|---|
| The shader stage is **already parallel at core count**: `--jobs` defaults to `os.cpu_count() or 8`, exported as `J`, consumed by `dmsh_build.py`'s `ThreadPoolExecutor(NJ)` | `porter/cli.py:36`, `porter/childenv.py:12`, `dmsh_build.py:1274`, `build_ipa_from_nsp.py:2565` | Thread count is **not** the lever. My earlier "hardcoded 8" note was wrong for the porter path; it only bites direct invocation. |
| A cold Mac pack spent **~40 min of 1h50 on 23,133 shaders, 22,680 uncached** | `docs/` pack run, 2026-11-03 | The cold cache is the cost centre. Warm reuse is the only real lever, and it already works. |
| Rewriting `main` + `sdk` takes **seconds** (454k / 596k patch bytes) | same run | The rewriter is not a cost centre. Leave it in Python. |
| `porter` has **no Mac target**: `pipeline.py:297` pins `DM_TARGET='android'`; the Mac app exists only through `nxnative/scripts/build_ipa_from_nsp.py --platform mac-app` | `porter/pipeline.py`, `docs/ARCHITECTURE.md` | Two entry points, two stage/reuse models. This is the structural gap that matters most. |
| `porter` has **no save export/import** (no match for `save.*export|export.*save`) | `porter/*.py` | The one parity feature a player of the same title on phone and Mac actually wants does not exist. |
| **CI never compiles the C host**: `fork-ci.yml` runs the Python suite on 4 hosts; no NDK, no `compile_check` | `.github/workflows/fork-ci.yml` | Apple clang 21's implicit-declaration break was invisible until someone built on a Mac. A whole class of regression lives here. |
| `dm/host/Makefile` lists sources by hand (`SRC=main.c … text_store.c thread.c save_sync.c … $(wildcard hle_*.c)`); Android globs `host/*.c` | `nxnative/dm/host/Makefile:20`, `dm/android/build.py` | A new non-`hle_*` host source links on Android and fails on Mac. Another invisible-until-Mac class. |
| 450 test methods under `tests/`; 158 C/ObjC test files driven by Makefiles | `tests/`, `nxnative/dm/*/tests` | Verification exists, but the two halves are gated differently: one in CI, one only on a developer's machine. |
| Phase 3 UAT: 2 passed, 5 pending, 0 issues | `.planning/phases/03-…/03-UAT.md` | The GUI milestone is ahead of this axis; nothing here blocks it. |
| M2 of the support plan has begun (`--tool-device`, `DM_TOOL_DEVICE`) | `porter/cli.py:35`, `pipeline.py:102` | Do not restart it; this plan only measures what it costs. |

## Principles

1. **Measure, then optimise.** `porter` already emits per-event `rate`/`eta`; T0 turns that into a
   stage table before anyone optimises anything.
2. **One pipeline, two targets.** A target is a parameter and a stage list, never a second script.
3. **A guard per incident.** Every bug that cost a device session becomes a test, not a paragraph.
   The tree already does this in `tests/arch_rules.py`; this plan extends the habit.
4. **Upstream-first.** Anything under `nxnative/` is shared with the iOS host: fix there, offer
   upstream, keep the fork's delta to `porter/` glue.
5. **Cheap and reversible.** Each phase must be shippable alone, and droppable after its own
   measurement if the numbers don't justify it.

## Phases

### T0 — Make the port's cost visible (S)

Goal: a per-stage wall-clock table for a cold and a warm port of one title, with cache hit/miss
per cached stage, written to `<build>/logs/timings.tsv` and printed as one table at the end.

Tasks: consume the existing progress events in a `devtools/port_timing.py` (no pipeline change
beyond what `runlog` already records); label reused stages as reused; record host CPU, core count
and RAM next to the table.

- Minimum: cold and warm runs of one title recorded side by side.
- Complete: the same for three titles of different engines, so "cold" has a range.
- Verification: the table is quoted in the plan's follow-ups; no number in T1/T2 is asserted
  without one.

### T1 — The cold shader path (M)

Goal: a cold port's shader stage is predicted before it starts, capped so it cannot thrash a
tester's machine, and never recomputed when it need not be.

Tasks: (a) report the stage's work size (`n shaders, m cached`) and an ETA at stage start, from the
existing `shader_map`; (b) make `NJ` RAM-aware, not just core-aware — each worker is a .NET
process, so `min(cores, ram / per-worker footprint)` with the footprint measured in T0;
(c) investigate why a Mac pack compiled 22,680 of 23,133 with the Android chain's `shader_map`
present — is the MSL chain's reuse key different from the SPIR-V chain's? If yes, one key fix may
turn a cold 40 min into a warm few.

- Minimum: stage ETA and RAM cap; a warm re-pack is measurably warm.
- Complete: cross-target reuse either demonstrated or explained as impossible in a comment in
  `dmsh_build.py`.
- Droppable: if T0 shows the stage is already minimal on a warm run, ship (b) alone and stop.

### T2 — One entry point, two targets (M)

Status note (2026-11-04): the CLI half landed ahead of this plan, in a parallel session — `porter port --platform mac-app` exists (`cli.py:24`, `run_mac()` at `pipeline.py:464`), with a per-target work folder and `DM_TARGET='apple'`. Treat the tasks below as the review checklist for what landed, plus the GUI half, rather than as work still to start.

Goal: `python -m porter port --platform android|mac-app` produces what `--platform mac-app` of the
upstream script produces today, with the same stage reuse, logging and JSON events.

Tasks: a target descriptor (stage list, `DM_TARGET` value, packer, data layout) behind the existing
stage functions; reuse keys namespaced by target so an Android build never poisons a Mac one (the
modules are host-specific — `read_layout` refuses the wrong one); route to `dm/mac/pack_app.py`
for `mac-app`; `porter inspect` and the run log name the target; the GUI's Port view gains the
choice (coordinate with roadmap Phase 4, `PORT-01`/`PORT-02`).

- Minimum: Skyrim's `.app` rebuilds through `porter` from a warm build folder.
- Complete: a fresh folder to `.app` and to APK from one command, one log format, one reuse model.
- Risk: reuse-key collisions. Mitigation: namespace, and keep reading the old unprefixed keys so
  existing build folders stay usable.
- Sequencing note: land the CLI half before Phase 4 is planned, or the Port view gets built twice.

### T3 — Saves that move between devices (M)

Goal: `porter saves list|export|import` for both targets, so the same title continues on the phone
and on the Mac.

Facts this meets: Android saves live in app-internal storage and die with a reinstall; Mac saves
live in `~/Library/Application Support/nxnative/<title ID>`; neither has a way out today.

Tasks: enumerate and zip the save directory plus a manifest (title ID, module build ID, file list
with SHA-256, timestamp); import refuses a different build ID with a precise reason rather than
writing an unloadable save; Android import goes through adb into the app's own files directory
after the app has created it (the install already starts the app once for exactly this group
reason); Mac import copies into Application Support.

- Minimum: round-trip on the device — export, wipe, import, load in-game (the player's judgement,
  per the standing rule that gameplay is validated by hand).
- Complete: both directions between Y700 and Mac for one title, plus a mismatch refused cleanly.
- Deferred: cloud sync, automatic backup on install.

### T4 — Cross-host build health (M)

Goal: the C host cannot break on a host we ship to without CI saying so.

Tasks: (a) build `dm/host` for Apple and Android in CI on every PR — reuse
`nxnative/dm/ios/tools/compile_check.py` for the Apple side and the NDK path for the other;
(b) kill the Makefile drift: derive Mac `SRC` from the directory like Android does, or add a test
that compares `SRC` against `dm/host/*.c` and fails with the missing file named; (c) turn the
implicit-declaration class into a hard error for the host (clang 21 already does; pin
`-Werror=implicit-function-declaration` so older toolchains agree); (d) exercise the
`dmsh_chain.lock` refusal with a synthetic mismatch in a test, so the remedy text cannot rot.

- Minimum: a Mac and an Android host compile in CI, and a deliberate missing source fails with a
  name.
- Complete: the four bundle hosts and both runtime hosts are all built on every push.
- Risk: CI cost and Xcode availability on `macos-15`. Accept minutes; it is cheaper than the
  session the last break cost.

### T5 — One command that answers "is this still good?" (M)

Goal: `python devtools/verify.py` runs the three gates a host change needs and prints one verdict:
the unit suite, a re-port of one title per engine family against cached extraction, and a device
smoke (install, run 60 s, pull the log, assert no `[RED]` and no crash).

Tasks: compose existing pieces (`tests/`, `porter port` with warm caches, `devtools/`'s push and
log-pull scripts); make each gate skippable and loud about skipping; never invent a new device
path (the one-port lock and `device.json` already exist).

- Minimum: it runs on this Mac with the Y700 attached and takes under ~20 minutes warm.
- Complete: it is what runs before a `dm/host` or `dm/gfx` commit, and its output is quoted in
  commit bodies.
- Not in scope: device-loop classification (support plan M3, item 2).

### T6 — Guards, one per incident (S, continuous)

Each is small and each closes a class this repo has already paid for:

| Guard | Incident it locks out |
|---|---|
| A static rule in `tests/arch_rules.py`: every signal handler installed in `dm/host`/`dm/android` must pass `SA_ONSTACK` | The `DM_VK_PROF` frame landing on guest registers — two Skyrim crashes, one 30 minutes into a session |
| Android stubs must log "unimplemented" once instead of returning a plausible `0` (start with `mtl_pkg_stats`) | "packaged textures: first uploads 0" read as a failure and pursued as a lead |
| `android.tsv` with space-separated rows: parse it, and if the key contains whitespace say *"rows are tab-separated"* instead of `unknown key 'status  playable'` | Three suite failures from one `cat`-invisible tab |
| A test that every `dm/android` `gfx_vk_*` counter either is implemented or is named in a stub list | A zero counter is not evidence; make that structural, not folklore |

### T7 — Upstream cadence, kept cheap (S, continuous)

Goal: the 417-commit wall never happens again.

Tasks: the release workflow already reports the `nxnative/` diff; add a push-time warning when the
distance crosses a threshold, with the pick checklist (import, reconcile `porter/upstream.py`
rename guards, gate what Android cannot use, regression three titles) as the linked remedy;
exercise `devtools/nuget_pins.py` regeneration in CI so a pinned hash cannot go stale unnoticed.

- Minimum: distance is visible on every push and a threshold warn exists.
- Complete: after support-plan M0 lands, a scheduled small-batch pick (one upstream commit per
  cadence) with the same regression gate as T5.

## Sequencing

```
T0 ──┬─► T1 ─────────────┐
     ├─► T2 ──► (GUI Phase 4 needs T2)
     ├─► T3 ─────────────┤
     └─────────────────► T4 ─► T5
T6, T7: continuous, independent of the above
```

Sizes are relative, not calendar: T0 S, T1 M, T2 M, T3 M, T4 M, T5 M, T6 S-each, T7 S.
T2 and T3 both touch `porter/pipeline.py`; run them in one phase if only one person is working.

## Success metrics

| Metric | Today | Target |
|---|---|---|
| Cold port, one title, wall clock | ~1h50 (Mac app, shader-heavy) | predicted before it starts; no stage a surprise |
| Warm port, unchanged inputs | minutes | unchanged, and reused stages are labelled reused |
| Cold shader compiles, second run | 22,680 misses on a fresh chain | cache hit explained or fixed |
| `[RED]` lines and crashes in a device smoke | not measured | zero, enforced by T5 |
| Hosts whose C compiles in CI | Python only | Apple + Android + the four bundle hosts |
| Platforms a port can target from `porter` | Android | Android + Mac app |
| Cross-device saves | none | export/import round-trip for one title |
| Upstream distance | 417 commits (2026-11-03) | warned before it is a wall |

## Managed deferrals

| Deferred | Why | Revisit when |
|---|---|---|
| Rust anywhere in the pipeline or host | 2026-11-03 verdict: the cost centres are cache and parity, not the language | The goal changes to shipping to strangers, or contributors arrive who won't touch C |
| Replacing PyInstaller with a native bundle | Not the pain; the NDK and .NET downloads remain either way | An antivirus false positive costs a release |
| Notarization / DMG for the ported app | Personal use only | Never, unless distribution is decided |
| Guest Vulkan/GL replay | Other plan (M4/M5) | There |
| Save cloud sync | T3 needs local round-trip first | After T3 proves the format |

## Execution

One GSD phase per milestone — T0 is roadmap Phase 7 through T7 as Phase 14 (2026-11-04), each
with its goal, dependencies and success criteria already written into `.planning/ROADMAP.md` and
its requirements in `.planning/REQUIREMENTS.md`. T0 alone is small enough to fold into Phase 8's
phase if preferred, but it is numbered separately because Phase 8's plan quotes its numbers.
Every phase updates `docs/ARCHITECTURE.md` where it changes a contract, and `docs/PORT_STATUS.md`
only when a game-visible fact changes. The unit suite (450 methods) plus `devtools/verify.py`
(Phase 12) is the gate; no phase is "done" on a green suite alone if it touched the host.
