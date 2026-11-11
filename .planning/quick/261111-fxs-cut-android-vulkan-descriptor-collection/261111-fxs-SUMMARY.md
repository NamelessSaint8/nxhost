---
phase: quick-261111-fxs
plan: 01
subsystem: android-vulkan-backend
tags: [vk, atlas, descriptor-sets, memo, performance, mario-kart-world]
status: complete
requires: []
provides:
  - "vk_atlas_version(): one monotonic change detector for everything vk_atlas_descriptor rechecks per call"
  - "vk_image_ownership_gen(): accessor for gfx_vk_tex.c's g_image_ownership_gen"
  - "setmemo 3: atlas shaders reach the per-stage descriptor-set memo"
affects: [nxnative/dm/android/gfx_vk_exec.c stage_set, nxnative/dm/android/gfx_vk_atlas.c vk_atlas_descriptor]
tech-stack:
  added: []
  patterns: ["sum of non-decreasing counters as one exact version key", "live env switches cached per submission epoch"]
key-files:
  created: []
  modified:
    - nxnative/dm/android/gfx_vk_atlas.c
    - nxnative/dm/android/gfx_vk_exec.c
    - nxnative/dm/android/gfx_vk_tex.c
    - nxnative/dm/android/gfx_vk.h
decisions:
  - "Code left UNCOMMITTED in the working tree: the four files carry the user's in-progress work and gfx_vk_atlas.c is untracked (orchestrator override of per-task commits)"
  - "DM_VK_ATLAS_NATIVE_FILTER / DM_VK_ATLAS_RESIDENCY now take effect at the next submission instead of the next descriptor"
metrics:
  duration: "~15 min"
  completed: 2026-11-11
actuals:
  tokens: 5000    # chars/4 over the 20,182-byte combined diff
  tasks: 2
  commits: 0      # measured: git rev-list --count 0dca94f1..HEAD = 0; intentional, see "Uncommitted code changes"
plan_head_before: 0dca94f1fc92385dee45ae3f4fea0f16cfc5721e
plan_head_after: 0dca94f1fc92385dee45ae3f4fea0f16cfc5721e
---

# Quick 261111-fxs: Cut Android Vulkan descriptor collection for atlas shaders Summary

vk_atlas_descriptor no longer calls getenv or vkGetPhysicalDeviceFormatProperties per descriptor. Atlas shaders (Mario Kart World) can now use the per-stage descriptor-set memo as `setmemo 3`, keyed on a new `vk_atlas_version()`.

## Uncommitted code changes (read this first)

**Nothing in this task is committed.** The four edited files hold the user's large uncommitted work, and `nxnative/dm/android/gfx_vk_atlas.c` is untracked, so by the orchestrator's override no code was staged, committed, stashed, checked out, restored or reformatted. The edits are in the working tree only. Pre-edit copies are in `/private/tmp/claude-501/-Volumes-Data-Dev-nxhost/3182d3eb-7ffd-46d1-b7c2-74094192d992/scratchpad/pre/`. The combined diff below is the only durable record (also at `/private/tmp/claude-501/-Volumes-Data-Dev-nxhost/3182d3eb-7ffd-46d1-b7c2-74094192d992/scratchpad/fxs.diff`).

`git status` after the task: `M gfx_vk.h`, `M gfx_vk_exec.c`, `M gfx_vk_tex.c`, `?? gfx_vk_atlas.c`; `git diff --cached --name-only` is empty.

## What changed, per file (line numbers in the edited working tree)

**nxnative/dm/android/gfx_vk_atlas.c** (Task 1 + Task 2)
- L35: `va_context` gains `filter_linear`.
- L40: `static uint64_t g_atlas_gen=1;` with its why-comment.
- L67 `retire()` and L198 `plan_build()` (the `c->revision++` line): `__atomic_add_fetch(&g_atlas_gen,1,__ATOMIC_RELEASE)`.
- L127-128 `context()`: the format's linear-filter support is queried once per new context, after the layout `die()` check.
- L211-221 `atlas_native_filter(int usable, ...)`: getenv and format query removed. The existing comment is kept, with a note that the caller reads the switch once per submission.
- L235-236 `vk_atlas_descriptor()`: function-static `env_epoch`, `native_on` and `residency_big` are refreshed once per atlas epoch, with both getenv calls on one line.
- L254: the residency test uses `residency_big`.
- L263: `atlas_native_filter(native_on && c->filter_linear, image)`.
- L299-301: `uint64_t vk_atlas_version(void)` = `g_atlas_gen + nvn_sparse_gen() + nvn_dirty_now() + vk_image_ownership_gen()`.

