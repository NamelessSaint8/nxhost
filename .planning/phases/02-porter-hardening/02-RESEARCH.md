# Phase 2: Porter Hardening - Research

**Researched:** 2026-10-30
**Domain:** Python CLI hardening: safe archive extraction, pinned downloads, OS file locks, atomic writes, env-dict subprocesses, upstream subtree edits, PySide6 escaping
**Confidence:** HIGH (most claims probed against the live code, the vendor indexes and real archives this session)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

#### Carried forward (decided earlier, not re-asked)
- Edits to upstream's busy files (`porter/cli.py`, `porter/pipeline.py`, `gui/app.py`) stay at hook lines. New logic goes in new porter files (Phase 1).
- Phase 1's D-08 "run in progress" marker (`porter/runlog.py` `build_folder`) was always meant to be replaced by HARD-05's per-stage stamps. D-08 below settles what stays.
- Protocol changes are additive only, with no version field (Phase 1).
- Already closed in Phase 1, so not redone here: cancel of the process tree, `call_json` keeping stderr, one-shot timeouts, the inspect error shown as the real cause, the window-close guard, pinned and hashed Python locks, cross-platform packaging.

#### Download pinning (PKG-07, HARD-03)
- **D-01:** One manifest in the repository pins each toolchain download (Android NDK r27c, one exact .NET SDK 10.0.x, one exact platform-tools release) by exact version, URL and hash. The downloader fetches the pinned URL. A pinned file that downloads but fails its hash stops with a clear message naming the file and both hashes.
- **D-02:** When the vendor no longer serves the pinned file (for example, Google's index lists only the newest platform-tools), porter falls back to the vendor's newest release, checks it against the vendor's own index hash (today's check), and warns in the log and the GUI that this version is untested. A pinned URL that is gone is not a "mismatch" and does not stop Setup.
- **D-03:** FPSLocker: the manifest pins one FPSLocker-Warehouse commit SHA, and configs are fetched at that commit (`raw.githubusercontent.com/.../<commit>/...` instead of the moving `v4` branch). When that commit has no config for the game's build (a game version newer than the pin), porter fetches from `v4` head and warns. Either way, the port log shows the commit the config came from and its SHA-256, and both are recorded in the build folder. Moving to newer configs is a one-line manifest bump.
- **D-04:** Toolchains the player already has (an NDK via `ANDROID_NDK_HOME`, a system .NET, a distro adb) keep today's checks (`porter/toolchain.py`: the NDK r27c revision, .NET major 10, adb present). The manifest governs only what porter downloads.
- **D-05:** NuGet pins live in porter's manifest only: each package (LibHac 0.19.0 for `nx_extract`, and the packages the Ryujinx projects restore for `dmsh_xlate`) with its exact version and SHA-512. After restore, porter compares them with the restored `.nupkg.sha512` files and stops on any mismatch, naming the package. No `packages.lock.json` goes into the nxnative subtree. The developer chose this over the research's lock-file recommendation (`.planning/research/PITFALLS.md` §14), accepting that the check runs after restore.

#### Concurrent and cut-off ports (HARD-04, HARD-05, HARD-07)
- **D-06:** A second port of the same game folder stops at once with "already running", naming the command holding the lock (port or install), its PID and its start time. The GUI shows it on the game card like any porter error. The lock is an OS file lock (`fcntl.flock` on POSIX, `msvcrt.locking` on Windows) on a file in `<tid>_build/`. The OS releases it when the holder dies, so a crash can never leave a stale lock to clear by hand.
- **D-07:** `porter port` and `porter install` of the same game take the same lock, so an install never pushes a pack that is halfway through its swap. Upstream's iOS script (`nxnative/scripts/build_ipa_from_nsp.py` `main()`) does not take it. The rule that iOS and Android builds share `<tid>_build/` is written down in `docs/ARCHITECTURE.md`.
- **D-08:** The "stamp last, atomically" fix goes into the subtree as a small, platform-neutral edit to `nxnative/scripts/build_ipa_from_nsp.py`: the reuse-key write becomes temp + `os.replace`, and any stage that writes its outputs in place is fixed to swap them in before its key is written. It also fixes the iOS build and is worth offering upstream. It is not done by overriding upstream helpers from porter.
- **D-09:** Once the stamps land, Phase 1's D-08 marker keeps only its message: the next port still says "the last port of this game was cut off in <stage>", but only stages whose stamps don't match run again. The redo-every-stage behaviour is removed.

