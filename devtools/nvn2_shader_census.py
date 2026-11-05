# A Switch 2 (NVN2) shader census of a game folder, before any host work: every BNSH program the game files hold (the .bfsha archives under RomFS/Shader),
# its stage, its instruction count and its Ampere opcode histogram — and, with --xlate, whether the offline translator (dmsh_xlate, arch sm86) already
# accepts each unique program. That pass/fail count is the number a port's shader work starts from: a failure names an instruction the translator cannot
# decode or emit yet ("unsupported native opcode"), not a container the split cannot read.
#   python devtools/nvn2_shader_census.py "/Volumes/Data/Switch/Mario Kart World" [--xlate <translator>] [--json out.json] [--any]
# The files are the ones the engine's own reader looks in: Nintendo's containers that carry a BNSH by name (.bfsha, .bfres, .esetb, .blarc, .bnsh,
# .ptcl, .sarc) plus main, read through shader_split's scan_blob, so every BNSH in a file is found, SARC members and all. --any reads every file of the
# folder instead, which is slow on a 20 GB RomFS. Files named after shaders alone are not enough: Mario Kart World keeps 198 of its 1,018 compute
# programs, and 3,938 graphics ones, in Effect/static.Nin_Ounce_NVN2.esetb.byml.zs.
# Ampere instructions are 16 bytes and their opcode is the low 12 bits of the low word
# (AmpereOp.Opcode); a graphics code area holds the 0x80-byte SPH in front of them, a compute one does not. Both facts are the engine's: see
# dm/gfx/tools/dmsh_ampere.py and dm/third_party/ryujinx/.../Decoders/AmpereOp.cs.
import argparse, collections, json, os, re, struct, subprocess, sys, tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
TOOLS = REPO / 'nxnative/dm/gfx/tools'
sys.path.insert(0, str(TOOLS))
# shader_split loads a game profile at import for its grouping and key rules; the BNSH reader used here reads none of them, and DM_GAME already set wins
os.environ.setdefault('DM_GAME', '0100152000022000')
import shader_split as S   # noqa: E402  (the BNSH / NVN2 readers: one source of truth with the port)
import dmsh_ampere   # noqa: E402

ZSTD_MAGIC = b'\x28\xb5\x2f\xfd'
SPH = 0x80           # a graphics code area's SPH, in front of the instructions
NAMES_CS = REPO / 'nxnative/dm/third_party/ryujinx/src/Ryujinx.Graphics.Shader/Instructions/InstEmitAmpere.cs'
CARRIERS = ('.bfsha', '.bfres', '.esetb', '.blarc', '.bnsh', '.ptcl', '.sarc')   # Nintendo's containers a BNSH hides in (dm/gfx/tools/shader_split.py)


def candidates(folder, any_file):
    """The files that may hold a BNSH: those of a container that carries one, or every file of the folder with --any. Matched anywhere in the name, not at
    its end: Mario Kart World's effect set is static.Nin_Ounce_NVN2.esetb.byml.zs, which neither .esetb nor .zs ends"""
    for dp, _, fs in os.walk(folder):
        for f in fs:
            p = Path(dp, f); n = f.lower()
            if any_file or n == 'main' or any(c in n for c in CARRIERS): yield p


def blobs(folder, any_file):
    """(label, bytes) of each candidate, a zstd frame decompressed first (compression.zstd, 3.14+, or its backport)"""
    for p in candidates(folder, any_file):
        try: raw = p.read_bytes()
        except OSError as e: print(f'[skip] {p}: {e}', file=sys.stderr); continue
        if raw[:4] == ZSTD_MAGIC:
            try: raw = S.zstd_mod().decompress(raw)   # the module's own call (shader_split 415): a frame whose size it cannot learn is refused, not guessed
            except Exception as e: print(f'[skip] {p}: zstd: {e}', file=sys.stderr); continue
        if b'BNSH' in raw: yield str(p.relative_to(folder)), raw


