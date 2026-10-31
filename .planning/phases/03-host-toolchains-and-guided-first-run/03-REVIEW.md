---
phase: 03-host-toolchains-and-guided-first-run
reviewed: 2026-10-31T00:00:00Z
depth: standard
files_reviewed: 48
files_reviewed_list:
  - .github/workflows/fork-release.yml
  - devtools/ndk_pin.py
  - docs/ARCHITECTURE.md
  - docs/RELEASE_CHECK.md
  - gui/app.py
  - gui/firstrun.py
  - gui/runner.py
  - gui/shell.py
  - nxnative/dm/android/build.py
  - packaging/INSTALL.md
  - packaging/smoke_bundle.py
  - porter/adb.py
  - porter/childenv.py
  - porter/cli.py
  - porter/config.py
  - porter/desktop.py
  - porter/distro.py
  - porter/fetch.py
  - porter/hosttools.py
  - porter/keys.py
  - porter/pins.py
  - porter/pipeline.py
  - porter/prepare.py
  - porter/probe.py
  - porter/runlog.py
  - porter/setup.py
  - porter/toolchain.py
  - tests/arch_rules.py
  - tests/fixtures/bridge/fake_porter.py
  - tests/fixtures/bridge/setup_first.json
  - tests/fixtures/bridge/setup_missing.json
  - tests/fixtures/bridge/setup_ready.json
  - tests/test_adb.py
  - tests/test_bridge.py
  - tests/test_desktop.py
  - tests/test_distro.py
  - tests/test_fetch.py
  - tests/test_firstrun.py
  - tests/test_hosttools.py
  - tests/test_keys.py
  - tests/test_packaging.py
  - tests/test_prepare.py
  - tests/test_probe.py
  - tests/test_runlog.py
  - tests/test_setup.py
  - tests/test_shell.py
  - tests/test_toolchain.py
  - tests/test_workflows.py
findings:
  critical: 1
  warning: 6
  info: 8
  total: 15
status: issues_found
---

# Phase 3: Code Review Report

**Reviewed:** 2026-10-31
**Depth:** standard
**Files Reviewed:** 48
**Status:** issues_found

## Summary

I reviewed the phase diff `5ed9215..HEAD`: the new porter modules (setup, keys, probe, hosttools, childenv, distro, desktop, prepare), the resumable download, the adb state parsing, the first-run wizard and shell, and the packaging and CI changes. The test suite passes (419 tests, run during the review).

The porter side is mostly sound. Values that come from outside are escaped or treated as plain text: key values are never read, adb text is shown as plain text, the Desktop Entry `Exec` line is quoted, and symlinks are refused. The main defects come from the wizard and the old Setup tab now sharing one window state:

- **Data loss:** the Setup tab keeps a stale copy of the settings, and its Save button writes that copy over what the wizard saved through porter (CR-01).
- **Shared runner:** the same tool-download runner can be started twice (WR-04).
- **Shutdown race:** a Prepare can start while the app quits (WR-05).
- **Readiness check:** the GUI's 45 s limit on `setup --json` is shorter than the probe's own limits, so a slow first probe never gets cached (WR-02). The probe cache write is unprotected, and every finished download starts two `setup` runs at the same time (WR-03).
- **Downloads:** a download cut off cleanly by the server is not retried or resumed. The partial file is hashed, fails the check and is deleted (WR-01). I confirmed this with a local socket test.

## Critical Issues

### CR-01: The Setup tab's "Save and check" overwrites settings the wizard just saved

