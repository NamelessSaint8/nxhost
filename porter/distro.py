# The Linux distribution, from /etc/os-release ID and ID_LIKE, for fix text that names the exact command (D-14, D-25). porter never runs these commands, it only
# shows them; the os-release values are only looked up as keys, the shown commands are porter's own.
import platform

from porter import hosttools

ADB = {'debian': 'sudo apt install adb', 'fedora': 'sudo dnf install android-tools', 'arch': 'sudo pacman -S android-tools'}
# The udev rules that let a user open the device (adb's `no permissions`): Debian's package pulls in android-udev-rules; Arch's is android-udev (RESEARCH, D-14)
UDEV = {'debian': 'sudo apt install android-sdk-platform-tools-common', 'fedora': 'sudo dnf install android-tools', 'arch': 'sudo pacman -S android-udev'}
FIXES = {'unauthorized': 'Unlock the device and tap Allow on the USB debugging prompt.', 'offline': 'Unplug the cable and plug it in again, or try another cable or USB port.',
         'authorizing': 'Wait a moment.', 'connecting': 'Wait a moment.'}


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


def state_kind(state): return 'no permissions' if state.startswith('no permissions') else state   # the no-permissions family carries its reason in adb's text


def device_fix(state, osr=None):
    """One line that fixes an adb device state ('' for a ready device or a state with no known fix). Only the state's kind and the os-release ID choose the text:
    nothing adb or the device printed is copied into it"""
    if state_kind(state) != 'no permissions': return FIXES.get(state, '')
    cmd = UDEV.get(family(osr))
    fix = f'Run {cmd}, then unplug the device and plug it in again.' if cmd else \
        'Install your distribution\'s Android udev rules (Debian/Ubuntu: {debian}; Fedora: {fedora}; Arch: {arch}), then unplug the device and plug it in again.'.format(**UDEV)
    return fix + (' Then run sudo usermod -aG plugdev $USER, and log out and in again.' if 'not in the plugdev group' in state else '')
