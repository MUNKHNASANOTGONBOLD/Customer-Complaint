"""CFPB credit-card complaint ingestion, descriptive signals and review dashboard."""
import argparse,csv,hashlib,html,io,json,os,sqlite3,time,urllib.request
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import date,datetime,timedelta,timezone
from pathlib import Path
from urllib.parse import urlencode
ROOT=Path(__file__).resolve().parent
API='https://www.consumerfinance.gov/data-research/consumer-complaints/search/api/v1/'
FIELDS={'Complaint ID':'complaint_id','Date received':'received_at','Product':'product','Sub-product':'sub_product','Issue':'issue','Sub-issue':'sub_issue','Company':'company','State':'state','Date sent to company':'sent_at','Company response to consumer':'response','Timely response?':'timely','Submitted via':'channel'}
SCHEMA='''
CREATE TABLE IF NOT EXISTS complaints(complaint_id TEXT PRIMARY KEY,received_date TEXT,company TEXT,product TEXT,sub_product TEXT,issue TEXT,sub_issue TEXT,state TEXT,sent_date TEXT,response TEXT,timely TEXT,channel TEXT,source_hash TEXT,fetched_at TEXT);
CREATE TABLE IF NOT EXISTS revisions(complaint_id TEXT,previous_values TEXT,replaced_at TEXT);
CREATE TABLE IF NOT EXISTS runs(started_at TEXT,finished_at TEXT,status TEXT,processed INTEGER,inserted INTEGER,updated INTEGER,detail TEXT);
DROP VIEW IF EXISTS daily_volume;
CREATE VIEW daily_volume AS SELECT received_date,company,issue,COUNT(*) complaints,SUM(CASE WHEN timely='No' THEN 1 ELSE 0 END) late_responses,SUM(CASE WHEN timely IN ('Yes','No') THEN 1 ELSE 0 END) known_timeliness FROM complaints GROUP BY received_date,company,issue;
'''

def now():return datetime.now(timezone.utc).isoformat()
def quarters():
    today=datetime.now(timezone.utc).date();y=2023;m=1
    while date(y,m,1)<=today:
        start=date(y,m,1);ny,nm=(y+1,1) if m==10 else (y,m+3)
        end=min(date(ny,nm,1),today+timedelta(days=1));yield start,end
        y,m=ny,nm

def extract(job):
    start,end,refresh=job
    path=ROOT/'data/raw'/f'{start}_{end}.csv';meta=path.with_suffix('.json')
    if refresh or not path.exists():
        params={'format':'csv','no_aggs':'true','product':'Credit card','date_received_min':str(start),'date_received_max':str(end)}
        url=API+'?'+urlencode(params)
        error=None
        for attempt in range(3):
            try:
                with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'ComplaintPipeline/1.0'}),timeout=120) as response:content=response.read()
                reader=csv.DictReader(io.StringIO(content.decode('utf-8-sig')))
                if not set(FIELDS).issubset(reader.fieldnames or []):raise ValueError('Unexpected CFPB CSV schema')
                rows=list(reader)
                # An empty, correctly shaped export is valid: this exact product
                # label was not used in every historical quarter.
                for row in rows:
                    dt=date.fromisoformat(row['Date received'][:10])
                    # Live API includes the max calendar date despite the spec
                    # describing an exclusive max. Keep raw boundary rows;
                    # enforce exclusive partition ends locally below.
                    if not start<=dt<=end or row['Product']!='Credit card':raise ValueError('API filter did not match requested scope')
                error=None;break
            except Exception as exc:
                error=exc
                if attempt<2:time.sleep(2**attempt)
        if error:raise error
        digest=hashlib.sha256(content).hexdigest()
        # Preserve changed raw snapshots and their metadata before replacement.
        if path.exists() and hashlib.sha256(path.read_bytes()).hexdigest()!=digest:
            old_hash=hashlib.sha256(path.read_bytes()).hexdigest()[:12]
            path.replace(path.with_name(path.stem+'_'+old_hash+'.csv'))
            if meta.exists():meta.replace(meta.with_name(meta.stem+'_'+old_hash+'.json'))
        tmp=path.with_suffix('.tmp');tmp.write_bytes(content);os.replace(tmp,path)
        meta.write_text(json.dumps({'url':url,'sha256':digest,'fetched_at':now(),'rows':len(rows),'start_inclusive':str(start),'end_exclusive':str(end)},indent=2))
    metadata=json.loads(meta.read_text());content=path.read_bytes()
    if hashlib.sha256(content).hexdigest()!=metadata['sha256']:raise ValueError('Raw hash mismatch')
    with path.open(newline='',encoding='utf-8-sig') as stream:
        rows=[r for r in csv.DictReader(stream) if start<=date.fromisoformat(r['Date received'][:10])<end]
    print(f'Loaded {start} to {end}: {len(rows):,} complaints',flush=True)
    return rows,metadata

