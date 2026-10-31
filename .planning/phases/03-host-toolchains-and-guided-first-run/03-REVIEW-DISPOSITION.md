---
phase: 03
review: 03-REVIEW.md
titles: json
findings:
  - id: CR-01
    severity: critical
    disposition: fixed
    title: "The Setup tab's \"Save and check\" overwrites settings the wizard just saved"
  - id: WR-01
    severity: warning
    disposition: fixed
    title: "A download the server cuts off cleanly is hashed as complete, then deleted, with no retry or resume"
  - id: WR-02
    severity: warning
    disposition: fixed
    title: "The GUI's `setup` limit (45 s) is shorter than the probe's own limits, so a slow first probe is killed and never cached"
  - id: WR-03
    severity: warning
    disposition: fixed
    title: "Probe cache write: fixed temp name, unhandled `OSError`, and two concurrent `setup` runs after every fetch"
  - id: WR-04
    severity: warning
    disposition: fixed
    title: "The Setup tab can start a second run on the window's shared `fetch`, orphaning the first one"
  - id: WR-05
    severity: warning
    disposition: fixed
    title: "The automatic Prepare after a download ignores a quit in progress"
  - id: WR-06
    severity: warning
    disposition: fixed
    title: "The probe's fix commands leave paths unquoted and break under \"Application Support\""
  - id: IN-01
    severity: info
    disposition: fixed
    title: "`Gate.start` is never used"
  - id: IN-02
    severity: info
    disposition: deferred
    title: "The keys page shows the path twice for a missing file"
  - id: IN-03
    severity: info
    disposition: deferred
    title: "The `.desktop` `TryExec` and `Icon` values are not string-escaped"
  - id: IN-04
    severity: info
    disposition: deferred
    title: "`devtools/ndk_pin.py` repeats the asset name and tag instead of reading them from the pin"
  - id: IN-05
    severity: info
    disposition: deferred
    title: "The plain CLI `config legal` skips the version guard, and `--prepare` silently wins over `--download`"
  - id: IN-06
    severity: info
    disposition: deferred
    title: "A `.part` left from an in-place re-upload gives a misleading message"
  - id: IN-07
    severity: info
    disposition: deferred
    title: "`setup.tool_items` calls the private `fetch._pinned`"
  - id: IN-08
    severity: info
    disposition: deferred
    title: "The `glslc` fallback in `build.py` applies on every host, not only Linux arm64"
open: 0
total: 15
recorded: 2026-10-31T17:42:05.244Z
---

# Phase 03: Code Review Disposition

| Finding | Severity | Disposition | Source |
|---------|----------|-------------|--------|
| CR-01 | critical | fixed | 03-15 Task 1 |
| WR-01 | warning | fixed | 03-13 Tasks 1-2 |
| WR-02 | warning | fixed | 03-15 Task 3 (setup limit 150 s, above the probe's two 60 s steps) |
| WR-03 | warning | fixed | porter half 03-13 Task 3 (per-process temp file, best-effort write); GUI half 03-15 Task 2 (one setup --json at a time) |
| WR-04 | warning | fixed | 03-15 Task 2 (also implements T-03-35's open mitigation) |
| WR-05 | warning | fixed | 03-14 Task 1 |
| WR-06 | warning | fixed | 03-13 Task 3 |
| IN-01 | info | fixed | 03-14 Task 3 (the same Gate line) |
| IN-02 | info | deferred | porter/keys.py:17 and the keys page are touched by no gap task; a one-line porter change plus a test assertion, for a quick task |
| IN-03 | info | deferred | porter/desktop.py is touched by no gap task; only a backslash in the bundle folder's name triggers it; a quick task |
| IN-04 | info | deferred | devtools/ndk_pin.py is a release-time script touched by no gap task; fix before the next community NDK pin bump |
| IN-05 | info | deferred | porter/cli.py is upstream's busy file (hook lines only) and the GUI always sends the guarded `config legal … --json`; a quick task |
| IN-06 | info | deferred | naming the `.part` after the pinned hash changes the resume key D-22 defines and discards testers' existing parts on upgrade; today it costs one misleading message after a rare in-place re-upload, and the next press works; revisit with the next community NDK pin bump |
| IN-07 | info | deferred | no behaviour change; renaming `fetch._pinned` touches porter/setup.py, porter/fetch.py and the tests that patch it; a quick task |
| IN-08 | info | deferred | nxnative/dm/android/build.py is touched by no gap task; it belongs with Phase 6's on-device parity work (VER-02) |

UI review (03-UI-REVIEW.md) items, recorded by 03-15:
- UI top fix 1: fixed, 03-14 Task 2.
- UI top fix 2: fixed in part, 03-15 Task 3: no "porter" on the Setup tab's check line, its download-list failure or the Port tab's device list; the Setup tab's Prepare-done line is the wizard's. The button name and its cancelled line are deferred (next item).
- UI top fix 3: fixed, 03-14 Task 3.
- One action, two names (the Setup tab's button and help text, its `cancelled` line, porter's fix text, README.md:14 and docs/ARCHITECTURE.md use upstream's name; the wizard's contract says `Download all missing`): deferred. The name is upstream's (gui/app.py, porter/toolchain.py:130, README.md:14); renaming it means porter fix text in five modules, README, ARCHITECTURE and about ten test assertions. The Setup tab keeps its own name and its plain `cancelled` until then, because the contract's cancelled line names a button that tab does not have. Phase 6 makes the shell (which has only the wizard's button) the default; the rename belongs to that copy pass.
- The Port tab card and the Games note still say porter (gui/app.py's own cause()/failed(), upstream's helpers; tests/test_bridge.py test_empty_answer pins it): deferred, outside the Setup tab; Phase 4 replaces the Port view.
- Keys result line starts lowercase with no subject: deferred, KeysPage.redraw is touched by no gap task.
- Tools total reads `about 200.0 MB`: deferred, size()'s one decimal; touched by no gap task.
- Tools page states the missing tool three times (step detail, step fix, row fix); the NDK row's size cell is empty while the total counts it: deferred, ToolsPage.redraw and total() are touched by no gap task.
- Download all missing is bold but not P+2; Accept and continue is the plain QWizard Next; the done page's adb path is not in Mono; Download all missing fills the row when `Every tool is here.` is hidden: deferred, page typography and the tools button row are touched by no gap task.
- Back and Next show QWizard's `&` mnemonics: deferred, Wizard.__init__ is touched by no gap task.
- KeyRow, DeviceRow and Line glyph colours are chosen when the row is built: deferred, the rows are rebuilt on every answer, so a theme switch shows on the next one; the banner, which never redraws, follows at once (03-14 Task 3).
- The done page has no primary action in the shell: deferred, expected until Phase 4 gives the shell a port view.
- The Setup tab's `reading the download lists…` pre-step that the wizard does not have: deferred, the dialog flow is upstream's; 03-15 Task 2 makes the two flows share one run safely.

Dispositions: `open` (recorded, not yet triaged), `fixed`, `skipped`, `deferred`.
Set `deferred` by hand and put the reason in the Source cell; both are preserved. A `|` in the reason is kept as prose and escaped on the next run.
Re-running the gate keeps every row it can. A row the current review no longer reports is kept and its Source cell flagged, so a finding does not leave this record silently. ONE exception: when a finding id is REUSED by a different finding, the earlier decision cannot keep a row — the id is taken — and it is dropped. A RECORDED decision (anything but `open`) is named on the console when that happens; a row still at `open` is replaced silently, because `open` records no decision to lose.
