# Downloading the toolchains a port needs, for a player who has none (`porter tools --download`, the Setup tab's Download button): the files pinned in
# porter/pins.py (Android NDK r27c and platform-tools from Google, the community r27c build on Linux arm64, the .NET SDK 10 from Microsoft), each checked against its
# pinned hash; Linux arm64 gets no platform-tools (Google ships none: the distribution's adb). When a vendor no longer
# serves a pinned file (404/410), platform-tools and .NET take the vendor's newest (same .NET major) checked against the vendor's listed hash, marked untested;
# the NDK never falls back. Then unpacked into the player's nx2android folder (paths.player_tools()), where toolchain.find_* look, and the settings point at it.
# The tool ships none of them: they come from their makers, under their licenses (LICENSES).
import hashlib, json, os, platform, shutil, stat, sys, tarfile, urllib.error, urllib.request, xml.etree.ElementTree as ET, zipfile
from dataclasses import dataclass
from pathlib import Path

from porter import config, hosttools, pins, toolchain, tls
from porter.paths import player_tools
from porter.upstream import BuildError, PROG

GOOGLE = 'https://dl.google.com/android/repository/'
GOOGLE_INDEX = GOOGLE + 'repository2-3.xml'   # what sdkmanager reads: every package's archives, sizes and SHA-1 per host OS
DOTNET_INDEX = f'https://builds.dotnet.microsoft.com/dotnet/release-metadata/{toolchain.DOTNET_MAJOR}.0/releases.json'   # every release's files with SHA-512
LICENSES = {'Android NDK': 'https://developer.android.com/studio/terms', 'adb': 'https://developer.android.com/studio/terms',
            '.NET SDK': 'https://github.com/dotnet/core/blob/main/license-information.md'}
NDK_PACKAGE = f'ndk;{toolchain.NDK_REVISION}'
FOLDERS = {'Android NDK': f'android-ndk-{toolchain.NDK_RELEASE}', 'adb': 'platform-tools', '.NET SDK': 'dotnet'}   # under player_tools()
UNPACKED = {'Android NDK': 2.6 * 2**30, '.NET SDK': 0.9 * 2**30, 'adb': 0.05 * 2**30}   # disk space unpacked (r27c on Windows: 2.5 GB), for the free-space check


@dataclass
class Item:
    name: str      # the doctor's row: 'Android NDK', '.NET SDK', 'adb'
    version: str
    url: str
    size: int
    hash: str
    algo: str      # 'sha1' / 'sha256' / 'sha512'
    folder: str    # under player_tools(): android-ndk-r27c, dotnet, platform-tools
    license: str
    untested: bool = False   # not the pinned file: the vendor's newest, or a host with no pinned row

    def as_dict(self): return dict(self.__dict__)


def _get(url, timeout=60):
    with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'nx2android'}), timeout=timeout, context=tls.context()) as r: return r.read()


def _head(url):   # the size a HEAD gives (0 when the server names none); a gone file raises HTTPError
    with urllib.request.urlopen(urllib.request.Request(url, method='HEAD', headers={'User-Agent': 'nx2android'}), timeout=60, context=tls.context()) as r: return int(r.headers.get('Content-Length') or 0)


def _google_os(): return {'win32': 'windows', 'darwin': 'macosx'}.get(sys.platform, 'linux')


def _ndk_host(): return 'linux-arm64' if hosttools.linux_arm64() else _google_os()   # pins.NDK's row: the community build on Linux arm64 (D-08)


def _dotnet_rid():
    os_ = {'win32': 'win', 'darwin': 'osx'}.get(sys.platform, 'linux')
    return f'{os_}-{"arm64" if platform.machine().lower() in ("arm64", "aarch64") else "x64"}'


def _google(index, path, name, folder):
    """The archive of SDK package `path` for this OS in Google's index"""
    for p in index.iter('remotePackage'):
        if p.get('path') != path: continue
        rev = p.find('revision'); version = '.'.join(rev.findtext(k) for k in ('major', 'minor', 'micro') if rev.findtext(k) is not None)
        for a in p.iter('archive'):
            if a.findtext('host-os') not in (None, _google_os()): continue
            c = a.find('complete')
            return Item(name, version, GOOGLE + c.findtext('url'), int(c.findtext('size')), c.findtext('checksum'), c.find('checksum').get('type', 'sha1'), folder, LICENSES[name])
    raise BuildError(f'{path} for {_google_os()} is not in Google\'s SDK repository ({GOOGLE_INDEX})')


