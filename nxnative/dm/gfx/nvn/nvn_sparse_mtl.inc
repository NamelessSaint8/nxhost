// NVN sparse textures whose 64 KB tile geometry matches Metal's. Read-only versions share immutable tiles; GPU-only images share mutable physical pages across aliases.
// Placement-sparse metadata and its physical placement heaps are separate resident allocations.
typedef struct { uint64_t off; uint32_t x, y, level, layer; } sparse_tile;
// A page's last owner returns its slot only after every metadata version using it has retired on its GPU fence.
static pthread_mutex_t g_sparse_mu = PTHREAD_MUTEX_INITIALIZER;
static pthread_mutex_t g_sparse_transfer_mu=PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t g_sparse_transfer_cv=PTHREAD_COND_INITIALIZER;
#define SPARSE_TRANSFER_BYTES (128ull<<20)
static size_t g_sparse_transfer_bytes,g_sparse_transfer_peak;
static unsigned g_sparse_transfer_waiters;
static _Atomic uint64_t g_sparse_failure_gen;
static void sparse_upload_wait(void){pthread_mutex_lock(&g_sparse_transfer_mu);while(g_sparse_transfer_bytes)pthread_cond_wait(&g_sparse_transfer_cv,&g_sparse_transfer_mu);pthread_mutex_unlock(&g_sparse_transfer_mu);}
static void sparse_transfer_begin(size_t n){
    pthread_mutex_lock(&g_sparse_transfer_mu);
    while(g_sparse_transfer_bytes && (n>SPARSE_TRANSFER_BYTES || g_sparse_transfer_bytes>SPARSE_TRANSFER_BYTES-n)){
        g_sparse_transfer_waiters++;pthread_cond_broadcast(&g_sparse_transfer_cv);pthread_cond_wait(&g_sparse_transfer_cv,&g_sparse_transfer_mu);g_sparse_transfer_waiters--;
    }
    g_sparse_transfer_bytes+=n;if(g_sparse_transfer_bytes>g_sparse_transfer_peak)g_sparse_transfer_peak=g_sparse_transfer_bytes;
    pthread_mutex_unlock(&g_sparse_transfer_mu);
}
static void sparse_transfer_end(size_t n){pthread_mutex_lock(&g_sparse_transfer_mu);g_sparse_transfer_bytes-=n;pthread_cond_broadcast(&g_sparse_transfer_cv);pthread_mutex_unlock(&g_sparse_transfer_mu);}
@interface NvSparseBlock : NSObject { @public id<MTLHeap> heap; uint64_t used[4]; unsigned capacity; } @end
@implementation NvSparseBlock
- (void)dealloc { res_remove(heap); }
@end
@interface NvSparsePage : NSObject { @public NvSparseBlock *block; unsigned index; } @end
@implementation NvSparsePage
- (void)dealloc { if (block) { pthread_mutex_lock(&g_sparse_mu); block->used[index/64] &= ~(1ull << (index%64)); pthread_mutex_unlock(&g_sparse_mu); } }
@end
static NSHashTable<NvSparseBlock *> *g_sparse_blocks;
static NSMapTable<NSData *,NvSparsePage *> *g_sparse_physical;
static NvSparsePage *sparse_page(MTLTextureDescriptor *d, size_t demand) { @autoreleasepool {
    NvSparsePage *page=[NvSparsePage new];
    pthread_mutex_lock(&g_sparse_mu);
    if(!g_sparse_blocks)g_sparse_blocks=[NSHashTable weakObjectsHashTable];
    for(NvSparseBlock *b in g_sparse_blocks)for(unsigned word=0;word<4;word++)if(b->used[word]!=UINT64_MAX){page->block=b;page->index=word*64+__builtin_ctzll(~b->used[word]);goto found;}
    {
        NvSparseBlock *b=[NvSparseBlock new]; b->capacity=(unsigned)MIN(MAX(demand,1u),256u);
        for(unsigned i=b->capacity;i<256;i++)b->used[i/64] |= 1ull<<(i%64);
        MTLHeapDescriptor *hd=[MTLHeapDescriptor new]; hd.type=MTLHeapTypePlacement;hd.storageMode=MTLStorageModePrivate;
        hd.cpuCacheMode=d.cpuCacheMode;hd.hazardTrackingMode=d.hazardTrackingMode;hd.maxCompatiblePlacementSparsePageSize=MTLSparsePageSize64;hd.size=b->capacity*65536;
        b->heap=[g_dev newHeapWithDescriptor:hd];if(!b->heap){pthread_mutex_unlock(&g_sparse_mu);return nil;}
        res_add(b->heap);[g_sparse_blocks addObject:b];page->block=b;
    }
found:
    page->block->used[page->index/64] |= 1ull<<(page->index%64);
    pthread_mutex_unlock(&g_sparse_mu);return page;
} }
@interface NvSparseHeap : NSObject { @public id<MTLHeap> heap; NSArray<NvSparsePage *> *pages; sparse_tile *tiles; size_t count; uint64_t stamp, gen, seen_gen, failure_gen; int gpu_storage; } @end
@implementation NvSparseHeap
- (void)dealloc { if(gpu_storage)atomic_fetch_sub(&g_sparse_gpu_n,1);free(tiles); }
@end
static char g_sparse_heap_owner_key;
static int g_native_sparse_on = -1;
static uint64_t g_sparse_uploads, g_sparse_backed, g_sparse_virtual, g_sparse_reused;
static int sparse_upload_lost(id<MTLTexture> mt){uint64_t gen=atomic_load(&g_sparse_failure_gen);if(!gen)return 0;NvSparseHeap *owner=objc_getAssociatedObject(mt,&g_sparse_heap_owner_key);return owner && !owner->gpu_storage && owner->failure_gen!=gen;}

