# porter/distro.py: the Linux distribution family from /etc/os-release (ID, then ID_LIKE) and the exact adb install command the fix text shows (D-25).
# Standard library only; os-release is passed in or stood in, so it runs the same on every host.
import os, sys, tempfile, unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
os.environ['NX2A_HOME'] = tempfile.mkdtemp()

from porter import distro   # noqa: E402


class Family(unittest.TestCase):
    def test_ids(self):
        for osr, want in (({'ID': 'ubuntu'}, 'debian'), ({'ID': 'linuxmint', 'ID_LIKE': 'ubuntu debian'}, 'debian'), ({'ID': 'raspbian', 'ID_LIKE': 'debian'}, 'debian'),
                          ({'ID': 'fedora'}, 'fedora'), ({'ID': 'manjaro', 'ID_LIKE': 'arch'}, 'arch'), ({'ID': 'opensuse-tumbleweed', 'ID_LIKE': 'opensuse suse'}, None), ({}, None)):
            with self.subTest(osr): self.assertEqual(distro.family(osr), want)

    def test_no_os_release(self):   # neither /etc/os-release nor /usr/lib/os-release
        with mock.patch.object(distro.platform, 'freedesktop_os_release', side_effect=OSError('no os-release')): self.assertIsNone(distro.family())
        with mock.patch.object(distro.platform, 'freedesktop_os_release', return_value={'ID': 'fedora'}): self.assertEqual(distro.family(), 'fedora')

    def test_runs_nothing(self):   # it shows commands, never runs them
        self.assertNotIn('subprocess', (REPO / 'porter' / 'distro.py').read_text(encoding='utf-8'))


class AdbCommand(unittest.TestCase):
    def test_commands(self):
        for osr, cmd in (({'ID': 'debian'}, 'sudo apt install adb'), ({'ID': 'fedora'}, 'sudo dnf install android-tools'), ({'ID': 'arch'}, 'sudo pacman -S android-tools'), ({'ID': 'gentoo'}, '')):
            with self.subTest(osr): self.assertEqual(distro.adb_install(osr), cmd)

    def test_hint(self):
        with mock.patch.object(distro.hosttools, 'linux_arm64', return_value=True):
            with mock.patch.object(distro.platform, 'freedesktop_os_release', return_value={'ID': 'ubuntu'}): self.assertEqual(distro.adb_hint(), 'Run sudo apt install adb, then press Re-check.')
            with mock.patch.object(distro.platform, 'freedesktop_os_release', side_effect=OSError):
                h = distro.adb_hint()
                for cmd in distro.ADB.values(): self.assertIn(cmd, h)
                self.assertEqual(len(distro.ADB), 3); self.assertTrue(h.endswith('then press Re-check.'))
        with mock.patch.object(distro.hosttools, 'linux_arm64', return_value=False): self.assertEqual(distro.adb_hint(), 'Download missing tools, or install Android platform-tools')


class DeviceFix(unittest.TestCase):   # DEV-01 / D-14: one line per adb state, the udev package by distribution for `no permissions`
    NOPERM = 'no permissions (missing udev rules? user is in the plugdev group); see [http://developer.android.com/tools/device.html]'
    NOGROUP = 'no permissions (user bob is not in the plugdev group); see [http://developer.android.com/tools/device.html]'

    def test_fixes(self):
        for st, want in (('unauthorized', 'Unlock the device and tap Allow on the USB debugging prompt.'),
                         ('offline', 'Unplug the cable and plug it in again, or try another cable or USB port.'),
                         ('authorizing', 'Wait a moment.'), ('connecting', 'Wait a moment.'), ('device', ''), ('sideload', ''), ('', '')):
            with self.subTest(st): self.assertEqual(distro.device_fix(st, {}), want)

    def test_no_permissions_per_distro(self):
        self.assertEqual(distro.device_fix(self.NOPERM, {'ID': 'ubuntu'}),
                         'Run sudo apt install android-sdk-platform-tools-common, then unplug the device and plug it in again.')
        self.assertIn('sudo dnf install android-tools', distro.device_fix(self.NOPERM, {'ID': 'fedora'}))
        self.assertIn('sudo pacman -S android-udev', distro.device_fix(self.NOPERM, {'ID': 'arch'}))
        g = distro.device_fix(self.NOPERM, {'ID': 'gentoo'})
        for cmd in ('sudo apt install android-sdk-platform-tools-common', 'sudo dnf install android-tools', 'sudo pacman -S android-udev'): self.assertIn(cmd, g)
        for osr in ({'ID': 'gentoo'}, {'ID': 'ubuntu'}): self.assertNotIn('plugdev', distro.device_fix(self.NOPERM, osr))
        f = distro.device_fix(self.NOGROUP, {'ID': 'ubuntu'})
        self.assertIn('sudo usermod -aG plugdev $USER', f); self.assertIn('log out', f); self.assertNotIn('bob', f)

    def test_kind(self):
        for st, want in ((self.NOPERM, 'no permissions'), (self.NOGROUP, 'no permissions'), ('unauthorized', 'unauthorized'), ('device', 'device'), ('offline', 'offline')):
            with self.subTest(st): self.assertEqual(distro.state_kind(st), want)


if __name__ == '__main__':
    unittest.main()
