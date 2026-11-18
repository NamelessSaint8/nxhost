# Adapted from BananaNative dm/gfx/tools/vk_android_spv.py, revision
# 341299f727c85fa5c58b1c44f7a7a8edabc905cc (nxnative-owned code, MIT).
# Only HMMA lowering is retained; no global-memory or general SSA rewrites.
#
# MIT License
# Copyright (c) 2026 seedds
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
"""Bounded, exact-arithmetic HMMA lowering for the Android Vulkan build."""
import struct

MAGIC = 119734787
OP_NAME, OP_EXTENSION, OP_EXT_INST_IMPORT, OP_EXT_INST, OP_ENTRY_POINT, OP_EXECUTION_MODE, OP_CAPABILITY = (5, 10, 11, 12, 15, 16, 17)
OP_TYPE_VOID, OP_TYPE_BOOL, OP_TYPE_INT, OP_TYPE_FLOAT, OP_TYPE_VECTOR, OP_TYPE_IMAGE, OP_TYPE_SAMPLER, OP_TYPE_SAMPLED_IMAGE = (19, 20, 21, 22, 23, 25, 26, 27)
OP_TYPE_ARRAY, OP_TYPE_RUNTIME_ARRAY, OP_TYPE_STRUCT, OP_TYPE_POINTER = (28, 29, 30, 32)
OP_CONSTANT, OP_CONSTANT_COMPOSITE, OP_FUNCTION, OP_FUNCTION_END, OP_VARIABLE, OP_LOAD, OP_STORE = (43, 44, 54, 56, 59, 61, 62)
OP_ACCESS_CHAIN, OP_IN_BOUNDS_ACCESS_CHAIN, OP_DECORATE, OP_MEMBER_DECORATE = (65, 66, 71, 72)
OP_COMPOSITE_EXTRACT, OP_COMPOSITE_INSERT, OP_COPY_OBJECT, OP_BITCAST, OP_FADD, OP_FMUL = (81, 82, 83, 124, 129, 133)
OP_EMIT_VERTEX, OP_EMIT_STREAM_VERTEX, OP_LABEL, OP_RETURN, OP_RETURN_VALUE, OP_IMAGE_TEXEL_POINTER = (218, 220, 248, 253, 254, 60)
SC_UNIFORM_CONSTANT, SC_INPUT, SC_UNIFORM, SC_OUTPUT, SC_FUNCTION, SC_PUSH_CONSTANT, SC_STORAGE_BUFFER = (0, 1, 2, 3, 7, 9, 12)
OP_FUNCTION_PARAMETER, OP_FUNCTION_CALL = (55, 57)
OP_IADD, OP_ISUB, OP_IMUL, OP_SHR_LOGICAL, OP_SHR_ARITH, OP_SHL_LOGICAL, OP_BITWISE_OR, OP_BITWISE_XOR, OP_BITWISE_AND = (128, 130, 132, 194, 195, 196, 197, 198, 199)
OP_CONTROL_BARRIER, OP_GROUP_NON_UNIFORM_SHUFFLE = (224, 345)
SC_WORKGROUP, SCOPE_SUBGROUP, SEM_ACQ_REL_WORKGROUP = (4, 3, 8 | 256)
VN_OPS = {OP_IADD, OP_ISUB, OP_IMUL, OP_SHR_LOGICAL, OP_SHR_ARITH, OP_SHL_LOGICAL, OP_BITWISE_OR, OP_BITWISE_XOR, OP_BITWISE_AND}
HMMA_NAME = 'dmsh_hmma16816_f16'
HMMA_KEEP = 2
OP_MEMORY_BARRIER, OP_COMPOSITE_CONSTRUCT, OP_TYPE_FUNCTION_ = (225, 80, 33)
GLSL_FMA, GLSL_PACK_HALF_2X16, GLSL_UNPACK_HALF_2X16 = (50, 58, 62)
NO_RESULT_OPS = {OP_STORE, OP_CONTROL_BARRIER, OP_MEMORY_BARRIER, OP_RETURN, OP_RETURN_VALUE, 246, 247, 249, 250, 251, 252, OP_FUNCTION_END}

