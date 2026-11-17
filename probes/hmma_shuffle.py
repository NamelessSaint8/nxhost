#!/usr/bin/env python3
"""Experimental HMMA helper replacement for captured-compute and synthetic proofs.

Uses our translator's fragment layout and FMA order. No third-party source is
copied. The 8-term rounding variant is an explicitly separate numerical model;
the default retains the existing helper's final-only half rounding.
This does not change the production shader chain.
"""
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'nxnative/dm/android/tools'))
import hmma_spv

CROSS = ROOT / 'nxnative/dm/gfx/tools/spirv_cross_bin/spirv-cross'

ROUND_HALF = '''
float dm_round_half(float value) {
    uint raw = floatBitsToUint(value);
    uint magnitude = raw & 0x7fffffffu;
    if (magnitude >= 0x7f800000u) return value;
    uint sign = raw & 0x80000000u;
    if (magnitude < 0x38800000u) {
        // Half subnormals are integer multiples of 2^-24, normal in float32.
        float units = roundEven(uintBitsToFloat(magnitude) * 16777216.0);
        return uintBitsToFloat(floatBitsToUint(units * 0.000000059604644775390625) | sign);
    }
    // Round the discarded thirteen float32 mantissa bits, ties to even.
    uint carry = 0xfffu + ((magnitude >> 13u) & 1u);
    uint rounded = (magnitude + carry) & 0xffffe000u;
    if (rounded >= 0x47800000u) rounded = 0x7f800000u;
    return uintBitsToFloat(rounded | sign);
}
'''


def helper(rounding=16, unroll=False):
    if rounding not in (8, 16):
        raise ValueError('rounding must be 8 or 16')
    rounding_code = '''
        if (pair == 3u) {
            acc0 = vec2(dm_round_half(acc0.x), dm_round_half(acc0.y));
            acc1 = vec2(dm_round_half(acc1.x), dm_round_half(acc1.y));
        }
''' if rounding == 8 else ''
    return (ROUND_HALF if rounding == 8 else '') + '''
int dmsh_hmma16816_f16(int logical_lane, int scratch_base,
                      int a0, int a1, int a2, int a3,
                      int b0, int b1, int c0, int c1, out int d1) {
    uint physical = gl_SubgroupInvocationID;
    uint warp = physical & ~31u;
    uint row = physical & 28u;
    uint column = (physical & 3u) * 8u;
    precise vec2 acc0 = unpackHalf2x16(uint(c0));
    precise vec2 acc1 = unpackHalf2x16(uint(c1));
    ''' + ('[[unroll]]' if unroll else '[[dont_unroll]]') + '''
    for (uint pair = 0u; pair < 8u; ++pair) {
        uint lane_offset = pair & 3u;
        uint a_lane = warp + row + lane_offset;
        uint b_lane = warp + column + lane_offset;
        uint aw0 = uint(pair < 4u ? a0 : a2);
        uint aw1 = uint(pair < 4u ? a1 : a3);
        uint bw = uint(pair < 4u ? b0 : b1);
        vec2 ar0 = unpackHalf2x16(subgroupShuffle(aw0, a_lane));
        vec2 ar1 = unpackHalf2x16(subgroupShuffle(aw1, a_lane));
        vec2 bc0 = unpackHalf2x16(subgroupShuffle(bw, b_lane));
        vec2 bc1 = unpackHalf2x16(subgroupShuffle(bw, b_lane + 4u));
        acc0 = fma(vec2(ar0.x), vec2(bc0.x, bc1.x), acc0);
        acc0 = fma(vec2(ar0.y), vec2(bc0.y, bc1.y), acc0);
        acc1 = fma(vec2(ar1.x), vec2(bc0.x, bc1.x), acc1);
        acc1 = fma(vec2(ar1.y), vec2(bc0.y, bc1.y), acc1);
''' + rounding_code + '''
    }
    d1 = int(packHalf2x16(acc1));
    return int(packHalf2x16(acc0));
}
'''


def replace_helper(source, rounding=16, unroll=False):
    match = re.search(r'\bint dmsh_hmma16816_f16\([^;]*?\)\s*\{', source)
    if not match:
        raise ValueError('no unique translator matrix helper')
    end = match.end()
    depth = 1
    while depth:
        if end >= len(source):
            raise ValueError('unterminated matrix helper')
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    source = source[:match.start()] + helper(rounding, unroll) + source[end:]
    for extension in ('GL_KHR_shader_subgroup_basic', 'GL_KHR_shader_subgroup_shuffle', 'GL_EXT_control_flow_attributes'):
        if f'#extension {extension} :' not in source:
            source = source.replace('#version 460', f'#version 460\n#extension {extension} : require', 1)
    return source


