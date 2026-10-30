---
phase: 02-porter-hardening
plan: 11
subsystem: porter
tags: [zip, symlink, zip-slip, fetch, unittest]
status: complete

requires:
  - phase: 02-porter-hardening
    provides: "02-04's _refuse_names, links-last _unzip and _install's except BaseException cleanup"
provides:
  - "porter/fetch.py _unzip: links made in one pass (absolute target or a folder outside refused when made), then every link resolved against the final tree"
  - "tests/test_fetch.py Unpack.test_link_through_later_link_refused (subTests forward, reversed)"
  - "CONCERNS.md zip-symlink closure row true as written, evidence names the new test"
affects: [porter, fetch, CONCERNS closure, HARD-01, TEST-01]

actuals:
  tokens: 1448
  tasks: 2
  commits: 3
plan_head_before: 1490dd2488932f2ee116956e26b7bf2fb147fa4d
plan_head_after: 0771093d9b2689ebea155110d046113c61667363

tech-stack:
  added: []
  patterns:
    - "Archive links: create with a creation-time folder check, then validate all of them against the final tree"

key-files:
  created: []
  modified:
    - porter/fetch.py
    - tests/test_fetch.py
    - .planning/codebase/CONCERNS.md

key-decisions:
  - "Zip links are checked in two passes: folder check when each link is made (nothing is ever created outside), full resolve of every link once all exist (order no longer matters)"

patterns-established:
  - "Order-independent link check: resolve every link only after the last one exists"

requirements-completed: [HARD-01, TEST-01]

coverage:
  - id: D1
    description: "A zip whose link runs through a later link is refused whole, in either member order, naming member a, leaving no .unpack and nothing outside"
    requirement: HARD-01
    verification:
      - kind: unit
        ref: "tests/test_fetch.py#Unpack.test_link_through_later_link_refused"
        status: pass
      - kind: unit
        ref: "tests/test_fetch.py#Unpack.test_escaping_links_refused"
        status: pass
    human_judgment: false
  - id: D2
    description: "Valid archives with internal links (the NDK shader-tools shape) still unpack with links and modes"
    requirement: TEST-01
    verification:
      - kind: unit
        ref: "tests/test_fetch.py#Unpack.test_valid_zip_kept"
        status: pass
    human_judgment: false
  - id: D3
    description: "CONCERNS.md zip-symlink closure row names test_link_through_later_link_refused"
    requirement: TEST-01
    verification:
      - kind: other
        ref: "grep -c test_link_through_later_link_refused .planning/codebase/CONCERNS.md == 1"
        status: pass
    human_judgment: false

duration: 2min
completed: 2026-10-30
---

# Phase 2 Plan 11: Zip link-order escape (CR-01) Summary

**`_unzip` now makes every zip link with a creation-time folder check, then resolves all of them against the finished tree, so a link through a link that comes later in the archive is refused in either order.**

## Performance

- **Duration:** 2 min
- **Started:** 2026-10-30T20:06:03Z
- **Completed:** 2026-10-30T20:08:20Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- CR-01 closed: the verifier's three-entry zip (`d1/d2/keep.txt`, `a -> d1/d2/b/../../../escaped`, `d1/d2/b -> ../..`) raises `BuildError` naming `a`, in forward and reversed order. `_install` removes `.x.unpack` and nothing appears outside it.
- `d -> ..` followed by `d/x -> y` is still refused while the links are being made, so no link is ever created outside the unpack folder (checked by hand against a scratch folder).
- The CONCERNS.md closure row for zip symlinks is true again and names its test.

## Task Commits

1. **Task 1 RED: failing test for a link through a later link**: `9f93d8d` (test)
2. **Task 1 GREEN: check every zip link against the final tree**: `cb7c1d5` (fix)
3. **Task 2: CONCERNS closure row names the test**: `0771093` (docs)

## Files Created/Modified
- `porter/fetch.py`: `_unzip` link handling split into a make pass and a final-tree check pass (CR-01 comment)
- `tests/test_fetch.py`: `Unpack.test_link_through_later_link_refused` (POSIX only, like `test_escaping_links_refused`)
- `.planning/codebase/CONCERNS.md`: one closure row (Closed-by gains 02-11; evidence names the test)

## TDD Gate Compliance

- **RED:** `9f93d8d`. `.venv/bin/python -m unittest tests.test_fetch.Unpack.test_link_through_later_link_refused -v` exited 1. The `forward` subTest failed with `AssertionError: BuildError not raised` and `reversed` passed, as the plan predicted. `gsd_run check tdd-red-evidence` returned `RED_EVIDENCE_OK` (`target_test_failed`, format unittest, 1 test, 1 fail). Semantic assessment: the target test ran and failed on the planned assertion (`refused()`'s `assertRaises(BuildError)`), not on an import, fixture or syntax error. The pre-fix code really accepts the hostile archive.
- **GREEN:** `cb7c1d5`, committed as `fix(porter): ...` because the plan says so. The gate's `feat(02-11)` grep therefore finds nothing. This is advisory only: `workflow.tdd_mode` is off, and the GREEN commit comes after the RED commit.
- **REFACTOR:** none needed.

## Decisions Made
- Pass 1 keeps the folder check at creation time. Pass 2 resolves `(into / name)` for every link made. A refusal in either pass gives the same message, built by one local `refuse` lambda so the text stays identical.

## Deviations from Plan

None. The plan was executed as written.

## Issues Encountered
None

## Verification
- `.venv/bin/python -m unittest tests.test_fetch -v`: 13 tests OK. `test_link_through_later_link_refused`, `test_escaping_links_refused` and `test_valid_zip_kept` all report `ok` (none skipped on macOS).
- `QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover tests`: 222 tests OK (221 before this plan).
- `.venv/bin/python tests/arch_rules.py`: all checks passed.
- Verifier repro re-run: `fetch._unzip` on the three-entry zip raises `t.zip: refused, link a → d1/d2/b/../../../escaped leaves the unpack folder`.
- Acceptance greps: CR-01 appears in fetch.py (1); `except BaseException: shutil.rmtree(tmp` (1); `t.extractall(into, filter='data')` (1); the test def (1); the escaped target (1); the CONCERNS test name (1); CONCERNS still has 84 table rows; numstat was `1 1`.
- Not run here: the fork-ci.yml Linux and macOS CI jobs (manual or CI).

## Known Stubs
None

## User Setup Required
None. No external service needs configuring.

## Next Phase Readiness
- HARD-01 and TEST-01 are ready for `/gsd-verify-work` to re-check. Edge HARD-01 stays flagged for manual review, as the planner asked.
- T-02-32 (link loops) is accepted with no test, per the plan.

## Self-Check: PASSED
- FOUND: porter/fetch.py, tests/test_fetch.py, .planning/codebase/CONCERNS.md
- FOUND: 9f93d8d, cb7c1d5, 0771093 (ancestors of HEAD)

---
*Phase: 02-porter-hardening*
*Completed: 2026-10-30*
