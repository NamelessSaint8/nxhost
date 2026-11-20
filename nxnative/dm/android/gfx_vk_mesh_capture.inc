// One draw's descriptor bytes, base shader binaries and attachment state.
// The manifest records ranges that exceed the bounded capture.
enum { MESH_CAPTURE_ITEMS = 32, MESH_CAPTURE_BYTES = 32 * 1024 * 1024 };
static struct {
    FILE *file;
    char base[1024];
    unsigned count;
    VkDeviceSize bytes;
    struct {
        char name[48];
        VkDescriptorBufferInfo buffer;
        VkImage image;
        VkBufferImageCopy texels[32];
        unsigned regions;
        VkDeviceSize bytes;
        const void *data;
    } item[MESH_CAPTURE_ITEMS];
} g_mesh_capture;

static void mesh_capture_write(const char *name, const void *bytes, size_t length) {
    char path[1100];
    snprintf(path, sizeof path, "%s.%s", g_mesh_capture.base, name);
    FILE *f = fopen(path, "wb");
    if (!f) die("[RED] cannot write mesh capture %s", path);
    if (fwrite(bytes, 1, length, f) != length || fclose(f)) die("[RED] short mesh capture %s", path);
}

static int mesh_capture_begin(uint64_t key, const uint32_t *args) {
    const char *root = getenv("DM_ROOT");
    if (!root) { VKLOG("mesh capture needs DM_ROOT"); return 0; }
    memset(&g_mesh_capture, 0, sizeof g_mesh_capture);
    snprintf(g_mesh_capture.base, sizeof g_mesh_capture.base, "%s/mesh_%016llx_%llu",
             root, (unsigned long long)key, (unsigned long long)g_tex_frame);
    char path[1100];
    snprintf(path, sizeof path, "%s.tsv", g_mesh_capture.base);
    g_mesh_capture.file = fopen(path, "w");
    if (!g_mesh_capture.file) { VKLOG("cannot open mesh capture %s", path); return 0; }
    fprintf(g_mesh_capture.file, "args %u %u %u %u\n", args[0], args[1], args[2], args[3]);
    return 1;
}

static int mesh_capture_reserve(VkDeviceSize bytes) {
    return g_mesh_capture.count < MESH_CAPTURE_ITEMS && bytes &&
           !(bytes & 3) && bytes <= MESH_CAPTURE_BYTES - g_mesh_capture.bytes;
}

static void mesh_capture_buffer(int stage, unsigned binding, unsigned type, const VkDescriptorBufferInfo *info) {
    FILE *f = g_mesh_capture.file;
    char name[48];
    snprintf(name, sizeof name, "s%d_b%u.bin", stage, binding);
    int take = info->buffer && !(info->offset & 3) && mesh_capture_reserve(info->range);
    fprintf(f, "buffer %d %u %u %llu %llu %s\n", stage, binding, type,
            (unsigned long long)info->offset, (unsigned long long)info->range, take ? name : "omitted");
    if (!take) return;
    typeof(g_mesh_capture.item[0]) *item = &g_mesh_capture.item[g_mesh_capture.count++];
    strcpy(item->name, name);
    item->buffer = *info;
    item->bytes = info->range;
    g_mesh_capture.bytes += item->bytes;
}

