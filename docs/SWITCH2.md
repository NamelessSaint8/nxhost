# Switch 2 titles

What a Switch 2 game's files mean for this port, measured on Mario Kart World 1.8.0 (program id `0400C3F00006E000`, dump layout: `exefs/` + `romfs/`).
The `porter` refuses such a game with `… is a Switch 2 program (its id starts 0400)`, naming this page. Nothing here is emulated or shipped: it says
what the engine already reads and what a port would still need.

## It is another console, not another game

| | Switch 1 | Switch 2 |
|---|---|---|
| Program id | `0100…` | `0400…` (the high byte is the console) |
| System services | Horizon 1.x: `fsp-srv`, `nvdrv`, `vi` | plus `nvsrv`, `gsv`, `gpu`, `vi2`, `syncpt`, a Switch 2 ACID in the NPDM |
| Graphics API | NVN | NVN2 over NvRm: GPU-visible memory handed to the game, its own channel/TSG ioctls, semaphored pushbuffers |
| Shaders | Maxwell SASS in a control section and a code area | Ampere (SM86) SASS: 16-byte instructions, a 0x80-byte SPH in front of them, a Turing+ macro (MME64) command stream |
| Memory | 4–8 GiB | a 12 GiB layout plus 8 GiB for the graphics server; a title plans ~9.5 GiB |

`porter` runs a Switch 1 title's own arm64 code against the host's Horizon/NVN stand-ins, so every row above is a surface the host would have to
implement. The engineering log for that surface, one row per problem solved, is the Eglantine project's `NX2_NOTES.md` (150+ rows; Eglantine is the
GPLv3 Switch 2 fork of Eden/Yuzu that runs a title on a PC by lowering Ampere code onto a Vulkan renderer).

## What already works here: the shaders

A Switch 2 game ships its shaders as `.bfsha` archives — `FSHA` wrapping a `BNSH` (`grsc` block), the same container as Switch 1 games, which
`dm/gfx/tools/shader_split.py` has read for years (Mario Kart 8 Deluxe: 29,650 shaders out of the same archives). Only two things differ:

- the program's stage slots are 0x20 bytes apart instead of 8, and the stage is named by the control section (`+0x56`) and the code area's SPH
  rather than by the slot's index (`bnsh_program_slots`);
- the code inside is Ampere, which `dmsh_xlate` already decodes (`arch: sm86`, `dm/third_party/ryujinx/.../Decoders/DecoderAmpere.cs`) and turns
  into SPIR-V or MSL like any other shader.

`devtools/nvn2_shader_census.py` measures a dump with both of those. On Mario Kart World 1.8.0 (2026-11-05, one machine):

| | |
|---|---|
| shader archives | 7 (`romfs/Shader/*.Nin_Ounce_NVN2.bfsha.zs` and one `.sarc.zs` holding a `BNSH`) |
| stage programs | 12,764 (6,382 vertex, 6,382 pixel), of which 3,238 unique |
| instructions | 2.4 million in the unique programs |
| **translator** | **3,238 of 3,238 unique programs translate** (SPIR-V, 30–85 KB each) |

So the shader half of a Switch 2 port is not a research problem: the corpus builds with the translator that is already in this tree. What is missing
is everything the shaders sit on — the NVN2 command stream, the GPU memory model and the services above.

## What a port would still need

1. **The NvRm surface**: device open, address spaces, channels/TSGs, GPU-visible memory (`nvsrv`, `gpu`, `gsv`), and the identity mapping of GPU VA
   to CPU VA a Switch 2 title assumes — not nvhost-as-gpu.
2. **The pushbuffer**: NVN2 submits with semaphored acquires, 4-byte releases, inline-to-memory subchannels, callable buffers and Turing+ macros;
   driving a Vulkan queue from that is the largest single piece (Eglantine's `NX2_NOTES.md` rows 42–66 and 130–152).
3. **The services**: `vi2` (layers, presents, fences), `syncpt`, the newer `am` commands, audio's `aud:u` style entry.
4. **Memory**: a title that plans 9.5 GiB does not fit a phone today, and the dump above needs 22 GB of RomFS on the device (the data pack would be
   pushed whole). A port would have to prove the game survives a smaller reported total, or target a device that has it.

Two facts make the work bounded rather than open-ended: the shaders build (above), and running the title's own arm64 code means no CPU emulation is
needed once the services answer — the same trade this port already makes for Switch 1.

## Running the census

```
python devtools/nvn2_shader_census.py "/Volumes/Data/Switch/Mario Kart World"          # counts, opcodes, translator pass/fail
python devtools/nvn2_shader_census.py <folder> --json census.json --top 20
python devtools/nvn2_shader_census.py <folder> --any                                  # scan every file, not just the shader archives by name
```

It needs `compression.zstd` (Python 3.14+, or `backports.zstd`) and, for the last section, the built translator
(`nxnative/dm/gfx/tools/dmsh_xlate_bin/dmsh_xlate`; build it with `dm/gfx/tools/dmsh_build.py`). A failure there is an Ampere instruction the
translator cannot decode or emit yet, and it names it.

## The emulator side

`NamelessSaint8/mkwsw2` is Eglantine's `nx2` branch with Mario Kart World fixes on top (`mkw-eglantine`), and Eglantine keeps an Android frontend
(`src/android`, per-SoC presets in `CMakeLists.txt`) with `hesanaltdoesgithub/Eglantine`'s `nx2-android` branch building an APK. That path runs a title
on a phone as an emulator; this port's would run it natively. They share the shader tooling above and nothing else.
