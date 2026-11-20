#!/usr/bin/env python3
"""Cache raw pool lookups per invocation, retaining the complete miss path.

Only GlobalToStorage's recognized table search changes. Reusing an
index requires both guest-address bounds to pass on the immutable current map.
The cached index is private to an invocation and begins at empty entry zero.
"""
import hmma_spv as spv


def ins(op,*args):
    return [((len(args)+1)<<16)|op,*args]


def cache_lookup(binary, map_binding=None, require_mixed=False, map_log2=12):
    m = spv.Module(binary)
    functions = [x[2] for x in m.ins if x[0]&65535==54]
    targets = [];access_kinds=set()
    descriptors={v for v,d in m.decos.items() if d.get(33)==[map_binding]} if map_binding is not None else None
    for fid in functions:
        a,b = m.function_range(fid)
        body = m.ins[a:b+1]
        scales = [i for i,x in enumerate(body) if x[0]&65535==132 and
                  any(m.consts.get(v,(None,None))[1]==[8] for v in x[3:])]
        if not scales:
            continue
        # The map helper scales each probe and the final index.
        if len(scales)!=map_log2+1:
            continue
        physical = [x for x in body if x[0]&65535==120 and
                    m.types.get(x[1],[0,0,0])[2]==5349]
        if not physical:
            continue
        accesses=[x for x in body[scales[0]:scales[-1]] if x[0]&65535==65]
        if not accesses or (descriptors is not None and any(x[3] not in descriptors for x in accesses)):
            continue
        pointers={x[2] for x in physical}
        access_kinds.update('read' for x in body if x[0]&65535==61 and x[3] in pointers)
        access_kinds.update('write' for x in body if x[0]&65535==62 and x[1] in pointers)
        if any(x[0]&65535 in (246,247,248,249,250,251) for x in body[scales[0]:scales[-1]]):
            raise ValueError('raw lookup is not a straight-line binary search')
        targets.append((fid,scales))
    # Store-only kernels have less opportunity to reuse a lookup. Keep their
    # existing form; the mixed load/store form has independent tablet coverage.
    if not targets or (require_mixed and access_kinds!={'read','write'}):
        return binary,0

    u32=m.add_type(21,32,0);u64=m.add_type(21,64,0);boolean=m.add_type(20)
    a,_=m.function_range(targets[0][0]);index_type=m.ins[a+targets[0][1][0]][1]
    if m.int_type(index_type)!=(32,1):
        raise ValueError('expected signed 32-bit lookup indices')
    private_ptr=m.add_type(32,6,index_type);cache=m.new_id()
    zero=m.add_const(index_type,0);eight=m.add_const(index_type,8)
    m._insert_decl(ins(59,private_ptr,cache,6,zero))
    if m.header[1]>=0x10400:
        m.entry.append(cache);m.entry[0]+=1<<16
    shift=m.new_id();m._insert_decl(ins(43,u64,shift,32,0))
    offsets=[m.add_const(index_type,i) for i in range(4)]

    for fid,_ in targets:
        a,b=m.function_range(fid);body=m.ins[a:b+1]
        scales=[i for i,x in enumerate(body) if x[0]&65535==132 and
                any(m.consts.get(v,(None,None))[1]==[8] for v in x[3:])]
        start,end=scales[0],scales[-1]
        last=body[end];old_index=next(v for v in last[3:] if v!=eight)
        args=[x for x in body if x[0]&65535==55]
        if len(args)<2 or any(m.types[x[1]][2:]!=[7,index_type] for x in args[:2]):
            raise ValueError('expected low/high address pointer parameters')
        access=next(x for x in body[start:end] if x[0]&65535==65)
        pointer_type,descriptor,field=access[1],access[3],access[4]
        if m.types[pointer_type][3]!=u32:
            raise ValueError('expected uint32 map words')
        prefix=[]
        def emit(op,ty,*values,output=prefix):
            ident=m.new_id();output.append(ins(op,ty,ident,*values));return ident
        def pair(low,high):
            return emit(197,u64,emit(113,u64,low),emit(196,u64,emit(113,u64,high),shift))
        low=emit(124,u32,emit(61,index_type,args[0][2]))
        high=emit(124,u32,emit(61,index_type,args[1][2]))
        address=pair(low,high)
        cached=emit(61,index_type,cache);entry=emit(132,index_type,cached,eight)
        def word(offset,entry=entry,pointer_type=pointer_type,descriptor=descriptor,field=field):
            index=emit(128,index_type,entry,offsets[offset])
            return emit(61,u32,emit(65,pointer_type,descriptor,field,index))
        lo=pair(word(0),word(1));hi=pair(word(2),word(3))
        hit=emit(167,boolean,emit(174,boolean,address,lo),emit(176,boolean,address,hi))
        hit_label,miss_label,join=m.new_id(),m.new_id(),m.new_id()
        selected=m.new_id()
        prefix.extend([ins(247,join,0),ins(250,hit,hit_label,miss_label),
                       ins(248,hit_label),ins(249,join),ins(248,miss_label)])
        suffix=[ins(249,join),ins(248,join),
                ins(245,index_type,selected,cached,hit_label,old_index,miss_label),
                ins(62,cache,selected)]
        last[:]=[last[0],last[1],last[2],*(selected if v==old_index else v for v in last[3:])]
        original_label=next(x[1] for x in reversed(body[:start]) if x[0]&65535==248)
        for x in body[end:]:
            if x[0]&65535==245:
                for i in range(4,len(x),2):
                    if x[i]==original_label:x[i]=join
        m.ins[a:b+1]=body[:start]+prefix+body[start:end]+suffix+body[end:]
    return m.data(),len(targets)
