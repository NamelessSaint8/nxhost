"""shader_split: Bethesda BSA archives (version 0x69: 24-byte folder records, inline folder names, LZ4-frame entries) and the Creation Engine .fxp shader packages
inside them (one control section + code area per record). Synthetic archives only; no game files needed."""
import os
import struct
import sys
import unittest
from pathlib import Path

import lz4.frame

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / 'dm/gfx/tools'))
_had = os.environ.get('DM_GAME'); os.environ['DM_GAME'] = '010029B0118E8000'   # shader_split loads a profile at import; other tests expect no default game
import shader_split as ss
if _had is None: del os.environ['DM_GAME']
else: os.environ['DM_GAME'] = _had

CTL, GFX = 0x98761234, 0x12345678
RECORD = 0x24 + 24 + 3   # the first file record of a one-folder archive with a one-letter folder name
DATA = RECORD + 16


def bsa(files, flags=3, version=105, nfile=None, nfname=None):
    """files: [(folder, name, raw, form)] → a v105 archive; form None stored, 'flag' compressed with the archive flag (its size counts the u32), 'bit' compressed
    with the file's bit 30 (its size does not). nfile / nfname override the header for the refusal tests."""
    groups = []
    for folder, name, raw, form in files:
        if not groups or groups[-1][0] != folder: groups.append((folder, []))
        groups[-1][1].append((name, raw, form))
    at = 0x24 + 24 * len(groups)
    for folder, ents in groups: at += 1 + len(folder) + 1 + 16 * len(ents)
    names = b''.join(name.encode() + b'\0' for _, name, _, _ in files)
    data_at = at + len(names)
    folder_recs = b''.join(struct.pack('<QI', 0, len(ents)) + bytes(12) for _, ents in groups)
    blocks, data = b'', b''
    for folder, ents in groups:
        blocks += bytes([len(folder) + 1]) + folder.encode() + b'\0'
        for name, raw, form in ents:
            if form == 'flag':
                stored = struct.pack('<I', len(raw)) + lz4.frame.compress(raw); size = len(stored)
            elif form == 'bit':
                frame = lz4.frame.compress(raw); stored = struct.pack('<I', len(raw)) + frame; size = 0x40000000 | len(frame)
            else: stored, size = raw, len(raw)
            blocks += struct.pack('<QII', 0, size, data_at + len(data)); data += stored
    head = struct.pack('<4s8I', b'BSA\0', version, 0x24, flags, len(groups), len(files) if nfile is None else nfile,
                       sum(len(f) + 1 for f, _ in groups) if nfname is None else nfname, len(names), 0)
    return head + folder_recs + blocks + names + data


def control(ncode, group=None):
    """A 0x848-byte control section naming its code area's length; group: a compute thread group (at +0x748)"""
    c = bytearray(0x848)
    struct.pack_into('<I', c, 0, CTL)
    struct.pack_into('<I', c, 0x20, len(c))
    struct.pack_into('<I', c, 0x704, ncode)
    if group: struct.pack_into('<III', c, 0x748, *group)
    return bytes(c)


def graphics(ps=True, n=0x80):
    """A graphics code area: 0x12345678 header and an SPH word 0 (bits 10..13: 1 vertex, 5 pixel)"""
    code = bytearray(n)
    struct.pack_into('<I', code, 0, GFX)
    struct.pack_into('<I', code, 0x30, (5 if ps else 1) << 10)
    return bytes(code)


def compute(n=0x40, group=(8, 8, 1)):
    """A compute code area without a 0x12345679 header (Skyrim's 19): raw instructions, the thread group in the control section"""
    return bytes(n)


def fxp(records):
    """records: [(control, code)] → a .fxp: an 8-byte header, then each record's 0x38-byte header, control section and code area"""
    out = bytearray(struct.pack('<II', 2, 2))
    for c, code in records:
        out += struct.pack('<I', 0x11223344) + bytes(0x34) + c + code
    return bytes(out)


