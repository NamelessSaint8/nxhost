# Phase 3: Host Toolchains and Guided First Run - Context

**Gathered:** 2026-10-31
**Status:** Ready for planning

<domain>
## Phase Boundary

A tester on any of the four hosts (Windows x64, macOS Apple Silicon, Linux x64, Linux arm64) goes from a fresh bundle download to a ready setup by following the GUI. Covers TOOL-01..04, FRUN-01..03 and DEV-01:

- Per-host toolchain facts in porter: the community linux-arm64 NDK r27c (pinned, hash-checked, compile-probed) and .NET 10 on Linux arm64, distro adb with version handling, tool discovery that works with a bare PATH (Finder / desktop-menu launches).
- `porter setup --json`: the readiness document the GUI draws on every launch. The GUI stores none of it.
- A skippable first-run wizard (legal → prod.keys → tools → device → done), a "setup incomplete" banner, and setup that can be reopened.
- Connected devices with their adb state and a one-line fix for `unauthorized`, `offline`, `no permissions`.

Not in this phase: the game library, per-game settings, the device manager's compatibility verdict and per-device install/remove (Phases 4–5), and making the new shell the bundle default (Phase 6).

</domain>

<decisions>
## Implementation Decisions

### Carried forward (decided earlier, not re-asked)
- The new GUI shell starts in Phase 3 beside `gui/app.py` and becomes the bundle default in Phase 6 (roadmap).
- Readiness comes from porter on every launch, and the GUI stores none of it (FRUN-03). There is no persisted device list and no "first run done" flag (research ARCHITECTURE.md §Key Data Flows).
- Pins live only in `porter/pins.py`. Its header already reserves a row for the community linux-arm64 NDK (sha256). A hash mismatch always stops, naming both hashes (Phase 2 D-01). The NDK never falls back to the vendor's newest.
- A toolchain the player supplies keeps today's checks in `porter/toolchain.py` (Phase 2 D-04).
- Edits to upstream's busy files (`porter/cli.py`, `porter/pipeline.py`, `gui/app.py`) stay at hook lines. New logic goes in new files. Protocol changes are additive only, with no version field.
- Every child process gets its own env dict with absolute tool paths. A port never writes `os.environ` (HARD-06).
- Phase 1 D-05/D-09 stop semantics apply to every long run: "stopping…", then "cancelled" only once the whole tree is gone.
- The download Cancel button was deferred to this phase from Phase 1 (D-07).
- The developer prefers resilience over strictness when a vendor moves on, but always stops on a hash that doesn't match (Phase 2 specifics).

### Wizard flow and skip
- **D-01:** The wizard is its own module (`gui/firstrun.py`) that talks to porter only through `gui/runner.py`. Today's window (`gui/app.py`) opens it through one hook line (where `Window.set_ready` jumps to the Setup tab today), so testers get it in the next bundle. The new shell reuses the same module unchanged.
- **D-02:** The wizard opens on launch only while the legal notice hasn't been accepted. Porter records the acceptance in `config.json`. After that, a launch that isn't ready shows only a banner naming what is missing, with a **Continue setup** button. There is no separate "skipped" flag.
- **D-03:** "Setup complete" (the banner goes away) means: legal notice accepted, plus prod.keys, the Android NDK, the .NET SDK and the signing key all pass. A missing adb or no authorized device is a softer note ("port now, install later"), not "setup incomplete".
- **D-04:** A reopened wizard starts at the first step porter reports as not ok, and Back still reaches the earlier steps. Today's Setup tab stays as the place to see every check and edit paths. Its checklist reads the same `setup --json`, and it gains a **Run setup** button.

### prod.keys and legal step
- **D-05:** Porter's keys check parses the file as `name = hex` lines, checks that the keys extraction needs are present (header_key plus the master/key-area keys), and reports the highest key generation present (for example "keys up to generation 19"). A bad file names what is missing. No decryption and no network.
- **D-06:** The keys step auto-detects the usual emulator key folders per OS (Ryujinx/Ryubing `system/`, Eden/yuzu `keys/`) and shows each file found with its check result. Browse is always available. `config.json` keeps only the path, as today, and the keys are never copied.
- **D-07:** There is one legal notice: your own dumps and keys only, nothing is uploaded, and the NDK, .NET and platform-tools come under their makers' licenses (with links). Porter records the notice's version in `config.json` on acceptance, and a changed notice asks again. The download confirmation dialog stops re-asking the vendor licenses.

