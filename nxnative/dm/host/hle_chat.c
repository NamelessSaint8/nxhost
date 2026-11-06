// nn::chat: the parts of the chat library a Switch 2 title initialises at start-up. Local and remote camera video storage are chat's own capture paths,
// and Mario Kart World feeds the handles they hand back into NVN2: main+0xd32318 asks for an image handle, puts it in an NVNnativeImageBuilder and
// initialises a texture from it, so a handle has to name a real picture -- nvnTextureInitializeFromNativeImage resolves it through dm_native_image,
// which knows only pools (hle_codec_video.c). Each storage therefore owns a one-picture pool of its own instead of answering with nothing behind it,
// and the picture is the host's: no camera exists, so nothing ever writes into it.
#include "hle.h"

typedef struct { uint32_t handle, w, h; } cam_pic;
static cam_pic g_cam_local, g_cam_remote;

static Result cam_init(cam_pic *c, const char *which, void *type, int w, int h, int fmt, void *buffer, size_t size) {
    if (!c->handle && w > 0 && h > 0) {
        c->handle = dm_picture_pool_new((uint32_t)w, (uint32_t)h);   // resolved by dm_native_image
        c->w = (uint32_t)w; c->h = (uint32_t)h;
    }
    static int n;
    if (n++ < 8)
        LOG("[chat] Initialize%sCameraVideoStorage(type %p, %dx%d fmt %d, buf %p, %#zx) -> picture handle %#x", which, type, w, h, fmt, buffer, size,
            c->handle);
    return c->handle ? RES_OK : RES_FAIL;
}

HLE_FORCE("_ZN2nn4chat33InitializeLocalCameraVideoStorageEPNS0_20LocalCameraVideoTypeEiiiPvm",
          "the host's own picture stands in for the camera's: this title hands its handle to NVN2", Result, h_chat_InitLocal, void *type, int w, int h,
          int fmt, void *buffer, size_t size) {
    return cam_init(&g_cam_local, "Local", type, w, h, fmt, buffer, size);
}

HLE_FORCE("_ZN2nn4chat34InitializeRemoteCameraVideoStorageEPNS0_21RemoteCameraVideoTypeEiiiPvm",
          "the host's own picture stands in for the remote camera's", Result, h_chat_InitRemote, void *type, int w, int h, int fmt, void *buffer,
          size_t size) {
    return cam_init(&g_cam_remote, "Remote", type, w, h, fmt, buffer, size);
}

HLE_FORCE("_ZN2nn4chat25GetLocalCameraImageHandleEPKNS0_20LocalCameraVideoTypeEi", "the picture the local storage owns", uint32_t,
          h_chat_LocalHandle, const void *type, int index) {
    (void)type; (void)index;
    static int n;
    if (n++ < 8) LOG("[chat] GetLocalCameraImageHandle -> %#x (%ux%u)", g_cam_local.handle, g_cam_local.w, g_cam_local.h);
    return g_cam_local.handle;
}

HLE_FORCE("_ZN2nn4chat26GetRemoteCameraImageHandleEPKNS0_21RemoteCameraVideoTypeEi", "the picture the remote storage owns", uint32_t,
          h_chat_RemoteHandle, const void *type, int index) {
    (void)type; (void)index;
    static int n;
    if (n++ < 8) LOG("[chat] GetRemoteCameraImageHandle -> %#x (%ux%u)", g_cam_remote.handle, g_cam_remote.w, g_cam_remote.h);
    return g_cam_remote.handle;
}
