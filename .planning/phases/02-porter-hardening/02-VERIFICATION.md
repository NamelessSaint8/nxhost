---
phase: 02-porter-hardening
verified: 2026-10-30T20:50:00Z
status: gaps_found
score: 80/83 must-haves verified (roadmap success criteria 3/5; plan truths 77/78)
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
  - devtools/hooks.py
  - devtools/nuget_pins.py
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
covered_digest: "v4:sha256:a0fe3020a9e3bb719e4851c3c5832ee6de82a2253699e09eb8ec8d6c1585d7a4"
behavior_unverified: 0
overrides_applied: 0
re_verification:
  previous_status: gaps_found
  previous_score: 65/71 must-haves verified (roadmap success criteria 2/5; plan truths 63/66)
  gaps_closed:
    - "02-04 / CR-01: a zip link through a later link is refused, in either member order (test_link_through_later_link_refused: red at 9f93d8d, green at HEAD; verifier repro refused both orders)"
    - "Roadmap SC5: the CONCERNS.md zip-symlink closure row is now true as written (links resolve inside the unpack folder, checked once every link exists)"
    - "02-10 / CR-03: a port that waited on the tools lock re-checks reuse under the lock (pipeline.py:347), and each key builds into its own dmsh_xlate-<key[:12]> folder (pipeline.py:344), so a rebuild never removes a dll another key's port uses"
  gaps_remaining:
    - "Roadmap SC1: hostile zips with symlinks are refused (now fails on CR-04 instead of CR-01)"
  regressions: []
gaps:
  - truth: "Roadmap SC1 / HARD-01: crafted zip archives with symlinks are refused (no link in the installed toolchain resolves outside it)"
    status: failed
    reason: "CR-04, reproduced by the verifier. fetch._unzip checks every link against the temporary <toolchains>/.<folder>.unpack folder, but fetch._install then strips the single top folder and moves it to <toolchains>/<folder>, so a relative target means something else once installed. One archive: NDK zip with top/up -> ../platform-tools/adb is ACCEPTED, and the installed android-ndk-r27c/up resolves to the sibling <toolchains>/platform-tools/adb. Two archives: platform-tools zip with platform-tools/z -> .. is ACCEPTED (installed z resolves to <toolchains>); a later NDK zip with top/k -> ../platform-tools/z/../config.json is ACCEPTED, and the installed k resolves to and reads <user dir>/config.json (signing-key.json sits beside it). Nothing is written through these links, so the 'writes nothing outside' clause and HARD-01's literal write wording still hold; 'refused' does not. The archive still has to match the pinned hash (or the vendor's listed hash on the untested fallback), and its binaries are executed by porter anyway, which limits the real-world impact: see the override suggestion in the report."
    artifacts:
      - path: "porter/fetch.py"
        issue: "lines 141-149: links are checked against `into` (the .unpack folder); lines 166-169: _install installs a different tree (top folder stripped, renamed to <toolchains>/<folder>) and never re-checks"
      - path: "tests/test_fetch.py"
        issue: "Unpack has no case where a link passes in the unpack folder but leaves the installed folder, so the suite is green with CR-04 present"
    missing:
      - "After src.replace(dest) in _install, walk dest (os.walk, followlinks=False), resolve every link and require it inside dest.resolve(); also refuse a target whose normalized path relative to dest starts with '..' (stops routes through a sibling toolchain that a later reinstall could redirect); on refusal rmtree(dest) and raise BuildError naming the archive and link"
      - "Add two tests to tests/test_fetch.py Unpack: top/up -> ../<sibling> refused; platform-tools with z -> .. then an NDK with k -> ../platform-tools/z/../config.json, both refused (the first install is already refused by the lexical rule)"
      - "Consider WR-05 at the same time: the new check adds a failure point after rmtree(dest), so rename the old dest aside and restore it on refusal"
