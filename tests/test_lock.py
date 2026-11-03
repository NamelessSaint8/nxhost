# The build-folder lock (porter/lock.py, D-06, D-07, D-14): a second port or install of a held <tid>_build/ stops at once naming the holder, and a dead
# holder never blocks the next one. Also the shared tools lock and the translator's reuse under it (CR-03). Holders are child processes; each test has its own NX2A_HOME; no game files, toolchains or device.
import errno, io, json, os, subprocess, sys, tempfile, time, unittest
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


# argv: repo, build folder, command[, seconds]. Holds the lock until killed, or for that many seconds
HOLD = '''import sys, time
sys.path.insert(0, sys.argv[1])
from porter import lock
f = lock.take(sys.argv[2], sys.argv[3]); print('held', flush=True); time.sleep(float(sys.argv[4]) if len(sys.argv) > 4 else 60)'''
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

# argv: repo, folder, command, out folder, key, go-file. Holds the lock; once the go-file exists, builds a translator into the out folder (key file last) and exits
BUILT = '''import sys, time
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from porter import lock
f = lock.take(sys.argv[2], sys.argv[3]); print('held', flush=True)
out, go = Path(sys.argv[4]), Path(sys.argv[6]); t = time.monotonic()
while not go.exists() and time.monotonic() - t < 30: time.sleep(0.05)
time.sleep(0.5); out.mkdir(parents=True, exist_ok=True); (out / 'dmsh_xlate.dll').write_text('built by the first port')
(out.parent / (out.name + '.key')).write_text(sys.argv[5] + '\\n')'''

class Spy(io.FileIO):   # CR-02: Windows refuses a read that overlaps another process's locked range; this makes POSIX refuse it too, so the bound is pinned off Windows
    def __init__(self, *a, **kw): super().__init__(*a, **kw); self.reads = []

    def _check(self, size):
        from porter import lock
        at = self.tell(); self.reads.append((at, size))
        if size < 0 or at + size > lock.AT: raise PermissionError(errno.EACCES, f'read of {size} bytes at {at} crosses the byte locked at {lock.AT}')

    def read(self, size=-1): self._check(size); return super().read(size)
    def readinto(self, b): self._check(len(b)); return super().readinto(b)


def porter(*args, home, env=None, **kw):
    e = dict(os.environ, NX2A_HOME=str(home), PYTHONIOENCODING='utf-8'); e.pop('NX2A_GUI', None); e.update(env or {})
    return subprocess.run([sys.executable, '-m', 'porter', *map(str, args)], cwd=REPO, env=e, capture_output=True, text=True, encoding='utf-8', timeout=120, **kw)


def events(out): return [json.loads(ln) for ln in out.splitlines() if ln.startswith('{')]