**File:** `gui/app.py:353-356`, `gui/app.py:430`; the writers are in `gui/firstrun.py:264`, `gui/firstrun.py:338` and `gui/firstrun.py:467`
**Issue:** `SetupTab.load()` copies `config.json` into the `QLineEdit`s for `keys`, `ndk`, `dotnet`, `adb`, `out` and `device`, but only at startup and after a fetch run ends (`fetched`). The wizard now saves `keys` (KeysPage), `ndk`/`dotnet`/`adb` (Use my own…) and `device` (DevicePage.pick) through `porter config <key> <value> --json`, then calls `win.recheck()`. In `gui/app.py` that is `self.setup.check()`, which runs `setup --json` but never reloads the edits. `SetupTab.save()` then writes every edit back:
```python
c = config.load()
for k, e in self.edits.items(): c[k] = e.text().strip()
config.save(c)
```
So a player who picks prod.keys in the wizard and later changes the output folder on the Setup tab and presses **Save and check** silently resets `keys` (and any NDK, dotnet, adb or device chosen in the wizard) to the values from launch, usually empty. The next port then fails with "prod.keys: not set" even though the wizard said it was saved.
**Fix:** reload the edits on every recheck, so they always match porter's file before Save can write them:
```python
def recheck(self): self.setup.load()   # load() refreshes the edits from config.json, then runs check()
```
A safer `save()` would also write only the fields the player changed, compared with the values loaded last.

## Warnings

### WR-01: A download the server cuts off cleanly is hashed as complete, then deleted, with no retry or resume

**File:** `porter/fetch.py:138-150`
**Issue:** `while chunk := r.read(1 << 20)` ends when `read()` returns `b''`. CPython's `HTTPResponse.read(amt)` returns `b''` and does not raise when the connection closes before `Content-Length` is reached. I checked this with a local server that announces 1000 bytes and sends 300: the result was "no exception, got 300 of 1000". The loop then breaks out of the retry `while True`, the hash fails, `part.unlink()` deletes the partial file, and a `BuildError` is raised. That breaks D-21/D-22: a dropped link on a 640 MB NDK loses all progress, and the 3-try retry never runs. A chunked response cut short raises `http.client.IncompleteRead`, which is an `HTTPException`, not an `OSError`, so the retry `except` does not catch that either.
**Fix:** treat a short body as a dropped link before checking the hash:
```python
import http.client
...
                with open(part, 'ab' if have else 'wb') as f:
                    while chunk := r.read(1 << 20): ...
                expect = int(r.headers.get('Content-Length') or 0)
                if expect and have < total: raise ConnectionResetError(f'got {have} of {total} bytes')   # retried and resumed, never hashed
            break
        ...
        except (urllib.error.URLError, http.client.HTTPException, OSError, TimeoutError) as e:
```

### WR-02: The GUI's `setup` limit (45 s) is shorter than the probe's own limits, so a slow first probe is killed and never cached

**File:** `gui/runner.py:18`, `porter/probe.py:12`, `porter/probe.py:43-47`
**Issue:** `setup --json` runs `toolchain.checks()`. That includes the NDK probe: `clang --version` plus a compile and link, each with `TIMEOUT = 60`, and the comment says a first run from a cold disk is "far slower". It also runs `dotnet --list-sdks` for each dotnet it finds, at up to 60 s each, and `adb version` at up to 15 s. `call_json` kills the whole session after 45 s. The probe caches only a pass, and a killed run writes nothing, so on a slow host (an SD-card Linux arm64 board, which this milestone targets) every launch hits the same uncached probe and fails again. The Setup tab shows "nx2android didn't answer in 45 s" every time and the wizard never gets a document. `doctor` (30 s) now runs the probe too.
**Fix:** keep the GUI limit above the inner limits: either raise `TIMEOUTS['setup']` above the worst case (for example 150 s), or give `setup` a time budget so the probe returns a "still checking, press Re-check" row instead of being killed. For example, pass the remaining budget to `probe.probe(ndk, timeout=...)` and report `fix: 'press Re-check'` when it runs out.

### WR-03: Probe cache write: fixed temp name, unhandled `OSError`, and two concurrent `setup` runs after every fetch

