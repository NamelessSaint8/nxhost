---
status: resolved
trigger: "How are things looking, and how does the potential look? Let's keep going."
created: 2026-11-10
updated: 2026-11-10
---

## Result

The complete Android shader set now builds, passes independent SPIR-V validation and loads on Adreno840: **11,603 programs**. Twelve native pipeline combinations observed in actual Mac opening runs compile on the device using their real task, mesh and fragment programs. These checks cover known shader modules and the recorded stage combinations. Rendering a full Android game scene remains open.

The prospects for the port have improved. Compression, terrain upload, driver state and real shader compatibility have device evidence. The 9–10 GB target still requires a measured game working set. These checks establish no new game RAM or FPS result.

The accepted Mac executable and overlay are preserved. No app installation, global Android setting, shared host replacement or commit occurred. Unrelated OOT work is untouched. Game-derived outputs remain external.

## Root cause and correction

The full build succeeded before the change, but independent validation rejected 40 padded vertex shaders. `dmsv_pad.py` created new scalar/vector/pointer declarations even when identical types existed. SPIR-V rejects duplicate non-aggregate types. Padding now reuses existing types and shares new declarations across missing output locations.

The expanded fixture also exposed incorrect defaults for shorter float vectors: padding put 1 in their last component. Missing generic attributes use (0,0,0,1), so vec2/vec3 require zero components. Only vec4 receives W=1. Integer defaults retain the earlier zero policy.

The host test checks valid SPIR-V, idempotence and literal defaults for vec2/vec3/vec4, signed/unsigned vectors and repeated types. A production GPU draw checks all those defaults and produces literal green. A control restoring only the old short-vector defaults stays valid SPIR-V but produces red and fails exactly one of ten draw checks. The failing original full bundle and both controls are preserved.

## Real program and pipeline coverage

- Full bundle: 7,301 fragment, 3,547 vertex, 729 compute, seven task and 19 mesh programs. All 11,603 build, validate for Vulkan1.2 and load on the device. The bundle is 495.7 MiB and does not use `--virtual-atlas`.
- Two existing Mac run logs supply 12 observed task/mesh/fragment combinations, including combinations absent from the static pair table. Their 27 distinct real programs compile into device graphics pipelines through production module variants and descriptor layouts. Basic interface inspection finds no missing locations or scalar-type mismatches. Per-primitive fragment qualification is exercised.
- Those pipeline checks use a minimal RGBA8 render pass. They bind no fabricated game buffers and dispatch no real game shader. Actual render-target types, attachment/blend/depth combinations and rendered scene correctness remain separate work. Compile calls span 7.2–87.5 ms in this run; they are isolated compilation timings, not frame stalls or FPS.
- The final executable passes 102 driver, 856 atlas, 120 terrain and ten ordinary draw checks, plus five pool-restoration sizes. The terrain suite retains its exact captured-height comparisons. All 194 production Android sources compile; 11 Python shader/audit tests and targeted Ruff pass.

The shell API validation layer remains unavailable. Independent SPIR-V validation and actual synthetic GPU readbacks passed. The five-title preflight selected MKW, Mario Odyssey, TotK, Xenoblade3 and HadesII for shared padding/interface behavior; their packaged Mac builds are absent, so it stopped before booting them. The docs suite retains its three existing failures.

## Sampling census and next work

`probes/audit_android_sampling.py` inspects actual image instructions and their declared types. It distinguishes ordinary sampled arrays, depth-comparison arrays and storage-image reads, and checks operand positions against an independently compiled fixture. No image value remains unresolved in this bundle.

For floating sampled 2D arrays, the complete shader set contains:

| Operation | Instruction sites |
|---|---:|
| Explicit LOD | 10,928 |
| Fetch with LOD | 1,988 |
| Implicit sampling | 6,825 |
| LOD query | 4,317 |
| Explicit LOD plus constant offset | 129 |
| Gather | 41 |
| Implicit sampling plus constant offset | 6 |
| Size with LOD | 8 |

Implicit sampling occurs in 2,359 fragment programs; LOD queries occur in 1,118 programs. These are complete asset-library counts, not frequencies measured during play. Shadow comparisons and 114 storage-image reads have separate paths and counts. The existing atlas rewrite covers explicit LOD, fetch and size/level queries. It still rejects the unimplemented sampling operations explicitly.

The next implementation target is fragment implicit sampling and LOD queries through the compressed atlas. Preserve virtual texture dimensions, derivatives, sampler LOD rules and dense fallbacks; compare actual pixels with dense sampling before adding offset/gather coverage. Then validate actual attachment types and attempt a bounded Android scene with the measurement overlay. Measure startup, process memory and frame stalls against the complete Mac reference.

## Evidence

External checkpoint: `/Volumes/Data/Switch/Mario Kart World/0400C3F00006E000-work/android-interfaces-20261110/`. It contains full before/after bundles, all independent validation results, the authoritative sampling census, observed-pipeline provenance and subset, exact device executable, synthetic controls, build inputs and logs. The initial sampling report used an incorrect shadow operand position; it is exploratory evidence only. The final census fixes that parser and has a dedicated regression test. Its 11,603 validation results are authoritative.

Device/toolchain remain Lenovo TB323FU / Adreno840, API36, Vulkan1.4.295, driver2c410f6f5c, NDK28.2.13676358/API31. Isolated build: `/tmp/nxhost-android-interface-runtime`; owned device folder: `/data/local/tmp/nxhost-mkw-interface-20261110`. No full game launched. See [probe reproduction](../../probes/README.md#real-android-shader-and-pipeline-audit).

Follow-up: [implicit atlas sampling](mkw-android-implicit.md) passes 2,166 GPU checks and converts/validates/loads2,417 real programs. Fragment function retention lowers measured shader-loading peak RSS by about 1.26 GiB. Offset/gather, actual attachments and a game scene remain next; full-game RAM/FPS are unmeasured.
