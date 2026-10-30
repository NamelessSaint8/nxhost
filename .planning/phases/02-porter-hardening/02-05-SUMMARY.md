---
phase: 02-porter-hardening
plan: 05
subsystem: porter
tags: [environment, dotnet, subprocess, upstream-subtree, disk-space]

requires:
  - phase: 02-porter-hardening
    provides: "02-01 build-folder lock hook in Port.inputs (check_space runs after it)"
provides:
  - "Port.run builds self.env with the dotnet folder first on PATH and DOTNET_ROOT; os.environ is never written by a port"
  - "use_profile_dir writes DM_GAMES_DIR / DM_GAMES_FIRST into self.env only; experimental and derived profiles load by path"
  - "upstream build_nx_extract runs dotnet by absolute path from the env's PATH; survey, extract(..., env=None), extract_aoc(..., env=None) pass env to nx_extract"
  - "porter/upstream.py _overrides(m): four overrides checked at import, AssertionError naming the attribute (survives python -O)"
  - "Port.check_space(extracted=False): counts the scanned base, updates and DLC; re-check after extraction, plus the output volume when it differs"
affects: [02-porter-hardening, gui, packaging, windows-ci]

actuals:
  tokens: 5952
  tasks: 3
  commits: 6
plan_head_before: fadabff7180cd645b358117d8682cb23cc2e7e1e
plan_head_after: ee220e40999ba2876f132e5c5e920c2e5bce0201

tech-stack:
  added: []
  patterns:
    - "Child processes get porter's env dict; programs run by absolute path (Windows resolves bare names through the parent's PATH)"
    - "In-process profile lookups go by folder path, never by title ID through DM_GAMES_DIR"
    - "Overrides of upstream internals live in one checked function and fail at import with the attribute's name"

key-files:
  created: []
  modified:
    - nxnative/scripts/build_ipa_from_nsp.py
    - porter/pipeline.py
    - porter/upstream.py
    - tests/test_porter.py

key-decisions:
  - "HARD-06: a port never writes os.environ; every child gets self.env with an absolute dotnet and DOTNET_ROOT"
  - "D-15 applied: the disk check counts exactly the base/updates/DLC scan_nsps picked plus the build folder recursively, and runs again after extraction"
  - "Tracer gate: the Task 1 human-check is the post-push Windows CI job, so it is deferred to end of phase; the automated verify was re-run green before expanding"

patterns-established:
  - "Subtree helper gains env as a trailing keyword with None default, so upstream's main() is unchanged"

requirements-completed: [HARD-06, HARD-09]

coverage:
  - id: D1
    description: "A port's children get porter's env with an absolute dotnet and DOTNET_ROOT; os.environ stays unchanged; profiles load by path"
    requirement: "HARD-06"
    verification:
      - kind: unit
        ref: "tests/test_porter.py#Env"
        status: pass
      - kind: unit
        ref: "tests/test_porter.py#Experimental.test_ios_profile_copied_with_experimental_android_tsv"
        status: pass
    human_judgment: true
    rationale: "Windows resolves programs through the parent's PATH; tests.test_porter.Env must also run green on the windows-2025 fork-ci job after the phase is pushed"
  - id: D2
    description: "porter's upstream overrides are named in _overrides and fail at import with the attribute's name"
    requirement: "HARD-06"
    verification:
      - kind: unit
        ref: "tests/test_porter.py#Overrides"
        status: pass
    human_judgment: false
  - id: D3
    description: "Disk check over the scanned family plus a re-check after extraction, including an output folder on another volume"
    requirement: "HARD-09"
    verification:
      - kind: unit
        ref: "tests/test_porter.py#Misc.test_disk_space"
        status: pass
      - kind: unit
        ref: "tests/test_porter.py#Misc.test_disk_space_after_extraction"
        status: pass
    human_judgment: false

duration: 4min
completed: 2026-10-30
status: complete
---

# Phase 02 Plan 05: Port env without os.environ, checked upstream overrides, family-based disk check Summary

**A port now hands every child its own env dict (dotnet folder first on PATH, DOTNET_ROOT set) and never writes os.environ. Upstream's nx_extract build runs dotnet by absolute path. porter's four upstream overrides fail at import with the name of the missing attribute. The disk check counts the base, updates and DLC the scan picked, then checks again after extraction.**

## Performance

- **Duration:** 4 min (measured from the first edit; reading came before that)
- **Tasks:** 3 of 3
- **Files modified:** 4

## Accomplishments

- `Port.run` builds `self.env` from a copy of the environment: the dotnet folder goes first on PATH and DOTNET_ROOT is set. The two `os.environ` writes are gone. `use_profile_dir` reads and writes `self.env` only.
- `experimental_profile` loads `game.load(str(d))` and the derived profile loads `game.load(str(pdir / g.id))`. Both go by path, so dropping the environment writes never falls back to the repository's profile.
- Subtree (`nxnative/scripts/build_ipa_from_nsp.py`, 7 lines added and 6 removed):
  - `build_nx_extract` runs `shutil.which('dotnet', path=(env or os.environ).get('PATH')) or 'dotnet'`.
  - `survey` passes `env` to its nx_extract run.
  - `extract` and `extract_aoc` gain a trailing `env=None` that reaches `run`. `main()` is unchanged.
