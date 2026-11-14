"""NVN2 stage-buffer compute IR to Vulkan EXT task/mesh GLSL.

The body remains a function: native early EXIT must not bypass the uniform
wrapper barriers or EXT output/emission calls. Metadata uses the same NVN2
layout decoder as Metal; resources retain their original descriptor bindings.
"""
import re

# The pipeline builder selects one common payload layout for both stages, so
# every task and task-fed mesh must declare the same one. 4 KiB is the largest
# any title has needed here (Ocarina of Time's mesh stage buffers take 804
# words) and stays inside the Adreno combined payload/shared limit.
PAYLOAD_WORDS = 1024


def compose(source, info, descriptor_set=0, payload_words=PAYLOAD_WORDS):
    """Wrap spirv-cross's Vulkan GLSL output of a translated stage-buffer body."""
    if info['kind'] not in (6, 7) or not 1 <= info['threads'] <= 32:
        raise ValueError('unsupported NVN2 task/mesh launch')
    needed = info['attr_words'] if info['kind'] == 6 else info['input_words']
    if needed > payload_words:
        raise ValueError('NVN2 payload exceeds selected pipeline payload layout')
    if 'layout(push_constant)' in source or re.search(r'layout\s*\(\s*push_constant', source):
        raise ValueError('NVN2 draw push constant collision')
    if len(re.findall(r'\bvoid main\(\)', source)) != 1:
        raise ValueError('NVN2 body has no unique entry')
    source = re.sub(r'^#version \d+', '#version 460\n#extension GL_EXT_mesh_shader : require', source, count=1, flags=re.M)
    source = re.sub(r'layout\(local_size_x\s*=.*?\) in;',
                    f'layout(local_size_x={info["threads"]},local_size_y=1,local_size_z=1) in;', source, count=1)
    source = re.sub(r'\bset\s*=\s*0\b', f'set = {descriptor_set}', source)
    source = source.replace('void main()', 'void dm_stage_body()')
    source = re.sub(r'\bgl_GlobalInvocationID\b', '(dm_group*uvec3(gl_WorkGroupSize)+gl_LocalInvocationID)', source)
    source = re.sub(r'\bgl_WorkGroupID\b', 'dm_group', source)
    source = re.sub(r'\bgl_NumWorkGroups\b', 'uvec3(dm_draw.count,1,1)', source)
    start = source.index('layout(local_size_x')
    common = ('layout(push_constant) uniform DmDraw { uint first; uint count; } dm_draw;\n'
              'uvec3 dm_group;\n')
    if info['kind'] == 6 or info.get('task_input'):
        common += f'struct DmPayload {{ uint words[{payload_words}]; }};\ntaskPayloadSharedEXT DmPayload dm_payload;\n'
    source = source[:start] + common + source[start:]
    group = 'gl_WorkGroupID' if info.get('task_input') else 'uvec3(gl_WorkGroupID.x+dm_draw.first,gl_WorkGroupID.yz)'
    body = '\nvoid main() {\n    uint tid=gl_LocalInvocationIndex;\n    dm_group=' + group + ';\n'
    if info['kind'] == 6:
        body += f'    for(uint i=tid;i<{info["attr_words"]}u;i+={info["threads"]}u) dm_stage_attr[i]=0u;\n'
        body += '    barrier();\n    dm_stage_body();\n    groupMemoryBarrier(); barrier();\n'
        body += f'    for(uint i=tid;i<{info["attr_words"]}u;i+={info["threads"]}u) dm_payload.words[i]=dm_stage_attr[i];\n'
        # EmitMeshTasksEXT is a workgroup-wide termination, never lane-0-only.
        return source + body + '    EmitMeshTasksEXT(dm_stage_attr[1],1,1);\n}\n'
    vertex, primitive = info['vertex_lines'], info['primitive_lines']
    if any(x < 28 or x >= 160 for x in vertex) or any(x < 32 or x >= 160 for x in primitive):
        raise ValueError('unsupported NVN2 output builtin')
    declarations = f'\nlayout(triangles,max_vertices={info["max_vertices"]},max_primitives={info["max_primitives"]}) out;\n'
    vertex_slots = sorted({(x-32)//4 for x in vertex if x >= 32} | set(info.get('extra_outputs', [])))
    if set(vertex_slots) & {(x-32)//4 for x in primitive}:
        raise ValueError('overlapping NVN2 vertex and primitive output locations')
    for slot in vertex_slots:
        declarations += f'layout(location={slot}) out vec4 dm_v{slot}[];\n'
    for slot in sorted({(x-32)//4 for x in primitive}):
        declarations += f'layout(location={slot}) perprimitiveEXT out vec4 dm_p{slot}[];\n'
    if 'shared uint dm_stage_input[' in source:
        value = 'dm_payload.words[i]' if info.get('task_input') else '0u'
        body += f'    for(uint i=tid;i<{info["input_words"]}u;i+={info["threads"]}u) dm_stage_input[i]={value};\n'
    body += '    if(tid==0u)dm_stage_map[0]=0u;\n    barrier();\n    dm_stage_body();\n    groupMemoryBarrier(); barrier();\n'
    body += f'    SetMeshOutputsEXT({info["max_vertices"]}u,dm_stage_map[0]);\n'
    body += f'    for(uint i=tid;i<{info["max_vertices"]}u;i+={info["threads"]}u) {{\n'
    body += '        gl_MeshVerticesEXT[i].gl_Position=vec4(0);\n'
    for slot in vertex_slots:
        body += f'        dm_v{slot}[i]=vec4(0,0,0,1);\n'
    for j, word in enumerate(vertex):
        field = f'gl_MeshVerticesEXT[i].gl_Position.{"xyzw"[word-28]}' if word < 32 else f'dm_v{(word-32)//4}[i].{"xyzw"[(word-32)%4]}'
        body += f'        {field}=uintBitsToFloat(dm_stage_attr[(i/32u)*{len(vertex)*32}u+i%32u+{j*32}u]);\n'
    body += '    }\n'
    base = (info['max_vertices']+31)//32 * len(vertex)*32
    body += f'    for(uint i=tid;i<dm_stage_map[0];i+={info["threads"]}u) {{\n'
    for slot in sorted({(x-32)//4 for x in primitive}):
        body += f'        dm_p{slot}[i]=vec4(0,0,0,1);\n'
    for j, word in enumerate(primitive):
        body += f'        dm_p{(word-32)//4}[i].{"xyzw"[(word-32)%4]}=uintBitsToFloat(dm_stage_attr[{base}u+(i/32u)*{len(primitive)*32}u+i%32u+{j*32}u]);\n'
    body += '        gl_PrimitiveTriangleIndicesEXT[i]=uvec3(dm_stage_map[4u+3u*i],dm_stage_map[5u+3u*i],dm_stage_map[6u+3u*i]);\n    }\n}\n'
    return source + declarations + body


def reflection(info, spv, payload_words=PAYLOAD_WORDS):
    """DMSV mesh trailer; count the final SPIR-V's actual workgroup allocations."""
    import struct
    words = struct.unpack(f'<{len(spv)//4}I', spv)
    types, constants, variables = {}, {}, []
    i = 5
    while i < len(words):
        n, op = words[i] >> 16, words[i] & 0xffff
        if not n or i+n > len(words): raise ValueError('malformed task/mesh SPIR-V')
        ins = words[i:i+n]
        if 20 <= op <= 32: types[ins[1]] = (op, ins[2:])
        elif op == 43 and n == 4: constants[ins[2]] = ins[3]
        elif op == 59 and ins[3] in (4, 5402): variables.append((ins[1], ins[3]))
        i += n
    def size(ident):
        op, args = types[ident]
        if op in (21, 22): return args[0]//8
        if op in (23, 24): return size(args[0])*args[1]
        if op == 28: return size(args[0])*constants[args[1]]
        if op == 30: return sum(size(x) for x in args)
        if op == 32: return size(args[1])
        raise ValueError(f'unsupported task/mesh shared type {op}')
    shared = sum(size(ty) for ty, storage in variables if storage == 4)
    payload = sum(size(ty) for ty, storage in variables if storage == 5402)
    expected = payload_words*4 if info['kind'] == 6 or info.get('task_input') else 0
    if payload != expected: raise ValueError('compiled task payload differs from selected ABI')
    vm = sum(1 << x for x in ({(w-32)//4 for w in info['vertex_lines'] if w >= 32} | set(info.get('extra_outputs', []))))
    pm = sum(1 << x for x in {(w-32)//4 for w in info['primitive_lines']})
    return struct.pack('<9I', 1, info['threads'], payload, shared, info['max_vertices'], info['max_primitives'], pm, vm, bool(info.get('task_input')))


def main():
    import argparse
    import json
    from pathlib import Path
    import subprocess
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('spv', type=Path, help='translated stage-buffer compute SPIR-V')
    parser.add_argument('metadata', type=Path, help='JSON from dmsh_nvn2_mesh.metadata')
    parser.add_argument('out', type=Path)
    parser.add_argument('--set', type=int, default=0, dest='descriptor_set')
    parser.add_argument('--payload-words', type=int, default=PAYLOAD_WORDS)
    parser.add_argument('--cross', default=str(Path(__file__).resolve().parents[2] / 'gfx/tools/spirv_cross_bin/spirv-cross'))
    parser.add_argument('--glslang', default='glslangValidator')
    args = parser.parse_args()
    info = json.loads(args.metadata.read_text())
    source = subprocess.run([args.cross, str(args.spv), '--vulkan-semantics', '--version', '460'], check=True, capture_output=True, text=True).stdout
    source = compose(source, info, args.descriptor_set, args.payload_words)
    glsl = args.out.with_suffix('.task' if info['kind'] == 6 else '.mesh')
    glsl.write_text(source)
    subprocess.run([args.glslang, '-V', '--target-env', 'vulkan1.2', '-Os', '-S', glsl.suffix[1:], str(glsl), '-o', str(args.out)], check=True)
    subprocess.run(['spirv-val', '--target-env', 'vulkan1.2', str(args.out)], check=True)


if __name__ == '__main__':
    main()
