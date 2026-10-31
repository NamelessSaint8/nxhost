# Phase 3 — UI Review (re-audit after gap closure 03-13..03-15)

**Audited:** 2026-10-31
**Baseline:** 03-UI-SPEC.md (approved); previous review 15/24
**Screenshots:** no Playwright run (desktop Qt app, no dev server). Offscreen renders (`QT_QPA_PLATFORM=offscreen`, Qt default style and fonts) through the `tests/test_firstrun.py` stand-in with `setup_missing.json`: main window plus banner, Setup tab, all five wizard pages, the tools page at 720x560, and the shell. A second pass applied a dark QPalette (Window `#202020`) to the main window, the Setup tab and every wizard page. Renders: `/private/tmp/claude-501/-Volumes-Data-Dev-nx2android/ef87d0b2-3303-461d-bdf9-90a67f7b2427/scratchpad/ui-shots-2/` (dark ones under `dark/`). Native-theme look on each host is still a human check.
**Interaction captures:** off (workflow.ui_interaction_capture is false). The interaction findings come from reading the code.

---

## Pillar Scores

| Pillar | Score | Was | Key Finding |
|--------|-------|-----|-------------|
| 1. Copywriting | 3/4 | 2 | "porter" is gone from the Setup tab's check line, download-list failure and device list. Still open: one action with two names, `about 200.0 MB`, and the lowercase keys line (all deferred on purpose) |
| 2. Visuals | 3/4 | 2 | The device page now reads top-down with the spare space below. The tools page still states the missing NDK three times |
| 3. Color | 3/4 | 2 | `firstrun.py` has no hex outside COLOUR, and the banner follows a dark palette. The Setup tab's download error (`app.py:342`) still hard-codes `#c62828` |
| 4. Typography | 3/4 | 3 | Unchanged: Download all missing is bold at P, not P+2; Accept and continue is the plain QWizard Next |
| 5. Spacing | 3/4 | 3 | The device page rhythm is fixed. Download all missing still stretches across the whole row |
| 6. Experience Design | 3/4 | 3 | One run per runner and Cancel from the start (03-15) make the two download views agree. Back still shows `&Back`, and the two flows still have different names and pre-steps |

**Overall: 18/24** (was 15/24, +3)

---

## Status of the previous findings

**Fixed (confirmed in code and renders)**
- Top fix 1, device page layout: `wiz-device.png` shows the heading at the top margin, three numbered lines, the empty line, and the free space below. The ok step's adb path is hidden (03-14 Task 2).
- Top fix 3, COLOUR table: `fill_checks` and `failed()` go through `colour()`, `#ef6c00` is gone from `firstrun.py`, and the banner and its `!` restyle on `PaletteChange`. In the dark render the banner is a dark amber bar with light text and the glyphs stay readable (`dark/main-missing.png`, `dark/wiz-done.png`) (03-14 Task 3).
- Top fix 2, in part: the Setup tab's check line, its download-list failure and the Port tab's device item use `firstrun.failed`/`firstrun.cause`. A Prepare finished from the Setup tab reads `.NET tools are ready.` (03-15 Task 3).

