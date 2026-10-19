"""Measured SCTE18/35 section inspection through the real JSONL engine.

Synthetic 3.45-4798 vectors do not establish receiver/splicer conformance,
encrypted-message support, SCTE35-2, SCTE65 or real OOB input support.
"""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from core_client import Core
from make_fixture import crc, descriptor, section, word

FIXTURE_ROOT = ROOT / 'tests/fixtures/scte345'
MANIFEST = json.loads((FIXTURE_ROOT / 'manifest.json').read_text(encoding='utf-8'))


def packetize(pid, raw):
    packets, first, cc = [], True, 0
    while raw:
        count = 183 if first else 184
        part, raw = raw[:count], raw[count:]
        payload = (b'\0' if first else b'') + part
        packets.append(bytes([0x47, (pid >> 8) | (0x40 if first else 0),
                              pid & 255, 0x10 | cc]) + payload + b'\xff' * (184 - len(payload)))
        first, cc = False, (cc + 1) & 15
    return b''.join(packets)


def nodes(tree, name):
    result = [tree] if tree.get('name') == name else []
    for child in tree.get('children', []):
        result.extend(nodes(child, name))
    return result


def number(value):
    return int(value.replace(',', ''), 0)


def fixture(name):
    return bytes.fromhex(MANIFEST['fixtures'][name]['hex'])


def repair_crc(raw):
    raw = bytearray(raw)
    raw[-4:] = crc(raw[:-4]).to_bytes(4, 'big')
    return bytes(raw)


class ScteExtensionsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='showpsisi-scte-')
        self.core = Core()

    def tearDown(self):
        self.core.close()
        self.temp.cleanup()

    def analyze(self, raw, pid=0x152, standard='scte', extra=True, prefix=b''):
        path = Path(self.temp.name) / 'synthetic.ts'
        path.write_bytes(prefix + packetize(pid, raw))
        state = self.core.call('analyze', {'path': str(path), 'standards': standard,
                                         'extra_pids': [pid] if extra else []})
        details = [self.core.call('inspect', {'id': table['id']}) for table in state['tables']]
        return state, details

    def decoded(self, name, **kwargs):
        raw = fixture(name)
        state, details = self.analyze(raw, **kwargs)
        matches = [d for d in details if d['raw_hex'] == raw.hex().upper()]
        self.assertEqual(len(matches), 1, f'{name}: exact section missing from {state["tables"]}')
        detail = matches[0]
        self.assertTrue(detail['valid'])
        self.assertTrue(detail['native_table_complete'])
        self.assertEqual(detail['table_decode_category'], 'decoded')
        self.assertEqual(detail['native_decode_status'], 'native TSDuck decoder')
        expected = 'cable_emergency_alert_table' if name == 'eas' else 'splice_information_table'
        self.assertEqual(detail['native_table']['name'], expected)
        self.assertIn('<' + expected, detail['tsduck_xml'])
        self.assertEqual(state['crc_errors'], 0)
        self.assertEqual(state['demux']['discontinuities'], 0)
        return detail

    def test_fixture_source_binary_hashes_and_crc(self):
        self.assertEqual(MANIFEST['generator'], 'tstabcomp: TSDuck - The MPEG Transport Stream Toolkit - version 3.45-4798')
        self.assertEqual(len(MANIFEST['fixtures']), 11)
        for name, entry in MANIFEST['fixtures'].items():
            with self.subTest(name=name):
                xml = (FIXTURE_ROOT / entry['xml']).read_text(encoding='utf-8').encode('utf-8')
                raw = fixture(name)
                self.assertEqual(hashlib.sha256(xml).hexdigest(), entry['xml_sha256'])
                self.assertEqual(hashlib.sha256(raw).hexdigest(), entry['sha256'])
                self.assertEqual(crc(raw), 0)
                self.assertEqual(((raw[1] & 15) << 8) | raw[2], len(raw) - 3)

    def test_eas_discovered_on_psip_pid_in_explicit_scte_mode(self):
        self.decoded('eas', pid=0x1ffb, extra=False)

    def test_eas_auto_and_atsc_discovery_still_work(self):
        for standard in ('auto', 'atsc'):
            with self.subTest(standard=standard):
                self.decoded('eas', pid=0x1ffb, standard=standard, extra=False)

    def test_eas_references_are_bounded_to_exact_table_descriptor_names(self):
        for standard in ('scte', 'atsc', 'auto'):
            with self.subTest(standard=standard):
                detail = self.decoded('eas', pid=0x1ffb, standard=standard)
                self.assertEqual([r['id'] for r in detail['references']], ['scte18'])
                self.assertIn('403', detail['references'][0]['access'])
                tree = detail['native_table']
                for name in ('EAS_audio_file_descriptor', 'EAS_inband_details_channel_descriptor',
                             'EAS_inband_exception_channels_descriptor'):
                    self.assertEqual([r['id'] for r in nodes(tree, name)[0]['references']], ['scte18'])
        catalog = json.loads((ROOT / 'references/standards.json').read_text(encoding='utf-8'))
        entry = next(item for item in catalog['sources'] if item['id'] == 'scte18')
        self.assertNotIn('EAS_metadata_descriptor', entry['descriptor_names'])

    def test_explicit_pid_scope_does_not_leak_between_analyses(self):
        # A synthetic/unadvertised operator PID is explicit, not auto-discovered.
        self.decoded('eas', pid=0x153, extra=True)
        state, details = self.analyze(fixture('eas'), pid=0x153, extra=False)
        self.assertEqual(state['tables'], [])
        self.assertEqual(details, [])
        state, details = self.analyze(fixture('eas'), pid=0x1ffb, standard='dvb', extra=False)
        self.assertEqual(details, [])

    def test_eas_on_1ffc_remains_explicit_transport_selection(self):
        # This is already-TS-framed input, not reception of an OOB/CableCARD link.
        self.decoded('eas', pid=0x1ffc, extra=True)
        state, details = self.analyze(fixture('eas'), pid=0x1ffc, extra=False)
        self.assertEqual(details, [])

    def test_eas_fields_text_locations_exceptions_and_descriptors(self):
        tree = self.decoded('eas', pid=0x1ffb)['native_table']
        attrs = tree['attributes']
        for key, expected in {'sequence_number': 3, 'eas_event_id': 1234,
                              'alert_priority': 11, 'alert_message_time_remaining': 30,
                              'event_duration': 15, 'details_oob_source_id': 100,
                              'audio_oob_source_id': 101, 'details_major_channel_number': 7,
                              'details_minor_channel_number': 2}.items():
            self.assertEqual(number(attrs[key]), expected)
        self.assertEqual(attrs['eas_originator_code'], 'WXR')
        self.assertEqual(attrs['eas_event_code'], 'TOR')
        self.assertEqual(attrs['event_start_time'], '2026-10-19 08:00:00')
        strings = nodes(nodes(tree, 'alert_text')[0], 'string')
        self.assertEqual({s['attributes']['language']: s['attributes']['text'] for s in strings},
                         {'eng': 'Synthetic test only', 'fra': 'Exercice synthétique'})
        self.assertEqual(nodes(tree, 'location')[0]['attributes'],
                         {'state_code': '42', 'county_subdivision': '0', 'county_code': '91'})
        exceptions = [n['attributes'] for n in tree['children'] if n['name'] == 'exception']
        self.assertEqual(len(exceptions), 2)
        self.assertEqual(exceptions[0], {'major_channel_number': '4', 'minor_channel_number': '1'})
        self.assertEqual(number(exceptions[1]['oob_source_id']), 102)
        details = nodes(tree, 'EAS_inband_details_channel_descriptor')[0]['attributes']
        self.assertEqual(number(details['details_rf_channel']), 33)
        self.assertEqual(number(details['details_program_number']), 500)
        excluded = nodes(nodes(tree, 'EAS_inband_exception_channels_descriptor')[0], 'exception')[0]['attributes']
        self.assertEqual(number(excluded['rf_channel']), 34)
        self.assertEqual(number(excluded['program_number']), 501)
        audio = nodes(nodes(tree, 'EAS_audio_file_descriptor')[0], 'file')[0]['attributes']
        self.assertEqual(audio['file_name'], 'drill.wav')
        for key, value in {'audio_format': 1, 'audio_source': 1, 'program_number': 502,
                           'carousel_id': 123, 'application_id': 456}.items():
            self.assertEqual(number(audio[key]), value)

    def test_program_splice_insert_keeps_wire_pts_and_break_duration(self):
        tree = self.decoded('insert_program')['native_table']
        self.assertEqual(number(tree['attributes']['pts_adjustment']), 90)
        insert = nodes(tree, 'splice_insert')[0]
        attrs = insert['attributes']
        for key, value in {'splice_event_id': 123, 'pts_time': 8589934500,
                           'unique_program_id': 55, 'avail_num': 2, 'avails_expected': 4}.items():
            self.assertEqual(number(attrs[key]), value)
        self.assertEqual(attrs['out_of_network'], 'true')
        self.assertEqual(attrs['splice_immediate'], 'false')
        duration = nodes(insert, 'break_duration')[0]['attributes']
        self.assertEqual(number(duration['duration']), 900000)
        self.assertEqual(duration['auto_return'], 'true')

    def test_component_splice_insert(self):
        insert = nodes(self.decoded('insert_components')['native_table'], 'splice_insert')[0]
        self.assertNotIn('pts_time', insert['attributes'])
        self.assertEqual([(number(n['attributes']['component_tag']), number(n['attributes']['pts_time']))
                          for n in nodes(insert, 'component')], [(3, 90000), (4, 90001)])

    def test_immediate_and_cancelled_splice_insert(self):
        for name, key, identity in [('insert_immediate', 'splice_immediate', 127),
                                    ('insert_cancel', 'splice_event_cancel', 125)]:
            with self.subTest(name=name):
                insert = nodes(self.decoded(name)['native_table'], 'splice_insert')[0]
                self.assertEqual(insert['attributes'][key], 'true')
                self.assertEqual(number(insert['attributes']['splice_event_id']), identity)
                self.assertNotIn('pts_time', insert['attributes'])
                self.assertEqual(nodes(insert, 'component'), [])

    def test_splice_schedule_program_components_and_cancellation(self):
        event = nodes(self.decoded('schedule')['native_table'], 'splice_event')[0]
        self.assertEqual(number(event['attributes']['splice_event_id']), 126)
        self.assertEqual(event['attributes']['utc_splice_time'], '2026-10-19 08:00:00')
        self.assertEqual(number(nodes(event, 'break_duration')[0]['attributes']['duration']), 180000)
        events = nodes(self.decoded('schedule_components')['native_table'], 'splice_event')
        self.assertEqual(len(events), 2)
        self.assertEqual([(number(n['attributes']['component_tag']), n['attributes']['utc_splice_time'])
                          for n in nodes(events[0], 'component')],
                         [(5, '2026-10-19 08:00:00'), (6, '2026-10-19 08:01:00')])
        self.assertEqual(events[1]['attributes']['splice_event_cancel'], 'true')
        self.assertNotIn('utc_splice_time', events[1]['attributes'])

    def test_null_bandwidth_and_opaque_private_command(self):
        for name, command in [('null', 'splice_null'), ('bandwidth', 'bandwidth_reservation')]:
            with self.subTest(name=name):
                self.assertEqual(len(nodes(self.decoded(name)['native_table'], command)), 1)
        command = nodes(self.decoded('private')['native_table'], 'private_command')[0]
        self.assertEqual(number(command['attributes']['identifier']), 0x11223344)
        self.assertEqual(''.join(command['text'].split()), 'DEADBEEF')

    def test_time_signal_unspecified_and_dtmf_audio_time_descriptors(self):
        tree = self.decoded('descriptors')['native_table']
        self.assertNotIn('pts_time', nodes(tree, 'time_signal')[0]['attributes'])
        dtmf = nodes(tree, 'splice_DTMF_descriptor')[0]['attributes']
        self.assertEqual(number(dtmf['preroll']), 12)
        self.assertEqual(dtmf['dtmf'], '123A')
        audio = nodes(nodes(tree, 'splice_audio_descriptor')[0], 'audio')[0]['attributes']
        self.assertEqual(audio['iso_code'], 'eng')
        for key, value in {'component_tag': 5, 'bit_stream_mode': 2, 'num_channels': 6}.items():
            self.assertEqual(number(audio[key]), value)
        self.assertEqual(audio['full_srvc_audio'], 'true')
        time = nodes(tree, 'splice_time_descriptor')[0]['attributes']
        for key, value in {'tai_seconds': 123456789, 'tai_ns': 123456000, 'utc_offset': 37}.items():
            self.assertEqual(number(time[key]), value)

    def test_pmt_discovery_covers_new_splice_command(self):
        pat = section(0, 1, 0, word(101) + word(0xe100))
        reg = descriptor(5, b'CUEI')
        pmt = section(2, 101, 0, word(0xffff) + word(0xf000 | len(reg)) + reg +
                      b'\x86' + word(0xe152) + word(0xf000))
        self.decoded('insert_program', extra=False, prefix=packetize(0, pat) + packetize(0x100, pmt))

    def assert_fallback(self, raw, generic):
        state, details = self.analyze(raw)
        self.assertEqual(len(details), 1)
        d = details[0]
        self.assertTrue(d['valid'])
        self.assertTrue(d['native_table_complete'])
        self.assertEqual(d['raw_hex'], raw.hex().upper())
        self.assertEqual(d['native_decode_status'], 'generic raw fallback')
        self.assertEqual(d['table_decode_category'], 'registered_decoder_fallback')
        self.assertEqual(d['native_table']['name'], generic)
        self.assertEqual(d['references'], [])
        self.assertEqual(d['native_table']['references'], [])
        self.assertEqual(state['crc_errors'], 0)

    def test_encrypted_splice_is_raw_fallback_not_decoded_success(self):
        raw = bytearray(fixture('insert_program'))
        raw[4] |= 0x80
        self.assert_fallback(repair_crc(raw), 'generic_short_table')

    def test_truncated_payload_with_valid_crc_does_not_claim_semantics(self):
        for name, header, generic in [('eas', 8, 'generic_long_table'),
                                       ('insert_program', 3, 'generic_short_table')]:
            with self.subTest(name=name):
                raw = bytearray(fixture(name)[:header + 2] + bytes(4))
                raw[1] = (raw[1] & 0xf0) | ((len(raw) - 3) >> 8)
                raw[2] = (len(raw) - 3) & 255
                self.assert_fallback(repair_crc(raw), generic)

    def test_corrupt_crc_is_invalid_and_excluded_from_export(self):
        for name in ('eas', 'insert_program'):
            with self.subTest(name=name):
                raw = bytearray(fixture(name)); raw[-1] ^= 1
                state, details = self.analyze(bytes(raw))
                self.assertEqual(len(details), 1)
                d = details[0]
                self.assertFalse(d['valid'])
                self.assertEqual(d['table_decode_category'], 'invalid_evidence')
                self.assertFalse(d['native_table_complete'])
                self.assertNotIn('native_table', d)
                self.assertEqual(d['raw_hex'], raw.hex().upper())
                self.assertEqual(d['references'], [])
                self.assertGreater(state['crc_errors'], 0)
                output = Path(self.temp.name) / (name + '-invalid.bin')
                # The engine rejects an empty export rather than emitting invalid bytes.
                with self.assertRaisesRegex(RuntimeError, 'No valid current sections'):
                    self.core.call('export', {'path': str(output), 'format': 'bin'})
                self.assertFalse(output.exists())

    def test_untouched_valid_scte_sections_export_exactly(self):
        for name in ('eas', 'insert_program', 'private'):
            with self.subTest(name=name):
                self.decoded(name)
                output = Path(self.temp.name) / (name + '.bin')
                self.core.call('export', {'path': str(output), 'format': 'bin'})
                self.assertEqual(output.read_bytes(), fixture(name))
                transport = Path(self.temp.name) / (name + '-roundtrip.ts')
                self.core.call('export', {'path': str(transport), 'format': 'ts'})
                state = self.core.call('analyze', {'path': str(transport), 'standards': 'scte',
                                                   'extra_pids': [0x152]})
                self.assertEqual(len(state['tables']), 1)
                detail = self.core.call('inspect', {'id': state['tables'][0]['id']})
                self.assertEqual(detail['raw_hex'], fixture(name).hex().upper())
                self.assertEqual(detail['table_decode_category'], 'decoded')


if __name__ == '__main__':
    unittest.main(verbosity=2)
