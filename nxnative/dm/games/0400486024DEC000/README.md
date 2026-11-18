# The Legend of Zelda: Ocarina of Time (Switch 2) — `0400486024DEC000`

A Switch 2 title, dumped loose as `exefs/` (`main` 29.9 MB, `sdk` 7.8 MB, `subsdk0` 533 KB, `rtld`) and `romfs/` (25 GB) from update **1.1.1**
(`Product.100`/`Product.111` tables, `RegionLangMask.txt` `111`). Nintendo EPD's engine (Nin_Ounce: sead / agl / gsys, Phive), SDK **22.2.8** (the `sdk`
names its spec `Ounce`), NVN2 with Ampere shaders. **Android now runs all eleven captured compute programs without abort parking or dispatch skips.**
Isolated precompilation avoids the native allocator failure. Logical-warp handling, two optimizer liveness bugs, storage-image usage and
transposed LDSM addressing are corrected. Earlier builds rendered a recognizable moonlit field while neural stores were missing.
Decoded pictures, CPU readback and GPU planes match the source movie; the earlier black captures were its opening fade.
**The corrected network now renders clean movie frames with every neural pass active.**
Logging and lookup improvements bring the ordinary game to about 241.64 ms per frame (4.14 fps).
A separate native cooperative-matrix experiment measures a further gain, with numerical equivalence still open;
see [the latest experiment](#follow-up-2026-11-17-cooperative-only-log-specialization).
The full rebuilt bundle now renders readable New Game and Options text over the title movie. The missing text was a guarded
deferred-register-write bug in the translator. Down selects Options, A opens it and B returns to the title menu.
Visible Options labels now render after adding omitted UI shaders, and New Game reaches the narrated tapestry opening.
Real-time playback and player-controlled gameplay remain open.

Reference: `NX2navi-0.5.0` beside the dump is a static recompilation of this game (v1.1.1) to Windows x86-64 with a Vulkan renderer. It is read for
**what the game asks of the SDK** — its architecture notes enumerate the services it had to serve (`fs`, `hid`, the audio renderer, `nn::codec`
movies, applet/account, the three-core scheduler) and the NVN2 commands it replays. Its additions are all rights reserved and its code is not copied
here; only the facts about the title are used.

**Target order: Android first, Metal/Mac second.** Android has a profile and an observed-path Vulkan bundle. The tablet has 15.2 GB usable memory;
the guest's reported 12 GiB application pool and virtual reservations do not establish its resident-memory requirements.

## What it needs

| Setting | Where | Why |
|---|---|---|
| `sys_resource 0x3000000` | [`game.tsv`](game.tsv) | the NPDM declares 48 MB, so the SDK's `IsVirtualAddressMemoryEnabled` is true (Donkey Kong Bananza's declares none) |
| the memory keys | `game.tsv` | 12 GiB reported application pool, 32 GiB virtual reservation; the title requests and receives a 9.20 GB heap; resident requirements remain unmeasured |
| `render_cond on` | `game.tsv` | agl's conditional clears, as on Bananza and Splatoon Raiders; to be confirmed on this game |
| zstd dictionaries | `Pack/ZsDic.pack.zs` | every RomFS `.zs` names one of four dictionaries (IDs 1 `zs`, 2 `bkprb`, 3 `bcett.byml`, 4 `pack`); `shader_split.zs_dicts` reads them and the census now loads them too |

The four dictionary IDs are not in pack order — `pack.zsdic` is third in the SARC and fourth by ID. Each dictionary records its own ID at +4 of its
0xEC30A437 header, which is what a frame's header names, so the table is read from the dictionaries rather than assumed.

## Boot (Mac)

The 2026-11-09 run reaches `nnMain` and the first NVN2 setup. Two steps stopped it on the way:

1. **`SetHeapSize OOM: req 0x18ce00000 > cap 0x130000000`** — the Splatoon Raiders split left 4.75 GB of heap for a title that asks 6.22 GB. Mario Kart
   World's reservation (25 GB reserve, 16 GB alias, 256 MB stack and a 256 MB gap) leaves 8.5 GB, and the host then reports
   `[mem] heap 6.70 GB (heap region 8.50 GB)` and carries on. This is the one measured memory number so far.
2. **`FATAL cannot read the shader map …/shader_map.tsv`** — until the split wrote the tables. Everything before it already ran: the RomFS mounted,
   `nvnDeviceGetInteger` answered API **231.40** (SDK 22, Switch 2), a 2560x1440 swap chain of 3 textures at interval 1 was created, the address
   regions were allocated, and CPU-written textures (serials 27–44) uploaded through the Metal layer.

3. **The 2,376 libraries it asks for are not the wall** (measured 2026-11-09, correcting the first reading). A targeted build of exactly the requested
   keys produced **2,324 of 2,376**; the 52 misses are all `Ampere 927 … task/mesh`. Booting on that cache gave **0 load failures** and the game aborted
   at the same `Result 0xa99` / `sdk+0x1f61ac`. The abort was never the missing libraries.
4. **`auddmg:u` is the wall.** Immediately before the abort the log says
   `[RED] sf: the game connects to service auddmg:u itself, which the host does not serve` — the Switch 2 audio device manager, a service the SDK does
   not proxy through its own registration. Its connect returned `ResultNotRegistered` and the title aborted. Serving the session and the HIPC close moves
   the failure one step later: `auddmg:u` command 0 (`OpenVirtualDeviceManager`) returns an **object/handle**, this host's generic session answers objects
   and handles with zeros, and the client dereferences null (`SIGSEGV at sdk+0x2ace08`, then inside the abort path at `sdk+0x2abf00`).

The reference port's `auddmg:u` shows what the manager answers afterwards: command 0 opens the manager, then `0` lists virtual output devices, `100`
returns the default output device's name, `300` checks a stream format, `401` returns a 0x228-byte properties block (a game this size sizes its mix from
it), `500` hands out a state-change event, and `700`/`800` attach and detach streams. So the next step on this title is a real service, not another
shader.

The modules rewrite as they are: `main` 48,889 plain sites, 861 conditional, 1,264 `tpidr` and 66 spin waits; `sdk` with 2 registered cuts, 5
observation gates and 57 SVC sites; `subsdk0` and `rtld`. The SDK's `AddressRegionManager node area 1 GB → 62 MB` patch matches; the
`AllocateAddressRegion` alignment patch still reports a version gap against SDK 22's code shape, as on Mario Kart World.

Run recipe:

```
make -C nxnative/dm/host GAME=0400486024DEC000 -j8 dmhost
DM_MSL_DIR=$W/shader/metal_cache DM_MEM_CAP_GB=48 DM_ROMFS="…/dump/romfs" DM_SAVE=$W/save DM_TEMP=$W/tmp ./dmhost $W/patched
```

with `$W` this title's work tree (`.gamedump/OcarinaOfTime/` here) and `patched/` written by `dm/tools/patch_nso.py` for all four modules. The dump's
`main` is ZBIC-compressed (NSO flag bit 7), so the tooling needs the optional `zbic` package.

The shader build needs `TMPDIR` set to the work tree: `dmsh_build.py` puts its intermediate MSL under the system temp, and at this title's 56,339
programs that is several GB in `/var/folders` (measured: about 5.8 GB of a run in progress, and 19 GB left behind by two runs that were stopped). With
`TMPDIR=$W/tmp/dmsh` it stays on the external volume, and the build's content-addressed cache makes a restart cheap.

## Shaders

Census (`nvn2_shader_census.py`, after the dictionary fix):

| | |
|---|---|
| files holding shaders | 13 of 8,184 candidates |
| stage programs | **122,083** (57,085 vs, 60,612 ps, 3,566 ds, 820 cs) in **33,939 unique** programs |
| instructions | 38,060,208 in the unique programs |
| translator (arch sm86) | **33,056 of 33,939 translate (97.4%)**, 883 fail |
| failures | 845 task/mesh (`Ampere 927`, ISBERD/ISBEWR — no task/mesh pipeline), 22 opcode `243`, 10 `f8c`, 6 `3a9` |

The task/mesh set is this host's known Switch 2 gap (the 26 refused programs of Mario Kart World, a few hundred in Bananza's terms, here 845), and it
is large because the game draws with mesh shaders rather than because the translator is weaker here. The other 38 are ordinary unimplemented Ampere
instructions (`243`, `f8c`, `3a9`), 26 of them in compute.

122,083 stage programs is roughly ten times Mario Kart World's 11,603 and five times Bananza's 22,852, so the first full translation and pipeline
build will be long even though the unique-program count is smaller than the stage count suggests. That cost is the reason the profile's tables are
split and built in the background rather than inline in a probe.

## Found on this game

