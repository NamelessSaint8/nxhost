// Android port: AV1 for the nn::codec decoders (hle_codec_video.c) through dav1d (dm/third_party/dav1d), the same software decoder the Mac uses when
// VideoToolbox has no AV1 hardware decoder. The Mac's file also carries a VideoToolbox path; Android has no counterpart here, so only dav1d is built in.
// dav1d's picture is planar and the interface wants NV12: the luma is copied when the stream is more than 8 bits, and the chroma is interleaved (4:2:0
// and 4:2:2 subsampled, 4:0:0 grey). The picture stays valid until the next mav1_decode call, as the interface says.
#include "dm.h"
#include "hle_movie_av1.h"
#include "dav1d/dav1d.h"
#include <stdarg.h>
#include <stdlib.h>
#include <string.h>

struct mav1 {
    Dav1dContext *dav1d;
    Dav1dPicture pic; int has_pic;
    uint8_t *y8, *uv; size_t ny8, nuv;   // the NV12 conversion of a picture: 16-bit luma shifted down, chroma interleaved
    int red;
};

mav1 *mav1_new(void) { mav1 *a = calloc(1, sizeof *a); if (!a) die("movie: AV1 decoder allocation failed"); return a; }
const char *mav1_backend(const mav1 *a) { (void)a; return "dav1d"; }

static void unlock_picture(mav1 *a) { if (a->has_pic) { dav1d_picture_unref(&a->pic); a->has_pic = 0; } }
void mav1_reset(mav1 *a) { unlock_picture(a); if (a->dav1d) dav1d_flush(a->dav1d); }
void mav1_free(mav1 *a) { if (a) { mav1_reset(a); if (a->dav1d) dav1d_close(&a->dav1d); free(a->y8); free(a->uv); free(a); } }

