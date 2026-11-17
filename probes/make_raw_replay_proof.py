#!/usr/bin/env python3
"""Synthetic aliased pool capture with an independent integer reference."""
import argparse
from pathlib import Path
import struct
import subprocess
from raw_memory_guard import guard

def build(out):
    out.mkdir(parents=True,exist_ok=True)
    source=(Path(__file__).parent/'shaders/global-memory.comp').read_text()
    source=source.replace('atomicAdd(word.value,17u+lane)','word.value')
    source=source.replace('    result.value[2048+lane]=flags;','')
    source=source.replace('    if((flags&1u)==0)record(target);','    word.value=result.value[lane]+17u+lane;\n    if((flags&1u)==0)record(target);')
    (out/'plain.comp').write_text(source)
    subprocess.run(['glslangValidator','-V','--target-env','vulkan1.2',str(out/'plain.comp'),'-o',str(out/'plain.spv')],check=True,capture_output=True)
    binary,count=guard((out/'plain.spv').read_bytes());(out/'guard.spv').write_bytes(binary)
    subprocess.run(['spirv-val','--target-env','vulkan1.2',str(out/'guard.spv')],check=True)
    guest=0x100000000;size=256*1024
    before=bytearray(b'\x3c'*size);struct.pack_into('<Q',before,0,guest+4096)
    after=bytearray(before)
    for lane in range(32):
        struct.pack_into('<I',after,256+lane*4,0x3c3c3c3c)
        struct.pack_into('<I',after,4096+lane*4096,0x3c3c3c3c+17+lane)
    table=bytearray(131072)
    for i in range(1,4096):struct.pack_into('<Q',table,i*32,0xffffffffffffffff)
    struct.pack_into('<4Q',table,32,guest,guest+size,0xdead000000-guest,0)
    for name,extent in [('valid',size),('missing',16384)]:
        base=out/name
        base.with_suffix('.tsv').write_text(f'capture 2\ndispatch 0000000000000001 1 1 1\nglobal_memory 1 map\nglobal_memory 2 log\nbuffer 0 7 8\nbuffer 1 7 131072\nbuffer 2 7 4100\nbuffer 3 7 128\npool 0 {guest} {extent}\nalias 0 0 0\nalias 3 0 256\n')
        for suffix,data in [('p0.before',before[:extent]),('p0.after',after[:extent]),('b0.before',before[:8]),('b1.before',table),('b2.before',bytes(4100)),('b3.before',before[256:384])]:
            Path(str(base)+'.'+suffix+'.bin').write_bytes(data)
    print(f'{count} guarded sites; independent pool reference -> {out}')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('out',type=Path);build(p.parse_args().out)