**nxnative/dm/android/gfx_vk_tex.c** (Task 2)
- L149: `uint64_t vk_image_ownership_gen(void)`, an acquire load of `g_image_ownership_gen`.

**nxnative/dm/android/gfx_vk.h** (Task 2)
- L143: prototype `vk_image_ownership_gen`.
- L159: prototype `vk_atlas_version`.
- L196: the `setmemo` comment documents value 3.

**nxnative/dm/android/gfx_vk_exec.c** (Task 2)
- L1071-1073: three comment lines on the memo block covering setmemo 3, why the memo epoch equals the atlas epoch, the mute/census re-read, the benign verify hash difference, and the Toad's Factory evidence.
- L1075: `set_memo_t` gains `av`.
- L1079-1084 `set_memo_ok`: the RK_ATLAS / `flags & 16` exclusion is dropped, an `atlas` flag is accumulated, `setmemo = ok && ncb <= MEMO_CB ? (atlas ? 3 : 1) : 2`, and it returns `setmemo != 2`. All other exclusions are unchanged.
- L1088 `set_memo_get`: `|| (s->setmemo == 3 && m->av != vk_atlas_version())`. setmemo 1 shaders never evaluate it.
- L1104 `stage_set`: `gav = memo && s->setmemo == 3 ? vk_atlas_version() : 0` is captured before collecting.
- L1223-1224: the verify `[RED]` line also prints `atlas %#llx / %#llx` (g_num_atlas, vam).
- L1226: the memo store sets `m->av = gav`.

## Verification

- Pre-edit baseline: `build.py --only-compile` printed `compiled 196 sources, 0 failed`, with 0 warning and 0 error lines (`build-check.baseline2.log`).
- Task 1 gate: **TASK1-OK**. Compile: `compiled 196 sources, 0 failed`, no warnings or errors.
- Task 2 gate: **TASK2-OK**. Compile: `compiled 196 sources, 0 failed`, 0 `warning:`/`error:` lines. `python3 -m unittest tests.test_architecture`: `Ran 1 test ... OK`. Nothing under `nxnative/` is staged, and `gfx_vk_atlas.c` is still `??`.
- All build output went to `/private/tmp/claude-501/-Volumes-Data-Dev-nxhost/3182d3eb-7ffd-46d1-b7c2-74094192d992/scratchpad/build-check` (logs `build-check.t1.log`, `build-check.t2.log`). No repo build folder was touched.

## Not done here

- No on-device run: no device was connected, so neither correctness nor speed is measured.
- No new unit test. `stage_set` needs the full Vulkan backend; `DM_VK_X_SETVERIFY=1` is the self-check.
- STATE.md and ROADMAP.md were not updated or committed; the orchestrator handles that.

## Device follow-up (the user's next step)

1. Build and install a test package per the nx2android-dev skill. Ask before installing, and use a `.test` package beside the user's own app.
2. Correctness: run with `DM_VK_X_SETVERIFY=1` at the parked Toad's Factory camera for several 600-frame reports. Pass means "memo differences 0" in the "replay per frame (last 600)" line and no "[RED] descriptor set memo" lines. If `[RED]` lines appear only for atlas shaders and only the hash differs (um, im, atlas masks and dynamic offsets the same), it may be the benign metadata re-copy named in the comment. Confirm with a `DM_VK_X_NOSETMEMO=1` A/B screenshot of the same frame before trusting it.
3. Speed: run A/B/A at the same camera, default vs `DM_VK_X_NOSETMEMO=1` (live). Compare "collecting ms", "descriptor sets ms" and "kept per stage a frame" in the 600-frame replay line, plus settled 400-presentation FPS windows. Record results in `nxnative/dm/games/0400C3F00006E000/README.md` only after measuring. That file has the user's uncommitted edits, so add to it and do not rewrite it.
4. Risk to watch: the atlas memo invalidates on every first CPU write to a protected page anywhere (`nvn_dirty_now`) and on every sparse remap. If "kept per stage" barely rises, measure that churn next.

## Deviations from Plan

None in code; the plan was executed as written. One process deviation: no per-task commits and `commits: 0`, as the orchestrator's override requires. The STATE.md updates were left to the orchestrator.

## Threat Flags

