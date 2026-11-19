---
phase: quick-261118-nit
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - nxnative/dm/android/gfx_vk_exec.c
  - tests/test_vk_copy_span.py
autonomous: true
requirements: [QUICK-261118-nit]

estimate:
  tokens: 30000
  raw_tokens: 30000
  tasks: 2
  confidence: low

must_haves:
  truths:
    - "A buffer to texture copy whose pool offset is not a multiple of the format's block size (4 for depth/stencil) reaches vkCmdCopyBufferToImage from an aligned scratch offset that holds the guest's bytes, copied on the GPU timeline"
    - "A texture to buffer copy at such an offset lands in the guest buffer at the guest's own offset, and the guest bytes between rows and slices that the copy does not cover keep their values"
    - "An aligned copy issues exactly the commands it issued before: no scratch allocation, no vkCmdCopyBuffer, no extra barrier"
    - "A misaligned copy whose span runs out of its memory pool logs one [RED] line and is skipped, before any scratch is allocated"
    - "The wrote-b2t detail string says staged 0 or staged 1"
    - "tests.test_vk_copy_span and tests.test_architecture pass and every Android source compiles (0 failed)"
    - "Nothing is staged or committed, the tablet is not touched, and no android.tsv or docs/PORT_STATUS.md changes"
  artifacts:
    - path: nxnative/dm/android/gfx_vk_exec.c
      provides: "copy_span helper; copy_b2t stages misaligned copies through scratch in both directions"
      contains: "static VkDeviceSize copy_span("
    - path: tests/test_vk_copy_span.py
      provides: "regression test that compiles copy_span from the C source with the host cc, no NDK"
      contains: "copy_span"
  key_links:
    - from: "copy_b2t"
      to: "copy_span"
      via: "span of the staged range, computed with the bytes per texel Vulkan uses for the copied aspect"
      pattern: "span = copy_span\\("
    - from: "copy_b2t"
      to: "vk_buf_at"
      via: "the whole span is resolved in a pool before scratch is taken"
      pattern: "vk_buf_at\\(c->src, span, &gb, &go\\)"
    - from: "copy_b2t"
      to: "vk_scratch"
      via: "staging range, over-allocated by need and aligned by hand"
      pattern: "vk_scratch\\(span \\+ need, 16, &b, &so\\)"
---

<objective>
Make `copy_b2t` honour Vulkan's rule that `bufferOffset` is a multiple of the texel block size (4 for depth/stencil). NVN has no such rule, so a guest buffer can sit anywhere.

Purpose: on Persona 4 Golden (Legion Y700, Adreno 840, build 65554), 315 of 658 BC7 copies had a source 8 bytes off a 16-byte block. Serial 770 read back as its source shifted by exactly 8 bytes and decoded to rainbow confetti; aligned serials 774 and 777 read back byte-identical. The alignment changes between loads, so a different set of objects breaks on each load. The fix is general: every format, every title, both directions.

Output: one helper and one staging block in `nxnative/dm/android/gfx_vk_exec.c`, plus `tests/test_vk_copy_span.py`. All of it stays UNCOMMITTED in the working tree.
</objective>

<execution_context>
@~/.claude/gsd-core/workflows/execute-plan.md
@~/.claude/gsd-core/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@.claude/CLAUDE.md
@.claude/skills/nx2android-dev/SKILL.md
@tests/test_vk_layout_cache.py

Locate code by identifier, not by line number: `gfx_vk_exec.c` was edited by something else while this plan was written (`copy_b2t` moved from line 2007 to 2010).

