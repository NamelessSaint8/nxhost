# Unit tests of the port pipeline's own parts (python -m unittest discover tests). They need no game files, toolchains or device.
import json, os, re, shutil, sys, tempfile, unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
os.environ['NX2A_HOME'] = tempfile.mkdtemp(prefix='nx2a_test_home_')

MISSING = None
try:
    from porter import config, datapack, pipeline, profiles   # noqa: E402
    from porter.upstream import android_profile, game, nsp     # noqa: E402
except ModuleNotFoundError as e:   # CI installs the lock, so there a missing engine module fails; locally it is a named skip
    if (MISSING := (e.name or '').split('.')[0]) not in ('lz4', 'capstone', 'PIL', 'yaml', 'backports') or os.environ.get('CI'): raise


def setUpModule():   # not a module-level SkipTest: `python -m unittest tests.test_porter` crashes on one
    if MISSING: raise unittest.SkipTest(f'{MISSING} is not installed (python -m pip install -r requirements.txt): the engine modules need it')

NEO = '010043B013C5C000'


def profile_dir(rows, gid='0100000000AAA000'):
    """A throwaway game profile with an android.tsv of these rows, found through DM_GAMES_DIR"""
    root = Path(tempfile.mkdtemp(prefix='nx2a_test_profiles_')); d = root / gid; d.mkdir()
    (d / 'game.tsv').write_text(f'title_id\t{gid}\nprogram_id\t{gid}\nname\tTest Game\nipa\tTestGame.ipa\nmodules\tmain sdk\n', encoding='utf-8')
    (d / 'android.tsv').write_text(''.join(f'{k}\t{v}\n' for k, v in rows), encoding='utf-8')
    os.environ['DM_GAMES_DIR'] = str(root)
    return d


class AndroidProfiles(unittest.TestCase):
    def tearDown(self): os.environ.pop('DM_GAMES_DIR', None)

    def test_neo(self):
        p = profiles.load(NEO)
        self.assertEqual(p.status, 'playable'); self.assertEqual(p.package, 'org.nx2a.neo'); self.assertTrue(p.landscape)
        self.assertEqual(p.settings, {'docked': '0', 'overlay': '1', 'rumble': '1'}); self.assertEqual(p.requires, ['bcn'])

    def test_only_android_profiles_listed(self):
        rows = profiles.all_entries()
        self.assertIn(NEO, [r.id for r in rows]); self.assertTrue(all(r.android for r in rows))
        self.assertGreater(len(profiles.all_entries(android_only=False)), len(rows))

    def test_fps_setting(self):   # the pause menu's Show FPS (front_android.c settings_load fps=)
        d = profile_dir([('status', 'boots'), ('setting', 'fps=1')])
        self.assertEqual(android_profile.load(d.name).settings, {'fps': '1'})
        with self.assertRaises(android_profile.ProfileError): android_profile.load(profile_dir([('status', 'boots'), ('setting', 'fps=2')]).name)

    def test_default_package(self):
        d = profile_dir([('status', 'boots')])
        self.assertEqual(android_profile.load(d.name).package, 'org.nx2a.t0100000000aaa000')

    def test_bad_keys_are_refused(self):
        for rows in ([('status', 'great')], [('colour', 'red')], [('setting', 'volume=3')], [('overlay', 'q 0.1 0.2')], [('env', 'lower=1')], [('package', 'Not A Package')],
                     [('status', 'boots'), ('status', 'playable')]):
            d = profile_dir(rows)
            with self.assertRaises(android_profile.ProfileError, msg=rows): android_profile.load(d.name)

    def test_space_separated_rows_say_tab(self):   # cat renders a TAB and a space alike, so the error has to name the real fault
        d = profile_dir([('status', 'boots')])
        (d / 'android.tsv').write_text('status  playable\n', encoding='utf-8')   # spaces, not a TAB
        with self.assertRaises(android_profile.ProfileError) as e: android_profile.load(d.name)
        self.assertIn('rows are tab-separated', str(e.exception)); self.assertNotIn('unknown key', str(e.exception))

    def test_header_default_layout(self):   # the generated table is overlay_layout.h's table as it was written by hand before it moved to overlay_default.tsv
        h = android_profile.header(android_profile.load(NEO))
        rows = re.findall(r'\{(OV_\w+), ([\d.]+)f, ([\d.]+)f, ([\d.]+)f, (\w+), "([^"]*)"\}', h)
        self.assertEqual(len(rows), 16)
        self.assertEqual(rows[0], ('OV_STICK_L', '0.12', '0.70', '0.12', '0', ''))
        self.assertEqual(rows[2], ('OV_BUTTON', '0.935', '0.60', '0.050', 'DM_BTN_A', 'A'))
        self.assertEqual(rows[10][-1], '-')   # the minus button's label, not "no label"

    def test_header_overlay_move(self):
        d = profile_dir([('status', 'boots'), ('overlay', 'a 0.5 0.5 0.07')])
        h = android_profile.header(android_profile.load(d.name))
        self.assertIn('{OV_BUTTON, 0.5f, 0.5f, 0.07f, DM_BTN_A, "A"}', h)


