# The games the tool knows: every game profile in nxnative/dm/games, and whether it has been ported to Android (its android.tsv, dm/android/tools/android_profile.py).
from dataclasses import dataclass, asdict

from porter.upstream import android_profile, game


@dataclass
class Entry:
    id: str
    name: str
    android: bool        # has an android.tsv
    status: str          # playable / wip / boots / experimental; 'ios only' without android.tsv
    tested: str
    package: str

    def as_dict(self): return asdict(self)


def entry(g, p):
    if p: return Entry(g.id, g.get('name', g.id), True, p.status, p.tested, p.package)
    return Entry(g.id, g.get('name', g.id), False, 'ios only', '', f'org.nx2a.t{g.id.lower()}')


def all_entries(android_only=True):
    rows = [entry(g, p) for g, p in android_profile.all_profiles()]
    return [r for r in rows if r.android or not android_only]


def by_title(tid):
    """(game profile, Android profile or None) of a base game's title ID; (None, None) when no profile matches"""
    g = game.by_title(tid)
    if not g: return None, None
    return g, (android_profile.AndroidProfile(g) if (g.dir / 'android.tsv').is_file() else None)


SWITCH2 = ('is a Switch 2 program (its id starts 0400): the port runs Switch 1 titles — the host stands in for Horizon and NVN — so this game cannot be '
           'ported yet. Its own code and shaders are Switch 2 ones (NVN2, Ampere GPU code): docs/SWITCH2.md')


def switch2_program(tid):
    """Whether a title id is a Switch 2 program's: its high byte is 04 (a Switch 1 title's is 01), e.g. Mario Kart World's 0400C3F00006E000"""
    return tid >> 56 == 0x04


def load(gid):
    """The Android profile of a game profile id (ProfileError when it has none)"""
    p = android_profile.load(gid)
    if not p: raise android_profile.ProfileError(f'{gid} has no android.tsv: it is not ported to Android')
    return p
