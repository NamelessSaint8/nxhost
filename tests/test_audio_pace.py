"""Check the paced Android audio output's block rule against a device that takes its audio in bursts, compiled with the host cc."""
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def function(src, head):
    start = src.index(head)
    return src[start:src.index('\n}\n', start) + 3]


class Pace(unittest.TestCase):
    @unittest.skipUnless(shutil.which('cc'), 'a host C compiler is required')
    def test_bursts(self):
        src = (ROOT / 'nxnative/dm/android/compat/audiotoolbox_aaudio.c').read_text()
        code = '#include <stdint.h>\n#include <assert.h>\n' + function(src, 'static int pace_blocks(') + function(src, 'static void pace_limits(') + r'''
enum { BLOCK = 240, TICKS = 200 * 60 };
// one simulated minute of 5 ms ticks; the device takes `burst` frames every `every` ticks, `extra` more frames every 1000 ticks (its clock running ahead)
static void run(int burst, int every, int extra, int stall_at) {
    int low, begin, cap; pace_limits(burst, BLOCK, &low, &begin, &cap);
    assert(low < begin && begin + burst <= cap);
    uint64_t used = 0, rendered = 0, after_stall = 0; int playing = 0;
    for (int t = 1; t <= TICKS; t++) {
        int n = pace_blocks(used, BLOCK, low, cap);
        assert(n >= 0 && n <= 2);
        used += (uint64_t)n * BLOCK; rendered += (uint64_t)n; assert(used <= (uint64_t)cap);
        if (stall_at && t > stall_at + 40) after_stall += (uint64_t)n;
        if (stall_at && t >= stall_at) continue;
        if (!playing && used >= (uint64_t)begin) playing = 1;
        if (playing && t % every == 0) { assert(used >= (uint64_t)burst); used -= (uint64_t)burst; }
        if (playing && extra && t % 1000 == 0) { assert(used >= (uint64_t)extra); used -= (uint64_t)extra; }
    }
    if (stall_at) { assert(after_stall == 0); return; }     // a stalled device stops the render callbacks: the watchdog's evidence
    uint64_t want = (uint64_t)TICKS * (uint64_t)burst / (uint64_t)every / BLOCK;
    assert(rendered + 16 >= want && rendered <= want + 16);  // the guest gets the device's whole rate back, not 3 blocks per burst
}
int main(void) {
    run(960, 4, 0, 0);    // the Y700's normal mixer track: 960 frames every 20 ms
    run(480, 2, 0, 0);    // a 10 ms track
    run(240, 1, 0, 0);    // an even 5 ms device
    run(1920, 8, 0, 0);   // a 40 ms burst
    run(960, 4, 48, 0);   // the device clock ahead of ours
    run(960, 4, 0, 2000); // the device stops calling back
    assert(pace_blocks(0, BLOCK, 720, 2640) == 2);    // start-up: catch up
    assert(pace_blocks(719, BLOCK, 720, 2640) == 2);  // just under the mark
    assert(pace_blocks(720, BLOCK, 720, 2640) == 1);  // at the mark: one block, even releases
    assert(pace_blocks(2400, BLOCK, 720, 2640) == 1); // the last block that fits
    assert(pace_blocks(2401, BLOCK, 720, 2640) == 0); // full
    return 0;
}
'''
        with tempfile.TemporaryDirectory() as d:
            c, exe = Path(d) / 'pace.c', Path(d) / 'pace'
            c.write_text(code)
            subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror', str(c), '-o', str(exe)], check=True)
            subprocess.run([str(exe)], check=True)


if __name__ == '__main__':
    unittest.main()
