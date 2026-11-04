# Roadmap: nx2android

## Overview

This milestone takes the Windows-only PySide6 GUI to four hosts and reworks it for testers. It starts with the long-lead risk: today's GUI, with a fixed process bridge, built, signed and smoke-tested by CI on Windows x64, macOS Apple Silicon, Linux x64 and Linux arm64. Porter hardening comes next, so killed or hostile runs can't corrupt builds or lose the signing key. The new GUI then arrives in vertical slices, each a porter-owned JSON command plus a view that displays it: host toolchains with a guided first run, the game library with per-game settings, and the device manager with diagnostics. The milestone ends when the new GUI becomes the default and testers port a playable title end to end on every host.

Phases 7–14 are a second workstream in the same milestone: what a port costs, the parity between its targets, and the loop that catches regressions (plan of record: `docs/TOOLING_PLAN.md`, whose T0–T7 are these phases in order). They are independent of the GUI slices except for one edge: Phase 9 must land before Phase 4 is planned, or the Port view's target choice is built twice.

## Phases

**Phase Numbering:**

- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Bridge, Bundles and CI** - Today's GUI stops runs cleanly, reports real errors, and ships as a CI-built bundle on all four hosts (completed 2026-10-30)
- [x] **Phase 2: Porter Hardening** - Ports survive kills, hostile archives and tampered downloads without losing builds or the signing key (completed 2026-10-31)
- [ ] **Phase 3: Host Toolchains and Guided First Run** - A fresh tester on any host reaches a ready setup by following the GUI
- [ ] **Phase 4: Game Library and Per-Game Settings** - Users port games and manage them in one library, with settings porter keeps per game
- [ ] **Phase 5: Device Manager and Diagnostics** - Users see device compatibility, manage ports per device, and copy a full diagnostics report
- [ ] **Phase 6: Switch-Over and Tester Verification** - The new GUI becomes the default and testers port a playable title end to end on every host
- [ ] **Phase 7: Measure what a port costs** - Every stage reports its wall clock and reuse outcome, so no claim about the pipeline rests on a guess
- [ ] **Phase 8: Make the cold shader stage predictable** - The shader stage announces its work and ETA, caps workers by RAM, and recomputes nothing it already has
- [ ] **Phase 9: One port entry point for Android and Mac** - `porter port --platform` yields both packages with one reuse model, one log format and one event protocol
- [ ] **Phase 10: Move saves between devices** - A player continues the same title on the phone and on the Mac, with a build mismatch refused cleanly
- [ ] **Phase 11: Compile the C host in CI** - One run makes an APK, a Mac app or both as the user chooses; CI compiles the host per target so a break names the push that caused it
- [ ] **Phase 12: One command that verifies a change** - Suite, warm re-ports and a device smoke give one verdict before a host commit
- [ ] **Phase 13: Guards from past incidents** - Each class of bug this repo has already paid for is locked out by a test
- [ ] **Phase 14: Keep the upstream pick cheap** - The distance to upstream is visible on every push and warned before it becomes a wall

## Phase Details

### Phase 1: Bridge, Bundles and CI

**Goal**: Today's GUI controls runs reliably and reaches testers as a CI-built bundle on Windows x64, macOS Apple Silicon, Linux x64 and Linux arm64
**Depends on**: Nothing (first phase)
**Requirements**: BRDG-01, BRDG-02, BRDG-03, BRDG-04, BRDG-05, BRDG-06, PKG-01, PKG-02, PKG-03, PKG-04, PKG-05, PKG-06, CI-01, CI-02, CI-03, CI-04, TEST-02, TEST-03
**Success Criteria** (what must be TRUE):

  1. A tester on each host downloads the release bundle and starts the GUI without installing Python: the Windows zip runs after unzipping, the notarized DMG opens from Finder on macOS 14+ with no Gatekeeper warning, and both Linux tarballs run under X11 and Wayland. A full port run from a read-only bundle location leaves the bundle unchanged, and `codesign --verify --strict` still passes on the `.app` afterwards.
  2. Cancel during a port leaves no dotnet, MSBuild, clang or shader-tool process on any host while the adb server keeps running, and the GUI shows "cancelled" only once the run has stopped. Closing the window mid-port asks first, and confirming stops the run the same way.
  3. When a porter command fails, crashes or hangs, the GUI shows the real cause, or a timeout message with Retry, never a swallowed stderr or "no game found". The full saved log of any run opens from the GUI.
  4. Every push runs the test suite on all four OSes, installed from the hashed lockfile, including headless GUI bridge tests that replay golden JSON-lines fixtures. A missing optional engine module (e.g. `lz4`) shows up as a clear skip, not an import failure.
  5. The release workflow builds all four bundles, signs and notarizes the macOS one, smoke-tests each frozen bundle, and reports the Linux glibc symbol floor and the `nxnative/` diff against upstream. Its signing secrets sit in a protected environment that pull-request workflows cannot reach, and every action is pinned by SHA.