### Linux arm64 NDK
- **D-08:** Source: HomuHomu833/android-ndk-custom (tag `r27`, asset `android-ndk-r27c-aarch64-linux-gnu.tar.xz`, `linux-arm64` host folder), pinned in `porter/pins.py` by URL, size and sha256. A hash mismatch stops with both hashes named, and the fix text says to wait for a pin bump or point Setup at your own NDK. No fallback.
- **D-09:** Once its compile probe passes, the community NDK's row is green, with the note "community r27c build (HomuHomu833), clang <version>: not the build the titles were tested with". The port log repeats it. Nothing is refused. Phase 6's on-device parity check (VER-02) can drop the note.
- **D-10:** The fallback recipe (distro clang/lld of the same major version plus the official r27c sysroot and clang runtime from Google's linux-x86_64 zip) is documented only. Porter does not assemble it. A player who builds that folder points Setup at it, and it gets the same checks and probe.
- **D-11:** The compile probe (`clang --version`, plus compiling and linking a one-line C file for `aarch64-linux-android29`) runs on every host, for whichever NDK is found. The result is cached by clang's path and mtime, so `doctor`/`setup` stay fast. It catches Exec format error, missing exec bits and macOS quarantine, not only arm64 problems.

### Distro adb and device states
- **D-12:** An adb that predates `push -Z` is used without `-Z`. Porter reads `adb version`, and below the version that added push compression it drops `-Z`, which is the same on the wire because older adb never compresses. Setup shows the version. A floor refuses only an adb that lacks something porter really uses, with fix text: a newer distro adb, or Download missing tools on x64.
- **D-13:** When several adbs exist, keep today's order: configured, then PATH, then Android SDK, then porter's download. Setup shows the chosen adb's path, version and source. The download is offered only when no adb is found.
- **D-14:** The `no permissions` fix text is distro-aware, from `/etc/os-release` `ID`/`ID_LIKE`, and names the exact command. Debian/Ubuntu: `sudo apt install android-sdk-platform-tools-common`. Fedora: `sudo dnf install android-tools`. Arch: `sudo pacman -S android-udev`. Then re-plug, and join plugdev where the distro needs it. An unknown distro gets the generic list. `unauthorized` and `offline` get one-line fixes as well (accept the USB-debugging prompt, re-plug or try another cable or port).
- **D-15:** The wizard's device step polls `porter devices --json` every 2–3 s while it is visible (the 15 s one-shot timeout stays), so `unauthorized` turns into `device` live. Polling stops when the step is left. With several devices, picking one saves `config device`. There is no Restart adb button.

### Tool discovery for Finder / menu launches
- **D-16:** `toolchain.find_*` search PATH plus a fixed per-OS list of known places on every lookup: Homebrew `/opt/homebrew/bin` and `/usr/local/bin`, `~/.dotnet`, `/usr/local/share/dotnet`, the Android SDK folders, `/snap/bin`, and porter's own `player_tools()`. They hand absolute paths to children. `config.json` keeps only what the player chose, so an upgraded or moved tool is found again. There is no login-shell PATH read.
- **D-17:** A macOS `Operation not permitted` on the game folder is mapped to a message naming System Settings › Privacy & Security. The purpose strings already ship in `packaging/nx2android.spec`.
- **D-18:** Porter's dotnet children (nx_extract, the shader translator, restores) always get `DOTNET_SYSTEM_GLOBALIZATION_INVARIANT=1`, plus `LANG=C.UTF-8` when none is set, through their env dicts. libicu then stops mattering. There is no libicu check in Setup.
- **D-19:** TOOL-04 is proven in two ways. CI runs the frozen bundle's `doctor --json` and `setup --json` under `env -i PATH=/usr/bin:/bin HOME=$HOME` on macOS and both Linux runners, with tools placed in known places, and checks that every tool row is found. A full port launched from Finder and from a desktop-menu entry is a manual UAT item in `docs/RELEASE_CHECK.md`, because CI has no game files.
- **D-20:** Linux menu entry: a porter command (for example `porter desktop-entry --install`) writes `~/.local/share/applications/nx2android.desktop` and an icon, pointing at the bundle's absolute executable. The wizard's last step offers it on Linux. Running it again after moving the bundle fixes the path. Nothing is written without asking.

### Downloads: cancel, resume, progress
- **D-21:** Cancel stops the whole `tools --download` run with Phase 1's stop. Tools that finished installing in that run stay installed. The file in flight keeps its `.part` for a resume, and a half-unpacked folder is removed (as `_install` does today).
- **D-22:** Resume uses HTTP Range on a `.part` named after the pinned file. It works within a run after a dropped connection (up to 3 logged retries, like `Adb.run`) and across runs after Cancel or a restart. The existing bytes are re-hashed first. A server that ignores Range starts from zero. A final hash mismatch deletes the `.part` and stops, naming both hashes (D-01 of Phase 2), with no silent re-download.
- **D-23:** In the tools step, each tool row shows found/missing, version, source and download size. A missing or wrong one gets **Use my own…**, which opens a file or folder picker, saves through `porter config`, re-runs `setup --json` and shows porter's verdict. **Download all missing** fetches only what is still missing.
- **D-24:** After .NET is ready, the tools step runs one more stage, **Prepare .NET tools**: the pipeline's NuGet restore, the hash check against `pins.NUGET`, and the nx_extract and shader-translator builds, with progress and Cancel. The first port then finds them cached. "Ready" (D-03) does not wait for it, so a failure is a note with its fix, not a blocker.
- **D-25:** On Linux arm64 with no adb found, the adb row shows the distro install command from `/etc/os-release` (Debian/Ubuntu `sudo apt install adb`, Fedora `sudo dnf install android-tools`, Arch `sudo pacman -S android-tools`), plus Re-check and Use my own…. On x64 the row offers the download, as today.
- **D-26:** Progress shows bytes, speed and time left per file, for example `[2/3] Android NDK r27c · downloading · 412 MB / 781 MB · 6.1 MB/s · 1 min left`, then checking and unpacking. Porter adds `rate`/`eta` fields to its `progress` events (additive). The bar covers the current file, and the stage counter covers the batch.
- **D-27:** Porter only downloads. There is no "install from a file I downloaded". Downloaded toolchains always go to `<user dir>/toolchains`. The disk-space check names that drive. `NX2A_HOME` or Use my own… covers anything else.

### Wizard's last step
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

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase scope and requirements
- `.planning/ROADMAP.md` §"Phase 3: Host Toolchains and Guided First Run": goal and the five success criteria
- `.planning/REQUIREMENTS.md`: TOOL-01..04, FRUN-01..03, DEV-01
- `.planning/PROJECT.md`: constraints (upstream compatibility, engine subtree, toolchains not bundled, Linux arm64 uses distro adb and a community NDK) and Key Decisions

### Research
- `.planning/research/ARCHITECTURE.md` §"Key Data Flows" (guided first run, `setup --json` shape), the state ownership table (no first-run flag), and the anti-patterns (no cached device list)
- `.planning/research/FEATURES.md` §4 "Guided First Run": steps, prod.keys step, toolchain step, device step, anti-features (no key links, no firmware step, never a blocking wizard)
- `.planning/research/PITFALLS.md` §7 (distro adb `-Z`, udev, `no permissions`), §8 (community arm64 NDK: layout, probe, sysroot fallback), §9 (Finder/launcher environment, TCC)
- `.planning/research/SUMMARY.md`: research flags for Phase 3 (HomuHomu833 hash drift, clang parity, glibc; adb `-Z` version)
- `.planning/research/STACK.md`: the HomuHomu833 tarball listing (tag, asset name, host folder, glslc, clang version)

### Prior phase decisions
- `.planning/phases/02-porter-hardening/02-CONTEXT.md`: D-01..D-05 (pinning, fallback, NuGet pins), the env-dict rules
- `.planning/phases/01-bridge-bundles-and-ci/01-CONTEXT.md`: D-03 (one-shot timeouts), D-05/D-09 (stop semantics), D-07 (download close guard)

### Project rules
- `docs/ARCHITECTURE.md`: the GUI holds no pipeline logic, the layers, and the JSON protocol
- `tests/arch_rules.py`: no PySide6 in `porter/`, no game-specific code in `nxnative/dm/android/`
- `docs/RELEASE_CHECK.md`: where the manual Finder/menu UAT items go (D-19)
- `packaging/INSTALL.md`: tester-facing install text (the Linux arm64 NDK line changes)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `porter/toolchain.py`: the `Check` rows (`name, ok, detail, required, path, fix`), `checks()`, `find_ndk/find_dotnet/find_adb`, `ndk_revision`, `dotnet_sdks`. D-16's known places and D-11's probe go here or beside it.
- `porter/fetch.py`: `plan()` (pinned first, 404/410 fallback), `_download` (already writes a `.part`, but opens it `'wb'` and the archive is deleted in `finally`, so there is no resume yet), `_install` (`.unpack` / `.old` swap), `download()` (disk check, one stage per tool, sets config). D-21/D-22/D-26 extend these.
- `porter/pins.py`: add the linux-arm64 NDK row. `fetch._google_os()` maps every Linux to `linux` today and needs an arm64 case for the NDK (`_dotnet_rid()` already handles arm64).
- `porter/adb.py`: `Adb.devices()` and the two `push -Z` sites (`push_tree`, `push_file`) for D-12. **Note:** `devices()` splits on whitespace, so `no permissions (missing udev rules? …)` parses as state `no`, which must be fixed for DEV-01.
- `porter/cli.py` `cmd_devices` / `cmd_tools` / `cmd_doctor`: the JSON one-shots the wizard calls. New commands (`setup`, the desktop entry, a keys check) go through hook lines.
- `gui/runner.py` `Porter` (long runs with stop) and `call_json(parent, args, done, timeout)` (one-shots with timeout and Retry): the only way the wizard reaches porter.
- `gui/app.py` `SetupTab` (download confirm dialog, `on_fetch` progress handling, `failed()` / `cause()` helpers) and `Window.set_ready` (today's first-check hook, which D-01 replaces with opening the wizard).

### Established Patterns
- One-shot JSON (`--json`) for checks, and JSON-lines (`--progress json`) for long runs. `[RED] ` prefixes problem lines.
- Errors name the file and the fix. Retries are explicit and logged.
- Dense one-line Python style, with file-header comments stating each module's job (`.claude/CLAUDE.md` Conventions).
- Tests: `unittest`, the `fake_porter` pattern for the GUI bridge, stand-in `os`/`sys` for per-OS detection (Phase 2 02-07), local `http.server` or a patched `_get` for downloads.

### Integration Points
- `gui/app.py` `Window.__init__` / `set_ready` (wizard launch and banner), `SetupTab` (Run setup button, Cancel for downloads).
- `porter/config.py` `KEYS` (new legal-version key).
- `nxnative/dm/android/build.py:27-28` (host folder).
- `packaging/` (the Linux icon for the desktop entry, `INSTALL.md`), and the CI workflows (the D-19 bare-env check).

</code_context>

<specifics>
## Specific Ideas

- The wizard must never trap the developer. It can be skipped, and it comes back automatically only until the legal notice is accepted.
- Show where every tool came from (configured, PATH, SDK, downloaded) and its version, so a tester's report says which adb or NDK was used.
- Fix text names the exact command for the tester's distro rather than a generic hint.
- The community arm64 NDK is usable but honestly labelled until Phase 6 proves parity on the device.

</specifics>

<deferred>
## Deferred Ideas

- `inspect` names the key generation a game needs against the generation the keys have (PORT-01, Phase 4).
- A Restart adb button for `offline` devices: rejected for now, because it disconnects the player's other adb tools.
- Installing a toolchain from an archive the tester downloaded themselves: rejected (D-27).
- A configurable toolchains folder: rejected (D-27).
- Automatic assembly of the sysroot + distro clang fallback: documented only (D-10).

</deferred>

---

*Phase: 03-host-toolchains-and-guided-first-run*
*Context gathered: 2026-10-31*
