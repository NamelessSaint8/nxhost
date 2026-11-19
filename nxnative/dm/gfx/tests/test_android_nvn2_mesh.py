"""Compile translated Ampere early-exit fixtures through the Vulkan mesh ABI.

The on-device pixel/descriptor/texture checks live in probes/vknvn2.c; this test
keeps their shader generation reproducible without an attached Android device.
"""
from pathlib import Path
import os
import json
import shutil
import subprocess
import sys
import tempfile
import struct
import hashlib
import unittest

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'nxnative/dm/android/tools'))
import nvn2_mesh
import shader_vk


class PayloadLayout(unittest.TestCase):
    def test_native_job_uses_control_stage_and_complete_primitive_header(self):
        control, area = bytearray(0x100), bytearray(0x200)
        struct.pack_into('<2I', control, 0, 0x98761234, 0xc9)
        struct.pack_into('<3I', control, 0x38, 0x90, 0, 0x200)
        struct.pack_into('<I', control, 0x54, 7 << 16)
        struct.pack_into('<HH', control, 0x58, 32, 0)
        control[0x5f] = 3
        struct.pack_into('<HHII', control, 0x60, 3, 1, 0x100, 0x80)
        area[0x35] = 0xf0; area[0x100+0x36] = 1
        # The primitive header lies beyond the instruction length. It must be
        # decoded before code is trimmed for translation.
        struct.pack_into('<I', area, 0, 1 << 10)
        shader_vk.FACTS = {}
        with tempfile.TemporaryDirectory() as directory:
            job, _ = shader_vk.job_for('fixture', 'ds', bytes(0x38)+area+control, directory)
            control[0x30] = 0xd8
            canonical = bytearray(control[:0x48]); canonical[0x30:0x34] = bytes(4)
            key = hashlib.sha256(canonical+area).hexdigest()[:16]
            (Path(directory)/(key+'.bin')).write_bytes(struct.pack('<4sII', b'DMSC', len(control), len(area))+control+area)
            capture = shader_vk.captured(directory)
            self.assertEqual(capture[key][0], 'cs')
        self.assertEqual(job['stage'], 'cs')
        self.assertEqual(job['nvn2_stage'][0], 7)
        self.assertEqual(job['nvn2_mesh']['primitive_lines'], [32])
        self.assertEqual(job['local'], [32, 1, 1])

    def test_rejects_payload_overflow_before_compilation(self):
        info = dict(kind=6, threads=32, attr_words=nvn2_mesh.PAYLOAD_WORDS + 1)
        with self.assertRaisesRegex(ValueError, 'payload exceeds'):
            nvn2_mesh.compose('void main(){}', info)

    def test_rejects_other_launch_models(self):
        for kind, threads in [(5,32),(6,64),(7,0)]:
            with self.subTest(kind=kind, threads=threads), self.assertRaises(ValueError):
                nvn2_mesh.compose('void main(){}', dict(kind=kind,threads=threads))


