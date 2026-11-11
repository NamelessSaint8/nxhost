"""Validate the exact runtime export transform, including component reads."""
import shutil
import struct
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]


@unittest.skipUnless(all(shutil.which(x) for x in ('clang', 'glslangValidator', 'spirv-val')), 'shader tools unavailable')
class Exports(unittest.TestCase):
    def test_mixed_outputs_and_component_access(self):
        with tempfile.TemporaryDirectory(prefix='android-exports-') as directory:
            d = Path(directory)
            cli = d/'outputs'
            subprocess.run(['clang', '-std=c11', '-Wall', '-Wextra', '-Werror', '-fsanitize=address,undefined', str(ROOT/'probes/spv_outputs.c'), '-o', str(cli)], check=True, capture_output=True)
            source = d/'test.frag'
            source.write_text('#version 450\nlayout(location=0)out vec4 a;layout(location=1)out vec4 b;layout(location=2)out float c;void main(){a=uintBitsToFloat(uvec4(17,31,63,127));a.z=uintBitsToFloat(floatBitsToUint(a.x)+9u);b=intBitsToFloat(ivec4(-1,-7,-23,-127));c=a.z;}')
            raw = d/'raw.spv'
            subprocess.run(['glslangValidator', '-V', '--target-env', 'vulkan1.2', str(source), '-o', str(raw)], check=True, capture_output=True)
            original = raw.read_bytes()
            for um, im in [(1, 2), (5, 2), (7, 0), (0, 7), (0, 0)]:
                out = d/f'{um}-{im}.spv'
                subprocess.run([str(cli), str(raw), str(out), str(um), str(im)], check=True, capture_output=True)
                valid = subprocess.run(['spirv-val', '--target-env', 'vulkan1.2', str(out)], text=True, capture_output=True)
                self.assertEqual(valid.returncode, 0, valid.stderr)
                # Inspect interface types, independent of the transform's memo.
                words = struct.unpack('<'+'I'*(len(out.read_bytes())//4), out.read_bytes())
                at, locations, variables = {}, {}, {}
                i = 5
                while i < len(words):
                    n, op = words[i] >> 16, words[i] & 65535
                    if 19 <= op <= 39: at[words[i+1]] = words[i:i+n]
                    if op == 71 and n == 4 and words[i+2] == 30: locations[words[i+1]] = words[i+3]
                    if op == 59 and words[i+3] == 3: variables[words[i+2]] = words[i+1]
                    i += n
                for variable, location in locations.items():
                    t = at[at[variables[variable]][3]]
                    if t[0] & 65535 == 23: t = at[t[2]]
                    expected = 1 if um >> location & 1 else 2 if im >> location & 1 else 0
                    self.assertEqual(t[0] & 65535, 21 if expected else 22)
                    if expected: self.assertEqual(t[3], expected-1)
            self.assertEqual(raw.read_bytes(), original)
            rejected = subprocess.run([str(cli), str(raw), str(d/'bad.spv'), '1', '1'])
            self.assertEqual(rejected.returncode, 3)


if __name__ == '__main__':
    unittest.main()
