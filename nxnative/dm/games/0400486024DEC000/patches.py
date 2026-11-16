# Patches for The Legend of Zelda: Ocarina of Time (Switch 2), update 1.1.1.
#
# Diagnostics, all read-only (dm/host/hle_svc.c).
#
#   main+0xf2722c  main's operator new (_Znwm at main+0xf271c0) failure path: x19 still holds the requested size there, and the next
#                  instructions tail-call the SDK's exception allocation with w0 = 16 (sizeof(std::bad_alloc)). This is the only place
#                  the size that could not be satisfied is readable — the throw itself carries an empty bad_alloc, and the abort that
#                  follows names neither the size nor the caller.
#   main+0x21f09b4 gRPC poll selection: "all" is the wildcard; EventFd availability decides whether its poll factory succeeds.
#   sdk+0x7780a4   the sdk's abort(): the dynsym's value 0x7780a0 is the entry the loader binds (the 0x778080 prologue before it
#                  belongs to a different function), so the gate sits on the `mov w0,w19` inside that entry. It reports the caller and,
#                  with DM_ABORT_CONT, parks the thread instead of letting the host's bionic abort end the process.
#   sdk+0x84f668   __cxa_throw's `mov x20,x1`: x1 is the type_info, whose +8 names the type, so the callback prints only the
#                  allocation failure (*St9bad_alloc) with the x29 chain of the thrower. main has no __throw_bad_alloc of its own.
#   sdk+0xba124    the message-less nn::diag abort entry: the x29 chain plus a stack scan names the code that gave up.
OBS = {
    'e0f3ccfaf50065ae4ea01eb5aeb13b1a': [   # main, update 1.1.1 (main.fixups.tsv)
        # main's malloc (main+0x14c6c90): 0x14c6cc8 is its failure path — it sets errno = 0xc (ENOMEM) and returns null — and 0x14c6ca8
        # is the normal path with the size still in x0. main's operator new[] (main+0xf204a0) is five instructions that move the size
        # from x0 to x1 before tail-calling 0x3ea70, so 0xf204a4 is its entry with the request in x0.
        (0x14c6cc8, 29 | 3 << 8, '52800189', 'malloc failure: errno = ENOMEM, returns null'),
        (0x14c6ca8, 29 | 4 << 8, 'aa0003e1', 'malloc entry: x0 is the requested size'),
        (0xf204a4, 29 | 5 << 8, 'aa0003e1', 'operator new[] entry: x0 is the requested size'),
        (0xf2722c, 29, 'aa1303e1', "operator new: x19 is the requested size, the caller is the gate's saved x30"),
        (0x21f09b4, 19, 'aa1503e0', 'gRPC poll selection: x21 is the requested strategy, x20 the all wildcard'),
    ],
}

BINDING = [
    {'what': 'Read-only allocator and gRPC observation gates', 'now': 'build', 'goal': 'build', 'purpose': 'runtime',
     'why': 'diagnostics at exact instructions in main 1.1.1; SDK observations live in sdk_patches.py'},
]
