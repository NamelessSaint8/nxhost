---
phase: quick-261118-nit
plan: 01
subsystem: android-vulkan
tags: [vulkan, nvn, android, texture-copy, buffer-alignment]
status: complete

requires: []
provides:
  - "copy_span: bytes a buffer and texture copy touches in its buffer"
  - "copy_b2t stages copies at a misaligned buffer offset through scratch, in both directions"
affects: [gfx_vk_exec.c, wrote-b2t texture history detail]

actuals:
  tokens: 980
  tasks: 2
  commits: 0
plan_head_before: 6bc4ebfbc600d9c97d9afc6f2682c314a98814b4
plan_head_after: 6bc4ebfbc600d9c97d9afc6f2682c314a98814b4

tech-stack:
  added: []
  patterns:
    - "Host-cc test that extracts one C helper from the Android source by text"

key-files:
  created:
    - tests/test_vk_copy_span.py
  modified:
    - nxnative/dm/android/gfx_vk_exec.c

key-decisions:
  - "The staged span uses the bytes per texel Vulkan lays out for the copied aspect, not NVN's size"
  - "Scratch is seeded from the guest in both directions, so row and slice gaps return unchanged after a texture to buffer copy"

requirements-completed: [QUICK-261118-nit]

metrics:
  duration: 3 min
  completed: 2026-11-18
---

# Phase quick-261118-nit Plan 01: Align Android Buffer and Texture Copies Summary

`copy_b2t` now moves a copy at a misaligned guest buffer offset through an aligned scratch range with GPU copies, in both directions. Aligned copies issue the same commands as before.

**All of this is uncommitted, and nothing ran on a device.** `nxnative/dm/android/gfx_vk_exec.c` stays modified alongside the user's Ocarina of Time work, and `tests/test_vk_copy_span.py` stays untracked. Commit hash for both tasks: uncommitted. `commits: 0` is deliberate: the plan's repository rules and the orchestrator forbid staging and committing here.

## Accomplishments

- `copy_span` computes the buffer span of a copy, with partial blocks, a row stride wider than the copy and an image height taller than it.
- Buffer to texture: when `bufferOffset` is off the block size (4 for depth/stencil), the guest range is copied to aligned scratch on the GPU timeline and `vkCmdCopyBufferToImage` reads from there.
- Texture to buffer: scratch is seeded from the guest, the image is copied over it, and the whole span goes back, so bytes between rows and slices keep their values.
- A misaligned copy whose span leaves its pool logs one `[RED]` line (`VKRED_ONCE(77, ...)`) and is skipped before any scratch is allocated.
- The `wrote-b2t` detail string ends in `staged 0` or `staged 1`.

## Task Commits

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Stage misaligned buffer to texture copies, test first | uncommitted | tests/test_vk_copy_span.py, nxnative/dm/android/gfx_vk_exec.c |
| 2 | Stage misaligned texture to buffer copies | uncommitted | nxnative/dm/android/gfx_vk_exec.c |

## Verification

| Check | Result |
|-------|--------|
| New test before the helper existed | failed as expected (`ValueError: substring not found`, 1 error) |
| Task 1 automated verify | passed (exit 0) |
| Task 2 automated verify | passed (exit 0) |
| `tests.test_vk_copy_span tests.test_architecture` | Ran 2 tests, OK |
| `build.py --only-compile` tail line | `compiled 267 sources, 0 failed` |
| Staged changes | none |
| `docs/PORT_STATUS.md`, `android.tsv` files | unchanged |

## Device Check Still Owed

The visual fix is unverified. It needs a Persona 4 Golden run after the user approves an install. `staged 1` in the `wrote-b2t` lines shows the path was taken, and the textures that came out as confetti should then read back correctly.

## Diff Against the Pre-Task Copy

Three hunks, all inside `copy_span` and `copy_b2t`. No hunk came from a concurrent edit.

