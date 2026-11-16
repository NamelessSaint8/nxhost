# Bounded Android Vulkan proofs

`vk_compute_replay.c` replays one raw compute capture from the Android host.
Set `DM_VK_CAPTURE_CS=<shader key>#<minimum present>` and `DM_ROOT` on a debug
host. The first matching dispatch saves `capture_<key>_<present>.tsv` and raw
binding files: GPU-visible buffers, CPU storage-buffer bytes, sampled/storage
texels, sampler parameters, and storage results. Copies immediately bracket the
dispatch, preserve packed bits, and synchronize readback. Capture perturbs
scheduling and is a diagnostic mode.

Version 1 accepts direct dispatches with buffers and single-level, single-layer
uncompressed 2D colour images. Unsupported descriptors, shapes and module
variants fail explicitly. Extract the translated SPIR-V from the same DMSV;
its bindings remain unchanged. Keep game-derived inputs and outputs in the
game's external work folder. Build the runner with NDK clang and
`-O2 -Wall -Wextra -Werror -lvulkan`, then run:

```sh
vk_compute_replay capture_prefix shader.spv output_prefix pipeline_cache.bin
# Optional final arguments select the first gx, gy, gz workgroups:
vk_compute_replay capture_prefix shader.spv output_prefix pipeline_cache.bin 1 1 1
```

The runner saves storage bindings and a pipeline cache, uses a ten-second GPU
fence timeout, and exits nonzero on failure. Compare raw outputs and inspect
the result separately; successful execution alone does not establish correctness.

`make_warp32_proof.py` and `vk_warp32.c` check translated Ampere lane IDs,
LDSM loads, MOVM shuffles, MATCH ballots, REDUX sums and HMMA F16 results on wider Vulkan
subgroups. Build fixtures with `python3 probes/make_warp32_proof.py "$PROBE_OUT"`,
compile the runner with NDK clang and `-lvulkan`, push that folder, then run
`vk_warp32 <device folder>`. CPU references cover both 32-lane warps of a
`32x2x1` workgroup. HMMA additionally checks either result used alone and reads
the out parameter before the returned value, catching IR liveness and AST call
ordering/removal bugs. Compile checks precede dispatch so undefined scratch
inputs are never submitted. Varied lane fragments and accumulators also match
an independent CPU matrix product. A transposed LDSM case verifies byte addressing
and the transpose's row/column layout. The complete run has sixteen checks. Safe legacy controls must reproduce the old upper-warp
errors on wave64; the legacy HMMA path is never dispatched because its scratch
accesses can exceed their array. Each submission has a ten-second fence timeout.

Add `--hmma-lds` to build twenty cases with the Android matrix lowering, including
dependent tile reuse, aliased input/output fragments, fractional halves and
subnormals. Use the current `vk_warp32.c` runner. Integer products match an
independent CPU matrix reference exactly. Fractional cases compare every word
against a separately compiled scalar GPU helper and check its CPU-reference
error is at most one half ULP; subnormals compare bit for bit with that scalar
GPU helper, preserving the driver's existing conversion behavior. The manifest's
mode is 0 for a CPU reference, 1 for a safe legacy negative control, 2 for a
scalar GPU reference and 3 for a scalar GPU reference plus the CPU precision
bound. `--hmma-reference` builds the additional cases without lowering.

`make_ampere_scoreboard_proof.py` builds eleven synthetic guarded deferred-write
cases for the same `vk_warp32` runner. Generate them with
`python3 probes/make_ampere_scoreboard_proof.py "$PROBE_OUT"`, push that folder,
and run `vk_warp32 <device folder>`. Cases cover regular and inverted predicates,
predicates changed after issue, a guarded-off reissue preserving an earlier
pending result, and different predicates in the two logical warps. Every word
must match the independent CPU register values. Seven cases fail with the old
unconditional deferred commits. `test_ampere_scoreboard.py` also checks nine
constant-predicate programs through independent GLSL constant folding; set
`DMSH_TEST_XLATE` to the translator executable to enable it.

For a missing-text investigation, `DM_VK_TEXDUMP=<width>x<height>` selects the
first sampled image with those dimensions; the existing `poolhex+offsethex`
selector remains available. Use it alongside `DM_VK_PASSDUMP` and a bounded
`DM_VK_PASSDUMP_SIZE` to distinguish a valid font atlas from a blank glyph target.
R8 readbacks appear in the red channel. `DM_VK_UBO_LOG=<shader key>#<count>` plus
the presence of `DM_VK_UBO_DUMP` saves up to 4,096 bytes per uniform/storage-buffer
diagnostic under `DM_ROOT`, as `ubo_<key>_<present>_<sequence>_s<stage>_r<reg>.bin`.
Storage-buffer register numbers have 16 added. These are CPU/deferred-uniform
snapshots, not evidence of GPU-only buffer contents. Keep them on the external
game drive and use exact shader/count limits. `DM_VK_SHOT` schedules specific
presents; live `DM_VK_SHOTS` is a count of consecutive captures, not a present.

