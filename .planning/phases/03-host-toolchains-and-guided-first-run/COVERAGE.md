# Phase 3: API coverage

Porter builds no API client in this phase. It adds one pinned file download (the community linux-arm64 NDK from a GitHub release), HTTP Range resume on the vendor downloads it already makes, and one unauthenticated GitHub REST read in a developer script. The detector fired on "SDK" (the .NET SDK and the Android SDK folders) and on "API" (that GitHub read).

| capability | decision | reason |
|---|---|---|
| Community linux-arm64 NDK r27c GitHub release asset, pinned by sha256 | INTEGRATE | HomuHomu833 android-ndk-custom r27, `android-ndk-r27c-aarch64-linux-gnu.tar.xz` (plan 03-03) |
| HTTP Range resume of pinned vendor downloads | INTEGRATE | dl.google.com, builds.dotnet.microsoft.com and GitHub release assets (plan 03-03) |
| GitHub REST: `releases/tags/r27` asset size and digest | INTEGRATE | read by devtools/ndk_pin.py before a release (plan 03-08) |
| .NET SDK and Android SDK folders: detection, version and source | INTEGRATE | plans 03-02, 03-04 |
| GitHub authentication (token) for the REST read | OPT-OUT | one unauthenticated call by hand before a release; far below the anonymous rate limit |
| Other community NDK assets (other hosts, musl builds, other NDK revisions) | OPT-OUT | not needed: only the linux-arm64 r27c gnu build is pinned (D-08) |
| Updating the pin from the API's digest automatically | OPT-OUT | explicitly out of scope: a pin changes only by a reviewed commit, and a mismatch always stops (Phase 2 D-01, D-08) |
