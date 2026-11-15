# Patches for The Legend of Zelda: Ocarina of Time (Switch 2), update 1.1.1.
#
# Diagnostics, all read-only (dm/host/hle_svc.c).
#
#   sdk+0x84f668  __cxa_throw's `mov x20,x1`: every C++ throw in the process passes here, and x1 is the type_info,
#                 whose +8 names the type. The callback prints only the allocation failure (type "*St9bad_alloc") with
#                 its x29 chain. main has no `__throw_bad_alloc` of its own — it imports __cxa_throw and defines
#                 _Znwm/malloc locally — so this is where main's throw lands. An earlier gate at sdk+0x7d8f44 was on
#                 the dynsym's thunk, not the body (the real _ZSt17__throw_bad_allocv is sdk+0x7d91a0), and never fired.
#   sdk+0xba124   the message-less nn::diag abort entry: the x29 chain plus a stack scan names the code that gave up
#                 (this title's is a gRPC creator lookup for "all", reported in the README).
OBS = {
    '1643a838814f9c10c696f930ed681e7f': [   # sdk, update 1.1.1 (sdk.fixups.tsv)
        (0x84f668, 27, 'aa0103f4', '__cxa_throw: x1 is the type_info, filtered to the allocation failure'),
        (0xba124, 20, '2a1f03e3', 'nn::diag abort without a message: the call site is in the stack scan'),
    ],
}
