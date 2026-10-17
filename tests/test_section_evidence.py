"""Additive section evidence contract, using exact synthetic wire sections."""
import sys, tempfile, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from core_client import Core
from make_fixture import section, descriptor, word, crc

class SectionEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.core=Core()
    def tearDown(self):
        self.core.close();self.tmp.cleanup()
    def sdt(self,version=1,number=0,last=1,current=True,bad=False):
        d=descriptor(0x48,b'\x01\x00\x04Test')
        raw=bytearray(section(0x42,1,version,word(2)+b'\xff'+word(100+number)+b'\xff'+word(0x8000+len(d))+d))
        raw[5]=(raw[5]&254)|int(current);raw[6]=number;raw[7]=last;raw[-4:]=crc(raw[:-4]).to_bytes(4,'big')
        if bad:raw[-1]^=1
        return bytes(raw)
    def scan(self,parts,**kwargs):
        counters={};packets=[]
        for item in parts:
            pid,raw=item if isinstance(item,tuple) else (0x11,item)
            cc=counters.get(pid,0);counters[pid]=(cc+1)%16
            packets.append(bytes([0x47,0x40|(pid>>8),pid&255,0x10|cc,0])+raw+b'\xff'*(183-len(raw)))
        p=Path(self.tmp.name)/'evidence.ts';p.write_bytes(b''.join(packets))
        return self.core.call('analyze',{'path':str(p),**kwargs})
    def test_repetitions_do_not_fill_missing_and_invalid_is_retained(self):
        state=self.scan([self.sdt(),self.sdt(),self.sdt(number=1,bad=True)])
        g=state['table_groups'][0]
        self.assertEqual(g['validity'],'mixed');self.assertEqual(g['missing_section_numbers'],[])
        self.assertEqual(g['missing_valid_section_numbers'],[1]);self.assertFalse(g['selected_complete'])
        self.assertEqual(g['valid_observations'],2);self.assertEqual(g['invalid_observations'],1)
        self.assertEqual(g['distribution']['observation_count'],3)
        self.assertEqual(sum(b['count'] for b in g['distribution']['bins']),3)
        bad=next(t for t in state['tables'] if not t['valid']);self.assertEqual(bad['crc']['status'],'invalid')
        detail=self.core.call('inspect',{'id':bad['id']});self.assertEqual(detail['raw_hex'],self.sdt(number=1,bad=True).hex().upper())
        self.assertNotEqual(bad['crc']['transmitted_hex'],bad['crc']['calculated_hex'])
        with self.assertRaises(RuntimeError):self.core.call('preview_rename',{'id':bad['id'],'service_id':101,'name':'No'})
    def test_all_invalid_and_missing_are_distinct(self):
        state=self.scan([self.sdt(bad=True),self.sdt(bad=True)])
        g=state['table_groups'][0];self.assertEqual(g['validity'],'all_invalid')
        self.assertEqual(g['observed_section_numbers'],[0]);self.assertEqual(g['missing_section_numbers'],[1])
        self.assertEqual(g['missing_valid_section_numbers'],[0,1]);self.assertEqual(g['selected_section_ids'],[])
    def test_merged_sources_and_cutoff(self):
        state=self.scan([self.sdt(),self.sdt(number=1),self.sdt()])
        zero=next(t for t in state['tables'] if t['section']==0)
        detail=self.core.call('inspect',{'id':zero['id'],'at_packet':1})
        self.assertTrue(detail['merged']['complete']);self.assertEqual(len(detail['native_table_sources']),2)
        self.assertEqual(set(detail['merged']['source_ids']),{t['id'] for t in state['tables']})
        self.assertEqual(detail['count'],1);self.assertEqual(detail['distribution']['last_packet'],0)
        early=self.core.call('query',{'at_packet':0});self.assertFalse(early['table_groups'][0]['selected_complete'])
        self.assertEqual(early['table_groups'][0]['missing_section_numbers'],[1])
    def test_reused_version_not_resurrected_in_selected_coverage(self):
        state=self.scan([self.sdt(),self.sdt(number=1),self.sdt(version=2),self.sdt()])
        g=next(g for g in state['table_groups'] if g['version']==1)
        self.assertEqual(g['valid_section_numbers'],[0,1]);self.assertFalse(g['selected_complete'])
        self.assertEqual(g['selected_missing_section_numbers'],[1])
    def test_identity_current_next_pid_and_bitrate_not_pcr(self):
        state=self.scan([self.sdt(last=0),self.sdt(last=0,current=False),(0x12,self.sdt(last=0)),self.sdt(last=0)],bitrate=1504)
        self.assertEqual(len(state['table_groups']),3)
        t=next(t for t in state['tables'] if t['pid']==0x11 and t['current'])
        self.assertEqual(t['identity']['current_next'],True);self.assertEqual(t['crc']['status'],'valid')
        self.assertEqual(t['distribution']['last_seconds'],3);self.assertEqual(t['distribution']['min_gap_packets'],3)
        self.assertFalse(t['distribution']['pcr_derived']);self.assertEqual(t['distribution']['basis'],'user supplied bitrate')
    def test_descriptor_parse_failure_is_not_unknown_and_crc_is_independent(self):
        malformed=descriptor(0x48,b'')
        raw=section(0x42,1,1,word(2)+b'\xff'+word(100)+b'\xff'+word(0x8000+len(malformed))+malformed)
        state=self.scan([raw]);row=state['tables'][0]
        self.assertFalse(row['valid']);self.assertEqual(row['crc']['status'],'valid')
        detail=self.core.call('inspect',{'id':row['id']});d=detail['descriptors'][0]
        self.assertTrue(d['decoder_registered']);self.assertEqual(d['decode_status'],'parse_failure')
        self.assertEqual(d['raw'],'4800')

    def test_superseded_merged_wrapper_has_no_mislabeled_section_xml(self):
        state=self.scan([self.sdt(last=0),self.sdt(version=2,last=0)])
        old=next(t for t in state['tables'] if t['version']==1)
        detail=self.core.call('inspect',{'id':old['id'],'at_packet':1})
        self.assertFalse(detail['merged']['complete']);self.assertIsNone(detail['merged']['tsduck_xml'])
        self.assertIsNone(detail['merged']['native_table']);self.assertNotIn(old['id'],detail['merged']['source_ids'])
        self.assertTrue(detail['tsduck_xml']);self.assertNotIn('section_number',state['table_groups'][0]['identity'])
    def test_same_packet_repeat_gap_is_zero(self):
        raw=self.sdt(last=0);packet=bytes([0x47,0x40,0x11,0x10,0])+raw+raw+b'\xff'*(183-2*len(raw))
        p=Path(self.tmp.name)/'same-packet.ts';p.write_bytes(packet)
        state=self.core.call('analyze',{'path':str(p)})
        self.assertEqual(state['tables'][0]['count'],2)
        self.assertEqual(state['table_groups'][0]['distribution']['min_gap_packets'],0)

    def test_short_tot_crc_checked_even_when_demux_accepts_short_section(self):
        raw=b'\x73\x70\x0b\xeb\x96\x12\x34\x56\xf0\x00'
        raw+=crc(raw).to_bytes(4,'big');bad=raw[:-1]+bytes([raw[-1]^1])
        state=self.scan([(0x14,raw),(0x14,bad),(0x14,bad)])
        self.assertEqual(state['crc_errors'],2)
        self.assertEqual({r['crc']['status'] for r in state['tables']},{'valid','invalid'})
        self.assertFalse(next(r for r in state['tables'] if r['crc']['status']=='invalid')['valid'])
    def test_repetitive_burst_distribution_is_bounded(self):
        state=self.scan([self.sdt(last=0)]*20000)
        g=state['table_groups'][0];self.assertEqual(g['distribution']['observation_count'],20000)
        self.assertLessEqual(len(g['distribution']['bins']),32)
        self.assertEqual(g['distribution']['min_gap_packets'],1);self.assertEqual(g['distribution']['max_gap_packets'],1)
        self.assertEqual(len(g['section_ids']),1);self.assertTrue(g['selected_complete'])

    def test_short_tdt_has_no_crc(self):
        state=self.scan([(0x14,b'\x70\x70\x05\xeb\x96\x12\x34\x56')])
        self.assertEqual(state['tables'][0]['crc']['status'],'not_present')
        self.assertIsNone(state['tables'][0]['crc']['transmitted_hex'])
        self.assertIsNone(state['tables'][0]['distribution']['first_seconds'])

    def test_eit_schedule_segment_holes_are_not_missing_sections(self):
        def eit(n,segment_last):
            raw=bytearray(section(0x50,1,1,word(1)+word(2)+bytes([segment_last,0x50])))
            raw[6]=n;raw[7]=8;raw[-4:]=crc(raw[:-4]).to_bytes(4,'big');return bytes(raw)
        state=self.scan([(0x12,eit(0,0)),(0x12,eit(8,8))])
        g=state['table_groups'][0];self.assertEqual(g['expected_section_numbers'],[0,8])
        self.assertEqual(g['missing_section_numbers'],[]);self.assertTrue(g['schedule_unobserved_segments_unknown'])
        self.assertEqual(state['tables'][0]['segment_last_section_number'],0)
        detail=self.core.call('inspect',{'id':state['tables'][0]['id']})
        self.assertTrue(detail['section_native_text']);self.assertFalse(detail['merged']['complete'])

if __name__=='__main__':unittest.main()
