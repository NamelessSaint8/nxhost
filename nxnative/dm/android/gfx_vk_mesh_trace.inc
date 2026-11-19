// Opt-in provenance for the indirect argument diagnostic. Record the resolved
// guest ranges in replay order. Snapshot watched words around matching compute
// dispatches to distinguish a bound output from an actual GPU write.
enum {
    MESH_TRACE_HISTORY = 16384, MESH_TRACE_WATCHES = 8, MESH_TRACE_PEEKS = 12,
    MESH_TRACE_BINDINGS = 16, MESH_TRACE_RECORDS = MESH_TRACE_WATCHES + MESH_TRACE_BINDINGS
};
static struct {
    uint64_t frame, address, size, key;
    const char *op;
    unsigned binding, write;
} g_mesh_history[MESH_TRACE_HISTORY];
static uint64_t g_mesh_history_next;
static struct {
    uint64_t address;
    VkBuffer buffer;
    VkDeviceSize offset;
    unsigned bytes, binding;
} g_mesh_watch[MESH_TRACE_RECORDS];
static unsigned g_mesh_watch_count, g_mesh_dispatch_watch, g_mesh_peeks;
static unsigned g_mesh_bind_count, g_mesh_bind_peeks;

static int mesh_trace_covers(uint64_t base, uint64_t size, uint64_t address, unsigned bytes) {
    return size >= bytes && address >= base && address - base <= size - bytes;
}

static void mesh_trace_record(const char *op, uint64_t key, unsigned binding, unsigned write,
                              uint64_t address, uint64_t size) {
    if (!g_mesh_trace_writers || !address || !size) return;
    typeof(g_mesh_history[0]) *event = &g_mesh_history[g_mesh_history_next++ % MESH_TRACE_HISTORY];
    *event = (typeof(*event)){g_tex_frame, address, size, key, op, binding, write};
}

static void mesh_trace_binding(const vkshader_t *shader, const dmsv_bind *binding,
                               uint64_t address, uint64_t size, VkBuffer buffer, VkDeviceSize offset) {
    unsigned write = !!(binding->flags & 4);
    mesh_trace_record("compute binding", shader->key, binding->binding, write, address, size);
    if (g_mesh_trace_binding_key == shader->key && g_tex_frame >= g_mesh_trace_binding_start &&
        g_mesh_bind_peeks < MESH_TRACE_PEEKS && g_mesh_bind_count < MESH_TRACE_BINDINGS && size >= 16 && !(offset & 3)) {
        unsigned i = MESH_TRACE_WATCHES + g_mesh_bind_count++;
        g_mesh_watch[i] = (typeof(g_mesh_watch[0])){address, buffer, offset, 16, binding->binding};
        g_mesh_dispatch_watch |= 1u << i;
    }
    // Reflection can miss a write reached through an atomic. Keep the
    // observed access separate from the reflection flag in the history.
    if (g_mesh_peeks >= MESH_TRACE_PEEKS) return;
    for (unsigned i = 0; i < g_mesh_watch_count; i++) {
        uint64_t target = g_mesh_watch[i].address;
        if (!mesh_trace_covers(address, size, target, g_mesh_watch[i].bytes)) continue;
        g_mesh_watch[i].buffer = buffer;
        g_mesh_watch[i].offset = offset + target - address;
        g_mesh_dispatch_watch |= 1u << i;
    }
}

static void mesh_trace_find_writers(uint64_t address, unsigned bytes) {
    if (!g_mesh_trace_writers) return;
    uint64_t oldest = g_mesh_history_next > MESH_TRACE_HISTORY ? g_mesh_history_next - MESH_TRACE_HISTORY : 0;
    unsigned matches = 0;
    for (uint64_t i = g_mesh_history_next; i > oldest && matches < 12; i--) {
        const typeof(g_mesh_history[0]) *event = &g_mesh_history[(i - 1) % MESH_TRACE_HISTORY];
        if (g_tex_frame - event->frame > 2) break;
        if (event->address <= address ? address - event->address >= event->size
                                      : event->address - address >= bytes) continue;
        VKLOG("indirect mesh writer history: address %#llx, present %llu, %s shader %016llx binding %u rw %u range %#llx+%#llx",
            (unsigned long long)address, (unsigned long long)event->frame, event->op,
            (unsigned long long)event->key, event->binding, event->write,
            (unsigned long long)event->address, (unsigned long long)event->size);
        matches++;
    }
    VKLOG("indirect mesh writer history: address %#llx, %u matching ranges", (unsigned long long)address, matches);
    for (unsigned i = 0; i < g_mesh_watch_count; i++)
        if (g_mesh_watch[i].address == address && g_mesh_watch[i].bytes == bytes) return;
    if (g_mesh_watch_count < MESH_TRACE_WATCHES) {
        g_mesh_watch[g_mesh_watch_count].address = address;
        g_mesh_watch[g_mesh_watch_count++].bytes = bytes;
    }
}

