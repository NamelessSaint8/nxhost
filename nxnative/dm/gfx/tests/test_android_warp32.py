"""Compile the synthetic warp-width proof through the shipped translator."""
import importlib.util
import os
from pathlib import Path
import re
import shutil
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[4]


@unittest.skipUnless(os.environ.get('DMSH_TEST_XLATE') and shutil.which('glslangValidator') and shutil.which('spirv-val'),
                     'set DMSH_TEST_XLATE and install glslangValidator/spirv-val')
class Warp32(unittest.TestCase):
    def test_translated_operations_and_safe_negative_controls(self):
        spec = importlib.util.spec_from_file_location('warp32_proof', ROOT / 'probes/make_warp32_proof.py')
        assert spec and spec.loader
        proof = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(proof)
        with tempfile.TemporaryDirectory(prefix='warp32-proof-') as directory:
            out = Path(directory)
            self.assertEqual(proof.build(out, Path(os.environ['DMSH_TEST_XLATE']).resolve()), 16)
            cases = (out / 'manifest.tsv').read_text().splitlines()
            self.assertIn('lane-128 64 0', cases)
            self.assertIn('ldsm-128 64 0', cases)
            self.assertIn('ldsm-transpose-128 64 0', cases)
            self.assertIn('movm-32 64 1', cases)
            self.assertIn('match-128 64 0', cases)
            self.assertIn('redux-128 64 0', cases)
            self.assertIn('hmma-128 128 0', cases)
            self.assertIn('hmma-low-128 64 0', cases)
            self.assertIn('hmma-high-128 64 0', cases)
            self.assertIn('hmma-out-first-128 128 0', cases)
            self.assertIn('hmma-varied-128 128 0', cases)
            self.assertFalse((out / 'hmma-32.vk.spv').exists())
            # Only the helper's out parameter starts undefined. Dropping one
            # HMMA result must not detach its live lane/block input producers.
            # These fixtures had three bare locals before the DCE fix; dispatch
            # would use undefined scratch addresses, so compile-check them first.
            for name in ('hmma-128', 'hmma-low-128', 'hmma-high-128', 'hmma-out-first-128', 'hmma-varied-128'):
                main = (out / (name + '.comp')).read_text().split('void translated_main()', 1)[1]
                self.assertEqual(len(re.findall(r'^    int _\d+;$', main, re.M)), 1, name)
                self.assertEqual(main.count('dmsh_hmma16816_f16('), 1, name)
                self.assertLess(main.index('dmsh_hmma16816_f16('), main.index('result.words['), name)


if __name__ == '__main__':
    unittest.main()
