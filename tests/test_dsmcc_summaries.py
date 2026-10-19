"""Exact-section DSM-CC source cards through the production core, no mocked parser."""
import hashlib
import json
from pathlib import Path
import sys
import unittest
import test_application_summaries as application_fixtures
packetize=application_fixtures.packetize
compatibility=application_fixtures.compatibility
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from make_fixture import section,word,crc


def dword(value):return value.to_bytes(4,'big')
def recalc(raw):
    raw=bytearray(raw);length=len(raw)-3;raw[1]=(raw[1]&0xf0)|(length>>8);raw[2]=length&255;raw[-4:]=crc(raw[:-4]).to_bytes(4,'big');return bytes(raw)
def message(tid,body,identifier=0x10203040,message_id=None,version=3,number=0,last=0,current=True,extension=7):
    if message_id is None:message_id=0x1003 if tid==0x3c else 0x1002
    payload=b'\x11\x03'+word(message_id)+dword(identifier)+b'\xff\0'+word(len(body))+body
    raw=bytearray(section(tid,extension,version,payload));raw[1]&=0xbf;raw[5]=(raw[5]&0xfe)|int(current);raw[6]=number;raw[7]=last;return recalc(raw)
def ddb(data=b'abcdef',download=0x10203040,module=7,module_version=3,block=0,**kwargs):
    return message(0x3c,word(module)+bytes([module_version,255])+word(block)+data,identifier=download,**kwargs)
def declaration(module=7,size=6,version=3,info=b'\0'*14):return word(module)+dword(size)+bytes([version,len(info)])+info
def dii(modules=None,download=0x10203040,block_size=4,compat=b'\0\0',transaction=0x80010002,**kwargs):
    if modules is None:modules=[declaration()]
    body=dword(download)+word(block_size)+b'\0'*10+compat+word(len(modules))+b''.join(modules)+b'\0\0'
    return message(0x3b,body,identifier=transaction,**kwargs)


