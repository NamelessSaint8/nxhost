---
phase: 02-porter-hardening
plan: 02
subsystem: signing
tags: [mkapk, signing-key, apk, doctor, probes]

requires:
  - phase: 02-porter-hardening
    provides: "nothing from 02-01 (same wave, independent)"
provides:
  - "mkapk.py save_key (mkstemp 0600, fsync / F_FULLFSYNC, os.link no-clobber publish) and load_key (tighten to 0600, refuse unreadable with [RED] recovery)"
  - "APK written to <out>.partial and os.replace'd over <out>"
  - "porter doctor's required 'Signing key' row; toolchain.require() stops a port on a broken key"
  - "one APK signer in the repository: the probe app's own mkapk.py is deleted"
affects: [porter, packaging, probes, gui-setup-tab]

actuals:
  tokens: 7364
  tasks: 3
  commits: 5
plan_head_before: 49ddc579336feafa0288bb7732d15fb6494144ba
plan_head_after: 84f6be389af9342f96d7989eacb3340ed0b439ac

tech-stack:
  added: []
  patterns:
    - "Publish a write-once file with mkstemp in the same folder + fsync + os.link; FileExistsError means another writer won, so load theirs"
    - "A file the tool must never replace is checked as a required doctor row, so the port stops before any stage"

key-files:
  created:
    - tests/test_signing.py
  modified:
    - nxnative/dm/android/apk/mkapk.py
    - porter/toolchain.py
    - probes/app/probeapp.c
    - RESEARCH.md
    - .claude/skills/switch-android-port/references/neo-case-study.md
    - packaging/INSTALL.md
  deleted:
    - probes/app/mkapk.py

key-decisions:
  - "The signing key is published with os.link (no-clobber), not os.replace, so two simultaneous first ports end with one signer"
  - "An existing group/other-readable key is tightened to 0600 on POSIX on its next use; Windows relies on %APPDATA%'s ACL"
  - "A JSON key that is not an object (AttributeError) counts as unreadable too, in both mkapk.py and the doctor row"
  - ".claude/CLAUDE.md line 351 was not edited by the executor: an agent may not change CLAUDE.md on its own authority; the user makes that one-line fix"

patterns-established:
  - "Write-once secret: mkstemp + fsync + os.link, loser loads the winner"

requirements-completed: [HARD-02, HARD-10]

coverage:
  - id: D1
    description: "A new signing key is written whole and 0600, no temp file is left, and the APK is written via .partial"
    requirement: HARD-02
    verification:
      - kind: unit
        ref: "tests/test_signing.py#Key.test_new_key_whole_and_private"
        status: pass
    human_judgment: false
  - id: D2
    description: "Two first ports at once end with one signer; a reused key keeps the signer"
    requirement: HARD-02
    verification:
      - kind: unit
        ref: "tests/test_signing.py#Key.test_two_first_ports_one_signer"
        status: pass
      - kind: unit
        ref: "tests/test_signing.py#Key.test_reuse_keeps_signer"
        status: pass
    human_judgment: false
  - id: D3
    description: "A garbage or unreadable key is refused with the [RED] recovery text and left untouched; a world-readable key is tightened to 0600"
    requirement: HARD-02
    verification:
      - kind: unit
        ref: "tests/test_signing.py#Key.test_garbage_key_refused"
        status: pass
      - kind: unit
        ref: "tests/test_signing.py#Key.test_unreadable_key_refused"
        status: pass
      - kind: unit
        ref: "tests/test_signing.py#Key.test_world_readable_tightened"
        status: pass
    human_judgment: false
  - id: D4
    description: "porter doctor shows a required Signing key row; a broken key is red and require() stops the port"
    requirement: HARD-02
    verification:
      - kind: unit
        ref: "tests/test_signing.py#Preflight"
        status: pass
      - kind: other
        ref: ".venv/bin/python -m porter doctor --json (contains \"name\": \"Signing key\")"
        status: pass
    human_judgment: false
  - id: D5
    description: "The probe app's own signer is deleted and probeapp.c's header packs it with nxnative/dm/android/apk/mkapk.py"
    requirement: HARD-10
    verification:
      - kind: unit
        ref: "tests/test_signing.py#Probe.test_one_signer"
        status: pass
    human_judgment: false
  - id: D6
    description: "Players get a signing-key backup and recovery note in packaging/INSTALL.md"
    requirement: HARD-02
    verification: []
    human_judgment: true
    rationale: "Wording and placement of player-facing docs need a human read"

duration: 4min
completed: 2026-10-30
status: complete
---

# Phase 2 Plan 02: Signing Key Hardening Summary

**mkapk.py now writes the signing key once (mkstemp 0600, fsync, os.link no-clobber) and refuses an unreadable key with a [RED] recovery message. It writes the APK through `.partial` + os.replace. `porter doctor` has a required Signing key row that stops a port before its first stage, and the probe app's duplicate signer is gone.**

## Performance

- **Duration:** 4 min
- **Started:** 2026-10-30T17:35:35Z
- **Completed:** 2026-10-30T17:39:54Z
- **Tasks:** 3
- **Files modified:** 8 (1 created, 6 modified, 1 deleted)

## Accomplishments
- New key: whole and 0600, or not written at all. On macOS the write is flushed with F_FULLFSYNC.
- When two first ports run at once, the second loads the first one's key, so both APKs carry the same signer.
- A key that exists but cannot be read or parsed stops mkapk.py with the backup / `--replace-signer` recovery. The file stays untouched and no new key is generated.
- An older key that group or others can read is set to 0600 on its next use.
- The APK never sits half-written at its final path.
- The `Signing key` doctor row (required) turns red for a broken key. `toolchain.require()` then raises ToolError, so `porter port` stops before extraction. The Setup tab shows the row with no GUI change, because it renders rows generically (checked in gui/app.py).
- The repository has one APK signer. probeapp.c's header gives the mkapk.py build line, and INSTALL.md tells players to back up `signing-key.json`.