def _dotnet():
    """The newest .NET SDK of the major the port builds with, for this OS and CPU"""
    rel = json.loads(_get(DOTNET_INDEX))
    rid, kind = _dotnet_rid(), ('.zip' if sys.platform == 'win32' else '.tar.gz')
    for r in rel['releases']:   # newest first
        for sdk in [r.get('sdk')] + r.get('sdks', []):
            for f in (sdk or {}).get('files', []):
                if f.get('rid') == rid and f['name'] == f'dotnet-sdk-{rid}{kind}':
                    return Item('.NET SDK', sdk['version'], f['url'], 0, f['hash'], 'sha512', 'dotnet', LICENSES['.NET SDK'])
    raise BuildError(f'no .NET SDK {toolchain.DOTNET_MAJOR} for {rid} in {DOTNET_INDEX}')


def _pinned(name):
    """(version, url, size, algo, hash) of the pinned file for this host, or None: no row (the index path, untested)"""
    pin, host = {'Android NDK': (pins.NDK, _ndk_host()), 'adb': (pins.PLATFORM_TOOLS, _google_os()), '.NET SDK': (pins.DOTNET, _dotnet_rid())}[name]
    row = pin['files'].get(host)
    return (pin['version'], *row) if row else None


def missing(cfg=None):
    """The doctor's rows a download can fix: NDK r27c, .NET SDK 10, adb (not on Linux arm64: the setup row shows the distribution's install command, D-25)"""
    rows = {r.name: r for r in toolchain.checks(cfg)}
    return [n for n in ('Android NDK', '.NET SDK', 'adb') if not rows[n].ok and not (n == 'adb' and hosttools.linux_arm64())]


def plan(names=None):
    """The Items to download: the missing tools (or `names`), with their sizes. The pinned file first; the vendor's newest only when it is gone, marked untested"""
    names = missing() if names is None else names
    if 'adb' in names and hosttools.linux_arm64():   # Google's linux platform-tools are x86-64 only
        raise BuildError("Google ships no Android platform-tools for Linux arm64: install your distribution's adb package (Setup shows the command), then check again")
    out, index = [], None
    for n in names:
        if p := _pinned(n):
            v, url, size, algo, h = p
            try: out.append(Item(n, v, url, _head(url) or size, h, algo, FOLDERS[n], LICENSES[n])); continue
            except urllib.error.HTTPError as e:
                if e.code not in (404, 410): raise   # gone is not a mismatch; any other answer stops as before
                if n == 'Android NDK': raise BuildError(f'NDK {toolchain.NDK_RELEASE} is no longer served at {url}: install it yourself (developer.android.com/ndk/downloads) and set its folder') from e
        if n in ('Android NDK', 'adb') and index is None: index = ET.fromstring(_get(GOOGLE_INDEX))
        it = _dotnet() if n == '.NET SDK' else _google(index, NDK_PACKAGE if n == 'Android NDK' else 'platform-tools', n, FOLDERS[n])
        it.untested = True; out.append(it)   # checked against the vendor's own listed hash
    for it in out:
        if not it.size: it.size = _head(it.url)
    return out


def _download(it, dest, retries=3):
    """To dest through dest.part, hashing as it goes (D-21, D-22); a body that ends before its announced length is a dropped link. A .part already there (a dropped link, a Cancel, a restart) is hashed first and the rest asked
    for with Range; only a 206 whose Content-Range starts at its size is appended to, so no other range is ever spliced in. A dropped link is retried, logged;
    KeyboardInterrupt (Cancel) is never caught, so the .part stays for the next run. A wrong final hash deletes the .part and stops"""
    part, name, failed = dest.with_suffix(dest.suffix + '.part'), Path(it.url).name, 0
    while True:
        have = part.stat().st_size if part.exists() else 0; h = hashlib.new(it.algo)
        if have:
            PROG.set(step='checking', done=0, total=have, unit='B')
            with open(part, 'rb') as f:
                while b := f.read(1 << 20): h.update(b)
        hdr = {'User-Agent': 'nx2android', **({'Range': f'bytes={have}-'} if have else {})}
        try:
            with urllib.request.urlopen(urllib.request.Request(it.url, headers=hdr), timeout=120, context=tls.context()) as r:
                st = getattr(r, 'status', 200)
                if have and not (st == 206 and (r.headers.get('Content-Range') or '').startswith(f'bytes {have}-')):
                    if st == 206: part.unlink(); continue   # another range than asked: asked again whole, never spliced
                    have = 0; h = hashlib.new(it.algo)   # the server ignored Range: this answer is the whole file
                end = have + int(n) if (n := r.headers.get('Content-Length')) else None   # None for a chunked answer
                PROG.set(step='downloading', done=have, total=end or it.size or None, unit='B')
                with open(part, 'ab' if have else 'wb') as f:
                    while chunk := r.read(1 << 20): f.write(chunk); h.update(chunk); have += len(chunk); PROG.set(done=have)
                # read() gives b'' on a clean close before Content-Length: 03-VERIFICATION gap 2, 300 of 1000 bytes made one request, a hash error, the .part deleted
                if end and have < end: raise ConnectionResetError(f'the server closed the link at {have} of {end} bytes')
            break
        except urllib.error.HTTPError as e:
            if e.code != 416 or not have: raise
            break   # 416: the .part is whole already (or longer): the hash decides
        except (urllib.error.URLError, OSError, TimeoutError) as e:
            failed += 1
            if failed >= retries: raise
            PROG.say(f'{name}: {e}, retry {failed}')   # explicit and logged, like Adb.run
    if (got := h.hexdigest().lower()) != it.hash.lower():
        part.unlink(missing_ok=True)
        fix = 'wait for a pin bump of porter/pins.py, or point Setup at your own NDK (Use my own…)' if it.name == 'Android NDK' else 'try again, and report it if it repeats'
        raise BuildError(f'{name}: its {it.algo} is {got}, not the expected {it.hash} (from {it.url}): {fix}')
    part.replace(dest)


