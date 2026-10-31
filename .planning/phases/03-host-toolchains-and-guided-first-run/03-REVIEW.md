---
phase: 03-host-toolchains-and-guided-first-run
reviewed: 2026-10-31T19:23:30Z
depth: standard
files_reviewed: 10
files_reviewed_list:
  - docs/ARCHITECTURE.md
  - gui/app.py
  - gui/firstrun.py
  - gui/runner.py
  - porter/fetch.py
  - porter/probe.py
  - tests/test_bridge.py
  - tests/test_fetch.py
  - tests/test_firstrun.py
  - tests/test_probe.py
findings:
  critical: 0
  warning: 2
  info: 3
  total: 5
status: issues_found
---

# Phase 3: Code Review Report (incremental re-review after gap closure 03-13..03-15)

**Reviewed:** 2026-10-31T19:23:30Z
**Depth:** standard
**Files Reviewed:** 10
**Status:** issues_found

## Summary

This review covers `git diff 8efba60..HEAD` for the 10 listed files, and checks each finding from the previous review that was marked fixed. The four touched test modules pass (179 tests, `QT_QPA_PLATFORM=offscreen`). Deferred findings IN-02..IN-08 were not raised again. None of them got worse.

Status of the previously fixed findings:

| Prior | Verdict | Evidence |
|-------|---------|----------|
| CR-01 | Fixed | `SetupTab.save` (gui/app.py:363-367) writes only fields that differ from `self.loaded`, and `load()` (357-361) refreshes untouched fields. A value the wizard saved through `porter config` is no longer written over, even with no re-check in between. |
| WR-01 | Fixed | porter/fetch.py:135-140: a clean close before `Content-Length` raises `ConnectionResetError`, and `http.client.HTTPException` (`IncompleteRead`) is caught at :143. Both cases are retried and resumed. The fix is tested over a real loopback socket. |
| WR-02 | **Partly fixed** | 150 s covers the probe and adb, but not dotnet's own 60 s limits. See WR-02 below. |
| WR-03 | Fixed | porter half: `mkstemp` gives each process its own temp file, and a failed write is ignored (probe.py:62-68). GUI half: `SetupTab.check` runs one `setup --json` at a time and folds extra requests into one more run (app.py:371-380). |
| WR-04 | Fixed | `Porter.start` refuses a second run (runner.py:58). `confirm_download` checks before and after its dialog (app.py:302, 313). `ToolsPage.start` checks first (firstrun.py:379). |
| WR-05 | Fixed | `ToolsPage.on_finished` does not chain Prepare while quitting (firstrun.py:404), and `start()` refuses on a quitting window (379). |
| WR-06 | Fixed | probe.py:49-51 quotes the paths with `shlex.quote` and keeps the glob outside the quotes. |
| IN-01 | Fixed | `Gate.start` has been removed. Nothing refers to it. |

New findings: the 03-14 layout edit caused one regression (WR-01). The WR-02 limit was worked out from an incomplete list of what `setup --json` runs, and the test and the docs repeat the same wrong bound (WR-02). There are also three small copy and consistency items.

## Warnings

### WR-01: A re-check while the device page is open resets Next to "Skip: install later" even when a device is ready

**File:** `gui/firstrun.py:449-451`
**Issue:** 03-14 Task 2 added `DevicePage.redraw` directly above what used to be the last line of `__init__`. That line, `self.setButtonText(QWizard.NextButton, 'Skip: install later')`, is now the body of `redraw`. `redraw` runs on every `setup --json` answer (`on_ready` → `Wizard.redraw`). Several things trigger one while the device page is showing: a download or the chained Prepare ending (`ToolsPage.on_finished` → `win.recheck()`), Save and check, or Retry. Each time, the button falls back to "Skip: install later" after `draw()` had set "Next" for a ready device. The label is only fixed by the next `devices --json` answer, `POLL_MS` (2.5 s) later. `draw()` returns early on a failed call (`if fail: ... return`, line 471), so while adb is failing the wrong label stays. The done page's summary uses `seen_device`, so it is unaffected; only the button text is wrong. No test covers it: the wizard calls `redraw` once at construction, which still produces the correct initial label.
**Fix:** Put the line back in `__init__`. Optionally, have `redraw` use the same rule as `draw`:
```python
    def __init__(self):
        ...
        self.v.addStretch(1)
        self.setButtonText(QWizard.NextButton, 'Skip: install later')

    def redraw(self, doc):   # an ok device step's detail is only the adb path ...
        super().redraw(doc); self.detail.setVisible(not step(doc, self.SID)['ok'])
```
Add a test: open the device page with one ready device, wait for "Next", call `w.recheck()` and wait for the answer, then assert the label is still "Next".

