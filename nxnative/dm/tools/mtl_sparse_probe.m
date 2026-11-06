// Does this Metal device support sparse textures, and for which formats? Mario Kart World's 8192x8192, 68-layer arrays are 2-9% mapped on the console, and the host
// materialises them dense (5803 MB BC6H, 1453 MB ASTC 8x8). A sparse texture would let us map only the pages that exist -- but only if Metal offers sparse placement
// for those block-compressed formats, which is what this asks. Prints one line per format: tile size (0 = no sparse support for it) and whether a sparse heap
// instance and a placed sparse texture can be made.
// Build: clang -fobjc-arc -framework Metal -framework Foundation -o mtl_sparse_probe mtl_sparse_probe.m
#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <stdio.h>

static const char *fmt_name(MTLPixelFormat f) {
    switch (f) {
        case MTLPixelFormatBC6H_RGBUfloat: return "BC6H_RGBUfloat (MKW's 5.8 GB array)";
        case MTLPixelFormatBC7_RGBAUnorm: return "BC7_RGBAUnorm";
        case MTLPixelFormatASTC_8x8_sRGB: return "ASTC_8x8_sRGB (MKW's 1.45 GB arrays)";
        case MTLPixelFormatASTC_4x4_LDR: return "ASTC_4x4_LDR";
        case MTLPixelFormatBGRA8Unorm: return "BGRA8Unorm (control)";
        default: return "?";
    }
}

int main(void) {
    @autoreleasepool {
        id<MTLDevice> dev = MTLCreateSystemDefaultDevice();
        if (!dev) { printf("no Metal device\n"); return 1; }
        printf("device: %s  unified %s\n", dev.name.UTF8String, dev.hasUnifiedMemory ? "yes" : "no");
        MTLPixelFormat fmts[] = {MTLPixelFormatBC6H_RGBUfloat, MTLPixelFormatBC7_RGBAUnorm, MTLPixelFormatASTC_8x8_sRGB,
                                 MTLPixelFormatASTC_4x4_LDR, MTLPixelFormatBGRA8Unorm};
        for (unsigned i = 0; i < sizeof fmts / sizeof *fmts; i++) {
            MTLPixelFormat f = fmts[i];
            MTLSize ts = [dev sparseTileSizeWithTextureType:MTLTextureType2DArray pixelFormat:f sampleCount:1];
            NSUInteger tile = ts.width * ts.height * ts.depth;
            MTLTextureDescriptor *d = [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:f width:8192 height:8192 mipmapped:YES];
            d.textureType = MTLTextureType2DArray; d.arrayLength = 68; d.mipmapLevelCount = 12;
            d.usage = MTLTextureUsageShaderRead;
            id<MTLTexture> sparse = nil; id<MTLHeap> heap = nil;
            if (tile) {
                MTLHeapDescriptor *hd = [MTLHeapDescriptor new];
                hd.type = MTLHeapTypeSparse;   // a sparse heap needs a size: without one the device returns nil
                hd.size = 8ull << 30;
                heap = [dev newHeapWithDescriptor:hd];
                if (heap) { sparse = [heap newTextureWithDescriptor:d offset:0]; }
            }
            printf("%-38s tile %5lu B  heap %s  placed %s", fmt_name(f), (unsigned long)tile, heap ? "ok" : "no", sparse ? "ok" : "no");
            if (sparse) printf("  %.0f MB for %.0f MB dense", (double)sparse.allocatedSize / 1048576.0, 5803.0);
            printf("\n");
        }
        printf("max sparse tile: %lu B\n", (unsigned long)dev.sparseTileSizeInBytes);
    }
    return 0;
}
