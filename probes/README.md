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
its bindings remain unchanged. New captures also save `capture_PREFIX.spv`, the
actual selected module, including coherent-log variants; prefer that file when
available. Keep game-derived inputs and outputs in the
game's external work folder. Build the runner with NDK clang and
`-O2 -Wall -Wextra -Werror -lvulkan`, then run:

```sh
vk_compute_replay capture_prefix shader.spv output_prefix pipeline_cache.bin
# Optional final arguments select the first gx, gy, gz workgroups:
vk_compute_replay capture_prefix shader.spv output_prefix pipeline_cache.bin 1 1 1
```

The runner saves storage bindings and a pipeline cache and exits nonzero on
failure. The first replay has a ten-second fence timeout. To measure dispatches
with GPU timestamps, set `DM_REPLAY_REPEAT=24 DM_REPLAY_WARMUP=4`. Each iteration
restores every captured input, including writable resources; uploads, pipeline
creation and readback are outside the timestamps. Repeated submissions have a
thirty-second fence timeout and must reproduce the first replay's storage bytes.
The JSON result includes individual samples, an upper median, p95 and the number
of storage resources changed from their inputs. Use cached pipelines and alternate
variant order when comparing implementations.
Set `DM_REPLAY_TIME_BARRIER=1` to include the post-dispatch completion barrier,
matching the host's compute timestamps. This changes only the timing boundary;
the barrier executes in either mode.
`DM_REPLAY_POOL_AHB=1` allocates raw pools with the host's BLOB hardware-buffer
usage, dma-buf mapping and dedicated Vulkan import. Scratch descriptors retain
ordinary Vulkan memory. Link the runner with `-lvulkan -landroid` using NDK API
31 or newer. `DM_REPLAY_ROBUST=0` matches the host's core buffer-robustness setting.
`DM_REPLAY_DYNAMIC_UBO=1` makes all uniform descriptors dynamic; mode `2` keeps
binding zero static, matching the support/driver layout of the NVN2 captures.
These controls isolate allocation and pipeline configuration; address guards and
complete-pool comparisons remain active in every mode.

Set `DM_REPLAY_REQUIRE_CHANGE=1` to reject an unchanged result with exit 4.
Unchanged outputs can make an equality comparison inconclusive. Compare raw
outputs and inspect the result separately; successful execution alone does not
establish correctness. Version 1 does not relocate pointers embedded in captured
buffers or capture memory reached only through raw global pointers. Captures with
reserved descriptors include `global_memory` records; version 1 rejects these.

Set `DM_VK_CAPTURE_POOLS=1` for version 2. It captures complete backing pools for
bound compute storage slots and descriptors, including raw outputs absent from
shader reflection. `pool` records give guest ranges; `alias` records preserve
descriptor subranges in the same allocation. Limits are sixteen pools, 64 MiB
each and 256 MiB total. `DM_VK_CAPTURE_POOL_ADDRS=hex,...` explicitly includes
additional indirect targets. `DM_VK_CAPTURE_FRAME=N` captures every dispatch of
one frame, adding a sequence suffix so repeated kernels remain distinct.

Before replaying a raw-address shader, run:

```sh
python3 probes/raw_memory_guard.py shader.spv guarded.spv
vk_compute_replay capture_prefix guarded.spv output_prefix
```

The runner allocates each pool once, checks descriptor aliases against captured
bytes and rebases the original global table to actual new Vulkan addresses.
Uncaptured ranges receive no address delta. Binding 30 guards every supported
32-bit physical load/store before dereference; an uncaptured access increments
a fault counter and fails with exit 6. Physical atomics/copies and occupied guard
bindings are rejected during instrumentation. Keep original guest pointers in
captured buffers. The runner compares whole-pool outputs and nonaliased storage
images, failing with exit 5 on differences. `DM_REPLAY_ALLOW_DIFFERENCE=1` permits
intentional numerical experiments; it never disables address checks. Repetitions
reset complete pools and check stable outputs, excluding write-log hash order.
Guard instrumentation changes execution cost; use ordinary game shaders for
frame-rate conclusions.

