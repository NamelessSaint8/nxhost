"""Check guarded deferred writes against independently specified register values."""

import importlib.util
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[4]
CROSS = ROOT / "nxnative/dm/gfx/tools/spirv_cross_bin/spirv-cross"


@unittest.skipUnless(
    os.environ.get("DMSH_TEST_XLATE")
    and shutil.which("glslangValidator")
    and shutil.which("spirv-val"),
    "set DMSH_TEST_XLATE and install glslangValidator/spirv-val",
)
class Scoreboard(unittest.TestCase):
    def test_issue_predicate_controls_eventual_write(self):
        spec = importlib.util.spec_from_file_location(
            "scoreboard_proof", ROOT / "probes/make_ampere_scoreboard_proof.py"
        )
        proof = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(proof)
        with tempfile.TemporaryDirectory(prefix="scoreboard-proof-") as directory:
            out = Path(directory)
            self.assertEqual(
                proof.build(out, Path(os.environ["DMSH_TEST_XLATE"]).resolve()), 11
            )
            expected = {"guarded-off-reissue": 0x40000000}
            for inverse in (0, 1):
                for active in (0, 1):
                    for change in (0, 1):
                        expected[f"guard-{inverse}-{active}-{change}"] = (
                            0x40000000 if active else 0x40E00000
                        )
            for name, word in expected.items():
                with self.subTest(case=name):
                    # Constant predicates let the independent GLSL compiler fold
                    # the complete program, including waits and deferred commits.
                    source = subprocess.check_output(
                        [
                            str(CROSS),
                            str(out / (name + ".vk.spv")),
                            "--version",
                            "460",
                            "--vulkan-semantics",
                        ],
                        text=True,
                    )
                    writes = re.findall(
                        r"result\.words\[gl_LocalInvocationIndex\] = (\d+)u;", source
                    )
                    self.assertEqual(writes, [str(word)])


if __name__ == "__main__":
    unittest.main()
