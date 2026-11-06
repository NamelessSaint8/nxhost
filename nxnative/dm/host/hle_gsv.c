// nn::gsv: the Switch 2 graphics server (the SDK's "ounce" spec). Nothing in sdk boots it — nn::gsv::BootWithTransferMemory and
// nn::gsv::BootWithRemoteMemory exist but are never called — so on hardware the system has already booted the server and a title only reads it back:
// IsInitialized tests the byte at 0xee1048, GetGraphicsResourceUserId returns the u64 at 0xee1058, and GetUserSession returns the static session at
// 0xee1050 only while that u64 is non-zero. The host presents a booted session instead of booting one: the three accessors answer from this block.
// The session's first field is the SdkMutexType its callers lock. nn::chat::gsv::Initialize locks it and then reads +4, which must be non-zero (it feeds
// the stream-generation generator). This is a stand-in for the server, not the server: NVN2 submits through gsv, so a title that draws needs the real one.
#include "hle.h"
#include <stdbool.h>

static struct {
    uint32_t mutex;          // SdkMutexType: 0 = unlocked; the SDK's own Lock/Unlock manage this word
    uint32_t session;        // the session handle at +4: the camera path sends its requests on it (main+0xcded98), chat reads it as a non-zero id
    uint64_t resource_user;  // what GetGraphicsResourceUserId returns, and the SDK's own validity test
    uint64_t pad[6];
} g_gsv_session = {.resource_user = 1};

// The handle at +4 is not a number the title invented: it is the session the caller sends requests on, so it has to name one of the host's own
// (hle_sf.c) rather than a small integer the sf layer would refuse.
static void *gsv_session(void) {
    if (!g_gsv_session.session) g_gsv_session.session = dm_sf_new("gsv:u");
    return &g_gsv_session;
}

HLE_FORCE("_ZN2nn3gsv13IsInitializedEv", "the system boots the graphics server before a title runs; the host reports one", bool, h_gsv_IsInit, void) {
    return true;
}
HLE_FORCE("_ZN2nn3gsv14GetUserSessionEv", "the booted session; +0 is its mutex, +4 the handle its callers send on", void *, h_gsv_Session,
          void) {
    return gsv_session();
}
// nn::gs: the Switch 2 graphics system a title talks to for native images and sync handles. On hardware the system initialises it before the title runs
// -- there is no nn::gs::Initialize in sdk that a title calls (the symbol is a 4-byte stub) -- so the guard at sdk+0x46e890 only checks a flag at
// 0xedb828 that nothing in the title can set. The host reports the system initialised, which is what a console with a booted graphics server looks like.
HLE_FORCE("_ZN2nn2gs3sdk30CheckGraphicsSystemInitializedEPKcm", "the graphics system is the host's: report it initialised", void, h_gs_CheckInit,
          const char *who, uint64_t id) {
    static int n;
    if (n++ < 8) LOG("[gs] CheckGraphicsSystemInitialized(%s, %#llx) -> initialised (the host provides it)", who ? who : "?", (unsigned long long)id);
}

HLE_FORCE("_ZN2nn3gsv25GetGraphicsResourceUserIdEv", "the graphics resource user of the booted session", uint64_t, h_gsv_ResourceUser, void) {
    return g_gsv_session.resource_user;
}