static void mesh_capture_image(int stage, const dmsv_bind *binding, vkimg_t *im,
                               const VkDescriptorImageInfo *info, int storage) {
    VkImageViewCreateInfo view;
    if (!im || !info->imageView || !vk_tex_view_description(im, info->imageView, &view)) return;
    FILE *f = g_mesh_capture.file;
    unsigned slot = g_mesh_capture.count;
    char name[48], sampler[48];
    snprintf(name, sizeof name, "s%d_b%u_i%u.bin", stage, binding->binding, slot);
    snprintf(sampler, sizeof sampler, "s%d_b%u_i%u.sampler.bin", stage, binding->binding, slot);
    const vkfmt_t *fmt = vk_fmt(im->nvn_format);
    VkImageSubresourceRange r = view.subresourceRange;
    unsigned w = im->w >> r.baseMipLevel, h = im->h >> r.baseMipLevel;
    w = w ? w : 1; h = h ? h : 1;
    VkDeviceSize bytes = 0;
    VkBufferImageCopy regions[32];
    if (fmt && r.levelCount <= 32) for (unsigned level = 0; level < r.levelCount; level++) {
        unsigned lw = w >> level, lh = h >> level;
        lw = lw ? lw : 1; lh = lh ? lh : 1;
        bytes = (bytes + 15) & ~(VkDeviceSize)15;
        regions[level] = (VkBufferImageCopy){.bufferOffset = bytes,
            .imageSubresource = {r.aspectMask, r.baseMipLevel + level, r.baseArrayLayer, r.layerCount},
            .imageExtent = {lw, lh, 1}};
        bytes += (VkDeviceSize)((lw + fmt->bw - 1) / fmt->bw) * ((lh + fmt->bh - 1) / fmt->bh) * fmt->bpb * r.layerCount;
    }
    int take = !storage && fmt && fmt->vk == im->fmt && im->samples == 1 &&
        fmt->bpb <= 16 && !(fmt->bpb & (fmt->bpb - 1)) && im->layout == VK_IMAGE_LAYOUT_GENERAL &&
        !im->file_paged && (im->usage & VK_IMAGE_USAGE_TRANSFER_SRC_BIT) &&
        r.aspectMask == VK_IMAGE_ASPECT_COLOR_BIT &&
        (view.viewType == VK_IMAGE_VIEW_TYPE_2D || view.viewType == VK_IMAGE_VIEW_TYPE_2D_ARRAY) &&
        r.levelCount && r.levelCount <= 32 && r.layerCount && mesh_capture_reserve(bytes);
    samp_par params;
    int have_sampler = take && vk_samp_parameters(info->sampler, &params);
    fprintf(f, "image %d %u %u %u %u %u %u %u %u %u %u %u %u %u %u %u %u %s %s\n",
            stage, binding->binding, im->fmt, view.format, w, h, view.viewType, r.aspectMask,
            r.baseMipLevel, r.levelCount, r.baseArrayLayer, r.layerCount, view.components.r,
            view.components.g, view.components.b, view.components.a, storage, take ? name : "omitted",
            have_sampler ? sampler : "omitted");
    if (!take) return;
    if (have_sampler) mesh_capture_write(sampler, &params, sizeof params);
    typeof(g_mesh_capture.item[0]) *item = &g_mesh_capture.item[g_mesh_capture.count++];
    strcpy(item->name, name);
    item->image = im->img;
    item->regions = r.levelCount;
    memcpy(item->texels, regions, r.levelCount * sizeof *regions);
    item->bytes = bytes;
    g_mesh_capture.bytes += item->bytes;
}

static void mesh_capture_pipeline(const pkey *k, vkshader_t *const shaders[3]) {
    FILE *f = g_mesh_capture.file;
    fprintf(f, "attachments %u %u %u %u %u\n", k->ncol, k->dfmt, k->samples, S.pass_w, S.pass_h);
    for (unsigned i = 0; i < k->ncol; i++) fprintf(f, "color %u %u %u\n", i, k->cfmt[i], k->wmask[i]);
    fprintf(f, "raster %u %u %u %u %u %u\n", k->cull, k->front, k->mode, k->dt, k->dw, k->df);
    fprintf(f, "viewport %g %g %g %g %g %g\n", S.vp[0][0], S.vp[0][1], S.vp[0][2], S.vp[0][3], S.dnear, S.dfar);
    VkRect2D scissor = scissor_rect();
    fprintf(f, "scissor %d %d %u %u\n", scissor.offset.x, scissor.offset.y, scissor.extent.width, scissor.extent.height);
    for (unsigned i = 0; i < 3; i++) if (shaders[i]) {
        char name[48];
        snprintf(name, sizeof name, "stage%u.spv", shaders[i]->stage);
        fprintf(f, "shader %u %u %016llx %llx %llx %llx %s\n", shaders[i]->stage, shaders[i]->set,
                (unsigned long long)shaders[i]->key, (unsigned long long)k->um[i],
                (unsigned long long)k->im[i], (unsigned long long)k->atlas[i], name);
        mesh_capture_write(name, shaders[i]->spv, (size_t)shaders[i]->nspv * 4);
    }
}

static void mesh_capture_finish(void) {
    VkCommandBuffer cb = vk_cmd();
    vk_img_barrier_all(cb);
    for (unsigned i = 0; i < g_mesh_capture.count; i++) {
        typeof(g_mesh_capture.item[0]) *item = &g_mesh_capture.item[i];
        VkBuffer staging;
        VkDeviceSize offset;
        item->data = vk_scratch(item->bytes, 16, &staging, &offset);
        if (item->image) {
            for (unsigned j = 0; j < item->regions; j++) item->texels[j].bufferOffset += offset;
            vkCmdCopyImageToBuffer(cb, item->image, VK_IMAGE_LAYOUT_GENERAL, staging, item->regions, item->texels);
        } else {
            VkBufferCopy copy = {item->buffer.offset, offset, item->bytes};
            vkCmdCopyBuffer(cb, item->buffer.buffer, staging, 1, &copy);
        }
    }
    vk_cmd_sync_host();
    for (unsigned i = 0; i < g_mesh_capture.count; i++)
        mesh_capture_write(g_mesh_capture.item[i].name, g_mesh_capture.item[i].data, g_mesh_capture.item[i].bytes);
    if (fclose(g_mesh_capture.file)) die("[RED] mesh capture manifest close failed");
    g_mesh_capture.file = NULL;
    VKLOG("mesh capture complete: %s", g_mesh_capture.base);
}
