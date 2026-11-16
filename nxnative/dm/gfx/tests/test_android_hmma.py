"""Validate the bounded Android lowering on translator-produced matrix helpers."""
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT/'nxnative/dm/android/tools'))
import hmma_spv


@unittest.skipUnless(os.environ.get('DMSH_TEST_XLATE') and shutil.which('glslangValidator') and shutil.which('spirv-val'),
                     'set DMSH_TEST_XLATE and install glslangValidator/spirv-val')
class Hmma(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory(prefix='hmma-proof-')
        cls.out = Path(cls.directory.name)
        spec = importlib.util.spec_from_file_location('warp32_proof',ROOT/'probes/make_warp32_proof.py')
        proof = importlib.util.module_from_spec(spec);spec.loader.exec_module(proof)
        cls.count = proof.build(cls.out,Path(os.environ['DMSH_TEST_XLATE']).resolve(),True)

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def test_lowered_gpu_fixtures(self):
        self.assertEqual(self.count,20)
        for name in ('hmma-reuse','hmma-alias','hmma-varied','hmma-high','hmma-out-first','hmma-fractional','hmma-denorm'):
            binary=(self.out/(name+'-128.lowered.spv')).read_bytes()
            self.assertIsNone(hmma_spv.hmma_helper(hmma_spv.Module(binary)))
            self.assertEqual(hmma_spv.lower(binary),(binary,0))

    def test_limits_and_unrelated_functions(self):
        binary=(self.out/'hmma-reuse-128.spv').read_bytes()
        for keep in (0,1,2):
            m=hmma_spv.Module(binary)
            void=m.add_type(19);fty=m.add_type(33,void);fn=m.new_id();label=m.new_id()
            unrelated=[[5<<16|54,void,fn,0,fty],[2<<16|248,label],[1<<16|253],[1<<16|56]]
            m.ins.extend(unrelated)
            optimized,count=hmma_spv.lower(m.data(),keep)
            self.assertEqual(count,6)
            out=hmma_spv.Module(optimized);a,e=out.function_range(fn)
            self.assertEqual(out.ins[a:e+1],unrelated)
            path=self.out/f'keep{keep}.spv';path.write_bytes(optimized)
            subprocess.run(['spirv-val','--target-env','vulkan1.2',str(path)],check=True,capture_output=True)
        with self.assertRaises(ValueError):hmma_spv.lower(binary,3)

    def test_unsupported_shape_is_unchanged(self):
        m=hmma_spv.Module((self.out/'hmma-128.spv').read_bytes())
        helper=hmma_spv.hmma_helper(m);a,e=m.function_range(helper['fid'])
        at=next(i for i in range(a,e) if m.ins[i][0]&65535==hmma_spv.OP_CONTROL_BARRIER)
        del m.ins[at]  # Valid SPIR-V but outside the helper contract; never dispatched.
        binary=m.data();self.assertEqual(hmma_spv.lower(binary),(binary,0))

    def test_no_matrix_helper_is_unchanged(self):
        binary=(self.out/'lane-128.spv').read_bytes()
        self.assertEqual(hmma_spv.lower(binary),(binary,0))

    def test_extended_opcode_literal_is_not_a_scratch_reference(self):
        m=hmma_spv.Module((self.out/'hmma-128.spv').read_bytes())
        helper=hmma_spv.hmma_helper(m);scratch=helper['scratch']
        self.assertEqual(scratch,23)  # GLSL.std.450 Asin; one float operand.
        f32=m.find_type(hmma_spv.OP_TYPE_FLOAT,32);zero=m.add_const(f32,0)
        glsl=hmma_spv.ensure_glsl(m);result=m.new_id()
        a,e=m.function_range(m.entry[2]);at=next(i for i in range(a,e) if m.ins[i][0]&65535==253)
        m.ins.insert(at,[6<<16|12,f32,result,glsl,scratch,zero])
        binary=m.data();optimized,count=hmma_spv.lower(binary)
        self.assertEqual(count,1)
        path=self.out/'opcode-collision.spv';path.write_bytes(optimized)
        subprocess.run(['spirv-val','--target-env','vulkan1.2',str(path)],check=True,capture_output=True)
        # An actual outside access to the same Workgroup variable still fails
        # the exclusive-scratch contract, and leaves the module unchanged.
        ptr=m.add_type(32,4,helper['u32']);index=m.add_const(helper['i32'],0);p=m.new_id()
        a,e=m.function_range(m.entry[2]);at=next(i for i in range(a,e) if m.ins[i][0]&65535==253)
        m.ins.insert(at,[5<<16|65,ptr,p,scratch,index])
        binary=m.data();self.assertEqual(hmma_spv.lower(binary),(binary,0))


if __name__ == '__main__':
    unittest.main()