- [Logical NVIDIA warps on wider Vulkan subgroups](../../../docs/reference/shaders.md#logical-nvidia-warps-on-wider-vulkan-subgroups): corrected Android job configuration and Ampere lane exchanges.
- [Native compiler exceeds the allocator mapping budget](../../../docs/reference/shaders.md#native-compiler-exceeds-the-allocator-mapping-budget): isolated cache preparation avoids the Scudo failure; cold compilation still needs substantial memory.
- [Dead matrix results detach live inputs or erase output calls](../../../docs/reference/shaders.md#dead-matrix-results-detach-live-inputs-or-erase-output-calls): two shared optimizer liveness fixes, with separate-result and call-order GPU regressions.
- [Storage views require image creation usage](../../../docs/reference/rendering.md#storage-views-require-image-creation-usage): ordinary conversion and reconstruction outputs lacked Vulkan storage permission.
- [Transposed LDSM scales byte addresses as a memory stride](../../../docs/reference/shaders.md#transposed-ldsm-scales-byte-addresses-as-a-memory-stride): fixed the nondeterministic movie-reconstruction bands; the captured movie input remains nearly black.
- [Decoder-to-GPU provenance](#follow-up-2026-11-15-decoder-to-gpu-provenance): the early black input is the source movie's fade; later pictures render, with decoded/readback bytes and GPU planes independently verified.
- [Vector HMMA gathers with bounded tile reuse](../../../docs/reference/shaders.md#vector-hmma-gathers-with-bounded-tile-reuse): integrated compute acceleration, preserving the scalar helper's results and reducing measured frame work by about 45%.
- [Guarded deferred writes overwrite newer register values](../../../docs/reference/shaders.md#guarded-deferred-writes-overwrite-newer-register-values): corrected collapsed glyph geometry and restored menu text.
- [Android reserved global-memory descriptors bind zero buffers](../../../docs/reference/shaders.md#android-reserved-global-memory-descriptors-bind-zero-buffers): binding and visibility corrected; the active neural path exposes another rendering defect.
- [Expression propagation delays mutable reads past overwrites](../../../docs/reference/shaders.md#expression-propagation-delays-mutable-reads-past-overwrites): the first incorrect nonzero weight fragment is traced to a shared-memory read moved past an overwrite; corrected full-network movie frames render cleanly on Adreno.
- [Raw write logs track pages the zero-copy backend does not consume](../../../docs/reference/shaders.md#raw-write-logs-track-pages-the-zero-copy-backend-does-not-consume): controlled tensor replays isolate logging and lookup costs; coherent zero-copy outputs now omit redundant page tracking.
- [Repeated raw pointer accesses search every pool again](../../../docs/reference/shaders.md#repeated-raw-pointer-accesses-search-every-pool-again): a validated invocation-private cache recovers the upsampling regression and improves the other mixed-memory pass; guarded timing can predict the wrong performance direction.
- [Native F16 cooperative matrices round products and additions separately](../../../docs/reference/shaders.md#native-f16-cooperative-matrices-round-products-and-additions-separately): an independent model explains the native convolution's fractional differences.
- [Inactive multi-probe atomic logging slows a cooperative kernel](../../../docs/reference/shaders.md#inactive-multi-probe-atomic-logging-slows-a-cooperative-kernel): controlled replays reproduce the gap and a coherent-only diagnostic recovers the full-game dispatch cost.
- Every RomFS `.zs` is a **dictionary** frame: the census's first run reported no BNSH under the whole dump because the reader had no
  `Pack/ZsDic.pack.zs` table. `shader_split` already supported such frames (Tears of the Kingdom); the census did not load the table.
- `shader_map.tsv` names one shader source this dump has and Mario Kart World's does not: `Shader/ApplicationPackage.Nin_Ounce_NVN2.release.sarc.zs`
  carries the agl `sharcb` packs for the game's own passes (`FoliageShader.sharcb` among them), plus `Lib/agl/agl_resource…sarc.zs` for the engine's
  common set.

## Android (2026-11-14)

The Android host is built from the same profile (`dm/android/build.py --game 0400486024DEC000`, NDK 28.2) and the four modules are rewritten with
`DM_TARGET=android` (main 48,889 plain sites, 51,720 slot references). The 25 GB RomFS was streamed to the tablet's `/data/local/tmp` and the host run
headless over adb.

- **It reaches the same graphics frontier as the Mac and past it.** `SetHeapSize` is accepted (heap 6.70 GB of an 8.50 GB region), the 2560x1440
  swap chain is created, the Vulkan backend reports Adreno 840, `auddmg:u`'s manager (commands 0, 300, 401) and `audsmx:u`'s user session are served,
  and the run reaches `WindowCrop 0,0 2048x1152` and the first NVN2 submission.
- **The title presents at 60 fps once the abort is parked** (numbers under the abort entry below). Earlier post-assert runs that kept presenting
  did so through the host crash gate's `none == me` miss, not by design.
- **The abort is `std::terminate` from a name lookup, not an NVN check** (measured 2026-11-14, correcting the first reading). The `nn::diag`
  abort carries no message at all — `VAbortImpl` gets empty `fn`/`expr`/`file`/`fmt` — and the guest frame chain names only the SDK's
  forwarding stubs (`sdk+0xba138 ← sdk+0x7bd670 ← sdk+0x777f30`), because each stub keeps the caller's `lr`. The SDK's
  `nvnTextureBuilderSetFlags` client at `sdk+0x6b0d20` never runs in this frame: gates on its boss block and on the SetFlags slot
  (`sdk+0x6b0f50`) never fire, and `sdk+0x1055100` / `sdk+0x1055148` are simply still zero because the client was never entered.
  Two gates do fire: `sdk+0xba124` (the message-less abort entry, with a stack scan of the guest's stack) and `main+0x21f09b4` (a register
  dump inside the lookup). Together they place it: `main+0x21f0c7c` calls the SDK's terminate wrapper, guarded by `cbz x8` on a creator
  looked up at `main+0x21f0c9x` eleven instructions earlier; the registry at `main+0x4d330a0..f8` holds exactly two filled entries, `"poll"`
  (`main+0x21f1280`) and `"none"` (`main+0x21f0fb0`), the rest are sentinels with a null creator, and the name the game asks for is **`"all"`**
  (a `std::string` on the alias heap, three characters, whose `strcmp` matches nothing). The call chain is `main+0x21e3c30 → main+0x21eaa50
  → the lookup → terminate`; the surrounding strings (`grpc_poll_strategy`, `grpc.so_reuseport`, `rpc.experimental.tcp_max_read_chunk_size`)
  put it in the game's gRPC init, i.e. a background thread, not the render thread.
- **`DM_ABORT_CONT=1` parks the aborting thread and the title runs** (a diagnostic, not the console's behaviour: the parked thread may hold
  a lock). With it the run reaches **1,500+ presents**: `frame time p50 16.66 / p95 17.5 ms`, frame work p50 16.6 ms, GPU p50 1.6–3.1 ms —
  vsync-bound at 60 fps on black output. This measures presentation pacing; gameplay performance is unmeasured.
- **The picture is black because the draws have no program, not because of the abort.** One 600-present window reported
  `draws 1229, skipped (no program 1092)`. The host captured each missing key into `captured_shaders/` (35 files, 384 KB); 24 of them were
  already in the package and **11 were not — all compute**. `shader_vk.py … --capture captured_shaders` with a key list that includes them
  builds **2,398 of 2,409 shaders (168.8 MB)**, and the `is not in the bundle` errors are gone.
- **The new wall is Adreno compute pipeline creation.** With those 11 compute shaders present, the first dispatch of each compiles for
  `1.15 s`, `0.45 s`, `0.42 s`, then `45.9 s`, `13.9 s` and `2.3 s` — a run spends a minute in the driver before it can go on, and a second
  run pays the same numbers again even though `vk_pipeline_cache.bin` was saved (174 KB). Whether the driver ignores its cache for these
  pipelines or the creation cost is not caching at all is open.
- **Skipping the dispatches is not what makes the picture black** (measured 2026-11-14, `DM_VK_CSKIP=1`). With every dispatch skipped the run
  is fast and complete: `frame time p50 16.67 / p95 17.49 ms`, GPU p50 2.09 ms, **`draws 1119, skipped (no program 0, no target 0, no pipeline
  0)`** — the capture-merged bundle closed the shader gap entirely — and `dispatches 6874 (skipped 6874)`. Every presented frame is
  **0.00 % lit**. A pass dump of present 400 shows the frame is three passes, `2048x1152` twice and the `2560x1440` present target, and **all
  three read 0.00 % lit**, so nothing is lost in a composite: the passes are empty of content themselves.
- **The heap is sized from the reported total, and 9.20 GB still is not enough** (measured 2026-11-14). With `app_pool` at the console's 12 GiB
  (`0x300000000`, `mem_reserve` 34 GB) the game asks for a bigger heap and the host grants `[mem] heap 9.20 GB (heap region 15.50 GB)` — up
  from 6.70 GB at a 9.5 GiB total. The request tracks the reported number, so the constant matters: at 48 GiB (`0xc00000000`, a slip made once)
  the game asked for `0xb4ce00000` and died when the host refused.
- **The `std::bad_alloc` belongs to the three expensive compute programs, not to the heap.** Skipping exactly those three
  (`DM_VK_CSKIP=e6be82d835fbe4d3,9442573ee4ace011,0a56002cdc7e1fce`) and letting the other eight run, a 9.20 GB run gets to about 17 s and
  then aborts with no message at all. Letting **all** compute run, the same 9.20 GB heap reaches the three 45.9 / 13.4 / 2.3 s compiles and
  then `libc++abi: terminating due to uncaught exception of type St9bad_alloc` at about 40 s. So the failing allocation follows those three
  shaders — they are the ones this port added from run-time captures — and more heap does not move it.
- **`main` has no `__throw_bad_alloc` of its own** (measured 2026-11-14). Its dynamic table *imports* `__cxa_throw` and *defines*
  `_Znwm` (`main+0xf271c0`, 132 bytes) and `malloc` (`main+0x14c6c90`), so an allocation failure in `main` tails into the **sdk's**
  `__cxa_throw` — that is where the throw is, not in a local `__throw_bad_alloc`. `_ZTISt9bad_alloc` and `_ZTSSt9bad_alloc` are `main`'s
  (`0x4958438`, `0x3ed3339`) and the `sdk` binds to them, but no `adrp`/relocation in `main` refers to the typeinfo, which is what
  pointed away from a local thrower in the first place.
- **The gate on `sdk+0x7d8f44` was on the wrong address.** The dynsym's `_ZSt17__throw_bad_allocv` value `0x7d8f20` is a thunk cluster;
  the body is `sdk+0x7d91a0`, which is why the gate never fired. The live gate is now on `sdk+0x84f668` — `__cxa_throw`'s `mov x20,x1`,
  where `x1` is the `type_info` and its `+8` names the type — filtered to `*St9bad_alloc` so every other exception stays silent, and it
  prints the x29 chain of the code that threw.
- **The `bad_alloc` is intermittent, and now survivable.** It does not reproduce every run: one 120 s run with all three expensive
  pipelines compiled (`45.7 / 13.9 / 2.3 s`) threw nothing at all, while the next reached `libc++abi: terminating due to uncaught
  exception of type St9bad_alloc` again. `DM_ABORT_CONT` now also parks at a fatal **signal** (crash.c, after the dump, with
  `crash_gate`'s 15 s alarm cancelled), and the bad_alloc run then carries on: `DM_ABORT_CONT: sig 6 parks this thread, the rest of the
  process continues`, and its audio thread reports 24,000 callbacks, 19,708 of them not silent, after the park.
- **That abort never passes a hook the host can gate.** It arrives as the host's own bionic `abort` (`pc=abort+0xa0`, `lr=abort+0x7c`)
  on a guest thread whose stack is inside the guest heap, and neither the gate on `sdk+0x84f668` (`__cxa_throw`) nor the one on
  `sdk+0x7780a4` (inside the entry the loader binds for `abort`, `0x7780a0` — the `0x778080` prologue before it belongs to a different
  function) fires for it. So the signal park is the catch, not a guest-side hook.
- **The failing size is still unnamed, and it is not `main`'s `operator new`.** `main+0xf2722c` is where `_Znwm` (`main+0xf271c0`) gives
  up with no new handler installed — `x19` still holds the requested size there, and the next instructions tail-call the SDK's exception
  allocation with `w0 = 16` — so a gate sits there (id 29, `main.obs.tsv`). A run that *does* reproduce the `bad_alloc` fired it for
  nothing, which rules `main`'s `operator new` out. The `sdk` defines `_Znwm` as well — `sdk+0x84f260` is the **aligned** variant (`x0` size,
  `x1` alignment) and it gives up at `0x84f2d4` with `x19` the alignment and `x20` the size after rounding; the dynsym's value `0x84f2e0`
  is inside that function's cold block, not a separate function.
- **Neither memory refusal happens, now that both are reported.** `AllocateAddressRegion` is decided inside the guest (VammManager), so
  the host only ever saw the regions that succeeded; the ask gate now compares each request against `alias_room()` and names one that
  cannot be placed. `MapPhysicalMemory`'s refusal only existed behind `mem_map_limit`, which this profile does not set — the host was
  granting maps past the application pool in silence — so the condition is now reported either way, as a refusal when the limit is
  enforced and as a grant hardware would have refused when it is not. A 70 s run with every compute program enabled hit **neither**: 7
  address regions recorded (largest 0.30 GB of a 16 GB alias region) and 0.75 GB mapped of a 12.00 GB pool.
- **Five allocator gates are installed and all silent.** One callback (id 29) serves them by parameter: `main+0xf2722c` (`29`),
  `sdk+0x84f2d4` (`1<<8`), `sdk+0x84f270` (`2<<8`), `main+0x14c6cc8` (`3<<8`, `malloc`'s ENOMEM path), `main+0x14c6ca8` (`4<<8`,
  `malloc` entry) and `main+0xf204a4` (`5<<8`, `operator new[]` entry) — the entry gates log only from 64 MiB up. `main.obs.tsv` and
  `sdk.obs.tsv` list them. Two completed runs fired none of them: an 85 s one that reached all three expensive compiles
  (`60.3 / 13.6 / 2.3 s`) and had no `bad_alloc` at all, and a 95 s one that did abort — but with no `bad_alloc` message, so nothing in
  it is attributable to an allocation. `malloc`'s own failure path is the strongest of the five: if the heap were simply exhausted, that
  gate would fire, and it has not.
- **AV1 is now built for Android and decodes.** `android/movie_av1.c` was a stub; it is now the Mac's dav1d path, and `build.py` compiles
  `dm/third_party/dav1d` plus its arm64 assembly with the NDK (a small `android/dav1d/config.h` clears the Apple build's symbol prefix). A run
  reports `AV1: dav1d 1.5.4 decoding` and `decoder 1: first picture 1920x1080 into buffer 0`.
- **The shader bundle** covered the 2,376 keys the boot asked for; the title asks for 23 more (`vs_layout`/`ps_layout`), all in `shader_map.tsv`,
  and a title bundle with them loads (2,386 of 2,397). The full 56,339-key build reached the end of translation but the process died while wrapping
  the 847 task/mesh programs with every SPIR-V resident (the temp directory held 169,093 files / 5.8 GB); 13 of the first 94 mesh programs also
  failed `glslangValidator` with exit 2. The practical path is the boot+title bundle plus the keys the game captures at run time; a full build needs
  a streaming writer and those failures keyed. Three boot shaders (`TerrainGround`, `Model`) use the NVN2 `_cb0_40000000` texture pool array,
  which the Android chain does not implement yet: their reflection does not fit the bundle ABI and they are skipped.

Run recipe:

```
DM_GAME=0400486024DEC000 python nxnative/dm/android/build.py --game 0400486024DEC000 --ndk <NDK 28.2> --out <W>/host --exe --lib
DM_GAME=0400486024DEC000 python nxnative/dm/android/tools/shader_vk.py <W>/shader/pkg <W>/android/shaders_world.dmsv \
    --keys "$(cat <W>/android/keys_world.txt)" --capture <W>/android/captured_shaders
adb push <W>/host/dmhost <W>/android/shaders_world.dmsv /data/local/tmp/oot/
adb shell 'cd /data/local/tmp/oot && DM_ROOT=$PWD DM_ROMFS=$PWD/RomFS DM_SAVE=$PWD/save DM_TEMP=$PWD/temp DM_VK_SHADERS=$PWD/shaders.dmsv \
    DM_ABORT_CONT=1 DM_VK_METRICS=1 ./dmhost mods'
```

`keys_world.txt` is `keys_title.txt` union the captured keys: `--keys` filters, and it filters the captures out too, so a bundle built with the
title list alone silently leaves out the very programs a run just captured. `DM_ABORT_CONT` parks the gRPC `std::terminate` thread; without it
the run ends about three seconds in.

## Open

- **`auddmg:u`**: the session, the HIPC close, the manager object and the manager's answer buffer now work. Command 0 returns a move handle and the
  client sends on it; when the output descriptor resolves to the active caller's stack, the host admits it and `ListVirtualOutputDevices` writes the
  name and count (the Android run then sends commands 300 and 401). The general pointer-buffer translation is still not modelled
  (`QueryPointerBufferSize` answers 0), so a descriptor naming ordinary guest memory outside the caller's stack is not written.
- **The `"all"` lookup is resolved.** The poll factory failed its local EventFd probe; see [the current findings](#follow-up-2026-11-15-startup-fixes-and-the-native-compiler).
- **Compute execution geometry and cache preparation are corrected.** The initial minute-long per-run pipeline creation led to isolated
  prewarming with actual NVN2 local sizes and a working warm cache; see [the compiler/cache follow-up](#follow-up-2026-11-15-compiler-cache-and-logical-warps).
  Cold compilation still costs substantial time and memory.
- **The host's crash gate.** `crash_gate`'s `none == me` test never `_exit`s on the same thread, so a crashing process can keep presenting
  instead of failing cleanly. `DM_ABORT_CONT` is a deliberate park, not a substitute: the gate itself still needs fixing.
- **The opening movie picture is verified.** The bands were a transposed LDSM addressing error, and the early black pictures were the source's
  fade. Later captures show the moonlit field; see [the decoder-to-GPU follow-up](#follow-up-2026-11-15-decoder-to-gpu-provenance).
  Performance and gameplay remain open; see [the menu-coverage follow-up](#follow-up-2026-11-15-menu-shader-coverage-and-new-game) for current UI and opening verification.
- **Native allocation failure is attributed.** A fourth compute program, `d15370a382630d4e`, fails inside the Adreno compiler even with the original three skipped. See the current findings below.
- The full translation build (the rest of the 56,339 keys). The Android Vulkan chain translates the native task/mesh programs as EXT task/mesh, so
  the 845 refused by the Mac chain are not a wall there; the 3 `_cb0_40000000` pool-array shaders and the 8 Ampere-243 programs are skipped.
- The 38 unimplemented Ampere instructions (`243`, `f8c`, `3a9`).
- Memory: the 6.22 GB heap is the measured number; the game's `System/HeapSize` table is still unread, and the 12 GiB console layout the title plans
  from is not modelled.
- Android: the 25 GB RomFS reads from the tablet's data partition; the APK and its data pack are not assembled yet.

## Historical handoff (2026-11-15, before the follow-up fixes)

### What runs now

`dmhost` built from this profile, the four rewritten modules, `android/shaders_world.dmsv` (2,398 of 2,409 shaders,
168.8 MB) and `DM_ABORT_CONT=1`, on the Legion Y700 (TB323FU, Adreno 840).

| What | Measured | Commit |
|---|---|---|
| Title runs to 1,500+ presents, vsync-bound | `frame time p50 16.66–16.67 / p95 17.5 ms`, `GPU p50 1.6–3.1 ms` | `9353d726` |
| No draw lacks a program any more | `draws 1119, skipped (no program 0, no target 0, no pipeline 0)` per 600 presents | `9353d726` |
| Bundle covers what the game asks for | 35 keys captured on device, 11 of them absent (all compute); `shader_vk.py --capture` rebuild | `9353d726` |
| Heap sized as on hardware | reporting the console's 12 GiB makes the game ask more: `[mem] heap 9.20 GB (heap region 15.50 GB)`, was 6.70 GB | `517e1ade` |
| The ~3 s abort is named and survivable | gRPC creator lookup for `"all"` → `std::terminate`; `DM_ABORT_CONT` parks that thread | `eb4fa63e` |
| The `bad_alloc` is survivable too | `DM_ABORT_CONT` parks at the fatal **signal**; that run's audio thread then reports 24,000 callbacks | `21852d32` |
| Compute dispatch can be skipped, all or by key | `DM_VK_CSKIP=1` or a key list; replay summary reports the skipped count | `9353d726` |
| Both memory refusals are visible | `AllocateAddressRegion` vs `alias_room()`, and `MapPhysicalMemory` past the pool even where `mem_map_limit` is off | `7a4a4087` |

### The one open item: the picture is black, and nothing attributes it

Every presented frame measures 0.00 % lit, and so does each of a frame's three passes (`2048x1152` twice, then the
`2560x1440` present target) — so nothing is lost in a composite. Everything measurable behind it has been ruled out:

| Property | Verified by | Result |
|---|---|---|
| draws are not skipped | `replay up to present … skipped (no program N)` | 0 |
| no shader is missing from the bundle | host `is not in the bundle` lines | 0 |
| the three expensive compute programs compile | `compute pipeline end ms=` | 45.9–60.3 s, 13.4–14.5 s, 2.3 s |
| … and the cheap ones too | same | 1.1 / 0.44 / 0.42 s |
| the driver cache does not help | `vk_pipeline_cache.bin` 174 KB, same numbers on the next run | — |
| allocators never fail | gates at `main+0xf2722c`, `sdk+0x84f2d4`, `sdk+0x84f270`, `main+0x14c6cc8`, `main+0x14c6ca8`, `main+0xf204a4` | all silent |
| no C++ throw passes the sdk | gate at `sdk+0x84f668` (`__cxa_throw`) | silent |
| the guest is not refused memory | region refusal + pool-crossing reports | 0 of 0; 7 regions, largest 0.30 GB of 16 GB; 0.75 GB of a 12.00 GB pool |

These checks establish coverage and absence of the observed guest-memory refusals. They do not exclude incorrect translation, missing compute
results, incomplete initialization, or allocation failures inside the native driver.

### Pick up here — one run, no build

`DM_VK_CSKIP` with only the three expensive keys, so the cheap compute runs and the run reaches frames in ~10 s:

```
adb shell 'cd /data/local/tmp/oot && DM_ROOT=$PWD DM_ROMFS=$PWD/RomFS DM_SAVE=$PWD/save2 DM_TEMP=$PWD/temp \
  DM_VK_SHADERS=$PWD/shaders.dmsv DM_VK_NOPREWARM=1 DM_ABORT_CONT=1 \
  DM_VK_CSKIP=e6be82d835fbe4d3,9442573ee4ace011,0a56002cdc7e1fce \
  DM_VK_METRICS=1 DM_VK_PASSDUMP=400 DM_VK_SHOT=200,600 DM_VK_SHOT_DIR=$PWD/shots \
  timeout 90 ./dmhost mods > log.txt 2>&1'
```

Read `pass_00..02.ppm` luma and the `replay` line. Two branches:

- **Passes still 0.00 % lit** → the draws themselves produce nothing. Take `DM_VK_TRACE_PASS` on one frame to name the
  programs and their textures, then a `texraw` of what the present pass samples; a zero texture or an identity transform
  would be visible there.
- **Passes now have content** → compute is required for the picture, and the work is making the three pipelines compile
  *once* (a prebuilt/persistent driver cache, or a prewarm pass) rather than per run.

### Traps this hunt already paid for

- `nvnTextureBuilderSetFlags` was **not** the abort: its lazy client (`sdk+0x6b0d20`) is never entered (`eb4fa63e`, `13b50e8a`).
- A dynsym **value is not an entry point**: `_ZSt17__throw_bad_allocv` `0x7d8f20` is a thunk (body `0x7d91a0`), `_Znwm`
  `0x84f2e0` lies inside a cold block, `abort` `0x7780a0` is the bound entry of a 16-byte stub (`9b8c742d`, `10e9f99c`).
- `main` has **no** `__throw_bad_alloc`; it imports `__cxa_throw` and defines `_Znwm`/`malloc` (`9b8c742d`, `eb539566`).
- A guest abort can arrive as the **host's own bionic abort** on a heap-stacked guest thread, where no patched gate sees it
  — hence the park at the signal (`21852d32`).
- `shader_vk.py --keys` also filters the **`--capture`** keys out, so a capture-merged rebuild must pass the union.
- 48 GiB is `0xc00000000`, not 12 GiB (`0x300000000`); the wrong constant made the game ask for `0xb4ce00000` (`517e1ade`).
- `mem_map_limit` is off for this profile, so `MapPhysicalMemory` refusals were never enforced *or* logged (`7a4a4087`).

### Housekeeping left

- The `bad_alloc` itself is unnamed: it is intermittent (absent from an 85 s run, present in others) and its throw is not
  reached by any host-visible gate.
- `crash_gate`'s `none == me` bug is still there; `DM_ABORT_CONT` is a deliberate park, not a substitute.
- The three expensive pipelines are not cached between runs (174 KB cache, no effect).
- `nxnative/dm/games/0400C3F00006E000/README.md` has local edits that are not part of this work.

## Follow-up (2026-11-15): startup fixes and the native compiler

These runs use a separate device host (`dmhost-eventfd`) and module set (`diag-20261115/mods`), without `DM_ABORT_CONT`.
Artifacts are preserved under `/Volumes/Data/Switch/Zelda Ocarina of Time/0400486024DEC000-work/bringup-20261115/`.
This section supersedes the earlier handoff's proposed causes and next probes.

### Resolved: gRPC startup and fiber authentication

- `"all"` is the wildcard, as in [upstream gRPC](https://github.com/grpc/grpc/blob/v1.40.0/src/core/lib/iomgr/ev_posix.cc#L150-L163).
  The guest matching branch is correct. Its poll factory (`main+0x21f1280`) reads availability through `main+0x21f3a10`.
  The probe at `main+0x21f3bd0` calls `nn::socket::EventFd(0, 0)` and closes the descriptor. ENETDOWN from the host disabled the engine.
  Local counters, read/write, poll/select and close now work; network sockets remain offline. See
  [the service mechanism](../../../docs/reference/services.md#local-eventfd-wakeup-descriptors-work-offline).
- Passing that probe exposed `AUTIASP` failing at `sdk+0x16d40c` on a newly started fiber. Gates proved that signing and restore stack modifiers
  match. An independent tablet probe showed different APIA signatures on two pthreads, with identical APIB signatures.
  [Bionic resets APIAKey at pthread startup](https://android.googlesource.com/platform/bionic/+/master/libc/bionic/pthread_create.cpp).
  Android-only SDK cuts pair both initial `PACIA` instructions with `PACIB` and `AUTIASP` with `AUTIBSP`. Subsequent SDK fiber switches already
  use the shared B-key; PACGA integrity and expected-continuation checks remain intact. See
  [the thread mechanism](../../../docs/reference/threads.md#initial-fiber-frames-on-android-pthreads).
- With both fixes, the run creates the gRPC dispatcher, timer and executor threads and reaches AV1 decoding without parking them.

### Corrected: captured compute execution geometry

All eleven captured compute programs had been translated with `local=[1,1,1]`, `shared=0`: they have no `shader_facts.tsv` row.
Both shader job builders now read ordinary NVN2 dimensions at control `+0x58` and shared bytes at `+0x64` directly.
For example, `d15370a382630d4e` declares `32x2x1` / 3072 shared bytes; `9442573ee4ace011` declares `32x4x1` / 5120 bytes.
All eleven rebuild with those sizes in SPIR-V/reflection. A fresh build of the complete 2,409-key observed-path request produces 2,398 shaders
(168.9 MB), with the same eight opcode-243 and three pool-array/reflection failures. Two non-triangle mesh records are reported as unparseable.
This correctness fix does **not** remove the native compiler failure below.

### Attributed: native compiler allocation failure

`DM_VK_PIPE_TIMING=1` now logs compute pipeline entry, naming creations that abort. The last unmatched entry is
`d15370a382630d4e`, dispatch groups `85x1x1`, including a run with the original three expensive keys skipped.
With corrected execution geometry the failure remains. The original three compile in 44.6 / 12.9 / 2.1 seconds before this fourth program starts.

Android backtraces now strip PAC bits from saved native return addresses and print library offsets for unexported functions.
Observed paths end in `malloc → operator new → libllvm-qgl.so+0xa050bc`, or `libc++.so → operator new[] → libllvm-qgl.so+0x369984`.
Process-filtered logcat reports `Scudo ERROR: internal map failure (error desc=Out of memory)`.

A skip-three run went from **14,515 to 65,993 VMAs**:

| Mapping kind | Before | At failure |
|---|---:|---:|
| Scudo secondary | 215 / 406 MiB | 25,956 / 2,897 MiB |
| anonymous (includes allocator guard/reservation mappings) | 5,783 | 31,520 |
| dma-buf | 6,420 | 6,420 |

RSS rose to about 3.8 GiB. The process address-space limit is unlimited; adb shell cannot read `max_map_count`.
Mapping exhaustion is supported by the count and allocator report; the exact kernel limit was not read. Stable dma-buf counts argue against
dirty-page fragmentation causing this spike. Increasing the guest heap does not address this native path.

The corrected shader is 1,592,244 bytes of SPIR-V. A bounded cleanup sequence (local load/store elimination, SSA rewrite, dead-code elimination,
instruction simplification and ID compaction) produces a validated 1,243,924-byte module in 0.4 seconds. A diagnostic bundle applying that sequence
to all eleven captures still aborts at the same program; the other three still take 43.0 / 13.1 / 2.1 seconds. No optimizer change was enabled
in the production build. Full `spirv-opt -O` was stopped after growing to 7.7 GB without completing.

### Checks and next step

EventFd passes 33 checks normally and with ASan/UBSan. SDK registry (16), paired fiber cuts (3), NVN2 compute job generation on both backends (4),
and shader-chain stamp tests (13) pass. The Android host compiles 267 sources. The available Mac regression harness has no packaged build of
this title. `make -C dm/gfx/tests GAME=0400486024DEC000 run` builds its tests but stops at `check_t_alpha` because the Metal compiler is unavailable.
Full docs checks have unrelated missing-note/link and guide-length failures. Full Python lint lacks ruff in its venv; clang-tidy is unavailable.
Targeted ruff checks pass.

A final diagnostic baseline with the freshly rebuilt bundle, `DM_VK_CSKIP=1`, and **no abort parking** reaches 1,200 presents without a crash.
The last timing window reports p50 16.68 / p95 17.72 ms, GPU p50 2.09 ms; no draw lacks a program, target or pipeline. Frames 200/400/600 and
all three passes dumped near present 400 are 0.00% nonzero RGB. Since all compute is deliberately skipped, this validates startup and pacing,
not rendering correctness or gameplay performance.

The new `DM_VK_COMPUTE_PROBE` mode reproduces the same native allocation failure **before loading any guest code**, allocating its heap or
textures, or dispatching compute. A small shader succeeds (6.73 ms), saves a 6,987-byte cache, and repeats in 0.08 ms with feedback `0x3`
(valid + application-cache hit). The failing shader can now be tested independently:

```
adb shell 'cd /data/local/tmp/oot/diag-20261115/probe && DM_ROOT=$PWD \
  DM_VK_SHADERS=/data/local/tmp/oot/diag-20261115/shaders-fixed.dmsv \
  DM_VK_COMPUTE_PROBE=d15370a382630d4e /data/local/tmp/oot/dmhost-eventfd'
```

An alternate SPIR-V representation through SPIRV-Cross GLSL and `glslangValidator -Od` passes validation and preserves descriptor interfaces
and `32x2x1` execution geometry. Its isolated creation did not finish within a 65-second diagnostic limit; no success or native failure was
observed before the timeout. It is not enabled in the build.

The isolated probe also supports `DM_VK_COMPUTE_PROBE_NOOPT=1` to request `VK_PIPELINE_CREATE_DISABLE_OPTIMIZATION_BIT`.
This still aborts in `libllvm-qgl.so+0xa050dc`; it is not a runtime workaround.

Pre-movie frame 60/100 captures and their passes are 0.00% nonzero RGB. The investigation below subsequently gets beyond this failure with every
compute dispatch enabled. These earlier captures do not establish what a correctly rendered movie/title frame would contain.

## Follow-up (2026-11-15): compiler cache and logical warps

### Resolved for warm runs: native compiler mapping exhaustion

The failing program contains 384 global-load helper calls, 384 global-store helper calls and 768 HMMA helper calls.
Their bodies contain 522, 739 and 1,222 SPIR-V instructions respectively; exhaustive expansion would approach 1.5 million instructions.
`DontInline` does not prevent failure. Replacing helper bodies is useful only as a compile diagnostic: it permits dead-code elimination and
does not isolate a single culprit. Bounded-loop representations of the address search, dirty-page logging and HMMA accumulation also fail
under the normal allocator, including a version with local SSA cleanup. None of these shader substitutions is enabled in the build.

The decisive experiment changes **only the isolated process's allocator**. Microsoft mimalloc v3.6.1 compiles the original program in
53.47 seconds and saves a 2,414,277-byte driver cache. The normal allocator then loads it in 4.48 ms with feedback `0x3` (confirmed cache hit).
The warp-corrected program below compiles in 53.38 seconds; sampling records a maximum of **7,944 MiB RSS and 2,088 mappings**.
Its cache is 2,414,131 bytes and loads normally in 4.43 ms, also feedback `0x3`. The earlier Scudo run failed near 66,000 mappings with much
lower resident memory. This supports allocator mapping exhaustion, not a guest heap shortage. The actual kernel map limit remains unreadable.

This is a platform/driver workaround, not a fix to native compiler memory demand. The ordinary game process uses its normal allocator.
No shader operation is skipped or replaced in the successful compilation. Cache loss, a changed shader or an incompatible driver requires
cold preparation again. The external allocator is not added as a production dependency.

Reproduction artifacts are under `<NSP folder>/0400486024DEC000-work/bringup-20261115/allocator-probe/`.
The source is [Microsoft's tagged v3.6.1 archive](https://github.com/microsoft/mimalloc/archive/refs/tags/v3.6.1.tar.gz), SHA256
`2672e6a99d4579fb4bb32d9de0d63aa424ce600d31fbfaf06eb74d940d2e07a6`.
Build `src/static.c` with NDK arm64 clang, `-shared -fPIC -O2 -DNDEBUG -DMI_DEBUG=0 -DMI_SHARED_LIB -DMI_SHARED_LIB_EXPORT
-DMI_MALLOC_OVERRIDE -ftls-model=initial-exec`, the source's `include` directory, `-pthread -ldl`.
Only the cold standalone probe uses `LD_PRELOAD=/data/local/tmp/oot/diag-20261115/libmimalloc.so`.
See [the general mechanism](../../../docs/reference/shaders.md#native-compiler-exceeds-the-allocator-mapping-budget).

### Fixed: physical wave64 was being treated as a 32-lane warp

A Vulkan property probe reports subgroup size **64**, minimum **64**, maximum **64**. The accessor previously inherited a default of 32.
Generated lane-ID reads were unmasked, shuffles could select the lower physical warp, and ballots/reductions selected word zero.
The upper half's HMMA lane-derived scratch offsets could also exceed the intended warp block.

Android jobs now select the existing wide-subgroup path (`subgroup_size=128`, a bound; actual lane IDs select the physical warp).
Ampere tensor shuffles and MATCH/REDUX additionally use warp-relative sources and active-mask words. Apple jobs retain the default 32-lane
path. The rebuilt translator and chain stamp are `05ce0731d5b8`; the host logs physical subgroup width.

`probes/make_warp32_proof.py` plus `probes/vk_warp32.c` pass **eleven GPU checks**, tested with both `64x1x1` and the game's `32x2x1`
workgroups. Lane IDs, LDSM, MOVM, MATCH, REDUX and all 128 HMMA result words match CPU references. Five safe legacy controls reproduce
upper-warp errors. Legacy HMMA is never dispatched because its scratch accesses can exceed their array. All six default-wave32 fixtures
remain byte-identical between the old and rebuilt translators. See [the general mechanism](../../../docs/reference/shaders.md#logical-nvidia-warps-on-wider-vulkan-subgroups).

The complete bundle rebuild produces **2,398 shaders / 170.2 MB**. Exactly 195 modules change; reflection, keys, stages and flags are
identical for every entry. Runtime-captured modules independently pass SPIR-V validation. The same eight opcode-243 and three reflection
failures remain outside this observed path. The host rebuild compiles 267 sources.

### Current run: all compute executes; the image is corrupted

The corrected bundle's eleven captured compute programs are prewarmed into a 5,393,651-byte cache. The game then runs for a bounded
65 seconds using the normal allocator, **no `DM_VK_CSKIP` and no `DM_ABORT_CONT`**. Every observed compute pipeline creates successfully;
`d15370a382630d4e` creates in 7.79 ms. No native crash is reported before the diagnostic timeout.

Frames 60 and 100 remain black. Frame **200 is 25.71118% nonzero RGB**, with black-and-white rectangular corruption rather than a
recognizable movie or title screen. This supersedes the earlier all-black baseline. Steady frames after compute starts take roughly
**405–420 ms on the GPU** (about 2.4 fps); successful compilation does not make the emulated compute practical.
Artifacts are in `bringup-20261115/device/full-warp32/`, including `frame200.png`, the PPM captures, cache and log.

A second capture at present 200 localizes the corruption before final presentation: pass 0 (`2048x1152`, Vulkan format 122) is completely
black; pass 1 (same size/format) is already corrupted, with 36.60185% nonzero RGB; pass 2 (`2560x1440`, format 37) propagates it.
These images are in `device/trace-warp32/`. A live-control trace near frame 122 records the fourteen compute dispatches between pass 0
and pass 1, including two uses each of `0a56002cdc7e1fce`, `e6be82d835fbe4d3` and `a8b4fb48fee0ccf8`;
the exact ordered log is in `device/late-warp32/`. `DM_VK_TRACE_PASS` selects a **submission pass index**, not a present number:
set `env DM_VK_TRACE_PASS=1` through `DM_CTL` after compute begins to inspect the first corrupted pass's draw and bindings.

The next correctness step is to inspect pass 1's sampled inputs and distinguish bad compute output from its draw's decoding/binding.
The tablet advertises `VK_KHR_cooperative_matrix`, but its F16 shapes are `64x16x16`, `64x32x16` and `64x64x16`, all subgroup-scoped;
it does not advertise the guest's `16x8x16` shape. Hardware acceleration therefore needs a tested packing/lowering design across the
64-lane physical subgroup, not a direct replacement of each 32-lane HMMA. Correct intermediate pixels take priority over that optimization.

Focused checks pass: eleven on-device warp cases, fixture generation/validation, seventeen existing Ampere tests, four compute-state job
tests and thirteen chain tests. The five-title regression attempt selects Ocarina, Mario Kart World, Bananza, Splatoon Raiders and
Fortune's Weave because the shared Vulkan/Ampere paths reach them, but stops because none has a packaged Mac build in the configured
local regression store. Metal compilation is still unavailable. These are validation limits, not gameplay passes.

## Follow-up (2026-11-15): compute inputs and optimizer liveness

### Localized: the copy draw receives corrupted compute output

A late pass-1 trace identifies vertex `8f9728d9b2b88600` and fragment `29e3c9dd92b8a571`. The fragment shader performs a single texture
sample and copies RGBA. Its source is the `2560x1440` sRGB image at pool offset `0x348400`, written by compute
`4f41ccf24f163e0d`. A GPU capture of that sampled image already contains the block pattern, so pass 1 is not its first source.

`DM_VK_TRACE_CS=<hex key>[#n]` now traces a bounded number of dispatches using the existing descriptor trace path. It logs guest buffer
ranges, sampled/storage view formats, texture flags and Vulkan image usage, and saves the traced compute push constants under `DM_ROOT`.
The trace restores normal draw tracing afterward. This is a diagnostic mode; it does not substitute shaders or skip work.

Captures under `bringup-20261115/device/compute-inputs/` and `device/stages-liveness/` distinguish these stages:

| Stage | Observed data |
|---|---|
| AV1 Y plane, `1920x1080` | Y is 16 throughout the sampled frame |
| AV1 UV plane, `960x540` | neutral chroma, bytes 127–129 |
| conversion `49dff010b9832251` output | nearly black RGB; R/B zero, G at most one byte unit |
| reconstruction `4f41ccf24f163e0d` first sampled input | nearly black `1920x1080` RGB10A2, consistent with conversion |
| reconstruction's `512x512` sampled input | all zero in the capture; its intended contents remain to be checked |
| reconstruction's `2560x1440` output | monochrome blocks/bands despite the near-black RGB input |

The captures are from nearby presents, not simultaneous snapshots of an animated frame. Here the black planes and neutral chroma are
stable. Saved conversion push constants contain a plausible BT.709 limited-range matrix and offsets `-16/255, -128/255, -128/255`.
The final compute program also reads storage slot 2, a 12,288-byte buffer. Its real contents and expected role need isolated replay.
The external `pass1-analysis/capture-stages.py` reproduces the sequence, deriving addresses from live descriptors; zero pool offsets
must be accepted as `+0`, not just `+0x...`.

### Fixed: two optimizer errors lose live matrix computation

The old final reconstruction translation had one HMMA call with all ten input locals undefined. Its machine code contains **46** HMMA
instructions. Debug translation also retained the undefined inputs, ruling out expression propagation alone.

The IR dead-code walk followed an instruction when one result became unused without considering its other results. It detached the
inputs of retained multi-result instructions. Recursion now requires that the whole producer satisfies `IsUnused`, including every
destination and side effects. This restores all 46 matrix operations and their live input chains.

An additional GPU regression using only HMMA's second result then failed all 64 outputs: AST cleanup had removed the call assignment
because its returned value was unused. Moving a call into a later expression could also read an out parameter before the call wrote it.
AST optimization now retains call assignments in order, preserving out-parameter and memory effects. This fixes the relevant passes;
it does not disable optimization or force debug-mode shaders. See [the general mechanism](../../../docs/reference/shaders.md#dead-matrix-results-detach-live-inputs-or-erase-output-calls).

The synthetic GPU proof now passes **15 cases**, including either matrix result alone, out-parameter-first reads, and varied lane
fragments/accumulators against an independent exact CPU matrix product. The unsafe pre-fix undefined-scratch cases were checked by
translation inspection before dispatch. Fixture generation additionally checks call retention, input definitions and execution order.

The updated chain is **`8d9d19113b56`**. The complete rebuild contains 2,398 shaders / 189.1 MiB; 305 modules change and all independently
validate as SPIR-V. Ten reflection records change as resource liveness is corrected; every compute-only record keeps its interface.
The same eight opcode-243 and three reflection-overflow failures remain. All eleven corrected compute programs prewarm successfully;
the cache grows to 10,717,318 bytes. Cold compilation sampling peaks at 7,952 MiB RSS and 2,097 mappings with the pooling allocator.

### Fixed: storage descriptors used images without storage usage

Both the conversion output and final reconstruction output were bound for storage writes while their Vulkan images had usage `0x17`,
which lacks storage bit `0x8`. Guest texture flags were zero or `0x8` (compressible), so creation's `IMAGE`-hint check omitted it.
Storage view creation cannot add a usage missing from the parent image.

Creation now includes storage permission for supported uncompressed single-sample colour formats and compatible linear views of sRGB
images. Restricted format lists retain extended usage when storage is available only through the twin. A storage view without the
required parent usage is rejected. Three GPU cases using the renderer's actual policy verify all 192 pixels after UNORM and sRGB
storage writes, including the restricted-list case. The real game now uses `0x1f`; corruption remains, so this is a validity fix rather
than a claimed complete explanation. See [the general mechanism](../../../docs/reference/rendering.md#storage-views-require-image-creation-usage).

### Current result and next investigation

The optimizer-corrected run reaches 300 presents without a reported crash. Frames 105/110 are black; later frames have corrupted bands,
with steady GPU time roughly 380–410 ms. An additional 60-second run with corrected storage usage reaches the frame-200 capture and
still shows the bands. No compute skips, abort parking or shader substitutions are used. These are not recognizable title or gameplay
frames. Artifacts are in `device/full-liveness/` and `device/full-storage/`; the latter includes `frame200.png`.

The next useful reproducer is **`4f41ccf24f163e0d` with its actual sampled textures, 256-byte push block and slot-2 buffer**. Compare CPU
and GPU buffer bytes, then replay a small set of workgroups against known black input and inspect the packed matrix fragments and final
stores. This separates real-data addressing/translation from generic tensor layout, which the varied-fragment GPU test now covers.
Retain the valid storage policy while investigating. Acceleration remains secondary to correct pixels.

Validation passes: 15 warp/matrix GPU cases, three storage-write/readback cases, 305 changed-module validations, 17 existing Ampere
translation tests, four compute-state tests, 13 chain tests, four tool-lock unit tests and the 267-source Android build. The five-title
Mac regression attempt remains unavailable for the same missing packaged builds, and the Metal toolchain is absent.

## Follow-up (2026-11-15): BananaNative comparison and reconstruction replay

### Captured: one dispatch with its real inputs

BananaNative's Android profile lists the same `main`, `subsdk0` and `sdk` build IDs as this dump. Its
[tensor emitter](https://github.com/shamonj03/BananaNative/blob/341299f727c85fa5c58b1c44f7a7a8edabc905cc/dm/third_party/ryujinx/src/Ryujinx.Graphics.Shader/Instructions/InstEmitAmpereTensor.cs)
distinguishes LDSM's transposition encoding from the ordinary shared-memory stride. Its gameplay reports also
include NDVE movie bypasses, so they do not establish this movie path's correctness.

`DM_VK_CAPTURE_CS=4f41ccf24f163e0d#150` captures the first matching dispatch at or after present 150.
The opt-in debug path saves raw GPU buffer/image copies immediately before and after the dispatch, exact view
formats and sampler parameters, CPU storage bytes and push constants. It waits for readback and perturbs scheduling.
The reusable standalone runner is `probes/vk_compute_replay.c` in the parent workspace. Version 1 explicitly
refuses unsupported descriptor shapes or shader variants.

The captured dispatch is `80x180x1`, local `128x1x1`. Its 12,288-byte slot-2 buffer (Vulkan binding 4) matches the
CPU bytes exactly and is unchanged after dispatch. The sampled views are RGB10A2/Vulkan 64 at `1920x1080` and
`512x512`; the output is an sRGB/Vulkan 43 image with linear storage view 37 at `2560x1440`.
The first input is nearly black; the second contains zero bytes. The push segment matches the earlier 256-byte capture.

### Fixed: transposed LDSM multiplies a byte address by four

The original standalone replay reproduces the bands. Identical-input repeats differ at 723,686 of 3,686,400 pixels.
Pointer instrumentation finds 44 shared-memory access sites outside the shader's 4,608-byte allocation, each failing
in all 128 invocations of the first workgroup. LDSM's transpose bit was passed to the ordinary LDS/STS stride decoder,
which shifted the base byte address left by two. LDSM now bypasses that scaling while retaining the optional uniform
address and signed offset; other memory instructions retain their stride. See the general finding linked above.

With the fix, all 239 instrumented shared/storage pointer sites in the first workgroup stay in range. Two uninstrumented
full-dispatch replays are byte-identical. Only 46 output pixels have nonzero RGB, and every RGB byte is 0 or 1, consistent
with the captured near-black source; the bands are gone. The new transposed 8x8 half-matrix test and the previous fifteen
GPU cases pass on the Adreno 840. This fix does not add LDSM barriers or change HMMA arithmetic.

The full bundle remains 2,398 of 2,409 shaders / 189.1 MiB: **32 compute modules change**, all independently validated,
and no reflection changes. The same eight opcode-243 and three reflection-overflow failures remain. Current chain:
**`db201a5c1896`**. All eleven observed compute pipelines prewarm successfully; the cache is 16,034,104 bytes.
The allocator preload is used only for isolated cold compilation, as before.

### Measured separately: HMMA lowering

BananaNative's `hmma_lds` from the pinned revision was tested externally on the corrected reconstruction module.
With two retained tiles it lowers all 46 helper calls, validates and produces a byte-identical result for this capture.
One submit/readback measurement was 27.8 ms, against 66.6 ms for the corrected scalar helper; these single samples include
readback and are not a benchmark or a whole-frame prediction. The lowering remains an external experiment, not a shipped
shader-chain change. Non-black real inputs and broader precision/synchronization checks remain necessary.

### Current result

A normal-allocator 90-second game run reaches at least 300 presents without a reported crash or red log line,
then ends at its configured timeout.
Frame 200 is now fully black, with no bands. This is not a recognizable title/movie/gameplay frame. GPU time remains
about 400 ms: the performance experiment is not enabled. No compute skip, movie bypass, abort parking or shader substitution
is used. The decoder log reports dav1d 1.5.4 and a first `1920x1080` picture; it does not prove that later pictures are non-black.
The next investigation is the decoded movie input and its delivery into the conversion path, retaining this reconstruction replay
as a regression and comparing non-black input before adopting acceleration.

Artifacts: `bringup-20261115/reconstruction-replay/` (exact capture, scalar/experimental SPIR-V, bounds scripts/counts,
outputs and frame-200 image), `device/prewarm-ldsm/`, `device/full-ldsm/`, and `shaders-ldsm-build.log`.
Android host build, sixteen GPU cases, 32 changed-module validations, Ampere memory tests, compute-state tests and chain checks pass.
The five-title Mac regression remains unavailable because its packaged builds are absent. Documentation tests retain the pre-existing
missing game-note/Skyrim links and debugging-guide length failures.

## Follow-up (2026-11-15): decoder-to-GPU provenance

### Resolved as expected input: the early black movie frames

The early black captures did not establish a decoder or texture-delivery fault. The active movie is
`Event/Movie/Dm_Title_0005.webm`, identified by a byte-exact match of the decoder's first submitted packet to
the source file's first video packet (370 bytes, SHA-256 `4ece583d775fd427ff989538571db1285bf82aec5b904fa3a0f00db7081da89e`).
The source begins with a long dark fade. Its first submitted timestamp is zero; packet 60 is at 0.983 seconds.
Host elapsed time is not movie time: the roughly 400 ms GPU frames make this short fade take well over a minute.

`DM_CV_PIXELS=1` now traces decoder delivery and client NV12 readback. `DM_CV_DUMP=1` optionally saves sampled
pictures and each decoder's first packet under `DM_ROOT`. Both are opt-in diagnostics, with no change to normal
decode behavior. See [the general tracing procedure](../../../docs/reference/movies.md#av1-movies-through-sdk-22s-decoder).

Independent checks on the longer run:

- Decoded pictures **153** and **420** match FFmpeg's source-file NV12 output byte for byte, all 3,110,400 bytes each.
  Their CPU NV12 readbacks are also byte-identical. Picture 153 has luma 16–33, picture 420 17–119.
- The GPU conversion capture at present **450**, shader `49dff010b9832251`, contains source movie picture **344** exactly:
  its R8 Y and RG8 UV bytes concatenate to the same NV12 frame. There is no observed plane upload corruption in that sample.
- A separate CPU BT.709 conversion, using the captured coefficients, limited-range offsets and bilinear chroma sampling,
  matches the GPU's RGBA8 output within **one byte per RGB channel**, with alpha 255 throughout.
- Presents **350**, **400**, **450** and **500** show the moonlit field without the former reconstruction bands. The run
  delivers at least 439 movie pictures and ends at the configured 180-second timeout without a reported crash or red log line.

The apparent lower/right border in raw screenshots is unused backing, not a demonstrated display fault. The game logs
`WindowCrop 0,0 2048x1152` for its `2560x1440` window image. Headless `DM_VK_SHOT` saves the entire backing image;
the window presenter already takes the crop. `decoder-analysis/frame500-crop.png` applies that explicit crop for inspection.
This is recognizable movie rendering, not title-menu or gameplay validation, and it remains far below real-time speed.

Artifacts: `bringup-20261115/device/decoder-long/` (raw source/readback samples, GPU conversion capture, original screenshots
and log), `decoder-analysis/` (independent source samples, conversion check and cropped screenshot), and the earlier
`reconstruction-replay/`. The Android host builds all 267 sources. The codec protocol/readback suite passes with ASan/UBSan,
both with tracing disabled and with `DM_CV_PIXELS=1`; the Mac run needs access to VideoToolbox outside the sandbox.

### Non-black reconstruction replay and acceleration candidate

An additional normal-allocator run captures `4f41ccf24f163e0d` at present 350 with non-black input.
The in-game output, two scalar replays and two replays with BananaNative's two-tile HMMA lowering are all byte-identical
(14,745,600 bytes each, SHA-256 `f2dd2d295aa9e7a5fed3de6dbf804aa297ce33fe080895134f5098765c3e62f1`).
The output has 10,501,741 nonzero RGB bytes. Scalar submit/readback times are 66.66 and 75.33 ms; lowered times are
33.65 and 32.69 ms. These few samples include readback, not a controlled throughput benchmark or a whole-frame prediction.
This extends the earlier black-input check to real movie data. The lowering remains external, not part of the production shader chain.
Artifacts: `device/reconstruction-colour/` and `decoder-analysis/reconstruction-colour-results.json`.
The next priority is compute acceleration with broader shader/precision checks, followed by the title-menu and gameplay path;
there is no observed decoder or NV12 upload bug to patch in these samples.

## Follow-up (2026-11-15): integrated HMMA acceleration

### Implemented and checked

The Android build now applies bounded vector HMMA gathers to the recognized translator helper. This is the narrow
BananaNative-derived lowering described in [the general mechanism](../../../docs/reference/shaders.md#vector-hmma-gathers-with-bounded-tile-reuse),
with its MIT notice retained. Other upstream global-memory/SSA transformations are not imported. The pass preserves the original
FMA sequence and half rounding, tracks fragment changes and retains at most two converted tiles between calls.

The acceleration measurement uses chain **`81febb969b11`**, including `shader_vk.py` and `hmma_spv.py`. The full bundle builds **2,398 of 2,409** entries,
now 261.4 MiB. It lowers **15,832 calls in 62 compute modules**; all 62 independently validate, and every reflection record is
unchanged. The same eight unsupported opcode-243 and three reflection-overflow failures remain. All eleven observed movie
pipelines prewarm; the final cache is **20,762,829 bytes**. The ordinary game run uses the normal allocator and no compute skips.
Cold prewarming still uses the previously documented allocator preload; this change does not establish its removal.

The narrowed integrated pass reproduces the real non-black reconstruction capture byte for byte. Twenty GPU cases pass,
including dependent tile reuse and fragments overwritten by an earlier output. Fractional and subnormal cases compare exactly
with the original scalar helper on the same GPU. A one-half-ULP fractional difference from a strict CPU `fmaf` reference is present
in the original helper too; it is measured and retained, not silently attributed to the new pass. Integer CPU matrix cases remain exact.

The first integration (`a0a454bc03f9`) missed `ba079f68ae288dba`: its scratch variable has ID 40, and 72 `OpExtInst` instructions
outside the helper also contain the literal instruction number 40. The conservative scratch-use scan mistook those literals for IDs.
Excluding that literal operand recognizes the same exclusive-scratch contract without accepting actual outside accesses. A synthetic
opcode collision and a real outside access test both paths. This lowers 72 more calls; both real storage outputs match their captured
scalar counterparts byte for byte. This shader was unchanged in the first timing comparison, but it does contain HMMA.

Retaining zero, one or two tiles gives identical real reconstruction output. Two retained tiles remain the fastest tested setting:
about 34–35 ms including replay readback, versus 37 ms with one and 40–43 ms with zero. These are short, uncontrolled replay
measurements. For `a8b4` and `e6be`, retaining one already produces the same module as retaining two.

### Whole-frame measurement

`DM_VK_PASS_TIMES=1` now includes compute dispatches by key. `DM_VK_PASS_REPORT=200` reports at present 200;
setting it to 1 through `DM_CTL` requests the next report. The completion thread and report path synchronize their statistics.
The scalar and integrated runs use the same device, game route and graphics settings, with warmed pipelines:

| GPU work | Scalar | First integration | Final integration |
|---|---:|---:|---:|
| Sum of timed steps per frame | 401.61 ms | 221.16 ms | 215.40 ms |
| `e6be82d835fbe4d3`, each of two dispatches | 71.00 ms | 32.24 ms | about 32.1 ms |
| Reconstruction `4f41ccf24f163e0d` | 70.83 ms | 26.40 ms | 26.41 ms |
| `a8b4fb48fee0ccf8`, each of two dispatches | about 31.5 ms | about 25.9 ms | 25.92 ms |
| `ba079f68ae288dba` | 33.17 ms | 33.12 ms (unchanged module) | 27.56 ms |

This is about **46% less timed GPU work**, or **1.86x throughput**, still only around **4.6 fps**. It is not real-time playback.
The comparison is not controlled for clocks/temperature, and timed steps exclude unrecorded gaps. The unchanged shader's cost
in the first comparison is a useful control. Remaining major costs include the two `e6be` passes, two `a8b4` passes and `ba079`.
The final measurement also uses the corrected timestamp-reader lock: statistics are updated only after a successful query read.

### Navigation and remaining validation

Normal controller scripts use separate copies of the test save, with no host movie bypass or abort parking.
Short presses, five-frame holds and repeated Plus/A presses before present 600 do not establish a menu transition.
The longer `menu-long` run renders the title logo fading in at present 1,275 and fully visible at 1,500. Its route is
`f2600:A~f9,f2950:A~f9`, adapted from BananaNative's Mac test route. After the first A press the logo fades, the decoder reinitializes
at present 2,759 and the tapestry intro renders at 2,800 and 3,000. The second A does not establish another transition by the end of
the run. No missing shader keys or red diagnostics appear. This run uses the first integration; the final integration is separately
checked on the ordinary movie route. The lower title prompt appears as a dark rectangle without readable text; a recognizable menu,
its navigation and gameplay are still open. The test save contains only `account.sav`, without a gameplay checkpoint.

Artifacts: `hmma-acceleration/` (first build and `timings.json`), its `literal-guard/` (final build and 62-module validation),
`hmma-precision-proof/`, `device/prewarm-hmma/`, `device/timing-scalar/`, `device/full-hmma/`, `device/menu-long/`,
`device/timing-literal/`, and the `device/title-*` route folders.
Validation passes: twenty GPU cases, five lowering contract tests, sixteen existing warp/matrix cases, compute-state tests,
chain-header and tool-lock/environment checks, and the 267-source Android host build. The five-title Mac regression remains
unavailable for absent packaged builds; full Metal rebuilds remain unavailable for the missing Metal toolchain.

## Follow-up (2026-11-15): guarded scoreboards and menu text

### Missing text resolved at the glyph producer

The title's dark prompt was collapsed geometry, not an empty font or a failed upload. The first glyph target is
**242x40 RGBA8**, drawn with vertex shader `b19e1bdd247555ec` and fragment shader `9b310b3349825e9a`.
Its sampled **256x46 R8** atlas contains readable **New Game** text in both the CPU pool and an independent GPU readback.
The sampled view correctly maps `(ONE, ONE, ONE, R)`. The following blur masks were empty because their glyph input was empty.

Capturing the actual glyph SSBO and uniform inputs, then replaying the real vertex arithmetic as compute, shows that all
twelve vertices of each of the seven visible glyph instances have identical Y before the fix. Their X coordinates vary.
After the shared [guarded scoreboard correction](../../../docs/reference/shaders.md#guarded-deferred-writes-overwrite-newer-register-values),
the same captured inputs produce positive glyph height and varying UV Y. Both glyph shaders retain identical reflection records.
A focused renderer run with only these two shader overrides restores readable **New Game** and **Options / ZELDA NOTES Setting**.
That focused run skips the eleven movie-network dispatches to reach the UI quickly; it establishes the glyph fix, not normal movie performance.

The relevant BananaNative lesson is its issue-time predicate handling, read at pinned MIT-licensed commit
`341299f727c85fa5c58b1c44f7a7a8edabc905cc`. The port is a shared translator fix; it adds no game-code skip or profile exception.

### Rebuild and validation

Current chain **`aea015ee5502`** rebuilds **2,398 of 2,409** observed-path entries into a **275,140,288-byte** bundle.
The same eight unsupported opcode-243 and three reflection-overflow failures remain. Compared with `81febb969b11`,
**1,508** modules change: 270 stage-0, 764 vertex, 439 compute and 35 stage-7 entries. Two reflection records change,
`6a1ceebb6cff56dd` and `eebdb9347d09b344`; each now retains an additional constant-buffer register 3, and neither is a glyph shader.
Three of the eleven movie compute modules change:
`4f41ccf24f163e0d`, `a8b4fb48fee0ccf8` and `ba079f68ae288dba`. All eleven pipelines prewarm successfully into a
**21,271,066-byte** cache. Isolated cold preparation retains the allocator preload; normal game verification does not.

An independent audit of every final module validates **2,391 of 2,398**. Seven vertex/stage-0 modules have an out-of-bounds
`OpCompositeExtract` (index 2 from a two-component vector); all seven reproduce the same error in `81febb969b11`.
These are pre-existing bundle defects, not resolved by this change: `1dc31f7fad13d519`, `21103450c76efd53`, `245a89d413e76f0f`,
`90c7de8d352a1650`, `94087d5d532eabb3`, `d9bb4bdb13d711fb` and `ee3c935e9b6080a7`. Runtime coverage of these keys remains open.

### Ordinary movie route

The full bundle, normal allocator and ordinary compute route render readable **New Game** and **Options / ZELDA NOTES Setting**
at present **1,500**, over the movie's field. This run uses neither shader overrides nor compute skips nor abort parking.
A live report measures **213.39 ms** in timed GPU steps per frame, consistent with the earlier acceleration result and still far below real time.
The scripted navigation route is `f1600:Down~f9,f1750:A~f9,f1900:B~f9`, with captures at 1,500, 1,650, 1,800 and 2,000.
Those captures verify the selection highlight moves to Options, the settings screen opens and B returns to the title with
Options still selected. The Options header and setting values render, but some setting labels are absent; this is a separate
remaining UI investigation. This does not establish gameplay or complete settings rendering.

Eleven synthetic scoreboard GPU cases pass; seven fail with the old translator. The automated regression independently
folds nine constant-predicate programs to their expected final register values. Twenty fresh warp/matrix GPU cases pass,
including fractional/subnormal HMMA comparisons, dependent reuse and output aliasing. The existing sixteen-fixture warp
translation test, five HMMA contract tests, four compute-state tests and thirteen chain tests pass. The Android host builds
all 267 sources. The five-title regression check was attempted for Ocarina, Mario Kart World, Bananza, Splatoon Raiders
and Fire Emblem Fortune's Weave; their packaged Mac builds are absent, so no cross-title runtime pass is claimed. Full Metal rebuilds
remain blocked by the unavailable Metal toolchain.

Artifacts under the external work folder's `bringup-20261115/ui-text/`: `guarded-shaders/` (full build, comparison and bundle),
`scoreboard-before-full/` and `scoreboard-after/` (eleven-case negative control and corrected GPU proofs), `vertex-replay/`
(identical-input vertex proof), `ui-glyph/` (captured inputs), `gpu-font-atlas.png`, `ui-fixed/frame_001553.png` (focused menu),
`hmma-guarded-proof/` (fresh twenty-case fixtures), and `menu-guarded/` (ordinary full-bundle route).
`guarded-shaders/validation.json` records the whole-bundle audit and its previous-chain negative controls.
`test-results.json` records the focused automated checks. Documentation checks still have the same three unrelated failures:
the absent `0100005027A18000` game note, missing `BRINGUP_SKYRIM.md` links and the over-length debugging guide.

## Follow-up (2026-11-15): menu shader coverage and New Game

### Resolved: the visible Options labels were absent from the bundle

The previous ordinary menu run captured **19 missing shader keys**. All are already in `shader_map.tsv`: layout
vertex/fragment programs and agl common/post-processing programs. They were omitted from the selected development
bundle, rather than failing translation. Rebuilding the selection with those keys produces **2,417 of 2,428** entries,
**275,602,400 bytes**, on the unchanged chain `aea015ee5502`. Every previous entry's stage, SPIR-V, reflection and flags
is byte-identical; all 19 added final modules independently pass `spirv-val`. The same eight opcode-243 and three
reflection-overflow failures remain, as do the previously documented seven invalid modules in the older portion.

The ordinary `options-newgame` run uses the normal allocator, no compute skips, no shader overrides and no abort
parking. Its route is `f1600:Down~f9,f1750:A~f9,f1900:B~f9,f2100:Up~f9,f2250:A~f9`, starting from a separate
empty test save. At present **1,800**, the Options screenshot now shows the amiibo/ZELDA NOTES panels, camera-axis
labels, rotation speed, motion aiming, targeting type, swap-jump label and right-hand explanation. The movie background
is blurred and the panels render correctly. This verifies the visible settings page; lower scrolled rows remain untested.
GPU p50 through frame 1,800 is **214.71 ms**, consistent with the earlier result. No new translator fix is needed for these labels.

### New Game reaches the narrated opening

After returning from Options, Up selects New Game and A begins its transition. Present **2,300** still shows the title
without a selected highlight; **2,500** shows the tapestry opening. Presents **2,700**, **3,200** and **3,551** show
readable narration subtitles and progression from the castle to the forest panel. The summaries through present 4,200
report **zero** draws skipped for missing programs, targets or pipelines, and zero skipped compute dispatches.
No missing shader keys, red diagnostics or crash are reported on this route.

Live Plus, X and A inputs are saved in `options-newgame/ctl`; these captures do not establish a complete movie skip or
attribute the narrative transitions to a particular press. The decoder state trace continues delivering pictures
(1,464 to 1,524 in consecutive observations), so the captured opening is progressing. `DM_KBD=Link` is configured
for any later software-keyboard request, but none has been observed. This verifies New Game's opening sequence,
not player-controlled gameplay or a gameplay save checkpoint. The normal movie route remains around 215 ms GPU per frame.
The run ends at its configured **900-second timeout** (exit 137); no owned test process remains on the tablet.

A separate coverage candidate translates **all 145 layout shaders**, with no translation failures and independent
validation of every final module. Merging them with the 2,417-entry bundle adds **113** entries and preserves every
existing entry byte for byte, yielding **2,530** entries / **278,465,164 bytes**. This candidate is staged separately on
the tablet; it is not the bundle used for the frame-1,800 verification.

Artifacts: `ui-text/options-complete/` (build and `comparison.json`), `ui-text/options-newgame/` (exact run command,
log and `frame_001800.png`), and `ui-text/layout-coverage/` (145-program bundle, merged candidate and `validation.json`).
The implementation checkpoint is commit `f56081c4`; the 43 focused shader/SDK/chain/patch tests and 33 EventFd checks
pass. Fresh documentation checks retain exactly the same three failures listed above; no new link failure is reported.

## Follow-up (2026-11-15): shuffle experiment and missing global writes

### Result: retain the current gather lowering

The Triforce review at commit `93eeb714c2f2d9dda543447564ee953f417b9c38` suggested a compact shuffle helper
and separate numerical checks. `probes/hmma_shuffle.py` independently implements our translator's fragment mapping
and FMA order; no Triforce code is copied. The default candidate retains final-only half rounding, a bounded loop
and helper calls. Production chain `aea015ee5502` and the 2,417-entry bundle remain unchanged.

Both kernels were captured from the ordinary movie route on the Adreno 840 tablet, driver `0x8034a01f`, physical
subgroup 64. Each comparison uses the same complete captured dispatch and input bytes. After four warmups, each
implementation has 48 timestamp samples in gather/shuffle/shuffle/gather order, resetting every input between samples.
Pipeline compilation, transfers and readback are excluded. Rounded aggregate medians:

| Kernel / dispatch groups | Current gather | Compact shuffle | Candidate cost |
|---|---:|---:|---:|
| `e6be82d835fbe4d3` / `120x1x1` | 31.97 ms | 86.02 ms | 2.69x |
| `a8b4fb48fee0ccf8` / `720x1x1` | 25.93 ms | 69.34 ms | 2.67x |

Both use local size `32x1x1`. The candidate reduces SPIR-V size from 4,068,356 to 1,170,596 bytes and from
427,484 to 204,508 bytes respectively, but is substantially slower. A separate unrolled version is slower again:
321.73 and 106.94 ms (12 samples each). These are measurements of the currently incomplete workload, not a
gameplay FPS estimate or evidence of correct neural reconstruction.

### Numerical checks and the deeper blocker

The default candidate passes all twenty existing GPU warp/matrix checks, including varied nonzero fragments,
both result-use orders, aliasing, reuse, fractional halves and subnormals. Fractional and subnormal results match
the separately compiled scalar GPU helper. The separate `--rounding 8` model changes 32 of 128 words in the
fractional fixture; nineteen checks pass. This establishes a numerical difference, not which model matches Ampere.

Neither real capture changes any of its bound storage buffers, even with the production shader. The `a8b4`
scalar/default/midpoint matrix traces are identical but entirely zero; the completed `e6be` default trace is also
entirely zero. Scalar and midpoint `e6be` trace pipeline creation fails with native `std::bad_alloc`; no numerical
comparison is claimed for those variants. All-zero traces are inconclusive even where both versions execute.

The [reserved global-memory descriptor defect](../../../docs/reference/shaders.md#android-reserved-global-memory-descriptors-bind-zero-buffers)
explains the missing raw stores. This qualifies earlier movie and timing results: source decoding, GPU movie
planes, readable menu pixels and navigation were verified, but faithful neural feature propagation was not.

The replay tool now reports observable writes, can reject unchanged outputs, and times independently reset
dispatches. An incrementing-buffer proof changes the expected 32 words, preserves the remaining 32, and stays
identical over two warmups and nine samples. The no-change guard rejects the real `a8b4` capture with exit 4.
Three new shader-interface/rejection tests pass; the probe builds with `-Wall -Wextra -Werror`.
The 27 existing HMMA, warp, compute-state, chain and toolchain checks pass. Documentation checks retain the same
three unrelated failures listed above; the regenerated symptom index is current and no new broken link is reported.

### Next work

1. Implement Android's reserved pool table and write log, including Vulkan device-address translation, pool
   lifetime and CPU/GPU visibility. Verify a synthetic indirect global store with nonzero data before another game run.
2. Recapture actual neural feature propagation, including raw-address destinations; extend replay to capture and
   relocate those pools. Establish meaningful nonzero output equivalence, then remeasure the full ordinary route.
3. Revisit native matrix tiling only after that baseline. The tablet exposes F16 cooperative tiles of `64x64x16`,
   `64x32x16` and `64x16x16`, with subgroup size fixed at 64. It does not expose Triforce's direct `16x8x16` shape;
   using native matrices requires retiled work and a fresh fragment-layout/rounding proof.

Artifacts remain under external `bringup-20261115/hmma-shuffle/`: `report.json` (hashes, results and limitations),
`capture/`, `abba/results.json`, `fixtures-r16.log`, `fixtures-r8.log`, `trace-results/`, `replay-reset-proof/`,
`device-properties.log` and `nochange-guard.json`. No performance candidate is promoted to production.

## Follow-up (2026-11-15): global writes execute and expose neural corruption

### Reserved bindings and device addresses corrected

The shared [Android global-memory correction](../../../docs/reference/shaders.md#android-reserved-global-memory-descriptors-bind-zero-buffers)
implements the translator's reserved pool map and write log, Vulkan device addresses and visibility of indirect writes.
There is no game-specific exception or compute skip. The first implementation conservatively waits after each operation
with indirect stores, before later replay operations can read guest data. It does not predict future write pools.

Chain **`4f0c7f8b9136`** rebuilds the complete development selection: **2,417 of 2,428** programs. All existing shader
SPIR-V, stages and entry flags are byte-identical; **88** reflection records change. There are **88 map** and **8 log**
bindings. The same eight unsupported opcode-243 and three reflection-size failures remain. The earlier seven invalid
vertex/stage-0 modules are unchanged. The Android host builds all **267** sources.

The actual renderer passes **27** new device checks: nine each with ordinary zero-copy, forced copied and lazy-copied
pools. The targets are never bound directly. Checks cover nonzero indirect atomics, preserved canaries, repeated writes,
log overflow, unmapped addresses and re-registering the same guest address. The copied-pool test caught a real first-pass
bug: synchronization published indirect destinations but left ordinary bound outputs stale. Both now become visible.
Another **135** related device checks pass for driver state, pool registry, copied bindings, scratch retirement,
timestamps and shared spill. **47** targeted Python tests pass, including three new reserved-descriptor tests.

### Actual feature propagation and remaining wrong picture

The ordinary 300-second diagnostic run uses the normal allocator and complete rebuilt bundle, with no movie bypass,
abort parking, shader override or skipped dispatch. `e6be82d835fbe4d3` is captured at present **350**, and
`a8b4fb48fee0ccf8` at **515**. The first kernel's 8,294,432-byte feature binding now contains **4,243,639 nonzero bytes**;
the second kernel's 16,588,832-byte binding contains **15,830,365**. Both older captures had only **21** nonzero bytes.
Their weight bindings are still populated. The pool map now has 131,072 bytes with valid ranges, and each fresh 4,100-byte log
changes after dispatch. Most large dispatches overflow the 1,024-page log; the visibility path handles that explicitly.

The feature bindings are inputs, so they stay unchanged across these individual producer dispatches; their raw-address
destinations are separate. These captures establish active propagation, not complete output equivalence. They explicitly
mark raw global bindings, and the v1 replay tool rejects their unrelocated physical pointers. Capturing indirect pools
and relocating them remains necessary before an exact-input replay can validate all writes.

Presents **350**, **500** and **800** show colored blocks, incorrect colors and a visible pixel grid. The field remains
recognizable at 800, but this is not a correct reconstructed movie. The missing stores had concealed this next defect.
No corrected nonzero-network image or hardware-accurate matrix result is claimed. The binding fix is retained in the
diagnostic build; that build is not promoted as a rendering improvement.

### Performance of the active path

Through frame 900, GPU p50 is **310.64 ms** and frame-time p50 **313.92 ms** (about **3.2 fps**). The pass report totals
**299.95 ms** in timed steps. The largest costs are `ba079f68ae288dba` at **41.53 ms**, the two `e6be` passes at
**39.74 / 40.01 ms**, and the two `a8b4` passes at **39.93 / 39.98 ms**. Reconstruction `4f41ccf24f163e0d` costs
**26.33 ms**. Most frame time is in the GPU steps, although the conservative synchronization also costs time.
These numbers are not directly comparable to the older incomplete network as an implementation speed regression.

A separate **180-second** run of the final source disables compute capture and limits global-write diagnostics. It reaches
frame **600** with GPU p50 **307.83 ms**, frame-time p50 **310.73 ms**, and **297.74 ms** in timed steps. It reports no
red diagnostic, skipped draw or skipped dispatch, and ends at the configured timeout. The final source's three pool-mode
proof runs also pass. No owned test process remains on the tablet. The bad movie colors remain visible in this run.

Next: find the first incorrect nonzero feature or reconstruction result, validate its layout and arithmetic independently,
then revisit performance. The earlier shuffle comparison does not establish which method wins on the now-active network.
Native matrix retiling remains deferred until that correctness baseline exists.

Artifacts under external `bringup-20261115/global-memory/`: `proof/` (synthetic and related device results), `shaders/`
(full build, exact command and byte comparison), `run/` (two captures, feature summaries, screenshots and log), and the
run command/exit records. The first run ends at its configured 300-second timeout, not a game crash.
Cross-title Mac checks remain unavailable for absent packaged builds. A full Mac shader build was attempted, but stops
at `ValueError: NVN2 mesh output is not a triangle list` while reading unsupported mesh metadata; no full Mac/iOS library
stamp is validated. Metal itself is now available and the host's thirteen built-in Mac libraries compile successfully.
Python lint reports unrelated findings in untouched files, and clang-tidy is not installed. Documentation checks retain
the three known unrelated failures. No change has been committed in this follow-up.

## Follow-up (2026-11-16): nonzero layer replay and memory ordering

### Current: full neural movie reconstruction renders cleanly on Adreno

The first incorrect nonzero operand is now traced and corrected in the shared translator. With the full rebuilt bundle,
ordinary allocator, every movie dispatch enabled and no shader overrides, **frame 350** shows the moon, clouds and landscape
without the previous colored blocks or green moon. The run reaches frame **600** and is deliberately stopped after its
capture and timing report. This validates the observed movie route on the Adreno 840; it does not repeat menu/gameplay UAT.

This is a correctness improvement. The frame-600 report gives frame time p50 **315.51 ms**, p95 **322.31 ms** and GPU p50
**312.38 ms**, p95 **318.80 ms**, approximately **3.17 fps**. The one captured frame is excluded from steady-state conclusions;
its readbacks cost extra time. No frame-rate improvement is established. Per-dispatch timing of the corrected network is
the current performance baseline; earlier results with missing global writes are not a valid complete-network comparison.

A separate warm Adreno run disables capture and enables `DM_VK_PASS_TIMES=1 DM_VK_PASS_REPORT=200`. Its 17 timed steps
sum to **303.70 ms** per frame. The dominant compute work is:

| Shader | Dispatches per frame | GPU time per dispatch | Combined |
|---|---:|---:|---:|
| `e6be82d835fbe4d3` | 2 | 41.93 / 41.75 ms | 83.68 ms |
| `a8b4fb48fee0ccf8` | 2 | 39.15 / 39.14 ms | 78.29 ms |
| `ba079f68ae288dba` | 1 | 41.49 ms | 41.49 ms |
| `4f41ccf24f163e0d` reconstruction | 1 | 28.77 ms | 28.77 ms |

The first three keys account for **203.46 ms, 67%** of timed work. They all use raw output stores. The next experiment
should separate matrix work from raw address lookup and write-log cost using the complete-pool replays, then improve
the dominant proven path. This timing does not yet attribute their cost to either mechanism or establish that compact
shuffle arithmetic is faster. Input conversion takes only **0.39 ms**; render steps are below **0.2 ms** each.
The 50-second timing run ends at its configured TERM timeout with a graceful exit, not a crash.

### Trace from complete pools to the first wrong fragment

One movie frame now captures all **14 dispatches**, including both uses of repeated kernels. All neural weights, activations
and raw output destinations reside in one **50,569,216-byte pool**. Capturing its full before/after contents preserves
aliases between bound SSBO ranges and raw destinations, which separate descriptor allocations would lose. The guarded v2
replay relocates actual Vulkan addresses and rejects uncaptured physical accesses; its valid synthetic aliased case passes
reset repetitions, while the missing-range control fails with exit 6 before dereference.

Across **13 of the 14 dispatches**, 25 production/scalar replays reproduce complete pool and storage-image outputs byte for
byte, with no uncaptured accesses. Both guarded variants of `d15370a382630d4e` abort during cold driver compilation, so that
isolated comparison remains unavailable. The input conversion also passes an independent CPU check across **2,073,600 pixels**:
maximum error one byte, no channel over one byte. Equality between shader implementations alone would not prove correct math.

Independent sampled convolution checks stay close through the downsampling stages, then first diverge substantially at
the 64-channel 3x3 convolution `0a56002cdc7e1fce` (sequence 6). The original scalar helper's first-warp operand trace identifies
calls **68/69**: their B tiles contain kernel tap 8, input channels **48–63**, where **32–47** are required. The next two calls
consume 48–63 again. A operands, the other B tiles and accumulator chaining agree with the expected tensor layout.
The [general finding](../../../docs/reference/shaders.md#expression-propagation-delays-mutable-reads-past-overwrites)
describes the delayed shared load and the AST correction. No Triforce implementation was copied.

On identical captured inputs, maximum sampled error against CPU float32 FMA/K16-half convolution falls from **1.20325** to
**0.00585938**. A fresh layer capture from the corrected full game has the same maximum and **zero of 33,088 checked values**
over 0.01. Small half-rounding differences remain; this does not claim bit-exact Nintendo hardware arithmetic.
Two focused Adreno GPU fixtures return the overwritten integer 99 in all 64 words before the correction and the saved 17
in all words afterward. The same two small fixtures also pass on the Mac GPU as a shared-translator regression; full-game
rendering and frame-rate evidence in this follow-up come from the Adreno tablet.

### Rebuild, compiler cache and validation

Chain **`dd39582388d1`** produces **2,417 of 2,428** programs, **277,209,504 bytes**. Relative to the preceding global-memory
bundle, **2,349** SPIR-V modules and **10** reflection records change; keys, stages and flags are unchanged. Nine reflection
records retain additional buffers, and one only changes binding-record order. The same eight opcode-243 and three reflection
overflow failures remain. Independent validation of every final module retains exactly the seven previously documented
vector-extract failures. Both translator launch architectures build, the universal launcher and pinned tool fingerprints
are updated, and the Android host rebuild compiles **267 sources with zero failures**.

The first ordinary cold launch aborts while compiling the large neural kernel. The existing isolated allocator workaround
prepares all eleven compute pipelines, including `d15370a382630d4e` in **34.35 seconds**, into a **4,585,700-byte** cache.
The successful full game then uses that cache with its normal allocator. This remains a cold-compiler workaround, separate
from the memory-ordering fix; cache loss still requires preparation.

The focused capture/guard/CPU tests, Ampere memory, scoreboards, HMMA, control flow and chain checks pass. Required five-title
Mac regression is attempted for OOT, Mario Kart World, Bananza, Raiders and Fortune's Weave because they share translator
memory/tensor paths; all lack packaged Mac builds. The full Mac shader rebuild again stops on unsupported mesh metadata.
Python lint retains fifteen findings in untouched files, and documentation checks retain the three known unrelated failures.
Full Mac/iOS game validation remains open. No changes in this follow-up are committed.

Artifacts remain in the external `bringup-20261115/neural-replay/` work folder: `capture/`, `replays/`, `proof/`, matrix traces,
`conv-cpu-reference.json`, `yuv-cpu-reference.json`, `snapshot-fixed/` (CPU/device regressions), `shaders-fixed/`, `runtime/`,
`prewarm-fixed/`, `fixed-game/`, `fixed-frame350.png`, `timing-report/`, and exact command/exit records. The capture/replay and CPU-reference
instructions are in [probes/README.md](../../../../probes/README.md#bounded-android-vulkan-proofs).

## Follow-up (2026-11-16): Adreno isolation and zero-copy write logs

### Controlled isolation with complete nonzero tensors

A fresh frame-350 capture uses the corrected neural network from `dd39582388d1`. The five hot dispatches retain complete
before/after backing pools, their descriptor aliases and original guest pointers. All comparisons run on **Adreno 840**,
reset every input, require observable nonzero storage writes, guard raw accesses and compare every output byte. Only
write-log contents are excluded from equality because their hash insertion order is not deterministic.

The diagnostic variants retain the matrix instructions. One removes only log CAS probes, another specializes lookup to
the real captured pool entry, and a fourth combines both. Sixteen GPU samples follow three warmups, with variant order
reversed between captures; subsequent confirmation uses warm pipeline caches, **16 warmups and 24 samples**.
Representative first-capture medians are:

| Shader | Original | No log | Captured-entry lookup | Both |
|---|---:|---:|---:|---:|
| `ba079f68ae288dba` | 41.80 ms | 27.02 ms | 33.51 ms | 19.58 ms |
| `a8b4fb48fee0ccf8` | 39.84 ms | 26.28 ms | 30.99 ms | 17.05 ms |
| `e6be82d835fbe4d3` | 41.29 ms | 35.93 ms | 36.39 ms | 29.22 ms |

All **20** comparisons across the five dispatches pass complete-pool equality and reset stability checks. These are
guarded replay timings, not uninstrumented frame measurements. Removing both mechanisms still leaves matrix work,
operand gathers, tensor traffic and the guard, so the remainder is not a pure arithmetic measurement. Compiler effects
also mean the two savings are not strictly additive. The captured-entry specialization remains diagnostic only.

### Selected production optimization

The [general mechanism](../../../docs/reference/shaders.md#raw-write-logs-track-pages-the-zero-copy-backend-does-not-consume)
now suppresses logging only for actual coherent zero-copy destinations. Copied pools retain page publication and the
same conservative overflow behavior; the host still waits after raw writers. No matrix rounding, tensor layout,
dispatch or game-code behavior is changed.

Helper shape matters on this driver. A plain branch around eight unrolled probes slows one tracked `e6be` case to
58.9 ms. A bounded loop removes that penalty; returning directly for ordinary zero-copy stores further improves the
store-only network kernels. The first full-game optimization measures **25.62 ms** for `7f7ff0f36b54d90f`, versus
**10.93 ms** before. Keeping a single store block gives an exact-input guarded replay of **5.56 ms**;
`d15370a382630d4e` measures **2.82 ms** in its replay. The final structural choice uses the presence of raw-read helpers,
not game or shader keys. It emits
**byte-identical SPIR-V** to the separately validated fast forms for all five investigated keys.

With logging suppressed, the selected guarded replay medians are **27.70 ms** for `ba079`, **26.44 ms** for each `a8b4`
dispatch and **29.56 ms** for each `e6be` dispatch. Tracking remains correct and the large `e6be` tracking slowdown is gone.
The final selection does **not** reproduce the mixed-memory replay gains in the full game: `7f7f` still costs
**25.58 ms** and `d153` **8.57 ms**. The upsampling regression remains open. Byte comparison confirms the selected
bundle contains the intended modules, and fresh native compilation rules out an obsolete pipeline-cache hit.
Including the completion barrier in the guarded `7f7f` replay still measures **5.56 ms**, as does allowing the guard
wrappers to inline. Neither experiment explains the discrepancy. Guard instrumentation and the standalone allocation
path still differ from the runtime; their effects have not been isolated. Do not count these replay-only gains as
achieved frame-rate improvements.

### Full tablet result and remaining costs

With all fourteen compute dispatches active and the ordinary game allocator, the final frame-600 interval improves
p50 frame time from **315.51 ms to 261.05 ms**, or about **3.17 to 3.83 fps** (**17.3% less frame time, 20.9% more fps**).
Frame-time p95 is **264.40 ms**; GPU p50/p95 is **258.11/261.02 ms**. The earlier full optimization measures
260.58 ms, so the structural refinement adds no demonstrated full-game improvement. Frame 350 remains visually clean.
The bounded run exits via its configured 180-second TERM timeout, with no red error lines and no skipped neural passes.

The last full-game report totals **248.20 ms** in timed steps. The two `e6be` dispatches cost **34.27/34.20 ms**,
reconstruction **28.79 ms**, `ba079` **27.32 ms**, the two `a8b4` dispatches **26.03/26.06 ms**, and upsampling
`7f7f` **25.58 ms**. Logging removal is a demonstrated gain; address lookup is the next independently measured
overhead. Before further compiler shaping, reproduce the mixed-memory timing gap with the runtime's allocation path
and guarded versus native modules under comparable conditions. The residual convolution time cannot yet be attributed
solely to matrix arithmetic.

### Rebuild and coverage

Final chain **`7453f031ea67`** builds **2,417 of 2,428** shader entries. Exactly **eight** raw-writing compute modules change
from the clean baseline; the final selection changes only the two shaders that use raw reads and writes compared with the
first full-game optimization. Reflection, shader keys, stages and bundle flags are unchanged. Independent validation of
every final module retains the same seven existing vector-extract failures. The eight opcode-243 and three reflection
overflow build failures are unchanged. The host rebuild checks **267 sources with zero failures**.

The real-backend proof passes **48 checks**: twelve each in zero-copy, forced-copy, lazy forced-copy and mixed-pool modes.
These include unbound atomic destinations, CPU visibility before NVN completion, repeated writes, complete canaries,
overflow, null addresses, pool removal/address reuse and returned pool flags. The new flag's ABI mirror, guarded-capture
rejection, CPU convolution, Ampere memory, scoreboards and control-flow tests pass. The broader ABI suite retains two
unrelated pre-existing failures (task/mesh table expectations and its literal ratchet); documentation/lint retain their
previous unrelated findings. Five-title regression remains unavailable for absent packaged Mac builds, and a full Mac
shader rebuild still stops on unsupported mesh metadata. No Mac GPU performance work is part of this follow-up.

All artifacts are external under `bringup-20261116/isolation/`: `report.json`, exact captures, `variants/`, `bench/`,
`proof/`, `mixed-memory/`, `timing-boundary/`, `adaptive/comparison.json`, full bundle comparisons, native-cache
preparation, `optimized-selected/frame350.png` and exact run commands.
The isolated native compiler still uses the documented allocator workaround; ordinary game runs use the normal allocator.
Changes remain uncommitted.

## Follow-up (2026-11-16): last-pool cache and the 30 FPS budget

### Allocation isolated; guarded timing remains a different workload

The replay now optionally uses the same BLOB hardware-buffer usage, dma-buf mapping and dedicated Vulkan import as
the runtime. Imported pools use device-local memory type 1 (flags `0x1`); ordinary replay pools use host-visible,
coherent Vulkan allocations. Core buffer robustness and dynamic uniform descriptors can be selected independently,
including a static support buffer and dynamic driver buffer matching this capture. Every mode retains physical
address guards, reset inputs and complete-pool output comparisons.

The exact production `7f7ff0f36b54d90f` module, including HMMA vector-gather lowering, still takes about **5.56 ms** in
guarded replay versus **25.58 ms** in the preceding full game. Imported allocation, robustness, dynamic descriptor
layout, including the completion barrier, and selectively inlining only the guard wrappers do not explain the gap.
The guarded module extracted anew from the production bundle is byte-identical to the previous guarded replay;
the build-stage-mismatch hypothesis is rejected. Replaying the original module against a fresh frame-350 capture
from the cache experiment also reproduces every output byte and the same fast guarded timing, ruling out those
captured inputs as the explanation. The remaining instrumentation/compiler-context effect is **open**.

### A generic lookup cache improves the ordinary game

The [general mechanism](../../../docs/reference/shaders.md#repeated-raw-pointer-accesses-search-every-pool-again)
uses an invocation-private last index and checks both pool bounds before reusing it. Misses retain the full search;
the final range check, relocation, page-log policy and neural arithmetic remain. Production eligibility follows
recognized mixed raw-read/write structure, with no game or shader-key branch.

A one-module diagnostic first reduces upsampling to **10.89 ms** and frame-600 p50 to **246.09 ms**. The final complete
build enables the same generic cache in both eligible modules:

| Ordinary full-game measurement | Before this follow-up | Final cache build |
|---|---:|---:|
| `7f7ff0f36b54d90f` upsampling | 25.58 ms | 10.89 ms |
| `d15370a382630d4e` | 8.57 ms | 4.50 ms |
| Total timed steps | 248.20 ms | 228.77 ms |
| Frame-600 p50 | 261.05 ms | 241.64 ms |
| Frame-600 p95 | 264.40 ms | 245.51 ms |
| GPU p50 / p95 | 258.11 / 261.02 ms | 238.60 / 242.68 ms |
| Approximate frame rate | 3.83 fps | 4.14 fps |

This recovers the upsampling regression documented above. It is **7.4% less frame time and 8.0% more fps** than the
previous build. Relative to the clean 315.51 ms baseline before page-log optimization, frame time is **23.4% lower**
and frame rate **30.6% higher**. All fourteen compute dispatches remain active, with the normal game allocator.
The bounded 180-second run exits through its configured TERM timeout, with no red error lines. Frame 350 is saved
for visual inspection.

The cache's guarded `7f7f` replay improves from about **5.56 to 3.13 ms**, but guarded `d153` instead changes from
about **2.82 to 6.71 ms**, despite improving in the ordinary game. These timings demonstrate why a guarded replay's
performance direction must not select production changes without a full-game measurement. They are useful output
proofs, not interchangeable hardware-throughput measurements.

### What would 30 FPS require?

At the current workload, 30 fps requires **33.33 ms per frame**, about **7.25 times** faster than the final run.
One of the two dominant `e6be` dispatches alone still takes **34.17 ms**, already more than that entire budget.
The pair costs about 68.4 ms, reconstruction another 28.8 ms, and the other convolution passes remain substantial.
Logging and pool lookup improvements cannot by themselves establish a route to 30 fps.

There is a reason to test a larger change: the tablet exposes native F16 cooperative matrix operations, while the
current translation lowers HMMA into scalar operations and operand gathers. Its reported `64x16x16`, `64x32x16`
and `64x64x16` tiles do not directly match guest `16x8x16` fragments. A native implementation needs new packing,
reuse across logical warps, and checks of lane layout and K16 rounding on actual nonzero tensors. The next decisive
experiment is one captured convolution layer with native tiling, including packing overhead and an independent
numerical reference. **30 fps remains plausible enough to investigate, but is not demonstrated or promised.**

### Rebuild, tests and artifacts

Chain **`cf82d6110b10`** builds **2,417 of 2,428** entries. Only the two mixed-memory modules change from the prior
complete bundle; every other module, all reflection records, keys, stages and flags are byte-identical. Independent
validation of every final module retains the same seven pre-existing vector-extract failures. The eight opcode-243
and three reflection-overflow build failures remain unchanged. The Android host compiles **267 sources with zero
failures**. The existing isolated allocator workaround prepares the native compiler cache; the full game uses its
normal allocator.

All four independent baseline/cached, ordinary/imported-memory GPU comparisons pass, including whole-pool canaries
and reset repetitions. Real captured outputs remain byte-identical. **39** focused Python tests and **13** chain tests
pass, and focused lint, tool-lock and diff checks pass. Five-title regression is attempted for OOT, Mario Kart World,
Bananza, Raiders and Fortune's Weave but their packaged Mac builds are unavailable. The required full Mac shader
rebuild again stops on unsupported mesh metadata. Existing broader ABI, documentation and lint findings remain
outside this change; this follow-up establishes no additional game or Mac/iOS validation.

Artifacts are external under `bringup-20261116/runtime-memory/`: `report.json`, exact production-module extraction,
the one-module native experiment and its capture, `validation/`, `timing-controls/`, independent lookup fixtures,
full bundle comparisons, compiler-cache preparation, and final `cache-final/` logs and screenshot. Exact commands
and exit codes are retained. Changes remain uncommitted.

## Follow-up (2026-11-16): native cooperative convolution experiment

### A measured gain remains diagnostic because numerical equivalence is open

A native F16 `64x16x16` cooperative-matrix kernel now runs a complete captured `270x480x32 -> 32` convolution.
It includes 3x3 halo loading, tensor packing, all eighteen K16 accumulations, bias/ReLU and output packing.
The tablet again reports only F16 accumulators for its F16-input native tiles; it offers no F32 accumulator variant.
This is an explicit experimental kernel using this captured driver ABI and dimensions, not a production translator rule.

The ordinary game compares two bundles on the **same newly compiled host**, with the normal allocator and no dispatch skips.
Exactly one of the 2,417 shader modules changes (`e6be82d835fbe4d3`, used twice per movie frame).
Its local size becomes `64x1x1`; its other reflection records and flags remain unchanged.
Every other module and reflection record is byte-identical. Both bounded runs exit through their configured 180-second TERM timeout.

| Frame-600 interval / timed step | Original shader | Native diagnostic |
|---|---:|---:|
| Frame p50 / p95 | 241.54 / 246.42 ms | 229.23 / 232.94 ms |
| GPU p50 / p95 | 238.61 / 242.95 ms | 226.16 / 229.58 ms |
| Approximate frame rate | 4.14 fps | 4.36 fps |
| First / second `e6be` dispatch | 34.26 / 34.24 ms | 27.86 / 27.75 ms |
| Total timed steps | 229.35 ms | 216.75 ms |

This is **5.1% less frame time**. All fourteen compute dispatches remain active, and neither run logs a red error.
The diagnostic frame-350 screenshot shows the moonlit field without visible corruption. It does not establish
numerical equivalence or player-controlled gameplay. The ordinary shader bundle remains the baseline.

### Integer and memory checks pass; fractional agreement needs more work

The independent synthetic integer convolution matches every output exactly. It exercises zero padding, negative inputs,
bias/ReLU and a partial final tile. Both real captures and the fractional fixture preserve all input bytes and both
64-byte output canaries. Repeated GPU submissions reset inputs and reproduce their initial outputs.
An additional original-descriptor replay guards every raw physical load/store and compares the complete backing pool:
**zero bytes change outside the output tensor**, and its output matches the direct-buffer native kernel bit for bit.

Native arithmetic does not reproduce the current scalar K16 reference for fractional values:

| Input | Maximum difference from captured/reference output | Full-output values differing by more than 0.01 |
|---|---:|---:|
| First real `e6be` capture | 0.0107421875 | 1 |
| Second real `e6be` capture | 0.015625 | 82 |
| Synthetic fractional halves | 0.017578125 | 12 |

Against 4,101 deterministic sampled pixels, the second native layer differs from the independent CPU model by at most
0.013671875, versus 0.005859375 for the current shader. Six sampled values exceed 0.01 with native arithmetic;
none do with the current shader. Native F16 accumulation order/precision needs investigation before promotion.
The [GLSL cooperative-matrix contract](https://docs.vulkan.org/glslext/latest/glslext/khr/GLSL_KHR_cooperative_matrix.html)
allows implementation-dependent operation order. Matching the present CPU or scalar model would itself remain
separate from proving the original Ampere hardware's rounding behavior.

### Standalone speed does not explain full-game speed

After sixteen warmups and twenty-four samples, direct-buffer native replays take **4.09 ms** and **4.16 ms** for the two captures.
Pipeline compilation, transfers and readback are excluded; packing executes inside the timestamps.
A controlled comparison with the current looping kernel uses identical inputs and produces identical output at both grids:
`2025x2x1` takes **4.16 ms**, while the game's `120x1x1` grid takes **6.37 ms**.
Launch geometry explains part of the gap, but does not explain the full game's roughly 27.8 ms native dispatches.
The guarded raw replay takes about 82.7 ms and is an output proof, not a throughput estimate.
Raw access/compiler context and native accumulation remain the next separate questions. No route to 30 fps is established.

### Checks and artifacts

The Android host compiles **267 sources with zero failures**. Fourteen focused Python tests pass, including independent
CPU convolution, native Vulkan-memory-model guard validation, alias rejection and diagnostic bundle preservation.
Focused lint and diff checks pass. The requested five-title regression covers OOT, Mario Kart World, Bananza, Raiders
and Fortune's Weave because the host's feature setup is shared; it exits 2 because these packaged Mac builds are absent.
Documentation checks retain the same three existing failures: a missing game note/row, the debugging guide's word limit,
and unrelated broken links. None names a new link from this experiment.
No Mac/iOS or broader gameplay validation is claimed.

Reproduction tools and numerical checks are in [probes/README.md](../../../../probes/README.md#native-cooperative-convolution-experiment).
Artifacts are external under `bringup-20261116/cooperative-matrix/`: `report.json`, `commands.json`, `grid-commands.json`,
the original and native diagnostic bundle hashes, source snapshots, exact captured tensors, synthetic proofs, replay outputs,
full-game/baseline logs, `frame350.png`, the isolated host and exact run commands. Chain `cf82d6110b10` is unchanged.
Changes remain uncommitted.

## Follow-up (2026-11-16): native arithmetic and inactive write logs

### Both numerical effects are measured; the native kernel remains diagnostic

The [native arithmetic finding](../../../docs/reference/shaders.md#native-f16-cooperative-matrices-round-products-and-additions-separately)
now explains this experiment's fractional behavior. Separate scalar, native and half-packing GPU probes identify
per-product/per-add half rounding and toward-zero final packing. The resulting CPU model matches all sampled native
values exactly in both original `e6be` captures, the fractional fixture and a fresh game capture.
It does not match the current float32-FMA/K16 model or establish original Ampere behavior.
The production translator therefore keeps its existing lowering.

### The inactive atomic log loop explains the raw-kernel timing gap

All comparisons use the same first real capture, `120x1x1` workgroups, sixteen warmups and twenty-four GPU samples.
Owned-buffer fixtures assign only the replay's own allocation addresses and preserve whole-tensor bounds checks.
Every variant produces identical output; every byte outside the output tensor stays unchanged, and the log stays empty.
The [general finding](../../../docs/reference/shaders.md#inactive-multi-probe-atomic-logging-slows-a-cooperative-kernel)
records the compiler-context limitation and why copied-pool logging must remain intact.

| Controlled variant | Median GPU time |
|---|---:|
| Direct descriptors | 6.36 ms |
| Owned physical addresses | 6.39 ms |
| Original raw map and log helper | 27.65 ms |
| Raw read-only qualifiers | 27.65 ms |
| Fixed lookup entry, full bounds checks | 27.36 ms |
| Early-return / no-inline helper shapes | 27.66–27.69 ms |
| Original lookup, logging omitted | 6.40 ms |
| Inactive non-atomic log probes | 6.46 ms |
| One inactive atomic | 6.40 ms |

Physical addressing and lookup are not the missing 21 ms. The inactive multi-probe atomic loop triggers the penalty;
the driver's precise code-generation mechanism remains open. The non-atomic and single-atomic controls are diagnostics,
not substitutes for correct copied-pool publication.

### A separate full-game diagnostic reaches 5.36 fps

The no-log kernel changes only the same `e6be` module in a copy of the complete bundle. It uses the existing isolated
cooperative-capable host with the normal allocator, a copied save and private caches. The frame-350 capture independently
confirms that its destination is coherent: all **2,140 valid map entries** have the no-write-log flag set.
Its sampled output matches the measured native CPU model exactly. Neither comparison changes arithmetic relative to
the preceding native experiment; both remain numerically different from the production shader.

| Ordinary full-game measurement | Previous native diagnostic | No-log native diagnostic |
|---|---:|---:|
| Frame-600 p50 / p95 | 229.23 / 232.94 ms | 186.47 / 191.08 ms |
| GPU p50 / p95 | 226.16 / 229.58 ms | 183.49 / 187.47 ms |
| Approximate frame rate | 4.36 fps | 5.36 fps |
| First / second `e6be` dispatch | 27.86 / 27.75 ms | 6.45 / 6.43 ms |
| Total timed steps | 216.75 ms | 174.24 ms |

The frame-900 interval is 185.73 ms p50 / 190.69 ms p95. All fourteen compute dispatches remain active; there are no red
errors, and the bounded run exits through its configured 180-second TERM timeout. The saved frame shows the moonlit
field without visible corruption. Relative to the same-host original shader run at 241.54 ms, frame time is 22.8% lower;
relative to the preceding native diagnostic it is 18.7% lower. These gains belong to the diagnostic experiment.
A production implementation still needs compatible arithmetic and a safe static specialization for destinations that
do not require logging; omitting logs for copied pools is not valid. No 30 fps result is established.

### Checks and artifacts

Eleven focused Python tests pass, including exact rounding counterexamples and existing CPU convolution, guard and
memory-snapshot checks. The updated replay builds with NDK clang and `-Wall -Wextra -Werror`; all generated modules
independently validate. Focused lint and diff checks pass. The required five-title regression again finds no packaged
Mac builds for OOT, Mario Kart World, Bananza, Raiders or Fortune's Weave. Existing unrelated documentation failures remain.

Artifacts are external under `bringup-20261116/cooperative-followup/`: `report.json`, `commands.json`, arithmetic
models, owned-buffer comparisons, exact source and runner snapshots, the diagnostic bundle, `game-fast/` capture/logs,
and `frame350.png`. [Probe instructions](../../../../probes/README.md#native-cooperative-convolution-experiment)
cover the new arithmetic and owned-allocation modes. Chain `cf82d6110b10` is unchanged. Changes remain uncommitted.

## Follow-up (2026-11-17): cooperative-only log specialization

### Runtime selection now preserves copied-pool tracking

The runtime implementation of the [inactive logging finding](../../../docs/reference/shaders.md#inactive-multi-probe-atomic-logging-slows-a-cooperative-kernel)
keeps a separate log-free module and pipeline for cooperative compute programs. It selects that module only when the
complete current map contains coherent allocations. Copied pools retain the original module, including overflow handling;
the completion wait remains in both paths. Pool generation changes invalidate the decision. The transform refuses
unknown uses of the reserved log pointer and leaves arithmetic instructions intact.

Broad application to the ordinary gather kernels is **rejected**: a bounded test reaches roughly 2.1–2.3 seconds of GPU
work per frame. This is a new compiler-context regression, not a correct performance result. The final eligibility rule
requires an actual cooperative-matrix type, so the production gather modules remain byte-identical.
A fresh original-bundle run returns to **240.12 ms p50 / 245.29 ms p95** at frame 300, with no red errors.
This selection rule is structural; it contains no game or shader-key condition.

The new native backend fixture tests coherent, copied, lazy-copied and mixed pools, then removes/replaces the destination
at the same guest address and switches between copied and coherent backing. Eighty native checks and twenty ordinary
scalar checks pass with Khronos validation active and zero API errors. The scalar fixture confirms that its original
module stays selected. A/B matrix scalar constructors fail native compilation on this driver; the fixture uses the
same shared-memory matrix-load interface as the convolution.

### Two more native dispatches raise the diagnostic to 6.93 fps

The `a8b4fb48fee0ccf8` kernel is a `540x960x16 -> 16` stride-1 convolution. A complete captured-pool replay of the
native implementation takes **5.19 ms** at its ordinary `720x1x1` launch grid. Every byte outside the output tensor stays
unchanged. Its sampled output matches the measured native half-product/half-add/toward-zero model exactly; its maximum
difference from the existing shader is 0.0074462890625, with mean absolute difference 0.00019353.

The final private bundle replaces only `a8b4` and `e6be` relative to the complete production baseline. All other modules,
reflection records and flags remain unchanged; the two selected modules use `64x1x1` local size. Unlike the previous
no-log experiment, both modules retain the full tracked path in their bundle. The host selects the coherent variant
at replay time. No shader operation or neural dispatch is skipped.

| Full-game measurement | Previous one-module native diagnostic | Two-module native diagnostic |
|---|---:|---:|
| Frame-600 p50 / p95 | 186.47 / 191.08 ms | 144.20 / 148.42 ms |
| GPU p50 / p95 | 183.49 / 187.47 ms | 141.21 / 144.81 ms |
| Approximate frame rate | 5.36 fps | 6.93 fps |
| First / second `a8b4` dispatch | 26.03 / 25.97 ms | 5.23 / 5.24 ms |
| First / second `e6be` dispatch | 6.45 / 6.43 ms | 6.41 / 6.42 ms |
| Total timed steps | 174.24 ms | 131.82 ms |

Frame-900 p50/p95 is 143.82/147.87 ms, and frame 1200 is 142.16/147.52 ms. The run uses the normal allocator and
exits through its configured 180-second TERM timeout, with all fourteen compute dispatches active and no red errors.
The frame-350 moonlit field has no visible corruption. The comparable frame-600 interval is **22.7% shorter** than
the preceding native diagnostic, or **29.3% more fps**.

The fresh `a8b4` capture contains 2,140 valid map entries, all coherent. Its 65,616 sampled output values match the native
CPU model exactly. Captures now also save the **actual selected SPIR-V module**, so replay need not infer a coherent
variant from the source bundle. That captured module independently validates and contains no logging atomics.

### A float32 alternative still needs arithmetic investigation

The tiled `FLOAT32_K16` candidate measures 15.55 ms on the original `e6be` capture and matches its explicit FMA/K16 CPU
model exactly. It differs from the current shader in 1,462,794 output bytes, with maximum absolute error 0.001953125.
That is insufficient for promotion. The candidate, both native convolutions and their rounding models remain diagnostic;
the production translator still selects the original lowering. Original Ampere rounding is not established.
The next largest measured costs are reconstruction at 28.77 ms and the first convolution at 27.03 ms.

### Checks and artifacts

The final Android host compiles **267 sources with zero failures**. Seventeen focused Python tests pass, including
sanitizer checks of the exact runtime transform and refusal of unsupported log reads/atomics. Every raw-writing compute
module in the baseline was independently transformed and validated during the audit; the final runtime applies that
transform only to cooperative modules. Focused lint and diff checks pass. The five-title regression again lacks packaged
Mac builds for OOT, Mario Kart World, Bananza, Raiders and Fortune's Weave. Existing unrelated documentation failures remain.

Artifacts are external under `bringup-20261117/coherent-specialization/`: `report.json`, `commands.json`, `audit/`,
the rejected broad-run logs, final original-bundle control, active-layer backend proofs, `a8/`, `precision/`, `native-two.dmsv`,
`game-two-native/` with its actual module capture, `frame350.png`, and isolated runtime/source snapshots.
Chain `cf82d6110b10` is unchanged. This checkpoint includes the runtime, translator, diagnostics and evidence above;
native arithmetic remains diagnostic and is not selected by the production translator.

## Follow-up (2026-11-17): first convolution reaches 8.27 fps

The preceding runtime/translator checkpoint is committed as `1d0a24ac`. The next
diagnostic replaces `ba079f68ae288dba`, the first convolution, alongside the two
previous native modules. Its input is a `1920x1080` RGBA8 UNORM texture: four
row-major pixels form sixteen channels at each `960x540` output position. The
kernel applies a zero-padded 3x3 convolution, sixteen output channels, bias and
ReLU. Every fourth weight input is zero (alpha padding). The independent CPU
checker establishes the unshuffle order rather than inferring it from a rendered
picture.

An owned full-pool replay takes **6.46 ms median / 6.66 ms p95**, with every byte
outside the destination unchanged. All **65,616 sampled values** match the native
half-product/half-add/toward-zero model exactly. Relative to the existing shader,
maximum absolute difference is 0.004150390625 and mean difference is 0.00007702.
The tracked kernel retains bounds checks and copied-pool logging; the runtime
selects the coherent specialization under the same complete-map rule.

| Full-game measurement | Two-module native diagnostic | Three-module native diagnostic |
|---|---:|---:|
| Frame-600 p50 / p95 | 144.20 / 148.42 ms | 120.89 / 124.73 ms |
| GPU p50 / p95 | 141.21 / 144.81 ms | 118.51 / 121.84 ms |
| Approximate frame rate | 6.93 fps | 8.27 fps |
| First convolution | 27.03 ms | 6.58 ms |
| Total timed steps | 131.82 ms | 111.75 ms |

The comparable interval is **16.2% shorter**, or **19.3% more fps**. Frame-900
p50/p95 is 120.41/124.31 ms; frame 1200 is 119.88/123.06 ms. The normal-allocator
run reaches frame 1500 and exits gracefully through the configured 180-second TERM
timeout. All fourteen compute dispatches remain active, none are skipped, and no
red errors are logged. The fresh first-convolution capture again matches the
native model exactly at 65,616 sampled values. The saved moonlit-field frame has
no visible corruption. These results remain diagnostic: neither CPU-model agreement
nor visual inspection establishes original Ampere numerical equivalence.

### Generic native reconstruction packing is rejected

The remaining largest pass is `4f41ccf24f163e0d`, at about 28.79 ms. A separate
experiment retains its original sampling, weights, image writes, all 46 HMMA calls
and `128x1x1` workgroup. It packs each pair of logical warp products into diagonal
blocks of a native `64x16` output. Seven integer fixtures match 768 reference
words exactly, including dependent and aliased calls; a further two-subgroup
fixture matches 256 distinct words with intact canaries.

On the same non-black captured inputs, current reconstruction takes **28.77 ms**
and generic native packing takes **88.51 ms**. Both source pools stay unchanged.
The current shader reproduces the captured image byte for byte; native packing
changes 121,645 of 14,745,600 output bytes by at most one byte value. It is slower
and numerically different, so it is excluded from the three-module game bundle.
Further reconstruction work needs a different tile/data-reuse strategy; replacing
each existing helper call independently does not provide a performance gain.

### Checks and artifacts

Twenty-three focused tests pass, including the new unshuffle reference and native
helper interface/convergence checks. Generated SPIR-V validates independently;
focused lint and diff checks pass. The required five-title check again reports no
packaged Mac builds for OOT, Mario Kart World, Bananza, Raiders or Fortune's Weave.
Existing unrelated documentation failures remain.

Artifacts are external under `bringup-20261117/remaining-kernels/`: `report.json`,
`commands.json`, `first/`, `fresh-first-model.json`, `native-three.dmsv`,
`game-three/`, `frame350.png`, `reconstruction-proof/`, `reconstruction-native/`,
`regression/` and source snapshots. Chain `cf82d6110b10` is unchanged. The follow-up
probe and documentation edits remain uncommitted after the requested checkpoint.

## Follow-up (2026-11-17): wider convolution tiles reach 8.62 fps

The `e6be82d835fbe4d3` native diagnostic now packs all 32 output channels into a
`64x32x16` cooperative tile. The prior `64x16x16` layout packed the same input
twice for two output-channel tiles. The wider layout reuses that input packing;
its K16 product/add order, bias, ReLU, bounds checks and tracked write path remain
the same. It changes no production translation rule.

On the original complete-pool capture, an N16/N32/N32/N16 comparison gives
**6.39 / 3.73 / 3.73 / 6.39 ms** median over sixteen samples each, after eight
warmups. All four resulting pools are byte-identical, and every byte outside the
output tensor stays unchanged. Integer and fractional synthetic convolutions
also produce byte-identical N16/N32 outputs, retain their canaries and inputs,
and match the independent native half-product/half-add model. These include
padding and a partial final 64-pixel tile.

| Full-game measurement | Previous three-module native diagnostic | Wider convolution tile |
|---|---:|---:|
| Frame-600 p50 / p95 | 120.89 / 124.73 ms | 116.05 / 120.07 ms |
| GPU p50 / p95 | 118.51 / 121.84 ms | 113.22 / 116.40 ms |
| Approximate frame rate | 8.27 fps | 8.62 fps |
| First / second `e6be` dispatch | 6.44 / 6.43 ms | 3.77 / 3.76 ms |
| Total timed steps | 111.75 ms | 106.60 ms |

The comparable interval is **4.0% shorter**, or **4.2% more fps**. Frame-900
p50/p95 is 113.91/118.81 ms; frame 1200 is 113.79/118.57 ms. The normal-allocator
run reaches frame 1500 and ends through its configured 180-second TERM timeout.
All fourteen compute dispatches remain active, none are skipped, and no red
errors are logged. Existing late-route texture-alias notices also occur in the
preceding run. The moonlit frame-350 picture shows no visible corruption.

The fresh in-game convolution capture matches the native CPU model exactly at
**131,232 sampled values**; all captured pool bytes outside its output stay
unchanged. Its actual selected module validates and contains no logging atomics.
Relative to `native-three.dmsv`, only `e6be` code changes: all 2,416 other modules,
reflection records and flags are unchanged. Native arithmetic remains diagnostic,
with original Ampere numerical equivalence still open.

### Reconstruction tile sharing is established, but both candidates lose

An instrumented scalar reconstruction checks every operand at all 46 matrix
calls over 14,400 workgroups: each call records 1,843,200 invocations. The first
44 calls form 22 pairs with identical A fragments within each pair. Across the
four logical warps, each pair shares either A or both B tiles, allowing a full
native tile through transposition or row packing. Verification builds check the
selected sharing condition again during the actual paired execution, with zero
faults. The final two matrix calls retain the original arithmetic.

Both full-workgroup and padded-subgroup mappings pass independent integer and
fractional CPU matrix models, including dependent accumulation and intact
canaries. A deliberately invalid sharing fixture sets the fault flag in both
mappings. Alternating baseline/candidate/candidate/baseline measurements still
reject them: **52.27 ms** for full-workgroup packing and **99.07 ms** for separate
subgroups, against **28.77 ms** for the current gather shader. Both candidates
change 120,884 of 14,745,600 image bytes, by at most one byte value. Neither enters
the game bundle. Shortening the synchronization scope alone does not recover
performance in these layouts.

An exact-arithmetic cache experiment also provides no gain: retention limits
2, 3, 4 and 8 emit identical modules and replay at about 28.77 ms, with outputs
byte-identical to the captured image. Raising the current two-tile limit has no
effect on this call sequence. Reconstruction remains the largest pass; the two
`0a56002cdc7e1fce` passes together cost about 21.2 ms and are the next substantial
unmodified workload.

### Checks and artifacts

Twenty-seven focused tests pass. New checks cover paired-call dependencies,
intervening side effects, output aliasing, verification-binding collisions,
both executable tile layouts and wider convolution grid/tensor preservation.
Generated modules independently validate; focused lint and diff checks pass.
The five-title Mac regression still lacks packaged builds for OOT, Mario Kart
World, Bananza, Raiders and Fortune's Weave. The same unrelated documentation
failures remain.

Artifacts are external under `bringup-20261117/reconstruction-tiles/`:
`report.json`, `commands.json`, `sharing/`, both matrix proof folders,
`paired/`, `subgroup/`, `exact-cache/`, `wide-convolution/`,
`native-three-wide.dmsv`, `game-wide/`, `frame350.png`, `regression/` and source
snapshots. Chain `cf82d6110b10` is unchanged; probe and documentation edits remain
part of this checkpoint. Native arithmetic remains diagnostic.

## Follow-up (2026-11-17): both 64-channel passes reach 9.81 fps

Checkpoint `38d059fc` commits the preceding probe, test and documentation work.
The next diagnostic replaces both uses of `0a56002cdc7e1fce`, a zero-padded 3x3
`135x240x64 -> 64` convolution followed by bias/ReLU. A fresh full-frame capture
uses the preceding three-module native bundle, including the wider `e6be` tile,
so both test inputs contain the current upstream feature data.

### N32 wins over the larger native tile

Six GPU fixtures cover integer and fractional 64-output-channel convolutions
with N16, N32 and N64 tiles. Each three-way comparison produces byte-identical
complete output buffers, preserves both canaries and all inputs, and matches
the independent native-half model. Partial final pixel tiles are included.

Both real dispatches then replay from complete owned pools, with eight warmups
and sixteen timestamp samples per measurement:

| Captured dispatch | First N16 | N32 | N64 | Final N16 |
|---|---:|---:|---:|---:|
| Sequence 6 | 6.142 ms | 3.738 ms | 4.002 ms | 6.137 ms |
| Sequence 7 | 6.136 ms | 3.731 ms | 4.007 ms | 6.140 ms |

All tile widths produce byte-identical full pools within each dispatch; every
byte outside its destination stays unchanged. Each selected output matches the
native CPU model exactly at 262,464 sampled values. N32 is selected for the game
experiment; the 64-wide tile is correct under this model but slower.

### Full-game gain and numerical limits

| Full-game measurement | Previous three-module native diagnostic | Four-module native diagnostic |
|---|---:|---:|
| Frame-600 p50 / p95 | 116.05 / 120.07 ms | 101.91 / 104.41 ms |
| GPU p50 / p95 | 113.22 / 116.40 ms | 99.14 / 101.60 ms |
| Approximate frame rate | 8.62 fps | 9.81 fps |
| First / second `0a56` dispatch | 10.64 / 10.56 ms | 3.81 / 3.80 ms |
| Total timed steps | 106.60 ms | 93.50 ms |

The comparable interval is **12.2% shorter**, or **13.9% more fps**. Frame-900
p50/p95 is 101.16/103.99 ms, and frame 1200 is 99.67/103.90 ms. The run reaches
frame 1800, uses the normal allocator and ends through the configured 180-second
TERM timeout. All fourteen compute dispatches stay active, none are skipped,
and no red errors are logged. Full-frame capture causes a 1.4-second outlier in
the frame-600 interval; later intervals contain no capture work.

Fresh in-game captures check both chained native dispatches, including the second
pass's changed input from the first native pass. Together, **524,928 sampled
values** match the native model exactly. Bytes outside each output remain
unchanged, and both selected modules validate without logging atomics.
Only this shader key changes relative to the preceding bundle; all other 2,416
modules and flags are retained. Its reflection only changes local size from
`32x4x1` to `64x1x1`.

The numerical difference from the current float32-FMA/K16 shader is larger at
this depth. On identical captured inputs, the first pass differs by at most
0.021484375 (mean 0.00053087), and the second by 0.078125 (mean 0.00096031).
The first pass has 558 of 2,073,600 values differing by more than 0.01; the second
has 22,925. Original Ampere numerical equivalence remains open. The saved
moonlit frame has no visible corruption, but the two full-game captures have
different first-pass source tensors, so their final pixels cannot establish
controlled numerical equivalence. Native arithmetic remains diagnostic and is
not selected by the production translator.

### Checks, artifacts and next costs

Twenty-eight focused tests pass, including the expanded 64-channel fixture and
rejection of partial N16 channel counts. Generated SPIR-V independently validates;
focused lint and diff checks pass. The five-title Mac check still has no packaged
builds for OOT, Mario Kart World, Bananza, Raiders or Fortune's Weave. Existing
unrelated documentation failures remain.

Artifacts are external under `bringup-20261117/pointwise/`: `report.json`,
`commands.json`, the fresh original `capture/`, `proof/`, `real/`,
`native-four.dmsv`, `selection.json`, `game-native-four/`, `frame350.png`,
`regression/` and source snapshots. The folder name predates identification of
the 3x3 kernel. Chain `cf82d6110b10` is unchanged; follow-up fixture/test and
documentation edits remain uncommitted after the requested checkpoint.
Reconstruction remains about 28.7 ms, followed by `7f7ff0f36b54d90f` at 10.9 ms
and `5a7d69b067a7f011` at 7.9 ms.

## Follow-up (2026-11-17): residual upsampling reaches 10.80 fps

`7f7ff0f36b54d90f` expands `270x480x32` features into `540x960x16`. Four
row-major subpixel matrices share each source pixel. Its weights are
`4x32x16` half values; the larger captured SSBO range also contains neighboring
data. Driver word 212 supplies a separate skip tensor. The shader initializes
matrix C from that residual, accumulates K16 fragments, then applies shared bias
and ReLU. Moving the residual to a final add changes native rounding; a new
counterexample test distinguishes those orders.

The diagnostic packs source pixels and phase/channel columns into native
cooperative tiles. It retains tensor bounds checks, the original launch grid,
copied-pool logging and residual order. The existing structural coherent-map
specialization removes logging only when all map entries are coherent.

### Small tiles win, with independent residual and phase checks

Six GPU fixtures cover integer and fractional inputs across N16/N32/N64.
Every complete output pool matches its dense CPU oracle byte for byte, including
all untouched inputs and canaries. The cases include partial final pixel tiles,
negative values and bias/ReLU. Separate reference tests check all four subpixel
positions and channels with explicit expected values.

The same fresh feature capture from the four-module native game then measures
**1.850 / 1.928 / 2.269 / 1.849 ms** for N16/N32/N64/N16, after eight warmups and
sixteen timestamp samples per measurement. All resulting full pools are
byte-identical; bytes outside the output tensor stay unchanged. N16 is selected.
Its 65,616 sampled values match the native half-product/half-add model exactly.
Against the current shader on those same inputs, maximum absolute difference
is 0.00213623046875, mean difference is 0.00009505, and no value differs by more
than 0.01. The separate FMA/K16 reference stays within 0.00048828125 of the
current shader. These comparisons establish the experiment's layout and arithmetic
model, while original Ampere numerical equivalence remains open.

### Full-game gain

| Full-game measurement | Four-module native diagnostic | Five-module native diagnostic |
|---|---:|---:|
| Frame-600 p50 / p95 | 101.91 / 104.41 ms | 92.57 / 95.93 ms |
| GPU p50 / p95 | 99.14 / 101.60 ms | 89.90 / 92.94 ms |
| Approximate frame rate | 9.81 fps | 10.80 fps |
| Upsampling dispatch | 11.09 ms | 1.90 ms |
| Total timed steps | 93.50 ms | 83.90 ms |

The comparable interval is **9.2% shorter**, or **10.1% more fps**. Frame-900
p50/p95 is 91.87/95.11 ms, and frame 1200 is 90.50/94.61 ms. The run reaches
frame 1800 and exits gracefully through its configured 180-second TERM timeout.
It uses the normal allocator, retains all fourteen compute dispatches without
skips, and logs no red errors. The saved moonlit frame shows no visible corruption.

The fresh upsampling capture again matches the native CPU model exactly at
65,616 sampled values, preserving every pool byte outside the output. Its actual
selected module independently validates and contains no logging atomics.
Only `7f7f` changes relative to `native-four.dmsv`; all other 2,416 modules and
flags remain. Its reflection only changes local size from `32x1x1` to `64x1x1`.
The host and production translator are unchanged; this remains a native-arithmetic
diagnostic bundle.

### Checks and artifacts

Thirty-two focused tests pass, including residual-rounding and phase-order
counterexamples, complete fixture outputs, invalid driver extents, alignment,
missing captured ranges and unsupported launch grids. Generated modules validate
independently; focused lint and diff checks pass. The five-title Mac regression
still lacks packaged builds for OOT, Mario Kart World, Bananza, Raiders and
Fortune's Weave. Existing unrelated documentation failures remain.

Artifacts are external under `bringup-20261117/upsample/`: `report.json`,
`commands.json`, `mapping.json`, `capture/`, `proof/`, `real/`,
`native-five.dmsv`, `game-native-five/`, `frame350.png`, `regression/` and source
snapshots. Chain `cf82d6110b10` is unchanged. Follow-up code and documentation
are included in this checkpoint. Reconstruction is still about 28.7 ms; the final
`5a7d69b067a7f011` pass is now next at 7.9 ms.

## Follow-up (2026-11-17): output-image convolution reaches 11.37 fps

Checkpoint `840e1e09` commits the preceding 64-channel convolution and residual
upsampling work. The next experiment replaces `5a7d69b067a7f011`: a zero-padded
3x3 `540x960x16 -> 16` convolution whose sixteen channels become four RGBA
subpixels at `1080x1920`. For phase `p`, RG comes from channels `2p,2p+1` and BA
from `8+2p,9+2p`. Each output adds the original RGBA8 image to the convolution,
then half bias, before RGB10A2 UNORM conversion. There is no intermediate ReLU.
Independent border and channel-layout comparisons distinguish this mapping from
clamped padding and contiguous RGBA phase layouts.

### Paired source loads cut packing cost

Four complete GPU fixtures cover integer and fractional inputs under native
half arithmetic and scalar float32 FMA with direct K16 half packing. Every trace
and packed output byte matches its dense oracle; source buffers and trace canaries
stay unchanged. The fixtures include descriptor prefixes, all phases/channels,
negative values, fractional image values and a partial final pixel tile.

On fresh captured inputs from the five-module native game, eight warmups and
sixteen timestamp samples give **7.918 / 5.034 / 9.021 / 7.925 ms** for original,
native, scalar FMA and original. Both original replays reproduce the captured
image byte for byte. Reading each 32-bit source word once and unpacking both half
values then reduces native packing cost: alternating scalar-load/paired-load/
paired-load/scalar-load measurements are **5.028 / 2.804 / 2.804 / 5.037 ms**.
Both synthetic fixtures and the real capture retain byte-identical full traces
and packed outputs across the two load variants. Paired loads are selected.

Against the current shader on identical captured inputs, native arithmetic changes
27,173 of 2,073,600 pixels and 27,369 RGB components, each by at most one RGB10
quantization step. Mean difference across all RGBA components is 0.003300 steps;
alpha is unchanged. The scalar direct-pack alternative changes 40,713 components,
also by at most one step. An external explicit-nearest-even conversion experiment
reduces that count to 7,994 but takes 15.659 ms and still is not byte-identical.
Both real traced arithmetic variants match their respective CPU models exactly
at 65,616 sampled residual values and 16,404 packed color components. These
comparisons establish the diagnostic models; original Ampere equivalence remains
open, including the preceding native feature passes.

### Full-game gain

| Full-game measurement | Five-module native diagnostic | Six-module native diagnostic |
|---|---:|---:|
| Frame-600 p50 / p95 | 92.57 / 95.93 ms | 87.94 / 90.66 ms |
| GPU p50 / p95 | 89.90 / 92.94 ms | 85.13 / 87.76 ms |
| Approximate frame rate | 10.80 fps | 11.37 fps |
| Output-image dispatch | 8.00 ms | 2.87 ms |
| Total timed steps | 83.90 ms | 79.02 ms |

The comparable interval is **5.0% shorter**, or **5.3% more fps**. Frame-900
p50/p95 is 86.69/90.58 ms, frame 1200 is 85.74/89.85 ms, and frame 2100 is
86.77/91.57 ms. The run uses the normal allocator, keeps all fourteen compute
dispatches active, skips none and logs no red errors. It exits gracefully through
the configured 180-second TERM timeout. The saved moonlit frame has no visible
corruption.

The fresh selected-module capture matches the native CPU model at all 16,404
sampled packed color components. Every byte in input buffers 4/5/6 and the complete
captured feature pool remains unchanged. The selected module independently
validates. Only `5a7d` changes relative to `native-five.dmsv`; all other 2,416
modules and flags remain. Reflection changes only local size from `32x1x1` to
`64x1x1`. The host and production translator are unchanged; this remains a
diagnostic bundle.

### Checks, artifacts and next costs

Thirty-six focused tests pass, covering phase mapping, border padding, RGB10A2
packing, dense fractional oracles, trace canaries, paired builds, tensor extents,
alignment, texture scale, image formats and unsupported launch grids. Generated
SPIR-V independently validates; focused lint and diff checks pass. The five-title
Mac regression still lacks packaged builds for OOT, Mario Kart World, Bananza,
Raiders and Fortune's Weave. Existing unrelated documentation failures remain.

Artifacts are external under `bringup-20261117/output-conv/`: `report.json`,
`commands.json`, `mapping.json`, `proof-report.json`, `bench-report.json`,
`paired-report.json`, `rne-report.json`, `capture/`, `proof/`, `real/`, `paired/`,
`rne/`, `native-six.dmsv`, `game-native-six/`, `frame350.png`, `regression/` and
source snapshots. Chain `cf82d6110b10` is unchanged. This follow-up remains
uncommitted after the requested checkpoint. Reconstruction still costs about
29 ms. Applying the verified paired source-word packing to the other native
convolution kernels is the next structural experiment; its benefit there is
unmeasured.
