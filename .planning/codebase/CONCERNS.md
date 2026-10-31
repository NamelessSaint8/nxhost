---
last_mapped_commit: 9d67edec2175ae5f4beadbd65f37eaa88105d132
last_mapped_at: 2026-10-29
---
# Codebase Concerns

**Analysis Date:** 2026-10-29

Scope: the whole repository, with `nxnative/dm/third_party/` read only for how the project patches, pins and syncs it. Upstream's own debt in that tree is out of scope.

## Priority Summary

| # | Concern | Area | Severity |
|---|---------|------|----------|
| 1 | GUI cancel does not stop the process tree on macOS/Linux | `gui/runner.py` | High (blocks cross-platform GUI) |
| 2 | A missing Python dependency makes the GUI fail silently or misleadingly | `porter/upstream.py`, `gui/app.py` | High |
| 3 | Zip extraction writes symlinks from unsanitized member names | `porter/fetch.py` | High (security) |
| 4 | The APK signing key is stored unencrypted with default permissions | `nxnative/dm/android/apk/mkapk.py` | Medium-High (security) |
| 5 | No lock prevents two ports of the same game folder from running at once | `porter/pipeline.py` | Medium |
| 6 | Import-time monkey-patching and process-wide environment mutation | `porter/upstream.py`, `porter/pipeline.py` | Medium |
| 7 | nxnative subtree has diverged from upstream; `git subtree pull` will conflict | `nxnative/`, `README.md` | Medium |
| 8 | Downloads and FPSLocker configs are trusted on transport integrity only | `porter/fetch.py`, `porter/fpslocker.py` | Medium |
| 9 | Test coverage is absent for the GUI, downloads, adb, CLI and devtools | `tests/` | Medium |
| 10 | Dependencies are unpinned and devtools import undeclared packages | `requirements.txt`, `devtools/` | Low-Medium |
| 11 | Windows-only packaging and release gate | `packaging/`, `docs/RELEASE_CHECK.md` | Medium (blocks cross-platform) |

## Tech Debt

**Monkey-patched upstream module at import time:**
- Issue: `porter/upstream.py` loads `nxnative/scripts/build_ipa_from_nsp.py` by file path and then replaces its globals (`m.nacp`, `m.pg`, `m.can_clone`, `m.profile_files`) before any caller runs. The `profile_files` wrapper filters out `android.tsv` by name. This makes the pipeline depend on the script's internal names and on import order.
- Files: `porter/upstream.py`, `nxnative/scripts/build_ipa_from_nsp.py`
- Impact: any rename or restructuring upstream breaks the port with an `AttributeError` far from the cause. Tests that import `porter` pick up the patched state, so ordering matters.
- Fix approach: move the four overrides into a single named function with a comment per override, and add a test that asserts each attribute exists on the loaded module, so an upstream change fails loudly at import.

**Process-wide environment mutation in the port pipeline:**
- Issue: `Port.run` prepends the chosen dotnet to `os.environ['PATH']` and sets `DOTNET_ROOT` (`porter/pipeline.py` around line 92). `use_profile_dir` writes `DM_GAMES_DIR` and `DM_GAMES_FIRST` into `os.environ` (line ~198). `porter/cli.py` `_with_progress` restores the environment in a `finally` block to undo this.
- Files: `porter/pipeline.py`, `porter/cli.py`
- Impact: correct only because each port runs as its own process. Any in-process caller (a test, a future API) inherits the mutated environment unless it goes through `_with_progress`.
- Fix approach: pass a copied env dict to `nsp.run` and the other subprocess helpers instead of mutating `os.environ`. `build_nx_extract` already receives `env` and calls `run(['dotnet', ...])` by bare name, so it relies on the PATH mutation. Pass the dotnet path explicitly there.

**Shared work directory with the iOS build:**
- Issue: the port writes into `<game folder>/<title ID>_build/`, which the iOS build of the same folder also uses (`porter/pipeline.py` header comment). `extract/`, `aoc/`, `shader/` and `logs/` are shared on purpose.
- Files: `porter/pipeline.py`, `nxnative/scripts/build_ipa_from_nsp.py`
- Impact: an iOS run and an Android run can overwrite each other's stage outputs. The reuse keys guard against stale data, but nothing guards against concurrent writes.
- Fix approach: document the sharing rule in `docs/ARCHITECTURE.md` and add a lock file per build folder (see concern 5).

**`inspect` failure is reported as "no game found":**
- Issue: `porter/cli.py` `cmd_inspect` catches only `BuildError`. Any other exception ends the process with a traceback on stderr and no JSON on stdout. `gui/app.py` `on_inspect` then shows "No game found in this folder", which is wrong for a folder that has a game.
- Files: `porter/cli.py` (`cmd_inspect`), `gui/app.py` (`on_inspect`), `porter/pipeline.py` (`inspect`)
- Impact: a real bug in a game folder is presented as a missing game.
- Fix approach: catch `Exception` in `cmd_inspect` and return a JSON error object, and have `on_inspect` show that message.