deferred:
  - truth: "Pinned toolchain downloads serve the host's own binaries (review WR-04: Linux arm64 is served the x86-64 NDK and platform-tools rows as pinned)"
    addressed_in: "Phase 3"
    evidence: "Phase 3 SC3: 'On Linux arm64, setup detects or downloads a community arm64 NDK r27c, checked by hash and a compile probe'; SC4 / TOOL-03: distro adb on Linux"
human_verification:
  - test: "Push HEAD (main is 108 commits ahead of origin/main) and check the windows-2025 job of fork-ci.yml runs tests.test_lock and tests.test_datapack green (02-01 human check, 02-12 deferred check, VALIDATION manual row 1)"
    expected: "A second porter on Windows gets 'already running: porter port, PID ...' naming the holder; test_wait_for_holder waits instead of crashing; test_holder_read_stays_below_lock green"
    why_human: "CR-02 is fixed in code (lock.py:20 opens unbuffered, so f.read(AT) is one raw read of at most 4096 bytes from offset 0; the Spy test enforces the bound on POSIX and was red before the fix). Whether Windows' ReadFile below a mandatory byte-range lock then succeeds is only shown by a Windows run, and the bundle ships only on Windows today"
  - test: "Check the windows-2025 job runs tests.test_porter.Env green (02-05 human check, VALIDATION manual row 2)"
    expected: "dotnet is reached by absolute path on Windows; no child depends on the parent's PATH"
    why_human: "Windows resolves a bare program name through the parent's PATH; only a Windows run shows it"
  - test: "Check fork-ci.yml runs the suite green on windows-2025, macos-15, ubuntu-22.04 and ubuntu-24.04-arm, plus the 3.11 job (02-07 human check, 02-10 phase gate)"
    expected: "All five jobs green"
    why_human: "Nothing in this phase has run on Windows or Linux; HEAD is not pushed"
  - test: "Flagged prohibitions (test-tier, no test enforces them; the verifier found each one holding today): 02-07 every test module sets its own NX2A_HOME before importing porter; 02-08 no FPSLocker-Warehouse config contents are committed; 02-10 no packages.lock.json or other pin file in the nxnative subtree"
    expected: "Accept as reviewed, or add a guard (for example an arch_rules check) so a later change cannot break them silently"
    why_human: "unverified-prohibition: human review recommended. Test-tier prohibitions without wired enforcement fail closed and cannot be counted as passed"
---

# Phase 2: Porter Hardening Verification Report

**Phase Goal:** Ports survive interruption, hostile archives and tampered downloads without corrupting builds or losing the signing key
**Verified:** 2026-10-30T20:50:00Z
**Status:** gaps_found
**Re-verification:** Yes, after gap-closure plans 02-11 and 02-12

## Goal Achievement

Plans 02-11 and 02-12 closed the three gaps from the last report, and I checked each one in the code, not in the summaries. A zip link through a later link is now refused in either member order. The translator rebuild no longer deletes a dll another port is using. The lock holder read is bounded to 4096 bytes. Each new test fails on its pre-fix commit and passes at HEAD.

"Hostile archives" still fails, now for a different reason (CR-04): the link check runs against the temporary unpack folder, then `_install` moves a different tree into place. I reproduced the reviewer's one-archive and two-archive cases. Both are accepted, and in the two-archive case the installed NDK holds a link that reads `<user dir>/config.json`. Every Windows behaviour is still unrun.

