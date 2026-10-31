# The compile probe every found NDK gets (D-11): clang --version, then compile and link a one-line C file for aarch64-linux-android29. It catches an NDK built for
# another CPU (Exec format error), lost exec bits and macOS quarantine before a 20-minute port does. A pass is cached by clang's path, mtime and size in
# <user dir>/probe.json; a failure is never cached, so a fixed NDK passes on the next check. No shell, a 60 s limit, run in a temp folder (never the bundle).
import errno, json, os, re, subprocess, sys, tempfile
from pathlib import Path

from porter import hosttools
from porter.paths import player_tools, user_dir

ARM_HOSTS = ('linux-arm64', 'linux-aarch64')   # an arm64 NDK's own host folder: Google ships none, the community build calls it linux-arm64
SOURCE = 'int main(void) { return 0; }'
TIMEOUT = 60   # the official r27c links it in 0.16 s on the developer's Mac; a first run from a cold disk is far slower


def host_folder(ndk):
    """The NDK's prebuilt host folder, the rule nxnative/dm/android/build.py copies (tests/test_probe.py HostFolder keeps them equal). Never a glob of prebuilt/*:
    the community tarball also holds a linux-x86_64 link to linux-arm64 (RESEARCH Pattern 6)"""
    host = 'windows-x86_64' if os.name == 'nt' else 'linux-x86_64' if sys.platform.startswith('linux') else 'darwin-x86_64'
    if hosttools.linux_arm64(): host = next((h for h in ARM_HOSTS if (Path(ndk) / 'toolchains/llvm/prebuilt' / h).is_dir()), host)
    return host


def clang(ndk): return Path(ndk) / 'toolchains/llvm/prebuilt' / host_folder(ndk) / 'bin' / ('clang.exe' if os.name == 'nt' else 'clang')


def _cache(): return user_dir() / 'probe.json'


def _load():
    try: c = json.loads(_cache().read_text(encoding='utf-8'))
    except (OSError, ValueError): return {}
    return c if isinstance(c, dict) else {}


def probe(ndk):
    """{'ok', 'detail', 'version', 'fix'}: whether this NDK's clang compiles and links an Android arm64 program on this machine"""
    c = clang(ndk)
    if not c.is_file(): return {'ok': False, 'detail': f'no clang at {c}', 'version': '', 'fix': 'use a complete NDK folder (toolchains/llvm/prebuilt/<host>/bin/clang)'}
    st = c.stat(); key = str(c.resolve()); hit = _load().get(key)
    if isinstance(hit, dict) and [hit.get('mtime'), hit.get('size')] == [st.st_mtime_ns, st.st_size]: return {'ok': True, 'detail': hit.get('detail', ''), 'version': hit.get('version', ''), 'fix': ''}
    fail = lambda d, fix='': {'ok': False, 'detail': d, 'version': '', 'fix': fix}
    try:
        r = subprocess.run([str(c), '--version'], capture_output=True, text=True, errors='replace', timeout=TIMEOUT)
        m = re.search(r'clang version (\S+)', r.stdout); version = f'clang {m.group(1)}' if m else 'clang'
        with tempfile.TemporaryDirectory() as t:
            (Path(t) / 'probe.c').write_text(SOURCE + '\n')
            r = subprocess.run([str(c), '--target=aarch64-linux-android29', '-fuse-ld=lld', 'probe.c', '-o', 'probe'], cwd=t, capture_output=True, text=True, errors='replace', timeout=TIMEOUT)
    except PermissionError:
        fix = f'chmod +x {c.parent}/*' + (f'; if it was downloaded in a browser: xattr -dr com.apple.quarantine {ndk}' if sys.platform == 'darwin' else '')
        return fail(f'cannot run {c}: not executable', fix)
    except subprocess.TimeoutExpired: return fail(f'{c} timed out after {TIMEOUT} s', 'run the check again; if it keeps timing out, use another copy of the NDK')
    except OSError as e:
        if e.errno == errno.ENOEXEC: return fail(f'cannot run {c}: Exec format error (built for another CPU)', 'use an NDK built for this computer')
        return fail(f'cannot run {c}: {e.strerror or e}', 'use another copy of the NDK')
    if r.returncode: return fail('cannot link an Android program: ' + (r.stderr.strip().splitlines() or [f'exit code {r.returncode}'])[-1], 'install NDK r27c (an unmodified copy for this computer)')
    detail = f'{version} links an Android arm64 program'
    c2 = _load(); c2[key] = {'mtime': st.st_mtime_ns, 'size': st.st_size, 'version': version, 'detail': detail}
    p = _cache(); tmp = p.with_suffix('.tmp'); tmp.write_text(json.dumps(c2, indent=1), encoding='utf-8'); tmp.replace(p)   # as config.save
    return {'ok': True, 'detail': detail, 'version': version, 'fix': ''}


def note(ndk, version):
    """'' for an NDK in a Google host folder; the community label otherwise (D-09, D-10): porter's own download of the pin names its builder"""
    if host_folder(ndk) not in ARM_HOSTS: return ''
    who = 'community r27c build (HomuHomu833)' if Path(ndk).is_relative_to(player_tools()) else 'community arm64 build'
    return f'{who}, {version}: not the build the titles were tested with'
