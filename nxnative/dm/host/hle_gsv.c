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
    uint32_t id;             // read at +4 by nn::chat::gsv; any non-zero value
    uint64_t resource_user;  // what GetGraphicsResourceUserId returns, and the SDK's own validity test
    uint64_t pad[6];
} g_gsv_session = {.id = 1, .resource_user = 1};

HLE_FORCE("_ZN2nn3gsv13IsInitializedEv", "the system boots the graphics server before a title runs; the host reports one", bool, h_gsv_IsInit, void) {
    return true;
}
HLE_FORCE("_ZN2nn3gsv14GetUserSessionEv", "the booted session; +0 is its mutex, +4 the id chat's stream generation reads", void *, h_gsv_Session,
          void) {
    return &g_gsv_session;
}
HLE_FORCE("_ZN2nn3gsv25GetGraphicsResourceUserIdEv", "the graphics resource user of the booted session", uint64_t, h_gsv_ResourceUser, void) {
    return g_gsv_session.resource_user;
}
