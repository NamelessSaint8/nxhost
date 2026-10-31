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


if __name__ == '__main__':
    unittest.main()
