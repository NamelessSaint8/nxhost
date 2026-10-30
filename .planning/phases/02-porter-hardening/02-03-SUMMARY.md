---
phase: 02-porter-hardening
plan: 03
subsystem: infra
tags: [git-hooks, gitignore, arch-rules, third-party, ryujinx, flip, housekeeping]

requires:
  - phase: 01
    provides: tests/arch_rules.py rule 1, .githooks/commit-msg, the vendored Ryujinx and FLIP trees
provides:
  - devtools/hooks.py (one command sets core.hooksPath to .githooks)
  - "*.code-workspace ignored"
  - FLIP recorded as v1.7, NVlabs/flip b475eb4
  - nxnative/dm/third_party/ryujinx/nxnative-local.patch against Ryubing Canary-1.3.351 (475615f)
  - arch_rules join_literals() with a self-check on a split title ID
  - tests/test_housekeeping.py (Hooks, Records, UpstreamOutput)
affects: [02-10 closure table, Ryujinx re-vendor, upstream subtree pulls]

actuals:
  tokens: 13709
  tasks: 3
  commits: 5
plan_head_before: f20f623b97bb3dc474dff7f92b520dec2f803734
plan_head_after: 477430e12323f7daf3dc7158dbe77b6ac6183747

tech-stack:
  added: []
  patterns:
    - "Upstream output strings porter parses are pinned by reading the sources as text (ast / regex), never importing engine modules"
    - "Vendored-code local changes live as a git-apply patch beside the vendored folder"

key-files:
  created:
    - devtools/hooks.py
    - tests/test_housekeeping.py
    - nxnative/dm/third_party/ryujinx/nxnative-local.patch
  modified:
    - README.md
    - .gitignore
    - tests/arch_rules.py
    - nxnative/dm/third_party/README.md
    - nxnative/dm/third_party/ryujinx/README.md

key-decisions:
  - "join_literals matches a literal plus the run after it, so literals pair left to right as rule 1's blanking does (a regex starting at a closing quote could blank real code)"
  - "The Ryujinx patch paths are relative to nxnative/dm/third_party/ryujinx/ (a/src/..., b/src/...); in-repo apply is git apply --directory=nxnative/dm/third_party/ryujinx"
  - "The unmarked Ryujinx hunks are one feature: the fixed-input geometry-as-compute path for dmsh_geometry.py (QueryGeometryInputFixed); listed per file in ryujinx/README.md for a re-vendor to check"

patterns-established:
  - "tests/test_housekeeping.py: stdlib-only repository records, runs without lz4"

requirements-completed: [HARD-10]

coverage:
  - id: D1
    description: "python devtools/hooks.py sets core.hooksPath = .githooks, idempotently; README points at it"
    requirement: HARD-10
    verification:
      - kind: unit
        ref: "tests/test_housekeeping.py#Hooks.test_sets_hooks_path_idempotently"
        status: pass
      - kind: unit
        ref: "tests/test_housekeeping.py#Hooks.test_readme_points_at_script"
        status: pass
    human_judgment: false
  - id: D2
    description: "*.code-workspace is ignored by git"
    requirement: HARD-10
    verification:
      - kind: unit
        ref: "tests/test_housekeeping.py#Hooks.test_workspace_ignored"
        status: pass
    human_judgment: false
  - id: D3
    description: "FLIP recorded as v1.7, NVlabs/flip b475eb4bf394ab877c42166c9eb0a84a02cc5b14"
    requirement: HARD-10
    verification:
      - kind: unit
        ref: "tests/test_housekeeping.py#Records.test_flip_version"
        status: pass
    human_judgment: false
  - id: D4
    description: "Ryujinx local changes as nxnative-local.patch against Canary-1.3.351; base + patch reproduces the vendored tree"
    requirement: HARD-10
    verification:
      - kind: unit
        ref: "tests/test_housekeeping.py#Records.test_ryujinx_patch"
        status: pass
      - kind: other
        ref: "scratch: clean 475615f checkout + git apply nxnative-local.patch, diff -r against vendored src/ (empty); git apply --check -R --directory=nxnative/dm/third_party/ryujinx in the repo (ok)"
        status: pass
    human_judgment: false
  - id: D5
    description: "arch_rules joins split string literals before searching for title IDs, with a self-check"
    verification:
      - kind: unit
        ref: "python tests/arch_rules.py (PASS arch_rules joins split string literals); tests/test_architecture.py"
        status: pass
    human_judgment: false
  - id: D6
    description: "Upstream output porter parses is pinned (shader_vk.py summary lines, pipeline.py regexes, build_sources keys)"
    verification:
      - kind: unit
        ref: "tests/test_housekeeping.py#UpstreamOutput"
        status: pass
    human_judgment: false

