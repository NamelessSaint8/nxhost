#!/usr/bin/env python3
"""Apply the generic raw-pool lookup cache for guarded capture experiments."""
import argparse
from pathlib import Path
import subprocess
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'nxnative/dm/android/tools'))
from gmem_cache_spv import cache_lookup


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input',type=Path);parser.add_argument('output',type=Path)
    args=parser.parse_args()
    binary,count=cache_lookup(args.input.read_bytes())
    if not count:raise ValueError('no recognized raw pool search')
    args.output.write_bytes(binary)
    subprocess.run(['spirv-val','--target-env','vulkan1.2',str(args.output)],check=True)
    print(f'cached {count} raw pool helpers')
