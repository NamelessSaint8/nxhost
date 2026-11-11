---
status: investigating
trigger: "Agreed Mac stability milestone before Android: correct scenes, stable memory, reduced recurring stalls."
created: 2026-11-09
updated: 2026-11-09
---

## Scope

Preserve the accepted CPU-streamed terrain fixes and the measurements/platform HUD. Establish a repeatable 30-minute Mac workload, determine whether memory plateaus, reclaim unused resources when justified, and measure recurring >50 ms frames. Android follows a stable rendering/memory baseline; exact 9–10 GB on Mac is not a prerequisite. No commits or shared dmhost replacement. Preserve others' edits and background OOT work. Derived data stays on the external game drive.

## Current hypothesis and next test

Hypothesis: long-run growth includes guest cache warming plus private GPU texture/cache retention; no leak or RAM floor established.
Next: finish the unchanged thirty-minute baseline, then run an isolated sequential timing comparison with allocation census and API validation disabled on both sides. Do not evict live assets without ownership/use evidence. The first course/results plateaus, while the second course adds guest and GPU working data.

## Sparse refresh optimization under verification

Baseline phase timing shows expensive sparse refreshes, including zero-tile-upload refreshes. The implementation still creates/maps replacement metadata and queues/waits for an upload even when every resulting tile points to the exact same immutable physical page. A regression fails on the original implementation: identical dirty contents replace metadata unnecessarily.

Candidate `dmhost-sparse-unchanged-20261109` retains the previous texture only for compatible read-only layout, an identical complete ordered tile list and identical physical page objects. A changed mapping may upload zero bytes by reusing cached contents, so zero bytes alone is never the predicate. Preserve the original queued completion dependency and advance validation stamps. Mutable GPU storage and failed-upload epochs keep their old paths. The NvPkg caller must not defer-release the retained allocation or remove its residency.

Tests cover an identical dirty write; changed mappings with zero uploads; unmaps; old-version reads; cached descriptor residency after deferred releases drain; and an unchanged pending upload returning without waiting or retaining an extra transfer reservation. Full graphics `make run` passes, including shader-pull/TBDR checks. Immutable-sharing async fixtures additionally pass 82 normal / 84 dropped-upload checks per encoding mode with API/shader validation. Five-title harness attempted for MKW, TotK, FFT, Great Ace Attorney and Skyrim: four packaged builds absent. Compdb 231 sources; clang-tidy unavailable. Docs retain the same three pre-existing failures, with no new broken links.

Evidence: `/tmp/mkw-sparse-noop-graphics-suite.log`, `/tmp/mkw-noop-async-final-*`, `/tmp/mkw-stability-regress.log`, `/tmp/mkw-stability-docs.log`. Exact candidate and fingerprint are external. Shared dmhost untouched; no commits.

## Controlled baseline progress

`stability-baseline-20261109-165657`, PID 94404, driver `/tmp/mkw-stability-baseline.py`. Initial menu route and a short accelerator hold reach the first race; longer acceleration finishes it, followed by a parked results phase. Explicit result/Next Race confirmations enter a second-course transition with five minutes of acceleration. Inputs, screenshots and memstat are recorded; this is not thirty minutes of uninterrupted driving.

First course/results: 120 s 11,127 MiB, 300 s 11,183, 600 s 11,247; stays near 11,200 through twenty minutes. At 1,489 s, second-course streaming reaches 12,470 MiB, guest charged 7,050 MiB, unattributed 3,465 MiB. This establishes a course-specific plateau and growth with additional content, not a universal RAM floor or a proven all-world leak.

Timing contamination: test compilation approximately 384–471 s; isolated host build 461–487 s; full graphics build/test 564–1,248 s. The allocation census itself stalls some frame boundaries. Compare timing only in separate uncontended runs with census disabled. `/tmp/mkw-stability-followup.py` requested the checkpoint stop; its PID identity guard encountered the transient exiting process and stopped. Explicit `ps` verified PID 94404 gone and no competing game/compiler; the driver reports exit 0 at 1,801.45 s. Comparison then launched directly, without overlap. Scripts and outputs remain external/scratch.

