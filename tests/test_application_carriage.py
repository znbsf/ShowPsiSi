"""PAT/PMT-to-AIT carriage declarations through the actual production core."""
import hashlib
from pathlib import Path
import unittest
import test_application_summaries as f
from make_fixture import section,word,descriptor,crc


def header(raw,number=0,last=0,current=True):
    b=bytearray(raw);b[5]=(b[5]&254)|int(current);b[6]=number;b[7]=last;b[-4:]=crc(b[:-4]).to_bytes(4,'big');return bytes(b)
def pat(programs=((101,0x100),),tsid=1,version=1,**kw):return header(section(0,tsid,version,b''.join(word(program)+word(0xe000|pid) for program,pid in programs)),**kw)
def signalling(entries=((0x10,1),)):return descriptor(0x6f,b''.join(word(0x8000|kind)+bytes([0xe0|version]) for kind,version in entries))
def stream(pid=0x150,kind=5,descriptors=None):
    if descriptors is None:descriptors=signalling()
    return bytes([kind])+word(0xe000|pid)+word(0xf000|len(descriptors))+descriptors
def pmt(program=101,streams=None,common=b'',version=1,**kw):
    if streams is None:streams=[stream()]
    return header(section(2,program,version,word(0xe201)+word(0xf000|len(common))+common+b''.join(streams)),**kw)


