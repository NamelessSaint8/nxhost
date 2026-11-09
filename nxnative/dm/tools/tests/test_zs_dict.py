"""shader_split: zstd frames that name a dictionary. Ocarina of Time compresses every RomFS .zs this way (Pack/ZsDic.pack.zs), so a reader without the
table sees no asset and no shader at all; the ID is the one in the dictionary's own header, not its place in the pack. No game files needed."""
import struct
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / 'dm/tools/fuzz'))
import fuzz_shader_split as fz   # its shader_split, imported with a profile
ss = fz.ss

from compression import zstd   # noqa: E402  (3.14+, as shader_split's zstd_mod)


def dictionary(dict_id, samples):
    """A zstd dictionary whose header names dict_id: a trained one, then the ID field it records is rewritten"""
    d = bytearray(zstd.train_dict(samples, dict_size=2048).dict_content)
    assert d[:4] == bytes.fromhex('37a430ec')
    struct.pack_into('<I', d, 4, dict_id)
    return bytes(d)


def sarc(members):
    """A SARC whose named members hold the given bytes (the layout shader_split's sarc_members reads)"""
    names = b''.join(n.encode() + b'\0' for n, _ in members)
    n = len(members); names_at = 0x14 + 0xc + 16 * n + 8
    doff = (names_at + len(names) + 0xff) & ~0xff
    out = bytearray(b'SARC' + struct.pack('<HHII', 0x14, 0xfeff, 0, doff) + bytes(4))
    out += b'SFAT' + struct.pack('<HHI', 0xc, n, 0x65)
    s, name_at = 0, 0
    for name, m in members:
        out += struct.pack('<IIII', 0, name_at << 24, s, s + len(m)); s += len(m); name_at += len(name) + 1
    out += b'SFNT' + struct.pack('<HH', 8, 0) + names
    out += bytes(doff - len(out)) + b''.join(m for _, m in members)
    struct.pack_into('<I', out, 8, len(out))
    return bytes(out)


SAMPLES = [f'line {i} of a synthetic romfs asset with repeated words '.encode() * 20 for i in range(64)]
PAYLOAD = b''.join(SAMPLES[:8])
DICTS = {i: dictionary(i, SAMPLES) for i in (1, 4, 9)}


class ZsDict(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / 'romfs'
        (self.root / 'Pack').mkdir(parents=True)
        pack = sarc([('zs.zsdic', DICTS[1]), ('pack.zsdic', DICTS[4])])   # 4's header says 4; its place in the pack would say 2
        (self.root / 'Pack/ZsDic.pack.zs').write_bytes(zstd.compress(pack))
        ss.ZDICTS.clear(); ss._ZD.clear()

    def tearDown(self):
        ss.ZDICTS.clear(); ss._ZD.clear()
        self.tmp.cleanup()

    def frame(self, dict_id):
        return zstd.compress(PAYLOAD, zstd_dict=zstd.ZstdDict(DICTS[dict_id]))

    def test_table_comes_from_the_dictionary_headers(self):
        self.assertEqual(sorted(ss.zs_dicts(str(self.root))), [1, 4])
        self.assertEqual(ss.zs_dicts(str(self.root))[4], DICTS[4])

    def test_a_folder_without_the_pack_has_an_empty_table(self):
        self.assertEqual(ss.zs_dicts(self.tmp.name), {})

    def test_frame_names_its_dictionary(self):
        self.assertEqual(ss.zs_dict_id(self.frame(4)), 4)
        self.assertEqual(ss.zs_dict_id(zstd.compress(PAYLOAD)), 0)

    def test_frame_decompresses_with_the_named_dictionary(self):
        ss.ZDICTS.update(ss.zs_dicts(str(self.root)))
        f = self.frame(1)
        self.assertEqual(ss.unzs_dict(f, ss.zs_dict_id(f), '/test.zs'), PAYLOAD)

    def test_missing_dictionary_is_named(self):
        ss.ZDICTS.update(ss.zs_dicts(str(self.root)))
        with self.assertRaises(SystemExit) as e: ss.unzs_dict(self.frame(9), 9, '/test.zs')
        self.assertIn('9', str(e.exception))


if __name__ == '__main__':
    unittest.main()
