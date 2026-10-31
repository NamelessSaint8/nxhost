---
phase: "02"
slug: "porter-hardening"
status: verified
# threats_open = count of OPEN threats at or above workflow.security_block_on severity (the blocking gate)
threats_open: 0
asvs_level: 1
created: "2026-10-31"
---

# Phase 02 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| porter ↔ another porter process | two runs (GUI and CLI) on one game's build folder, or on the shared `<user dir>/tools` | build outputs, the translator, the lock holder's text |
| porter ↔ local disk | data pack swap, stage outputs, signing key and APK writes, cut off at any point | the signing key (secret), build outputs |
| player's account ↔ other local users | the signing key file on a shared machine | the signing key (secret) |
| vendor servers (Google, Microsoft) → porter | NDK, platform-tools and .NET archives and their indexes, over HTTPS | executables porter later runs |
| downloaded archive → `<user dir>/toolchains` | member names and links chosen by whoever built the archive | files beside `config.json` and `signing-key.json` |
| nuget.org → porter's package folder | packages restored by dotnet, then built and run | code built into nx_extract and the translator |
| GitHub (raw content, API) → porter | FPSLocker-Warehouse configs applied to game memory and code | third-party patch data |
| porter → child processes | env and program path every tool runs with | PATH, DOTNET_ROOT |
| porter → device over adb | stale-file removal driven by the pack's file list | files on the device |
| porter JSON / game files → GUI rich text | names and texts reaching Qt's HTML renderer | untrusted strings |
| contributor ↔ repository history; vendored code ↔ upstream | commit-message checks, local Ryujinx changes, title IDs in core code | source |

---

## Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-02-01 | Tampering | `<tid>_build/` written by two porters at once | medium | mitigate | `porter/lock.py` `take`; taken in `pipeline.py:128` and `cli.py:114`; `tests/test_lock.py` | closed |
| T-02-02 | Denial of service | data pack between removal and rename | medium | mitigate | `porter/datapack.py` `recover`; `tests/test_datapack.py` | closed |
| T-02-03 | Denial of service | whole-file MD5 of big modules | low | mitigate | `porter/adb.py:10` `hashlib.file_digest` | closed |
| T-02-04 | Information disclosure | build-folder path reaching the device in the pack | low | mitigate | sidecar `<App>-data.build`; `Swap.test_no_host_path_in_pack` | closed |
| T-02-05 | Information disclosure | `signing-key.json` readable by other users | high | mitigate | `mkapk.py:192` `save_key` via mkstemp (0600); `:209` tightens an older key to 0600 | closed |
| T-02-06 | Denial of service | truncated or forked signing key | high | mitigate | `mkapk.py:199` `os.link` no-clobber publish; `toolchain.py:107` Signing key doctor row | closed |
| T-02-07 | Tampering | APK half-written when pushed | medium | mitigate | `mkapk.py:232` `.partial` then rename | closed |
| T-02-08 | Repudiation | unchecked commit messages in a fresh clone | low | mitigate | `devtools/hooks.py` sets `core.hooksPath` | closed |
| T-02-09 | Tampering | Ryujinx local changes lost on re-vendor | low | mitigate | `nxnative/dm/third_party/ryujinx/nxnative-local.patch` | closed |
| T-02-10 | Elevation of privilege | title ID slipping into dm/android by concatenation | low | mitigate | `tests/arch_rules.py:18` `join_literals` | closed |
| T-02-11 | Tampering / Elevation | `_unzip` zip-slip and link escape | high | mitigate | `porter/fetch.py` `_unzip`/`_install`; `tests/test_fetch.py` `Unpack` | closed |
| T-02-12 | Tampering | `_untar` filter bypass (CVE-2025-4517 family) | high | mitigate | `fetch.py:198` `filter='data'`; Python floor in `toolchain.py:91` | closed |
| T-02-13 | Tampering | compromised index listing a bad hash | high | mitigate | hashes pinned in `porter/pins.py`, compared in `fetch.py` | closed |
| T-02-14 | Tampering | fallback trusting the vendor index | medium | mitigate | fallback only on 404/410, marked untested; NDK never falls back (`fetch.py:3`) | closed |
| T-02-15 | Spoofing | markup through index strings in the download dialog | medium | mitigate | `html.escape` in `gui/app.py` | closed |
| T-02-16 | Tampering | bare `dotnet` resolved through the parent's PATH | medium | mitigate | `pipeline.py:97` env with own PATH and `DOTNET_ROOT`; Env tests on windows-2025 (UAT 2) | closed |
| T-02-17 | Tampering | upstream rename silently disabling an override | low | mitigate | `porter/upstream.py:25` `_overrides` | closed |
| T-02-18 | Denial of service | drive filling mid-port | low | mitigate | `pipeline.py:167` and `:174` free-space checks | closed |
| T-02-19 | Tampering | half-written stage outputs reused after a kill | medium | mitigate | `build_ipa_from_nsp.py:364` `swap_in`, `:374` `write_whole`; `tests/test_stages.py` | closed |
| T-02-20 | Tampering | key surviving a power loss without its data | low | accept | documented in `docs/ARCHITECTURE.md:54` with the recovery | closed |
| T-02-21 | Tampering / data loss | stale-file removal on the device | medium | mitigate | `tests/test_adb.py:87` `test_stale_removed_in_batches` | closed |
| T-02-22 | Denial of service | `tools --only` unknown name traceback | low | mitigate | `cli.py:66` named error, exit 2 | closed |
| T-02-23 | Tampering | config changed on the moving v4 branch | medium | mitigate | `fpslocker.py:50` pinned commit first; `pipeline.py:273` commit and SHA-256 logged | closed |
| T-02-24 | Tampering | truncated cache converted offline | low | mitigate | `pipeline.py:272` `write_whole` with the commit in line 1 | closed |
| T-02-25 | Denial of service | GitHub API rate limit | low | accept | see Accepted Risks Log | closed |
| T-02-26 | Spoofing | markup in game/profile strings on the game card | medium | mitigate | `html.escape` in `gui/app.py`; `tests/test_bridge.py:409` `Escaping` | closed |
| T-02-27 | Spoofing | crafted language name in the combo box | low | accept | see Accepted Risks Log | closed |
| T-02-28 | Tampering | substituted NuGet package | high | mitigate | `pins.NUGET`; `porter/nuget.py` check; `tests/test_nuget.py` | closed |
| T-02-29 | Tampering | two ports building the shared tools at once | medium | mitigate | blocking `<user dir>/tools/.porter.lock` (`porter/lock.py`) | closed |
| T-02-30 | Tampering | package targets running during restore | low | accept | see Accepted Risks Log | closed |
| T-02-31 | Tampering / Elevation | link through a later link escaping the unpack folder (CR-01) | high | mitigate | two-pass link check in `fetch.py`; `test_fetch.py:171` `test_link_through_later_link_refused` | closed |
| T-02-32 | Denial of service | zip link loop | low | accept | superseded by T-02-38 (now refused with BuildError) | closed |
| T-02-33 | Tampering / DoS | waiting port swapping over a translator in use (CR-03) | high | mitigate | reuse check in `nuget.py:32` `restored`; per-key `dmsh_xlate-<key[:12]>` (`pipeline.py:336`) | closed |
| T-02-34 | Denial of service | Windows holder read crossing the locked byte (CR-02) | medium | mitigate | `lock.py:20` `buffering=0`; `test_lock.py:123` `test_holder_read_stays_below_lock` | closed |
| T-02-35 | Denial of service (disk) | old translator folders piling up | low | accept | see Accepted Risks Log | closed |
| T-02-36 | Tampering / Info disclosure | link leaving the installed toolchain after the top folder is stripped (CR-04) | high | mitigate | `fetch.py:140` `_link_refusal` | closed |
| T-02-37 | Tampering | in-memory model diverging from disk (case, aliases, duplicates) | medium | mitigate | casefolded, printable-ASCII checks in `fetch.py:145` | closed |
| T-02-38 | Denial of service | link loops and long chains (IN-06) | low | mitigate | 40-substitution cap in `fetch.py`; `test_fetch.py:185` `test_link_loop_refused` | closed |
| T-02-39 | Tampering (availability) | `_install` deleting the old toolchain first (WR-05) | medium | mitigate | `.old` aside in `fetch.py:208`; `test_failed_move_keeps_old_toolchain`, `test_cut_off_move_restored` | closed |
| T-02-40 | Denial of service (availability) | stricter rule refusing a genuine pinned archive | medium | mitigate | `devtools/zip_links.py`; `tests/fixtures/zip_links.json`; `test_fetch.py:280` `test_pinned_archives_pass` | closed |
| T-02-41 | Tampering | fixture link tables not hash-verified | low | accept | see Accepted Risks Log | closed |
| T-02-42 | Tampering | two `tools --download` runs racing | low | accept | see Accepted Risks Log | closed |
| T-02-SC | Tampering | NuGet restore (02-10) | high | mitigate | every restored package's content hash checked against `porter/pins.py` before build (`porter/nuget.py`) | closed |
| T-02-SC | Tampering | npm/pip/cargo installs (all other plans) | low | accept | see Accepted Risks Log | closed |

