---
phase: 02-porter-hardening
verified: 2026-10-30T19:30:00Z
status: gaps_found
score: 65/71 must-haves verified (roadmap success criteria 2/5; plan truths 63/66)
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
covered_digest: "v4:sha256:252b07f5732cff83f885749373832e004251712f6e2e2afdf0c0598c586dd3dd"
behavior_unverified: 0
overrides_applied: 0
gaps:
  - truth: "Roadmap SC1 / 02-04: crafted zip archives with symlinks are refused (a link that is absolute, escaping, or runs through an earlier link would resolve outside the unpack folder)"
    status: failed
    reason: "fetch._unzip checks each link against the tree as it stands when that link is made. A link whose path runs through a component that does not exist yet resolves lexically and passes; a later link then creates that component pointing back up. Reproduced by the verifier (three-entry zip: file d1/d2/keep.txt, link a -> d1/d2/b/../../../escaped, link d1/d2/b -> ../..): _unzip returns without error and a resolves outside the unpack folder. Nothing is written through the link (links are made last), so 'writes nothing outside' still holds, but the archive is not refused and the installed toolchain keeps a link pointing outside its folder. Same as review CR-01."
    artifacts:
      - path: "porter/fetch.py"
        issue: "lines 141-146: per-link resolve check runs before later links exist"
      - path: "tests/test_fetch.py"
        issue: "Unpack.test_escaping_links_refused has no forward-reference case, so the suite passes with the bypass present"
    missing:
      - "Create every link first, then check every link against the final tree (resolve().is_relative_to(root)); _install already removes the .unpack folder on any exception"
      - "Add the three-entry zip above to tests/test_fetch.py Unpack"
  - truth: "Roadmap SC5: every item in CONCERNS.md is closed"
    status: partial
    reason: "The closure row 'Zip extraction writes symlinks from unsanitized member names' says links 'must resolve inside the unpack folder'. That is false while the gap above is open. The other rows check out against the code and tests. The root cause is the same as the gap above, and so is the fix."
    artifacts:
      - path: ".planning/codebase/CONCERNS.md"
        issue: "closure row for zip symlinks claims a guarantee the code does not give"
    missing:
      - "Close the zip-link gap above; the row then becomes true as written"
  - truth: "02-10: builds of the tools every game shares take a blocking lock, so two ports of different games build them one after the other"
    status: partial
    reason: "The lock is taken and held (test_restored_holds_tools_lock), but Port.translator checks reuse only before nuget.restored() takes the lock and never again inside it. A port that waited then removes the key, rebuilds and swap_in()s over <user dir>/tools/dmsh_xlate (rmtree first) even though the first port has just built the same key, while the first port may be running shader_vk.py --xlate on that dll. On POSIX the first port's shader stage can fail; on Windows the rmtree fails part-way on the loaded dll and leaves the shared translator half-deleted with no key. A re-run recovers (no key, so it rebuilds), but the lock does not do what it was added for. Read from the code, not run. Same as review CR-03."
    artifacts:
      - path: "porter/pipeline.py"
        issue: "lines 343-348: no reuse re-check after the tools lock is held"
    missing:
      - "Repeat `if dll.is_file() and nsp.reused(kf, key) is not None: return dll, key` as the first line inside `with nuget.restored(...)`"
      - "For a genuinely different key, either hold the tools lock (wait=True) around the shaders stage's use of the dll, or build into a key-named folder that is never deleted while in use"
deferred:
  - truth: "Pinned toolchain downloads serve the host's own binaries (review WR-04: Linux arm64 is served the x86-64 NDK and platform-tools rows as pinned)"
    addressed_in: "Phase 3"
    evidence: "Phase 3 SC3: 'On Linux arm64, setup detects or downloads a community arm64 NDK r27c, checked by hash and a compile probe'; SC4 / TOOL-03: distro adb on Linux"
