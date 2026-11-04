---
phase: 11-compile-the-c-host-in-ci
verified: 2026-11-04T18:05:00Z
status: passed
score: 38/38 must-haves verified
behavior_unverified: 0
overrides_applied: 0
deferred: # Items not yet observed but owned by a later phase — informational, not gaps
  - truth: "A real `porter port --platform both` on this Mac produces the APK and the `.app` in one run, with two live result rows"
    addressed_in: "Phase 12"
    evidence: "Phase 12 success criterion 1: 'runs the unit suite, re-ports one title per engine family against cached extraction, and runs a device smoke'; the phase context defers the device smoke loop here, and Phase 11's plans (11-01 D6, 11-03 D9) record it as Phase 12's smoke"
---

# Phase 11: Compile the C host in CI Verification Report

**Phase Goal:** One run makes an APK, a Mac app, or both, as the user chooses in the GUI or the CLI; and the C host cannot break on a host we ship to without the push that broke it saying so
**Verified:** 2026-11-04T18:05:00Z
**Status:** passed
**Re-verification:** Yes — prior verification was `human_needed` with six items; all six are now settled by `11-UAT.md` (status complete, 6/6) and are re-checked here against the code and the live repository.

## Goal Achievement

The goal has two halves and both are now demonstrated, not just present in code.

**One run, one-or-both targets.** `porter port --platform both` is a real third `--platform` value (`porter/cli.py:24`), dispatched to `Port.run_both()` (`porter/pipeline.py:105-142`), which drives an Android child then a Mac child from the single `BOTH` tuple, both inheriting the driver's `work`/`app`/`fam` so the folder is scanned and the build folder is locked once. Each target reports `{platform, status, out, reason}` in `result['targets']` beside the untouched flat `apk`/`data`/`app` keys, and the exit code is the callback's return: 1 iff a row is `failed` (`porter/cli.py:142-145`, `_with_progress` returning `fn() or 0` at line 120). The GUI supplies the choice as two checkboxes in the form's first row, with the host's default, the off-macOS refusal in words, and exactly one mapping helper (`gui/app.py:57-124`, `223-227`); the results block draws one row per target with its own Reveal and porter's own reason (`gui/app.py:104-117`, `346-360`).

**The C host compiled per target, and the guard shown working.** `.github/workflows/host-build.yml` is two independent, path-filtered jobs (`host-apple` on `macos-26` through `dm/host/Makefile`, `host-android` on `ubuntu-22.04` through `dm/android/build.py`), every `uses:` pinned to the same commit as `fork-ci.yml`, no secrets, no PR-derived strings. The guard has now run in the field and caught a real break on the push that caused it: run 41878713095 (`host-apple` failed, `host-android` succeeded) failed with 8 property-not-found errors on `MTL4FXTemporalScaler` because the macos-26 image tops out at Xcode 26.6 / SDK 26.5. Commit `1aff5907` guarded the block with `#if __MAC_OS_X_VERSION_MAX_ALLOWED >= 270000`, leaving behaviour on the 27 SDK unchanged, and re-run 41880689832 has both jobs success. Branch protection is applied and read back from the API: required checks `host-apple` + `host-android`, strict false, enforce_admins false. That makes the jobs "blocking" in QUAL-09's sense.

### Observable Truths

