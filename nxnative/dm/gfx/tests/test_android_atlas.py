"""Sampling ABI rejection/compilation checks; GPU replay is vknvn2_replay --atlas."""
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT/'nxnative/dm/android/tools'))
import atlas_glsl
import shader_vk
import dmsv_atlas

class SamplingContract(unittest.TestCase):
    def test_2d_upgrade_preserves_reflection_constants_and_trailer(self):
        binding=struct.pack('<BBBBHHhBBii',7,2,1,0,3,1,8,1,0,-1,0)
        original=struct.pack('<5I',1,4,8,2,1)+binding+b'C123'+b'native-trailer'
        upgraded=dmsv_atlas.reflect_2d(original,[3])
        self.assertEqual(struct.unpack_from('<5I',upgraded),(2,4,8,2,1))
        self.assertEqual(upgraded[23],17)
        self.assertEqual(struct.unpack_from('<BBBBHHhBBii',upgraded,40),(15,1,255,0,2051,1,-1,0,0,3,0))
        self.assertEqual(upgraded[60:],b'C123native-trailer')
        with self.assertRaisesRegex(ValueError,'collision'):
            dmsv_atlas.reflect_2d(upgraded,[3])

    @unittest.skipUnless(os.environ.get('DMSH_TEST_XLATE') and shutil.which('glslangValidator') and shutil.which('spirv-val'),'GLSL/SPIR-V tools unavailable')
    def test_native_2d_round_trip_and_idempotence(self):
        with tempfile.TemporaryDirectory(prefix='android-atlas-2d-') as directory:
            path=Path(directory);source=path/'source.comp';original=path/'source.spv'
            source.write_text('#version 450\nlayout(local_size_x=1)in;layout(binding=0)uniform sampler2D cp_t2d_tcb_8;layout(binding=1,std430)buffer O{vec4 v;}o;void main(){ivec2 extent=textureSize(cp_t2d_tcb_8,0);o.v=texelFetchOffset(cp_t2d_tcb_8,extent/2,0,ivec2(1))+textureLod(cp_t2d_tcb_8,vec2(.5),0);}')
            subprocess.run(['glslangValidator','-V','--target-env','vulkan1.2',str(source),'-o',str(original)],check=True,capture_output=True)
            binary,converted=shader_vk.compile_atlas(original.read_bytes(),'cs',path/'converted.spv')
            self.assertEqual(converted,[0])
            bindings=shader_vk.spirv_bindings(binary)[0]
            self.assertTrue(next(b['arrayed'] for b in bindings if b['binding']==0))
            again,converted=shader_vk.compile_atlas(binary,'cs',path/'again.spv')
            self.assertEqual(converted,[])
            self.assertEqual(again,binary)

    @unittest.skipUnless(os.environ.get('DMSH_TEST_XLATE') and shutil.which('glslangValidator') and shutil.which('spirv-val'),'GLSL/SPIR-V tools unavailable')
    def test_2d_upgrade_preserves_explicit_shadow_lod(self):
        with tempfile.TemporaryDirectory(prefix='android-atlas-shadow-') as directory:
            path=Path(directory);source=path/'source.comp';original=path/'source.spv'
            source.write_text('#version 450\n#extension GL_EXT_texture_shadow_lod:require\nlayout(local_size_x=1)in;layout(binding=0)uniform sampler2D cp_t2d_tcb_8;layout(binding=2)uniform sampler2DArrayShadow cp_t2das_tcb_A;layout(binding=1,std430)buffer O{vec4 v;}o;void main(){o.v=textureLod(cp_t2d_tcb_8,vec2(.5),0)+vec4(textureLod(cp_t2das_tcb_A,vec4(.5,.5,0,.4),0));}')
            subprocess.run(['glslangValidator','-V','--target-env','vulkan1.2',str(source),'-o',str(original)],check=True,capture_output=True)
            binary,converted=shader_vk.compile_atlas(original.read_bytes(),'cs',path/'converted.spv')
            self.assertEqual(converted,[0])
            def shadow_lods(binary):
                words=struct.unpack('<'+str(len(binary)//4)+'I',binary);constants={};lods=[];i=5
                while i<len(words):
                    size,op=words[i]>>16,words[i]&65535
                    if op==43 and size==4:constants[words[i+2]]=words[i+3]==0
                    if op==44:constants[words[i+2]]=all(constants[x] for x in words[i+3:i+size])
                    if op==46:constants[words[i+2]]=True
                    if op==90:
                        self.assertIn(words[i+6],(2,4))
                        lods.extend(words[i+7:i+size])
                    i+=size
                self.assertTrue(lods)
                return all(constants[x] for x in lods)
            self.assertTrue(shadow_lods(original.read_bytes()))
            self.assertTrue(shadow_lods(binary))
            malformed='#version 460\nlayout(binding=2)uniform sampler2DArrayShadow s;void main(){float x=textureGrad(s,vec4(.5),0.0);}'
            repaired=atlas_glsl._shadow_lod(malformed)
            self.assertIn('textureLod(s,vec4(.5),0.0)',repaired)
            self.assertIn('GL_EXT_texture_shadow_lod',repaired)

    def test_rejects_unimplemented_operations_and_arrays(self):
        for call in ['textureGrad(t,vec3(0),vec2(0),vec2(0))','custom(t)']:
            with self.subTest(call=call), self.assertRaisesRegex(ValueError,'unsupported atlas operation'):
                atlas_glsl.compose('#version 450\nlayout(binding=0)uniform sampler2DArray t;void main(){vec4 v='+call+';}')
        with self.assertRaisesRegex(ValueError,'descriptor arrays'):
            atlas_glsl.compose('#version 450\nlayout(binding=0)uniform sampler2DArray t[2];void main(){vec4 v=textureLod(t[0],vec3(0),0);}')

    def test_implicit_operations_require_fragment_stage(self):
        for stage in (None, 'vs', 'cs', 'ts', 'ms'):
            for call in ('texture(t,vec3(0))', 'textureQueryLod(t,vec2(0))','textureOffset(t,vec3(0),ivec2(1))'):
                with self.subTest(stage=stage,call=call), self.assertRaisesRegex(ValueError,'requires a fragment stage'):
                    atlas_glsl.compose('#version 450\nlayout(binding=0)uniform sampler2DArray t;void main(){vec4 v=vec4('+call+');}',stage)

    def test_rejects_metadata_binding_collision(self):
        with self.assertRaisesRegex(ValueError,'binding collision'):
            atlas_glsl.compose('#version 450\nlayout(binding=0)uniform sampler2DArray t;layout(binding=2048)uniform U{uint x;};void main(){vec4 v=textureLod(t,vec3(0),0);}')

    def test_other_image_types_are_preserved(self):
        for kind in ('sampler2D','usampler2DArray','sampler2DArrayShadow'):
            source='#version 450\nlayout(binding=0)uniform '+kind+' t;void main(){}'
            self.assertEqual(atlas_glsl.compose(source),(source,[]))

    @unittest.skipUnless(os.environ.get('DMSH_TEST_XLATE') and shutil.which('glslangValidator') and shutil.which('spirv-val'),'GLSL/SPIR-V tools unavailable')
    def test_round_trip_reflection_retains_paired_metadata(self):
        with tempfile.TemporaryDirectory(prefix='android-atlas-') as directory:
            path=Path(directory);original=path/'source.spv'
            source=path/'source.comp';source.write_text((ROOT/'probes/shaders/mapped-atlas.comp').read_text())
            subprocess.run(['glslangValidator','-V','--target-env','vulkan1.2',str(source),'-o',str(original)],check=True,capture_output=True)
            binary,converted=shader_vk.compile_atlas(original.read_bytes(),'cs',path/'converted.spv')
            self.assertEqual(converted,[0])
            binds,_,_=shader_vk.spirv_bindings(binary)
            resources={'sbufs':[{'binding':1,'cb_slot':0,'cb_offset':0x310//4,'flags':2},{'binding':2,'cb_slot':0,'cb_offset':0x320//4,'flags':0}]}
            reflected=[shader_vk.classify('cs',b,resources) for b in binds]
            for b in reflected:
                if b['binding'] in converted:b['atlas']=True
            self.assertEqual({b['kind'] for b in reflected},{'tex','sbuf','atlas_meta'})
            self.assertEqual(next(b['off'] for b in reflected if b['kind']=='atlas_meta'),0)
            blob=shader_vk.refl_bin(reflected,b'', [32,1,1])
            records=[struct.unpack_from('<BBBBHHhBBii',blob,20+20*i) for i in range(len(reflected))]
            self.assertTrue(next(r[3] for r in records if r[4]==0)&16)
            self.assertEqual(next(r[0] for r in records if r[4]==2048),15)

    @unittest.skipUnless(os.environ.get('DMSH_TEST_XLATE') and shutil.which('glslangValidator') and shutil.which('spirv-val'),'GLSL/SPIR-V tools unavailable')
    def test_fragment_implicit_round_trip(self):
        with tempfile.TemporaryDirectory(prefix='android-atlas-fragment-') as directory:
            path=Path(directory);source=path/'source.frag';original=path/'source.spv'
            source.write_text((ROOT/'probes/shaders/implicit-atlas.frag').read_text())
            subprocess.run(['glslangValidator','-V','--target-env','vulkan1.2',str(source),'-o',str(original)],check=True,capture_output=True)
            binary,converted=shader_vk.compile_atlas(original.read_bytes(),'ps',path/'converted.spv')
            self.assertEqual(converted,[0,1])
            binds,_,_=shader_vk.spirv_bindings(binary)
            classified=[shader_vk.classify('ps',b,{}) for b in binds]
            self.assertEqual({b['off'] for b in classified if b['kind']=='atlas_meta'},{0,1})
            self.assertEqual([b['reg'] for b in classified if b['kind']=='cbuf'],[0])
            self.assertNotIn('?',{b['kind'] for b in classified})

    @unittest.skipUnless(os.environ.get('DMSH_TEST_XLATE') and shutil.which('glslangValidator') and shutil.which('spirv-val'),'GLSL/SPIR-V tools unavailable')
    def test_offset_gather_constants_and_nested_calls(self):
        with tempfile.TemporaryDirectory(prefix='android-atlas-offset-') as directory:
            path=Path(directory);source=path/'source.frag';original=path/'source.spv'
            source.write_text((ROOT/'probes/shaders/offset-atlas.frag').read_text())
            subprocess.run(['glslangValidator','-V','--target-env','vulkan1.2',str(source),'-o',str(original)],check=True,capture_output=True)
            binary,converted=shader_vk.compile_atlas(original.read_bytes(),'ps',path/'converted.spv')
            self.assertEqual(converted,[0,1]);binds,_,_=shader_vk.spirv_bindings(binary)
            self.assertEqual({b['off'] for b in (shader_vk.classify('ps',r,{}) for r in binds) if b['kind']=='atlas_meta'},{0,1})
            # Local constants remain in scope for the original native branch.
            text='#version 450\nlayout(binding=0)uniform sampler2DArray t;layout(location=0)out vec4 color;void main(){const ivec2 offset=ivec2(1,-1);color=textureLodOffset(t,textureLodOffset(t,vec3(.5),0.0,offset).xyz,1.0,offset);}'
            rewritten,converted=atlas_glsl.compose(text,'ps');self.assertEqual(converted,[0]);source.write_text(rewritten)
            subprocess.run(['glslangValidator','-V','--target-env','vulkan1.2',str(source),'-o',str(original)],check=True,capture_output=True)
            subprocess.run(['spirv-val','--target-env','vulkan1.2',str(original)],check=True,capture_output=True)

if __name__=='__main__':unittest.main()
