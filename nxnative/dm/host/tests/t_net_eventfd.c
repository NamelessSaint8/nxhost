// Exercise the local wakeup API gRPC probes, including waits across close/reuse.
#include "../hle_net.c"
#include <unistd.h>

__thread _Atomic int dm_host_work;
static _Atomic int waiting;
static int checks, fails;
static int64_t slept;
uint64_t now_ns(void) { struct timespec t; clock_gettime(CLOCK_MONOTONIC, &t); return (uint64_t)t.tv_sec * 1000000000 + (uint64_t)t.tv_nsec; }
uint64_t guest_ns(void) { return now_ns(); }
int dm_detclock_enabled(void) { return 0; }
void dm_guest_sleep_ns(int64_t ns) { slept = ns; }
void dm_thread_native_wait(int entering) { atomic_fetch_add(&waiting, entering ? 1 : -1); }
#define CHECK(c, msg) do { checks++; if (!(c)) { fails++; fprintf(stderr, "FAIL: %s\n", msg); } } while (0)
typedef struct { int fd, result, error, writing; uint64_t value; int poll; } work;
static void *waiter(void *arg) {
    work *w = arg;
    if (w->poll) { sk_pollfd p = {w->fd, SK_POLLIN, 0}; w->result = dm_sk_poll(&p, 1, 1000); w->value = (uint64_t)p.revents; }
    else w->result = efd_transfer(w->fd, &w->value, w->writing);
    w->error = t_skerr;
    return NULL;
}
static void await_waiter(void) { while (!atomic_load(&waiting)) { struct timespec t = {0, 1000000}; nanosleep(&t, NULL); } }
int main(void) {
    alarm(10);
    int fd = h_sk_EventFd(0, 6); uint64_t value = 99;
    CHECK(fd == 0, "guest descriptors start at zero");
    CHECK(h_nsk_Close(fd) == 0, "gRPC availability probe closes through the C API");
    fd = h_sk_EventFd(0, 6);
    CHECK(h_sk_EventFdRead(fd, &value) == -1 && h_sk_GetLastError() == SK_EAGAIN && value == 99, "empty nonblocking read preserves output and reports BSD EAGAIN");
    CHECK(h_sk_EventFdWrite(fd, 3) == 0 && h_sk_EventFdWrite(fd, 4) == 0, "writes accumulate");
    sk_pollfd p[] = {{fd, SK_POLLIN, 0}, {-1, SK_POLLIN, 7}};
    CHECK(dm_sk_poll(p, 2, 0) == 1 && p[0].revents == SK_POLLIN && !p[1].revents, "poll reports the counter and ignores negative descriptors");
    CHECK(h_sk_EventFdRead(fd, &value) == 0 && value == 7, "ordinary read drains the counter");
    CHECK(dm_sk_poll(p, 2, 0) == 0, "draining removes read readiness");
    CHECK(h_sk_EventFdWrite(fd, UINT64_MAX) == -1 && t_skerr == SK_EINVAL, "reserved counter value rejected");
    CHECK(h_sk_EventFdWrite(fd, UINT64_MAX - 1) == 0, "maximum counter accepted");
    CHECK(h_sk_EventFdWrite(fd, 1) == -1 && t_skerr == SK_EAGAIN, "full counter cannot wrap");
    p[0].events = SK_POLLOUT;
    CHECK(dm_sk_poll(p, 1, 0) == 0, "full counter is not writable");
    CHECK(h_sk_EventFdRead(fd, &value) == 0 && value == UINT64_MAX - 1, "full counter drains exactly");
    CHECK(h_sk_Close(fd) == 0, "C++ close shares the descriptor table");
    fd = h_sk_EventFd(2, SK_EFD_SEMAPHORE | SK_EFD_NONBLOCK);
    CHECK(h_sk_EventFdRead(fd, &value) == 0 && value == 1, "semaphore read consumes one");
    CHECK(h_sk_EventFdRead(fd, &value) == 0 && value == 1, "semaphore leaves the remaining count");
    CHECK(h_sk_EventFdRead(fd, &value) == -1 && t_skerr == SK_EAGAIN, "semaphore becomes empty");
    uint64_t r[16] = {1}, w[16] = {1}, e[16] = {1}; int64_t tv[2] = {0, 0};
    CHECK(dm_sk_select(fd + 1, r, w, e, tv) == 1 && !r[0] && w[0] == 1 && !e[0], "select clears unready bits and reports write readiness");
    CHECK(h_sk_EventFdWrite(fd, 1) == 0, "prepare readable select");
    r[0] = w[0] = 1;
    CHECK(dm_sk_select(fd + 1, r, w, NULL, tv) == 2 && r[0] == 1 && w[0] == 1, "select counts ready bits across both sets");
    h_sk_Close(fd);
    fd = h_sk_EventFd(0, 0);
    work a = {.fd = fd, .poll = 1}; pthread_t thread;
    pthread_create(&thread, NULL, waiter, &a); await_waiter();
    CHECK(h_sk_EventFdWrite(fd, 1) == 0, "writer signals a blocked poller");
    pthread_join(thread, NULL);
    CHECK(a.result == 1 && a.value == SK_POLLIN, "poll wakes on write");
    h_sk_EventFdRead(fd, &value);
    a = (work){.fd = fd};
    pthread_create(&thread, NULL, waiter, &a); await_waiter();
    // Close and reuse under one lock: the reader must not consume the new object.
    dm_host_mutex_lock(&g_efd_mu);
    g_efd[fd].used = 0; g_efd[fd].generation++; g_efd[fd].used = 1; g_efd[fd].count = 5;
    pthread_cond_broadcast(&g_efd_cv); pthread_mutex_unlock(&g_efd_mu);
    pthread_join(thread, NULL);
    CHECK(a.result == -1 && a.error == SK_EBADF && g_efd[fd].count == 5, "blocked reader rejects a reused descriptor");
    h_sk_EventFdRead(fd, &value);
    CHECK(h_sk_EventFdWrite(fd, UINT64_MAX - 1) == 0, "fill blocking counter");
    a = (work){.fd = fd, .writing = 1, .value = 2};
    pthread_create(&thread, NULL, waiter, &a); await_waiter();
    CHECK(h_sk_EventFdRead(fd, &value) == 0 && value == UINT64_MAX - 1, "reader releases counter capacity");
    pthread_join(thread, NULL);
    CHECK(a.result == 0 && h_sk_EventFdRead(fd, &value) == 0 && value == 2, "blocked writer wakes after a read");
    sk_pollfd timeout_poll = {fd, SK_POLLIN, 0}; uint64_t start = now_ns();
    CHECK(dm_sk_poll(&timeout_poll, 1, 10) == 0 && now_ns() - start >= 9000000, "empty event descriptor honors finite poll timeout");
    a = (work){.fd = fd, .poll = 1};
    pthread_create(&thread, NULL, waiter, &a); await_waiter(); h_sk_Close(fd); pthread_join(thread, NULL);
    CHECK(a.result == 1 && a.value == SK_POLLNVAL, "close wakes a poller with invalid-descriptor readiness");
    CHECK(h_sk_Socket(2, 1, 0) == -1 && t_skerr == SK_ENETDOWN, "network sockets remain offline");
    CHECK(h_sk_EventFd(0, 8) == -1 && t_skerr == SK_EINVAL, "unknown flags fail");
    CHECK(h_sk_EventFdRead(0, NULL) == -1 && t_skerr == 14, "null read destination fails without dereferencing");
    CHECK(dm_sk_poll(NULL, 0, 33) == 0 && slept == 33000000, "empty poll retains its timeout behavior");
    CHECK(dm_sk_poll(NULL, 0, -1) == 0 && slept == 100000000, "empty indefinite poll retains the collector boundary");
    CHECK(!atomic_load(&waiting), "native wait entry and exit balance");
    printf("net eventfd: %d checks, %d failures\n", checks, fails);
    return fails != 0;
}
