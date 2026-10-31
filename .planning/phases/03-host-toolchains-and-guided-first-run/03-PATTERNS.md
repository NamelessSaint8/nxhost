# Phase 3: Host Toolchains and Guided First Run - Pattern Map

**Mapped:** 2026-10-31
**Files analyzed:** 22 (9 new porter/gui modules, 8 modified, 5+ new tests/fixtures)
**Analogs found:** 21 / 22 (all analogs are git-tracked; checked with `git ls-files porter gui tests`)

House style for every file (CLAUDE.md): `#` header block of 1-5 lines stating the module's job and contract; dense one-line bodies (`if x: return y`, `try: ... / except (OSError, ValueError): ...`); `[RED] ` prefix for problem lines; named `<Thing>Error` exceptions with a message that names the file and the fix; no PySide6 in `porter/`.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `porter/setup.py` (new) | service | request-response (one JSON doc) | `porter/toolchain.py` `checks()` + `Check` (L22-31, L112-141) | exact |
| `porter/hosttools.py` (new) | utility | file-I/O + subprocess probe | `porter/toolchain.py` `find_*`, `_sdk_roots`, `dotnet_sdks` (L34-87) | exact |
| `porter/keys.py` (new) | utility | file-I/O / transform | `porter/toolchain.py` `_signing_key_check` (L102-109), `ndk_revision` (L42-46) | role-match |
| `porter/distro.py` (new) | utility | file-I/O (os-release) | `porter/toolchain.py` `ndk_revision` (regex over a text file) | role-match |
| `porter/desktop.py` (new) | utility | file-I/O (write) | `porter/config.py` `save()` (atomic tmp+replace, L28-30) | role-match |
| `porter/prepare.py` (new, D-24) | service | streaming (`--progress json`) | `porter/cli.py` `cmd_tools` download branch (L134-149) + `porter/fetch.py` `download()` (L223-242) | role-match |
| `porter/childenv.py` (optional) | utility | transform | `gui/runner.py` `_env()` (L20-24) as shape only | partial |
| `porter/cli.py` (modify, hook lines) | controller | request-response | itself: `devices` / `cmd_devices` (L30, L122-131), dispatch dict (L172) | exact |
| `porter/toolchain.py` (modify) | utility | file-I/O | itself (`find_adb` L82-86, `checks()` adb row) | exact |
| `porter/fetch.py` (modify: arm64 NDK host, Range resume) | service | streaming download | itself `_download` L111-121, `_google_os` L47, `_dotnet_rid` L50-52 | exact |
| `porter/pins.py` (modify: linux-arm64 NDK row) | config | data | `pins.NDK['files']` rows (L8-12) | exact |
| `porter/adb.py` (modify: `devices()` parse, `-Z` gating) | service | subprocess request-response | itself L61-68, L171, L191 | exact |
| `porter/config.py` (modify: legal-version key) | config | CRUD | `KEYS` dict L7-15 | exact |
| `gui/firstrun.py` (new) | component (QWizard + banner + poll) | event-driven | `gui/app.py` `SetupTab` (L257-367) | role-match |
| `gui/app.py` (modify, hook lines) | component | event-driven | `Window.set_ready` L430-432, `SetupTab.check` L353-367 | exact |
| `gui/runner.py` (modify: `TIMEOUTS`) | config line | — | `TIMEOUTS` L17 | exact |
| `tests/test_setup.py`, `tests/test_keys.py`, `tests/test_hosttools.py` (new) | test | unit | `tests/test_toolchain.py`, `tests/test_adb.py` (`fake()` subprocess table), `tests/test_fetch.py` | exact |
| `tests/test_firstrun.py` (new) | test | GUI offscreen | `tests/test_bridge.py` | exact |
| `tests/fixtures/bridge/fake_porter.py` (modify) + `setup_*.json` (new) | test fixture | — | itself `ONE_SHOT` L13, `--fixture` L35 | exact |
| `tests/fixtures/keys/*` (new, fake hex only) | fixture | data | `tests/fixtures/zip_links.json` (data fixture precedent) | partial |
| `tests/arch_rules.py` (modify: firstrun import rule) | test | static check | `porter/ imports no UI` rule L81-91 | exact |
| CI step for compile probe (`fork-release.yml`) | config | — | not mapped (outside porter/gui/tests; see RESEARCH.md L469) | none |

