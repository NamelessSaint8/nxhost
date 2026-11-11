"""Move oversized uint workgroup arrays into isolated per-workgroup buffers."""
import re
import struct


def compose(source, limit, binding):
    declarations=list(re.finditer(r'\bshared\s+uint\s+(\w+)\s*\[\s*(\d+)\s*\]\s*;',source))
    words=sum(int(match[2]) for match in declarations)
    if words*4<=limit:return source,0
    if len(re.findall(r'\bshared\b',source))!=len(declarations):
        raise ValueError('oversized workgroup storage includes unsupported declarations')
    source=re.sub(r'\bshared\s+uint\s+\w+\s*\[\s*\d+\s*\]\s*;','',source)
    offset=0
    for declaration in declarations:
        name,count=declaration[1],int(declaration[2]);pattern=re.compile(r'\b'+re.escape(name)+r'\s*\[')
        pieces=[];unreplaced=[];start=0
        for match in pattern.finditer(source):
            if match.start()<start:continue
            end=match.end();depth=1
            while end<len(source) and depth:
                depth+=(source[end]=='[')-(source[end]==']');end+=1
            if depth:raise ValueError('unterminated workgroup access')
            index=source[match.end():end-1]
            unreplaced.extend((source[start:match.start()],index))
            pieces.extend((source[start:match.start()],f'dm_workgroup.words[dm_workgroup_base()+{offset}u+uint({index})]'));start=end
        unreplaced.append(source[start:]);pieces.append(source[start:])
        if re.search(r'\b'+re.escape(name)+r'\b',''.join(unreplaced)):raise ValueError('workgroup array escapes an indexed access')
        source=''.join(pieces)
        offset+=count
    declaration=(f'layout(set=0,binding={binding},std430) coherent buffer DmWorkgroup {{ uint words[]; }} dm_workgroup;\n'
                 f'uint dm_workgroup_base(){{uvec3 p=gl_WorkGroupID,n=gl_NumWorkGroups;return ((p.z*n.y+p.y)*n.x+p.x)*{words}u;}}\n')
    # GLSL directives must precede ordinary declarations.
    lines=source.splitlines(keepends=True);at=1
    while at<len(lines) and (not lines[at].strip() or lines[at].lstrip().startswith('#')):at+=1
    lines.insert(at,declaration)
    return ''.join(lines),words*4


def barrier_storage(spv):
    """Retarget original shared-memory barrier semantics to buffer memory."""
    words=list(struct.unpack('<'+'I'*(len(spv)//4),spv));constants={};first_function=len(words);i=5
    while i<len(words):
        n,op=words[i]>>16,words[i]&65535
        if not n or i+n>len(words):raise ValueError('malformed SPIR-V')
        if op==43 and n==4:constants[words[i+2]]=(words[i+1],words[i+3])
        if op==54:first_function=min(first_function,i)
        i+=n
    extra=[];replacement={};i=5
    while i<len(words):
        n,op=words[i]>>16,words[i]&65535
        operand=i+3 if op==224 else i+2 if op==225 else None
        if operand is not None:
            old=words[operand]
            if old not in constants:raise ValueError('nonconstant memory semantics')
            kind,value=constants[old]
            if value&0x100:
                if old not in replacement:
                    replacement[old]=words[3];extra.extend((4<<16|43,kind,words[3],(value&~0x100)|0x40));words[3]+=1
                words[operand]=replacement[old]
        i+=n
    words[first_function:first_function]=extra
    return struct.pack('<'+'I'*len(words),*words)
