// Optional disk-backed canonical CPU storage. GPU_NO_ACCESS pools cannot own
// direct GPU buffers. A regular shared file mapping lets the kernel write back
// and reclaim their pages without losing source texels. Preserve the virtual
// address and every byte; the mapping owns the unlinked file after fd close.
#include <fcntl.h>
static int pool_cpu_file(void *memory,uint64_t size) {
    const char *option=getenv("DM_VK_CPU_BACKING"),*directory=getenv("DM_TEMP");
    if(!option || strcmp(option,"file") || size<(1u<<20))return 0;
    size_t page=(size_t)getpagesize();if(((uintptr_t)memory|size)&(page-1))return 0;
    if(!directory || !*directory)die("[RED] file-backed CPU pools require a private DM_TEMP directory");
    char path[1200];if(snprintf(path,sizeof path,"%s/nvn-cpu-XXXXXX",directory)>=(int)sizeof path)die("[RED] CPU backing directory path is too long");
    struct timespec begin,end;clock_gettime(CLOCK_MONOTONIC,&begin);
    int fd=mkstemp(path);if(fd<0)die("[RED] create CPU backing file: %s",strerror(errno));
    if(unlink(path)){int error=errno;close(fd);die("[RED] unlink private CPU backing file: %s",strerror(error));}
    fcntl(fd,F_SETFD,FD_CLOEXEC);
    for(uint64_t offset=0;offset<size;){size_t length=size-offset>(1u<<20)?(1u<<20):(size_t)(size-offset);
        ssize_t written=pwrite(fd,(uint8_t *)memory+offset,length,(off_t)offset);
        if(written<0 && errno==EINTR)continue;
        if(written<=0){int error=written<0?errno:ENOSPC;close(fd);die("[RED] write canonical CPU backing: %s",strerror(error));}
        offset+=(uint64_t)written;
    }
    if(fdatasync(fd)){int error=errno;close(fd);die("[RED] sync canonical CPU backing: %s",strerror(error));}
    void *mapped=mmap(memory,(size_t)size,PROT_READ|PROT_WRITE,MAP_FIXED|MAP_SHARED,fd,0);int error=errno;close(fd);
    if(mapped==MAP_FAILED || mapped!=memory)die("[RED] map canonical CPU backing: %s",strerror(error));
    clock_gettime(CLOCK_MONOTONIC,&end);
    VKLOG("CPU canonical file backing: %.2f MiB, %.2f ms (same address/content; reclaimable file pages)",size/1048576.0,(end.tv_sec-begin.tv_sec)*1000.0+(end.tv_nsec-begin.tv_nsec)/1e6);
    return 1;
}
