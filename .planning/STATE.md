---
gsd_state_version: "1.0"
current_phase: 03
current_phase_name: Host Toolchains and Guided First Run
status: executing
stopped_at: Completed 03-08-PLAN.md
last_updated: "2026-10-31T16:34:20.285Z"
last_activity: 2026-10-31
last_activity_desc: Phase 03 execution started
state_head: d7b76d7748b6c052225b93c896775702a9431b71
progress:
  total_phases: 6
  completed_phases: 2
  total_plans: 35
  completed_plans: 31
  percent: 33
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-10-31)

**Core value:** A tester on any supported host (Windows x64, macOS Apple Silicon, Linux x64, Linux arm64) can take their own Switch dump and get a working port onto their Android device through the GUI, without help.
**Current focus:** Phase 03 — Host Toolchains and Guided First Run

## Current Position

Phase: 03 (Host Toolchains and Guided First Run) — EXECUTING
Plan: 9 of 12
Status: Ready to execute
Last activity: 2026-10-31 — Phase 03 execution started

Progress: [███░░░░░░░] 33%

## Performance Metrics

**Velocity:**
- Total plans completed: 23
- Average duration: -
- Total execution time: 0.0 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01 | 10 | - | - |
| 02 | 13 | - | - |

**Recent Trend:**
- Last 5 plans: -
- Trend: -

*Updated after each plan completion*
**Per-Plan Metrics:**

