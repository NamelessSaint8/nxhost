---
status: testing
phase: 03-host-toolchains-and-guided-first-run
source: [03-VERIFICATION.md]
started: 2026-10-31T00:00:00Z
updated: 2026-11-01T03:42:22Z
---

## Current Test

number: 3
name: Launch the bundle from Finder (macOS) and from the Add to app menu entry (Linux x64 and arm64), then port a playable title
expected: |
  Every tool found by absolute path and the port completes
awaiting: user response

## Tests

### 1. Run fork-release.yml: the bare-PATH smoke step on macOS and both Linux bundles, and 'Community NDK download and probe (linux-arm64)' on ubuntu-24.04-arm
expected: Every tool row (Android NDK, .NET SDK, adb) found by absolute path; the arm64 NDK row ok with the community note
result: pass
evidence: fork-release run 41235719427 (d132fe9)

### 2. On a real Linux arm64 host: Download all missing, then setup --json and a host build
expected: Community NDK r27c downloaded, hash-checked, probe passes, .NET 10 found or downloaded, build.py uses toolchains/llvm/prebuilt/linux-arm64
result: pass
evidence: bundle d132fe9 linux-arm64

### 3. Launch the bundle from Finder (macOS) and from the Add to app menu entry (Linux x64 and arm64), then port a playable title
expected: Every tool found by absolute path and the port completes
result: [pending]

### 4. Plug a device with USB debugging not yet allowed into the wizard's device page; on Linux without udev rules, plug one in
expected: unauthorized with its one-line fix, turning live to device after Allow; no permissions with the distro udev package command
result: [pending]

### 5. On Ubuntu 22.04 / Debian 12 with distro adb 29.0.6, install a port
expected: The adb row shows 29.0.6 and the no -Z note; the install succeeds
result: [pending]

### 6. On a slow host (SD-card arm64 board), first launch right after downloading both the NDK and .NET
expected: setup --json answers within the GUI's 150 s limit; if not, Retry answers (the probe pass was cached before the dotnet checks)
result: [pending]

### 7. Judgment-tier prohibition (03-05): the wizard links to no keys or firmware source, offers no firmware step, shows no key value
expected: Confirmed by reading the pages
result: [pending]

## Summary

total: 7
passed: 2
issues: 0
pending: 5
skipped: 0
blocked: 0

## Gaps
