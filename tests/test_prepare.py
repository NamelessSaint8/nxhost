# porter/prepare.py (`porter tools --prepare`, D-24): Prepare .NET tools builds the shader translator through the pipeline's own Port.translator (so the first port
# reuses it by the same key) and nx_extract once in a temporary folder, under the port's dotnet env (D-18); no SDK 10 stops naming the fix. The dotnet children
# are stood in: no .NET, NuGet or network is used.
import json, os, subprocess, sys, tempfile, unittest
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
HOME = Path(tempfile.mkdtemp()); os.environ['NX2A_HOME'] = str(HOME)

MISSING = None
for _m in ('lz4.block', 'capstone'):   # porter.prepare's run() imports porter.pipeline and porter.upstream, which need lz4
    try: __import__(_m)
    except ModuleNotFoundError:
        if os.environ.get('CI'): raise   # CI installs the lock: a missing module there is a failure
        MISSING = MISSING or _m


def setUpModule():
    if MISSING: raise unittest.SkipTest(f'{MISSING} is not installed (python -m pip install -r requirements.txt)')
    os.environ['NX2A_HOME'] = str(HOME)   # again: discovery imports other test modules that set their own


class Prepare(unittest.TestCase):
    def setUp(self):
        from porter import nuget, pipeline, prepare, toolchain
        from porter.upstream import PROG, nsp
        self.prepare, self.pipeline, self.seen = prepare, pipeline, []
        @contextmanager
        def restored(project, dotnet, env, log): self.seen.append(('restore', Path(project).name)); yield
        def build(repo, work, logs, env): self.work = work; self.assertTrue(work.is_dir()); self.seen.append(('build', 'nx_extract'))
        def translator(ns): self.ns = ns; self.seen.append(('build', 'translator')); return Path('/x/dmsh_xlate.dll'), 'abcdef0123456789ffff'
        for p in (mock.patch.object(toolchain, 'find_dotnet', return_value=Path('/x/dotnet')), mock.patch.object(toolchain, 'dotnet_sdks', return_value=['9.0.1', '10.0.403']),
                  mock.patch.object(pipeline.Port, 'translator', translator), mock.patch.object(nuget, 'restored', restored), mock.patch.object(nsp, 'build_nx_extract', build),
                  mock.patch.object(PROG, 'stage', lambda name, **kw: self.seen.append(('stage', name))), mock.patch.object(PROG, 'end', lambda summary='', ok=True: self.seen.append(('end', summary))),
                  mock.patch.object(PROG, 'plan', lambda n: self.seen.append(('plan', n))), mock.patch.object(PROG, 'close', lambda ok=True: None)):
            p.start(); self.addCleanup(p.stop)

    def test_stages(self):
        self.prepare.run()
        stages = [v for k, v in self.seen if k == 'stage']
        self.assertEqual(len(stages), 2); self.assertTrue(all(s.endswith(n) for s, n in zip(stages, self.prepare.STAGES)))
        self.assertEqual(self.prepare.STAGES, ('shader translator', 'nx_extract'))
        self.assertEqual(self.seen, [('plan', 2), ('stage', stages[0]), ('build', 'translator'), ('end', 'abcdef012345'), ('stage', stages[1]), ('restore', 'nx_extract'), ('build', 'nx_extract'), ('end', 'builds')])
        self.assertEqual(self.ns.tools['dotnet'], Path('/x/dotnet')); self.assertEqual(self.ns.env['DOTNET_SYSTEM_GLOBALIZATION_INVARIANT'], '1')
        self.assertIn('DOTNET_ROOT', self.ns.env); self.assertTrue(self.ns.logs.is_dir())
        self.assertFalse(self.work.exists())   # the per-game nx_extract binary is not kept: the temporary folder is gone

    def test_translator_unbound(self):   # the pipeline's own function, so the reuse key and folder are the port's, not a copy
        self.prepare.run()   # the stand-in patched onto pipeline.Port.translator was the one called: run() looks it up there, it keeps no copy
        self.assertTrue(hasattr(self, 'ns')); self.assertNotIsInstance(self.ns, self.pipeline.Port)
        self.assertIn('Port.translator(', Path(self.prepare.__file__).read_text(encoding='utf-8'))

    def test_no_dotnet(self):
        from porter import toolchain
        from porter.upstream import BuildError
        for sdks in ([], ['9.0.203']):
            with self.subTest(sdks=sdks), mock.patch.object(toolchain, 'dotnet_sdks', return_value=sdks):
                with self.assertRaisesRegex(BuildError, 'Download missing tools'): self.prepare.run()
        with mock.patch.object(toolchain, 'find_dotnet', return_value=None), self.assertRaisesRegex(BuildError, 'Download missing tools'): self.prepare.run()
        self.assertNotIn(('build', 'translator'), self.seen)


class Cli(unittest.TestCase):
    def test_cli_long(self):   # a long command: its own log first, then an error event naming the fix, exit 1
        home = Path(tempfile.mkdtemp()); stub = home / 'dotnet'; stub.write_text('not a dotnet\n')   # the configured dotnet wins and lists no SDK
        (home / 'config.json').write_text(json.dumps({'dotnet': str(stub)}))
        e = dict(os.environ, NX2A_HOME=str(home), PYTHONIOENCODING='utf-8'); e.pop('NX2A_GUI', None)
        r = subprocess.run([sys.executable, '-m', 'porter', 'tools', '--prepare', '--progress', 'json'], cwd=REPO, env=e, capture_output=True, text=True, encoding='utf-8', timeout=120)
        ev = [json.loads(ln) for ln in r.stdout.splitlines() if ln.startswith('{')]
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr); self.assertEqual(ev[0]['ev'], 'log', r.stdout)
        self.assertRegex(Path(ev[0]['path']).name, r'-tools(-\d+)?\.log$')
        err = [x for x in ev if x['ev'] == 'error']
        self.assertEqual(len(err), 1, r.stdout); self.assertIn('Download missing tools', err[0]['msg'])


if __name__ == '__main__': unittest.main()