```diff
@@ -2007,6 +2007,10 @@
     int layered = im->layers > 1;
     return (VkImageSubresourceLayers){im->aspect & VK_IMAGE_ASPECT_COLOR_BIT ? VK_IMAGE_ASPECT_COLOR_BIT : (im->aspect & VK_IMAGE_ASPECT_DEPTH_BIT ? VK_IMAGE_ASPECT_DEPTH_BIT : VK_IMAGE_ASPECT_STENCIL_BIT), lv, ly + (layered ? (uint32_t)z : 0), 1};
 }
+static VkDeviceSize copy_span(uint32_t w, uint32_t h, uint32_t depth, uint32_t rowlen, uint32_t imgh, uint32_t bw, uint32_t bh, uint32_t bpb) {
+    VkDeviceSize row = (VkDeviceSize)(((rowlen ? rowlen : w) + bw - 1) / bw) * bpb, rows = (h + bh - 1) / bh, slice = (VkDeviceSize)(((imgh ? imgh : h) + bh - 1) / bh) * row;
+    return (VkDeviceSize)(depth - 1) * slice + (rows - 1) * row + (VkDeviceSize)((w + bw - 1) / bw) * bpb;
+}
 static void copy_b2t(const p_copy_b2t *c, int to_texture) {
     vk_end_pass_land();
     vkimg_t *im = vk_tex(c->tex); const vkfmt_t *f = vk_fmt(c->tex->d.format);
@@ -2033,6 +2037,17 @@
     VkBufferImageCopy r = {o, rowlen, imgh, sub_of(im, &c->view, c->has_view, c->r.zoffset), {c->r.xoffset, c->r.yoffset, layered ? 0 : c->r.zoffset},
                            {(uint32_t)c->r.width, (uint32_t)(c->r.height ? c->r.height : 1), layered ? 1 : (uint32_t)depth}};
     if (layered) r.imageSubresource.layerCount = (uint32_t)depth;
+    // Vulkan wants bufferOffset on a texel block (4 for depth/stencil), NVN does not: Persona 4 Golden had 315 of 658 BC7 copies 8 bytes off, and the image read back shifted by those 8.
+    // Staged with GPU copies, so a GPU write to the buffer earlier in this submission still counts
+    VkDeviceSize need = f->depth || f->stencil ? 4 : f->bpb, span = 0, go = 0; VkBuffer gb = b; int staged = need && o % need;
+    if (staged) {
+        uint32_t tb = f->depth || f->stencil ? (r.imageSubresource.aspectMask == VK_IMAGE_ASPECT_STENCIL_BIT ? 1 : f->vk == VK_FORMAT_D16_UNORM ? 2 : 4) : f->bpb;   // what Vulkan lays out for this aspect, not NVN's size
+        span = copy_span(r.imageExtent.width, r.imageExtent.height, (uint32_t)depth, rowlen, imgh, bw, bh, tb);
+        if (!vk_buf_at(c->src, span, &gb, &go)) { VKRED_ONCE(77, "buffer ↔ texture copy at an unaligned offset runs past its memory pool, skipped (buffer %#llx, %llu bytes)", (unsigned long long)c->src, (unsigned long long)span); return; }
+        VkDeviceSize so; vk_scratch(span + need, 16, &b, &so); so += (need - so % need) % need; r.bufferOffset = so;
+        // Seeded in both directions: an image to buffer copy leaves the row and slice gaps alone, so the copy back returns the guest's own bytes there
+        VkBufferCopy in = {go, so, span}; vkCmdCopyBuffer(cb, gb, b, 1, &in); vk_img_barrier_all(cb);
+    }
     if (g_watch_off >= 0) { char w[96]; snprintf(w, sizeof w, "buffer copy %s (buffer %#llx, %dx%d)", to_texture ? "destination" : "source", (unsigned long long)c->src, c->r.width, c->r.height); vk_watch(im, w); }
     if (to_texture) { vkCmdCopyBufferToImage(cb, b, im->img, VK_IMAGE_LAYOUT_GENERAL, 1, &r); vk_tex_mark_gpu_write(im); vk_texraw_dump(im, c->tex->serial);
         // DM_VK_TEXPAINT=all (or a serial): right after its copy, a compressed image is cleared to magenta, so the player can say which surfaces draw *this* image.
@@ -2041,11 +2056,12 @@
             VkClearColorValue mag = {{1.0f, 0.0f, 1.0f, 1.0f}};
             VkImageSubresourceRange rg = {VK_IMAGE_ASPECT_COLOR_BIT, 0, VK_REMAINING_MIP_LEVELS, 0, VK_REMAINING_ARRAY_LAYERS};
             vkCmdClearColorImage(cb, im->img, VK_IMAGE_LAYOUT_GENERAL, &mag, 1, &rg); } }
-        char d[160]; snprintf(d, sizeof d, "level %u %ux%u at %d,%d buffer %#llx row %lld image %lld rowlen %u imgh %u spat %d",
+        char d[160]; snprintf(d, sizeof d, "level %u %ux%u at %d,%d buffer %#llx row %lld image %lld rowlen %u imgh %u spat %d staged %d",
                               r.imageSubresource.mipLevel, r.imageExtent.width, r.imageExtent.height, r.imageOffset.x, r.imageOffset.y,
-                              (unsigned long long)c->src, (long long)S.row_stride, (long long)S.image_stride, rowlen, imgh, f->bc != 0);
+                              (unsigned long long)c->src, (long long)S.row_stride, (long long)S.image_stride, rowlen, imgh, f->bc != 0, staged);
         vk_tex_wrote(im, c->tex, 3, d); }
     else { vkCmdCopyImageToBuffer(cb, im->img, VK_IMAGE_LAYOUT_GENERAL, b, 1, &r);
+        if (staged) { vk_img_barrier_all(cb); VkBufferCopy back = {r.bufferOffset, go, span}; vkCmdCopyBuffer(cb, b, gb, 1, &back); }
         void vk_gpu_wrote(uint64_t a, uint64_t n); vkpool_t *p = vk_pool_of(c->src, 1); vk_gpu_wrote(c->src, p ? p->hi - c->src : 1); }   // (to the pool's end: the copy's extent in memory is not worked out here)
     vk_img_barrier_all(cb);
 }
```

