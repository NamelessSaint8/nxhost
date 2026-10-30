---
phase: 02-porter-hardening
reviewed: 2026-10-30T12:00:00Z
depth: standard
files_reviewed: 32
files_reviewed_list:
  - devtools/hooks.py
  - devtools/nuget_pins.py
  - gui/app.py
  - nxnative/dm/android/apk/mkapk.py
  - nxnative/scripts/build_ipa_from_nsp.py
  - porter/adb.py
  - porter/cli.py
  - porter/datapack.py
  - porter/fetch.py
  - porter/fpslocker.py
  - porter/lock.py
  - porter/nuget.py
  - porter/pins.py
  - porter/pipeline.py
  - porter/runlog.py
  - porter/toolchain.py
  - porter/upstream.py
  - probes/app/probeapp.c
  - tests/arch_rules.py
  - tests/test_adb.py
  - tests/test_bridge.py
  - tests/test_cli.py
  - tests/test_datapack.py
  - tests/test_fetch.py
  - tests/test_housekeeping.py
  - tests/test_lock.py
  - tests/test_nuget.py
  - tests/test_porter.py
  - tests/test_runlog.py
  - tests/test_signing.py
  - tests/test_stages.py
  - tests/test_toolchain.py
findings:
  critical: 3
  warning: 6
  info: 5
  total: 14
status: issues_found
---

# Phase 02: Code Review Report

**Reviewed:** 2026-10-30T12:00:00Z
**Depth:** standard
**Files Reviewed:** 32
**Status:** issues_found

## Summary

I reviewed the diff from `74523e2..HEAD` across the 32 listed files, reading the code around each change. That covered the OS file locks, the data-pack swap, the signing-key write, pinned downloads with zip/tar unpacking, the Python floor, the per-child env, the whole-file stage keys, the FPSLocker pin, the NuGet hash check and the GUI escaping. The 141 unit tests in the phase's test modules pass on macOS.

There are three blockers:
- The zip symlink guard can be bypassed by the order the links come in. I reproduced this with a three-entry zip.
- On Windows, the lock's "who holds it" read probably runs into the locked byte. If so, the second porter crashes instead of reporting the holder or waiting. This is from reading the code; it was not run on Windows.
- The shared translator build checks whether it can reuse the last build before it takes the tools lock, and never checks again after. A port that waited then rebuilds and deletes the translator another port is using.

The warnings cover a recover-before-lock race in `porter install`, a tools lock held for a whole survey, hard-link-only key publishing, x86-64 pins served as "tested" to Linux arm64, and toolchain/pack replacements that are not atomic on Windows.

## Critical Issues

### CR-01: Zip symlink check depends on link order; a later link turns an accepted link into an escape

**File:** `porter/fetch.py:141-146`
**Issue:** Each link is checked against the filesystem as it stands when that link is created. A link whose path runs through a component that does not exist yet is resolved lexically, and it passes. A later link can then create that component pointing back at the unpack root. The first link then escapes. Reproduced against `fetch._unzip` with three entries: a file `d1/d2/keep.txt`, then `a -> d1/d2/b/../../../escaped`, then `d1/d2/b -> ../..`. Result: `a` resolves to the parent of the unpack folder's parent, `is_relative_to(root)` is False, and no error is raised. The escape depth is arbitrary (one level per `..` behind the planted link). The archive does have to pass the pinned hash, or on the untested fallback the vendor's listed hash. But this guard exists for exactly the hostile-archive case, and it does not hold.
**Fix:** Validate after all links exist, when the tree is final, and remove everything on failure (`_install` already removes `tmp` on any exception):
```python
for info in filter(link, infos):
    t, target = into / info.filename, z.read(info).decode()
    if target.startswith('/') or '\\' in target: raise BuildError(...)
    t.parent.mkdir(parents=True, exist_ok=True); t.unlink(missing_ok=True); os.symlink(target, t)
for info in filter(link, infos):   # final tree: every link resolved with every other link in place
    if not (into / info.filename).resolve().is_relative_to(root):
        raise BuildError(f'{arc.name}: refused, link {info.filename} leaves the unpack folder')
```
Add the three-entry zip above to `tests/test_fetch.py`.

### CR-02: Windows lock holder lookup reads into the locked byte; the second porter crashes, and `wait=True` never waits

**File:** `porter/lock.py:31` (with `AT = 4096`, line 9)
**Issue:** `f` is a buffered `a+b` file. `f.read(AT)` asks for 4096 bytes, but CPython's `BufferedReader` fills its internal buffer with a raw read of `buffer_size` bytes (8 KiB, or more on newer versions) from offset 0. That raw `ReadFile` overlaps the holder's mandatory lock on byte 4096. Windows fails a read that overlaps another process's exclusive range (`ERROR_LOCK_VIOLATION`, which Python raises as `PermissionError`). The `OSError` is raised inside the `except OSError` handler, so it escapes `take()` as a raw traceback:
- with `wait=False`, the user sees a crash instead of "already running: ... PID ...";
- with `wait=True` (the shared tools lock in `porter/nuget.py:37`), the second port dies instead of waiting. That defeats the tools lock on the only platform the bundle ships for today.

