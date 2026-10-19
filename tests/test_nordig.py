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

    def test_native_lcd_reference_links_require_actual_namespace_and_dvb_context(self):
        v1 = descriptor(0x83, word(100) + word(0xc000 | 42))
        for standards in ('dvb', 'auto', None):
            state = self.scan([self.nit(self.pds() + v1 + self.lcd())], standards)
            detail = self.core.call('inspect', {'id': state['tables'][0]['id']})
            for tag, version in ((0x83, 1), (0x87, 2)):
                item = next(d for d in detail['descriptors'] if d['tag'] == tag)
                self.assertEqual(item['native']['name'], f'nordig_logical_channel_descriptor_v{version}')
                refs = [r for r in item['references'] if r['id'] == 'nordig-unified']
                self.assertEqual(len(refs), 1)
                self.assertEqual(refs[0]['version'], '3.2.2 (November 2025)')
                self.assertEqual(refs[0]['url'], 'https://nordig.org/wp-content/uploads/2016/03/NorDig-Unified-Requirements-ver.-3.2.2.pdf')
                self.assertEqual(refs, [r for r in item['native']['references'] if r['id'] == 'nordig-unified'])

    def test_reference_registry_does_not_label_wrong_namespace_family_or_generic_linkage(self):
        v1 = descriptor(0x83, word(100) + word(0xc000 | 42))
        linkage = descriptor(0x4a, word(1) + word(2) + word(100) + b'\x82')
        cases = [(v1 + self.lcd(), 'dvb'), (self.pds(0x28) + v1 + self.lcd(), 'dvb'),
                 (v1 + self.lcd() + self.pds(), 'dvb'),
                 (self.pds() + v1 + self.lcd(), 'atsc'),
                 (self.pds() + v1 + self.lcd(), 'isdb'), (self.pds() + linkage, 'dvb')]
        def walk(node):
            yield node
            for child in node.get('children', []):
                yield from walk(child)
        for payload, standards in cases:
            with self.subTest(payload=payload.hex(), standards=standards):
                state = self.scan([self.nit(payload)], standards)
                detail = self.core.call('inspect', {'id': state['tables'][0]['id']})
                nodes = list(detail['descriptors']) + list(walk(detail.get('native_table', {})))
                self.assertFalse(any(r['id'] == 'nordig-unified' for n in nodes for r in n.get('references', [])))

    def test_namespace_barriers_withhold_lcd_candidates_and_merged_sdk_references(self):
        v1 = descriptor(0x83, word(100) + word(0xc007))
        barriers = [descriptor(0x0f, b'\x12\x34\x56\x78'), descriptor(0x5f, b'\x00\x00\x29'),
                    descriptor(0x5f, b'\x00\x00\x00\x00\x29')]
        def walk(node):
            yield node
            for child in node.get('children', []): yield from walk(child)
        for barrier in barriers:
            for renew in (False, True):
                with self.subTest(barrier=barrier.hex(), renew=renew):
                    nit = self.nit(self.pds() + barrier + (self.pds() if renew else b'') + v1 + self.lcd())
                    state = self.scan([nit, self.sdt()]); service = state['services'][0]
                    self.assertEqual(len(service['lcn_candidates']), int(renew))
                    self.assertEqual(len(service['lcn_list_candidates']), int(renew))
                    detail = self.core.call('inspect', {'id': next(t['id'] for t in state['tables'] if t['table_id'] == 0x40)})
                    self.assertEqual(detail['raw_hex'], nit[1].hex().upper())
                    for item in [d for d in detail['descriptors'] if d['tag'] in (0x83, 0x87)]:
                        self.assertEqual(any(r['id'] == 'nordig-unified' for r in item['references']), renew)
                    # Keep SDK output as evidence, but it does not establish the
                    # original descriptor namespace, including in the valid case.
                    self.assertFalse(any(r['id'] == 'nordig-unified' for n in walk(detail['native_table']) for r in n['references']))
                    self.assertTrue(detail['native_decode_warnings'])
                    self.assertIsNone(detail['section_native_text'])

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

