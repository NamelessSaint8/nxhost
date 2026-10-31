# Reads the member list and the link entries of every zip pinned in porter/pins.py by HTTP Range requests (the central directory and each link's few bytes,
# not the whole file; network needed), runs porter's own link rule (fetch._top, fetch._link_refusal) over the full member list, prints one line per archive
# and writes tests/fixtures/zip_links.json, the link tables LinkRule.test_pinned_archives_pass checks offline. Run it after bumping a pinned NDK,
# platform-tools or .NET zip, then run the tests.
#   python devtools/zip_links.py
import io, json, stat, sys, urllib.request, zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from porter import fetch, pins, tls   # noqa: E402

FIXTURE = HERE.parent / 'tests' / 'fixtures' / 'zip_links.json'


class Remote(io.RawIOBase):   # a seekable read-only file over one URL, each read one Range request
    def __init__(self, url):
        self.url, self.pos, self.size = url, 0, fetch._head(url)
        if not self.size: sys.exit(f'{url}: the server names no size (Content-Length)')

    def readable(self): return True
    def seekable(self): return True
    def tell(self): return self.pos

    def seek(self, off, whence=0):
        self.pos = {0: off, 1: self.pos + off, 2: self.size + off}[whence]; return self.pos

    def readinto(self, b):
        if self.pos >= self.size: return 0
        end = min(self.pos + len(b), self.size) - 1
        req = urllib.request.Request(self.url, headers={'User-Agent': 'nx2android', 'Range': f'bytes={self.pos}-{end}'})
        with urllib.request.urlopen(req, timeout=60, context=tls.context()) as r:
            # a server that ignores Range answers 200 with the whole file, which would be read as the asked bytes
            if r.status != 206: sys.exit(f'{self.url}: answered {r.status} to a Range request, not 206')
            data = r.read()
        b[:len(data)] = data; self.pos += len(data); return len(data)


def main():
    table, bad = {}, False
    for name, pin in (('Android NDK', pins.NDK), ('adb', pins.PLATFORM_TOOLS), ('.NET SDK', pins.DOTNET)):
        for url, size, algo, h in pin['files'].values():
            if not url.endswith('.zip'): continue
            file = Path(url).name
            with zipfile.ZipFile(io.BufferedReader(Remote(url), 1 << 16)) as z:
                infos = z.infolist(); names = [i.filename for i in infos]
                links = {i.filename: z.read(i).decode('utf-8', 'replace') for i in infos if stat.S_ISLNK(i.external_attr >> 16)}   # zipfile checks each CRC
            top = fetch._top(names, fetch.FOLDERS[name])
            if reason := fetch._link_refusal(names, links, top): print(f'[RED] {file}: refused, {reason}'); bad = True
            else: print(f'{file}: {len(names)} members, {len(links)} links, installed from {top or "the whole archive"}: ok')
            table[file] = {'url': url, 'hash': h, 'members': len(names), 'top': top, 'links': links}
    if bad: sys.exit('a pinned archive is refused: the fixture is not written (a refused layout is never recorded as passing)')
    FIXTURE.parent.mkdir(exist_ok=True)
    FIXTURE.write_text(json.dumps(table, indent=1, sort_keys=True) + '\n', encoding='utf-8', newline='\n')
    print(f'wrote {FIXTURE.relative_to(HERE.parent)}')


if __name__ == '__main__':
    main()