**Plans**: 10/10 plans complete

Plans:
**Wave 1**

- [x] 01-01-PLAN.md — Hashed universal lockfile (runtime, build, dev) and the reviewed .venv (wave 1)
- [x] 01-05-PLAN.md — Read-only bundle: resource root and per-version engine copy in the player's folder (wave 1)

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 01-02-PLAN.md — Porter run logs, log/error events, JSON one-shot errors, stop channel with Job Object, cut-off marker (wave 2)
- [x] 01-06-PLAN.md — Per-OS bundles (zip, signed .app in a DMG, tar.gz), read-only smoke test, glibc floor, install guide (wave 2)

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 01-03-PLAN.md — GUI: real cause and Open log, tree-wide Cancel with "stopping…", close confirmation (wave 3)

**Wave 4** *(blocked on Wave 3 completion)*

- [x] 01-04-PLAN.md — GUI: one-shot timeouts with Retry, real errors in every view, golden JSON-lines replays (wave 4)

**Wave 5** *(blocked on Wave 4 completion)*

- [x] 01-07-PLAN.md — fork-ci.yml on four hosts from the lock, TEST-02 skip, first green run (wave 5)

**Wave 6** *(blocked on Wave 5 completion)*

- [x] 01-08-PLAN.md — fork-release.yml: build, sign, notarize, smoke, glibc and upstream-diff reports, draft release (wave 6)

**Gap closure** *(UAT gaps G-01-6, G-01-7)*

- [x] 01-09-PLAN.md — porter's own SSL context: downloads trust the host's CA file when the bundled OpenSSL has none (G-01-6, wave 1)
- [x] 01-10-PLAN.md — Linux bundles without PySide6's gtk3 theme and the runner's GTK3/GIO stack; release run and frozen-bundle checks for both gaps (G-01-7, G-01-6, wave 2)

**UI hint**: yes

### Phase 2: Porter Hardening

**Goal**: Ports survive interruption, hostile archives and tampered downloads without corrupting builds or losing the signing key
**Depends on**: Phase 1
**Requirements**: HARD-01, HARD-02, HARD-03, HARD-04, HARD-05, HARD-06, HARD-07, HARD-08, HARD-09, HARD-10, PKG-07, TEST-01
**Success Criteria** (what must be TRUE):

  1. Crafted zip and tar archives with `..`, absolute paths or symlinks are refused and write nothing outside the unpack folder, and porter refuses to run on a Python without the CVE-2025-4517 tarfile fix (below 3.11.13, 3.12.11 or 3.13.4 and lacking `os.path.ALLOW_MISSING`).
  2. A port killed at any stage redoes that stage on the next run, a crash during the data-pack swap leaves the game with a working pack, and starting a second port of the same game folder shows "already running".
  3. Each downloaded toolchain, NuGet package and FPSLocker config is checked against the exact version and hash recorded in one manifest, the FPSLocker hash appears in the port log, and a mismatch stops with a clear message.
  4. The signing key is created atomically with mode 0600, and when the key file exists but can't be read, porter stops with an error instead of making a new key.
  5. Every item in `.planning/codebase/CONCERNS.md` is closed (escaped game names, system monospace font, recursive disk-space check with a re-check after extraction, env dicts with absolute tool paths, named and asserted upstream overrides, repo housekeeping), and the suite covers downloads and unpacking, adb and install, per-OS toolchain detection and CLI error paths.

**Plans**: 13/13 plans complete

Plans:
**Wave 1**