**Tracked and untracked repository hygiene:**
- Issue: `nx2android.code-workspace` is untracked at the repository root and not ignored (`git status` at session start). `.gitignore` covers `*-signing-key.json` but not editor workspace files.
- Files: `.gitignore`, `nx2android.code-workspace`
- Fix approach: add `*.code-workspace` to `.gitignore` or commit the file deliberately.

## Known Bugs

**GUI cancel on macOS and Linux leaves children running:**
- Symptoms: pressing Cancel during a port on macOS or Linux kills only the direct `python -m porter` child. The `dotnet` build, the shader translator (`dotnet`), and the NDK `clang` processes started by it keep running and keep writing into the build folder.
- Files: `gui/runner.py` (`Porter.cancel`, the `else` branch calling `self.p.kill()`), `nxnative/scripts/build_ipa_from_nsp.py` (`run`, which uses `subprocess.Popen` without `start_new_session` or a process group)
- Trigger: start a port from the GUI on macOS or Linux, then click Cancel during the shader or host stage.
- Workaround: none in the app. On Windows the `taskkill /T` path kills the tree correctly.
- Note: the docstring at the top of `gui/runner.py` says cancelling stops the whole process tree. That is true only on Windows.
- Fix approach: start the porter process in its own session (`start_new_session=True` through a `subprocess`-level launcher, or a `QProcess` wrapper that calls `os.killpg`), and kill the group on cancel. Add a manual test on macOS.

**Missing dependency reported as a network or empty-list failure:**
- Symptoms: when `lz4` (or another module `porter/upstream.py` imports) is absent from the interpreter that runs the GUI, the Games tab stays empty, and the Download button reports "Could not read the download lists from Google and Microsoft" (`gui/app.py` `confirm_download`). The real cause is a `ModuleNotFoundError` written to stderr, which `call_json` discards.
- Files: `porter/upstream.py` (import-time imports of `android_profile`, `game`, `nacp`, `profile_guess`), `porter/fetch.py` (imports `porter.upstream` for `BuildError`), `porter/profiles.py`, `gui/app.py` (`call_json`, `GamesTab.got`, `SetupTab.confirm_download`)
- Trigger: run `python -m gui` with a Python that lacks `requirements.txt` packages. The Setup tab's doctor check works, but the other tabs do not.
- Observed: in this environment, `python3 -m unittest discover tests` fails at import of `tests/test_porter.py` with `No module named 'lz4'` through `porter/pipeline.py` → `porter/install.py` → `porter/upstream.py` → `nxnative/dm/games/profile_guess.py` → `nxnative/dm/tools/nso_syms.py`.
- Fix approach: have `call_json` keep stderr and show its last line in the failing tab, and have `porter/fetch.py` import only what it needs (move `BuildError` into a module without the nxnative imports). Run `checks()` before showing the Games tab.

**`PortTab.cancel` reports cancellation before the child exits:**
- Symptoms: `PortTab.cancel` appends "[RED] cancelled" to the log at once, while `on_finished` only learns the outcome later. If the kill fails, the log says cancelled while the run continues.
- Files: `gui/app.py` (`PortTab.cancel`), `gui/runner.py` (`cancel`)
- Fix approach: append the cancelled line from `on_finished` when the exit code is 130 or the process is confirmed gone.

## Security Considerations

**Zip extraction writes symlinks from unsanitized member names:**
- Risk: `porter/fetch.py` `_unzip` handles symlink entries itself and does not use `zipfile.extract`. For a symlink member it builds `t = into / info.filename` with no path check, and calls `os.symlink(target, t)`. A member name containing `..` or an absolute path escapes the unpack folder. Regular files go through `z.extract`, which strips such components, so only the symlink path is exposed. A later regular file written through a planted symlink could also escape.
- Files: `porter/fetch.py` (`_unzip`)
- Current mitigation: the archives come from Google's SDK repository and the link target is checked against the list's SHA-1 before unpacking (`_download` deletes a mismatched file). A compromised index could supply both.
- Recommendations: resolve `t` and require it to be inside `into`; reject absolute link targets and targets that leave `into` after resolution; reject member names with `..`. Add a unit test with a crafted zip.

**Tar extraction falls back to unfiltered extraction on older Pythons:**
- Risk: `porter/fetch.py` `_untar` passes `filter='tar'` only when `tarfile.tar_filter` exists. Python 3.11.0 through 3.11.3 do not have it, and the project supports 3.11 and later (`README.md`). Extraction on those versions is unfiltered.
- Files: `porter/fetch.py` (`_untar`), `packaging/build_bootloader.py` (uses `filter='data'` unconditionally, which also fails on those versions)
- Current mitigation: the .NET tarball's hash comes from Microsoft's release metadata.
- Recommendations: require Python 3.11.4 or later in `porter/toolchain.py` `checks`, or implement the member check manually.

