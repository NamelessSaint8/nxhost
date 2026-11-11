#!/usr/bin/env python3
"""Build a bounded NVN2 Vulkan proof; optional real stages stay external.

make_nvn2_proof.py OUT [--real-mesh MAC_STAGE_EXPORT]
Requires the in-repo translator/spirv-cross, glslangValidator and spirv-val.
"""
from pathlib import Path
import argparse,json,subprocess,sys,struct,math
repo=Path(__file__).resolve().parent.parent
ap=argparse.ArgumentParser(description=__doc__)
ap.add_argument('out',type=Path)
ap.add_argument('--real-mesh',type=Path,help='external folder of .ctl/.area and translated/<key>.spv')
ap.add_argument('--xlate',type=Path,default=repo/'nxnative/dm/gfx/tools/dmsh_xlate_bin/dmsh_xlate')
a=ap.parse_args()
sys.path.insert(0,str(repo/'nxnative/dm/gfx/tools'))
sys.path.insert(0,str(repo/'nxnative/dm/android/tools'))
import dmsh_nvn2_mesh,nvn2_mesh
def instruction(hi,lo): return struct.pack('<QQ',lo,hi)
def mov(value): return instruction(0x000fc60000000f00,value<<32|0x7802)
def write(offset,region=3,word=True):
 return instruction(0x000fe20000000000|1<<15|region<<12|int(word)<<11,offset<<40|255<<24|0x7927)
def read(offset): return instruction(0x000fe20000007800,offset<<40|255<<24|0x7923)
out=a.out.resolve();out.mkdir(parents=True,exist_ok=True)
cross=repo/'nxnative/dm/gfx/tools/spirv_cross_bin/spirv-cross'
old=a.real_mesh
infos={p.stem:dmsh_nvn2_mesh.metadata(p.read_bytes(),p.with_suffix('.area').read_bytes()) for p in old.glob('*.ctl')} if old else {}
synthetic=[]
for name in ('task','empty','mesh','direct'):
 task=name in ('task','empty')
 info=dict(kind=6 if task else 7,threads=32,attr_words=8 if task else 192,input_words=8,map_words=7,max_vertices=3,max_primitives=1,vertex_lines=[28,29,30,31,32,33],primitive_lines=[],task_input=name=='mesh')
 code=bytearray(128)
 code+=instruction(0x000e220000002100,0x0000000000027919)+instruction(0x000fe20003f06070,1<<32|2<<24|0x780c)+instruction(0x000fea0003800000,0x094d)
 if task:code+=read(0)+write(16)+mov(0 if name=='empty' else 1)+write(4)
 else:
  for vertex,point in enumerate(((-.75,-.75),(.75,-.75),(0,.75))):
   for component,value in enumerate((*point,0.,1.)):
    bits=struct.unpack('<I',struct.pack('<f',value))[0];code+=mov(bits)+write((component*32+vertex)*4)
   code+=read(16 if name=='mesh' else 0)+write((4*32+vertex)*4)
   code+=read(0)+write((5*32+vertex)*4)
  code+=mov(1)+write(3,0)
  for i in range(3):code+=mov(i)+write(4+i,0,False)
 code+=instruction(0x000fea0003800000,0x794d)
 binary=out/(name+'.bin');binary.write_bytes(code)
 synthetic.append(dict(key=name,stage='cs',arch='sm86',code=str(binary),debug=False,tex={},img={},attr={},fout={},local=[32,1,1],nvn2_stage=[info['kind'],8,info['attr_words'],7]))
 infos[name]=info
