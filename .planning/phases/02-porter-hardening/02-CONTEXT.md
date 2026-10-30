# Phase 2: Porter Hardening - Context

**Gathered:** 2026-10-30
**Status:** Ready for planning

<domain>
## Phase Boundary

Ports survive interruption, hostile archives and tampered downloads without corrupting builds or losing the signing key. Requirements: HARD-01 to HARD-10, PKG-07, TEST-01 (see `.planning/REQUIREMENTS.md`), measured by the five success criteria of Phase 2 in `.planning/ROADMAP.md`.

In scope: safe zip/tar extraction and the old-Python refusal; one pin manifest for toolchain downloads, NuGet packages and the FPSLocker source; the build-folder lock; atomic stage stamps; the atomic data-pack swap and chunked install hashing; the signing key written safely; env dicts instead of `os.environ` mutation; named and asserted upstream overrides; the rest of `.planning/codebase/CONCERNS.md` still open after Phase 1; the TEST-01 suite.

Not in scope: the Linux arm64 community NDK and its pinned hash (Phase 3, which extends this phase's manifest), NuGet restore during Setup (Phase 3), the download Cancel button (Phase 3, FRUN-01), and per-game settings UI (Phase 4).

</domain>

<decisions>
## Implementation Decisions

### Carried forward (decided earlier, not re-asked)
- Edits to upstream's busy files (`porter/cli.py`, `porter/pipeline.py`, `gui/app.py`) stay at hook lines. New logic goes in new porter files (Phase 1).
- Phase 1's D-08 "run in progress" marker (`porter/runlog.py` `build_folder`) was always meant to be replaced by HARD-05's per-stage stamps. D-08 below settles what stays.
- Protocol changes are additive only, with no version field (Phase 1).
- Already closed in Phase 1, so not redone here: cancel of the process tree, `call_json` keeping stderr, one-shot timeouts, the inspect error shown as the real cause, the window-close guard, pinned and hashed Python locks, cross-platform packaging.

### Download pinning (PKG-07, HARD-03)
- **D-01:** One manifest in the repository pins each toolchain download (Android NDK r27c, one exact .NET SDK 10.0.x, one exact platform-tools release) by exact version, URL and hash. The downloader fetches the pinned URL. A pinned file that downloads but fails its hash stops with a clear message naming the file and both hashes.
- **D-02:** When the vendor no longer serves the pinned file (for example, Google's index lists only the newest platform-tools), porter falls back to the vendor's newest release, checks it against the vendor's own index hash (today's check), and warns in the log and the GUI that this version is untested. A pinned URL that is gone is not a "mismatch" and does not stop Setup.
- **D-03:** FPSLocker: the manifest pins one FPSLocker-Warehouse commit SHA, and configs are fetched at that commit (`raw.githubusercontent.com/.../<commit>/...` instead of the moving `v4` branch). When that commit has no config for the game's build (a game version newer than the pin), porter fetches from `v4` head and warns. Either way, the port log shows the commit the config came from and its SHA-256, and both are recorded in the build folder. Moving to newer configs is a one-line manifest bump.
- **D-04:** Toolchains the player already has (an NDK via `ANDROID_NDK_HOME`, a system .NET, a distro adb) keep today's checks (`porter/toolchain.py`: the NDK r27c revision, .NET major 10, adb present). The manifest governs only what porter downloads.
- **D-05:** NuGet pins live in porter's manifest only: each package (LibHac 0.19.0 for `nx_extract`, and the packages the Ryujinx projects restore for `dmsh_xlate`) with its exact version and SHA-512. After restore, porter compares them with the restored `.nupkg.sha512` files and stops on any mismatch, naming the package. No `packages.lock.json` goes into the nxnative subtree. The developer chose this over the research's lock-file recommendation (`.planning/research/PITFALLS.md` §14), accepting that the check runs after restore.
  - **Amended 2026-10-30 (developer, after the plan check):** porter compares each package's *content hash* instead of `.nupkg.sha512`. The content hash is the `sha512` in `obj/project.assets.json` `libraries.<id>/<version>.sha512`, which equals `.nupkg.metadata` `contentHash`. It leaves out nuget.org's repository signature, so a re-sign does not break ports, while `.nupkg.sha512` hashes the whole signed file and would change. Everything else in D-05 stands: the pins live only in porter's manifest, the check runs after restore and before any build, a mismatch stops the port and names the package, and no lock file goes into the subtree. The `.nupkg.sha512` wording above is superseded; it stays here as history (RESEARCH A2).

### Concurrent and cut-off ports (HARD-04, HARD-05, HARD-07)
- **D-06:** A second port of the same game folder stops at once with "already running", naming the command holding the lock (port or install), its PID and its start time. The GUI shows it on the game card like any porter error. The lock is an OS file lock (`fcntl.flock` on POSIX, `msvcrt.locking` on Windows) on a file in `<tid>_build/`. The OS releases it when the holder dies, so a crash can never leave a stale lock to clear by hand.
- **D-07:** `porter port` and `porter install` of the same game take the same lock, so an install never pushes a pack that is halfway through its swap. Upstream's iOS script (`nxnative/scripts/build_ipa_from_nsp.py` `main()`) does not take it. The rule that iOS and Android builds share `<tid>_build/` is written down in `docs/ARCHITECTURE.md`.
- **D-08:** The "stamp last, atomically" fix goes into the subtree as a small, platform-neutral edit to `nxnative/scripts/build_ipa_from_nsp.py`: the reuse-key write becomes temp + `os.replace`, and any stage that writes its outputs in place is fixed to swap them in before its key is written. It also fixes the iOS build and is worth offering upstream. It is not done by overriding upstream helpers from porter.
- **D-09:** Once the stamps land, Phase 1's D-08 marker keeps only its message: the next port still says "the last port of this game was cut off in <stage>", but only stages whose stamps don't match run again. The redo-every-stage behaviour is removed.

### Housekeeping (HARD-10)
- **D-10:** `probes/app/mkapk.py` is deleted. The probe app's build instructions (the header of `probes/app/probeapp.c`) call the committed `nxnative/dm/android/apk/mkapk.py` with `--lib`, `--package`, `--label` and an explicit key path. That leaves one signer, so the 0600/atomic key fix covers both.
- **D-11:** The commit hook is bootstrapped by a small devtools script that runs `git config core.hooksPath .githooks`. The README's contributor section says to run it once. No test fails or warns when it hasn't been run.
- **D-12:** The language list has one source, upstream's `nacp.LANGUAGES`. `porter inspect` adds the game's supported languages to its JSON (codes and names, from the control data's supported-language flags via `nacp`), and the GUI's language box fills from that. `gui/app.py`'s own `LANGUAGES` list goes away.

### Amendment 2026-10-30 (developer decisions after the plan check)
The orchestrator asked the developer about the four points the plan check raised. These decisions are locked and replace the matching text elsewhere in this file. D-05's change is recorded under D-05 above.
- **D-13 (Python check: version or marker):** porter accepts a Python at or above 3.11.13, 3.12.11 or 3.13.4 (or 3.14+). It also accepts an older one that has `os.path.ALLOW_MISSING`, because a distro backport of the CVE-2025-4517 fix, such as Ubuntu 24.04's patched 3.12.3, keeps its old version number but adds that marker. Every other Python is refused (`doctor` still runs and shows the red row). This makes RESEARCH A1 a decision. ROADMAP Phase 2 success criterion 1 now reads "porter refuses to run on a Python without the CVE-2025-4517 tarfile fix (below 3.11.13, 3.12.11 or 3.13.4 and lacking `os.path.ALLOW_MISSING`)".
- **D-14 (build-folder path: host sidecar):** `porter install` finds a pack's build folder through a small file written next to the `<App>-data` pack folder on the host, outside the folder that gets pushed to the device. `nx2a-data.json` gets no `build` key, and no host path may reach the device. A pack without the sidecar (made before this phase, or copied without it) installs without the lock. This resolves RESEARCH Open Question 3.
- **D-15 (HARD-09 scope: the files the port reads):** the disk-space check counts the base, update and DLC files that `inspect` picked, plus a recursive count of the build folder, and checks again after extraction with the real sizes. It does not walk every `.nsp`/`.xci` under the game folder. This resolves RESEARCH Open Question 2.

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

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Scope and requirements
- `.planning/ROADMAP.md` § Phase 2: goal and the five success criteria
- `.planning/REQUIREMENTS.md`: HARD-01 to HARD-10, PKG-07, TEST-01
- `.planning/codebase/CONCERNS.md`: every concern this phase closes, with files and fix approaches (some were closed in Phase 1, see Carried forward)

### Research
- `.planning/research/PITFALLS.md`: §4 stage stamps written last and atomically; §14 pinning (exact versions, FPSLocker commit and hash, NuGet; the platform-tools URL lifetime is unverified); the signing-key atomic write recipe (around line 264); the Windows env-dict / bare `dotnet` pitfall
- `.planning/research/SUMMARY.md`: Phase 2 items (atomic stamps, `atomic_write` helper, data-pack swap, chunked hashing, env dicts, lock, manifest)

### Prior phase
- `.planning/phases/01-bridge-bundles-and-ci/01-CONTEXT.md`: D-08 (cut-off marker), D-05/D-09 (stop semantics), and the hook-lines-only rule
- `.planning/STATE.md` § Blockers/Concerns: the cut-off cache risk and the platform-tools URL research item

### Project rules
- `docs/ARCHITECTURE.md`: layer rules. The GUI holds no pipeline logic. The iOS/Android sharing rule for `<tid>_build/` goes here (D-07)
- `tests/arch_rules.py`: the enforced static checks (no PySide6 in `porter/`, and so on)
- `.planning/PROJECT.md` § Constraints: upstream compatibility, keeping subtree edits small and platform-guarded, the Python version floors, never shipping keys or FPSLocker configs

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `nsp.swap_in(tmp, dst)`, `nsp.reused(kf, key)`, `nsp.fingerprint(...)` (`nxnative/scripts/build_ipa_from_nsp.py:363,677,655`): upstream's stage-reuse helpers, where D-08's atomic key write goes. Key writes are at lines ~773, 805, 849, 898, 1229 and 1327, and porter's own at `porter/pipeline.py:295,323`.
- `porter/runlog.py` `build_folder` / `_unmark` / `cut_off`: the D-08 marker. It keeps its message and loses the redo-all (D-09).
- `porter/fetch.py` `Item`, `_download` (hash while downloading, delete on mismatch), `_unzip`, `_untar`, `plan`: where the manifest pins, the fallback and safe extraction plug in.
- `porter/fpslocker.py` `RAW`, `url()`, `fetch()`: the fetch to move to a pinned commit with a head fallback.
- `porter/datapack.py` `build`: already builds into `<dst>.partial`. Only the final `rmtree` + `rename` needs the aside-swap.
- `porter/adb.py` `push_tree` / `remote_md5`: the whole-file `read_bytes()` MD5 to make chunked.
- `porter/procs.py`: process-tree handling from Phase 1. The lock holder's PID and start time can go in the lock file.
- `porter/tls.py` `context()`: every `urlopen` must pass `context=tls.context()` (enforced by a test since Phase 1, WR-02).
- `tests/fixtures/bridge/` and the `fake_porter` pattern from Phase 1: a model for a fake `adb`.

### Established Patterns
- Errors the user sees are `BuildError` with a message that names the file and the fix. Problem log lines start with `[RED] `.
- Dense one-line Python style; module header comments state the module's job and contract; comments cite the evidence (game, log line).
- New CLI flags go into `porter/cli.py` first, and the GUI reaches porter only through `--json` / `--progress json`.
- Upstream overrides live in `porter/upstream.py` `_load_nsp()` (four today: `nacp`, `pg`, `can_clone`, `profile_files`).

### Integration Points
- `porter/pipeline.py:81-95` `Port.run`: where `os.environ` PATH/`DOTNET_ROOT` is mutated today; `:162-165` `use_profile_dir` writes `DM_GAMES_DIR`/`DM_GAMES_FIRST` into `os.environ`.
- `porter/pipeline.py:154` `check_space`: counts only the folder's top-level NSP/XCI.
- `porter/pipeline.py:147-150` `inputs`: where the lock and the cut-off note hook in (hook lines only).
- `porter/install.py` / `porter/cli.py` `install`: the install side of the D-07 lock.
- `nxnative/dm/android/apk/mkapk.py:193-198`: key read and create (plain `open(keyf, 'w')`).
- `gui/app.py:18` `LANGUAGES`, `:63,121-127` rich-text card, `:102` font: D-12, escaping and the system mono font.
- `porter/toolchain.py:96-97`: today's Python `>= (3, 11)` check.

</code_context>

<specifics>
## Specific Ideas

- The developer prefers resilience over strictness when a vendor moves on (D-02, D-03): fall back with a visible "untested" warning rather than block testers, but always stop on a hash that doesn't match.
- Small, platform-neutral subtree edits are acceptable when they fix the cause where it lives (D-08), and preferred to growing porter's overrides of upstream internals.
- No new files in the nxnative subtree just for pinning (D-05).

</specifics>

<deferred>
## Deferred Ideas

None. The discussion stayed within the phase scope.

</deferred>

---

*Phase: 02-porter-hardening*
*Context gathered: 2026-10-30*
*Amended: 2026-10-30 (D-05 content hash; D-13 to D-15 added after the plan check)*
