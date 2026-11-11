#!/usr/bin/env python3
"""Summarize bounded Android replay measurements; never infer gameplay FPS/RAM."""
import argparse
import csv
import hashlib
import json
import math
import statistics
from pathlib import Path

PHASES = ('first_use', 'unchanged', 'remap_existing', 'new_content')
TIMES = ('begin_ns', 'prepare_wall_ns', 'prepare_thread_cpu_ns', 'submit_ns', 'wait_ns', 'gpu_main_ns')
def percentile(values, fraction):
    ordered = sorted(values)
    return ordered[max(0, math.ceil(len(ordered)*fraction)-1)]

def read_run(path):
    lines = path.read_text().splitlines()
    rows = list(csv.DictReader(line for line in lines if line and not line.startswith('#')))
    if not rows:
        raise ValueError(f'{path}: no measurements')
    for row in rows:
        for key, value in row.items():
            if key != 'phase':
                row[key] = float(value)
                if not math.isfinite(row[key]) or row[key] < 0:
                    raise ValueError(f'{path}: unavailable/invalid {key}: {value}')
    if any(row['phase'] not in PHASES for row in rows):
        raise ValueError(f'{path}: unexpected phase')
    phases = {}
    for phase in PHASES:
        selected = [r for r in rows if r['phase'] == phase and (phase != 'unchanged' or r['iteration'] >= 10)]
        if not selected:
            raise ValueError(f'{path}: missing phase {phase}')
        phase_rows = [r for r in rows if r['phase'] == phase]
        if [r['iteration'] for r in phase_rows] != list(range(len(phase_rows))):
            raise ValueError(f'{path}: incomplete phase {phase}')
        phases[phase] = {'samples': len(selected), 'timings_ms': {key: {'median': statistics.median(r[key] for r in selected)/1e6, 'p95': percentile([r[key] for r in selected], .95)/1e6, 'max': max(r[key] for r in selected)/1e6} for key in TIMES}, 'uploaded_bytes': sum(r['uploaded_bytes'] for r in phase_rows), 'metadata_bytes': sum(r['metadata_bytes'] for r in phase_rows), 'max_atlas_allocated_bytes': max(r['atlas_allocated_bytes'] for r in phase_rows)}
    if phases['unchanged']['uploaded_bytes'] or phases['remap_existing']['uploaded_bytes']:
        raise ValueError(f'{path}: unexpected content upload in reuse phase')
    footer = [line for line in lines if line.startswith('# released_workload')]
    if len(footer) != 1 or not any('atlas_remaining_bytes=0 ' in line for line in lines):
        raise ValueError(f'{path}: missing successful cleanup')
    released = dict(item.split('=') for item in footer[0].split()[2:])
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'rows': len(rows), 'comments': [line for line in lines if line.startswith('#')], 'phases': phases, 'peak_atlas_bytes': max(r['atlas_peak_bytes'] for r in rows), 'sampled_peak_rss_kib': max(r['rss_kib'] for r in rows), 'process_hwm_kib': float(released['hwm_kib']), 'sampled_peak_pss_kib': max(r['pss_kib'] for r in rows), 'released_pss_kib': float(released['pss_kib'])}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', type=Path, nargs='+', required=True)
    parser.add_argument('--candidate', type=Path, nargs='+', required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    groups = {name: [read_run(path) for path in getattr(args, name)] for name in ('baseline', 'candidate')}
    layouts = {run['comments'][0].split(' logical_bytes=', 1)[1].split(' setup_ns=', 1)[0] for runs in groups.values() for run in runs}
    if len(layouts) != 1:
        raise ValueError('workload layouts differ')
    result = {'scope': 'offscreen native compressed atlas replay, not gameplay; serialized submissions, 4 queries/job; GPU timestamp excludes private atlas upload submissions; PSS/RSS and Vulkan allocation counters overlap and must not be added', 'warmup': 'first 10 unchanged jobs excluded; first_use and mapping/content changes retained', 'runs': groups, 'comparison': {}}
    for phase in PHASES:
        values = {name: [run['phases'][phase]['timings_ms']['prepare_wall_ns']['median'] for run in runs] for name, runs in groups.items()}
        before, after = (statistics.median(values[name]) for name in ('baseline', 'candidate'))
        result['comparison'][phase] = {'baseline_prepare_medians_ms': values['baseline'], 'candidate_prepare_medians_ms': values['candidate'], 'median_prepare_reduction_percent': 100*(1-after/before) if before else None}
    args.out.write_text(json.dumps(result, indent=2)+'\n')
    for phase, values in result['comparison'].items():
        print(phase, 'prepare ms', values['baseline_prepare_medians_ms'], '->', values['candidate_prepare_medians_ms'])
    for name, runs in groups.items():
        print(name, 'atlas peak MiB', [r['peak_atlas_bytes']/1048576 for r in runs], 'process HWM MiB', [r['process_hwm_kib']/1024 for r in runs])

if __name__ == '__main__':
    main()
