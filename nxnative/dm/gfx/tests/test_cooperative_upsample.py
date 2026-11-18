"""Residual ordering, phase layout and bounded capture admission for upsampling."""
import importlib.util
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT/'probes'))


@unittest.skipUnless(importlib.util.find_spec('numpy'), 'requires numpy')
class UpsampleReference(unittest.TestCase):
    @unittest.skipUnless(shutil.which('glslangValidator') and shutil.which('spirv-val'), 'requires SPIR-V tools')
    def test_packed_load_widths_keep_pool_grid_and_guarded_accesses(self):
        import json
        import subprocess
        from make_cooperative_upsample import build
        from make_cooperative_upsample_proof import fixture
        from raw_memory_guard import guard
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder)
            base = fixture(p, True, inputs=64, channels=32)
            for n in (16, 32, 64):
                for width in (2, 4):
                    out = p/f'n{n}-w{width}'
                    result = build(base, out, (9, 13, 64), 32, n, width)
                    self.assertEqual(result['load_width'], width)
                    self.assertEqual(result['grid'], [2, 128//n, 1])
                    for b in (0, 1, 4, 6):
                        self.assertEqual((out/f'owned.b{b}.before.bin').read_bytes(),
                                         (p/f'n{n}/owned.b{b}.before.bin').read_bytes())
                    self.assertEqual(json.loads((out/'experiment.json').read_text())['load_width'], width)
                    binary, accesses = guard((out/'native.raw.spv').read_bytes())
                    self.assertEqual(accesses, 3 if width==2 else 4)
                    target = out/'guarded.spv'
                    target.write_bytes(binary)
                    subprocess.run(['spirv-val', '--target-env', 'vulkan1.2', str(target)], check=True)
            for width in (0, 3, 8):
                with self.assertRaises(ValueError):
                    build(base, p/'bad', (9, 13, 64), 32, load_width=width)
                self.assertFalse((p/'bad').exists())

    @unittest.skipUnless(shutil.which('glslangValidator') and shutil.which('spirv-val'), 'requires SPIR-V tools')
    def test_wider_fractional_fixture_and_partial_channel_rejection(self):
        import numpy as np
        from check_upsample_capture import load_tensors, reference
        from make_cooperative_upsample_proof import fixture
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder)
            base = fixture(p, True, inputs=64, channels=32)
            x, w, b, c, actual = load_tensors(base, (9, 13, 64), 32)
            ys, xs = np.indices((18, 26)).reshape(2, -1)
            expected = reference(x.reshape(9, 13, 64), w.reshape(4, 64, 32), b,
                                 c.reshape(18, 26, 32), ys, xs)
            np.testing.assert_array_equal(expected, actual.reshape(-1, 32))
            for inputs, channels in ((24, 32), (64, 24), (0, 32)):
                with self.assertRaises(ValueError):
                    fixture(p/'bad', inputs=inputs, channels=channels)
                self.assertFalse((p/'bad').exists())

    def test_four_subpixels_channels_bias_and_relu(self):
        import numpy as np
        from check_upsample_capture import reference
        source = np.arange(32, dtype='f4').reshape(1, 2, 16)-4
        weights = np.stack([np.eye(16, dtype='f4')*(phase+1) for phase in range(4)])
        residual = np.arange(2*4*16, dtype='f4').reshape(2, 4, 16)%3
        bias = np.arange(16, dtype='f4')-8
        ys, xs = np.indices((2, 4)).reshape(2, -1)
        expected = np.maximum(source[ys//2, xs//2]*((ys%2)*2+xs%2+1)[:, None]+residual[ys, xs]+bias, 0)
        for model in ('half-mul-add', 'fma-k16'):
            np.testing.assert_array_equal(reference(source, weights, bias, residual, ys, xs, model), expected)
        with self.assertRaises(ValueError):
            reference(source, weights, bias, residual, ys, xs, 'unknown')

    def test_residual_initialization_has_a_rounding_counterexample(self):
        import numpy as np
        from check_upsample_capture import reference
        source = np.full((1, 1, 16), 2**-12, 'f4')
        weights = np.ones((4, 16, 16), 'f4')
        residual = np.ones((2, 2, 16), 'f4')
        ys, xs = np.indices((2, 2)).reshape(2, -1)
        bias = np.zeros(16, 'f4')
        np.testing.assert_array_equal(reference(source, weights, bias, residual, ys, xs), 1)
        np.testing.assert_array_equal(reference(source, weights, bias, residual, ys, xs, 'fma-k16'), 1+2**-8)

    @unittest.skipUnless(shutil.which('glslangValidator') and shutil.which('spirv-val'), 'requires SPIR-V tools')
    def test_dense_fixture_all_pixels_and_detected_output_change(self):
        import numpy as np
        from check_upsample_capture import check, load_tensors, reference
        from make_cooperative_upsample_proof import fixture
        with tempfile.TemporaryDirectory() as folder:
            base = fixture(Path(folder))
            x, w, b, c, actual = load_tensors(base, (9, 13, 32), 16)
            ys, xs = np.indices((18, 26)).reshape(2, -1)
            expected = reference(x.reshape(9, 13, 32), w.reshape(4, 32, 16), b,
                                 c.reshape(18, 26, 16), ys, xs)
            np.testing.assert_array_equal(expected, actual.reshape(-1, 16))
            self.assertEqual(check(base, (9, 13, 32), 16)['max_absolute_error'], 0)
            driver = np.fromfile(f'{base}.b1.before.bin', '<u4')
            path = Path(f'{base}.p0.after.bin')
            raw = bytearray(path.read_bytes())
            at = int(driver[196])
            value = np.frombuffer(raw, '<f2', count=1, offset=at)
            value[0] += 2
            path.write_bytes(raw)
            self.assertEqual(check(base, (9, 13, 32), 16)['max_absolute_error'], 2)

    @unittest.skipUnless(shutil.which('glslangValidator') and shutil.which('spirv-val'), 'requires SPIR-V tools')
    def test_declared_bounds_alignment_grid_and_multiple_pools_reject(self):
        import numpy as np
        from check_upsample_capture import load_tensors
        from make_cooperative_upsample import build
        from make_cooperative_upsample_proof import fixture
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder)
            base = fixture(p)
            driver_path = Path(f'{base}.b1.before.bin')
            driver = np.fromfile(driver_path, '<u4')
            for word, value in ((214, 2), (212, int(driver[212])+2), (213, 2)):
                changed = driver.copy()
                changed[word] = value
                driver_path.write_bytes(changed.tobytes())
                with self.assertRaises(ValueError):
                    load_tensors(base, (9, 13, 32), 16)
            driver_path.write_bytes(driver.tobytes())
            driver_path.write_bytes(driver[:212].tobytes())
            with self.assertRaises(ValueError):
                load_tensors(base, (9, 13, 32), 16)
            driver_path.write_bytes(driver.tobytes())
            original = base.with_suffix('.tsv').read_text()
            for extra in ('pool 1 1099511627776 1024\n', 'dispatch test 1 1 2\n'):
                base.with_suffix('.tsv').write_text(original+extra)
                with self.assertRaises(ValueError):
                    build(base, p/'invalid', (9, 13, 32), 16)
                self.assertFalse((p/'invalid').exists())
            with self.assertRaises(ValueError):
                build(base, p/'invalid', (9, 13, 32), 16, 8)


if __name__ == '__main__':
    unittest.main()