Facts the planner verified against the working tree (do not re-derive):
- `copy_b2t` is the only image copy that hands a guest pool offset to Vulkan unchecked. `lin_copy` in `gfx_vk_tex.c` already refuses `o % f->bpb`; the other copies use their own buffers or scratch. Its two callers are the `OP_COPY_B2T` and `OP_COPY_T2B` cases.
- `copy_b2t` already has the locals `b`, `o`, `cb`, `bw`, `bh`, `rowlen`, `imgh`, `layered`, `depth`, `r`. Its `depth` equals `layered ? r.imageSubresource.layerCount : r.imageExtent.depth`, so it is the value to pass.
- `nvn_fmt_bpb` gives NVN sizes: S8 1, D16 2, D24 variants and D32F 4, D32F_S8 8. Vulkan's buffer layout for a depth aspect is 2 bytes for D16 and 4 otherwise, and 1 byte for a stencil aspect. `sub_of` picks the depth aspect of a combined format, and NVN's stencil-only format becomes D24_S8 on a device without S8 attachments. So `f->bpb` is wrong for the span in both directions on those formats: too large for D32F_S8, too small for that S8 fallback.
- `vk_scratch` masks its alignment, so it takes powers of two only; `need` may be 3, 6 or 12. Scratch lives until the submission completes and has TRANSFER_SRC and TRANSFER_DST usage (`POOL_USAGE0`).
- `vk_img_barrier_all` is a full ALL_COMMANDS memory barrier. `VKRED_ONCE` ids 70 to 76 and 80 are taken and 77 is free in `nxnative/dm/android`.
- Baselines (planner run on the dirty tree): `build.py --only-compile` printed `compiled 267 sources, 0 failed` (it prints compiler output only for failed files, so warnings do not reach its log); `tests.test_architecture` passes; nothing is staged; inside `copy_b2t` the count of `vkCmdCopyBuffer(cb` is 0. The six `copy_span` test values below were compiled and run under `cc -std=c11 -Wall -Wextra -Werror` and hold. The staging code of both tasks, applied to a scratch copy of the file, passed NDK clang `-fsyntax-only` with `build.py`'s warning flags and printed nothing.
- `tests/arch_rules.py` strips comments before matching, so a comment may name the game. A branch may not.

<interfaces>
New helper, verbatim, placed directly above `copy_b2t`:

```c
static VkDeviceSize copy_span(uint32_t w, uint32_t h, uint32_t depth, uint32_t rowlen, uint32_t imgh, uint32_t bw, uint32_t bh, uint32_t bpb) {
    VkDeviceSize row = (VkDeviceSize)(((rowlen ? rowlen : w) + bw - 1) / bw) * bpb, rows = (h + bh - 1) / bh, slice = (VkDeviceSize)(((imgh ? imgh : h) + bh - 1) / bh) * row;
    return (VkDeviceSize)(depth - 1) * slice + (rows - 1) * row + (VkDeviceSize)((w + bw - 1) / bw) * bpb;
}
```

Existing, used unchanged: `int vk_buf_at(uint64_t addr, uint64_t len, VkBuffer *buf, VkDeviceSize *off)`, `void *vk_scratch(VkDeviceSize n, VkDeviceSize align, VkBuffer *buf, VkDeviceSize *off)`, `void vk_img_barrier_all(VkCommandBuffer cb)`.
</interfaces>
</context>

<repository_state_rules>
HARD RULES for the executor:
1. `nxnative/dm/android/gfx_vk_exec.c` and `gfx_vk_tex.c` hold the user's uncommitted Ocarina of Time work. Edit in place on the main tree with scoped Edit calls. No worktree, no formatter, no change to any line outside the hunks this plan names, and `gfx_vk_tex.c` is not edited at all.
2. Run none of: `git add`, `git commit`, `git stash`, `git checkout`, `git restore`. There are no task commits. `gfx_vk_exec.c` stays modified and `tests/test_vk_copy_span.py` stays untracked; say so in SUMMARY.md. The quick-task wrapper handles its own `.planning` files.
3. Do not touch the tablet: no adb install, launch or push. Do not change any `android.tsv` or `docs/PORT_STATUS.md`, because nothing has been verified on the device.
4. Build output goes only to the scratch folder in the verify commands. Never omit `--out`.
5. If the compile fails for a reason outside `copy_b2t` and `copy_span`, stop and report it. Do not fix it.
</repository_state_rules>

<tasks>

