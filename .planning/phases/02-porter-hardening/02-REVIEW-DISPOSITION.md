---
phase: 02
review: 02-REVIEW.md
titles: json
findings:
  - id: CR-01
    severity: critical
    disposition: open
    title: "Zip symlink check depends on link order; a later link turns an accepted link into an escape"
  - id: CR-02
    severity: critical
    disposition: open
    title: "Windows lock holder lookup reads into the locked byte; the second porter crashes, and `wait=True` never waits"
  - id: CR-03
    severity: critical
    disposition: open
    title: "Translator reuse check is outside the tools lock and is not repeated inside it; a waiting port rebuilds and deletes the translator another port is using"
  - id: WR-01
    severity: warning
    disposition: open
    title: "`porter install` recovers the pack before taking the port's lock"
  - id: WR-02
    severity: warning
    disposition: open
    title: "The tools lock is held for a whole survey, not just the nx_extract build"
  - id: WR-03
    severity: warning
    disposition: open
    title: "The signing key is published only through `os.link`; a folder without hard links can never get a key"
  - id: WR-04
    severity: warning
    disposition: open
    title: "Linux arm64 gets the x86-64 NDK and platform-tools as \"pinned\", not flagged untested"
  - id: WR-05
    severity: warning
    disposition: open
    title: "Replacing an existing toolchain is not atomic; a failed replace leaves a half-deleted NDK/.NET"
  - id: WR-06
    severity: warning
    disposition: open
    title: "Moving the old data pack aside has no Windows retry, unlike `swap_in`"
  - id: IN-01
    severity: info
    disposition: open
    title: "The status badge text is the one game-card string left unescaped"
  - id: IN-02
    severity: info
    disposition: open
    title: "A failed inspect keeps the previous game's language list"
  - id: IN-03
    severity: info
    disposition: open
    title: "The NuGet check assumes the first package folder"
  - id: IN-04
    severity: info
    disposition: open
    title: "Two game folders of the same title, sharing one output folder, race on the pack's `.partial`"
  - id: IN-05
    severity: info
    disposition: open
    title: "Stale reference to the deleted probe packer"
open: 14
total: 14
recorded: 2026-10-30T18:56:16.251Z
---

# Phase 02: Code Review Disposition

| Finding | Severity | Disposition | Source |
|---------|----------|-------------|--------|
| CR-01 | critical | open | - |
| CR-02 | critical | open | - |
| CR-03 | critical | open | - |
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

Dispositions: `open` (recorded, not yet triaged), `fixed`, `skipped`, `deferred`.
Set `deferred` by hand and put the reason in the Source cell; both are preserved. A `|` in the reason is kept as prose and escaped on the next run.
Re-running the gate keeps every row it can. A row the current review no longer reports is kept and its Source cell flagged, so a finding does not leave this record silently. ONE exception: when a finding id is REUSED by a different finding, the earlier decision cannot keep a row — the id is taken — and it is dropped. A RECORDED decision (anything but `open`) is named on the console when that happens; a row still at `open` is replaced silently, because `open` records no decision to lose.
