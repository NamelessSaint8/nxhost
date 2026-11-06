# Bring-up brief: The Elder Scrolls V: Skyrim (01000A10041EA000)

For the agent picking this up. State of the world: 2026-11-06 (the last update at the top; the session notes below are kept as they were written).

## Session update (2026-11-06): the Mac app, the overdrive, and the holes at load

- **The Mac black screen was patience, not a fault.** After New Game the app plays the publisher cards and the dark intro fade for roughly 25–40 s before the cart scene becomes visible; the player quit after a few seconds. `DM_CTL shot` through the transition shows the Bethesda logo and "Presents" on black, then a dim scene that brightens. Nothing to fix.
- **The overdrive/static was the rear fold.** With the Mac app running, the player's A/B was decisive: front pair alone clean, the full 6 → 2 fold overdriven. `DM_AUDREN_PCM6` shows why: centre and LFE are all zero, and the rear pair is **exactly half the front** (41 s of gameplay: rear L = 0.5 × front L, residual RMS 0.5 of one 16-bit sample; the same for R). The plain ITU fold adds 0.707 × rear = 0.354 × front, i.e. **+2.6 dB of the same music** (RMS 1305 → 1767) with no new content. The fold is now duplicate-aware by default (`hle_audren.c`; `DM_AUDREN_DOWNMIX=all` restores the old fold, `=front` is the A/B mode). The player confirms it is clean and nothing is missing; the rear carries no independent content.
- **The load pop was mostly the ignored second renderer.** Skyrim opens a 32-voice `AudioRenderer` at boot and the host drove only the first. A dump of the second (`DM_AUDREN_PCM2`, diagnostic since removed) has a continuous 2 s run exactly across the first renderer's boot holes. Rendering the second once per output frame and adding it to the first takes the boot holes from **60 to 4** (the rest is the pre-audio silence and three sub-frame holes at 7.55 s) and the peak to 26k of 32k, no clipping. The player, on a labelled A/B: "Mixed sounds much better, but there's still some pop … smaller and fewer." The mix is the default; `DM_AUDREN_MIX2=0` restores the old behaviour for an A/B.
- **Ruled out on the way:** the output queue (0 underruns, 0 rendered frames dropped), the rear fold (front-only still popped), silent catch-up frames (8 dropped at boot), and the shared capture buffer (made `_Thread_local`). The remaining sub-frame holes are in the guest's own DSP mix; a frame-level declick was tried and did not remove them (removed from the tree).
- **The Mac app was rebuilt from HEAD** (`make -C nxnative/dm/host GAME=01000A10041EA000`), with the rebuilt `dmhost` copied into `The Elder Scrolls V - Skyrim.app/Contents/MacOS/`; its `Info.plist` `DMCommit` now says `149e2c1a`. **The app carries shader chain `0bfb5437fc0e`** (it was packed from a dirty tree), while HEAD's `dmsh_chain.h` says `5f4fb6fce881`: a host built from HEAD fails to load every shader. A local rebuild must pin `DMSH_CHAIN "0bfb5437fc0e"` for this app, or the app's shaders must be rebuilt for the new chain. The app's `.app` seal is stale as a result of the host replacement; it still launches by path.
- **Diagnostics added, not game patches:** `DM_AUDREN_PCM6=<file>` (six channels before the fold, startable live with `DM_CTL env`), the `DM_AUDREN_DOWNMIX` switch, `DM_AUDREN_MIX2=0`, a counted line for a dropped output block, and `audren: a catch-up frame … not played as a silent block`. The catalogue entries are in `nxnative/docs/reference/audio.md` under "Downmix", "Renderers" and "Timing and catch-up".

## Session update: the frame-1 stall was a GPU fence the host broke

The blocker described further down is solved, and it was not a lost job wake-up. How it was found, in order:

