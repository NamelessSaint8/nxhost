#!/usr/bin/env python3
"""shader_split's BNSH reader on both program layouts: NVN's stage slots (8 bytes apart from program +8, the index naming the stage) and NVN2's
(Switch 2, 0x20 bytes apart, the stage named by the control section and the code's SPH — Mario Kart World's *.Nin_Ounce_NVN2.bfsha: 1023 variations
of a vertex and a pixel stage). Both fixtures are built here, so the Switch 1 path is pinned by the names it used to give: read at the wrong stride,
its pixel stage at slot 4 would come out as a hull stage. Needs no game files and no translator."""
import os, struct, sys, unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1] / 'tools'
os.environ.setdefault('DM_GAME', '0100152000022000')   # shader_split reads a profile at import; the BNSH reader uses none of its rules
sys.path.insert(0, str(TOOLS))
import shader_split as S  # noqa: E402

CTL_MAGIC = bytes.fromhex('34127698')
GFX_MAGIC = bytes.fromhex('78563412')
VS, PS = 1, 5   # SPH word 0, bits 10..13: shader type


def sph(stage): return stage << 10 | 0x61


def fixture(nvar, stages, slot_stride, ctl_size, nvn2, code_len):
    """A BNSH with nvar variations of these stage slots. The program block is 6 slots (slot si at +8 + stride*si, holding a descriptor offset), then one
    0x40-byte descriptor per present stage (control offset, code offset, code length, control length), then each stage's control section and code area"""
    slots = 8 + slot_stride * 5
    top = slots + 0x40 * len(stages) + len(stages) * (ctl_size + code_len)
    hdr = bytearray(0x100 + 0x40 * nvar)
    hdr[0:4] = b'BNSH'; hdr[0x60:0x64] = b'grsc'
    struct.pack_into('<IQ', hdr, 0x7c, nvar, 0x100)
    body = bytearray()
    for v in range(nvar):
        prog = len(body); struct.pack_into('<Q', hdr, 0x100 + 0x40 * v + 0x10, len(hdr) + prog)
        rec = bytearray(top)
        for i, si in enumerate(stages):
            desc = slots + 0x40 * i; ctl = slots + 0x40 * len(stages) + i * (ctl_size + code_len); code = ctl + ctl_size
            struct.pack_into('<Q', rec, 8 + slot_stride * si, len(hdr) + prog + desc)   # the descriptor
            c = bytearray(ctl_size); c[0:4] = CTL_MAGIC
            if nvn2:
                struct.pack_into('<I', c, 4, 0xc9)   # version 0xc9: an NVN2 control section
                struct.pack_into('<I', c, 0x30, ctl_size); struct.pack_into('<II', c, 0x38, code_len, code_len)
                struct.pack_into('<I', c, 0x44, code_len); c[0x56] = 0 if si == 0 else 1
                k = bytearray(code_len); struct.pack_into('<I', k, 0, sph(VS if si == 0 else PS))   # the SPH, then instructions
            else:
                struct.pack_into('<I', c, 4, 1); struct.pack_into('<I', c, 0x20, ctl_size); struct.pack_into('<I', c, 0x704, code_len)
                k = bytearray(code_len); k[0:4] = GFX_MAGIC; struct.pack_into('<I', k, 0x30, sph(VS if si == 0 else PS))
            struct.pack_into('<QQII', rec, desc + 8, len(hdr) + prog + ctl, len(hdr) + prog + code, code_len, ctl_size)   # the descriptor: +8 control offset
            rec[ctl:ctl + ctl_size] = c; rec[code:code + code_len] = k
        body += rec
    return bytes(hdr + body)


def nvn(nvar): return fixture(nvar, (0, 4), 8, 0x880, False, 0x200)   # vertex in slot 0, pixel in slot 4
def nvn2(nvar): return fixture(nvar, (0, 1), 0x20, 0xd8, True, 0x300)   # vertex, then pixel


class Nvn(unittest.TestCase):
    def test_stages_are_named_by_their_slot(self):   # read at 0x20 bytes, the pixel stage at slot 4 would come out as hull
        got = S.bnsh_shaders(nvn(2), 0, 'fixture.nvn.bfsha')
        self.assertEqual([st for _, st, _, _ in got], ['vs', 'ps', 'vs', 'ps'])

    def test_code_and_control_come_from_the_descriptor(self):
        for _, st, ctl, code in S.bnsh_shaders(nvn(1), 0, 'fixture.nvn.bfsha'):
            self.assertEqual((len(ctl), len(code)), (0x880, 0x200))
            self.assertEqual(code[:4], GFX_MAGIC); self.assertEqual(S.sph_stage(code), st)


class Nvn2(unittest.TestCase):
    def test_both_stages_are_found(self):
        got = S.bnsh_shaders(nvn2(3), 0, 'fixture.Nin_Ounce_NVN2.bfsha')
        self.assertEqual([st for _, st, _, _ in got], ['vs', 'ps'] * 3)

    def test_stage_comes_from_the_control_section(self):   # slots 0 and 1 are vertex and hull by NVN's order
        got = S.bnsh_shaders(nvn2(1), 0, 'fixture.Nin_Ounce_NVN2.bfsha')
        self.assertEqual([st for _, st, _, _ in got], ['vs', 'ps'])
        for _, _, ctl, code in got:
            self.assertTrue(S.nvn2_ctl(ctl)); self.assertEqual(len(code), 0x300)

    def test_a_slot_read_at_both_strides_is_not_counted_twice(self):   # read at 8 bytes, NVN2's slot 4 is slot 1 again
        got = S.bnsh_shaders(nvn2(1), 0, 'fixture.Nin_Ounce_NVN2.bfsha')
        self.assertEqual(len({S.skey(ctl, code) for _, _, ctl, code in got}), 2)


class Stage(unittest.TestCase):   # nvn2_stage: the control section's stage byte (+0x56) or the code area's SPH, and never both at odds
    def ctl(self, stage_byte):
        c = bytearray(0xd8); c[0x56] = stage_byte
        return bytes(c)

    def test_compute_has_no_sph(self):   # word 0 is an instruction (LDS 0x57919), as every compute program's is
        self.assertEqual(S.nvn2_stage(self.ctl(5), struct.pack('<I', 0x57919) + bytes(0x20)), 'cs')

    def test_a_compute_section_over_a_graphics_code_area_is_refused(self):   # Mario Kart World's sharcb @0xa1de4: another entry's code area
        self.assertIsNone(S.nvn2_stage(self.ctl(5), struct.pack('<I', sph(VS)) + bytes(0x20)))

    def test_a_graphics_section_is_named_by_its_sph(self):
        self.assertEqual(S.nvn2_stage(self.ctl(1), struct.pack('<I', sph(PS)) + bytes(0x20)), 'ps')


if __name__ == '__main__':
    unittest.main()
