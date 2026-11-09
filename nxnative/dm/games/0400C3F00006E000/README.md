# Mario Kart World (Switch 2)

Split and shader-built from a loose dump of update 917504. Direct Mac host runs now reach the title, menus, Grand Prix movie and first race,
with textured gameplay verified on an M4 Max. This profile has provisional memory reservations but no registered `build` rows or `android.tsv`;
memory use, some frame-rate drops and task/mesh rendering remain open.

- Dump: `exefs/` (main 33.6 MB, sdk, subsdk0/1) + `romfs/` (22 GB), loose.
- Engine: Nintendo EPD's Nin_Ounce (sead / agl / gsys, Phive), SDK with NVN2; Ampere shaders.
- Shaders: 11,603 in [`shader_map.tsv`](shader_map.tsv), from `Shader/*.Nin_Ounce_NVN2.bfsha.zs` (BNSH), one `.sarc.zs` with agl `sharcb` packs,
  `Lib/agl/agl_resource.Nin_Ounce_NVN2.release.sarc` (BAHS packs, 3,924 of them), the effect set (`Effect/static.…esetb.byml.zs`, 1,017 compute
  programs) and the UI layouts.

## Current rendering diagnosis (2026-11-08)

The Mac shader build for chain `4af3b2a70fef` has 11,577 successful translations and 26 failures: 13 entries labelled vertex and 13 labelled domain,
all task/mesh programs from `DrivePassShaderDefault.sharcb`. Every failure explicitly refuses ISBERD/ISBEWR because the host has no task/mesh pipeline.
All 19 shader-library load failures in `mvdrive.log` are members of that failed set. Their keys **are present** in `shader_map.tsv`; rebuilding the same
chain cannot produce the missing libraries without implementing the refused stages.

`nvnCommandBufferDrawMeshTasks` has no semantic implementation: it reaches `nvn_unimpl_c`, logs once and returns without recording a draw. A 136 s
instrumented Mac run recorded **131,329 calls** to it while reproducing the menus and course-loading transition. These are recording API calls, not
a count of cached command executions. Missing mesh geometry is therefore a confirmed rendering gap, beyond any texture upload question.

**Resolved: black intro movie and disconnected render-target aliases.** A matched pass capture found a correct, changing 2560x1440 movie in
RGBA8 texture serial 31381, while the compositor sampled an empty RGBA8_SRGB serial 31382. A storage probe confirmed both descriptors name the
same pool, offset, dimensions and storage size. The scene also has writer/reader descriptors differing only by `COMPRESSIBLE`. The host now shares
that storage while preserving each descriptor's format interpretation; see [Linear and sRGB descriptors share texture storage](../../../docs/reference/rendering.md#linear-and-srgb-descriptors-share-texture-storage).
With the fix, movie captures at 1, 5 and 10 seconds show different, correctly displayed frames instead of black. The menu's 2D world map and course
art still render, and the run reaches the first race with a live HUD, minimap and visible 3D outlines.

