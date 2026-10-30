# Phase 2: Porter Hardening - Pattern Map

**Mapped:** 2026-10-30
**Files analyzed:** 30 (new + modified + deleted)
**Analogs found:** 27 / 30 (others use RESEARCH.md patterns)

All cited paths are git-tracked (checked with `git ls-files`). Line numbers are from the live tree on 2026-10-30.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `porter/pins.py` (NEW) | config (data-only module) | static data | `porter/fpslocker.py:15-19` module constants; `porter/toolchain.py` `NDK_RELEASE`/`NDK_REVISION`/`DOTNET_MAJOR` | role-match |
| `porter/lock.py` (NEW) | utility | file-I/O (OS lock) | `porter/runlog.py` `build_folder` marker (lines 44-58) | role-match |
| `porter/nuget.py` (NEW, or helper in toolchain.py) | service | batch / transform | `porter/pipeline.py` `translator()` + `nsp.run` usage | partial |
| `porter/fetch.py` (MOD) | service | file-I/O + request-response | itself: `plan` (80-91), `_download` (94-104), `_unzip` (107-117), `_untar` (120-122), `_install` (125+) | exact (self) |
| `porter/fpslocker.py` (MOD) | service | request-response | itself: `RAW`, `url`, `fetch` (15-34) | exact (self) |
| `porter/datapack.py` (MOD) | service | file-I/O | itself `build` tail (lines ~58-61) + `nsp.swap_in` (`nxnative/scripts/build_ipa_from_nsp.py:363-370`) | exact |
| `porter/adb.py` (MOD) | service | file-I/O | itself `push_tree` (146-160), line with `hashlib.md5(p.read_bytes())` | exact (self) |
| `porter/toolchain.py` (MOD) | service | request-response | itself `checks()` (92-115) | exact (self) |
| `porter/runlog.py` (MOD) | utility | event-driven | itself `build_folder` (44-58) | exact (self) |
| `porter/upstream.py` (MOD) | utility | config | itself `_load_nsp` (19-26) | exact (self) |
| `porter/pipeline.py` (MOD, hook lines) | service | batch | itself `run` (81-99), `inputs` (118-150), `check_space` (152-158), `use_profile_dir` (160-163), `experimental_profile` (165-187) | exact (self) |
| `porter/cli.py` (MOD, hook lines) | controller | request-response | itself `cmd_install` (105-113) | exact (self) |
| `nxnative/scripts/build_ipa_from_nsp.py` (SUBTREE, small) | service | file-I/O | itself `swap_in` (363-370), `build_nx_extract` (~355-360), key writes ~773/805/849/898/1229/1327/1349/1446 | exact (self) |
| `nxnative/dm/android/apk/mkapk.py` (MOD, fork layer) | utility | file-I/O | itself `main()` (191-206) | exact (self) |
| `probes/app/mkapk.py` (DELETE) | — | — | — | — |
| `probes/app/probeapp.c` (MOD header comment) | docs | — | mkapk usage in `mkapk.py:8-9` defaults | role-match |
| `gui/app.py` (MOD) | component | request-response | itself: `LANGUAGES` 18-19/71, font 102, card 121-136, download list 301 | exact (self) |
| `devtools/hooks.py` (NEW) | utility (script) | one-shot | `devtools/device.py` / `devtools/port_check.py` header style | role-match |
| `devtools/nuget_pins.py` (NEW, suggested by RESEARCH Pattern 9) | utility (script) | batch | `devtools/port_check.py` | partial |
| `docs/ARCHITECTURE.md`, `README.md`, `.gitignore`, `nxnative/dm/third_party/README.md`, Ryujinx patch file | docs/config | — | existing text | n/a |
| `tests/test_fetch.py` (NEW) | test | file-I/O + mocked HTTP | `tests/test_tls.py` (mock.patch.object style) | exact |
| `tests/test_lock.py` (NEW) | test | subprocess | `tests/test_runlog.py` `Stop` (185+) subprocess with own `NX2A_HOME` | role-match |
| `tests/test_stages.py` (NEW) | test | subprocess kill | `tests/test_runlog.py` `Marker` (100-126) | exact |
| `tests/test_signing.py` (NEW) | test | file-I/O | `tests/test_porter.py` `DataPack` (74+) temp-dir pattern | role-match |
| `tests/test_adb.py` (NEW) | test | mocked subprocess | `tests/fixtures/bridge/fake_porter.py` + `tests/test_tls.py` mock style | role-match |
| `tests/test_toolchain.py` (NEW) | test | mocked env/platform | `tests/test_tls.py::test_windows_reads_no_host_file` (patching `os.name`) | exact |
| `tests/test_cli.py` (NEW) | test | subprocess JSON | `tests/test_runlog.py` `OneShot` (138+) | exact |
| `tests/test_runlog.py` (MOD) | test | — | `Marker.test_cut_off_redoes_stages` (113-126) must flip | exact |
| `tests/test_porter.py` (MOD) | test | — | `Experimental` (96-110) assertion on `os.environ` must flip | exact |
| `tests/test_tls.py` (maybe MOD) | test | — | `test_every_urlopen_passes_the_context` counts urlopen calls (new ones in fpslocker head lookup must pass `context=`) | exact |