class Bsa(unittest.TestCase):
    def test_directory_and_names(self):
        d = bsa([(r'meshes\a', 'x.nif', b'one', None), (r'meshes\a', 'y.nif', b'two', None), (r'strings', 's.txt', b'three', None)])
        got = list(ss.bsa_members(d, '/Data/T.bsa'))
        self.assertEqual([(f, n, c) for f, n, _, _, c in got], [(r'meshes\a', 'x.nif', False), (r'meshes\a', 'y.nif', False), ('strings', 's.txt', False)])
        self.assertEqual([ss.bsa_read(d, off, size, comp, n) for _, n, off, size, comp in got], [b'one', b'two', b'three'])

    def test_compressed_entries_by_archive_flag(self):
        d = bsa([('a', 'one.bin', b'x' * 300, 'flag'), ('a', 'two.bin', b'y' * 40, 'flag')], flags=7)
        got = list(ss.bsa_members(d, '/A.bsa'))
        self.assertTrue(all(c for *_, c in got))
        self.assertEqual([ss.bsa_read(d, off, size, comp, n) for _, n, off, size, comp in got], [b'x' * 300, b'y' * 40])

    def test_compressed_entries_by_size_bit(self):
        d = bsa([('a', 'one.bin', b'x' * 300, 'bit')], flags=0x83)
        _, _, off, size, comp = next(iter(ss.bsa_members(d, '/A.bsa')))
        self.assertTrue(comp)
        self.assertEqual(ss.bsa_read(d, off, size, comp, 'one'), b'x' * 300)

    def test_unknown_version_is_named(self):
        with self.assertRaisesRegex(SystemExit, r'version 104, not the 0x69 layout'):
            list(ss.bsa_members(bsa([], version=104), '/Old.bsa'))

    def test_file_count_mismatch_is_named(self):
        with self.assertRaisesRegex(SystemExit, r'the folders hold 1 files, the header says 2'):
            list(ss.bsa_members(bsa([('a', 'x', b'x', None)], nfile=2), '/Bad.bsa'))

    def test_folder_name_length_mismatch_is_named(self):
        with self.assertRaisesRegex(SystemExit, r'the folder names take 0x2 bytes, the header says 0x9'):
            list(ss.bsa_members(bsa([('a', 'x', b'x', None)], nfname=9), '/Bad.bsa'))

    def test_member_outside_the_archive_is_named(self):
        d = bytearray(bsa([('a', 'x', b'x', None)]))
        struct.pack_into('<I', d, RECORD + 0xc, 0xFFFF)   # the file offset of the first record
        with self.assertRaisesRegex(SystemExit, r'a/x at 0xffff .* lies outside the data'):
            list(ss.bsa_members(bytes(d), '/Bad.bsa'))

    def test_a_compressed_archive_needs_its_frame(self):
        d = bytearray(bsa([('a', 'x', b'x', 'flag')], flags=7))
        struct.pack_into('<I', d, DATA + 4, 0)   # the frame's magic
        with self.assertRaisesRegex(SystemExit, r'without an LZ4 frame'):
            ss.bsa_read(bytes(d), DATA, struct.unpack_from('<I', d, RECORD + 8)[0], True, 'x')


class Fxp(unittest.TestCase):
    def test_stages_and_records(self):
        ps, vs, cs = graphics(ps=True), graphics(ps=False), compute()
        d = fxp([(control(len(ps)), ps), (control(len(vs)), vs), (control(len(cs), (16, 16, 1)), cs)])
        got = ss.fxp_shaders(d, '/S/shaders011.fxp')
        self.assertEqual([s for _, s, _, _ in got], ['ps', 'vs', 'cs'])
        self.assertEqual(got[0][2], control(len(ps)))
        self.assertEqual(got[0][3], ps)
        self.assertEqual(got[0][0], '/S/shaders011.fxp#FXP@0x40')

    def test_a_control_magic_inside_code_is_not_a_record(self):
        code = bytearray(graphics(n=0x100))
        struct.pack_into('<I', code, 0x80, CTL)   # a magic inside the code area: its +0x20 is not a control length
        d = fxp([(control(len(code)), bytes(code))])
        self.assertEqual(len(ss.fxp_shaders(d, '/S/a.fxp')), 1)

    def test_no_record_is_named(self):
        with self.assertRaisesRegex(SystemExit, r'/S/a.fxp: no .fxp shader record'):
            ss.fxp_shaders(fxp([]) + bytes(0x100), '/S/a.fxp')

    def test_bsa_shaders_reads_only_the_fxp_entry(self):
        ps = graphics()
        d = bsa([('shadersfx', 'shaders011.fxp', fxp([(control(len(ps)), ps)]), None), ('textures', 'big.dds', b'DDS ' + bytes(100), None)])
        got = ss.bsa_shaders(d, '/Data/Skyrim - Shaders.bsa')
        self.assertEqual([(w, s) for w, s, _, _ in got], [('/Data/Skyrim - Shaders.bsa/shadersfx/shaders011.fxp#FXP@0x40', 'ps')])


if __name__ == '__main__':
    unittest.main()
