---
phase: 02-porter-hardening
plan: 08
subsystem: porter
tags: [fpslocker, pins, supply-chain, sha256, atomic-write]

requires:
  - phase: 02-porter-hardening
    provides: "02-04 porter/pins.py manifest and untested-fallback pattern; 02-05 self.env; 02-06 write_whole"
provides:
  - "pins.FPSLOCKER: one masagrator/FPSLocker-Warehouse commit (575eef0824e3519e6567c3fdb27707136448923a)"
  - "fpslocker.fetch() -> (text, commit) or None: pinned commit first, v4 head (GitHub API) on a 404; head() rejects anything but 40 hex digits with OSError"
  - "fpslocker.url(title_id, build_id, ref=None) and RAW with a {ref} field; HEAD_API"
  - "fps_unlock: src names the URL at the commit, the commit and the config's SHA-256 (log, fpslock.tsv, patches.py); [RED] untested line off the pin"
  - "The offline cache <build ID>.yaml is written whole with a '# FPSLocker-Warehouse commit <sha>' first line; an older cache reads as commit unknown"
affects: [02-porter-hardening, gui, packaging]

actuals:
  tokens: 3259
  tasks: 2
  commits: 3
plan_head_before: d6bf51785b329a6a3285a3fc3ba439766da60582
plan_head_after: 4928b5d287ef94c42128393964bd01736cbbe2ff

tech-stack:
  added: []
  patterns:
    - "A third-party data source is fetched at a pinned commit; a newer one is taken only as a visible [RED] untested fallback"

key-files:
  created: []
  modified:
    - porter/pins.py
    - porter/fpslocker.py
    - porter/pipeline.py
    - tests/test_porter.py
    - docs/ARCHITECTURE.md

key-decisions:
  - "HARD-03/D-03: FPSLocker configs come from pins.FPSLOCKER; a 404 there falls back to v4's head, logged [RED] untested; head == pin is not fetched twice"
  - "A pre-pin cache (no commit line) is used offline as commit unknown, its URL shown at v4 (where it came from), and flagged untested"

patterns-established:
  - "Cache files carry their provenance in a first comment line, written whole with write_whole"

requirements-completed: [HARD-03, PKG-07]

coverage:
  - id: D1
    description: "A config is fetched at the pinned commit without calling the GitHub API"
    requirement: "HARD-03"
    verification:
      - kind: unit
        ref: "tests/test_porter.py#FpsLocker.test_pinned_commit"
        status: pass
    human_judgment: false
  - id: D2
    description: "A build missing at the pin falls back to v4's head; none anywhere is None; a bad head answer is an OSError"
    requirement: "HARD-03"
    verification:
      - kind: unit
        ref: "tests/test_porter.py#FpsLocker.test_head_fallback"
        status: pass
      - kind: unit
        ref: "tests/test_porter.py#FpsLocker.test_none_anywhere"
        status: pass
      - kind: unit
        ref: "tests/test_porter.py#FpsLocker.test_bad_head"
        status: pass
    human_judgment: false
  - id: D3
    description: "The commit and SHA-256 reach the log, fpslock.tsv and patches.py; the cache keeps the commit and offline ports read it back (or 'unknown')"
    requirement: "PKG-07"
    verification:
      - kind: unit
        ref: "tests/test_porter.py#FpsLocker.test_source_recorded"
        status: pass
      - kind: unit
        ref: "tests/test_porter.py#FpsLocker.test_fps_unlock_records_commit"
        status: pass
      - kind: unit
        ref: "tests/test_porter.py#FpsLocker.test_url"
        status: pass
    human_judgment: false
  - id: D4
    description: "docs/ARCHITECTURE.md 60 fps paragraph and table row describe the pin, fallback, SHA-256 and cache commit line"
    verification:
      - kind: other
        ref: "grep -c FPSLOCKER / SHA-256 / 'never committed' docs/ARCHITECTURE.md; tests.test_architecture"
        status: pass
    human_judgment: false

duration: 3min
completed: 2026-10-30
status: complete
---

# Phase 2 Plan 08: FPSLocker Configs at a Pinned Commit Summary

