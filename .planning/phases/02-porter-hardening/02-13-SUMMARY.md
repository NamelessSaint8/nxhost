---
phase: 02-porter-hardening
plan: 13
subsystem: porter
tags: [zip, tar, symlinks, toolchain-download, hardening, tdd]
requires:
  - phase: 02-porter-hardening
    provides: "02-04 and 02-11's unpack checks (_bad_name, _refuse_names, links last, data filter)"
provides:
  - "fetch._parts, fetch._top, fetch._link_refusal: one pure in-memory link rule rooted at the installed folder"
  - "_unzip/_untar(arc, into, folder) return the folder to install; _install moves exactly that"
  - "WR-05: installed toolchain moved aside to .<folder>.old and restored on failure or after a cut-off move"
  - "devtools/zip_links.py and tests/fixtures/zip_links.json: the pinned zips' link tables"
affects: [porter-hardening, setup-downloads, ci]
actuals:
  tokens: 9700
  tasks: 3
  commits: 5
plan_head_before: 001101939025d8db90e0a1deeb2142bdf5972995
plan_head_after: e7a68745227a538438ac92d4434a3b23ba0f8d61
tech-stack:
  added: []
  patterns:
    - "Decide archive safety from the member list before writing; never from the disk"
    - "Aside-rename swap (.<name>.old) with restore, as datapack.py does"
key-files:
  created:
    - devtools/zip_links.py
    - tests/fixtures/zip_links.json
  modified:
    - porter/fetch.py
    - tests/test_fetch.py
    - docs/ARCHITECTURE.md
    - .planning/codebase/CONCERNS.md
key-decisions:
  - "Links are resolved in memory from the folder that is installed (archive root less _top), so the check and the install share one root (CR-04)"
  - "Link resolution caps at 40 substitutions (Linux MAXSYMLINKS), so loops are a BuildError on every Python (IN-06)"
  - "Link names and targets must be printable ASCII; case-variant link names, duplicate names and members under a link are refused (case-insensitive APFS)"
  - "The rule runs on Windows too; Windows still writes a link member as a plain file"
requirements-completed: [HARD-01, TEST-01]
coverage:
  - id: D1
    description: "A link that leaves the installed toolchain (CR-04 one and two archives, relocation, loops, IN-06 shapes) is refused before anything is written"
    requirement: HARD-01
    verification:
      - kind: unit
        ref: "tests/test_fetch.py#Unpack.test_link_to_sibling_refused, test_link_above_root_refused, test_relocated_link_refused, test_link_loop_refused, test_link_beside_folder_refused, test_link_under_link_refused"
        status: pass
      - kind: unit
        ref: "tests/test_fetch.py#LinkRule.test_refusals, test_rooted_at_installed_folder, test_top"
        status: pass
    human_judgment: false
  - id: D2
    description: "Legitimate NDK link layouts still install as links"
    requirement: TEST-01
    verification:
      - kind: unit
        ref: "tests/test_fetch.py#Unpack.test_internal_links_kept, test_valid_zip_kept; LinkRule.test_inside_passes"
        status: pass
    human_judgment: false
  - id: D3
    description: "Every pinned zip passes the rule, checked offline from a committed fixture"
    requirement: TEST-01
    verification:
      - kind: unit
        ref: "tests/test_fetch.py#LinkRule.test_pinned_archives_pass, test_real_links_one_level_up_refused"
        status: pass
      - kind: other
        ref: "python3 devtools/zip_links.py (all seven ok)"
        status: pass
    human_judgment: false
  - id: D4
    description: "Replacing an installed toolchain never leaves the player without one (WR-05)"
    requirement: HARD-01
    verification:
      - kind: unit
        ref: "tests/test_fetch.py#Unpack.test_failed_move_keeps_old_toolchain, test_cut_off_move_restored"
        status: pass
    human_judgment: false
  - id: D5
    description: "The same tests pass on the Windows, Linux and Python 3.11 CI jobs"
    verification: []
    human_judgment: true
    rationale: "Only run on macOS Python 3.14.5 locally; fork-ci.yml's windows-2025, ubuntu and 3.11 jobs have not run on these commits"
duration: 7min
completed: 2026-10-31
status: complete
---

