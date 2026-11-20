---
status: verifying
trigger: "now fix the audio please (Persona 4 Golden on Android: audio crackles because too few audio blocks reach the device in the foreground)"
created: 2026-11-18
updated: 2026-11-18
---

## Current Focus

hypothesis: confirmed by measurement (see Resolution.root_cause); the fix's device measurement is still needed.
test: Install the paced debug APK, then cold-launch with DM_AUDIO_LOG=1 several times until a Path A launch (fast track refused at open, 20 ms wakes) is logged, and read blocks/s, underruns, ms padded, and the paced line's device-short frames for t=15-40 s in the opening credits. Then the same with DM_AUDIO_PACE=0.
expecting: Paced, Path A: 200 blocks/s, underruns near 0, 0 device-short frames after start-up. DM_AUDIO_PACE=0, Path A: about 150 blocks/s and 25% padding again.
next_action: CHECKPOINT: ask the user to approve installing .gamedump/Persona4Golden/Persona4Golden.apk (11,881,122 bytes, sha256 cb0b6ec151283ad5...) as org.nx2a.p4g.test on HA2M2W71 with `porter install` (no uninstall).

## Symptoms

expected: Clean continuous sound in the foreground: the device drains 200 blocks/s and 200 blocks/s arrive, with underruns near 0.
actual: Audible crackle. In the foreground about 153 blocks/s arrive against 200 needed, so about 25% of the output is zero padding.
errors: No crash and no [RED] line. The evidence is the `device callbacks` log line from DM_AUDIO_LOG=1. `underruns` is counted per 128/112-frame chunk, so about 1000 "underruns" is about 500 silent callbacks.
timeline: Present since the game first ran on Android (2026-11-03 or earlier). Commit 1f66e03c made an 80 ms ring the default for all titles with only compile verification, and the Qwen notes say it had no effect.
reproduction: Launch org.nx2a.p4g.test on the Legion Y700 with DM_AUDIO_LOG=1 in the data folder's env.txt, stay in the foreground at the title or in a loaded scene, read log.txt.

## Environment and rules

- Device: Lenovo Legion Y700 TB323FU, serial HA2M2W71, Adreno 840, Android 16. Package org.nx2a.p4g.test only, data under /sdcard/Android/data/org.nx2a.p4g.test/files. Installed versionCode 65537, debug build, so DM_CTL and ctl.txt work when DM_CTL is set.
- adb: `adb` from ~/Library/Android/sdk/platform-tools if it is not on PATH. NDK: $HOME/Library/Android/sdk/ndk/27.2.12479018.
- Game folder: .gamedump/Persona4Golden (never print keys, never copy game files into the repo or chat).
- Port command and its output: scratchpad /private/tmp/claude-501/-Volumes-Data-Dev-nxhost/d441efc6-415b-44b7-b67f-33e41d93597a/scratchpad/p4g-port.log and p4g-install.log. Device helpers there: step.sh, title.py.
- Backups: .gamedump/Persona4Golden/save-backup-20261118.tar. env.txt must end the session byte-equal to the pack's .gamedump/Persona4Golden/Persona4Golden-data/env.txt (header comment plus DM_LANG, DM_SHARED_FONT, DM_SHARED_FONT_EXT, DM_ROMFS; 5 lines, 362 bytes, no DM_CTL), and ctl.txt must be empty. (Corrected 2026-11-18: env-before-20261118.txt was taken after debug switches were added, so it has 9 lines and is not the restore target.) Keep the 17:11 APK in the scratchpad audio/ folder for rollback.
- Never uninstall: the save is in the app's private storage. `porter install` will not downgrade.
- Never save in the game, and never press confirm blindly in the user's save. If the screen shows the user is using the tablet, stop and ask.
- Ask the user before installing a new build. Name the package and the APK size.
- Do not commit, stage or push anything.
- nxnative/dm/host/hle_audren.c, nxnative/docs/reference/audio.md and the gfx_vk files hold unrelated uncommitted Ocarina work. Do not revert or reformat it. Prefer fixing in nxnative/dm/android/ (compat/audiotoolbox_aaudio.c) and keep changes to nxnative/dm/host small and guarded.
- The fix must be general: no title IDs, game names or per-game branches in core code (tests/arch_rules.py). A per-game value goes in the profile's android.tsv `env` key only if the semantics really are per-game.
- Tests: QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover tests. Android compile check: nxnative/dm/android/build.py --game 010062B01525C000 --ndk <ndk> --out <scratch> --only-compile.

