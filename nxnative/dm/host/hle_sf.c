// Services whose client a game links into its own main (nn::sf::hipc): Animal Crossing: New Horizons 3.0.3 carries the clients of olsc:u (cloud save data backup settings,
// main+0x404bc6c) and npns (push notifications). The SDK's client code connects through sm (an abort in sm::Initialize under InitializeHipcServiceResolution, from main+0x5b8198) and talks
// HIPC through svcSendSyncRequest; the host has neither. It hands out sessions of its own instead and answers each request in the message buffer, for the services listed in sf_served:
// success, the output data zeroed, no objects or handles. For olsc that reads as "backup off for every user", so the game leaves the settings alone (main+0x2809c8c asks per user and
// switches backup off where it is on). Any other service name is refused with a red line, as sm refuses a service that is not registered.
// auddmg:u is Ocarina of Time (Switch 2, SDK 22): its audio device manager is a service the SDK does not proxy, and the title aborts (Result 0xa99) when the
// connect comes back ResultNotRegistered. Zeroed answers read as "no audio device", which is what this host's silent sink already reports elsewhere.
// The SDK's own client functions are taken over where they reach the kernel (their calls inside sdk go through its PLT): the session manager's CreateNewSession runs natively on
// DuplicateSession, and ConvertToDomainImpl on QueryPointerBufferSize and ConvertSessionToDomain. DM_SF_TRACE=1 dumps every request.
// Message layout (Atmosphère / libnx): HIPC header {u16 type, counts of X / A / B / W descriptors; u32 data words, receive list, special header flag}, the special header and descriptors,
// then the data words, whose CMIF part starts 16-byte aligned to the buffer: in a domain session the domain header {u8 type, u8 objects, u16 size, u32 object, u32, u32 token} first,
// then {"SFCI", version, command, token} and the arguments. The response is the same with {u32 objects, 3 × u32} and {"SFCO", version, result, token}
#include "hle.h"
#include <pthread.h>
#include "sf_buffers.h"
int dm_guest_as_contains(uintptr_t a);   // hle_svc.c: the address lies in the reserved guest address block

#define SF_H0 0xd0000u   // session handles: outside the kernel handle table (0x1000 + slot, 4096 slots, hle_thread.c)
#define SF_MAX 64
static struct { char name[16]; int used, domain, anon; uint32_t handle; unsigned seen, next_obj; } g_sf[SF_MAX];
static pthread_mutex_t g_sf_mu = PTHREAD_MUTEX_INITIALIZER;
static const char *const sf_served[] = {"olsc:u", "chat:u", "auddmg:u", "audsmx:u"};
// Services whose command 0 opens an object (a manager or a user session the guest then sends on): the reply must carry a handle, not zeros.
static int sf_opens_object(const char *n) { return !strncmp(n, "auddmg:u", 8) || !strncmp(n, "audsmx:u", 8); }
#define SF_OBJ_H0 0x20000u    // object handles: outside the kernel table (0x1000+slot) and the host's session handles (0xd0000+slot)
static char g_obj_name[0x1000][10];   // handle - SF_OBJ_H0 → the service whose command 0 returned it, so an adopted session keeps its identity
static unsigned g_obj_n;              // objects handed out so far: a handle is never reused while its name is here (a title holds several at once)
static uint32_t sf_obj_new(const char *name) {
    while (g_obj_n < 0x1000 && g_obj_name[g_obj_n][0]) g_obj_n++;
    if (g_obj_n == 0x1000) die("sf: more than 4096 service objects");
    snprintf(g_obj_name[g_obj_n], sizeof g_obj_name[0], "%.8s", name);
    return SF_OBJ_H0 + g_obj_n++;
}

