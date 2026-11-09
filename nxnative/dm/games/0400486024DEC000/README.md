# The Legend of Zelda: Ocarina of Time (Switch 2) — `0400486024DEC000`

A Switch 2 title, dumped loose as `exefs/` (`main` 29.9 MB, `sdk` 7.8 MB, `subsdk0` 533 KB, `rtld`) and `romfs/` (25 GB) from update **1.1.1**
(`Product.100`/`Product.111` tables, `RegionLangMask.txt` `111`). Nintendo EPD's engine (Nin_Ounce: sead / agl / gsys, Phive), an `sdk` whose spec is
`Ounce`, NVN2 with Ampere shaders. **In bring-up: the host has not booted this title yet.** What is measured so far is its shader set.

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

- The host boot itself: nothing has been run against this profile. The first probes are the SVCs the SDK reaches, then the same order the other two
  Switch 2 titles used (`docs/SWITCH2.md`, Donkey Kong Bananza's Boot section).
- The 845 task/mesh programs (this host has no task/mesh pipeline) and the 38 unimplemented instructions.
- Memory: the 12 GiB layout the title plans from, and whether this engine's heap fits the host's reserve; the game's `System/HeapSize` table is
  unread so far.
- Android: untested, and the 25 GB RomFS is the first question there.