## Eliminated

- hypothesis: The guest audio mixer is too slow to produce 200 blocks/s.
  evidence: Under the silent sink in the background it produced 200/s, and after a long background and resume it ran 200/s with 0 underruns in the one full logged window.
  timestamp: 2026-11-18

- hypothesis: The data callback length (DM_AUDIO_CALLBACK) or the device buffer (DM_AUDIO_BUFFER) sets the shortfall.
  evidence: cb480, cb120 and buf1920 on Path A stay at 150-151 blocks/s; buf480's 196/s came from the -899 fallback to performance mode NONE (logcat), not from the buffer.
  timestamp: 2026-11-18

- hypothesis: The 80 ms host ring (DM_AUDIO_RING_MS) is involved.
  evidence: ring0 on Path A: 150.2 blocks/s, the same as with the ring.
  timestamp: 2026-11-18

- hypothesis: Frame load in the foreground slows the guest mixer.
  evidence: The silent sink in the foreground, same movie, game rendering: 200.0 blocks/s in 25 of 25 windows.
  timestamp: 2026-11-18

## Evidence

- timestamp: 2026-11-18
  checked: Earlier device runs in this session's work, foreground.
  found: About 153 blocks/s against 200 needed, about 25% zero padding.
  implication: The shortfall depends on the foreground stream, not on guest speed.

- timestamp: 2026-11-18
  checked: nxnative/dm/android/compat/audiotoolbox_aaudio.c comments near lines 52 and 86-136.
  found: HOLD_MAX_S=60 ends a stream after a long stop, and the next start opens a new one. Comments record Unicorn Overlord's CRI output going short in every other callback for good (998 underruns of 2000, 25% zero padding) where a new stream had none. They also credit Persona 4 Golden's 6-channel CRI output with arriving about two blocks at a time, and offer DM_AUDIO_CALLBACK=<frames> and DM_AUDIO_BUFFER=<frames>. DM_AUDIO_PERF=none forces the normal path.
  implication: The same 25% signature was seen in another CRI title, and switches for the first tests already exist. Treat the comments as leads and confirm them with measurements.

- timestamp: 2026-11-18
  checked: ~/.qwen/projects/-Volumes-Data-Dev-nx2android/memory/project/p4g-audio-underruns-on-both-present-paths.md exists.
  found: Older notes; some of their conclusions (a too-slow guest mixer) were overturned by the evidence above.
  implication: Read them for leads only.

- timestamp: 2026-11-18
  checked: env.txt on the device at the start of this continuation against .gamedump/Persona4Golden/env-before-20261118.txt.
  found: The device has 5 lines, 362 bytes, no DM_CTL (saved as scratchpad audio/env-found-at-start.txt, sha256 278e44d9...). The backup file has 9 lines, 507 bytes, and adds DM_CTL, DM_AUDIO_LOG=1, DM_VK_TEXLOG=all, DM_ROOT. The session notes call the backup "5 lines, no DM_CTL", which it is not.
  implication: "equal to the backup" and "5 lines, no DM_CTL" cannot both hold at restore. Must be reported to the user at the end.

