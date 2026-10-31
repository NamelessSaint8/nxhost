---
phase: 02-porter-hardening
reviewed: 2026-10-31T02:06:39Z
depth: standard
files_reviewed: 5
files_reviewed_list:
  - devtools/zip_links.py
  - docs/ARCHITECTURE.md
  - porter/fetch.py
  - tests/fixtures/zip_links.json
  - tests/test_fetch.py
findings:
  critical: 0
  warning: 9
  info: 13
  total: 22
status: issues_found
---

# Phase 02: Code Review Report

**Reviewed:** 2026-10-31T02:06:39Z
**Depth:** standard
**Files Reviewed:** 5
**Status:** issues_found

## Summary

Scope is plan 02-13's diff from `0cad9c6`: the in-memory link rule (`_parts`, `_top`, `_link_refusal`), the `_unzip`/`_untar` changes that return the folder to install, the move-aside swap in `_install`, the fixture generator `devtools/zip_links.py`, its fixture, and the tests.

I checked whether the link rule can be escaped. I traced `_link_refusal` by hand, then ran it against the real filesystem. Over 40,000 random archives (two seeds, links mixed with files, `..`/`.` and mixed-case parts, with and without a top folder), none passed the rule while a link resolved outside the installed folder on disk (macOS APFS, case-insensitive). The CR-01, CR-04 and IN-06 shapes are closed. `tests.test_fetch` passes (28 tests).

02-13 resolves CR-04, WR-05 and IN-06 (see "Resolved in this round"). This round adds no blockers and has nine new findings: WR-07 to WR-10 and IN-10 to IN-14. The four new warnings:
- WR-07: a claimed invariant ("no member is written through a link") breaks on APFS for names that differ only by Unicode normalization.
- WR-08: the Windows file-in-use case, which the WR-05 swap was built for, still ends in a raw traceback.
- WR-09: the offline fixture test is weaker than its name says.
- WR-10: the fixture generator never checks it read the pinned file.

Thirteen earlier findings in files 02-13 did not touch are carried forward unchanged. Since the diff base `0cad9c6`, `git diff` shows no change to `porter/cli.py`, `porter/pipeline.py`, `porter/datapack.py`, `porter/nuget.py`, `gui/app.py`, `mkapk.py`, `tests/test_lock.py` or `.claude/CLAUDE.md`. WR-04 is in `porter/fetch.py`, and `_google_os`/`_pinned` there are unchanged.

## Narrative Findings (AI reviewer)

## Resolved in this round

### CR-04: Links are checked against the unpack folder, but a different tree is installed, so a link can leave the installed toolchain (resolved by 02-13)

**Resolved:** `_link_refusal` (`porter/fetch.py:140-171`) now resolves every link in memory from the installed root: `_top` names the folder, and `_unzip`/`_untar` return `into / top`, which `_install` moves. So `top/up -> ../adb` and `platform-tools/z -> ..` are refused (`test_link_to_sibling_refused`, `test_link_above_root_refused`, `test_relocated_link_refused`, `test_rooted_at_installed_folder`). These tests pass, and the 40,000-archive fuzz above found no escape.

### WR-05: Replacing an existing toolchain is not atomic (resolved by 02-13)

**Resolved:** `_install` (`porter/fetch.py:207-220`) now renames `dest` to `.<folder>.old`. It moves the new tree in, puts the old copy back if that move fails, and restores a swap that was cut off on the next run. `test_failed_move_keeps_old_toolchain` and `test_cut_off_move_restored` cover this. The raw error the player sees on that failure path is tracked separately as WR-08.

### IN-06: Some hostile zips are refused with a raw OS error instead of the `refused` message (resolved by 02-13)

**Resolved:** link loops are now refused by the 40-hop cap, a link that shares a folder's name by the `count` check, and a link under a link by the `under` check. All three raise `BuildError` before anything is written (`porter/fetch.py:144-167`; `test_link_loop_refused`, `test_link_beside_folder_refused`, `test_link_under_link_refused`). One residual raw `FileExistsError`, for names that alias only after APFS normalization, is tracked as WR-07.

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

### WR-06: Moving the old data pack aside has no Windows retry, unlike `swap_in` (carried forward)

**File:** `porter/datapack.py:66`
**Issue:** `dst.rename(old)` has no retry for a scanner or indexer that holds files in the pack, which `swap_in` handles with up to 15 s of retries.
**Fix:** Reuse `swap_in`'s retry loop around `dst.rename(old)`.

### WR-07: Normalization aliases on APFS bypass the "no member under a link" check

