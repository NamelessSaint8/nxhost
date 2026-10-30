---
phase: 01
review: 01-REVIEW.md
titles: json
findings:
  - id: WR-01
    severity: warning
    disposition: open
    title: "The CA-file fallback can run on Windows, where `/etc/ssl/...` resolves against the current drive"
  - id: WR-02
    severity: warning
    disposition: open
    title: "The urlopen scan test accepts any `context=`, not `context=tls.context()`"
  - id: WR-03
    severity: warning
    disposition: open
    title: "The hook overrides are copies of PyInstaller 6.22.3's hooks, with nothing that fails when PyInstaller moves"
  - id: IN-01
    severity: info
    disposition: open
    title: "Only the first existing CA file is tried; an unreadable or empty one fails the download instead of falling through"
  - id: IN-02
    severity: info
    disposition: open
    title: "`x509_ca` does not count a capath store, so the \"used as it is\" contract is not exact"
  - id: IN-03
    severity: info
    disposition: open
    title: "`test_no_host_file_stays_verifying` asserts the mock's own defaults"
  - id: WR-04
    severity: warning
    disposition: fixed
    title: "`upstream-diff` is described as \"a report, not a gate\", but the release job needs it"
  - id: WR-05
    severity: warning
    disposition: fixed
    title: "The GUI's `devices` limit (15 s) is shorter than porter's own adb timeouts (30 s)"
  - id: WR-06
    severity: warning
    disposition: fixed
    title: "Unit tests start the developer machine's real adb server"
  - id: IN-04
    severity: info
    disposition: open
    title: "Two ways of escaping, and a misleading status on quit"
open: 7
total: 10
recorded: 2026-10-30T07:51:36.899Z
---

# Phase 01: Code Review Disposition

| Finding | Severity | Disposition | Source |
|---------|----------|-------------|--------|
| WR-01 | warning | open | - |
| WR-02 | warning | open | - |
| WR-03 | warning | open | - |
| IN-01 | info | open | - |
| IN-02 | info | open | - |
| IN-03 | info | open | - |
| WR-04 | warning | fixed | 01-REVIEW-FIX.md (not in the current review) |
| WR-05 | warning | fixed | 01-REVIEW-FIX.md (not in the current review) |
| WR-06 | warning | fixed | 01-REVIEW-FIX.md (not in the current review) |
| IN-04 | info | open | - (not in the current review) |

Dispositions: `open` (recorded, not yet triaged), `fixed`, `skipped`, `deferred`.
Set `deferred` by hand and put the reason in the Source cell; both are preserved. A `|` in the reason is kept as prose and escaped on the next run.
Re-running the gate keeps every row it can. A row the current review no longer reports is kept and its Source cell flagged, so a finding does not leave this record silently. ONE exception: when a finding id is REUSED by a different finding, the earlier decision cannot keep a row — the id is taken — and it is dropped. A RECORDED decision (anything but `open`) is named on the console when that happens; a row still at `open` is replaced silently, because `open` records no decision to lose.
