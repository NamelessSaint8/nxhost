# Compares porter/pins.py's community linux-arm64 NDK row with what GitHub serves now. The maintainer re-uploads the asset in place at times (RESEARCH
# Pitfall 1), and then every arm64 player's download fails its sha256 (D-08) until the row is bumped. Run it before a release; exit 1 on a difference.
#   python devtools/ndk_pin.py
import json, sys, urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from porter import pins, tls   # noqa: E402

RELEASE = 'https://api.github.com/repos/HomuHomu833/android-ndk-custom/releases/tags/r27'
ASSET = 'android-ndk-r27c-aarch64-linux-gnu.tar.xz'


def compare(release, row):
    """One line per difference between the release's asset (GitHub's `size` and `digest` "sha256:<hex>") and the pin (url, size, algorithm, hash)"""
    a = next((a for a in release.get('assets') or [] if a.get('name') == ASSET), None)
    if a is None: return [f'{ASSET} is not in the release any more']
    out = []
    if a.get('size') != row[1]: out.append(f"size: pinned {row[1]}, published {a.get('size')}")
    if a.get('digest') != f'{row[2]}:{row[3]}': out.append(f"digest: pinned {row[2]}:{row[3]}, published {a.get('digest')}")
    return out


def main():
    req = urllib.request.Request(RELEASE, headers={'User-Agent': 'nx2android', 'Accept': 'application/vnd.github+json'})
    with urllib.request.urlopen(req, context=tls.context(), timeout=60) as r: release = json.load(r)
    diff = compare(release, pins.NDK['files']['linux-arm64'])
    for d in diff: print(f'[RED] {d}')
    if not diff: print(f'PASS {ASSET} matches porter/pins.py')
    return 1 if diff else 0


if __name__ == '__main__':
    sys.exit(main())
