// Diagnostic: intercept the two nn::os handle calls nn::chat::gsv::Initialize reaches, log what they ask, and answer success.
// The SDK's own implementation is deliberately not called: these symbols bind to an earlier module's definition, so calling the SDK's code from here
// could re-enter this stub. What it establishes is whether either call is the source of the "Result 0x20" abort -- if the run gets past that, one of
// the two returning non-zero was it.
#include "hle.h"
#include <stdbool.h>

HLE_FORCE("_ZN2nn2os17CloseNativeHandleEj", "diagnostic: logged, then answered success rather than forwarded", uint32_t, h_os_CloseHandleLog,
          uint32_t h) {
    static int n;
    if (n++ < 16) LOG("[oslog] CloseNativeHandle(%#x) -> success (diagnostic, the SDK's code is not called)", h);
    return 0;
}

HLE_FORCE("_ZN2nn2os33AttachReadableHandleToSystemEventEPNS0_15SystemEventTypeEjbNS0_14EventClearModeE",
          "diagnostic: logged, then answered success rather than forwarded", uint32_t, h_os_AttachLog, void *ev, uint32_t h, bool readable,
          uint32_t mode) {
    static int n;
    if (n++ < 16)
        LOG("[oslog] AttachReadableHandleToSystemEvent(ev %p, handle %#x, readable %d, mode %u) -> success (diagnostic)", ev, h, readable ? 1 : 0,
            mode);
    return 0;
}