duration: 7min
completed: 2026-10-30
status: complete
---

# Phase 2 Plan 03: Repository Housekeeping Summary

**`python devtools/hooks.py` turns the commit hook on, `*.code-workspace` is ignored, FLIP and Ryujinx have their real upstream versions recorded, Ryujinx's local changes are a proven `git apply` patch against Canary-1.3.351, and arch_rules now catches a title ID split across string concatenation.**

## Performance

- **Duration:** about 7 min
- **Started:** 2026-10-30T17:42:15Z
- **Completed:** 2026-10-30T17:49Z
- **Tasks:** 3
- **Files modified:** 8 (3 new)

## Accomplishments

- `devtools/hooks.py` sets `core.hooksPath` to `.githooks` in its own clone. Running it twice is safe, and README's Commit messages section now says to run it. Per D-11, nothing checks whether it was run.
- `.gitignore` ignores `*.code-workspace`, so `nx2android.code-workspace` no longer shows as untracked. The file itself was left alone.
- `nxnative/dm/third_party/README.md` records FLIP as v1.7, NVlabs/flip commit `b475eb4bf394ab877c42166c9eb0a84a02cc5b14` (2025-11-07).
- `nxnative/dm/third_party/ryujinx/nxnative-local.patch`: 15 files of `Ryujinx.Graphics.Shader`, 245 lines added and 29 removed (274 changed lines), 652 lines of patch. Against Canary-1.3.351, `Ryujinx.Common` and `Spv.Generator` are identical.
  - Proof: a clean checkout of 475615f's three projects plus `git apply` of the patch gives no difference under `diff -r` against the vendored `src/` (tracked files only, so no bin/ or obj/).
  - The patch also reverse-applies in the repo (`git apply --check -R --directory=nxnative/dm/third_party/ryujinx`).
  - Both READMEs now name the base as Canary-1.3.351 (475615f); neither says "Ryujinx 1.3.2" any more.
  - `ryujinx/README.md` adds the marked changes it did not list before (InstEmitFlowControl BRX, the passthrough in TranslatorContext and AttributeUsage), the unmarked hunks one per file, and a Re-vendoring paragraph.
- `tests/arch_rules.py` has `join_literals()`. Rule 1 now joins `"0100" "000000AAA000"` and `'0100' + '000000AAA000'` (across newlines too) into one literal before it blanks literals, and a self-check confirms GAME_RX finds the joined ID.
- `tests/test_housekeeping.py` pins the upstream strings porter parses: shader_vk.py's `translating N shaders` and `N of M shaders` prints, the matching regexes in pipeline.py, and the five `build_sources` / `shader_sources` keys that `check_graphics` reads.

## Task Commits

1. **Task 1: hook bootstrap and ignored workspaces** (tracer, TDD): `da2e36d` (test, RED), `8a846a6` (feat, GREEN)
2. **Task 2: FLIP version, join_literals, upstream-output pins** (TDD): `9d60c68` (test, RED), `3028f3d` (feat, GREEN)
3. **Task 3: Ryujinx patch against its real base**: `477430e` (chore)

## TDD Gate Compliance

- **Task 1 RED:** `.venv/bin/python -m unittest tests.test_housekeeping.Hooks -v` exited 1.
  - The classifier returned `RED_EVIDENCE_OK` for target `test_workspace_ignored`.
  - Semantic check: all three tests failed for the planned reason. `devtools/hooks.py` did not exist (FileNotFoundError on the copy), README did not name it, and `git check-ignore` exited 1.
- **Task 1 GREEN:** 3/3 pass. Tracer gate (interactive, `end-of-phase`, automated-only verify): verify re-run green, then expansion.
- **Task 2 RED:** `.venv/bin/python -m unittest tests.test_housekeeping -v` exited 1.
  - The classifier returned `RED_EVIDENCE_OK` for target `test_flip_version`, which failed on its assertion (`'b475eb4' not found`).
  - The UpstreamOutput tests passed at RED by design: they pin output that already exists, so they fail only when upstream wording changes.
  - The arch_rules self-check went into the GREEN commit together with `join_literals`, because it cannot exist before the function does.