**File:** `porter/fetch.py:148-154`
**Issue:** `full()` only casefolds names. APFS is also normalization-insensitive, and some characters have a one-character canonical decomposition to ASCII. I confirmed this on this Mac: after `mkdir 'a;b'` (U+037E GREEK QUESTION MARK), `os.path.exists('a;b')` is True. The rule requires ASCII only for link names and targets, not for other members. So `_link_refusal(['a;b/x', 'a;b'], {'a;b': '.'}, '')` returns `None`, but on disk `a;b/x` is a member under link `a;b`.
- In a zip, the link is made last and `os.symlink` raises a raw `FileExistsError` instead of porter's refusal.
- In a tar, members are written in archive order, so a member can be written through the link. That breaks the guarantee in the line-152 comment and in ARCHITECTURE.md. It can't escape: the link target is still resolved inside, and `filter='data'` checks each member. But the invariant the comments rely on does not hold.

Other aliases: U+1FEF → `` ` ``, and U+212A (KELVIN SIGN) → `K`, which casefold happens to catch.
**Fix:** Normalize before casefolding, so the comparison matches what APFS does:
```python
import unicodedata
full = lambda m: unicodedata.normalize('NFD', '/'.join(_parts(m))).casefold()
```
Alternatively, refuse any non-ASCII member name in an archive that has links. Add the `a;b` case to `test_refusals`.

### WR-08: The WR-05 failure (a toolchain file in use on Windows) still ends in a raw traceback

**File:** `porter/fetch.py:213-218`
**Issue:** The swap was built for one case: a file is in use on Windows, so the rename fails. In that case `dest.replace(old)` or `src.replace(dest)` raises a bare `PermissionError`/`OSError`. Nothing converts it to `BuildError`, so `cli._with_progress` hits `except Exception: ... raise` and the player sees a traceback, or `[RED] PermissionError: [WinError 5] ...` in JSON mode. They are not told what to do. That breaks the project rule that user-facing errors name the file and the fix. `test_failed_move_keeps_old_toolchain` (test_fetch.py:223) asserts the raw `OSError`, so the tests lock this behaviour in.
**Fix:**
```python
try:
    src = (_unzip if arc.suffix == '.zip' else _untar)(arc, tmp, it.folder)
    try: dest.exists() and dest.replace(old)
    except OSError as e: raise BuildError(f'{dest} is in use: close the program using it (adb, a build, an editor) and try again') from e
    try: src.replace(dest)
    except BaseException as e:
        if old.exists(): old.replace(dest)
        if isinstance(e, OSError): raise BuildError(f'cannot move the new {it.name} into {dest} ({e}): close what uses it and try again') from e
        raise
```
Then change the test to expect `BuildError`.

### WR-09: `test_pinned_archives_pass` runs the rule on link names only, not the real member list

**File:** `tests/test_fetch.py:285`, `tests/fixtures/zip_links.json`
**Issue:** The test calls `_link_refusal(list(e['links']), e['links'], e['top'])`, so `names` holds only the links. The `count` (duplicate-name) and `under` (member under a link) checks only ever see links, never the 9,000-odd real NDK members. `top` is read from the fixture, not recomputed by `_top`. The header of `zip_links.py` says the full member list is checked, and that is true when the generator runs. Offline, though, a regression in `_top`, `count` or `under` that refused (or wrongly passed) a real NDK layout would go unnoticed. The fixture's `members` count and `url` are written but never read.
**Fix:** Have `zip_links.py` record the member names. A compact form is enough: the casefolded set of every link name's prefixes plus every directory that holds a link. Then the test can call `_link_refusal(e['names'], e['links'], fetch._top(e['names'], folder))` and assert that the computed top equals `e['top']`. At minimum, assert `fetch._top` on the recorded names.

### WR-10: `zip_links.py` never checks that it read the pinned file

**File:** `devtools/zip_links.py:18-19, 42, 51`
**Issue:** The fixture stores each link table under the pinned `hash`, and the test treats a matching hash as proof that "the pinned archive passes". But the generator reads only the central directory and the link members over Range requests. It never confirms those bytes belong to the file with that hash. The pinned `size` is unpacked on line 42 and never used. If the vendor or a CDN served a different file at the same URL, its link table would be recorded as the pinned archive's.
**Fix:** Compare the server's size with the pin (the NDK and platform-tools pins give exact sizes). Optionally also check the `Content-Range` total on each 206 response:
```python
for url, size, algo, h in pin['files'].values():
    if not url.endswith('.zip'): continue
    r = Remote(url)
    if size and r.size != size: sys.exit(f'{url}: {r.size} bytes, the pin says {size}: not the pinned file')
    with zipfile.ZipFile(io.BufferedReader(r, 1 << 16)) as z: ...
