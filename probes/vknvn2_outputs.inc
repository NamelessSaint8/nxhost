// Exercise production attachment selection, mixed MRT types and cached variants.
static void output_tests(void) {
    uint8_t *memory = mmap(NULL, 65536, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    if (memory == MAP_FAILED) abort(); mtl_pool_add(memory, 65536);
    prog_t program = {.serial = 2600, .nstage = 2}; program.sd[0].data = 23; program.sd[1].data = 26;
    // Three independent locations produce 27 numeric type combinations, then a
    // narrow unsigned target and a repeat prove the original and cached modules.
    const unsigned formats[] = {0x2e, 0x0b, 0x0c};
    const uint32_t raw[] = {35, (uint32_t)-7, 0x3e800000};
    for (unsigned test = 0; test < 29; test++) {
        tex_t targets[3]; memset(targets, 0, sizeof targets);
        unsigned num[3], select = test < 27 ? test : 0;
        for (unsigned i = 0; i < 3; i++) {
            num[i] = select % 3; select /= 3;
            targets[i].magic = MAGIC('T','E','X',0); targets[i].serial = 2700 + test*3 + i;
            targets[i].d.width = targets[i].d.height = 8;
            targets[i].d.depth = targets[i].d.samples = targets[i].d.levels = 1;
            targets[i].d.target = NVN_TEXTURE_TARGET_2D; targets[i].d.format = formats[num[i]];
        }
        if (test == 27) { targets[0].d.format = 0x03; num[0] = 1; }
        size_t used = 0;
#define EMIT(OP,X) do { size_t n = (8 + sizeof(X) + 7) & ~7ull; op_hdr h = {OP, (uint32_t)n}; memcpy(memory+used, &h, 8); memcpy(memory+used+8, &(X), sizeof(X)); used += n; } while (0)
        p_set_rt rt = {.n = 3}; for (unsigned i = 0; i < 3; i++) rt.color[i] = &targets[i]; EMIT(OP_SET_RT, rt);
        p_viewports vp = {.n = 1}; vp.v[0][2] = vp.v[0][3] = 8; EMIT(OP_VIEWPORTS, vp);
        p_scissor sc = {0,0,8,8}; EMIT(OP_SCISSOR, sc);
        for (unsigned i = 0; i < 3; i++) { p_clear_color clear = {.index = (int)i, .mask = 15, .rgba = {3,3,3,3}}; EMIT(OP_CLEAR_COLOR, clear); }
        p_bind_program bind = {&program, 0xff}; EMIT(OP_BIND_PROGRAM, bind);
        p_draw draw = {.prim = 4, .count = 3, .instances = 1}; EMIT(OP_DRAW, draw);
        op_hdr end = {OP_END,8}; memcpy(memory+used, &end, 8);
#undef EMIT
        mtl_sub_begin(); mtl_exec(memory); uint64_t fence = mtl_sub_commit();
        if (!mtl_wait(fence, 10000000000ull)) abort();
        for (unsigned i = 0; i < 3; i++) {
            uint32_t pixels[8*8*4]; memset(pixels, 0, sizeof pixels);
            unsigned bytes = test == 27 && i == 0 ? 1 : num[i] ? 4 : 16;
            NVNcopyRegion region = {.width = 8, .height = 8, .depth = 1};
            mtl_read_texels(&targets[i], 0, 0, &region, (uint8_t *)pixels, 8*bytes, 64*bytes);
            int ok = 1;
            for (unsigned p = 0; p < 64; p++) {
                uint32_t got = bytes == 1 ? ((uint8_t *)pixels)[p] : pixels[p*(bytes/4)];
                if (num[i]) ok &= got == raw[i];
                else if (i == 0) ok &= got == 0 || got == raw[i]; // hardware may flush float subnormals
                else if (i == 1) ok &= (got & 0x7f800000) == 0x7f800000 && (got & 0x7fffff); // NaN
                else ok &= got == raw[i];
            }
            checks++; failed += !ok;
            printf("fragment exports case=%u location=%u format=%x %s\n", test, i, targets[i].d.format, ok ? "PASS" : "FAIL");
            mtl_tex_release(&targets[i]);
        }
    }
    vkshader_t *s = vk_shader(26, 1);
    int cached = s->nvar == 26 && s->capvar >= s->nvar;
    checks++; failed += !cached;
    printf("fragment exports cached variants=%d capacity=%d %s\n", s->nvar, s->capvar, cached ? "PASS" : "FAIL");
    mtl_pool_del(memory); munmap(memory, 65536);
}