## Thirty-minute baseline complete

1,801 seconds, peak 12,558 MiB (13.17 decimal GB), final 12,544 MiB. The final five-minute range is 12,466–12,558 MiB; guest charged stays about 7,051 MiB. The city results capture confirms the second race finished with road/scenery present. No logged GPU execution error or crash. This is a bounded two-course result, not proof of a worldwide plateau or a RAM floor. Baseline `stability-summary.json` and updated `session.json` record limits and build activity.

Active timing comparison: `stability-compare-20261109-172737`, driver `/tmp/mkw-stability-compare.py`, session 82756. Baseline PID 20073 starts first; candidate follows only after baseline reaped. Both 210 s, same save/recipe seed/route, API/shader validation and allocation census disabled, per-frame timing TSV enabled, sparse phase timing and HUD retained. One sequential pair with different NPC trajectories is not a matched FPS benchmark.

## Timing result and corrected optimization target

The first comparison completes with both processes exiting 0. Baseline 85–204 s: 59.43 FPS, 11 frames >50 ms, 4 >100 ms, max 152.268 ms. Exact-match candidate: 59.33 FPS, 13 / 5, max 158.901 ms. No expensive exact-match hits are logged: large zero-upload refreshes change tile lists and therefore legitimately need new metadata. The exact-match optimization is correct in the synthetic fixtures but does not improve this workload.

Actual root: mapping-only refreshes reuse completed immutable pages yet submit an empty classic upload command buffer and wait on the CPU. New read-only mapping-only path keeps new resident metadata, all page references and Metal 4 queue signal/wait ordering; it skips the classic upload and CPU completion wait. Actual uploads and mutable GPU storage retain existing paths. Pending old-page uploads keep their already-enqueued queue dependency. Apple MTL4CommandQueue event contract checked against official documentation.

Regression: hold the classic upload queue while changed mappings reuse completed pages. Original blocks until a 3 s rescue, failing all four format/GOB cases. Fixed returns before rescue, then samples the changed mapping and retained old versions correctly. Empty atlas readbacks validate metadata with no physical pages. Full graphics suite passes again (`/tmp/mkw-map-only-graphics-suite.log`), including 1,500 sharing checks per encoding mode, shader-pull and TBDR. Focused async sharing remains 82/84; writable GPU aliases 286 per mode. Docs/clang-tidy/cross-title blockers unchanged.

Final candidate: external `dmhost-sparse-map-only-20261109`, fingerprint `sparse-map-only-20261109-build.json`. Replay `stability-map-only-20261109-174248`, PID 31355, session 76282: completes 210 s, exit 0, no logged GPU execution error/crash, frames 5400/9000 road/scenery complete, HUD enabled. 22 mapping-only refreshes logged. Race window: 59.62 FPS; 7 >50 ms, 2 >100 ms; max 133.298 ms; p95 18.338 / p99 21.828 ms. Baseline p95 18.121 / p99 22.003. Peak 10,904 MiB (11.43 GB) vs baseline 10,924 (11.45): no demonstrated RAM saving. Individual NPC trajectories differ; average FPS improvement/general stutter elimination unproven. Six remaining >50 ms frames cluster at actual uploads, with CPU page checking still costly.

All owned runs stopped. Comparison evidence and validation logs preserved externally. No shared host replacement or commits. Bounded Mac checkpoint is complete; overall RAM/stall investigation remains open. Next useful Android milestone: actual task/mesh rendering and compressed-texture allocation/readback proof on the target device, using this Mac renderer as the correctness reference. Vulkan RAM savings remain unmeasured; current Adreno sparse format/alias limits require a separate storage design.

## Existing evidence

opening-terrain-correct-20261109-153351 (no automatic menu input): 30 s footprint 8,548 MiB; 599 s 11,421; 1,200 s 14,677; 2,241 s 16,302. Guest charged grows 4,945→8,477 MiB; ordinary host heap 766→1,036; GPU-attributed VM 279→451; unattributed/private GPU 1,624→5,342. Device logical allocation reaches 18,178 MiB. No logged GPU error/assertion; the process ended without an identified exit reason. At end: 9,094 serial objects, 303 aliases, ghost table capped at 512; no freed-but-alive pool buffers. This argues against declaring a fixed memory floor or blaming all growth on malloc.

