---
status: resolved
trigger: "Let's do it: implement implicit atlas sampling and LOD queries."
created: 2026-11-10
updated: 2026-11-10
---

## Result

Fragment implicit sampling and LOD queries now work through the compressed atlas. The corrected path passes 2,166 GPU checks. All 2,417 eligible real shaders convert, validate independently and load on-device, with 6,579 classified atlas bindings. A shader storage change also cuts peak process RSS in the real-module loading benchmark from 2.196 GiB to 0.933 GiB. Full-game RAM/FPS and the 9–10 GB target remain open.

The complete Mac renderer and overlay are preserved. No app installation, Android global setting, shared host replacement or commit occurred. Unrelated OOT work is untouched. Game-derived outputs remain on the external game drive.

## Sampling implementation

`atlas_glsl.compose` now receives the shader stage. Fragment `texture` calls, including shader bias, and `textureQueryLod` are rewritten. Other stages reject these implicit operations explicitly. Existing explicit LOD/fetch paths remain available.

The helper scales normalized query coordinates by logical-view extent divided by physical-cache extent. It uses the GPU's unclamped query result, then selects the logical mip range and sampler filtering. Shader bias clamps to the device limit recorded in metadata word 14. Dense descriptors retain native sampling/query operations. Anisotropy, nonzero sampler bias, reduction modes, offset/gather and descriptor arrays retain their explicit rejection paths.

DMSV entry flag bit 2 marks the new fragment metadata contract. The loader accepts it only for fragments; older loaders reject the new bundle explicitly. Bit0 remains the native trailer and bit 1 the NVN2 ABI. Legacy bundles still load. An old-runtime control fails exactly the new synthetic fragment entry, with the expected unsupported-flags diagnostic.

## Pixel and real-shader evidence

The synthetic comparison uses identical prepacked native blocks in dense and virtual textures. Every reference mip/layer is verified byte for byte on the GPU: 198 checks. Another 1,968 cases compare all 1,024 pixels, totaling 2,015,232 pixel comparisons across BC6H, ASTC4x4 and ASTC8x8 sRGB in both GOB orders. Cases cover min/mag filters, nearest/linear mips, repeat/clamp, mip/layer views, positive/negative/limited bias, sampler LOD bounds, zero derivatives and dense fallback.

All 2,166 checks pass. Maximum colour error is 0.010272 for HDR BC6H, 0.004688 for ASTC4x4 and 0.004555 for ASTC8x8 sRGB; query error is at most 0.000782. Preset tolerances are 0.025 for colour and 0.01 for query values. Removing only the logical-dimension correction fails 1,680 checks. An early fixture omitted its prepacked-layout marker; that invalid reference is retained as exploratory evidence, not a renderer regression.

The real asset census selects 2,417 of 2,419 programs using floating array implicit sampling or LOD queries. All selected programs convert and independently validate, with no unknown reflected bindings. Two programs in that group still require offset/gather support and fail explicitly. Other offset/gather-only programs also remain outside the current contract.

All 2,417 compact programs load on Adreno840. Twelve observed native stage combinations compile, including one replaced real fragment; eleven combinations retain their prior fragment programs. These are compile-only checks using a minimal RGBA8 pass. No real game buffers are dispatched.

## Shader storage and memory

The offline size pass aggressively inlined repeated atlas lookup trees. Retaining fragment function calls reduces the real bundle from 719.481 to 288.056 MiB, a 59.96% reduction. The largest checked module shrinks from 8,642,680 to 252,188 bytes. Both representations validate and load. Compute/native wrappers retain their previous compiler paths: a separate all-stages no-optimization experiment raised the small workload's peak RSS by about 8 MiB.

Two fresh processes per representation load the same 2,417 programs in inlined/compact/compact/inlined order. Android `time -v` records:

| Representation | Peak process RSS, KiB |
|---|---:|
| Inlined, run1/run2 | 2,302,172 / 2,302,172 |
| Compact, run1/run2 | 978,148 / 978,736 |

This saves about 1.26 GiB in a complete shader-subset loading benchmark. It includes bundle/module storage and process overhead; it allocates no game texture working set and compiles no game pipelines. It does not establish the saving during actual play.

The final repeated 121-job explicit-atlas workload retains a 40 MiB atlas allocation peak. Baseline/candidate remap medians are 2.176 versus 2.161–2.163 ms; new-content medians are 2.602–2.611 versus 2.607–2.609 ms. Process VmHWM is 138.48–138.99 versus 138.34–138.72 MiB. Earlier samples include remap medians of 2.17 and 3.74 ms; their cause remains unresolved. No speed gain is claimed. This regression workload does not measure the new fragment path's game GPU cost. GPU timestamps exclude private transfers; process and Vulkan counters overlap and must not be added.

## Checks, artifacts and next work

The final executable retains 102 driver, 856 atlas, 120 terrain and ten ordinary draw checks, plus five pool-restoration sizes. All 194 Android sources compile; 13 Python tests and targeted Ruff pass. The shell API validation layer remains unavailable. The five-title preflight selects MKW, Monster Hunter Rise, Odyssey, TotK and Xenoblade3 for compressed sampling/shared shader paths; their packaged Mac builds are absent. Docs retain their three existing failures.

Evidence: `/Volumes/Data/Switch/Mario Kart World/0400C3F00006E000-work/android-implicit-20261110/`. It preserves compact/inlined bundles, classified reflection, validation outputs, exact executable, controls, memory logs, raw CSVs, source hashes and reproduction scripts. Device/toolchain remain Lenovo TB323FU / Adreno840, Vulkan1.4.295, driver2c410f6f5c, API36, NDK28.2.13676358/API31. Owned device folder: `/data/local/tmp/nxhost-mkw-implicit-20261110`.

Next cover offset/gather and actual attachment types, then build the Android profile and attempt a bounded rendered scene with the measurement overlay. Measure real startup, working-set memory and frame stalls against the complete Mac reference. The full game has not launched; the overall 9–10 GB goal remains open.

Follow-up: [offset/gather and typed attachments](mkw-android-offset.md) passes 15,750 sampling checks, 88 typed export checks and fourteen recorded-format pipeline cases. All 21 real offset/gather programs convert, validate and load. Next build the Android profile and attempt a bounded scene.
