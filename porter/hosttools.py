# The places a GUI started from Finder or a desktop menu cannot see through PATH (D-16), where a found tool came from (D-13), dotnet's real root (RESEARCH Pitfall 4)
# and adb's version (D-12). The known places are searched on every lookup and never saved; no login-shell PATH and no shell startup file is ever read.
import os, platform, re, shutil, subprocess, sys
from pathlib import Path

from porter.paths import LOCAL_TOOLS, player_tools   # not toolchain: toolchain imports this module


def known(name):
    """The absolute paths a tool may have outside a bare PATH, existing or not, in their fixed order (RESEARCH Pattern 3). None on Windows: an Explorer launch keeps the user's PATH"""
    if os.name == 'nt': return []
    home = str(Path.home() / '.dotnet')
    dirs = ['/opt/homebrew/bin', '/usr/local/bin', home, '/usr/local/share/dotnet'] if sys.platform == 'darwin' else \
           ['/usr/bin', '/usr/local/bin', '/snap/bin', home, '/usr/lib/dotnet', '/usr/lib64/dotnet', '/usr/share/dotnet']   # Ubuntu's dotnet package, Fedora's, the tarball's
    return [f'{d}/{name}' for d in dirs]


def dotnet_root(dotnet):
    """The folder dotnet's runtime and SDKs are in: the one above the `[.../sdk]` path `dotnet --list-sdks` prints, else the resolved executable's folder.
    Homebrew's /opt/homebrew/bin/dotnet, Ubuntu's /usr/bin/dotnet and snap's /snap/bin/dotnet are links: their own folder as DOTNET_ROOT breaks nx_extract's apphost (Pitfall 4)"""
    try: r = subprocess.run([str(dotnet), '--list-sdks'], capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired): r = None
    m = r and re.search(r'\[(.+)\]\s*$', r.stdout, re.M)
    return Path(m.group(1)).parent if m else Path(dotnet).resolve().parent


ADB_Z_MAJOR = 30   # platform-tools 30.0.0 added push compression (RESEARCH Pitfall 6): an older adb never compresses, so pushing without -Z is the same on the wire (D-12)
ADB_MIN_PROTOCOL = 39   # every adb feature porter uses predates protocol 1.0.39 (RESEARCH A2)


def adb_version(exe):
    """`adb version` as {'version', 'major', 'protocol'} (the major and protocol as numbers, a Debian epoch ignored; an unread part is None); None when adb does not run"""
    try: r = subprocess.run([str(exe), 'version'], capture_output=True, text=True, errors='replace', timeout=15)
    except (OSError, subprocess.TimeoutExpired): return None
    v = re.search(r'^Version\s+((?:\d+:)?(\d+)\.\d+\.\d+\S*)', r.stdout, re.M); p = re.search(r'version 1\.0\.(\d+)', r.stdout)
    return {'version': v and v.group(1), 'major': v and int(v.group(2)), 'protocol': p and int(p.group(1))}


def push_flags(exe):   # -Z unless the adb is known to be older than push compression: an unread version keeps today's -Z, which protects adbd on new adbs
    major = (adb_version(exe) or {}).get('major')
    return [] if major is not None and major < ADB_Z_MAJOR else ['-Z']


def linux_arm64(): return sys.platform.startswith('linux') and platform.machine().lower() in ('aarch64', 'arm64')


def source_of(path, cfg, key, sdk_roots=()):
    """Where a found tool came from (D-13). 'downloaded' first: a downloaded tool the settings point at still reads as downloaded (RESEARCH Open Question 3)"""
    p = Path(path)
    if p.is_relative_to(player_tools()): return 'downloaded'
    if cfg.get(key) and p == Path(cfg[key]): return 'configured'
    if any(os.environ.get(k) and p.is_relative_to(os.environ[k]) for k in ('DOTNET_ROOT', 'ANDROID_NDK_HOME', 'ANDROID_NDK_ROOT')): return 'env'
    w = shutil.which(p.name)
    if w and p == Path(w): return 'PATH'
    if str(p) in known(p.name): return 'known place'
    if any(p.is_relative_to(r) for r in sdk_roots): return 'Android SDK'
    return 'known place'   # LOCAL_TOOLS, and find_dotnet's other fixed folders (Program Files, ~/.dotnet on Windows)
