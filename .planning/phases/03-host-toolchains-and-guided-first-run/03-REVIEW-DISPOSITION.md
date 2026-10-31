---
phase: 03
review: 03-REVIEW.md
titles: json
findings:
  - id: CR-01
    severity: critical
    disposition: open
    title: "The Setup tab's \"Save and check\" overwrites settings the wizard just saved"
  - id: WR-01
    severity: warning
    disposition: open
    title: "A download the server cuts off cleanly is hashed as complete, then deleted, with no retry or resume"
  - id: WR-02
    severity: warning
    disposition: open
    title: "The GUI's `setup` limit (45 s) is shorter than the probe's own limits, so a slow first probe is killed and never cached"
  - id: WR-03
    severity: warning
    disposition: open
    title: "Probe cache write: fixed temp name, unhandled `OSError`, and two concurrent `setup` runs after every fetch"
  - id: WR-04
    severity: warning
    disposition: open
    title: "The Setup tab can start a second run on the window's shared `fetch`, orphaning the first one"
  - id: WR-05
    severity: warning
    disposition: open
    title: "The automatic Prepare after a download ignores a quit in progress"
  - id: WR-06
    severity: warning
    disposition: open
    title: "The probe's fix commands leave paths unquoted and break under \"Application Support\""
  - id: IN-01
    severity: info
    disposition: open
    title: "`Gate.start` is never used"
  - id: IN-02
    severity: info
    disposition: open
    title: "The keys page shows the path twice for a missing file"
  - id: IN-03
    severity: info
    disposition: open
    title: "The `.desktop` `TryExec` and `Icon` values are not string-escaped"
  - id: IN-04
    severity: info
    disposition: open
    title: "`devtools/ndk_pin.py` repeats the asset name and tag instead of reading them from the pin"
  - id: IN-05
    severity: info
    disposition: open
    title: "The plain CLI `config legal` skips the version guard, and `--prepare` silently wins over `--download`"
  - id: IN-06
    severity: info
    disposition: open
    title: "A `.part` left from an in-place re-upload gives a misleading message"
  - id: IN-07
    severity: info
    disposition: open
    title: "`setup.tool_items` calls the private `fetch._pinned`"
  - id: IN-08
    severity: info
    disposition: open
    title: "The `glslc` fallback in `build.py` applies on every host, not only Linux arm64"
open: 15
total: 15
recorded: 2026-10-31T17:42:05.244Z
---

# Phase 03: Code Review Disposition

| Finding | Severity | Disposition | Source |
|---------|----------|-------------|--------|
| CR-01 | critical | open | - |
| WR-01 | warning | open | - |
| WR-02 | warning | open | - |
| WR-03 | warning | open | - |
| WR-04 | warning | open | - |
| WR-05 | warning | open | - |
| WR-06 | warning | open | - |
| IN-01 | info | open | - |
| IN-02 | info | open | - |
| IN-03 | info | open | - |
| IN-04 | info | open | - |
| IN-05 | info | open | - |
| IN-06 | info | open | - |
| IN-07 | info | open | - |
| IN-08 | info | open | - |

Dispositions: `open` (recorded, not yet triaged), `fixed`, `skipped`, `deferred`.
Set `deferred` by hand and put the reason in the Source cell; both are preserved. A `|` in the reason is kept as prose and escaped on the next run.
Re-running the gate keeps every row it can. A row the current review no longer reports is kept and its Source cell flagged, so a finding does not leave this record silently. ONE exception: when a finding id is REUSED by a different finding, the earlier decision cannot keep a row — the id is taken — and it is dropped. A RECORDED decision (anything but `open`) is named on the console when that happens; a row still at `open` is replaced silently, because `open` records no decision to lose.
