// BC block decoders: BC1 (DXT1), BC2 (DXT3), BC3 (DXT5), BC4 and BC5, in the NVN formats 0x41–0x4C.
// The block layouts are the D3D10 / OpenGL S3TC and RGTC ones: the endpoints first, then a per-texel index field packed
// little-endian, texel 0 at the top-left of the block. Interpolated values are rounded to nearest, as D3D10 states them
// ((2a + b + 1) / 3 rather than a truncating divide): a decoder that truncates differs from a GPU's BC sampler by one in the
// low bit of half the texels, which the image comparison against a BC device shows.
#include "nvn_bc.h"

// NVN texture formats (the numbering of dm/gfx/nvn/nvn_tex.c and the Android backend's format table)
enum {
    NVN_R8 = 0x01, NVN_R8_SNORM = 0x02, NVN_RG8 = 0x0D, NVN_RG8_SNORM = 0x0E, NVN_RGBA8 = 0x25, NVN_RGBA8_SRGB = 0x37,
    NVN_BC1_RGB = 0x41, NVN_BC1_RGBA, NVN_BC2, NVN_BC3, NVN_BC1_RGB_SRGB, NVN_BC1_RGBA_SRGB, NVN_BC2_SRGB, NVN_BC3_SRGB,
    NVN_BC4 = 0x49, NVN_BC4_SNORM, NVN_BC5, NVN_BC5_SNORM
};

int nvn_bc_unpacked_format(int f) {
    switch (f) {
    case NVN_BC1_RGB: case NVN_BC1_RGBA: case NVN_BC2: case NVN_BC3: return NVN_RGBA8;
    case NVN_BC1_RGB_SRGB: case NVN_BC1_RGBA_SRGB: case NVN_BC2_SRGB: case NVN_BC3_SRGB: return NVN_RGBA8_SRGB;
    case NVN_BC4: return NVN_R8; case NVN_BC4_SNORM: return NVN_R8_SNORM;
    case NVN_BC5: return NVN_RG8; case NVN_BC5_SNORM: return NVN_RG8_SNORM;
    default: return 0;
    }
}
int nvn_bc_can_unpack(int f) { return nvn_bc_unpacked_format(f) != 0; }

static void rgb565(uint16_t v, uint8_t c[3]) {
    unsigned r = v >> 11 & 31, g = v >> 5 & 63, b = v & 31;
    c[0] = (uint8_t)(r << 3 | r >> 2); c[1] = (uint8_t)(g << 2 | g >> 4); c[2] = (uint8_t)(b << 3 | b >> 2);
}

// The four colours of a BC1 colour block (RGBA). four: BC1_RGBA, BC2 and BC3 carry four colours whatever the endpoints' order;
// a BC1_RGB block whose first endpoint is not the larger is three colours and transparent black
static void bc1_colours(const uint8_t *blk, int four, uint8_t c[4][4]) {
    uint16_t e0 = (uint16_t)(blk[0] | blk[1] << 8), e1 = (uint16_t)(blk[2] | blk[3] << 8);
    rgb565(e0, c[0]); c[0][3] = 255;
    rgb565(e1, c[1]); c[1][3] = 255;
    if (four || e0 > e1) {
        for (int i = 0; i < 3; i++) {
            c[2][i] = (uint8_t)((2 * c[0][i] + c[1][i] + 1) / 3);
            c[3][i] = (uint8_t)((c[0][i] + 2 * c[1][i] + 1) / 3);
        }
        c[2][3] = c[3][3] = 255;
    } else {
        for (int i = 0; i < 3; i++) {
            c[2][i] = (uint8_t)((c[0][i] + c[1][i] + 1) / 2);
            c[3][i] = 0;
        }
        c[2][3] = 255; c[3][3] = 0;
    }
}

