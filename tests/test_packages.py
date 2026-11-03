# The container matrix (M1): hand-made packages for scan_nsps / nsp_versions / pick_nsps — every dump variation a player's folder can hold, without game data or keys.
# The scan reads only package magic, PFS0 file names (a <rights id>.tik names the title) and the file names' [title ID] / [vN] tags, so a package fixture is its header.
# The meta-NCA reader (from_package / contents_of, nx_extract --title / --contents behind it) is stubbed: these tests cover the scan's semantics, not LibHac's crypto.
import struct, sys, tempfile, unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
from porter import upstream   # upstream.nsp is the NSP script module (porter/upstream.py loads it)   # noqa: E402

BASE, UPD = 0x010074F013262000, 0x010074F013262800


def nsp(path, ticket=None, files=()):   # a minimal NSP (header only)
    """A minimal NSP: a PFS0 whose file names are all the scan reads (a ticket's name is the rights ID, whose first 16 digits are the title ID). No NCA data."""
    names = [f'{ticket}.tik'] if ticket else list(files)
    strs, ents = b'', []
    for n in names: ents.append(struct.pack('<QQII', 0, 0, len(strs), 0)); strs += n.encode() + b'\0'
    path.write_bytes(b'PFS0' + struct.pack('<III', len(ents), len(strs), 0) + b''.join(ents) + strs)
    return path


def xci(path, ticket=None):
    """A minimal XCI: HEAD at 0x100 is what is_package looks for (its secure partition holds the game's files; the scan does not go in)."""
    path.write_bytes(b'\0' * 0x100 + b'HEAD' + b'\0' * 32)
    return path


class Matrix(unittest.TestCase):
    def setUp(self):
        self.t = Path(tempfile.mkdtemp(prefix='nx2a_pkgs_')); self.addCleanup(lambda: __import__('shutil').rmtree(self.t, ignore_errors=True))

    def scan(self, *names, from_package=None, contents_of=None, want=None):
        return upstream.nsp.scan_nsps(self.t, from_package, contents_of, want)

    def test_tagged_base_and_updates(self):
        nsp(self.t / 'Game [010074F013262000][v0].nsp'); nsp(self.t / 'Game [010074F013262800][v65536].nsp'); nsp(self.t / 'Game [010074F013262800][v131072].nsp')
        app, fam = self.scan()
        self.assertEqual(app, BASE); self.assertIs(fam['base'], None or fam['base'])   # the base is keyed by name below
        self.assertEqual(sorted(v for v, _ in fam['updates']), [65536, 131072])   # the folder order, not the version order
        self.assertEqual(upstream.nsp.nsp_versions(fam, ['v0', 'v65536'])['v65536'], fam['updates'][1][1])   # the folder's alphabetical order puts v131072 first

    def test_ticket_names_untagged(self):
        nsp(self.t / 'base.nsp', ticket=f'{BASE:016x}0000000000000000'); nsp(self.t / 'upd.nsp', ticket=f'{UPD:016x}0000000000000000')
        app, fam = self.scan()
        self.assertEqual(app, BASE)
        self.assertEqual([(v, p.name) for v, p in fam['updates']], [(None, 'upd.nsp')])
        self.assertEqual(upstream.nsp.nsp_versions(fam, ['v0', 'v65536']), {'v0': None, 'v65536': self.t / 'upd.nsp'})   # one loose update = the profile's newest

    def test_meta_names_untagged_and_versions(self):
        nsp(self.t / 'base.nsp'); nsp(self.t / 'upd.nsp')
        meta = {str(self.t / 'base.nsp'): (BASE, None), str(self.t / 'upd.nsp'): (UPD, 262144)}
        app, fam = self.scan(from_package=lambda p: meta.get(str(p)))
        self.assertEqual(app, BASE)
        self.assertEqual([(v, p.name) for v, p in fam['updates']], [(262144, 'upd.nsp')])   # the meta NCA's version, no [vN] tag needed
        self.assertEqual(upstream.nsp.nsp_versions(fam, []), {'v0': None, 'v262144': self.t / 'upd.nsp'})

    def test_meta_version_beats_a_wrong_tag(self):
        nsp(self.t / 'base [010074F013262000][v0].nsp')
        nsp(self.t / 'upd [v999].nsp')   # the tag says 999; the package's own meta NCA says 65536
        app, fam = self.scan(from_package=lambda p: (UPD, 65536) if p.name.startswith('upd') else (BASE, None))
        self.assertEqual(fam['updates'], [(65536, self.t / 'upd [v999].nsp')])

    def test_xci_base_named_by_meta(self):
        xci(self.t / 'game.xci')
        app, fam = self.scan(from_package=lambda p: (BASE, None))
        self.assertEqual((app, fam['base'], fam['updates'], fam['dlc']), (BASE, self.t / 'game.xci', [], []))

    def test_merged_package_counts_as_each(self):
        nsp(self.t / 'all-in-one.nsp', files=('base.cnmt.nca', 'upd.cnmt.nca'))   # is_merged: several content metas named inside
        cs = [('Application', BASE, 0), ('Patch', UPD, 65536), ('AddOnContent', BASE + 0x1001, 0)]
        app, fam = self.scan(contents_of=lambda p: cs)
        self.assertEqual(app, BASE); self.assertIsNotNone(fam['base'])
        self.assertEqual(fam['updates'], [(65536, self.t / 'all-in-one.nsp')])
        self.assertEqual(fam['dlc'], [(BASE + 0x1001, 0, self.t / 'all-in-one.nsp')])

    def test_dlc_index(self):
        nsp(self.t / 'dlc [010074F013263001][v0].nsp')
        with self.assertRaises(upstream.BuildError) as c: self.scan()   # a DLC alone is no game: the base is missing
        self.assertIn('no base game', str(c.exception))
        nsp(self.t / 'G [010074F013262000][v0].nsp')
        app, fam = self.scan()
        self.assertEqual(fam['dlc'], [(BASE + 0x1001, 0, self.t / 'dlc [010074F013263001][v0].nsp')])

    def test_multi_game_folder_and_want(self):
        nsp(self.t / 'G1 [0100000000010000][v0].nsp'); nsp(self.t / 'G2 [0100000000020000][v0].nsp')
        with self.assertRaises(upstream.BuildError) as c: self.scan()
        self.assertIn('0100000000010000', str(c.exception)); self.assertIn('0100000000020000', str(c.exception))
        app, fam = self.scan(want=0x0100000000020000)
        self.assertEqual(app, 0x0100000000020000)

    def test_junk_skipped(self):
        nsp(self.t / 'G [010074F013262000][v0].nsp')
        (self.t / '._G [010074F013262000][v0].nsp').write_bytes(b'junk')   # an AppleDouble file
        (self.t / 'broken.nsp').write_bytes(b'\0' * 16)                     # not a package
        (self.t / 'empty.nsp').write_bytes(b'')                             # an incomplete download
        app, fam = self.scan()
        self.assertEqual(app, BASE)

    def test_nsz_beside_its_nsp_skipped(self):
        nsp(self.t / 'G [010074F013262000][v0].nsp'); (self.t / 'G [010074F013262000][v0].nsz').write_bytes(b'whatever')
        app, fam = self.scan()
        self.assertEqual(fam['base'], self.t / 'G [010074F013262000][v0].nsp')

    def test_no_base_refused(self):
        nsp(self.t / 'upd [010074F013262800][v65536].nsp')
        with self.assertRaises(upstream.BuildError) as c: self.scan()
        self.assertIn('no base game', str(c.exception))


if __name__ == '__main__': unittest.main()