**File:** `porter/probe.py:57-58`; `gui/app.py:337` and `gui/firstrun.py:392` start the concurrent calls
**Issue:** `probe()` writes `<user dir>/probe.tmp` and then `tmp.replace(p)`, with no `try`. Any `OSError` there (a read-only or full home, or Windows refusing a replace while another process has the file open) escapes `toolchain.checks()`. That crashes `doctor`, `setup`, `tools`, and `port` at `require()`. When a fetch run ends, two `setup --json` processes start at the same moment: `SetupTab.fetched` → `load()` → `check()`, and `ToolsPage.on_finished` → `win.recheck()`. After an NDK download both miss the cache and probe the same new NDK at the same time. With the interleaving A writes tmp, B writes tmp, A replaces, B replaces, process B gets `FileNotFoundError` and answers `{"error": ...}`. If that answer arrives last, the Setup tab shows a failure with Retry right after a successful download.
**Fix:** treat the cache as best-effort and give each process its own temp file:
```python
try:
    fd, tmp = tempfile.mkstemp(dir=p.parent, prefix='.probe-', suffix='.tmp')
    with os.fdopen(fd, 'w', encoding='utf-8') as f: f.write(json.dumps(c2, indent=1))
    os.replace(tmp, p)
except OSError: Path(tmp).unlink(missing_ok=True) if 'tmp' in dir() else None   # an unwritable cache only costs a re-probe
```
Also drop the duplicate recheck: `ToolsPage.on_finished` does not need `win.recheck()` when the host window's own `fetched` already re-checks, or `Window.recheck` could merge calls that overlap.

### WR-04: The Setup tab can start a second run on the window's shared `fetch`, orphaning the first one

**File:** `gui/app.py:300-313` (`confirm_download`), `gui/app.py:295-297` (`download`), `gui/runner.py:53-54` (`Porter.start`)
**Issue:** The phase made `SetupTab.fetch` the window's shared runner: the wizard's tools page starts downloads and Prepare on it. `confirm_download` runs only after `tools --json` answers, which can take up to 60 s while it sends HEAD requests. During that time the non-modal wizard's **Download all missing** can start a run. Pressing **Yes** then calls `self.fetch.start(...)` on a running `Porter`. `Porter.start` overwrites `self.p` without checking, so the first `porter tools --download` keeps running untracked: its `_done` is ignored because `run is not self.p`, and the close guard no longer sees it. Two downloads then write the same `.part` files and `_install` the same folders. Also, until the first event arrives, `dl_btn` still reads "Download missing tools" while a wizard run is going, and pressing it stops that run (`download()` takes the `running()` branch).
**Fix:** refuse a second start in both places:
```python
def confirm_download(self, items, code, fail):
    if self.fetch.running(): self.dl_btn.setEnabled(True); return   # the wizard started one meanwhile
    ...
# gui/runner.py
def start(self, args):
    if self.running(): raise RuntimeError('Porter is already running')   # or return False
```
Update the Setup tab's button label from `Porter.start` or the `log` event, not only from later events.

### WR-05: The automatic Prepare after a download ignores a quit in progress

**File:** `gui/firstrun.py:385-392`
**Issue:** `on_finished` schedules `QTimer.singleShot(0, self, self.prepare)` whenever a wizard download exits 0. If the player chose **Stop and quit** just as the download finished, `Porter._done` keeps code 0, because only a non-zero code is mapped to 130 while stopping. `Window.run_ended` (connected earlier) then closes the window, and on the next event loop turn the timer starts `porter tools --prepare` on a window that is closing. Its dotnet children run in their own session, so when the app exits only porter is killed with the `QProcess`, and the dotnet builds are orphaned. That is exactly what the close guard is there to prevent.
**Fix:**
```python
if kind == 'download' and not getattr(self.wizard().win, 'quitting', False): QTimer.singleShot(0, self, self.prepare)
```
and check `quitting` again inside `prepare()`/`start()`.

### WR-06: The probe's fix commands leave paths unquoted and break under "Application Support"

**File:** `porter/probe.py:49`
**Issue:** `fix = f'chmod +x {c.parent}/*' + f'; ... xattr -dr com.apple.quarantine {ndk}'` puts raw paths into a command the player is meant to paste into a shell. On macOS, the NDK that porter downloads lives in `~/Library/Application Support/nx2android/toolchains/...`, which has a space. The command then turns into `chmod +x /Users/x/Library/Application` plus a second word, and it fails or touches the wrong files. Paths with spaces are also common for an NDK the player chose with "Use my own…".
**Fix:**
```python
import shlex
fix = f'chmod +x {shlex.quote(str(c.parent))}/*' + (f'; if it was downloaded in a browser: xattr -dr com.apple.quarantine {shlex.quote(str(ndk))}' if sys.platform == 'darwin' else '')
```