class Lock(unittest.TestCase):
    def setUp(self):
        self.work = Path(tempfile.mkdtemp(prefix='nx2a_test_lock_')) / '0100000000AAA000_build'; self.work.mkdir()

    def hold(self, work, cmd='port', prog=HOLD, *more):
        p = subprocess.Popen([sys.executable, '-c', prog, str(REPO), str(work), cmd, *more], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.addCleanup(lambda: (p.kill(), p.wait(), p.stdout.close(), p.stderr.close()))
        self.assertEqual(p.stdout.readline().strip(), 'held', p.stderr.read() if p.poll() is not None else '')
        return p

    def translator_port(self):   # a Port with only what translator() reads
        from porter import pipeline
        port = pipeline.Port(pipeline.Options(folder=self.work.parent))
        port.tools = {'dotnet': Path('dotnet')}; port.env = {}; port.logs = Path(tempfile.mkdtemp(prefix='nx2a_test_logs_'))
        return port

    def test_new_translator_key_keeps_old(self):   # CR-03: a rebuild for another key (an engine or .NET update) never removes the dll another port's shader_vk.py uses
        from porter import nuget, pipeline
        keys = ['1' * 64, '2' * 64]; cur = []; ran = []
        def fp(*a, **kw): cur[:] = [keys.pop(0)]; return cur[0]
        def run(cmd, log, env=None, **kw):
            ran.append(cmd[1])
            if cmd[1] == 'build': o = Path(cmd[cmd.index('-o') + 1]); o.mkdir(parents=True, exist_ok=True); (o / 'dmsh_xlate.dll').write_text(cur[0])
        with mock.patch.dict(os.environ, {'NX2A_HOME': tempfile.mkdtemp(prefix='nx2a_test_home_')}), mock.patch.object(pipeline.nsp, 'fingerprint', fp), \
             mock.patch.object(pipeline.nsp, 'run', run), mock.patch.object(nuget, 'check', lambda project: None):
            port = self.translator_port()
            d1, k1 = port.translator(); d2, k2 = port.translator()
            self.assertEqual((k1, k2), ('1' * 64, '2' * 64)); self.assertNotEqual(d1, d2)
            self.assertEqual(d1.read_text(), '1' * 64); self.assertEqual(d2.read_text(), '2' * 64)

    def test_waiting_port_reuses_translator(self):   # CR-03: the two first ports after an engine update; the one that waited used to rebuild and swap over the translator the first had just built
        from porter import nuget, paths, pipeline
        K = 'c' * 64; ran = []
        with mock.patch.dict(os.environ, {'NX2A_HOME': tempfile.mkdtemp(prefix='nx2a_test_home_')}):
            tools = paths.user_dir() / 'tools'; out = tools / f'dmsh_xlate-{K[:12]}'; go = tools / 'go'
            self.hold(tools, 'tool build', BUILT, str(out), K, str(go))
            def fp(*a, **kw): go.touch(); return K   # runs just before translator()'s first reuse check: the holder builds only after that check has failed
            def run(cmd, log, env=None, **kw):
                ran.append(cmd[1])
                if cmd[1] == 'build': o = Path(cmd[cmd.index('-o') + 1]); o.mkdir(parents=True, exist_ok=True); (o / 'dmsh_xlate.dll').write_text('rebuilt')
            with mock.patch.object(pipeline.nsp, 'fingerprint', fp), mock.patch.object(pipeline.nsp, 'run', run), mock.patch.object(nuget, 'check', lambda project: None):
                self.assertEqual(self.translator_port().translator(), (out / 'dmsh_xlate.dll', K))
            self.assertEqual(ran, ['restore']); self.assertEqual((out / 'dmsh_xlate.dll').read_text(), 'built by the first port')

    def test_second_take_names_holder(self):
        from porter import lock
        from porter.upstream import BuildError
        p = self.hold(self.work)
        with self.assertRaises(BuildError) as c: lock.take(self.work, 'install')
        self.assertTrue(str(c.exception).startswith(f'already running: porter port, PID {p.pid}, started '), str(c.exception))
        self.assertIn(str(self.work), str(c.exception))

    def test_holder_read_stays_below_lock(self):   # CR-02: the holder lookup never asks the OS for the byte the holder locked at AT
        from porter import lock
        from porter.upstream import BuildError
        p = self.hold(self.work); made = []
        def opener(path, mode, buffering=-1):   # the same layering open() builds
            raw = Spy(path, mode); made.append(raw); return raw if buffering == 0 else io.BufferedRandom(raw)
        with mock.patch.object(lock, 'open', opener, create=True), self.assertRaises(BuildError) as c: lock.take(self.work, 'install')
        self.assertTrue(str(c.exception).startswith(f'already running: porter port, PID {p.pid}'), str(c.exception))
        reads = [r for raw in made for r in raw.reads]
        self.assertTrue(reads); self.assertTrue(all(at + n <= lock.AT for at, n in reads), reads)

    def test_wait_for_holder(self):   # the shared tools lock: a second port waits for the first instead of stopping
        from porter import lock
        self.hold(self.work, 'tool build', HOLD, '2'); t = time.monotonic()
        f = lock.take(self.work, 'tool build', wait=True); self.addCleanup(f.close)
        self.assertGreaterEqual(time.monotonic() - t, 1); self.assertLess(time.monotonic() - t, 10)
        self.assertTrue((self.work / '.porter.lock').read_text(encoding='utf-8').startswith(f'porter tool build, PID {os.getpid()}, '))

    def test_wait_false_unchanged(self):
        from porter import lock
        from porter.upstream import BuildError
        self.hold(self.work); t = time.monotonic()
        with self.assertRaises(BuildError) as c: lock.take(self.work, 'port')
        self.assertIn('already running', str(c.exception)); self.assertLess(time.monotonic() - t, 1)

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
        with mock.patch.object(pipeline.nsp, 'scan_nsps', lambda folder, from_package=None, contents_of=None, want=None: (0x0100000000AAA000, {})), \
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
