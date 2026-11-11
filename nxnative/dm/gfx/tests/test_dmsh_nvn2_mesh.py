"""Synthetic Ampere stage-buffer instructions through the production mesh renderer."""
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
TOOLS = HERE.parent / 'tools'
sys.path.insert(0, str(TOOLS))
import dmsh_geometry
import dmsh_nvn2_mesh


def instruction(hi, lo):
    return struct.pack('<QQ', lo, hi)


def mov(value):
    return instruction(0x000fc60000000f00, value << 32 | 0x7802)


def write(offset, region=3, word=True):
    hi = 0x000fe20000000000 | 1 << 15 | region << 12 | int(word) << 11
    return instruction(hi, offset << 40 | 255 << 24 | 0x7927)


def read(offset):
    return instruction(0x000fe20000007800, offset << 40 | 255 << 24 | 0x7923)


@unittest.skipUnless(os.environ.get('DMSH_TEST_XLATE'), 'set DMSH_TEST_XLATE')
class MeshGPU(unittest.TestCase):
    def test_stage_buffers_and_raster(self):
        with tempfile.TemporaryDirectory(prefix='nvn2_mesh_') as temporary:
            root = Path(temporary)
            jobs = []
            layouts = {}
            for name in ('task', 'empty', 'mesh', 'direct'):
                task = name in ('task', 'empty')
                info = dict(kind=6 if task else 7, threads=32, attr_words=8 if task else 192,
                            input_words=8, map_words=7, max_vertices=3, max_primitives=1,
                            vertex_lines=[28, 29, 30, 31, 32, 33], primitive_lines=[],
                            task_input=name == 'mesh')
                code = bytearray(128)
                # S2R R2, SR_TID.X; ISETP.GE P0,R2,1; @P0 EXIT.
                # The other 31 invocations must still reach the wrapper barrier.
                code += instruction(0x000e220000002100, 0x0000000000027919)
                code += instruction(0x000fe20003f06070, 1 << 32 | 2 << 24 | 0x780c)
                code += instruction(0x000fea0003800000, 0x094d)
                if task:
                    code += read(0) + write(16) + mov(0 if name == 'empty' else 1) + write(4)
                else:
                    for vertex, point in enumerate(((-.75, -.75), (.75, -.75), (0, .75))):
                        for component, value in enumerate((*point, 0., 1.)):
                            bits = struct.unpack('<I', struct.pack('<f', value))[0]
                            code += mov(bits) + write((component * 32 + vertex) * 4)
                        code += read(16 if name == 'mesh' else 0) + write((4 * 32 + vertex) * 4)
                        code += read(0) + write((5 * 32 + vertex) * 4)
                    code += mov(1) + write(3, 0)
                    for i in range(3):
                        code += mov(i) + write(4 + i, 0, False)
                code += instruction(0x000fea0003800000, 0x794d)
                binary = root / (name + '.bin')
                binary.write_bytes(code)
                jobs.append(dict(key=name, stage='cs', arch='sm86', code=str(binary), debug=False,
                                 tex={}, img={}, attr={}, fout={}, local=[32, 1, 1],
                                 nvn2_stage=[info['kind'], 8, info['attr_words'], 7]))
                layouts[name] = info
            (root / 'jobs.json').write_text(json.dumps(jobs))
            result = subprocess.run([os.environ['DMSH_TEST_XLATE'], str(root / 'jobs.json'), str(root)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            for name, info in layouts.items():
                spv = root / (name + '.spv')
                self.assertTrue(spv.exists(), result.stdout + result.stderr)
                dmsh_geometry.flatten_sets(spv)
                cross = subprocess.run([str(TOOLS / 'spirv_cross_bin/spirv-cross'), str(spv), '--msl',
                                        '--msl-version', '20300', '--msl-argument-buffers'], capture_output=True, text=True)
                self.assertEqual(cross.returncode, 0, cross.stderr)
                metal = root / (name + '.metal')
                # Add explicit ABI consumers beside the translated instructions:
                # each logical stage must receive its own UBO, SSBO and c0 table.
                source = cross.stdout
                declaration = ('struct DmTestArgs { constant uint* cb [[id(0)]]; '
                               'device uint* sb [[id(1)]]; constant uint* driver [[id(2)]]; };\n')
                source = source.replace('kernel void main0(', declaration +
                                        'kernel void main0(constant DmTestArgs& abi [[buffer(0)]], ')
                base = 0x670 if info['kind'] == 6 else 0x770
                checks = (f'abi.cb[0]!={info["kind"]}u || abi.sb[0]!={info["kind"]+10}u || '
                          f'abi.driver[{base//4+2}]!=64u')
                invalidate = 'dm_stage_attr[4]=0;' if info['kind'] == 6 else 'for(uint i=0;i<3;i++)dm_stage_attr[128+i]=0;'
                source = source.rstrip()[:-1] + f'if({checks}){{{invalidate}}}\n}}\n'
                self.assertRegex(source, r'kernel void main0\(constant DmTestArgs&')
                metal.write_text(dmsh_nvn2_mesh.compose(source, info))
                subprocess.run(['xcrun', '-sdk', 'macosx', 'metal', '-std=metal3.0', '-c', str(metal), '-o', str(root / (name + '.air'))], check=True, capture_output=True)
                subprocess.run(['xcrun', '-sdk', 'macosx', 'metallib', str(root / (name + '.air')), '-o', str(root / (name + '.metallib'))], check=True, capture_output=True)
            subprocess.run(['make', 'GAME=0400C3F00006E000', 't_nvn2_mesh'], cwd=HERE, check=True, capture_output=True)
            for threaded in ('0', '1'):
                env = dict(os.environ, DM_NVN_ENC_THREAD=threaded, MTL_DEBUG_LAYER='1',
                           MTL_SHADER_VALIDATION='1', MTL_SHADER_VALIDATION_REPORT_TO_STDERR='1')
                gpu = subprocess.run([str(HERE / 't_nvn2_mesh'), str(root)], env=env, capture_output=True, text=True)
                self.assertEqual(gpu.returncode, 0, gpu.stdout + gpu.stderr)


if __name__ == '__main__':
    unittest.main()