human_verification:
  - test: "Push HEAD and check the windows-2025 job of fork-ci.yml runs tests.test_lock and tests.test_datapack green (02-01 human check, VALIDATION manual row 1)"
    expected: "A second porter on Windows gets 'already running: porter port, PID …' naming the holder; test_wait_for_holder waits instead of crashing"
    why_human: "Windows byte-range locks are only exercised on a Windows host. Review CR-02 predicts a failure here: the verifier measured that on Python 3.14 a buffered f.read(4096) issues a raw read of 131072 bytes from offset 0 (and even with a 4096-byte buffer, a second raw read crosses byte 4096), so the holder lookup's read covers the locked byte. If Windows refuses that read, the second porter raises PermissionError from inside the except handler. Windows is the only platform the bundle ships on today."
  - test: "Check the windows-2025 job runs tests.test_porter.Env green (02-05 human check, VALIDATION manual row 2)"
    expected: "dotnet is reached by absolute path on Windows; no child depends on the parent's PATH"
    why_human: "Windows resolves a bare program name through the parent's PATH; only a Windows run shows it"
  - test: "Check fork-ci.yml runs tests.test_toolchain green on windows-2025, macos-15, ubuntu-22.04 and ubuntu-24.04-arm, plus the 3.11 job (02-07 human check, 02-10 phase gate)"
    expected: "All five jobs green"
    why_human: "Nothing in this phase has run on Windows or Linux; HEAD is not pushed"
  - test: "Flagged prohibitions (test-tier, no test enforces them; the verifier found each one holding today): 02-07 every test module sets its own NX2A_HOME before importing porter; 02-08 no FPSLocker-Warehouse config contents are committed; 02-10 no packages.lock.json or other pin file in the nxnative subtree"
    expected: "Accept as reviewed, or add a guard (for example an arch_rules check) so a later change cannot break them silently"
    why_human: "unverified-prohibition: human review recommended. Test-tier prohibitions without wired enforcement fail closed and cannot be counted as passed"
---

# Phase 2: Porter Hardening Verification Report

**Phase Goal:** Ports survive interruption, hostile archives and tampered downloads without corrupting builds or losing the signing key
**Verified:** 2026-10-30T19:30:00Z
**Status:** gaps_found
**Re-verification:** No (initial verification)

## Goal Achievement

The phase delivers most of what it promised. The signing key is safe, NuGet and toolchain downloads are pinned and checked, stage stamps are written last and whole, and the data-pack swap keeps a pack in place. It falls short on "hostile archives": the zip link guard can be bypassed by link order, and I reproduced that myself. The shared translator lock also doesn't stop a waiting port from rebuilding and deleting the translator. Every Windows behaviour is still unrun, and that includes the build-folder lock, which the code review expects to crash on Windows.

### Observable Truths (roadmap success criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Crafted zip/tar with `..`, absolute paths or symlinks are refused and write nothing outside; porter refuses a Python without the CVE-2025-4517 fix | FAILED | Names (`..`, `/`, `\`, drive) refused before any write (`_bad_name`, test_bad_names_refused). Tar always uses `filter='data'` plus the same name check (test_tar_refused). Python floor: `python_ok` gives the right answer for 3.11.12/13, 3.12.3+marker, 3.12.10, 3.13.4, 3.10, 3.14 (run by verifier), and `runlog.run` refuses every command except doctor. **But** the zip link check is order-dependent: verifier repro with a three-entry zip returns without error, leaving a link that resolves outside the unpack folder (CR-01). |
| 2 | A port killed at any stage redoes it; a crash mid pack swap leaves a working pack; a second port shows "already running" | UNCERTAIN (Windows) | POSIX verified by tests: `write_whole` at every key write; the key is removed before outputs (e.g. `extract_aoc` `rmtree(kf)` … `swap_in` … `write_whole`); test_stages CutOff kills with `os._exit` mid-stage and redoes it; datapack renames the old pack aside before the swap and `recover()` puts it back (test_crash_mid_swap_keeps_old_pack); `lock.take` in `Port.inputs` (pipeline.py:128) and `cmd_install` (cli.py:114), checked across processes (test_second_take_names_holder, test_install_cli_already_running). The Windows `msvcrt` branch has never run; CR-02 predicts it crashes there (see Human Verification 1). |
| 3 | Toolchains, NuGet packages and FPSLocker configs are checked against version and hash in one manifest; the FPSLocker hash is in the port log; a mismatch stops clearly | VERIFIED | `porter/pins.py` holds NDK r27c (3 hosts), platform-tools 37.0.1 (3), .NET 10.0.403 (4), FPSLOCKER commit, and NUGET (58 content hashes, LibHac/0.19.0 included). `_download` deletes the part file and names both hashes (test_mismatch_names_both_hashes). `nuget.check` stops naming the package and removes its folder (test_mismatch_stops_and_removes, unpinned, missing-hash). FPSLocker: fetched at the pinned commit, with head fallback marked `[RED] … untested`; the commit and SHA-256 go into the log line and fpslock.tsv (pipeline.py:270-273, test_source_recorded). There is no stored per-config hash to compare against; under D-03 and HARD-03 the commit is the pin and the hash is recorded, not checked. |
| 4 | Signing key created atomically, mode 0600; unreadable key stops instead of making a new one | VERIFIED | `save_key`: mkstemp (0600), fsync/F_FULLFSYNC, `os.link` (never overwrites). `load_key` exits `[RED]` with the recovery steps and tightens group/other bits. The doctor `Signing key` row is red so `require()` stops the port before any stage runs. Tests: test_signing Key/Preflight/Probe, including two first ports ending with one signer. |
| 5 | Every CONCERNS.md item closed; the suite covers downloads/unpacking, adb/install, per-OS detection, CLI errors | FAILED (partial) | The closure table exists with a row per concern, and the rows I checked match the code. Coverage modules exist and pass: test_fetch, test_adb (Sizes/Push/Install), test_toolchain Detection, test_cli ErrorPaths. **But** the zip-symlink closure row asserts the guarantee CR-01 breaks. |