```

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

### IN-07: The second reuse check runs after the restore and the NuGet check, not right after the lock (carried forward)

**File:** `porter/pipeline.py:345-346`, `porter/nuget.py:36-40`
**Issue:** A port that waited for the tools lock and only needs to reuse the translator still runs `dotnet restore` and `nuget.check` before it re-checks. If that restore fails, for example on a network or feed error during a non-no-op restore, the port fails even though a usable translator is already built.
**Fix:** Give `restored()` an optional `ready` callable that is checked right after `lock.take`, and skip the restore when it returns true. Alternatively, take the lock in `translator()` itself and call `restored` only for a rebuild.

### IN-08: Orphaned and unpruned translator folders (carried forward)

**File:** `porter/pipeline.py:341-343`
**Issue:** The pre-02-12 `<user dir>/tools/dmsh_xlate/` folder and `dmsh_xlate.key` are now never used or removed. Each new key leaves one more `dmsh_xlate-<k>/` folder plus its `.key`, which the code comment acknowledges as a shortcut.
**Fix:** Remove the old `dmsh_xlate`/`dmsh_xlate.key` once, under the tools lock. Pruning other keys can wait until ports record which translator they use, as the shortcut comment says.

### IN-09: `test_waiting_port_reuses_translator` depends on a 0.5 s window (carried forward)

**File:** `tests/test_lock.py:48`, `tests/test_lock.py:107-113`
**Issue:** The holder builds 0.5 s after the go file appears. If the test process stalls longer than that between `fp()` and the first reuse check (a loaded CI runner), the first check succeeds, `ran` is `[]`, and `assertEqual(ran, ['restore'])` fails. That is a false failure, not a false pass. `ran` is also never asserted in `test_new_translator_key_keeps_old`, and the `mkdtemp` folders the tests create are never removed.
**Fix:** Have the holder build only after a second go file, which the test's `nuget.check` stub touches. That point is reached only after the lock has been taken, so the first check is guaranteed to fail first. In the other test, drop `ran` or assert it equals `['restore', 'build', 'restore', 'build']`.

### IN-10: The link-table read is duplicated between the installer and the fixture generator

**File:** `porter/fetch.py:178`, `devtools/zip_links.py:47`
**Issue:** The same one-line link-table read (`stat.S_ISLNK(i.external_attr >> 16)` with `decode('utf-8', 'replace')`) appears in both files. If one changes and the other doesn't, the fixture generator no longer reads links the way the installer does, and the fixture stops showing what porter would do.
**Fix:** Add `def _zip_links(z, infos)` to `fetch.py` and call it from both places.

### IN-11: The 40-hop cap is Linux's; macOS's MAXSYMLINKS is 32

**File:** `porter/fetch.py:165-167`
**Issue:** The rule accepts chains of 33 to 40 links. These are ELOOP on macOS, and the cap test at `test_fetch.py:265` asserts a chain of 41 links passes, which the kernel rejects on both OSes. This is not an escape, only an unusable link that the comment calls Linux-correct.
**Fix:** Use 32 (the stricter host), or note in the comment that the cap only catches loops.

### IN-12: ARCHITECTURE.md says "files first, links last" for tar too

**File:** `docs/ARCHITECTURE.md:104`
**Issue:** Only `_unzip` writes links last. `tarfile.extractall` writes members in archive order. Tar is safe because of the `under`/`count` checks and `filter='data'`, not because of the order.
**Fix:** "zip files are written first and links last; tar relies on the same member-under-link refusal and `filter='data'`".

### IN-13: Two link-escape tests are still skipped on Windows, though the rule now runs there

**File:** `tests/test_fetch.py:165, 170`
**Issue:** `test_escaping_links_refused` and `test_link_through_later_link_refused` keep `skipIf(os.name == 'nt')`. `_link_refusal` now refuses these archives on every OS before anything is written, as the CR-04 tests below them show. Windows CI loses that coverage for no reason.
**Fix:** Drop both `skipIf` decorators.

### IN-14: `Remote.readinto` assumes the server returned exactly the requested range

**File:** `devtools/zip_links.py:34-36`
**Issue:** The code checks the 206 status but not `Content-Range`. A longer body makes `b[:len(data)] = data` raise a bare `ValueError`. A short body is silently treated as a short read.
**Fix:** Check `r.headers['Content-Range'].startswith(f'bytes {self.pos}-{end}/')` and that `len(data) == end - self.pos + 1`, and exit with the URL on a mismatch.

---

_Reviewed: 2026-10-31T02:06:39Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