## Pattern Assignments

### `porter/setup.py` (service, one JSON document)

**Analog:** `porter/toolchain.py`

Header + imports (L1-9): module comment, stdlib imports on one line, `from porter import config`.

Row type to reuse, not reinvent (L22-31):
```python
@dataclass
class Check:
    name: str
    ok: bool
    detail: str
    required: bool = True
    path: str = ''
    fix: str = ''

    def as_dict(self): return dict(self.__dict__)
```
Ordered-steps builder (L112-141): `out = []; out.append(Check(...))` per requirement, `fix=''` when ok. `ready` = `all(r.ok or not r.required for r in rows)` (same rule as `cli.cmd_doctor` L47 and `SetupTab.check` L366). No network, no device listing (RESEARCH Pattern 1).

### `porter/hosttools.py` (known places, NDK host folder, compile probe, adb version)

**Analog:** `porter/toolchain.py` L34-87.

Per-OS place list (L34-39):
```python
def _sdk_roots():
    out = [os.environ.get(k) for k in ('ANDROID_HOME', 'ANDROID_SDK_ROOT')]
    if os.name == 'nt': out.append(os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Android', 'Sdk'))
    elif sys.platform == 'darwin': out.append(os.path.expanduser('~/Library/Android/sdk'))
    else: out.append(os.path.expanduser('~/Android/Sdk'))
    return [Path(p) for p in out if p]
```
Candidate-list search (L82-86, `find_adb`): first `Path(c).is_file()` of a list; dedupe with `dict.fromkeys` (L66). Subprocess probe with timeout and narrow except (L70-73):
```python
try: r = subprocess.run([str(dotnet), '--list-sdks'], capture_output=True, text=True, timeout=60)
except (OSError, subprocess.TimeoutExpired): return []
return re.findall(r'^(\d+\.\d+\.\d+)', r.stdout, re.M)
```
adb version: same shape with regex `^Version\s+(?:\d+:)?(\d+)\.(\d+)\.(\d+)` (RESEARCH L376); unparseable keeps `-Z`. Hook back into `toolchain.find_adb/find_dotnet/find_ndk` candidate lists by one added element each (upstream file: hook lines only).

### `porter/keys.py`

**Analog:** `toolchain._signing_key_check` (L102-109): parse in one `try`, collect `bad`, return a `Check` with `fix` text. Errors: narrow `except (OSError, ValueError, ...)`. Raise `KeysError(Exception)` only where the CLI must stop; otherwise return rows.

### `porter/distro.py`

**Analog:** `toolchain.ndk_revision` (L42-46):
```python
try: t = (Path(d) / 'source.properties').read_text(errors='replace')
except OSError: return None
m = re.search(r'Pkg\.Revision\s*=\s*([\d.]+)', t)
```
Apply to `/etc/os-release` `ID` / `ID_LIKE`; return command strings only.

### `porter/desktop.py`

**Analog:** `porter/config.py` `save()` L28-30 (atomic write):
```python
p = path(); tmp = p.with_suffix('.tmp')
tmp.write_text(json.dumps(...), encoding='utf-8'); tmp.replace(p)
```

### `porter/prepare.py` (streaming, `--progress json`)

**Analog:** `porter/cli.py` `cmd_tools` L142-148 + `fetch.download` L223-242: `_with_progress(a.progress, go)`; inside, `PROG.plan(n)`, `PROG.stage(name, step=...)`, `PROG.say('[RED] ...')`, `PROG.end(str(dest))`, `PROG.close()`; failure raises `BuildError` (from `porter.upstream`).