**APK signing key is stored unencrypted with default permissions:**
- Risk: `nxnative/dm/android/apk/mkapk.py` writes the player's signing key as JSON with `open(keyf, 'w')` (around line 197). The file gets the process umask, normally world-readable on macOS and Linux. It is not written atomically, so an interrupted write leaves a truncated key, and the next run generates a new signer. Every app the player ported would then fail to install over the previous one.
- Files: `nxnative/dm/android/apk/mkapk.py`, `porter/paths.py` (`signing_key()` returns `user_dir()/signing-key.json`), `porter/pipeline.py` (`apk()` passes it)
- Current mitigation: the key lives outside the repository and `*-signing-key.json` is ignored by git.
- Recommendations: write the key with mode `0600` (`os.open` with `0o600`), write to a temporary file and `os.replace`, and fail instead of regenerating when the file exists but does not parse. Document that losing the key means reinstalling every port with `--replace-signer`.

**Duplicate, diverged signing code under `probes/`:**
- Risk: `probes/app/mkapk.py` is a separate copy of `nxnative/dm/android/apk/mkapk.py` (the two files differ, and the probe copy writes `probe-signing-key.json` next to the output by default). Fixes to one copy will not reach the other.
- Files: `probes/app/mkapk.py`, `nxnative/dm/android/apk/mkapk.py`
- Fix approach: point the probe app at the committed `mkapk.py`, or delete the probe copy once the probes are retired.

**Third-party configuration fetched at port time and applied to game memory:**
- Risk: `porter/fpslocker.py` fetches a YAML config from a `raw.githubusercontent.com` path on the `v4` branch of `masagrator/FPSLocker-Warehouse` (`RAW`, line 13) and turns its memory writes and code cuts into `fpslock.tsv` and a patches file applied to the game's `main` module. The config is parsed and refused whole for anything unsupported (`Refused`), which limits the damage, but the source is an unpinned branch, not a commit.
- Files: `porter/fpslocker.py`, `porter/pipeline.py` (`fps_unlock`)
- Current mitigation: expression and type validation; the warehouse's configs are never committed, which matches the source's lack of a license.
- Recommendations: pin the fetch to a commit SHA or record the config's SHA-256 in the build folder, and show the hash in the port log.

**Download integrity relies on the same origin as the archive:**
- Risk: `porter/fetch.py` checks each archive against the SHA-1 (Google's index) or SHA-512 (Microsoft's release metadata) that the same HTTPS service gives. A compromised index endpoint can pass a bad archive with a matching hash. There is no detached signature.
- Files: `porter/fetch.py` (`GOOGLE_INDEX`, `DOTNET_INDEX`, `_download`), `packaging/build_bootloader.py` (PyInstaller sdist, hash from PyPI JSON on the same host)
- Current mitigation: HTTPS, and the user confirms each download in the GUI (`gui/app.py` `confirm_download`).
- Recommendations: record the expected hashes of the archives the project has tested in the repository (for example in `docs/RELEASE_CHECK.md`), and warn when a downloaded archive's hash differs from the recorded one.

## Performance Bottlenecks

**Full rebuild of the data pack on any change:**
- Problem: `porter/datapack.py` `build` removes the whole pack folder (`shutil.rmtree(dst)`) and renames the new one into place, after `link_tree` has created hard links for every file. The docstring says the pack "is rebuilt whole when anything in it changes."
- Files: `porter/datapack.py`
- Cause: the swap is not atomic: between the `rmtree` and the `rename`, the previous complete pack is gone, and a crash there leaves no pack at `dst`.
- Improvement path: rename the old pack aside first, rename the new one in, then delete the old one.

**Install reads whole files into memory to compare MD5s:**
- Problem: `porter/adb.py` `push_tree` calls `hashlib.md5(p.read_bytes())` for each file that is a candidate for content verification, which reads the whole file into memory. Device-side hashes come from `md5sum` in batches of 64 (`remote_md5`).
- Files: `porter/adb.py` (`push_tree`, `remote_md5`), `porter/install.py` (the `verify` predicate)
- Cause: the predicate excludes `RomFS` and `aoc`, so the cost falls on `mods/` files. A game with large rewritten modules pays the full read on every install.
- Improvement path: hash in chunks over a file handle, and cache host-side hashes per build.

## Fragile Areas

**The engine's shader and rewrite steps depend on exact upstream outputs:**
- Files: `porter/pipeline.py` (`check_graphics`, `fps_unlock`, `shaders`), `porter/upstream.py`, `nxnative/scripts/build_ipa_from_nsp.py`
- Why fragile: the port reads upstream's report strings and file layouts (for example `re.search(r'^(\d+) of (\d+) shaders', ...)` in `shaders`, and `profile_guess.build_sources` keys). A wording change upstream turns into a "no shader translated" or wrong-profile failure.
- Safe modification: change the upstream call and its parser in the same commit, and run `tests/test_porter.py`.
- Test coverage: the parsers are not tested directly.

**Per-game data sits next to shared core in one tree:**
- Files: `nxnative/dm/games/<title ID>/`, `nxnative/dm/android/`, `nxnative/dm/host/`
- Why fragile: `tests/arch_rules.py` enforces that Android code has no title IDs or game names, but the check is regex-based and skips quoted strings that contain game names. A title ID split across a string concatenation would pass.
- Safe modification: keep `arch_rules.py` runnable in CI and add a case for string concatenation.

