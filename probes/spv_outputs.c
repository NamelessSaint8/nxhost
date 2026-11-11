// Host-side entry to the exact Android fragment-export transform.
#include <stdio.h>
#include "../nxnative/dm/android/gfx_vk_spv_outputs.inc"
int main(int argc, char **argv) {
    if (argc != 5 && !(argc==6 && !strcmp(argv[5],"inputs"))) return 2;
    FILE *f = fopen(argv[1], "rb"); if (!f) return 2;
    if (fseek(f, 0, SEEK_END)) return 2;
    long bytes = ftell(f); rewind(f);
    if (bytes < 20 || bytes % 4) return 2;
    uint32_t *w = malloc((size_t)bytes), nw = 0;
    if (!w || fread(w, 1, (size_t)bytes, f) != (size_t)bytes) return 2;
    fclose(f);
    uint32_t *out = (argc==6?spv_int_inputs:spv_int_outputs)(w, (uint32_t)bytes/4, (uint32_t)strtoul(argv[3], NULL, 0), (uint32_t)strtoul(argv[4], NULL, 0), &nw);
    free(w); if (!out) return 3;
    f = fopen(argv[2], "wb"); if (!f) { free(out); return 2; }
    int ok = fwrite(out, 4, nw, f) == nw; if (fclose(f)) ok = 0;
    free(out); return ok ? 0 : 2;
}
