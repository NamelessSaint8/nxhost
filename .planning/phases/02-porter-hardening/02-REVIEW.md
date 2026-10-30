---
phase: 02-porter-hardening
reviewed: 2026-10-30T20:23:52Z
depth: standard
files_reviewed: 6
files_reviewed_list:
  - docs/ARCHITECTURE.md
  - porter/fetch.py
  - porter/lock.py
  - porter/pipeline.py
  - tests/test_fetch.py
  - tests/test_lock.py
findings:
  critical: 1
  warning: 6
  info: 9
  total: 16
status: issues_found
---

# Phase 02: Code Review Report

**Reviewed:** 2026-10-30T20:23:52Z
**Depth:** standard
**Files Reviewed:** 6
**Status:** issues_found

## Summary

This is an incremental re-review of `git diff 472214a..HEAD` over the six listed files, after gap-closure plans 02-11 (CR-01) and 02-12 (CR-02, CR-03). I also read the code these changes call: `nsp.reused`, `nsp.swap_in`, `nsp.write_whole` and `nsp.rmtree` in `nxnative/scripts/build_ipa_from_nsp.py`, `nuget.restored`, and `fetch._install`. `tests.test_lock` and `tests.test_fetch` pass on macOS with Python 3.14.5 (25 tests).

Where the three earlier blockers stand:

| Earlier finding | Status | Notes |
|---|---|---|
| CR-01: a zip link through a later link escapes | **Closed for the reported repro; the guard still leaks, see CR-04** | The second pass resolves every link once all of them exist, which defeats the three-entry zip in both orders. The pass checks against the temporary `.<folder>.unpack` folder, though, and `_install` then installs a different tree: it strips the top folder and moves it to a new name. Links that pass the check can point outside the installed toolchain. I reproduced this (CR-04). |
| CR-02: the Windows holder read crosses the locked byte | **Closed in code; not yet run on Windows** | With `buffering=0`, `f.read(AT)` is one raw `read(4096)` at offset 0, covering bytes 0 to 4095, and never reaches byte 4096. `tests/test_lock.py` `test_holder_read_stays_below_lock` pins that bound on POSIX. `main` is 106 commits ahead of `origin/main`, so the `windows-2025` job in `fork-ci.yml` has not run this code yet. |
| CR-03: the translator rebuild deletes a dll that is in use | **Closed** | Each key now builds into its own `dmsh_xlate-<key[:12]>` folder, and reuse is checked again once the tools lock is held. A folder is only removed by a rebuild for its own key, and that runs only after the reuse check has failed under the lock, which means the key file is missing. A port that is using the folder read that key file, so this does not happen in normal operation. |

There is one new blocker (CR-04). WR-01 to WR-06 and IN-01 to IN-05 from the earlier review are in files this change did not touch. I re-checked each at its line in the current tree and carry them forward unchanged.

## Narrative Findings (AI reviewer)

## Critical Issues

### CR-04: Links are checked against the unpack folder, but a different tree is installed, so a link can leave the installed toolchain

**File:** `porter/fetch.py:141-149` (check), `porter/fetch.py:166-169` (`_install` strips the top folder and moves it)
**Issue:** `_unzip` resolves every link and requires it to stay inside `into` (`<toolchains>/.<folder>.unpack`). `_install` then installs `src`, which is the single top folder when there is one, or the whole folder for .NET, under a different name, `<toolchains>/<folder>`. Relative link targets mean something different after that move:
- **One archive, one level up.** In the unpack folder, `top/up -> ../adb` resolves to `.ndk.unpack/adb`, which is inside the folder, so it is accepted. After the move, `ndk/up` resolves to `<toolchains>/adb`, the sibling toolchain. Reproduced with `fetch._install`: `ACCEPTED ... up -> ../adb => .../toolchains/adb  inside dest: False`.
- **Name tricks.** A target that climbs out and comes back in by the unpack folder's name (`../../.ndk.unpack/...`), or by a top folder that has a sibling's name (a top folder called `adb` with `x -> ../adb/...`), passes the check and points somewhere else after the move.
- **Chained across installs, to any depth.** Reproduced: platform-tools with `platform-tools/z -> ..` is accepted, because it resolves to the unpack root. Installed, `adb/z` resolves to `<toolchains>`. A later NDK with `top/k -> ../adb/z/../config.json` is accepted, because `adb` does not exist in its unpack folder and the path is resolved lexically. Installed, `ndk/k` resolves to and reads `<user dir>/config.json`. The same folder holds `signing-key.json`. Each reinstall can stack one more level.

