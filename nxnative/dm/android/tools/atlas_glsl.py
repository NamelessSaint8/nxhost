"""Opt-in compressed atlas sampling ABI for single floating 2D-array bindings.

Each converted image keeps its ordinary sampler and gains one SSBO at binding
2048+image. A zero header selects the original dense operation. Unsupported
operations/descriptor arrays are rejected rather than approximated.
"""
import re

BINDING_BASE = 2048
HEADER_WORDS = 96
MAX_LEVELS = 16


def _arguments(source, opening):
    """Split a generated GLSL call without splitting nested constructors."""
    arguments, start, stack = [], opening+1, []
    pairs = {')':'(', ']':'[', '}':'{'}
    for position in range(opening+1, len(source)):
        char = source[position]
        if char in '([{': stack.append(char)
        elif char in ')]}':
            if char == ')' and not stack:
                argument = source[start:position].strip()
                if argument: arguments.append(argument)
                return arguments, position+1
            if not stack or stack.pop() != pairs[char]: raise ValueError('unbalanced atlas call')
        elif char == ',' and not stack:
            arguments.append(source[start:position].strip()); start = position+1
    raise ValueError('unterminated atlas call')


def _rewrite_calls(source, name, tag, allowed, arrayed=True):
    pattern = re.compile(r'\b(\w+)\s*\(\s*'+re.escape(name)+r'\s*([,\)])')
    pieces, position = [], 0
    while match := pattern.search(source, position):
        opening = source.index('(', match.start())
        arguments, end = _arguments(source, opening)
        arguments = [_rewrite_calls(arg, name, tag, allowed, arrayed) for arg in arguments[1:]]
        operation = match[1]
        if not arrayed and operation not in ('textureSize', 'textureQueryLevels', 'textureQueryLod'):
            vector = 'ivec3' if operation in ('texelFetch', 'texelFetchOffset') else 'vec3'
            arguments[0] = vector+'('+arguments[0]+',0)'
        call = tag+'_'+allowed[operation]+'('+','.join(arguments)+')'
        if operation in ('textureLodOffset','textureOffset','texelFetchOffset','textureGather','textureGatherOffset','textureGatherOffsets'):
            # Offset/component operands must remain constant expressions in the
            # native intrinsic. Keep that branch in its original lexical scope.
            native = operation+'('+','.join([name, *arguments])+')'
            call = '('+tag+'_word(0u)==0u?'+native+':'+call+')'
        if not arrayed and operation == 'textureSize': call = '('+call+').xy'
        pieces.extend((source[position:match.start()], call)); position = end
    return ''.join(pieces)+source[position:]


def _shadow_lod(source):
    """Preserve explicit depth LOD when SPIRV-Cross emits a three-arg Grad.

    GL_EXT_texture_shadow_lod supplies the exact textureLod overload. A Grad
    call requires two gradient vectors; its scalar third operand here is LOD.
    Only this invalid overload on an array shadow sampler is repaired.
    """
    changed = False
    for name in re.findall(r'\buniform\s+sampler2DArrayShadow\s+(\w+)\s*;', source):
        pattern = re.compile(r'\btextureGrad\s*\(\s*'+re.escape(name)+r'\s*,')
        parts, position = [], 0
        while match := pattern.search(source, position):
            args, end = _arguments(source, source.index('(', match.start()))
            call = source[match.start():end]
            if len(args) == 3:
                call = 'textureLod('+','.join(args)+')'
                changed = True
            parts.extend((source[position:match.start()], call)); position = end
        source = ''.join(parts)+source[position:]
    if changed and 'GL_EXT_texture_shadow_lod' not in source:
        end = source.index('\n')+1
        source = source[:end]+'#extension GL_EXT_texture_shadow_lod : require\n'+source[end:]
    return source


