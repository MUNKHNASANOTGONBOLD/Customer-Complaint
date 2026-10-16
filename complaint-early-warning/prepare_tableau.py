"""Create Tableau-ready CSVs from a completed pipeline export. Python standard library."""
import csv
import json
from pathlib import Path
import os
import shutil

BASE = Path(__file__).resolve().parent

def main():
    source = BASE / 'output'
    dest = BASE / 'tableau_data'
    dest.mkdir(exist_ok=True)
    q = json.loads((source / 'quality_summary.json').read_text())
    tmp = dest / 'complaints.tmp'
    count = 0
    with (source / 'complaints.csv').open(newline='', encoding='utf-8-sig') as inp, tmp.open('w', newline='', encoding='utf-8') as out:
        reader = csv.DictReader(inp)
        extras = ['is_recent', 'is_baseline', 'is_review_period', 'recent_start', 'recent_end', 'baseline_start', 'baseline_end', 'snapshot_built_at']
        writer = csv.DictWriter(out, fieldnames=reader.fieldnames + extras)
        writer.writeheader()
        for row in reader:
            d = row['received_date']
            row['is_recent'] = int(q['recent_start'] <= d <= q['recent_end'])
            row['is_baseline'] = int(q['baseline_start'] <= d <= q['baseline_end'])
            row['is_review_period'] = int(q['baseline_start'] <= d <= q['recent_end'])
            for field in ['recent_start','recent_end','baseline_start','baseline_end']:
                row[field] = q[field]
            row['snapshot_built_at'] = q['built_at']
            writer.writerow(row)
            count += 1
    if count != q['records']:
        tmp.unlink()
        raise ValueError('Export count differs from quality summary; rerun pipeline.py export.')
    os.replace(tmp, dest / 'complaints.csv')
    for name in ['investigation_queue.csv', 'pipeline_runs.csv']:
        temp = dest / (name + '.tmp')
        shutil.copyfile(source / name, temp)
        os.replace(temp, dest / name)
    with (dest / 'quality.csv').open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=list(q))
        w.writeheader()
        w.writerow(q)
    print(f'Tableau exports ready: {count:,} complaints; {q["review_candidates"]} candidates.')

if __name__ == '__main__':
    main()
