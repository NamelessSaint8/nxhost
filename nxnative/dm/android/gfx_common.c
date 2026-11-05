// Android port: what both graphics backends (gfx_null.c, gfx_vk_*.c) report for the host's statistics and diagnostic hooks of the Metal backend
// (nvn_mtl.m) that have no counterpart yet: zeros.
#include "dm.h"
#include "nvn_obj.h"
#include "nvn_mtl.h"
#include <string.h>

// A statistic this backend does not keep. It still answers 0, but the first call names it: a plain 0 in the log ("packaged textures: first uploads 0") reads as a
// measured failure otherwise, and a zero counter was once pursued as a lead for that reason (2026-11-03). One static per function, so a run logs each name at
// most once (a benign race between two threads can repeat it). A counter added below without STUB0 fails tests/arch_rules.py rule 14 — add its name to
// tests/fixtures/gfx_stub_counters.txt in the same change.
#define STUB0(what) do { static int once_; if (!once_) { once_ = 1; LOG("[dm] " what ": not implemented on the Android backend; its 0 is not a measurement"); } } while (0)

// ---------------- statistics and diagnostics: nothing to report ----------------
void mtl_vbuf_stats(uint64_t *a, uint64_t *b, uint64_t *c, uint64_t *d, uint64_t *e, uint64_t *f) { STUB0("mtl_vbuf_stats"); *a = *b = *c = *d = *e = *f = 0; }
void mtl_res_counts(uint32_t tick, const char *why) { (void)tick; (void)why; }
void mtl_res_snapshot(mtl_res_count *out) { STUB0("mtl_res_snapshot"); memset(out, 0, sizeof *out); }
void mtl_alloc_stats(uint64_t *w, uint64_t *g, int *n) { STUB0("mtl_alloc_stats"); *w = *g = 0; *n = 0; }
void mtl_args_stats(uint64_t *e, uint64_t *r) { STUB0("mtl_args_stats"); *e = *r = 0; }
void mtl_barrier_stats(uint64_t *s, uint64_t *f) { STUB0("mtl_barrier_stats"); *s = *f = 0; }
uint64_t mtl_blit_splits(void) { STUB0("mtl_blit_splits"); return 0; }
void mtl_bw(uint64_t *l, uint64_t *s, uint64_t *f) { STUB0("mtl_bw"); *l = *s = *f = 0; }
uint64_t mtl_copy_cut_count(void) { STUB0("mtl_copy_cut_count"); return 0; }
uint64_t mtl_cut_count(void) { STUB0("mtl_cut_count"); return 0; }
void mtl_create_ns(uint64_t *l, uint64_t *p) { STUB0("mtl_create_ns"); *l = *p = 0; }
void mtl_create_stats(uint64_t *l, uint64_t *p) { STUB0("mtl_create_stats"); *l = *p = 0; }
uint64_t mtl_drawable_ns_take(void) { STUB0("mtl_drawable_ns_take"); return 0; }
uint64_t mtl_ds_omit(void) { STUB0("mtl_ds_omit"); return 0; }
__attribute__((weak)) double mtl_gpu_ms(uint64_t f) { STUB0("mtl_gpu_ms"); (void)f; return 0; }   // gfx_vk_core.c has the real one
int mtl_gpu_span(uint64_t f, uint64_t *t0, uint64_t *t1) { STUB0("mtl_gpu_span"); (void)f; *t0 = *t1 = 0; return 0; }
void mtl_lc_stats(uint64_t *t, uint64_t *l) { STUB0("mtl_lc_stats"); *t = *l = 0; }
void mtl_mem_stat(unsigned long long frame, unsigned long long rss_mb) { (void)frame; (void)rss_mb; }
uint64_t mtl_pkg_miss(void) { STUB0("mtl_pkg_miss"); return 0; }
void mtl_pkg_stats(uint64_t *u, uint64_t *r) { STUB0("mtl_pkg_stats"); *u = *r = 0; }
void mtl_res_stats(char *out, size_t n) { STUB0("mtl_res_stats"); if (n) out[0] = 0; }
void mtl_stats(uint64_t *p, uint64_t *d) { STUB0("mtl_stats"); *p = *d = 0; }
void mtl_ub_present(double iv) { (void)iv; }
void mtl_ubd_stats(uint64_t *d, uint64_t *c) { STUB0("mtl_ubd_stats"); *d = *c = 0; }
void mtl_ubp_stats(uint64_t *m, uint64_t *r, uint64_t *f) { STUB0("mtl_ubp_stats"); *m = *r = *f = 0; }
void mtl_ubp_why(uint64_t w[5]) { STUB0("mtl_ubp_why"); memset(w, 0, 5 * sizeof *w); }
uint64_t mtl_udc_saved_bytes(void) { STUB0("mtl_udc_saved_bytes"); return 0; }
uint64_t mtl_upload_bytes(void) { STUB0("mtl_upload_bytes"); return 0; }
uint64_t mtl_upload_gpu_ns_take(void) { STUB0("mtl_upload_gpu_ns_take"); return 0; }
uint64_t mtl_upload_ns_take(void) { STUB0("mtl_upload_ns_take"); return 0; }
void mtl_use_stats(uint64_t *c, uint64_t *s) { STUB0("mtl_use_stats"); *c = *s = 0; }
void dm_gfx_passdump_next(long n) { (void)n; }
void dm_gfx_shot_at(long k, const char *path) { (void)k; (void)path; }
void dm_gfx_texdump_next(const char *path) { (void)path; }
void dm_gfx_texlist(int target) { (void)target; }
void dm_gfx_texraw(uint64_t serial, const char *path) { (void)serial; (void)path; }