class DataPack(unittest.TestCase):
    def test_build(self):
        t = Path(tempfile.mkdtemp(prefix='nx2a_test_pack_'))
        try:
            (t / 'patched').mkdir(); (t / 'patched/main.patched.bin').write_bytes(b'x' * 10)
            (t / 'romfs/Data').mkdir(parents=True); (t / 'romfs/Data/a.bin').write_bytes(b'y' * 20)
            (t / 'aoc/1').mkdir(parents=True); (t / 'aoc/1/d.bin').write_bytes(b'z')
            (t / 'shaders.dmsv').write_bytes(b'DMSV')
            p = profiles.load(NEO)
            man = datapack.build(t / 'out-data', profile=p, version='v196608', display='1.03', patched=t / 'patched', romfs=t / 'romfs', shaders=t / 'shaders.dmsv',
                                 aoc=t / 'aoc', language='ja')
            o = t / 'out-data'
            self.assertTrue((o / 'mods/main.patched.bin').is_file()); self.assertTrue((o / 'RomFS/Data/a.bin').is_file()); self.assertTrue((o / 'aoc/1/d.bin').is_file())
            env = (o / 'env.txt').read_text()
            self.assertIn('DM_LANG=ja', env); self.assertIn('DM_AOC_DIR=/sdcard/Android/data/org.nx2a.neo/files/aoc', env)
            self.assertEqual((o / 'settings.txt').read_text(), 'docked=0\noverlay=1\nrumble=1\n')
            self.assertEqual((man['files'], man['bytes'], man['dlc'], man['requires']), (4, 35, [1], ['bcn']))   # the installer checks requires
            self.assertEqual(datapack.read_manifest(o)['package'], 'org.nx2a.neo')
        finally:
            shutil.rmtree(t, ignore_errors=True)


class Experimental(unittest.TestCase):
    def test_ios_profile_copied_with_experimental_android_tsv(self):   # an iOS-only profile is copied out of the repository, never edited in place
        odyssey = '0100000000010000'
        t = Path(tempfile.mkdtemp(prefix='nx2a_test_exp_')); environ = dict(os.environ)
        try:
            port = pipeline.Port(pipeline.Options(folder=t, experimental=True)); port.env = {}; port.work = t / f'{odyssey}_build'; port.o.keys = None
            g, ap = port.experimental_profile(game.load(odyssey), odyssey)
            self.assertEqual(g.dir, (t / f'{odyssey}_build/profile/{odyssey}').resolve())
            self.assertEqual((ap.status, ap.package), ('experimental', f'org.nx2a.t{odyssey}'))
            self.assertFalse((REPO / f'nxnative/dm/games/{odyssey}/android.tsv').exists())
            self.assertFalse((g.dir / 'patches.py').exists())   # patch_nso.py finds the per-build cuts in dm/games
            self.assertEqual(port.env.get('DM_GAMES_FIRST'), '1')
            self.assertEqual(dict(os.environ), environ)   # HARD-06: the profile reaches the tools through port.env only
        finally:
            os.environ.clear(); os.environ.update(environ); shutil.rmtree(t, ignore_errors=True)


class Env(unittest.TestCase):   # HARD-06: a port never writes os.environ; every child gets port.env, dotnet by absolute path
    def setUp(self): self.t = Path(tempfile.mkdtemp(prefix='nx2a_test_env_')); self.run = nsp.run
    def tearDown(self): nsp.run = self.run; shutil.rmtree(self.t, ignore_errors=True)

    def test_use_profile_dir_leaves_environ(self):
        from types import SimpleNamespace as NS
        before, p = dict(os.environ), NS(env={'DM_GAMES_DIR': 'x'})
        pipeline.Port.use_profile_dir(p, self.t, first=True)
        self.assertEqual(p.env['DM_GAMES_DIR'], os.pathsep.join([str(self.t), 'x'])); self.assertEqual(p.env['DM_GAMES_FIRST'], '1')
        self.assertEqual(dict(os.environ), before)

    def test_nx_extract_gets_env(self):   # nx_extract's apphost finds .NET 10 through DOTNET_ROOT in the env it is given
        envs, E = [], {'DOTNET_ROOT': 'x'}
        def run(cmd, log, env=None, **k): envs.append(env); Path(cmd[4]).mkdir(parents=True)
        nsp.run = run
        base = self.t / 'base.nsp'; base.write_bytes(b'\0'); (self.t / 'logs').mkdir()
        nsp.extract('nx', 'keys', self.t / 'ex', 'v0', base, None, None, self.t / 'logs', {'romfs_marker': 'm'}, 0x1000000000000, env=E)
        nsp.extract_aoc('nx', 'keys', pipeline.NXNATIVE, self.t, 0x0100000000AAA000, {'dlc': [(0x0100000000AAB001, 0, base)]}, self.t / 'logs', env=E)
        self.assertEqual(envs, [E, E])

    def test_dotnet_absolute(self):   # Windows finds a bare program name through the parent's PATH, not the child's
        exe = self.t / ('dotnet.exe' if os.name == 'nt' else 'dotnet'); exe.write_bytes(b''); exe.chmod(0o755)
        argv = []; nsp.run = lambda cmd, log, env=None, **k: argv.extend(cmd)
        with self.assertRaises(pipeline.BuildError): nsp.build_nx_extract(pipeline.NXNATIVE, self.t / 'work', self.t / 'logs', {'PATH': str(self.t)})   # no executable built
        self.assertEqual(Path(argv[0]).resolve(), exe.resolve())

    def test_no_environ_writes(self):
        code = '\n'.join(ln for ln in (REPO / 'porter/pipeline.py').read_text(encoding='utf-8').splitlines() if not ln.lstrip().startswith('#'))
        self.assertIsNone(re.search(r"os\.environ\[[^]]*\]\s*=(?!=)|os\.environ\.(update|setdefault|pop)\(", code))


