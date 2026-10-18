"""Satellite candidates from real wire sections and a source-attributed offline catalog."""
import json
import shutil
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path
from test_signal_metadata import packets, section, descriptor, word, Core, ROOT


def satellite_descriptor(position=130, east=True, frequency="01153800"):
    # DVB frequency in 10 kHz, orbital position in tenths, symbols in 100 sym/s.
    return descriptor(0x43, bytes.fromhex(frequency + f"{position:04d}" + ("86" if east else "06") + "02200003"))


def satellite_fixture(tid=0x40, desc=None):
    desc=satellite_descriptor() if desc is None else desc
    transport=word(10)+word(20)+word(0xf000|len(desc))+desc
    return packets(0x10,section(tid,1,1,word(0xf000)+word(0xf000|len(transport))+transport))


class SatelliteTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.core=Core()
        self.addCleanup(self.core.close)

    def lookup(self,position=13,direction='E',**kwargs):
        return self.core.call('lookup_satellite',dict(orbital_position_degrees=position,direction=direction,**kwargs))

    def inspect(self,raw):
        path=Path(self.tmp.name)/'satellite.ts';path.write_bytes(raw)
        state=self.core.call('analyze',{'path':str(path),'standards':'dvb'})
        detail=self.core.call('inspect',{'id':state['tables'][0]['id']})
        self.assertEqual(path.read_bytes(),raw)
        return detail

    def test_colocated_and_single_matches_are_never_confirmed(self):
        result=self.lookup()
        self.assertEqual({x['name'] for x in result['candidates']},{'HOTBIRD 13F','HOTBIRD 13G'})
        self.assertIsNone(result['confirmed_satellite'])
        for c in result['candidates']:
            self.assertEqual(c['status'],'candidate')
            self.assertIsNone(c['assignment_valid_at_capture'])
            self.assertTrue(c['source']['url'].startswith('https://www.eutelsat.com/'))
        single=self.lookup(122)
        self.assertEqual([c['name'] for c in single['candidates']],['AsiaSat 9'])
        self.assertIsNone(single['confirmed_satellite'])
        self.assertEqual(single['status'],'candidates')

    def test_east_west_no_match_missing_position_and_tolerance(self):
        self.assertEqual(self.lookup(5,'W')['candidates'][0]['name'],'EUTELSAT 5 WEST B')
        self.assertEqual(self.lookup(5,'E')['status'],'no_catalog_match')
        self.assertEqual(self.lookup(13.1)['status'],'no_catalog_match')
        self.assertEqual(len(self.lookup(13.1,tolerance_degrees=.1)['candidates']),2)
        self.assertEqual(self.lookup(13.11,tolerance_degrees=.1)['status'],'no_catalog_match')
        result=self.core.call('lookup_satellite',{'frequency_hz':11538000000})
        self.assertEqual(result['status'],'insufficient_parameters')
        self.assertEqual(result['candidates'],[])

    def test_other_parameters_preserved_but_never_reduce_candidates(self):
        result=self.lookup(frequency_hz=123,symbol_rate=456,polarization='right')
        self.assertEqual(len(result['candidates']),2)
        self.assertEqual(result['raw_parameters']['frequency_hz'],123)
        self.assertIn('frequency_hz',result['matching']['unchecked_parameters'])
        self.assertEqual(result['catalog']['entry_count'],22)
        self.assertTrue(result['catalog']['fingerprint'])

    def test_invalid_queries_rejected(self):
        for key,value in [('orbital_position_degrees',-1),('orbital_position_degrees',181),('orbital_position_degrees',True),('orbital_position_degrees','13'),('direction','east'),('tolerance_degrees',2),('frequency_hz',0),('symbol_rate',False),('polarization','X')]:
            with self.subTest(key=key,value=value),self.assertRaises(RuntimeError):
                self.core.call('lookup_satellite',{'orbital_position_degrees':13,'direction':'E',key:value})

    def test_exact_wire_values_sources_and_transport_scope(self):
        detail=self.inspect(satellite_fixture())
        x=detail['satellite_associations'][0]
        self.assertEqual(x['raw_parameters']['frequency_hz'],11538000000)
        self.assertEqual(x['raw_parameters']['symbol_rate'],22000000)
        self.assertEqual(x['raw_parameters']['modulation_system'],'DVB-S2')
        self.assertEqual(x['transport']['transport_stream_id'],10)
        self.assertEqual(x['transport']['original_network_id'],20)
        self.assertEqual(x['wire_source']['section_id'],detail['id'])
        offset=x['wire_source']['section_offset']
        self.assertEqual(bytes.fromhex(detail['raw_hex'])[offset:offset+13].hex().upper(),x['raw_descriptor_hex'])
        self.assertTrue(x['sdk_parameters'])
        self.assertEqual(len(x['candidates']),2)

    def test_nit_other_advertisement_is_not_received_satellite(self):
        x=self.inspect(satellite_fixture(0x41))['satellite_associations'][0]
        self.assertIn('not proof',x['observation_scope'])
        self.assertEqual(x['wire_source']['table_id'],0x41)
        self.assertIsNone(x['confirmed_satellite'])

    def test_isdb_layout_is_not_relabelled_as_dvb(self):
        path=Path(self.tmp.name)/'isdb.ts';path.write_bytes(satellite_fixture())
        state=self.core.call('analyze',{'path':str(path),'standards':'isdb-japan'})
        detail=self.core.call('inspect',{'id':state['tables'][0]['id']})
        x=detail['satellite_associations'][0]
        self.assertEqual(x['status'],'unsupported_delivery_system')
        self.assertEqual(x['sdk_parameters']['modulation_system'],'ISDB-S')
        self.assertEqual(x['candidates'],[])
        self.assertEqual(x['raw_parameters'],{})

    def test_invalid_bcd_and_position_never_yield_candidates(self):
        for desc in [satellite_descriptor(frequency='0A153800'),satellite_descriptor(position=1900)]:
            with self.subTest(desc=desc):
                detail=self.inspect(satellite_fixture(desc=desc))
                self.assertTrue(all(x['status']=='invalid_parameters' and not x['candidates'] for x in detail['satellite_associations']))
                self.assertIn(desc.hex().upper(),detail['raw_hex'])

    def test_no_inference_from_other_descriptor_tags(self):
        detail=self.inspect(satellite_fixture(desc=descriptor(0x79,b'\x00')+descriptor(0x80,b'\x01'*11)))
        self.assertEqual(detail['satellite_associations'],[])

    def test_transport_loops_and_historical_sections_remain_separate(self):
        def nit(version,positions):
            transports=b''.join(word(i+10)+word(20)+word(0xf00d)+satellite_descriptor(p) for i,p in enumerate(positions))
            return section(0x40,1,version,word(0xf000)+word(0xf000|len(transports))+transports)
        path=Path(self.tmp.name)/'history.ts'
        path.write_bytes(packets(0x10,nit(1,[130,1220]))+packets(0x10,nit(2,[192,1340]),1))
        state=self.core.call('analyze',{'path':str(path),'standards':'dvb'})
        older=next(t for t in state['tables'] if t['version']==1)
        detail=self.core.call('inspect',{'id':older['id'],'at_packet':older['first_packet']})
        a,b=detail['satellite_associations']
        self.assertEqual(a['transport']['transport_stream_id'],10)
        self.assertEqual(b['transport']['transport_stream_id'],11)
        self.assertEqual([c['name'] for c in b['candidates']],['AsiaSat 9'])
        self.assertEqual({c['name'] for c in a['candidates']},{'HOTBIRD 13F','HOTBIRD 13G'})

    def test_private_display_name_cannot_establish_satellite_syntax(self):
        extension={'id':'satellite-spoof','descriptors':[{'tag':128,'pds':0,'table_ids':[64],'name':'satellite_delivery_system_descriptor','payload_bytes':11,'fields':[]}]}
        path=Path(self.tmp.name)/'extension.json';path.write_text(json.dumps(extension))
        self.core.call('load_extension',{'path':str(path)})
        detail=self.inspect(satellite_fixture(desc=descriptor(0x80,satellite_descriptor()[2:])))
        self.assertEqual(detail['satellite_associations'],[])

    def test_optional_catalog_failure_preserves_wire_evidence(self):
        root=Path(self.tmp.name)/'root'
        (root/'api').mkdir(parents=True);(root/'references').mkdir()
        shutil.copy(ROOT/'api/tools.json',root/'api/tools.json')
        with patch('core_client.ROOT',root):core=Core()
        self.addCleanup(core.close)
        path=Path(self.tmp.name)/'input.ts';path.write_bytes(satellite_fixture())
        for data in [None,'{broken',json.dumps({'schema_version':1,'revision':'bad','entries':[{}]})]:
            if data is not None:(root/'references/satellites.json').write_text(data,encoding='utf-8')
            result=core.call('lookup_satellite',{'orbital_position_degrees':13,'direction':'E'})
            self.assertEqual(result['status'],'catalog_unavailable')
            state=core.call('analyze',{'path':str(path),'standards':'dvb'})
            detail=core.call('inspect',{'id':state['tables'][0]['id']})
            self.assertTrue(detail['raw_hex'])
            self.assertEqual(detail['satellite_associations'][0]['status'],'catalog_unavailable')
        shutil.copy(ROOT/'references/satellites.json',root/'references/satellites.json')
        result=core.call('lookup_satellite',{'orbital_position_degrees':13,'direction':'E'})
        self.assertEqual(result['status'],'candidates')
        catalog=json.loads((root/'references/satellites.json').read_text())
        catalog['entries'][0]['longitude_degrees_east']=180
        (root/'references/satellites.json').write_text(json.dumps(catalog))
        changed=core.call('lookup_satellite',{'orbital_position_degrees':180,'direction':'W'})
        self.assertNotEqual(changed['catalog']['fingerprint'],result['catalog']['fingerprint'])
        self.assertEqual(changed['candidates'][0]['orbital_delta_degrees'],0)
        catalog['entries'].append(catalog['entries'][0])
        (root/'references/satellites.json').write_text(json.dumps(catalog))
        self.assertEqual(core.call('lookup_satellite',{})['status'],'catalog_unavailable')

    def test_readonly_discovery_and_catalog_provenance(self):
        tool=next(t for t in self.core.call('capabilities',{})['tools'] if t['name']=='lookup_satellite')
        self.assertTrue(tool['annotations']['readOnlyHint'])
        catalog=json.loads((ROOT/'references/satellites.json').read_text(encoding='utf-8'))
        self.assertEqual(len({c['id'] for c in catalog['entries']}),len(catalog['entries']))
        for c in catalog['entries']:
            self.assertIsNone(c['source']['assignment_valid_from'])
            self.assertIsNone(c['source']['assignment_valid_until'])
            self.assertEqual(c['source']['reviewed_at'],'2026-10-18')