`vk_storage_usage.c` uses the renderer's image-usage helper and checks actual
compute writes and byte readback through UNORM views of both UNORM and sRGB
images, including a restricted format list. Compile
`probes/shaders/storage-usage.comp` with `glslangValidator -V --target-env vulkan1.2`,
build the runner with NDK clang and `-lvulkan -lm`, and pass the compiled shader
path to it. Three cases must report zero bad pixels; submissions have a
ten-second fence timeout.

`vknvn2.c` checks actual translated NVN2 task/mesh execution and compressed image
storage on an Android Vulkan device. It creates no window or installed app and
does not start a game. The required features are task/mesh shaders, BC and ASTC
LDR compression, and a graphics/compute queue. Use a dedicated temporary device
folder; the proof leaves its pixel images there for inspection.

Build synthetic shaders and the probe (the NDK directory and output folder are
explicit; keep game-derived outputs on the external game drive):

```sh
PROBE_OUT="/path/on/external/drive/android-proof"
NDK_BIN="/path/to/android-ndk/toolchains/llvm/prebuilt/darwin-x86_64/bin"
python3 probes/make_nvn2_proof.py "$PROBE_OUT"
"$NDK_BIN/aarch64-linux-android29-clang" -O1 -Wall -Werror \
    probes/vknvn2.c -o "$PROBE_OUT/vknvn2" -lvulkan -lm
```

The builder needs the repository's native `dmsh_xlate` and `spirv-cross`, plus
`glslangValidator` and `spirv-val` on PATH. To include real-program pipeline
checks, add `--real-mesh /external/stage-export` to the builder. That export has
`<key>.ctl`, `<key>.area`, and `translated/<key>.spv` produced by the existing
stage-buffer translator. Reflected layouts and matching test fragment consumers
are generated for those pipelines. The real programs are compiled, never
dispatched with fabricated game buffers.

```sh
DEVICE_PROOF="/data/local/tmp/nxhost-nvn2-proof"
adb shell mkdir -p "$DEVICE_PROOF"
adb push "$PROBE_OUT/vknvn2" "$DEVICE_PROOF/vknvn2"
for proof_file in "$PROBE_OUT"/*.spv "$PROBE_OUT"/*.layout.tsv "$PROBE_OUT/real-stages.tsv"; do
    adb push "$proof_file" "$DEVICE_PROOF/"
done
adb shell "$DEVICE_PROOF/vknvn2" "$DEVICE_PROOF" "$DEVICE_PROOF"
```

The default synthetic run has 18 checks. A Mario Kart World export adds 26
pipeline checks, for 44 total. A failure exits nonzero. Submitted work has a
10-second fence timeout. The run verifies:

- Direct mesh and task/mesh raster pixels from synthetic Ampere instructions,
  nonzero first groups, task payloads, and 31 early-exiting invocations.
- Independent task/mesh UBO/SSBO bindings, negative binding controls, empty tasks
  and zero task counts.
- BC1, BC6H UFLOAT, ASTC 4x4 UNORM and ASTC 8x8 sRGB arrays, each four layers and
  three mips, with byte-exact compressed readback and expected decoded colours.
  BC6H includes nonzero HDR values; ASTC gray distinguishes linear/sRGB decoding.
- The bound image allocation size versus compressed payload and RGBA8 storage.

`DM_VK_VALIDATE=1` requests `VK_LAYER_KHRONOS_validation` and counts API errors
when that layer is discoverable. Android shell loaders may not discover a layer
from `LD_LIBRARY_PATH`/`VK_LAYER_PATH`; `VK_ERROR_LAYER_NOT_PRESENT` is a failed
validation attempt, never a validation pass. On the tested TB323FU, a diagnostic
LD_PRELOAD shim can instead call the platform's GraphicsEnv::setLayerPaths for
this process alone. Source and exact binary are archived in the external game's
`android-game-20261110/validation-tools/`. This private platform ABI helper is
for diagnostics; it is not shipped in an APK. Set `NXHOST_LOCAL_LAYER_PATH` to
the owned directory containing the official Khronos layer and preload the shim.
Require `validation layer on` and zero `validation error:` lines as well as
passing GPU checks. No system properties need to change.

The shared metadata decoder comes from the Mac mesh path; Vulkan uses an
explicit common payload ABI (default 2 KiB). A runtime must query device limits
and choose compatible payload/shared/output sizes and stage interfaces. The original standalone proof does not establish game RAM/FPS or playable-game status.
The production replay and separate storage prototype are checked below.

Host shader-generation regression:

```sh
DMSH_TEST_XLATE="$PWD/nxnative/dm/gfx/tools/dmsh_xlate_bin/dmsh_xlate" \
    python3 -m unittest nxnative/dm/gfx/tests/test_android_nvn2_mesh.py
```


## Production command replay

`vknvn2_replay.c` links the real Android host/backend objects. Its synthetic
shader-key lookup replaces guest program input; its NVN command records exercise
production bindings, pipelines, draw dispatch and readback. It needs no game files.