`cache_raw_lookup.py INPUT OUTPUT` applies the generic last-pool lookup cache.
It changes no arithmetic, checks both guest range bounds on every hit and retains
the original full search on misses. The build enables it for recognized mixed
raw-read/write helpers; the diagnostic can also exercise a read-only fixture.
`make_lookup_cache_proof.py OUT` creates an independent two-pool integer reference
covering repeated hits, pool switching, an exact end boundary, null pointers and
whole-pool canaries. Run both generated `*.guard.spv` variants with reset
repetitions and ordinary/imported allocations. Cache hits are per invocation,
and entry zero starts empty. Guarded timing can predict the wrong direction of
a performance change, so verify the uninstrumented full game before selection.

`make_raw_replay_proof.py OUT` produces a synthetic aliased capture with an
independent integer reference. Its valid case passes with reset repetitions;
its deliberately missing pool range must fail with exit 6. It uses no game data.
`hmma_operand_trace.py` adds binding 31 to the original scalar SPIR-V and records
the first 1,024 matrix calls in the first logical warp of the first workgroup.
Each lane records A0..A3, B0..B1, C0..C1, D0..D1, sequence+1 and magic. Later
logical warps are excluded to prevent trace collisions. Original arithmetic and
existing buffer-block types remain unchanged. Trace runs are correctness probes.

`check_yuv_capture.py` independently checks R8/RG8 conversion on the CPU, including
the captured matrix, offsets and bilinear chroma sampling. `check_conv_capture.py`
checks deterministic samples of HWC half tensors against CPU convolution, with
K16 rounding, zero padding, stride-2 downsampling, bias and ReLU. It requires
NumPy and explicit dimensions; its docstring describes the driver-pointer ABI.
CPU references can differ in half packing/sampler precision, so inspect absolute
errors and tensor layouts instead of treating replay equality as ground truth.

`make_memory_snapshot_proof.py OUT --xlate TRANSLATOR` produces two fixtures for
`vk_warp32`: a shared read followed by overwrite and later use, with and without
a barrier. Each invocation owns its word. Both must export the original integer
17; the faulty translator exports 99. The fixtures exercise optimized AST code.

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

`hmma_shuffle.py` is an experimental, independently written replacement for the
translator's original matrix helper. It retains the logical 32-lane fragment
layout, uses subgroup shuffles and keeps the loop and helper calls intact:

```sh
python3 probes/hmma_shuffle.py original-translator.spv candidate.spv
```

Use the original translator SPIR-V, before `hmma_spv.py` lowering. The script
checks that helper contract, compiles with the pinned SPIRV-Cross plus glslang
and spirv-opt, and validates the result. It does not modify the production chain.
`--unroll` is a separate loop experiment. `--rounding 8` adds intermediate half
rounding after eight terms; this is a different numerical model and must be
tested separately from the default final-only rounding. Neither model's match
to original hardware follows from matching our scalar helper.

