// Keep the platform ELF declarations separate from the guest loader's ELF
// declarations. Profiling must not count a nearby driver library as host code.
#define _GNU_SOURCE
#include <link.h>
#include <stdint.h>
typedef struct {uintptr_t base,end;} text_extent;
static int text_extent_visit(struct dl_phdr_info *info,size_t size,void *opaque){
    (void)size;text_extent *extent=opaque;if(info->dlpi_addr!=extent->base)return 0;
    for(unsigned i=0;i<info->dlpi_phnum;i++){
        const ElfW(Phdr) *ph=&info->dlpi_phdr[i];
        if(ph->p_type==PT_LOAD && (ph->p_flags&PF_X)){
            uintptr_t end=info->dlpi_addr+ph->p_vaddr+ph->p_memsz;if(end>extent->end)extent->end=end;
        }
    }
    return 1;
}
uintptr_t vk_prof_text_end(uintptr_t base){text_extent extent={base,base};dl_iterate_phdr(text_extent_visit,&extent);return extent.end;}
