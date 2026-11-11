// Fragment exports are raw 32-bit registers. Integer attachments consume their
// bits, not a floating-point conversion. Keep arithmetic and reads of outputs
// in their original type; retype only the interface and its pointer accesses.
// This file has no Vulkan dependency so the exact runtime transform is tested
// with the host compiler and spirv-val as well as GPU readback.
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
typedef struct {
    const uint32_t *w;
    uint32_t base, bound, fn, *at, *types, *decl, nd, storage;
} spvo_ctx;
static uint32_t spvo_decl(spvo_ctx *c, uint32_t op, uint32_t a, uint32_t b) {
    for (uint32_t i = 5; i < c->fn; i += c->w[i] >> 16)
        if ((c->w[i] & 0xffff) == op && c->w[i] >> 16 == 4 && c->w[i+2] == a && c->w[i+3] == b) return c->w[i+1];
    for (uint32_t i = 0; i < c->nd; i += c->decl[i] >> 16)
        if ((c->decl[i] & 0xffff) == op && c->decl[i+2] == a && c->decl[i+3] == b) return c->decl[i+1];
    uint32_t id = c->bound++;
    c->decl[c->nd++] = 4u << 16 | op; c->decl[c->nd++] = id;
    c->decl[c->nd++] = a; c->decl[c->nd++] = b;
    return id;
}
static uint32_t spvo_type(spvo_ctx *c, uint32_t old, unsigned kind) {
    if (!old || old >= c->base || !kind || kind > 2) return 0;
    uint32_t *memo = &c->types[old * 2 + kind - 1];
    if (*memo) return *memo;
    uint32_t i = c->at[old]; if (!i) return 0;
    uint32_t op = c->w[i] & 0xffff, n = c->w[i] >> 16, t;
    if ((op == 22 && n == 3 && c->w[i+2] == 32) || (op == 21 && n == 4 && c->w[i+2] == 32))
        t = spvo_decl(c, 21, 32, kind - 1);
    else if (op == 23 && n == 4 && (t = spvo_type(c, c->w[i+2], kind)))
        t = spvo_decl(c, 23, t, c->w[i+3]);
    else if (op == 32 && n == 4 && c->w[i+2] == c->storage && (t = spvo_type(c, c->w[i+3], kind)))
        t = spvo_decl(c, 32, c->storage, t);
    else return 0;   // matrices, blocks and arrays need a location-aware transform
    return *memo = t;
}
static uint32_t *spv_int_interface(const uint32_t *w, uint32_t nw, uint32_t um, uint32_t im, uint32_t storage, uint32_t *onw) {
    *onw = 0;
    if (nw < 5 || w[0] != 0x07230203 || !w[3] || w[3] > (1u << 24) || nw > (1u << 27) || (um & im)) return NULL;
    spvo_ctx c = {.w = w, .base = w[3], .bound = w[3], .fn = nw, .storage = storage};
    c.at = calloc(c.base, 4); c.types = calloc((size_t)c.base * 2, 4);
    c.decl = malloc(((size_t)nw * 3 + 64) * 4);
    uint32_t *ty = calloc(c.base, 4), *loc = malloc((size_t)c.base * 4);
    uint8_t *kind = calloc(c.base, 1);
    uint32_t *o = malloc(((size_t)nw * 4 + 1024) * 4), *body = malloc(((size_t)nw * 4 + 1024) * 4);
    int ok = c.at && c.types && c.decl && ty && loc && kind && o && body;
    if (!ok) goto done;
    memset(loc, 0xff, (size_t)c.base * 4);
    // Index definitions and locations, checking instruction boundaries first.
    for (uint32_t i = 5; i < nw;) {
        uint32_t n = w[i] >> 16, op = w[i] & 0xffff;
        if (!n || n > nw - i) { ok = 0; goto done; }
        if (op == 54 && c.fn == nw) c.fn = i;
        if (op >= 19 && op <= 39 && n >= 2 && w[i+1] < c.base) c.at[w[i+1]] = i;
        if (op == 71 && n == 4 && w[i+2] == 30 && w[i+1] < c.base) loc[w[i+1]] = w[i+3];
        // Only instructions that define the pointer/value IDs used below.
        if ((op == 59 || op == 61 || op == 65 || op == 66 || op == 67 || op == 70 || op == 83 || op == 169 || op == 245) && n >= 3 && w[i+2] < c.base) ty[w[i+2]] = w[i+1];
        i += n;
    }
    for (uint32_t i = 5; i < c.fn; i += w[i] >> 16) {
        uint32_t n = w[i] >> 16, id = n >= 3 ? w[i+2] : 0;
        if ((w[i] & 0xffff) == 59 && n >= 4 && w[i+3] == storage && id < c.base && loc[id] == UINT32_MAX && (um | im)) {
            uint32_t ptr = ty[id] < c.base ? c.at[ty[id]] : 0;
            uint32_t t = ptr && w[ptr+3] < c.base ? c.at[w[ptr+3]] : 0;
            if (t && (w[t] & 0xffff) == 30) { ok = 0; goto done; }
        }
        if ((w[i] & 0xffff) == 59 && n >= 4 && w[i+3] == storage && id < c.base && loc[id] < 32) {
            kind[id] = um >> loc[id] & 1 ? 1 : im >> loc[id] & 1 ? 2 : 0;
            if (kind[id] && (n != 4 || !spvo_type(&c, ty[id], kind[id]))) { ok = 0; goto done; }
        }
    }
    // Propagate pointer kinds to a fixed point, including loop-carried aliases.
    int changed;
    do {
        changed = 0;
        for (uint32_t i = c.fn; i < nw; i += w[i] >> 16) {
            uint32_t n = w[i] >> 16, op = w[i] & 0xffff, id = n >= 3 ? w[i+2] : 0, k = 0;
            if ((op == 65 || op == 66 || op == 67 || op == 70 || op == 83) && n >= 4 && w[i+3] < c.base) k = kind[w[i+3]];
            if (op == 169 && n == 6) for (uint32_t j = 4; j < 6; j++) if (w[i+j] < c.base && kind[w[i+j]]) k = kind[w[i+j]];
            if (op == 245) for (uint32_t j = 3; j < n; j += 2) if (w[i+j] < c.base && kind[w[i+j]]) k = kind[w[i+j]];
            if (k && id < c.base && !kind[id]) { kind[id] = (uint8_t)k; changed = 1; }
        }
    } while (changed);
    uint32_t nb = 0;
    for (uint32_t i = c.fn; i < nw;) {
        uint32_t n = w[i] >> 16, op = w[i] & 0xffff, src = n >= 4 ? w[i+3] : 0;
        uint32_t k = src < c.base ? kind[src] : 0, start = nb;
        if (op == 57) {   // passing an output pointer needs a function-type rewrite
            for (uint32_t j = 4; j < n; j++) if (w[i+j] < c.base && kind[w[i+j]]) { ok = 0; goto done; }
        }
        if ((op == 63 || op == 64) && n >= 3 && ((w[i+1] < c.base && kind[w[i+1]]) || (w[i+2] < c.base && kind[w[i+2]]))) { ok = 0; goto done; }
        if (op == 62 && n >= 3 && w[i+1] < c.base && kind[w[i+1]]) {
            uint32_t ptr = ty[w[i+1]], at = ptr < c.base ? c.at[ptr] : 0;
            uint32_t t = at ? spvo_type(&c, w[at+3], kind[w[i+1]]) : 0, id = c.bound++;
            if (!t) { ok = 0; goto done; }
            body[nb++] = 4u << 16 | 124; body[nb++] = t; body[nb++] = id; body[nb++] = w[i+2];
            memcpy(body + nb, w + i, n * 4); body[nb+2] = id; nb += n;
        } else {
            memcpy(body + nb, w + i, n * 4); nb += n;
            if (op == 61 && k) {
                uint32_t t = spvo_type(&c, w[i+1], k), id = c.bound++;
                if (!t) { ok = 0; goto done; }
                body[start+1] = t; body[start+2] = id;
                body[nb++] = 4u << 16 | 124; body[nb++] = w[i+1]; body[nb++] = w[i+2]; body[nb++] = id;
            } else if ((op == 65 || op == 66 || op == 67 || op == 70 || op == 83 || op == 169 || op == 245) && n >= 3 && w[i+2] < c.base && kind[w[i+2]]) {
                k = kind[w[i+2]];
                if (op == 169 || op == 245) for (uint32_t j = op == 169 ? 4 : 3; j < n; j += op == 169 ? 1 : 2)
                    if (w[i+j] >= c.base || kind[w[i+j]] != k) { ok = 0; goto done; }
                uint32_t t = spvo_type(&c, w[i+1], k); if (!t) { ok = 0; goto done; }
                body[start+1] = t;
            }
        }
        i += n;
    }
    // New types must precede global variables. Move all globals together; this
    // also handles declarations originally interleaved with unrelated types.
    uint32_t no = 5; memcpy(o, w, 20);
    for (uint32_t i = 5; i < c.fn; i += w[i] >> 16) if ((w[i] & 0xffff) != 59) { uint32_t n = w[i] >> 16; memcpy(o+no, w+i, n*4); no += n; }
    memcpy(o+no, c.decl, c.nd*4); no += c.nd;
    for (uint32_t i = 5; i < c.fn; i += w[i] >> 16) if ((w[i] & 0xffff) == 59) {
        uint32_t n = w[i] >> 16, id = w[i+2]; memcpy(o+no, w+i, n*4);
        if (id < c.base && kind[id]) o[no+1] = c.types[ty[id]*2 + kind[id]-1];
        no += n;
    }
    memcpy(o+no, body, nb*4); no += nb; o[3] = c.bound; *onw = no;
done:
    free(c.at); free(c.types); free(c.decl); free(ty); free(loc); free(kind); free(body);
    if (!ok) { free(o); o = NULL; }
    return o;
}

static uint32_t *spv_int_outputs(const uint32_t *w,uint32_t nw,uint32_t um,uint32_t im,uint32_t *onw){return spv_int_interface(w,nw,um,im,3,onw);}
static uint32_t *spv_int_inputs(const uint32_t *w,uint32_t nw,uint32_t um,uint32_t im,uint32_t *onw){return spv_int_interface(w,nw,um,im,1,onw);}
