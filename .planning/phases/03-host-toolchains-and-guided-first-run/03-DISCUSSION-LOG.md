# Phase 3: Host Toolchains and Guided First Run - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-10-31
**Phase:** 03-host-toolchains-and-guided-first-run
**Areas discussed:** Wizard flow and skip, prod.keys and legal step, Linux arm64 NDK trust, Distro adb and device states, Finder/menu tool discovery, Download cancel and resume, Wizard's last step

---

## Wizard flow and skip

### Where does the wizard live?

| Option | Selected |
|--------|----------|
| Own module, both windows | ✓ |
| New shell only |  |
| Make the new shell the default now |  |

**User's choice:** Own module (gui/firstrun.py), opened by today's window via one hook line and reused by the new shell

### After a skip, what does the next launch do?

| Option | Selected |
|--------|----------|
| Reopen until legal accepted | ✓ |
| Reopen while not ready |  |
| Banner only after the first skip |  |

**User's choice:** Wizard opens on launch only while the legal notice is unaccepted (porter records acceptance in config.json); afterwards banner with Continue setup

### What counts as setup complete?

| Option | Selected |
|--------|----------|
| Keys + NDK + .NET; device optional | ✓ |
| Also needs adb + a device |  |
| Needs adb, not a device |  |

**User's choice:** Legal accepted + prod.keys + NDK + .NET + signing key; adb and device optional (softer note)

### Reopened wizard: where does it start, and the Setup tab?

| Option | Selected |
|--------|----------|
| First unmet step; keep Setup tab | ✓ |
| Always step 1; keep Setup tab |  |
| First unmet step; wizard replaces Setup tab |  |

**User's choice:** Starts at the first step porter reports not ok (Back reaches earlier ones); Setup tab stays, reads the same setup --json, gains a Run setup button

---

## prod.keys and legal step

### Key check depth

| Option | Selected |
|--------|----------|
| Parse, required keys, generation | ✓ |
| Also test-decrypt a game |  |
| Existence only |  |

**User's choice:** Parse name = hex lines, check the keys extraction needs, report highest key generation; no decryption, no network

### Finding the file, what porter keeps

| Option | Selected |
|--------|----------|
| Auto-detect + Browse, keep path | ✓ |
| Browse only, keep path |  |
| Auto-detect + Browse, copy in |  |

**User's choice:** Auto-detect usual emulator key folders per OS + Browse; config.json keeps only the path, never copies

### Legal step scope and re-asking

| Option | Selected |
|--------|----------|
| One notice, versioned, once | ✓ |
| Two acceptances |  |
| Notice once, licenses every time |  |

**User's choice:** One notice (own dumps/keys, nothing uploaded, vendor licenses with links), version recorded in config.json on accept; changed notice re-asks; download dialog stops asking

---

## Linux arm64 NDK trust

### Download source

| Option | Selected |
|--------|----------|
| HomuHomu833, pinned; drift stops | ✓ |
| Re-host a verified copy on the fork |  |
| HomuHomu833, drift = untested warning |  |

**User's choice:** HomuHomu833 r27c pinned in pins.py (URL, size, sha256); mismatch stops naming both hashes; fix text: wait for pin bump or use own NDK; no fallback

### How it is presented

| Option | Selected |
|--------|----------|
| Usable, marked community | ✓ |
| Fully supported once probe passes |  |
| Experimental until Phase 6 |  |

**User's choice:** Green once probe passes, with note 'community r27c build, clang <ver>: not the build the titles were tested with'; port log repeats; Phase 6 parity may drop note; nothing refused

### Sysroot + distro clang fallback

| Option | Selected |
|--------|----------|
| Document only | ✓ |
| Automatic fallback |  |
| Drop it |  |

**User's choice:** Document the recipe only; a self-assembled folder passes the same checks and probe

### Compile probe scope

| Option | Selected |
|--------|----------|
| Every host, cached | ✓ |
| Linux arm64 only |  |
| At port time only |  |

**User's choice:** Every host, any NDK found; cached by clang path + mtime

---

## Distro adb and device states

### Old distro adb without push -Z

| Option | Selected |
|--------|----------|
| Use it, drop -Z | ✓ |
| Refuse below 30 |  |
| Refuse on x64, allow on arm64 |  |

**User's choice:** Use it; read adb version and drop -Z below the compression version; floor only for features porter really uses, with fix text

### Which adb when several

| Option | Selected |
|--------|----------|
| Keep today's order, show it | ✓ |
| Prefer porter's download |  |
| Ask in the wizard |  |

**User's choice:** Keep today's order (config, PATH, SDK, porter download); Setup shows path, version, source; download offered only when none found

### no permissions fix text

| Option | Selected |
|--------|----------|
| Distro-aware | ✓ |
| One generic line |  |
| Link to a docs page |  |

**User's choice:** Distro-aware from /etc/os-release ID/ID_LIKE with the exact command; unknown distro gets generic list

### Device step detection

| Option | Selected |
|--------|----------|
| Poll while open | ✓ |
| Refresh button |  |
| Poll + Restart adb button |  |

**User's choice:** Poll porter devices --json every 2-3 s while the step is visible; stop when left; pick saves config device when several

---

## Finder/menu tool discovery

### How tools are found with a bare PATH