class Overrides(unittest.TestCase):   # porter/upstream.py _overrides: what porter replaces in upstream's NSP script, checked at import
    def test_loaded_module(self):
        from porter import upstream
        self.assertIs(nsp.nacp, upstream.nacp); self.assertIs(nsp.pg, upstream.profile_guess)
        if sys.platform != 'darwin': self.assertFalse(nsp.can_clone(Path('.')))
        self.assertNotIn('android.tsv', [f.name for f in nsp.profile_files(game.load(NEO))])

    def test_missing_attribute_fails_loudly(self):   # an upstream rename fails at import, naming the attribute
        from types import SimpleNamespace as NS
        from porter.upstream import _overrides
        def main():
            global nacp, pg; nacp = pg = None
        def main_no_pg():
            global nacp; nacp = None
        with self.assertRaisesRegex(AssertionError, 'profile_files'): _overrides(NS(main=main, can_clone=lambda d: True))
        with self.assertRaisesRegex(AssertionError, 'nacp.*pg|pg.*nacp'): _overrides(NS(main=main_no_pg, can_clone=lambda d: True, profile_files=lambda g: []))


class Misc(unittest.TestCase):
    def test_config_roundtrip(self):
        config.set_value('device', 'abc:5555'); self.assertEqual(config.load()['device'], 'abc:5555')
        with self.assertRaises(KeyError): config.set_value('nope', 'x')

    def test_version_code_grows_with_updates(self):
        self.assertLess(pipeline.version_code('v0'), pipeline.version_code('v65536'))
        self.assertEqual(pipeline.version_code('v196608'), 196609)

    def test_app_stem(self):
        self.assertEqual(pipeline.app_stem(game.load(NEO), 'NEO'), 'NeoTheWorldEndsWithYou')

    def test_disk_space(self):   # twice the files the port reads (base, updates, DLC, wherever they sit), less what the build folder holds, plus 1 GB (D-15)
        from types import SimpleNamespace as NS
        d = Path(tempfile.mkdtemp(prefix='nx2a_test_game_')); work = d / 'build'; (d / 'dlc').mkdir(); M, G = 2**20, 2**30
        fam = {'base': d / 'g.nsp', 'updates': [(65536, d / 'u.nsp')], 'dlc': [(1, 0, d / 'dlc/a.nsp')]}
        for f in (d / 'g.nsp', d / 'u.nsp', d / 'dlc/a.nsp'): f.write_bytes(b'\0' * M)
        (d / 'other.nsp').write_bytes(b'\0' * 2 * M)   # not in the family: not counted
        p = NS(o=NS(folder=d), work=work, fam=fam); real = shutil.disk_usage
        try:
            shutil.disk_usage = lambda _: NS(free=6 * M + G - 1)
            with self.assertRaises(pipeline.BuildError): pipeline.Port.check_space(p)
            shutil.disk_usage = lambda _: NS(free=6 * M + G); pipeline.Port.check_space(p)
            shutil.disk_usage = lambda _: NS(free=5 * M + G)
            work.mkdir(); (work / 'sub').mkdir(); (work / 'sub/x').write_bytes(b'\0' * M); pipeline.Port.check_space(p)   # a build folder already there counts, recursively
        finally: shutil.disk_usage = real; shutil.rmtree(d, ignore_errors=True)

    def test_disk_space_after_extraction(self):   # the re-check with real sizes; an output folder on another volume needs the RomFS and DLC again (hard links become copies)
        from types import SimpleNamespace as NS
        d = Path(tempfile.mkdtemp(prefix='nx2a_test_game_')); work, out = d / 'build', d / 'out'; M, G = 2**20, 2**30
        (d / 'g.nsp').write_bytes(b'\0' * M); out.mkdir()
        for f in (work / 'extract/v0/RomFS/f', work / 'aoc/1/f'): f.parent.mkdir(parents=True); f.write_bytes(b'\0' * M)
        p = NS(o=NS(folder=d, out=out), work=work, fam={'base': d / 'g.nsp', 'updates': [], 'dlc': []}, game=work / 'extract/v0', aoc=work / 'aoc')
        real_du, real_stat, free = shutil.disk_usage, os.stat, {}
        try:
            shutil.disk_usage = lambda q: NS(free=free.get(Path(q), G))
            pipeline.Port.check_space(p, extracted=True)   # same volume: 2 × 1 MiB − 2 MiB built + 1 GiB
            def stat(q, *a, **k):
                r = real_stat(q, *a, **k)
                return NS(st_dev=r.st_dev + 1, st_mode=r.st_mode, st_size=r.st_size) if Path(q) == out else r
            os.stat = stat
            free[out] = 2 * M + G - 1
            with self.assertRaisesRegex(pipeline.BuildError, re.escape(str(out))): pipeline.Port.check_space(p, extracted=True)
            free[out] = 2 * M + G; pipeline.Port.check_space(p, extracted=True)
        finally: shutil.disk_usage, os.stat = real_du, real_stat; shutil.rmtree(d, ignore_errors=True)


