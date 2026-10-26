"""Additive section evidence contract, using exact synthetic wire sections."""
import sys, tempfile, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from core_client import Core
from make_fixture import section, descriptor, word, crc

class SectionEvidenceTests(unittest.TestCase):
    def test_all_table_history_transitions_and_exact_jump(self):
        pat1=section(0,1,1,word(100)+word(0xe100))
        pat2=section(0,1,2,word(100)+word(0xe101))
        pmt=section(2,100,1,word(0xe200)+word(0xf000))
        private=section(0x80,3,1,b'private-evidence')
        tdt=b'\x70\x70\x05\xeb\x96\x12\x34\x56'
        state=self.scan([(0,pat1),(0,pat1),(0,pat2),(0,pat1),(0x100,pmt),
                         (0x11,private),(0x14,tdt),(0x14,tdt),
                         self.sdt(last=0,current=False), self.sdt(last=0,bad=True)])
        history=state['table_history']
        self.assertEqual({h['table_id'] for h in history},{0,2,0x80,0x70,0x42})
        pats=[h for h in history if h['table_id']==0]
        self.assertEqual([h['version'] for h in pats],[1,2,1])
        self.assertEqual([h['at_packet'] for h in pats],[0,2,3])
        self.assertEqual(pats[0]['last_packet'],1)
        self.assertEqual(pats[0]['observations'],2)
        short=next(h for h in history if h['table_id']==0x70)
        self.assertIsNone(short['version']);self.assertEqual(short['observations'],2)
        self.assertTrue(any(not h['valid'] for h in history))
        self.assertTrue(any(not h['current'] for h in history))
        for h in history:
            snapshot=self.core.call('query',{'at_packet':h['at_packet']})
            self.assertIn(h['id'],[r['id'] for r in snapshot['tables']])
            inspected=self.core.call('inspect',{'id':h['id'],'at_packet':h['at_packet']})
            self.assertEqual(inspected['native_table_at_packet'],h['at_packet'])
            self.assertEqual(inspected['pid'],h['pid'])
            self.assertEqual(snapshot['table_history'],history)
        cleared=self.scan([(0,pat2)])
        self.assertEqual(len(cleared['table_history']),1)

    def test_short_pat_pmt_are_retained_invalid_without_crash_or_derived_fields(self):
        for tid,pid in [(0,0),(2,0x100)]:
            for length in (0,1,2,5,8,12,20,40):
                with self.subTest(table_id=tid,payload_length=length):
                    raw=bytes([tid,0x30,length])+bytes(length)
                    state=self.scan([(pid,raw)],standards='dvb',extra_pids=[pid])
                    row=next(r for r in state['tables'] if r['table_id']==tid)
                    self.assertFalse(row['valid']);self.assertTrue(any(d['code']=='long_section_required' for d in state['diagnostics']))
                    detail=self.core.call('inspect',{'id':row['id']});self.assertEqual(detail['raw_hex'],raw.hex().upper());self.assertNotIn('programs',detail['fields']);self.assertNotIn('streams',detail['fields']);self.assertEqual(detail['si_structure']['children'],[])
                    graph=self.core.call('query_topology',{});self.assertFalse(any(n['object_type'] in ('program','component') for n in graph['nodes']))
    def test_short_pat_pmt_cannot_discover_forged_dependent_pids(self):
        pat=bytearray(section(0,1,1,word(100)+word(0xe321)));pat[1]&=0x7f;pat[-4:]=crc(pat[:-4]).to_bytes(4,'big')
        pmt=bytearray(section(2,100,1,word(0xe200)+word(0xf000)+b'\x05'+word(0xe321)+word(0xf000)));pmt[1]&=0x7f;pmt[-4:]=crc(pmt[:-4]).to_bytes(4,'big')
        private=section(0x80,3,1,b'not-discovered')
        for pid,raw in [(0,pat),(0x100,pmt)]:
            with self.subTest(table_id=raw[0]):
                state=self.scan([(pid,bytes(raw)),(0x321,private)],standards='dvb',extra_pids=[pid]);self.assertNotIn(0x321,[r['pid'] for r in state['tables']]);self.assertFalse(state['tables'][0]['valid'])
        # The same process remains usable and normal discovery still works.
        good=section(0,1,1,word(100)+word(0xe321));state=self.scan([(0,good),(0x321,private)],standards='dvb');self.assertIn(0x321,[r['pid'] for r in state['tables']])

    @staticmethod
    def short_envelope(raw):
        changed=bytearray(raw);changed[1]&=0x7f;changed[-4:]=crc(changed[:-4]).to_bytes(4,'big');return bytes(changed)
    def test_short_sdt_and_cat_do_not_fabricate_services_or_descriptors(self):
        for tid,pid,raw in [(0x42,0x11,self.sdt(last=0)),(0x46,0x11,section(0x46,1,1,self.sdt(last=0)[8:-4])),(1,1,section(1,1,1,descriptor(9,word(1)+word(0xe100))))]:
            with self.subTest(table_id=tid):
                raw=self.short_envelope(raw);state=self.scan([(pid,raw)],standards='dvb',extra_pids=[pid]);row=state['tables'][0]
                self.assertFalse(row['valid']);self.assertEqual(state['services'],[]);self.assertEqual(state['events'],[])
                detail=self.core.call('inspect',{'id':row['id']});self.assertEqual(detail['raw_hex'],raw.hex().upper());self.assertEqual(detail['services'],[]);self.assertEqual(detail['descriptors'],[]);self.assertTrue(any(d['code']=='long_section_required' for d in state['diagnostics']))
                graph=self.core.call('query_topology',{});self.assertFalse(any(n['object_type']=='service' for n in graph['nodes']))
    def test_short_network_bouquet_and_eit_tables_do_not_fabricate_lcns_or_events(self):
        lcn=descriptor(0x5f,(0x28).to_bytes(4,'big'))+descriptor(0x83,word(100)+word(0x8007));transport=word(1)+word(2)+word(0xf000|len(lcn))+lcn;network=word(0xf000)+word(0xf000|len(transport))+transport
        for tid,pid in [(0x40,0x10),(0x41,0x10),(0x4a,0x11)]:
            with self.subTest(table_id=tid):
                raw=self.short_envelope(section(tid,10,1,network));state=self.scan([self.sdt(last=0),(pid,raw)],standards='dvb');row=next(r for r in state['tables'] if r['table_id']==tid)
                self.assertFalse(row['valid']);self.assertEqual(len(state['services']),1);self.assertIsNone(state['services'][0]['logical_channel_number']);detail=self.core.call('inspect',{'id':row['id']});self.assertNotIn('transports',detail['fields']);self.assertEqual(detail['descriptors'],[]);self.assertEqual(detail['raw_hex'],raw.hex().upper())
        title=descriptor(0x4d,b'eng\x03Bad\x00');event=word(123)+bytes.fromhex('eb96123456010000')+word(0x8000|len(title))+title
        for tid in range(0x4e,0x70):
            with self.subTest(table_id=tid):
                raw=self.short_envelope(section(tid,100,1,word(1)+word(2)+bytes([0,tid])+event));state=self.scan([(0x12,raw)],standards='dvb');self.assertFalse(state['tables'][0]['valid']);self.assertEqual(state['events'],[]);detail=self.core.call('inspect',{'id':state['tables'][0]['id']});self.assertEqual(detail['events'],[]);self.assertEqual(detail['raw_hex'],raw.hex().upper())
        good=section(0x4e,100,1,word(1)+word(2)+bytes([0,0x4e])+event);self.assertEqual(len(self.scan([(0x12,good)],standards='dvb')['events']),1)
        good=section(0x40,10,1,network);self.assertEqual(self.scan([self.sdt(last=0),(0x10,good)],standards='dvb')['services'][0]['logical_channel_number'],7)
    def test_genuine_short_tdt_tot_rst_remain_valid(self):
        tdt=bytes.fromhex('707005eb96123456');tot=bytearray.fromhex('73700beb96123456f000');tot+=crc(tot).to_bytes(4,'big');rst=bytes.fromhex('717000')
        state=self.scan([(0x14,tdt),(0x14,bytes(tot)),(0x13,rst)],standards='dvb');self.assertEqual(len(state['tables']),3);self.assertTrue(all(r['valid'] for r in state['tables']));self.assertFalse(state['diagnostics'])

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
