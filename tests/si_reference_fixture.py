"""Existing pinned protocol vectors used to audit generic SI tree presentation.

These are compiler-generated/synthetic references, not broadcast captures.
No protocol byte parser or test-time SDK compiler is introduced here.
"""
import hashlib
import json
from pathlib import Path
from test_protocol_coverage import FIXTURES, EXPANDED_FIXTURES, ProtocolCoverageTests
from make_fixture import section, descriptor, word

ROOT = Path(__file__).resolve().parents[1]


def cases():
    isdb = {'BIT', 'CDT', 'SDTT', 'LDT', 'NBIT', 'ITT', 'ISDB_SPECIAL_NIT'}
    atsc = {'MGT', 'TVCT', 'STT', 'ATSC_SPECIAL_TVCT', 'ATSC_SPECIAL_EIT'}
    for name, (pid, raw) in sorted(FIXTURES.items()):
        standard = EXPANDED_FIXTURES[name]['standard'] if name in EXPANDED_FIXTURES else 'isdb' if name in isdb else 'atsc' if name in atsc else 'scte' if name == 'SCTE_SPLICE' else 'dvb'
        yield name, standard, pid, bytes.fromhex(raw)
    directory = ROOT / 'tests/fixtures/scte345'
    manifest = json.loads((directory / 'manifest.json').read_text(encoding='utf-8'))
    for name, item in sorted(manifest['fixtures'].items()):
        yield 'SCTE_' + name, item['standard'], item['pid'], bytes.fromhex(item['hex'])
    directory = ROOT / 'tests/fixtures/application-signalling'
    manifest = json.loads((directory / 'manifest.json').read_text(encoding='utf-8'))
    for name, item in sorted(manifest['fixtures'].items()):
        raw = (directory / (name + '.bin')).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == item['bin_sha256']
        yield name, 'dvb', 0x150, raw
    yield 'CAT', 'dvb', 1, section(1, 1, 1, descriptor(9, word(0x100) + word(0xe101)))
    event = descriptor(0x4d, b'eng\x01E\x01T')
    yield 'DVB_EIT', 'dvb', 0x12, section(0x4e, 100, 1, word(1) + word(2) + b'\x00\x4e' + word(5) + bytes.fromhex('eb96123456010000') + word(0x8000 + len(event)) + event)


def collect(core, directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    result = []
    for name, standard, pid, raw in cases():
        path = directory / (name + '.ts')
        path.write_bytes(b''.join(ProtocolCoverageTests.packetize(pid, raw)))
        state = core.call('analyze', {'path': str(path), 'standards': standard, 'extra_pids': [pid]})
        records = [r for r in state['tables'] if r['pid'] == pid]
        assert len(records) == 1, (name, len(records))
        detail = core.call('inspect', {'id': records[0]['id']})
        assert detail['raw_hex'].lower() == raw.hex(), name
        assert detail['valid'] and detail['native_table_complete'], name
        result.append({'name': name, 'standard': standard, 'raw_sha256': hashlib.sha256(raw).hexdigest(), 'state': state, 'detail': detail})
    return result
