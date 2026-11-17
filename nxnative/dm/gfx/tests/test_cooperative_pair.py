"""Executable interface and fail-closed admission for diagnostic paired tiles."""
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT/'probes'))
import hmma_cooperative_pair as pair

SOURCE = '''#version 460
layout(local_size_x=128) in;
layout(set=0,binding=0,std430) buffer Output { uint words[]; } output_data;
int dmsh_hmma16816_f16(int lane,int scratch,int a0,int a1,int a2,int a3,
    int b0,int b1,int c0,int c1,out int d1) {
    d1=c1+a1+b1;return c0+a0+b0;
}
void main()
{
    int a0=int(output_data.words[0]);
    int a1=int(output_data.words[1]);
    int a2=int(output_data.words[2]);
    int a3=int(output_data.words[3]);
    int hi0;
    int low0 = dmsh_hmma16816_f16(0, 0, a0, a1, a2, a3, a0, a1, 0, 0, hi0);
    int alias0 = low0;
    int hi1;
    int low1 = dmsh_hmma16816_f16(0, 0, a0, a1, a2, a3, a2, a3, 0, 0, hi1);
    int hi2;
    int low2 = dmsh_hmma16816_f16(0, 0, a0, a1, a2, a3, a2, a3, alias0, low1, hi2);
    output_data.words[0]=uint(low2+hi2+hi0+hi1);
}
'''


class PairAdmission(unittest.TestCase):
    def test_preserves_deferred_alias_and_rejects_dependencies(self):
        source = pair.compose(SOURCE, [128, 1, 1], 'a')
        self.assertLess(source.index('dm_paired_a(a0'), source.index('int alias0 = low0;'))
        self.assertEqual(source.count(' = dmsh_hmma16816_f16('), 1)
        for original, replacement in (
            ('int alias0 = low0;', 'int alias0 = low0+1;'),
            ('int hi1;', 'int side = unknown_function();\n    int hi1;'),
            ('a2, a3, 0, 0, hi1', 'a2, a3, low0, 0, hi1'),
            ('a2, a3, 0, 0, hi1', 'a2, a3, 0, 0, hi0'),
            ('0, 0, a0, a1, a2, a3, a2, a3', '0, 0, a1, a1, a2, a3, a2, a3'),
        ):
            with self.subTest(replacement=replacement), self.assertRaises(ValueError):
                pair.compose(SOURCE.replace(original, replacement), [128, 1, 1], 'a')

    def test_rejects_launch_scope_and_verification_collisions(self):
        for local, sharing in (([64, 1, 1], 'a'), ([128, 1, 1], ''),
                               ([128, 1, 1], 'z'), ([128, 1, 1], 'aa')):
            with self.subTest(local=local, sharing=sharing), self.assertRaises(ValueError):
                pair.compose(SOURCE, local, sharing)
        with self.assertRaises(ValueError):
            pair.compose(SOURCE, [128, 1, 1], 'a', scope='unknown')
        with self.assertRaises(ValueError):
            pair.compose(SOURCE.replace('binding=0', 'binding=31'), [128, 1, 1], 'a', verify=True)
        with self.assertRaises(ValueError):
            pair.compose(SOURCE.replace('void main()\n{', 'void main()\n{\nif(true)return;'), [128, 1, 1], 'a')

    @unittest.skipUnless(all(shutil.which(s) for s in ('glslangValidator', 'spirv-opt', 'spirv-val')),
                         'requires SPIR-V tools')
    def test_both_layouts_compile_validate_and_preserve_workgroup(self):
        with tempfile.TemporaryDirectory() as folder:
            for scope in ('workgroup', 'subgroup'):
                for mode in ('a', 'b'):
                    with self.subTest(scope=scope, mode=mode):
                        target = Path(folder)/(scope+mode+'.spv')
                        source = pair.compose(SOURCE, [128, 1, 1], mode, verify=True, scope=scope)
                        pair.hmma_shuffle.compile_source(source, target, compact=False)
                        module = pair.hmma_shuffle.hmma_spv.Module(target.read_bytes())
                        self.assertIn([17, 128, 1, 1], module.modes)
                        self.assertTrue(any(x[0]&65535 == 4456 for x in module.ins))
                        bindings = {d[33][0] for d in module.decos.values() if 33 in d}
                        self.assertEqual(bindings, {0, 31})
                        subprocess.run(['spirv-val', '--target-env', 'vulkan1.2', str(target)], check=True)


if __name__ == '__main__':
    unittest.main()
