"""Compiled Qt local-document workbench, driven through the real C++ importer."""
import hashlib
import json
import unittest
from pathlib import Path
import test_qt_topology as topology_qt
from dvbi_fixture import fixture, many_services, document, service
from ui_agent import request


class QtDvbiTests(unittest.TestCase):
    application = topology_qt.QtTopologyTests.application
    wait = topology_qt.QtTopologyTests.wait
    action = topology_qt.QtTopologyTests.action

    def imported(self, directory, raw=None):
        path=directory/'service-list.xml';path.write_bytes(fixture() if raw is None else raw)
        self.action('dvbi_import',path=str(path))
        state=self.wait(lambda s:s['settled'] and bool(s['dvbi']['data'].get('page')))
        self.assertEqual(state['input_kind'],'dvbi')
        self.assertEqual(state['dvbi']['metadata']['source']['sha256'],hashlib.sha256(path.read_bytes()).hexdigest())
        self.assertFalse(state['dvbi']['error'],state['dvbi']['error'])
        return state,path

    def test_document_import_sources_and_ts_restoration_in_both_themes(self):
        for theme in ('dark','light'):
            with self.subTest(theme=theme),self.application(theme=theme) as (directory,ts):
                before=self.wait(lambda s:s['settled']);state,path=self.imported(directory)
                lcn_ids={n['node_id'] for n in state['dvbi']['data']['nodes'] if n['object_type']=='lcn_table'}
                labels=[r['text'] for r in state['dvbi']['row_identities'] if r['id'] in lcn_ids]
                self.assertEqual(len(labels),2);self.assertEqual(len(set(labels)),2);self.assertTrue(all('Region ref' in label and 'XML e' in label for label in labels))
                for node in state['dvbi']['data']['nodes']:
                    self.action('dvbi_select',id=node['node_id'])
                    selected=self.wait(lambda s:s['dvbi']['selected']==node['node_id'])
                    self.assertIsNone(selected['dvbi']['evidence'])
                    self.assertEqual(selected['dvbi']['view'],'Summary')
                    for index,ref in enumerate(selected['dvbi']['sources']):
                        self.action('dvbi_source',index=index)
                        source=self.wait(lambda s:s['settled'] and s['dvbi']['evidence']==ref)
                        result=source['dvbi']['inspection'];resolution=source['dvbi']['resolution']
                        self.assertEqual(result['element']['element_id'],ref['element_id'])
                        self.assertEqual(result['document_revision'],ref['document_revision'])
                        self.assertEqual(result['source']['sha256'],ref['source_sha256'])
                        self.assertEqual(resolution['status'],'resolved')
                        self.assertEqual(resolution['precision'],ref['precision'])
                        self.action('dvbi_view',value='XML')
                        self.wait(lambda s:s['dvbi']['xml_selection']=='<')
                        self.action('dvbi_back')
                        self.wait(lambda s:s['dvbi']['view']=='Summary')
                self.action('input_kind',value='ts')
                restored=self.wait(lambda s:s['input_kind']=='ts')
                for key in ('source','selected','packet','inspection','tab','inspector'):
                    self.assertEqual(restored[key],before[key],key)
                self.action('input_kind',value='dvbi')
                self.assertEqual(self.wait(lambda s:s['input_kind']=='dvbi')['dvbi']['metadata']['source']['path'],str(path))

    def test_failed_replace_preserves_document_and_unknown_namespace_tree_is_bounded(self):
        with self.application() as (directory,ts):
            state,path=self.imported(directory)
            original=state['dvbi']['metadata'];bad=directory/'rejected.xml';bad.write_bytes(b'<!DOCTYPE x><x/>')
            self.action('dvbi_import',path=str(bad))
            failed=self.wait(lambda s:s['settled'] and bool(s['dvbi']['error']))
            self.assertEqual(failed['dvbi']['metadata'],original)
            loaded=next(c for c in failed['controls'] if c['id']=='dvbiLoadedSource')['text']
            self.assertIn(str(path),loaded);self.assertIn(original['source']['sha256'],loaded)
            self.assertEqual(next(c for c in failed['controls'] if c['id']=='dvbiPath')['text'],str(bad))
            unknown=b'<x xmlns="urn:unrecognized">'+b'<child a="&lt;script&gt;">plain</child>'*405+b'</x>'
            path.write_bytes(unknown);self.action('dvbi_import',path=str(path))
            raw=self.wait(lambda s:s['settled'] and s['dvbi']['metadata'].get('document_revision')==2)
            self.assertEqual(raw['dvbi']['metadata']['status'],'unsupported');self.assertEqual(raw['dvbi']['data']['nodes'],[])
            self.action('dvbi_root');root=self.wait(lambda s:s['settled'] and bool(s['dvbi']['inspection'].get('element')))
            self.assertEqual(len(root['dvbi']['inspection']['child_summaries']),200)
            self.assertEqual(root['dvbi']['inspection']['child_page']['total'],405)
            self.action('dvbi_children',offset=400)
            last=self.wait(lambda s:s['settled'] and s['dvbi']['inspection']['child_page']['offset']==400)
            self.assertEqual(len(last['dvbi']['inspection']['child_summaries']),5)
            child=last['dvbi']['inspection']['child_summaries'][0]
            self.action('dvbi_child',id=child['element_id'])
            child_state=self.wait(lambda s:s['settled'] and s['dvbi']['inspection']['element']['element_id']==child['element_id'])
            self.assertEqual(child_state['dvbi']['inspection']['element']['attributes'][0]['value'],'<script>')
            self.action('dvbi_back');self.assertEqual(self.wait(lambda s:s['settled'])['dvbi']['inspection']['child_page']['offset'],400)

    def test_large_list_search_expansion_and_document_byte_pages(self):
        with self.application(compact=True) as (directory,ts):
            state,path=self.imported(directory,many_services(510).replace(b'Programme 509',b'OnlyUnloadedServiceCanary'))
            self.assertEqual(len(state['dvbi']['data']['nodes']),500)
            self.assertEqual(state['dvbi']['data']['page']['total'],511)
            self.action('dvbi_search',value='OnlyUnloadedServiceCanary')
            self.assertFalse(self.wait(lambda s:s['dvbi']['search']=='OnlyUnloadedServiceCanary')['dvbi']['rows'])
            self.action('dvbi_more')
            full=self.wait(lambda s:s['settled'] and len(s['dvbi']['data']['nodes'])==511 and bool(s['dvbi']['rows']))
            self.assertTrue(full['dvbi']['rows']);target=next(n for n in full['dvbi']['data']['nodes'] if n['label']=='OnlyUnloadedServiceCanary')
            self.action('dvbi_select',id=target['node_id']);self.wait(lambda s:s['dvbi']['selected']==target['node_id'])
            self.action('dvbi_source',index=0);opened=self.wait(lambda s:s['settled'] and bool(s['dvbi']['inspection'].get('element')))
            source=opened['dvbi']['inspection']['original_source'];self.assertGreater(source['offset'],0)
            self.assertEqual(bytes.fromhex(source['data']),path.read_bytes()[source['offset']:source['offset']+source['length']])
            self.action('dvbi_view',value='XML');self.wait(lambda s:s['dvbi']['xml_selection']=='<')
            self.action('dvbi_page',delta=-1);previous=self.wait(lambda s:s['settled'] and s['dvbi']['inspection']['original_source']['offset']==source['offset']-4096)
            self.assertIsNone(previous['dvbi']['inspection']['original_source']['element_start_character'])
            self.action('dvbi_jump');self.wait(lambda s:s['settled'] and s['dvbi']['xml_selection']=='<')

    def test_theme_source_capture_and_ts_rescan_keep_document_session(self):
        for theme in ('dark','light'):
            with self.subTest(theme=theme),self.application(theme=theme,compact=True) as (directory,ts):
                state,path=self.imported(directory);node=state['dvbi']['data']['nodes'][1]
                self.action('dvbi_select',id=node['node_id']);self.action('dvbi_source',index=0)
                opened=self.wait(lambda s:s['settled'] and bool(s['dvbi']['inspection'].get('element')))
                self.action('dvbi_view',value='XML');self.wait(lambda s:s['dvbi']['xml_selection']=='<')
                self.action('dvbi_focus',id=node['node_id']);self.action('topology_key',value='F6')
                self.wait(lambda s:any(c['id']=='dvbiOriginalXml' and c['focused'] for c in s['controls']))
                self.action('topology_key',value='F6');self.wait(lambda s:any(c['id']=='dvbiList' and c['focused'] for c in s['controls']))
                self.action('input_kind',value='ts');self.action('rescan')
                self.wait(lambda s:s['settled'] and s['inspection'].get('revision',0)>opened['inspection']['revision'])
                self.action('input_kind',value='dvbi');restored=self.wait(lambda s:s['input_kind']=='dvbi')
                self.assertEqual(restored['dvbi']['metadata'],opened['dvbi']['metadata']);self.assertEqual(restored['dvbi']['inspection'],opened['dvbi']['inspection'])
                self.assertEqual(restored['dvbi']['view'],'XML');self.assertEqual(restored['dvbi']['xml_selection'],'<')
                for control in ('dvbiView_XML','dvbiSourceJump','dvbiOpen'):
                    c=next(c for c in restored['controls'] if c['id']==control);self.assertTrue(c['visible']);self.assertGreaterEqual(c['bounds']['x'],0);self.assertLessEqual(c['bounds']['x']+c['bounds']['width'],1000)

    def test_pending_document_query_owns_loading_and_blocks_replacement(self):
        with self.application(proxy='dvbi_delay_query') as (directory,ts):
            path=directory/'first.xml';path.write_bytes(fixture());other=directory/'second.xml';other.write_bytes(document(service(name='Replacement')))
            self.action('dvbi_import',path=str(path))
            loading=self.wait(lambda s:s['dvbi']['operation']=='query' and (directory/'held.json').exists())
            for name in ('dvbiOpen','dvbiImport','inputKind'):
                self.assertFalse(next(c for c in loading['controls'] if c['id']==name)['enabled'])
            self.action('dvbi_import',path=str(other))
            with self.assertRaisesRegex(RuntimeError,'Unsupported UI action'):self.action('input_kind',value='ts')
            held=self.wait(lambda s:s['dvbi']['operation']=='query');self.assertEqual(held['input_kind'],'dvbi')
            self.assertEqual(held['dvbi']['metadata']['source']['path'],str(path))
            (directory/'held.release').write_text('release',encoding='utf-8')
            settled=self.wait(lambda s:s['settled'] and bool(s['dvbi']['data'].get('nodes')))
            self.assertEqual(settled['dvbi']['metadata']['document_revision'],1);self.assertFalse(settled['dvbi']['error'])

    def test_query_and_source_failures_have_explicit_retry(self):
        for mode in ('dvbi_query_error','dvbi_inspect_error'):
            with self.subTest(mode=mode),self.application(proxy=mode) as (directory,ts):
                path=directory/'input.xml';path.write_bytes(fixture())
                self.action('dvbi_import',path=str(path))
                state=self.wait(lambda s:s['settled'] and bool(s['dvbi']['metadata']))
                if mode=='dvbi_query_error':
                    self.assertIn('Injected',state['dvbi']['error']);self.assertEqual(state['dvbi']['data'],{})
                    self.action('dvbi_reload');state=self.wait(lambda s:s['settled'] and bool(s['dvbi']['data'].get('nodes')))
                node=state['dvbi']['data']['nodes'][1];self.action('dvbi_select',id=node['node_id']);self.action('dvbi_source',index=0)
                state=self.wait(lambda s:s['settled'])
                if mode=='dvbi_inspect_error':
                    self.assertIn('Injected',state['dvbi']['error']);self.assertEqual(state['dvbi']['inspection'],{})
                    self.action('dvbi_retry');state=self.wait(lambda s:s['settled'] and bool(s['dvbi']['inspection'].get('element')))
                self.assertEqual(state['dvbi']['resolution']['status'],'resolved');self.assertFalse(state['dvbi']['error'])

    def test_stale_source_and_disconnect_are_explicit(self):
        for mode in ('dvbi_mismatch','dvbi_disconnect'):
            with self.subTest(mode=mode),self.application(proxy=mode) as (directory,ts):
                state,path=self.imported(directory);node=state['dvbi']['data']['nodes'][1]
                self.action('dvbi_select',id=node['node_id']);self.action('dvbi_source',index=0)
                state=self.wait(lambda s:s['settled'] and bool(s['dvbi']['error']))
                self.assertTrue(state['dvbi']['stale']);self.assertEqual(state['dvbi']['inspection'],{})
                self.assertEqual(state['dvbi']['metadata']['source']['path'],str(path))
                if mode=='dvbi_mismatch':
                    self.action('dvbi_import',path=str(path));state=self.wait(lambda s:s['settled'] and s['dvbi']['metadata'].get('document_revision')==2)
                    self.assertFalse(state['dvbi']['stale']);self.assertFalse(state['dvbi']['error'])

    def test_keyboard_focus_and_unicode_original_xml(self):
        raw=fixture();prefix=b'\xef\xbb\xbf'+raw.split(b'\n',1)[0]+b'\r\n<!-- \xf0\x9f\x93\xba -->\r\n';raw=prefix+raw.split(b'\n',1)[1]
        with self.application() as (directory,ts):
            state,path=self.imported(directory,raw);node=state['dvbi']['data']['nodes'][1]
            self.action('dvbi_focus',id=node['node_id']);self.action('topology_key',value='Return')
            selected=self.wait(lambda s:s['dvbi']['selected']==node['node_id']);self.assertIsNone(selected['dvbi']['evidence']);self.assertEqual(selected['dvbi']['inspection'],{})
            self.action('dvbi_source',index=0);opened=self.wait(lambda s:s['settled'] and bool(s['dvbi']['inspection'].get('element')))
            source=opened['dvbi']['inspection']['original_source'];self.assertEqual(source['text'].encode(),raw)
            self.action('dvbi_view',value='XML');self.wait(lambda s:s['dvbi']['xml_selection']=='<')
            self.action('topology_key',value='Alt+Left');self.wait(lambda s:s['dvbi']['view']=='Summary')
            self.assertTrue(path.read_bytes().startswith(b'\xef\xbb\xbf'))

if __name__=='__main__':unittest.main()
