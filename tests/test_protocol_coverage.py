"""Protocol fixtures compiled by TSDuck 3.39-3956 tstabcomp, not RF samples.

Source XML and expected provenance are documented in docs/PROTOCOL_COVERAGE.md.
Tests exercise ShowPsiSi's actual JSON API rather than counting SDK classes.
"""
import sys
import tempfile
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from core_client import Core

# Generated from the pinned SDK XML model using tstabcomp. CRC is part of bytes.
FIXTURES = {
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

class ProtocolCoverageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='showpsi-protocol-')
        self.core = Core()
    def tearDown(self):
        self.core.close()
        self.tmp.cleanup()
    def analyze(self, names, standard, extra_pids=None):
        packets, counters = [], {}
        for _ in range(3):
            for name in names:
                pid, raw = FIXTURES[name]
                body = bytes.fromhex(raw)
                cc = counters.get(pid, 0)
                counters[pid] = (cc + 1) & 15
                packets.append(bytes([0x47, 0x40 | (pid >> 8), pid & 255, 0x10 | cc, 0]) + body + b'\xff' * (183-len(body)))
        path = Path(self.tmp.name) / 'protocol.ts'
        path.write_bytes(b''.join(packets))
        params = {'path': str(path), 'standards': standard}
        if extra_pids is not None:
            params['extra_pids'] = extra_pids
        result = self.core.call('analyze', params)
        self.assertEqual(result['crc_errors'], 0)
        details = [self.core.call('inspect', {'id': t['id']}) for t in result['tables']]
        return result, details
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
        _, details = self.analyze(['MGT', 'TVCT'], 'isdb', [0x1ffb, 0x123])
        self.assertEqual(len(details), 2)
        self.assertTrue(all(d['native_table']['name'] == 'generic_long_table' for d in details))
        self.assertTrue(all(d['references'] == [] for d in details))
    def test_standards_choice_is_validated(self):
        with self.assertRaises(RuntimeError):
            self.analyze(['BIT'], 'invented-standard')

if __name__ == '__main__':
    unittest.main(verbosity=2)