class FpsLocker(unittest.TestCase):   # porter/fpslocker.py: FPSLocker-Warehouse configs → the host's rows (hle_fpslock.c DM_FPS_LOCKS) and the rewriter's cuts
    BID = 'd49165c05ead8ae140f189aa97934f39'
    UNITY = ('ALL_FPS:\n  # Vsync\n  -\n    type: evaluate_write\n    address: [MAIN, 0x7A642D8]\n    value_type: int32\n    value: VSYNC_TARGET\n'
             '  -\n    type: evaluate_write\n    address: [MAIN, 0x7A642E4]\n    value_type: float\n    value: "1 / FPS_LOCK_TARGET"\n')   # the shape of Viractal 1.4.5's config

    def rows(self, text, image=b''):
        from porter import fpslocker
        tsv, cuts = fpslocker.convert(text, image, self.BID, 'test')
        return [l.split('\t') for l in tsv.splitlines() if not l.startswith('#')], cuts

    def test_unity_vsync_and_frame_time(self):   # 2 vsyncs / 1/30 s at 30; 1 vsync / 1/62 s at 60 (FPS_LOCK_TARGET is the target + 2 at the refresh rate)
        rows, cuts = self.rows(self.UNITY)
        self.assertEqual(rows[0], ['build', self.BID]); self.assertEqual(cuts, [])
        self.assertEqual(rows[1][1:], ['int32', '0x7a642d8', '2', '1', '-'])
        self.assertEqual(rows[2][1:3], ['float', '0x7a642e4']); self.assertAlmostEqual(float(rows[2][3]), 1 / 30); self.assertAlmostEqual(float(rows[2][4]), 1 / 62)

    def test_expressions(self):
        from porter.fpslocker import evaluate
        self.assertEqual(evaluate('TruncDec(FRAMETIME_TARGET, 2)', 30), 33.33); self.assertEqual(evaluate('2^3', 60), 8)
        self.assertEqual(evaluate('VSYNC_TARGET', 60), 1); self.assertEqual(evaluate('floor(FPS_TARGET / 7)', 60), 8)
        with self.assertRaises(Exception): evaluate('__import__("os")', 60)

    def test_pointers_lists_and_compares(self):
        rows, _ = self.rows('ALL_FPS:\n  -\n    type: compare\n    compare_address: [MAIN, 0x10, 0x8]\n    compare_type: "!="\n    compare_value_type: int8\n    compare_value: 0\n'
                            '    address: [MAIN, 0x20, 0x30, -4]\n    value_type: int32\n    value: [2, 2]\n  -\n    type: block\n    what: timing\n')
        self.assertEqual(rows[1][1:], ['int32', '0x20,0x30,-0x4', '2,2', '2,2', 'int8 0x10,0x8 != 0'])
        self.assertEqual(len(rows), 2)   # block timing is FPSLocker's own frame delay: dropped

    def test_refused_whole(self):   # entries work together: one the host cannot apply refuses the config
        from porter import fpslocker
        for text in (self.UNITY + 'DECLARATIONS:\n  -\n    type: variable\n    name: x\n    value_type: float\n    default_value: 0\n',
                     self.UNITY + 'MASTER_WRITE:\n  -\n    type: asm_a64\n    main_offset: 0x10\n    instructions: [[b.ne, :goto1], [nop], :goto1, [nop]]\n',   # labels parse
                     'ALL_FPS:\n  -\n    type: write\n    address: [HEAP, 0x10]\n    value_type: int32\n    value: 1\n',
                     'ALL_FPS:\n  -\n    type: compare\n    compare_address: [MAIN, 0x10]\n    compare_type: "=="\n    compare_value_type: int8\n    compare_value: 1\n    value_type: refresh_rate\n    value: 30\n',
                     'ALL_FPS: [\n'):
            with self.assertRaises(fpslocker.Refused): fpslocker.convert(text, b'', self.BID)

    def test_master_write_bytes_are_cuts(self):   # the original bytes come from main's image, so the rewriter can assert them
        image = bytes(range(256)) * 4
        _, cuts = self.rows(self.UNITY + 'MASTER_WRITE:\n  -\n    type: bytes\n    main_offset: 0x10\n    value_type: uint8\n    value: [0x1F, 0x20, 0x03]\n', image)
        self.assertEqual(cuts, [(0x10, '101112', '1f2003', 'FPSLocker-Warehouse MASTER_WRITE entry 1')])
        from porter import fpslocker
        ns = {}; exec(fpslocker.patches_py(self.BID, cuts), ns); self.assertEqual(ns['CUTS'][self.BID][0][:3], (0x10, '101112', '1f2003'))

    def test_url(self):
        from porter import fpslocker, pins
        self.assertTrue(fpslocker.url('0100fd501f95a000', self.BID).endswith('/patches/0100FD501F95A000/D49165C05EAD8AE1.yaml'))
        self.assertIn(f'/{pins.FPSLOCKER}/', fpslocker.url('0100fd501f95a000', self.BID)); self.assertIn('/abc/', fpslocker.url('0100fd501f95a000', self.BID, 'abc'))

    # fetch over a faked urlopen: {url: body} answers 200, any other URL a 404; the configs are the synthetic UNITY sample, never the warehouse's
    TID, HEAD = '0100FD501F95A000', 'b' * 40

    def fetch(self, table):
        import io, urllib.error
        from unittest import mock
        from porter import fpslocker
        seen = []
        def urlopen(req, timeout=None, context=None):
            seen.append(req.full_url)
            if req.full_url not in table: raise urllib.error.HTTPError(req.full_url, 404, 'gone', {}, None)
            return io.BytesIO(table[req.full_url].encode())
        with mock.patch.object(fpslocker.urllib.request, 'urlopen', urlopen): return fpslocker.fetch(self.TID, self.BID), seen

    def test_pinned_commit(self):
        from porter import fpslocker, pins
        got, seen = self.fetch({fpslocker.url(self.TID, self.BID): self.UNITY})
        self.assertEqual(got, (self.UNITY, pins.FPSLOCKER)); self.assertNotIn(fpslocker.HEAD_API, seen)

    def test_head_fallback(self):   # a build newer than the pin: the config at v4's head
        from porter import fpslocker
        got, _ = self.fetch({fpslocker.HEAD_API: self.HEAD + '\n', fpslocker.url(self.TID, self.BID, self.HEAD): self.UNITY})
        self.assertEqual(got, (self.UNITY, self.HEAD))

    def test_none_anywhere(self):
        from porter import fpslocker, pins
        self.assertIsNone(self.fetch({fpslocker.HEAD_API: self.HEAD})[0])
        got, seen = self.fetch({fpslocker.HEAD_API: pins.FPSLOCKER})   # head is the pin: its config is not asked for twice
        self.assertIsNone(got); self.assertEqual(seen.count(fpslocker.url(self.TID, self.BID)), 1)

    def test_bad_head(self):   # a rate-limit page or anything not a commit takes the cached-copy path
        from porter import fpslocker
        with self.assertRaises(OSError): self.fetch({fpslocker.HEAD_API: '{"message": "API rate limit exceeded"}'})

    def test_source_recorded(self):   # fps_unlock's source names the URL at the commit, the commit and the config's SHA-256; the build folder's fpslock.tsv keeps it
        import hashlib
        from porter import fpslocker
        src = f'{fpslocker.url(self.TID, self.BID, self.HEAD)} (commit {self.HEAD[:12]}, sha256 {hashlib.sha256(self.UNITY.encode()).hexdigest()})'
        tsv, _ = fpslocker.convert(self.UNITY, b'', self.BID, src)
        self.assertIn(src, tsv.splitlines()[0]); self.assertIn(src, fpslocker.patches_py(self.BID, [], src).splitlines()[0])

    def fps_unlock(self, aw, got):   # pipeline.Port.fps_unlock with main's image and the fetch faked; returns the say lines
        import hashlib
        from types import SimpleNamespace
        from unittest import mock
        port = pipeline.Port.__new__(pipeline.Port); said = []
        port.env, port.o, port.aw, port.game, port.package = {}, SimpleNamespace(fps60=True), aw, aw, 'com.example.game'
        port.g = SimpleNamespace(id=self.TID, get=lambda k, d=None: d)
        fetch = mock.Mock(side_effect=got) if isinstance(got, Exception) else mock.Mock(return_value=got)
        with mock.patch.object(pipeline.fpslocker, 'nso_image', return_value=(b'', self.BID)), mock.patch.object(pipeline.fpslocker, 'fetch', fetch), \
             mock.patch.object(pipeline, 'PROG'), mock.patch.object(pipeline, 'say', said.append): port.fps_unlock()
        self.assertIn(f'sha256 {hashlib.sha256(self.UNITY.encode()).hexdigest()}', (aw / 'fpslock' / 'fpslock.tsv').read_text().splitlines()[0])
        return said

    def test_fps_unlock_records_commit(self):   # the cache keeps the commit; offline it is read back; a cache from before the pin reads as commit unknown
        from porter import pins
        with tempfile.TemporaryDirectory() as t:
            aw = Path(t); cache = aw / 'fpslock' / f'{self.BID[:16].upper()}.yaml'
            said = self.fps_unlock(aw, (self.UNITY, pins.FPSLOCKER))
            self.assertEqual(cache.read_text(), f'# FPSLocker-Warehouse commit {pins.FPSLOCKER}\n{self.UNITY}')
            self.assertIn(f'commit {pins.FPSLOCKER[:12]}', said[-1]); self.assertFalse([l for l in said if 'untested' in l])
            said = self.fps_unlock(aw, OSError('offline'))
            self.assertIn(f'commit {pins.FPSLOCKER[:12]}', said[-1]); self.assertIn('copy fetched before', said[0])
            cache.write_text(self.UNITY); said = self.fps_unlock(aw, OSError('offline'))
            self.assertIn('commit unknown', said[-1]); self.assertTrue([l for l in said if l.startswith('[RED]') and 'untested' in l])
            said = self.fps_unlock(aw, (self.UNITY, self.HEAD))
            self.assertTrue([l for l in said if l.startswith('[RED]') and 'untested' in l and f'/{self.HEAD}/' in l])