### `porter/cli.py` (hook lines only)

Parser line, same as `devices` (L30):
```python
dv = sub.add_parser('devices', help='the devices adb sees'); dv.add_argument('--json', action='store_true')
```
Command, lazy import inside the function, `_print_json` (L39, L122-131):
```python
def cmd_devices(a):
    from porter import config, toolchain
    ...
    if a.json: _print_json([...]); return 0
```
Dispatch (L172): add `'setup': cmd_setup` (and `desktop-entry`, keys check) to the dict passed to `runlog.run`. Error document for JSON callers: `_print_json({'error': msg}) if a.json else print(msg, file=sys.stderr); return 2` (L139) — `call_json` turns `{"error"}` into `fail['error']`.

### `porter/fetch.py`

- Host key: `_google_os()` L47 returns `'linux'` for all Linux; model the arm64 case on `_dotnet_rid()` L50-52 (`platform.machine().lower() in ("arm64", "aarch64")`), used only for the NDK in `_pinned()` L79-83 (adb stays on distro on arm64).
- Resume: `_download` L111-121 opens `part` with `'wb'`; `download()` L234-236 deletes `arc` in `finally` (not the `.part`). Resume = `Range: bytes=<part size>-` header on the existing `Request(..., headers={'User-Agent': 'nx2android'})`, open `'ab'`, re-hash existing bytes first; keep the mismatch message unchanged (L118-120, pinned by `tests/test_fetch.py` `test_mismatch_names_both_hashes`).

### `porter/pins.py`

Add `'linux-arm64'` (or the key chosen in fetch) to `NDK['files']` in the exact tuple form (L9-11): `(url, size, 'sha256', '<hex>')`. Header comment L5 already reserves it. `tests/test_fetch.py::Pins.test_rows_complete` (L68) covers row shape.

### `porter/adb.py`

`devices()` L61-68 splits on whitespace (bug for `no permissions (...)`):
```python
for ln in out.splitlines()[1:]:
    parts = ln.split()
    if len(parts) >= 2: rows.append((parts[0], parts[1], ' '.join(p for p in parts[2:] if p.startswith(('model:', 'device:')))))
```
Replace with one regex per line, keep the `(serial, state, info)` tuple (callers: `pick()` L70, `cli.cmd_devices`). `-Z` sites: L171 and L191 (`self.run('push', '-Z', ...)`); gate both through one attribute set from hosttools' adb version.

### `porter/config.py`

Add one `KEYS` entry (L7-15), e.g. `'legal': 'version of the notice the player accepted'`; `load()`/`save()` need no change.

### `gui/firstrun.py` (QWizard, banner, device poll)

**Analog:** `gui/app.py` `SetupTab` L257-367.

- Imports: PySide6 + `from gui.runner import Porter, call_json` only (arch rule; no `porter.config`, unlike `gui/app.py`).
- One-shot with failure + Retry (L353-367 and `failed()` L36-39, `cause()` L31-33). UI-SPEC: reuse `failed()`/`cause()` with the word "porter" changed to "nx2android" — import from `gui.app` or move? UI-SPEC says reuse; avoid editing `gui/app.py` beyond hooks, so pass the text through a small local wrapper.
- Long run with progress/Cancel: `self.fetch = Porter(self); self.fetch.event.connect(self.on_fetch); self.fetch.finished.connect(self.fetched)` (L280), `on_fetch` event switch (L312-323), `fetched(code)` treating `130` as cancelled (L325-333). Cancel = `Porter.stop()` (runner L70).
- Download consent dialog: `confirm_download` L297-310 (rich text, `html.escape(..., quote=True)` for hrefs).
- Colours: define `COLOUR` dict + `colour(widget, key)` per UI-SPEC L122; do not edit `STATUS_COLOUR` (app.py L18).
- Polling: `QTimer` calling `call_json(self, ['devices', '--json'], got)` (pattern at app.py L156); `call_json` already drops callbacks once the owner is gone (runner L136).

