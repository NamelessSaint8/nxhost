---
status: resolved
trigger: "Let's do it! Continue the Android driver work and measurements."
created: 2026-11-09
updated: 2026-11-09
---

## Result

The tested Android NVN2 push-constant and dispatch-driver gaps are fixed. The final GPU replay passes 102 checks. All 755 selected real programs now pass independent SPIR-V validation and device module loading. Full-game rendering, RAM/FPS and the 9–10 GB target remain open.

The accepted Mac executable, overlay and unrelated OOT work are preserved. No installed app, Android setting or shared host binary changed. No commit was made. Game-derived files stay in the external game work folder.

## Causes and corrections

- `OP_PUSH_CONST` was ignored and bank24 was filled as a handle bank. Replay now maintains separate 256-byte graphics/compute state, applies partial byte updates, invalidates affected descriptor memo entries and snapshots c24 for each use.
- Direct dispatch dimensions reached descriptors one dispatch late. They now precede descriptor construction. NVN2 reads counts at c0+4 and canonical c0+0x200; classic compute keeps its own layout. DMSV entry flag bit1 records the NVN2 ABI. Bit0 retains the task/mesh trailer; legacy native entries still work. Old unmarked NVN2 compute bundles require rebuilding.
- Indirect arguments may be produced by earlier GPU work. Ordered GPU copies now fill both driver count fields from the actual argument buffer, with fresh immutable driver storage for each dispatch. No CPU read supplies those counts. Invalid ranges/alignment and malformed push records stop explicitly.
- Shader reflection misclassified uniform c17/c18 as driver banks. Uniform c3 through c18 now map to slots0 through15; c24 remains push state.
- Independent validation found 239 real programs missing formatless storage-image capability declarations. Android SPIR-V finalization adds capabilities55/56 only for actual Unknown-format image reads/writes. It preserves instructions, types, IDs and bounds. All 755 modules then validate; 88 declare read capability and 235 write capability, with overlap. The GPU fixture verifies a formatless R32F write, read and image readback. Device read/write support is present.

## Evidence

Device: Lenovo TB323FU, Adreno840, API36, Vulkan1.4.295, driver2c410f6f5c. NDK28.2.13676358, production API31 build. Isolated output: `/tmp/nxhost-android-driver-runtime`; fixture: `/tmp/nvn2-driver-shaders`; owned device folder: `/data/local/tmp/nxhost-mkw-driver-20261109`.

The original runtime fails 57 of the 100 common driver checks. The corrected suite passes those 100 plus two formatless-image checks. It covers independent stage groups, full/partial/unaligned push updates, c24 tails, immutable descriptor snapshots, classic/NVN2 direct counts, zero counts, GPU-written and deferred-upload indirect counts, reused indirect addresses, uniform slot15, graphics and native task/mesh push state. Five malformed-record/address/count controls abort as expected; an unknown DMSV flag is rejected during loading.

The same final executable passes 856 atlas, 120 terrain and nine ordinary draw checks, plus pool restoration at five sizes. Terrain retains the earlier exact match of 540,800 captured height texels and 64 shader samples. All 194 production sources compile; nine Python shader tests and targeted Ruff pass. The unavailable shell API layer remains a validation gap. These are SPIR-V and GPU readback results.

The real subset contains 729 compute, seven task and 19 mesh programs, with 30 c24 bindings. All 755 build, validate and load. This driver census bundle does not use `--virtual-atlas`; it is not a full-game bundle and no real game buffers are dispatched. The previously accepted atlas-aware task/mesh bundle is retained separately.

## Measurement comparison

Two fresh processes per version run the same 121-job compressed-atlas fixture in baseline/candidate/candidate/baseline order. Baseline here means the accepted optimized renderer from the previous measurement checkpoint, rather than the earlier slow atlas implementation. First ten unchanged jobs are excluded from steady-state summaries.

| Metric | Previous renderer | Driver correction |
|---|---:|---:|
| Remap preparation, per-run medians | 2.256–2.266 ms | 2.254–2.268 ms |
| New-content preparation, per-run medians | 2.695–2.697 ms | 2.696–2.699 ms |
| Unchanged preparation, per-run medians | 0.0497–0.0503 ms | 0.0501–0.0502 ms |
| Atlas allocation peak | 40 MiB | 40 MiB |
| Process VmHWM, including teardown | 138.05–139.04 MiB | 139.96–140.41 MiB |
| First-use preparation wall time | 177–179 ms | 202–226 ms |
| First-use preparation thread CPU | 167–168 ms | 169–193 ms |

Steady refresh costs are retained. First-use samples and process high-water memory are higher; this comparison does not establish their cause or a full-game startup regression. These runs establish no further RAM or performance gain. Each run preserves all source/output bytes after cleanup. Main GPU timestamps exclude private atlas transfers; process and Vulkan allocation counters overlap and must not be added. No gameplay FPS is inferred.

## Reproduction and next work

The external `0400C3F00006E000-work/android-driver-state-20261109/` checkpoint preserves exact binaries, source snapshots, build flags, control inputs, shader bundles, validation census, raw CSVs, comparison JSON and device logs. See [probe commands](../../probes/README.md#android-driver-state-replay) and the [game checkpoint](../../nxnative/dm/games/0400C3F00006E000/README.md#android-driver-state-parity-2026-11-09).

The required five-title preflight targets MKW and Donkey Kong Bananza for NVN2 push/dispatch state, plus TotK, Xenoblade3 and 13Sentinels for classic dispatch/reflection behavior. The preflight stopped because all five packaged Mac builds are missing locally. The docs suite retains its three existing failures: a missing game note, guide05 over its word limit and existing missing note/Skyrim links.

Next, audit actual sampling modes and task/mesh-to-fragment interfaces, including typed outputs. Then add the Android profile and attempt a bounded rendered game scene with the measurement overlay. Measure startup, process memory and frame stalls against the complete Mac reference. Preserve all texture and terrain data while pursuing the 9–10 GB goal.

Follow-up: [Android interfaces](mkw-android-interfaces.md) validates and device-loads the full 11,603-program set, repairs 40 padded vertex modules and compiles 12 observed native pipeline combinations. Implicit atlas sampling/LOD queries are the next substantial coverage gap; actual attachments and a game scene remain open.