None. The change adds no new surface beyond the plan's threat model. T-fxs-01 and T-fxs-02 are mitigated as planned: the version key is captured before collecting, SETVERIFY prints the atlas masks, and the first draw of each submission always collects.

## Uncommitted code changes: full diff against the pre-edit copies

```diff
--- a/nxnative/dm/android/gfx_vk_atlas.c
+++ b/nxnative/dm/android/gfx_vk_atlas.c
@@ -32,11 +32,12 @@
     uint32_t tw,th,tail,count,slots,capacity,layers; va_cell *cell; nvn_hmap by_content;
     uint32_t *table; uint64_t gen,stamp,used_fence,used_frame,revision,referenced_revision,reported_revision;
     uint64_t mapped_entries,mapped_native_pages,total_native_pages;
-    uint64_t checked_gen,checked_stamp,cpu_gen,cpu_epoch; int cpu_readable;
+    uint64_t checked_gen,checked_stamp,cpu_gen,cpu_epoch; int cpu_readable,filter_linear;
     VkImage image; VkDeviceMemory memory; VkDeviceSize allocated; va_view *views;
     struct { view_t view; samp_par sampler; uint64_t epoch,revision; VkImageView image; VkDescriptorBufferInfo meta; } binding;
 } va_context;
 static va_context *g_context;
+static uint64_t g_atlas_gen=1;   // bumped when any context's table revision changes or its image is retired: a memoized descriptor set (gfx_vk_exec.c) cannot outlive the view or metadata it names
 static pthread_mutex_t g_atlas_mu=PTHREAD_MUTEX_INITIALIZER;
 static VkCommandPool g_pool;
 static VkCommandBuffer g_cmd;
@@ -63,7 +64,7 @@
 static void retire(va_context *c) {
     if(c->image){va_retired *r=calloc(1,sizeof*r);r->image=c->image;r->memory=c->memory;r->views=c->views;r->bytes=c->allocated;r->fence=c->used_fence;
         if(r->fence<=vk_fence_done())resource_free(r);else{r->next=g_retired;g_retired=r;}}
-    c->views=NULL;c->image=VK_NULL_HANDLE;c->memory=VK_NULL_HANDLE;c->allocated=0;c->binding.epoch=0;
+    c->views=NULL;c->image=VK_NULL_HANDLE;c->memory=VK_NULL_HANDLE;c->allocated=0;c->binding.epoch=0;__atomic_add_fetch(&g_atlas_gen,1,__ATOMIC_RELEASE);
 }
 int vk_atlas_enabled(void) { static int enabled=-1;int value=__atomic_load_n(&enabled,__ATOMIC_ACQUIRE);if(value<0){const char *p=getenv("DM_VK_ATLAS");value=p && atoi(p);__atomic_store_n(&enabled,value,__ATOMIC_RELEASE);}return value; }
 static int check_cache_enabled(void) {
@@ -123,6 +124,8 @@
     va_context *c=calloc(1,sizeof*c);c->pool=t->pool;c->pool_generation=t->pool->generation;c->off=t->off;c->desc=t->d;c->layout=t->L;c->by_content.klen=sizeof(va_key);
     c->tail=nvn_tex_sparse_tiles(&t->d,&c->tw,&c->th,&(uint32_t){0});
     if(!c->tw || !c->th || t->d.levels>VA_LEVELS || (t->d.target!=NVN_TEXTURE_TARGET_2D_ARRAY && t->d.target!=NVN_TEXTURE_TARGET_2D) || t->d.samples>1 || (c->tail<t->d.levels && t->L.layer_size-nvn_tex_level_offset(&t->d,c->tail)>65536))die("[RED] [vk] unsupported atlas layout");
+    // Once per context (its format never changes): this query used to run for every descriptor.
+    VkFormatProperties properties;vkGetPhysicalDeviceFormatProperties(V.pd,vk_fmt(t->d.format)->vk,&properties);c->filter_linear=!!(properties.optimalTilingFeatures&VK_FORMAT_FEATURE_SAMPLED_IMAGE_FILTER_LINEAR_BIT);
     c->count=VA_HEADER;
     for(uint32_t mip=0;mip<t->d.levels;mip++){uint32_t w=t->d.width>>mip,h=t->d.height>>mip;if(!w)w=1;if(!h)h=1;uint64_t entries=(uint64_t)((w+c->tw-1)/c->tw)*((h+c->th-1)/c->th)*t->L.layers;if(entries>UINT32_MAX-c->count)die("[RED] [vk] atlas table too large");c->count+=(uint32_t)entries;}
     c->next=g_context;g_context=c;return c;
@@ -192,7 +195,7 @@
                 g_copy[g_ncopy++]=(VkBufferImageCopy){g_stage_used,0,0,{VK_IMAGE_ASPECT_COLOR_BIT,0,id/(VA_GRID*VA_GRID),1},{(int32_t)((id%VA_GRID)*c->tw),(int32_t)(((id/VA_GRID)%VA_GRID)*c->th),0},{upload_w,upload_h,1}};g_stage_used+=bytes;}
         }
     }
-    upload_flush(c);free(source);free(linear);c->table=table;c->gen=gen;c->stamp=stamp;c->revision++;
+    upload_flush(c);free(source);free(linear);c->table=table;c->gen=gen;c->stamp=stamp;c->revision++;__atomic_add_fetch(&g_atlas_gen,1,__ATOMIC_RELEASE);
     c->mapped_entries=mapped_entries;c->mapped_native_pages=mapped_pages;c->total_native_pages=total_pages;
     if(!c->used_fence && c->slots)cache_size(c,c->slots,f);   // startup deduplication can release the conservative allocation immediately
 }
@@ -205,13 +208,13 @@
 }
 // Physical atlas images have one mip. Guest filter/LOD rules remain in metadata;
 // this sampler is used only by the shader's same-tile bilinear fast path.
-static int atlas_native_filter(const vkfmt_t *f,VkDescriptorImageInfo *image){
+static int atlas_native_filter(int usable,VkDescriptorImageInfo *image){
     static VkSampler sampler;
     // Live A/B from the diagnostic console; descriptor metadata is rebuilt for
     // each submission, so the hardware bilinear fast path can be priced there.
-    const char *e=getenv("DM_VK_ATLAS_NATIVE_FILTER");if(!e || !atoi(e))return 0;
-    VkFormatProperties properties;vkGetPhysicalDeviceFormatProperties(V.pd,f->vk,&properties);
-    if(!(properties.optimalTilingFeatures&VK_FORMAT_FEATURE_SAMPLED_IMAGE_FILTER_LINEAR_BIT))return 0;
+    // The caller reads DM_VK_ATLAS_NATIVE_FILTER once per submission and passes
+    // it with the context's linear-filter support.
+    if(!usable)return 0;
     if(!sampler){VkSamplerCreateInfo ci={.sType=VK_STRUCTURE_TYPE_SAMPLER_CREATE_INFO,.magFilter=VK_FILTER_LINEAR,.minFilter=VK_FILTER_LINEAR,.mipmapMode=VK_SAMPLER_MIPMAP_MODE_NEAREST,.addressModeU=VK_SAMPLER_ADDRESS_MODE_CLAMP_TO_EDGE,.addressModeV=VK_SAMPLER_ADDRESS_MODE_CLAMP_TO_EDGE,.addressModeW=VK_SAMPLER_ADDRESS_MODE_CLAMP_TO_EDGE,.maxAnisotropy=1};VKCHK(vkCreateSampler(V.dev,&ci,NULL,&sampler));}
     image->sampler=sampler;return 1;
 }
@@ -229,6 +232,8 @@
         if(!compressed){pthread_mutex_unlock(&g_atlas_mu);return 0;}
         die("[RED] [vk] atlas sampler/view mode is not implemented (filter %u/%u wrap %u/%u bias %g aniso %g compare %u reduction %u)",sp.minf,sp.magf,sp.ws,sp.wt,sp.lod_bias,sp.aniso,sp.cmp_mode,sp.reduction);}
     va_context *c=context(t);uint64_t epoch=mtl_last_fence()+1,gen=nvn_sparse_gen(),stamp=nvn_dirty_now();int cached=check_cache_enabled();
+    // Live switches, read once per submission instead of per descriptor (under g_atlas_mu); this also keeps the sampler and data[15] consistent within it.
+    static uint64_t env_epoch;static int native_on,residency_big;if(env_epoch!=epoch){const char *e=getenv("DM_VK_ATLAS_NATIVE_FILTER");native_on=e && atoi(e);e=getenv("DM_VK_ATLAS_RESIDENCY");residency_big=e && !strcmp(e,"big");env_epoch=epoch;}
     // Finalizing physical storage drains replay but does not bump the mapping
     // generation. Recheck readability each submission as well as each remap.
     // GPU ownership above is always checked, including within a submission.
@@ -246,8 +251,7 @@
     }
     // DM_VK_ATLAS_RESIDENCY=big (live): census large virtual textures after
     // their current page tables are built; distinct cells reflect deduplication.
-    const char *residency=getenv("DM_VK_ATLAS_RESIDENCY");
-    if(residency && !strcmp(residency,"big") && t->d.width>=8192 && t->d.height>=8192 && t->L.layers>=64 && c->reported_revision!=c->revision){
+    if(residency_big && t->d.width>=8192 && t->d.height>=8192 && t->L.layers>=64 && c->reported_revision!=c->revision){
         uint32_t active=0;for(uint32_t i=0;i<c->slots;i++)if(c->cell[i].refs)active++;
         VKLOG("atlas residency: serial %llu format %#x %ux%ux%u levels %u mapped-pages %llu/%llu mapped-entries %llu/%u unique-cells %u packed-bytes %llu revision %llu",
             (unsigned long long)t->serial,t->d.format,t->d.width,t->d.height,t->L.layers,t->d.levels,
@@ -256,7 +260,7 @@
         c->reported_revision=c->revision;
     }
     if(c->used_fence!=epoch || c->referenced_revision!=c->revision){for(uint32_t i=VA_HEADER;i<c->count;i++)if(c->table[i]!=VA_MISSING)c->cell[c->table[i]].fence=epoch;c->used_fence=epoch;c->referenced_revision=c->revision;}
-    int native_filter=atlas_native_filter(f,image);
+    int native_filter=atlas_native_filter(native_on && c->filter_linear,image);
     c->used_frame=g_tex_frame;view_t v={0};if(view)v=*view;
     if(c->binding.epoch==epoch && c->binding.revision==c->revision && !memcmp(&c->binding.view,&v,sizeof v) && !memcmp(&c->binding.sampler,&sp,sizeof sp)){image->imageView=c->binding.image;image->imageLayout=VK_IMAGE_LAYOUT_GENERAL;*meta=c->binding.meta;pthread_mutex_unlock(&g_atlas_mu);return 1;}
     VkComponentMapping swz=view_swizzle(t,view,f);va_view *vv=c->views;while(vv && memcmp(&vv->swz,&swz,sizeof swz))vv=vv->next;
@@ -292,3 +296,6 @@
 void vk_atlas_stats(uint64_t *allocated,uint64_t *uploaded,uint64_t *reused,uint64_t *metadata){pthread_mutex_lock(&g_atlas_mu);collect();*allocated=g_allocated;*uploaded=g_uploaded;*reused=g_reused;*metadata=g_metadata;pthread_mutex_unlock(&g_atlas_mu);}
 
 uint64_t vk_atlas_peak_bytes(void){pthread_mutex_lock(&g_atlas_mu);uint64_t peak=g_peak_allocated;pthread_mutex_unlock(&g_atlas_mu);return peak;}
+// What vk_atlas_descriptor rechecks per call besides the texture, view, sampler and submission: tables and images, GPU ownership, sparse remaps and
+// first CPU writes to protected pages. Every term only increases, so the sum is unchanged only if each term is (gfx_vk_exec.c set_memo_get, setmemo 3).
+uint64_t vk_atlas_version(void){return __atomic_load_n(&g_atlas_gen,__ATOMIC_ACQUIRE)+nvn_sparse_gen()+nvn_dirty_now()+vk_image_ownership_gen();}
--- a/nxnative/dm/android/gfx_vk_exec.c
+++ b/nxnative/dm/android/gfx_vk_exec.c
@@ -1068,21 +1068,24 @@
 // first build gave them: the fence it names is the same for the whole submission. Not for compute (its driver segment holds the dispatch size and its storage
 // buffers are marked written), nor for a shader that reads handles or addresses from uniform buffer memory (that memory changes under the same bindings).
 // DM_VK_X_NOSETMEMO=1 (live): always collected. DM_VK_X_SETVERIFY=1 (live): one hit in 64 is collected anyway and compared, [RED] on a difference
+// Atlas shaders (setmemo 3; Mario Kart World Toad's Factory: 886 of 975 main-pass draws, about 12.7 ms a frame collecting) are also keyed on vk_atlas_version.
+// The memo epoch is the atlas epoch (vk_exec_reset is the only g_set_epoch++, the commit the only ++g_fence), so a submission's first draw collects and marks the
+// cells' fences, used_fence and used_frame; mute/census are re-read there too. A verify hash difference alone can be atlas metadata copied again (as good).
 enum { MEMO_CB = 16 };
-typedef struct { vkshader_t *s; uint64_t epoch, bind, ubo, ubd, tex, samp, h, um, im, atlas; uint32_t pool, binst, dofs[96]; int ncb; uint8_t ci[MEMO_CB], cpos[MEMO_CB]; VkDescriptorBufferInfo cd[MEMO_CB]; VkDescriptorSet set; } set_memo_t;
+typedef struct { vkshader_t *s; uint64_t epoch, bind, ubo, ubd, tex, samp, h, um, im, atlas, av; uint32_t pool, binst, dofs[96]; int ncb; uint8_t ci[MEMO_CB], cpos[MEMO_CB]; VkDescriptorBufferInfo cd[MEMO_CB]; VkDescriptorSet set; } set_memo_t;
 static set_memo_t g_smemo[8]; static uint64_t g_bind_gen[8], g_ubo_gen[8];   // a stage's handles or storage buffers changed (bind_handles_rec, OP_BIND_SSBO), its uniform buffers (OP_BIND_UBO)
 uint64_t g_set_memo, g_set_memo_bad;   // memo hits, and differences the verify mode found
 extern uint64_t g_ubd_gen; uint32_t vk_pool_gen(void);
 static int set_memo_ok(vkshader_t *s) {
-    if (!s->setmemo) { int ok = 1, ncb = 0;
-        for (int i = 0; i < s->nbind; i++) { const dmsv_bind *b = &s->b[i]; ncb += b->kind == RK_CBUF;
-            ok &= b->kind != RK_ATLAS && !(b->flags & 16) && b->kind != RK_SBUF_UBO && b->kind != RK_UBO_PTR && b->kind != RK_TEX_UBO && b->kind != RK_IMG_UBO && b->kind != RK_TBUF_UBO && b->samp != RS_UBO && i < 256; }
-        s->setmemo = ok && ncb <= MEMO_CB ? 1 : 2; }
-    return s->setmemo == 1;
+    if (!s->setmemo) { int ok = 1, ncb = 0, atlas = 0;
+        for (int i = 0; i < s->nbind; i++) { const dmsv_bind *b = &s->b[i]; ncb += b->kind == RK_CBUF; atlas |= b->kind == RK_ATLAS || (b->flags & 16);
+            ok &= b->kind != RK_SBUF_UBO && b->kind != RK_UBO_PTR && b->kind != RK_TEX_UBO && b->kind != RK_IMG_UBO && b->kind != RK_TBUF_UBO && b->samp != RS_UBO && i < 256; }
+        s->setmemo = ok && ncb <= MEMO_CB ? (atlas ? 3 : 1) : 2; }
+    return s->setmemo != 2;
 }
 static int set_memo_get(int st, vkshader_t *s, uint32_t *dofs) {
     set_memo_t *m = &g_smemo[st];
-    if (m->s != s || m->epoch != g_set_epoch || m->bind != g_bind_gen[st] || m->tex != g_tex_gen || m->samp != __atomic_load_n(&g_samp_gen, __ATOMIC_ACQUIRE) || m->pool != vk_pool_gen() || m->binst != g_draw_binst) return 0;
+    if (m->s != s || m->epoch != g_set_epoch || m->bind != g_bind_gen[st] || m->tex != g_tex_gen || m->samp != __atomic_load_n(&g_samp_gen, __ATOMIC_ACQUIRE) || m->pool != vk_pool_gen() || m->binst != g_draw_binst || (s->setmemo == 3 && m->av != vk_atlas_version())) return 0;
     if (m->ubo != g_ubo_gen[st] || m->ubd != g_ubd_gen) {   // the constant buffers again: most draws move only their offsets
         for (int c = 0; c < m->ncb; c++) { VkDescriptorBufferInfo d; cbuf_desc(st, s, &s->b[m->ci[c]], &d);
             if (d.buffer != m->cd[c].buffer || d.range != m->cd[c].range || (m->cpos[c] == 0xff && d.offset != m->cd[c].offset)) return 0;
@@ -1098,7 +1101,7 @@
     uint32_t vd[96]; uint64_t vum = 0, vim = 0,vam=0;   // verify: what the memo gave
     if (memo && set_memo_get(st, s, dofs)) { static unsigned nv; if (!g_x_setverify || ++nv % 64) { g_set_memo++; return g_smemo[st].set; }
         verify = 1; memcpy(vd, dofs, sizeof *dofs * (size_t)s->ndyn); vum = g_num_um; vim = g_num_im;vam=g_num_atlas; }
-    uint64_t gtex = g_tex_gen, gsamp = __atomic_load_n(&g_samp_gen, __ATOMIC_ACQUIRE); uint32_t gpool = vk_pool_gen();   // before collecting: a change racing it (game thread) leaves the memo outdated
+    uint64_t gtex = g_tex_gen, gsamp = __atomic_load_n(&g_samp_gen, __ATOMIC_ACQUIRE), gav = memo && s->setmemo == 3 ? vk_atlas_version() : 0; uint32_t gpool = vk_pool_gen();   // before collecting: a change racing it (game thread) leaves the memo outdated
     VkDescriptorSet set = VK_NULL_HANDLE; struct { uint32_t b, o; int i; } dp[96]; int nd = 0; uint64_t tb0 = tick();
     VkWriteDescriptorSet w[96]; VkDescriptorBufferInfo bi[96], atlas_pair[96]; VkDescriptorImageInfo ii[96 * 4]; VkBufferView bv[96]; uint8_t atlas_pair_ready[96] = {0}; uint32_t nw = 0, nii = 0;
     int ncb = 0; uint8_t mci[MEMO_CB]; VkDescriptorBufferInfo mcd[MEMO_CB];   // the constant buffers, for the memo
@@ -1217,10 +1220,10 @@
     // verify: the same content (hash), integer-texel bindings and dynamic offsets as the memo gave. A lone difference in dofs alone can be a driver segment
     // copied again after its g_drvc entry was taken by another (the memo's copy is as good); anything repeated is a dependency the memo misses
     if (verify && (h != g_smemo[st].h || g_num_um != vum || g_num_im != vim || g_num_atlas!=vam || memcmp(vd, dofs, sizeof *dofs * (size_t)s->ndyn))) { g_set_memo_bad++; static int n;
-        if (n++ < 20) VKLOG("[RED] descriptor set memo: stage %d shader %016llx: a fresh set differs from the memo's (hash %016llx / %016llx, um %#llx / %#llx, im %#llx / %#llx, dynamic offsets %s)", st, (unsigned long long)s->key,
-                            (unsigned long long)h, (unsigned long long)g_smemo[st].h, (unsigned long long)g_num_um, (unsigned long long)vum, (unsigned long long)g_num_im, (unsigned long long)vim, memcmp(vd, dofs, sizeof *dofs * (size_t)s->ndyn) ? "differ" : "same"); }
+        if (n++ < 20) VKLOG("[RED] descriptor set memo: stage %d shader %016llx: a fresh set differs from the memo's (hash %016llx / %016llx, um %#llx / %#llx, im %#llx / %#llx, atlas %#llx / %#llx, dynamic offsets %s)", st, (unsigned long long)s->key,
+                            (unsigned long long)h, (unsigned long long)g_smemo[st].h, (unsigned long long)g_num_um, (unsigned long long)vum, (unsigned long long)g_num_im, (unsigned long long)vim, (unsigned long long)g_num_atlas, (unsigned long long)vam, memcmp(vd, dofs, sizeof *dofs * (size_t)s->ndyn) ? "differ" : "same"); }
     if (memo) { set_memo_t *m = &g_smemo[st];   // (set_memo_ok: at most MEMO_CB constant buffers)
-        m->s = s; m->epoch = g_set_epoch; m->bind = g_bind_gen[st]; m->ubo = g_ubo_gen[st]; m->ubd = g_ubd_gen; m->tex = gtex; m->samp = gsamp; m->pool = gpool; m->binst = g_draw_binst;
+        m->s = s; m->epoch = g_set_epoch; m->bind = g_bind_gen[st]; m->ubo = g_ubo_gen[st]; m->ubd = g_ubd_gen; m->tex = gtex; m->samp = gsamp; m->pool = gpool; m->binst = g_draw_binst; m->av = gav;
         m->h = h; m->um = g_num_um; m->im = g_num_im;m->atlas=g_num_atlas; m->set = set; memcpy(m->dofs, dofs, sizeof *dofs * (size_t)s->ndyn); m->ncb = ncb; memcpy(m->ci, mci, (size_t)ncb); memcpy(m->cd, mcd, sizeof *mcd * (size_t)ncb);
         for (int c = 0; c < ncb; c++) { m->cpos[c] = 0xff; for (int j = 0; j < nd; j++) if (dp[j].i == mci[c]) m->cpos[c] = (uint8_t)j; } }
     return set;
--- a/nxnative/dm/android/gfx_vk_tex.c
+++ b/nxnative/dm/android/gfx_vk_tex.c
@@ -146,6 +146,7 @@
 static nvn_hmap g_by_serial = {.klen = sizeof(uint64_t)};  // serial → vkimg_t* (images with no storage key: no pool memory)
 static pthread_mutex_t g_img_mu = PTHREAD_MUTEX_INITIALIZER;
 static _Atomic uint64_t g_image_ownership_gen=1;
+uint64_t vk_image_ownership_gen(void) { return atomic_load_explicit(&g_image_ownership_gen,memory_order_acquire); }   // gfx_vk_atlas.c vk_atlas_version
 void vk_tex_note_use(vkimg_t *im){
     if(!im)return;extern uint64_t g_tex_frame;uint64_t fence=mtl_last_fence()+(vk_sub_open()?1:0);
     if(!im->touch_ns || im->used!=g_tex_frame || im->last_use!=fence){struct timespec now;clock_gettime(CLOCK_MONOTONIC,&now);im->touch_ns=(uint64_t)now.tv_sec*1000000000ull+now.tv_nsec;}
--- a/nxnative/dm/android/gfx_vk.h
+++ b/nxnative/dm/android/gfx_vk.h
@@ -140,6 +140,7 @@
 };
 vkimg_t *vk_tex(const tex_t *t);                                 // the image of a texture object (created, uploaded or refreshed as needed)
 int vk_tex_gpu_content(const tex_t *t); // GPU destinations, including sparse versions and overlapping aliases
+uint64_t vk_image_ownership_gen(void);   // changes whenever an image's GPU ownership changes or an image is created or dropped (vk_atlas_version)
 void vk_tex_mark_gpu_write(vkimg_t *im);
 void vk_tex_note_use(vkimg_t *im);
 void vk_lrz_forget(vkimg_t *im);                                 // an image is being dropped: the pass code forgets it (gfx_vk_exec.c)
@@ -155,6 +156,7 @@
 void vk_atlas_drop_pool(const void *pool);
 void vk_atlas_sweep(uint64_t frame);
 void vk_atlas_stats(uint64_t *allocated, uint64_t *uploaded, uint64_t *reused, uint64_t *metadata);
+uint64_t vk_atlas_version(void);   // changes whenever an atlas descriptor could change for the same texture, view and sampler (key of the setmemo 3 memo)
 extern __thread VkFormat vk_view_fmt; extern __thread uint32_t vk_view_layers;   // the format and layer count of the view vk_tex_view last returned on this thread
 VkImageView vk_dummy_view(int dim, int arrayed, int ms, int storage, int is_int);
 VkSampler vk_dummy_sampler(void);
@@ -191,7 +193,7 @@
                                                                                     // that declare the vec4 outputs xo (bit = location) the next stage reads, and (fd) that write gl_FragDepth = gl_FragCoord.z
     int depth_repl;                     // a fragment shader that writes gl_FragDepth (DepthReplacing / DepthGreater / DepthLess)
     uint32_t in_locs, out_locs;         // the vec4 (or per-vertex vec4) inputs and outputs it declares, by location
-    int setmemo;                        // gfx_vk_exec.c stage_set: 1 its set may be memoized per stage, 2 not (it reads handles or addresses from uniform buffer memory), 0 not known yet
+    int setmemo;                        // gfx_vk_exec.c stage_set: 1 its set may be memoized per stage, 3 too and also keyed on vk_atlas_version (it has atlas bindings), 2 not (it reads handles or addresses from uniform buffer memory), 0 not known yet
 } vkshader_t;
 vkshader_t *vk_shader(uint64_t key, int stage);   // NULL when the bundle has no such shader
 VkShaderModule vk_shader_module(vkshader_t *s, uint64_t um, uint64_t im, uint32_t xo, int fd, uint32_t pm, uint32_t ou, uint32_t oi);   // pm: per-primitive inputs; ou/oi: unsigned/signed attachment locations
```

## Self-Check: PASSED

- All four files exist and contain the planned symbols: `vk_atlas_version`, `vk_image_ownership_gen`, `g_atlas_gen`, `env_epoch`, `filter_linear`, `setmemo == 3`.
- No commits to check (0 by design); HEAD is unchanged at 0dca94f1.
