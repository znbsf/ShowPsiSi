"""Independent synthetic J.94 (10/2016) Annex B wire vectors through real core.

No SDK serializer, receiver actions, full map assembly or current SCTE65 claim.
The official source/hash and edition boundary are in CABLE_OOB_INPUT_DESIGN.md.
"""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from core_client import Core
from make_fixture import crc, word, descriptor
import test_protocol_coverage as protocols


def section(tid, body, flags=0x30):
    length = len(body) + 4
    raw = bytes([tid, flags | (length >> 8), length & 255]) + body
    return raw + crc(raw).to_bytes(4, 'big')


def nit(subtype=1, first=1, records=None, tail=b'', protocol=0):
    if records is None:
        # B.6.1.1: two 6 MHz spaced carriers starting at 450 MHz, 125 kHz units.
        records = [b'\x02' + word(0x8000 | 48) + word(0x8000 | 3600) + b'\0']
    return section(0xc2, bytes([protocol, first, len(records), subtype]) + b''.join(records) + tail)


def svct(subtype, body, vct=42, tail=b''):
    return section(0xc4, bytes([0, subtype]) + word(vct) + body + tail)


def sns_record(identity=100, text=b'\x00\x04News', application=False, descriptors=()):
    return bytes([0x80 if application else 0]) + word(identity) + bytes([len(text)]) + text + bytes([len(descriptors)]) + b''.join(descriptors)


def ntt(records=None, language=b'eng', tail=b'', subtype=6):
    if records is None:
        records = [sns_record()]
    return section(0xc3, b'\0' + language + bytes([subtype, len(records)]) + b''.join(records) + tail)


def stt(time=0, offset=0, tail=b''):
    return section(0xc5, bytes(2) + time.to_bytes(4, 'big') + bytes([offset]) + tail)


def revision_descriptor(version=0, number=0, last=0, extra=b'', reserved=0xe0):
    return descriptor(0x93,bytes([reserved|version,number,last])+extra)


class CableOobTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='showpsisi-j94-')
        self.core = Core()

    def tearDown(self):
        self.core.close()
        self.temp.cleanup()

    def scan(self, sections, standard='j94-system-b', pid=0x1ffc, extra=False):
        packets, counter = [], 0
        for raw in sections:
            added = protocols.ProtocolCoverageTests.packetize(pid, raw, counter)
            counter = (counter + len(added)) & 15
            packets.extend(added)
        path = Path(self.temp.name) / 'j94.ts'
        path.write_bytes(b''.join(packets))
        args = {'path': str(path), 'standards': standard}
        if extra:
            args['extra_pids'] = [pid]
        state = self.core.call('analyze', args)
        return state, [self.core.call('inspect', {'id': row['id']}) for row in state['tables']]

    def decoded(self, raw):
        state, details = self.scan([raw])
        self.assertEqual(len(details), 1)
        d = details[0]
        self.assertTrue(d['valid'])
        self.assertEqual(d['crc']['status'], 'valid')
        self.assertEqual(d['raw_hex'], raw.hex().upper())
        self.assertEqual(d['table_decode_category'], 'decoded')
        self.assertFalse(d['table_decoder_registered'])
        self.assertIn('J.94', d['application_decoder'])
        self.assertEqual(d['native_decode_status'], 'application J.94 section decoder')
        self.assertIsNone(d['section_native_text'])
        self.assertIsNone(d['tsduck_xml'])
        self.assertTrue(d['native_xml_guarded'])
        self.assertFalse(d['merged']['complete'])
        self.assertEqual([r['id'] for r in d['references']], ['j94-system-b'])
        self.assertFalse(d['fields']['j94_system_b']['map_assembled'])
        self.assertEqual(state['services'], [])
        return d

    def test_nit_cds_discovery_units_sources_and_raw(self):
        raw = nit(tail=descriptor(0x99, b'opaque'))
        d = self.decoded(raw)
        f = d['fields']['j94_system_b']['fields']
        self.assertEqual(f['subtype_name'], 'CDS')
        r = f['records'][0]
        self.assertEqual((r['first_carrier_index'], r['number_of_carriers']), (1, 2))
        self.assertEqual((r['first_frequency_hz'], r['spacing_hz'], r['last_frequency_hz']),
                         (450000000, 6000000, 456000000))
        self.assertEqual(raw[r['offset']], 2)
        desc = f['descriptors'][0]
        self.assertEqual(raw[desc['offset']:desc['offset']+desc['length']+2].hex().upper(), desc['raw_hex'])

    def test_context_label_does_not_promote_colliding_sdk_family_guess(self):
        for raw in (nit(), svct(1,word(1)+b'\x01\x81'), section(0xc3,b'\0eng\0\0'),section(0xc5,b'\0\0'+bytes(5))):
            state, details = self.scan([raw])
            self.assertEqual(state['standards_context'],'j94-system-b')
            self.assertEqual(state['detected_standards'],'MPEG (J.94 System B selected explicitly)')
            self.assertIsInstance(state['sdk_inferred_standards'],str)
            self.assertIn('colliding',state['standards_inference_warning'])
            self.assertTrue(details[0]['name'].startswith('J94_SystemB_'))

    def test_cds_multiple_records_and_10khz_units(self):
        r1 = b'\x03' + word(100) + word(1000) + b'\0'
        r2 = b'\x01' + word(0) + word(2000) + b'\0'
        rows = self.decoded(nit(first=4, records=[r1, r2]))['fields']['j94_system_b']['fields']['records']
        self.assertEqual([r['first_carrier_index'] for r in rows], [4, 7])
        self.assertEqual(rows[0]['last_frequency_hz'], 12000000)
        self.assertFalse(rows[1]['spacing_applicable'])

    def test_mms_codes_symbol_rate_and_record_descriptors(self):
        item = b'\x2f\x90' + (5360537).to_bytes(4, 'big') + b'\x01' + descriptor(0x88, b'\x01')
        f = self.decoded(nit(2, first=3, records=[item]))['fields']['j94_system_b']['fields']
        r = f['records'][0]
        self.assertEqual(f['subtype_name'], 'MMS')
        self.assertEqual((r['modulation_index'], r['transmission_system'], r['inner_coding_mode']), (3, 2, 15))
        self.assertEqual((r['modulation_format'], r['symbol_rate'], r['split_bitstream_mode']), (16, 5360537, True))
        self.assertEqual(r['descriptors'][0]['raw_hex'], '880101')

    def test_unsigned_frequency_and_symbol_rate_boundaries(self):
        # Valid wire maxima remain unsigned integers even above 32-bit Hz.
        item = b'\xff' + word(0xbfff) + word(0xffff) + b'\0'
        r = self.decoded(nit(records=[item]))['fields']['j94_system_b']['fields']['records'][0]
        self.assertEqual(r['last_frequency_hz'], 32767*125000+254*16383*125000)
        self.assertGreater(r['last_frequency_hz'], 2**32)
        mms = b'\x0f\x00' + (0x0fffffff).to_bytes(4,'big') + b'\0'
        r = self.decoded(nit(2, first=255, records=[mms]))['fields']['j94_system_b']['fields']['records'][0]
        self.assertEqual(r['symbol_rate'], 0x0fffffff)
        self.assertEqual(r['modulation_index'], 255)

    def test_distinct_observation_diff_does_not_fabricate_map_version(self):
        self.scan([nit(), nit(first=3)])
        diff = self.core.call('diff_snapshots', {'from_packet':0,'to_packet':1,'kind':'tables'})
        self.assertEqual(diff['summary']['tables']['added'],1)
        self.assertEqual(diff['summary']['tables']['changed'],0)
        change = diff['changes'][0]
        self.assertFalse(change['identity']['versioning_supported'])
        self.assertIsNone(change['identity']['version'])
        self.assertIn('observation_key',change['identity'])

    def test_defined_channel_map_retains_ranges_without_expansion(self):
        f = self.decoded(svct(1, word(2) + b'\x03\x82\x03\x81'))['fields']['j94_system_b']['fields']
        self.assertEqual((f['vct_id'], f['subtype_name']), (42, 'DCM'))
        self.assertEqual([(r['first_virtual_channel'], r['last_virtual_channel'], r['range_defined']) for r in f['records']],
                         [(2, 3, True), (4, 6, False), (7, 7, True)])

    def test_inverse_channel_map_keeps_zero_channel_placeholder(self):
        f = self.decoded(svct(2, word(5) + b'\x02' + word(100) + word(7) + word(101) + word(0)))['fields']['j94_system_b']['fields']
        self.assertEqual(f['subtype_name'], 'ICM')
        self.assertEqual([(r['map_index'], r['source_id'], r['virtual_channel_number']) for r in f['records']],
                         [(5, 100, 7), (6, 101, 0)])

    def test_virtual_channel_map_digital_analogue_application_and_inactive(self):
        digital = word(7) + b'\x00' + word(100) + b'\x01' + word(200) + b'\x03\x00'
        analogue = word(8) + b'\xb1' + word(300) + b'\x02\x82\x00\x00\x01' + descriptor(0x91, b'x')
        inactive = word(9) + b'\x01' + word(0) + b'\x00' + word(0) + b'\x00\x00'
        f = self.decoded(svct(0, b'\x20\x80' + (123456).to_bytes(4, 'big') + b'\x03' + digital + analogue + inactive))['fields']['j94_system_b']['fields']
        self.assertEqual((f['activation_time'], f['splice'], f['record_count']), (123456, True, 3))
        a,b,c = f['records']
        self.assertEqual((a['source_id'], a['program_number'], a['cds_reference'], a['mms_reference']), (100,200,1,3))
        self.assertEqual((b['application_id'], b['video_standard'], b['path_select'], b['scrambled']), (300,2,1,True))
        self.assertNotIn('source_id', b)
        self.assertEqual(c['program_number'], 0)
        self.assertEqual(b['descriptors'][0]['raw_hex'], '910178')

    def test_active_digital_channel_requires_mms_but_inactive_ignores_it(self):
        for program, expected in ((200, 'malformed'), (0, 'decoded')):
            raw = svct(0, bytes(6)+b'\x01'+word(7)+b'\0'+word(100)+b'\1'+word(program)+b'\0')
            with self.subTest(program=program):
                d = self.scan([raw])[1][0]
                self.assertEqual(d['fields']['j94_system_b']['decode_status'], expected)
                self.assertEqual(d['raw_hex'], raw.hex().upper())
                if program:
                    self.assertNotIn('fields', d['fields']['j94_system_b'])
                    self.assertIn('MMS reference', d['fields']['j94_system_b']['warnings'][0])
                    self.assertEqual(d['references'], [])

    def test_forbidden_long_bit_does_not_create_fake_extension_anchor(self):
        raw=bytearray(nit());raw[1]|=0x80;raw[-4:]=crc(raw[:-4]).to_bytes(4,'big')
        _,details=self.scan([bytes(raw)])
        self.assertTrue(details)
        self.assertFalse(any(a['display_path']=='table_id_extension' for a in details[0]['evidence_anchors']))
        self.assertEqual(details[0]['raw_hex'],raw.hex().upper())

    def test_short_envelope_never_claims_wire_version_or_section_number(self):
        state, details = self.scan([nit()])
        for view in [state['tables'][0], details[0]]:
            self.assertFalse(view['versioning_supported'])
            for key in ('version','section','last_section','extension','current'):
                self.assertIsNone(view[key])
            self.assertIn('short envelope', view['header_semantics'])
        self.assertFalse(any(a['display_path']=='table_id_extension' for a in details[0]['evidence_anchors']))
        group = state['table_groups'][0]
        self.assertFalse(group['versioning_supported'])
        self.assertFalse(group['selected_complete'])
        self.assertEqual(group['expected_section_numbers'], [])
        self.assertIsNone(group['version'])
        history = state['table_history'][0]
        self.assertFalse(history['versioning_supported'])
        self.assertIsNone(history['section'])
        self.assertIsNone(history['current'])

    def test_crc_failure_is_retained_but_never_decoded(self):
        raw = bytearray(nit()); raw[-1] ^= 1
        state, details = self.scan([bytes(raw)])
        d = details[0]
        self.assertFalse(d['valid'])
        self.assertEqual(d['crc']['status'], 'invalid')
        self.assertEqual(d['table_decode_category'], 'invalid_evidence')
        self.assertNotIn('native_table', d)
        self.assertNotIn('j94_system_b', d['fields'])
        self.assertEqual(d['references'], [])
        self.assertEqual(d['raw_hex'], raw.hex().upper())
        self.assertEqual(state['crc_errors'], 1)

    def test_missing_mandatory_crc_never_enters_application_parser(self):
        for tid in range(0xc2,0xc6):
            for length in range(4):
                raw = bytes([tid,0x30,length])+bytes(length)
                with self.subTest(tid=tid,length=length):
                    d = self.scan([raw])[1][0]
                    self.assertEqual(d['raw_hex'],raw.hex().upper())
                    self.assertFalse(d['valid'])
                    self.assertEqual(d['crc']['status'],'unavailable')
                    self.assertEqual(d['table_decode_category'],'invalid_evidence')
                    self.assertFalse(d['native_table_complete'])
                    self.assertNotIn('native_table',d)
                    self.assertNotIn('j94_system_b',d['fields'])
                    self.assertEqual(d['issues'][0]['code'],'j94_crc_unavailable')

    def test_context_and_fixed_pid_do_not_leak(self):
        self.decoded(nit())
        for standard in ('auto','dvb','atsc','isdb','scte'):
            state, details = self.scan([nit()], standard=standard)
            self.assertEqual(details, [], standard)
        for standard in ('auto','atsc','isdb'):
            state, details = self.scan([nit()], standard=standard, extra=True)
            self.assertEqual(len(details), 1)
            self.assertNotIn('j94_system_b', details[0]['fields'])
            self.assertNotIn('application_decoder', details[0])
            self.assertEqual(details[0]['raw_hex'], nit().hex().upper())
        state, details = self.scan([nit()], pid=0x155)
        self.assertEqual(details, [])
        self.assertEqual(self.scan([nit()], pid=0x155, extra=True)[1][0]['table_decode_category'], 'decoded')

    def test_new_protocol_and_unknown_subtypes_are_raw_only(self):
        examples = [nit(protocol=1), nit(subtype=15), svct(15,b''),
                    ntt(subtype=0), section(0xc5,b'\1\0' + bytes(5))]
        for raw in examples:
            with self.subTest(raw=raw.hex()):
                state, details = self.scan([raw])
                d = details[0]
                self.assertTrue(d['valid'])
                self.assertEqual(d['fields']['j94_system_b']['decode_status'], 'unsupported')
                self.assertNotIn('fields', d['fields']['j94_system_b'])
                self.assertEqual(d['table_decode_category'], 'unknown_or_unsupported')
                self.assertEqual(d['native_table']['name'], 'generic_short_table')
                self.assertEqual(d['references'], [])
                self.assertEqual(d['raw_hex'], raw.hex().upper())

    def test_every_payload_truncation_is_bounded_and_keeps_exact_bytes(self):
        mms = nit(2, records=[b'\x2f\x10' + (1).to_bytes(4,'big') + b'\0'])
        vcm = svct(0, bytes(6)+b'\x01'+word(1)+b'\0'+word(2)+b'\1'+word(3)+b'\1')
        for full in (nit(), mms, vcm, svct(1, word(0)+b'\x01\x81'), svct(2, word(0)+b'\x01'+word(3)+word(4)), ntt(), stt()):
            for length in range(len(full)-7):
                raw = section(full[0], full[3:3+length])
                with self.subTest(tid=full[0], length=length):
                    state, details = self.scan([raw])
                    self.assertEqual(len(details), 1)
                    d = details[0]
                    self.assertEqual(d['raw_hex'], raw.hex().upper())
                    self.assertNotEqual(d['table_decode_category'], 'decoded')
                    self.assertEqual(d['fields']['j94_system_b']['decode_status'], 'malformed')
                    self.assertNotIn('fields', d['fields']['j94_system_b'])
        self.decoded(nit())

    def test_invalid_ranges_lengths_and_zero_bits_do_not_partially_decode(self):
        cases = [nit(first=0), nit(first=255), nit(records=[b'\0'+word(1)+word(1)+b'\0']),
                 nit(records=[b'\2'+word(0)+word(1)+b'\0']), nit(tail=b'\x99\x02\x01'),
                 nit(records=[b'\1'+word(0x4001)+word(1)+b'\0']),
                 svct(1,word(4095)+b'\x01\x82'), svct(1,word(0)+b'\x01\x80'),
                 svct(2,word(4095)+b'\x02'+word(1)+word(1)+word(2)+word(2))]
        for raw in cases:
            with self.subTest(raw=raw.hex()):
                d = self.scan([raw])[1][0]
                self.assertTrue(d['valid'])
                self.assertEqual(d['fields']['j94_system_b']['decode_status'], 'malformed')
                self.assertNotIn('fields',d['fields']['j94_system_b'])
                self.assertEqual(d['raw_hex'], raw.hex().upper())

    def test_ntt_sns_language_id_names_and_opaque_descriptors(self):
        raw = ntt([sns_record(descriptors=[descriptor(0x88,b'x')]),
                   sns_record(300,b'\x3f\x04\x4e\x2d\x65\x87',True)],tail=descriptor(0xfe,b'raw'))
        f = self.decoded(raw)['fields']['j94_system_b']['fields']
        self.assertEqual((f['language_code'],f['language_code_raw'],f['language_wildcard']),('eng','656E67',False))
        self.assertEqual((f['subtype_name'],f['table_subtype'],f['record_count']),('SNS',6,2))
        a,b = f['records']
        self.assertEqual((a['source_id'],a['source_name']['text']), (100,'News'))
        self.assertNotIn('application_id',a)
        self.assertEqual((b['application_id'],b['source_name']['text']),(300,'中文'))
        self.assertNotIn('source_id',b)
        self.assertEqual(a['descriptors'][0]['raw_hex'],'880178')
        for row in f['records']:
            name = row['source_name']
            self.assertEqual(raw[name['offset']:name['offset']+name['length']].hex().upper(),name['raw_hex'])
            for segment in name['segments']:
                self.assertEqual(raw[segment['offset']:segment['offset']+len(segment['raw_hex'])//2].hex().upper(),segment['raw_hex'])
        self.assertEqual(f['descriptors'][0]['raw_hex'],'FE03726177')

    def test_ntt_wildcard_multiple_languages_and_duplicate_sources_remain_observations(self):
        sections = [ntt(language=b'\xff'*3), ntt(language=b'fra'),
                    ntt([sns_record(100,b'\0\x01A'),sns_record(100,b'\0\x01B')])]
        state, details = self.scan(sections)
        self.assertEqual(len(details),3)
        fields = [d['fields']['j94_system_b']['fields'] for d in details]
        wildcard = next(f for f in fields if f['language_wildcard'])
        self.assertIsNone(wildcard['language_code'])
        self.assertEqual(wildcard['language_code_raw'],'FFFFFF')
        duplicate = next(f for f in fields if f['record_count']==2)
        self.assertEqual([r['source_name']['text'] for r in duplicate['records']],['A','B'])
        self.assertEqual(state['services'],[])

    def test_mts_character_pages_and_mode_zero_special_mapping(self):
        text = b'\0\x08A\xe9\x98\x9a\x9c\x9d\x9e\x9f' + b'\x03\x01\xa9' + b'\x30\x01\x42'
        name = self.decoded(ntt([sns_record(text=text)]))['fields']['j94_system_b']['fields']['records'][0]['source_name']
        self.assertEqual(name['text'],'Aé‰♪←↑→↓Ωあ')
        self.assertEqual(name['text_status'],'decoded')
        self.assertEqual(name['format_effectors_ignored'],0)

    def test_mts_all_defined_pages_use_bmp_mapping(self):
        for page in [*range(7),*range(9,0x11),*range(0x20,0x28),*range(0x30,0x34)]:
            with self.subTest(page=page):
                name = self.decoded(ntt([sns_record(text=bytes([page,1,65]))]))['fields']['j94_system_b']['fields']['records'][0]['source_name']
                self.assertEqual(name['text'],chr(page*256+65))

    def test_ntt_format_effectors_are_retained_and_ignored_without_execution(self):
        text = b'\x87\0\x05<tag>\x80\xa0\x03abc\x88\x40'
        name = self.decoded(ntt([sns_record(text=text)]))['fields']['j94_system_b']['fields']['records'][0]['source_name']
        self.assertEqual(name['text'],'<tag>')
        self.assertEqual(name['format_effectors_ignored'],5)
        self.assertEqual(name['raw_hex'],text.hex().upper())
        self.assertEqual([s['mode'] for s in name['segments'] if s['kind']=='format_effector'],[0x87,0x80,0xa0,0x88,0x40])
        self.assertEqual([s['text_status'] for s in name['segments'] if s['kind']=='format_effector'],['ignored_in_NTT']*5)

    def test_unknown_pages_and_reserved_mode_zero_bytes_withhold_whole_text(self):
        for text in (b'\0\x01A\x07\x01B\0\x01C',b'\0\x03A\x80C', b'\x3e\x01x'):
            with self.subTest(text=text.hex()):
                d = self.decoded(ntt([sns_record(text=text)]))
                name = d['fields']['j94_system_b']['fields']['records'][0]['source_name']
                self.assertIsNone(name['text'])
                self.assertEqual(name['text_status'],'unsupported')
                self.assertTrue(d['fields']['j94_system_b']['warnings'])
                self.assertEqual(name['raw_hex'],text.hex().upper())

    def test_mts_bmp_surrogates_are_invalid_not_utf8_or_supplementary_claims(self):
        for text in (b'\x3f\x02\xd8\x00', b'\x3f\x04\xd8\x3d\xde\x00'):
            d = self.decoded(ntt([sns_record(text=text)]))
            name = d['fields']['j94_system_b']['fields']['records'][0]['source_name']
            self.assertIsNone(name['text'])
            self.assertEqual(name['text_status'],'invalid_encoding')
            self.assertEqual(name['segments'][0]['text_status'],'invalid_encoding')
            self.assertEqual(name['raw_hex'],text.hex().upper())

    def test_ntt_nested_lengths_zero_bits_and_odd_bmp_do_not_partially_decode(self):
        cases = [ntt(records=[]),ntt([sns_record(text=b'')]),ntt([sns_record(text=b'\0')]),
                 ntt([sns_record(text=b'\0\x02A')]),ntt([sns_record(text=b'\x3f\x01A')]),
                 ntt([sns_record(text=b'\xa0')]),ntt([sns_record(text=b'\xa0\x02A')]),
                 ntt([bytes([1])+sns_record()[1:]]),ntt(subtype=0x16),
                 ntt([sns_record(descriptors=[b'\x99\x02x'])]),ntt(tail=b'\x99\x02x'),
                 section(0xc5,b'\0\x01'+bytes(5)), stt(tail=b'\x99\x02x')]
        for raw in cases:
            with self.subTest(raw=raw.hex()):
                d = self.scan([raw])[1][0]
                self.assertTrue(d['valid'])
                self.assertEqual(d['fields']['j94_system_b']['decode_status'],'malformed')
                self.assertNotIn('fields',d['fields']['j94_system_b'])
                self.assertEqual(d['raw_hex'],raw.hex().upper())
                self.assertEqual(d['references'],[])

    def test_ntt_maximum_name_and_many_small_segments_remain_bounded(self):
        for text, expected in ((b'\0\xfd'+b'A'*253,'A'*253),(b'\x80'*255,'')):
            name = self.decoded(ntt([sns_record(text=text)]))['fields']['j94_system_b']['fields']['records'][0]['source_name']
            self.assertEqual(name['length'],255)
            self.assertEqual(name['text'],expected)
            self.assertLessEqual(len(name['segments']),255)
        raw = ntt([sns_record(i,b'\x80') for i in range(160)])
        f = self.decoded(raw)['fields']['j94_system_b']['fields']
        self.assertEqual(f['record_count'],160)
        self.assertEqual(f['records'][-1]['source_id'],159)

    def test_stt_utc_zero_offset_and_gps_offset_are_section_local_signed_arithmetic(self):
        for time, offset in ((0,0),(123456,0),(123456,18),(0,255),(0xffffffff,255)):
            with self.subTest(time=time,offset=offset):
                f = self.decoded(stt(time,offset,descriptor(0x99,b'x')))['fields']['j94_system_b']['fields']
                self.assertEqual((f['system_time'],f['gps_utc_offset']),(time,offset))
                self.assertEqual(f['utc_seconds_since_gps_epoch'],time-offset)
                self.assertEqual(f['utc_unix_seconds'],315964800+time-offset)
                self.assertEqual(f['signalled_time_basis'].split()[0],'GPS' if offset else 'UTC')
                self.assertIn('no clock setting',f['time_scope'])
                self.assertEqual(f['descriptors'][0]['raw_hex'],'990178')

    def cable(self, **args):
        return self.core.call('query_cable_oob',args)

    def test_revision_descriptor_is_scoped_and_preserves_future_trailing_bytes(self):
        raw = nit(tail=revision_descriptor(31,0,0,b'future',reserved=0))
        d = self.decoded(raw)
        rev = d['fields']['j94_system_b']['revision_detection']
        self.assertEqual(rev['status'],'valid')
        self.assertEqual((rev['selected']['table_version_number'],rev['selected']['section_number'],rev['selected']['last_section_number']),(31,0,0))
        self.assertEqual(rev['selected']['extension_hex'],b'future'.hex().upper())
        self.assertIsNone(d['version'])
        self.assertIsNone(d['section'])
        self.assertFalse(d['versioning_supported'])
        group = self.cable()['groups'][0]
        self.assertEqual(group['status'],'complete_subtable')
        self.assertFalse(group['network_lineup_complete'])

    def test_revision_tag_in_record_or_stt_loop_never_versions_the_table(self):
        nested = revision_descriptor()
        cds = b'\x01'+word(1)+word(1)+b'\x01'+nested
        vcm = svct(0,b'\x20\0'+bytes(4)+b'\x01'+word(1)+b'\0'+word(2)+b'\x01'+word(3)+b'\x01\x01'+nested)
        for raw in (nit(records=[cds]),ntt([sns_record(descriptors=[nested])]),vcm):
            d = self.decoded(raw)
            self.assertEqual(d['fields']['j94_system_b']['revision_detection']['status'],'absent')
            self.assertEqual(self.cable()['groups'][0]['status'],'unversioned')
        d = self.decoded(stt(tail=nested))
        self.assertNotIn('revision_detection',d['fields']['j94_system_b'])
        self.assertEqual(self.cable()['groups'],[])

    def test_competing_duplicate_and_malformed_revision_descriptors_block_assembly(self):
        for tail,status in ((revision_descriptor()*2,'duplicate'),
                            (revision_descriptor()+revision_descriptor(1),'conflicting'),
                            (descriptor(0x93,b''),'malformed'),(descriptor(0x93,b'\0'),'malformed'),
                            (descriptor(0x93,b'\0\0'),'malformed'),(revision_descriptor(0,2,1),'malformed')):
            with self.subTest(status=status,tail=tail.hex()):
                raw = nit(tail=tail);d = self.decoded(raw)
                self.assertEqual(d['fields']['j94_system_b']['revision_detection']['status'],status)
                group = self.cable()['groups'][0]
                self.assertEqual(group['status'],'revision_ambiguous')
                self.assertEqual(group['records'],[])
                self.assertFalse(group['subtable_complete'])
                self.assertEqual(d['raw_hex'],raw.hex().upper())

    def test_profile_one_observations_never_become_an_implicitly_selected_map(self):
        self.scan([nit(),nit(first=3)])
        group = self.cable()['groups'][0]
        self.assertEqual(group['status'],'unversioned')
        self.assertEqual(len(group['observations']),2)
        self.assertEqual(group['records'],[])
        self.assertIsNone(group['revision_detection'])

    def test_out_of_order_revised_subtable_assembly_preserves_record_provenance(self):
        raw1 = nit(first=3,tail=revision_descriptor(7,1,1))
        raw0 = nit(tail=revision_descriptor(7,0,1))
        state,details = self.scan([raw1,raw0])
        out = self.cable(analysis_revision=state['revision'],at_packet=1)
        self.assertEqual(out['at_packet'],1)
        group = out['groups'][0]
        self.assertTrue(group['sections_complete'])
        self.assertTrue(group['subtable_complete'])
        self.assertEqual([r['first_carrier_index'] for r in group['records']],[1,3])
        raw_by_id = {d['id']:bytes.fromhex(d['raw_hex']) for d in details}
        for record in group['records']:
            src = record['source'];raw=raw_by_id[src['section_id']]
            self.assertEqual(src['analysis_revision'],state['revision'])
            self.assertEqual(src['at_packet'],1)
            self.assertEqual(raw[src['record_offset']],record['number_of_carriers'])
            self.assertEqual(raw[src['revision_descriptor_offset']],0x93)
        self.assertEqual(group['missing_section_numbers'],[])

    def test_revised_missing_sections_and_cutoffs_do_not_borrow_future_evidence(self):
        state,_ = self.scan([nit(first=3,tail=revision_descriptor(0,1,2)),nit(tail=revision_descriptor(0,0,2))])
        first = self.cable(at_packet=0)['groups'][0]
        self.assertEqual(first['missing_section_numbers'],[0,2])
        self.assertEqual([r['first_carrier_index'] for r in first['records']],[3])
        final = self.cable()['groups'][0]
        self.assertEqual(final['missing_section_numbers'],[2])
        self.assertEqual(final['status'],'incomplete')
        self.assertFalse(final['sections_complete'])

    def test_old_complete_to_new_incomplete_revision_has_no_complete_fallback(self):
        self.scan([nit(tail=revision_descriptor(31,0,1)),nit(first=3,tail=revision_descriptor(31,1,1)),
                   nit(first=5,tail=revision_descriptor(0,0,1))])
        self.assertTrue(self.cable(at_packet=1)['groups'][0]['subtable_complete'])
        group = self.cable()['groups'][0]
        self.assertEqual(group['revision_detection']['table_version_number'],0)
        self.assertEqual(group['missing_section_numbers'],[1])
        self.assertEqual([r['first_carrier_index'] for r in group['records']],[5])

    def test_reused_revision_cannot_resurrect_siblings_from_an_earlier_cycle(self):
        zero = nit(tail=revision_descriptor(0,0,1))
        self.scan([zero,nit(first=3,tail=revision_descriptor(0,1,1)),nit(first=5,tail=revision_descriptor(1,0,1)),zero])
        group = self.cable()['groups'][0]
        self.assertEqual(group['missing_section_numbers'],[1])
        self.assertEqual(len(group['records']),1)
        self.assertEqual(group['sources'][0]['last_observed_packet'],3)
        self.assertEqual(group['generation_barrier_receive_order'],3)

    def test_same_packet_receive_order_keeps_reused_revision_barrier(self):
        zero = nit(tail=revision_descriptor(0,0,1))
        raws = [zero,nit(first=3,tail=revision_descriptor(0,1,1)),nit(first=5,tail=revision_descriptor(1,0,1)),zero]
        payload=b'\0'+b''.join(raws)
        self.assertLessEqual(len(payload),184)
        packet=bytes([0x47,0x40|0x1f,0xfc,0x10])+payload+b'\xff'*(184-len(payload))
        path=Path(self.temp.name)/'same-packet.ts';path.write_bytes(packet)
        self.core.call('analyze',{'path':str(path),'standards':'j94-system-b'})
        group=self.cable(at_packet=0)['groups'][0]
        self.assertEqual(group['missing_section_numbers'],[1])
        self.assertEqual(group['sources'][0]['receive_order'],4)
        self.assertEqual(group['generation_barrier_receive_order'],3)

    def test_same_revision_slot_with_different_raw_bytes_stays_conflicted(self):
        self.scan([nit(tail=revision_descriptor()),nit(first=3,tail=revision_descriptor())])
        group=self.cable()['groups'][0]
        self.assertEqual(group['status'],'conflict')
        self.assertFalse(group['sections_complete'])
        self.assertEqual(len(group['sources']),2)
        self.assertEqual(group['records'],[])
        self.assertEqual(group['diagnostics'][0]['code'],'conflicting_section_slot')

    def test_ambiguous_or_missing_newest_revision_blocks_older_complete_generation(self):
        for tail in (b'',revision_descriptor()*2):
            zero=nit(tail=revision_descriptor(0,0,1))
            self.scan([zero,nit(first=3,tail=revision_descriptor(0,1,1)),nit(first=5,tail=tail),zero])
            self.assertEqual(self.cable(at_packet=2)['groups'][0]['records'],[])
            final=self.cable()['groups'][0]
            self.assertEqual(final['missing_section_numbers'],[1])
            self.assertEqual(final['generation_barrier_receive_order'],3)

    def test_crc_invalid_revision_does_not_select_or_complete_a_generation(self):
        bad=bytearray(nit(first=3,tail=revision_descriptor(1,1,1)));bad[-1]^=1
        state,details=self.scan([nit(tail=revision_descriptor()),bytes(bad)])
        result=self.cable();group=result['groups'][0]
        self.assertTrue(group['subtable_complete'])
        self.assertEqual(group['revision_detection']['table_version_number'],0)
        self.assertEqual(len(result['excluded_evidence']),1)
        self.assertEqual(result['excluded_evidence'][0]['reason'],'invalid_integrity')
        self.assertIn(bytes(bad).hex().upper(),[d['raw_hex'] for d in details])

    def test_carrier_modulation_and_dcm_overlaps_are_conflicts_not_overwrites(self):
        mms=lambda first,number:nit(2,first,[b'\x2f\x10'+(1).to_bytes(4,'big')+b'\0'],tail=revision_descriptor(0,number,1))
        cases=[(nit(tail=revision_descriptor(0,0,1)),nit(first=2,tail=revision_descriptor(0,1,1))),
               (mms(255,0),mms(255,1)),
               (svct(1,word(0)+b'\x01\x82',tail=revision_descriptor(0,0,1)),svct(1,word(1)+b'\x01\x82',tail=revision_descriptor(0,1,1)))]
        for raws in cases:
            self.scan(raws);group=self.cable()['groups'][0]
            self.assertTrue(group['sections_complete'])
            self.assertFalse(group['subtable_complete'])
            self.assertEqual(group['status'],'conflict')
            self.assertTrue(any(x['code']=='overlapping_index_range' for x in group['diagnostics']))
            self.assertEqual(len(group['records']),2)

    def test_index_gaps_are_observed_coverage_not_missing_section_guesses(self):
        self.scan([nit(tail=revision_descriptor(0,0,1)),nit(first=5,tail=revision_descriptor(0,1,1))])
        group=self.cable()['groups'][0]
        self.assertTrue(group['subtable_complete'])
        self.assertEqual(group['range_coverage']['gaps_between_observed_ranges'],[{'first':3,'last':4}])
        self.assertFalse(group['range_coverage']['gaps_are_proof_of_missing_transmission'])
        self.assertEqual(group['range_coverage']['outside_observed_bounds'],'unknown')

    def test_nit_first_index_plus_record_count_overflow_is_excluded_raw_evidence(self):
        record=b'\x2f\x10'+(1).to_bytes(4,'big')+b'\0'
        for raw in (nit(first=255,tail=revision_descriptor()),nit(2,255,[record,record],tail=revision_descriptor())):
            self.scan([raw]);out=self.cable()
            self.assertEqual(out['groups'],[])
            self.assertEqual(out['excluded_evidence'][0]['reason'],'unsupported_or_malformed_payload')
        self.scan([nit(2,254,[record,record],tail=revision_descriptor())])
        self.assertEqual([r['modulation_index'] for r in self.cable()['groups'][0]['records']],[254,255])

    def test_name_keys_and_inverse_map_indexes_remain_conflicted(self):
        self.scan([ntt([sns_record(100,b'\0\x01A'),sns_record(100,b'\0\x01B')],tail=revision_descriptor())])
        group=self.cable()['groups'][0]
        self.assertEqual(group['status'],'conflict')
        self.assertEqual([r['source_name']['text'] for r in group['records']],['A','B'])
        self.scan([svct(2,word(1)+b'\x01'+word(100)+word(7),tail=revision_descriptor(0,0,1)),
                   svct(2,word(1)+b'\x01'+word(101)+word(8),tail=revision_descriptor(0,1,1))])
        self.assertEqual(self.cable()['groups'][0]['status'],'conflict')

    def test_vcm_activation_times_are_preserved_not_executed_or_flattened(self):
        def vcm(time,number):
            return svct(0,b'\0\0'+time.to_bytes(4,'big')+b'\x01'+word(7)+b'\0'+word(100)+b'\x01'+word(200)+b'\x01',tail=revision_descriptor(0,number,1))
        self.scan([vcm(100,0),vcm(200,1)])
        group=self.cable()['groups'][0]
        self.assertTrue(group['subtable_complete'])
        self.assertEqual([r['activation_time'] for r in group['records']],[100,200])
        self.assertFalse(group['network_lineup_complete'])
        self.scan([vcm(100,0),vcm(100,1)])
        self.assertEqual(self.cable()['groups'][0]['status'],'conflict')

    def test_repetitions_of_same_section_do_not_become_conflicting_slots(self):
        raw=nit(tail=revision_descriptor());self.scan([raw,raw])
        group=self.cable()['groups'][0]
        self.assertTrue(group['subtable_complete'])
        self.assertEqual(len(group['records']),1)
        self.assertEqual(group['sources'][0]['occurrences'],2)

    def test_group_identity_and_pagination_bind_language_vct_revision_and_cutoff(self):
        state,_=self.scan([ntt(language=b'eng',tail=revision_descriptor()),ntt(language=b'fra',tail=revision_descriptor()),
                          svct(1,word(1)+b'\x01\x81',vct=42,tail=revision_descriptor()),
                          svct(1,word(1)+b'\x01\x81',vct=43,tail=revision_descriptor())])
        first=self.cable(limit=2)
        self.assertEqual(first['total_groups'],4)
        self.assertEqual(first['next_offset'],2)
        with self.assertRaises(RuntimeError):self.cable(offset=2,limit=2)
        second=self.cable(offset=2,limit=2,analysis_revision=first['analysis_revision'],at_packet=first['at_packet'])
        self.assertIsNone(second['next_offset'])
        groups=first['groups']+second['groups'];self.assertEqual(len({g['id'] for g in groups}),4)
        for g in groups:self.assertEqual((g['analysis_revision'],g['at_packet']),(state['revision'],3))

    def test_query_lifecycle_stale_pages_and_invalid_arguments_fail_closed(self):
        with self.assertRaises(RuntimeError):self.cable()
        state,_=self.scan([nit(tail=revision_descriptor())])
        for args in ({'limit':0},{'limit':101},{'offset':513},{'offset':-1},{'limit':True},
                     {'at_packet':-1},{'at_packet':1},{'at_packet':0.5},{'analysis_revision':True}):
            with self.subTest(args=args),self.assertRaises(RuntimeError):self.cable(**args)
        self.scan([nit(tail=revision_descriptor(1))])
        with self.assertRaises(RuntimeError):self.cable(analysis_revision=state['revision'])
        self.scan([nit()],standard='dvb')
        with self.assertRaises(RuntimeError):self.cable()

    def test_same_table_identity_on_distinct_pids_never_joins_sections(self):
        packets=[]
        for pid,raw in ((0x1ffc,nit(tail=revision_descriptor(0,0,1))),
                        (0x155,nit(first=3,tail=revision_descriptor(0,1,1)))):
            packets.extend(protocols.ProtocolCoverageTests.packetize(pid,raw))
        path=Path(self.temp.name)/'two-pids.ts';path.write_bytes(b''.join(packets))
        self.core.call('analyze',{'path':str(path),'standards':'j94-system-b','extra_pids':[0x155]})
        out=self.cable();self.assertEqual(out['total_groups'],2)
        self.assertEqual({g['identity']['pid'] for g in out['groups']},{0x1ffc,0x155})
        self.assertFalse(any(g['subtable_complete'] for g in out['groups']))
        self.assertEqual(sorted(g['missing_section_numbers'] for g in out['groups']),[[0],[1]])

    def test_conflicting_last_numbers_do_not_combine_or_reuse_old_sections(self):
        self.scan([nit(tail=revision_descriptor(0,0,1)),nit(first=3,tail=revision_descriptor(0,1,1)),
                   nit(first=5,tail=revision_descriptor(0,0,2))])
        group=self.cable()['groups'][0]
        self.assertEqual(group['revision_detection']['last_section_number'],2)
        self.assertEqual(group['missing_section_numbers'],[1,2])
        self.assertEqual([r['first_carrier_index'] for r in group['records']],[5])

    def test_group_and_record_resource_limits_keep_raw_inspection_available(self):
        raws=[ntt(language=bytes([65+i//676,65+(i//26)%26,65+i%26]),tail=revision_descriptor()) for i in range(513)]
        state,_=self.scan(raws)
        with self.assertRaisesRegex(RuntimeError,'group limit'):self.cable()
        self.assertEqual(self.core.call('inspect',{'id':state['tables'][0]['id']})['raw_hex'],raws[0].hex().upper())
        raws=[ntt([sns_record(i*160+j,b'\x80') for j in range(160)],tail=revision_descriptor(0,i,51)) for i in range(52)]
        self.scan(raws)
        with self.assertRaisesRegex(RuntimeError,'assembled-record limit'):self.cable()

    def test_1024_byte_limit_and_oversized_descriptor_work_are_bounded(self):
        base = b'\0\1\0\1' # NIT no records, descriptors consume remaining section.
        tail = descriptor(0x99, bytes(255))*3 + descriptor(0x99,bytes(240))
        exact = section(0xc2, base+tail)
        self.assertEqual(len(exact), 1024)
        self.decoded(exact)
        oversized = section(0xc2,base+tail+descriptor(0x99,b''))
        d = self.scan([oversized])[1][0]
        self.assertEqual(d['fields']['j94_system_b']['decode_status'], 'malformed')
        self.assertNotIn('fields', d['fields']['j94_system_b'])

    def test_variants_are_retained_without_latest_map_guess_and_cutoffs_hold(self):
        first, second = nit(), nit(first=3)
        state, details = self.scan([first,second,first])
        self.assertEqual(len(details), 2)
        self.assertEqual(sorted(d['count'] for d in details), [1,2])
        self.assertTrue(all(not g['selected_complete'] for g in state['table_groups']))
        earlier = self.core.call('query', {'at_packet': 0})
        self.assertEqual(len(earlier['tables']), 1)
        new = next(d for d in details if d['raw_hex']==second.hex().upper())
        with self.assertRaisesRegex(RuntimeError, 'not observed'):
            self.core.call('inspect', {'id':new['id'],'at_packet':0})
        self.assertEqual(len(self.scan([second])[1]),1)

    def test_export_refuses_undefined_map_selection_without_creating_file(self):
        self.decoded(nit())
        for format in ('ts','bin'):
            path = Path(self.temp.name)/('out.'+format)
            with self.assertRaisesRegex(RuntimeError, 'J.94 snapshot export is unsupported'):
                self.core.call('export', {'path':str(path),'format':format})
            self.assertFalse(path.exists())
            self.assertFalse(Path(str(path)+'.manifest.json').exists())


if __name__ == '__main__':
    unittest.main()
