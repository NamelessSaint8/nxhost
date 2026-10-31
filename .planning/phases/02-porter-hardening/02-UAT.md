---
status: testing
phase: 02-porter-hardening
source: [02-VERIFICATION.md]
started: 2026-10-31T02:21:03Z
updated: 2026-10-31T02:21:03Z
---

## Current Test

number: 1
name: Windows lock (tests.test_lock, tests.test_datapack on windows-2025)
expected: |
  Push HEAD first (main is 120 commits ahead of origin/main). On the windows-2025 job of fork-ci.yml,
  a second porter gets 'already running: porter port, PID ...' naming the holder;
  test_wait_for_holder waits instead of crashing; test_holder_read_stays_below_lock is green.
awaiting: user response

## Tests

### 1. Windows lock (tests.test_lock, tests.test_datapack on windows-2025)
expected: A second porter on Windows gets 'already running: porter port, PID ...' naming the holder; test_wait_for_holder waits instead of crashing; test_holder_read_stays_below_lock green. Needs HEAD pushed first.
result: [pending]

### 2. Windows env and toolchain swap (tests.test_porter.Env, tests.test_fetch on windows-2025)
expected: dotnet is reached by absolute path; the link rule refuses the crafted archives on Windows too (LinkRule class green); Unpack.test_failed_move_keeps_old_toolchain green, so a failed toolchain swap keeps the old toolchain.
result: [pending]

### 3. All five fork-ci jobs green (windows-2025, macos-15, ubuntu-22.04, ubuntu-24.04-arm, Python 3.11)
expected: All five jobs green; on 3.11 Unpack.test_link_loop_refused gives BuildError, not RuntimeError.
result: [pending]

### 4. Flagged prohibitions with no enforcing test (02-07, 02-08, 02-10)
expected: Accept as reviewed, or add a guard (for example an arch_rules check): every test module sets its own NX2A_HOME before importing porter; no FPSLocker-Warehouse config contents are committed; no packages.lock.json or other pin file in the nxnative subtree.
result: [pending]

### 5. Triage the open 02-13 review warnings WR-07 to WR-10 (02-REVIEW-DISPOSITION.md)
expected: Each row carries a decision (fixed, or deferred with a reason). None is an escape; WR-08 (raw traceback when a toolchain file is in use on Windows) is the most user-visible.
result: [pending]

## Summary

total: 5
passed: 0
issues: 0
pending: 5
skipped: 0
blocked: 0

## Gaps
