---
status: resolved
trigger: "Keep going from production Android task/mesh replay toward bounded native compressed atlas storage."
created: 2026-11-09
updated: 2026-11-09
---

## Bounded checkpoint achieved

The opt-in Android compressed atlas path now consumes actual NVN virtual-pool mappings and samples native compressed storage through production shader transformation, descriptors and command replay. This resolves this backend checkpoint only. No full Android game launch, game RAM/FPS or achievement of the 9–10 GB target is claimed.

Accepted Mac reference/overlay, shared `nxnative/dm/host/dmhost` and other dirty/OOT work are preserved. No agents, commit, app installation or global Android setting change. Only owned temporary device executables were used. Game-derived outputs remain on the external game drive.

## Implementation

- `dm/android/gfx_vk_atlas.c`: native compressed read-only 2D-array cell cache, real shared NVN mappings/dirty state/layout/deswizzle, content-hash sharing, immutable table snapshots and fence-protected cell/image retirement. Cache growth copies old content into a larger packed image. Private upload staging is bounded at 8 MiB, including batching beyond that size. Small logical mip uploads use whole compressed-block extents. Idle contexts evict after completion and reload from live mappings; pool cleanup releases atlas-owned backing. Statistics include current/retired cache images and private staging, excluding metadata/general scratch, NVN pools and driver overhead.
- `atlas_glsl.py` / `shader_vk.py --virtual-atlas`: supported floating sampler2DArray direct explicit-LOD/fetch/size/level operations receive a paired metadata SSBO (binding2048+original, RK_ATLAS15, texture flag16). Bilinear taps and both mip levels resolve independently. Logical dimensions, layers, view mips, object/view swizzles, native sRGB/HDR decoding, sampler nearest/linear/mip filters, clamp/repeat and LOD bounds are retained. Dense textures use original native operations through metadata zero.
- `gfx_vk_exec.c`: virtual descriptor and paired metadata resolution; disables descriptor memo reuse for these bindings. Also fixes independent NVN2 driver cache bug: task/mesh bank-zero hash extends from0x648 through0x870 to include storage tables at0x670/0x770. Classic/bank-one hash extents unchanged.
- `hle_nvn.c`: Android atlas mode records mappings without unsupported CPU vm_remap aliases; Mac/default behavior unchanged. Sparse virtual buffer access, unsupported sparse textures and unrewritten compressed atlas bindings fail explicitly instead of reading inaccessible memory or allocating a huge dense substitute.
- Supported scope: read-only native compressed 2D arrays, up to16mips, full64KiB source cells or holes. Partial subpages, implicit/gradient/gather/offset sampling, descriptor arrays, nonzero bias, anisotropy, mirror/border, comparison/reduction, reinterpretation, sparse writes/copies/attachments and uncompressed sparse storage remain unsupported/rejected. Do not enable this as a full-game renderer yet.

## Final evidence

External evidence: `/Volumes/Data/Switch/Mario Kart World/0400C3F00006E000-work/android-mapped-atlas-20261109/`. Isolated build `/tmp/nxhost-android-atlas-runtime`; synthetic shaders `/tmp/nvn2-atlas-shaders`; device folder `/data/local/tmp/nxhost-mkw-mapped-atlas-20261109`. Exact binaries, bundles, source snapshots/hashes, generated headers, commands and positive/negative logs are archived there. Reproduction: `probes/README.md#production-mapped-compressed-atlases`.

- Device Lenovo TB323FU, Adreno840, API36, Vulkan1.4.295, driver2c410f6f5c. NDK28.2.13676358, API31. All194 production Android sources compile; fixture compiles with-Wall-Werror.
- Final latest-binary run: **700/700 atlas checks, 9/9 draw checks, 26/26 real bundle module loads**. Real game modules are load-only, without dispatching game buffers. Synthetic atlas fixture uses real NVN pool initialize/map/finalize and production GPU replay.
- Patterned BC6H UFLOAT, ASTC4x4 UNORM, ASTC8x8 sRGB, both GOB orders; virtual offset32GiB. BC6H8192²×68layers/12mips logical NVN storage6,087,507,968bytes; ASTC rectangular8192×4096×68/12. Tests include seams/tails/filtering/views/queries/swizzles/holes; remap/write/unmap before submission; growth through multiple image layers and >8MiB upload staging; eighty replacements; idle eviction/reload; dense fallback and pool cleanup.
- Completed cache image+private staging20MiB (12+8), zero after pool release. Thin synthetic mapped workload only; this is neither full process RSS nor game working-set/peak. Growth can hold old+new images while previous draws remain live. Metadata and general scratch allocations are separate.
- Atlas-aware real bundle:26task/mesh modules,1,360,132bytes; reflection29storage,21driver,41constant,4texture+4atlas metadata bindings. Four texture bindings converted. Full11,603-program atlas coverage has not been rebuilt/audited.
- Isolated old-driver-hash binary fails2/9draw checks, fixed9/9. Partial-mapping, unsupported-sampler and virtual-buffer controls each abort explicitly as expected. No unexpected failure in final results JSON.
- Eight Python shader tests pass with translator/glslang/spirv-val available. Targeted Ruff0.15.13 with repository config passes; this is not the pinned0.17.2/Pyright ratchet. Full Mac graphics suite passes; separately added `check_test_android_shaders` target passes. `git diff --check` passes.
- Docs symptom index757. Docs11tests retain three pre-existing failures: missing0100005027A18000note, guide05length6242>6000, existing missing note/old Skyrim links. No new broken links. MKW/OOT boot-harness checks cannot run because packaged Mac builds are absent; report is saved. clang-tidy unavailable. No API-validation-layer pass: shell loader still cannot discover the Khronos layer. SPIR-V validation and GPU readbacks pass.
- During expansion a missing vkUnmapMemory PFN caused a compile failure and an earlier binary was inadvertently run. That result was discarded, the PFN was added, and the accepted final results came from the rebuilt binary after the compressed-block-copy correction. Stale log is not accepted/archive evidence.

## Next authorized work

Terrain follow-up is now complete for the tested inputs: [Android terrain upload parity](mkw-android-terrain.md), 120 checks including all540800texels and64shader samples from the eight accepted Mac height captures. The earlier handoff below remains historical for that item; shader/driver interfaces and a full scene are still open.

Audit remaining actual shader sampling instructions/modes and mesh/fragment interfaces (the26native keys lack static variation pairs), then NVN2 push-constant/compute-driver parity, typed colour outputs and CPU-streamed terrain uploads. Unsupported semantics must be implemented or identified before full-game enablement; never discard absent tiles to meet a memory target. Representative real-data population and transient allocation accounting are needed before a bounded game scene.

After those prerequisites, add `android.tsv` and attempt a bounded rendered scene with the existing platform/measurements overlay. Measure full process memory, startup and frame stalls; compare against the accepted textured Mac reference. The 9–10GB overall target and full Android runtime port remain open; see `mkw-memory-growth.md`.
