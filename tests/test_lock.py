# The build-folder lock (porter/lock.py, D-06, D-07, D-14): a second port or install of a held <tid>_build/ stops at once naming the holder, and a dead
# holder never blocks the next one. Holders are child processes; each test has its own NX2A_HOME; no game files, toolchains or device.
import json, os, subprocess, sys, tempfile, unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
os.environ['NX2A_HOME'] = tempfile.mkdtemp(prefix='nx2a_test_home_')

MISSING = None
for _m in ('lz4.block', 'capstone'):
    try: __import__(_m)
    except ModuleNotFoundError:
        if os.environ.get('CI'): raise   # CI installs the lock: a missing module there is a failure
        MISSING = MISSING or _m


def setUpModule():   # not a module-level SkipTest: `python -m unittest tests.test_lock` crashes on one
    if MISSING: raise unittest.SkipTest(f'{MISSING} is not installed (python -m pip install -r requirements.txt)')


# argv: repo, build folder, command. Holds the lock until killed
HOLD = '''import sys, time
sys.path.insert(0, sys.argv[1])
from porter import lock
f = lock.take(sys.argv[2], sys.argv[3]); print('held', flush=True); time.sleep(60)'''
# the OS lock only, with no text in the file (as take's branches)
RAW = '''import os, sys, time
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from porter import lock
f = open(Path(sys.argv[2]) / '.porter.lock', 'a+b')
if os.name == 'nt':
    import msvcrt; f.seek(lock.AT); msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
else:
    import fcntl; fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
print('held', flush=True); time.sleep(60)'''


def porter(*args, home, env=None, **kw):
    e = dict(os.environ, NX2A_HOME=str(home), PYTHONIOENCODING='utf-8'); e.pop('NX2A_GUI', None); e.update(env or {})
    return subprocess.run([sys.executable, '-m', 'porter', *map(str, args)], cwd=REPO, env=e, capture_output=True, text=True, encoding='utf-8', timeout=120, **kw)


def events(out): return [json.loads(ln) for ln in out.splitlines() if ln.startswith('{')]


class Lock(unittest.TestCase):
    def setUp(self):
        self.work = Path(tempfile.mkdtemp(prefix='nx2a_test_lock_')) / '0100000000AAA000_build'; self.work.mkdir()

    def hold(self, work, cmd='port', prog=HOLD):
        p = subprocess.Popen([sys.executable, '-c', prog, str(REPO), str(work), cmd], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.addCleanup(lambda: (p.kill(), p.wait(), p.stdout.close(), p.stderr.close()))
        self.assertEqual(p.stdout.readline().strip(), 'held', p.stderr.read() if p.poll() is not None else '')
        return p

    def test_second_take_names_holder(self):
        from porter import lock
        from porter.upstream import BuildError
        p = self.hold(self.work)
        with self.assertRaises(BuildError) as c: lock.take(self.work, 'install')
        self.assertTrue(str(c.exception).startswith(f'already running: porter port, PID {p.pid}, started '), str(c.exception))
        self.assertIn(str(self.work), str(c.exception))

    def test_freed_when_holder_dies(self):
        from porter import lock
        p = self.hold(self.work); p.kill(); p.wait()
        f = lock.take(self.work, 'port'); f.close()
        self.assertTrue((self.work / '.porter.lock').exists())

    def test_creates_folder(self):
        from porter import lock
        w = self.work / 'new'
        f = lock.take(w, 'port'); self.addCleanup(f.close)
        self.assertTrue((w / '.porter.lock').read_text(encoding='utf-8').startswith(f'porter port, PID {os.getpid()}, started '))

    def test_empty_lock_file(self):
        from porter import lock
        from porter.upstream import BuildError
        self.hold(self.work, prog=RAW)
        with self.assertRaises(BuildError) as c: lock.take(self.work, 'port')
        self.assertIn('already running: another porter', str(c.exception))

    @unittest.skipIf(os.name == 'nt', 'symlinks need privileges on Windows')
    def test_symlink_spelling(self):   # the lock is on the file, not on its path
        from porter import lock
        from porter.upstream import BuildError
        self.hold(self.work)
        link = self.work.parent / 'link_build'; link.symlink_to(self.work, target_is_directory=True)
        with self.assertRaises(BuildError) as c: lock.take(link, 'port')
        self.assertIn('already running', str(c.exception))

    def test_port_inputs_takes_lock(self):
        from porter import pipeline
        from porter.upstream import BuildError
        game = self.work.parent
        with mock.patch.object(pipeline.nsp, 'scan_nsps', lambda folder: (0x0100000000AAA000, {})), \
             mock.patch.object(pipeline.profiles, 'by_title', lambda tid: (None, None)):
            p = self.hold(self.work)
            port = pipeline.Port(pipeline.Options(folder=game))
            with self.assertRaises(BuildError) as c: port.inputs()
            self.assertIn('already running', str(c.exception))
            p.kill(); p.wait()
            port = pipeline.Port(pipeline.Options(folder=game))
            with self.assertRaises(BuildError) as c: port.inputs()
            self.addCleanup(port.lock.close)
            self.assertIn('no game profile', str(c.exception))

    def test_install_cli_already_running(self):   # the pack names its build folder through the host-only sidecar beside it (D-14)
        t = self.work.parent
        (t / 'X-data').mkdir(); (t / 'X-data/nx2a-data.json').write_text('{"package": "org.nx2a.x", "name": "X"}', encoding='utf-8')
        (t / 'X-data.build').write_text(str(self.work), encoding='utf-8')
        self.hold(self.work)
        r = porter('install', t / 'X-data', '--progress', 'json', home=Path(tempfile.mkdtemp()))
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        err = [e for e in events(r.stdout) if e['ev'] == 'error']
        self.assertEqual(len(err), 1, r.stdout)
        self.assertTrue(err[0]['msg'].startswith('already running: porter port'), err[0])


if __name__ == '__main__':
    unittest.main()
