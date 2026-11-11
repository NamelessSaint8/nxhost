"""Validate padded vertex interfaces and literal missing-attribute defaults."""
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT/'nxnative/dm/android/tools'))
import dmsv_pad


@unittest.skipUnless(shutil.which('glslangValidator') and shutil.which('spirv-val'), 'GLSL/SPIR-V tools unavailable')
class Padding(unittest.TestCase):
    def test_shared_types_and_defaults(self):
        with tempfile.TemporaryDirectory(prefix='android-padding-') as directory:
            root = Path(directory)
            vertex = '#version 450\nlayout(location=0)out vec4 existing;void main(){gl_Position=vec4(0,0,0,1);existing=vec4(1);}'
            pixel = '#version 450\nlayout(location=0)in vec4 existing;layout(location=1)in vec2 a;layout(location=2)in vec3 b;layout(location=3)in vec4 c;layout(location=4)flat in ivec4 d;layout(location=5)flat in uvec4 e;layout(location=6)in vec4 f;layout(location=0)out vec4 color;void main(){color=existing+vec4(a,b.xy)+c+vec4(d)+vec4(e)+f;}'
            binaries = []
            for stage, source in [('vert', vertex), ('frag', pixel)]:
                path = root/('source.'+stage)
                path.write_text(source)
                target = path.with_suffix('.'+stage+'.spv')
                subprocess.run(['glslangValidator', '-V', '--target-env', 'vulkan1.2', str(path), '-o', str(target)], check=True, capture_output=True)
                binaries.append(target.read_bytes())
            padded, added, skipped = dmsv_pad.pad(binaries[0], [binaries[1]])
            self.assertEqual((added, skipped), ([1, 2, 3, 4, 5, 6], []))
            target = root/'padded.spv'
            target.write_bytes(padded)
            r = subprocess.run(['spirv-val', '--target-env', 'vulkan1.2', str(target)], text=True, capture_output=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(dmsv_pad.pad(padded, [binaries[1]]), (padded, [], []))
            # Inspect each added output's stored literal, independently of GLSL.
            chunks = dmsv_pad._chunks(dmsv_pad._words(padded))
            locations, constants, composites, stores = {}, {}, {}, {}
            for w in chunks:
                op = w[0] & 0xffff
                if op == 71 and w[2] == 30: locations[w[3]] = w[1]
                elif op == 43: constants[w[2]] = w[3]
                elif op == 44: composites[w[2]] = w[3:]
                elif op == 62: stores[w[1]] = w[2]
            expected = {1: [0, 0], 2: [0, 0, 0], 3: [0, 0, 0, 0x3f800000],
                        4: [0, 0, 0, 0], 5: [0, 0, 0, 0], 6: [0, 0, 0, 0x3f800000]}
            for location, words in expected.items():
                self.assertEqual([constants[x] for x in composites[stores[locations[location]]]], words)


if __name__ == '__main__':
    unittest.main()
