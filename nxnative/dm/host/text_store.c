// A guest store into a module's own read-only page is corruption, not self-modification.
// The modules' writable segments (.data, .bss) are mapped writable, so a store can only fault inside a
// module when the address is code: a pointer that should hold a data address holds a code address
// instead. Skyrim's vertex/texture interpreter writes a 2-byte packed value to `[base + 24 * index]`,
// where `base` comes from a structure field; on the way back to the tavern that field held `lr`, so the
// store landed on the return address + 4 and the process died over two bytes of its own instructions.
// Report the first sites (pc, target, the instruction, the registers that address it) and drop the
// store: nothing can read bytes written into code nobody jumps to, and the run continues.
#include "dm.h"
#include "dm_uc.h"
#include <stdatomic.h>
#include <stdio.h>
#define MAX_SITES 16
static uint64_t g_site_pc[MAX_SITES], g_site_at[MAX_SITES];
static _Atomic int g_nsite;
static _Atomic uint64_t g_dropped;
static int site_index(uint64_t pc, uint64_t at) {   // -1 when this site is new and there is room for it
    int n = atomic_load(&g_nsite);
    for (int i = 0; i < n; i++) if (g_site_pc[i] == pc && g_site_at[i] == at) return i;
    if (n >= MAX_SITES) return MAX_SITES;          // full: no more reporting, the count still grows
    g_site_pc[n] = pc; g_site_at[n] = at; atomic_store(&g_nsite, n + 1);
    return -1;
}
int text_store_fault(void *addr, int is_write, void *ucv) {
    uint64_t at = (uint64_t)addr;
    if (!is_write) return 0;
    module_t *m = module_of((const void *)at);
    if (!m) return 0;
    ucontext_t *uc = ucv;
    uint64_t pc = DM_UC_SS(uc)->__pc, lr = DM_UC_SS(uc)->__lr;
    uint32_t insn = *(const uint32_t *)(uintptr_t)pc;
    uint64_t n = atomic_fetch_add(&g_dropped, 1) + 1;
    int i = site_index(pc, at);
    if (i < -1) { if (n <= 8 || !(n & 255)) LOG("[RED] guest store into read-only text: %llu in all, new sites are no longer reported", (unsigned long long)n); }
    else if (i >= 0) { if (n <= 8 || !(n & 255)) LOG("[RED] guest store into %s+%#llx again (%llu in all)", m->name, (unsigned long long)(at - (uint64_t)(uintptr_t)m->base), (unsigned long long)n); }
    else {
        module_t *pm = module_of((const void *)pc);
        char where[64];
        if (pm) snprintf(where, sizeof where, "%s+%#llx", pm->name, (unsigned long long)(pc - (uint64_t)(uintptr_t)pm->base));
        else snprintf(where, sizeof where, "the host %#llx", (unsigned long long)pc);
        LOG("[RED] a guest store into read-only text was dropped: %s+%#llx from %s by the instruction %08x (x1 %#llx x2 %#llx x19 %#llx x20 %#llx lr %#llx)",
            m->name, (unsigned long long)(at - (uint64_t)(uintptr_t)m->base), where, insn,
            (unsigned long long)DM_UC_SS(uc)->__x[1], (unsigned long long)DM_UC_SS(uc)->__x[2],
            (unsigned long long)DM_UC_SS(uc)->__x[19], (unsigned long long)DM_UC_SS(uc)->__x[20], (unsigned long long)lr);
    }
    DM_UC_SS(uc)->__pc = pc + 4;   // Every A64 store is one instruction wide; dropping it leaves the page as it was
    return 1;
}
void text_store_install(void) { dm_fault_hook_register(text_store_fault); }
