---
phase: 11-compile-the-c-host-in-ci
plan: 04
subsystem: infra
tags: [ci, github-actions, makefile, build-strictness, tool-lock, unittest]

# Dependency graph
requires:
  - phase: 03-host-toolchains-and-guided-first-run
    provides: the NDK probe's host-folder rule build.py copies, and the pin that ubuntu-22.04 exports ANDROID_NDK_HOME — the reason the Android job downloads no toolchain
  - phase: 11-compile-the-c-host-in-ci
    provides: fork-ci.yml's trigger/pinning skeleton and tests/test_workflows.py's Ci walk (plan 11-01, a sibling wave-1 plan)
provides:
  - ".github/workflows/host-build.yml: host-apple (macos-26) and host-android (ubuntu-22.04), path-filtered to nxnative/** and .github/**, no needs: and no matrix, each job named for its target"
  - "dm/host/Makefile CFLAGS: -Werror=implicit-function-declaration, so the Apple host is as strict as the Android NDK already was"
  - "tests/arch_rules.py rule 12: the Makefile's hand-listed SRC against dm/host/*.c|m|S, failing by name with the remedy (Android globs, the Mac list does not)"
  - "tool_lock.main(argv) returning 0 / 1 / 2 with the [RED] mismatch sentence as the MISMATCH constant, asserted without Xcode or .NET"
  - "tests/test_workflows.py Ci.test_host_build_jobs: the new workflow held to the pinning/trigger rules and to its own two-job shape"
affects: [12-one-command-that-verifies-a-change, 13-guards-from-past-incidents, 14-keep-the-upstream-pick-cheap, QUAL-09 verification, branch protection]

# Actuals (#2632, chars/4 over the realized diff, not a harness token count)
actuals:
  tokens: 4000
  tasks: 3
  commits: 4

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Path filters live in their own workflow file: GitHub applies paths: to the event, so adding them to fork-ci.yml would skip the four-host suite on a documentation-only push"
    - "A hand-written source list that Android globs is guarded by a static check (SRC against the directory), not by waiting for the link that only a Mac would run"
    - "A refusal becomes testable by returning its code from main(argv) and holding its sentence in one constant, with sys.exit left in the __main__ guard"

key-files:
  created:
    - .github/workflows/host-build.yml
    - tests/test_tool_lock.py
  modified:
    - nxnative/dm/host/Makefile
    - tests/arch_rules.py
    - nxnative/dm/gfx/tools/tool_lock.py
    - tests/test_workflows.py

key-decisions:
  - "The two jobs are independent (no needs:, no matrix): fail-fast in a matrix would cancel the sibling, and a needs: chain would hide one target's verdict behind the other's (QUAL-09 adjacency, D-09)"
  - "Each job runs the repo's own entry point — make -C nxnative/dm/host ... dmhost and build.py --game ... — because the real link is what catches a source missing from SRC and a dangling project symbol; build.py's --only-compile exits before that link"
  - "MACOS_MIN is overridden from the runner's SDK on the make command line instead of editing dm/mac/min_os.mk: a command-line variable beats :=, so the image's 26.5 SDK is used without a tree change (Pitfall 3)"
  - "The Apple job installs no Metal toolchain: it gates the C host, not MSL, and a comment says so, so a green run is never read as 'the shaders compile' (Pitfall 4)"
  - "-Werror=implicit-function-declaration goes in the host's CFLAGS only, never a blanket -Werror: the libvpx and dav1d rules carry their own flags, and a blanket -Werror would pull other phases' warnings into this gate (Pitfall 8)"
  - "The SRC drift check lists the directory rather than git ls-files: a file someone is adding is exactly when the rule has to fire, and an untracked zz_probe.c must fail it"
  - "tool_lock's usage path now returns 2 (it exited 1 as a string); that matches porter's usage-error convention and is what the plan asked for, and it is the only code this refactor changed"

patterns-established:
  - "A CI job per target, named for the target, so a red check names the platform on the push that caused it"
  - "A static tree check that names both the offending file and the edit that fixes it, so the failure is actionable without the link"

requirements-completed: [QUAL-09]

