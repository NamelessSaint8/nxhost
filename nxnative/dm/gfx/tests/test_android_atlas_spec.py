"""Validate the exact runtime atlas transform, including directional sampling."""
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT/'nxnative/dm/android/tools'))
import shader_vk


@unittest.skipUnless(all(shutil.which(x) for x in ('clang','glslangValidator','spirv-val')),'SPIR-V tools unavailable')
class AtlasSpecialization(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scratch=tempfile.TemporaryDirectory(prefix='atlas-spec-')
        cls.path=Path(cls.scratch.name)
        cls.tool=cls.path/'transform'
        subprocess.run(['clang','-std=c11','-O1','-g','-Wall','-Wextra','-Werror','-fsanitize=address,undefined',str(ROOT/'probes/spv_atlas.c'),'-o',str(cls.tool)],check=True,capture_output=True)

    @classmethod
    def tearDownClass(cls): cls.scratch.cleanup()

    def compile(self,stage,source):
        path=self.path/('source.'+stage);path.write_text(source)
        original=self.path/'original.spv'
        subprocess.run(['glslangValidator','-V','--target-env','vulkan1.2','-S',stage,str(path),'-o',str(original)],check=True,capture_output=True)
        binary,converted=shader_vk.compile_atlas(original.read_bytes(),'ps' if stage=='frag' else 'cs',self.path/'atlas.spv')
        self.assertEqual(converted,[0,3])
        return binary

    def transform(self,binary):
        source=self.path/'input.spv';source.write_bytes(binary);dest=self.path/'specialized.spv'
        result=subprocess.run([str(self.tool),str(source),str(dest),'2048','0','2051','3'],check=True,capture_output=True,text=True)
        subprocess.run(['spirv-val','--target-env','vulkan1.2',str(dest)],check=True,capture_output=True)
        words=struct.unpack('<'+str(dest.stat().st_size//4)+'I',dest.read_bytes());specs={};defaults={};i=5
        while i<len(words):
            n,op=words[i]>>16,words[i]&65535
            if op==71 and n==4 and words[i+2]==1:specs[words[i+3]]=words[i+1]
            if op==50 and n==4:defaults[words[i+2]]=words[i+3]
            i+=n
        self.last_words=words
        self.last_specs=set(specs.values())
        return result.stdout,{key:defaults[value] for key,value in specs.items()}

    def test_retained_helpers_distinguish_implicit_from_explicit_lod(self):
        binary=self.compile('frag','#version 450\nlayout(binding=0)uniform sampler2DArray a;layout(binding=3)uniform sampler2DArray b;layout(location=0)in vec2 p;layout(location=0)out vec4 o;void main(){o=textureLod(a,vec3(p,0),1)+texture(b,vec3(p,0));}')
        report,specs=self.transform(binary)
        self.assertIn('mask=0x9',report);self.assertIn('directional=0x8',report)
        self.assertEqual(specs,{20000:0,20003:0})
        # A retained accessor's word-zero call must expose the specialization
        # in its caller. Adreno rejects OpCopyObject directly from a spec value;
        # exact uint addition of zero is accepted by the GPU fixture.
        words=self.last_words;i=5;exposed=0
        while i<len(words):
            n,op=words[i]>>16,words[i]&65535
            if op==128 and n==5 and words[i+3] in self.last_specs:exposed+=1
            self.assertFalse(op==83 and n==4 and words[i+3] in self.last_specs)
            i+=n
        self.assertGreaterEqual(exposed,2)

    def test_inlined_compute_headers_validate_with_native_defaults(self):
        binary=self.compile('comp','#version 450\nlayout(local_size_x=1)in;layout(binding=0)uniform sampler2D a;layout(binding=3)uniform sampler2D b;layout(binding=1,std430)buffer O{vec4 v;}o;void main(){o.v=textureLod(a,vec2(.5),1)+texelFetch(b,ivec2(0),0);}')
        report,specs=self.transform(binary)
        self.assertIn('directional=0 ',report)
        self.assertEqual(specs,{20000:0,20003:0})

    def test_existing_user_specialization_is_preserved(self):
        binary=self.compile('comp','#version 450\nlayout(constant_id=20000)const uint user=7;layout(local_size_x=1)in;layout(binding=0)uniform sampler2D a;layout(binding=3)uniform sampler2D b;layout(binding=1,std430)buffer O{vec4 v;}o;void main(){o.v=textureLod(a,vec2(.5),1)+textureLod(b,vec2(.5),1)+vec4(user);}')
        report,specs=self.transform(binary)
        self.assertIn('mask=0x8',report)
        self.assertEqual(specs,{20000:7,20003:0})
