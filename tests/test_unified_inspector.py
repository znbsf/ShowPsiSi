"""Real-engine evidence for the unified inspector, using synthetic DVB sections."""
import datetime
import json
import sys
import tempfile
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from core_client import Core
from make_fixture import section,descriptor,word,crc

def fixture():
    pat=section(0,0x1001,31,word(101)+word(0xe100))
    pmt=section(2,101,1,word(0xe101)+word(0xf000)+bytes([0x1b])+word(0xe101)+word(0xf006)+descriptor(0x52,b'\x01')+descriptor(0xe2,b'\x42'))
    transport=word(0x1001)+word(0x2001)+word(0xf000)
    name=descriptor(0x47,b'Local fixture bouquet')
    bat=section(0x4a,88,1,word(0xf000+len(name))+name+word(0xf000+len(transport))+transport)
    mjd=(datetime.date(2026,10,21)-datetime.date(1858,11,17)).days
    next_pat=bytearray(pat);next_pat[5]&=0xfe;next_pat[-4:]=crc(next_pat[:-4]).to_bytes(4,'big')
    pairs=[(0,pat),(0x100,pmt),(0x11,bat),(0,bytes(next_pat)),(0,section(0,0x1001,0,word(101)+word(0xe100))),(0,pat)]
    for hour in [9,10,9]:
        utc=word(mjd)+bytes([0x09 if hour==9 else 0x10,0,0])
        tdt=b'\x70\x70\x05'+utc
        tot=b'\x73\x70\x0b'+utc+word(0xf000);tot+=crc(tot).to_bytes(4,'big')
        pairs += [(0x14,tdt),(0x14,tot)]
    cc={};packets=[]
    for pid,raw in pairs:
        n=cc.get(pid,0);cc[pid]=(n+1)%16
        packets.append(bytes([0x47,0x40|(pid>>8),pid&255,0x10|n,0])+raw+b'\xff'*(183-len(raw)))
    return b''.join(packets)

class UnifiedInspectorEngineTests(unittest.TestCase):
    def test_short_syntax_repeats_and_program_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'inspector.ts';path.write_bytes(fixture())
            core=Core()
            try:
                state=core.call('analyze',{'path':str(path),'standards':'dvb'})
                self.assertEqual(state['crc_errors'],0)
                details=[core.call('inspect',{'id':r['id']}) for r in state['tables']]
                times=[r for r in state['tables'] if r['table_id'] in (0x70,0x73)]
                self.assertEqual(len(times),4)
                self.assertEqual(sorted(r['count'] for r in times),[1,1,2,2])
                sequence=[r for r in state['table_history'] if r['table_id']==0x70]
                self.assertEqual(len(sequence),3)
                self.assertEqual(sequence[0]['id'],sequence[2]['id'])
                self.assertNotEqual(sequence[0]['id'],sequence[1]['id'])
                for r in sequence:
                    self.assertFalse(r['versioning_supported'])
                    for key in ('current','extension','section'):self.assertIsNone(r[key])
                for group in state['table_groups']:
                    if group['table_id'] in (0x70,0x73):
                        self.assertIn('DVB time',group['coverage_model'])
                        self.assertEqual(group['observed_section_numbers'],[])
                for r in times:
                    self.assertFalse(r['versioning_supported'])
                    self.assertIn('2026',r['utc_time'])
                    for key in ('version','current','extension','section','last_section'):self.assertIsNone(r[key])
                    self.assertIsNone(r['identity']['version'])
                    self.assertEqual(r['crc']['status'],'not_present' if r['table_id']==0x70 else 'valid')
                pats=[r for r in state['tables'] if r['name']=='PAT']
                self.assertEqual(len(pats),3)
                self.assertEqual({(r['version'],r['current']) for r in pats},{(31,True),(31,False),(0,True)})
                self.assertEqual(sum(r['count'] for r in pats),4)
                out=ROOT/'artifacts/unified-inspector';out.mkdir(parents=True,exist_ok=True)
                (out/'fixture.ts').write_bytes(path.read_bytes())
                (out/'engine-evidence.json').write_text(json.dumps({'state':state,'details':details},indent=2),encoding='utf-8')
            finally:core.close()

if __name__=='__main__':unittest.main()
