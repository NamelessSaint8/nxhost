# The command line (python -m porter …). Every command the GUI uses is here, so a port runs the same headless. Exit codes: 0 done, 1 error, 130 interrupted.
import argparse, json, os, sys
from pathlib import Path


def _parser():
    ap = argparse.ArgumentParser(prog='porter', description='Port your own Switch game files to an Android app (docs/ARCHITECTURE.md).')
    sub = ap.add_subparsers(dest='cmd', required=True)
    d = sub.add_parser('doctor', help='check the tools a port needs'); d.add_argument('--json', action='store_true'); d.add_argument('-k', '--keys')
    p = sub.add_parser('profiles', help='list the games the tool can port'); p.add_argument('--all', action='store_true', help='also the iOS profiles not ported to Android'); p.add_argument('--json', action='store_true')
    i = sub.add_parser('inspect', help='what a game folder holds and whether it can be ported'); i.add_argument('folder'); i.add_argument('--title-id', default='', help='the game to look at when the folder holds several'); i.add_argument('--json', action='store_true')
    tr = sub.add_parser('triage', help='boot a built game on a device N times and read every log (the bring-up loop)')
    tr.add_argument('folder', help='the game folder (its <title ID>_build is what gets booted)')
    tr.add_argument('--device', default='', help="an adb serial, or '' for the first attached")
    tr.add_argument('--runs', type=int, default=3)
    tr.add_argument('--secs', type=int, default=45)
    tr.add_argument('--title-id', default='')
    tr.add_argument('--json', action='store_true')
    tr.set_defaults(func=cmd_triage)
    po = sub.add_parser('port', help='make the APK and the data pack (and install them), or with --platform mac-app a Mac app')
    po.add_argument('folder', help='the game\'s folder: its base game NSP / XCI, updates and DLC')
    po.add_argument('-k', '--keys', help='prod.keys (default: the configured one)')
    po.add_argument('-o', '--out', help='folder for the APK and the data pack (default: the game folder); with --platform mac-app, the .app or the folder it goes in')
    po.add_argument('--platform', choices=('android', 'mac-app', 'both'), default='android',
                    help='android = the APK and the data pack; mac-app = a double-clickable Mac app built on this Mac with Xcode (dm/mac/pack_app.py), ad-hoc signed; '
                         'both = the APK and the Mac app in one run, Android first (a Mac app needs a Mac)')
    po.add_argument('-p', '--version', default='', help='version to pack, v<N> (default: the newest in the folder)')
    po.add_argument('-l', '--language', default='', help='game language, a code or a name (default: English)')
    po.add_argument('--app-name', default='', help='the app\'s name on the device (default: the game\'s name)')
    po.add_argument('--install', action='store_true', help='install on the connected device afterwards')
    po.add_argument('--device', default='', help='adb serial of the device to install on')
    po.add_argument('--replace-signer', action='store_true', help='uninstall an app of the same package signed with another key first (deletes its saves)')
    po.add_argument('--debug', action='store_true', help='a development build: debug information, debuggable, DM_CTL key presses')
    po.add_argument('--experimental', action='store_true', help='try a game not ported to Android yet (a profile guessed from a survey of its files; it may not start)')
    po.add_argument('--package', default='', help="the app's package instead of the profile's (a test install beside another build of the game)")
    po.add_argument('--fps60', action='store_true', help='60 fps: the profile\'s own frame-rate cap, else the community\'s FPSLocker-Warehouse config of the game\'s build, fetched from GitHub')
    po.add_argument('--title-id', default='', help='the game to port when the folder holds several, e.g. a cartridge dump with two games')
    po.add_argument('--tool-device', default='', help="run the Mac-host steps (the heap check) on an Android device instead: an adb serial, or 'any'")
    po.add_argument('--allow-other-metal', action='store_true', help='--platform mac-app: build the Metal shaders with this Mac\'s compiler even when it is not the one dmsh_chain.lock pins (untested)')
    po.add_argument('--jobs', type=int, default=os.cpu_count() or 8)
    po.add_argument('--progress', default='auto', choices=('auto', 'bar', 'lines', 'json', 'off'), help='json: one JSON event per line, for the GUI')
    ins = sub.add_parser('install', help='install a port made earlier'); ins.add_argument('data', help='the data pack folder (<App>-data)'); ins.add_argument('--apk', help='the APK (default: <App>.apk beside the pack)')
    ins.add_argument('--device', default=''); ins.add_argument('--replace-signer', action='store_true'); ins.add_argument('--progress', default='auto', choices=('auto', 'bar', 'lines', 'json', 'off'))
    dv = sub.add_parser('devices', help='the devices adb sees'); dv.add_argument('--json', action='store_true')
    t = sub.add_parser('tools', help='list, or download, the missing tools (Android NDK, .NET SDK, platform-tools) from Google and Microsoft')
    t.add_argument('--download', action='store_true', help='download and unpack them into the nx2android folder (you accept their licenses)')
    t.add_argument('--prepare', action='store_true', help='restore the .NET tools\' NuGet packages, check them against the pins and build the shader translator and nx_extract once, so the first port finds them ready')
    t.add_argument('--only', default='', help='these instead of the missing ones: ndk, dotnet, adb (comma-separated)'); t.add_argument('--json', action='store_true')
    t.add_argument('--progress', default='auto', choices=('auto', 'bar', 'lines', 'json', 'off'))
    c = sub.add_parser('config', help='show or change the saved settings'); c.add_argument('key', nargs='?'); c.add_argument('value', nargs='?')
    c.add_argument('--json', action='store_true')
    de = sub.add_parser('desktop-entry', help='add the Linux bundle to the app menu (~/.local/share/applications)'); de.add_argument('--install', action='store_true'); de.add_argument('--json', action='store_true')
    su = sub.add_parser('setup', help='what setup still needs, for the first-run wizard (one JSON document with --json)'); su.add_argument('--json', action='store_true')
    return ap


