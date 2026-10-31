---
phase: 02-porter-hardening
verified: 2026-10-31T02:40:00Z
status: human_needed
score: 95/97 must-haves verified (roadmap success criteria 4/5; plan truths 91/92)
covered_files:
  - .planning/codebase/CONCERNS.md
  - .planning/phases/02-porter-hardening/02-01-PLAN.md
  - .planning/phases/02-porter-hardening/02-01-SUMMARY.md
  - .planning/phases/02-porter-hardening/02-02-PLAN.md
  - .planning/phases/02-porter-hardening/02-02-SUMMARY.md
  - .planning/phases/02-porter-hardening/02-03-PLAN.md
  - .planning/phases/02-porter-hardening/02-03-SUMMARY.md
  - .planning/phases/02-porter-hardening/02-04-PLAN.md
  - .planning/phases/02-porter-hardening/02-04-SUMMARY.md
  - .planning/phases/02-porter-hardening/02-05-PLAN.md
  - .planning/phases/02-porter-hardening/02-05-SUMMARY.md
  - .planning/phases/02-porter-hardening/02-06-PLAN.md
  - .planning/phases/02-porter-hardening/02-06-SUMMARY.md
  - .planning/phases/02-porter-hardening/02-07-PLAN.md
  - .planning/phases/02-porter-hardening/02-07-SUMMARY.md
  - .planning/phases/02-porter-hardening/02-08-PLAN.md
  - .planning/phases/02-porter-hardening/02-08-SUMMARY.md
  - .planning/phases/02-porter-hardening/02-09-PLAN.md
  - .planning/phases/02-porter-hardening/02-09-SUMMARY.md
  - .planning/phases/02-porter-hardening/02-10-PLAN.md
  - .planning/phases/02-porter-hardening/02-10-SUMMARY.md
  - .planning/phases/02-porter-hardening/02-11-PLAN.md
  - .planning/phases/02-porter-hardening/02-11-SUMMARY.md
  - .planning/phases/02-porter-hardening/02-12-PLAN.md
  - .planning/phases/02-porter-hardening/02-12-SUMMARY.md
  - .planning/phases/02-porter-hardening/02-13-PLAN.md
  - .planning/phases/02-porter-hardening/02-13-SUMMARY.md
  - devtools/hooks.py
  - devtools/nuget_pins.py
  - devtools/zip_links.py
  - docs/ARCHITECTURE.md
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
  - tests/fixtures/zip_links.json
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
covered_digest: "v4:sha256:15877b5b21754d94b8ed610791d4c072bd3a03a99e8decc201208534fb0b9ce2"
behavior_unverified: 0
overrides_applied: 0
re_verification:
  previous_status: gaps_found
  previous_score: 80/83 must-haves verified (roadmap success criteria 3/5; plan truths 77/78)
  gaps_closed:
    - "Roadmap SC1 / HARD-01 (CR-04): a link that leaves the installed toolchain is refused. fetch._link_refusal resolves every link in memory from the folder _install moves (fetch.py:140-171, 174-200, 203-221). The verifier's one-archive and two-archive repros are both REFUSED through fetch._install; a 3,000-archive zip/tar fuzz found 0 accepted archives with a link resolving outside the installed folder on disk; the six new RED tests fail at e482289 and pass at HEAD"
  gaps_remaining: []
  regressions: []
deferred:
  - truth: "Pinned toolchain downloads serve the host's own binaries (review WR-04: Linux arm64 is served the x86-64 NDK and platform-tools rows as pinned)"
    addressed_in: "Phase 3"
    evidence: "Phase 3 SC3: 'On Linux arm64, setup detects or downloads a community arm64 NDK r27c, checked by hash and a compile probe'; SC4 / TOOL-03: distro adb on Linux"