**--fps60 fetches each build's FPSLocker-Warehouse config at the commit pinned in porter/pins.py, falls back to v4's head only as a logged "[RED] untested" config, and records the commit and the config's SHA-256 in the port log, fpslock.tsv, patches.py and a whole-written offline cache.**

## Performance

- **Duration:** 3 min
- **Started:** 2026-10-30T18:26:04Z
- **Completed:** 2026-10-30T18:28:42Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- `pins.FPSLOCKER` pins 575eef0824e3519e6567c3fdb27707136448923a. On 2026-10-30 a config answered 200 at it (`0100001019F6E000/D60A7F43A98034BE.yaml`), and the v4 head was still the same commit.
- `fpslocker.fetch` tries the pin first. On a 404 it asks the GitHub API for v4's head, and it never fetches the same commit twice. Any head answer that is not 40 hex digits, a rate-limit page included, raises OSError, which sends the port to its cached copy.
- `fps_unlock` builds the source as `<url at commit> (commit <12>, sha256 <64>)`. The final say line, `fpslock.tsv` and `patches.py` all carry it. A config from a commit other than the pin gets a `[RED] ... untested` line.
- The cache is written with `nsp.write_whole` and its first line is `# FPSLocker-Warehouse commit <sha>`. The plain `cache.write_text` that wrote it in place is gone.

## Task Commits

1. **Task 1 (RED): fetch tests** - `4b25c50` (test)
2. **Task 1 (GREEN): pinned fetch, head fallback, commit + SHA-256 in log/build folder** - `c2f949e` (feat)
3. **Task 2: 60 fps docs** - `4928b5d` (docs)

## Files Created/Modified
- `porter/pins.py` - adds the `FPSLOCKER` commit pin and how to bump it
- `porter/fpslocker.py` - adds `{ref}` in RAW, `HEAD_API`, `head()`, `_get`/`_at` helpers and `fetch()` returning (text, commit)
- `porter/pipeline.py` - `fps_unlock` hook lines only (plus `pins` in the import line): unpack the commit, compute the SHA-256, add the untested line, write the cache whole, read the commit line offline
- `tests/test_porter.py` - FpsLocker fetch tests over a faked urlopen, plus a `fps_unlock` test driven through `Port.__new__` (synthetic UNITY config only)
- `docs/ARCHITECTURE.md` - updates the 60 fps paragraph and the table row's output column

## Decisions Made
- A cache written before this phase is used offline with commit `unknown`. Its URL is shown at `v4`, the branch it came from, and it is flagged untested. The next online port rewrites it with a commit line.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing check] Added a test that drives fps_unlock itself**
- **Found during:** Task 1
- **Issue:** The plan's behaviours tested `fetch` and `convert`, but nothing covered the new cache parsing (commit line, or `unknown` for an old cache) or the untested line in `fps_unlock`.
- **Fix:** Added `FpsLocker.test_fps_unlock_records_commit`. It fakes `nso_image` and `fetch`, then checks online, offline, a pre-pin cache and the head fallback.
- **Files modified:** tests/test_porter.py
- **Committed in:** c2f949e

**Total deviations:** 1 auto-fixed (1 missing check). **Impact:** test-only, no scope change.

## Issues Encountered
None. The faked HTTPError (fp=None) prints a harmless ResourceWarning, the same one tests/test_fetch.py produces.

## Verification
- `.venv/bin/python -m unittest tests.test_porter.FpsLocker tests.test_tls`: 18 tests OK
- `QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover tests`: 201 tests OK
- `.venv/bin/python tests/arch_rules.py`: all checks passed
- Acceptance greps: no `/v4/SaltySD` left outside comments (0), `pins.FPSLOCKER` appears 4 times, `cache.write_text` is gone (0), `sha256` appears in pipeline.py (1), the pin is 40 hex digits; ARCHITECTURE.md mentions FPSLOCKER, SHA-256 and "never committed" (1 each)

## User Setup Required
None.

## Next Phase Readiness
Ready for 02-09. No warehouse config contents are committed: only the SHA is pinned, and the test fixtures are synthetic.

## Self-Check: PASSED
- Modified files exist; commits 4b25c50, c2f949e, 4928b5d are ancestors of HEAD.
