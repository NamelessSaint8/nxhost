# The Linux bundle's app menu entry (D-20): ${XDG_DATA_HOME:-~/.local/share}/applications/nx2android.desktop and its icon <user dir>/nx2android.svg, written only by
# `porter desktop-entry --install` (the wizard's offer, never on its own), pointing at the bundle's absolute executable; a second run after the bundle moved rewrites it.
# Exec is quoted per the Desktop Entry spec (exec-variables), since the folder the player unpacked into ends up in a line the desktop runs (T-03-03).
import json, os, sys, tempfile
from pathlib import Path

from porter import paths


class DesktopError(Exception):
    pass


ICON = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256" width="256" height="256">
  <rect x="8" y="8" width="240" height="240" rx="48" fill="#1f2430"/>
  <text x="128" y="160" font-family="DejaVu Sans, Arial, sans-serif" font-size="104" font-weight="bold" fill="#ffffff" text-anchor="middle">nx</text>
</svg>
'''


def _exec(exe):   # quote level: " ` $ \ backslash-escaped inside double quotes; string level: every \ doubled again (a literal \ is four); % is %%
    return '"' + ''.join('\\' + c if c in '"`$\\' else c for c in exe).replace('\\', '\\\\').replace('%', '%%') + '"'


def entry(exe, icon):
    exe, icon = str(exe), str(icon)
    if any(c in s for s in (exe, icon) for c in '\r\n'): raise DesktopError(f'cannot add {exe!r} to the app menu: its path has a line break')   # it would add keys of its own
    return (f'[Desktop Entry]\nType=Application\nName=nx2android\nComment=Port your own Switch games to Android\nExec={_exec(exe)}\nTryExec={exe}\nIcon={icon}\n'
            'Terminal=false\nCategories=Game;Utility;\n')


def target():
    return Path(os.environ.get('XDG_DATA_HOME') or Path.home() / '.local/share') / 'applications/nx2android.desktop'


def _write(p, text):   # a temp file in the same folder, then one replace: no half-written entry, and a link at p is replaced, never followed
    fd, tmp = tempfile.mkstemp(dir=p.parent, prefix='.nx2android-', suffix='.tmp')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f: f.write(text)
        os.replace(tmp, p)
    except BaseException:
        Path(tmp).unlink(missing_ok=True); raise


def install(exe):
    """{'path', 'icon', 'exec'} of the entry written for exe; DesktopError when the entry or its folder is a symlink (T-03-04: another program's link is not followed)"""
    t = target(); icon = paths.user_dir() / 'nx2android.svg'
    if t.is_symlink() or t.parent.is_symlink(): raise DesktopError(f'{t} or its folder is a symbolic link: remove it, then run desktop-entry --install again')
    text = entry(exe, icon)
    t.parent.mkdir(parents=True, exist_ok=True)
    _write(icon, ICON); _write(t, text)
    return {'path': str(t), 'icon': str(icon), 'exec': _exec(str(exe))}


def main(a):
    exe = Path(sys.executable).resolve()
    try:
        if not a.install: d = {'path': str(target()), 'exec': _exec(str(exe)), 'installed': target().is_file()}
        elif not (sys.platform.startswith('linux') and paths.FROZEN): raise DesktopError('the app menu entry is for the Linux bundle: run nx2android -m porter desktop-entry --install from it')
        else: d = install(exe)
    except (DesktopError, OSError) as e:
        if a.json: print(json.dumps({'error': str(e)}, ensure_ascii=False))
        else: print(f'[RED] {e}', file=sys.stderr)
        return 1
    if a.json: print(json.dumps(d, ensure_ascii=False, indent=2))
    else: print(f'{d["path"]}\nExec={d["exec"]}' + ('' if a.install else '\n(desktop-entry --install writes it, from the Linux bundle)'))
    return 0
