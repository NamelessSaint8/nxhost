// vksh: compile a DMSV shader bundle (dm/android/tools/shader_vk.py) on the device's own Vulkan driver — the step a translator check cannot make, and the
// one a port lives or dies by. Every entry gets a shader module; a compute program (stage 5) also gets a compute pipeline, and with --pairs
// <shader_pairs.tsv> each vertex/pixel pair gets a graphics pipeline, which is where Adreno's compiler does the real work. The graphics pipeline is a
// bare one: dynamic rendering with one R8G8B8A8 colour attachment and a D32 depth attachment, no vertex buffers (the port's vertex stage reads its
// attributes from the constant buffer), no blending. A failure here is the driver refusing the code, not a host interface.
//   vksh <bundle.dmsv> [--compute-only | --pairs <tsv>] [--limit N] [--verbose]
// Build: aarch64-linux-android29-clang -O1 vksh.c -o vksh -lvulkan
#define _GNU_SOURCE
#define VK_NO_PROTOTYPES
#include <dlfcn.h>
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <unistd.h>
#include <vulkan/vulkan.h>

#define VKF(n) static PFN_##n n
VKF(vkGetInstanceProcAddr); VKF(vkCreateInstance); VKF(vkEnumeratePhysicalDevices); VKF(vkGetPhysicalDeviceProperties);
VKF(vkGetPhysicalDeviceQueueFamilyProperties); VKF(vkGetPhysicalDeviceFeatures2); VKF(vkEnumerateDeviceExtensionProperties);
VKF(vkCreateDevice); VKF(vkGetDeviceProcAddr);
VKF(vkCreateShaderModule); VKF(vkDestroyShaderModule); VKF(vkCreatePipelineLayout); VKF(vkDestroyPipelineLayout);
VKF(vkCreateComputePipelines); VKF(vkCreateGraphicsPipelines); VKF(vkDestroyPipeline);

struct entry { uint64_t key; uint32_t stage, spv_off, spv_len, refl_off, refl_len, pad; };

static VkDevice dev;
static VkPipelineLayout layout;

// Every optional feature the device reports, enabled: a shader refused because the harness enabled nothing says nothing about the shader. The query
// fills each struct with what the device supports, and that same chain is what the device is created with.
struct feats {
    VkPhysicalDeviceFeatures2 base;
    VkPhysicalDeviceVulkan11Features v11;
    VkPhysicalDeviceVulkan12Features v12;
    VkPhysicalDeviceVulkan13Features v13;
    VkPhysicalDevice8BitStorageFeatures b8;
    VkPhysicalDevice16BitStorageFeatures b16;
    VkPhysicalDeviceShaderFloat16Int8Features f16i8;
    VkPhysicalDeviceRobustness2FeaturesEXT robust2;
    VkPhysicalDeviceFragmentShaderInterlockFeaturesEXT interlock;
    VkPhysicalDeviceFragmentShadingRateFeaturesKHR shading_rate;
    VkPhysicalDeviceMeshShaderFeaturesEXT mesh;
};

static void chain_features(VkPhysicalDevice pd, struct feats *f) {
    memset(f, 0, sizeof(*f));
#define LINK(a, t, n) do { f->a.sType = t; f->a.pNext = n; } while (0)
    LINK(v11, VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_VULKAN_1_1_FEATURES, &f->v12);
    LINK(v12, VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_VULKAN_1_2_FEATURES, &f->v13);
    LINK(v13, VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_VULKAN_1_3_FEATURES, &f->b8);
    LINK(b8, VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_8BIT_STORAGE_FEATURES, &f->b16);
    LINK(b16, VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_16BIT_STORAGE_FEATURES, &f->f16i8);
    LINK(f16i8, VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_SHADER_FLOAT16_INT8_FEATURES, &f->robust2);
    LINK(robust2, VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_ROBUSTNESS_2_FEATURES_EXT, &f->interlock);
    LINK(interlock, VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_FRAGMENT_SHADER_INTERLOCK_FEATURES_EXT, &f->shading_rate);
    LINK(shading_rate, VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_FRAGMENT_SHADING_RATE_FEATURES_KHR, &f->mesh);
    LINK(mesh, VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_MESH_SHADER_FEATURES_EXT, NULL);
    LINK(base, VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_FEATURES_2, &f->v11);
#undef LINK
    vkGetPhysicalDeviceFeatures2(pd, &f->base);   // fills every struct in the chain with what the device supports
}

