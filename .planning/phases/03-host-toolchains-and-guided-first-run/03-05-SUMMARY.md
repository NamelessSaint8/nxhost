---
phase: 03-host-toolchains-and-guided-first-run
plan: 05
subsystem: gui
tags: [gui, first-run, wizard, banner, setup, legal]

requires:
  - phase: 03-01
    provides: "`porter setup --json` readiness document; `porter config legal <version> --json`"
provides:
  - "gui/firstrun.py: attach, on_ready, open_setup, first_open, fill_checks, Gate, Wizard, LegalPage, KeysPage, ToolsPage, DevicePage, DonePage, COLOUR/colour, cause/failed/size/mono"
  - "Window protocol: Window.fetch, Window.recheck(), Window.port_a_game(), Window.set_ready(ok, doc=None)"
  - "SetupTab reads `setup --json`; Run setup button (SetupTab.run_btn)"
  - "runner.TIMEOUTS['setup'] = 45"
  - "tests/fixtures/bridge/setup_{ready,first,missing}.json; the stand-in porter answers setup, config, desktop-entry"
affects: [03-07 shell and firstrun arch rule, 03-10 device and done pages, 03-11 tools page, 03-12 prod.keys page]

tech-stack:
  added: []
  patterns:
    - "A GUI module that draws one porter document: the window hands it the answer through one hook line (set_ready -> firstrun.on_ready)"
    - "Page tests over a stand-in call_json patched on gui.app and gui.firstrun, answering on the next event-loop turn with the owner as context"

key-files:
  created:
    - gui/firstrun.py
    - tests/test_firstrun.py
    - tests/fixtures/bridge/setup_ready.json
    - tests/fixtures/bridge/setup_first.json
    - tests/fixtures/bridge/setup_missing.json
  modified:
    - gui/app.py
    - gui/runner.py
    - tests/fixtures/bridge/fake_porter.py
    - tests/test_bridge.py
    - docs/ARCHITECTURE.md

key-decisions:
  - "The wizard reaches a later start page by walking next() from the legal page (a `jumping` flag skips the legal save), because QWizard's Back follows visited pages: starting with setStartId would leave Back with nowhere to go (D-04)"
  - "Every way out of the wizard (Skip setup, close box, Esc, Close setup) goes through an overridden done(), which clears the gate and deletes the wizard, so the next Continue setup builds a fresh one with the current answer"
  - "Run setup or Continue setup with no answer yet (the last setup --json failed) asks porter again instead of opening an empty wizard"
  - "The banner shows when ready is false and missing is not empty; soft notes never show it"

patterns-established:
  - "firstrun keeps its own cause()/failed()/size() copies that say nx2android, not porter"

requirements-completed: [FRUN-01, FRUN-02, FRUN-03]

actuals:
  tokens: 21157
  tasks: 2
  commits: 5
plan_head_before: a037927ee38e96059498c4f9eeb1202c7a1e27a2
plan_head_after: c25bf9bb4b3306e7ff1e165fc108171fc11c94e3

coverage:
  - id: D1
    description: "Every launch asks setup --json (45 s) and draws it: the Setup tab checklist with notes as ! rows, and a plain-text banner naming porter's missing list; nothing written, no config sent"
    requirement: FRUN-03
    verification:
      - kind: integration
        ref: "tests/test_firstrun.py#Launch, SetupTab.test_checks_and_notes, SetupTab.test_failed_check_marks"
        status: pass
    human_judgment: false
  - id: D2
    description: "Banner zero-one-many, plain text, soft notes never show it; a failed or timed-out call shows Retry on the Setup tab, calls set_ready(False) and opens nothing"
    requirement: FRUN-02
    verification:
      - kind: integration
        ref: "tests/test_firstrun.py#Banner"
        status: pass
    human_judgment: false
  - id: D3
    description: "Wizard: non-modal ClassicStyle, opens at the first not-ok step (done when all ok), Back reaches earlier steps, one instance, Skip/Esc close with no write and it never reopens by itself, Next never disabled, page text from porter"
    requirement: FRUN-02
    verification:
      - kind: integration
        ref: "tests/test_firstrun.py#Wizard, SetupTab.test_run_setup_opens_done"
        status: pass
    human_judgment: false
  - id: D4
    description: "Legal page: porter's text in a scroll area, escaped links, Accept and continue saves porter's version (saving..., disabled), then rechecks and moves on; a failed save shows Retry and stays"
    requirement: FRUN-01
    verification:
      - kind: integration
        ref: "tests/test_firstrun.py#Legal"
        status: pass
    human_judgment: false
  - id: D5
    description: "Banner wraps at 720 px; the legal notice scrolls with the button row visible at 560 px, in light and dark themes on macOS and Linux"
    verification: []
    human_judgment: true
    rationale: "Visual backstop rows from the UI-SPEC; offscreen tests cannot judge wrapping and theme contrast"

duration: 8min
completed: 2026-10-31
status: complete
---

# Phase 3 Plan 05: First-run banner, wizard and legal page Summary

**Every launch now reads `porter setup --json`. It fills the Setup tab's checklist and shows a plain-text banner, "Setup is not finished: missing …", with a Continue setup button. While the legal notice is not accepted, a skippable, non-modal wizard opens at the legal page, and accepting saves porter's own notice version.**

## Performance

- **Duration:** 8 min
- **Started:** 2026-10-31T16:03:32Z
- **Completed:** 2026-10-31T16:11:27Z
- **Tasks:** 2
- **Files modified:** 10, plus 2 RED evidence records

## Accomplishments