class MacTarget(unittest.TestCase):   # --platform mac-app: a Mac app's port (pipeline.run_mac, dm/mac/pack_app.py), no game files or toolchains needed here
    def test_platform_option_reaches_the_port(self):
        from porter import cli
        self.assertEqual(cli._parser().parse_args(['port', 'x']).platform, 'android')   # the APK stays the default
        a = cli._parser().parse_args(['port', 'x', '--platform', 'mac-app', '--allow-other-metal'])
        self.assertEqual((a.platform, a.allow_other_metal), ('mac-app', True))
        self.assertTrue(pipeline.Port(pipeline.Options(folder=Path('x'), platform='mac')).mac)   # 'mac' still reaches run_mac (upstream's own name for a Mac-only build)
        port = pipeline.Port(pipeline.Options(folder=Path('x'), platform=a.platform, allow_other_metal=a.allow_other_metal))
        self.assertTrue(port.mac); self.assertFalse(pipeline.Port(pipeline.Options(folder=Path('x'))).mac)
        port.mac_options()   # nothing to refuse

    def test_flags_a_mac_app_cannot_take(self):   # refused before a tool is probed, each naming the Mac's own way to that setting
        from porter.upstream import BuildError
        for kw, says in (({'install': True}, 'Finder'), ({'device': 'HA2M2W71'}, 'Finder'), ({'replace_signer': True}, 'Finder'), ({'fps60': True}, 'Frame rate'),
                         ({'debug': True}, 'release build'), ({'package': 'org.nx2a.t1'}, 'own bundle'), ({'tool_device': 'any'}, 'Mac host')):
            with self.subTest(**kw):
                port = pipeline.Port(pipeline.Options(folder=Path('x'), platform='mac-app', **kw))
                with self.assertRaises(BuildError) as e: port.mac_options()
                self.assertIn(says, str(e.exception))

    def test_allow_other_metal_arms_upstream_switch(self):   # dmsh_chain.lock pins Apple's Metal compiler; --allow-other-metal is upstream's escape hatch
        from unittest import mock
        port = pipeline.Port(pipeline.Options(folder=Path('x'), platform='mac-app', allow_other_metal=True))
        with mock.patch.object(pipeline.nsp, 'ALLOW_OTHER_METAL', False):
            port.mac_options(); self.assertTrue(pipeline.nsp.ALLOW_OTHER_METAL)