- [x] 02-01-PLAN.md — Build-folder lock shared by port and install (found through a host-only sidecar), data pack swapped aside with recovery, chunked install MD5 (HARD-04, HARD-07)
- [x] 02-02-PLAN.md — Signing key written whole and 0600, unreadable key refused (mkapk + doctor row), probe app on the committed signer (HARD-02, HARD-10)
- [x] 02-03-PLAN.md — Hook bootstrap script, *.code-workspace ignored, FLIP version, Ryujinx patch against Canary-1.3.351, arch_rules and upstream-output checks (HARD-10)

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 02-04-PLAN.md — One pin manifest for toolchain downloads with untested fallback, safe zip/tar unpacking, Python floor refusal (HARD-01, PKG-07)
- [x] 02-05-PLAN.md — Env dicts with absolute dotnet instead of os.environ writes, named and asserted upstream overrides, disk-space check with re-check (HARD-06, HARD-09)

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 02-06-PLAN.md — Stage stamps written last and whole (write_whole), profile copy swapped in, cut-off marker names the stage (HARD-05)
- [x] 02-07-PLAN.md — Tests for CLI error paths, adb and install, per-OS toolchain detection; tools --only named error (TEST-01)

**Wave 4** *(blocked on Wave 3 completion)*

- [x] 02-08-PLAN.md — FPSLocker configs at a pinned commit with head fallback, commit and SHA-256 in the log and build folder (HARD-03, PKG-07)
- [x] 02-09-PLAN.md — One language list through porter inspect, escaped game card, system fixed font (HARD-08, HARD-10)

**Wave 5** *(blocked on Wave 4 completion)*

- [x] 02-10-PLAN.md — NuGet content-hash pins generated and checked before every build, shared tools lock, CONCERNS.md closure table (PKG-07, HARD-04)

**Gap closure** *(from 02-VERIFICATION.md; both wave 1, run in parallel)*

- [x] 02-11-PLAN.md — Zip links checked against the final tree in any order (CR-01), CONCERNS.md zip row names its test (HARD-01, TEST-01)
- [x] 02-12-PLAN.md — Translator built per key and reuse re-checked inside the tools lock (CR-03), lock holder read bounded below the locked byte (CR-02) (HARD-04)

**Gap closure, round 2** *(from the re-verification: CR-04)*

- [x] 02-13-PLAN.md — Zip and tar links decided in memory from the folder that is installed, before anything is written (CR-04, IN-06); pinned zips' link tables as a fixture; installed toolchain moved aside until its replacement is in (WR-05) (HARD-01, TEST-01)

### Phase 3: Host Toolchains and Guided First Run

**Goal**: A tester on any of the four hosts goes from a fresh download to a ready setup (keys, toolchains, a connected device) by following the GUI
**Depends on**: Phase 2
**Requirements**: TOOL-01, TOOL-02, TOOL-03, TOOL-04, FRUN-01, FRUN-02, FRUN-03, DEV-01
**Success Criteria** (what must be TRUE):

  1. On first launch the GUI walks the user through the legal notice, prod.keys (validated, with key generation shown), toolchain downloads (progress, cancel, resume, hash check) and connecting a first device.
  2. A user who skips the wizard sees a banner naming what is missing until setup is complete, and can reopen setup later. Readiness comes from `porter setup --json` on every launch, and the GUI stores none of it.
  3. On Linux arm64, setup detects or downloads a community arm64 NDK r27c, checked by hash and a compile probe, and .NET 10, and the host build uses the NDK's `linux-arm64` folder.
  4. On Linux, setup shows the distro adb version and handles or refuses one without `push -Z`, with fix text. Connected devices show their adb state, and `unauthorized`, `offline` and `no permissions` each come with a one-line fix (the udev rules package for `no permissions`).
  5. Launched from Finder or a desktop menu with a minimal PATH, the app finds every tool by absolute path and a port runs.

**Plans**: 15/15 plans executed

Plans:
**Wave 1**