class ApplicationCarriageTests(unittest.TestCase):
    setUp=f.ApplicationSummaryTests.setUp
    tearDown=f.ApplicationSummaryTests.tearDown
    objects=f.ApplicationSummaryTests.objects
    assert_evidence=f.ApplicationSummaryTests.assert_evidence
    def scan(self,sections=None,standard='dvb',at_packet=None):
        sections=sections or [(0,pat()),(0x100,pmt()),(0x150,f.ait())]
        self.path=Path(self.tmp.name)/'carriage.ts';self.path.write_bytes(f.packetize(sections));self.before=hashlib.sha256(self.path.read_bytes()).hexdigest()
        self.state=self.core.call('analyze',{'path':str(self.path),'standards':standard,'extra_pids':sorted({pid for pid,_ in sections})})
        ids=[x['id'] for x in self.state['tables'] if x['table_id']==0x74];self.ait_id=ids[-1]
        return self.core.call('inspect',{'id':self.ait_id,'at_packet':self.state['packets']-1 if at_packet is None else at_packet})['application_signalling']
    def carriers(self,s):return self.objects(s,'application_carriage')
    def test_declared_carriage_has_exact_three_table_sources_and_no_onid(self):
        s=self.scan();cards=self.carriers(s);self.assertEqual(s['carriage_context']['status'],'ok');self.assertEqual(len(cards),1);c=cards[0]
        self.assertEqual(c['identity'],{'transport_stream_id':1,'program_number':101,'pmt_pid':256,'ait_pid':336,'application_type':16,'observed_ait_version':1,'test_application_flag':False});self.assertNotIn('original_network_id',c['identity']);self.assertEqual(c['attributes']['runtime_compatibility'],'not_evaluated');self.assertEqual({x['table_identity']['table_id'] for x in c['evidence']},{0,2,0x74});self.assert_evidence(s)
    def test_source_navigation_requires_the_original_analysis_revision(self):
        s=self.scan();e=self.carriers(s)[0]['evidence'][1];args={'id':e['section_id'],'at_packet':e['at_packet'],'analysis_revision':e['analysis_revision']}
        self.assertEqual(self.core.call('inspect',args)['analysis_revision'],e['analysis_revision'])
        self.core.call('analyze',{'path':str(self.path),'standards':'dvb'})
        with self.assertRaises(RuntimeError):self.core.call('inspect',args)
    def test_enrichment_does_not_mutate_query_or_semantic_diff(self):
        self.scan();args={'from_packet':0,'to_packet':self.state['packets']-1};query=self.core.call('query',{});diff=self.core.call('diff_snapshots',args)
        self.core.call('inspect',{'id':self.ait_id,'at_packet':self.state['packets']-1});self.assertEqual(self.core.call('query',{}),query);self.assertEqual(self.core.call('diff_snapshots',args),diff)
    def test_pmt_discovers_ait_without_extra_pid_override(self):
        self.scan();self.state=self.core.call('analyze',{'path':str(self.path),'standards':'dvb'})
        ait=next(x for x in self.state['tables'] if x['table_id']==0x74);s=self.core.call('inspect',{'id':ait['id'],'at_packet':self.state['packets']-1})['application_signalling'];self.assertEqual(self.carriers(s)[0]['resolution_status'],'resolved');self.assertEqual(self.state['crc_errors'],0);self.assert_evidence(s)
    def test_empty_descriptor_is_valid_without_type_or_version_requirement(self):
        s=self.scan([(0,pat()),(0x100,pmt(streams=[stream(descriptors=signalling(()))])),(0x150,f.ait())]);c=self.carriers(s)[0];self.assertEqual(c['resolution_status'],'resolved');self.assertEqual(c['attributes']['version_signalling'],'not_signalled');self.assertEqual(c['attributes']['application_type_advertisement'],'not_signalled');self.assert_evidence(s)
    def test_other_type_advertisement_preserves_stream_carriage_and_explicit_omission(self):
        s=self.scan([(0,pat()),(0x100,pmt(streams=[stream(descriptors=signalling(((0x11,3),)))])),(0x150,f.ait())]);c=self.carriers(s)[0]
        self.assertEqual(c['resolution_status'],'resolved');self.assertEqual(c['attributes']['advertised_application_types'],[0x11]);self.assertEqual(c['attributes']['application_type_advertisement'],'not_listed');self.assertEqual(c['attributes']['version_signalling'],'not_signalled');self.assert_evidence(s)
    def test_mixed_valid_and_malformed_descriptors_keep_limited_version_fact_unresolved(self):
        s=self.scan([(0,pat()),(0x100,pmt(streams=[stream(descriptors=signalling()+descriptor(0x6f,b'\x80'))])),(0x150,f.ait())]);c=self.carriers(s)[0]
        self.assertEqual(c['resolution_status'],'unresolved');self.assertEqual(c['attributes']['descriptor_validation'],'mixed');self.assertEqual(c['attributes']['version_signalling'],'matching');self.assertEqual(c['attributes']['version_signalling_scope'],'validated_descriptor_entries_only');self.assertTrue(c['unresolved_reasons']);self.assertEqual(sum(e['assertion_key']=='descriptor' for e in c['evidence']),2)
        edge=next(e for e in s['relations'] if e['from']==c['node_id']);self.assertEqual(edge['relation'],'declares_carriage');self.assertEqual(edge['resolution_status'],'unresolved');self.assert_evidence(s)
    def test_shared_ait_pid_has_multiple_independent_program_carriers(self):
        s=self.scan([(0,pat(((101,0x100),(102,0x101)))),(0x100,pmt()),(0x101,pmt(program=102)),(0x150,f.ait())]);c=self.carriers(s);self.assertEqual({x['identity']['program_number'] for x in c},{101,102});self.assertTrue(all(x['resolution_status']=='resolved' for x in c));self.assert_evidence(s)
    def test_wrong_stream_type_missing_and_misplaced_descriptor_remain_unresolved(self):
        for raw in [pmt(streams=[stream(kind=0x0b)]),pmt(streams=[stream(descriptors=b'')]),pmt(streams=[stream(descriptors=b'')],common=signalling())]:
            s=self.scan([(0,pat()),(0x100,raw),(0x150,f.ait())]);c=self.carriers(s)[0];self.assertEqual(c['resolution_status'],'unresolved');self.assertEqual(next(e for e in s['relations'] if e['from']==c['node_id'])['relation'],'references_ait_pid');self.assert_evidence(s)
    def test_malformed_and_reserved_descriptor_fields_are_not_promoted(self):
        for desc in [descriptor(0x6f,b'\x80'),descriptor(0x6f,word(0x10)+b'\xe1'),descriptor(0x6f,word(0x8010)+b'\x01')]:
            s=self.scan([(0,pat()),(0x100,pmt(streams=[stream(descriptors=desc)])),(0x150,f.ait())]);c=self.carriers(s)[0];self.assertEqual(c['resolution_status'],'unresolved');self.assertFalse(c['attributes']['valid_descriptor_present']);self.assert_evidence(s)
    def test_captured_reserved_bit_violation_remains_source_linked_and_unknown(self):
        # Exact descriptor bytes observed in the public UHF22 capture. Table 17
        # and TS 102 809 section 5.3.3.2 require the leading reserved bit to be 1.
        s=self.scan([(0,pat()),(0x100,pmt(streams=[stream(descriptors=bytes.fromhex('6f030010e1'))])),(0x150,f.ait(version=4))]);c=self.carriers(s)[0]
        self.assertEqual(c['resolution_status'],'unresolved');self.assertEqual(c['attributes']['version_signalling'],'unavailable_malformed_descriptor');self.assertEqual(c['attributes']['advertised_ait_versions'],[]);self.assert_evidence(s)
    def test_advertised_version_conflicts_preserve_candidates(self):
        for entries,expected in [(((0x10,2),),[2]),(((0x10,1),(0x10,2)),[1,2])]:
            s=self.scan([(0,pat()),(0x100,pmt(streams=[stream(descriptors=signalling(entries))])),(0x150,f.ait())]);c=self.carriers(s)[0];self.assertEqual(c['resolution_status'],'conflict');self.assertEqual(c['attributes']['advertised_ait_versions'],expected)
    def test_identical_repeated_descriptors_keep_every_wire_source(self):
        s=self.scan([(0,pat()),(0x100,pmt(streams=[stream(descriptors=signalling()+signalling())])),(0x150,f.ait())]);c=self.carriers(s)[0];self.assertEqual(c['resolution_status'],'resolved');self.assertEqual(c['attributes']['advertised_ait_versions'],[1]);self.assertEqual(sum(x['assertion_key']=='descriptor' for x in c['evidence']),2);self.assert_evidence(s)
    def test_conflicting_pat_pids_do_not_select_one_owner(self):
        s=self.scan([(0,pat(((101,0x100),(101,0x101)))),(0x100,pmt()),(0x101,pmt()),(0x150,f.ait())]);self.assertEqual(len(self.carriers(s)),2);self.assertTrue(all(x['resolution_status']=='conflict' for x in self.carriers(s)));self.assert_evidence(s)
    def test_ambiguous_pat_transport_context_is_not_guessed(self):
        s=self.scan([(0,pat()),(0,pat(tsid=2)),(0x100,pmt()),(0x150,f.ait())]);self.assertFalse(self.carriers(s));self.assertEqual(s['carriage_context']['status'],'conflict')
    def test_missing_pat_or_wrong_pmt_program_has_no_carrier(self):
        for sections,status in [([(0x100,pmt()),(0x150,f.ait())],'missing_pat'),([(0,pat()),(0x100,pmt(program=102)),(0x150,f.ait())],'unresolved')]:
            s=self.scan(sections);self.assertFalse(self.carriers(s));self.assertEqual(s['carriage_context']['status'],status)
    def test_incomplete_pat_generation_does_not_borrow_old_sections(self):
        s=self.scan([(0,pat(number=0,last=1)),(0,pat(((102,0x101),),number=1,last=1)),(0x100,pmt()),(0x150,f.ait()),(0,pat(version=2,number=0,last=1))]);self.assertFalse(self.carriers(s));self.assertEqual(s['carriage_context']['status'],'incomplete_pat')
        early=self.core.call('inspect',{'id':self.ait_id,'at_packet':3})['application_signalling'];self.assertEqual(len(self.carriers(early)),1)
    def test_pmt_version_reuse_and_same_packet_order_do_not_resurrect_carrier(self):
        a=pmt(streams=[],version=31,number=0,last=1);b=pmt(version=31,number=1,last=1);new=pmt(streams=[],version=0,number=0,last=1)
        s=self.scan([(0,pat()),(0x100,a),(0x100,b),(0x150,f.ait()),(0x100,new+a)]);self.assertFalse(self.carriers(s));early=self.core.call('inspect',{'id':self.ait_id,'at_packet':3})['application_signalling'];self.assertEqual(len(self.carriers(early)),1)
    def test_next_and_crc_invalid_pmt_do_not_supply_current_carriage(self):
        bad=bytearray(pmt());bad[-1]^=1
        for raw in [pmt(current=False),bytes(bad)]:s=self.scan([(0,pat()),(0x100,raw),(0x150,f.ait())]);self.assertFalse(self.carriers(s))
        s=self.scan([(0,pat()),(0x100,pmt()),(0x150,f.ait(current=False))]);self.assertFalse(self.carriers(s));self.assertEqual(s['carriage_context']['status'],'unsupported_next')
    def test_superseded_ait_is_not_enriched(self):
        self.scan([(0,pat()),(0x100,pmt()),(0x150,f.ait()),(0x150,f.ait(version=2))]);old=next(x['id'] for x in self.state['tables'] if x['table_id']==0x74 and x['version']==1);s=self.core.call('inspect',{'id':old,'at_packet':3})['application_signalling'];self.assertFalse(self.carriers(s));self.assertEqual(s['carriage_context']['status'],'unavailable_ait')
    def test_short_pat_and_pmt_envelopes_do_not_supply_long_table_identity(self):
        fake=bytearray(pat());fake[1]&=0x7f;fake[-4:]=crc(fake[:-4]).to_bytes(4,'big')
        for raw in [bytes.fromhex('003000'),bytes(fake)]:
            s=self.scan([(0,raw),(0x100,pmt()),(0x150,f.ait())]);self.assertFalse(self.carriers(s));self.assertIn(s['carriage_context']['status'],['missing_pat','incomplete_pat'])
        s=self.scan([(0,pat()),(0x100,bytes.fromhex('023000')),(0x150,f.ait())]);self.assertFalse(self.carriers(s))
    def test_profile_guard_and_program_zero(self):
        s=self.scan(standard='atsc');self.assertFalse(self.carriers(s));self.assertEqual(s['carriage_context']['status'],'unsupported_profile')
        s=self.scan([(0,pat(((0,0x100),))),(0x100,pmt(program=0)),(0x150,f.ait())]);self.assertFalse(self.carriers(s))
    def test_duplicate_stream_entries_are_conflicting_not_collapsed(self):
        s=self.scan([(0,pat()),(0x100,pmt(streams=[stream(),stream()])),(0x150,f.ait())]);self.assertEqual(len(self.carriers(s)),2);self.assertTrue(all(x['resolution_status']=='conflict' for x in self.carriers(s)));self.assert_evidence(s)
    def test_card_cap_returns_no_partial_carriage_graph(self):
        sections=[(0,pat(tuple((i,0x200+i) for i in range(1,258))))]+[(0x200+i,pmt(program=i)) for i in range(1,258)]+[(0x150,f.ait())]
        s=self.scan(sections);self.assertEqual(s['carriage_context']['status'],'resource_limit');self.assertFalse(self.carriers(s));self.assertTrue(self.objects(s,'application'))
    def test_pat_mapping_work_is_bounded_before_typed_decode(self):
        sections=[(0,pat(tuple((101,0x100) for _ in range(1000)),number=i,last=4)) for i in range(5)]+[(0x100,pmt()),(0x150,f.ait())];s=self.scan(sections);self.assertEqual(s['carriage_context']['status'],'resource_limit');self.assertFalse(self.carriers(s))
    def test_pmt_stream_work_is_bounded_before_typed_decode(self):
        sections=[(0,pat(tuple((i,0x200+i) for i in range(1,22))))]+[(0x200+i,pmt(program=i,streams=[stream(pid=0x400+j,kind=2,descriptors=b'') for j in range(200)])) for i in range(1,22)]+[(0x150,f.ait())];s=self.scan(sections);self.assertEqual(s['carriage_context']['status'],'resource_limit');self.assertFalse(self.carriers(s))
    def test_source_cap_does_not_drop_repeated_mapping_evidence_silently(self):
        sections=[(0,pat(tuple((101,0x100) for _ in range(800)),number=i,last=2)) for i in range(3)]+[(0x100,pmt()),(0x150,f.ait())];s=self.scan(sections);self.assertEqual(s['carriage_context']['status'],'resource_limit');self.assertFalse(self.carriers(s));self.assertIn('source-reference',' '.join(s['diagnostics']))
    def test_descriptor_work_is_bounded_before_typed_decode(self):
        programs=tuple((i,0x200+i) for i in range(1,43));common=descriptor(0x80,b'')*200
        sections=[(0,pat(programs))]+[(pid,pmt(program=i,streams=[],common=common)) for i,pid in programs]+[(0x150,f.ait())];s=self.scan(sections);self.assertEqual(s['carriage_context']['status'],'resource_limit');self.assertFalse(self.carriers(s))
    def test_group_cap_is_explicit_and_atomic(self):
        programs=[(i,0x500+i) for i in range(1,1025)]
        sections=[(0,pat(programs[:512],number=0,last=1)),(0,pat(programs[512:],number=1,last=1))]+[(pid,pmt(program=i,streams=[])) for i,pid in programs]+[(0x150,f.ait())];s=self.scan(sections);self.assertEqual(s['carriage_context']['status'],'resource_limit');self.assertFalse(self.carriers(s))
    def test_unrelated_pid_and_program_loop_names_cannot_create_carriage(self):
        s=self.scan([(0,pat()),(0x100,pmt(streams=[stream(pid=0x151)])),(0x150,f.ait())]);self.assertFalse(self.carriers(s));self.assertEqual(s['carriage_context']['status'],'unresolved')

if __name__=='__main__':unittest.main()