**Commit hygiene is opt-in:**
- Files: `.githooks/commit-msg`, `.githooks/commit_msg.py`, `README.md` ("Commit messages")
- Why fragile: the hook runs only after `git config core.hooksPath .githooks`. In this clone that setting is unset, so commits are not checked (`git config --get core.hooksPath` returned nothing). `README.md` says the commits before 2026-10-28 predate the rule.
- Safe modification: add the setting to a documented bootstrap step, or have `porter`'s developer scripts check it.

**Tests that must import the full engine:**
- Files: `tests/test_porter.py`, `porter/upstream.py`
- Why fragile: `python -m unittest discover tests` imports `porter.pipeline` at module load in `tests/test_porter.py`. Without the requirements installed, the whole suite errors at import (observed: 9 tests ran, one import error, one skip). The C tests compile with `cc` at test time (`tests/test_vk_layout_cache.py`, `tests/test_vk_present_timing.py`, `tests/test_perf_adaptive.py`) and need a C compiler on the test machine.
- Safe modification: state the requirements in the test's module docstring, or skip with a clear message when `lz4` is absent.

## Scaling Limits

**Disk use per port:**
- Current capacity: `porter/pipeline.py` `check_space` requires `2 * game files - built + 1 GiB` free on the game folder's drive. The NEO port is noted at 7 GB of build folder for 6.8 GB of game files. `porter/toolchain.py` `DISK_GB = 20` is the setup-check threshold.
- Limit: a large game (for example Viractal with 1.4 GB of files producing 2.7 GB of build, per the comment) on a nearly full drive stops mid-extraction if the estimate is wrong, because the check counts only top-level files in the game folder.
- Scaling path: count files recursively and the DLC folders the port reads, and re-check after extraction.

**Single-process port:**
- Current capacity: one port at a time per GUI window. `gui/app.py` disables Port while a run is active, but two windows or a CLI run can start the same folder (see concern 5).
- Limit: no cross-process lock.
- Scaling path: see concern 5.

## Dependencies at Risk

**Unpinned Python dependencies:**
- Risk: `requirements.txt` lists `lz4`, `capstone`, `pillow`, `pyyaml`, `PySide6` and `backports.zstd` without version bounds. A major version change in PySide6 or capstone can break the GUI or the rewriter without any code change.
- Impact: builds of the bundle (`packaging/build_bundle.py`) and developer setups can resolve differently.
- Migration plan: pin the tested versions (or a lower and upper bound) and record them in `docs/RELEASE_CHECK.md` next to the results.

**Undeclared modules in developer tools:**
- Risk: `devtools/burst.py` imports `numpy`, `devtools/rec_flicker.py` imports `av` (PyAV) and `numpy`, and `devtools/nso_image.py` imports `lz4.block`. `numpy` and `av` are not in `requirements.txt`.
- Impact: these scripts fail on a fresh setup with `ModuleNotFoundError`.
- Migration plan: add a `requirements-dev.txt` with `numpy` and `av`, or note the requirement in each script's header.

**Vendored third-party code and its records:**
- Risk: `nxnative/dm/third_party/README.md` records versions for libvpx (v1.17.0, unmodified), stb_vorbis (1.22, unmodified), vulkan-headers (1.4.363, unmodified) and Ryujinx (1.3.2 with local changes listed in `nxnative/dm/third_party/ryujinx/README.md`). The NVIDIA FLIP entry says "Not recorded in the directory".
- Impact: the FLIP version cannot be checked for updates or known issues. The Ryujinx local patches must be re-applied by hand after any re-vendoring.
- Migration plan: record the FLIP upstream commit, and keep a patch file (`git format-patch` output) for the Ryujinx local changes so a re-vendor can reapply them mechanically.

**Subtree sync with a diverged tree:**
- Risk: `README.md` ("Updating nxnative") uses `git subtree pull --prefix nxnative ... --squash`. The tree contains a large Android layer (`nxnative/dm/android/`), per-game profiles, and local edits to shared core (`dm/host`, `dm/gfx`, `dm/tools`, `dm/third_party`), and `porter/upstream.py` reaches into `scripts/build_ipa_from_nsp.py` internals. `docs/ARCHITECTURE.md` says the diff to upstream must stay small, but no check measures it.
- Impact: a squashed subtree pull will conflict in the shared core and may silently change the functions `porter/upstream.py` overrides.
- Migration plan: measure the diff against the recorded upstream commit (`6034fca`, per the subtree history) before each pull, and run `tests/arch_rules.py` and `tests/test_porter.py` after the merge.

## Missing Critical Features

**No automated Windows/macOS/Linux bundle build or check:**
- Problem: `packaging/build_bundle.py` runs only on Windows (`packaging/build_bootloader.py` compiles the launcher with the MSVC toolchain, and `is_local()` checks `PyInstaller/bootloader/Windows-64bit-intel`). `docs/RELEASE_CHECK.md` describes a Windows-only manual check.
- Blocks: shipping for macOS or Linux, and automated release verification.