def _bad_name(n):   # absolute, a drive, a backslash or a .. part: refused before anything is written
    return n.startswith('/') or '\\' in n or ':' in n.split('/', 1)[0] or '..' in n.split('/')


def _refuse_names(arc, names):
    if bad := next((n for n in names if _bad_name(n)), None): raise BuildError(f'{arc.name}: refused, member {bad} would land outside the unpack folder')


def _parts(n): return [p for p in n.split('/') if p not in ('', '.')]   # a member name's or link target's components: tar names start with ./, and the first is . itself


def _top(names, folder):   # the one folder an archive is installed from, '' for none: its single top folder, never stripped for .NET (the archive is the folder)
    ps = [p for p in map(_parts, names) if p]; firsts = {p[0] for p in ps}
    return firsts.pop() if len(firsts) == 1 and folder != 'dotnet' and any(len(p) > 1 for p in ps) else ''


def _link_refusal(names, links, top):
    """Why the archive's links cannot be installed, or None. names: every member name; links: each link member's name -> its target. Every link is resolved in memory,
    component by component, from the folder that is installed (the archive root less top), through any link it passes; the disk is never read, so member order (CR-01),
    the move on install (CR-04) and Python's own loop handling (IN-06) cannot change the answer"""
    for n, t in links.items():
        # the default macOS volume is case-insensitive: names are compared casefolded, and that matches the disk only for plain ASCII
        if not t or not _parts(n) or not (n + t).isascii() or not (n + t).isprintable(): return f'link {n} → {t!r} is not a plain ASCII path'
        if t.startswith('/'): return f'link {n} → {t} leaves the installed folder'
    full = lambda m: '/'.join(_parts(m)).casefold(); count, under = {}, {}
    for m in names:
        f = full(m); count[f] = count.get(f, 0) + 1; ps = f.split('/')
        for k in range(1, len(ps)): under.setdefault('/'.join(ps[:k]), m)
    for n in links:   # so links last is safe: no member is written through a link, and no link's folder passes through one
        if count[full(n)] > 1: return f'link {n} shares its name with another member'
        if full(n) in under: return f'member {under[full(n)]} is under link {n}'
    s = 1 if top else 0
    R = {'/'.join(_parts(n)[s:]): t for n, t in links.items()}; F = {k.casefold(): k for k in R}
    for n, t in links.items():
        stack, work, hops = _parts(n)[s:-1], _parts(t), 0
        while work:
            c = work.pop(0)
            if c == '..':
                if not stack: return f'link {n} → {t} leaves the installed folder'
                stack.pop(); continue
            p = '/'.join(stack + [c])
            if p in R:   # 40 is Linux's MAXSYMLINKS; Path.resolve raised RuntimeError for a loop on 3.11/3.12 and accepted it on 3.13+ (IN-06)
                hops += 1
                if hops > 40: return f'link {n} → {t} runs through more than 40 links (a loop)'
                work[:0] = _parts(R[p])   # relative to that link's folder, which is the stack
            elif p.casefold() in F: return f'link {n} → {t} names link {F[p.casefold()]} in another case'
            else: stack.append(c)
    return None