- [x] 03-01-PLAN.md — `porter setup --json` readiness document, legal notice record, prod.keys check and emulator folders, `config --json`, Linux `desktop-entry` (FRUN-01, FRUN-02, FRUN-03, TOOL-04)
- [x] 03-02-PLAN.md — Known places for a bare PATH, source labels, dotnet's real root and the dotnet child env, adb version parsing (TOOL-04, TOOL-02, TOOL-03)

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 03-03-PLAN.md — Community linux-arm64 NDK pin, no x86 platform-tools on arm64, Range resume and cancel-safe `.part`, `rate` on progress, macOS privacy message (TOOL-01, TOOL-02, FRUN-01)
- [x] 03-04-PLAN.md — NDK compile probe and community note, adb version/-Z/floor rows, distro adb command, build.py's linux-arm64 host folder (TOOL-01, TOOL-03)
- [x] 03-05-PLAN.md — gui/firstrun.py: banner, non-modal wizard, legal page and the other pages' step text, Setup tab on setup --json with Run setup (FRUN-01, FRUN-02, FRUN-03)

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 03-06-PLAN.md — adb device states parsed whole, one-line distro-aware fixes in `devices --json`, `-Z` only for adb 30+ (DEV-01, TOOL-03)
- [x] 03-07-PLAN.md — The new shell (`python -m gui.shell`) beside today's window, reusing gui/firstrun.py; arch rules for both first-run views (FRUN-02, FRUN-03)
- [x] 03-08-PLAN.md — Bare-PATH bundle smoke, arm64 community NDK download and probe in the release workflow, pin watcher, release-check rows, INSTALL.md (TOOL-04, TOOL-01)
- [x] 03-12-PLAN.md — Wizard prod.keys page: found key files with porter's verdict and generation, Browse…, save through `config keys` and re-check (FRUN-01)

**Wave 4** *(blocked on Wave 3 completion)*

- [x] 03-09-PLAN.md — Tool facts in setup --json (sizes, sources, arm64 adb command), `tools --prepare` (Prepare .NET tools) (FRUN-01, TOOL-01, TOOL-02, TOOL-03)
- [x] 03-10-PLAN.md — Wizard device page (live adb states and fixes) and done page (summary, games that play today, Add to app menu, Port a game) (DEV-01, FRUN-01, TOOL-04)

**Wave 5** *(blocked on Wave 4 completion)*

- [x] 03-11-PLAN.md — Wizard tools page and Setup tab downloads: progress with speed, Cancel, resume, Use my own…, Prepare .NET tools (FRUN-01, TOOL-01, TOOL-03)

**Gap closure** *(from 03-VERIFICATION.md: CR-01, WR-01; review warnings WR-02..WR-06 and UI-review top fixes folded in)*

- [x] 03-13-PLAN.md — A download cut off cleanly or mid-chunk is retried and resumed, never hashed short (WR-01); best-effort probe cache and quoted fix text (WR-03, WR-06) (FRUN-01, TOOL-01, wave 1)
- [x] 03-14-PLAN.md — No Prepare on a quitting window (WR-05); compact device page; colours through COLOUR and a banner that follows the theme (UI fixes 1 and 3, IN-01) (FRUN-01, FRUN-02, DEV-01, TOOL-02, wave 1)
- [x] 03-15-PLAN.md — Wizard saves survive the Setup tab's Save (CR-01); one run per runner and one setup check at a time (WR-04, T-03-35, WR-03); setup limit 150 s (WR-02); nx2android wording (UI fix 2, in part); findings ledger (FRUN-01, FRUN-03, TOOL-01, wave 2)

**UI hint**: yes

### Phase 4: Game Library and Per-Game Settings

