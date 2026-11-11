---
status: resolved
trigger: "Let's do it: remaining sampling modes and actual attachment validation."
created: 2026-11-10
updated: 2026-11-10
---

## Result

Android offset/gather sampling and typed integer fragment exports pass production GPU checks. All 21 real offset/gather programs convert. Independent validation and device loading pass. Fourteen pipeline cases cover twelve attachment contexts captured from the accepted Mac renderer. The full Android game has not launched; gameplay memory, frame stalls and the 9–10 GB target remain open.

The complete Mac reference and measurement overlay remain available. Its bounded diagnostic run exited cleanly. No shared host replacement, app installation, Android global setting, clock change or commit occurred. Unrelated OOT work is untouched. Game-derived files remain on the external game drive.

## Sampling evidence

The helper supports explicit LOD offsets, fragment implicit offsets with optional bias, fetch offsets, and default/selected-component gathers with single/four offsets. Native fallback calls keep local constant operands. Offsets apply in texels independently at each logical mip before wrapping. Gathers use the logical base mip and specified component order. Four independent offsets each originate at the lower-left base texel.

The final binary passes 15,750 checks: 198 compressed-reference checks plus 15,552 cases of 1,024 pixel comparisons, totaling 15,925,248 comparisons. Coverage includes BC6H, ASTC4x4, ASTC8x8 sRGB, both GOB orders, filters, clamp/repeat, full/mip-layer/swizzled views and LOD/bias variations. Ignoring only filter offsets fails 3,440 checks; reversing only gather order fails 5,328. Both control modules independently validate.

All 21 real programs containing these floating array operations convert with 24 atlas bindings and no unknown reflected resources. Each validates and loads on-device. This resolves both programs blocked in the preceding implicit/query subset. It does not establish a complete atlas-enabled release bundle for every game program.

## Attachment evidence

The frozen complete Mac reference runs for 100 seconds with the overlay and pass diagnostics. The trace contains 1,005 native mesh draws in twelve contexts. Colors use RGBA16Float, RGBA16Unorm, RGBA8Unorm and R8Uint. The extractor joins the latest draw state before each mesh marker, including multiple programs sharing one pass. This capture is diagnostic, not a performance benchmark.

The R8Uint pass exposed a float fragment-output declaration incompatible with the integer attachment. Android now selects output types from actual attachment view formats and bitcasts export stores and output loads. Mixed signed/unsigned/float locations remain independent. Variants compose with existing image/depth/per-primitive transforms. Unsupported output layouts fail explicitly. A growing cache keeps modules beyond the previous eight-entry limit.

Host sanitizer checks and independent SPIR-V validation cover mixed targets and scalar/component access. Production GPU replay passes 88 checks, including all 27 numeric-class combinations across three MRTs, a narrow R8 target, return to the original float module and 26 cached variants. The real R8-target shader independently validates after transformation.

All fourteen real pipeline checks pass with recorded color formats, blend/depth/cull/write-mask state and sample counts. Two depth contexts each have two alternatives: Metal format 260 loses the original D24S8 versus D32S8 distinction, so both are checked. R8Uint uses an unsigned attachment matching its observed numeric type. These are compile-only checks; no real shader receives fabricated game buffers.

## Verification and continuation

The same final binary passes 2,166 implicit, 102 driver, 856 atlas, 120 captured-terrain and ten ordinary draw checks, plus five pool-restoration sizes. All 194 Android sources compile. Sixteen host tests and configured targeted Ruff pass. The shell API validation layer remains unavailable. The five-title preflight selects MKW, Rise, Odyssey, TotK and Xenoblade3 for shared sampling/output paths; packaged Mac builds are missing. Docs have three existing failures.

Evidence: `/Volumes/Data/Switch/Mario Kart World/0400C3F00006E000-work/android-offset-20261110/`. Final binary SHA256: `c5e530d18b3d1514b2be532353b5889894672427480e22068a3c0983daacd8ca`. Host and device hashes match. The archive preserves exact sources and generated shaders alongside control bundles, validation, raw logs, attachment provenance and reproduction scripts.

Device/toolchain: Lenovo TB323FU, Adreno840, API36, Vulkan1.4.295, driver2c410f6f5c, NDK28.2.13676358/API31. Owned device directory: `/data/local/tmp/nxhost-mkw-offset-20261110`.

Next build the Android profile and attempt a bounded scene with the overlay. Measure texture completeness, startup, actual process/graphics memory and frame stalls against the complete Mac reference. Keep unsupported atlas modes explicit. No new full-game memory saving or Android FPS is claimed.