coverage:
  - id: D1
    description: "host-build.yml exists with exactly two independent jobs, host-apple on macos-26 and host-android on ubuntu-22.04, each running the repo's own entry point with the fixed game"
    requirement: QUAL-09
    verification:
      - kind: unit
        ref: "tests/test_workflows.py#Ci.test_host_build_jobs"
        status: pass
      - kind: unit
        ref: "tests/test_workflows.py#Ci.test_actions_pinned (SHA pins, walked over every workflow file)"
        status: pass
    human_judgment: false
  - id: D2
    description: "The macOS 26.5 SDK versus the pinned deployment target is absorbed by a command-line MACOS_MIN, checked with make -n on this Mac"
    requirement: QUAL-09
    verification:
      - kind: other
        ref: "make -n -C nxnative/dm/host GAME=01000A10041EA000 dmhost MACOS_MIN=$(xcrun -sdk macosx --show-sdk-version) — the recipe carries -mmacosx-version-min=<SDK>"
        status: pass
    human_judgment: false
  - id: D3
    description: "The two jobs actually compile and link dmhost on GitHub's Apple and Android runners, and only a push or PR touching the two paths starts them"
    requirement: QUAL-09
    verification:
      - kind: manual_procedural
        ref: "the first push or PR touching nxnative/** or .github/** — no GitHub runner was available here"
        status: unknown
    human_judgment: true
    rationale: "CI truth is only observable on a push: the images' SDK, NDK and Xcode toolchains cannot be reproduced in this sandbox, so the Apple link and the Android link are unproven until the first run. Recorded in .planning/WINDOWS.md as an open unrun-verify."
  - id: D4
    description: "An implicit function declaration is an error on the Mac build, and a dm/host source the Makefile's SRC misses fails tests/arch_rules.py by name with the remedy"
    requirement: QUAL-09
    verification:
      - kind: unit
        ref: "tests/test_architecture.py#test_rules (arch_rules rule 12 PASS on the clean tree)"
        status: pass
      - kind: other
        ref: "an untracked nxnative/dm/host/zz_probe.c made arch_rules print 'FAIL dm/host: every source is in the Makefile SRC (line 23): zz_probe.c (add it to SRC in nxnative/dm/host/Makefile)' and exit 1; deleted again, the tree passes"
        status: pass
      - kind: other
        ref: "clang -fsyntax-only with the CI flags on main.c hle.c hle_fs.c hle_thread.c hle_movie.c loader.c — no diagnostics"
        status: pass
    human_judgment: false
  - id: D5
    description: "A synthetic dmsh_chain.lock mismatch returns 1 and prints the module constant's sentence, a match returns 0 with no [RED] line, no argument returns 2 with the usage line, and the no-run remedy still names brew install --cask dotnet-sdk and DOTNET_ROOT"
    requirement: QUAL-09
    verification:
      - kind: unit
        ref: "tests/test_tool_lock.py#Lock.test_a_mismatch_names_its_key_and_returns_one"
        status: pass
      - kind: unit
        ref: "tests/test_tool_lock.py#Lock.test_a_match_returns_zero_and_says_nothing_red"
        status: pass
      - kind: unit
        ref: "tests/test_tool_lock.py#Lock.test_no_option_is_usage"
        status: pass
      - kind: unit
        ref: "tests/test_tool_lock.py#Lock.test_the_no_run_remedy_still_names_the_runtime"
        status: pass
      - kind: integration
        ref: "python nxnative/dm/gfx/tools/tool_lock.py --check-tools on this Mac exits 0 (the real tool chain still matches its lock after the refactor)"
        status: pass
      - kind: unit
        ref: "nxnative/dm/tools/tests/test_nsp_env_checks.py (15 tests, the module's other importer)"
        status: pass
    human_judgment: false
  - id: D6
    description: "Both job names are required status checks on the default branch, so a red host build blocks a merge"
    requirement: QUAL-09
    verification: []
    human_judgment: true
    rationale: "Branch protection is repository settings, not a file in the tree: the user adds `host-apple` and `host-android` to Settings → Branches → the main rule → Require status checks, after the first green run (user_setup)."

# Metrics
duration: 3min
completed: 2026-11-04
status: complete
---

# Phase 11 Plan 04: The C host compiled per target in CI Summary

**A path-filtered `host-build.yml` compiles `dm/host` twice — `host-apple` on `macos-26` through the Makefile and `host-android` on `ubuntu-22.04` through `build.py` — as two independent jobs named for their targets, backed by a strict Mac `CFLAGS` and two static guards (a `SRC`-versus-directory check and a tested `dmsh_chain.lock` refusal).**

## Performance

