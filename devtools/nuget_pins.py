# Prints porter/pins.py's NUGET block: the content hash of every NuGet package nx_extract and the shader translator (dmsh_xlate) restore, read from a real
# restore into a fresh temporary NUGET_PACKAGES folder (network and .NET SDK 10 needed). Run it after changing a .csproj or Directory.Packages.props, paste
# the output into porter/pins.py and run the tests. The obj/ folders the restore leaves in the engine are build outputs: do not commit them.
#   python devtools/nuget_pins.py
import os, subprocess, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from porter import nuget                    # noqa: E402
from porter.paths import DM, NXNATIVE       # noqa: E402
from porter.toolchain import find_dotnet    # noqa: E402

PROJECTS = [NXNATIVE / 'dm/tools/nx_extract', DM / 'gfx/tools/dmsh_xlate']


def main():
    dotnet = find_dotnet()
    if not dotnet: sys.exit('no dotnet found: install the .NET SDK 10 or set it with `python -m porter config dotnet <path>`')
    got = {}
    with tempfile.TemporaryDirectory(prefix='nx2a_nuget_') as t:
        env = dict(os.environ, NUGET_PACKAGES=t, DOTNET_ROOT=str(dotnet.parent), DOTNET_CLI_TELEMETRY_OPTOUT='1')
        for p in PROJECTS:
            subprocess.run([str(dotnet), 'restore', str(p), '--nologo', '-v', 'quiet'], env=env, check=True); got.update(nuget.hashes(p))
    none = sorted(k for k, (h, _) in got.items() if not h)
    if none: sys.exit(f'no content hash (sha512) in obj/project.assets.json for: {", ".join(none)}')
    print('NUGET = {'); print(''.join(f"    '{k}': '{got[k][0]}',\n" for k in sorted(got)), end=''); print('}')


if __name__ == '__main__':
    main()
