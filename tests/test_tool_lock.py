# dm/gfx/tools/tool_lock.py's refusals: a synthetic dmsh_chain.lock mismatch names its key in the exact [RED] sentence and returns 1, a match returns 0, and no argument is a usage error.
# No Xcode, .NET or brew here: tools_now (which shells out to xcrun for the Metal compilers) and xlate_source_sha (the rebuild note) are patched, so this runs on all four CI hosts, and the
# constant the test asserts is the module's own, so the remedy a player reads cannot drift from what is checked.
import io, sys, tempfile, unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / 'nxnative/dm/gfx/tools'))   # as tests/test_hosttools.py reaches the engine's tools

import tool_lock   # noqa: E402


class Lock(unittest.TestCase):
    def lock(self, **rows):   # a synthetic lock file: the given key/value rows under the real header's shape
        p = Path(tempfile.mkdtemp()) / 'dmsh_chain.lock'
        p.write_text('# synthetic\n' + ''.join(f'{k}\t{v}\n' for k, v in rows.items()), encoding='utf-8')
        return p

    def run_main(self, argv, rows, now):   # main's return code with the lock file and the tools stood in for
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(tool_lock, 'LOCK', self.lock(**rows)), mock.patch.object(tool_lock, 'tools_now', lambda: now), \
                mock.patch.object(tool_lock, 'xlate_source_sha', lambda: 'in-repo'), redirect_stdout(out), redirect_stderr(err):
            code = tool_lock.main(argv)
        return code, out.getvalue(), err.getvalue()

    def test_a_mismatch_names_its_key_and_returns_one(self):
        code, out, err = self.run_main(['--check-tools'], {'spirv-cross': 'lock-value', 'xlate_source': 'in-repo'},
                                       {'spirv-cross': 'other-build', 'xlate_source': 'in-repo'})
        self.assertEqual(code, 1, out + err)
        self.assertEqual(out.splitlines(), [f'{tool_lock.MISMATCH}spirv-cross: lock lock-value / actual other-build'])

    def test_a_match_returns_zero_and_says_nothing_red(self):
        rows = {'spirv-cross': 'lock-value', 'xlate_source': 'in-repo'}
        code, out, err = self.run_main(['--check-tools'], rows, dict(rows))
        self.assertEqual(code, 0, out + err)
        self.assertNotIn('[RED]', out + err)

    def test_no_option_is_usage(self):   # the one path that used to sys.exit a string: a code, not a SystemExit to guess at
        code, out, err = self.run_main([], {}, {})
        self.assertEqual(code, 2, out + err)
        self.assertIn('usage: tool_lock.py --check-tools | --update-lock', out + err)

    def test_the_no_run_remedy_still_names_the_runtime(self):
        msg = tool_lock.no_run_message('does not run (boom)')
        self.assertIn('brew install --cask dotnet-sdk', msg)
        self.assertIn('DOTNET_ROOT', msg)


if __name__ == '__main__':
    unittest.main()
