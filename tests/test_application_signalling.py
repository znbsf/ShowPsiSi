"""Real-core AIT HTTP and SSU/UNT evidence; fixtures are synthetic, not captures."""
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from core_client import Core
from make_fixture import crc, descriptor, section, word
import test_protocol_coverage as helpers

FIXTURES = ROOT / 'tests/fixtures/application-signalling'


class FixtureCheckoutTests(unittest.TestCase):
    def test_pinned_inputs_survive_crlf_checkout_without_changing_hashes(self):
        inputs = {}
        manifest = json.loads((FIXTURES / 'manifest.json').read_text(encoding='utf-8'))
        for name, entry in manifest['fixtures'].items():
            for extension in ('xml', 'bin'):
                inputs[f'tests/fixtures/application-signalling/{name}.{extension}'] = entry[extension + '_sha256']
        for directory in ('scte345', 'tsduck345'):
            fixtures = ROOT / 'tests/fixtures' / directory
            manifest = json.loads((fixtures / 'manifest.json').read_text(encoding='utf-8'))
            for entry in manifest['fixtures'].values():
                inputs[f'tests/fixtures/{directory}/' + entry['xml']] = entry['xml_sha256']
        with tempfile.TemporaryDirectory(prefix='showpsi-fixture-checkout-') as temp:
            repository = Path(temp)
            git = ['git', '-C', str(repository), '-c', 'core.autocrlf=true', '-c', 'core.eol=crlf']
            def run(*args):
                return subprocess.run([*git, *args], check=True, capture_output=True, timeout=30)
            run('init', '--quiet')
            (repository / '.gitattributes').write_bytes((ROOT / '.gitattributes').read_bytes())
            for name, expected in inputs.items():
                raw = (ROOT / name).read_bytes()
                self.assertEqual(hashlib.sha256(raw).hexdigest(), expected)
                path = repository / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(raw)
            # The control must be converted, proving this really exercises Git's
            # CRLF smudge path rather than merely copying the source bytes.
            (repository / 'unprotected.txt').write_bytes(b'line one\nline two\n')
            run('add', '.')
            checkout = repository / 'checkout'
            run('checkout-index', '--all', '--force', '--prefix=' + checkout.as_posix() + '/')
            self.assertEqual((checkout / 'unprotected.txt').read_bytes(), b'line one\r\nline two\r\n')
            for name, expected in inputs.items():
                with self.subTest(path=name):
                    self.assertEqual(hashlib.sha256((checkout / name).read_bytes()).hexdigest(), expected)


class ApplicationSignallingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='showpsi-app-signalling-')
        self.core = Core()

    def tearDown(self):
        self.core.close()
        self.tmp.cleanup()

    def analyze(self, raw, pid=0x150, standard='dvb', prefix=None):
        packets = list(prefix or [])
        packets += helpers.ProtocolCoverageTests.packetize(pid, raw)
        path = Path(self.tmp.name) / 'fixture.ts'
        path.write_bytes(b''.join(packets))
        args = {'path': str(path), 'standards': standard}
        if prefix is None:
            args['extra_pids'] = [pid]
        state = self.core.call('analyze', args)
        details = [self.core.call('inspect', {'id': table['id']})
                   for table in state['tables'] if table['pid'] == pid]
        self.assertTrue(details)
        return state, details[-1]

    def nodes(self, detail, name):
        return helpers.ProtocolCoverageTests.tree_nodes(detail['native_table'], name)

    def test_fixture_compiler_inputs_and_binary_hashes(self):
        manifest = json.loads((FIXTURES / 'manifest.json').read_text())
        self.assertEqual(manifest['compiler'], 'TSDuck 3.45-4798')
        for name, entry in manifest['fixtures'].items():
            for extension in ('xml', 'bin'):
                raw = (FIXTURES / (name + '.' + extension)).read_bytes()
                self.assertEqual(hashlib.sha256(raw).hexdigest(), entry[extension + '_sha256'])
            self.assertEqual(crc((FIXTURES / (name + '.bin')).read_bytes()), 0)

    def test_http_ait_preserves_identifiers_transport_and_path(self):
        raw = (FIXTURES / 'ait-http.bin').read_bytes()
        _, d = self.analyze(raw)
        self.assertTrue(d['native_table_complete'])
        self.assertEqual(d['native_table']['name'], 'AIT')
        self.assertTrue(any(r['id'] == 'dvb-interactive' for r in d['references']))
        self.assertEqual(bytes.fromhex(d['raw_hex']), raw)
        self.assertEqual(self.nodes(d, 'application_identifier')[0]['attributes'],
                         {'application_id': '0x0007', 'organization_id': '0x10203040'})
        self.assertEqual(self.nodes(d, 'url')[0]['attributes']['base'], 'https://example.invalid/hbbtv/')
        self.assertEqual(self.nodes(d, 'extension')[0]['attributes']['value'], 'regional/')
        self.assertEqual(self.nodes(d, 'simple_application_location_descriptor')[0]['attributes']['initial_path'], 'index.html')
        self.assertEqual(self.nodes(d, 'transport_protocol')[0]['attributes']['label'], '0x02')
        self.assertEqual(self.nodes(d, 'transport_protocol_descriptor')[0]['attributes']['transport_protocol_label'], '0x02')

    def test_pmt_discovers_hbbtv_ait_without_extra_pid_override(self):
        packetize = helpers.ProtocolCoverageTests.packetize
        pat = section(0, 1, 0, word(101) + word(0xe100))
        signalling = descriptor(0x6f, word(0x10) + bytes([0xe7]))
        pmt = section(2, 101, 0, word(0xe201) + word(0xf000) +
                      b'\x05' + word(0xe150) + word(0xf000 | len(signalling)) + signalling)
        prefix = packetize(0, pat) + packetize(0x100, pmt)
        state, d = self.analyze((FIXTURES / 'ait-http.bin').read_bytes(), prefix=prefix)
        self.assertEqual(d['native_table']['name'], 'AIT')
        self.assertTrue(any(r['id'] == 'dvb-interactive' for r in d['references']))
        self.assertEqual(state['crc_errors'], 0)
        self.assertEqual(d['version'], 7)

    def test_unt_preserves_update_target_transport_and_uri(self):
        raw = (FIXTURES / 'unt.bin').read_bytes()
        _, d = self.analyze(raw, pid=0x151)
        self.assertEqual(d['native_table']['name'], 'UNT')
        self.assertTrue(d['native_table_complete'])
        self.assertEqual(bytes.fromhex(d['raw_hex']), raw)
        attrs = d['native_table']['attributes']
        self.assertEqual(int(attrs['oui'], 0), 0x1122)
        self.assertEqual(attrs['version'], '3')
        location = self.nodes(d, 'SSU_location_descriptor')[0]
        self.assertEqual(int(location['attributes']['association_tag'], 0), 0x1234)
        self.assertEqual(int(location['attributes']['data_broadcast_id'], 0), 10)
        self.assertEqual(self.nodes(d, 'SSU_uri_descriptor')[0]['attributes'], {
            'max_holdoff_time': '10', 'min_polling_interval': '20',
            'uri': 'https://example.invalid/update.bin'})
        self.assertTrue(any(r['id'] == 'dvb-ssu' for r in d['references']))

    def test_truncated_valid_crc_tables_use_raw_semantic_fallback(self):
        for name in ('ait-http', 'unt'):
            with self.subTest(name=name):
                raw = bytearray((FIXTURES / (name + '.bin')).read_bytes()[:12])
                raw += b'\x00' * 4
                length = len(raw) - 3
                raw[1] = (raw[1] & 0xf0) | (length >> 8)
                raw[2] = length & 0xff
                raw[-4:] = crc(raw[:-4]).to_bytes(4, 'big')
                _, d = self.analyze(bytes(raw))
                self.assertEqual(bytes.fromhex(d['raw_hex']), raw)
                # This flag describes section assembly, not semantic validity.
                self.assertTrue(d['native_table_complete'])
                self.assertEqual(d['native_decode_status'], 'generic raw fallback')
                self.assertEqual(d['native_table']['name'], 'generic_long_table')

    def test_every_payload_truncation_is_bounded_and_keeps_original_evidence(self):
        # Recompute CRC/section length so failures exercise semantic parsers,
        # rather than being rejected only by the outer transport envelope.
        for name, expected_name in (('ait-http', 'AIT'), ('unt', 'UNT')):
            original = (FIXTURES / (name + '.bin')).read_bytes()
            for length in range(8, len(original) - 4):
                with self.subTest(name=name, retained_bytes=length):
                    raw = bytearray(original[:length])
                    section_length = len(raw) + 4 - 3
                    raw[1] = (raw[1] & 0xf0) | (section_length >> 8)
                    raw[2] = section_length & 0xff
                    raw += crc(raw).to_bytes(4, 'big')
                    state, d = self.analyze(bytes(raw))
                    self.assertEqual(state['crc_errors'], 0)
                    self.assertEqual(bytes.fromhex(d['raw_hex']), raw)
                    self.assertIn(d['native_table']['name'], (expected_name, 'generic_long_table'))
                    # The same process must remain usable after each malformed input.
                    self.assertIn('native_registry', self.core.call('capabilities'))

    def test_bad_crc_is_preserved_and_reported_not_valid(self):
        for name in ('ait-http', 'unt'):
            with self.subTest(name=name):
                raw = bytearray((FIXTURES / (name + '.bin')).read_bytes())
                raw[-1] ^= 1
                state, d = self.analyze(bytes(raw))
                self.assertGreater(state['crc_errors'], 0)
                self.assertFalse(d['valid'])
                self.assertEqual(bytes.fromhex(d['raw_hex']), raw)


if __name__ == '__main__':
    unittest.main()
