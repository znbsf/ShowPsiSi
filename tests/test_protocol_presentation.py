"""Shared Qt/Web protocol-card formatting; positive summaries use the real core."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from core_client import Core
import test_protocol_coverage as protocol
import test_nordig as nordig


def cards(detail, offset=0, limit=20):
    script = "const fs=require('fs'),vm=require('vm');let c={};vm.createContext(c);vm.runInContext(fs.readFileSync(process.argv[1],'utf8'),c);let x=JSON.parse(fs.readFileSync(0,'utf8'));process.stdout.write(JSON.stringify(c.workbench.protocolCards(x.detail,x.offset,x.limit)));"
    run = subprocess.run(['node', '-e', script, str(ROOT / 'ui/tauri/web/workbench.js')],
                         input=json.dumps({'detail': detail, 'offset': offset, 'limit': limit}),
                         text=True, capture_output=True, timeout=10, check=True)
    return json.loads(run.stdout)


class ProtocolPresentationTests(unittest.TestCase):
    def test_actual_nordig_lists_keep_separate_country_and_wire_evidence(self):
        case = nordig.NorDigTests();case.setUp()
        try:
            d = case.pds() + case.lcd() + case.lcd(identifier=2, name=b'South', country=b'DNK')
            state = case.scan([case.nit(d), case.sdt()])
            table = next(t for t in state['tables'] if t['table_id'] == 0x40)
            detail = case.core.call('inspect', {'id': table['id']})
            result = cards(detail)
            self.assertEqual(result['total'], 2)
            self.assertIn('SWE', result['cards'][0]['title'])
            self.assertIn('DNK', result['cards'][1]['title'])
            self.assertIn('list not selected', result['cards'][0]['text'])
            self.assertEqual(result['cards'][0]['evidence']['section_id'], table['id'])
            self.assertEqual(result['cards'][0]['evidence']['pds'], 0x29)
            self.assertEqual(result['cards'][0]['evidence']['analysis_revision'], detail['analysis_revision'])
            self.assertEqual(result['cards'][0]['evidence']['at_packet'], detail['native_table_at_packet'])
        finally:
            case.tearDown()

    def test_actual_ait_cards_preserve_source_relations_and_no_execution(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / 'ait.ts'
            raw = (ROOT / 'tests/fixtures/application-signalling/ait-http.bin').read_bytes()
            p.write_bytes(b''.join(protocol.ProtocolCoverageTests.packetize(0x150, raw)))
            c = Core()
            try:
                state = c.call('analyze', {'path': str(p), 'standards': 'dvb', 'extra_pids': [0x150]})
                detail = c.call('inspect', {'id': state['tables'][0]['id']})
                result = cards(detail)
                self.assertEqual(result['total'], len(detail['application_signalling']['objects']) + 1)
                self.assertIn('not executed', result['cards'][0]['text'])
                self.assertIn('https://example.invalid/hbbtv/', json.dumps(result))
                self.assertTrue(any(x['evidence'].get('relations') for x in result['cards'][1:]))
                self.assertEqual(p.read_bytes(), b''.join(protocol.ProtocolCoverageTests.packetize(0x150, raw)))
            finally:
                c.close()

    def test_malformed_nordig_card_keeps_full_exact_source_context(self):
        case = nordig.NorDigTests();case.setUp()
        try:
            state = case.scan([case.nit(case.pds() + nordig.descriptor(0x87, b'\x01\xff'))])
            detail = case.core.call('inspect', {'id': state['tables'][0]['id'], 'at_packet': 0})
            result = cards(detail)['cards'][0]
            self.assertIn('invalid', result['title'])
            evidence = result['evidence']
            self.assertEqual(evidence['section_id'], detail['id'])
            self.assertEqual(evidence['analysis_revision'], detail['analysis_revision'])
            self.assertEqual(evidence['at_packet'], 0)
            self.assertEqual(evidence['table_identity']['table_id'], 0x40)
            self.assertEqual(evidence['table_identity']['section_number'], detail['section'])
            self.assertEqual(evidence['descriptor']['raw'], '870201FF')
        finally:
            case.tearDown()

    def test_only_current_page_formats_values_at_object_limit(self):
        script = """const fs=require('fs'),vm=require('vm');let c={};vm.createContext(c);
        vm.runInContext(fs.readFileSync(process.argv[1],'utf8'),c);
        let formatted=0;const objects=Array.from({length:4096},(_,i)=>({node_id:'n'+i,
          label:'Object '+i,attributes:{value:{toJSON(){formatted++;return 'value';}}}}));
        const page=c.workbench.protocolCards({application_signalling:{objects}},0,20);
        if(page.total!==4097 || page.cards.length!==20 || formatted!==19)
          throw new Error('Off-page formatting: '+formatted);
        formatted=0;c.workbench.protocolCards({application_signalling:{objects}},20,20);
        if(formatted!==20)throw new Error('Wrong second-page formatting: '+formatted);"""
        subprocess.run(['node', '-e', script, str(ROOT/'ui/tauri/web/workbench.js')], timeout=10, check=True)

    def test_paging_and_clamping_cover_all_cards_without_losing_identity(self):
        detail = {'application_signalling': {'status': 'ok', 'objects': [
            {'node_id': 'n'+str(i), 'label': 'Object '+str(i), 'object_type': 'application',
             'identity': {'application_id': i}} for i in range(47)]}}
        pages = [cards(detail, n) for n in (0, 20, 40)]
        self.assertEqual([len(p['cards']) for p in pages], [20, 20, 8])
        self.assertEqual([p['has_more'] for p in pages], [True, True, False])
        self.assertEqual(len({c['title'] for p in pages for c in p['cards']}), 48)
        self.assertEqual(cards(detail, 999)['offset'], 40)
        self.assertEqual(cards(detail, -10)['offset'], 0)
        self.assertEqual(cards(detail, 0, 999)['limit'], 50)

    def test_untrusted_labels_are_plain_values_and_not_dispatched(self):
        payload = '<script>throw new Error("executed")</script>'
        detail = {'application_signalling': {'status': 'ok', 'objects': [
            {'node_id': '__proto__', 'label': payload, 'attributes': {'url': 'javascript:alert(1)'}}],
            'relations': [{'from': '__proto__', 'to': 'constructor', 'edge_id': 'e'}]}}
        before = json.dumps(detail)
        result = cards(detail)
        self.assertEqual(result['cards'][1]['title'], payload)
        self.assertEqual(len(result['cards'][1]['evidence']['relations']), 1)
        self.assertEqual(json.dumps(detail), before)

    def test_invalid_and_unsupported_states_remain_visible(self):
        result = cards({'descriptors': [{'lcn_list_decode_status': 'invalid',
                        'lcn_list_warnings': ['Truncated list']}],
                        'application_signalling': {'status': 'unsupported_profile', 'objects': []}})
        self.assertEqual(result['total'], 2)
        self.assertIn('Truncated list', result['cards'][0]['text'])
        self.assertIn('unsupported_profile', result['cards'][1]['title'])

    def test_no_protocol_data_does_not_fabricate_a_card(self):
        self.assertEqual(cards({})['cards'], [])
        self.assertEqual(cards({})['total'], 0)


if __name__ == '__main__':
    unittest.main()
