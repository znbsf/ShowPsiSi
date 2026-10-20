"""Independent adversarial acceptance tests for compact/sampled analysis.

Real native core only. No timing-based pause tests or mocked parser results.
"""
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from core_client import Core
from make_fixture import crc, descriptor, section, word

COLLECTIONS = ('tables', 'services', 'events', 'history', 'table_history',
               'diagnostics', 'density', 'table_groups')


def sdt(number=0, last=0, version=1, name=b'Review'):
    desc = descriptor(0x48, b'\x01\x00' + bytes([len(name)]) + name)
    raw = bytearray(section(0x42, 1, version,
                            word(2) + b'\xff' + word(100 + number) +
                            b'\xff' + word(0x8000 + len(desc)) + desc))
    raw[6], raw[7] = number, last
    raw[-4:] = crc(raw[:-4]).to_bytes(4, 'big')
    return bytes(raw)


def packet(raw=None, cc=0):
    if raw is None:
        return b'\x47\x1f\xff\x10' + b'\xff' * 184
    assert len(raw) <= 183
    return bytes([0x47, 0x40, 0x11, 0x10 | (cc & 15), 0]) + raw + b'\xff' * (183 - len(raw))


class PreviewReviewTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='showpsisi-review-')
        self.core = Core()

    def tearDown(self):
        self.core.close()
        self.tmp.cleanup()

    def source(self, packets, stride=188, name='review.ts'):
        path = Path(self.tmp.name) / name
        path.write_bytes(b''.join((b'\x00' * 4 if stride == 192 else b'') + p +
                                  (b'\x00' * 16 if stride == 204 else b'') for p in packets))
        return str(path)

    def pages(self, revision, collection, at=None, limit=1):
        values, offset, total = [], 0, None
        while True:
            args = {'analysis_revision': revision, 'collection': collection,
                    'offset': offset, 'limit': limit}
            if at is not None:
                args['at_packet'] = at
            response = self.core.call('query_result', args)
            if total is None:
                total = response['total']
            self.assertEqual(response['total'], total)
            values.extend(response['items'])
            next_offset = response['next_offset']
            if next_offset is None:
                self.assertEqual(len(values), response['total'])
                return values
            self.assertGreater(next_offset, offset)
            self.assertEqual(next_offset, len(values))
            offset = next_offset

    def test_range_preserves_absolute_offsets_for_all_framings(self):
        for stride in (188, 192, 204):
            with self.subTest(stride=stride):
                path = self.source([packet()] * 4 + [packet(sdt())] + [packet()] * 7,
                                   stride, str(stride) + '.ts')
                result = self.core.call('analyze', {'path': path, 'scan_mode': 'range',
                    'start_packet': 4, 'end_packet': 8, 'response_mode': 'compact'})
                rows = self.pages(result['revision'], 'tables')
                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0]['first_packet'], 4)
                detail = self.core.call('inspect', {'id': rows[0]['id']})
                self.assertEqual(detail['first_file_offset'], 4 * stride + (4 if stride == 192 else 0))
                self.assertEqual(detail['occurrences'], [4])
                self.assertEqual(detail['occurrence_end_packets'], [4])

    def test_compact_pages_match_legacy_snapshots(self):
        path = self.source([packet(sdt(name=b'Old'), 0), packet(),
                            packet(sdt(version=2, name=b'New'), 1)] + [packet()] * 9)
        result = self.core.call('analyze', {'path': path, 'response_mode': 'compact'})
        for at in (0, 2, 11):
            legacy = self.core.call('query', {'at_packet': at})
            for collection in COLLECTIONS:
                with self.subTest(at=at, collection=collection):
                    paged = self.pages(result['revision'], collection, at)
                    # Compact table summaries intentionally omit expensive distribution;
                    # additive group identity/selection fields support paged reconstruction;
                    # all retained legacy semantics must agree with legacy query.
                    expected = legacy[collection]
                    if collection in ('tables', 'table_groups'):
                        expected = [{k: v for k, v in row.items() if k not in ('distribution', 'table_group_id', 'selected_in_snapshot')} for row in expected]
                        paged = [{k: v for k, v in row.items() if k not in ('distribution', 'table_group_id', 'selected_in_snapshot')} for row in paged]
                    self.assertEqual(paged, expected)

    def test_compact_progress_and_terminal_omit_evidence_arrays(self):
        path = self.source([packet(sdt(), i) for i in range(100)])
        progress = []
        result = self.core.call('analyze', {'path': path, 'response_mode': 'compact'}, progress.append)
        self.assertTrue(progress)
        for state in [event['state'] for event in progress] + [result]:
            for key in COLLECTIONS:
                self.assertNotIn(key, state)
            self.assertLess(len(json.dumps(state).encode()), 65536)

    def test_distributed_windows_do_not_complete_cross_gap_generations(self):
        for stride in (188, 192, 204):
            with self.subTest(stride=stride):
                packets = [packet()] * 12
                packets[0] = packet(sdt(0, 1, 1, b'First'), 0)
                packets[4] = packet(sdt(0, 1, 2, b'Unobserved'), 1)
                packets[10] = packet(sdt(1, 1, 1, b'Second'), 2)
                path = self.source(packets, stride, 'gap-' + str(stride) + '.ts')
                result = self.core.call('analyze', {'path': path, 'response_mode': 'compact',
                    'scan_mode': 'distributed', 'max_packets': 4, 'window_count': 2})
                self.assertEqual(result['coverage']['ranges'], [
                    {'start_packet': 0, 'end_packet': 2},
                    {'start_packet': 10, 'end_packet': 12}])
                self.assertTrue(result['coverage']['partial'])
                self.assertEqual(result['coverage']['scanned_packets'], 4)
                self.assertEqual(self.pages(result['revision'], 'services'), [])
                rows = self.pages(result['revision'], 'tables')
                self.assertEqual([row['first_packet'] for row in rows], [0, 10])
                groups = self.pages(result['revision'], 'table_groups')
                self.assertTrue(groups)
                self.assertTrue(all(not row['selected_complete'] for row in groups))
                for row in rows:
                    inspected = self.core.call('inspect', {'id': row['id'], 'at_packet': 11})
                    self.assertFalse(inspected['native_table_complete'])
                    self.assertEqual(inspected['first_file_offset'], row['first_packet'] * stride +
                                     (4 if stride == 192 else 0))

    def test_distributed_windows_do_not_splice_section_fragments(self):
        raw = section(0x80, 1, 1, b'x' * 300)
        packets = [packet()] * 12
        packets[1] = bytes([0x47, 0x40, 0x11, 0x10, 0]) + raw[:183]
        rest = raw[183:]
        packets[10] = bytes([0x47, 0x00, 0x11, 0x11]) + rest + b'\xff' * (184 - len(rest))
        path = self.source(packets)
        result = self.core.call('analyze', {'path': path, 'response_mode': 'compact',
            'scan_mode': 'distributed', 'max_packets': 4, 'window_count': 2})
        self.assertEqual(self.pages(result['revision'], 'tables'), [])
        self.assertEqual(result['observations'], 0)
        self.assertEqual(result['demux']['discontinuities'], 0)

    def test_adjacent_distributed_ranges_preserve_continuous_assembly(self):
        raw = section(0x80, 1, 1, b'x' * 300)
        packets = [packet()] * 12
        packets[2] = bytes([0x47, 0x40, 0x11, 0x10, 0]) + raw[:183]
        rest = raw[183:]
        packets[3] = bytes([0x47, 0x00, 0x11, 0x11]) + rest + b'\xff' * (184 - len(rest))
        result = self.core.call('analyze', {'path': self.source(packets),
            'response_mode': 'compact', 'scan_mode': 'distributed',
            'max_packets': 11, 'window_count': 4})
        rows = self.pages(result['revision'], 'tables')
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['first_packet'], 2)
        self.assertEqual(rows[0]['last_packet'], 3)
        self.assertEqual(result['coverage']['scanned_packets'], 11)

    def test_full_scan_is_not_silently_limited_by_preview_budget(self):
        path = self.source([packet()] * 10 + [packet(sdt())] + [packet()])
        result = self.core.call('analyze', {'path': path, 'response_mode': 'compact',
                                           'scan_mode': 'full', 'max_packets': 1})
        self.assertFalse(result['coverage']['partial'])
        self.assertEqual(result['coverage']['scanned_packets'], 12)
        self.assertEqual(len(self.pages(result['revision'], 'tables')), 1)

    def test_truncated_group_members_remain_reconstructable_from_table_pages(self):
        path = self.source([packet(sdt(name=('Variant' + str(i)).encode()), i)
                            for i in range(130)])
        result = self.core.call('analyze', {'path': path, 'response_mode': 'compact'})
        groups = self.pages(result['revision'], 'table_groups', limit=500)
        self.assertEqual(len(groups), 1)
        group = groups[0]
        self.assertTrue(group['member_ids_truncated'])
        self.assertEqual(len(group['section_ids']), 128)
        self.assertEqual(group['section_ids_total'], 130)
        tables = self.pages(result['revision'], 'tables', limit=17)
        members = [row for row in tables if row['table_group_id'] == group['id']]
        self.assertEqual(len(members), 130)
        self.assertEqual(len({row['id'] for row in members}), 130)
        self.assertEqual([row['id'] for row in members if row['selected_in_snapshot']],
                         group['selected_section_ids'])

    def test_compact_density_retains_structurally_invalid_observations(self):
        raw = bytearray(sdt())
        raw[17] = 255  # Descriptor extends beyond its valid enclosing loop.
        raw[-4:] = crc(raw[:-4]).to_bytes(4, 'big')
        path = self.source([packet(bytes(raw), i) for i in range(12)])
        result = self.core.call('analyze', {'path': path, 'response_mode': 'compact'})
        legacy = self.core.call('query')
        self.assertTrue(legacy['diagnostics'])
        self.assertFalse(legacy['tables'][0]['valid'])
        self.assertEqual(sum(row['bad'] for row in legacy['density']), 12)
        self.assertEqual(self.pages(result['revision'], 'density'), legacy['density'])

    def test_dsmcc_blocks_never_reconstruct_across_sampled_gap(self):
        import test_dsmcc_summaries as dsmcc
        packets = [packet()] * 12
        packets[0] = packet(dsmcc.dii(), 0)
        packets[1] = packet(dsmcc.ddb(b'abcd'), 1)
        packets[9] = packet(dsmcc.dii(), 2)
        packets[10] = packet(dsmcc.ddb(b'ef', block=1), 3)
        path = self.source(packets)
        full = self.core.call('analyze', {'path': path, 'standards': 'dvb'})
        declaration = next(row for row in full['tables'] if row['table_id'] == 0x3b)
        detail = self.core.call('inspect', {'id': declaration['id'], 'at_packet': 11})
        modules = [obj for obj in detail['application_signalling']['objects']
                   if obj['object_type'] == 'download_module']
        self.assertEqual(len(modules), 1)
        self.assertEqual(modules[0]['attributes']['assembly_status'], 'complete')
        result = self.core.call('analyze', {'path': path, 'standards': 'dvb',
            'response_mode': 'compact', 'scan_mode': 'distributed',
            'max_packets': 6, 'window_count': 2})
        detail = self.core.call('inspect', {'id': declaration['id'], 'at_packet': 11})
        self.assertTrue(detail['coverage']['partial'])
        self.assertIn('semantic_scope', detail)
        modules = [obj for obj in detail['application_signalling']['objects']
                   if obj['object_type'] == 'download_module']
        self.assertEqual(len(modules), 1)
        self.assertEqual(modules[0]['attributes']['assembly_status'], 'incomplete')
        self.assertEqual(modules[0]['attributes']['received_block_count'], 1)
        self.assertIsNone(modules[0]['attributes']['assembled_sha256'])

    def test_cable_subtables_never_complete_across_sampled_gap(self):
        import test_cable_oob as cable
        packets = [packet()] * 12
        packets[0] = packet(cable.nit(tail=cable.revision_descriptor(0, 0, 1)), 0)
        packets[10] = packet(cable.nit(first=3, tail=cable.revision_descriptor(0, 1, 1)), 1)
        path = self.source(packets)
        self.core.call('analyze', {'path': path, 'standards': 'j94-system-b'})
        full = self.core.call('query_cable_oob')
        self.assertEqual(len(full['groups']), 1)
        self.assertTrue(full['groups'][0]['subtable_complete'])
        self.core.call('analyze', {'path': path, 'standards': 'j94-system-b',
            'response_mode': 'compact', 'scan_mode': 'distributed',
            'max_packets': 4, 'window_count': 2})
        partial = self.core.call('query_cable_oob')
        self.assertTrue(partial['coverage']['partial'])
        self.assertIn('semantic_scope', partial)
        self.assertEqual(len(partial['groups']), 1)
        self.assertFalse(partial['groups'][0]['subtable_complete'])
        self.assertEqual(partial['groups'][0]['missing_section_numbers'], [0])

    def test_percentage_preview_obeys_packet_budget_for_all_framings(self):
        for stride in (188, 192, 204):
            for mode in ('prefix', 'distributed'):
                for size, percent in ((73, 10), (7, 1)):
                    with self.subTest(stride=stride, mode=mode, size=size, percent=percent):
                        path = self.source([packet(sdt(), i) for i in range(size)], stride,
                                           f'percent-{stride}-{mode}-{size}.ts')
                        result = self.core.call('analyze', {'path': path,
                            'response_mode': 'compact', 'scan_mode': mode,
                            'sample_percent': percent})
                        coverage = result['coverage']
                        budget = max(1, size * percent // 100)
                        self.assertEqual(coverage['requested_sample_percent'], percent)
                        self.assertEqual(coverage['source_packets'], size)
                        self.assertEqual(coverage['scanned_packets'], budget)
                        self.assertEqual(sum(r['end_packet'] - r['start_packet']
                                             for r in coverage['ranges']), budget)
                        previous_end = 0
                        for observed in coverage['ranges']:
                            self.assertGreaterEqual(observed['start_packet'], previous_end)
                            self.assertGreater(observed['end_packet'], observed['start_packet'])
                            self.assertLessEqual(observed['end_packet'], size)
                            previous_end = observed['end_packet']
                        self.assertTrue(coverage['partial'])
                        self.assertEqual(result['progress_fraction'], 1.0)

    def test_hundred_percent_preview_covers_whole_source_for_all_framings(self):
        for stride in (188, 192, 204):
            path = self.source([packet(sdt(), i) for i in range(13)], stride,
                               f'whole-{stride}.ts')
            full = self.core.call('analyze', {'path': path})
            for mode in ('prefix', 'distributed'):
                with self.subTest(stride=stride, mode=mode):
                    result = self.core.call('analyze', {'path': path,
                        'response_mode': 'compact', 'scan_mode': mode, 'sample_percent': 100})
                    self.assertFalse(result['coverage']['partial'])
                    self.assertEqual(result['coverage']['scanned_packets'], 13)
                    self.assertEqual(result['coverage']['ranges'],
                                     [{'start_packet': 0, 'end_packet': 13}])
                    self.assertEqual(result['observations'], full['observations'])
                    self.assertEqual(self.pages(result['revision'], 'services'), full['services'])

    def test_percentage_rejects_invalid_values_and_conflicting_budget(self):
        path = self.source([packet()] * 12)
        for value in (0, 101, -1, 1.5, True, '10'):
            with self.subTest(value=value), self.assertRaises(RuntimeError):
                self.core.call('analyze', {'path': path, 'scan_mode': 'prefix',
                                           'sample_percent': value})
        for mode in ('full', 'prefix', 'range', 'distributed'):
            with self.subTest(mode=mode, conflicting=True), self.assertRaises(RuntimeError):
                self.core.call('analyze', {'path': path, 'scan_mode': mode,
                                           'sample_percent': 10, 'max_packets': 4})
        for mode in ('full', 'range'):
            with self.subTest(mode=mode, unsupported=True), self.assertRaises(RuntimeError):
                self.core.call('analyze', {'path': path, 'scan_mode': mode,
                                           'sample_percent': 10})

    def test_stale_pages_and_preview_writes_are_rejected(self):
        path = self.source([packet(sdt(), i) for i in range(12)])
        old = self.core.call('analyze', {'path': path, 'response_mode': 'compact'})
        result = self.core.call('analyze', {'path': path, 'scan_mode': 'prefix',
                                           'max_packets': 6, 'response_mode': 'compact'})
        with self.assertRaises(RuntimeError):
            self.pages(old['revision'], 'tables')
        rows = self.pages(result['revision'], 'tables')
        self.assertTrue(rows)
        with self.assertRaises(RuntimeError):
            self.core.call('preview_rename', {'id': rows[0]['id'], 'service_id': 100, 'name': 'Forbidden'})
        destination = str(Path(self.tmp.name) / 'forbidden.bin')
        with self.assertRaises(RuntimeError):
            self.core.call('export', {'path': destination, 'format': 'bin'})
        self.assertFalse(Path(destination).exists())


if __name__ == '__main__':
    unittest.main()