### WR-02: The 150 s `setup` limit ignores dotnet's own 60 s limits; the test and the docs repeat the incomplete bound

**File:** `gui/runner.py:16-19`, `tests/test_bridge.py:435-438`, `docs/ARCHITECTURE.md:102`
**Issue:** The new limit is justified as "the NDK probe's two 60 s steps plus adb version (15 s)", and the test asserts exactly that: `TIMEOUTS['setup'] > 2 * probe.TIMEOUT + 15`. But `toolchain.checks()`, which `setup --json` runs, also starts `dotnet --list-sdks` with `timeout=60` at least twice. `find_dotnet` calls `dotnet_sdks` for each candidate until one has SDK 10 or later (porter/toolchain.py:76-83), and `checks()` calls `dotnet_sdks(dn)` again (toolchain.py:137). The worst case for one run is 2×60 (probe) + 2×60 or more (dotnet) + 15 (adb) = 255 s or more, well over 150. This is the same cold-disk case WR-02 was about: the check right after a download has just installed both the NDK and .NET. Mitigation: the probe runs first and caches its pass before dotnet starts, so a run killed during the dotnet steps still leaves the probe cached, and Retry usually succeeds. The actual failure is one spurious "nx2android didn't answer in 150 s". But the documented rule ("above the probe's limits ... a killed run caches nothing") and the test pin a bound that does not hold.
**Fix:** Either size the limit from every child porter's `setup` can start, or cap dotnet's own wait. Then make the test assert the real sum:
```python
# gui/runner.py: 2 probe steps + find_dotnet's and checks()'s dotnet --list-sdks + adb version, with headroom
TIMEOUTS = {..., 'setup': 300, ...}
# tests/test_bridge.py
self.assertGreater(runner.TIMEOUTS['setup'], 2 * probe.TIMEOUT + 2 * 60 + 15)
```
A cheaper option is to call `dotnet_sdks` once per candidate in `checks()` (reuse `find_dotnet`'s result) and lower `--list-sdks` to about 20 s; that call only lists folders. Whichever way you go, update the `setup` sentence in ARCHITECTURE.md:102 to name dotnet.

## Info

### IN-01: The device combo's tooltip still says "porter"

**File:** `gui/app.py:151`
**Issue:** The item text now uses `firstrun.cause(fail)`, but the tooltip fallback still calls gui/app.py's own `cause(fail)`: `setItemData(0, fail['stderr'] or cause(fail), Qt.ToolTipRole)`. On a timeout, or an `{"error"}` with no stderr, players see "porter didn't answer in 45 s" when they hover. UI fix 2 and ARCHITECTURE.md:102 both say the device list never shows "porter". The test (test_bridge.py:163-165) only checks the item text.
**Fix:** `self.device.setItemData(0, fail['stderr'] or firstrun.cause(fail), Qt.ToolTipRole)`.

### IN-02: The Setup tab's download-failure line still uses a hardcoded `#c62828`

**File:** `gui/app.py:342`
**Issue:** `check_msg` above it now takes its colour from the palette (`firstrun.failed` → `colour(None, 'bad')`), but `fetched()`'s failure line still hardcodes light-theme red. On a dark palette the two error lines in one group box use different reds, and this one has the low contrast UI fix 3 was meant to remove.
**Fix:** `'<span style="color:%s">' % firstrun.colour(self, 'bad') + ...`.

### IN-03: A config value with leading or trailing whitespace counts as "typed" forever and is saved stripped

**File:** `gui/app.py:357-367`
**Issue:** `load()` compares `e.text().strip()` with the raw `self.loaded[k]`. A saved value like `"/path/prod.keys "` is legal on POSIX, and `porter config` does not strip. Such a value never compares equal after `setText`, so the field is never refreshed from config.json again. `save()` then sees it as changed and writes the stripped path, which points at a different file. This brings back a narrow form of CR-01 for such values.
**Fix:** Compare unstripped values in `load()` (`if e.text() == self.loaded.get(k, '')`), and strip only the value `save()` writes.

---

_Reviewed: 2026-10-31T19:23:30Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