(out/'jobs.json').write_text(json.dumps(synthetic));r=subprocess.run([str(a.xlate),str(out/'jobs.json'),str(out)],capture_output=True,text=True)
if r.returncode:raise RuntimeError(r.stdout+r.stderr)
failed=[]
for key,info in infos.items():
 source_spv=(out if key in ('task','empty','mesh','direct') else old/'translated')/(key+'.spv')
 glsl=subprocess.run([str(cross),str(source_spv),'--vulkan-semantics','--version','460'],capture_output=True,text=True,check=True).stdout
 stage='task' if info['kind']==6 else 'mesh'
 glsl=nvn2_mesh.compose(glsl,info,0 if stage=='task' else 1)
 if key in ('task','empty','mesh','direct'):
  abi='layout(set='+str(0 if stage=='task' else 1)+',binding=8,std140) uniform Abi { uint value; } abi;\nlayout(set='+str(0 if stage=='task' else 1)+',binding=9,std430) readonly buffer Storage {uint value;} sb;\n'
  glsl=glsl.replace('void dm_stage_body()',abi+'void dm_stage_body()')
  failure='dm_stage_attr[1]=0u;' if stage=='task' else 'for(uint i=0u;i<3u;i++)dm_stage_attr[128u+i]=0u;'
  glsl=glsl.replace('dm_stage_body();',f'dm_stage_body(); if(tid==0u && (abi.value!={info["kind"]}u || sb.value!={info["kind"]+10}u)){{{failure}}}')
 src=out/(key+'.'+stage);src.write_text(glsl)
 spv=out/(key+'.vk.spv')
 r=subprocess.run(['glslangValidator','-V','--target-env','vulkan1.2','-Os','-S',stage,str(src),'-o',str(spv)],capture_output=True,text=True)
 if not r.returncode:r=subprocess.run(['spirv-val','--target-env','vulkan1.2',str(spv)],capture_output=True,text=True)
 if r.returncode:failed.append((key,r.stdout+r.stderr))
 print(key,stage,'PASS' if not r.returncode else 'FAIL',flush=True)
(out/'conversion-results.json').write_text(json.dumps({'failed':failed,'metadata':infos},indent=2)+'\n')
for k,e in failed:print(k,e[:1800])
if failed:raise SystemExit(1)

# Resource layouts make the optional real-stage pipeline checks valid without
# binding or dispatching any of the game's own buffers.
manifest=[]
for key,info in infos.items():
 if any(k==key for k,_ in failed):continue
 reflected=json.loads(subprocess.run([str(cross),str(out/(key+'.vk.spv')),'--reflect'],capture_output=True,text=True,check=True).stdout)
 rows=[]
 for group,descriptor in [('ubos',6),('ssbos',7),('textures',1),('separate_images',2),('separate_samplers',0),('images',3)]:
  for entry in reflected.get(group,[]):
   count=math.prod(entry.get('array',[1]))
   if count<=0:raise ValueError('runtime descriptor array needs an explicit proof layout')
   kind=4 if group=='textures' and 'Buffer' in entry.get('type','') else 5 if group=='images' and 'Buffer' in entry.get('type','') else descriptor
   rows.append(f'{entry["binding"]} {kind} {count}')
 (out/(key+'.layout.tsv')).write_text('\n'.join(rows)+'\n')
 if len(key)==16:manifest.append(f'{key} {info["kind"]} {int(info.get("task_input",False))}')
(out/'real-stages.tsv').write_text('\n'.join(manifest)+'\n')
# Use a complete producer/consumer pipeline for the driver check. The fixture
# consumes all declared mesh outputs; it does not dispatch the game programs.
for key,info in infos.items():
 if len(key)!=16:continue
 mesh=infos['mesh'] if info['kind']==6 else info
 vertex=sorted({(x-32)//4 for x in mesh['vertex_lines'] if x>=32})
 primitive=sorted({(x-32)//4 for x in mesh['primitive_lines']})
 source='#version 460\n#extension GL_EXT_mesh_shader : require\nlayout(location=0) out vec4 color;\n'
 source+=''.join(f'layout(location={slot}) in vec4 v{slot};\n' for slot in vertex)
 source+=''.join(f'layout(location={slot}) perprimitiveEXT flat in vec4 p{slot};\n' for slot in primitive)
 source+='void main(){color=clamp(abs(vec4(0)'+''.join(f'+v{slot}' for slot in vertex)+''.join(f'+p{slot}' for slot in primitive)+'),vec4(0),vec4(1));}\n'
 fragment=out/(key+'.proof.frag');fragment.write_text(source)
 subprocess.run(['glslangValidator','-V','--target-env','vulkan1.2','-S','frag',str(fragment),'-o',str(fragment)+'.spv'],check=True,capture_output=True)

for stage in ('frag','comp'):
 subprocess.run(['glslangValidator','-V','--target-env','vulkan1.2','-S',stage,str(repo/('probes/shaders/nvn2-proof.'+stage)),'-o',str(out/('proof.'+stage+'.spv'))],check=True)
print('Built proof:',out,flush=True)
