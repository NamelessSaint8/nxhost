// BC decompression unit tests (milliseconds). A BC1/BC2/BC3/BC4/BC5 blocks decoded against hand-calculated texel values;
// B the two interpolation modes and the transparent texel; C geometry: block rows, pitches, a size that is not whole blocks;
// D the format mapping (including the ones with no decoder).
// Usage: t_bc
#include "../nvn_bc.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static int checks, fails;
#define CHECK(c, ...) do { checks++; if (!(c)) { fails++; printf("  ✗ "); printf(__VA_ARGS__); printf("\n"); } } while (0)

static void put565(uint8_t *b, uint16_t c0, uint16_t c1, const unsigned *codes) {   // a BC1 colour block: two RGB565 endpoints, 2-bit codes
    unsigned w = 0;
    b[0] = (uint8_t)c0; b[1] = (uint8_t)(c0 >> 8); b[2] = (uint8_t)c1; b[3] = (uint8_t)(c1 >> 8);
    for (int t = 0; t < 16; t++) w |= (codes[t] & 3) << (2 * t);
    for (int i = 0; i < 4; i++) b[4 + i] = (uint8_t)(w >> (8 * i));
}
static void put_alpha(uint8_t *b, unsigned a0, unsigned a1, const unsigned *codes) {   // a BC3 / BC4 block: two endpoints, 3-bit codes, 48 bits
    unsigned long long w = 0;
    b[0] = (uint8_t)a0; b[1] = (uint8_t)a1;
    for (int t = 0; t < 16; t++) w |= (unsigned long long)(codes[t] & 7) << (3 * t);
    for (int i = 0; i < 6; i++) b[2 + i] = (uint8_t)(w >> (8 * i));
}

// Decodes one block (4×4) of a format into out[] as RGBA (r8 stays in the first channel) and returns its byte count per texel
static int one_block(int fmt, const uint8_t *blocks, uint8_t out[16][4]) {
    uint8_t row[16 * 4];
    int f2 = nvn_bc_unpacked_format(fmt);
    int bpp = f2 == 0x25 || f2 == 0x37 ? 4 : f2 == 0x0D || f2 == 0x0E ? 2 : 1;
    size_t dpitch = (size_t)4 * bpp;   // four texels a row
    memset(out, 0, 16 * 4); memset(row, 0xEE, sizeof row);
    CHECK(!nvn_bc_decode(fmt, blocks, 16 * 2, 4, 4, row, dpitch), "decode failed for format %#x", fmt);
    for (int t = 0; t < 16; t++) memcpy(out[t], row + (size_t)(t / 4) * dpitch + (size_t)(t % 4) * bpp, (size_t)bpp);
    return bpp;
}

static void groupA(void) {   // BC1 four-colour: white and black endpoints, codes 0..3 in turn
    unsigned codes[16]; for (int t = 0; t < 16; t++) codes[t] = (unsigned)(t % 4);
    uint8_t blk[8]; put565(blk, 0xFFFF, 0x0000, codes);
    uint8_t o[16][4]; int bpp = one_block(0x42, blk, o);
    CHECK(bpp == 4, "BC1_RGBA decodes to %d bytes per texel, not 4", bpp);
    // e0 = white, e1 = black, e0 > e1: c2 = (2·255 + 0 + 1)/3 = 170, c3 = (255 + 2·0 + 1)/3 = 85
    static const uint8_t want[4][4] = {{255, 255, 255, 255}, {0, 0, 0, 255}, {170, 170, 170, 255}, {85, 85, 85, 255}};
    int ok = 1;
    for (int t = 0; t < 16; t++) ok &= !memcmp(o[t], want[t % 4], 4);
    CHECK(ok, "BC1 four-colour: texel 0 is %d %d %d %d, texel 2 %d %d %d %d (expected 255s, then 0s, then 170s, then 85s)",
          o[0][0], o[0][1], o[0][2], o[0][3], o[2][0], o[2][1], o[2][2], o[2][3]);
    printf("  A BC1 %-28s c0 255 255 255, c1 0 0 0, c2 170, c3 85 %s\n", "four-colour endpoints", ok ? "as specified" : "DIFFERS");

    // RGB565 expansion: 0x8000 = bits 11..15 = 16 of 31 red → (16 << 3) | (16 >> 2) = 132 ; 0x07E0 = full green = 255
    put565(blk, 0x8000, 0x07E0, codes);
    one_block(0x42, blk, o);
    CHECK(o[0][0] == 132 && o[0][1] == 0 && o[1][1] == 255, "RGB565 expansion: %d %d / %d %d", o[0][0], o[0][1], o[1][0], o[1][1]);
    printf("  A BC1 %-28s 0x8000 → r 132, 0x07E0 → g 255\n", "RGB565 expansion");
}

