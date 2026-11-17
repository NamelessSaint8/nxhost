#!/usr/bin/env python3
"""Build synthetic shaders and a DMSV bundle for vknvn2_replay.c (no game data)."""
import argparse
import json
import struct
import subprocess
import sys
from pathlib import Path

repo = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(repo/'nxnative/dm/android/tools'))
import nvn2_mesh, shader_vk, dmsv_workgroup   # noqa: E402

def build_runtime(out, ndk, game):
    """Link the fixture with the same compiled objects as the Android host."""
    dm = repo/'nxnative/dm'
    subprocess.run([sys.executable, str(dm/'android/build.py'), '--game', game, '--ndk', str(ndk), '--out', str(out), '--only-compile', '--jobs', '4'], check=True)
    compiler = ndk/'toolchains/llvm/prebuilt/darwin-x86_64/bin/clang'
    includes = ['-include', str(dm/'android/compat/include/darwin_compat.h')]
    includes += ['-I'+str(dm/x) for x in ['android/compat/include','host','gfx/nvn','gfx/tex','gfx/nvn/include','third_party/vulkan-headers/include','android']]
    includes += ['-I'+str(out/'gen'/game)]
    obj = out/'replay.o'
    subprocess.run([str(compiler), '--target=aarch64-linux-android31', '-O1', '-g', '-DDM_ANDROID=1', '-fno-strict-aliasing', '-Wall', '-Werror'] + includes + ['-c', str(repo/'probes/vknvn2_replay.c'), '-o', str(obj)], check=True)
    subprocess.run([str(compiler), '--target=aarch64-linux-android31', '-fuse-ld=lld', '-Wl,-z,max-page-size=16384', '-Wl,--wrap=main,--wrap=prog_key', '-pie', '-o', str(out/'vknvn2_replay'), str(obj)] + [str(o) for o in sorted((out/'obj').glob('*.o'))] + ['-landroid','-llog','-lvulkan','-laaudio','-lnativewindow','-lmediandk','-lm','-ldl'], check=True)

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('out', type=Path)
    ap.add_argument('--ndk', type=Path, help='also build/link the backend replay executable (macOS NDK host)')
    ap.add_argument('--build-out', type=Path, help='isolated Android build folder')
    ap.add_argument('--game', default='0400C3F00006E000', help='host build profile; no game files are loaded')
    args = ap.parse_args()
    out = args.out.resolve()
    subprocess.run([sys.executable, str(repo/'probes/make_nvn2_proof.py'), str(out)], check=True, capture_output=True)
    metadata = json.loads((out/'conversion-results.json').read_text())['metadata']
    entries = []
    def add(key, stage, binary, info=None, bindings=()):
        io=shader_vk.spirv_bindings(binary)[2]
        header=[info['threads'],1,1] if info else io[1] if stage==0 else io[3] if stage==1 else [0,0,0]
        refl = struct.pack('<5I', len(bindings), 0, *header)
        for row in bindings:
            kind, desc, binding, *reg = row
            refl += struct.pack('<BBBBHHhBBii', kind, desc, 255, 0, binding, 1, reg[0] if reg else 0, 0, 0, -1, 0)
        if info: refl += nvn2_mesh.reflection(info, binary)
        entries.append((key, stage, binary, refl, int(info is not None)))
    def compile_glsl(name, stage, source):
        src = out/(name+'.'+stage); src.write_text(source)
        binary = out/(name+'.spv')
        target_env = 'vulkan1.0' if name == 'primitive-consumer' else 'vulkan1.2'
        subprocess.run(['glslangValidator', '-V', '--target-env', target_env, '-S', stage, str(src), '-o', str(binary)], check=True, capture_output=True)
        subprocess.run(['spirv-val', '--target-env', 'vulkan1.2', str(binary)], check=True)
        return binary.read_bytes()
    for key, name in enumerate(('task', 'empty', 'mesh', 'direct'), 1):
        info = metadata[name]; stage = 'task' if info['kind']==6 else 'mesh'
        source = (out/(name+'.'+stage)).read_text()
        driver = 'layout(set=0,binding=10,std140) uniform DmDriver {uvec4 words[256];} dm_driver;\n'
        source = source.replace('void dm_stage_body()', driver+'void dm_stage_body()')
        base = 0x670 if info['kind']==6 else 0x770
        source = source.replace(f'sb.value!={info["kind"]+10}u', f'sb.value!={info["kind"]+10}u || dm_driver.words[{base//16}].z!=64u')
        add(key, info['kind'], compile_glsl(name+'-driver',stage,source), info, [(1,0,8),(4,1,9),(3,0,10)])
    for key, group in [(5, 1), (6, 0)]:
        source = f'#version 450\nlayout(location=0) in vec4 value;layout(location=0) out vec4 color;void main(){{color=value.x==1.0&&value.y=={group}.0?vec4(0,1,0,1):vec4(1,0,0,1);}}'
        add(key, 1, compile_glsl(str(key), 'frag', source))
    source = '#version 460\n#extension GL_EXT_mesh_shader : require\nlayout(local_size_x=32) in;layout(triangles,max_vertices=3,max_primitives=1) out;layout(location=0) perprimitiveEXT out vec4 value[];void main(){SetMeshOutputsEXT(3,1);if(gl_LocalInvocationIndex==0){gl_MeshVerticesEXT[0].gl_Position=vec4(-.75,-.75,0,1);gl_MeshVerticesEXT[1].gl_Position=vec4(.75,-.75,0,1);gl_MeshVerticesEXT[2].gl_Position=vec4(0,.75,0,1);gl_PrimitiveTriangleIndicesEXT[0]=uvec3(0,1,2);value[0]=vec4(0,1,0,1);}}'
    info = dict(metadata['direct'], vertex_lines=[28,29,30,31], primitive_lines=[32,33,34,35])
    add(7, 7, compile_glsl('primitive', 'mesh', source), info)
    # Plain fragment input: replay must select the PerPrimitiveEXT variant.
    fragment = '#version 450\nlayout(location=0) in vec4 value;layout(location=0) out vec4 color;void main(){color=value;}'
    binary = compile_glsl('primitive-consumer', 'frag', fragment)
    add(8, 1, binary)
    vertex = '#version 450\nlayout(location=0) out vec4 value;void main(){vec2 points[3]=vec2[3](vec2(-.75,-.75),vec2(.75,-.75),vec2(0,.75));gl_Position=vec4(points[gl_VertexIndex],0,1);value=vec4(0,1,0,1);}'
    add(9, 0, compile_glsl('vertex', 'vert', vertex))
    add(10, 1, binary)
    atlas_source = (repo/'probes/shaders/mapped-atlas.comp').read_text()
    original = compile_glsl('mapped-atlas-original','comp',atlas_source)
    binary, converted = shader_vk.compile_atlas(original,'cs',out/'mapped-atlas.spv')
    if converted != [0]: raise RuntimeError('mapped atlas fixture did not convert its sampler')
    binds, _, _ = shader_vk.spirv_bindings(binary)
    resources = {'sbufs':[{'binding':1,'cb_slot':0,'cb_offset':0x310//4,'flags':2},{'binding':2,'cb_slot':0,'cb_offset':0x320//4,'flags':0}]}
    classified = [shader_vk.classify('cs',b,resources) for b in binds]
    for binding in classified:
        if binding['binding'] in converted: binding['atlas']=True
    if any(b['kind']=='?' for b in classified): raise RuntimeError(classified)
    entries.append((11,5,binary,shader_vk.refl_bin(classified,b'', [32,1,1]),0))
    def reflected_compute(key, source, nvn2):
        binary = compile_glsl('driver-'+str(key),'comp',source)
        binds, local, _ = shader_vk.spirv_bindings(binary)
        res = {'sbufs':[{'binding':2,'cb_slot':0,'cb_offset':0x310//4,'flags':2}]}
        classified = [shader_vk.classify('cs',b,res) for b in binds]
        if any(b['kind']=='?' for b in classified): raise ValueError(classified)
        entries.append((key,5,binary,shader_vk.refl_bin(classified,b'',local),2 if nvn2 else 0))
    driver_source = (repo/'probes/shaders/driver-state.comp').read_text()
    reflected_compute(12,driver_source,True)
    reflected_compute(13,driver_source,False)
    writer = '#version 450\nlayout(local_size_x=1) in;layout(binding=0,std140) uniform cp_c24 {uvec4 words[16];} pushed;layout(binding=2,std430) buffer cp_s0 {uvec4 words[];} result;void main(){result.words[0]=pushed.words[0];}'
    reflected_compute(14,writer,True)
    vertex = '#version 450\nlayout(binding=0,std140)uniform vp_c24 {uvec4 words[16];} pushed;layout(location=0)out vec4 color;void main(){vec2 p[3]=vec2[3](vec2(-.75,-.75),vec2(.75,-.75),vec2(0,.75));gl_Position=vec4(p[gl_VertexIndex],0,1);color=vec4(float(pushed.words[0].x)/255.0,0,0,1);}'
    fragment = '#version 450\nlayout(binding=0,std140)uniform fp_c24 {uvec4 words[16];} pushed;layout(location=0)in vec4 color;layout(location=0)out vec4 result;void main(){result=vec4(color.r,vec2(pushed.words[0].yz)/255.0,float(pushed.words[15].w)/255.0);}'
    add(15,0,compile_glsl('push-vertex','vert',vertex),bindings=[(3,0,0,24)])
    add(16,1,compile_glsl('push-fragment','frag',fragment),bindings=[(3,0,0,24)])
    for key,name in [(17,'task'),(18,'mesh'),(19,'direct')]:
        info=metadata[name];stage='task' if info['kind']==6 else 'mesh'
        source=(out/(name+'-driver.'+stage)).read_text()
        declaration='layout(set=0,binding=11,std140)uniform DmPush {uvec4 words[16];} dm_push;\n'
        source=source.replace('void dm_stage_body()',declaration+'void dm_stage_body()')
        test='dm_push.words[0].x!=32u' if stage=='task' else 'dm_push.words[0].z!=96u'
        source=source.replace('sb.value!=',test+' || sb.value!=')
        add(key,info['kind'],compile_glsl(name+'-push',stage,source),info,[(1,0,8),(4,1,9),(3,0,10),(3,0,11,24)])
    image_source = '#version 450\nlayout(local_size_x=1)in;layout(r32f,binding=0)uniform image2D cp_i2d_tcb_48;layout(binding=2,std430)buffer cp_s0 {float value;} result;void main(){imageStore(cp_i2d_tcb_48,ivec2(0),vec4(.625));memoryBarrierImage();result.value=imageLoad(cp_i2d_tcb_48,ivec2(0)).x;}'
    typed = compile_glsl('formatless-image','comp',image_source)
    words=list(struct.unpack('<'+str(len(typed)//4)+'I',typed));i=5
    while i<len(words):
        n,op=words[i]>>16,words[i]&0xffff
        if op==25:words[i+8]=0
        i+=n
    binary,capabilities=shader_vk.formatless_image_capabilities(struct.pack('<'+str(len(words))+'I',*words))
    if capabilities!=[55,56]: raise ValueError('formatless fixture lacks independent capability repair')
    image_spv=out/'formatless-image.spv';image_spv.write_bytes(binary)
    subprocess.run(['spirv-val','--target-env','vulkan1.2',str(image_spv)],check=True,capture_output=True)
    binds,local,_=shader_vk.spirv_bindings(binary);classified=[shader_vk.classify('cs',b,{'sbufs':[{'binding':2,'cb_slot':0,'cb_offset':0x310//4,'flags':2}]}) for b in binds]
    if any(b['kind']=='?' for b in classified): raise ValueError(classified)
    entries.append((20,5,binary,shader_vk.refl_bin(classified,b'',local),2))
    vertex='#version 450\nlayout(location=0)out vec4 existing;void main(){vec2 p[3]=vec2[3](vec2(-.75,-.75),vec2(.75,-.75),vec2(0,.75));gl_Position=vec4(p[gl_VertexIndex],0,1);existing=vec4(1);}'
    pixel='#version 450\nlayout(location=0)in vec4 existing;layout(location=1)in vec2 a;layout(location=2)in vec3 b;layout(location=3)in vec4 c;layout(location=4)flat in ivec4 d;layout(location=5)flat in uvec4 e;layout(location=6)in vec4 f;layout(location=0)out vec4 color;void main(){bool ok=all(equal(existing,vec4(1)))&&all(equal(a,vec2(0)))&&all(equal(b,vec3(0)))&&all(equal(c,vec4(0,0,0,1)))&&all(equal(d,ivec4(0)))&&all(equal(e,uvec4(0)))&&all(equal(f,vec4(0,0,0,1)));color=ok?vec4(0,1,0,1):vec4(1,0,0,1);}'
    fragment=compile_glsl('padded-consumer','frag',pixel)
    padded,added,skipped=shader_vk.dmsv_pad.pad(compile_glsl('padded-producer','vert',vertex),[fragment])
    if added!=[1,2,3,4,5,6] or skipped:raise ValueError('incomplete padded vertex fixture')
    path=out/'padded-producer-final.spv';path.write_bytes(padded)
    subprocess.run(['spirv-val','--target-env','vulkan1.2',str(path)],check=True,capture_output=True)
    add(21,0,padded);add(22,1,fragment)
    vertex='#version 450\nvoid main(){vec2 p[3]=vec2[3](vec2(-1,-1),vec2(3,-1),vec2(-1,3));gl_Position=vec4(p[gl_VertexIndex],0,1);}'
    add(23,0,compile_glsl('implicit-atlas-vertex','vert',vertex))
    source=(repo/'probes/shaders/implicit-atlas.frag').read_text()
    original=compile_glsl('implicit-atlas-original','frag',source)
    binary,converted=shader_vk.compile_atlas(original,'ps',out/'implicit-atlas.spv')
    if converted!=[0,1]:raise ValueError('implicit atlas fixture did not convert both array samplers')
    binds,_,io=shader_vk.spirv_bindings(binary)
    classified=[shader_vk.classify('ps',b,{}) for b in binds]
    for b in classified:
        if b['binding'] in converted:b['atlas']=True
    if any(b['kind']=='?' for b in classified):raise ValueError(classified)
    entries.append((24,1,binary,shader_vk.refl_bin(classified,b'',io[3]),4))
    source=(repo/'probes/shaders/offset-atlas.frag').read_text()
    original=compile_glsl('offset-atlas-original','frag',source)
    binary,converted=shader_vk.compile_atlas(original,'ps',out/'offset-atlas.spv')
    if converted!=[0,1]:raise ValueError('offset atlas fixture did not convert both array samplers')
    binds,_,io=shader_vk.spirv_bindings(binary);classified=[shader_vk.classify('ps',b,{}) for b in binds]
    for b in classified:
        if b['binding'] in converted:b['atlas']=True
    if any(b['kind']=='?' for b in classified):raise ValueError(classified)
    entries.append((25,1,binary,shader_vk.refl_bin(classified,b'',io[3]),4))
    source = '#version 450\nlayout(location=0)out vec4 a;layout(location=1)out vec4 b;layout(location=2)out vec4 c;void main(){a=uintBitsToFloat(uvec4(17,31,63,127));a.z=uintBitsToFloat(floatBitsToUint(a.x)+9u);a.x=uintBitsToFloat(floatBitsToUint(a.z)+9u);b=intBitsToFloat(ivec4(-7,-23,-63,-127));c=vec4(.25,.5,.75,1);}'
    add(26,1,compile_glsl('integer-exports','frag',source))
    source=atlas_source.replace('sampler2DArray','sampler2D').replace('ivec3(q.fetch.xy,int(q.coordinate.w))','q.fetch.xy').replace('vec3(q.coordinate.xy,q.coordinate.w)','q.coordinate.xy').replace('vec4(textureSize(cp_t2da_tcb_8,q.fetch.w),textureQueryLevels(cp_t2da_tcb_8))','vec4(textureSize(cp_t2da_tcb_8,q.fetch.w),0,textureQueryLevels(cp_t2da_tcb_8))')
    original=compile_glsl('uncompressed-2d-original','comp',source)
    binary,converted=shader_vk.compile_atlas(original,'cs',out/'uncompressed-2d.spv')
    if converted!=[0]:raise ValueError('2D fixture did not convert its sampler')
    binds,local,_=shader_vk.spirv_bindings(binary)
    classified=[shader_vk.classify('cs',b,{'sbufs':[{'binding':1,'cb_slot':0,'cb_offset':0x310//4,'flags':2},{'binding':2,'cb_slot':0,'cb_offset':0x320//4,'flags':0}]}) for b in binds]
    for b in classified:
        if b['binding'] in converted:b['atlas']=True
    if any(b['kind']=='?' for b in classified):raise ValueError(classified)
    entries.append((27,5,binary,shader_vk.refl_bin(classified,b'',local),0))
    source='#version 450\nlayout(local_size_x=32)in;layout(binding=0)uniform sampler2DArray cp_t2da_tcb_8;layout(binding=1)uniform sampler2DArray cp_t2da_tcb_A;layout(binding=2,std430)buffer cp_s0{vec4 values[];}o;struct Q{vec4 p;ivec4 f;};layout(binding=3,std430)readonly buffer cp_s1{Q q[];}i;void main(){uint n=gl_GlobalInvocationID.x;if(n>=i.q.length())return;vec4 p=i.q[n].p;o.values[n*2]=textureLod(cp_t2da_tcb_8,vec3(p.xy,p.w),p.z);o.values[n*2+1]=textureLod(cp_t2da_tcb_A,vec3(p.xy,p.w),p.z);}'
    original=compile_glsl('explicit-lod-native','comp',source)
    binary,converted=shader_vk.compile_atlas(original,'cs',out/'explicit-lod.spv')
    if converted!=[0,1]:raise ValueError('explicit LOD fixture did not convert both samplers')
    binds,local,_=shader_vk.spirv_bindings(binary)
    classified=[shader_vk.classify('cs',b,{'sbufs':[{'binding':2,'cb_slot':0,'cb_offset':0x310//4,'flags':2},{'binding':3,'cb_slot':0,'cb_offset':0x320//4,'flags':0}]}) for b in binds]
    for b in classified:
        if b['binding'] in converted:b['atlas']=True
    if any(b['kind']=='?' for b in classified):raise ValueError(classified)
    entries.append((28,5,binary,shader_vk.refl_bin(classified,b'',local),0))
    for key, source in [
        (29, '#version 450\nlayout(local_size_x=1)in;layout(r32f,binding=0)uniform image2D cp_i2d_tcb_48;layout(binding=2,std430)buffer cp_s0{uint words[];}o;void main(){imageStore(cp_i2d_tcb_48,ivec2(0),vec4(uintBitsToFloat(o.words[0])));memoryBarrierImage();o.words[1]=floatBitsToUint(imageLoad(cp_i2d_tcb_48,ivec2(0)).x);}'),
        (30, '#version 450\nlayout(local_size_x=1)in;layout(binding=1)uniform sampler2D cp_t2d_tcb_8;layout(binding=2,std430)buffer cp_s0{uint words[];}o;void main(){o.words[2]=floatBitsToUint(texelFetch(cp_t2d_tcb_8,ivec2(0),0).x);}')]:
        binary=compile_glsl('storage-bits-'+str(key),'comp',source)
        words=list(struct.unpack('<'+str(len(binary)//4)+'I',binary));i=5
        while i<len(words):
            n,op=words[i]>>16,words[i]&0xffff
            if op==25 and words[i+7]==2:words[i+8]=0
            i+=n
        binary,_=shader_vk.formatless_image_capabilities(struct.pack('<'+str(len(words))+'I',*words))
        binds,local,_=shader_vk.spirv_bindings(binary)
        classified=[shader_vk.classify('cs',b,{'sbufs':[{'binding':2,'cb_slot':0,'cb_offset':0x310//4,'flags':2}]}) for b in binds]
        if any(b['kind']=='?' for b in classified):raise ValueError(classified)
        entries.append((key,5,binary,shader_vk.refl_bin(classified,b'',local),2))
    for key,kind,expected in [(31,'int','ivec4(-7,12,123,1)'),(32,'uint','uvec4(7,12,123,1)')]:
        conversion='floatBitsToInt' if kind=='int' else 'floatBitsToUint'
        source=f'#version 450\nlayout(location=0)in vec4 raw;layout(location=0)out vec4 color;void main(){{vec2 p[3]=vec2[3](vec2(-1,-1),vec2(3,-1),vec2(-1,3));gl_Position=vec4(p[gl_VertexIndex],0,1);color=all(equal({conversion}(raw),{expected}))?vec4(0,1,0,1):vec4(1,0,0,1);}}'
        add(key,0,compile_glsl('raw-vertex-'+kind,'vert',source))
    source='#version 450\nlayout(local_size_x=64)in;shared uint tile[12288];layout(binding=2,std430)buffer cp_s0{uint words[];}o;void main(){uvec3 p=gl_WorkGroupID,n=gl_NumWorkGroups;uint group=(p.z*n.y+p.y)*n.x+p.x,lane=gl_LocalInvocationID.x;for(uint i=lane;i<12288;i+=64)tile[i]=(group*817u)^i;barrier();atomicAdd(tile[12287],1u);barrier();for(uint i=lane;i<12288;i+=64)o.words[group*12288u+i]=tile[(i+17u)%12288u];}'
    original=compile_glsl('shared-oversize-original','comp',source)
    binary,spill_bytes=dmsv_workgroup.spill(original,3,32768,out/'shared-spill.spv')
    binds,local,_=shader_vk.spirv_bindings(original)
    classified=[shader_vk.classify('cs',b,{'sbufs':[{'binding':2,'cb_slot':0,'cb_offset':0x310//4,'flags':2}]}) for b in binds]
    meta=dmsv_workgroup.reflection(shader_vk.refl_bin(classified,b'',local),3,spill_bytes)
    entries.append((33,5,binary,meta,10))
    binary=compile_glsl('global-memory','comp',(repo/'probes/shaders/global-memory.comp').read_text())
    binds,local,_=shader_vk.spirv_bindings(binary)
    resources={'sbufs':[{'binding':0,'cb_slot':0,'cb_offset':0x310//4,'flags':0},
                        {'binding':1,'cb_slot':255,'cb_offset':0,'flags':0},
                        {'binding':2,'cb_slot':255,'cb_offset':1,'flags':1},
                        {'binding':3,'cb_slot':0,'cb_offset':0x320//4,'flags':1}]}
    classified=[shader_vk.classify('cs',b,resources) for b in binds]
    entries.append((34,5,binary,shader_vk.refl_bin(classified,b'',local),0))
    source=(repo/'probes/shaders/global-memory.comp').read_text().replace('#version 460','#version 460\n#define COOPERATIVE 1',1)
    binary=compile_glsl('global-memory-cooperative','comp',source)
    binds,local,_=shader_vk.spirv_bindings(binary)
    classified=[shader_vk.classify('cs',b,resources) for b in binds]
    entries.append((35,5,binary,shader_vk.refl_bin(classified,b'',local),0))
    entries.sort()
    offset = 12+32*len(entries); table, blobs = [], []
    for key, stage, binary, refl, flag in entries:
        table.append(struct.pack('<Q6I', key, stage, offset, len(binary), offset+len(binary), len(refl), flag))
        blobs.extend((binary, refl)); offset += len(binary)+len(refl)
    (out/'replay.dmsv').write_bytes(struct.pack('<4s2I', b'DMSV', 1, len(entries))+b''.join(table)+b''.join(blobs))
    print(f'{len(entries)} replay shaders -> {out/"replay.dmsv"}')
    if args.ndk: build_runtime((args.build_out or out/'runtime').resolve(), args.ndk.resolve(), args.game)

if __name__ == '__main__': main()