// shader_vk STAGES: vs 0, ps 1, gs 2, hs 3, ds 4, cs 5
static VkShaderModule module_for(const uint8_t *map, const struct entry *e) {
    VkShaderModuleCreateInfo smci = {VK_STRUCTURE_TYPE_SHADER_MODULE_CREATE_INFO, NULL, 0, e->spv_len, (const uint32_t *)(map + e->spv_off)};
    VkShaderModule m = VK_NULL_HANDLE;
    return vkCreateShaderModule(dev, &smci, NULL, &m) == VK_SUCCESS ? m : VK_NULL_HANDLE;
}

static VkResult graphics_pipeline(VkShaderModule vs, VkShaderModule ps, VkPipeline *out) {
    VkPipelineShaderStageCreateInfo stages[2] = {
        {VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO, NULL, 0, VK_SHADER_STAGE_VERTEX_BIT, vs, "main", NULL},
        {VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO, NULL, 0, VK_SHADER_STAGE_FRAGMENT_BIT, ps, "main", NULL},
    };
    VkPipelineVertexInputStateCreateInfo vi = {VK_STRUCTURE_TYPE_PIPELINE_VERTEX_INPUT_STATE_CREATE_INFO, NULL, 0, 0, NULL, 0, NULL};
    VkPipelineInputAssemblyStateCreateInfo ia = {VK_STRUCTURE_TYPE_PIPELINE_INPUT_ASSEMBLY_STATE_CREATE_INFO, NULL, 0, VK_PRIMITIVE_TOPOLOGY_TRIANGLE_LIST, VK_FALSE};
    VkViewport vp = {0, 0, 1920, 1080, 0, 1};
    VkRect2D sc = {{0, 0}, {1920, 1080}};
    VkPipelineViewportStateCreateInfo vps = {VK_STRUCTURE_TYPE_PIPELINE_VIEWPORT_STATE_CREATE_INFO, NULL, 0, 1, &vp, 1, &sc};
    VkPipelineRasterizationStateCreateInfo rs = {VK_STRUCTURE_TYPE_PIPELINE_RASTERIZATION_STATE_CREATE_INFO, NULL, 0, VK_FALSE, VK_FALSE,
                                                 VK_POLYGON_MODE_FILL, VK_CULL_MODE_NONE, VK_FRONT_FACE_COUNTER_CLOCKWISE, VK_FALSE, 0, 0, 0, 1.0f};
    VkPipelineMultisampleStateCreateInfo ms = {VK_STRUCTURE_TYPE_PIPELINE_MULTISAMPLE_STATE_CREATE_INFO, NULL, 0, VK_SAMPLE_COUNT_1_BIT, VK_FALSE, 1.0f, NULL, VK_FALSE, VK_FALSE};
    VkPipelineDepthStencilStateCreateInfo ds = {VK_STRUCTURE_TYPE_PIPELINE_DEPTH_STENCIL_STATE_CREATE_INFO};
    VkPipelineColorBlendAttachmentState att = {VK_FALSE, VK_BLEND_FACTOR_ZERO, VK_BLEND_FACTOR_ZERO, VK_BLEND_OP_ADD, VK_BLEND_FACTOR_ZERO, VK_BLEND_FACTOR_ZERO,
                                               VK_BLEND_OP_ADD, VK_COLOR_COMPONENT_R_BIT | VK_COLOR_COMPONENT_G_BIT | VK_COLOR_COMPONENT_B_BIT | VK_COLOR_COMPONENT_A_BIT};
    VkPipelineColorBlendStateCreateInfo cb = {VK_STRUCTURE_TYPE_PIPELINE_COLOR_BLEND_STATE_CREATE_INFO, NULL, 0, VK_FALSE, VK_LOGIC_OP_COPY, 1, &att, {0, 0, 0, 0}};
    VkPipelineRenderingCreateInfo prc = {VK_STRUCTURE_TYPE_PIPELINE_RENDERING_CREATE_INFO, NULL, 0, 1, &(VkFormat){VK_FORMAT_R8G8B8A8_UNORM},
                                         VK_FORMAT_D32_SFLOAT, VK_FORMAT_UNDEFINED};
    VkGraphicsPipelineCreateInfo gp = {VK_STRUCTURE_TYPE_GRAPHICS_PIPELINE_CREATE_INFO, &prc, 0, 2, stages, &vi, &ia, NULL, &vps, &rs, &ms, &ds, &cb, NULL,
                                       layout, VK_NULL_HANDLE, 0, VK_NULL_HANDLE, -1};
    return vkCreateGraphicsPipelines(dev, VK_NULL_HANDLE, 1, &gp, NULL, out);
}