- `porter/upstream.py` `_overrides(m)` checks first and replaces second:
  - It checks that `{'nacp','pg'} <= co_names` of `main` and that `can_clone` and `profile_files` are callable. Each failed check is an explicit `raise AssertionError`, and `python -O` keeps it (checked by hand).
  - It then replaces nacp/pg, can_clone (off macOS) and profile_files (drops android.tsv), with one comment each.
- `Port.check_space(extracted=False)`:
  - It counts the distinct base, update and DLC paths in `self.fam` against the build folder, counted recursively.
  - `Port.run` calls `check_space(extracted=True)` right after `extract()`.
  - In that re-check, an output folder on another volume (st_dev differs) also needs RomFS + aoc + 1 GiB free there.

## Task Commits

1. **Task 1: porter's env with an absolute dotnet, os.environ untouched** - RED `9763546` (test), GREEN `3dc901c` (feat)
2. **Task 2: named, import-checked upstream overrides** - RED `5d6fe00` (test), GREEN `0796cbe` (feat)
3. **Task 3: disk check over the family and a re-check after extraction** - RED `cc60d80` (test), GREEN `ee220e4` (feat)

No REFACTOR commits (none needed).

## TDD Gate Compliance

- Task 1 RED: `.venv/bin/python -m unittest tests.test_porter.Env tests.test_porter.Experimental -v` exited 1. There were 4 FAILs and 1 ERROR:
  - `test_dotnet_absolute` got argv[0] as a bare `dotnet`.
  - `test_no_environ_writes` matched `os.environ['PATH'] =`.
  - `test_use_profile_dir_leaves_environ` saw the process DM_GAMES_DIR used instead of self.env's.
  - In Experimental, os.environ had changed.
  - `test_nx_extract_gets_env` hit a TypeError for the `env` keyword, which does not exist yet.

  `gsd_run check tdd-red-evidence` returned RED_EVIDENCE_OK for the target `tests.test_porter.Env.test_dotnet_absolute`. Semantic assessment: each test failed on the planned behaviour, with no load or fixture faults.
- Task 2 RED: `tests.test_porter.Overrides` exited 1. `test_missing_attribute_fails_loudly` raised ImportError because `_overrides` did not exist yet, which is the planned behaviour missing. `test_loaded_module` passed, as expected: it pins today's override behaviour as a regression test.
- Task 3 RED: `tests.test_porter.Misc` exited 1 with 2 ERRORs:
  - `test_disk_space` raised BuildError at the step that should pass, because the old top-level count included `other.nsp`, which is not in the family.
  - `test_disk_space_after_extraction` hit a TypeError for the `extracted` keyword, which does not exist yet.

  The first draft of `test_disk_space` passed against the old code by coincidence, so `other.nsp` was made 2 MiB to tell the two counts apart before the RED commit.
- All three GREEN commits come after their RED commits.

## Files Created/Modified

- `nxnative/scripts/build_ipa_from_nsp.py`: absolute dotnet in build_nx_extract; env on the survey, extract and extract_aoc nx_extract runs.
- `porter/pipeline.py`: self.env without os.environ writes; use_profile_dir on self.env; profiles loaded by path; env=self.env to extract and extract_aoc; check_space(extracted) plus the hook after extract().
- `porter/upstream.py`: `_overrides(m)` with import-time checks; one new clause in the header.
- `tests/test_porter.py`: new classes Env and Overrides; Experimental asserts os.environ is unchanged; Misc.test_disk_space rewritten; Misc.test_disk_space_after_extraction added.

## Decisions Made

- The test for "no assignment into os.environ" also refuses `os.environ.update`, `setdefault` and `pop` in pipeline.py, which is a little broader than plain assignments.
- Grep of the upstream helpers porter calls in-process (derive_profile, refine_after_rewrite, write_profile, split_shaders, provisional_prep): none calls `game.load` by title ID. Only upstream `main()` does, and porter never calls it. Nothing else needed a path.
- `porter/cli.py` `_with_progress` keeps its os.environ restore, as the plan says.

## Deviations from Plan

None - plan executed exactly as written. (One comment in use_profile_dir was reworded so the `game.load(str(` acceptance grep counts code only.)

## Issues Encountered

None.

## Verification

- `.venv/bin/python -m unittest tests.test_porter -v`: green.
- `QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover tests`: 170 tests, OK. `python3 -m unittest discover tests`: OK.
- `.venv/bin/python tests/arch_rules.py`: all checks passed.
- Every acceptance grep in Tasks 1 to 3 gives the planned count. The subtree diff is 7 lines added, within the cap of 8.

## Next Phase Readiness

Ready for 02-06. After the phase is pushed, check that `tests.test_porter.Env` passes on the windows-2025 fork-ci job (the human-check from the Task 1 tracer).

## Self-Check: PASSED

- Modified files exist; commits 9763546, 3dc901c, 5d6fe00, 0796cbe, cc60d80, ee220e4 are ancestors of HEAD.
