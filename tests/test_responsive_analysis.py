"""Real-engine contracts for bounded scans, result paging and pause/resume.

The native opt-in gate from test_cancellation makes lifecycle checks deterministic:
no large-file race or sleep is used as evidence that an analysis was paused.
Ordinary scan/payload tests run the production binary. Missing binaries fail.
"""
import hashlib
import json
import os
from pathlib import Path
import queue
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from make_fixture import crc, descriptor, section, word
from test_cancellation import HELPER, PRODUCTION, Wire
from test_mcp_cancellation import CancellationTestCase as MCPCancellationTestCase


COLLECTIONS = (
    'tables', 'services', 'events', 'history', 'table_history',
    'diagnostics', 'density', 'table_groups',
)
NULL_PACKET = bytes([0x47, 0x1f, 0xff, 0x10]) + b'\xff' * 184


def packet(pid, payload, cc=0, start=True):
    """One TS payload packet, including the pointer field only at a section start."""
    payload = (b'\0' if start else b'') + payload
    if len(payload) > 184:
        raise ValueError('Fixture payload exceeds one TS packet')
    return bytes([0x47, (0x40 if start else 0) | (pid >> 8), pid & 255,
                  0x10 | (cc & 15)]) + payload + b'\xff' * (184 - len(payload))


def sdt(version=1, number=0, last=0, name='Responsive Lab'):
    encoded = name.encode('utf-8')
    desc = descriptor(0x48, b'\x01\0' + bytes([len(encoded)]) + encoded)
    payload = word(2) + b'\xff' + word(100 + number) + b'\xff'
    payload += word(0x8000 | len(desc)) + desc
    raw = bytearray(section(0x42, 1, version, payload))
    raw[6], raw[7] = number, last
    raw[-4:] = crc(raw[:-4]).to_bytes(4, 'big')
    return bytes(raw)


def framed(packets, width=188):
    if width == 188:
        return b''.join(packets)
    if width == 192:
        return b''.join(index.to_bytes(4, 'big') + item for index, item in enumerate(packets))
    if width == 204:
        return b''.join(item + b'\0' * 16 for item in packets)
    raise ValueError('Unknown fixture framing')


class ResponsiveAnalysisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        for binary in (HELPER, PRODUCTION):
            if not binary.is_file():
                raise AssertionError(f'Build the matching production and opt-in test cores: {binary}')

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='showpsisi-responsive-')
        self.addCleanup(self.tmp.cleanup)
        self.sequence = 100
        self.wires = 0

    def wire(self, *, stage=None, **kwargs):
        self.wires += 1
        directory = Path(self.tmp.name) / f'wire-{self.wires}'
        directory.mkdir()
        wire = Wire(directory, stage=stage, production=stage is None, **kwargs)
        self.addCleanup(wire.close)
        return wire

    def call(self, wire, method, params=None):
        self.sequence += 1
        reply = wire.call(self.sequence, method, params)
        self.assertIn('result', reply, repr(reply))
        return reply['result']

    def path(self, name, packets, width=188):
        path = Path(self.tmp.name) / name
        path.write_bytes(framed(packets, width))
        return path

    def source(self, count=128):
        # Complete independent tables, repeated with valid PID-local counters.
        # New SDT versions make snapshots/history meaningful without large inputs.
        packets = []
        counters = {}
        parts = [
            (0, section(0, 1, 1, word(100) + word(0xe100))),
            (0x100, section(2, 100, 1, word(0xe200) + word(0xf000))),
            (0x11, sdt()),
            (0x12, section(0x4e, 100, 1, word(1) + word(2) + b'\0\x4e'
                           + word(200) + bytes.fromhex('eb96123456010000')
                           + word(0x8000 | 12) + descriptor(0x4d, b'eng\x05Title\0'))),
        ]
        while len(packets) < count:
            for pid, raw in parts:
                cc = counters.get(pid, 0)
                counters[pid] = (cc + 1) & 15
                packets.append(packet(pid, raw, cc))
                if len(packets) == count:
                    break
        return self.path('source.ts', packets)

    def analyze(self, wire, source, **params):
        return self.call(wire, 'analyze', {'path': str(source), **params})

    def test_compact_j94_standards_metadata_matches_legacy(self):
        from test_cable_oob import nit, stt
        source = self.path('j94-standards.ts',
                           [packet(0x1ffc, nit(), 0), packet(0x1ffc, stt(), 1)]
                           + [NULL_PACKET] * 18)
        fields = ('standards_context', 'detected_standards',
                  'sdk_inferred_standards', 'standards_inference_warning')
        for mode in ('full', 'prefix'):
            with self.subTest(mode=mode):
                wire = self.wire()
                args = {'standards': 'j94-system-b', 'response_mode': 'compact',
                        'scan_mode': mode}
                if mode == 'prefix':
                    args['sample_percent'] = 10
                compact = self.analyze(wire, source, **args)
                legacy = self.call(wire, 'query')
                self.assertEqual({key: compact[key] for key in fields},
                                 {key: legacy[key] for key in fields})
                self.assertEqual(compact['detected_standards'],
                                 'MPEG (J.94 System B selected explicitly)')
                for event in (m for m in wire.messages if m.get('event') == 'progress'):
                    progress = event['state']
                    self.assertEqual(progress['detected_standards'], compact['detected_standards'])
                    self.assertEqual(progress['standards_inference_warning'],
                                     compact['standards_inference_warning'])
                    self.assertIn('sdk_inferred_standards', progress)
                for cutoff in (None, 0):
                    params = {} if cutoff is None else {'at_packet': cutoff}
                    plain = self.call(wire, 'query', params)
                    small = self.call(wire, 'query', {**params, 'response_mode': 'compact'})
                    self.assertEqual({key: small[key] for key in fields},
                                     {key: plain[key] for key in fields})
                ordinary = self.analyze(wire, source, standards='dvb', response_mode='compact')
                self.assertNotIn('sdk_inferred_standards', ordinary)
                self.assertNotIn('standards_inference_warning', ordinary)

    def compact(self, state):
        for key in COLLECTIONS:
            self.assertNotIn(key, state, f'Compact state leaked {key}')
        self.assertIn('analysis_revision', state)
        self.assertIn('analysis_status', state)
        self.assertIn('coverage', state)
        self.assertEqual(set(state['result_counts']), set(COLLECTIONS))
        self.assertTrue(all(count is None or type(count) is int and count >= 0
                            for count in state['result_counts'].values()))
        self.assertLessEqual(len(json.dumps(state, separators=(',', ':')).encode('utf-8')),
                             16 * 1024)

    def counts_match(self, compact, full, *, materialized=False):
        for collection in COLLECTIONS:
            count = compact['result_counts'][collection]
            if materialized or count is not None:
                self.assertEqual(count, len(full[collection]), collection)

    @staticmethod
    def row_semantics(collection, rows):
        # Compact paging intentionally does not compute occurrence distributions.
        # Selection flags and grouping IDs are additive explorer metadata.
        if collection not in ('tables', 'table_groups'):
            return rows
        omitted = {'distribution', 'table_group_id', 'selected_in_snapshot'}
        return [{key: value for key, value in row.items() if key not in omitted} for row in rows]

    def coverage(self, state, mode, source_packets, ranges):
        coverage = state['coverage']
        self.assertEqual(coverage['mode'], mode)
        self.assertEqual(coverage['source_packets'], source_packets)
        self.assertEqual(coverage['ranges'], [
            {'start_packet': start, 'end_packet': end} for start, end in ranges
        ])
        count = sum(end - start for start, end in ranges)
        self.assertEqual(coverage['scanned_packets'], count)
        self.assertEqual(coverage['partial'], count != source_packets)
        return coverage

    def page(self, wire, revision, collection, **kwargs):
        return self.call(wire, 'query_result', {
            'analysis_revision': revision, 'collection': collection, **kwargs,
        })

    def wait_status(self, wire, request_id, status, *, after=0, timeout=10):
        """Wait for owner-published state, preserving the Wire response router."""
        def matches(message):
            return (message.get('event') == 'progress'
                    and type(message.get('request_id')) is type(request_id)
                    and message.get('request_id') == request_id
                    and message.get('state', {}).get('analysis_status') == status)
        for message in wire.messages[after:]:
            if matches(message):
                return message['state']
        deadline = time.monotonic() + timeout
        while True:
            try:
                message = wire.incoming.get(timeout=max(.01, deadline - time.monotonic()))
            except queue.Empty:
                self.fail(f'No owner-published {status!r} state; messages={wire.messages!r}')
            if message is None:
                self.fail('Engine exited while waiting for status: ' + wire.proc.stderr.read())
            if isinstance(message, Exception):
                raise message
            wire.messages.append(message)
            if 'event' not in message:
                wire.pending.append(message)
                if type(message.get('id')) is type(request_id) and message.get('id') == request_id:
                    self.fail(f'Analysis terminated before {status!r}: {message!r}')
            if matches(message):
                return message['state']

    def pause(self, wire, source, request_id=1, **kwargs):
        wire.send(request_id, 'analyze', {'path': str(source), **kwargs})
        wire.gate()
        ack = self.call(wire, 'pause_analysis', {'request_id': request_id})
        self.assertTrue(ack['requested'])
        self.assertEqual(ack['request_id'], request_id)
        wire.release()
        return self.wait_status(wire, request_id, 'paused')

    def test_compact_analyze_query_and_all_pages_match_full_snapshot(self):
        wire = self.wire()
        source = self.source()
        compact = self.analyze(wire, source, response_mode='compact')
        self.compact(compact)
        full = self.call(wire, 'query')
        self.assertTrue(full['events'], 'Fixture must exercise nonempty event paging')
        self.assertTrue(full['services'])
        self.assertEqual(compact['analysis_revision'], full['analysis_revision'])
        self.counts_match(compact, full)
        queried = self.call(wire, 'query', {'response_mode': 'compact'})
        self.compact(queried)
        self.assertEqual(queried['result_counts'], compact['result_counts'])
        for key in COLLECTIONS:
            with self.subTest(collection=key):
                offset, collected = 0, []
                while True:
                    page = self.page(wire, compact['analysis_revision'], key,
                                     offset=offset, limit=3)
                    self.assertEqual(page['total'], len(full[key]))
                    self.assertEqual(self.row_semantics(key, page['items']),
                                     self.row_semantics(key, full[key][offset:offset + 3]))
                    self.assertLessEqual(len(page['items']), 3)
                    self.assertLess(len(json.dumps(page).encode('utf-8')), 64 * 1024)
                    collected.extend(page['items'])
                    if page['next_offset'] is None:
                        break
                    self.assertEqual(page['next_offset'], offset + len(page['items']))
                    self.assertGreater(page['next_offset'], offset)
                    offset = page['next_offset']
                self.assertEqual(self.row_semantics(key, collected),
                                 self.row_semantics(key, full[key]))
                beyond = self.page(wire, compact['analysis_revision'], key,
                                   offset=len(full[key]) + 10, limit=3)
                self.assertEqual(beyond['items'], [])
                self.assertEqual(beyond['total'], len(full[key]))
                self.assertIsNone(beyond['next_offset'])
        materialized = self.call(wire, 'query', {'response_mode': 'compact'})
        self.counts_match(materialized, full, materialized=True)

    def test_paging_defaults_bounds_and_stale_revision_are_enforced(self):
        packets = [packet(0x11, section(0x80, index, 1, b'page'), index)
                   for index in range(521)]
        wire = self.wire()
        state = self.analyze(wire, self.path('many.ts', packets), response_mode='compact')
        revision = state['analysis_revision']
        first = self.page(wire, revision, 'table_history')
        self.assertEqual(first['total'], 521)
        self.assertEqual(len(first['items']), 200)
        self.assertEqual(first['next_offset'], 200)
        maximum = self.page(wire, revision, 'table_history', limit=500)
        self.assertEqual(len(maximum['items']), 500)
        self.assertEqual(maximum['next_offset'], 500)
        tail = self.page(wire, revision, 'table_history', offset=500, limit=500)
        self.assertEqual(len(tail['items']), 21)
        self.assertIsNone(tail['next_offset'])
        # Large table summaries hit a byte budget before the row-count ceiling.
        # Continuation must cover every row once, even with a requested limit 500.
        offset, seen = 0, []
        while True:
            bounded = self.page(wire, revision, 'tables', offset=offset, limit=500)
            self.assertEqual(bounded['total'], 521)
            self.assertTrue(bounded['items'])
            self.assertLessEqual(len(bounded['items']), 500)
            self.assertLessEqual(len(json.dumps(bounded, separators=(',', ':')).encode('utf-8')),
                                 256 * 1024 + 2 * 1024)
            seen.extend(row['id'] for row in bounded['items'])
            if bounded['next_offset'] is None:
                break
            self.assertEqual(bounded['next_offset'], offset + len(bounded['items']))
            self.assertGreater(bounded['next_offset'], offset)
            offset = bounded['next_offset']
        self.assertEqual(len(seen), 521)
        self.assertEqual(len(set(seen)), 521)
        for params in (
            {'collection': 'tables'},
            {'analysis_revision': revision, 'collection': 'not_a_collection'},
            {'analysis_revision': revision, 'collection': 'tables', 'limit': 501},
            {'analysis_revision': revision, 'collection': 'tables', 'limit': 0},
            {'analysis_revision': revision, 'collection': 'tables', 'offset': -1},
            {'analysis_revision': revision, 'collection': 'tables', 'limit': True},
            {'analysis_revision': str(revision), 'collection': 'tables'},
        ):
            with self.subTest(params=params):
                self.sequence += 1
                self.assertIn('error', wire.call(self.sequence, 'query_result', params))
        newer = self.analyze(wire, self.source(), response_mode='compact')
        self.assertGreater(newer['analysis_revision'], revision)
        self.sequence += 1
        stale = wire.call(self.sequence, 'query_result', {
            'analysis_revision': revision, 'collection': 'tables',
        })
        self.assertIn('error', stale)

    def test_packet_cutoff_is_applied_before_page_counts_and_rows(self):
        packets = [packet(0x11, sdt(version=1), 0)] + [NULL_PACKET] * 8
        packets += [packet(0x11, sdt(version=2, name='Later'), 1)]
        wire = self.wire()
        state = self.analyze(wire, self.path('versions.ts', packets), response_mode='compact')
        for cutoff in (0, 8, 9):
            with self.subTest(at_packet=cutoff):
                full = self.call(wire, 'query', {'at_packet': cutoff})
                small = self.call(wire, 'query', {'at_packet': cutoff, 'response_mode': 'compact'})
                self.compact(small)
                self.counts_match(small, full)
                for key in COLLECTIONS:
                    page = self.page(wire, state['analysis_revision'], key,
                                     at_packet=cutoff, limit=500)
                    self.assertEqual(page['total'], len(full[key]))
                    self.assertEqual(self.row_semantics(key, page['items']),
                                     self.row_semantics(key, full[key]))
                materialized = self.call(wire, 'query', {
                    'at_packet': cutoff, 'response_mode': 'compact',
                })
                self.counts_match(materialized, full, materialized=True)
        early = self.page(wire, state['analysis_revision'], 'services', at_packet=8)
        self.assertEqual([row['name'] for row in early['items']], ['Responsive Lab'])

    def test_compact_progress_payload_stays_bounded_with_many_records(self):
        packets = [packet(0x11, section(0x80, index, 1, b'bounded'), index)
                   for index in range(600)]
        wire = self.wire()
        state = self.analyze(wire, self.path('payload.ts', packets * 8),
                             response_mode='compact')
        self.compact(state)
        self.assertEqual(state['result_counts']['tables'], 600)
        progress = [item for item in wire.messages if item.get('event') == 'progress']
        self.assertTrue(progress, 'First real section must publish progress')
        for message in progress:
            self.compact(message['state'])
            self.assertLessEqual(len(json.dumps(message, separators=(',', ':')).encode('utf-8')),
                                 16 * 1024)
        full = self.call(wire, 'query')
        self.assertGreater(len(json.dumps(full).encode('utf-8')),
                           10 * len(json.dumps(state).encode('utf-8')))

    def test_group_members_are_explicitly_bounded_without_losing_raw_records(self):
        packets = [packet(0x11, section(0x80, 1, 1, word(index)), index)
                   for index in range(180)]
        wire = self.wire()
        state = self.analyze(wire, self.path('group-variants.ts', packets),
                             response_mode='compact')
        groups = self.page(wire, state['analysis_revision'], 'table_groups')
        self.assertEqual(groups['total'], 1)
        group = groups['items'][0]
        self.assertEqual(len(group['section_ids']), 128)
        self.assertEqual(group['section_ids_total'], 180)
        self.assertTrue(group['member_ids_truncated'])
        self.assertNotIn('bins', group['distribution'])
        tables = self.page(wire, state['analysis_revision'], 'tables', limit=500)
        self.assertEqual(tables['total'], 180)
        self.assertEqual(len({row['id'] for row in tables['items']}), len(tables['items']))
        full = self.call(wire, 'query')
        self.assertEqual(len(full['tables']), 180)
        self.assertEqual(len(full['table_groups'][0]['section_ids']), 180)
        self.assertEqual(group['section_ids'], full['table_groups'][0]['section_ids'][:128])

    def test_exact_range_ignores_sampling_budget_and_preserves_absolute_framing(self):
        packets = [packet(0x11, section(0x80, index, 1, b'absolute'), index)
                   for index in range(120)]
        wire = self.wire()
        for width in (188, 192, 204):
            source = self.path(f'absolute-{width}.ts', packets, width)
            for mode, args, expected in (
                ('full', {}, [(0, 120)]),
                ('full', {'max_packets': 1}, [(0, 120)]),
                ('prefix', {'max_packets': 7}, [(0, 7)]),
                # max_packets limits prefix/distributed, never an explicitly
                # requested full scan or exact half-open range.
                ('range', {'start_packet': 37, 'end_packet': 50, 'max_packets': 7},
                 [(37, 50)]),
                ('range', {'start_packet': 37, 'end_packet': 40, 'max_packets': 7},
                 [(37, 40)]),
            ):
                with self.subTest(width=width, mode=mode, args=args):
                    state = self.analyze(wire, source, scan_mode=mode, **args)
                    self.assertEqual(state['packet_size'], width)
                    self.coverage(state, mode, 120, expected)
                    self.assertEqual([row['first_packet'] for row in state['tables']],
                                     list(range(*expected[0])))
                    self.assertEqual(state['demux']['discontinuities'], 0)
                    detail = self.call(wire, 'inspect', {'id': state['tables'][0]['id']})
                    first = expected[0][0]
                    self.assertEqual(detail['occurrences'], [first])
                    self.assertEqual(detail['first_file_offset'], first * width + (4 if width == 192 else 0))

    def test_distributed_windows_exact_budget_and_absolute_density(self):
        packets = [packet(0x11, section(0x80, index, 1, b'window'), index)
                   for index in range(120)]
        wire = self.wire()
        for width in (188, 192, 204):
            with self.subTest(width=width):
                state = self.analyze(wire, self.path(f'window-{width}.ts', packets, width),
                                     scan_mode='distributed', max_packets=12, window_count=3)
                expected = [(0, 4), (58, 62), (116, 120)]
                self.coverage(state, 'distributed', 120, expected)
                positions = [pos for start, end in expected for pos in range(start, end)]
                self.assertEqual([row['first_packet'] for row in state['tables']], positions)
                self.assertEqual(state['observations'], 12)
                self.assertEqual(state['demux']['discontinuities'], 0)
                self.assertFalse(any(row['code'] == 'transport_discontinuity'
                                     for row in state['diagnostics']))
                self.assertEqual(sum(row['count'] for row in state['density']), 12)
                self.assertGreater(state['density'][-1]['count'], 0)
                self.assertEqual([row['at_packet'] for row in state['table_history']], positions)

    def test_distributed_default_window_count_and_uneven_budget(self):
        wire = self.wire()
        source = self.path('default-windows.ts', [NULL_PACKET] * 120)
        state = self.analyze(wire, source, scan_mode='distributed', max_packets=13)
        coverage = state['coverage']
        self.assertEqual(len(coverage['ranges']), 4)
        self.assertEqual(coverage['scanned_packets'], 13)
        ranges = [(row['start_packet'], row['end_packet']) for row in coverage['ranges']]
        self.assertEqual(ranges[0][0], 0)
        self.assertEqual(ranges[-1][1], 120)
        self.assertTrue(all(0 <= start < end <= 120 for start, end in ranges))
        self.assertTrue(all(left[1] <= right[0] for left, right in zip(ranges, ranges[1:])))
        widths = [end - start for start, end in ranges]
        self.assertLessEqual(max(widths) - min(widths), 1)
        repeated = self.analyze(wire, source, scan_mode='distributed', max_packets=13)
        self.assertEqual(repeated['coverage'], coverage)
        maximum = self.analyze(wire, source, scan_mode='distributed',
                               max_packets=32, window_count=16)
        self.assertEqual(len(maximum['coverage']['ranges']), 16)
        self.assertEqual(maximum['coverage']['scanned_packets'], 32)

    def test_distributed_keeps_real_discontinuity_inside_a_window(self):
        packets = [packet(0x11, section(0x80, index, 1, b'continuity'), index)
                   for index in range(120)]
        packets[2] = packet(0x11, section(0x80, 2, 1, b'continuity'), 9)
        packets[3] = packet(0x11, section(0x80, 3, 1, b'continuity'), 10)
        wire = self.wire()
        state = self.analyze(wire, self.path('real-discontinuity.ts', packets),
                             scan_mode='distributed', max_packets=12, window_count=3)
        self.assertEqual(state['demux']['discontinuities'], 1)
        diagnostics = [row for row in state['diagnostics']
                       if row['code'] == 'transport_discontinuity']
        self.assertEqual(len(diagnostics), 1)
        self.assertEqual(diagnostics[0]['count'], 1)

    def test_default_packet_budget_and_short_source_coverage(self):
        wire = self.wire()
        source = Path(self.tmp.name) / 'default-budget.ts'
        with source.open('wb') as output:
            # Roughly 47 MB of null packets, with constant retained evidence.
            for _ in range(250):
                output.write(NULL_PACKET * 1000)
            output.write(NULL_PACKET * 17)
        state = self.analyze(wire, source, scan_mode='prefix', response_mode='compact')
        self.coverage(state, 'prefix', 250017, [(0, 250000)])
        small = self.path('short.ts', [NULL_PACKET] * 8)
        for mode in ('prefix', 'distributed'):
            with self.subTest(mode=mode):
                state = self.analyze(wire, small, scan_mode=mode, response_mode='compact')
                self.coverage(state, mode, 8, [(0, 8)])

    def test_percentage_budget_has_exact_coverage_and_framing(self):
        packets = [packet(0x11, section(0x80, index, 1, b'percentage'), index)
                   for index in range(120)]
        wire = self.wire()
        samples = (
            (1, 1, [(0, 1)]),
            # The workbench's requested one-tenth preview is explicitly 10%.
            (10, 12, [(0, 3), (39, 42), (78, 81), (117, 120)]),
            # 120 * 33 / 100 = 39.6: budgets floor, never round up.
            (33, 39, [(0, 10), (37, 47), (74, 84), (111, 120)]),
            (100, 120, [(0, 120)]),
        )
        for width in (188, 192, 204):
            source = self.path(f'percentage-{width}.ts', packets, width)
            for mode in ('prefix', 'distributed'):
                for percent, budget, windows in samples:
                    with self.subTest(width=width, mode=mode, sample_percent=percent):
                        state = self.analyze(wire, source, scan_mode=mode,
                                             sample_percent=percent)
                        expected = [(0, budget)] if mode == 'prefix' else windows
                        self.coverage(state, mode, 120, expected)
                        self.assertEqual(state['packet_size'], width)
                        positions = [position for start, end in expected
                                     for position in range(start, end)]
                        self.assertEqual([row['first_packet'] for row in state['tables']], positions)
                        self.assertEqual(state['observations'], budget)
                        self.assertEqual(state['demux']['discontinuities'], 0)
                        # Percentage is a packet budget, not a byte fraction that
                        # accidentally changes between 188/192/204-byte framing.
                        self.assertEqual(state['coverage']['scanned_packets'],
                                         max(1, 120 * percent // 100))

    def test_one_percent_of_one_packet_scans_one_packet(self):
        wire = self.wire()
        for width in (188, 192, 204):
            source = self.path(f'tiny-percentage-{width}.ts',
                               [packet(0x11, sdt())], width)
            for mode in ('prefix', 'distributed'):
                with self.subTest(width=width, mode=mode):
                    state = self.analyze(wire, source, scan_mode=mode, sample_percent=1)
                    self.coverage(state, mode, 1, [(0, 1)])
                    self.assertEqual(state['packet_size'], width)
                    self.assertEqual(len(state['services']), 1)
                    self.assertTrue(state['complete'])

    def test_percentage_validation_rejects_ambiguous_and_unsupported_requests(self):
        wire = self.wire()
        source = self.source()
        invalid = [
            {'scan_mode': 'prefix', 'sample_percent': value}
            for value in (0, 101, -1, .5, 10.5, True, '10', None)
        ]
        invalid.extend([
            {'scan_mode': mode, 'sample_percent': 10, 'max_packets': 12}
            for mode in ('prefix', 'distributed')
        ])
        invalid.extend([
            {'scan_mode': 'full', 'sample_percent': 10},
            {'scan_mode': 'range', 'start_packet': 0, 'end_packet': 12,
             'sample_percent': 10},
            {'sample_percent': 10},  # Omitted scan_mode is still full.
        ])
        for params in invalid:
            with self.subTest(params=params):
                self.sequence += 1
                reply = wire.call(self.sequence, 'analyze', {
                    'path': str(source), **params,
                })
                self.assertIn('error', reply)
        # Existing absolute budgets remain available and retain their meaning.
        for mode in ('prefix', 'distributed'):
            state = self.analyze(wire, source, scan_mode=mode, max_packets=7,
                                 response_mode='compact')
            self.assertEqual(state['coverage']['scanned_packets'], 7)
            self.assertTrue(state['complete'])

    def test_invalid_scan_arguments_are_rejected_and_process_remains_usable(self):
        wire = self.wire()
        source = self.source()
        for args in (
            {'scan_mode': 'unknown'}, {'response_mode': 'unknown'},
            {'max_packets': 0}, {'max_packets': True}, {'max_packets': 1.5},
            {'window_count': 0}, {'window_count': 17}, {'window_count': True},
            {'scan_mode': 'range', 'start_packet': -1, 'end_packet': 3},
            {'scan_mode': 'range', 'start_packet': 10, 'end_packet': 10},
            {'scan_mode': 'range', 'start_packet': 20, 'end_packet': 10},
        ):
            with self.subTest(args=args):
                self.sequence += 1
                reply = wire.call(self.sequence, 'analyze', {'path': str(source), **args})
                self.assertIn('error', reply)
        self.assertTrue(self.analyze(wire, source, response_mode='compact')['complete'])

    def test_sample_gaps_never_assemble_one_section_across_windows(self):
        raw = section(0x80, 77, 1, b'x' * 230)
        packets = [NULL_PACKET] * 20
        packets[1] = packet(0x11, raw[:183], 0)
        packets[18] = packet(0x11, raw[183:], 1, start=False)
        source = self.path('split-across-gap.ts', packets)
        wire = self.wire()
        full = self.analyze(wire, source)
        self.assertEqual(len(full['tables']), 1)
        self.assertEqual(full['tables'][0]['first_packet'], 1)
        self.assertEqual(full['tables'][0]['last_packet'], 18)
        sampled = self.analyze(wire, source, scan_mode='distributed',
                               max_packets=4, window_count=2)
        self.coverage(sampled, 'distributed', 20, [(0, 2), (18, 20)])
        self.assertEqual(sampled['tables'], [])
        self.assertEqual(sampled['observations'], 0)

    def test_sample_gaps_never_complete_a_generation_from_separate_windows(self):
        packets = [NULL_PACKET] * 20
        packets[1] = packet(0x11, sdt(number=0, last=1), 0)
        packets[18] = packet(0x11, sdt(number=1, last=1), 1)
        source = self.path('generation-across-gap.ts', packets)
        wire = self.wire()
        full = self.analyze(wire, source)
        self.assertEqual(len(full['services']), 2)
        self.assertTrue(full['table_groups'][0]['selected_complete'])
        sampled = self.analyze(wire, source, scan_mode='distributed',
                               max_packets=4, window_count=2)
        self.assertEqual(len(sampled['tables']), 2, 'Retain both genuine section observations')
        self.assertEqual(sampled['services'], [], 'A sample gap is not observed generation continuity')
        self.assertTrue(sampled['table_groups'])
        self.assertFalse(any(group['selected_complete'] for group in sampled['table_groups']))
        detail = self.call(wire, 'inspect', {'id': sampled['tables'][-1]['id']})
        self.assertFalse(detail['merged']['complete'])

    def test_partial_scan_rejects_edit_preview_and_export_without_writes(self):
        wire = self.wire()
        source = self.source()
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        for mode, params in (
            ('prefix', {'max_packets': 12}),
            ('range', {'start_packet': 0, 'end_packet': 12}),
            ('distributed', {'max_packets': 12, 'window_count': 3}),
        ):
            with self.subTest(mode=mode):
                state = self.analyze(wire, source, scan_mode=mode, **params)
                self.assertTrue(state['coverage']['partial'])
                service = state['services'][0]
                self.sequence += 1
                reply = wire.call(self.sequence, 'preview_rename', {
                    'id': service['source_id'], 'service_id': service['id'], 'name': 'Not permitted',
                })
                self.assertIn('error', reply)
                output = Path(self.tmp.name) / f'partial-{mode}.ts'
                self.sequence += 1
                self.assertIn('error', wire.call(self.sequence, 'export', {'path': str(output)}))
                self.assertFalse(output.exists())
                self.assertFalse(Path(str(output) + '.manifest.json').exists())
        self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), digest)

    def test_pause_resume_preserves_all_evidence_and_compact_progress(self):
        source = self.source()
        baseline = self.analyze(self.wire(), source)
        wire = self.wire(stage='after_progress')
        paused = self.pause(wire, source, response_mode='compact')
        self.compact(paused)
        self.assertFalse(paused['complete'])
        cursor = len(wire.messages)
        ack = self.call(wire, 'resume_analysis', {'request_id': 1})
        self.assertTrue(ack['requested'])
        result = wire.response(1)
        self.assertIn('result', result, repr(result))
        self.compact(result['result'])
        self.assertTrue(any(item.get('event') == 'progress'
                            and item.get('state', {}).get('analysis_status') == 'analyzing'
                            for item in wire.messages[cursor:]))
        final = self.call(wire, 'query')
        for key in (*COLLECTIONS, 'packets', 'observations', 'crc_errors', 'demux', 'coverage'):
            self.assertEqual(final[key], baseline[key], key)
        self.assertEqual(sum('event' not in item and item.get('id') == 1
                             for item in wire.messages), 1)

    def test_pause_preserves_pending_section_on_another_pid(self):
        first = section(0x80, 71, 1, b'A' * 230)
        pending = section(0x80, 72, 1, b'B' * 230)
        # Completing PID A triggers the first progress gate while PID B has a
        # real section fragment waiting in its demux. Resume must retain it.
        source = self.path('interleaved-pending-section.ts', [
            packet(0x11, first[:183], 0),
            packet(0x12, pending[:183], 0),
            packet(0x11, first[183:], 1, start=False),
            packet(0x12, pending[183:], 1, start=False),
        ])
        baseline_wire = self.wire()
        baseline = self.analyze(baseline_wire, source)
        self.assertEqual(len(baseline['tables']), 2)
        pending_row = next(row for row in baseline['tables'] if row['pid'] == 0x12)
        self.assertEqual(pending_row['first_packet'], 1)
        self.assertEqual(pending_row['last_packet'], 3)
        baseline_detail = self.call(baseline_wire, 'inspect', {'id': pending_row['id']})

        wire = self.wire(stage='after_progress')
        paused = self.pause(wire, source, response_mode='compact')
        self.assertEqual(paused['packets'], 3)
        self.assertEqual(paused['result_counts']['tables'], 1)
        self.assertTrue(self.call(wire, 'resume_analysis', {'request_id': 1})['requested'])
        self.assertTrue(wire.response(1)['result']['complete'])
        final = self.call(wire, 'query')
        for key in (*COLLECTIONS, 'packets', 'observations', 'crc_errors', 'demux', 'coverage'):
            self.assertEqual(final[key], baseline[key], key)
        resumed_detail = self.call(wire, 'inspect', {'id': pending_row['id']})
        self.assertEqual(resumed_detail['raw_hex'], pending.hex().upper())
        for key in ('raw_hex', 'occurrences', 'occurrence_end_packets', 'first_file_offset'):
            self.assertEqual(resumed_detail[key], baseline_detail[key], key)

    def test_cancel_wakes_paused_owner_and_discards_evidence(self):
        wire = self.wire(stage='after_progress')
        self.pause(wire, self.source(), response_mode='compact')
        ack = self.call(wire, 'cancel_analysis', {'request_id': 1})
        self.assertTrue(ack['requested'])
        result = wire.response(1)
        self.assertEqual(result['error']['code'], 'analysis_cancelled')
        state = self.call(wire, 'query', {'response_mode': 'compact'})
        self.compact(state)
        self.assertEqual(state['analysis_status'], 'cancelled')
        self.assertFalse(state['complete'])
        self.assertEqual(state['observations'], 0)
        full = self.call(wire, 'query')
        for collection in COLLECTIONS:
            if collection == 'density':
                self.assertTrue(all(row == {'count': 0, 'bad': 0} for row in full[collection]))
            else:
                self.assertEqual(full[collection], [])
        self.assertTrue(self.analyze(wire, self.source(), response_mode='compact')['complete'])

    def test_pause_resume_require_exact_typed_target_and_valid_ids(self):
        wire = self.wire(stage='after_progress')
        wire.send(1, 'analyze', {'path': str(self.source()), 'response_mode': 'compact'})
        wire.gate()
        for method in ('pause_analysis', 'resume_analysis'):
            for target in ('1', 'unknown', 999):
                with self.subTest(method=method, target=target):
                    self.assertFalse(self.call(wire, method, {'request_id': target})['requested'])
            for target in (None, True, 1.0, [], {}):
                with self.subTest(method=method, invalid=target):
                    self.sequence += 1
                    self.assertIn('error', wire.call(self.sequence, method, {'request_id': target}))
        self.assertTrue(self.call(wire, 'pause_analysis', {'request_id': 1})['requested'])
        wire.release()
        self.wait_status(wire, 1, 'paused')
        self.assertFalse(self.call(wire, 'resume_analysis', {'request_id': '1'})['requested'])
        self.assertTrue(self.call(wire, 'resume_analysis', {'request_id': 1})['requested'])
        self.assertTrue(wire.response(1)['result']['complete'])

    def test_eof_resumes_paused_analysis_and_drains_queued_queries(self):
        wire = self.wire(stage='after_progress')
        wire.send('paused-eof', 'analyze', {
            'path': str(self.source()), 'response_mode': 'compact',
        })
        wire.gate()
        # This work is accepted before pause, not an inspection rejected while paused.
        wire.send(2, 'query', {'response_mode': 'compact'})
        self.assertTrue(self.call(wire, 'pause_analysis', {'request_id': 'paused-eof'})['requested'])
        wire.release()
        self.wait_status(wire, 'paused-eof', 'paused')
        wire.proc.stdin.close()
        result = wire.response('paused-eof')
        self.assertIn('result', result, repr(result))
        self.assertTrue(result['result']['complete'])
        self.assertTrue(wire.response(2)['result']['complete'])
        wire.proc.wait(timeout=10)
        self.assertEqual(wire.proc.returncode, 0)

    def test_paused_inspection_is_rejected_promptly_without_changing_analysis(self):
        wire = self.wire(stage='after_progress')
        paused = self.pause(wire, self.source(), response_mode='compact')
        for method, params in (
            ('query', {'response_mode': 'compact'}),
            ('query_result', {'analysis_revision': paused['analysis_revision'],
                              'collection': 'tables'}),
            ('inspect', {'id': 'not-yet-selected'}),
        ):
            with self.subTest(method=method):
                self.sequence += 1
                reply = wire.call(self.sequence, method, params)
                self.assertEqual(reply['error']['code'], 'analysis_paused')
        self.assertTrue(self.call(wire, 'resume_analysis', {'request_id': 1})['requested'])
        self.assertTrue(wire.response(1)['result']['complete'])

    def test_pause_resume_bypass_full_fifo_and_preserve_query_order(self):
        wire = self.wire(stage='after_progress')
        wire.send(1, 'analyze', {'path': str(self.source()), 'response_mode': 'compact'})
        wire.gate()
        for request_id in range(1000, 1064):
            wire.send(request_id, 'query', {'response_mode': 'compact'})
        wire.send(1064, 'query', {'response_mode': 'compact'})
        self.assertEqual(wire.response(1064)['error']['code'], 'queue_full')
        self.assertTrue(self.call(wire, 'pause_analysis', {'request_id': 1})['requested'])
        wire.release()
        self.wait_status(wire, 1, 'paused')
        self.assertTrue(self.call(wire, 'resume_analysis', {'request_id': 1})['requested'])
        self.assertTrue(wire.response(1)['result']['complete'])
        for request_id in range(1000, 1064):
            self.assertTrue(wire.response(request_id)['result']['complete'])
        terminals = [message['id'] for message in wire.messages
                     if 'result' in message and message.get('id') in range(1000, 1064)]
        self.assertEqual(terminals, list(range(1000, 1064)))
        terminal = next(index for index, message in enumerate(wire.messages)
                        if message.get('id') == 1 and 'result' in message)
        self.assertFalse(any(message.get('event') == 'progress'
                             and message.get('request_id') == 1
                             for message in wire.messages[terminal + 1:]))

    def test_late_controls_cannot_change_completed_analysis(self):
        wire = self.wire(stage='after_complete')
        wire.send('finished', 'analyze', {'path': str(self.source()), 'response_mode': 'compact'})
        wire.gate()
        for method in ('pause_analysis', 'resume_analysis'):
            ack = self.call(wire, method, {'request_id': 'finished'})
            self.assertFalse(ack['requested'])
            self.assertEqual(ack['reason'], 'not_running')
        wire.release()
        completed = wire.response('finished')['result']
        for method in ('pause_analysis', 'resume_analysis'):
            self.assertFalse(self.call(wire, method, {'request_id': 'finished'})['requested'])
        queried = self.call(wire, 'query', {'response_mode': 'compact'})
        self.assertEqual(queried['result_counts'], completed['result_counts'])
        self.assertTrue(queried['complete'])
        self.assertEqual(queried['analysis_status'], 'complete')

    def test_source_change_while_paused_fails_instead_of_mixing_evidence(self):
        cases = [(stage, mutation) for stage in ('after_progress', 'before_complete')
                 for mutation in ('same_size', 'append')]
        for stage, mutation in cases:
            with self.subTest(stage=stage, mutation=mutation):
                source = self.source()
                wire = self.wire(stage=stage)
                self.pause(wire, source, response_mode='compact')
                before = source.stat()
                if mutation == 'append':
                    with source.open('ab') as output:
                        output.write(NULL_PACKET)
                else:
                    data = bytearray(source.read_bytes())
                    data[-1] ^= 1
                    source.write_bytes(data)
                # Explicitly change metadata, independent of filesystem timestamp resolution.
                os.utime(source, ns=(before.st_atime_ns, before.st_mtime_ns + 2_000_000_000))
                self.assertTrue(self.call(wire, 'resume_analysis', {'request_id': 1})['requested'])
                result = wire.response(1)
                self.assertIn('error', result)
                self.assertNotEqual(result['error']['code'], 'analysis_cancelled')
                failed = self.call(wire, 'query', {'response_mode': 'compact'})
                self.assertEqual(failed['analysis_status'], 'failed')
                self.assertFalse(failed['complete'])
                self.assertEqual(failed['observations'], 0)
                self.assertEqual(failed['result_counts']['tables'], 0)
                self.assertIn(failed['result_counts']['services'], (None, 0))
                self.assertEqual(self.call(wire, 'query')['services'], [])
                recovered = self.analyze(wire, source, response_mode='compact')
                self.assertTrue(recovered['complete'])
                self.assertGreater(recovered['analysis_revision'], failed['analysis_revision'])


