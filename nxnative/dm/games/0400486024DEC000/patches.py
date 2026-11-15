# Patches for The Legend of Zelda: Ocarina of Time (Switch 2), update 1.1.1.
#
# Diagnostics, all read-only (dm/host/hle_svc.c).
#
#   sdk+0x7780a4  the sdk's abort(): the dynsym's value 0x7780a0 is the entry the loader binds (the 0x778080 prologue before
#                 it belongs to a different function), so the gate sits on the `mov w0,w19` inside that entry. It reports the
#                 caller and, with DM_ABORT_CONT, parks the thread instead of letting the host's bionic abort end the process.
#   sdk+0x84f668  __cxa_throw's `mov x20,x1`: every C++ throw passes here and x1 is the type_info, whose +8 names the type,
#                 so the callback prints only the allocation failure (*St9bad_alloc) with the x29 chain of the thrower.
#                 main has no __throw_bad_alloc — it imports __cxa_throw and defines _Znwm/malloc locally.
#   sdk+0xba124   the message-less nn::diag abort entry: the x29 chain plus a stack scan names the code that gave up (this
#                 title's is a gRPC creator lookup for "all", reported in the README).
OBS = {
    '1643a838814f9c10c696f930ed681e7f': [   # sdk, update 1.1.1 (sdk.fixups.tsv)
        (0x7780a4, 28, '2a1303e0', "the sdk's abort(): the entry the loader binds is 0x7780a0, so the gate sits inside it"),
        (0x84f668, 27, 'aa0103f4', '__cxa_throw: x1 is the type_info, filtered to the allocation failure'),
        (0xba124, 20, '2a1f03e3', 'nn::diag abort without a message: the call site is in the stack scan'),
    ],
}