## Pattern Assignments

### `porter/pins.py` (NEW, data only)
Keep it a `.py` module (bundled by `collect_submodules('porter')` in `packaging/nx2android.spec`, no `datas` change). Header style copies `porter/fpslocker.py`; constants copy `RAW`/`TARGETS` style:
```python
RAW = 'https://raw.githubusercontent.com/masagrator/FPSLocker-Warehouse/v4/SaltySD/plugins/FPSLocker/patches/{tid}/{bid}.yaml'
TARGETS = (30, 60)
REFRESH = 60   # the display rate FPS_LOCK_TARGET compares with (the host presents at 60 Hz)
```
Values: RESEARCH.md Pattern 3 table (NDK sha1s, platform-tools 37.0.1 sha1s, .NET 10.0.403 sha512 per RID, FPSLOCKER `575eef08…`, NUGET contentHashes generated by script). Top comment states the bump procedure.

### `porter/lock.py` (NEW)
**Analog:** `porter/runlog.py:44-58` (writes a PID + time file into `work`):
```python
m.write_text(f'{os.getpid()} {time.strftime("%Y-%m-%d %H:%M:%S")}\n', encoding='utf-8')
```
Error type: import `BuildError` from `porter.upstream` lazily as `cli.cmd_install` does (`from porter.upstream import BuildError, PROG`, cli.py:107). Body: RESEARCH Pattern 5 verbatim (`take(work, cmd)`, `AT = 4096`, flock / msvcrt). Hooks:
- `porter/pipeline.py` `inputs`, right after `self.work = o.folder / f'{tid}_build'` (line 122): `self.lock = lock.take(self.work, 'port')`.
- `porter/cli.py` `cmd_install.go()` (lines 108-112), before `install.install(...)`; never inside `install.install` (same-process flock conflict).

### `porter/fetch.py` (MOD)
Today's code to replace/extend:
- `plan` HEAD for size (line ~89) — becomes HEAD of pinned URL; 404/410 → fallback with `untested=True`:
```python
with urllib.request.urlopen(urllib.request.Request(it.url, method='HEAD', headers={'User-Agent': 'nx2android'}), timeout=60, context=tls.context()) as r: it.size = int(r.headers.get('Content-Length') or 0)
```
- `_download` mismatch (keep the delete; change message to name both hashes):
```python
if h.hexdigest().lower() != it.hash.lower():
    part.unlink(missing_ok=True); raise BuildError(f'{it.url}: the download\'s {it.algo} is not the one its list gives (try again)')
```
- `_unzip` vulnerable symlink line (the hole): `t = into / info.filename; ...; os.symlink(z.read(info).decode(), t)` → RESEARCH Pattern 2 (names checked first, files, links last with resolved-root check).
- `_untar`: drop the `hasattr` fallback, use `filter='data'` unconditionally:
```python
PROG.set(step='unpacking'); t.extractall(into, **({'filter': 'tar'} if hasattr(tarfile, 'tar_filter') else {}))
```
- `_install`: wrap unpack in try/except that `rmtree(tmp)` then re-raises.
- Every new `urlopen` passes `context=tls.context()` (tested in `tests/test_tls.py`).

