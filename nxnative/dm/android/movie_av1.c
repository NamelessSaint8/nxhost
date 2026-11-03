// Android port: no AV1 movie decoder yet (dm/host/hle_movie_av1.c is VideoToolbox + dav1d; a MediaCodec or dav1d build for Android is future work, M0 excludes
// the file). The interface stubs out: no decoder, so a game whose movies are AV1 (Fire Emblem Fortune's Weave) gets its movies skipped like a game with no
// decoder at all (hle_movie_av1.c's own no-decoder path is what the Mac had before dav1d was vendored). av1C parsing (mav1_av1c) is host code, kept here.
#include "dm.h"
#include "hle_movie_av1.h"
#include <stdlib.h>
#include <string.h>

mav1 *mav1_new(void) { return NULL; }
void mav1_free(mav1 *a) { (void)a; }
void mav1_reset(mav1 *a) { (void)a; }
int mav1_decode(mav1 *a, const uint8_t *data, size_t n, mav1_picture *out) { (void)a; (void)data; (void)n; (void)out; return -1; }
const char *mav1_backend(const mav1 *a) { (void)a; return "none"; }

// The AV1 binding's av1C record (ISO-BMFF 2.3.3): seq_profile 3 bits, seq_level_idx_0 5 bits, then the flags, from the sequence header OBU's first bytes
int mav1_av1c(const uint8_t *obu, size_t n, uint8_t c[4], int *w, int *h) {
    if (n < 4) return 0;
    c[0] = (uint8_t)((obu[0] << 5) | (obu[1] >> 3));   // seq_profile << 5 | seq_level_idx_0 >> 3
    c[1] = (uint8_t)((obu[1] << 5) | 0x10);            // the rest of seq_level_idx_0, initial_presentation_delay 0 (absent)
    c[2] = c[3] = 0;
    *w = *h = 0;
    return 1;
}