## Info

### IN-01: `Gate.start` is never used

**File:** `gui/firstrun.py:70`
**Issue:** `Gate.__init__` sets `self.start = None`, and nothing reads or writes it.
**Fix:** Remove it.

### IN-02: The keys page shows the path twice for a missing file

**File:** `porter/keys.py:17`, `gui/firstrun.py:248`
**Issue:** `detail` is `no such file: {p}`, and the page draws `<path>: <detail>`, which gives `/x/prod.keys: no such file: /x/prod.keys`. The comment on line 28 avoids this for the other details, but not for this one.
**Fix:** Use `'no such file'` (and `'cannot read: …'`) without the path. The GUI already puts the path in front.

### IN-03: The `.desktop` `TryExec` and `Icon` values are not string-escaped

**File:** `porter/desktop.py:28`
**Issue:** `Exec` gets both escaping levels, but `TryExec={exe}` and `Icon={icon}` are written raw. A backslash in the folder name would be read as an escape sequence, and `TryExec` would then hide the entry.
**Fix:** Escape backslashes in string values: `exe.replace('\\', '\\\\')` and the same for `icon`.

### IN-04: `devtools/ndk_pin.py` repeats the asset name and tag instead of reading them from the pin

**File:** `devtools/ndk_pin.py:10-11`
**Issue:** `RELEASE` (tag `r27`) and `ASSET` are hard-coded next to `pins.NDK['files']['linux-arm64'][0]`. If the URL is bumped and these two are not, the script checks the old asset and reports PASS.
**Fix:** Take both from the URL, for example `ASSET = row[0].rsplit('/', 1)[1]`, and the tag from the path part before it.

### IN-05: The plain CLI `config legal` skips the version guard, and `--prepare` silently wins over `--download`

**File:** `porter/cli.py:231-241`, `porter/cli.py:216`
**Issue:** The T-03-05 guard (`legal` takes only `setup.VERSION`) applies only with `--json`. `porter config legal 7` stores junk, which then reads as "the notice changed since you accepted it". `tools --download --prepare` runs only Prepare and says nothing.
**Fix:** Apply the `legal` check on both paths. Reject the two flags together with argparse (a mutually exclusive group).

### IN-06: A `.part` left from an in-place re-upload gives a misleading message

**File:** `porter/fetch.py:256-258`, `porter/fetch.py:372`
**Issue:** `download()` keeps `.part` files by file name only. The scenario pins.py documents (the community NDK asset re-uploaded in place under the same name) resumes the old bytes with the new upload's tail, fails the hash, and tells the player to "wait for a pin bump", even when the pin has already been bumped. The next press works.
**Fix:** Name the `.part` after the pinned hash (for example `<name>.<hash[:12]>.part`), so a pin bump never resumes an old upload.

### IN-07: `setup.tool_items` calls the private `fetch._pinned`

**File:** `porter/setup.py:30`
**Issue:** It reaches across modules into a private helper. If `_pinned` is renamed, the setup document silently loses its `download` sizes, because only `ImportError` is caught.
**Fix:** Make it public (`fetch.pinned`) or add a small public `fetch.download_info(name)`.

### IN-08: The `glslc` fallback in `build.py` applies on every host, not only Linux arm64

**File:** `nxnative/dm/android/build.py:81-82`
**Issue:** The comment says it is for a player-built arm64 NDK, but the fallback is not guarded. On any host, an NDK that is missing `shader-tools` (a broken or partial install) quietly builds with whatever `glslc` is on PATH, which can be a different shaderc version. The only sign is a `[RED]` line in the host stage's log.
**Fix:** Guard it the same way as the host-folder rule above it (`sys.platform.startswith('linux') and platform.machine().lower() in ('aarch64', 'arm64')`), or fail with a message that names the missing file.

---

_Reviewed: 2026-10-31_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