def _print_json(obj): print(json.dumps(obj, ensure_ascii=False, indent=2))


def cmd_triage(a):
    from porter import triage
    r = triage.triage(a.folder, a.device, a.runs, a.secs, a.title_id)
    if a.json: _print_json(r)


def cmd_doctor(a):
    from porter import toolchain
    rows = toolchain.checks(keys=a.keys)
    if a.json: _print_json([r.as_dict() for r in rows])
    else:
        for r in rows: print(f'{"ok " if r.ok else ("!! " if r.required else "-- ")} {r.name:15} {r.detail}' + (f'\n{"":19}→ {r.fix}' if r.fix and not r.ok else ''))
    return 0 if all(r.ok or not r.required for r in rows) else 1


def cmd_setup(a):
    from porter import setup
    return setup.main(a)


def cmd_desktop(a):
    from porter import desktop
    return desktop.main(a)


def cmd_profiles(a):
    from porter import profiles
    rows = profiles.all_entries(android_only=not a.all)
    if a.json: _print_json([r.as_dict() for r in rows]); return 0
    for r in rows: print(f'{r.id}  {r.status:12} {r.name}' + (f'  ({r.tested})' if r.tested else ''))
    return 0


def cmd_inspect(a):
    from porter import pipeline
    from porter.upstream import BuildError, PROG, nacp, nsp
    if a.json: PROG._out = lambda text: print(text, file=sys.stderr, flush=True)   # the scan's narration goes to stderr: stdout stays the one JSON doc the GUI card parses whole
    try: info = pipeline.inspect(a.folder, getattr(a, 'title_id', ''))
    except BuildError as e:
        if a.json: _print_json({'error': str(e)})
        else: print(e, file=sys.stderr)
        return 2
    # D-12: one language list, upstream's; the flags come only from an extraction a port made (inspect never extracts), and no flags means every language
    x = Path(a.folder) / f'{info["title_id"]}_build/extract'; f = next((n for n in [x / str(info.get('pack')) / 'control.nacp', *sorted(x.glob('*/control.nacp'))] if n.is_file()), None)
    have = nacp.languages(f) if f else []; info['languages'] = [{'code': c, 'name': n} for c, n in nacp.LANGUAGES if not have or c in have]
    if a.json: _print_json(info); return 0 if info['supported'] else 2
    print(f'{info["title_id"]}  {info.get("name", "")}\n  base: {info["base"]}')
    for u in info['updates']: print(f'  update {u["version"]}: {u["file"]}')
    for d in info['dlc']: print(f'  DLC {d["title_id"]}: {d["file"]}')
    if info.get('pack'): print(f'  packs {info["pack"]} (versions in the folder: {", ".join(info["versions"])})')
    if info['android']: print(f'  Android: {info["android"]["status"]}' + (f', tested on {info["android"]["tested"]}' if info['android']['tested'] else ''))
    if info['reason']: print(f'  {info["reason"]}')
    if info.get('experimental'): print('  porter port --experimental tries it')
    return 0 if info['supported'] else 2


def _with_progress(mode, fn):
    from porter.upstream import BuildError, PROG, nsp
    PROG.mode = nsp.progress_mode(mode)
    environ = dict(os.environ)
    try:
        fn(); return 0
    except BuildError as e:
        PROG.close(ok=False); PROG.say(f'[RED] {e}'); return 1
    except KeyboardInterrupt:
        PROG.close(ok=False); PROG.say('[RED] interrupted'); return 130
    except Exception as e:
        PROG.close(ok=False)
        if PROG.mode == 'json': PROG.say(f'[RED] {type(e).__name__}: {e}')
        raise
    finally:
        PROG.close(ok=False)
        for k in os.environ.keys() - environ.keys(): del os.environ[k]
        os.environ.update(environ)


def cmd_port(a):
    from porter import pipeline
    opts = pipeline.Options(folder=Path(a.folder), keys=Path(a.keys) if a.keys else None, out=Path(a.out) if a.out else None, version=a.version, language=a.language,
                            app_name=a.app_name, install=a.install, device=a.device, replace_signer=a.replace_signer, debug=a.debug, experimental=a.experimental, package=a.package, fps60=a.fps60, jobs=a.jobs, title_id=a.title_id,
                            tool_device=getattr(a, 'tool_device', ''), platform=getattr(a, 'platform', 'android'), allow_other_metal=getattr(a, 'allow_other_metal', False))
    return _with_progress(a.progress, lambda: pipeline.emit_result(pipeline.Port(opts).run()))