def normalize(row,digest,stamp):
    values={new:row[old].strip() for old,new in FIELDS.items()}
    for k in ['complaint_id','received_at','company','product','issue']:
        if not values[k] or values[k]=='None':raise ValueError('Missing required '+k)
    received=date.fromisoformat(values['received_at'][:10]).isoformat()
    sent=None if values['sent_at'] in ('','None') else date.fromisoformat(values['sent_at'][:10]).isoformat()
    if values['product']!='Credit card':raise ValueError('Unexpected product')
    timely=values['timely'] if values['timely'] in ('Yes','No') else None
    return (values['complaint_id'],received,values['company'],values['product'],values['sub_product'],values['issue'],values['sub_issue'],values['state'],sent,values['response'],timely,values['channel'],digest,stamp)

def load(db,batches):
    inserted=updated=processed=0
    for rows,meta in batches:
        for raw in rows:
            record=normalize(raw,meta['sha256'],meta['fetched_at']);processed+=1
            old=db.execute('SELECT * FROM complaints WHERE complaint_id=?',(record[0],)).fetchone()
            if old is None:inserted+=1
            elif tuple(old[1:12])!=record[1:12]:
                updated+=1;db.execute('INSERT INTO revisions VALUES(?,?,?)',(record[0],json.dumps(list(old)),now()))
            db.execute('INSERT INTO complaints VALUES('+','.join(['?']*14)+') ON CONFLICT(complaint_id) DO UPDATE SET '+','.join(c+'=excluded.'+c for c in ['received_date','company','product','sub_product','issue','sub_issue','state','sent_date','response','timely','channel','source_hash','fetched_at']),record)
    return processed,inserted,updated

def signal_rows(records,asof):
    # Frozen dates make the descriptive comparison reproducible. Receipt dates,
    # not publication dates. Exclude newest 60 days as a sensitivity assumption.
    end=asof-timedelta(days=60);recent_start=end-timedelta(days=364)
    baseline_start=recent_start-timedelta(days=365)
    grouped={};weeks=defaultdict(lambda:defaultdict(int));examples=defaultdict(list)
    for r in records:
        dt=date.fromisoformat(r['received_date'])
        if not baseline_start<=dt<=end:continue
        key=(r['company'],r['issue'])
        row=grouped.setdefault(key,{'company':key[0],'issue':key[1],'recent':0,'baseline':0,'known':0,'late':0,'monetary_relief':0,'nonmonetary_relief':0})
        week=(dt-timedelta(days=dt.weekday())).isoformat();weeks[r['company']][week]+=1
        if dt<recent_start:row['baseline']+=1
        else:
            row['recent']+=1
            row['known']+=r['timely'] in ('Yes','No');row['late']+=r['timely']=='No'
            row['monetary_relief']+=r['response']=='Closed with monetary relief'
            row['nonmonetary_relief']+=r['response']=='Closed with non-monetary relief'
            examples[key].append({k:r[k] for k in ['complaint_id','received_date','company','issue','sub_issue','state','response','timely']})
    result=[]
    for key,r in grouped.items():
        expected=r['baseline'];ratio=r['recent']/expected if expected else None
        rate=100*r['late']/r['known'] if r['known'] else None
        volume=r['recent']>=20 and expected>=10 and ratio>=1.5 and r['recent']-expected>=10
        late=r['known']>=30 and r['late']>=3 and rate>=10
        result.append({**r,'expected_complaints':round(expected,2),'volume_ratio':round(ratio,3) if ratio is not None else None,'excess':round(r['recent']-expected,2),'late_pct':round(rate,2) if rate is not None else None,'volume_signal':bool(volume),'late_signal':bool(late),'signal_count':int(volume)+int(late),'examples':sorted(examples[key],key=lambda r:r['received_date'],reverse=True)[:12]})
    result.sort(key=lambda r:(r['signal_count'],r['excess'],r['recent']),reverse=True)
    periods={'as_of':str(asof),'mature_through':str(end),'recent_start':str(recent_start),'recent_end':str(end),'baseline_start':str(baseline_start),'baseline_end':str(recent_start-timedelta(days=1)),'excluded_newest_days':60}
    return result,periods,weeks

