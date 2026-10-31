# Phase 3 — UI Review

**Audited:** 2026-10-31
**Baseline:** 03-UI-SPEC.md (approved)
**Screenshots:** not captured with Playwright (desktop Qt app, no dev server). Offscreen renders (`QT_QPA_PLATFORM=offscreen`, Qt default fonts, Fusion light only) were taken through the `tests/test_firstrun.py` stand-in with `setup_missing.json`: main window plus banner, Setup tab, all five wizard pages, the tools page at its 720x560 minimum, and the shell. Colour and theme findings are approximate. Dark theme was not rendered.
**Interaction captures:** off (workflow.ui_interaction_capture is false). The interaction findings come from reading the code.

---

## Pillar Scores

| Pillar | Score | Key Finding |
|--------|-------|-------------|
| 1. Copywriting | 2/4 | The Setup tab still says "porter" and keeps its own idle and cancelled wording, so the same action has two names |
| 2. Visuals | 2/4 | The device page spreads its few widgets down the whole page; the tools page repeats the same fact three times |
| 3. Color | 2/4 | `fill_checks` and `failed()` hard-code `#ef6c00` and `#c62828`; the banner tint is chosen once and never follows a theme change |
| 4. Typography | 3/4 | Download all missing is bold but not P+2; Accept and continue is QWizard's plain Next button |
| 5. Spacing | 3/4 | The tokens are followed, but Download all missing stretches across the full width, and the device page stretch breaks the spacing rhythm |
| 6. Experience Design | 3/4 | States are well covered. The Setup tab's cancel and finish wording does not match the wizard, and Back and Next keep their `&` mnemonics |

**Overall: 15/24**

---

## Top 3 Priority Fixes

1. **The device page layout falls apart when no device is connected** (BLOCKER-adjacent WARNING). In `wiz-device.png` the heading sits about 70 px down, and four lines float with gaps of about 90 px between them. The page detail shows only a bare adb path (`/opt/.../adb`), which means nothing to a player. Cause: `DevicePage` builds with `stretch=False`, the list gets stretch 1, and then `self.list.hide()` leaves the free space to be shared among all the labels (`gui/firstrun.py:760-764`). Fix: add `self.v.addStretch(1)` after `self.error` and toggle it against the list (or keep the list visible with a placeholder item), and hide `self.detail` when the step is ok. Also put the three steps on separate lines (`\n`) so they read as a numbered list.
2. **The Setup tab breaks the copy contract** (WARNING). `gui/app.py:33-38` `cause`/`failed` show "porter didn't answer" and "porter failed" in the Setup tab's `check_msg`, which is exactly the launch failure path in Launch 8. `app.py:151` shows `porter: <cause>` in the device combo. `app.py:331` says `cancelled` and `the tools are ready` where the spec says `cancelled. Download all missing resumes where it stopped.` and `.NET tools are ready.`. The idle button reads `Download missing tools` (`app.py:278, 330`) while the wizard says `Download all missing (<size>)`. Fix: point `SetupTab.check` at `firstrun.failed` (a hook-line change, as `fill_checks` already is), and reuse the wizard's strings for the finished and idle labels.
3. **Colours bypass the `COLOUR` table** (WARNING). `fill_checks` (`gui/firstrun.py:866`) still draws optional-missing rows in `#ef6c00` (3.08:1, which the spec explicitly replaced) and uses the light-only `#2e7d32` and `#c62828`. `firstrun.failed()` (`:368`) hard-codes `#c62828`, so the error is red on dark backgrounds at about 3:1. The banner stylesheet (`:410`) and its `!` are set once in `attach`, so a light or dark switch while the app runs leaves a cream bar on a dark window. Fix: use `colour(table, 'ok'|'bad'|'note')` in `fill_checks`, pass a widget into `failed()` for `colour(w,'bad')`, and reapply the banner style in `on_ready` (or on `QEvent.PaletteChange`).

---

## Detailed Findings

### Pillar 1: Copywriting (2/4)
- WARNING: "porter" is visible to players through `gui/app.py` `cause`/`failed` (lines 33-38), which the Setup tab uses on a failed `setup --json`, and through `app.py:151` (`'porter: ' + cause(fail)`). The spec forbids it: "Players never see the word porter".
- WARNING: The same action has two names. The Setup tab says `Download missing tools` and its help paragraph uses **Download missing tools**, while the wizard says `Download all missing (…)`. Porter's own fix text also says "Download missing tools, or set the NDK folder" (tools page, `setup_missing.json`).
- WARNING: The Setup tab's finish copy is `cancelled` / `the tools are ready` (`app.py:331`), not the contract's strings.
- WARNING: The keys result line reads `not set. Choose your prod.keys (dumped from your own Switch).`, starting with a lowercase word and no subject (`firstrun.py:582`, `wiz-keys.png`). Prefix it with `prod.keys: `, or capitalise it when there is no path.
- WARNING: The tools total reads `about 200.0 MB` (`size()` with `.1f`). "about 200 MB" is the contract's wording for .NET.
- Device steps are one run-on paragraph (`firstrun.py:761`), so the "three numbered instructions" are hard to scan.
- PASS: The headings, Accept and continue, Skip setup, Close setup, Skip: install later, Every tool is here, the keys body and empty state, the device empty state and No device yet all match the contract word for word.

