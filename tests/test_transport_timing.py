"""Known PCR arithmetic, wrap, discontinuity, gaps and bounded evidence."""
import json,os,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from core_client import Core,CoreError
M=(1<<33)*300

def pcr_packet(ticks,cc=0,discontinuity=False):
 base,ext=divmod(ticks%M,300);data=bytes([(base>>25)&255,(base>>17)&255,(base>>9)&255,(base>>1)&255,((base&1)<<7)|0x7e|(ext>>8),ext&255])
 return (bytes([0x47,0x01,0,0x30|(cc&15),7,0x10|(0x80 if discontinuity else 0)])+data).ljust(188,b'\xff')
NULL=bytes([0x47,0x1f,0xff,0x10])+b'\xff'*184

def clock_fixture(values):
 return b''.join(pcr_packet(v,i)+NULL*9 for i,v in enumerate(values))
class TransportTimingTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.core=Core();self.addCleanup(self.core.close);self.path=Path(self.tmp.name)/'clock.ts'
 def load(self,raw,**options):
  self.path.write_bytes(raw);s=self.core.call('analyze',{'path':str(self.path),'standards':'dvb','scan_mode':'full',**options});self.rev=s['revision'];return s
 def page(self,**options):return self.core.call('query_timing',{'analysis_revision':self.rev,**options})
 def test_measured_rate_pcr_source_and_original_packet_link(self):
  state=self.load(clock_fixture([0,270000,540000]));s=state['transport_summary'];self.assertTrue(s['pcr_derived']);self.assertAlmostEqual(s['measured_bitrate_bps'],1504000);self.assertAlmostEqual(s['observed_duration_seconds'],.02);self.assertEqual(s['timing']['primary_pcr_pid'],256)
  page=self.page(limit=2);self.assertEqual(len(page['items']),2);self.assertEqual(page['next_offset'],2);self.assertEqual(page['items'][1]['packet_index'],10);self.assertEqual(page['items'][1]['delta_27mhz'],270000)
  packet=self.core.call('query_packet',{'analysis_revision':self.rev,'packet_index':10});self.assertEqual(packet['adaptation']['pcr_27mhz'],270000)
  row=self.core.call('query_transport',{'analysis_revision':self.rev})['items'][0];self.assertAlmostEqual(row['bitrate_bps'],150400)
  out=os.environ.get('SHOWPSISI_TIMING_EVIDENCE_DIR')
  if out:
   root=Path(out);root.mkdir(parents=True,exist_ok=True);(root/'fixture.ts').write_bytes(self.path.read_bytes());(root/'engine-evidence.json').write_text(json.dumps({'state':state,'timing':self.page(),'transport':self.core.call('query_transport',{'analysis_revision':self.rev,'sort':'packets','descending':True})}),encoding='utf-8')
 def test_wrap_discontinuity_jump_and_missing_clock(self):
  s=self.load(clock_fixture([M-135000,135000]));self.assertEqual(s['transport_summary']['timing']['pcr_wraps'],1);self.assertAlmostEqual(s['transport_summary']['measured_bitrate_bps'],1504000)
  s=self.load(pcr_packet(0)+NULL*9+pcr_packet(270000,1,True)+NULL*9);self.assertIsNone(s['transport_summary']['measured_bitrate_bps']);self.assertEqual(s['transport_summary']['timing']['pcr_discontinuities'],1)
  s=self.load(clock_fixture([540000,270000]));self.assertIsNone(s['transport_summary']['measured_bitrate_bps']);self.assertEqual(s['transport_summary']['timing']['pcr_jumps'],1)
  s=self.load(NULL*10);self.assertIsNone(s['transport_summary']['effective_bitrate_bps']);self.assertEqual(self.page()['items'],[])
 def test_observation_gaps_never_join_clocks(self):
  s=self.load(pcr_packet(0)+NULL*18+pcr_packet(270000,1),scan_mode='distributed',max_packets=2,window_count=2);self.assertIsNone(s['transport_summary']['measured_bitrate_bps'])
 def test_supplied_rate_and_pcr_measurement_are_distinct(self):
  s=self.load(clock_fixture([0,270000]),bitrate=2000000);self.assertFalse(s['transport_summary']['pcr_derived']);self.assertEqual(s['transport_summary']['effective_bitrate_bps'],2000000);self.assertEqual(s['transport_summary']['measured_bitrate_bps'],1504000)
 def test_continuity_duplicate_and_invalid_pcr_are_explicit(self):
  first=pcr_packet(0,0);s=self.load(first+first+first+pcr_packet(270000,4)+NULL*8);t=s['transport_summary']['timing'];self.assertEqual(t['duplicate_payload_packets'],2);self.assertEqual(t['continuity_error_packets'],2)
  bad=bytearray(pcr_packet(0));bad[10]&=0x81;s=self.load(bytes(bad)+NULL*9);self.assertEqual(s['transport_summary']['timing']['invalid_pcr_fields'],1);self.assertIsNone(s['transport_summary']['measured_bitrate_bps'])
 def test_raw_pcr_evidence_and_query_are_bounded(self):
  s=self.load(b''.join(pcr_packet(i*270000,i) for i in range(4100)));self.assertEqual(s['transport_summary']['timing']['retained_samples'],4096);self.assertTrue(s['transport_summary']['timing']['samples_truncated']);self.assertEqual(self.page(offset=4095)['next_offset'],None)
  with self.assertRaises(CoreError):self.page(limit=101)
  with self.assertRaises(CoreError):self.page(analysis_revision=self.rev+1)
if __name__=='__main__':unittest.main()