def cmd_install(a):
    from porter import config, datapack, install, lock, toolchain
    from porter.upstream import BuildError, PROG
    def go():
        data = Path(a.data).resolve()
        datapack.recover(data)   # HARD-07: a pack a crash left aside is put back before it is read
        b = datapack.build_dir(data); held = lock.take(b, 'install') if b and b.is_dir() else None   # D-07: the port's lock, on the folder the pack's sidecar names (D-14)
        apk = Path(a.apk) if a.apk else data.with_name(data.name.removesuffix('-data') + '.apk')
        PROG.plan(1)
        cfg = config.load()
        install.install(apk, data, toolchain.find_adb(cfg), a.device or cfg.get('device'), replace_signer=a.replace_signer)
    return _with_progress(a.progress, go)


def cmd_devices(a):
    from porter import config, distro, toolchain
    from porter.adb import Adb
    exe = toolchain.find_adb()
    if not exe and a.json: _print_json({'error': 'adb not found: ' + distro.adb_hint()}); return 1
    if not exe: print('adb not found', file=sys.stderr); return 1
    # detail: adb's own state text, which testers quote; state: its kind ('no permissions' for that family)
    rows = [{'serial': s, 'state': distro.state_kind(st), 'info': d, 'detail': st, 'fix': distro.device_fix(st)} for s, st, d in Adb(exe).devices()]
    if a.json: _print_json(rows); return 0
    for r in rows: print(f"{r['serial']}\t{r['detail']}\t{r['info']}" + (f"\n  {r['fix']}" if r['fix'] else ''))
    if not rows: print('no device')
    return 0


def cmd_tools(a):
    from porter import fetch
    from porter.upstream import BuildError
    known = {'ndk': 'Android NDK', 'dotnet': '.NET SDK', 'adb': 'adb'}; given = [n.strip() for n in a.only.split(',') if n.strip()]
    if bad := [n for n in given if n not in known]:
        msg = f'unknown tool {", ".join(bad)}: --only takes ndk, dotnet, adb'
        _print_json({'error': msg}) if a.json else print(msg, file=sys.stderr); return 2
    names = [known[n] for n in given] or None
    if a.prepare: from porter import prepare; return _with_progress(a.progress, prepare.run)
    if a.download:
        def go():
            items = fetch.plan(names)
            if not items: fetch.PROG.say('nothing to download: every tool is there'); return
            for it in items: fetch.PROG.say(f'{it.name} {it.version} ({it.size / 2**20:,.0f} MB) from {it.url}, license: {it.license}')
            fetch.download(items)
        return _with_progress(a.progress, go)
    try: items = fetch.plan(names)
    except (BuildError, OSError) as e: print(f'cannot read the download lists: {e}', file=sys.stderr); return 1
    if a.json: _print_json([it.as_dict() for it in items]); return 0
    for it in items: print(f'{it.name:12} {it.version:16} {it.size / 2**20:8,.0f} MB  {it.url}\n{"":12} license: {it.license}')
    print('porter tools --download fetches them' if items else 'nothing to download: every tool is there')
    return 0


def cmd_config(a):
    from porter import config
    if a.key is None:
        if a.json: _print_json(config.load()); return 0
        for k, v in config.load().items(): print(f'{k:9} {v or "-":40}  {config.KEYS[k]}')
        print(f'({config.path()})'); return 0
    if not a.json:
        if a.value is None: print(config.load().get(a.key, '')); return 0
        try: config.set_value(a.key, a.value)
        except KeyError as e: print(e.args[0], file=sys.stderr); return 1
        return 0
    from porter import setup
    if a.key not in config.KEYS: _print_json({'error': f'unknown setting {a.key!r}: one of {", ".join(config.KEYS)}'}); return 1
    if a.value is None: _print_json({'key': a.key, 'value': config.load()[a.key]}); return 0
    # T-03-05: the notice is accepted only at the version setup --json shows, so a stale or made-up value never reads as accepted
    if a.key == 'legal' and a.value != str(setup.VERSION): _print_json({'error': f'legal takes the current notice version, {setup.VERSION} (porter setup shows the notice)'}); return 1
    config.set_value(a.key, a.value); _print_json({'key': a.key, 'value': a.value}); return 0


def main(argv):
    if hasattr(sys.stdout, 'reconfigure'): sys.stdout.reconfigure(encoding='utf-8', errors='replace')   # game names and progress bars on a Windows console
    a = _parser().parse_args(argv)
    from porter import runlog
    return runlog.run(a, {'doctor': cmd_doctor, 'profiles': cmd_profiles, 'inspect': cmd_inspect, 'triage': cmd_triage, 'port': cmd_port, 'install': cmd_install, 'devices': cmd_devices, 'tools': cmd_tools, 'config': cmd_config, 'setup': cmd_setup, 'desktop-entry': cmd_desktop}[a.cmd])