class MCPResponsiveAnalysisTests(MCPCancellationTestCase):
    """Outer MCP IDs must never leak or be confused with native transport IDs."""

    def tool_value(self, process, request_id, method, args):
        process.tool(request_id, method, args)
        result = process.result(request_id)
        self.assertFalse(result['isError'], repr(result))
        return result['structuredContent']

    def test_pause_resume_map_outer_ids_and_preserve_successful_terminal(self):
        for index, analysis_id in enumerate(('2', 2, 2.0)):
            with self.subTest(analysis_id=analysis_id):
                self.gate = self.directory / f'mcp-pause-{index}'
                self.env['SHOWPSISI_TEST_GATE'] = str(self.gate)
                process = self.mcp()
                process.request('tools', 'tools/list')
                tools = {tool['name']: tool for tool in process.result('tools')['tools']}
                for method in ('pause_analysis', 'resume_analysis'):
                    self.assertIn(method, tools)
                    self.assertIn('outer MCP', tools[method]['description'])
                process.tool(analysis_id, 'analyze', {
                    'path': str(self.source), 'response_mode': 'compact',
                }, token=f'progress-{index}')
                self.ready(process.proc)
                process.until(lambda item: item.get('method') == 'notifications/progress')
                wrong = 2 if isinstance(analysis_id, str) else '2'
                for method in ('pause_analysis', 'resume_analysis'):
                    ack = self.tool_value(process, f'wrong-{method}', method, {'request_id': wrong})
                    self.assertEqual(ack, {'request_id': wrong, 'requested': False,
                                           'reason': 'not_running'})
                ack = self.tool_value(process, 'pause', 'pause_analysis', {'request_id': analysis_id})
                self.assertEqual(ack, {'request_id': analysis_id, 'requested': True})
                self.assertIs(type(ack['request_id']), type(analysis_id))
                self.release()
                # The native input path confirms the pause flag without blocking
                # the MCP reader or pretending ACK is owner-thread progress.
                process.tool('paused-query', 'query', {'response_mode': 'compact'})
                paused_query = process.result('paused-query')
                self.assertTrue(paused_query['isError'])
                self.assertEqual(paused_query['structuredContent']['error']['code'],
                                 'analysis_paused')
                ack = self.tool_value(process, 'resume', 'resume_analysis', {'request_id': analysis_id})
                self.assertEqual(ack, {'request_id': analysis_id, 'requested': True})
                self.assertIs(type(ack['request_id']), type(analysis_id))
                terminal = process.result(analysis_id)
                self.assertFalse(terminal['isError'])
                self.assertTrue(terminal['structuredContent']['complete'])
                for method in ('pause_analysis', 'resume_analysis'):
                    late = self.tool_value(process, f'late-{method}', method, {'request_id': analysis_id})
                    self.assertFalse(late['requested'])
                process.close()
                terminals = [item for item in process.messages
                             if type(item.get('id')) is type(analysis_id)
                             and item.get('id') == analysis_id]
                self.assertEqual(len(terminals), 1)
                self.assert_source_preserved()

    def test_explicit_cancel_of_paused_outer_id_keeps_original_error(self):
        process = self.mcp()
        process.tool('paused-analysis', 'analyze', {
            'path': str(self.source), 'response_mode': 'compact',
        }, token='pause-token')
        self.ready(process.proc)
        self.assertTrue(self.tool_value(process, 'pause', 'pause_analysis',
                                       {'request_id': 'paused-analysis'})['requested'])
        self.release()
        process.tool('paused-query', 'query')
        self.assertEqual(process.result('paused-query')['structuredContent']['error']['code'],
                         'analysis_paused')
        ack = self.tool_value(process, 'cancel', 'cancel_analysis', {'request_id': 'paused-analysis'})
        self.assertEqual(ack, {'request_id': 'paused-analysis', 'requested': True})
        terminal = process.result('paused-analysis')
        self.assertTrue(terminal['isError'])
        error = terminal['structuredContent']['error']
        self.assertEqual(error['code'], 'analysis_cancelled')
        self.assertEqual(error['data']['state']['analysis_status'], 'cancelled')
        result = self.tool_value(process, 'rescan', 'analyze', {
            'path': str(self.source), 'response_mode': 'compact',
        })
        self.assertTrue(result['complete'])
        process.close()
        self.assertEqual(sum(item.get('id') == 'paused-analysis'
                             for item in process.messages), 1)
        self.assert_source_preserved()

    def test_malformed_pause_resume_targets_cannot_affect_active_analysis(self):
        process = self.mcp()
        process.tool('typed-target', 'analyze', {
            'path': str(self.source), 'response_mode': 'compact',
        })
        self.ready(process.proc)
        sequence = 1000
        for method in ('pause_analysis', 'resume_analysis'):
            for target in (True, False, None, .5, [], {}):
                with self.subTest(method=method, target=target):
                    sequence += 1
                    process.tool(sequence, method, {'request_id': target})
                    result = process.result(sequence)
                    self.assertTrue(result['isError'])
                    self.assertEqual(result['structuredContent']['error']['code'], 'request_failed')
        self.release()
        self.assertTrue(process.result('typed-target')['structuredContent']['complete'])
        self.assert_source_preserved()

    def test_mcp_eof_resumes_paused_analysis_instead_of_deadlocking(self):
        process = self.mcp()
        process.tool('paused-eof', 'analyze', {
            'path': str(self.source), 'response_mode': 'compact',
        })
        self.ready(process.proc)
        self.assertTrue(self.tool_value(process, 'pause', 'pause_analysis',
                                       {'request_id': 'paused-eof'})['requested'])
        self.release()
        process.tool('pause-fence', 'query')
        self.assertEqual(process.result('pause-fence')['structuredContent']['error']['code'],
                         'analysis_paused')
        process.proc.stdin.close()
        terminal = process.result('paused-eof')
        self.assertFalse(terminal['isError'])
        self.assertTrue(terminal['structuredContent']['complete'])
        process.proc.wait(timeout=10)
        self.assertEqual(process.proc.returncode, 0)
        self.assert_source_preserved()


if __name__ == '__main__':
    unittest.main()
