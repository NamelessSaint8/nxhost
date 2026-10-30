# porter/fetch.py and porter/pins.py: the toolchain downloads are the pinned files or a visibly untested fallback, a wrong hash stops naming both hashes,
# and hostile zip and tar archives are refused whole and leave nothing behind. urlopen and the vendor indexes are faked: no network, no real toolchain.
import hashlib, io, json, os, sys, tempfile, unittest, urllib.error
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
HOME = Path(tempfile.mkdtemp()); os.environ['NX2A_HOME'] = str(HOME)   # player_tools() lands here

MISSING = None
for _m in ('lz4.block', 'capstone'):   # porter.fetch imports porter.upstream, which needs lz4
    try: __import__(_m)
    except ModuleNotFoundError:
        if os.environ.get('CI'): raise   # CI installs the lock: a missing module there is a failure
        MISSING = MISSING or _m


def setUpModule():
    if MISSING: raise unittest.SkipTest(f'{MISSING} is not installed (python -m pip install -r requirements.txt)')
    os.environ['NX2A_HOME'] = str(HOME)   # again: discovery imports other test modules that set their own


class Resp(io.BytesIO):
    def __init__(self, body, headers): super().__init__(body); self.headers = headers


def fake(table, seen=None):   # urlopen answering from {url: status or (status, headers, body)}; an unknown URL is a 404
    def urlopen(req, timeout=None, context=None):
        url = req.full_url; v = table.get(url, 404)
        if seen is not None: seen.append((req.get_method(), url))
        st, hd, body = v if isinstance(v, tuple) else (v, {}, b'')
        if st >= 400: raise urllib.error.HTTPError(url, st, 'gone', {}, None)
        return Resp(body, hd)
    return urlopen


HOSTS = ('windows', 'macosx', 'linux')
RIDS = ('win-x64', 'osx-arm64', 'osx-x64', 'linux-x64', 'linux-arm64')
REPO_XML = ('<repo><remotePackage path="platform-tools"><revision><major>38</major><minor>0</minor><micro>0</micro></revision><archives>'
            + ''.join(f'<archive><complete><size>5</size><checksum type="sha1">{h[0] * 40}</checksum><url>platform-tools_r38.0.0-{h}.zip</url></complete>'
                      f'<host-os>{h}</host-os></archive>' for h in HOSTS) + '</archives></remotePackage></repo>').encode()
KIND = '.zip' if sys.platform == 'win32' else '.tar.gz'
NEW_DN = 'https://builds.dotnet.microsoft.com/dotnet/Sdk/10.0.500/dotnet-sdk-10.0.500-{}' + KIND


def releases():   # newest first, as Microsoft lists them
    rel = lambda v, url, c: {'sdk': {'version': v, 'files': [{'rid': r, 'name': f'dotnet-sdk-{r}{KIND}', 'url': url.format(r), 'hash': c * 128} for r in RIDS]}, 'sdks': []}
    return json.dumps({'releases': [rel('10.0.500', NEW_DN, 'e'), rel('10.0.403', 'https://x/old-{}', 'd')]}).encode()


