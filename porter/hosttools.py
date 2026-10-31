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


ADB_Z_MAJOR = 30
ADB_MIN_PROTOCOL = 39


def adb_version(exe): return None   # stub (RED)
def push_flags(exe): return ['-Z']   # stub (RED)
def linux_arm64(): return False   # stub (RED)
def source_of(path, cfg, key, sdk_roots=()): return ''   # stub (RED)
