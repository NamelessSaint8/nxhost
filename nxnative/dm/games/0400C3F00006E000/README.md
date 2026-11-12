# Mario Kart World (Switch 2)

Split and shader-built from a loose dump of update 917504. Direct Mac host runs now reach the title, menus, Grand Prix movie and first race,
with textured gameplay verified on an M4 Max. This profile has provisional memory reservations and an experimental Android profile, but no registered `build` rows;
memory use, frame-time stalls and broader rendering validation remain open.

- Dump: `exefs/` (main 33.6 MB, sdk, subsdk0/1) + `romfs/` (22 GB), loose.
- Engine: Nintendo EPD's Nin_Ounce (sead / agl / gsys, Phive), SDK with NVN2; Ampere shaders.
- Shaders: 11,603 in [`shader_map.tsv`](shader_map.tsv), from `Shader/*.Nin_Ounce_NVN2.bfsha.zs` (BNSH), one `.sarc.zs` with agl `sharcb` packs,
  `Lib/agl/agl_resource.Nin_Ounce_NVN2.release.sarc` (BAHS packs, 3,924 of them), the effect set (`Effect/static.…esetb.byml.zs`, 1,017 compute
  programs) and the UI layouts.

## Android full-game bring-up (2026-11-10)

The O2 Android release preview **0.17** completes a three-lap Crown City race and reaches results on Lenovo TB323FU / Adreno 840 / Android 16. Checked captures show road, city scenery, riders and the race HUD without the earlier broad pink cast. Preview 0.14 previously completed Mario Bros. Circuit, then stopped late in its second Grand Prix race after stale command headers and an unsupported sampler binding. The [command-copy ownership fix](../../../docs/reference/nvn-objects.md#copied-command-streams-own-their-recorded-bytes) passes old/shallow/final GPU controls; those failure signatures do not recur in the current direct Crown City run. Different routes and broader renderer limits remain untested. Recurring stalls and the 9–10 GB target remain open. The accepted Mac renderer and overlay are preserved.

| Preview | Observed racing FPS | Result |
|---|---:|---|
| 0.6 | 4.2–4.4 | Memory guard at 950s |
| 0.7 | 5.2 | Stopped manually near low memory |
| 0.8 | 12–14 | Memory guard at 991s |
| 0.9 | About 12 | Textures preserved after paging; multi-second save batches and later memory pressure |
| 0.13 | No steady race sample | Thirty-minute run dominated by cold compilation |
| 0.14 | 12.0 across an early 430-second racing window; 16.1 in a later 100-second window | Completed Mario Bros. Circuit; stopped late in the second race |
| 0.17 | 12.0 across 300 seconds of Crown City; 13.6 in its later 100-second window | Completed all three laps and results; no fatal renderer stop or memory guard |

These are sampled on-screen results from actual races, not controlled identical camera paths. Preview 0.8 peaks at 6,600,262 KiB sampled TOTAL PSS; final swap PSS is 2,637,331 KiB, recorded separately. Preview 0.9 peaks at 7,142,125 KiB TOTAL PSS and reaches a transient low of 495,764 KiB system MemAvailable before manual stop. Vulkan allocation bytes overlap process accounting and exclude driver internals. The overlay keeps platform, FPS, frame interval, explicit Vulkan bytes, CPU RSS and available system memory visible.

Preview 0.17 runs for about 24 minutes across opening/menu navigation, Crown City and results; this is not 24 minutes of uninterrupted driving. Its 300-second race window (1000–1300 s) averages 12.01 FPS, with a 6.154 s maximum frame. The later 1200–1300 s window averages 13.56 FPS, with a 1.282 s maximum. These include first-use and streaming pauses; the instrumented run also enables focused binding diagnostics. The 90-second 1920×1200 H.264 POC retains the overlay, with actual variable capture timing and no audio.

The 278 Android memory samples peak at **8,019,806 KiB PSS (7.65 GiB / 8.21 GB)**. At that sample RSS is 5,415,242 KiB and swap PSS 2,700,286 KiB, recorded separately. Minimum system MemAvailable is 1,451,984 KiB; final availability is 2,323,396 KiB. There is no memory-guard stop. File-backed residency and swap mean this does not establish a universal 9–10 GB working-set ceiling. Fifty-five complete driver-cache writes total 35,988,622,619 bytes, making cache write amplification a measured next target alongside guest/streaming waits and first-use materials.

A follow-on source change uses [Vulkan cache-hit feedback](../../../docs/reference/shaders.md#vulkan-cache-hits-do-not-need-another-disk-snapshot) to skip disk snapshots when the supplied cache serves a pipeline. Cold and warm synthetic GPU replays pass; the warm run leaves its cache file unchanged. This change is not in preview 0.17, and its full-game write reduction remains unmeasured.

### Android frame-rate profiling (2026-11-10)

On a private 0.18 diagnostic build, the Crown City results screen was sampled on the Lenovo TB323FU / Adreno 840. The 3840×2160 source and 1920×1080 crop stayed fixed. Alternating native 3040×1904 and half-size 1520×952 **final presentation** windows saved about 0.16–0.17 ms of presentation GPU time at half size, but did not give a repeatable FPS gain: the two half-size windows measured 17.20 and 13.66 FPS against adjacent native windows of 14.24, 14.60 and 14.58 FPS. Their other game work varied. Reducing final presentation size alone is therefore not a supported performance setting for this scene.

In a subsequent Crown City VS race, with Peach parked near the starting bridge, the trace identified a 1248×700 color/depth pass with 817 draws and 231 shader pairs; an earlier unsplit race sample attributed about 32.3 ms median to this pass out of 45.3 ms median across measured passes. The existing opt-in Vulkan pass-split control ends and reloads long passes so earlier draw groups can be submitted while later groups are recorded. In alternating parked-race windows, unsplit presentation cadence was 17.43, 18.31 and 17.48 FPS; splitting at 256 draws gave 19.12 and 19.11 FPS in settled windows, and splitting at 128 draws gave 19.30 FPS. Median frame intervals were 54.73–56.62 ms in the later unsplit windows versus 51.88–52.18 ms with splitting. The second 256-draw interval **including** a 9.481 s console-transition stall was only 15.28 FPS; its separately reported settled portion was 19.11 FPS. GPU submission spans can contain CPU recording gaps and are not GPU-busy time.

The next test drove one Crown City VS race through parts of laps 1–3 on the same installed 0.18 diagnostic build. Cold unsplit driving gave 9.89 FPS over 103.1 s with heavy page faults. With 256-draw color/depth splitting, the entire 129.8 s window gave 11.80 FPS; its first 90.0 s gave 15.82 FPS, then a burst of malformed submission-copy records coincided with a 2.71 FPS final 39.8 s. After restoring both split controls to zero, warm unsplit driving gave 13.99 FPS over 109.0 s. The sampled split frames show city streets, elevated road, HUD and plausible depth, but do not establish pixel parity. Different course positions, traffic and streaming prevent attributing the 15.82 versus 13.99 FPS difference to splitting. Malformed records also occurred with splitting off, and an earlier unsplit 0.18 process crashed after similar records. The 0.18 race reached its results screen after the FPS sample; its final log, TSVs and screenshot were saved before replacement. Resolve the correctness fault and compare matched warm race scenes before promoting the opt-in control. Raw per-frame/presentation TSVs, logs, summaries and screenshots are in the external `0400C3F00006E000-work/android-game-20261110/android-fps-20261110/` folder. Preview 0.17 and its normal data pack remain unchanged.

The private 0.20 record-trace build completed a Crown City race without reproducing the malformed command record. A separate run with trace disabled aborted on a valid 2× directional anisotropic sampler in the compressed atlas; this sampler remains unsupported. An experimental implementation failed 72 of 366 focused dense-versus-atlas GPU comparisons and was not shipped. The 0.20 trace build was then used for a matched stationary Peach Beach VS A/B: settled unsplit gave 12.73 FPS over 49.7 s, while a second settled 256-draw depth-split window gave 13.06 FPS over 36.8 s; an earlier settled split window gave 12.03 FPS over 60.7 s with page faults. The complete transition windows included 9.8 s and 18.4 s stalls. A one-minute split-enabled drive showed moving shoreline, rider and HUD without an obvious depth failure, but does not establish pixel parity. The sampled trace log has no command-record fault. No repeatable split FPS improvement is established; both controls were restored to off. These timings include record-trace overhead and are not release FPS. Evidence and exact windows are in `android-fps-20261110/peach-trace-ab-20261110/`; the sampler study is in `android-fps-20261110/aniso-study-20261110/`.

A one-frame draw trace of that Peach Beach scene shows 473 draws in a 1248×700 depth pass, followed by 476 draws across 97 vertex/fragment pairs in the main 1248×700 scene pass. A nearby rolling GPU report attributes about 1.6 ms to the depth pass and 16.4 ms to the main pass, out of 34.4 ms summed across render passes per frame. These counts identify the main scene pass as the first GPU optimization target; they do not identify the most expensive shader pair. At this workload, 30 FPS requires reducing both GPU pass cost and the longer observed frame cadence; 60 FPS needs much larger changes. The one-frame log and parsed pair counts are archived with the Peach trace A/B evidence.

### Android atlas binding cost (2026-11-11)

A 0.20 one-frame trace at stationary Toad's Factory found 886 atlas-active draws among 975 main-scene draws. Its main 1248×700 pass was about 40–42 ms in nearby rolling GPU pass reports, with about 53–55 ms summed over render passes; these pass timestamps do not prove full-frame GPU occupancy because CPU submission gaps can occur between passes. The suggested `ff6ddbc333e4e2f0` shader had only dense sampled bindings in both the separate Peach Beach trace and its 21 Toad draws. The Toad trace instead identified fragment shader `db8851f37ecd07de` with atlas metadata on bindings 3, 6, 9 and 10.

The signed 0.21 diagnostic build adds `DM_VK_ATLAS_CENSUS_SHADER=<hex shader key>` and live `DM_VK_ATLAS_MUTE=<stage>:<hex shader key>:<binding>`. Mute substitutes a valid dummy dense view for one active atlas binding, yielding deliberately wrong pixels without allocating a dense copy of the sparse texture. It measures the effect of removing that binding's atlas sampling in the selected shader, not a general atlas speedup; individual deltas are not additive. The census confirmed all four bindings at runtime. Bindings 3, 9 and 10 are each 8192×8192×68 with 12 levels; binding 9 is BC6H. The driver's earlier dense requirement for this BC6H shape is about 5.8 GiB, so full dense upload is not a suitable assumption without a mapped-page census and memory budget.

At the same parked Toad camera, settled 400-presentation windows (console transitions excluded) gave 14.55 FPS before binding-3 mute, 15.16 muted, and 13.94 after restoration. Bindings 9, 10 and 6 gave 14.46, 14.20 and 14.25 FPS, with a later restored baseline of 14.29 FPS; none showed a clear gain. The session's changing lighting and frame-time drift limit precision. A separate native-filter A/B/A on the same 0.21 session gave 14.29 FPS with hardware bilinear enabled, 13.70 disabled, then 14.27 restored. Native filtering is beneficial by roughly 0.6 FPS here, not the missing factor of two. Android thermal status was 0 during the test. The app remains running with mute and census off and native filtering restored. Raw timing/log snapshots, the 0.21 package and a wrong-picture diagnostic screenshot are archived in `android-fps-20261110/atlas-mute-0.21-20261111/`.

The 0.22 diagnostic build extends mute to `DM_VK_ATLAS_MUTE=all` and adds `DM_VK_ATLAS_RESIDENCY=big`. At the same stationary Toad camera, the three 8192×8192×68 arrays have only 3,432/23,256, 13,592/92,888 and 3,432/23,256 mapped native pages (14.6–14.8%). Their packed images allocate 128, 132 and 44 MiB, respectively, after content deduplication; the BC6H array is the 132 MiB one. The mapped virtual pages are not the same as unique physical pages. A full dense image is therefore an unsuitable shortcut for these textures in this scene.

The settled 400-presentation A/B/A windows measured **13.64 FPS normal, 21.70 FPS with all active atlas bindings replaced by dummy dense views, and 14.18 FPS restored**. Nearby rolling reports put the main scene pass near 38.2, 11.2 and 37.5 ms, and the sum of render-pass spans near 51.5, 28.7 and 51.3 ms. The mute intentionally breaks materials, alpha and lighting, so its delta is an optimistic bound on removing atlas sampling, not a playable setting or a literal additive shader cost. Even that optimistic 21.7 FPS remains below the stable 30 FPS target. Replay still spends about 25–26 ms per frame on CPU, including about 15 ms building descriptor sets (about 11–12 ms collecting bindings); queue submission itself is below 0.2 ms. The next independent cost to investigate is repeated descriptor collection, while a correct shared atlas shader improvement addresses the main pass. Pass timestamp spans and the GPU timestamp span can include CPU gaps. Raw snapshots, APK, matching library, screenshots and exact window summary are archived in `android-fps-20261110/atlas-global-0.22-20261111/`.

The signed 0.23 build reuses the sampled texture's atlas metadata for its paired descriptor, avoiding a second atlas lookup and keeping both on one snapshot. It renders the Toad scene correctly. After an early 11.30 FPS window during scene settling, a later 400-presentation parked window recovered to **13.36 FPS**; the adjacent 600-frame reports show 2,625–2,663 draws, about **12.7–12.9 ms** collecting descriptors, and **15.9–16.2 ms** total descriptor-set work. This does **not** demonstrate a CPU or FPS improvement over the 0.22 return window (14.18 FPS, 11.5 ms collecting, 15.2 ms descriptor sets), though the runs have varying draw counts and are not a same-process A/B. The 0.23 tablet app is running with normal atlas rendering. APK, matching library, logs, screenshots and exact frame windows are in `android-fps-20261110/atlas-pair-0.23-20261111/`.

The shared shader helper now computes the logical mip extent once per filtered sample and passes it to native bilinear selection and fallback taps. Its rebuilt synthetic bundle passes **868 mapped, 2,166 implicit, 15,750 offset and 400 uncompressed atlas GPU checks**, all with zero failures on Adreno 840. Aggressive SPIR-V optimization of the two-binding implicit fixture yields 14,492 instructions versus 16,712 before. The helper source, fixture binaries and raw logs are archived in `android-fps-20261110/atlas-extent-hoist-20261111/`.

An alternate 1.8 GiB game shader bundle recompiles the 145 fragment programs covering 950/975 draws in the traced Toad main pass. All 11,603 keys remain, and only those 145 SPIR-V binaries differ from the original bundle: reflection and flags match exactly. With the same 0.23 renderer and parked Peach/Mach Rocket VS 150cc camera, settled 400-presentation windows measured **15.31 and 15.37 FPS** on the alternate bundle, **13.15 FPS** after restoring the original bundle, then **15.46 and 15.98 FPS** on an alternate-bundle repeat. The last clear-start-line reports have about 2,653 versus 2,679 draws, **41.74 versus 24.52 ms** in the main outdoor pass, and **55.29 versus 39.89 ms** summed across render passes (original versus alternate). The later original-bundle 23 FPS window is excluded because Peach had moved inside the factory. Cold shader compilation and loading transitions are excluded. This is evidence of a useful shader gain, but time of day, draw counts and device state are not locked by a frame replay, so the precise delta is not established. A large blue plane appeared briefly during the alternate repeat's race loading and cleared; its cause remains unknown. The exact bundles, manifest, logs, screenshots and window timings are in `android-fps-20261110/atlas-extent-game-20261111/`. The tablet has been restored to the original `shaders.dmsv`; the alternate 1.8 GiB copy was removed from it after archiving.

The atlas descriptor-set memo was then checked on the Lenovo tablet with `DM_VK_X_SETVERIFY=1`, first with the original shader bundle and then with the hoisted-helper bundle through Shy Guy Bazaar loading and racing. A diagnostic pass exposed raw `VkDescriptorImageInfo` padding in the descriptor hash: 29 of its first 32 warnings had identical image view, sampler and layout fields. Hashing those fields separately removed that false difference. With the corrected hash, the original bundle logged one sampled difference and the helper bundle 22. All 23 were dynamic-offset changes whose old and fresh 4 KiB scratch copies compared byte-for-byte equal; the original case also changed its scratch buffer handle and descriptor hash. No sampled binding, atlas mask, `um` mask or `im` mask changed. The earlier helper-bundle content warning for shader `e38a5d4d7d779895` was not sampled again, so that specific dependency remains open. The verifier now distinguishes byte-identical recopy events from real or unreadable content differences and names the binding when a difference is found. See [descriptor memo verification](../../../docs/reference/nvn-objects.md#vulkan-descriptor-memo-verification-compares-bound-bytes).

In one nearby helper race pair, a 600-frame memo-off report had 2,543 draws, 11.51 ms collecting and zero sets kept per stage; a memo-on report had 2,503 draws, 7.15 ms collecting and 2,124 kept per stage. These are moving race windows, so their 4.36 ms collecting difference is a sample, not a fixed per-frame gain or a matched FPS result. The final verifier reporting change passed an Android compile of 196 sources with zero failures and `git diff --check`; that reporting change was made after the tablet run and has not itself been rerun on-device. The diagnostic APK, helper copy and temporary controls were removed, and the restored 0.24 APK launched with the original external shader bundle and byte-identical original environment. Logs and screenshots for this check are in `android-fps-20261110/descriptor-memo-20261111/` on the external volume.

The late unsplit crash is symbolized against the exact installed 0.18 library (matching build ID `c3788da185abd99a`): `rec_flat+0x38` dereferenced a nested command-list jump target of `0x3f000000`. The trace depth was two calls. Other malformed records contain float-shaped or textual data instead of command headers. This locates the failure in command submission copying but does not identify who overwrote the list or link. The opt-in `DM_NVN_REC_TRACE=1` diagnostic APK, version 0.20, was installed over 0.18 with app data preserved. It records parent handles, jump source/target and host-segment ownership. A full Crown City 150cc VS race reached results without a malformed record or crash, and a second race toward Choco Mountain started cleanly. The intermittent overwrite is still unresolved. The trace perturbs timing, so 0.20 FPS readings are not an optimization comparison. Device evidence and the APK are archived in `android-fps-20261110/record-trace-0.20/`.

The release APK and linked data pack live in the external `android-game-20261110/android-preview` work folder. Four Android-rewritten modules, the 23,512,391,287-byte indexed RomFS and 11,603 shader programs retain the original main build ID. The latest shader bundle keeps every program, reflection record and nonfragment binary, including all 168 compute programs lowered to the device's workgroup-storage limit. The normal data pack includes the checked memory settings, current shader bundle and prepared cache for the tested GPU/driver. The standard installer and a separate 180-second production opening/title launch pass with the normal internal save and no diagnostic switches; five data-pack tests pass in Python 3.13.5. Live full prewarm remains disabled so its full set of pipeline objects is not retained during play. Diagnostic runs use an isolated copy of the accepted save; the production pack contains no test save, watchdog or profiler.

The main reductions are [first-binding buffer allocation](../../../docs/reference/memory.md#cached-cpu-pools-allocate-gpu-buffers-at-first-binding), [file-backed canonical CPU storage](../../../docs/reference/memory.md#canonical-cpu-texture-storage-can-use-file-backing-on-android), [versioned descriptor checks](../../../docs/reference/nvn-objects.md#vulkan-atlas-descriptor-checks-reuse-unchanged-page-versions) and [GPU ownership queries](../../../docs/reference/nvn-objects.md#gpu-image-ownership-queries-cache-versioned-storage-ranges). Actual sparse physical pages feed compressed atlases for both array and plain 2D sampling. Unused copied buffers no longer serialize unrelated submissions.

Preview 0.12 adds [lossless inactive-image retention](../../../docs/reference/memory.md#inactive-gpu-images-retain-pixels-in-private-file-storage) and [hardware filtering within atlas tiles](../../../docs/reference/rendering.md#vulkan-atlas-interiors-use-native-bilinear-filtering). GPU-written images save every subresource before releasing storage; inactive CPU-backed copies rebuild from canonical bytes. Cleanup spreads across presents at whole-image boundaries. Idle time also uses a five-second monotonic threshold during slow loading; completed fences and current-frame protection still govern retirement. Tile edges, holes and wrap/clamp cases retain manual filtering. The related suites pass 23,191 GPU checks with Khronos validation active and zero API errors. Twenty-five Android Python tests pass. These checks establish correctness of the covered paths, not full-game performance.

Cold shader rebuilding exposed a diagnostic false stall before the first frame. [Completed pipeline builds now count as watchdog progress](../../../docs/reference/shaders.md#completed-pipeline-builds-count-as-watchdog-progress), preserving frame/tick counters and the original inactivity threshold. Two process checks verify both continued work and a real stall.

Writable sparse depth/color images still use dense compatibility storage. A later remap of GPU-written sparse storage stops explicitly until physical tile coherence is implemented. First-use material compilation and broader course validation also remain open. Earlier GPU losses have not been established as fixed by the framebuffer and interface corrections alone.

## Mac stability pass (2026-11-09)

The agreed next milestone is a bounded Mac stability pass before Android: complete checked scenes, memory that levels off, and fewer recurring
stalls. The exact 9–10 GB target remains open and is not a prerequisite to starting Android. Preserve the platform/measurement HUD and the
accepted CPU-streamed terrain fixes. Allocation diagnostics and concurrent compilation perturb timing; their runs are memory/ownership
evidence rather than controlled FPS benchmarks.

`stability-baseline-20261109-165657` uses the unchanged accepted binary, copied save and recorded Grand Prix entry/acceleration inputs.
It completes **1,801 seconds**, spanning the opening/menus, first race/results and the transition/race into Crown City. Parked results phases
are included; this is not thirty minutes of uninterrupted driving. Checked captures show textured road and scenery on both courses. The
driver stops its own process at the checkpoint (exit 0); no GPU execution error or crash is logged.

First course/results footprint stays near **11,200 MiB / 11.74 GB**. Streaming the second course raises the peak to **12,558 MiB / 13.17 GB**;
the final reading is 12,544 MiB. The final five minutes range from 12,466 to 12,558 MiB, with guest charged memory steady near 7,051 MiB.
This supports course-specific working sets that settle after streaming, not an all-world plateau, a fixed RAM floor or the 9–10 GB target.
Metal's logical allocation is recorded separately and must not be added to process footprint. JSON summaries, input events, screenshots,
copied-save provenance and the exact accepted host are retained externally.

An isolated candidate `dmhost-sparse-unchanged-20261109` avoids redundant sparse mapping/submission work only when every immutable tile/page
remains identical; it does not evict resources or change compression. The full graphics suite and its shader-pull/TBDR checks pass. Additional
immutable-sharing async fixtures pass 82 normal / 84 dropped-upload checks per encoding mode under API/shader validation, including an
unchanged pending upload and staging-budget release. See [Unchanged sparse refreshes retain their metadata](../../../docs/reference/rendering.md#unchanged-sparse-refreshes-retain-their-metadata).
The sequential timing comparison `stability-compare-20261109-172737` uses the same copied save, recipe seed and input sequence, with allocation
census and API/shader validation disabled on both sides. In the 85–204 s race window, baseline averages 59.43 FPS with 11 frames >50 ms and
a 152.3 ms maximum; the exact-match candidate averages 59.33 FPS with 13 frames >50 ms and a 158.9 ms maximum. NPC trajectories differ,
so these are individual samples rather than a matched FPS benchmark. The candidate logs no expensive exact-match hits. The large zero-upload
refreshes change tile lists, so their new mappings still require metadata; their empty classic upload submission/completion wait remains.

`dmhost-sparse-map-only-20261109` additionally removes that empty submission/CPU wait for read-only mapping-only refreshes, preserving GPU
event ordering, resident metadata, existing pages and pending-upload dependencies. The held-upload-queue regression fails four cases before
the change and passes afterward. The full graphics suite, shader-pull/TBDR checks and focused sharing/async failure recovery/writable-image
checks pass in both encoding modes. The final sharing fixture includes 1,500 checks per mode, including empty metadata and zero GPU reads
after every tile unmaps. See [Sparse mapping-only refreshes skip empty upload submissions](../../../docs/reference/rendering.md#sparse-mapping-only-refreshes-skip-empty-upload-submissions).

`stability-map-only-20261109-174248` replays the same 210 s route after builds finish. It exits 0, with textured road/scenery at race frames 5400
and 9000, no logged GPU execution error/crash and 22 logged mapping-only refreshes. Its 85–204 s race window averages **59.62 FPS**, with
**7 frames >50 ms / 2 >100 ms / maximum 133.3 ms**, against the recorded baseline's **59.43 FPS / 11 / 4 / 152.3 ms**. Frame p99 is
21.83 vs 22.00 ms; p95 is 18.34 vs 18.12 ms. This is one sample per configuration with different NPC trajectories, so it does not establish
a general FPS gain or eliminate stalls. Six remaining >50 ms frames cluster around actual tile uploads; CPU page scanning remains costly.
The short candidate peaks at **10,904 MiB / 11.43 GB**, against baseline 10,924 MiB / 11.45 GB: this does not establish a RAM saving.
The thirty-minute run is the unchanged rendering baseline; the final optimization has the shorter replay and synthetic validation.
`comparison-summary.json`, per-frame TSVs, memory summaries, scripts, exact candidate/fingerprint and validation logs remain external.
HUD remains enabled. Shared `dmhost` is not replaced. The diagnostic thirty-minute RAM sample includes Metal API validation overhead;
the separate short first-course samples have validation disabled. The five-title boot harness remains blocked by four missing packaged builds;
clang-tidy is unavailable. Documentation checks retain the three pre-existing failures and no new broken links.

## CPU-streamed terrain tiles (2026-11-09)

**Fixed in the checked opening scenes:** missing road/ground and scenery came from CPU-filled terrain tiles staying empty on the GPU. This is
independent of the RAM reductions: a dense run around 25 GB failed too. GPU-ordered snapshots in `opening-height-history-20261109-151737`
show eight actual 260×260 R16Unorm height textures containing only zeros, while their 152,064-byte block-linear backing contains about
135,000 nonzero bytes each. They have `MINIMAL_LAYOUT`, no packaged layout, and reside in a `CPU_CACHED | GPU_CACHED` pool (`0x24`).

The profile now enables the existing `tex_flush_upload` and `tex_dirty_upload` mechanisms. Tracking alone restored seven of eight captured tiles
in one run; separate locations/runs are not a matched benchmark. Two shared gaps are also fixed: initial uncompressed content filled before
texture initialization is admitted by the CPU-stream profile, and render-target capability no longer suppresses later CPU fills before actual
GPU render/copy use. See [CPU-streamed uncompressed textures](../../../docs/reference/nvn-objects.md#cpu-streamed-uncompressed-textures).

`opening-stream-initial-fixed-20261109-153020` uses the complete candidate with normal materials, depth and culling, with the HUD retained.
All eight sampled GPU height tiles now contain 67,600 nonzero texels each, with varied height values. Frames 900 and 1800 show textured road,
terrain and scenery where earlier runs had a blank plane. The bounded probes and their derived files remain in the external work folder;
no probe overrides or shader-color changes are part of the production renderer. The clean exact binary is saved as
`0400C3F00006E000-work/dmhost-streamed-terrain-fixed-20261109`, with build fingerprint `streamed-terrain-fixed-20261109-build.json`.
Its `opening-terrain-correct-20261109-153351` run remains available with the HUD; the user confirms that the road, terrain and scenery look complete.

Focused validation: `t_cpu_tex --metal` passes 75 checks in each encoding mode under Metal API/shader validation, including initial/late CPU
fills, actual GPU target preservation and view/upgrade ownership. The full graphics suite also passes, including 228 NVN API checks and the
shader-pull/TBDR checks. Its API fixture now gives 1280×720 swapchain textures a correctly sized GPU-only pool, rather than the reused 1 MiB
command/data pool; CPU-stream tracking exposed that invalid fixture. Two profile checks pass. The five-title harness was attempted for MKW,
TotK, FINAL FANTASY TACTICS, Great Ace Attorney and Skyrim (CPU streams, targets and aliases); four absent packaged Mac builds block it.
Documentation checks retain three pre-existing failures (missing game note, guide length and old Skyrim links); generated indexes are current.
The clean run has no GPU execution error or assertion in the checked log. The capture helper stalled before ScreenCaptureKit content enumeration
completed and produced no new video; its stuck processes were stopped, while screenshots and logs are preserved.
The 9–10 GB target, streaming/shader stalls and collision slowdowns remain open; no new performance or RAM claim follows from these diagnostics.

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
the synthetic benchmark and validation logs preserve all five experiments. The run log stamps the correct MKW profile, but a later audit found
that the shared build output had replaced the archived `dmhost-copy-loop-20261109` with an Ocarina of Time-profile binary; it cannot reproduce this recording. Both
startup prewarm and validation are off during gameplay, the HUD and phase timing are on, and each run uses a copied save. A separate final
check of the synchronous default passes another 410 sparse GPU checks.

**Current: normal preparation and shader publication (2026-11-09).** A shared-path audit excludes `stalls-20261109-normal-prepare` and
`stalls-20261109-prepared-baseline` from MKW comparisons: both identify Ocarina of Time profile `0400486024DEC000`. Earlier streaming run logs,
including `copy-loop`, identify the correct MKW profile. The new `stalls-20261109-prepared-fixed` run uses profile `0400C3F00006E000` and the
saved `dmhost-prepared-20261109` executable; its replay script names that saved binary rather than the shared build output.

Normal startup prepares the 11,873-row device list in 9.30 seconds: 6,249 shaders, 5,431 render pipelines and 193 compute pipelines, with no
new pulling bases compiled. No libraries or pipelines compile synchronously on the render thread through frame 8400. Review found that
publishing these ready shaders did not update program-prefetch deduplication, allowing a later program creation to prepare them again. See
[Published startup shaders were loaded again at program creation](../../../docs/reference/shaders.md#published-startup-shaders-were-loaded-again-at-program-creation).
The fix passes 123 synthetic checks through each real Metal compiler path, including GPU pixels, prepared S/R/C publication and an unprepared
prefetch control; all three prepared-program cases reloaded a library before the fix and none does after it.

The correct-profile run exits gracefully at frame 8400 without GPU execution errors and peaks at **13,341 MiB / 13.99 GB app footprint**.
Its 31.01-second `Mario-Kart-World-prepared.mp4` preserves the platform/resolution/FPS/GPU/app-memory overlay and corrected materials; checked
frames at 5 / 20 seconds read 50.44 / 58.06 FPS, 13.97 / 13.98 GB app memory and 5.83 / 6.71 ms GPU time. The user confirmed a concurrent
Ocarina of Time build on this machine: these samples establish rendering and stability, not an FPS or RAM improvement. Whole-frame pauses
remain, including a 368 ms frame with 7.8 ms submission, 8.5 ms GPU time and no uploads or compilation; an idle-machine pacing measurement is
still needed. `measurements.json`, `host-profile-audit.json`, proof images, scripts and validation logs preserve the result. The shader chain and
profile inputs remain unchanged. The five-game harness preflight is blocked by four missing packaged Mac builds; clang-tidy is not installed.
The graphics run completes all 101 test executables and the pull/TBDR Python checks after repairing a stale depth-eligibility texture mock's
missing `pixelFormat` property. The symptom-index/gallery checks pass; the full documentation suite retains its four unrelated existing failures.

**Current: lower-RAM compiler-cache configuration (2026-11-09).** The fresh `ram-20261109-census` run peaks at 13,457 MiB / 14.11 GB app
footprint. Its heap snapshot includes 1,230,800,752 bytes of `NSConcreteData` storage and 307 archive objects. An isolated compaction copy
successfully writes 4,810 bases into one 251.7 MiB file and removes 290 old files, but the archive-only restart still costs about 960 MiB.
The original cache and its crash-recovery marker are untouched. Releasing 6,217 shader argument encoders in an isolated real-library probe
changes no measured footprint, so that change is not adopted.

A bounded archive-handle prototype passes 31 real Metal/GPU checks, but the gameplay heap retains 1,222,379,376 bytes of `NSConcreteData`
despite only 114 archive objects. Later lookups grow malloc use and the run reaches 15.82 GB before it is stopped; the prototype is removed
from production source. A lower retained-handle counter is not a RAM saving. See
[Pipeline archive imports retain substantial host file data](../../../docs/reference/memory.md#pipeline-archive-imports-retain-substantial-host-file-data).

The separate `ram-20261109-compiler-cache` run uses the saved correct-profile `dmhost-prepared-20261109` with **`DM_PSO_ARCHIVE=off`**, retaining
normal manifest preparation. It peaks at **12,426 MiB / 13.03 GB app footprint**, versus 13.99 GB in the previous correct-profile prepared run
and 14.11 GB in the new allocation census. Host malloc charge at the end is 756 MiB versus 2,137 MiB in the census; Metal allocation grows,
so only the measured app-footprint change is counted. Preparation takes 20.24 seconds versus the census's 7.25 seconds; 4,817 bases go through
the compiler API before the first frame instead of coming from app archives. The run ends gracefully at frame 8400 without GPU execution
errors, with no synchronous library or pipeline builds in its logged race windows. This is an optional RAM/startup tradeoff, not a profile or
global-default change; future courses with keys outside the saved list remain unchecked.

Its 30.87-second `Mario-Kart-World-compiler-cache.mp4` keeps the overlay and corrected materials. At 5 / 20 seconds the HUD reads 12.91 / 13.02 GB
app memory, 13.68 / 13.77 GB Metal allocation, 44.76 / 53.83 FPS and 4.20 / 4.42 ms GPU time. These are different gameplay windows on the shared
machine, not an FPS comparison; frame-pacing stalls remain. Scripts, heap snapshots, videos, proof images and `measurements.json` preserve the
experiments. The 9–10 GB target remains unproven; remaining large candidates are guest/GPU backing duplication and driver/pipeline storage.

**Current: identical immutable sparse contents (2026-11-09).** The user prefers longer startup to lower steady RAM. The archive-off configuration above
remains the starting point. Switching the entire pipeline to `MTLDevice` (`ram-20261109-whole-pipeline`) peaks at 12,356 MiB / 12.96 GB,
which does not establish a meaningful additional saving. A physical-page-identity cache (`ram-20261109-ro-share`) finds no extra reuse and is
superseded by exact-content sharing. Both retain normal preparation and reach frame 8400.

The opt-in **`DM_NVN_SPARSE_RO_SHARE=1`** mode shares immutable 64 KB tiles with identical source bytes and decode layouts, including duplicates
within one texture and across distinct source allocations. The corrected `ram-20261109-content-final` run uses frozen
`dmhost-content-final-20261109`, `DM_PSO_ARCHIVE=off`, normal preparation and synchronous sparse transfers. It peaks at **10,941 MiB / 11.47 GB
app footprint**, versus 13.03 GB in the archive-off reference: about **1.56 GB lower measured peak**. It logs 28,714 content-reuse events, reaches
frame 8400 and exits gracefully without GPU execution errors. Event counts are cumulative and are not a live-memory total. Shader chain
`4af3b2a70fef` and profile inputs `9286520fae55` are unchanged. The isolated build uses the saved earlier `hle_sf.c` so concurrent OOT work is
excluded; its exact source is preserved with the proof. The shared `dmhost` path is not used.

A pixel regression found that direct buffer-to-texture copies mutated shared immutable pages. The fix persists CPU buffer bytes in canonical
physical storage and queues an ordered buffer readback for GPU-written sources before sampling a new version. The test fails 21 checks before
the fix and passes afterward; all 5,120 focused checks pass with content sharing enabled. The earlier `ram-20261109-content-share` run's
11.55 GB result predates this correction and is provisional. See
[Identical immutable sparse tiles share physical backing](../../../docs/reference/rendering.md#identical-immutable-sparse-tiles-share-physical-backing)
and [Copies into sparse textures persist in physical storage](../../../docs/reference/rendering.md#copies-into-sparse-textures-persist-in-physical-storage).

The final run's screenshots retain textured road, scenery and characters without the broad pink cast in the checked frames. Its automatic
ScreenCaptureKit recording failed on the first sample; a separate proof capture is recorded below. Warm OS compiler caches reduce this run's
preparation to 0.78 seconds, so it is not a cold-start comparison. The earlier 20.24-second archive-off preparation establishes the startup
tradeoff; no FPS improvement is inferred from different events on a shared machine. The mode remains opt-in pending broader game checks.
The full graphics suite passes all 101 executable targets plus the Python pull/TBDR checks. The final run still logs six race frames over
100 ms: the longest is 347.5 ms, including 329.9 ms compiling three previously unseen pipelines; other pauses include sparse gather/upload
work. Those three recipes are recorded in its user list for preparation on the next launch. The memory saving does not resolve all stalls.

The repeat `ram-20261109-content-proof-awake` run peaks at **10,681 MiB / 11.20 GB**, reaches frame 8400 and exits without GPU execution
errors. Holding the display awake restores ScreenCaptureKit samples; `record-window.swift` writes 1,586 frames through AVAssetWriter into
the 30.18-second `Mario-Kart-World-content-final.mp4` (1280×752, silent H.264). The platform/resolution/memory/GPU overlay is preserved.
At 5 / 20 seconds it reports 11.10 / 11.19 GB app memory, 11.73 / 12.09 GB Metal allocation and 7.84 / 7.12 ms GPU time. Its Apple HUD FPS
field reports `inf` and zero frame interval: that field and its flat graph are invalid. Host five-second windows around the capture range
from 53.9 to 60.3 FPS; four logged race frames still exceed 100 ms (worst 141.0 ms). This is not a controlled FPS comparison. Proof PNGs,
`measurements.json`, the exact capture script and a timestamped fresh-save `run-proof.py` are preserved. The repeat launcher uses a merged
11,951-row recipe seed from correct-profile, same-chain runs; that merged seed is prepared for the next run, not independently boot-tested.

**Experimental: GPU-only sampled sparse targets (2026-11-09).** A follow-up heap census totals 688.5 MB of host allocations. A packaged-texture
census finds only about 1 MiB of identical dense uploaded contents and no spare textures; neither suggests a large cache-eviction win. An isolated
pipeline-lifetime probe stays at 266.5 MiB after dropping base handles and replacing the compiler, and falls to 233.9 MiB only after dropping all
specializations. These diagnostics do not justify evicting live pipelines and adding race-time compilation.

The allocation trace instead finds atlas serial 32882, RGBA8 SNORM, 6144×6144×2 with four mips, becoming a 389.5 MiB dense texture when attached
as a render target. The rejected zero-`ClearTexture` experiment never handles this transition and is removed. Experimental
**`DM_NVN_SPARSE_GPU_SAMPLED=1`** retains eligible sampled GPU-only textures on mutable sparse physical pages from first use. This atlas's
3,060 mapped tiles refer to 765 distinct physical tiles, about 47.8 MiB of backing. See
[GPU-only sampled sparse textures can become render targets](../../../docs/reference/rendering.md#gpu-only-sampled-sparse-textures-can-become-render-targets).
The `ram-20261109-sampled-target` run, frozen `dmhost-sampled-target-20261109`, peaks at **10,520 MiB / 11.03 GB**, reaches frame 8400 and
exits without GPU execution errors. It preserves a 30-second gameplay video and textured race captures. This differs from earlier gameplay
windows and is not a controlled app-RAM or FPS comparison. The mode defaults off: the user's report of missing content in the opening before
the menus remains an acceptance issue. Keep the earlier 11.20–11.47 GB configuration as the accepted reference.

**Open: opening-scene content and HUD timing.** Separate no-input opening captures from the reference and experimental hosts choose different
locations, so their images cannot attribute missing scenery to this change. Both report the same 19 unavailable shader keys; build records
identify unsupported task/mesh programs (`ISBERD`/`ISBEWR`), a confirmed pre-existing rendering gap. The connection to each visibly missing
object remains unproven. Fixed-clock trials stall after the first present and are excluded; an entropy-only diagnostic still chooses different
locations and is not a matched comparison. The HUD's `inf`/zero-interval fault also remains open. Small standalone presentation probes show
finite frame timing with classic Metal, Metal 4, a display link and reused command buffers, so those features alone do not explain the fault.
The user's later live screenshots have finite 59.88 / 44.58 FPS and 16.70 / 22.43 ms intervals; the earlier `inf` fault is intermittent rather
than present in every run.

**Confirmed missing rendering path: live opening inspection (2026-11-09).** In `opening-live-20261109-123016`, the user identifies major absent
road surfaces and off-road scenery, especially the haunted mansion scene. The reference `opening-reference-live-20261109-123441`, with the
sampled-target experiment disabled, has the same failure; `baseline-diagnostic.png` shows the kart above absent road/terrain. The user independently
confirms the reference looks about the same. Its frame 3295 trace has 1,450 ordinary draw-entry records, all with loaded vertex shaders and no
rejected render pipelines. That does not rule out mesh draws: those calls never enter the ordinary replay trace.

The dense comparison `opening-dense-live-20261109-123718` uses the frozen content-final host with both native sparse allocation and immutable
tile sharing disabled. `frame-900.png`, `dense-current.png` and `dense-failed-diagnostic.png` still show major missing road/ground surfaces; the
user confirms the failure at about 25 GB app RAM. These are different opening locations, so this is not a pixel-matched regression comparison,
but the missing-surface failure persists without the native sparse allocation paths. It does not establish a RAM floor or justify discarding
the measured sparse memory savings. Earlier race captures establish only those captured racing scenes, not complete opening rendering.

The isolated `opening-mesh-probe-20261109-124252` logs program keys at binding and the existing unsupported mesh calls without changing their
rendering behavior. It records approximately **85 `nvnCommandBufferDrawMeshTasks` calls per steady frame**, with raw arguments 0 / 1. Actual
calls bind fragment `1e3e40ea043238db`, task `6098504f5d12ea03` and mesh `1de24686294997d8`; another program binds fragment `3cafb02cdf0d87fb`
and task/mesh-stage key `11ed01f0618a65a3`. The active cache's build records reject the latter stage programs on `ISBEWR`. Thus these programs
are used for actual mesh work, not merely requested by prefetch. The host's unimplemented call handler records and executes none of that work.
See [Unimplemented mesh draws leave holes in terrain](../../../docs/reference/rendering.md#unimplemented-mesh-draws-leave-holes-in-terrain).
The NVN2 mesh command/stage pipeline below is now implemented; allocation changes remain frozen pending a complete opening image.
Scene-level image comparison is still required to attribute and restore every absent surface. The temporary logging
host/source/build arguments and call TSV remain outside the repository; diagnostic timing is not a performance benchmark.

**Mesh implementation and early terrain investigation (2026-11-09).** Chain `cb0cf4544169` builds all **11,603** primary libraries, including all
26 native task/mesh programs (7 task, 19 mesh), with profile inputs unchanged at `9286520fae55`. The isolated
`/tmp/dmhost-mkw-nvn2-mesh` preserves the shared host and OOT work. The synthetic GPU fixture verifies native stage-buffer reads/writes, nonzero
first-group handling, task-relative mesh groups, independent task/mesh UBO/SSBO/c0 bindings, zero-output tasks and early EXIT by 31 of 32
invocations under Metal API/shader validation in both encoding modes. The larger fixture caught deferred encoding retaining only mesh thread
width and replacing object width with 1; it now retains all nine grid/object/mesh dimensions. A live material also exposed a flat varying
forwarded into R8Uint without an integer fragment entry; the builder now provides that entry without numerically converting its bits.
A zero-width direct compute dispatch exposed Metal 4's rejection of an otherwise legal empty NVN grid; it now executes no invocations.

Before the CPU-stream fix above, the opening has substantial absent road/ground and scenery in `opening-mesh-live-20261109-135643`,
`opening-mesh-final-20261109-141317` and the user's live inspection. The captured frame 4140 has 1,448 draw-entry records, including mesh work.
Some other opening locations render road surfaces correctly; these are not matched A/B scenes. A depth-refresh diagnostic and a logging-only
cache probe did **not** establish a stale depth-state bug: the latter found no cached/wanted state mismatch and still shows missing terrain at
frames 6000 and 12000. Do not ship a depth override or claim the mesh implementation restores all terrain. The selected terrain streams,
constants and ordered attachment snapshots are preserved in `opening-terrain-trace-20261109-141748`; its first captured location has intact
road surfaces. The all-texture debug readback aborted on an integer texture sampled by its float preview shader; this is a diagnostic limitation,
separate from the game's rendering. The broad opening-wide GPU-validation run was stopped during expensive startup compilation.

Validation so far: all 101 graphics executables and their shader-pull/TBDR checks pass; 111 shader Python tests pass with two optional tests
skipped, and 13 chain tests pass. The expanded 32-invocation fixture also passes after the deferred mesh fix. The final graphics suite was
repeated after that fix. The five-title harness remains blocked by the same four absent packaged builds (MKW, Bananza, TotK and Odyssey;
Skyrim alone is packaged). The compilation database contains 231 sources; clang-tidy and the Python lint dependencies are unavailable.
Documentation checks also retain unrelated failures for a missing game note, guide length, old broken links and the generated patch index.
Those early runs did not resolve the terrain failure; the CPU-stream finding above supersedes that status. The RAM target and stalls remain open; these diagnostic runs are not performance acceptance.

Validation of the sampled-target experiment: all 101 graphics executables plus four shader-pull and five TBDR-budget Python checks pass with
both sparse modes enabled. The final writable-image check passes 286 checks in each encoding mode, including GPU readback and dense fallback.
The five-title harness is blocked by four missing packaged builds; compilation-database generation succeeds for 230 sources, while clang-tidy
is unavailable. The shader chain and profile inputs are unchanged.

**Open: 9–10 GB app RAM target, streaming/shader pauses, collision slowdowns and wider rendering validation.** Accepted content-sharing runs peak at 11.20–11.47 GB app memory;
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

- [Vulkan cache-hit feedback](../../../docs/reference/shaders.md#vulkan-cache-hits-do-not-need-another-disk-snapshot): avoids rewriting a loaded cache for confirmed hits; full-game savings remain to be measured.

- [Canonical CPU texture storage with private file backing](../../../docs/reference/memory.md#canonical-cpu-texture-storage-can-use-file-backing-on-android): experimental lossless storage that trades disk I/O for reclaimable pages.

- [Wide sparse copies repeatedly scan dirty ranges](../../../docs/reference/nvn-objects.md#wide-sparse-copies-repeatedly-scan-dirty-ranges): removes repeated page-preparation scans while preserving copied bytes and untouched tiles.

- [Integer vertex inputs](../../../docs/reference/shaders.md#vulkan-vertex-inputs-preserve-integer-fetch-bits), [unused distance members](../../../docs/reference/shaders.md#unused-distance-declarations-exceed-the-mobile-interface-limit) and [oversized compute shared storage](../../../docs/reference/shaders.md#compute-shared-storage-exceeds-the-device-limit): preserve shader work within Vulkan device limits.
- [Imageless framebuffer usage](../../../docs/reference/rendering.md#imageless-framebuffers-inherit-attachment-view-usage) and [storage image types/swizzles](../../../docs/reference/rendering.md#storage-image-views-preserve-numeric-words-and-identity-swizzles): API-validated descriptor and render-pass fixes.

- [Vulkan memory-pool registry grows without moving records](../../../docs/reference/memory.md#vulkan-memory-pool-registry-grows-without-moving-records): removes the Android 4,096-pool ceiling and speeds address lookup.
- [Cached CPU pools allocate GPU buffers at first binding](../../../docs/reference/memory.md#cached-cpu-pools-allocate-gpu-buffers-at-first-binding): avoids buffers for CPU texture sources while retaining canonical bytes and later GPU access.
- [Unbound copied pools do not require GPU completion waits](../../../docs/reference/memory.md#unbound-copied-pools-do-not-require-gpu-completion-waits): preserves the first GPU writes while allowing unrelated submissions to overlap.
- [Vulkan atlas descriptor checks reuse unchanged page versions](../../../docs/reference/nvn-objects.md#vulkan-atlas-descriptor-checks-reuse-unchanged-page-versions): removes repeated range scans while retaining write, mapping and retirement checks.
- [GPU image ownership queries cache versioned storage ranges](../../../docs/reference/nvn-objects.md#gpu-image-ownership-queries-cache-versioned-storage-ranges): removes whole-cache scans while keeping GPU destinations and aliases visible.

- [Vulkan atlas offset/gather semantics](../../../docs/reference/rendering.md#vulkan-atlas-offsets-and-gathers-preserve-logical-texel-semantics) and [typed integer fragment exports](../../../docs/reference/shaders.md#vulkan-integer-attachments-consume-raw-fragment-export-bits), verified on Android (2026-11-10).

- [Vulkan atlas derivatives use logical texture dimensions](../../../docs/reference/rendering.md#vulkan-atlas-derivatives-use-logical-texture-dimensions): implicit sampling and LOD queries preserve logical views and dense fallbacks.
- [Fragment atlas helpers retain function calls](../../../docs/reference/shaders.md#fragment-atlas-helpers-retain-function-calls): reduces shader storage and measured module-loading peak memory without dropping operations.

- [Padded Vulkan vertex outputs reuse SPIR-V types](../../../docs/reference/shaders.md#padded-vulkan-vertex-outputs-reuse-spir-v-types): validates missing output padding and corrects short-vector defaults with literal GPU checks.

- [Vulkan push and dispatch constants preserve command order](../../../docs/reference/rendering.md#vulkan-push-and-dispatch-constants-preserve-command-order): independent stage state, immutable direct/indirect driver snapshots and full uniform-slot reflection.
- [Formatless storage images require SPIR-V capabilities](../../../docs/reference/shaders.md#formatless-storage-images-require-spir-v-capabilities): independent validation catches missing read/write declarations despite successful module loading.

- [Zero-copy Android pool restoration uses bounded scratch](../../../docs/reference/memory.md#zero-copy-android-pool-restoration-uses-bounded-scratch): avoids a pool-sized temporary copy during finalization and preserves CPU/GPU bytes.
- [Vulkan atlas refreshes reuse completed cells and fence each revision](../../../docs/reference/rendering.md#vulkan-atlas-refreshes-reuse-completed-cells-and-fence-each-revision): measured refresh cost and transient allocation reduction, with ordered-version regression coverage.
- [Vulkan CPU-streamed textures preserve GPU ownership](../../../docs/reference/nvn-objects.md#vulkan-cpu-streamed-textures-preserve-gpu-ownership): initial/late terrain fills reach Vulkan images while actual GPU destinations keep their content.
- [Vulkan compressed atlas mappings preserve image versions](../../../docs/reference/rendering.md#vulkan-compressed-atlas-mappings-preserve-image-versions): opt-in native compressed sampling from real NVN mappings, immutable versions and reloadable residency.
- [Vulkan task and mesh driver caches include their storage tables](../../../docs/reference/rendering.md#vulkan-task-and-mesh-driver-caches-include-their-storage-tables): covers the NVN2 high storage slots omitted by the original driver-buffer hash.
- [CPU-streamed uncompressed textures](../../../docs/reference/nvn-objects.md#cpu-streamed-uncompressed-textures): restores initial and late CPU-filled terrain tiles without replacing actual GPU-rendered data.

- [Linear and sRGB descriptors share texture storage](../../../docs/reference/rendering.md#linear-and-srgb-descriptors-share-texture-storage): resolved black movie output; race rendering remains incomplete.
- [Conditional rendering evaluated at replay](../../../docs/reference/rendering.md#conditional-rendering-evaluated-at-replay): `render_cond on` preserves the completed course and kart by skipping repeated conditional clears.
- [Copies into sparse textures persist in physical storage](../../../docs/reference/rendering.md#copies-into-sparse-textures-persist-in-physical-storage): corrects stale atlas content and reduces redundant allocations.
- [Sparse texture versions share unchanged physical tiles](../../../docs/reference/rendering.md#sparse-texture-versions-share-unchanged-physical-tiles): native compression, physical-page sharing and smaller refresh uploads.
- [Dirty-range lookup hints preserve first matches](../../../docs/reference/nvn-objects.md#dirty-range-lookup-hints-preserve-first-matches): removes repeated whole-registry searches from sparse tile checks; shared by Mac and Android.
- [Sparse mapping batches group tiles by backing heap](../../../docs/reference/rendering.md#sparse-mapping-batches-group-tiles-by-backing-heap): avoids scanning every tile again for every physical heap.
- [Unchanged sparse refreshes retain their metadata](../../../docs/reference/rendering.md#unchanged-sparse-refreshes-retain-their-metadata): identical immutable mappings keep their existing allocation and completion dependency.
- [Sparse mapping-only refreshes skip empty upload submissions](../../../docs/reference/rendering.md#sparse-mapping-only-refreshes-skip-empty-upload-submissions): changed read-only mappings reuse uploaded pages without a CPU completion wait.
- [Read-only sparse uploads use queue events](../../../docs/reference/rendering.md#read-only-sparse-uploads-use-queue-events): overlaps CPU replay with immutable uploads while bounding pending staging and preserving copy order.
- [Region writes hoist block-linear row addressing](../../../docs/reference/nvn-objects.md#region-writes-hoist-block-linear-row-addressing): reduces CPU copy work shared by Mac and Android while preserving partial writes and sparse holes.
- [Published startup shaders were loaded again at program creation](../../../docs/reference/shaders.md#published-startup-shaders-were-loaded-again-at-program-creation): ready startup shaders also enter the synchronized prefetch set, avoiding later duplicate preparation.
- [Identical immutable sparse tiles share physical backing](../../../docs/reference/rendering.md#identical-immutable-sparse-tiles-share-physical-backing): exact-content sharing lowers the corrected run to 11.47 GB; the mode remains opt-in.
- [Pipeline archive imports retain substantial host file data](../../../docs/reference/memory.md#pipeline-archive-imports-retain-substantial-host-file-data): the compiler-cache configuration reduces measured app footprint with a longer startup; handle eviction alone is rejected by the heap census.
- [Writable sparse textures preserve GPU physical pages](../../../docs/reference/rendering.md#writable-sparse-textures-preserve-gpu-physical-pages): removes dense GPU atlas backing while keeping shader/raster writes coherent across aliases.
- [GPU-only sampled sparse textures can become render targets](../../../docs/reference/rendering.md#gpu-only-sampled-sparse-textures-can-become-render-targets): an opt-in experiment avoids densifying a sampled atlas; opening-scene validation remains open.
- [Unimplemented mesh draws leave holes in terrain](../../../docs/reference/rendering.md#unimplemented-mesh-draws-leave-holes-in-terrain): actual opening mesh calls bind unsupported task/mesh programs and produce no host geometry, including with dense texture allocation.
- [Packed signed vertex conversion processes four vertices together](../../../docs/reference/frame-rate.md#packed-signed-vertex-conversion-processes-four-vertices-together): removes repeated format decoding from the racing CPU hotspot.
- [Vulkan sparse support is checked per format](../../../docs/reference/rendering.md#vulkan-sparse-support-is-checked-per-format): measures Android residency, format, aliasing and address-space prerequisites separately.
- [NVN2 stage buffers become Vulkan task and mesh stages](../../../docs/reference/rendering.md#nvn2-stage-buffers-become-vulkan-task-and-mesh-stages): translated task/mesh execution and compressed-array allocation/readback proof on Adreno.
- [Compressed virtual atlases use a page table in a storage prototype](../../../docs/reference/rendering.md#compressed-virtual-atlases-use-a-page-table-in-a-storage-prototype): bounded tile addressing, filtering and remap proof on Adreno.
- [Residency mutations and queue commits share a lock](../../../docs/reference/nvn-objects.md#residency-mutations-and-queue-commits-share-a-lock): fixes the independently reproduced queue race and destructor deadlock.
- [Writable image views follow the instruction dimension](../../../docs/reference/rendering.md#writable-image-views-follow-the-instruction-dimension): preserves a selected array layer/mip for non-array compute image instructions.
- [Performance HUD collection scope](../../../docs/reference/frame-rate.md#performance-hud-collection-scope): presentation metrics remain visible without the severe default-HUD regression.

- [Inactive GPU images retain pixels in private file storage](../../../docs/reference/memory.md#inactive-gpu-images-retain-pixels-in-private-file-storage): bounded transfer staging preserves GPU-only contents while releasing inactive image storage.
- [Vulkan atlas interiors use native bilinear filtering](../../../docs/reference/rendering.md#vulkan-atlas-interiors-use-native-bilinear-filtering): preserves logical sampling at boundaries while filtering tile interiors in hardware.
- [Completed pipeline builds count as watchdog progress](../../../docs/reference/shaders.md#completed-pipeline-builds-count-as-watchdog-progress): diagnostic cold starts track successful compilation without inventing frames.
- [Raw NVN timestamp units](../../../docs/reference/frame-rate.md#raw-nvn-timestamp-units): Vulkan GPU reports now match the shared 614.4 MHz conversion; independent device queries confirm the scale and epoch.

- [Recorded Vulkan states can prepare before replay](../../../docs/reference/shaders.md#recorded-vulkan-states-can-prepare-before-replay): moves known compilation work into an isolated preparation process that exits before gameplay.

- [Copied command streams own their recorded bytes](../../../docs/reference/nvn-objects.md#copied-command-streams-own-their-recorded-bytes): preserves copied state after source-memory reuse including nested source streams.

## Android GPU proof (2026-11-09)

**Passed on the connected Lenovo TB323FU / Adreno 840:** the isolated Vulkan task/mesh bridge builds and SPIR-V-validates all **26** real
programs (7 task, 19 mesh). All 26 also compile as device graphics pipelines with reflected resource layouts and matching test fragment
consumers. They are compile checks, with no game buffer data bound or dispatched. The earlier producer-only discard probe refused 24 with
`VK_ERROR_UNKNOWN`; the complete pipelines pass, so that refusal does not identify invalid shader IR.

Separately, synthetic Ampere instructions run through the same translator/bridge and produce the expected rasterized triangle. The draw
tests cover a nonzero first group, task payload/relative child group, 31 early EXITs, independent task/mesh UBO and SSBO bindings, negative
binding controls, an empty task and a zero task count. GPU readbacks verify BC1, BC6H UFLOAT, ASTC 4×4 UNORM and ASTC 8×8 sRGB arrays
with four layers and three mips. Nonzero BC6H colours include HDR red near 2.0; ASTC gray checks linear versus sRGB conversion. Compressed
blocks survive upload/readback byte for byte. **44 probe checks pass**, comprising 26 real pipeline checks and 18 synthetic draw/texture checks.
See [NVN2 stage buffers become Vulkan task and mesh stages](../../../docs/reference/rendering.md#nvn2-stage-buffers-become-vulkan-task-and-mesh-stages).

For 1024×1024, four layers, three mips, the actual bound allocation equals the compressed payload:

| Format | Bound allocation | RGBA8 equivalent |
|---|---:|---:|
| BC1 | 2.625 MiB | 21 MiB |
| BC6H UFLOAT | 5.25 MiB | 21 MiB (42 MiB for RGBA16F) |
| ASTC 4×4 UNORM | 5.25 MiB | 21 MiB |
| ASTC 8×8 sRGB | 1.3125 MiB | 21 MiB |

This validates compression for these bounded images; it does not establish full-game RAM use or the 9–10 GB target. The refreshed capability
probe still reports no sparse physical-page aliasing and no sampled/upload sparse properties for the tested BC6H/ASTC formats, with a
4095 MiB sparse address space. The largest checked mesh layout fits with a 2 KiB payload inside the device's 32 KiB combined mesh
payload/shared limit. A common payload size is an explicit pipeline ABI, not a game memory clamp.

Evidence and reproducible fresh outputs: `0400C3F00006E000-work/android-proof-20261109/` (the `repro/` subfolder is built by the checked-in
`probes/make_nvn2_proof.py`). NDK 28.2 compiles the probe with `-O1 -Wall -Werror`; three Python tests and a targeted Ruff check pass.
The Khronos layer was copied only to the temporary probe folder, but the shell loader cannot discover it (`VK_ERROR_LAYER_NOT_PRESENT`);
this is SPIR-V validation plus actual GPU readback, not an API-validation-layer pass. No Android system setting or installed application changed.
MKW/OOT boot-harness checks are blocked by absent packaged builds; neither game is claimed playable from this proof.

## Android offset/gather and attachment parity (2026-11-10)

**Current checkpoint:** the compressed Android atlas supports all floating array offset/gather operations found in this shader census. The GPU comparison passes **15,750 checks**, including 198 compressed-reference checks and **15,925,248 pixel comparisons**. It covers twelve operation forms across BC6H, ASTC4x4 and ASTC8x8 sRGB, both GOB orders, mip/layer/swizzle views, wrapping, filters and LOD/bias. Ignoring only filter offsets fails 3,440 checks; reversing only gather order fails 5,328. All **21 real offset/gather programs** convert, validate independently and load, with 24 atlas bindings and no unknown reflected resources. This resolves both programs blocked at the preceding implicit checkpoint.

A bounded diagnostic run of the accepted complete Mac renderer captures **1,005 native mesh draws in 12 attachment contexts**. Their colors use RGBA16Float, RGBA16Unorm, RGBA8Unorm and R8Uint. Android lacked typed fragment exports for the integer target; the general fix preserves export bits and selects signed/unsigned types per attachment location. **88 production GPU checks** pass, including mixed targets and reuse of 26 cached variants. The real R8-target shader independently validates after conversion. See [integer export mechanism](../../../docs/reference/shaders.md#vulkan-integer-attachments-consume-raw-fragment-export-bits) and [offset/gather semantics](../../../docs/reference/rendering.md#vulkan-atlas-offsets-and-gathers-preserve-logical-texel-semantics).

All **14 recorded-format pipeline checks** pass with the captured blend, depth-test, culling and write-mask state. These represent the twelve contexts with two depth-precision alternatives: Metal format 260 does not distinguish original D24S8 from D32S8, so both Vulkan formats are checked. The R8Uint context uses an unsigned attachment matching its observed Metal numeric type. Real game programs are compiled without fabricated buffers or dispatches. The diagnostic Mac run preserves the overlay and is not a performance benchmark.

The same final Android binary retains **2,166 implicit, 102 driver, 856 atlas, 120 captured-terrain and ten ordinary draw checks**, plus five pool-restoration sizes. All 194 Android sources compile; 16 host tests and configured targeted Ruff pass. The API validation layer remains unavailable, and the five-title Mac preflight still lacks packaged builds. Docs retain three existing failures. Evidence: external `0400C3F00006E000-work/android-offset-20261110/`. [Reproduction](../../../../probes/README.md#offset-gather-and-typed-attachments).

Next build the Android game profile and attempt a bounded scene with the measurement overlay. Establish real startup, working-set memory, texture completeness and frame stalls before further memory tuning. These are backend checks; **Android gameplay RAM/FPS and the 9–10 GB target remain open**. The complete Mac reference remains available.

## Android implicit atlas sampling (2026-11-10)

**Preceding checkpoint:** fragment implicit sampling, shader bias and LOD queries work through the compressed atlas. Dense-versus-virtual comparison passes **2,166 GPU checks**, including byte-exact reference blocks and 2,015,232 pixel comparisons. It covers BC6H/ASTC in both GOB orders, sampler filters and LOD clamps, mip/layer views, wrapping, zero derivatives and dense fallback. Removing only the logical-dimension correction fails 1,680 checks. See [sampling semantics](../../../docs/reference/rendering.md#vulkan-atlas-derivatives-use-logical-texture-dimensions).

All **2,417 eligible real programs** convert, validate independently and load on-device with **6,579 atlas bindings** and no unknown reflected resources. Two other programs in the implicit/query group require offset/gather and fail explicitly; other offset/gather-only programs remain outside the contract. Twelve observed native pipeline combinations compile, including one newly converted fragment. These are compile-only checks with a minimal RGBA8 pass; no real game buffers are dispatched. DMSV flag bit 2 gates the new fragment metadata, with an old-runtime rejection control.

Preserving fragment helper functions reduces the real bundle from **719.481 to 288.056 MiB**. In two fresh loads per representation, peak process RSS falls from **2,302,172KiB** to **978,148–978,736KiB**, about **1.26 GiB lower**. These loads use the complete tested shader subset and do not allocate a game texture working set or compile game pipelines. Actual gameplay savings remain unmeasured. [Compiler mechanism](../../../docs/reference/shaders.md#fragment-atlas-helpers-retain-function-calls). Compute/native wrappers retain their prior compiler paths.

The final explicit-atlas regression workload retains its **40 MiB** allocation peak and about **2.16 ms remap / 2.61 ms new-content preparation**. Earlier noisy samples and the all-stages compiler experiment remain archived. No speed gain or full-game RAM result is claimed. The new fragment path's real-scene GPU cost remains open.

The same final binary passes **102 driver, 856 atlas, 120 terrain and 10 draw** checks and five pool-restoration sizes. All 194 Android sources compile;13 Python tests and targeted Ruff pass. The API validation layer remains unavailable. Five-title boot preflight (MKW, Rise, Odyssey, TotK, Xenoblade3) stops on missing packaged builds; docs retain three existing failures. Evidence: external `0400C3F00006E000-work/android-implicit-20261110/`. [Reproduction](../../../../probes/README.md#implicit-atlas-sampling). Offset/gather and recorded attachment formats are now covered in the checkpoint above. The **9–10 GB target and full-game RAM/FPS remain open**; the complete Mac reference/overlay is preserved.

## Android shader and interface coverage (2026-11-10)

**Current checkpoint:** all **11,603 programs** build, pass independent Vulkan1.2 SPIR-V validation and load on Adreno840: 7,301 fragment, 3,547 vertex, 729 compute, seven task and 19 mesh. The full 495.7 MiB bundle is not atlas-converted. Independent validation exposed 40 padded vertex programs with duplicate type declarations; [type reuse fixes them](../../../docs/reference/shaders.md#padded-vulkan-vertex-outputs-reuse-spir-v-types). The expanded fixture also corrects missing vec2/vec3 defaults while retaining vec4 W=1. Its literal GPU pixel test passes; restoring only the wrong short-vector defaults fails exactly one of ten draw checks.

Two recorded Mac opening runs identify **12 actual task/mesh/fragment combinations**, including combinations absent from the static pair table. All 12 compile on the device using 27 distinct real programs, production descriptor layouts and per-primitive fragment variants. Basic interface inspection finds no missing locations or scalar-type mismatches. These are compile-only checks with a minimal RGBA8 pass; no real game buffers are bound or dispatched. Actual target formats, blend/depth state and rendered-scene correctness remain open. Isolated compile calls take 7.2–87.5 ms in this run; these are not game frame times.

The final binary retains **102 driver, 856 atlas, 120 terrain and ten draw checks**, plus five pool-restoration sizes. All 194 Android sources compile; 11 Python tests and targeted Ruff pass. The shell API layer remains unavailable. Five-title boot preflight (MKW, Odyssey, TotK, Xenoblade3, HadesII for shared padding/interfaces) stops because the packaged builds are absent. Docs retain their three existing failures.

The complete shader census identifies floating array implicit sampling in **2,359 fragment programs** and LOD queries in **1,118 programs**. It also finds offset and gather operations outside the current atlas contract. These are asset-library counts, not runtime usage rates. Storage-image and shadow operations are counted separately. The next implementation target is implicit sampling/LOD queries with verified derivatives, logical dimensions and sampler behavior, followed by offset/gather and actual attachment coverage before a bounded game scene.

Evidence, exact binaries/bundles, before/after validation, observed-pipeline provenance, controls and census are saved externally in `0400C3F00006E000-work/android-interfaces-20261110/`. [Reproduction](../../../../probes/README.md#real-android-shader-and-pipeline-audit). Shader compatibility evidence has improved; full-game RAM/FPS, stalls and the **9–10 GB target remain open**. The complete Mac reference and overlay are preserved.

## Android driver-state parity (2026-11-09)

**Current bounded checkpoint:** NVN2 graphics/compute push constants, driver c24, direct/indirect dispatch counts and uniform slots0–15 pass GPU replay checks. The original runtime fails 57 of the 100 common checks; the corrected runtime passes those 100 plus two formatless-image checks. Graphics/task/mesh state is checked through actual pixels, and compute through literal output buffers. Five invalid-record/count/address controls stop explicitly; unknown DMSV flags are rejected. See [push and dispatch semantics](../../../docs/reference/rendering.md#vulkan-push-and-dispatch-constants-preserve-command-order).

Independent SPIR-V validation found **239 programs with missing formatless storage-image capabilities** despite successful module loading. Android finalization now declares the capabilities required by actual image accesses, preserving executable instructions and image types. The device exposes both formatless read/write features, and a formatless R32F write/read round trip passes. All **755 selected real programs** (729 compute, seven task, 19 mesh) build, validate independently and load on Adreno840; they include 30 c24 bindings. This census bundle is not atlas-converted and no real game buffers are dispatched. See [shader correction](../../../docs/reference/shaders.md#formatless-storage-images-require-spir-v-capabilities).

The same final executable passes **102 driver, 856 atlas, 120 terrain and nine ordinary draw checks**, plus five pool-restoration sizes. All 194 Android sources compile; nine Python shader tests and targeted Ruff pass. The shell API validation layer remains unavailable. The five-title regression preflight selected MKW/Bananza for NVN2 state and TotK/Xenoblade3/13Sentinels for classic dispatch/reflection; none has a packaged Mac build locally. The docs suite retains three existing failures.

Two fresh processes per version retain the previous atlas performance in the same 121-job offscreen workload: remap medians **2.256–2.266 → 2.254–2.268 ms**, new-content medians **2.695–2.697 → 2.696–2.699 ms**, and **40 MiB** atlas peak in both. Process VmHWM is **138.05–139.04 → 139.96–140.41 MiB**, including teardown. First-use wall samples rise **177–179 → 202–226 ms**, with thread CPU **167–168 → 169–193 ms**; their cause remains unresolved. No additional RAM/FPS improvement is claimed. GPU timestamps exclude private transfer work, and process/Vulkan counters must not be added.

Exact source/build/binary hashes, before/after controls, raw timing CSVs, shader-validation census and device logs are preserved externally in `0400C3F00006E000-work/android-driver-state-20261109/`. [Reproduction](../../../../probes/README.md#android-driver-state-replay). Next cover actual sampling modes and task/mesh-to-fragment/typed-output interfaces, then add `android.tsv` and attempt a measured rendered scene with the overlay. Full Android game RAM/FPS, broader stalls and the **9–10 GB target remain open**. The accepted complete Mac renderer is preserved.

## Android atlas measurements (2026-11-09)

**Current measured checkpoint:** a repeatable offscreen workload uses the real NVN mappings, native BC6H cache, shader descriptors and Vulkan submissions on Lenovo TB323FU / Adreno840. It maps 512 distinct 64 KiB cells (32 MiB) into the logical 6,087,507,968-byte/8192²×68-layer atlas. Thirty additional source cells supply content changes. Each serialized job performs four sampling/query operations and waits for completion. The synthetic source patterns retain native compression and verify sampled values; this is not a game scene or an estimate of the game's mapped working set.

The comparison runs baseline/candidate/candidate/baseline, two fresh processes per version with identical data and fixture code. Each has one first-use job, 60 unchanged jobs, 30 remaps to existing content and 30 new-content mappings. The first ten unchanged jobs are excluded from steady-state summaries. No device clocks or global settings are changed. The mechanism and lifetime fix are described [here](../../../docs/reference/rendering.md#vulkan-atlas-refreshes-reuse-completed-cells-and-fence-each-revision).

| Metric | Baseline | Candidate |
|---|---:|---:|
| Remap-existing median CPU preparation, per-run range | 10.199–10.221 ms | 2.166–2.167 ms |
| New-content median CPU preparation, per-run range | 10.653–10.670 ms | 2.608–2.609 ms |
| Unchanged median CPU preparation | 0.0499–0.0500 ms | 0.0500–0.0502 ms |
| Remap-existing CPU preparation p95 | 10.339–10.400 ms | 2.190–2.193 ms |
| New-content CPU preparation p95 | 10.819–10.861 ms | 2.636–2.757 ms |
| Atlas image/staging allocation peak, including overlapping image generations | 76 MiB | 40 MiB |
| Retained atlas image/staging after mapping changes | 44 MiB | 40 MiB |
| Process VmHWM, including teardown | 170.26–171.97 MiB | 141.00–142.60 MiB |
| Sampled process PSS peak during jobs | 67.28–67.40 MiB | 67.28–69.29 MiB |

The measured preparation reduction is about **79% for remaps and 75.5% for new content**. The main sampling command-buffer GPU median stays near 0.0082–0.0083 ms; it excludes the separate private transfer submissions. CPU wall time includes synchronous upload waits, and thread CPU time is recorded separately. First-use preparation is 181–198 ms versus about 171 ms, but shader/driver cache state makes this a limited offscreen startup sample, not game startup evidence. Source setup is recorded separately. Each unchanged/remap job uploads zero compressed bytes; each new-content job uploads 65,536 bytes. Metadata is 373,296 bytes per job in both versions.

**The process high-water reduction is a teardown improvement.** Atlas changes alone did not lower process VmHWM in the initial comparison. The final candidate also restores zero-copy pools using bounded scratch instead of a whole-pool temporary copy; see [pool restoration](../../../docs/reference/memory.md#zero-copy-android-pool-restoration-uses-bounded-scratch). Cleanup falls from 11.69–11.99 ms to 8.14–8.15 ms; all 35,520,512 source bytes and 65,536 GPU output bytes remain identical. Five additional restoration checks cover page/chunk boundaries and GPU writes. During-job PSS remains similar, so no lower persistent working set is established. Teardown is included in VmHWM. Allocation bytes and process counters must not be added. Full Android game RAM/FPS and the **9–10 GB target remain open**.

Correctness: the final executable passes **856/856 atlas checks, 120/120 terrain checks and 9/9 draw checks**. The stronger fixture exposes the previously hidden revision-fence bug: the old baseline fails 24/856; the candidate with only revision-aware tagging removed fails 64/856. All 194 production Android sources compile, fixture `-Wall -Werror`, eight Python shader tests and targeted Ruff pass. Shell API validation remains unavailable; SPIR-V validation and actual GPU readbacks pass. The five-title Mac preflight (MKW, TotK, Xenoblade 3, 13 Sentinels, Hades II) remains blocked by absent packaged builds; no Mac runtime changed. Docs retain the same three existing failures. No installed app, shared host, overlay or profile change; no commit.

Raw CSVs, comparison JSON, exact baseline/candidate/control binaries, source snapshots, capture provenance and logs are external in `0400C3F00006E000-work/android-measure-20261109/`. [Measurement reproduction](../../../../probes/README.md#measured-android-atlas-refresh). Next: NVN2 push-constant/compute-driver parity, remaining shader sampling and stage/output interfaces, then a bounded Android game scene with the existing measurement overlay. Further performance claims need a representative game workload.

## Android terrain upload parity (2026-11-09)

The [measured atlas follow-up above](#android-atlas-measurements-2026-11-09) retains these terrain checks and expands the atlas suite to856checks.

**Current bounded checkpoint:** the Android backend now uploads initially filled and late CPU-streamed textures, detects actual GPU ownership through shared storage keys, invalidates descriptors on first CPU classification, and releases tracking at the appropriate texture/pool lifetime. The previous backend fails **60 of 91** common terrain checks. The final suite passes **120/120** on Lenovo TB323FU / Adreno 840. See [the mechanism](../../../docs/reference/nvn-objects.md#vulkan-cpu-streamed-textures-preserve-gpu-ownership).

The synthetic checks use actual NVN pool/texture initialization, dirty-write polling and Vulkan image readback for 260×260 R16, RG16 and R8 in both GOB orders. They cover pre-initialization fills, unflushed first use, empty resolution followed by a late fill, repeated updates, shared-storage ownership, actual GPU clears before/after CPU classification, shader-writable storage and finalized command snapshots. Twelve thousand unfilled texture initialization/finalization cycles retain no extra identity records, and each pool cleanup leaves zero tracking records. Retired CPU classification survives only as pool-associated metadata until pool finalization; these checks are not a full-game memory bound.

**Actual game data:** the eight `height-*-source.bin` files from `opening-stream-initial-fixed-20261109-153020/height-inputs` are replayed through the real Android upload path. Every Vulkan R16 texel matches the saved complete Mac GPU row captures: **540,800/540,800 height values**, plus 64 production shader fetch samples covering interiors and edges. The capture header's format20 is Metal R16Unorm; the NVN input remains format0x6. Reusing the same storage for successive texture objects also verifies refresh when data was filled before initialization.

All194 Android sources compile in the isolated terrain output; the fixture compiles with `-Wall -Werror`. The final executable also passes **700/700 compressed-atlas checks and 9/9 draw checks**. Eight Python shader tests, targeted Ruff and `git diff --check` pass. SPIR-V validation/GPU readbacks pass; the shell API validation layer remains unavailable. The five-title Mac boot preflight (MKW, TotK, FFT, Great Ace Attorney and Hades II) remains blocked by absent packaged builds. Docs retain the three existing failures. No shared Mac host, profile, installed app or measurement overlay changed. No commit made.

Exact baseline/candidate binaries, source/dependency hashes, capture provenance, build commands and logs are saved externally in `0400C3F00006E000-work/android-terrain-20261109/`; [reproduction](../../../../probes/README.md#cpu-streamed-terrain-upload-parity). This establishes terrain upload/sampling parity for these captured inputs, not Android gameplay, a whole scene or a RAM/FPS improvement. The **9–10 GB target remains open**.

**Next:** NVN2 push-constant/compute-driver parity, actual shader sampling coverage and mesh/fragment interfaces, and typed colour outputs. Then add `android.tsv` and attempt a bounded rendered scene with the platform/measurement overlay. The complete Mac renderer remains the visual reference.

## Android mapped-atlas runtime (2026-11-09)

The [terrain upload follow-up above](#android-terrain-upload-parity-2026-11-09) closes the tested CPU-stream gap; other limitations of this checkpoint remain open.

**Current bounded checkpoint:** the compressed atlas path now consumes actual NVN virtual-pool mappings and runs through production Vulkan descriptors, command replay and shader sampling. `DM_VK_ATLAS=1` and bundles built with `shader_vk.py --virtual-atlas` opt into it. The default path is unchanged. See [the mechanism and explicit limits](../../../docs/reference/rendering.md#vulkan-compressed-atlas-mappings-preserve-image-versions); this does not yet cover a complete game renderer.

On Lenovo TB323FU / Adreno 840, **700 GPU/CPU comparisons pass** with patterned BC6H UFLOAT, ASTC4x4 UNORM and ASTC8x8 sRGB, each in both GOB orders. The fixture uses the real NVN pool/map APIs, native 64 KiB source cells and a virtual offset of 32 GiB. BC6H's logical 8192²×68-layer/12-mip storage is 6,087,507,968 bytes; the ASTC fixtures are rectangular 8192×4096. Tests cover seams, fractional LOD, nearest/repeat/clamp modes, LOD limits, view-relative mips/layers, swizzles, unmapped defaults, source writes and remaps before submission, cache growth and uploads beyond 8 MiB staging, eighty replacements, idle eviction/reload, and final pool release. Partial mapping, unsupported anisotropic sampling and direct virtual-buffer controls each stop explicitly as expected.

After completed GPU work, the tested cache image plus its private upload staging stood at **20 MiB** (12 MiB image and 8 MiB staging), and reached zero after pool cleanup. That count includes retained old image generations while they are live, but excludes page-table/general scratch storage, driver allocations and NVN pools. The fixture maps a small synthetic working set: **20 MiB is not a game memory estimate**. Real data population, cache-growth peaks, startup cost and rendering performance still need measurement.

All 26 real task/mesh programs build and load with the atlas-aware bundle; four texture bindings receive paired metadata (29 storage-buffer, 21 driver-buffer, 41 constant-buffer, four texture and four atlas-metadata bindings). No real game buffers are dispatched. A separate replay regression exposed a driver-buffer cache hash that missed task/mesh storage tables; extending it through `0x870` restores **9/9 draw checks**. Restoring only the old hash fails two of nine checks. See [driver cache correction](../../../docs/reference/rendering.md#vulkan-task-and-mesh-driver-caches-include-their-storage-tables).

Validation: 194 production Android sources compile in an isolated output, the fixture builds with `-Wall -Werror`, eight shader tests and targeted Ruff pass, and the Mac graphics suite passes. SPIR-V validation and actual GPU readbacks pass; the Android shell still cannot discover the API validation layer. MKW/OOT boot-harness checks remain blocked by missing packaged Mac builds. The docs suite retains three pre-existing failures. Exact binaries, bundles, source hashes, build flags, controls and logs are saved externally in `0400C3F00006E000-work/android-mapped-atlas-20261109/`; [reproduction](../../../../probes/README.md#production-mapped-compressed-atlases).

**Next:** audit actual shader sampling coverage and mesh/fragment interfaces, NVN2 push-constant/compute-driver parity, typed colour outputs and CPU-streamed terrain uploads before adding `android.tsv` and attempting a bounded game scene with the existing measurements overlay. No Android gameplay, full-game RAM or FPS result is claimed. The 9–10 GB target remains open. The accepted Mac binary and overlay remain available; the shared host and OOT work were not replaced.

## Android replay and virtual-atlas prototype (2026-11-09)

Historical checkpoint preceding the [mapped-atlas runtime above](#android-mapped-atlas-runtime-2026-11-09). Its standalone prototype and measurements remain useful for comparison.

**Passed:** task/mesh integration in the production Android bundle and replay backend, tested through NVN command records on the Lenovo TB323FU / Adreno 840. Nine pixel checks cover direct and task mesh, first-group parameters, empty/zero draws, independent task/mesh resource bindings with negative controls, per-primitive fragment inputs, a conventional vertex draw afterward, and rejection of oversized launches. The fixture replaces synthetic shader-key lookup; it links the real backend and host objects and loads no game modules. The per-primitive fragment fixture starts as SPIR-V 1.0, exercising the variant's upgrade to the mesh extension's SPIR-V 1.4 interface rules.

The production builder translates all 26 real programs (7 task, 19 mesh) into `mesh.dmsv`. All 26 load through the production shader loader with launch-limit checks and descriptor layouts on the tablet; no real game buffers are dispatched. Reflection identifies 29 storage-buffer, 21 driver-buffer, 41 constant-buffer and four texture bindings, with zero unknown kinds. The GLSL block/instance naming issue was found and fixed during this check. Versioned metadata records compiled shared memory and payload size; task/mesh descriptors use distinct sets and eight-stage resource state. Native capture now preserves the compiler metadata and canonical NVN2 hash. See [the mechanism and checks](../../../docs/reference/rendering.md#nvn2-stage-buffers-become-vulkan-task-and-mesh-stages).

**Storage alternative proved in isolation:** a logical 8192×8192×68-layer BC6H atlas, 14 mip levels, sampled through a page table into four compressed 128×128 physical tiles. All 22 GPU/CPU comparisons pass, including tile boundaries, fractional mip filtering, array layers, mip tails, clamped edges and a logical page remap that preserves another alias. Allocation is 65,536 bytes for the physical image plus 1,487,296 bytes for 371,824 page-table entries, 65,536 bytes of upload staging and 352 bytes of query/results payload. Query/result buffers bind 384 bytes after alignment; total bound image/buffer memory is 1,618,752 bytes, excluding driver/pipeline overhead. These are synthetic repeated-colour pages: this does not measure how many real game tiles must remain resident.

The same driver reports dense image requirements for that shape of 6,085,001,216 bytes (5,803.1 MiB) for BC6H or ASTC 4×4, and 1,521,598,464 bytes (1,451.1 MiB) for ASTC 8×8 sRGB. Those large images were never allocated. These queries compare format storage costs; changing a game's format requires a separate conversion and quality investigation. The prototype avoids the driver's unsupported compressed sparse path by explicit shader page lookup, and is not wired into game sampling yet. See [prototype limits](../../../docs/reference/rendering.md#compressed-virtual-atlases-use-a-page-table-in-a-storage-prototype).

Validation: all 193 Android sources compile in an isolated output, the replay executable links with `-Wall -Werror` for its fixture, four shader-generation tests and targeted Ruff checks pass, and the graphics suite passes. MKW/OOT boot-harness checks remain blocked by absent packaged Mac builds. Evidence: `0400C3F00006E000-work/android-runtime-20261109/`; reproduction in `probes/README.md`. No installed app, Android global setting, shared Mac host binary or accepted overlay changed. No commit made.

**Next milestone:** connect the page-table sampling path to actual atlas mappings and shader accesses with correct filtering, residency and in-flight lifetimes; verify streamed terrain uploads in Vulkan; then add the Android profile and attempt a bounded, measured rendered scene. The title still has no `android.tsv`. Native Android game RAM/FPS and the 9–10 GB target remain open. The accepted Mac reference stays available.

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