**Score:** 2/5 roadmap criteria verified (2 failed, 1 uncertain); 63/66 plan truths verified; 0 present-but-behavior-unverified.

### Plan truths

| Plan | Truths | Verified | Not verified |
|------|--------|----------|--------------|
| 02-01 lock, pack swap, chunked MD5 | 9 | 8 | #1 "already running" on Windows: UNCERTAIN (CR-02, human item 1) |
| 02-02 signing key, probe signer | 7 | 7 | (CLAUDE.md:351 still names deleted `probes/app/mkapk.py`; doc only, IN-05) |
| 02-03 hooks, ignore, FLIP, Ryujinx patch, arch_rules, upstream output | 7 | 7 | |
| 02-04 pins, safe unpack, Python floor | 7 | 6 | #5 zip links: FAILED (CR-01) |
| 02-05 env dicts, overrides, disk space | 7 | 7 | `porter/pipeline.py` has no `os.environ` write. `procs.setup` (Phase 1, process-wide MSBuild switches) and the restore in `cli.py:97-98` are outside the pipeline |
| 02-06 stage stamps, profile copy, cut-off marker | 5 | 5 | |
| 02-07 CLI errors, adb, detection | 6 | 6 | |
| 02-08 FPSLocker pin | 5 | 5 | |
| 02-09 languages, escaping, font | 7 | 7 | (status badge `{st}` unescaped, values limited by arch_rules: IN-01) |
| 02-10 NuGet pins, tools lock, CONCERNS | 6 | 5 | #5 shared tools lock: FAILED partial (CR-03) |

### Deferred Items

| # | Item | Addressed In | Evidence |
|---|------|-------------|----------|
| 1 | Linux arm64 gets the x86-64 NDK / platform-tools rows as pinned (WR-04) | Phase 3 | SC3 (community arm64 NDK r27c, hash-checked) and SC4 / TOOL-03 (distro adb) |

### Required Artifacts

`gsd-tools verify.artifacts` passed for all 10 plans (44/44 artifacts present with their required contents). I read the main ones; none is a stub: `porter/lock.py`, `porter/datapack.py`, `porter/fetch.py`, `porter/pins.py`, `porter/nuget.py`, `porter/toolchain.py`, `porter/runlog.py`, `nxnative/dm/android/apk/mkapk.py`, `nxnative/scripts/build_ipa_from_nsp.py`, `gui/app.py`.

### Key Link Verification

`verify.key-links` could not parse the plans' prose `from:` fields, so I grepped every pattern by hand. All 24 are WIRED:

