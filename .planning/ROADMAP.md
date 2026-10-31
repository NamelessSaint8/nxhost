# Roadmap: nx2android

## Overview

This milestone takes the Windows-only PySide6 GUI to four hosts and reworks it for testers. It starts with the long-lead risk: today's GUI, with a fixed process bridge, built, signed and smoke-tested by CI on Windows x64, macOS Apple Silicon, Linux x64 and Linux arm64. Porter hardening comes next, so killed or hostile runs can't corrupt builds or lose the signing key. The new GUI then arrives in vertical slices, each a porter-owned JSON command plus a view that displays it: host toolchains with a guided first run, the game library with per-game settings, and the device manager with diagnostics. The milestone ends when the new GUI becomes the default and testers port a playable title end to end on every host.

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
**Plans**: 6/12 plans executed

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
- [ ] 03-07-PLAN.md — The new shell (`python -m gui.shell`) beside today's window, reusing gui/firstrun.py; arch rules for both first-run views (FRUN-02, FRUN-03)
- [ ] 03-08-PLAN.md — Bare-PATH bundle smoke, arm64 community NDK download and probe in the release workflow, pin watcher, release-check rows, INSTALL.md (TOOL-04, TOOL-01)
- [ ] 03-12-PLAN.md — Wizard prod.keys page: found key files with porter's verdict and generation, Browse…, save through `config keys` and re-check (FRUN-01)

**Wave 4** *(blocked on Wave 3 completion)*
- [ ] 03-09-PLAN.md — Tool facts in setup --json (sizes, sources, arm64 adb command), `tools --prepare` (Prepare .NET tools) (FRUN-01, TOOL-01, TOOL-02, TOOL-03)
- [ ] 03-10-PLAN.md — Wizard device page (live adb states and fixes) and done page (summary, games that play today, Add to app menu, Port a game) (DEV-01, FRUN-01, TOOL-04)

**Wave 5** *(blocked on Wave 4 completion)*
- [ ] 03-11-PLAN.md — Wizard tools page and Setup tab downloads: progress with speed, Cancel, resume, Use my own…, Prepare .NET tools (FRUN-01, TOOL-01, TOOL-03)
**UI hint**: yes

### Phase 4: Game Library and Per-Game Settings
**Goal**: Users port games and manage them from one library, with settings that porter stores per game and reuses on every re-port, from the GUI or the CLI
**Depends on**: Phase 3 (and Phase 2's build lock and env dicts, which Re-port and per-game env switches rely on)
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
| 3. Host Toolchains and Guided First Run | 6/12 | In Progress | - |
| 4. Game Library and Per-Game Settings | 0/TBD | Not started | - |
| 5. Device Manager and Diagnostics | 0/TBD | Not started | - |
| 6. Switch-Over and Tester Verification | 0/TBD | Not started | - |
