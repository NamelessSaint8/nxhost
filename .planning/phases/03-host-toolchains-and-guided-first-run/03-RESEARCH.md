# Phase 3: Host Toolchains and Guided First Run - Research

**Researched:** 2026-10-31
**Domain:** per-host toolchain discovery and download (Python stdlib, urllib, tarfile), adb on Linux, a PySide6 first-run wizard over porter's JSON protocol
**Confidence:** HIGH for the community NDK facts, adb strings, Range support and in-repo hooks (all measured this session); MEDIUM for emulator key folders and LibHac key derivation; LOW for the adb version that first rejects `-Z` (no observation possible here)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

#### Carried forward (decided earlier, not re-asked)
- The new GUI shell starts in Phase 3 beside `gui/app.py` and becomes the bundle default in Phase 6 (roadmap).
- Readiness comes from porter on every launch, and the GUI stores none of it (FRUN-03). There is no persisted device list and no "first run done" flag (research ARCHITECTURE.md §Key Data Flows).
- Pins live only in `porter/pins.py`. Its header already reserves a row for the community linux-arm64 NDK (sha256). A hash mismatch always stops, naming both hashes (Phase 2 D-01). The NDK never falls back to the vendor's newest.
- A toolchain the player supplies keeps today's checks in `porter/toolchain.py` (Phase 2 D-04).
- Edits to upstream's busy files (`porter/cli.py`, `porter/pipeline.py`, `gui/app.py`) stay at hook lines. New logic goes in new files. Protocol changes are additive only, with no version field.
- Every child process gets its own env dict with absolute tool paths. A port never writes `os.environ` (HARD-06).
- Phase 1 D-05/D-09 stop semantics apply to every long run: "stopping…", then "cancelled" only once the whole tree is gone.
- The download Cancel button was deferred to this phase from Phase 1 (D-07).
- The developer prefers resilience over strictness when a vendor moves on, but always stops on a hash that doesn't match (Phase 2 specifics).

#### Wizard flow and skip
- **D-01:** The wizard is its own module (`gui/firstrun.py`) that talks to porter only through `gui/runner.py`. Today's window (`gui/app.py`) opens it through one hook line (where `Window.set_ready` jumps to the Setup tab today), so testers get it in the next bundle. The new shell reuses the same module unchanged.
- **D-02:** The wizard opens on launch only while the legal notice hasn't been accepted. Porter records the acceptance in `config.json`. After that, a launch that isn't ready shows only a banner naming what is missing, with a **Continue setup** button. There is no separate "skipped" flag.
- **D-03:** "Setup complete" (the banner goes away) means: legal notice accepted, plus prod.keys, the Android NDK, the .NET SDK and the signing key all pass. A missing adb or no authorized device is a softer note ("port now, install later"), not "setup incomplete".
- **D-04:** A reopened wizard starts at the first step porter reports as not ok, and Back still reaches the earlier steps. Today's Setup tab stays as the place to see every check and edit paths. Its checklist reads the same `setup --json`, and it gains a **Run setup** button.

#### prod.keys and legal step
- **D-05:** Porter's keys check parses the file as `name = hex` lines, checks that the keys extraction needs are present (header_key plus the master/key-area keys), and reports the highest key generation present (for example "keys up to generation 19"). A bad file names what is missing. No decryption and no network.
- **D-06:** The keys step auto-detects the usual emulator key folders per OS (Ryujinx/Ryubing `system/`, Eden/yuzu `keys/`) and shows each file found with its check result. Browse is always available. `config.json` keeps only the path, as today, and the keys are never copied.
- **D-07:** There is one legal notice: your own dumps and keys only, nothing is uploaded, and the NDK, .NET and platform-tools come under their makers' licenses (with links). Porter records the notice's version in `config.json` on acceptance, and a changed notice asks again. The download confirmation dialog stops re-asking the vendor licenses.

