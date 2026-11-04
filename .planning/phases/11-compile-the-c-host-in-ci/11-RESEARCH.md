# Phase 11: Compile the C host in CI (and deliver one-or-both targets) - Research

**Researched:** 2026-11-04
**Domain:** Python pipeline orchestration (`porter`), a JSON-lines GUI protocol (PySide6), a hand-listed C Makefile vs a globbing Python Android build, and GitHub Actions job design
**Confidence:** HIGH on the code and CI facts (read this session), MEDIUM on the macOS runner's deployment-target behaviour, HIGH on what the two targets need to build

> **Tooling note (honest limitation):** this session had no shell tool — only file search, file edit and web fetch. Every in-repo claim below was read from the file named in its citation and quoted verbatim with a line range; nothing was executed. Claims that would need a command run to confirm are tagged `[ASSUMED]` and listed in the Assumptions Log.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** The target is the user's choice — Android, the Mac app, or both — from the CLI and from the GUI, and the work done follows that choice. Compilation is never fixed to one target in the pipeline. — **Reversibility:** costly — once `--platform both` is in the CLI, the JSON protocol and the GUI depend on it; withdrawing it means deprecating a documented flag and a control, not just deleting a branch.
- **D-02:** Two checkboxes in the Port view (Android, Mac app), both allowed, **defaulting to what suits the host**: on macOS the Mac app is ticked, everywhere else Android is. No zero-target state is reachable. The remembered-per-game form of this is Phase 4's business, not this phase's.
- **D-03:** On Windows and Linux the Mac app checkbox is **disabled with the reason** (a Mac app is built on a Mac; `pipeline.py` already refuses off `darwin`). The GUI never offers a target that cannot be built on that host.
- **D-04:** Run **Android first, then the Mac app**. Android is the cheap chain, so a broken toolchain or profile fails in minutes instead of after the twenty-plus-minute Metal chain.
- **D-05:** The two chains **share extraction and the shader split**; only target-specific stages run per target (the rewrite with its `DM_TARGET`, the Vulkan vs Metal shader build, the host compile, the pack), in the existing `work/android` and `work/mac` folders.
- **D-06:** A failing target does **not** stop the other. The run reports **per-target results** (built / failed / skipped, with the reason) and exits non-zero if any target failed. A working APK is never discarded because the Metal chain was unhappy. — **Reversibility:** costly — the exit-code contract and the result shape are what a script or a tester reads; changing it later breaks callers silently.
- **D-07:** A profile with no `android.tsv` (52 of 54 upstream profiles have none) is **skipped for Android with the reason named**, and the Mac app is still built. No provisional profile is invented and no experimental Android build starts implicitly.
- **D-08:** One run produces **one result** whose JSON `result` event gains a per-target list (platform, output path, ok/failed/skipped, reason); the Port view draws one row per target with its own Reveal, and the run log names both. A single-target run keeps today's shape, so the golden bridge fixtures stay valid. — **Reversibility:** costly — `tests/fixtures/bridge/` goldens and `gui/runner.py` parse this; a rename would break the protocol tests and any saved log reader.
- **D-09:** Two **blocking** compile jobs, one per target (apple, android), **path-filtered** to `nxnative/**` and `.github/**` so documentation-only pushes skip them. A failure names its target.

### the agent's Discretion

Not discussed — follow these defaults, and surface anything rated one-way as a `checkpoint:decision`:

- **Warnings strictness:** `-Werror=implicit-function-declaration` for `dm/host` and `dm/gfx` on the Apple job (the class that bit Apple clang 21); the Android job keeps the NDK's defaults plus the same flag. Full `-Werror` is out — it would pull other phases' work in.
- **The profile CI builds against:** a committed one (`01000A10041EA000`, Skyrim) via `GAME=`, since `dm/host/Makefile` refuses to build without a profile and all 142 profiles are data in the tree. No fixture profile unless the committed one proves unstable.
- **Compile depth on Apple:** per-file `-c` like `nxnative/dm/ios/tools/compile_check.py` first, then link the `dmhost` binary if it is cheap — linking is what catches a source missing from the Makefile's hand-listed `SRC`.
- **The `SRC` drift guard:** a test that compares `dm/host/SRC` against `dm/host/*.c` and names any file that would link on Android (which globs) but not on Mac. Cheaper and more precise than waiting for a link failure.
- **The `dmsh_chain.lock` refusal test:** a synthetic mismatch fed to `tool_lock.py`, asserting the remedy text and exit, so the message cannot rot.
- **Off-Mac CLI behaviour for a Mac target:** skipped with the reason, never a failed target.

### Deferred Ideas (OUT OF SCOPE)

