---
status: resolved
trigger: "User authorized Android task/mesh rendering and compressed-texture memory proof after the Mac stability checkpoint."
created: 2026-11-09
updated: 2026-11-09
---

## Bounded objective achieved

Connected Lenovo TB323FU / Adreno 840, API 36, Vulkan 1.4.295, driver build 2c410f6f5c. Native task/mesh draw from synthetic Ampere instructions succeeds; compressed allocation/readback succeeds. No Android game boot, runtime integration or RAM/FPS claim. No app install, global Android setting, shared Mac host replacement or commit. Other dirty work and OOT build are preserved. No agents spawned.

## Implementation and evidence

- New `nxnative/dm/android/tools/nvn2_mesh.py`: workgroup SPIR-V -> spirv-cross Vulkan GLSL -> native EXT task/mesh wrapper. Shared metadata from `dmsh_nvn2_mesh`; native EXIT remains in the body function, so uniform wrapper barriers/emission/output calls execute. Independent descriptor sets, first-group push constants, task-relative child groups, per-primitive output layout. Explicit common payload ABI, default 512 words; caller must check limits. CLI included and tested.
- New `probes/make_nvn2_proof.py`: reproducible synthetic SASS fixtures, optional real .ctl/.area + translated SPIR-V export, matching fragment consumers and reflected descriptor layouts. All game-derived data stays external.
- New `probes/vknvn2.c` + `probes/shaders/nvn2-proof.{frag,comp}`: actual offscreen Vulkan draw/readback. NDK 28.2, API29, -O1 -Wall -Werror. Six raster controls, four compressed formats with allocation/raw/decoded checks, optional real pipeline checks. Ten-second fence waits; destroys owned resources.
- `probes/vkprobe.c` extended with mesh/subgroup limits. Adreno supports task/mesh subgroup stages (mask 0xf0), task payload 16 KiB, task payload+shared 48 KiB, mesh payload+shared 32 KiB, mesh output 32 KiB, 256 vertices/primitives. Largest checked bridge layout with 2 KiB payload fits.
- New `test_android_nvn2_mesh.py`: 3 tests pass, native EXT fixture/CLI compile and SPIR-V validation included. Targeted Ruff 0.15.13 passes (not the pinned full-project ratchet). No production shader-chain change.

Fresh reproducible run: `/Volumes/Data/Switch/Mario Kart World/0400C3F00006E000-work/android-proof-20261109/repro/`. `summary.json`, source snapshots/hashes, exact probe binary, images, capability/build/device logs in parent folder. Dedicated device directory `/data/local/tmp/nxhost-mkw-proof-20261109/repro`. Reproduction instructions `probes/README.md`.

## Results

44 checks, 0 failed: all 26 real programs (7 task, 19 mesh) compile as device pipelines with reflected resources and matching test fragment consumers; they are not dispatched without real game buffers. Translated synthetic native instructions test nonzero first group, payload/relative child group, 31 early EXITs, independent UBO/SSBO stage bindings, negative controls, empty task and zero task count. Triangle pixels are green; negative controls correctly yield red/blue.

BC1 / BC6H UFLOAT / ASTC4x4 UNORM / ASTC8x8 sRGB arrays: 1024², four layers, three mips, byte-exact compressed readback plus varied expected decoded colours. BC6H includes nonzero HDR red near 2.0; ASTC gray tests actual sRGB decode. Bound allocations 2.625 / 5.25 / 5.25 / 1.3125 MiB, equal compressed payload, against 21 MiB RGBA8 (42 MiB RGBA16F). No full-game RAM savings established.

Initial producer-only discard pipeline probe refused 24/26 with VK_ERROR_UNKNOWN. Complete matching fragment consumers yield 26/26; do not label these programs invalid or claim a proven compiler/ISA bug. API validation layer copied only to own temp folder but shell loader cannot discover it (VK_ERROR_LAYER_NOT_PRESENT), so no validation-layer pass is claimed. No system properties changed. SPIR-V validation and GPU readback pass.

MKW/OOT regression harness attempted (narrow reach: only new Switch 2 proof tooling, not existing runtime); both packaged builds absent. Docs retain three pre-existing failures (missing game note, guide length, old Skyrim links), with no new broken links. Index regenerated. `git diff --check` passes.

## Next authorized direction to propose/execute

Android runtime integration is still pending: `shader_vk.py` emits only stages0–5; `gfx_vk_shader.c` stage/set mappings default unknown stages to compute; `gfx_vk_exec.c` uses six-stage resource arrays and has no mesh pipeline/draw dispatch. The proof is isolated and introduces no `android.tsv` or playable-game claim. Wire proper task/mesh stage metadata, descriptor bindings, program/pipeline keys and OP_DRAW_MESH replay, with explicit device capability checks. Verify CPU-streamed height uploads in the Vulkan texture path against the accepted Mac tests. The older Android texture backend has CPU-written tracking, but parity for all initial/uncompressed and late terrain streams needs verification.

Storage remains a distinct integration problem: current Adreno lacks sparse physical-page aliasing and sampled/upload sparse properties for tested BC6H/ASTC formats; sparse address space 4095 MiB. Native compression works for bounded dense arrays, but directly copying Metal's sparse alias strategy is unsupported. Prove a bounded alternative for the large compressed virtual atlases before a full-game allocation/run. Game RAM target 9–10 GB remains open; Vulkan savings unmeasured. Preserve the Mac reference and measurement overlay.

Follow-up: production task/mesh replay and a separate atlas storage prototype are now checked in [mkw-android-runtime.md](mkw-android-runtime.md); its remaining work supersedes this earlier handoff.

Latest: [mapped-atlas runtime checkpoint](mkw-android-mapped-atlas.md) connects supported compressed sampling to actual NVN mappings and passes700GPU checks. Remaining full-game coverage and memory measurement are tracked there.
