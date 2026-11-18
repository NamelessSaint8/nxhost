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
    def test_paired_loads_preserve_replay_contract_and_raw_guards(self):
        import json
        import subprocess
        from make_cooperative_conv import build
        from make_cooperative_conv_proof import fixture
        from raw_memory_guard import guard
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder)
            fixture(p, fractional=True, channels=64)
            for n in (16, 32, 64):
                out = p/f'n{n}'
                build(p/'fixture', out, (9, 13, 32), 64, n, True)
                for b in range(4):
                    self.assertEqual((out/f'layer.b{b}.before.bin').read_bytes(),
                                     (p/'experiment'/f'layer.b{b}.before.bin').read_bytes())
                self.assertTrue(json.loads((out/'experiment.json').read_text())['paired_loads'])
                binary, accesses = guard((out/'native.raw.spv').read_bytes())
                self.assertEqual(accesses, 4)
                target = out/'guarded.spv'
                target.write_bytes(binary)
                subprocess.run(['spirv-val', '--target-env', 'vulkan1.2', str(target)], check=True)
            # Pair indexing must also compile with texture unshuffle, physical
            # address tables and the independent float32 arithmetic path.
            for defines in (['-DRAW_LAYOUT=1', '-DTEXTURE_INPUT=1'],
                            ['-DADDRESS_LAYOUT=1'], ['-DFLOAT32_K16=1']):
                target = p/'interface.spv'
                subprocess.run(['glslangValidator', '-V', '--target-env', 'vulkan1.2',
                                '-DHEIGHT=9', '-DWIDTH=13', '-DCI=16', '-DCO=16', '-DPAIRED_LOADS=1',
                                *defines, str(ROOT/'probes/shaders/cooperative-conv.comp'),
                                '-o', str(target)], check=True, capture_output=True)
                subprocess.run(['spirv-val', '--target-env', 'vulkan1.2', str(target)], check=True)

    def test_n64_fixture_preserves_all_channels_and_rejects_unsupported_count(self):
        import numpy as np
        from make_cooperative_conv import build, tensors
        from make_cooperative_conv_proof import fixture
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder)
            fixture(p, fractional=True, channels=64)
            source, weights, bias, output = tensors(p/'fixture', 9, 13, 32, 64)
            self.assertEqual(len(source), 9*13*32*2)
            self.assertEqual(len(weights), 9*32*64*2)
            self.assertEqual(len(bias), 64*2)
            self.assertEqual(len(output), 9*13*64*2)
            self.assertTrue(np.isfinite(np.frombuffer(output, '<f2')).all())
            build(p/'fixture', p/'wide', (9, 13, 32), 64, 64)
            self.assertIn('dispatch native-conv 2 1 1', (p/'wide/layer.tsv').read_text())
            self.assertEqual((p/'wide/captured-output.bin').read_bytes(), output)
            with self.assertRaises(ValueError):
                fixture(p/'invalid', channels=24)
            self.assertFalse((p/'invalid').exists())

    def test_wider_tile_preserves_tensors_and_rejects_partial_channels(self):
        from make_cooperative_conv import build
        from make_cooperative_conv_proof import fixture
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder)
            fixture(p)
            build(p/'fixture', p/'wide', (9, 13, 32), 32, 32)
            for binding in range(4):
                self.assertEqual((p/'wide'/f'layer.b{binding}.before.bin').read_bytes(),
                                 (p/'experiment'/f'layer.b{binding}.before.bin').read_bytes())
            self.assertIn('dispatch native-conv 2 1 1', (p/'wide/layer.tsv').read_text())
            self.assertEqual((p/'wide/captured-output.bin').read_bytes(),
                             (p/'experiment/captured-output.bin').read_bytes())
            with self.assertRaises(ValueError):
                build(p/'fixture', p/'invalid', (9, 13, 32), 16, 32)
            self.assertFalse((p/'invalid').exists())

    def test_first_convolution_rgba_unshuffle_channel_order(self):
        import numpy as np
        from check_first_conv_capture import check
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)/'capture'
            image = ((np.arange(4*6*4).reshape(4, 6, 4)//3)%2*255).astype('u1')
            Path(f'{base}.b2.before.bin').write_bytes(image.tobytes())
            weights = np.zeros((9, 16, 16), '<f2')
            weights[4] = np.eye(16, dtype='<f2')
            Path(f'{base}.b3.before.bin').write_bytes(weights.tobytes())
            Path(f'{base}.b4.before.bin').write_bytes(bytes(32))
            expected = (image.reshape(2, 2, 3, 2, 4).transpose(0, 2, 1, 3, 4).reshape(2, 3, 16)/255).astype('<f2')
            raw = bytes([0xa5])*16+expected.tobytes()+bytes([0x5a])*16
            Path(f'{base}.p0.after.bin').write_bytes(raw)
            driver = np.zeros(1024, '<u4');driver[196] = 4096+16
            Path(f'{base}.b1.before.bin').write_bytes(driver.tobytes())
            base.with_suffix('.tsv').write_text(f'capture 2\nimage 2 1 6 4 37 37 4 0 0 0 0\npool 0 4096 {len(raw)}\n')
            for model in ('half-mul-add', 'fma-k16'):
                self.assertEqual(check(base, arithmetic=model)['max_absolute_error'], 0)
            changed = expected.copy();changed[0, 0, 0] = 1-changed[0, 0, 0]
            Path(f'{base}.p0.after.bin').write_bytes(raw[:16]+changed.tobytes()+raw[-16:])
            self.assertEqual(check(base)['max_absolute_error'], 1)

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
