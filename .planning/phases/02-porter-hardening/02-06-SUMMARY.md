---
phase: 02-porter-hardening
plan: 06
subsystem: porter
tags: [stage-cache, reuse-keys, atomic-write, upstream-subtree, run-marker]

requires:
  - phase: 02-porter-hardening
    provides: "02-04 runlog.run (Python floor) and 02-05 self.env, extract_aoc(..., env=None) in the NSP script"
provides:
  - "write_whole(p, text) in build_ipa_from_nsp.py: <name>.tmp then os.replace (retried on Windows like swap_in)"
  - "Every reuse-key write in the NSP script (8 sites) and porter's two (Vulkan shaders, translator) goes through write_whole"
  - "experimental_profile builds its iOS copy or provisional profile in <id>.partial and swaps it in; android.tsv written whole"
  - "The .port-running marker holds <pid> <time>, a tab and the stage, rewritten at each stage start; no key sweep (D-09)"
affects: [02-porter-hardening, gui, ios-build]

actuals:
  tokens: 3835
  tasks: 3
  commits: 6
plan_head_before: 9c85262afb986bcb77e550d4c6f96a59b985a95f
plan_head_after: 43a1820b75daaaf13b5d7ef4c3bf48bcdf89a10b

tech-stack:
  added: []
  patterns:
    - "Stamp rule: remove the key, build into <name>.partial, swap it in, write the key last with write_whole"
    - "A cut-off run is detected by its marker but repaired by the keys: the marker only names the stage"

key-files:
  created:
    - tests/test_stages.py
  modified:
    - nxnative/scripts/build_ipa_from_nsp.py
    - porter/pipeline.py
    - porter/runlog.py
    - tests/test_runlog.py
    - docs/ARCHITECTURE.md

key-decisions:
  - "HARD-05/D-08: every reuse key is written last and whole through write_whole (temp file + os.replace) after its outputs are swapped in"
  - "D-09: the cut-off marker names the stage and keeps every reuse key; the Phase 1 key sweep (and its extract/ exemption) is gone"
  - "write_whole retries os.replace for 15 s on Windows, as swap_in does, since a virus scanner can hold the fresh .tmp"

patterns-established:
  - "Kill tests: a child process stubs the tool runner and calls os._exit(9) mid-stage (no finally, no atexit), then a second child redoes the stage"

requirements-completed: [HARD-05]

coverage:
  - id: D1
    description: "A DLC stage killed mid-run leaves no key and no output, is redone on the next run and reused on the one after"
    requirement: "HARD-05"
    verification:
      - kind: integration
        ref: "tests/test_stages.py#CutOff.test_killed_dlc_stage_redone"
        status: pass
      - kind: unit
        ref: "tests/test_stages.py#CutOff.test_write_whole_never_half"
        status: pass
    human_judgment: false
  - id: D2
    description: "Every upstream and porter reuse key goes through write_whole; a cut-off experimental profile copy is never reused"
    requirement: "HARD-05"
    verification:
      - kind: unit
        ref: "tests/test_stages.py#CutOff.test_all_key_writes_whole"
        status: pass
      - kind: unit
        ref: "tests/test_stages.py#CutOff.test_cut_off_profile_copy_recopied"
        status: pass
      - kind: unit
        ref: "tests/test_porter.py#Experimental.test_ios_profile_copied_with_experimental_android_tsv"
        status: pass
    human_judgment: false
  - id: D3
    description: "A cut-off port is announced with its stage, keeps its keys, and a Phase 1 marker still gives the line"
    requirement: "HARD-05"
    verification:
      - kind: unit
        ref: "tests/test_runlog.py#Marker"
        status: pass
    human_judgment: false
  - id: D4
    description: "The iOS build path (upstream's own main) still writes its keys correctly through write_whole"
    requirement: "HARD-05"
    verification: []
    human_judgment: true
    rationale: "The Mac host, iOS shader-library and font key sites run only in an iOS build on a Mac with Xcode; no test drives them. The edit is a mechanical write_text to write_whole swap with the same text"

duration: 5min
completed: 2026-10-30
status: complete
---

# Phase 02 Plan 06: Whole reuse keys, swapped-in profile copies and a marker that names the stage Summary

**A port killed at any stage now redoes only that stage. `write_whole` writes every reuse key last and whole, after the stage's outputs are swapped in. The experimental profile copy is built in `<id>.partial` and swapped in. The cut-off marker names the stage and no longer deletes the keys.**

## Performance

- **Duration:** about 5 min of editing (reading came before that)
- **Started:** 2026-10-30T18:11:01Z
- **Completed:** 2026-10-30T18:15:55Z
- **Tasks:** 3 of 3
- **Files modified:** 6 (plus 3 RED evidence records)

## Accomplishments

- `nxnative/scripts/build_ipa_from_nsp.py` (subtree, 13 lines added and 8 changed):
  - `write_whole(p, text)` sits beside `swap_in`. It writes `<name>.tmp` as UTF-8, then `os.replace`s it over the key. On Windows the replace is retried for up to 15 s, as `swap_in` does.
  - All 8 key writes now use it: extract_aoc, collect_nros, rewrite, the Mac host, split_shaders, the two shader-library loops and the font. Each keeps its own logic (the `if key:` guard and the `for k in …` loops).
- `porter/pipeline.py`:
  - `shaders()` and `translator()` write their keys with `nsp.write_whole` after `nsp.swap_in`.
  - `experimental_profile` builds the iOS copy (same `copytree` and ignore patterns) or the survey's provisional profile in `<id>.partial`, then swaps it in. `android.tsv` is written with `nsp.write_whole`.
