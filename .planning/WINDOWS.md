---
schema_version: 1
open_count: 1
waived_count: 0
fixed_count: 0
total_count: 1
last_updated: 2026-11-04T16:11:41.702Z
---

# Broken Windows Ledger

> Cross-phase defect register. `/gsd-ship` blocks while `open_count > 0`.
> Waive with `gsd-tools windows waive <id> "<reason>"` (reason required).
> Mark fixed with `gsd-tools windows fixed <id>`.

| id | phase | kind | file | line | description | status | reason | recorded_at | resolved_at |
|----|-------|------|------|------|-------------|--------|--------|-------------|-------------|
| 1 | 11 | unrun-verify | .github/workflows/host-build.yml |  | host-build.yml's two jobs have not run on a GitHub runner yet: the first push or PR touching nxnative/** or .github/** is the only place the Apple link and the Android link are proven | open |  | 2026-11-04T16:11:41.702Z |  |

````json
[
  {
    "id": 1,
    "kind": "unrun-verify",
    "phase": "11",
    "file": ".github/workflows/host-build.yml",
    "line": null,
    "description": "host-build.yml's two jobs have not run on a GitHub runner yet: the first push or PR touching nxnative/** or .github/** is the only place the Apple link and the Android link are proven",
    "status": "open",
    "reason": "",
    "recorded_at": "2026-11-04T16:11:41.702Z",
    "resolved_at": null
  }
]
````