## Deviations from Plan

None in the code: the plan was executed as written.

The per-task commit protocol was replaced by the plan's `<repository_state_rules>`, so there are no task commits.

## Known Limits

- A misaligned copy whose span crosses two chunks of a memory pool has no single buffer, so `vk_buf_at` refuses it and the copy is skipped with the `[RED]` line.
- `build.py` prints compiler output only for failed files, so a compiler warning in the new code would not show in the compile log.

## Self-Check: PASSED

- Found: `tests/test_vk_copy_span.py`, `nxnative/dm/android/gfx_vk_exec.c`, this summary.
- All 44 diff lines above match the file's diff against the pre-task copy, and the file has not changed since the last verify.
- Nothing is staged and HEAD is still `6bc4ebfb`.

## Device verification (2026-11-18)

Installed over `org.nx2a.p4g.test` (versionCode 65537, Legion Y700, Adreno 840) with the save kept; the 14 save files match the pre-install backup.

- With `DM_VK_TEXLOG`: 384 block-compressed uploads over six load windows, 142 misaligned, 142 staged, no mismatch between the two, no `[RED]` line.
- 35 staged BC7 images read back from the GPU decode as real textures; aligned pairs 1705 and 1710 match their source byte for byte.
- Dojima living room (both saves), the April 11 bedroom from the original rainbow capture, the street and the classroom all render without confetti.
- Without diagnostics, the bedroom session ran at frame time p50 16.65 ms, 0 dropped in the last window.
- `python -m unittest discover tests`: 499 tests, OK.

Committed afterwards at the user's request, with only the `copy_span` and `copy_b2t` hunks of `gfx_vk_exec.c`. The unrelated Ocarina of Time changes in that file stay uncommitted, and the device build above included them.
