"""Exercise native convolution fixture boundaries and diagnostic bundle isolation."""
import importlib.util
from pathlib import Path
import shutil
import struct
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT/'probes'))
import make_cooperative_bundle as bundle


class BundleIsolation(unittest.TestCase):
    def test_only_selected_module_and_local_size_change(self):
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder)
            source, shader, destination = (p/n for n in ('source', 'native', 'result'))
            reflection = struct.pack('<5I', 0, 0, 32, 1, 1)
            # Build a real native module so independent validation is exercised.
            if not shutil.which('glslangValidator') or not shutil.which('spirv-val'):
                self.skipTest('requires glslangValidator and spirv-val')
            import subprocess
            comp = p/'empty.comp'
            comp.write_text('#version 450\nlayout(local_size_x=64) in;void main(){}\n')
            subprocess.run(['glslangValidator', '-V', str(comp), '-o', str(shader)],
                           check=True, capture_output=True)
            header = struct.pack('<4sII', b'DMSV', 1, 2)
            table = struct.pack('<Q6I', 1, 5, 76, 4, 80, 20, 2)
            table += struct.pack('<Q6I', 2, 5, 100, 4, 104, 20, 2)
            original = header+table+b'aaaa'+reflection+b'bbbb'+reflection
            source.write_bytes(original)
            bundle.replace(source, shader, destination, 1)
            result = destination.read_bytes()
            self.assertEqual(source.read_bytes(), original)
            first = struct.unpack_from('<Q6I', result, 12)
            second = struct.unpack_from('<Q6I', result, 44)
            self.assertEqual(result[first[2]:first[2]+first[3]], shader.read_bytes())
            self.assertEqual(struct.unpack_from('<5I', result, first[4]), (0, 0, 64, 1, 1))
            self.assertEqual(result[second[2]:second[2]+second[3]], b'bbbb')
            self.assertEqual(result[second[4]:second[4]+second[5]], reflection)
            self.assertEqual((second[0], second[1], second[6]), (2, 5, 2))
            with self.assertRaises(ValueError):
                bundle.replace(source, shader, source, 1)
            with self.assertRaises(ValueError):
                bundle.replace(source, shader, p/'missing', 99)
            self.assertFalse((p/'missing').exists())


@unittest.skipUnless(importlib.util.find_spec('numpy') and shutil.which('glslangValidator')
                     and shutil.which('spirv-val'), 'requires numpy and SPIR-V tools')
class NativeFixtures(unittest.TestCase):
    def test_half_rounding_and_nonfused_product_counterexample(self):
        import numpy as np
        from check_conv_capture import round_half
        values = np.array([1+3*2**-11, -(1+3*2**-11), .75*2**-24], np.float64)
        np.testing.assert_array_equal(round_half(values), [1+2**-9, -(1+2**-9), 2**-24])
        np.testing.assert_array_equal(round_half(values, 'rtz'), [1+2**-10, -(1+2**-10), 0])
        product = np.array([(1+2**-10)*(1-2**-10)], np.float64)
        self.assertEqual(round_half(product-1)[0], -2**-20)
        self.assertEqual(round_half(round_half(product)-1)[0], 0)
        with self.assertRaises(ValueError):
            round_half(values, 'unknown')

    def test_integer_reference_canaries_and_vulkan_guard(self):
        import numpy as np
        import subprocess
        from make_cooperative_conv_proof import fixture
        from check_cooperative_conv import inspect
        from raw_memory_guard import guard
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder)
            fixture(p)
            experiment = p/'experiment'
            replay = p/'reference'
            for i in range(3):
                Path(f'{replay}.b{i}.after.bin').write_bytes((experiment/f'layer.b{i}.before.bin').read_bytes())
            expected = (experiment/'captured-output.bin').read_bytes()
            result = bytes([0xa5])*64+expected+bytes([0x5a])*64
            output = Path(f'{replay}.b3.after.bin')
            output.write_bytes(result)
            report = inspect(experiment, replay)
            self.assertEqual(report['native_vs_cpu']['max_absolute_error'], 0)
            self.assertEqual(report['vs_capture']['exact_fraction'], 1)
            output.write_bytes(b'\0'+result[1:])
            with self.assertRaisesRegex(ValueError, 'canary'):
                inspect(experiment, replay)
            raw = (experiment/'native.raw.spv').read_bytes()
            binary, accesses = guard(raw)
            self.assertEqual(accesses, 4)
            guarded = p/'guarded.spv'
            guarded.write_bytes(binary)
            subprocess.run(['spirv-val', '--target-env', 'vulkan1.2', str(guarded)], check=True)
            self.assertTrue(np.count_nonzero(np.frombuffer(expected, '<f2')))


if __name__ == '__main__':
    unittest.main()
