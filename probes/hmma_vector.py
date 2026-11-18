#!/usr/bin/env python3
"""Vectorize independent scalar K16 FMA chains without changing their operands.

Diagnostic only. Retains the existing gathers, cache, barriers, per-component
FMA order and final half packs. Unsupported or externally used chains stay intact.
"""

import argparse
from collections import Counter
import json
from pathlib import Path
import subprocess

from hmma_shuffle import hmma_spv as spv


def transform(binary, width=4):
    if width not in (2, 4):
        raise ValueError("requires vector width two or four")
    m = spv.Module(binary)
    if not m.entry or m.entry[1] != 5:
        return binary, 0
    f32 = m.find_type(spv.OP_TYPE_FLOAT, 32)
    if f32 is None:
        return binary, 0
    vec = m.add_type(spv.OP_TYPE_VECTOR, f32, width)
    glsl = spv.ensure_glsl(m)
    definitions = {}
    positions = {}
    blocks = {}
    uses = Counter()
    block = None
    inside = False
    for i, x in enumerate(m.ins):
        op = x[0] & 65535
        if op == spv.OP_FUNCTION:
            inside = True
        if op == spv.OP_FUNCTION_END:
            inside = False
        if not inside:
            continue
        if op == spv.OP_LABEL:
            block = x[1]
        uses.update(x[1:])  # Literal collisions only cause conservative rejection.
        if op in (spv.OP_EXT_INST, spv.OP_COMPOSITE_CONSTRUCT):
            definitions[x[2]] = x
            positions[x[2]] = i
            blocks[x[2]] = block

    def fma(ident):
        x = definitions.get(ident)
        return (
            x
            if x
            and len(x) == 8
            and x[0] & 65535 == spv.OP_EXT_INST
            and x[1] == f32
            and x[3:5] == [glsl, spv.GLSL_FMA]
            else None
        )

    def chain(ident):
        rows = []
        while (x := fma(ident)) is not None:
            if uses[ident] != 2 or any(d != 42 for d in m.decos.get(ident, {})):
                return None
            rows.append(x)
            ident = x[7]
            if len(rows) > 16:
                return None
        return (list(reversed(rows)), ident) if len(rows) == 16 else None

    packs = []
    for ident, x in definitions.items():
        if (
            len(x) != 6
            or x[0] & 65535 != spv.OP_EXT_INST
            or x[3:5] != [glsl, spv.GLSL_PACK_HALF_2X16]
        ):
            continue
        value = definitions.get(x[5])
        if (
            not value
            or value[0] & 65535 != spv.OP_COMPOSITE_CONSTRUCT
            or len(value) != 5
        ):
            continue
        ty = m.types.get(value[1])
        lanes = [chain(v) for v in value[3:]]
        if (
            not ty
            or ty[0] & 65535 != spv.OP_TYPE_VECTOR
            or ty[2:] != [f32, 2]
            or any(c is None for c in lanes)
        ):
            continue
        if uses[value[2]] != 2:
            continue
        packs.append((ident, x, value, lanes))
    removed = set()
    discarded = set()
    deferred_positions = set()
    insertions = {}
    decorations = []
    count = 0
    for at in range(0, len(packs), width // 2):
        group = packs[at : at + width // 2]
        if len(group) != width // 2 or len({blocks[p[0]] for p in group}) != 1:
            continue
        last = positions[group[-1][0]]
        deferred = []
        if width == 4:
            first = positions[group[0][0]]
            # The first pack moves to the second pack. Its result must not be
            # observed in between, and no barrier, write, call or branch moves.
            aliases = {group[0][0]}
            admissible = True
            for index in range(first + 1, last):
                x = m.ins[index]
                if aliases.intersection(x[1:]):
                    if x[0] & 65535 not in (spv.OP_BITCAST, spv.OP_COPY_OBJECT):
                        admissible = False
                        break
                    aliases.add(x[2])
                    deferred.append((index, x))
            if not admissible:
                continue
            pure = {
                spv.OP_EXT_INST,
                spv.OP_COMPOSITE_EXTRACT,
                spv.OP_COMPOSITE_CONSTRUCT,
                spv.OP_LOAD,
                spv.OP_ACCESS_CHAIN,
                spv.OP_IN_BOUNDS_ACCESS_CHAIN,
                spv.OP_BITCAST,
                spv.OP_COPY_OBJECT,
            }
            if any(x[0] & 65535 not in pure for x in m.ins[first + 1 : last]):
                continue
        lanes = [c for p in group for c in p[3]]
        ids = [x[2] for rows, _ in lanes for x in rows]
        if len(set(ids)) != len(ids) or set(ids) & removed:
            continue
        source_ids = [c for rows, init in lanes for x in rows for c in x[5:7]] + [
            init for _, init in lanes
        ]
        if set(source_ids) & set(ids):
            continue
        emitted = []

        def emit(op, ty, *args):
            ident = m.new_id()
            emitted.append([(3 + len(args)) << 16 | op, ty, ident, *args])
            return ident

        acc = emit(spv.OP_COMPOSITE_CONSTRUCT, vec, *(init for _, init in lanes))
        for k in range(16):
            a = emit(
                spv.OP_COMPOSITE_CONSTRUCT, vec, *(rows[k][5] for rows, _ in lanes)
            )
            b = emit(
                spv.OP_COMPOSITE_CONSTRUCT, vec, *(rows[k][6] for rows, _ in lanes)
            )
            acc = emit(spv.OP_EXT_INST, vec, glsl, spv.GLSL_FMA, a, b, acc)
            if any(42 in m.decos.get(rows[k][2], {}) for rows, _ in lanes):
                decorations.append([3 << 16 | spv.OP_DECORATE, acc, 42])
        for pindex, (_, pack, value, _) in enumerate(group):
            parts = [
                emit(spv.OP_COMPOSITE_EXTRACT, f32, acc, pindex * 2 + j)
                for j in range(2)
            ]
            emitted.append(
                [5 << 16 | spv.OP_COMPOSITE_CONSTRUCT, value[1], value[2], *parts]
            )
            emitted.append(list(pack))
            removed.update((pack[2], value[2]))
        emitted.extend(x for _, x in deferred)
        deferred_positions.update(index for index, _ in deferred)
        removed.update(ids)
        discarded.update(ids)
        insertions[last] = emitted
        count += 1
    if not count:
        return binary, 0
    out = []
    for i, x in enumerate(m.ins):
        op = x[0] & 65535
        if i in insertions:
            out.extend(insertions[i])
        if i in deferred_positions:
            continue
        if op in (spv.OP_EXT_INST, spv.OP_COMPOSITE_CONSTRUCT) and x[2] in removed:
            continue
        if op in (spv.OP_NAME, spv.OP_DECORATE) and x[1] in discarded:
            continue
        out.append(x)
    if decorations:
        first_type = next(i for i, x in enumerate(out) if 19 <= x[0] & 65535 <= 39)
        out[first_type:first_type] = decorations
    m.ins = out
    return m.data(), count


def build(source, target, width=4):
    source, target = Path(source), Path(target)
    if source.resolve() == target.resolve():
        raise ValueError("refusing to overwrite source module")
    binary, count = transform(source.read_bytes(), width)
    target.write_bytes(binary)
    subprocess.run(["spirv-val", "--target-env", "vulkan1.2", str(target)], check=True)
    return dict(
        width=width,
        regions=count,
        scalar_chains=count * width,
        bytes=len(binary),
        diagnostic_only=True,
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("input", type=Path)
    p.add_argument("output", type=Path)
    p.add_argument("--width", type=int, choices=(2, 4), default=4)
    a = p.parse_args()
    print(json.dumps(build(a.input, a.output, a.width), indent=2))