### Observable Truths (roadmap success criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Crafted zip/tar with `..`, absolute paths or symlinks are refused and write nothing outside; porter refuses a Python without the CVE-2025-4517 fix | FAILED | Names, tar `filter='data'` and the Python floor still hold (suite green). CR-01 is closed: the three-entry zip is refused in both orders (my repro: `cr01a: REFUSED`, `cr01b: REFUSED`). **But CR-04:** links are checked against `.<folder>.unpack` (fetch.py:141-149) and `_install` then installs the stripped top folder as `<toolchains>/<folder>` (fetch.py:166-169). My repro through `fetch._install`: `top/up -> ../platform-tools/adb` is ACCEPTED and resolves to the sibling toolchain; `platform-tools/z -> ..` is ACCEPTED, then an NDK with `top/k -> ../platform-tools/z/../config.json` is ACCEPTED and reads `{"secret": 1}` from `<home>/config.json`. Nothing is written through the links, so the "write nothing outside" clause holds. The "refused" clause does not. |
| 2 | A port killed at any stage redoes it; a crash mid pack swap leaves a working pack; a second port shows "already running" | UNCERTAIN (Windows) | POSIX behaviour is verified by tests, as before (test_stages CutOff, test_crash_mid_swap_keeps_old_pack, test_second_take_names_holder). CR-02 is fixed in code: `open(..., 'a+b', buffering=0)` (lock.py:20), so `f.read(AT)` asks for at most 4096 bytes from offset 0. test_holder_read_stays_below_lock (a Spy FileIO that refuses reads past AT) fails at 5b2f4f6 with `read of 131072 bytes at 0 crosses the byte locked at 4096` and passes at HEAD. The Windows `msvcrt` branch itself has never run (human item 1). |
| 3 | Toolchains, NuGet packages and FPSLocker configs checked against one manifest; FPSLocker hash in the log; mismatch stops clearly | VERIFIED | Unchanged since the last report, regression check only: pins.py, `_download` mismatch, `nuget.check`, fps_unlock source line; suite green. |
| 4 | Signing key created atomically, mode 0600; unreadable key stops | VERIFIED | Unchanged, regression check only: test_signing green. |
| 5 | Every CONCERNS.md item closed; the suite covers downloads/unpacking, adb/install, per-OS detection, CLI errors | VERIFIED | The zip-symlink closure row (CONCERNS.md:292) now says links "must resolve inside the unpack folder, checked once every link is in place" and names test_link_through_later_link_refused. That is true as written. CR-04 goes beyond that concern's stated scope (the risk text is about writes escaping the unpack folder), so it is carried under SC1. The coverage modules are present and green. |

**Score:** 3/5 roadmap criteria verified (1 failed, 1 uncertain); 77/78 plan truths verified; 0 present-but-behavior-unverified.

### Previous gaps, re-checked

| Gap | Status now | Evidence |
|-----|------------|----------|
| CR-01 zip link through a later link | CLOSED | fetch.py:149 resolves every link once all exist. Repro refused both orders. test_link_through_later_link_refused fails at 9f93d8d (`BuildError not raised`) and passes at HEAD. |
| SC5 CONCERNS row untrue | CLOSED | The row is true as written (see SC5). |
| CR-03 translator rebuilt under a waiting port | CLOSED | pipeline.py:344 key-named `dmsh_xlate-<key[:12]>` folder and `.key`. pipeline.py:347 re-checks reuse inside `nuget.restored`. test_new_translator_key_keeps_old fails at 5acfd1a; test_waiting_port_reuses_translator fails at cad95dc (`['restore', 'build'] != ['restore']`); both pass at HEAD. The reuse re-check runs after the restore and NuGet check, not right after the lock (IN-07). That is a wasted restore, not a correctness gap. |
| CR-02 (human item last time) | Fixed in code; Windows unrun | See SC2. |

### Plan truths