static int sf_slot(uint32_t h) {
    unsigned i = h - SF_H0;
    if (i < SF_MAX && g_sf[i].used && !g_sf[i].anon && g_sf[i].handle == h) return (int)i;   // the handles the host issued: slot = handle - SF_H0
    for (unsigned k = 0; k < SF_MAX; k++) if (g_sf[k].used && g_sf[k].anon && g_sf[k].handle == h) return (int)k;   // adopted ones, by the handle they came in on
    return -1;
}
// A handle the host never issued: the guest's own (the SDK builds requests against client objects whose +4 is a kernel handle, and on Horizon that is a
// small number). The host serves every service generically, so it answers this one under a name of its own rather than refusing it.
static int sf_adopt(uint32_t h) {
    pthread_mutex_lock(&g_sf_mu);
    unsigned i = 0; while (i < SF_MAX && g_sf[i].used) i++;
    if (i == SF_MAX) { pthread_mutex_unlock(&g_sf_mu); return -1; }
    if (h >= SF_OBJ_H0 && h < SF_OBJ_H0 + 0x1000 && g_obj_name[h - SF_OBJ_H0][0])
        snprintf(g_sf[i].name, sizeof g_sf[i].name, "%.8s-mgr", g_obj_name[h - SF_OBJ_H0]);   // an object a service handed out keeps its origin
    else snprintf(g_sf[i].name, sizeof g_sf[i].name, "svc:%#x", h);
    g_sf[i].used = 1; g_sf[i].domain = 0; g_sf[i].anon = 1; g_sf[i].handle = h;
    g_sf[i].seen = 0; g_sf[i].next_obj = 2;
    pthread_mutex_unlock(&g_sf_mu);
    return (int)i;
}
static uint32_t sf_new(const char *name, int domain) {
    pthread_mutex_lock(&g_sf_mu);
    unsigned i = 0; while (i < SF_MAX && g_sf[i].used) i++;
    if (i == SF_MAX) die("sf: more than %d host service sessions", SF_MAX);
    strlcpy(g_sf[i].name, name, sizeof g_sf[i].name); g_sf[i].used = 1; g_sf[i].domain = domain; g_sf[i].anon = 0;
    g_sf[i].handle = SF_H0 + i; g_sf[i].seen = 0; g_sf[i].next_obj = 2;
    pthread_mutex_unlock(&g_sf_mu);
    return SF_H0 + i;
}

HLE_FORCE("_ZN2nn2sf4hipc31InitializeHipcServiceResolutionEv", "service name resolution (connects to sm); the host resolves the names it serves itself", Result, h_sf_InitRes, void) { return RES_OK; }
HLE_FORCE("_ZN2nn2sf4hipc29FinalizeHipcServiceResolutionEv", "service name resolution (sm)", void, h_sf_FinRes, void) {}
HLE_FORCE("_ZN2nn2sf4hipc20ConnectToHipcServiceEPNS_3svc6HandleEPKc", "connect to a service through sm → a host session for the services the host serves", Result, h_sf_Connect,
          uint32_t *out, const char *name) {
    for (size_t k = 0; k < sizeof sf_served / sizeof *sf_served; k++)
        if (!strncmp(name, sf_served[k], 8)) { *out = sf_new(sf_served[k], 0); LOG("sf: %s → host session %#x (every request succeeds with zeroed output)", sf_served[k], *out); return RES_OK; }
    LOG("[RED] sf: the game connects to service %.8s itself, which the host does not serve", name);
    return 0xe15u;   // sm ResultNotRegistered
}
HLE_FORCE("_ZN2nn2sf4hipc24CloseClientSessionHandleENS_3svc6HandleE", "close a session (kernel handle) → the host session", void, h_sf_Close, uint32_t h) {
    int i = sf_slot(h);
    if (i < 0) { LOG("[RED] sf: CloseClientSessionHandle on %#x, not a host session", h); return; }
    pthread_mutex_lock(&g_sf_mu); g_sf[i].used = 0; pthread_mutex_unlock(&g_sf_mu);
}
// The in-process server writes client output lists directly, with a 4 KiB
// pointer-transfer budget. Reporting zero rejects mandatory HipcPointer outputs
// in the SDK before any request is sent (result 0x11a0b).
// Control requests: the domain conversion makes the session's object 1, a duplicate
// is a new session to the same object
HLE_FORCE("_ZN2nn2sf4hipc6client22QueryPointerBufferSizeEPtNS_3svc6HandleE", "control request: in-process server pointer-transfer budget", Result, h_sf_PtrBuf, uint16_t *out, uint32_t h) {
    int i=sf_slot(h);
    if(i<0 && h>=SF_OBJ_H0 && h<SF_OBJ_H0+0x1000 && g_obj_name[h-SF_OBJ_H0][0])i=sf_adopt(h);
    if (i < 0) { LOG("[RED] sf: QueryPointerBufferSize on %#x, not a host session", h); return RES_FAIL; }
    *out = 4096; return RES_OK;
}
HLE_FORCE("_ZN2nn2sf4hipc6client22ConvertSessionToDomainEPNS0_4cmif18CmifDomainObjectIdENS_3svc6HandleE", "control request: convert a session to a domain → the host session's object 1", Result, h_sf_ToDomain,
          uint32_t *out, uint32_t h) {
    int i = sf_slot(h);
    if (i < 0) { LOG("[RED] sf: ConvertSessionToDomain on %#x, not a host session", h); return RES_FAIL; }
    g_sf[i].domain = 1; *out = 1; return RES_OK;
}
HLE_FORCE("_ZN2nn2sf4hipc6client16DuplicateSessionEPNS_3svc6HandleES4_", "control request: clone a session → a new host session to the same service", Result, h_sf_Dup, uint32_t *out, uint32_t h) {
    int i = sf_slot(h);
    if (i < 0) { LOG("[RED] sf: DuplicateSession on %#x, not a host session", h); return RES_FAIL; }
    *out = sf_new(g_sf[i].name, g_sf[i].domain); return RES_OK;
}
HLE_FORCE("_ZN2nn2sf4hipc6client18DuplicateSessionExEPNS_3svc6HandleES4_j", "control request: clone a session (with a tag) → a new host session to the same service", Result, h_sf_DupEx,
          uint32_t *out, uint32_t h, unsigned tag) { (void)tag; return h_sf_Dup(out, h); }

