// Android port: an AudioUnit output unit on AAudio (dm/android/compat/include/AudioToolbox/AudioToolbox.h).
// The stream asks for low latency and the unit's own format (interleaved 16-bit or float PCM at its rate and channel count); AAudio's data callback
// calls the unit's render callback with one AudioBuffer over AAudio's buffer, so the host's pull code (hle_audio.c pull_device) is unchanged.
// A stream that disconnects (headphones unplugged, another app taking exclusive audio) stops calling back; the host's watchdog then retries the start,
// which opens a new stream.
#include <AudioToolbox/AudioToolbox.h>
#include <aaudio/AAudio.h>
#include <android/log.h>
#include <pthread.h>
#include <sched.h>
#include <stdatomic.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/prctl.h>
#include <sys/resource.h>
#include <time.h>

struct dm_audio_component { int unused; };
struct dm_audio_unit {
    AudioStreamBasicDescription fmt; int have_fmt;
    AURenderCallbackStruct cb;
    int32_t frames_hint;
    AAudioStream *st;
    _Atomic uint64_t sample_time;
    uint64_t stop_time;    // sample_time at the unit's last stop: unchanged at the next start = the stream stopped calling back (a stall), so it is opened again
    _Atomic int failed;    // the error callback came (disconnected): the next start opens a new stream
    _Atomic int held, in_cb;   // held: stopped, the stream calls back with silence and never into the host (AudioOutputUnitStop); in_cb: data callbacks running
    uint64_t held_frames;  // silence played since the stop: past HOLD_MAX the stream stops itself
    // paced output (pace_thread): the pacer writes ring_tail, the data callback ring_head and playing; both count frames from the last reset
    uint8_t *ring; uint64_t ring_frames; _Atomic uint64_t ring_head, ring_tail, pace_short;
    int32_t pace_block, pace_low, pace_begin, pace_cap;
    _Atomic int paced, pace_run; int playing, pace_on; pthread_t pace_th;
};
static struct dm_audio_component g_output;

AudioComponent AudioComponentFindNext(AudioComponent after, const AudioComponentDescription *d) {
    return !after && d && d->componentType == kAudioUnitType_Output ? &g_output : NULL;
}
OSStatus AudioComponentInstanceNew(AudioComponent c, AudioComponentInstance *out) {
    if (c != &g_output) return kAudio_UnimplementedError;
    *out = calloc(1, sizeof **out); return *out ? noErr : -1;
}
OSStatus AudioUnitSetProperty(AudioUnit u, AudioUnitPropertyID id, AudioUnitScope scope, AudioUnitElement el, const void *data, UInt32 size) {
    (void)scope; (void)el;
    switch (id) {
    case kAudioUnitProperty_StreamFormat:
        if (size < sizeof u->fmt) return -50;
        memcpy(&u->fmt, data, sizeof u->fmt);
        if (u->fmt.mFormatID != kAudioFormatLinearPCM || (u->fmt.mFormatFlags & kAudioFormatFlagIsNonInterleaved)) return kAudioUnitErr_FormatNotSupported;
        if (!(u->fmt.mFormatFlags & kAudioFormatFlagIsFloat) && u->fmt.mBitsPerChannel != 16) return kAudioUnitErr_FormatNotSupported;
        u->have_fmt = 1; return noErr;
    case kAudioUnitProperty_SetRenderCallback: if (size < sizeof u->cb) return -50; memcpy(&u->cb, data, sizeof u->cb); return noErr;
    case kAudioDevicePropertyBufferFrameSize: if (size >= 4) u->frames_hint = (int32_t)*(const UInt32 *)data; return noErr;
    default: return noErr;
    }
}
OSStatus AudioUnitInitialize(AudioUnit u) { return u->have_fmt && u->cb.inputProc ? noErr : -50; }

enum { HOLD_MAX_S = 60 };   // a stop longer than this (the app in the background) ends the stream: the next start opens a new one

