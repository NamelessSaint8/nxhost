# Texture sub-module unit tests (seconds): make run
CFLAGS = -O2 -g -Wall -Wextra
# SAN: extra compiler flags, O: the output folder (with a trailing slash) of a sanitizer or coverage build (make asan and make coverage below set both); both empty otherwise
SAN ?=
O ?=
CLANG = clang $(SAN)
$(O)t_tex: t_tex.c ../nvn_deswizzle.c ../nvn_deswizzle.h ../../nvn/nvn_tex.c ../../nvn/nvn_tex.h
	$(CLANG) $(CFLAGS) -o $@ t_tex.c ../nvn_deswizzle.c ../../nvn/nvn_tex.c -lm
$(O)t_fmt_mtl: t_fmt_mtl.m ../nvn_fmt_mtl.c ../nvn_fmt_mtl.h
	$(CLANG) $(CFLAGS) -fobjc-arc -o $@ t_fmt_mtl.m ../nvn_fmt_mtl.c -framework Metal -framework Foundation
$(O)t_bc: t_bc.c ../nvn_bc.c ../nvn_bc.h
	$(CLANG) $(CFLAGS) -o $@ t_bc.c ../nvn_bc.c
run: t_tex t_fmt_mtl t_bc
	./t_fmt_mtl && ./t_tex && ./t_bc
.PHONY: run
# ASan and UBSan (../../../sanitizers/sanitizers.mk): the CPU tests t_tex and t_bc, built into asan/ (t_fmt_mtl creates Metal textures and stays local)
include ../../../sanitizers/sanitizers.mk
.PHONY: asan
asan:
	@$(call san_fresh,asan,$(ASAN_FLAGS))
	$(MAKE) O=asan/ SAN="$(ASAN_FLAGS)" asan/t_tex asan/t_bc
	$(ASAN_ENV) ./asan/t_tex && $(ASAN_ENV) ./asan/t_bc
# Line coverage (../../../sanitizers/coverage.mk): t_tex and t_bc built into cov/ with COV_FLAGS and run; writes cov/coverage.lcov
include ../../../sanitizers/coverage.mk
.PHONY: coverage
coverage:
	@$(call san_fresh,cov,$(COV_FLAGS))
	rm -rf cov/prof
	$(MAKE) O=cov/ SAN="$(COV_FLAGS)" cov/t_tex cov/t_bc
	-LLVM_PROFILE_FILE="$(call cov_profile,cov)" ./cov/t_tex
	-LLVM_PROFILE_FILE="$(call cov_profile,cov)" ./cov/t_bc
	@$(call cov_export,cov)
