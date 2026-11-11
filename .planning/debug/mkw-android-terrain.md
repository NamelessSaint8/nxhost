---
status: resolved
trigger: "Keep going toward a measured Android scene after the mapped compressed-atlas checkpoint."
created: 2026-11-09
updated: 2026-11-09
---

## Bounded checkpoint achieved

Android CPU-streamed terrain initialization and refresh now reach Vulkan images and production sampling while actual GPU-owned data is preserved. All eight captured complete Mac height tiles match. This resolves the tested terrain prerequisite, not the full Android port or the 9–10GB target. No full game launch or Android RAM/FPS claim.

No agents, commit, app installation, Android global setting change, Mac profile or shared host replacement. Accepted Mac binary/overlay and unrelated/OOT work are preserved. Game-derived evidence remains external. Only temporary standalone device executables were used.

## Root cause and fix

- The previous Vulkan backend lacked the initial nonzero storage admission and first-use nvn_ft_written path. A CPU fill before initialization has no later write stamp; an unflushed fill after initialization needs shared dirty registration to be resolved. mtl_tex_gpu_owned always returned0, so polling could also replace real GPU data with stale pool bytes.
- gfx_vk_tex.c now checks dirty registration and initial CPU-accessible storage once per serial. Existing profile controls admit uncompressed CPU streams. Sparse/linear/depth/image/compressible/buffer/multisample resources retain their existing distinct paths. Native compressed first-use storage has the same admission rule as the Mac.
- Shared storage-key construction is reused for ownership lookup. Actual GPU destination writes and shader-writable usage protect GPU content; render capability alone does not. CPU-backed images subsequently cleared/copied/rendered keep the later GPU data.
- First CPU classification bumps the texture generation to invalidate descriptors. Live serial identities are freed at TextureFinalize. Only CPU classification/pool metadata survives for command snapshots; pool finalization frees live/retired entries and empty hash backing. initial_cpu_serial on the image avoids recreating identity records for finalized snapshots.
- New probes/vknvn2_terrain.inc is part of the existing real backend replay. It tests initialization, late polling, GPU preservation, storage sharing, snapshots, metadata lifetimes and optional real captured inputs. No shader translation chain or Mac renderer change was needed.

## Accepted verification

Device Lenovo TB323FU / Adreno840 / API36 / Vulkan1.4.295, driver2c410f6f5c. NDK28.2.13676358/API31. Isolated output /tmp/nxhost-android-terrain-runtime; shaders /tmp/nvn2-terrain-shaders; owned device directory /data/local/tmp/nxhost-mkw-terrain-20261109.

- Frozen pre-fix executable:91checks,60failures. The failure is established before changing the backend; it includes missing initial/late fills and corrupting GPU-owned content. Control sources and binary are retained.
- Final executable:120/120terrain checks pass. Synthetic103checks cover260×260R16/RG16/R8, both GOB orders, before-init/first-use/late/repeat fills, actual GPU clears, shader-writable storage, storage-sharing aliases, CPU-backed targets after GPU writes and finalized snapshots. 12000unfilled initialize/finalize cycles retain no additional identity records. Each pool cleanup leaves0tracking entries.
- Actual game inputs: opening-stream-initial-fixed-20261109-153020/height-inputs,8raw152064-byte block-linear sources and8Mac GPU row captures. All540800R16texels match;64production shader fetch samples match too. All8use the same storage slot successively, verifying new API objects over reused storage. The capture header stores Metal format20, not NVN format6; the probe reader was corrected before accepted results. Earlier capture-reader abort is not accepted evidence.
- Final same executable:700/700mapped-atlas checks and9/9draw checks pass. All194production Android sources compile; the fixture compiles with-Wall-Werror. Eight Python shader tests pass with translator/GLSL/SPIR-V tools present; targeted Ruff0.15.13 with repository config passes, not the unavailable pinned0.17.2/Pyright ratchet. git diff --check passes.
- API validation layer remains unavailable to shell loader; actual GPU readbacks and SPIR-V validation pass. Five-title Mac boot preflight requested MKW, TotK, FFT, Great Ace Attorney and HadesII because of CPU-stream/linear/ownership semantics. All five packaged Mac builds are absent (only Skyrim found); not a boot pass. Documentation suite retains three prior failures: missing0100005027A18000note, guide05length6242>6000, existing missing note/old Skyrim links. Symptom index regenerated to758. No new link failures. No auto-review rejection.

Exact binaries, source/dependency hashes, build flags/generated headers, fixture bundle, real capture provenance and logs: /Volumes/Data/Switch/Mario Kart World/0400C3F00006E000-work/android-terrain-20261109/. Reproduction is in probes/README.md#cpu-streamed-terrain-upload-parity. The old mapped-atlas checkpoint and its exact artifacts remain available separately.

## Remaining work

Measured follow-up: [Android measurements](mkw-android-measurements.md) records a repeated timing/memory comparison, faster atlas refresh, bounded pool restoration and expanded856-check version coverage. This terrain checkpoint remains accepted; full Android gameplay/RAM/FPS are still open.

The full Android game has not launched; no android.tsv exists yet. [Driver-state parity](mkw-android-driver-state.md) is now checked. Next cover actual shader sampling, mesh/fragment interfaces (the26native keys lack static variation pairs), and typed colour outputs. Terrain parity here is for captured input uploads/readback/sampling; it is not a full terrain scene or every upload-order/alias case.

After prerequisites, add the Android profile and attempt a bounded game scene with the existing measurement/platform overlay. Measure full process memory, startup and frame stalls against the complete Mac reference. The9–10GBtarget and broader memory/stall investigation remain open in mkw-memory-growth.md.