human_verification:
  - test: "Push HEAD (main is 120 commits ahead of origin/main) and check the windows-2025 job of fork-ci.yml runs tests.test_lock and tests.test_datapack green (02-01 human check, 02-12 deferred check, VALIDATION manual row 1)"
    expected: "A second porter on Windows gets 'already running: porter port, PID ...' naming the holder; test_wait_for_holder waits instead of crashing; test_holder_read_stays_below_lock green"
    why_human: "The msvcrt lock branch has never run. Whether ReadFile below a mandatory byte-range lock succeeds is only shown by a Windows run, and the bundle ships on Windows today (roadmap SC2)"
  - test: "Check the windows-2025 job runs tests.test_porter.Env and tests.test_fetch green, including Unpack.test_failed_move_keeps_old_toolchain and the LinkRule class"
    expected: "dotnet is reached by absolute path; the link rule refuses the crafted archives on Windows too; a failed toolchain swap keeps the old toolchain"
    why_human: "PATH semantics and rename-of-a-file-in-use are Windows-only behaviours; nothing in this phase has run on Windows"
  - test: "Check fork-ci.yml runs the suite green on windows-2025, macos-15, ubuntu-22.04, ubuntu-24.04-arm, plus the Python 3.11 job (02-07 human check, 02-10 phase gate, 02-13 D5)"
    expected: "All five jobs green; on 3.11 Unpack.test_link_loop_refused gives BuildError, not RuntimeError"
    why_human: "Only macOS Python 3.14.5 has run this suite; local 3.12/3.13/3.15 cannot import the test modules (missing lz4 / import error)"
  - test: "Flagged prohibitions (test-tier, no test enforces them; each holds today on inspection): 02-07 every test module sets its own NX2A_HOME before importing porter; 02-08 no FPSLocker-Warehouse config contents are committed; 02-10 no packages.lock.json or other pin file in the nxnative subtree"
    expected: "Accept as reviewed, or add a guard (for example an arch_rules check) so a later change cannot break them silently"
    why_human: "unverified-prohibition: human review recommended. Test-tier prohibitions without wired enforcement fail closed and cannot be counted as passed"
  - test: "Decide on the open 02-13 review warnings WR-07 to WR-10 (02-REVIEW-DISPOSITION.md, all 'open'): fix now, or set them to 'deferred' with a reason"
    expected: "Each row carries a decision. None is an escape: the verifier reproduced WR-07 and the aliased member lands inside the installed folder"
    why_human: "Triage of non-blocking findings is the developer's call; WR-08 in particular is the Windows file-in-use case WR-05's swap was built for, and it still ends in a raw traceback instead of a 'close the program using it' message"
---

# Phase 2: Porter Hardening Verification Report

**Phase Goal:** Ports survive interruption, hostile archives and tampered downloads without corrupting builds or losing the signing key
**Verified:** 2026-10-31T02:40:00Z
**Status:** human_needed
**Re-verification:** Yes, after gap-closure plan 02-13

## Goal Achievement

Plan 02-13 closes CR-04, the one blocking gap. I checked the code and ran the attacks myself; I did not rely on the summary. Links are now decided in memory, from the archive's own member list, before anything is written. They are resolved from the folder `_install` actually moves into place: `_top` names it, and `_unzip`/`_untar` return `into / top`. So the folder that is checked and the folder that is installed are the same by construction.

Every behaviour the goal names now holds on macOS. Nothing has run on Windows or Linux, and HEAD is not pushed. That keeps the phase at human_needed.

