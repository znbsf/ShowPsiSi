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

    def test_protocol_actions_use_actual_anchors_or_section_only_fallback(self):
        from protocol_ui_fixture import protocol_ui_fixture
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'apps.ts';path.write_bytes(protocol_ui_fixture())
            core=Core()
            try:
                state=core.call('analyze',{'path':str(path),'standards':'dvb'})
                table=next(t for t in state['tables'] if t['table_id']==0x74)
                detail=core.call('inspect',{'id':table['id']})
                script="const fs=require('fs'),vm=require('vm'),c={};vm.createContext(c);vm.runInContext(fs.readFileSync(process.argv[1],'utf8'),c);const d=JSON.parse(fs.readFileSync(0,'utf8'));console.log(JSON.stringify(c.workbench.protocolCards(d,0,50).cards.flatMap(x=>c.workbench.protocolCardSources(x))));"
                result=subprocess.run(['node','-e',script,str(ROOT/'ui/tauri/web/workbench.js')],input=json.dumps(detail),text=True,capture_output=True,check=True)
                rows=json.loads(result.stdout)
                self.assertGreater(len(rows),1)
                self.assertTrue(all(r['available'] for r in rows))
                self.assertTrue(any(r['precision']=='field' for r in rows))
                for row in rows:
                    ref=row['ref']
                    self.assertEqual(ref['analysis_revision'],state['analysis_revision'])
                    self.assertIn(ref['section_id'],[t['id'] for t in state['tables']])
            finally:core.close()
        case=nordig.NorDigTests();case.setUp()
        try:
            state=case.scan([case.nit(case.pds()+b'\x87\x02\x01\xff')])
            detail=case.core.call('inspect',{'id':state['tables'][0]['id']})
            result=subprocess.run(['node','-e',script,str(ROOT/'ui/tauri/web/workbench.js')],input=json.dumps(detail),text=True,capture_output=True,check=True)
            rows=json.loads(result.stdout);self.assertEqual(len(rows),1)
            ref=rows[0]['ref'];self.assertEqual(rows[0]['precision'],'section');self.assertTrue(rows[0]['available'])
            self.assertIsNone(ref['locator']['field_id']);self.assertIsNone(ref['locator']['container_id']);self.assertIsNone(ref['locator']['byte_range'])
            self.assertEqual(ref['section_id'],detail['id'])
        finally:case.tearDown()

    def test_real_j94_short_header_formatting_never_invents_long_fields(self):
        from test_cable_oob import CableOobTests, nit
        case=CableOobTests();case.setUp()
        try:
            state,details=case.scan([nit()]);detail=details[0]
            script="const fs=require('fs'),vm=require('vm');let c={};vm.createContext(c);vm.runInContext(fs.readFileSync(process.argv[1],'utf8'),c);const x=JSON.parse(fs.readFileSync(0,'utf8'));console.log(JSON.stringify([c.workbench.wireHeaderText(x.detail),c.workbench.groupText(x.group),c.workbench.historyText(x.history),c.workbench.structure(x.detail,'section',-1)]));"
            result=subprocess.run(['node','-e',script,str(ROOT/'ui/tauri/web/workbench.js')],input=json.dumps({'detail':detail,'group':state['table_groups'][0],'history':state['table_history'][0]}),capture_output=True,text=True,check=True,timeout=10)
            rendered=json.loads(result.stdout)
            for value in rendered[:3]:
                self.assertIn('version not carried',value)
                self.assertIn('extension not carried',value)
                self.assertIn('section number not carried',value)
                self.assertNotIn('0x0000',value)
                self.assertNotIn('null',value)
            self.assertNotIn('observed 0/1',rendered[1])
            self.assertIn('map assembly unsupported',rendered[1])
            self.assertEqual(rendered[3]['value'],'version not carried · valid')
            self.assertTrue(any(n['label'].startswith('Application decoded') for n in rendered[3]['children']))
        finally:
            case.tearDown()

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
