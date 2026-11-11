"""Preserve used distance outputs and lower oversized workgroup storage."""
import shutil
import re
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT/'nxnative/dm/android/tools'))
import dmsv_workgroup
import workgroup_glsl


def chunks(binary):
    words=struct.unpack('<'+'I'*(len(binary)//4),binary);result=[];i=5
    while i<len(words):
        n=words[i]>>16;result.append(words[i:i+n]);i+=n
    return result


@unittest.skipUnless(all(shutil.which(t) for t in ('clang','glslangValidator','spirv-val')),'shader tools unavailable')
class Limits(unittest.TestCase):
    @unittest.skipUnless(all(shutil.which(t) for t in ('spirv-as','spirv-dis')),'SPIR-V assembly tools unavailable')
    def test_extended_instruction_literal_is_not_output_pointer(self):
        with tempfile.TemporaryDirectory(prefix='android-distance-literal-') as directory:
            d=Path(directory);cli=d/'prune';source=d/'case.vert';raw=d/'raw.spv';out=d/'out.spv'
            subprocess.run(['clang','-std=c11','-Wall','-Wextra','-Werror','-fsanitize=address,undefined',str(ROOT/'probes/spv_limits.c'),'-o',str(cli)],check=True,capture_output=True)
            source.write_text('#version 450\nlayout(location=0)in float a;out gl_PerVertex{vec4 gl_Position;float gl_PointSize;float gl_ClipDistance[8];float gl_CullDistance[1];};void main(){gl_Position=vec4(min(a,0.5),0,0,1);}')
            subprocess.run(['glslangValidator','-V','--target-env','vulkan1.2',str(source),'-o',str(raw)],check=True,capture_output=True)
            asm=subprocess.check_output(['spirv-dis','--raw-id',str(raw)],text=True)
            block=re.search(r'OpMemberDecorate %(\d+) \d+ BuiltIn ClipDistance',asm)[1]
            pointer=re.search(r'%(\d+) = OpTypePointer Output %'+block+r'\b',asm)[1]
            variable=re.search(r'%(\d+) = OpVariable %'+pointer+r' Output',asm)[1]
            # FMin is GLSL.std.450 opcode37. Make its literal collide with the
            # interface variable ID, without changing any actual references.
            fresh=struct.unpack_from('<I',raw.read_bytes(),12)[0]+1
            asm=re.sub(r'%(\d+)\b',lambda m:'%'+('37' if m[1]==variable else str(fresh) if m[1]=='37' else m[1]),asm)
            (d/'case.spvasm').write_text(asm)
            subprocess.run(['spirv-as','--preserve-numeric-ids','--target-env','spv1.5',str(d/'case.spvasm'),'-o',str(raw)],check=True,capture_output=True)
            subprocess.run([str(cli),str(raw),str(out)],check=True,capture_output=True)
            subprocess.run(['spirv-val','--target-env','vulkan1.2',str(out)],check=True,capture_output=True)
            members={w[4] for w in chunks(out.read_bytes()) if w[0]&65535==72 and len(w)==5 and w[3]==11}
            self.assertNotIn(3,members);self.assertNotIn(4,members)

    def test_distance_members_and_shifted_access(self):
        with tempfile.TemporaryDirectory(prefix='android-limits-') as directory:
            d=Path(directory);cli=d/'prune'
            subprocess.run(['clang','-std=c11','-Wall','-Wextra','-Werror','-fsanitize=address,undefined',str(ROOT/'probes/spv_limits.c'),'-o',str(cli)],check=True,capture_output=True)
            for active in ('','gl_CullDistance[0]=0.75;','for(int i=0;i<8;i++)gl_ClipDistance[i]=1.0;'):
                source=d/'case.vert';source.write_text('#version 450\nout gl_PerVertex{vec4 gl_Position;float gl_PointSize;float gl_ClipDistance[8];float gl_CullDistance[1];};void main(){gl_Position=vec4(0,0,0,1);gl_PointSize=1;'+active+'}')
                raw=d/'raw.spv';out=d/'out.spv'
                subprocess.run(['glslangValidator','-V','--target-env','vulkan1.2',str(source),'-o',str(raw)],check=True,capture_output=True)
                subprocess.run([str(cli),str(raw),str(out)],check=True,capture_output=True)
                subprocess.run(['spirv-val','--target-env','vulkan1.2',str(out)],check=True,capture_output=True)
                members={w[4] for w in chunks(out.read_bytes()) if w[0]&65535==72 and len(w)==5 and w[3]==11}
                self.assertEqual(3 in members,'ClipDistance[i]' in active)
                self.assertEqual(4 in members,'CullDistance[0]' in active)
                again=d/'again.spv';subprocess.run([str(cli),str(out),str(again)],check=True,capture_output=True)
                self.assertEqual(out.read_bytes(),again.read_bytes())
            # A whole-block load has an unknown use of every member. Keep it.
            binary=raw.read_bytes();words=list(struct.unpack('<'+'I'*(len(binary)//4),binary));instructions=chunks(binary)
            block=next(w[1] for w in instructions if w[0]&65535==72 and w[3:]==(11,3))
            pointer=next(w[1] for w in instructions if w[0]&65535==32 and w[2:]==(3,block))
            variable=next(w[2] for w in instructions if w[0]&65535==59 and w[1]==pointer)
            at=5
            while words[at]&65535!=248:at+=words[at]>>16
            at+=words[at]>>16
            while words[at]&65535==59:at+=words[at]>>16
            words[at:at]=[4<<16|61,block,words[3],variable];words[3]+=1
            raw.write_bytes(struct.pack('<'+'I'*len(words),*words));subprocess.run(['spirv-val','--target-env','vulkan1.2',str(raw)],check=True,capture_output=True)
            subprocess.run([str(cli),str(raw),str(out)],check=True,capture_output=True);self.assertEqual(raw.read_bytes(),out.read_bytes())

    def test_workgroup_buffer_and_barriers(self):
        with tempfile.TemporaryDirectory(prefix='android-workgroup-') as directory:
            d=Path(directory);source=d/'source.comp'
            source.write_text('#version 450\nlayout(local_size_x=64)in;shared uint words[12288];layout(binding=2,std430)buffer Output{uint values[];}o;void main(){uint i=gl_LocalInvocationID.x;words[i]=i;barrier();atomicAdd(words[12287],1);barrier();o.values[i]=words[(i+1)%64];}')
            raw=d/'raw.spv';subprocess.run(['glslangValidator','-V','--target-env','vulkan1.2',str(source),'-o',str(raw)],check=True,capture_output=True)
            self.assertEqual(dmsv_workgroup.shared_bytes(raw.read_bytes()),49152)
            cli=d/'limits'
            subprocess.run(['clang','-std=c11','-Wall','-Wextra','-Werror','-fsanitize=address,undefined',str(ROOT/'probes/spv_limits.c'),'-o',str(cli)],check=True,capture_output=True)
            self.assertEqual(subprocess.check_output([str(cli),str(raw)],text=True).strip(),'49152')
            lowered,bytes_=dmsv_workgroup.spill(raw.read_bytes(),3,32768,d/'lowered.spv')
            self.assertEqual(bytes_,49152);self.assertEqual(dmsv_workgroup.shared_bytes(lowered),0)
            self.assertEqual(subprocess.check_output([str(cli),str(d/'lowered.spv')],text=True).strip(),'0')
            instructions=chunks(lowered);constants={w[2]:w[3] for w in instructions if w[0]&65535==43 and len(w)==4}
            barriers=[constants[w[3]] for w in instructions if w[0]&65535==224]
            self.assertEqual(len(barriers),2);self.assertTrue(all(v&0x40 and not v&0x100 for v in barriers))
            self.assertEqual(workgroup_glsl.compose(source.read_text(),65536,3),(source.read_text(),0))
            with self.assertRaises(ValueError):workgroup_glsl.compose('shared uint a[12288];void main(){use(a);}',32768,3)


if __name__=='__main__':unittest.main()
