---
status: testing
phase: 01-bridge-bundles-and-ci
source: [01-VERIFICATION.md]
started: 2026-10-30T08:25:00Z
updated: 2026-10-30T08:25:00Z
---

## Current Test

number: 1
name: UAT test 6 again: Download missing tools from the 1ce9643 DMG opened from Finder
expected: |
  The download lists load and the missing tool downloads into the nx2android folder, with no CERTIFICATE_VERIFY_FAILED
awaiting: user response

## Tests

### 1. UAT test 6 again: Download missing tools from the 1ce9643 DMG opened from Finder (G-01-6, PKG-02)
Download the 1ce9643 DMG (fork-release run 41017737613) in a browser, open it from Finder, start the app, and press Download missing tools on the Setup tab on a Mac that lacks a tool.
expected: The download lists load and the missing tool downloads into the nx2android folder, with no CERTIFICATE_VERIFY_FAILED
result: [pending]

### 2. G-01-6 on Linux: download lists from both tarballs in fedora:44 (PKG-03, PKG-04)
In fedora:44 containers (linux/amd64 and linux/arm64), unpack the 1ce9643 linux-x64 and linux-arm64 tarballs and run `NX2A_HOME=/tmp/h ./nx2android -m porter tools --only ndk,dotnet,adb --json` (exact command in 01-10-PLAN.md Task 3 `<human-check>`).
expected: Three items and exit 0 on both (the d2ec054 arm64 bundle loaded 0 CAs on Fedora 44 and failed)
result: [pending]

### 3. G-01-7 old against new in debian:trixie as a GNOME desktop (PKG-03, PKG-04)
In debian:trixie containers with `XDG_CURRENT_DESKTOP=GNOME` and `QT_QPA_PLATFORM=xcb` under xvfb, start the d2ec054 and 1ce9643 tarballs and the folder-picker probe (exact command in 01-10-PLAN.md Task 3 `<human-check>`; the d2ec054 artifacts expire about 2026-11-05).
expected: The d2ec054 rows print the gvfs 'undefined symbol' lines (proving the container loads the gtk3 theme); the 1ce9643 rows print 'start: no GIO module errors' and "picker closed: ''"
result: [pending]

### 4. UAT test 7 again: Linux x64 bundle on the Debian-family GNOME host (G-01-7, PKG-04)
On the Debian-family x64 GNOME host where the gvfs lines first appeared, unpack the 1ce9643 linux-x64 tarball and run `QT_QPA_PLATFORM=xcb ./nx2android` from a terminal in the GNOME session, then use the Port tab's folder button.
expected: No 'undefined symbol' or 'Failed to load module' line; the folder picker (now Qt's own dialog) opens and fills in the chosen folder
result: [pending]

### 5. Linux arm64 tarball under X11 and Wayland (PKG-04, SC1)
On a Linux arm64 host (glibc 2.39+), unpack the 1ce9643 linux-arm64 tarball and start `./nx2android` with `QT_QPA_PLATFORM=xcb` and with `QT_QPA_PLATFORM=wayland`.
expected: The window appears under both with no Fontconfig, platform-plugin or GIO module errors
result: [pending]

## Summary

total: 5
passed: 0
issues: 0
pending: 5
skipped: 0
blocked: 0

## Gaps
