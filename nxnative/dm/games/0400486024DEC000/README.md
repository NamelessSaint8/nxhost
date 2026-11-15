# The Legend of Zelda: Ocarina of Time (Switch 2) — `0400486024DEC000`

A Switch 2 title, dumped loose as `exefs/` (`main` 29.9 MB, `sdk` 7.8 MB, `subsdk0` 533 KB, `rtld`) and `romfs/` (25 GB) from update **1.1.1**
(`Product.100`/`Product.111` tables, `RegionLangMask.txt` `111`). Nintendo EPD's engine (Nin_Ounce: sead / agl / gsys, Phive), SDK **22.2.8** (the `sdk`
names its spec `Ounce`), NVN2 with Ampere shaders. **The host boots it to `nnMain` and its first NVN2 frame setup**; the next gate is the Switch 2
audio device manager (`auddmg:u`), not shaders — the 2,376 libraries the boot asks for now load (2,324 built, 52 refused task/mesh).

Reference: `NX2navi-0.5.0` beside the dump is a static recompilation of this game (v1.1.1) to Windows x86-64 with a Vulkan renderer. It is read for
**what the game asks of the SDK** — its architecture notes enumerate the services it had to serve (`fs`, `hid`, the audio renderer, `nn::codec`
movies, applet/account, the three-core scheduler) and the NVN2 commands it replays. Its additions are all rights reserved and its code is not copied
here; only the facts about the title are used.

**Target order (2026-11-09): Android first, Metal/Mac second.** The Mac host is the only one executing this title today, so it stays the instrument
for finding walls; the Android side then needs the Vulkan shader bundle built from the same package, an `android.tsv` for this profile, and a memory
answer on the tablet (15.2 GB usable against the 12 GiB layout the title sizes itself from and the 6.22 GB heap it asks for).

## What it needs

| Setting | Where | Why |
|---|---|---|
| `sys_resource 0x3000000` | [`game.tsv`](game.tsv) | the NPDM declares 48 MB, so the SDK's `IsVirtualAddressMemoryEnabled` is true (Donkey Kong Bananza's declares none) |
| the memory keys | `game.tsv` | a starting split borrowed from Splatoon Raiders (same engine and SDK generation), **not measured here**; the first `SetHeapSize` line corrects it |
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
  vsync-bound at 60 fps, so the 20–30 fps target is met on everything this title draws so far.
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
- **The `bad_alloc` is intermittent, and the run that follows is a different death.** A 120 s run with all three expensive pipelines
  compiled (`45.7 / 13.9 / 2.3 s`) produced **no throw at all** through the gate and no `bad_alloc` message: it ends in a bare
  `abort()` (host bionic, `pc=abort+0xa0`) about 40 s in. `abort` is defined by the `sdk` (`0x7780a0`, again an interior of a stub
  cluster) and imported by `main`, so that path needs a hook of its own.
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
- **The `"all"` creator lookup.** The abort is understood as far as its call site (`main+0x21f0c7c` → the SDK's terminate wrapper) and its
  trigger (a null creator for the name `"all"` in the registry at `main+0x4d330a0..f8`, which holds only `"poll"` and `"none"`). What is not
  understood is why the game asks for `"all"` in a registry with those two entries: on the console the same code must find something, so either
  the registry is populated differently there (four of its six slots hold a `"tail_custom"` sentinel in this build) or the name comes from
  configuration the host does not serve. The strings around it are gRPC's (`grpc_poll_strategy`, `grpc.so_reuseport`), and gRPC's poll-strategy
  names in tree are `epoll1` / `epoll` / `epollex` / `poll` / `none` — `"all"` is not one of them, so the naming deserves a second look before
  any more of the chain is read.
- **Adreno compute pipeline creation: a minute a run.** The 11 captured compute programs compile once each, and three of them take `45.9 s`,
  `13.9 s` and `2.3 s` — on a second run too, with `vk_pipeline_cache.bin` (174 KB) loaded and re-saved. A run therefore spends most of a minute
  in the driver before the title can continue, which is why no capture has yet been taken past the intro. Worth checking whether the driver
  caches compute pipelines at all, and whether those three are being asked for with the local size their NVN2 control section declares.
- **The host's crash gate.** `crash_gate`'s `none == me` test never `_exit`s on the same thread, so a crashing process can keep presenting
  instead of failing cleanly. `DM_ABORT_CONT` is a deliberate park, not a substitute: the gate itself still needs fixing.
- **The picture.** Every frame is black and no draw is skipped, so the empty picture is not the shader bundle and not a composite: the frame is
  three passes (two `2048x1152`, one `2560x1440` present target) and each measures 0.00 % lit on its own. Two candidates remain, and a pass dump
  with `DM_VK_PASSDUMP=400` plus the per-pass draws (`DM_VK_TRACE_PASS`) tells them apart: the passes draw nothing because the game has nothing to
  draw yet (it is still loading, and the compute results it needs were skipped), or they draw with a texture or uniform that reads zero.
- **The `std::bad_alloc` that follows the three expensive compute programs.** The heap is now the console's 12 GiB layout (9.20 GB granted), so
  a flat shortage is ruled out: it does not happen when those three are skipped and does when they run, which points at what they compute or
  at their translation — they are three of the eleven programs this port added from run-time captures. The next probes are a gate on `main`'s
  own `__throw_bad_alloc` (not a dynamic symbol; find it by the `_ZTISt9bad_alloc` reference, which is in `main`'s data at `0x4958438`) and a
  picture from a run with only those three skipped, where the other eight compute programs do run.
- The full translation build (the rest of the 56,339 keys). The Android Vulkan chain translates the native task/mesh programs as EXT task/mesh, so
  the 845 refused by the Mac chain are not a wall there; the 3 `_cb0_40000000` pool-array shaders and the 8 Ampere-243 programs are skipped.
- The 38 unimplemented Ampere instructions (`243`, `f8c`, `3a9`).
- Memory: the 6.22 GB heap is the measured number; the game's `System/HeapSize` table is still unread, and the 12 GiB console layout the title plans
  from is not modelled.
- Android: the 25 GB RomFS reads from the tablet's data partition; the APK and its data pack are not assembled yet.

## Handoff (2026-11-14, Android)

What runs on the Y700 today: `dmhost` built from this profile with the four rewritten modules, the 2,398-shader bundle
(`android/shaders_world.dmsv`, 168.8 MB) and `DM_ABORT_CONT=1`, reaching 1,500+ presents at p50 16.66 ms with the AV1
intro decoding and no missing shader. The picture is still black.

The one open item: the three compute pipelines that cost 45.9 s, 13.9 s and 2.3 s to create on every run, which keep a
35 s run from ever reaching a frame worth capturing. Their bundle keys are not the `shader=%016llx` values the host logs
(those are the translated module's own key), so the next step is to find how `gfx_vk_exec.c` names them and read their
local size against the NVN2 control section — or to skip the dispatch behind an opt-in switch and see what the title
draws without them.

Pick up with this run and read `[vk] replay up to present … skipped (no program N)` plus the `compute pipeline end` lines:

```
adb shell 'cd /data/local/tmp/oot && DM_ROOT=$PWD DM_ROMFS=$PWD/RomFS DM_SAVE=$PWD/save2 DM_TEMP=$PWD/temp \
  DM_VK_SHADERS=$PWD/shaders.dmsv DM_ABORT_CONT=1 DM_VK_METRICS=1 DM_VK_SHOT=300,1200 DM_VK_SHOT_DIR=$PWD/shots \
  timeout 150 ./dmhost mods > log.txt 2>&1'
```