```sh
NDK="/path/to/android-ndk"
REPLAY_OUT="/path/to/isolated/replay-proof"
python3 probes/make_nvn2_replay.py "$REPLAY_OUT" --ndk "$NDK"
adb shell mkdir -p /data/local/tmp/nxhost-replay-proof
adb push "$REPLAY_OUT/runtime/vknvn2_replay" "$REPLAY_OUT/replay.dmsv" /data/local/tmp/nxhost-replay-proof/
adb shell 'cd /data/local/tmp/nxhost-replay-proof && chmod 700 vknvn2_replay && ./vknvn2_replay replay.dmsv'
```

The build helper currently selects the macOS NDK host tools. `--build-out` reuses
an isolated build folder; `--game` selects its host profile (default MKW), without
loading a game. Ten GPU readbacks cover padded vertex inputs, direct and task mesh, empty/zero draws,
separate task/mesh bindings with negative controls, per-primitive fragment inputs,
a conventional vertex draw afterward and oversized-launch rejection. The per-primitive
fragment starts as SPIR-V 1.0 to exercise the runtime's mesh-qualification upgrade.
An optional `vknvn2_replay bundle.dmsv --load-only` checks bundle/runtime metadata
and creates shader modules and descriptor layouts without dispatch.
Keep game-derived bundles external and explicitly identify load-only results.

`--atlas-checks` measures 1,000 descriptor lookups over a 1 GiB logical array
and verifies CPU-write, remap and hole versions through GPU reads before one
fence. It also checks physical-pool retirement and far mapped pages after holes. Compare
`DM_VK_ATLAS_CHECK_CACHE=0` with `1`; the default enables caching. Ten checks
pass under Vulkan validation. This isolates descriptor CPU cost, not game FPS.

`--lazy-pools` checks deferred cached-pool buffers: initial bytes, first GPU
binding, CPU/GPU writes, overlaps, finalization and reuse. Run it both normally
and with `DM_VK_NO_ZEROCOPY=1` to exercise copied-buffer promotion. Both paths
pass thirteen checks. Enable `DM_VK_LAZY_CACHED_POOLS=1`; optional file backing
also requires `DM_VK_CPU_BACKING=file` and a private writable `DM_TEMP` folder.

`--lazy-all-pools` enables `DM_VK_LAZY_POOLS=1` and runs the same checks across
seven pool flag classes: 91 checks, both normally and with forced copies.
`--copied-bindings` uses a timeline semaphore to prove that unbound copied
storage does not drain unrelated GPU work. Six checks also cover initial data,
GPU writes in the first used submission and finalization.

`--ownership-checks` compares `DM_VK_OWNERSHIP_CACHE=0` and `1` over 1,024 real
images. Thirteen checks include repeated/alternating aligned ranges, a GPU
clear, overlapping aliases, storage-image creation, sparse remaps, pixels and
retirement. The fixture enables page-table mode itself. Timings isolate CPU
queries; they do not measure game frame rate.

## Implicit atlas sampling

The production replay now has 24 synthetic shaders. Build as described above,
then run the pixel comparison in its owned temporary device folder:

```sh
adb shell 'cd /data/local/tmp/nxhost-replay-proof && ./vknvn2_replay replay.dmsv --implicit-atlas'
```

The 2,166 checks comprise 198 byte-exact reference mip/layer readbacks and 1,968
cases comparing every pixel of a 32×32 float target. Dense and virtual inputs
contain identical native BC6H/ASTC blocks. Cases cover both GOB orders, filtering,
LOD limits, bias, view ranges, wrapping, zero derivatives and dense fallback.
The output target is cleared to a failure sentinel before each draw. Reference
inputs must be marked as prepacked data and verified before colour comparisons.

A shader-only control replacing the logical/physical coordinate scale with 1
must fail 1,680 checks. Preserve shader bundles and exact executable hashes.
Run the existing driver, atlas, terrain, draw and restoration checks on the same
candidate. Use alternate fresh `--measure` processes for the explicit-atlas
regression workload; it does not measure the new fragment path's game GPU cost.

DMSV flag bit 2 selects fragment atlas metadata v2, including the device LOD-bias
limit. Older runtimes must reject it with `unsupported entry flags`. Fragment
helpers retain functions in SPIR-V; other stages keep their existing compiler
path. Independently validate converted real modules and check reflected bindings.
For shader storage comparisons, load identical program sets in alternate fresh
processes with `/system/bin/time -v`; peak RSS is not a gameplay working set.
No game texture data or sampling operation is discarded.

