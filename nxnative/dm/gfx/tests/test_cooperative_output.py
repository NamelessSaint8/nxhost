"""Residual image phase order, zero padding, packed colors and capture bounds."""
import importlib.util
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT/'probes'))


@unittest.skipUnless(importlib.util.find_spec('numpy'), 'requires numpy')
class OutputReference(unittest.TestCase):
    def test_packed_color_clamping_channels_and_ties(self):
        import numpy as np
        from check_output_capture import pack_color, unpack_color
        value = np.array([[-1, 2, .5, 2], [1, 0, 0, .5]], 'f4')
        packed = pack_color(value)
        self.assertEqual(int(packed[0]), (1023<<10)|(512<<20)|(3<<30))
        np.testing.assert_array_equal(unpack_color(packed), [[0, 1023, 512, 3], [1023, 0, 0, 2]])

    def test_zero_padding_and_interleaved_rgba_phases(self):
        import numpy as np
        from check_output_capture import convolution, combine
        source = np.arange(2*3*16, dtype='f4').reshape(2, 3, 16)/128
        weights = np.zeros((9, 16, 16), 'f4')
        weights[0] = np.eye(16, dtype='f4')
        for mode in ('half-mul-add', 'fma-k16-rne', 'fma-k16-rtz'):
            actual = convolution(source, weights, np.array([0, 1]), np.array([0, 1]), mode)
            np.testing.assert_array_equal(actual, np.stack([np.zeros(16), source[0, 0]]))
        with self.assertRaises(ValueError):
            convolution(source, weights, np.array([0]), np.array([0]), 'unknown')
        image = np.zeros((2, 2, 4), 'f4')
        residual = np.tile(np.arange(16, dtype='f4'), (4, 1))/32
        ys, xs = np.array([0, 0, 1, 1]), np.array([0, 1, 0, 1])
        expected = np.array([[0, 1, 8, 9], [2, 3, 10, 11], [4, 5, 12, 13], [6, 7, 14, 15]], 'f4')/32
        np.testing.assert_array_equal(combine(image, residual, np.zeros(16, 'f4'), ys, xs), expected)

    @unittest.skipUnless(shutil.which('glslangValidator') and shutil.which('spirv-val'), 'requires SPIR-V tools')
    def test_dense_oracles_trace_canaries_and_packed_compilation(self):
        from check_output_capture import check
        from make_cooperative_output import build
        from make_cooperative_output_proof import fixture
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder)
            base = fixture(p, True)
            for mode, model in (('native', 'half-mul-add'), ('float32', 'fma-k16-rtz')):
                report = check(base, (9, 13, 32), Path(f'{base}.{mode}.color.bin'),
                               Path(f'{base}.{mode}.trace.bin'), arithmetic=model)
                self.assertEqual(report['max_quantization_units'], 0)
                self.assertEqual(report['trace_max_absolute_error'], 0)
                build(base, p/(mode+'-paired'), (9, 13, 32), mode, True, True)
                quad = build(base, p/(mode+'-quad'), (9, 13, 32), mode, True, quad=True)
                self.assertEqual(quad['grid'], [2, 1, 1])
                self.assertEqual((p/(mode+'-quad')/'layer.tsv').read_bytes(),
                                 (p/(mode+'-paired')/'layer.tsv').read_bytes())
            with self.assertRaisesRegex(ValueError, 'paired or quad'):
                build(base, p/'bad', (9, 13, 32), paired=True, quad=True)
            self.assertFalse((p/'bad').exists())
            trace = p/'bad-trace'
            value = bytearray(Path(f'{base}.native.trace.bin').read_bytes())
            value[0] = 0
            trace.write_bytes(value)
            with self.assertRaisesRegex(ValueError, 'canary'):
                check(base, (9, 13, 32), Path(f'{base}.native.color.bin'), trace)

    @unittest.skipUnless(shutil.which('glslangValidator') and shutil.which('spirv-val'), 'requires SPIR-V tools')
    def test_driver_extent_alignment_format_and_grid_reject(self):
        import numpy as np
        from check_output_capture import load
        from make_cooperative_output import build
        from make_cooperative_output_proof import fixture
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder)
            base = fixture(p)
            driver_path = Path(f'{base}.b1.before.bin')
            driver = np.fromfile(driver_path, '<u4')
            for word, value in ((200, int(driver[200])+2), (206, 2), (210, 2)):
                changed = driver.copy()
                changed[word] = value
                driver_path.write_bytes(changed.tobytes())
                with self.assertRaises(ValueError):
                    load(base, (9, 13, 32))
            driver_path.write_bytes(driver[:210].tobytes())
            with self.assertRaises(ValueError):
                load(base, (9, 13, 32))
            driver_path.write_bytes(driver.tobytes())
            support = Path(f'{base}.b0.before.bin')
            support.write_bytes(bytes(212))
            with self.assertRaises(ValueError):
                load(base, (9, 13, 32))
            support.unlink()
            manifest = base.with_suffix('.tsv').read_text()
            base.with_suffix('.tsv').write_text(manifest.replace('64 64 4', '43 37 4'))
            with self.assertRaises(ValueError):
                load(base, (9, 13, 32))
            base.with_suffix('.tsv').write_text(manifest+'dispatch bad 1 1 2\n')
            with self.assertRaises(ValueError):
                build(base, p/'bad', (9, 13, 32))
            self.assertFalse((p/'bad').exists())
            with self.assertRaises(ValueError):
                build(base, p/'bad', (9, 13, 32), 'unknown')


if __name__ == '__main__':
    unittest.main()
