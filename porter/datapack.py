# The data pack: everything the app reads from its files folder on the device (/sdcard/Android/data/<package>/files, front_android.c), as a folder beside the APK:
#   mods/          the rewritten code modules (patch_nso.py's outputs)
#   RomFS/         the game's files (the packed version's merged RomFS)
#   aoc/<index>/   the DLC the player has
#   shaders.dmsv   the Vulkan shaders (dm/android/tools/shader_vk.py)
#   env.txt        host switches: the game language, the DLC folder, the profile's env rows
#   settings.txt   the pause menu's first-launch defaults (the profile's setting rows); the installer never replaces the player's own
#   nx2a-data.json what the pack is: the game, the package, the version, the device features the profile requires (android.tsv requires), which the installer checks
# Beside the pack on the host only, never pushed: <name>-data.build, the build folder it was made from, whose lock `porter install` takes (D-07, D-14).
# Big trees are hard links into the extraction when the volume allows, so the pack takes no extra space; the pack is rebuilt whole when anything in it changes
# and swapped in by renaming the old one aside first (<name>-data.old), so a crash at any point leaves a working pack (HARD-07).
import json, os, shutil, time
from pathlib import Path

MANIFEST = 'nx2a-data.json'
KEEP_ON_DEVICE = ('settings.txt',)          # the player's choices win over the pack's defaults
OWNED = ('mods', 'RomFS', 'aoc')            # folders the pack owns on the device: files there that the pack lacks are stale (an older version's) and removed
SIDECAR = '.build'                          # <pack>.build beside the pack: the build folder's absolute path (D-14)


def link_or_copy(src, dst):
    dst.parent.mkdir(parents=True, exist_ok=True)
    try: os.link(src, dst)
    except OSError: shutil.copy2(src, dst)


def link_tree(src, dst):   # (files, bytes)
    n = b = 0
    for root, _, files in os.walk(src):
        for f in files:
            s = Path(root) / f
            link_or_copy(s, dst / s.relative_to(src)); n += 1; b += s.stat().st_size
    return n, b


def files_folder(package): return f'/sdcard/Android/data/{package}/files'


def build(dst, *, profile, version, display, patched, romfs, shaders, aoc=None, language='en-US', package=None, build=None, env=(), files=None, progress=None):
    romfs = Path(romfs) if romfs else romfs   # romfs.py's Path subclass answers is_file() with False; a real pathlib.Path here
    """Write the pack to dst (replacing it). profile: the AndroidProfile; package: the app's, when not the profile's; build: the build folder, named in the sidecar;
    env: more env.txt rows, after the profile's; files: {name in the pack: source} (the 60 fps memory writes, fpslock.tsv). Returns the manifest"""
    package = package or profile.package
    recover(dst)
    tmp = dst.with_name(dst.name + '.partial')
    if tmp.exists(): shutil.rmtree(tmp)
    tmp.mkdir(parents=True)
    n = b = 0
    for what, src, sub in (('the rewritten modules', patched, 'mods'), ('the RomFS', romfs, 'RomFS'), ('the DLC', aoc, 'aoc')):
        if not src: continue
        if progress: progress(what)
        if sub == 'RomFS' and src.is_file():   # upstream's RomFS image: one file the host reads in place of the folder (hle_fs.c)
            link_or_copy(src, tmp / 'RomFS.img'); n += 1; b += src.stat().st_size; continue
        dn, db = link_tree(src, tmp / sub); n += dn; b += db
    link_or_copy(shaders, tmp / 'shaders.dmsv'); n += 1; b += shaders.stat().st_size
    for name, src in (files or {}).items(): shutil.copyfile(src, tmp / name); n += 1; b += Path(src).stat().st_size
    rows = [f'# Written by nx2android\'s porter for {profile.name} ({profile.id}); KEY=VALUE per line, read by the app at launch',
            f'DM_LANG={language}']
    if aoc: rows.append(f'DM_AOC_DIR={files_folder(package)}/aoc')
    if romfs and Path(romfs).is_file(): rows.append(f'DM_ROMFS={files_folder(package)}/RomFS.img')   # the host's default is the RomFS folder beside env.txt
    rows += profile.env + list(env)
    (tmp / 'env.txt').write_text('\n'.join(rows) + '\n', encoding='utf-8', newline='\n')
    if profile.settings: (tmp / 'settings.txt').write_text(''.join(f'{k}={v}\n' for k, v in profile.settings.items()), encoding='utf-8', newline='\n')
    man = dict(title_id=profile.id, name=profile.name, package=package, version=version, display=display, language=language, requires=profile.requires,
               files=n, bytes=b, dlc=sorted(int(p.name) for p in aoc.iterdir() if p.is_dir() and p.name.isdigit()) if aoc else [], made=time.strftime('%Y-%m-%d %H:%M:%S'))
    (tmp / MANIFEST).write_text(json.dumps(man, indent=2), encoding='utf-8')
    from porter.upstream import nsp
    old = dst.with_name(dst.name + '.old')
    if old.exists(): shutil.rmtree(old)   # an earlier finished swap's leftover: recover() above already put back one that was the only pack
    if dst.exists(): dst.rename(old)      # aside, not removed: the old pack goes only once the new one is in
    nsp.swap_in(tmp, dst)                 # dst is gone, so this is the rename, with its retry while a Windows virus scanner holds a new file
    shutil.rmtree(old, ignore_errors=True)   # a leftover goes with the next build
    if build:   # the build folder whose lock `porter install` takes (D-07): beside the pack, never in it, because the pack is pushed and no host path may reach the device (D-14)
        s = dst.with_name(dst.name + SIDECAR + '.tmp'); s.write_text(str(Path(build).resolve()), encoding='utf-8'); os.replace(s, dst.with_name(dst.name + SIDECAR))
    return man


def recover(dst):   # a crash mid-swap: the old pack is aside and none is in place, so the aside copy comes back
    dst = Path(dst); old = dst.with_name(dst.name + '.old')
    if old.is_dir() and not dst.exists(): old.rename(dst)


def build_dir(dst):   # the build folder the pack's sidecar names, or None (a pack made before the sidecar, or copied without it)
    try: return Path(Path(dst).with_name(Path(dst).name + SIDECAR).read_text(encoding='utf-8').strip())
    except OSError: return None


def read_manifest(d):
    try: return json.loads((Path(d) / MANIFEST).read_text(encoding='utf-8'))
    except (OSError, ValueError): return None