| From | To | Evidence |
|------|----|----------|
| Port.inputs | lock.take | pipeline.py:128 `self.lock = lock.take(self.work, 'port')` |
| cmd_install | lock.take / build_dir | cli.py:114 |
| Port.data | datapack.build | pipeline.py:388 `build=self.work` |
| toolchain.require | Signing key row | toolchain.py:107 |
| Port.apk | mkapk.py | pipeline.py:367 |
| README | devtools/hooks.py | README.md:102 |
| arch_rules rule 1 | join_literals | arch_rules.py:39, self-check :45 |
| fetch.plan | pins | fetch.py:81 |
| SetupTab download dialog | untested | gui/app.py:302 (escaped) |
| runlog.run | python_ok | runlog.py:136 |
| Port.extract | nsp.extract / extract_aoc with env | pipeline.py:219, 233 |
| Port.run | check_space(extracted=True) | pipeline.py:104 |
| upstream._load_nsp | _overrides(m) | upstream.py:21 |
| runlog stage wrapper | MARKER | runlog.py:60 |
| shaders/translator | nsp.write_whole(kf | pipeline.py:319, 348 |
| fpslocker.fetch | pins.FPSLOCKER | fpslocker.py:27, 50-51 |
| fps_unlock | sha256 in source | pipeline.py:273 |
| on_inspect | info['languages'] | gui/app.py:125-126 |
| cmd_inspect | nacp.LANGUAGES | cli.py:69 |
| extract / experimental / translator | nuget.restored | pipeline.py:192, 216, 344 |
| nuget.restored | lock.take(wait=True) | nuget.py:36 |
| Port.run env | NUGET_PACKAGES | pipeline.py:95-99 |

### Data-Flow Trace (Level 4)

Not applicable beyond the GUI card. The card's fields come from `call_json(['inspect', …, '--json'])` and the language list from `info['languages']`, which comes from upstream `nacp.LANGUAGES`. Nothing in that chain is hardcoded.

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Full suite (run once) | `QT_QPA_PLATFORM=offscreen python3 -m unittest discover tests` | 221 tests OK, 19.4 s | PASS |
| Architecture rules | `python3 tests/arch_rules.py` | all checks passed | PASS |
| Zip forward-reference link escape | `python3 -I repro.py` (fetch._unzip on a three-entry zip) | `NOT REFUSED`; `a` resolves to `…/T/escaped`, outside the root | FAIL |
| Python floor | `toolchain.python_ok` over 7 version/marker cases | all as specified | PASS |
| Raw read size behind the lock's holder lookup | BufferedRandom over a logging FileIO, `f.read(4096)` | raw read of 131072 bytes from offset 0 on 3.14 (covers locked byte 4096) | ? SKIP (needs Windows to see the effect) |
| No pin file in the subtree | `find nxnative -name packages.lock.json` | none | PASS |
| Debt markers in the phase diff | grep TBD/FIXME/XXX/TODO/HACK | none | PASS |

### Probe Execution

Step 7c: SKIPPED. No `scripts/*/tests/probe-*.sh` exists and no plan declares one. The `probes/` folder holds on-device C probes, not verification probes.

### Requirements Coverage

| Requirement | Source Plan | Status | Evidence |
|-------------|-------------|--------|----------|
| HARD-01 | 02-04 | BLOCKED | tar and names OK, Python floor OK; zip symlink escape (CR-01) |
| HARD-02 | 02-02 | SATISFIED | save_key/load_key, doctor row, test_signing |
| HARD-03 | 02-08 | SATISFIED | pinned commit, commit and SHA-256 in log and fpslock.tsv |
| HARD-04 | 02-01, 02-10 | NEEDS HUMAN (Windows) / partial | POSIX lock verified; Windows unrun (CR-02); shared tools lock re-check missing (CR-03) |
| HARD-05 | 02-06 | SATISFIED | write_whole everywhere, test_stages CutOff |
| HARD-06 | 02-05 | SATISFIED (Windows run pending) | self.env only; `shutil.which('dotnet', path=…)`; _overrides raises |
| HARD-07 | 02-01 | SATISFIED | aside-then-swap and recover; `hashlib.file_digest` in adb.md5 |
| HARD-08 | 02-09 | SATISFIED | every card field goes through `e()`, test_card_escapes (status badge IN-01 is a minor exception) |
| HARD-09 | 02-05 | SATISFIED | check_space over the family plus a re-check after extract |
| HARD-10 | 02-02, 02-03, 02-09 | SATISFIED | probe uses the committed signer; FLIP v1.7; Ryujinx patch; hooks.py; `*.code-workspace` ignored; one language list. CLAUDE.md stale line (IN-05) is doc only |
| PKG-07 | 02-04, 02-08, 02-10 | SATISFIED | pins.py: NDK, PLATFORM_TOOLS, DOTNET, FPSLOCKER, NUGET (58) |
| TEST-01 | 02-07 (and 02-04) | SATISFIED on macOS | test_fetch, test_adb, test_toolchain Detection, test_cli ErrorPaths. The crafted-zip tests miss the CR-01 ordering case |

No orphaned requirements. All 12 IDs mapped to Phase 2 in REQUIREMENTS.md appear in at least one plan. REQUIREMENTS.md already marks all 12 `[x] Complete`; HARD-01 and HARD-04 should not be marked complete until the gaps close.

### Prohibitions (all test-tier)

| Plan | Prohibition | Disposition |
|------|-------------|-------------|
| 02-01 | must not remove the old pack before the new is in | VERIFIED: test_crash_mid_swap_keeps_old_pack |
| 02-02 | must not make a new key when the file exists but is unreadable | VERIFIED: test_garbage_key_refused, test_unreadable_key_refused; `os.link` cannot overwrite |
| 02-04 | must not install an archive whose hash differs | VERIFIED: test_mismatch_names_both_hashes, part file deleted |
| 02-07 | tests must not touch the real NX2A_HOME | FLAGGED: holds on inspection (each porter-importing module sets NX2A_HOME before import); no test enforces it |
| 02-08 | must not commit FPSLocker config contents | FLAGGED: holds (no committed config YAML; fixtures synthetic); no test enforces it |
| 02-10 | must not add packages.lock.json or a pin file to nxnative | FLAGGED: holds (none found); no test enforces it |

### Anti-Patterns and Open Review Findings

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| porter/fetch.py | 141-146 | order-dependent link check (CR-01) | BLOCKER | hostile zip accepted, escaping link left in the toolchain folder |
| porter/pipeline.py | 343-348 | reuse check outside the tools lock (CR-03) | BLOCKER | a waiting port deletes the translator another port is using |
| porter/lock.py | 31 | buffered read past the locked byte on Windows (CR-02) | WARNING (unproven) | on Windows a second porter may crash instead of showing "already running" or waiting |
| porter/cli.py | 113-114 | recover before lock (WR-01) | WARNING | install mid-port fails the port; a pack stays in place |
| porter/pipeline.py | 192-193 | tools lock held for a whole survey (WR-02) | WARNING | other games' ports wait minutes |
| nxnative/dm/android/apk/mkapk.py | 199-201 | `os.link` only (WR-03) | WARNING | no key can ever be made on FAT32/exFAT/some SMB homes; a traceback, not key loss |
| porter/fetch.py | 166 | rmtree then replace (WR-05) | WARNING | re-download on Windows can half-delete the old toolchain |
| porter/datapack.py | 66 | no Windows retry on the aside rename (WR-06) | WARNING | data stage fails at the end of a port; the old pack is kept |
| gui/app.py | 132 | `{st}` unescaped (IN-01) | Info | arch_rules limits the committed values |
| .claude/CLAUDE.md | 351 | stale `probes/app/mkapk.py` (IN-05) | Info | doc only; 02-02 listed it but did not edit it |
| commit 3dc901c | body | 106-character line | Info | breaks the 100-character rule; the hook is not enabled in this clone |

### Human Verification Required

1. **Windows lock (tests.test_lock, tests.test_datapack on windows-2025).** Push HEAD and check the job. Expected: "already running: …" naming the holder, and wait=True waits. Why human: the `msvcrt` branch has never run, and CR-02 plus my read-size measurement suggest it fails.
2. **Windows env (tests.test_porter.Env on windows-2025).** Expected: green. Why human: Windows-only PATH semantics.
3. **All five fork-ci jobs green** (windows-2025, macos-15, ubuntu-22.04, ubuntu-24.04-arm, 3.11). Why human: nothing has run off macOS.
4. **Three flagged prohibitions** (above): accept them, or add a guard.

### Gaps Summary

There are two blocking gaps and one partial. They come from two causes.

1. **Zip link guard (CR-01)** fails roadmap SC1 and makes SC5's closure row untrue. The fix is small and local to `porter/fetch.py`: make all links, then check them all against the final tree, then add the three-entry test. The hash pin means an attacker would need a vendor-served archive to reach this, but the guard exists for exactly that case, and the plan's own truth names "through an earlier link".
2. **Shared translator rebuild (CR-03)**: the 02-10 tools lock serializes the builds, but a waiting port does not re-check reuse, so it rebuilds and deletes the translator in use. Add a one-line re-check inside the lock, and decide how to protect a dll that is in use from a rebuild with a genuinely different key.

Separately, the Windows lock path (CR-02) is the most likely failure once CI runs on Windows. Fixing it (an unbuffered `os.read` of at most `AT` bytes, or `buffering=0`) before pushing would save a CI round.

---

_Verified: 2026-10-30T19:30:00Z_
_Verifier: Claude (gsd-verifier)_