#### Linux arm64 NDK
- **D-08:** Source: HomuHomu833/android-ndk-custom (tag `r27`, asset `android-ndk-r27c-aarch64-linux-gnu.tar.xz`, `linux-arm64` host folder), pinned in `porter/pins.py` by URL, size and sha256. A hash mismatch stops with both hashes named, and the fix text says to wait for a pin bump or point Setup at your own NDK. No fallback.
- **D-09:** Once its compile probe passes, the community NDK's row is green, with the note "community r27c build (HomuHomu833), clang <version>: not the build the titles were tested with". The port log repeats it. Nothing is refused. Phase 6's on-device parity check (VER-02) can drop the note.
- **D-10:** The fallback recipe (distro clang/lld of the same major version plus the official r27c sysroot and clang runtime from Google's linux-x86_64 zip) is documented only. Porter does not assemble it. A player who builds that folder points Setup at it, and it gets the same checks and probe.
- **D-11:** The compile probe (`clang --version`, plus compiling and linking a one-line C file for `aarch64-linux-android29`) runs on every host, for whichever NDK is found. The result is cached by clang's path and mtime, so `doctor`/`setup` stay fast. It catches Exec format error, missing exec bits and macOS quarantine, not only arm64 problems.

#### Distro adb and device states
- **D-12:** An adb that predates `push -Z` is used without `-Z`. Porter reads `adb version`, and below the version that added push compression it drops `-Z`, which is the same on the wire because older adb never compresses. Setup shows the version. A floor refuses only an adb that lacks something porter really uses, with fix text: a newer distro adb, or Download missing tools on x64.
- **D-13:** When several adbs exist, keep today's order: configured, then PATH, then Android SDK, then porter's download. Setup shows the chosen adb's path, version and source. The download is offered only when no adb is found.
- **D-14:** The `no permissions` fix text is distro-aware, from `/etc/os-release` `ID`/`ID_LIKE`, and names the exact command. Debian/Ubuntu: `sudo apt install android-sdk-platform-tools-common`. Fedora: `sudo dnf install android-tools`. Arch: `sudo pacman -S android-udev`. Then re-plug, and join plugdev where the distro needs it. An unknown distro gets the generic list. `unauthorized` and `offline` get one-line fixes as well (accept the USB-debugging prompt, re-plug or try another cable or port).
- **D-15:** The wizard's device step polls `porter devices --json` every 2–3 s while it is visible (the 15 s one-shot timeout stays), so `unauthorized` turns into `device` live. Polling stops when the step is left. With several devices, picking one saves `config device`. There is no Restart adb button.

#### Tool discovery for Finder / menu launches
- **D-16:** `toolchain.find_*` search PATH plus a fixed per-OS list of known places on every lookup: Homebrew `/opt/homebrew/bin` and `/usr/local/bin`, `~/.dotnet`, `/usr/local/share/dotnet`, the Android SDK folders, `/snap/bin`, and porter's own `player_tools()`. They hand absolute paths to children. `config.json` keeps only what the player chose, so an upgraded or moved tool is found again. There is no login-shell PATH read.
- **D-17:** A macOS `Operation not permitted` on the game folder is mapped to a message naming System Settings › Privacy & Security. The purpose strings already ship in `packaging/nx2android.spec`.
- **D-18:** Porter's dotnet children (nx_extract, the shader translator, restores) always get `DOTNET_SYSTEM_GLOBALIZATION_INVARIANT=1`, plus `LANG=C.UTF-8` when none is set, through their env dicts. libicu then stops mattering. There is no libicu check in Setup.
- **D-19:** TOOL-04 is proven in two ways. CI runs the frozen bundle's `doctor --json` and `setup --json` under `env -i PATH=/usr/bin:/bin HOME=$HOME` on macOS and both Linux runners, with tools placed in known places, and checks that every tool row is found. A full port launched from Finder and from a desktop-menu entry is a manual UAT item in `docs/RELEASE_CHECK.md`, because CI has no game files.
- **D-20:** Linux menu entry: a porter command (for example `porter desktop-entry --install`) writes `~/.local/share/applications/nx2android.desktop` and an icon, pointing at the bundle's absolute executable. The wizard's last step offers it on Linux. Running it again after moving the bundle fixes the path. Nothing is written without asking.

#### Downloads: cancel, resume, progress
- **D-21:** Cancel stops the whole `tools --download` run with Phase 1's stop. Tools that finished installing in that run stay installed. The file in flight keeps its `.part` for a resume, and a half-unpacked folder is removed (as `_install` does today).
- **D-22:** Resume uses HTTP Range on a `.part` named after the pinned file. It works within a run after a dropped connection (up to 3 logged retries, like `Adb.run`) and across runs after Cancel or a restart. The existing bytes are re-hashed first. A server that ignores Range starts from zero. A final hash mismatch deletes the `.part` and stops, naming both hashes (D-01 of Phase 2), with no silent re-download.
- **D-23:** In the tools step, each tool row shows found/missing, version, source and download size. A missing or wrong one gets **Use my own…**, which opens a file or folder picker, saves through `porter config`, re-runs `setup --json` and shows porter's verdict. **Download all missing** fetches only what is still missing.
- **D-24:** After .NET is ready, the tools step runs one more stage, **Prepare .NET tools**: the pipeline's NuGet restore, the hash check against `pins.NUGET`, and the nx_extract and shader-translator builds, with progress and Cancel. The first port then finds them cached. "Ready" (D-03) does not wait for it, so a failure is a note with its fix, not a blocker.
- **D-25:** On Linux arm64 with no adb found, the adb row shows the distro install command from `/etc/os-release` (Debian/Ubuntu `sudo apt install adb`, Fedora `sudo dnf install android-tools`, Arch `sudo pacman -S android-tools`), plus Re-check and Use my own…. On x64 the row offers the download, as today.
- **D-26:** Progress shows bytes, speed and time left per file, for example `[2/3] Android NDK r27c · downloading · 412 MB / 781 MB · 6.1 MB/s · 1 min left`, then checking and unpacking. Porter adds `rate`/`eta` fields to its `progress` events (additive). The bar covers the current file, and the stage counter covers the batch.
- **D-27:** Porter only downloads. There is no "install from a file I downloaded". Downloaded toolchains always go to `<user dir>/toolchains`. The disk-space check names that drive. `NX2A_HOME` or Use my own… covers anything else.

#### Wizard's last step
- **D-28:** The last page shows a summary of what is ready and any notes (for example "no device yet: port now, install later"), the playable titles from `porter profiles --json` so testers know which dumps will work, the Linux "Add to app menu" offer (D-20), and a **Port a game** button that closes the wizard and opens the Port tab's folder picker.

### Claude's Discretion
These follow the research defaults (`.planning/research/ARCHITECTURE.md`, `PITFALLS.md` §7–9, `FEATURES.md` §4). Raise a `checkpoint:decision` only if one turns out to be one-way.
- **`setup --json` shape:** start from research ARCHITECTURE.md's `{steps:[{id:'legal'|'keys'|'tools'|'device', ok, detail, fix, ...}], ready}`, composed from `toolchain.checks`, `fetch.plan`, `Adb.devices` and `config`. Whether it is a new command or a `doctor` extension is your call, but `doctor --json` keeps working for today's Setup tab. Put it in new porter files with a hook line in `cli.py`.
- **New config keys:** `config.save` writes only `KEYS`, so the legal-notice version needs a new key there (for example `legal`).
- **`build.py` host folder:** `nxnative/dm/android/build.py:27` hardcodes `linux-x86_64` on Linux, for clang and `shader-tools/<host>/glslc`. Make it pick the NDK's own host folder (glob `toolchains/llvm/prebuilt/*`, or porter passes it in), as a small platform-guarded edit. This is the fork's Android layer, not the protected `host/gfx/tools/third_party`. The community build ships glslc. If a player-supplied arm64 NDK lacks it, distro `glslc` (shaderc) is acceptable with a log note.
- **A player-supplied arm64 NDK:** accepted under D-04's revision check plus the D-11 probe.
- **The distro detection helper** (`/etc/os-release`) is shared by D-14, D-25 and any other distro-aware fix text.
- **Key folder locations** per OS for D-06, the exact key names extraction needs, and the generation mapping (research from LibHac / nx_extract).
- **The adb version** that added push compression (research says 30.x; Debian 12 / Ubuntu 22.04 ship 29.0.6) and the real floor for D-12.
- **Banner placement and wording** in today's window. Exact poll interval and timeouts. The probe cache location (under `<user dir>`). Cleanup of stale `.part` files after a pin bump.
- **Proxies:** rely on urllib's own env/OS proxy handling. Adding a proxy setting is out of scope.
- **`tools --download` config writes:** `fetch.download` sets `config` to the installed folder today. Keep that (downloading is the player's choice), or drop it now that D-16 searches `player_tools()`. Your call.

### Deferred Ideas (OUT OF SCOPE)
- `inspect` names the key generation a game needs against the generation the keys have (PORT-01, Phase 4).
- A Restart adb button for `offline` devices: rejected for now, because it disconnects the player's other adb tools.
- Installing a toolchain from an archive the tester downloaded themselves: rejected (D-27).
- A configurable toolchains folder: rejected (D-27).
- Automatic assembly of the sysroot + distro clang fallback: documented only (D-10).
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| TOOL-01 | Linux arm64 gets a community arm64 NDK r27c detected or downloaded, verified by hash and a compile probe; the host build uses its `linux-arm64` folder | Pin row measured (size 127731408, sha256 `9c6214a6…fdc00c`, re-hashed locally); tarball layout listed; porter's own `_link_refusal` accepts it; `linux-x86_64 -> linux-arm64` alias links found; probe command proven on darwin r27c; build.py edit (Pattern 6) |
| TOOL-02 | Linux arm64 gets .NET 10 detected or downloaded | `pins.DOTNET['linux-arm64']` already exists, `_dotnet_rid()` maps aarch64; add Linux distro dotnet places and take `DOTNET_ROOT` from `--list-sdks` (Pitfall 4) |
| TOOL-03 | Linux shows the distro adb version; `push -Z` handled or refused; `no permissions` points to the udev package | Release notes: compression arrived in 30.0.0; Debian/Ubuntu versions per suite; `adb version` format; distro hint helper (`platform.freedesktop_os_release`) |
| TOOL-04 | Finder / desktop-menu launch finds every tool by absolute path | Measured on this Mac: bare PATH hides `/opt/homebrew/bin/adb` and `dotnet`; known-places list; smoke_bundle.py bare-env step; `.desktop` Exec rules |
| FRUN-01 | First launch walks legal → prod.keys → downloads (progress, cancel, resume, hash) → first device | `setup --json` shape; keys parser; Range resume (verified 206/416 on all three hosts, urllib keeps Range across GitHub's redirect); `eta` already in progress events; device polling |
| FRUN-02 | Skip; banner names what is missing; reopen setup | Banner via `QToolBar` in `Window`, `Continue setup` button, `Run setup` on Setup tab |
| FRUN-03 | Readiness from `porter setup --json` on every launch; GUI stores nothing | No flag; legal version lives in `config.json` (porter writes it); arch rule for `gui/firstrun.py` imports |
| DEV-01 | Devices with adb state and a one-line fix for `unauthorized`, `offline`, `no permissions` | adb source strings quoted; `devices()` mis-parse reproduced; regex fix; `fix` field added to `devices --json` |
</phase_requirements>

## Summary

Most of the phase is porter work behind four existing seams: `toolchain.find_*` (known places, probe, adb version), `fetch` (arm64 NDK row, Range resume, cancel-safe `.part`), `adb.devices()` (state parsing, `-Z` gating), and one new `setup --json` document that the GUI draws. The GUI side is one new module, `gui/firstrun.py`, attached to today's `Window` by hook lines. No new Python packages are needed: everything is stdlib (`urllib`, `hashlib`, `tarfile`/`lzma`, `platform.freedesktop_os_release`) plus the PySide6 already shipped (`QWizard`, `QToolBar`, `QTimer`).

The community NDK is in better shape than milestone research feared. The pinned asset (re-uploaded in place on 2026-10-03, unchanged since) is r27c (`Pkg.Revision = 27.2.12479018`), carries `shader-tools/linux-arm64/glslc`, needs only glibc 2.29, and passes porter's own archive-safety checks unchanged. **It also ships relative symlinks `toolchains/llvm/prebuilt/linux-x86_64 -> linux-arm64` and `shader-tools/linux-x86_64 -> linux-arm64`, so today's hardcoded `build.py` already works with it.** The build.py edit is still worth making (for player-supplied arm64 NDKs without the alias, and so logs show the real folder), but it is not on the critical path. Its clang is a rebuild (`based on r522817c`, built by clang 22.1.8), not Google's binary, so D-09's "not the build the titles were tested with" note is factually right.

Two in-repo facts change the plan. First, `progress` events already carry `eta` and `elapsed`. `rate` is not there, and adding it means editing upstream's `Progress` class in `nxnative/scripts/build_ipa_from_nsp.py` (subtree). The GUI can show speed as `(total - done) / eta`, which needs no protocol change. Second, nx_extract is built per game into `<work>/tools/nx_extract` by upstream's `build_nx_extract`, so D-24's "Prepare .NET tools" can warm the NuGet cache and the shared translator, but not an nx_extract binary the first port reuses.

**Primary recommendation:** Build porter first (`porter/hosttools.py`, `porter/keys.py`, `porter/distro.py`, `porter/setup.py`, the Range resume in `fetch._download`, the `devices()` regex), each with unit tests, and add `setup --json` with one hook line in `cli.py`. Then write `gui/firstrun.py` against fixed `setup --json` fixtures, using the existing `fake_porter` pattern.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Readiness (`ready`, per-step ok/detail/fix) | porter (`porter/setup.py`) | GUI draws it | FRUN-03: the GUI stores and derives nothing |
| prod.keys parse, generation, emulator folder scan | porter (`porter/keys.py`) | — | A rule about the input; the CLI needs it too |
| Legal notice text, version, acceptance record | porter (`setup.py` + `config` key `legal`) | GUI shows the text | D-07: porter records it; the text must not fork between CLI and GUI |
| Tool discovery (known places, source label, probe, adb version) | porter (`porter/hosttools.py`, hooks in `toolchain.py`) | — | TOOL-04: children get absolute paths from porter |
| Downloads, resume, hash, cancel | porter (`porter/fetch.py`) | GUI Cancel calls `Porter.stop()` | Stop semantics already live in `runner.Porter` + `procs` |
| Distro-aware fix text | porter (`porter/distro.py`) | — | One helper for D-14 and D-25 |
| Device state + fix text | porter (`adb.devices()` + `cmd_devices`) | GUI polls and shows | DEV-01; the GUI only renders |
| Desktop entry write | porter (`porter/desktop.py`, `desktop-entry` command) | GUI offers it | A file write with path quoting is a rule |
| Wizard pages, banner, polling | GUI (`gui/firstrun.py`) | — | Presentation and timers only |
| NDK host folder for the build | `nxnative/dm/android/build.py` | porter's probe uses the same rule | build.py runs standalone too |

## Project Constraints (from CLAUDE.md)

- The GUI holds no pipeline logic. A new CLI flag goes in `porter/cli.py` first. Enforced by `docs/ARCHITECTURE.md` and `tests/arch_rules.py` (no PySide6 in `porter/`).
- Keep diffs to upstream files small. Upstream-owned (added by Phạm Minh Tùng, from `git log --diff-filter=A`): `porter/{adb,cli,config,datapack,fetch,fpslocker,install,paths,pipeline,profiles,toolchain,upstream}.py`, `gui/{app,runner}.py`. Fork-owned, free to edit: `porter/{pins,procs,runlog,tls,nuget,lock}.py`. New logic goes in new files.
- Engine subtree `nxnative/dm/{host,gfx,tools,third_party}`: small, platform-guarded edits only. `nxnative/scripts/build_ipa_from_nsp.py` is upstream too. Do not add `rate` there.
- No game-specific code in `nxnative/dm/android/`.
- Toolchains are never bundled. Linux arm64 uses distro adb and the community NDK.
- Python 3.11+ for dev runs (tests run on 3.11 in CI), and the bundles ship 3.14. Tar extraction keeps `filter='data'`.
- Style: dense one-line Python, a file-header comment block saying the module's job, `[RED] ` prefix on problem lines, errors that name the file and the fix, explicit logged retries.
- Tests: `unittest`. Conventional Commits. Keep docs in the same commit (`docs/ARCHITECTURE.md` for protocol and command changes, `packaging/INSTALL.md` for the arm64 NDK line, `docs/RELEASE_CHECK.md` for the D-19 manual items).
- Legal: never ship keys, never print key values, and never link to keys.
- GSD workflow: edits happen through `/gsd-execute-phase`.

## Standard Stack

### Core (all already present: no installs)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `urllib.request` | stdlib | Range GET, HEAD, redirects | Already used by `fetch.py`. Verified this session: a `Range` header set through `Request(headers=…)` survives GitHub's 302 to `release-assets.githubusercontent.com` (206, `Content-Range: bytes 127731400-127731407/127731408`) |
| `hashlib` | stdlib | sha256 / sha1 / sha512 of downloads | Already used |
| `tarfile` + `lzma` | stdlib | Unpack `.tar.xz` | `tarfile.open()` auto-detects xz. The bundle spec collects the whole stdlib (`packaging/nx2android.spec:10-15`) |
| `platform.freedesktop_os_release()` | stdlib 3.10+ | `/etc/os-release` `ID`, `ID_LIKE` | Don't hand-roll the parser. It raises `OSError` when the file is missing |
| PySide6-Essentials | 6.12.0 (locked in `requirements.txt`) | `QWizard`/`QWizardPage`, `QToolBar` banner, `QTimer` polling | Already shipped. `QWizard` gives Back/Next/Finish, `setStartId`, and custom buttons for Skip |

### Toolchain artifacts (downloads, not packages)
| Artifact | Pin | Source |
|----------|-----|--------|
| Community NDK r27c, linux-arm64 | URL `https://github.com/HomuHomu833/android-ndk-custom/releases/download/r27/android-ndk-r27c-aarch64-linux-gnu.tar.xz`, size `127731408`, sha256 `9c6214a64fc3c532b78ec68d56711413e0e9ead27d5c6f2c61d92b9555fdc00c` | [VERIFIED: GitHub API `releases/tags/r27` asset `digest` field, plus a local `shasum -a 256` of the downloaded file, both this session] |
| .NET SDK 10.0.403 linux-arm64 | already in `porter/pins.py` | unchanged |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `QWizard` | `QStackedWidget` + own buttons | QWizard already has Back/Next/start-page logic; a stack is only better if the new shell (Phase 6) needs inline embedding. Recommend QWizard used non-modally (`show()`, never `exec()`) |
| Adding `rate` to upstream `Progress._json_progress` | GUI shows `(total - done) / eta` | The upstream edit is one line, but in the subtree. Only make it if the developer insists on a literal `rate` field |
| `QMainWindow.setMenuWidget` banner | `QToolBar` (non-movable) | A menu widget fights a native macOS menu bar if one is added later; a toolbar needs no layout change |

**Installation:** none.

## Package Legitimacy Audit

No external packages are installed by this phase. All code uses the stdlib and the already-locked PySide6. The only new third-party binary is a toolchain download:

| Package | Registry | Age | Downloads | Source Repo | Verdict | Disposition |
|---------|----------|-----|-----------|-------------|---------|-------------|
| android-ndk-r27c-aarch64-linux-gnu.tar.xz (not a registry package) | GitHub Release | release 2025-07-19, asset re-uploaded 2026-10-03 | 16 (asset `download_count`) | github.com/HomuHomu833/android-ndk-custom | n/a (pinned by sha256) | Approved under D-08: pinned, labelled per D-09, single maintainer |

**Packages removed due to [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none. The NDK asset is a single-maintainer binary. Its risk is handled by the sha256 pin and D-09's label, not by a registry check.

## Architecture Patterns

### System Architecture Diagram

```
 launch (Finder / menu / terminal)
        │
        ▼
 gui Window ──hook──► firstrun.attach(win)
        │                    │ call_json(['setup','--json'])  (every launch)
        │                    ▼
        │        porter setup --json ──► setup.report()
        │             ├─ config.load()  → legal accepted?  keys path
        │             ├─ keys.check(path) + keys.candidates()  (emulator folders)
        │             ├─ toolchain.checks()  ──► find_* (configured → PATH → known places → SDK → player_tools)
        │             │        └─ hosttools.probe(ndk)  (cached by clang path+mtime)
        │             │        └─ hosttools.adb_version(adb)
        │             └─ distro.hint(...)  (/etc/os-release, Linux only)
        │                    │  {ready, steps[legal,keys,tools,device], checks[...]}
        │                    ▼
        │     legal not accepted? ──yes──► Wizard (non-modal) ──► pages
        │                    │no                     │ keys: config keys <p> --json → setup again
        │            ready? ─┤                       │ tools: Porter(['tools','--download','--progress','json'])  Cancel=stop()
        │              no ──► Banner "Continue setup"│        then Porter(['tools','--prepare',...])  (D-24)
        │                                            │ device: QTimer → call_json(['devices','--json']) every 2.5 s
        │                                            │ done: profiles --json, desktop-entry --install (Linux), Port a game
        ▼
 Setup tab: same setup --json → table + "Run setup"
```

### Recommended Project Structure (new files only)
```
porter/
├── hosttools.py   # known places per OS, source labels, NDK host folder, compile probe + cache, adb version + push flags
├── keys.py        # prod.keys parse/check, generation, emulator key folder candidates
├── distro.py      # os-release → install/udev commands (D-14, D-25)
├── setup.py       # setup --json report, legal text + version (D-02..D-07)
├── desktop.py     # .desktop + icon writer (D-20)
├── prepare.py     # Prepare .NET tools (D-24)
└── childenv.py    # (optional) the dotnet child env dict shared by pipeline and prepare (D-18)
gui/
└── firstrun.py    # wizard + banner + device polling; imports only gui.runner (and PySide6)
tests/
├── test_setup.py, test_keys.py, test_hosttools.py, test_firstrun.py   # new
└── fixtures/bridge/setup_*.json                                        # setup docs for GUI tests
```

### Pattern 1: `setup --json` document (porter/setup.py)
**What:** one JSON document, ordered steps, no network, no device listing (fast on every launch).
**Recommended shape (additive, no version field):**
```json
{"ready": false,
 "legal": {"version": 1, "accepted": 0, "text": "…", "links": {"Android NDK": "https://developer.android.com/studio/terms", "…": "…"}},
 "steps": [
  {"id": "legal", "ok": false, "detail": "not accepted yet", "fix": "read and accept the notice"},
  {"id": "keys", "ok": true, "detail": "keys up to generation 19", "fix": "", "path": "/…/prod.keys",
   "found": [{"path": "~/.config/Ryujinx/system/prod.keys", "ok": true, "detail": "keys up to generation 19", "generation": 19, "missing": []}]},
  {"id": "tools", "ok": true, "items": [
     {"name": "Android NDK", "ok": true, "required": true, "path": "…", "source": "downloaded", "version": "27.2.12479018",
      "detail": "…", "fix": "", "note": "community r27c build (HomuHomu833), clang 18.0.3: not the build the titles were tested with",
      "download": {"version": "r27c", "size": 127731408}}],
   "downloadable": ["adb"]},
  {"id": "device", "ok": false, "soft": true, "detail": "adb 29.0.6 at /usr/bin/adb (PATH): pushes without -Z", "fix": "…"}],
 "notes": ["no device yet: port now, install later"],
 "checks": [ /* toolchain.checks() rows, exactly doctor --json's list */ ]}
```
- `ready` = legal accepted AND keys ok AND NDK ok AND .NET ok AND signing key ok (D-03). Python and Python modules rows are informational inside a bundle.
- `checks` lets the Setup tab table read `setup --json` (D-04) with today's rendering code unchanged.
- `download.size` comes from `pins` (`size` field). `.NET` pins carry `0`, so the size is unknown offline. Show "about 200 MB" text or leave it blank. Never HEAD on launch: `tools --json` (network) runs only when the player presses Download.
- The device step in `setup` carries the adb facts (path, version, source, `-Z` mode) but **not** the device list: `adb devices` starts a server and can stall (45 s limit). The wizard's device page polls `devices --json` itself.
- `cli.py` hook: one `sub.add_parser('setup', …)` line plus `'setup': cmd_setup` in the dispatch dict, where `cmd_setup` is `lambda a: setup.main(a)` imported lazily. Add `'setup': 45` to `gui/runner.py` `TIMEOUTS`.

### Pattern 2: config writes through porter with a JSON answer
`call_json` treats a non-JSON stdout as a failure, and `porter config key value` prints nothing today. Add `--json` to `config` (prints `{"key": …, "value": …}`), and add `legal` to `config.KEYS`. The wizard then calls `call_json(['config','keys',p,'--json'])` followed by `call_json(['setup','--json'])`. Legal acceptance becomes `config legal <version> --json`. The version number comes from `setup --json`, so the GUI holds no notice version of its own.

### Pattern 3: tool discovery = configured → PATH → known places (hosttools)
```python
# porter/hosttools.py: the places a GUI launched from Finder or a desktop menu cannot see through PATH (D-16)
def known(name):   # absolute candidate paths for 'adb' / 'dotnet', in order, existing or not
    h = Path.home(); exe = name + ('.exe' if os.name == 'nt' else '')
    if sys.platform == 'darwin': dirs = ['/opt/homebrew/bin', '/usr/local/bin', h / '.dotnet', '/usr/local/share/dotnet']
    elif os.name == 'nt': dirs = []
    else: dirs = ['/usr/bin', '/usr/local/bin', '/snap/bin', h / '.dotnet', '/usr/lib/dotnet', '/usr/lib64/dotnet', '/usr/share/dotnet']
    return [str(Path(d) / exe) for d in dirs]
```
Hook into `toolchain.find_adb` / `find_dotnet` as one list insertion each, after `shutil.which(...)` (D-13 order kept). Add a `source` label (configured / env / PATH / known place / Android SDK / downloaded) to the `Check` row. Do it in `hosttools.source_of(path, cfg)` and keep `Check` unchanged (the `setup` items carry `source`).

### Pattern 4: Range resume in `fetch._download`
```python
def _download(it, dest, retries=3):   # resumes dest.part: its bytes are re-hashed, then the rest asked for with Range; a final mismatch deletes it (D-22)
    h, part = hashlib.new(it.algo), dest.with_suffix(dest.suffix + '.part')
    for attempt in range(retries):
        have = part.stat().st_size if part.exists() else 0; h = hashlib.new(it.algo)
        if have:
            PROG.set(step='checking', done=0, total=have, unit='B')
            with open(part, 'rb') as f:
                while b := f.read(1 << 20): h.update(b)
        hdr = {'User-Agent': 'nx2android', **({'Range': f'bytes={have}-'} if have else {})}
        try:
            with urllib.request.urlopen(urllib.request.Request(it.url, headers=hdr), timeout=120, context=tls.context()) as r:
                if have and r.status != 206 or not (r.headers.get('Content-Range') or '').startswith(f'bytes {have}-') and have:
                    have = 0; h = hashlib.new(it.algo)   # the server ignored Range: start over (D-22)
                total = have + int(r.headers.get('Content-Length') or 0) or it.size or None
                PROG.set(step='downloading', done=have, total=total, unit='B')
                with open(part, 'ab' if have else 'wb') as f:
                    while chunk := r.read(1 << 20): f.write(chunk); h.update(chunk); have += len(chunk); PROG.set(done=have)
            break
        except urllib.error.HTTPError as e:
            if e.code != 416: raise   # 416: the .part is already whole (or longer): the hash below decides
            break
        except (urllib.error.URLError, OSError, TimeoutError) as e:
            if attempt + 1 == retries: raise
            PROG.say(f'{Path(it.url).name}: {e}, retry {attempt + 1}')   # explicit and logged, like Adb.run
    if (got := h.hexdigest().lower()) != it.hash.lower():
        part.unlink(missing_ok=True)
        raise BuildError(f'{Path(it.url).name}: its {it.algo} is {got}, not the expected {it.hash} (from {it.url}): …')
    part.replace(dest)
```
Measured this session: `dl.google.com`, `builds.dotnet.microsoft.com` and the GitHub asset all answer a `-r 100-199` request with `206`. Google answers a start past the end with `416` and `Content-Range: bytes */9054187`. A `KeyboardInterrupt` (SIGTERM through `procs._term`) leaves `.part` in place, because nothing deletes it on that path. `download()`'s `finally: arc.unlink()` only removes the finished archive. Stale `.part` files: at the start of `download()`, delete every `player_tools()/*.part` whose name is not one of this plan's archive names (this covers a pin bump).

### Pattern 5: devices -l parsing and fix text
adb formats each `-l` line as `"%-22s %s"` (serial, state), then optional `devpath` (e.g. `usb:1-1`), `product:`, `model:`, `device:`, then ` transport_id:<n>` [CITED: android.googlesource.com/platform/packages/modules/adb transport.cpp `append_transport`]. A no-permission state string is `"no permissions (<problem>); see [http://developer.android.com/tools/device.html]"`, where `<problem>` is `missing udev rules? user is in the plugdev group` or `user <name> is not in the plugdev group` [CITED: platform/system/core diagnose_usb.cpp]. A serial can be `(no serial number)`, which contains spaces.
```python
ROW = re.compile(r'^(\(no serial number\)|\S+)\s+(.+?)(?=\s+(?:usb:|product:|model:|device:|transport_id:)|\s*$)')
# reproduced this session: today's ln.split() turns the no-permissions line into state 'no'; ROW gives the whole state text
```
Classify `state.startswith('no permissions')` as `no permissions`, keep the raw text in `detail`, and add `fix` per state (`unauthorized`, `offline`, `no permissions`, `authorizing`/`connecting`: "wait a moment") to the `devices --json` rows. This is additive: keep `serial`/`state`/`info`. `pick()` compares `st == 'device'` and still works.

### Pattern 6: build.py host folder (platform-guarded, two lines)
Today [VERIFIED: nxnative/dm/android/build.py:27-29, 41]:
```python
host = 'windows-x86_64' if os.name == 'nt' else 'linux-x86_64' if sys.platform.startswith('linux') else 'darwin-x86_64'
bin_ = Path(a.ndk) / 'toolchains/llvm/prebuilt' / host / 'bin'
CC = str(bin_ / ('clang.exe' if os.name == 'nt' else 'clang'))
GLSLC = Path(a.ndk) / 'shader-tools' / host / ('glslc.exe' if os.name == 'nt' else 'glslc')
```
Recommended addition right after line 27:
```python
if sys.platform.startswith('linux') and platform.machine().lower() in ('aarch64', 'arm64'):   # an arm64 NDK's own host folder (community builds: linux-arm64)
    host = next((h for h in ('linux-arm64', 'linux-aarch64') if (Path(a.ndk) / 'toolchains/llvm/prebuilt' / h).is_dir()), host)
```
and before the glslc loop: `if not GLSLC.is_file() and shutil.which('glslc'): print('[RED] no glslc in the NDK: using the system one', …); GLSLC = Path(shutil.which('glslc'))`. Do not glob `prebuilt/*` blindly: the community tarball holds **both** `linux-arm64` and a `linux-x86_64` symlink to it.

### Pattern 7: compile probe (hosttools.probe)
```python
cmd = [clang, '--target=aarch64-linux-android29', '-fuse-ld=lld', src, '-o', out]   # src: 'int main(void) { return 0; }'
```
Proven this session with the official r27c (darwin-x86_64): it links an `ELF 64-bit LSB pie executable, ARM aarch64 … interpreter /system/bin/linker64` in 0.16 s. Run `clang --version` first and keep its first line. Cache it in `<user dir>/probe.json` keyed by `[str(clang.resolve()), st_mtime_ns, st_size]`. Catch `OSError` (Exec format error = `errno.ENOEXEC`, `PermissionError` for missing exec bits) and `subprocess.TimeoutExpired` (60 s first run). Run it in a temp dir, never in the bundle. The host folder for the probe comes from the same rule as Pattern 6. The community label in D-09 applies when the host folder is `linux-arm64`/`linux-aarch64`, a folder Google never ships.

### Pattern 8: GUI hooks in today's window (gui/app.py, hook lines only)
- `Window.__init__`: `firstrun.attach(self)` adds a hidden non-movable `QToolBar` banner (text + **Continue setup**) and keeps a reference.
- `Window.set_ready(ok)` [VERIFIED: gui/app.py:430-432] today jumps to the Setup tab on the first failed check. Replace its body's jump with `firstrun.on_ready(self, ok, doc)`, or keep `set_ready(ok)` and add a sibling `self.setup_doc(doc)` call from `SetupTab.check`. `tests/test_bridge.py:110-118` asserts `ready.assert_called_with(False)` on a crashed check, so keep a `set_ready(False)` call on failure.
- `SetupTab.check` switches from `['doctor','--json']` to `['setup','--json']` and renders `doc['checks']`. Add a **Run setup** button (`firstrun.open(win)`) and a **Cancel** button next to the download bar (`self.fetch.stop()`).
- The wizard reuses `win.setup.fetch` (the `Porter` the window's `closeEvent` already tracks) for downloads and Prepare. A second `Porter` would escape the D-07 close guard unless added to `Window.runs()`.

### Anti-Patterns to Avoid
- **A `firstrun_done` flag or cached tool list in the GUI:** violates FRUN-03. Only `config.json` (written by porter) holds `legal`.
- **Modal `QWizard.exec()`:** blocks the event loop's other one-shots and every GUI test. Use `show()`.
- **Fixed-interval device polling with `setInterval`:** a stalled `adb devices` (45 s limit) would stack calls. Schedule the next poll with `QTimer.singleShot(2500, …)` from the previous answer, and only while the page is current.
- **Login-shell PATH reads** (`zsh -lc 'echo $PATH'`): rejected by D-16, slow, and they run user dotfiles.
- **Copying prod.keys** anywhere, or putting key values into `setup --json` or logs.
- **Resolving `/opt/homebrew/bin/dotnet` only for `DOTNET_ROOT`** via `Path.parent`: see Pitfall 4.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| os-release parsing | a line parser | `platform.freedesktop_os_release()` | Handles quoting and both `/etc/os-release` and `/usr/lib/os-release` |
| Download resume state | a sidecar JSON | the `.part` file's own size + re-hash | D-22; nothing to go stale |
| Progress speed/ETA | a new rate tracker | `progress` event's existing `eta` (last-minute rate) and `done/total` | Already emitted by upstream `Progress._json_progress` |
| Archive safety | new checks for `.tar.xz` | `fetch._untar` (`_refuse_names`, `_link_refusal`, `filter='data'`) | Verified to accept the community tarball unchanged |
| Wizard navigation | a page stack with Back/Next logic | `QWizard` (`setStartId`, `nextId`) | Built in |
| Process stop for Cancel | new kill code | `runner.Porter.stop()` | Phase 1 D-05/D-09 semantics |
| DOTNET_ROOT discovery | readlink games | `dotnet --list-sdks` output `10.0.403 [/usr/local/share/dotnet/sdk]` → parent of the bracketed folder | Works for symlinks, Homebrew and snap |

## Common Pitfalls

### Pitfall 1: The community NDK asset is re-uploaded in place
**What goes wrong:** The release dates from 2025-07-19, but its assets were re-created on 2026-10-03 (r27c gnu) and 2026-10-21/22 (others). The next rebuild changes the sha256, and every arm64 download then stops.
**How to avoid:** D-08 already fails closed with both hashes. Add a cheap pin watcher, a `devtools/` script run before releases: `gh api repos/HomuHomu833/android-ndk-custom/releases/tags/r27 --jq '.assets[]|select(.name=="android-ndk-r27c-aarch64-linux-gnu.tar.xz")|.digest'` compared with `pins.NDK`.
**Warning signs:** a tester's `[RED] … its sha256 is X, not the expected 9c62…`.

### Pitfall 2: `fetch` would download x86 tools on Linux arm64
**What goes wrong:** `_google_os()` maps every Linux to `'linux'` [VERIFIED: porter/fetch.py:47 `def _google_os(): return {'win32': 'windows', 'darwin': 'macosx'}.get(sys.platform, 'linux')`]. On arm64, `_pinned('adb')` finds the `'linux'` platform-tools row, which is an x86_64 build, and an NDK with no arm64 row would fall back to Google's index.
**How to avoid:** Pick the NDK host key as `'linux-arm64'` when `platform.machine()` is aarch64/arm64, and add that row to `pins.NDK['files']`. Remove `adb` from `missing()`/`plan()` on Linux arm64 (D-25: the row shows the distro command instead).

### Pitfall 3: `devices()` mis-parses `no permissions`
**What goes wrong:** [VERIFIED: porter/adb.py:66-67 `parts = ln.split()` / `rows.append((parts[0], parts[1], …))`] gives state `no`. Reproduced this session with the source-derived line.
**How to avoid:** the Pattern 5 regex, plus a unit test fed every state line (including `(no serial number)`).

### Pitfall 4: `DOTNET_ROOT` from a symlinked dotnet is wrong
**What goes wrong:** On this Mac, `/opt/homebrew/bin/dotnet -> /usr/local/share/dotnet/dotnet` (measured). `pipeline.run` sets `DOTNET_ROOT=dn` where `dn = str(self.tools['dotnet'].parent)` (pipeline.py:96-97), so a known-places hit at `/opt/homebrew/bin` gives `DOTNET_ROOT=/opt/homebrew/bin`. nx_extract's apphost then may not find the runtime [ASSUMED consequence]. The same applies to `/usr/bin/dotnet -> /usr/lib/dotnet/dotnet` on Ubuntu and to snap's `/snap/bin/dotnet`.
**How to avoid:** Have `find_dotnet` return the real executable: the parent of the `--list-sdks` bracket path (`[/usr/local/share/dotnet/sdk]` → `/usr/local/share/dotnet/dotnet`), falling back to `Path.resolve()`.

### Pitfall 5: The bare PATH hides tools on the developer's own Mac
**What goes wrong:** Measured: `env -i PATH=/usr/bin:/bin HOME=$HOME python3 -c "shutil.which('adb'), shutil.which('dotnet')"` → `None None`, while `toolchain` finds `/opt/homebrew/bin/adb` and `/opt/homebrew/bin/dotnet` from a terminal. Today's `find_adb` has no Homebrew entry, and `find_dotnet` has none either (it does have `/usr/local/share/dotnet/dotnet`).
**How to avoid:** Pattern 3, plus the D-19 bare-env CI step.

### Pitfall 6: `-Z` on an old adb
**What goes wrong:** Platform-tools release notes put push/pull/sync compression in **30.0.0 (April 2020)** [CITED: developer.android.com/tools/releases/platform-tools]. Debian 12 ships `1:29.0.6-28` and Ubuntu 22.04 ships `29.0.6`. An adb that predates the flag likely rejects `-Z` as an unknown option [ASSUMED: not observable here]. Debian 11's `1:10.0.0+r36` is older still, but its glibc 2.31 cannot run either bundle.
**How to avoid:** Parse `^Version\s+(?:\d+:)?(\d+)\.(\d+)\.(\d+)` from `adb version`. This session's Homebrew adb prints `Android Debug Bridge version 1.0.41` / `Version 36.0.0-13206524`. Major < 30 means no `-Z`; unparseable means keep `-Z` (today's behaviour, which protects adbd on new adbs). Gate it in `Adb` once per instance (`self.nocompress = ['-Z'] if … else []`) and use it at the two sites [VERIFIED: porter/adb.py:171 and :191, `self.run('push', '-Z', …)`]. Floor: everything porter uses (`devices -l`, `push` of several files to a folder, `install -r`, `uninstall`, `shell` with exit status, `pull`, `wait-for-device`, `start-server`) predates 29.0.6 [ASSUMED]. Set the refusal floor below 29 only on the protocol line `1.0.N`, N < 39 [ASSUMED], with fix text. No supported tester distro hits it.
**Warning signs:** `adb push: unrecognized option` on Ubuntu 22.04 / Debian 12 x64 testers using the distro adb.

### Pitfall 7: The wizard's download run escapes the close guard
**What goes wrong:** `Window.runs()` only knows `self.port.porter` and `self.setup.fetch` (app.py:407). A `Porter` the wizard creates itself can be orphaned on quit.
**How to avoid:** The wizard drives `win.setup.fetch` (Pattern 8), or `Window.runs()` gains the wizard's porters through one hook.

### Pitfall 8: D-24 cannot cache nx_extract's binary across games
**What goes wrong:** Upstream `build_nx_extract(repo, work, logs, env)` builds into `<work>/tools/nx_extract` [VERIFIED: nxnative/scripts/build_ipa_from_nsp.py:351-361], and `work` is the per-game build folder. The translator, by contrast, goes to `user_dir()/tools/dmsh_xlate-<key[:12]>` (pipeline.py `translator`).
**How to avoid:** Prepare = `nuget.restored(...)` for both projects (fills `user_dir()/nuget`, checks `pins.NUGET`), the translator build (same key, so the first port reuses it), and one nx_extract `dotnet build` into a temp folder (proves the SDK builds it; MSBuild's `obj/` in the engine copy speeds the per-game build). Call `pipeline.Port.translator` unbound with a namespace (`tools`, `env`, `logs`) so the key logic is not copied, and pin that with a test. The UI text should say "Prepare .NET tools", not "build nx_extract once".

### Pitfall 9: The fake porter has no `setup`
**What goes wrong:** `tests/fixtures/bridge/fake_porter.py` answers only `ONE_SHOT = ('doctor', 'devices', 'profiles', 'tools', 'inspect')` with `[]`. Once `Window` calls `setup --json` at start-up, every bridge test window would get a non-dict, and a wizard opening at start would break unrelated tests.
**How to avoid:** Add `setup` to the fake, answering a ready document with legal accepted (a fixture file), and add `--fixture` cases for "legal not accepted" and "not ready".

### Pitfall 10: The macOS TCC denial is `EPERM`, not `EACCES`
**What goes wrong:** A TCC denial raises `PermissionError: [Errno 1] Operation not permitted` from deep inside inspect or port. Today it reaches the GUI as a bare `PermissionError: …`.
**How to avoid:** Map `isinstance(e, PermissionError) and e.errno == errno.EPERM and sys.platform == 'darwin'` to the System Settings › Privacy & Security text, in `runlog.py` (fork-owned) at both error branches (the one-shot `{"error"}` and the long-run `error` event).

## Code Examples

### prod.keys check (porter/keys.py)
```python
# Source: key names read from LibHac 0.19.0's LibHac.dll strings this session (header_key, master_key, titlekek, key_area_key_application …)
LINE = re.compile(r'^\s*([A-Za-z0-9_]+)\s*=\s*([0-9A-Fa-f]+)\s*$')
IDX = re.compile(r'(master_key|titlekek|key_area_key_application)_([0-9a-f]{2})')

def check(path):
    """{'ok', 'detail', 'generation', 'missing'}: the names extraction needs, never the values"""
    p = Path(path)
    if not p.is_file(): return {'ok': False, 'detail': f'no such file: {p}', 'generation': None, 'missing': []}
    if p.stat().st_size > 1 << 20: return {'ok': False, 'detail': f'{p} is not a prod.keys file (over 1 MB)', 'generation': None, 'missing': []}
    keys = {m[1].lower(): m[2] for ln in p.read_text(encoding='utf-8', errors='replace').splitlines() if (m := LINE.match(ln))}
    by = {}
    for k in keys:
        if m := IDX.fullmatch(k): by.setdefault(int(m[2], 16), set()).add(m[1])
    usable = [g for g, s in by.items() if 'master_key' in s or {'titlekek', 'key_area_key_application'} <= s]
    missing = [] if len(keys.get('header_key', '')) == 64 else ['header_key']
    if not usable: missing.append('master_key_00')
    gen = max(usable) if usable else None
    return {'ok': not missing, 'generation': gen, 'missing': missing,
            'detail': f'keys up to generation {gen}' if not missing else 'missing: ' + ', '.join(missing)}
```
The generation shown is the highest key index (e.g. `master_key_13` → 19). An NCA's key generation *g* uses index `max(g, 1) - 1` [ASSUMED]. Phase 4 (PORT-01) compares against it, so keep the index in the JSON.

### Emulator key folder candidates (porter/keys.py)
```python
def candidates():
    h = Path.home(); ad = Path(os.environ.get('APPDATA') or h / 'AppData/Roaming')
    cfg = Path(os.environ.get('XDG_CONFIG_HOME') or h / '.config'); data = Path(os.environ.get('XDG_DATA_HOME') or h / '.local/share')
    fams = ('yuzu', 'eden', 'citron', 'sudachi', 'suyu')
    if os.name == 'nt': dirs = [ad / 'Ryujinx/system', *[ad / f / 'keys' for f in fams]]
    elif sys.platform == 'darwin':
        sup = h / 'Library/Application Support'; dirs = [sup / 'Ryujinx/system', *[sup / f / 'keys' for f in fams]]
    else: dirs = [cfg / 'Ryujinx/system', *[d / f / 'keys' for d in (data, cfg) for f in fams],
                  *map(Path, glob.glob(str(h / '.var/app/*/config/Ryujinx/system'))), *map(Path, glob.glob(str(h / '.var/app/*/data/*/keys')))]
    dirs.append(h / '.switch')   # hactool's and Ryujinx's per-user folder (AppDataManager.KeysDirPathUser)
    return [str(d / 'prod.keys') for d in dirs if (d / 'prod.keys').is_file()]
```
Ryujinx: `<SpecialFolder.ApplicationData>/Ryujinx/system` plus `~/.switch` [VERIFIED: nxnative/dm/third_party/ryujinx/src/Ryujinx.Common/Configuration/AppDataManager.cs:11 `DefaultBaseDir = "Ryujinx"`, :17 `KeysDir = "system"`, :47 `KeysDirPathUser = Path.Combine(…UserProfile), ".switch")`, :52 `ApplicationData`; its comments evaluate ApplicationData to `~/Library/Application Support` on macOS and `~/.config` on Linux]. Ryubing is a fork of this code and keeps the `Ryujinx` folder name [ASSUMED]. The yuzu-family folders are [ASSUMED]; the globs make wrong guesses harmless.

### distro hint (porter/distro.py)
```python
UDEV = {'debian': 'sudo apt install android-sdk-platform-tools-common', 'fedora': 'sudo dnf install android-tools', 'arch': 'sudo pacman -S android-udev'}
ADB = {'debian': 'sudo apt install adb', 'fedora': 'sudo dnf install android-tools', 'arch': 'sudo pacman -S android-tools'}

def family(osr=None):   # 'debian' / 'fedora' / 'arch' / None, from ID then ID_LIKE (ubuntu, mint, raspbian → debian; manjaro → arch)
    try: osr = osr if osr is not None else platform.freedesktop_os_release()
    except OSError: return None
    ids = [osr.get('ID', ''), *osr.get('ID_LIKE', '').split()]
    return next((f for i in ids for f in (('debian',) if i in ('debian', 'ubuntu') else (i,)) if f in UDEV), None)
```
Debian's `android-sdk-platform-tools-common` depends on `android-udev-rules` [CITED: packages.debian.org/trixie/android-sdk-platform-tools-common]. Arch's `android-udev` is in `extra` (20260922-1) [CITED: archlinux.org/packages/extra/any/android-udev].

### .desktop entry (porter/desktop.py)
```python
def entry(exe, icon):   # Exec quoting per the Desktop Entry spec: double quotes; \" \` \$ \\ escaped, then each \ doubled again by the string rule; % as %%
    q = '"' + ''.join('\\\\' + c if c in '"`$\\' else c for c in str(exe)).replace('%', '%%') + '"'
    return f'[Desktop Entry]\nType=Application\nName=nx2android\nComment=Port your own Switch games to Android\nExec={q}\nTryExec={exe}\nIcon={icon}\nTerminal=false\nCategories=Game;Utility;\n'
```
Write to `${XDG_DATA_HOME:-~/.local/share}/applications/nx2android.desktop` through a temp file and `replace` (as `config.save` does). Use an absolute `Icon=` path to a PNG copied into `<user dir>/` so moving the bundle does not lose the icon. **No app icon exists in the repo today** (`git ls-files` finds no png/ico/icns outside nxnative docs/games), so the plan needs an icon asset added to the bundle `datas`. As a fallback, use the theme name `applications-games`. Offer the entry only when `paths.FROZEN` (the executable is `sys.executable`). Rules [CITED: specifications.freedesktop.org/desktop-entry/latest/exec-variables.html]: reserved characters require double quotes; `"`, `` ` ``, `$`, `\` are backslash-escaped inside them; a literal backslash takes four backslashes in the file; `%` is `%%`.

### Bare-env check for D-19 (packaging/smoke_bundle.py, POSIX)
```python
home2 = tmp / 'bare'; (home2 / '.dotnet').mkdir(parents=True)   # stand-ins in known places that /usr/bin:/bin cannot see
stub(home2 / '.dotnet/dotnet', "echo '10.0.403 [%s/sdk]'" % (home2 / '.dotnet'))
stub(home2 / ('Library/Android/sdk' if sys.platform == 'darwin' else 'Android/Sdk') / 'platform-tools/adb', "echo 'Version 36.0.0-0'")
ndk = home2 / ('Library/Android/sdk' if sys.platform == 'darwin' else 'Android/Sdk') / 'ndk/27.2.12479018'; ndk.mkdir(parents=True)
(ndk / 'source.properties').write_text('Pkg.Revision = 27.2.12479018\n')
env = {'PATH': '/usr/bin:/bin', 'HOME': str(home2), 'NX2A_HOME': str(home2 / 'nx2a')}
doc, code, err = porter(exe, env, 'setup', '--json')
check('bare PATH: every tool row found', all(i['path'] for i in doc['steps'][2]['items']), err)
```
The probe fails on a stub NDK. That is fine: D-19 checks that each row is *found* (`path` set), not that it is ok. Run it in `fork-release.yml` (it already calls `smoke_bundle.py` on all four targets; skip on Windows). Mirror it unfrozen in `tests/test_hosttools.py` (POSIX only) so `fork-ci` catches it on every push.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| adb push uncompressed only | compression on push/pull/sync, `-Z` disables it | platform-tools 30.0.0 (Apr 2020) [CITED] | `-Z` must be gated for 29.x |
| No Google arm64 Linux NDK | community rebuilds (HomuHomu833 r27c, clang 18.0.3 `based on r522817c`, built with clang 22.1.8) | ongoing | Labelled per D-09, glibc 2.29 floor |
| GitHub assets without digests | API returns `digest: "sha256:…"` per asset | seen this session | The pin can be checked without downloading |

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | adb 29.x rejects `push -Z` as an unknown option (instead of ignoring it) | Pitfall 6 | Low: gating by version is right either way |
| A2 | Everything porter uses exists in adb ≥ 1.0.39 / platform-tools < 29; floor N < 39 | Pitfall 6 | Low: no supported distro ships below 29.0.6 |
| A3 | A wrong `DOTNET_ROOT` (`/opt/homebrew/bin`) breaks nx_extract's apphost | Pitfall 4 | Low: resolving the root is correct regardless |
| A4 | LibHac 0.19.0 derives titlekek / key_area_key from `master_key_XX` with built-in sources, so `master_key_XX` alone makes a generation usable | Code Examples (keys) | Medium: a file with only master keys might pass the check and fail extraction. Test with a real Lockpick dump (it has all three families) |
| A5 | NCA key generation g uses master key index `max(g,1)-1` | Code Examples (keys) | Low here (display only); matters in Phase 4 |
| A6 | Ryubing keeps `Ryujinx/system`; yuzu/Eden/Citron use `<data>/<name>/keys` (`~/.local/share` on Linux, `%APPDATA%` on Windows, `~/Library/Application Support` on macOS) | Code Examples (keys) | Low: a missed folder only means Browse |
| A7 | `clang --version` of the community build prints `Android (36531653132, +pgo, -bolt, +lto, +mlgo, based on r522817c) clang version 18.0.3 …` (vendor string found in the binary, `AndroidVersion.txt` says 18.0.3) | Pattern 7 / D-09 note | Low: the note shows whatever the probe reads. **The executor must run the probe on an arm64 host** |
| A8 | Ubuntu's `dotnet` package lives in `/usr/lib/dotnet`, Fedora's in `/usr/lib64/dotnet` | Pattern 3 | Low: PATH covers them in a terminal; `--list-sdks` gives the root anyway |

## Open Questions

1. **Literal `rate` field (D-26)**
   - What we know: `progress` already has `eta`, `done`, `total`, `elapsed` [VERIFIED: nxnative/scripts/build_ipa_from_nsp.py:155-158]. Upstream's emitter builds a fixed dict.
   - Unclear: whether the developer wants a `rate` key in the protocol or only the speed on screen.
   - Recommendation: show `(total - done) / eta` in the GUI. If a field is required, add `'rate'` to `_json_progress` (one line in the subtree) and record it in `docs/ARCHITECTURE.md`. This one is reversible.
2. **Community probe on real arm64**
   - What we know: layout, revision, glibc 2.29, the alias links and the archive safety pass were all measured here.
   - Unclear: the actual `clang --version` line, and whether the link step succeeds on Ubuntu 24.04 arm64.
   - Recommendation: a CI step on `ubuntu-24.04-arm` in `fork-release.yml` (or a manual dispatch job): `porter tools --download --only ndk` then `porter setup --json`, asserting the NDK row is ok. Cost: 128 MB per run.
3. **`tools --download` config writes**
   - Recommendation: keep `config.set_value` after install (today's behaviour). With D-16, `player_tools()` is found anyway, but the explicit config makes Setup's "source" read "downloaded" rather than a guess, and D-13 order puts configured first.

## Environment Availability

| Dependency | Required By | Available (this Mac) | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python venv | tests | ✓ `.venv/bin/python` | 3.14.5 | — |
| PySide6-Essentials | GUI tests | ✓ (lock) | 6.12.0 | — |
| Android NDK r27c (darwin) | probe tests | ✓ `~/Library/Android/sdk/ndk/27.2.12479018` | clang 18.0.3 | stub clang script in tests |
| adb | adb version tests | ✓ `/opt/homebrew/bin/adb` | 36.0.0 | fake `subprocess.run` (test_adb pattern) |
| dotnet | prepare | ✓ `/usr/local/share/dotnet` | 10.0.403 | — |
| `gh` | pin watcher | ✓ | — | curl the API |
| Linux arm64 host | TOOL-01 end-to-end | ✗ here | — | CI `ubuntu-24.04-arm` + tester UAT |
| Linux x64 with distro adb 29 | TOOL-03 | ✗ here | — | CI `ubuntu-22.04` (`apt install adb` gives 29.0.6) for the version parse; tester UAT for a device |

**Missing dependencies with no fallback:** none block planning. The arm64 port parity check is Phase 6 (VER-02).

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | `unittest` (stdlib) |
| Config file | none |
| Quick run command | `.venv/bin/python -m unittest tests.test_setup tests.test_keys tests.test_hosttools tests.test_fetch tests.test_adb -v` |
| Full suite command | `QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover tests && .venv/bin/python tests/arch_rules.py` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| TOOL-01 | linux-arm64 `plan()` picks the community row (patched `sys.platform`/`platform.machine`); a hash mismatch names both hashes; adb is not planned on arm64 | unit | `.venv/bin/python -m unittest tests.test_fetch -v` | ✅ extend |
| TOOL-01 | probe: ok / ENOEXEC / no exec bit / cached by path+mtime (stub clang script) | unit | `.venv/bin/python -m unittest tests.test_hosttools -v` | ❌ Wave 0 |
| TOOL-01 | build.py picks `linux-arm64` on aarch64 (fake NDK, stub clang, `--only-compile`) | integration, skip unless Linux aarch64 | `python -m unittest tests.test_hosttools.BuildHost` on `ubuntu-24.04-arm` | ❌ Wave 0 |
| TOOL-01 | real community NDK download + probe | CI job / manual | `porter tools --download --only ndk && porter setup --json` on arm64 | ❌ |
| TOOL-02 | `_dotnet_rid()` → linux-arm64; DOTNET_ROOT from `--list-sdks` path; child env has `DOTNET_SYSTEM_GLOBALIZATION_INVARIANT=1` | unit | `.venv/bin/python -m unittest tests.test_toolchain tests.test_stages -v` | ✅ extend |
| TOOL-03 | `adb version` parse (36.0.0-…, 29.0.6-debian, 1:10.0.0+r36, garbage); push argv with/without `-Z` | unit | `.venv/bin/python -m unittest tests.test_adb -v` | ✅ extend |
| TOOL-03 | distro family + commands from stub os-release dicts | unit | `.venv/bin/python -m unittest tests.test_hosttools -v` | ❌ Wave 0 |
| TOOL-04 | bare-env `doctor/setup --json` finds stubs in known places (POSIX) | unit (subprocess) | `.venv/bin/python -m unittest tests.test_hosttools.BarePath -v` | ❌ Wave 0 |
| TOOL-04 | frozen bundle bare-env smoke | CI | `python packaging/smoke_bundle.py dist/nx2android` (release workflow) | ✅ extend |
| TOOL-04 | full port from Finder / desktop menu | manual UAT | `docs/RELEASE_CHECK.md` rows | ❌ add rows |
| FRUN-01 | wizard pages in order; keys page shows candidates; tools page Cancel calls `stop`; device page polls and stops polling on leave | GUI (fake_porter) | `QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest tests.test_firstrun -v` | ❌ Wave 0 |
| FRUN-01 | Range resume: local `http.server` with Range support; resume after cut; server ignoring Range restarts; 416 with a whole `.part`; final mismatch deletes `.part` | unit | `.venv/bin/python -m unittest tests.test_fetch -v` | ✅ extend |
| FRUN-02 | not-ready doc → banner with missing names; Continue setup opens the wizard at the first not-ok step | GUI | `QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest tests.test_firstrun -v` | ❌ |
| FRUN-03 | `gui/firstrun.py` imports only `gui.runner` + PySide6 (no `porter.config`, no file writes) | arch rule | `.venv/bin/python tests/arch_rules.py` | ✅ extend |
| FRUN-03 | `setup --json` shape + `ready` per D-03 (legal/keys/NDK/.NET/signing key) | unit | `.venv/bin/python -m unittest tests.test_setup -v` | ❌ Wave 0 |
| DEV-01 | `devices()` parses all states incl. `no permissions (…); see [...]` and `(no serial number)`; `devices --json` has `fix` | unit | `.venv/bin/python -m unittest tests.test_adb tests.test_cli -v` | ✅ extend |
| DEV-01 | real `unauthorized` → `device` transition on a tablet; Linux `no permissions` | manual UAT | — | — |

### Sampling Rate
- **Per task commit:** the quick run command for the touched modules
- **Per wave merge:** full suite command
- **Phase gate:** full suite green, plus the `fork-ci` matrix (four hosts and 3.11), before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/test_setup.py`, `tests/test_keys.py`, `tests/test_hosttools.py`, `tests/test_firstrun.py`
- [ ] `tests/fixtures/bridge/fake_porter.py`: add `setup` (and `config … --json`) to `ONE_SHOT`; fixtures `setup_ready.json`, `setup_first.json`, `setup_missing.json`
- [ ] `tests/fixtures/keys/`: synthetic prod.keys files with **fake hex** (never real keys): complete, no header_key, only master keys, junk
- [ ] An `arch_rules.py` rule for `gui/firstrun.py` imports

## Security Domain

### Applicable ASVS Categories
| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | — |
| V3 Session Management | no | — |
| V4 Access Control | no | — |
| V5 Input Validation | yes | prod.keys: regex lines, 1 MB cap, names only in output; `Content-Range` start must equal the `.part` size; `.desktop` Exec quoting; os-release values used only as dict keys |
| V6 Cryptography | yes | `hashlib` sha256/sha1/sha512 against `pins.py`; no custom crypto; never decrypt keys |
| V10 Malicious Code / supply chain | yes | Community NDK pinned by sha256, fail-closed, labelled (D-08/D-09); archive refusal rules unchanged |
| V12 Files and Resources | yes | `.part` only under `player_tools()`; stale `.part` cleanup only of `*.part` there; `.desktop` written via temp + replace into the XDG folder; `filter='data'` |
| V14 Configuration | yes | TLS via `tls.context()` for every fetch, including the GitHub redirect target |

### Known Threat Patterns
| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Tampered or re-uploaded NDK asset | Tampering | sha256 pin, stop naming both hashes, no fallback |
| MITM on download | Tampering | `tls.context()` (CERT_REQUIRED), hash check |
| Resume splicing (server returns a different range) | Tampering | Accept 206 only with `Content-Range: bytes <have>-`; final whole-file hash |
| prod.keys contents leaking into logs or JSON | Information disclosure | Output key *names* and generation only; tests assert no hex value appears |
| `.desktop` Exec injection via an odd bundle path | Elevation (runs in the menu) | Spec quoting (`"`, `` ` ``, `$`, `\` escaped, `%%`); `TryExec` |
| Symlinked `~/.local/share/applications` target | Tampering | Write a temp file in the same folder, `replace`; refuse if the target is a symlink |
| Running an untrusted NDK binary for the probe | Elevation | Only the pinned or player-chosen NDK; run in a temp dir with a timeout; no shell |

## Sources

### Primary (HIGH confidence)
- GitHub API `repos/HomuHomu833/android-ndk-custom/releases/tags/r27`: asset name, size 127731408, digest `sha256:9c6214a6…fdc00c`, created 2026-10-03, 606 assets, no body text
- Local download and `shasum -a 256` (matches the digest); `tar -tJvf` listing (14,823 entries); porter's `fetch._bad_name/_top/_link_refusal` run on the member list (top `android-ndk-r27c`, refusal `None`, 17 relative symlinks, no hard links); `source.properties` (`Pkg.Revision = 27.2.12479018`, `Pkg.ReleaseName = r27c`); `AndroidVersion.txt` (`18.0.3`, `based on r522817c`); `objdump -p` (GLIBC needs up to 2.29, NEEDED libm/libc/ld-linux-aarch64/libpthread/libdl); `.comment` (`clang version 22.1.8`, `Linker: LLD 22.1.8`); unpacked size 1.17 GiB
- curl `-r` probes: 206 from dl.google.com, builds.dotnet.microsoft.com and the GitHub asset; Python urllib keeps `Range` across the GitHub redirect; 416 past the end on Google
- Official r27c darwin clang probe run (`--target=aarch64-linux-android29 -fuse-ld=lld`) → aarch64 PIE in 0.16 s
- In-repo files read this session: `porter/{toolchain,pins,fetch,adb,config,paths,cli,procs,runlog,tls,upstream,pipeline}.py`, `gui/{app,runner}.py`, `nxnative/dm/android/build.py`, `nxnative/scripts/build_ipa_from_nsp.py` (Progress, build_nx_extract), `Ryujinx.Common/Configuration/AppDataManager.cs`, `packaging/{nx2android.spec,smoke_bundle.py}`, `.github/workflows/*.yml`, `tests/test_bridge.py`, `tests/fixtures/bridge/fake_porter.py`
- LibHac 0.19.0 nupkg from nuget.org: key-name strings in `lib/net7.0/LibHac.dll`

### Secondary (MEDIUM confidence)
- [AOSP adb transport.cpp](https://android.googlesource.com/platform/packages/modules/adb/+/refs/heads/main/transport.cpp): `-l` line format
- [AOSP adb.cpp](https://android.googlesource.com/platform/packages/modules/adb/+/refs/heads/main/adb.cpp): `to_string(ConnectionState)`
- [AOSP diagnose_usb.cpp](https://android.googlesource.com/platform/system/core/+/refs/heads/main/diagnose_usb/diagnose_usb.cpp): `no permissions` text
- [Platform-tools release notes](https://developer.android.com/tools/releases/platform-tools): compression in 30.0.0
- [packages.debian.org adb](https://packages.debian.org/search?keywords=adb&searchon=names&exact=1&suite=all&section=all): bookworm 1:29.0.6-28, trixie 1:34.0.5-12, bullseye 1:10.0.0+r36-7
- [Launchpad android-platform-tools](https://launchpad.net/ubuntu/+source/android-platform-tools): jammy 29.0.6, noble 34.0.4, resolute 34.0.5
- [Debian android-sdk-platform-tools-common](https://packages.debian.org/trixie/android-sdk-platform-tools-common), [Arch android-udev](https://archlinux.org/packages/extra/any/android-udev/)
- [Desktop Entry spec, Exec variables](https://specifications.freedesktop.org/desktop-entry/latest/exec-variables.html)

### Tertiary (LOW confidence)
- Web guides for Eden/yuzu key folders ([tech-insider.org](https://tech-insider.org/fi/eden-emulaattori-nintendo-switch-pc-12-askelta-2026/)) and the [Ryujinx wiki Keys page](https://github.com/Ryujinx/Ryujinx/wiki/Keys): used only to choose glob candidates

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH. No new packages, and every stdlib behaviour this relies on was measured.
- Architecture: HIGH. Hooks and seams read in the code, with upstream vs fork ownership from git history.
- Pitfalls: HIGH for 1–5 and 7–9 (measured or read); MEDIUM for 6 (adb `-Z` rejection unobserved) and 10.

**Research date:** 2026-10-31
**Valid until:** 2026-11-14 for the NDK pin (the asset is re-uploaded in place; re-check its digest before release); 30 days for the rest.