<task type="tracer">
  <name>Task 1: Stage misaligned buffer to texture copies end to end, test first</name>
  <files>tests/test_vk_copy_span.py, nxnative/dm/android/gfx_vk_exec.c</files>
  <read_first>
    - tests/test_vk_layout_cache.py (the pattern: extract a C function by text, compile with host cc)
    - nxnative/dm/android/gfx_vk_exec.c, the function `copy_b2t` (find it with grep, then read that range only)
  </read_first>
  <action>
1. Before the first edit, create the folder /private/tmp/claude-501/-Volumes-Data-Dev-nxhost/d441efc6-415b-44b7-b67f-33e41d93597a/scratchpad/pre and copy `nxnative/dm/android/gfx_vk_exec.c` into it. The file is already dirty, so this copy is what isolates this task's diff.

2. Create `tests/test_vk_copy_span.py`, modelled on `tests/test_vk_layout_cache.py` but with no `porter` import and no NDK lookup. Read `nxnative/dm/android/gfx_vk_exec.c` from `ROOT`, take the text from `static VkDeviceSize copy_span(` through the first following line-start closing brace (the same `src.index` pair as the model). Decorate the test with `unittest.skipUnless(shutil.which('cc'), ...)`. The harness is `#include <stdint.h>`, `#include <assert.h>`, `typedef unsigned long long VkDeviceSize;`, the extracted helper, and a `main` of asserts. Compile in a `tempfile.TemporaryDirectory` with `cc -std=c11 -Wall -Wextra -Werror` and run the binary, both with `check=True`. Assert, as `copy_span(w, h, depth, rowlen, imgh, bw, bh, bpb)`:
   - (256, 256, 1, 0, 0, 4, 4, 16) is 65536 (BC7)
   - (512, 512, 1, 0, 0, 4, 4, 8) is 131072 (BC1)
   - (6, 6, 1, 0, 0, 4, 4, 16) is 64 (partial blocks round up)
   - (256, 8, 1, 512, 0, 4, 4, 16) is 128*16 + 64*16 (the last row is not a full stride)
   - (16, 16, 2, 0, 32, 4, 4, 16) is 768 (two layers with an image height set)
   - (16, 16, 1, 0, 0, 1, 1, 4) is 1024 (RGBA8)
   Run it now and see it fail, because the helper does not exist yet.

3. Insert the `copy_span` helper from the `<interfaces>` block, verbatim, on the lines directly above `static void copy_b2t(`.

4. In `copy_b2t`, directly after the line `if (layered) r.imageSubresource.layerCount = (uint32_t)depth;` and before the `g_watch_off` line, add the staging block in the file's dense style:
   - A one or two line comment giving the why: Vulkan wants `bufferOffset` on a block boundary (4 for depth/stencil) and NVN does not; Persona 4 Golden had 315 of 658 BC7 copies 8 bytes off, and the image read back shifted by those 8 bytes. Say the staging uses GPU copies so a GPU write to the buffer earlier in this submission still counts.
   - `VkDeviceSize need = f->depth || f->stencil ? 4 : f->bpb, span = 0, go = 0; VkBuffer gb = b; int staged = to_texture && need && o % need;` The `to_texture` term keeps the reverse direction on its present path until Task 2.
   - `if (staged)`: compute the bytes per texel of the copied aspect, `f->depth || f->stencil ? (r.imageSubresource.aspectMask == VK_IMAGE_ASPECT_STENCIL_BIT ? 1 : f->vk == VK_FORMAT_D16_UNORM ? 2 : 4) : f->bpb`. This is the one refinement over passing `f->bpb`; the reason is in the facts above.
   - `span = copy_span(r.imageExtent.width, r.imageExtent.height, (uint32_t)depth, rowlen, imgh, bw, bh, <those bytes>);`
   - `if (!vk_buf_at(c->src, span, &gb, &go)) { VKRED_ONCE(77, ...); return; }` with a message saying a buffer and texture copy at an unaligned offset runs past its memory pool and is skipped, printing the buffer address and span. This check comes before the scratch allocation, so a bad guest range cannot grow scratch.
   - `VkDeviceSize so; vk_scratch(span + need, 16, &b, &so); so += (need - so % need) % need; r.bufferOffset = so;` Reassigning `b` lets the existing `vkCmdCopyBufferToImage` line run unchanged from scratch.
   - `VkBufferCopy in = {go, so, span}; vkCmdCopyBuffer(cb, gb, b, 1, &in); vk_img_barrier_all(cb);`