static void groupB(void) {   // three colours and the transparent texel, the explicit alpha of BC2, both BC3 modes, BC4 / BC5 channels
    unsigned codes[16]; for (int t = 0; t < 16; t++) codes[t] = (unsigned)(t % 4);
    uint8_t blk[16], o[16][4];
    put565(blk, 0x0000, 0xFFFF, codes);   // e0 <= e1: three colours
    one_block(0x41, blk, o);   // BC1_RGB: the fourth code is black, its alpha opaque (the format has none)
    CHECK(o[0][0] == 0 && o[1][0] == 255 && o[2][0] == 128, "BC1 three-colour: %d %d %d (expected 0, 255, 128)", o[0][0], o[1][0], o[2][0]);
    CHECK(o[3][0] == 0 && o[3][3] == 255, "BC1_RGB fourth code: %d with alpha %d (expected 0 and 255)", o[3][0], o[3][3]);
    one_block(0x42, blk, o);   // BC1_RGBA: the fourth code is transparent black
    CHECK(o[3][3] == 0, "BC1_RGBA fourth code alpha %d (expected 0)", o[3][3]);
    printf("  B BC1 %-28s three colours, fourth code 128 = (0 + 255 + 1)/2, alpha 0 for RGBA\n", "endpoints out of order");

    memset(blk, 0, sizeof blk);
    put565(blk + 8, 0xFFFF, 0xFFFF, codes);
    blk[0] = 0x0F; blk[1] = 0xF0;   // texels 0..3: 0, 255, 255, 0 in turn
    one_block(0x43, blk, o);
    CHECK(o[0][3] == 0 && o[1][3] == 255 && o[2][3] == 255 && o[3][3] == 0, "BC2 alpha %d %d %d %d (expected 0 255 255 0)", o[0][3], o[1][3], o[2][3], o[3][3]);
    printf("  B BC2 %-28s 4-bit alpha × 17: 0, 255, 255, 0\n", "explicit alpha nibbles");

    put_alpha(blk, 255, 0, codes);  memset(blk + 8, 0, 8);
    put565(blk + 8, 0xFFFF, 0xFFFF, codes);
    one_block(0x44, blk, o);
    // a0 > a1: value[k] = ((7 - k)·255 + k·0 + 3)/7 = 219, 182, 146, 109, 73, 36 for k = 1..6
    static const uint8_t want8[8] = {255, 0, 219, 182, 146, 109, 73, 36};
    int ok = 1;
    for (int t = 0; t < 16; t++) ok &= o[t][3] == want8[t % 4];
    CHECK(ok, "BC3 eight-value alpha: texel 3 is %d (expected 109)", o[3][3]);
    printf("  B BC3 %-28s 255, 0, 219, 182, 146, 109, 73, 36 %s\n", "eight interpolated values", ok ? "as specified" : "DIFFERS");

    put_alpha(blk, 0, 255, codes);
    one_block(0x44, blk, o);
    // a0 <= a1: value[k] = (k·255 + 2)/5 = 51, 102, 153, 204 for k = 1..4, then 0 and 255
    static const uint8_t want6[8] = {0, 255, 51, 102, 153, 204, 0, 255};
    ok = 1;
    for (int t = 0; t < 16; t++) ok &= o[t][3] == want6[t % 4];
    CHECK(ok, "BC3 six-value alpha: texel 3 is %d (expected 204)", o[3][3]);
    printf("  B BC3 %-28s 0, 255, 51, 102, 153, 204, 0, 255 %s\n", "six values and two limits", ok ? "as specified" : "DIFFERS");

    put_alpha(blk, 200, 100, codes);   // BC4 alone: one channel, no alpha
    int bpp = one_block(0x49, blk, o);
    // 200 > 100: value[k] = ((7 - k)·200 + k·100 + 3)/7 = 186, 171, 157, 143, 129, 114 for k = 1..6, so code 3 is 171
    CHECK(bpp == 1, "BC4 decodes to %d bytes per texel, not 1", bpp);
    CHECK(o[0][0] == 200 && o[1][0] == 100 && o[2][0] == 186 && o[3][0] == 171, "BC4 values %d %d %d %d (expected 200 100 186 171)",
          o[0][0], o[1][0], o[2][0], o[3][0]);
    printf("  B BC4 %-28s one channel: 200, 100, 186, 171 for codes 0..3\n", "RGTC single channel");

    put_alpha(blk, 255, 0, codes); put_alpha(blk + 8, 0, 255, codes);   // BC5: R from the first, G from the second block
    bpp = one_block(0x4B, blk, o);
    CHECK(bpp == 2, "BC5 decodes to %d bytes per texel, not 2", bpp);
    CHECK(o[0][0] == 255 && o[0][1] == 0 && o[1][0] == 0 && o[1][1] == 255, "BC5 texels %d/%d and %d/%d (expected 255/0 and 0/255)",
          o[0][0], o[0][1], o[1][0], o[1][1]);
    printf("  B BC5 %-28s R and G from two blocks: 255/0 then 0/255\n", "RGTC two channels");

    // The codes pick the eight values in turn: every texel's alpha is the table entry its code names
    unsigned ramp[16]; for (int t = 0; t < 16; t++) ramp[t] = (unsigned)(t % 8);
    put_alpha(blk, 255, 0, ramp); put565(blk + 8, 0x0000, 0xFFFF, ramp);
    one_block(0x44, blk, o);
    ok = 1;
    for (int t = 0; t < 16; t++) ok &= o[t][3] == want8[t % 8];
    CHECK(ok, "BC3 alpha by code: texel 5 is %d (expected %d)", o[5][3], want8[5]);
    printf("  B BC3 %-28s all eight codes reach their value: %d %d %d …\n", "every code in turn", o[0][3], o[1][3], o[2][3]);
}