## Baseline and validation

Accepted exact binary: /Volumes/Data/Switch/Mario Kart World/0400C3F00006E000-work/dmhost-streamed-terrain-fixed-20261109. Shader chain cb0cf4544169, inputs 9286520fae55. Isolated rebuild argv /tmp/mkw-stream-fixed-build-argv.json, frozen FS /tmp/mkw-isolated-hle_sf.c. Prior graphics suite 101 executables passes; terrain fix confirmed by user. Five-title harness blocked by four missing packaged builds; clang-tidy/Python lint deps absent; three pre-existing docs failures.


## Android follow-up checkpoint (2026-11-09)

Latest: [mkw-android-implicit.md](mkw-android-implicit.md). Implicit sampling/LOD queries pass 2166 GPU checks. All 2417 eligible real programs convert/validate/device-load with 6579 atlas bindings. Retaining fragment functions cuts the real bundle719.5→288.1 MiB and module-loading peak RSS2.196→0.933 GiB, with no game working set allocated. Explicit-atlas preparation remains about 2.16/2.61 ms at 40 MiB peak. Offset/gather and actual attachments precede a game scene. No full-game RAM/FPS result;9–10 GB remains open.

Latest (2026-11-10): [mkw-android-interfaces.md](mkw-android-interfaces.md). All11,603 real programs build/validate/device-load after repairing40padded vertex modules. Twelve observed native stage combinations compile. The same binary passes102driver/856atlas/120terrain/10draw checks. Implicit atlas sampling/LOD queries, then offset/gather and actual attachment coverage precede a rendered scene. No new game RAM/FPS result;9–10GBremains open.

Current: [mkw-android-driver-state.md](mkw-android-driver-state.md). Push/c24/direct/indirect dispatch and high uniform slots pass 102 GPU checks including formatless image read/write. All755 selected real programs build/validate/load after correcting missing formatless image capabilities in239. The same binary retains856atlas/120terrain/9draw passes and40MiB atlas peak; steady refresh timing is unchanged. First-use samples/process HWM are higher and documented, with no new performance claim. Actual sampling/stage interfaces precede a rendered Android scene; full-game RAM/FPS and9–10GB remain open.

Latest measured iteration: [mkw-android-measurements.md](mkw-android-measurements.md). In a bounded offscreen workload, atlas refresh preparation falls from about10.2/10.7ms to2.17/2.61ms, native atlas allocation peak76to40MiB, and process teardown high-water170–172to141–143MiB after chunked pool restoration. Persistent working-set/full-game RAM savings remain unproven;9–10GBtarget remains open. Final856atlas/120terrain/9draw checks pass.

Latest: [mkw-android-terrain.md](mkw-android-terrain.md) closes the tested Vulkan CPU-streamed terrain gap:120checks pass, including540800real height texels matching Mac GPU captures and64shader fetch samples. GPU ownership and pool cleanup are checked. The same binary retains700atlas/9draw passes. Full Android game RAM/FPS and9–10GB remain unmeasured/open; next are the remaining shader/driver interfaces before a bounded scene.

Earlier: [mkw-android-mapped-atlas.md](mkw-android-mapped-atlas.md). Production task/mesh replay passes nine device draw checks; all26real modules build/load with four atlas-aware texture bindings. Actual NVN mapped compressed sampling passes700GPU checks, including in-flight versions, growth, replacement and eviction/reload. The thin fixture's20MiB cache/staging is not a game memory estimate. Remaining shader/terrain/rendering coverage precedes an Android profile and bounded game scene. The full Android game and its RAM/FPS remain unmeasured. The Mac baseline and9–10GB overall target remain unchanged/open. Earlier22-check storage prototype is historical evidence.

Latest: [mkw-android-offset.md](mkw-android-offset.md). Offset/gather and recorded attachments now pass. Next establish a bounded Android scene with the overlay and real startup/memory/frame-stall measurements. The 9–10 GB target remains open.
