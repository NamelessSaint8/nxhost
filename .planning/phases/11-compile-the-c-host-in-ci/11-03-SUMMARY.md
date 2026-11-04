---
phase: 11-compile-the-c-host-in-ci
plan: 03
subsystem: ui
tags: [pyside6, gui, porttab, targetrow, qtreewidget, fixtures, golden, mac-app, android]

# Dependency graph
requires:
  - phase: 11-compile-the-c-host-in-ci
    plan: 01
    provides: "result.targets[] and platform on stage/step/progress/stage_end — the two protocol facts these rows and keys read"
  - phase: 11-compile-the-c-host-in-ci
    plan: 02
    provides: "MAC_HOST, TargetChoice, platform_arg(), android_box/mac_box/targets_note/install_row"
  - phase: 03-host-toolchains-and-guided-first-run
    provides: "firstrun.colour/Elided/mono — the palette and the path label reused, not reinvented"
provides:
  - "gui.app.TargetRow: one target's outcome — glyph, `<Target> · <word>`, elided package path, its own Reveal, porter's reason below"
  - "PortTab.results / results_layout / show_results / clear_results / rows: the results block, hidden until a result and cleared at every run"
  - "TARGET_LABEL / STATUS_WORD / STATUS_GLYPH / STATUS_KEY: the one place targets[].status becomes a word, a glyph and a colour key"
  - "PortTab.update_install_button: Install on device follows a built Android row"
  - "The stage tree keyed by (platform, k), with the `<Target> · ` prefix only when the event carries a platform"
  - "on_finished's four branches: done / finished (partial) / failed / cancelled"
  - "tests/fixtures/bridge/port_both.jsonl + Replay.test_port_both: a real two-target stream with platform on every stage event"
affects: [04-library, 12-one-command-that-verifies-a-change, gui PortTab, Phase 12 smoke]

# Actuals (#2632, chars/4 over the realized diff, not a harness token count)
actuals:
  tokens: 11600
  tasks: 2
  commits: 4

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "A row built from one target's {platform, status, out, reason} and nothing else: no view-side guessing, no second code path for a skip"
    - "A layout keyed by the pair the protocol can repeat: (platform, k), so two chains that both number their stages from 1 cannot collide"
    - "A golden fixture generated through the real command namespace (cmd='port' + --platform both), because runlog only wraps — and so only stamps platform — for 'port' and 'install'"

key-files:
  created:
    - tests/fixtures/bridge/port_both.jsonl
  modified:
    - gui/app.py
    - tests/test_bridge.py
    - tests/fixtures/bridge/record.py

key-decisions:
  - "The rows are drawn on the `result` event, not in on_finished, so the block's lifetime is exactly 'a result arrived → cleared by the next run' (rule 15-16)"
  - "targets[].status goes through STATUS_WORD/STATUS_GLYPH/STATUS_KEY once; the view computes no status of its own, so a failure can never render as a green glyph (T-11-10)"
  - "The glyph and the reason line carry the row's colour; the `<Target> · <word>` label stays window text, because the target name is not a status word"
  - "Reveal's accessible name follows UI-SPEC rule 19 ('Reveal the Android APK' / 'Reveal the Mac app'), not the plan's shorter spelling, since the spec is the contract"
  - "record.py emulates a real `porter port --platform both` namespace (cmd 'port', platform 'both'): runlog.run only wraps — and so only stamps platform — when a.cmd is in LONG"
  - "record.py takes an optional fixture-name argument, so one golden can be regenerated without rewriting the others' timestamps"

patterns-established:
  - "A protocol value the view must never derive (status) crosses exactly one map, and the map is a module constant beside the palette"

requirements-completed: [QUAL-07]

