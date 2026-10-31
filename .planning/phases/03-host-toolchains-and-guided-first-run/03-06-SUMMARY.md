---
phase: 03-host-toolchains-and-guided-first-run
plan: 06
subsystem: porter
tags: [adb, devices, udev, distro, push-compression, cli-json]

requires:
  - phase: 03-02
    provides: "hosttools.push_flags(exe), ADB_Z_MAJOR = 30"
  - phase: 03-04
    provides: "distro.family(osr), distro.ADB, distro.adb_hint()"
provides:
  - "porter/adb.py: ROW regex (serial incl. `(no serial number)`, whole state text); Adb.nz cached push flags used at both push sites"
  - "porter/distro.py: UDEV, FIXES, state_kind(state), device_fix(state, osr=None)"
  - "`devices --json` rows add `detail` (adb's state text) and `fix`; `state` reads `no permissions` for that family; no adb with --json answers {error} with adb_hint()"
affects: [03-08 manual UAT (unauthorized -> device, Linux no permissions), 03-10 device page and device list]

actuals:
  tokens: 5548
  tasks: 2
  commits: 4
plan_head_before: f072595eefcb9fcd021d67c5d89b787ccdb35670
plan_head_after: 87e644d73bfd12e08630dd52b0ce289affcb89df

tech-stack:
  added: []
  patterns:
    - "One anchored regex per adb output line; fields after the state are read only for model:/device:"
    - "Per-instance tool capability as functools.cached_property calling hosttools (asked once, only when used)"

key-files:
  created: []
  modified:
    - porter/adb.py
    - porter/distro.py
    - porter/cli.py
    - tests/test_adb.py
    - tests/test_distro.py
    - docs/ARCHITECTURE.md

key-decisions:
  - "devices() parses the lines after the `List of devices attached` header (all lines when it is absent) instead of dropping line 1, so a daemon notice on stdout cannot shift the header into the rows"
  - "cmd_devices builds the JSON rows once and the text output prints from them (serial, adb's detail text, info, then the fix on an indented line), so device_fix is called in one place"
  - "The plugdev line is appended only when adb's text says the user is not in the plugdev group; the user name from adb's text is never copied into the fix"
  - "Requirements DEV-01 and TOOL-03 are not marked complete in REQUIREMENTS.md: 03-10 also lists DEV-01, and 03-09 / 03-11 list TOOL-03"

patterns-established:
  - "Fix text is chosen from porter's own literals by state kind and os-release family only (T-03-21)"

requirements-completed: [DEV-01, TOOL-03]

coverage:
  - id: D1
    description: "Every `adb devices -l` line is read whole: `(no serial number)`, the full `no permissions (...)` text, authorizing/connecting, model/device info; pick() unchanged"
    requirement: DEV-01
    verification:
      - kind: unit
        ref: "tests/test_adb.py#Devices.test_states"
        status: pass
      - kind: unit
        ref: "tests/test_adb.py#Devices.test_pick_unchanged"
        status: pass
    human_judgment: false
  - id: D2
    description: "One-line fix per state, with the udev rules command per distribution and the plugdev line for `no permissions`"
    requirement: DEV-01
    verification:
      - kind: unit
        ref: "tests/test_distro.py#DeviceFix.test_fixes"
        status: pass
      - kind: unit
        ref: "tests/test_distro.py#DeviceFix.test_no_permissions_per_distro"
        status: pass
      - kind: unit
        ref: "tests/test_distro.py#DeviceFix.test_kind"
        status: pass
    human_judgment: false
  - id: D3
    description: "`devices --json` rows carry detail and fix; no adb answers {error} with the adb install hint; porter never runs kill-server, reconnect or sudo"
    requirement: DEV-01
    verification:
      - kind: unit
        ref: "tests/test_adb.py#Devices.test_cli_json"
        status: pass
      - kind: unit
        ref: "tests/test_adb.py#Devices.test_cli_no_adb"
        status: pass
      - kind: unit
        ref: "tests/test_adb.py#Devices.test_never_restarts_server"
        status: pass
    human_judgment: false
  - id: D4
    description: "Pushes pass -Z only to an adb of 30.0.0+ or an unread version; a 29.0.6 distro adb pushes without it"
    requirement: TOOL-03
    verification:
      - kind: unit
        ref: "tests/test_adb.py#Compression"
        status: pass
    human_judgment: false
  - id: D5
    description: "A real tablet going unauthorized -> device, and a real Linux `no permissions` fixed by the shown command"
    verification: []
    human_judgment: true
    rationale: "Needs a physical device and a Linux host; planned as manual UAT rows in 03-08"

duration: 4min
completed: 2026-10-31
status: complete
---

# Phase 3 Plan 06: adb device states and push compression Summary

