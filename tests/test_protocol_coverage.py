"""Protocol fixtures compiled by official TSDuck tstabcomp, not RF samples.

Legacy vectors retain their 3.39-3956 bytes; added vectors use 3.45-4798.

Source XML and expected provenance are documented in docs/PROTOCOL_COVERAGE.md.
Tests exercise ShowPsiSi's actual JSON API rather than counting SDK classes.
"""
import sys
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from core_client import Core
from make_fixture import section, descriptor, word, crc

# Generated from the pinned SDK XML model using tstabcomp. CRC is part of bytes.
FIXTURES = {
    'DELIVERY_NIT': (0x10, '40f06f004dc10000f000f06200010002f014430b0115380001928e022000027905dffc002a0700020002f01c5a0b03dfd2401f8112ffffffff7f0d040300090394000c03f83c400000030002f00d440b04500000fff2050069000f00040002f00d430b01195400019281027500030fb4dffc'),
    'MGT': (0x1ffb, 'c7f0190000c100000000010000e123e000000000f000f0001ba35769'),
    'TVCT': (0x123, 'c8f02d0001c100000001004c00410042002d004800440000f01c010400000000000100650dc20065fc00fc0038fd04e2'),
    'STT': (0x1ffb, 'cdf0110000c1000000566d3e8012600070dc0b4b'),
    'BIT': (0x24, 'c4f00e0002c10000f00001f00026424aa9'),
    'CDT': (0x29, 'c8f0100003c10000000201f000cafeaa1c7356'),
    'SDTT': (0x23, 'c3f0100003c100000001000200650023cd1b06'),
    'LDT': (0x25, 'c7f0120065c10000000100020009fff000ffca0fda'),
    'NBIT': (0x25, 'c5f0090002c10000edda6ab4'),
    'ITT': (0x130, 'd2f00b0007c10000f00038f88823'),
}

# Reproduction sources for the additional pinned-compiler fixtures. Tests consume
# embedded binary sections so tstabcomp is not a test-time dependency.
SPECIAL_FIXTURE_XML = {
    'SCTE_SPLICE': '''<tsduck>
  <splice_information_table pts_adjustment="90">
    <time_signal pts_time="900000" />
    <splice_segmentation_descriptor segmentation_event_id="17" segmentation_duration="5400000" segmentation_type_id="0x30" segment_num="1" segments_expected="2">
      <segmentation_upid type="0x0F">4C41422D3137</segmentation_upid>
    </splice_segmentation_descriptor>
    <splice_avail_descriptor provider_avail_id="42" />
  </splice_information_table>
</tsduck>''',
    'DVB_AIT': '''<tsduck>
  <AIT application_type="0x0010" version="7" test_application_flag="false">
    <application control_code="1">
      <application_identifier organization_id="0x10203040" application_id="7" />
      <application_descriptor service_bound="true" visibility="3" application_priority="5">
        <profile application_profile="1" version="1.2.3" />
        <transport_protocol label="1" />
      </application_descriptor>
      <application_name_descriptor>
        <language code="eng" application_name="Lab Guide" />
      </application_name_descriptor>
      <transport_protocol_descriptor transport_protocol_label="1">
        <object_carousel component_tag="11" />
      </transport_protocol_descriptor>
    </application>
  </AIT>
</tsduck>''',
    'ATSC_SPECIAL_TVCT': '''<tsduck>
  <TVCT transport_stream_id="1">
    <channel short_name="LAB-HD" major_channel_number="7" minor_channel_number="1" modulation_mode="8-VSB" channel_TSID="1" program_number="101" source_id="101">
      <service_location_descriptor PCR_PID="0x201">
        <component stream_type="0x1b" elementary_PID="0x201" />
        <component stream_type="0x81" elementary_PID="0x202" ISO_639_language_code="eng" />
      </service_location_descriptor>
      <extended_channel_name_descriptor>
        <long_channel_name_text>
          <string language="eng" text="Laboratory HD" />
        </long_channel_name_text>
      </extended_channel_name_descriptor>
      <caption_service_descriptor>
        <service language="eng" digital_cc="true" caption_service_number="1" easy_reader="false" wide_aspect_ratio="true" />
      </caption_service_descriptor>
    </channel>
  </TVCT>
</tsduck>''',
    'ATSC_SPECIAL_EIT': '''<tsduck>
  <ATSC_EIT source_id="101" version="4">
    <event event_id="17" start_time="2026-10-16 12:00:00" ETM_location="0" length_in_seconds="3600">
      <title_text>
        <string language="eng" text="Science Lab" />
      </title_text>
      <content_advisory_descriptor>
        <region rating_region="1">
          <dimension rating_dimension_j="0" rating_value="3" />
          <rating_description>
            <string language="eng" text="PG" />
          </rating_description>
        </region>
      </content_advisory_descriptor>
      <caption_service_descriptor>
        <service language="spa" digital_cc="true" caption_service_number="2" easy_reader="true" wide_aspect_ratio="true" />
      </caption_service_descriptor>
    </event>
  </ATSC_EIT>
</tsduck>''',
    'ISDB_SPECIAL_NIT': '''<tsduck>
  <NIT network_id="2">
    <system_management_descriptor broadcasting_flag="3" broadcasting_identifier="3" additional_broadcasting_identification="1" />
    <transport_stream transport_stream_id="1" original_network_id="2">
      <ISDB_terrestrial_delivery_system_descriptor area_code="0x123" guard_interval="1/8" transmission_mode="mode3">
        <frequency value="473000000" />
      </ISDB_terrestrial_delivery_system_descriptor>
      <TS_information_descriptor remote_control_key_id="7" ts_name="ISDB Lab">
        <transmission_type transmission_type_info="15">
          <service id="101" />
        </transmission_type>
      </TS_information_descriptor>
      <partial_reception_descriptor>
        <service id="101" />
      </partial_reception_descriptor>
    </transport_stream>
  </NIT>
</tsduck>''',
    'DVB_SPECIAL_PMT': '''<tsduck>
  <PMT service_id="101" PCR_PID="0x201">
    <component elementary_PID="0x201" stream_type="0x24">
      <HEVC_video_descriptor profile_space="0" tier_flag="false" profile_idc="1" profile_compatibility_indication="0x60000000" progressive_source_flag="true" interlaced_source_flag="false" non_packed_constraint_flag="false" frame_only_constraint_flag="true" level_idc="120" HEVC_still_present_flag="false" HEVC_24hr_picture_present_flag="false" />
    </component>
    <component elementary_PID="0x202" stream_type="6">
      <DVB_AC4_descriptor ac4_dialog_enhancement_enabled="true" ac4_channel_mode="1" />
      <ISO_639_language_descriptor>
        <language code="eng" audio_type="0" />
      </ISO_639_language_descriptor>
    </component>
    <component elementary_PID="0x203" stream_type="6">
      <subtitling_descriptor>
        <subtitling language_code="eng" subtitling_type="0x10" composition_page_id="1" ancillary_page_id="2" />
      </subtitling_descriptor>
    </component>
    <component elementary_PID="0x150" stream_type="5">
      <application_signalling_descriptor>
        <application application_type="0x10" AIT_version_number="7" />
      </application_signalling_descriptor>
    </component>
  </PMT>
</tsduck>''',
}

FIXTURES.update({
    'SCTE_SPLICE': (0x152, 'fc303c00000000005a00fff00506fe000dbba00026021a43554549000000117fff00005265c00f064c41422d31373001020008435545490000002a5563e253'),
    'DVB_AIT': (0x150, '74f0370010cf0000f000f02a10203040000701f0210009050001010203ff0501010d656e67094c616220477569646502050001017f0bc4650ce1'),
    'ATSC_SPECIAL_TVCT': (0x1ffb, 'c8f05e0001c100000001004c00410042002d004800440000f01c010400000000000100650dc20065fc31a10fe201021be20100000081e202656e67a01501656e670100000d4c61626f7261746f72792048448607e1656e67c17ffffc009671314d'),
    'ATSC_SPECIAL_EIT': (0x151, 'cbf0450065c900000001c01157fcd440c00e101301656e670100000b536369656e6365204c6162f01b8710c1010100f30a01656e670100000250478607e1737061c2ffffab7d5a45'),
    'ISDB_SPECIAL_NIT': (0x10, '40f0310002c10000f004fe02c301f02000010002f01afa04123a0cefcd0e072149534442204c61620f010065fb0200658d629a9f'),
    'DVB_SPECIAL_PMT': (0x100, '02b04a0065c10000e201f00024e201f00f380d0160000000900000000000781f06e202f00b7f031580a00a04656e670006e203f00a5908656e67100001000205e150f0056f038010e78ba4a1a7'),
})

# Exact 3.45-4798 compiler inputs, options and immutable section bytes. Runtime
# tests do not require tstabcomp; reproduction instructions are beside the XML.
EXPANDED_FIXTURE_DIR = ROOT / 'tests' / 'fixtures' / 'tsduck345'
EXPANDED_MANIFEST = json.loads((EXPANDED_FIXTURE_DIR / 'manifest.json').read_text(encoding='utf-8'))
EXPANDED_FIXTURES = EXPANDED_MANIFEST['fixtures']
FIXTURES.update({name: (fixture['pid'], fixture['hex'])
                 for name, fixture in EXPANDED_FIXTURES.items()})

class ProtocolCoverageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='showpsi-protocol-')
        self.core = Core()
    def tearDown(self):
        self.core.close()
        self.tmp.cleanup()
    @staticmethod
    def packetize(pid, raw, cc=0):
        """Payload-only TS packets, including the first packet's pointer field."""
        packets = []
        first = True
        while raw:
            capacity = 183 if first else 184
            chunk, raw = raw[:capacity], raw[capacity:]
            payload = (b'\0' if first else b'') + chunk
            packets.append(bytes([0x47, (pid >> 8) | (0x40 if first else 0),
                                  pid & 255, 0x10 | cc]) + payload + b'\xff' * (184 - len(payload)))
            cc = (cc + 1) & 15
            first = False
        return packets

    @staticmethod
    def sdt_part(version, number, name, current=True, last=1):
        text = name.encode('ascii')
        desc = descriptor(0x48, b'\x01\x00' + bytes([len(text)]) + text)
        raw = bytearray(section(0x42, 1, version, word(2) + b'\xff' +
                               word(100 + number) + b'\xff' + word(0x8000 + len(desc)) + desc))
        raw[5] = (raw[5] & 0xfe) | int(current)
        raw[6], raw[7] = number, last
        raw[-4:] = crc(raw[:-4]).to_bytes(4, 'big')
        return bytes(raw)

    @staticmethod
    def tree_nodes(node, name):
        matches = [node] if node.get('name') == name else []
        for child in node.get('children', []):
            matches.extend(ProtocolCoverageTests.tree_nodes(child, name))
        return matches

    @staticmethod
    def number(value):
        return int(value.replace(',', ''), 0)

    def analyze_packets(self, packets, standard='dvb', extra_pids=None):
        path = Path(self.tmp.name) / 'protocol.ts'
        path.write_bytes(b''.join(packets))
        params = {'path': str(path), 'standards': standard}
        if extra_pids is not None:
            params['extra_pids'] = extra_pids
        result = self.core.call('analyze', params)
        self.assertEqual(result['crc_errors'], 0)
        details = [self.core.call('inspect', {'id': t['id']}) for t in result['tables']]
        return result, details

    def analyze(self, names, standard, extra_pids=None):
        packets, counters = [], {}
        for _ in range(3):
            for name in names:
                pid, raw = FIXTURES[name]
                emitted = self.packetize(pid, bytes.fromhex(raw), counters.get(pid, 0))
                counters[pid] = (counters.get(pid, 0) + len(emitted)) & 15
                packets.extend(emitted)
        return self.analyze_packets(packets, standard, extra_pids)

    def assert_native(self, details, name):
        matching = [d for d in details if d.get('native_table', {}).get('name') == name]
        self.assertTrue(matching, '%s missing: %s' % (name, [(d.get('table_id'), d.get('native_table')) for d in details]))
        self.assertTrue(matching[0]['native_table_complete'])
        self.assertIn('<' + name, matching[0]['tsduck_xml'])
        return matching[0]['native_table']
    def test_atsc_mgt_discovers_nonstandard_vct_pid(self):
        state, details = self.analyze(['MGT', 'TVCT', 'STT'], 'atsc')
        for name in ['MGT', 'TVCT', 'STT']:
            self.assert_native(details, name)
        self.assertTrue(any(t['pid'] == 0x123 for t in state['tables']))
        vct = self.assert_native(details, 'TVCT')
        channel = next(c for c in vct['children'] if c['name'] == 'channel')
        self.assertEqual(channel['attributes']['short_name'], 'LAB-HD')
    def test_isdb_reserved_pids_and_colliding_table_ids(self):
        _, details = self.analyze(['BIT', 'CDT', 'SDTT', 'LDT', 'NBIT'], 'isdb')
        for name in ['BIT', 'CDT', 'SDTT', 'LDT', 'NBIT']:
            self.assert_native(details, name)
        self.assertFalse(any(d.get('native_table', {}).get('name') in ('TVCT', 'MGT') for d in details))
    def test_user_specified_pid_is_generic_decoded(self):
        _, details = self.analyze(['ITT'], 'isdb', [0x130])
        self.assert_native(details, 'ITT')
    def test_registered_catalog_and_official_references(self):
        registry = self.core.call('capabilities')['native_registry']
        self.assertEqual(registry['table_count'], len(registry['table_names']))
        self.assertEqual(registry['descriptor_count'], len(registry['descriptor_names']))
        for name in ['MGT', 'TVCT', 'STT', 'BIT', 'CDT', 'SDTT']:
            self.assertIn(name, registry['table_names'])
        self.assertIn('satellite_delivery_system_descriptor', registry['descriptor_names'])
        _, details = self.analyze(['MGT', 'TVCT', 'STT'], 'atsc')
        for detail in details:
            refs = detail['references']
            self.assertTrue(refs)
            self.assertTrue(all(ref['url'].startswith('https://') for ref in refs))
            self.assertTrue(any('ATSC' in ref['title'] for ref in refs))
        _, details = self.analyze(['BIT', 'CDT'], 'isdb')
        bit = next(d for d in details if d['native_table']['name'] == 'BIT')
        cdt = next(d for d in details if d['native_table']['name'] == 'CDT')
        self.assertTrue(bit['references'])
        self.assertEqual(cdt['references'], [])  # STD-B21 must not be mislabeled B10.
    def test_private_pds_is_scoped_and_unknown_bytes_survive(self):
        from make_fixture import section, descriptor, word
        private = descriptor(0x83, word(101) + word(0xfc0a))
        pds = descriptor(0x5f, bytes.fromhex('00000028'))
        reg = descriptor(0x05, b'CUEI')
        unknown = descriptor(0xe2, bytes.fromhex('cafebabe'))
        def service(sid, descriptors):
            return word(sid) + b'\xff' + word(0x8000 + len(descriptors)) + descriptors
        raw = section(0x42, 1, 1, word(2) + b'\xff' + service(101, pds + reg + private + unknown) + service(102, private + unknown))
        packets = [bytes([0x47, 0x40, 0x11, 0x10 + cc, 0]) + raw + b'\xff' * (183-len(raw)) for cc in range(3)]
        path = Path(self.tmp.name) / 'private.ts'
        path.write_bytes(b''.join(packets))
        state = self.core.call('analyze', {'path': str(path), 'standards': 'dvb'})
        detail = self.core.call('inspect', {'id': state['tables'][0]['id']})
        channels = [d for d in detail['descriptors'] if d['tag'] == 0x83]
        self.assertEqual([d['pds'] for d in channels], [0x28, 0])
        self.assertEqual(channels[0]['native']['name'], 'eacem_logical_channel_number_descriptor')
        self.assertEqual(channels[1]['native']['name'], 'generic_descriptor')
        unknowns = [d for d in detail['descriptors'] if d['tag'] == 0xe2]
        self.assertEqual([d['raw'] for d in unknowns], ['E204CAFEBABE'] * 2)
        self.assertTrue(all(not d['native_decoded'] for d in unknowns))
        self.assertTrue(all(d.get('references') == [] for d in unknowns))
        # Reanalysis without a PDS must not inherit the previous file's namespace.
        raw = section(0x42, 1, 1, word(2) + b'\xff' + service(103, private))
        path.write_bytes(b''.join(bytes([0x47,0x40,0x11,0x10+cc,0])+raw+b'\xff'*(183-len(raw)) for cc in range(3)))
        state = self.core.call('analyze', {'path': str(path), 'standards': 'dvb'})
        detail = self.core.call('inspect', {'id': state['tables'][0]['id']})
        self.assertEqual(detail['descriptors'][0]['native']['name'], 'generic_descriptor')
    def test_auto_fixed_pid_evidence_and_wrong_context_fallback(self):
        for names in [['MGT', 'TVCT', 'STT'], ['BIT', 'CDT', 'LDT']]:
            _, details = self.analyze(names, 'auto')
            for name in names:
                self.assert_native(details, name)
        # TSDuck 3.39's first registered matching table wins when explicit ISDB
        # and detected ATSC evidence conflict. Windows and Linux registration
        # orders can produce the correct ATSC native table or a raw fallback.
        # Neither outcome may relabel these bytes as ISDB LDT/CDT.
        for standard in ['atsc', 'isdb']:
            _, details = self.analyze(['MGT', 'TVCT'], standard, [0x1ffb, 0x123])
            self.assertEqual(len(details), 2)
            for detail in details:
                with self.subTest(standard=standard, pid=detail['pid']):
                    expected = {0xc7: 'MGT', 0xc8: 'TVCT'}[detail['table_id']]
                    native = detail['native_table']
                    self.assertEqual(detail['standards_context'], standard)
                    self.assertEqual(detail['pid'], FIXTURES[expected][0])
                    self.assertEqual(detail['raw_hex'], FIXTURES[expected][1].upper())
                    self.assertTrue(detail['native_table_complete'])
                    self.assertIn(native['name'], (expected, 'generic_long_table'), repr(detail))
                    if native['name'] == 'generic_long_table':
                        self.assertEqual(standard, 'isdb', repr(detail))
                        self.assertEqual(detail['native_decode_status'], 'generic raw fallback')
                        payload = ''.join(native['children'][0]['text'].split())
                        self.assertEqual(payload, FIXTURES[expected][1][16:-8].upper())
                    else:
                        self.assertEqual(detail['native_decode_status'], 'native TSDuck decoder')
                        if expected == 'MGT':
                            entry = next(n for n in native['children'] if n['name'] == 'table')['attributes']
                            self.assertEqual(entry['type'], 'TVCT-current')
                            self.assertEqual(int(entry['pid'], 0), 0x123)
                            self.assertEqual(int(entry['version_number'], 0), 0)
                        else:
                            channel = next(n for n in native['children'] if n['name'] == 'channel')['attributes']
                            self.assertEqual(channel['short_name'], 'LAB-HD')
                            self.assertEqual(int(channel['major_channel_number'], 0), 7)
                            self.assertEqual(int(channel['minor_channel_number'], 0), 1)
                            self.assertEqual(int(channel['program_number'], 0), 101)
                            self.assertEqual(int(channel['source_id'], 0), 101)
                    # Reference policy uses the explicitly chosen family even if
                    # the SDK decoded a known table from another family.
                    if standard == 'isdb':
                        self.assertEqual(detail['references'], [])
                    else:
                        self.assertTrue(any(r['id'] == 'atsc-psip' for r in detail['references']))
    def test_dvb_s_s2_t_t2_c_delivery_fields_and_references(self):
        _, details = self.analyze(['DELIVERY_NIT'], 'dvb')
        nit = self.assert_native(details, 'NIT')
        transports = {int(n['attributes']['transport_stream_id'], 0): n['children'] for n in nit['children']}
        def descriptor(tsid, name):
            node = next(n for n in transports[tsid] if n['name'] == name)
            self.assertTrue(any(r['id'] == 'dvb-si' and r['url'].startswith('https://www.etsi.org/') for r in node['references']))
            return node
        def number(value):
            return int(value.replace(',', ''), 0)
        satellite = descriptor(1, 'satellite_delivery_system_descriptor')['attributes']
        self.assertEqual(number(satellite['frequency']), 11538000000)
        self.assertEqual(number(satellite['symbol_rate']), 22000000)
        self.assertEqual(satellite['modulation_system'], 'DVB-S2')
        self.assertEqual(satellite['modulation_type'], '8PSK')
        self.assertEqual(satellite['roll_off'], '0.25')
        s2 = descriptor(1, 'S2_satellite_delivery_system_descriptor')['attributes']
        self.assertEqual(number(s2['scrambling_sequence_index']), 42)
        self.assertEqual(number(s2['input_stream_identifier']), 7)
        terrestrial = descriptor(2, 'terrestrial_delivery_system_descriptor')['attributes']
        self.assertEqual(number(terrestrial['centre_frequency']), 650000000)
        self.assertEqual(terrestrial['bandwidth'], '8MHz')
        self.assertEqual(terrestrial['constellation'], '64-QAM')
        self.assertEqual(terrestrial['transmission_mode'], '8k')
        t2 = descriptor(2, 'T2_delivery_system_descriptor')
        self.assertEqual(number(t2['attributes']['plp_id']), 3)
        self.assertEqual(number(t2['attributes']['t2_system_id']), 9)
        extension = next(n for n in t2['children'] if n['name'] == 'extension')
        self.assertEqual(extension['attributes']['bandwidth'], '8MHz')
        self.assertEqual(extension['attributes']['transmission_mode'], '32k')
        self.assertEqual(extension['attributes']['guard_interval'], '1/128')
        frequency = extension['children'][0]['children'][0]['attributes']['value']
        self.assertEqual(number(frequency), 666000000)
        cable = descriptor(3, 'cable_delivery_system_descriptor')['attributes']
        self.assertEqual(number(cable['frequency']), 450000000)
        self.assertEqual(number(cable['symbol_rate']), 6900000)
        self.assertEqual(cable['modulation'], '256-QAM')
        dvbs = descriptor(4, 'satellite_delivery_system_descriptor')['attributes']
        self.assertEqual(number(dvbs['frequency']), 11954000000)
        self.assertEqual(number(dvbs['symbol_rate']), 27500000)
        self.assertEqual(dvbs['modulation_system'], 'DVB-S')
        self.assertEqual(dvbs['modulation_type'], 'QPSK')
        # Both the flattened descriptor list and native hierarchy retain semantic decoding.
        self.assertEqual(len(details[0]['descriptors']), 6)
        self.assertTrue(all(d['native_decoded'] and d['references'] for d in details[0]['descriptors']))
    def test_pat_program_zero_discovers_nondefault_nit_pid(self):
        from make_fixture import section, word
        pat = section(0, 1, 0, word(0) + word(0xe000 | 0x135))
        nit = bytes.fromhex(FIXTURES['DELIVERY_NIT'][1])
        packets = []
        for cc in range(3):
            for pid, raw in [(0, pat), (0x135, nit)]:
                packets.append(bytes([0x47, 0x40 | (pid >> 8), pid & 255, 0x10 | cc, 0]) + raw + b'\xff' * (183-len(raw)))
        path = Path(self.tmp.name) / 'network-discovery.ts'
        path.write_bytes(b''.join(packets))
        state = self.core.call('analyze', {'path': str(path), 'standards': 'dvb'})
        tables = [t for t in state['tables'] if t['pid'] == 0x135]
        self.assertEqual(len(tables), 1)
        detail = self.core.call('inspect', {'id': tables[0]['id']})
        self.assert_native([detail], 'NIT')
        self.assertEqual(state['crc_errors'], 0)
    def test_next_sections_remain_inspectable_without_becoming_current(self):
        parts = [self.sdt_part(1, 0, 'Current A'), self.sdt_part(1, 1, 'Current B'),
                 self.sdt_part(1, 0, 'Next A', current=False),
                 self.sdt_part(1, 1, 'Next B', current=False)]
        packets = [self.packetize(0x11, raw, cc)[0] for cc, raw in enumerate(parts)]
        state, details = self.analyze_packets(packets)
        self.assertEqual([s['name'] for s in state['services']], ['Current A', 'Current B'])
        self.assertEqual(len(details), 4)
        for detail in details:
            at = 3 if not detail['current'] else 1
            inspected = self.core.call('inspect', {'id': detail['id'], 'at_packet': at})
            self.assertTrue(inspected['native_table_complete'])
            names = [n['attributes']['service_name'] for n in
                     self.tree_nodes(inspected['native_table'], 'service_descriptor')]
            self.assertEqual(names, ['Current A', 'Current B'] if detail['current'] else ['Next A', 'Next B'])
        output = Path(self.tmp.name) / 'current.bin'
        self.core.call('export', {'path': str(output), 'format': 'bin'})
        self.assertEqual(output.read_bytes(), parts[0] + parts[1])
        self.assertEqual(len(state['history']), 2)

    def test_reused_version_inspection_does_not_resurrect_previous_cycle(self):
        # A repeated 5-bit version after an intervening version is a new observed
        # generation. Old same-number siblings cannot complete its partial table.
        parts = [self.sdt_part(0, 0, 'Cycle one A'), self.sdt_part(0, 1, 'Cycle one B'),
                 self.sdt_part(31, 0, 'Version31 A'), self.sdt_part(31, 1, 'Version31 B'),
                 self.sdt_part(0, 0, 'Cycle two A'), self.sdt_part(0, 1, 'Cycle two B')]
        packets = [self.packetize(0x11, raw, cc)[0] for cc, raw in enumerate(parts)]
        state, _ = self.analyze_packets(packets)
        first = next(t['id'] for t in state['tables'] if t['first_packet'] == 4)
        partial = self.core.call('query', {'at_packet': 4})
        self.assertEqual(partial['services'], [])
        inspected = self.core.call('inspect', {'id': first, 'at_packet': 4})
        self.assertFalse(inspected['native_table_complete'])
        self.assertNotIn('native_table', inspected)
        complete = self.core.call('inspect', {'id': first, 'at_packet': 5})
        self.assertTrue(complete['native_table_complete'])
        self.assertEqual([n['attributes']['service_name'] for n in
                          self.tree_nodes(complete['native_table'], 'service_descriptor')],
                         ['Cycle two A', 'Cycle two B'])
        original = next(t['id'] for t in state['tables'] if t['first_packet'] == 0)
        old = self.core.call('inspect', {'id': original, 'at_packet': 1})
        self.assertEqual([n['attributes']['service_name'] for n in
                          self.tree_nodes(old['native_table'], 'service_descriptor')],
                         ['Cycle one A', 'Cycle one B'])

    def test_reused_identical_section_keeps_occurrence_generation_boundary(self):
        same = self.sdt_part(0, 0, 'Unchanged A')
        parts = [same, self.sdt_part(0, 1, 'Old B'),
                 self.sdt_part(31, 0, 'Version31 A'), self.sdt_part(31, 1, 'Version31 B'),
                 same, self.sdt_part(0, 1, 'New B')]
        state, _ = self.analyze_packets([self.packetize(0x11, raw, cc)[0]
                                         for cc, raw in enumerate(parts)])
        record = next(t for t in state['tables'] if t['first_packet'] == 0)
        partial = self.core.call('inspect', {'id': record['id'], 'at_packet': 4})
        self.assertEqual(partial['count'], 2)
        self.assertEqual(partial['occurrences'], [0, 4])
        self.assertFalse(partial['native_table_complete'])
        original = self.core.call('inspect', {'id': record['id'], 'at_packet': 1})
        self.assertTrue(original['native_table_complete'])
        self.assertEqual([n['attributes']['service_name'] for n in
                          self.tree_nodes(original['native_table'], 'service_descriptor')],
                         ['Unchanged A', 'Old B'])
        latest = self.core.call('inspect', {'id': record['id'], 'at_packet': 5})
        self.assertEqual([n['attributes']['service_name'] for n in
                          self.tree_nodes(latest['native_table'], 'service_descriptor')],
                         ['Unchanged A', 'New B'])

    def test_spanning_section_continuity_gap_discards_partial_and_recovers(self):
        raw = self.sdt_part(1, 0, 'L' * 200, last=0)
        lost = self.packetize(0x11, raw, 0)
        self.assertEqual(len(lost), 2)
        corrupt = bytearray(lost[1])
        corrupt[3] = 0x12  # Missing counter 1, without a discontinuity indicator.
        recovered = self.packetize(0x11, raw, 3)
        state, details = self.analyze_packets([lost[0], bytes(corrupt)] + recovered)
        self.assertEqual(state['demux']['discontinuities'], 1)
        self.assertEqual(state['observations'], 1)
        self.assertEqual(len(state['services']), 1)
        self.assertEqual(details[0]['occurrences'], [2])
        self.assertEqual(details[0]['occurrence_end_packets'], [3])
        self.assertEqual(details[0]['raw_hex'], raw.hex().upper())
        warning = next(d for d in state['diagnostics'] if d['code'] == 'transport_discontinuity')
        self.assertTrue(warning['aggregate'])
        self.assertEqual(warning['count'], 1)
        self.assertEqual(self.core.call('query', {'at_packet': 2})['services'], [])

    def test_duplicate_ts_packet_does_not_duplicate_or_break_spanning_section(self):
        raw = self.sdt_part(1, 0, 'D' * 200, last=0)
        packets = self.packetize(0x11, raw, 0)
        state, details = self.analyze_packets([packets[0], packets[0], packets[1]])
        self.assertEqual(state['demux']['discontinuities'], 0)
        self.assertEqual(state['observations'], 1)
        self.assertEqual(details[0]['raw_hex'], raw.hex().upper())
        self.assertEqual(details[0]['occurrences'], [0])
        self.assertEqual(details[0]['occurrence_end_packets'], [2])

    def test_pointer_field_completes_old_section_then_starts_new_one(self):
        first = self.sdt_part(1, 0, 'P' * 200)
        second = self.sdt_part(1, 1, 'Following')
        initial = self.packetize(0x11, first, 0)[0]
        tail = first[183:]
        payload = bytes([len(tail)]) + tail + second
        self.assertLessEqual(len(payload), 184)
        final = bytes([0x47, 0x40, 0x11, 0x11]) + payload + b'\xff' * (184 - len(payload))
        state, details = self.analyze_packets([initial, final])
        self.assertEqual(state['demux']['discontinuities'], 0)
        self.assertEqual(state['observations'], 2)
        self.assertEqual([s['name'] for s in state['services']], ['P' * 200, 'Following'])
        self.assertEqual([d['occurrence_end_packets'] for d in details], [[1], [1]])
        self.assertEqual(self.core.call('query', {'at_packet': 0})['services'], [])
        self.assertTrue(all(d['native_table_complete'] for d in details))

    def test_multisection_pat_waits_for_all_current_generation_sections(self):
        def pat(version, number, pid):
            raw = bytearray(section(0, 1, version, word(100 + number) + word(0xe000 | pid)))
            raw[6], raw[7] = number, 1
            raw[-4:] = crc(raw[:-4]).to_bytes(4, 'big')
            return bytes(raw)
        parts = [(0x11, self.sdt_part(0, 0, 'Service A')),
                 (0x11, self.sdt_part(0, 1, 'Service B')),
                 (0, pat(31, 0, 0x100)), (0, pat(31, 1, 0x101)),
                 (0, pat(0, 0, 0x110)), (0, pat(0, 1, 0x111))]
        counters, packets = {}, []
        for pid, raw in parts:
            packets += self.packetize(pid, raw, counters.get(pid, 0))
            counters[pid] = counters.get(pid, 0) + 1
        state, _ = self.analyze_packets(packets)
        def pids(at):
            return [s['pmt_pid'] for s in self.core.call('query', {'at_packet': at})['services']]
        self.assertEqual(pids(2), [None, None])
        self.assertEqual(pids(3), [0x100, 0x101])
        self.assertEqual(pids(4), [None, None])
        self.assertEqual(pids(5), [0x110, 0x111])
        self.assertEqual(state['demux']['discontinuities'], 0)

    def test_dvb_special_descriptors_and_pmt_discovered_ait(self):
        pat = section(0, 1, 0, word(101) + word(0xe100))
        packets = self.packetize(0, pat)
        packets += self.packetize(0x100, bytes.fromhex(FIXTURES['DVB_SPECIAL_PMT'][1]))
        packets += self.packetize(0x150, bytes.fromhex(FIXTURES['DVB_AIT'][1]))
        state, details = self.analyze_packets(packets)
        pmt = self.assert_native(details, 'PMT')
        expected = ['HEVC_video_descriptor', 'DVB_AC4_descriptor', 'ISO_639_language_descriptor',
                    'subtitling_descriptor', 'application_signalling_descriptor']
        for name in expected:
            self.assertEqual(len(self.tree_nodes(pmt, name)), 1)
        hevc = self.tree_nodes(pmt, 'HEVC_video_descriptor')[0]['attributes']
        self.assertEqual(self.number(hevc['profile_idc']), 1)
        self.assertEqual(self.number(hevc['level_idc']), 120)
        ac4 = self.tree_nodes(pmt, 'DVB_AC4_descriptor')[0]['attributes']
        self.assertEqual(ac4['ac4_dialog_enhancement_enabled'], 'true')
        subtitle = self.tree_nodes(pmt, 'subtitling')[0]['attributes']
        self.assertEqual(subtitle['language_code'], 'eng')
        self.assertEqual(self.number(subtitle['composition_page_id']), 1)
        ait = self.assert_native(details, 'AIT')
        self.assertEqual(self.number(ait['attributes']['application_type']), 0x10)
        self.assertEqual(self.tree_nodes(ait, 'language')[0]['attributes']['application_name'], 'Lab Guide')
        self.assertEqual(self.tree_nodes(ait, 'profile')[0]['attributes']['version'], '1.2.3')
        self.assertEqual(self.number(self.tree_nodes(ait, 'object_carousel')[0]['attributes']['component_tag']), 11)
        self.assertTrue(any(t['pid'] == 0x150 for t in state['tables']))

    def test_atsc_caption_location_multiple_strings_and_content_advisory(self):
        _, details = self.analyze(['ATSC_SPECIAL_TVCT', 'ATSC_SPECIAL_EIT'], 'atsc', [0x151])
        vct = self.assert_native(details, 'TVCT')
        location = self.tree_nodes(vct, 'service_location_descriptor')[0]
        self.assertEqual(self.number(location['attributes']['pcr_pid']), 0x201)
        self.assertEqual([self.number(c['attributes']['elementary_pid']) for c in location['children']],
                         [0x201, 0x202])
        self.assertEqual(location['children'][1]['attributes']['iso_639_language_code'], 'eng')
        strings = self.tree_nodes(vct, 'string')
        self.assertEqual(strings[0]['attributes']['text'], 'Laboratory HD')
        caption = self.tree_nodes(vct, 'caption_service_descriptor')[0]['children'][0]['attributes']
        self.assertEqual(caption['language'], 'eng')
        self.assertEqual(caption['digital_cc'], 'true')
        self.assertEqual(self.number(caption['caption_service_number']), 1)
        eit = self.assert_native(details, 'ATSC_EIT')
        event = self.tree_nodes(eit, 'event')[0]
        self.assertEqual(self.number(event['attributes']['event_id']), 17)
        self.assertEqual(event['attributes']['start_time'], '2026-10-16 12:00:00')
        self.assertEqual(self.number(event['attributes']['length_in_seconds']), 3600)
        self.assertEqual([n['attributes']['text'] for n in self.tree_nodes(eit, 'string')], ['Science Lab', 'PG'])
        rating = self.tree_nodes(eit, 'dimension')[0]['attributes']
        self.assertEqual(self.number(rating['rating_value']), 3)
        self.assertEqual(self.tree_nodes(eit, 'caption_service_descriptor')[0]['children'][0]['attributes']['language'], 'spa')

    def test_atsc_family_context_reaches_flat_pmt_descriptors(self):
        # 0x86 is ATSC caption_service_descriptor in this context, not a DVB
        # private descriptor requiring an on-wire private-data-specifier.
        caption = bytes.fromhex('8607e1656e67c17fff')
        pmt = section(2, 101, 0, word(0xe201) + word(0xf000) +
                      bytes([0x1b]) + word(0xe201) + word(0xf000 | len(caption)) + caption)
        _, details = self.analyze_packets(self.packetize(0x100, pmt), 'atsc', [0x100])
        native = self.assert_native(details, 'PMT')
        self.assertEqual(len(self.tree_nodes(native, 'caption_service_descriptor')), 1)
        flat = details[0]['descriptors'][0]
        self.assertEqual(flat['pds'], 0)  # Preserve actual wire evidence.
        self.assertTrue(flat['native_decoded'])
        self.assertEqual(flat['native']['name'], 'caption_service_descriptor')
        service = flat['native']['children'][0]['attributes']
        self.assertEqual(service['language'], 'eng')
        self.assertEqual(self.number(service['caption_service_number']), 1)

    def test_isdb_terrestrial_ts_information_and_partial_reception(self):
        _, details = self.analyze(['ISDB_SPECIAL_NIT'], 'isdb')
        nit = self.assert_native(details, 'NIT')
        delivery = self.tree_nodes(nit, 'ISDB_terrestrial_delivery_system_descriptor')[0]
        self.assertEqual(self.number(delivery['attributes']['area_code']), 0x123)
        self.assertEqual(delivery['attributes']['guard_interval'], '1/8')
        self.assertEqual(delivery['attributes']['transmission_mode'], '8k')
        self.assertEqual(self.number(delivery['children'][0]['attributes']['value']), 473000000)
        info = self.tree_nodes(nit, 'TS_information_descriptor')[0]
        self.assertEqual(self.number(info['attributes']['remote_control_key_id']), 7)
        self.assertEqual(info['attributes']['ts_name'], 'ISDB Lab')
        self.assertEqual(self.number(self.tree_nodes(info, 'service')[0]['attributes']['id']), 101)
        partial = self.tree_nodes(nit, 'partial_reception_descriptor')[0]
        self.assertEqual(self.number(partial['children'][0]['attributes']['id']), 101)
        management = self.tree_nodes(nit, 'system_management_descriptor')[0]['attributes']
        self.assertEqual(self.number(management['broadcasting_identifier']), 3)
        self.assertTrue(all(d['native_decoded'] for d in details[0]['descriptors']))

    def test_pmt_discovers_scte_splice_pid_and_preserves_segmentation_fields(self):
        pat = section(0, 1, 0, word(101) + word(0xe100))
        registration = descriptor(0x05, b'CUEI')
        pmt = section(2, 101, 0, word(0xffff) + word(0xf000 | len(registration)) +
                      registration + bytes([0x86]) + word(0xe152) + word(0xf000))
        raw = bytes.fromhex(FIXTURES['SCTE_SPLICE'][1])
        packets = self.packetize(0, pat) + self.packetize(0x100, pmt) + self.packetize(0x152, raw)
        state, details = self.analyze_packets(packets, 'scte')
        splice = self.assert_native(details, 'splice_information_table')
        self.assertEqual(self.number(splice['attributes']['pts_adjustment']), 90)
        self.assertEqual(self.number(self.tree_nodes(splice, 'time_signal')[0]['attributes']['pts_time']), 900000)
        segmentation = self.tree_nodes(splice, 'splice_segmentation_descriptor')[0]
        self.assertEqual(self.number(segmentation['attributes']['segmentation_event_id']), 17)
        self.assertEqual(self.number(segmentation['attributes']['segmentation_duration']), 5400000)
        self.assertEqual(self.number(segmentation['attributes']['segmentation_type_id']), 0x30)
        upid = self.tree_nodes(segmentation, 'segmentation_upid')[0]
        self.assertEqual(self.number(upid['attributes']['type']), 0x0f)
        self.assertEqual(''.join(upid['text'].split()), '4C41422D3137')
        self.assertEqual(self.number(self.tree_nodes(splice, 'splice_avail_descriptor')[0]['attributes']['provider_avail_id']), 42)
        detail = next(d for d in details if d['pid'] == 0x152)
        self.assertEqual(detail['raw_hex'], raw.hex().upper())
        self.assertEqual(state['demux']['discontinuities'], 0)

    def test_snapshot_same_packet_versions_follow_wire_observation_order(self):
        a = self.sdt_part(0, 0, 'A', last=0)
        b = self.sdt_part(1, 0, 'B', last=0)
        for order, expected in [([b, a], 'A'), ([a, b], 'B')]:
            with self.subTest(expected=expected):
                payload = b'\0' + b''.join(order)
                packet = bytes([0x47, 0x40, 0x11, 0x11]) + payload + b'\xff' * (184 - len(payload))
                state, _ = self.analyze_packets(self.packetize(0x11, a) + [packet])
                self.assertEqual(state['observations'], 3)
                self.assertEqual([service['name'] for service in state['services']], [expected])
                change = self.core.call('diff_snapshots', {'from_packet': 0, 'to_packet': 1})
                if expected == 'A':
                    self.assertEqual(change['total_changes'], 0)
                    self.assertEqual(change['summary']['services']['unchanged'], 1)
                else:
                    self.assertEqual(change['summary']['services']['changed'], 1)
                    self.assertEqual(change['summary']['tables']['changed'], 1)
                    service = next(c for c in change['changes'] if c['kind'] == 'services')
                    self.assertEqual(service['before']['value']['name'], 'A')
                    self.assertEqual(service['after']['value']['name'], 'B')
                selected = state['services'][0]['source_id']
                inspected = self.core.call('inspect', {'id': selected, 'at_packet': 1})
                self.assertTrue(inspected['native_table_complete'])
                self.assertEqual(self.tree_nodes(inspected['native_table'], 'service_descriptor')[0]
                                 ['attributes']['service_name'], expected)

    def test_snapshot_completion_cutoff_does_not_expose_partial_section(self):
        old = self.sdt_part(0, 0, 'Before', last=0)
        new = self.sdt_part(1, 0, 'N' * 200, last=0)
        packets = self.packetize(0x11, old) + self.packetize(0x11, new, 1)
        state, _ = self.analyze_packets(packets)
        incomplete = self.core.call('diff_snapshots', {'from_packet': 0, 'to_packet': 1})
        self.assertEqual(incomplete['total_changes'], 0)
        complete = self.core.call('diff_snapshots', {'from_packet': 1, 'to_packet': 2})
        self.assertEqual(complete['summary']['services']['changed'], 1)
        service = next(c for c in complete['changes'] if c['kind'] == 'services')
        self.assertEqual(service['before']['value']['name'], 'Before')
        self.assertEqual(service['after']['value']['name'], 'N' * 200)
        self.assertEqual(service['after']['evidence'][0]['first_packet'], 1)
        self.assertEqual(service['after']['evidence'][0]['last_packet'], 2)
        self.assertEqual(state['packets'], 3)

    def test_snapshot_pagination_order_and_repeat_evidence_are_stable(self):
        # Network IDs have a deliberately different numeric/lexicographic order.
        parts = []
        for onid in [9, 2, 20, 10]:
            raw = bytearray(self.sdt_part(0, 0, 'Network ' + str(onid), last=0))
            raw[8:10] = word(onid)
            raw[-4:] = crc(raw[:-4]).to_bytes(4, 'big')
            parts.append(bytes(raw))
        null = bytes([0x47, 0x1f, 0xff, 0x10]) + b'\xff' * 184
        packets = [null] + [self.packetize(0x11, raw, index)[0]
                            for index, raw in enumerate(parts + parts)]
        state, _ = self.analyze_packets(packets)
        args = {'from_packet': 0, 'to_packet': 8}
        baseline = self.core.call('diff_snapshots', args)
        self.assertEqual(baseline['total_changes'], 8)
        self.assertEqual([c['kind'] for c in baseline['changes']], ['tables'] * 4 + ['services'] * 4)
        for kind in ['tables', 'services']:
            keys = [c['key'] for c in baseline['changes'] if c['kind'] == kind]
            self.assertEqual(keys, sorted(keys))
        for kind in ['all', 'tables', 'services', 'events']:
            with self.subTest(kind=kind):
                expected = [c for c in baseline['changes'] if kind == 'all' or c['kind'] == kind]
                rows, offset = [], 0
                while offset is not None:
                    page = self.core.call('diff_snapshots', {**args, 'kind': kind, 'offset': offset, 'limit': 3})
                    self.assertEqual(page['summary'], baseline['summary'])
                    self.assertEqual(page['total_changes'], len(expected))
                    self.assertEqual(page['revision'], state['revision'])
                    rows.extend(page['changes'])
                    self.assertTrue(page['next_offset'] is None or page['next_offset'] > offset)
                    offset = page['next_offset']
                self.assertEqual(rows, expected)
                for offset in [len(expected), 9007199254740991]:
                    empty = self.core.call('diff_snapshots', {**args, 'kind': kind, 'offset': offset})
                    self.assertEqual(empty['changes'], [])
                    self.assertIsNone(empty['next_offset'])
        repeated = self.core.call('diff_snapshots', {'from_packet': 4, 'to_packet': 8})
        self.assertEqual(repeated['total_changes'], 0)
        self.assertEqual(repeated['summary']['services']['unchanged'], 4)
        self.assertTrue(all(c['after']['evidence'][0]['count'] == 2 for c in baseline['changes']))

    @staticmethod
    def eit_events(version, entries, onid=2):
        payload = word(1) + word(onid) + bytes([0, 0x4e])
        for eid, hour, title in entries:
            text = title.encode('ascii')
            desc = descriptor(0x4d, b'eng' + bytes([len(text)]) + text + b'\0')
            payload += (word(eid) + word(61000) + bytes([hour, 0, 0, 1, 0, 0]) +
                        word(0x8000 | len(desc)) + desc)
        return section(0x4e, 101, version, payload)

    def test_snapshot_rescheduled_and_duplicate_eit_identities_remain_distinct(self):
        old = self.eit_events(0, [(7, 9, 'First'), (7, 9, 'Duplicate')])
        new = self.eit_events(1, [(7, 9, 'First'), (7, 9, 'Duplicate changed')])
        rescheduled = self.eit_events(2, [(7, 0x10, 'First'), (7, 0x10, 'Duplicate changed')])
        other = self.eit_events(0, [(7, 9, 'Other network')], onid=3)
        null = bytes([0x47, 0x1f, 0xff, 0x10]) + b'\xff' * 184
        packets = [null] + [self.packetize(0x12, raw, index)[0]
                            for index, raw in enumerate([old, new, rescheduled, other])]
        self.analyze_packets(packets)
        initial = self.core.call('diff_snapshots', {'from_packet': 0, 'to_packet': 1, 'kind': 'events'})
        self.assertEqual(initial['total_changes'], 2)
        self.assertEqual(len({c['key'] for c in initial['changes']}), 2)
        self.assertEqual(sorted(c['identity'].get('duplicate_index', 0) for c in initial['changes']), [0, 1])
        changed = self.core.call('diff_snapshots', {'from_packet': 1, 'to_packet': 2, 'kind': 'events'})
        self.assertEqual(changed['summary']['events'], {'added': 0, 'removed': 0, 'changed': 1, 'unchanged': 1})
        self.assertEqual(changed['changes'][0]['changed_fields'], ['language_variants', 'title'])
        moved = self.core.call('diff_snapshots', {'from_packet': 2, 'to_packet': 3, 'kind': 'events'})
        self.assertEqual(moved['summary']['events'], {'added': 2, 'removed': 2, 'changed': 0, 'unchanged': 0})
        self.assertEqual(len({c['key'] for c in moved['changes']}), 4)
        independent = self.core.call('diff_snapshots', {'from_packet': 3, 'to_packet': 4, 'kind': 'events'})
        self.assertEqual(independent['summary']['events'], {'added': 1, 'removed': 0, 'changed': 0, 'unchanged': 2})
        self.assertEqual(independent['changes'][0]['identity']['original_network_id'], 3)

    def test_extra_pid_sdt_cannot_shadow_canonical_service_projection(self):
        fixed = self.sdt_part(0, 0, 'Fixed initial', last=0)
        extra = self.sdt_part(0, 0, 'Extra conflicting', last=0)
        updated = self.sdt_part(1, 0, 'Fixed new', last=0)
        for extra_first in [False, True]:
            with self.subTest(extra_first=extra_first):
                entries = [(0x11, fixed, 0), (0x20, extra, 0)]
                if extra_first:
                    entries.reverse()
                entries.append((0x11, updated, 1))
                state, details = self.analyze_packets(
                    [self.packetize(pid, raw, cc)[0] for pid, raw, cc in entries], extra_pids=[0x20])
                self.assertEqual([service['name'] for service in state['services']], ['Fixed new'])
                self.assertEqual([service['name'] for service in
                                  self.core.call('query', {'at_packet': 1})['services']], ['Fixed initial'])
                changes = self.core.call('diff_snapshots', {'from_packet': 1, 'to_packet': 2})
                self.assertEqual(changes['summary']['services']['changed'], 1)
                service = next(c for c in changes['changes'] if c['kind'] == 'services')
                self.assertEqual(service['before']['value']['name'], 'Fixed initial')
                self.assertEqual(service['after']['value']['name'], 'Fixed new')
                self.assertTrue(all(e['pid'] == 0x11 for e in service['after']['evidence']))
                noncanonical = next(d for d in details if d['pid'] == 0x20)
                self.assertTrue(noncanonical['native_table_complete'])
                self.assertEqual(noncanonical['raw_hex'], extra.hex().upper())
                self.assertEqual(self.tree_nodes(noncanonical['native_table'], 'service_descriptor')[0]
                                 ['attributes']['service_name'], 'Extra conflicting')
        state, details = self.analyze_packets(self.packetize(0x20, extra), extra_pids=[0x20])
        self.assertEqual(state['services'], [])
        self.assertEqual(len(state['tables']), 1)
        self.assert_native(details, 'SDT')
        unchanged = self.core.call('diff_snapshots', {'from_packet': 0, 'to_packet': 0})
        self.assertEqual(unchanged['summary']['services']['unchanged'], 0)
        self.assertEqual(unchanged['summary']['tables']['unchanged'], 1)


    def assert_fixture_native(self, details, fixture_name, table_name):
        """Require semantic decoding AND the exact on-wire fixture section."""
        pid, raw = FIXTURES[fixture_name]
        matched = [d for d in details if d['pid'] == pid and d['raw_hex'] == raw.upper()]
        self.assertEqual(len(matched), 1, fixture_name)
        self.assertEqual(matched[0]['native_decode_status'], 'native TSDuck decoder')
        return self.assert_native(matched, table_name)

    def test_expanded_fixture_provenance_and_crc(self):
        self.assertIn('version 3.45-4798', EXPANDED_MANIFEST['generator'])
        for name, fixture in EXPANDED_FIXTURES.items():
            with self.subTest(fixture=name):
                self.assertEqual(hashlib.sha256((EXPANDED_FIXTURE_DIR / fixture['xml']).read_text(encoding='utf-8').encode('utf-8')).hexdigest(),
                                 fixture['xml_sha256'])
                raw = bytes.fromhex(fixture['hex'])
                self.assertEqual(hashlib.sha256(raw).hexdigest(), fixture['sha256'])
                self.assertEqual(3 + ((raw[1] & 15) << 8 | raw[2]), len(raw))
                self.assertEqual(crc(raw), 0)

    def test_dtmb_drm_fields_and_exact_license_bytes(self):
        state, details = self.analyze(['DTMB_DRM_PMT'], 'dtmb', [0x100])
        pmt = self.assert_fixture_native(details, 'DTMB_DRM_PMT', 'PMT')
        drm = self.tree_nodes(pmt, 'DTMB_DRM_descriptor')[0]
        self.assertEqual({k: self.number(v) for k, v in drm['attributes'].items()},
                         {'video_format': 3, 'video_encryption_method': 2,
                          'audio_format': 5, 'audio_encryption_method': 1})
        self.assertEqual(''.join(drm['children'][0]['text'].split()), '1020CAFE')
        flat = details[0]['descriptors'][0]
        self.assertEqual(flat['native']['name'], 'DTMB_DRM_descriptor')
        self.assertTrue(flat['native_decoded'])
        self.assertEqual(flat['pds'], 0)
        self.assertEqual(flat['raw'], 'C00632511020CAFE')
        self.assertEqual(details[0]['standards_context'], 'dtmb')
        # Encryption signaling is inspected, never treated as decryption.
        self.assertEqual(state['crc_errors'], 0)

    def test_dtmb_explicit_utf8_selector_preserves_chinese_and_bmp_unicode(self):
        # --china alone selects a standards flag. UTF-8 is independently explicit
        # in the compiler arguments AND the service descriptor's 0x15 selectors.
        _, details = self.analyze(['DTMB_UTF8_SDT'], 'dtmb')
        sdt = self.assert_fixture_native(details, 'DTMB_UTF8_SDT', 'SDT')
        service = self.tree_nodes(sdt, 'service_descriptor')[0]['attributes']
        self.assertEqual(service['service_provider_name'], '实验室 Ω')
        self.assertEqual(service['service_name'], '中文频道 Ω')
        raw = bytes.fromhex(FIXTURES['DTMB_UTF8_SDT'][1])
        self.assertIn(b'\x15' + '实验室 Ω'.encode('utf-8'), raw)
        self.assertIn(b'\x15' + '中文频道 Ω'.encode('utf-8'), raw)

    def test_dtmb_wrong_family_and_truncated_descriptor_keep_raw_evidence(self):
        _, details = self.analyze(['DTMB_DRM_PMT'], 'dvb', [0x100])
        self.assertEqual(details[0]['raw_hex'], FIXTURES['DTMB_DRM_PMT'][1].upper())
        self.assertFalse(self.tree_nodes(details[0]['native_table'], 'DTMB_DRM_descriptor'))
        self.assertEqual(details[0]['descriptors'][0]['native']['name'], 'generic_descriptor')
        short = descriptor(0xc0, b'\x32')  # Missing audio format/encryption octet.
        pmt = section(2, 101, 0, word(0xe201) + word(0xf000) +
                      b'\x1b' + word(0xe201) + word(0xf000 | len(short)) + short)
        _, details = self.analyze_packets(self.packetize(0x100, pmt), 'dtmb', [0x100])
        self.assertEqual(details[0]['raw_hex'], pmt.hex().upper())
        flat = details[0]['descriptors'][0]
        self.assertFalse(flat['native_decoded'])
        self.assertEqual(flat['native']['name'], 'generic_descriptor')
        self.assertEqual(flat['raw'], 'C00132')

    def test_isdb_amt_reserved_pid_ipv4_ipv6_and_private_data(self):
        state, details = self.analyze(['ISDB_AMT'], 'isdb')
        amt = self.assert_fixture_native(details, 'ISDB_AMT', 'AMT')
        self.assertTrue(any(t['pid'] == 0x2e for t in state['tables']))
        services = self.tree_nodes(amt, 'service')
        self.assertEqual([self.number(n['attributes']['service_id']) for n in services], [101, 102])
        self.assertEqual(services[0]['attributes']['src'], '192.0.2.17/24')
        self.assertEqual(services[0]['attributes']['dst'], '239.1.2.3/32')
        self.assertEqual(services[1]['attributes']['src'], '2001:db8::17/64')
        self.assertEqual(services[1]['attributes']['dst'], 'ff3e::1234/128')
        self.assertEqual([''.join(n['children'][0]['text'].split()) for n in services], ['CAFE', '010203'])

    def test_isdb_advanced_cable_numeric_fields_and_other_data_preservation(self):
        _, details = self.analyze(['ISDB_ADVANCED_CABLE_NIT'], 'isdb')
        nit = self.assert_fixture_native(details, 'ISDB_ADVANCED_CABLE_NIT', 'NIT')
        descriptors = self.tree_nodes(nit, 'ISDB_advanced_cable_delivery_system_descriptor')
        self.assertEqual(len(descriptors), 2)
        normal = descriptors[0]['children'][0]
        self.assertEqual({k: self.number(v) for k, v in normal['attributes'].items()},
                         {'plp_id': 7, 'effective_symbol_length': 2, 'guard_interval': 3, 'bundled_channel': 4})
        carrier = normal['children'][0]['attributes']
        self.assertEqual({k: self.number(v) for k, v in carrier.items()},
                         {'data_slice_id': 9, 'frequency': 450000000, 'frame_type': 2,
                          'fec_outer': 1, 'modulation': 5, 'fec_inner': 3})
        other = descriptors[1]['children'][0]
        self.assertEqual(self.number(other['attributes']['descriptor_tag_extension']), 1)
        # The compiler pads extension 1 to its specified 88-byte capacity.
        self.assertEqual(bytes.fromhex(other['text']), bytes(range(28)) + b'\xff' * 60)
        self.assertTrue(all(d['native_decoded'] for d in details[0]['descriptors']))

    def test_atsc_aggregate_event_tables_unicode_and_timing(self):
        names = ['ATSC_AEIT', 'ATSC_AETT', 'ATSC_LTST']
        _, details = self.analyze(names, 'atsc', [FIXTURES[n][0] for n in names])
        aeit = self.assert_fixture_native(details, 'ATSC_AEIT', 'AEIT')
        self.assertEqual(self.number(aeit['attributes']['mgt_tag']), 7)
        event = self.tree_nodes(aeit, 'event')[0]['attributes']
        self.assertEqual(event['start_time'], '2026-10-16 12:00:00')
        self.assertEqual(self.number(event['duration']), 1800)
        self.assertEqual(self.number(event['event_id']), 17)
        self.assertEqual(self.tree_nodes(aeit, 'string')[0]['attributes']['text'], '数据实验 Ω')
        aett = self.assert_fixture_native(details, 'ATSC_AETT', 'AETT')
        self.assertEqual(self.number(self.tree_nodes(aett, 'ETM_data')[0]['attributes']['etm_id']), 0x00650046)
        self.assertEqual(self.tree_nodes(aett, 'string')[0]['attributes']['text'], '节目详情 Café')
        ltst = self.assert_fixture_native(details, 'ATSC_LTST', 'LTST')
        data = self.tree_nodes(ltst, 'data')[0]['attributes']
        self.assertEqual(self.number(data['data_id']), 10)
        self.assertEqual(data['start_time'], '2026-10-16 13:00:00')
        self.assertEqual(self.number(data['length_in_seconds']), 600)
        self.assertEqual(self.tree_nodes(ltst, 'string')[0]['attributes']['text'], '长期数据')

    def test_atsc_data_tables_fields_and_opaque_payloads(self):
        names = ['ATSC_DET', 'ATSC_DST', 'ATSC_NRT']
        _, details = self.analyze(names, 'atsc', [FIXTURES[n][0] for n in names])
        det = self.assert_fixture_native(details, 'ATSC_DET', 'DET')
        data = self.tree_nodes(det, 'data')[0]['attributes']
        self.assertEqual(self.number(data['data_id']), 9)
        self.assertEqual(data['start_time'], '2026-10-16 12:00:00')
        self.assertEqual(self.number(data['length_in_seconds']), 1800)
        self.assertEqual(self.tree_nodes(det, 'string')[0]['attributes']['text'], 'Data Ω')
        download = self.tree_nodes(det, 'ATSC_download_descriptor')[0]['attributes']
        self.assertEqual({k: self.number(v) for k, v in download.items()},
                         {'download_id': 0x12345678, 'carousel_period': 3000, 'control_msg_time_out_value': 5000})
        dst = self.assert_fixture_native(details, 'ATSC_DST', 'DST')
        self.assertEqual(self.number(dst['attributes']['table_id_extension']), 0x1234)
        self.assertEqual(''.join(self.tree_nodes(dst, 'app_id')[0]['text'].split()), '11223344')
        self.assertEqual(''.join(self.tree_nodes(dst, 'app_data')[0]['text'].split()), '0102CAFE')
        self.assertEqual(''.join(self.tree_nodes(dst, 'service_private_data')[0]['text'].split()), 'AABBCC')
        nrt = self.assert_fixture_native(details, 'ATSC_NRT', 'NRT')
        self.assertEqual(self.number(nrt['attributes']['table_id_extension']), 0x4321)
        self.assertEqual(''.join(self.tree_nodes(nrt, 'private_data')[0]['text'].split()), '001122CAFE')

    def test_atsc_satellite_vct_chinese_name_and_carrier_fields(self):
        _, details = self.analyze(['ATSC_SVCT'], 'atsc', [0x166])
        svct = self.assert_fixture_native(details, 'ATSC_SVCT', 'SVCT')
        channel = self.tree_nodes(svct, 'channel')[0]['attributes']
        self.assertEqual(channel['short_name'], '实验HD')
        self.assertEqual(self.number(channel['major_channel_number']), 7)
        self.assertEqual(self.number(channel['minor_channel_number']), 2)
        self.assertEqual(self.number(channel['carrier_frequency']), 12345000000)
        self.assertEqual(self.number(channel['carrier_symbol_rate']), 27500000)
        self.assertEqual(self.number(channel['feed_id']), 11)

    def test_dsmcc_download_block_and_control_module_fields(self):
        _, details = self.analyze(['DSMCC_DDB', 'DSMCC_DII'], 'dvb', [0x170, 0x171])
        ddb = self.assert_fixture_native(details, 'DSMCC_DDB', 'DSMCC_download_data_message')
        self.assertEqual(self.number(ddb['attributes']['message_id']), 0x1003)
        self.assertEqual(self.number(ddb['attributes']['download_id']), 0x10203040)
        self.assertEqual(self.number(ddb['attributes']['module_id']), 7)
        self.assertEqual(self.number(ddb['attributes']['module_version']), 3)
        self.assertEqual(''.join(self.tree_nodes(ddb, 'block_data')[0]['text'].split()), '00010203CAFE')
        dii = self.assert_fixture_native(details, 'DSMCC_DII', 'DSMCC_user_to_network_message')
        self.assertEqual(self.number(dii['attributes']['transaction_id']), 0x12345678)
        header = self.tree_nodes(dii, 'DII')[0]['attributes']
        self.assertEqual(self.number(header['download_id']), 0x10203040)
        self.assertEqual(self.number(header['block_size']), 1024)
        module = self.tree_nodes(dii, 'module')[0]['attributes']
        self.assertEqual(self.number(module['module_id']), 7)
        self.assertEqual(self.number(module['module_size']), 6)
        self.assertEqual(self.number(module['module_timeout']), 1000)
        self.assertEqual(self.tree_nodes(dii, 'dsmcc_name_descriptor')[0]['attributes']['name'], 'module.bin')
        self.assertEqual(self.number(self.tree_nodes(dii, 'dsmcc_CRC32_descriptor')[0]['attributes']['crc_32']), 0x12345678)
        self.assertFalse(self.tree_nodes(dii, 'registration_descriptor'))
        # These fields do not establish extraction, decompression or file reassembly.

    def test_dvb_container_fonts_fec_and_astra_service_guide(self):
        names = ['DVB_CONTAINER', 'DVB_DFIT', 'DVB_MPE_FEC', 'DVB_MPE_IFEC', 'ASTRA_SGT']
        _, details = self.analyze(names, 'dvb', [FIXTURES[n][0] for n in names])
        container = self.assert_fixture_native(details, 'DVB_CONTAINER', 'container_table')
        self.assertEqual(self.number(container['attributes']['container_id']), 7)
        self.assertEqual(''.join(self.tree_nodes(container, 'compression_wrapper')[0]['text'].split()), '001122CAFE')
        font = self.assert_fixture_native(details, 'DVB_DFIT', 'DFIT')
        self.assertEqual(font['attributes']['font_family'], 'Lab Sans')
        self.assertEqual(self.number(font['attributes']['font_id']), 7)
        self.assertEqual(self.number(self.tree_nodes(font, 'font_style_weight')[0]['attributes']['font_weight']), 6)
        self.assertEqual(self.tree_nodes(font, 'font_file_URI')[0]['attributes']['uri'], 'https://example.invalid/font.otf')
        fec = self.assert_fixture_native(details, 'DVB_MPE_FEC', 'MPE_FEC')
        self.assertEqual(self.number(fec['attributes']['padding_columns']), 4)
        self.assertEqual(self.number(self.tree_nodes(fec, 'real_time_parameters')[0]['attributes']['address']), 42)
        self.assertEqual(''.join(self.tree_nodes(fec, 'rs_data')[0]['text'].split()), '00112233CAFE')
        ifec = self.assert_fixture_native(details, 'DVB_MPE_IFEC', 'MPE_IFEC')
        self.assertEqual(self.number(ifec['attributes']['ifec_burst_size']), 8)
        self.assertEqual(self.number(self.tree_nodes(ifec, 'real_time_parameters')[0]['attributes']['prev_burst_size']), 43)
        self.assertEqual(''.join(self.tree_nodes(ifec, 'IFEC_data')[0]['text'].split()), 'DEADBEEFCAFE')
        sgt = self.assert_fixture_native(details, 'ASTRA_SGT', 'SGT')
        service = self.tree_nodes(sgt, 'service')[0]['attributes']
        self.assertEqual(self.number(service['service_id']), 101)
        self.assertEqual(self.number(service['logical_channel_number']), 123)
        self.assertEqual(service['new_service_flag'], 'true')
        self.assertEqual(self.number(service['genre_code']), 0x1002)

    def test_truncated_new_table_payloads_fall_back_without_losing_bytes(self):
        for name in ['ISDB_AMT', 'ATSC_DET', 'DSMCC_DDB']:
            with self.subTest(fixture=name):
                fixture = EXPANDED_FIXTURES[name]
                raw = bytearray.fromhex(fixture['hex'])[:9]
                # Keep a complete CRC-correct section with too little semantic
                # payload. Transport completeness is not semantic validity.
                size = len(raw) + 4 - 3
                raw[1] = (raw[1] & 0xf0) | (size >> 8)
                raw[2] = size & 255
                raw += crc(raw).to_bytes(4, 'big')
                _, details = self.analyze_packets(self.packetize(fixture['pid'], bytes(raw)),
                                                 fixture['standard'], [fixture['pid']])
                self.assertEqual(len(details), 1)
                self.assertEqual(details[0]['raw_hex'], raw.hex().upper())
                self.assertTrue(details[0]['native_table_complete'])
                self.assertEqual(details[0]['native_table']['name'], 'generic_long_table')
                self.assertEqual(details[0]['native_decode_status'], 'generic raw fallback')


    def test_dsmcc_unknown_namespace_never_labels_crc_as_mpeg_registration(self):
        for context in ['auto', 'atsc', 'isdb']:
            with self.subTest(context=context):
                _, details = self.analyze(['DSMCC_DII'], context, [0x171])
                dii = self.assert_fixture_native(details, 'DSMCC_DII', 'DSMCC_user_to_network_message')
                self.assertFalse(self.tree_nodes(dii, 'registration_descriptor'))
                self.assertNotIn('<registration_descriptor', details[0]['tsduck_xml'])
                descriptors = self.tree_nodes(dii, 'generic_descriptor')
                self.assertEqual([self.number(d['attributes']['tag']) for d in descriptors], [2, 5])
                self.assertEqual([''.join(d['text'].split()) for d in descriptors],
                                 ['6D6F64756C652E62696E', '12345678'])
                self.assertTrue(all(not d.get('references') for d in descriptors))
                self.assertTrue(details[0]['native_decode_warnings'])

    def test_mpeg_registration_inheritance_order_and_loop_session_isolation(self):
        _, details = self.analyze(['MPEG_VANC_REGISTRATION_PMT'], 'dvb', [0x100])
        pmt = self.assert_fixture_native(details, 'MPEG_VANC_REGISTRATION_PMT', 'PMT')
        anc = self.tree_nodes(pmt, 'smpte_anc_data_descriptor')[0]
        self.assertEqual(''.join(anc['text'].split()), '00112233')
        flat = next(d for d in details[0]['descriptors'] if d['tag'] == 0xc4)
        self.assertEqual(flat['registration_ids'], [0x56414e43])
        self.assertEqual(flat['native']['name'], 'smpte_anc_data_descriptor')
        self.assertEqual(flat['pds'], 0)
        raw_anc = bytes.fromhex(flat['raw'])
        registration = descriptor(5, b'VANC')
        other_registration = descriptor(5, b'CUEI')
        def component(pid, descs):
            return b'\x06' + word(0xe000 | pid) + word(0xf000 | len(descs)) + descs
        def analyze_pmt(top, streams):
            raw = section(2, 101, 0, word(0xe201) + word(0xf000 | len(top)) + top + b''.join(streams))
            _, observed = self.analyze_packets(self.packetize(0x100, raw), 'dvb', [0x100])
            self.assertEqual(observed[0]['raw_hex'], raw.hex().upper())
            return observed[0]
        # Program-level registrations precede local registrations; a sibling has
        # only program-level context, not a preceding component's local context.
        detail = analyze_pmt(registration, [component(0x201, other_registration + raw_anc),
                                            component(0x202, raw_anc)])
        flat = [d for d in detail['descriptors'] if d['tag'] == 0xc4]
        self.assertEqual([d['registration_ids'] for d in flat],
                         [[0x56414e43, 0x43554549], [0x56414e43]])
        self.assertTrue(all(d['native']['name'] == 'smpte_anc_data_descriptor' for d in flat))
        detail = analyze_pmt(b'', [component(0x201, registration + raw_anc), component(0x202, raw_anc)])
        flat = [d for d in detail['descriptors'] if d['tag'] == 0xc4]
        self.assertEqual([d['registration_ids'] for d in flat], [[0x56414e43], []])
        self.assertEqual([d['native']['name'] for d in flat], ['smpte_anc_data_descriptor', 'generic_descriptor'])
        self.assertEqual([n['name'] for c in self.tree_nodes(detail['native_table'], 'component')
                          for n in c['children'] if n['name'] != 'registration_descriptor'],
                         ['smpte_anc_data_descriptor', 'generic_descriptor'])
        # A new analysis must discard all previous REGID evidence.
        detail = analyze_pmt(b'', [component(0x201, raw_anc)])
        self.assertEqual(detail['descriptors'][0]['registration_ids'], [])
        self.assertFalse(detail['descriptors'][0]['native_decoded'])
        self.assertEqual(detail['descriptors'][0]['native']['name'], 'generic_descriptor')

    def test_expanded_reference_links_are_family_scoped(self):
        fixtures = [('DTMB_DRM_PMT', 'PMT', 'DTMB_DRM_descriptor', 'dtmb-drm'),
                    ('ISDB_AMT', 'AMT', None, 'isdb-si'),
                    ('ISDB_ADVANCED_CABLE_NIT', 'NIT', 'ISDB_advanced_cable_delivery_system_descriptor', 'isdb-cable'),
                    ('ATSC_DET', 'DET', None, 'atsc-data'),
                    ('ATSC_AEIT', 'AEIT', None, 'atsc-dth'),
                    ('DSMCC_DII', 'DSMCC_user_to_network_message', None, 'mpeg-dsmcc'),
                    ('DVB_DFIT', 'DFIT', None, 'dvb-ttml'),
                    ('DVB_CONTAINER', 'container_table', None, 'dvb-tv-anytime'),
                    ('DVB_MPE_FEC', 'MPE_FEC', None, 'dvb-data'),
                    ('DVB_MPE_IFEC', 'MPE_IFEC', None, 'dvb-mpe-ifec')]
        for name, table, descriptor_name, reference in fixtures:
            with self.subTest(fixture=name):
                fixture = EXPANDED_FIXTURES[name]
                _, details = self.analyze([name], fixture['standard'], [fixture['pid']])
                native = self.assert_fixture_native(details, name, table)
                node = self.tree_nodes(native, descriptor_name)[0] if descriptor_name else native
                self.assertIn(reference, [r['id'] for r in node['references']])
                self.assertTrue(all(r['url'].startswith('https://') for r in node['references']))
        _, details = self.analyze(['DTMB_DRM_PMT'], 'dvb', [0x100])
        self.assertNotIn('dtmb-drm', [r['id'] for d in details[0]['descriptors'] for r in d['references']])
        _, details = self.analyze(['ASTRA_SGT'], 'dvb', [0x176])
        self.assertEqual(self.assert_fixture_native(details, 'ASTRA_SGT', 'SGT')['references'], [])


    def test_avs3_registration_dispatch_never_mislabels_unrelated_family(self):
        _, details = self.analyze(['MPEG_AVS3_REGISTRATION_PMT'], 'dvb', [0x100])
        pmt = self.assert_fixture_native(details, 'MPEG_AVS3_REGISTRATION_PMT', 'PMT')
        # Depending on registry resolution, exact AVS3 decoding or explicitly
        # warned raw fallback is safe. An unrelated ISDB label never is.
        self.assertFalse(self.tree_nodes(pmt, 'reference_descriptor'))
        self.assertNotIn('<reference_descriptor', details[0]['tsduck_xml'])
        flat = next(d for d in details[0]['descriptors'] if d['tag'] == 0xd1)
        self.assertEqual(flat['registration_ids'], [0x41565356])
        self.assertEqual(flat['pds'], 0)
        self.assertEqual(flat['raw'], 'D10820409A67010101FF')
        name = flat['native']['name']
        self.assertIn(name, ['AVS3_video_descriptor', 'generic_descriptor'])
        nodes = self.tree_nodes(pmt, name)
        self.assertEqual(len(nodes), 1)
        if name == 'generic_descriptor':
            self.assertFalse(self.tree_nodes(pmt, 'AVS3_video_descriptor'))
            self.assertEqual(self.number(nodes[0]['attributes']['tag']), 0xd1)
            self.assertEqual(''.join(nodes[0]['text'].split()), '20409A67010101FF')
            self.assertFalse(flat['native_decoded'])
            self.assertTrue(flat['native_decode_warning'])
            self.assertEqual(flat['references'], [])
            self.assertTrue(details[0]['native_xml_guarded'])
            self.assertTrue(details[0]['native_decode_warnings'])
        else:
            self.assertTrue(flat['native_decoded'])
            self.assertFalse(self.tree_nodes(pmt, 'generic_descriptor'))
            for node in [nodes[0], flat['native']]:
                fields = node['attributes']
                self.assertEqual(self.number(fields['profile_id']), 0x20)
                self.assertEqual(self.number(fields['level_id']), 0x40)
                self.assertEqual(fields['multiple_frame_rate_flag'], 'true')
                self.assertEqual(self.number(fields['frame_rate_code']), 3)
                self.assertEqual(self.number(fields['sample_precision']), 2)
                self.assertEqual(self.number(fields['colour_primaries']), 1)

    def test_avs3_private_pds_decodes_without_leaking_to_sibling_or_session(self):
        _, details = self.analyze(['MPEG_AVS3_PDS_PMT'], 'dvb', [0x100])
        pmt = self.assert_fixture_native(details, 'MPEG_AVS3_PDS_PMT', 'PMT')
        avs = self.tree_nodes(pmt, 'AVS3_video_descriptor')
        self.assertEqual(len(avs), 1)
        fields = avs[0]['attributes']
        self.assertEqual(self.number(fields['profile_id']), 0x20)
        self.assertEqual(self.number(fields['level_id']), 0x40)
        self.assertEqual(fields['multiple_frame_rate_flag'], 'true')
        self.assertEqual(self.number(fields['frame_rate_code']), 3)
        self.assertEqual(self.number(fields['sample_precision']), 2)
        self.assertEqual(self.number(fields['colour_primaries']), 1)
        flat = [d for d in details[0]['descriptors'] if d['tag'] == 0xd1]
        self.assertEqual([d['pds'] for d in flat], [0x41565356, 0])
        self.assertEqual([d['registration_ids'] for d in flat], [[], []])
        self.assertEqual([d['native']['name'] for d in flat], ['AVS3_video_descriptor', 'generic_descriptor'])
        self.assertEqual([d['native_decoded'] for d in flat], [True, False])
        self.assertFalse(self.tree_nodes(pmt, 'reference_descriptor'))
        raw_avs = bytes.fromhex(flat[0]['raw'])
        raw = section(2, 101, 0, word(0xe201) + word(0xf000) +
                      b'\x06' + word(0xe201) + word(0xf000 | len(raw_avs)) + raw_avs)
        _, details = self.analyze_packets(self.packetize(0x100, raw), 'dvb', [0x100])
        self.assertEqual(details[0]['raw_hex'], raw.hex().upper())
        flat = details[0]['descriptors'][0]
        self.assertEqual(flat['pds'], 0)
        self.assertEqual(flat['registration_ids'], [])
        self.assertFalse(flat['native_decoded'])
        self.assertEqual(flat['native']['name'], 'generic_descriptor')
        self.assertFalse(self.tree_nodes(details[0]['native_table'], 'reference_descriptor'))

    def test_standards_choice_is_validated(self):
        with self.assertRaises(RuntimeError):
            self.analyze(['BIT'], 'invented-standard')

if __name__ == '__main__':
    unittest.main(verbosity=2)