// Shared with svc 0x21: a title that sends through the syscall instead of the API names the same sessions, and dm_sf_new mints one for a service
// the host answers without a name of its own.
static int sf_output_valid(uint64_t address,uint64_t bytes,void *context) {
    (void)context;
    int ok=bytes && bytes-1<=UINT64_MAX-address && dm_guest_as_contains((uintptr_t)address) && dm_guest_as_contains((uintptr_t)(address+bytes-1));
    // The initial guest main also runs on the calling native thread's stack.
    // Admit active caller stack storage, never arbitrary writable host memory.
    uintptr_t active=(uintptr_t)&ok,top=(uintptr_t)pthread_get_stackaddr_np(pthread_self());
    if(!ok && bytes && address>=active && address<top && bytes<=top-address)ok=1;
    if(!ok)LOG("[sf] rejected output address=%#llx bytes=%#llx",(unsigned long long)address,(unsigned long long)bytes);
    return ok;
}
static Result sf_send(uint32_t h, uint32_t *m, uint64_t size) {
    if(!m || size<8)return 0xe401u;
    int i = sf_slot(h);
    if (i < 0) {
        if (size < 0x40 || (i = sf_adopt(h)) < 0) { LOG("[RED] sf: SendSyncRequest on %#x (%llu bytes) with no room to serve it", h, (unsigned long long)size); return 0xe401u; }
        module_t *mod = module_of(__builtin_return_address(0));
        LOG("sf: SendSyncRequest on %#x, a handle the host never issued -- served as %s (from %s+%#llx, header %08x %08x)", h, g_sf[i].name,
            mod ? mod->name : "?", mod ? (unsigned long long)((uintptr_t)__builtin_return_address(0) - (uintptr_t)mod->base) : 0, m[0], m[1]);
    }
    uint8_t *base = (uint8_t *)m;
    sf_out_buffer output[28];int noutput=sf_output_buffers(m,(size_t)size,output);
    if(noutput<0){LOG("[RED] sf: invalid output descriptor layout");return 0xe401u;}
    unsigned type = m[0] & 0xffff, nx = m[0] >> 16 & 15, na = m[0] >> 20 & 15, nb = m[0] >> 24 & 15;
    if(type==2)return RES_OK; // Close has no CMIF body.
    unsigned nabw = na + nb + (m[0] >> 28 & 15), ndw = m[1] & 0x3ff;
    uint32_t *p = m + 2;
    if (m[1] >> 31) { uint32_t sh = *p++; p += (sh & 1 ? 2 : 0) + (sh >> 1 & 15) + (sh >> 5 & 15); }   // special header: process ID, copy and move handles
    p += nx * 2 + nabw * 3;
    size_t data = (size_t)((uint8_t *)p - base), cm = (data + 15) & ~(size_t)15;
    if(cm+16>size)return 0xe401u;
    // An adopted session's domain state is not known: the message says it (a domain request puts its header before the CMIF part)
    int dom = g_sf[i].anon ? (cm+32<=size && *(uint32_t *)(base + cm) != 0x49434653 && *(uint32_t *)(base + cm + 16) == 0x49434653)
                          : (g_sf[i].domain && (type == 4 || type == 6));
    unsigned dtype = dom ? base[cm] : 1, obj = dom ? *(uint32_t *)(base + cm + 4) : 0;
    size_t hin = cm + (dom ? 16 : 0);
    if (hin + 16 > size || data + ndw * 4 > size) { LOG("[RED] sf: %s: request of %u data words does not fit %llu bytes", g_sf[i].name, ndw, (unsigned long long)size); return 0xe401u; }
    uint32_t magic = *(uint32_t *)(base + hin), ver = *(uint32_t *)(base + hin + 4), cmd = *(uint32_t *)(base + hin + 8);
    static int trace = -1; if (trace < 0) trace = getenv("DM_SF_TRACE") && atoi(getenv("DM_SF_TRACE"));
    if (trace) { char hx[3 * 0x80 + 1] = ""; for (unsigned k = 0; k < 0x80 && k < size; k++) snprintf(hx + 3 * k, 4, "%02x ", base[k]); LOG("sf: %s request: %s", g_sf[i].name, hx); }
    // HIPC type 2 is Close, not a request: the guest is done with the session and expects success with no reply body. Refusing it left the SDK's client
    // dereferencing a null result (Ocarina of Time's auddmg:u: SIGSEGV at sdk+0x2ace08 after "message type 2 not served"). The session itself stays until
    // the guest closes the kernel handle (CloseClientSessionHandle), which is the call that frees the slot.
    if (type == 2) return RES_OK;
    if (type != 4 && type != 6) { LOG("[RED] sf: %s: HIPC message type %u not served", g_sf[i].name, type); return 0xe401u; }
    if (dtype == 2) { memset(base, 0, 16); return RES_OK; }   // a domain object closed: nothing to answer
    if (magic != 0x49434653) { LOG("[RED] sf: %s: request without SFCI (%#x)", g_sf[i].name, magic); return 0xe401u; }
    if(!sf_zero_outputs(output,noutput,sf_output_valid,NULL)){LOG("[RED] sf: %s: output buffer is outside the guest address space",g_sf[i].name);return 0xe401u;}
    // Keep the decoded client output before the reply replaces its descriptors.
    uint64_t baddr=noutput?output[0].address:0,bsize=noutput?output[0].size:0;
    unsigned key = (obj & 0xff) << 16 | (cmd & 0xffff);   // log each object / command once
    pthread_mutex_lock(&g_sf_mu); int first = g_sf[i].seen != key; g_sf[i].seen = key; pthread_mutex_unlock(&g_sf_mu);
    if (first || trace) LOG("sf: %s object %u command %u (%u data words in): success, zeroed output", g_sf[i].name, obj, cmd, ndw);
    // The response: no special header and no descriptors, so the data words start at +8 and the CMIF part at +0x10; everything after the headers up to the buffer's end reads as zero
    size_t end = size < 0x1000 ? size : 0x1000;
    memset(base, 0, end);
    // auddmg:u command 0 is OpenVirtualDeviceManager and hands the client an object: a move handle the guest then sends its manager requests on. A reply with
    // no handle leaves the client's object null and it dereferences it (SIGSEGV at sdk+0x2abf00, inside its abort path). The handle is outside the kernel
    // handle table and the host's session handles, and sf_adopt serves it generically once the client sends on it.
    if (!g_sf[i].anon && sf_opens_object(g_sf[i].name) && cmd == 0) {   // the service session opens the object; the object's own command 0 is its first request
        // A domain session (audsmx:u's user session is one) returns a domain object: the out-object count in the domain header, then its id in
        // the first CMIF output word. A move handle here is a different reply shape and leaves the client's object null.
        if (dom) {
            uint32_t id = g_sf[i].next_obj++;
            m[1] = (uint32_t)((end - 8) / 4 < 0x3ff ? (end - 8) / 4 : 0x3ff);
            *(uint32_t *)(base + 0x10) = 1;
            uint32_t *oh = (uint32_t *)(base + 0x20); oh[0] = 0x4f434653; oh[1] = ver; oh[2] = RES_OK; oh[3] = 0; oh[4] = id;
            LOG("sf: %.8s command 0: domain object %u", g_sf[i].name, id);
            return RES_OK;
        }
        uint32_t handle = sf_obj_new(g_sf[i].name);
        m[1] = 0x80000000u | (uint32_t)((end - 8) / 4 < 0x3ff ? (end - 8) / 4 : 0x3ff);   // a special header follows
        uint32_t *sp = (uint32_t *)(base + 8);
        sp[0] = 1u << 5;   // one move handle, no process id
        sp[1] = handle;
        uint32_t *oh = (uint32_t *)(base + 0x10); oh[0] = 0x4f434653; oh[1] = ver; oh[2] = RES_OK; oh[3] = 0;
        LOG("sf: %.8s command 0: object as handle %#x", g_sf[i].name, handle);
        return RES_OK;
    }
    m[1] = (uint32_t)((end - 8) / 4 < 0x3ff ? (end - 8) / 4 : 0x3ff);
    size_t out = 0x10 + (dom ? 16 : 0);
    uint32_t *o = (uint32_t *)(base + out); o[0] = 0x4f434653; o[1] = ver; o[2] = RES_OK; o[3] = 0;   // "SFCO"; a domain's out-object count before it stays 0
    // auddmg:u's manager: answer into the caller's buffer. Command 0 lists virtual output devices (a count, then 0x100 bytes of name each); the rest are
    // not implemented yet and leave the zeroed reply, which is what the title is expected to trip over next.
    if (bsize && baddr && !strncmp(g_sf[i].name, "auddmg:u", 8)) {
        int in_as=sf_output_valid(baddr,bsize,NULL);
        LOG("sf: auddmg:u manager command %u: output %#llx+%#llx%s",cmd,(unsigned long long)baddr,(unsigned long long)bsize,in_as?"":" (not written)");
        if (in_as && cmd == 0 && bsize >= 0x100) {
            static const char name[] = "AudioVirtualOutput0";
            size_t n = bsize < 0x200 ? (size_t)bsize : 0x200;
            uint8_t *dst = (uint8_t *)(uintptr_t)baddr;
            memset(dst, 0, n); memcpy(dst, name, sizeof name - 1);
            o[4] = 1;   // one virtual output device
        }
    }
    // Probe: nn::chat::detail::InitializeUserService dereferences the object this call returns, so a zeroed reply leaves it null
    // (SIGSEGV at sdk+0x6bc400, addr 0). Answer with an object id instead, and count it in the domain header when the session is one.
    if (!strncmp(g_sf[i].name, "chat:u", 8) && cmd == 0) {
        if (dom) *(uint32_t *)(base + 0x10) = 1;
        o[4] = 1;
        LOG("sf: chat:u command 0: out object 1 (probe, was a zeroed reply)");
    }
    return RES_OK;
}

HLE_FORCE("_ZN2nn2sf4hipc15SendSyncRequestENS_3svc6HandleEPvm", "send a request on a session (svcSendSyncRequest) → answered by the host for its sessions",
          Result, h_sf_Send, uint32_t h, uint32_t *m, uint64_t size) {
    return sf_send(h, m, size);
}
Result dm_sf_send(uint32_t h, void *m, uint64_t size) { return sf_send(h, (uint32_t *)m, size); }
uint32_t dm_sf_new(const char *name) { return sf_new(name, 0); }
