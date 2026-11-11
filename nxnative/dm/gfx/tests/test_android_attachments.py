"""A shared pass can contain several different native mesh pipelines."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]/'probes'))
from extract_nvn2_attachments import extract, fixture_rows


class Attachments(unittest.TestCase):
    def test_latest_draw_state_and_ambiguous_depth(self):
        lines = ['[pass] F1 P 7 c0 ser=1 fmt=115 128x128 ms1 lv0 sl0 load',
                 '[pass] F1 P 7 d ser=2 fmt=260 128x128 load']
        for mesh, pixel in [('11', '21'), ('12', '22'), ('11', '21')]:
            lines.extend([f'[pass] F1 d 7 vs={mesh}_b fs={pixel}_b blend=0xff b0=0x482040810 dt=1 dw=0 df=4 cull=0 st=0 cmask=0xffffffff po=0/0,0,0 dc=0',
                          f'[pass] F1 n 7 NVN2 mesh first=0 groups=1 task=- mesh={mesh}_b'])
        report = extract('\n'.join(lines))
        self.assertEqual(report['sampled_native_draws'], 3)
        self.assertEqual([r['sampled_draws'] for r in report['contexts']], [2, 1])
        self.assertEqual([r['pixel'] for r in report['contexts']], ['21', '22'])
        rows = fixture_rows(report)
        self.assertEqual(len(rows), 4)
        self.assertEqual({r.split()[4] for r in rows}, {'35', '36'})
        with self.assertRaises(ValueError):
            extract('\n'.join(lines).replace('st=0', 'st=1'))


if __name__ == '__main__':
    unittest.main()
