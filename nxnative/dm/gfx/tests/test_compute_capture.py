"""Capture diagnostics reject incomplete raw accesses and preserve read timing."""
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'probes'))
import raw_memory_guard


@unittest.skipUnless(all(shutil.which(t) for t in ('glslangValidator', 'spirv-val')),
                     'requires glslangValidator and spirv-val')
class RawGuard(unittest.TestCase):
    def compile(self, folder, body, extra=''):
        source = ('#version 460\n#extension GL_EXT_buffer_reference2 : require\n'
                  '#extension GL_EXT_shader_explicit_arithmetic_types_int64 : require\n'
                  'layout(local_size_x=32) in;\n'
                  'layout(buffer_reference,buffer_reference_align=4) buffer Word { uint value; };\n'
                  'layout(binding=0) buffer Input { uint64_t address; } data;\n'
                  + extra + '\nvoid main(){Word word=Word(data.address);' + body + '}\n')
        path = folder / 'test.comp'
        path.write_text(source)
        target = folder / 'test.spv'
        subprocess.run(['glslangValidator', '-V', '--target-env', 'vulkan1.2', str(path),
                        '-o', str(target)], check=True, capture_output=True)
        return target.read_bytes()

    def test_physical_load_and_store_validate_with_guard(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            binary = self.compile(folder, 'word.value=word.value+17u;')
            guarded, sites = raw_memory_guard.guard(binary)
            self.assertEqual(sites, 2)
            target = folder / 'guarded.spv'
            target.write_bytes(guarded)
            subprocess.run(['spirv-val', '--target-env', 'vulkan1.2', str(target)], check=True)
            with self.assertRaisesRegex(ValueError, 'binding 30'):
                raw_memory_guard.guard(guarded)

    def test_unrecognized_raw_module_is_unchanged_by_lookup_cache(self):
        import gmem_cache_spv
        with tempfile.TemporaryDirectory() as directory:
            binary=self.compile(Path(directory),'word.value=word.value+17u;')
            self.assertEqual(gmem_cache_spv.cache_lookup(binary),(binary,0))

    def test_lookup_cache_validates_and_respects_map_and_mixed_eligibility(self):
        import gmem_cache_spv
        import make_lookup_cache_proof
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory)
            make_lookup_cache_proof.build(folder)
            binary=(folder/'baseline.spv').read_bytes()
            cached,count=gmem_cache_spv.cache_lookup(binary,0)
            self.assertEqual(count,1)
            self.assertEqual(cached,(folder/'cached.spv').read_bytes())
            self.assertEqual(gmem_cache_spv.cache_lookup(cached,0),(cached,0))
            self.assertEqual(gmem_cache_spv.cache_lookup(binary,9),(binary,0))
            self.assertEqual(gmem_cache_spv.cache_lookup(binary,0,require_mixed=True),(binary,0))

    def test_physical_atomic_is_rejected_instead_of_partly_guarded(self):
        with tempfile.TemporaryDirectory() as directory:
            binary = self.compile(Path(directory), 'atomicAdd(word.value,1u);')
            with self.assertRaisesRegex(ValueError, 'physical atomic/copy'):
                raw_memory_guard.guard(binary)

    def test_existing_guard_binding_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            binary = self.compile(Path(directory), 'word.value=other.value;',
                                  'layout(binding=30) buffer Other { uint value; } other;')
            with self.assertRaisesRegex(ValueError, 'binding 30'):
                raw_memory_guard.guard(binary)

    def test_guard_range_count_and_unrecognized_ablations_reject(self):
        import isolate_raw_store
        with tempfile.TemporaryDirectory() as directory:
            binary = self.compile(Path(directory), 'word.value=word.value+17u;')
            for ranges in (0,17):
                with self.assertRaisesRegex(ValueError, '1..16'):
                    raw_memory_guard.guard(binary,ranges)
            self.assertEqual(isolate_raw_store.isolate(binary)[0],binary)
            with self.assertRaises(ValueError):isolate_raw_store.isolate(binary,map_entry=1)
            with self.assertRaises(ValueError):isolate_raw_store.isolate(binary,log_binding=0)


@unittest.skipUnless(os.environ.get('DMSH_TEST_XLATE') and shutil.which('glslangValidator'),
                     'set DMSH_TEST_XLATE and install glslangValidator')
class MemorySnapshot(unittest.TestCase):
    def test_read_is_evaluated_before_overwrite_with_and_without_barrier(self):
        import make_memory_snapshot_proof
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            make_memory_snapshot_proof.build(folder, Path(os.environ['DMSH_TEST_XLATE']).resolve())
            for name in ('snapshot', 'snapshot-barrier'):
                source = (folder / (name + '.comp')).read_text()
                # The generated shader must snapshot the shared read in a local
                # before writing 99, and export that local after the overwrite.
                shared = re.search(r'shared uint (\w+)\[', source).group(1)
                read = re.search(r'(?:float|uint|int)\s+(\w+)\s*=\s*(?:uintBitsToFloat\()?'
                                 + re.escape(shared) + r'\[', source)
                self.assertIsNotNone(read, source)
                self.assertLess(read.start(), source.index(' = 99u;'), source)
                self.assertIn(read[1], source[source.index('result.words'):])


class CpuConvolution(unittest.TestCase):
    def test_asymmetric_channels_padding_bias_and_downsample(self):
        import check_conv_capture
        import numpy as np
        for stride in (1, 2):
            with self.subTest(stride=stride), tempfile.TemporaryDirectory() as directory:
                base = Path(directory) / 'capture'
                pool = bytearray(8192)
                source = np.arange(1, 5, dtype='f4').reshape(2, 2, 1) * np.arange(1, 17, dtype='f4') / 16
                pool[:128] = source.astype('<f2').tobytes()
                kernel = 3 if stride == 1 else 2
                weights = np.zeros((kernel * kernel, 16, 16), '<f2')
                for tap in range(kernel * kernel):
                    for k in range(16):
                        weights[tap, k, (k + 1) % 16] = tap + 1
                pool[128:128 + weights.nbytes] = weights.tobytes()
                bias = -np.arange(16, dtype='<f2')
                pool[4736:4768] = bias.tobytes()
                driver = bytearray(4096)
                for word, offset in ((196, 4800), (200, 0), (204, 128), (208, 4736)):
                    struct.pack_into('<Q', driver, word * 4, 0x100000000 + offset)
                Path(f'{base}.b1.before.bin').write_bytes(driver)
                Path(f'{base}.tsv').write_text('capture 2\npool 0 4294967296 8192\n')
                Path(f'{base}.p0.before.bin').write_bytes(pool)
                factors = np.array([[77, 67], [47, 37]], dtype='f4') if stride == 1 else np.array([[30]], dtype='f4')
                expected = np.maximum(factors[:, :, None] * np.r_[16, np.arange(1, 16)] / 16 + bias, 0).astype('<f2')
                pool[4800:4800 + expected.nbytes] = expected.tobytes()
                Path(f'{base}.p0.after.bin').write_bytes(pool)
                result = check_conv_capture.check(base, (2, 2, 16), 16, stride)
                self.assertEqual(result['max_absolute_error'], 0)


if __name__ == '__main__':
    unittest.main()
