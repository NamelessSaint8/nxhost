#!/usr/bin/env python3
"""Independently validate the runtime atlas transform across a complete DMSV."""
import argparse
import concurrent.futures
import json
import struct
import subprocess
from pathlib import Path


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('bundle',type=Path)
    parser.add_argument('--tool',type=Path,required=True)
    parser.add_argument('--work',type=Path,required=True)
    parser.add_argument('--jobs',type=int,default=4)
    args=parser.parse_args();args.work.mkdir(parents=True,exist_ok=True)
    data=args.bundle.read_bytes();magic,version,count=struct.unpack_from('<4sII',data)
    if magic!=b'DMSV' or version!=1:raise ValueError('invalid bundle')
    jobs=[]
    for index in range(count):
        key,stage,offset,size,ro,rs,flags=struct.unpack_from('<Q6I',data,12+32*index)
        if offset+size>len(data) or ro+rs>len(data):raise ValueError('truncated entry')
        bindings=struct.unpack_from('<I',data,ro)[0];pairs=[]
        for i in range(bindings):
            kind,desc,dim,bflags,binding,n,reg,samp,fmt,slot,sarg=struct.unpack_from('<BBBBHHhBBii',data,ro+20+i*20)
            if kind==15 and 0<=slot<64:pairs.extend((str(binding),str(slot)))
        if pairs:jobs.append((key,data[offset:offset+size],pairs))

    def check(job):
        key,binary,pairs=job;source=args.work/f'{key:016x}.input.spv';dest=args.work/f'{key:016x}.spv';source.write_bytes(binary)
        result=subprocess.run([str(args.tool),str(source),str(dest),*pairs],capture_output=True,text=True)
        if result.returncode==3:return 'unchanged',None
        if result.returncode:return 'failed',{'key':f'{key:016x}','error':result.stdout+result.stderr}
        validated=subprocess.run(['spirv-val','--target-env','vulkan1.2',str(dest)],capture_output=True,text=True)
        if validated.returncode:return 'failed',{'key':f'{key:016x}','error':validated.stdout+validated.stderr}
        return 'validated',None

    totals={'programs':count,'candidates':len(jobs),'validated':0,'unchanged':0,'failed':0};failures=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as pool:
        for i,(status,error) in enumerate(pool.map(check,jobs),1):
            totals[status]+=1
            if error:failures.append(error)
            if i%500==0:print(i,totals,flush=True)
    report={**totals,'failures':failures};(args.work/'audit.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report if not failures else {**totals,'failures':failures[:8]},indent=2))
    raise SystemExit(bool(failures))


if __name__=='__main__':main()
