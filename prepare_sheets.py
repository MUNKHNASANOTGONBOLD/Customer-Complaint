"""Aggregate the complaint project's published exports; no API credentials needed."""
import csv, json, sqlite3, sys
from pathlib import Path

def build(project):
    output=project/'output'
    q=json.loads((output/'quality_summary.json').read_text())
    c=sqlite3.connect(f'file:{project / "data/complaints.sqlite"}?mode=ro',uri=True)
    c.row_factory=sqlite3.Row
    signals={ (r['company'],r['issue']):r for r in csv.DictReader((output/'investigation_queue.csv').open(encoding='utf-8-sig',newline='')) }
    headers=['company','issue','total_complaints','recent','baseline','known','late','expected_complaints','volume_ratio','excess','volume_signal','late_signal','signal_count','recent_start','recent_end','snapshot_built_at']
    groups=[headers]
    for r in c.execute('SELECT company,issue,count(*) total FROM complaints GROUP BY company,issue ORDER BY company,issue'):
        s=signals.get((r['company'],r['issue']),{})
        numeric=[int(s.get(k,0)) for k in ['recent','baseline','known','late']]
        ratios=[float(s[k]) if s.get(k) not in [None,'','None'] else None for k in ['expected_complaints','volume_ratio','excess']]
        groups.append([r['company'],r['issue'],r['total']]+numeric+ratios+[s.get('volume_signal')=='True',s.get('late_signal')=='True',int(s.get('signal_count',0)),q['recent_start'],q['recent_end'],q['built_at']])
    monthly=[['month','company','issue','complaints','known_responses','late_responses','snapshot_built_at']]
    for r in c.execute("SELECT substr(received_date,1,7)||'-01' month, company, issue, count(*) complaints, sum(timely IN ('Yes','No')) known, sum(timely='No') late FROM complaints GROUP BY month,company,issue ORDER BY month,company,issue"):
        monthly.append([r['month'],r['company'],r['issue'],r['complaints'],r['known'] or 0,r['late'] or 0,q['built_at']])
    weekly=[['week_start','issue','complaints','known_responses','late_responses','snapshot_built_at']]
    sql="""SELECT date(received_date, '-' || ((cast(strftime('%w',received_date) AS integer)+6)%7) || ' days') week_start, issue, count(*) complaints, sum(timely IN ('Yes','No')) known, sum(timely='No') late FROM complaints WHERE received_date BETWEEN ? AND ? GROUP BY week_start,issue ORDER BY week_start,issue"""
    for r in c.execute(sql,(q['baseline_start'],q['recent_end'])):
        weekly.append([r['week_start'],r['issue'],r['complaints'],r['known'] or 0,r['late'] or 0,q['built_at']])
    quality=[list(q),list(q.values())]
    data={'Signals':groups,'Monthly':monthly,'ReviewTrend':weekly,'Quality':quality}
    assert sum(r[2] for r in groups[1:])==q['records']==sum(r[3] for r in monthly[1:])
    assert sum(r[12]>0 for r in groups[1:])==q['review_candidates']
    assert sum(r[3] for r in groups[1:])==c.execute('SELECT count(*) FROM complaints WHERE received_date BETWEEN ? AND ?',(q['recent_start'],q['recent_end'])).fetchone()[0]
    # Metadata is a separate data table; it is never joined to facts.
    data['Sources']=[['source','scope','url'],['CFPB','Credit card category; no narratives','https://www.consumerfinance.gov/data-research/consumer-complaints/'],['Method','Recent 365 days vs preceding 365; newest 60 days excluded','https://cfpb.github.io/api/ccdb/']]
    dest=Path(__file__).resolve().parent/'sheets_data.json'
    dest.write_text(json.dumps(data,ensure_ascii=False,allow_nan=False),encoding='utf-8')
    print(json.dumps({'records':q['records'],'tabs':{k:len(v)-1 for k,v in data.items()},'bytes':dest.stat().st_size}))
    return data

if __name__=='__main__':
    build(Path(sys.argv[1]).resolve() if len(sys.argv)>1 else Path(__file__).resolve().parent/'complaint-early-warning')