class NorDigTopologyTests(unittest.TestCase):
    """List declarations are inspection objects, never receiver-selected lineups."""
    setUp = NorDigTests.setUp
    tearDown = NorDigTests.tearDown
    scan = NorDigTests.scan
    channel_list = staticmethod(NorDigTests.channel_list)
    pds = staticmethod(NorDigTests.pds)
    nit = staticmethod(NorDigTests.nit)
    sdt = staticmethod(NorDigTests.sdt)
    lcd = NorDigTests.lcd

    def graph(self, **args):
        return self.core.call('query_topology', {'limit': 500, **args})

    @staticmethod
    def objects(graph, kind):
        return [item for item in graph['nodes'] if item['object_type'] == kind]

    def assert_sources(self, graph):
        for item in graph['nodes'] + graph['edges']:
            for evidence in item['evidence']:
                detail = self.core.call('inspect', {'id': evidence['section_id'], 'at_packet': graph['at_packet']})
                self.assertEqual(evidence['analysis_revision'], graph['analysis_revision'])
                self.assertEqual(evidence['at_packet'], graph['at_packet'])
                locator = evidence['locator']
                if locator['byte_range'] is None:
                    self.assertFalse(evidence['assertion_key'].startswith('nordig_'), evidence)
                    self.assertEqual(locator['precision'], 'section')
                    continue
                self.assertTrue(any(anchor['field_id'] == locator['field_id'] and
                                    anchor['container_id'] == locator['container_id'] and
                                    anchor['byte_range'] == locator['byte_range']
                                    for anchor in detail['evidence_anchors']), evidence)
                span = locator['byte_range']
                raw = bytes.fromhex(detail['raw_hex'])
                self.assertLessEqual(span['offset'] + span['length'], len(raw))

    def test_cross_transport_lists_merge_by_onid_with_exact_sources(self):
        from topology_fixture import nit, sdt
        d1 = self.pds() + self.lcd()
        d2 = self.pds() + self.lcd(entries=((200, 9, True),))
        state = self.scan([nit(transports=((2, 1, d1), (2, 2, d2))), self.sdt(),
                           sdt(tsid=2, tid=0x46, services=((200, 'Remote'),))])
        before = self.core.call('query', {})
        graph = self.graph()
        self.assertEqual(before, self.core.call('query', {}))
        lists = self.objects(graph, 'channel_list')
        entries = self.objects(graph, 'channel_list_entry')
        self.assertEqual(len(lists), 1)
        self.assertIsNone(lists[0]['parent_id'])
        self.assertEqual(lists[0]['identity'], {'original_network_id': 2, 'channel_list_id': 1, 'namespace': 'nordig_lcd_v2'})
        self.assertEqual(lists[0]['attributes']['selection_status'], 'selection_required')
        self.assertFalse(lists[0]['attributes']['selected'])
        self.assertEqual(lists[0]['attributes']['transmission_completeness'], 'unknown')
        self.assertEqual({(e['identity']['transport_stream_id'], e['identity']['service_id'], e['attributes']['logical_channel_number'])
                          for e in entries}, {(1, 100, 7), (2, 200, 9)})
        self.assertEqual(len([e for e in graph['edges'] if e['relation'] == 'references']), 2)
        self.assertEqual(state['services'][0]['lcn_list_candidates'][0]['number'], 7)
        self.assert_sources(graph)

    def test_aggregated_anchors_match_independent_unicode_wire_fields(self):
        name=b'\x15Norr \xc3\xa5';body=self.channel_list(name=name,country=b'900')
        pid,raw=self.nit(self.pds()+descriptor(0x87,body))
        self.scan([(pid,raw),self.sdt()]);graph=self.graph()
        expected={'nordig_channel_list':body,'nordig_channel_list_id':b'\x01',
                  'nordig_channel_list_name':name,'nordig_country_code':b'900',
                  'nordig_service_id':word(100),'nordig_logical_channel_number':word(0xfc07),
                  'nordig_visible_service_flag':word(0xfc07),'nordig_list_entry':word(100)+word(0xfc07)}
        observed=set()
        for item in graph['nodes']+graph['edges']:
            for evidence in item['evidence']:
                key=evidence['assertion_key']
                if key in expected:
                    span=evidence['locator']['byte_range'];observed.add(key)
                    self.assertEqual(raw[span['offset']:span['offset']+span['length']],expected[key],key)
        self.assertEqual(observed,set(expected))
        self.assertEqual(self.objects(graph,'channel_list')[0]['attributes']['channel_list_name'],'Norr \u00e5')

    def test_multiple_lists_and_entries_resolve_through_shared_ui_container_ids(self):
        import json,shutil,subprocess
        node=shutil.which('node') or shutil.which('nodejs')
        self.assertIsNotNone(node,'Node.js is required for actual shared evidence resolution')
        body=self.channel_list(entries=((100,7,True),(101,8,True)))+self.channel_list(2,entries=((200,9,True),(201,10,True)))
        self.scan([self.nit(self.pds()+descriptor(0x87,body))])
        graph=self.graph();pairs=[];seen=set()
        for item in graph['edges']:
            for ref in item['evidence']:
                if ref['assertion_key'] not in ('nordig_channel_list','nordig_list_entry'):continue
                key=(ref['section_id'],ref['assertion_key'],ref['locator']['byte_range']['offset'])
                if key in seen:continue
                seen.add(key);pairs.append({'ref':ref,'detail':self.core.call('inspect',{'id':ref['section_id'],'at_packet':ref['at_packet']})})
        self.assertEqual(len(pairs),6)
        script="const fs=require('fs'),vm=require('vm'),c={};vm.createContext(c);vm.runInContext(fs.readFileSync(process.argv[1],'utf8'),c);const pairs=JSON.parse(fs.readFileSync(0,'utf8'));console.log(JSON.stringify(pairs.map(p=>c.workbench.resolveTopologyEvidence(p.ref,p.detail))));"
        result=subprocess.run([node,'-e',script,str(ROOT/'ui/tauri/web/workbench.js')],input=json.dumps(pairs),text=True,capture_output=True,check=True)
        resolved=json.loads(result.stdout)
        for pair,answer in zip(pairs,resolved):
            self.assertEqual(answer['status'],'resolved')
            self.assertEqual(answer['precision'],'container')
            self.assertEqual(answer['byte_range'],pair['ref']['locator']['byte_range'])
        self.assertEqual(len({p['ref']['locator']['container_id'] for p in pairs}),6)

    def test_shared_onid_list_never_picks_one_network_parent(self):
        self.scan([self.nit(self.pds() + self.lcd(), network=10),
                   self.nit(self.pds() + self.lcd(), network=11), self.sdt()])
        graph = self.graph(); item = self.objects(graph, 'channel_list')[0]
        self.assertIsNone(item['parent_id'])
        links = [e for e in graph['edges'] if e['relation'] == 'announces' and e['to'] == item['node_id']]
        self.assertEqual({e['from'] for e in links}, {'dvb:network:10', 'dvb:network:11'})
        self.assertEqual(len(self.objects(graph, 'channel_list_entry')), 1)
        source_ids = {e['section_id'] for e in item['evidence']}
        self.assertEqual(len(source_ids), 2)
        self.assert_sources(graph)

    def test_same_list_identifier_different_onid_stays_separate(self):
        from topology_fixture import nit
        d = self.pds() + self.lcd()
        self.scan([nit(transports=((2, 1, d), (3, 1, d))), self.sdt()])
        graph = self.graph()
        self.assertEqual({n['identity']['original_network_id'] for n in self.objects(graph, 'channel_list')}, {2, 3})
        entries = self.objects(graph, 'channel_list_entry')
        self.assertEqual(len(entries), 2)
        self.assertEqual(len([e for e in graph['edges'] if e['relation'] == 'references']), 1)
        missing = next(n for n in entries if n['identity']['original_network_id'] == 3)
        self.assertEqual(missing['resolution_status'], 'unresolved')
        self.assert_sources(graph)

    def test_conflicting_list_name_and_country_are_not_selected(self):
        from topology_fixture import nit
        self.scan([nit(transports=((2, 1, self.pds() + self.lcd()),
                                   (2, 2, self.pds() + self.lcd(name=b'South', country=b'DNK'))))])
        graph = self.graph(); item = self.objects(graph, 'channel_list')[0]
        self.assertEqual(item['resolution_status'], 'conflict')
        for field, expected in [('channel_list_name', {'North', 'South'}), ('country_code', {'SWE', 'DNK'})]:
            self.assertIsNone(item['attributes'][field])
            self.assertEqual({c['value'] for c in item['attribute_conflicts'][field]}, expected)
            self.assertTrue(all(c['evidence'] for c in item['attribute_conflicts'][field]))
        self.assertEqual(len(self.objects(graph, 'channel_list_entry')), 2)
        self.assert_sources(graph)

    def test_conflicting_numbers_and_visibility_retain_all_candidates(self):
        self.scan([self.nit(self.pds() + self.lcd(), network=10),
                   self.nit(self.pds() + self.lcd(entries=((100, 0, False),)), network=11), self.sdt()])
        graph = self.graph(); entry = self.objects(graph, 'channel_list_entry')[0]
        self.assertEqual(entry['resolution_status'], 'conflict')
        self.assertIsNone(entry['attributes']['logical_channel_number'])
        self.assertIsNone(entry['attributes']['visible'])
        self.assertEqual({c['value'] for c in entry['attribute_conflicts']['logical_channel_number']}, {0, 7})
        self.assertEqual({c['value'] for c in entry['attribute_conflicts']['visible']}, {False, True})
        self.assertFalse(entry['attributes']['receiver_policy_applied'])
        self.assert_sources(graph)

    def test_empty_list_and_unobserved_service_references_survive(self):
        self.scan([self.nit(self.pds() + descriptor(0x87, self.channel_list(name=b'', entries=()) +
                                                  self.channel_list(2, entries=((200, 1023, True),))))])
        graph = self.graph()
        self.assertEqual(len(self.objects(graph, 'channel_list')), 2)
        entry = self.objects(graph, 'channel_list_entry')[0]
        self.assertEqual(entry['attributes']['allocation_status'], 'reserved')
        self.assertEqual(entry['resolution_status'], 'unresolved')
        self.assertFalse(self.objects(graph, 'service'))
        self.assert_sources(graph)

    def test_equal_numbers_do_not_imply_service_identity_or_selection(self):
        from topology_fixture import sdt
        self.scan([self.nit(self.pds() + self.lcd(entries=((100, 7, True), (101, 7, True)))),
                   sdt(services=((100, 'TV'), (101, 'Radio')))])
        graph = self.graph(); entries = self.objects(graph, 'channel_list_entry')
        self.assertEqual(len(entries), 2)
        self.assertTrue(all(e['resolution_status'] == 'resolved' for e in entries))
        self.assertTrue(all(e['attributes']['logical_channel_number'] == 7 and not e['attributes']['selected'] for e in entries))

    def test_duplicate_triplet_within_list_is_explicit_conflict(self):
        self.scan([self.nit(self.pds() + self.lcd(entries=((100, 7, True), (100, 7, True)))), self.sdt()])
        graph = self.graph(); entry = self.objects(graph, 'channel_list_entry')[0]
        self.assertEqual(entry['resolution_status'], 'conflict')
        self.assertTrue(any('Duplicate' in why for why in entry['unresolved_reasons']))
        self.assertGreaterEqual(len([e for e in entry['evidence'] if e['assertion_key'] == 'nordig_service_id']), 2)

    def test_same_nit_generation_duplicate_across_blocks_descriptors_and_sections(self):
        body=self.channel_list()
        cases=[[self.nit(self.pds()+descriptor(0x87,body+body))],
               [self.nit(self.pds()+self.lcd()+self.lcd())],
               [self.nit(self.pds()+self.lcd(),number=0,last=1),
                self.nit(self.pds()+self.lcd(),number=1,last=1)]]
        for parts in cases:
            with self.subTest(parts=len(parts),raw=parts[0][1].hex()):
                self.scan(parts+[self.sdt()]);graph=self.graph()
                entry=self.objects(graph,'channel_list_entry')[0]
                self.assertEqual(entry['resolution_status'],'conflict')
                sources=[e for e in entry['evidence'] if e['assertion_key']=='nordig_service_id']
                self.assertEqual(len(sources),2)
                self.assertEqual(len({(e['section_id'],e['locator']['byte_range']['offset']) for e in sources}),2)
        self.scan([self.nit(self.pds()+self.lcd(),network=10),self.nit(self.pds()+self.lcd(),network=11),self.sdt()])
        self.assertEqual(self.objects(self.graph(),'channel_list_entry')[0]['resolution_status'],'resolved')

    def test_default_decode_and_explicit_topology_family_have_distinct_roles(self):
        parts = [self.nit(self.pds() + self.lcd()), self.sdt()]
        for profile in ('dvb', 'auto', None, 'atsc', 'isdb-japan'):
            with self.subTest(profile=profile):
                state = self.scan(parts, profile)
                self.assertEqual(state['services'][0]['lcn_list_candidates'][0]['number'], 7)
                graph = self.graph()
                self.assertEqual(len(self.objects(graph, 'channel_list')), 1 if profile == 'dvb' else 0)
                if profile is None or profile == 'auto':
                    self.assertEqual(graph['interpretation_profile'], 'auto')
                    self.assertEqual(graph['status'], 'unresolved')

    def test_wrong_missing_late_pds_and_network_loop_never_project(self):
        for desc in (self.lcd(), self.pds(0x28) + self.lcd(), self.lcd() + self.pds()):
            self.scan([self.nit(desc), self.sdt()])
            self.assertFalse(self.objects(self.graph(), 'channel_list'))
        self.scan([self.nit(self.pds() + self.lcd(), first_loop=True), self.sdt()])
        self.assertFalse(self.objects(self.graph(), 'channel_list'))

    def test_current_crc_and_nested_length_admission_preserve_raw(self):
        pid, raw = self.nit(self.pds() + self.lcd())
        cases = [(pid, raw[:-1] + bytes([raw[-1] ^ 1])),
                 self.nit(self.pds() + self.lcd(), current=False),
                 self.nit(self.pds() + descriptor(0x87, self.channel_list()[:-1]))]
        for item in cases:
            state = self.scan([item, self.sdt()])
            self.assertFalse(self.objects(self.graph(), 'channel_list'))
            row = next(t for t in state['tables'] if t['table_id'] == 0x40)
            self.assertEqual(self.core.call('inspect', {'id': row['id']})['raw_hex'], item[1].hex().upper())

    def test_incomplete_new_version_and_cutoffs_do_not_borrow_old_list(self):
        old = self.nit(self.pds() + self.lcd(), version=31)
        new = self.nit(self.pds() + self.lcd(name=b'New'), version=0, last=1)
        self.scan([old, self.sdt(), new])
        graph = self.graph(at_packet=1)
        self.assertEqual(self.objects(graph, 'channel_list')[0]['attributes']['channel_list_name'], 'North')
        self.assert_sources(graph)
        self.assertFalse(self.objects(self.graph(), 'channel_list'))

    def test_reused_version_cannot_restore_prior_transport_sibling(self):
        first = self.nit(self.pds() + self.lcd(), version=0, last=1)
        sibling = self.nit(self.pds() + self.lcd(), tsid=2, version=0, number=1, last=1)
        self.scan([first, sibling, self.sdt(), self.nit(self.pds() + self.lcd(), version=1), first])
        self.assertEqual(len(self.objects(self.graph(at_packet=2), 'channel_list_entry')), 2)
        self.assertFalse(self.objects(self.graph(), 'channel_list'))

    def test_root_and_child_paging_preserve_aggregated_source_navigation(self):
        state = self.scan([self.nit(self.pds() + self.lcd(), network=10),
                           self.nit(self.pds() + self.lcd(), network=11), self.sdt()])
        graph = self.graph(); item = self.objects(graph, 'channel_list')[0]
        roots = self.graph(parent_id='', analysis_revision=state['revision'], at_packet=2)
        self.assertIn(item['node_id'], [n['node_id'] for n in roots['nodes']])
        page = self.graph(parent_id=item['node_id'], limit=1, analysis_revision=state['revision'], at_packet=2)
        self.assertEqual(page['page']['total'], 1)
        self.assertEqual(page['context_nodes'][0]['node_id'], item['node_id'])
        self.assert_sources(page)
        with self.assertRaises(RuntimeError):
            self.graph(analysis_revision=state['revision'] + 1)

    def test_conflicting_metadata_bound_refuses_without_losing_raw(self):
        parts = [self.nit(self.pds() + self.lcd(name=f'List-{i}'.encode()), network=i + 1) for i in range(257)]
        state = self.scan(parts)
        with self.assertRaisesRegex(RuntimeError, 'conflicting-attribute limit'):
            self.graph()
        self.assertEqual(self.core.call('inspect', {'id': state['tables'][0]['id']})['raw_hex'], parts[0][1].hex().upper())


    def test_aggregated_reference_edge_obeys_per_object_evidence_bound(self):
        from topology_fixture import sdt
        nit_parts = [self.nit(self.pds() + self.lcd(), network=i + 1) for i in range(350)]
        sdt_parts = [sdt(number=i, last=79) for i in range(80)]
        self.scan(nit_parts + sdt_parts)
        with self.assertRaisesRegex(RuntimeError, 'per-object evidence limit'):
            self.graph()


