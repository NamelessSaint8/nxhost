#!/usr/bin/env python3
"""The three Ampere opcodes Mario Kart World's shaders use that the decoder lacked, at the encodings the game ships: UP2UR (0x883, 29 of its pixel
shaders), SURED.D.2D.ADD.U32 (0x59f, one race compute), and ISBERD/ISBEWR (0x923/0x927), which are refused by name because they mark a task or mesh
program (Eglantine's NX2_NOTES row 89) and this host has no task or mesh pipeline. Needs DMSH_TEST_XLATE (the translator) like the other translator
tests. UP2UR's predicate values are not exercised here: with no uniform predicate set the moved bits are 0, so the test pins the decode, the UR write
reaching a store, and the refusal of a mode outside URZ/PT, not the runtime predicate state."""
import json, os, struct, subprocess, sys, tempfile, unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1] / 'tools'
EXIT = (0x000fea0003800000, 0x000000000000794d)
# UP2UR UR6, UPR, URZ, 8 (Mario Kart World 426d59e13bc625ba +0x300): bit 3 of UR6 is UP3
UP2UR = (0x000fe20008000000, 0x000000083f067883)
# the same word with its source field (24..32) cleared: not URZ, so not a mode the instruction has
UP2UR_BAD_SRC = (0x000fe20008000000, 0x0000000800067883)
# SURED.D.2D.ADD.STRONG.GPU.IGN U32 [R4], 0 (ab77eaee44cfef88 +0xc0): image word 12, coordinate (R4, R5), value RZ
SURED = (0x000fe2000010e000, 0x60000c000400759f)
# ISBEWR.O.ATTR [R1 + 0x10], R2 (fea1d6ca04512de1 +0x2d0): the write a mesh program makes into its stage buffer
ISBEWR = (0x0041e8000000b800, 0x0000100201007927)


def inst(hi, lo): return struct.pack('<QQ', lo, hi)


def sts(offset, rb):   # STS.U32 [RZ + offset], Rb: keeps its result
    return inst(0x000fe80000000800, offset << 40 | rb << 32 | 0xff << 24 | 0x7388)


UP2UR_READ = inst(0x000fe20000000000, 0xc02 | 0x7000 | 5 << 16 | 0x3f << 24 | 6 << 32)   # MOV R5, UR6


@unittest.skipUnless(os.environ.get('DMSH_TEST_XLATE'), 'set DMSH_TEST_XLATE to the offline translator')
class Translated(unittest.TestCase):
    def run_jobs(self, jobs, work):
        (work / 'jobs.json').write_text(json.dumps(jobs))
        r = subprocess.run([os.environ['DMSH_TEST_XLATE'], str(work / 'jobs.json'), str(work / 'out')], capture_output=True, text=True)
        return r

    def translate(self, code, **extra):
        with tempfile.TemporaryDirectory(prefix='ampere_nvn2_') as d:
            work = Path(d); (work / 'k.bin').write_bytes(code)
            job = dict(key='k', stage='cs', arch='sm86', code=str(work / 'k.bin'), tex={}, img={}, attr={}, fout={}, debug=True,
                       local=[32, 1, 1], nvn2_cs=[0, 0, 2, 0x40, 0], **extra)
            r = self.run_jobs([job], work)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertTrue((work / 'out/k.spv').exists(), r.stdout + r.stderr)
            sys.path.insert(0, str(TOOLS)); import dmsh_geometry
            dmsh_geometry.flatten_sets(work / 'out/k.spv')
            r = subprocess.run([str(TOOLS / 'spirv_cross_bin/spirv-cross'), '--msl', '--msl-version', '20300', '--msl-argument-buffers',
                                '--msl-texture-buffer-native', str(work / 'out/k.spv')], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            return r.stdout

    def refusal(self, code):
        with tempfile.TemporaryDirectory(prefix='ampere_nvn2_') as d:
            work = Path(d); (work / 'k.bin').write_bytes(code)
            job = dict(key='k', stage='cs', arch='sm86', code=str(work / 'k.bin'), tex={}, img={}, attr={}, fout={}, debug=True,
                       local=[32, 1, 1], nvn2_cs=[0, 0, 2, 0x40, 0])
            return self.run_jobs([job], work)


class Up2ur(Translated):
    def test_the_uniform_bit_reaches_a_store(self):   # mask bit 3 is worth 8, under UP3, which nothing has set here (the select reads false)
        msl = self.translate(inst(*UP2UR) + UP2UR_READ + sts(0x10, 5) + inst(*EXIT))
        self.assertIn('false ? 8 : 0', msl)
        self.assertRegex(msl, r'_18\[4\] = uint\(')

    def test_a_source_that_is_not_urz_is_refused(self):
        r = self.refusal(inst(*UP2UR_BAD_SRC) + inst(*EXIT))
        self.assertEqual(r.returncode, 1)
        self.assertIn('UP2UR mode', r.stderr)


class Sured(Translated):
    def test_it_becomes_an_image_reduction(self):
        msl = self.translate(inst(*SURED) + inst(*EXIT))
        self.assertIn('atomic_fetch_add_explicit', msl)   # ADD, U32
        self.assertRegex(msl, r', 0u, memory_order_relaxed\)')   # the value is RZ


class TaskMesh(Translated):
    def test_isbewr_is_refused_as_a_task_or_mesh_program(self):
        r = self.refusal(inst(*ISBEWR) + inst(*EXIT))
        self.assertEqual(r.returncode, 1)
        self.assertIn('task/mesh program (ISBERD/ISBEWR)', r.stderr)


if __name__ == '__main__':
    unittest.main()
