"""Original-source packet navigation; every byte is read back from a real file."""
import os,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from core_client import Core,CoreError
from test_unified_inspector import fixture

def packet(pid,payload=b'',afc=1,pusi=False,cc=0):
 return (bytes([0x47,(pid>>8)|(0x40 if pusi else 0),pid&255,(afc<<4)|cc])+payload).ljust(188,b'\xff')
class PacketInspectionTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.path=Path(self.tmp.name)/'source.ts';self.core=Core();self.addCleanup(self.core.close)
  self.packets=[fixture()[:188]]+[packet(8191,cc=i%16) for i in range(1,8)]+[packet(0x123,b'\x00\x00\x01\xe0\x00\x00\x80\x00\x00ABC',pusi=True)]+[packet(8191),packet(0x123,b'last')]
 def load(self,stride=188,prefix=0,**options):
  raw=b''.join((b'\x01\x02\x03\x04' if prefix else b'')+p+(b'\xee'*16 if stride==204 else b'') for p in self.packets);self.path.write_bytes(raw)
  self.state=self.core.call('analyze',{'path':str(self.path),'standards':'dvb','scan_mode':'full',**options});self.revision=self.state['revision'];return raw
 def read(self,index,**options):return self.core.call('query_packet',{'analysis_revision':self.revision,'packet_index':index,**options})
 def test_original_packet_and_encapsulation_offsets(self):
  for stride,prefix in [(188,0),(192,4),(204,0)]:
   with self.subTest(stride=stride):
    raw=self.load(stride,prefix);r=self.read(8);self.assertEqual(bytes.fromhex(r['raw_hex']),self.packets[8]);self.assertEqual(bytes.fromhex(r['frame_hex']),raw[8*stride:9*stride]);self.assertEqual(r['file_offset'],8*stride+prefix);self.assertEqual(r['header']['PID'],0x123);self.assertEqual(r['pes']['stream_id'],0xe0);self.assertTrue(r['in_analyzed_window']);self.assertEqual([x['kind'] for x in r['regions']],['header','pes_header','payload'])
 def test_search_continuation_and_reverse_do_not_skip_boundary(self):
  self.load();r=self.read(0,pid=0x123,direction='forward',scan_limit=4);self.assertFalse(r['found']);self.assertEqual(r['next_index'],4)
  r=self.read(r['next_index'],pid=0x123,direction='forward',scan_limit=4);self.assertFalse(r['found']);self.assertEqual(r['next_index'],8)
  self.assertEqual(self.read(8,pid=0x123,direction='forward')['packet_index'],8)
  self.assertEqual(self.read(9,pid=0x123,direction='backward')['packet_index'],8)
  self.assertEqual(self.read(10,pid=0x123,direction='backward')['packet_index'],10)
  end=self.read(0,pid=0x123,direction='backward');self.assertFalse(end['found']);self.assertIsNone(end['next_index'])
 def test_revision_bounds_and_source_changes_fail_closed(self):
  self.load()
  for args in [{'packet_index':11},{'packet_index':-1},{'pid':8192},{'scan_limit':0},{'analysis_revision':self.revision+1}]:
   with self.subTest(args=args),self.assertRaises(CoreError):self.read(0,**args) if 'packet_index' not in args else self.core.call('query_packet',{'analysis_revision':self.revision,**args})
  self.path.write_bytes(self.path.read_bytes()+packet(0))
  with self.assertRaisesRegex(CoreError,'Source changed'):self.read(0)
 def test_partial_scan_packet_read_does_not_claim_analyzed(self):
  self.load(scan_mode='range',start_packet=0,end_packet=5);self.assertTrue(self.read(0)['in_analyzed_window']);self.assertFalse(self.read(8)['in_analyzed_window']);self.assertEqual(self.read(8)['header']['PID'],0x123)
 def test_pointer_and_pcr_ranges_and_malformed_feedback(self):
  # PID 0 is identified as PSI by the actual PAT parsed from packet 0.
  self.packets.extend([packet(0,b'\xff',pusi=True),packet(0x321,b'\x07\x10'+bytes.fromhex('000000007E00'),afc=3),packet(0x321,b'\xff',afc=3)])
  self.load();pat=self.read(0);self.assertEqual(pat['pointer_field'],0);self.assertTrue(pat['section_links'])
  malformed=self.read(11);self.assertIn('Pointer field overruns payload',malformed['issues'])
  pcr=self.read(12);self.assertEqual(pcr['adaptation']['pcr_27mhz'],0);self.assertEqual(pcr['payload_offset'],12)
  self.assertTrue(self.read(13)['issues'])
if __name__=='__main__':unittest.main()
