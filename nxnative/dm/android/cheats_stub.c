// Android port: the cheats module (dm/host/hle_cheats.c, upstream's GCD- and Mach-alias-based implementation) is not built on Android yet (M0 excludes it; a pthread
// and compat-shim port is future work). The interface stubs out: no cheat file loads, the menu shows none, and the per-present apply is a no-op. dm_cheats_exit is
// called from hle_lifecycle.c (dm_cheats_keys lives in hle_hid.c).
#include "dm.h"

void dm_cheats_init(void) {}
void dm_cheats_present(void) {}
int dm_cheats_found(void) { return 0; }
int dm_cheats_ncheats(void) { return 0; }
const char *dm_cheats_build(void) { return ""; }
const char *dm_cheats_dir_path(void) { return ""; }
int dm_cheats_nothers(void) { return 0; }
const char *dm_cheats_other(int i) { (void)i; return ""; }
const char *dm_cheat_name_at(int i) { (void)i; return ""; }
const char *dm_cheat_why_at(int i) { (void)i; return ""; }
int dm_cheat_kind_at(int i) { (void)i; return 0; }
int dm_cheat_on_at(int i) { (void)i; return 0; }
void dm_cheat_toggle(int i) { (void)i; }
void dm_cheats_reload(void) {}
int dm_cheat_flags_at(int i) { (void)i; return 0; }
const char *dm_cheat_section_at(int i) { (void)i; return ""; }
const char *dm_cheat_note_at(int i) { (void)i; return ""; }
const char *dm_cheat_type_at(int i) { (void)i; return ""; }
int dm_cheat_pair_at(int i) { (void)i; return -1; }
int dm_cheat_preview(int i, char *out, size_t cap) { (void)i; (void)out; (void)cap; return 0; }
int dm_cheat_value_get(int i, char *out, size_t cap) { (void)i; (void)out; (void)cap; return 0; }
int dm_cheat_value_set(int i, const char *text) { (void)i; (void)text; return -1; }
const char *dm_cheat_value_bounds(int i) { (void)i; return ""; }
int dm_cheats_master(void) { return 0; }
void dm_cheats_master_set(int on) { (void)on; }
int dm_cheats_safe(void) { return 0; }
void dm_cheats_safe_restore(void) {}
const char *dm_cheats_report(void) { return "cheats are not built into the Android host yet"; }
const char *dm_cheats_version(void) { return ""; }
const char *dm_cheats_other_version(int i) { (void)i; return ""; }
int dm_cheats_nskipped(void) { return 0; }
const char *dm_cheats_skipped_name(int i) { (void)i; return ""; }
const char *dm_cheats_skipped_why(int i) { (void)i; return ""; }
int dm_cheats_nsources(void) { return 0; }
const char *dm_cheats_source(int i) { (void)i; return ""; }
void dm_cheats_exit(void) {}