class Both(unittest.TestCase):   # --platform both: one run, two targets (D-04 Android first, D-06 a failure does not stop the other, D-07/D-08 the result)
    def setUp(self):
        self.t = Path(tempfile.mkdtemp(prefix='nx2a_test_both_'))
        self.addCleanup(shutil.rmtree, self.t, True)

    def driver(self, **kw):
        """A 'both' port whose scan has already happened (begin()): the folders here hold no NSPs, so the driver's own scan is stubbed out"""
        p = pipeline.Port(pipeline.Options(folder=self.t, platform='both', keys=self.t / 'prod.keys', **kw))
        p.work, p.app, p.fam = self.t / f'{NEO}_build', int(NEO, 16), {'base': None, 'updates': [], 'dlc': []}
        return p

    def test_both_runs_android_then_mac(self):   # D-04: the order is the driver's, not the caller's; D-08: one result, targets[] beside today's flat keys
        from types import SimpleNamespace
        from unittest import mock
        p, seen = self.driver(), []
        def run(child):
            seen.append((child.o.platform, child.multi_target, child.work, child.app, child.fam))
            if child.o.platform == 'android':
                return {'apk': str(self.t / 'Game.apk'), 'data': str(self.t / 'Game-data'), 'title_id': NEO, 'name': 'Game', 'package': 'org.nx2a.neo',
                        'version': 'v0', 'display': '1.0', 'language': 'en-US', 'status': 'playable', 'derived': False, 'installed': False}
            return {'app': str(self.t / 'Game.app'), 'title_id': NEO, 'name': 'Game', 'platform': 'mac-app', 'version': 'v0', 'display': '1.0', 'language': 'en-US'}
        with mock.patch.object(pipeline, 'sys', SimpleNamespace(platform='darwin')), mock.patch.object(pipeline.Port, 'begin') as begin, \
             mock.patch.object(pipeline.Port, 'run', run), mock.patch.object(pipeline, 'say'):
            res = p.run_both()
        begin.assert_called_once_with()                                   # one scan and one lock for the run, not one per target (QUAL-13)
        self.assertEqual([r['platform'] for r in res['targets']], ['android', 'mac-app'])
        self.assertEqual([r['status'] for r in res['targets']], ['ok', 'ok'])
        self.assertEqual([r['out'] for r in res['targets']], [str(self.t / 'Game.apk'), str(self.t / 'Game.app')])
        self.assertEqual([r['reason'] for r in res['targets']], ['', ''])
        self.assertEqual(res['platform'], 'both')                          # the run's own platform, not the last child's ('mac-app')
        self.assertEqual((res['apk'], res['data'], res['app'], res['package']), (str(self.t / 'Game.apk'), str(self.t / 'Game-data'), str(self.t / 'Game.app'), 'org.nx2a.neo'))
        self.assertEqual([s[0] for s in seen], ['android', 'mac-app'])     # each child is its own target
        self.assertEqual({s[1] for s in seen}, {True})                     # multi_target: a missing profile is a skip, not a failure
        self.assertTrue(all(s[2] == p.work and s[3] == p.app and s[4] is p.fam for s in seen))   # one work folder, one scan, inherited

    def test_run_dispatches_both_to_the_driver(self):   # 'both' is a driver over two Ports, never the single-target stage sequence
        from types import SimpleNamespace
        from unittest import mock
        p = pipeline.Port(pipeline.Options(folder=self.t, platform='both', keys=self.t / 'prod.keys'))
        tools = {'ndk': Path('/ndk'), 'dotnet': Path('/dotnet'), 'adb': None, 'notes': []}
        both, apk = mock.Mock(return_value={'targets': []}), mock.Mock()
        with mock.patch.object(pipeline, 'sys', SimpleNamespace(platform='darwin')), mock.patch.object(pipeline.Port, 'run_both', both), \
             mock.patch.object(pipeline.Port, 'apk', apk), mock.patch.object(pipeline.toolchain, 'require', return_value=tools), \
             mock.patch.object(pipeline.childenv, 'dotnet', return_value={}):
            self.assertEqual(p.run(), {'targets': []})
        both.assert_called_once_with()
        apk.assert_not_called()

    def test_runlog_platform_reaches_the_event_not_the_result(self):   # D-08/RESEARCH Pattern 2: the target rides on the stage events so the GUI can key (platform, k)
        from types import SimpleNamespace
        from porter import runlog
        seen = []
        prog = SimpleNamespace(k=1, n=4, cur=None, stage=lambda name, poll=None, step='', **kw: None, end=lambda summary='', ok=True: None,
                               say=lambda msg: None, _json=lambda obj: seen.append(obj))
        unwrap = runlog._wrap(prog, SimpleNamespace(clock=lambda: '00:00:00'))
        try:
            runlog.reset(); runlog.set_platform('mac-app')
            prog._json({'ev': 'stage', 'k': 1, 'name': 'host'})
            prog._json({'ev': 'stage_end', 'k': 1, 'name': 'host'})
            prog._json({'ev': 'say', 'msg': 'not a stage event'})
            prog._json({'ev': 'result', 'apk': 'x'})
            runlog.set_platform(None)
            prog._json({'ev': 'stage', 'k': 2, 'name': 'APK'})
        finally:
            unwrap(); runlog.reset()
        self.assertEqual([e.get('platform') for e in seen], ['mac-app', 'mac-app', None, None, None])
        self.assertNotIn('platform', seen[3])   # the result carries targets[], never a platform key of its own

    def test_no_android_tsv_is_a_skip_in_a_both_run(self):   # D-07: 52 of 54 upstream profiles have no android.tsv, and the Mac app is still built
        root = Path(tempfile.mkdtemp(prefix='nx2a_test_bothprof_')); gid = '0100000000AAA000'; d = root / gid; d.mkdir()
        (d / 'game.tsv').write_text(f'title_id\t{gid}\nprogram_id\t{gid}\nname\tTest Game\nipa\tTestGame.ipa\nmodules\tmain sdk\n', encoding='utf-8')
        before = dict(os.environ); os.environ['DM_GAMES_DIR'] = str(root)
        try:
            p = self.driver(); p.app = int(gid, 16); p.multi_target = True
            with self.assertRaises(pipeline.TargetSkipped) as e: p.inputs()
            reason = str(e.exception)
            self.assertIn('Test Game', reason); self.assertIn('no android.tsv for this game', reason)
            self.assertNotIn('--experimental', reason)   # a single-target remedy: not offered as a both run's skip reason
            p.multi_target = False
            with self.assertRaises(pipeline.BuildError) as e: p.inputs()
            self.assertIs(type(e.exception), pipeline.BuildError)   # a single target keeps today's refusal, remedy and all
            self.assertIn('--experimental', str(e.exception))
        finally:
            os.environ.clear(); os.environ.update(before); shutil.rmtree(root, ignore_errors=True)

    def test_no_game_profile_is_a_skip_for_a_mac_target_too(self):   # the Mac row of a both run must not read as a failure for a game nobody supports yet
        from unittest import mock
        p = pipeline.Port(pipeline.Options(folder=self.t, platform='mac-app', keys=self.t / 'prod.keys'))
        p.work, p.app, p.fam, p.multi_target = self.t / 'b', 0x0100000000FFF000, {'base': None, 'updates': [], 'dlc': []}, True
        with mock.patch.object(pipeline.profiles, 'by_title', lambda tid: (None, None)), self.assertRaises(pipeline.TargetSkipped) as e: p.inputs()
        self.assertIn('no game profile', str(e.exception))

    def test_mac_target_is_skipped_off_macos(self):   # D-03: never a target the host cannot build, and never a failure
        from types import SimpleNamespace
        from unittest import mock
        p, built = self.driver(), []
        def run(child): built.append(child.o.platform); return {'apk': str(self.t / 'Game.apk')}
        with mock.patch.object(pipeline, 'sys', SimpleNamespace(platform='linux')), mock.patch.object(pipeline.Port, 'begin'), \
             mock.patch.object(pipeline.Port, 'run', run), mock.patch.object(pipeline, 'say'):
            res = p.run_both()
        self.assertEqual(built, ['android'])   # no Mac child was even constructed
        self.assertEqual([r['platform'] for r in res['targets']], ['android', 'mac-app'])
        self.assertEqual((res['targets'][1]['status'], res['targets'][1]['out'], res['targets'][1]['reason']), ('skipped', '', pipeline.MAC_NEEDS_MAC))
        self.assertEqual((res['targets'][0]['status'], res['apk']), ('ok', str(self.t / 'Game.apk')))

    def test_run_mac_refusal_is_the_skip_reason(self):   # D-03/D-07: the skip reason and the refusal are one sentence, so they cannot drift apart
        from types import SimpleNamespace
        from unittest import mock
        p = pipeline.Port(pipeline.Options(folder=self.t, platform='mac-app'))
        with mock.patch.object(pipeline, 'sys', SimpleNamespace(platform='linux')), self.assertRaises(pipeline.BuildError) as e: p.run_mac()
        self.assertEqual(str(e.exception), pipeline.MAC_NEEDS_MAC)

    def test_the_driver_takes_the_lock_and_a_child_does_not(self):   # QUAL-13: one lock per run; a child that took it again would refuse itself
        from unittest import mock
        p = self.driver(); p.app, p.multi_target = 0x0100000000FFF000, True   # a title with no profile: the child stops at the profile check
        with mock.patch.object(pipeline.Port, 'begin') as begin, mock.patch.object(pipeline.profiles, 'by_title', lambda tid: (None, None)), \
             self.assertRaises(pipeline.TargetSkipped):
            p.inputs()
        begin.assert_not_called()   # inputs() keeps the scan and the lock the driver took

    def test_a_failed_target_does_not_stop_the_other(self):   # D-06: a working Mac app is not discarded because the Android toolchain is unhappy
        from types import SimpleNamespace
        from unittest import mock
        p = self.driver()
        def run(child):
            if child.o.platform == 'android': raise pipeline.BuildError('the Android NDK is missing')
            return {'app': str(self.t / 'Game.app')}
        with mock.patch.object(pipeline, 'sys', SimpleNamespace(platform='darwin')), mock.patch.object(pipeline.Port, 'begin'), \
             mock.patch.object(pipeline.Port, 'run', run), mock.patch.object(pipeline, 'say'):
            res = p.run_both()
        self.assertEqual([(r['platform'], r['status']) for r in res['targets']], [('android', 'failed'), ('mac-app', 'ok')])
        self.assertEqual(res['targets'][0]['reason'], 'the Android NDK is missing')
        self.assertEqual(res['app'], str(self.t / 'Game.app'))

    def test_a_crash_is_not_a_target_failure(self):   # a TypeError must not read as 'the Mac app failed' and lose its traceback (RESEARCH Pattern 1)
        from types import SimpleNamespace
        from unittest import mock
        p = self.driver()
        def run(child): raise RuntimeError('boom')
        with mock.patch.object(pipeline, 'sys', SimpleNamespace(platform='darwin')), mock.patch.object(pipeline.Port, 'begin'), \
             mock.patch.object(pipeline.Port, 'run', run), mock.patch.object(pipeline, 'say'), self.assertRaises(RuntimeError):
            p.run_both()

    def test_both_names_both_outcomes_in_the_log(self):   # D-08: the run log says what each target did, and the [RED] line is what runlog reports
        from types import SimpleNamespace
        from unittest import mock
        said, p = [], self.driver()
        def run(child):
            if child.o.platform == 'android': return {'apk': str(self.t / 'Game.apk')}
            raise pipeline.BuildError('no Xcode here')
        with mock.patch.object(pipeline, 'sys', SimpleNamespace(platform='darwin')), mock.patch.object(pipeline.Port, 'begin'), \
             mock.patch.object(pipeline.Port, 'run', run), mock.patch.object(pipeline, 'say', said.append):
            p.run_both()
        self.assertTrue([s for s in said if s.startswith('done: ') and 'the APK built' in s and 'the Mac app failed' in s], said)
        self.assertTrue([s for s in said if s.startswith('[RED] ') and 'the Mac app failed' in s and 'no Xcode here' in s], said)

    def cmd_port_code(self, result):   # cmd_port's callback's return is the process's exit code (Pitfall 6)
        from unittest import mock
        from porter import cli
        a = cli._parser().parse_args(['port', str(self.t), '--platform', 'both', '--progress', 'json', '-k', str(self.t / 'prod.keys')])
        with mock.patch.object(pipeline.Port, 'run', lambda port: result), mock.patch.object(pipeline, 'emit_result'), \
             mock.patch.object(cli, '_with_progress', lambda mode, fn: fn() or 0):
            return cli.cmd_port(a)

    def test_exit_code_one_when_a_target_failed(self):   # T-11-01/D-06: a green exit must never hide a broken target
        code = self.cmd_port_code({'platform': 'both', 'targets': [{'platform': 'android', 'status': 'ok'}, {'platform': 'mac-app', 'status': 'failed'}]})
        self.assertEqual(code, 1)

    def test_exit_code_zero_when_none_failed(self):
        for statuses in (('ok', 'ok'), ('ok', 'skipped'), ('skipped', 'skipped')):
            with self.subTest(statuses=statuses):
                rows = [{'platform': p, 'status': s} for p, s in zip(('android', 'mac-app'), statuses)]
                self.assertEqual(self.cmd_port_code({'platform': 'both', 'targets': rows}), 0)
        self.assertEqual(self.cmd_port_code({'apk': 'x', 'data': 'y'}), 0)   # a single-target result keeps today's shape, and its 0


