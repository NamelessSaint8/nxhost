---
status: resolved
trigger: "Continue the Android task/mesh milestone and prove a bounded alternative for compressed atlas storage."
created: 2026-11-09
updated: 2026-11-09
---

## Bounded checkpoint achieved

Task/mesh stages now pass through the production Android shader bundle, loader, bindings, pipeline construction and OP_DRAW_MESH replay. An explicit shader page-table storage prototype works on the connected Lenovo TB323FU / Adreno 840. This resolves this checkpoint only: the full Android game has not launched, full-game RAM/FPS remain unmeasured, and the 9–10 GB target is still open.

No agents, commit, app installation, global Android settings change or replacement of the shared Mac dmhost. The accepted Mac binary/overlay and OOT background work are preserved. Game outputs and evidence are external.

## Implementation

- `shader_vk.py` reads shared NVN2 compiler metadata before instruction trimming, translates stage-buffer IR and compiles native EXT task/mesh stages. DMSV stage IDs 6/7; entry.pad=1 adds a 36-byte versioned trailer after bindings/c1. Actual compiled workgroup allocations, common payload ABI (512 words), output counts/masks and task-input mode are recorded. Block names survive the spirv-cross/GLSL instance suffix through type-name reflection; native unknown bindings fail the build. Imports are usable by tests without CLI parsing/profile loading.
- `gfx_vk_core.c` optionally queries/enables task/mesh features and properties, preserving devices without them. `gfx_vk_shader.c` maps task set0, fragment set1, mesh set2, checks launch/shared/payload/output limits and creates mesh push-constant layouts. `gfx_vk_exec.c` keeps eight-stage resources and implements mesh pipeline/prewarm/draw paths without vertex input. First/count are push constants, task child groups remain relative, zero counts do no work, unsupported launches are rejected. Cache keys/magic distinguish mesh draws. Graphics dynamic UBO budgets allow three simultaneous stages.
- Per-primitive fragment inputs use a qualified variant; SPIR-V before1.4 gets the required global interface expansion. Ordinary vertex draws retain the original fragment interface. Native EXIT stays in a body function, leaving uniform wrapper barriers/emission/output reachable.
- Capture correction: shared SetShaders callback obtains NVN2 code length from its own header, rather than reading Maxwell +0x704. Version0xc9 control metadata is0xd8 bytes (all26 real exports); debug copy/capture retain it without reading a Maxwell0x880 section. Canonical NVN2 keys hash the first0x48 bytes with+0x30 zero, plus code.
- `probes/make_nvn2_replay.py` builds fixtures and optionally links all production host/backend objects. Only fixture program-key lookup replaces guest inputs. `vknvn2_replay.c` verifies replay pixels and offers load-only bundle checks.
- `probes/vkatlas.c` / `shaders/virtual-atlas.comp`: separate compressed physical tile array + logical page table; each bilinear tap resolves its own page and trilinear filtering resolves both mip levels. An ordered mapping update leaves another alias unchanged. Not production game sampling or an eviction policy.

## Verified evidence

External root: `/Volumes/Data/Switch/Mario Kart World/0400C3F00006E000-work/android-runtime-20261109/`. Summary JSON, exact binaries, source snapshots/hashes, build flags/profile header and logs. Owned device folder `/data/local/tmp/nxhost-mkw-replay-20261109`.

- All193 Android sources compile, isolated `/tmp/nxhost-android-mesh-runtime`; fixture links and compiles with `-Wall -Werror`. NDK28.2/API31.
- Nine replay GPU readbacks pass: direct/task mesh, first group, empty task, zero count, bad task UBO, bad mesh SSBO, per-primitive fragment input, ordinary vertex after mesh and oversized launch. Per-primitive fragment starts at SPIR-V1.0. Latest log `/tmp/mkw-android-replay-device.log`.
- All26 real stages build and load through the production loader (7task,19mesh), no game buffer dispatch. Reflection:29sbuf,21driver,41constant,4texture bindings; zero unknown kinds. `/tmp/mkw-android-bundle-device.log`. Earlier separate complete pipeline proof26/26 remains in `mkw-android-gpu-proof.md`.
- Virtual atlas22/22 comparisons pass. Logical8192²×68layers/14mips, four constant-colour128² BC6H tiles. HDR red decoded1.999, independent CPU reference2.0; tolerance0.025. Includes seams, fractional LOD, array layers, tails, clamp edges and mapping change.
- Physical image allocation65,536bytes; page table1,487,296bytes/371,824entries; upload65,536bytes; query/result payload352bytes, actual buffers384bytes. Total bound allocation1,618,752bytes, excluding driver/pipeline overhead. This deliberately aliases repeated synthetic colours; it does not estimate game resident tile count.
- Dense requirements for the same shape: BC6H/ASTC4x4 each6,085,001,216bytes, ASTC8x8s1,521,598,464bytes. No large dense image memory was allocated. Format conversion/quality is not tested or enabled.
- Four Python shader-generation tests pass (native metadata beyond trimmed instructions, capture canonical key/stage, block-name reflection, payload/launch rejection, native EXT generation/CLI/spirv-val). Targeted Ruff0.15.13 passes, not the pinned full-project lint ratchet. `git diff --check` passes.
- Full `make -j4 -C nxnative/dm/gfx/tests GAME=0400C3F00006E000 run` passes after the shared callback fix. `/tmp/mkw-android-runtime-gfx-tests.log`.
- Narrow MKW/OOT boot harness cannot run: neither packaged Mac build exists under `/Volumes/Data/Switch` (only Skyrim found). Initial sandbox worktree-metadata restriction was resolved with approved escalation; the remaining block is absent packages, not a pass. No auto-review rejection.
- Docs symptom index regenerated (755). Docs suite has the same three pre-existing failures: missing0100005027A18000 note, guide05 at6242words, existing missing note/old Skyrim links. No new link failure. API validation layer still unavailable to shell loader; these are SPIR-V validation/GPU readback checks, not an API layer pass.

## Next bounded milestone

Follow-up complete for the supported read-only compressed sampling scope: [mapped-atlas runtime checkpoint](mkw-android-mapped-atlas.md). It passes700GPU checks against actual NVN mappings, including concurrent versions, growth and eviction/reload. The next paragraphs record the earlier handoff; remaining unsupported sampling/rendering and game-scene work are tracked in the new checkpoint.

Implement actual compressed atlas mappings and shader sampling indirection, preserving native formats, filters and in-flight resource versions. Establish tile population/residency/eviction and memory accounting on representative real data before a full game allocation. Missing mappings must not become discarded textures. Check actual mesh/fragment interfaces (the runtime26 keys have no static variation pairs), unimplemented NVN2 push-constant/compute-driver parity, typed colour outputs and Vulkan CPU-streamed terrain uploads. Then add the Android profile (`android.tsv` still absent) and attempt a bounded rendered scene with the measurement overlay.

The standalone storage prototype covers clamp, explicit LOD and 2D-array BC6H only. Other sampling modes/instructions, derivatives, anisotropy, comparison/border semantics, texture writes/copies and concurrent mapping lifetimes need implementation/verification. Its eight texel taps plus table accesses need performance measurement; no Android gameplay FPS or RAM saving is established.
