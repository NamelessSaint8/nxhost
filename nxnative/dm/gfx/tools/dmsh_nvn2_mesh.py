"""NVN2 task/mesh stage buffers to Metal object/mesh entry points.

The native bodies use workgroup IR. Their stage buffers stay explicit until the
Metal wrapper has run every invocation to completion; its epilogue then publishes
payload or raster outputs. An EXIT returns from the body, never from the wrapper.
Layout reference: Mesa NVK mesh_shading_notes / isbe_layout (linear byte addresses,
32-element attribute groups, one 128-byte line per component).
"""
import re
import struct

PAYLOAD_WORDS = 4096
DRAW_SLOT = 12


def output_lines(sph):
    if len(sph) < 0x50:
        raise ValueError('NVN2 mesh output header is truncated')
    if any(sph[0x48:0x4a]):
        raise ValueError('NVN2 mesh fixed-function outputs are unsupported')
    return ([24 + b for b in range(8) if sph[0x35] >> b & 1] +
            [32 + b for b in range(128) if sph[0x36 + b // 8] >> (b % 8) & 1])


def metadata(control, area):
    """Read the NVN2 compiler's mesh stage, launch bounds and embedded primitive SPH."""
    if len(control) < 0x6c or struct.unpack_from('<II', control) != (0x98761234, 0xc9):
        return None
    kind = struct.unpack_from('<I', control, 0x54)[0] >> 16 & 255
    if kind not in (6, 7):
        return None
    threads, shared = struct.unpack_from('<HH', control, 0x58)
    if not 1 <= threads <= 32:
        raise ValueError('NVN2 mesh workgroup exceeds one SIMD group')
    vertices, primitives = struct.unpack_from('<HH', control, 0x60)
    if kind == 7 and control[0x5f] != 3:
        raise ValueError('NVN2 mesh output is not a triangle list')
    offset, size = struct.unpack_from('<II', control, 0x64)
    vertex = output_lines(area) if kind == 7 else []
    primitive = []
    if kind == 7 and size:
        if size != 0x80 or offset + size > len(area):
            raise ValueError('NVN2 primitive output header range')
        primitive = output_lines(area[offset:offset + size])
    if kind == 7 and (not 1 <= vertices <= 256 or not 1 <= primitives <= 512):
        raise ValueError('NVN2 mesh output exceeds Metal limits')
    if set(vertex) & set(primitive):
        raise ValueError('Overlapping NVN2 vertex and primitive outputs')
    words = ((vertices + 31) // 32 * len(vertex) + (primitives + 31) // 32 * len(primitive)) * 32
    return dict(kind=kind, threads=threads, shared=shared, max_vertices=vertices,
                max_primitives=primitives, vertex_lines=vertex, primitive_lines=primitive,
                attr_words=max(words, (shared + 19) // 4) if kind == 6 else max(words, 1),
                input_words=(shared + 19) // 4, map_words=primitives * 3 + 4,
                task_input=kind == 7 and (struct.unpack_from('<I', area)[0] >> 10 & 15) != 1)


def _params(s):
    parts, depth, first = [], 0, 0
    for i, c in enumerate(s):
        if c in '<([': depth += 1
        if c in '>)]': depth -= 1
        if c == ',' and depth == 0:
            parts.append(s[first:i].strip()); first = i + 1
    return parts + [s[first:].strip()] if s.strip() else []


def compose(source, info):
    """Keep the translated body and resource struct; replace only its kernel entry ABI."""
    entry = re.search(r'kernel void main0\((.*?)\)\s*\{', source, re.S)
    if not entry or source[entry.end():].rstrip()[-1:] != '}':
        raise ValueError('NVN2 stage body has no unique kernel entry')
    if info['input_words'] > PAYLOAD_WORDS or (info['kind'] == 6 and info['attr_words'] > PAYLOAD_WORDS):
        raise ValueError('NVN2 task payload exceeds Metal limit')
    params, args, resources = [], [], []
    # Mesh groups emitted by an object stage are numbered within that task.
    # Only object groups and direct mesh groups use DrawMeshTasks' first group.
    group_x = 'dm_group.x' if info.get('task_input') else 'dm_group.x+dm_draw.x'
    builtins = {'thread_index_in_simdgroup': 'dm_lane', 'thread_index_in_threadgroup': 'dm_tid',
                'thread_position_in_threadgroup': 'uint3(dm_tid,0,0)',
                'threadgroup_position_in_grid': f'uint3({group_x},dm_group.y,dm_group.z)',
                'thread_position_in_grid': f'uint3(({group_x})*{info["threads"]}u+dm_tid,0,0)',
                'threadgroups_per_grid': 'uint3(dm_draw.y,1,1)'}
    for p in _params(entry[1]):
        m = re.fullmatch(r'(.+?)\s+(\w+)\s+\[\[(\w+)(?:\((\d+)\))?\]\]', p)
        if not m:
            raise ValueError('NVN2 stage parameter: ' + p)
        params.append(m[1] + ' ' + m[2])
        if m[3] == 'buffer':
            if int(m[4]) == DRAW_SLOT: raise ValueError('NVN2 stage draw slot collision')
            resources.append(p); args.append(m[2])
        elif m[3] in builtins: args.append(builtins[m[3]])
        else: raise ValueError('NVN2 stage builtin: ' + m[3])
    body = source[entry.end():].rstrip()[:-1]
    declarations = re.findall(r'^\s*threadgroup (spvUnsafeArray<\w+, \d+>) (\w+);', body, re.M)
    for ty, name in declarations:
        params.append(f'threadgroup {ty}& {name}'); args.append(name)
    body = re.sub(r'^\s*threadgroup spvUnsafeArray<\w+, \d+> \w+;', '', body, flags=re.M)
    head = source[:entry.start()]
    head += '\nstatic inline void dm_stage_body(' + ', '.join(params) + ')\n{' + body + '\n}\n'
    head += f'\nstruct DmStagePayload {{ uint words[{PAYLOAD_WORDS}]; }};\n'
    shared = '\n'.join('    threadgroup ' + ty + ' ' + name + ';' for ty, name in declarations)
    call = '    dm_stage_body(' + ', '.join(args) + ');\n'
    common = resources + [f'constant uint4& dm_draw [[buffer({DRAW_SLOT})]]',
                          'uint dm_tid [[thread_index_in_threadgroup]]',
                          'uint dm_lane [[thread_index_in_simdgroup]]',
                          'uint3 dm_group [[threadgroup_position_in_grid]]']
    if info['kind'] == 6:
        if info['attr_words'] > PAYLOAD_WORDS:
            raise ValueError('NVN2 task payload exceeds Metal limit')
        parameters = common + ['object_data DmStagePayload& dm_payload [[payload]]', 'mesh_grid_properties dm_grid']
        return head + '\n[[object]] void dm_task(' + ', '.join(parameters) + ')\n{\n' + shared + f'''
    for(uint i=dm_tid;i<{info['attr_words']}u;i+={info['threads']}u) dm_stage_attr[i]=0;
    threadgroup_barrier(mem_flags::mem_threadgroup);
''' + call + f'''
    threadgroup_barrier(mem_flags::mem_threadgroup | mem_flags::mem_device);
    for(uint i=dm_tid;i<{info['attr_words']}u;i+={info['threads']}u) dm_payload.words[i]=dm_stage_attr[i];
    if(dm_tid==0) dm_grid.set_threadgroups_per_grid(uint3(dm_stage_attr[1],1,1));
}}
'''
    if any(x < 28 or 160 <= x for x in info['vertex_lines']) or any(x < 32 or 160 <= x for x in info['primitive_lines']):
        raise ValueError('NVN2 unsupported mesh output builtin')
    vertex_slots = sorted({(x - 32) // 4 for x in info['vertex_lines'] if x >= 32})
    primitive_slots = sorted({(x - 32) // 4 for x in info['primitive_lines']})
    head += 'struct DmMeshVertex { float4 position [[position]]; ' + ' '.join(f'float4 v{s} [[user(locn{s})]];' for s in vertex_slots) + ' };\n'
    head += 'struct DmMeshPrimitive { ' + ' '.join(f'float4 v{s} [[user(locn{s})]];' for s in primitive_slots) + ' };\n'
    if not primitive_slots: head = head.replace('struct DmMeshPrimitive {  };', 'struct DmMeshPrimitive { bool culled [[primitive_culled]]; };')
    mesh_type = f'metal::mesh<DmMeshVertex,DmMeshPrimitive,{info["max_vertices"]},{info["max_primitives"]},metal::topology::triangle>'
    extra = [mesh_type + ' dm_mesh']
    if info['task_input']: extra += ['const object_data DmStagePayload& dm_payload [[payload]]']
    parameters = common + extra
    vertices, primitives = info['vertex_lines'], info['primitive_lines']
    base = (info['max_vertices'] + 31) // 32 * len(vertices) * 32
    vs = []
    for i, word in enumerate(vertices):
        field = 'position.' + 'xyzw'[word - 28] if word < 32 else f'v{(word-32)//4}.' + 'xyzw'[(word-32)%4]
        vs.append(f'        v.{field}=as_type<float>(dm_stage_attr[(i/32u)*{len(vertices)*32}u+i%32u+{i*32}u]);')
    ps = []
    for j, word in enumerate(primitives):
        field = f'v{(word-32)//4}.' + 'xyzw'[(word-32)%4]
        ps.append(f'        p.{field}=as_type<float>(dm_stage_attr[{base}u+(i/32u)*{len(primitives)*32}u+i%32u+{j*32}u]);')
    result = head
    for name, depth in [('dm_mesh', True), ('dm_mesh_z', False)]:
        setup = ''
        if any(n == 'dm_stage_input' for _, n in declarations):
            value = 'dm_payload.words[i]' if info['task_input'] else '0u'
            setup += f'    for(uint i=dm_tid;i<{info["input_words"]}u;i+={info["threads"]}u) dm_stage_input[i]={value};\n'
        setup += '    if(dm_tid==0) dm_stage_map[0]=0;\n    threadgroup_barrier(mem_flags::mem_threadgroup);\n'
        result += f'\n[[mesh]] void {name}(' + ', '.join(parameters) + ')\n{\n' + shared + '\n' + setup + call + f'''
    threadgroup_barrier(mem_flags::mem_threadgroup);
    uint count=dm_stage_map[0];
    if(dm_tid==0) dm_mesh.set_primitive_count(count);
    for(uint i=dm_tid;i<{info['max_vertices']}u;i+={info['threads']}u) {{
        DmMeshVertex v={{}};
''' + '\n'.join(vs) + ('\n        v.position.z=(v.position.z+v.position.w)*0.5f;' if depth else '') + f'''
        dm_mesh.set_vertex(i,v);
    }}
    for(uint i=dm_tid;i<count;i+={info['threads']}u) {{
        DmMeshPrimitive p={{}};
''' + '\n'.join(ps) + '''
        dm_mesh.set_primitive(i,p);
        dm_mesh.set_index(3u*i,dm_stage_map[4u+3u*i]);
        dm_mesh.set_index(3u*i+1u,dm_stage_map[5u+3u*i]);
        dm_mesh.set_index(3u*i+2u,dm_stage_map[6u+3u*i]);
    }
}
'''
    return result