The archives still have to match the pinned hash, or on the fallback path the vendor's listed hash. This guard exists for the hostile-archive case, and it does not hold for the tree the player actually gets. This is the same impact model the earlier CR-01 was rated on.
**Fix:** Validate the tree where it will live. After `src.replace(dest)`, resolve every link under `dest` and require it to stay inside `dest`. Also refuse targets that climb above `dest` lexically. That second rule stops paths that pass through a sibling folder and back in, which a later reinstall of that sibling could redirect. On refusal, remove `dest`.
```python
def _links_inside(arc, root):   # every link where it is installed, with every other link and every sibling toolchain in place
    r = root.resolve()
    for d, dirs, files in os.walk(root):   # followlinks=False: a link to a folder is checked, not entered
        for n in dirs + files:
            p = Path(d, n)
            if not p.is_symlink(): continue
            t = os.readlink(p); rel = os.path.normpath(os.path.join(os.path.relpath(d, root), t))
            try: inside = not rel.startswith('..') and p.resolve().is_relative_to(r)
            except RuntimeError: inside = False   # 3.11/3.12: a link loop
            if not inside: raise BuildError(f'{arc.name}: refused, link {p.relative_to(root)} → {t} leaves {root.name}')

# _install:
        shutil.rmtree(dest, ignore_errors=True); src.replace(dest)
        try: _links_inside(arc, dest)
        except BaseException: shutil.rmtree(dest, ignore_errors=True); raise
```
`_unzip`'s two passes can stay as they are, as the first line of defence. Add two tests to `tests/test_fetch.py`: `top/up -> ../adb` must be refused, and the platform-tools then NDK pair above must be refused.

## Warnings

### WR-01: `porter install` recovers the pack before taking the port's lock (carried forward, not touched by 02-11/02-12)

**File:** `porter/cli.py:113-114`
**Issue:** `datapack.recover(data)` runs before `lock.take(b, 'install')`. A port in the middle of a swap has renamed `dst` to `.old` and is about to call `swap_in(tmp, dst)`. On Windows that window lasts up to 15 s while `swap_in` retries. If `install` runs in that window, its `recover` renames `.old` back to `dst`. The port's `tmp.rename(dst)` then fails, and `install` fails too, on the lock it only takes afterwards.
**Fix:** Take the lock first, then recover:
```python
b = datapack.build_dir(data); held = lock.take(b, 'install') if b and b.is_dir() else None
datapack.recover(data)
```

### WR-02: The tools lock is held for a whole survey, not just the nx_extract build (carried forward)

**File:** `porter/pipeline.py:192-193`
**Issue:** `with nuget.restored(...): facts = nsp.survey(...)` holds `<user dir>/tools/.porter.lock` while the survey builds nx_extract, extracts, and reads the results. That can take minutes. Every other game's port waits at its tool build stage the whole time.
**Fix:** Build nx_extract under the lock and run the survey outside it. For example, wrap only `nsp.build_nx_extract` through an override in `porter/upstream.py`.

### WR-03: The signing key is published only through `os.link` (carried forward)

**File:** `nxnative/dm/android/apk/mkapk.py:199-201`
**Issue:** Only `FileExistsError` is handled. On FAT32/exFAT (`NX2A_HOME` on a USB drive) or some SMB homes, `os.link` raises `PermissionError` or `OSError(EPERM/ENOTSUP)`, the APK stage dies, and no port on that setup can ever be signed.
**Fix:** If the link fails for any other `OSError`, return `False` when `keyf` exists, and otherwise `os.rename(tmp, keyf)`.

### WR-04: Linux arm64 gets the x86-64 NDK and platform-tools as "pinned" (carried forward)

**File:** `porter/fetch.py:47`, `porter/fetch.py:79-83`
**Issue:** `_google_os()` returns `'linux'` on every Linux CPU. On aarch64 this installs x86-64 binaries that are presented as the tested pins, after a download of about 660 MB.
**Fix:** In `_pinned`/`_google`, return `None` or refuse `Android NDK` and `adb` when `platform.machine()` is `aarch64` or `arm64` on Linux.

### WR-05: Replacing an existing toolchain is not atomic (carried forward)

**File:** `porter/fetch.py:169`
**Issue:** `shutil.rmtree(dest, ignore_errors=True); src.replace(dest)`. On Windows, a file that is in use survives `rmtree`, and then `replace` fails. The old toolchain is left half-deleted while `config` still points at it. The fix for CR-04 adds another failure point after this deletion, which makes this worse.
**Fix:** Rename `dest` aside, run `src.replace(dest)` and the link check, then remove the aside copy. On failure, rename the aside copy back.