// A partially mapped hardware tile can contain unmapped 4 KB pages. Preserve zero reads for those pages: zero compressed ASTC bytes would instead decode as magenta.
static void sparse_gather_tile(const tex_t *t, uint64_t off, uint8_t *out, size_t n) {
    uint64_t a = (uint64_t)(uintptr_t)t->mem + off;
    nvn_sparse_copy(t->pool, out, a, n);
    if (t->d.format < 0x79 || t->d.format > 0x94) return;
    static const uint8_t black[16] = {0xfc,0xfd,0xff,0xff,0xff,0xff,0xff,0xff,0,0,0,0,0,0,0,0};
    for (size_t p = 0; p < n; p += 4096) if (!nvn_sparse_mapped(t->pool, a + p, MIN(n - p, 4096u)))
        for (size_t b = p; b < MIN(p + 4096, n); b += 16) memcpy(out + b, black, 16);
}
static id<MTLTexture> sparse_upload(const tex_t *t, MTLTextureDescriptor *descriptor, uint64_t *stamp, id<MTLTexture> previous, int gpu_storage) {
    MTLTextureDescriptor *d=[descriptor copy];   // a rejected sparse layout must leave the caller's dense fallback descriptor unchanged
    // Unsupported devices and layouts keep the dense path. DM_NVN_NATIVE_SPARSE=0 allows a diagnostic comparison.
    if (g_native_sparse_on < 0) { const char *e = getenv("DM_NVN_NATIVE_SPARSE"); g_native_sparse_on = !e || atoi(e); }
    if (!g_native_sparse_on || !g_dev.supportsPlacementSparse || !t->pool || !nvn_sparse_pool(t->pool) || !(t->d.flags & NVN_TEXTURE_FLAGS_SPARSE) ||
        (t->d.target != NVN_TEXTURE_TARGET_2D && t->d.target != NVN_TEXTURE_TARGET_2D_ARRAY) ||
        (!gpu_storage && (d.usage & ~MTLTextureUsageShaderRead)) || (gpu_storage && (fmt_compressed(t->d.format) || !(t->pool->flags & NVN_MEMORY_POOL_FLAGS_CPU_NO_ACCESS))) || d.sampleCount > 1 || d.mipmapLevelCount != t->d.levels) return nil;
    if(gpu_storage) {
        if(fmt_depth(t->d.format) || storage_format(t->d.format)!=t->d.format)return nil;
        // Metal changes physical tile layout with image-write usage. Every GPU-only alias must have one layout from its first allocation, including a later RegisterImage.
        d.usage |= MTLTextureUsageShaderWrite | MTLTextureUsagePixelFormatView | (pf_r32i(d.pixelFormat)?MTLTextureUsageShaderAtomic:0);
    }
    // Diagnostic isolation of a format's sparse path; zero keeps every eligible format.
    static int format = -1; if (format < 0) { const char *e = getenv("DM_NVN_SPARSE_FORMAT"); format = e ? (int)strtol(e, NULL, 0) : 0; }
    if (format && t->d.format != format) return nil;
    int bw, bh, bpb = nvn_fmt_bpb(t->d.format,&bw,&bh);
    uint32_t tw, th, td; unsigned tail = (unsigned)nvn_tex_sparse_tiles(&t->d,&tw,&th,&td);
    if (!bpb || !tail || td != 1 || t->L.layer_size < 65536) return nil;
    MTLSize tile = [g_dev sparseTileSizeWithTextureType:d.textureType pixelFormat:d.pixelFormat sampleCount:1 sparsePageSize:MTLSparsePageSize64];
    if (tile.width != tw || tile.height != th || tile.depth != 1) return nil;
    uint64_t tail_off = nvn_tex_level_offset(&t->d,tail);
    if (tail < d.mipmapLevelCount && t->L.layer_size - tail_off > 65536) return nil;
    static int profile=-1;if(profile<0){const char *e=getenv("DM_NVN_SPARSE_TIMING");profile=e && atoi(e);}
    uint64_t started=profile?bp_now():0,gather_ns=0,linear_ns=0;
    if (stamp && !gpu_storage) { *stamp = nvn_dirty_now(); nvn_sparse_protect(t->pool,(uint64_t)(uintptr_t)t->mem,t->L.size); }
    sparse_tile *tiles = NULL; size_t count = 0, cap = 0;
    for (unsigned layer = 0; layer < t->L.layers; layer++) for (unsigned level = 0; level < MIN(tail + 1,d.mipmapLevelCount); level++) {
        uint32_t w = MAX(t->d.width >> level,1u), h = MAX(t->d.height >> level,1u);
        unsigned nx = level == tail ? 1 : (w + tw - 1)/tw, ny = level == tail ? 1 : (h + th - 1)/th;
        uint64_t base = layer*t->L.layer_size + nvn_tex_level_offset(&t->d,level);
        for (unsigned y = 0; y < ny; y++) for (unsigned x = 0; x < nx; x++) {
            uint64_t off = base + ((uint64_t)y*nx + x)*65536;
            uint64_t mapped=nvn_sparse_mapped_bytes(t->pool,(uint64_t)(uintptr_t)t->mem+off,65536);
            if (!mapped) continue;
            if (gpu_storage && mapped!=65536) { free(tiles); return nil; }   // partial hardware tiles retain the dense compatibility path
            if (count == cap) { cap = cap ? cap*2 : 256; sparse_tile *p = realloc(tiles,cap*sizeof *p); if (!p) { free(tiles); return nil; } tiles = p; }
            tiles[count++] = (sparse_tile){off,x,y,level,layer};
        }
    }
    uint64_t scanned=profile?bp_now():0;
    NvSparseHeap *old=previous ? objc_getAssociatedObject(previous,&g_sparse_heap_owner_key) : nil;
    if(old && (previous.pixelFormat!=d.pixelFormat || previous.width!=d.width || previous.height!=d.height || previous.arrayLength!=d.arrayLength || previous.mipmapLevelCount!=d.mipmapLevelCount))old=nil;
    uint64_t failure_gen=atomic_load(&g_sparse_failure_gen);if(old && !gpu_storage && old->failure_gen!=failure_gen)old=nil;
    NvSparseHeap *owner=[NvSparseHeap new]; owner->stamp=stamp ? *stamp : nvn_dirty_now();owner->gen=owner->seen_gen=nvn_sparse_gen();owner->failure_gen=failure_gen;owner->gpu_storage=gpu_storage;if(gpu_storage)atomic_fetch_add(&g_sparse_gpu_n,1);
    NSMutableArray<NvSparsePage *> *pages=[NSMutableArray arrayWithCapacity:count]; size_t changed=0,oi=0;
    uint8_t *upload=calloc(MAX(count,1u),1);
    id<MTLHeap> heap=nil; id<MTLTexture> mt=nil;
    d.placementSparsePageSize=MTLSparsePageSize64;mt=[g_dev newTextureWithDescriptor:d];
    if (!mt || !mt.isSparse || (tail < d.mipmapLevelCount ? mt.firstMipmapInTail != tail || mt.tailSizeInBytes != 65536 : mt.firstMipmapInTail < d.mipmapLevelCount)) { free(tiles);free(upload); return nil; }
    for(size_t i=0;i<count;i++) {
        while(old && oi<old->count && old->tiles[oi].off<tiles[i].off)oi++;
        NvSparsePage *page=nil; NSData *physical_key=nil;
        if (gpu_storage) {
            uint64_t key[35]={storage_format(t->d.format),0,0};
            if(tiles[i].level==tail){key[1]=(uint64_t)MAX(t->d.width>>tail,1u)|((uint64_t)MAX(t->d.height>>tail,1u)<<32);key[2]=d.mipmapLevelCount-tail;}
            if(!nvn_sparse_tile_identity(t->pool,(uint64_t)(uintptr_t)t->mem+tiles[i].off,key+3)){free(tiles);free(upload);return nil;}
            physical_key=[NSData dataWithBytes:key length:sizeof key];
            pthread_mutex_lock(&g_sparse_mu);
            if(!g_sparse_physical)g_sparse_physical=[NSMapTable strongToWeakObjectsMapTable];
            page=[g_sparse_physical objectForKey:physical_key];pthread_mutex_unlock(&g_sparse_mu);
        }
        if(!page && old && oi<old->count && old->tiles[oi].off==tiles[i].off &&
            !(gpu_storage ? nvn_sparse_mapping_since(t->pool,(uint64_t)(uintptr_t)t->mem+tiles[i].off,65536,old->gen) : nvn_sparse_since(t->pool,(uint64_t)(uintptr_t)t->mem+tiles[i].off,65536,old->gen,old->stamp)))page=old->pages[oi];
        if(!page){page=sparse_page(d,count-i);upload[i]=1;changed++;}else g_sparse_reused++;
        if(page && physical_key){pthread_mutex_lock(&g_sparse_mu);[g_sparse_physical setObject:page forKey:physical_key];pthread_mutex_unlock(&g_sparse_mu);}
        if(!page){free(tiles);free(upload);return nil;}[pages addObject:page];
    }
    owner->pages=pages;heap=pages.count ? pages[0]->block->heap : nil;owner->heap=heap;
    uint64_t paged=profile?bp_now():0;
    static int async_on=-1;if(async_on<0){const char *e=getenv("DM_NVN_SPARSE_ASYNC");async_on=e && atoi(e);}   // opt-in until end-to-end frame pacing improves as well
    int async=async_on && !gpu_storage && on_sub_thread();size_t staging_bytes=MAX(changed,1u)*65536;
    if(async)sparse_transfer_begin(staging_bytes);
    id<MTLBuffer> staging = [g_dev newBufferWithLength:staging_bytes options:MTLResourceStorageModeShared];
    uint8_t *source = malloc(65536);
    if (!staging || !source) { if(async)sparse_transfer_end(staging_bytes);free(tiles); free(upload); free(source); return nil; }
    id<MTLCommandBuffer> cb = q_cb();
    uint64_t queued=profile?bp_now():0;
    id<MTLSharedEvent> event = [g_dev newSharedEvent];
    {
        res_commit();
        MTL4UpdateSparseTextureMappingOperation *ops=calloc(MAX(count,1u),sizeof *ops);
        // Build each heap's operations once. Rescanning every tile for every heap made mapping work grow with tiles * heaps.
        typedef struct { __unsafe_unretained NvSparseBlock *block; size_t count,first,used; } mapping_batch;
        mapping_batch *batches=calloc(MAX(count,1u),sizeof *batches);size_t nbatches=0;
        nvn_hmap by_block={.klen=sizeof(uintptr_t)};
        for(NvSparsePage *page in pages){uintptr_t key=(uintptr_t)(__bridge void *)page->block;mapping_batch *batch=nvn_hm_get(&by_block,&key);
            if(!batch){batch=&batches[nbatches++];batch->block=page->block;nvn_hm_put(&by_block,&key,batch);}batch->count++;
        }
        for(size_t i=1;i<nbatches;i++)batches[i].first=batches[i-1].first+batches[i-1].count;
        for(size_t i=0;i<count;i++){NvSparsePage *page=pages[i];uintptr_t key=(uintptr_t)(__bridge void *)page->block;mapping_batch *batch=nvn_hm_get(&by_block,&key);
            const sparse_tile *p=&tiles[i];ops[batch->first+batch->used++]=(MTL4UpdateSparseTextureMappingOperation){MTLSparseTextureMappingModeMap,MTLRegionMake2D(p->x,p->y,1,1),p->level,p->layer,page->index};
        }
        pthread_mutex_lock(&g_res_mu);
        for(size_t i=0;i<nbatches;i++)[g_q4 updateTextureMappings:mt heap:batches[i].block->heap operations:ops+batches[i].first count:batches[i].count];
        [g_q4 signalEvent:event value:1];pthread_mutex_unlock(&g_res_mu);
        free(by_block.keys);free(by_block.vals);free(batches);free(ops);[cb encodeWaitForEvent:event value:1];
    }
    id<MTLBlitCommandEncoder> blit = [cb blitCommandEncoder];
    uint64_t mapped_at=profile?bp_now():0;
    uint64_t copied = 0; size_t uploaded=0;
    for (size_t i = 0; i < count; i++) {
        if(!upload[i])continue;
        const sparse_tile *p = &tiles[i]; size_t dst = uploaded++*65536;
        uint64_t gather_start=profile?bp_now():0;
        if(gpu_storage)memset(source,0,65536);else sparse_gather_tile(t,p->off,source,65536);
        if(profile)gather_ns+=bp_now()-gather_start;
        for (unsigned level = p->level; level < (p->level == tail ? d.mipmapLevelCount : p->level + 1); level++) {
            uint32_t w = MAX(t->d.width >> level,1u), h = MAX(t->d.height >> level,1u);
            unsigned sh, sd; nvn_tex_level_tiles(&t->d,level,&sh,&sd);
            nvn_texdesc local = t->d; local.target = NVN_TEXTURE_TARGET_2D; local.flags = 0; local.depth = local.levels = 1;
            local.width = level == tail || p->level == tail ? w : tw; local.height = p->level == tail ? h : th;
            local.pkg_block_h = (int)sh + 1;
            size_t pitch = (((size_t)(local.width+bw-1)/bw*bpb)+255)&~(size_t)255, rows = (local.height+bh-1)/bh;
            uint64_t so = p->level == tail ? nvn_tex_level_offset(&t->d,level)-tail_off : 0;
            uint64_t linear_start=profile?bp_now():0;
            if (pitch*rows > uploaded*65536-dst || nvn_deswizzle(&local,0,0,source+so,(uint8_t *)staging.contents+dst,pitch)) { [blit endEncoding];if(async)sparse_transfer_end(staging_bytes);free(tiles); free(upload); free(source); return nil; }
            if(profile)linear_ns+=bp_now()-linear_start;
            NSUInteger x = p->level == tail ? 0 : p->x*tw, y = p->level == tail ? 0 : p->y*th;
            [blit copyFromBuffer:staging sourceOffset:dst sourceBytesPerRow:pitch sourceBytesPerImage:pitch*rows sourceSize:MTLSizeMake(MIN(w-x,local.width),MIN(h-y,local.height),1)
                      toTexture:mt destinationSlice:p->layer destinationLevel:level destinationOrigin:MTLOriginMake(x,y,0)];
            dst += pitch*rows; copied += pitch*rows;
        }
    }
    [blit endEncoding];
    uint64_t encoded=profile?bp_now():0;
    [cb encodeSignalEvent:event value:2];
    owner->tiles=tiles;owner->count=count;
    objc_setAssociatedObject(mt,&g_sparse_heap_owner_key,owner,OBJC_ASSOCIATION_RETAIN_NONATOMIC);
    res_add(mt);
    if(async){
        static int lost_at=-1;static uint64_t batch_n;if(lost_at<0){const char *e=getenv("DM_TEST_SPARSE_LOST");lost_at=e?atoi(e):0;}
        int fake_lost=lost_at && ++batch_n==(uint64_t)lost_at;
        [cb addCompletedHandler:^(id<MTLCommandBuffer> done){@autoreleasepool{
            if(done.status!=MTLCommandBufferStatusCompleted || fake_lost){
                atomic_fetch_add(&g_sparse_failure_gen,1);
                // A failed command buffer may never reach its signal; unblock the consumer queue and rebuild read-only versions on their next use.
                if(event.signaledValue<2)event.signaledValue=2;
                pthread_mutex_lock(&g_smu);g_ser_gen++;pthread_mutex_unlock(&g_smu);
                MLOG("%ssparse upload dropped (%lu-wide texture, %zu tiles): read-only versions will be rebuilt%s%s",fake_lost?"DM_TEST_SPARSE_LOST: ":"[RED] ",(unsigned long)mt.width,owner->count,done.error?": ":"",done.error?done.error.localizedDescription.UTF8String:"");
            }
            // The command buffer retains its staging, texture metadata and physical pages until completion.
            sparse_transfer_end(staging_bytes);
        }}];
    }
    queue3_commit(cb);if(!async)[cb waitUntilCompleted];
    pthread_mutex_lock(&g_res_mu); [g_q4 waitForEvent:event value:2]; pthread_mutex_unlock(&g_res_mu);
    free(upload); free(source);
    if(!async && cb.status!=MTLCommandBufferStatusCompleted){res_remove(mt);MLOG("[RED] sparse upload failed ser=%llu: %s",t->serial,cb.error.localizedDescription.UTF8String);return nil;}
    g_bp_up_bytes += copied;
    if(profile && bp_now()-started>=5000000ull)MLOG("sparse upload timing ser=%llu fmt=%#x: %zu mapped / %zu changed tiles, %.1f MB; scan %.2f, pages %.2f, queue %.2f, map %.2f, fill %.2f (gather %.2f, linearize %.2f), completion %.2f ms",t->serial,t->d.format,count,changed,copied/1048576.0,(scanned-started)/1e6,(paged-scanned)/1e6,(queued-paged)/1e6,(mapped_at-queued)/1e6,(encoded-mapped_at)/1e6,gather_ns/1e6,linear_ns/1e6,(bp_now()-encoded)/1e6);
    g_sparse_uploads++; g_sparse_backed += changed*65536; g_sparse_virtual += t->L.size;
    if (g_sparse_uploads <= 8 || t->L.size >= (512ull<<20)) MLOG("native sparse texture ser=%llu: %zu tiles, %.1f MB backing for %.1f MB guest storage; %.1f MB uploaded",t->serial,count,count*65536/1048576.0,t->L.size/1048576.0,copied/1048576.0);
    return mt;
}