def programs(folder, any_file):
    """(found programs, archives read, [(label, reason) of archives the reader refused]) — one entry per stage of every variation"""
    out, n, bad = [], 0, []
    for label, raw in blobs(folder, any_file):
        got = []
        try: S.scan_blob(raw, label, got)   # the engine's own reader: every BNSH in the file, SARC members included
        except SystemExit as e:   # red(): a damaged archive, or a layout this reader does not know: reported, not fatal
            bad.append((label, str(e).replace('[RED] ', '', 1))); continue
        if not got: continue   # a container that holds no shader (a model archive)
        n += 1
        for where, st, ctl, code in got: out.append(dict(key=S.skey(ctl, code), stage=st, ctl=ctl, code=code, where=where))
    return out, n, bad


def inst_span(p):
    """(start, bytes) of the instructions in a code area: the SPH in front of a graphics stage's, none in front of compute's, and never past the area"""
    n = min(dmsh_ampere.inst_len(p['ctl']), len(p['code']))
    start = 0 if p['stage'] == 'cs' else SPH
    return (start, n - start) if n > start else (0, 0)


def amd_hist(programs):
    """Opcode histogram over the unique programs: {opcode: (count, shaders it appears in)}"""
    hist = collections.Counter(); shaders = collections.Counter()
    for p in programs:
        start, n = inst_span(p)
        seen = set()
        for i in range(0, n - n % 16, 16):
            op = struct.unpack_from('<Q', p['code'], start + i)[0] & 0xfff
            hist[op] += 1; seen.add(op)
        shaders.update(seen)
    return hist, shaders


def opcode_names():
    """The opcodes the translator names as constants (control flow, IPA and the memory forms); every other prints as its number"""
    try: text = NAMES_CS.read_text(encoding='utf-8')
    except OSError: return {}
    return {int(v, 16): k for k, v in re.findall(r'public const int (\w+) = (0x[0-9a-fA-F]+);', text)}


def translate(programs, exe):
    """{key: (ok, message)} of the offline translator (dmsh_xlate) over the unique programs, one jobs file for all of them: the job an NVN2 program
    needs is the one dmsh_build's job_for builds (arch sm86, the c1 segment the control section delimits, and compute's c0 layout)"""
    with tempfile.TemporaryDirectory(prefix='nvn2_census_') as d:   # every code area and .spv of the run: read, then gone
        work = Path(d); jobs, out = [], work / 'out'
        for p in programs:
            cp = work / f"{p['key']}.bin"
            start, n = inst_span(p)
            cp.write_bytes(p['code'][:start + n])
            job = dict(key=p['key'], stage=p['stage'], arch='sm86', code=str(cp), tex={}, img={}, attr={}, fout={},
                       c1=dmsh_ampere.c1_segment(p['ctl'], p['code']).hex(), debug=False, reduced=True, no_facts=True)
            if p['stage'] == 'cs':
                sh = struct.unpack_from('<I', p['ctl'], 0x64)[0] if len(p['ctl']) > 0x68 else 0
                job['local'] = list(struct.unpack_from('<3I', p['ctl'], 0x58))
                job['shared'] = (sh + 15) // 16 * 16
                job['nvn2_cs'] = [p['ctl'][0xb1], p['ctl'][0xb2], p['ctl'][0xb3], struct.unpack_from('<H', p['ctl'], 0xba)[0], p['ctl'][0xa9] * 4]
            jobs.append(job)
        (work / 'jobs.json').write_text(json.dumps(jobs))
        cmd = (['dotnet', str(exe)] if str(exe).endswith('.dll') else [str(exe)]) + [str(work / 'jobs.json'), str(out)]
        r = subprocess.run(cmd, capture_output=True, text=True)
        res = {p['key']: [False, 'the translator wrote no result'] for p in programs}
        for key in res:
            spv = out / f'{key}.spv'
            if spv.exists() and spv.stat().st_size: res[key] = [True, '']
        for line in r.stderr.splitlines():
            m = re.match(r'\[RED\] (\w+): (.*)', line)
            if m and m.group(1) in res: res[m.group(1)] = [False, m.group(2)]
        if 'translated:' not in r.stdout + r.stderr: print(f'[skip] translator: {r.returncode}: {(r.stderr or r.stdout).strip()[:300]}', file=sys.stderr)
        return res


