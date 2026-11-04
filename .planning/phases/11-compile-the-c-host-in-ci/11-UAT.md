---
status: testing
phase: 11-compile-the-c-host-in-ci
source: [11-01-SUMMARY.md, 11-02-SUMMARY.md, 11-03-SUMMARY.md, 11-04-SUMMARY.md]
started: "2026-11-04T11:50:00Z"
updated: "2026-11-04T11:50:00Z"
---

## Current Test

number: 1
name: Both CI host-compile jobs run green on a code push
expected: |
  A push touching `nxnative/**` or `.github/**` starts both `host-apple` (macos-26)
  and `host-android` (ubuntu-22.04) from `.github/workflows/host-build.yml`, and both
  finish green. A docs-only push starts neither, while `fork-ci.yml` still runs its
  four-host Python suite.
awaiting: user response

## Tests

### 1. Both CI host-compile jobs run green on a code push
expected: A push touching `nxnative/**` or `.github/**` starts both `host-apple` and `host-android`, and both finish green; a docs-only push starts neither while `fork-ci.yml` still runs.
result: pending

### 2. Branch protection makes the two jobs actually blocking
expected: `host-apple` and `host-android` are listed as required status checks on `main`, so a PR touching `nxnative/**` cannot merge while either is red.
result: blocked
blocked_by: third-party
reason: repository settings live in GitHub, not in the tree — this is the plan's declared `user_setup`

### 3. The prefixed step line wraps at 980 px
expected: With both targets ticked and a long step, the step line above the progress bar wraps inside a 980 px window instead of widening it.
result: pending

### 4. A prefixed stage name stays readable at 980 px
expected: `Mac app · <long stage name>` in the `ResizeToContents` Stage column remains readable at 980 px with both chains listed.
result: pending

### 5. A long porter reason wraps at 980 px
expected: A ~300-character porter `reason` on a failed/skipped result row wraps to two or three lines and does not widen the window.
result: pending

### 6. Partial success reads correctly beside a working package
expected: A run where Android built and the Mac app failed exits 1, shows two result rows (`Android APK · built`, `Mac app · failed` with the reason), keeps the bar at 1000, and the status line reads `finished in <took>: the Mac app failed` — the wording is the desired one.
result: pending

## Summary

total: 6
passed: 0
issues: 0
pending: 5
skipped: 0
blocked: 1

## Gaps
