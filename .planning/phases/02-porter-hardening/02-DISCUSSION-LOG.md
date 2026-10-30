# Phase 2: Porter Hardening - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md. This log keeps the alternatives that were considered.

**Date:** 2026-10-30
**Phase:** 02-porter-hardening
**Areas discussed:** Download pinning policy, Concurrent/cut-off ports, Housekeeping choices

---

## Download pinning policy

### When the vendor stops serving the pinned toolchain file

| Option | Description | Selected |
|--------|-------------|----------|
| Exact pin, stop | Download only the manifest's URL; if it's gone, Setup stops until the manifest is bumped | |
| Exact pin, fallback to newest | Try the pinned URL; on a 404, take the vendor's newest, check it against the vendor hash, and warn that it's untested | ✓ |

**User's choice:** Exact pin, fallback to newest

### FPSLocker configs

| Option | Description | Selected |
|--------|-------------|----------|
| Pinned commit + head fallback | Manifest pins a warehouse commit; fetch at that commit; fall back to v4 head with a warning; log the commit and SHA-256 | ✓ |
| Head, stop if config changed | Fetch the newest; record the hash; stop when the same build's config changes until the player accepts it | |
| Head, record and warn only | Fetch the newest; log the hash; warn on a change | |

**User's choice:** Pinned commit + head fallback (recommended)

### Toolchains the player already has

| Option | Description | Selected |
|--------|-------------|----------|
| Version check, warn | Compare the found version with the manifest; amber "not the tested version" | |
| Leave as today | Keep today's checks; the manifest governs downloads only | ✓ |
| Version mismatch stops | Refuse any version not in the manifest | |

**User's choice:** Leave as today

### NuGet pins

| Option | Description | Selected |
|--------|-------------|----------|
| Lock files, manifest points | Commit packages.lock.json beside each .csproj; `--locked-mode`; the manifest names the lock files | |
| Manifest only, porter checks | Packages, versions and SHA-512 in porter's manifest; porter checks `.nupkg.sha512` after restore | ✓ |

**User's choice:** Manifest only, porter checks (against the research recommendation; keeps the subtree free of new files)

---

## Concurrent/cut-off ports

### Second port of the same game folder

| Option | Description | Selected |
|--------|-------------|----------|
| Stop with who holds it | "Already running" with the command, PID and start time; OS file lock, never stale | ✓ |
| Wait for the first to finish | Queue until the lock frees | |

**User's choice:** Stop with who holds it (recommended)

### Lock scope

| Option | Description | Selected |
|--------|-------------|----------|
| Port + install | Same lock for port and install of a game; the iOS sharing rule is documented | ✓ |
| Port only | Only ports lock | |
| Port + install + iOS | Also lock in upstream's iOS `main()` (a subtree edit) | |

**User's choice:** Port + install (recommended)

### Where the atomic stamp fix goes

| Option | Description | Selected |
|--------|-------------|----------|
| Small edit in the subtree | Atomic key write and in-place stage fixes in `build_ipa_from_nsp.py` | ✓ |
| Override from porter | Named, asserted overrides in `porter/upstream.py` | |

**User's choice:** Small edit in the subtree (recommended)

### The D-08 marker after the stamps land

| Option | Description | Selected |
|--------|-------------|----------|
| Keep the note, drop redo-all | Still says "cut off in <stage>"; only mismatched stamps rerun | ✓ |
| Remove it entirely | Stamps alone, no note | |
| Keep redo-all as a safety net | Leave D-08 as it is | |

**User's choice:** Keep the note, drop redo-all (recommended)

---

## Housekeeping choices

### probes/app/mkapk.py

| Option | Description | Selected |
|--------|-------------|----------|
| Delete it, use committed | Probe build calls `nxnative/dm/android/apk/mkapk.py` with flags | ✓ |
| Thin wrapper | A few lines calling the committed signer with the probe's defaults | |

**User's choice:** Delete it, use committed (recommended)

### Commit hook bootstrap

| Option | Description | Selected |
|--------|-------------|----------|
| Bootstrap script + README | A small devtools script sets `core.hooksPath`; the README says to run it | ✓ |
| Test warns when unset | The suite warns in a checkout without the hook | |
| README step only | Make the existing line more prominent | |

**User's choice:** Bootstrap script + README (recommended)

### Language list source

| Option | Description | Selected |
|--------|-------------|----------|
| inspect JSON, game's own | `inspect` reports the game's supported languages from nacp; the GUI fills from it | ✓ |
| Full nacp list via JSON | All 16 nacp languages, unfiltered | |
| GUI imports nacp directly | Fewest lines; pulls engine imports into the GUI | |

**User's choice:** inspect JSON, game's own (recommended)

---

## Claude's Discretion

- Signing key safety (not selected for discussion): research defaults, which are an atomic 0600 write and a stop rather than a silent regeneration of an unreadable key
- Hostile archives and where the Python refusal sits; manifest format and location; fallback bounds; the NuGet cache location; the data-pack aside-swap; env dicts; the smaller CONCERNS items; the TEST-01 approach

## Deferred Ideas

None.
