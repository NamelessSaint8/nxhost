# Universal game support — implementation plan

Status: draft (2026-11-03, revised same day after surveying the upstream checkout and borrowing sources). Owner: nx2android. Companion to the GUI milestone in `.planning/ROADMAP.md`; this plan covers the porter and the host, not the GUI.

## What "works with every game" means

Four populations, four different problems. Each milestone below targets one. "Every game" is measured per population, not as a title count — the long tail is bounded by engine families and graphics APIs, not by the number of titles.

| # | Population | Today | Blocked by |
|---|---|---|---|
| P1 | Every dump of a supported game | Tag-less / NSZ / XCZ / personalized-ticket dumps fail or need manual work | Container tooling only (`scan_nsps`, `nx_extract`, porter input checks) |
| P2 | Every version/build of a supported game | Unregistered versions pack from derived profiles, **without** that build's `patches.py` cuts or fixed-address gates | Build-coupled host behavior (`module_t.build_id` lookups) |
| P3 | Every unprofiled game on a known engine | `--experimental` surveys and guesses, but heap keys need a Mac and bring-up is a manual loop | Android tool mode; strength of `profile_guess.py`; general rules accumulated in the host |
| P4 | Every graphics API | `porter/pipeline.py:248` refuses non-NVN ("the Android host replays NVN only"); several split steps need a Mac boot | Guest Vulkan and GL replay on Android; capture/decode steps without a Mac |

Success metrics (how we know a population is done):

- **P1**: every dump variant in the variant matrix (below) ports from one folder for three profiled games of different engines, on every host OS, with no manual renaming.
- **P2**: for three shipped games, a brand-new update NSP with no profile changes produces a port that boots to its title (RED warning allowed) — or is refused with a precise reason, never a silent wrong build.
- **P3**: N consecutive unprofiled games per engine family (Unity IL2CPP/NVN, UE4, UE5) reach `boots` on a device with zero code changes; tracked per family in `docs/PORT_STATUS.md`.
- **P4**: Hades and Super Mario Galaxy 1/2 (guest Vulkan) and Digimon Story Cyber Sleuth and Balatro (guest GL) port and play on Android with no Mac in the loop.

## Risk register