// ---- The sequence header (AV1 5.5), read as far as the colour config; its four bytes are the av1C record's ----
typedef struct { const uint8_t *p; size_t n, bit; int bad; } av1_bits;
static uint32_t rb(av1_bits *b, unsigned n) {
    uint32_t v = 0;
    if (b->bit + n > b->n * 8) { b->bad = 1; return 0; }
    while (n--) { v = v << 1 | ((b->p[b->bit / 8] >> (7 - b->bit % 8)) & 1); b->bit++; }
    return v;
}
static void uvlc(av1_bits *b) { unsigned z = 0; while (!b->bad && !rb(b, 1)) if (++z >= 32) return; if (z < 32) rb(b, z); }
static size_t leb128(const uint8_t *p, size_t n, uint64_t *v) {
    *v = 0;
    for (size_t i = 0; i < n && i < 8; i++) { *v |= (uint64_t)(p[i] & 0x7f) << (i * 7); if (!(p[i] & 0x80)) return i + 1; }
    return 0;
}
int mav1_av1c(const uint8_t *obu, size_t n, uint8_t c[4], int *w, int *h) {
    if (n < 2 || (obu[0] >> 3 & 15) != 1 || !(obu[0] & 2)) return 0;   // a sequence header with a size field
    size_t at = obu[0] & 4 ? 2 : 1; uint64_t size;
    size_t l = at < n ? leb128(obu + at, n - at, &size) : 0;
    if (!l || size > n - at - l) return 0;
    av1_bits b = {obu + at + l, (size_t)size, 0, 0};
    unsigned profile = rb(&b, 3); rb(&b, 1); unsigned reduced = rb(&b, 1), level = 0;
    unsigned decoder_model = 0, delay_len = 0;
    if (reduced) level = rb(&b, 5);
    else {
        if (rb(&b, 1)) {   // timing_info
            rb(&b, 32); rb(&b, 32); if (rb(&b, 1)) uvlc(&b);
            if ((decoder_model = rb(&b, 1))) { delay_len = rb(&b, 5) + 1; rb(&b, 32); rb(&b, 5); rb(&b, 5); }
        }
        unsigned display_delay = rb(&b, 1), points = rb(&b, 5) + 1;
        for (unsigned i = 0; i < points && !b.bad; i++) {
            rb(&b, 12); unsigned lv = rb(&b, 5), t = lv > 7 ? rb(&b, 1) : 0;
            if (!i) level = lv;
            (void)t;
            if (decoder_model && rb(&b, 1)) { rb(&b, delay_len); rb(&b, delay_len); rb(&b, 1); }
            if (display_delay && rb(&b, 1)) rb(&b, 4);
        }
    }
    unsigned wb = rb(&b, 4) + 1, hb = rb(&b, 4) + 1;
    *w = (int)rb(&b, wb) + 1; *h = (int)rb(&b, hb) + 1;
    if (!reduced && rb(&b, 1)) { rb(&b, 4); rb(&b, 3); }   // frame ids
    rb(&b, 3);   // 128x128 superblocks, filter intra, intra edge filter
    if (!reduced) {
        rb(&b, 4);   // inter-intra, masked compound, warped motion, dual filter
        unsigned order_hint = rb(&b, 1);
        if (order_hint) rb(&b, 2);   // jnt_comp, ref_frame_mvs
        unsigned tools = rb(&b, 1) ? 2 : rb(&b, 1);
        if (tools && !rb(&b, 1)) rb(&b, 1);   // force_integer_mv
        if (order_hint) rb(&b, 3);
    }
    rb(&b, 3);   // superres, cdef, restoration
    unsigned hbd = rb(&b, 1), twelve = profile == 2 && hbd ? rb(&b, 1) : 0, mono = profile == 1 ? 0 : rb(&b, 1), cp = 2, tc = 2, mc = 2, ssx = 1, ssy = 1, pos = 0;
    if (rb(&b, 1)) { cp = rb(&b, 8); tc = rb(&b, 8); mc = rb(&b, 8); }
    if (!mono) {
        if (cp == 1 && tc == 13 && mc == 0) ssx = ssy = 0;   // sRGB
        else {
            rb(&b, 1);   // colour range
            if (profile == 1) ssx = ssy = 0;
            else if (profile == 2) { if (twelve) { ssx = rb(&b, 1); ssy = ssx ? rb(&b, 1) : 0; } else { ssx = 1; ssy = 0; } }
            if (ssx && ssy) pos = rb(&b, 2);
        }
    }
    if (b.bad) return 0;
    c[0] = 0x81;   // marker, version 1
    c[1] = (uint8_t)(profile << 5 | (level & 31));
    c[2] = (uint8_t)(hbd << 6 | twelve << 5 | mono << 4 | ssx << 3 | ssy << 2 | pos);
    c[3] = 0;
    return 1;
}

