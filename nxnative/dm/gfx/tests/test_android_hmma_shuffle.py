"""Check the experimental helper's executable shader interface and rejection.

GPU numerical coverage uses the existing twenty-case warp/matrix proof suite;
these tests enforce that changing the helper does not change descriptor or local
workgroup contracts, and that diagnostic trace writes have a separate binding.
"""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'probes'))
import hmma_shuffle
import hmma_cooperative


@unittest.skipUnless(os.environ.get('DMSH_TEST_XLATE') and
                     all(shutil.which(s) for s in ('glslangValidator', 'spirv-val', 'spirv-opt')),
                     'set DMSH_TEST_XLATE and install the SPIR-V tools')
class ShuffleContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory(prefix='shuffle-contract-')
        cls.folder = Path(cls.directory.name)
        spec = importlib.util.spec_from_file_location('proof', ROOT / 'probes/make_warp32_proof.py')
        proof = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(proof)
        proof.build(cls.folder, Path(os.environ['DMSH_TEST_XLATE']).resolve(), False, True)

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def reflect(self, path):
        data = json.loads(subprocess.check_output([str(hmma_shuffle.CROSS), str(path), '--reflect'], text=True))
        bindings = {(kind, row.get('set', 0), row['binding'])
                    for kind in ('ubos', 'ssbos', 'textures', 'images') for row in data.get(kind, [])}
        return bindings, data['entryPoints'][0]['workgroup_size']

    def test_rounding_and_loop_variants_preserve_shader_interface(self):
        source = (self.folder / 'hmma-varied-128.comp').read_text()
        baseline = self.reflect(self.folder / 'hmma-varied-128.vk.spv')
        for rounding, unroll in ((16, False), (8, False), (16, True)):
            with self.subTest(rounding=rounding, unroll=unroll):
                target = self.folder / f'candidate-{rounding}-{unroll}.spv'
                result = hmma_shuffle.compile_source(hmma_shuffle.replace_helper(source, rounding, unroll), target)
                self.assertEqual(self.reflect(target), baseline)
                self.assertEqual(result['helper_calls'], 1)

    def test_trace_binding_is_separate_and_every_matrix_call_is_retained(self):
        source = (self.folder / 'hmma-reuse-128.comp').read_text().replace('binding=31', 'binding=30')
        source, calls = hmma_shuffle.instrument_source(hmma_shuffle.replace_helper(source))
        self.assertEqual(calls, 6)
        target = self.folder / 'trace.spv'
        result = hmma_shuffle.compile_source(source, target)
        bindings, workgroup = self.reflect(target)
        self.assertIn(('ssbos', 0, 30), bindings)
        self.assertIn(('ssbos', 0, 31), bindings)
        self.assertEqual(workgroup, [32, 2, 1])
        self.assertEqual(result['helper_calls'], 6)

    def test_unsupported_program_and_trace_collision_reject(self):
        with self.assertRaises(ValueError):
            hmma_shuffle.build(self.folder / 'lane-128.spv', self.folder / 'bad.spv')
        with self.assertRaises(ValueError):
            hmma_shuffle.instrument_source((self.folder / 'hmma-128.comp').read_text())

    def native_source(self):
        source = (self.folder / 'hmma-reuse-128.comp').read_text()
        # The fixture's STS readback wrapper has no matrix operations itself.
        return source[:source.rindex('void main()')].replace('void translated_main()', 'void main()')

    def test_native_helper_preserves_interface_and_dependent_calls(self):
        source, calls = hmma_cooperative.compose(self.native_source(), [32, 2, 1])
        target = self.folder/'native.spv'
        result = hmma_shuffle.compile_source(source, target, compact=False)
        self.assertEqual(self.reflect(target), self.reflect(self.folder/'hmma-reuse-128.vk.spv'))
        self.assertEqual(calls, 6)
        self.assertEqual(result['helper_calls'], 6)
        module = hmma_shuffle.hmma_spv.Module(target.read_bytes())
        self.assertTrue(any(x[0]&65535 == 4456 for x in module.ins))

    def test_native_helper_rejects_incomplete_waves_and_divergence(self):
        source = self.native_source()
        for local in ([32, 1, 1], [96, 1, 1], [256, 1, 1]):
            with self.subTest(local=local), self.assertRaises(ValueError):
                hmma_cooperative.compose(source, local)
        for control in ('if (gl_LocalInvocationIndex == 0u) return;', 'if (true) {'):
            unsafe = source.replace('void main()\n{', 'void main()\n{\n'+control, 1)
            with self.subTest(control=control), self.assertRaises(ValueError):
                hmma_cooperative.compose(unsafe, [32, 2, 1])
        with self.assertRaises(ValueError):
            hmma_cooperative.build(self.folder/'lane-128.spv', self.folder/'bad-native.spv')


if __name__ == '__main__':
    unittest.main()
