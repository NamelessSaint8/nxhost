# porter/desktop.py: the Linux bundle's app menu entry (D-20). Pinned here: Exec quoted per the Desktop Entry spec (T-03-03), the entry and icon written
# through a temp file and rewritten by a second run, a symlinked target refused (T-03-04), and nothing written unless `desktop-entry --install` runs in the bundle.
import json, os, subprocess, sys, tempfile, unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
os.environ['NX2A_HOME'] = tempfile.mkdtemp()

from porter import desktop   # noqa: E402


def lines(text): return dict(ln.split('=', 1) for ln in text.splitlines() if '=' in ln)


def porter(*args, data):
    e = dict(os.environ, NX2A_HOME=tempfile.mkdtemp(), XDG_DATA_HOME=str(data), PYTHONIOENCODING='utf-8'); e.pop('NX2A_GUI', None)
    return subprocess.run([sys.executable, '-m', 'porter', *args], cwd=REPO, env=e, capture_output=True, text=True, encoding='utf-8', timeout=120)


class Entry(unittest.TestCase):
    def setUp(self):
        self.data, self.home = Path(tempfile.mkdtemp()), Path(tempfile.mkdtemp())
        env = mock.patch.dict(os.environ, XDG_DATA_HOME=str(self.data), NX2A_HOME=str(self.home)); env.start(); self.addCleanup(env.stop)

    def test_quoting(self):
        exe = '/opt/my apps/nx"2a$`x\\%/nx2android'   # a str, so Windows keeps the separators as written
        e = lines(desktop.entry(exe, '/u/nx2android.svg'))
        self.assertIn('Exec', e)
        # quote level: \" \$ \` \\ inside double quotes; string level: each \ doubled again (a literal \ is four); % is %%
        self.assertEqual(e['Exec'], r'"/opt/my apps/nx\\"2a\\$\\`x\\\\%%/nx2android"')
        self.assertEqual((e['TryExec'], e['Icon'], e['Terminal'], e['Categories'], e['Type']), (exe, '/u/nx2android.svg', 'false', 'Game;Utility;', 'Application'))
        self.assertTrue(desktop.entry(exe, 'i').startswith('[Desktop Entry]\n'))
        with self.assertRaises(desktop.DesktopError): desktop.entry('/opt/a\nExec=evil', 'i')   # a line break would add keys of its own

    def test_install_writes_both(self):
        r = desktop.install(Path('/opt/a/nx2android'))
        d = self.data / 'applications/nx2android.desktop'; icon = self.home / 'nx2android.svg'
        self.assertEqual((r['path'], r['icon']), (str(d), str(icon)))
        self.assertTrue(icon.read_text(encoding='utf-8').lstrip().startswith('<svg'))
        self.assertEqual(lines(d.read_text(encoding='utf-8'))['Icon'], str(icon))
        desktop.install(Path('/opt/b/nx2android'))   # the bundle moved: the entry follows it
        self.assertEqual(lines(d.read_text(encoding='utf-8'))['Exec'], '"/opt/b/nx2android"')
        self.assertEqual(sorted(p.name for p in d.parent.iterdir()), ['nx2android.desktop'])   # no .tmp left behind

    @unittest.skipIf(os.name == 'nt', 'symlinks need privileges on Windows')
    def test_symlink_refused(self):
        apps = self.data / 'applications'; apps.mkdir(); other = self.data / 'other'; other.write_text('orig')
        (apps / 'nx2android.desktop').symlink_to(other)
        with self.assertRaises(desktop.DesktopError): desktop.install(Path('/opt/a/nx2android'))
        self.assertEqual(other.read_text(), 'orig')
        (apps / 'nx2android.desktop').unlink(); apps.rmdir(); real = self.data / 'real'; real.mkdir(); apps.symlink_to(real, target_is_directory=True)
        with self.assertRaises(desktop.DesktopError): desktop.install(Path('/opt/a/nx2android'))
        self.assertEqual(list(real.iterdir()), [])

    def test_cli_refuses_outside_bundle(self):
        r = porter('desktop-entry', '--install', '--json', data=self.data)
        self.assertNotIn('Traceback', r.stderr); self.assertEqual(r.returncode, 1, r.stderr)
        self.assertIn('Linux bundle', json.loads(r.stdout)['error']); self.assertEqual(list(self.data.iterdir()), [])

    def test_setup_writes_nothing(self):
        r = porter('setup', '--json', data=self.data)
        self.assertNotIn('Traceback', r.stderr); self.assertIn('ready', json.loads(r.stdout))
        self.assertEqual(list(self.data.iterdir()), [])


if __name__ == '__main__': unittest.main()