static void groupC(void) {   // geometry: two block columns and rows, a destination pitch set by the caller, width 7 × height 5
    uint8_t src[2 * 2 * 8], out[8 * 32];
    unsigned solid[16]; for (int t = 0; t < 16; t++) solid[t] = 0;
    memset(src, 0, sizeof src);
    put565(src + 0, 0x001F, 0x001F, solid);            // block (0,0): blue
    put565(src + 8, 0x07E0, 0x07E0, solid);            // block (1,0): green
    put565(src + 16, 0xF800, 0xF800, solid);           // block (0,1): red
    put565(src + 24, 0xFFFF, 0xFFFF, solid);           // block (1,1): white
    memset(out, 0xEE, sizeof out);
    size_t dpitch = 8 * 4;   // two blocks wide: 8 texels of RGBA8
    CHECK(!nvn_bc_decode(0x41, src, 16, 7, 5, out, dpitch), "7×5 decode failed");
    uint8_t *px = out;
    CHECK(px[0 * 4 + 2] == 255 && px[0 * 4 + 0] == 0, "texel (0,0) should be blue: %d %d", px[0], px[2]);
    CHECK(px[4 * 4 + 1] == 255, "texel (4,0) should be green: %d %d %d", px[16], px[17], px[18]);
    CHECK(px[4 * dpitch + 0] == 255 && px[4 * dpitch + 1] == 0, "texel (0,4) should be red");
    CHECK(px[4 * dpitch + 4 * 4 + 0] == 255 && px[4 * dpitch + 4 * 4 + 1] == 255, "texel (4,4) should be white");
    CHECK(px[0 * 4 + 3] == 255, "BC1_RGB alpha should be opaque");
    printf("  C %-34s 2×2 blocks at pitch %zu: blue, green, red, white in place\n", "7×5 texture from blocks", dpitch);

    // The tail of a 7-wide row: texel 7 lies past the width but inside the pitch, so the block's fourth texel is written there
    CHECK(px[7 * 4 + 1] == 255 && px[4 * dpitch + 7 * 4 + 0] == 255, "the block's fourth texel was not written");
    printf("  C %-34s a 7-wide row's fourth texel written inside the pitch\n", "partial block column");
}