// The eight values a BC3 / BC4 block interpolates between its two endpoints (BC4 uses the same layout for its one channel)
static void bc4_values(const uint8_t *blk, uint8_t v[8]) {
    unsigned a0 = blk[0], a1 = blk[1];
    v[0] = (uint8_t)a0; v[1] = (uint8_t)a1;
    if (a0 > a1) {
        for (int k = 1; k <= 6; k++) v[k + 1] = (uint8_t)(((7 - k) * a0 + k * a1 + 3) / 7);
    } else {
        for (int k = 1; k <= 4; k++) v[k + 1] = (uint8_t)(((5 - k) * a0 + k * a1 + 2) / 5);
        v[6] = 0; v[7] = 255;
    }
}
static unsigned bc4_index(const uint8_t *blk, int t) {   // the block's 48-bit index field, three bits per texel, little-endian
    unsigned long long w = 0;
    for (int i = 0; i < 6; i++) w |= (unsigned long long)blk[2 + i] << (8 * i);
    return (unsigned)(w >> (3 * t) & 7);
}

static void block(int f, const uint8_t *src, uint8_t *dst, size_t dpitch, uint32_t bx, uint32_t by) {
    int wide = f <= NVN_BC3_SRGB;                          // RGBA8, else one or two 8-bit channels
    int bpp = wide ? 4 : (f == NVN_BC5 || f == NVN_BC5_SNORM ? 2 : 1);
    const uint8_t *cblk = src + (f == NVN_BC2 || f == NVN_BC2_SRGB || f == NVN_BC3 || f == NVN_BC3_SRGB ? 8 : 0);
    uint8_t rgba[4][4], r[8], g[8];
    if (wide) {
        bc1_colours(cblk, f != NVN_BC1_RGB && f != NVN_BC1_RGBA && f != NVN_BC1_RGB_SRGB && f != NVN_BC1_RGBA_SRGB, rgba);
        if (f == NVN_BC3 || f == NVN_BC3_SRGB) bc4_values(src, r);
    } else if (f == NVN_BC5 || f == NVN_BC5_SNORM) { bc4_values(src, r); bc4_values(src + 8, g); }
    else bc4_values(src, r);
    unsigned cidx = (unsigned)cblk[4] | (unsigned)cblk[5] << 8 | (unsigned)cblk[6] << 16 | (unsigned)cblk[7] << 24;
    for (int t = 0; t < 16; t++) {
        uint8_t *o = dst + (size_t)(by * 4 + t / 4) * dpitch + (size_t)(bx * 4 + t % 4) * bpp;
        if (wide) {
            const uint8_t *c = rgba[cidx >> (2 * t) & 3];
            o[0] = c[0]; o[1] = c[1]; o[2] = c[2]; o[3] = c[3];
            if (f == NVN_BC1_RGB || f == NVN_BC1_RGB_SRGB) o[3] = 255;   // a format without alpha: the third colour's entry is black, not transparent
            if (f == NVN_BC2 || f == NVN_BC2_SRGB) o[3] = (uint8_t)((src[t / 2] >> (t % 2 ? 0 : 4) & 15) * 17);   // the high nibble of each byte first
            else if (f == NVN_BC3 || f == NVN_BC3_SRGB) o[3] = r[bc4_index(src, t)];
        } else if (bpp == 2) {
            o[0] = r[bc4_index(src, t)]; o[1] = g[bc4_index(src + 8, t)];
        } else o[0] = r[bc4_index(src, t)];
    }
}

int nvn_bc_decode(int f, const void *src, size_t spitch, uint32_t w, uint32_t h, void *dst, size_t dpitch) {
    if (!nvn_bc_can_unpack(f)) return -1;
    size_t bpb = f == NVN_BC1_RGB || f == NVN_BC1_RGBA || f == NVN_BC1_RGB_SRGB || f == NVN_BC1_RGBA_SRGB ||
                 f == NVN_BC4 || f == NVN_BC4_SNORM ? 8 : 16;
    for (uint32_t by = 0; by < (h + 3) / 4; by++)
        for (uint32_t bx = 0; bx < (w + 3) / 4; bx++)
            block(f, (const uint8_t *)src + (size_t)by * spitch + (size_t)bx * bpb, (uint8_t *)dst, dpitch, bx, by);
    return 0;
}