coverage:
  - id: D1
    description: "A finished two-target run draws one row per target in the run's order: coloured glyph, `<Target> · <word>`, the package path elided in the middle in the mono font with the full path in the tooltip, and its own Reveal enabled only on a built row (rules 16-19)"
    requirement: QUAL-07
    verification:
      - kind: unit
        ref: "tests/test_bridge.py#Results.test_one_row_per_target_in_the_runs_order"
        status: pass
      - kind: unit
        ref: "tests/test_bridge.py#Results.test_a_skipped_row_and_a_built_rows_reveal"
        status: pass
    human_judgment: false
  - id: D2
    description: "A failed or skipped row shows porter's own reason verbatim on a second line, Qt.PlainText and word-wrapped, with a disabled Reveal and no path when there is no package (rules 17, 26-27; T-11-09)"
    requirement: QUAL-07
    verification:
      - kind: unit
        ref: "tests/test_bridge.py#Results.test_a_failed_row_shows_porters_reason_as_plain_text"
        status: pass
      - kind: unit
        ref: "tests/test_bridge.py#Results.test_a_skipped_row_and_a_built_rows_reveal"
        status: pass
    human_judgment: false
  - id: D3
    description: "The results block is hidden until a result arrives, holds no heading or placeholder, and is cleared at the start of every run; a single-target result without targets[] still draws exactly one row from the flat apk/data/app keys (rules 15-16)"
    requirement: QUAL-07
    verification:
      - kind: unit
        ref: "tests/test_bridge.py#Results.test_a_single_target_result_draws_one_row_and_a_run_clears_it"
        status: pass
    human_judgment: false
  - id: D4
    description: "The single `Open output folder` button is gone (`open_btn`/`open_out`), and `Install on device` is enabled only for a built Android row while the Android box is ticked (rules 19-20)"
    requirement: QUAL-07
    verification:
      - kind: unit
        ref: "tests/test_bridge.py#Results.test_the_single_output_button_is_gone"
        status: pass
      - kind: unit
        ref: "tests/test_bridge.py#Results.test_install_follows_a_built_android_row"
        status: pass
    human_judgment: false
  - id: D5
    description: "Both chains stay in one stage list — the tree keyed by (platform, k) — and the Stage column and step line carry `<Target> · ` only when the event carries a platform, so a single-target run reads exactly as today (rules 12-14, Pitfall 5)"
    requirement: QUAL-07
    verification:
      - kind: unit
        ref: "tests/test_bridge.py#Replay.test_both_chains_stay_in_one_tree"
        status: pass
      - kind: unit
        ref: "tests/test_bridge.py#Replay.test_a_single_target_run_reads_exactly_as_today"
        status: pass
      - kind: unit
        ref: "tests/test_bridge.py#Replay.test_the_step_line_names_the_target_on_a_two_target_run"
        status: pass
      - kind: integration
        ref: "tests/test_bridge.py#Replay.test_port_ok (the golden replays unchanged)"
        status: pass
    human_judgment: false
  - id: D6
    description: "The finish line tells the four outcomes apart: exit 0 → `done in <took>` with the bar full (a skip is not a failure); non-zero beside a built row → `finished in <took>: the <targets> failed` with the bar still full; nothing built → `failed after <took>: <cause>` with the bar empty; 130 → `cancelled`, bar empty (rules 21-25)"
    requirement: QUAL-07
    verification:
      - kind: unit
        ref: "tests/test_bridge.py#Replay.test_the_finish_line_tells_done_partial_failure_and_cancel_apart"
        status: pass
      - kind: unit
        ref: "tests/test_bridge.py#Stop.test_port_tab_status (today's 'cancelled' unchanged)"
        status: pass
    human_judgment: false
  - id: D7
    description: "`port_both.jsonl` is generated by record.py from porter's own emitter: two chains that both number their stages from k=1 with platform on every stage event, and one result whose targets[] is Android ok + Mac app failed; port_ok.jsonl and every other golden stay byte-identical"
    requirement: QUAL-07
    verification:
      - kind: integration
        ref: "tests/test_bridge.py#Replay.test_port_both"
        status: pass
      - kind: integration
        ref: "tests/test_bridge.py#Replay.test_fixtures_are_scrubbed"
        status: pass
      - kind: manual_procedural
        ref: "`.venv/bin/python tests/fixtures/bridge/record.py port_both.jsonl` twice, compared after normalising the wall clock (t, elapsed, [HH:MM:SS], the log name's stamp) — identical"
        status: pass
    human_judgment: false
  - id: D8
    description: "The three held-out visual checks: the prefixed step line wraps inside the 980 px window, `Mac app · <long stage name>` stays readable in the ResizeToContents Stage column, and a 300-character porter reason wraps instead of widening the window"
    verification: []
    human_judgment: true
    rationale: "Pixel-width judgements at 980 px that no headless test measures; the plan marks them backstop truths and defers them to $gsd-verify-work."
  - id: D9
    description: "A real `porter port --platform both` on this Mac shows the two rows and both chains live"
    verification:
      - kind: manual_procedural
        ref: "deferred to Phase 12's device smoke: needs a game folder, the NDK and the Metal chain"
        status: unknown
    human_judgment: true
    rationale: "No game files or toolchains in this environment; the golden stream and the unit tests stand in for the run."

