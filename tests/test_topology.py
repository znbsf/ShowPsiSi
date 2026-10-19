"""Actual JSONL/MCP engine topology contract and adversarial wire fixtures."""
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from topology_fixture import ROOT, pat, pmt, sdt, nit, channel, vct, parts, write_ts, versioned, japan_descriptors, descriptor, word
from core_client import Core


class TopologyTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.core=Core()
    def tearDown(self):
        self.core.close();self.tmp.cleanup()
    def scan(self, sections=None, profile='dvb', **kwargs):
        self.path=write_ts(Path(self.tmp.name)/'topology.ts',parts(profile) if sections is None else sections)
        self.before=hashlib.sha256(self.path.read_bytes()).hexdigest()
        return self.core.call('analyze',{'path':str(self.path),'standards':profile,**kwargs})
    def graph(self, **kwargs):
        return self.core.call('query_topology',{'limit':500,**kwargs})
    def nodes(self, graph, kind):return [n for n in graph['nodes'] if n['object_type']==kind]
    def assert_evidence(self, graph):
        cache={}
        for entity in graph['nodes']+graph['edges']:
            self.assertTrue(entity['evidence'],entity)
            for e in entity['evidence']:
                self.assertEqual(e['analysis_revision'],graph['analysis_revision']);self.assertEqual(e['at_packet'],graph['at_packet'])
                sid=e['section_id']
                if sid not in cache:cache[sid]=self.core.call('inspect',{'id':sid,'at_packet':e['at_packet']})
                detail=cache[sid];self.assertEqual(detail['analysis_revision'],e['analysis_revision'])
                self.assertLessEqual(max(detail['occurrence_end_packets']),e['at_packet'])
                self.assertEqual(detail['pid'],e['table_identity']['pid'])
                locator=e['locator'];span=locator['byte_range']
                if span:
                    self.assertEqual(span['offset_scope'],'section_bytes');self.assertGreater(span['length'],0)
                    self.assertLessEqual(span['offset']+span['length'],len(detail['raw_hex'])//2)
                    self.assertTrue(any(a.get('field_id')==locator['field_id'] and a.get('container_id')==locator['container_id'] and a['byte_range']==span for a in detail['evidence_anchors']))
                else:self.assertEqual(locator['precision'],'section')
        self.assertEqual(hashlib.sha256(self.path.read_bytes()).hexdigest(),self.before)
    def test_short_section_anchors_do_not_invent_long_header_fields(self):
        from make_fixture import crc
        tdt=bytes.fromhex('707005e190123456')
        tot=bytearray.fromhex('73700be190123456f000')
        tot+=crc(tot).to_bytes(4,'big')
        for raw in (tdt,bytes(tot)):
            with self.subTest(table_id=raw[0]):
                state=self.scan([(0x14,raw)])
                detail=self.core.call('inspect',{'id':state['tables'][0]['id']})
                anchors=detail['evidence_anchors']
                self.assertFalse(any(a['display_path']=='table_id_extension' for a in anchors))
                header=next(a for a in anchors if a['display_path']=='section_header')
                self.assertEqual(header['byte_range'],{'offset_scope':'section_bytes','offset':0,'length':3})
                self.assertEqual(detail['raw_hex'],raw.hex().upper())

    def test_all_three_real_adapters_and_every_evidence_anchor(self):
        for profile in ['dvb','atsc','isdb-japan']:
            with self.subTest(profile=profile):
                state=self.scan(profile=profile);before=self.core.call('query',{});g=self.graph();self.assertEqual(before,self.core.call('query',{}));self.assertEqual(g['analysis_revision'],state['revision'])
                self.assertEqual(g['interpretation_profile'],profile);self.assertTrue(g['nodes']);self.assert_evidence(g)
                self.assertEqual(g['counts']['nodes'],len(g['nodes']));self.assertEqual(g['counts']['edges'],len(g['edges']))
    def test_dvb_announced_other_transport_never_borrows_pmt(self):
        self.scan([pat(),pmt(),sdt(),sdt(onid=3,tsid=1,tid=0x46),nit(transports=((2,1,b''),(3,1,b'')))])
        g=self.graph();services=self.nodes(g,'service');self.assertEqual(len(services),2)
        remote=next(s for s in services if s['identity']['original_network_id']==3)
        self.assertEqual(remote['observation_status'],'announced_only');self.assertNotIn('pmt_pid',remote['attributes'])
        self.assertTrue(all(c['parent_id']!=remote['node_id'] for c in self.nodes(g,'component')))
        self.assert_evidence(g)
    def test_multi_nit_membership_retained_without_duplicate_transport(self):
        self.scan([pat(),pmt(),sdt(),nit(),nit(network=11)])
        g=self.graph();self.assertEqual(len(self.nodes(g,'transport')),1)
        self.assertEqual(len([e for e in g['edges'] if e['relation']=='announces']),2)
    def test_pat_only_identity_is_unknown_not_zero(self):
        self.scan([pat(programs=((0,0x10),(100,0x100))),pmt()]);g=self.graph()
        self.assertEqual(len(self.nodes(g,'mpeg_program')),1);t=self.nodes(g,'transport_observation')[0]
        self.assertIsNone(t['identity']['original_network_id']);self.assertEqual(len(self.nodes(g,'service')),0)
        self.assertNotIn('network',[n['object_type'] for n in g['nodes']]);self.assert_evidence(g)
    def test_actual_sdt_ambiguous_onid_never_assigned_arbitrarily(self):
        self.scan([pat(),pmt(),sdt(),sdt(onid=3)]);g=self.graph()
        for n in self.nodes(g,'service'):
            self.assertEqual(n['resolution_status'],'conflict');self.assertNotIn('pmt_pid',n['attributes'])
        self.assertEqual(len(self.nodes(g,'mpeg_program')),1)
    def test_same_sid_different_transport_and_extra_pid_do_not_merge(self):
        self.scan([pat(),pmt(),sdt(),sdt(onid=2,tsid=9,tid=0x46),sdt(onid=4,pid=0x300)],extra_pids=[0x300]);g=self.graph()
        self.assertEqual(len(self.nodes(g,'service')),2)
        self.assertFalse(any(n['identity'].get('original_network_id')==4 for n in g['nodes']))
    def test_conflicting_names_and_pat_mapping_preserve_both(self):
        self.scan([pat(programs=((100,0x100),(100,0x101))),pmt(),sdt(services=((100,'First'),(100,'Other')))])
        g=self.graph();n=self.nodes(g,'service')[0];self.assertEqual(n['resolution_status'],'conflict')
        self.assertIsNone(n['attributes']['name']);self.assertEqual({c['value'] for c in n['attribute_conflicts']['name']},{'First','Other'})
        self.assertIsNone(n['attributes']['pmt_pid']);self.assertFalse(self.nodes(g,'component'));self.assert_evidence(g)
    def test_pmt_switch_cutoff_no_old_pmt_fallback(self):
        self.scan([pat(),pmt(),sdt(),pat(programs=((100,0x101),),version=2),pmt(pid=0x101,streams=((0xf0,0x210,b''),),pcr=0x210)])
        old=self.graph(at_packet=2);gap=self.graph(at_packet=3);latest=self.graph()
        self.assertEqual(len(self.nodes(old,'component')),2);self.assertFalse(self.nodes(gap,'component'))
        c=self.nodes(latest,'component')[0];self.assertEqual(c['attributes']['pid'],0x210);self.assertEqual(c['attributes']['classification'],'unknown')
        self.assert_evidence(old);self.assert_evidence(gap)
    def test_generation_missing_sibling_crc_next_and_reused_version(self):
        a=sdt(number=0,last=1,services=((100,'One'),));b=sdt(number=1,last=1,services=((101,'Two'),))
        self.scan([pat(),a,b,sdt(version=2,number=0,last=1),a])
        self.assertEqual(len(self.nodes(self.graph(at_packet=2),'service')),2)
        self.assertFalse(self.nodes(self.graph(),'service'));self.assertTrue(self.graph()['diagnostics'])
        self.scan([pat(),a,(b[0],versioned(b[1],number=1,last=1,bad=True)),sdt(current=False)])
        self.assertFalse(self.nodes(self.graph(),'service'))
    def test_same_version_changed_content_and_later_repetition_cutoff(self):
        self.scan([pat(),pmt(),sdt(services=((100,'Old'),)),sdt(services=((100,'New'),)),sdt(services=((100,'Old'),))])
        for cutoff,name in [(2,'Old'),(3,'New'),(4,'Old')]:
            g=self.graph(at_packet=cutoff);self.assertEqual(self.nodes(g,'service')[0]['attributes']['name'],name);self.assert_evidence(g)
    def test_vct_one_two_part_source_duplicate_and_header_tsid(self):
        self.scan([pat(),pmt(),vct([channel(),channel(8,2,source=55)],tsid=99),vct([channel(0x3f1,7)],tid=0xc9)],profile='atsc')
        g=self.graph();channels=self.nodes(g,'virtual_channel');self.assertEqual(len(channels),3)
        self.assertEqual({n['attributes']['atsc_source_id'] for n in channels},{55})
        self.assertEqual(next(n for n in channels if n['attributes']['channel_number']['format']=='one_part')['attributes']['channel_number']['one_part'],1031)
        self.assertEqual(len([e for e in g['edges'] if e['relation']=='maps_to']),3)
        self.assertFalse(any('original_network_id' in n['identity'] for n in g['nodes']));self.assert_evidence(g)
    def test_vct_remote_analog_inactive_hidden_no_false_pmt(self):
        self.scan([pat(),pmt(),vct([channel(7,1,tsid=9),channel(7,2,program=0),channel(7,3,program=65535),channel(7,4,hidden=True)])],profile='atsc')
        g=self.graph();channels=self.nodes(g,'virtual_channel');self.assertEqual(len(channels),4)
        self.assertEqual(sum(n['attributes'].get('mapping_status')=='resolved' for n in channels),1)
        self.assertEqual(len(self.nodes(g,'mpeg_program_reference')),1)
        self.assertTrue(next(n for n in channels if n['attributes']['channel_number']['minor']==4)['attributes']['hidden'])
    def test_duplicate_vct_slot_is_separate_observation_conflict(self):
        self.scan([vct([channel(source=55),channel(source=56)])],profile='atsc');g=self.graph()
        channels=self.nodes(g,'virtual_channel');self.assertEqual(len(channels),2);self.assertNotEqual(channels[0]['node_id'],channels[1]['node_id'])
        self.assertTrue(all(n['resolution_status']=='conflict' for n in channels));self.assert_evidence(g)
    def test_service_location_conflict_is_not_missing_pmt_replacement(self):
        desc=descriptor(0xa1,word(0xe202)+b'\x01'+b'\x81'+word(0xe202)+b'eng')
        self.scan([pat(),pmt(),vct([channel(desc=desc)])],profile='atsc');g=self.graph()
        n=self.nodes(g,'virtual_channel')[0];self.assertEqual(n['resolution_status'],'conflict')
        self.assertTrue(any(e['resolution_status']=='conflict' for e in g['edges'] if e['relation']=='maps_to'));self.assert_evidence(g)
        self.scan([pat(),vct([channel(desc=desc)])],profile='atsc');self.assertFalse(self.nodes(self.graph(),'component'))
    def test_vct_numbering_reserved_and_profile_collision_not_guessed(self):
        self.scan([vct()],profile='auto');g=self.graph();self.assertFalse(self.nodes(g,'virtual_channel'));self.assertEqual(g['status'],'unresolved')
        self.scan([vct()],profile='isdb-japan');self.assertFalse(self.nodes(self.graph(),'virtual_channel'))
    def test_isdb_regional_guard_remote_key_and_partial_reference(self):
        for profile in ['isdb-japan','isdb-brazil','isdb']:
            self.scan([pat(),pmt(),sdt(),nit(transports=((2,1,japan_descriptors()),))],profile=profile)
            g=self.graph();t=self.nodes(g,'transport')[0]
            if profile=='isdb-japan':
                self.assertEqual(t['attributes']['remote_control_key_id'],7);self.assertEqual(len(self.nodes(g,'service_reference')),1)
                self.assertTrue(any(e['relation']=='references' and ':service:' in e['to'] for e in g['edges']))
                self.assertEqual(t['attributes']['transmission_types'][0]['transmission_type_info'],15)
            else:self.assertNotIn('remote_control_key_id',t['attributes']);self.assertFalse(self.nodes(g,'service_reference'))
            self.assertEqual(g['interpretation_profile'],profile);self.assert_evidence(g)
    def test_private_tags_not_mistaken_for_isdb_or_media(self):
        private=descriptor(0xfb,word(100))+descriptor(0xcd,b'\x07\x01\x0f\x01'+word(100))
        self.scan([pat(),pmt(streams=((0x81,0x200,b''),)),sdt(),nit(transports=((2,1,private),))])
        g=self.graph();self.assertFalse(self.nodes(g,'service_reference'));self.assertNotIn('remote_control_key_id',self.nodes(g,'transport')[0]['attributes'])
        self.assertEqual(self.nodes(g,'component')[0]['attributes']['classification'],'unknown')
    def test_paging_roots_context_and_profile_filter(self):
        self.scan();all_nodes=self.graph()['nodes'];seen=[];offset=0
        while True:
            g=self.graph(offset=offset,limit=1);seen.extend(n['node_id'] for n in g['nodes'])
            if not g['page']['has_more']:break
            self.assertEqual(g['page']['next_offset'],offset+1);offset=g['page']['next_offset']
        self.assertEqual(seen,[n['node_id'] for n in all_nodes]);roots=self.graph(parent_id='')
        self.assertTrue(all(n['parent_id'] is None for n in roots['nodes']))
        parent=roots['nodes'][0]['node_id'];children=self.graph(parent_id=parent)
        self.assertTrue(all(n['parent_id']==parent for n in children['nodes']));self.assertTrue(children['context_nodes'])
        self.assertFalse(self.graph(family='atsc')['nodes'])
        self.assertFalse(self.graph(offset=9007199254740991)['nodes'])
        with self.assertRaises(RuntimeError):self.graph(parent_id='does-not-exist')
        with self.assertRaises(RuntimeError):self.graph(limit=501)
    def test_revision_cutoff_failure_and_no_existing_semantic_changes(self):
        with self.assertRaises(RuntimeError):self.graph()
        s=self.scan();before=self.core.call('query',{});g=self.graph();after=self.core.call('query',{})
        self.assertEqual(before,after);self.assertEqual(g['at_packet'],s['packets']-1)
        with self.assertRaises(RuntimeError):self.graph(at_packet=s['packets'])
        with self.assertRaises(RuntimeError):self.graph(analysis_revision=s['revision']+1)
        self.scan();
        with self.assertRaises(RuntimeError):self.graph(analysis_revision=s['revision'])
        with self.assertRaises(RuntimeError):self.core.call('analyze',{'path':str(Path(self.tmp.name)/'missing.ts')})
        with self.assertRaises(RuntimeError):self.graph()
    def test_same_packet_receive_order_and_version_rollover(self):
        a=sdt(version=31,number=0,last=1);b=sdt(version=31,number=1,last=1,services=((101,'Other'),))
        zero=sdt(version=0,number=0,last=1)
        self.scan([pat(),pmt(),a,b,(0x11,zero[1]+a[1])])
        self.assertEqual(len(self.nodes(self.graph(at_packet=3),'service')),2)
        g=self.graph(at_packet=4);self.assertFalse(self.nodes(g,'service'));self.assertTrue(g['diagnostics'])
        self.assert_evidence(g)
    def test_multisection_vct_completion_and_reserved_number(self):
        self.scan([pat(),pmt(),vct([channel()],number=0,last=1),vct([channel(8,2)],number=1,last=1)],profile='atsc')
        self.assertFalse(self.nodes(self.graph(at_packet=2),'virtual_channel'))
        g=self.graph();self.assertEqual(len(self.nodes(g,'virtual_channel')),2);self.assert_evidence(g)
        self.scan([vct([channel(1001,0,source=0),channel(1002,0,source=0)],tid=0xc9)],profile='atsc')
        g=self.graph();self.assertEqual(len(self.nodes(g,'programme_source_reference')),2)
        self.assertTrue(all(n['attributes']['channel_number']['format']=='reserved' and n['resolution_status']=='unresolved' for n in self.nodes(g,'virtual_channel')))
    def test_malformed_vct_retains_raw_without_semantic_channels(self):
        from make_fixture import crc
        pid,raw=vct();raw=bytearray(raw);raw[9]=2;raw[-4:]=crc(raw[:-4]).to_bytes(4,'big')
        state=self.scan([(pid,bytes(raw))],profile='atsc');g=self.graph()
        self.assertFalse(self.nodes(g,'virtual_channel'));self.assertEqual(g['counts']['raw_sections'],1);self.assertEqual(g['status'],'incomplete')
        self.assertTrue(any(d['code']=='vct_parse_failure' for d in g['diagnostics']))
        detail=self.core.call('inspect',{'id':state['tables'][0]['id']});self.assertEqual(detail['raw_hex'],raw.hex().upper())
    def test_exact_inspect_revision_guard(self):
        s=self.scan();g=self.graph();e=self.nodes(g,'service')[0]['evidence'][0]
        detail=self.core.call('inspect',{'id':e['section_id'],'at_packet':e['at_packet'],'analysis_revision':e['analysis_revision']})
        self.assertEqual(detail['analysis_revision'],s['revision'])
        with self.assertRaises(RuntimeError):self.core.call('inspect',{'id':e['section_id'],'analysis_revision':s['revision']+1})
    def test_more_than_2500_programs_paginate_without_silent_loss(self):
        total=2501;sections=[]
        chunks=[tuple((i,0x100) for i in range(start,min(start+200,total+1))) for start in range(1,total+1,200)]
        for index,programs in enumerate(chunks):sections.append(pat(programs=programs,number=index,last=len(chunks)-1))
        self.scan(sections);offset=0;ids=[]
        while True:
            g=self.graph(offset=offset);self.assertEqual(g['counts']['nodes'],total+1);self.assertLessEqual(len(g['nodes']),500)
            ids.extend(n['node_id'] for n in g['nodes'])
            if not g['page']['has_more']:break
            offset=g['page']['next_offset']
        self.assertEqual(len(ids),total+1);self.assertEqual(len(set(ids)),total+1)
    def test_graph_limit_fails_explicitly_instead_of_partial_success(self):
        total=20000;sections=[]
        chunks=[tuple((i,0x100) for i in range(start,min(start+200,total+1))) for start in range(1,total+1,200)]
        for index,programs in enumerate(chunks):sections.append(pat(programs=programs,number=index,last=len(chunks)-1))
        self.scan(sections)
        with self.assertRaisesRegex(RuntimeError,'Topology node limit exceeded'):
            self.graph(limit=1)
    def test_empty_name_has_identity_label_and_unrelated_incomplete_table_is_not_a_topology_failure(self):
        from make_fixture import section
        unrelated=versioned(section(0x80,8,1,b'private'),number=0,last=1)
        self.scan([pat(),pmt(),sdt(services=((100,''),)),nit(),(0x11,unrelated)])
        g=self.graph();n=self.nodes(g,'service')[0]
        self.assertEqual(n['label'],'Service 0x0064');self.assertEqual(n['attributes']['name'],'')
        self.assertEqual(g['status'],'ok');self.assertEqual(g['diagnostics'],[]);self.assert_evidence(g)
    def test_dvb_delivery_and_nominal_candidates_are_scoped_declarations(self):
        from test_satellite_metadata import satellite_descriptor
        self.scan([nit(transports=((2,1,satellite_descriptor()),(3,9,satellite_descriptor(position=1220))))])
        g=self.graph();delivery=self.nodes(g,'delivery_parameters');candidates=self.nodes(g,'satellite_candidate')
        self.assertEqual(len(delivery),2);self.assertEqual(len(candidates),3)
        self.assertEqual({n['attributes']['name'] for n in candidates},{'HOTBIRD 13F','HOTBIRD 13G','AsiaSat 9'})
        for n in delivery:
            self.assertEqual(n['attributes']['parameters']['frequency_hz'],11538000000)
            self.assertEqual(n['attributes']['parameters']['symbol_rate'],22000000)
            self.assertIsNone(n['attributes']['physical_transponder_id']);self.assertIsNone(n['attributes']['confirmed_satellite'])
            self.assertEqual(n['observation_status'],'announced_only');self.assertFalse(n['attributes']['reception_verified'])
        for n in candidates:
            self.assertIsNone(n['attributes']['assignment_valid_at_capture']);self.assertIsNone(n['attributes']['confirmed_satellite'])
            self.assertTrue(n['reference_sources'][0]['source']['url'].startswith('https://'))
        self.assertTrue(all(e['relation']=='candidate_association' and e['reference_sources'] for e in g['edges'] if ':satellite-candidate:' in e['to']))
        self.assertTrue(all(n['object_type'] not in ['transponder','satellite'] for n in g['nodes']));self.assert_evidence(g)
    def test_delivery_dvb_c_t_values_use_real_sdk_and_exact_loop(self):
        cable=descriptor(0x44,bytes.fromhex('04500000fff2050069000f'))
        terrestrial=descriptor(0x5a,bytes.fromhex('03dfd2401f8112ffffffff'))
        self.scan([nit(transports=((2,1,cable),(2,2,terrestrial)))])
        g=self.graph();delivery=self.nodes(g,'delivery_parameters');self.assertEqual(len(delivery),2)
        by_system={n['attributes']['delivery_system']:n for n in delivery}
        self.assertEqual(by_system['DVB-C']['attributes']['parameters']['frequency_hz'],450000000)
        self.assertEqual(by_system['DVB-C']['attributes']['parameters']['symbol_rate'],6900000)
        self.assertEqual(by_system['DVB-T']['attributes']['parameters']['frequency_hz'],650000000)
        self.assertEqual(by_system['DVB-T']['attributes']['parameters']['bandwidth_hz'],8000000)
        self.assertFalse(self.nodes(g,'satellite_candidate'));self.assert_evidence(g)
    def test_delivery_unspecified_terrestrial_frequency_keeps_known_parameters(self):
        for frequency in ['ffffffff','00000000']:
            with self.subTest(frequency=frequency):
                terrestrial=descriptor(0x5a,bytes.fromhex(frequency+'1f8552ffffffff'))
                self.scan([nit(transports=((2,1,terrestrial),))]);g=self.graph();n=self.nodes(g,'delivery_parameters')[0]
                self.assertEqual(n['attributes']['parameter_status'],'partial');self.assertEqual(n['resolution_status'],'unresolved')
                p=n['attributes']['parameters'];self.assertIsNone(p['frequency_hz']);self.assertEqual(p['frequency_code'],int(frequency,16))
                self.assertEqual(p['bandwidth_hz'],8000000);self.assertEqual(p['constellation_code'],2);self.assertEqual(p['code_rate_hp_code'],5)
                self.assertTrue(n['unresolved_reasons']);self.assert_evidence(g)
    def test_delivery_cutoff_invalid_no_match_and_isdb_guard(self):
        from test_satellite_metadata import satellite_descriptor
        first=nit(transports=((2,1,satellite_descriptor()),),tid=0x41)
        second=nit(transports=((2,1,satellite_descriptor(position=123)),),tid=0x41,version=2)
        self.scan([first,second]);old=self.graph(at_packet=0);latest=self.graph()
        self.assertEqual(len(self.nodes(old,'satellite_candidate')),2);self.assertFalse(self.nodes(latest,'satellite_candidate'))
        self.assertEqual(self.nodes(latest,'delivery_parameters')[0]['attributes']['satellite_association_status'],'no_catalog_match');self.assert_evidence(old)
        self.scan([nit(transports=((2,1,satellite_descriptor(frequency='0A153800')),))]);g=self.graph()
        self.assertFalse(self.nodes(g,'satellite_candidate'));n=self.nodes(g,'delivery_parameters')[0]
        self.assertEqual(n['resolution_status'],'unresolved');self.assertEqual(n['attributes']['parameters'],{});self.assert_evidence(g)
        self.scan([first],profile='isdb-japan');self.assertFalse(self.nodes(self.graph(),'delivery_parameters'));self.assertFalse(self.nodes(self.graph(),'satellite_candidate'))
    def test_delivery_private_display_name_and_catalog_failure_do_not_confirm(self):
        from test_satellite_metadata import satellite_descriptor
        import shutil
        from unittest.mock import patch
        extension={'id':'fake-delivery','descriptors':[{'tag':128,'pds':0,'table_ids':[64],'name':'satellite_delivery_system_descriptor','payload_bytes':11,'fields':[]}]}
        path=Path(self.tmp.name)/'extension.json';path.write_text(json.dumps(extension));self.core.call('load_extension',{'path':str(path)})
        self.scan([nit(transports=((2,1,descriptor(0x80,satellite_descriptor()[2:])),))]);self.assertFalse(self.nodes(self.graph(),'delivery_parameters'))
        root=Path(self.tmp.name)/'missing-catalog';(root/'api').mkdir(parents=True);shutil.copy(ROOT/'api/tools.json',root/'api/tools.json')
        with patch('core_client.ROOT',root):other=Core()
        try:
            path=write_ts(Path(self.tmp.name)/'catalog.ts',[nit(transports=((2,1,satellite_descriptor()),))])
            other.call('analyze',{'path':str(path),'standards':'dvb'});g=other.call('query_topology',{'limit':500})
            self.assertFalse(self.nodes(g,'satellite_candidate'));d=self.nodes(g,'delivery_parameters')[0]
            self.assertEqual(d['attributes']['satellite_association_status'],'catalog_unavailable')
            self.assertEqual(d['attributes']['parameters']['frequency_hz'],11538000000)
        finally:other.close()
    def test_mcp_discovery_and_real_topology_call(self):
        path=write_ts(Path(self.tmp.name)/'mcp.ts',parts())
        p=subprocess.Popen([sys.executable,str(ROOT/'scripts/mcp_server.py')],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf-8')
        def call(i,method,params):
            p.stdin.write(json.dumps({'jsonrpc':'2.0','id':i,'method':method,'params':params})+'\n');p.stdin.flush()
            while True:
                message=json.loads(p.stdout.readline())
                if message.get('id')==i:return message
        try:
            call(1,'initialize',{'protocolVersion':'2024-11-05','capabilities':{},'clientInfo':{'name':'topology-test','version':'1'}})
            result=call(2,'tools/list',{})['result'];tool=next(t for t in result['tools'] if t['name']=='query_topology');self.assertTrue(tool['annotations']['readOnlyHint'])
            scan=call(3,'tools/call',{'name':'analyze','arguments':{'path':str(path),'standards':'dvb'}});self.assertNotIn('error',scan)
            result=call(4,'tools/call',{'name':'query_topology','arguments':{}})['result'];self.assertFalse(result.get('isError',False));g=json.loads(result['content'][0]['text']);self.assertTrue(g['nodes'])
        finally:
            p.stdin.close();p.wait(timeout=10);p.stdout.close();p.stderr.close()

if __name__=='__main__':unittest.main()
