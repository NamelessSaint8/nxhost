// Raw guest pointers use the translator's sorted pool table (dmsh_abi.h).
// Included by gfx_vk_core.c: allocations stay in submission scratch, and pool
// buffers retire through the existing deferred-free queue.
void vk_gmem_descriptor(int log, VkDescriptorBufferInfo *out) {
    if(!V.has_bda || !vkGetBufferDeviceAddress)die("[RED] raw global memory requires Vulkan buffer device addresses");
    vksub_t *s=cur();
    if(log){
        const size_t bytes=4*(1+(1u<<DMSH_GMEM_LOG_LOG2));
        uint32_t *words=vk_scratch(bytes,V.props.limits.minStorageBufferOffsetAlignment,&out->buffer,&out->offset);
        out->range=bytes;memset(words,0,bytes);
        if(s->ngmem_logs==s->capgmem_logs){
            unsigned capacity=s->capgmem_logs?s->capgmem_logs*2:8;
            const uint32_t **logs=realloc(s->gmem_logs,capacity*sizeof *logs);
            if(!logs)die("[RED] global-memory log registry allocation failed");
            s->gmem_logs=logs;s->capgmem_logs=capacity;
        }
        s->gmem_logs[s->ngmem_logs++]=words;
        return;
    }
    if(!s->gmem_valid || s->gmem_gen!=vk_pool_gen()){
        uint64_t (*table)[4]=vk_scratch(DMSH_GMEM_MAP_ENTRIES*DMSH_GMEM_MAP_ENTRY,
            V.props.limits.minStorageBufferOffsetAlignment,&s->gmem_map.buffer,&s->gmem_map.offset);
        s->gmem_map.range=DMSH_GMEM_MAP_ENTRIES*DMSH_GMEM_MAP_ENTRY;
        memset(table,0,(size_t)s->gmem_map.range);
        for(unsigned i=1;i<DMSH_GMEM_MAP_ENTRIES;i++)table[i][0]=UINT64_MAX;
        pthread_rwlock_wrlock(&g_pool_mu);
        // An indirect address can reach any GPU-accessible pool, including one
        // not bound directly yet. Physical backing is GPU-accessible here only
        // when it has a full linear virtual mapping.
        unsigned count=1;uint64_t end=0;s->gmem_coherent=1;
        for(int i=0;i<g_npool;i++){
            vkpool_t *p=g_pool[i];
            if (!pool_has_gpu_access(p)) continue;
            pool_use_locked(p);
            if(p->lo<end)die("[RED] overlapping GPU pools need alias resolution before raw global-memory access");
            uint64_t lo=p->lo;
            if(lo>=p->hi)continue;
            if(count==DMSH_GMEM_MAP_ENTRIES)die("[RED] raw global-memory pool table capacity exceeded");
            VkBufferDeviceAddressInfo info={VK_STRUCTURE_TYPE_BUFFER_DEVICE_ADDRESS_INFO,NULL,p->buf};
            uint64_t address=vkGetBufferDeviceAddress(V.dev,&info);
            if(!address)die("[RED] global-memory pool has no Vulkan device address");
            table[count][0]=lo;table[count][1]=p->hi;table[count][2]=address-p->lo;
            // finish still waits for every raw writer. It consumes logged
            // pages only for copied pools; coherent zero-copy stores need no
            // page publication. This immutable per-pool flag avoids millions
            // of redundant CAS probes without weakening copied-pool tracking.
            table[count++][3]=p->zero_copy?DMSH_GMEM_MAP_NO_WRITE_LOG:0;
            if(!p->zero_copy)s->gmem_coherent=0;
            end=p->hi;
        }
        s->gmem_gen=vk_pool_gen();s->gmem_valid=1;
        pthread_rwlock_unlock(&g_pool_mu);
        static int said;if(!said++)VKLOG("raw global memory: %u address ranges; indirect writes publish their logged pages before the next replay operation",count-1);
    }
    *out=s->gmem_map;
}

int vk_gmem_coherent(void) {
    if(g_cur<0)return 0;vksub_t *s=cur();
    return s->gmem_valid && s->gmem_gen==vk_pool_gen() && s->gmem_coherent;
}

void vk_gmem_finish(void) {
    if(g_cur<0 || !g_slot[g_cur].ngmem_logs)return;
    vksub_t *s=cur();
    // The destinations are GPU data. Until we have a proven dependency model,
    // resolve them before another replay operation can take a CPU shadow or
    // read a handle. This conservative path deliberately waits; no prediction
    // of future write pools is used. Timestamps still bracket the GPU shader.
    vk_end_pass_land();vk_cmd_sync_host();
    uint64_t pages=0,bytes=0;unsigned overflow=0;
    pthread_rwlock_rdlock(&g_pool_mu);
    for(unsigned j=0;j<s->ngmem_logs;j++){
        const uint32_t *words=s->gmem_logs[j];overflow+=words[0]!=0;
        for(int i=0;i<g_npool;i++){
            vkpool_t *p=g_pool[i];if(!p->shadow || !p->synced)continue;
            if(words[0]){
                // The hash set overflowed, so no precise page list is known.
                // Preserve writes by publishing every accessible copied pool.
                sub_gpu_wrote(p->lo,p->hi-p->lo);continue;
            }
            for(unsigned k=1;k<=1u<<DMSH_GMEM_LOG_LOG2;k++)if(words[k]){
                // The ABI logs the low 32 bits of address>>12. Reconstruct
                // each possible matching page in this pool, including hosts
                // whose pointers occupy more than 44 bits.
                const uint64_t period=1ull<<44;
                uint64_t a=(p->lo&~(period-1))|((uint64_t)words[k]<<12);
                if(a+4096<=p->lo)a+=period;
                for(;a<p->hi;a+=period){
                    uint64_t lo=a>p->lo?a:p->lo,hi=a+4096<p->hi?a+4096:p->hi;
                    sub_gpu_wrote(lo,hi-lo);
                }
            }
        }
        for(unsigned k=1;k<=1u<<DMSH_GMEM_LOG_LOG2;k++)pages+=words[k]!=0;
    }
    // Publish ordinary bound outputs as well: a CPU handle read after this
    // synchronization must see all completed writes, not just the indirect
    // destinations. Limit copies to recorded ranges, retaining unrelated CPU
    // bytes even in cached pools.
    for(int i=0;i<g_npool;i++){
        vkpool_t *p=g_pool[i];if(!p->shadow || !p->synced)continue;
        for(int k=0;k<s->ngw;k++){
            uint64_t lo=s->gw[k].lo>p->lo?s->gw[k].lo:p->lo,hi=s->gw[k].hi<p->hi?s->gw[k].hi:p->hi;
            if(lo<hi){memcpy((void *)(uintptr_t)lo,p->shadow+lo-p->lo,(size_t)(hi-lo));bytes+=hi-lo;}
        }
    }
    pthread_rwlock_unlock(&g_pool_mu);
    s->ngmem_logs=0;
    static uint64_t calls;if(++calls<=4 || !(calls%1024))VKLOG("raw global writes: %llu logged pages, %llu copied bytes, %u overflowing logs (conservative full copy-back)",
        (unsigned long long)pages,(unsigned long long)bytes,overflow);
}
