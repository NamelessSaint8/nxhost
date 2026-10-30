---
phase: 01-bridge-bundles-and-ci
reviewed: 2026-10-30T07:50:25Z
depth: standard
files_reviewed: 7
files_reviewed_list:
  - porter/tls.py
  - porter/fetch.py
  - porter/fpslocker.py
  - tests/test_tls.py
  - packaging/hooks/hook-PySide6.QtGui.py
  - packaging/hooks/hook-PySide6.QtNetwork.py
  - packaging/nx2android.spec
findings:
  critical: 0
  warning: 3
  info: 3
  total: 6
status: issues_found
---

# Phase 01: Code Review Report

**Reviewed:** 2026-10-30T07:50:25Z
**Depth:** standard
**Files Reviewed:** 7
**Status:** issues_found

## Summary

This is an incremental review of gap-closure plans 01-09 (G-01-6: one SSL context for every HTTPS call in `porter/`) and 01-10 (G-01-7: PyInstaller hook overrides that keep the GTK3/GIO stack out of the Linux bundles). For `porter/fetch.py`, `porter/fpslocker.py` and `packaging/nx2android.spec`, only the changes since `5e240ef` were reviewed. The earlier 36-file review is in git history.

Checks that passed:
- All four `urlopen` calls in `porter/` pass `context=tls.context()`. No other HTTPS client exists in `porter/`, `gui/`, `nxnative/scripts` or `nxnative/dm/android`. `packaging/build_bootloader.py` uses a bare `urlopen`, but it only runs on the build host.
- `tls.context()` never lowers `verify_mode` or `check_hostname` and never writes the environment.
- The fallback's `ssl.SSLError` and `PermissionError` are both `OSError`, so `pipeline.py`'s `fps_unlock` handler (`except OSError`) and the `porter tools` error path still catch them.
- Apart from the filter line, both hooks are byte-for-byte copies of the stock PyInstaller 6.22.3 hooks (checked with `diff` against `.venv`).
- User `hookspath` hooks get `HOOK_PRIORITY_USER_HOOKS` and replace the stock hooks (`build_main.py:525-533`, `imphook.py:128-136`). PySide6 registers no `pyinstaller40` hook directory of its own.
- `collect_module` adds a hidden import instead of plugins for any Qt library that has a Python module. So `platformthemes` comes only from the QtGui hook and `networkinformation` only from the QtNetwork hook. Filtering in those two hooks is enough.
- `build_bundle.py` runs PyInstaller with `--clean`, so edits to the hooks are not hidden by a cached Analysis.
- The test fixture is a public certificate only (no `PRIVATE` block), with CA:TRUE, valid until 2126.
- `tests/test_tls.py` passes (5 tests).

No blockers. There are three warnings: the CA fallback runs on Windows, where the POSIX paths resolve against the current drive; the urlopen scan test is weaker than the contract it pins; and the copied stock hooks have no guard against PyInstaller version drift.

## Warnings

### WR-01: The CA-file fallback can run on Windows, where `/etc/ssl/...` resolves against the current drive

