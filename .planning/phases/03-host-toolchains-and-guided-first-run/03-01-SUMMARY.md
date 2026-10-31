---
phase: 03-host-toolchains-and-guided-first-run
plan: 01
subsystem: porter
tags: [porter, cli, setup, prod.keys, desktop-entry, first-run]

requires: []
provides:
  - "`porter setup --json`: the readiness document (ready, legal, steps legal/keys/tools/device, missing, notes, desktop, checks)"
  - "`porter config <key> [<value>] --json` answering {key, value} or {error}; `legal` config key that takes only the current notice version"
  - "porter/keys.py: prod.keys checked by key names and highest generation; emulator folder candidates per OS"
  - "`porter desktop-entry [--install] [--json]`: the Linux bundle's app menu entry"
affects: [03-05 first-run wizard, 03-07 shell, 03-08 bundle smoke test, 04 PORT-01 key generation]

actuals:
  tokens: 10339
  tasks: 3
  commits: 6
plan_head_before: 4fd1672b5df74d2e6bee30b52a8758efd1627176
plan_head_after: 3fbd61e3ba037e1c9f3dabf23448cd6990e60ecc

tech-stack:
  added: []
  patterns:
    - "One-shot readiness document built from one toolchain.checks() call; checks passed through unchanged as as_dict() rows"
    - "Settings written through `porter config ... --json` so the GUI gets a JSON answer"

key-files:
  created:
    - porter/setup.py
    - porter/keys.py
    - porter/desktop.py
    - tests/test_setup.py
    - tests/test_keys.py
    - tests/test_desktop.py
  modified:
    - porter/cli.py
    - porter/config.py
    - porter/runlog.py
    - docs/ARCHITECTURE.md

key-decisions:
  - "Legal notice VERSION = 1; config legal accepts only str(setup.VERSION); setup never writes config.json"
  - "`missing` takes the keys step (not the doctor's prod.keys row) for prod.keys, then every other failing required check row in checks order"
  - "Desktop Exec quoting follows the spec exactly: a literal backslash is four in the file (RESEARCH's example wrote three)"
  - "A path with a line break is refused for the .desktop entry, since it would inject keys"
  - "`config --json` with no key prints the whole config as one JSON object"

patterns-established:
  - "TDD RED with interface stubs committed beside the test so RED fails on assertions, not on import"

requirements-completed: [FRUN-01, FRUN-02, FRUN-03, TOOL-04]

coverage:
  - id: D1
    description: "`porter setup --json` answers the readiness document with fixed step order, D-03 ready rules and missing in step order; no config.json still answers"
    requirement: FRUN-03
    verification:
      - kind: unit
        ref: "tests/test_setup.py#Report"
        status: pass
      - kind: integration
        ref: "tests/test_setup.py#Cli.test_no_config, Cli.test_checks_match_doctor"
        status: pass
    human_judgment: false
  - id: D2
    description: "Legal notice recorded only through `config legal <current version> --json`; `config <key> <value> --json` answers {key, value} or {error}"
    requirement: FRUN-01
    verification:
      - kind: integration
        ref: "tests/test_setup.py#Cli.test_legal_round_trip, Cli.test_config_json_any_key"
        status: pass
    human_judgment: false
  - id: D3
    description: "prod.keys checked by key names and generation (1 MB cap, no values out) and found in the emulator folders per OS"
    requirement: FRUN-01
    verification:
      - kind: unit
        ref: "tests/test_keys.py#Check, Candidates"
        status: pass
    human_judgment: false
  - id: D4
    description: "Missing items listed in step order"
    requirement: FRUN-02
    verification:
      - kind: unit
        ref: "tests/test_setup.py#Report.test_missing_order"
        status: pass
    human_judgment: false
  - id: D5
    description: "`desktop-entry --install` writes the Linux menu entry and icon with spec-quoted Exec, refuses symlinks and refuses outside the Linux bundle; setup writes nothing there"
    requirement: TOOL-04
    verification:
      - kind: unit
        ref: "tests/test_desktop.py#Entry"
        status: pass
    human_judgment: false
  - id: D6
    description: "The menu entry actually appears and launches from a real Linux desktop's app menu"
    verification: []
    human_judgment: true
    rationale: "Needs the frozen Linux bundle and a desktop session; only the file contents are tested here"

duration: 8min
completed: 2026-10-31
status: complete
---

# Phase 3 Plan 01: Setup readiness, prod.keys check and Linux menu entry Summary

**`porter setup --json` now returns one readiness document: the legal notice and its accepted version, the prod.keys key-name and generation check across emulator folders, the toolchain rows, and missing items in order. `porter desktop-entry --install` writes a spec-quoted Linux menu entry.**

## Performance

- **Duration:** 8 min
- **Started:** 2026-10-31T15:24:29Z
- **Completed:** 2026-10-31T15:32:30Z
- **Tasks:** 3
- **Files modified:** 10 (plus 3 RED evidence records)

## Accomplishments

