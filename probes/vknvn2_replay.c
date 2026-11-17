// Production Vulkan backend replay fixture. Link all Android host objects with
// --wrap=main,--wrap=prog_key; only fixture shader-key lookup replaces guest input.
#include "gfx_vk.h"
#include <sys/mman.h>
#include <unistd.h>
#include <sys/wait.h>
#include <signal.h>
static unsigned checks, failed;
static unsigned proof_write_mask=15;
static int proof_mask_test;
int __wrap_prog_key(const prog_t *p, unsigned st, uint8_t key[8]) {
    if (st >= p->nstage) return 0;
    for (unsigned i = 0; i < 8; i++) key[i] = p->sd[st].data >> (56 - 8 * i);
    return 1;
}
static void test_case(unsigned mode) {
    static const char *names[] = {"direct", "task", "empty", "zero-count", "bad-task-ubo", "bad-mesh-ssbo", "per-primitive", "vertex-after-mesh", "oversize-groups", "padded-inputs"};
    uint8_t *memory = mmap(NULL, 65536, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    if (memory == MAP_FAILED) abort();
    mtl_pool_add(memory, 65536);
    prog_t program = {.serial = 200 + mode};
    int task = mode == 1 || mode == 2 || mode == 4 || mode == 5;
    program.sd[program.nstage++].data = mode == 9 ? 21 : mode == 7 ? 9 : mode == 6 ? 7 : task ? 3 : 4;
    program.sd[program.nstage++].data = mode == 9 ? 22 : mode == 7 ? 10 : mode == 6 ? 8 : task ? 6 : 5;
    if (task) program.sd[program.nstage++].data = mode == 2 ? 2 : 1;
    tex_t target = {.magic = MAGIC('T','E','X',0), .serial = 300 + mode};
    target.d.width = target.d.height = 32; target.d.depth = target.d.samples = target.d.levels = 1;
    target.d.target = NVN_TEXTURE_TARGET_2D; target.d.format = NVN_FORMAT_RGBA8;
    size_t used = 0;
#define EMIT(OP,X) do { size_t n = (8 + sizeof(X) + 7) & ~7ull; op_hdr h = {OP, (uint32_t)n}; memcpy(memory + used, &h, 8); memcpy(memory + used + 8, &(X), sizeof(X)); used += n; } while (0)
    p_set_rt rt = {.n = 1}; rt.color[0] = &target; EMIT(OP_SET_RT, rt);
    p_viewports vp = {.n = 1}; vp.v[0][2] = vp.v[0][3] = 32; EMIT(OP_VIEWPORTS, vp);
    p_scissor sc = {0,0,32,32}; EMIT(OP_SCISSOR, sc);
    p_clear_color clear = {.index = 0, .mask = 15, .rgba = {proof_mask_test?1:0,0,1,proof_mask_test?0:1}}; EMIT(OP_CLEAR_COLOR, clear);
    p_bind_program bind = {&program, 0xff}; EMIT(OP_BIND_PROGRAM, bind);
    chmask_st channels={.mask=0xfffffff0u|proof_write_mask};p_bind_state channel_state={.kind=2};memcpy(channel_state.bytes,&channels,sizeof channels);EMIT(OP_BIND_STATE,channel_state);
    for (unsigned stage = 6; stage <= 7; stage++) {
        uint32_t *cb = (uint32_t *)(memory + 4096 + stage * 512), *sb = cb + 64;
        cb[0] = stage - (mode == 4 && stage == 6); sb[0] = stage + 10 - (mode == 5 && stage == 7);
        p_bind_buf uniform = {.stage = stage, .index = 0, .addr = (uint64_t)cb, .size = 64}; EMIT(OP_BIND_UBO, uniform);
        p_bind_buf storage = {.stage = stage, .index = 0, .addr = (uint64_t)sb, .size = 64}; EMIT(OP_BIND_SSBO, storage);
    }
    if (mode == 7 || mode == 9) { p_draw d = {.prim = 4, .count = 3, .instances = 1}; EMIT(OP_DRAW, d); }
    else { p_draw_mesh d = {.first = 0x3f800000, .count = mode == 3 ? 0 : mode == 8 ? UINT32_MAX : 1}; EMIT(OP_DRAW_MESH, d); }
    op_hdr end = {OP_END,8}; memcpy(memory + used, &end, 8);
#undef EMIT
    mtl_sub_begin(); mtl_exec(memory); uint64_t fence = mtl_sub_commit();
    if (!mtl_wait(fence, 10000000000ull)) abort();
    uint8_t pixels[4096]; NVNcopyRegion region = {.width = 32, .height = 32, .depth = 1};
    mtl_read_texels(&target, 0, 0, &region, pixels, 128, 4096);
    const uint8_t *center = pixels + (16 * 32 + 16) * 4;
    unsigned empty = mode == 2 || mode == 3 || mode == 4 || mode == 8;
    unsigned red = mode == 5;
    uint8_t expected[4]={red?255:0,empty||red?0:255,empty?255:0,255};
    for(unsigned i=0;i<4;i++)if(!(proof_write_mask>>i&1))expected[i]=(uint8_t)(clear.rgba[i]*255);
    int ok=!memcmp(center,expected,4);
    checks++; failed += !ok;
    printf("replay %s %s pixel=%u,%u,%u,%u\n", names[mode], ok ? "PASS" : "FAIL", center[0], center[1], center[2], center[3]);
    mtl_pool_del(memory); munmap(memory, 65536);
}
#include "vknvn2_atlas.inc"
#include "vknvn2_copy_pages.inc"
#include "vknvn2_terrain.inc"
#include "vknvn2_measure.inc"
#include "vknvn2_atlas_checks.inc"
#include "vknvn2_driver.inc"
#include "vknvn2_gmem.inc"
#include "vknvn2_pipelines.inc"
#include "vknvn2_implicit.inc"
#include "vknvn2_offset.inc"
#include "vknvn2_outputs.inc"
#include "vknvn2_inputs.inc"
#include "vknvn2_memory.inc"
#include "vknvn2_command_copies.inc"
#include "vknvn2_image_file.inc"
#include "vknvn2_timestamps.inc"
#include "vknvn2_sparse_depth.inc"
#include "vknvn2_indirect.inc"
#include "vknvn2_uncompressed.inc"
#include "vknvn2_explicit.inc"
static int watch_work_tests(void){
    int channel[2];if(pipe(channel))abort();fflush(NULL);pid_t child=fork();if(child<0)abort();
    if(!child){close(channel[0]);unsetenv("DM_WATCH");setenv("DM_WATCH_STALL","1",1);extern void crash_install(void);crash_install();uint64_t count=crash_watch_progress_count();
        for(unsigned i=0;i<6;i++){usleep(350000);crash_watch_work_completed();}
        uint64_t after=crash_watch_progress_count();char marker=after==count?'P':'F';if(write(channel[1],&marker,1)!=1)_exit(2);close(channel[1]);for(;;)usleep(100000);
    }
    close(channel[1]);char marker=0;ssize_t got=read(channel[0],&marker,1);close(channel[0]);memory_check(got==1 && marker=='P',"completed work keeps watchdog alive without inventing presented frames");
    int status=0,done=0;for(unsigned i=0;i<500;i++){if(waitpid(child,&status,WNOHANG)==child){done=1;break;}usleep(10000);}if(!done){kill(child,SIGKILL);waitpid(child,&status,0);}
    memory_check(done && WIFEXITED(status) && WEXITSTATUS(status)==128+SIGALRM,"watchdog still stops actual inactivity after completed work ceases");
    printf("Watchdog completed work: %u checks, %u failed\n",checks,failed);return failed!=0;
}
int __wrap_main(int argc, char **argv) {
    if (argc != 2 && argc != 3) return 2;
    if(argc==3 && !strcmp(argv[2],"--watch-work"))return watch_work_tests();
    setenv("DM_VK_SHADERS", argv[1], 1);
    // Opt in only for the isolated cold/warm cache replay. Other proof modes
    // retain empty caches so first-use pipeline creation is exercised.
    if(!getenv("DM_PROBE_CACHE")){setenv("DM_VK_NOPREWARM", "1", 1);setenv("DM_VK_NOPCACHE", "1", 1);}
    if(argc==3 && (!strncmp(argv[2],"--atlas",7) || !strcmp(argv[2],"--explicit-lod") || !strcmp(argv[2],"--uncompressed-atlas") || !strcmp(argv[2],"--sparse-depth") || !strcmp(argv[2],"--measure") || !strcmp(argv[2],"--implicit-atlas") || !strcmp(argv[2],"--offset-atlas")))setenv("DM_VK_ATLAS","1",1);
    if(argc==3 && (!strcmp(argv[2],"--copy-pages") || !strcmp(argv[2],"--ownership-checks")))setenv("DM_VK_ATLAS","1",1);
    mtl_init();
    if(argc==3 && !strcmp(argv[2],"--prewarm-recorded")){
        setenv("DM_VK_PREWARM_SYNC","1",1);unsetenv("DM_VK_NOPREWARM");uint64_t start=measure_ns(CLOCK_MONOTONIC);vk_exec_reset();uint64_t processed,total;vk_prewarm_stats(&processed,&total);
        memory_check(total>0 && processed==total,"synchronous startup processes every unique recorded pipeline before replay");
        printf("recorded prewarm: processed=%llu total=%llu elapsed_ms=%.2f RSS_KiB=%ld PSS_KiB=%ld\n",(unsigned long long)processed,(unsigned long long)total,(measure_ns(CLOCK_MONOTONIC)-start)/1e6,measure_proc("/proc/self/status","VmRSS:"),measure_proc("/proc/self/smaps_rollup","Pss:"));
        printf("Recorded prewarm: %u checks, %u failed\n",checks,failed);return failed!=0;
    }
    if(argc==3 && !strcmp(argv[2],"--command-copies")){command_copy_tests();printf("Command lifetimes: %u checks, %u failed\n",checks,failed);return failed!=0;}
    if(argc==3 && !strcmp(argv[2],"--timestamps")){timestamp_tests();printf("NVN timestamps: %u checks, %u failed\n",checks,failed);return failed!=0;}
    if(argc==3 && !strcmp(argv[2],"--atlas-checks")){atlas_checks_tests();printf("Atlas descriptor checks: %u checks, %u failed\n",checks,failed);return failed!=0;}
    if(argc==3 && !strcmp(argv[2],"--ownership-checks")){ownership_checks_tests();printf("Ownership checks: %u checks, %u failed\n",checks,failed);return failed!=0;}
    if(argc==3 && !strcmp(argv[2],"--copy-pages")){copy_pages_tests();printf("Sparse copy pages: %u checks, %u failed\n",checks,failed);return failed!=0;}
    if(argc==3 && !strcmp(argv[2],"--atlas-cpu-physical")){atlas_physical_flags=0x18c;atlas_tests();printf("CPU physical atlas: %u checks, %u failed\n",checks,failed);return failed!=0;}
    if(argc==3 && !strcmp(argv[2],"--lazy-pools")){lazy_pool_tests();printf("Lazy cached pools: %u checks, %u failed\n",checks,failed);return failed!=0;}
    if(argc==3 && !strcmp(argv[2],"--lazy-all-pools")){lazy_all_pool_tests();printf("Lazy all pools: %u checks, %u failed\n",checks,failed);return failed!=0;}
    if(argc==3 && !strcmp(argv[2],"--copied-bindings")){copied_binding_tests();printf("Copied pool bindings: %u checks, %u failed\n",checks,failed);return failed!=0;}
    if(argc==3 && !strcmp(argv[2],"--cpu-file")){cpu_file_tests();printf("CPU file backing: %u checks, %u failed\n",checks,failed);return failed!=0;}
    if(argc==3 && !strcmp(argv[2],"--pool-registry")){pool_registry_tests();printf("Pool registry: %u checks, %u failed\n",checks,failed);return failed!=0;}
    if(argc==3 && !strcmp(argv[2],"--image-heap")){image_heap_tests();printf("Image heap: %u checks, %u failed\n",checks,failed);return failed!=0;}
    if(argc==3 && !strcmp(argv[2],"--scratch-retirement")){scratch_retirement_tests();printf("Scratch retirement: %u checks, %u failed\n",checks,failed);return failed!=0;}
    if(argc==3 && !strcmp(argv[2],"--fragment-libraries")){
        proof_mask_test=1;
        for(proof_write_mask=0;proof_write_mask<16;proof_write_mask++)test_case(7);
        uint64_t created,reused;vk_fragment_library_stats(&created,&reused);checks+=2;failed+=created!=1;failed+=reused!=15;
        printf("Fragment libraries: %u checks, %u failed, created=%llu reused=%llu\n",checks,failed,(unsigned long long)created,(unsigned long long)reused);return failed!=0;
    }
    if(argc==3 && !strcmp(argv[2],"--mapping-fragmentation")){fragmentation_tests();printf("Mapping fragmentation: %u checks, %u failed\n",checks,failed);return failed!=0;}
    if(argc==3 && !strcmp(argv[2],"--explicit-lod")){explicit_tests();printf("Explicit LOD: %u checks, %u failed\n",checks,failed);return failed!=0;}
    if(argc==3 && !strcmp(argv[2],"--uncompressed-atlas")){uncompressed_tests();printf("Uncompressed atlas: %u checks, %u failed\n",checks,failed);return failed!=0;}
    if(argc==3 && !strcmp(argv[2],"--indirect-count")){indirect_tests();printf("Indirect count: %u checks, %u failed\n",checks,failed);return failed!=0;}
    if(argc==3 && !strcmp(argv[2],"--sparse-depth")){sparse_depth_tests();printf("Sparse depth: %u checks, %u failed\n",checks,failed);return failed!=0;}
    if(argc==3 && !strcmp(argv[2],"--memory-accounting")){memory_tests();printf("Memory accounting: %u checks, %u failed\n",checks,failed);return failed!=0;}
    if(argc==3 && !strcmp(argv[2],"--image-file")){image_file_tests();printf("GPU image file cache: %u checks, %u failed\n",checks,failed);return failed!=0;}
    if(argc==3 && !strcmp(argv[2],"--fragment-outputs")){output_tests();printf("Fragment exports: %u checks, %u failed\n",checks,failed);return failed!=0;}
    if(argc==3 && !strcmp(argv[2],"--storage-bits")){storage_bits_tests();printf("Storage bits: %u checks, %u failed\n",checks,failed);return failed!=0;}
    if(argc==3 && !strcmp(argv[2],"--vertex-bits")){vertex_bits_tests();printf("Vertex bits: %u checks, %u failed\n",checks,failed);return failed!=0;}
    if(argc==3 && !strcmp(argv[2],"--shared-spill")){shared_spill_tests();printf("Shared spill: %u checks, %u failed\n",checks,failed);return failed!=0;}
    if(argc==3 && !strcmp(argv[2],"--offset-atlas")){offset_tests();printf("Offset atlas replay: %u checks, %u failed\n",checks,failed);return failed!=0;}
    if(argc==3 && !strcmp(argv[2],"--implicit-atlas")){implicit_tests();printf("Implicit atlas replay: %u checks, %u failed\n",checks,failed);return failed!=0;}
    if(argc==3 && !strncmp(argv[2],"--pipelines=",12)){observed_pipelines(argv[2]+12);printf("Observed pipelines: %u checks, %u failed (compile only)\n",checks,failed);return failed!=0 || !checks;}
    if(argc==3 && !strncmp(argv[2],"--driver-reject-",16)){const char *mode=argv[2]+16;driver_reject(!strcmp(mode,"push")?0:!strcmp(mode,"truncated")?1:!strcmp(mode,"groups")?2:!strcmp(mode,"address")?3:4);return 3;}
    if(argc==3 && (!strcmp(argv[2],"--global-memory") || !strcmp(argv[2],"--global-memory-cooperative"))){gmem_tests(!strcmp(argv[2],"--global-memory-cooperative"));printf("Raw global memory: %u checks, %u failed\n",checks,failed);return failed!=0;}
    if(argc==3 && !strcmp(argv[2],"--driver-state")){driver_tests();printf("Driver state replay: %u checks, %u failed\n",checks,failed);return failed!=0;}
    if(argc==3 && !strcmp(argv[2],"--restore-check")){measure_restore_check();return 0;}
    if(argc==3 && !strcmp(argv[2],"--measure")){measure_atlas();return 0;}
    if(argc==3 && !strncmp(argv[2],"--atlas-reject-",15)){atlas_negative=!strcmp(argv[2]+15,"partial")?1:!strcmp(argv[2]+15,"sampler")?2:3;if(atlas_negative==2)implicit_case(0,1,0);else atlas_case(0,1);return 3;}
    if(argc==3 && !strcmp(argv[2],"--terrain")){terrain_tests();printf("Terrain replay: %u checks, %u failed\n",checks,failed);return failed!=0;}
    if(argc==3 && !strcmp(argv[2],"--atlas")){atlas_tests();printf("Mapped atlas replay: %u checks, %u failed\n",checks,failed);return failed!=0;}
    if (argc == 3 && !strcmp(argv[2], "--load-only")) {
        FILE *file = fopen(argv[1], "rb"); if (!file) return 2;
        uint32_t header[3]; if (fread(header, sizeof header, 1, file) != 1 || header[0] != 0x56534d44) return 2;
        for (uint32_t i = 0; i < header[2]; i++) {
            struct __attribute__((packed)) { uint64_t key; uint32_t stage, rest[5]; } entry;
            if (fread(&entry, sizeof entry, 1, file) != 1) return 2;
            vkshader_t *shader = vk_shader(entry.key, entry.stage);
            int ok = shader != NULL; checks++; failed += !ok;
            printf("module %016llx stage=%u %s\n", (unsigned long long)entry.key, entry.stage, ok ? "PASS" : "FAIL");
        }
        fclose(file); printf("Bundle modules: %u checks, %u failed (no dispatch)\n", checks, failed); return failed != 0;
    }
    for (unsigned i = 0; i < 10; i++) test_case(i);
    if(getenv("DM_PROBE_CACHE")){mtl_drain();test_case(7);test_case(6);mtl_drain();}
    printf("NVN2 replay: %u checks, %u failed\n", checks, failed); return failed != 0;
}
