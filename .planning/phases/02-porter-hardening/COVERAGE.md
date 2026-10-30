# Phase 2: API coverage

Porter builds no API client in this phase. It keeps downloading vendor files it already fetched (Google's SDK repository, Microsoft's .NET release list, FPSLocker-Warehouse configs, NuGet packages through `dotnet restore`) and pins them by version and hash. The only REST call it adds is one unauthenticated GitHub request for the `v4` branch's head commit (plan 02-08). The detector fired on "SDK" (the probe app's signer, plan 02-02) and on "API" (that GitHub call).

| capability | decision | reason |
|---|---|---|
| GitHub REST: the `v4` head commit SHA (`GET /repos/masagrator/FPSLocker-Warehouse/commits/v4`, `Accept: application/vnd.github.sha`, plan 02-08) | INTEGRATE | |
| raw.githubusercontent.com: a config at a pinned commit (plan 02-08) | INTEGRATE | |
| Google SDK repository index and archives, pinned (plan 02-04) | INTEGRATE | |
| Microsoft .NET release list and SDK archives, pinned (plan 02-04) | INTEGRATE | |
| NuGet restore of the engine's existing packages, checked against pins (plan 02-10) | INTEGRATE | |
| GitHub authentication (token) for higher rate limits | OPT-OUT | one call per port that needs it, after the pinned commit has no config; a refused call takes the cached-copy path (RESEARCH A8) |
| GitHub contents/trees API to list configs | OPT-OUT | the config path is known from the title and build IDs; a 404 on the raw URL answers "no config" |
| NuGet lock files (`packages.lock.json`, `--locked-mode`) | OPT-OUT | the developer chose pins in porter/pins.py only, with no new file in the nxnative subtree (D-05) |