| Plan | Truths | Verified | Not verified |
|------|--------|----------|--------------|
| 02-01 lock, pack swap, chunked MD5 | 9 | 8 | #1 "already running" on Windows: UNCERTAIN (human item 1) |
| 02-02 signing key, probe signer | 7 | 7 | |
| 02-03 housekeeping | 7 | 7 | |
| 02-04 pins, safe unpack, Python floor | 7 | 7 | #5 (zip links, worded against the unpack folder) now holds. CR-04 is tracked under SC1 |
| 02-05 env dicts, overrides, disk space | 7 | 7 | |
| 02-06 stage stamps | 5 | 5 | |
| 02-07 CLI errors, adb, detection | 6 | 6 | |
| 02-08 FPSLocker pin | 5 | 5 | |
| 02-09 languages, escaping, font | 7 | 7 | |
| 02-10 NuGet pins, tools lock, CONCERNS | 6 | 6 | #5 tools lock now holds (CR-03 closed) |
| 02-11 zip link order | 6 | 6 | All six are worded against the unpack folder and hold. The plan did not consider the installed tree, and that is where CR-04 lives |
| 02-12 translator under the lock, holder read | 6 | 6 | Read bound pinned by the Spy test on POSIX; the effect on Windows is human item 1 |

### Deferred Items

| # | Item | Addressed In | Evidence |
|---|------|-------------|----------|
| 1 | Linux arm64 gets the x86-64 NDK / platform-tools rows as pinned (WR-04) | Phase 3 | SC3 (community arm64 NDK r27c, hash-checked) and SC4 / TOOL-03 (distro adb) |

CR-04 is not deferred. No later phase's criteria mention link checks on unpacked toolchains. Phase 3 SC1 names only "progress, cancel, resume, hash check".

### Advisory (New Scope, Unevidenced)

None. CR-04 is new scope, but it passes the evidence gate on two counts: `porter/fetch.py` was modified since the last verification (02-11), and I reproduced it.

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `porter/fetch.py` | `_unzip` two-pass link check (CR-01) | VERIFIED | lines 141-149 |
| `tests/test_fetch.py` | test_link_through_later_link_refused | VERIFIED | line 171, red before the fix |
| `.planning/codebase/CONCERNS.md` | closure row names the test | VERIFIED | line 292 |
| `porter/pipeline.py` | `dmsh_xlate-` key folders, re-check under the lock | VERIFIED | lines 344-351 |
| `porter/lock.py` | `buffering=0` | VERIFIED | line 20, no OS branch |
| `tests/test_lock.py` | Spy, three new tests | VERIFIED | lines 51, 87, 101, 123 |
| `docs/ARCHITECTURE.md` | tools-lock bullet names key folders | VERIFIED | line 100 |

Artifacts from plans 02-01 to 02-10: regression check only. All are present and the suite is green.

### Key Link Verification

| From | To | Via | Status |
|------|----|-----|--------|
| `_install` | `_unzip` | inside `try/except BaseException` that removes tmp (fetch.py:164-170) | WIRED |
| test_fetch `refused` | `_install` | assertRaises, no `.x.unpack` left | WIRED |
| `Port.shaders` | `Port.translator` | `xlate, xkey = self.translator()` (pipeline.py:305) | WIRED |
| `Port.translator` | `nuget.restored(src` | pipeline.py:346 | WIRED |
| `nuget.restored` | `lock.take(..., wait=True)` | nuget.py:36 | WIRED |
| **`_install` installed tree** | **link check** | **none: `dest` is never re-checked after `src.replace(dest)`** | **NOT_WIRED (CR-04)** |

The 24 key links from 02-01 to 02-10 are unchanged (regression grep only).

### Data-Flow Trace (Level 4)

Not applicable. No rendered dynamic data changed in 02-11 or 02-12.

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Full suite (run once) | `QT_QPA_PLATFORM=offscreen python3 -m unittest discover tests` | 225 tests OK, 21.5 s, Python 3.14.5 | PASS |
| Architecture rules | `python3 tests/arch_rules.py` | all checks passed | PASS |
| CR-01 three-entry zip, both orders | `python3 -I repro.py` via `fetch._install` | REFUSED, naming `top/a` | PASS |
| CR-04 one archive | `top/up -> ../platform-tools/adb` via `fetch._install` | ACCEPTED, resolves to `<toolchains>/platform-tools/adb`, inside dest: False | FAIL |
| CR-04 two archives | `platform-tools/z -> ..`, then NDK `top/k -> ../platform-tools/z/../config.json` | both ACCEPTED; `k` reads `<home>/config.json` | FAIL |
| New tests are red before their fix | each named test run on an exported tree of 9f93d8d, 5acfd1a, 5b2f4f6, cad95dc | all four fail there; all four pass at HEAD | PASS |
| Debt markers in the changed files | grep TBD/FIXME/XXX | none | PASS |

