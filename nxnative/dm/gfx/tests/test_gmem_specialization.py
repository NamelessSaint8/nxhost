"""Validate the runtime transform and its refusal to erase unknown log uses."""
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[4]


@unittest.skipUnless(all(shutil.which(s) for s in ('clang', 'glslangValidator', 'spirv-val')), 'SPIR-V tools unavailable')
class CoherentLog(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='gmem-specialization-')
        cls.folder = Path(cls.temp.name)
        cls.tool = cls.folder/'transform'
        subprocess.run(['clang', '-O1', '-g', '-Wall', '-Wextra', '-Werror', '-fsanitize=address,undefined',
                        str(ROOT/'probes/spv_gmem.c'), '-o', str(cls.tool)], check=True, capture_output=True)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def compile(self, body):
        source = self.folder/'source.comp'
        source.write_text('#version 450\nlayout(local_size_x=1)in;'
                          'layout(binding=0,std430)buffer Log{uint words[];}log;'
                          'layout(binding=1,std430)buffer Out{uint words[];}o;void main(){'+body+'}')
        path = self.folder/'input.spv'
        subprocess.run(['glslangValidator', '-V', '--target-env', 'vulkan1.2', str(source), '-o', str(path)],
                       check=True, capture_output=True)
        return path

    def test_log_writes_removed_other_atomics_and_output_retained(self):
        source = self.compile('uint old=atomicCompSwap(log.words[1],0,17);'
                              'if(old!=0)atomicOr(log.words[0],1);'
                              'log.words[2]=21;o.words[0]=atomicAdd(o.words[1],19);')
        before = source.read_bytes()
        output = self.folder/'output.spv'
        subprocess.run([str(self.tool), str(source), str(output), '0'], check=True)
        self.assertEqual(source.read_bytes(), before)
        subprocess.run(['spirv-val', '--target-env', 'vulkan1.2', str(output)], check=True, capture_output=True)
        words = struct.unpack('<%dI' % (output.stat().st_size//4), output.read_bytes())
        ops = [];i = 5
        while i < len(words):
            ops.append(words[i]&65535);i += words[i]>>16
        self.assertNotIn(230, ops)
        self.assertNotIn(241, ops)
        self.assertIn(234, ops)  # guest-visible atomicAdd
        self.assertIn(62, ops)  # ordinary output write

    def test_reads_and_unsupported_log_atomics_refuse_specialization(self):
        for body in ('o.words[0]=log.words[0];log.words[1]=17;',
                     'o.words[0]=atomicAdd(log.words[0],1);', 'o.words[0]=5;'):
            with self.subTest(body=body):
                source = self.compile(body)
                result = subprocess.run([str(self.tool), str(source), str(self.folder/'refused.spv'), '0'])
                self.assertEqual(result.returncode, 3)


if __name__ == '__main__':
    unittest.main()
