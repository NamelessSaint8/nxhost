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

`dm/games/0400C3F00006E000/` is this dump's game profile: `shader_split.py` over its RomFS and then the Android chain's `shader_vk.py`, so the numbers
below are the ones a port would carry, not a sample. On Mario Kart World 1.8.0 (2026-11-05, one machine):

| | |
|---|---|
| shaders (split) | **11,603** — 7,301 pixel, 3,560 vertex, 729 compute, 13 domain — in 5,180 variation pairs, from 54 files: `Shader/*.Nin_Ounce_NVN2.bfsha.zs`, one `.sarc.zs` of agl `sharcb` packs, `Lib/agl/agl_resource…sarc` (3,924 alone), the effect set and the UI layouts |
| **SPIR-V (Android chain)** | **11,577 of 11,603 build (99.8%)**, a 495 MB `shaders.dmsv` bundle |
| the 26 that do not | every one is a **task or mesh program** (`ISBERD`/`ISBEWR`): NVN2 draws some geometry with a task program in the vertex slot and a mesh program in the tessellation slot, each writing its vertices into a stage buffer (Eglantine's `NX2_NOTES` rows 89 and 97) |

`devtools/nvn2_shader_census.py` is the same measurement without a profile, for a dump that has none.

Two instructions the decoder lacked were added on the way: `UP2UR` (`0x883`, 29 of the pixel programs) and `SURED.D.2D.ADD.U32` (`0x59f`, one race
compute). The third pair, `ISBERD`/`ISBEWR`, is refused by name rather than decoded: it only appears in task/mesh programs, and reading it as a store
would have made those programs "build" into shaders the host cannot dispatch. Changing the translator moves the chain version (`dmsh_chain.lock`,
`dm/gfx/nvn/dmsh_chain.h`), so the next port rebuilds every shader it packs.

Naming the files after shaders is not enough: the effect set (`Effect/static.Nin_Ounce_NVN2.esetb.byml.zs`) alone holds 1,017 compute programs, and
`Lib/agl`'s resource pack 3,924 shaders that a pass over `Shader/` alone reports as nothing. Three Switch 2 titles already have split shader tables in
this tree (`dm/games/040074A01BF12000` Donkey Kong Bananza, `04007EF01F8AE000` Fire Emblem Fortune's Weave, `0400380020056000` Splatoon Raiders).

An agl `sharcb` pack is read by walking its 16-byte entry records at a 4-byte stride, which can pair one entry's control section with another's code
area; one such window in `DrivePassShaderDefault.sharcb` named a compute stage over a code area that opens with a vertex SPH. That pairing is now
refused (`nvn2_stage`) rather than handed to the translator.

So the shader half of a Switch 2 port is not a research problem: 99.8% of this title's shaders build with the toolchain that is already in this tree,
and what is left is a pipeline this host does not have rather than a decode gap. What is missing is everything the shaders sit on — the NVN2 command
stream, the GPU memory model and the services above.

## What a port would still need

1. **The NvRm surface**: device open, address spaces, channels/TSGs, GPU-visible memory (`nvsrv`, `gpu`, `gsv`), and the identity mapping of GPU VA
   to CPU VA a Switch 2 title assumes — not nvhost-as-gpu.
2. **The pushbuffer**: NVN2 submits with semaphored acquires, 4-byte releases, inline-to-memory subchannels, callable buffers and Turing+ macros;
   driving a Vulkan queue from that is the largest single piece (Eglantine's `NX2_NOTES.md` rows 42–66 and 130–152).
3. **The services**: `vi2` (layers, presents, fences), `syncpt`, the newer `am` commands, audio's `aud:u` style entry.
4. **A task/mesh pipeline** for the geometry drawn that way (`ISBERD`/`ISBEWR`): Vulkan's `VK_EXT_mesh_shader` or Metal's mesh stages, with the
   stage buffer those two stages hand each other. The 26 programs above are exactly those draws.
5. **Memory**: a title that plans 9.5 GiB does not fit a phone today, and the dump above needs 22 GB of RomFS on the device (the data pack would be
   pushed whole). Measured in an emulator, it does *not* survive a smaller reported total: given 10 GiB it touches memory that only exists in the
   12 GiB layout and never reaches its shaders (see below). The total is therefore fixed, and a port needs a host that can back it.

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

## On a device: does the driver compile it?

A translator's SPIR-V is not a driver's answer, so `probes/vksh.c` takes a `shaders.dmsv` bundle to an Android device and compiles it there: every entry
becomes a shader module, each compute program a compute pipeline (empty layout — the code is what is under test), and with `--pairs` each
vertex/pixel pair a graphics pipeline (dynamic rendering, one colour attachment, no vertex buffers). Every optional feature the device reports is enabled,
or a refusal would say nothing about the shader.

Measured on a Lenovo Legion Y700 (SM8850P, Adreno 840, driver 512.842.31, Vulkan 1.4.295), bundle of 11,577:

| | |
|---|---|
| compute pipelines | **729 of 729 compile** |
| graphics pipelines | **5,180 of 5,180 pairs compile** |
| before the padding | 5,124 of 5,180 compiled; the 56 that did not failed with `VK_ERROR_UNKNOWN` while both their modules were created, and the failure followed the *pair*, not a shader — re-pairing each failing pixel stage with a known-good vertex stage flipped 47 of 112 to success. That is the stage-link defect the Mac chain fixes with `dmsh_build.vs_pad` (331 of 9,043 pairs before it); `dmsv_pad.py` is the SPIR-V side, and padding 40 vertex shaders with 40 outputs closed all 56 |
| `VK_EXT_mesh_shader` | **present** — the 26 task/mesh programs are feasible on this GPU, so that gap is the host's, not the device's |
| `VK_EXT_fragment_shader_interlock` | **absent**, though all 7,301 pixel shaders declare `SPV_EXT_fragment_shader_interlock`; they compile without it, so only a shader that *uses* the capability would be refused |
| BC1–BC7 | sampled, filterable and blittable, which is what a Switch title's textures need |

```
aarch64-linux-android29-clang -O1 probes/vksh.c -o vksh -lvulkan
adb push vksh shaders.dmsv shader_pairs.tsv /data/local/tmp/mkw/ && adb shell /data/local/tmp/mkw/vksh shaders.dmsv --pairs shader_pairs.tsv
```

## The emulator side

`NamelessSaint8/mkwsw2` is Eglantine's `nx2` branch with Mario Kart World fixes on top (`mkw-eglantine`), and Eglantine keeps an Android frontend
(`src/android`, per-SoC presets in `CMakeLists.txt`) with `hesanaltdoesgithub/Eglantine`'s `nx2-android` branch building an APK. That path runs a title
on a phone as an emulator; this port's would run it natively. They share the shader tooling above and nothing else.

It is also the only host that executes a Switch 2 title today, which makes it the one way to ask what the port's fifth requirement costs in practice.
Measured on the same Y700 with the whole 22.9 GB dump in place (206,344 files), best run:

| | |
|---|---|
| memory layout | forced to 12 GiB by the emulator for any `0400…` program (`core.cpp`) |
| shaders lowered | 1,186 |
| pipelines | 201 graphics, 15 compute, 0 task/mesh |
| audio | ~45 s, at real time |
| then | no further progress, in one of two shapes: `VK_TIMEOUT` / `VK_ERROR_DEVICE_LOST` uncaught on the Vulkan worker thread, or a silent stop with every thread asleep after the last `nx2:gpu` submit |

The cause is memory, and the logs say so directly: `lowmemorykiller` logs continuous low-pressure events through the run, and the GPU waits then expire.

| | |
|---|---|
| guest (sizes its heap from the reported total) | ~9 GB |
| emulator overhead | ~1.0 GB |
| Android underneath | ~3.8 GB |
| host | 15.6 GB, ~15.2 GB usable |
| peak resident, 3× internal resolution | 10.81 GB, `MemFree` 16 MB |
| peak resident, 1× internal resolution | 9.79 GB, `MemFree` 33 MB |

So the arithmetic closes to ~13.8 of 15.2 GB, and the margin is spent by page cache: the title streams 22.9 GB of RomFS through the kernel while the
guest holds its heap. Dropping the internal resolution from 3× to 1× is worth about 1 GB and did not change the outcome alone.

Three things were ruled out rather than assumed:

- **the shaders**: the Khronos validation layer, enabled on the device for a full run, reported nothing about them — only pre-existing
  `vkCmdDrawIndexed` / `vkCmdEndQuery` misuse in the emulator itself;
- **a 16-bit storage-write path** the emulator takes on Qualcomm drivers, whose helper function it defined under a different condition than it called
  it (fixed; the stall reproduces with the retry loop removed, so it was not the cause);
- **a smaller reported total**: presented with 10 GiB, the title logs 62 `Unmapped InvalidateNCE … @ 0x0` straight after the Switch 2 `InfoType 33`
  queries and never reaches shader compilation. It sizes its heap from the total and then addresses memory that only the 12 GiB layout provides.

For this port that is the useful answer: the ~1 GB of emulator overhead is real, so a native host fits where this one does not, but it is small next to
a 9 GB guest — a 16 GB device stays marginal and a 24 GB one is comfortable. Two operational notes for reproducing it: a setting in Eglantine's
`config.ini` only takes effect when its companion `key\default` line is also flipped, and any rebuild of the shader translator moves the bundle
(`dmsh_chain.lock`).

## On the native host: where the port stands

The Mac host is built per profile — `make GAME=<id>` generates `game_profile.h` from `dm/games/<id>/game.tsv` — and a Switch 2 profile needs four keys a
split-only one does not carry: `mem_reserve`, `mem_alias`, `mem_stack`, `app_pool`. They are host address-space reservations rather than values the title
reports, so Mario Kart World's are first-pass numbers read off the 12 GiB layout: a 20 GB reserve (12 GiB plus the graphics server's 8 GiB), a 16 GB
alias, a 256 MB stack and a ~9.5 GiB application pool. Nothing has been measured against them yet; the profile says so where they are defined.

With them the port gets further than the shader tables alone suggested:

| | |
|---|---|
| `tools/patch_nso.py` | accepts all four Switch 2 NSOs unchanged — `main` 35,422 sites, 1.5 MB patch area; `sdk` 22,637; `subsdk0` 3,231; `subsdk1` 492 |
| loader | maps and relocates all four (`main`: 275,810 `relr`, 3,986 abs/glob, 1,220 jump; `sdk`: 922 symbols bound to `main`) |
| execution | `guest_main` runs and makes 33 supervisor calls, then faults |

```
CRASH sig=11 addr=0x2040 pc=sdk+0x158250 lr=sdk+0x15d8d4
bt: sdk+0x15f6f0  main+0x84a50  main+0x84988  guest_main+0x2e8  main+0x10c
```

The registers name the input rather than just the symptom: the guest registers a 54 MB range at guest address `0x2000` — `x1=0x2000`, `x2=0x35ff000`,
recorded as `{0x2000, 0x3601000}` through a global at `main+0x37790d0` — and the first store into it faults. The guest's own validation accepted the
pair (non-zero, page-aligned, slot free), so the base was read out of a structure as though it held an address. Its startup path asks for the range
through `main+0x84978`, which takes an out pointer and the 54 MB size.

Two hypotheses are excluded on the way to the real one. The rewriter's skipped `AllocateAddressRegion` alignment patch is a **version gap**, not an
oversight: the module is `nnSdk-Generic_21_4_0` (SDK 21) and that rule matches SDK 20's code shape. And no address region is allocated before the
fault. Naming the call sites resolves the rest, because each one is an import:

| | |
|---|---|
| `main+0x84978` | `nn::os::AllocateMemoryBlock(&block, 0x3600000)` — returned **`0x1000`** |
| `sdk` | a 24-byte trampoline through a pool pointer at `0xe25fa0` |
| `sdk` | `nn::os::detail::MemoryHeapManager::AllocateFromHeap(out, size)` |
| `main+0x84a10` | `nn::mem::StandardAllocator::Initialize(0x1000, 54 MB, false)` → registers `[0x2000, 0x3601000)` |

The base was not a Switch 2 unknown at all: **it was this profile's first-pass memory plan.** This host gives the heap whatever the reserve has left
after the alias region and the stack, and a 20 GB reserve left only 3.5 GB. The title's first `SetHeapSize` asks for `0x1fe400000` (8.16 GB), so it was
refused (`SetHeapSize OOM: req 0x1fe400000 > cap 0xe0000000`) — and with no heap the SDK's block allocator returns `0x1000` and the allocator's first
store faults. Sized to 25 GB, which leaves 8.5 GB of heap:

| | |
|---|---|
| `SetHeapSize` | accepted — `[mem] heap 7.97 GB (heap region 8.50 GB)` |
| first address region | `1 address regions live`, ending `+1.00 GB` into the 16 GB alias region |
| module initialisers | all of them — `main` 2,960 entries, `sdk` 88, `subsdk1` 4 |
| `nnMain` | **reached** |

Two things this measurement corrects, both of which this page asserted first: the crash was not a Switch 2 structure left unpopulated by the host, and
the numbers in a first-pass memory plan are load-bearing rather than provisional detail.

With the RomFS mounted as `DM_ROMFS` the run leaves the loader behind — 164 supervisor calls, guest threads, an NVN shader lookup — and then keeps going,
because the two things this page blamed next were both fixable:

| | |
|---|---|
| the shader cache the host asked for | it was never built, because `dmsh_build.py` opens `shader_map.tsv.conflicts.tsv` and digests it, so a profile without that table both fails and computes a different chain version than the header carries (`0bfb…` against `5f4f…`). With the empty table every profile from `scripts/build_ipa_from_nsp.py` gets, the Mac chain builds **11,577 of 11,603** — the 26 are the task/mesh programs, the same count the Android chain reaches — plus 7,213 alpha-test, 570 logic-operation and 3,485 pulling libraries, none failing to compile. The host then misses **no** shader, where it previously reported five on a single screen |
| `chat:u` | served by the host session mechanism, and its first command answered with an out object rather than zeros, which clears the null dereference in `nn::chat::detail::InitializeUserService` |

What stops it now is the port's own surface rather than plumbing:

```
0x6c1cb0  bl  _ZN2nn3gsv14GetUserSessionEv      ; nn::gsv::GetUserSession() → null
0x6c1cb8  bl  _ZN2nn2os12SdkMutexType4LockEv    ; Lock(null) → SIGSEGV, pc sdk+0x171ef8
```

`nn::gsv` is the Switch 2 graphics server. The call arrives from `nn::chat::gsv::GetMetadataStreamGeneration` on the guest's `Prepare Thread`, and the
session is null because the host has no `gsv` code at all and no `nx2:gsv` connect is ever attempted. That is requirement 1 of "what a port would still
need", met for the first time from the native side — and reading the SDK says what "providing it" means, which is not a service to answer:

- **there is no `nn::gsv::Initialize`.** gsv is *booted* — `BootWithTransferMemory(MemoryRegion, void*, size)` (`sdk+0x488580`) and
  `BootWithRemoteMemory(MemoryRegion)` (`sdk+0x4887a0`) — and neither is called anywhere in `sdk`, so on hardware the system has already booted the
  server before a title runs and the title only reads it back.
- The read-backs are three accessors over one static group: `IsInitialized` (`0x4889e0`) tests a bit at `0xee1048`;
  `GetGraphicsResourceUserId` (`0x4889f0`) returns the `u64` at `0xee1058`; `GetUserSession` (`0x488a00`) returns the static session at `0xee1050`
  **only while that same `u64` is non-zero**. So the session's layout is fixed by the caller: mutex at `+0`, an id at `+4` that must be non-zero, the
  resource user at `+8`.
- Chat's demand on it is concrete: `nn::chat::gsv::Initialize` (`0x6c0810`) is a one-shot (atomic flag at `0xfe8348`) that locks **its own** object
  (`this+0x218`), then locks the gsv session and feeds `session+4` to a generator — and it `AbortImpl`s on any error, so a missing session is fatal
  rather than degrading.

The host therefore supplies a booted session instead of booting one: a small host-side stand-in answers the three accessors from a block holding a
zeroed mutex, `id = 1` and `resource_user = 1`. With it the null dereference is gone and the run fails in a well-formed way instead:

```
game called nn::diag abort: Result 0x20, call site sdk+0x6c085c     ; nn::chat::gsv::Initialize's own error path
```

So the stand-in is accepted past the lock and past the `+4` read, and what is rejected lies further in — either the meaning of that id or the next call
(`0x6c1e30`, entered from `0x6c1d64` after a second `GetUserSession`). Worth stating plainly: this is a stand-in for the graphics server, not the
server. NVN2 submits through gsv, so the real requirement stands — `BootWithRemoteMemory` taking a `MemoryRegion` is the shape of the thing that will
have to exist before the title draws.


Two things worth recording about the order of events, because they bound the work. The graphics stack is fully up *before* `chat:u` is contacted:
`vi` vsync at 60 Hz, the `nvn-mtl` window with `present tick 60 Hz` and the present-thread time-constraint policy, the 11,603-entry shader map with a
background prefetch, a run of texture uploads, 20 live address regions, and the guest's own `Prepare Thread` and `Presentation Thread`. So the renderer is
complete and idle when the run dies — but no frame has been presented, and the presentation thread is parked, not running.

There is also one latent defect this pass surfaced and did not chase: the Mac chain prints `Attribute offset 0x5C is not valid` across 2,838 of those
shaders. They translate and load, so it will show up as wrong geometry rather than as a crash, and it is the first thing to check when rendering starts.

### The syscall behind the abort: svc 0x21

The abort above is not the graphics server refusing something; it is a **syscall** the host answers with a placeholder. Following it out:

- `sdk+0x6c1c90` loads a value out of the gsv session (`+4`) and hands it to a bare `svc #0x21` trampoline (`0x1a4500`), then reads its result from
  `tpidrro_el0 + 8` rather than from the syscall's return.
- That word is why the abort read `Result 0x20`: the SDK writes `0x20` into the thread-local region (`0x6c1ea4`) and later treats it as the outcome.
  Reading an abort code without following which register produced it is how a status word gets mistaken for a message.
- `0x21` is `SendSyncRequest`. The SDK's own wrapper settles it: `nn::sf::hipc::SendSyncRequest(handle, msg, size)` compares `msg` against
  `tpidrro_el0` and calls `0x21` when they match, `0x22` (with the buffer) when they do not. `hle_svc.c` implements
  `0x01–0x06, 0x1E, 0x26, 0x27, 0x29, 0x2C, 0x2D` — no `0x21` — so it fell through to `(placeholder returns success)`.

Wiring `0x21` into the service handler (with the gsv session's `+4` minted as a real host session) disproved the buffer assumption rather than fixing it:

```
[RED] sf: gsv:u: HIPC message type 1217 not served
[RED] svc 0x21 on handle 0xd0001 -> 0xe401
```

`1217` is `0x4c1`, chat's own tag word at `tls[0]`. So the thread-local region carries the thread's **state**, not an IPC message, and the SDK's
`msg == tpidrro_el0` comparison only says which syscall its API wrapper picks.

One region further settles it the same way. At the syscall, `tls[0..0x7f]` is the tag followed by zeros, and `tls+0x100` is 16 zeros, a single `'S'` at
`+0x110`, then zeros again — no `SFCI` request and no CMIF header anywhere the host could parse. `0x6c1c90` shows why: it writes a state tag
(`0x4c1`, and after the call `0x4c1 | 1<<32`) at `tls[0]`, passes the session's `+4` field to the syscall, and reads the outcome back from `tls[8]` —
the same slot whose `0x20` was mistaken for the abort's message. Two of the three slots are bookkeeping; the region itself is the kernel's message buffer,
which simply holds no message.

The `'S'` that looked like the discriminator is not one, and the search for its writer ends in this host rather than in the guest: `dm/host/thread.c`'s
`guest_thread_set_id` stores the 32-bit thread id at `tlr + 0x110`, and Mario Kart World's `Prepare Thread` is thread 83 — `0x53`, which is `'S'` by
coincidence. The region is the guest's own TLRegion (state tag at `[0]`, outcome at `[8]`) plus host bookkeeping at `+0x110` (thread id) and `+0x1f8`
(thread object).

### Where `svc 0x21` gets its message

Eglantine is an Atmosphère-lineage kernel, so this is answerable by reading it rather than probing: `SvcId::SendSyncRequest = 0x21`
(`src/core/hle/kernel/svc.h`), dispatched in `svc.cpp`, implemented in `svc/svc_ipc.cpp`. `SendSyncRequest(handle)` passes `message = 0, size = 0`, and
the kernel then substitutes the **thread's local region** as the message buffer — `CleanupServerHandles`, `ReceiveMessage` and `SendMessage` all do
`msg_ptr = GetPointer(tls)`, `buffer_size = MessageBufferSize` when no buffer is given. That is also why the SDK's wrapper compares `msg` against
`tpidrro_el0`: passing the TLS pointer is how a caller asks for the kernel's buffer.

So chat's call *does* name a buffer, and it is the thread-local region — which is why looking 0x100 past it found nothing. What is missing there is the
**message**: at the syscall the region holds chat's tag `0x4c1` and zeros, because the step that would build a request (`0x6c1a50`, which asks for a
readable handle and receives 0) has nothing to build one from. No gsv, no handle, no request — and the SDK then reads its own `0x20` status back as the
result and aborts.

One layout note from the same source: `k_process.cpp` writes the **thread handle** at `tls + 0x110`, the slot this host fills with an ordinal thread id.
Same slot, different content — worth remembering for anything that reads it back.

### A frame

Four faults stood between the frontier above and a presented frame. Each was named from the guest's own code, and only the first is a stand-in:

| | |
|---|---|
| `nn::camera::Initialize` aborts with `Result 0xe401` at `main+0xcded98` | the request comes from `main+0x1c6d430`, a 12-word `SFCI` message whose session handle the caller reads out of its client object at `+4` (`ldr w23, [x0, #4]`) — and that word is `1`, a handle the host never minted (`hle_sf.c` issues `0xd0000+`). Its origin is not in any log; the sf layer now answers such a handle as a session of its own (`svc:0x1`) instead of refusing it |
| gsv's session, used through `svc 0x21` | `GetUserSession` hands out a block whose `+4` the SDK passes to the syscall; as the integer `1` it named no session. It is minted as a host session now, so the same field serves both readers |
| `CRASH sig=11 addr=0 pc=0 lr=main+0x959ae8`, frame 106 | `main+0x959ae4` calls `nn::vi::SetLayerNextHdrAdjustableBezierMetadata` through a PLT stub whose GOT slot holds `0`: the import is undefined **and strong**, and the loader bound it to 0 without a word. A void stub answers it — the host has one layer and no display manager — and the loader now prints every strong import it binds to 0, because finding that null jump cost far more than the line costs to print |
| `[nvn-mtl] FATAL submit re-entered` | `submit_now` unlocked `g_sub_mu` and never locked it: the lock was dropped in `02e336f0` while the unlock stayed, so the title's render and prepare threads replayed into one command buffer. Holding it for the whole submission is the order the comment above that mutex already claimed is valid |

With those, the title presents:

| | |
|---|---|
| swap chain | `WindowInitialize swap chain 3 textures, interval 1, first 3840x2160 format 0x25` |
| window crop | `WindowCrop 0,0 2560x1440`, then `0,0 2048x1152` — the picture the title presents is smaller than the swap chain, and scaling it up is the **system's** job, which the host's present pass does (`present_viewport` letterboxes the crop onto the canvas) |
| frames | 300 presented before the host's own memory watchdog stopped the run: `resident 37382 MB, GPU allocated 38440 MB` against a 24 GB guard. Steady frames are 25–50 ms with 12 ms of GPU; 87 of the 300 were long, up to 11 s, all of them pipeline compiles for pairs the boot prebuild had not built |
| the picture | a full-frame, correctly exposed render — 10.7 k distinct colours in a 160×90 sample, mean luma 103 — not a clear colour or a partial blit |

The 300 frames above are this host's guard, not the title's limit. With `DM_MEM_CAP_GB=48` the same dump ran to **frame 1585 in 414 s** with no
watchdog message and no crash, and the footprint it holds is a working set rather than a leak:

| frames | resident | GPU allocated | residency set |
|---|---|---|---|
| 300 | 39,169 MB | 38,357 MB | 2659 |
| 600 | 39,483 MB | 38,553 MB | 3455 |
| 1200 | 40,139 MB | 38,884 MB | 4756 |
| 1500 | 40,485 MB | 38,977 MB | 4982 |

~40.5 GB with 8 GB of the cap left, but it does creep: 1.3 GB over 1,200 frames while the residency set grows by 2,300 objects, which is slow enough to be
worth a longer run before calling it steady. The frame-time floor there was 20.8 ms.

Two things this measurement corrects. A screenshot taken without `DM_NVN_SHOT_OUT` saves the **raw swap chain**, where the 2048×1152 crop sits in the top-left corner of a black 3840×2160 frame; that is what the present pass is for, and reading it as the presented picture would have sent the next hour into the wrong subsystem. And the remaining `[RED] failed to create compute pipeline: Threadgroup memory size (49152) exceeds the maximum threadgroup memory allowed (32768)` is a real ceiling rather than noise: Apple GPUs cap threadgroup memory at 32 KB, and some of this title's compute passes ask for 48 KB. Those passes are what stands between "a frame" and "a correct frame". The 24 GB guard is a default for hosts where runaway memory once panicked the machine, and on
this 64 GB Mac it was silently bounding a title that needs about 40 GB -- the wall read as a rendering failure at frame 300.

### Where the 40 GB goes

The footprint above is this host's, not the title's: the guest maps **0.98 GB** of address regions while Metal holds **37.4 GB**. `DM_NVN_ALLOCPROF=1` was extended to
answer the second half of that question -- a census of the residency set plus the guest's own description of any very large texture:

```
residency census: resident set 33.4 GB of 37.4 GB -- 1598 textures 30.1 GB, 1105 buffers 3.3 GB, 0 other 0.0 GB;
  largest textures: 8192x8192x1 fmt 151 x68 mips12 s1 (5803 MB), ... (5803 MB), ... (5803 MB)
big texture: guest 8192x8192x68 levels 12 target 4 fmt 0x8e → Metal 8192x8192x1 mips 12 array 68 fmt 194 1451 MB (ser 31607) standalone
```

Two textures of that shape, and both are the title's own:

| guest format | Metal | size |
|---|---|---|
| `0x8E` ASTC 8x8 sRGB | `ASTC_8x8_sRGB` | **1451 MB** |
| `0x4F` BC6H | `BC6H_RGBUfloat` | **5803 MB** |

The second is 4x the first because BC6H is a byte per texel where ASTC 8x8 is a quarter of one -- that is the guest's own format, not a rewrite of it, and the first reading of these
numbers (an upload path densifying an ASTC texture) was wrong. What was actually wrong is **how many copies of it the host kept**: a streamed texture is re-uploaded into a new
Metal texture and the one it replaced is kept as a *spare* so a submission still reading the old content does not wait -- so the array, its spare and the copy still retiring were
three of it, 17.4 GB of a 33.4 GB resident set. Past 512 MB the replaced texture is retired on its fence instead, which took the frame-300 footprint from **37.1 GB to 30.9 GB**
with no crash and no change to the picture.

Two costs remain, both visible in the same log:

How much of it is even there settled the next step. `nvn_sparse_copy` already returned the bytes it could not map; logging that number (`36f3ea7c`) says:

| array | storage | unmapped | mapped |
|---|---|---|---|
| BC6H 8192x8192x68 | 5805 MB | 5292 MB | **9%** |
| ASTC 8x8 sRGB, two of them | 1453 MB each | 1323 / 1407 MB | **2-9%** |

So a dense upload gathered and uploaded about five times the content the title had, and the gather itself -- `malloc` plus a zero-filling copy -- dirtied every byte of it:
5.3 GB of zeros written per upload. The buffer now comes from a fresh anonymous mapping, which reads 0 without committing anything, and unmapped runs are left alone
(`nvn_sparse_copy_zeroed`, `81e2bc61`):

| frame 300 | before | after |
|---|---|---|
| resident | 30,907 MB | 28,829 MB |
| GPU allocated | 29,654 MB | 29,552 MB |
| rate | 3,296 frames in 178 s | 6,356 frames in 166 s |

The zeros were memory traffic as well as memory, which is why the run nearly doubled. What remains is one full-size Metal staging buffer per upload (line 2436, 5.8 GB while an
upload of that array runs) and the dense materialisation itself: the array is **sparse** on the console, only mapped pages are paid for, and a dense 5.8 GB texture for a 9% mapping
is the difference between this host's ~29 GB and the console's budget. Metal's own answer to that is sparse heaps, not a smaller format.

### Sparse textures are not available, so the arrays are dense

If the arrays are 2-9% mapped, the obvious question is whether Metal can hold them sparsely. `tools/mtl_sparse_probe.m` answers it on this machine (Apple M4 Max, macOS 26):

| | |
|---|---|
| per-format sparse tile size | reported for every format, including `BC6H_RGBUfloat` (16 KB) and `ASTC_8x8_sRGB` (64 KB) |
| `MTLHeapTypeSparse` heap | created only with an explicit size; then `newTextureWithDescriptor:offset:` returns **nil** for every format, a 512x512 BGRA8 control included -- so it is the path, not the format or the size |
| `MTLHeapTypePlacement` + `placementSparsePageSize` | the heap and the texture are created, for the exact shapes this title uses, but the texture is **not** sparse: `isSparse` is false, `sparseTextureTier` is `None`, `updateTextureMapping:` does not exist, and `allocatedSize` is the whole dense size (5803 MB for the BC6H array, 1451 MB for the ASTC 8x8 one) |

So a texture of that shape costs its dense size on this GPU, whatever the title has mapped: the 29 GB is 5.8 GB + 5.8 GB of one array plus the rest, and no Metal API turns it into 9%. The alternatives are structural rather than a format or hint -- allocate one texture per layer and only the mapped ones, with the translated shaders sampling through a table instead of a layer index, which is a shader-translation project rather than a fix.

Recorded because it rules out a whole direction cheaply: a `MTLHeapTypeSparse` heap that creates fine and then refuses to place a texture is easy to read as a wrong descriptor and spend a day on.

### The 48 KB compute kernels are one threadgroup each

The compute pipelines Apple refuses are uniform: of Mario Kart World's 729 compute kernels, 251 declare threadgroup arrays and **168 declare exactly 49152 B** --
`threadgroup spvUnsafeArray<uint, 12288> _37;`, the array SPIRV-Cross emits for a workgroup buffer. Apple's limit is 32768 B, so they never create, and every dispatch of them
is retried (12,309 attempts in one 130 s run). None of the 168 touches `.elements`, and the indices are data-dependent (`_37[int(_676)]`), so the array cannot be shrunk on
inspection.

What makes this fixable rather than a project is the dispatch shape: with the refusal path naming its program and grid (`a92` above), **every one of them is grid 1x1x1** --
one threadgroup per dispatch. So the array can be spilled to an ordinary device buffer with no per-group indexing at all: a 48 KB scratch buffer per dispatch, bound as an
extra buffer argument, with `threadgroup spvUnsafeArray<T, N> x;` rewritten to `device spvUnsafeArray<T, N>* x [[buffer(K)]]` (the type is kept, so `x[i]` still means what it
meant). A dispatch in flight could overlap the next, so the host wants a small ring of these buffers rather than one.

That is the next piece of work: the rewrite in `dm/gfx/tools/dmsh_build.py`, the binding and ring in `nvn_mtl.m`'s dispatch path, and the 168 kernels as the test.

The rewrite was compiled before any of it was built into the tool. On one of the 168 (`7caf175d0e2ada58_b.metal`, kernel `main0`), in `.gamedump/MarioKartWorld/spike/`, the
declaration `threadgroup spvUnsafeArray<uint, 12288> _37;` is dropped and the kernel gains one parameter:

```metal
kernel void main0(constant spvDescriptorSetBuffer0& spvDescriptorSet0 [[buffer(0)]], uint3 gl_WorkGroupID [[threadgroup_position_in_grid]],
                  uint3 gl_LocalInvocationID [[thread_position_in_threadgroup]],
                  device spvUnsafeArray<uint, 12288>& _37 [[buffer(30)]])
```

`xcrun metal -std=metal3.0 -c` accepts it (10,464 bytes of air against the original's 10,240, and no threadgroup memory left), and two shapes that look natural do **not** work:

- a **pointer** (`device spvUnsafeArray<...>* _37`) fails at the first store -- `_37[i]` becomes pointer arithmetic on whole arrays, and the prelude's assignment operator is address-space qualified;
- index **31** is refused by the compiler itself: a kernel's `[[buffer(n)]]` must be 0..30 here, and only 0 is in use (the argument buffer), so 30 is free.

That is the shape to build into `dmsh_build.py`: rewrite the declaration to that reference parameter, record the byte count in the shader's metadata, bind a ring of 48 KB buffers
at argument-table index 30 in the dispatch path, and take the 168 kernels as the acceptance test. Changing the translator changes the chain version, so this costs one full
retranslation of the 11,603 shaders and a new `b-<chain>` directory.

Built and run: **zero refusals**.

| | before | after |
|---|---|---|
| `failed to create compute pipeline` | 12,309 in 130 s | **0** |
| shaders in the library | 11,577 | 11,577 (168 with `tg_spill`) |
| shader load misses | 95 | 93 |
| frames | 6,356 in 166 s | 2,853 in 156 s |

The retranslation needed the game's own carriers, which had to be rebuilt first: `shader_split.py <romfs> <exefs/main> <package> ...` over Mario Kart World's dump
produced 11,603 shaders (729 compute, matching the census) and 14 carrier files in `.gamedump/MarioKartWorld/shader/`, which is the directory `dmsh_build.py` wants as its
package argument. With it the chain `e768d85cea2b` built completely -- 11,577 metallibs, the same count as before -- and 168 of the reflection files carry `tg_spill`,
exactly the kernels that used to be refused.

The superseded chain `b-5f4fb6fce881` (1.5 GB) was deleted once the new one was verified, as its cache is keyed by a version nothing looks for any more.

### What the 0x5C warning is not

`translator 2838 in 2838 shaders Attribute offset 0x5C is not valid.` is Metal's own warning text, counted by the build like the threadgroup one. The obvious reading --
that NVN attribute *byte offsets* are being used as Metal attribute *indices*, and 92 is out of range -- is **wrong**: the generated MSL uses `[[attribute(0)]]` through
`[[attribute(8)]]` and nothing above 31 anywhere in the 11,577 shaders.

So the offset Metal is rejecting belongs to a *byte* layout, which points at the vertex layout the host builds for a draw (a stride/offset beyond the buffer), not at the
translated shader. That matters because it is the leading suspect for the picture: models black, sky pieces missing, with only 93 shader-load misses in the log -- a silent
defect, exactly what bad vertex offsets look like.

Next probe: take a draw whose shader warns, log the vertex layout the host constructs for it beside the guest's own attribute table (offset, stride, format), and compare.

Follow-up attempts, all negative, narrowing where the warning can come from:

| tried | result |
|---|---|
| attribute indices above 31 in the MSL | none -- the library uses `[[attribute(0)]]`..`[[attribute(8)]]` |
| `xcrun metal -std=metal3.0 -c` on 400 shaders | no warning |
| `xcrun metal -c -O1 -fpreserve-invariance` (the build's own flags) on 120 vertex shaders | no warning |
| `metal -c` then `metallib` on 60 vertex shaders | no warning |
| the phrase in any file of the tree, including the vendored spirv-cross and its binary | only in `dist/`'s copy of vendored Ryujinx sources, never in live code |

So the text is neither ours nor reproduced by the toolchain on an arbitrary shader: it comes from the build path itself, for a subset of shaders the alphabetical sample missed. The next
attempt should not guess a subset -- run `dmsh_build.py` with a single shader key (`<package> <cache> <key>`) for a shader that warns, and capture the exact tool invocation and its
stderr. The build already knows which keys they are; the summary only prints the count.

Located. The text is Ryujinx's, not Metal's -- `third_party/ryujinx/src/Ryujinx.Graphics.Shader/Instructions/AttributeMap.cs`:

```csharp
if (!(isPerPatch ? _attributesPerPatch : _attributes).TryGetValue(offset, out AttributeEntry entry))
{
    context.TranslatorContext.GpuAccessor.Log($"Attribute offset 0x{offset:X} is not valid.");
    return Const(0);          // the load becomes a literal zero
}
```

So in 2,838 shaders the machine code loads a vertex attribute at byte offset **0x5C that the translator's attribute map has no entry for**, and gets 0 back with no
error. That is the shape of the picture: a component read as zero rather than a draw failing, so nothing reports it.

`tools/shader_notes.py` now lists the keys behind a note (read from the built reflections, so it never costs a retranslation):

```
11577 shaders in .../b-e768d85cea2b
  2838  Attribute offset 0x5C is not valid.
        keys: 0058e86e0e243199_b 007fd1f61fa16b45_b ...
```

The first of them, `0058e86e0e243199_b`, is a **vertex** shader whose recorded inputs are locations 1, 2, 3 and 5 -- so the map it was built from is sparse, and the
question is now narrow: why its attribute table omits 0x5C when the code reads it. Compare that shader's declared table (the SPH attribute list the translator reads)
against the offsets its code loads.
