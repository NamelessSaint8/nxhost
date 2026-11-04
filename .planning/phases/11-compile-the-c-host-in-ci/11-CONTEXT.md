# Phase 11: Compile the C host in CI - Context

**Gathered:** 2026-11-04
**Status:** Ready for planning

<domain>
## Phase Boundary

Two things, because the discussion joined them:

1. **The target is the user's choice, one or both.** `porter` gains a two-target run (`--platform both` or equivalent) that produces an APK and a Mac app from one game folder, and the GUI offers the choice as two checkboxes with a host-appropriate default. The two chains share extraction and the shader split and run Android first.
2. **CI compiles the C host, per target.** Every push that touches `nxnative/**` or `.github/**` compiles `dm/host` for Apple arm64 and for Android arm64 as two blocking jobs, so a break names its target on the push that caused it.

This absorbs the GUI half of Phase 9 (requirement QUAL-07, "the Port view offers the target") and adds QUAL-13 (one run, two packages). Phase 9 keeps its CLI half, which already landed. Out of scope: the device smoke loop (Phase 12), upstream cadence (Phase 14), a per-game saved target preference (Phase 4's library), and running the two chains concurrently.

</domain>

<decisions>
## Implementation Decisions

### The choice itself
- **D-01:** The target is the user's choice — Android, the Mac app, or both — from the CLI and from the GUI, and the work done follows that choice. Compilation is never fixed to one target in the pipeline. — **Reversibility:** costly — once `--platform both` is in the CLI, the JSON protocol and the GUI depend on it; withdrawing it means deprecating a documented flag and a control, not just deleting a branch.
- **D-02:** Two checkboxes in the Port view (Android, Mac app), both allowed, **defaulting to what suits the host**: on macOS the Mac app is ticked, everywhere else Android is. No zero-target state is reachable. The remembered-per-game form of this is Phase 4's business, not this phase's.
- **D-03:** On Windows and Linux the Mac app checkbox is **disabled with the reason** (a Mac app is built on a Mac; `pipeline.py` already refuses off `darwin`). The GUI never offers a target that cannot be built on that host.

### What a two-target run does
- **D-04:** Run **Android first, then the Mac app**. Android is the cheap chain, so a broken toolchain or profile fails in minutes instead of after the twenty-plus-minute Metal chain.
- **D-05:** The two chains **share extraction and the shader split**; only target-specific stages run per target (the rewrite with its `DM_TARGET`, the Vulkan vs Metal shader build, the host compile, the pack), in the existing `work/android` and `work/mac` folders.
- **D-06:** A failing target does **not** stop the other. The run reports **per-target results** (built / failed / skipped, with the reason) and exits non-zero if any target failed. A working APK is never discarded because the Metal chain was unhappy. — **Reversibility:** costly — the exit-code contract and the result shape are what a script or a tester reads; changing it later breaks callers silently.
- **D-07:** A profile with no `android.tsv` (52 of 54 upstream profiles have none) is **skipped for Android with the reason named**, and the Mac app is still built. No provisional profile is invented and no experimental Android build starts implicitly.
- **D-08:** One run produces **one result** whose JSON `result` event gains a per-target list (platform, output path, ok/failed/skipped, reason); the Port view draws one row per target with its own Reveal, and the run log names both. A single-target run keeps today's shape, so the golden bridge fixtures stay valid. — **Reversibility:** costly — `tests/fixtures/bridge/` goldens and `gui/runner.py` parse this; a rename would break the protocol tests and any saved log reader.

### CI
- **D-09:** Two **blocking** compile jobs, one per target (apple, android), **path-filtered** to `nxnative/**` and `.github/**` so documentation-only pushes skip them. A failure names its target.

### the agent's Discretion
Not discussed — follow these defaults, and surface anything rated one-way as a `checkpoint:decision`:
- **Warnings strictness:** `-Werror=implicit-function-declaration` for `dm/host` and `dm/gfx` on the Apple job (the class that bit Apple clang 21); the Android job keeps the NDK's defaults plus the same flag. Full `-Werror` is out — it would pull other phases' work in.
- **The profile CI builds against:** a committed one (`01000A10041EA000`, Skyrim) via `GAME=`, since `dm/host/Makefile` refuses to build without a profile and all 142 profiles are data in the tree. No fixture profile unless the committed one proves unstable.
- **Compile depth on Apple:** per-file `-c` like `nxnative/dm/ios/tools/compile_check.py` first, then link the `dmhost` binary if it is cheap — linking is what catches a source missing from the Makefile's hand-listed `SRC`.
- **The `SRC` drift guard:** a test that compares `dm/host/SRC` against `dm/host/*.c` and names any file that would link on Android (which globs) but not on Mac. Cheaper and more precise than waiting for a link failure.
- **The `dmsh_chain.lock` refusal test:** a synthetic mismatch fed to `tool_lock.py`, asserting the remedy text and exit, so the message cannot rot.
- **Off-Mac CLI behaviour for a Mac target:** skipped with the reason, never a failed target.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Scope and requirements
- `.planning/ROADMAP.md` §Phase 11 (goal and success criteria), §Phase 9 (its CLI half is done; its GUI half is now here), §Phase 4 (the library's per-game settings, which inherit D-02 later)
- `.planning/REQUIREMENTS.md`: QUAL-07, QUAL-09, QUAL-13 (the exact wording), and QUAL-06 for the existing single-target contract
- `docs/TOOLING_PLAN.md` §T4 — the plan of record for this phase, including why CI never compiling the host is a class of bug rather than one incident

### Existing code the phase builds on
- `porter/pipeline.py` — `Port.run()` (Android stages), `run_mac()` (~line 464), `self.mac`, `self.aw = work/('mac'|'android')` (~line 176), the `DM_TARGET` rewrite (~line 321), the permitted-platform check (~line 91) and the `darwin` refusal (~line 466)
- `porter/cli.py` — the `port` parser: `--platform` choices (~line 24), `--allow-other-metal` (~line 38), `--jobs` default (~line 36)
- `gui/runner.py` and `gui/app.py` — the `PortTab` that would carry the two checkboxes; the JSON-lines event contract
- `tests/fixtures/bridge/` — the golden streams that pin the protocol a per-target `result` must extend additively
- `nxnative/dm/ios/tools/compile_check.py` — the existing per-file compile check, documented as "CI's iOS build check"; derives its source list from `make -n`
- `nxnative/dm/host/Makefile` — the profile requirement (`GAME`), the hand-listed `SRC` (~line 20) and the wildcard `GFX` (~line 23)
- `nxnative/dm/android/build.py` — the NDK host build (`--lib`, `--jobs`), what the Android CI job drives
- `.github/workflows/fork-ci.yml` — the four-host matrix, action pinning, no-secrets rule this phase extends
- `nxnative/dm/android/tools/android_profile.py` — the `android.tsv` keys, i.e. what "has an Android profile" means for D-07

### Rules and docs to keep in step
- `docs/ARCHITECTURE.md` §"The port" and the Distribution row — the stage table and platform split the two-target run changes
- `.planning/codebase/TESTING.md` — unittest conventions, `NX2A_HOME` isolation
- `tests/arch_rules.py` — the layer rules (no game-specific code in `dm/android`, profiles are data only)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `compile_check.py` already turns `make -n` output into a per-file compile list with `GAME` set — the Apple job is largely this script with `MSL_SDK=macosx` instead of `iphoneos`.
- `Port.run()` and `Port.run_mac()` are already separate stage sequences with separate work folders, so a two-target run is a driver over them, not a rewrite.
- `PROG.stage()` / the `stage_end` and `result` events already carry enough structure for per-target reporting; `gui/runner.py` already parses them into signals.
- `tests/fixtures/bridge/record.py` regenerates goldens from porter's own emitter, so extending `result` is a fixture regeneration plus a GUI assertion, not hand-written JSON.

### Established Patterns
- The pipeline is a straight-line sequence of `PROG.stage()` calls with per-stage reuse keys written last and whole; a two-target run must keep that discipline per target.
- Additive protocol changes only, no version field (Phase 1's decision).
- `[RED] ` prefix for anything unimplemented or refused; English logs; the why in the comment.
- CI actions pinned by SHA, no secrets in the test matrix, `fail-fast: false` so one host's failure does not hide another's.

### Integration Points
- `porter/cli.py` `--platform` gains its third value; `pipeline.py`'s platform check (~line 91) and `self.mac` (~line 83) are the first places that must stop assuming one target.
- `self.work` per-target folders (~line 176) are the existing seam for D-05.
- `result` is built around line 479 (`self.result.update(...)`) — the per-target list attaches there.
- `.github/workflows/fork-ci.yml` gains two jobs beside `test`, with `paths:` filters on the workflow trigger.

</code_context>

<specifics>
## Specific Ideas

- The user's words: "I would like the user to be able to choose one or both from the UI and base the compilation off of those choices." The choice is the feature; the CI work follows from it rather than leading it.
- Skipping Android for a profile without `android.tsv` is preferred over inventing a profile: no experimental ports should start without the player asking.
- A green run must never hide a broken target, hence the non-zero exit when any target failed even though the other produced a package.

</specifics>

<deferred>
## Deferred Ideas

- Per-game remembered target choice in the library (two checkboxes pre-filled from the game's settings): Phase 4, which owns per-game settings.
- Running the two chains concurrently: deferred; it complicates cancel and the shared shader cache for a wall-clock gain only on large machines.
- A `porter doctor` row naming Xcode/Metal against `dmsh_chain.lock` before a Mac build starts: belongs with the Mac-tooling gaps, not here.
- The device smoke loop that would exercise both packages on a device: Phase 12.

</deferred>

---

*Phase: 11-compile-the-c-host-in-ci*
*Context gathered: 2026-11-04*
