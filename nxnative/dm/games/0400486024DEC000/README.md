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

## Open

- **`auddmg:u`**: the session, the HIPC close and the manager object work. Command 0 now returns a move handle (`0x20000`), and the client sends its
  manager requests on it (the host adopts the handle and answers). What is not solved is the manager's **answer buffer**: the descriptor resolves to
  a host address (`0x16d991120`; the three words are logged, `00000800 6d121110 10000000`, and the address differs every run) — so no device count or
  name is written. A page-mapped test is not a guest test: trying it let the write land in host memory, and that write is reverted. The gap is the
  pointer-buffer translation this host does not model (`QueryPointerBufferSize` answers 0). The manager's commands and its 0x228-byte properties block are
  described in the reference port's note.
- **A second abort follows, and it is not audio.** Past auddmg the run logs `WindowCrop 0,0 2048x1152`, an unimplemented
  `nvnCommandBufferSetComputeWorkloadPriority`, and then `nn::diag abort` with **Result 0** and an empty message at `sdk+0xb8fe8`
  (`bt: sdk+0xba138 sdk+0x7bd670 sdk+0x777f30 main+0x21f0c80`). In the same window the renderer says
  `[RED] program has no vertex shader (or it is not mapped)`, so a draw with one of the 52 missing task/mesh programs is the leading candidate rather
  than an auddmg failure. `audsmx:u` is served as an object but its `CreateStream` protocol is unimplemented, so audio is a stand-in at both ends.
- The full translation build (the rest of the 56,339 programs) and the 845 task/mesh programs, which stay refused until this host has a task/mesh pipeline.
- The 38 unimplemented Ampere instructions (`243`, `f8c`, `3a9`).
- Memory: the 6.22 GB heap is the measured number; the game's `System/HeapSize` table is still unread, and the 12 GiB console layout the title plans
  from is not modelled.
- Android: untested, and the 25 GB RomFS is the first question there.