def _unzip(arc, into, folder):   # zipfile drops Unix modes and symlinks; the NDK and platform-tools need both outside Windows. Returns the folder to install
    with zipfile.ZipFile(arc) as z:
        infos = z.infolist(); PROG.set(step='unpacking', done=0, total=len(infos), unit='files')
        names = [i.filename for i in infos]; _refuse_names(arc, names)
        links = {i.filename: z.read(i).decode('utf-8', 'replace') for i in infos if stat.S_ISLNK(i.external_attr >> 16)}   # every OS: a bad byte is a refusal, not a crash
        top = _top(names, folder)
        if reason := _link_refusal(names, links, top): raise BuildError(f'{arc.name}: refused, {reason}')
        link = lambda i: os.name != 'nt' and stat.S_ISLNK(i.external_attr >> 16)   # Windows writes a link as a plain file holding its target
        for k, info in enumerate(i for i in infos if not link(i)):
            mode = info.external_attr >> 16; p = Path(z.extract(info, into))
            if os.name != 'nt' and mode & 0o777 and not info.is_dir(): p.chmod(mode & 0o777)
            if k % 200 == 0: PROG.set(done=k)
        for info in filter(link, infos):   # links last, after every file: no file is ever written through a link
            t = into / info.filename; t.parent.mkdir(parents=True, exist_ok=True); os.symlink(links[info.filename], t)
    return into / top


def _untar(arc, into, folder):   # the data filter, always: its bypasses fixed in 3.11.13 / 3.12.11 / 3.13.4 are why porter refuses older Pythons (runlog.run)
    with tarfile.open(arc) as t:
        PROG.set(step='unpacking'); ms = t.getmembers(); names = [m.name for m in ms]
        _refuse_names(arc, names)   # the filter would strip a leading / and go on: the whole archive is refused instead
        top = _top(names, folder)
        # symlinks get the zip rule; hard links stay with the data filter (a hard link shares content and points nowhere once made)
        if reason := _link_refusal(names, {m.name: m.linkname for m in ms if m.issym()}, top): raise BuildError(f'{arc.name}: refused, {reason}')
        try: t.extractall(into, filter='data')
        except tarfile.FilterError as e: raise BuildError(f'{arc.name}: refused, {e}') from e
    return into / top


def _install(it, arc):
    """Unpack arc into player_tools()/it.folder: the folder installed is the one _unzip / _untar name from the archive's members (its single top folder, the NDK
    and platform-tools, or the whole archive for .NET). A refused or failed unpack removes its partial .unpack folder; a toolchain already there is moved aside
    and put back if the new one cannot be moved in"""
    root = player_tools(); tmp, dest = root / f'.{it.folder}.unpack', root / it.folder
    old = root / f'.{it.folder}.old'   # dot-named like .unpack, so toolchain.find_ndk's android-ndk-* glob never takes a half-swapped copy
    if old.exists() and not dest.exists(): old.replace(dest)   # a move cut off between its two renames last time
    shutil.rmtree(tmp, ignore_errors=True); shutil.rmtree(old, ignore_errors=True); tmp.mkdir(parents=True)
    try:
        src = (_unzip if arc.suffix == '.zip' else _untar)(arc, tmp, it.folder)
        if dest.exists(): dest.replace(old)   # WR-05: a rename instead of a delete; a file in use on Windows fails the rename, and the old toolchain stays whole
        try: src.replace(dest)
        except BaseException:
            if old.exists(): old.replace(dest)
            raise
    except BaseException: shutil.rmtree(tmp, ignore_errors=True); raise
    shutil.rmtree(tmp, ignore_errors=True); shutil.rmtree(old, ignore_errors=True)
    return dest


def download(items):
    """Download, check and unpack every Item; the settings then point at them. One stage per tool"""
    root = player_tools(); root.mkdir(parents=True, exist_ok=True)
    keep = {Path(it.url).name + '.part' for it in items}
    for p in root.glob('*.part'):   # another archive's leftover (a pin bump): this run's own parts stay for their resume
        if p.name not in keep: p.unlink(missing_ok=True)
    need = sum(it.size + UNPACKED.get(it.name, 0) for it in items); free = shutil.disk_usage(root).free
    if free < need: raise BuildError(f'{need / 2**30:.1f} GB needed in {root} (drive {root.anchor}) for the tools, {free / 2**30:.1f} GB free there: '
                                     'free some space, or point NX2A_HOME or Use my own… elsewhere')
    PROG.plan(len(items))
    keys = {'Android NDK': ('ndk', ''), '.NET SDK': ('dotnet', f'dotnet{toolchain.EXE}'), 'adb': ('adb', f'adb{toolchain.EXE}')}
    for it in items:
        if it.untested: PROG.say(f'[RED] {it.name} {it.version} is not the version porter pins (porter/pins.py): untested')
        PROG.stage(f'{it.name} {it.version}', step='downloading')
        arc = root / Path(it.url).name
        try:
            _download(it, arc); dest = _install(it, arc)
        finally: arc.unlink(missing_ok=True)
        key, exe = keys[it.name]
        config.set_value(key, str(dest / exe) if exe else str(dest))
        PROG.end(str(dest))
    PROG.close()
    bad = [n for n in missing() if n in {it.name for it in items}]
    if bad: raise BuildError('downloaded, but the check still fails for: ' + ', '.join(bad) + ' (porter doctor says why)')
