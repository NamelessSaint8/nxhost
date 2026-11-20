# Persona 5 Royal (`01005CA01580E000`)

Update 1.0.2 (`v65536`) over the base game, SDK 13.3.2. Atlus GFD / Needle on NVN, with CRI middleware. Modules `main`, `subsdk0` (NintendoSDK_movie) and `sdk`.

**Current:** opening casino gameplay tested on Mac with the complete shader library. The unsigned 1.0.2 IPA is built (15,969,549,546 bytes, about 14.9 GiB). iOS and later battles have not been tested.
**Android:** the title runs on the Y700 at its own 30 fps cap with the complete shader library (2026-11-18, [below](#android-2026-11-18)). Later battles and the Mac on the current chain are still open.

## What it needs

| Setting | Where | Why |
|---|---|---|
| `mem_reserve 0x100000000`, `mem_alias 0x10000000`, `mem_stack 0x10000000`, `app_pool 0xCD500000` | [`game.tsv`](game.tsv) | the NPDM declares no system resource; the game sets a heap in the existing 4 GB layout |
| `mem_used 0x4c00000` | `game.tsv` | the rewritten modules require 76 MB, exceeding the default 64 MB deducted from the pool |
| `pad_layout full` | `game.tsv` | movement and camera use both sticks |

## Rendering

- **Resolved:** the first boot trapped in `SetupSurfaceInfoMemoryInside`, at `main+0x1028fbc`, asserting `ctx.memorySize <= localmemsetupinfo.memorySize`. A 16x16 RGBA8 texture with flags `0x44` (`IMAGE | LINEAR_RENDER_TARGET`) and stride 128 received only 1 KB from the host; the game independently calculated 2 KB. The general fix is linked below. No executable cut is needed.

- **Resolved:** the casino clears only alpha on a 1920x1080 RGBA8 texture (`mask 0x8`). The general partial-channel texture clear implementation preserves RGB and supports explicit regions; no game-specific override is needed.

## Files and builds

- `CPK/ALL_USEU.CPK` contains 94,631 files, 74,521 CRILAYLA-compressed; `CPK/PATCH1.CPK` contains one USM movie. The host reads the archives through the game's own CRI file system.
- The available release supports English, French, German, Spanish and Italian language codes. The build defaults to American English.
- Only the merged update is extracted and registered. Fixed addresses in this note refer to `main` build `d4b150b29a931cd381e2a30318fc299f`.

## Shaders

- **Resolved:** the initial split found no shaders. NEEDLE `HNSHV002` containers hold 228 shader records in `main` and 30,418 in nine GSC files inside `ALL_USEU.CPK`. The descriptor-based reader extracts 30,646 unique keys: 29,526 pixel, 1,114 vertex and 6 compute, with 3,342 single-stage cover pairs.
- All 13 shader control/code pairs captured during startup match the extracted package bytes and keys (8 from `main`, 5 from GSC files).
- **Resolved:** all 30,646 keys translated successfully for both Mac and iOS, producing 27,501 variants. The full libraries use chain `dec5ee141a9f` and profile-input stamp `f53e8a12f4ad`; there are no unfillable driver reads or undecoded bindings. Final Mac gameplay validation loaded this full stamped library on base `7a3b958`. The port was subsequently integrated onto `c3a0880`, whose upstream image-atomic changes advance the chain to `467efdfd0b62`; the affected Metal regression tests were rebuilt and passed there, but a full game shader rebuild and gameplay replay on that chain have not been performed. The existing IPA remains the validated earlier-chain build.

## Testing and running

On 2026-10-25, update 1.0.2 was tested on an M4 Pro Mac with Metal API validation enabled. Boot, startup movies, title and language menus, opening dialogue, and casino gameplay rendered. Movement, camera control and the first two platform jumps were exercised. The full-library run exceeded 35 minutes without a crash, missing shader or Metal validation error. Recent casino frame-time windows measured p50 33.33 ms and p95 33.36 ms (about 30 fps); occasional longer frames occurred during the run. Resident memory was about 1.9 GB and GPU allocations about 1.75 GB. This is an opening-sequence check, not a full playthrough.

Build with `scripts/build_ipa_from_nsp.py` pointed at the NSP folder and the local keys file. The output is `Persona5Royal.ipa`; it contains no code signature or provisioning profile. For Mac testing use the generated `<title ID>_build/tools/dmhost` and `patched_v65536`, with `DM_ROOT` set to the build directory, `DM_ROMFS` to `extract/v65536/RomFS`, `DM_MSL_DIR` to `shader/cache`, and `DM_FONT_DIR` to `font`. Set `DM_NVN_SHMAP` to this profile's `shader_map.tsv`, `DM_LANG=en-US`, and writable `DM_SAVE` / `DM_TEMP` directories under the NSP folder. See the [control-file recipe](../../../docs/agents/05-debugging.md) for `DM_CTL`.

Choose offline mode at the network prompt, then New Game and English voices. Advance the opening dialogue; Plus shows and confirms movie skipping. In the casino, the left stick moves, the right stick controls the camera, and A jumps at marked platform edges.

## Found on this game

- [Linear render-target storage without the LINEAR flag](../../../docs/reference/nvn-objects.md#linear-render-target-storage-without-the-linear-flag): sizing, row pitch and deswizzle eligibility must all recognize `LINEAR_RENDER_TARGET` independently.
- [Needle shader containers in main and GFD archives](../../../docs/reference/shaders.md#needle-shader-containers-in-main-and-gfd-archives): descriptor-based extraction of NVN control/code sections.

- [Texture clears with partial channel masks or regions](../../../docs/reference/rendering.md#texture-clears-with-partial-channel-masks-or-regions): a load/store draw applies the requested write mask and rectangle.

## Android (2026-11-18)

The Android row ([`android.tsv`](android.tsv), `status wip`) was written on 2026-11-18 and the port built with it: `python -m porter port <folder> --platform android`. The extraction matched the registered build (`main` `d4b150b2…`, `subsdk0` `a8cb9780…`, `sdk` `357efc19…`), so nothing was derived. Chain `8d58a1fdc9dd`.

| | |
|---|---|
| shader split | **30,646 shaders**, the profile's own count (2:32; the tables were rewritten, not re-derived) |
| Vulkan bundle | **30,646 of 30,646 translated**, no failures, 469 MB |
| host / APK / data pack | 2.7 MB / 2.9 MB / 14.7 GB (one 15.2 GB `RomFS.img`) |
| device install | 8:28 push to `org.nx2a.p5r` on the Y700 (`HA2M2W71`) |

Measured while playing (2026-11-18, window around present 7,800):

| | |
|---|---|
| boot | `>>> nnMain`, `[mem] heap 3.13 GB (heap region 3.25 GB)`, RomFS image mounted, Adreno 840 / Vulkan 1.4 / BC yes |
| frame rate | **30 fps, the game's own cap**: frame time p50 33.33 / p95 33.60 ms, on-screen p99 33.34 ms, dropped 0–1 per 300 frames |
| GPU | p50 **17.85** / p95 20.13 ms — about 54 % of the 33.33 ms budget |
| CPU replay | **9.11 ms** a frame: 1,135 draws, descriptor sets 2.35 ms, pipeline keys 1.05 ms, queue submit 0.24 ms |
| draws | 3,848,400 in 7,799 presents, **skipped (no program 0, no target 0, no pipeline 0)**; 104,304 compute dispatches, 454 pipelines |
| descriptors | 1,555,197 sets reused, 713,247 new over the run (hashing 0.29 ms a frame) |
| memory | Vulkan live 1.88 GB (zero-copy, inside the guest heap); process **PSS 2.53 GiB**, RSS 2.64 GiB |

- **The one `[RED]` line is the known one:** `SetRenderEnableConditional: the host draws anyway for now`, the same unvalidated conditional rendering the Mac run reports ([Open](#open)). Nothing failed to load, draw or dispatch.
- **`[movie]` is never called, even with `DM_MOVIE_TRACE=1`.** The title's videos go through CRI's own player in guest code rather than the SDK codec HLE, so the host's movie path is not on this title's route; boot, the Thieves' Guild prompt and the transition past the P-Studio logo all happen with zero movie-HLE calls.
- **Textures are drawn with something other than their storage, and it is not yet attributed.** The per-window `packaged textures` counters are **not measurements on Android** (`mtl_pkg_stats: not implemented on the Android backend`), so their `first uploads 0` and `re-uploads 0` say nothing. Seen in play: pop as an area appears, and a **black attack screen** with its UI drawn over it (2026-11-18). The instrument for this class is [`DM_VK_TEXLOG`](../../android/gfx_vk_tex.c), which answered the same question for Persona 4 Golden's blocks of colour by naming how each image was filled (`lin-copy`, `pkg-block`, or `lin-declined`/`no-layout`/`no-memory` for an image nothing filled) with hashes of the guest bytes and of the texels the GPU gets.
- **The 2D dialogue bustups upload through one reused staging block.** A `DM_VK_TEXLOG=5000` run into the casino prologue (2026-11-19) logged **438 `wrote-b2t` copies and 0 packaged uploads**: every compressed texture (BC1 `0x42`, BC2 `0x43`, BC3 `0x44`, BC7 `0x4d`) arrives through `nvngfxCommandCopyBufferToTexture`, and the bustups and the overlays drawn over them all read from the same three blocks (`0x…c67000` for the 768×768 BC7 bustups and their 128×80 overlays, two more for the casino's 3D textures). Each of those images was created once and filled once — no eviction and no re-upload appears for the serials that draw black — so the black is the copy's content, not a lost image. The class and its fix are [a buffer → texture copy read at execution](../../../docs/reference/rendering.md#a-buffer--texture-copy-reads-its-source-when-the-copy-runs-not-when-it-was-recorded); `DM_VK_B2T_SNAP=1` is armed for the bustup A/B, which is still the open check.
- `DM_CTL` is unset in a release build (`front_android.c`), so the live instruments can only be armed from `env.txt` at launch; `porter port --debug` builds a host that also takes live control lines.
- `porter triage` cannot boot this title: it looks for an experimental profile under `<build>/profile/<id>` and a repository profile has none. The boot above was started with `am start -n org.nx2a.p5r/android.app.NativeActivity` and read from `log.txt` in the app's files folder.

## Open

- Rebuild the complete game libraries and host on the current upstream chain, then repeat gameplay validation.
- Test battles, later story scenes and save/load over a longer playthrough.
- `SetRenderEnableConditional` still reports that the host draws unconditionally. No visual failure was identified in the tested opening; conditional rendering remains unvalidated.
- Device validation remains for the user after sideloading.
- Android: attribute the texture pop seen in play (a texture-upload log across a transition, not the steady-play counters), then test battles, saves and the pause menu on the device.
- Android: the casino bustup A/B for `DM_VK_B2T_SNAP=1` — Morgana's and Futaba's 768×768 BC7 bustups (they draw black inside the silhouette with the switch off) against the same dialogue with it on. The device APK and the `env.txt` line are in place; the run that reaches the dialogue has not been driven yet (the tablet was driven blind from `ctl.txt` on 2026-11-20 and stopped in the title's 3D scene, which ignores A, Plus and the left stick).
- Android: make `porter triage` find a repository profile, so this title's bring-up loop is one command.