### Pillar 2: Visuals (2/4)
- WARNING: The device page with no device has its heading offset and large blank bands between the labels (see Fix 1).
- WARNING: The tools page repeats one fact three times. The step detail says `missing: Android NDK`, the step fix says `Download missing tools, or choose your own`, and the row fix says `Download missing tools, or set the NDK folder`, all above or inside the table (`wiz-tools-min.png`). `StepPage` shows the detail and fix for the tools page even though the table already carries them. Hide `detail`/`fix` on `ToolsPage`, or keep only the summary.
- WARNING: The NDK row's `Size or note` cell is empty while a download is offered. The column header promises a size, and the fixture's NDK has no `download`, yet the total still counts it as "about 200 MB". Check that `total()` and the cell agree.
- On the done page, `Port a game` is the clear focal point and the glyph column scans well. PASS.
- In the banner, `!`, the text and Continue setup sit on one line and the tint stands apart from the tab chrome. PASS.

### Pillar 3: Color (2/4)
- WARNING: `#ef6c00`, `#2e7d32` and `#c62828` are hard-coded in `fill_checks` (`firstrun.py:866`), which goes against the Color section's "note #9a5b00 replaces #ef6c00".
- WARNING: `failed()` (`firstrun.py:368`) uses a light-only red, and every Retry error in the wizard uses it.
- WARNING: The banner and `!` colours are fixed at `attach` time (`firstrun.py:410-412`), and so are the glyph colours of `KeyRow`/`DeviceRow`/`Line`, chosen at construction. Only the Line rows are rebuilt on redraw.
- The accent is limited to the default button, the progress bar and list selection, as the contract says. Links use the palette Link colour. PASS.
- The theme risk is still the spec's open assumption (lightness < 128). Rendering in dark theme is a human check.

### Pillar 4: Typography (3/4)
- WARNING: `ToolsPage.dl` is bold at P, not P+2 (`firstrun.py:630`), but `DonePage.port` is P+2 (`:826`). The two primary buttons do not match.
- WARNING: `Accept and continue` is QWizard's Next button: no bold, no P+2, and no 36 px minimum height (`wiz-legal.png`), although the contract lists it as a primary action.
- The page headings are P+4 bold, and Mono is the 9 pt system fixed font for paths, commands and adb state. Only two weights are used. PASS.
- Minor: the done page's `adb: /opt/.../adb` path is in the Body font, not Mono.

### Pillar 5: Spacing (3/4)
- Margins are 16, page spacing 16 plus 8 under the heading (24), 16 plus 16 above the done row (32), the banner is (16,8,16,8), and the rows use 8 and 4. All match the scale. PASS.
- WARNING: `Download all missing` fills the full row width when `all_here` is hidden, because the stretch belongs to the hidden label (`firstrun.py:631`). The row should end in `addStretch` with the button on the right, as the done page does.
- WARNING: The device page spacing (Fix 1).
- The tools page at 720x560 keeps the button row in view and the table scrolls. PASS (backstop check done offscreen).

### Pillar 6: Experience Design (3/4)
- PASS: There is one wizard at most, the device poll is chained (no stacking), the saving… states disable their source, Retry links are present, Next never blocks, and the close guard covers the fetch.
- WARNING: `< Back` / `Next >` show QWizard's mnemonic underline (`&Back`) in every render, against the "no `&`" rule. Set the button text with `setButtonText(QWizard.BackButton, 'Back')` and do the same for Next.
- WARNING: The Setup tab's download row and the wizard can drive the same `fetch`. The Setup tab finishes with different copy, and its `dl_btn` is disabled during `reading the download lists…`, which is a second pre-step the wizard does not have. The two flows behave differently.
- WARNING: When the shell (`gui/shell.py`) is not ready, `DonePage` shows no Port a game, so the page has no primary action. That is expected for Phase 4, but the done page then ends on Close setup alone.
- Registry audit: not applicable (no shadcn).

---

## Files Audited
- gui/firstrun.py, gui/shell.py, gui/app.py (hook lines 1-40, 260-440), gui/runner.py (call_json use)
- tests/test_firstrun.py (harness), tests/fixtures/bridge/setup_missing.json, fake_porter.py
- .planning/phases/03-host-toolchains-and-guided-first-run/03-UI-SPEC.md
- Offscreen renders: /private/tmp/claude-501/-Volumes-Data-Dev-nx2android/ef87d0b2-3303-461d-bdf9-90a67f7b2427/scratchpad/ui-shots/*.png