I also checked the tar path by reading the code. `.NET` tarballs are not top-stripped (`it.folder == 'dotnet'` keeps the whole unpack folder), and the data filter refuses a lexical climb above the unpack root. A link there can only be renamed through `../.dotnet.unpack/...`, which leaves it dangling after the move. Info only, not run.

### Probe Execution

Step 7c: SKIPPED. No `scripts/*/tests/probe-*.sh` exists and no plan declares one.

### Requirements Coverage

| Requirement | Source Plan | Status | Evidence |
|-------------|-------------|--------|----------|
| HARD-01 | 02-04, 02-11 | BLOCKED | The literal write clause holds: nothing is written outside the unpack folder. The "symlinks" class is not refused once the tree is installed (CR-04), which fails roadmap SC1, the contract for this requirement |
| HARD-02 | 02-02 | SATISFIED | unchanged |
| HARD-03 | 02-08 | SATISFIED | unchanged |
| HARD-04 | 02-01, 02-10, 02-12 | SATISFIED on POSIX / NEEDS HUMAN (Windows) | CR-03 closed, CR-02 fixed in code; the Windows run is pending |
| HARD-05 | 02-06 | SATISFIED | unchanged |
| HARD-06 | 02-05 | SATISFIED (Windows run pending) | unchanged |
| HARD-07 | 02-01 | SATISFIED | unchanged |
| HARD-08 | 02-09 | SATISFIED | unchanged (IN-01 status badge) |
| HARD-09 | 02-05 | SATISFIED | unchanged |
| HARD-10 | 02-02, 02-03, 02-09 | SATISFIED | unchanged (IN-05 stale CLAUDE.md line) |
| PKG-07 | 02-04, 02-08, 02-10 | SATISFIED | unchanged |
| TEST-01 | 02-07, 02-04, 02-11 | SATISFIED on macOS, with a coverage hole | The crafted-zip tests now include the link-order case. They have no installed-tree case, so they pass with CR-04 present |

No orphaned requirements: all 12 Phase 2 IDs appear in at least one plan. REQUIREMENTS.md marks HARD-01, HARD-04 and TEST-01 "Gaps Found". HARD-01 should stay that way until CR-04 is closed or overridden.

### Prohibitions

| Plan | Prohibition | Tier | Disposition |
|------|-------------|------|-------------|
| 02-01 | must not remove the old pack before the new is in | test | VERIFIED (test_crash_mid_swap_keeps_old_pack) |
| 02-02 | must not make a new key when the file exists but is unreadable | test | VERIFIED |
| 02-04 | must not install an archive whose hash differs | test | VERIFIED |
| 02-07 | tests must not touch the real NX2A_HOME | test | FLAGGED: holds on inspection; no test enforces it |
| 02-08 | must not commit FPSLocker config contents | test | FLAGGED: holds; no test enforces it |
| 02-10 | must not add a pin file to nxnative | test | FLAGGED: holds; no test enforces it |
| 02-11 | must not add a zip-link test that passes on the pre-fix `_unzip` | test | VERIFIED: I ran it at 9f93d8d and it fails (`BuildError not raised`) |
| 02-12 | must not put the bounded read behind a Windows-only branch | judgment | VERIFIED: lock.py:20 is unconditional, and the POSIX Spy test would fail if it were not |
| 02-12 | translator tests must not write into the real nx2android folder | test | VERIFIED: test_lock.py:9 sets NX2A_HOME before import; lines 94 and 104 give each translator test its own |