# Metrics
duration: 45min
completed: 2026-11-04
status: complete
---

# Phase 11 Plan 03: The Port view reports what a two-target run produced Summary

**After a run the Port view draws one row per target with its own Reveal and porter's own reason, keeps both chains' stages in one list, and reads `done`, `finished … failed`, `failed` and `cancelled` apart — with today's single-target view byte-identical.**

## Performance

- **Duration:** ~45 min
- **Started:** 2026-11-04T16:26Z
- **Completed:** 2026-11-04T17:10Z
- **Tasks:** 2 (the tracer, then the stage list, finish lines and golden)
- **Files modified:** 4 (3 modified, 1 new)

## Accomplishments
- `gui.app.TargetRow`: a coloured glyph, `<Target> · <word>`, the package path elided in the middle in the mono font (full path in the tooltip), its own **Reveal** (the folder holding that target's package), and porter's `reason` on a second line as `Qt.PlainText` — hidden when the row is built, disabled Reveal and no path when there is no package.
- `PortTab` draws one row per `targets[]` entry in the run's order, or one row from the flat `apk`/`data`/`app` keys for today's single-target result; the block is hidden before a result, has no heading or placeholder, and is cleared by every `run()`.
- The single **Open output folder** button is gone (`open_btn`, `open_out`, its bar slot and its enable call); **Open log** and **Install on device** keep their labels and positions, and Install is enabled only for a built Android row while the Android box is ticked.
- The stage tree is keyed by `(platform, k)`, so the Mac chain's own `k = 1…n` appends after the Android chain's instead of overwriting it, and the Stage column and step line take `<Target> · ` only when the event carries a platform — a single-target run keeps today's text, which is what keeps `port_ok.jsonl` valid next to the new `port_both.jsonl`.
- `on_finished` now branches four ways: `done in …` (bar 1000), `finished in …: the <targets> failed` (bar still 1000 — something was produced), `failed after …: <cause>` (bar 0), `cancelled` (bar 0).
- `tests/fixtures/bridge/port_both.jsonl` generated by `record.py` from porter's own emitter: 65 platform-stamped stage events over two chains that both start at `k = 1`, and one result whose `targets[]` is Android `ok` + Mac app `failed` with a real reason sentence.

## Task Commits

Each task followed RED → GREEN:

1. **Task 1 RED: the per-target result rows** — `7b39ef05` (test)
2. **Task 1 GREEN: TargetRow, the results block, the button retired** — `7d5d83d9` (feat)
3. **Task 2 RED: both chains, the prefix, the four finish lines** — `897dc929` (test)
4. **Task 2 GREEN: `(platform, k)` keys, the prefix, the branches, the golden** — `ca718b75` (feat)

**Plan metadata:** the commit after this file (`docs(11-03): complete …`).

_Note: `b9…` (perf(vk): a copied pool's copy-back…) landed between commits 3 and 4 from another session on the same branch. It is not this plan's work and was neither staged nor reverted._

## Files Created/Modified
- `gui/app.py` — `TARGET_LABEL`/`STATUS_WORD`/`STATUS_GLYPH`/`STATUS_KEY`; `TargetRow`; `PortTab.rows`/`results`/`results_layout`/`show_results`/`clear_results`/`update_install_button`/`target_prefix`; `item(k, name, platform)`; the prefixed step lines; `setWordWrap(True)` on the step label; the four `on_finished` branches; `open_btn`/`open_out` deleted.
- `tests/test_bridge.py` — the `Results` class (6 cases) and 5 new `Replay` cases (golden round-trip, both chains, single-target unchanged, the step prefix, the four finish lines).
- `tests/fixtures/bridge/record.py` — `BOTH` stage list, `MAC_FAILED`, `both()` on the real `porter port --platform both` namespace, and an optional fixture-name argument.
- `tests/fixtures/bridge/port_both.jsonl` — generated, never hand-written.

## Decisions Made
- **Rows are drawn on the `result` event** (rule 16), not in `on_finished`: the block's lifetime is then exactly "a result arrived" → "the next run cleared it", and rule 25 (a run that dies before `result` shows no rows) falls out for free.
- **One map per protocol fact.** `targets[].status` reaches the screen only through `STATUS_WORD`/`STATUS_GLYPH`/`STATUS_KEY`; the view has no second opinion about whether a target succeeded (T-11-10), and every row carries a word as well as a glyph.
- **Colour on the glyph and the reason line, not on the name.** The `<Target> · <word>` label stays window text: the target name is not a status, and the row already has two non-colour signals.
- **`Reveal the Android APK` / `Reveal the Mac app`** for `setAccessibleName`, per UI-SPEC rule 19, rather than the plan's shorter `Reveal Android APK`.
- **The fixture generator drives a real command namespace.** `runlog.run` wraps `PROG` (and therefore stamps `platform`) only when `a.cmd` is in `LONG = ('port', 'install')`; the generator now passes `cmd='port'` with `platform='both'`, which is what a real both run is.
- **Install on device follows the row, not the exit code**: a partial success (APK built, Mac app failed, exit 1) can still install the APK, which is the whole point of D-06.
- **`self.red` and `self.cancelled` exist before a run**: `on_finished` reads both, and until now they only appeared in `run()`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] The `both` fixture emitted no `platform` on its stage events**
- **Found during:** Task 2 (the golden stream)
- **Issue:** `record.py`'s `emit()` dispatched on `cmd == 'both'`, so `argparse.Namespace(cmd='both')` made `runlog.run` take its non-long path — no `_wrap`, no `set_platform` effect — and every stage event came out unstamped. `grep -c '"platform"'` was 1 (the result only).
- **Fix:** the namespace now says `cmd='port'`, `platform='both'` — a real `porter port --platform both` — and the callback is chosen separately.
- **Files modified:** `tests/fixtures/bridge/record.py`
- **Verification:** `grep -c '"platform"' tests/fixtures/bridge/port_both.jsonl` → 65; `Replay.test_port_both` asserts every stage event carries one
- **Committed in:** `ca718b75` (Task 2 feat)

**2. [Rule 2 - Missing critical functionality] Regenerating one golden rewrote all four**
- **Found during:** Task 2 (generating the fixture)
- **Issue:** `main()` always regenerated `port_ok.jsonl`, `install_ok.jsonl` and `port_build_error.jsonl` too, moving their `t`/`elapsed` bytes — which the plan's own critical constraint forbids ("if `port_ok.jsonl` changed, you have a bug").
- **Fix:** `main()` accepts an optional list of fixture names (`record.py port_both.jsonl`) and skips the rest; the header documents both forms.
- **Files modified:** `tests/fixtures/bridge/record.py`
- **Verification:** `git status --short tests/fixtures/bridge/` shows only `record.py` modified and `port_both.jsonl` new; `Replay.test_port_ok`/`test_install_ok`/`test_port_build_error` unchanged and green
- **Committed in:** `ca718b75` (Task 2 feat)

**3. [Rule 1 - Bug] `on_finished` read two attributes that only existed after a run**
- **Found during:** Task 1 (the RED run surfaced it)
- **Issue:** `PortTab.on_finished` reads `self.red` and `self.cancelled`, both first assigned in `run()`; any finish path outside a run (and the new tests, which drive the event handlers directly) raised `AttributeError` before drawing a line.
- **Fix:** both are initialised in `PortTab.__init__` beside `self.rows`.
- **Files modified:** `gui/app.py`
- **Verification:** `Results.test_install_follows_a_built_android_row` drives `on_finished` with no run; `Replay.test_the_finish_line_tells_done_partial_failure_and_cancel_apart` does it for all four codes
- **Committed in:** `7d5d83d9` (Task 1 feat)

### Criteria that could not be met literally

**Byte-identical regeneration.** The plan's acceptance criterion "regenerating the fixture twice produces the same bytes" is not achievable for any fixture in this repo, including the existing ones: the emitter stamps wall-clock values into every run — `"t"`, `"elapsed"`, the `[HH:MM:SS]` clock in each `say`, and the log file's `YYYYMMDD-HHMMSS` name. Verified instead that two generations are identical once those are normalised (the only differences). Stripping them in `scrub()` would rewrite `port_ok.jsonl` and every other golden, which the plan forbids, so nothing was changed here.

---

**Total deviations:** 3 auto-fixed (1 Rule 1, 1 Rule 2, 1 Rule 3) plus 1 criterion that cannot hold as written.
**Impact on plan:** All three keep the contract intact; the fixture generator's namespace fix is what makes the protocol additions visible at all. No scope creep.

## Issues Encountered
- The tracer feedback gate (non-interactive run, no `AUTO_*` chain active): the tracer's `<verify>` (`python -m unittest tests.test_bridge.Results -v`) was re-run end to end after `7d5d83d9` — 6/6 green — before the expansion task began.
- `tests/test_bridge.py`'s `QProcess: Destroyed while process is still running.` line is pre-existing noise (it appears with the new classes excluded from the run).

## TDD Gate Compliance
- RED `7b39ef05` (6 cases failing on a missing `results`/`TargetRow`/`open_btn` removal), GREEN `7d5d83d9` (all 6 green).
- RED `897dc929` (3 failures and 3 errors: no `wordWrap`, no partial line, no golden), GREEN `ca718b75` (`Replay` 10/10 green).

## Threat Flags
None beyond the plan's register. T-11-09: every porter string in a row is `Qt.PlainText` and word-wrapped, and the path goes through `firstrun.Elided`, so `<`, `&` or a tag cannot become markup (asserted with a `<b>`-bearing reason). T-11-10: the word and glyph come from one map keyed by `targets[].status`. T-11-SC: no install step was added; `port_both.jsonl` is generated in-repo.

## User Setup Required
None — no external service configuration required.

## Known Stubs
None.

## Next Phase Readiness
- The Port view now consumes the whole plan 11-01 protocol: `targets[]`, `platform` on the stage events, and the flat keys for today's single-target shape. `gui/runner.py` needed no change, as the interface context predicted.
- Deferred and recorded for `$gsd-verify-work` / Phase 12: the three held-out 980 px visual checks (D8) and a real `porter port --platform both` on this Mac (D9).

---
*Phase: 11-compile-the-c-host-in-ci*
*Completed: 2026-11-04*

## Self-Check: PASSED

- Commits `7b39ef05`, `7d5d83d9`, `897dc929`, `ca718b75` all present.
- `gui/app.py`, `tests/test_bridge.py`, `tests/fixtures/bridge/record.py`, `tests/fixtures/bridge/port_both.jsonl` and this SUMMARY present.
- `python -m unittest tests.test_porter tests.test_bridge tests.test_architecture` 110/110 green; `python tests/arch_rules.py` all checks passed.
- `git status tests/fixtures/bridge/` shows no change to `port_ok.jsonl` or any other existing golden.