static void groupD(void) {   // the format mapping: what each BC format becomes, and what is not decompressed
    static const struct { int bc, want; const char *what; } map[] = {
        {0x41, 0x25, "BC1_RGB → RGBA8"}, {0x42, 0x25, "BC1_RGBA → RGBA8"}, {0x43, 0x25, "BC2 → RGBA8"}, {0x44, 0x25, "BC3 → RGBA8"},
        {0x45, 0x37, "BC1_RGB sRGB → RGBA8 sRGB"}, {0x46, 0x37, "BC1_RGBA sRGB → RGBA8 sRGB"},
        {0x47, 0x37, "BC2 sRGB → RGBA8 sRGB"}, {0x48, 0x37, "BC3 sRGB → RGBA8 sRGB"},
        {0x49, 0x01, "BC4 → R8"}, {0x4A, 0x02, "BC4 SNORM → R8 SNORM"}, {0x4B, 0x0D, "BC5 → RG8"}, {0x4C, 0x0E, "BC5 SNORM → RG8 SNORM"},
    };
    int ok = 1;
    for (size_t i = 0; i < sizeof map / sizeof *map; i++) {
        int got = nvn_bc_unpacked_format(map[i].bc);
        if (got != map[i].want) { ok = 0; printf("  ✗ %s gave %#x, not %#x\n", map[i].what, got, map[i].want); }
        if (!nvn_bc_can_unpack(map[i].bc)) { ok = 0; printf("  ✗ %s is not offered as decompressable\n", map[i].what); }
    }
    checks++; if (!ok) fails++;
    printf("  D %-34s %zu mappings checked\n", "BC → uncompressed format", sizeof map / sizeof *map);

    CHECK(!nvn_bc_unpacked_format(0x4D) && !nvn_bc_can_unpack(0x4E) && !nvn_bc_can_unpack(0x50), "BC7 / BC6H must stay undecompressed");
    CHECK(!nvn_bc_can_unpack(0x25) && !nvn_bc_unpacked_format(0x01), "a format that is not BC must map to nothing");
    uint8_t b[16] = {0}, o[64];
    CHECK(nvn_bc_decode(0x4D, b, 16, 4, 4, o, 16) == -1, "BC7 must be refused by the decoder");
    printf("  D %-34s BC7 and BC6H refused, not mis-decoded\n", "no decoder, no guess");

    // The sRGB pairs carry their gamma in the format, not in the data: the same block decodes to the same bytes
    unsigned codes[16]; for (int t = 0; t < 16; t++) codes[t] = (unsigned)(t % 4);
    uint8_t blk[8], a[16][4], s[16][4];
    put565(blk, 0x1234, 0x8765, codes);
    one_block(0x42, blk, a); one_block(0x46, blk, s);
    CHECK(!memcmp(a, s, sizeof a), "a BC1 block decoded differently as sRGB");
    printf("  D %-34s the same bytes for the UNORM and sRGB formats\n", "sRGB in the format only");
}

static void groupE(void) {   // the row the caller sizes its scratch and its copy by: padded to whole blocks, per channel width
    static const struct { int fmt; uint32_t w; size_t want; } rows[] = {
        {0x42, 1, 16}, {0x42, 3, 16}, {0x42, 4, 16}, {0x42, 5, 32}, {0x42, 7, 32}, {0x42, 8, 32}, {0x42, 1024, 4096},
        {0x46, 1000, 4000}, {0x44, 999, 4000}, {0x49, 5, 8}, {0x4A, 4, 4}, {0x4B, 3, 8}, {0x4C, 1, 8},
    };
    int ok = 1;
    for (size_t i = 0; i < sizeof rows / sizeof *rows; i++) {
        size_t got = nvn_bc_row_bytes(rows[i].fmt, rows[i].w);
        if (got != rows[i].want) { ok = 0; printf("  ✗ %#x width %u: %zu bytes a row, not %zu\n", rows[i].fmt, rows[i].w, got, rows[i].want); }
    }
    checks++; if (!ok) fails++;
    printf("  E %-34s 13 widths, RGBA8 / RG8 / R8, padded to whole 4×4 blocks\n", "row bytes of a decompressed level");

    CHECK(!nvn_bc_row_bytes(0x25, 8) && !nvn_bc_row_bytes(0x4D, 8), "a format with no decompression must have no row");
    printf("  E %-34s uncompressed and BC7 formats give 0\n", "no decoder, no row");
}

int main(void) {
    printf("BC decompression\n");
    groupA(); groupB(); groupC(); groupD(); groupE();
    printf("%s: %d checks, %d failed\n", fails ? "FAIL" : "ok", checks, fails);
    return fails ? 1 : 0;
}
