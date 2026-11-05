#!/usr/bin/env python3
# dmsv_pad: give a vertex shader the outputs its paired pixel shaders read but it does not write.
# On the hardware an attribute the vertex stage never wrote reads as (0,0,0,1), and NVN's pixel stage simply reads it; Vulkan refuses to link such a pair
# ("Fragment input ... not written by vertex shader"). dmsh_build.py's vs_pad patches the Mac chain's MSL text for the same reason (331 of 9,043 pairs
# failed to link before it); this is the SPIR-V side, for dm/android/tools/shader_vk.py.
#   from dmsv_pad import pad             # pad(vs_spv, [ps_spv, ...]) -> (new vs_spv, [locations added], [locations skipped])
# Only scalar and vector 32-bit float/int inputs are padded (what an NVN2 attribute is); a pixel-stage input of any other type (a matrix, an array, a
# struct member) is reported and left alone, so that pair fails to link exactly as before rather than being padded wrongly.
import struct

OP_ENTRY_POINT, OP_DECORATE, OP_TYPE_INT, OP_TYPE_FLOAT, OP_TYPE_VECTOR, OP_TYPE_POINTER = 15, 71, 21, 22, 23, 32
OP_CONSTANT, OP_CONSTANT_COMPOSITE, OP_VARIABLE, OP_STORE, OP_FUNCTION, OP_LABEL = 43, 44, 59, 62, 54, 248
ANNOTATIONS, DECORATE_LOCATION, SC_INPUT, SC_OUTPUT = (71, 72, 73, 74, 75), 30, 1, 3


def _words(b): return list(struct.unpack(f'<{len(b) // 4}I', b))
def _blob(w): return struct.pack(f'<{len(w)}I', *w)


def _chunks(w):
    """the module's instructions, each as its own list of words (the 5-word header is dropped)"""
    out, i = [], 5
    while i < len(w):
        wc = w[i] >> 16
        if not wc: break
        out.append(w[i:i + wc]); i += wc
    return out


def _op(c): return c[0] & 0xffff


def _type_of(chunks, tid):
    """('float'|'int', width, components, signed) of a scalar or vector type id, else None"""
    for c in chunks:
        if len(c) < 2 or c[1] != tid: continue
        op = _op(c)
        if op == OP_TYPE_FLOAT and c[2] == 32: return ('float', 32, 1, False)
        if op == OP_TYPE_INT and c[2] == 32: return ('int', 32, 1, bool(c[3]))
        if op == OP_TYPE_VECTOR:
            inner = _type_of(chunks, c[2])
            return None if inner is None else (inner[0], inner[1], c[3], inner[3])
    return None


def _io_locations(chunks, storage):
    """{location: type} of the module's Input (1) or Output (3) variables"""
    ptr, deco, vars_, locs = {}, {}, [], {}
    for c in chunks:
        op = _op(c)
        if op == OP_DECORATE and len(c) > 3: deco.setdefault(c[1], {})[c[2]] = c[3]
        elif op == OP_TYPE_POINTER: ptr[c[1]] = (c[2], c[3])
        elif op == OP_VARIABLE: vars_.append((c[1], c[2], c[3]))
    for rtype, rid, sc in vars_:
        if sc != storage or DECORATE_LOCATION not in deco.get(rid, {}): continue
        p = ptr.get(rtype)
        t = _type_of(chunks, p[1]) if p else None
        if t: locs[deco[rid][DECORATE_LOCATION]] = t
    return locs


def pad(vs, pss):
    """(new vertex SPIR-V, locations added, locations skipped) for one vertex module and the pixel modules paired with it"""
    wv = _words(vs)
    chunks = _chunks(wv)
    outs = _io_locations(chunks, SC_OUTPUT)
    want, skipped = {}, []
    for ps in pss:
        for loc, t in _io_locations(_chunks(_words(ps)), SC_INPUT).items():
            if loc in outs: continue
            if t[2] > 4: skipped.append(loc); continue
            want.setdefault(loc, t)
    if not want: return vs, [], sorted(set(skipped))

    nid = wv[3]                                    # the module's bound is its first free id
    def new():
        nonlocal nid
        nid += 1
        return nid - 1

    decls, consts, decos, stores, iface = [], [], [], [], []
    scalars = {}
    for loc, t in sorted(want.items()):
        kind, _, comps, signed = t
        key = (kind, signed)
        if key not in scalars:
            scalars[key] = new()
            sid = scalars[key]
            decls.append([(3 << 16) | OP_TYPE_FLOAT, sid, 32] if kind == 'float'
                         else [(4 << 16) | OP_TYPE_INT, sid, 32, 1 if signed else 0])
        scalar = scalars[key]
        ty = scalar
        if comps > 1:
            ty = new(); decls.append([(4 << 16) | OP_TYPE_VECTOR, ty, scalar, comps])
        ptr = new(); decls.append([(4 << 16) | OP_TYPE_POINTER, ptr, SC_OUTPUT, ty])
        zero = new(); consts.append([(4 << 16) | OP_CONSTANT, scalar, zero, 0])
        if comps == 1:
            value = zero
        else:
            parts = [zero] * comps
            if kind == 'float':                    # (0,0,0,1): the w an unwritten attribute carries
                parts[-1] = new(); consts.append([(4 << 16) | OP_CONSTANT, scalar, parts[-1], 0x3f800000])
            value = new(); consts.append([((3 + comps) << 16) | OP_CONSTANT_COMPOSITE, ty, value] + parts)
        var = new(); consts.append([(4 << 16) | OP_VARIABLE, ptr, var, SC_OUTPUT])
        decos.append([(4 << 16) | OP_DECORATE, var, DECORATE_LOCATION, loc])
        stores.append([(3 << 16) | OP_STORE, var, value])
        iface.append(var)

    # splice: decorations after the last annotation, declarations before the first function, stores after the entry block's variables
    last_ann = max((n for n, c in enumerate(chunks) if _op(c) in ANNOTATIONS), default=None)
    first_fn = next((n for n, c in enumerate(chunks) if _op(c) == OP_FUNCTION), None)
    ep = next((n for n, c in enumerate(chunks) if _op(c) == OP_ENTRY_POINT), None)
    if first_fn is None or ep is None: return vs, [], sorted(set(skipped) | set(want))
    fn_id = chunks[ep][2]
    fn_at = next((n for n, c in enumerate(chunks) if _op(c) == OP_FUNCTION and len(c) > 2 and c[2] == fn_id), None)
    if fn_at is None: return vs, [], sorted(set(skipped) | set(want))
    label = next((n for n, c in enumerate(chunks) if _op(c) == OP_LABEL and n > fn_at), None)
    if label is None: return vs, [], sorted(set(skipped) | set(want))
    store_at = label + 1
    while store_at < len(chunks) and _op(chunks[store_at]) == OP_VARIABLE: store_at += 1

    chunks[ep] = [((len(chunks[ep]) + len(iface)) << 16) | OP_ENTRY_POINT] + chunks[ep][1:] + iface
    out = []
    for n, c in enumerate(chunks):
        if last_ann is None and n == 0: out.extend(decos)
        out.append(c)
        if n == last_ann: out.extend(decos)
        if n == store_at - 1: out.extend(stores)
        if n + 1 == first_fn: out.extend(decls); out.extend(consts)
    flat = wv[:5] + [w for c in out for w in c]
    flat[3] = nid
    return _blob(flat), sorted(want), sorted(set(skipped))
