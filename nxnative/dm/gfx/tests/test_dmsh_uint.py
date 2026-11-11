"""Integer render-target entries for typeless values forwarded across stages."""
import ast
from pathlib import Path
import re
import unittest

builder = Path(__file__).resolve().parents[1] / 'tools/dmsh_build.py'
tree = ast.parse(builder.read_text())
function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'fs_uint')
namespace = {'re': re}
exec(compile(ast.Module(body=[function], type_ignores=[]), str(builder), 'exec'), namespace)
fs_uint = namespace['fs_uint']

SOURCE = '''struct main0_out {\n    float4 color [[color(0)]];\n};
struct main0_in {\n    float4 bits [[user(locn0), flat]];\n};
fragment main0_out main0(main0_in in [[stage_in]]) {
    main0_out out = {};
    float first = in.bits.x;
    float second = first;
    out.color.x = second;
    return out;
}
'''


class IntegerTargets(unittest.TestCase):
    def test_flat_forward_preserves_integer_bits(self):
        source, mixed = fs_uint(SOURCE)
        self.assertIn('fragment main0_out_u main0_u(', source)
        self.assertIn('as_type<uint4>(out.color)', source)
        self.assertEqual(mixed, 0)

    def test_interpolated_float_does_not_imply_an_integer_origin(self):
        self.assertEqual(fs_uint(SOURCE.replace(', flat', '')), (None, 0))

    def test_arithmetic_is_not_a_flat_passthrough(self):
        self.assertEqual(fs_uint(SOURCE.replace('float second = first;', 'float second = first + 0.5;')), (None, 0))


if __name__ == '__main__':
    unittest.main()