5. Append ` staged %d` to the end of the `wrote-b2t` detail format string held in `d`, and pass `staged` as the last argument after `f->bc != 0`.
  </action>
  <verify>
    <automated>S=/private/tmp/claude-501/-Volumes-Data-Dev-nxhost/d441efc6-415b-44b7-b67f-33e41d93597a/scratchpad; F=nxnative/dm/android/gfx_vk_exec.c; R="$(awk '/^static void copy_b2t\(/,/^}/' $F)"; .venv/bin/python -m unittest tests.test_vk_copy_span tests.test_architecture && [ "$(grep -c '^static VkDeviceSize copy_span(' $F)" = 1 ] && printf '%s\n' "$R" | grep -q 'int staged = to_texture && need && o % need' && printf '%s\n' "$R" | grep -q 'vk_buf_at(c->src, span, &gb, &go)' && printf '%s\n' "$R" | grep -q 'VKRED_ONCE(77,' && printf '%s\n' "$R" | grep -q 'vk_scratch(span + need, 16, &b, &so)' && printf '%s\n' "$R" | grep -q ' staged %d' && [ "$(printf '%s\n' "$R" | grep -o 'vkCmdCopyBuffer(cb' | wc -l | tr -d ' ')" = 1 ] && .venv/bin/python nxnative/dm/android/build.py --game 010062B01525C000 --ndk "$HOME/Library/Android/sdk/ndk/27.2.12479018" --out "$S/base-compile" --only-compile > "$S/b2t-compile.log" 2>&1 && tail -1 "$S/b2t-compile.log" | grep -q ', 0 failed'</automated>
  </verify>
  <done>
Gate baselines and targets: `copy_span` definitions 0 to 1; `vkCmdCopyBuffer(cb` inside `copy_b2t` 0 to 1; `VKRED_ONCE(77,` 0 to 1; `staged %d` 0 to 1. The new test failed before step 3 and passes after it. The compile reports 0 failed. A misaligned buffer to texture copy now reads from an aligned scratch range; an aligned one runs no new command; a texture to buffer copy behaves as before.
  </done>
</task>

<task type="auto">
  <name>Task 2: Stage misaligned texture to buffer copies without disturbing guest bytes</name>
  <files>nxnative/dm/android/gfx_vk_exec.c</files>
  <read_first>
    - nxnative/dm/android/gfx_vk_exec.c, the function `copy_b2t` as Task 1 left it
  </read_first>
  <action>
1. Change the staging condition to `int staged = need && o % need;` so both directions take the block.

2. Keep the guest to scratch copy for this direction too. It is what protects the guest: with a row stride wider than the copy, or an image height taller than it, `vkCmdCopyImageToBuffer` leaves gaps in the scratch range, and the copy back covers the whole span. Seeded from the guest, those gap bytes go back unchanged. Say this in a one line comment.

3. In the texture to buffer branch, directly after the existing `vkCmdCopyImageToBuffer` call and before the `vk_gpu_wrote` declaration on the next line, add: `if (staged) { vk_img_barrier_all(cb); VkBufferCopy back = {r.bufferOffset, go, span}; vkCmdCopyBuffer(cb, b, gb, 1, &back); }`. Leave the `vk_gpu_wrote` call and the function's closing `vk_img_barrier_all(cb)` as they are.

