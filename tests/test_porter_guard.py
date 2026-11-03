# TEST-02: tests.test_porter's engine modules. Upstream made the third-party imports lazy (the rewriter imports lz4 when a
# module's sections are LZ4-compressed, not at porter start), so a missing lz4 no longer breaks the engine's import chain:
# the suite runs to completion with lz4 shadowed, locally and under CI alike. It fails only when a stage actually reads a
# compressed module, as a run error the GUI shows (runlog.run's handler).
import os, subprocess, sys, unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
# sys.modules[name] = None makes `import lz4` raise ImportError, as a missing install does
BOOT = "import sys, unittest; sys.modules['lz4'] = None; unittest.main(module=None, argv=['x', '-v', 'tests.test_porter'])"


def run(ci):
    env = {k: v for k, v in os.environ.items() if k != 'CI'}   # GitHub Actions sets CI=true; the local case must not see it
    if ci: env['CI'] = '1'
    return subprocess.run([sys.executable, '-c', BOOT], cwd=REPO, env=env, capture_output=True, text=True, timeout=300)


class PorterGuard(unittest.TestCase):
    def test_missing_lz4_is_lazy(self):
        for ci in (False, True):
            with self.subTest(ci=ci):
                r = run(ci); out = r.stdout + r.stderr
                self.assertEqual(r.returncode, 0, out)
                self.assertNotIn('ModuleNotFoundError', out)   # nothing imports lz4 eagerly anymore
                self.assertNotIn('lz4 is not installed', out)  # and no named skip is needed


if __name__ == '__main__': unittest.main()
