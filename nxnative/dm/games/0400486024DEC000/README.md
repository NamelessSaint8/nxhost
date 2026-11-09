# The Legend of Zelda: Ocarina of Time (Switch 2) — `0400486024DEC000`

A Switch 2 title, dumped loose as `exefs/` (`main` 29.9 MB, `sdk` 7.8 MB, `subsdk0` 533 KB, `rtld`) and `romfs/` (25 GB) from update **1.1.1**
(`Product.100`/`Product.111` tables, `RegionLangMask.txt` `111`). Nintendo EPD's engine (Nin_Ounce: sead / agl / gsys, Phive), SDK **22.2.8** (the `sdk`
names its spec `Ounce`), NVN2 with Ampere shaders. **The host boots it to `nnMain` and its first NVN2 frame setup**; the shader map and the pipeline
build are the next gate.

Reference: `NX2navi-0.5.0` beside the dump is a static recompilation of this game (v1.1.1) to Windows x86-64 with a Vulkan renderer. It is read for
**what the game asks of the SDK** — its architecture notes enumerate the services it had to serve (`fs`, `hid`, the audio renderer, `nn::codec`
movies, applet/account, the three-core scheduler) and the NVN2 commands it replays. Its additions are all rights reserved and its code is not copied
here; only the facts about the title are used.

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
2. **`FATAL cannot read the shader map …/shader_map.tsv`** — expected until the split finishes. Everything before it already ran: the RomFS mounted,
   `nvnDeviceGetInteger` answered API **231.40** (SDK 22, Switch 2), a 2560x1440 swap chain of 3 textures at interval 1 was created, the address
   regions were allocated, and CPU-written textures (serials 27–44) uploaded through the Metal layer.

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

- The shader map and the first full translation/pipeline build: 122,083 stage programs is a long build, and the 845 task/mesh programs stay refused
  until this host has a task/mesh pipeline.
- How far past the first frame the title gets: nothing after the shader map has run yet.
- The 38 unimplemented Ampere instructions (`243`, `f8c`, `3a9`).
- Memory: the 6.22 GB heap is the measured number; the game's `System/HeapSize` table is still unread, and the 12 GiB console layout the title plans
  from is not modelled.
- Android: untested, and the 25 GB RomFS is the first question there.
