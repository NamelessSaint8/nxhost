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


if __name__ == '__main__':
    unittest.main()
