#!/usr/bin/env python3
"""Independent two-pool integer proof for the last-lookup cache candidate."""
import argparse
from pathlib import Path
import struct
import subprocess

from cache_raw_lookup import cache_lookup
from raw_memory_guard import guard


def build(out):
    out.mkdir(parents=True,exist_ok=True)
    steps=[]
    for step in (1<<i for i in reversed(range(12))):
        steps.append(f'''{{int candidate=index+{step};int entry=candidate*8;
uint sl=map.words[entry],sh=map.words[entry+1];
uint below=uint(sh<hi)|(uint(sh==hi)&uint(sl<=lo));index=below!=0u?candidate:index;}}''')
    source='''#version 460
#extension GL_EXT_buffer_reference2 : require
#extension GL_EXT_shader_explicit_arithmetic_types_int64 : require
layout(local_size_x=32) in;
layout(binding=0) readonly buffer Map {uint words[];} map;
layout(binding=1) buffer Output {uint values[];} result;
layout(buffer_reference,buffer_reference_align=4) buffer Word {uint value;};
uint raw_read(int low,int high){uint lo=uint(low),hi=uint(high);int index=0;
'''+ '\n'.join(steps)+'''
int entry=index*8;uint el=map.words[entry+2],eh=map.words[entry+3];
uint inside=uint(hi<eh)|(uint(hi==eh)&uint(lo<el));if(inside==0u)return 0;
uint64_t address=(uint64_t(hi)<<32)|uint64_t(lo);
uint64_t delta=(uint64_t(map.words[entry+5])<<32)|uint64_t(map.words[entry+4]);
return Word(address+delta).value;}
void main(){uint lane=gl_LocalInvocationIndex;
uint a=raw_read(int(1024u+lane*4u),1);
uint b=raw_read(int(1024u+((lane+1u)%32u)*4u),1);
uint c=raw_read(int(512u+lane*4u),2);
uint edge=raw_read(4096,2),missing=raw_read(0,0);
result.values[lane]=(a+b)^c^edge^missing;}
'''
    (out/'proof.comp').write_text(source)
    subprocess.run(['glslangValidator','-V','--target-env','vulkan1.2',str(out/'proof.comp'),'-o',str(out/'baseline.spv')],check=True,capture_output=True)
    baseline=(out/'baseline.spv').read_bytes();cached,count=cache_lookup(baseline)
    (out/'cached.spv').write_bytes(cached)
    for name,binary in [('baseline',baseline),('cached',cached)]:
        guarded,_=guard(binary,2);path=out/f'{name}.guard.spv';path.write_bytes(guarded)
        subprocess.run(['spirv-val','--target-env','vulkan1.2',str(path)],check=True)
    pool0=bytearray(b'\x3c'*4096);pool1=bytearray(b'\x5a'*4096)
    a=[0x12340000+i*0x113 for i in range(32)];c=[0xabcd0000+i*0x71 for i in range(32)]
    struct.pack_into('<32I',pool0,1024,*a);struct.pack_into('<32I',pool1,512,*c)
    after=bytearray(pool0)
    struct.pack_into('<32I',after,256,*[((a[i]+a[(i+1)%32])&0xffffffff)^c[i] for i in range(32)])
    table=bytearray(4096*32)
    for i in range(1,4096):struct.pack_into('<Q',table,i*32,0xffffffffffffffff)
    for i,guest in enumerate((1<<32,2<<32),1):struct.pack_into('<4Q',table,i*32,guest,guest+4096,0,0)
    base=out/'proof'
    base.with_suffix('.tsv').write_text('capture 2\ndispatch 0000000000000001 1 1 1\nglobal_memory 0 map\nbuffer 0 7 131072\nbuffer 1 7 128\npool 0 4294967296 4096\npool 1 8589934592 4096\nalias 1 0 256\n')
    for suffix,data in [('b0.before',table),('b1.before',pool0[256:384]),('p0.before',pool0),('p0.after',after),('p1.before',pool1),('p1.after',pool1)]:
        Path(str(base)+'.'+suffix+'.bin').write_bytes(data)
    print(f'{count} cached helper; two pools, repeated hits, misses, end boundary, null and canaries -> {out}')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('out',type=Path)
    build(parser.parse_args().out)
