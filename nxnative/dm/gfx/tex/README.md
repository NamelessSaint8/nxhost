# dm/gfx/tex — texture format mapping, block-linear deswizzling, BC decompression

The part of the graphics layer that deals with texture data, called by the replay layer `../nvn/nvn_mtl.m`. It does three things:

1. converts NVN texture format numbers to Metal pixel formats;
2. unpacks the Switch's "block-linear" layout into an ordinary row-by-row layout;
3. decompresses BC textures on GPUs that do not support BC compressed textures.

Block linear is how the Tegra X1 GPU stores textures: the data is not one row after another, but interleaved in small blocks of 64 bytes × 8 rows (GOBs), and several GOBs are then stacked into larger blocks according to a "block height" and a "block depth". The game's packaged texture files are in exactly this layout, and it must be undone before uploading to Metal.

## Files

| File | Contents |
|---|---|
| `nvn_fmt_mtl.h`, `nvn_fmt_mtl.c` | `nvn_fmt_to_mtl()`: NVN format (0x01–0x9C) → Metal pixel format + component remapping. Returns 1 for an exact match, 2 for a substitute (precision, bit order or interpretation differs and a conversion is needed), 0 when Metal has no corresponding format. How each format is handled is written in the comments inside the table. Pure C, no dependency on Metal headers |
| `nvn_deswizzle.h`, `nvn_deswizzle.c` | `nvn_deswizzle()`: deswizzles one level and one layer from block linear to linear; `nvn_swizzle()`: the reverse, used for round trips in unit tests; `nvn_bl_offset()`: the block-linear address of a single point. Pure C |
| `nvn_deswizzle_gpu.h`, `nvn_deswizzle_gpu.m` | A Metal compute shader version of the same deswizzling algorithm, used by the replay layer when uploading packaged textures; when initialization fails or an unsupported format is encountered, the replay layer falls back to the CPU version |
| `nvn_bc.h`, `nvn_bc.c` | `nvn_bc_decode()`: decompresses one level of BC1, BC2, BC3, BC4 or BC5 blocks into rows of RGBA8, R8 or RG8 texels; `nvn_bc_unpacked_format()`: the uncompressed NVN format each of those becomes; `nvn_bc_can_unpack()`. Used where the GPU has no BC formats. Pure C |
| `tests/` | Unit tests |

The offsets of each level and layer within the storage, and the block height and block depth actually used by each level, are all taken from `../nvn/nvn_tex.c` (`nvn_tex_layout`, `nvn_tex_level_offset`, `nvn_tex_level_tiles`); this directory only does addressing and moving within a level. Packaged parameters override the automatic block dimensions: [Packaged texture block dimensions and linear storage rows](../../../docs/reference/nvn-objects.md#packaged-texture-block-dimensions-and-linear-storage-rows).

## BC textures

Where the GPU has BC compressed textures (`supportsBCTextureCompression` of `MTLDevice`: Apple silicon Macs and the latest iPhones; `textureCompressionBC` on Vulkan), a BC texture is created and uploaded as BC, block for block.

Where it does not — a Mali GPU on the MediaTek Dimensity and Samsung tablets, Apple GPUs before the A17 Pro — the texture becomes the uncompressed format that stands in for it and `nvn_bc_decode()` decompresses the guest's blocks at upload: BC1, BC2 and BC3 → RGBA8 (sRGB kept), BC4 → R8, BC5 → RG8. The Vulkan backend does this in `dm/android/gfx_vk_tex.c` (`pkg_upload_`: the blocks are deswizzled into one scratch range and decoded into another, and a row is padded to whole 4×4 blocks). Cost: four texel bytes where BC3 had one for the colour formats, which is GPU memory (Skyrim's live textures: 161 MB → about 640 MB) and the bandwidth a tiling GPU reads them with. BC6H and BC7 have no decoder here and are still dropped, with a line in the log: a game that needs them needs an HDR or a partitioned-block decoder first.

A BC texture is never a render target and its raw blocks are not sampled through an uncompressed view (Metal has no such views; Breath of the Wild encodes one 32×32 BC4 texture on the GPU, GitHub issue #4). A texture read through a view of *another* BC format (the block-size reinterpretation a game can make of one storage, which a BC GPU does in hardware) is decoded once as the texture's own format here, so such a view is not reproduced.

## Tests

```sh
make -C dm/gfx/tex/tests run       # run t_fmt_mtl, t_tex and t_bc
```

- **`t_fmt_mtl`**: takes the mapping for every NVN format in 0x01–0x9C and, for every one whose mapping is not 0, actually creates a texture on the local Metal device; all of them must be created successfully. It also checks that every NVN format with sRGB in its name lands on a Metal sRGB format. No game files needed.
- **`t_tex`**: the deswizzling tests, in several groups:

  | Group | Criterion |
  |---|---|
  | A round trip | Writes random data into each level and layer and reads it back out; must be byte-for-byte equal. Covers 2D, 2D array and 3D, several bytes-per-block values and non-power-of-two sizes |
  | B address formula | The result of `nvn_bl_offset()` equals the address computed by hand from the public layout rules |
  | D differential copies | Both copy directions match a byte-address oracle for 1,029 deterministic layouts, including padded pitches, byte tails, sparse mip tails, packaged block dimensions, arrays and cubes; untouched storage and row padding are compared too |
  | E hand-made 3D | Places markers at hand-computed addresses, checks where they land after deswizzling, and checks block height, block depth and storage size |

  The A round trip can only prove "one-to-one and within bounds"; it cannot prove that the layout formula is right. What backs it up is the hand-computed addresses of groups B and E, and the games that render right.

- **`t_bc`**: the decompression tests, against values calculated by hand from the block formats — BC1's four-colour and three-colour modes with the transparent texel, its RGB565 expansion, BC2's four-bit alpha in the high nibble of each byte first, BC3's eight-value and six-value alpha modes, BC4's single and BC5's two channels, a block row whose width is not a multiple of four, and the format mapping (BC7 and BC6H must be refused rather than mis-decoded).

## Limitations

- `nvn_deswizzle()` does not support multisampled textures, textures with the LINEAR flag (which are linear to begin with) or the BUFFER target; it returns -1 when it encounters them.
- Cubes and cube arrays are handled as layered textures.
- The component bit order of the 16-bit packed formats (565 / 5551 / 4444) is mapped according to the format names and has not been checked with real data; they are marked as "substitute" in the format table.