### `porter/fpslocker.py` (MOD)
Analog is its own `fetch` (lines 25-31):
```python
def fetch(title_id, build_id, timeout=30):
    try:
        with urllib.request.urlopen(urllib.request.Request(url(title_id, build_id), headers={'User-Agent': 'nx2android'}), timeout=timeout, context=tls.context()) as r: return r.read().decode('utf-8-sig')
    except urllib.error.HTTPError as e:
        if e.code == 404: return None
        raise
```
Change `RAW` `v4` → `{ref}`, return `(text, commit)`, loop pinned → head (RESEARCH Pattern 4). Caller `Port.fps_unlock` (pipeline.py ~250) gains the sha256 and writes the cache with temp + `os.replace`. Return-type change: grep callers of `fpslocker.fetch` and `url` (pipeline, tests `FpsLocker` class at test_porter.py:135).

### `porter/datapack.py` (MOD)
Tail of `build` today (the HARD-07 hole):
```python
(tmp / MANIFEST).write_text(json.dumps(man, indent=2), encoding='utf-8')
if dst.exists(): shutil.rmtree(dst)
tmp.rename(dst)
return man
```
Replace with aside swap + `recover(dst)` (RESEARCH Pattern 6). Module is stdlib-only; if not importing `nsp.swap_in`, copy its Windows retry loop (build_ipa_from_nsp.py:365-369, the Tales of Eternia comment). The build folder goes in a host-only sidecar `<App>-data.build` beside the pack, never in the manifest (D-14, decided 2026-10-30; Open Question 3 resolved). Hook `datapack.recover(data)` in `cli.cmd_install` before reading the sidecar.

### `porter/adb.py` (MOD)
One line in `push_tree` (~line 155):
```python
changed = {rel for rel, p in files if rel in same and rmd5.get(rel) != hashlib.md5(p.read_bytes()).hexdigest()}
```
→ open the file and use `hashlib.file_digest(f, 'md5').hexdigest()`. Also grep the rest of porter for `.read_bytes()` hashing (e.g. `porter/install.py`).

### `porter/toolchain.py` (MOD)
Analog row (line 97):
```python
out.append(Check('Python', v >= (3, 11), f'{v.major}.{v.minor}.{v.micro} ({sys.executable})', fix='Python 3.11 or later'))
```
→ `python_ok()` (RESEARCH Pattern 1) and fix text naming 3.11.13 / 3.12.11 / 3.13.4. Refusal of other commands goes in `runlog.run` (fork-owned), not `cli.py`.

### `porter/runlog.py` (MOD)
`build_folder` (lines 44-58): keep the marker write, delete the key sweep:
```python
say('[RED] the last port of this game was cut off: every stage runs again')
for root, dirs, files in os.walk(work):
    if root == str(work) and 'extract' in dirs: dirs.remove('extract')
    for n in files:
        if n.endswith('.key'): os.unlink(os.path.join(root, n))
```
New message names the stage (marker rewritten by the stage wrapper with `S['stage']`). Update header comment (lines 4-5) which says "redoes every cached stage".

### `porter/upstream.py` (MOD)
`_load_nsp` (lines 19-26) → one named function `_overrides(m)` with a comment per override and asserts before replacing:
```python
m.nacp, m.pg = nacp, profile_guess   # module globals its main() sets
if sys.platform != 'darwin': m.can_clone = lambda d: False
files = m.profile_files
m.profile_files = lambda g: [p for p in files(g) if p.name != 'android.tsv']
```
Asserts: `{'nacp','pg'} <= set(m.main.__code__.co_names)`; `callable(getattr(m, n))` for `can_clone`, `profile_files`.

### `porter/pipeline.py` (MOD, hook lines only)
- `run` lines 92-95: stop writing `os.environ`; build `self.env = dict(os.environ, ...)` with PATH prepended, `DOTNET_ROOT`, `NUGET_PACKAGES=str(paths.user_dir()/'nuget')`. Today:
```python
os.environ['PATH'] = os.pathsep.join([str(self.tools['dotnet'].parent), os.environ.get('PATH', '')])
os.environ['DOTNET_ROOT'] = str(self.tools['dotnet'].parent)
self.env = dict(os.environ, J=str(o.jobs), PYTHONIOENCODING='utf-8', PYTHONUTF8='1', DOTNET_CLI_TELEMETRY_OPTOUT='1')
```
  Plus signing-key preflight after `toolchain.require` (raise `BuildError`, same text as mkapk).
