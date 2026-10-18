"""Wire-level metadata contracts through the real engine, without SDK compiler dependencies."""
import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from core_client import Core
from make_fixture import section,descriptor,word

def packets(pid,raw,cc=0):
    result=b'';first=True
    while raw:
        size=183 if first else 184
        payload=(b'\0' if first else b'')+raw[:size];raw=raw[size:]
        result+=bytes([0x47,(pid>>8)|(0x40 if first else 0),pid&255,0x10|cc])+payload+b'\xff'*(184-len(payload))
        cc=(cc+1)%16;first=False
    return result

def dvb(value): return b'\x15'+value.encode('utf-8')
def sized(value): return bytes([len(value)])+value
def short(language,title,text=b''):
    return descriptor(0x4d,language.encode('ascii')+sized(title)+sized(text))
def extended(language,number,last,text,items=b''):
    return descriptor(0x4e,bytes([(number<<4)|last])+language.encode('ascii')+sized(items)+sized(text))
def eit(descriptors,event_id=10,version=1):
    event=word(event_id)+bytes.fromhex('ef55090000010000')+word(0x8000|len(descriptors))+descriptors
    return section(0x4e,101,version,word(1)+word(1)+b'\x00\x4e'+event)
def metadata_fixture():
    desc=short('eng',dvb('News'),dvb('English summary'))+short('zho',dvb('新闻'),dvb('中文简介'))
    desc+=extended('eng',1,1,dvb('second'))+extended('eng',0,1,dvb('First '))
    desc+=extended('zho',0,1,dvb('缺少后半段'))
    service=descriptor(0x48,b'\x01'+sized(dvb('Provider'))+sized(dvb('Metadata TV')))
    sdt=section(0x42,1,1,word(1)+b'\xff'+word(101)+b'\xff'+word(0x8000|len(service))+service)
    return packets(0x11,sdt)+packets(0x12,eit(desc))

class SignalMetadataTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.core=Core();self.addCleanup(self.core.close)
    def analyze(self,raw,**kwargs):
        path=Path(self.tmp.name)/'input.ts';path.write_bytes(raw);self.before=hashlib.sha256(raw).hexdigest()
        state=self.core.call('analyze',{'path':str(path),'standards':'dvb',**kwargs})
        details=[self.core.call('inspect',{'id':r['id']}) for r in state['tables']]
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),self.before)
        return state,details
    def variants(self,desc):
        state,details=self.analyze(packets(0x12,eit(desc)))
        return {v['language_code']:v for v in details[0]['events'][0]['language_variants']}
    def test_lookup_names_ranges_context_and_unknowns(self):
        lookup=lambda kind,value,standard='dvb':self.core.call('lookup_identifier',{'namespace':kind,'value':value,'standards':standard})
        ca=lookup('ca_system_id',0x500)
        self.assertIn('Viaccess',ca['label']);self.assertEqual(ca['raw_hex'],'0x0500')
        self.assertEqual(ca['source']['file'],'tsduck.dtv.names');self.assertIn('not verified',ca['uncertainty'])
        self.assertEqual(lookup('ca_system_id',1,'auto')['status'],'context_required')
        self.assertNotEqual(lookup('ca_system_id',1)['label'],lookup('ca_system_id',1,'isdb-japan')['label'])
        self.assertIn('CUEI',lookup('registration_id',0x43554549,'auto')['label'])
        self.assertEqual(lookup('registration_id',0xffffffff)['status'],'unknown')
        with self.assertRaisesRegex(RuntimeError,'out of range'):lookup('network_id',65536)
        for invalid in [-1, 1.5, True, '0x500']:
            with self.subTest(invalid=invalid), self.assertRaises(RuntimeError):lookup('ca_system_id',invalid)
    def test_registered_descriptor_ids_have_wire_sources(self):
        registration=descriptor(0x05,b'CUEI')
        ca=descriptor(0x09,word(0x0500)+word(0xe100))
        pmt=section(0x02,101,1,word(0xe100)+word(0xf000|len(registration+ca))+registration+ca)
        _,details=self.analyze(packets(0x100,pmt),extra_pids=[0x100])
        ids={v['namespace']:v for v in details[0]['identifier_lookups']}
        self.assertEqual(ids['registration_id']['raw_hex'],'0x43554549')
        self.assertEqual(ids['ca_system_id']['label'],'Viaccess')
        self.assertIn('descriptors@',ids['ca_system_id']['field_path'])
        self.assertEqual(ids['ca_system_id']['wire_source']['section_id'],details[0]['id'])
    def test_wire_identifiers_sources_and_text_offsets(self):
        state,details=self.analyze(metadata_fixture())
        sdt=next(d for d in details if d['table_id']==0x42)
        lookup=sdt['identifier_lookups'][0]
        self.assertEqual(lookup['raw_value'],1);self.assertEqual(lookup['wire_source']['section_offset'],8)
        self.assertEqual(lookup['wire_source']['section_id'],sdt['id'])
        for t in sdt['text_diagnostics']:
            raw=bytes.fromhex(sdt['raw_hex']);offset=t['source']['section_offset']
            self.assertEqual(raw[offset:offset+t['available_bytes']].hex().upper(),t['raw_hex'])
            self.assertEqual(t['selector_hex'],'15');self.assertEqual(t['basis'],'wire_selector')
        self.assertEqual(sdt['text_diagnostics'][1]['decoded_text'],'Metadata TV')
    def test_language_preservation_order_and_missing_fragments(self):
        state,details=self.analyze(metadata_fixture())
        event=state['events'][0];v={x['language_code']:x for x in event['language_variants']}
        self.assertEqual(set(v),{'eng','zho'});self.assertEqual(v['zho']['title'],'新闻')
        self.assertEqual(v['eng']['extended_text'],'First second');self.assertEqual(event['title'],'News')
        self.assertEqual(v['zho']['extended_status'],'incomplete');self.assertEqual(v['zho']['missing_fragments'],[1])
        self.assertIsNone(v['zho']['extended_text'])
    def test_conflicts_are_not_silently_selected(self):
        v=self.variants(short('eng',dvb('A'))+short('eng',dvb('B'))+extended('eng',0,0,dvb('one'))+extended('eng',0,0,dvb('two')))['eng']
        self.assertEqual(v['short_status'],'conflict');self.assertEqual(v['title'],'')
        self.assertEqual(v['extended_status'],'conflict');self.assertIsNone(v['extended_text'])
        self.assertEqual(len(v['extended_fragments']),2)
    def test_duplicate_fragments_and_items_preserved(self):
        item=sized(dvb('Host'))+sized(dvb('Someone'))
        frag=extended('eng',0,0,dvb('Body'),item)
        v=self.variants(short('eng',b'Title')+frag+frag)['eng']
        self.assertEqual(v['extended_status'],'complete');self.assertEqual(v['extended_text'],'Body')
        self.assertEqual(v['duplicate_fragments'],[0]);self.assertEqual(v['items'],[{'description':'Host','value':'Someone'}])
    def test_inconsistent_numbering_and_invalid_fragment(self):
        v=self.variants(extended('eng',0,1,b'A')+extended('eng',1,2,b'B'))['eng']
        self.assertEqual(v['extended_status'],'conflict')
        invalid=descriptor(0x4e,b'\x00eng\x00\x05ab')
        v=self.variants(invalid)['eng']
        self.assertEqual(v['extended_status'],'invalid');self.assertIsNone(v['extended_text'])
        self.assertEqual(v['extended_fragments'][0]['text_diagnostics'][0]['status'],'truncated')
    def test_charset_override_and_explicit_selector_precedence(self):
        raw=packets(0x12,eit(short('fra',b'\xe9')+short('zho',dvb('中文'))))
        state,details=self.analyze(raw,default_charset='ISO-8859-1')
        v={x['language_code']:x for x in state['events'][0]['language_variants']}
        self.assertEqual(v['fra']['title'],'é');self.assertEqual(v['zho']['title'],'中文')
        diagnostics=details[0]['text_diagnostics']
        self.assertEqual(diagnostics[0]['basis'],'default_charset');self.assertEqual(diagnostics[2]['basis'],'wire_selector')
        with self.assertRaisesRegex(RuntimeError,'Unsupported default_charset'):self.analyze(raw,default_charset='invented')
    def test_invalid_selectors_preserve_wire_bytes(self):
        for title in [b'\x10',b'\x1f',b'\x08abc']:
            with self.subTest(title=title):
                _,details=self.analyze(packets(0x12,eit(short('eng',title))))
                t=details[0]['text_diagnostics'][0]
                self.assertEqual(t['raw_hex'],title.hex().upper());self.assertEqual(t['status'],'unsupported_or_invalid_selector')
    def test_event_and_history_boundaries(self):
        first=eit(short('eng',b'Old')+extended('eng',0,1,b'first'),version=1)
        later=eit(short('eng',b'New')+extended('eng',1,1,b'last'),version=2)
        state,details=self.analyze(packets(0x12,first)+packets(0x12,later,1))
        self.assertEqual(state['events'][0]['title'],'New')
        self.assertEqual(state['events'][0]['language_variants'][0]['extended_status'],'incomplete')
        old=self.core.call('query',{'at_packet':0})['events'][0]
        self.assertEqual(old['title'],'Old');self.assertEqual(old['language_variants'][0]['missing_fragments'],[1])
        diff=self.core.call('diff_snapshots',{'from_packet':0,'to_packet':1,'kind':'events'})
        self.assertEqual(diff['total_changes'],1)
    def test_raw_profile_does_not_invent_dvb_selector(self):
        _,details=self.analyze(packets(0x12,eit(short('eng',b'\x15Hello'))),default_charset='RAW-UTF-8')
        t=details[0]['text_diagnostics'][0]
        self.assertEqual(t['basis'],'configured_charset');self.assertEqual(t['selector_hex'],'')
    def test_same_section_events_do_not_share_fragments(self):
        a=eit(short('eng',b'A')+extended('eng',0,1,b'first'),event_id=1)
        b=eit(short('eng',b'B')+extended('eng',1,1,b'last'),event_id=2)
        combined=section(0x4e,101,1,a[8:14]+a[14:-4]+b[14:-4])
        state,_=self.analyze(packets(0x12,combined))
        self.assertEqual(len(state['events']),2)
        for event in state['events']:
            self.assertEqual(event['language_variants'][0]['extended_status'],'incomplete')
            self.assertIsNone(event['language_variants'][0]['extended_text'])
    def test_provenance_changes_do_not_change_event_content(self):
        desc=short('eng',b'Unchanged')+extended('eng',0,0,b'Body')
        first,later=eit(desc,version=1),eit(desc,version=2)
        self.analyze(packets(0x12,first)+packets(0x12,later,1))
        diff=self.core.call('diff_snapshots',{'from_packet':0,'to_packet':1,'kind':'events'})
        self.assertEqual(diff['total_changes'],0)
    def test_private_display_name_does_not_claim_standard_text(self):
        payload=b'eng'+sized(b'Not an event')+sized(b'')
        extension={'id':'test.private','descriptors':[{'tag':0xe1,'pds':0,'table_ids':[0x4e],
            'payload_bytes':len(payload),'name':'short_event_descriptor','fields':[]}]}
        path=Path(self.tmp.name)/'extension.json';path.write_text(__import__('json').dumps(extension))
        self.core.call('load_extension',{'path':str(path)})
        state,details=self.analyze(packets(0x12,eit(descriptor(0xe1,payload))))
        self.assertEqual(state['events'][0]['language_variants'],[])
        self.assertEqual(details[0]['text_diagnostics'],[])

if __name__=='__main__':unittest.main()