- **Duration:** 3 min by the sandbox clock (four commits span 16:10:12Z–16:11:31Z; the clock barely advanced during this run, so it reads lower than the effort)
- **Started:** 2026-11-04T16:08:30Z (after 11-01's docs commit)
- **Completed:** 2026-11-04T16:11:40Z
- **Tasks:** 3
- **Files modified:** 6 (2 created, 4 modified)

## Accomplishments
- `.github/workflows/host-build.yml`: two jobs, no `needs:`, no matrix, every `uses:` pinned by the SHA `fork-ci.yml` already uses, no `secrets.`, `permissions: contents: read`, `concurrency` on `github.ref` with cancel-in-progress. Both trigger on `push` and `pull_request` filtered to `nxnative/**` and `.github/**` plus `workflow_dispatch`; `fork-ci.yml` keeps no `paths:`, so a documentation-only push still runs the four-host suite (QUAL-09 empty edge).
- `host-apple` runs `make -C nxnative/dm/host GAME=01000A10041EA000 -j<hw.ncpu> dmhost MACOS_MIN="$(xcrun -sdk macosx --show-sdk-version)"` and then `ls -l`s the binary; `host-android` runs `build.py --game 01000A10041EA000 --out "$RUNNER_TEMP/host-android"` and `ls`es the executable and the `.so`. Neither is a bespoke `clang` line; the workflow says in place that the Android step is the real link (which is what catches a missed source and a dangling symbol), and `test_host_build_jobs` pins both entry-point commands.
- `dm/host/Makefile`'s `CFLAGS` now carries `-Werror=implicit-function-declaration` — the strictness `dm/android/build.py` already had — with a comment naming why the third-party rules below it are untouched and why there is no blanket `-Werror`.
- `tests/arch_rules.py` gained rule 12: it reads the `SRC=` line, tokenises it (the `hle_*.c` wildcard stays a pattern), lists `dm/host/*.c|*.m|*.S` from the directory, and fails naming each file that Android's `host/*.c` glob would compile and the Mac list would miss, with the remedy in the same line.
- `tool_lock.py` grew `MISMATCH` and `main(argv) -> int` (0 clean, 1 mismatch or a translator that does not run, 2 usage); `sys.exit` remains only in the `__main__` guard. `tests/test_tool_lock.py` asserts the sentence, the code and both remedy texts with `LOCK` and `tools_now` patched, so it runs on all four hosts without Xcode, .NET or brew.
- `tests/test_workflows.py`'s `Ci` class gained `test_host_build_jobs`, which pins the two job names, their runner images, the absence of `needs:`/`strategy`, both path filters, and the two entry-point commands.

## Task Commits

Each task was committed atomically (Task 3 followed RED → GREEN):

1. **Task 1: End-to-end "the host compiles in CI"** — `a89ef298` (feat, tracer)
2. **Task 2: The two cheap guards** — `4ae701d1` (feat)
3. **Task 3: The `dmsh_chain.lock` refusal, made testable** — `d4098a4f` (test, RED), `5eb27450` (feat, GREEN)

**Plan metadata:** the commit after this file (`docs(11-04): complete ...`)

## Files Created/Modified
- `.github/workflows/host-build.yml` — the two path-filtered compile jobs, their trigger, pins, timeout and the comments that hold each pitfall (SDK override, arm64 runner, Metal toolchain, `--only-compile`).
- `nxnative/dm/host/Makefile` — `CFLAGS` gains the implicit-declaration error; nothing else changed, so the libvpx/dav1d rules keep their own flags.
- `tests/arch_rules.py` — rule 12, the `SRC`-versus-directory drift check, placed with the other tree rules so `tests/test_architecture.py` runs it on every host.
- `nxnative/dm/gfx/tools/tool_lock.py` — `MISMATCH`, `main(argv)`, one `sys.exit` left in the `__main__` guard; `check_tools`, `tools_now`, `xlate_embedded` and `no_run_message` untouched.
- `tests/test_tool_lock.py` — the four lock-refusal behaviours, hermetic (no `xcrun`, `dotnet` or `brew`).
- `tests/test_workflows.py` — `Ci.test_host_build_jobs`.

## Decisions Made
- **Independent jobs, not a matrix** — `fail-fast: false` inside a matrix would still cancel the sibling on the first failure, and a `needs:` chain would make one target's verdict depend on the other's (T-11-16).
- **The real link, both sides** — a per-file `-c` check would pass while `SRC` misses a file; the link is what the Makefile and `build.py` do and what the plan's truth asks for. The cost is the `timeout-minutes: 45` on Apple, sized for a cold libvpx and dav1d build.
- **`MACOS_MIN` from the SDK on the command line, no tree edit** — `dm/mac/min_os.mk` stays 26.6 for real Macs; the runner's SDK wins because a command-line variable beats `:=`. Confirmed by `make -n` on this Mac, where `-mmacosx-version-min=<SDK>` follows the override.
- **The Makefile comment does not repeat the flag literal** — the first draft named `-Werror=implicit-function-declaration` in the comment above `CFLAGS`, which made the acceptance grep return two matches; the comment now says "strict on implicit function declarations", so `grep -c` of the flag is exactly 1 (the `CFLAGS` line) and the reasoning is still written down.
- **`--update-lock`'s refusals return 1 instead of `sys.exit(<string>)`** — `sys.exit(str)` prints to stderr and exits 1, so printing to stderr and returning 1 is byte-identical on both streams, and it is what T-11-17 asks for (one `sys.exit`, in the `__main__` guard).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing critical functionality] `--update-lock`'s two refusals were hoisted with the rest of `main`**
- **Found during:** Task 3 (GREEN)
- **Issue:** the plan said to keep the other refusals "on their existing paths and codes". `sys.exit('[RED] …')` inside `main()` would keep the code but make `main` untestable on those paths and leave two `sys.exit` calls outside the `__main__` guard — the exact shape T-11-17 mitigates.
- **Fix:** `print(…, file=sys.stderr); return 1` — the same stream and the same exit code `sys.exit(str)` produced.
- **Files modified:** `nxnative/dm/gfx/tools/tool_lock.py`
- **Verification:** `grep -c sys.exit` returns 1; `tool_lock --check-tools` on this Mac still exits 0.
- **Committed in:** `5eb27450` (Task 3 feat)

**2. [Rule 3 - Blocking issue] The usage path's exit code had to move from 1 to 2 to be assertable**
- **Found during:** Task 3 (RED)
- **Issue:** the plan's Test 3 requires `main([])` to return 2, while the old `sys.exit('usage: …')` exited 1. The two cannot both hold.
- **Fix:** followed the plan and `porter`'s usage-error convention: usage returns 2. The plan tolerates this (its Test 3 is explicit) but it is a behaviour change for anyone scripting the old code.
- **Files modified:** `nxnative/dm/gfx/tools/tool_lock.py`
- **Verification:** `tests/test_tool_lock.py#Lock.test_no_option_is_usage`; `.venv/bin/python nxnative/dm/gfx/tools/tool_lock.py` prints the usage line and returns 2.
- **Committed in:** `5eb27450` (Task 3 feat)

---

**Total deviations:** 2 auto-fixed (1 Rule 2, 1 Rule 3)
**Impact on plan:** Both stay inside the plan's contract (T-11-17 and Test 3 name them); the only observable change outside the plan's text is the usage exit code, which the plan itself specified.

## Issues Encountered
- **No GitHub runner here**, so neither job has executed. What was verified instead: the workflow's shape and rules statically (`tests/test_workflows.py`), the Apple command line with `make -n` (the recipe shows `-mmacosx-version-min=<this Mac's SDK>`, i.e. the override reaches clang), and six representative host sources compiled with `-fsyntax-only` under the exact new `CFLAGS` include set — no diagnostics. The Android link was **not** run: no NDK build of that size was attempted in this sandbox. Recorded in `.planning/WINDOWS.md` (`unrun-verify`, open) rather than claimed.
- **The sandbox clock is compressed** (it advanced ~80 s across four commits), so the duration above is the clock's, not the effort's.
- The generated `nxnative/dm/host/gen/` headers written while spot-checking are gitignored; the temporary `zz_probe.c` was deleted after proving the check, and neither appears in a commit.

## User Setup Required

Branch protection, once (it is repository settings, not a file):

1. Open GitHub → **Settings → Branches** → the protection rule for `main` → **Require status checks to pass**.
2. Add **`host-apple`** and **`host-android`** to the required checks — after the first push or PR that runs them, so the names exist to pick.

Nothing else: no secrets, no environment, no variables. The Apple job needs no Metal toolchain by design.

## Known Stubs
None.

## Next Phase Readiness
- QUAL-09's code half is done: a host break on either target now has a job that names it, and the two guards that a link would only find late fail by name in the shared suite.
- Open by design: the first CI run (`.planning/WINDOWS.md` `unrun-verify`) and the branch-protection ticks (above). Both are visible to the ship gate.
- Plans 11-02 and 11-03 are untouched by this plan; nothing here depends on their GUI or protocol work.

---
*Phase: 11-compile-the-c-host-in-ci*
*Completed: 2026-11-04*

## Self-Check: PASSED

- Commits `a89ef298`, `4ae701d1`, `d4098a4f`, `5eb27450` all present.
- `.github/workflows/host-build.yml`, `tests/test_tool_lock.py`, `nxnative/dm/host/Makefile`, `tests/arch_rules.py`, `nxnative/dm/gfx/tools/tool_lock.py`, `tests/test_workflows.py` present.
- `nxnative/dm/games/010062B01525C000/game.tsv` and the Phase 03 planning files untouched (still the other work's uncommitted changes).