def main():
    ap = argparse.ArgumentParser(description='Census a Switch 2 game\'s NVN2 shaders.')
    ap.add_argument('folder', help='the game folder: a loose dump (romfs/, or the folder holding it)')
    ap.add_argument('--xlate', help='the offline translator (dmsh_xlate, or its .dll with dotnet); default: the built one in nxnative/dm/gfx/tools/dmsh_xlate_bin')
    ap.add_argument('--json', help='write the census here')
    ap.add_argument('--top', type=int, default=12, help='opcodes to list (default 12)')
    ap.add_argument('--any', action='store_true', help='decompress every file of the folder, not only the shader archives by name')
    a = ap.parse_args()

    found, archives, bad = programs(a.folder, a.any)
    if not found: sys.exit(f'[RED] no BNSH program under {a.folder} (is this a loose dump? --any tries every file)')
    keys = {}
    for p in found: keys.setdefault(p['key'], {**p, 'n': 0})['n'] += 1
    uniq = sorted(keys.values(), key=lambda p: (p['stage'], p['key']))
    stages = collections.Counter(p['stage'] for p in found)
    print(f'{archives} file(s) hold shaders, {len(found):,} stage programs ({", ".join(f"{v:,} {k}" for k, v in sorted(stages.items()))}), {len(uniq):,} unique')
    print(f'instructions: {sum(inst_span(p)[1] for p in uniq) // 16:,} in the unique programs (a graphics area starts after its {SPH:#x}-byte SPH)')
    for label, why in bad: print(f'[RED] {label}: {why}')

    hist, in_shaders = amd_hist(uniq)
    names = opcode_names()
    print(f'\ntop {a.top} Ampere opcodes of the unique programs (16-byte instructions; *.Lo & 0xfff):')
    print('  opcode  name        count  in shaders   (a blank name is an ALU form: bits 0..8 are the opcode, 9..11 the operand form)')
    for op, c in hist.most_common(a.top):
        print(f'  0x{op:03x}  {names.get(op, ""):10s}  {c:7,}  {in_shaders[op]:7,}')

    result = None
    exe = Path(a.xlate) if a.xlate else TOOLS / 'dmsh_xlate_bin/dmsh_xlate'
    if exe.exists() or (a.xlate and str(exe).endswith('.dll')):
        res = translate(uniq, exe)
        ok = [p for p in uniq if res[p['key']][0]]
        failed = [p for p in uniq if not res[p['key']][0]]
        print(f'\ntranslator (dmsh_xlate, arch sm86): {len(ok):,} of {len(uniq):,} unique programs translate, {len(failed):,} fail')
        by_stage = collections.Counter(p['stage'] for p in failed)
        if failed: print('  failed by stage: ' + ', '.join(f'{v:,} {k}' for k, v in sorted(by_stage.items())))
        why = collections.Counter(re.sub(r'\b[0-9a-fx]{4,}\b', '<n>', res[p['key']][1])[:120] for p in failed)
        for msg, c in why.most_common(10): print(f'  {c:5,}  {msg}')
        for p in failed[:5]: print(f'  e.g. {p["where"]} {p["stage"]}: {res[p["key"]][1][:150]}')
        result = {p['key']: res[p['key']][0] for p in uniq}
    elif a.xlate: sys.exit(f'[RED] no translator at {exe} (build it with dm/gfx/tools/dmsh_build.py, or pass --xlate)')

    if a.json:
        Path(a.json).write_text(json.dumps(dict(
            folder=str(Path(a.folder).resolve()), archives=archives, programs=dict(stages), unique=len(uniq),
            refused=[dict(archive=l, reason=w) for l, w in bad],
            opcodes={f'0x{op:03x}': dict(name=names.get(op, ''), count=c, shaders=in_shaders[op]) for op, c in hist.most_common()},
            translated=result), indent=1))
        print(f'\nwrote {a.json}')


if __name__ == '__main__': main()
