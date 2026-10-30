# NuGet pins (PKG-07, D-05 as amended 2026-10-30): the packages nx_extract and the shader translator restore are pinned in porter/pins.py NUGET by
# <id>/<version> and their content hash, the `sha512` NuGet writes into obj/project.assets.json (equal to the package's .nupkg.metadata contentHash).
# porter restores into <user dir>/nuget, compares, and stops before any build, naming the package. The content hash leaves out nuget.org's repository
# signature, so a re-signed package still passes: that is why the whole-file `.nupkg.sha512` is never compared.
import contextlib, json, shutil
from pathlib import Path

from porter import lock, paths, pins


def hashes(project):
    """{'<id>/<version>': (content hash or None, its package folder)} for every package project's last restore resolved (project references left out).
    Standard library only: devtools/nuget_pins.py uses it"""
    a = json.loads((Path(project) / 'obj/project.assets.json').read_text(encoding='utf-8'))
    folder = Path(next(iter(a['packageFolders'])))
    return {k: (v.get('sha512'), folder / v.get('path', k.lower())) for k, v in a['libraries'].items() if v.get('type') == 'package'}


def check(project):
    """Every restored package must have the pinned content hash; else its folder is removed (the next restore fetches it again) and BuildError names it"""
    bad = []
    for k, (got, d) in sorted(hashes(project).items()):
        pin = pins.NUGET.get(k)
        if got and got == pin: continue
        shutil.rmtree(d, ignore_errors=True); bad.append(f'{k} (restored {got or "none"}, pinned {pin or "nothing"})')
    if bad:
        from porter.upstream import BuildError
        raise BuildError(f'NuGet package not the pinned one: {"; ".join(bad)}: porter/pins.py NUGET')


@contextlib.contextmanager
def restored(project, dotnet, env, log):
    """with restored(...): <build>. dotnet restore of project with env (its NUGET_PACKAGES), then check(), then the body, all under the shared tools lock"""
    from porter.upstream import nsp
    # the engine's nx_extract and dmsh_xlate obj/ folders and <user dir>/tools/dmsh_xlate.partial are shared by every game's port (RESEARCH Pitfall 6)
    held = lock.take(paths.user_dir() / 'tools', 'tool build', wait=True)
    try:
        Path(log).parent.mkdir(parents=True, exist_ok=True)
        nsp.run([str(dotnet), 'restore', str(project), '--nologo', '-v', 'quiet'], log, env=env)
        check(project)
        yield
    finally: held.close()