def export(db):
    db.row_factory=sqlite3.Row
    records=[dict(r) for r in db.execute('SELECT * FROM complaints')]
    rows,periods,weeks=signal_rows(records,datetime.now(timezone.utc).date())
    companies=sorted({r['company'] for r in records})
    status={'records':len(records),'companies':len(companies),'earliest_received':min(r['received_date'] for r in records),'latest_received':max(r['received_date'] for r in records),'built_at':now()}
    runs=[dict(r) for r in db.execute('SELECT * FROM runs ORDER BY rowid DESC LIMIT 8')]
    # Zero-fill weekly series for all companies with mature-window complaints.
    weekly=[];first=date.fromisoformat(periods['baseline_start']);last=date.fromisoformat(periods['recent_end'])
    first-=timedelta(days=first.weekday())
    while first<=last:
        weekly.append({'week':str(first),'companies':{c:weeks[c].get(str(first),0) for c in weeks}});first+=timedelta(days=7)
    payload={'status':status,'periods':periods,'companies':companies,'queue':rows,'weekly':weekly,'runs':runs}
    output=ROOT/'output'
    (output/'dashboard_data.json').write_text(json.dumps(payload,separators=(',',':')))
    for name,values in [('investigation_queue',[{k:v for k,v in r.items() if k!='examples'} for r in rows]),('pipeline_runs',runs)]:
        if values:
            with (output/(name+'.csv')).open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=values[0]);w.writeheader();w.writerows(values)
    with (output/'complaints.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=[c for c in records[0] if c not in ['source_hash','fetched_at']]);w.writeheader();w.writerows({k:r[k] for k in w.fieldnames} for r in records)
    (output/'dashboard.html').write_text((ROOT/'dashboard.html').read_text().replace('__DATA__',json.dumps(payload,separators=(',',':')).replace('</','<\\/')))
    # Store transparent signal output in SQLite for Power BI/SQL use.
    with db:
        db.execute('DROP TABLE IF EXISTS investigation_queue')
        db.execute('CREATE TABLE investigation_queue(company TEXT,issue TEXT,recent INTEGER,baseline INTEGER,expected_complaints REAL,volume_ratio REAL,excess REAL,known INTEGER,late INTEGER,late_pct REAL,volume_signal INTEGER,late_signal INTEGER)')
        db.executemany('INSERT INTO investigation_queue VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',[(r['company'],r['issue'],r['recent'],r['baseline'],r['expected_complaints'],r['volume_ratio'],r['excess'],r['known'],r['late'],r['late_pct'],r['volume_signal'],r['late_signal']) for r in rows])
    summary={**status,**periods,'volume_signals':sum(r['volume_signal'] for r in rows),'late_signals':sum(r['late_signal'] for r in rows),'review_candidates':sum(r['signal_count']>0 for r in rows)}
    (output/'quality_summary.json').write_text(json.dumps(summary,indent=2));return summary

def run(args):
    for folder in ['data/raw','output']:(ROOT/folder).mkdir(parents=True,exist_ok=True)
    db=sqlite3.connect(ROOT/'data/complaints.sqlite',timeout=60);db.executescript(SCHEMA)
    started=now()
    try:
        if args.command!='export':
            today=datetime.now(timezone.utc).date()
            jobs=[(a,b,args.refresh or args.command=='daily') for a,b in quarters() if args.command=='backfill' or b>=today-timedelta(days=180)]
            with ThreadPoolExecutor(max_workers=2) as pool:batches=list(pool.map(extract,jobs))
            with db:
                processed,inserted,updated=load(db,batches)
                count=db.execute('SELECT COUNT(*) FROM complaints').fetchone()[0]
                if args.command=='backfill' and count<100000:raise ValueError('Fewer than 100000 distinct complaints; incomplete project backfill')
                db.execute('INSERT INTO runs VALUES(?,?,?,?,?,?,?)',(started,now(),'success',processed,inserted,updated,'CFPB CSV export API; Credit card product only; quarterly partitions'))
        print(json.dumps(export(db),indent=2))
    except Exception as error:
        if args.command!='export':
            with db:db.execute('INSERT INTO runs VALUES(?,?,?,?,?,?,?)',(started,now(),'failed',0,0,0,str(error)))
        raise
    finally:db.close()

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('command',choices=['backfill','daily','export']);p.add_argument('--refresh',action='store_true');run(p.parse_args())
