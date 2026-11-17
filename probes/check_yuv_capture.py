#!/usr/bin/env python3
"""Independent CPU YUV matrix check for a captured four-pixel conversion.

R8 Y and half-resolution RG8 UV are normalized to floats. UV samples use the
quarter-texel bilinear footprint at each Y pixel center; RGB comes from the
captured 3x3 matrix and offsets, with float32 fused operations and UNORM output.
Requires NumPy. Hardware sampler precision may account for a one-byte error.
"""
import argparse
import json
from pathlib import Path
import struct
import numpy as np

def check(base):
    def load(binding,phase='before'):return Path(f'{base}.b{binding}.{phase}.bin').read_bytes()
    rows=[r.split() for r in Path(str(base)+'.tsv').read_text().splitlines()]
    images={int(r[1]):[int(v) for v in r[2:]] for r in rows if r[0]=='image'}
    ymeta,uvmeta,outmeta=(images[i] for i in (1,2,3));_,width,height,fmt,*_=ymeta
    if fmt!=9 or uvmeta[3]!=16 or outmeta[3]!=37:raise ValueError('requires R8/RG8 inputs and RGBA8 UNORM output')
    if uvmeta[1:3]!=[width//2,height//2] or outmeta[1:3]!=[width,height]:raise ValueError('unsupported dimensions')
    sampler=struct.unpack('<8B8f',Path(f'{base}.b2.sampler.bin').read_bytes())
    if sampler[1]!=1 or sampler[2:4]!=(7,7):raise ValueError(f'requires linear magnification and edge-clamped UV sampler: {sampler[:8]}')
    y=np.frombuffer(load(1),np.uint8).reshape(height,width).astype(np.float32)/np.float32(255)
    uv=np.frombuffer(load(2),np.uint8).reshape(height//2,width//2,2).astype(np.float32)/np.float32(255)
    fx=np.arange(width,dtype=np.float32)/2-np.float32(.25);fy=np.arange(height,dtype=np.float32)/2-np.float32(.25)
    x0=np.floor(fx).astype(int);y0=np.floor(fy).astype(int);wx=(fx-x0).astype(np.float32)[None,:,None];wy=(fy-y0).astype(np.float32)[:,None,None]
    x1=np.clip(x0+1,0,width//2-1);y1=np.clip(y0+1,0,height//2-1);x0=np.clip(x0,0,width//2-1);y0=np.clip(y0,0,height//2-1)
    top=uv[y0[:,None],x0[None,:]]*(1-wx)+uv[y0[:,None],x1[None,:]]*wx
    bottom=uv[y1[:,None],x0[None,:]]*(1-wx)+uv[y1[:,None],x1[None,:]]*wx
    samples=top*(1-wy)+bottom*wy
    constants=np.frombuffer(load(4),'<f4').reshape(-1,4);offset=constants[3,:3]
    y=y+offset[0];u=samples[:,:,0]+offset[1];v=samples[:,:,1]+offset[2]
    expected=np.full((height,width,4),255,dtype=np.uint8)
    def fma(a,b,c):return (a.astype(np.float64)*np.float64(b)+c.astype(np.float64)).astype(np.float32)
    for channel in range(3):
        matrix=constants[channel,:3];color=fma(v,matrix[2],fma(y,matrix[0],u*matrix[1]))
        expected[:,:,channel]=np.rint(np.clip(color,0,1)*255).astype(np.uint8)
    actual=np.frombuffer(load(3,'after'),np.uint8).reshape(height,width,4)
    error=np.abs(actual.astype(np.int16)-expected.astype(np.int16))
    return {'pixels':width*height,'max_byte_error':int(error.max()),'channels_over_one_byte':int((error>1).sum()),'different_channels':int((error!=0).sum()),'mean_byte_error':float(error.mean()),'matrix':constants[:4].tolist()}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('capture',type=Path);a=p.parse_args();result=check(a.capture);print(json.dumps(result,indent=2));raise SystemExit(bool(result['channels_over_one_byte']))
