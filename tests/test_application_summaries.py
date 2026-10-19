"""Actual-core AIT summary objects, scoped relations and original-byte anchors."""
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from core_client import Core
from make_fixture import crc,descriptor,section,word


def application(identifier=7,organization=0x10203040,control=1,descriptors=None,labels=(2,)):
    if descriptors is None:descriptors=properties(labels)+http(2)+descriptor(0x15,b'index.html')
    return organization.to_bytes(4,'big')+word(identifier)+bytes([control])+word(0xf000|len(descriptors))+descriptors

def properties(labels=(2,)):
    return descriptor(0,b'\0\xff\x05'+bytes(labels))

def http(label=2,base=b'https://example.invalid/app/'):
    return descriptor(2,word(3)+bytes([label,len(base)])+base+b'\0')

def ait(applications=None,common=b'',version=1,number=0,last=0,current=True):
    if applications is None:applications=[application()]
    apps=b''.join(applications)
    raw=bytearray(section(0x74,0x10,version,word(0xf000|len(common))+common+word(0xf000|len(apps))+apps))
    raw[5]=(raw[5]&0xfe)|int(current);raw[6]=number;raw[7]=last;raw[-4:]=crc(raw[:-4]).to_bytes(4,'big');return bytes(raw)

def packetize(sections):
    counters={};packets=[]
    for pid,data in sections:
        first=True
        while data:
            count=183 if first else 184;payload=(b'\0' if first else b'')+data[:count];data=data[count:]
            cc=counters.get(pid,0);counters[pid]=(cc+1)&15
            packets.append(bytes([0x47,(pid>>8)|(0x40 if first else 0),pid&255,0x10|cc])+payload+b'\xff'*(184-len(payload)));first=False
    return b''.join(packets)


