"""Reserved raw-address descriptors must never be decoded as game uniforms."""
from pathlib import Path
import re
import struct
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'android/tools'))
import shader_vk


class GlobalMemory(unittest.TestCase):
    def test_pool_log_control_matches_the_shared_abi(self):
        import dmsh_abi
        shader=Path(__file__).resolve().parents[2]/'third_party/ryujinx/src/Ryujinx.Graphics.Shader/Translation/Optimizations/GlobalToStorage.cs'
        value=int(re.search(r'const int GmemMapNoWriteLog = (\d+)',shader.read_text())[1])
        self.assertEqual(value,dmsh_abi.GMEM_MAP_NO_WRITE_LOG)
        self.assertEqual(dmsh_abi.GMEM_MAP_ENTRY,32)

    def binding(self,stage,slot,offset):
        return shader_vk.classify(stage,{'name':'cp_s0','binding':5,'type':'ssbo','dim':255,'count':1},
            {'sbufs':[{'binding':40,'cb_slot':slot,'cb_offset':offset,'flags':1}]})

    def test_reserved_map_and_log_in_every_stage(self):
        for stage in ('vs','ps','gs','cs','ts','ms'):
            for offset,kind in ((0,'gmem_map'),(1,'gmem_log')):
                with self.subTest(stage=stage,offset=offset):
                    binding=self.binding(stage,255,offset)
                    self.assertEqual(binding['kind'],kind)
                    self.assertIsNone(binding['reg'])
                    binary=shader_vk.refl_bin([binding],b'',[32,1,1])
                    row=struct.unpack_from('<BBBBHHhBBii',binary,20)
                    self.assertEqual((row[0],row[1],row[4],row[6]),(17+offset,1,5,-1))

    def test_unknown_reserved_offset_rejected(self):
        with self.assertRaises(ValueError):self.binding('cs',255,2)

    def test_ordinary_uniform_pointer_is_preserved(self):
        binding=self.binding('cs',3,14)
        self.assertEqual((binding['kind'],binding['reg'],binding['off']),('sbuf_ubo',0,56))


if __name__=='__main__':unittest.main()
