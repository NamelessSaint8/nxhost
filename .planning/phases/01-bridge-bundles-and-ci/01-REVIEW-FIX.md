---
phase: 01-bridge-bundles-and-ci
fixed_at: 2026-10-30T15:10:37Z
review_path: .planning/phases/01-bridge-bundles-and-ci/01-REVIEW.md
iteration: 1
findings_in_scope: 3
fixed: 3
skipped: 0
status: all_fixed
---

# Phase 01: Code Review Fix Report

**Fixed at:** 2026-10-30
**Source review:** .planning/phases/01-bridge-bundles-and-ci/01-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 3 (WR-01, WR-02, WR-03; Info findings out of scope)
- Fixed: 3
- Skipped: 0

## Fixed Issues

### WR-01: The CA-file fallback can run on Windows, where `/etc/ssl/...` resolves against the current drive

**Files modified:** `porter/tls.py`, `tests/test_tls.py`
**Commit:** d4f5a2e
**Applied fix:** `context()` now returns the default context when `os.name == 'nt'`, before it looks at any CA file, so on Windows it never reads a path relative to the current drive. The new test `test_windows_reads_no_host_file` patches `tls.os.name` to `'nt'` and uses the empty default context. It checks that `isfile` is never called and that no CA was loaded.

### WR-02: The urlopen scan test accepts any `context=`, not `context=tls.context()`

**Files modified:** `tests/test_tls.py`
**Commit:** f53bacd
**Applied fix:** `test_every_urlopen_passes_the_context` now walks the `ast` of every `porter/*.py` file instead of scanning line by line. Every `Call` whose function ends in `urlopen` must have the keyword `context` with the value `tls.context()`. A call wrapped over several lines is still counted, and `context=None` or an unverified context now fails the test. Negative check: changing `fetch.py:89` to `context=ssl._create_unverified_context()` failed the test with `['porter/fetch.py:89']`, and the file was then reverted. The unused `re` import was removed.

### WR-03: The hook overrides are copies of PyInstaller 6.22.3's hooks, with nothing that fails when PyInstaller moves

**Files modified:** `packaging/nx2android.spec`
**Commit:** e05bb64
**Applied fix:** I added a single guard to the spec, just before `Analysis`. It is not in each hook and there is no new test. The guard runs `sys.exit('[RED] ...')`, in the same style as the GTK guard below it, whenever `PyInstaller.__version__ != '6.22.3'`, and the message says to copy both stock hooks again, keep the filter lines, and then change the version. If `uv pip compile` moves the build to 6.22.4 or later, the bundle build now stops instead of silently keeping the old hook logic. I ran the guard lines against `.venv`'s PyInstaller 6.22.3 and they pass.

## Verification

- All checks ran in the main checkout's `.venv` after the fast-forward. The fixes were made and committed in an isolated worktree (`.claude/worktrees/rf-01-24077-*`, since removed), and `main` was fast-forwarded to e05bb64.
- `tests.test_tls`: 6 tests OK, run after each of WR-01 and WR-02.
- WR-03: `ast.parse` on the spec, and the guard lines run under PyInstaller 6.22.3: they pass. No full bundle build was run.
- Full suite `QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover tests`: 115 tests, OK.
- All three commit messages pass `.githooks/commit_msg.py`.

---

_Fixed: 2026-10-30_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