### `gui/app.py` (hook lines)

`Window.set_ready` L430-432 is the hook:
```python
def set_ready(self, ok):   # the first check: a missing requirement opens the Setup tab
    if self.first and not ok: self.tabs.setCurrentWidget(self.setup)
    self.first = False
```
Replace the jump with the firstrun call (RESEARCH Pattern 8). Keep `set_ready(False)` on a failed check (`tests/test_bridge.py` L110-118 asserts `ready.assert_called_with(False)`). New Setup-tab buttons (Run setup, Cancel) sit in the `dl` row (L277-279).

### `gui/runner.py`

One edit, L17: `TIMEOUTS = {..., 'setup': 45}`; extend the comment above (L14-16) with why.

### Tests

- Porter unit tests: header comment naming the module under test + what is pinned; `REPO`/`sys.path` + `os.environ['NX2A_HOME'] = tempfile.mkdtemp()` before importing porter (`tests/test_toolchain.py` L1-10). Optional-module skip via `setUpModule` (`tests/test_adb.py` L12-21). Subprocess faking: `fake(table, calls)` in `tests/test_adb.py` L26+ (use for adb version / devices states / compile probe). Network faking: `Resp(io.BytesIO)` in `tests/test_fetch.py` L24 (Range resume).
- `tests/test_firstrun.py`: copy `tests/test_bridge.py` L1-40 preamble (offscreen, OLD/MISSING skip, `setUpModule`, `runner.PORTER = [FAKE, ...]`, `until(...)` waits).
- `fake_porter.py`: add `'setup'` (and `config`) to `ONE_SHOT` L13; feed setup docs with `--fixture tests/fixtures/bridge/setup_ready.json` (L35 path already writes bytes verbatim). Note: a one-shot answers `[]` today, a dict is needed for setup — default answer should be a ready doc so existing bridge Windows start cleanly (RESEARCH L388).
- `tests/arch_rules.py`: copy L89-91:
```python
ui = [f for f in porter if any(i.split('.')[0] in ('PySide6', ...) for i in imports(f))]
check('porter/ imports no UI', not ui, ', '.join(ui))
```
as `check('gui/firstrun.py imports only gui.runner and PySide6', ...)` over `imports('gui/firstrun.py')`.

## Shared Patterns

- **JSON one-shot contract:** `cli._print_json` (cli L39); error = `{"error": msg}` exit 2; GUI side `call_json(parent, args, done, timeout)` -> `done(obj, code, fail)` (runner L126-154). Apply to `setup`, `desktop-entry`, keys check.
- **Streaming contract:** `_with_progress` + `PROG.stage/say/end/close` (cli L81, fetch L223-242); GUI `Porter` events `stage/progress/say/log/error` (app L312-323). Apply to prepare and downloads.
- **Errors:** `BuildError` from `porter.upstream` for user-facing stops; wrap with `raise X(str(e)) from e`; `[RED] ` prefix on problem `say` lines.
- **Row shape:** `toolchain.Check` (`name, ok, detail, required, path, fix`) for every readiness step.
- **Settings writes:** only porter writes `config.json` (`config.set_value`, config L33-35); GUI firstrun never does.

## No Analog Found

| File | Role | Reason |
|---|---|---|
| `fork-release.yml` compile-probe step | CI config | outside the mapped dirs; follow RESEARCH.md L469 (`smoke_bundle.py` already runs per target) |

QWizard itself has no in-repo precedent; use UI-SPEC + RESEARCH Standard Stack for page structure, `SetupTab` for everything inside a page.

## Metadata

**Analog search scope:** `porter/`, `gui/`, `tests/`, `tests/fixtures/bridge/`
**Files scanned:** 14
**Pattern extraction date:** 2026-10-31
