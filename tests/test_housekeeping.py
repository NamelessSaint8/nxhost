# Repository records and checks that need no engine modules: the commit-hook bootstrap, ignored editor files,
# the versions of vendored third-party code, and the upstream output porter parses. Standard library only, so it runs without lz4.
import ast, re, shutil, subprocess, sys, tempfile, unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TP = REPO / 'nxnative/dm/third_party'
def text(p): return (REPO / p).read_text(encoding='utf-8')


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


class Records(unittest.TestCase):
    def test_flip_version(self):
        s = (TP / 'README.md').read_text(encoding='utf-8')
        self.assertIn('b475eb4', s); self.assertIn('1.7', s)

    def test_ryujinx_patch(self):
        p = (TP / 'ryujinx/nxnative-local.patch').read_text(encoding='utf-8')
        self.assertTrue(p.startswith('diff --git'))
        paths = re.findall(r'^diff --git a/(\S+) b/(\S+)$', p, re.M)
        self.assertTrue(paths); self.assertTrue(all(a.startswith('src/') and b.startswith('src/') for a, b in paths), paths)
        self.assertIn('475615f', (TP / 'ryujinx/README.md').read_text(encoding='utf-8'))
        for f in ('README.md', 'ryujinx/README.md'): self.assertNotIn('Ryujinx 1.3.2', (TP / f).read_text(encoding='utf-8'), f)


class UpstreamOutput(unittest.TestCase):
    # porter/pipeline.py reads these lines of upstream tools: a wording change upstream must fail here, not in a player's port
    def test_shader_summary(self):
        sv, pl = text('nxnative/dm/android/tools/shader_vk.py'), text('porter/pipeline.py')
        self.assertRegex(sv, r"print\(f'\{[^}]+\} of \{[^}]+\} shaders ")
        self.assertRegex(sv, r"print\(f'translating \{[^}]+\} shaders ")
        for rx in (r'^(\d+) of (\d+) shaders', r'translating (\d+) shaders'): self.assertIn(f"r'{rx}'", pl)
        self.assertTrue(re.search(r'^(\d+) of (\d+) shaders', 'log\n5 of 7 shaders → x (1.0 MB)\n', re.M))
        self.assertTrue(re.match(r'translating (\d+) shaders', 'translating 7 shaders in 2 batches ...'))

    def test_build_sources_keys(self):
        t = ast.parse(text('nxnative/dm/games/profile_guess.py')); fn = {n.name: n for n in t.body if isinstance(n, ast.FunctionDef)}
        ret = [n.value for n in ast.walk(fn['build_sources']) if isinstance(n, ast.Return)]
        self.assertTrue(any(isinstance(v, ast.Call) and getattr(v.func, 'id', '') == 'shader_sources' for v in ret))
        keys = {k.value for n in ast.walk(fn['shader_sources']) if isinstance(n, ast.Return) and isinstance(n.value, ast.Dict) for k in n.value.keys if isinstance(k, ast.Constant)}
        for k in ('graphics', 'glslc_capture', 'ue_decode', 'oodle_packs', 'ue_legacy'): self.assertIn(k, keys)
        for k in ('glslc_capture', 'ue_decode', 'oodle_packs', 'ue_legacy'): self.assertIn(f"'{k}'", text('porter/pipeline.py'))


if __name__ == '__main__':
    unittest.main()