**`adb devices -l` lines parsed whole by one anchored regex (so `no permissions (...)` and `(no serial number)` survive), each state answered with a distro-specific one-line fix in `devices --json`, and `push -Z` passed only to adb 30.0.0+.**

## Performance

- **Duration:** 4 min (execution; 2026-10-31T16:14:53Z to 2026-10-31T16:18:25Z plus summary)
- **Tasks:** 2 of 2
- **Files modified:** 6

## Accomplishments

- `porter/adb.py`: `ROW` regex replaces `ln.split()`. A no-permissions row used to come back with state `no` and serial `(no`; it now keeps the whole state text and the real serial. The return is still `(serial, state, info)`, so `pick()` and `install.py` work unchanged.
- `porter/distro.py`: `UDEV`, `FIXES`, `state_kind()` and `device_fix()`. For `no permissions` the fix names `sudo apt install android-sdk-platform-tools-common` on Debian/Ubuntu, `sudo dnf install android-tools` on Fedora and `sudo pacman -S android-udev` on Arch. Any other distribution gets all three. The plugdev line is added only when adb says the user is not in the group.
- `porter/cli.py` `cmd_devices`: rows add `detail` and `fix`. With `--json` and no adb, porter now answers an `{"error"}` document holding `adb_hint()`; the GUI's `call_json` already shows that message inline. Text output prints the fix under its row.
- `Adb.nz` (a `functools.cached_property` over `hosttools.push_flags`) is used at both push sites, so `adb version` is asked once per Adb and only when it pushes.
- `docs/ARCHITECTURE.md`: a `devices --json` bullet (fields, fix wording, porter runs none of them, no server restart, the `{error}` on missing adb), and the `-Z` rule in the install paragraph.

## Task Commits

1. **Task 1 (tracer): every adb state parsed whole and answered with its fix**: `b8fbc79` (test, RED), `dfb6f8a` (feat, GREEN)
2. **Task 2: -Z only for an adb with push compression, plus docs**: `f25401e` (test, RED), `87e644d` (feat, GREEN)

## TDD Gate Compliance

- **RED 1:** `tests.test_adb.Devices.test_states`, with `.venv/bin/python -m unittest tests.test_adb.Devices tests.test_distro.DeviceFix` → exit 1, classifier `RED_EVIDENCE_OK` (target_test_failed). Semantic assessment: the target ran and failed on its planned assertion (serial list held `'(no'` from `ln.split()`), not on an import or load error. The other failures were also the planned gaps: no `device_fix`, no `detail`/`fix`, no JSON on missing adb.
- **GREEN 1:** `dfb6f8a`. The tracer verify (`tests.test_adb tests.test_distro tests.test_cli`) passed with 30 tests, then the full suite passed with 351.
- **RED 2:** `tests.test_adb.Compression.test_old_adb_no_z`, with `.venv/bin/python -m unittest tests.test_adb.Compression` → exit 1, `RED_EVIDENCE_OK`. Semantic assessment: the target failed on the planned "`adb version` asked once" assertion, because no version was asked and `-Z` was unconditional.
- **GREEN 2:** `87e644d`. `tests.test_adb` passed with 14 tests.
- No REFACTOR commits. In Task 1, `cmd_devices` was reshaped before the GREEN commit so that `device_fix(` appears once.

## Verification

- `.venv/bin/python -m unittest tests.test_adb tests.test_distro tests.test_cli -v`: OK (30 tests)
- `QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover tests`: OK (354 tests, up from 343 at base)
- `.venv/bin/python tests/arch_rules.py`: all checks passed
- Acceptance greps: `ln.split()` in adb.py 0; `device_fix(` in cli.py 1; `'push', '-Z'` in adb.py 0; `*self.nz` in adb.py 2; `no permissions` in ARCHITECTURE.md 1

## Deviations from Plan

None. The plan was executed as written. One small choice: devices() reads lines after the header text instead of dropping the first line, which is still covered by "skip lines it does not match" (see key-decisions).

**Total deviations:** 0.

## Known Stubs

None.

## Notes for later plans

- 03-10 (device page and device list): rows now carry `detail` and `fix`; show `fix` as plain text under a non-ready row (T-03-20). `state == 'device'` still marks a ready row.
- 03-08 UAT: the live `unauthorized` → `device` switch and a real Linux `no permissions` are still manual checks.

## Self-Check: PASSED

- Files modified exist: porter/adb.py, porter/distro.py, porter/cli.py, tests/test_adb.py, tests/test_distro.py, docs/ARCHITECTURE.md
- Commits on this branch: b8fbc79, dfb6f8a, f25401e, 87e644d (4 = `git rev-list --count f072595..HEAD`)