## Task Commits

1. **Task 1: mkapk key and APK writes** (TDD tracer): RED `efa38fe` (test), GREEN `7ba30cd` (feat)
2. **Task 2: Signing key doctor row** (TDD): RED `387ab86` (test), GREEN `7403cec` (feat)
3. **Task 3: one signer (D-10)**: `84f6be3` (refactor; deletes probes/app/mkapk.py on purpose)

## TDD Gate Compliance

- Task 1 RED: `tests.test_signing.Key`. 5 of 6 tests failed on assertions: garbage key gave a JSONDecodeError traceback with no recovery text, mode 0644 instead of 0600, two first ports produced different signers, a chmod-000 key gave a PermissionError traceback, and a world-readable key was not tightened. `test_reuse_keeps_signer` passed at RED because it guards behaviour that already worked. Classifier: RED_EVIDENCE_OK (target `test_garbage_key_refused`). Semantic assessment: every failure was on the planned assertion, with no load or fixture errors.
- Task 2 RED: `tests.test_signing.Preflight`. 4 of 4 failed on `assertIn('Signing key', rows)`, so the row was missing. Classifier: RED_EVIDENCE_OK (target `test_broken_key_is_red`). The first draft's `next()` raised StopIteration ERRORs; I changed it to an assertion before recording RED.
- GREEN followed RED for both tasks. No REFACTOR commits.
- Tracer gate (Task 1): end-of-phase mode with automated-only verify. I re-ran the verify and it was green before expanding.

## Files Created/Modified
- `nxnative/dm/android/apk/mkapk.py`: save_key, load_key, main() uses them, APK via `.partial`, header Usage updated
- `porter/toolchain.py`: `_signing_key_check()` and the `Signing key` row in checks()
- `tests/test_signing.py`: Key (6), Preflight (4) and Probe (1) tests. A module-level first key is shared by all classes, and every path and NX2A_HOME is temporary.
- `probes/app/probeapp.c`: header build lines calling the committed signer
- `probes/app/mkapk.py`: deleted
- `RESEARCH.md`, `.claude/skills/switch-android-port/references/neo-case-study.md`: name the one signer
- `packaging/INSTALL.md`: "Your signing key" paragraph

## Decisions Made
See key-decisions in the frontmatter. The main one: publish with os.link, not os.replace (RESEARCH A9).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] A key file holding valid JSON that is not an object crashed instead of being refused**
- **Found during:** Task 1 and Task 2
- **Issue:** The planned exception list (OSError, ValueError, KeyError, TypeError) misses AttributeError, which `d.items()` raises on a JSON list or string.
- **Fix:** Added AttributeError to the caught exceptions in mkapk.py load_key and in the doctor row.
- **Files modified:** nxnative/dm/android/apk/mkapk.py, porter/toolchain.py
- **Committed in:** 7ba30cd, 7403cec

**2. [Rule 3 - Blocking] The shared test key moved to setUpModule**
- **Found during:** Task 2
- **Issue:** Key.tearDownClass deleted the shared key before Preflight could copy it.
- **Fix:** setUpModule/tearDownModule own the first key, held on a small `K` holder class.
- **Files modified:** tests/test_signing.py
- **Committed in:** 387ab86

**3. [Guardrail] .claude/CLAUDE.md line 351 not edited**
- **Found during:** Task 3
- **Issue:** The plan asked to replace the `probes/app/mkapk.py` mention in .claude/CLAUDE.md. My instructions do not let an agent change CLAUDE.md on its own authority.
- **Effect:** `git grep -l "probes/app/mkapk" -- ':!.planning'` still prints `.claude/CLAUDE.md`. All other Task 3 criteria pass.
- **User action:** on line 351, change `probes/` (C probes and `probes/app/mkapk.py`) to `probes/` (C probes; the probe app is packed by `nxnative/dm/android/apk/mkapk.py`).

---

**Total deviations:** 2 auto-fixed (1 bug, 1 blocking) and 1 guardrail skip.
**Impact on plan:** The auto-fixes widen correctness only. The guardrail skip leaves one stale path in the project instructions for the user to fix.

## Issues Encountered
None.

## User Setup Required
None. The one-line CLAUDE.md fix in deviation 3 is a doc edit, not setup.

## Verification
- `.venv/bin/python -m unittest tests.test_signing -v`: 11 tests OK
- `QT_QPA_PLATFORM=offscreen python3 -m unittest discover tests`: 138 tests OK (also OK with .venv/bin/python)
- `.venv/bin/python tests/arch_rules.py`: all checks passed
- `.venv/bin/python -m porter doctor --json`: has the `Signing key` row (ok, "made on the first port" on this machine; nothing was written)

## Next Phase Readiness
HARD-02 is done, along with HARD-10's probe-signer item. The other HARD-10 items (FLIP version, Ryujinx patch, hook bootstrap, `*.code-workspace`, language list) belong to other plans.

## Self-Check: PASSED
- FOUND: nxnative/dm/android/apk/mkapk.py, porter/toolchain.py, tests/test_signing.py, probes/app/probeapp.c, packaging/INSTALL.md; GONE as intended: probes/app/mkapk.py
- FOUND commits: efa38fe, 7ba30cd, 387ab86, 7403cec, 84f6be3

---
*Phase: 02-porter-hardening*
*Completed: 2026-10-30*