| Risk | Impact | Kind | Retired in |
|---|---|---|---|
| Android host cannot run headless tool-mode boots (no surface, no permissions, ART constraints) | Sinks M2 and the M3 heap-check plan; Mac stays required | Critical + unknown | M2 spike (first thing built) |
| Guest GL replay has no sane path on Android (no Metal; ANGLE vendoring vs. porting `hle_gl.m`'s ~150-function surface) | P4 GL games stay refused | Critical + unknown | M5 decision point; de-risked late on purpose |
| `nsz` as an external dependency is unreliable across hosts (pip availability, key handling, disk churn of full decompression) | M1 degrades to today's manual message | Known, bounded | M1 (ship the fallback, not a dependency) |
| CNMT scan needs the header key, but `porter inspect` is keyless today | API shape of `scan_nsps` changes; GUI cards must not regress | Known, bounded | M1 (keys-optional scan) |
| Replay ports drift from upstream's Metal implementations and become unmaintainable | Long-term maintenance of two backends | Architectural | Mitigation: shared semantics layer, upstream-first policy (see Execution) |
| The 417-commit upstream pick conflicts with our in-subtree deltas (`dm/android/`, NDK build, porter coupling in `porter/upstream.py`) | M0 stalls or silently drops an Android fix | Known, bounded | M0 (reconcile checklist in the milestone) |
| Test fixtures cannot ship Nintendo data | Verification relies on hand-made synthetic NSP/XCI fixtures | Known, bounded | Every milestone (fixture builder in M1) |

## Borrowing sources

Two sources, used differently:

**Upstream nxnative (local checkout `/Volumes/Data/Dev/nxnative`, MIT)** — the same project this repo's `nxnative/` subtree tracks. As of 2026-11-03 it is **417 commits ahead** of our last pick (the DKCR one, `53843cc7` → our `f73ca5b`), 54 of them in the NSP script alone, and it already contains most of what this plan's M1 was going to build:

- NSZ / XCZ converted once with `nsz -D` into `<build>/nsp/`, reused by name/size/mtime (`decompress_nsz`, `nsz_command`; pip `nsz` or a standalone 5.0+ on PATH)
- Merged NSPs and multi-game cartridges count as each title they hold; `--title-id` picks the game (`8ef752a2`)
- A package with no ticket and no `[title ID]` tag names itself from its own meta NCA (`85578fc9`, `package_title_reader`, `nx_extract --title` / `--contents`)
- `--work-dir` for the build folder; `--app <title ID>` in nx_extract for explicit program picks
- Engine coverage this plan's M3 needs: Unity 6000.3 ComputeShader (`#857`), Unity 2020.3 stripped ComputeShader (`#939`), gzip-wrapped shader archives (`#908`), Heaps (Dead Cells), Gust chunked zlib (Atelier Ryza), plus new first-party titles
- Rewriter and host hardening throughout (`#761` parallel scans, `#952` register-write analysis, jump-table fixes)

**Not in upstream and still ours:** version-from-CNMT (upstream `nsp_versions` is still `[vN]`-tag based), title keys / personalized tickets (upstream `nx_extract` still rejects them), everything Android (upstream has no `dm/android/`), the tool mode beyond the Mac host, and both replay backends beyond what `hle_vk.m` / `hle_gl.m` already show.

**Eden / the yuzu lineage (GPL — reference only, never copy code into this repo; upstream nxnative is MIT, this repo carries no GPL)** — a battle-tested emulator's worth of *behavior* to mine, with specific evaluation tasks in the milestones that name them: container and ticket semantics for M1's leftovers, and — to be verified, not assumed — whether it has a guest-Vulkan layer worth studying for M4. Its shader decompiler and host backends are not relevant to this repo's replay architecture.

**`eden-nx2` (`git.eden-emu.dev/Takoroka/eden-nx2`, GPLv3 — same reference-only rule)** — Eden's experimental Switch 2 fork, synced with Eden master. Three uses here, even though Switch 2 itself is deferred:

- **Switch 2 behavior reference** for whenever that deferral lifts: loader (ZBIC / zstd NSO decompression, firmware 22.0+), the Switch 2 GPU work in `video_core`, and OS-level version gating. Upstream nxnative has already started its own Switch 2 path (Ampere shader translation, Donkey Kong Bananza) — when those picks arrive via M0, this fork is the second opinion on anything that misbehaves on Android.
- **Block-compressed NSZ / XCZ support (their `#4552`)** — the exact question behind this plan's deferred streaming-`.ncz` item. If testers ever hit the disk pressure that would justify it, read their format handling first (behavior only).
- **Android platform hardening** — the fork builds for Android with 16 KB-page support, the same requirement class our NDK host builds face on Android 15+; worth surveying their build flags and loader work when we get there.

## M0 — Take upstream (do this first)

Goal: bring the `nxnative/` subtree from upstream's `53843cc7` (our last pick) to a current commit — 417 commits, which delivers most of old-M1 and large parts of M3's engine coverage as a side effect — without losing our Android deltas.

Tasks:

1. **Re-import the subtree** at a chosen upstream commit (the established "Add `nxnative/` from commit …" workflow), keeping our in-subtree additions: `dm/android/` (upstream has no such folder), the NDK arm64 host-folder build (`6442909`), and any local touches in `dm/host` or the tools that upstream reworked.
2. **Reconcile the porter coupling.** `porter/upstream.py`'s rename guards must pass against the new script (they will name what moved): `scan_nsps` grew `from_package` / `contents_of` / `want` parameters, NSZ conversion needs the keys and the child env, `--title-id` needs plumbing into `porter port` / `inspect` options and the GUI card, and porter's own NSZ refusal (`porter/pipeline.py:50`) is deleted in favor of upstream's `decompress_nsz`.
3. **Gate what Android does not use.** The pick brings Switch 2 work (Ampere shader translation, Donkey Kong Bananza, vendored dav1d, Xcode expectations). Out of scope here: Switch 2 titles on Android. Make sure the Android build does not grow requirements it cannot meet, and note the exclusion in PORT_STATUS.
4. **Regression pass.** Re-port three shipped games (one per engine family) from untouched game folders; stage reuse keys invalidate as they should; `python -m unittest discover tests` green.
5. **Cadence.** After the bulk pick, adopt a routine small-batch pick rhythm (the repo already does single-commit picks; the lesson of the 417-commit wall is written into this plan).

- Minimum success: three games re-port clean on the picked subtree; porter guards pass; no Android feature lost.
- Complete success: `--title-id`, merged-NSP and NSZ/XCZ handling usable from the porter CLI and GUI.
- Deferred: Switch 2 support (explicitly out of scope for this plan).

## M1 — The container delta (P1)

Goal: what M0 did not bring. Now three items, not five.

Tasks:

1. **Title keys.** `nx_extract` loads a `title.keys` file beside prod.keys into its `KeySet` (rights-ID → access key), so personalized-ticket dumps (still rejected at `Program.cs:180` after the pick, with advice nothing implements) port once the player supplies their title keys. Reference for ticket semantics: Eden/yuzu `core/file_sys` (behavior only — GPL). No key value is ever printed or logged. Contribute back to upstream (MIT, same file).
2. **Version from the CNMT.** Extend the meta-NCA read upstream added for title IDs to also report each update's version, and let `nsp_versions` use it: kills the remaining `[vN]`-tag dependence — several untagged updates, mis-tagged ones, untagged XCIs. Contribute back.
3. **Fixture builder + tests.** A `tests/fixtures` generator writing hand-made NSP/XCI/NSZ-shaped files covering the variant matrix: {NSP, XCI, NSZ, XCZ} × {tagged, untagged, mis-tagged} × {base only, base+1 update, base+2 updates, +DLC} × {common ticket, personalized ticket + title.keys}, plus merged NSPs, multi-game cartridges, empty and damaged files. Unit tests around the scan/version/pick functions on both the keyless and keyed paths.

- Minimum success: the common tester cases (M0's coverage) verified by tests rather than by hand.
- Complete success: the whole matrix, `--title` pick tested, personalized-ticket dump ports.
- Deferred: streaming `.ncz` (no materialized copy) — reference implementations exist in the GPL emulators to study if disk pressure ever demands it.

## M2 — Android host tool mode (retires the biggest unknown; unblocks M3)

Goal: the host's existing headless/tool paths — today built as a Mac host (`build_mac_host`, `boot_mac`, `heap_check` in `build_ipa_from_nsp.py`; `DM_OODLE_SERVE` / `DM_OODLE_HOST` decode in `hle_oodle.c`) — run on Android, driven by the porter over adb, so **no step of a port requires a Mac**.

Tasks:

1. **Spike first: one headless boot.** Get the Android host (`dm/android/`, entry through `front_android.c:487`) to run a game headless from an adb shell (env-driven like the Mac's `DM_ROMFS`/`DM_SAVE`/…), with stdout reaching the porter, for a few seconds, on one device. Everything else in M2/M3 depends on this shape. Questions the spike answers: does the host need a surface at all (NVN replay without present), SELinux/executor constraints on app_process-style launches, and where the log lands (`Documents/log.txt` vs. stdout).
2. **Tool-mode steps.** Port the porter's Mac-host steps to prefer Android: the heap check (`heap_check`), GLSLC / run-time shader capture (`glslc_capture`, `vk_capture`, `gl_capture` steps), and Oodle / LZ5 / Trinity / PKZ decode for the shader split (`DM_OODLE_HOST` / `DM_OODLE_MODULES`). Mac stays as a fallback where it already works (`sys.platform == 'darwin'`), so iOS contributors see no regression.
3. **Porter wiring.** A device or emulator becomes an optional *build* input: `porter port --tool-device <serial>` (default: any attached device when the step needs it); the stage logs say which host ran what. Respect the one-port-at-a-time lock (`porter/lock.py`).

- Minimum success: the heap check runs on an Android device and produces the same `heap_signals` keys the Mac path does, for one virtual-address-memory game (e.g. a Unity title).
- Complete success: Three Houses (GLSLC capture), Pokémon Legends: Z-A or an UE title (Oodle decode) and Balatro (GL capture) port end to end on a Windows/Linux PC with only a phone attached.
- Deferred: capturing on-device during real play (first-boot capture); performance of decode on mid-range devices (measure, don't optimize).

## M3 — Experimental path hardening (P3)

Goal: unprofiled games on engines the repo already knows reach `boots` with zero code changes, and each manual fix keeps landing as a general rule (the flywheel: spin waits, `thr_yield`, `OP_BIND_TEX1`, `fs_uint`, `prog_resolve` all started as one game's bug).

Tasks:

1. **Heap keys without a Mac**: `profile_guess.py heap_signals` fed by the M2 Android heap check; provisional profiles stop shipping guessed pools for virtual-address-memory games.
2. **Device-loop triage**: `porter` gains a loop-friendly command that installs the experimental build, runs it headless or foreground for N seconds, pulls `log.txt`, and prints the first `[RED]`/crash classified against upstream's bring-up catalogue (`nxnative/docs/agents/03-bringup.md`) — the same loop `device-loop.md` describes, executable. Not a fixer; a lens. Fixes stay human-reviewed general rules.
3. **Engine-family bring-up sprints**: per family (Unity IL2CPP/NVN across Unity 2017–6000, UE4, UE5, KTGL, first-party sead/agl), take the next unported title from `dm/games`' iOS-only set, port it with `--experimental`, and land whatever general rule it needed. `docs/PORT_STATUS.md` grows a per-family coverage table (ported / boots / refused-with-reason).
4. **Survey quality**: keep `profile_guess.py`'s markers and `shader_split.py` readers in step with every new engine variant found; a new engine gets a reader before its games count as "supported family".

- Minimum success: 3 consecutive unprofiled Unity IL2CPP/NVN titles reach `boots` untouched.
- Complete success: same for UE4 and UE5; the triage command is part of the loop; PORT_STATUS carries the family table.
- Deferred: automated fix suggestion beyond classification; new-engine readers beyond the families named here.

## M4 — Guest Vulkan replay on Android (P4, first half)

Goal: games whose `main` renders with Vulkan (Hades, Super Mario Galaxy 1/2 — upstream keys them `graphics vulkan`) port to Android. Upstream's Metal implementation (`dm/gfx/vk/hle_vk.m`, ~1.5k lines) is the reference semantics; the Android Vulkan backend (`dm/android/gfx_vk_*.c`, ~4.4k lines, currently NVN-replay only) is the target.

Tasks:

1. **Census before code**: run `dm/tools/loader_census.py` against the Vulkan titles' mains to size the vk surface actually used (as `hle_gl.m`'s GL census did), so the milestone has a real denominator. In the same pass, evaluate Eden/yuzu-lineage sources for a guest-Vulkan layer (grep for a guest `vkCreateInstance` dispatch / ICD shim): if one exists, study its handle/object mapping as a second reference beside upstream's `hle_vk.m`; if not, `hle_vk.m` alone is sufficient — it is a complete, proven implementation. GPL: behavior reference only, no code.
2. **Core objects and dispatch**: instance/device bootstrap where the host answers `main`'s vk* calls (the same "host's Vulkan layer answers, a loaded driver would take them first" rule `profile_guess.py:130` applies on iOS), memory, queues, command buffers.
3. **Shaders and pipelines**: SPIR-V pass-through where possible (the host already speaks Vulkan natively here — the replay layer maps guest handles, it does not re-translate), with the existing `gfx_vk_shader.c` doing the work.
4. **Present and input**: swapchain through `gfx_vk_present.c`; the frame-step / fps-lock keys (`fps_target`, `present_interval`) behave as on iOS.
5. **The `vk_capture` path**: Galaxy-style run-time-generated shaders captured via M2's Android capture instead of the Mac.

- Minimum success: Hades reaches its title and gameplay on one device, from a PC-only setup.
- Complete success: Hades, Galaxy 1 and Galaxy 2 playable; `porter/pipeline.py:248` stops refusing `graphics vulkan` games; PORT_STATUS updated.
- Deferred: Vulkan extensions beyond what the census finds; performance tuning beyond "plays".

## M5 — Guest GL replay on Android (P4, second half; decision point at start)

Goal: GL-rendering games (Digimon Story Cyber Sleuth's MVGL, Balatro's LÖVE — upstream keys `graphics gl`, `dm/gfx/gl/hle_gl.m`, ~2k lines) port to Android. GL has no native path on Android Vulkan; this is the riskiest milestone, which is why it is last and starts with a decision.

Decision (last responsible moment = start of M5, informed by M4's scars): vendor ANGLE (GL-on-Vulkan, battle-tested, heavy) vs. port `hle_gl.m`'s census-sized surface (~150 GL functions for LÖVE, 79 for Digimon) onto the Android backend. M4's experience with the shared-semantics question is the main input; do not decide earlier.

- Minimum success: Balatro (LÖVE, the smaller census) plays on one device.
- Complete success: Digimon and Balatro playable; the `graphics gl` refusal gone; the decision and its rationale recorded as an ADR in this repo.
- Deferred: GL ES titles (none known in the set); desktop-GL features no census-title uses.

## M6 — Version drift (P2)

Goal: a new build of a shipped game ports correctly with no human, or refuses precisely. Runs opportunistically alongside M3–M5; it is the standing work of moving host behavior off fixed addresses.

Tasks:

1. **Reduce fixed-address behavior**: each `module_t.build_id`-keyed branch in the host and each `patches.py` cut is a candidate for replacement by import/symbol/SDK-shape detection (repo policy already demands general over per-build). Track the count; drive it down.
2. **fnmap automation**: `dm/tools/nso_fnmap.py` carry-over wired into the derived-profile path so a new build gets candidate addresses flagged for disassembly check rather than silent absence.
3. **Derived-profile regression harness**: for three shipped games, a CI-able check that a derived port of their *registered* version behaves identically to the registered port (guards the derive path itself).

- Minimum success: the harness runs for three games in `python -m unittest discover tests`.
- Complete success: fixed-address count trending down release over release; a real new update of a shipped game ported end to end with only the RED derived-profile warning and no wrong build.

## Execution framework

**Sequencing.** M0 → M1 → M2 → M3, with M4 after (or beside) M3 and M5 strictly after M4. M6 is continuous. M0 first: the 417-commit pick delivers most of old-M1 and M3's new engine readers in one move, and every later milestone is easier on a current subtree. M2 retires the plan's biggest unknown before anything depends on it; M3 converts M2 into coverage; M4/M5 are the long poles and are ordered by risk. Sizing (not calendar): M0 M, M1 S, M2 M, M3 M-per-family, M4 L, M5 L, M6 continuous. Calendar commitments are deliberately not made here; each milestone gets its own phase plan when started (GSD or otherwise).

**Upstream-first policy.** `build_ipa_from_nsp.py`, `nx_extract`, `shader_split.py`, `hle_oodle.c` and everything else under `nxnative/` is shared with upstream (iOS) — `porter/upstream.py` imports the script as a library and guards renames, and M0 exists because falling 417 commits behind is what made container support look like our work. Changes there should be made in the subtree *and* offered upstream (upstream is MIT); porter-only glue (nsz invocation, `--title`, `--tool-device`) lives in `porter/`. Never fork semantics the two hosts share. Borrowing from GPL projects (Eden and kin) is behavior-study only.

**Quality gates.** Every milestone: `python -m unittest discover tests` green; no Nintendo-owned data in fixtures or the repo; no key values printed or logged; English everywhere; `[RED]` lines for anything unimplemented. Device verification on at least one arm64 device per milestone that changes the host (M2–M5). Docs updated in the same change: `docs/PORT_STATUS.md`, `nxnative/docs/agents/` failure entries, and this file's status line.

**Managed deferrals (registry).**

| Deferred item | From | Revisit |
|---|---|---|
| Streaming `.ncz` decode (no materialized NSP) | M1 | If disk pressure shows up in tester reports |
| Switch 2 / Ampere titles on Android | M0 | After this plan's populations are covered; behavior reference: `eden-nx2` (GPL, study only); the Ampere shader translation and Bananza work arrive from upstream via the picks |
| On-device capture during real play | M2 | After M3's triage loop exists |
| Automated fix application (beyond classification) | M3 | Only if classification data shows a safe, frequent pattern |
| Vulkan extensions beyond census | M4 | Per title, when a refusal names one |
| GL ES guests | M5 | When a census finds one |
| Vulkan-on-iOS ↔ Android semantic unification refactor | M4 | If drift pain is real during M4 |