This was not run on Windows (the file's own comment assumes the read stays below the lock). The tests that would show it, such as `tests/test_lock.py` `test_second_take_names_holder`, have only run on POSIX.
**Fix:** Read the holder text with an unbuffered read that cannot pass `AT`, and never let the lookup itself fail:
```python
try: os.lseek(f.fileno(), 0, os.SEEK_SET); who = os.read(f.fileno(), AT).decode('utf-8', errors='replace').strip() or 'another porter'
except OSError: who = 'another porter'
```
Alternatively, open the lock file with `buffering=0`. Run `tests/test_lock.py` on a Windows runner before calling D-06/D-07 done.

### CR-03: Translator reuse check is outside the tools lock and is not repeated inside it; a waiting port rebuilds and deletes the translator another port is using

**File:** `porter/pipeline.py:343-349`
**Issue:** `if dll.is_file() and nsp.reused(kf, key) is not None: return dll, key` runs before `nuget.restored(...)` takes the tools lock. Take two ports that start with a stale or missing key, for example the first ports after an engine update (the scenario Pitfall 6 describes). Port A builds while port B waits. When B gets the lock, it never checks reuse again. It unconditionally does `rmtree(kf)`, rebuilds, and calls `swap_in(tmp, out)`, which `rmtree`s `<user dir>/tools/dmsh_xlate`. Port A may by then be in its Vulkan shaders stage, running `shader_vk.py --xlate <out>/dmsh_xlate.dll`.
- On POSIX, A's translator runs can find the dll or its dependencies missing mid-swap.
- On Windows, B's `rmtree(out)` fails part-way on the dll A has loaded. Some files are deleted, the key is gone, and both ports can be left broken.
**Fix:** Check reuse again once the lock is held, and only rebuild if it still fails:
```python
if dll.is_file() and nsp.reused(kf, key) is not None: return dll, key
with nuget.restored(src, self.tools['dotnet'], self.env, self.logs / 'nuget_restore_translator.log'):
    if dll.is_file() and nsp.reused(kf, key) is not None: return dll, key   # another port built it while this one waited
    tmp = out.with_name('dmsh_xlate.partial'); ...
```
This still leaves a rebuild with a genuinely different key able to remove a dll that a concurrent port is using. Either hold the tools lock for shared reads too (lock with `wait=True` around the shaders stage's use of the dll), or build into a key-named folder (`dmsh_xlate-<key[:12]>`) and never delete it while in use.

## Warnings

### WR-01: `porter install` recovers the pack before taking the port's lock

**File:** `porter/cli.py:113-114`
**Issue:** `datapack.recover(data)` runs before `lock.take(b, 'install')`. A port that is mid-swap has `dst` renamed to `.old` and is about to call `swap_in(tmp, dst)`. On Windows that window is up to 15 s while `swap_in` retries for a virus scanner. If `install` runs then, its `recover` renames `.old` back into `dst`. The port's `tmp.rename(dst)` then fails (dst exists), so the port fails at the data stage. `install` then fails too, on the lock it only takes afterwards.
**Fix:** Take the lock first, then recover (the sidecar `<pack>.build` is beside the pack, so `build_dir(data)` does not need the pack to be in place):
```python
b = datapack.build_dir(data); held = lock.take(b, 'install') if b and b.is_dir() else None
datapack.recover(data)
```

### WR-02: The tools lock is held for a whole survey, not just the nx_extract build

**File:** `porter/pipeline.py:192-193`
**Issue:** `with nuget.restored(...): facts = nsp.survey(...)` holds `<user dir>/tools/.porter.lock` while survey builds nx_extract, extracts the code modules and RomFS manifest, and reads them. That can take minutes. Every other game's port waits at its own `build nx_extract` or translator stage for the whole time, with only "waiting for porter tool build" to show for it.
**Fix:** Build nx_extract under the lock and run the survey without it. For example, pass a prebuilt `nx` to survey, or wrap only `nsp.build_nx_extract` through a small override in `porter/upstream.py._overrides`, so `survey()`'s internal `build_nx_extract` call takes the lock itself.

### WR-03: The signing key is published only through `os.link`; a folder without hard links can never get a key

**File:** `nxnative/dm/android/apk/mkapk.py:199-201`
**Issue:** Only `FileExistsError` is handled. On FAT32/exFAT, which is possible via `NX2A_HOME` on a USB drive, and on some SMB/network homes, `os.link` raises `PermissionError` or `OSError(EPERM/ENOTSUP)`. The `finally` removes the temp file and the APK stage dies with a traceback. Every later port repeats this, so no port on that setup can ever be signed.
**Fix:** Fall back to a no-overwrite rename when hard links are unsupported:
```python
try: os.link(tmp, keyf)
except FileExistsError: return False
except OSError:
    if os.path.exists(keyf): return False
    os.rename(tmp, keyf)   # Windows: fails if keyf appeared; POSIX: a lost race here is the narrow window the link closed
return True
```

### WR-04: Linux arm64 gets the x86-64 NDK and platform-tools as "pinned", not flagged untested

**File:** `porter/fetch.py:79-83`, `porter/pins.py` NDK/PLATFORM_TOOLS `'linux'` rows
**Issue:** `_google_os()` returns `'linux'` on every Linux CPU, so `_pinned()` returns the x86-64 linux rows on an aarch64 host. `plan()` presents them as the pinned, tested files. `download()` then installs binaries that cannot run, and the player only finds out from the "downloaded, but the check still fails" error after a ~660 MB download. Linux arm64 is a stated target host.
**Fix:** In `_pinned` (and `_google`), return `None` / refuse for `Android NDK` and `adb` when `sys.platform.startswith('linux') and platform.machine().lower() in ('aarch64', 'arm64')`. Point the player at distro adb and the community NDK (Phase 3), rather than downloading x86-64 binaries.

### WR-05: Replacing an existing toolchain is not atomic; a failed replace leaves a half-deleted NDK/.NET

**File:** `porter/fetch.py:166`
**Issue:** `shutil.rmtree(dest, ignore_errors=True); src.replace(dest)`. On Windows, a `dotnet.exe`, `adb.exe` (the adb server keeps running) or NDK file that is in use survives `rmtree`, and the errors are ignored. `src.replace(dest)` then fails because `dest` is not empty. The new `except BaseException` cleans up `tmp` and re-raises, but the old toolchain is already partly deleted, and `config` still points at it. That is the "half-done swap" this phase set out to remove elsewhere.
**Fix:** Move the old toolchain aside first, as `datapack.build` now does: `if dest.exists(): dest.rename(aside)`, then `src.replace(dest)`, then `rmtree(aside, ignore_errors=True)`. On failure, rename `aside` back. The rename itself fails cleanly while files are in use, which leaves the old toolchain intact.

### WR-06: Moving the old data pack aside has no Windows retry, unlike `swap_in`

**File:** `porter/datapack.py:66`
**Issue:** `dst.rename(old)` renames a large directory that a virus scanner, Explorer or the indexer may hold briefly. That is the same `[WinError 5]` that `swap_in` retries for 15 s, but here there is no retry. The data stage fails at the end of a 20-minute port.
**Fix:** Reuse the retry. For example, factor `swap_in`'s loop into a `rename_retry(a, b)` helper in the upstream script, or loop locally `for i in range(30 if os.name == 'nt' else 0)` around `dst.rename(old)`.

## Info

### IN-01: The status badge text is the one game-card string left unescaped

**File:** `gui/app.py:132`
**Issue:** `{st}` (`android.tsv` `status`, or the profile/inspect fallback) is placed in rich text without going through `e()`. Today `arch_rules` restricts the values, but an experimental or derived profile under the build folder is not checked by `arch_rules`.
**Fix:** `&nbsp;{e(st)}&nbsp;`.

### IN-02: A failed inspect keeps the previous game's language list

**File:** `gui/app.py:123-125`
**Issue:** The `fail` return happens before the combo is reset. After switching from game A to a broken folder B, A's languages stay selectable for the next inspect.
**Fix:** Reset the combo to the default entry before the `if fail:` return.

### IN-03: The NuGet check assumes the first package folder

**File:** `porter/nuget.py:15`
**Issue:** If NuGet resolves a package from a fallback folder (for example the Visual Studio offline folder on Windows), that package's real folder is not `packageFolders[0] / path`. On a mismatch, `rmtree` deletes nothing, and the bad package is restored again from the fallback every run.
**Fix:** Look the package up in every `packageFolders` key, or set `RestoreFallbackFolders=` (clear) via env/`-p:` on the restore so NUGET_PACKAGES is the only source.

### IN-04: Two game folders of the same title, sharing one output folder, race on the pack's `.partial`

**File:** `porter/datapack.py:47-49`
**Issue:** The lock is per build folder, but `<out>/<stem>-data.partial` is per output folder. Two copies of one game that both output to the configured `out` `rmtree` each other's partial pack.
**Fix:** Document it, or also lock `<out>/<stem>-data.build` with `lock.take`.

### IN-05: Stale reference to the deleted probe packer

**File:** `.claude/CLAUDE.md:351`
**Issue:** It still lists `probes/app/mkapk.py`, which this phase deleted (the probe now uses `nxnative/dm/android/apk/mkapk.py`, as `probes/app/probeapp.c` says).
**Fix:** Update the line.

---

_Reviewed: 2026-10-30T12:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
