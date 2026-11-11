// Opt-in presentation experiment. Only the Android swapchain changes size;
// guest targets, viewports and texture data keep their original dimensions.
// Android WSI scales a smaller swapchain to the same physical window.
static unsigned g_present_divisor = 1;
static uint32_t g_source_size[4];   // presented texture and active crop
static int present_size_poll(void) {
    static int initialized; static const char *control; static uint64_t next;
    unsigned divisor = g_present_divisor;
    if (!initialized) {
        initialized = 1; control = getenv("DM_VK_PRESENT_CONTROL");
        const char *e = getenv("DM_VK_PRESENT_DIVISOR");
        if (e) { int n = atoi(e); if (n >= 1 && n <= 4) divisor = (unsigned)n;
            else VKLOG("[RED] presentation divisor must be 1..4; keeping native size"); }
    }
    if (control && *control) {
        struct timespec ts; clock_gettime(CLOCK_MONOTONIC, &ts);
        uint64_t now = (uint64_t)ts.tv_sec * 1000000000ull + (uint64_t)ts.tv_nsec;
        if (now >= next) {
            next = now + 1000000000ull;
            FILE *f = fopen(control, "r");
            if (f) { unsigned n; char extra; int fields = fscanf(f, "%u %c", &n, &extra); fclose(f);
                if (fields == 1 && n >= 1 && n <= 4) divisor = n; }
        }
    }
    if (divisor == g_present_divisor) return 0;
    g_present_divisor = divisor;
    VKLOG("presentation divisor %u: guest render targets unchanged", divisor);
    return 1;
}

// These timestamps bracket the fully recorded presentation command buffer,
// excluding guest replay/recording and compositor work after queue present.
// Each result is read only after its existing present-slot fence completes.
static VkQueryPool g_present_queries;
static uint64_t g_present_tick_mask;
typedef struct { uint64_t ticket; double time; uint32_t size[6]; int pending; } present_sample;
static present_sample g_present_samples[8];
static FILE *g_present_times_file;
static void present_times_init(void) {
    static int initialized; if (initialized) return; initialized = 1;
    const char *e = getenv("DM_VK_PRESENT_TIMES"); if (!e || !atoi(e)) return;
    uint32_t n = 0; vkGetPhysicalDeviceQueueFamilyProperties(V.pd, &n, NULL);
    VkQueueFamilyProperties *q = calloc(n, sizeof *q); if (!q) return;
    vkGetPhysicalDeviceQueueFamilyProperties(V.pd, &n, q);
    uint32_t bits = V.qf < n ? q[V.qf].timestampValidBits : 0; free(q);
    if (!bits) { VKLOG("[RED] presentation timing unavailable on this queue"); return; }
    g_present_tick_mask = bits >= 64 ? UINT64_MAX : (1ull << bits) - 1;
    VkQueryPoolCreateInfo ci = {VK_STRUCTURE_TYPE_QUERY_POOL_CREATE_INFO, NULL, 0, VK_QUERY_TYPE_TIMESTAMP, 16};
    if (vkCreateQueryPool(V.dev, &ci, NULL, &g_present_queries)) { g_present_queries = VK_NULL_HANDLE; return; }
    const char *path = getenv("DM_VK_PRESENT_TIMES_OUT");
    if (path && *path) {
        g_present_times_file = fopen(path, "w");
        if (g_present_times_file) {
            setvbuf(g_present_times_file, NULL, _IOLBF, 0);
            fprintf(g_present_times_file, "ticket\ttime_s\tsource_w\tsource_h\tcrop_w\tcrop_h\tpresent_w\tpresent_h\tgpu_ms\n");
        } else VKLOG("[RED] cannot write presentation timing file");
    }
}
static void present_times_collect(unsigned k) {
    present_sample *s = &g_present_samples[k];
    if (!g_present_queries || !s->pending) return;
    uint64_t ticks[2];
    VkResult r = vkGetQueryPoolResults(V.dev, g_present_queries, k * 2, 2, sizeof ticks, ticks, 8, VK_QUERY_RESULT_64_BIT);
    if (r == VK_SUCCESS) {
        double ms = ((ticks[1] - ticks[0]) & g_present_tick_mask) * (double)V.props.limits.timestampPeriod / 1e6;
        if (g_present_times_file) fprintf(g_present_times_file, "%llu\t%.6f\t%u\t%u\t%u\t%u\t%u\t%u\t%.6f\n",
            (unsigned long long)s->ticket, s->time, s->size[0], s->size[1], s->size[2], s->size[3], s->size[4], s->size[5], ms);
    } else VKLOG("[RED] completed presentation timestamps unavailable: %d", r);
    s->pending = 0;
}
