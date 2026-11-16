#!/usr/bin/env python3
"""Synthetic guarded Ampere scoreboard writes; run with vk_warp32. No game inputs."""

import argparse
import json
from pathlib import Path
import re
import struct
import subprocess

TOOLS = Path(__file__).resolve().parents[1] / "nxnative/dm/gfx/tools"


def inst(hi, lo):
    return struct.pack("<QQ", lo, hi)


def mov(rd, value):
    return inst(0x000FC60000000F00, value << 32 | rd << 16 | 0x7802)


def predicate(value):
    # ISETP.GE.AND P0, PT, R5, 32, PT.
    return mov(5, 40 if value else 1) + inst(
        0x000FE20003F06070, 32 << 32 | 5 << 24 | 0x780C
    )


def mufu(guard=7, barrier=0, src=2):
    hi = (0x000FE20000000800 & ~(7 << 46)) | barrier << 46
    return inst(hi, src << 32 | 1 << 16 | guard << 12 | 0x308)


def build(out, xlate):
    out.mkdir(parents=True, exist_ok=True)
    cases = {}
    for inverse in (False, True):
        for active in (False, True):
            for change in (False, True):
                name = f"guard-{int(inverse)}-{int(active)}-{int(change)}"
                pred = active != inverse
                code = (
                    mov(1, 0x41100000)
                    + mov(2, 0x3F800000)
                    + mov(3, 0x40E00000)
                    + predicate(pred)
                )
                code += mufu(8 if inverse else 0)
                # Complementary guarded MOV R1, R3 before the deferred result lands.
                code += inst(
                    0x000FC60000000F00,
                    3 << 32 | 1 << 16 | (0 if inverse else 8) << 12 | 0x202,
                )
                if change:
                    code += predicate(not pred)
                cases[name] = (code, 0x40000000 if active else 0x40E00000)
    # A later guarded-off deferred write must not cancel an earlier live result.
    cases["guarded-off-reissue"] = (
        mov(1, 0x41100000)
        + mov(2, 0x3F800000)
        + mov(3, 0x40000000)
        + predicate(False)
        + mufu()
        + mufu(0, 1, 3),
        0x40000000,
    )
    for change in (False, True):
        code = mov(1, 0x41100000) + mov(2, 0x3F800000) + mov(3, 0x40E00000)
        code += inst(0x000FE20000000000 | 33 << 8, 0x7919 | 5 << 16)
        code += inst(0x000FE20003F06070, 32 << 32 | 5 << 24 | 0x780C) + mufu(0)
        code += inst(0x000FC60000000F00, 3 << 32 | 1 << 16 | 8 << 12 | 0x202)
        if change:
            code += predicate(False)
        cases[f"lane-guard-{int(change)}"] = (
            code,
            [0x40E00000] * 32 + [0x40000000] * 32,
        )
    jobs = []
    for name, (code, _) in cases.items():
        # STS waits for barriers 0 and 1, then exports the destination register.
        code += inst(0x000FE80000000800 | 3 << 52, 1 << 32 | 255 << 24 | 0x7388)
        code += inst(0x000FEA0003800000, 0x794D)
        binary = out / (name + ".bin")
        binary.write_bytes(code)
        jobs.append(
            dict(
                key=name,
                stage="cs",
                arch="sm86",
                code=str(binary),
                tex={},
                img={},
                attr={},
                fout={},
                debug=False,
                reduced=True,
                local=[32, 2, 1],
                shared=512,
                nvn2_cs=[0, 0, 0, 0x40, 0],
                subgroup_size=128,
            )
        )
    (out / "jobs.json").write_text(json.dumps(jobs))
    subprocess.run([str(xlate), str(out / "jobs.json"), str(out)], check=True)
    manifest = []
    for name, (_, expected) in cases.items():
        source = subprocess.check_output(
            [
                str(TOOLS / "spirv_cross_bin/spirv-cross"),
                str(out / (name + ".spv")),
                "--vulkan-semantics",
                "--version",
                "460",
            ],
            text=True,
        )
        source = source.replace("gl_LocalInvocationID.x", "gl_LocalInvocationIndex")
        shared = re.search(r"shared uint (\w+)\[128\];", source)[1]
        source, n = re.subn(
            r"\b" + shared + r"\[0\] =",
            "result.words[gl_LocalInvocationIndex] =",
            source,
        )
        assert n == 1, (name, n)
        source = source.replace(
            "void main()",
            "layout(std430,binding=31) buffer Results {uint words[];} result;\nvoid main()",
        )
        path = out / (name + ".comp")
        path.write_text(source)
        spv = out / (name + ".vk.spv")
        subprocess.run(
            [
                "glslangValidator",
                "-V",
                "--target-env",
                "vulkan1.2",
                "-Os",
                str(path),
                "-o",
                str(spv),
            ],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["spirv-val", "--target-env", "vulkan1.2", str(spv)],
            check=True,
            capture_output=True,
        )
        values = expected if isinstance(expected, list) else [expected] * 64
        (out / (name + ".expected")).write_bytes(struct.pack("<64I", *values))
        manifest.append(f"{name} 64 0")
    (out / "manifest.tsv").write_text("\n".join(manifest) + "\n")
    return len(cases)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("out", type=Path)
    parser.add_argument(
        "--xlate", type=Path, default=TOOLS / "dmsh_xlate_bin/dmsh_xlate"
    )
    args = parser.parse_args()
    print("validated fixtures:", build(args.out.resolve(), args.xlate.resolve()))