- **`DM_CTL memdump`/`peek` could not read the polled word** (0 of 64 bytes at an alias address). The control file copied with `vm_read_overwrite` alone; the host already had guest-aware readers. `dm_guest_read`/`dm_guest_write` (`hle_svc.c`) now read and write the way the guest can — the opened heap, committed alias pages, a kernel copy for anything else — and `peek`/`memdump`/the new `poke` use them. `poke <addr> <value> [bytes]` is the pair of `peek`: it writes one value into guest memory, which is how a wait the game never leaves gets probed.
- **The polled word was a report slot.** `while ([x19+0x10] != 0) YieldThread()` in `main+0xbfeb6c` is called from two 24-byte-bucket registries; the node's `+0x10` points at a 16-byte NVN report record (`{counter, timestamp}`), and all four records the engine had registered held a **timestamp in the counter field**. Writing 0 into the first one by hand (`poke 0x69a4560110 0 8`) moved `JobListManager` off the spin and put the main thread on the *next* slot — proof that this was the gate.
- **The cause, and it is general:** a timestamp report puts 0 in the counter field (the time goes in the second field), which is what lets a game use `ReportCounter(TIMESTAMP_TOP, rec)` as a fence — write a token into `rec`, report, poll for 0. The host wrote the *timestamp* into that field unless the profile key `render_cond` was set, in both backends (`nvn_mtl.m`, `android/gfx_vk_core.c`), so Skyrim's fence never cleared. Both now write `{0, time}` whatever the profile says (`render_cond` only decides whether conditions are evaluated); `t_nvn` checks it, and the catalogue entry is [A timestamp report used as a fence](reference/rendering.md#a-timestamp-report-used-as-a-fence).

### Where the port stands now

- **It presents frames continuously**: 300 frames per report window, 0 dropped, p99 33.34 ms (30 fps: the engine asks for present interval 2), footprint about 1.05 GB, frame 2,100 when last watched. The one `[RED]` line left is `audren: a second renderer (the host drives only one)` — the second `OpenAudioRenderer` — and it does not block.
- **The intro-skipping overlay is still in place** (`DM_ROMFS_OVERLAY` with `sIntroSequence=`), so what is on screen is the engine's own loading/menu path, not the intro movie. Consecutive `screencap`s differ, so the picture is animating rather than frozen (the next update identifies the screen and drives it).
- **Diagnostics added this session** (general, not Skyrim patches): `dm_guest_read`/`dm_guest_write` and `DM_CTL poke`, `dm_guest_describe` (a dump that stops short now says where: opened heap, alias offset committed or not), and the alias-region read fix behind all of it.

## Session update: the port is playable — control, saves, streaming

Checked against the "what would make this playable" list, item by item:

- **1. Control: there.** The pause menu opens with `Plus` (`QUEST JOURNAL`, `GENERAL STATS`, `SYSTEM`, `QUICKSAVE`, `LOAD`, `LEVEL 1`, and the clock `Sundas, 10:59 AM, 17th of Last Seed, 4E 201`), and the current quest reads `UNBOUND`. `B` backs out one level at a time (two presses from the pause menu's root). In the world a held `LUp~2` moves the camera/character: the frame changes across its whole upper half, not the idle animation's corner.
- **2. Input:** stick and buttons reach the game in gameplay, not only in menus (the walk above), and `A`/`Y`/`B`/`Plus` do what the on-screen hints say. Still to check by a player: the prompts for a real pad on Android, where the front end swaps A/B for physical controllers.
- **3. Saves: both halves work.** The engine wrote them by itself during the intro — `…_Save1_E17C50DC_0_507269736F6E6572_536B797269.sav0` and `…_Autosave1_…sav0`, 2.5 MB each, in the app's internal `files/save/Saves` (the name carries the hex of "Prisoner" and "Skyr…"). After a restart the main menu offers `CONTINUE`, and accepting "continue from your last saved game?" loads it and gives control back. Not yet done: a manual save from the pause menu, and quitting to the menu on purpose (the restart above did it for us).
- **4/5. Streaming and memory:** the alias region holds **2.00 GB** of its 3.21 GB application pool, footprint **1.62 GB**, no refused `MapPhysicalMemory`, no `SetHeapSize OOM`, 298–300 frames per window with 0–2 dropped at p99 33.34 ms (30 fps) through the load, the walk and a menu. Fast travel and a city interior have not been tried yet.
- **6. The skipped draws: closed twice.** The message named them (`draw skipped: vertex bound, pixel missing … the program holds <key> 0 0, its last bind had stage mask 0x1`), which first exposed that this backend read `BindProgram`'s stage mask 0 as "all stages" and cleared the shader shadow (`7c3252d4`, [A stage mask of 0 replaces no stage](reference/rendering.md#a-stage-mask-of-0-replaces-no-stage)) — and later that those vertex-only draws are a **depth prepass**, not draws that render nothing: see below.

### Resolved: actor skin, tree trunks and legs were the depth prepass

Reported by the player, 2026-11-03: armour, hair, eyes and foliage rendered, but no skin (bodies, faces, hands, the player's legs) and no tree **trunks** — and inside a head you could see the mouth, so the outer surfaces were absent rather than black. The player also guessed the tree trunks and the skin shared a cause, and they did.

- **The cause:** Skyrim draws a **depth prepass** with a program that holds a vertex shader only — `BindProgram(vs, 0x1)`, no pixel stage, rasterizer discard off. On the GPU that rasterizes with no colour output and writes depth; the shading pass then tests depth `EQUAL` against it. The Vulkan replay refused such draws (`prepare_draw`: "vertex bound, pixel missing"), 330 a frame and 1.58 M of 2.93 M by the 4,800th present, so those meshes never entered the depth buffer and the second pass discarded all their fragments. Alpha-tested foliage and armour do not use that pair of passes, which is why only skin, trunks and legs vanished.
- **The fix:** such a draw now runs as a **depth-only pipeline** (pipeline key `depth_only`): an empty fragment shader (validated 45-word SPIR-V) so Vulkan accepts the pipeline, and every colour attachment's write mask 0, so depth alone is written from the vertex stage. The Metal backend has always built "a vertex-only pipeline for the prepass"; this brings the Vulkan backend to it. Catalogue: [A depth prepass draws without a pixel shader](reference/rendering.md#a-depth-prepass-draws-without-a-pixel-shader).
- **Verified on the device:** `skipped (no program 0, no target 0, no pipeline 0)` (was 1.58 M), zero pipeline failures, and the player confirms bodies, trunks and legs are all back.
- **Found on the way, and wrong turns worth remembering:** `DM_VK_PROGBIND=1` (a bind inventory) is what produced the sequence; the "packaged textures: first uploads 0" line is a stub on Android and meant nothing; the fragment-depth variant, the one swizzled texture and the colour write mask all tested clean; the pipeline must be built with a *validated* SPIR-V blob (a hand-assembled one was refused with `-13 = VK_ERROR_INVALID_SHADER_NV`).

### Playing it with the on-screen gamepad

Skyrim has no inventory key: **Plus opens the pause menu**, and **ZL / ZR switch its category tabs** (ITEMS, MAGIC, SKILLS, MAP); the item list is the right-hand column, `A` equips or uses, `B` backs out one level. The overlay draws every button the game needs (`overlay_default.tsv`): `+` and `−` at the top centre, `ZL`/`ZR` at the top corners (x 0.06 / 0.94, y 0.30), `L`/`R` above them, a d-pad at (0.30, 0.80) — **d-pad Up is the favourites menu**, the quick weapon/spell switch — and a right stick at (0.74, 0.80). The tab switch was verified on the device: `ZR` in the pause menu changed the tab (14 % of the frame, the quest name changing from `UNBOUND` to `BEFORE THE STORM`).

### The route, as a script

`01000A10041EA000_build/route_skyrim.py` drives a launch from the title screen into the game, looking at the screen after every press (OCR through `scripts/ocr_shot.swift`) instead of firing a timed script:

```
python3 route_skyrim.py HA2M2W71              # title → CONTINUE (a save on the device) → control, checked by the pause menu
python3 route_skyrim.py HA2M2W71 --continue   # the same, explicitly
python3 route_skyrim.py HA2M2W71 --until intro   # NEW game: creation (Y = Done), name entry (adb Enter), stop at the intro
```

It handles the `PRESS ANY BUTTON` title screen, and `CONTINUE` versus `NEW` depending on whether the device holds a save.

## Session update: into a new game, through character creation, into the opening

With the fence fixed the port plays: main menu → New Game → character creation → the cart ride. What was needed to drive it, and what it cost:

- **The menu was readable only by OCR.** The screen is nearly black (luminance under 0.1) and no vision model was available, so screenshots were read with `scripts/ocr_shot.swift` (macOS Vision): `NEW <` / `LOAD` / `CRÉDITS` / `X Change User` with the `<` caret and the brightness ranking of each label, which is what identified the selection. Presses go through `DM_CTL` (`A`, `Down`, `Up`) and the engine answers them: `A` on `NEW` opened `Start a new game?`, the next `A` loaded the character-creation screen ("Song of the Dragonborn", `LEVEL 1`), whose confirmation starts the game.
- **The BSAs stream as soon as a game starts**: `DM_FSLOG` grows from 786 KB to 1.0 MB of read lines during character creation and the intro (a few hundred KB of reads per 15 s), footprint 1.05 → **1.55 GB**, still 30 fps (p99 33.34 ms, 0–2 dropped per 300-frame window), 42,000+ frames presented.
- **Still open, in order:** (1) one `[RED] [vk] draw with a program whose shaders are not in the bundle: skipped` (`gfx_vk_exec.c` `prepare_draw`, `S.sh[0]`/`S.sh[1]`), logged once by `VKRED_ONCE` without naming the program — the next step is to print the program's serial and which stage is missing, then take that shader into the split; (2) whether the intro reaches the execution scene and the HUD (the last captures show a full-frame 3D scene with no UI text, so this has not been confirmed); (3) the muted `audren: a second renderer` line, which does not block; (4) a **release** rebuild: the device still runs the 8.2 MB debug APK.
- **The route through character creation, for the next session:** main menu (`A` on `NEW`) → `Start a new game?` (`A` = Ok, the left option) → character-creation pages (`A` selects; the summary page's confirm is **`Y` Done**, not `A`; `Body`/`Head` rows are the tabs) → `Finish and name your character?` (`A` on `Ok`) → the name entry. That last one is the **host's own on-screen keyboard** (`front_android.c`, `nn::swkbd` → `front_text_input`), not the game's: its hint row reads `A key · B delete · Y shift · + OK · - cancel`, but it reads *Android input events*, so a `DM_CTL` press never reaches it — `adb shell input keyevent 66` (Enter) accepted the default name, `swkbd: title '' initial 'Prisoner' limit 26 min 0 → OK 'Prisoner'` in the log, and the intro loaded. A scripted `DM_KEYS`/`DM_CTL` route that has to type a name needs the overlay to read the scripted pad state too (an open, general improvement).
- **The intro then plays**: a bright daylight scene (the cart road) that changes every second, `DM_FSLOG` still growing, 300 frames per window with 0–1 dropped at 24–30 fps, footprint 1.57 GB. No HUD or subtitle text yet, so the execution scene has not been reached.

## Session update: the port boots and renders one frame

Done since the brief was written (commits `353e9539`, `0f7060c3`, `9653cd17`):

- **The BSA reader exists** (`shader_split.py`: `bsa_members`, `bsa_read`, `fxp_records`, `fxp_shaders`, `bsa_shaders`). All 89 archives are version 0x69 with 24-byte folder records (not 16), inline bzstrings and LZ4-frame entries. `shadersfx/shaders011.fxp` holds 23,082 shader records; `fxp_records` also finds 53 built-in records in `main` (the game draws the menu with two of them: `c654c9273c80debb`, `8f865c34471ac9d7`).
- **Split and translation**: 23,133 shaders (23,080 data + 53 main), 23,133 of 23,133 translated, 463 MB into `shaders.dmsv`.
- **Profile memory was wrong for this game**: the provisional 5 GB / 4.375 GB alias aborts `nnosInitialize` (`AllocateAddressRegion result 0x1803`). Measured on the Y700 with `DM_ALIAS_SIZE=0x1000000000` + `DM_REGIONS`: 24 regions, the last ending at alias +0x1baa00000 (7.4 GB). The build's `profile/01000A10041EA000/game.tsv` now has `mem_reserve 0x440000000`, `mem_alias 0x400000000` (16 GB, room for streaming); the host header confirms both.
- **Vulkan replay gaps fixed** (`dm/android/gfx_vk_exec.c`): `OP_BIND_UBO_SMALL` / `OP_BIND_VBUF1` (Skyrim sizes command memory from `GetCommandMemoryUsed`, so it emits the 24-byte bindings) and `OP_DRAW_TEX` (blit into each bound colour target). Unknown record ops are now named once each. `crash_dump_now` prints a running thread's guest stack inside an SVC (`dm/host/hle_thread.c`), which is how the looping threads were read.
- **Boot state on the Y700 (HA2M2W71)**: through `nnosInitialize`, `nnMain`, shader bundle load (23,133), audio (two `OpenAudioRenderer`s; the host drives one and says so), and the first menu/loading frame: 50 NVN functions, 543 calls, 16 `DrawElements`, 6 `SetRenderTargets`, 33 programs. The screen then stops changing (`shot` never writes a second frame; the window stays on frame 1).

### The remaining blocker (solved above: the polled word was a report slot)

Both the intro movie player and (with the intro skipped) the JobListManager spin in the same engine wait with `nn::os::YieldThread` (thousands of yields/s, `CPU` ~1 s):

```
main+0xbfeb94  (return into the caller of YieldThread)
main+0xbf5d14
...
```

`main+0xbfeb6c` loads `x20 = [x19+0x10]` and loops while `[x20]` is non-zero (`x20` = 0x69a4560110 in the alias, `x19` = 0x690a1ea020 — the same guest addresses across runs). The code around it reads the intro INI keys (`bPreloadIntroSequence`, `bAllowBinkSkipping`, `Data/Video/`) and the engine's own GPU profile strings (`%s%s (%0.2fms) (%ddraw %dtri)`, `Average GPU`), and frame 1 calls `CommandBufferReportValue=15` / `CommandBufferReportCounter=2`. So the wait is for a value the GPU should write (or a refcount a completed job should clear) and it never lands.

Next moves: find who clears that flag (the object is in the alias; `DM_CTL memdump` cannot read it because `vm_read_overwrite`'s `process_vm_readv` fails there, so use a host-side read or the Metal backend as the reference); compare `ReportValue`'s completion-time write with what the engine polls; check whether the second `OpenAudioRenderer` (32 voices, no host thread) is what the job waits on. The engine's `JobThread0/1/2` are idle on their condvar while the JobListManager spins, so a lost wake-up (or a job that waits on GPU feedback) is the shape to test.

Useful switches used this session (all in the device's `files/env.txt` unless noted): `DM_ALIAS_SIZE=0x1000000000` (sizing), `DM_REGIONS=<file>`, `DM_FSLOG=<file>`, `DM_ROMFS_OVERLAY=<dir>` (an overlay `Skyrim.ini` with `sIntroSequence=` skips the intro), `DM_VK_LOG=1`, and `DM_CTL=<file>` (only in a `--debug` APK: `dump`, `shot <path>`, `passdump <n>`, `memdump`, key presses by name). The debug APK is 8.2 MB; the release one is 1.8 MB and ignores `DM_CTL`.

## Where Skyrim stands

- **No profile anywhere**: not in `nxnative/dm/games/` (neither iOS nor Android), not in the user games dir. It has never been ported on any platform of this repo.
- **A survey exists** (the expensive part is done): `/Volumes/Data/Switch/Skyrim/01000A10041EA000_survey/survey.md` — read it first. Key facts: NVN + Havok, SDK 14.3.0, main build `771bdfb65f8d0af7203ad4dfeeb548fa`, system resource a mere 8 MB (no virtual-address heap drama expected), update v262144 surveyed.
- **A build folder exists** from a past experiment (`/Volumes/Data/Switch/Skyrim/01000A10041EA000_build/` — extraction and logs only; nothing reusable).
- **Game folder**: `/Volumes/Data/Switch/Skyrim/` holds base `[v0][US].nsp` (14.3 GB) + update `[v262144][US].nsp` (7.6 GB, note the stray `)` in its name — tags still parse) + a licence-only Anniversary DLC NSP (`…EB009`, no content, 121 KB).

## The one known blocker

The port refuses at the shader split: **"no BNSH / BAHS at the top level: the shaders are inside compressed or other containers or in main, and must be located first."** Skyrim's RomFS is 89 `.bsa` archives (12.35 GB of 12.36) — Creation Engine's shaders are almost certainly BNSH/BAHT records inside the BSAs.

**First task: a BSA reader in `nxnative/dm/gfx/tools/shader_split.py`.** Follow the existing reader patterns in that file (the docstring at the top lists them; e.g. the Monolith arh, Gust chunked-zlib, and Heaps readers are recent examples of the shape: open the container in python, walk its records, yield `(shader-key, source-label, stage, data)` the same way the other readers do, and add the dispatch entry so the split finds shaders under `Data/*.bsa`). BSA/BA2 are publicly documented formats (`0x00415342` "BSA" magic for classic, "BTDX" for BA2 with GENERIC/Texture variants); verify which one the Switch port ships by reading a header before writing the walker. If the records are compressed (LZ4/zlib), the file already has decompress helpers used by other readers.

**Do not** copy code from GPL emulators for the format — write the reader from the format spec/headers you inspect (behavior reference only; this repo is MIT).

## The machine you run (all validated this session)

1. `porter port "/Volumes/Data/Switch/Skyrim/" --experimental --progress json` — the unattended path: survey → provisional profile → rewrite → split (this is where the BSA refusal fires until the reader exists) → Vulkan translate → APK + data pack. Links Awakening (also never ported) went through in under 5 minutes once its reader path existed.
2. Device boots without a human: `--tool-device HA2M2W71` (the Legion Y700; also plain `--tool-device any`). The tool mode pushes dmhost + rewritten modules + RomFS image + shader bundle to `/data/local/tmp/nx2a-tool/<title ID>/` itself and boots headless with `DM_TOOL_BOOT`. `boot_android()` in `nxnative/scripts/build_ipa_from_nsp.py` is the implementation; the heap/region/GLSLC checks call it through `DM_TOOL_DEVICE` in the env.
3. Read a crash: the headless log goes to `<build>/logs/*.log` on the Mac. `[dm] CRASH sig=… pc=main+0x…` lines give the offset; disassemble the rewritten module (`.venv/bin/python`, `sys.path` `nxnative/dm/tools`, `import nso, capstone`, `nso.read(<patched>/main).image`). The rewritten modules live in `<build>/android/patched_<ver>/` (the module *files*, beside the `*.tsv` records — note `nso.read` takes the module file path).
4. Abort messages are spelled in the crash registers — decode x4–x7/x12–x15 as ASCII (two examples in `docs` history: "missing RomFS", "not a common ticket").

## What "done" means, and the rules

- Success = the game boots on the Y700, and every fix along the way is a **general rule**, not a Skyrim patch: engine-level in the host/rewriter, a reader in the split, a key in `profile_guess.py`. `nxnative/AGENTS.md` and `nxnative/docs/agents/03-bringup.md` (upstream's failure catalogue) are the canon; classify every crash against the catalogue before inventing anything new.
- Repo rules: English everywhere; `python -m unittest discover tests` (450/450 today) green before commits; commit style is `type(scope): summary` with a body of facts (see `git log`); never commit keys or game files; changes under `nxnative/` should be written to be offerable upstream.
- The three merge-era regressions found this session (unresolved `mtl_*` symbols, the `dm_tsd` TSD bug that broke every Android build, the tool boot's missing shader bundle) are all fixed and committed — `git log --oneline -12` tells the story. If a device boot draws nothing, check for `[vk] [RED]` lines first.
- The debug loop that works: add `LOG(">>> step")` markers where the boot stalls, rebuild (`dm/android/build.py --game 01000A10041EA000 --ndk <NDK> --out <build>/android/host --lib --exe`), push, run, read. Each cycle is ~3 minutes.

## Parallel thread (don't break it)

Link's Awakening is mid-bring-up: ported, boots through `nnMain` on the Y700, heap signal 3.14 GB captured, now stuck at `main+0x1c180`. Decoded so far (register dump in `<build>/logs/la_boot.log`, disassembly of `<build>/android/patched_v131072/main.patched.bin` — the rewritten modules are `*.patched.bin` files, not directories):

```
+0x1c16c: ldrh w8, [x19, #0xa0]        ; a 16-bit index from a live guest-heap object (x19 = 0x7520994020, in the 3.14 GB heap)
+0x1c174: adrp x10 …+0x898             ; a 0x58-byte-stride table in main's data at +0x1bcc898
+0x1c17c: madd x8, x8, x9, x10
+0x1c180: ldrb w8, [x8, #0x49]         ; <<< SIGSEGV, the index resolved outside the mapped table
```

The object's `+0xa0` field holds a garbage index — and the picture sharpened on 2026-11-03 ~01:00:

- **The Mac host passes this exact code** (same game, Mac rewrite, headless boot): it crashes *later*, at shader-library loads, only because its `DM_MSL_DIR` was empty. So `+0x1c180` is Android-path-specific in effect — but not a single wrong API answer:
- **The crash is timing-dependent.** With `DM_NVN_LOG=1` (slower execution) the same build crashes earlier and elsewhere: `main+0x111e0d0`, `addr=0x38` — a null-object deref. Two sites under timing shifts = a **race in the game's early render init** (main thread vs its render thread), the class the bring-up catalogue knows from other games (spin waits, sync semantics).
- The mode index at `[x19+0xa0]` is copied from the caller's stack struct (`[x21+0x38]`, x21 on the guest stack) — set in a caller before the second `vi::SetLayerCrop`. Game-visible log lines match the Mac exactly through both vsync/setcrop phases; the divergence is after the second `SetLayerCrop 1920x1080`.
- Symbols: the shipped `main` has 51 dynamic symbols only; `main.obs.tsv` has 9 rows — identification is semantic (disassembly + string refs), not by name.

Next moves, in order: (1) run the Android boot 5× plain and 5× with `DM_NVN_LOG=1` — if the two crash sites alternate, it's the race confirmed; (2) chase `+0x111e0d0`'s null object (whose pointer is it — disassemble back for the object's origin); (3) check the render-thread sync HLE (`svcWaitSynchronization` on the vsync event / fence semantics in `hle_thread.c`) against the catalogue's spin-wait entries; (4) the Mac comparison at MSL-complete parity (run `dmsh_build`'s Mac chain for LA first) tells whether the race is engine-generic but merely *won* on Mac timing. Fix as a general rule in the sync/wait layer if (3) confirms.

## Session update: the tavern-return crash (2026-11-03)

The player's run ended 1,791 s in, while screen recording and walking back to the tavern: `CRASH sig=11 addr=main+0x115cf9c pc=main+0x34af778 lr=main+0x115cf98`, a 16-bit store into the game's own code. Nothing on the host side was wrong: footprint flat at 1,688 MiB, 0 dropped frames in 95 of 98 windows, audio 0 underruns, no refused allocation, and the only `[RED]` lines are the two known start-up ones (a second audren renderer, the present thread's policy). The three `[vk] [alias] stale read` lines are image-side only (an albedo sampled over a shadow map), so the alias path is exonerated as a source of CPU-visible corruption.

What the code says (`<build>/android/patched_v262144/main.patched.bin`, and the unpatched `main` from the survey extract for the original instructions):

```
+0x115cb0c: add  x18, x8, x15          ; x18 used as a scratch pointer here, not the TLS base
+0x115cb14: str  w10, [x18]
+0x115cb38: sub  w18, w18, w10
+0x115cb3c: lsr  w18, w18, #2
+0x115cb40: strh w18, [x1, x2]         ; <<< the crash, x1 = lr, x2 = 4
```

- **It is an interpreter loop**: `madd x1, x10, x16, x20` with `x16 = 0x18` (a 24-byte stride) and `x20` = the base loaded from a structure field (`ldr x28, [x24, #0xb0]` at `+0x115cf18`, passed as the helper's second argument). The store writes a packed 16-bit value into a source structure, indexed by a jump table (`ldrsw x2, [x11, w2, sxtw #2]`).
- **The rewriter is not at fault.** Its `x18` sites in this loop are shadow-register stubs in the patch area (the patched image is 55 MB against the original 33.9 MB, so `+0x34af75c` is appended by `patch_nso.py`): each stub is entered by exactly one branch (checked over every `B`/`BL` in the image), keeps the shadow in TLS at `*(tpidr_el0+0x10) + G`, and preserves `x0`/`x1`/`x3` in the red zone. The dump agrees with the code everywhere else — `x0` = `0xc37` is exactly the word the stub had just loaded from the shadow slot, `x17` = `x8 + x14` exactly, `x16` = `0x18` — so the shadow model is faithful. The one register that does not fit the arithmetic is `x1`, which equals `lr`: the base field held a code address, so `[base + 24 * index + 4]` landed on the return address + 4. **What corrupted that field is still unknown**; the run's own log has no earlier fault to blame.
- **New general rule** (`dm/host/text_store.c`, `fix(host): a guest store into a module's own text is reported and dropped`): a write fault inside a module is a bad pointer, not self-modification — the writable segments are mapped writable, so only code can fault — and the store is reported once per distinct (pc, target) with its instruction and `x1`/`x2`/`x19`/`x20`/`lr`, then dropped so the run continues. Reference entry: `nxnative/docs/reference/memory.md` "A guest store into a module's own text". Test: `make -C nxnative/dm/host/tests GAME=<id> text_store`.

If it recurs, grep the log for `[RED] a guest store into read-only text was dropped`: the line names the site and the registers that addressed it, and the run keeps going instead of dying. To find the writer rather than the victim, arm `DM_PROBE_WATCH=<address of the field that held the base>` (see `dm/host/probe.c`) once the field is identified.

Still open from this session: the load-time replay cost (50–125 ms in `submit+present` on a cell load — `acquire` waits at steady state, the replay itself during streaming), fast travel and interior streaming, and a 30-minute soak.

## Session update: 60 fps, and why VRR is not on the table (2026-11-03)

The player asked for VRR or 60 fps once combat and magic worked. Two different answers:

- **VRR: no.** The Y700 reports fixed modes only — `mSupportedRefreshRates=[120, 165, 144, 90, 60, 30]`, `hasArrSupport false`, no VRR mode — so there is nothing to switch on. It would also not help: at 30 fps the port already lands every fourth vsync of the 120 Hz surface (p99 33.34 ms, 0 dropped), and all the frame-time variation sits inside cell loads, which no panel mode absorbs.
- **60 fps: yes, and it cost no code.** The cap is the game's own NVN **present interval 2** on a 60 Hz tick, not an engine limiter: the boot line says it (`present tick 60 Hz, interval mode game (game profile present_interval; present interval set by the game 2; window, fixed 60 Hz)`). The port already has the switch for exactly this shape of cap, so `DM_PRESENT_INTERVAL=display` gave 60 fps at the title screen and in a loaded save: **0 dropped, p99 16.67 ms, frame time p50 16.64 / p95 17.94 / max 18.80 ms**. The profile's `present_interval` is now `display`, so 60 is the port's default.
- **The speed check came first.** `present_interval display` is only safe for a game that does not count frames; a frame-counted one runs at double speed. The player played at 60 and reported walk pace, NPC animation, combat and magic timing, and the in-game clock all at normal speed — Skyrim's logic is time-based.
- **The budget is now full, which is the new constraint.** Frame work p50 **16.54 of the 16.67 ms**, GPU busy 12.30 ms, replay 4.46 ms over 2,050 draws (descriptor sets 1.26), queue submit 0.85 ms. Steady country holds 60; cities and combat will drop frames before they stutter, and the headroom to buy is in the replay.

Reference entries: `nxnative/docs/reference/frame-rate.md` "A 30 fps cap that is only a present interval" (the pattern and the proof required), and the `present_interval` row in `nxnative/dm/games/README.md` (the switch's contract).

## Session update: the tavern crash, classified (2026-11-03)

The run that died 1,791 s in — screen recording, walking back to the tavern — is
`CRASH sig=11 addr=main+0x115cf9c pc=main+0x34af778 lr=main+0x115cf98`, a
`strh w0, [x1, x2]` with `x2 = 4` inside a rewriter stub: a two-byte store that
landed 4 bytes past the return address, in `main`'s own text. Classified against
the catalogue as **guest-side data corruption**, and the host is exonerated on
every axis the log carries:

| Check | Value before the crash | Reads as |
|---|---|---|
| Allocation failures | none: the only `[RED]` in 2,981 lines is `audren: a second renderer` (benign, present since boot) | no refused allocation, no OOM path |
| Memory | `alias region mapped 2.00 GB (3.21 GB pool)`, footprint flat at 1,688 MiB across the last windows | no growth, no eviction storm |
| Frame health | `on-screen up to frame 53400: 300 frames, dropped 0, p99 33.34 ms`; adaptive rate 40 fps, `late on screen 0 of 64` | not a timing failure |
| Host writes into textures | `writes beside a texture only (not re-uploaded) 0`; `write-protection faults 516, pages unprotected before host writes 0` | no host write escaped its texture |
| What the process was busy with | profiler top: libc `syscall`/`read` and `vkAllocateDescriptorSets` | I/O and descriptor churn, i.e. load, not corruption |

So nothing in the host produced the bad pointer: a guest structure field held a
code address where a data address belonged, and the value equals the current
link register — the shape of a stack slot that held a return address being read
as a data pointer. No log line can show which read did that; it needs the first
corruption, not the crash.

**What that means in practice:** the `text_store.c` guard (7b33cfa7) covers this
exact fault — the target is a module's read-only text — so the same corruption
now logs `[RED] a guest store into read-only text was dropped: main+0x115cf9c
from main+0x34af778 by the instruction … (x1 … x2 …)` and the run continues
instead of ending. That line is the reproduction signal to watch for: if it
appears, the crash is back and the reported registers name the pointer.

**What would settle the cause**, in order of cost: a 30-minute soak with screen
recording to see whether it recurs at all (one occurrence is not enough to chase);
then `DM_PROBE_WATCH` on the structure field once the dropped-store line names a
stable `x1`, to catch the writer rather than the victim. The alias write-protect
path is already the least likely suspect (its stale reads are image-side only),
but disabling it (`DM_NVN_DIRTY=0`) is a one-run way to rule it in or out.
