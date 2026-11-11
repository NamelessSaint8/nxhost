---
phase: quick-261111-fxs
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - nxnative/dm/android/gfx_vk_atlas.c
  - nxnative/dm/android/gfx_vk_exec.c
  - nxnative/dm/android/gfx_vk_tex.c
  - nxnative/dm/android/gfx_vk.h
autonomous: true
requirements: [QUICK-261111-fxs]

estimate:
  tokens: 70000
  raw_tokens: 70000
  tasks: 2
  confidence: low

must_haves:
  truths:
    - "vk_atlas_descriptor makes no getenv call and no vkGetPhysicalDeviceFormatProperties call on its per-descriptor path: the two DM_VK_ATLAS_* switches are read once per submission (atlas epoch), the format's linear-filter support once per atlas context"
    - "A shader with atlas bindings (an RK_ATLAS binding or a texture binding with flags & 16) can take the per-stage descriptor-set memo (set_memo_get) when nothing it depends on changed since the stage's last set in the same submission"
    - "An atlas table rebuild or image replacement (plan_build, retire), a GPU-ownership change, a sparse remap (nvn_sparse_gen) or a first CPU write to a protected page (nvn_dirty_now) between two draws makes the next atlas-shader draw collect again (memo miss)"
    - "Shaders without atlas bindings keep exactly the memo keys they have today (no new invalidation source for them)"
    - "DM_VK_X_NOSETMEMO=1 still disables the memo and DM_VK_X_SETVERIFY=1 still collects 1 hit in 64 and logs [RED] on a difference, now also for atlas shaders, with the atlas binding masks printed"
    - "Every Android source compiles (build.py --only-compile: 0 failed, 0 warnings) and tests.test_architecture passes"
    - "None of the four files is staged or committed; gfx_vk_atlas.c stays untracked; no other line of the user's uncommitted work is changed"
  artifacts:
    - path: nxnative/dm/android/gfx_vk_atlas.c
      provides: "per-epoch env cache, per-context filter_linear, g_atlas_gen bumped in plan_build and retire, vk_atlas_version()"
      contains: "vk_atlas_version"
    - path: nxnative/dm/android/gfx_vk_tex.c
      provides: "vk_image_ownership_gen() accessor for the static g_image_ownership_gen"
      contains: "vk_image_ownership_gen"
    - path: nxnative/dm/android/gfx_vk_exec.c
      provides: "set_memo_ok admits atlas shaders as setmemo 3; set_memo_get/stage_set key them on vk_atlas_version"
      contains: "vk_atlas_version()"
    - path: nxnative/dm/android/gfx_vk.h
      provides: "prototypes vk_atlas_version, vk_image_ownership_gen; setmemo comment documents value 3"
      contains: "vk_atlas_version"
  key_links:
    - from: "gfx_vk_exec.c set_memo_get"
      to: "gfx_vk_atlas.c vk_atlas_version"
      via: "memo key field compared when s->setmemo == 3"
      pattern: "vk_atlas_version\\(\\)"
    - from: "gfx_vk_atlas.c vk_atlas_version"
      to: "gfx_vk_tex.c vk_image_ownership_gen, nvn_sparse_gen, nvn_dirty_now, g_atlas_gen"
      via: "sum of four monotonic counters"
      pattern: "vk_image_ownership_gen\\(\\)"
    - from: "gfx_vk_atlas.c plan_build / retire"
      to: "g_atlas_gen"
      via: "__atomic_add_fetch on every table revision and image retirement"
      pattern: "g_atlas_gen"
---

<objective>
Cut the Android Vulkan backend's descriptor-collection CPU for atlas shaders (Mario Kart World, title 0400C3F00006E000) in two independent steps:
(B, Task 1) remove the per-descriptor getenv and vkGetPhysicalDeviceFormatProperties calls from vk_atlas_descriptor;
(A, Task 2) let shaders with atlas bindings use the per-stage descriptor-set memo, keyed on everything vk_atlas_descriptor rechecks per call.

