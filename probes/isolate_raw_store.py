#!/usr/bin/env python3
"""Correct-output raw-store ablations for guarded, captured-pool replay only.

no-log folds only CAS operations on the named log descriptor to successful
insertions. fixed-map specializes the final index of the recognized 4096-entry
binary search to a captured entry; its end check, relocation and store remain.
These diagnostics are never production shaders. Whole-pool equality and the raw
address guard remain mandatory. Math instructions are not changed.
"""
import argparse
from pathlib import Path
import subprocess

from raw_memory_guard import ins, spv


def isolate(binary, log_binding=None, map_entry=None):
    m = spv.Module(binary)
    result_types = {x[2]: x[1] for x in m.ins if len(x)>2 and x[1] in m.types and x[0]&65535>39}
    pointers = {x[2]: x[3] for x in m.ins if x[0]&65535 in (65,66,67,70,83)}
    def root(ident):
        seen = set()
        while ident in pointers and ident not in seen:
            seen.add(ident)
            ident = pointers[ident]
        return ident
    changed = dict(log_cas=0, map_searches=0)
    if log_binding is not None:
        variables = [v for v,d in m.decos.items() if d.get(33)==[log_binding] and d.get(34,[0])==[0]]
        if len(variables)!=1:raise ValueError('expected one log descriptor')
        for x in list(m.ins):
            if x[0]&65535==230 and root(x[3])==variables[0]:
                ty, ident = x[1:3]
                if m.int_type(ty)!=(32,0):raise ValueError('expected uint32 log CAS')
                x[:] = ins(83,ty,ident,m.add_const(ty,0))
                changed['log_cas'] += 1
        if changed['log_cas']!=8:raise ValueError('expected eight log probes in one raw-store helper')
    if map_entry is not None:
        if not 1<=map_entry<4096:raise ValueError('expected captured real map entry')
        functions = [x[2] for x in m.ins if x[0]&65535==54]
        for fid in functions:
            a,b = m.function_range(fid)
            body = m.ins[a:b+1]
            stores=[]
            for x in body:
                if x[0]&65535!=62:continue
                ty=m.types.get(result_types.get(x[1],0),[])
                if len(ty)==4 and ty[0]&65535==32 and ty[2]==5349:stores.append(x)
            if not stores:continue
            scales = [x for x in body if x[0]&65535==132 and
                      any(m.consts.get(v,(None,None))[1]==[8] for v in x[3:])]
            if len(stores)!=1 or len(scales)!=13:raise ValueError('unrecognized raw-store map search')
            last = scales[-1]
            ty,ident = last[1:3]
            last[:] = ins(83,ty,ident,m.add_const(ty,map_entry*8))
            changed['map_searches'] += 1
        if changed['map_searches']!=1:raise ValueError('expected one raw-store helper')
    return m.data(),changed


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input',type=Path);parser.add_argument('output',type=Path)
    parser.add_argument('--log-binding',type=int);parser.add_argument('--map-entry',type=int)
    args=parser.parse_args()
    binary,counts=isolate(args.input.read_bytes(),args.log_binding,args.map_entry)
    args.output.write_bytes(binary)
    subprocess.run(['spirv-val','--target-env','vulkan1.2',str(args.output)],check=True)
    print(counts)
