---
phase: 03
review: 03-REVIEW.md
titles: json
findings:
  - id: WR-01
    severity: warning
    disposition: open
    title: "A re-check while the device page is open resets Next to \"Skip: install later\" even when a device is ready"
  - id: WR-02
    severity: warning
    disposition: open
    title: "The 150 s `setup` limit ignores dotnet's own 60 s limits; the test and the docs repeat the incomplete bound"
  - id: IN-01
    severity: info
    disposition: open
    title: "The device combo's tooltip still says \"porter\""
  - id: IN-02
    severity: info
    disposition: open
    title: "The Setup tab's download-failure line still uses a hardcoded `#c62828`"
  - id: IN-03
    severity: info
    disposition: open
    title: "A config value with leading or trailing whitespace counts as \"typed\" forever and is saved stripped"
  - id: CR-01
    severity: critical
    disposition: fixed
    title: "The Setup tab's \"Save and check\" overwrites settings the wizard just saved"
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
open: 5
total: 15
recorded: 2026-10-31T19:24:32.168Z
---

# Phase 03: Code Review Disposition

| Finding | Severity | Disposition | Source |
|---------|----------|-------------|--------|
| WR-01 | warning | open | - |
| WR-02 | warning | open | - |
| IN-01 | info | open | - |
| IN-02 | info | open | - |
| IN-03 | info | open | - |
| CR-01 | critical | fixed | 03-15 Task 1 (not in the current review) |
| WR-03 | warning | fixed | porter half 03-13 Task 3 (per-process temp file, best-effort write); GUI half 03-15 Task 2 (one setup --json at a time) (not in the current review) |
| WR-04 | warning | fixed | 03-15 Task 2 (also implements T-03-35's open mitigation) (not in the current review) |
| WR-05 | warning | fixed | 03-14 Task 1 (not in the current review) |
| WR-06 | warning | fixed | 03-13 Task 3 (not in the current review) |
| IN-04 | info | deferred | devtools/ndk_pin.py is a release-time script touched by no gap task; fix before the next community NDK pin bump (not in the current review) |
| IN-05 | info | deferred | porter/cli.py is upstream's busy file (hook lines only) and the GUI always sends the guarded `config legal … --json`; a quick task (not in the current review) |
| IN-06 | info | deferred | naming the `.part` after the pinned hash changes the resume key D-22 defines and discards testers' existing parts on upgrade; today it costs one misleading message after a rare in-place re-upload, and the next press works; revisit with the next community NDK pin bump (not in the current review) |
| IN-07 | info | deferred | no behaviour change; renaming `fetch._pinned` touches porter/setup.py, porter/fetch.py and the tests that patch it; a quick task (not in the current review) |
| IN-08 | info | deferred | nxnative/dm/android/build.py is touched by no gap task; it belongs with Phase 6's on-device parity work (VER-02) (not in the current review) |

Dispositions: `open` (recorded, not yet triaged), `fixed`, `skipped`, `deferred`.
Set `deferred` by hand and put the reason in the Source cell; both are preserved. A `|` in the reason is kept as prose and escaped on the next run.
Re-running the gate keeps every row it can. A row the current review no longer reports is kept and its Source cell flagged, so a finding does not leave this record silently. ONE exception: when a finding id is REUSED by a different finding, the earlier decision cannot keep a row — the id is taken — and it is dropped. A RECORDED decision (anything but `open`) is named on the console when that happens; a row still at `open` is replaced silently, because `open` records no decision to lose.
