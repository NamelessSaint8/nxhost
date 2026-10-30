# What porter downloads, pinned (PKG-07, D-01): each toolchain by exact version, and per host its URL, size, hash algorithm and hash. fetch.plan() takes
# these first and checks every download against them; only when a vendor no longer serves a pinned file does it take the vendor's newest, marked untested.
# Only downloads are governed: a toolchain the player already has keeps toolchain.checks() (D-04). Data only.
# Bump: change one row (version, URL, size and hash copied by script from Google's repository2-3.xml or Microsoft's releases.json, never by hand),
# run `python -m porter tools --download --only <tool>` on each host and the test suite, commit. Phase 3 adds the community linux-arm64 NDK row (sha256).
# Size 0: the HEAD of the URL gives it.

NDK = {'version': 'r27c', 'files': {
    'windows': ('https://dl.google.com/android/repository/android-ndk-r27c-windows.zip', 781511249, 'sha1', 'ac5f7762764b1f15341094e148ad4f847d050c38'),
    'macosx': ('https://dl.google.com/android/repository/android-ndk-r27c-darwin.zip', 836128272, 'sha1', '0217c10ffbec496bb9fbfbb3c6fc2477c6b77297'),
    'linux': ('https://dl.google.com/android/repository/android-ndk-r27c-linux.zip', 663987688, 'sha1', '090e8083a715fdb1a3e402d0763c388abb03fb4e'),
}}

PLATFORM_TOOLS = {'version': '37.0.1', 'files': {
    'windows': ('https://dl.google.com/android/repository/platform-tools_r37.0.1-win.zip', 8044989, 'sha1', 'e03e78b1d80b396f1c3358e31251cb31740e1110'),
    'macosx': ('https://dl.google.com/android/repository/platform-tools_r37.0.1-darwin.zip', 16110554, 'sha1', '6ae73f4de6452dc57e62ec02b68eed92a4c21661'),
    'linux': ('https://dl.google.com/android/repository/platform-tools_r37.0.1-linux.zip', 9054187, 'sha1', '477254aa5f903c15cf51001717bdf347fb6b53e0'),
}}

DOTNET = {'version': '10.0.403', 'files': {
    'win-x64': ('https://builds.dotnet.microsoft.com/dotnet/Sdk/10.0.403/dotnet-sdk-10.0.403-win-x64.zip', 0, 'sha512', '7a114c318fa7f1d9822991b534b2814d0e78386ceda816b371f5141acefe741d87ccb606ede06cadac8f9ac5070e32b708a67bbd1619ff5e5a7858a27874ef48'),
    'osx-arm64': ('https://builds.dotnet.microsoft.com/dotnet/Sdk/10.0.403/dotnet-sdk-10.0.403-osx-arm64.tar.gz', 0, 'sha512', '5893c66b48ea3674c7da18501059d606e96f3672fabe4d5e41762e692c7c83df3ee0b2b9dc5a0786191da2dc413d7335158101c14c935ab217f31ac2529770f3'),
    'linux-x64': ('https://builds.dotnet.microsoft.com/dotnet/Sdk/10.0.403/dotnet-sdk-10.0.403-linux-x64.tar.gz', 0, 'sha512', 'b7b3d8461cf98b07d2552ce9199702fa3ad010ac2671a5f8cd5136f7534e50f6855ba7bbb02b11494563f1d04156276a31cda1103b900e5eecd0d9473dc7b9c5'),
    'linux-arm64': ('https://builds.dotnet.microsoft.com/dotnet/Sdk/10.0.403/dotnet-sdk-10.0.403-linux-arm64.tar.gz', 0, 'sha512', '0966aa2b70f4677b8319be9df447a78a0dcd6164836425b55a68fd714f4023feb87b4cac21b9a996b79472ad54487cd0adcd2a9dfd570e2b2a1d26423a2baa9b'),
}}

# masagrator/FPSLocker-Warehouse: the v4 head on 2026-10-29. --fps60 fetches each build's config at this commit (D-03); a build the commit has no config for
# falls back to v4's head, flagged untested in the port log. Bump: set the new SHA after a port with --fps60 works on it (one line).
FPSLOCKER = '575eef0824e3519e6567c3fdb27707136448923a'