class ApplicationSummaryTests(unittest.TestCase):
    def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.core=Core()
    def tearDown(self):self.core.close();self.tmp.cleanup()
    def scan(self,sections=None,standard='dvb'):
        self.path=Path(self.tmp.name)/'applications.ts';self.path.write_bytes(packetize(sections or [(0x150,ait())]));self.before=hashlib.sha256(self.path.read_bytes()).hexdigest()
        self.state=self.core.call('analyze',{'path':str(self.path),'standards':standard,'extra_pids':[0x150]});return self.state
    def detail(self,index=-1,**kwargs):return self.core.call('inspect',{'id':self.state['tables'][index]['id'],**kwargs})
    def objects(self,summary,kind):return [x for x in summary['objects'] if x['object_type']==kind]
    def assert_evidence(self,summary):
        for item in summary['objects']+summary['relations']:
            self.assertTrue(item['evidence'])
            for evidence in item['evidence']:
                self.assertEqual(evidence['analysis_revision'],self.state['revision']);self.assertEqual(evidence['at_packet'],summary['at_packet'])
                detail=self.core.call('inspect',{'id':evidence['section_id'],'at_packet':evidence['at_packet']});locator=evidence['locator'];span=locator['byte_range']
                self.assertTrue(any(a['field_id']==locator['field_id'] and a['container_id']==locator['container_id'] and a['byte_range']==span for a in detail['evidence_anchors']))
                self.assertEqual(span['offset_scope'],'section_bytes');self.assertLessEqual(span['offset']+span['length'],len(detail['raw_hex'])//2)
        self.assertEqual(hashlib.sha256(self.path.read_bytes()).hexdigest(),self.before)
    def test_pinned_http_ait_has_source_cards_without_execution(self):
        self.scan([(0x150,(ROOT/'tests/fixtures/application-signalling/ait-http.bin').read_bytes())]);d=self.detail();s=d['application_signalling'];self.assertEqual(s['status'],'ok')
        app=self.objects(s,'application')[0];self.assertEqual(app['identity']['organization_id'],0x10203040);self.assertEqual(app['identity']['application_id'],7);self.assertEqual(app['attributes']['control_code'],1)
        t=self.objects(s,'application_transport')[0];self.assertEqual(t['attributes']['http_locations'][0]['extensions'],['regional/']);self.assertEqual(t['attributes']['fetch_status'],'not_requested')
        location=self.objects(s,'application_location')[0];self.assertEqual(location['attributes']['initial_path'],'index.html');self.assertIsNone(location['attributes']['resolved_url']);self.assert_evidence(s)
    def test_common_and_local_duplicate_labels_preserve_all_candidates(self):
        a=application(7,descriptors=properties()+http(2,b'https://example.invalid/local/'))
        b=application(8,descriptors=properties())
        self.scan([(0x150,ait([a,b],common=http()))]);s=self.detail()['application_signalling'];apps={x['identity']['application_id']:x for x in self.objects(s,'application')}
        maps=[e for e in s['relations'] if e['relation']=='maps_to'];self.assertEqual(len(maps),3)
        self.assertEqual(apps[7]['resolution_status'],'conflict');self.assertEqual(apps[8]['resolution_status'],'resolved')
        self.assertEqual(len([e for e in maps if e['from']==apps[7]['node_id'] and e['resolution_status']=='conflict']),2);self.assert_evidence(s)
    def test_local_transport_cannot_leak_to_another_application(self):
        self.scan([(0x150,ait([application(7),application(8,descriptors=properties())]))]);s=self.detail()['application_signalling'];missing=self.objects(s,'application_transport_reference');self.assertEqual(len(missing),1)
        app=next(x for x in self.objects(s,'application') if x['identity']['application_id']==8);self.assertEqual(missing[0]['parent_id'],app['node_id']);self.assert_evidence(s)
    def test_common_transport_in_another_section_is_subtable_scoped(self):
        self.scan([(0x150,ait([],common=http(),number=0,last=1)),(0x150,ait([application(descriptors=properties())],number=1,last=1))]);s=self.detail()['application_signalling'];self.assertEqual(s['status'],'ok')
        edge=next(e for e in s['relations'] if e['relation']=='maps_to');self.assertEqual(len({e['section_id'] for e in edge['evidence']}),2);self.assert_evidence(s)
        early=self.detail(index=0,at_packet=0)['application_signalling'];self.assertEqual(early['status'],'incomplete_or_superseded');self.assertFalse(early['objects'])
    def test_duplicate_application_ids_are_not_overwritten(self):
        self.scan([(0x150,ait([application(control=1),application(control=2)]))]);s=self.detail()['application_signalling'];apps=self.objects(s,'application');self.assertEqual(len(apps),2)
        self.assertEqual({x['attributes']['control_code'] for x in apps},{1,2});self.assertTrue(all(x['resolution_status']=='conflict' for x in apps));self.assert_evidence(s)
    def test_versions_cutoffs_next_and_superseded_do_not_mix(self):
        self.scan([(0x150,ait([application(control=1)],version=31)),(0x150,ait([application(control=2)],version=0)),(0x150,ait([application(control=3)],version=1,current=False))]);first=next(i for i,t in enumerate(self.state['tables']) if t['version']==31);latest=next(i for i,t in enumerate(self.state['tables']) if t['version']==0)
        old=self.detail(first,at_packet=0)['application_signalling'];self.assertEqual(self.objects(old,'application')[0]['attributes']['control_code'],1)
        now=self.detail(latest)['application_signalling'];self.assertEqual(self.objects(now,'application')[0]['attributes']['control_code'],2)
        stale=self.detail(first,at_packet=self.state['packets']-1)['application_signalling'];self.assertEqual(stale['status'],'incomplete_or_superseded');self.assertFalse(stale['objects']);self.assert_evidence(old);self.assert_evidence(now)
    def test_object_carousel_declaration_does_not_claim_a_module_join(self):
        carousel=descriptor(2,word(1)+b'\x02\x7f\x33')
        self.scan([(0x150,ait([application(descriptors=properties()+carousel)]))]);s=self.detail()['application_signalling']
        transport=self.objects(s,'application_transport')[0]['attributes']['object_carousel']
        self.assertEqual(transport['component_tag'],0x33);self.assertEqual(transport['module_reconstruction'],'unsupported');self.assertIsNone(transport['original_network_id']);self.assert_evidence(s)
    def test_unknown_protocol_and_private_descriptor_stay_opaque(self):
        payload=properties()+descriptor(2,word(0x1234)+b'\x02\x01\x02\x03')+descriptor(0x80,b'\0\x03\x02')
        self.scan([(0x150,ait([application(descriptors=payload)]))]);s=self.detail()['application_signalling'];t=self.objects(s,'application_transport')[0]
        self.assertEqual(t['attributes']['selector_hex'],'010203');self.assertEqual(t['resolution_status'],'unresolved');self.assertNotIn('http_locations',t['attributes']);self.assert_evidence(s)
    def test_malformed_descriptor_is_raw_and_does_not_resolve_label(self):
        self.scan([(0x150,ait([application(descriptors=properties()+descriptor(2,b'\0'))]))]);s=self.detail()['application_signalling'];self.assertEqual(s['status'],'incomplete');self.assertTrue(self.objects(s,'application_transport_reference'));self.assert_evidence(s)
    def test_empty_transport_labels_do_not_claim_resolved_delivery(self):
        self.scan([(0x150,ait([application(descriptors=properties(labels=()))]))]);s=self.detail()['application_signalling'];app=self.objects(s,'application')[0]
        self.assertEqual(app['resolution_status'],'unresolved');self.assertFalse([e for e in s['relations'] if e['relation']=='maps_to']);self.assert_evidence(s)
    def test_explicit_profile_guard(self):
        for profile in ['auto','atsc','isdb-japan']:
            with self.subTest(profile=profile):
                self.scan(standard=profile);s=self.detail()['application_signalling'];self.assertEqual(s['status'],'unsupported_profile');self.assertFalse(s['objects'])
    def test_bad_crc_and_truncation_never_generate_semantic_objects(self):
        raw=bytearray(ait());raw[-1]^=1;self.scan([(0x150,bytes(raw))]);s=self.detail()['application_signalling'];self.assertEqual(s['status'],'invalid');self.assertFalse(s['objects'])
        raw=bytearray(ait()[:12]+b'\0'*4);raw[1]=(raw[1]&0xf0)|((len(raw)-3)>>8);raw[2]=(len(raw)-3)&255;raw[-4:]=crc(raw[:-4]).to_bytes(4,'big');self.scan([(0x150,bytes(raw))]);self.assertFalse(self.detail()['application_signalling']['objects'])
    def test_object_limit_is_explicit_and_preserves_raw_inspection(self):
        common=descriptor(0x80,b'')*240;sections=[(0x150,ait([],common=common,number=i,last=19)) for i in range(20)];self.scan(sections);d=self.detail();s=d['application_signalling']
        self.assertEqual(s['status'],'unresolved');self.assertFalse(s['objects']);self.assertIn('limit',s['diagnostics'][0]);self.assertEqual(bytes.fromhex(d['raw_hex']),sections[-1][1]);self.assertIn('native_registry',self.core.call('capabilities'))



def compatibility(model=0x1234,version=5,oui=0x1122,private=None):
    sub=b'' if private is None else descriptor(0xfe,private)
    entry=bytes([1,9+len(sub),1])+oui.to_bytes(3,'big')+word(model)+word(version)+bytes([bool(sub)])+sub
    return word(len(entry)+2)+word(1)+entry

def platform(target=b'',operational=b''):
    return word(0xf000|len(target))+target+word(0xf000|len(operational))+operational

def devices(platforms=None,compat=None):
    data=b''.join(platforms if platforms is not None else [platform(operational=descriptor(0x0d,b'\x0a\x14https://example.invalid/update.bin'))])
    return (compat if compat is not None else compatibility())+word(len(data))+data

def unt(groups=None,common=b'',oui=0x1122,action=1,version=3,number=0,last=0,processing=0,current=True):
    payload=oui.to_bytes(3,'big')+bytes([processing])+word(0xf000|len(common))+common+b''.join(groups if groups is not None else [devices()])
    raw=bytearray(section(0x4b,(action<<8)|((oui>>16)^((oui>>8)&255)^(oui&255)),version,payload));raw[5]=(raw[5]&0xfe)|int(current);raw[6]=number;raw[7]=last;raw[-4:]=crc(raw[:-4]).to_bytes(4,'big');return bytes(raw)


class UpdateSummaryTests(unittest.TestCase):
    setUp=ApplicationSummaryTests.setUp
    tearDown=ApplicationSummaryTests.tearDown
    scan=ApplicationSummaryTests.scan
    detail=ApplicationSummaryTests.detail
    objects=ApplicationSummaryTests.objects
    assert_evidence=ApplicationSummaryTests.assert_evidence
    def test_pinned_unt_preserves_both_conflicting_locations_without_selection(self):
        self.scan([(0x150,(ROOT/'tests/fixtures/application-signalling/unt.bin').read_bytes())]);s=self.detail()['application_signalling'];self.assertEqual(s['status'],'incomplete')
        context=self.objects(s,'update_notification')[0];self.assertEqual(context['identity']['oui'],0x1122);self.assertIsNone(context['attributes']['firmware_suitability'])
        transport=self.objects(s,'update_transport_reference')[0];self.assertEqual(transport['attributes']['association_tag'],0x1234);self.assertEqual(transport['attributes']['private_data_hex'],'010203');self.assertIsNone(transport['attributes']['component_pid'])
        uri=self.objects(s,'update_uri')[0];self.assertEqual(uri['attributes']['max_holdoff_minutes'],10);self.assertEqual(uri['attributes']['min_polling_interval_hours'],20);self.assertEqual(uri['attributes']['fetch_status'],'not_requested')
        target=self.objects(s,'update_target')[0];self.assertEqual(target['attributes']['location_resolution_status'],'conflict');self.assert_evidence(s)
    def test_device_model_version_and_opaque_subselectors_retained(self):
        self.scan([(0x150,unt([devices(compat=compatibility(private=b'\xca\xfe'))]))]);s=self.detail()['application_signalling'];c=self.objects(s,'update_device_compatibility')[0];selector=c['attributes']['selectors'][0]
        self.assertEqual((selector['specifier_data'],selector['model'],selector['version']),(0x1122,0x1234,5));self.assertEqual(selector['sub_descriptors'][0]['additional_information_hex'],'CAFE');self.assertIsNone(c['attributes']['device_match']);self.assertEqual(c['resolution_status'],'unresolved');self.assert_evidence(s)
    def test_operational_location_overrides_only_same_section_common(self):
        common=descriptor(0x0d,b'\x01\x02https://example.invalid/common')
        local=descriptor(0x0d,b'\x03\x04https://example.invalid/local')
        self.scan([(0x150,unt([devices([platform(operational=local),platform()])],common=common))]);s=self.detail()['application_signalling'];targets=self.objects(s,'update_target');self.assertEqual(len(targets),2)
        uri={x['node_id']:x['attributes']['uri'] for x in self.objects(s,'update_uri')};refs=[e for e in s['relations'] if e['relation']=='references']
        self.assertEqual({uri[e['to']] for e in refs},{'https://example.invalid/common','https://example.invalid/local'});self.assertEqual(len([e for e in s['relations'] if e['relation']=='overrides']),1);self.assert_evidence(s)
    def test_common_location_does_not_leak_across_sections(self):
        common=descriptor(0x0d,b'\x01\x02https://example.invalid/common')
        self.scan([(0x150,unt([],common=common,number=0,last=1)),(0x150,unt([devices([platform()])],number=1,last=1))]);s=self.detail()['application_signalling'];target=self.objects(s,'update_target')[0]
        self.assertEqual(target['attributes']['location_resolution_status'],'missing');self.assertFalse([e for e in s['relations'] if e['relation']=='references']);self.assert_evidence(s)
    def test_full_oui_hash_collision_prevents_mixed_device_summary(self):
        # 00:11:22 and 00:10:23 share the 8-bit hash but are different authorities.
        self.scan([(0x150,unt(number=0,last=1)),(0x150,unt(oui=0x1023,number=1,last=1))]);s=self.detail()['application_signalling'];self.assertFalse(s['objects']);self.assertIn('hash collision',s['diagnostics'][0])
    def test_invalid_oui_hash_and_unknown_action_have_raw_only_summary(self):
        raw=bytearray(unt());raw[4]^=1;raw[-4:]=crc(raw[:-4]).to_bytes(4,'big')
        for value,phrase in [(bytes(raw),'OUI hash'),(unt(action=0x80),'action type')]:
            with self.subTest(phrase=phrase):
                self.scan([(0x150,value)]);d=self.detail();s=d['application_signalling'];self.assertFalse(s['objects']);self.assertIn(phrase,s['diagnostics'][0]);self.assertEqual(bytes.fromhex(d['raw_hex']),value)
    def test_target_selectors_keep_masks_and_never_evaluate_device_match(self):
        target=descriptor(6,b'\x01\x02\x03\x04\xaa')+descriptor(8,b'\x12\x34')+descriptor(7,bytes.fromhex('ffffffffffff001122334455'))+descriptor(9,bytes.fromhex('ffffff00c0000201'))+descriptor(10,b'\xff'*16+bytes.fromhex('20010db8000000000000000000000001'))
        self.scan([(0x150,unt([devices([platform(target=target,operational=descriptor(0x0d,b'\0\0https://example.invalid/'))])]))]);s=self.detail()['application_signalling'];selectors=self.objects(s,'update_target_selector');self.assertEqual(len(selectors),5)
        self.assertTrue(all(x['attributes']['device_match'] is None for x in selectors));ip=next(x for x in selectors if x['attributes']['descriptor_tag']==9);self.assertEqual(ip['attributes']['matches'],['192.0.2.1']);self.assert_evidence(s)
    def test_wrong_loop_private_target_and_full_association_are_not_guessed(self):
        # A location tag in a target loop is wrong context; private data remains opaque.
        target=descriptor(3,word(10)+word(0x1234))+descriptor(0x80,b'\x01\x02')
        operational=descriptor(3,word(10)+word(0xab34))
        self.scan([(0x150,unt([devices([platform(target=target,operational=operational)])]))]);s=self.detail()['application_signalling'];transport=self.objects(s,'update_transport_reference');self.assertEqual(len(transport),1);self.assertEqual(transport[0]['attributes']['association_tag'],0xab34)
        unknown=self.objects(s,'update_descriptor_reference');self.assertEqual(len(unknown),2);self.assertTrue(all(x['resolution_status']=='unresolved' for x in unknown));self.assert_evidence(s)
    def test_unt_cutoff_and_ouispaces_do_not_borrow_old_groups(self):
        self.scan([(0x150,unt()),(0x150,unt(oui=0x445566,version=4)),(0x150,unt(version=4,number=0,last=1))]);d=self.detail(index=0,at_packet=0);s=d['application_signalling'];self.assertEqual(self.objects(s,'update_notification')[0]['identity']['oui'],0x1122)
        late=self.detail(index=0,at_packet=self.state['packets']-1)['application_signalling'];self.assertFalse(late['objects']);self.assertEqual(late['status'],'incomplete_or_superseded');self.assert_evidence(s)

    def test_subgroup_oui_is_independent_and_bad_schedule_is_explicit(self):
        import datetime
        def timestamp(day):
            mjd=(datetime.date(2026,10,day)-datetime.date(1858,11,17)).days
            return word(mjd)+b'\x09\0\0'
        subgroup=descriptor(0x0b,bytes.fromhex('aabbcc1234'))
        schedule=descriptor(1,timestamp(20)+timestamp(19)+b'\0\x01\x02\x03')
        advice=descriptor(2,b'\x47\xaa\xbb')
        self.scan([(0x150,unt([devices([platform(operational=subgroup+schedule+advice)])]))]);s=self.detail()['application_signalling']
        group=self.objects(s,'update_subgroup_reference')[0];self.assertEqual(group['attributes']['defining_oui'],0xaabbcc);self.assertEqual(group['attributes']['subgroup_id'],0x1234);self.assertIsNone(group['attributes']['carousel_group'])
        self.assertEqual(self.objects(s,'update_schedule')[0]['resolution_status'],'unresolved');self.assertFalse(self.objects(s,'update_advice')[0]['attributes']['action_taken']);self.assert_evidence(s)
    def test_malformed_operational_location_does_not_become_valid_override(self):
        common=descriptor(0x0d,b'\0\0https://example.invalid/common')
        bad=descriptor(0x0d,b'\0')
        self.scan([(0x150,unt([devices([platform(operational=bad)])],common=common))]);s=self.detail()['application_signalling'];p=self.objects(s,'update_target')[0]
        self.assertEqual(p['attributes']['location_resolution_status'],'unresolved');self.assertEqual(p['resolution_status'],'unresolved')
        overrides=[e for e in s['relations'] if e['relation']=='overrides'];self.assertEqual(len(overrides),1);self.assertEqual(overrides[0]['resolution_status'],'unresolved');self.assert_evidence(s)

    def test_compatibility_presence_is_required_per_subtable_not_per_section(self):
        self.scan([(0x150,unt([],number=0,last=1)),(0x150,unt([devices()],number=1,last=1))]);s=self.detail()['application_signalling']
        self.assertEqual(s['status'],'ok');self.assertEqual(len(self.objects(s,'update_notification')),2)
        self.assertEqual(len(self.objects(s,'update_device_compatibility')),1);self.assert_evidence(s)
    def test_all_empty_unt_subtable_retains_missing_compatibility_reason(self):
        self.scan([(0x150,unt([],number=0,last=1)),(0x150,unt([],number=1,last=1))]);s=self.detail()['application_signalling']
        self.assertEqual(s['status'],'incomplete');contexts=self.objects(s,'update_notification');self.assertEqual(len(contexts),2)
        self.assertTrue(all(any('selected UNT sub-table' in reason for reason in x['unresolved_reasons']) for x in contexts));self.assert_evidence(s)

    def test_compatibility_counts_cannot_silently_discard_or_invent_selectors(self):
        cases=[]
        for count in (0,2,65535):
            value=bytearray(compatibility());value[2:4]=word(count);cases.append(bytes(value))
        for count in (0,2,255):
            value=bytearray(compatibility(private=b'\xaa'));value[14]=count;cases.append(bytes(value))
        for value in cases:
            with self.subTest(raw=value.hex()):
                raw=unt([devices(compat=value)]);self.scan([(0x150,raw)]);d=self.detail();s=d['application_signalling']
                self.assertFalse(s['objects']);self.assertEqual(s['status'],'unresolved');self.assertIn('count',s['diagnostics'][0]);self.assertEqual(bytes.fromhex(d['raw_hex']),raw)

if __name__=='__main__':unittest.main()
