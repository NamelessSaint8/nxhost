---
status: resolved
trigger: "Keep going and get measurements so we can improve and optimize."
created: 2026-11-09
updated: 2026-11-09
---

## Measured iteration achieved

Added repeatable offscreen Android measurements, reduced measured CPU refresh cost and transient allocations, and fixed a newly exposed texture-version lifetime bug. A second measured change bounds zero-copy pool restoration scratch and lowers process teardown high-water memory. This is a bounded backend workload, not an Android game scene. Full-game RAM/FPS and the 9–10 GB target remain open.

No agents, commit, installed app, global Android setting, Mac profile/host/overlay change. Shared dmhost and unrelated/OOT work are preserved. Only owned temporary device executables were used; game-derived captures and evidence remain external.

## Workload and instrumentation

- Lenovo TB323FU / Adreno840, API36, Vulkan1.4.295, driver2c410f6f5c. NDK28.2.13676358/API31. Build /tmp/nxhost-android-measure-runtime; fixture /tmp/nvn2-measure-shaders; device /data/local/tmp/nxhost-mkw-measure-20261109.
- Native BC6H logical storage6,087,507,968 bytes (8192²×68 layers,12mips);512 distinct64KiB cells mapped,30 extra source cells,35,520,512 source bytes. Synthetic patterns deliberately have distinct compressed bytes. Four sampling/query operations per job with expected values checked. Serialized submissions wait for completion; no FPS inferred.
- New probes/vknvn2_measure.inc, CLI --measure: first-use job,60 unchanged jobs,30 reuse remaps,30 new-content jobs. Per-row wall/thread CPU preparation, begin/submit/wait, valid-bit-masked main GPU timestamps, process RSS/HWM/PSS/SwapPSS, native atlas allocation current/peak, uploads, metadata and cell reuses. Source setup and cleanup are separate comments. GPU timestamps exclude private transfer submissions; CPU preparation wall includes synchronous transfer waits. Process counters and Vulkan allocation sizes are distinct, never additive.
- New summarize_nvn2_measure.py validates finite counters, workload equality, ordered phases/iterations and completed cleanup; excludes first10 unchanged jobs and keeps per-run medians/p95. Formal order baseline4,candidate4,candidate5,baseline5; two fresh processes per version. Exact raw CSVs, logs, executable hashes and comparison JSON archived. Earlier pilot/atlas-only measurements retained separately, not mixed into final table.

## Root causes and fixes

- Atlas plan loops recomputed native mip layouts for every logical cell, including holes. Hoisted offsets once per mip/pass and skipped second-pass work for nonpending cells.
- Capacity planning retained old CPU-plan references and treated each pending cell as additional storage. Replacement plans retain unchanged references, then drop old CPU references; completed zero-reference cells can be reused while GPU fence holds protect in-flight cells. This avoids an unnecessary image layer and old/new growth overlap in the measured case.
- Cell fences were assigned only once per submission. New cells from a later metadata revision in the same unsubmitted batch lacked that hold, sometimes hidden by image growth. Every referenced revision now tags its cells. Expanded regression proves this: original baseline fails24/856; optimized candidate with only revision tagging removed fails64/856; corrected candidate passes856/856.
- Atlas memory accounting now records allocation at vkAllocateMemory time, before retiring old backing, so the high-water counter includes transient old/new image overlap and staging.
- pool_copy_back duplicated an entire imported pool (up to256MiB per chunk) in malloc memory before restoring anonymous pages. Allocation failure silently discarded bytes. It now restores page-aligned64KiB chunks and explicitly stops on allocation/mapping failure. Whole-source/output hashes verify preservation, including GPU writes.

## Final measurements

Two per-run median ranges, same workload/data/fixture:

| Metric | Baseline | Candidate |
|---|---:|---:|
| Remap CPU preparation |10.199–10.221ms|2.166–2.167ms|
| New-content CPU preparation |10.653–10.670ms|2.608–2.609ms|
| Unchanged CPU preparation |0.0499–0.0500ms|0.0500–0.0502ms|
| Atlas image/staging peak |76MiB|40MiB|
| Retained atlas after remaps |44MiB|40MiB|
| Process VmHWM incl. teardown |170.26–171.97MiB|141.00–142.60MiB|
| Sampled during-job PSS peak |67.28–67.40MiB|67.28–69.29MiB|
| Pool cleanup wall |11.69–11.99ms|8.14–8.15ms|

About79%/75.5% lower changed-atlas preparation. GPU main sampling remains about0.008ms. No persistent process-memory reduction is established; VmHWM improves during teardown. First-use samples include shader/driver cache effects and are not game startup benchmarks. Every unchanged/remap job uploads0compressed bytes; each new-content job65536bytes. Metadata373296bytes/job in both versions. Source setup excluded from preparation; complete teardown included in HWM. Peak reductions are not estimates of full-game savings.

## Accepted checks and artifacts

- Final same executable:856atlas,120terrain,9draw checks pass; the terrain suite still matches540800 actual Mac height texels and64shader samples.
- --restore-check passes five pool sizes:4096,61440,65536,69632,135168 bytes on this4KiB-page device; CPU patterns plus GPU writes survive exact SHA256 comparison. Each measured run also preserves all35,520,512 source bytes and65536 GPU output bytes after pool restoration. Atlas backing returns to0after pool cleanup.
- All194 production Android sources compile; fixture-Wall-Werror. Eight Python shader tests, targeted Ruff0.15.13/repository config and git diff --check pass. Pinned0.17.2/Pyright ratchet and clang-tidy unavailable. SPIR-V validation and GPU readbacks pass, not an API-layer validation pass (shell loader still cannot discover Khronos layer).
- Five-title Mac preflight: MKW, TotK, Xenoblade3,13Sentinels,HadesII for large/imported/streamed pool behavior. Packaged builds absent; not a boot pass. No Mac renderer change. Docs retain three existing failures: missing0100005027A18000note, guide05length6242>6000, existing missing note/old Skyrim links. Symptom index760; no new link failures. No auto-review rejection.
- External evidence: /Volumes/Data/Switch/Mario Kart World/0400C3F00006E000-work/android-measure-20261109/. Exact baseline/candidate/no-revision controls, baseline atlas/core sources, control builder, CSVs/JSON, fixture bundle, full dependency/source hashes, generated headers, capture provenance and logs. Reproduction in probes/README.md#measured-android-atlas-refresh.

## Next work

Follow-up: [Android driver state](mkw-android-driver-state.md) fixes and GPU-checks push/c24/direct/indirect dispatch parity, high uniform slots and formatless image capabilities. Its fresh comparison retains steady atlas refresh costs and records higher first-use samples separately. No full Android game launched; android.tsv remains absent. Next cover actual sampling modes and mesh/fragment/typed-output interfaces before a bounded scene. Preserve full texture/terrain correctness while pursuing the memory goal.

Use the new measurements to compare representative real-data workloads and eventual game startup/steady play. The complete textured Mac renderer remains the visual/overlay reference; full-game target and broader stalls remain open in mkw-memory-growth.md.
