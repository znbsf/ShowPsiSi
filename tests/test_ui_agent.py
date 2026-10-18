"""Real frontend + real engine UI diagnostics; no mock stream or screenshot."""
import json
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from ui_agent import request
from test_qt_ui import native_environment


class UiAgentTests(unittest.TestCase):
    def exercise(self, frontend, binary):
        if not binary or not Path(binary).is_file():
            self.skipTest('Set SHOWPSISI_' + frontend.upper() + ' to a freshly built application')
        evidence = Path(os.environ.get('SHOWPSISI_AGENT_TEST_ARTIFACTS', ROOT / 'artifacts/ui-agent-tests'))
        evidence.mkdir(parents=True, exist_ok=True)
        directory = Path(tempfile.mkdtemp(prefix=frontend + '-', dir=evidence))
        session = directory / 'session'
        env = native_environment()
        sample = Path(env['SHOWPSISI_SAMPLE'])
        source_hash = hashlib.sha256(sample.read_bytes()).hexdigest()
        env.update(SHOWPSISI_AGENT_DIR=str(session), SHOWPSISI_SETTINGS_PATH=str(directory / 'settings.ini'), SHOWPSISI_SCRIPT='', SHOWPSISI_THEME='dark')
        if frontend == 'tauri':
            env['WEBVIEW2_USER_DATA_FOLDER'] = str(directory / 'webview-profile')
        with (directory / 'application.log').open('w', encoding='utf-8') as log:
            process = subprocess.Popen([str(binary)], env=env, cwd=ROOT, stdout=log, stderr=log)
            try:
                deadline = time.monotonic() + 45
                state = None
                while time.monotonic() < deadline:
                    self.assertIsNone(process.poll(), 'Application exited; see ' + str(directory))
                    if (session / 'session.json').exists():
                        state = request(session, 'snapshot')
                        if state.get('settled') and state.get('tree'):
                            break
                    time.sleep(.1)
                self.assertTrue(state and state.get('settled') and state.get('tree'), state)
                self.assertFalse(state['diagnostics']['error'])
                self.assertFalse(state['diagnostics'].get('frontend_errors'))
                from collections import Counter
                from core_client import Core
                engine = Core()
                try:
                    evidence_state = engine.call('analyze', {'path':str(sample),'standards':'dvb'})
                finally:
                    engine.close()
                groups = evidence_state['table_groups']
                counts = Counter((g['pid'], g['name'] or 'Private / other') for g in groups)
                expected = [{'pid':-1,'name':'All tables','count':len(groups)}] + [dict(pid=pid,name=name,count=count) for (pid,name),count in sorted(counts.items())]
                self.assertEqual([{k:r[k] for k in ('pid','name','count')} for r in state['explorer']], expected)
                self.assertEqual(state['table_filter'], {'pid':-1,'name':'','count_unit':'logical_tables'})
                self.assertFalse(any(r['selected'] for r in state['explorer']))
                self.assertTrue(any(r['kind'] == 'number' for r in state['tree']), state['tree'])
                self.assertTrue(any(r['kind'] == 'string' for r in state['tree']), state['tree'])
                from test_ui_contrast import table_palettes
                qml = (ROOT / 'ui/qt/Main.qml').read_text(encoding='utf-8')
                css = (ROOT / 'ui/tauri/web/style.css').read_text(encoding='utf-8')
                palettes = table_palettes(qml, css)[0]
                symbols = {'PAT':'◆','PMT':'▲','CAT':'■','NIT':'◈','SDT':'▦','BAT':'◇','EIT':'◷','TDT':'◴','TOT':'◶','AIT':'▤'}
                for theme in ('dark', 'light', 'dark'):
                    request(session, 'action', {'name':'set_theme', 'value':theme})
                    state = request(session, 'snapshot')
                    self.assertEqual(state['theme'], theme)
                    colors = dict(zip(('branch','label','number','string','meta'),
                        ('#4ec9b0','#dce1e9','#b5cea8','#d6a089','#abb4c2') if theme == 'dark' else
                        ('#147358','#202733','#326837','#955021','#566171')))
                    def color(hex_value):
                        return 'rgb(%d, %d, %d)' % tuple(int(hex_value[i:i+2],16) for i in (1,3,5)) if frontend == 'tauri' else hex_value
                    controls = {c['id']:c for c in state['controls']}
                    checked = 0
                    for row in state['tree']:
                        label = controls.get('treeLabel:' + row['path'])
                        if frontend == 'qt' and (not label or not label['visible']):
                            continue  # Qt virtualizes rows outside the viewport.
                        checked += 1
                        expected_label = color(colors['branch' if row['branch'] else 'label'])
                        expected_glyph = ('▸' if row['closed'] else '▾') if row['branch'] else '·'
                        expected_value = color(colors.get(row['kind'], colors['meta']))
                        if frontend == 'tauri':
                            self.assertEqual(row['label_color'], expected_label)
                            self.assertEqual(row['glyph'].strip('"'), expected_glyph)
                            self.assertEqual(row['glyph_color'], color(colors['meta']))
                            if row['value']:
                                self.assertEqual(row['value_color'], expected_value)
                        else:
                            self.assertEqual(label['color'], expected_label)
                            self.assertEqual(controls['treeGlyph:' + row['path']]['text'], expected_glyph)
                            self.assertEqual(controls['treeGlyph:' + row['path']]['color'], color(colors['meta']))
                            self.assertEqual(controls['treeValue:' + row['path']]['color'], expected_value)
                    self.assertGreater(checked, 5)
                    checked_explorer = 0
                    for row in state['explorer']:
                        if row['name'] not in symbols:
                            continue
                        if frontend == 'tauri':
                            actual_color, glyph = row['color'], row['glyph']
                        else:
                            suffix = str(row['pid']) + ':' + row['name']
                            label = controls.get('explorerLabel:' + suffix)
                            icon = controls.get('explorerIcon:' + suffix)
                            if not label or not icon or not label['visible']:
                                continue
                            actual_color, glyph = label['color'], icon['text']
                            self.assertEqual(icon['color'], actual_color)
                        self.assertEqual(actual_color, color(palettes[theme][row['name']]))
                        self.assertEqual(glyph, symbols[row['name']])
                        checked_explorer += 1
                    self.assertGreaterEqual(checked_explorer, 3)
                    (directory / (theme + '.json')).write_text(json.dumps(state, indent=2), encoding='utf-8')
                (directory / 'initial.json').write_text(json.dumps(state, indent=2), encoding='utf-8')
                branch = next(r for r in state['tree'] if r['branch'])
                request(session, 'action', {'name':'toggle_tree', 'path':branch['path']})
                changed = request(session, 'snapshot')
                row = next(r for r in changed['tree'] if r['path'] == branch['path'])
                self.assertNotEqual(row['closed'], branch['closed'])
                request(session, 'action', {'name':'toggle_tree', 'path':branch['path']})
                request(session, 'action', {'name':'search_tree', 'value':'service'})
                searched = request(session, 'snapshot')
                self.assertEqual(searched['tree_search'], 'service')
                request(session, 'action', {'name':'search_tree', 'value':'Section header'})
                header_search = request(session, 'snapshot')
                self.assertTrue(any(r['label']=='pid' for r in header_search['tree']), header_search['tree'])
                with self.assertRaisesRegex(RuntimeError, 'Unsupported'):
                    request(session, 'action', {'name':'eval', 'value':'arbitrary code'})
                request(session, 'action', {'name':'search_tree', 'value':''})
                request(session, 'action', {'name':'select_tab', 'value':'Tables'})
                self.assertEqual(request(session, 'snapshot')['tab'], 'Tables')
                request(session, 'action', {'name':'select_tab', 'value':'Services'})
                restored = request(session, 'snapshot')
                target = next(row for row in restored['tree'] if row['kind'] == 'string' and not row['branch'])
                request(session, 'action', {'name':'focus_tree', 'path':target['path']})
                self.assertEqual(request(session, 'snapshot')['focused_tree_path'], target['path'])
                # Capture checks settled state itself and publishes manifest last.
                capture = request(session, 'capture')
                captured = Path(capture['directory'])
                manifest = json.loads((captured / 'manifest.json').read_text(encoding='utf-8'))
                self.assertTrue(manifest['complete'])
                self.assertGreater(manifest['width'], 900)
                png = (captured / manifest['screenshot']).read_bytes()
                self.assertTrue(png.startswith(b'\x89PNG\r\n\x1a\n'))
                self.assertGreater(len(png), 10000)
                saved = json.loads((captured / manifest['state']).read_text(encoding='utf-8'))
                self.assertTrue(saved['settled'])
                self.assertEqual(saved['selected'], state['selected'])
                def settled(selected_id=None):
                    end=time.monotonic()+20
                    while time.monotonic()<end:
                        current=request(session,'snapshot')
                        if current['settled'] and (selected_id is None or current['selected']==selected_id):
                            return current
                        time.sleep(.05)
                    self.fail('Workbench did not settle: '+str(current))
                request(session,'action',{'name':'select_tab','value':'Tables'})
                current=settled()
                self.assertEqual(len(current['records']['groups']),len(groups))
                expected_visible=[r for r in evidence_state['tables'] if r['crc']['status']!='invalid']
                self.assertEqual(set(current['records']['sections']),{r['id'] for r in expected_visible})
                request(session,'action',{'name':'set_bad_crc','value':True})
                self.assertEqual(len(settled()['records']['sections']),len(evidence_state['tables']))
                request(session,'action',{'name':'set_grouped','value':False})
                self.assertFalse(settled()['records']['grouped'])
                request(session,'action',{'name':'search_records','value':'PMT 0x0100'})
                searched=settled()
                self.assertEqual(len(searched['records']['groups']),1)
                request(session,'action',{'name':'search_records','value':''})
                request(session,'action',{'name':'set_grouped','value':True})
                request(session,'action',{'name':'history_scope','value':True})
                self.assertEqual(settled()['history']['entries'],evidence_state['table_history'])
                # Each captured family can be inspected, scoped and jumped at exactly
                # the packet advertised by the visible history control.
                for tid in sorted({h['table_id'] for h in evidence_state['table_history']}):
                    h=next(h for h in evidence_state['table_history'] if h['table_id']==tid)
                    request(session,'action',{'name':'select_record','id':h['id']})
                    settled(h['id'])
                    request(session,'action',{'name':'history_scope','value':False})
                    focused=settled()
                    self.assertTrue(focused['history']['entries'])
                    self.assertTrue(all(e['table_id']==tid and e['pid']==h['pid'] and e['extension']==h['extension'] for e in focused['history']['entries']))
                    for scope in ('section','merged'):
                        request(session,'action',{'name':'set_scope','value':scope})
                        for view in ('Structure','Hex','XML','Decoded','Metadata','References'):
                            request(session,'action',{'name':'set_view','value':view})
                            inspected=settled()
                            self.assertEqual(inspected['evidence_scope'],scope)
                            self.assertFalse(inspected['diagnostics']['error'])
                            self.assertFalse(inspected['diagnostics'].get('frontend_errors'))
                    # Run the last family jump after all source records were visited;
                    # early snapshots deliberately exclude future evidence.
                target=focused['history']['entries'][0]
                request(session,'action',{'name':'history_jump','index':0})
                jumped=settled(target['id'])
                self.assertEqual(jumped['packet'],target['at_packet'])
                self.assertEqual(jumped['table_filter']['pid'],target['pid'])
                self.assertIn(target['id'],jumped['records']['sections'])
                (directory/'workbench-parity.json').write_text(json.dumps(jumped,indent=2),encoding='utf-8')
                self.assertEqual(hashlib.sha256(sample.read_bytes()).hexdigest(), source_hash)
                (directory / 'verified.json').write_text(json.dumps({'passed':True,'capture':capture},indent=2),encoding='utf-8')
            finally:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill(); process.wait(timeout=5)
        diagnostics = (directory / 'application.log').read_text(encoding='utf-8')
        for error in ['ReferenceError:', 'TypeError:', 'QQmlApplicationEngine failed']:
            self.assertNotIn(error, diagnostics)

    def test_qt_live_diagnostics(self):
        self.exercise('qt', os.environ.get('SHOWPSISI_QT'))

    def test_tauri_live_diagnostics(self):
        self.exercise('tauri', os.environ.get('SHOWPSISI_TAURI'))


if __name__ == '__main__':
    unittest.main()