- **Task 2 GREEN:** all tests pass and `arch_rules.py` prints `PASS  arch_rules joins split string literals`.
- Task 3 is `type="auto"` with no `tdd` attribute. Its test was added in the same commit.

## Files Created/Modified

- `devtools/hooks.py`: `git config core.hooksPath .githooks` for the clone
- `README.md`: Commit messages section runs `python devtools/hooks.py`
- `.gitignore`: editor workspace section, `*.code-workspace`
- `tests/arch_rules.py`: `LIT_RUN`, `join_literals()`, rule 1 joins before it blanks, the self-check
- `tests/test_housekeeping.py`: Hooks, Records, UpstreamOutput
- `nxnative/dm/third_party/README.md`: FLIP version cell; ryujinx row base and patch
- `nxnative/dm/third_party/ryujinx/README.md`: base, newly listed changes, unmarked hunks, Re-vendoring
- `nxnative/dm/third_party/ryujinx/nxnative-local.patch`: the local changes (data file, LF)

## Decisions Made

- `join_literals` matches a literal plus any run of literals after it, so literals pair left to right, as rule 1's blanking pairs them. A pattern that could start at a closing quote would treat code between two literals as a literal and blank it, which would hide that code from GAME_RX.
- There is a `shortcut:` comment for escaped quotes.
- The patch paths are relative to the ryujinx folder. Re-vendoring runs `git apply --directory=nxnative/dm/third_party/ryujinx …` from the repo root.
- Review of the unmarked hunks (RESEARCH Open Question 4): they are a single local feature, the fixed-input geometry-as-compute path for `dmsh_geometry.py`.
  - The feature is switched on through `IGpuAccessor.QueryGeometryInputFixed` (default false), which dmsh_xlate's `Program.cs` implements.
  - `VertexInfoBufferField.GeometryCounts`, which it uses, is already in the base.
  - Each hunk is listed in ryujinx/README.md so a re-vendor can check it.

## Deviations from Plan

None. The plan ran as written. The only process notes are the UpstreamOutput tests passing at RED (they pin existing output) and the arch_rules self-check landing in GREEN, both explained under TDD Gate Compliance.

## Issues Encountered

None. The precondition held: `git ls-remote` listed 475615f as `master`, `HEAD` and the peeled `Canary-1.3.351` tag.

## Threat Flags

None. T-02-08, T-02-09 and T-02-10 are mitigated as planned. The Ryujinx clone was only read to make the diff, in the scratchpad; it was never built or run.

## User Setup Required

None. This clone still has `core.hooksPath` unset. Run `python devtools/hooks.py` once if you want the hook here.

## Next Phase Readiness

The HARD-10 items owned by this plan are closed: hook bootstrap, `*.code-workspace`, FLIP version and the Ryujinx patch. The probe signer was 02-02's item; the one language list is 02-09's. The 02-10 closure table can cite `tests/test_housekeeping.py` and the arch_rules self-check for the two CONCERNS.md fragile-area items.

Full suite: `.venv/bin/python -m unittest discover tests`, 145 tests OK. `python3` (3.14.5) gives the same result. `tests/arch_rules.py`: all checks passed.

## Self-Check: PASSED

- FOUND: devtools/hooks.py, tests/test_housekeeping.py, nxnative/dm/third_party/ryujinx/nxnative-local.patch, tests/arch_rules.py
- FOUND commits on HEAD: da2e36d, 8a846a6, 9d60c68, 3028f3d, 477430e
- Acceptance criteria re-run, all PASS:
  - `grep -c core.hooksPath devtools/hooks.py` = 3
  - README names devtools/hooks.py (1)
  - `grep -cx '*.code-workspace' .gitignore` = 1
  - `git check-ignore` exits 0
  - b475eb4 appears once in the third_party README
  - `def join_literals` appears once in arch_rules.py
  - the patch's first 10 bytes are `diff --git`
  - 475615f appears in ryujinx/README.md (1)
  - "Ryujinx 1.3.2" appears 0 times in both READMEs

---
*Phase: 02-porter-hardening*
*Completed: 2026-10-30*