- timestamp: 2026-11-18
  checked: Foreground A/B, cold launch of installed build (versionCode 65537), no input, opening credits movie, env = device's 5 lines + DM_AUDIO_LOG=1 + the switch named. Window t=15-40 s after the first append. Raw logs in scratchpad audio/runs/<name>.
  found: |
    base1 (no switch, low latency requested): 153.8 blocks/s, 51 guest wakes/s, 3.0 blocks per wake; 976-998 underruns per 2000 callbacks, 2440-2495 ms zero padded per 2000 (25%). logcat: "flags changed 0x104 to 0", "perfMode changed from 12 to 10", frameCount 960, so the fast track is REFUSED and it is a normal mixer track. AudioTrack thread wakes 60-68/s, gap p50 18-20 ms.
    perfnone (DM_AUDIO_PERF=none): 195.1 blocks/s, 92 wakes/s, 2.11 blocks/wake; 86-202 underruns per 2000, 215-505 ms per 2000. AudioTrack thread wakes 156/s, gap p50 8.3 ms. Same 960-frame normal track.
    silent (DM_AUDIO=0, silent sink, foreground, same movie): 200.0 blocks/s, 141 wakes/s, 1.42 blocks/wake.
    ring0 (DM_AUDIO_RING_MS=0): 150.2 blocks/s, 57 wakes/s; 992-1000 underruns per 2000. Wake gap p50 19.9 ms.
  implication: The guest makes 200 blocks/s in the foreground with the game rendering when it is released on an even 5 ms clock, so neither guest speed nor frame load is the limit. The shortfall follows the device callback cadence: a track whose low-latency request was refused is woken about every 20 ms and gets about 3 blocks per wake. The ring is not the cause and does not help.

- timestamp: 2026-11-18
  checked: DM_AUDIO_CALLBACK / DM_AUDIO_BUFFER A/Bs, same scene and window (t=15-40 s), env = device's 5 lines + DM_AUDIO_LOG=1 + switch. logcat of each run for the stream path.
  found: |
    cb480 (DM_AUDIO_CALLBACK=480): 150.8 blocks/s, 5841 underruns of 4000 callbacks, 9735 ms padded. Fast track refused at open; AudioTrack gap p50 20.0 ms.
    cb120 (DM_AUDIO_CALLBACK=120): 150.2 blocks/s, 3913 underruns of 16000, 9782 ms. Refused at open; gap p50 19.8 ms.
    buf1920 (DM_AUDIO_BUFFER=1920): 150.2 blocks/s, 3934 of 8000, 9835 ms. Refused at open; gap p50 20.0 ms.
    buf480 (DM_AUDIO_BUFFER=480): 195.9 blocks/s, 458 of 8000, 1145 ms. NOT a buffer effect: logcat shows the MMAP stream opened, requestStart returned -899, and the code's fallback reopened it with performance mode NONE. Gap p50 8.6 ms.
    none_buf480: 196.1 blocks/s, 460 of 8000, 1150 ms. none_buf1920: 195.1 blocks/s, 336 of 8000, 840 ms. Gap p50 8.6-8.9 ms.
  implication: Callback length and buffer size do not move the rate. Only the stream path does.