**Goal**: Users port games and manage them from one library, with settings that porter stores per game and reuses on every re-port, from the GUI or the CLI
**Depends on**: Phase 3 (and Phase 2's build lock and env dicts, which Re-port and per-game env switches rely on); its Port view also waits for Phase 9, which gives porter a target to choose
**Requirements**: PORT-01, PORT-02, LIB-01, LIB-02, LIB-03, LIB-04, LIB-05, LIB-06, SET-01, SET-02, SET-03, SET-04, SET-05
**Success Criteria** (what must be TRUE):

  1. User picks a game folder, sees the base, update, DLC and profile status found there, sees whether it may be ported (supported / experimental / not, as porter decides), and ports it with per-stage progress.
  2. The library lists every ported game with icon, name, status, built version and last port date from porter's registry. It flags an update waiting in the folder, a missing folder (with relocate or remove), and a built version that differs from the profile's tested one, and shows the profile's compatibility line.
  3. User sets 60 fps, language, app name, update version, DLC and Advanced env switches per game, with a read-only preview of the effective `env.txt`. Each change shows its cost (data pack only / APK rebuild / full re-port), applying runs only that work, a later CLI port of the game uses the same settings, and reset restores the defaults.
  4. User drags touch-overlay buttons on a canvas (or edits the numeric table over the same rows), and the layout is applied through porter without the profile being edited.
  5. Re-port after an update reuses the game's saved settings. Uninstall from device, delete build files and remove from library are three separate confirmed actions, and uninstall warns that saves on the device are lost.

**Plans**: TBD
**UI hint**: yes

### Phase 5: Device Manager and Diagnostics

**Goal**: Users see which of their devices can run ports, manage the ports installed on each, and hand the developer a complete report with one button
**Depends on**: Phase 4
**Requirements**: DEV-02, DEV-03, DEV-04, DEV-05, DEV-06, DEV-07, DIAG-01
**Success Criteria** (what must be TRUE):

  1. Each connected device shows a compatibility verdict (BC textures, Vulkan 1.3, Android 10+, arm64, free space, with unknowns shown as unknown) beside its raw GPU/driver string, and the list updates when a device is plugged in or removed.
  2. User sees which ports are installed on each device and their versions, and can install, update or remove a port on a chosen device, with an explicit confirmation for a signer mismatch and for save loss.
  3. User launches a ported app on the device from the GUI and collects a filtered logcat for the run.
  4. One button copies diagnostics: doctor output, device info and verdict, inspect result, log tail, and the device log if one was collected.

**Plans**: TBD
**UI hint**: yes

### Phase 6: Switch-Over and Tester Verification

**Goal**: The new GUI is what every bundle opens, and testers on all four hosts confirm the core value without help
**Depends on**: Phase 5
**Requirements**: VER-01, VER-02
**Success Criteria** (what must be TRUE):

  1. The release bundles open the new GUI by default on all four hosts.
  2. On each of the four hosts, a tester downloads the bundle in a browser, then ports and installs at least one already-playable title end to end through the new GUI without help.
  3. The title ported on Linux arm64 plays on the device the same as its Linux x64 build.
  4. A test merge of current upstream shirai91/nx2android into the fork conflicts only on hook lines in shared files.

**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5 → 6

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Bridge, Bundles and CI | 10/10 | Complete    | 2026-10-30 |
| 2. Porter Hardening | 13/13 | Complete    | 2026-10-31 |
| 3. Host Toolchains and Guided First Run | 15/15 | In Progress | - |
| 4. Game Library and Per-Game Settings | 0/TBD | Not started | - |
| 5. Device Manager and Diagnostics | 0/TBD | Not started | - |
| 6. Switch-Over and Tester Verification | 0/TBD | Not started | - |
| 7. Measure what a port costs | 0/TBD | Not started | - |
| 8. Make the cold shader stage predictable | 0/TBD | Not started | - |
| 9. One port entry point for Android and Mac | 0/TBD | Not started | - |
| 10. Move saves between devices | 0/TBD | Not started | - |
| 11. Compile the C host in CI | 0/TBD | Not started | - |
| 12. One command that verifies a change | 0/TBD | Not started | - |
| 13. Guards from past incidents | 0/TBD | Not started | - |
| 14. Keep the upstream pick cheap | 0/TBD | Not started | - |

### Phase 7: Measure what a port costs

**Goal**: Every stage of a port reports its wall clock and its reuse outcome, so no claim about the pipeline rests on a guess
**Depends on**: Nothing (independent of the GUI slices; it measures the pipeline as it is today)
**Requirements**: QUAL-01, QUAL-02
**Success Criteria** (what must be TRUE):

  1. A cold and a warm port of one title each produce a table of per-stage wall clock, with reused stages labelled reused and cached stages showing hits and misses, written to `<build>/logs/timings.tsv` and printed once at the end.
  2. The table records host CPU, core count and RAM beside it, so a number from one machine can be read against another.
  3. Three titles of different engines (Unity, Unreal, first-party) have cold and warm tables recorded, so "a cold port" is a range rather than one sample.
  4. No number quoted in Phase 8's plan is asserted without a row from this table.

**Plans**: TBD

### Phase 8: Make the cold shader stage predictable

**Goal**: The shader stage says how much work it has and how long it will take before it starts, cannot thrash a tester's machine, and recomputes nothing it already has
**Depends on**: Phase 7 (the footprint and cold/warm numbers it measures)
**Requirements**: QUAL-03, QUAL-04, QUAL-05
**Success Criteria** (what must be TRUE):

  1. The stage logs `n shaders, m cached` and an ETA at its start, derived from `shader_map`, before the first shader is compiled.
  2. Worker count is capped by available RAM as well as core count, with the per-worker footprint taken from Phase 7's table, so a 16-core/16 GB host neither swaps nor runs out of memory.
  3. The Mac pack's 22,680-of-23,133 misses are settled: either cross-target reuse is demonstrated (a second run is measurably warm) or the reason it cannot happen is written as a comment in `dmsh_build.py`.
  4. A warm re-pack stays warm: no stage recompiles a shader whose inputs are unchanged.

**Plans**: TBD

### Phase 9: One port entry point for Android and Mac

**Goal**: `python -m porter port --platform android|mac-app` is the only way either package is made, with the same stage reuse, logging and JSON events
**Depends on**: Nothing for the CLI half, and the CLI half must land before Phase 4 is planned, or the Port view's target choice is built twice
**Requirements**: QUAL-06
**Success Criteria** (what must be TRUE):

  1. `porter port --platform mac-app` rebuilds Skyrim's `.app` from a warm build folder and `--platform android` is unchanged, both emitting the same event protocol and writing the same log format.
  2. Reuse keys are namespaced per target, so an Android module directory never satisfies a Mac run (`read_layout`'s refusal still fires), and build folders written with today's unprefixed keys keep working.
  3. `porter inspect` and the run log name the target being built.

**Note** (2026-11-04): most of the CLI half already exists in the working tree, uncommitted, from a parallel session and verified end to end on Skyrim — `--platform` at `porter/cli.py:24`, `run_mac()` at `porter/pipeline.py:464`, a per-target work folder (`work/mac` vs `work/android`) and `DM_TARGET='apple'` for the rewrite. Plan this phase against what is actually there: check criterion 2's key namespacing against what landed. Its old criterion 4 and requirement QUAL-07 moved to Phase 11 on 2026-11-04, when the user asked for one-or-both targets end to end.

**Plans**: TBD

### Phase 10: Move saves between devices

**Goal**: A player continues the same title on the phone and on the Mac, deliberately and verifiably
**Depends on**: Nothing (uses adb and the Mac's Application Support path, both already known)
**Requirements**: QUAL-08
**Success Criteria** (what must be TRUE):

  1. `porter saves list|export|import` works for both targets, and export writes a zip with a manifest (title ID, module build ID, file list with SHA-256, timestamp).
  2. An import whose build ID differs is refused with a precise reason, never written as a save the game cannot load.
  3. Round-trip on the device: export, remove the app's saves, import, load the save in-game (the player's judgement).
  4. Both directions work between the Y700 and this Mac for one title.

**Plans**: TBD

### Phase 11: Compile the C host in CI

**Goal**: One run makes an APK, a Mac app, or both, as the user chooses in the GUI or the CLI; and the C host cannot break on a host we ship to without the push that broke it saying so
**Depends on**: Phase 9 for the single-target contract it extends (the two-target run is a driver over `run()` and `run_mac()`, not a rewrite). The CI half is independent and can start immediately.
**Requirements**: QUAL-07, QUAL-09, QUAL-13
**Success Criteria** (what must be TRUE):

  1. `porter port --platform both` on a Mac with a profile that has an `android.tsv` produces the APK and the `.app` in one run, Android first, sharing extraction and the shader split; each target's stages run in their own `work/android` and `work/mac` folder.
  2. A failing target does not stop the other: the run reports per target (built / failed / skipped with the reason) and exits non-zero if any failed, so a working APK survives a Metal failure and a green run never hides a broken target.
  3. A profile with no `android.tsv` is skipped for Android with the reason named and the Mac app still built; on Windows and Linux the Mac app checkbox is disabled with the reason, and a Mac target requested there is skipped, never failed.
  4. The GUI's Port view offers the choice as two checkboxes defaulting to what suits the host, and one run shows one result with a row per target and its own Reveal.
  5. Every push touching `nxnative/**` or `.github/**` compiles `dm/host` for Apple arm64 and for Android arm64 as two blocking jobs, each naming its target when it fails.
  6. A new `dm/host/*.c` that is neither named in `SRC` nor matched by the `hle_*.c` wildcard fails with the missing file named, in CI or in a test that compares `SRC` against the directory.
  7. The host builds with implicit function declarations as an error on every toolchain, not only Apple clang 21, and a synthetic `dmsh_chain.lock` mismatch is exercised by a test so the refusal's remedy text cannot rot.

**Note** (2026-11-04): widened by discussion. The user asked for one-or-both targets chosen in the UI with the work following that choice, so this phase absorbed Phase 9's GUI half (QUAL-07) and gained QUAL-13. The phase name still says "CI" because the directory and requirement QUAL-09 are keyed to it; the plan covers both halves.

**Plans**: 0/4 plans complete

Plans:
**Wave 1**

- [ ] 11-01-PLAN.md — `--platform both`: one run, Android then the Mac app, per-target result and exit code (QUAL-13)
- [ ] 11-04-PLAN.md — `host-build.yml`'s two blocking jobs, `SRC` drift check, `dmsh_chain.lock` refusal test (QUAL-09)

**Wave 2** *(blocked on Wave 1 completion)*

- [ ] 11-02-PLAN.md — Port view Targets row, host-appropriate default, one `--platform` token (QUAL-07)

**Wave 3** *(blocked on Wave 2 completion)*

- [ ] 11-03-PLAN.md — per-target result rows with their own Reveal, `(platform, k)` stage keys, golden stream (QUAL-07)

### Phase 12: One command that verifies a change

**Goal**: One command answers "is this still good?" for a host or pipeline change: the suite, a warm re-port per engine family, and a device smoke, in one verdict
**Depends on**: Phase 11 (the host builds it reuses) and Phase 7 (warm-run numbers to judge itself against)
**Requirements**: QUAL-10
**Success Criteria** (what must be TRUE):

  1. `python devtools/verify.py` runs the unit suite, re-ports one title per engine family against cached extraction, and runs a device smoke (install, 60 s, pull the log, assert no `[RED]` and no crash), then prints one verdict.
  2. Each gate can be skipped, and a skip is loud, named and never counted as a pass.
  3. It runs warm in under ~20 minutes on this Mac with the Y700 attached, and it is what runs before a `dm/host` or `dm/gfx` commit.

**Plans**: TBD

### Phase 13: Guards from past incidents

**Goal**: Each class of bug this repo has already paid for is locked out by a test rather than remembered as advice
**Depends on**: Nothing (each guard stands alone)
**Requirements**: QUAL-11
**Success Criteria** (what must be TRUE):

  1. A static rule in `tests/arch_rules.py` fails when a signal handler in `dm/host` or `dm/android` is installed without `SA_ONSTACK`.
  2. Every Android stub counter either is implemented or logs "unimplemented" once, so a zero cannot be misread as a measurement (`mtl_pkg_stats` first).
  3. An `android.tsv` row written with spaces says "rows are tab-separated" instead of `unknown key 'status  playable'`.
  4. The `gfx_vk_*` stub-counter list is a fixture: adding a stub without listing it fails the suite.

**Plans**: TBD

### Phase 14: Keep the upstream pick cheap

**Goal**: The distance to upstream nxnative is visible on every push, and a threshold warns before it becomes a wall
**Depends on**: Phase 11 (the CI job it extends)
**Requirements**: QUAL-12
**Success Criteria** (what must be TRUE):

  1. Every push reports the `nxnative/` distance to upstream, and crossing a threshold warns with the pick checklist linked.
  2. The checklist is the one `docs/UNIVERSAL_SUPPORT_PLAN.md` M0 defines: import, reconcile porter's rename guards, gate what Android cannot use, regress three titles.
  3. `devtools/nuget_pins.py` regeneration is exercised in CI, so a pinned hash cannot go stale unnoticed.

**Plans**: TBD