*Status: open · closed · open — below high threshold (non-blocking)*
*Severity: critical > high > medium > low — only open threats at or above workflow.security_block_on count toward threats_open*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-02-01 | T-02-20 | fsync of whole trees is too slow (RESEARCH A10); recovery is deleting the build folder, documented in ARCHITECTURE.md | developer, plan 02-06 | 2026-10-31 |
| AR-02-02 | T-02-25 | a refused lookup is an OSError and takes the cached-copy path; the pinned commit is tried first, so most ports never call the API | developer, plan 02-08 | 2026-10-31 |
| AR-02-03 | T-02-27 | QComboBox items are plain text; names come from upstream's fixed `nacp.LANGUAGES` | developer, plan 02-09 | 2026-10-31 |
| AR-02-04 | T-02-30 | restore runs no package targets (RESEARCH A7); the hash check still precedes every build and run | developer, plan 02-10 | 2026-10-31 |
| AR-02-05 | T-02-32 | superseded by T-02-38: loops are now refused with BuildError on every Python | developer, plan 02-11 | 2026-10-31 |
| AR-02-06 | T-02-35 | about 5 MB per translator change; old folders can be deleted by hand | developer, plan 02-12 | 2026-10-31 |
| AR-02-07 | T-02-41 | test data, not the install path: every real install checks the whole archive's pinned hash; zipfile checks each link entry's CRC | developer, plan 02-13 | 2026-10-31 |
| AR-02-08 | T-02-42 | not serialized today; the GUI runs one download at a time | developer, plan 02-13 | 2026-10-31 |
| AR-02-09 | T-02-SC | no npm/pip/cargo install in plans 02-01 to 02-09 and 02-11 to 02-13; no new dependency added | developer, plans 02-01..02-13 | 2026-10-31 |

*Accepted risks do not resurface in future audit runs.*

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-10-31 | 44 | 44 | 0 | /gsd-secure-phase 02 (L1 grep check, register from plan time; no auditor spawned per the short-circuit rule) |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-10-31