#### Housekeeping (HARD-10)
- **D-10:** `probes/app/mkapk.py` is deleted. The probe app's build instructions (the header of `probes/app/probeapp.c`) call the committed `nxnative/dm/android/apk/mkapk.py` with `--lib`, `--package`, `--label` and an explicit key path. That leaves one signer, so the 0600/atomic key fix covers both.
- **D-11:** The commit hook is bootstrapped by a small devtools script that runs `git config core.hooksPath .githooks`. The README's contributor section says to run it once. No test fails or warns when it hasn't been run.
- **D-12:** The language list has one source, upstream's `nacp.LANGUAGES`. `porter inspect` adds the game's supported languages to its JSON (codes and names, from the control data's supported-language flags via `nacp`), and the GUI's language box fills from that. `gui/app.py`'s own `LANGUAGES` list goes away.

### Claude's Discretion
These follow the research defaults (`.planning/research/PITFALLS.md`, `.planning/codebase/CONCERNS.md`). Raise a `checkpoint:decision` only if one turns out to be one-way.
- **Manifest format and location:** one file (for example JSON at a stable repo path), readable by porter and by CI. Phase 3 adds the community arm64 NDK and its hash to the same file. The bump procedure is documented beside it (a version bump is a one-line change after a test).
- **Fallback bounds (D-02):** a fallback never takes a version that `toolchain.checks()` would reject. The NDK stays r27c (no fallback to another NDK), and .NET stays on major 10.
- **NuGet check (D-05):** consider restoring into a porter-owned `NUGET_PACKAGES` folder under the user dir, so a package that fails its hash can be removed and isn't shared with the player's global NuGet cache. Ryujinx's unversioned references are already pinned centrally by `nxnative/dm/third_party/ryujinx/Directory.Packages.props`. The manifest records what that resolves to.
- **Signing key (HARD-02):** write with `tempfile.mkstemp(dir=key.parent)` (0600), fsync (`F_FULLFSYNC` on macOS), then `os.replace`. A key that exists but can't be read or parsed stops the run with a message naming the file and the recovery: restore it from a backup, or remove it deliberately and reinstall every port with `--replace-signer`. Never regenerate silently. Whether to tighten an existing world-readable key to 0600 on first read is your call. Mode bits mean nothing on Windows, so say so in a comment. The fix lives in `nxnative/dm/android/apk/mkapk.py`, the fork's Android layer, outside the shared-core folders the subtree constraint protects.
- **Hostile archives (HARD-01):** refuse the whole archive on any member with `..`, an absolute path, or a link that resolves outside the unpack folder, and remove the partial unpack. Tar uses `filter='data'` unconditionally. Where the Python refusal (< 3.11.13 / 3.12.11 / 3.13.4) sits: `doctor` must still run and show it as a red row, and the other commands refuse.
- **Data pack swap (HARD-07):** rename the old pack aside, rename the new one in, then delete the old one. On the next run, a missing pack with an aside copy present is restored. Install hashes files in chunks over a file handle.
- **Env dicts (HARD-06):** subprocesses get a copied env with absolute tool paths. Windows resolves a bare program name through the parent's PATH, not the child env's (research pitfall). Upstream's `build_nx_extract` runs `dotnet` by bare name, so that call needs the absolute path, either as a small subtree edit (as D-08) or by passing it in. The four upstream overrides in `porter/upstream.py` move into one named function, with a comment each and an import-time assert that each attribute exists.
- **Smaller items:** escape control-data strings in rich-text labels (`html.escape`, or plain-text labels); the log pane uses `QFontDatabase.systemFont(QFontDatabase.FixedFont)` in place of `Consolas`/`Menlo`; `check_space` counts files recursively, including DLC folders, and re-checks after extraction; record the FLIP upstream commit in `nxnative/dm/third_party/README.md`; keep the Ryujinx local changes as a patch file; add `*.code-workspace` to `.gitignore`.
- **D-12 edge case:** a game whose control data has no supported-language flags gets the full `nacp.LANGUAGES` list.
- **TEST-01 approach:** crafted zip and tar archives built in temp dirs; downloads tested with a patched `_get`/`urlopen` or a local `http.server`; adb through a fake `adb` script or a stub `Adb.run` (following Phase 1's `fake_porter` pattern); per-OS toolchain detection by patching `sys.platform` and env, with CI running the suite on all four hosts; CLI error paths through the JSON outputs. Add a test that kills a stage mid-run and checks that the next run redoes it (PITFALLS §4).

### Deferred Ideas (OUT OF SCOPE)
None. The discussion stayed within the phase scope.

Also out of scope per CONTEXT.md `<domain>`: the Linux arm64 community NDK and its pinned hash (Phase 3), NuGet restore during Setup (Phase 3), the download Cancel button (Phase 3, FRUN-01), per-game settings UI (Phase 4).
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| HARD-01 | Zip and tar extraction cannot write outside the unpack folder; tar uses `filter='data'`; porter refuses Pythons without the CVE-2025-4517 fix | Hole reproduced in today's `_unzip`; real NDK r27c zips (darwin, linux) and the .NET 10.0.403 tarball pass the strict rules; Python floor check via version floors OR `os.path.ALLOW_MISSING` (§ Pattern 1, 2) |
| HARD-02 | Signing key 0600, atomic, refuse to regenerate an unreadable key | mkapk.py:193-198 rewrite with `mkstemp` + fsync + `os.link` no-clobber publish; porter preflight (§ Pattern 7) |
| HARD-03 | FPSLocker pinned commit or hash recorded and shown | Pinned raw URL serves 200 at a commit, 404 when absent; `v4` head SHA from the GitHub API with `Accept: application/vnd.github.sha` (§ Pattern 4) |
| HARD-04 | "already running" build-folder lock | `porter/lock.py` with `flock` / `msvcrt.locking`; install lock goes in `cmd_install`, never in `install.install` (§ Pattern 5) |
| HARD-05 | Cut-off stage redone on the next run | Per-stage audit: every keyed stage already deletes its key first; real holes are elsewhere (table in § Pattern 6) |
| HARD-06 | Env dicts with absolute tool paths; upstream overrides named and asserted | Four upstream subprocess sites run with `env=None` or bare `dotnet`; in-process `game.load` reads `os.environ` (§ Pattern 8) |
| HARD-07 | Data-pack swap never leaves no pack; install hashes in chunks | Aside-rename swap + `recover()`; `hashlib.file_digest` (§ Pattern 6, Code Examples) |
| HARD-08 | Control-data strings escaped in the GUI | Unescaped interpolations listed in gui/app.py (§ Pattern 10) |
| HARD-09 | Recursive disk-space check incl. DLC, re-check after extraction | `scan_nsps` reads only top-level files; count the scanned family plus a re-check after `extract()` (§ Pattern 11) |
| HARD-10 | Housekeeping (probe signer, FLIP version, Ryujinx patch, hook bootstrap, `*.code-workspace`, one language list) | FLIP = NVlabs/flip `b475eb4` (v1.7); vendored Ryujinx is NOT 1.3.2 but Canary-1.3.351 `475615f` + 15 changed files; `inspect` cannot read control data without an extraction (§ Pattern 12) |
| PKG-07 | Toolchains and NuGet pinned in one manifest | Pin values read from the vendor indexes this session; old URLs stay served; NuGet compare against `project.assets.json` `sha512` (contentHash), 58 packages (§ Pattern 3) |
| TEST-01 | Tests for downloads/unpacking, adb/install, per-OS toolchain detection, CLI error paths | Mock `subprocess.run` inside `porter.adb`; crafted archives; patched `urlopen`; `os._exit` models SIGKILL (§ Validation Architecture) |
</phase_requirements>

## Summary

Phase 2 is almost entirely standard-library work inside porter, plus a few small subtree edits. No new package is installed. The research checked each locked decision against the live code and the real vendor artifacts, and found five things the planner must know that the CONTEXT does not say:

1. **The NuGet hash to compare is the `contentHash`, not `.nupkg.sha512`.** In a real restore of both projects this session, `libhac.0.19.0.nupkg.sha512` held `hWsrphNcx…` (the SHA-512 of the signed file), while `project.assets.json` and `.nupkg.metadata` held `7uMUGFpO2V0…` (the content hash, which leaves out the signature file). A re-sign by nuget.org changes the first and not the second. D-05's intent (exact version and SHA-512, check after restore, stop and name the package) is met best by reading `obj/project.assets.json` `libraries[*].sha512`. **Flag this to the user as a refinement of D-05's wording** (Assumption A2).
2. **A pure version floor refuses patched distro Pythons.** Ubuntu 24.04's fixed python3.12 still reports 3.12.3 (USN-7583-1). The CVE fix added `os.path.ALLOW_MISSING`: present in every patched Python probed (3.11.15, 3.13.5, 3.13.9, 3.14.5, 3.15.2) and absent from the pre-fix 3.12.9 here. Accept `version ≥ floor OR 'ALLOW_MISSING' in vars(os.path)` (Assumption A1).
3. **HARD-05's real holes are not the key writes.** Every keyed stage (upstream and porter) deletes its key before touching outputs and writes it after the swap, so a cut-off key write fails safe. The live holes are `experimental_profile`'s in-place `copytree` (reused when only `game.tsv` landed), the FPSLocker cache written in place, `mkapk.py`'s APK written in place, and `swap_in`'s rmtree-then-rename window. D-08's temp + `os.replace` key write is still worth doing (it is locked), but the plan must also fix these.
4. **`porter inspect` cannot read supported languages without an extraction.** The flags live in `control.nacp` inside an encrypted NCA. D-12 can only use an extraction that already exists (`<tid>_build/extract/<pack>/control.nacp`), else the full `nacp.LANGUAGES` list (Assumption A3).
5. **The vendored Ryujinx is not 1.3.2.** It uses C# 14 `extension` blocks. `Ryujinx.Common` and `Spv.Generator` match Ryubing tag `Canary-1.3.351` (`475615f`, master head) exactly. `Ryujinx.Graphics.Shader` differs by 274 lines over 15 files, more than the four changes its README lists. The patch file must be made against `475615f`, and the README's version label corrected.

**Primary recommendation:** Put new logic in new fork-owned modules (`porter/pins.py`, `porter/lock.py`, plus small helpers in `porter/fetch.py`, `porter/datapack.py`, `porter/runlog.py`, `porter/toolchain.py`), touch upstream's busy files only at hook lines, and limit subtree edits to `build_ipa_from_nsp.py` (key-write helper, `swap_in` aside-rename, `env` passed to the three `nx_extract` runs, absolute `dotnet`) and `nxnative/dm/android/apk/mkapk.py` (key and APK writes).

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Safe unzip/untar, Python floor | Porter CLI (`porter/fetch.py`, `porter/toolchain.py`, `porter/runlog.py`) | GUI shows the doctor row | Every rule lives in porter; the GUI only reads `doctor --json` |
| Download pins, fallback, hash check | Porter (`porter/pins.py`, `porter/fetch.py`) | GUI confirm dialog shows an additive `untested` field | Additive protocol field only |
| NuGet pin check | Porter (`porter/pipeline.py` hook → new helper) | Engine projects (restore output in `obj/`) | No file added to the subtree (D-05) |
| FPSLocker pin + hash record | Porter (`porter/fpslocker.py`) | — | Fork-owned module |
| Build-folder lock | Porter (`porter/lock.py`; hooks in `pipeline.inputs`, `cli.cmd_install`) | GUI shows the error on the game card (already does for any porter error) | OS lock, no GUI logic |
| Stage stamps | Engine subtree (`build_ipa_from_nsp.py`) | Porter's own two keyed stages | D-08: fix where it lives |
| Data-pack swap + recovery, chunked MD5 | Porter (`porter/datapack.py`, `porter/adb.py`) | — | Fork-owned |
| Signing key | Fork Android layer (`nxnative/dm/android/apk/mkapk.py`) | Porter preflight (early, clear error) | mkapk runs standalone too (probes) |
| Env dicts, upstream overrides | Porter (`pipeline.py` hook lines, `upstream.py`) | Engine subtree (absolute `dotnet`, `env=` on `nx_extract` runs) | Windows ignores the child env's PATH |
| Escaping, font, language list | GUI (`gui/app.py`) | Porter `inspect` JSON (additive `languages`) | GUI renders; porter decides the list |
| Repo housekeeping | Repo/docs/devtools | — | — |

## Project Constraints (from CLAUDE.md)

- The GUI holds no pipeline logic; every rule lives in `porter/` and reaches the GUI through `--json` / `--progress json`. A new CLI flag goes into `porter/cli.py` first. Enforced by `docs/ARCHITECTURE.md` and `tests/arch_rules.py`.
- Keep diffs to shared files small and mergeable (upstream shirai91/nx2android sync). Edits to `porter/cli.py`, `porter/pipeline.py`, `gui/app.py` stay at hook lines.
- Changes to `nxnative/dm/{host,gfx,tools,third_party}` stay small and platform-guarded (merged with `git subtree pull`). `nxnative/scripts/` edits are also subtree edits: keep them small and platform-neutral (D-08).
- No game-specific code in the Android runtime; no game IDs/names in core code (`tests/arch_rules.py`).
- No PySide6 imports inside `porter/` (`tests/arch_rules.py`).
- Toolchains are not bundled; downloaded by Setup or supplied by the player.
- Python 3.11+ for dev runs (CLI), 3.12+ for the GUI (STATE.md, Phase 1); bundles ship 3.14. Safe tar extraction needs `filter='data'` and the CVE-2025-4517 fix.
- Never ship keys, game files or FPSLocker configs. Logs name the keys file's path, never its contents.
- Style: dense one-line Python, 4-space indent, module header comment stating job and contract, comments cite the evidence, `[RED] ` prefix on problem log lines, English only, LF line endings.
- Errors the user sees are `BuildError` with a message that names the file and the fix; wrap lower errors with `raise … from e`; narrowest `except`.
- Every `urlopen` passes `context=tls.context()` (enforced by `tests/test_tls.py::test_every_urlopen_passes_the_context`, which also asserts at least 4 calls).
- Commit messages: Conventional Commits, ≤100 chars per line; docs updated in the same commit (`docs/ARCHITECTURE.md` when a stage, key or layer changes).
- Tests before committing: `python -m unittest discover tests` (includes `tests/arch_rules.py`).
- GSD workflow: file changes go through a GSD command.

## Standard Stack

### Core (all standard library; nothing to install)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `tarfile` with `filter='data'` | stdlib, 3.11.4+ (fixed in 3.11.13 / 3.12.11 / 3.13.4) | .NET tarball extraction | Refuses absolute paths, `..`, links leaving the destination; the 10.0.403 osx-arm64 tarball (5,630 members, 0 links) extracts and `dotnet --list-sdks` runs [VERIFIED: probe this session] |
| `zipfile` + own name/link checks | stdlib | NDK, platform-tools zips | `zipfile` drops Unix modes and symlinks, so porter keeps its own link handling; regular files go through `ZipFile.extract`, which already sanitizes names [CITED: docs.python.org/3/library/zipfile.html] |
| `hashlib.file_digest` | stdlib 3.11+ | Chunked MD5 for install | Verified on 3.11.15 this session |
| `fcntl.flock` / `msvcrt.locking` | stdlib | Build-folder lock | OS releases it on process death [CITED: docs.python.org/3/library/msvcrt.html] |
| `tempfile.mkstemp` + `os.fsync` / `fcntl.F_FULLFSYNC` + `os.link` / `os.replace` | stdlib | Atomic, 0600 key write | `mkstemp` makes the file 0600 (verified `0o600` on 3.11.15) |
| `html.escape` | stdlib | GUI rich-text escaping | Already imported in `gui/app.py:6` |
| `QFontDatabase.systemFont(QFontDatabase.FixedFont)` | PySide6 6.12 (already pinned) | Log pane font | Platform's own monospace font |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Vendor hash (SHA-1 from Google's index, SHA-512 from Microsoft's) in the manifest | Our own SHA-256 of each archive | SHA-256 needs ~2.3 GB of NDK downloads per bump. A pinned SHA-1 of an existing file still needs a second-preimage attack to defeat, which is not practical [ASSUMED]. `_download` already takes `algo`. Phase 3's community NDK (no vendor hash) uses `sha256` in the same field. |
| `porter/pins.py` (dict literal) | `porter/pins.json` | JSON needs a `datas` entry in `packaging/nx2android.spec` (which collects `porter` as code only: `hidden = collect_submodules('porter')`, spec line 11). A `.py` data module is bundled with no packaging change and CI reads it with `python -c "from porter import pins"`. |
| `project.assets.json` `sha512` (contentHash) | `.nupkg.sha512` files (D-05 wording) | `.nupkg.sha512` changes when nuget.org re-signs a package; contentHash does not. One JSON read vs a folder walk. |
| `packages.lock.json` + `--locked-mode` | — | Rejected by the developer (D-05). |

**Installation:** none.

## Package Legitimacy Audit

No external package is installed by this phase. All new code uses the Python standard library and the already-pinned PySide6 (`requirements.in`: `PySide6-Essentials==6.12.*`). The NuGet packages the manifest pins are not new: the engine already restores them today; this phase only pins and checks them.

| Package | Registry | Age | Downloads | Source Repo | Verdict | Disposition |
|---------|----------|-----|-----------|-------------|---------|-------------|
| (none) | — | — | — | — | — | — |

**Packages removed due to [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

## Architecture Patterns

### System Architecture Diagram

```
porter tools --download / Setup tab
   │
   ▼
fetch.plan(names) ──► pins.py entry for this OS? ──no──► vendor index (today) + untested=True ──┐
   │ yes                                                                                       │
   ▼                                                                                           │
HEAD pinned URL ──404/410──► fallback (NDK: stop; .NET: newest 10.x; adb: newest) ──────────────┤
   │ 200                                                                                       │
   ▼                                                                                           ▼
_download (hash as it streams) ──mismatch──► BuildError(file, expected, got)      Item(untested) → log [RED] + GUI dialog
   │ ok
   ▼
_install → .unpack tmp ──► _unzip (names checked first, files, links last + resolved check) / _untar(filter='data')
   │            └─ any refusal → rmtree(tmp), BuildError
   ▼
rename into player_tools()

porter port <folder>
   │
   ▼
runlog.run ──► Python floor ok? ──no──► refuse (doctor still runs)
   │
   ▼
Port.run: env dict (PATH+DOTNET_ROOT+NUGET_PACKAGES), signing-key preflight
   │
   ▼
inputs: work=<tid>_build ──► lock.take(work,'port') ──held──► BuildError "already running: porter install, PID…, started…"
   │                       runlog.build_folder: marker found → "[RED] … cut off in <stage>" (no key sweep)
   ▼
stages (each: key gone → outputs into .partial → swap_in → write_key) ── nx_extract/dmsh_xlate: dotnet restore → NuGet pin check → build
   │
   ▼
data: build .partial → dst→dst.old → .partial→dst → rmtree(dst.old)
   │
   ▼
install (same process, lock already held) ── chunked MD5 ── push

porter install <pack> ──► datapack.recover(pack) ──► lock.take(manifest['build'],'install') ──► install.install
```

### Recommended Project Structure (new and touched files)

```
porter/
├── pins.py        # NEW: the manifest (toolchain URLs+hashes per OS, FPSLocker commit, NuGet contentHashes), data only
├── lock.py        # NEW: take(work, cmd) → open file object; "already running" BuildError
├── fetch.py       # pins + fallback, safe _unzip/_untar, partial unpack removed
├── fpslocker.py   # pinned commit, head fallback, sha256 recorded
├── datapack.py    # aside swap + recover(); manifest gains "build"
├── adb.py         # hashlib.file_digest
├── toolchain.py   # Python floor (python_ok), NuGet check helper (or a new porter/nuget.py)
├── runlog.py      # marker keeps the message with the stage; key sweep removed; Python refusal
├── upstream.py    # _load_nsp → named overrides with asserts
├── pipeline.py    # hook lines only: env dict, lock, preflight, check_space re-check, game.load by path
└── cli.py         # hook lines only: install lock, tools --only error
nxnative/scripts/build_ipa_from_nsp.py   # write_key helper, swap_in aside, env= on nx_extract runs, absolute dotnet
nxnative/dm/android/apk/mkapk.py         # key: mkstemp+fsync+link; refuse unreadable; APK via temp+replace
probes/app/mkapk.py                      # DELETED; probeapp.c header gets the build lines
devtools/hooks.py (or hooks.sh)          # NEW: git config core.hooksPath .githooks
nxnative/dm/third_party/README.md        # FLIP commit
nxnative/dm/third_party/ryujinx/         # local-changes patch + corrected base in README
gui/app.py                               # escaping, system mono font, languages from inspect
tests/test_fetch.py, test_lock.py, test_stages.py, test_signing.py, test_adb.py, test_toolchain.py, test_cli.py   # NEW
```

### Pattern 1: Python floor that accepts distro backports

**What:** `doctor` shows a red Python row; every other command refuses.
**When to use:** `toolchain.checks()` row and a guard at the top of `runlog.run` (fork-owned, so `cli.py` stays untouched).

```python
# porter/toolchain.py
FLOORS = {11: 13, 12: 11, 13: 4}   # CVE-2025-4517 and friends: tarfile's 'data' filter could be bypassed before these (gh-135034)

def python_ok(v=sys.version_info):
    """3.11+ with the tarfile fix. A distro's patched build keeps its old micro version (Ubuntu 24.04: 3.12.3-1ubuntu0.7), but the fix added os.path.ALLOW_MISSING"""
    return v >= (3, 11) and (v[:2] >= (3, 14) or v[2] >= FLOORS[v[1]] or 'ALLOW_MISSING' in vars(os.path))
```

Today's row is `out.append(Check('Python', v >= (3, 11), f'{v.major}.{v.minor}.{v.micro} ({sys.executable})', fix='Python 3.11 or later'))` [VERIFIED: porter/toolchain.py:97]. Change the test to `python_ok()` and the fix text to name the three floors. Evidence for the marker: pre-fix 3.12.9 → `False`; 3.11.15, 3.13.5, 3.13.9, 3.14.5, 3.15.2 → `True` [VERIFIED: local probe]; the fix PR adds `os.path.realpath(strict=ALLOW_MISSING)` [CITED: github.com/python/cpython/pull/135037]. 3.14.0b3+ carries the fix [CITED: osv.dev/vulnerability/CVE-2025-4517].

### Pattern 2: Safe unzip (refuse whole archive, links last)

Probed this session: today's `_unzip` creates `../escaped-link → /etc/hosts` outside the unpack folder [VERIFIED: probe]. The vulnerable line is `t = into / info.filename; t.parent.mkdir(parents=True, exist_ok=True); t.unlink(missing_ok=True); os.symlink(z.read(info).decode(), t)` [VERIFIED: porter/fetch.py:111].

Real archives under the strict rules [VERIFIED: range-request probe of Google's zips; local probe of the platform-tools zip]:

| Archive | Members | Symlinks | Bad names | Absolute links | Links leaving tree | Members under a link |
|---------|---------|----------|-----------|----------------|--------------------|----------------------|
| android-ndk-r27c-darwin.zip | 9,177 | 23 | 0 | 0 | 0 | 0 |
| android-ndk-r27c-linux.zip | 9,277 | 35 (e.g. `shader-tools/linux-x86_64/libc++.so → ../../toolchains/llvm/prebuilt/linux-x86_64/lib/libc++.so`) | 0 | 0 | 0 | 0 |
| platform-tools_r37.0.1-darwin.zip | 14 | 0 | 0 | 0 | 0 | 0 |

So refusing backslashes, `..` parts, absolute names and links that resolve outside rejects nothing legitimate.

```python
def _bad_name(n):   # absolute, a drive, a backslash or a .. part: refused before anything is written
    return n.startswith('/') or '\\' in n or ':' in n.split('/', 1)[0] or '..' in n.split('/')

def _unzip(arc, into):
    with zipfile.ZipFile(arc) as z:
        infos = z.infolist()
        if bad := [i.filename for i in infos if _bad_name(i.filename)]: raise BuildError(f'{arc.name}: refused, member {bad[0]!r} would land outside the unpack folder')
        links = [i for i in infos if os.name != 'nt' and stat.S_ISLNK(i.external_attr >> 16)]
        # files first, links last: no file is ever written through a link
        ...extract the others as today...
        root = into.resolve()
        for i in links:
            t, target = into / i.filename, z.read(i).decode()
            if target.startswith('/') or not (t.parent.resolve() / target).resolve().is_relative_to(root) or not t.parent.resolve().is_relative_to(root):
                raise BuildError(f'{arc.name}: refused, link {i.filename} → {target} leaves the unpack folder')
            t.parent.mkdir(parents=True, exist_ok=True); t.unlink(missing_ok=True); os.symlink(target, t)
```

Resolve both sides: `/tmp` and `/var` are symlinks to `/private/...` on macOS [CITED: PITFALLS.md §10]. `_install` must `rmtree(tmp)` on any exception (today it leaves it until the next install).

### Pattern 3: One manifest, pinned URL first, vendor fallback second

Values read from the vendor indexes this session [VERIFIED: dl.google.com/android/repository/repository2-3.xml; builds.dotnet.microsoft.com/dotnet/release-metadata/10.0/releases.json]:

| Tool | Pin | Host | URL file | Size | Hash |
|------|-----|------|----------|------|------|
| NDK | r27c (`27.2.12479018`) | windows | `android-ndk-r27c-windows.zip` | 781511249 | sha1 `ac5f7762764b1f15341094e148ad4f847d050c38` |
| NDK | r27c | macosx | `android-ndk-r27c-darwin.zip` | 836128272 | sha1 `0217c10ffbec496bb9fbfbb3c6fc2477c6b77297` |
| NDK | r27c | linux | `android-ndk-r27c-linux.zip` | 663987688 | sha1 `090e8083a715fdb1a3e402d0763c388abb03fb4e` |
| platform-tools | 37.0.1 (index's newest today) | windows | `platform-tools_r37.0.1-win.zip` | 8044989 | sha1 `e03e78b1d80b396f1c3358e31251cb31740e1110` |
| platform-tools | 37.0.1 | macosx | `platform-tools_r37.0.1-darwin.zip` | 16110554 | sha1 `6ae73f4de6452dc57e62ec02b68eed92a4c21661` |
| platform-tools | 37.0.1 | linux | `platform-tools_r37.0.1-linux.zip` | 9054187 | sha1 `477254aa5f903c15cf51001717bdf347fb6b53e0` |
| .NET SDK | 10.0.403 (the SDK on this Mac, and `latest-sdk`) | win-x64, osx-arm64, linux-x64, linux-arm64 | `https://builds.dotnet.microsoft.com/dotnet/Sdk/10.0.403/dotnet-sdk-10.0.403-<rid>.{zip,tar.gz}` | HEAD | sha512 from `releases.json` (copy the full value with a script; prefixes: win-x64 `7a114c31…`, osx-arm64 `5893c66b…`, linux-x64 `b7b3d846…`, linux-arm64 `0966aa2b…`) |

Google URLs are `GOOGLE + file`, where `GOOGLE = 'https://dl.google.com/android/repository/'` [VERIFIED: porter/fetch.py:13].

**The open research item (STATE.md "whether older platform-tools URLs stay downloadable") is answered:** HEAD on versioned URLs returned 200 for every darwin/linux release tried back to r29.0.6 (2020), and for Windows back to r35.0.2. Older Windows builds returned 404 under the `-win.zip` name (they used another file name) [VERIFIED: curl probe]. An old .NET SDK (10.0.100 osx-arm64) also returned 200 [VERIFIED: curl probe]. So a pin stays downloadable for years, and D-02's fallback is the rare path. It must still exist and be tested.

Shape (data only; Phase 3 adds a `linux-arm64` NDK row with `sha256`):

```python
# porter/pins.py: what porter downloads, pinned (PKG-07). Bump: change one row, run `python -m porter tools --download --only <tool>` on each host and the suite, commit.
NDK = {'version': 'r27c', 'files': {'windows': ('android-ndk-r27c-windows.zip', 781511249, 'sha1', 'ac5f7762…'), 'macosx': (...), 'linux': (...)}}
PLATFORM_TOOLS = {'version': '37.0.1', 'files': {...}}
DOTNET = {'version': '10.0.403', 'files': {'win-x64': ('https://builds.dotnet.microsoft.com/dotnet/Sdk/10.0.403/dotnet-sdk-10.0.403-win-x64.zip', 'sha512', '…'), ...}}
FPSLOCKER = '575eef0824e3519e6567c3fdb27707136448923a'   # masagrator/FPSLocker-Warehouse v4 head on 2026-10-29
NUGET = {'LibHac/0.19.0': '7uMUGFpO2V0XJowS5/NjX6qlAlO94dQhLvxNdF3VhW36BXkoHCJPxTzL9r0U4p8w0jKm+9oAUF6XriWrAbIrsw==', ...}   # contentHash, 58 packages
```

Rules for `plan()`:
- A host with no pinned row (osx-x64 .NET, linux-arm64 NDK until Phase 3) takes today's index path, marked `untested`.
- HEAD the pinned URL (this replaces today's HEAD for size at `porter/fetch.py:89`). 200 → pinned Item. `HTTPError` 404/410 → fallback. Any other error → raise as today.
- Fallback bounds: NDK never falls back (stop: "NDK r27c is no longer served at <url>: install it yourself and set its folder"). .NET only takes 10.x (the index is the 10.0 channel already). platform-tools takes the newest.
- `Item` gains `untested: bool` (additive in `tools --json`). `download()` says `[RED] <name> <version> is not the pinned <pin>: untested` and the GUI dialog appends "(untested)".
- A mismatch message names the file and both hashes: `f'{it.url}: {it.algo} {got} is not the pinned {it.hash}'`.

### Pattern 4: FPSLocker at a pinned commit, head fallback

Probed: a config at the pinned commit returned 200; a missing build at the same commit returned 404; `GET https://api.github.com/repos/masagrator/FPSLocker-Warehouse/commits/v4` with `Accept: application/vnd.github.sha` returns the bare SHA (`575eef0824e3519e6567c3fdb27707136448923a`, committed 2026-10-29) [VERIFIED: curl probe].

```python
RAW = 'https://raw.githubusercontent.com/masagrator/FPSLocker-Warehouse/{ref}/SaltySD/plugins/FPSLocker/patches/{tid}/{bid}.yaml'

def fetch(title_id, build_id, timeout=30):
    """(text, commit) of this build's config: at the pinned commit, else at v4's head (a newer game build); None when neither has one. Other errors raise OSError"""
    for ref in (pins.FPSLOCKER, None):
        commit = ref or _head(timeout)   # api.github.com/.../commits/v4, Accept: application/vnd.github.sha
        try: ... urlopen(RAW.format(ref=commit, ...), context=tls.context()) → return text, commit
        except urllib.error.HTTPError as e:
            if e.code != 404: raise
    return None
```

Today's `RAW` is `'https://raw.githubusercontent.com/masagrator/FPSLocker-Warehouse/v4/SaltySD/plugins/FPSLocker/patches/{tid}/{bid}.yaml'` [VERIFIED: porter/fpslocker.py:15]. In `Port.fps_unlock`, compute `hashlib.sha256(text.encode()).hexdigest()`. Pass `src = f'{url} (commit {commit[:12]}, sha256 {h})'` into `convert`/`patches_py` (they already take `source`), so the build folder's `fpslock.tsv` and `patches.py` record both. Say the same in the port log; when `commit != pins.FPSLOCKER`, say it with `[RED] … not the pinned commit: untested`. Write the cache atomically (temp + `os.replace`): today `cache.write_text(text, …)` writes in place, and a truncated cache read offline converts a partial config. The GitHub API allows 60 unauthenticated requests per hour [ASSUMED]; a failure there is an `OSError` and takes the existing "use the cached copy" path.

### Pattern 5: Build-folder lock

```python
# porter/lock.py: one port or install of a game at a time (D-06, D-07). An OS lock on <tid>_build/.porter.lock, which the OS lets go when the holder dies.
# The file is never deleted (deleting races a porter that already opened it). It holds the holder's command, PID and start time for the "already running" message.
import errno, os, time
AT = 4096   # Windows locks are mandatory: the locked byte sits past the text, so a second porter can still read who holds it

def take(work, cmd):
    work.mkdir(parents=True, exist_ok=True); f = open(work / '.porter.lock', 'a+b')
    try:
        if os.name == 'nt': import msvcrt; f.seek(AT); msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
        else: import fcntl; fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as e:
        if e.errno in (errno.ENOLCK, errno.EOPNOTSUPP): return f   # a share without locks: run unlocked rather than refuse (say so with [RED])
        f.seek(0); who = f.read(AT).decode('utf-8', 'replace').strip() or 'another porter'; f.close()
        raise BuildError(f'already running: {who} is using {work}. Wait for it to finish, or stop it first')
    f.seek(0); f.truncate(); f.write(f'porter {cmd}, PID {os.getpid()}, started {time.strftime("%Y-%m-%d %H:%M:%S")}\n'.encode()); f.flush()
    return f   # keep a reference for the whole run: closing it, or losing the last reference, lets the lock go
```

- `msvcrt.locking`: "The locked region of the file extends from the current file position for nbytes bytes, and may continue beyond the end of the file"; `LK_NBLCK` raises `OSError` at once [CITED: docs.python.org/3/library/msvcrt.html]. Windows byte-range locks block reads by other processes [ASSUMED], hence the byte at `AT`.
- Python opens files non-inheritable (PEP 446), so children do not hold the lock [CITED: docs.python.org/3/library/os.html#fd-inheritance].
- **Port hook:** in `pipeline.inputs` right after `self.work = o.folder / f'{tid}_build'` (pipeline.py:122), before `experimental_profile` writes into it: `self.lock = lock.take(self.work, 'port')`.
- **Install hook:** in `cli.cmd_install`'s `go()`, never inside `install.install`. `Port.install` calls `install.install` in the same process that already holds the flock, and a second `open()` + `flock` in the same process conflicts (flock locks belong to the open file description) [CITED: man7.org flock(2)].
- **Finding the build folder from a pack:** `datapack.build` adds `build=str(work)` to the manifest (additive). `cmd_install` locks `man['build']` when present. Note: the manifest is pushed to the device, so the device sees the player's local path. If that matters, keep it in a sidecar beside the pack instead (Open Question 3).
- The iOS script does not lock (D-07). Document in `docs/ARCHITECTURE.md` that iOS and Android share `<tid>_build/` and that only porter locks it.

### Pattern 6: Stage stamps, per-stage audit (HARD-05) and the data-pack swap (HARD-07)

Audit of every reuse key the port reaches [VERIFIED: read of build_ipa_from_nsp.py and porter/pipeline.py this session]:

| Stage | Key file | Key removed before work? | Outputs | Cut-off safe today? |
|-------|----------|--------------------------|---------|---------------------|
| extract (upstream `extract`) | none; reuse = `ExeFS/main` and the RomFS marker exist | — | `.partial` → `swap_in` | Yes (dst is replaced only when incomplete) |
| DLC (`extract_aoc`, :762-773) | `aoc.key` | yes (`rmtree(kf)`) | `aoc.partial` → `swap_in` | Yes |
| NRO collect (:796-805) | `nro_*.key` | yes | `.partial` → `swap_in` | Yes |
| rewrite (:822-849) | `patched_<v>.key` | yes | `.partial` → `swap_in` | Yes |
| shader split (:1206-1229) | `pkg.key` | yes, just before the swap; outputs built in `.partial` | `swap_in` | Yes |
| porter shaders (pipeline.py:279-295) | `shaders.dmsv.key` | yes (:287) | `.partial` → `swap_in` | Yes |
| porter translator (pipeline.py:318-323) | `dmsh_xlate.key` | yes (:320) | `.partial` → `swap_in` | Yes, but shared across games (see Pitfall 6) |
| **experimental profile copy** (pipeline.py:180-181) | reuse = `game.tsv` exists and is newer | — | **`copytree` in place** | **No**: a cut-off copy with `game.tsv` already written is reused |
| **FPSLocker cache** (pipeline.py:250) | — | — | **written in place**, read when offline | **No** |
| **APK** (mkapk.py:204 `open(out, 'wb').write(apk)`) | none (always rebuilt) | — | **in place** | Rebuilt by `port`, but `porter install` can push a truncated APK |
| **data pack** (datapack.py:59-60) | none | — | `shutil.rmtree(dst)` then `tmp.rename(dst)` | **No**: a crash between the two lines leaves no pack (HARD-07) |
| iOS Mac host / font (:891-898, :1441-1446) | yes | yes | in place | Yes (key first); iOS only |

**Conclusion:** a cut-off key write already fails safe (a truncated key never matches). D-08's temp + `os.replace` helper is still locked: add one `write_key(kf, text)` to the upstream script, use it at its key-write sites (:773, :805, :849, :898, :1229, :1327, :1349, :1446) and porter's two (pipeline.py:295, :323). Then fix the four real holes: the profile copy goes to `.partial` and through `nsp.swap_in`; the FPSLocker cache is written atomically; mkapk writes `out + '.partial'` then `os.replace`; the data pack swaps aside.

`swap_in` today [VERIFIED: build_ipa_from_nsp.py:363-370]: `rmtree(dst)`, then a Windows-only 15 s retry loop on `PermissionError`, then `tmp.rename(dst)`. Changing it to an aside-rename (`dst → dst.old`, `tmp → dst`, `rmtree(dst.old)`) is the "D-08 swap" in one place, and the data pack can reuse it:

```python
# porter/datapack.py
def recover(dst):   # a crash mid-swap: the old pack is aside and no pack is in place, so the aside copy comes back
    old = dst.with_name(dst.name + '.old')
    if old.is_dir() and not dst.exists(): old.rename(dst)
# build(): ...tmp filled...; recover(dst); old = ...; nsp.rmtree(old); if dst.exists(): dst.rename(old); nsp.swap_in(tmp, dst); nsp.rmtree(old)
# cli.cmd_install: datapack.recover(data) before read_manifest
```

`datapack` imports only the standard library today. Importing `porter.upstream` for `nsp.swap_in` pulls in lz4, which every caller already loads. If the planner keeps datapack stdlib-only, copy the Windows retry (antivirus holding a just-written file, the "Tales of Eternia" comment at :365-366).

**D-09 marker:** keep `.port-running`. Have `runlog._wrap.stage` rewrite it with the stage name (`S['work']` known). On a marker found, say `[RED] the last port of this game was cut off in <stage>: the stages it had not finished run again`, and delete the key sweep (`runlog.py:52-55`). `tests/test_runlog.py::Marker::test_cut_off_redoes_stages` must flip to "keys kept, message names the stage".

### Pattern 7: Signing key (mkapk.py, stdlib only, runs standalone)

Today [VERIFIED: nxnative/dm/android/apk/mkapk.py:193-198]:
```python
keyf = ARGS.key if ARGS.key else os.path.join(os.path.dirname(os.path.abspath(out)), 'probe-signing-key.json')
if os.path.exists(keyf): k = {a: int(v) for a, v in json.load(open(keyf)).items() if a != 'cert'}; crt = bytes.fromhex(json.load(open(keyf))['cert'])
else:
    t = time.time(); k = gen_key(); crt = cert(k)
    json.dump({**{a: str(v) for a, v in k.items()}, 'cert': crt.hex()}, open(keyf, 'w'))
```

Recommended:
```python
def save_key(keyf, text):   # whole and 0600, or not at all (mode bits mean nothing on Windows: %APPDATA%'s ACL protects it there)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(os.path.abspath(keyf)), prefix='.signing-key-')
    try:
        with os.fdopen(fd, 'w') as f:
            f.write(text); f.flush(); fcntl.fcntl(f, fcntl.F_FULLFSYNC) if sys.platform == 'darwin' else os.fsync(f.fileno())
        try: os.link(tmp, keyf)   # never over a key another first port wrote a moment ago: two keys would fork the signer
        except FileExistsError: return False
        finally: os.unlink(tmp)
        return True
    except BaseException:
        if os.path.exists(tmp): os.unlink(tmp)
        raise
```
- On `FileExistsError`, load the key that won. `os.link` gives no-clobber publish on POSIX and NTFS. `os.replace` would let two simultaneous first ports overwrite each other's key [ASSUMED: race reasoning].
- An unreadable or unparsable existing key: `sys.exit(f'[RED] {keyf}: the signing key cannot be read ({e}). Restore it from a backup; or remove it on purpose and reinstall every port with --replace-signer (their saves go with them)')`.
- Tighten an existing key: `if os.name != 'nt' and os.stat(keyf).st_mode & 0o077: os.chmod(keyf, 0o600)` (recommended; cheap).
- **Porter preflight** (hook line in `Port.run` after `toolchain.require`): if `paths.signing_key()` exists, parse it and raise the same message as a `BuildError` before a 20-minute port starts. Otherwise the failure only shows at the APK stage as `mkapk.py exit code 1 (full output: …)`, with the reason in the log tail.
- The APK write becomes `open(out + '.partial', 'wb')` then `os.replace`.
- `probes/app/probeapp.c` header gets the build lines, for example: `python nxnative/dm/android/apk/mkapk.py build/libprobe.so build/apk/nx2a-probe.apk build/probe-signing-key.json --lib probe --package org.nx2a.probe --label "NX2A Probe"`. mkapk's defaults are already `--package org.nx2a.probe`, `--label 'NX2A Probe'`, `--lib probe` [VERIFIED: mkapk.py:8-9]. Also update the three mentions of `probes/app/mkapk.py`: `RESEARCH.md:116` (repo root), `.claude/skills/switch-android-port/references/neo-case-study.md:23`, `.claude/CLAUDE.md:351`.

### Pattern 8: Env dicts and the upstream sites that need them (HARD-06)

`os.environ` writes in porter [VERIFIED: grep + read]: `pipeline.py:92-93` (PATH, DOTNET_ROOT), `pipeline.py:164-165` (DM_GAMES_DIR, DM_GAMES_FIRST), `procs.py:14` (MSBuild switches, set once at command start, Phase 1, out of the pipeline), and `cli.py:94-95` (the restore in `_with_progress`).

Why they exist, and what replaces each:

| Mutation | Who needs it | Replacement |
|----------|--------------|-------------|
| PATH += dotnet dir | upstream `build_nx_extract` runs `run(['dotnet', 'build', …], …, env=env)` (:357). On Windows `env` cannot override PATH lookup [CITED: docs.python.org/3/library/subprocess.html, Popen warning] | Subtree edit: `run([shutil.which('dotnet', path=(env or os.environ).get('PATH')) or 'dotnet', 'build', …])`. Upstream already uses `shutil.which('dotnet', path=env['PATH'])` at :1548. Keep `PATH` prepended in `self.env` only. |
| DOTNET_ROOT | the `nx_extract` apphost, run with **no env** at :475 (`survey`), :745 (`extract`), :771 (`extract_aoc`) | Subtree edit: pass `env=env` at :475 (survey already receives `env`); add `env=None` to `extract(...)` and `extract_aoc(...)` and pass it to `run`. Upstream's `main()` keeps working (defaults). Porter passes `self.env`. |
| DM_GAMES_DIR / FIRST | in-process `game.load(tid)` at pipeline.py:186 and `game.load(g.id)` at :211, which read `os.environ` (`game.py:49-54`) | Load by path: `game.find_dir` takes a path "as is" when it contains `os.sep` (`game.py:57-58`), so `game.load(str(d))` and `game.load(str(pdir / g.id))`. Keep writing both keys into `self.env` for the child tools. |

Then delete `_with_progress`'s restore (`cli.py:81, 94-95`) or leave it as a harmless guard (planner's call). `tests/test_porter.py::Experimental` asserts `os.environ.get('DM_GAMES_FIRST') == '1'`; it must flip to asserting `port.env` and an unchanged `os.environ`.

**NuGet folder:** add `NUGET_PACKAGES=str(paths.user_dir() / 'nuget')` to `self.env`. Every `dotnet` call (restore, build, `--version`) must see the same value, or the build re-restores into the other folder. A restore into a scratch folder showed `project.assets.json` `packageFolders` = that folder [VERIFIED: probe]. The 58 packages take about 50 MB.

**Upstream overrides** [VERIFIED: porter/upstream.py:19-26]: `m.nacp, m.pg = nacp, profile_guess`; `can_clone` on non-darwin; `profile_files` filtered. `nacp` and `pg` do not exist on the module before `main()` runs, so `hasattr` cannot assert them. Assert `{'nacp', 'pg'} <= set(m.main.__code__.co_names)` (True today [VERIFIED: probe]) and `callable(getattr(m, n))` for `can_clone`, `profile_files` before replacing them.

### Pattern 9: NuGet pin check

```python
def nuget_check(project, dotnet, env, log):
    """dotnet restore, then every package in obj/project.assets.json must be pinned with the same contentHash (pins.NUGET); anything else stops the port"""
    nsp.run([dotnet, 'restore', project, '-v', 'quiet', '--nologo'], log, env=env)
    libs = json.loads((Path(project) / 'obj/project.assets.json').read_text(encoding='utf-8'))['libraries']
    bad = [f'{k} ({v.get("sha512")})' for k, v in libs.items() if v.get('type') == 'package' and pins.NUGET.get(k) != v.get('sha512')]
    if bad:
        for k in bad: nsp.rmtree(Path(env['NUGET_PACKAGES']) / k.split(' ')[0].lower())   # the bad package is fetched again next time
        raise BuildError(f'NuGet package not the pinned one: {"; ".join(bad)} (porter/pins.py NUGET)')
```

- Restore resolved **1** package for `nx_extract` (`LibHac/0.19.0`) and **57** for `dmsh_xlate` (Gommon 2.8.1.2, Humanizer 3.0.10 plus 51 `Humanizer.Core.*` packages, Microsoft.IO.RecyclableMemoryStream 3.0.1, MsgPack.Cli 1.0.1, System.CodeDom 4.4.0) [VERIFIED: restore probe]. Generate `pins.NUGET` from a restore with a small devtools script, never by hand.
- `project.assets.json` `sha512` = `.nupkg.metadata` `contentHash` ≠ `.nupkg.sha512` [VERIFIED: probe on LibHac, Gommon, Humanizer.Core]. contentHash leaves out the signature file [CITED: github.com/NuGet/Home/wiki/Nupkg-Metadata-File].
- Order: restore → check → build. Restore does not run package build targets [ASSUMED], so the check gates code before any package code runs. For `nx_extract`, run restore + check before `nsp.build_nx_extract` (extract stage) and before `nsp.survey` (experimental). For the translator, run it inside `Port.translator()` before its `dotnet build` (skipped when its key matches).
- The global-folder subfolder name is the lowercased package id (`pkgs/libhac/0.19.0/`) [VERIFIED: probe].

### Pattern 10: GUI escaping (HARD-08), font, languages

Unescaped rich-text interpolations in `gui/app.py` [VERIFIED: read]: `:121` folder path; `:131` `info["name"]`, `info["title_id"]`; `:134` `info["pack"]`; `:135` `a["tested"]`; `:136` `info["reason"]`; `:301` the download list (`it["name"]`, `it["version"]`, `it["url"]`, `it["license"]` as an `href`; these come from the network). Use one `esc = lambda s: html.escape(str(s), quote=True)` at each interpolation. `quote=True` matters for the `href`.
- Font (`:102`): `self.log.setFont(QFontDatabase.systemFont(QFontDatabase.FixedFont))`, then set the point size to 9 if wanted.
- D-12: replace `LANGUAGES` (`:18-19`) and its use (`:71`). `inspect` returns `languages: [{'code','name'}]` (additive). Build it from `nacp.languages(work/'extract'/pack/'control.nacp')` when that file exists, else all of `nacp.LANGUAGES`. Names come from `dict(nacp.LANGUAGES)`. The combo keeps a first `('', 'English (default)')` item so the default stays "no `--language` flag". `nacp.LANGUAGES` has 16 entries (`('en-US', 'American English')` … `('pt-BR', 'Brazilian Portuguese')`) [VERIFIED: nxnative/dm/tools/nacp.py:10-11].

### Pattern 11: Disk space (HARD-09)

`scan_nsps` globs only the top level: `for p in sorted([*nsp_dir.glob('*.nsp'), *nsp_dir.glob('*.xci')])` [VERIFIED: build_ipa_from_nsp.py scan_nsps]. DLC NSPs therefore sit in the same folder and are in `self.fam['dlc']`. Count exactly what the port reads: `game = sum(p.stat().st_size for p in [fam['base'], *(p for _, p in fam['updates']), *(p for _, _, p in fam['dlc'])])`. This is accurate and covers DLC. The `built` side already uses `rglob` (pipeline.py:158). Re-check after extraction with one hook line after `self.extract()`: the formula subtracts what the build folder now holds. When `o.out` is on another volume than the build folder (`os.stat(...).st_dev` differs), the pack's hard links fall back to copies (`datapack.link_or_copy`), so check the extracted RomFS + `aoc` size against `o.out`'s free space before `data()`. The literal "recursive including DLC folders" wording versus "what the port reads" is Open Question 2.

### Pattern 12: Housekeeping facts

- **FLIP:** the vendored `FLIP.h` (blob `8f7fefe…`) and `tool/FLIPToolHelpers.h` (blob `6c7a9cd…`) match NVlabs/flip commit `b475eb4bf394ab877c42166c9eb0a84a02cc5b14` (2025-11-07); the tool prints "FLIP v1.7" (`MajorVersion = 1; MinorVersion = 7`, `tool/FLIPToolHelpers.h:482-483`) [VERIFIED: gh api blob match]. Record "v1.7, upstream commit `b475eb4`" in `nxnative/dm/third_party/README.md` (one table cell; a doc-only subtree edit).
- **Ryujinx:** tag `1.3.2` (`9d83dfd`) is at `https://git.ryujinx.app/ryubing/ryujinx.git` (git protocol; the web/API URLs 404) [VERIFIED: git ls-remote]. The vendored tree is **not** 1.3.2 (2,068 changed lines vs 1.3.2; C# 14 `extension(InputTopology topology)` in `InputTopology.cs`). Changed lines against canary tags: 1.3.3 → 2068, Canary-1.3.250 → 874, -1.3.300 → 673, -1.3.330 → 312, -1.3.351 → 274. `Canary-1.3.351` = master head `475615f0431b4995b03c930c5089d20f6f3570e0` (2026-08-26). Against it, `Ryujinx.Common` and `Spv.Generator` are identical, and `Ryujinx.Graphics.Shader` differs in 15 files. Eight of those carry `nxnative:` markers, including `InstEmitFlowControl.cs`, `AttributeUsage.cs`, `TranslatorContext.cs`, which the README does not list [VERIFIED: sparse clone + diff]. Make the patch with `git diff --no-index` against a sparse checkout of `475615f` (three project folders), review the unmarked hunks (EmitterContext, ResourceReservations, ShaderDefinitions, GeometryToCompute, EmitterContextInsts, ResourceManager, StructuredProgram), and correct the README's "Ryujinx 1.3.2" label.
- **Hook bootstrap:** README already documents `git config core.hooksPath .githooks` at `README.md:102`. D-11 adds a devtools script and points the contributor section at it.
- **`.gitignore`:** add `*.code-workspace` (the untracked `nx2android.code-workspace` is in `git status`).

### Anti-Patterns to Avoid
- **Taking the lock in `install.install`:** the port's own install step would deadlock against its own flock.
- **Deleting the lock file on exit:** races a second porter that opened the old file; leave it.
- **Holding the lock only in a local variable:** garbage collection closes the file and frees the lock mid-run. Store it on `self`.
- **Comparing `.nupkg.sha512`:** changes when nuget.org re-signs.
- **Pure `sys.version_info` floor:** refuses Ubuntu's patched 3.12.3.
- **Checking a zip link target lexically only:** `d → .` plus `d/x → ../y` escapes physically. Resolve on disk, links last.
- **Removing `os.environ['DOTNET_ROOT']` without passing `env` to the `nx_extract` runs:** nx_extract then finds the system runtime, which may lack .NET 10.
- **Calling `game.load(tid)` after dropping the `DM_GAMES_DIR` mutation:** it silently loads the repo profile instead of the derived or experimental one.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Tar member path checks | A member loop with `..` checks | `extractall(into, filter='data')` | Covers hard links, absolute links, device files, mode bits; the bypasses were fixed in CPython itself |
| Chunked file hashing | A read loop | `hashlib.file_digest(f, 'md5')` | 3.11+, one line |
| Concurrency guard | PID file + "is PID alive" | `fcntl.flock` / `msvcrt.locking` | PID reuse and stale files; the OS frees a lock when the process dies |
| NuGet resolution listing | Walking `~/.nuget/packages` | `obj/project.assets.json` `libraries` | Exactly what the build will use, with contentHash |
| HTML escaping | `.replace('<', '&lt;')` chains | `html.escape(s, quote=True)` | Attribute contexts (`href`) need quotes escaped |
| Monospace font choice | `os.name` switch | `QFontDatabase.systemFont(FixedFont)` | Linux has neither Consolas nor Menlo |
| Hash pins for Google archives | Downloading 2.3 GB to compute SHA-256 | The index's SHA-1, pinned in the repo | Second-preimage protection without the download |

**Key insight:** every hardening item here has a standard-library primitive. The risk is in where it is called (lock lifetime, link order, which hash), not in the primitive.

## Runtime State Inventory

This phase changes semantics of state that already exists on testers' machines.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | Existing `<tid>_build/*.key` reuse keys (same format; stay valid). Existing `<tid>_build/.port-running` markers from Phase 1 builds (new semantics: message only). Existing data packs without the `build` manifest key | None for keys and markers (code edit only). `cmd_install` must treat a missing `build` key as "no lock" |
| Live service config | None. The project has no hosted service (verified: CLAUDE.md "No server-side deployment") | None |
| OS-registered state | None. No scheduled tasks, services or launch agents are registered by the tool | None |
| Secrets/env vars | `<user dir>/signing-key.json` written with the umask (likely 0644) by earlier versions | Code: tighten to 0600 on first read (POSIX). No migration task needed |
| Build artifacts / installed packages | Toolchains already downloaded unpinned into `<user dir>/toolchains/` (kept, D-04). NuGet packages from earlier ports in the player's global `~/.nuget/packages`; with `NUGET_PACKAGES` moved under the user dir, the first port after the update re-downloads ~50 MB and needs network. Engine copies in `<user dir>/engine/<id>/` get the subtree edits only with a new bundle ENGINE id (by design, Phase 1) | Say in the release notes that the first port after the update downloads the NuGet packages again |

## Common Pitfalls

### Pitfall 1: The lock freed by garbage collection or a second open
**What goes wrong:** `lock.take()`'s file object goes out of scope, or the same process opens the lock file again; the lock is gone or the port blocks itself.
**How to avoid:** store it on `Port` (`self.lock`); take it only in `pipeline.inputs` and `cli.cmd_install`.
**Warning signs:** the "already running" test passes only when the holder is a separate process.

### Pitfall 2: Windows mandatory byte locks hide the holder's details
**What goes wrong:** the second porter cannot read the PID text inside the locked range and shows an empty message.
**How to avoid:** lock one byte at offset 4096; write the text at offset 0. Run the test on Windows CI.

### Pitfall 3: Version floor refuses patched distro Pythons
**What goes wrong:** Ubuntu 24.04's `python3` (3.12.3-1ubuntu0.7, fixed) is refused.
**How to avoid:** Pattern 1 (`ALLOW_MISSING` marker). The refusal message names the floors and says the bundle needs no Python.

### Pitfall 4: `os.environ` removal breaks Windows only
**What goes wrong:** `FileNotFoundError: dotnet` or nx_extract "You must install .NET" on Windows; macOS dev runs pass.
**How to avoid:** the three `env=` subtree edits plus the absolute `dotnet`; a test asserts `os.environ` is unchanged after `Port.run`-level code. CI's `windows-2025` job runs it.

### Pitfall 5: Experimental profile reuse after a cut-off copy
**What goes wrong:** `copytree` killed after `game.tsv` landed. Next run sees `game.tsv` newer than the repo's, reuses a profile with missing tables, and the shader split fails confusingly.
**How to avoid:** copy to `d.with_name(d.name + '.partial')`, then `nsp.swap_in`.

### Pitfall 6: Shared tool builds race across games
**What goes wrong:** two ports of **different** games (the per-folder lock allows it) both build the translator into `<user dir>/tools/dmsh_xlate.partial`, and both `dotnet build`/`restore` the same engine `obj/` folders.
**How to avoid (recommended, small):** a second, blocking lock (same helper, `LOCK_EX` without `LOCK_NB`; `LK_LOCK` on Windows) on `<user dir>/tools/.build.lock`, held around `translator()` and the `nx_extract` restore + build. Not required by HARD-04; Open Question 1.

### Pitfall 7: NuGet folder must match between restore and build
**What goes wrong:** restore with `NUGET_PACKAGES` set and build without it, or the reverse; the build re-restores elsewhere and the check guarded the wrong folder.
**How to avoid:** set it once in `self.env`; pass `env=self.env` to every dotnet call (`fingerprint(('cmd', …), env=self.env)` already does).

### Pitfall 8: Tests touching the real signing key or user dir
**What goes wrong:** a new test calls `paths.signing_key()` with the real `NX2A_HOME` and overwrites the developer's key.
**How to avoid:** every new test module sets `NX2A_HOME` to a temp dir at import, as `tests/test_porter.py:7` does. mkapk tests pass an explicit temp key path.

### Pitfall 9: `tools --only bogus` crashes with a KeyError
**What goes wrong:** `porter tools --only bogus --json` prints a traceback and `{"error": "KeyError: 'bogus'"}` [VERIFIED: run this session].
**How to avoid:** `choices` validation or a named error in `cmd_tools` (hook line), and cover it in the CLI error-path tests.

### Pitfall 10: Power loss versus D-09
**What goes wrong:** with the redo-all sweep removed, a machine crash (not a kill) could keep a key whose outputs' data blocks never reached the disk.
**How to avoid:** accepted residual risk [ASSUMED: journaled filesystems commit data before the later key's metadata in ordered mode]. fsyncing every output tree is too slow. Note it in ARCHITECTURE.md beside the marker rule.

## Code Examples

### Chunked install hash (HARD-07)
```python
# porter/adb.py:155 today: hashlib.md5(p.read_bytes()).hexdigest()
def md5(p):   # in pieces: a rewritten module can be hundreds of MB
    with open(p, 'rb') as f: return hashlib.file_digest(f, 'md5').hexdigest()
```

### Kill a stage mid-run, then redo it (HARD-05 test)
```python
# tests/test_stages.py: os._exit skips finally blocks and atexit, like SIGKILL, on every OS
CHILD = '''
import sys; sys.path.insert(0, {repo!r})
from pathlib import Path
from porter.upstream import nsp
def run(cmd, log, env=None, **kw):
    out = Path(str(cmd[-1])); out.mkdir(parents=True, exist_ok=True); (out / 'half').write_text('x')
    if {kill}: import os; os._exit(9)
    (out / 'whole').write_text('x')
nsp.run = run
nsp.extract_aoc(Path('nx'), Path('k'), nsp.Path({nxnative!r}), Path({work!r}), 0x0100000000AAA000, {{'dlc': [(0x0100000000AAB001, 0, Path({dlc!r}))]}}, Path({work!r}) / 'logs')
'''
# first child with kill=True → exit 9; second with kill=False → aoc/1/whole exists and aoc.key holds the key
```

### Crafted archives
```python
def evil_zip(path, name, target=None):
    with zipfile.ZipFile(path, 'w') as z:
        i = zipfile.ZipInfo(name)
        if target is not None: i.external_attr = (stat.S_IFLNK | 0o777) << 16; z.writestr(i, target)
        else: z.writestr(i, 'x')

def evil_tar(path, name, kind=tarfile.REGTYPE, linkname=''):
    with tarfile.open(path, 'w:gz') as t:
        ti = tarfile.TarInfo(name); ti.type = kind; ti.linkname = linkname; t.addfile(ti, io.BytesIO(b'') if kind == tarfile.REGTYPE else None)
# cases: '../x', '/abs', 'a\\..\\b', 'C:x', link 'l' → '/etc', link 'd' → '.', then 'd/x' → '../y', a valid 'lib/libc++.so.1' → 'libc++.so', tar hardlink to '../outside'
```

### adb without a device
```python
# tests/test_adb.py: subprocess.run inside porter.adb answers from a table; portable to Windows (no fake executable)
def fake(table, calls):
    def run(argv, **kw):
        calls.append(argv[1:]); out = next((v for k, v in table.items() if k in ' '.join(map(str, argv))), '')
        return subprocess.CompletedProcess(argv, 0, out, '')
    return run
# with mock.patch.object(adb.subprocess, 'run', fake({'find . -type f': '12 ./mods/main\n5 ./RomFS/a\n'}, calls)): ...
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `filter='tar'` when available | `filter='data'` everywhere; it is the default from 3.14 | 3.14 | `packaging/build_bootloader.py` already uses `data` |
| `.nupkg.sha512` as the package hash | `contentHash` (signature excluded) in lock/assets files | NuGet 4.9 repository signing | Survives re-signing |
| PID files for single-instance | OS advisory/byte-range locks | — | No stale locks |

**Deprecated/outdated:**
- "Require Python 3.11.4" (CONCERNS.md) is not enough: the filter bypasses were fixed in 3.11.13 / 3.12.11 / 3.13.4 [CITED: osv.dev/vulnerability/CVE-2025-4517].
- "Ryujinx 1.3.2" in `third_party/README.md` and `ryujinx/README.md`: the base is Canary-1.3.351.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Accept a Python below the floors when `os.path.ALLOW_MISSING` exists (distro backport). The success criterion's literal wording says "refuses … older than 3.11.13 …" | Pattern 1 | If the user wants the literal floor, Ubuntu 24.04 system-Python dev runs are refused; if a backport lacked the marker, it would be refused too (safe direction) |
| A2 | Compare `project.assets.json` `sha512` (contentHash) instead of `.nupkg.sha512` as D-05 words it | Pattern 9 | With `.nupkg.sha512`, a nuget.org re-sign breaks every port until the pins are bumped |
| A3 | D-12 languages come from an existing extraction, else the full list; `inspect` does not extract | Pattern 10 | If the user expects the real list before the first port, inspect would need nx_extract + keys (slow, needs dotnet) |
| A4 | Pinned vendor SHA-1 is adequate (second-preimage resistance) | Standard Stack | If the user wants SHA-256 everywhere, a pin script must download ~2.3 GB of NDKs per bump |
| A5 | Pins: .NET SDK 10.0.403 and platform-tools 37.0.1 (newest today; 10.0.403 is the SDK on this Mac) | Pattern 3 | A different tested version means different rows |
| A6 | Windows byte-range locks block reads by other processes, hence locking past the text | Pattern 5 | None if wrong (the offset is harmless) |
| A7 | `dotnet restore` runs no package-supplied build targets before the check | Pattern 9 | If wrong, a tampered package's targets could run before the check; still caught before nx_extract/translator runs |
| A8 | GitHub API unauthenticated limit (60/h) is ample for the FPSLocker head lookup | Pattern 4 | A rate-limited lookup takes the "use the cached copy" path |
| A9 | `os.link` no-clobber publish of the key is worth it over `os.replace` (two simultaneous first ports) | Pattern 7 | Over-engineering at worst; the locked text says `os.replace` (user may prefer it) |
| A10 | Power loss after D-09 is an accepted residual risk | Pitfall 10 | A rare corrupt reuse after a machine crash; the user deletes the build folder |

**Confirmed 2026-10-30:** the developer confirmed A1 (version floor or the `ALLOW_MISSING` marker, now D-13) and A2 (compare the contentHash, D-05 as amended). See the amendment in `02-CONTEXT.md`. A9 stays the planner's choice in a discretion area.

## Open Questions (RESOLVED)

1. **Lock shared tool builds across different games?**
   - What we know: the per-folder lock leaves `<user dir>/tools/dmsh_xlate.partial` and the engine `obj/` folders open to two ports of different games.
   - Recommendation: add the blocking `tools/.build.lock` (three lines with the same helper). Ask only if the planner wants to keep HARD-04 strictly scoped.
   - **Resolution:** Added (planner decision, no user input needed). Plan 02-10 Task 2 gives `porter/lock.py` `take(..., wait=True)` and holds `<user dir>/tools/.porter.lock` around NuGet restore, the check and the build. Two ports of different games would otherwise build the shared translator and the engine's `nx_extract` `obj/` folders at the same time. The per-folder lock (02-01) still stops at once; the tools lock waits and says whom it is waiting for.
2. **HARD-09 "recursive, including DLC folders":** count the files the port reads (exact; DLC NSPs are top-level per `scan_nsps`), or `rglob` the folder for `.nsp/.xci` (literal, over-counts subfolders the port ignores)?
   - Recommendation: the scanned family plus the re-check after extraction. Confirm with the user if the literal wording is meant.
   - **Resolution:** Developer confirmed on 2026-10-30 (D-15): count the base, update and DLC files that `inspect`/`scan_nsps` picked, plus a recursive count of the build folder, then check again after extraction with the real sizes. Plan 02-05 implements this.
3. **Where install finds the build folder:** a `build` key in `nx2a-data.json` (pushed to the device, so the device sees a local path) or a sidecar beside the pack?
   - Recommendation: manifest key (simplest); a sidecar if the user minds the path on the device.
   - **Resolution:** Developer chose the sidecar on 2026-10-30 (D-14). `datapack.build` writes the build folder's path to `<App>-data.build`, a file next to the `<App>-data/` pack folder on the host and outside the folder that gets pushed. `porter install` reads it to find the lock. `nx2a-data.json` gets no `build` key, and no host path reaches the device. Plan 02-01 implements it and tests that the pack holds no host path.
4. **Ryujinx patch base:** confirm the unmarked Shader hunks are local changes and not upstream commits between canaries; the patch task should review them before recording "Canary-1.3.351 + patch".
   - **Resolution:** Planner decision, no user input needed. The patch is made against Ryubing Canary-1.3.351 (`475615f`), the closest upstream commit. Shader diffs without `nxnative:` markers are treated as local changes. "Canary-1.3.351 + nxnative-local.patch" rebuilds the vendored tree either way, because every hunk is by definition a difference from that base. Plan 02-03 checks this by applying the patch to a clean `475615f` checkout and comparing the result with the vendored tree, and its README lists the unmarked files so a later re-vendor can review them.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python (venv) | all tests | ✓ | 3.14.5 (`.venv/bin/python`) | — |
| Python 3.11 floor | floor tests | ✓ | 3.11.15 (uv) | CI `ubuntu-22.04` 3.11 job |
| Pre-fix Python | negative floor probe | ✓ | 3.12.9 (`/usr/local/bin/python3.12`) | Patch `sys.version_info` + `vars(os.path)` in the test |
| .NET SDK | NuGet pin generation, restore tests (optional) | ✓ | 10.0.403 (`/usr/local/share/dotnet`) | Unit test the check against a fixture `project.assets.json` |
| adb | none (tests mock it) | ✓ | 36.0.0 (Homebrew) | — |
| Android NDK | none in this phase's tests | ✗ | — | Tests use crafted archives and fake `source.properties` |
| `gh` / network | pin generation, FPSLocker SHA | ✓ | — | — |
| CI hosts | per-OS runs | ✓ | windows-2025, macos-15, ubuntu-22.04, ubuntu-24.04-arm, ubuntu-22.04/3.11 (`fork-ci.yml:27-31`) | — |

**Missing dependencies with no fallback:** none.
**Missing dependencies with fallback:** NDK (not needed by the tests).

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | Python `unittest` (stdlib); PySide6 QtTest for GUI checks (offscreen) |
| Config file | none (discover over `tests/`); CI `.github/workflows/fork-ci.yml` |
| Quick run command | `.venv/bin/python -m unittest tests.test_fetch tests.test_lock tests.test_stages -v` |
| Full suite command | `QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover -v tests && .venv/bin/python tests/arch_rules.py` (baseline: 115 tests, 13.4 s, OK) |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| HARD-01 | Crafted zip (`..`, absolute, backslash, drive, abs link, escaping link, link-through-link) refused, nothing outside, tmp removed; valid internal link kept; tar `..`/abs/hardlink-outside refused | unit | `python -m unittest tests.test_fetch.Unpack -v` | ❌ Wave 0 |
| HARD-01 | `python_ok` for (3,11,12)/(3,11,13)/(3,12,10)/(3,12,11)/(3,13,3)/(3,13,4)/(3,14,0) and marker on/off; `doctor` shows the red row; `port`/`inspect --json` refuse | unit + subprocess | `python -m unittest tests.test_toolchain.PythonFloor -v` | ❌ Wave 0 |
| HARD-02 | New key 0600 (POSIX), written whole; unreadable key → exit with message, file untouched; existing 0644 tightened; porter preflight BuildError | subprocess (mkapk with a dummy .so) | `python -m unittest tests.test_signing -v` | ❌ Wave 0 |
| HARD-03 | Pinned 200 → commit recorded; pinned 404 → head + `[RED]` untested; both 404 → None; sha256 in log and `fpslock.tsv` | unit (patched urlopen) | `python -m unittest tests.test_porter.FpsLocker -v` | ✅ extend |
| HARD-04 | Holder subprocess holds `.porter.lock`; second `take` raises "already running: porter port, PID …"; holder killed → free | integration | `python -m unittest tests.test_lock -v` | ❌ Wave 0 |
| HARD-05 | `os._exit` mid-`extract_aoc` → next run redoes; experimental copy cut off → recopied; marker message names the stage, keys kept | integration | `python -m unittest tests.test_stages -v` | ❌ Wave 0 |
| HARD-06 | `os.environ` unchanged after `use_profile_dir`/env build; `game.load` by path; overrides assert at import (simulate a missing attribute → AssertionError naming it) | unit | `python -m unittest tests.test_porter.Env -v` | ❌ Wave 0 (class) |
| HARD-07 | Crash after `dst→old` → `recover()` restores; build leaves no `.old`; `md5()` equals `hashlib.md5` of bytes | unit | `python -m unittest tests.test_stages.DataPack tests.test_adb -v` | ❌ Wave 0 |
| HARD-08 | Game card with name `<b>&x</b>` renders literally; download list href escaped; log font is the system fixed font | GUI offscreen | `QT_QPA_PLATFORM=offscreen python -m unittest tests.test_bridge.Escaping -v` | ✅ extend |
| HARD-09 | Space counts base+updates+DLC; re-check after extraction raises when free space drops | unit | `python -m unittest tests.test_porter.Misc.test_disk_space -v` | ✅ extend |
| HARD-10 | `probes/app/mkapk.py` gone; `.gitignore` has `*.code-workspace`; FLIP commit in README; patch file applies to `475615f`; `inspect` JSON has `languages`; GUI has no `LANGUAGES` | unit/static | `python -m unittest tests.test_porter.Housekeeping -v` | ❌ Wave 0 |
| PKG-07 | Pinned row used; hash mismatch names both hashes and deletes the file; pinned 404 → fallback `untested`; NDK 404 stops; no-row host → untested; NuGet check flags an extra/changed package and removes its folder | unit (patched urlopen, fixture assets JSON) | `python -m unittest tests.test_fetch.Pins tests.test_fetch.NuGet -v` | ❌ Wave 0 |
| TEST-01 | adb: `push_file` resume keeps pieces at size; `remote_sizes` parses `stat` lines with spaces; stale files removed in batches of 64; replace-signer uninstalls then installs; plain incompatible install raises the named error | unit (mocked `subprocess.run`) | `python -m unittest tests.test_adb -v` | ❌ Wave 0 |
| TEST-01 | Toolchain: `find_ndk` order (config > `ANDROID_NDK_HOME` > r27c preferred among found); `find_dotnet` prefers SDK 10; `user_dir` per platform | unit (patched env, `sys.platform`, fake folders) | `python -m unittest tests.test_toolchain -v` | ❌ Wave 0 |
| TEST-01 | CLI error paths: `inspect` empty folder `{"error"}`; `port` without keys → error event; `install` non-pack → error; `config badkey` → 1; `tools --only bogus` named error | subprocess | `python -m unittest tests.test_cli -v` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** the touched test module(s), e.g. `.venv/bin/python -m unittest tests.test_fetch -v`
- **Per wave merge:** full suite command plus `tests/arch_rules.py`
- **Phase gate:** full suite green locally and on `fork-ci.yml`'s five jobs (Windows lock and env tests matter most) before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/test_fetch.py`: Unpack, Pins, NuGet (+ fixture `tests/fixtures/nuget/project.assets.json`)
- [ ] `tests/test_lock.py`
- [ ] `tests/test_stages.py`: cut-off, DataPack
- [ ] `tests/test_signing.py` (fixture: tiny `.so` bytes; generate one key in `setUpClass`, which takes a few seconds in pure Python)
- [ ] `tests/test_adb.py`
- [ ] `tests/test_toolchain.py`
- [ ] `tests/test_cli.py`
- [ ] Every new module sets `NX2A_HOME` to a temp dir at import, and follows `tests/test_porter.py`'s lz4/CI skip guard

## Security Domain

### Applicable ASVS Categories (Level 1)

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | — |
| V3 Session Management | no | — |
| V4 Access Control | yes (local files) | 0600 key, OS lock, unpack confined to its folder |
| V5 Input Validation | yes | Archive member checks, `filter='data'`, FPSLocker `Refused` (existing), manifest-driven hashes, `html.escape` |
| V6 Cryptography | yes | `hashlib` for pins; existing mkapk RSA (not changed); no new crypto |
| V8 Data Protection | yes | Signing key 0600 + atomic; logs never hold key contents (existing test) |
| V10 Malicious Code / supply chain | yes | Pinned URLs + hashes, NuGet contentHash pins, FPSLocker commit pin |
| V12 Files and Resources | yes | Path traversal / zip-slip / symlink escape refused |
| V14 Configuration | yes | One manifest, bump procedure beside it |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Zip-slip via member name or symlink | Tampering / Elevation | Names checked first, links last, resolved containment, partial unpack removed |
| Tar filter bypass (CVE-2025-4517 family) | Tampering | `filter='data'` + Python floor/marker |
| Compromised vendor index serving a matching bad hash | Tampering | Hash pinned in the repo, not taken from the index (except the flagged `untested` fallback) |
| NuGet package substitution or re-publish | Tampering | contentHash pins checked after restore, before build |
| FPSLocker config changed on a moving branch | Tampering | Commit pin; sha256 recorded and logged |
| Signing key read by other local users | Information disclosure | 0600 on POSIX; `%APPDATA%` ACL on Windows |
| Signing key truncated or forked | Denial of service (updates fail) | Atomic no-clobber write; refuse to regenerate an unreadable key |
| Concurrent writers corrupt a build | Tampering | Per-folder OS lock; port and install share it |
| Markup injection in Qt rich text (game names, network strings) | Spoofing | `html.escape(..., quote=True)` |

## Sources

### Primary (HIGH confidence)
- Live code read this session: `porter/{fetch,pipeline,cli,runlog,upstream,toolchain,paths,datapack,install,adb,fpslocker,procs}.py`, `gui/app.py`, `nxnative/scripts/build_ipa_from_nsp.py`, `nxnative/dm/android/apk/mkapk.py`, `nxnative/dm/games/game.py`, `nxnative/dm/tools/nacp.py`, csproj/props files, tests.
- Google SDK index `https://dl.google.com/android/repository/repository2-3.xml` (fetched); .NET `https://builds.dotnet.microsoft.com/dotnet/release-metadata/10.0/releases.json` (fetched; 10.0.403 tarball hash matched).
- Probes: NDK r27c zips via HTTP range; platform-tools and .NET archives; NuGet restore; Python marker on six interpreters; current `_unzip` escape; FPSLocker pinned/raw/API; FLIP blob match (gh api); Ryujinx tags (git ls-remote, sparse clone).
- [Python subprocess docs](https://docs.python.org/3/library/subprocess.html): Windows `env` cannot override PATH lookup.
- [Python msvcrt docs](https://docs.python.org/3/library/msvcrt.html): `locking` region and `LK_NBLCK`.
- [Python os.path docs](https://docs.python.org/3/library/os.path.html): `ALLOW_MISSING`.

### Secondary (MEDIUM confidence)
- [CPython PR #135037](https://github.com/python/cpython/pull/135037): tarfile link normalisation, adds `realpath(strict=ALLOW_MISSING)`.
- [OSV CVE-2025-4517](https://osv.dev/vulnerability/CVE-2025-4517), [Debian tracker](https://security-tracker.debian.org/tracker/CVE-2025-4517): fixed in 3.9.23 / 3.10.18 / 3.11.13 / 3.12.11 / 3.13.4, 3.14.0b3.
- [Ubuntu CVE-2025-4517](https://ubuntu.com/security/CVE-2025-4517), [USN-7583-1](https://ubuntu.com/security/notices/USN-7583-1): noble python3.12 fixed in 3.12.3-1ubuntu0.7.
- [NuGet Nupkg Metadata File wiki](https://github.com/NuGet/Home/wiki/Nupkg-Metadata-File), [NuGet/Home#7283](https://github.com/NuGet/Home/issues/7283): contentHash excludes the signature; `.nupkg.sha512` is the whole file.
- [remotebranch.eu 3.12 backport commit](https://remotebranch.eu/Stowage/cpython/commit/19de092debb3d7e832e5672cc2f7b788d35951da), [3.11 backport](https://remotebranch.eu/Stowage/cpython/commit/4633f3f497b1ff70e4a35b6fe2c907cbe2d4cb2e).

### Tertiary (LOW confidence)
- [openSUSE python313 changes](https://src.opensuse.org/pool/python313/raw/branch/slfo-1.2/python313.changes), [Vulert CVE-2025-4517](https://vulert.com/vuln-db/CVE-2025-4517), [Alpine tracker](https://security.alpinelinux.org/vuln/CVE-2025-4517), [nuget-packageslock2nix](https://github.com/mdarocha/nuget-packageslock2nix).

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH (stdlib only; behaviour probed on real archives and interpreters)
- Architecture: HIGH (hook points and subtree sites read line by line)
- Pitfalls: MEDIUM-HIGH (Windows lock read-blocking and power-loss ordering are assumed)

**Research date:** 2026-10-30
**Valid until:** 2026-11-30 for pins (the .NET SDK moves monthly; re-read the indexes when writing `pins.py`); 2027-01 for the rest
