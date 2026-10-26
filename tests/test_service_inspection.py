"""Full service identity and nonexclusive AIT evidence through the production core."""
import sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from core_client import Core,CoreError
from make_fixture import section,descriptor,word
from test_application_carriage import pat,pmt
import test_application_summaries as app

def sdt(onid=1,tsid=1,services=(101,)):
 payload=word(onid)+b'\xff'
 for sid in services:
  desc=descriptor(0x48,b'\x01\x00\x04News');payload+=word(sid)+b'\xff'+word(0x8000+len(desc))+desc
 return section(0x42,tsid,1,payload)
def eit(onid=1,tsid=1,sid=101,event=7):
 return section(0x4e,sid,1,word(tsid)+word(onid)+b'\x00\x4e'+word(event)+bytes.fromhex('eb96123456010000')+word(0x8000))
def ts(pairs):
 cc={};out=[]
 for pid,raw in pairs:
  counter=cc.get(pid,0)
  while raw:
   first=counter==cc.get(pid,0);capacity=183 if first else 184;payload=(b'\x00' if first else b'')+raw[:capacity];raw=raw[capacity:];out.append((bytes([0x47,(pid>>8)|(0x40 if first else 0),pid&255,0x10|(counter&15)])+payload).ljust(188,b'\xff'));counter+=1
  cc[pid]=counter
 return b''.join(out)
class ServiceInspectionTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.core=Core();self.addCleanup(self.core.close);self.path=Path(self.tmp.name)/'services.ts'
 def load(self,pairs):
  self.path.write_bytes(ts(pairs));self.state=self.core.call('analyze',{'path':str(self.path),'standards':'dvb'});self.rev=self.state['revision'];return self.state
 def read(self,onid=1,tsid=1,sid=101,**options):return self.core.call('query_service',{'analysis_revision':self.rev,'original_network_id':onid,'transport_stream_id':tsid,'service_id':sid,**options})
 def test_eit_never_joins_same_sid_on_other_transport(self):
  self.load([(0,pat()),(0x100,pmt()),(0x11,sdt()),(0x12,eit()),(0x12,eit(tsid=2,event=8)),(0x12,eit(onid=2,event=9))]);r=self.read();self.assertEqual([e['id'] for e in r['events']],[7]);self.assertEqual(r['identity'],{'original_network_id':1,'transport_stream_id':1,'service_id':101});self.assertTrue(r['components']);self.assertEqual(r['components'][0]['structure_path'],'section/stream/12');self.assertEqual(r['components'][0]['section_offset'],12);self.assertTrue(all(c['source_id'] in {t['id'] for t in self.state['tables'] if t['name']=='PMT'} for c in r['components']))
 def test_conflicting_actual_sdt_networks_withhold_pmt_association(self):
  state=self.load([(0,pat()),(0x100,pmt()),(0x11,sdt()),(0x11,sdt(onid=2))]);self.assertEqual(len(state['services']),2)
  for service in state['services']:self.assertIsNone(service['pmt_pid']);self.assertNotIn('components',service);self.assertIn('Ambiguous',service['media_status'])
  self.assertEqual(self.read()['components'],[]);self.assertEqual(self.read(onid=2)['components'],[])
 def test_shared_ait_pid_keeps_nonexclusive_carriers_and_exact_sources(self):
  self.load([(0,pat(((101,0x100),(102,0x101)))),(0x100,pmt()),(0x101,pmt(program=102)),(0x11,sdt(services=(101,102))),(0x150,app.ait())]);a=self.read();b=self.read(sid=102);self.assertTrue(a['applications']);self.assertTrue(b['applications']);self.assertEqual(a['applications'][0]['source_id'],b['applications'][0]['source_id']);self.assertEqual(a['applications'][0]['carriage_status'],'resolved');self.assertIn('Nonexclusive',a['applications'][0]['scope'])
 def test_automatic_profile_explains_missing_application_association(self):
  self.path.write_bytes(ts([(0,pat()),(0x100,pmt()),(0x11,sdt()),(0x150,app.ait())]));self.state=self.core.call('analyze',{'path':str(self.path),'standards':'auto'});self.rev=self.state['revision'];r=self.read();self.assertEqual(r['applications'],[]);self.assertTrue(any('explicit DVB' in w for w in r['warnings']))
 def test_revision_missing_identity_and_paging_are_guarded(self):
  self.load([(0,pat()),(0x100,pmt()),(0x11,sdt()),(0x12,eit())]);r=self.read(event_limit=1);self.assertEqual(r['event_total'],1);self.assertIsNone(r['event_next_offset']);self.assertEqual(self.read(event_offset=1)['events'],[])
  with self.assertRaises(CoreError):self.read(onid=2)
  with self.assertRaises(CoreError):self.read(analysis_revision=self.rev+1)
  with self.assertRaises(CoreError):self.read(event_limit=101)
if __name__=='__main__':unittest.main()
