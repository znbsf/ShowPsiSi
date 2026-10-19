"""Compiled Qt topology flows against deterministic wire input and the real core.

Offscreen coverage does not establish native Windows interaction. No semantic
response is mocked: the proxy used for ordering tests only holds real replies.
"""
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import subprocess
import shutil
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'scripts'), str(ROOT / 'scripts/ci')]
from core_client import Core
from ui_agent import request
from qt_evidence import retain_qt_evidence
from test_qt_ui import native_environment
from topology_fixture import parts, delivery_parts, write_ts, pat, sdt, nit


class QtTopologyTests(unittest.TestCase):
    @contextmanager
    def application(self, profile='dvb', sections=None, theme='dark', compact=False, proxy=None):
        binary = Path(os.environ.get('SHOWPSISI_QT', ROOT / 'build/cloud/bin/showpsisi-qt'))
        if not binary.is_file():
            self.skipTest('Build the native Qt target or set SHOWPSISI_QT')
        with tempfile.TemporaryDirectory(prefix='qt-topology-') as temp:
            directory = Path(temp)
            sample = write_ts(directory / 'topology.ts', sections or parts(profile))
            digest = hashlib.sha256(sample.read_bytes()).hexdigest()
            session, logpath = directory / 'session', directory / 'application.log'
            env = native_environment()
            env.update(SHOWPSISI_SAMPLE=str(sample), SHOWPSISI_AGENT_DIR=str(session),
                       SHOWPSISI_STANDARDS=profile, SHOWPSISI_SCRIPT='', SHOWPSISI_THEME=theme,
                       SHOWPSISI_TEST_SIZE='compact' if compact else '',
                       SHOWPSISI_SETTINGS_PATH=str(directory / 'settings.ini'))
            if proxy:
                env.update(SHOWPSISI_REAL_CORE=env['SHOWPSISI_CORE'], SHOWPSISI_CORE=sys.executable,
                           SHOWPSISI_CORE_ARGS_JSON=json.dumps(['-u', str(ROOT / 'tests/fixtures/qt_topology_proxy.py')]),
                           SHOWPSISI_TOPOLOGY_PROXY=proxy, SHOWPSISI_TOPOLOGY_GATE=str(directory / 'held.json'))
            evidence = Path(os.environ.get('SHOWPSISI_QT_TEST_ARTIFACTS', ROOT / 'artifacts/qt-topology-tests'))
            target = evidence / self._testMethodName / (profile+'-'+theme+('-compact' if compact else ''))
            retained = [logpath, sample, directory / 'state.json', directory / 'held.json', directory / 'screenshot.png', directory / 'capture-manifest.json', directory / 'captured-state.json']
            with retain_qt_evidence(target, retained):
                with logpath.open('w', encoding='utf-8') as log:
                    process = subprocess.Popen([str(binary)], env=env, cwd=ROOT, stdout=log, stderr=log)
                    self.session, self.process = session, process
                    try:
                        self.wait(lambda s:s['settled'] and bool(s.get('inspection', {}).get('id')))
                        yield directory, sample
                        self.assertEqual(hashlib.sha256(sample.read_bytes()).hexdigest(), digest)
                        state = self.wait(lambda s:s['settled'])
                        (directory / 'state.json').write_text(json.dumps(state, indent=2), encoding='utf-8')
                        capture = request(session, 'capture')
                        capture_dir = Path(capture['directory'])
                        for source_name, target_name in (('screenshot.png','screenshot.png'),('manifest.json','capture-manifest.json'),('state.json','captured-state.json')):
                            shutil.copyfile(capture_dir / source_name, directory / target_name)
                    finally:
                        if process.poll() is None:
                            process.terminate()
                        try:
                            process.wait(5)
                        except subprocess.TimeoutExpired:
                            process.kill(); process.wait(5)
                diagnostics = logpath.read_text(encoding='utf-8')
                for error in ('ReferenceError:', 'TypeError:', 'Cannot assign', 'Unable to assign', 'QQmlApplicationEngine failed'):
                    self.assertNotIn(error, diagnostics)

    def wait(self, predicate, timeout=30):
        deadline, state = time.monotonic()+timeout, None
        while time.monotonic()<deadline:
            self.assertIsNone(self.process.poll(), 'Qt exited before state settled')
            if (self.session / 'session.json').exists():
                state = request(self.session, 'snapshot')
                if predicate(state):
                    return state
            time.sleep(.04)
        self.fail('Qt state did not meet predicate: '+json.dumps(state))

    def action(self, name, **values):
        return request(self.session, 'action', dict(name=name, **values))

    def topology(self):
        self.action('select_tab', value='Topology')
        return self.wait(lambda s:s['settled'] and bool(s['topology']['data'].get('schema_version')))

    def test_three_profile_graphs_all_sources_and_precise_navigation(self):
        for profile in ('dvb', 'atsc', 'isdb-japan'):
            with self.subTest(profile=profile), self.application(profile) as (_, sample):
                state = self.topology()
                core = Core()
                try:
                    core.call('analyze', {'path':str(sample), 'standards':profile})
                    expected = core.call('query_topology', {'limit':500})
                finally:
                    core.close()
                self.assertEqual(state['topology']['data'], expected)
                self.assertTrue(state['topology']['summary'])
                self.assertEqual(state['topology']['selected_node'], '')
                nodes = state['topology']['data']['nodes']
                node = next(n for n in nodes if n['object_type']==('virtual_channel' if profile=='atsc' else 'service'))
                self.action('topology_select', id=node['node_id'])
                state = self.wait(lambda s:s['topology']['selected_node']==node['node_id'])
                sources = state['topology']['sources']
                self.assertGreaterEqual(len(sources), len(node['evidence']))
                self.assertEqual({json.dumps(v,sort_keys=True) for v in node['evidence']},
                                 {json.dumps(v['ref'],sort_keys=True) for v in sources if v['edge_id'] is None})
                packet = state['packet']
                for index, source in enumerate(sources):
                    with self.subTest(profile=profile, source=index):
                        self.action('topology_source', index=index)
                        state = self.wait(lambda s:s['settled'])
                        evidence, resolution = source['ref'], state['topology']['resolution']
                        self.assertEqual(state['inspection']['id'], evidence['section_id'])
                        self.assertEqual(state['inspection']['cutoff'], evidence['at_packet'])
                        self.assertEqual(state['inspection']['revision'], evidence['analysis_revision'])
                        self.assertEqual(state['topology']['active_evidence'], evidence)
                        self.assertEqual(state['topology']['selected_node'], node['node_id'])
                        self.assertEqual(state['packet'], packet)
                        self.assertEqual(state['evidence_scope'], 'section')
                        self.assertIn(resolution['status'], ('resolved', 'fallback'))
                        self.assertEqual(resolution['precision'], evidence['locator']['precision'])
                        path = resolution['path'].removeprefix('section/')
                        self.assertIn(path, [row['path'] for row in state['tree']])
                        controls={c['id']:c for c in state['controls']}
                        target=controls.get('tree:'+path)
                        self.assertIsNotNone(target, 'Located anchor must be materialized in the viewport')
                        tree=controls['fieldTree']['bounds'];row=target['bounds']
                        self.assertGreaterEqual(row['y'],tree['y']-1)
                        self.assertLessEqual(row['y']+row['height'],tree['y']+tree['height']+1)
                        self.action('set_view', value='Hex')
                        hex_state = self.wait(lambda s:s['inspector']=='Hex')
                        if resolution['byte_range']:
                            self.assertTrue(hex_state['inspection']['hex_selection'])
                        self.action('topology_back')
                        state = self.wait(lambda s:s['topology']['summary'])
                        self.assertEqual(state['topology']['selected_node'], node['node_id'])
                self.action('topology_source', index=0)
                self.wait(lambda s:s['settled'])
                for view in ('Structure','Hex','XML','Decoded','Metadata','References'):
                    self.action('set_view', value=view)
                    self.assertEqual(self.wait(lambda s:s['settled'])['inspector'], view)
                self.action('topology_tables')
                shown = self.wait(lambda s:s['tab']=='Tables')
                self.assertIn(shown['inspection']['id'], shown['records']['sections'])
                self.assertEqual(shown['packet'], packet)
                self.action('topology_back')
                restored = self.wait(lambda s:s['settled'] and s['tab']=='Topology')
                self.assertEqual(restored['topology']['active_evidence'], sources[0]['ref'])
                self.action('topology_back')
                self.wait(lambda s:s['topology']['summary'])

    def test_delivery_parameters_and_catalog_candidates_keep_wire_sources_separate(self):
        with self.application(sections=delivery_parts()):
            state = self.topology()
            nodes = state['topology']['data']['nodes']
            delivery = [n for n in nodes if n['object_type']=='delivery_parameters']
            candidates = [n for n in nodes if n['object_type']=='satellite_candidate']
            self.assertEqual(len(delivery), 3)
            self.assertEqual(len(candidates), 2)
            for node in delivery+candidates:
                self.action('topology_select', id=node['node_id'])
                state = self.wait(lambda s:s['topology']['selected_node']==node['node_id'])
                summary = next(c for c in state['controls'] if c['id']=='topologySummaryText')['text']
                if node in candidates:
                    self.assertIn('Catalog provenance', summary)
                    self.assertEqual(node['reference_sources'], next(n for n in state['topology']['data']['nodes'] if n['node_id']==node['node_id'])['reference_sources'])
                    self.assertIn('unresolved', summary.lower())
                sources = state['topology']['sources']
                self.assertTrue(sources)
                for index, source in enumerate(sources):
                    self.assertIn('section_id', source['ref'])
                    self.assertNotIn('catalog', source['ref'])
                    self.action('topology_source', index=index)
                    shown = self.wait(lambda s:s['settled'])
                    self.assertEqual(shown['inspection']['id'], source['ref']['section_id'])
                    self.assertEqual(shown['topology']['resolution']['precision'], source['ref']['locator']['precision'])
                    self.assertEqual(shown['topology']['selected_node'], node['node_id'])
                    self.action('topology_back')
                    self.wait(lambda s:s['topology']['summary'])

    def test_focus_selection_search_themes_compact_and_missing_cutoff(self):
        for theme in ('dark','light'):
            with self.subTest(theme=theme), self.application(theme=theme, compact=True):
                state = self.topology()
                root = state['topology']['rows'][0]['node_id']
                self.action('topology_focus', id=root)
                self.action('topology_key', value='Return')
                state = self.wait(lambda s:s['topology']['selected_node']==root)
                self.action('topology_key', value='Right')
                self.action('topology_key', value='Down')
                state = self.wait(lambda s:s['topology']['focused_node']!=root)
                self.assertEqual(state['topology']['selected_node'], root)
                self.assertIsNone(state['topology']['active_evidence'])
                self.action('topology_key', value='Return')
                self.wait(lambda s:s['topology']['selected_node']==s['topology']['focused_node'])
                self.action('topology_search', value='0x0064')
                state = self.wait(lambda s:s['topology']['search']=='0x0064')
                self.assertTrue(any(r.get('node',{}).get('object_type')=='service' for r in state['topology']['rows']))
                self.assertTrue(any(r.get('node',{}).get('object_type')=='network' for r in state['topology']['rows']))
                self.action('topology_key', value='Ctrl+K')
                self.action('topology_key', value='Escape')
                state = self.wait(lambda s:not s['topology']['search'])
                self.assertEqual(state['theme'], theme)
                controls = {c['id']:c for c in state['controls']}
                for key in ('tab_Services','tab_Topology','tab_Tables','tab_EPG','tab_Issues','tab_Changes'):
                    self.assertTrue(controls[key]['visible'])
                    r=controls[key]['bounds'];self.assertLessEqual(r['x']+r['width'], state['viewport']['width'])
                service = next(n for n in state['topology']['data']['nodes'] if n['object_type']=='service')
                self.action('topology_select', id=service['node_id'])
                self.action('select_snapshot', packet=0)
                state = self.wait(lambda s:s['settled'] and s['topology']['data'].get('at_packet')==0)
                self.assertIsNone(state['topology']['active_evidence'])
                self.assertNotIn(service['node_id'], [n['node_id'] for n in state['topology']['data']['nodes']])
                self.assertIn('not observed',state['topology']['error'])
                self.action('select_snapshot', packet=-1)
                state = self.wait(lambda s:s['settled'] and s['topology']['data'].get('at_packet')==3)
                self.assertFalse(state['topology']['stale'])
                self.assertEqual(state['topology']['selected_node'], service['node_id'])

    def test_large_graph_load_more_and_scoped_search(self):
        # 510 independent SDT services require paging, without inventing PMTs.
        entries=[(i+100,'Service '+str(i)) for i in range(510)]
        sections=[pat(programs=()), nit()]
        for index in range(0,len(entries),15):
            sections.append(sdt(services=entries[index:index+15],number=index//15,last=33))
        with self.application(sections=sections):
            state=self.topology()
            self.assertTrue(state['topology']['data']['page']['has_more'])
            self.assertEqual(len(state['topology']['data']['nodes']),500)
            self.action('topology_search',value='Service 509')
            state=self.wait(lambda s:s['topology']['search']=='Service 509')
            self.assertIn('loaded objects only',next(c['text'] for c in state['controls'] if c['id']=='topologyContext'))
            self.action('topology_more')
            state=self.wait(lambda s:s['settled'] and not s['topology']['data']['page']['has_more'])
            self.assertEqual(len(state['topology']['data']['nodes']),state['topology']['data']['page']['total'])
            self.assertTrue(any(r.get('node',{}).get('label')=='Service 509' for r in state['topology']['rows']))

    def test_unknown_profile_keeps_raw_evidence_accessible(self):
        with self.application(profile='auto', sections=parts('atsc')):
            state=self.topology()
            self.assertTrue(state['topology']['data']['counts']['raw_sections'])
            self.action('select_tab',value='Tables')
            state=self.wait(lambda s:s['tab']=='Tables')
            self.assertTrue(state['records']['sections'])

    def test_related_section_preserves_evidence_cutoff_and_back(self):
        sections=parts('dvb')[:2]+[sdt(number=0,last=1),sdt(services=((101,'Related service'),),number=1,last=1),nit()]
        with self.application(sections=sections):
            state=self.topology()
            service=next(n for n in state['topology']['data']['nodes'] if n['object_type']=='service' and n['identity']['service_id']==100)
            other=next(n for n in state['topology']['data']['nodes'] if n['object_type']=='service' and n['identity']['service_id']==101)
            section=next(e['section_id'] for e in other['evidence'] if e['assertion_key']=='name')
            self.action('topology_select',id=service['node_id'])
            state=self.wait(lambda s:bool(s['topology']['sources']))
            index=next(i for i,s in enumerate(state['topology']['sources']) if s['ref']['assertion_key']=='name')
            self.action('topology_source',index=index)
            original=self.wait(lambda s:s['settled'])
            self.action('topology_sibling',id=section)
            state=self.wait(lambda s:s['settled'])
            self.assertEqual(state['inspection']['id'],section)
            self.assertEqual(state['inspection']['cutoff'],original['inspection']['cutoff'])
            self.assertEqual(state['packet'],original['packet'])
            self.assertFalse(state['topology']['summary'])
            self.assertEqual(state['topology']['resolution']['precision'],'section')
            self.assertEqual(state['topology']['active_evidence'],original['topology']['active_evidence'])
            self.action('topology_back')
            state=self.wait(lambda s:s['settled'])
            self.assertEqual(state['inspection']['id'],original['inspection']['id'])
            self.assertEqual(state['topology']['resolution']['precision'],'field')
            self.assertIsNone(state['topology']['section_context'])

    def test_backend_disconnect_settles_pending_topology(self):
        with self.application(proxy='disconnect'):
            self.action('select_tab',value='Topology')
            state=self.wait(lambda s:s['settled'] and s['diagnostics']['backend']=='disconnected')
            self.assertFalse(state['topology']['loading'])
            self.assertEqual(state['topology']['data'],{})
            self.assertIsNone(state['topology']['active_evidence'])
            self.assertIn('disconnected',state['topology']['error'])

    def test_comparison_topology_preserves_workspace_and_return_target(self):
        sections=parts('dvb')+[sdt(services=((100,'Later name'),),version=2)]
        with self.application(sections=sections):
            initial=self.wait(lambda s:s['settled'])
            self.action('compare_snapshots',**{'from':2,'to':4})
            state=self.wait(lambda s:s['settled'] and bool(s['comparison_context']['data'].get('changes')))
            index=next(i for i,c in enumerate(state['comparison_context']['data']['changes']) if c['kind']=='services' and c.get('before'))
            self.action('comparison_source',index=index,side='before')
            state=self.wait(lambda s:s['settled'] and s['inspection']['cutoff']==2)
            self.action('comparison_topology')
            state=self.wait(lambda s:s['settled'] and s['topology']['data'].get('at_packet')==2)
            self.assertEqual(state['packet'],initial['packet'])
            self.assertEqual(state['topology']['scope'],'Comparison A')
            service=next(n for n in state['topology']['data']['nodes'] if n['object_type']=='service')
            self.action('topology_select',id=service['node_id'])
            self.action('topology_source',index=0)
            state=self.wait(lambda s:s['settled'])
            self.assertEqual(state['inspection']['cutoff'],2)
            self.assertFalse(state['topology']['can_reveal'])
            self.action('topology_tables')
            self.assertEqual(self.wait(lambda s:s['settled'])['tab'],'Topology')
            self.action('topology_back')
            self.wait(lambda s:s['topology']['summary'])
            self.action('topology_back')
            state=self.wait(lambda s:s['settled'] and s['tab']=='Changes')
            self.assertEqual(state['inspection']['cutoff'],2)
            self.assertEqual(state['comparison_context']['side'],'before')
            self.action('select_tab',value='Services')
            state=self.wait(lambda s:s['settled'])
            self.assertEqual(state['packet'],initial['packet'])
            self.assertEqual(state['inspection']['id'],initial['inspection']['id'])

    def test_read_error_retains_stale_graph_then_retry_recovers(self):
        with self.application(proxy='error'):
            initial=self.topology()
            self.action('topology_reload')
            failed=self.wait(lambda s:s['settled'] and bool(s['topology']['error']))
            self.assertEqual(failed['topology']['data'],initial['topology']['data'])
            self.assertTrue(failed['topology']['stale'])
            self.assertIn('Injected topology read failure',failed['topology']['error'])
            self.action('topology_reload')
            recovered=self.wait(lambda s:s['settled'] and not s['topology']['error'])
            self.assertFalse(recovered['topology']['stale'])

    def test_delayed_topology_cannot_replace_new_cutoff(self):
        with self.application(proxy='topology') as (directory,_):
            self.action('select_tab',value='Topology')
            self.wait(lambda s:s['topology']['loading'] and (directory/'held.json').exists())
            self.action('select_snapshot',packet=0)
            state=self.wait(lambda s:s['settled'] and s['topology']['data'].get('at_packet')==0)
            self.assertEqual(state['packet'],0)
            self.assertFalse(state['topology']['stale'])
            self.assertFalse(state['topology']['error'])

    def test_delayed_evidence_cannot_replace_new_source(self):
        with self.application(proxy='inspect') as (directory,_):
            state=self.topology()
            service=next(n for n in state['topology']['data']['nodes'] if n['object_type']=='service')
            self.action('topology_select',id=service['node_id'])
            state=self.wait(lambda s:s['topology']['sources'])
            sources=state['topology']['sources']
            other=next(i for i,s in enumerate(sources) if s['ref']['section_id']!=sources[0]['ref']['section_id'])
            self.action('topology_source',index=0)
            self.wait(lambda s:bool(s['topology']['active_evidence']) and (directory/'held.json').exists())
            self.action('topology_source',index=other)
            state=self.wait(lambda s:s['settled'])
            self.assertEqual(state['inspection']['id'],sources[other]['ref']['section_id'])
            self.assertEqual(state['topology']['active_evidence'],sources[other]['ref'])
            self.assertNotEqual(state['topology']['resolution']['status'],'mismatch')


if __name__=='__main__':
    unittest.main()