### Anti-Patterns and Open Review Findings

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| porter/fetch.py | 141-149, 166-169 | link check on the unpack folder, a different tree installed (CR-04) | BLOCKER | a link in an accepted archive leaves the installed toolchain and can read `config.json` / `signing-key.json` |
| porter/fetch.py | 145-149 | raw OSError / RuntimeError on some hostile zips (IN-06) | Info | fails closed, but the player sees a traceback, not "refused" |
| porter/pipeline.py | 346-347 | reuse re-check after the restore (IN-07) | Info | a waiting port runs a needless restore that can fail on the network |
| porter/pipeline.py | 343 | old translator folders never pruned (IN-08) | Info | a documented `shortcut:` comment |
| tests/test_lock.py | 48, 107-113 | 0.5 s timing window (IN-09) | Info | a false failure on a loaded runner, never a false pass |
| porter/cli.py | 113-114 | recover before lock (WR-01) | WARNING | carried forward |
| porter/pipeline.py | 192-193 | tools lock held for a whole survey (WR-02) | WARNING | carried forward |
| nxnative/dm/android/apk/mkapk.py | 199-201 | `os.link` only (WR-03) | WARNING | carried forward |
| porter/fetch.py | 169 | rmtree then replace (WR-05) | WARNING | carried forward; the CR-04 fix adds a failure point here |
| porter/datapack.py | 66 | no Windows retry on the aside rename (WR-06) | WARNING | carried forward |

### Human Verification Required

1. **Windows lock** (tests.test_lock and tests.test_datapack on windows-2025). Push HEAD first: main is 108 commits ahead of origin/main. Expected: "already running: ..." naming the holder, and wait=True waits. Why human: the `msvcrt` branch has never run. CR-02's fix bounds the read, but only Windows shows whether ReadFile below a mandatory lock succeeds.
2. **Windows env** (tests.test_porter.Env on windows-2025). Expected: green. Why human: PATH semantics only Windows has.
3. **All five fork-ci jobs green** (windows-2025, macos-15, ubuntu-22.04, ubuntu-24.04-arm, 3.11). Why human: nothing has run off macOS.
4. **Three flagged prohibitions** (02-07, 02-08, 02-10): accept them, or add a guard.

### Override option for CR-04

This may be acceptable as a known limit, and that is the developer's call. The archive has to match the pinned hash, or the vendor's listed hash on the untested fallback. Porter then runs that archive's `clang`, `adb` and `dotnet`. An archive that gets past the hash check already runs code as the player, and the link guard does not change that. Against that, the roadmap says "refused", the previous round rated CR-01 a blocker on the same impact model, and the fix is about ten lines in `_install`. If you accept it instead of fixing it, add:

```yaml
overrides:
  - must_have: "Roadmap SC1 / HARD-01: crafted zip archives with symlinks are refused (no link in the installed toolchain resolves outside it)"
    reason: "Archives are hash-pinned and their binaries are executed anyway; links are checked against the unpack folder and nothing is written through them"
    accepted_by: "{name}"
    accepted_at: "{ISO timestamp}"
```

### Gaps Summary

One blocking gap is left, and it is self-contained: CR-04 in `porter/fetch.py`. The check proves the links are safe in the folder the archive was unpacked into. The player gets a different folder: the top folder is stripped, the tree is renamed, and sibling toolchains sit next to it. So the check has to run again where the tree will live. Re-check every link under `dest` after `src.replace(dest)`, refuse any target that climbs above `dest` lexically, remove `dest` on refusal, and add the two reproduced cases as tests. Fix WR-05 in the same change, because the new check adds a failure after `dest` has already been deleted.

Everything else in the phase holds on macOS. Windows remains the platform the bundle ships on, and it is still unrun.

---

_Verified: 2026-10-30T20:50:00Z_
_Verifier: Claude (gsd-verifier)_
