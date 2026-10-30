# nxnative's own tools, used as libraries: the NSP script's steps (scripts/build_ipa_from_nsp.py: NSP scan, extraction, rewrite, shader split, stage reuse, progress), the game profiles
# (dm/games/game.py), the guesses from game files (dm/games/profile_guess.py), the control data reader (dm/tools/nacp.py) and the Android profile (dm/android/tools/android_profile.py).
# Importing them instead of copying keeps one implementation of each step for iOS and Android; what differs on Android (the rewrite target, the Vulkan shaders, the host, the APK)
# is in porter.pipeline. What porter overrides in the NSP script is in _overrides, and an upstream rename of it fails at import, naming the attribute.
import importlib.util, sys

from porter.paths import DM, NXNATIVE

for d in (DM / 'games', DM / 'tools', DM / 'android/tools'):
    if str(d) not in sys.path: sys.path.insert(0, str(d))

import android_profile   # noqa: E402
import game              # noqa: E402
import nacp              # noqa: E402
import profile_guess     # noqa: E402


def _load_nsp():
    spec = importlib.util.spec_from_file_location('build_ipa_from_nsp', NXNATIVE / 'scripts/build_ipa_from_nsp.py')
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    _overrides(m)
    return m


def _overrides(m):
    """What porter replaces in the NSP script. Each one is checked first (raise, not assert: python -O keeps it), so an upstream rename fails here, naming the attribute"""
    if not {'nacp', 'pg'} <= set(m.main.__code__.co_names): raise AssertionError('porter.upstream._overrides: upstream main() no longer sets the globals nacp / pg')
    for k in ('can_clone', 'profile_files'):
        if not callable(getattr(m, k, None)): raise AssertionError(f'porter.upstream._overrides: upstream has no function {k}')
    m.nacp, m.pg = nacp, profile_guess   # the module globals main() would set (porter calls the helpers without main)
    if sys.platform != 'darwin': m.can_clone = lambda d: False   # APFS clones (clonefile) exist only on a Mac
    files = m.profile_files   # the shader stages' reuse keys: android.tsv changes no shader (an edit to it re-split and re-translated Viractal's 25,464 shaders)
    m.profile_files = lambda g: [p for p in files(g) if p.name != 'android.tsv']


nsp = _load_nsp()
BuildError, PROG, say = nsp.BuildError, nsp.PROG, nsp.say