- `porter/runlog.py`:
  - The marker is now `<pid> <time>`, a tab, then the stage. `build_folder` writes it with no stage, and the wrapped `PROG.stage` rewrites it at each stage start. An `OSError` there is logged in red, not raised.
  - A port that finds a marker says `[RED] the last port of this game was cut off in <stage>: the stages it had not finished run again`. A marker with no stage (Phase 1) gives the same line without `in <stage>`.
  - The `os.walk` key sweep is deleted. The module header now states D-09.
- `docs/ARCHITECTURE.md`:
  - Under "The port": the stamp rule, `write_whole`, the profile copy and the power-loss risk (delete the build folder after a power cut).
  - The `.port-running` bullet is rewritten for the new marker.

## Task Commits

1. **Task 1 (tracer): a killed DLC stage is redone** - RED `e64290a` (test), GREEN `1097d2c` (feat)
2. **Task 2: every key whole, the profile copy swapped in** - RED `f0f7a0b` (test), GREEN `03fd6e5` (feat)
3. **Task 3: the marker names the stage and keeps the keys** - RED `052d9d7` (test), GREEN `43a1820` (feat)

No REFACTOR commits (none needed). Tracer gate: interactive run, `end-of-phase` mode, automated-only verify. `tests.test_stages` was re-run green before Task 2 started.

## TDD evidence

- **T1 RED** (`.red-02-06-t1.json`, RED_EVIDENCE_OK): the target `test_write_whole_never_half` failed on its first assertion (no `write_whole`). `test_killed_dlc_stage_redone` already passed before the change. extract_aoc already removed its key first and wrote it last, as RESEARCH Pattern 6 found. The test pins that behaviour with a real `os._exit` kill.
- **T2 RED** (`.red-02-06-t2.json`, RED_EVIDENCE_OK): both targets failed on their assertions.
  - The in-place `copytree` left a folder holding only `game.tsv`, which the next run would reuse.
  - The grep found 8 upstream key writes and 2 porter key writes still using `write_text`.
- **T3 RED** (`.red-02-06-t3.json`, RED_EVIDENCE_OK): all three new Marker tests failed on their assertions. The sweep deleted both keys, and the marker had no stage. `test_written_and_removed_on_success` kept passing.

## Files Created/Modified

- `tests/test_stages.py` (new): class `CutOff` with 4 tests. The kill test uses child processes; the others run in-process.
- `nxnative/scripts/build_ipa_from_nsp.py`: `write_whole` and the 8 key sites
- `porter/pipeline.py`: 2 key writes, the `.partial` profile copy, a whole `android.tsv`
- `porter/runlog.py`: `_mark(stage)`, the stage-naming message, no sweep
- `tests/test_runlog.py`: `test_cut_off_redoes_stages` replaced by three Marker tests
- `docs/ARCHITECTURE.md`: the stamp rule and the marker bullet

## Decisions Made

- The STATE.md decision "01-02: the cut-off key sweep prunes the top-level extract/ folder" no longer applies, because the sweep is gone (D-09).
- The marker is rewritten in place at each stage start. A torn write reads as an unknown stage. The marker only names the stage and never decides what reruns.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Windows retry in write_whole**
- **Found during:** Task 1
- **Issue:** `os.replace` over a file fails with `PermissionError` while a virus scanner holds the fresh file open. The code comment in `swap_in` records that failure for a folder rename (Tales of Eternia, 2026-10-28). A bare `os.replace` would turn the old in-place key write into a new failure on Windows.
- **Fix:** On Windows, `os.replace` is retried 30 times at 0.5 s, the same loop as `swap_in`. Other platforms are unchanged.
- **Files modified:** nxnative/scripts/build_ipa_from_nsp.py
- **Verification:** `CutOff.test_write_whole_never_half` (the old content survives a failed replace)
- **Committed in:** 1097d2c

**2. [Rule 1 - Acceptance grep] The "cut off in" literal**
- **Found during:** Task 3
- **Issue:** The first version built the message with a nested f-string, so `grep -c "cut off in" porter/runlog.py` printed 0.
- **Fix:** The message now has two literals, one with the stage and one without. They share the tail `rest`.
- **Committed in:** 43a1820

---

**Total deviations:** 2 auto-fixed (1 missing critical, 1 acceptance fix). **Impact:** neither changes the plan's scope.

## Issues Encountered

None.

## Verification

- `QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover tests`: Ran 176 tests, OK (170 before; +4 in test_stages, +3 −1 in test_runlog)
- `.venv/bin/python tests/arch_rules.py`: all checks passed
- Acceptance greps (all pass):

  | Check | Result |
  |---|---|
  | `def write_whole` in the script | 1 |
  | `(kf\|k).write_text` in the script | 0 |
  | `kf.write_text` in pipeline.py | 0 |
  | `write_whole(` in the script | 9 |
  | `nsp.write_whole(` in pipeline.py | 3 |
  | `n.endswith('.key')` in runlog.py | 0 |
  | `cut off in` in runlog.py | 1 |
  | `test_cut_off_redoes_stages` in test_runlog.py | 0 |
  | `write_whole` in ARCHITECTURE.md | 1 |

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- The Phase 1 blocker "a cancelled run can leave a stage output the cache trusts" (STATE.md) is closed for the reuse keys and the profile copy. The FPSLocker cache is left to 02-08. The APK (02-02) and the data pack (02-01) are already covered.
- The iOS-only key sites (Mac host, shader libraries, font) are not exercised by any test (coverage D4).

## Self-Check: PASSED

- All 6 key files exist on disk. All 6 task commits are ancestors of HEAD.
- `check evaluation-scope --plan 02-06 --commits-only` resolves the plan's commits.

---
*Phase: 02-porter-hardening*
*Completed: 2026-10-30*