4. Run `diff -u` between the copy in the scratch `pre` folder and `nxnative/dm/android/gfx_vk_exec.c` and put the output in SUMMARY.md. If it shows hunks outside `copy_span` and `copy_b2t`, they came from the concurrent edit: report them and leave them alone. In SUMMARY.md, state that the code is uncommitted, that nothing ran on the device, and that the check still owed is a Persona 4 Golden run after the user approves an install, where `staged 1` in the `wrote-b2t` lines shows the path was taken.
  </action>
  <verify>
    <automated>S=/private/tmp/claude-501/-Volumes-Data-Dev-nxhost/d441efc6-415b-44b7-b67f-33e41d93597a/scratchpad; F=nxnative/dm/android/gfx_vk_exec.c; R="$(awk '/^static void copy_b2t\(/,/^}/' $F)"; .venv/bin/python -m unittest tests.test_vk_copy_span tests.test_architecture && printf '%s\n' "$R" | grep -q 'int staged = need && o % need' && printf '%s\n' "$R" | grep -q 'VkBufferCopy back = {r.bufferOffset, go, span}' && [ "$(printf '%s\n' "$R" | grep -o 'vkCmdCopyBuffer(cb' | wc -l | tr -d ' ')" = 2 ] && .venv/bin/python nxnative/dm/android/build.py --game 010062B01525C000 --ndk "$HOME/Library/Android/sdk/ndk/27.2.12479018" --out "$S/base-compile" --only-compile > "$S/b2t-compile.log" 2>&1 && tail -1 "$S/b2t-compile.log" | grep -q ', 0 failed' && git diff --cached --quiet && A="$(git status --porcelain -- docs/PORT_STATUS.md 'nxnative/dm/games/*/android.tsv')" && [ -z "$A" ] && U="$(git status --porcelain -- tests/test_vk_copy_span.py)" && [ "$U" = '?? tests/test_vk_copy_span.py' ]</automated>
  </verify>
  <done>
`vkCmdCopyBuffer(cb` inside `copy_b2t` goes from 1 to 2. Both directions stage a misaligned copy; the guest buffer receives the image data at its own offset and keeps the bytes between rows and slices. Tests and the compile pass, nothing is staged, the new test is untracked, and SUMMARY.md carries the diff and the device check still owed.
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| guest game -> GPU copy commands | The guest chooses the buffer address, stride, extent and layer count of every copy |
| scratch -> guest memory | The texture to buffer path writes scratch contents back over guest memory |

## STRIDE Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation Plan |
|-----------|----------|-----------|----------|-------------|-----------------|
| T-nit-01 | Tampering | `copy_b2t` copy back to the guest buffer | high | mitigate | The span uses the copied aspect's real bytes per texel, so D32F_S8 cannot write past the copy, and scratch is seeded from the guest first, so row and slice gaps return unchanged (Tasks 1 and 2) |
| T-nit-02 | Denial of service | `copy_b2t` scratch allocation | medium | mitigate | `vk_buf_at(c->src, span, ...)` must succeed before `vk_scratch`, so the allocation is bounded by a real pool range; failure logs `VKRED_ONCE(77, ...)` and skips the copy |
| T-nit-03 | Information disclosure | Uninitialised scratch reaching the image or guest | low | mitigate | Every staged byte in the span is written by the guest to scratch copy before any use |
| T-nit-SC | Tampering | npm/pip/cargo installs | low | accept | This plan installs no packages |
</threat_model>

<verification>
Run from the repository root:
- `.venv/bin/python -m unittest tests.test_vk_copy_span tests.test_architecture`
- The `build.py --only-compile` command in Task 2's verify: `compiled ... 0 failed`
- `git diff --cached --quiet` succeeds, so nothing was staged

Not verifiable here: the visual fix on the device. It needs an install, which needs the user's approval and comes after this task.
</verification>

<success_criteria>
- Misaligned copies in both directions satisfy Vulkan's `bufferOffset` rule and move the same bytes the guest asked for
- Aligned copies are unchanged, command for command
- Regression test and architecture test pass, all Android sources compile
- The user's uncommitted work is intact and this change is left uncommitted
</success_criteria>

<output>
Create `.planning/quick/261118-nit-align-android-buffer-texture-copies-to-t/261118-nit-SUMMARY.md` when done
</output>