`--instrument` records both results of each matrix call at storage binding 31;
provide a separate sufficiently sized trace buffer in the capture manifest.
This diagnostic indexes by X only and is intended for the captured 1D kernels,
with every call executed once per invocation. `--original --instrument` traces
the scalar reference. Compare nonzero synthetic matrices as well as captured
traces, and measure uninstrumented shaders. The OOT experiment rejected the
shuffle candidate as slower and found an [open Android global-memory binding
defect](../nxnative/docs/reference/shaders.md#android-reserved-global-memory-descriptors-bind-zero-buffers).

The production replay also has `--global-memory` (build using
`make_nvn2_replay.py` below). Its synthetic shader loads guest pointers from
memory and atomically writes an unbound destination through the reserved pool
table. Twelve checks cover repeated nonzero writes, canaries, log overflow, null
addresses and unregistering/reusing a guest address. Run the same mode with
`DM_VK_NO_ZEROCOPY=1`, then additionally `DM_VK_LAZY_POOLS=1`, to exercise copied
and lazy destination visibility before NVN completion. `DM_VK_ZEROCOPY_MAX_MB=1`
also exercises a zero-copy descriptor pool with a copied indirect destination.
The shader returns the destination's actual pool flags: only materialized
zero-copy ranges may suppress write logging. Copied destinations retain tracked
page publication, and all four modes preserve their canaries and CPU-visible
results. These are real backend
tests, not standalone substitute bindings. The current implementation waits
after indirect stores; the proof does not imply correct game matrix arithmetic.

`isolate_raw_store.py` provides two output-preserving diagnostics for the
pre-optimization raw-store helper contract: `--log-binding N` removes only its
eight CAS probes, and `--map-entry N` specializes its final lookup to the real
entry found in a capture's table. Unsupported helper shapes reject explicitly.
Apply `raw_memory_guard.py` afterward and use whole-pool comparison. For a
capture with one backing pool, `--ranges 1` keeps the guard to that one range;
uncaptured accesses still fail before dereference. Keep the same guard in every
compared variant. Repetitions must reset all inputs, retain nonzero tensor
outputs, and use warm pipeline caches plus GPU warmups. Removing both lookup
and logging leaves matrix computation, gathers, tensor traffic and the guard;
its timing is not a pure matrix-arithmetic measurement. These diagnostic
specializations are never promoted as production shortcuts.

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

The current replay has 35 synthetic shader programs. Build with `make_nvn2_replay.py` and use these additional modes:

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

## Native cooperative convolution experiment

`make_cooperative_conv.py CAPTURE OUT --shape H W CI --channels CO` extracts
finite HWC half tensors from the captured driver-pointer ABI used by
`check_conv_capture.py`. It builds a diagnostic 3x3, stride-1 convolution using
native subgroup-scoped F16 `64x16x16` tiles. Input packing, halo loads, K16
accumulation, bias/ReLU and output packing execute inside the measured dispatch.
The direct-buffer output has 64-byte canaries at both ends. Run with:

```sh
DM_REPLAY_COOPERATIVE=1 DM_REPLAY_REQUIRE_CHANGE=1 \
  DM_REPLAY_WARMUP=16 DM_REPLAY_REPEAT=24 \
  vk_compute_replay OUT/layer OUT/native.spv OUT/native
python3 probes/check_cooperative_conv.py OUT LOCAL_REPLAY_PREFIX
```

The runner requires the native tile, F16 arithmetic, Vulkan memory model and
64-lane subgroup support. `make_cooperative_conv_proof.py OUT` builds independent
integer and fractional fixtures with padding, negative values, bias/ReLU and
partial final tiles. Integer results must match exactly; fractional differences
are reported against the CPU K16 reference. Successful execution or a small
average error alone does not establish guest numerical equivalence.

`native.raw.spv` uses the original driver's bindings and guest pointers, retains
pool bounds and copied-pool write logs, and distributes tiles across the original
dispatch grid. Guard it with `raw_memory_guard.py` before replaying real capture
pools. Check the entire pool outside the output tensor, not just its end canaries.
Cooperative modules use the Vulkan memory model; the guard declares the capability
needed by its cross-workgroup Device-scope fault counter.

`make_cooperative_bundle.py SOURCE NATIVE_RAW_SPV DEST --key HEX` replaces one
explicitly selected compute module in a separate diagnostic bundle. It retains
all other shaders, reflection records and flags, changing the selected local size
to `64x1x1`. It refuses to overwrite the source bundle. The raw kernel's captured
ABI and dimensions must be established before using this experiment in a game.
The Android host enables cooperative-matrix features when the device exposes them;
the production shader translator does not select this experimental kernel.

Full-game measurements remain necessary: direct-buffer layout, raw pointers,
launch grid and guard instrumentation can change the measured performance.
See the [OOT experiment](../nxnative/dm/games/0400486024DEC000/README.md#follow-up-2026-11-16-native-cooperative-convolution-experiment).

`cooperative_arithmetic.py OUT` builds three independent matrix probes: native
K16, scalar float32 FMA with explicit half conversion, and scalar FMA with direct
half packing. Replay them against `OUT/fixture`, then pass `--native PREFIX
--scalar PREFIX` to compare GPU results with CPU accumulation models. If
`scalar-pack.b3.after.bin` is beside the scalar output, the analysis also checks
round-to-nearest-even and round-toward-zero packing. `check_conv_capture.py`
accepts `--arithmetic half-mul-add --packing rtz` to test the observed native
model through a complete sampled convolution. These are explicit diagnostic
models; default CPU-reference behavior is preserved.

Two version-1 manifest records isolate address handling without inserting
per-access guards. `address_table 4` requires five SSBOs at bindings 0–4 and a
64-byte table at binding 4. The replay fills that table with the addresses and
sizes of its four owned allocations. `owned_pool MAP BACKING GUEST FLAGS` fills
a 4096-entry map with one owned backing allocation and its guest-to-device
relocation. The corresponding kernels check whole-tensor bounds before access;
the experiment checks full outputs, untouched input regions and canaries.
Neither mode changes version-2 captures' mandatory raw-access guards.

The convolution shader's `QUALIFIED_READS`, `EARLY_RETURN_STORE` and explicit
function-control experiments test compiler effects while retaining logging.
`OMIT_WRITE_LOG`, `MINIMAL_ATOMIC_LOG`, `NON_ATOMIC_LOG` and `FIXED_MAP_ENTRY`
are controlled diagnostics, not production policies. Omit or simplify logging
only for a destination independently proved coherent; copied pools require page
publication. The [follow-up findings](../nxnative/dm/games/0400486024DEC000/README.md#follow-up-2026-11-16-native-arithmetic-and-inactive-write-logs)
record the numerical model and the ordinary-game cost of inactive logging code.

The runtime's coherent-log transform is restricted to cooperative-matrix compute
modules. It selects a separate module and pipeline only when every range in the
current immutable map is coherent; copied ranges retain tracking. `spv_gmem.c`
exposes the exact transform for sanitizer and independent-validation checks.
`--global-memory` and `--global-memory-cooperative` each run twenty backend checks,
including copied/coherent replacement of the same guest address and CPU visibility
before NVN completion. Run both under active Vulkan validation. The cooperative
fixture requires the reported native F16 tile and uses shared-memory matrix loads.
Scalar A/B constructors fail compilation on the tested driver.

`FLOAT32_K16` selects a diagnostic tiled float32-FMA implementation in the
convolution probe. Its half accumulator conversion and final packing are checked
independently; matching this CPU model does not establish byte equality with the
game's existing shader. Neither this mode nor the native kernel is selected by
the production translator.

`TEXTURE_INPUT` with `RAW_LAYOUT` and `CI=16` reads four row-major RGBA pixels
as sixteen channels before the convolution. It requires a `2*WIDTH` by
`2*HEIGHT` texture at binding 2; weights, bias and destination keep the raw ABI.
`check_first_conv_capture.py CAPTURE [--output FULL_POOL]` independently checks
the RGBA8 UNORM unshuffle, zero padding and measured native arithmetic at sampled
corners, center and seeded random pixels. Its `fma-k16` option is a separate
numerical model. Check the full pool outside the destination after owned replay.

`hmma_cooperative.py SCALAR_HELPER_SPV DEST` is a separate diagnostic packing
experiment. It retains the caller's sampling, weights, image writes and local
size, placing two logical `16x8` results in a native `64x16` tile. It requires
one or two complete physical wave64 subgroups and rejects nested calls or early
exits from main. Native half arithmetic differs from the production helper.
Integer GPU fixtures check fragment order, dependent/aliased calls, both result
words and isolated subgroups; executable contract tests check the descriptor
interface. This generic packing is **rejected for OOT reconstruction performance**:
88.51 ms versus 28.77 ms on identical captured inputs. Do not use the convolution
bundle tool for this module: that tool sets local size to 64, whereas this
experiment preserves the original local size.

`hmma_cooperative_pair.py SCALAR_HELPER_SPV DEST --sharing aabb...` fuses
consecutive matrix calls with identical A fragments in a `128x1x1` group.
Each letter selects an independently established shared operand across logical
warps. `a` transposes the product to combine varying B tiles; `b` combines A rows
against two shared B tiles. The tool rejects dependencies, intervening side
effects, nested calls and early exits. `--verify` reserves a 512-byte SSBO at
binding 31: words 0–63 must stay zero, and words 64–127 count completed groups per
pair. Always run this check over the whole capture before the timing build.
`--scope subgroup` uses separate padded tiles for the two physical subgroups;
the default uses one full tile and workgroup synchronization. Both are diagnostic
native-half models. On the measured reconstruction capture they take about 99.07
and 52.27 ms respectively, so neither is used in the game bundle.

The convolution builder accepts `--tile-n 32` to reuse one packed input tile for
32 output channels. The shader's `TILE_N` defaults to 16; output channels must be
divisible by the chosen tile width. Grid partitioning, weight packing, accumulator
dimensions and output indexing change together. Compare full output pools between
tile widths and check padding/canaries and the independent native-half reference.
This option preserves the preceding diagnostic native arithmetic; it does not
establish guest numerical equivalence.

`--paired-loads` selects `PAIRED_LOADS` in both direct and raw convolution
modules. Each lane unpacks both halves of a source or weight word when filling
shared matrices. The texture-input variant fetches one RGBA texel for each pair
of adjacent channels, preserving the existing row-major unshuffle and half
conversion. Whole K16 inputs and supported N tiles keep pair indices even.
The option also compiles with address-table and float32 arithmetic experiments;
it changes packing work while keeping accumulation, bias/ReLU, launch partitioning
and copied-pool logging. Compare complete outputs at each tile width against a
dense oracle and the preceding module, including input regions, padding and
canaries. Benchmark coherent raw modules with the exact runtime log transform,
then measure the selected tracked modules in the full game.

`--quad-loads` selects `QUAD_LOADS` instead of paired packing. Each source or
weight load supplies four adjacent half channels. Buffer variants read two
32-bit words; texture input fetches one whole RGBA texel. Whole K16 inputs and
N16 output tiles prevent row crossings. Existing bounds, accumulation order,
output packing and copied-pool logs remain. The builder rejects simultaneous
paired and quad options. Validate complete outputs across strides and tile
widths, then measure each interface: fewer texture fetches need not make the
buffer variant faster.

`make_cooperative_conv.py ... --stride 2` selects a non-overlapping 2x2 kernel
with no padding and half-sized spatial output. The default remains a zero-padded
3x3 stride-1 kernel. Tensor extraction, driver extent checks, weight bounds,
output allocation, tile count and output indexing all follow the selected stride.
Odd input dimensions are rejected for stride 2. `--shape` always describes the
input tensor; `check_cooperative_conv.py` reads the recorded stride when checking
the output. The raw module still distributes tiles across the supplied launch
grid. Texture-input convolution currently requires stride 1.

`make_cooperative_conv_proof.py OUT --stride 2 --channels 64` builds integer and
fractional fixtures with a partial final output tile. Check every output channel,
all input regions and both canaries against a dense native-half oracle before
timing real pools; native half arithmetic remains distinct from float32 FMA.

`make_cooperative_conv_proof.py OUT --channels 64` generates integer and fractional
fixtures covering all 64 output channels. The default remains 32. Rebuild each
fixture with `make_cooperative_conv.py OUT/integer/fixture DEST --shape 9 13 32
--channels 64 --tile-n N` for each supported N before real-capture replay.
Compare complete output buffers, both canaries, immutable inputs and the
independent native arithmetic model. Choose the tile width from measurements;
the largest supported shape need not be the fastest.

## Native cooperative residual upsampling

`make_cooperative_upsample.py CAPTURE OUT --shape H W CI --channels CO --tile-n N`
builds a separate diagnostic for four row-major output subpixels per input
pixel. Weights are phase/CI/CO. The residual initializes the accumulator before
K16 multiplication; bias/ReLU and final packing follow. Native half arithmetic
is a separate model from the production float32-FMA helper.

The raw ABI uses driver words 196/200/204/208/212 for destination, source,
weights, bias and residual, with map binding 4 and log binding 6. The builder
requires finite bounded tensors in one complete captured pool. `owned.tsv`
relocates that pool without losing its aliases; its backing allocation is
coherent. Keep `native.raw.spv` tracked in diagnostic bundles. For owned timing,
the exact coherent-log transform exposed by `spv_gmem.c` can produce a separate
module; copied pools still require the tracked module.

`make_cooperative_upsample_proof.py OUT` builds integer and fractional fixtures
for N16/N32/N64, including residuals, negative values, bias/ReLU and partial
pixel tiles. Compare every pool byte against each fixture's dense oracle.
`check_upsample_capture.py CAPTURE --shape H W CI --channels CO --output FULL_POOL`
checks corners, center and seeded sampled pixels independently. Its `fma-k16`
alternative is explicit; neither model establishes original Ampere equivalence.

`make_cooperative_upsample_proof.py OUT --inputs CI --channels CO` expands the
same residual-order and phase proofs to other whole K16/N16 channel counts.
Defaults remain CI32/CO16. Check complete pools across tile widths, including
the residual tensor and partial pixel tiles, before selecting a real-capture
variant from timings.

`--load-width 2` unpacks each source, weight and residual word once while
filling the shared matrices. Width `4` reads two adjacent words for four half
channels; the default `1` preserves scalar loading. Whole K16/N16 channels
keep each group within one source row, weight row and residual subpixel, even
when a tile spans phases. Residual initialization, native accumulation order,
bias/output packing, bounds checks and copied-pool logging are unchanged.
Compare complete pools against dense oracles for both channel sizes and partial
tiles, then retune N16/N32/N64 on real captures: packing can change the best tile.

## Native cooperative output-image convolution

`make_cooperative_output.py CAPTURE OUT --shape H W CI --paired-loads` builds a
separate bounded 3x3 convolution with sixteen output channels, shuffled into four
RGBA subpixels. It requires zero padding, RG/BA channel planes, an identity
RGBA8 UNORM source image at binding 2 and an RGB10A2 destination at binding 3,
both twice the feature dimensions. The final order is source image plus residual,
then bias, followed by UNORM conversion. There is no intermediate ReLU.

Read-only SSBOs 4/5/6 retain captured weights/features/bias. Their word-aligned
offsets come from the low byte of driver words 204/200/208; declared extents and
actual buffer lengths must contain the complete tensors. A captured translator
support block must specify unit texture scale. The builder preserves the launch
grid in a version-1 replay with separate descriptor snapshots; it requires no
guest pointers or write logs. `--paired-loads` unpacks both half values from each
32-bit source word while filling the shared matrices.

`--arithmetic float32` selects explicit FMA with direct half packing at K16
boundaries; the default uses native F16 cooperative tiles. Both remain diagnostic
numerical models. `--trace` adds a binding-7 half tensor before bias and image
combination, protected by 64-byte canaries. Disable tracing for timings and game
bundles. `make_cooperative_output_proof.py OUT` generates integer and fractional
fixtures with descriptor prefixes, all phases/channels and partial pixel tiles.
Compare complete trace and packed-image bytes with the dense oracle, and verify
all input buffers remain unchanged.

`check_output_capture.py CAPTURE --shape H W CI --output IMAGE --trace TRACE`
checks sampled corners, center and seeded pixels against an independent model.
It reports packed RGB10A2 component differences in quantization units and checks
trace canaries. `--arithmetic fma-k16-rne` and `fma-k16-rtz` make the rounding model
explicit. Compare whole output images and captured pools as well: sampled model
agreement alone cannot establish full-image equality or original guest arithmetic.
See the [OOT output-image findings](../nxnative/dm/games/0400486024DEC000/README.md#follow-up-2026-11-17-output-image-convolution-reaches-1137-fps).

## Reconstruction arithmetic and scheduling probes

`hmma_packed.py INPUT_SPV OUTPUT_SPV --mode packed|stream` requires the original
translator's scalar matrix-helper contract and aligned per-warp scratch ABI.
The default `--arithmetic fma32` preserves per-output FMA order, both packed
results and direct final half packing. Packed mode loads contiguous half words
before arithmetic; stream mode reads them within the loop. `--unroll` changes
the loop control hint. The tool preserves descriptors and local workgroup size,
uses a separate scratch array and refuses to overwrite its source module.

`--arithmetic fma16` and `muladd16` are separate half-accumulator experiments.
The latter explicitly separates the product from the addition. Source spelling
alone does not establish the device's numerical behavior: compare fused and
separately rounded CPU models with cancellation, fractional, tiny-increment and
subnormal fixtures. Check complete results and canaries, then compare full
captured images and immutable source pools. These modes do not establish guest
arithmetic equivalence.

`hmma_vector.py INPUT_SPV OUTPUT_SPV --width 2|4` works on scalar FMA chains
already in the module. It preserves their operands, gathers, cache and K16
per-component order while forming vector FMAs before the same final half packs.
Only sixteen-term, single-consumer chains feeding a two-component half pack
qualify. Width four also requires neighboring packs in one block, with no
intervening writes, barriers, branches or non-alias use of the first pack.
Direct bitcast/copy aliases may move with that pack. Other consumers or precision
decorations reject the region; unsupported modules stay byte-identical.
Both widths are diagnostics requiring independent validation and GPU output
comparisons before a timing result can justify further use.
