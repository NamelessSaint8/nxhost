# Patches for The Legend of Zelda: Ocarina of Time (Switch 2), update 1.1.1.
#
# Diagnostics for the first-frame abort, all read-only (dm/host/hle_svc.c). The host reports the abort as
# "call site sdk+0xb8fe8" with an empty message, and the guest's own x29 chain is the SDK's forwarding stubs
# (0xba138 ← 0x7bd670), so a stack scan of the aborting thread was needed to find the code that gave up:
#
#   main+0x21e3c30  bl 0x21eaa50  → a registry lookup's error path
#   main+0x21f09a0  the lookup: six name/creator pairs at main+0x4d330a0..f8, compared with strcmp, and only
#                   two are filled in this build — "poll" (main+0x21f1280) and "none" (main+0x21f0fb0); the rest
#                   hold the sentinel name "tail_custom" with a null creator. Nothing matched, the object at
#                   [x23+0xf8] stayed null, and main+0x21f0c7c asserted through the SDK (sdk+0x777f24).
#
# The gate reads the requested name (x21) and the surroundings: whatever string the game asked a creator for, no
# entry in its own table answers to it.
#   sdk+0xba124  the message-less abort entry (sdk+0xba110): the stack scan names the code that aborted
OBS = {
    'e0f3ccfaf50065ae4ea01eb5aeb13b1a': [   # main, update 1.1.1 (main.fixups.tsv)
        (0x21f09b4, 19, 'aa1503e0', 'creator lookup: x21 is the name it wants, x0.. the name it compares with'),
    ],
    '1643a838814f9c10c696f930ed681e7f': [   # sdk, update 1.1.1 (sdk.fixups.tsv)
        (0xba124, 20, '2a1f03e3', 'nn::diag abort without a message: the call site is in the stack scan'),
    ],
}