class Switch2(unittest.TestCase):   # a Switch 2 program is named as one, before any profile lookup or survey: no profile can port it (docs/SWITCH2.md)
    MKW = '0400C3F00006E000'

    def setUp(self):
        self.t = Path(tempfile.mkdtemp(prefix='nx2a_test_switch2_'))
        self.addCleanup(shutil.rmtree, self.t, True)

    def test_the_id_names_a_switch2_program(self):
        self.assertTrue(profiles.switch2_program(int(self.MKW, 16)))
        self.assertTrue(profiles.switch2_program(0x0400380020056000))   # Splatoon Raiders, NX2_NOTES row 80
        self.assertFalse(profiles.switch2_program(int(NEO, 16)))         # NEO: The World Ends with You, a Switch 1 title

    def test_inspect_says_switch2_not_no_profile(self):
        from unittest import mock
        fam = {'base': Path('x.nsp'), 'updates': [], 'dlc': []}
        with mock.patch.object(pipeline.nsp, 'scan_nsps', return_value=(int(self.MKW, 16), fam)):
            info = pipeline.inspect(self.t)
        self.assertTrue(info.get('switch2'))
        self.assertIn('Switch 2', info['reason'])
        self.assertNotIn('no game profile', info['reason'])   # the reason a player needs: not "unsupported", but "this is the other console's game"
        self.assertFalse(info['supported'])

    def test_a_port_refuses_it_without_asking_for_a_profile(self):   # --experimental has nothing to survey it with either
        p = pipeline.Port(pipeline.Options(folder=self.t, platform='android', keys=self.t / 'prod.keys'))
        p.work, p.app, p.fam = self.t / 'b', int(self.MKW, 16), {'base': None, 'updates': [], 'dlc': []}
        with self.assertRaises(pipeline.BuildError) as e: p.inputs()
        self.assertIn('Switch 2', str(e.exception))
        self.assertIn('nvn2_shader_census', str(e.exception))   # the tool that measures one
        self.assertNotIn('--experimental', str(e.exception))


if __name__ == '__main__':
    unittest.main()