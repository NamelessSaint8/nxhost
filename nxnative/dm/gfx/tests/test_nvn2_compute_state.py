"""Ordinary captured NVN2 compute must retain its declared execution geometry."""
import ast
import os
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest import mock
from typing import Any

DM = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(DM / 'gfx/tools'))
sys.path.insert(0, str(DM / 'android/tools'))
import dmsh_ampere  # noqa: E402
import shader_vk  # noqa: E402


def control():
    ctl = bytearray(0xd8)
    struct.pack_into('<II', ctl, 0, dmsh_ampere.CTL_MAGIC, dmsh_ampere.CTL_VERSION)
    struct.pack_into('<I', ctl, 0x38, 16)
    struct.pack_into('<4I', ctl, 0x58, 32, 2, 1, 3072)
    return ctl


class ComputeState(unittest.TestCase):
    def test_control_declares_all_dimensions_and_shared_memory(self):
        self.assertEqual(dmsh_ampere.compute_state(control()), {'local': [32, 2, 1], 'shared': 3072})

    def test_missing_or_zero_execution_geometry_fails(self):
        with self.assertRaises(ValueError):
            dmsh_ampere.compute_state(control()[:0x64])
        ctl = control()
        struct.pack_into('<I', ctl, 0x5c, 0)
        with self.assertRaises(ValueError):
            dmsh_ampere.compute_state(ctl)

    def test_android_capture_needs_no_facts_row(self):
        # A package-shaped record, as captured() supplies to job_for().
        rec = bytes(0x38) + bytes(16) + control()
        with tempfile.TemporaryDirectory() as work, mock.patch.object(shader_vk, 'FACTS', {}, create=True), mock.patch.object(shader_vk.dmsh_nvn2_mesh, 'metadata', return_value=None):
            job, _ = shader_vk.job_for('0123456789abcdef', 'cs', rec, work)
        self.assertTrue(job['no_facts'])
        self.assertEqual(job['local'], [32, 2, 1])
        self.assertEqual(job['shared'], 3072)
        self.assertEqual(job['subgroup_size'], 128)

    def test_metal_job_also_keeps_compute_state_without_facts(self):
        # dmsh_build is a CLI at import time; load its actual job function alone.
        source = DM / 'gfx/tools/dmsh_build.py'
        function = next(n for n in ast.parse(source.read_text()).body if isinstance(n, ast.FunctionDef) and n.name == 'job_for')
        env: dict[str, Any] = {'os': os, 'struct': struct, 'FACTS': {}, 'dmsh_ampere': dmsh_ampere, 'dmsh_nvn2_mesh': shader_vk.dmsh_nvn2_mesh}
        exec(compile(ast.Module(body=[function], type_ignores=[]), str(source), 'exec'), env)
        with tempfile.TemporaryDirectory() as work, mock.patch.object(shader_vk.dmsh_nvn2_mesh, 'metadata', return_value=None):
            job, _ = env['job_for']('0123456789abcdef', 'cs_runtime.bin', bytes(0x38) + bytes(16) + control(), work)
        self.assertEqual(job['local'], [32, 2, 1])
        self.assertEqual(job['shared'], 3072)


if __name__ == '__main__':
    unittest.main()
