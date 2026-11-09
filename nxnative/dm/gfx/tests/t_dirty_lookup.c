// Dirty-range lookups preserve first-match semantics across pool retirement, slot reuse and overlapping registrations.
#include "../nvn/nvn_dirty.h"
#include "../../host/dm.h"
#include <pthread.h>
#include <sys/mman.h>
#include <time.h>
#include <unistd.h>
#include <stdio.h>
#include <stdlib.h>

module_t *g_mod; int g_nmod;
module_t *module_of(const void *p) { (void)p; return NULL; }
void crash_install(void);
static int checks, failed;
#define CHECK(c, label) do { checks++; if (!(c)) { failed++; fprintf(stderr, "FAIL: %s\n", label); } } while (0)
static uint64_t ticks(void) { struct timespec t; clock_gettime(CLOCK_MONOTONIC, &t); return (uint64_t)t.tv_sec*1000000000ull+t.tv_nsec; }
typedef struct { const void *address, *span; size_t size; int ok; } lookup_thread;
static void *thread_check(void *arg) {
    lookup_thread *t=arg; t->ok=1;
    for(unsigned i=0;i<10000;i++) if(nvn_dirty_span(t->address,t->size)!=t->span)t->ok=0;
    return NULL;
}
int main(void) {
    crash_install(); size_t pg=(size_t)getpagesize(); enum { N=3000, QUERIES=100000 };
    uint8_t *mem=mmap(NULL,(N+4)*pg,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANON,-1,0);
    if(mem==MAP_FAILED)return 2;
    for(unsigned i=0;i<N;i++)nvn_dirty_add_range(mem+i*pg,pg);
    uint8_t *last=mem+(N-1)*pg; const void *old=nvn_dirty_span(last,pg);
    CHECK(old!=NULL,"late pool is tracked"); uint64_t stamp=nvn_dirty_now();
    volatile int keep=0; uint64_t start=ticks();
    for(unsigned i=0;i<QUERIES;i++)keep+=nvn_dirty_since(last,pg,stamp);
    double lookup_ms=(ticks()-start)/1e6; start=ticks();
    for(unsigned i=0;i<QUERIES;i++)keep+=nvn_dirty_since_span(old,last,pg,stamp);
    printf("dirty lookup benchmark: %.2f ms, explicit span %.2f ms (%d queries, %d pools; %d)\n",lookup_ms,(ticks()-start)/1e6,QUERIES,N,keep);
    CHECK(keep==0,"unwritten late pool stays clean during repeated lookup");
    lookup_thread a={last,old,pg,0},b={mem+pg,nvn_dirty_span(mem+pg,pg),pg,0};pthread_t ta,tb;
    CHECK(!pthread_create(&ta,NULL,thread_check,&a),"first lookup thread starts");
    CHECK(!pthread_create(&tb,NULL,thread_check,&b),"second lookup thread starts");
    pthread_join(ta,NULL);pthread_join(tb,NULL);CHECK(a.ok && b.ok,"lookup hints are independent per thread");
    nvn_dirty_add_range(mem+pg+1,2*pg);
    const void *broad=nvn_dirty_span(mem+pg,2*pg);
    CHECK(broad && broad!=b.span,"a larger query uses the later overlapping range");
    CHECK(nvn_dirty_span(mem+pg,pg)==b.span,"a smaller query still uses its earlier first match after the broad lookup");
    nvn_dirty_remove_range(mem+pg+1);
    CHECK(nvn_dirty_span(last,pg)==old,"warm the late pool before earlier-slot overlap");
    nvn_dirty_remove_range(mem);nvn_dirty_add_range(last+1,2*pg);
    const void *overlap=nvn_dirty_span(last,pg);
    CHECK(overlap && overlap!=old,"an overlapping registration in an earlier slot invalidates the previous first match");
    CHECK(nvn_dirty_span(last+pg,pg)==overlap,"overlapping pool holds its complete rounded range");
    nvn_dirty_protect(last,pg);stamp=nvn_dirty_now();last[0]=7;
    CHECK(nvn_dirty_since(last,pg,stamp),"writes are tracked through the earlier overlapping range");
    nvn_dirty_remove_range(last+1);
    CHECK(nvn_dirty_span(last,pg)==old,"retiring the earlier overlap restores the surviving first match");
    CHECK(!nvn_dirty_tracked(last+pg,pg),"retired overlap does not leave a cached tracked tail");
    nvn_dirty_remove_range(last);
    CHECK(!nvn_dirty_tracked(last,pg),"a retired cached pool is untracked");
    CHECK(nvn_dirty_since(last,pg,nvn_dirty_now()),"untracked memory is conservatively dirty");
    nvn_dirty_add_range(last,pg);nvn_dirty_protect(last,pg);stamp=nvn_dirty_now();
    CHECK(!nvn_dirty_since(last,pg,stamp),"a new pool at the same address starts clean");last[0]=9;
    CHECK(nvn_dirty_since(last,pg,stamp),"the new pool's writes are tracked after slot reuse");
    CHECK(!nvn_dirty_tracked(last,2*pg),"lookup checks the full requested span");
    CHECK(!nvn_dirty_since(last,0,0),"empty dirty checks remain clean");
    for(unsigned i=1;i<N;i++)nvn_dirty_remove_range(mem+i*pg);
    munmap(mem,(N+4)*pg);printf("dirty lookup: %d checks, %d failed\n",checks,failed);return failed!=0;
}