class NorDigSimulcastTests(unittest.TestCase):
    setUp = NorDigTests.setUp
    tearDown = NorDigTests.tearDown
    scan = NorDigTests.scan
    pds = staticmethod(NorDigTests.pds)
    nit = staticmethod(NorDigTests.nit)
    graph = NorDigTopologyTests.graph
    objects = staticmethod(NorDigTopologyTests.objects)
    assert_sources = NorDigTopologyTests.assert_sources

    @staticmethod
    def linkage(onid=2, tsid=1, sid=200, kind=0x82, private=b''):
        return descriptor(0x4a, word(tsid) + word(onid) + word(sid) + bytes([kind]) + private)

    @staticmethod
    def sdt(services=((100, b''), (200, b'')), onid=2, tsid=1, version=1, tid=0x42, pid=0x11, **kwargs):
        from topology_fixture import versioned
        body = word(onid) + b'\xff'
        for sid, extra in services:
            desc = descriptor(0x48, b'\x01\x00\x04Test') + extra
            body += word(sid) + b'\xff' + word(0x8000 | len(desc)) + desc
        return pid, versioned(section(tid, tsid, version, body), **kwargs)

    def declarations(self, graph=None):
        return self.objects(self.graph() if graph is None else graph, 'simulcast_replacement_reference')

    def test_dvb_automatically_projects_namespace_backed_sdt_declaration(self):
        parts = [self.sdt(((100, self.pds() + self.linkage()), (200, b'')))]
        state = self.scan(parts)
        graph = self.graph(); item, = self.declarations(graph)
        self.assertEqual(item['parent_id'], 'dvb:service:2:1:100')
        self.assertEqual(item['identity'], {'original_network_id': 2, 'transport_stream_id': 1,
                                          'service_id': 200, 'namespace': 'nordig_simulcast_replacement'})
        self.assertEqual(item['resolution_status'], 'resolved')
        self.assertFalse(item['attributes']['receiver_policy_applied'])
        self.assertFalse(item['attributes']['selected'])
        self.assertEqual(item['attributes']['media_equivalence'], 'unverified')
        self.assertEqual(item['attributes']['reception_and_decoder_support'], 'unverified')
        self.assertEqual(item['references'][0]['clause'], '12.3.5')
        self.assertEqual(item['references'][0]['version'], '3.2.2 (November 2025)')
        self.assertEqual({s['id'] for s in state['services']}, {100, 200})
        self.assertTrue(all(s['logical_channel_number'] is None for s in state['services']))
        refs = [e for e in graph['edges'] if e['from'] == item['node_id']]
        self.assertEqual([(e['relation'], e['to']) for e in refs], [('references', 'dvb:service:2:1:200')])
        self.assert_sources(graph)

    def test_target_resolution_requires_full_triplet_across_transports(self):
        self.scan([self.sdt(((100, self.pds() + self.linkage(3, 9, 200)), (200, b''))),
                   self.sdt(((200, b''),), onid=3, tsid=9, tid=0x46),
                   self.sdt(((200, b''),), onid=4, tsid=9, tid=0x46),
                   self.sdt(((200, b''),), onid=3, tsid=8, tid=0x46)])
        graph = self.graph(); item, = self.declarations(graph)
        links = [e for e in graph['edges'] if e['from'] == item['node_id'] and e['relation'] == 'references']
        self.assertEqual([e['to'] for e in links], ['dvb:service:3:9:200'])
        self.assert_sources(graph)

    def test_absent_target_stays_unresolved_without_inventing_service(self):
        self.scan([self.sdt(((100, self.pds() + self.linkage(3, 9, 200)), (200, b'')))])
        graph = self.graph(); item, = self.declarations(graph)
        self.assertEqual(item['resolution_status'], 'unresolved')
        self.assertFalse(any(e['from'] == item['node_id'] and e['relation'] == 'references' for e in graph['edges']))
        self.assertNotIn('dvb:service:3:9:200', {n['node_id'] for n in graph['nodes']})

    def test_missing_wrong_late_overridden_and_malformed_pds_do_not_project(self):
        for desc in (self.linkage(), self.pds(0x28) + self.linkage(), self.linkage() + self.pds(),
                     self.pds() + self.pds(0x28) + self.linkage(),
                     self.pds() + descriptor(0x5f, b'\x00\x00\x29') + self.linkage()):
            with self.subTest(desc=desc.hex()):
                parts = [self.sdt(((100, desc),))]
                state = self.scan(parts)
                self.assertEqual(self.declarations(), [])
                detail = self.core.call('inspect', {'id': state['tables'][0]['id']})
                self.assertEqual(detail['raw_hex'], parts[0][1].hex().upper())
                self.assertFalse(any(a['display_path'].startswith('nordig_replacement_') for a in detail['evidence_anchors']))

    def test_private_data_indicator_ends_scope_until_another_valid_pds(self):
        for indicator in (b'\x12\x34\x56\x78', b'\x00\x00\x00\x29', b'', b'\x29'):
            barrier = descriptor(0x0f, indicator)
            self.scan([self.sdt(((100, self.pds() + barrier + self.linkage()),))])
            self.assertEqual(self.declarations(), [], indicator.hex())
            self.scan([self.sdt(((100, self.pds() + barrier + self.pds() + self.linkage()),))])
            item, = self.declarations()
            pds_refs = [e for e in item['evidence'] if e['assertion_key'] == 'nordig_private_data_specifier']
            self.assertEqual(len(pds_refs), 1)
            # The renewed namespace, rather than the old declaration, is cited.
            self.assertEqual(pds_refs[0]['locator']['byte_range']['offset'], 35 + len(indicator))

    def test_short_syntax_lookalike_does_not_supply_long_sdt_linkage_fields(self):
        pid, raw = self.sdt(((100, self.pds() + self.linkage()),))
        raw = bytearray(raw); raw[1] &= 0x7f; raw[-4:] = crc(raw[:-4]).to_bytes(4, 'big')
        state = self.scan([(pid, bytes(raw))])
        self.assertEqual(self.declarations(), [])
        if state['tables']:
            detail = self.core.call('inspect', {'id': state['tables'][0]['id']})
            self.assertEqual(detail['raw_hex'], bytes(raw).hex().upper())
            self.assertFalse(any(a['display_path'].startswith('nordig_replacement_') for a in detail['evidence_anchors']))

    def test_namespace_never_leaks_between_services_sections_or_analyses(self):
        self.scan([self.sdt(((99, self.pds()), (100, self.linkage())))])
        self.assertEqual(self.declarations(), [])
        self.scan([self.sdt(((99, self.pds()),), number=0, last=1),
                   self.sdt(((100, self.linkage()),), number=1, last=1)])
        self.assertEqual(self.declarations(), [])
        self.scan([self.sdt(((100, self.pds() + self.linkage()),))])
        self.assertEqual(len(self.declarations()), 1)
        self.scan([self.sdt(((100, self.linkage()),))])
        self.assertEqual(self.declarations(), [])

    def test_family_scope_and_generic_linkage_reference_remain_distinct(self):
        for profile in ('auto', None, 'atsc', 'isdb', 'isdb-japan'):
            state = self.scan([self.sdt(((100, self.pds() + self.linkage()),))], profile)
            self.assertEqual(self.declarations(), [])
            detail = self.core.call('inspect', {'id': state['tables'][0]['id']})
            link = next(d for d in detail['descriptors'] if d['tag'] == 0x4a)
            self.assertEqual(link['native']['name'], 'linkage_descriptor')
            self.assertFalse(any(r['id'] == 'nordig-unified' for r in link['references']))

    def test_other_linkage_types_and_wrong_table_or_pid_are_not_nordig(self):
        for kind in (0x05, 0x08, 0x81, 0x83):
            self.scan([self.sdt(((100, self.pds() + self.linkage(kind=kind)),))])
            self.assertEqual(self.declarations(), [])
        self.scan([self.nit(self.pds() + self.linkage())])
        self.assertEqual(self.declarations(), [])
        self.scan([self.sdt(((100, self.pds() + self.linkage()),), pid=0x10)])
        self.assertEqual(self.declarations(), [])

    def test_truncated_prefix_is_raw_only_and_private_tail_remains_opaque(self):
        prefix = word(1) + word(2) + word(200) + b'\x82'
        for length in range(7):
            parts = [self.sdt(((100, self.pds() + descriptor(0x4a, prefix[:length])),))]
            state = self.scan(parts)
            self.assertEqual(self.declarations(), [])
            self.assertEqual(self.core.call('inspect', {'id': state['tables'][0]['id']})['raw_hex'], parts[0][1].hex().upper())
        tail = b'\x00\xff\x82\x29unknown'
        parts = [self.sdt(((100, self.pds() + self.linkage(private=tail)), (200, b'')))]
        state = self.scan(parts); item, = self.declarations()
        self.assertEqual(item['identity']['service_id'], 200)
        detail = self.core.call('inspect', {'id': state['tables'][0]['id']})
        self.assertIn(tail.hex().upper(), detail['raw_hex'])
        self.assertNotIn('private_data', item['attributes'])

    def test_duplicate_same_target_aggregates_all_descriptor_sources(self):
        self.scan([self.sdt(((100, self.pds() + self.linkage() + self.linkage()), (200, b'')))])
        item, = self.declarations()
        descriptor_refs = [e for e in item['evidence'] if e['assertion_key'] == 'descriptor']
        self.assertEqual(len(descriptor_refs), 2)
        self.assertEqual(len({e['locator']['container_id'] for e in descriptor_refs}), 2)
        self.assertEqual(item['resolution_status'], 'resolved')

    def test_competing_targets_remain_explicit_and_unselected(self):
        self.scan([self.sdt(((100, self.pds() + self.linkage(sid=200) + self.linkage(sid=300)), (200, b''), (300, b'')))])
        graph = self.graph(); items = self.declarations(graph)
        self.assertEqual(len(items), 2)
        self.assertTrue(all(n['resolution_status'] == 'conflict' and not n['attributes']['selected'] for n in items))
        self.assertEqual({n['identity']['service_id'] for n in items}, {200, 300})
        self.assertEqual(len(self.objects(graph, 'service')), 3)
        self.assert_sources(graph)

    def test_self_and_cyclic_links_preserve_finite_parent_tree(self):
        self.scan([self.sdt(((100, self.pds() + self.linkage(sid=100)),))])
        item, = self.declarations()
        self.assertEqual(item['resolution_status'], 'conflict')
        self.scan([self.sdt(((100, self.pds() + self.linkage(sid=200)), (200, self.pds() + self.linkage(sid=100))))])
        graph = self.graph(); items = self.declarations(graph)
        self.assertEqual(len(items), 2)
        self.assertEqual(len([e for e in graph['edges'] if e['relation'] == 'references']), 2)
        self.assertTrue(all(n['parent_id'] in ('dvb:service:2:1:100', 'dvb:service:2:1:200') for n in items))
        self.assertTrue(all(not n['attributes']['receiver_policy_applied'] for n in items))
        self.assertEqual(self.graph()['nodes'], graph['nodes'])

    def test_invalid_crc_and_next_sections_cannot_supply_declarations(self):
        for kwargs in ({'bad': True}, {'current': False}):
            parts = [self.sdt(((100, self.pds() + self.linkage()),), **kwargs)]
            state = self.scan(parts)
            self.assertEqual(self.declarations(), [])
            self.assertEqual(self.core.call('inspect', {'id': state['tables'][0]['id']})['raw_hex'], parts[0][1].hex().upper())

    def test_new_incomplete_generation_withholds_old_complete_declaration(self):
        first = self.sdt(((100, self.pds() + self.linkage()), (200, b'')))
        newer = self.sdt(((100, self.pds() + self.linkage(sid=300)),), version=2, last=1)
        self.scan([first, newer])
        self.assertEqual(self.declarations(), [])
        earlier = self.graph(at_packet=0)
        self.assertEqual(self.declarations(earlier)[0]['identity']['service_id'], 200)
        self.assert_sources(earlier)

    def test_reused_sdt_version_does_not_recover_stale_sibling(self):
        first = self.sdt(((100, self.pds() + self.linkage()),), last=1)
        sibling = self.sdt(((200, b''),), number=1, last=1)
        self.scan([first, sibling, self.sdt(((100, b''),), version=2), first])
        self.assertEqual(self.declarations(), [])
        earlier = self.graph(at_packet=1)
        self.assertEqual(self.declarations(earlier)[0]['resolution_status'], 'resolved')

    def test_exact_field_sources_and_actual_shared_resolver(self):
        import json, shutil, subprocess
        parts = [self.sdt(((100, self.pds() + self.linkage(0x1234, 0x5678, 0x9abc)),))]
        self.scan(parts); graph = self.graph(); item, = self.declarations(graph)
        expected = {'nordig_private_data_specifier': b'\x00\x00\x00\x29',
                    'nordig_replacement_original_network_id': word(0x1234),
                    'nordig_replacement_transport_stream_id': word(0x5678),
                    'nordig_replacement_service_id': word(0x9abc), 'nordig_replacement_linkage_type': b'\x82'}
        pairs = []
        for evidence in item['evidence']:
            if evidence['assertion_key'] not in expected: continue
            span = evidence['locator']['byte_range']
            self.assertEqual(parts[0][1][span['offset']:span['offset'] + span['length']], expected.pop(evidence['assertion_key']))
            pairs.append({'ref': evidence, 'detail': self.core.call('inspect', {'id': evidence['section_id']})})
        self.assertEqual(expected, {})
        node = shutil.which('node') or shutil.which('nodejs'); self.assertIsNotNone(node)
        script = "const fs=require('fs'),vm=require('vm'),c={};vm.createContext(c);vm.runInContext(fs.readFileSync(process.argv[1],'utf8'),c);console.log(JSON.stringify(JSON.parse(fs.readFileSync(0,'utf8')).map(p=>c.workbench.resolveTopologyEvidence(p.ref,p.detail))));"
        result = subprocess.run([node, '-e', script, str(ROOT/'ui/tauri/web/workbench.js')], input=json.dumps(pairs), text=True, capture_output=True, check=True)
        for pair, resolved in zip(pairs, json.loads(result.stdout)):
            self.assertEqual(resolved['status'], 'resolved')
            self.assertEqual(resolved['byte_range'], pair['ref']['locator']['byte_range'])
        self.assert_sources(graph)

    def test_source_parent_pages_keep_revision_cutoff_and_stale_refusal(self):
        state = self.scan([self.sdt(((100, self.pds() + self.linkage()), (200, b'')))])
        graph = self.graph(); item, = self.declarations(graph)
        page = self.graph(parent_id=item['parent_id'], limit=1, analysis_revision=state['revision'], at_packet=0)
        self.assertIn(item['node_id'], [n['node_id'] for n in page['nodes']])
        self.assertEqual(page['analysis_revision'], state['revision'])
        self.assertEqual(page['at_packet'], 0)
        self.assert_sources(page)
        with self.assertRaises(RuntimeError): self.graph(analysis_revision=state['revision'] + 1)

    def test_redundant_declaration_sources_obey_per_object_limit(self):
        # Each section contributes 12 distinct source locators across two equal
        # linkage descriptors; 172 * 12 exceeds the fixed 2048-object cap.
        parts = [self.sdt(((100, self.pds() + self.linkage() + self.linkage()),), number=i, last=171) for i in range(172)]
        state = self.scan(parts)
        with self.assertRaisesRegex(RuntimeError, 'per-object evidence limit'):
            self.graph()
        self.assertEqual(self.core.call('inspect', {'id': state['tables'][0]['id']})['raw_hex'], parts[0][1].hex().upper())

if __name__ == '__main__':
    unittest.main()