### WR-06: Moving the old data pack aside has no Windows retry, unlike `swap_in` (carried forward)

**File:** `porter/datapack.py:66`
**Issue:** `dst.rename(old)` has no retry for a scanner or indexer that holds files in the pack, which `swap_in` handles with up to 15 s of retries.
**Fix:** Reuse `swap_in`'s retry loop around `dst.rename(old)`.

## Info

### IN-01: The status badge text is the one game-card string left unescaped (carried forward)

**File:** `gui/app.py:132`
**Fix:** `&nbsp;{e(st)}&nbsp;`.

### IN-02: A failed inspect keeps the previous game's language list (carried forward)

**File:** `gui/app.py:123-125`
**Fix:** Reset the combo before the `if fail:` return.

### IN-03: The NuGet check assumes the first package folder (carried forward)

**File:** `porter/nuget.py:15`
**Fix:** Look the package up in every `packageFolders` key, or clear `RestoreFallbackFolders`.

### IN-04: Two game folders of one title with one output folder race on the pack's `.partial` (carried forward)

**File:** `porter/datapack.py:44`
**Fix:** Document it, or also lock `<out>/<stem>-data.build`.

### IN-05: Stale reference to the deleted probe packer (carried forward)

**File:** `.claude/CLAUDE.md:351`
**Fix:** Drop `probes/app/mkapk.py` from the line.

### IN-06: Some hostile zips are refused with a raw OS error instead of the `refused` message

**File:** `porter/fetch.py:145-149`
**Issue:** These archives fail closed, and `_install` removes `.unpack`, but the player sees a traceback instead of a `BuildError`:
- A link loop (`a -> b`, `b -> a`) raises `RuntimeError: Symlink loop` from `Path.resolve()` on Python 3.11/3.12. On 3.13+ the same loop is accepted. It is harmless, because the kernel fails ELOOP on any path through it.
- A link entry with the same name as a folder entry fails `t.unlink` with `PermissionError`/`IsADirectoryError`.
- A link under an earlier dangling link fails `mkdir` with `FileExistsError`.

I reproduced all three.
**Fix:** In the link loop, catch `(OSError, RuntimeError)` and raise `refuse(info.filename, target)` from it.

### IN-07: The second reuse check runs after the restore and the NuGet check, not right after the lock

**File:** `porter/pipeline.py:345-346`, `porter/nuget.py:36-40`
**Issue:** A port that waited for the tools lock and only needs to reuse the translator still runs `dotnet restore` and `nuget.check` before it re-checks. If that restore fails, for example on a network or feed error during a non-no-op restore, the port fails even though a usable translator is already built.
**Fix:** Give `restored()` an optional `ready` callable that is checked right after `lock.take`, and skip the restore when it returns true. Alternatively, take the lock in `translator()` itself and call `restored` only for a rebuild.

### IN-08: Orphaned and unpruned translator folders

**File:** `porter/pipeline.py:341-343`
**Issue:** The pre-02-12 `<user dir>/tools/dmsh_xlate/` folder and `dmsh_xlate.key` are now never used or removed. Each new key leaves one more `dmsh_xlate-<k>/` folder plus its `.key`, which the code comment acknowledges as a shortcut.
**Fix:** Remove the old `dmsh_xlate`/`dmsh_xlate.key` once, under the tools lock. Pruning other keys can wait until ports record which translator they use, as the shortcut comment says.

### IN-09: `test_waiting_port_reuses_translator` depends on a 0.5 s window

**File:** `tests/test_lock.py:48`, `tests/test_lock.py:107-113`
**Issue:** The holder builds 0.5 s after the go file appears. If the test process stalls longer than that between `fp()` and the first reuse check (a loaded CI runner), the first check succeeds, `ran` is `[]`, and `assertEqual(ran, ['restore'])` fails. That is a false failure, not a false pass. `ran` is also never asserted in `test_new_translator_key_keeps_old`, and the `mkdtemp` folders the tests create are never removed.
**Fix:** Have the holder build only after a second go file, which the test's `nuget.check` stub touches. That point is reached only after the lock has been taken, so the first check is guaranteed to fail first. In the other test, drop `ran` or assert it equals `['restore', 'build', 'restore', 'build']`.

---

_Reviewed: 2026-10-30T20:23:52Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
