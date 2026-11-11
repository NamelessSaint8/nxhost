---
status: resolved
trigger: "lots of textures missing now."
created: 2026-11-09
updated: 2026-11-09
---

## Symptoms

Expected: the opening before menus renders road/ground and scenery completely, with the performance/platform HUD preserved. Correctness precedes further RAM reduction; 9–10 GB remains a target.

Actual: whole ground/road surfaces and scenery are missing in numerous opening locations. Other locations (some paved roads and tree-house paths) render correctly. The defect persists at roughly 25 GB with sparse textures disabled. User reconfirmed it repeatedly on current runs.

## Current Focus

resolved: valid CPU terrain tiles were not uploaded into their sampled Metal textures.
verification: all eight captured GPU height tiles contain varied nonzero data; the clean production run restores textured road/ground/scenery, confirmed by the user. Full graphics suite passes.
next_action: use this corrected renderer as the baseline for separate RAM/stall work. Keep the live run PID38050 available; no new RAM optimization is part of this fix.

## Evidence

- 26 native task/mesh programs previously could not run. Mesh draw/stage support is implemented; all 11,603 shaders build on chain cb0cf4544169 (profile inputs 9286520fae55). This did not restore the main terrain loss.
- Synthetic GPU fixture covers independent task/mesh resources, first group, task-relative groups, zero tasks and 31 early EXITs out of 32 invocations in both encoding modes under API/shader validation. It exposed and verified a fix for deferred encoding dropping object thread dimensions.
- Additional concrete fixes: empty direct compute grids execute no invocations; a flat-varying passthrough fragment gets an integer target entry.
- Opening frame 4140 in opening-mesh-final-20261109-141317 visibly lacks ground and has 1,448 draw-entry records including actual mesh work. User confirms missing content.
- A logging-only depth-state probe found no cached/wanted state mismatches and still has missing terrain at frames 6000 and 12000. Different startup locations made the earlier depth-refresh comparison inconclusive.
- Live culling-off and depth-always diagnostics in opening-raster-probe-20261109-142726 did not restore missing off-road terrain; both flags were restored to zero. These are separate /tmp sources, not production changes.
- GPU frame capture cannot currently reach the scene: its required MTLDevice pipeline path stalls in Apple's pipeline compiler. Retried with empty prewarm list; no trace produced. Both attempts stopped. Xcode was opened but no GPU frame was inspected.
- All-texture debug readback hit an integer-texture/float-preview validation assertion. Avoid that diagnostic. It is separate from gameplay rendering.
- opening-terrain-trace-20261109-141748 has selected vertex/constant/index buffers and eight ordered raw attachment snapshots for frame 2159, whose nearby road is intact.
- Many indirect argument records are zero after frame 2159. End-of-frame observations do not prove they were zero at draw time.
- Exact shader 3aa955bf42b91d65 builds e9806085093845df/50a275e9d32af1c7 indirect arguments. Controlled GPU execution on positive input counts passes 114 checks for N=1/4/16/32 (instance counts and prefix base instances). Source/probe/log: /tmp/mkw-prefix-probe.{m,log}, /tmp/mkw-prefix-build.log. Live GPU-ordered snapshots in opening-cs-snapshot-20261109-145032 show valid N=76/cap=16384 and all 76 input counts zero before the dispatch. The builder correctly produces zero; this moves the question upstream. The producer e8b67edbc1c57f9d scatters instances using density, height and type maps, and may be vegetation rather than base terrain; relevance to missing road remains unproved.
- opening-pull-probe-20261109-144058 switches normal fetch to manual pulling in the same run. More than 1,000 draws/frame use the pulling path (log confirms), but fetch-manual.png and fetch-manual-later.png still show absent ground around Peach's castle/beach. Manual fetch was restored to off. This bounds a vertex-descriptor/format decoder explanation.
- Attribute 0x5C warning in inspected procedural shader e9806085093845df is an AST output write at code+0xd30, not an ALD input read. Do not assume this warning means missing vertex input.

- opening-producer-probe-20261109-150025 snapshots e8b67edbc1c57f9d in GPU order: terrain-type R8Uint map has 2,235,187 nonzero texels out of 4,194,304. The producer indirect dispatch is actually 2×2×0 and its rectangle list is zero, so these samples request no work. They do not establish a failing compute shader or relevance to base terrain. Density/height mip snapshots were zero, but the sampled mip levels differ from the shader's explicit level 0 and cannot establish its actual sampled content.
- The same run captures a visibly broken Peach meadow road at frame 1552, 12 ordered attachments and all bindings. Snapshot cap stops before the main shaded passes (169489/169490); the early black HDR targets are depth-only passes with zero color write masks, not evidence of a lost shaded image. Source/output/raw inspection script: /tmp/mkw-view-attachments.py.