// A guest refills only the blocks the output has released, and the host releases them from the render callback. A stream that is not low latency calls back in bursts:
// on the Legion Y700 (TB323FU, Android 16) AAudio's MMAP path is often refused at launch (openMmapStream -19, or start -898), and the normal mixer track that replaces it
// woke every 20 ms, so Persona 4 Golden's CRI output got 3 blocks back per wake: 150 of the 200 blocks a second, 25% of the sound zero padding, whatever the callback
// length, device buffer or host ring (a 10 ms track: 195 a second with dips; the silent sink's even 5 ms, in the same scene: 200.0). So such a stream is fed from a small
// ring that this thread fills one block per block period, and the guest sees an even clock. Low-latency streams call back evenly and stay direct. DM_AUDIO_PACE=0 turns it off
// Blocks one tick renders: one keeps the releases even; two under the low mark (start-up, a device clock running ahead); none when full, so a stalled device stops the
// render callbacks and the host's watchdog still sees the stall
static int pace_blocks(uint64_t used, int32_t block, int32_t low, int32_t cap) {
    int n = used < (uint64_t)low ? 2 : 1;
    while (n && used + (uint64_t)n * (uint64_t)block > (uint64_t)cap) n--;
    return n;
}
// burst: the most the device takes at once. Playing starts with a burst plus the margin queued; the ticks between bursts refill what a burst took
static void pace_limits(int32_t burst, int32_t block, int32_t *low, int32_t *begin, int32_t *cap) {
    if (burst < block) burst = block;
    *low = 3 * block; *begin = burst + *low; *cap = *begin + burst + 2 * block;
}
static void pace_read(AudioUnit u, uint8_t *dst, int32_t frames) {   // the data callback's side: what the ring has, silence for the rest
    size_t bpf = u->fmt.mBytesPerFrame;
    uint64_t h = atomic_load_explicit(&u->ring_head, memory_order_relaxed), avail = atomic_load_explicit(&u->ring_tail, memory_order_acquire) - h, n = (uint64_t)frames;
    if (!u->playing && avail < (uint64_t)u->pace_begin) { memset(dst, 0, (size_t)frames * bpf); return; }
    u->playing = 1;
    if (n > avail) n = avail;
    uint64_t off = h % u->ring_frames, k = u->ring_frames - off; if (k > n) k = n;
    memcpy(dst, u->ring + off * bpf, k * bpf); memcpy(dst + k * bpf, u->ring, (n - k) * bpf);
    atomic_store_explicit(&u->ring_head, h + n, memory_order_release);
    if (n < (uint64_t)frames) { memset(dst + n * bpf, 0, ((uint64_t)frames - n) * bpf); atomic_fetch_add(&u->pace_short, (uint64_t)frames - n); u->playing = 0; }   // short: queue the margin again
}
static void *pace_thread(void *p) {
    AudioUnit u = p; prctl(PR_SET_TIMERSLACK, 1UL); setpriority(PRIO_PROCESS, 0, -16); pthread_setname_np(pthread_self(), "dm-audio-pace");
    size_t bpf = u->fmt.mBytesPerFrame; int32_t block = u->pace_block; int log = getenv("DM_AUDIO_LOG") != NULL;
    int64_t period = (int64_t)block * 1000000000 / (int64_t)u->fmt.mSampleRate; uint64_t ticks = 0, rendered = 0, shown = 0;
    struct timespec next; clock_gettime(CLOCK_MONOTONIC, &next);
    while (atomic_load_explicit(&u->pace_run, memory_order_acquire)) {
        uint64_t t = atomic_load_explicit(&u->ring_tail, memory_order_relaxed), used = t - atomic_load_explicit(&u->ring_head, memory_order_acquire);
        for (int n = pace_blocks(used, block, u->pace_low, u->pace_cap); n > 0; n--) {
            uint8_t *dst = u->ring + t % u->ring_frames * bpf;   // whole blocks: the ring is a multiple of the block, and the tail moves by blocks
            AudioBufferList bl = {1, {{u->fmt.mChannelsPerFrame, (UInt32)((size_t)block * bpf), dst}}}; AudioUnitRenderActionFlags fl = 0;
            struct timespec c; clock_gettime(CLOCK_MONOTONIC, &c);
            AudioTimeStamp ts = {.mSampleTime = (Float64)rendered, .mHostTime = (UInt64)c.tv_sec * 1000000000ull + (UInt64)c.tv_nsec};
            if (u->cb.inputProc(u->cb.inputProcRefCon, &fl, &ts, 0, (UInt32)block, &bl)) memset(dst, 0, (size_t)block * bpf);
            t += (uint64_t)block; rendered += (uint64_t)block; atomic_store_explicit(&u->ring_tail, t, memory_order_release);
        }
        if (log && ++ticks % 2000 == 0) {
            uint64_t sh = atomic_load(&u->pace_short);
            fprintf(stderr, "[dm] audio paced output: %llu frames queued, %llu frames short at the device in the last %llu ticks\n", (unsigned long long)used, (unsigned long long)(sh - shown), 2000ull); shown = sh; }
        next.tv_nsec += period; while (next.tv_nsec >= 1000000000) { next.tv_nsec -= 1000000000; next.tv_sec++; }
        struct timespec now; clock_gettime(CLOCK_MONOTONIC, &now);
        if ((now.tv_sec - next.tv_sec) * 1000000000ll + (now.tv_nsec - next.tv_nsec) > 100000000) next = now;   // far behind (the process was stopped): do not make it up
        clock_nanosleep(CLOCK_MONOTONIC, TIMER_ABSTIME, &next, NULL);
    }
    return NULL;
}
static void pace_reset(AudioUnit u) { atomic_store(&u->ring_head, 0); atomic_store(&u->ring_tail, 0); u->playing = 0; }   // no callback may be reading: before the stream starts, or while it is held
static void pace_stop(AudioUnit u) { if (u->pace_on) { atomic_store_explicit(&u->pace_run, 0, memory_order_release); pthread_join(u->pace_th, NULL); u->pace_on = 0; } }
static void pace_go(AudioUnit u) {
    if (!atomic_load(&u->paced) || u->pace_on) return;
    atomic_store_explicit(&u->pace_run, 1, memory_order_release);
    if (pthread_create(&u->pace_th, NULL, pace_thread, u)) { atomic_store(&u->paced, 0); __android_log_print(ANDROID_LOG_WARN, "dmhost", "audio: no pacing thread, the device callback renders directly"); return; }
    u->pace_on = 1;
}
static void pace_setup(AudioUnit u, int32_t block) {   // a stream just opened, not started yet
    const char *e = getenv("DM_AUDIO_PACE"); aaudio_performance_mode_t mode = AAudioStream_getPerformanceMode(u->st);
    atomic_store(&u->paced, 0);
    if ((e && !atoi(e)) || mode == AAUDIO_PERFORMANCE_MODE_LOW_LATENCY) return;
    int32_t burst = AAudioStream_getFramesPerBurst(u->st), size = AAudioStream_getBufferSizeInFrames(u->st);
    pace_limits(burst > size ? burst : size, block, &u->pace_low, &u->pace_begin, &u->pace_cap);
    uint64_t rf = (uint64_t)block * ((uint64_t)u->pace_cap / (uint64_t)block + 2);
    if (rf != u->ring_frames) { free(u->ring); u->ring = malloc(rf * u->fmt.mBytesPerFrame); u->ring_frames = u->ring ? rf : 0; }
    if (!u->ring) return;
    u->pace_block = block; pace_reset(u); atomic_store(&u->paced, 1);
    __android_log_print(ANDROID_LOG_INFO, "dmhost", "audio: paced output (performance mode %d, burst %d, buffer %d): %d frames per tick, starts at %d queued, at most %d", mode, burst, size, block, u->pace_begin, u->pace_cap);
}
static aaudio_data_callback_result_t on_data(AAudioStream *st, void *ud, void *audio, int32_t frames) {
    AudioUnit u = ud;
    atomic_fetch_add(&u->in_cb, 1);
    if (atomic_load(&u->held)) {   // stopped: silence, and the host's output (which it may have freed) is not touched
        memset(audio, 0, (size_t)frames * u->fmt.mBytesPerFrame); atomic_fetch_add(&u->sample_time, (uint64_t)frames);
        int end = (u->held_frames += (uint64_t)frames) > (uint64_t)(u->fmt.mSampleRate * HOLD_MAX_S);
        atomic_fetch_sub(&u->in_cb, 1); (void)st; return end ? AAUDIO_CALLBACK_RESULT_STOP : AAUDIO_CALLBACK_RESULT_CONTINUE;
    }
    if (atomic_load(&u->paced)) { pace_read(u, audio, frames); atomic_fetch_add(&u->sample_time, (uint64_t)frames); atomic_fetch_sub(&u->in_cb, 1); (void)st; return AAUDIO_CALLBACK_RESULT_CONTINUE; }
    AudioBufferList bl = {1, {{u->fmt.mChannelsPerFrame, (UInt32)frames * u->fmt.mBytesPerFrame, audio}}};
    AudioUnitRenderActionFlags fl = 0;
    struct timespec t; clock_gettime(CLOCK_MONOTONIC, &t);
    AudioTimeStamp ts = {.mSampleTime = (Float64)atomic_fetch_add(&u->sample_time, (uint64_t)frames), .mHostTime = (UInt64)t.tv_sec * 1000000000ull + (UInt64)t.tv_nsec};
    if (u->cb.inputProc(u->cb.inputProcRefCon, &fl, &ts, 0, (UInt32)frames, &bl)) memset(audio, 0, (size_t)frames * u->fmt.mBytesPerFrame);
    atomic_fetch_sub(&u->in_cb, 1); (void)st; return AAUDIO_CALLBACK_RESULT_CONTINUE;
}
static void on_error(AAudioStream *st, void *ud, aaudio_result_t err) {
    (void)st; atomic_store(&((AudioUnit)ud)->failed, 1); __android_log_print(ANDROID_LOG_WARN, "dmhost", "AAudio stream error %d (%s): the host's watchdog restarts it", err, AAudio_convertResultToText(err));
}
// requestStop only asks: the data callback may still be running after it returns, and the host frees the output it pulls from once the unit is stopped
// (hle_audio.c au_close; games close and open outputs when the operation mode changes). So ending a stream (uninitialize, dispose, opening a new one) waits
// until it is stopped, and a stream that does not get there within a second is closed
static void close_stream(AudioUnit u) { pace_stop(u); if (u->st) { AAudioStream_close(u->st); u->st = NULL; } }
static void stop_stream(AudioUnit u) {
    pace_stop(u);
    if (!u->st) return;
    aaudio_stream_state_t s = AAUDIO_STREAM_STATE_UNKNOWN;
    if (AAudioStream_requestStop(u->st) == AAUDIO_OK) {
        s = AAudioStream_getState(u->st);
        for (int i = 0; i < 10 && s != AAUDIO_STREAM_STATE_STOPPED && s != AAUDIO_STREAM_STATE_DISCONNECTED && s != AAUDIO_STREAM_STATE_CLOSED; i++)
            if (AAudioStream_waitForStateChange(u->st, s, &s, 100000000) != AAUDIO_OK) break;
    }
    if (s != AAUDIO_STREAM_STATE_STOPPED) close_stream(u);
}