**No GUI tests and no GUI release check:**
- Problem: `docs/RELEASE_CHECK.md` says "`gui/` or docs only: nothing (start the app once)". Nothing in `tests/` imports `gui`.
- Blocks: refactoring the GUI without a regression check.

## Test Coverage Gaps

**GUI (`gui/app.py`, `gui/runner.py`, `gui/__main__.py`):**
- What's not tested: the Porter event stream (`Porter._out`, `_done`), cancel, the Setup tab's save and check, and the Games table.
- Files: `gui/runner.py`, `gui/app.py`
- Risk: the cancel bug in concern "GUI cancel on macOS and Linux" and the silent failures above went unnoticed.
- Priority: High

**Downloads and unpacking (`porter/fetch.py`):**
- What's not tested: `_unzip` symlink handling, `_untar` with and without filter, checksum mismatch cleanup, `_install` folder logic.
- Files: `porter/fetch.py`
- Risk: the zip-slip path above; a wrong `into` for a `.NET` archive.
- Priority: High

**ADB and install (`porter/adb.py`, `porter/install.py`):**
- What's not tested: `push_file` resume, `remote_sizes` parsing, `install` with `replace_signer`, the stale-file removal.
- Files: `porter/adb.py`, `porter/install.py`
- Risk: data loss on the device if the stale-file list is wrong.
- Priority: Medium

**Toolchain detection (`porter/toolchain.py`, `porter/paths.py`):**
- What's not tested: `find_ndk` preference order, `find_dotnet` on Windows and macOS paths, `user_dir` per platform.
- Files: `porter/toolchain.py`, `porter/paths.py`
- Risk: the wrong NDK or SDK picked silently; the port's `Check` results mislead the Setup tab.
- Priority: Medium

**Devtools (`devtools/*.py`, `devtools/*.sh`):**
- What's not tested: all devtools. `devtools/device.py` resolves the device and package used by every script.
- Files: `devtools/`
- Risk: scripts that push or delete on the wrong device if `devtools/device.json` is wrong.
- Priority: Low

## Cross-Platform Blockers

These matter for the planned cross-platform GUI. The engine and the pipeline already branch on `os.name` and `sys.platform` in many places (`porter/paths.py`, `porter/toolchain.py`, `porter/fetch.py`, `porter/adb.py`, `nxnative/dm/android/build.py`, `nxnative/scripts/build_ipa_from_nsp.py`), so the remaining blockers are concentrated in the GUI, the packaging and the developer tools.

| Location | What is Windows-specific or POSIX-only | Effect on macOS/Linux | Fix |
|----------|----------------------------------------|----------------------|-----|
| `gui/runner.py` `cancel` | `taskkill /T /F` on Windows; `QProcess.kill()` elsewhere | Children survive a cancel (concern 1) | Process group kill (see Known Bugs) |
| `gui/app.py` | `Consolas` vs `Menlo` font choice by `os.name` | Falls back to Qt's default font on Linux | Use `QFontDatabase` or the system monospace font |
| `packaging/nx2android.py` | Hides the console with `ctypes.windll` on `nt` only | Correct on other platforms; no other platform's bundle exists | Keep the guard; add a platform-neutral entry point |
| `packaging/build_bootloader.py` | MSVC build with `waf`; checks `Windows-64bit-intel` | No macOS/Linux bootloader step; PyInstaller's prebuilt launchers are not flagged there | Make the step Windows-only and document the others |
| `packaging/build_bundle.py` | Requires `is_local()`, which is Windows-only | Build refuses to run on macOS/Linux | Make the check conditional on `os.name == 'nt'` |
| `packaging/nx2android.spec` | `console=True` single-folder build; no icon or `.app` bundle | Produces a folder, not an app bundle, on macOS | Add a `BUNDLE` target for macOS |
| `packaging/INSTALL.md` | Windows install steps only | Users on other platforms have no guide | Add platform sections |
| `devtools/*.sh` | POSIX shell; `MSYS_NO_PATHCONV=1` is for Git Bash on Windows | Work on macOS/Linux; the env var is harmless there | Keep; note in the header |
| `devtools/burst.py`, `devtools/rec_flicker.py` | `numpy` and `av` not declared (see Dependencies at Risk) | Fail on any platform without them | Declare them |
| `porter/adb.py` `LONG_PATH` | Windows MAX_PATH workaround via `short_paths` | Not applied on macOS/Linux, which is correct | None |
| `nxnative/scripts/build_ipa_from_nsp.py` `TOOL_PATHS` | Homebrew paths, used only by upstream's iOS `main()` | None for the port, which does not call `main()` | None needed for the port |
| `docs/RELEASE_CHECK.md` | Windows PC release check | No macOS or Linux verification | Add per-platform rows |

Other potential blockers that need no change today: `porter/paths.py` already selects `%APPDATA%`, `~/Library/Application Support` or `~/.config`. `porter/toolchain.py` already searches `ANDROID_HOME`, `~/Library/Android/sdk` and `~/Android/Sdk`. `porter/fetch.py` already maps platforms to Google's and Microsoft's identifiers (`windows`, `macosx`, `linux`; `win`, `osx`, `linux`). `nxnative/dm/android/build.py` already chooses the NDK host folder per platform.