| Option | Selected |
|--------|----------|
| Search known places each time | ✓ |
| Save resolved paths at Setup |  |
| Known places + login-shell PATH |  |

**User's choice:** Search PATH plus a fixed per-OS list of known places on every lookup; absolute paths to children; config keeps only player choices

### Anything else on discovery (privacy message proposed)

| Option | Selected |
|--------|----------|
| Next area |  |
| More questions | ✓ |

**User's choice:** Map macOS 'Operation not permitted' on game folder to a message naming System Settings > Privacy & Security (purpose strings already ship)

### libicu / LANG for dotnet children

| Option | Selected |
|--------|----------|
| Invariant mode for porter's dotnet | ✓ |
| Check libicu in Setup |  |
| Both |  |

**User's choice:** Porter's dotnet children always get DOTNET_SYSTEM_GLOBALIZATION_INVARIANT=1, LANG=C.UTF-8 when unset, via env dicts

### How TOOL-04 is proven

| Option | Selected |
|--------|----------|
| CI bare-env doctor + manual UAT | ✓ |
| Manual UAT only |  |
| Unit tests only |  |

**User's choice:** CI runs frozen bundle doctor/setup --json under env -i PATH=/usr/bin:/bin on macOS + both Linux runners with tools in known places; full Finder/menu port is manual UAT in docs/RELEASE_CHECK.md

### Linux desktop menu entry

| Option | Selected |
|--------|----------|
| Porter writes it, wizard offers it | ✓ |
| Ship a .desktop file + INSTALL.md steps |  |
| Terminal launch only on Linux |  |

**User's choice:** Porter command writes ~/.local/share/applications/nx2android.desktop + icon with the bundle's absolute exe; wizard last step offers it on Linux; rerun after moving fixes it; nothing written without asking

---

## Download cancel and resume

### Cancel

| Option | Selected |
|--------|----------|
| Stop batch, keep partial | ✓ |
| Per-tool skip + cancel all |  |
| Stop batch, discard partial |  |

**User's choice:** Stops the whole tools --download run with Phase 1 stop; finished tools stay; in-flight file keeps .part; half-unpacked folder removed

### Resume

| Option | Selected |
|--------|----------|
| Range resume, across restarts | ✓ |
| Same run only |  |
| Range resume + auto-redownload once |  |

**User's choice:** HTTP Range on .part named after the pinned file, same run (3 logged retries) and across restarts; existing bytes re-hashed first; Range ignored -> from zero; final mismatch deletes .part and stops naming both hashes, never silent redownload

### Already have a tool

| Option | Selected |
|--------|----------|
| Per-tool 'I have it' Browse | ✓ |
| Only on the Setup tab |  |
| Auto-detect only |  |

**User's choice:** Per-tool 'Use my own...' picker saves via porter config, re-runs setup --json, row shows porter's verdict; Download all missing fetches only what's missing

### Prepare .NET tools in setup

| Option | Selected |
|--------|----------|
| Prepare in setup | ✓ |
| Leave it to the first port |  |
| Prepare, and require it for ready |  |

**User's choice:** Yes: extra 'Prepare .NET tools' stage (restore, NuGet hash check, nx_extract + translator build) with progress/cancel; ready does not wait for it; failure is a note

### Linux arm64 no adb

| Option | Selected |
|--------|----------|
| Distro install command | ✓ |
| Install command on every Linux |  |
| Generic text |  |

**User's choice:** Distro-aware install command from /etc/os-release + Re-check + Use my own; x64 keeps the download

### Progress detail

| Option | Selected |
|--------|----------|
| Bytes + speed + time left | ✓ |
| Keep today's line |  |
| Overall bar too |  |

**User's choice:** Bytes + speed + time left per file; porter adds rate/eta to progress events (additive); bar per file, stage counter for batch

### Install from a user-downloaded archive

| Option | Selected |
|--------|----------|
| No, porter downloads only | ✓ |
| Yes, Install from file... |  |

**User's choice:** No, porter downloads only

### Toolchain location

| Option | Selected |
|--------|----------|
| Keep the fixed place | ✓ |
| A Tools folder setting |  |

**User's choice:** Fixed <user dir>/toolchains; disk check names the drive; NX2A_HOME or Use my own for elsewhere

---

## Wizard's last step

### What the last page shows

| Option | Selected |
|--------|----------|
| Summary + playable list | ✓ |
| Summary + Port a game |  |
| Plain Done |  |

**User's choice:** Summary + notes, playable titles from profiles --json, Linux Add to app menu, Port a game button opening the Port tab's picker

---

## Claude's Discretion

- `setup --json` shape and command placement; new config key for the legal version; `build.py` host-folder edit and glslc fallback; player-supplied arm64 NDK acceptance; shared `/etc/os-release` helper; key folder locations, required key names and generation mapping; adb compression version and floor; banner wording, poll interval, timeouts, probe cache location, stale `.part` cleanup; proxies via urllib; whether `tools --download` keeps writing config.

## Deferred Ideas

- inspect names the key generation a game needs vs the keys present (PORT-01, Phase 4)
- Restart adb button for offline devices (rejected for now)
- Install toolchain from a user-downloaded archive (rejected)
- Configurable toolchains folder (rejected)
- Automatic sysroot + distro clang fallback (documented only)
