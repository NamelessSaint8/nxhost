// Android's arm64 assembly is ELF, so dav1d's symbols have no leading underscore. The vendored config (generated for the Apple build) defines PREFIX, which
// makes src/arm/asm.S emit "_dav1d_*"; this wrapper is found first on the include path and clears it. Everything else is the vendored configuration.
#pragma once
#include "../../third_party/dav1d/config/config.h"
#undef PREFIX
