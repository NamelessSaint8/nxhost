# The bring-up flywheel's read step, as one command (M3 task 2 of docs/UNIVERSAL_SUPPORT_PLAN.md): `porter triage` boots a built game on a device
# N times, reads each log, and prints what happened -- crash sites as module+offset, die()/abort messages decoded from the registers they are spelled
# in, the markers reached, the heap line, the RED lines -- as a histogram across runs. A timing-dependent crash (two sites under DM_NVN_LOG) shows as
# two outcomes with counts; a deterministic one as one outcome. The classifier names the known classes (the failure catalogue's job grows here).
import os, re, subprocess, sys, tempfile, time
from collections import Counter
from pathlib import Path

from porter import childenv, config, toolchain, paths
from porter.upstream import BuildError, PROG, nsp


def _game_of(work, title_id):
    sys.path.insert(0, str(paths.NXNATIVE / 'dm/games'))
    import game as gamemod
    for cand in (work / 'profile' / title_id, work / f'{title_id}_survey' / 'provisional' / title_id):
        if (cand / 'game.tsv').is_file(): return gamemod.Game(cand)
    raise BuildError(f'no profile under {work}: run a port first (triage boots what a port built)')


def _decode_message(log):
    # die()/assert messages are spelled in the crash dump's register rows (x4-x7, x12-x15 little-endian ASCII): pull them out as text
    out = []
    for line in log.splitlines():
        m = re.match(r'\[dm\] \*x(\d+): (.*)', line)
        if not m: continue
        for v in m.group(2).split():
            if not re.fullmatch(r'0x[0-9a-f]{16}', v): continue
            n = int(v, 16)
            s = bytes.fromhex(f'{n:016x}')[::-1]
            if all(9 <= c < 127 for c in s) and sum(65 <= c <= 122 or c == 32 for c in s) >= 5: out.append(s.decode())
    return (' '.join(out) if out else '')


def _outcome(text):
    hits = []
    for pat in ('>>> nnMain', '[mem] heap ', 'FATAL ', '[RED]', 'CRASH sig', 'tool boot:'):
        for line in [l for l in text.splitlines() if pat in l]:
            hits.append(line.replace('[dm] ', '', 1)[:150])
    crash = next((l for l in hits if l.startswith('CRASH')), None)
    parts = []
    if crash: parts.append('crash ' + crash)
    if not any('>>> nnMain' in h for h in hits): parts.insert(0, 'never reached nnMain')
    else: parts.append('reached nnMain')
    heap = next((h for h in hits if '[mem] heap' in h), None)
    if heap: parts.append(heap)
    fatal = next((h for h in hits if h.startswith('FATAL')), None)
    msg = _decode_message(text)
    if fatal or msg: parts.append('message: ' + (fatal or '')[:80] + ' | ' + msg[:120])
    reds = [h for h in hits if '[RED]' in h]
    if reds: parts.append(f'{len(reds)} [RED] lines (first: {reds[0][:90]})')
    if not crash: parts.append('no crash (timed exit or clean return)')
    return '; '.join(parts), (re.sub(r'sp=0x[0-9a-f]+', '', crash) if crash else fatal or 'no crash')   # the histogram key: the site, not the stack address


def triage(folder, device='', runs=3, secs=45, title_id=''):
    folder = Path(folder)
    build = next(iter(sorted(folder.glob('*_build'))), None)
    if not build: raise BuildError(f'no <title ID>_build under {folder}: run a port first')
    title_id = title_id or build.name[:16]
    g = _game_of(build.parent if (build.parent / 'profile').is_dir() else folder, title_id) if False else _game_of(build, title_id)
    vers = sorted(p.name[1:] for p in (build / 'extract').glob('v*') if p.is_dir())
    ver = 'v' + vers[-1] if vers else None
    if not ver: raise BuildError(f'no extraction under {build}: run a port first')
    patched = build / 'android' / f'patched_{ver}'
    if not patched.is_dir(): raise BuildError(f'no Android rewrite under {build} (patched_{ver})')
    cfg = config.load()
    tools = toolchain.require(cfg, str(cfg.get('keys') or ''), adb=True)
    env = childenv.dotnet(tools['dotnet'], 8)
    env.update(DM_TOOL_DEVICE=device or 'any', ANDROID_NDK_HOME=str(tools['ndk']), PATH=os.pathsep.join([str(Path(tools['adb']).parent), env.get('PATH', '')]))
    env.update(DM_TOOL_ROMFS=str(nsp.rfs.source(build / 'extract' / ver)), DM_NVN_SHMAP=str(g.table('shader_map.tsv')),
               DM_VK_SHADERS=str(build / 'android' / 'shaders.dmsv'))
    logs = build / 'logs'; logs.mkdir(exist_ok=True)
    PROG.say(f'triaging {g.id} ({ver}) on {device or "the first attached device"}: {runs} boot(s) of {secs} s')
    out, hist = [], Counter()
    for i in range(runs):
        log = logs / f'triage_{i}.log'
        t0 = time.time()
        rc = nsp.boot_android(paths.NXNATIVE, build / 'extract' / ver, patched, build, env, logs, g, secs, lambda: False, log)
        text = log.read_text(errors='replace')
        one, key = _outcome(text)
        hist[key] += 1
        out.append((i, rc, one, log))
        PROG.say(f'run {i + 1}/{runs} ({time.time() - t0:.0f} s, rc {rc}): {one[:170]}')
    PROG.say(f'--- outcomes over {runs} run(s):')
    for key, n in hist.items(): PROG.say(f'  {n}/{runs}: {key[:170]}')
    return {'runs': runs, 'outcomes': [{'n': i + 1, 'rc': rc, 'what': one, 'log': str(log)} for i, rc, one, log in out],
            'histogram': {k: v for k, v in hist.items()}}