# Phase 2 Plan 13: Links decided in memory from the installed folder Summary

**One pure rule, `fetch._link_refusal`, resolves every zip and tar link from the archive's member list, rooted at the same top folder `_install` moves into place, before anything is written. That closes CR-04 and IN-06. WR-05 is fixed with an aside rename and restore. All seven pinned zips pass, proven offline by a committed link-table fixture.**

## Performance

- **Duration:** about 7 min
- **Started:** 2026-10-31T01:50:07Z
- **Completed:** 2026-10-31T01:57Z
- **Tasks:** 3
- **Files modified:** 6 (2 created)

## Accomplishments
- CR-04 closed by construction. `_top(names, folder)` names the one folder that is installed. `_unzip`/`_untar` check links against that root through `_link_refusal` and return `into / top`. `_install` moves exactly that path and no longer lists the unpack folder.
- IN-06 closed: loops (pair and self), a link with a member under it, and a link under another link are refused with porter's own BuildError. Before, Python raised RuntimeError or an OSError, or let them through.
- WR-05 closed: the old toolchain is renamed to `.<folder>.old` and restored if the move in fails. The next install also restores it after a cut-off swap.
- The real pinned archives are proven to pass: `devtools/zip_links.py` range-reads the full member lists. `tests/fixtures/zip_links.json` holds the 58 real links, and `LinkRule.test_pinned_archives_pass` checks them offline.

## Task Commits

1. **Task 1 RED: crafted zips whose links leave the installed toolchain** - `790e470` (test)
2. **Task 1 GREEN: decide zip and tar links in memory from the folder that is installed** - `a5e1836` (fix)
3. **Task 2: pinned zips' link tables pass the link rule offline** - `3ed0e99` (test)
4. **Task 3 RED: a failed toolchain replace keeps the installed one** - `c814d94` (test)
5. **Task 3 GREEN: move an installed toolchain aside until its replacement is in** - `e7a6874` (fix)

## Files Created/Modified
- `porter/fetch.py`: `_parts`, `_top`, `_link_refusal`. `_unzip`/`_untar` now take `folder` and return the install root. In `_install`, the aside swap replaces the delete-then-replace.
- `tests/test_fetch.py`: 9 new Unpack tests and a new `LinkRule` class with 6 tests.
- `devtools/zip_links.py`: `Remote` (seekable RawIOBase over HTTP Range, refuses any answer that is not 206) and `main()`, which writes the fixture.
- `tests/fixtures/zip_links.json`: link tables of the 7 pinned zips, with their pinned hashes.
- `docs/ARCHITECTURE.md`: the unpack sentence on line 104.
- `.planning/codebase/CONCERNS.md`: the zip-symlink closure row.

## TDD Gate Compliance

RED evidence was recorded per test and classified with `gsd-tools check tdd-red-evidence`; each returned `RED_EVIDENCE_OK` (`target_test_failed`). Each run was `python3 -m unittest tests.test_fetch.Unpack.<test>` on Python 3.14.5 against the unchanged `porter/fetch.py`.

| Test | Failure at RED |
|------|----------------|
| test_link_to_sibling_refused | `AssertionError: BuildError not raised` |
| test_link_above_root_refused | `AssertionError: BuildError not raised` |
| test_relocated_link_refused | `AssertionError: BuildError not raised` |
| test_link_loop_refused | `AssertionError: BuildError not raised` in both subTests [pair] and [self] |
| test_link_beside_folder_refused | ERROR `PermissionError: [Errno 1] Operation not permitted: '.../toolchains/.x.unpack/d'` |
| test_link_under_link_refused | ERROR `FileExistsError: [Errno 17] File exists: '.../toolchains/.x.unpack/a'` |
| test_internal_links_kept (guard) | passed at RED, as planned |
| test_failed_move_keeps_old_toolchain | `AssertionError: False is not true` at line 224, `(dest / 'old.txt').is_file()` after the failed move |
| test_cut_off_move_restored | `AssertionError: False is not true` at line 232, `(root / 'x' / 'old.txt').is_file()` |

Semantic assessment: each target test ran and failed on its planned assertion, or with the raw OS error the plan names for IN-06. There were no load or fixture faults.