class DsmccSummaryTests(unittest.TestCase):
    setUp=application_fixtures.ApplicationSummaryTests.setUp
    tearDown=application_fixtures.ApplicationSummaryTests.tearDown
    detail=application_fixtures.ApplicationSummaryTests.detail
    objects=application_fixtures.ApplicationSummaryTests.objects
    assert_evidence=application_fixtures.ApplicationSummaryTests.assert_evidence
    def scan(self,sections=None,standard='dvb'):
        sections=sections or [(0x150,ddb())];self.path=Path(self.tmp.name)/'carousel.ts';self.path.write_bytes(packetize(sections));self.before=hashlib.sha256(self.path.read_bytes()).hexdigest()
        self.state=self.core.call('analyze',{'path':str(self.path),'standards':standard,'extra_pids':sorted({pid for pid,_ in sections})});return self.state
    def test_pinned_sdk_compiler_vectors_have_stable_original_bytes(self):
        fixtures=json.loads((ROOT/'tests/fixtures/tsduck345/manifest.json').read_text())['fixtures']
        for name,kind in [('DSMCC_DII','download_information'),('DSMCC_DDB','download_data_block')]:
            fixture=fixtures[name];raw=bytes.fromhex(fixture['hex']);self.assertEqual(hashlib.sha256(raw).hexdigest(),fixture['sha256'])
            self.scan([(fixture['pid'],raw)]);d=self.detail();s=d['application_signalling'];node=self.objects(s,kind)[0]
            self.assertEqual(node['identity']['download_id'],0x10203040);self.assertEqual(bytes.fromhex(d['raw_hex']),raw);self.assert_evidence(s)
    def test_exact_high_number_ddb_preserves_independent_block_number(self):
        raw=ddb(data=b'x'*4064,number=226,last=255,block=482,version=17);self.scan([(0x150,raw)]);d=self.detail();s=d['application_signalling']
        self.assertFalse(d['native_table_complete']);node=self.objects(s,'download_data_block')[0]
        self.assertEqual(node['identity']['block_number'],482);self.assertEqual(node['identity']['section_version'],17);self.assertEqual(node['attributes']['section_number'],226);self.assertEqual(node['attributes']['data_length_bytes'],4064)
        self.assertIsNone(node['attributes']['assembled_sha256']);self.assertEqual(bytes.fromhex(d['raw_hex']),raw);self.assert_evidence(s)
    def test_dii_fields_duplicates_and_compatibility_remain_source_declarations(self):
        raw=dii([declaration(),declaration(size=9)],compat=compatibility(private=b'\x12\x34'))
        self.scan([(0x150,raw)]);d=self.detail();s=d['application_signalling'];root=self.objects(s,'download_information')[0];modules=self.objects(s,'download_module_announcement')
        self.assertEqual(root['identity']['transaction_id'],0x80010002);self.assertEqual(root['identity']['download_id'],0x10203040);self.assertIsNone(root['attributes']['device_match']);self.assertEqual(len(modules),2)
        self.assertEqual({m['attributes']['declared_size_bytes'] for m in modules},{6,9});self.assertTrue(all(m['resolution_status']=='conflict' for m in modules));self.assert_evidence(s)
    def test_protected_sdk_adapter_upgrade_contract_matches_native_complete_fields(self):
        self.scan([(0x150,dii()),(0x150,ddb(block=11,version=23,current=False))])
        for i in range(2):
            d=self.detail(i);s=d['application_signalling'];self.assertEqual(d['native_decode_status'],'native TSDuck decoder')
            self.assertTrue(s['objects']);self.assert_evidence(s)
        node=self.objects(self.detail(1)['application_signalling'],'download_data_block')[0]
        self.assertEqual(node['identity']['block_number'],11);self.assertEqual(node['identity']['section_version'],23);self.assertFalse(node['identity']['current'])
        self.assertIn('download_id="0x10203040"',self.detail(1)['tsduck_xml']);self.assertIn('version="23"',self.detail(1)['tsduck_xml'])
    def test_message_length_protocol_ids_reserved_and_adaptation_are_guarded(self):
        cases=[]
        for offset,value in [(8,0x10),(9,4),(11,4),(16,0),(17,1),(19,0)]:
            raw=bytearray(ddb());raw[offset]=value;cases.append(recalc(raw))
        for raw in cases:
            with self.subTest(raw=raw.hex()):
                self.scan([(0x150,raw)]);d=self.detail();self.assertFalse(d['application_signalling']['objects']);self.assertTrue(d['application_signalling']['diagnostics']);self.assertEqual(bytes.fromhex(d['raw_hex']),raw)
    def test_prefix_truncation_exercises_payload_checks_with_repaired_message_lengths(self):
        for original in [dii(),ddb()]:
            end_limit=len(original)-4 if original[0]==0x3b else 26
            for end in range(8,end_limit):
                raw=bytearray(original[:end]+b'\0'*4)
                if end>=20:raw[18:20]=word(end-20)
                raw=recalc(raw)
                with self.subTest(tid=original[0],end=end):
                    self.scan([(0x150,raw)]);d=self.detail();self.assertFalse(d['application_signalling']['objects']);self.assertEqual(bytes.fromhex(d['raw_hex']),raw)
        self.assertIn('native_registry',self.core.call('capabilities'))
    def test_dii_module_count_is_bounded_before_sdk_allocates_entries(self):
        self.scan([(0x150,dii([declaration(module=i,info=b'') for i in range(257)]))]);s=self.detail()['application_signalling'];self.assertEqual(s['status'],'resource_limit');self.assertFalse(s['objects'])
    def test_bad_compatibility_counts_and_unsupported_module_info_are_not_promoted(self):
        bad=bytearray(compatibility());bad[2:4]=word(2)
        for raw in [dii(compat=bytes(bad)),dii([declaration(info=b'\x80')])]:
            self.scan([(0x150,raw)]);s=self.detail()['application_signalling'];self.assertFalse(s['objects']);self.assertTrue(s['diagnostics'])
    def test_zero_block_size_never_acquires_a_default(self):
        self.scan([(0x150,dii(block_size=0))]);s=self.detail()['application_signalling'];m=self.objects(s,'download_module_announcement')[0];self.assertEqual(m['attributes']['block_size_bytes'],0);self.assertIn('zero',' '.join(m['unresolved_reasons']));self.assert_evidence(s)
    def test_crc_failure_and_non_dvb_profiles_have_no_semantic_cards(self):
        raw=bytearray(ddb());raw[-1]^=1;self.scan([(0x150,bytes(raw))]);self.assertEqual(self.detail()['application_signalling']['status'],'invalid')
        for profile in ['auto','atsc','isdb-japan']:
            self.scan(standard=profile);s=self.detail()['application_signalling'];self.assertEqual(s['status'],'unsupported_profile');self.assertFalse(s['objects'])
    def test_short_or_private_header_combinations_remain_explicitly_unsupported(self):
        for flags in [0x30,0x70,0xf0]:
            raw=bytearray(ddb());raw[1]=(raw[1]&15)|flags;raw=recalc(raw);self.scan([(0x150,raw)]);s=self.detail()['application_signalling'];self.assertFalse(s['objects']);self.assertIn(s['status'],['invalid','unsupported_framing'])

if __name__=='__main__':unittest.main()
