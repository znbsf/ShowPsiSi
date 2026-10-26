"""Real source PES, Teletext captures and exact original unit fragments."""
import hashlib,sys,struct,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from core_client import Core,CoreError
H=[0x15,0x02,0x49,0x5e,0x64,0x73,0x38,0x2f,0xd0,0xc7,0x8c,0x9b,0xa1,0xb6,0xfd,0xea]
def rev(v):return int(f'{v:08b}'[::-1],2)
def odd(v):return v if v.bit_count()%2 else v|128
def unit(row,text=b'',mag=1,header=None):
 address=(row<<3)|(mag&7);body=bytes([rev(H[address&15]),rev(H[address>>4])])
 if row==0:body+=bytes(rev(H[n]) for n in (header or [0,0,0,8,0,0,0,0]))+bytes(rev(odd(v)) for v in text.ljust(32,b' ')[:32])
 else:body+=bytes(rev(odd(v)) for v in text.ljust(40,b' ')[:40])
 return bytes([2,44,0xc0,0xe4])+body
def pes(payload,stream=0xbd):return b'\0\0\x01'+bytes([stream])+struct.pack('>H',len(payload)+39)+bytes([0x80,0,36])+b'\xff'*36+payload
def packetize(packets,pid=0x202,stride=188,first_capacity=184):
 out=[];cc=0
 for data in packets:
  first=True
  while data:
   size=min(first_capacity if first else 184,len(data));chunk=data[:size];data=data[size:];afc=0x10 if size==184 else 0x30;header=bytes([0x47,(pid>>8)|(0x40 if first else 0),pid&255,afc|(cc&15)])
   adaptation=b'' if size==184 else bytes([183-size])+(b'\0'+b'\xff'*(182-size) if size<183 else b'')
   ts=header+adaptation+chunk;assert len(ts)==188
   out.append((b'\0'*4+ts) if stride==192 else ts+b'\0'*16 if stride==204 else ts);first=False;cc+=1
 return b''.join(out)
class TeletextInspectionTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.path=Path(self.tmp.name)/'pages.ts';self.core=Core();self.addCleanup(self.core.close)
 def load(self,units=None,raw=None,**options):
  self.raw=packetize([pes(b'\x10'+b''.join(units or []))],**options) if raw is None else raw;self.path.write_bytes(self.raw);self.state=self.core.call('analyze',{'path':str(self.path),'standards':'dvb','extra_pids':[0x202]});self.rev=self.state['revision'];return self.read()
 def read(self,**kw):return self.core.call('query_teletext',{'analysis_revision':self.rev,'pid':0x202,**kw})
 def test_page_cells_colours_and_exact_unit_source_bytes(self):
  r=self.load([unit(0,b'CAPTURED CLOCK 12:34:56'),unit(1,b'\x01RED\x02GREEN')]);self.assertEqual(r['page_hex'],0x100);self.assertEqual(len(r['cells']),960);c=r['cells'][41];self.assertEqual(c['unicode'],ord('R'));self.assertEqual(c['foreground'],1);self.assertIsNone(r['cells'][0]['packet_index']);self.assertIsNone(r['cells'][80]['packet_index'])
  for row in r['rows']:
   reconstructed=b''.join(self.raw[f['file_offset']:f['file_offset']+f['length']] for f in row['fragments']);self.assertEqual(reconstructed,bytes.fromhex(row['raw_hex']))
 def test_capture_step_preserves_time_and_erase_semantics(self):
  r=self.load([unit(0,b'12:00:00'),unit(1,b'OLD'),unit(0,b'12:00:01'),unit(2,b'NEW')]);self.assertEqual(len(r['captures']),2);self.assertEqual(r['capture_index'],1);self.assertFalse(any(c['source_present'] for c in r['cells'][40:80]));old=self.read(capture_index=0);self.assertEqual(old['cells'][40]['unicode'],ord('O'));self.assertNotEqual(old['rows'][0]['raw_hex'],r['rows'][0]['raw_hex'])
 def test_header_erase_establishes_blank_geometry_without_fabricating_rows(self):
  r=self.load([unit(0),unit(20,b'VISIBLE SUBTITLE')]);self.assertTrue(r['erase_blanks_applied']);self.assertTrue(r['body_layout_complete']);self.assertTrue(r['cells'][800]['geometry_known']);self.assertEqual(r['cells'][800]['unicode'],ord('V'));self.assertFalse(r['cells'][40]['source_present']);self.assertIsNone(r['cells'][40]['packet_index']);self.assertEqual({row['row'] for row in r['rows']},{0,20})
 def test_subcode_and_parallel_magazine_identity(self):
  r=self.load([unit(0,header=[0,0,1,8,0,0,0,0]),unit(1,b'A'),unit(0,mag=2),unit(1,b'B',mag=2),unit(0,header=[0,0,2,8,0,0,0,0]),unit(1,b'C')]);self.assertEqual({(p['page_hex'],p['subcode']) for p in r['pages']},{(0x100,1),(0x100,2),(0x200,0)});self.assertEqual(self.read(page_hex=0x100,subcode=2)['cells'][40]['unicode'],ord('C'))
 def test_invalid_parity_and_unknown_charset_remain_explicit(self):
  bad=bytearray(unit(1,b'A'));bad[6]^=1;r=self.load([unit(0),bytes(bad)]);self.assertGreater(r['parity_errors'],0);self.assertFalse(r['cells'][40]['source_parity_valid'])
  r=self.load([unit(0),unit(28,b'UNSUPPORTED'),unit(1,b'TEXT')]);self.assertTrue(r['charset_override_unsupported']);self.assertEqual(r['cells'][40]['kind'],6)
 def test_double_height_mosaic_and_conceal_attributes(self):
  r=self.load([unit(0),unit(1,b'\x0dTALL'),unit(2,b'IGNORED'),unit(3,b'\x11\x7f\x18HIDDEN')]);self.assertEqual(r['cells'][41]['role'],3);self.assertEqual(r['cells'][81]['role'],4);self.assertEqual(r['cells'][121]['mosaic_mask'],63);self.assertTrue(r['cells'][123]['conceal'])
 def test_direct_pes_header_can_straddle_ts_but_psi_pointer_is_rejected(self):
  data=pes(b'\x10'+unit(0)+unit(1,b'OK'));r=self.load(raw=packetize([data],first_capacity=2));self.assertEqual(r['cells'][40]['unicode'],ord('O'))
  r=self.load(raw=packetize([b'\0'+data]));self.assertEqual(r['status'],'no_acquired_pages');self.assertGreater(r['scan']['errors'],0)
 def test_192_and_204_source_framing_exact_mapping(self):
  for stride in (192,204):
   r=self.load([unit(0),unit(1,b'FRAME')],stride=stride)
   for row in r['rows']:
    for f in row['fragments']:self.assertEqual(f['framing_stride'],stride)
    self.assertEqual(b''.join(self.raw[f['file_offset']:f['file_offset']+f['length']] for f in row['fragments']),bytes.fromhex(row['raw_hex']))
 def test_continuity_gap_cannot_reuse_a_stale_page_header(self):
  raw=bytearray(packetize([pes(b'\x10'+unit(0)+unit(1,b'BEFORE')),pes(b'\x10'+unit(1,b'ORPHAN AFTER GAP'))]));raw[188+3]=(raw[188+3]&0xf0)|3
  r=self.load(raw=bytes(raw));self.assertGreater(r['context_resets'],0);self.assertEqual(r['cells'][40]['unicode'],ord('B'));self.assertEqual(len(r['captures']),1);self.assertGreater(r['unassociated_rows'],0)
 def test_range_revision_source_and_capture_guards(self):
  self.load([unit(0),unit(1,b'OK')])
  with self.assertRaises(CoreError):self.read(capture_index=99)
  with self.assertRaises(CoreError):self.read(analysis_revision=self.rev+1)
  with self.assertRaises(CoreError):self.read(page_hex=0x200,subcode=0)
  self.path.write_bytes(self.raw+b'\0'*188)
  with self.assertRaises(CoreError):self.read()
if __name__=='__main__':unittest.main()
