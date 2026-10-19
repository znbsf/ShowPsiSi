"""NorDig LCD v2 evidence, not receiver channel-selection certification.

Independently authored wire fixtures follow NorDig Unified 3.2.2 section
12.2.9.3. No broadcaster capture, external application, or RF is simulated.
"""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from core_client import Core
from make_fixture import section, descriptor, word, crc
import test_protocol_coverage as protocols


class NorDigTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='showpsisi-nordig-')
        self.core = Core()

    def tearDown(self):
        self.core.close()
        self.tmp.cleanup()

    @staticmethod
    def channel_list(identifier=1, name=b'North', country=b'SWE', entries=((100, 7, True),)):
        services = b''.join(word(sid) + word((0x8000 if visible else 0) | 0x7c00 | number)
                            for sid, number, visible in entries)
        return bytes([identifier, len(name)]) + name + country + bytes([len(services)]) + services

    def lcd(self, **kwargs):
        return descriptor(0x87, self.channel_list(**kwargs))

    @staticmethod
    def pds(value=0x29):
        return descriptor(0x5f, value.to_bytes(4, 'big'))

    @staticmethod
    def nit(desc, onid=2, tsid=1, version=1, number=0, last=0, tid=0x40, first_loop=False, network=10, current=True):
        transport = word(tsid) + word(onid) + word(0xf000 | (0 if first_loop else len(desc))) + (b'' if first_loop else desc)
        raw = bytearray(section(tid, network, version,
                               word(0xf000 | (len(desc) if first_loop else 0)) + (desc if first_loop else b'') +
                               word(0xf000 | len(transport)) + transport))
        raw[5] = (raw[5] & 0xfe) | int(current)
        raw[6:8] = bytes([number, last])
        raw[-4:] = crc(raw[:-4]).to_bytes(4, 'big')
        return (0x10, bytes(raw))

    @staticmethod
    def sdt():
        desc = descriptor(0x48, b'\x01\x00\x04Test')
        return (0x11, section(0x42, 1, 1, word(2) + b'\xff' + word(100) + b'\xff' + word(0x8000 | len(desc)) + desc))

    def scan(self, parts, standards="dvb"):
        counters, packets = {}, []
        for pid, raw in parts:
            added = protocols.ProtocolCoverageTests.packetize(pid, raw, counters.get(pid, 0))
            counters[pid] = (counters.get(pid, 0) + len(added)) & 15
            packets.extend(added)
        path = Path(self.tmp.name) / 'nordig.ts'
        path.write_bytes(b''.join(packets))
        args = {'path': str(path)}
        if standards is not None:
            args['standards'] = standards
        return self.core.call('analyze', args)

    def test_v2_lists_keep_country_name_numbers_and_exact_evidence(self):
        body = self.channel_list(name=b'\x15' + 'Norr \u00e5'.encode()) + self.channel_list(2, b'South', b'DNK', ((100, 9, False),))
        nit = self.nit(self.pds() + descriptor(0x87, body))
        state = self.scan([nit, self.sdt()])
        service = state['services'][0]
        candidates = service['lcn_list_candidates']
        self.assertEqual([(c['channel_list_id'], c['channel_list_name'], c['country_code'], c['number'], c['visible'])
                          for c in candidates], [(1, 'Norr \u00e5', 'SWE', 7, True), (2, 'South', 'DNK', 9, False)])
        self.assertEqual(service['lcn_list_status'], 'selection_required')
        self.assertEqual(service['lcn_status'], 'selection_required')
        self.assertIsNone(service['logical_channel_number'])
        self.assertTrue(all(c['onid'] == 2 and c['ts_id'] == 1 and c['pds'] == 0x29 for c in candidates))
        detail = self.core.call('inspect', {'id': candidates[0]['source_id']})
        self.assertEqual(detail['raw_hex'], nit[1].hex().upper())
        for candidate in candidates:
            self.assertEqual(nit[1][candidate['entry_offset']:candidate['entry_offset'] + 2], word(100))
        self.assertEqual(service['source_id'], next(t['id'] for t in state['tables'] if t['table_id'] == 0x42))

    def test_dvb_and_default_auto_decode_both_versions_without_profile_switch(self):
        v1 = descriptor(0x83, word(100) + word(0xc000 | 42))
        for standards in ('dvb', 'auto', None):
            with self.subTest(standards=standards):
                state = self.scan([self.nit(self.pds() + v1 + self.lcd()), self.sdt()], standards)
                service = state['services'][0]
                self.assertEqual(service['lcn_candidates'][0]['number'], 42)
                self.assertEqual(service['lcn_list_candidates'][0]['number'], 7)
                self.assertEqual(service['lcn_list_status'], 'selection_required')
                self.assertIsNone(service['logical_channel_number'])

    def test_family_choice_never_supplies_missing_private_namespace(self):
        # Existing context is evidence-driven, not a strict family rejection filter.
        # A real NIT + PDS can resolve DVB even in a contradictory requested family.
        for standards in ('atsc', 'isdb', 'isdb-japan', 'isdb-brazil', 'auto'):
            for pds, expected in ((self.pds(), 1), (b'', 0), (self.pds(0x28), 0)):
                with self.subTest(standards=standards, pds=pds.hex()):
                    nit = self.nit(pds + self.lcd())
                    state = self.scan([nit, self.sdt()], standards)
                    candidates = state['services'][0]['lcn_list_candidates']
                    self.assertEqual(len(candidates), expected)
                    detail = self.core.call('inspect', {'id': next(t['id'] for t in state['tables'] if t['table_id'] == 0x40)})
                    self.assertEqual(detail['raw_hex'], nit[1].hex().upper())
                    lcd = next(d for d in detail['descriptors'] if d['tag'] == 0x87)
                    if expected:
                        self.assertEqual(lcd['name'], 'nordig_logical_channel_descriptor_v2')
                    else:
                        self.assertNotIn('lcn_lists', lcd)
                        self.assertNotEqual(lcd['name'], 'nordig_logical_channel_descriptor_v2')

    def test_maximum_descriptor_payload_is_bounded_and_complete(self):
        # 23-byte name + 6-byte header + 56 entries uses 253 of 255 bytes.
        entries = tuple((100 + i, 7 + i, True) for i in range(56))
        payload = self.channel_list(name=b'x' * 23, entries=entries)
        self.assertEqual(len(payload), 253)
        payload += self.channel_list(name=b'', entries=())[:2]  # invalid trailing header
        nit = self.nit(self.pds() + descriptor(0x87, payload))
        state = self.scan([nit, self.sdt()])
        self.assertEqual(state['services'][0]['lcn_list_candidates'], [])
        valid = self.nit(self.pds() + self.lcd(name=b'x' * 23, entries=entries))
        state = self.scan([valid, self.sdt()])
        candidate = state['services'][0]['lcn_list_candidates'][0]
        self.assertEqual(candidate['number'], 7)
        detail = self.core.call('inspect', {'id': candidate['source_id']})
        lcd = next(d for d in detail['descriptors'] if d['tag'] == 0x87)
        self.assertEqual(len(lcd['lcn_lists'][0]['services']), 56)
        self.assertEqual(detail['raw_hex'], valid[1].hex().upper())

    def test_missing_wrong_or_late_pds_never_establishes_nordig(self):
        for desc in (self.lcd(), self.pds(0x28) + self.lcd(), self.lcd() + self.pds()):
            with self.subTest(desc=desc.hex()):
                service = self.scan([self.nit(desc), self.sdt()])['services'][0]
                self.assertEqual(service['lcn_list_candidates'], [])
                self.assertEqual(service['lcn_list_status'], 'none')

    def test_pds_is_loop_local_and_analysis_local(self):
        first = word(9) + word(2) + word(0xf006) + self.pds()
        desc = self.lcd()
        second = word(1) + word(2) + word(0xf000 | len(desc)) + desc
        nit = (0x10, section(0x40, 10, 1, word(0xf000) + word(0xf000 | len(first + second)) + first + second))
        self.scan([self.nit(self.pds() + self.lcd()), self.sdt()])
        self.assertEqual(self.scan([nit, self.sdt()])['services'][0]['lcn_list_candidates'], [])
        self.assertEqual(self.scan([self.nit(self.lcd()), self.sdt()])['services'][0]['lcn_list_candidates'], [])

    def test_wrong_triplet_and_non_transport_loops_are_not_associated(self):
        for kwargs in ({'onid': 3}, {'tsid': 2}, {'first_loop': True}, {'tid': 0x4a}):
            with self.subTest(kwargs=kwargs):
                service = self.scan([self.nit(self.pds() + self.lcd(), **kwargs), self.sdt()])['services'][0]
                self.assertEqual(service['lcn_list_candidates'], [])

    def test_same_number_in_two_lists_still_requires_a_choice(self):
        desc = self.pds() + descriptor(0x87, self.channel_list() + self.channel_list(2))
        service = self.scan([self.nit(desc), self.sdt()])['services'][0]
        self.assertEqual(len(service['lcn_list_candidates']), 2)
        self.assertEqual(service['lcn_list_status'], 'selection_required')
        self.assertIsNone(service['logical_channel_number'])

    def test_v2_never_silently_uses_v1_number(self):
        v1 = descriptor(0x83, word(100) + word(0xc000 | 42))
        service = self.scan([self.nit(self.pds() + v1 + self.lcd()), self.sdt()])['services'][0]
        self.assertEqual(service['lcn_candidates'][0]['number'], 42)
        self.assertEqual(service['lcn_status'], 'selection_required')
        self.assertIsNone(service['logical_channel_number'])

    def test_v1_retains_14_bit_lcn_without_v2(self):
        v1 = descriptor(0x83, word(100) + word(0xc000 | 12345))
        service = self.scan([self.nit(self.pds() + v1), self.sdt()])['services'][0]
        self.assertEqual(service['logical_channel_number'], 12345)
        self.assertEqual(service['lcn_status'], 'known')
        self.assertEqual(service['lcn_list_candidates'], [])

    def test_duplicate_service_and_inconsistent_list_identity_are_conflicts(self):
        duplicate = self.lcd(entries=((100, 7, True), (100, 7, True)))
        conflicting = self.lcd() + self.lcd(name=b'Other', country=b'FIN')
        for desc in (duplicate, conflicting):
            with self.subTest(desc=desc.hex()):
                service = self.scan([self.nit(self.pds() + desc), self.sdt()])['services'][0]
                self.assertEqual(service['lcn_list_status'], 'conflict')
                self.assertEqual(len(service['lcn_list_candidates']), 2)
                self.assertIsNone(service['logical_channel_number'])

    def test_hidden_and_reserved_allocations_are_preserved_without_selection(self):
        for number, visible, status in ((0, False, 'hidden'), (999, True, 'visible'),
                                         (1023, True, 'reserved'), (0, True, 'reserved'), (7, False, 'reserved')):
            with self.subTest(number=number, visible=visible):
                service = self.scan([self.nit(self.pds() + self.lcd(entries=((100, number, visible),))), self.sdt()])['services'][0]
                candidate = service['lcn_list_candidates'][0]
                self.assertEqual((candidate['number'], candidate['visible'], candidate['allocation_status']), (number, visible, status))
                self.assertIsNone(service['logical_channel_number'])

    def test_truncated_nested_loops_and_overlong_name_keep_raw_without_partial_projection(self):
        body = self.channel_list()
        for damaged in (body[:-1], body[:1], body[:2], body[:7],
                        body[:10] + b'\x03' + body[11:], self.channel_list(name=b'x' * 24)):
            desc = self.pds() + descriptor(0x87, damaged)
            nit = self.nit(desc)
            with self.subTest(payload=damaged.hex()):
                state = self.scan([nit, self.sdt()])
                self.assertEqual(state['services'][0]['lcn_list_candidates'], [])
                row = next(t for t in state['tables'] if t['table_id'] == 0x40)
                detail = self.core.call('inspect', {'id': row['id']})
                self.assertEqual(detail['raw_hex'], nit[1].hex().upper())
                lcd = next(d for d in detail['descriptors'] if d['tag'] == 0x87)
                self.assertEqual(lcd['lcn_list_decode_status'], 'invalid')
                self.assertTrue(lcd['lcn_list_warnings'])

    def test_23_wire_byte_name_and_country_group_are_retained(self):
        service = self.scan([self.nit(self.pds() + self.lcd(name=b'x' * 23, country=b'900')), self.sdt()])['services'][0]
        self.assertEqual(service['lcn_list_candidates'][0]['country_code'], '900')
        self.assertEqual(service['lcn_list_candidates'][0]['channel_list_name'], 'x' * 23)

    def test_nit_other_and_current_next_are_distinct(self):
        for current, expected in ((True, 1), (False, 0)):
            service = self.scan([self.nit(self.pds() + self.lcd(), tid=0x41, current=current), self.sdt()])['services'][0]
            self.assertEqual(len(service['lcn_list_candidates']), expected)

    def test_incomplete_new_generation_does_not_borrow_old_lists(self):
        first = self.nit(self.pds() + self.lcd())
        second = self.nit(self.pds() + self.lcd(entries=((100, 9, True),)), version=2, last=1)
        state = self.scan([first, self.sdt(), second])
        self.assertEqual(state['services'][0]['lcn_list_candidates'], [])
        earlier = self.core.call('query', {'at_packet': 1})['services'][0]
        self.assertEqual(earlier['lcn_list_candidates'][0]['number'], 7)

    def test_reused_version_does_not_restore_stale_sibling(self):
        first = self.nit(self.pds() + self.lcd(), last=1)
        second = self.nit(self.pds() + self.lcd(identifier=2), number=1, last=1)
        state = self.scan([first, second, self.sdt(), self.nit(self.pds() + self.lcd(), version=2), first])
        self.assertEqual(state['services'][0]['lcn_list_candidates'], [])

    def test_bad_crc_cannot_supply_list_candidates(self):
        pid, raw = self.nit(self.pds() + self.lcd())
        service = self.scan([(pid, raw[:-1] + bytes([raw[-1] ^ 1])), self.sdt()])['services'][0]
        self.assertEqual(service['lcn_list_candidates'], [])

    def test_redundant_sources_and_list_order_do_not_change_service_semantics(self):
        first = self.nit(self.pds() + descriptor(0x87, self.channel_list() + self.channel_list(2)))
        second = self.nit(self.pds() + descriptor(0x87, self.channel_list(2) + self.channel_list()), network=11)
        self.scan([first, self.sdt(), second])
        diff = self.core.call('diff_snapshots', {'from_packet': 1, 'to_packet': 2})
        self.assertEqual(diff['summary']['services']['changed'], 0)

    def test_semantic_change_carries_old_and_new_list_evidence(self):
        self.scan([self.nit(self.pds() + self.lcd()), self.sdt(),
                   self.nit(self.pds() + self.lcd(entries=((100, 9, True),)), version=2)])
        diff = self.core.call('diff_snapshots', {'from_packet': 1, 'to_packet': 2, 'kind': 'services'})
        self.assertEqual(diff['summary']['services']['changed'], 1)
        self.assertIn('lcn_list_candidates', diff['changes'][0]['changed_fields'])


if __name__ == '__main__':
    unittest.main()