### Observable Truths (roadmap success criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Crafted zip/tar with `..`, absolute paths or symlinks are refused and write nothing outside; porter refuses a Python without the CVE-2025-4517 fix | VERIFIED | `_link_refusal` (fetch.py:140-171) resolves links from the installed root, called in `_unzip` (178-180) and `_untar` (197) before any write. My repro through `fetch._install`: `top/up -> ../platform-tools/adb` REFUSED; `platform-tools/z -> ..` REFUSED; the NDK half `top/k -> ../platform-tools/z/../config.json` REFUSED; tar `./up -> ../config.json` and `./up -> ../.dotnet.unpack/sdk/x` REFUSED; `top` -> `..` with `top/x` REFUSED. Fuzz, 2 seeds × 3,000 random zip/tar archives (mixed case, `.`/`..`, with and without top folder): 1,108 + 1,118 accepted, **0** with a link resolving outside `dest` on disk, nothing left under NX2A_HOME but `config.json` and `toolchains`. Names, tar `filter='data'` and the Python floor unchanged (suite green). |
| 2 | A port killed at any stage redoes it; a crash mid pack swap leaves a working pack; a second port shows "already running" | UNCERTAIN (Windows) | POSIX: unchanged and green (test_stages CutOff, test_crash_mid_swap_keeps_old_pack, test_second_take_names_holder, test_holder_read_stays_below_lock). `lock.py:20` still opens with `buffering=0`. The Windows `msvcrt` branch has never run (human item 1). |
| 3 | Toolchains, NuGet packages and FPSLocker configs checked against one manifest; FPSLocker hash in the log; mismatch stops clearly | VERIFIED | Regression check only: pins.py, `_download` mismatch (fetch.py:118-120), `nuget.check`; suite green. |
| 4 | Signing key created atomically, mode 0600; unreadable key stops | VERIFIED | Regression check only: mkapk.py:199-209, test_signing green. |
| 5 | Every CONCERNS.md item closed; the suite covers downloads/unpacking, adb/install, per-OS detection, CLI errors | VERIFIED | CONCERNS.md:292 closure row now names 02-13 and the in-memory rule rooted at the installed folder, which matches the code. Coverage modules present and green (240 tests). |

**Score:** 4/5 roadmap criteria verified (1 uncertain, Windows); 91/92 plan truths verified; 0 present-but-behavior-unverified.

### Previous gap, re-checked

