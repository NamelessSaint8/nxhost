"""Check census operand positions against independently compiled image calls."""
import importlib.util
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[4]
spec = importlib.util.spec_from_file_location('sampling_audit', ROOT/'probes/audit_android_sampling.py')
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


@unittest.skipUnless(shutil.which('glslangValidator'), 'glslangValidator unavailable')
class SamplingCensus(unittest.TestCase):
    def test_float_and_shadow_operands(self):
        source = '#version 450\nlayout(binding=0)uniform sampler2DArray t;layout(binding=1)uniform sampler2DArrayShadow s;layout(location=0)out vec4 color;void main(){color=texture(t,vec3(0))+textureLod(t,vec3(0),2)+texelFetch(t,ivec3(1),0)+vec4(texture(s,vec4(0)))+vec4(textureQueryLod(t,vec2(0)),0,0);}'
        with tempfile.TemporaryDirectory(prefix='sampling-census-') as directory:
            path = Path(directory)/'source.frag'
            path.write_text(source)
            target = path.with_suffix('.spv')
            subprocess.run(['glslangValidator', '-V', '--target-env', 'vulkan1.2', str(path), '-o', str(target)], check=True, capture_output=True)
            report = audit.inspect(target.read_bytes())
        self.assertEqual(report['array_operations'], {'float:implicit:mask=0': 1,
                         'float:explicit:mask=2': 1, 'float:fetch:mask=2': 1,
                         'shadow:dref_implicit:mask=0': 1, 'float:query_lod:mask=0': 1})
        self.assertEqual(report['unresolved_image_values'], {})
        self.assertEqual(report['io']['output']['0']['type'], 'float32x4')


if __name__ == '__main__':
    unittest.main()