int mtl_pso_prebuild_tool(void) {   // main() asks first, every boot: 0 = no tool run, the game starts (Mac's pipeline-archive prebuild, nvn_mtl.m, DM_PSO_PREBUILD=tool)
    if (getenv("DM_PSO_PREBUILD")) LOG("[RED] DM_PSO_PREBUILD is the Mac host's pipeline archive prebuild; the Android host has no such tool, starting the game");
    return 0;
}


// ---- the Mac host's hooks the shared NVN layer calls (nvn_mtl.m): diagnostics, present pacing and the capture plug points. The Vulkan backend has its own ----
// ---- for each; these answers keep the shared paths on their no- or default-branch (mtl_link_rate 60: no ProMotion link here)                        ----
#include "nvn_obj.h"
void mtl_prog_prefetch(const prog_t *cp) { (void)cp; }   // a program's libraries prefetch at set time (Metal); the Vulkan side loads at first use
void mtl_queue_activate(uint64_t serial) { (void)serial; }   // the display link's serial bookkeeping (caller holds the submission lock)
void mtl_queue_forget(uint64_t serial) { (void)serial; }
void mtl_set_queue_origin_lower_left(int on) { (void)on; }   // Metal's NDC origin flip; the Vulkan backend keeps its own convention
void nvn_cap_submit(int n, const uint64_t *h) { (void)n; (void)h; }   // DM_NVN_CAPTURE (nvn_capture.inc): a Mac diagnostic, off on Android
void nvn_cap_present(const tex_t *t, const int crop[4]) { (void)t; (void)crop; }
int mtl_snap_on(void) { return 0; }   // present snapshots: the acquire's ring-slot wait paces them on Mac; off here
uint64_t mtl_snap_acquire_wait(void) { STUB0("mtl_snap_acquire_wait"); return 0; }
void mtl_pso_line(char *o, size_t n) { STUB0("mtl_pso_line"); if (n) o[0] = 0; }   // the pipeline trace's one-line summary
unsigned mtl_cpu_tex_count(void) { STUB0("mtl_cpu_tex_count"); return 0; }
void mtl_ab_gpu(uint64_t f, double gpu_ms, double frame_ms) { (void)f; (void)gpu_ms; (void)frame_ms; }   // DM_AB phases trace
int mtl_link_rate(void) { return 60; }   // no display link: the standard rate
int mtl_link_stalled(void) { return 0; }
int mtl_link_tick(uint64_t n, double *target, double *lead, int *ticks, double *gap) { (void)n; (void)target; (void)lead; (void)ticks; (void)gap; return 0; }
int mtl_link_wait_ticks(int ticks, uint64_t timeout_ns) { (void)ticks; (void)timeout_ns; return 0; }
void mtl_cshoist_stats(uint64_t *moved, uint64_t *depth, uint64_t *stops) { STUB0("mtl_cshoist_stats"); *moved = *depth = 0; if (stops) for (int i = 0; i < 8; i++) stops[i] = 0; }
void mtl_geohoist_stats(uint64_t *moved, uint64_t *runs, uint64_t *stops) { STUB0("mtl_geohoist_stats"); *moved = *runs = 0; if (stops) for (int i = 0; i < 6; i++) stops[i] = 0; }
void mtl_geomesh_stats(uint64_t *n, uint64_t *wait) { STUB0("mtl_geomesh_stats"); *n = *wait = 0; }
void mtl_hybrid_stats(uint64_t *draws, uint64_t *made, uint64_t *none) { STUB0("mtl_hybrid_stats"); *draws = *made = *none = 0; }
void mtl_sm_stats(uint64_t *np, uint64_t *nc, uint64_t *nw) { STUB0("mtl_sm_stats"); *np = *nc = *nw = 0; }
uint64_t mtl_pkg_edge_skips(void) { STUB0("mtl_pkg_edge_skips"); return 0; }