The complete evidence and reproduction scripts live externally in
`android-implicit-20261110/`; see [results and limits](../nxnative/dm/games/0400C3F00006E000/README.md#android-implicit-atlas-sampling-2026-11-10).

## Real Android shader and pipeline audit

Keep all game-derived bundles, reports and validation inputs on the external game
drive. The full-bundle audit checks actual sampled/shadow/storage image operations
and reports basic interfaces for observed native stage combinations:

```sh
GAME_WORK="/external/game-work/android-interfaces"
python3 probes/audit_android_sampling.py "$GAME_WORK/full.dmsv" \
    --out "$GAME_WORK/sampling.json" \
    --pipelines "$GAME_WORK/observed-pipelines.json" \
    --validate "$GAME_WORK/validated"
```

The optional observed-pipeline JSON has a `pipelines` array with `task`, `mesh`
and `fragment` hexadecimal shader-key strings; task is null when absent. Keep the
source run logs and their hashes beside it. Validation uses `spirv-val` for
Vulkan1.2 with four workers. A report without `--validate` records zero modules
validated and a null validation-failure count. Instruction-site counts describe
assets, not runtime frequency or performance.

For a compile-only device check, put the selected real programs in a DMSV subset
and their combinations in a three-column hexadecimal TSV: task (0 if absent),
mesh, fragment. Use the production replay executable:

```sh
adb shell 'cd /data/local/tmp/nxhost-replay-proof && ./vknvn2_replay observed.dmsv --pipelines=observed-pipelines.tsv'
```

This compiles real stage combinations using production modules, descriptor
layouts and per-primitive fragment variants, with a minimal RGBA8 render pass.
It dispatches no game shader and does not validate actual game attachments,
blend/depth combinations or rendered output. Per-call compilation timings are
not gameplay frame times.

The synthetic builder now emits 24 shaders. The default replay has ten pixel
checks, adding missing float/signed/unsigned inputs and repeated output types.
An isolated shader control restoring only the wrong vec2/vec3 defaults must fail
the `padded-inputs` case with a literal red pixel; the corrected output is green.
Host checks: `test_android_pad.py` and `test_android_sampling_audit.py`, alongside
the existing Android mesh/atlas tests. See [results and limits](../nxnative/dm/games/0400C3F00006E000/README.md#android-shader-and-interface-coverage-2026-11-10).

## Android driver-state replay

Build the production replay and its synthetic bundle as described above, then
copy the executable and `replay.dmsv` into the owned temporary device directory.
The current builder generates 24 shaders and independently validates their SPIR-V.

```sh
DEVICE_REPLAY="/data/local/tmp/nxhost-replay-proof"
adb shell "cd $DEVICE_REPLAY && ./vknvn2_replay replay.dmsv --driver-state"
```

The 102 checks cover separate graphics/compute c24 state, partial byte updates,
immutable descriptor snapshots, high uniform slots, classic/NVN2 direct counts,
zero counts and GPU-produced indirect arguments. Indirect tests rewrite the same
argument address and include deferred CPU uploads. Graphics, task and mesh push
state has literal pixel checks and negative binding controls. A formatless R32F
image write/read also checks actual image content and logs device feature bits.

Each of `--driver-reject-push`, `--driver-reject-truncated`,
`--driver-reject-groups`, `--driver-reject-address` and
`--driver-reject-unaligned` must stop nonzero with the corresponding explicit
record/count/address error. These are expected abort controls, run separately.
An entry with an unknown DMSV flag must fail `--load-only` with
`unsupported entry flags`; valid entries still load.

DMSV entry flag bit 0 selects the native task/mesh trailer; bit1 records the NVN2
ABI. Bit 2 marks fragment atlas metadata v2. Native entries with legacy bit 0 alone remain accepted. Rebuild old unmarked
NVN2 compute bundles to receive bit 1. The production helper adds missing
formatless image capability declarations without changing executable instructions.
Independent `spirv-val --target-env vulkan1.2` and actual GPU readbacks are required;
module creation alone is insufficient. This does not claim an API-layer pass.

Run atlas, terrain, ordinary draw and restoration regressions on the same final
binary. Repeat `--measure` in alternate fresh processes and preserve first use
separately. Evidence and controls are archived externally under
`android-driver-state-20261109/`; see [results and limits](../nxnative/dm/games/0400C3F00006E000/README.md#android-driver-state-parity-2026-11-09).

## Measured Android atlas refresh

The same replay build supports `--measure`. It creates a native BC6H virtual
atlas with 512 distinct 64 KiB mapped cells and 30 extra source cells. Logical
storage is 6,087,507,968 bytes; only the small mapped working set is populated.
Jobs perform four sampling/query operations through production descriptors,
validate their results and wait for completion. This is not a gameplay frame.

```sh
adb shell 'cd /data/local/tmp/nxhost-replay-proof && ./vknvn2_replay replay.dmsv --measure' > run.csv 2> run.log
```

Each fresh process records one first-use job, 60 unchanged jobs, 30 remaps to
existing content and 30 new-content mappings. `DM_MEASURE_CELLS` (1–1024) and
`DM_MEASURE_FRAMES` (10–1000) change workload size; use more than ten unchanged
jobs when comparing after the ten-job warmup. Raw CSVs contain CPU wall/thread
preparation, submission and wait times in nanoseconds, main-command GPU
timestamps, process RSS/HWM/PSS/SwapPSS in KiB, native atlas image/staging current
and peak allocation bytes, upload bytes, table bytes and cell sharing counts.
Unavailable process counters are reported as -1, and the summary refuses them.
Timestamp validity is checked against the actual queue's bit width; missing
completed results fail the run. GPU times exclude the atlas's separate private
upload submissions. Source setup and cleanup are recorded separately in comments.
VmHWM includes pool teardown; the final comment records memory after workload
mappings are unmapped. Other backend scratch/pool/driver memory is excluded from
atlas allocation counters. Do not add RSS/PSS and Vulkan allocation bytes.

Compare alternate fresh-process runs, preserving the exact executables and CSVs:

```sh
python3 probes/summarize_nvn2_measure.py \
    --baseline baseline-1.csv baseline-2.csv \
    --candidate candidate-1.csv candidate-2.csv --out comparison.json
```

The summary validates workload equality, phase/iteration structure, completed
cleanup, finite counters and zero content uploads in unchanged/reuse phases.
It retains per-run medians and p95 instead of treating all rows as independent
experiments. First ten unchanged jobs are excluded; first use is kept separately.
The accepted baseline/candidate/candidate/baseline comparison and the exact
control builder are archived in the external game work folder's
`android-measure-20261109/`. See [results and limits](../nxnative/dm/games/0400C3F00006E000/README.md#android-atlas-measurements-2026-11-09).
No gameplay FPS or full-game RAM is inferred from these samples.

`--restore-check` additionally verifies CPU patterns and GPU writes across five
pool sizes around page/64 KiB chunk boundaries. The benchmark verifies all
35,520,512 source bytes and 65,536 GPU output bytes after finalization. The final
candidate restores pools with bounded scratch, reducing teardown high-water
memory in the fixture; persistent process working-set savings remain unproven.

The expanded atlas suite now has 856 checks. It changes content repeatedly within
one unsubmitted batch while image capacity remains available, verifying that
every metadata revision protects its new cells. The earlier baseline fails 24;
an isolated candidate control removing only revision-aware fence tagging fails 64;
the corrected candidate passes all 856, plus 120 terrain and 9 draw checks.

## CPU-streamed terrain upload parity

The replay build also includes `vknvn2_terrain.inc`. It uses real NVN pool/texture
initialization, dirty polling, finalization and Vulkan image readback, without
starting a game. Build/copy the combined replay executable and bundle as above.

```sh
adb shell 'cd /data/local/tmp/nxhost-replay-proof && ./vknvn2_replay replay.dmsv --terrain'
```

The synthetic run has 103 checks: 260×260 R16, RG16 and R8 in both GOB orders,
prefilled storage, unflushed first use, late fill after empty resolution, repeated
refreshes, actual GPU ownership, compatible storage-sharing objects, CPU-backed
images subsequently written by the GPU, shader-writable images, queued snapshots
after finalization, and metadata cleanup. Twelve thousand unfilled object
initialization/finalization cycles keep the identity-record count unchanged.
Each completed pool releases all tracking records. The pre-fix binary failed
60 of the original 91 common checks; its frozen baseline is retained externally.

For the actual Mario Kart World height inputs, use the sixteen saved files from
the accepted Mac opening's `height-inputs` directory: `height-0-source.bin` through
`height-7-source.bin` and `height-0.bin` through `height-7.bin`. Keep these derived
game files on the external game drive and in the dedicated device proof folder.

```sh
CAPTURES="/external/game-work/opening-stream-initial-fixed-20261109-153020/height-inputs"
adb shell mkdir -p /data/local/tmp/nxhost-replay-proof/captured-height
for height_file in "$CAPTURES"/height-*.bin; do
    adb push "$height_file" /data/local/tmp/nxhost-replay-proof/captured-height/
done
adb shell 'cd /data/local/tmp/nxhost-replay-proof && DM_TERRAIN_CAPTURE_DIR=./captured-height ./vknvn2_replay replay.dmsv --terrain'
```

This adds seventeen checks (120 total): all 540,800 R16 texels must match the
saved Mac GPU row captures, plus 64 shader fetch samples and final pool cleanup.
The raw sources are native block-linear 152,064-byte tiles. The GPU capture
header is `260 260 20 768`: width, height, **Metal** format20 (R16Unorm), row bytes.
The corresponding NVN builder uses R16/0x6, MINIMAL_LAYOUT and a CPU-cached,
GPU-cached pool. The real sampling check goes through production descriptors
and an array view of each ordinary 2D tile. A missing/malformed supplied capture
is an error; without the environment variable only synthetic checks run.

Latest tested device: Lenovo TB323FU / Adreno840. The same final binary passes
the nine draw checks and 856 mapped-atlas checks. These offscreen upload/sampling
results do not establish full Android game rendering, RAM or FPS. See the
[game checkpoint](../nxnative/dm/games/0400C3F00006E000/README.md#android-terrain-upload-parity-2026-11-09).

## Production mapped compressed atlases

The same replay binary now links `gfx_vk_atlas.c`. `--atlas` enables
`DM_VK_ATLAS=1` before backend initialization, then uses actual NVN pool/map APIs,
texture registration and production descriptors/dispatch/readback. Its combined
fixture bundle is built with the production atlas GLSL transformation and includes
the ordinary draw fixtures. This is an offscreen backend check, without a game.

After building and copying the replay binary and bundle as above:

```sh
adb shell 'cd /data/local/tmp/nxhost-replay-proof && ./vknvn2_replay replay.dmsv --atlas'
```

The current suite has 856 checks, independent CPU-reference samples and a nonzero
exit on failure. It covers patterned BC6H UFLOAT, ASTC4x4 UNORM and ASTC8x8 sRGB in
both native GOB orders; rectangular dimensions, tails, seams, fractional LOD,
nearest/linear/mip filtering, repeat/clamp, LOD bounds, swizzles and view-relative
queries. Mapping, unmapping and source changes are recorded before submission to
check immutable versions. Growth uploads exceed the private 8 MiB staging buffer;
eighty replacements check cell reuse; idle eviction/reload checks that content is
recoverable, and pool finalization checks owned backing release. A dense texture
also checks that metadata-zero sampling retains ordinary native sampler modes.

The fixture's largest logical NVN storage is 6,087,507,968 bytes, but it populates
only a small synthetic working set. Completed cache image plus private staging
allocation was 20 MiB on Adreno 840 and zero after pool cleanup. This count excludes
page-table/general scratch, NVN pools and driver allocations. Neither this number
nor the logical image size estimates full-game RAM, FPS or startup time. Growing
images can temporarily retain old generations until submission completion.

These controls must fail nonzero with the named explicit reason:

```sh
adb shell 'cd /data/local/tmp/nxhost-replay-proof && ./vknvn2_replay replay.dmsv --atlas-reject-partial'
# partially mapped compressed atlas cells need subpage coverage support
adb shell 'cd /data/local/tmp/nxhost-replay-proof && ./vknvn2_replay replay.dmsv --atlas-reject-sampler'
# atlas sampler/view mode is not implemented
adb shell 'cd /data/local/tmp/nxhost-replay-proof && ./vknvn2_replay replay.dmsv --atlas-reject-buffer'
# sparse virtual buffer access is not supported by the atlas sampling path
```

Production bundles opt in with `shader_vk.py --virtual-atlas`, paired with runtime
`DM_VK_ATLAS=1`. Native compressed 2D arrays with complete 64 KiB cells or holes
are supported for direct explicit-LOD/fetch/size/level operations, at most 16 mips,
nearest/linear/mip filtering, clamp-edge/repeat and LOD bounds. Implicit/gradient/
gather/offset operations, sampler descriptor arrays, partial mapped cells,
anisotropy, nonzero bias, mirror/border, comparison/reduction and reinterpretation
are rejected. Sparse writes/copies/attachments, uncompressed sparse textures and
direct virtual buffers remain unsupported. Do not enable this as a complete game
renderer or interpret rejection as a missing-texture fallback.

The nine ordinary draw checks now read the actual high task/mesh driver storage
slots. An isolated control restoring the old bank-zero hash end (`0x648` instead
of task/mesh `0x870`) fails two of nine; the corrected binary passes all nine.
The exact control source/build script is archived with the
`0400C3F00006E000-work/android-mapped-atlas-20261109/` evidence. All 26 real task/mesh
programs build and load with atlas metadata for four texture bindings, without
dispatching real game buffers. Exact shader selection/build arguments are saved
in that folder's `build-argv.json`; keep derived bundles on the game drive.

```sh
DMSH_TEST_XLATE="$PWD/nxnative/dm/gfx/tools/dmsh_xlate_bin/dmsh_xlate" \
    make -C nxnative/dm/gfx/tests GAME=0400C3F00006E000 check_test_android_shaders
```

The eight Python tests check native task/mesh generation and atlas compiler
rejection/reflection. With the translator and GLSL tools available, they compile
fixtures and run `spirv-val`; unavailable tools cause the compile checks to skip,
which is not a compile-validation pass. The Android shell's unavailable API layer
limitation described above still applies.

## Compressed virtual-atlas storage prototype

`vkatlas.c` queries dense image requirements without allocating those images,
then samples a logical 8192×8192×68-layer, 14-mip BC6H image using a page table
and four physical 128×128 tiles. The tile contents are synthetic constant colours.

```sh
"$NDK/toolchains/llvm/prebuilt/darwin-x86_64/bin/aarch64-linux-android29-clang" \
    -O1 -Wall -Werror probes/vkatlas.c -o "$REPLAY_OUT/vkatlas" -lvulkan -lm
glslangValidator -V --target-env vulkan1.2 probes/shaders/virtual-atlas.comp \
    -o "$REPLAY_OUT/virtual-atlas.comp.spv"
spirv-val --target-env vulkan1.2 "$REPLAY_OUT/virtual-atlas.comp.spv"
adb push "$REPLAY_OUT/vkatlas" "$REPLAY_OUT/virtual-atlas.comp.spv" /data/local/tmp/nxhost-replay-proof/
adb shell 'cd /data/local/tmp/nxhost-replay-proof && chmod 700 vkatlas && ./vkatlas .'
```

Twenty-two CPU-reference/GPU comparisons check bilinear tile boundaries, trilinear
mips, array layers, mip tails, clamp-to-edge and an ordered page remap that leaves
another alias unchanged. On Adreno 840: 65,536-byte compressed image allocation,
1,487,296-byte page table, 65,536-byte staging and 352 bytes of query/result data
(384 bytes bound after alignment). Total bound image/buffer memory is 1,618,752 bytes,
excluding driver/pipeline overhead.
This historical prototype proves bounded addressing/filtering/remapping. The
[production mapped-atlas replay above](#production-mapped-compressed-atlases)
adds NVN mapping integration, residency/eviction and concurrent versions for its
explicitly supported modes. Neither fixture's cache size is a game working-set
estimate. This separate prototype does not replace native game texture accesses.

## Offset, gather and typed attachments

The current synthetic bundle contains 26 programs. Build it with
`make_nvn2_replay.py` as above and run:

```sh
./vknvn2_replay replay.dmsv --offset-atlas
./vknvn2_replay replay.dmsv --fragment-outputs
./vknvn2_replay replay.dmsv --implicit-atlas
```

Offset/gather runs 15,750 checks: 198 compressed-reference byte checks plus
15,552 cases of 1,024 pixel comparisons. Twelve operations cover explicit,
implicit and fetch offsets, default/selected components, and single/four offsets.
Three compressed formats, both GOB orders, filters, clamp/repeat, three views and
three LOD/bias setups exercise logical mip selection and base-mip gather rules.
Native fallback calls preserve local constant operands. The atlas remains
opt-in; gradient, shadow, descriptor-array and unsupported sampler/storage modes
retain rejection.

Fragment exports run 88 checks: 27 numeric-class combinations over three MRTs,
a narrow R8 unsigned case, return to float outputs, and the 26-entry module cache.
Readback checks raw export bits, including component reads/writes. The host test
compiles the exact runtime transform with sanitizers and validates its SPIR-V.
`probes/spv_outputs.c` exposes that transform for independent real-program checks.

Capture actual Mac attachments in a bounded run using
`DM_NVN_PASSDUMP=every:300 DM_NVN_PASSDUMP_ALL=1`. Keep derived files externally:

```sh
python3 probes/extract_nvn2_attachments.py "$GAME_WORK/reference/run.log" "$GAME_WORK/attachment-proof"
./vknvn2_replay observed.dmsv --pipelines=observed-attachments.tsv
```

The extended TSV includes attachment types, samples, blend factors/operations,
depth test/write/compare, culling and write mask. Three-key TSVs retain the
previous minimal RGBA8 pass. The extractor supports one color target with
optional depth and rejects unrepresented captured states. It joins the latest
draw state before each mesh marker, including programs sharing a pass. Metal
format 260 loses original depth precision, so both D24S8 and D32S8 are checked.
R8Uint is represented by R8UI to match its observed numeric type. Real programs
are compiled without invented game buffers or dispatches; synthetic readback
checks actual export behavior separately.

The MKW checkpoint records 1,005 native draws, twelve contexts and fourteen
passing pipeline cases. All 21 real offset/gather programs convert, validate and
load. Deliberately ignoring filter offsets or reversing gather order fails
3,440 and 5,328 checks respectively. Exact sources, binary hashes, control
bundles, raw logs and reproduction scripts live in external
`0400C3F00006E000-work/android-offset-20261110/`. These backend checks do not
establish API-validation-layer coverage or full-game RAM/FPS.


## Full-game sparse storage and native indirect counts

The current replay has 33 synthetic shader programs. Build with `make_nvn2_replay.py` and use these additional modes:

| Mode | What it verifies | Adreno 840 checks |
|---|---|---:|
| `--sparse-depth` | D16/D32F/RGBA8SNORM pixels, mips/layers, CPU changes, holes, remaps, same-fence versions and GPU clears | 246 |
| `--uncompressed-atlas` | R16/RG16/RGBA8/RGBA8SNORM through native 2D and array samplers, aliases, partial-page holes, edge clamping and bounded backing | 400 |
| `--indirect-count` | GPU-produced arguments/counts, indexed and nonindexed draws, zero/partial/clamped counts and padded strides | 10 |
| `--memory-accounting` | Shared Vulkan allocations counted once, GPU contents and allocation/free balance | 7 |
| `--pool-registry` | 5,120 reverse-inserted pools, cached identities, overlaps, overflow, removal, reuse and GPU writes | 8 |
| `--storage-bits` | Signed/unsigned 8/16/32-bit image reads/writes and separate sampled/storage swizzles | 36 |
| `--vertex-bits` | Signed/unsigned 8/16/32-bit vertex input interfaces and raw fetched bits | 8 |
| `--cpu-file` | Whole-byte identity, dirty writes, forced eviction/reload and post-finalization CPU storage | 15 |
| `--copy-pages` | 16 MiB sparse copies, 4,096 extra tracked ranges, every copied/untouched byte and untouched tile stamps | 6 |
| `--shared-spill` | Every 48 KiB shared word, isolated 3D workgroups, barriers, atomics and GPU-produced indirect counts | 6 |

`--atlas` now has 868 checks. Its compressed-copy cases update native physical storage, sample an aliased layer and retain earlier versions until the same GPU fence. The other GPU regressions remain separate modes. `--terrain` without captured Mac inputs has 103 checks; the optional captured-height inputs add further comparisons.

CPU-backed sparse depth and render targets currently use dense compatibility images. GPU writes persist; a subsequent CPU update or virtual remap after GPU writes stops explicitly until physical tile coherence is implemented. These tests do not establish full-game texture completeness or gameplay memory.

The integer-interface, workgroup and driver-state fixtures pass under actual
Khronos API validation on Adreno 840. The imageless-framebuffer fix also passes
draw, indirect, sparse, implicit and fragment-output regressions with zero API
errors. Earlier pixel-only passes that logged API errors are retained as failed
validation evidence.

`dm/android/tools/dmsv_workgroup.py SOURCE DEST --work EXTERNAL_DIR --limit 32768`
lowers compute uint arrays exceeding the selected shared-memory limit into
separate storage for each workgroup. It retains execution scopes, retargets
memory barriers and checks descriptor interfaces and every changed SPIR-V
module. The destination keeps all shader entries. Runtime reflection allocates
fence-owned storage sized from actual direct or GPU-produced indirect counts.
`test_android_limits.py` verifies used clip/cull outputs, member reindexing,
conservative unknown uses, workgroup byte counts and barrier semantics under
ASAN/UBSAN and independent validation. `probes/spv_limits.c` exposes the exact
runtime transform: two paths prune distance declarations; one path prints
logical workgroup bytes. The runtime rejects a known oversized compute module
before pipeline creation and names this rebuild tool.

`dm/android/tools/dmsv_atlas.py` can upgrade plain 2D samplers in an existing DMSV without translating guest code again. It preserves constant banks, stage metadata and native mesh trailers, and adds checked sampling metadata. It validates every changed SPIR-V module and leaves the destination untouched on any failure. `--reuse` accepts validated outputs with identical generated GLSL in that build folder. The regular `shader_vk.py --virtual-atlas` path also covers plain 2D samplers.


## Atlas mode specialization

`--explicit-lod` adds 384 GPU comparisons between dense and mapped BC6H, ASTC4x4 and ASTC8x8 sRGB sampling in both GOB orders, at anisotropy1/2/4/8. Both logical/dense binding positions are exercised, and output alpha must be 1. The implicit suite retains a negative anisotropy 2 case through `--atlas-reject-sampler`; it must stop nonzero. Directional filtering remains unsupported.

`probes/spv_atlas.c` runs the exact runtime header transform on the host. Build with ASAN/UBSAN. After the input/output SPIR-V paths, pass pairs of metadata descriptor binding and texture binding. `audit_android_specialization.py BUNDLE --tool TOOL --work EXTERNAL_DIR` independently transforms every atlas-bearing module and runs `spirv-val`. `test_android_atlas_spec.py` covers retained helpers, inlined compute code, direct exposure of the header constant and existing user specialization IDs. GPU implicit and offset regressions must accompany structural validation: valid SPIR-V alone did not catch Adreno's rejection of `OpCopyObject` directly from a specialization constant.


`--image-file` runs 30 checks of optional lossless GPU image retention. Independent whole-mip transfers hash GPU-only contents across mips, layers, large 3D row chunks, depth/stencil aspects, repeated eviction after new writes, and retirement while paged. Canonical guest bytes stay unchanged; actual Vulkan allocations must decrease despite the bounded transfer buffer. Further checks cover work spread across presents, five-second wall-time aging, actual pending GPU reads, and reconstruction of inactive CPU color/depth images before and after source writes. Run with a private `DM_TEMP` and active API validation.


`--watch-work` checks diagnostic progress before Vulkan initialization. Completed work keeps the one-second watchdog alive for over two seconds without changing frame counts. When work stops, the same watchdog must terminate the child at its original threshold. Two checks pass. The expected child watchdog message is part of this test.

Set `DM_VK_ATLAS_NATIVE_FILTER=1` when running the implicit, offset/gather, explicit-LOD, mapped and uncompressed suites to compare hardware filtering within atlas tiles against dense references. Repeat implicit sampling with the option disabled. API validation must remain active.


`--timestamps` compares NVN reports through their public nanosecond conversion with independent Vulkan timestamp queries over 512/1024/2048 MiB of real GPU fills. Nine checks cover the separate zero counter field, guest-clock epoch and elapsed time. The old Vulkan writer gives a 0.03125 elapsed-time ratio and fails six checks; the corrected writer gives 0.99991–0.99998 and passes with API validation active.

`--prewarm-recorded` prepares an existing private `DM_ROOT/vk_pipelines.bin` against the supplied full shader bundle. Set `DM_PROBE_CACHE=1` so the fixture permits cache reuse. The mode selects single-threaded synchronous preparation, checks that every unique record was processed, and reports elapsed time, RSS and PSS. Run with API validation and a memory guard, then inspect every pipeline result as well as the summary: processing a record alone does not prove that its shader exists or that Vulkan accepted its interface. Use a private copy of the game cache and recipes. This mode records no gameplay FPS.

`--command-copies` uses the real NVN command API and GPU readbacks to distinguish immediate copying from deferred calls. It rerecords and overwrites source storage, reuses both parent and child source storage after copying, and forces destination segment overflow. Four checks pass on the corrected host; the old copy implementation fails the first color check with zero API errors.
