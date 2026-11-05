---
id: SEED-261031-oe1
status: dormant
planted: 2026-10-31
planted_during: GUI rework milestone, Phase 03 (Host Toolchains and Guided First Run)
trigger_when: next milestone, once the GUI rework milestone ships (Phase 6 verified)
scope: large
---

# SEED-261031-oe1: Plug-and-play ports: build an optimized profile automatically for a game that has none

## Why This Matters

Goal (the developer's words): getting a game running should stop being the question; a player's dump should port
plug-and-play. A game with no hand-made profile should get one built automatically, and an optimized one, not just
one that boots.

Where that stands today:
- 68 profiles in `nxnative/dm/games/`, 14 brought up on Android (`android.tsv`).
- A game with no profile ports only with `--experimental`: `porter/pipeline.py` `experimental_profile` writes a
  provisional profile from the survey (`nxnative/scripts/build_ipa_from_nsp.py` `write_profile`,
  `nxnative/dm/games/profile_guess.py`) and warns "the game may not start".
- `profile_guess.py` decides only the keys a game's files show. The keys a short boot cannot decide keep their
  defaults (render_cond, tex_flush_upload, tex_dirty_upload, core_preempt, gpu_timestamps, feedback_snap,
  alpha_from_red, vconv_range, present_interval).
- Shaders no game file holds are captured on the device on the first run (`gfx_vk_shader.c` `vk_shader_missing`)
  and pulled on the next port (`pipeline.py` `pull_captures`): two rounds before such a game draws everything.
- 18 profiles carry a hand-written `patches.py` of rewriter cuts per NSO build, each found by crash analysis
  (Super Mario Bros. Wonder: resource heap +16 KB).
- Frame rate is tuned by hand per game; Wonder dips to 40, Xenoblade Chronicles 3 runs at 30 (`docs/PORT_STATUS.md`).

## Direction (to research at milestone start)

1. Census: run an experimental port of every dump at hand with no profile and record where each stops (build, boot,
   first frame, play) and why. `profile_guess.py --check` already compares guesses with the hand-made profiles.
2. Automatic probe run: porter installs the provisional build, boots it on the device (idle or scripted input),
   collects `[RED]` lines, missing shaders, the signals for the runtime-only keys and frame times, then rebuilds
   with what it learned, in one port instead of a hand loop.
3. Fix classes, not games: move recurring `patches.py` patterns (heap slack and the like) into general rewriter or
   host rules (`dm/tools/patch_nso.py`, `dm/tools/sdk_patches.py`), so `patches.py` holds only true one-offs.
4. Performance: tune each game from the probe's frame times (fps target, present interval, adaptive perf in
   `perf_android.c`), and speed up the NVN-on-Vulkan replay path itself (the dropped Phase 7, kept below).

Constraints: `profile_guess.py` and `build_ipa_from_nsp.py` are upstream code under `nxnative/`, so guessing rules
both platforms use belong upstream or behind small hooks; probing and tuning live in `porter/` and
`nxnative/dm/android/`. A generated profile is data in the player's build folder, never game-specific code in the
Android runtime, and nothing from the game is shipped.

## When to Surface

**Trigger:** next milestone, once the GUI rework milestone ships.

This seed will surface during `/gsd-new-milestone` when the milestone scope matches.

## Scope Estimate

**Large**: a full milestone, about four phases (census, automatic probe and rebuild, fix classes into the core,
performance).

## Breadcrumbs

- `porter/pipeline.py`: `experimental_profile`, `pull_captures`
- `nxnative/scripts/build_ipa_from_nsp.py`: `survey`, `write_profile`
- `nxnative/dm/games/profile_guess.py`: `guess`, `--check`
- `nxnative/dm/tools/patch_nso.py`, `nxnative/dm/tools/sdk_patches.py`, `nxnative/dm/games/*/patches.py`
- `nxnative/dm/android/gfx_vk_shader.c` (`vk_shader_missing`), `nxnative/dm/android/perf_android.c`
- `docs/PORT_STATUS.md`, `.claude/skills/switch-android-port/SKILL.md`

## Notes

Dropped Phase 7 (NVN-on-Vulkan Performance), added and removed on 2026-10-31 so the GUI milestone keeps its scope.
Its success criteria, to reuse as the performance phase:
1. A repeatable on-device benchmark records per-frame CPU time on the replay path (NVN call handling, state
   tracking, command recording, submit) and GPU time for a fixed scene in at least two titles; its baseline is
   committed before any optimization lands.
2. The hottest replay-path costs are cut, each change citing before and after numbers in its commit and comment.
3. No frame over twice the target frame time from a pipeline or shader compile in a soak run.
4. Super Mario Bros. Wonder no longer dips below 60 fps where it dropped to 40; `docs/PORT_STATUS.md` records
   every title whose frame rate changed.
5. No rendering regressions; changes in shared `nxnative/dm/{host,gfx}` stay small and `DM_ANDROID`-guarded.
