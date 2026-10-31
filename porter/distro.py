# The Linux distribution, from /etc/os-release ID and ID_LIKE, for fix text that names the exact command (D-14, D-25). porter never runs these commands, it only
# shows them; the os-release values are only looked up as keys, the shown commands are porter's own.
import platform

from porter import hosttools

ADB = {'debian': 'sudo apt install adb', 'fedora': 'sudo dnf install android-tools', 'arch': 'sudo pacman -S android-tools'}


def family(osr=None):
    """'debian' / 'fedora' / 'arch' / None, from ID then each ID_LIKE word (ubuntu, mint, raspbian: debian; manjaro: arch)"""
    try: osr = osr if osr is not None else platform.freedesktop_os_release()
    except OSError: return None   # neither /etc/os-release nor /usr/lib/os-release
    for i in [osr.get('ID', ''), *osr.get('ID_LIKE', '').split()]:
        i = 'debian' if i == 'ubuntu' else i
        if i in ADB: return i
    return None


def adb_install(osr=None): return ADB.get(family(osr), '')


def adb_hint():   # the adb row's fix when no adb is found: Google ships no platform-tools for Linux arm64, so there it is the distro's package
    if not hosttools.linux_arm64(): return 'Download missing tools, or install Android platform-tools'
    cmd = adb_install()
    return f'Run {cmd}, then press Re-check.' if cmd else \
        'Install adb from your distribution (Debian/Ubuntu: sudo apt install adb; Fedora: sudo dnf install android-tools; Arch: sudo pacman -S android-tools), then press Re-check.'