def string_at(words, i):
    """A nul-terminated literal string starting at words[i] → (text, index of the word after it)"""
    out = bytearray()
    while i < len(words):
        b = struct.pack('<I', words[i])
        i += 1
        if 0 in b:
            out += b[:b.index(0)]
            break
        out += b
    return (out.decode('utf-8', 'replace'), i)

def lit_string(text):
    b = text.encode() + b'\x00'
    b += b'\x00' * (-len(b) % 4)
    return list(struct.unpack('<%dI' % (len(b) // 4), b))

class Module:

    def __init__(self, data):
        if len(data) % 4 or len(data) < 20:
            raise ValueError('not a SPIR-V module (length)')
        w = list(struct.unpack('<%dI' % (len(data) // 4), data))
        if w[0] != MAGIC:
            raise ValueError('not a SPIR-V module (magic)')
        self.header, self.ins, i = (w[:5], [], 5)
        while i < len(w):
            n = w[i] >> 16
            if not n or i + n > len(w):
                raise ValueError('malformed SPIR-V instruction at word %d' % i)
            self.ins.append(w[i:i + n])
            i += n
        self.index()

    def index(self):
        self.names, self.decos, self.types, self.consts, self.vars, self.caps, self.exts = ({}, {}, {}, {}, {}, [], [])
        self.entry = None
        self.modes = []
        for x in self.ins:
            op = x[0] & 65535
            if op == OP_NAME:
                self.names[x[1]] = string_at(x, 2)[0]
            elif op == OP_DECORATE:
                self.decos.setdefault(x[1], {})[x[2]] = x[3:]
            elif op == OP_CAPABILITY:
                self.caps.append(x[1])
            elif op == OP_EXTENSION:
                self.exts.append(string_at(x, 1)[0])
            elif op == OP_ENTRY_POINT:
                self.entry = x
            elif op == OP_EXECUTION_MODE:
                self.modes.append(x[2:])
            elif 19 <= op <= 39:
                self.types[x[1]] = x
            elif op == OP_CONSTANT:
                self.consts[x[2]] = (x[1], x[3:])
            elif op == OP_VARIABLE and len(x) >= 4:
                self.vars[x[2]] = (x[1], x[3])

    def data(self):
        return struct.pack('<%dI' % (5 + sum((len(x) for x in self.ins))), *self.header, *(v for x in self.ins for v in x))

    def new_id(self):
        i = self.header[3]
        self.header[3] += 1
        return i

    def op(self, ident):
        return self.types[ident][0] & 65535 if ident in self.types else None

    def pointee(self, ptr):
        t = self.types[ptr]
        return (t[2], t[3])

    def int_type(self, t):
        x = self.types.get(t)
        return (x[2], x[3]) if x and x[0] & 65535 == OP_TYPE_INT else None

    def find_type(self, op, *operands):
        for i, x in self.types.items():
            if x[0] & 65535 == op and x[2:] == list(operands):
                return i
        return None

    def add_type(self, op, *operands):
        """An existing type with these operands, or a new one placed after the last type / constant declaration"""
        i = self.find_type(op, *operands)
        if i is not None:
            return i
        i = self.new_id()
        x = [2 + len(operands) << 16 | op, i, *operands]
        self._insert_decl(x)
        self.types[i] = x
        return i

    def add_const(self, ty, value):
        for i, (t, v) in self.consts.items():
            if t == ty and v == [value]:
                return i
        i = self.new_id()
        x = [4 << 16 | OP_CONSTANT, ty, i, value]
        self._insert_decl(x)
        self.consts[i] = (ty, [value])
        return i

    def _insert_decl(self, x):
        at = next((k for k, y in enumerate(self.ins) if y[0] & 65535 == OP_FUNCTION))
        self.ins.insert(at, x)

    def function_range(self, fid):
        a = next((k for k, x in enumerate(self.ins) if x[0] & 65535 == OP_FUNCTION and x[2] == fid))
        return (a, next((k for k in range(a, len(self.ins)) if self.ins[k][0] & 65535 == OP_FUNCTION_END)))

def functions_named(m):
    return {m.names.get(x[2], ''): x[2] for x in m.ins if x[0] & 65535 == OP_FUNCTION}

def ensure_glsl(m):
    """The GLSL.std.450 import's id, added before OpMemoryModel when the module has none"""
    for x in m.ins:
        if x[0] & 65535 == OP_EXT_INST_IMPORT and string_at(x, 2)[0] == 'GLSL.std.450':
            return x[1]
    i = m.new_id()
    s = lit_string('GLSL.std.450')
    at = next((k for k, x in enumerate(m.ins) if x[0] & 65535 == 14))
    m.ins.insert(at, [2 + len(s) << 16 | OP_EXT_INST_IMPORT, i, *s])
    return i

class BlockValues:
    """Value numbers within a block of the translator's code, which keeps its registers in Function variables: a load of a variable numbers as the value last stored to it in
    the block, or as (variable, version) with a version that every store and every call taking it as an argument moves; bit casts and copies keep their operand's number;
    integer arithmetic numbers by its operation and operands' numbers, a load of an Input variable (or of a constant index into one) by the variable. Two values with one
    number hold the same bits in every lane. see(x) before x is passed on; block()
    at each label; function() at each OpFunction"""

    def __init__(self, m):
        self.m = m
        self.inptr = {}
        self.function()

    def function(self):
        self.fvars, self.fbase, self.ver, self.stored, self.vn = (set(), {}, {}, {}, {})

    def block(self):
        self.stored = {}

    def __call__(self, i):
        return self.vn.get(i, i)

    def key_of_var(self, p):
        b = self.fbase.get(p, p)
        return self(self.stored[p]) if p in self.stored else ('ld', b, self.ver.get(b, 0))

    def bump(self, p):
        b = self.fbase.get(p, p)
        self.ver[b] = self.ver.get(b, 0) + 1
        self.stored.pop(b, None)

    def see(self, x):
        m, op = (self.m, x[0] & 65535)
        if op == OP_FUNCTION:
            self.function()
        elif op == OP_LABEL:
            self.block()
        elif op == OP_VARIABLE and len(x) > 3 and (x[3] == SC_FUNCTION) or (op == OP_FUNCTION_PARAMETER and m.op(x[1]) == OP_TYPE_POINTER and (m.types[x[1]][2] == SC_FUNCTION)):
            self.fvars.add(x[2])
        elif op in (OP_ACCESS_CHAIN, OP_IN_BOUNDS_ACCESS_CHAIN) and (x[3] in self.fvars or x[3] in self.fbase):
            self.fbase[x[2]] = self.fbase.get(x[3], x[3])
        elif op == OP_STORE and (x[1] in self.fvars or x[1] in self.fbase):
            self.bump(x[1])
            if x[1] in self.fvars:
                self.stored[x[1]] = x[2]
        elif op == OP_LOAD and x[3] in self.fvars:
            self.vn[x[2]] = self.key_of_var(x[3])
        elif op == OP_LOAD and (x[3] in self.inptr or m.vars.get(x[3], (0, 0))[1] == SC_INPUT):
            self.vn[x[2]] = ('in', self.inptr.get(x[3], x[3]))
        elif op in (OP_ACCESS_CHAIN, OP_IN_BOUNDS_ACCESS_CHAIN) and m.vars.get(x[3], (0, 0))[1] == SC_INPUT and all((i in m.consts for i in x[4:])):
            self.inptr[x[2]] = (x[3], *x[4:])
        elif op in (OP_BITCAST, OP_COPY_OBJECT):
            self.vn[x[2]] = self(x[3])
        elif op in VN_OPS:
            self.vn[x[2]] = (op, self(x[3]), self(x[4]))
        elif op == OP_FUNCTION_CALL:
            for p in x[4:]:
                if p in self.fvars or p in self.fbase:
                    self.bump(p)

def hmma_helper(m):
    """The translator's HMMA.16816 helper (HelperFunctionManager.GenerateHmma16816F16) when it has the translator's shape: 11 pointer arguments, one block, 8 + 64 accesses
    of one Workgroup array of u32 used by nothing else, two subgroup barriers → {fid, i32, u32, scratch, barrier}, else None"""
    fid = functions_named(m).get(HMMA_NAME)
    if fid is None:
        return None
    a, e = m.function_range(fid)
    i32 = m.ins[a][1]
    if m.int_type(i32) != (32, 1):
        return None
    params = [x for x in m.ins[a + 1:e] if x[0] & 65535 == OP_FUNCTION_PARAMETER]
    if len(params) != 11 or any((m.types.get(p[1], [0, 0, 0, 0])[2:4] != [SC_FUNCTION, i32] for p in params)):
        return None
    body = m.ins[a + 1 + len(params):e]
    if sum((1 for x in body if x[0] & 65535 == OP_LABEL)) != 1:
        return None
    chains = [x for x in body if x[0] & 65535 in (OP_ACCESS_CHAIN, OP_IN_BOUNDS_ACCESS_CHAIN)]
    if len(chains) != 8 + 64 or len({x[3] for x in chains}) != 1:
        return None
    scratch = chains[0][3]
    pwu = chains[0][1]
    if m.vars.get(scratch, (0, 0))[1] != SC_WORKGROUP or m.types.get(pwu, [0, 0, 0])[2] != SC_WORKGROUP:
        return None
    u32 = m.pointee(pwu)[1]
    arr = m.pointee(m.vars[scratch][0])[1]
    if m.int_type(u32) != (32, 0) or m.op(arr) != OP_TYPE_ARRAY or m.types[arr][2] != u32 or m.consts[m.types[arr][3]][1][0] % 4:
        return None
    # OpExtInst's instruction number is a literal, not a module ID. A GLSL
    # opcode can have the same number as scratch without referencing it.
    if any((scratch in (x[1:4] + x[5:] if x[0] & 65535 == OP_EXT_INST else x[1:]) for k, x in enumerate(m.ins) if not a <= k <= e and (not (x[0] & 65535 in (OP_NAME, OP_DECORATE, OP_VARIABLE) or 19 <= x[0] & 65535 <= 52)))):
        return None
    groups, cur = ([], None)
    for x in body:
        if x[0] & 65535 in (OP_CONTROL_BARRIER, OP_MEMORY_BARRIER):
            if cur is None:
                cur = []
                groups.append(cur)
            cur.append(list(x))
        else:
            cur = None
    if len(groups) != 2 or groups[0] != groups[1]:
        return None
    imports = {x[1] for x in m.ins if x[0] & 65535 == OP_EXT_INST_IMPORT and string_at(x, 2)[0] == 'GLSL.std.450'}
    if sum(x[0] & 65535 == OP_EXT_INST and x[3] in imports and x[4] == GLSL_FMA for x in body) != 64:
        return None
    return {'fid': fid, 'i32': i32, 'u32': u32, 'scratch': scratch, 'barrier': groups[0]}

def hmma_lds(m, keep=None, *, split_rows=False):
    """Lower the recognized f16 HMMA helper into vector shared-memory gathers.
Keep at most two converted A/B tiles between calls, preserving FMA order and half rounding.
Other functions and global-memory helpers are unchanged. The diagnostic split
layout uses the translator's 256-word scratch block per logical warp."""
    h = hmma_helper(m)
    if h is None:
        return 0
    if keep is None:
        keep = HMMA_KEEP
    fid, i32, u32, scratch = (h['fid'], h['i32'], h['u32'], h['scratch'])
    n = m.consts[m.types[m.pointee(m.vars[scratch][0])[1]][3]][1][0]
    if split_rows and (n < 256 or n % 256):
        return 0
    glsl = ensure_glsl(m)
    f32 = m.add_type(OP_TYPE_FLOAT, 32)
    v2f = m.add_type(OP_TYPE_VECTOR, f32, 2)
    uv4 = m.add_type(OP_TYPE_VECTOR, u32, 4)
    arr4 = m.add_type(OP_TYPE_ARRAY, uv4, m.add_const(u32, n // 4))
    p_arr4 = m.add_type(OP_TYPE_POINTER, SC_WORKGROUP, arr4)
    p_uv4 = m.add_type(OP_TYPE_POINTER, SC_WORKGROUP, uv4)
    p_u = m.add_type(OP_TYPE_POINTER, SC_WORKGROUP, u32)
    k = next((k for k, x in enumerate(m.ins) if x[0] & 65535 == OP_VARIABLE and x[2] == scratch))
    x = m.ins.pop(k)
    x[1] = p_arr4
    m._insert_decl(x)
    CI = {v: m.add_const(i32, v) for v in (1, 2, 3, 8, 32)}
    if split_rows:
        CI[5] = m.add_const(i32, 5)
        CI[16] = m.add_const(i32, 16)
    CU = {v: m.add_const(u32, v) for v in (0, 1)}
    m.index()
    calls = 0

    def tile_keys(x, V):
        key = [V.key_of_var(p) for p in x[4:14]]
        return (('A', *key[:6]), ('B', *key[:2], *key[6:8]))
    for f in [x[2] for x in m.ins if x[0] & 65535 == OP_FUNCTION and x[2] != fid]:
        a, e = m.function_range(f)
        seq = []
        V = BlockValues(m)
        for x in m.ins[a:e + 1]:
            if x[0] & 65535 == OP_FUNCTION_CALL and x[3] == fid:
                seq.append(tile_keys(x, V))
                V.see([3 << 16 | OP_STORE, x[14], ('d1', len(seq))])
            else:
                V.see(x)
        uses = {}
        for i, ks in enumerate(seq):
            for q in ks:
                uses.setdefault(q, []).append(i)
        out = []
        V = BlockValues(m)
        cache = {}
        ci = 0

        def em(op, ty, *ops, output=out):
            r = m.new_id()
            output.append([3 + len(ops) << 16 | op, ty, r, *ops])
            return r

        def integer(op, p, q):
            return em(op, i32, p, q)

        def cvt(w):
            u = [em(OP_EXT_INST, v2f, glsl, GLSL_UNPACK_HALF_2X16, x) for x in w]
            return [(em(OP_COMPOSITE_EXTRACT, f32, v, 0), em(OP_COMPOSITE_EXTRACT, f32, v, 1)) for v in u]

        def next_use(q, i, uses=uses):
            return next((j for j in uses[q] if j > i), None)
        for x in m.ins[a:e + 1]:
            op = x[0] & 65535
            if op == OP_LABEL:
                cache = {}
            if not (op == OP_FUNCTION_CALL and x[3] == fid):
                V.see(x)
                out.append(x)
                continue
            args = x[4:15]
            kA, kB = seq[ci]
            need = [q for q in (kA, kB) if q not in cache]
            if need:
                lane, bse = (em(OP_LOAD, i32, args[0]), em(OP_LOAD, i32, args[1]))
                g = integer(OP_SHR_LOGICAL, lane, CI[2])
                t = integer(OP_BITWISE_AND, lane, CI[3])
                b4 = integer(OP_SHR_LOGICAL, bse, CI[2])
                vi = integer(OP_SHR_LOGICAL, t, CI[1])
                c0 = em(OP_BITCAST, u32, integer(OP_SHL_LOGICAL, integer(OP_BITWISE_AND, t, CI[1]), CI[1]))
                c1 = em(OP_IADD, u32, c0, CU[1])
                # Each logical warp owns 64 vectors. Store its 24 rows in
                # separate 32-vector planes, one plane for each half of a row.
                if split_rows:
                    rowA = lambda r, base=b4: integer(OP_IADD, base, r)
                    rowB = lambda r, row=rowA: row(integer(OP_IADD, r, CI[16]))
                    vi = integer(OP_SHL_LOGICAL, vi, CI[5])
                else:
                    rowA = lambda r, base=b4: integer(OP_IADD, base, integer(OP_SHL_LOGICAL, r, CI[1]))
                    rowB = lambda c, base=b4: integer(OP_IADD, base, integer(OP_IADD, CI[32], integer(OP_SHL_LOGICAL, c, CI[1])))

                def st(row, w0, w1, vector=vi, component0=c0, component1=c1, output=out):
                    v4 = integer(OP_IADD, row, vector)
                    for c, w in ((component0, w0), (component1, w1)):
                        output.append([3 << 16 | OP_STORE, em(OP_ACCESS_CHAIN, p_u, scratch, v4, c), em(OP_BITCAST, u32, w)])
                g8 = integer(OP_IADD, g, CI[8])
                if kA in need:
                    st(rowA(g), em(OP_LOAD, i32, args[2]), em(OP_LOAD, i32, args[4]))
                    st(rowA(g8), em(OP_LOAD, i32, args[3]), em(OP_LOAD, i32, args[5]))
                if kB in need:
                    st(rowB(g), em(OP_LOAD, i32, args[6]), em(OP_LOAD, i32, args[7]))
                out.extend((list(b) for b in h['barrier']))

                def ld_row(r0):
                    w = []
                    for p in range(2):
                        offset = CI[32 if split_rows else 1]
                        v4 = em(OP_LOAD, uv4, em(OP_ACCESS_CHAIN, p_uv4, scratch, integer(OP_IADD, r0, offset) if p else r0))
                        w += [em(OP_COMPOSITE_EXTRACT, u32, v4, c) for c in range(4)]
                    return cvt([w[2 * (kw % 4) + kw // 4] for kw in range(8)])
                if kA in need:
                    cache[kA] = [ld_row(rowA(g)), ld_row(rowA(g8))]
                if kB in need:
                    t2 = integer(OP_SHL_LOGICAL, t, CI[1])
                    cache[kB] = [ld_row(rowB(t2)), ld_row(rowB(integer(OP_IADD, t2, CI[1])))]
                out.extend((list(b) for b in h['barrier']))
            A, B = (cache[kA], cache[kB])
            d = []
            for q in range(2):
                cv = em(OP_EXT_INST, v2f, glsl, GLSL_UNPACK_HALF_2X16, em(OP_BITCAST, u32, em(OP_LOAD, i32, args[8 + q])))
                acc = [em(OP_COMPOSITE_EXTRACT, f32, cv, 0), em(OP_COMPOSITE_EXTRACT, f32, cv, 1)]
                for j in range(2):
                    for kw in range(8):
                        for hh in range(2):
                            acc[j] = em(OP_EXT_INST, f32, glsl, GLSL_FMA, A[q][kw][hh], B[j][kw][hh], acc[j])
                d.append(em(OP_BITCAST, i32, em(OP_EXT_INST, u32, glsl, GLSL_PACK_HALF_2X16, em(OP_COMPOSITE_CONSTRUCT, v2f, *acc))))
            st_out = [3 << 16 | OP_STORE, args[10], d[1]]
            out.append(st_out)
            V.see(st_out)
            out.append([4 << 16 | OP_COPY_OBJECT, i32, x[2], d[0]])
            nu = {q: next_use(q, ci) for q in cache}
            cache = {q: v for q, v in cache.items() if nu[q] is not None and q in sorted((q for q in nu if nu[q] is not None), key=nu.get)[:keep]}
            calls += 1
            ci += 1
        m.ins[a:e + 1] = out
    a, e = m.function_range(fid)
    gone = {y[2] for y in m.ins[a:e + 1] if len(y) > 2 and y[0] & 65535 not in NO_RESULT_OPS} | {y[1] for y in m.ins[a:e + 1] if y[0] & 65535 == OP_LABEL}
    del m.ins[a:e + 1]
    m.ins = [y for y in m.ins if not (y[0] & 65535 in (OP_NAME, OP_DECORATE) and y[1] in gone)]
    m.index()
    return calls

def lower(binary, keep=2, *, split_rows=False):
    """Return (SPIR-V, calls lowered); unsupported helper shapes stay byte-identical."""
    if keep not in (0, 1, 2):
        raise ValueError('HMMA cache limit must be 0, 1 or 2')
    module = Module(binary)
    if not module.entry or module.entry[1] != 5:
        return binary, 0
    calls = hmma_lds(module, keep, split_rows=split_rows)
    return (module.data(), calls) if calls else (binary, 0)