- timestamp: 2026-11-18
  checked: Three cold launches with logcat of the open sequence, and the audio stream after a 75 s background (run bg75).
  found: |
    The same build and env reach three different streams, and the launch path varies from run to run:
    Path A, low latency refused at open (MMAP openMmapStream status -19, AudioTrack "flags changed 0x104 to 0", perfMode 12 to 10): callback thread wakes about every 20 ms. 153.8 blocks/s, 25% padded (base1, ring0, cb480, cb120, buf1920, launches 2 and 3).
    Path B, MMAP opens but requestStart returns -899 ("stream was probably stolen"), fallback opens performance mode NONE; or DM_AUDIO_PERF=none: wakes about every 8-10 ms. 200 blocks/s most of the time with a dip to about 154 for 1-3 s every 9 s; 86-200 underruns per 2000 (perfnone, buf480, bg75's first stream, launch 1).
    Path C, MMAP stream started (AudioStreamInternal, thread AAudio_1), reached after a background over 60 s: bg75 after return: 200 blocks/s, 3.0 blocks queued, 0 underruns and 0.0 ms padded in 3 of 3 windows of 2000 callbacks.
  implication: The rate follows the cadence at which the device asks for audio. 5 ms even (silent sink, MMAP) gives 200/s; 10 ms gives about 195/s with periodic dips; 20 ms gives about 150/s, which is 3 blocks per 20 ms. The earlier reading "the first stream is bad, a new one is good" is really "MMAP was refused at launch and granted at resume".

- timestamp: 2026-11-18
  checked: Second background run (bg70b, 70 s away).
  found: The log has no "audio suspended" line and restarts at t=0: the process did not survive the background, so `am start` was a cold launch, which took Path A again (150.2 blocks/s, 3928 underruns of 8000). MMAP callback cadence was therefore NOT sampled directly.
  implication: Path C's even 5 ms cadence is inferred from its 200/s and 0 underruns, not measured. The fix does not depend on it, because it only acts on streams that are not low latency.

- timestamp: 2026-11-18
  checked: Fix built. tests/test_audio_pace.py, full suite, Android compile, `porter port --debug --package org.nx2a.p4g.test` (no install).
  found: Test OK; 500 tests OK; 267 sources compiled, 0 failed; APK 11,881,122 bytes, libdmhost.so contains "dm-audio-pace" and DM_AUDIO_PACE. Rewrite, shader split and Vulkan shaders were reused, so the data pack is unchanged. The APK also carries working-tree changes made after the installed 17:11 build: gfx_vk_exec.c, gfx/nvn/dmsh_chain.h, the untracked gfx_vk_mesh_trace.inc. The 17:11 APK is kept as scratchpad audio/Persona4Golden-installed-17-11.apk.
  implication: Ready for the device. The other changes are not mine and could affect rendering.

- timestamp: 2026-11-18
  checked: Device state before the install checkpoint.
  found: App force-stopped (pidof empty). env.txt byte-equal to the state found at the start of this continuation (5 lines, 362 bytes, no DM_CTL); NOT equal to env-before-20261118.txt, which has 9 lines (adds DM_CTL, DM_AUDIO_LOG=1, DM_VK_TEXLOG=all, DM_ROOT). ctl.txt 0 bytes. Saves pulled with run-as (files/save, files/save.work, 16 entries) match save-backup-20261118.tar (diff -r: no differences). Installed APK still the 17:11 build (versionCode 65537). No game input was sent in this continuation; the only key was one HOME press in each background run.
  implication: The device is as found. Which env.txt the user wants at the end is an open question.

## Resolution

root_cause: Two conditions together. (1) nxnative/dm/host/hle_audio.c releases the guest's audio blocks only from the device callback. (2) On this tablet Android refuses the MMAP low-latency stream at launch (openMmapStream -19 or start -898), so the output is a normal-mixer AudioTrack whose callbacks arrive in bursts about 20 ms apart. The guest refills only what was released, about 3 blocks per burst, so 150 of 200 blocks/s arrive and 25% of the output is zero padding.
fix: nxnative/dm/android/compat/audiotoolbox_aaudio.c: a stream whose performance mode is not low latency is fed by a render thread (dm-audio-pace) that calls the unit's render callback one block (240 frames, 5 ms) per block period into a ring the AAudio data callback reads; two blocks per tick under a low mark (3 blocks), none when the ring is at its cap (burst + 3 blocks + burst + 2 blocks), so a stalled device still stops the render callbacks for the host watchdog. Playing starts at burst + 3 blocks queued, and a short read queues that margin again. Low-latency streams (MMAP, fast tracks) stay direct. DM_AUDIO_PACE=0 turns it off for A/B in the same build. With DM_AUDIO_LOG=1 a line every 10 s gives the frames short at the device.
verification:
  target_test:        { result: pass, test: "tests/test_audio_pace.py Pace.test_bursts (host cc; 20/10/5/40 ms bursts, drift, stall, block-rule boundaries)" }
  mutation_check:     { result: pass, reason: "no Stryker for C; manual mutants of pace_blocks (always 1, always 2, no cap) and pace_limits (begin without burst, cap = begin) each fail the test by assertion" }
  no_op_deletion:     { result: pass, note: "92 insertions, 4 deletions, all additive; no behaviour removed" }
  adjacent_tests:     { result: pass, suites_run: ["python -m unittest discover tests: 500 tests OK", "build.py --only-compile: 267 sources, 0 failed"] }
  revert_and_reconfirm: { result: pending, plan: "on the device, same build: DM_AUDIO_PACE=0 must bring back about 150 blocks/s on a Path A launch, and the default must give 200" }
  device_check:       { result: pending, reason: "installing needs the user's approval" }
  guardrail_verdict:  pending
files_changed: [nxnative/dm/android/compat/audiotoolbox_aaudio.c, tests/test_audio_pace.py, .claude/skills/switch-android-port/references/switches.md]
