#!/usr/bin/env python3
"""Trace original HMMA operands/results for the first workgroup only.

Binding 31 contains 1024 calls x 32 lanes x 12 uints. Each record is
A0..A3, B0..B1, C0..C1, D0..D1, sequence+1, magic. Original arithmetic
instructions remain untouched. Use the scalar translator SPIR-V as input.
"""
import argparse
from pathlib import Path
import subprocess
import sys
from raw_memory_guard import ins

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'nxnative/dm/android/tools'))
import hmma_spv as h

def trace(binary):
    m=h.Module(binary);helper=h.hmma_helper(m)
    if helper is None:raise ValueError('original helper contract required')
    if any(d.get(33)==[31] for d in m.decos.values()):raise ValueError('trace binding 31 occupied')
    u32=m.add_type(21,32,0);boolean=m.add_type(20);pu32=m.add_type(32,12,u32)
    # Do not reuse an existing BufferBlock type: adding Block to it would
    # change the meaning of the original shader's Uniform-class SSBOs.
    array=m.new_id();m._insert_decl(ins(29,array,u32));m.types[array]=ins(29,array,u32)
    block=m.new_id();m._insert_decl(ins(30,block,array));m.types[block]=ins(30,block,array);ptr=m.add_type(32,12,block)
    private=m.add_type(32,6,u32);zero=m.add_const(u32,0);one=m.add_const(u32,1)
    for word in range(12):m.add_const(u32,word)
    variable,sequence=m.new_id(),m.new_id();m._insert_decl(ins(59,ptr,variable,12));m._insert_decl(ins(59,private,sequence,6,zero))
    deco=[ins(71,array,6,4),ins(71,block,2),ins(72,block,0,35,0),ins(71,variable,34,0),ins(71,variable,33,31)]
    at=next(i for i,x in enumerate(m.ins) if 19<=x[0]&65535<=39);m.ins[at:at]=deco
    if m.header[1]>=0x10400:m.entry.append(variable);m.entry[0]+=1<<16
    group=next(i for i,d in m.decos.items() if d.get(11)==[26]);group_ty=m.types[m.vars[group][0]][3]
    a,e=m.function_range(helper['fid']);params=[x[2] for x in m.ins[a:e] if x[0]&65535==55];entry=next(i for i in range(a,e) if m.ins[i][0]&65535==248)+1
    while m.ins[entry][0]&65535==59:entry+=1
    code=[]
    def emit(op,ty,*args):
        ident=m.new_id();code.append(ins(op,ty,ident,*args));return ident
    seq=emit(61,u32,sequence);next_seq=emit(128,u32,seq,one);code.append(ins(62,sequence,next_seq))
    wg=emit(61,group_ty,group);first=None
    for axis in range(3):
        coord=emit(81,u32,wg,axis);yes=emit(170,boolean,coord,zero);first=yes if first is None else emit(167,boolean,first,yes)
    # Multi-warp workgroups share the same lane numbers. Restrict the record
    # to their first logical warp, otherwise later warps race over its words.
    local=next(i for i,d in m.decos.items() if d.get(11)==[27])
    local_value=emit(61,group_ty,local)
    for axis in (1,2):
        first=emit(167,boolean,first,emit(170,boolean,emit(81,u32,local_value,axis),zero))
    first=emit(167,boolean,first,emit(176,boolean,emit(81,u32,local_value,0),m.add_const(u32,32)))
    first=emit(167,boolean,first,emit(176,boolean,seq,m.add_const(u32,1024)))
    lane=emit(124,u32,emit(61,helper['i32'],params[0]));base=emit(132,u32,emit(128,u32,emit(132,u32,seq,m.add_const(u32,32)),lane),m.add_const(u32,12))
    def store(word,value):
        index=emit(128,u32,base,m.add_const(u32,word));p=emit(65,pu32,variable,zero,index);code.append(ins(62,p,value))
    def open_if():
        yes,end=m.new_id(),m.new_id();code.extend([ins(247,end,0),ins(250,first,yes,end),ins(248,yes)]);return end
    def close_if(end):code.extend([ins(249,end),ins(248,end)])
    end=open_if()
    for i in range(8):store(i,emit(124,u32,emit(61,helper['i32'],params[i+2])))
    store(10,next_seq);store(11,m.add_const(u32,0x444d0001));close_if(end)
    # Declarations inserted while building the trace moved the entry position.
    a,e=m.function_range(helper['fid']);entry=next(i for i in range(a,e) if m.ins[i][0]&65535==248)+1
    while m.ins[entry][0]&65535==59:entry+=1
    m.ins[entry:entry]=code
    a,e=m.function_range(helper['fid']);returns=[(i,x[1]) for i,x in enumerate(m.ins[a:e],a) if x[0]&65535==254]
    for index,result in reversed(returns):
        code=[];end=open_if();store(8,emit(124,u32,result));store(9,emit(124,u32,emit(61,helper['i32'],params[10])));close_if(end);m.ins[index:index]=code
    return m.data()

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('input',type=Path);p.add_argument('output',type=Path);a=p.parse_args();a.output.write_bytes(trace(a.input.read_bytes()));subprocess.run(['spirv-val','--target-env','vulkan1.2',str(a.output)],check=True)