**Deferred on purpose (03-15-PLAN findings ledger, 03-REVIEW-DISPOSITION.md). They are still visible, so they still count against the score.**
- `Download missing tools` vs `Download all missing`, and the Setup tab's plain `cancelled` (`app.py:275, 278, 309, 335, 338`). This is upstream's name, and the rename is planned for Phase 6's copy pass.
- The Port tab card and the Games note still say porter (`app.py:33-38`, which are upstream's `cause`/`failed`). Phase 4 replaces that view.
- The keys result line starts lowercase: `not set. Choose your prod.keys…` (`dark/wiz-keys.png`).
- `about 200.0 MB` (`firstrun.py:41`, `.1f`).
- The tools page repeats the fact three times, and the NDK size cell is empty (`wiz-tools-min.png`).
- Download all missing is not P+2; Accept and continue is unstyled; the done page's adb path is not Mono; Download all missing fills the row.
- `&Back`/`&Next` mnemonics: `Wizard.__init__` never sets the Back text (`firstrun.py:129` sets only CustomButton1 and Finish).
- The glyph colours of KeyRow, DeviceRow and Line are set when the row is built. They are rebuilt on the next answer.
- The done page has no primary action in the shell (expected until Phase 4).
- The Setup tab's `reading the download lists…` pre-step.

**New in this audit**
- WARNING: `app.py:342` writes the Setup tab's download failure in a hard-coded `<span style="color:#c62828">`. It was not routed through `colour()` the way the check line was, so a failed download on a dark theme shows light-only red at about 3:1. This is a hook-sized fix inside the Setup tab, which is the scope 03-15 already touched.
- INFO: `app.py:19, 131-137, 194, 218` (the status colours of the Port and Games views, the log and the stage glyphs) still use light-only hex values. They are upstream's Port view, which Phase 4 replaces, so they are outside this phase's contract and are listed here only so they are not lost.

---

## Top 3 Priority Fixes

1. **The tools page says the same thing three times, and its total reads `about 200.0 MB`** (WARNING). Players read `missing: Android NDK`, then `Download missing tools, or choose your own`, then the row's `Download missing tools, or set the NDK folder`. Two of those name a button that is not on the page. Fix: hide `StepPage.detail`/`fix` on `ToolsPage` (the table carries them), and format `size()` with `:.0f` at 10 or more of a unit.
2. **The Setup tab's download error ignores the COLOUR table** (WARNING). It is unreadable red on a dark theme. Fix: build the `app.py:342` span with `firstrun.colour(self, 'bad')`, or route it through `firstrun.failed`-style escaping.
3. **The wizard chrome breaks two contract rules at once** (WARNING). `< &Back` shows its mnemonic, and `Download all missing` is a bold, full-width P button, not a right-aligned P+2 primary. Fix: in `Wizard.__init__` add `setButtonText(QWizard.BackButton, 'Back')`. In `ToolsPage`, end the button row with `addStretch(1)` before the button and apply the same font as `DonePage.port`.

(Phase 6 copy pass, already planned: rename `Download missing tools` to the wizard's name across porter fix text, README and the Setup tab.)

---

## Detailed Findings

### Pillar 1: Copywriting (3/4)
- PASS: No "porter" appears on the Setup tab or in the device list (`app.py:150` comment, `firstrun.cause`). The Prepare done line is `firstrun.PREPARED` (`app.py:338`).
- PASS: The device steps are three numbered lines (`wiz-device.png`) and match the contract.
- WARNING (deferred): One action has two names. The Setup tab and porter's row fix say `Download missing tools`, and the wizard says `Download all missing`.
- WARNING (deferred): The keys line is lowercase and has no subject. The total reads `about 200.0 MB`.
- WARNING (deferred, outside this phase's screens): the Port card still shows `porter failed` / `porter didn't answer` (`app.py:33-38`).

### Pillar 2: Visuals (3/4)
- PASS: The device page now has a clear top-down order.
- PASS: The done page keeps `Port a game` as its focal point in both themes.
- WARNING: The tools page repeats the missing tool three times, and the NDK size cell is empty while the total counts 200 MB.

### Pillar 3: Color (3/4)
- PASS: `firstrun.py` has no hex literal outside the COLOUR table and its comment. The dark render confirms the banner, the `!` and the glyphs adapt.
- WARNING: `app.py:342` hard-codes `#c62828` on the Setup tab's download failure.
- INFO (deferred): The row glyph colours are set at build time, and the Port and Games views use upstream's light-only hex values.
- The accent stays on the default button, the progress bar and the selection. PASS.

### Pillar 4: Typography (3/4)
- WARNING (deferred): `ToolsPage.dl` is bold P, while `DonePage.port` is P+2 (the dark render shows the size gap). `Accept and continue` is unstyled.
- PASS: The headings are P+4 bold and the paths are Mono. Two weights are used.

### Pillar 5: Spacing (3/4)
- PASS: The device page's labels sit at their natural height, and the trailing stretch takes the rest (`setStretch(self.v.count() - 1, …)`).
- PASS: The tokens are 16/8/4, and the banner is (16,8,16,8).
- WARNING (deferred): `Download all missing` spans the full 700 px row (`wiz-tools-min.png`, `dark/wiz-tools.png`).

### Pillar 6: Experience Design (3/4)
- PASS: `Porter.start` refuses a second run and emits `started`, so both download buttons show Cancel from the first moment. `setup --json` runs one at a time with a 150 s limit. The wizard starts no Prepare while the window is quitting. The Setup tab saves only the fields the player changed, so a wizard save survives a re-check (CR-01).
- WARNING (deferred): `< &Back` / `&Next >` show their mnemonics.
- WARNING (deferred): The Setup tab and the wizard still differ in naming, cancelled copy and the download-list pre-step.
- Registry audit: not applicable (no shadcn).

---

## Files Audited
- gui/firstrun.py, gui/app.py, gui/shell.py, gui/runner.py
- tests/test_firstrun.py (harness), tests/fixtures/bridge/setup_missing.json
- 03-UI-SPEC.md, the previous 03-UI-REVIEW.md, 03-14-SUMMARY.md, 03-15-SUMMARY.md, the 03-15-PLAN.md findings ledger, 03-REVIEW-DISPOSITION.md
- Renders: `/private/tmp/claude-501/-Volumes-Data-Dev-nx2android/ef87d0b2-3303-461d-bdf9-90a67f7b2427/scratchpad/ui-shots-2/*.png` and `.../ui-shots-2/dark/*.png`; render script `.../scratchpad/shoot2.py` (wraps `.../scratchpad/shoot.py`)