| Plan | Duration | Tasks | Files |
|------|----------|-------|-------|
| Phase 01 P01 | resumed | 3 tasks | 8 files |
| Phase 01 P05 | 3 min | 2 tasks | 3 files |
| Phase 01 P02 | 7 min | 3 tasks | 6 files |
| Phase 01 P06 | 9 min | 3 tasks | 9 files |
| Phase 01 P03 | 10min | 3 tasks | 5 files |
| Phase 01 P04 | 11min | 3 tasks | 11 files |
| Phase 01 P07 | 2 fix rounds | 3 tasks | 12 files |
| Phase 01 P08 | 3 sessions | 3 tasks | 7 files |
| Phase 01 P09 | 2min | 2 tasks | 5 files |
| Phase 01 P10 | 77min | 3 tasks | 4 files |
| Phase 02 P01 | 10 min | 2 tasks | 8 files |
| Phase 02 P02 | 4 min | 3 tasks | 8 files |
| Phase 02 P03 | 7 min | 3 tasks | 8 files |
| Phase 02 P04 | 8 min | 3 tasks | 12 files |
| Phase 02 P05 | 4 min | 3 tasks | 4 files |
| Phase 02 P06 | 5 min | 3 tasks | 6 files |
| Phase 02 P07 | 5 min | 3 tasks | 4 files |
| Phase 02 P08 | 3 min | 2 tasks | 5 files |
| Phase 02 P09 | 4 min | 2 tasks | 4 files |
| Phase 02 P10 | 8 min | 3 tasks | 9 files |
| Phase 02 P11 | 2 min | 2 tasks | 3 files |
| Phase 02 P12 | 4 min | 3 tasks | 4 files |
| Phase 02 P13 | 7 min | 3 tasks | 6 files |
| Phase 03 P01 | 8 min | 3 tasks | 10 files |
| Phase 03 P02 | 15min | 3 tasks | 6 files |
| Phase 03 P03 | 8 min | 3 tasks | 6 files |
| Phase 03 P04 | 8min | 3 tasks | 11 files |
| Phase 03 P05 | 8min | 2 tasks | 10 files |
| Phase 03 P06 | 4 min | 2 tasks | 6 files |
| Phase 03 P07 | 3 min | 2 tasks | 4 files |
| Phase 03 P08 | 25min | 3 tasks | 7 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [Roadmap]: PySide6 6.12 on every host (Linux arm64 tester on glibc 2.39+, macOS testers on 14+), so no PySide6 6.8 fallback or per-arch lock
- [Roadmap]: BRDG-01 is whole in Phase 1, including the Windows Job Object and MSBuild node-reuse env that research had put in Phase 2
- [Roadmap]: GUI features are vertical slices (porter JSON command + view per phase); the new shell starts in Phase 3 beside `gui/app.py` and becomes the default in Phase 6
- [Roadmap]: DEV-06 (launch on device) and DEV-07 (logcat) stay in v1 per REQUIREMENTS.md, although research listed them as v1.x
- [Phase 01]: Runtime, build and dev deps each get their own .in and hashed uv lock; build/dev locks constrained by requirements.txt
- [Phase 01]: 01-05: frozen porter builds from <user dir>/engine/<ENGINE id>/nxnative; a missing or non-alphanumeric ENGINE id falls back to the bundle's own nxnative
- [Phase 01]: 01-05: other engine versions are pruned only by the start that installs a copy
- [Phase 01]: 01-02: runlog prints its own log and error events, so a failed porter.upstream import still names its log
- [Phase 01]: 01-02: the cut-off key sweep prunes the top-level extract/ folder and never walks the extracted RomFS
- [Phase 01]: 01-02: LOGS_KEPT = 30 counts the new log (29 old ones stay)
- [Phase 01]: 01-06: CFBundleShortVersionString is the dotted numeric prefix of the fork tag (0.1.2 of 0.1.2-ns.1), 0.0.0 for hash builds
- [Phase 01]: 01-06: build_bootloader.py is required on Windows only; macOS and Linux bundles use PyInstaller's own bootloader
- [Phase 01]: 01-06: smoke_gui.py runs from the checkout through the frozen exe, so the bundle is not changed for the smoke test
- [Phase 01]: Porter._kill never signals a pgid <= 1; stop() before started falls back to QProcess.kill
- [Phase 01]: A stopped run ending by signal (CrashExit) reports 130 even with exit code 0; unstopped CrashExit with code 0 reports -1
- [Phase 01]: Failed downloads show their escaped cause and an Open log link inline; 130 shows cancelled
- [Phase 01]: test_bridge sets NX2A_HOME in setUpModule because test_porter sets its own at import
- [Phase 01]: 01-04: one-shot calls report done(obj, code, fail); the exit code alone is no failure (inspect exits 2 for an unportable game)
- [Phase 01]: 01-04: a one-shot whose owner is destroyed mid-call calls nothing and kills its own session (shiboken6.isValid guard)
- [Phase 01]: 01-04: port_build_error.jsonl records a port of a missing folder (machine-independent, names the folder); fake_porter --hang makes a one-shot hang
- [Phase 01]: The GUI needs Python 3.12+ (PySide6 6.12 drops a ref on True per signal emit, aborting 3.11); the CLI keeps 3.11+. Supersedes the GUI part of 'Python 3.11+ for dev runs'
- [Phase 01]: test_bridge skips on Python < 3.12 in CI too: a declared version floor, a deliberate exception to TEST-02's fail-in-CI rule
- [Phase 01]: Linux x64 floor is glibc 2.35 (PKG-03), not 2.34: the ubuntu-22.04 runner's libpython, libgcc_s, cairo, tcl and tk need it; user chose this over a container build or trimming (supersedes RESEARCH Open Question 4)
- [Phase 01]: fork-release retries stapler staple up to 4 times; notarization itself is not retried
- [Phase 01]: TLS trust: porter/tls.py context() loads the first host CA file only when the default store holds no CA; no truststore, no process-wide SSL_CERT_FILE
- [Phase 01]: G-01-7 fixed by what ships: packaging/hooks overrides drop PySide6's gtk3 theme and glib network plugin, the spec refuses libgio-2.0/libgtk-3; no GIO or Qt theme env var
- [Phase 02]: Build-folder lock: porter/lock.py OS lock on <tid>_build/.porter.lock; install finds the folder via the host-only sidecar <App>-data.build (D-14)
- [Phase 02]: Data pack swapped aside via <App>-data.old; datapack.recover runs first in build and porter install (HARD-07)
- [Phase 02]: Signing key published with os.link (no-clobber), not os.replace: two simultaneous first ports end with one signer
- [Phase 02]: An unreadable signing key is a required red doctor row, so porter port stops before any stage; mkapk.py never replaces it
- [Phase 02]: Existing group/other-readable signing key tightened to 0600 on POSIX on next use
- [Phase 02]: arch_rules join_literals joins a literal and the run after it, pairing left to right as rule 1 blanking does
- [Phase 02]: Ryujinx base is Ryubing Canary-1.3.351 (475615f) plus nxnative-local.patch (paths relative to ryujinx/, apply with --directory); the unmarked hunks are the fixed-input geometry path
- [Phase 02]: Toolchain downloads pinned in porter/pins.py (NDK r27c, platform-tools 37.0.1, .NET SDK 10.0.403); vendor-newest fallback only on 404/410, marked untested; NDK never falls back
- [Phase 02]: Archive member-name check applies to tar too (filter='data' alone strips a leading / and extracts)
- [Phase 02]: runlog.run refuses every command but doctor on a Python without the CVE-2025-4517 fix (floors or os.path.ALLOW_MISSING), error type PythonError
- [Phase 02]: HARD-06: a port never writes os.environ; every child gets self.env with an absolute dotnet and DOTNET_ROOT, profiles load by path
- [Phase 02]: HARD-09/D-15: disk check counts the scanned base, updates and DLC plus the build folder recursively, and re-checks after extraction (output volume too)
- [Phase 02]: Upstream overrides live in porter/upstream.py _overrides and raise AssertionError naming the attribute at import
- [Phase 02]: HARD-05/D-08: every reuse key is written last and whole through write_whole (temp file + os.replace) after its outputs are swapped in; the experimental profile copy goes through <id>.partial + swap_in
- [Phase 02]: D-09: the .port-running marker names the stage (rewritten at each stage start) and keeps every reuse key; the Phase 1 key sweep and its extract/ exemption are gone
- [Phase 02]: 02-07: an unknown porter tools --only name is a usage error: named message, exit 2
- [Phase 02]: 02-07: per-OS detection tests swap the module's os/sys for stand-ins instead of patching os.name (pathlib would build WindowsPath on POSIX)
- [Phase 02]: HARD-03/D-03: FPSLocker configs come from pins.FPSLOCKER; a 404 there falls back to v4 head, logged [RED] untested
- [Phase 02]: A pre-pin FPSLocker cache is used offline as commit unknown and flagged untested
- [Phase 02]: inspect reads language flags only from an extraction a port made (packed version first); none gives all 16 nacp.LANGUAGES
- [Phase 02]: GUI language box: 'English (default)' plus porter inspect's languages; the chosen code survives a re-inspect
- [Phase 02]: NuGet packages are pinned by content hash (obj/project.assets.json sha512) in pins.NUGET, generated by devtools/nuget_pins.py; every NuGet-backed build runs inside nuget.restored()
- [Phase 02]: Shared tool builds (restore, check, nx_extract build, translator .partial/build/swap) hold <user dir>/tools/.porter.lock with wait=True
- [Phase 02]: Zip links are checked in two passes: folder check as each link is made, then every link resolved once all exist (CR-01, order-independent)
- [Phase 02]: 02-12: each shader-translator key builds into <user dir>/tools/dmsh_xlate-<key[:12]>, chosen over holding the tools lock around the shaders stage (deadlocks on POSIX flock); reuse is re-checked inside the lock; the lock file is opened unbuffered so the holder read stays below the Windows-locked byte
- [Phase 02]: 02-13: links resolved in memory from the installed folder (_top), one rule for check and install (CR-04)
- [Phase 02]: 02-13: link resolution capped at 40 substitutions so loops are a BuildError on every Python (IN-06)
- [Phase 02]: 02-13: link names/targets must be printable ASCII; case-variant, duplicate and member-under-link refused (APFS)
- [Phase 02]: 02-13: installed toolchain renamed to .<folder>.old and restored on failure or cut-off swap (WR-05)
- [Phase 03]: setup --json is the readiness document; legal notice VERSION=1 accepted only via config legal <VERSION> --json
- [Phase 03]: prod.keys judged by key names and highest generation (master_key_XX or titlekek+key_area_key_application pair); values never leave porter
- [Phase 03]: desktop Exec quoting follows the spec exactly (literal backslash = four); paths with line breaks refused
- [Phase 03]: find_dotnet dedupes candidates by resolved path, keeping the earliest spelling (Homebrew's dotnet link asked once)
- [Phase 03]: hosttools.source_of falls back to 'known place' for LOCAL_TOOLS and find_dotnet's other fixed folders
- [Phase 03]: childenv.dotnet is the one env builder for dotnet children; Port.run uses it and Prepare (03-09) must too
- [Phase 03]: 03-03: a 206 for another offset discards the .part and re-requests without Range; only a 206 whose Content-Range starts at the part size is appended
- [Phase 03]: 03-03: rate (bytes/s) is added to unit-B progress events in runlog._wrap from upstream's eta, never in the engine subtree
- [Phase 03]: NDK rows are green only after a compile probe links an aarch64-linux-android29 program; only passes are cached in probe.json
- [Phase 03]: build.py copies probe.host_folder's arm64 rule, held equal by a source-text test
- [Phase 03]: require() returns every passing row's note and Port.run says each in the port log (community NDK, adb without -Z)
- [Phase 03]: TOOL-03 stays pending until 03-06 adds the udev fix
- [Phase 03]: 03-05: the wizard reaches a later start page by walking next() from the legal page, so QWizard's Back still reaches earlier steps (D-04)
- [Phase 03]: 03-05: every exit from the wizard goes through done(), which clears the gate and deletes it; Run/Continue setup with no setup answer asks porter again
- [Phase 03]: devices() reads the lines after the List of devices attached header, so a daemon notice on stdout cannot shift the header into the rows
- [Phase 03]: devices --json fix text comes only from porter literals chosen by state kind and os-release family; the plugdev user name from adb is never copied (T-03-21)
- [Phase 03]: Push -Z is gated per Adb by a cached hosttools.push_flags: one adb version, asked only when pushing
- [Phase 03]: gui/shell.py is a second window on gui/firstrun.py's protocol (fetch, recheck, set_ready); it imports nothing from gui/app.py and has no port_a_game in Phase 3
- [Phase 03]: tests/arch_rules.py 5b keeps gui/firstrun.py and gui/shell.py pure views: stdlib, PySide6 and gui.runner (+ gui.firstrun) only, no open(/write_text(/write_bytes(/QSettings; rule 6 reads hyphenated subcommands and call_json(<owner>, [...]) calls
- [Phase 03]: smoke_bundle.py bare_env_check runs frozen in fork-release and unfrozen in the suite; a missing tool row fails naming it (D-19)
- [Phase 03]: The linux-arm64 release job downloads the community NDK through the frozen bundle and requires an ok NDK row with the community note (TOOL-01)
- [Phase 03]: The D-10 fallback NDK recipe uses a bin/clang wrapper passing -resource-dir and --sysroot in a linux-arm64 host folder, documented only

### Pending Todos

None yet.

### Blockers/Concerns

- [Phase 1]: packaging/nx2android.spec refuses any PyInstaller but 6.22.3 (WR-03 fix): after recompiling requirements-build.txt to a newer 6.22.x, copy the stock QtGui/QtNetwork hooks into packaging/hooks/ again, keep the filter lines, then bump the version in the spec
- [Phase 1]: A root CA that exists only in the macOS keychain (TLS-inspecting proxy) is not trusted; the player can set SSL_CERT_FILE. Read the keychain (truststore) when a tester needs it
- [Phase 2]: Research: whether older platform-tools URLs stay downloadable after pinning
- [Phase 3]: Research: HomuHomu833 arm64 NDK (asset re-uploaded in place, so the pinned hash can drift; clang build parity with r27c; its glibc), minimum distro adb and when `push -Z` arrived (Debian 12 ships 29.0.6)
- [Phase 5]: Research: confirm `feature:android.hardware.vulkan.version` on the Y700 via `pm list features`, and `pm list packages --show-versioncode` reliability
- Upstream sync: merge shirai91/nx2android weekly (never rebase); keep edits to `pipeline.py`, `cli.py`, `gui/app.py` to hook lines

## Deferred Items

Items acknowledged and deferred at milestone close, most recent first:

| Category | Item | Status | Deferred At | Milestone |
|----------|------|--------|-------------|-----------|
| *(none)* | | | | |

## Session Continuity

Last session: 2026-10-31T16:34:20.049Z
Stopped at: Completed 03-08-PLAN.md
Resume file: None