// ---- dav1d ----
static void d_log(void *cookie, const char *fmt, va_list ap) {
    (void)cookie; char b[256]; vsnprintf(b, sizeof b, fmt, ap);
    size_t l = strlen(b); if (l && b[l - 1] == '\n') b[l - 1] = 0;
    LOG("[movie] dav1d: %s", b);
}
static int grow(uint8_t **p, size_t *have, size_t want) {
    if (*have >= want) return 1;
    uint8_t *q = realloc(*p, want); if (!q) return 0;
    *p = q; *have = want; return 1;
}
// dav1d's planar picture as the NV12 the interface gives: 4:4:4 is subsampled horizontally too, 4:0:0 becomes grey chroma
static int dav1d_nv12(mav1 *a, const Dav1dPicture *p, mav1_picture *out) {
    int w = p->p.w, h = p->p.h, sh = p->p.bpc - 8, l = p->p.layout, cw = (w + 1) / 2, ch = (h + 1) / 2;
    int sx = l != DAV1D_PIXEL_LAYOUT_I444, sy = l == DAV1D_PIXEL_LAYOUT_I420;
    if (!grow(&a->uv, &a->nuv, (size_t)cw * 2 * ch) || (sh && !grow(&a->y8, &a->ny8, (size_t)w * h))) return 0;
    const uint8_t *y = p->data[0]; size_t ys = (size_t)p->stride[0];
    if (sh) {
        for (int r = 0; r < h; r++) { const uint16_t *s = (const uint16_t *)((const uint8_t *)p->data[0] + (ptrdiff_t)r * p->stride[0]); uint8_t *o = a->y8 + (size_t)r * w; for (int x = 0; x < w; x++) o[x] = (uint8_t)(s[x] >> sh); }
        y = a->y8; ys = (size_t)w;
    }
    for (int r = 0; r < ch; r++) {
        uint8_t *o = a->uv + (size_t)r * cw * 2;
        if (l == DAV1D_PIXEL_LAYOUT_I400) { memset(o, 128, (size_t)cw * 2); continue; }
        const uint8_t *u = (const uint8_t *)p->data[1] + (ptrdiff_t)(sy ? r : 2 * r) * p->stride[1], *v = (const uint8_t *)p->data[2] + (ptrdiff_t)(sy ? r : 2 * r) * p->stride[1];
        for (int x = 0; x < cw; x++) {
            int c = sx ? x : 2 * x;
            o[2 * x] = sh ? (uint8_t)(((const uint16_t *)u)[c] >> sh) : u[c]; o[2 * x + 1] = sh ? (uint8_t)(((const uint16_t *)v)[c] >> sh) : v[c];
        }
    }
    unsigned mc = p->seq_hdr->mtrx;
    if (mc == DAV1D_MC_UNKNOWN) mc = h < 720 ? DAV1D_MC_BT601 : DAV1D_MC_BT709;
    *out = (mav1_picture){y, a->uv, ys, (size_t)cw * 2, w, h, mc == DAV1D_MC_BT709 ? 2 : mc == DAV1D_MC_BT2020_NCL || mc == DAV1D_MC_BT2020_CL ? 5 : 1, p->seq_hdr->color_range};
    return 1;
}
static int decode_dav1d(mav1 *a, const uint8_t *data, size_t n, mav1_picture *out) {
    if (!a->dav1d) {
        Dav1dSettings st; dav1d_default_settings(&st);
        st.n_threads = 2; st.max_frame_delay = 1;   // one picture per temporal unit: the submitting thread waits for it
        st.logger.cookie = a; st.logger.callback = d_log;
        if (dav1d_open(&a->dav1d, &st)) { a->dav1d = NULL; if (!a->red++) LOG("[RED] movie: dav1d could not be opened"); return -1; }
        static int once; if (!once++) LOG("[movie] AV1: dav1d %s decoding", dav1d_version());
    }
    Dav1dData d = {0}; uint8_t *buf = dav1d_data_create(&d, n);
    if (!buf) return -1;
    memcpy(buf, data, n);
    Dav1dPicture p = {0}; int got = 0;
    for (int tries = 0; d.sz && tries < 64; tries++) {
        int r = dav1d_send_data(a->dav1d, &d);
        if (r && r != DAV1D_ERR(EAGAIN)) { dav1d_data_unref(&d); if (!a->red++) LOG("[RED] movie: dav1d refused a temporal unit (%d, first case)", r); return -1; }
        while (!dav1d_get_picture(a->dav1d, &p)) { if (a->has_pic) dav1d_picture_unref(&a->pic); a->pic = p; a->has_pic = 1; got = 1; }
    }
    if (d.sz) { dav1d_data_unref(&d); if (!a->red++) LOG("[RED] movie: dav1d took no more data, a temporal unit dropped (first case)"); return -1; }
    if (!got) return 0;
    if (!dav1d_nv12(a, &a->pic, out)) { if (!a->red++) LOG("[RED] movie: no memory for a %dx%d AV1 picture", a->pic.p.w, a->pic.p.h); return -1; }
    return 1;
}

int mav1_decode(mav1 *a, const uint8_t *data, size_t n, mav1_picture *out) {
    unlock_picture(a);
    return decode_dav1d(a, data, n, out);
}