static id<MTLTexture> sparse_gpu_upgrade(const tex_t *t,id<MTLTexture> base,MTLTextureDescriptor *d) {
    NvSparseHeap *owner=objc_getAssociatedObject(base,&g_sparse_heap_owner_key);
    return owner && owner->gpu_storage ? sparse_upload(t,d,NULL,base,1) : nil;
}
static id<MTLTexture> sparse_gpu_refresh(const tex_t *t,id<MTLTexture> base) {
    NvSparseHeap *owner=objc_getAssociatedObject(base,&g_sparse_heap_owner_key); uint64_t gen=nvn_sparse_gen();
    if(!owner || !owner->gpu_storage || owner->seen_gen==gen)return base;
    owner->seen_gen=gen;
    if(!nvn_sparse_mapping_since(t->pool,(uint64_t)(uintptr_t)t->mem,t->L.size,owner->gen))return base;
    MTLTextureDescriptor *d=tex_desc(t,0);d.usage=base.usage | (tex_atomic_capable(base)?MTLTextureUsageShaderAtomic:0);
    id<MTLTexture> next=sparse_upload(t,d,NULL,base,1);
    if(!next){MLOG("sparse image mapping no longer matches hardware tiles ser=%llu: dense compatibility storage",t->serial);return tex_upgrade(t,base,0,base.pixelFormat);}
    tex_replace_shared(base,next);return next;
}
