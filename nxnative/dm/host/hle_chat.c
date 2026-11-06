// nn::chat: the parts of the chat library a Switch 2 title initialises at start-up. Local camera video storage is chat's own video capture path -- a
// camera stream it records locally -- and the host has neither a camera nor anywhere to put it, so the call is stubbed to succeed rather than aborting.
// Mario Kart World asserts inside this function on any failure (AbortImpl at sdk+0x6bf45c), which is why a stub is enough to move it on: it never
// inspects what the storage points at until something asks it to record.
#include "hle.h"

HLE_FORCE("_ZN2nn4chat33InitializeLocalCameraVideoStorageEPNS0_20LocalCameraVideoTypeEiiiPvm",
          "stubbed: chat's local camera video storage does not exist on this host", Result, h_chat_InitCameraStorage, void *type, int a, int b,
          int c, void *buffer, size_t size) {
    static int n;
    if (n++ < 8) LOG("[chat] InitializeLocalCameraVideoStorage(type %p, %d, %d, %d, buf %p, %#zx) -> success (stub)", type, a, b, c, buffer, size);
    return RES_OK;
}