## Existing `gui/` Directory: State

- Size: 4 files, about 500 lines (`gui/app.py` 367, `gui/runner.py` 69, `gui/__main__.py`, `gui/__init__.py`).
- Design: a PySide6 front end that runs `python -m porter …` with `QProcess` and reads newline-delimited JSON events (`gui/runner.py`). It holds no pipeline logic, as `docs/ARCHITECTURE.md` requires. Its three tabs are Port, Setup and Games.
- Good foundation for a cross-platform GUI: the process boundary keeps the pipeline platform-neutral, and `porter/paths.py` already encodes per-platform settings locations.
- What needs work before it is robust:
  - No tests (see Test Coverage Gaps).
  - Cancel is wrong on macOS and Linux (Known Bugs).
  - Errors from the child process are reduced to its last stderr line, and `call_json` discards stderr entirely.
  - No window-close guard: `gui/app.py` has no `closeEvent`, so closing the window during a port does not ask for confirmation or stop the run. Whether the child survives the GUI's exit depends on Qt's `QProcess` teardown; this was not verified.
  - No timeouts on `call_json` requests. A hung `porter inspect` on a very large folder leaves the card at "Reading the game folder…" with no way to cancel, and the Setup tab's Download button stays disabled while `porter tools --json` runs.
  - The monospace font is chosen by `os.name` (`Consolas` or `Menlo`), which falls back on other systems.
  - Game names from the control data are put into rich-text labels without escaping (`PortTab.on_inspect` in `gui/app.py` uses `info["name"]` inside `<b>…</b>`), so a name containing `<` or `&` renders wrongly and can inject markup.
- `LANGUAGES` in `gui/app.py` duplicates the language list that upstream keeps as `nacp.LANGUAGES` (`nxnative/dm/tools/nacp.py`). Keep one source.

## Third-Party Code: Patching, Pinning and Syncing

- Pins: `nxnative/dm/third_party/README.md` lists versions for libvpx, stb_vorbis and vulkan-headers. These are unmodified copies. Ryujinx is a vendored subset with local changes documented in `nxnative/dm/third_party/ryujinx/README.md`.
- Patching: the local Ryujinx changes are not kept as a patch file, so they can only be reapplied by hand.
- Syncing: `README.md` documents `git subtree pull` for `nxnative/`. See the Subtree sync concern under Dependencies at Risk.
- Unrecorded version: NVIDIA FLIP has no version or commit recorded (`nxnative/dm/third_party/README.md`).
- Adapted code outside the directory: `nxnative/dm/gfx/nvn/nvn_mtl.m` and `nxnative/dm/gfx/tools/dmsh_xlate/Program.cs` contain MacNativeGames-derived code and deko3d-derived layout code. Each is named in `nxnative/dm/third_party/README.md`, so attribution is recorded, but the adapted code has no version pin.

---

*Concerns audit: 2026-10-29*

## Closure (Phase 2)

**Closed:** 2026-10-30. One row per concern above: the phase and plan that closed it and the test or file that shows it, or "no action" with the reason. Phase 1 rows come from `.planning/phases/01-bridge-bundles-and-ci/01-VERIFICATION.md`; Phase 2 rows from the 02-01 to 02-10 summaries.

