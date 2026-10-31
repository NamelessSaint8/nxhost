---
phase: 02
review: 02-REVIEW.md
titles: json
findings:
  - id: CR-04
    severity: critical
    disposition: fixed
    title: "Links are checked against the unpack folder, but a different tree is installed, so a link can leave the installed toolchain (resolved by 02-13)"
  - id: WR-05
    severity: warning
    disposition: fixed
    title: "Replacing an existing toolchain is not atomic (resolved by 02-13)"
  - id: IN-06
    severity: info
    disposition: fixed
    title: "Some hostile zips are refused with a raw OS error instead of the `refused` message (resolved by 02-13)"
  - id: WR-01
    severity: warning
    disposition: open
    title: "`porter install` recovers the pack before taking the port's lock (carried forward, not touched by 02-11/02-12)"
  - id: WR-02
    severity: warning
    disposition: open
    title: "The tools lock is held for a whole survey, not just the nx_extract build (carried forward)"
  - id: WR-03
    severity: warning
    disposition: open
    title: "The signing key is published only through `os.link` (carried forward)"
  - id: WR-04
    severity: warning
    disposition: open
    title: "Linux arm64 gets the x86-64 NDK and platform-tools as \"pinned\" (carried forward)"
  - id: WR-06
    severity: warning
    disposition: open
    title: "Moving the old data pack aside has no Windows retry, unlike `swap_in` (carried forward)"
  - id: WR-07
    severity: warning
    disposition: open
    title: "Normalization aliases on APFS bypass the \"no member under a link\" check"
  - id: WR-08
    severity: warning
    disposition: open
    title: "The WR-05 failure (a toolchain file in use on Windows) still ends in a raw traceback"
  - id: WR-09
    severity: warning
    disposition: open
    title: "`test_pinned_archives_pass` runs the rule on link names only, not the real member list"
  - id: WR-10
    severity: warning
    disposition: open
    title: "`zip_links.py` never checks that it read the pinned file"
  - id: IN-01
    severity: info
    disposition: open
    title: "The status badge text is the one game-card string left unescaped (carried forward)"
  - id: IN-02
    severity: info
    disposition: open
    title: "A failed inspect keeps the previous game's language list (carried forward)"
  - id: IN-03
    severity: info
    disposition: open
    title: "The NuGet check assumes the first package folder (carried forward)"
  - id: IN-04
    severity: info
    disposition: open
    title: "Two game folders of one title with one output folder race on the pack's `.partial` (carried forward)"
  - id: IN-05
    severity: info
    disposition: open
    title: "Stale reference to the deleted probe packer (carried forward)"
  - id: IN-07
    severity: info
    disposition: open
    title: "The second reuse check runs after the restore and the NuGet check, not right after the lock (carried forward)"
  - id: IN-08
    severity: info
    disposition: open
    title: "Orphaned and unpruned translator folders (carried forward)"
  - id: IN-09
    severity: info
    disposition: open
    title: "`test_waiting_port_reuses_translator` depends on a 0.5 s window (carried forward)"
  - id: IN-10
    severity: info
    disposition: open
    title: "The link-table read is duplicated between the installer and the fixture generator"
  - id: IN-11
    severity: info
    disposition: open
    title: "The 40-hop cap is Linux's; macOS's MAXSYMLINKS is 32"
  - id: IN-12
    severity: info
    disposition: open
    title: "ARCHITECTURE.md says \"files first, links last\" for tar too"
  - id: IN-13
    severity: info
    disposition: open
    title: "Two link-escape tests are still skipped on Windows, though the rule now runs there"
  - id: IN-14
    severity: info
    disposition: open
    title: "`Remote.readinto` assumes the server returned exactly the requested range"
  - id: CR-01
    severity: critical
    disposition: fixed
    title: "Zip symlink check depends on link order; a later link turns an accepted link into an escape"
  - id: CR-02
    severity: critical
    disposition: fixed
    title: "Windows lock holder lookup reads into the locked byte; the second porter crashes, and `wait=True` never waits"
  - id: CR-03
    severity: critical
    disposition: fixed
    title: "Translator reuse check is outside the tools lock and is not repeated inside it; a waiting port rebuilds and deletes the translator another port is using"
open: 22
total: 28
recorded: 2026-10-31T02:11:41.174Z
---

# Phase 02: Code Review Disposition

| Finding | Severity | Disposition | Source |
|---------|----------|-------------|--------|
| CR-04 | critical | fixed | 02-13, a5e1836 (re-review 5aadf77: resolved) |
| WR-05 | warning | fixed | 02-13, e7a6874 (re-review 5aadf77: resolved) |
| IN-06 | info | fixed | 02-13, a5e1836 (re-review 5aadf77: resolved) |
| WR-01 | warning | open | - |
| WR-02 | warning | open | - |
| WR-03 | warning | open | - |
| WR-04 | warning | open | - |
| WR-06 | warning | open | - |
| WR-07 | warning | open | - |
| WR-08 | warning | open | - |
| WR-09 | warning | open | - |
| WR-10 | warning | open | - |
| IN-01 | info | open | - |
| IN-02 | info | open | - |
| IN-03 | info | open | - |
| IN-04 | info | open | - |
| IN-05 | info | open | - |
| IN-07 | info | open | - |
| IN-08 | info | open | - |
| IN-09 | info | open | - |
| IN-10 | info | open | - |
| IN-11 | info | open | - |
| IN-12 | info | open | - |
| IN-13 | info | open | - |
| IN-14 | info | open | - |
| CR-01 | critical | fixed | 02-11, verified in e482289 (not in the current review) |
| CR-02 | critical | fixed | 02-12, verified in e482289 (not in the current review) |
| CR-03 | critical | fixed | 02-12, verified in e482289 (not in the current review) |

Dispositions: `open` (recorded, not yet triaged), `fixed`, `skipped`, `deferred`.
Set `deferred` by hand and put the reason in the Source cell; both are preserved. A `|` in the reason is kept as prose and escaped on the next run.
Re-running the gate keeps every row it can. A row the current review no longer reports is kept and its Source cell flagged, so a finding does not leave this record silently. ONE exception: when a finding id is REUSED by a different finding, the earlier decision cannot keep a row — the id is taken — and it is dropped. A RECORDED decision (anything but `open`) is named on the console when that happens; a row still at `open` is replaced silently, because `open` records no decision to lose.
