// BC (S3TC / RGTC / BPTC) decompression for GPUs without BC texture formats: Mali and the other mobile GPUs of the MediaTek
// and Samsung tablets, and Apple GPUs before the A17 Pro. The host keeps BC textures as they are where the GPU has them; a
// device without them is handed the uncompressed stand-in instead, decoded here once per upload.
#pragma once
#include <stddef.h>
#include <stdint.h>

// 1 when this NVN format is a BC format nvn_bc_decode() unpacks, 0 otherwise. BC6H and BC7 are not decompressed (they need
// an HDR / partitioned-block decoder no game here has yet asked for): a texture in one of those is dropped, and the caller says so.
int nvn_bc_can_unpack(int nvn_format);

// The uncompressed NVN format a BC format becomes, in the same numbering the rest of the host uses (0x25 RGBA8 / 0x37 RGBA8 sRGB
// for BC1–BC3, 0x01 R8 / 0x02 R8 SNORM for BC4, 0x0D RG8 / 0x0E RG8 SNORM for BC5, sRGB kept). 0 when the format is not a BC format.
int nvn_bc_unpacked_format(int nvn_format);

// Decompress one level (w × h texels) from its BC blocks — src, src_pitch bytes per row of 4×4 blocks — into the uncompressed
// format's rows, dst_pitch bytes per row of texels. Rows past the last whole block are written, and a width that is not a
// multiple of four leaves the tail of each row decoded but past w (the caller's pitch covers it).
// Returns 0, or -1 for a format this file does not decompress.
int nvn_bc_decode(int nvn_format, const void *src, size_t src_pitch, uint32_t w, uint32_t h, void *dst, size_t dst_pitch);

// Bytes one row of the decompressed level takes, for w texels of the uncompressed stand-in: a row is padded out to whole 4×4
// blocks, so it is ceil(w/4) × 4 texels wide (a caller's copy names that width). 0 when the format is not a BC format.
size_t nvn_bc_row_bytes(int nvn_format, uint32_t w);
