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
@interface NvSparsePage : NSObject { @public NvSparseBlock *block; unsigned index; uint64_t ro_ticket, ro_failure; int ro_ready; } @end
@implementation NvSparsePage
- (void)dealloc { if (block) { pthread_mutex_lock(&g_sparse_mu); block->used[index/64] &= ~(1ull << (index%64)); pthread_mutex_unlock(&g_sparse_mu); } }
@end
static NSHashTable<NvSparseBlock *> *g_sparse_blocks;
static NSMapTable<NSData *,NvSparsePage *> *g_sparse_physical;
static NSMapTable<NSData *,NvSparsePage *> *g_sparse_readonly;
static uint64_t g_sparse_ro_shared, g_sparse_ro_ticket;
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
static int sparse_gpu_owned(id<MTLTexture> mt) { NvSparseHeap *owner=objc_getAssociatedObject(mt,&g_sparse_heap_owner_key);return owner && owner->gpu_storage; }
static int g_native_sparse_on = -1;
static uint64_t g_sparse_uploads, g_sparse_backed, g_sparse_virtual, g_sparse_reused, g_sparse_unchanged, g_sparse_mapping_only;
static int sparse_upload_lost(id<MTLTexture> mt){uint64_t gen=atomic_load(&g_sparse_failure_gen);if(!gen)return 0;NvSparseHeap *owner=objc_getAssociatedObject(mt,&g_sparse_heap_owner_key);return owner && !owner->gpu_storage && owner->failure_gen!=gen;}
static void sparse_readonly_ready(NvSparseHeap *owner) {
    pthread_mutex_lock(&g_sparse_mu);
    for (NvSparsePage *page in owner->pages) page->ro_ready = 1;
    pthread_mutex_unlock(&g_sparse_mu);
}
// Immutable content sharing includes the decode layout and exact bytes staged for this upload.
// Physical addresses alone miss repeated tile contents in distinct source allocations.
static NSData *sparse_readonly_key(const tex_t *t, MTLTextureDescriptor *d, const sparse_tile *p, unsigned tail, uint32_t tw, uint32_t th, const uint8_t source[65536]) {
    uint64_t key[25] = {d.pixelFormat, 0, 0, 0, (uint64_t)nvn_gob_switch2};size_t nkey=9;
    uint32_t w=MAX(t->d.width>>p->level,1u), h=MAX(t->d.height>>p->level,1u);
    unsigned sh,sd; nvn_tex_level_tiles(&t->d,p->level,&sh,&sd);
    key[1]=(uint64_t)(p->level==tail?w:MIN(tw,w-p->x*tw)) | ((uint64_t)(p->level==tail?h:MIN(th,h-p->y*th))<<32);
    key[2]=p->level==tail ? (1ull<<63)|(d.mipmapLevelCount-tail) : 0;
    key[3]=(uint64_t)sh|((uint64_t)sd<<32);
    CC_SHA256(source,65536,(uint8_t *)(key+5));
    if(p->level==tail){
        if(d.mipmapLevelCount-tail>16)return nil;
        uint64_t base=nvn_tex_level_offset(&t->d,tail);
        for(unsigned level=tail;level<d.mipmapLevelCount;level++)key[nkey++]=nvn_tex_level_offset(&t->d,level)-base;
    }
    return [NSData dataWithBytes:key length:nkey*sizeof *key];
}