- Solid-color family runs: opening-grid-constants-20261109-150808 (GridifyGeo magenta, normal depth/culling) renders many large surfaces; their camera/world constants are valid (curvature radius 20,000, threshold 500). opening-material-families-20261109-151012 colors Procedural cyan, Others yellow, Stage green: cyan covers the blank foreground. This narrows the affected path without proving every absent surface has the same cause.
- **Concrete mismatch:** opening-height-inputs-20261109-151516 captures 8 exact 260×260 R16Unorm height tiles in GPU order before draws by 1da6a11929e4125a; every texel is zero. Normal rendering remains visibly broken. The normal renderer is restored (no color/depth/culling override).
- opening-height-history-20261109-151737 captures the same GPU tiles and CPU block-linear backing. All eight CPU sources contain about 135,000 nonzero bytes of 152,064, while the actual Metal tiles remain zero. No logged T2T or image writer for these height shapes. This establishes lost upload/refresh data, not a RAM shortage. Current MKW generated profile has TEX_FLUSH_UPLOAD=0 and TEX_DIRTY_UPLOAD=0. A /tmp-only build with the existing two CPU-stream tracking mechanisms enabled is being prepared; production profile unchanged pending live proof.

## Eliminated / bounded

- RAM floor: not established; dense rendering also fails.
- Missing native task/mesh commands as sole explanation: disproven by live implementation.
- Stale depth-state cache: not supported by logging probe.
- Ordinary face culling or depth testing as sole explanation: neither isolated override restored the missing terrain.
- Indirect prefix/draw-record builder universally producing zero: controlled shader execution works.
- Vertex-descriptor fetch as sole explanation: the independent manual fetch path also fails with substantial confirmed usage.

## Constraints and validation

No commits or changes to the shared dm/host/dmhost. Preserve background OOT work; frozen FS build source /tmp/mkw-isolated-hle_sf.c is used by /tmp/mkw-nvn2-mesh-build-argv.txt. Game-derived data stays on the external game drive. Current shaders: /Volumes/Data/Switch/Mario Kart World/0400C3F00006E000-work/mesh-20261109/cache/b-cb0cf4544169.

Full graphics suite (101 executables plus Python checks) passed after final runtime fixes. Shader Python suite: 111 tests, two optional skips. Chain tests: 13 passed. Five-title harness blocked by four absent packages. clang-tidy, ruff and pyright unavailable; docs tests retain unrelated failures. These diagnostic runs are not performance acceptance.

## Fix and current verification

- Production profile enables tex_flush_upload and tex_dirty_upload for the observed CPU_CACHED streams.
- Shared tex_cpu_content admits pre-initialization uncompressed data for profiles explicitly enabling CPU streams, with GPU/depth/compressible/linear/sparse exclusions preserved.
- GPU render ownership records actual attachment/copy use on the allocation, instead of render-target capability; views and upgrades preserve it. Explicit shader-write intent and sparse ownership retain protection.
- t_cpu_tex now tests late uncompressed fills after an empty resolve, pre-initialization fills, actual GPU target preservation after CPU writes, and view/upgrade ownership. 75 checks pass in both encoding modes with API/shader validation.
- opening-stream-initial-fixed-20261109-153020: all eight actual 260×260 height tiles contain 67,600 nonzero texels, varied heights. Frames 900/1800/4200 show textured terrain and roads. Probe is bounded and materials/depth/culling are normal.
- Clean exact binary: external work/dmhost-streamed-terrain-fixed-20261109; build fingerprint: streamed-terrain-fixed-20261109-build.json. Current production run opening-terrain-correct-20261109-153351, PID38050, HUD on, copied save, no probe overrides; 120-second proof recording.
- Full graphics suite is running after changes. Five-title harness was retried with authorized scratch Git worktrees; four absent packaged Mac builds block MKW/TotK/FFT/Great Ace Attorney, only Skyrim packaged. Not a pass. No new RAM/performance conclusion yet.

## Final verification

- User feedback on corrected clean run: "They look complete" (road, terrain and scenery).
- Full graphics suite PASS: /tmp/mkw-stream-fixed-graphics-tests-final.log. t_cpu_tex: 75 checks in each encoding mode with API/shader validation; t_nvn: 228 checks after correcting its undersized swapchain fixture. Profile checks: 2 pass.
- Five-title harness blocked by four missing packaged Mac builds; docs tests have three pre-existing failures after updating both generated indexes. No false regression pass.
- Clean production binary/source fingerprint archived externally; live run PID38050 is retained, HUD on, copied save. Checked log has no GPU execution error/assertion. Measurements are not a matched benchmark and 9–10 GB remains unmet.
- The ScreenCaptureKit recording helper stalled before enumeration returned: no new video. Stopped only the 13 stuck helper processes launched for our runs; the game stays running. Run session.json records the capture failure and correct background-preparation settings.
- No commits and no replacement of shared dm/host/dmhost.