def instrument_source(source):
    """Record both results of every actual matrix call, independent of stores.

    Only for the captured 1D kernels. Binding 31 must be supplied separately by
    the replay manifest. Timings use uninstrumented shaders instead.
    """
    calls = len(re.findall(r'\bdmsh_hmma16816_f16\(', source)) - 1
    if calls <= 0 or re.search(r'\bbinding\s*=\s*31\b', source):
        raise ValueError('no matrix calls or trace binding already used')
    source = source.replace('int dmsh_hmma16816_f16(', 'int dm_hmma_core(', 1)
    start = source.index('int dm_hmma_core(')
    end = source.index('{', start)+1
    depth = 1
    while depth:
        depth += (source[end] == '{')-(source[end] == '}')
        end += 1
    declarations = ('layout(set=0,binding=31,std430) buffer MatrixTrace { uvec2 words[]; } dm_matrix_trace;\n'
                    'uint dm_matrix_sequence=0u;\n')
    params = ', '.join('int p'+str(i) for i in range(10))+', out int p10'
    args = ','.join('p'+str(i) for i in range(11))
    wrapper = ('\nint dmsh_hmma16816_f16('+params+') {\n'
               '    int low=dm_hmma_core('+args+');\n'
               f'    dm_matrix_trace.words[gl_GlobalInvocationID.x*{calls}u+dm_matrix_sequence++]=uvec2(uint(low),uint(p10));\n'
               '    return low;\n}\n')
    return source[:start]+declarations+source[start:end]+wrapper+source[end:], calls


def compile_source(source, target, compact=True):
    target = Path(target)
    glsl = target.with_suffix('.comp')
    glsl.write_text(source)
    raw = target.with_suffix('.raw.spv')
    subprocess.run(['glslangValidator', '-V', '--target-env', 'vulkan1.2', '-Od', '-S', 'comp', str(glsl), '-o', str(raw)], check=True, capture_output=True)
    # Keep helper calls and its bounded loop. Optimize the surrounding data flow
    # without the size pass's exhaustive function inlining.
    subprocess.run(['spirv-opt', '--eliminate-local-single-block', '--eliminate-local-single-store', '--ssa-rewrite',
                    '--ccp', '--simplify-instructions', '--eliminate-dead-code-aggressive', '--eliminate-dead-variables',
                    '--eliminate-dead-functions', '--compact-ids', str(raw), '-o', str(target)], check=True, capture_output=True)
    m = hmma_spv.Module(target.read_bytes())
    functions = [fid for name, fid in hmma_spv.functions_named(m).items()
                 if name.split('(', 1)[0] == hmma_spv.HMMA_NAME]
    if len(functions) != 1:
        raise ValueError('compiler removed the named helper')
    fid = functions[0]
    start, end = m.function_range(fid)
    m.ins[start][3] = 2 if compact else 0  # FunctionControl DontInline
    target.write_bytes(m.data())
    subprocess.run(['spirv-val', '--target-env', 'vulkan1.2', str(target)], check=True, capture_output=True)
    return {'bytes': target.stat().st_size,
            'helper_instructions': end-start+1,
            'helper_calls': sum(x[0] & 65535 == 57 and x[3] == fid for x in m.ins),
            'helper_control': m.ins[start][3]}


def build(binary, output, rounding=16, unroll=False, instrument=False, original=False):
    m = hmma_spv.Module(Path(binary).read_bytes())
    if hmma_spv.hmma_helper(m) is None:
        raise ValueError('input is outside the original matrix helper contract')
    source = subprocess.check_output([str(CROSS), str(binary), '--vulkan-semantics', '--version', '460'], text=True)
    if not original:
        source = replace_helper(source, rounding, unroll)
    if instrument:
        source, calls = instrument_source(source)
    result = compile_source(source, output)
    if instrument:
        result['trace_calls'] = calls
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--rounding', type=int, choices=(8, 16), default=16)
    parser.add_argument('--unroll', action='store_true')
    parser.add_argument('--instrument', action='store_true')
    parser.add_argument('--original', action='store_true')
    args = parser.parse_args()
    print(json.dumps(build(args.input, args.output, args.rounding, args.unroll, args.instrument, args.original)))
