---
status: testing
phase: 11-compile-the-c-host-in-ci
source: [11-01-SUMMARY.md, 11-02-SUMMARY.md, 11-03-SUMMARY.md, 11-04-SUMMARY.md]
started: "2026-11-04T11:50:00Z"
updated: "2026-11-04T17:25:00Z"
---

## Current Test

number: 1
name: Both CI host-compile jobs run green on a code push
expected: |
  A push touching `nxnative/**` or `.github/**` starts both `host-apple` (macos-26)
  and `host-android` (ubuntu-22.04) from `.github/workflows/host-build.yml`, and both
  finish green. A docs-only push starts neither, while `fork-ci.yml` still runs its
  four-host Python suite.
awaiting: user response — this needs a push to origin

## Tests

### 1. Both CI host-compile jobs run green on a code push
expected: A push touching `nxnative/**` or `.github/**` starts both `host-apple` and `host-android`, and both finish green; a docs-only push starts neither while `fork-ci.yml` still runs.
result: pending
evidence: pushed 23815667 to NamelessSaint8/nx2android; host-build run 41878713095 and fork-ci run 41878712610 both triggered on that SHA. At the time of writing both jobs are queued. A previous head (d132fe9e) already had a red fork-ci, so ours must be checked against that, not assumed.

### 2. Branch protection makes the two jobs actually blocking
expected: `host-apple` and `host-android` are listed as required status checks on `main`, so a PR touching `nxnative/**` cannot merge while either is red.
result: pass
evidence: `gh api repos/NamelessSaint8/nx2android/branches/main/protection` now returns contexts ["host-apple","host-android"], strict false, enforce_admins false — required for PRs, admin (this account) can still push straight to main.

### 3. The prefixed step line wraps at 980 px
expected: With both targets ticked and a long step, the step line above the progress bar wraps inside a 980 px window instead of widening it.
result: pass
evidence: probe_both.py — label 940x30 px, 2 lines, window stays 980 px.

### 4. A prefixed stage name stays readable at 980 px
expected: `Mac app · <long stage name>` in the `ResizeToContents` Stage column remains readable at 980 px with both chains listed.
result: pass
evidence: probe_both.py — Stage column 180 px of 940 px, with both chains' six stage rows present and not overwriting each other.

### 5. A long porter reason wraps at 980 px
expected: A ~300-character porter `reason` on a failed/skipped result row wraps to two or three lines and does not widen the window.
result: pass
evidence: probe_both.py — reason label 940x45 px, 3 lines; result block 940 px, window unchanged at 980 px.

### 6. Partial success reads correctly beside a working package
expected: A run where Android built and the Mac app failed exits 1, shows two result rows (`Android APK · built`, `Mac app · failed` with the reason), keeps the bar at 1000, and the status line reads `finished in <took>: the Mac app failed` — the wording is the desired one.
result: pass
evidence: probe_both.py — two rows, bar at 1000, status line `finished in 0:12: the Mac app failed`, matching UI-SPEC rule 22. Change the wording only if that sentence reads wrong to you.

## Summary

total: 6
passed: 5
issues: 0
pending: 1
skipped: 0
blocked: 0

## Gaps
