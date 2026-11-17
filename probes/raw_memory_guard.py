#!/usr/bin/env python3
"""Guard captured 32-bit physical loads/stores without rebuilding shader math.

Binding 30: uint fault count at byte 0, twelve padding bytes, then sixteen
{uint64 start, end} Vulkan address ranges. Noncaptured pool deltas become zero
in the replay table; this guard refuses their accesses instead of dereferencing
stale pointers. Atomics/copies through physical pointers are rejected at build.
"""
import argparse
from pathlib import Path
import subprocess
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'nxnative/dm/android/tools'))
import hmma_spv as spv

MARKER='dm_replay_raw_guard_v1'

def ins(op,*args):return [((len(args)+1)<<16)|op,*args]

def guard(binary, ranges=16):
    if not 1<=ranges<=16:raise ValueError('guard requires 1..16 captured ranges')
    m=spv.Module(binary)
    # The guard counts failures across workgroups using Device-scope atomics.
    # Cooperative matrix shaders use the Vulkan memory model, where that scope
    # needs an explicit capability (the replay enables the corresponding feature).
    if any(x[0]&65535==14 and x[2]==3 for x in m.ins):
        if not any(x[0]&65535==17 and x[1]==5346 for x in m.ins):
            m.ins.insert(0,ins(17,5346))
    if not m.entry or m.entry[1]!=5:raise ValueError('only compute capture is supported')
    if any(d.get(33)==[30] and d.get(34,[0])==[0] for d in m.decos.values()):raise ValueError('guard binding 30 is occupied')
    result_types={x[2]:x[1] for x in m.ins if len(x)>2 and x[1] in m.types and (x[0]&65535)>39}
    def physical(ident):
        ty=m.types.get(result_types.get(ident,0),[])
        return len(ty)==4 and ty[0]&65535==32 and ty[2]==5349
    accesses=[]
    for x in m.ins:
        op=x[0]&65535
        if op in (61,62):
            pointer=x[3] if op==61 else x[1]
            if physical(pointer):
                ty=m.types[result_types[pointer]][3]
                if m.int_type(ty)!=(32,0):raise ValueError('only uint32 physical memory is supported')
                memory=x[4:] if op==61 else x[3:]
                if memory!=[2,4]:raise ValueError('only Aligned 4 physical memory is supported')
                accesses.append((op,ty))
        elif op in (63,64,*range(227,243),318,319):
            pointers=x[1:3] if op in (63,64) else [x[1] if op in (228,319) else x[3]]
            if any(physical(v) for v in pointers):raise ValueError('physical atomic/copy requires a separate capture contract')
    if not accesses:raise ValueError('no physical loads/stores')
    u32=m.add_type(21,32,0);u64=m.add_type(21,64,0);boolean=m.add_type(20);void=m.add_type(19)
    zero=m.add_const(u32,0);one=m.add_const(u32,1);sixteen=m.add_const(u32,16)
    vector=m.add_type(23,u64,2);array=m.add_type(28,vector,sixteen)
    block=m.add_type(30,u32,array);ptr=m.add_type(32,12,block)
    pu32=m.add_type(32,12,u32);pu64=m.add_type(32,12,u64)
    variable=m.new_id();m._insert_decl(ins(59,ptr,variable,12))
    decorations=[ins(71,array,6,16),ins(71,block,2),ins(72,block,0,35,0),ins(72,block,1,35,16),ins(71,variable,34,0),ins(71,variable,33,30)]
    at=next(i for i,x in enumerate(m.ins) if 19<=x[0]&65535<=39)
    m.ins[at:at]=decorations
    # Interface operands are mandatory for SPIR-V 1.4+ resources.
    if m.header[1]>=0x10400:m.entry.append(variable);m.entry[0]+=1<<16
    false=m.new_id();m._insert_decl(ins(42,boolean,false))
    four=m.new_id();m._insert_decl(ins(43,u64,four,4,0))
    wrappers={};functions=[]
    for op,ty in sorted(set(accesses)):
        function_type=m.add_type(33,void if op==62 else u32,u64,*([u32] if op==62 else []))
        function=m.new_id();wrappers[op]=function;address=m.new_id();value=m.new_id() if op==62 else None
        body=[ins(54,void if op==62 else u32,function,2,function_type),ins(55,u64,address)]
        if value is not None:body.append(ins(55,u32,value))
        label=m.new_id();body.append(ins(248,label))
        def emit(code,ty,*args,output=body):
            ident=m.new_id();output.append(ins(code,ty,ident,*args));return ident
        end_address=emit(128,u64,address,four);valid=false
        for i in range(ranges):
            index=m.add_const(u32,i)
            low_ptr=emit(65,pu64,variable,one,index,zero);high_ptr=emit(65,pu64,variable,one,index,one)
            low=emit(61,u64,low_ptr);high=emit(61,u64,high_ptr)
            inside=emit(167,boolean,emit(174,boolean,address,low),emit(178,boolean,end_address,high))
            inside=emit(167,boolean,inside,emit(174,boolean,end_address,address))
            valid=emit(166,boolean,valid,inside)
        yes,no,merge=m.new_id(),m.new_id(),m.new_id()
        body.extend([ins(247,merge,0),ins(250,valid,yes,no),ins(248,yes)])
        physical_pointer=m.add_type(32,5349,u32);target=emit(120,physical_pointer,address)
        if op==62:body.append(ins(62,target,value,2,4));loaded=None
        else:loaded=emit(61,u32,target,2,4)
        body.extend([ins(249,merge),ins(248,no)])
        fault=emit(65,pu32,variable,zero);emit(234,u32,fault,one,zero,one)
        body.extend([ins(249,merge),ins(248,merge)])
        if loaded is None:body.append(ins(253))
        else:body.append(ins(254,emit(245,u32,loaded,yes,zero,no)))
        body.append(ins(56));functions.extend(body)
    output=[]
    for x in m.ins:
        op=x[0]&65535;pointer=x[3] if op==61 else x[1] if op==62 else 0
        if op in (61,62) and physical(pointer):
            address=m.new_id();output.append(ins(117,u64,address,pointer))
            output.append(ins(57,void if op==62 else u32,m.new_id() if op==62 else x[2],wrappers[op],address,*([x[2]] if op==62 else [])))
        else:output.append(x)
    m.ins=output+functions
    names=next(i for i,x in enumerate(m.ins) if x[0]&65535 in (71,72,19))
    # The marker is a debug name and does not change the original arithmetic.
    m.ins.insert(names,ins(5,variable,*spv.lit_string(MARKER)))
    return m.data(),len(accesses)

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('input',type=Path);p.add_argument('output',type=Path);p.add_argument('--ranges',type=int,default=16);a=p.parse_args()
    binary,count=guard(a.input.read_bytes(),a.ranges);a.output.write_bytes(binary)
    subprocess.run(['spirv-val','--target-env','vulkan1.2',str(a.output)],check=True)
    print(f'guarded {count} physical access sites')

if __name__=='__main__':main()
