"""dmsv_pad: the SPIR-V side of dmsh_build.py's vs_pad. A vertex stage that does not write an output its pixel stage reads makes Vulkan refuse the pair
(NVN reads 0,0,0,1 there), so shader_vk.py pads the vertex module: this builds the two modules by hand and checks the splice — declarations, the location
decoration, the store, the entry point's interface list and the bound — because a wrong word count here produces a module that parses as garbage."""
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'nxnative/dm/android/tools'))
import dmsv_pad as P  # noqa: E402

VERTEX, FRAGMENT = 0, 4


def module(exec_model, storage, locations):
    """A minimal valid-feeling module: a float4 variable at each location in the storage class, an entry point main that declares them, and an empty body"""
    w = [0x07230203, 0x00010000, 0, 0, 0]
    nid = 1
    def new():
        nonlocal nid
        nid += 1
        return nid - 1
    void, fnty, main = new(), new(), new()
    f32, v4 = new(), new()
    ptr = {loc: new() for loc in locations}
    var = {loc: new() for loc in locations}
    lbl = new()
    w += [(2 << 16) | 17, 1]                                     # OpCapability Shader
    w += [(3 << 16) | 14, 0, 1]                                  # OpMemoryModel Logical GLSL450
    w += [((5 + len(locations)) << 16) | 15, exec_model, main, 0x6e69616d, 0] + [var[l] for l in locations]   # header, model, function, "main\0", interface
    for loc in locations: w += [(4 << 16) | 71, var[loc], 30, loc]   # OpDecorate Location
    w += [(2 << 16) | 19, void]                                  # OpTypeVoid
    w += [(3 << 16) | 33, fnty, void]                            # OpTypeFunction
    w += [(3 << 16) | 22, f32, 32]                               # OpTypeFloat 32
    w += [(4 << 16) | 23, v4, f32, 4]                            # OpTypeVector float 4
    for loc in locations:
        w += [(4 << 16) | 32, ptr[loc], storage, v4]             # OpTypePointer
        w += [(4 << 16) | 59, ptr[loc], var[loc], storage]       # OpVariable
    w += [(5 << 16) | 54, void, main, 0, fnty]                   # OpFunction
    w += [(2 << 16) | 248, lbl]                                  # OpLabel
    w += [(1 << 16) | 253]                                       # OpReturn
    w += [(1 << 16) | 56]                                        # OpFunctionEnd
    w[3] = nid
    return struct.pack(f'<{len(w)}I', *w)


def outputs(spv):
    return {loc: t for loc, t in P._io_locations(P._chunks(P._words(spv)), P.SC_OUTPUT).items()}


class Pad(unittest.TestCase):
    def test_an_output_the_pixel_stage_reads_is_added(self):
        vs, ps = module(VERTEX, P.SC_OUTPUT, [2]), module(FRAGMENT, P.SC_INPUT, [0, 2])
        new, added, skipped = P.pad(vs, [ps])
        self.assertEqual((added, skipped), ([0], []))
        self.assertEqual(sorted(outputs(new)), [0, 2])
        self.assertEqual(outputs(new)[0], ('float', 32, 4, False))
        self.assertEqual(5 + sum(len(c) for c in P._chunks(P._words(new))), len(P._words(new)))   # the stream still walks cleanly

    def test_the_entry_point_and_the_bound_cover_the_new_variable(self):
        vs, ps = module(VERTEX, P.SC_OUTPUT, []), module(FRAGMENT, P.SC_INPUT, [3])
        new, added, _ = P.pad(vs, [ps])
        self.assertEqual(added, [3])
        w = P._words(new)
        self.assertGreater(w[3], P._words(vs)[3])
        ep = next(c for c in P._chunks(w) if P._op(c) == 15)
        var = next(c[2] for c in P._chunks(w) if P._op(c) == 59)
        self.assertIn(var, ep[3:])                                  # SPIR-V 1.3 lists the interface's IO variables
        stores = [c for c in P._chunks(w) if P._op(c) == 62]
        self.assertEqual(len(stores), 1)
        self.assertEqual(stores[0][1], var)

    def test_nothing_missing_leaves_the_module_alone(self):
        vs, ps = module(VERTEX, P.SC_OUTPUT, [0, 1]), module(FRAGMENT, P.SC_INPUT, [1])
        new, added, skipped = P.pad(vs, [ps])
        self.assertEqual((new, added, skipped), (vs, [], []))


if __name__ == '__main__':
    unittest.main()
