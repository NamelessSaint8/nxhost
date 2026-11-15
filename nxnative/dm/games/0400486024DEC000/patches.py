# Patches for The Legend of Zelda: Ocarina of Time (Switch 2), update 1.1.1.
#
# Diagnostics, all read-only (dm/host/hle_svc.c).
#
#   sdk+0x7d8f44  std::__throw_bad_alloc's `mov x19,x0`: the guest's own allocation failure reaches the host only as
#                 "terminating due to uncaught exception of type St9bad_alloc", which names neither the size nor the
#                 caller. The gate reads both from the registers and frame the failing caller left behind.
#   sdk+0xba124   the message-less nn::diag abort entry: the x29 chain plus a stack scan names the code that gave up
#                 (this title's is a gRPC creator lookup for "all", reported below).
OBS = {
    '1643a838814f9c10c696f930ed681e7f': [   # sdk, update 1.1.1 (sdk.fixups.tsv)
        (0x7d8f44, 27, 'aa0003f3', 'std::__throw_bad_alloc: the caller registers and frame hold the failed size'),
        (0xba124, 20, '2a1f03e3', 'nn::diag abort without a message: the call site is in the stack scan'),
    ],
}