// key → entry index, open addressing
#define HASH 32768
static uint32_t slot[HASH];
static void build_index(uint32_t count, struct entry *ents) {
    memset(slot, 0xff, sizeof(slot));
    for (uint32_t i = 0; i < count; i++) {
        uint32_t h = (uint32_t)(ents[i].key ^ (ents[i].key >> 32)) & (HASH - 1);
        while (slot[h] != 0xffffffffu) h = (h + 1) & (HASH - 1);
        slot[h] = i;
    }
}
static int find(uint32_t count, struct entry *ents, uint64_t key) {
    uint32_t h = (uint32_t)(key ^ (key >> 32)) & (HASH - 1);
    while (slot[h] != 0xffffffffu) {
        if (ents[slot[h]].key == key) return (int)slot[h];
        h = (h + 1) & (HASH - 1);
    }
    (void)count;
    return -1;
}

int main(int argc, char **argv) {
    if (argc < 2) { fprintf(stderr, "usage: vksh <bundle.dmsv> [--compute-only | --pairs <tsv>] [--limit N] [--verbose]\n"); return 2; }
    int compute_only = 0, verbose = 0; long limit = -1; const char *pairs_path = NULL;
    for (int i = 2; i < argc; i++) {
        if (!strcmp(argv[i], "--compute-only")) compute_only = 1;
        else if (!strcmp(argv[i], "--verbose")) verbose = 1;
        else if (!strcmp(argv[i], "--pairs") && i + 1 < argc) pairs_path = argv[++i];
        else if (!strcmp(argv[i], "--limit") && i + 1 < argc) limit = atol(argv[++i]);
    }

    int fd = open(argv[1], O_RDONLY);
    if (fd < 0) { perror("open"); return 1; }
    struct stat st; fstat(fd, &st);
    const uint8_t *map = mmap(NULL, st.st_size, PROT_READ, MAP_PRIVATE, fd, 0);
    if (map == MAP_FAILED) { perror("mmap"); return 1; }
    if (memcmp(map, "DMSV", 4)) { fprintf(stderr, "not a DMSV bundle\n"); return 1; }
    uint32_t count, version;
    memcpy(&version, map + 4, 4); memcpy(&count, map + 8, 4);
    struct entry *ents = (struct entry *)(map + 12);
    printf("bundle %s: version %u, %u shaders, %.1f MB\n", argv[1], version, count, st.st_size / 1e6);

    void *lib = dlopen("libvulkan.so", RTLD_NOW);
    if (!lib) { fprintf(stderr, "no libvulkan.so: %s\n", dlerror()); return 1; }
    vkGetInstanceProcAddr = (PFN_vkGetInstanceProcAddr)dlsym(lib, "vkGetInstanceProcAddr");
    *(void **)&vkCreateInstance = (void *)vkGetInstanceProcAddr(NULL, "vkCreateInstance");
    VkInstance inst = VK_NULL_HANDLE;
    VkApplicationInfo app = {VK_STRUCTURE_TYPE_APPLICATION_INFO, NULL, "vksh", 1, NULL, 0, VK_API_VERSION_1_3};
    VkInstanceCreateInfo ici = {VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO, NULL, 0, &app, 0, NULL, 0, NULL};
    if (vkCreateInstance(&ici, NULL, &inst) != VK_SUCCESS) { fprintf(stderr, "no 1.3 instance\n"); return 1; }
    vkEnumeratePhysicalDevices = (PFN_vkEnumeratePhysicalDevices)vkGetInstanceProcAddr(inst, "vkEnumeratePhysicalDevices");
    vkGetPhysicalDeviceProperties = (PFN_vkGetPhysicalDeviceProperties)vkGetInstanceProcAddr(inst, "vkGetPhysicalDeviceProperties");
    vkGetPhysicalDeviceQueueFamilyProperties = (PFN_vkGetPhysicalDeviceQueueFamilyProperties)vkGetInstanceProcAddr(inst, "vkGetPhysicalDeviceQueueFamilyProperties");
    vkGetPhysicalDeviceFeatures2 = (PFN_vkGetPhysicalDeviceFeatures2)vkGetInstanceProcAddr(inst, "vkGetPhysicalDeviceFeatures2");
    vkEnumerateDeviceExtensionProperties = (PFN_vkEnumerateDeviceExtensionProperties)vkGetInstanceProcAddr(inst, "vkEnumerateDeviceExtensionProperties");
    uint32_t nd = 8; VkPhysicalDevice pds[8]; vkEnumeratePhysicalDevices(inst, &nd, pds);
    if (!nd) { fprintf(stderr, "no device\n"); return 1; }
    VkPhysicalDeviceProperties props; vkGetPhysicalDeviceProperties(pds[0], &props);
    printf("device: %s  API %u.%u.%u  driver %u.%u.%u\n", props.deviceName, VK_VERSION_MAJOR(props.apiVersion), VK_VERSION_MINOR(props.apiVersion),
           VK_VERSION_PATCH(props.apiVersion), VK_VERSION_MAJOR(props.driverVersion), VK_VERSION_MINOR(props.driverVersion), VK_VERSION_PATCH(props.driverVersion));
    uint32_t nq = 16; VkQueueFamilyProperties qs[16]; vkGetPhysicalDeviceQueueFamilyProperties(pds[0], &nq, qs);
    uint32_t qf = UINT32_MAX;
    for (uint32_t i = 0; i < nq; i++) if (qs[i].queueFlags & VK_QUEUE_COMPUTE_BIT) { qf = i; break; }
    if (qf == UINT32_MAX) { fprintf(stderr, "no compute queue\n"); return 1; }
    float prio = 1.0f; VkDeviceQueueCreateInfo qci = {VK_STRUCTURE_TYPE_DEVICE_QUEUE_CREATE_INFO, NULL, 0, qf, 1, &prio};
    // the shader-facing extensions the bundle's modules can declare, enabled when the driver has them
    static const char *want[] = {"VK_KHR_fragment_shading_rate", "VK_EXT_fragment_shader_interlock", "VK_EXT_mesh_shader",
                                 "VK_EXT_shader_image_atomic_int64", "VK_EXT_shader_atomic_float", "VK_EXT_shader_atomic_float2",
                                 "VK_KHR_shader_subgroup_extended_types", "VK_EXT_robustness2", "VK_EXT_shader_viewport_index_layer",
                                 "VK_EXT_shader_demote_to_helper_invocation", "VK_EXT_subgroup_size_control", "VK_KHR_shader_float_controls"};
    VkExtensionProperties exts[256]; uint32_t nx = 256; uint32_t non = 0;
    const char *on[sizeof want / sizeof *want];
    if (vkEnumerateDeviceExtensionProperties(pds[0], NULL, &nx, exts) == VK_SUCCESS)
        for (unsigned w = 0; w < sizeof want / sizeof *want; w++)
            for (uint32_t e = 0; e < nx; e++) if (!strcmp(exts[e].extensionName, want[w])) { on[non++] = want[w]; break; }
    printf("extensions enabled: %u of %u wanted", non, (unsigned)(sizeof want / sizeof *want));
    for (unsigned w = 0; w < sizeof want / sizeof *want; w++) {
        int have = 0;
        for (uint32_t e = 0; e < nx; e++) if (!strcmp(exts[e].extensionName, want[w])) { have = 1; break; }
        if (!have) printf("  missing %s", want[w]);
    }
    printf("\n");
    struct feats f; chain_features(pds[0], &f);
    VkDeviceCreateInfo dci = {VK_STRUCTURE_TYPE_DEVICE_CREATE_INFO, &f.base, 0, 1, &qci, 0, NULL, non, on, NULL};
    *(void **)&vkCreateDevice = (void *)vkGetInstanceProcAddr(inst, "vkCreateDevice");
    if (vkCreateDevice(pds[0], &dci, NULL, &dev) != VK_SUCCESS) { fprintf(stderr, "no device object\n"); return 1; }
    vkGetDeviceProcAddr = (PFN_vkGetDeviceProcAddr)vkGetInstanceProcAddr(inst, "vkGetDeviceProcAddr");
#define DGET(n) *(void **)&n = (void *)vkGetDeviceProcAddr(dev, #n)
    DGET(vkCreateShaderModule); DGET(vkDestroyShaderModule); DGET(vkCreatePipelineLayout); DGET(vkDestroyPipelineLayout);
    DGET(vkCreateComputePipelines); DGET(vkCreateGraphicsPipelines); DGET(vkDestroyPipeline);

    VkPipelineLayoutCreateInfo plci = {VK_STRUCTURE_TYPE_PIPELINE_LAYOUT_CREATE_INFO, NULL, 0, 0, NULL, 0, NULL};
    vkCreatePipelineLayout(dev, &plci, NULL, &layout);

    uint32_t mod_ok = 0, mod_bad = 0, cs_ok = 0, cs_bad = 0, gp_ok = 0, gp_bad = 0, shown = 0;
    if (pairs_path) {
        build_index(count, ents);
        FILE *f = fopen(pairs_path, "r");
        if (!f) { perror("pairs"); return 1; }
        char line[256];
        while (fgets(line, sizeof line, f)) {
            if (line[0] == '#' || line[0] == '\n') continue;
            unsigned long long vk_ = 0, pk = 0;
            if (sscanf(line, "%llx %llx", &vk_, &pk) != 2) continue;
            if (limit >= 0 && (long)(gp_ok + gp_bad) >= limit) break;
            int vi = find(count, ents, vk_), pi = find(count, ents, pk);
            if (vi < 0 || pi < 0) { gp_bad++; if (verbose || shown++ < 10) printf("  [pair] %016llx/%016llx: not in the bundle\n", vk_, pk); continue; }
            VkShaderModule vm = module_for(map, &ents[vi]), pm = module_for(map, &ents[pi]);
            if (!vm || !pm) { gp_bad++; if (verbose || shown++ < 10) printf("  [pair] %016llx/%016llx: module\n", vk_, pk); continue; }
            mod_ok += 2;
            VkPipeline pipe; VkResult r = graphics_pipeline(vm, pm, &pipe);
            if (r == VK_SUCCESS) { gp_ok++; vkDestroyPipeline(dev, pipe, NULL); }
            else { gp_bad++; if (verbose || shown++ < 10) printf("  [graphics] %016llx/%016llx: %d\n", vk_, pk, r); }
            vkDestroyShaderModule(dev, vm, NULL); vkDestroyShaderModule(dev, pm, NULL);
        }
        fclose(f);
        printf("graphics pipelines: %u ok, %u failed (%u modules made)\n", gp_ok, gp_bad, mod_ok);
    } else {
        for (uint32_t i = 0; i < count; i++) {
            struct entry *e = &ents[i];
            if (compute_only && e->stage != 5) continue;
            if (limit >= 0 && (long)(mod_ok + mod_bad) >= limit) break;
            VkShaderModule m = module_for(map, e);
            if (!m) { mod_bad++; if (verbose || shown++ < 10) printf("  [module] %016llx stage %u\n", (unsigned long long)e->key, e->stage); continue; }
            mod_ok++;
            if (e->stage == 5) {
                VkPipelineShaderStageCreateInfo stage = {VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO, NULL, 0, VK_SHADER_STAGE_COMPUTE_BIT, m, "main", NULL};
                VkComputePipelineCreateInfo cpci = {VK_STRUCTURE_TYPE_COMPUTE_PIPELINE_CREATE_INFO, NULL, 0, stage, layout, VK_NULL_HANDLE, -1};
                VkPipeline pipe; VkResult r = vkCreateComputePipelines(dev, VK_NULL_HANDLE, 1, &cpci, NULL, &pipe);
                if (r == VK_SUCCESS) { cs_ok++; vkDestroyPipeline(dev, pipe, NULL); }
                else { cs_bad++; if (verbose || shown++ < 10) printf("  [compute] %016llx: %d\n", (unsigned long long)e->key, r); }
            }
            vkDestroyShaderModule(dev, m, NULL);
        }
        printf("modules: %u ok, %u failed\n", mod_ok, mod_bad);
        printf("compute pipelines: %u ok, %u failed\n", cs_ok, cs_bad);
    }
    vkDestroyPipelineLayout(dev, layout, NULL);
    return (mod_bad || cs_bad || gp_bad) ? 1 : 0;
}