Fail-first for the fixture test (not committed): `android-ndk-r27c/shader-tools/linux-x86_64/libc++.so` was pushed to `../../../toolchains/...`, giving:
`FAIL: test_pinned_archives_pass (tests.test_fetch.LinkRule.test_pinned_archives_pass) [android-ndk-r27c-linux.zip]`
`AssertionError: 'link android-ndk-r27c/shader-tools/linux-x86_64/libc++.so → ../../../toolchains/llvm/prebuilt/linux-x86_64/lib/libc++.so leaves the installed folder' is not None`
The fixture was then regenerated with the script, and the committed file is the script's output.

## devtools/zip_links.py output (2026-10-31, exit 0)

```
android-ndk-r27c-windows.zip: 8386 members, 0 links, installed from android-ndk-r27c: ok
android-ndk-r27c-darwin.zip: 9177 members, 23 links, installed from android-ndk-r27c: ok
android-ndk-r27c-linux.zip: 9277 members, 35 links, installed from android-ndk-r27c: ok
platform-tools_r37.0.1-win.zip: 15 members, 0 links, installed from platform-tools: ok
platform-tools_r37.0.1-darwin.zip: 14 members, 0 links, installed from platform-tools: ok
platform-tools_r37.0.1-linux.zip: 12 members, 0 links, installed from platform-tools: ok
dotnet-sdk-10.0.403-win-x64.zip: 5577 members, 0 links, installed from the whole archive: ok
wrote tests/fixtures/zip_links.json
```

The .NET tarballs were not re-read. The planner streamed them on 2026-10-30: osx-arm64 has 5,630 members, linux-x64 5,631 and linux-arm64 5,631, with 0 symlinks each.

## Verification

- `python3 -m unittest tests.test_fetch -v`: 28 tests, OK, none skipped on macOS.
- `python3 -m unittest discover tests`: 240 tests, OK (232 after Task 1).
- `python3 tests/arch_rules.py`: all checks passed.
- The verifier's CR-04 repros, run through `fetch._install`:
  - `android-ndk-r27c.zip: refused, link top/up → ../platform-tools/adb leaves the installed folder`
  - `platform-tools.zip: refused, link platform-tools/z → .. leaves the installed folder`
  - In both cases nothing was installed.
- Every acceptance-criteria grep from the three tasks passed: `is_relative_to` 0, `iterdir` 0, `shutil.rmtree(dest` 0, `_link_refusal(` 3, CONCERNS rows 84, docs numstat `1 1` for each file, `urlopen` 6, and the fixture has `7 58`.

## Decisions Made
- Followed the plan's rule as specified. One addition: a link whose name has no components (such as a tar link named `.`) is refused as "not a plain ASCII path", because it has no name to resolve from.

## Deviations from Plan

**1. [Rule 1 - Bug] The guard test asserted that a folder link resolves to a file**
- **Found during:** Task 1 RED
- **Issue:** The behavior block says each link's `resolve()` is a file, but `top/lib -> lib64` is a folder link, so the guard failed at HEAD on the subTest for `lib`.
- **Fix:** The guard now asserts `resolve().exists()` and that the target is inside dest.
- **Files modified:** tests/test_fetch.py
- **Committed in:** 790e470

**Total deviations:** 1 auto-fixed (Rule 1). **Impact:** test-only; the guard checks the same containment.

## Issues Encountered
- Local Python 3.12.9 and 3.13 could not run the suite: 3.12 hit an import error loading `tests.test_fetch`, and 3.13 has no lz4. The 3.11 behaviour (loop refused instead of RuntimeError) still has to be confirmed by the fork-ci 3.11 job.

## Flagged (carried from the plan, unresolved)
- Two `porter tools --download` runs at once are not serialized over `.<folder>.unpack` / `.<folder>.old` (T-02-42, accepted; the GUI runs one download at a time).
- Edge HARD-01 (probe `unclassified`) is left for manual review, as the planner flagged it.

## User Setup Required
None.

## Next Phase Readiness
CR-04, IN-06 and WR-05 are closed in code and tests. The phase is ready for re-verification and for the CI run on Windows, Linux and 3.11.

## Self-Check: PASSED
- Found all six key files; found commits 790e470, a5e1836, 3ed0e99, c814d94 and e7a6874 on HEAD.