- `gui/firstrun.py` (new) imports only the standard library, PySide6 and `gui.runner`.
  - `attach(win)` builds the banner as a fixed QToolBar.
  - `on_ready(win, doc)` sets the banner, redraws an open wizard, and opens the wizard on the launch's first answer while the notice is not accepted.
  - `open_setup(win, start=None)` opens the wizard at the first not-ok step, or raises the one already open.
  - `fill_checks(table, doc)` draws the checklist the way the Setup tab drew it before, and adds notes as `!` rows.
- The wizard is a QWizard in ClassicStyle with five pages in `PAGES` order.
  - Its buttons are Skip setup, Back, Next and Close setup.
  - The legal page shows porter's text and links. The keys, tools and device pages show porter's detail, plus the fix while the step is not ok. The done page heading says whether setup is ready.
- `gui/app.py` changes are hook lines only:
  - `SetupTab.check` calls `['setup', '--json']`.
  - The Run setup button sits at the right of the Requirements group.
  - Window gains `fetch`, `recheck()` and `port_a_game()`.
  - `set_ready(ok, doc=None)` passes porter's answer to `firstrun.on_ready`. It switches to the Setup tab only when the first check fails.
- `gui/runner.py`: `TIMEOUTS['setup'] = 45`.
- The stand-in porter answers `setup` with `setup_ready.json`, and answers `config` and `desktop-entry` too, so the `test_bridge` windows start on a ready document. All 27 `test_bridge` tests pass unchanged except `test_default_limits`, which now expects `setup`.

## Task Commits

1. **Task 1 (tracer): launch to banner.** RED `402d06c`, GREEN `dd58760`. The tracer gate re-ran the full verify (`tests.test_firstrun tests.test_bridge`, 50 tests) and it passed before Task 2 started.
2. **Task 2: wizard, buttons, legal page, step pages.** RED `8beb7d3`, GREEN `64d22cc`.
3. **Docs:** `c25bf9b` adds the `docs/ARCHITECTURE.md` bullet for `gui/firstrun.py` and switches the Setup tab line from `doctor` to `setup`.

## TDD Gate Compliance

Each task has a `test(03-05)` commit followed by a `feat(03-05)` commit. `gsd-tools check tdd-red-evidence` returned `RED_EVIDENCE_OK` for both records:

- **T1, `Banner.test_names_missing`:** failed on `assertIsNotNone(first_run)`. At that point `gui/firstrun.py` was an interface stub and `gui/app.py` had no hook. The other RED failures were also the planned gaps: no `setup --json` call, no checklist rows, no `'setup'` limit, and no `recheck` or `run_btn`. There were no load or fixture faults.
- **T2, `Legal.test_accept_saves_version`:** failed on `assertIsNotNone(wizard)`. In Task 1, `open_setup` only recorded the start page. The 12 Task 1 tests still passed.

The records are in `.planning/phases/03-host-toolchains-and-guided-first-run/tdd/03-05-t{1,2}-red.json`. No REFACTOR commits were needed.

## Verification

- `QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover tests`: 343 tests OK (320 at base, plus 23 in `tests/test_firstrun.py`).
- `.venv/bin/python tests/arch_rules.py`: all checks passed.
- Acceptance greps:
  - `firstrun.attach(self)` appears once in `gui/app.py`.
  - `'doctor', '--json'` no longer appears in `gui/app.py`.
  - `'setup': 45` appears once in `gui/runner.py`.
  - `gui/firstrun.py` has no porter import, no `.exec()`, `ClassicStyle` once, and `'config', 'legal'` once.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Back could not reach earlier steps when the wizard started at a later page**
- **Found during:** Task 2
- **Issue:** QWizard's Back follows visited pages. A plain `setStartId(keys)` would leave Back with nothing to return to, which breaks D-04.
- **Fix:** `Wizard.go(start)` calls `restart()` and then `next()` once per page before `start`. Every earlier page is ok, because `start` is the first not-ok step. A `jumping` flag stops the legal page from saving during the walk.
- **Files modified:** gui/firstrun.py
- **Commit:** 64d22cc

**2. [Rule 2 - Missing critical] Documented the new GUI module**
- **Found during:** after Task 2
- **Issue:** CLAUDE.md asks for `docs/ARCHITECTURE.md` to change with a layer, and no later plan documents `gui/firstrun.py`.
- **Fix:** Added one bullet on the module and its window protocol, and switched the Setup tab line from `doctor` to `setup`.
- **Files modified:** docs/ARCHITECTURE.md
- **Commit:** c25bf9b

The fixture path `/opt/nx2a-test/home/` was renamed to `/opt/nx2a-test/user/` before the RED commit, because the scrub test forbids `/home/`.

## Known Stubs

These are intentional, per the plan's scope split. Each page shows porter's step text today, and its controls arrive in a later plan:

- `gui/firstrun.py` `KeysPage`: the candidate list, Browse… and saving the path come in 03-12.
- `gui/firstrun.py` `ToolsPage`: the tool table and downloads come in 03-11.
- `gui/firstrun.py` `DevicePage` and `DonePage`: device polling, the summary list, the playable titles, Add to app menu and Port a game come in 03-10.

## Notes for later plans

- The arch rule that keeps `gui/firstrun.py` a pure view belongs to 03-07. Until it lands, the grep gate holds.
- `tests/arch_rules.py` "every GUI action is a CLI subcommand" lists the GUI's commands without `setup`. Its scan does not pick up the `['setup', '--json']` literal. It still passes, because `setup` is a CLI subcommand.

## Self-Check: PASSED