Purpose: the device measurement in nxnative/dm/games/0400C3F00006E000/README.md (lines 47-63) shows replay CPU at about 25-26 ms/frame, about 16 ms of it building descriptor sets and about 12.7-12.9 ms of that "collecting", for about 2,650 draws/frame; at Toad's Factory 886 of 975 main-pass draws are atlas-active and set_memo_ok excludes every one of them. The 30 FPS target needs this CPU back. This task targets the collecting cost only.

Output: small edits in four Android-only files, left UNCOMMITTED in the working tree (see the repository-state rule below), plus a SUMMARY.md that carries the full diff and the device follow-up recipe.
</objective>

<execution_context>
@~/.claude/gsd-core/workflows/execute-plan.md
@~/.claude/gsd-core/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@.claude/CLAUDE.md
@.claude/skills/nx2android-dev/SKILL.md
@nxnative/dm/games/0400C3F00006E000/README.md

Source regions (line numbers verified against the working tree on 2026-11-11; the user has uncommitted work in these files, so re-locate by identifier, not by number):
- nxnative/dm/android/gfx_vk_atlas.c (untracked, 294 lines): va_context struct ~L29-38 (cpu_readable on ~L35); retire() ~L63-67; context() ~L121-129; plan_build() ~L137-198 (c->revision++ on ~L195); atlas_native_filter() ~L206-217; vk_atlas_descriptor() ~L218-277 (epoch computed ~L231, DM_VK_ATLAS_RESIDENCY getenv ~L249-250, atlas_native_filter call ~L259, binding-cache early return ~L261).
- nxnative/dm/android/gfx_vk_exec.c: tex_desc_for ~L982-1020; memo comment block ~L1063-1070; set_memo_t ~L1072; local prototypes line "extern uint64_t g_ubd_gen; uint32_t vk_pool_gen(void);" ~L1075; set_memo_ok ~L1076-1082 (exclusion on ~L1079); set_memo_get ~L1083-1093; stage_set ~L1095 (version capture line "uint64_t gtex = g_tex_gen, ..." ~L1101; verify [RED] line ~L1219-1221; memo store ~L1222-1225).
- nxnative/dm/android/gfx_vk_tex.c: "static _Atomic uint64_t g_image_ownership_gen=1;" ~L148 (bumped in vk_tex_mark_gpu_write ~L156, img_drop_mode ~L414, image creation ~L470, gpu_w clear ~L662; read by vk_tex_gpu_content's owner cache ~L604).
- nxnative/dm/android/gfx_vk.h: vk_tex_gpu_content prototype ~L142; vk_atlas_* prototypes ~L152-157; vkshader_t "int setmemo;" comment ~L194.

Facts already verified by the planner (do not re-derive; cite in comments where useful):
- Memo epoch equals atlas epoch. g_set_epoch++ happens only in vk_exec_reset (gfx_vk_exec.c ~L215), called only from submission begin (gfx_vk_core.c ~L934); g_fence changes only at the commit's "++g_fence" (gfx_vk_core.c ~L1158). So within one g_set_epoch, mtl_last_fence()+1 (the atlas epoch) is constant, and the first stage_set of a shader in a submission always misses the memo and calls vk_atlas_descriptor.
- DM_VK_ATLAS_MUTE / DM_VK_ATLAS_CENSUS_SHADER are re-read by x_read() inside vk_exec_reset, at the same moment g_set_epoch++ happens, so a memo hit can never carry a stale mute/census state across a toggle: no lag at all.
- nvn_dirty_now() (nvn_dirty.c g_now), nvn_sparse_gen() (hle_nvn.c g_vp_gen) and g_image_ownership_gen change only by atomic fetch_add; they never decrease. A sum of non-decreasing counters read in order is unchanged only if each counter is unchanged, so one summed version is an exact change detector.
- g_image_ownership_gen is already the key of vk_tex_gpu_content's own owner cache (with nvn_sparse_gen), and image creation bumps it, so keying the memo on it is never staler than that cache.
- Baselines at HEAD+working tree (planner run): build.py --only-compile into the scratch dir printed "compiled 196 sources, 0 failed", 0 "warning:" and 0 "error:" lines; python3 -m unittest tests.test_architecture: OK. Grep-gate baselines are listed in each task's verify.

<interfaces>
New, to be created (exact signatures):
- gfx_vk_tex.c: uint64_t vk_image_ownership_gen(void);   returns atomic_load_explicit(&g_image_ownership_gen, memory_order_acquire)
- gfx_vk_atlas.c: uint64_t vk_atlas_version(void);   returns g_atlas_gen (atomic acquire load) + nvn_sparse_gen() + nvn_dirty_now() + vk_image_ownership_gen()
- gfx_vk.h: both prototypes, beside vk_tex_gpu_content and the vk_atlas_* block respectively
Existing, used unchanged: nvn_sparse_gen() (declared locally at gfx_vk_atlas.c ~L20), nvn_dirty_now() (nvn_dirty.h, included by gfx_vk_atlas.c), mtl_last_fence(), vk_pool_gen().
</interfaces>
</context>

<repository_state_rules>
HARD RULES for the executor (the user has in-progress work in these exact files):
1. gfx_vk_exec.c, gfx_vk_tex.c and gfx_vk.h are modified-uncommitted, gfx_vk_atlas.c is UNTRACKED. Never run git add, git commit, git stash, git checkout, git restore or any formatter on them. Code changes stay in the working tree, uncommitted; say so in SUMMARY.md.
2. Use the Edit tool with scoped replacements only. Do not reflow, reindent or touch any line outside the hunks this plan names.
3. Work on the main tree; no worktrees.
4. Before the first edit, copy the four files unchanged to /private/tmp/claude-501/-Volumes-Data-Dev-nxhost/3182d3eb-7ffd-46d1-b7c2-74094192d992/scratchpad/pre/ (create the folder), and re-run the baseline compile (Task 1 verify's build command, output to build-check.baseline2.log) to confirm "0 failed" and no warnings before you change anything. If the baseline now fails, stop and report: the failure is the user's, not yours.
5. Build output goes only to the scratch build-check folder named in the verify commands; never omit --out (build.py's default writes into nxnative/dm/android/out/ inside the repo).
6. Only the quick task's own .planning files may be committed, by explicit path, never with git add -A or git add . (another session may have uncommitted STATE.md/ROADMAP.md edits; do not revert them).
</repository_state_rules>

<tasks>

<task type="auto">
  <name>Task 1: Hoist getenv and the format-property query out of vk_atlas_descriptor's per-descriptor path</name>
  <files>nxnative/dm/android/gfx_vk_atlas.c</files>
  <read_first>
    - nxnative/dm/android/gfx_vk_atlas.c (whole file, 294 lines; focus va_context, context(), atlas_native_filter(), vk_atlas_descriptor())
  </read_first>
  <action>
Finding B: before its own binding-cache early return (~L261), vk_atlas_descriptor runs getenv("DM_VK_ATLAS_RESIDENCY") on every call, and atlas_native_filter runs getenv("DM_VK_ATLAS_NATIVE_FILTER") plus vkGetPhysicalDeviceFormatProperties on every call. The device runs with native filtering on (README: restored after the A/B), so the query is on the hot path thousands of times a frame.

1. va_context: add an int field filter_linear next to cpu_readable (extend "int cpu_readable;" to "int cpu_readable,filter_linear;").
2. context(): when it creates a new context (after the existing die() check on the layout), query vkGetPhysicalDeviceFormatProperties(V.pd, vk_fmt(t->d.format)->vk, ...) once and store whether optimalTilingFeatures has VK_FORMAT_FEATURE_SAMPLED_IMAGE_FILTER_LINEAR_BIT in c->filter_linear. vk_fmt cannot be NULL here: vk_atlas_descriptor only reaches context() after vk_atlas_candidate (compressed) or the uncompressed eligibility test, both of which require a format. A context's desc (and so its format) never changes, so once per context is exact. One-line why-comment: the query ran per descriptor.
3. atlas_native_filter(): change its first parameter from the format to an int "usable" (the caller passes env-enabled AND c->filter_linear); it returns 0 when not usable, otherwise lazily creates the static linear sampler exactly as today and sets image->sampler. Remove its getenv and its format query. Keep the existing comment and add that the switch is read once per submission (the granularity the comment already promises, since descriptor metadata is rebuilt per submission).
4. vk_atlas_descriptor(): right after the line that computes epoch=mtl_last_fence()+1 (~L231; the function holds g_atlas_mu there, so function-static state is safe), add function-static caches: a uint64_t env_epoch and two ints (native filter on, residency big). When env_epoch != epoch, read getenv("DM_VK_ATLAS_NATIVE_FILTER") (on = set and atoi nonzero, as today) and getenv("DM_VK_ATLAS_RESIDENCY") (big = set and equal to "big", as today), then set env_epoch = epoch. Keep that whole guarded refresh, including both getenv calls, on ONE line in the file's dense style (the verify gate relies on every getenv in this function sharing a line with env_epoch). Replace the residency getenv/strcmp test at ~L249-250 with the cached flag (the rest of that condition unchanged), and call atlas_native_filter with (native-on && c->filter_linear, image). Live A/B from the diagnostic console still works, now at submission granularity; also note in the one-line comment that this keeps the hardware sampler and the metadata's data[15] (written once per epoch by the binding cache) consistent within a submission, which per-call reads did not guarantee.
5. Change nothing else in the file (Task 2 adds its own lines separately).
  </action>
  <verify>
    <automated>cd /Volumes/Data/Dev/nxhost && F=nxnative/dm/android/gfx_vk_atlas.c && S=/private/tmp/claude-501/-Volumes-Data-Dev-nxhost/3182d3eb-7ffd-46d1-b7c2-74094192d992/scratchpad/build-check && [ "$(awk '/^static va_context \*context\(/,/^}/' $F | grep -c vkGetPhysicalDeviceFormatProperties)" -ge 1 ] && [ "$(awk '/^static int atlas_native_filter\(/,/^}/' $F | grep -c 'getenv\|vkGetPhysicalDeviceFormatProperties')" = 0 ] && [ "$(awk '/^int vk_atlas_descriptor\(/,/^}/' $F | grep getenv | grep -v env_epoch | wc -l | tr -d ' ')" = 0 ] && [ "$(awk '/^int vk_atlas_descriptor\(/,/^}/' $F | grep -c 'DM_VK_ATLAS_NATIVE_FILTER')" -ge 1 ] && python3 nxnative/dm/android/build.py --game 0400C3F00006E000 --ndk "$HOME/Library/Android/sdk/ndk/27.2.12479018" --only-compile --out "$S" > "$S.t1.log" 2>&1 && grep -q ', 0 failed' "$S.t1.log" && ! grep -q 'warning:\|error:' "$S.t1.log" && echo TASK1-OK</automated>
  </verify>
  <done>
Gate baselines (planner-run) and targets: format query inside context() 0 -> 1; getenv/format query inside atlas_native_filter 2 -> 0; getenv lines in vk_atlas_descriptor without env_epoch 1 -> 0; DM_VK_ATLAS_NATIVE_FILTER inside vk_atlas_descriptor 0 -> 1. build.py --only-compile prints ", 0 failed" with no warning or error lines. Behaviour: identical output for unchanged env; both switches still toggle live, taking effect at the next submission.
  </done>
</task>

<task type="auto">
  <name>Task 2: Let atlas shaders use the per-stage descriptor-set memo, keyed on an atlas version</name>
  <files>nxnative/dm/android/gfx_vk_atlas.c, nxnative/dm/android/gfx_vk_tex.c, nxnative/dm/android/gfx_vk.h, nxnative/dm/android/gfx_vk_exec.c</files>
  <read_first>
    - nxnative/dm/android/gfx_vk_exec.c lines ~1063-1227 (memo comment, set_memo_t, set_memo_ok, set_memo_get, stage_set) and ~982-1020 (tex_desc_for, for the atlas call site)
    - nxnative/dm/android/gfx_vk_tex.c lines ~145-160 (g_image_ownership_gen)
    - nxnative/dm/android/gfx_vk.h lines ~140-160 and ~190-196
    - nxnative/dm/android/gfx_vk_atlas.c retire(), plan_build() end (~L195), and the file-scope globals block (~L39-51)
  </read_first>
  <action>
Finding A: set_memo_ok's line "ok &= b->kind != RK_ATLAS && !(b->flags & 16) && ..." (~L1079) keeps every atlas shader off set_memo_get, so each of their draws collects and hashes every binding. vk_atlas_descriptor's answer for an unchanged texture, view and sampler within one submission depends on four things outside today's memo keys: its table/image (plan_build, retire), GPU ownership (vk_tex_gpu_content, uncompressed path), the sparse mapping generation and the dirty clock (the per-call nvn_sparse_since / plan_build recheck, and the uncompressed cpu_readable recheck). The plan folds these into one version and keys only atlas shaders on it.

1. gfx_vk_tex.c: directly after "static _Atomic uint64_t g_image_ownership_gen=1;" add the accessor uint64_t vk_image_ownership_gen(void) returning atomic_load_explicit(&g_image_ownership_gen, memory_order_acquire), one line, with a short trailing comment naming its consumer (gfx_vk_atlas.c vk_atlas_version).
2. gfx_vk_atlas.c:
   a. In the globals block add "static uint64_t g_atlas_gen=1;" with a one-line comment: bumped whenever any context's table revision changes or its image is retired, so a memoized descriptor set (gfx_vk_exec.c) cannot outlive the view or metadata it names.
   b. retire(): add __atomic_add_fetch(&g_atlas_gen,1,__ATOMIC_RELEASE) (covers cache_size's image replacement and context_free from drop_pool/sweep).
   c. plan_build(): add the same bump on the line with c->revision++ (~L195).
   d. After vk_atlas_peak_bytes (end of file) or next to vk_atlas_stats, add uint64_t vk_atlas_version(void) returning __atomic_load_n(&g_atlas_gen,__ATOMIC_ACQUIRE)+nvn_sparse_gen()+nvn_dirty_now()+vk_image_ownership_gen(). Why-comment (one or two lines): what vk_atlas_descriptor rechecks per call besides the texture, view, sampler and submission (tables and images, GPU ownership, sparse remaps, first CPU writes to protected pages); every term only increases, so the sum is unchanged only if each term is.
3. gfx_vk.h: add the prototype for vk_image_ownership_gen beside vk_tex_gpu_content (~L142) and for vk_atlas_version in the vk_atlas_* block (~L152-157), each with a short trailing comment. Update the setmemo field comment (~L194) to document the new value: 3 = memoized and also keyed on vk_atlas_version (the shader has atlas bindings). Touch no other header line.
4. gfx_vk_exec.c:
   a. set_memo_t (~L1072): add a uint64_t field av (the atlas version the set was collected under).
   b. set_memo_ok (~L1076-1082): drop "b->kind != RK_ATLAS && !(b->flags & 16) &&" from the ok &= line; accumulate a local atlas flag (b->kind == RK_ATLAS or b->flags & 16) in the same loop; store s->setmemo = ok && ncb <= MEMO_CB ? (atlas ? 3 : 1) : 2; return s->setmemo != 2. All other exclusions (RK_SBUF_UBO, RK_UBO_PTR, RK_TEX_UBO, RK_IMG_UBO, RK_TBUF_UBO, RS_UBO, i < 256) stay exactly as they are; they also exclude an atlas shader whose paired texture is read from uniform memory.
   c. set_memo_get (~L1085): extend the first early-miss condition with "|| (s->setmemo == 3 && m->av != vk_atlas_version())". Non-atlas shaders (setmemo 1) never evaluate it: their keys are unchanged.
   d. stage_set: on the version-capture line (~L1101, the one that reads gtex/gsamp/gpool "before collecting"), also capture uint64_t gav = memo && s->setmemo == 3 ? vk_atlas_version() : 0, before the collect loop, so a change racing the collection leaves the memo outdated, never wrong-and-current (same rule as the existing captures). In the memo store block (~L1223) set m->av = gav.
   e. The verify [RED] line (~L1219-1221) already compares g_num_atlas with vam; add "atlas %#llx / %#llx" (g_num_atlas, vam) to its printed text so an atlas-mask difference is visible.
   f. Extend the memo comment block (~L1063-1070) by at most three lines: atlas shaders (setmemo 3) are memoized too and also keyed on vk_atlas_version; the memo epoch is the atlas epoch (vk_exec_reset is the only g_set_epoch++, the commit the only ++g_fence), so the first draw of a submission always collects and the atlas cells' fences, used_fence and used_frame are marked once per submission as before (later hits name the same table revision, whose cells already carry this submission's fence; sweep never frees a context whose used_fence is not yet done); mute/census are re-read in vk_exec_reset, so no hit spans a toggle; a verify difference in the hash alone on an atlas shader can also be atlas metadata copied again after its context's single binding entry was taken by another view or sampler (the memo's copy, written in this submission for the same revision, is as good). Cite the evidence briefly: Mario Kart World Toad's Factory, 886 of 975 main-pass draws atlas-active, about 12.7 ms a frame collecting.
   g. Declare nothing new locally if the header prototypes are visible (gfx_vk_exec.c includes gfx_vk.h); -Werror=implicit-function-declaration will catch a miss.
5. Do not change tex_desc_for, the atlas call site, DM_VK_X_NOSETMEMO / DM_VK_X_SETVERIFY handling, or anything for compute/mesh stages (memo stays st < 3).
6. After the compile passes, write the before/after diff for the SUMMARY: for each of the four files run diff -u against the scratchpad/pre/ copy and paste the combined output into SUMMARY.md under "Uncommitted code changes" (it is the only durable record of this task's code, because nothing is committed). Follow the user's openwolf bookkeeping (.wolf/anatomy.md, .wolf/memory.md) for the edited files.
  </action>
  <verify>
    <automated>cd /Volumes/Data/Dev/nxhost && A=nxnative/dm/android && S=/private/tmp/claude-501/-Volumes-Data-Dev-nxhost/3182d3eb-7ffd-46d1-b7c2-74094192d992/scratchpad/build-check && [ "$(grep -c '^uint64_t vk_image_ownership_gen(void)' $A/gfx_vk_tex.c)" -ge 1 ] && [ "$(grep -c '^uint64_t vk_atlas_version(void)' $A/gfx_vk_atlas.c)" -ge 1 ] && [ "$(awk '/^static void retire\(/,/^}/' $A/gfx_vk_atlas.c | grep -c g_atlas_gen)" -ge 1 ] && [ "$(awk '/^static void plan_build\(/,/^}/' $A/gfx_vk_atlas.c | grep -c g_atlas_gen)" -ge 1 ] && [ "$(grep -c 'vk_atlas_version\|vk_image_ownership_gen' $A/gfx_vk.h)" -ge 2 ] && [ "$(awk '/^static int set_memo_ok\(/,/^}/' $A/gfx_vk_exec.c | grep 'ok &=' | grep -c 'RK_ATLAS\|flags & 16')" = 0 ] && [ "$(grep -c 'vk_atlas_version()' $A/gfx_vk_exec.c)" -ge 2 ] && [ "$(grep -c 'setmemo == [3]' $A/gfx_vk_exec.c)" -ge 2 ] && python3 nxnative/dm/android/build.py --game 0400C3F00006E000 --ndk "$HOME/Library/Android/sdk/ndk/27.2.12479018" --only-compile --out "$S" > "$S.t2.log" 2>&1 && grep -q ', 0 failed' "$S.t2.log" && ! grep -q 'warning:\|error:' "$S.t2.log" && python3 -m unittest tests.test_architecture && STAGED=$(git diff --cached --name-only -- nxnative) && [ -z "$STAGED" ] && GS=$(git status --short -- $A/gfx_vk_atlas.c) && case "$GS" in '??'*) true;; *) false;; esac && echo TASK2-OK</automated>
  </verify>
  <done>
Gate baselines (planner-run) and targets: vk_image_ownership_gen accessor in gfx_vk_tex.c 0 -> 1; vk_atlas_version definition 0 -> 1; g_atlas_gen in retire() 0 -> 1 and in plan_build() 0 -> 1; header prototypes 0 -> 2; RK_ATLAS / flags & 16 on set_memo_ok's ok &= line 1 -> 0; vk_atlas_version() uses in gfx_vk_exec.c 0 -> at least 2; the setmemo-3 test in gfx_vk_exec.c (grep 'setmemo == [3]') 0 -> at least 2. Compile ", 0 failed", no warnings; arch test OK; nothing under nxnative/ staged; gfx_vk_atlas.c still untracked. SUMMARY.md contains the full diff and the device recipe below.
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| guest game memory -> atlas snapshot | The game thread remaps sparse pages and writes texture memory concurrently with replay; descriptors must not outlive the snapshot they name |
| replay CPU -> GPU | A reused descriptor set must name only images, views and metadata still alive until the submission's fence completes |

## STRIDE Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation Plan |
|-----------|----------|-----------|----------|-------------|-----------------|
| T-fxs-01 | Tampering (stale data) | gfx_vk_exec.c set_memo_get for setmemo 3 | medium | mitigate | Key atlas shaders on vk_atlas_version (g_atlas_gen bumped in plan_build and retire, plus nvn_sparse_gen, nvn_dirty_now, vk_image_ownership_gen), captured before collecting; DM_VK_X_SETVERIFY=1 re-collects 1 hit in 64 and logs [RED] with atlas masks on any difference |
| T-fxs-02 | Denial of service (GPU fault / use after free) | atlas cell and image lifetime on memo hits | medium | mitigate | Memo epoch equals atlas epoch (single g_set_epoch++ and single ++g_fence site), so the first draw per submission always collects and marks used_fence and cell fences; retire holds images by used_fence; sweep skips contexts whose used_fence is not done |
| T-fxs-03 | Repudiation (diagnostics lie) | live switches DM_VK_ATLAS_NATIVE_FILTER / RESIDENCY / MUTE | low | accept | Read once per submission (mute/census already per submission in x_read); effect lands at the next submission, which is what the existing comment promises |
| T-fxs-04 | Information disclosure | none | low | accept | No new data leaves the device; no keys or game data involved |
</threat_model>

<verification>
Local (this session, no device connected):
1. Task 1 and Task 2 automated gates print TASK1-OK and TASK2-OK.
2. Final: python3 -m unittest tests.test_architecture is OK; build.py --only-compile into the scratch build-check folder prints ", 0 failed" with no warnings.
3. git status shows the four files still modified/untracked and nothing under nxnative/ staged; the diff against scratchpad/pre/ touches only the hunks named in the tasks.

Device follow-up (record verbatim in SUMMARY.md as the user's next step; not runnable now):
1. Build and install a test package per the nx2android-dev skill (ask before installing; use a .test package beside the user's own app).
2. Correctness: run with DM_VK_X_SETVERIFY=1 at the parked Toad's Factory camera for several 600-frame reports. Pass = "memo differences 0" in the "replay per frame (last 600)" line and no "[RED] descriptor set memo" lines. If [RED] lines appear only for atlas shaders with the hash alone differing (um, im, atlas masks and dynamic offsets the same), it may be the benign metadata re-copy named in the comment: confirm with a DM_VK_X_NOSETMEMO=1 A/B screenshot of the same frame before trusting it.
3. Speed: A/B/A at the same camera, default vs DM_VK_X_NOSETMEMO=1 (live), comparing "collecting ms", "descriptor sets ms" and "kept per stage a frame" in the 600-frame replay line, plus settled 400-presentation FPS windows. Record results in nxnative/dm/games/0400C3F00006E000/README.md only after measuring (that file has the user's uncommitted edits: add, do not rewrite).
4. Risk to watch: the atlas memo invalidates on every first CPU write to a protected page anywhere (nvn_dirty_now) and every sparse remap; if "kept per stage" barely rises, that churn is the next thing to measure.
</verification>

<success_criteria>
- vk_atlas_descriptor's per-call path has no getenv and no vkGetPhysicalDeviceFormatProperties.
- Atlas shaders reach set_memo_get (setmemo 3) and miss it whenever vk_atlas_version changes; non-atlas shaders' memo behaviour is byte-for-byte the same keys as before.
- All Android sources compile with 0 failed and 0 warnings; tests.test_architecture passes.
- No code is staged or committed; the user's uncommitted work outside the named hunks is untouched; SUMMARY.md records the full diff, the fact that the code is uncommitted, and the device recipe.
- Not done here and stated in SUMMARY: no on-device measurement or correctness run (no device connected), and no new unit test (stage_set needs the full Vulkan backend; DM_VK_X_SETVERIFY is the self-check).
</success_criteria>

<output>
Create `.planning/quick/261111-fxs-cut-android-vulkan-descriptor-collection/261111-fxs-SUMMARY.md` when done
</output>
