import unittest,sqlite3
from datetime import date,timedelta
from pipeline import signal_rows,SCHEMA,load

class SignalTests(unittest.TestCase):
 def records(self,count,dt,timely='Yes'):
  return [dict(complaint_id=str(i),received_date=str(dt),company='Test Company',issue='Test Issue',sub_issue='Test detail',state='NC',response='Closed with explanation',timely=timely) for i in range(count)]
 def test_boundary_windows_and_publication_exclusion(self):
  asof=date(2026,10,10);end=asof-timedelta(days=60);start=end-timedelta(days=364)
  records=self.records(60,start)+self.records(30,start-timedelta(days=1))+self.records(100,end+timedelta(days=1))
  rows,p,_=signal_rows(records,asof)
  self.assertEqual((rows[0]['recent'],rows[0]['baseline']), (60,30))
  self.assertTrue(rows[0]['volume_signal'])
  self.assertEqual(rows[0]['expected_complaints'],30)
  self.assertEqual(p['recent_start'],'2025-08-12')
  self.assertEqual(p['baseline_start'],'2024-08-12')
  self.assertEqual(p['baseline_end'],'2025-08-11')
 def test_unknown_timeliness_not_in_denominator(self):
  dt=date(2026,8,1)
  rows,_,_=signal_rows(self.records(30,dt,'Yes')+self.records(10,dt,'No')+self.records(100,dt,None),date(2026,10,10))
  self.assertEqual(rows[0]['known'],40);self.assertEqual(rows[0]['late_pct'],25)
  self.assertTrue(rows[0]['late_signal'])
 def test_no_baseline_is_not_infinite_growth(self):
  rows,_,_=signal_rows(self.records(200,date(2026,8,1)),date(2026,10,10))
  self.assertIsNone(rows[0]['volume_ratio']);self.assertFalse(rows[0]['volume_signal'])
 def test_revisions_and_transactional_rollback(self):
  raw={'Complaint ID':'123','Date received':'2026-01-01','Product':'Credit card','Sub-product':'Card','Issue':'Fees','Sub-issue':'Fee','Company':'Example','State':'NC','Date sent to company':'2026-01-02','Company response to consumer':'In progress','Timely response?':'Yes','Submitted via':'Web'}
  meta={'sha256':'test','fetched_at':'test'}
  with sqlite3.connect(':memory:') as db:
   db.executescript(SCHEMA);load(db,[([raw],meta)]);load(db,[([raw],meta)])
   self.assertEqual(db.execute('SELECT COUNT(*) FROM revisions').fetchone()[0],0)
   raw={**raw,'Company response to consumer':'Closed with explanation'};load(db,[([raw],meta)]);db.commit()
   self.assertEqual(db.execute('SELECT COUNT(*) FROM revisions').fetchone()[0],1)
   with self.assertRaises(ValueError):
    with db:load(db,[([{**raw,'Company':'Changed'}, {**raw,'Complaint ID':''}],meta)])
   self.assertEqual(db.execute('SELECT company FROM complaints').fetchone()[0],'Example')
if __name__=='__main__':unittest.main()
