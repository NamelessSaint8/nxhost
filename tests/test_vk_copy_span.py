"""Check the byte span copy_b2t stages for a buffer and texture copy, compiled with the host cc."""
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class CopySpan(unittest.TestCase):
    @unittest.skipUnless(shutil.which('cc'), 'a host C compiler is required')
    def test_span(self):
        src = (ROOT / 'nxnative/dm/android/gfx_vk_exec.c').read_text()
        start = src.index('static VkDeviceSize copy_span(')
        helper = src[start:src.index('\n}\n', start) + 3]
        code = r'''
#include <stdint.h>
#include <assert.h>
typedef unsigned long long VkDeviceSize;
''' + helper + r'''
int main(void) {
    assert(copy_span(256, 256, 1, 0, 0, 4, 4, 16) == 65536);        // BC7
    assert(copy_span(512, 512, 1, 0, 0, 4, 4, 8) == 131072);        // BC1
    assert(copy_span(6, 6, 1, 0, 0, 4, 4, 16) == 64);               // partial blocks round up
    assert(copy_span(256, 8, 1, 512, 0, 4, 4, 16) == 128*16 + 64*16); // the last row is not a full stride
    assert(copy_span(16, 16, 2, 0, 32, 4, 4, 16) == 768);           // two layers with an image height set
    assert(copy_span(16, 16, 1, 0, 0, 1, 1, 4) == 1024);            // RGBA8
    return 0;
}
'''
        with tempfile.TemporaryDirectory() as d:
            c, exe = Path(d) / 'span.c', Path(d) / 'span'
            c.write_text(code)
            subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror', str(c), '-o', str(exe)], check=True)
            subprocess.run([str(exe)], check=True)


if __name__ == '__main__':
    unittest.main()