- Per-game remembered target choice in the library (two checkboxes pre-filled from the game's settings): Phase 4, which owns per-game settings.
- Running the two chains concurrently: deferred; it complicates cancel and the shared shader cache for a wall-clock gain only on large machines.
- A `porter doctor` row naming Xcode/Metal against `dmsh_chain.lock` before a Mac build starts: belongs with the Mac-tooling gaps, not here.
- The device smoke loop that would exercise both packages on a device: Phase 12.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| QUAL-07 | The GUI's Port view offers the target through porter — Android, the Mac app, or both as two checkboxes defaulting to what suits the host, with the Mac app disabled off macOS — and one run shows one result with a row per target, with no second code path from view to pipeline | §B: `PortTab.start()` (`gui/app.py:164-173`) builds one argv today; the checkbox → `--platform` mapping is a 3-line helper; `PortTab.item()`/`on_event` (`gui/app.py:196-229`) need `(platform, k)` keys; UI-SPEC rules 1-28 are the visual contract |
| QUAL-09 | CI compiles `dm/host` for Apple arm64 and Android arm64 on every push, as two blocking jobs path-filtered to `nxnative/**` and `.github/**`; a source missing from `SRC` fails naming the file; implicit function declarations are errors on every toolchain; the `dmsh_chain.lock` refusal is covered by a test | §C: path filters are per-*workflow*, not per-job, so a new `host-build.yml` is required; both toolchains are preinstalled on `macos-26` and `ubuntu-22.04`; §E/§F give the two guards |
| QUAL-13 | One run can produce the APK, the Mac app, or both: Android first, extraction and the shader split shared, per-target stages in their own folders; a failing target does not stop the other, the run reports per target and exits non-zero if any failed; a profile without `android.tsv` is skipped for Android with the reason named | §A: `run()` and `run_mac()` are already separate sequences over `self.aw` (`pipeline.py:92,109,176`), so `both` is a driver over two `Port` objects; reuse keys make extraction and split cache hits, no refactor needed |
</phase_requirements>

## Summary

**Phase 11 is two independent halves that share one vocabulary, and both are smaller than they look.**

The **pipeline half** is genuinely a driver: `Port.run()` already validates options, resolves the toolchain and builds the child environment for a *single* target, and then bails out to `run_mac()` at `pipeline.py:109` before any Android stage runs (`if self.mac: return self.run_mac()   # everything below is the Android port's`). Per-target work folders already exist (`self.aw = self.work / ('mac' if self.mac else 'android')`, `pipeline.py:176`), and the extraction and shader-split stages already have on-disk reuse keys, so "shared extraction and split" is what happens *for free* when the second target runs in the same game folder — no stage needs hoisting. `--platform both` is therefore: run an Android `Port`, catch a reported failure, run a Mac `Port`, collect two rows. The two things that actually need design are (a) the **skip** paths (no `android.tsv`, off-macOS) which must not look like failures, and (b) the **event identity** problem: `PROG.plan()` resets `k` to 1 per target, and the GUI keys its stage tree by `k` (`gui/app.py:196-199`), so two targets would overwrite each other's rows unless events gain `platform`.

The **CI half** cannot go in `fork-ci.yml`. GitHub path filters are a property of the *workflow* trigger, and `fork-ci.yml:6-9` triggers on every push with no `paths:`; adding `paths:` there would also skip the four-host Python suite on documentation-only pushes, which D-09 does not ask for. A second workflow, `host-build.yml`, with its own `paths: [nxnative/**, .github/**]`, is the only shape that satisfies "documentation-only pushes skip the compile jobs" without collateral damage. Both toolchains are already on the hosted images — `macos-26` (arm64, GA) with Xcode 26.6, and `ubuntu-22.04` (x64) with `ANDROID_NDK_HOME=/usr/local/lib/android/sdk/ndk/27.3.13750724` — so neither job downloads an NDK or an SDK. The Android side is already strict: `dm/android/build.py:66` passes `-Werror=implicit-function-declaration`. The Apple side is not: `dm/host/Makefile:18` has `-O1 -g -Wall -Wno-unused-function -mmacosx-version-min=$(MACOS_MIN)` and nothing more.

**Primary recommendation:** implement `--platform both` as a thin driver that constructs two `Port` objects (Android first), marks each event with `platform` inside `porter/runlog.py`'s existing event wrapper rather than in the engine subtree, adds `result.targets[]` *alongside* today's top-level keys, and returns a non-zero exit by letting `cmd_port`'s lambda return the code. Put the two CI jobs in a new path-filtered `host-build.yml`, run the real links (not `--only-compile`, not per-file `-c` alone), and land the `SRC` drift check as a new `check()` in `tests/arch_rules.py` where all four CI hosts already run it.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Target selection (which packages to build) | Browser/GUI (`gui/app.py` PortTab) | — | It is a user preference, not a build fact; the view passes it down as one argv token and never decides what can be built (UI-SPEC rule 26-28) |
| Deciding whether a target *can* be built | API/Backend (`porter/pipeline.py`) | GUI (disabled state only) | `MAC_HOST` disables a box; only porter knows about `android.tsv`, Xcode and `darwin`. Two owners would duplicate the rule |
| Stage sequencing per target | API/Backend (`pipeline.py` `run()`, `run_mac()`) | — | Existing `PROG.stage()` straight line; the driver must not fork it |
| Event protocol (`stage`/`step`/`progress`/`result`) | API/Backend (`porter/runlog.py` wrapper + `pipeline.emit_result`) | GUI (`gui/runner.py` pass-through) | `gui/runner.py` emits parsed dicts unmodified, so the protocol is porter's to extend |
| Per-row results and Reveal buttons | Browser/GUI (`gui/app.py` `TargetRow`) | — | Pure presentation over `result.targets[]` |
| Compiling the C host | CI (`.github/workflows/host-build.yml`) | Local make/build.py (same commands) | CI reuses the repo's own build entry points, never a bespoke command line |
| `SRC` completeness | Build config (`dm/host/Makefile`) | Test (`tests/arch_rules.py`) | The Makefile is the source of truth; the test only mirrors it against the directory |

## Standard Stack

**This phase installs nothing.** No new Python package, no npm crate, no Rust crate, no GitHub Action beyond the two SHAs the repo already pins. Everything below is a toolchain the build already uses, with the version that CI will actually get.

### Core (existing, not added)

| Tool | Version / label | Purpose | Why this one |
|------|-----------------|---------|--------------|
| Apple clang + `make` | `macos-26` image, Xcode 26.6 default (`/Applications/Xcode_26.6.app`, SDK `macosx26.5`) | Compiles and links `dmhost` via `dm/host/Makefile` | The Makefile *is* the Mac build; CI must run the same target a developer runs `[VERIFIED: raw.githubusercontent.com/actions/runner-images/main/images/macos/macos-26-arm64-Readme.md]` |
| Android NDK | `27.3.13750724`, preinstalled at `/usr/local/lib/android/sdk/ndk/27.3.13750724`, exported as `ANDROID_NDK_HOME` on `ubuntu-22.04` (x64) | Compiles/links `dmhost` + `libdmhost.so` via `dm/android/build.py` | `build.py`'s `--ndk` default already reads `ANDROID_NDK_HOME`, so CI needs no download `[VERIFIED: images/ubuntu/Ubuntu2204-Readme.md]` |
| Python 3 | 3.10.12 on `ubuntu-22.04`; system `python3` on macOS | Runs `game.py header`, `android_profile.py header`, `host_msl.py`, `dm/android/build.py` | All four are plain scripts with no third-party imports `[VERIFIED: images/ubuntu/Ubuntu2204-Readme.md]` |
| `actions/checkout` | already pinned in-repo to `3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1` | Checkout, `persist-credentials: false` | Reuse the existing pin; no new supply-chain decision `[VERIFIED: .github/workflows/fork-ci.yml:38-40]` |

### Supporting

| Tool | Version | Purpose | When to Use |
|------|---------|---------|-------------|
| `xcrun -sdk macosx metal` | present only if the Metal toolchain component is installed | Compiles `dm/gfx/msl/*.metal` into `gen/msl-macosx/host_msl_gen.h` | Optional: `host_msl.py` degrades to a sources-only header and prints a note `[VERIFIED: nxnative/dm/gfx/tools/host_msl.py:35]` |
| `xcrun -sdk macosx --show-sdk-version` | on the image | Escape hatch if `MACOS_MIN` (26.6) is newer than the SDK (26.5) | Only if the Apple link complains; see Pitfall 3 |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| A new `.github/workflows/host-build.yml` | Adding `paths:` to `fork-ci.yml` | `paths:` is workflow-level: the four-host `test` matrix would also stop running on docs-only pushes. Rejected — it breaks QUAL-09's spirit and CI-0x coverage |
| The preinstalled NDK | `curl` the pinned r27c archive, or `android-actions/setup-android` | Downloading ~700 MB per run and adding an unpinned third-party action for a toolchain the image already ships in a supported version. `porter/pins.py` pins r27c for *players*, not for CI |
| `dm/android/build.py` (native entry point) | Hand-written `clang` invocation in the workflow | The script owns the source lists (`HOST`/`GFX`/`PORT`/`ASM`/`VPX`), the `--target`, the flag stamp and the post-link symbol audit (`build.py:125-132`). Reimplementing it in YAML would drift immediately |
| `make ... dmhost` (real link) | `--only-compile` / per-file `-c` only | `--only-compile` skips the link, which is exactly what catches a missing `SRC` entry and dangling symbols. Compile-only is a *debugging* mode, not the gate |

**Installation:** none. `requirements.txt` is unchanged; the CI jobs install nothing (`pip` is not needed for either job).

**Version verification:** the two images were confirmed from the runner-images READMEs this session (macOS 26 arm64: Xcode 26.6 default; Ubuntu 22.04: NDK 27.3.13750724 default, `ANDROID_NDK_HOME` set). No package version was taken from training data.

## Package Legitimacy Audit

**No external packages are installed by this phase.** The Package Legitimacy Gate was therefore not applicable and was not run (and could not be: this session had no shell). The only supply-chain decisions this phase makes are:

| Item | Registry | Age | Downloads | Source Repo | Verdict | Disposition |
|------|----------|-----|-----------|-------------|---------|-------------|
| `actions/checkout@3d3c42e5…` | GitHub Actions | already in use in this repo | n/a | github.com/actions/checkout | OK (unchanged pin) | Approved — reuse the existing SHA |
| Android NDK 27.3.13750724 | Google, preinstalled on the runner image | shipped with the image | n/a | developer.android.com | OK | Approved — no download, no pin change |
| Xcode 26.6 / macOS 26.5 SDK | Apple, preinstalled on the runner image | shipped with the image | n/a | developer.apple.com | OK | Approved |

**Packages removed due to [SLOP] verdict:** none.
**Packages flagged as suspicious [SUS]:** none.
**Do not add** a third-party "setup-android"/"setup-ndk" action for this phase: the toolchain is already on the image, and any new action is a new SHA to trust.

## Architecture Patterns

### System Architecture Diagram

```
                        GUI (gui/app.py PortTab)
        target boxes ──┐
        [x] Android APK│  start() → one argv
        [ ] Mac app   ─┘
                        │
                        ▼
   python -m porter port <folder> --platform both --progress json
                        │
                 porter/cli.py cmd_port  (Options)
                        │
                        ▼
            porter/pipeline.py  Port.run()          ← driver (new)
                        │
        ┌───────────────┴────────────────┐
        ▼ 1st                           ▼ 2nd (skipped off darwin)
   Port(platform='android')        Port(platform='mac-app')
        │                               │
   common prologue: validate → toolchain.require → childenv.dotnet
        │                               │
   inputs()  ─── game folder scan ───► inputs()      (mac: profile only)
        │        (same <tid>_build)     │
   extract() ── reuse key hit ──────► extract()      ← D-05 shared work
   rewrite(DM_TARGET=android)          rewrite(DM_TARGET=apple)   [work/android | work/mac]
   shaders()  (Vulkan)                 shaders() (Metal libs)     split() shared
   host()     (NDK)                    host()    (Xcode mac_host)
   apk() + data()                      pack_app()
        │                               │
        └────────► result per target ◄──┘
                        │
      PROG events (stage/step/progress/stage_end) + platform
                        │
                        ▼
        porter/runlog.py wrapper  → JSON lines on stdout
                        │
                        ▼
     gui/runner.py Porter.event  (dict pass-through, no parsing)
                        │
                        ▼
   PortTab.on_event → stage tree / step line / results block (one row per target)
```

### Recommended Project Structure (touched files, not new folders)

```
porter/cli.py                     # --platform gains 'both'; cmd_port maps a failed target to exit 1
porter/pipeline.py                # Port.run_both(); TargetSkipped; arm the no-android.tsv skip
porter/runlog.py                  # add 'platform' to stage/step/progress/stage_end inside _wrap
gui/app.py                        # Targets row, TargetRow, results block, (platform, k) keys
tests/fixtures/bridge/record.py   # add a two-target golden
tests/fixtures/bridge/port_both.jsonl   # new golden (generated, not hand-written)
tests/test_bridge.py              # replay port_both.jsonl; assert two rows and two Reveals
tests/test_porter.py              # both-run driver: order, skip, failure isolation, exit code
tests/arch_rules.py               # new check(): Makefile SRC vs dm/host/*.c
nxnative/dm/host/Makefile         # CFLAGS += -Werror=implicit-function-declaration
nxnative/dm/gfx/tools/tool_lock.py# refusal message → module constant + main(argv) returning the code
.github/workflows/host-build.yml  # NEW: two path-filtered blocking jobs
docs/ARCHITECTURE.md              # §The port stage table + protocol section; result.targets[]
```

### Pattern 1: A driver over two `Port` objects, not a forked stage sequence

**What:** `Options.platform == 'both'` makes `Port.run()` delegate: build an Android `Port`, run it, catch a *reported* failure, then build a Mac `Port`, run it, and assemble `result` from both.
**When to use:** always for `both`; single-target runs keep running exactly the code they run today.
**Why not one `Port` with a phase list:** `self.mac`, `self.aw`, `self.ap`, `self.host_bin`, `self.patched` are all per-target state on the instance; a shared instance would need every one of them parameterised. Two instances cost nothing because the expensive work is on disk and keyed.

```python
# Shape only — the verified anchors are: pipeline.py:91 (platform check), :109 (mac bail-out),
# :176 (per-target work folder), :487-488 (emit_result).
NEW = ('android', 'mac-app')          # D-04 order

class TargetSkipped(BuildError):
    """A target this run cannot build on this host or with this profile — not a failure (D-06/D-07)."""

def run_both(self):
    rows = []
    for platform in NEW:
        child = Port(dataclasses.replace(self.o, platform=platform))
        child.multi_target = True          # makes inputs() raise TargetSkipped, not BuildError
        if platform == 'mac-app' and sys.platform != 'darwin':
            rows.append({'platform': platform, 'status': 'skipped',
                         'out': '', 'reason': 'a Mac app is built on a Mac: this host builds the Android APK'})
            continue
        try:
            res = child.run()
            rows.append({'platform': platform, 'status': 'ok',
                         'out': res.get('app') or res.get('apk', ''), 'reason': ''})
        except TargetSkipped as e:
            rows.append({'platform': platform, 'status': 'skipped', 'out': '', 'reason': str(e)})
        except BuildError as e:            # D-06: the other target still runs
            rows.append({'platform': platform, 'status': 'failed', 'out': '', 'reason': str(e)})
    # additive only: today's top-level keys stay, filled from whichever targets built (D-08)
    self.result = {'targets': rows}
    return self.result
```

**Two constraints the driver must respect**

1. **Only `BuildError` is a target failure.** `cli.py:125-128` re-raises anything else as a crash; the driver must do the same, or a `TypeError` would be reported as "the Mac app failed" and the traceback lost.
2. **`PROG.plan()` is global and per-run** (`PROG.plan(1 + len(self.versions) + bool(self.fam['dlc']) + bool(o.fps60) + 6 + bool(o.install))`, `pipeline.py:115`; `PROG.plan(1 + len(self.versions) + bool(self.fam['dlc']) + 4)`, `pipeline.py:470`). Each child calls it, so `k` restarts at 1 for target 2. That is *acceptable* only if the events carry `platform` (below); otherwise the GUI's `self.items[k]` collides.

### Pattern 2: `platform` goes on the event inside `porter/runlog.py`, not in the engine subtree

**What:** `runlog._wrap` already rewrites events on their way out — it adds `log` to `result` and `rate` to byte `progress` events.
**When to use:** for `stage`, `step`, `progress`, `stage_end` (the GUI needs the first three; `stage_end` so the tree's Result/Time columns land on the right row).

```python
# porter/runlog.py:115 — verified today:
#     if obj.get('ev') == 'result': obj = {**obj, 'log': str(S['path'])}
# Add beside it, driven by S['platform'] which run_both() sets before each child:
#     if S.get('platform') and obj.get('ev') in ('stage', 'step', 'progress', 'stage_end'):
#         obj = {**obj, 'platform': S['platform']}
```

**Why here and not in `nxnative/scripts/build_ipa_from_nsp.py:140,166,182`:** that file is the upstream engine subtree; `porter/` is the fork's glue and the documented place for glue. Editing the subtree buys a merge conflict on every upstream pick (`docs/TOOLING_PLAN.md` principle 4), and `runlog._wrap` is exactly the seam porter already uses for two other additive fields.

### Pattern 3: Skips are raised, failures are caught

**What:** the two skip conditions are discovered at different times, so they take different routes.

| Condition | When it is known | How it becomes `skipped` |
|-----------|------------------|--------------------------|
| Mac app requested off macOS | before the child runs | `sys.platform` check in `run_both()` — no child constructed |
| Profile has no `android.tsv` | inside `inputs()`, after the NSP scan gives the title ID (`pipeline.py:144`: `g, ap = profiles.by_title(self.app)`) | `TargetSkipped` raised at `pipeline.py:154-155` instead of `BuildError`, only when `self.multi_target`; the message drops the `--experimental` advice, which is a single-target remedy |

`[VERIFIED: porter/pipeline.py:144]` `        g, ap = profiles.by_title(self.app)`
`[VERIFIED: porter/pipeline.py:154]` `                what = f'no game profile for {tid}' if not g else f'{g.get("name", g.id)} ({g.id}) has a game profile but is not ported to Android yet (no android.tsv in {g.dir})'`

**Do not** invent a pre-flight scan to decide the skip earlier: it would scan the NSPs twice and would need its own copy of the "is there an android.tsv" rule, which `porter/profiles.py` already owns.

### Pattern 4: The GUI keys the stage tree by `(platform, k)`

**What:** `PortTab.item(k, name)` stores `self.items[k]`; today `k` is unique because there is one chain. With two chains, `k` repeats.
**When to use:** whenever `--platform both` was requested.

```python
# gui/app.py:196-199 today (verified): the stage rows are keyed by k alone
def item(self, k, name):
    ...
    it = QTreeWidgetItem(['…', name, '', '']); self.stages.addTopLevelItem(it); self.items[k] = it
# becomes: self.items[(ev.get('platform', ''), k)] = it
# and the Stage column text gains the prefix for a multi-target run (UI-SPEC rule 12):
#     'Android APK · rewrite' / 'Mac app · rewrite'; a single-target run keeps the bare name.
```

### Pattern 5: One new workflow, two jobs, no `if:` gymnastics

```yaml
# .github/workflows/host-build.yml — shape; every action SHA copied from fork-ci.yml
name: host-build
on:
  push:          { paths: ['nxnative/**', '.github/**'] }
  pull_request:  { paths: ['nxnative/**', '.github/**'] }
  workflow_dispatch:
permissions: { contents: read }
concurrency: { group: host-build-${{ github.ref }}, cancel-in-progress: true }
jobs:
  host-apple:    # runs-on: macos-26, timeout-minutes: 45
  host-android:  # runs-on: ubuntu-22.04, timeout-minutes: 30
```

### Anti-Patterns to Avoid

- **Forking `run()` into `run_android()` + `run_both()`:** two copies of a 20-stage sequence drift within a week; the existing `run_mac()` split is the only fork allowed, and it already exists.
- **Adding `paths:` to `fork-ci.yml`:** silently disables the four-host Python suite for docs-only pushes.
- **`--only-compile` as the CI gate:** it returns before the link (`build.py:113`: `if a.only_compile: sys.exit(1 if failed else 0)`), so a missing `SRC` file and every dangling symbol pass.
- **A `--platform both` that emits two `result` events:** D-08 says one; the GUI's `self.result` would keep only the last.
- **Making the GUI decide skips:** UI-SPEC rule 26-28 forbids it — a `skipped` row's reason must be porter's own sentence.
- **Editing `nxnative/` to add `platform` to the emitter:** merge cost on every upstream pick for a field porter's own wrapper can add.
- **Touching `clear_all`/`STATUS_COLOUR`:** `STATUS_COLOUR` (`gui/app.py:19`) is the *game* status badge, a different axis; UI-SPEC says do not edit it.

## What the plan builds on — the facts, one research question at a time

### Q1/Q2: how the protocol and the GUI consume events today

The GUI does **no protocol parsing of its own**; `gui/runner.py` splits stdout on newlines, `json.loads` each, and emits the dict — a non-JSON line becomes `{'ev': 'say', 'msg': s}`.

`[VERIFIED: gui/runner.py:99-103]`
```
            s = ln.decode('utf-8', 'replace').strip()
            if not s: continue
            try: ev = json.loads(s)
            except ValueError: ev = {'ev': 'say', 'msg': s}
            self.event.emit(ev if isinstance(ev, dict) else {'ev': 'say', 'msg': s})
```

**Consequence:** the runner needs **no change at all** for `platform` or `targets[]`. Every additive protocol change is invisible to it, and old streams stay valid automatically. The dicts reach `PortTab.on_event` unchanged.

`[VERIFIED: gui/app.py:202-229]` (abridged to the branches that matter)
```
        e = ev.get('ev')
        ...  e == 'stage':  self.cur = ev; it = self.item(ev['k'], ev['name']); it.setText(0, '▶') ...
            self.step.setText(f'[{ev["k"]}/{ev["n"]}] {ev["name"]}' + (f' · {ev["step"]}' if ev.get('step') else ''))
        ...  e == 'stage_end':  it = self.item(ev['k'], ev['name']); ok = ev.get('ok', True)
            it.setText(2, ev.get('summary', '')); it.setText(3, hms(ev.get('elapsed')))
        ...  e == 'say':  self.append(ev.get('msg', ''))
        ...  e == 'log':  self.log_path = ev.get('path'); self.log_btn.setEnabled(bool(self.log_path))
        ...  e == 'result':  self.result = ev; self.log_path = ev.get('log') or self.log_path; self.log_btn.setEnabled(bool(self.log_path))
```

**Consequences for a two-target run:**

1. `self.item(ev['k'], …)` is keyed by `k` alone → **collision** (Pattern 4).
2. `self.step.setText(f'[{ev["k"]}/{ev["n"]}] …')` shows the wrong denominator when target 2 replans; UI-SPEC rule 12-13 handles this by prefixing the *name*, not by rewriting the counter.
3. `on_finished(code)` (`gui/app.py:237-247`) branches on `code == 0`, `code == 130 or self.cancelled`, else failure. UI-SPEC rules 21-25 give the exact strings for: all built (0), some failed but one built (non-zero with a result), nothing built, cancelled. **The non-zero-with-a-built-target case is new** and must be added to this method, or a partial success would read as a total failure.

### Q3: what each CI job actually runs

**Android (x64 only).** `dm/android/build.py` picks the NDK's host folder itself:

`[VERIFIED: nxnative/dm/android/build.py:14]`
```
ap.add_argument('--ndk', default=os.environ.get('ANDROID_NDK_HOME') or str(DM.parent.parent / 'tools/android-ndk-r27c'))
```
`[VERIFIED: nxnative/dm/android/build.py:27-32]`
```
host = 'windows-x86_64' if os.name == 'nt' else 'linux-x86_64' if sys.platform.startswith('linux') else 'darwin-x86_64'
if sys.platform.startswith('linux') and platform.machine().lower() in ('aarch64', 'arm64'):   # an arm64 NDK's own host folder (community builds: linux-arm64; never prebuilt/*, it also has a linux-x86_64 link)
    host = next((h for h in ('linux-arm64', 'linux-aarch64') if (Path(a.ndk) / 'toolchains/llvm/prebuilt' / h).is_dir()), host)
```
**Pitfall, hard:** on `ubuntu-24.04-arm` that fallback fails (Google's NDK has no `linux-arm64` prebuilt), so `host` stays `linux-x86_64` and the x86_64 `clang` binary is executed on arm64. Use **`ubuntu-22.04`** (x64), which is also where the preinstalled NDK and `ANDROID_NDK_HOME` are documented.

The script needs, beyond the NDK: `dm/games/<GAME>/game.tsv` (`build.py:38` runs `game.py header`), `dm/games/<GAME>/android.tsv` (`build.py:40` runs `android_profile.py header`), `glslc` from the NDK's `shader-tools` (`build.py:43`, with a system `glslc` fallback), and the in-tree `libvpx` sources (`build.py:61`, confirmed present — `nxnative/dm/third_party/libvpx/vp8/**/*.c` exists). It does **not** need .NET, pip, the APK signer, or adb when invoked with just `--game`.

**Apple.** `dm/host/Makefile` is the build; the target needs `GAME`:

`[VERIFIED: nxnative/dm/host/Makefile:3-5]`
```
ifeq ($(strip $(GAME)),)
ifneq ($(filter-out clean,$(or $(MAKECMDGOALS),dmhost)),)
$(error GAME is not set: make GAME=<base game title ID>: $(shell python3 ../games/game.py list | awk -F'\t' '{printf "%s (%s)  ", $$1, $$3}'))
```
`[VERIFIED: nxnative/dm/host/Makefile:79]`
```
dmhost: $(SRC) $(GFX) ../third_party/stb_vorbis/stb_vorbis.c dm.h hle.h romfs_image.h save_sync.h dm_input.h pad_slots.h hle_haptics.h haptics_apple.h motion_fusion.h motion_apple.h motion_pro.h motion_pro_mac.h pad_apple.h pad_hid.h pad_hid_mac.h front.h $(GFX_H) $(GAME_H) $(GAME_STAMP) $(VPX_LIB) $(DAV1D_LIB) $(MSL_H)
```
The recipe on `Makefile:80` is one `clang $(CFLAGS) … -fobjc-arc -o $@ $(SRC) $(GFX) $(VPX_LIB) $(DAV1D_LIB)` followed by twelve `-framework` flags: `Cocoa QuartzCore Metal MetalFX GameController CoreHaptics IOKit AudioToolbox VideoToolbox CoreMedia CoreVideo ImageIO UniformTypeIdentifiers`.

So the Apple job is `make -C nxnative/dm/host GAME=01000A10041EA000 dmhost` (plus `-j`), and it pulls in libvpx **and** dav1d static libraries, the Metal header generation, and twelve system frameworks. Time on a 3-core `macos-26` runner is the unknown, not the correctness: budget `timeout-minutes: 45` and consider `actions/cache` on `nxnative/dm/host/gen` keyed by `hashFiles('nxnative/dm/host/*.c','nxnative/dm/third_party/**')` only if the first run proves slow.

**Why not `compile_check.py` as-is:** it is the *iOS* check — it passes `MSL_SDK=iphoneos`, drops `_mac` sources, and appends `dm/ios/Sources` (`compile_check.py:14,28-29`). The Mac job wants the opposite. Reuse its *technique* (make `-n` → per-file `-c`) only if the link proves too slow; the link is what catches a missing `SRC`, so the recommended gate is the real link.

### Q4: `SRC` is hand-listed, Android globs — and the tree is clean today

`[VERIFIED: nxnative/dm/host/Makefile:19-23]`
```
# Service-layer takeover hle_*.c files are included by wildcard: adding a file does not touch this line (avoids merge conflicts)
SRC=main.c loader.c hle.c crash.c probe.c text_store.c thread.c save_sync.c memstat.m haptics_apple.m $(sort $(wildcard hle_*.c)) front_mac.m entry.S
# NVN null device + nn::vi + the Vulkan layer (dm/gfx/)
# Sources under dm/gfx, dm/gfx/nvn, dm/gfx/tex, dm/gfx/vk and dm/gfx/gl are included by wildcard (tests/ and metal/ do not go into the host): adding a file does not touch this line
GFX=$(sort $(wildcard ../gfx/*.c ../gfx/nvn/*.c ../gfx/nvn/*.m ../gfx/nvn/*.S ../gfx/tex/*.c ../gfx/tex/*.m ../gfx/vk/*.m ../gfx/gl/*.m))
```
`[VERIFIED: nxnative/dm/android/build.py:57]`
```
HOST = [p for p in srcs('host/*.c') if p.name not in ('hle_movie_avc.c', 'hle_movie_av1.c', 'hle_cheats.c')]   # VideoToolbox / GCD: dm/android/movie_avc.c / movie_av1.c / cheats_stub.c instead
```

`dm/host/*.c` holds **48 files**: 40 match `hle_*.c`; the 8 non-`hle_` ones are exactly `main.c loader.c hle.c crash.c probe.c text_store.c thread.c save_sync.c` — all listed. `dm/host/*.m` + `entry.S` are 4 files, all listed. **A drift test passes on today's tree**, which is the precondition for landing it without a sweep.

**Smallest useful test** (goes in `tests/arch_rules.py`, which `tests/test_architecture.py` runs on all four CI hosts):

```python
# 6. dm/host adds a file, the Makefile must learn it (Android globs host/*.c; Mac lists SRC by hand)
mk = (R / 'nxnative/dm/host/Makefile').read_text(encoding='utf-8', errors='replace')
src_line = next(l for l in mk.splitlines() if l.startswith('SRC='))
explicit = set(re.findall(r'[\w.]+\.(?:c|m|S)', src_line.replace('$(sort $(wildcard hle_*.c))', '')))
have = {p.name for p in (R / 'nxnative/dm/host').iterdir() if p.suffix in ('.c', '.m', '.S')}
missing = sorted(n for n in have - explicit if not (n.endswith('.c') and n.startswith('hle_')))
check('dm/host: every source is in the Makefile SRC (or hle_*)', not missing, ', '.join(missing))
```
`arch_rules.py`'s `check()` prints `PASS`/`FAIL` and appends to `fails`, and `test_architecture.py` asserts the subprocess exits 0 — so the failure names the file in the `detail` column and fails the suite on every host. Note `arch_rules.py` shells out to `git ls-files` at import, so the check runs against the committed tree.

### Q5: implicit function declarations — one toolchain is already strict, one is not

| Toolchain | Today | What to change |
|-----------|-------|----------------|
| Android (NDK clang) | already an error — `'-Wno-gnu-folding-constant', '-Werror=implicit-function-declaration', '-Werror=return-type',` `[VERIFIED: nxnative/dm/android/build.py:66]` | nothing |
| Apple (macOS host) | `CFLAGS=-O1 -g -Wall -Wno-unused-function -mmacosx-version-min=$(MACOS_MIN)` `[VERIFIED: nxnative/dm/host/Makefile:18]` — no `-Werror=…`; it "works" only because Apple clang 21 makes it an error by default | add `-Werror=implicit-function-declaration` to that line |
| iOS (`compile_check.py`) | `[VERIFIED: nxnative/dm/ios/tools/compile_check.py:31]` `flags = ['-arch', 'arm64', '-miphoneos-version-min=26.0', '-mcpu=apple-a18', '-fobjc-arc', '-O1', '-w'] + defs + [f'-I{d}' for d in incs + dirs]` — `-w` only suppresses *warnings*; an error-by-default diagnostic survives it | optional: add the flag so the intent is explicit and survives a future `-Wno-…` |

Put the flag **in `CFLAGS` only** (the host's own compile line at `Makefile:80`). The libvpx/dav1d object rules have their own `clang -O2 …` commands (`Makefile:32,45`) and must stay untouched — third-party code is not this phase's business. `[ASSUMED]` that no current `dm/host` or `dm/gfx` source would fail: the last known break (`hle_thread.c` calling `getpagesize()` without `<unistd.h>`) was fixed on 2026-11-03 per project memory, but I could not compile to confirm the tree is clean today — **the first CI run is the verification**, and it is worth landing the flag before the first green run so a latent break surfaces there rather than later.

### Q6: the `dmsh_chain.lock` refusal — text, exit, and how to test it without a .NET runtime

`[VERIFIED: nxnative/dm/gfx/tools/tool_lock.py:36-42]`
```
def check_tools():
    want = dict(l.rstrip('\n').split('\t', 1) for l in open(LOCK) if '\t' in l and not l.startswith('#'))
    now = tools_now(); ran = not now['xlate_source'].startswith(NO_RUN)
    bad = [f'{k}: lock {want.get(k)} / actual {v}' for k, v in now.items() if want.get(k) != v and (ran or k != 'xlate_source')]
    if not ran: bad.append(no_run_message(now['xlate_source']))
    elif now['xlate_source'] != xlate_source_sha(): bad.append(f'the translator was not built from the in-repo source: embedded source {now["xlate_source"]} / in repo {xlate_source_sha()} (rebuild dmsh_xlate)')
    return bad
```
`[VERIFIED: nxnative/dm/gfx/tools/tool_lock.py:52-55]`
```
    elif a == ['--check-tools']:
        bad = check_tools()
        for b in bad: print('[RED] translation chain tools do not match the lock file: ' + b)
        sys.exit(1 if bad else 0)
```

**Test design (no Xcode, no .NET, works on all four CI hosts):** `tool_lock` is import-safe — it only inserts its own directory on `sys.path` and imports `LOCK`, `XLATE_DIR`, `SPIRV_CROSS`, `xlate_source_sha` from `dmsh_chain` (`tool_lock.py:8-9`), and `dmsh_chain` has no import-time work (`dmsh_chain.py:14,27,30,32` are constants). So:

1. `sys.path.insert(0, str(REPO / 'nxnative/dm/gfx/tools'))`, `import tool_lock`.
2. Monkey-patch **both** `tool_lock.LOCK` (a temp file with one `key\tvalue` line) and `tool_lock.tools_now` (a dict returning a wrong value for that key) — patching `tools_now` is mandatory because the real one calls `xcrun` (`tool_lock.py:21`) and would raise `FileNotFoundError` on Linux/Windows.
3. Assert `check_tools()` returns `['<key>: lock <a> / actual <b>']`.
4. For the *exit* and the *wording*, the current `__main__` block is untestable (it calls `sys.exit` inline). Recommended small refactor: hoist the prefix into a module constant and give the file a `main(argv)` returning the code, so a test asserts `tool_lock.main(['--check-tools']) == 1` and the captured line equals `[RED] translation chain tools do not match the lock file: <key>: lock … / actual …`. That is the "remedy text cannot rot" guard QUAL-09 asks for; asserting only `check_tools()` would leave the `[RED]` sentence and the exit code unguarded.

Also worth asserting: `no_run_message()` (`tool_lock.py:34`) still names `brew install --cask dotnet-sdk` and `DOTNET_ROOT` — that is the remedy a player actually reads.

### Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| "Which stages for this target" | A new stage table or descriptor | `Port.run()` / `Port.run_mac()` as they are | They already encode 20 stages with reuse keys, `PROG.plan` counts and per-stage logging |
| "Share extraction between targets" | A pre-pass that extracts once then hands folders down | The existing reuse keys (`extract()` skips when `(ex / v)` exists) | Extracting into a second folder would double the disk cost and break `check_space` |
| Adding `platform` to events | Editing `nxnative/scripts/build_ipa_from_nsp.py` | `porter/runlog.py`'s `_wrap` | The subtree is upstream; `porter/` is the fork's glue |
| A per-target argv builder in the GUI | Three branches inside `start()` | One helper mapping the two boxes → one of three `--platform` values | UI-SPEC rule 8: "through one helper, never from" ad-hoc checks |
| Deciding "is this profile Android-ported" | A new check in `gui/app.py` or `run_both()` | `profiles.by_title()` / `android.tsv` in `inputs()` | One owner; the GUI must not read the profile (UI-SPEC rule 26) |
| Compiling the host in CI with a bespoke command | A hand-written `clang` line per job | `make … dmhost` and `build.py --game …` | Both scripts own flags, source lists and post-link checks |
| Downloading an NDK | curl/cache/setup-android | The image's preinstalled NDK via `ANDROID_NDK_HOME` | Zero bytes, zero new pins |

**Key insight:** every hard part of this phase already exists in the repo — two stage sequences, two work folders, reuse keys, a toolchain lock and a hand-listed Makefile. The phase's risk is not in *building* the mechanisms but in the three seams that were written assuming one target: `k` in the GUI, `PROG.plan` per run, and `result` being one flat dict.

## Runtime State Inventory

> Included because this phase is a *protocol migration* as much as a feature: the `result` event and the `stage`/`step`/`progress` events are consumed outside this process (goldens, saved logs). A grep of the repo does not find the consumers' expectations — the files below do.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data (golden streams) | `tests/fixtures/bridge/port_ok.jsonl`, `install_ok.jsonl`, `port_build_error.jsonl`, `edge.jsonl`. `record.py:5` states the contract: "The protocol only grows additively (no version field), so old fixtures stay valid." | **Keep the three generated goldens byte-identical**; add `port_both.jsonl` (regenerate with `.venv/bin/python tests/fixtures/bridge/record.py`, or by hand from `record.py --emit`), never edit the old three |
| Stored data (saved logs) | `<user dir>/logs/<stamp>-port.log`, written by `porter/runlog.py`; `result` carries `log` (`runlog.py:115`) | No change: the log is text. The plan should make `run_both()` note both targets in the log (`say`) so a reader of the log sees two outcomes (D-08) |
| Live service config | none (no service, no daemon, no schedule) — verified by reading the phase's surfaces: CLI, GUI, CI only | None |
| OS-registered state | none. The one port-at-a-time lock is `<tid>_build/.porter.lock`, taken per folder (`docs/ARCHITECTURE.md` §protocol, "One port or install of a game folder at a time"); a `both` run takes it once, and the child `Port` objects must **not** try to take it again | Verify the lock is taken by the outer run only; if it is taken in `Port.run()`, a child would deadlock or refuse with "already running" |
| Secrets / env vars | `NX2A_HOME` (isolation in tests), `NX2A_GUI` (stop channel), `DM_GAME`/`DM_TARGET`/`DM_ROOT` (`pipeline.py:180,321`), `ANDROID_NDK_HOME` (CI) | No new variable. `DM_TARGET` is already per-target (`'apple' if self.mac else 'android'`) and each child sets it itself — do not hoist it into the parent env |
| Build artifacts / installed packages | `work/android` vs `work/mac` inside `<tid>_build`; `<user dir>/tools/dmsh_xlate-<key>`; `gen/msl-<sdk>/host_msl_gen.h`; `gen/game.stamp` | No migration. A `both` run writes both folders; existing single-target folders keep working (`self.aw` is chosen by target, `pipeline.py:176`) |

**The one state risk worth a task:** the golden fixtures are the contract. If `result.targets[]` were emitted *for single-target runs too*, `port_ok.jsonl` would no longer match a fresh recording and the replay test would keep passing against a stale file — a slow rot. Emit `targets[]` only for `--platform both`, exactly as UI-SPEC line 307-308 says.

## Common Pitfalls

### Pitfall 1: `paths:` on the wrong workflow level
**What goes wrong:** adding `paths: [nxnative/**, .github/**]` to `fork-ci.yml` makes the entire four-host test matrix skip on documentation-only pushes.
**Why it happens:** GitHub applies `paths` to the *event*, not the job; `fork-ci.yml:6-9` is `on: push: / pull_request: / workflow_dispatch:` with no filters today.
**How to avoid:** a second workflow file with its own filters.
**Warning signs:** a docs-only PR where the only checks that report are the two host builds.

### Pitfall 2: the arm64 runner and `build.py`'s host detection
**What goes wrong:** on `ubuntu-24.04-arm`, `host` stays `linux-x86_64` (Google's NDK ships no `linux-arm64` prebuilt) and the workflow tries to execute an x86_64 `clang`.
**Why it happens:** `build.py:27-29` only switches when it *finds* `linux-arm64`/`linux-aarch64`.
**How to avoid:** run the Android job on `ubuntu-22.04` (x64). If arm64 is ever wanted, the NDK must be the community build — out of scope here.
**Warning signs:** `Exec format error` / `cannot execute binary file` on the first compile.

### Pitfall 3: `MACOS_MIN` (26.6) newer than the runner's SDK (26.5)
**What goes wrong:** `macos-26`'s default Xcode 26.6 carries SDK `macosx26.5`, while `nxnative/dm/mac/min_os.mk:3` pins `MACOS_MIN := 26.6`. Compiling and linking with a deployment target above the SDK is usually tolerated (it is only an `LC_BUILD_VERSION`), but it produces linker warnings and is not a state to depend on.
**Why it happens:** the repo targets the Mac the port is built on (macOS 26.6), the image is one SDK behind.
**How to avoid:** let make override it from the SDK, no tree edit — command-line variables beat `:=` in a makefile: `make -C nxnative/dm/host GAME=… dmhost MACOS_MIN=$(xcrun -sdk macosx --show-sdk-version)`. `[ASSUMED]` that this is needed at all; the first run decides.
**Warning signs:** `ld: warning: building for macOS 26.6, but linking with dylib built for macOS 26.5`, or an outright availability error in one source.

### Pitfall 4: no Metal toolchain on the runner
**What goes wrong:** `xcrun -sdk macosx metal --version` fails, so `host_msl.py` writes a header with the *sources* only and the host would compile MSL at run time. The CI job still passes — which is fine — but nobody should later believe CI proved the MSL shaders compile.
**Why it happens:** recent Xcode needs `xcodebuild -downloadComponent MetalToolchain`, and the runner README does not list it.
**How to avoid:** accept it (the host build is the gate, not MSL), and say so in the workflow's comment; add the `-downloadComponent` step only if MSL compilation in CI is wanted (it downloads a compiler that does *not* match `dmsh_chain.lock`, which is why the Mac shader chain is not in this phase's scope).
**Warning signs:** the step log line `host_msl.py: no Metal compiler for macosx … the host compiles its shaders at run time`.

### Pitfall 5: two targets, one `k`, one stage tree
**What goes wrong:** target 2's `stage` events reuse `k = 1, 2, …`, so `self.items[k]` overwrites target 1's rows and the tree ends up showing only the Mac chain.
**Why it happens:** `PROG.plan()` resets `k` (`pipeline.py:115` and `:470` are two separate plans) and the GUI keys on `k` (`gui/app.py:196-199`).
**How to avoid:** key on `(platform, k)` and prefix the Stage column for multi-target runs; add a test that replays `port_both.jsonl` and asserts **two** top-level rows groups / four rows, not two.
**Warning signs:** a 9-row tree after a `both` run whose Android stages read as Mac stages.

### Pitfall 6: the exit code contract, silently changed
**What goes wrong:** a `both` run where the Mac chain failed returns 0 because `_with_progress` does `fn(); return 0` (`cli.py:120`), and `Port.run()` merely returns a dict.
**Why it happens:** the pipeline has no channel for "succeeded with a failed part".
**How to avoid:** let `fn()` return the code (`return fn() or 0` at `cli.py:120`) and have `cmd_port`'s lambda return `1` when any `targets[].status == 'failed'` — do **not** raise, because raising would add an `error` event after `result` and `runlog` would log the run as failed.
**Warning signs:** `porter port --platform both; echo $?` printing 0 with `"status": "failed"` in the result.

### Pitfall 7: `install_now()` loses its paths
**What goes wrong:** `install_now()` reads `self.result['data']` and `self.result['apk']` (`gui/app.py:177`). If a `both` run's `result` contained *only* `targets[]`, Install on device would break even though the APK was built.
**Why it happens:** D-08 says "gains a per-target list", which is additive, but a careless implementation would replace the flat fields.
**How to avoid:** keep the top-level keys filled from whichever targets built, and add `targets[]` beside them; `TargetRow` reads `targets[]` and `out`, Install reads the Android entry (or the top-level `apk`/`data`).
**Warning signs:** Install enabled but pressing it raises `KeyError: 'data'`, or disabled after a successful Android build in a `both` run.

### Pitfall 8: `-Werror=implicit-function-declaration` landing on third-party code
**What goes wrong:** adding the flag to a global `CFLAGS` that also feeds the libvpx/dav1d rules turns a working third-party build red.
**Why it happens:** `dm/host/Makefile` has three separate `clang` lines (`:32`, `:45`, `:80`); only `:18`'s `CFLAGS` is the host's.
**How to avoid:** edit `CFLAGS` only; leave `:32`/`:45` alone.
**Warning signs:** failures whose paths start with `../third_party/`.

### Pitfall 9: `host_msl`'s `FORCE` regenerating on every CI run
**What goes wrong:** the Metal header rule is `$(MSL_H): $(MSL_SRC) ../gfx/tools/host_msl.py FORCE` (`Makefile:56`) and `game_profile.h` is regenerated every build too (`Makefile:64`) — so caching `gen/` helps less than expected.
**Why it happens:** the design wants a toolchain recheck every build (which is exactly right locally).
**How to avoid:** don't build a caching story on `gen/` beyond the third-party object folders (`gen/vpx`, `gen/dav1d`), and only if the first CI run is slow.
**Warning signs:** a "cache hit" job that still takes the full time.

## Code Examples

### The verified anchors a plan will point at

`[VERIFIED: porter/pipeline.py:83]`
```
        self.mac = opts.platform in ('mac', 'mac-app')   # a Mac app, built on a Mac: run_mac's stages instead of the Android port's
```
`[VERIFIED: porter/pipeline.py:91]`
```
        if o.platform not in ('android', 'mac', 'mac-app'): raise BuildError(f'platform must be android or mac-app: {o.platform}')
```
`[VERIFIED: porter/pipeline.py:109]`
```
        if self.mac: return self.run_mac()   # everything below is the Android port's
```
`[VERIFIED: porter/pipeline.py:176]`
```
        self.aw = self.work / ('mac' if self.mac else 'android'); self.logs = self.work / 'logs'
```
`[VERIFIED: porter/pipeline.py:321]`
```
        nsp.rewrite(PY, NXNATIVE, self.game / 'ExeFS', self.patched, dict(self.env, DM_TARGET='apple' if self.mac else 'android'), self.logs, self.g)
```
`[VERIFIED: porter/pipeline.py:466-467]`
```
        if sys.platform != 'darwin': raise BuildError('a Mac app is built on a Mac: it runs the game\'s own arm64 code natively and links with Xcode (--platform mac-app needs macOS)')
        if not nsp.apple_silicon(): raise BuildError('a Mac app is built on Apple silicon: the Mac host runs the game\'s own arm64 code natively')
```
`[VERIFIED: porter/pipeline.py:487-488]`
```
def emit_result(r):   # the last JSON event of a port (the GUI's done screen); a summary line in the other modes
    if PROG.mode == 'json': PROG._json({'ev': 'result', **r})
```
`[VERIFIED: porter/cli.py:24]`
```
    po.add_argument('--platform', choices=('android', 'mac-app'), default='android',
```
`[VERIFIED: porter/cli.py:137]`
```
    opts = pipeline.Options(folder=Path(a.folder), keys=Path(a.keys) if a.keys else None, out=Path(a.out) if a.out else None, version=a.version, language=a.language,
```
`[VERIFIED: porter/cli.py:140]`
```
    return _with_progress(a.progress, lambda: pipeline.emit_result(pipeline.Port(opts).run()))
```
The `Options(...)` call spans `cli.py:137-139`; `:140` is the whole exit-code path for a port.

### The protocol additions (UI-SPEC, verbatim)

`[VERIFIED: .planning/phases/11-compile-the-c-host-in-ci/11-UI-SPEC.md:307-311]`
```
- `result` gains `targets: [{platform: 'android'|'mac-app', status: 'ok'|'failed'|'skipped',
  out: <absolute package path or ''>, reason: <string or ''>}]`, present only for a run with
  more than one target. Single-target runs keep today's shape (`apk`, `data`, `app`,
  `platform`).
- `stage`, `step` and `progress` gain `platform`, so the Stage column and the step line can
```
**Note the word mapping:** the *protocol* says `ok`, the *row word* is `built` (`✓ built`). The GUI maps `ok → built`, `failed → failed`, `skipped → skipped` — do not invent a fourth word.

### The two exact argv shapes the GUI must produce (UI-SPEC rule 8)

`[VERIFIED: .planning/phases/11-compile-the-c-host-in-ci/11-UI-SPEC.md:217-219]`
```
   - both ticked → `--platform both`
   - only `android` → `--platform android`
   - only `mac` → `--platform mac-app`
```
and `--install`/`--device` only while `android` is ticked (rule 9).

## Environment Availability

> The phase's external dependencies are (a) the two CI runner images and (b) the developer machine for local verification. No command could be run this session, so the local column records what the repo says rather than a probe. **The plan's first task should probe locally** (`python -m unittest discover tests`, `make -C nxnative/dm/host GAME=01000A10041EA000 -n dmhost`).

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `macos-26` runner (arm64) | Apple CI job | ✓ (GA per the runner-images README, this session) | Xcode 26.6, SDK 26.5 | `macos-15` (arm64, older SDK) or the `xcode-27` preview |
| `ubuntu-22.04` runner (x64) | Android CI job | ✓ | NDK 27.3.13750724, Python 3.10.12 | `ubuntu-24.04` (x64) — **not** the `-arm` variant |
| In-tree `dm/third_party/libvpx` + `dav1d` sources and `config/` headers | both builds | ✓ verified by glob (`vp8/**/*.c`, `config/*.h`) | in tree | — |
| `dm/games/01000A10041EA000/{game.tsv,android.tsv}` | both builds, `GAME=` | ✓ verified by glob | — | another committed profile with an `android.tsv` |
| NDK locally (`tools/android-ndk-r27c` or `ANDROID_NDK_HOME`) | Android link, a local warm port | `[ASSUMED]` present on the dev Mac (project memory and `porter/pins.py` say r27c is the expected one) | r27c | the preinstalled `tools/` folder; the CI job needs none |
| Xcode + `xcrun metal` locally | Mac host build | `[ASSUMED]` present (the Mac app was built from this tree on 2026-11-04 per project memory) | Xcode 27.2 is the *shader* chain's pinned compiler | — |

**Missing dependencies with no fallback:** none identified.
**Missing dependencies with fallback:** the Metal toolchain on the Apple runner (falls back to a sources-only header, by design).

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | Python `unittest` (stdlib). No pytest, no config file |
| Config file | none — "[d]iscovery is controlled by the command line" (`[VERIFIED: .planning/codebase/TESTING.md:15]`) |
| Quick run command | `python -m unittest tests.test_porter tests.test_bridge tests.test_architecture` |
| Full suite command | `python -m unittest discover -v tests` (what CI runs, `fork-ci.yml:52`), then `python tests/arch_rules.py` for the per-check PASS/FAIL list |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|--------------|
| QUAL-13 | `--platform both` runs Android then Mac, one `result`, one row per target | unit (argv + driver with fakes) | `python -m unittest tests.test_porter.<Both>` | ❌ Wave 0 |
| QUAL-13 | A failing Android target does not stop the Mac target; exit is 1 with one built | unit (`run_both` with a child raising `BuildError`) | same module | ❌ Wave 0 |
| QUAL-13 | No `android.tsv` → Android `skipped` with the reason, Mac still built | unit (fake profile dir, like `Experimental.test_ios_profile_copied_with_experimental_android_tsv`) | same module | ❌ Wave 0 |
| QUAL-13 | Off-darwin, a Mac request is `skipped`, never `failed` | unit (`mock.patch('sys.platform', 'linux')`-style, or an injectable platform) | same module | ❌ Wave 0 |
| QUAL-07 | Two boxes → three `--platform` values; no zero-target state; Mac disabled off macOS | unit (construct `PortTab`, click) | `python -m unittest tests.test_bridge` | ⚠️ extend (the `Fake`/`Close` classes already drive the real view) |
| QUAL-07 | One `result` with `targets[]` draws two rows, each with its own Reveal; `ok` renders as `built` | replay | `python -m unittest tests.test_bridge.Replay.test_port_both` | ❌ Wave 0 (needs `port_both.jsonl`) |
| QUAL-09 | `dm/host/*.c` not in `SRC` and not `hle_*.c` fails naming the file | static | `python tests/arch_rules.py` (via `tests.test_architecture`) | ❌ Wave 0 (new `check()`) |
| QUAL-09 | `dmsh_chain.lock` mismatch: message + exit 1 | unit (patched `LOCK` + `tools_now`) | `python -m unittest tests.test_tool_lock` | ❌ Wave 0 |
| QUAL-09 | Apple and Android hosts compile in CI | CI job | `host-build.yml` (no local command needed) | ❌ Wave 0 (workflow) |

### Sampling Rate
- **Per task commit:** the quick run (`tests.test_porter tests.test_bridge tests.test_architecture`), < 60 s.
- **Per wave merge:** `python -m unittest discover -v tests` (the gate CI runs on four hosts).
- **Phase gate:** full suite green **and** both `host-build.yml` jobs green on a push that touches `nxnative/**`.

### Wave 0 Gaps
- [ ] `tests/test_porter.py` — a `Both` class (order, skip-on-no-android.tsv, skip-off-darwin, failure isolation, exit code); the file already boots `pipeline.Port(pipeline.Options(...))` with no game files (`MacTarget.test_platform_option_reaches_the_port`)
- [ ] `tests/test_bridge.py` — `Replay.test_port_both` + a `PortTab` Targets-row test; `tests/fixtures/bridge/port_both.jsonl` generated from `record.py` (add a `BOTH` stage list and an `emit_result` with `targets[]`)
- [ ] `tests/test_tool_lock.py` — synthetic lock mismatch; needs `tool_lock.main(argv)` to exist
- [ ] `tests/arch_rules.py` — the `SRC` drift `check()` (no new file)
- [ ] `.github/workflows/host-build.yml` — the two jobs
- [ ] Framework install: none (stdlib `unittest`, already in `requirements.txt`'s environment)

## Security Domain

> `security_enforcement` is not disabled in `.planning/config.json` (no such key seen while reading the phase's context), so this section is included.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | No user, no session |
| V3 Session Management | no | — |
| V4 Access Control | no | Local desktop tool, single user |
| V5 Input Validation | yes | The new inputs are: two QCheckBox states (two booleans), one `--platform` choice from `choices=(...)`, and the `targets[]` list read by the GUI. Validate at the CLI parser (`argparse` `choices`), and keep the GUI's rendering of porter's `reason` as **plain text** (`Qt.PlainText`, UI-SPEC rule 26-27) so a profile path containing `<`/`&` cannot become markup |
| V6 Cryptography | no | Nothing new is signed or hashed; the APK signer and `dmsh_chain.lock` fingerprints are untouched |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Unpinned CI action (supply chain) | Tampering | Every action pinned to a full commit SHA with a `# vX.Y.Z` comment, `permissions: contents: read`, `persist-credentials: false` — the existing `fork-ci.yml` rule, carried into the new workflow (`[VERIFIED: .github/workflows/fork-ci.yml:2,11-12,38-40]`) |
| A new workflow that runs repo code on a `pull_request` from a fork with a writable token | Elevation of privilege | The new workflow takes the default read-only token and declares `permissions: contents: read`; it runs `make`/`python` only, never a script from the PR's own untrusted input |
| Build script mis-invoked with attacker-controlled paths | Tampering | CI passes only a constant `GAME=01000A10041EA000`; no PR-derived string reaches `game.py`, `android_profile.py` or `build.py` |
| A `skipped`/`failed` reason rendered as HTML in the Port view | Spoofing / XSS-equivalent in Qt rich text | The reason is porter's own sentence, shown with `Qt.PlainText` (UI-SPEC rule 26), never `setTextFormat(Qt.RichText)` |
| The exit code "green run hides a broken target" | Repudiation | D-06's non-zero exit + the `host-build.yml` jobs' blocking status; a test asserts the exit code, not just the rows |

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `porter` pinned `DM_TARGET='android'` and the Mac app existed only via `build_ipa_from_nsp.py --platform mac-app` | `porter port --platform mac-app` with `run_mac()`, a per-target work folder and reuse keys | 2026-11-04 (Phase 9's CLI half, landed early) | The phase's driver has something to drive; no rewrite needed |
| CI = the Python suite only; "CI never compiles the C host" | Two host-compile jobs on every `nxnative/**` push | this phase | The Apple clang 21 class of break becomes visible on the push that causes it |
| GitHub hosted macOS runners were Intel or 15.x | `macos-26` (arm64, GA); `macos-latest` now points at it | 2025-2026 | `macos-15` in `fork-ci.yml`'s matrix still works (arm64), but the host job should use `macos-26` for the SDK |

**Deprecated/outdated:**
- `macos-14`: retired 2026-11-02 — do not use in the new workflow.
- `android-actions/setup-android`-style actions: unnecessary here; the toolchain is preinstalled.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The current `dm/host` + `dm/gfx` sources compile clean under `-Werror=implicit-function-declaration` | Q5 | A red Apple CI job on the first push, and the flag has to be landed with a small fix-up commit rather than in isolation. Low risk: the known break was fixed 2026-11-03 |
| A2 | `-mmacosx-version-min=26.6` with the runner's macOS 26.5 SDK links without an error | Pitfall 3 | The Apple job fails on the first run; fix is a one-line `MACOS_MIN=$(xcrun … --show-sdk-version)` override, no tree change |
| A3 | `make -C nxnative/dm/host dmhost` completes inside 45 min on a `macos-26` runner | Q3 | A timeout; mitigation is `actions/cache` on `gen/vpx`+`gen/dav1d`, or falling back to per-file `-c` (weaker gate) |
| A4 | The dev Mac still has the NDK and Xcode the phase needs to verify both targets by hand | Environment | A manual verification step has to be reshaped around what is installed |
| A5 | The `macos-26` image lacks the Metal toolchain (so `host_msl.py` degrades) | Pitfall 4 | If it *is* present, CI additionally verifies MSL — strictly better; if absent, CI silently does not |

## Open Questions

1. **Where does the one-run lock live?**
   - What we know: `docs/ARCHITECTURE.md` says a port takes `<tid>_build/.porter.lock` for the folder; `runlog.build_folder()` and the marker `.port-running` exist.
   - What's unclear: whether the lock is taken in `runlog.run()` (once per process) or in `Port.__init__/run()`. If it is per `Port`, the second child would refuse with "already running".
   - Recommendation: read `porter/runlog.py`/`pipeline.py` for the lock call before writing `run_both()`; if it is inside `Port.run()`, the driver needs an `Options`-level opt-out or must take the lock itself once. **This is the single most likely implementation trap.**

2. **Does `result` keep the flat keys in a `both` run?**
   - What we know: D-08 says "gains a per-target list"; UI-SPEC says `targets[]` is "present only for a run with more than one target" and that a *single*-target run keeps `apk`/`data`/`app`/`platform`.
   - What's unclear: whether the flat keys should also be filled in a `both` run. `install_now()` (`gui/app.py:177`) reads `self.result['data']` and `['apk']`, so leaving them out breaks Install after a successful Android build.
   - Recommendation: keep them (additive), filled from whichever target built; assert in a test that a `both` result carries `apk`+`data` when Android built. If the user prefers the strict reading, `install_now()` must instead read the Android entry, and the entry needs both paths (today `targets[]` has a single `out`).

3. **Should the two CI jobs be *required checks*?**
   - What we know: D-09 says "blocking". A GitHub job is only blocking if branch protection lists it.
   - What's unclear: whether this repo has protection configured (not in the tree).
   - Recommendation: note it as a one-line manual step in the plan's task list ("add `host-build / host-apple` and `host-build / host-android` to the branch protection rules"), and remember that path-filtered required checks stay "pending" on PRs that do not touch the paths — either accept it or add an always-running gate job.

4. **Does the GUI need a per-target `[k/n]`?**
   - What we know: UI-SPEC rule 12-13 prefixes the *name*; the counter is left as porter sends it.
   - What's unclear: whether `[3/19]` on the Mac chain (after a 15-stage Android chain) will read as a bug to the user.
   - Recommendation: implement the UI-SPEC as written; if it reads badly in UAT, the cheap fix is a monotonic `k` in the driver, not a GUI change.

## Sources

### Primary (HIGH confidence)
- In-repo, read this session: `porter/pipeline.py` (lines 21-39, 83, 89-132, 135-176, 144-155, 321, 329-362, 396-407, 445-488), `porter/cli.py` (6-56, 115-140, 214-218), `porter/runlog.py` (93-122, 115-117), `gui/runner.py` (44-122, 133-145), `gui/app.py` (19, 51-105, 160-181, 196-257), `gui/firstrun.py` (15, 22, 63, 218), `nxnative/dm/host/Makefile` (1-80), `nxnative/dm/android/build.py` (1-132), `nxnative/dm/mac/min_os.mk`, `nxnative/dm/ios/tools/compile_check.py`, `nxnative/dm/gfx/tools/tool_lock.py`, `nxnative/dm/gfx/tools/dmsh_chain.py` (14-92), `nxnative/dm/gfx/tools/host_msl.py`, `.github/workflows/fork-ci.yml`, `tests/arch_rules.py`, `tests/test_architecture.py`, `tests/test_porter.py` (327-351), `tests/test_bridge.py` (505-523), `tests/fixtures/bridge/record.py`, `tests/fixtures/bridge/port_ok.jsonl`, `porter/profiles.py`, `.planning/codebase/TESTING.md`, `.planning/*` artifacts listed above
- `https://raw.githubusercontent.com/actions/runner-images/main/README.md` — image labels and status (macOS 26 arm64 GA, macOS 14 retired 2026-11-02)
- `https://raw.githubusercontent.com/actions/runner-images/main/images/macos/macos-26-arm64-Readme.md` — Xcode 26.6 default, macOS 26.5 SDK, NDK 27.3.13750724 / 28.2 / 29.0 preinstalled
- `https://raw.githubusercontent.com/actions/runner-images/main/images/ubuntu/Ubuntu2204-Readme.md` — NDK 27.3.13750724 default with `ANDROID_NDK_HOME`, Python 3.10.12

### Secondary (MEDIUM confidence)
- GNU make's "command-line variable overrides a makefile assignment" semantics (used for the `MACOS_MIN` override; standard documented behaviour)
- GitHub Actions' workflow-level `paths` filtering (used for the "new workflow, not a new filter" conclusion; standard documented behaviour)

### Tertiary (LOW confidence)
- None used as a basis for a recommendation. Items that would need a run to confirm are in the Assumptions Log instead.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no packages, and every toolchain version came from the runner-images READMEs this session
- Architecture (driver, protocol, GUI): HIGH — every seam quoted with a line range from the file that owns it
- CI design: HIGH on job shape and toolchain availability; MEDIUM on run time and the deployment-target/SDK mismatch (A2, A3)
- Pitfalls: HIGH for 1, 2, 4, 5, 6, 7, 8, 9 (each traces to a quoted line); MEDIUM for 3 (assumed symptom)

**Research date:** 2026-11-04
**Valid until:** ~2026-12-04 for the repo facts (fast-moving working tree — `porter/pipeline.py` changed as recently as 2026-11-04); ~2027-01 for the runner-image labels (they rotate on a multi-month cadence, and `macos-15` will eventually follow `macos-14`)

*Phase: 11-compile-the-c-host-in-ci*
*Researched: 2026-11-04*