@unittest.skipUnless(os.environ.get('DMSH_TEST_XLATE') and shutil.which('glslangValidator') and shutil.which('spirv-val'), 'set DMSH_TEST_XLATE and install glslang/spirv-tools')
class StageBufferCompilation(unittest.TestCase):
    def test_formatless_storage_image_capabilities(self):
        with tempfile.TemporaryDirectory(prefix='formatless-image-') as directory:
            source=Path(directory)/'image.comp';target=source.with_suffix('.spv')
            source.write_text('#version 450\nlayout(local_size_x=1)in;layout(r32f,binding=0)uniform image2D input_image;layout(rgba32f,binding=1)uniform image2DArray output_image;void main(){imageStore(output_image,ivec3(0),imageLoad(input_image,ivec2(0)));}')
            subprocess.run(['glslangValidator','-V','--target-env','vulkan1.2',str(source),'-o',str(target)],check=True,capture_output=True)
            original=target.read_bytes();self.assertEqual(shader_vk.formatless_image_capabilities(original),(original,[]))
            words=list(struct.unpack('<'+str(len(original)//4)+'I',original));positions=[];i=5
            while i<len(words):
                n,op=words[i]>>16,words[i]&0xffff
                if op==25:positions.append(i)
                i+=n
            for position in positions:words[position+8]=0
            unqualified=struct.pack('<'+str(len(words))+'I',*words);target.write_bytes(unqualified)
            self.assertNotEqual(subprocess.run(['spirv-val','--target-env','vulkan1.2',str(target)],capture_output=True).returncode,0)
            fixed,added=shader_vk.formatless_image_capabilities(unqualified);self.assertEqual(added,[55,56]);target.write_bytes(fixed)
            result=subprocess.run(['spirv-val','--target-env','vulkan1.2',str(target)],capture_output=True,text=True);self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(shader_vk.formatless_image_capabilities(fixed),(fixed,[]))
            # A typed write alone must not require formatless-write support.
            partial=set();original_words=struct.unpack('<'+str(len(original)//4)+'I',original)
            for position in positions:
                mixed=words.copy();mixed[position+8]=original_words[position+8]
                _,added=shader_vk.formatless_image_capabilities(struct.pack('<'+str(len(mixed))+'I',*mixed));partial.add(tuple(added))
            self.assertEqual(partial,{(55,),(56,)})

    def test_task_mesh_and_early_exit_fixture(self):
        with tempfile.TemporaryDirectory(prefix='nvn2-vulkan-proof-') as directory:
            result = subprocess.run([sys.executable, str(ROOT/'probes/make_nvn2_proof.py'), directory,
                                     '--xlate', os.environ['DMSH_TEST_XLATE']], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
            for name, model in [('task','TaskEXT'),('empty','TaskEXT'),('mesh','MeshEXT'),('direct','MeshEXT')]:
                with self.subTest(shader=name):
                    binary = Path(directory)/(name+'.vk.spv')
                    self.assertTrue(binary.is_file())
                    validation = subprocess.run(['spirv-val','--target-env','vulkan1.2',str(binary)],capture_output=True,text=True)
                    self.assertEqual(validation.returncode, 0, validation.stderr)
                    disassembly = subprocess.run(['spirv-dis',str(binary)],check=True,capture_output=True,text=True).stdout
                    self.assertIn('OpEntryPoint '+model, disassembly)
            metadata = json.loads((Path(directory)/'conversion-results.json').read_text())['metadata']['task']
            fields = struct.unpack('<9I', nvn2_mesh.reflection(metadata, (Path(directory)/'task.vk.spv').read_bytes()))
            self.assertEqual(fields[:4], (1, 32, 4 * nvn2_mesh.PAYLOAD_WORDS, 32))
            # A GLSL round trip gives buffers instance suffixes. Bindings must
            # still be classified using their translator ABI block names.
            source = Path(directory)/'bindings.comp'
            source.write_text('#version 450\nlayout(local_size_x=1) in;layout(binding=0,std140) uniform cp_c0 {uint value;} cp_c0_1;layout(binding=2,std140) uniform cp_c24 {uint value;} cp_c24_1;layout(binding=3,std140) uniform cp_c18 {uint value;} cp_c18_1;layout(binding=1,std430) buffer cp_s0 {uint value;} cp_s0_1;void main(){cp_s0_1.value=cp_c0_1.value+cp_c24_1.value+cp_c18_1.value;}')
            target = source.with_suffix('.spv')
            subprocess.run(['glslangValidator','-V',str(source),'-o',str(target)],check=True,capture_output=True)
            binds, _, _ = shader_vk.spirv_bindings(target.read_bytes())
            classified = [shader_vk.classify('ms', b, {'sbufs':[{'binding':1,'cb_slot':0,'cb_offset':0x770//4,'flags':0}]}) for b in binds]
            self.assertEqual({e['kind'] for e in classified}, {'drvcb', 'sbuf', 'cbuf'})
            self.assertEqual({e['bank'] for e in classified if e['kind']=='drvcb'}, {0,24})
            self.assertEqual(next(e['reg'] for e in classified if e['kind']=='cbuf'), 15)
            self.assertEqual(next(e['reg'] for e in classified if e['kind']=='sbuf'), 0)
            info = Path(directory)/'task-info.json'
            info.write_text(json.dumps(metadata))
            cli = subprocess.run([sys.executable, str(ROOT/'nxnative/dm/android/tools/nvn2_mesh.py'),
                                  str(Path(directory)/'task.spv'),str(info),str(Path(directory)/'task-cli.spv')],
                                 capture_output=True,text=True)
            self.assertEqual(cli.returncode, 0, cli.stdout+cli.stderr)


if __name__ == '__main__':
    unittest.main()