- `inputs` line 122: lock hook.
- `check_space` (152-158): replace top-level `iterdir` sum with the family sum (`fam['base']`, updates, dlc); add a re-check call after `self.extract()` in `run`.
- `use_profile_dir` (160-163): write only `self.env`, not `os.environ`.
- `experimental_profile`: `copytree` → into `d.with_name(d.name+'.partial')` then `nsp.swap_in`; `game.load(tid)` → `game.load(str(d))` (also `:211` `game.load(str(pdir / g.id))`).
- Key writes at :295, :323 → upstream `nsp.write_key`.
- `inspect` adds `languages` (D-12) from `nacp.languages(...)` if `<tid>_build/extract/<pack>/control.nacp` exists, else full `nacp.LANGUAGES`.

### `porter/cli.py` (MOD, hook lines only)
`cmd_install` (105-113):
```python
def go():
    data = Path(a.data).resolve()
    apk = ...
    PROG.plan(1)
    cfg = config.load()
    install.install(apk, data, toolchain.find_adb(cfg), a.device or cfg.get('device'), replace_signer=a.replace_signer)
```
Add `datapack.recover(data)` and `lk = lock.take(Path(man['build']), 'install')` when the manifest names it. Optionally drop `_with_progress`'s env restore (cli.py ~81, 94-95).

### `nxnative/scripts/build_ipa_from_nsp.py` (SUBTREE: small, platform-neutral)
- Add `write_key(kf, text)` (temp + `os.replace`) beside `swap_in`; call at each key-write site.
- `swap_in` (363-370) → aside rename (`dst→dst.old`, `tmp→dst`, rmtree old), keep the Windows retry loop and comment.
- `build_nx_extract`: `run(['dotnet', 'build', ...], ..., env=env)` → `shutil.which('dotnet', path=(env or os.environ).get('PATH')) or 'dotnet'` (upstream already does this at ~:1548).
- `env=env` on the `nx_extract` runs at :475 (survey), :745 (`extract`), :771 (`extract_aoc`) with `env=None` default params so `main()` is unchanged.
- No new files in the subtree (D-05).

### `nxnative/dm/android/apk/mkapk.py` (MOD)
Today (lines 193-204):
```python
if os.path.exists(keyf): k = {a: int(v) for a, v in json.load(open(keyf)).items() if a != 'cert'}; crt = bytes.fromhex(json.load(open(keyf))['cert'])
else:
    t = time.time(); k = gen_key(); crt = cert(k)
    json.dump({**{a: str(v) for a, v in k.items()}, 'cert': crt.hex()}, open(keyf, 'w'))
...
open(out, 'wb').write(apk)
```
→ RESEARCH Pattern 7 `save_key` (mkstemp, fsync/F_FULLFSYNC, `os.link` no-clobber), refuse unreadable key with `sys.exit('[RED] …')`, chmod 0600 on POSIX, APK to `out + '.partial'` then `os.replace`. Stdlib only; runs standalone. `fcntl` import guarded (not on Windows).

### `gui/app.py` (MOD)
- Line 18-19 `LANGUAGES` and line 71 `for code, name in LANGUAGES: self.language.addItem(name, code)` → fill from `info['languages']` after inspect, keeping first item `('', 'English (default)')`.
- Line 102: `self.log.setFont(QFont('Consolas' if os.name == 'nt' else 'Menlo', 9))` → `QFontDatabase.systemFont(QFontDatabase.FixedFont)`.
- Escape with `html.escape(str(s), quote=True)` (already imported, line 6) at: 121 (folder `d`), 131 (`info["name"]`, `info["title_id"]`), 134 (`info["pack"]`), 135-136 (`tested`, `reason`), 301 (`it[...]` incl. `href`). Also show `(untested)` from the new `Item.untested` field in the 301 list.
- No pipeline logic here (arch rule).

