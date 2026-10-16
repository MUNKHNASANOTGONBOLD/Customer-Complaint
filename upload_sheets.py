"""Refresh existing managed tabs atomically via staging; preserve target tab IDs."""
import argparse, json, time
from pathlib import Path
from datetime import datetime,timezone,date
import google.auth
from google.oauth2 import service_account
from google.auth.transport.requests import AuthorizedSession
BASE=Path(__file__).resolve().parent
SCOPES=['https://www.googleapis.com/auth/spreadsheets']

def cell(v):
    if v is None:return {}
    if isinstance(v,str) and len(v)==10:
        try:
            serial=(date.fromisoformat(v)-date(1899,12,30)).days
            return {'userEnteredValue':{'numberValue':serial}}
        except ValueError:pass
    if isinstance(v,str) and 'T' in v and v[:4].isdigit():
        try:
            dt=datetime.fromisoformat(v)
            serial=(dt.astimezone(timezone.utc)-datetime(1899,12,30,tzinfo=timezone.utc)).total_seconds()/86400
            return {'userEnteredValue':{'numberValue':serial}}
        except ValueError:pass
    if isinstance(v,bool):return {'userEnteredValue':{'boolValue':v}}
    if isinstance(v,(int,float)):return {'userEnteredValue':{'numberValue':v}}
    return {'userEnteredValue':{'stringValue':str(v)}}

def main():
    config=json.loads((BASE/'config.json').read_text())
    sid=config['spreadsheet_id']
    if not sid or sid=='PASTE_SPREADSHEET_ID':raise ValueError('Set spreadsheet_id in config.json.')
    key=Path(config['service_account_file']).expanduser()
    if not key.is_absolute():key=BASE/key
    auth=service_account.Credentials.from_service_account_file(str(key),scopes=SCOPES)
    session=AuthorizedSession(auth)
    url=f'https://sheets.googleapis.com/v4/spreadsheets/{sid}'
    def request(method,path='',body=None):
        for attempt in range(4):
            r=session.request(method,url+path,json=body,timeout=120)
            if r.status_code in [429,500,502,503,504] and attempt<3:
                time.sleep(2**attempt);continue
            if not r.ok:raise RuntimeError(f'Sheets request failed HTTP {r.status_code}. Check sheet sharing, API access and quota.')
            return r.json()
    data=json.loads((BASE/'sheets_data.json').read_text())
    meta=request('GET','?fields=sheets.properties')
    tabs={s['properties']['title']:s['properties'] for s in meta['sheets']}
    missing=set(data)-set(tabs)
    if missing:raise ValueError('Import the supplied workbook first. Missing managed tabs: '+', '.join(sorted(missing)))
    # Any previous failed staging tabs are hidden scratch tabs and never target facts.
    old=[{'deleteSheet':{'sheetId':v['sheetId']}} for k,v in tabs.items() if k.startswith('_pipeline_stage_')]
    if old:request('POST',':batchUpdate',{'requests':old})
    used={v['sheetId'] for v in tabs.values()}
    stage={}; adds=[]
    for name,rows in data.items():
        stid=max(used)+1;used.add(stid);stage[name]=stid
        adds.append({'addSheet':{'properties':{'sheetId':stid,'title':'_pipeline_stage_'+name,'hidden':True,'gridProperties':{'rowCount':max(2,len(rows)),'columnCount':len(rows[0])}}}})
    # addSheet must not be retried after an ambiguous connection failure; rerun cleans staging.
    request('POST',':batchUpdate',{'requests':adds})
    for name,rows in data.items():
        for start in range(0,len(rows),1000):
            body={'requests':[{'updateCells':{'start':{'sheetId':stage[name],'rowIndex':start,'columnIndex':0},'rows':[{'values':[cell(v) for v in row]} for row in rows[start:start+1000]],'fields':'userEnteredValue'}}]}
            request('POST',':batchUpdate',body)
    commit=[]
    for name,rows in data.items():
        target=tabs[name];tid=target['sheetId'];nr=len(rows);nc=len(rows[0])
        grid=target.get('gridProperties',{})
        commit.append({'updateSheetProperties':{'properties':{'sheetId':tid,'gridProperties':{'rowCount':max(nr,grid.get('rowCount',0)),'columnCount':max(nc,grid.get('columnCount',0))}},'fields':'gridProperties.rowCount,gridProperties.columnCount'}})
        commit.append({'repeatCell':{'range':{'sheetId':tid},'cell':{},'fields':'userEnteredValue'}})
        commit.append({'copyPaste':{'source':{'sheetId':stage[name],'startRowIndex':0,'endRowIndex':nr,'startColumnIndex':0,'endColumnIndex':nc},'destination':{'sheetId':tid,'startRowIndex':0,'endRowIndex':nr,'startColumnIndex':0,'endColumnIndex':nc},'pasteType':'PASTE_VALUES'}})
    # Format the entire populated ranges, including rows added by future runs.
    for name, rows in data.items():
        for col, header in enumerate(rows[0]):
            if header in {'month','week_start','earliest_received','latest_received','as_of','mature_through','recent_start','recent_end','baseline_start','baseline_end','built_at','snapshot_built_at'}:
                timestamp=header in {'built_at','snapshot_built_at'}
                commit.append({'repeatCell':{'range':{'sheetId':tabs[name]['sheetId'],'startRowIndex':1,'endRowIndex':len(rows),'startColumnIndex':col,'endColumnIndex':col+1},'cell':{'userEnteredFormat':{'numberFormat':{'type':'DATE_TIME' if timestamp else 'DATE','pattern':'yyyy-mm-dd hh:mm:ss' if timestamp else 'yyyy-mm-dd'}}},'fields':'userEnteredFormat.numberFormat'}})
    # Stage deletion is separate: the commit remains idempotent if response is lost.
    request('POST',':batchUpdate',{'requests':commit})
    request('POST',':batchUpdate',{'requests':[{'deleteSheet':{'sheetId':v}} for v in stage.values()]})
    check=request('GET',"/values/Quality!A1:Z2")['values']
    expected=data['Quality'];actual=dict(zip(check[0],check[1]))
    assert int(actual['records'])==int(expected[1][expected[0].index('records')])
    log={'uploaded_at':datetime.now(timezone.utc).isoformat(),'status':'succeeded','rows':{k:len(v)-1 for k,v in data.items()}}
    with (BASE/'upload_runs.jsonl').open('a') as f:f.write(json.dumps(log)+'\n')
    print('Google Sheets refreshed and record-count metadata verified. Tableau Public refresh occurs separately.')

if __name__=='__main__':
    try:main()
    except Exception as e:
        with (BASE/'upload_runs.jsonl').open('a') as f:f.write(json.dumps({'at':datetime.now(timezone.utc).isoformat(),'status':'failed','error_type':type(e).__name__})+'\n')
        print(str(e));raise SystemExit(1)
