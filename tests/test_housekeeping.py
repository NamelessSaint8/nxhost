# Repository records and checks that need no engine modules: the commit-hook bootstrap, ignored editor files,
# the versions of vendored third-party code, and the upstream output porter parses. Standard library only, so it runs without lz4.
import shutil, subprocess, sys, tempfile, unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


class Hooks(unittest.TestCase):
    def test_sets_hooks_path_idempotently(self):
        with tempfile.TemporaryDirectory() as d:
            subprocess.run(['git', 'init', '-q', d], check=True)
            (Path(d) / 'devtools').mkdir()
            shutil.copy2(REPO / 'devtools' / 'hooks.py', Path(d) / 'devtools' / 'hooks.py')
            for _ in range(2):
                r = subprocess.run([sys.executable, str(Path(d) / 'devtools' / 'hooks.py')], capture_output=True, text=True)
                self.assertEqual(r.returncode, 0, r.stderr)
            got = subprocess.run(['git', '-C', d, 'config', 'core.hooksPath'], capture_output=True, text=True).stdout.strip()
            self.assertEqual(got, '.githooks')

    def test_readme_points_at_script(self):
        self.assertIn('devtools/hooks.py', (REPO / 'README.md').read_text(encoding='utf-8'))

    def test_workspace_ignored(self):
        r = subprocess.run(['git', 'check-ignore', '-q', 'nx2android.code-workspace'], cwd=REPO)
        self.assertEqual(r.returncode, 0)


if __name__ == '__main__':
    unittest.main()