static void mesh_trace_copy(VkCommandBuffer cb, const uint32_t *out[MESH_TRACE_RECORDS]) {
    for (unsigned i = 0; i < MESH_TRACE_WATCHES + g_mesh_bind_count; i++) {
        if (!(g_mesh_dispatch_watch & (1u << i))) continue;
        VkBuffer staging;
        VkDeviceSize to;
        unsigned bytes = g_mesh_watch[i].bytes;
        out[i] = vk_scratch(bytes, 4, &staging, &to);
        VkBufferCopy copy = {g_mesh_watch[i].offset, to, bytes};
        vkCmdCopyBuffer(cb, g_mesh_watch[i].buffer, staging, 1, &copy);
    }
    vk_img_barrier_all(cb);
}

static void mesh_trace_raw_bindings(void) {
    if (g_mesh_peeks >= MESH_TRACE_PEEKS) return;
    for (unsigned i = 0; i < g_mesh_watch_count; i++) {
        typeof(g_mesh_watch[0]) *watch = &g_mesh_watch[i];
        if (vk_buf_at(watch->address, watch->bytes, &watch->buffer, &watch->offset))
            g_mesh_dispatch_watch |= 1u << i;
    }
}

static const uint32_t *mesh_trace_group_copy(VkCommandBuffer cb, uint64_t address) {
    VkBuffer source, staging;
    VkDeviceSize from, to;
    if (!address || (address & 3) || !vk_buf_at(address, 12, &source, &from)) return NULL;
    mesh_trace_find_writers(address, 12);
    const uint32_t *words = vk_scratch(12, 4, &staging, &to);
    VkBufferCopy copy = {from, to, 12};
    vkCmdCopyBuffer(cb, source, staging, 1, &copy);
    vk_img_barrier_all(cb);
    return words;
}

static void mesh_trace_dispatch_end(VkCommandBuffer cb, const vkshader_t *shader,
                                    const uint32_t *before[MESH_TRACE_RECORDS], const uint32_t *groups) {
    const uint32_t *after[MESH_TRACE_RECORDS] = {0};
    mesh_trace_copy(cb, after);
    vk_cmd_sync_host();
    for (unsigned i = 0; i < MESH_TRACE_WATCHES + g_mesh_bind_count; i++) {
        if (!after[i]) continue;
        const uint32_t *a = before[i], *b = after[i];
        unsigned bytes = g_mesh_watch[i].bytes;
        char binding[32] = "";
        if (i >= MESH_TRACE_WATCHES) snprintf(binding, sizeof binding, " binding %u", g_mesh_watch[i].binding);
        VKLOG("indirect mesh writer snapshot: present %llu shader %016llx groups %ux%ux%u indirect %#llx address %#llx bytes %u%s before %08x %08x %08x %08x after %08x %08x %08x %08x",
            (unsigned long long)g_tex_frame, (unsigned long long)shader->key,
            groups ? groups[0] : g_dispatch[0], groups ? groups[1] : g_dispatch[1], groups ? groups[2] : g_dispatch[2],
            (unsigned long long)g_dispatch_ind,
            (unsigned long long)g_mesh_watch[i].address, bytes, binding,
            a[0], a[1], a[2], bytes == 16 ? a[3] : 0, b[0], b[1], b[2], bytes == 16 ? b[3] : 0);
    }
    if (g_mesh_dispatch_watch & ((1u << MESH_TRACE_WATCHES) - 1)) g_mesh_peeks++;
    if (g_mesh_bind_count) g_mesh_bind_peeks++;
}
