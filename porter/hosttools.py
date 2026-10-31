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


def dotnet_root(dotnet):   # stub (RED)
    return Path(dotnet).parent