class Pins(unittest.TestCase):
    def setUp(self):
        from porter import fetch, pins
        self.fetch, self.pins = fetch, pins
        for name, val in (('_google_os', lambda: 'macosx'), ('_dotnet_rid', lambda: 'osx-arm64')):   # the same rows on every CI host
            p = mock.patch.object(fetch, name, val); p.start(); self.addCleanup(p.stop)

    def urls(self, *drop):   # every pinned URL of this (patched) host answering HEAD 200, but those in drop
        f = self.pins
        rows = {'ndk': f.NDK['files']['macosx'], 'adb': f.PLATFORM_TOOLS['files']['macosx'], 'dotnet': f.DOTNET['files']['osx-arm64']}
        return {r[0]: (200, {'Content-Length': '123'}, b'') for k, r in rows.items() if k not in drop}, rows

    def plan(self, table, index=None, names=('Android NDK', 'adb', '.NET SDK')):
        get = mock.Mock(side_effect=index or AssertionError('an index was fetched'))
        with mock.patch.object(self.fetch.urllib.request, 'urlopen', fake(table)), mock.patch.object(self.fetch, '_get', get): return self.fetch.plan(list(names)), get

    def test_rows_complete(self):
        p = self.pins
        self.assertEqual(set(p.NDK['files']), set(HOSTS)); self.assertEqual(set(p.PLATFORM_TOOLS['files']), set(HOSTS))
        self.assertEqual(set(p.DOTNET['files']), {'win-x64', 'osx-arm64', 'linux-x64', 'linux-arm64'})
        for pin in (p.NDK, p.PLATFORM_TOOLS, p.DOTNET):
            for host, (url, size, algo, h) in pin['files'].items():
                with self.subTest(host=host, url=url):
                    self.assertTrue(url.startswith('https://')); self.assertIsInstance(size, int)
                    self.assertRegex(h, {'sha1': r'^[0-9a-f]{40}$', 'sha512': r'^[0-9a-f]{128}$'}[algo])

    def test_pinned_row_used(self):
        table, rows = self.urls()
        items, get = self.plan(table)
        get.assert_not_called()
        for it, k, pin in zip(items, ('ndk', 'adb', 'dotnet'), (self.pins.NDK, self.pins.PLATFORM_TOOLS, self.pins.DOTNET)):
            with self.subTest(it.name):
                self.assertEqual((it.url, it.algo, it.hash, it.version), (rows[k][0], rows[k][2], rows[k][3], pin['version']))
                self.assertFalse(it.untested); self.assertTrue(it.size)

    def test_adb_gone_falls_back(self):
        table, _ = self.urls('adb')
        (it,), _ = self.plan(table, index=lambda url: REPO_XML, names=['adb'])
        self.assertEqual((it.version, it.hash, it.algo), ('38.0.0', 'm' * 40, 'sha1')); self.assertTrue(it.untested)
        self.assertTrue(it.url.endswith('platform-tools_r38.0.0-macosx.zip'))

    def test_dotnet_gone_falls_back(self):
        table, rows = self.urls('dotnet'); table[rows['dotnet'][0]] = 410; table[NEW_DN.format('osx-arm64')] = (200, {'Content-Length': '9'}, b'')
        (it,), _ = self.plan(table, index=lambda url: releases(), names=['.NET SDK'])
        self.assertEqual((it.version, it.url, it.hash, it.size), ('10.0.500', NEW_DN.format('osx-arm64'), 'e' * 128, 9)); self.assertTrue(it.untested)

    def test_ndk_gone_stops(self):
        from porter.upstream import BuildError
        table, rows = self.urls('ndk')
        with self.assertRaises(BuildError) as cm: self.plan(table, index=lambda url: REPO_XML, names=['Android NDK'])
        self.assertIn(rows['ndk'][0], str(cm.exception)); self.assertIn('r27c', str(cm.exception))

    def test_no_row_is_untested(self):
        table = {NEW_DN.format('osx-x64'): (200, {'Content-Length': '9'}, b'')}
        with mock.patch.object(self.fetch, '_dotnet_rid', lambda: 'osx-x64'): (it,), get = self.plan(table, index=lambda url: releases(), names=['.NET SDK'])
        get.assert_called(); self.assertEqual(it.url, NEW_DN.format('osx-x64')); self.assertTrue(it.untested)

    def test_mismatch_names_both_hashes(self):
        from porter.upstream import BuildError
        d = Path(tempfile.mkdtemp()); url = 'https://h/x/tool.zip'
        it = self.fetch.Item('adb', '1', url, 5, '0' * 40, 'sha1', 'platform-tools', '')
        with mock.patch.object(self.fetch.urllib.request, 'urlopen', fake({url: (200, {'Content-Length': '5'}, b'hello')})), self.assertRaises(BuildError) as cm:
            self.fetch._download(it, d / 'tool.zip')
        msg = str(cm.exception)
        for s in ('tool.zip', '0' * 40, hashlib.sha1(b'hello').hexdigest()): self.assertIn(s, msg)
        self.assertEqual(list(d.iterdir()), [])


if __name__ == '__main__': unittest.main()