def compose(source, stage=None):
    source = _shadow_lod(source)
    declarations = list(re.finditer(r'layout\s*\((?P<layout>[^)]*)\)\s*uniform\s+sampler2D(?P<arrayed>Array)?\s+(?P<name>\w+)\s*(?P<descriptors>\[[^;]+\])?\s*;', source))
    converted, prefixes, definitions = [], [], []
    for decl in declarations:
        binding = re.search(r'\bbinding\s*=\s*(\d+)', decl['layout'])
        descriptor_set = re.search(r'\bset\s*=\s*(\d+)', decl['layout'])
        if not binding: raise ValueError('atlas sampler has no descriptor binding')
        number, name = int(binding[1]), decl['name']
        arrayed = bool(decl['arrayed'])
        # A compiled bundle may already contain checked array wrappers. A
        # subsequent 2D upgrade leaves those bindings and helpers untouched.
        if re.search(r'\bdm_atlas_'+str(number)+r'\b', source): continue
        # GLSL overloads all start with the sampler expression. Calls with this
        # sampler must be direct, so a helper cannot hide an unsupported access.
        calls = list(re.finditer(r'\b(\w+)\s*\(\s*'+re.escape(name)+r'\s*([,\)])', source))
        if decl['descriptors'] and re.search(r'\b'+re.escape(name)+r'\s*\[', source[decl.end():]):
            raise ValueError(f'{name}: atlas descriptor arrays are not supported yet')
        if not calls: continue
        if decl['descriptors']: raise ValueError(f'{name}: atlas descriptor arrays are not supported yet')
        allowed = {'textureSize':'size', 'textureQueryLevels':'levels', 'texelFetch':'fetch', 'textureLod':'lod',
                   'textureLodOffset':'lod_offset', 'texelFetchOffset':'fetch_offset',
                   'textureGather':'gather', 'textureGatherOffset':'gather_offset', 'textureGatherOffsets':'gather_offsets'}
        fragment = any(call[1] in ('texture', 'textureQueryLod', 'textureOffset') for call in calls)
        if fragment:
            if stage not in ('ps', 'frag'):
                raise ValueError(f'{name}: implicit atlas sampling/LOD query requires a fragment stage')
            allowed.update(texture='sample', textureQueryLod='query', textureOffset='sample_offset')
        for call in calls:
            if call[1] not in allowed: raise ValueError(f'{name}: unsupported atlas operation {call[1]}')
        extra = BINDING_BASE+number
        if extra > 65535 or re.search(r'\bbinding\s*=\s*'+str(extra)+r'\b', source): raise ValueError('atlas metadata binding collision')
        tag = f'dm_va_{number}'
        operations = {call[1] for call in calls}
        source = _rewrite_calls(source, name, tag, allowed, arrayed)
        if not arrayed:
            # Packed storage always uses array images. Native 2D coordinates
            # select layer zero; size queries retain their original ivec2 type.
            source = source.replace(decl[0], decl[0].replace('sampler2D', 'sampler2DArray'), 1)
        prefixes.append(f'layout(set={int(descriptor_set[1]) if descriptor_set else 0},binding={extra},std430) readonly buffer DmAtlas_{number} {{ uint d[]; }} dm_atlas_{number};\n'
                        f'ivec3 {tag}_size(int l); int {tag}_levels(); vec4 {tag}_fetch(ivec3 p,int l); vec4 {tag}_lod(vec3 p,float l);\n'
                        +(f'vec2 {tag}_query(vec2 p); vec4 {tag}_sample(vec3 p); vec4 {tag}_sample(vec3 p,float bias);\n' if fragment else '')
                        +_advanced_prototypes(tag, operations))
        definitions.append(_functions(tag, name, f'dm_atlas_{number}', fragment, operations))
        converted.append(number)
    if not converted: return source, []
    first = re.search(r'\b(?:void|float|int|uint|bool|[biu]?vec[234])\s+\w+\s*\(', source)
    if not first: raise ValueError('atlas source has no function insertion point')
    source = source[:first.start()]+''.join(prefixes)+source[first.start():]
    return source+'\n'+''.join(definitions), converted