| Concern (its bold heading, row or bullet) | Closed by | Evidence |
|-------------------------------------------|-----------|----------|
| Monkey-patched upstream module at import time | Phase 2, 02-05: `_overrides(m)` checks every attribute it replaces and fails at import naming the missing one | `tests/test_porter.py` Overrides |
| Process-wide environment mutation in the port pipeline | Phase 2, 02-05: every child gets `self.env`; `os.environ` is never written; `build_nx_extract` runs dotnet by absolute path | `tests/test_porter.py` Env |
| Shared work directory with the iOS build | Phase 2, 02-01: the sharing rule is in `docs/ARCHITECTURE.md`, and porter locks `<tid>_build/.porter.lock` | `tests/test_lock.py` Lock, `docs/ARCHITECTURE.md` |
| `inspect` failure is reported as "no game found" | Phase 1, 01-04: the card shows porter's error document, the stderr tail or the timeout with Retry; Phase 2, 02-07 pins inspect's error paths | `tests/test_bridge.py` Timeout (test_inspect_card_retry), `tests/test_cli.py` ErrorPaths |
| Tracked and untracked repository hygiene | Phase 2, 02-03: `*.code-workspace` is ignored | `.gitignore`, `tests/test_housekeeping.py` Hooks (test_workspace_ignored) |
| GUI cancel on macOS and Linux leaves children running | Phase 1, 01-02 and 01-03: porter runs in its own session (a Job Object on Windows) and stop kills the whole tree | `tests/test_bridge.py` Stop, `tests/test_runlog.py` Stop |
| Missing dependency reported as a network or empty-list failure | Phase 1, 01-04 (one-shot calls show the stderr tail) and 01-07 (a missing `lz4` is a named skip, a failure in CI) | `tests/test_bridge.py` Errors (test_doctor_crash_shows_stderr), `tests/test_porter_guard.py` |
| `PortTab.cancel` reports cancellation before the child exits | Phase 1, 01-03: "cancelled" is shown only once the run has stopped | `tests/test_bridge.py` Stop (test_port_tab_status) |
| Zip extraction writes symlinks from unsanitized member names | Phase 2, 02-04, 02-11 and 02-13: every member name and every link is checked from the archive's own member list before anything is written; each link is resolved in memory from the folder that is installed (the top folder stripped as on install), so member order and the move into place cannot change the answer | `tests/test_fetch.py` Unpack (test_link_to_sibling_refused, test_relocated_link_refused, test_link_loop_refused, test_link_through_later_link_refused) |
| Tar extraction falls back to unfiltered extraction on older Pythons | Phase 2, 02-04: `filter='data'` plus the same name check, and the Python floors 3.11.13 / 3.12.11 / 3.13.4 / 3.14 | `tests/test_fetch.py` Unpack (test_tar_refused), `tests/test_toolchain.py` PythonFloor |
| APK signing key is stored unencrypted with default permissions | Phase 2, 02-02: written once, whole and 0600; an unreadable key stops with the recovery steps; the doctor's Signing key row | `tests/test_signing.py` Key, Preflight |
| Duplicate, diverged signing code under `probes/` | Phase 2, 02-02: the probe app uses nxnative's `mkapk.py`; the copy is gone | `tests/test_signing.py` Probe |
| Third-party configuration fetched at port time and applied to game memory | Phase 2, 02-08: fetched at the commit pinned in `porter/pins.py` `FPSLOCKER`; the commit and the config's SHA-256 are in the log, `fpslock.tsv` and `patches.py` | `tests/test_porter.py` FpsLocker |
| Download integrity relies on the same origin as the archive | Phase 2, 02-04 (toolchains pinned by version and hash in `porter/pins.py`) and 02-10 (NuGet packages pinned by content hash in `pins.NUGET`) | `tests/test_fetch.py` Pins, `tests/test_nuget.py` Check, Pins |
| Full rebuild of the data pack on any change | Phase 2, 02-01: the old pack is renamed aside first, so a crash leaves one whole pack (the rebuild itself takes seconds and stays) | `tests/test_datapack.py` Swap |
| Install reads whole files into memory to compare MD5s | Phase 2, 02-01: `adb.md5` hashes in pieces | `tests/test_datapack.py` Swap (test_md5_in_pieces), `tests/test_adb.py` Push |
| The engine's shader and rewrite steps depend on exact upstream outputs | Phase 2, 02-03: the strings and keys porter parses are pinned by tests | `tests/test_housekeeping.py` UpstreamOutput |
| Per-game data sits next to shared core in one tree | Phase 2, 02-03: `arch_rules.py` joins split string literals before it looks for title IDs | `tests/arch_rules.py` (run by `tests/test_architecture.py`) |
| Commit hygiene is opt-in | Phase 2, 02-03: `python devtools/hooks.py` turns the hook on and README says to run it (D-11: nothing checks that it was run) | `devtools/hooks.py`, `tests/test_housekeeping.py` Hooks |
| Tests that must import the full engine | Phase 1, 01-07: a missing engine module is a named skip locally and a failure in CI | `tests/test_porter_guard.py` |
| Disk use per port | Phase 2, 02-05: `check_space` counts what the port reads, DLC included, and checks again after extraction | `tests/test_porter.py` Misc (check_space) |
| Single-process port | Phase 2, 02-01 (one port or install per build folder) and 02-10 (builds of the tools every game shares take turns) | `tests/test_lock.py` Lock, `tests/test_nuget.py` Check (test_restored_holds_tools_lock) |
| Unpinned Python dependencies | Phase 1, 01-01: hashed locks from `requirements*.in` | `tests/test_workflows.py` Lock |
| Undeclared modules in developer tools | Phase 1, 01-01: `numpy` and `av` declared in `requirements-dev.in` and locked apart | `requirements-dev.in`, `tests/test_workflows.py` Lock (test_dev_apart) |
| Vendored third-party code and its records | Phase 2, 02-03: FLIP v1.7 (commit `b475eb4`) recorded; the Ryujinx local changes kept as a proven patch | `tests/test_housekeeping.py` Records |
| Subtree sync with a diverged tree | Phase 1, 01-08: the release workflow reports the `nxnative/` diff to upstream (CI-04, a report, not a gate); Phase 2 kept subtree edits to hook lines | `.github/workflows/fork-release.yml` (upstream-diff), `tests/arch_rules.py` |
| No automated Windows/macOS/Linux bundle build or check | Phase 1, 01-06 and 01-08: one build script for the four hosts, smoke-tested in `fork-release.yml` | `tests/test_packaging.py`, `tests/test_workflows.py` Release |
| No GUI tests and no GUI release check | Phase 1, 01-03 and 01-04: headless GUI tests and golden protocol streams, run in CI on every push | `tests/test_bridge.py` |
| GUI (`gui/app.py`, `gui/runner.py`, `gui/__main__.py`) | Phase 1, 01-03 and 01-04 | `tests/test_bridge.py` Fake, Stop, Close, Replay |
| Downloads and unpacking (`porter/fetch.py`) | Phase 2, 02-04 | `tests/test_fetch.py` Pins, Unpack |
| ADB and install (`porter/adb.py`, `porter/install.py`) | Phase 2, 02-07 | `tests/test_adb.py` Sizes, Push, Install |
| Toolchain detection (`porter/toolchain.py`, `porter/paths.py`) | Phase 2, 02-07 | `tests/test_toolchain.py` Detection |
| Devtools (`devtools/*.py`, `devtools/*.sh`) | Phase 2, 02-07 for `devtools/device.py`, the resolver every script uses; no action for the other scripts: they are by-hand device tools with no logic of their own to pin | `tests/test_cli.py` DeviceTool |
| Cross-platform: `gui/runner.py` `cancel` | Phase 1, 01-02 and 01-03 | `tests/test_bridge.py` Stop |
| Cross-platform: `gui/app.py` font | Phase 2, 02-09: the system fixed-width font | `tests/test_bridge.py` Escaping (test_log_font) |
| Cross-platform: `packaging/nx2android.py` | No change needed: its Fix column says keep the guard; the other hosts' entry point came with 01-06 | `tests/test_packaging.py` Bundle |
| Cross-platform: `packaging/build_bootloader.py` | Phase 1, 01-06 | `tests/test_packaging.py`, `.github/workflows/fork-release.yml` |
| Cross-platform: `packaging/build_bundle.py` | Phase 1, 01-06: builds on all four hosts | `tests/test_packaging.py` Bundle |
| Cross-platform: `packaging/nx2android.spec` | Phase 1, 01-06: `nx2android.app` in a DMG on macOS | `tests/test_packaging.py` Bundle |
| Cross-platform: `packaging/INSTALL.md` | Phase 1, 01-06: the four-host install guide | `packaging/INSTALL.md` |
| Cross-platform: `devtools/*.sh` | No change needed, per its Fix column ("Keep; note in the header") | `devtools/soak.sh` |
| Cross-platform: `devtools/burst.py`, `devtools/rec_flicker.py` | Phase 1, 01-01: declared in the dev lock | `requirements-dev.in` |
| Cross-platform: `porter/adb.py` `LONG_PATH` | No action: correct as it is (its Fix column says None) | `porter/adb.py` |
| Cross-platform: `build_ipa_from_nsp.py` `TOOL_PATHS` | No action: the port never calls upstream's `main()` | `nxnative/scripts/build_ipa_from_nsp.py` |
| Cross-platform: `docs/RELEASE_CHECK.md` | Phase 1, 01-08: the four-host release check | `docs/RELEASE_CHECK.md` |
| `gui/` bullet: no tests | Phase 1, 01-03 and 01-04 | `tests/test_bridge.py` |
| `gui/` bullet: cancel is wrong on macOS and Linux | Phase 1, 01-02 and 01-03 | `tests/test_bridge.py` Stop |
| `gui/` bullet: errors reduced to the last stderr line, `call_json` discards stderr | Phase 1, 01-03 (failed run: cause and Open log) and 01-04 (one-shot: stderr tail inline) | `tests/test_bridge.py` Errors |
| `gui/` bullet: no window-close guard | Phase 1, 01-03: closing mid-port asks, then stops the run | `tests/test_bridge.py` Close |
| `gui/` bullet: no timeouts on `call_json` | Phase 1, 01-04: per-command limits that kill the call's session | `tests/test_bridge.py` Timeout |
| `gui/` bullet: monospace font chosen by `os.name` | Phase 2, 02-09 | `tests/test_bridge.py` Escaping (test_log_font) |
| `gui/` bullet: game names in rich text unescaped | Phase 2, 02-09: every interpolated string html-escaped | `tests/test_bridge.py` Escaping (test_card_escapes) |
| `gui/` bullet: `LANGUAGES` duplicates `nacp.LANGUAGES` | Phase 2, 02-09: the list comes from `porter inspect`, from upstream's `nacp.LANGUAGES` | `tests/test_cli.py` Languages, `tests/test_bridge.py` Escaping (test_one_language_source) |
| Third-party: pins | Phase 2, 02-03 | `tests/test_housekeeping.py` Records |
| Third-party: patching (Ryujinx changes only by hand) | Phase 2, 02-03: `nxnative-local.patch` against Canary-1.3.351, proven to apply | `nxnative/dm/third_party/ryujinx/nxnative-local.patch`, `tests/test_housekeeping.py` Records (test_ryujinx_patch) |
| Third-party: syncing | Phase 1, 01-08 (CI-04 report) | `.github/workflows/fork-release.yml` (upstream-diff) |
| Third-party: unrecorded FLIP version | Phase 2, 02-03 | `tests/test_housekeeping.py` Records (test_flip_version) |
| Third-party: adapted code outside the directory | No action: attribution recorded in `nxnative/dm/third_party/README.md`; the adapted code is maintained as engine code | `nxnative/dm/third_party/README.md` |
