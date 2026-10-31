---
phase: "3"
slug: "host-toolchains-and-guided-first-run"
status: verified
# threats_open = count of OPEN threats at or above workflow.security_block_on severity (the blocking gate)
threats_open: 0
asvs_level: 1
created: "2026-10-31"
---

# Phase 3 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| player's prod.keys file → porter | an untrusted text file parsed for key names | key names and hex lengths only; values dropped while parsing |
| bundle path → `.desktop` Exec line | the folder the player unpacked the bundle into ends up in a line the desktop executes | a filesystem path |
| porter → XDG applications folder | a write into a folder another program may have made a symlink | the menu entry and icon |
| GUI → porter command line / `porter config` | paths and values the GUI passes as argv are written to config.json | prod.keys, NDK, .NET and adb paths; the legal notice version; the device serial |
| known places on disk → porter | executables in system and user folders porter runs (`--list-sdks`, `version`) | tool output |
| porter → child processes | the env dict every dotnet and engine child inherits | environment variables |
| GitHub release asset (single maintainer) → porter | the community NDK archive, reached through a redirect | a 128 MB archive, sha256-pinned |
| HTTP server → `.part` file | resumed bytes appended to what is on disk | partial archive bytes |
| downloaded archive → player's disk | member names and links | tar members |
| NDK binaries (pinned download or the player's folder) → porter | clang is executed by the probe on every check | compiler output |
| probe.json → porter | a cache file in the player's folder | probe pass records |
| /etc/os-release → fix text | distro-controlled strings used to pick a command | distro ids |
| adb's stdout → porter → GUI | device lines from a USB device and the adb daemon | serials, models, state text |
| porter fix text → the player's terminal / clipboard | commands the player may copy and run | porter's own literal commands |
| porter's JSON and event stream → Qt labels | strings rendered in widgets | paths, details, notice, link URLs, error text, hashes |
| shell → child porter runs | the download / Prepare run the window owns | process lifetime |
| nuget.org → `<user dir>/nuget`; player's dotnet → Prepare | packages restored by Prepare and the SDK that builds | NuGet packages checked against pins.NUGET |
| CI runner → the community NDK asset; GitHub API → devtools/ndk_pin.py | an unattended download on a release runner; release metadata read before a release | archive bytes, asset size and digest |

---

## Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-03-01 | Information disclosure | keys.check / setup --json | high | mitigate | porter/keys.py:21 keeps only key name and hex length; :28, :50 return no values; tests/test_keys.py:55 `test_no_values_out` | closed |
| T-03-02 | Denial of service | keys.check on a huge or binary file | low | mitigate | keys.py:8 `MAX_BYTES` 1 MB checked before read (:18-19); test_keys.py:48 `test_too_big` | closed |
| T-03-03 | Elevation of privilege | desktop.entry Exec quoting | medium | mitigate | porter/desktop.py:21-22 `_exec` escaping, :27 refuses line breaks, :28 TryExec; tests/test_desktop.py:27 `test_quoting` | closed |
| T-03-04 | Tampering | desktop.install symlink target | medium | mitigate | desktop.py:48 refuses symlinked target or folder; :36-42 mkstemp + `os.replace`; test_desktop.py:48 `test_symlink_refused` | closed |
| T-03-05 | Tampering / Repudiation | config legal | low | mitigate | porter/cli.py:189 accepts only `setup.VERSION`; setup.py:39 reads accepted only on equality; test_setup.py:128 `test_legal_round_trip` | closed |
| T-03-06 | Elevation of privilege | hosttools.known / find_* | medium | mitigate | porter/hosttools.py:9-15 fixed folders; toolchain.py:72, :89 D-13 order; argv lists with timeouts, no shell; test_hosttools.py:43, :69 `BarePath` | closed |
| T-03-07 | Tampering | childenv env dict | low | mitigate | porter/childenv.py:10 works on a copy of `os.environ`; test_hosttools.py:107, test_porter.py:139 | closed |
| T-03-08 | Information disclosure | tool source labels in output | low | accept | see Accepted Risks Log AR-03-01 | closed |
| T-03-09 | Tampering | community NDK asset replaced | high | mitigate | porter/pins.py:14-15 sha256 pin; fetch.py:123-127 whole-file re-hash on resume, :147-150 stop naming both hashes, :108 no fallback; test_fetch.py:113, :125, :130 | closed |
| T-03-10 | Tampering | resume splicing | high | mitigate | fetch.py:132 appends only on 206 with `Content-Range: bytes <have>-`; :133-134 restart otherwise; :147 final hash; test_fetch.py:217-229 | closed |
| T-03-11 | Tampering | MITM on the redirect target | medium | mitigate | fetch.py:41, :45, :130 `tls.context()`; porter/tls.py:19-26 always verifies; tests/test_tls.py:47 AST check of every urlopen | closed |
| T-03-12 | Tampering / Elevation | hostile tarball members | high | mitigate | fetch.py:221-230 `_refuse_names`, `_link_refusal`, `extractall(filter='data')`; runlog.py:146 refuses on a Python without the CVE-2025-4517 fix; test_fetch.py:377 + `LinkRule` | closed |
| T-03-13 | Denial of service | stale .part cleanup | low | mitigate | fetch.py:256-258 deletes only top-level `*.part` not named after this run's archives; test_fetch.py:247 | closed |
| T-03-14 | Elevation of privilege | probe running clang | medium | mitigate | porter/probe.py:37 runs only find_ndk's clang; :43, :47 argv with 60 s timeout, cwd a TemporaryDirectory; test_probe.py:63 `test_timeout` | closed |
| T-03-15 | Tampering | probe.json poisoning | low | mitigate | probe.py:39-40 key by resolved path, mtime_ns, size; :57-58 cache passes only; :29-32 ignore corrupt; test_probe.py:72, :83 | closed |
| T-03-16 | Tampering | os-release values in fix text | low | mitigate | porter/distro.py:18-20 lookup only; :7-9 literal commands; no subprocess import; test_distro.py:24 `test_runs_nothing` | closed |
| T-03-17 | Spoofing / Tampering | wizard rich text | medium | mitigate | gui/firstrun.py:79, :108-109 PlainText; :174-176 `html.escape(quote=True)` on links; `failed()` escapes; `Banner.test_plain_text`, `Legal.test_text_and_links` | closed |
| T-03-18 | Information disclosure | key material in the GUI | high | mitigate | firstrun.py:215-220, :241-248 use only path, ok, detail, fix; arch_rules.py:117-120 forbids file reads/writes in the views; test_firstrun.py:317 `Keys.test_no_values` | closed |
| T-03-19 | Tampering | argv injection via a picked path | low | mitigate | firstrun.py:269 argv list via QProcess (runner.py:31), absolute paths only; porter re-checks on next setup --json | closed |
| T-03-20 | Spoofing | device-named text | low | mitigate | porter/adb.py:22 anchored ROW regex, :70-77 fields; GUI side plain text (T-03-31) | closed |
| T-03-21 | Elevation of privilege | copied sudo fix text | medium | mitigate | distro.py:37-44 picks literals by state kind and distro family only; no device text in commands; `DeviceFix` tests | closed |
| T-03-22 | Denial of service | stalled `adb devices` | low | accept | see Accepted Risks Log AR-03-02 | closed |
| T-03-23 | Denial of service | shell close orphaning a download tree | medium | mitigate | gui/shell.py:54-71 refuse close, ask, stop each run, close after finished; runner.py:71-116 session kill; test_shell.py:127 `Close` | closed |
| T-03-24 | Spoofing | shell markup | low | mitigate | shell.py:27 `fill_checks` plain items; :44 `firstrun.failed` escaped | closed |
| T-03-25 | Tampering | community NDK in the release job | medium | mitigate | fork-release.yml:12-13 `contents: read`; :60-62 runs the pinned download through porter; test_workflows.py:117, :127 | closed |
| T-03-26 | Tampering | workflow script injection | low | mitigate | fork-release.yml:62 takes no expression; test_workflows.py:74 | closed |
| T-03-27 | Spoofing | ndk_pin.py trusting the API | low | accept | see Accepted Risks Log AR-03-03 | closed |
| T-03-28 | Tampering | NuGet packages restored by Prepare | high | mitigate | porter/prepare.py:23, :26 inside `nuget.restored`; nuget.py:19-41 checks every package against pins.NUGET before building; test_prepare.py:41, :51 | closed |
| T-03-29 | Denial of service | Prepare racing a port | low | mitigate | nuget.py:36 `lock.take(... 'tool build', wait=True)` | closed |
| T-03-30 | Information disclosure | setup --json tool paths | low | accept | see Accepted Risks Log AR-03-04 | closed |
| T-03-31 | Spoofing | device model or serial as markup | low | mitigate | firstrun.py:411-419 `body()` PlainText; :451 errors in plain labels | closed |
| T-03-32 | Denial of service | device polls piling up | medium | mitigate | firstrun.py:441-449 busy flag + generation, next poll from each answer, :435-439 stop on leave; `Device.test_no_stacking` | closed |
| T-03-33 | Tampering | menu entry without consent | low | mitigate | firstrun.py:498, :518-523 only on press and only when offered; setup.py:49 frozen Linux only; desktop.py:59 refuses elsewhere | closed |
| T-03-34 | Spoofing | error and say text as markup | medium | mitigate | firstrun.py:276, :356-357, :394-399 PlainText / `html.escape`; app.py:302-309, :334-336 escape; `Tools.test_failure_inline`, `test_download_failure_inline` | closed |
| T-03-35 | Denial of service | cancelled download leaving children behind | medium | mitigate | Cancel goes through `Porter.stop` (firstrun.py:371, app.py:296) and `Tools.test_cancel` passes, but gui/app.py:300-313 `confirm_download` starts `self.fetch` without checking `running()`, and `Porter.start` (runner.py:53-60) replaces the tracked process; a second start leaves the first run (and a Prepare run's dotnet children) untracked by Cancel and the close guard (app.py:407-427). Fix: `if self.fetch.running(): return` at the top of `confirm_download`, or the same guard in `Porter.start` | open — below high threshold (non-blocking) |
| T-03-36 | Tampering | Copy command clipboard | low | mitigate | firstrun.py:325 copies only `it['command']`, a distro.py literal (setup.py:31) | closed |
| T-03-SC | Tampering | npm / pip / cargo installs (all 12 plans) | low | accept | see Accepted Risks Log AR-03-05 | closed |

*Status: open · closed · open — below high threshold (non-blocking)*
*Severity: critical > high > medium > low — only open threats at or above workflow.security_block_on count toward threats_open*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-03-01 | T-03-08 | hosttools.py:47-57 returns fixed source labels for the player's own tool paths, shown only to that player and in their own logs | plan 03-02 threat model; confirmed by gsd-security-auditor | 2026-10-31 |
| AR-03-02 | T-03-22 | a stalled `adb devices` is bounded: adb.py:72 timeout=30 s, runner.py:18 gives `devices` 45 s | plan 03-06 threat model; confirmed by gsd-security-auditor | 2026-10-31 |
| AR-03-03 | T-03-27 | devtools/ndk_pin.py:14-30 only compares, prints and exits 0/1; it never writes pins.py, so a lying API can only cause a false PASS/FAIL report before a release | plan 03-08 threat model; confirmed by gsd-security-auditor | 2026-10-31 |
| AR-03-04 | T-03-30 | `setup --json` prints the player's own tool paths to stdout only; no network (test_setup.py:89 `test_no_network`) | plan 03-09 threat model; confirmed by gsd-security-auditor | 2026-10-31 |
| AR-03-05 | T-03-SC | no dependency manifest changed in Phase 3 (empty diff on requirements*.txt, package.json, Cargo.toml, *.csproj, *.props); the one new binary download is sha256-pinned (T-03-09) | all 12 plan threat models; confirmed by gsd-security-auditor | 2026-10-31 |

*Accepted risks do not resurface in future audit runs.*

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-10-31 | 37 | 36 | 1 (T-03-35, medium, non-blocking) | gsd-security-auditor (ASVS L1, block_on high) via /gsd-execute-phase 3 |

Audit depth: L1 (each mitigation present and placed where its plan says, cited at file:line; 264 pinning tests run green). Not done: an end-to-end L3 trace, a real `fork-release.yml` run, or race-window analysis between the symlink check and the write in `desktop.install` beyond L1. The 03-12 keys-page tooltip (`firstrun.py:209`, not HTML-escaped) reopens no threat: the path comes from porter's search or the file dialog and Qt tooltips run no script.

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-10-31 (T-03-35 open below the high threshold; owner to fix or accept)

## Security Audit 2026-10-31

| Metric | Count |
|---|---|
| Threats found | 37 |
| Closed | 36 |
| Open | 1 |