// A partially mapped hardware tile can contain unmapped 4 KB pages. Preserve zero reads for those pages: zero compressed ASTC bytes would instead decode as magenta.
static void sparse_gather_tile(const tex_t *t, uint64_t off, uint8_t *out, size_t n) {
    uint64_t a = (uint64_t)(uintptr_t)t->mem + off;
    nvn_sparse_copy(t->pool, out, a, n);
    if (t->d.format < 0x79 || t->d.format > 0x94) return;
    static const uint8_t black[16] = {0xfc,0xfd,0xff,0xff,0xff,0xff,0xff,0xff,0,0,0,0,0,0,0,0};
    for (size_t p = 0; p < n; p += 4096) if (!nvn_sparse_mapped(t->pool, a + p, MIN(n - p, 4096u)))
        for (size_t b = p; b < MIN(p + 4096, n); b += 16) memcpy(out + b, black, 16);
}
// Fill one staging slot from the same snapshot that was hashed; reading guest bytes again after
// publishing a content key could associate that key with different data during a concurrent CPU write.
static int sparse_stage_tile(const tex_t *t, MTLTextureDescriptor *d, const sparse_tile *p, unsigned tail, uint64_t tail_off, uint32_t tw, uint32_t th, const uint8_t *source, uint8_t *dest) {
    int bw,bh,bpb=nvn_fmt_bpb(t->d.format,&bw,&bh);size_t pos=0;
    for(unsigned level=p->level;level<(p->level==tail?d.mipmapLevelCount:p->level+1);level++) {
        uint32_t w=MAX(t->d.width>>level,1u),h=MAX(t->d.height>>level,1u);unsigned sh,sd;nvn_tex_level_tiles(&t->d,level,&sh,&sd);
        nvn_texdesc local=t->d;local.target=NVN_TEXTURE_TARGET_2D;local.flags=0;local.depth=local.levels=1;
        local.width=p->level==tail?w:tw;local.height=p->level==tail?h:th;local.pkg_block_h=(int)sh+1;
        size_t pitch=(((size_t)(local.width+bw-1)/bw*bpb)+255)&~(size_t)255,rows=(local.height+bh-1)/bh;
        uint64_t so=p->level==tail?nvn_tex_level_offset(&t->d,level)-tail_off:0;
        if(pos+pitch*rows>65536 || nvn_deswizzle(&local,0,0,source+so,dest+pos,pitch))return -1;
        pos+=pitch*rows;
    }
    return 0;
}
static id<MTLTexture> sparse_upload(const tex_t *t, MTLTextureDescriptor *descriptor, uint64_t *stamp, id<MTLTexture> previous, int gpu_storage) {
    MTLTextureDescriptor *d=[descriptor copy];   // a rejected sparse layout must leave the caller's dense fallback descriptor unchanged
    static int ro_share=-1;if(ro_share<0){const char *e=getenv("DM_NVN_SPARSE_RO_SHARE");ro_share=e && atoi(e);}   // opt-in while measuring identical immutable tile contents
    int share_readonly=ro_share && !gpu_storage && stamp;
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
    static int async_on=-1;if(async_on<0){const char *e=getenv("DM_NVN_SPARSE_ASYNC");async_on=e && atoi(e);}
    int async=async_on && !gpu_storage && on_sub_thread();size_t staging_bytes=0;
    id<MTLBuffer> staging=nil;uint8_t *source=NULL;
    if(share_readonly) {
        size_t candidates=0;
        for(size_t i=0;i<count;i++) {
            while(old && oi<old->count && old->tiles[oi].off<tiles[i].off)oi++;
            NvSparsePage *page=nil;
            if(old && oi<old->count && old->tiles[oi].off==tiles[i].off && !nvn_sparse_since(t->pool,(uint64_t)(uintptr_t)t->mem+tiles[i].off,65536,old->gen,old->stamp))page=old->pages[oi];
            [pages addObject:page ?: (id)NSNull.null];if(!page)candidates++;
        }
        // Reserve the worst case before staging allocation; duplicate contents touch fewer slots.
        staging_bytes=MAX(candidates,1u)*65536;if(async)sparse_transfer_begin(staging_bytes);
        staging=[g_dev newBufferWithLength:staging_bytes options:MTLResourceStorageModeShared];source=malloc(65536);
        if(!staging || !source){if(async)sparse_transfer_end(staging_bytes);free(tiles);free(upload);free(source);return nil;}
        uint64_t ticket=++g_sparse_ro_ticket;size_t packed=0;
        for(size_t i=0;i<count;i++) {
            if((id)pages[i]!=NSNull.null){g_sparse_reused++;continue;}
            uint64_t started_gather=profile?bp_now():0;sparse_gather_tile(t,tiles[i].off,source,65536);if(profile)gather_ns+=bp_now()-started_gather;
            NSData *key=sparse_readonly_key(t,d,&tiles[i],tail,tw,th,source);
            pthread_mutex_lock(&g_sparse_mu);NvSparsePage *page=key?[g_sparse_readonly objectForKey:key]:nil;
            if(page && (page->ro_failure!=failure_gen || (!page->ro_ready && page->ro_ticket!=ticket)))page=nil;
            pthread_mutex_unlock(&g_sparse_mu);
            if(page){g_sparse_ro_shared++;g_sparse_reused++;}
            else {
                page=sparse_page(d,count-i);
                uint64_t linear_start=profile?bp_now():0;
                if(!page || sparse_stage_tile(t,d,&tiles[i],tail,tail_off,tw,th,source,(uint8_t *)staging.contents+packed*65536)){
                    if(async)sparse_transfer_end(staging_bytes);free(tiles);free(upload);free(source);return nil;
                }
                if(profile)linear_ns+=bp_now()-linear_start;
                page->ro_ticket=ticket;page->ro_failure=failure_gen;upload[i]=1;changed++;packed++;
                if(key){pthread_mutex_lock(&g_sparse_mu);if(!g_sparse_readonly)g_sparse_readonly=[NSMapTable strongToWeakObjectsMapTable];[g_sparse_readonly setObject:page forKey:key];pthread_mutex_unlock(&g_sparse_mu);}
            }
            pages[i]=page;
        }
    } else {
        for(size_t i=0;i<count;i++) {
            while(old && oi<old->count && old->tiles[oi].off<tiles[i].off)oi++;
            NvSparsePage *page=nil; NSData *physical_key=nil;
            // Keep the original version-reuse and mutable physical-alias paths unchanged.
            if(!gpu_storage && old && oi<old->count && old->tiles[oi].off==tiles[i].off &&
                !nvn_sparse_since(t->pool,(uint64_t)(uintptr_t)t->mem+tiles[i].off,65536,old->gen,old->stamp))page=old->pages[oi];
            if (gpu_storage) {
                uint64_t key[35]={storage_format(t->d.format),0,0};
                if(tiles[i].level==tail){key[1]=(uint64_t)MAX(t->d.width>>tail,1u)|((uint64_t)MAX(t->d.height>>tail,1u)<<32);key[2]=d.mipmapLevelCount-tail;}
                if(!nvn_sparse_tile_identity(t->pool,(uint64_t)(uintptr_t)t->mem+tiles[i].off,key+3)){free(tiles);free(upload);return nil;}
                physical_key=[NSData dataWithBytes:key length:sizeof key];
                pthread_mutex_lock(&g_sparse_mu);
                if(!g_sparse_physical)g_sparse_physical=[NSMapTable strongToWeakObjectsMapTable];
                page=[g_sparse_physical objectForKey:physical_key];pthread_mutex_unlock(&g_sparse_mu);
            }
            if(gpu_storage && !page && old && oi<old->count && old->tiles[oi].off==tiles[i].off &&
                !nvn_sparse_mapping_since(t->pool,(uint64_t)(uintptr_t)t->mem+tiles[i].off,65536,old->gen))page=old->pages[oi];
            if(!page){page=sparse_page(d,count-i);upload[i]=1;changed++;}else g_sparse_reused++;
            if(page && physical_key){pthread_mutex_lock(&g_sparse_mu);[g_sparse_physical setObject:page forKey:physical_key];pthread_mutex_unlock(&g_sparse_mu);}
            if(!page){free(tiles);free(upload);return nil;}[pages addObject:page];
        }
    }
    // CPU writes/remaps can resolve to the same immutable contents. If every tile
    // still names the same physical page, no GPU mapping or upload changed. Keep
    // the current metadata and its already-queued completion dependency. Zero
    // uploaded bytes alone is insufficient: a different mapping may reuse pages
    // from the content cache. Mutable GPU storage always keeps versioning.
    if(old && !gpu_storage && !changed && old->count==count && previous.textureType==mt.textureType && previous.usage==mt.usage) {
        int same=1;
        for(size_t i=0;i<count && same;i++) {
            const sparse_tile *a=&old->tiles[i],*b=&tiles[i];
            same=old->pages[i]==pages[i] && a->off==b->off && a->x==b->x && a->y==b->y && a->level==b->level && a->layer==b->layer;
        }
        if(same) {
            old->stamp=owner->stamp;old->gen=owner->gen;old->seen_gen=owner->seen_gen;
            if(share_readonly && async)sparse_transfer_end(staging_bytes);
            free(tiles);free(upload);free(source);g_sparse_unchanged++;
            if(profile && bp_now()-started>=5000000ull)MLOG("unchanged sparse refresh ser=%llu: %zu tiles keep their metadata and physical pages, %.2f ms (%llu total)",t->serial,count,(bp_now()-started)/1e6,g_sparse_unchanged);
            return previous;
        }
    }
    owner->pages=pages;heap=pages.count ? pages[0]->block->heap : nil;owner->heap=heap;
    uint64_t paged=profile?bp_now():0;
    int mapping_only=!gpu_storage && !changed;
    if(!share_readonly && !mapping_only) {
        staging_bytes=MAX(changed,1u)*65536;if(async)sparse_transfer_begin(staging_bytes);
        staging=[g_dev newBufferWithLength:staging_bytes options:MTLResourceStorageModeShared];source=malloc(65536);
        if(!staging || !source){if(async)sparse_transfer_end(staging_bytes);free(tiles);free(upload);free(source);return nil;}
    }
    id<MTLCommandBuffer> cb = mapping_only ? nil : q_cb();
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
        [g_q4 signalEvent:event value:1];
        if(mapping_only)[g_q4 waitForEvent:event value:1];   // mapping completion orders subsequent GPU work, without a CPU/classic-queue round trip
        pthread_mutex_unlock(&g_res_mu);
        free(by_block.keys);free(by_block.vals);free(batches);free(ops);if(cb)[cb encodeWaitForEvent:event value:1];
    }
    if(mapping_only) {
        // Every page is already uploaded, or belongs to this texture's pending
        // version whose event wait is already on g_q4. Only the mappings change;
        // an empty classic upload submission would add a CPU completion wait.
        owner->tiles=tiles;owner->count=count;
        objc_setAssociatedObject(mt,&g_sparse_heap_owner_key,owner,OBJC_ASSOCIATION_RETAIN_NONATOMIC);res_add(mt);
        if(share_readonly && async)sparse_transfer_end(staging_bytes);
        free(upload);free(source);g_sparse_mapping_only++;g_sparse_uploads++;g_sparse_virtual+=t->L.size;
        if(profile && bp_now()-started>=5000000ull)MLOG("sparse mapping-only refresh ser=%llu: %zu tiles, scan %.2f, pages %.2f, map %.2f ms; no upload submission or CPU completion wait (%llu total)",t->serial,count,(scanned-started)/1e6,(paged-scanned)/1e6,(bp_now()-paged)/1e6,g_sparse_mapping_only);
        return mt;
    }
    id<MTLBlitCommandEncoder> blit = [cb blitCommandEncoder];
    uint64_t mapped_at=profile?bp_now():0;
    uint64_t copied = 0; size_t uploaded=0;
    for (size_t i = 0; i < count; i++) {
        if(!upload[i])continue;
        const sparse_tile *p = &tiles[i]; size_t dst = uploaded++*65536;
        uint64_t gather_start=profile?bp_now():0;
        if(!share_readonly)sparse_gather_tile(t,p->off,source,65536);   // new GPU pages inherit physical initial bytes; existing pages retain GPU writes
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
            if (pitch*rows > uploaded*65536-dst || (!share_readonly && nvn_deswizzle(&local,0,0,source+so,(uint8_t *)staging.contents+dst,pitch))) { [blit endEncoding];if(async)sparse_transfer_end(staging_bytes);free(tiles); free(upload); free(source); return nil; }
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
            } else if(share_readonly)sparse_readonly_ready(owner);
            // The command buffer retains its staging, texture metadata and physical pages until completion.
            sparse_transfer_end(staging_bytes);
        }}];
    }
    queue3_commit(cb);if(!async)[cb waitUntilCompleted];
    pthread_mutex_lock(&g_res_mu); [g_q4 waitForEvent:event value:2]; pthread_mutex_unlock(&g_res_mu);
    free(upload); free(source);
    if(!async && cb.status!=MTLCommandBufferStatusCompleted){res_remove(mt);MLOG("[RED] sparse upload failed ser=%llu: %s",t->serial,cb.error.localizedDescription.UTF8String);return nil;}
    if(!async && share_readonly)sparse_readonly_ready(owner);
    g_bp_up_bytes += copied;
    if(profile && bp_now()-started>=5000000ull)MLOG("sparse upload timing ser=%llu fmt=%#x: %zu mapped / %zu changed tiles, %.1f MB; scan %.2f, pages %.2f, queue %.2f, map %.2f, fill %.2f (gather %.2f, linearize %.2f), completion %.2f ms",t->serial,t->d.format,count,changed,copied/1048576.0,(scanned-started)/1e6,(paged-scanned)/1e6,(queued-paged)/1e6,(mapped_at-queued)/1e6,(encoded-mapped_at)/1e6,gather_ns/1e6,linear_ns/1e6,(bp_now()-encoded)/1e6);
    g_sparse_uploads++; g_sparse_backed += changed*65536; g_sparse_virtual += t->L.size;
    if (g_sparse_uploads <= 8 || t->L.size >= (512ull<<20)) MLOG("native sparse texture ser=%llu: %zu tiles, %.1f MB mapped coverage for %.1f MB guest storage; %.1f MB uploaded; content-shared tiles %llu",t->serial,count,count*65536/1048576.0,t->L.size/1048576.0,copied/1048576.0,g_sparse_ro_shared);
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