def _advanced_prototypes(tag, operations):
    text = 'uint TAG_word(uint i);\n'
    if operations & {'textureLodOffset', 'textureOffset'}:
        text += 'vec4 TAG_lod_offset(vec3 p,float lod,ivec2 offset);\n'
    if 'texelFetchOffset' in operations: text += 'vec4 TAG_fetch_offset(ivec3 p,int level,ivec2 offset);\n'
    if 'textureOffset' in operations: text += 'vec4 TAG_sample_offset(vec3 p,ivec2 offset);vec4 TAG_sample_offset(vec3 p,ivec2 offset,float bias);\n'
    if 'textureGather' in operations: text += 'vec4 TAG_gather(vec3 p);vec4 TAG_gather(vec3 p,int component);\n'
    if 'textureGatherOffset' in operations: text += 'vec4 TAG_gather_offset(vec3 p,ivec2 offset);vec4 TAG_gather_offset(vec3 p,ivec2 offset,int component);\n'
    if 'textureGatherOffsets' in operations: text += 'vec4 TAG_gather_offsets(vec3 p,ivec2 offsets[4]);vec4 TAG_gather_offsets(vec3 p,ivec2 offsets[4],int component);\n'
    return text.replace('TAG', tag)


def _functions(tag, sampler, metadata, fragment=False, operations=frozenset()):
    text = r'''
uint TAG_word(uint i){return META.d[i];}
vec4 TAG_hole(){return vec4(uintBitsToFloat(TAG_word(16)),uintBitsToFloat(TAG_word(17)),uintBitsToFloat(TAG_word(18)),uintBitsToFloat(TAG_word(19)));}
int TAG_levels(){if(TAG_word(0)==0u)return textureQueryLevels(SAMPLER);return int(TAG_word(1));}
ivec3 TAG_size(int level){
    if(TAG_word(0)==0u)return textureSize(SAMPLER,level);
    uint m=uint(clamp(level,0,int(TAG_word(1))-1))+TAG_word(2);
    return ivec3(TAG_word(32u+m*4u),TAG_word(33u+m*4u),TAG_word(4));
}
vec4 TAG_fetch(ivec3 p,int level){
    if(TAG_word(0)==0u)return texelFetch(SAMPLER,p,level);
    if(level<0 || level>=int(TAG_word(1)))return TAG_hole();
    uint m=uint(level)+TAG_word(2),h=32u+m*4u;
    ivec2 extent=ivec2(TAG_word(h),TAG_word(h+1u));
    if(any(lessThan(p,ivec3(0))) || any(greaterThanEqual(p,ivec3(extent,int(TAG_word(4))))))return TAG_hole();
    uvec2 tile=uvec2(TAG_word(5),TAG_word(6)),q=uvec2(p.xy)/tile;
    uint page=TAG_word(TAG_word(h+3u)+((uint(p.z)+TAG_word(3))*((uint(extent.y)+tile.y-1u)/tile.y)+q.y)*TAG_word(h+2u)+q.x);
    if(page==0xffffffffu)return TAG_hole();
    uint grid=TAG_word(7),layer=page/(grid*grid),cell=page%(grid*grid);
    ivec2 xy=ivec2(uvec2(cell%grid,cell/grid)*tile+uvec2(p.xy)%tile);
    return texelFetch(SAMPLER,ivec3(xy,int(layer)),0);
}
int TAG_address(int p,int extent,uint mode){if(mode==1u)return ((p%extent)+extent)%extent;return clamp(p,0,extent-1);}
vec4 TAG_tap_extent(ivec2 p,int layer,int level,ivec2 e){return TAG_fetch(ivec3(TAG_address(p.x,e.x,TAG_word(10)),TAG_address(p.y,e.y,TAG_word(11)),layer),level);}
vec4 TAG_tap(ivec2 p,int layer,int level){return TAG_tap_extent(p,layer,level,TAG_size(level).xy);}
// Four adjacent logical taps can use one hardware filter only when they all
// belong to the same mapped tile. Edges, wrapping and holes retain exact taps.
bool TAG_linear(ivec2 i,vec2 f,int layer,int level,ivec2 extent,out vec4 value){
    if(TAG_word(15)==0u)return false;
    if(any(lessThan(i,ivec2(0))) || any(greaterThanEqual(i+1,extent)))return false;
    uvec2 tile=uvec2(TAG_word(5),TAG_word(6)),q=uvec2(i)/tile;
    if(any(notEqual(q,uvec2(i+1)/tile)))return false;
    uint h=32u+(uint(level)+TAG_word(2))*4u;
    uint page=TAG_word(TAG_word(h+3u)+((uint(layer)+TAG_word(3))*((uint(extent.y)+tile.y-1u)/tile.y)+q.y)*TAG_word(h+2u)+q.x);
    if(page==0xffffffffu)return false;
    uint grid=TAG_word(7),physicalLayer=page/(grid*grid),cell=page%(grid*grid);
    vec2 xy=vec2(uvec2(cell%grid,cell/grid)*tile+uvec2(i)%tile)+.5+f;
    value=textureLod(SAMPLER,vec3(xy/vec2(textureSize(SAMPLER,0).xy),float(physicalLayer)),0.0);
    return true;
}
vec4 TAG_filter(vec2 uv,int layer,int level,bool linearFilter){
    ivec2 extent=TAG_size(level).xy;
    vec2 p=uv*vec2(extent);
    if(!linearFilter)return TAG_tap_extent(ivec2(floor(p)),layer,level,extent);
    p-=.5;ivec2 i=ivec2(floor(p));vec2 f=fract(p);
    vec4 nativeValue;if(TAG_linear(i,f,layer,level,extent,nativeValue))return nativeValue;
    return mix(mix(TAG_tap_extent(i,layer,level,extent),TAG_tap_extent(i+ivec2(1,0),layer,level,extent),f.x),mix(TAG_tap_extent(i+ivec2(0,1),layer,level,extent),TAG_tap_extent(i+ivec2(1,1),layer,level,extent),f.x),f.y);
}
vec4 TAG_lod(vec3 p,float lod){
    if(TAG_word(0)==0u)return textureLod(SAMPLER,p,lod);
    float lambda=clamp(lod,uintBitsToFloat(TAG_word(12)),uintBitsToFloat(TAG_word(13)));
    uint minFilter=TAG_word(8);bool linearFilter=lambda<=0.0?TAG_word(9)!=0u:(minFilter==1u || minFilter==3u || minFilter==5u);
    int layer=clamp(int(floor(p.z+.5)),0,int(TAG_word(4))-1);
    lambda=clamp(lambda,0.0,float(TAG_word(1)-1u));
    if(minFilter<=1u)lambda=0.0;
    if(minFilter<4u)return TAG_filter(p.xy,layer,int(floor(lambda+.5)),linearFilter);
    int low=int(floor(lambda)),high=min(low+1,int(TAG_word(1))-1);
    return mix(TAG_filter(p.xy,layer,low,linearFilter),TAG_filter(p.xy,layer,high,linearFilter),fract(lambda));
}
'''
    if fragment:
        # Keep the device's derivative/LOD calculation: scaling normalized
        # coordinates makes its physical texel footprint equal the logical one.
        # Query Y is unclamped; query X must use the logical view's mip count.
        text += r'''
vec2 TAG_query(vec2 p){
    if(TAG_word(0)==0u)return textureQueryLod(SAMPLER,p);
    vec2 scale=vec2(TAG_size(0).xy)/vec2(textureSize(SAMPLER,0).xy);
    float raw=textureQueryLod(SAMPLER,p*scale).y;
    float level=clamp(clamp(raw,uintBitsToFloat(TAG_word(12)),uintBitsToFloat(TAG_word(13))),0.0,float(TAG_word(1)-1u));
    if(TAG_word(8)<4u)level=floor(level+.5);
    return vec2(level,raw);
}
vec4 TAG_sample(vec3 p,float bias){
    if(TAG_word(0)==0u)return texture(SAMPLER,p,bias);
    float limit=uintBitsToFloat(TAG_word(14));
    return TAG_lod(p,TAG_query(p.xy).y+clamp(bias,-limit,limit));
}
vec4 TAG_sample(vec3 p){return TAG_sample(p,0.0);}
'''
    if operations & {'textureLodOffset','textureOffset'}:
        text += r'''
vec4 TAG_filter_offset(vec2 uv,int layer,int level,bool linearFilter,ivec2 offset){
    ivec2 extent=TAG_size(level).xy;
    vec2 p=uv*vec2(extent);
    if(!linearFilter)return TAG_tap_extent(ivec2(floor(p))+offset,layer,level,extent);
    p-=.5;ivec2 i=ivec2(floor(p))+offset;vec2 f=fract(p);
    vec4 nativeValue;if(TAG_linear(i,f,layer,level,extent,nativeValue))return nativeValue;
    return mix(mix(TAG_tap_extent(i,layer,level,extent),TAG_tap_extent(i+ivec2(1,0),layer,level,extent),f.x),mix(TAG_tap_extent(i+ivec2(0,1),layer,level,extent),TAG_tap_extent(i+ivec2(1,1),layer,level,extent),f.x),f.y);
}
vec4 TAG_lod_offset(vec3 p,float lod,ivec2 offset){
    float lambda=clamp(lod,uintBitsToFloat(TAG_word(12)),uintBitsToFloat(TAG_word(13)));
    uint minFilter=TAG_word(8);bool linearFilter=lambda<=0.0?TAG_word(9)!=0u:(minFilter==1u || minFilter==3u || minFilter==5u);
    int layer=clamp(int(floor(p.z+.5)),0,int(TAG_word(4))-1);
    lambda=clamp(lambda,0.0,float(TAG_word(1)-1u));if(minFilter<=1u)lambda=0.0;
    if(minFilter<4u)return TAG_filter_offset(p.xy,layer,int(floor(lambda+.5)),linearFilter,offset);
    int low=int(floor(lambda)),high=min(low+1,int(TAG_word(1))-1);
    return mix(TAG_filter_offset(p.xy,layer,low,linearFilter,offset),TAG_filter_offset(p.xy,layer,high,linearFilter,offset),fract(lambda));
}
'''
    if 'textureOffset' in operations:
        text += r'''
vec4 TAG_sample_offset(vec3 p,ivec2 offset,float bias){float limit=uintBitsToFloat(TAG_word(14));return TAG_lod_offset(p,TAG_query(p.xy).y+clamp(bias,-limit,limit),offset);}
vec4 TAG_sample_offset(vec3 p,ivec2 offset){return TAG_sample_offset(p,offset,0.0);}
'''
    if 'texelFetchOffset' in operations:
        text += '\nvec4 TAG_fetch_offset(ivec3 p,int level,ivec2 offset){return TAG_fetch(ivec3(p.xy+offset,p.z),level);}\n'
    if operations & {'textureGather','textureGatherOffset'}:
        text += r'''
vec4 TAG_gather_offset(vec3 p,ivec2 offset,int component){
    ivec2 i=ivec2(floor(p.xy*vec2(TAG_size(0).xy)-.5))+offset;
    int layer=clamp(int(floor(p.z+.5)),0,int(TAG_word(4))-1);
    return vec4(TAG_tap(i+ivec2(0,1),layer,0)[component],TAG_tap(i+ivec2(1,1),layer,0)[component],TAG_tap(i+ivec2(1,0),layer,0)[component],TAG_tap(i,layer,0)[component]);
}
'''
    if 'textureGather' in operations:
        text += '\nvec4 TAG_gather(vec3 p,int component){return TAG_gather_offset(p,ivec2(0),component);}\nvec4 TAG_gather(vec3 p){return TAG_gather(p,0);}\n'
    if 'textureGatherOffset' in operations:
        text += '\nvec4 TAG_gather_offset(vec3 p,ivec2 offset){return TAG_gather_offset(p,offset,0);}\n'
    if 'textureGatherOffsets' in operations:
        text += r'''
vec4 TAG_gather_offsets(vec3 p,ivec2 offsets[4],int component){
    ivec2 i=ivec2(floor(p.xy*vec2(TAG_size(0).xy)-.5));int layer=clamp(int(floor(p.z+.5)),0,int(TAG_word(4))-1);
    return vec4(TAG_tap(i+offsets[0],layer,0)[component],TAG_tap(i+offsets[1],layer,0)[component],TAG_tap(i+offsets[2],layer,0)[component],TAG_tap(i+offsets[3],layer,0)[component]);
}
vec4 TAG_gather_offsets(vec3 p,ivec2 offsets[4]){return TAG_gather_offsets(p,offsets,0);}
'''
    return text.replace('TAG', tag).replace('SAMPLER', sampler).replace('META', metadata)
