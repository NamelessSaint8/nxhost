# Patches for The Legend of Zelda: Ocarina of Time (Switch 2), update 1.1.1.
#
# Diagnostics, all read-only (dm/host/hle_svc.c).
#
#   main+0xf2722c  main's operator new (_Znwm at main+0xf271c0) failure path: x19 still holds the requested size there, and the next
#                  instructions tail-call the SDK's exception allocation with w0 = 16 (sizeof(std::bad_alloc)). This is the only place
#                  the size that could not be satisfied is readable — the throw itself carries an empty bad_alloc, and the abort that
#                  follows names neither the size nor the caller.
#   main+0x21f09b4 the creator lookup that aborts: x21 is the name it wants ("all"), which its own registry does not answer.
#   sdk+0x7780a4   the sdk's abort(): the dynsym's value 0x7780a0 is the entry the loader binds (the 0x778080 prologue before it
#                  belongs to a different function), so the gate sits on the `mov w0,w19` inside that entry. It reports the caller and,
#                  with DM_ABORT_CONT, parks the thread instead of letting the host's bionic abort end the process.
#   sdk+0x84f668   __cxa_throw's `mov x20,x1`: x1 is the type_info, whose +8 names the type, so the callback prints only the
#                  allocation failure (*St9bad_alloc) with the x29 chain of the thrower. main has no __throw_bad_alloc of its own.
#   sdk+0xba124    the message-less nn::diag abort entry: the x29 chain plus a stack scan names the code that gave up.
OBS = {
    'e0f3ccfaf50065ae4ea01eb5aeb13b1a': [   # main, update 1.1.1 (main.fixups.tsv)
        (0xf2722c, 29, 'aa1303e1', "operator new failed: x19 is the requested size, the caller is the gate's saved x30"),
        (0x21f09b4, 19, 'aa1503e0', 'creator lookup: x21 is the name it wants, x0.. the name it compares with'),
    ],
    '1643a838814f9c10c696f930ed681e7f': [   # sdk, update 1.1.1 (sdk.fixups.tsv)
        (0x7780a4, 28, '2a1303e0', "the sdk's abort(): the entry the loader binds is 0x7780a0, so the gate sits inside it"),
        (0x84f668, 27, 'aa0103f4', '__cxa_throw: x1 is the type_info, filtered to the allocation failure'),
        (0xba124, 20, '2a1f03e3', 'nn::diag abort without a message: the call site is in the stack scan'),
    ],
}