### `devtools/hooks.py` (NEW)
Copy the module header comment style of other `devtools/*.py`; body: `subprocess.run(['git', 'config', 'core.hooksPath', '.githooks'], cwd=REPO, check=True)`. Update `README.md:102` contributor section.

## Tests

### Shared test skeleton
**Source:** `tests/test_porter.py:1-20`, `tests/test_tls.py:1-12`
```python
import ast, os, ssl, sys, unittest
from pathlib import Path
from unittest import mock
REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
```
`os.environ['NX2A_HOME'] = tempfile.mkdtemp(prefix='nx2a_test_home_')` at module top (test_porter.py:7). Modules importing `porter.upstream` (lz4 etc.) use `setUpModule()` skip, not module-level SkipTest (test_porter.py:17, test_runlog.py:18). Pure-stdlib modules (`fetch` parts, `lock`, `toolchain.python_ok`) should stay importable without engine deps so they run on all four CI hosts like `test_tls.py`.

### Mocking style
**Source:** `tests/test_tls.py:36-39`
```python
with mock.patch.object(tls.ssl, 'create_default_context', empty), mock.patch.object(tls.os, 'name', 'nt'), \
     mock.patch.object(tls.os.path, 'isfile', isfile): c = tls.context(ca_files=(CA,))
```
Use for `urlopen` (test_fetch), `sys.platform`/`os.name` (test_toolchain), `subprocess.run` in `porter.adb` (test_adb).

### Subprocess runs with own home
**Source:** `tests/test_runlog.py:23` and `Stop` (185+):
```python
e = dict(os.environ, NX2A_HOME=str(home), PYTHONIOENCODING='utf-8'); e.pop('NX2A_GUI', None); e.update(env or {})
```
For test_lock (second process gets "already running") and test_stages (child does `os._exit` mid-stage, next run redoes it). test_cli copies `OneShot` (138+) for `--json` error paths.

### Flips required
- `tests/test_runlog.py::Marker::test_cut_off_redoes_stages` (113-126): assert keys kept and message names the stage.
- `tests/test_porter.py::Experimental` line 107: `os.environ.get('DM_GAMES_FIRST') == '1'` → `port.env['DM_GAMES_FIRST'] == '1'` and `os.environ` unchanged.
- `tests/test_porter.py::Misc::test_disk_space` (~127) if `check_space` signature/inputs change (now reads `self.fam`).
- `tests/test_porter.py::FpsLocker` if `fetch` returns a tuple.

## Shared Patterns

### Errors
`BuildError` from `porter.upstream` (`BuildError, PROG, say = nsp.BuildError, nsp.PROG, nsp.say`, upstream.py:30). Messages name the file and the fix; wrap with `raise BuildError(str(e)) from e` (pipeline.py:89). Apply to lock, fetch, nuget, signing preflight.

### Logging
`say('[RED] …')` for problems/untested fallbacks (runlog.py:51). Progress via `PROG.set(step=..., done=..., total=..., unit=...)` (fetch.py `_download`/`_unzip`).

### Network
Every `urlopen(..., context=tls.context())` with `headers={'User-Agent': 'nx2android'}` (fetch.py, fpslocker.py).

### Atomic swap
`nsp.swap_in(tmp, dst)` and the `.partial` sibling naming (datapack.py `tmp = dst.with_name(dst.name + '.partial')`). Reuse for profile copy, data pack, and (via `write_key`) stamps.

### Style
Dense one-line Python; `#` header comment of 1-5 lines stating job + contract and evidence (see runlog.py:1-5, datapack.py:1-9).

## No Analog Found

| File | Role | Data Flow | Reason |
|---|---|---|---|
| `porter/nuget.py` (or helper) | service | batch | No existing post-restore verification; use RESEARCH Pattern 9 |
| Ryujinx local-changes patch file | docs/data | — | Generated by `git diff --no-index` vs `475615f` (RESEARCH Pattern 12) |
| `devtools/nuget_pins.py` | script | batch | Nothing generates pins today |

## Metadata
**Analog search scope:** `porter/`, `gui/app.py`, `tests/`, `tests/fixtures/bridge/`, `nxnative/scripts/build_ipa_from_nsp.py`, `nxnative/dm/android/apk/mkapk.py`
**Pattern extraction date:** 2026-10-30
