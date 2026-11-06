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
          "initialises the guest SystemEventType from the handle rather than forwarding", uint32_t, h_os_AttachLog, void *ev, uint32_t h,
          bool readable, uint32_t mode) {
    static int n;
    if (n++ < 16)
        LOG("[oslog] AttachReadableHandleToSystemEvent(ev %p, handle %#x, readable %d, mode %u)", ev, h, readable ? 1 : 0, mode);
    // The layout is the SDK's own: nn::os::TryWaitSystemEvent dispatches on a type byte at +0x28 (1 = Event, 2 = InterProcessEvent, anything else
    // aborts), and nn::os::TryWaitEvent reads the state at +0x10, the autoclear flag at +0x12 and locks a mutex at +0x1c. Leaving these as the guest
    // left them is what made chat abort in TryWaitSystemEvent.
    if (ev) {
        uint8_t *e = (uint8_t *)ev;
        *(uint32_t *)(e + 0x1c) = 0;                      // the lock TryWaitEvent takes
        *(uint8_t *)(e + 0x10) = readable ? 1 : 0;        // signalled when the handle is readable; not signalled otherwise
        *(uint8_t *)(e + 0x12) = mode == 0 ? 1 : 0;       // EventClearMode::AutoClear is 0
        *(uint8_t *)(e + 0x28) = 1;                       // SystemEventType::Type::Event
    }
    return 0;
}