| Gap | Status now | Evidence |
|-----|------------|----------|
| CR-04: links checked on the unpack folder, a different tree installed | CLOSED | See SC1. The install root comes from one place (`_top`), and `_install` no longer lists the unpack folder (`src = (_unzip if ...)(arc, tmp, it.folder)`, fetch.py:212). The six RED tests fail at e482289 for their stated reasons (I ran each on an exported e482289 tree with HEAD's tests): four `BuildError not raised`, one raw `PermissionError`, one raw `FileExistsError`. All pass at HEAD. |

### Plan truths

| Plan | Truths | Verified | Note |
|------|--------|----------|------|
| 02-01 to 02-12 | 78 | 77 | Regression only, suite green. #1 of 02-01 ("already running" on Windows) stays UNCERTAIN (human item 1) |
| 02-13 link rule, toolchain swap | 14 | 14 | Detail below |

02-13 truths, each checked against code or a run:

| # | Truth (short) | Status | Evidence |
|---|---------------|--------|----------|
| 1 | CR-04 one archive refused, nothing installed, no `.x.unpack` | VERIFIED | test_link_to_sibling_refused; my repro |
| 2 | `platform-tools/z -> ..` refused at its own install | VERIFIED | test_link_above_root_refused; my repro |
| 3 | Relocation case refused naming `top/a` | VERIFIED | test_relocated_link_refused; LinkRule.test_refusals |
| 4 | CR-01 test unchanged and green | VERIFIED | body unchanged (test_fetch.py:171), passes |
| 5 | Loops refused with BuildError on 3.11-3.14 | VERIFIED (3.14 run) | 40-hop cap is pure arithmetic in memory, no `Path.resolve`, so no Python version can change it. Run only on 3.14.5; the 3.11 CI job is human item 3 |
| 6 | IN-06 shapes `d/x`+`d -> .` and `a -> nowhere`+`a/b -> x` refused with BuildError | VERIFIED | test_link_beside_folder_refused, test_link_under_link_refused; raw OSErrors at e482289 |
| 7 | One pure `_link_refusal`, called by `_unzip` and `_untar` on every OS | VERIFIED | grep: 3 references, no OS branch around the call (links are read on every OS, fetch.py:178) |
| 8 | One decision of the install root | VERIFIED | `_unzip`/`_untar` return `into / top`; `_install` has no `iterdir` |
| 9 | Legit NDK layouts still install as links | VERIFIED | test_internal_links_kept, test_valid_zip_kept, LinkRule.test_inside_passes |
| 10 | Every pinned zip passes the rule | VERIFIED | I re-ran `devtools/zip_links.py`'s `main()` against the live vendor URLs, writing to the scratchpad: all seven `ok`, and its output equals the committed fixture byte for byte (sorted JSON). This covers the full member lists, which the offline test does not (WR-09) |
| 11 | WR-05 aside swap, restore on failure, no `.old`/`.unpack` left | VERIFIED | test_failed_move_keeps_old_toolchain fails at 3ed0e99 (line 224, `False is not true`) and passes at HEAD |
| 12 | Cut-off move put back by the next `_install` | VERIFIED | test_cut_off_move_restored fails at 3ed0e99 (line 232), passes at HEAD; fetch.py:209 |
| 13 | ARCHITECTURE.md and CONCERNS.md describe the rule | VERIFIED | ARCHITECTURE.md:104 contains "resolved in memory from the folder that is installed"; CONCERNS.md:292 |
| 14 | New tests run offline | VERIFIED | Unpack/LinkRule use local archives and the committed fixture; no urlopen in them |

### Deferred Items

| # | Item | Addressed In | Evidence |
|---|------|-------------|----------|
| 1 | Linux arm64 gets the x86-64 NDK / platform-tools rows as pinned (WR-04) | Phase 3 | SC3 (community arm64 NDK r27c, hash-checked) and SC4 / TOOL-03 (distro adb) |

### Advisory (New Scope, Unevidenced)

None. The new review findings (WR-07 to WR-10, IN-10 to IN-14) are listed under anti-patterns. None is a blocker: WR-07 I reproduced, and it stays inside the installed folder; the others are about message quality, test strength or the dev tool.

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `porter/fetch.py` | `_parts`, `_top`, `_link_refusal`; `_unzip`/`_untar` return the install root; aside swap | VERIFIED | lines 132-221 |
| `tests/test_fetch.py` | 9 new Unpack tests, class LinkRule | VERIFIED | lines 176-232, 243-294 |
| `devtools/zip_links.py` | Range reader, runs the rule, writes fixture | VERIFIED | I ran it (to scratchpad); exit 0 |
| `tests/fixtures/zip_links.json` | link tables of 7 pinned zips | VERIFIED | 7 entries, 58 links, hashes equal the pins (test_pinned_archives_pass) |
| `docs/ARCHITECTURE.md` | the rule as built | VERIFIED | line 104 |
| `.planning/codebase/CONCERNS.md` | closure row | VERIFIED | line 292 |

### Key Link Verification

| From | To | Via | Status |
|------|----|-----|--------|
| `_unzip` / `_untar` | `_link_refusal` | called after `_refuse_names`, before the first write (fetch.py:180, 197) | WIRED |
| `_install` | folder `_unzip`/`_untar` return | `src = (_unzip if arc.suffix == '.zip' else _untar)(arc, tmp, it.folder)` (fetch.py:212) | WIRED |
| `LinkRule.test_pinned_archives_pass` | fixture and pins.py | hashes compared, rule run per table | WIRED (link names only, WR-09) |
| `devtools/zip_links.py` | `fetch._top`, `fetch._link_refusal` | same functions over the full member list | WIRED |
| `download` | `_install` | fetch.py:235 | WIRED |

The 02-01 to 02-12 key links are unchanged (regression grep, suite green).

### Data-Flow Trace (Level 4)

Not applicable. 02-13 renders no dynamic data.

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Full suite (run once) | `QT_QPA_PLATFORM=offscreen python3 -m unittest discover tests` | 240 tests OK, 20.1 s, Python 3.14.5 | PASS |
| Architecture rules | `python3 tests/arch_rules.py` | all checks passed | PASS |
| CR-04 repros and tar/top-link variants | `python3 -I repro.py` through `fetch._install` | all 7 REFUSED with porter's message | PASS |
| Link fuzz | 2 × 3,000 random zip/tar archives | 0 escapes among 2,226 accepted | PASS |
| RED tests red before their fix | HEAD tests on exported e482289 / 3ed0e99 | all 8 fail for their stated reasons; test_internal_links_kept passes there (guard) | PASS |
| Pinned zips pass with full member lists | `zip_links.main()` with FIXTURE redirected | 7 ok, output equals committed fixture | PASS |
| WR-07 on APFS | tar `a;b -> sub` + `a;b/x` | ACCEPTED; `x` written through the link to `dotnet/sub/x`, inside | Info (confirms review, no escape) |
| Debt markers | grep TBD/FIXME/XXX in changed files | none | PASS |

### Probe Execution

Step 7c: SKIPPED. No `scripts/*/tests/probe-*.sh` exists and no plan declares one.

### Requirements Coverage

| Requirement | Source Plan | Status | Evidence |
|-------------|-------------|--------|----------|
| HARD-01 | 02-04, 02-11, 02-13 | SATISFIED | SC1 above |
| HARD-02 | 02-02 | SATISFIED | unchanged |
| HARD-03 | 02-08 | SATISFIED | unchanged |
| HARD-04 | 02-01, 02-10, 02-12 | SATISFIED on POSIX / NEEDS HUMAN (Windows) | human item 1 |
| HARD-05 | 02-06 | SATISFIED | unchanged |
| HARD-06 | 02-05 | SATISFIED (Windows run pending) | human item 2 |
| HARD-07 | 02-01 | SATISFIED | unchanged |
| HARD-08 | 02-09 | SATISFIED | unchanged (IN-01 status badge open) |
| HARD-09 | 02-05 | SATISFIED | unchanged |
| HARD-10 | 02-02, 02-03, 02-09 | SATISFIED | unchanged (IN-05 stale CLAUDE.md line open) |
| PKG-07 | 02-04, 02-08, 02-10 | SATISFIED | unchanged |
| TEST-01 | 02-07, 02-04, 02-11, 02-13 | SATISFIED on macOS | crafted-archive tests now include installed-tree cases; offline pinned-archive test is link-only (WR-09) |

No orphaned requirements: all 12 Phase 2 IDs appear in at least one plan. REQUIREMENTS.md still marks all twelve "Gaps Found"; the orchestrator should update the rows when it records this verdict.

### Prohibitions

| Plan | Prohibition | Tier | Disposition |
|------|-------------|------|-------------|
| 02-01 | must not remove the old pack before the new is in | test | VERIFIED |
| 02-02 | must not make a new key when the file exists but is unreadable | test | VERIFIED |
| 02-04 | must not install an archive whose hash differs | test | VERIFIED |
| 02-07 | tests must not touch the real NX2A_HOME | test | FLAGGED: holds on inspection; no test enforces it |
| 02-08 | must not commit FPSLocker config contents | test | FLAGGED: holds; no test enforces it |
| 02-10 | must not add a pin file to nxnative | test | FLAGGED: holds; no test enforces it |
| 02-11 | must not add a zip-link test that passes on the pre-fix `_unzip` | test | VERIFIED |
| 02-12 | bounded read not behind a Windows-only branch | judgment | VERIFIED |
| 02-12 | translator tests must not write into the real nx2android folder | test | VERIFIED |
| 02-13 | must not refuse any pinned archive | test | VERIFIED: test_pinned_archives_pass (link tables) plus my live full-list run of all seven zips. The three .NET tarballs have no symlinks per the planner's 2026-10-30 stream; I did not re-read them, but `_link_refusal` returns None for any archive with no links, so they cannot be refused by this rule |
| 02-13 | must not delete the installed toolchain before its replacement is in | test | VERIFIED: test_failed_move_keeps_old_toolchain, red at 3ed0e99 |
| 02-13 | no CR-04/IN-06/WR-05 test that passes at e482289 | test | VERIFIED: all eight fail at e482289 (the two WR-05 tests on their CR-04 setup line); the WR-05 pair also fails at 3ed0e99 on the WR-05 assertion itself |

### Anti-Patterns and Open Review Findings

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| porter/fetch.py | 148-154 | casefold only, no Unicode normalization (WR-07) | WARNING | APFS aliases a non-ASCII member to an ASCII link; zip gives a raw FileExistsError, tar writes through the link. Reproduced: lands inside the installed folder |
| porter/fetch.py | 213-216 | raw OSError when a toolchain is in use on Windows (WR-08) | WARNING | old toolchain kept, but the player gets a traceback, not a fix |
| tests/test_fetch.py | 285 | pinned-archive test checks link names only (WR-09) | WARNING | `_top`/`count`/`under` regressions on real NDK layouts would pass offline |
| devtools/zip_links.py | 18-51 | no hash check of the read file (WR-10) | WARNING | dev tool only |
| porter/fetch.py | 182-186 | raw NotADirectoryError / IsADirectoryError / FileExistsError for file-vs-folder name clashes (found by my fuzz, ~12% of random archives, mostly case clashes on APFS) | Info | fails closed: `.x.unpack` removed, nothing left behind; the player sees a traceback, not "refused". Not covered by the plan's two named IN-06 shapes |
| porter/fetch.py | 209 | the cut-off restore runs only inside `_install`, after a successful download | Info | between a cut-off and the next successful download the config points at a missing folder |
| tests/test_fetch.py | 165, 170 | two link tests still skipped on Windows (IN-13) | Info | Windows CI loses that coverage |
| porter/fetch.py | 165-167 | 40-hop cap vs macOS's 32 (IN-11) | Info | unusable link accepted, no escape |
| docs/ARCHITECTURE.md | 104 | "links last" stated for tar too (IN-12) | Info | doc precision |
| porter/cli.py | 113-114 | recover before lock (WR-01) | WARNING | carried forward |
| porter/pipeline.py | 192-193 | tools lock held for a whole survey (WR-02) | WARNING | carried forward |
| nxnative/dm/android/apk/mkapk.py | 199-201 | `os.link` only (WR-03) | WARNING | carried forward; on FAT/exFAT homes no port can be signed |
| porter/datapack.py | 66 | no Windows retry on the aside rename (WR-06) | WARNING | carried forward |

Two `porter tools --download` runs at once are still not serialized over `.<folder>.unpack` / `.old` (T-02-42, accepted in the plan; the GUI runs one download at a time).

### Human Verification Required

1. **Windows lock** (tests.test_lock, tests.test_datapack on windows-2025). Push HEAD first: main is 120 commits ahead of origin/main. Expected: "already running: ..." naming the holder; wait=True waits. Why human: the `msvcrt` branch has never run.
2. **Windows env and toolchain swap** (tests.test_porter.Env, tests.test_fetch on windows-2025). Expected: green. Why human: PATH semantics and renaming a folder with a file in use only exist on Windows.
3. **All five fork-ci jobs green**, including 3.11. Why human: only macOS 3.14.5 has run.
4. **Three flagged prohibitions** (02-07, 02-08, 02-10): accept them, or add a guard.
5. **Triage WR-07 to WR-10** in 02-REVIEW-DISPOSITION.md: fix or defer with a reason. WR-08 is the most user-visible: it is the exact Windows case the new swap exists for.

### Gaps Summary

No blocking gaps remain. CR-04 is closed by construction, and the attacks I tried do not get through: the reviewer's repros, tar variants, a link named as the top folder, and 6,000 random archives. Every pinned zip still installs, which I confirmed against the vendors' live files. What is left is platform evidence (Windows, Linux, 3.11, all unrun because HEAD is not pushed) and triage of four non-blocking review warnings.

---

_Verified: 2026-10-31T02:40:00Z_
_Verifier: Claude (gsd-verifier)_