**Resolved: the completed race scene was cleared again.** GPU-timeline snapshots of the same frame show a coloured kart and course after the material
passes, then a black target after subsequent clear-only passes. The game guards those clears with timestamp-report conditions, which the provisional
profile ignored. Enabling the existing `render_cond` implementation preserves the completed scene. The candidate pass trace shows the repeated clears
skipped when their counters are `0 / 0`, and the starting sequence and race now display the kart, opponents and textured course. See
[Conditional rendering evaluated at replay](../../../docs/reference/rendering.md#conditional-rendering-evaluated-at-replay).

**Resolved: whole-pool vertex conversion dominated the race CPU time.** A CPU sample identified `vconv_fill` converting entire bound mesh pools.
The existing `vconv_range on` path limits conversion to the vertices each draw reads. The player confirmed playable racing, and the
`materials-20261108-vconv-range` run recorded race windows around 40–50 FPS, with some later windows above 50. Its index-range validation checked
over 14 million reuses with zero differences. The same host's dense-texture baseline, `poc-20261108-no-hud-check`, also records 40–43 FPS in the race.
This is a measured improvement over the earlier roughly 7 FPS run; it does not establish a sustained 60 FPS.

**Resolved: performance HUD regression.** `poc-20261108` and `poc-20261108-hud-check` reproduced single-digit race windows with the default HUD
configuration. The same executable with the HUD off restored 40–43 FPS. Explicitly disabling optional encoder timing, insights and logging, and
selecting the requested presentation metrics, restores racing with the overlay visible in `poc-20261108-hud-basic`. Its 42.53-second H.264 POC
video records the game window at 1280×752 (1280×720 content plus its title bar), without audio. Checked frames show 42–59 FPS, about 35 GB process
footprint, and the remaining pink cast. The exact optional collector responsible is still unknown. See
[Performance HUD collection scope](../../../docs/reference/frame-rate.md#performance-hud-collection-scope).

**Resolved: broad pink course materials and unnecessary atlas copies.** Sparse atlas copies previously updated only the Metal image, leaving
its mapped physical storage stale. Later uploads could restore invalid ASTC blocks. Equal-format sparse copies now persist through the guest page
table, with ordered readbacks for GPU-written sources and a new texture version at first use. Consecutive level copies no longer upload whole atlases.
See [Copies into sparse textures persist in physical storage](../../../docs/reference/rendering.md#copies-into-sparse-textures-persist-in-physical-storage).
The `ram-pink-20261108-copy-dense-check` run reaches the race under Metal API validation with native sparse allocation disabled. Its moving captures
show grey road/metal, green barriers and textured canyon materials where the earlier POC had a broad pink wash. A HUD capture reads 46.95 FPS,
24.52 GB app footprint and 23.57 GB Metal allocation, versus the earlier POC's 35.37 GB / 34.49 GB. Later race windows measure 46–51 FPS and
about 23 GiB process footprint. These are measured windows, not a sustained 60 FPS claim or a complete material audit.
The final `ram-pink-20261108-copy-fixed-clean` run uses the same dense allocation with both validation layers off and the HUD on. Its 26.49-second
H.264 clip, `Mario-Kart-World-fixed-materials.mp4`, shows corrected materials while driving; checked HUD frames at 5 and 20 seconds read 60.63 /
62.38 FPS and 24.32 / 24.33 GB app memory. Log windows include 43–60 FPS and one 16.7 FPS window: frames 5629–5637 re-upload whole 1.5–8.7 GB
atlases repeatedly, taking up to 2.9 seconds per frame. Incremental atlas updates are therefore the next measured stall target. The run reaches
racing without GPU execution errors or crashes; `measurements.json` beside the clip preserves the windows and stalls. Native sparse allocation stays
disabled. The tested executable is saved as `0400C3F00006E000-work/dmhost-atlas-fixed-20261108`.

**Current: native sparse allocation and incremental versions (2026-11-08).** The automatic-sparse fault is resolved by using placement-sparse
metadata and making both metadata and physical heaps resident. A separate queue/residency race and associated-heap retirement deadlock are fixed.
Eligible compressed atlases now use this path by default on supported hardware (`DM_NVN_NATIVE_SPARSE=0` restores dense allocation). Unchanged
64 KB tiles are shared between immutable metadata versions; writes replace only affected tiles, preserving earlier draws. A 765.5 MiB atlas
refresh uploads 84–168 MiB rather than the full atlas. See [Sparse texture versions share unchanged physical tiles](../../../docs/reference/rendering.md#sparse-texture-versions-share-unchanged-physical-tiles)
and [Residency mutations and queue commits share a lock](../../../docs/reference/nvn-objects.md#residency-mutations-and-queue-commits-share-a-lock).
The clean `ram-20261108-sparse-pages` run reaches lap 3 with corrected course materials and no GPU execution error. Its 21.31-second H.264 proof,
`Mario-Kart-World-sparse-tiles.mp4`, retains the platform, resolution, FPS, GPU time and app/Metal memory HUD. A checked frame at 5 seconds reads
54.16 FPS, 16.46 GB app memory and 16.51 GB Metal allocation, versus the dense proof's 24.32 GB app memory. These are different gameplay windows,
not a matched-frame benchmark. First-use shader work still causes 1.2–1.5-second pauses; later streaming windows still contain 100–243 ms frames.
A compute image dimension mismatch found by shader validation is also fixed and covered by an actual GPU write to the selected mip/array layer:
[Writable image views follow the instruction dimension](../../../docs/reference/rendering.md#writable-image-views-follow-the-instruction-dimension).

**Current: writable sparse atlases and packed vertex conversion (2026-11-09).** A large-allocation census in `ram-20261108-writable-census`
found ten GPU-written sparse atlases with about 3,131 MiB dense Metal allocation but only 152 MiB mapped: four 16384² R8, four 8192² RG16 and
two 8192² R16 textures. Eligible GPU-only images now use sparse physical pages shared through NVN mappings, preserving GPU writes across
descriptor aliases and remaps. Unsupported layouts retain dense storage. See
[Writable sparse textures preserve GPU physical pages](../../../docs/reference/rendering.md#writable-sparse-textures-preserve-gpu-physical-pages).
`t_sparse_image` passes 249 checks in each encoding mode with both validation layers, including actual shader/raster writes and physical-pool reuse.

The writable-sparse race sample then identified packed signed vertex conversion as a remaining CPU bottleneck: `vconv_fill` appeared in 493 of
966 presentation-thread samples. A dedicated SIMD loop preserves its float bits and default fourth component; the new sample has 72 of 707
presentation-thread samples there. The separate samples are not matched frames. See
[Packed signed vertex conversion processes four vertices together](../../../docs/reference/frame-rate.md#packed-signed-vertex-conversion-processes-four-vertices-together).
Its 864 bit-exact checks and 422 GPU vertex-fetch checks pass. The focused CPU benchmark is about 34× faster; that is not a gameplay speed multiplier.

The clean `ram-20261109-vectorized` run ended gracefully after frame 15000 with no GPU execution error. Its 21.29-second H.264 proof,
`Mario-Kart-World-vectorized.mp4`, keeps the M4 Max/macOS 27.0, 1280×720, FPS, GPU time and app/Metal memory overlay (1280×752 window capture,
no audio). At 5 seconds the HUD reads **58.66 FPS, 13.83 GB app memory, 13.19 GB Metal allocation and 7.02 ms GPU time**, versus the previous
precise-page proof's 16.78 GB app memory. These are different gameplay windows. Frames 5100–15000 have 34 reporting windows, median 60.0 FPS,
range 35.8–60.0; 28 of 34 are at least 59 FPS. The final window overlaps CPU sampling and is not an unperturbed frame-time measurement.
Captured racing retains the corrected road, kart and canyon materials. `measurements.json`, `proof-5s.png` and `run-proof.py` preserve the result;
`0400C3F00006E000-work/dmhost-vectorized-20261109` preserves the rebuilt executable with these fixes. Only allocation-dump column cleanup and
comments changed after the gameplay capture; `measurements.json` records that distinction. Startup prewarm is disabled and the save is copied.

The remaining stalls have two measured sources before CPU sampling: frame 5763 took 174.3 ms with 130.9 MB texture uploads taking 111.7 ms
and no new pipelines/libraries; frame 5841 took 111.7 ms with 92.3 ms in new pipelines/libraries and negligible uploads. Other streaming frames
upload about 126 MB in 112–118 ms while the GPU frame remains around 7 ms. Incremental uploads still block replay, and first-use compilation
remains visible with diagnostic prewarm disabled. These need separate remedies; an average near 60 FPS does not establish smooth frame pacing.
The final focused suite passes 1,800 checks. The required five-game harness was attempted for Mario Kart World, Monster Hunter Rise,
Age of Calamity, Super Mario Bros. Wonder and Skyrim (shared NVN pools, writable images and packed vertex conversion); it refuses the run because
the first four lack packaged Mac builds under `/Volumes/Data/Switch`. Skyrim is present, but this refusal is not a regression pass.

**Current: streaming CPU lookup cost (2026-11-09).** Phase timing in `stalls-20261109-timing` separates sparse protection/census, page checks,
queue preparation, mapping, gather/deswizzle and completion. At 14,936 mapped BC6H tiles, checking the pages takes 33–35 ms: each physical-run
check scans the registered memory pools again. A thread-local hint with lifecycle invalidation and first-match overlap bounds removes those
repeated scans. The same page-check phase is 1.85–2.23 ms in `stalls-20261109-lookup`. See
[Dirty-range lookup hints preserve first matches](../../../docs/reference/nvn-objects.md#dirty-range-lookup-hints-preserve-first-matches).
In frames 5000–6600 with no new shader/pipeline work, the largest recorded upload time falls from 110.6 to 60.5 ms; these are separate runs of the
same route, not matched frames. Both end gracefully at frame 6600 without GPU execution errors. The focused lookup test passes 19 cases, and
the shared tracker passes slot/shared-page, write-publication and retirement-race checks. The modified C source also compiles with Android NDK
28.2; an Android runtime benefit is unmeasured.

Mapping still rescanned the entire page array for every backing heap. It now builds per-heap operation batches in linear passes; see
[Sparse mapping batches group tiles by backing heap](../../../docs/reference/rendering.md#sparse-mapping-batches-group-tiles-by-backing-heap).
In `stalls-20261109-mapping`, the matched 14,936-tile / 84 MB and 63 MB refreshes spend 2.47–3.92 ms mapping, versus 9.18–10.07 ms with the
lookup fix alone. The largest upload-only time in frames 5000–6600 is now 53.7 ms (110.6 ms before either change); this remains a separate-route
comparison, and complete frames can still exceed 100 ms. CPU fill and GPU completion waits remain significant, so the upload path is not stall-free.
The run ends gracefully after frame 7800 without GPU execution errors. Its 31.21-second `Mario-Kart-World-streaming.mp4` keeps the full metrics
overlay; checked HUD frames at 5 / 20 seconds read 59.38 / 60.20 FPS, 13.38 / 13.73 GB app memory and 7.67 / 7.46 ms GPU time. Materials remain
correct in the checked frames. This work targets CPU stalls and establishes no additional RAM saving. `comparison.json`, per-run `measurements.json`,
proof images, driver scripts and test logs preserve all three runs; `0400C3F00006E000-work/dmhost-streaming-20261109` is the exact executable
used for the final capture. Startup prewarm and validation are off during these gameplay runs; phase timing and the HUD are on, and saves are copied.
The two changes pass 2,512 sparse GPU checks across direct/deferred encoding, including copy-on-write, compressed holes/tails, mutable aliases,
remaps and GPU-written sources, under API and shader validation. Residency stress completes 12,000 Metal 4 plus 120 classic commits during
12,000 allocation replacements. The five-title harness was attempted for Mario Kart World, Xenoblade Chronicles 3, OCTOPATH TRAVELER,
Super Mario Bros. Wonder and Skyrim (shared dirty tracking and streamed textures); the first four lack packaged Mac builds and block the run.
This is not a five-title regression pass. The shader chain and its inputs are unchanged.

**Experimental: asynchronous read-only sparse transfers (2026-11-09).** With `DM_NVN_SPARSE_ASYNC=1`, sparse refreshes submit immutable tile uploads without waiting for each
classic command buffer on the CPU. The existing Metal 4 mapping → classic upload → Metal 4 consumer shared events still order GPU access.
Pending staging is bounded at 128 MiB, with an individually larger transfer admitted alone; explicit finish/drain boundaries wait for callbacks.
GPU-written sparse storage keeps its synchronous path. The default remains synchronous because the presentation-rate comparison is inconclusive. See
[Read-only sparse uploads use queue events](../../../docs/reference/rendering.md#read-only-sparse-uploads-use-queue-events).
The new gated test passes 58 cases normally and 81 with injected upload loss in each encoding mode, including old/new pixel versions,
backpressure, oversized transfer accounting and rebuilding without a guest write. With the existing sparse sampling/copy and writable-alias
suite, 2,790 checks pass under Metal API and shader validation. A separate synchronous-path run passes 410 checks; residency commit stress
also passes. The required harness was attempted for Mario Kart World, OCTOPATH TRAVELER, Xenoblade Chronicles 3, Super Mario Bros. Wonder and
Skyrim; four missing packaged Mac builds block it. The direct Mac comparison uses copied saves and the same executable for both modes.

`stalls-20261109-async-control` and `stalls-20261109-async` show matching 14,936-tile refreshes losing about 10–15 ms of CPU completion wait;
the asynchronous enqueue phase is 0.03 ms. Upload-only maxima in frames 5000–6600 are 53.4 / 38.5 ms, but complete frames still reach about
100 ms. The first control had no video capture, so presentation was checked again in `stalls-20261109-async-control-capture` with the same
capture settings. Its checked HUD frames at 5 / 20 / 28 seconds show 58.97 / 59.99 / 59.79 FPS; the asynchronous clip shows 49.31 / 48.16 /
56.80 FPS. The scripted input is the same but collision outcomes and camera positions diverge, so this does not isolate a causal regression.
It also does not establish an end-to-end benefit: the asynchronous path stays opt-in. Both captured runs end gracefully at frame 7800 without
GPU execution errors and preserve corrected materials. The exact comparison executable is `dmhost-async-experimental-20261109` in the work folder.

**Current: CPU copy-loop cost (2026-11-09).** The separate `stalls-20261109-copy-timing` run identifies 10–16 MiB writes to sparse physical
storage taking about 9–14 ms before uploading. Their page-preparation counts are normal; the loop recalculates the complete block-linear address
and uses a variable-length copy for each 16-byte piece. Hoisting the row terms and using constant-length full-piece copies preserves partial
edges, holes and dirty-page precision while reducing that CPU work. See
[Region writes hoist block-linear row addressing](../../../docs/reference/nvn-objects.md#region-writes-hoist-block-linear-row-addressing).
Three alternating synthetic runs have median 9.60 ms before / 7.05 ms after for an identical 16 MiB sparse copy. The changed shared NVN source
passes an Android NDK 28.2 syntax check after removing an Apple-specific `MIN` macro dependency. This is compile coverage, not Android gameplay.
The final focused suite passes 227 NVN checks (including complete-level oracles for partial writes and copy mirrors) plus 2,790 sparse/ordering
checks under Metal validation, including both upload modes. The shader chain and inputs remain unchanged.

The final synchronous `stalls-20261109-copy-loop` run ends gracefully at frame 7800 without GPU execution errors. Matched 16 MiB writes with
1,024 page preparations take about 11.3 ms versus about 14.0 ms in the diagnostic baseline; complete frame stalls remain. Its 31.21-second
`Mario-Kart-World-copy-loop.mp4` keeps the platform/resolution/FPS/GPU/app-memory overlay: checked frames at 5 / 20 seconds read 60.00 / 59.87 FPS,
13.49 / 13.83 GB app memory and 8.09 / 7.73 ms GPU time, with corrected materials. These are sampled frames, not a sustained frame-rate claim
or a new RAM saving. Peak sampled footprint in the run is 13,370 MiB. `comparison.json`, per-run `measurements.json`, proof images, scripts,
the synthetic benchmark and validation logs preserve all five experiments; `dmhost-copy-loop-20261109` is the exact final executable. Both
startup prewarm and validation are off during gameplay, the HUD and phase timing are on, and each run uses a copied save. A separate final
check of the synchronous default passes another 410 sparse GPU checks.

**Open: 9–10 GB app RAM target, streaming/shader pauses, collision slowdowns and task/mesh rendering.** The latest proof uses about 13.8 GB app memory;
the RAM target is not met. A read-only census finds no large cache-only retired texture accumulation. An isolated archive census costs
about 1.2 GiB host footprint, but its failed lookups add no significant Metal allocation. A cold 4 GiB zero-copy-buffer probe changes Metal's logical
allocation count by 4 GiB with essentially no app-footprint change: logical GPU allocation is not itself a RAM saving. Remaining memory work needs
app-footprint measurements. Collision-specific stalls still need controlled reproduction; a full game-wide shader-validation audit remains open.
The earlier precise-page run's 21.33-second proof, `ram-20261108-precise-pages/Mario-Kart-World-precise-sparse.mp4`, shows 56.47 FPS,
16.78 GB app memory and 16.60 GB Metal allocation at 5 seconds. Its `measurements.json`, `proof-5s.png` and `run-proof.py` preserve the result;
`0400C3F00006E000-work/dmhost-native-sparse-20261108` preserves the executable. The RAM target remains unmet.
The native-default check is recorded separately in `ram-20261108-native-default`; startup prewarm remains disabled in these measurements to expose first-use work. Precise sparse dirty-page tracking is checked separately in `ram-20261108-precise-pages`. All runs use copied saves. The focused GPU checks run direct
and deferred encoding with both validation layers, stderr error reporting and abort-on-fault. The required five-title harness cannot run because
four packaged Mac builds are absent under `/Volumes/Data/Switch` (only Skyrim is packaged); this does not count as a pass.
The 26 unsupported task/mesh stages above are a separate confirmed gap; their prefetch
errors did not establish the cause of the black race image, which the ordered snapshots and conditional-clear comparison now identify.

Screenshots without `DM_NVN_SHOT_OUT` save the whole 3840x2160 swapchain. Black pixels outside its 2048x1152 window crop are expected in those files;
they do not establish that presentation failed to scale the crop. This is separate from missing content inside the crop.

Local evidence: `.gamedump/MarioKartWorld/logs/{mvdrive,cvdrive}.log`, the active cache's `_b_build.json`, and
`.gamedump/MarioKartWorld/diagnose-20261108/{run.log,calls.tsv,findings.json,shot-*.png}`. The diagnostic used a separate save copy and ended gracefully.
Storage probes and matched movie/race captures are in the external game work folder,
`0400C3F00006E000-work/{storage-20261108,transition-20261108-a,transition-20261108-fixed2,race-20261108-storage-fixed}/`.
All these runs used copied saves and ended gracefully.
The conditional-clear comparison is in `0400C3F00006E000-work/materials-20261108-{baseline,conditional}/`: `run.log`, `race-*.png`, `cbuf/` and
GPU-ordered raw attachments in `passes/`. These raw pass filenames name the preceding pass counter; add one for ordinary draw passes when matching
the `P` records. End-of-frame target dumps alone hid the correctly coloured intermediate scene because the same target was cleared later.

Validation: the storage, usage-upgrade, dynamic-image-alias, pixel-format-view, swizzle, stencil, image-usage, copy-alias and mip-view GPU checks pass
under Metal validation, including both encoding modes where provided. The required regression harness was attempted on Mario Kart World,
Xenoblade Chronicles 3, Persona 5 Royal, Link's Awakening and Skyrim (shared textures, deferred targets and movies); it refused the run because only
Skyrim has a packaged Mac build under the local games directory. The loose dumps are usable for direct runs but do not satisfy that harness.

## Found on this game

- [Linear and sRGB descriptors share texture storage](../../../docs/reference/rendering.md#linear-and-srgb-descriptors-share-texture-storage): resolved black movie output; race rendering remains incomplete.
- [Conditional rendering evaluated at replay](../../../docs/reference/rendering.md#conditional-rendering-evaluated-at-replay): `render_cond on` preserves the completed course and kart by skipping repeated conditional clears.
- [Copies into sparse textures persist in physical storage](../../../docs/reference/rendering.md#copies-into-sparse-textures-persist-in-physical-storage): corrects stale atlas content and reduces redundant allocations.
- [Sparse texture versions share unchanged physical tiles](../../../docs/reference/rendering.md#sparse-texture-versions-share-unchanged-physical-tiles): native compression, physical-page sharing and smaller refresh uploads.
- [Dirty-range lookup hints preserve first matches](../../../docs/reference/nvn-objects.md#dirty-range-lookup-hints-preserve-first-matches): removes repeated whole-registry searches from sparse tile checks; shared by Mac and Android.
- [Sparse mapping batches group tiles by backing heap](../../../docs/reference/rendering.md#sparse-mapping-batches-group-tiles-by-backing-heap): avoids scanning every tile again for every physical heap.
- [Read-only sparse uploads use queue events](../../../docs/reference/rendering.md#read-only-sparse-uploads-use-queue-events): overlaps CPU replay with immutable uploads while bounding pending staging and preserving copy order.
- [Region writes hoist block-linear row addressing](../../../docs/reference/nvn-objects.md#region-writes-hoist-block-linear-row-addressing): reduces CPU copy work shared by Mac and Android while preserving partial writes and sparse holes.
- [Writable sparse textures preserve GPU physical pages](../../../docs/reference/rendering.md#writable-sparse-textures-preserve-gpu-physical-pages): removes dense GPU atlas backing while keeping shader/raster writes coherent across aliases.
- [Packed signed vertex conversion processes four vertices together](../../../docs/reference/frame-rate.md#packed-signed-vertex-conversion-processes-four-vertices-together): removes repeated format decoding from the racing CPU hotspot.
- [Vulkan sparse support is checked per format](../../../docs/reference/rendering.md#vulkan-sparse-support-is-checked-per-format): measures Android residency, format, aliasing and address-space prerequisites separately.
- [Residency mutations and queue commits share a lock](../../../docs/reference/nvn-objects.md#residency-mutations-and-queue-commits-share-a-lock): fixes the independently reproduced queue race and destructor deadlock.
- [Writable image views follow the instruction dimension](../../../docs/reference/rendering.md#writable-image-views-follow-the-instruction-dimension): preserves a selected array layer/mip for non-array compute image instructions.
- [Performance HUD collection scope](../../../docs/reference/frame-rate.md#performance-hud-collection-scope): presentation metrics remain visible without the severe default-HUD regression.

## Android memory prerequisites

On 2026-11-09, the updated `probes/vkprobe.c` was compiled with NDK 28.2 (`-O1 -Wall`, no diagnostics), copied to a temporary device path and
run on the connected Lenovo TB323FU / Adreno 840, stock Qualcomm driver (build `2c410f6f5c`, dated 2026-02-13), Vulkan 1.4.295. This is a
capability query, not Android gameplay or an allocation/readback proof. Evidence is `ram-20261109-vectorized/android-capabilities.log` in the
external game work folder.

| Capability | Measured answer |
|---|---|
| Native BC and ASTC LDR texture sampling | Supported |
| Sparse binding / 2D image residency | Supported, with strict nonresident reads |
| Sparse physical-page aliasing | Unsupported |
| Sparse address space | 4095 MiB |
| R16 / RG16 sparse image granularity | 256×128 / 128×128 texels; both sampled/upload and render/storage usage supported |
| R8, BC6H, ASTC 4×4 UNORM, ASTC 8×8 sRGB | No sparse properties for sampled-plus-upload usage |
| Ordinary host-pointer import / memory-budget extension | Neither reported |

`dm/android/gfx_vk_tex.c::img_new` currently creates fully bound dense images; it does not implement sparse residency. A Vulkan port may have
different overhead from Metal, but this driver cannot directly inherit the Metal physical-page-sharing strategy. The queried compressed formats
need another storage strategy or driver capability before a native-sparse implementation can help them. No Android game footprint has been
measured, and the 9–10 GB target is not established there. The title still has no `android.tsv`; its successful SPIR-V pipeline checks below are
shader proofs rather than a completed Android runtime port.

## Shaders

`shader_split.py` over the whole RomFS: 11,603 shaders (7,301 pixel, 3,560 vertex, 729 compute, 13 domain), 5,180 variation pairs.

`shader_vk.py` (the Android chain, SPIR-V): **11,577 of 11,603 build**, 495 MB bundle. The 26 that do not are **task and mesh programs** (`ISBERD`/
`ISBEWR`), which this host cannot dispatch: NVN2 draws some geometry with a task program in the vertex slot and a mesh program in the tessellation
slot, writing each vertex into a stage buffer (Eglantine's `NX2_NOTES` rows 89 and 97 — the same reason high-detail LODs pop in and out there). The
translator refuses them by name.

On a device (`probes/vksh.c`, Lenovo Legion Y700, Adreno 840): 729 of 729 compute pipelines compile and **5,180 of 5,180** vertex/pixel pairs compile.
The pairs first came out 5,124: the 56 that did not were stage-link failures, which is what the Mac chain's `vs_pad` fixes — `dmsv_pad.py` now pads the
vertex modules the same way (40 shaders, 40 outputs). The device reports `VK_EXT_mesh_shader`, so the task/mesh gap is this host's, not the GPU's.
`docs/SWITCH2.md` has the table.

Reproduce (the profile is the game, so `DM_GAME` is its program id):

```
DM_GAME=0400C3F00006E000 J=8 python dm/gfx/tools/shader_split.py <dump>/romfs <dump>/exefs/main \
    /tmp/mkw/pkg . shader_facts.tsv shader_pairs.tsv pso_pairs.tsv      # shader_map.tsv, the facts, the pairs
DM_GAME=0400C3F00006E000 python dm/android/tools/shader_vk.py /tmp/mkw/pkg /tmp/mkw/shaders.dmsv --jobs 8
```

`docs/SWITCH2.md` says what a port would still need (the NVN2 command stream, the services, a task/mesh pipeline, memory); `devtools/nvn2_shader_census.py`
measures a dump without a profile.
