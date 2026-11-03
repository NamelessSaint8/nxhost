# Bring-up brief: The Elder Scrolls V: Skyrim (01000A10041EA000)

For the agent picking this up. State of the world: 2026-11-03, after the M0 upstream merge (HEAD ≈ `a16ac09d`). Everything below was verified this session.

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