- `porter/setup.py`: `VERSION`, `TEXT`, `LINKS`, `TOOLS`, `accepted(cfg)`, `report(cfg)` and `main(a)`. The document's shape matches the plan's interfaces block exactly, and `checks` is `doctor --json`'s list unchanged.
- `porter config <key> [<value>] --json`: answers `{key, value}` or `{error}`. `legal` accepts only `str(setup.VERSION)`. Without `--json`, behaviour is unchanged.
- `porter/keys.py`:
  - `check(path)` needs `header_key` (64 hex digits) and at least one usable generation, and reports the highest generation as an int. A file over 1 MB is not read. Key values are dropped as the file is parsed.
  - `candidates()` searches the Ryujinx/Ryubing folders, the yuzu family, the Flatpak globs and `~/.switch`.
  - `step(cfg)` adds the `found` list.
- `porter/desktop.py`: `entry`, `target`, `install` and `main`. Files are written through a temp file and replaced. A symlinked entry or folder is refused. `--install` refuses to run outside the Linux bundle.
- `runlog.run` lets `setup` through on an old Python, as it does `doctor`.
- `docs/ARCHITECTURE.md` documents `setup --json`, `config --json` and `desktop-entry`.

## Task Commits

1. **Task 1 (tracer): setup --json end to end.** RED `0bb5606`, GREEN `315f9d5`.
2. **Task 2: prod.keys check and emulator folders.** RED `dc745fd`, GREEN `3d48e2e`.
3. **Task 3: desktop-entry --install.** RED `aac824d`, GREEN `3fbd61e`.

## TDD Gate Compliance

Every task has a `test(03-01)` commit followed by a `feat(03-01)` commit. Each RED record was checked by `gsd-tools check tdd-red-evidence`, which returned `RED_EVIDENCE_OK` for all three:

- **T1, `Report.test_shape`:** failed on the document-keys assertion against a stub `report()` that returned `{}`.
- **T2, `Check.test_complete`:** failed on the check-result assertion against a stub `check()`. `test_no_values_out` passes on the stub by design: it is a guard, not a RED target.
- **T3, `Entry.test_quoting`:** failed on `assertIn('Exec', …)` against a stub `entry()`.

The records are in `.planning/phases/03-host-toolchains-and-guided-first-run/tdd/03-01-t{1,2,3}-red.json`. Each RED commit also adds interface stubs (for example `porter/setup.py` returning `{}`), so RED fails on an assertion and not as an import or load failure. No REFACTOR commits were needed.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Exec backslash quoting in RESEARCH's example was one level short**
- **Found during:** Task 3
- **Issue:** The `.desktop` example in RESEARCH builds `'\\\\' + c`, which writes three backslashes for a literal `\`. The spec needs four: `\\` at the quote level, then each `\` doubled at the string level.
- **Fix:** `desktop._exec` escapes at the quote level, then doubles every backslash. `Entry.test_quoting` pins the exact Exec value.
- **Files modified:** porter/desktop.py, tests/test_desktop.py
- **Commit:** 3fbd61e

**2. [Rule 2 - Security] A path with a line break is refused for the .desktop entry**
- **Found during:** Task 3 (threat T-03-03)
- **Issue:** A newline in the bundle path would end the Exec, TryExec or Icon line, and the rest of the path could add keys of its own.
- **Fix:** `entry()` raises `DesktopError` when either path contains `\r` or `\n`. The temp file uses `mkstemp` (O_EXCL) instead of a fixed `.tmp` name.
- **Files modified:** porter/desktop.py, tests/test_desktop.py
- **Commit:** 3fbd61e

**3. [Rule 2 - Missing] `config --json` with no key printed the text table**
- **Found during:** Task 1
- **Issue:** `porter config --json` would have printed the human-readable table, which a JSON reader cannot parse.
- **Fix:** It now prints `config.load()` as one JSON object.
- **Files modified:** porter/cli.py
- **Commit:** 315f9d5

**Total deviations:** 3 auto-fixed (1 bug, 2 missing critical). **Impact:** all three stay inside the plan's files and leave the document shape unchanged.

## Known Stubs

None. The RED-commit stubs in porter/setup.py, porter/keys.py and porter/desktop.py were all replaced by their GREEN commits.

## Verification

- `.venv/bin/python -m unittest tests.test_setup tests.test_keys tests.test_desktop tests.test_cli tests.test_toolchain`: OK.
- `QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover tests`: 263 tests, OK.
- `.venv/bin/python tests/arch_rules.py`: exit 0.
- Acceptance greps all match:
  - `'setup': cmd_setup` and `'desktop-entry': cmd_desktop` appear once each in porter/cli.py.
  - `'legal'` appears once in porter/config.py.
  - porter/setup.py defines `def report` and porter/keys.py defines `def candidates`.
  - `setup --json` appears twice in docs/ARCHITECTURE.md.
  - `git ls-files tests` lists no `*.keys` file.
- `porter desktop-entry --install --json` from the checkout prints an `{"error"}` document and exits 1.

## Next Phase Readiness

The document is ready for 03-05 (the wizard). Two follow-ups from RESEARCH are still open and belong to later plans:
- `setup` needs adding to `gui/runner.py` `TIMEOUTS` (45 s).
- `tests/fixtures/bridge/fake_porter.py` needs a `setup` answer (RESEARCH Pitfall 9).

## Self-Check: PASSED
