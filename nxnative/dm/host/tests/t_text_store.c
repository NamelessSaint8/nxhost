// A guest store into a module's read-only text: dropped and reported (host/text_store.c).
// What the rule is for: the modules' writable segments are mapped writable, so a store can only fault
// inside a module when the address is code -- a pointer that should hold a data address holds a code
// address (Skyrim wrote a 2-byte value to `lr + 4`). Nobody can read bytes written into code, so the
// two bytes are not worth the process: the store is dropped and the run continues.
#include "dm.h"
#include "dm_uc.h"
#include <stdio.h>
#include <string.h>
#include <sys/mman.h>

static int failures;
#define EXPECT(what, want, got) do { long long w_ = (long long)(want), g_ = (long long)(got); \
    if (w_ == g_) printf("ok   %s\n", what); else { printf("FAIL %s: want %lld, got %lld\n", what, w_, g_); failures++; } } while (0)

static module_t modules[2];   // Two real mappings: the hook reads the instruction at the faulting pc
module_t *module_of(const void *p) {   // Stub for loader.c, which this test does not link
    for (int i = 0; i < 2; i++)
        if ((const uint8_t *)p >= modules[i].base && (const uint8_t *)p < modules[i].base + modules[i].size) return &modules[i];
    return NULL;
}
static int (*g_registered)(void *, int, void *);   // Stub for crash.c, which owns the fault dispatch
void dm_fault_hook_register(int (*fn)(void *addr, int is_write, void *uc)) { g_registered = fn; }
static ucontext_t uc;
#if defined(__APPLE__)
static _STRUCT_MCONTEXT64 mc;   // Darwin keeps the registers behind a pointer that a zeroed context does not have
#endif
static void at(uint64_t pc, uint64_t x1, uint64_t x2) {
    memset(&uc, 0, sizeof uc);
#if defined(__APPLE__)
    uc.uc_mcontext = &mc; memset(&mc, 0, sizeof mc);
#endif
    DM_UC_SS(&uc)->__pc = pc; DM_UC_SS(&uc)->__x[1] = x1; DM_UC_SS(&uc)->__x[2] = x2; DM_UC_SS(&uc)->__lr = x1;
}
static uint64_t map_module(const char *name, size_t size) {
    uint8_t *b = mmap(NULL, size, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANON, -1, 0);
    if (b == MAP_FAILED) { perror("mmap"); exit(2); }
    memset(b, 0, size);
    module_t *m = &modules[modules[0].base ? 1 : 0];
    m->base = b; m->size = size;
    snprintf(m->name, sizeof m->name, "%s", name);
    return (uint64_t)(uintptr_t)b;
}
int main(void) {
    uint64_t main_base = map_module("main", 0x10000), sdk_base = map_module("sdk", 0x10000);
    uint32_t *writer = (uint32_t *)(uintptr_t)(main_base + 0x1000);
    *writer = 0x79000020;   // strh w0, [x1] -- what the site in Skyrim's interpreter is
    text_store_install();
    EXPECT("the rule is registered with the fault dispatch", 1, g_registered == text_store_fault);
    // The crash this was found on: an interpreter's 16-bit store lands on the return address + 4
    uint64_t code = main_base + 0x2000, pc = (uint64_t)(uintptr_t)writer;
    at(pc, main_base + 0x100, 4);
    EXPECT("a store into a module's code is handled", 1, text_store_fault((void *)code, 1, &uc));
    EXPECT("its instruction is dropped (pc moves on by one)", (long long)(pc + 4), (long long)DM_UC_SS(&uc)->__pc);
    at(pc, main_base + 0x100, 4);
    EXPECT("the same site is still handled", 1, text_store_fault((void *)code, 1, &uc));
    at(pc, main_base + 0x100, 4);
    EXPECT("a read fault is not this rule's", 0, text_store_fault((void *)code, 0, &uc));
    EXPECT("a read fault leaves the pc alone", (long long)pc, (long long)DM_UC_SS(&uc)->__pc);
    at(pc, 0, 0);
    EXPECT("a store outside every module is not this rule's", 0, text_store_fault((void *)(uintptr_t)(sdk_base + 0x20000), 1, &uc));
    at(pc, 0, 0);
    EXPECT("a store into another module's code is handled too", 1, text_store_fault((void *)(uintptr_t)(sdk_base + 0x800), 1, &uc));
    // More distinct sites than the table holds: reported as such, still handled
    int handled = 0;
    for (int i = 0; i < 40; i++) { at(pc, 0, 0); handled += text_store_fault((void *)(uintptr_t)(main_base + 0x4000 + 4 * i), 1, &uc) == 1; }
    EXPECT("every distinct site past the table is dropped too", 40, handled);
    printf(failures ? "\n%d FAILED\n" : "\nall passed\n", failures);
    return failures != 0;
}
