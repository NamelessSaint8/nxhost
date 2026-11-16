"""The Android SDK fiber cut keeps signing/restore paired without affecting Apple."""
import importlib.util
import os
from pathlib import Path
import struct
import unittest
from unittest import mock

SDK = Path(__file__).resolve().parents[1] / 'sdk_patches.py'
BUILD = '1643a838814f9c10c696f930ed681e7f'


def patches(target):
    spec = importlib.util.spec_from_file_location('sdk_fiber_test', SDK)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    with mock.patch.dict(os.environ, {'DM_TARGET': target}):
        spec.loader.exec_module(mod)
    return mod


class Fibers(unittest.TestCase):
    def test_android_signing_and_restore_use_the_same_shared_key(self):
        import capstone
        decoder = capstone.Cs(capstone.CS_ARCH_ARM64, capstone.CS_MODE_ARM)
        cuts = patches('android').CUTS[BUILD]
        # Both initial signatures must change with authentication. A partial cut
        # would fail the SDK's signature equality or authentication checks.
        paired = [(off, old, new) for off, old, new, _ in cuts if off in (0x16d0e8, 0x16d0f8, 0x16d40c)]
        self.assertEqual(len(paired), 3)
        for (_, old, new), (before, after) in zip(paired, [('pacia', 'pacib'), ('pacia', 'pacib'), ('autiasp', 'autibsp')]):
            a = list(decoder.disasm(bytes.fromhex(old), 0))[0]
            b = list(decoder.disasm(bytes.fromhex(new), 0))[0]
            self.assertEqual((a.mnemonic, b.mnemonic), (before, after))
            self.assertEqual(a.op_str, b.op_str)

    def test_registered_build_keeps_previously_matched_node_area_cuts(self):
        cuts = patches('android').CUTS[BUILD]
        for off in (0x16ba48, 0x16bad4):
            row = next(c for c in cuts if c[0] == off)
            self.assertEqual(struct.unpack('<I', bytes.fromhex(row[1]))[0] & 31,
                             struct.unpack('<I', bytes.fromhex(row[2]))[0] & 31)
            self.assertIn(row[2], ('087ca052', '097ca052'))

    def test_apple_retains_original_fiber_code_and_function_matching(self):
        apple, android = patches('apple'), patches('android')
        self.assertNotIn(BUILD, apple.CUTS)
        self.assertEqual(android.MATCH_CUTS, apple.MATCH_CUTS)
        self.assertEqual({k: v for k, v in android.CUTS.items() if k != BUILD}, apple.CUTS)


if __name__ == '__main__':
    unittest.main()
