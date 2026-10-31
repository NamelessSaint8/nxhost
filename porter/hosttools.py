# The places a GUI started from Finder or a desktop menu cannot see through PATH (D-16), where a found tool came from (D-13), dotnet's real root (RESEARCH Pitfall 4)
# and adb's version (D-12). The known places are searched on every lookup and never saved; no login-shell PATH and no shell startup file is ever read.
import os, platform, re, shutil, subprocess, sys
from pathlib import Path

from porter.paths import LOCAL_TOOLS, player_tools   # not toolchain: toolchain imports this module


def known(name):   # stub (RED)
    return []
