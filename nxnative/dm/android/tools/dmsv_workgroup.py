#!/usr/bin/env python3
"""Lower oversized compute workgroup storage for a device's shared-memory limit."""
import argparse
import json
import mmap
import struct
import subprocess
from pathlib import Path

import shader_vk
import workgroup_glsl


def shared_bytes(binary):
    words=struct.unpack('<'+'I'*(len(binary)//4),binary);types={};constants={};variables=[];i=5
    while i<len(words):
        n,op=words[i]>>16,words[i]&65535
        if not n or i+n>len(words):raise ValueError('malformed SPIR-V')
        if 19<=op<=39:types[words[i+1]]=words[i:i+n]
        if op==43 and n==4:constants[words[i+2]]=words[i+3]
        if op==59 and words[i+3]==4:variables.append(words[i+1])
        i+=n
    def size(t):
        ins=types[t];op=ins[0]&65535
        if op in (21,22):return ins[2]//8
        if op==20:return 4
        if op in (23,24):return size(ins[2])*ins[3]
        if op==28:return size(ins[2])*constants[ins[3]]
        if op==30:return sum(size(m) for m in ins[2:])
        if op==32:return size(ins[3])
        raise ValueError(f'unsupported workgroup type {op}')
    return sum(size(t) for t in variables)


def spill(binary, binding, limit, path):
    path=Path(path);original=path.with_suffix('.input.spv');original.write_bytes(binary)
    source=subprocess.run([str(shader_vk.TOOLS/'spirv_cross_bin/spirv-cross'),str(original),'--vulkan-semantics','--version','460'],check=True,capture_output=True,text=True).stdout
    source,bytes_=workgroup_glsl.compose(source,limit,binding)
    if not bytes_:raise ValueError('oversized SPIR-V has no supported workgroup array')
    source_path=path.with_suffix('.comp');source_path.write_text(source)
    subprocess.run(['glslangValidator','-V','--target-env','vulkan1.2','-Os','-S','comp',str(source_path),'-o',str(path)],check=True,capture_output=True)
    result=workgroup_glsl.barrier_storage(path.read_bytes())
    result,_=shader_vk.formatless_image_capabilities(result);path.write_bytes(result)
    subprocess.run(['spirv-val','--target-env','vulkan1.2',str(path)],check=True,capture_output=True)
    if shared_bytes(result)>limit:raise ValueError('lowering left oversized workgroup storage')
    before={b['binding']:(b['type'],b['dim'],b['arrayed'],b['count']) for b in shader_vk.spirv_bindings(binary)[0]}
    after={b['binding']:(b['type'],b['dim'],b['arrayed'],b['count']) for b in shader_vk.spirv_bindings(result)[0]}
    if any(after.get(b)!=v for b,v in before.items()) or set(after)!=set(before)|{binding}:raise ValueError('lowering changed existing descriptor interfaces')
    return result,bytes_


def reflection(data,binding,bytes_):
    header=list(struct.unpack_from('<5I',data));end=20+header[0]*20
    if end+header[1]>len(data) or header[0]>=96:raise ValueError('invalid or full reflection')
    header[0]+=1
    record=struct.pack('<BBBBHHhBBii',16,1,255,0,binding,1,-1,0,0,bytes_,0)
    return struct.pack('<5I',*header)+data[20:end]+record+data[end:]


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('source',type=Path);parser.add_argument('destination',type=Path);parser.add_argument('--work',required=True,type=Path);parser.add_argument('--limit',required=True,type=int);args=parser.parse_args()
    if args.limit<4:raise ValueError('invalid device shared-memory limit')
    args.work.mkdir(parents=True,exist_ok=True);changed=[]
    with args.source.open('rb') as source,mmap.mmap(source.fileno(),0,access=mmap.ACCESS_READ) as data:
        magic,version,count=struct.unpack_from('<4sII',data)
        if magic!=b'DMSV' or version!=1 or 12+32*count>len(data):raise ValueError('invalid DMSV')
        entries=[struct.unpack_from('<Q6I',data,12+i*32) for i in range(count)];replacements={}
        for key,stage,offset,size,roff,rsize,flags in entries:
            if offset+size>len(data) or roff+rsize>len(data):raise ValueError('truncated DMSV entry')
            if stage!=5:continue
            binary=data[offset:offset+size];bytes_=shared_bytes(binary)
            if bytes_<=args.limit:continue
            old=shader_vk.spirv_bindings(binary)[0];binding=max((b['binding'] for b in old),default=-1)+1
            new,spilled=spill(binary,binding,args.limit,args.work/f'{key:016x}.spv')
            new_reflection=reflection(data[roff:roff+rsize],binding,spilled);replacements[key]=(new,new_reflection,flags|8)
            changed.append({'key':f'{key:016x}','shared_bytes':bytes_,'spill_bytes':spilled,'binding':binding});print(changed[-1],flush=True)
        temporary=args.destination.with_suffix(args.destination.suffix+'.new')
        try:
            with temporary.open('wb') as output:
                output.write(struct.pack('<4sII',magic,version,count));output.write(bytes(32*count));table=[]
                for key,stage,offset,size,roff,rsize,flags in entries:
                    binary,meta,newflags=replacements.get(key,(None,None,flags));where=output.tell()
                    output.write(binary if binary is not None else data[offset:offset+size]);length=output.tell()-where;meta_at=output.tell()
                    output.write(meta if meta is not None else data[roff:roff+rsize]);table.append(struct.pack('<Q6I',key,stage,where,length,meta_at,output.tell()-meta_at,newflags))
                output.seek(12);output.write(b''.join(table))
            temporary.replace(args.destination)
        finally:temporary.unlink(missing_ok=True)
    report={'modules':count,'limit':args.limit,'changed':changed};(args.work/'audit.json').write_text(json.dumps(report,indent=2)+'\n');print(f'{len(changed)} workgroup modules lowered; all changed SPIR-V independently validates')


if __name__=='__main__':main()