static int32_t audio_cb_frames(const struct dm_audio_unit *u) {   // the data callback's length: the game's own buffer request, else 5 ms; DM_AUDIO_CALLBACK overrides
    const char *e = getenv("DM_AUDIO_CALLBACK");
    if (e && atoi(e) > 0) return (int32_t)atoi(e);
    return u->frames_hint > 0 ? u->frames_hint : (int32_t)(u->fmt.mSampleRate / 200);
}
OSStatus AudioOutputUnitStart(AudioUnit u) {
    // A stop and start (the pause menu holds the game, the app goes to the background) go on with the same stream, which played silence meanwhile. Each new
    // stream is a new AudioFlinger track, and on the Legion Y700 the app's first was a fast track (bypassing the output's Dolby DAP effect), the ones after it
    // normal mixer tracks through it: the sound got louder after the pause menu (13 Sentinels, four toggles: track 1536 frames fast, then four of 2886; the
    // game's own samples at -30 dBFS throughout). Nor is the stream stopped and started again: on a Legion Y700 (TB322FC, Android 16) a restarted stream left
    // Unicorn Overlord's CRI output short in every other callback for good (998 underruns of 2000, 25% of the sound zero padding; the same 200 callbacks a
    // second), where a new stream had none. A stream that failed, stopped itself (HOLD_MAX_S), or did not call back since the stop (the watchdog's retry after
    // a stall) is opened again
    if (u->st && !atomic_load(&u->failed) && AAudioStream_getState(u->st) == AAUDIO_STREAM_STATE_STARTED && (!atomic_load(&u->held) || atomic_load(&u->sample_time) != u->stop_time)) {
        if (atomic_load(&u->paced) && !u->pace_on) pace_reset(u);   // held since the stop: nothing is reading, and what is queued is old
        atomic_store(&u->held, 0); pace_go(u); return noErr; }
    stop_stream(u); close_stream(u);
    atomic_store(&u->failed, 0); atomic_store(&u->held, 0);
    // A stream that will not start is opened again through the normal mixer path: on the Legion Y700 the low-latency (fast) track goes past the output's Dolby DAP
    // effect, and AAudio answered requestStart with AAUDIO_ERROR_DISCONNECTED (-899) on every retry, so the game stayed silent for good (Skyrim's first boot on
    // the Y700: 48,000 rendered frames, not one audible). DM_AUDIO_PERF=none forces the normal path from the start
    const char *pf = getenv("DM_AUDIO_PERF");
    int perf = pf && !strcasecmp(pf, "none") ? AAUDIO_PERFORMANCE_MODE_NONE : AAUDIO_PERFORMANCE_MODE_LOW_LATENCY;
    for (int attempt = 0; attempt < 2; attempt++, perf = AAUDIO_PERFORMANCE_MODE_NONE) {
    AAudioStreamBuilder *b; aaudio_result_t r = AAudio_createStreamBuilder(&b);
    if (r != AAUDIO_OK) return r;
    AAudioStreamBuilder_setDirection(b, AAUDIO_DIRECTION_OUTPUT);
    AAudioStreamBuilder_setSampleRate(b, (int32_t)u->fmt.mSampleRate);
    AAudioStreamBuilder_setChannelCount(b, (int32_t)u->fmt.mChannelsPerFrame);
    AAudioStreamBuilder_setFormat(b, u->fmt.mFormatFlags & kAudioFormatFlagIsFloat ? AAUDIO_FORMAT_PCM_FLOAT : AAUDIO_FORMAT_PCM_I16);
    AAudioStreamBuilder_setPerformanceMode(b, perf);
    AAudioStreamBuilder_setSharingMode(b, AAUDIO_SHARING_MODE_SHARED);
    AAudioStreamBuilder_setUsage(b, AAUDIO_USAGE_GAME);
    AAudioStreamBuilder_setContentType(b, AAUDIO_CONTENT_TYPE_MUSIC);
    // 5 ms callbacks unless the host asks otherwise, as the iOS front end sets its I/O buffer (docs/agents/03-bringup.md "Crackling on iOS only"): left to itself AAudio
    // on the Legion Y700 called back with 6-960 frames, more than Tales of Eternia Remastered's CRI output keeps queued (about 2 blocks), so 2600 of 2000 callbacks
    // underran and 11% of the sound was zero padding; with 240 frames, 0 underruns. A title that hands its audio over in lumps (Persona 4 Golden's 6-channel CRI output
    // arrived about two blocks at a time, so every other 5 ms callback found an empty queue: 1.5 blocks queued, 1000 underruns of 2000) wants a callback as long as
    // the lump: DM_AUDIO_CALLBACK=<frames> at start-up, then the buffer below is four of those
    int32_t cb = audio_cb_frames(u);
    AAudioStreamBuilder_setFramesPerDataCallback(b, cb);
    // The buffer has to absorb the jitter of the thread that feeds it. AAudio's own default left about two callbacks queued and Skyrim lost 310 of every 2000
    // callbacks to underruns (1550 ms of zero padding in 10 s: audible crackle and judder); four callbacks of slack fixed it. DM_AUDIO_BUFFER=<frames> overrides
    { const char *e = getenv("DM_AUDIO_BUFFER"); int32_t want = e && atoi(e) > 0 ? (int32_t)atoi(e) : 4 * cb;
      AAudioStreamBuilder_setBufferCapacityInFrames(b, want); }
    AAudioStreamBuilder_setDataCallback(b, on_data, u);
    AAudioStreamBuilder_setErrorCallback(b, on_error, u);
    r = AAudioStreamBuilder_openStream(b, &u->st);
    AAudioStreamBuilder_delete(b);
    if (r != AAUDIO_OK) { u->st = NULL; if (perf == AAUDIO_PERFORMANCE_MODE_LOW_LATENCY) { __android_log_print(ANDROID_LOG_WARN, "dmhost", "audio: the low-latency output would not open (%d %s): trying the normal mixer path", r, AAudio_convertResultToText(r)); continue; } return r; }
    // capacity alone does not set the queue: ask for the whole buffer, then report what the device granted
    { const char *e = getenv("DM_AUDIO_BUFFER"); int32_t cb = audio_cb_frames(u);
      int32_t want = e && atoi(e) > 0 ? (int32_t)atoi(e) : 4 * cb, cap = AAudioStream_getBufferCapacityInFrames(u->st);
      if (want > cap) want = cap;
      AAudioStream_setBufferSizeInFrames(u->st, want);
      __android_log_print(ANDROID_LOG_INFO, "dmhost", "audio: buffer %d of %d frames, %d per callback, %d Hz", AAudioStream_getBufferSizeInFrames(u->st), cap, cb, (int)u->fmt.mSampleRate);
      pace_setup(u, cb); }
    // the device's own rate and channel count must be ours: AAudio converts when they differ (it reports the requested format back)
    r = AAudioStream_requestStart(u->st);
    if (r != AAUDIO_OK) {
        close_stream(u);
        if (perf == AAUDIO_PERFORMANCE_MODE_LOW_LATENCY) { __android_log_print(ANDROID_LOG_WARN, "dmhost", "audio: the low-latency output would not start (%d %s): trying the normal mixer path", r, AAudio_convertResultToText(r)); continue; }
        return r;
    }
    if (perf == AAUDIO_PERFORMANCE_MODE_NONE && pf == NULL) __android_log_print(ANDROID_LOG_INFO, "dmhost", "audio: playing through the normal mixer path (the low-latency one was refused)");
    pace_go(u);
    return noErr;
    }
    return (aaudio_result_t)-899;
}
// A stop holds the stream (silence, see AudioOutputUnitStart): once it returns no callback is inside the host's render callback, and none enters it until
// the next start (held is set before in_cb is read, and each callback counts itself in before it reads held)
OSStatus AudioOutputUnitStop(AudioUnit u) {
    if (!u->st) return noErr;
    u->held_frames = 0; atomic_store(&u->held, 1);
    while (atomic_load(&u->in_cb)) sched_yield();
    pace_stop(u);   // joined: the pacer is out of the host's render callback too
    u->stop_time = atomic_load(&u->sample_time); return noErr;
}
OSStatus AudioUnitUninitialize(AudioUnit u) { stop_stream(u); close_stream(u); return noErr; }
OSStatus AudioComponentInstanceDispose(AudioComponentInstance u) { if (u) { stop_stream(u); close_stream(u); free(u->ring); free(u); } return noErr; }
// AudioConverter (AAC → PCM) is on MediaCodec: dm/android/compat/audioconverter_mediacodec.c