**File:** `porter/tls.py:19-24`
**Issue:** `context()` does not check the OS. On Windows, `/etc/ssl/cert.pem` has no drive letter, so it resolves against the current drive (`ntpath.isabs('/etc/ssl/cert.pem')` is `False` on 3.13+; `splitdrive` gives `''`). If the Windows ROOT/CA enumeration ever returns 0 CAs, `os.path.isfile` checks `C:\etc\ssl\cert.pem` or `D:\etc\ssl\...`, depending on the working directory. By default any authenticated user can create folders at `C:\`, and a data or exFAT drive (where game dumps often sit) usually has no ACL at all. A CA planted there would then be trusted for the NDK, .NET and platform-tools downloads. Those downloads are checked against hashes that arrive over the same TLS, so TLS is the only root of trust. The precondition (empty Windows stores) is rare, but the plan says "Windows needs nothing", and the code does not enforce that.
**Fix:** Keep the fallback to POSIX hosts:
```python
if c.cert_store_stats()['x509_ca'] or os.name == 'nt': return c   # Windows: the system stores; never read drive-relative /etc paths
```
Add a test that patches `tls.os.name` to `'nt'` with the empty default and asserts that `isfile` is not called.

### WR-02: The urlopen scan test accepts any `context=`, not `context=tls.context()`

**File:** `tests/test_tls.py:41-49`
**Issue:** The plan's must-have says "Every urllib.request.urlopen call in porter/ passes context=tls.context(); a new call without it fails tests/test_tls.py". The test only checks `'context=' not in code`. So `urlopen(req, context=ssl._create_unverified_context())`, which is the most likely "quick fix" for a CERTIFICATE_VERIFY_FAILED report, or `context=None`, passes the test. The test also fails a correct `urlopen(` call whose `context=` argument is on the next line.
**Fix:** Pin the exact argument, and scan the logical statement instead of the physical line (or at least the exact substring):
```python
if 'context=tls.context()' not in code: bare.append(...)
```
To survive wrapping, use `ast`: walk `ast.Call` nodes whose func ends in `urlopen` and require a `context` keyword whose value is `tls.context()`.

### WR-03: The hook overrides are copies of PyInstaller 6.22.3's hooks, with nothing that fails when PyInstaller moves

**File:** `packaging/hooks/hook-PySide6.QtGui.py:1`, `packaging/hooks/hook-PySide6.QtNetwork.py:1` (and `requirements-build.in`: `pyinstaller==6.22.*`)
**Issue:** The overrides replace the stock hooks completely (user priority). Their headers say "copy the stock hook again on a PyInstaller upgrade", but `requirements-build.in` allows any 6.22.x. Running `uv pip compile` again can move to 6.22.4+. If that release changes either stock hook (new plugin types, a new `collect_*` call, a fix for a Qt bump), the bundle silently keeps the old logic. The spec's GTK guard only catches libgio or GTK coming back. It does not catch a stock-hook change being lost.
**Fix:** Make the drift fail the build. Either assert the version in each hook (or once in the spec):
```python
import PyInstaller
assert PyInstaller.__version__ == '6.22.3', 'packaging/hooks/ copy PyInstaller 6.22.3 hooks: copy the stock hooks again, then bump this'
```
or add a test, skipped when PyInstaller is absent, that compares each override minus its header and filter line with `PyInstaller/hooks/<same name>`.

## Info

### IN-01: Only the first existing CA file is tried; an unreadable or empty one fails the download instead of falling through

**File:** `porter/tls.py:22-23`
**Issue:** `next(p for p in ca_files if os.path.isfile(p))` picks the first file that exists. If that file cannot be read (`PermissionError`) or holds no certificate (`ssl.SSLError`), `load_verify_locations` raises, and every download fails, even when a later candidate is valid. It still fails safely (no unverified fallback), and truststore behaves the same way, so this is a robustness note only.
**Fix:** Loop over the candidates and `try: c.load_verify_locations(cafile=p); break` / `except (OSError, ssl.SSLError): continue`.

### IN-02: `x509_ca` does not count a capath store, so the "used as it is" contract is not exact

**File:** `porter/tls.py:21` (comment and docstring)
**Issue:** OpenSSL loads certificates from a hashed CA directory (`SSL_CERT_DIR`, or an OPENSSLDIR with only `certs/`) lazily, so `cert_store_stats()` reports 0 for them. When a player sets only `SSL_CERT_DIR`, the fallback adds the host bundle on top of their directory, which contradicts the plan's "a default store that holds CAs is used as it is". Verification still works (the set of trusted CAs only grows), so nothing breaks today.
**Fix:** Treat `os.environ.get('SSL_CERT_DIR')` as a working default, or note the capath exception in the docstring.

### IN-03: `test_no_host_file_stays_verifying` asserts the mock's own defaults

**File:** `tests/test_tls.py:28-30`
**Issue:** `empty()` returns `SSLContext(PROTOCOL_TLS_CLIENT)`, which is already `CERT_REQUIRED` with `check_hostname=True`. `tls.context()` never touches either setting, so the assertions only catch an explicit downgrade added to the fallback branch. That is the intent, but the test name suggests more than it covers.
**Fix:** None needed. If you want broader coverage, also run the assertion on the `test_empty_default_takes_first_host_file` path, so that a downgrade inside the load branch is caught too.

---

_Reviewed: 2026-10-30T07:50:25Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