| #   | Truth | Status | Evidence |
| --- | ----- | ------ | -------- |
| 1 | One `--platform both` invocation drives Android then the Mac app in run order, sharing extraction and the shader split, each target's stages in its own `work/android` / `work/mac`; that order fixes both the stage stream and `targets[]` | ✓ VERIFIED | `BOTH = ('android', 'mac-app')` and the `for platform in BOTH` loop (`pipeline.py:18,116`); `self.aw = self.work / ('mac' if self.mac else 'android')` per child (`pipeline.py:239`); `test_both_runs_android_then_mac` asserts `['android','mac-app']` from `targets[]` and the child order, with `begin` called once |
| 2 | A failing target does not stop the other; per-target `targets[]` rows carry `platform`, `status` (`ok`/`failed`/`skipped`), `out`, `reason`; only `BuildError` is a target failure, so any other exception propagates as the crash it is | ✓ VERIFIED | `run_both` catches only `TargetSkipped`/`BuildError` per child and continues (`pipeline.py:126-131`); `test_a_failed_target_does_not_stop_the_other`, `test_a_crash_is_not_a_target_failure` (`RuntimeError` propagates out of `run_both`) |
| 3 | Exit code is 1 iff any `targets[].status == 'failed'`, 0 when both built or one was skipped | ✓ VERIFIED | `go()` returns `1 if any(r['status'] == 'failed' ...) else 0` (`cli.py:145`); `_with_progress` returns `fn() or 0` (line 120); `test_exit_code_one_when_a_target_failed`, `test_exit_code_zero_when_none_failed` (ok/ok, ok/skipped, skipped/skipped, single-target) |
| 4 | A profile with no `android.tsv` is `skipped` for Android with a player-words reason (no `--experimental`) and the Mac app still builds | ✓ VERIFIED | `raise TargetSkipped(f'{why}: no android.tsv for this game')` under `if self.multi_target` (`pipeline.py:215-217`); `test_no_android_tsv_is_a_skip_in_a_both_run` asserts the phrase, no `--experimental`, and that the single-target path keeps today's `BuildError` with the remedy |
| 5 | Off macOS the Mac target is `skipped` with `MAC_NEEDS_MAC` — the same sentence `run_mac()` raises — never `failed` | ✓ VERIFIED | One constant, used at the skip (`pipeline.py:118`) and the refusal (`pipeline.py:530`); `test_mac_target_is_skipped_off_macos` (no Mac child constructed, android still ok), `test_run_mac_refusal_is_the_skip_reason` |
| 6 | `targets[]` is present only for a multi-target run; a single-target result keeps today's exact shape, so `port_ok.jsonl` stays valid | ✓ VERIFIED | `targets` is set only in `run_both` (`pipeline.py:141`); `Replay.test_port_both` asserts `port_ok.jsonl` has no `targets`; `Replay.test_port_ok` passes unchanged; fixture grep: 1 `"targets"` in `port_both.jsonl`, 0 in `port_ok.jsonl` |
| 7 | A `both` result keeps the flat keys (`platform`, `apk`, `data`, `app`, `title_id`, `name`, `package`, `version`, `display`, `language`) filled from whichever targets built, so `install_now()` keeps working | ✓ VERIFIED | `pipeline.py:132-140` copies the nine keys then sets `platform='both'`; `gui/app.py`'s `install_now()` still reads `result['data']`/`['apk']` (line 246); `test_both_runs_android_then_mac` asserts apk/data/app/package together |
| 8 | One folder scan and one build-folder lock per run; the child Ports inherit `work`/`app`/`fam` and never take the lock again | ✓ VERIFIED | `begin()` owns the scan and `lock.take` (`pipeline.py:188-198`, exactly one `lock.take` in the file); `inputs()` calls it only `if self.work is None` (line 199); `Port.run_both` sets the three fields on every child (lines 121-122); `test_the_driver_takes_the_lock_and_a_child_does_not`, `test_both_runs_android_then_mac` (`begin` once, inherited fields) |
| 9 | The QUAL-13 unclassified assumption is recorded, not dropped: the contract is the pair (exit code, `targets[]`) and the user confirms the partial-run wording in UAT | ✓ VERIFIED | `11-01-PLAN.md` §"Assumptions surfaced" names the edge and the settling test; `11-01-SUMMARY.md` coverage D5 is `human_judgment: true`; the wording itself is asserted by `test_both_names_both_outcomes_in_the_log`; UAT item 6 confirms `finished in 0:12: the Mac app failed`, bar 1000 |
| 10 | The Port view's first Options row is `Targets`, holding exactly `Android APK` and `Mac app` 8 px apart, hugging the field column | ✓ VERIFIED | `f.insertRow(0, 'Targets', self.targets)` (`gui/app.py:148`); `TargetChoice`'s `QHBoxLayout` spacing 8, margins 0, stretch after (`gui/app.py:75`); `Targets.test_default_is_the_hosts_own_target` (two boxes, checked states) |
| 11 | Host-appropriate default (macOS: `Mac app` only; elsewhere: `Android APK` only), and both boxes are tickable together wherever the host permits | ✓ VERIFIED | `setChecked(not MAC_HOST)` / `setChecked(MAC_HOST)` with signals blocked (`gui/app.py:80-82`); `Targets.test_default_is_the_hosts_own_target`, `test_one_helper_names_the_target` (both ticked → `both`) |
| 12 | No zero-target state: unticking the last ticked box re-ticks it and shows `Keep at least one target ticked.` | ✓ VERIFIED | `changed()` reverts inside the slot with signals blocked (`gui/app.py:86-92`); `Targets.test_the_last_box_cannot_be_unticked` asserts the box, the token, the text and visibility |
| 13 | Off macOS the Mac box is disabled with the exact tooltip and note | ✓ VERIFIED | `setEnabled(bool(MAC_HOST))`, `MAC_OFF_TIP`, `OFF_MAC` (`gui/app.py:58-76`); `Targets.test_off_macos_the_mac_box_says_why` asserts both strings byte-for-byte |
| 14 | One helper turns the boxes into exactly one `--platform` token (`both` / `android` / `mac-app`), and `start()` has no second mapping | ✓ VERIFIED | `platform_arg()` is the only mapping (`gui/app.py:223-227`), called once in `start()` (line 236); `Targets.test_one_helper_names_the_target`, `test_start_asks_for_the_ticked_targets` (argv token per state) |
| 15 | `--install`/`--device` are passed only while `android` is ticked; the Install row is disabled with `Install on the device and the device list apply to the Android APK.` | ✓ VERIFIED | `if self.android_box.isChecked() and self.install.isChecked()` (`gui/app.py:241-243`); `on_targets_changed` gates `install_row` (lines 219-222); `NO_ANDROID` note; `test_start_asks_for_the_ticked_targets`, `test_on_macos_the_mac_box_is_offered` |
| 16 | Both target boxes are disabled for the run and restored afterwards without leaving zero ticked | ✓ VERIFIED | `self.targets.boxes_enabled(False)` in `run()` and `boxes_enabled(True)` in `on_finished` (`gui/app.py:255, 326`); `boxes_enabled` re-offers the Mac box only where offered (line 95); `Targets.test_the_boxes_wait_for_the_run` |
| 17 | The row never reads the game folder, `android.tsv`, `dmsh_chain.lock` or the profile; `MAC_HOST` is the only host fact | ✓ VERIFIED | `TargetChoice` has no filesystem access and no import beyond Qt/firstrun; the warden rule passes: `PASS gui/ holds no pipeline logic`, `PASS every GUI action is a CLI subcommand` |
| 18 | The one note under the row is a plain-text, word-wrapped `QLabel` (no elision/truncation), so long copy wraps onto as many lines as it needs | ✓ VERIFIED | `setTextFormat(Qt.PlainText)`, `setWordWrap(True)`, one label reused for all three notes (`gui/app.py:76-79, 93-95`); no elision/`Elided` on the note; `test_off_macos_the_mac_box_says_why` reads it |
| 19 | After a `both` result the view draws one row per target in run order: glyph, `<Target> · <word>`, the path middle-elided in the mono font with the full path in the tooltip, and its own `Reveal` | ✓ VERIFIED | `show_results` builds one `TargetRow` per entry and nothing else (`gui/app.py:346-354`); `TargetRow` uses `firstrun.Elided` (mono font, `Qt.ElideMiddle`, tooltip = full path — `gui/firstrun.py:218-223`); `Results.test_one_row_per_target_in_the_runs_order` asserts names, glyphs, paths and exactly two layout children |
| 20 | Row words are exactly `built`/`failed`/`skipped`, glyphs `✓`/`✗`/`–`, colour keys `ok`/`bad`/`note`; colour is never the only signal | ✓ VERIFIED | `STATUS_WORD`/`STATUS_GLYPH`/`STATUS_KEY` (`gui/app.py:21-23`), each row shows a glyph **and** a word; `Results.test_one_row_per_target_in_the_runs_order`, `test_a_skipped_row_and_a_built_rows_reveal` |
| 21 | `Reveal` is enabled only on a `built` row, opens that target's package folder, and carries the exact tooltip plus a distinguishing accessible name | ✓ VERIFIED | `setEnabled(status == 'ok' and bool(self.out))`, tooltip `Show the {name} in your file manager`, `setAccessibleName(f'Reveal the {name}')`, `open()` opens `Path(out).parent` (`gui/app.py:107-117`); `test_a_skipped_row_and_a_built_rows_reveal` (disabled/enabled, `/out` opened, two distinct names) |
| 22 | A failed or skipped row shows porter's reason verbatim on a second line as `Qt.PlainText`, word-wrapped, hidden when the row is built | ✓ VERIFIED | `reason` label: PlainText, wordWrap, visible only when non-empty and status != 'ok' (`gui/app.py:114-116`); `Results.test_a_failed_row_shows_porters_reason_as_plain_text` (a `<b>`-bearing reason appears literally) |
| 23 | The results block is hidden until a `result`, has no heading or placeholder, is cleared at every run start, and a single-target result draws exactly one row from the flat keys | ✓ VERIFIED | `results.setVisible(False)` at construction, `clear_results()` in `run()`, one synthetic row when `targets` is absent (`gui/app.py:155, 252, 348`); `Results.test_a_single_target_result_draws_one_row_and_a_run_clears_it`, `test_one_row_per_target_in_the_runs_order` (hidden before) |
| 24 | The stage tree is keyed by `(platform, k)` and takes the `<Target> · ` prefix only when the event carries a platform, so a single-target run reads exactly as today | ✓ VERIFIED | `self.items[(platform, k)]` (`gui/app.py:281`), `target_prefix()` gates on `ev.get('platform')` (`283-285`); `Replay.test_both_chains_stay_in_one_tree` (both `Android APK · rewrite` and `Mac app · rewrite` present, count equals stage events), `test_a_single_target_run_reads_exactly_as_today` |
| 25 | `self.step` wraps; the finish line distinguishes done / partial success / total failure / cancelled, with the right bar value | ✓ VERIFIED | `setWordWrap(True)` (`gui/app.py:157`); four branches in `on_finished` (`324-336`); `Replay.test_the_finish_line_tells_done_partial_failure_and_cancel_apart` (done/partial/failed/cancelled plus the `: the Mac app failed` tail, bar 1000 on partial), `test_the_step_line_names_the_target_on_a_two_target_run`, `test_a_single_target_run_reads_exactly_as_today` (wordWrap true) |
| 26 | `open_btn`/`open_out` are gone; `Open log` and `Install on device` keep their labels and positions, and Install is enabled only for a built Android row while Android is ticked | ✓ VERIFIED | No `open_btn` and no `def open_out` remain (only a comment names `open_out`); bar is `for b in (self.log_btn, self.inst_btn)` (`gui/app.py:154`); `update_install_button` (`356-358`); `Results.test_the_single_output_button_is_gone`, `test_install_follows_a_built_android_row` |
| 27 | The status line and bar are cleared to `starting…`/0 at the start of every run, so no previous run's text or bar survives | ✓ VERIFIED | `self.prog.setValue(0); self.step.setText('starting…'); self.clear_results()` in `run()` (`gui/app.py:252`) |
| 28 | Backstop: with the target prefix on, the step label wraps inside 980 px instead of widening it | ✓ VERIFIED | `probe_both.py` measures it: label 940x30 px, 2 lines, window stays 980 px (8/8 checks pass) |
| 29 | Backstop: `Mac app · <long stage name>` stays readable in the ResizeToContents Stage column at 980 px | ✓ VERIFIED | `probe_both.py`: Stage column 180 px of 940 px, with both chains' six stage rows present and not overwriting each other |
| 30 | Backstop: a 300-character porter reason wraps to two or three lines without widening the window at 980 px | ✓ VERIFIED | `probe_both.py`: reason label 940x45 px, 3 lines; result block 940 px, window unchanged at 980 px |
| 31 | `host-build.yml` has exactly two jobs, `host-apple` (`macos-26`) and `host-android` (`ubuntu-22.04`), path-filtered to `nxnative/**` and `.github/**` on push and pull request; `fork-ci.yml` keeps no `paths:` and still runs its four-host suite on every push | ✓ VERIFIED | Workflow lines 8-14, 28-31, 47-50; `grep -c paths: fork-ci.yml` → 0; `Ci.test_host_build_jobs` (job set, runners, both filters), `Ci.test_ci_matrix` unchanged; live runs 41878713095 and 41880689832 both started `host-build` |
| 32 | Each job runs the repo's own entry point and links a real binary — never a bespoke `clang` line, never `--only-compile` | ✓ VERIFIED | `make -C nxnative/dm/host GAME=01000A10041EA000 ... dmhost` then `ls` of the binary (lines 43-44; the Makefile's `dmhost` rule links at line 83); `build.py --game ... --out ...` then `ls` of `dmhost`/`libdmhost.so` (lines 56-57; `build.py:118-123` links both); `grep --only-compile` → nothing; `test_host_build_jobs` pins both command fragments; green-run logs: Android `compiled 190 sources, 0 failed` → `linked .../dmhost` + `linked .../libdmhost.so`, Apple ends with `-rwxr-xr-x ... nxnative/dm/host/dmhost` (4.6 MB) |
| 33 | The two jobs are independent — no `needs:`, no matrix — and each is named for the target it compiles | ✓ VERIFIED | No `needs:`/`matrix:` in the file; `name: host-apple` / `name: host-android` (`host-build.yml:29,46`); `test_host_build_jobs` asserts neither declares `needs`/`strategy`; run 41878713095 shows `host-android` success beside `host-apple` failure |
| 34 | Every `uses:` is SHA-pinned to the same commit `fork-ci.yml` uses; no `secrets.*`; only the literal `GAME=01000A10041EA000` | ✓ VERIFIED | Both `actions/checkout@3d3c42e5…` match `fork-ci.yml:38`; `Ci.test_actions_pinned`, `test_run_scripts_take_no_expressions`, `test_no_privileged_pr_trigger` pass; `grep -c "secrets\."` → 0 |
| 35 | `dm/host/Makefile`'s `CFLAGS` carries `-Werror=implicit-function-declaration`, and the Android build stays strict | ✓ VERIFIED | `Makefile:21` (flag exactly once on the `CFLAGS` line; the comment avoids repeating the literal); `build.py:66` still has it |
| 36 | A `dm/host` source that is neither in `SRC` nor matched by `hle_*.c` fails the static check, naming the file and the remedy | ✓ VERIFIED | `tests/arch_rules.py` rule 12 (lines 171-178); live run: `PASS dm/host: every source is in the Makefile SRC (line 23)`; a temp-tree reproduction of the rule flagged `zz_probe.c` (`missing -> ['zz_probe.c']`) while `hle_*.c` files were excluded |
| 37 | `tool_lock.main(argv)` returns 0/1/2 with the `MISMATCH` constant's exact sentence, and `no_run_message()` still names `brew install --cask dotnet-sdk` and `DOTNET_ROOT` | ✓ VERIFIED | `tool_lock.py:44-62`; `tests/test_tool_lock.py` asserts the exact line `MISMATCH + 'spirv-cross: lock lock-value / actual other-build'`, the clean 0, the usage 2 and both remedy substrings; the refactor diff shows the printed sentence byte-identical to the pre-phase `sys.exit` text |
| 38 | Backstop: `host-apple` links `dmhost` on `macos-26` inside 45 minutes without a tree edit for `MACOS_MIN`, failing loudly if the SDK 26.5 versus deployment target 26.6 mismatch bites | ✓ VERIFIED | Live green run: the recipe compiled with `-mmacosx-version-min=26.5` (from `xcrun -sdk macosx --show-sdk-version`, not the tree's 26.6) and left `nxnative/dm/host/dmhost` at 4,627,720 bytes; the earlier run failed loudly with clang's own diagnostic instead of passing silently |

**Score:** 38/38 truths verified (0 behavior-unverified; the four prior backstops are now measured or observed live)

### Deferred Items

| # | Item | Addressed In | Evidence |
|---|------|-------------|----------|
| 1 | A real `porter port --platform both` on this Mac producing the APK and the `.app`, with two live rows | Phase 12 | Phase 12 SC1: "re-ports one title per engine family against cached extraction, and runs a device smoke … prints one verdict" |

### Required Artifacts

| Artifact | Expected | Status | Details |
| -------- | -------- | ------ | ------- |
| `porter/pipeline.py` | `BOTH`, `MAC_NEEDS_MAC`, `TargetSkipped`, `Port.begin/_preflight/run_both`, `work`/`multi_target`, exit-shaping result | ✓ VERIFIED | All present, wired, and covered by the `Both` class; exactly one `lock.take` |
| `porter/cli.py` | `--platform both`, `_with_progress` returns the callback's code, one `result` emitter, 1-iff-failed | ✓ VERIFIED | Lines 24-25, 120, 140-145; `emit_result` is called only from `cmd_port.go()` |
| `porter/runlog.py` | `set_platform`, platform on the four stage events, never on `result`, cleared in `reset()` | ✓ VERIFIED | Lines 21, 24-25, 117-119; test asserts `platform` absent from `result` |
| `gui/app.py` | `MAC_HOST`, `TargetChoice`, `platform_arg`, `TargetRow`, the maps, the results block, `(platform,k)`, four finish branches, `open_btn` gone | ✓ VERIFIED | All present and wired; no `open_btn`, no `def open_out` |
| `.github/workflows/host-build.yml` | Two independent, path-filtered, SHA-pinned jobs running the repo's entry points | ✓ VERIFIED | 59 lines; static rules and `test_host_build_jobs` pass; both jobs observed running live |
| `nxnative/dm/host/Makefile` | `-Werror=implicit-function-declaration` on `CFLAGS` | ✓ VERIFIED | Line 21 |
| `tests/arch_rules.py` | Rule 12: `SRC` versus `dm/host/*.c|m|S`, by name and remedy | ✓ VERIFIED | Lines 171-178; PASS live; fires on a probe file |
| `nxnative/dm/gfx/tools/tool_lock.py` | `MISMATCH`, `main(argv) -> int`, `sys.exit` only in the guard | ✓ VERIFIED | Lines 44-62; one `sys.exit`, in `__main__` |
| `tests/test_porter.py` | `Both` class: order, inheritance, lock, skips, isolation, crash, log, exit code | ✓ VERIFIED | 13 tests, all green |
| `tests/test_bridge.py` | `Targets` (7), `Results` (6), new `Replay` cases incl. `test_port_both` | ✓ VERIFIED | 23 targeted tests green offscreen |
| `tests/test_tool_lock.py` | Synthetic mismatch/match/usage/no-run remedy, hermetic | ✓ VERIFIED | 4 tests green |
| `tests/test_workflows.py` | `Ci.test_host_build_jobs` beside the pinning walk | ✓ VERIFIED | Green |
| `tests/fixtures/bridge/port_both.jsonl` | A real two-target stream: `platform` on every stage event, one `targets` result | ✓ VERIFIED | 65 `"platform"` lines, 1 `"targets"` line, Android ok + Mac app failed |
| `docs/ARCHITECTURE.md` | The both run, the extended event keys, `targets` only on multi-target | ✓ VERIFIED | Lines 82 (the run), 94 (protocol) |

### Key Link Verification

| From | To | Via | Status | Details |
| ---- | -- | --- | ------ | ------- |
| `--platform both` (cli) | `Options.platform` → `Port.run()` → `run_both()` | argparse choice + dispatch after `_preflight`, before `toolchain.require` | ✓ WIRED | `cli.py:24`, `pipeline.py:149`; `test_run_dispatches_both_to_the_driver` (run_both once, `apk` never) |
| `runlog.set_platform(p)` | `platform` on `stage`/`step`/`progress`/`stage_end` → GUI `(platform,k)` key and prefix | wrapper's `_json` | ✓ WIRED | `runlog.py:117-119`, `gui/app.py:281-285`; both tests |
| Driver's `work`/`app`/`fam` | child `Port.work`/`.app`/`.fam` | inheritance before `child.run()` | ✓ WIRED | `pipeline.py:121-122`, `inputs()` skips `begin()`; lock test proves it |
| `result.targets[]` + flat `apk`/`data`/`app` | `TargetRow` rows and `install_now()` | `show_results`, `install_now` | ✓ WIRED | `gui/app.py:346-354`, `0` still reads the flat keys; tests |
| `platform_arg()` | `start()`'s single `--platform` token → `porter` argv | one call site | ✓ WIRED | `gui/app.py:223, 236`; argv asserted for all three states |
| Makefile `SRC` ↔ `dm/host/*.c|m|S` | arch_rules rule 12 → `tests/test_architecture.py` on every host | directory listing | ✓ WIRED | Live PASS, negative reproduction fires |
| `tool_lock.main(argv)` | exit code + `MISMATCH` sentence | test with patched `LOCK`/`tools_now` | ✓ WIRED | `tests/test_tool_lock.py` |
| workflow `paths:` filter | the two compile jobs; `fork-ci.yml` untouched | workflow-level trigger | ✓ WIRED | `host-build.yml:8-14`; `fork-ci.yml` has 0 `paths:`; both runs observed |
| branch protection (repo settings) | `host-apple`/`host-android` required checks | GitHub API | ✓ WIRED | `required_status_checks.contexts` = both names; `strict: false`, `enforce_admins: false` |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
| -------- | ------------- | ------ | ------------------ | ------ |
| `gui/app.py` TargetRow | `platform`, `status`, `out`, `reason` | `result.targets[]` from `Port.run_both` (per-child `res`) | Yes — each field is read straight off the event, no defaults or invented status | ✓ FLOWING |
| `gui/app.py` stage tree | row identity + Stage text | `stage`/`stage_end` events' `k`, `name`, `platform` | Yes — `platform` stamped by runlog from the live child | ✓ FLOWING |
| `gui/app.py` Install button | enabled state | `self.rows` (from the result) + `android_box` | Yes — a built Android row is required | ✓ FLOWING |
| `porter/pipeline.py` `targets[].out` | package path | child's `result['apk'] or ['app']` | Yes — absolute paths from `apk()`/`run_mac()` | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| -------- | ------- | ------ | ------ |
| `both` driver, skips, isolation, lock, exit code | `.venv/bin/python -m unittest tests.test_porter.Both tests.test_tool_lock tests.test_workflows -v` | 36 tests, `OK` | ✓ PASS |
| Targets row, result rows, both chains, finish lines | `QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest tests.test_bridge.Targets tests.test_bridge.Results tests.test_bridge.Replay -v` | 23 tests, `OK` | ✓ PASS |
| 980 px UI backstops and partial-success wording | `QT_QPA_PLATFORM=offscreen .venv/bin/python probe_both.py` | `8/8 checks passed`; step 940x30 / 2 lines, Stage column 180 px of 940, reason 940x45 / 3 lines, window stays 980, line `finished in 0:12: the Mac app failed` | ✓ PASS |
| `SRC` drift rule on the clean tree + the GUI warden rules | `.venv/bin/python tests/arch_rules.py` | `PASS dm/host: every source is in the Makefile SRC (line 23)`, `PASS gui/ holds no pipeline logic`, `PASS every GUI action is a CLI subcommand`, `all checks passed` | ✓ PASS |
| The `SRC` rule actually fires on an unlisted source (temp-tree reproduction, repo untouched) | inline Python over a temp copy + `zz_probe.c` | `missing -> ['zz_probe.c']`; `hle_account.c` … excluded by the wildcard | ✓ PASS |
| Golden fixture shape | `grep -c '"platform"' / '"targets"' port_both.jsonl` | 65 platform stamps; 1 `targets` with Android `ok` + Mac app `failed` | ✓ PASS |
| Workflow invariants | `grep` for `paths:`, `needs:`, `uses:`, `secrets.`, `--only-compile`, `GAME=` | Only `host-build.yml` has `paths:`; 2 pinned `uses:`; no `needs:`/secrets/`--only-compile`; `GAME` literal twice | ✓ PASS |

### Live Repository Checks (the prior human items)

| Item | Command | Result | Status |
| ---- | ------- | ------ | ------ |
| The guard caught a real break on the causing push | `gh api repos/NamelessSaint8/nx2android/actions/runs/41878713095` + `gh run view --log-failed` | Run on `23815667`: `host-android` **success**, `host-apple` **failure**; 8 `error: property '...' not found on ... MTL4FXTemporalScaler` at `nvn_mtl.m:10851-10854`, compiled against Xcode 26.6 / SDK 26.5 | ✓ VERIFIED |
| The break is fixed and both jobs pass | `gh api .../runs/41880689832` + `/jobs` + `gh run view --log` | Run on `1aff5907`: `conclusion: success`; `host-android` success 17:48:48–17:49:26 (`compiled 190 sources, 0 failed`, `linked .../dmhost` and `.../libdmhost.so`); `host-apple` success 17:48:50–17:50:00 (`-mmacosx-version-min=26.5`, `dmhost` 4,627,720 bytes; 52 warnings, no errors) | ✓ VERIFIED |
| The guard is the committed fix and leaves 27-SDK behaviour unchanged | `git show 1aff5907 -- nxnative/dm/gfx/nvn/nvn_mtl.m` | Adds `#if __MAC_OS_X_VERSION_MAX_ALLOWED >= 270000` around the content-offset branch, `else` outside it, and a comment; the `[RED]` warning remains unconditional | ✓ VERIFIED |
| The jobs are blocking | `gh api repos/NamelessSaint8/nx2android/branches/main/protection` | `required_status_checks.contexts` = `["host-apple","host-android"]`, `strict: false`, `enforce_admins: false` | ✓ VERIFIED |
| A docs-only push starts neither host job | trigger config + run list | `host-build.yml`'s push and pull-request triggers are the `paths: ['nxnative/**', '.github/**']` filters (the only other trigger is an explicit `workflow_dispatch`, which a push does not use); the host-build run list contains only the two code-bearing push heads (`1aff5907`, `23815667`) — the docs-only commits `34f104ff`/`e216accb` were pushed inside those ranges, not as standalone heads — while `fork-ci` (no `paths:`) runs on every push | ✓ VERIFIED by trigger configuration; a standalone docs-only push was not exercised (the docs-only head commit `b044895e` is not pushed) |

### Probe Execution

| Probe | Command | Result | Status |
| ----- | ------- | ------ | ------ |
| `probe_both.py` | `QT_QPA_PLATFORM=offscreen .venv/bin/python probe_both.py` | 8/8 checks passed; exit 0 | ✓ PASS |
| Other phase probes | — | The phase declares no `scripts/*/tests/probe-*.sh`; every task's `<automated>` verify is a `unittest` command, run above | SKIPPED (none besides `probe_both.py`) |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| ----------- | ----------- | ----------- | ------ | -------- |
| QUAL-07 | 11-02, 11-03 | Port view offers the target through porter (Android, Mac app, or both; two checkboxes defaulting to the host, Mac disabled off macOS); one run shows one result with a row per target; no second code path from view to pipeline | ✓ SATISFIED | `MAC_HOST`, `TargetChoice`, `platform_arg()` (one token), `TargetRow` per target with its own Reveal; `gui/ holds no pipeline logic` PASS; rows 10-27 |
| QUAL-09 | 11-04 | CI compiles `dm/host` for Apple arm64 and Android arm64 on every push as two blocking jobs path-filtered to `nxnative/**` and `.github/**`; a source missing from `SRC` fails naming the file; implicit declarations are errors on every toolchain; the `dmsh_chain.lock` refusal is covered by a test | ✓ SATISFIED | `host-build.yml` two independent path-filtered jobs; both ran live (run 41880689832 success); branch protection lists both as required; `Makefile:21`; arch_rules rule 12; `tool_lock.main` + `tests/test_tool_lock.py`; rows 31-38 |
| QUAL-13 | 11-01 | One run can produce the APK, the Mac app, or both: Android first, extraction and the shader split shared, per-target stages in their own folders; a failing target does not stop the other; the run reports per target and exits non-zero if any failed; a profile without `android.tsv` is skipped for Android with the reason named | ✓ SATISFIED | `run_both`, `begin()`, `TargetSkipped`, `targets[]`, `MAC_NEEDS_MAC`, exit contract; rows 1-9 |

**Orphaned requirements:** none. `REQUIREMENTS.md` maps exactly QUAL-07, QUAL-09 and QUAL-13 to Phase 11 (lines 239/241/245), and every one is claimed by a plan's `requirements:` frontmatter.

### Known Pre-Existing Issues (not Phase 11 gaps)

| Issue | Evidence | Impact on this phase |
| ----- | -------- | -------------------- |
| `fork-ci` is red on Linux legs, pre-existing | Run 41235725205 on head `d132fe9e` (before any Phase 11 commit): `test_probe.Probe.test_quoted_fix` fails on `ubuntu-22.04` (3.14 and 3.11) and `ubuntu-24.04-arm`, because the test computes `probe.clang(d)` outside its `sys.platform='darwin'` mock, so on Linux the expectation becomes `linux-x86_64`. The `windows-2025` leg is also red for separate pre-existing tests (`test_install_writes_both`, `test_nx_extract_gets_env`, `test_linux_arm64_dotnet_places`, `test_not_executable`, `test_killed_dlc_stage_redone`, `test_empty_default_takes_first_host_file`); `test_quoted_fix` passes there. | None. These are pre-existing failures on the base commit; the same legs were red before Phase 11 and are unrelated to the C host or the target choice. The phase's own CI (`host-build`) is green on the fix commit. |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| ---- | ---- | ------- | -------- | ------ |
| — | — | No `TBD`/`FIXME`/`XXX`/`HACK`/`PLACEHOLDER` in any file this phase changed | — | Debt-marker gate passes |
| `gui/app.py` | 112 | The word `open_out` survives in a comment ("exactly today's `open_out` once per row") | ℹ️ Info | Documentation only; `open_btn` and `def open_out` are gone (grep 0) |
| `gui/app.py` | 356-358 | `update_install_button` does not require a device to be chosen, while UI-SPEC rule 20's literal clause says "a device is chosen" | ℹ️ Info | Not a must-have (the plan's truth says "built Android row and `android` ticked"); behaviour is the pre-phase one (`porter install` falls back to the only connected device), so pressing Install still works. Worth a line in Phase 4 if the library re-hosts this button |

No blocker or warning anti-patterns were found. The phase's own prohibited patterns (RichText for porter strings, a second palette, a second view→pipeline path, a bespoke `clang` CI line, `--only-compile` as the gate, `paths:` on `fork-ci.yml`) are all absent.

### Human Verification Required

None. The six prior items are settled:

1. **The two CI jobs ran.** Run 41878713095: `host-android` success, `host-apple` failure on 8 MetalFX property errors; run 41880689832 after `1aff5907`: both success, with the Android link and the Apple `dmhost` binary confirmed in the logs. The docs-only branch is verified from the trigger configuration — push and pull-request are filtered to `nxnative/**` and `.github/**` (an explicit `workflow_dispatch` is the only other trigger) — while `fork-ci`, which has no `paths:`, still runs on every push; no standalone docs-only push was exercised because the docs-only head commit is not pushed.
2. **Branch protection is applied.** API readback: `host-apple` + `host-android` required, strict false, admin bypass allowed.
3-5. **The three 980 px visual checks are measured.** `probe_both.py` 8/8: step 940x30 / 2 lines, Stage column 180 px of 940, reason 940x45 / 3 lines, window stays 980.
6. **The partial-success wording is confirmed.** `finished in 0:12: the Mac app failed`, bar at 1000, two rows.

### Gaps Summary

No gaps. Every must-have is now verified: the `both` driver with its order, single scan, single lock, per-target skips and exit contract; the Port view's target choice, one-token mapping, per-target rows and four finish lines; the two path-filtered CI jobs, the branch protection that makes them blocking, and the two cheap guards. The guard was also demonstrated in the field — it caught a real SDK-version break on the push that caused it and went green on the fix. The only unobserved item is the real end-to-end `porter port --platform both` on a Mac, which is Phase 12's smoke and is recorded as deferred. The pre-existing `fork-ci` red legs are noted above and are not counted against this phase.

---

_Verified: 2026-11-04T18:05:00Z_
_Verifier: the agent (gsd-verifier)_
