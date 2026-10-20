"""Real Chromium + real native-engine integration tests (not native Tauri tests).

SHOWPSISI_CORE=/path/to/core python -m unittest discover -s tests -p test_web_ui.py -v
Requires Playwright Python and Chromium (PLAYWRIGHT_CHROMIUM_EXECUTABLE optional).
Screenshots: artifacts/web-ui-tests/. Every response is produced by the native core.
Cancellation tests also use the compile-only showpsisi-core-test checkpoint helper.
Transport gates delay/replay authentic responses. Positive results are never
fabricated; foreign/malformed event tests intentionally inject invalid envelopes.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from urllib.request import Request, urlopen
from urllib.error import HTTPError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from cloud_preview import Bridge, Server

class BrowserTests(unittest.TestCase):
    def dvbi_import(self,raw=None,name='dvbi.xml'):
        from dvbi_fixture import fixture
        path=self.output/name;path.write_bytes(fixture() if raw is None else raw)
        self.page.locator('#input-kind').select_option('dvbi')
        self.page.locator('#dvbi-source').fill(str(path));self.page.locator('#dvbi-import').click()
        self.page.wait_for_function('()=>window.showpsisi.getUiState().dvbi.metadata && !window.showpsisi.getUiState().dvbi.importing && !window.showpsisi.getUiState().dvbi.loading')
        return path

    def test_dvbi_independent_session_sources_unknowns_and_original_bytes(self):
        from dvbi_fixture import fixture
        self.topology_source();self.select_topology_service();p=self.page
        p.locator('[data-topology-source]').filter(has_text='name').first.click()
        p.wait_for_function('()=>window.showpsisi.getUiState().settled')
        before=p.evaluate('({state:window.showpsisi.getState(),detail:window.showpsisi.getDetail(),topology:window.showpsisi.getUiState().topology})')
        widths=p.evaluate('({left:document.querySelector("#split-left").getAttribute("aria-valuenow"),right:document.querySelector("#split-right").getAttribute("aria-valuenow")})')
        requests=[];p.on('request',lambda r:requests.append(r.url))
        path=self.dvbi_import();self.assertEqual(p.evaluate('window.showpsisi.getDvbi().nodes.length'),13)
        p.keyboard.press('Control+k');self.assertEqual(p.evaluate('document.activeElement.id'),'dvbi-search')
        self.assertFalse(p.locator('#reset-layout').is_visible())
        p.set_viewport_size({'width':1000,'height':900});p.set_viewport_size({'width':1440,'height':1000})
        self.assertFalse(p.locator('#timeline').is_visible());self.assertFalse(p.locator('#standards').is_visible())
        self.assertFalse(p.locator('#app > footer').is_visible());self.assertIn('Local XML · document revision',p.locator('#dvbi-footer').inner_text())
        first=p.locator('[data-dvbi-node]').first;first.focus();p.keyboard.press('ArrowRight');p.keyboard.press('ArrowDown')
        self.assertEqual(p.evaluate('window.showpsisi.getUiState().dvbi.selected'),'')
        p.keyboard.press('Enter');self.assertTrue(p.evaluate('window.showpsisi.getUiState().dvbi.selected'))
        for theme in ('dark','light'):
            if p.locator('html').get_attribute('data-theme')!=theme:p.locator('#theme-toggle').click()
            p.screenshot(path=str(self.artifacts/('dvbi-service-object-'+theme+'.png')),full_page=True)
        root=p.evaluate('window.showpsisi.getDvbi().nodes.find(n=>!n.parent_id).node_id')
        p.locator('[data-dvbi-node="'+root+'"]').click()
        for theme in ('dark','light'):
            if p.locator('html').get_attribute('data-theme')!=theme:p.locator('#theme-toggle').click()
            p.screenshot(path=str(self.artifacts/('dvbi-list-object-'+theme+'.png')),full_page=True)
        self.assertIn('Region ref north',p.locator('#dvbi-list').inner_text());self.assertIn('Region ref south',p.locator('#dvbi-list').inner_text())
        refs=p.evaluate('workbench.dvbiEvidence(window.showpsisi.getDvbi().nodes.find(n=>!n.parent_id))')
        index=next(i for i,r in enumerate(refs) if r['precision']=='attribute')
        p.locator('#dvbi-ref-'+str(index)).click();p.wait_for_function('()=>window.showpsisi.getUiState().dvbi.resolution?.precision==="attribute"')
        self.assertEqual(p.locator('[data-dvbi-highlight="attribute"]').count(),1)
        for view in ('text','hex','metadata','structure'):
            p.locator('[data-dvbi-view="'+view+'"]').click()
            if view=='text':self.assertEqual(p.locator('[data-dvbi-highlight="element-start"]').inner_text(),'<')
        p.keyboard.press('Alt+ArrowLeft');self.assertEqual(p.evaluate('document.activeElement.id'),'dvbi-ref-'+str(index))
        unknown=next(i for i,r in enumerate(refs) if 'FutureFeature' in r['path'])
        p.locator('#dvbi-ref-'+str(unknown)).click();p.wait_for_function('()=>window.showpsisi.getDvbiDetail()?.element.local_name==="FutureFeature"')
        self.assertIn('unknown extension',p.locator('#dvbi-inspector').inner_text())
        self.assertIn('0–0 / 0 children',p.locator('#dvbi-document').inner_text())
        for theme in ('light','dark'):
            if p.locator('html').get_attribute('data-theme')!=theme:p.locator('#theme-toggle').click()
            p.screenshot(path=str(self.artifacts/('dvbi-sources-'+theme+'.png')),full_page=True)
        self.assertFalse(any('example.invalid' in url for url in requests),'Signalling URLs must never be fetched')
        self.assertEqual(path.read_bytes(),fixture())
        p.locator('#input-kind').select_option('ts')
        after=p.evaluate('({state:window.showpsisi.getState(),detail:window.showpsisi.getDetail(),topology:window.showpsisi.getUiState().topology})')
        self.assertEqual(before,after);self.assertTrue(p.locator('#topology-back').is_visible())
        self.assertEqual(widths,p.evaluate('({left:document.querySelector("#split-left").getAttribute("aria-valuenow"),right:document.querySelector("#split-right").getAttribute("aria-valuenow")})'))
        self.assertTrue(p.locator('#reset-layout').is_visible());self.assertTrue(p.locator('#app > footer').is_visible())
        p.locator('#input-kind').select_option('dvbi');self.assertEqual(p.evaluate('window.showpsisi.getDvbiDetail().element.local_name'),'FutureFeature')
        p.locator('[data-dvbi-node]').first.click();self.assertIsNone(p.evaluate('window.showpsisi.getDvbiDetail()'))
        self.assertNotIn('Element navigation',p.locator('#dvbi-document').inner_text())

    def test_dvbi_failed_replacement_preserves_document_and_unsupported_raw_navigation(self):
        from dvbi_fixture import fixture
        p=self.page;path=self.dvbi_import();p.locator('[data-dvbi-node]').first.click();p.locator('#dvbi-root').click()
        p.wait_for_function('()=>window.showpsisi.getDvbiDetail()!=null')
        before=p.evaluate('({snapshot:window.showpsisi.getDvbi(),detail:window.showpsisi.getDvbiDetail(),selected:window.showpsisi.getUiState().dvbi.selected})')
        invalid=self.output/'bad.xml';invalid.write_text('<!DOCTYPE x [<!ENTITY e SYSTEM "file:///secret">]><x>&e;</x>')
        p.locator('#dvbi-source').fill(str(invalid));p.locator('#dvbi-import').click()
        p.wait_for_function('()=>!window.showpsisi.getUiState().dvbi.importing && !!window.showpsisi.getUiState().dvbi.error')
        self.assertEqual(before,p.evaluate('({snapshot:window.showpsisi.getDvbi(),detail:window.showpsisi.getDvbiDetail(),selected:window.showpsisi.getUiState().dvbi.selected})'))
        self.assertTrue(p.locator('#dvbi-message').inner_text())
        unsupported=self.output/'unknown.xml';unsupported.write_bytes(fixture(namespace='urn:unknown:edition'))
        p.locator('#dvbi-source').fill(str(unsupported));p.locator('#dvbi-import').click()
        p.wait_for_function('()=>window.showpsisi.getDvbi()?.status==="unsupported" && !window.showpsisi.getUiState().dvbi.importing')
        self.assertEqual(p.evaluate('window.showpsisi.getDvbi().nodes.length'),0)
        p.locator('#dvbi-root').click();p.wait_for_function('()=>window.showpsisi.getDvbiDetail()!=null')
        p.locator('[data-dvbi-view="text"]').click();self.assertIn('urn:unknown:edition',p.locator('#dvbi-inspector pre.evidence').inner_text())
        revision=p.evaluate('window.showpsisi.getDvbi().document_revision');p.locator('#dvbi-import').click()
        p.wait_for_function('(revision)=>window.showpsisi.getDvbi()?.document_revision>revision && !window.showpsisi.getUiState().dvbi.importing',arg=revision)

    def test_dvbi_pagination_children_and_utf8_original_source_marker(self):
        from dvbi_fixture import many_services
        p=self.page;raw=b'\xef\xbb\xbf'+many_services(510).replace(b'?>\n',b'?>\r\n<!-- prefix \xf0\x9f\x8e\xac -->\r\n').replace(b'\n',b'\r\n')
        self.dvbi_import(raw);self.assertEqual(p.evaluate('window.showpsisi.getDvbi().nodes.length'),500)
        p.locator('#dvbi-search').fill('Programme 509');self.assertEqual(p.locator('[data-dvbi-node]').count(),0)
        self.assertIn('loaded objects only',p.locator('#dvbi-loaded-note').inner_text())
        p.locator('#dvbi-more').click();p.wait_for_function('()=>window.showpsisi.getDvbi().nodes.length===511')
        self.assertGreater(p.locator('[data-dvbi-node]').count(),0)
        self.assertEqual(p.evaluate('new Set(window.showpsisi.getDvbi().nodes.map(n=>n.node_id)).size'),511)
        p.locator('#dvbi-root').click();p.wait_for_function('()=>window.showpsisi.getDvbiDetail()!=null')
        self.assertEqual(p.locator('#dvbi-document [data-dvbi-child]').count(),100)
        p.locator('#dvbi-child-next').click();p.wait_for_function('()=>window.showpsisi.getDvbiDetail()?.child_page.offset===100')
        p.locator('[data-dvbi-view="text"]').click()
        self.assertEqual(p.locator('[data-dvbi-highlight="element-start"]').inner_text(),'<')
        source=p.evaluate('window.showpsisi.getDvbiDetail().original_source')
        self.assertEqual(bytes.fromhex(source['data']),raw[source['offset']:source['offset']+source['length']])
        p.locator('#dvbi-source-next').click();p.wait_for_function('()=>window.showpsisi.getDvbiDetail()?.original_source.offset===4096')
        self.assertEqual(p.locator('[data-dvbi-highlight="element-start"]').count(),0)
        p.locator('#dvbi-element-start').click();p.wait_for_function('()=>window.showpsisi.getDvbiDetail()?.original_source.offset===window.showpsisi.getDvbiDetail()?.element.original_byte_offset')
        self.assertEqual(p.locator('[data-dvbi-highlight="element-start"]').inner_text(),'<')

    def test_dvbi_new_import_supersedes_pending_query(self):
        from dvbi_fixture import fixture,many_services
        self.gate_native_messages();self.dvbi_import(many_services(510));p=self.page
        p.evaluate('window.testGate.methods=["query_dvbi"]');p.locator('#dvbi-more').click()
        p.wait_for_function('()=>window.testGate.held.length===1')
        replacement=self.output/'replacement.xml';replacement.write_bytes(fixture())
        p.locator('#dvbi-source').fill(str(replacement));p.locator('#dvbi-import').click()
        p.wait_for_function('()=>window.testGate.held.length===2')
        p.evaluate('window.testGate.release("query_dvbi")')
        p.wait_for_function('()=>window.showpsisi.getDvbi()?.document_revision===2 && !window.showpsisi.getUiState().dvbi.importing && !window.showpsisi.getUiState().dvbi.loading')
        self.assertEqual(p.evaluate('window.showpsisi.getDvbi().nodes.length'),13)
        self.assertEqual(p.evaluate('window.showpsisi.getDvbi().source.path'),str(replacement))

    def test_dvbi_delayed_inspection_supersession_and_foreign_source_rejection(self):
        self.gate_native_messages();self.dvbi_import();p=self.page
        p.locator('[data-dvbi-node]').first.click()
        p.evaluate('window.testGate.methods=["inspect_dvbi"]')
        p.locator('[data-dvbi-ref]').first.click();p.wait_for_function('()=>window.testGate.held.length===1')
        self.assertIn('Loading XML',p.locator('#dvbi-inspector').inner_text())
        p.locator('#dvbi-root').click();p.wait_for_function('()=>window.testGate.held.length===2')
        p.evaluate('window.testGate.release("inspect_dvbi")')
        p.wait_for_function('()=>!window.showpsisi.getUiState().dvbi.inspectLoading')
        self.assertEqual(p.evaluate('window.showpsisi.getDvbiDetail().element.element_id'),'e0')
        p.locator('#dvbi-root').click();p.wait_for_function('()=>window.testGate.held.length===1')
        p.evaluate('window.testGate.held[0].event.payload.result.source.sha256="foreign";window.testGate.release("inspect_dvbi")')
        p.wait_for_function('()=>!!window.showpsisi.getUiState().dvbi.inspectError')
        self.assertIsNone(p.evaluate('window.showpsisi.getDvbiDetail()'))
        self.assertEqual(p.locator('[data-dvbi-highlight]').count(),0)
        p.evaluate('window.testGate.methods=[]');p.locator('#dvbi-retry-inspect').click()
        p.wait_for_function('()=>window.showpsisi.getDvbiDetail()!=null')
        self.bridge.proc.kill();self.bridge.proc.wait(timeout=5)
        p.wait_for_function('()=>!!window.showpsisi.getUiState().diagnostics.error')
        self.assertTrue(p.locator('#dvbi-root').is_disabled());self.assertTrue(p.locator('#dvbi-import').is_disabled())

    def test_protocol_source_actions_exact_anchor_fallback_and_back(self):
        from protocol_ui_fixture import protocol_ui_fixture
        p=self.page;path=self.output/'protocol-sources.ts';path.write_bytes(protocol_ui_fixture())
        p.locator('#standards').select_option('dvb');self.analyze(path)
        p.locator('[data-tab="Tables"]').click();p.locator('#search').fill('AIT');p.locator('#list .table-branch > summary').first.click()
        p.wait_for_function('()=>window.showpsisi.getDetail().table_id===0x74');p.locator('[data-view="metadata"]').click();p.locator('#protocol-next').click()
        source=p.locator('.protocol-sources').first;source.locator('summary').click()
        button=source.locator('[data-protocol-source]').first;button_id=button.get_attribute('id');section=p.evaluate('window.showpsisi.getDetail().id')
        button.click();p.wait_for_function('()=>window.showpsisi.getUiState().settled && window.showpsisi.getUiState().protocol_source.resolution!=null')
        self.assertIn(p.evaluate('window.showpsisi.getUiState().protocol_source.resolution.precision'),('field','container'))
        for view in ('hex','xml','decoded','metadata','references','tree'):p.locator('[data-view="'+view+'"]').click()
        p.locator('#protocol-back').click();self.assertEqual(p.evaluate('window.showpsisi.getDetail().id'),section)
        self.assertIn('21–40',p.locator('section[aria-label="Protocol summaries"]').inner_text())
        self.assertEqual(p.evaluate('document.activeElement.id'),button_id)
        from test_nordig import NorDigTests
        case=NorDigTests();pid,raw=case.nit(case.pds()+b'\x87\x02\x01\xff')
        from test_protocol_coverage import ProtocolCoverageTests
        path=self.output/'malformed-nordig.ts';path.write_bytes(b''.join(ProtocolCoverageTests.packetize(0x10,raw)))
        self.analyze(path);p.locator('[data-tab="Tables"]').click();p.locator('#search').fill('NIT');p.locator('#list .table-branch > summary').first.click()
        p.wait_for_function('()=>window.showpsisi.getDetail().table_id===0x40');p.locator('[data-view="metadata"]').click()
        p.locator('.protocol-sources summary').click();p.locator('[data-protocol-source]').first.click()
        p.wait_for_function('()=>window.showpsisi.getUiState().settled && window.showpsisi.getUiState().protocol_source.resolution?.precision==="section"')
        self.assertEqual(p.locator('[data-source-highlight]').count(),0)
        p.locator('[data-view="hex"]').click();self.assertEqual(p.locator('.source-byte').count(),0)

    def test_dsmcc_module_cards_keep_snapshot_hash_and_all_sources(self):
        self.open_scan_options()
        import test_dsmcc_summaries as f
        p=self.page
        for complete in (False,True):
            with self.subTest(complete=complete):
                sections=[f.dii(),f.ddb(b'abcd')]+([f.ddb(b'ef',block=1)] if complete else [])
                path=self.output/('module-'+str(complete)+'.ts');raw=f.packetize([(0x150,r) for r in sections]);path.write_bytes(raw)
                p.locator('#standards').select_option('dvb');p.locator('#extra-pids').fill('0x150');self.analyze(path)
                p.locator('[data-tab="Tables"]').click()
                if p.locator('#table-group-toggle').get_attribute('aria-pressed')=='true':p.locator('#table-group-toggle').click()
                source=p.evaluate('window.showpsisi.getState().tables.reduce((a,b)=>a.first_packet>b.first_packet?a:b).id')
                p.locator('#list [data-key="'+source+'"]').click();p.wait_for_function('(id)=>window.showpsisi.getDetail()?.id===id',arg=source)
                p.locator('[data-view="metadata"]').click()
                module=p.locator('.protocol-card').filter(has_text='download_module ·')
                self.assertEqual(module.count(),1);text=module.inner_text()
                self.assertIn('assembly status: '+('complete' if complete else 'incomplete'),text)
                self.assertIn('execution status: not_executed',text)
                digest=hashlib.sha256(b'abcdef').hexdigest()
                self.assertIn('assembled sha256: '+(digest if complete else 'null'),text)
                refs=p.evaluate("workbench.protocolCardSources(workbench.protocolCards(window.showpsisi.getDetail(),0,50).cards.find(c=>c.evidence?.object?.object_type==='download_module')).map(s=>s.ref)")
                self.assertEqual(len({r['section_id'] for r in refs}),len(sections))
                self.assertGreaterEqual(len(refs),len(sections))
                for index,ref in enumerate(refs):
                    module=p.locator('.protocol-card').filter(has_text='download_module ·')
                    disclosure=module.locator('.protocol-sources')
                    if disclosure.get_attribute('open') is None:disclosure.locator('summary').click()
                    disclosure.locator('[data-protocol-source]').nth(index).click()
                    p.wait_for_function('()=>window.showpsisi.getUiState().settled && !!window.showpsisi.getUiState().protocol_source.resolution')
                    detail=p.evaluate('window.showpsisi.getDetail()');resolution=p.evaluate('window.showpsisi.getUiState().protocol_source.resolution')
                    self.assertEqual(detail['id'],ref['section_id']);self.assertEqual(detail['analysis_revision'],ref['analysis_revision']);self.assertEqual(detail['native_table_at_packet'],len(sections)-1)
                    self.assertEqual(resolution['status'],'resolved');self.assertIn(resolution['precision'],('field','container'))
                    p.locator('[data-view="hex"]').click();self.assertGreater(p.locator('.source-byte').count(),0)
                    p.locator('#protocol-back').click();self.assertEqual(p.evaluate('window.showpsisi.getDetail().id'),source)
                self.assertEqual(path.read_bytes(),raw)

    def test_j94_explicit_profile_short_header_and_raw_fallback(self):
        from test_cable_oob import nit
        from test_protocol_coverage import ProtocolCoverageTests
        p=self.page
        for protocol,status in ((0,'decoded'),(1,'unknown_or_unsupported')):
            with self.subTest(protocol=protocol):
                raw=nit(protocol=protocol)
                source=self.output/('j94-'+str(protocol)+'.ts')
                encoded=b''.join(ProtocolCoverageTests.packetize(0x1ffc,raw));source.write_bytes(encoded)
                p.locator('#standards').select_option('j94-system-b');self.analyze(source)
                p.locator('[data-tab="Tables"]').click()
                p.locator('#list .table-branch > summary').first.click()
                p.wait_for_function('()=>window.showpsisi.getDetail().versioning_supported===false')
                p.locator('[data-view="tree"]').click()
                self.assertEqual(p.evaluate('window.showpsisi.getDetail().raw_hex'),raw.hex().upper())
                self.assertEqual(p.evaluate('window.showpsisi.getDetail().table_decode_category'),status)
                self.assertIn('version not carried',p.locator('#inspector').inner_text())
                self.assertIn('section number not carried',p.locator('#inspector').inner_text())
                self.assertIn('extension not carried',p.locator('#list').inner_text())
                self.assertIn('map assembly unsupported',p.locator('#list').inner_text())
                text=p.locator('main').inner_text()+p.locator('#timeline').inner_text()
                for fabricated in ('vnull','§null','Version null','section null','null/null','Ext 0x0000','observed 0/1'):
                    self.assertNotIn(fabricated,text)
                p.locator('[data-view="hex"]').click()
                self.assertIn('C2',p.locator('pre.evidence').inner_text())
                self.assertEqual(source.read_bytes(),encoded)

    def test_protocol_cards_real_engine_paging_themes_and_reset(self):
        from protocol_ui_fixture import protocol_ui_fixture
        raw=protocol_ui_fixture();path=self.output/'protocol-cards.ts';path.write_bytes(raw)
        p=self.page;p.locator('#standards').select_option('dvb');self.analyze(path)
        p.locator('[data-tab="Tables"]').click();p.locator('#search').fill('AIT')
        p.locator('#list .table-branch > summary').first.click()
        p.wait_for_function('() => window.showpsisi.getDetail().table_id === 0x74')
        p.locator('[data-view="metadata"]').click()
        region=p.locator('section[aria-label="Protocol summaries"]')
        self.assertEqual(region.locator('.metadata-card').count(),20)
        self.assertIn('not executed',region.inner_text())
        p.locator('#protocol-next').focus();p.locator('#protocol-next').press('Enter')
        self.assertIn('21–40',region.inner_text())
        self.assertEqual(p.evaluate('document.activeElement.id'),'protocol-next')
        p.keyboard.press('Enter');self.assertIn('41–60',region.inner_text())
        self.assertEqual(p.evaluate('document.activeElement.id'),'protocol-next')
        # Sixteen applications yield 64 object cards, two summary cards, and
        # the newly source-linked PAT/PMT carriage declaration.
        p.keyboard.press('Enter');self.assertIn('61–67 of 67',region.inner_text())
        self.assertEqual(region.locator('.metadata-card').count(),7)
        self.assertIn('application_carriage · resolved',region.inner_text())
        self.assertEqual(p.evaluate('document.activeElement.id'),'protocol-previous')
        p.keyboard.press('Enter');self.assertIn('41–60',region.inner_text())
        self.assertEqual(p.evaluate('document.activeElement.id'),'protocol-previous')
        p.keyboard.press('Enter');self.assertIn('21–40',region.inner_text())
        p.keyboard.press('Enter');self.assertIn('1–20',region.inner_text())
        self.assertEqual(p.evaluate('document.activeElement.id'),'protocol-next')
        for theme in ('dark','light'):
            if p.locator('html').get_attribute('data-theme')!=theme:p.locator('#theme-toggle').click()
            self.assertEqual(region.locator('.metadata-card').count(),20)
            evidence=region.locator('.metadata-card details').nth(1)
            if evidence.get_attribute('open') is None:evidence.locator('summary').click()
            self.assertIn('section_id',evidence.inner_text())
            p.screenshot(path=str(self.artifacts/f'protocol-cards-{theme}.png'),full_page=True)
        p.locator('#protocol-next').click()
        p.locator('#search').fill('PMT');p.locator('#list .table-branch > summary').first.click()
        p.wait_for_function('() => window.showpsisi.getDetail().table_id === 2')
        self.assertEqual(p.locator('section[aria-label="Protocol summaries"]').count(),0)
        p.locator('#search').fill('AIT');p.locator('#list .table-branch > summary').first.click()
        p.wait_for_function('() => window.showpsisi.getDetail().table_id === 0x74')
        self.assertIn('1–20',region.inner_text())
        self.assertEqual(path.read_bytes(),raw)

    def topology_source(self, profile='dvb', sections=None):
        from topology_fixture import parts, write_ts
        source=write_ts(self.output/('topology-'+profile+'.ts'),sections or parts(profile))
        self.page.locator('#standards').select_option(profile)
        self.analyze(source)
        self.page.locator('[data-tab="Topology"]').click()
        self.page.wait_for_function('() => window.showpsisi.getTopology() && !window.showpsisi.getUiState().topology.loading')
        return source

    def select_topology_service(self):
        node=self.page.evaluate('window.showpsisi.getTopology().nodes.find(n=>n.object_type === "service")')
        self.page.locator('#search').fill(node['label'])
        self.page.locator('[data-topology-node="'+node['node_id']+'"]').click()
        return node

    def test_nordig_lists_entries_keep_distinct_exact_source_containers(self):
        from test_nordig import NorDigTests
        from make_fixture import descriptor
        case=NorDigTests();body=case.channel_list(entries=((100,7,True),(101,8,True)))+case.channel_list(2,entries=((200,9,True),(201,10,True)))
        path=self.topology_source(sections=[case.nit(case.pds()+descriptor(0x87,body))]);before=path.read_bytes();p=self.page
        nodes=p.evaluate('window.showpsisi.getTopology().nodes.filter(n=>["channel_list","channel_list_entry"].includes(n.object_type))')
        self.assertEqual(len(nodes),6);containers=set()
        for node in nodes:
            p.locator('#search').fill(node['label']);p.locator('[data-topology-node="'+node['node_id']+'"]').click()
            sources=p.evaluate('(id)=>{const g=window.showpsisi.getTopology();return workbench.topologyEvidence(g.nodes.find(n=>n.node_id===id),g.edges)}',node['node_id'])
            assertion='nordig_channel_list' if node['object_type']=='channel_list' else 'nordig_list_entry'
            own=next(s['ref'] for s in sources if s['ref']['assertion_key']==assertion)
            index=next(i for i,s in enumerate(sources) if s['ref']==own)
            p.locator('[data-topology-source]').nth(index).click();p.wait_for_function('()=>window.showpsisi.getUiState().settled && !!window.showpsisi.getUiState().topology.locator_resolution')
            resolution=p.evaluate('window.showpsisi.getUiState().topology.locator_resolution')
            self.assertEqual(resolution['status'],'resolved');self.assertEqual(resolution['precision'],'container');self.assertEqual(resolution['byte_range'],own['locator']['byte_range'])
            containers.add(own['locator']['container_id']);p.locator('[data-view="hex"]').click();self.assertGreater(p.locator('.source-byte').count(),0)
            p.locator('#topology-back').click()
        self.assertEqual(len(containers),6);self.assertEqual(path.read_bytes(),before)

    def test_simulcast_declaration_exact_field_jumps_and_back_both_themes(self):
        from protocol_ui_fixture import simulcast_ui_parts
        p = self.page
        path = self.topology_source(sections=simulcast_ui_parts())
        original = path.read_bytes()
        node = p.evaluate('window.showpsisi.getTopology().nodes.find(n=>n.object_type==="simulcast_replacement_reference")')
        self.assertEqual(node['resolution_status'], 'resolved')
        self.assertFalse(node['attributes']['receiver_policy_applied'])
        expected = {'nordig_private_data_specifier', 'nordig_replacement_original_network_id',
                    'nordig_replacement_transport_stream_id', 'nordig_replacement_service_id',
                    'nordig_replacement_linkage_type'}
        p.set_viewport_size({'width':1000, 'height':900})
        for theme in ('dark', 'light'):
            with self.subTest(theme=theme):
                if p.locator('html').get_attribute('data-theme') != theme:
                    p.locator('#theme-toggle').click()
                p.locator('#search').fill(node['label'])
                p.locator('[data-topology-node="'+node['node_id']+'"]').click()
                sources = p.evaluate('(id)=>{const g=window.showpsisi.getTopology();return workbench.topologyEvidence(g.nodes.find(n=>n.node_id===id),g.edges)}', node['node_id'])
                seen = set()
                for index, source in enumerate(sources):
                    ref = source['ref']
                    if ref['assertion_key'] not in expected or ref['assertion_key'] in seen:
                        continue
                    seen.add(ref['assertion_key'])
                    p.locator('[data-topology-source]').nth(index).click()
                    p.wait_for_function('()=>window.showpsisi.getUiState().settled && !!window.showpsisi.getUiState().topology.locator_resolution')
                    detail = p.evaluate('window.showpsisi.getDetail()')
                    resolution = p.evaluate('window.showpsisi.getUiState().topology.locator_resolution')
                    self.assertEqual(detail['id'], ref['section_id'])
                    self.assertEqual(detail['analysis_revision'], ref['analysis_revision'])
                    self.assertEqual(detail['native_table_at_packet'], ref['at_packet'])
                    self.assertEqual(resolution['status'], 'resolved')
                    self.assertEqual(resolution['precision'], 'field')
                    self.assertEqual(resolution['byte_range'], ref['locator']['byte_range'])
                    self.assertEqual(p.locator('[data-source-highlight]').count(), 1)
                    p.locator('[data-view="hex"]').click()
                    self.assertEqual(p.locator('.source-byte').count(), ref['locator']['byte_range']['length'])
                    p.locator('#topology-back').click()
                    self.assertEqual(p.evaluate('window.showpsisi.getUiState().topology.selected_node'), node['node_id'])
                self.assertEqual(seen, expected)
                p.screenshot(path=str(self.artifacts/('simulcast-compact-'+theme+'.png')), full_page=True)
        self.assertEqual(path.read_bytes(), original)

    def test_carriage_card_three_table_sources_restore_origin_both_themes(self):
        from protocol_ui_fixture import carriage_ui_parts
        from test_application_summaries import packetize
        p = self.page
        path = self.output/'carriage-ui.ts'
        original = packetize(carriage_ui_parts())
        path.write_bytes(original)
        p.locator('#standards').select_option('dvb')
        self.analyze(path)
        p.locator('[data-tab="Tables"]').click()
        p.locator('#search').fill('AIT')
        p.locator('#list .table-branch > summary').first.click()
        p.wait_for_function('()=>window.showpsisi.getDetail()?.table_id===0x74')
        source_id = p.evaluate('window.showpsisi.getDetail().id')
        p.evaluate('(id)=>window.showpsisi.snapshot(2,id)', source_id)
        p.wait_for_function('(id)=>window.showpsisi.getUiState().settled && window.showpsisi.getDetail()?.id===id', arg=source_id)
        p.locator('#table-family').select_option('AIT')
        p.locator('[data-view="metadata"]').click()
        p.set_viewport_size({'width':1000, 'height':900})
        origin = p.evaluate('window.showpsisi.getDetail()')
        origin_state = p.evaluate('window.showpsisi.getUiState()')
        origin_history = p.locator('.history-point').all_text_contents()
        origin_page = p.locator('#page-label').inner_text()
        self.assertEqual(origin_state['packet'], 2)
        for theme in ('dark', 'light'):
            with self.subTest(theme=theme):
                if p.locator('html').get_attribute('data-theme') != theme:
                    p.locator('#theme-toggle').click()
                card = p.locator('.protocol-card').filter(has_text='application_carriage · resolved')
                self.assertEqual(card.count(), 1)
                self.assertIn('runtime compatibility: not_evaluated', card.inner_text())
                refs = p.evaluate("workbench.protocolCardSources(workbench.protocolCards(window.showpsisi.getDetail(),0,50).cards.find(c=>c.evidence?.object?.object_type==='application_carriage')).map(s=>s.ref)")
                self.assertEqual({r['table_identity']['table_id'] for r in refs}, {0, 2, 0x74})
                for index, ref in enumerate(refs):
                    card = p.locator('.protocol-card').filter(has_text='application_carriage · resolved')
                    disclosure = card.locator('.protocol-sources')
                    if disclosure.get_attribute('open') is None:
                        disclosure.locator('summary').click()
                    button = disclosure.locator('[data-protocol-source]').nth(index)
                    button_id = button.get_attribute('id')
                    button.click()
                    p.wait_for_function('()=>window.showpsisi.getUiState().settled && !!window.showpsisi.getUiState().protocol_source.resolution')
                    detail = p.evaluate('window.showpsisi.getDetail()')
                    resolution = p.evaluate('window.showpsisi.getUiState().protocol_source.resolution')
                    self.assertEqual(detail['id'], ref['section_id'])
                    self.assertEqual(detail['analysis_revision'], ref['analysis_revision'])
                    self.assertEqual(detail['native_table_at_packet'], ref['at_packet'])
                    self.assertEqual(resolution['status'], 'resolved')
                    self.assertEqual(resolution['precision'], ref['locator']['precision'])
                    self.assertEqual(resolution['byte_range'], ref['locator']['byte_range'])
                    p.locator('[data-view="hex"]').click()
                    self.assertEqual(p.locator('.source-byte').count(), ref['locator']['byte_range']['length'])
                    p.locator('#protocol-back').click()
                    p.wait_for_function('()=>window.showpsisi.getUiState().settled')
                    restored = p.evaluate('window.showpsisi.getDetail()')
                    self.assertEqual(restored['id'], origin['id'])
                    self.assertEqual(restored['native_table_at_packet'], origin['native_table_at_packet'])
                    self.assertEqual(p.evaluate('document.activeElement.id'), button_id)
                    restored_state = p.evaluate('window.showpsisi.getUiState()')
                    for key in ('selected', 'packet', 'table_filter', 'records', 'history', 'evidence_scope'):
                        self.assertEqual(restored_state[key], origin_state[key], key)
                    self.assertEqual(p.locator('#search').input_value(), 'AIT')
                    self.assertEqual(p.locator('#table-family').input_value(), 'AIT')
                    self.assertEqual(p.locator('#page-label').inner_text(), origin_page)
                    self.assertEqual(p.locator('.history-point').all_text_contents(), origin_history)
                    self.assertEqual(p.locator('.selection-hidden').count(), 0)
                    self.assertEqual(p.locator('#list [data-key="'+origin['id']+'"]').get_attribute('aria-selected'), 'true')
                card.locator('article > strong').scroll_into_view_if_needed()
                p.screenshot(path=str(self.artifacts/('carriage-compact-'+theme+'.png')), full_page=True)
        self.assertEqual(path.read_bytes(), original)

    def test_topology_objects_all_sources_six_views_and_back(self):
        source=self.topology_source()
        original=source.read_bytes()
        p=self.page
        p.locator('#search').fill('Topology Lab')
        first=p.locator('[data-topology-node]').first
        first.focus();p.keyboard.press('ArrowDown')
        self.assertEqual(p.evaluate('window.showpsisi.getUiState().topology.selected_node'),'','Arrow focus must not activate an object')
        self.assertEqual(p.locator('[data-topology-source]').count(),0)
        node=self.select_topology_service()
        selected=p.evaluate('window.showpsisi.getUiState().topology')
        expected=p.evaluate('id=>workbench.topologyEvidence(window.showpsisi.getTopology().nodes.find(n=>n.node_id===id),window.showpsisi.getTopology().edges).length',node['node_id'])
        self.assertEqual(p.locator('[data-topology-source]').count(),expected)
        p.locator('[data-topology-source]').filter(has_text='name').first.click()
        p.wait_for_function('()=>window.showpsisi.getUiState().settled && window.showpsisi.getUiState().topology.locator_resolution?.precision === "field"')
        self.assertEqual(p.evaluate('window.showpsisi.getUiState().inspection_context'),'topology')
        self.assertEqual(p.locator('[data-source-highlight]').count(),1)
        self.assertIn('Exact source field located',p.locator('#topology-locator-status').inner_text())
        self.assertEqual(p.locator('#edit').is_enabled(),False)
        p.screenshot(path=str(self.artifacts/'topology-exact-field-dark.png'))
        for view in ('hex','xml','decoded','metadata','references','tree'):
            p.locator('[data-view="'+view+'"]').click()
            if view=='hex':self.assertGreater(p.locator('.source-byte').count(),0)
        cutoff=p.evaluate('window.showpsisi.getState().selected_packet')
        p.locator('#topology-show-table').click()
        self.assertEqual(p.evaluate('window.showpsisi.getUiState().tab'),'Tables')
        p.locator('#topology-back').click()
        self.assertEqual(p.evaluate('window.showpsisi.getUiState().tab'),'Topology')
        self.assertEqual(p.evaluate('document.activeElement.id'),'topology-show-table')
        self.assertEqual(p.evaluate('window.showpsisi.getUiState().topology.focused_node'),selected['focused_node'])
        p.locator('#topology-back').click()
        self.assertEqual(p.locator('#search').input_value(),node['label'])
        self.assertEqual(p.evaluate('window.showpsisi.getUiState().topology.selected_node'),node['node_id'])
        for index in range(expected):
            p.locator('[data-topology-source]').nth(index).click()
            p.wait_for_function('()=>window.showpsisi.getUiState().settled && window.showpsisi.getUiState().topology.locator_resolution!==null')
            state=p.evaluate('window.showpsisi.getUiState()')
            detail=p.evaluate('window.showpsisi.getDetail()')
            self.assertEqual(detail['id'],state['topology']['evidence_ref']['section_id'])
            self.assertEqual(detail['native_table_at_packet'],state['topology']['evidence_ref']['at_packet'])
            self.assertEqual(state['packet'],cutoff)
            p.locator('#topology-back').click()
        p.locator('.all-tables').click()
        self.assertEqual(p.evaluate('window.showpsisi.getUiState().tab'),'Tables')
        p.locator('[data-tab="Topology"]').click()
        self.assertEqual(p.locator('#search').input_value(),node['label'])
        self.assertEqual(p.evaluate('window.showpsisi.getUiState().topology.expanded_ids'),selected['expanded_ids'])
        self.assertEqual(source.read_bytes(),original)

    def test_topology_three_profiles_themes_and_keyboard(self):
        for profile,title in (('dvb','DVB'),('atsc','ATSC 1.0'),('isdb-japan','ISDB Japan'),('isdb-brazil','ISDB Brazil'),('isdb','ISDB · region unspecified')):
            with self.subTest(profile=profile):
                self.topology_source(profile)
                p=self.page
                self.assertIn(title,p.locator('.topology-context').inner_text())
                rows=p.locator('[data-topology-node]')
                self.assertGreater(rows.count(),0)
                rows.first.focus();p.keyboard.press('End');p.keyboard.press('Home')
                p.keyboard.press('ArrowRight');p.keyboard.press('Enter')
                self.assertNotEqual(p.evaluate('window.showpsisi.getUiState().topology.selected_node'),'')
                p.keyboard.press('Tab')
                self.assertFalse(p.evaluate('document.activeElement.matches("[data-topology-node]")'))
                for width in (1440,1180,1000):
                    p.set_viewport_size({'width':width,'height':900})
                    for theme in ('dark','light'):
                        if p.evaluate('window.showpsisi.getUiState().theme')!=theme:p.locator('#theme-toggle').click()
                        self.assertTrue(p.locator('[data-tab="Topology"]').is_visible())
                        self.assertGreaterEqual(rows.first.bounding_box()['height'],28)
                p.locator('[data-tab="Services"]').click()

    def test_topology_loading_stale_cutoff_and_rescan_response(self):
        self.gate_native_messages()
        from topology_fixture import parts, write_ts
        source=write_ts(self.output/'topology-late.ts',parts())
        p=self.page;p.locator('#standards').select_option('dvb');self.analyze(source)
        p.evaluate('window.testGate.methods=["query_topology"]')
        p.locator('[data-tab="Topology"]').click()
        p.wait_for_function('()=>window.testGate.held.some(x=>x.method==="query_topology")')
        self.assertTrue(p.evaluate('window.showpsisi.getUiState().topology.loading'))
        self.assertIn('Loading',p.locator('#page-label').inner_text())
        p.evaluate('window.showpsisi.snapshot(0)')
        p.wait_for_function('()=>window.testGate.held.filter(x=>x.method==="query_topology").length===2')
        p.evaluate('window.testGate.held.reverse();window.testGate.methods=[];window.testGate.release()')
        p.wait_for_function('()=>window.showpsisi.getUiState().settled')
        self.assertEqual(p.evaluate('window.showpsisi.getTopology().at_packet'),0)
        self.assertEqual(p.evaluate('window.showpsisi.getState().selected_packet'),0)
        p.evaluate('window.testGate.methods=["query_topology"];window.showpsisi.snapshot(-1)')
        p.wait_for_function('()=>window.testGate.held.some(x=>x.method==="query_topology")')
        old=p.evaluate('window.showpsisi.getState().revision')
        p.locator('#scan').click()
        p.wait_for_function('old=>window.showpsisi.getState().complete && window.showpsisi.getState().revision>old',arg=old)
        p.wait_for_function('()=>window.testGate.held.filter(x=>x.method==="query_topology").length===2')
        p.evaluate('window.testGate.methods=[];window.testGate.release()')
        p.wait_for_function('()=>window.showpsisi.getUiState().settled')
        self.assertEqual(p.evaluate('window.showpsisi.getTopology().analysis_revision'),p.evaluate('window.showpsisi.getState().revision'))

    def test_topology_mismatch_missing_anchor_and_failed_refresh(self):
        self.gate_native_messages()
        self.topology_source();self.select_topology_service();p=self.page
        p.evaluate('window.testGate.methods=["inspect"]')
        p.locator('[data-topology-source]').filter(has_text='name').first.click()
        p.wait_for_function('()=>window.testGate.held.some(x=>x.method==="inspect")')
        self.assertIn('Locating exact source',p.locator('#topology-locator-status').inner_text())
        # Deliberate fault injection into an authentic response is a rejection
        # test, never evidence of successful protocol decoding.
        p.evaluate('window.testGate.held.find(x=>x.method==="inspect").event.payload.result.pid=8191;window.testGate.methods=[];window.testGate.release()')
        p.wait_for_function('()=>window.showpsisi.getUiState().settled')
        self.assertIn('does not match pid',p.locator('#inspector').inner_text())
        self.assertEqual(p.locator('[data-source-highlight]').count(),0)
        p.locator('#topology-back').click()
        p.evaluate('window.testGate.methods=["inspect"]')
        p.locator('[data-topology-source]').filter(has_text='name').first.click()
        p.wait_for_function('()=>window.testGate.held.some(x=>x.method==="inspect")')
        p.evaluate('window.testGate.held.find(x=>x.method==="inspect").event.payload.result.evidence_anchors=[];window.testGate.methods=[];window.testGate.release()')
        p.wait_for_function('()=>window.showpsisi.getUiState().settled')
        self.assertIn('Located the exact section',p.locator('#topology-locator-status').inner_text())
        self.assertEqual(p.locator('[data-source-highlight]').count(),0)
        p.locator('#topology-back').click()
        # A failed read must settle and remain visibly stale/error, never look
        # like an empty success or disable retry indefinitely.
        p.evaluate('window.testGate.methods=["query_topology"];window.showpsisi.snapshot(0)')
        p.wait_for_function('()=>window.testGate.held.some(x=>x.method==="query_topology")')
        p.evaluate('const x=window.testGate.held.find(x=>x.method==="query_topology");delete x.event.payload.result;x.event.payload.error={code:"test_read_failure",message:"Topology read failed"};window.testGate.methods=[];window.testGate.release()')
        p.wait_for_function('()=>window.showpsisi.getUiState().settled')
        self.assertIn('Topology read failed',p.locator('.topology-warning').first.inner_text())
        self.assertTrue(p.locator('#retry-topology').is_enabled())
        p.locator('#retry-topology').click()
        p.wait_for_function('()=>window.showpsisi.getUiState().settled && window.showpsisi.getTopology().at_packet===0')

    def test_topology_pagination_search_all_objects_and_safe_labels(self):
        from topology_fixture import pat, sdt
        sections=[pat(programs=())]
        for section in range(24):
            services=tuple((100+i,'Bulk Service %03d'%i) for i in range(section*25,(section+1)*25))
            sections.append(sdt(services=services,number=section,last=23))
        self.topology_source(sections=sections)
        p=self.page
        state=p.evaluate('window.showpsisi.getUiState().topology')
        self.assertGreater(state['total_nodes'],500)
        self.assertEqual(state['loaded_nodes'],500)
        self.assertIn('Search covers loaded objects only',p.locator('.topology-loaded-note').inner_text())
        p.locator('#search').fill('Bulk Service 599')
        self.assertEqual(p.locator('[data-topology-node]').count(),0)
        p.locator('#topology-load-more').click()
        p.wait_for_function('()=>window.showpsisi.getUiState().settled && !window.showpsisi.getTopology().page.has_more')
        state=p.evaluate('window.showpsisi.getUiState().topology')
        self.assertEqual(state['loaded_nodes'],state['total_nodes'])
        self.assertTrue(p.locator('[data-topology-node]').filter(has_text='Bulk Service 599').is_visible())
        p.locator('#search').fill('')
        p.locator('[data-topology-node]').first.focus();p.keyboard.press('ArrowRight')
        self.assertGreater(p.locator('[data-topology-more]').count(),0)
        old=p.locator('[data-topology-node]').count();p.locator('[data-topology-more]').first.click()
        self.assertGreater(p.locator('[data-topology-node]').count(),old)
        self.assertEqual(len(p.locator('[data-topology-node]').evaluate_all('(els)=>els.map(e=>e.dataset.topologyNode)')),len(set(p.locator('[data-topology-node]').evaluate_all('(els)=>els.map(e=>e.dataset.topologyNode)'))))
        # Real long-tree scrolling must survive source -> Tables -> Back, along
        # with search, selection, expansion and keyboard focus, not just IDs.
        p.locator('#search').fill('Bulk Service')
        p.locator('[data-topology-node]').filter(has=p.get_by_text('Bulk Service 090',exact=True)).click()
        selected=p.evaluate('window.showpsisi.getUiState().topology')
        scroll=p.locator('#list').evaluate('(el)=>el.scrollTop')
        self.assertGreater(scroll,500)
        p.locator('[data-topology-source]').filter(has_text='name').first.click()
        p.wait_for_function('()=>window.showpsisi.getUiState().settled && window.showpsisi.getUiState().topology.locator_resolution?.precision === "field"')
        p.locator('#topology-show-table').click()
        p.locator('#topology-back').click()
        self.assertEqual(p.evaluate('document.activeElement.id'),'topology-show-table')
        self.assertAlmostEqual(p.locator('#list').evaluate('(el)=>el.scrollTop'),scroll,delta=1)
        p.locator('#topology-back').click()
        self.assertEqual(p.locator('#search').input_value(),'Bulk Service')
        self.assertAlmostEqual(p.locator('#list').evaluate('(el)=>el.scrollTop'),scroll,delta=1)
        restored=p.evaluate('window.showpsisi.getUiState().topology')
        for key in ('selected_node','focused_node','expanded_ids'):
            self.assertEqual(restored[key],selected[key])
        self.assertTrue(p.evaluate('document.activeElement.matches("[data-topology-source]")'))
        # Untrusted broadcast names remain plain text, including markup-looking
        # names. This new scan also clears prior selection/search/revision state.
        p.locator('[data-tab="Services"]').click()
        self.topology_source(sections=[pat(),sdt(services=((100,'<img src=x>'),))])
        self.select_topology_service()
        self.assertIn('<img src=x>',p.locator('#inspector').inner_text())
        self.assertEqual(p.locator('#inspector img').count(),0)

    def test_topology_comparison_newer_side_supersedes_pending_query(self):
        self.gate_native_messages()
        from topology_fixture import parts, sdt
        self.topology_source(sections=parts()+[sdt(services=((100,'Later topology'),),version=2)])
        p=self.page;p.locator('[data-tab="Changes"]').click()
        p.locator('#compare-from').fill('3');p.locator('#compare-to').fill('4');p.locator('#run-comparison').click()
        p.wait_for_function('()=>window.showpsisi.getComparison() && window.showpsisi.getUiState().settled')
        p.evaluate('window.testGate.methods=["query_topology"]')
        p.locator('[data-comparison-topology$=":A"]').first.click()
        p.wait_for_function('()=>window.testGate.held.filter(x=>x.method==="query_topology").length===1')
        p.locator('[data-tab="Changes"]').click()
        p.locator('[data-comparison-topology$=":B"]').first.click()
        p.wait_for_function('()=>window.testGate.held.filter(x=>x.method==="query_topology").length===2')
        p.evaluate('window.testGate.held.reverse();window.testGate.methods=[];window.testGate.release()')
        p.wait_for_function('()=>window.showpsisi.getUiState().settled && window.showpsisi.getTopology()?.at_packet===4')
        self.assertIn('Comparison B',p.locator('.topology-context').inner_text())
        self.assertEqual(p.evaluate('window.showpsisi.getState().selected_packet'),None)

    def test_topology_delivery_and_satellite_candidates_keep_wire_provenance(self):
        from topology_fixture import delivery_parts
        self.topology_source(sections=delivery_parts())
        p=self.page
        snapshot=p.evaluate('window.showpsisi.getTopology()')
        declarations=[n for n in snapshot['nodes'] if n['object_type']=='delivery_parameters']
        self.assertEqual({n['attributes']['delivery_system'] for n in declarations},{'DVB-S2','DVB-C','DVB-T'})
        candidates=[n for n in snapshot['nodes'] if n['object_type']=='satellite_candidate']
        self.assertGreater(len(candidates),1,'Co-located candidates must remain ambiguous')
        for node in declarations+candidates:
            p.locator('#search').fill(node['label'])
            p.locator('[data-topology-node="'+node['node_id']+'"]').click()
            self.assertIn(node['label'],p.locator('#inspector h2').inner_text())
            if node['object_type']=='satellite_candidate':
                self.assertIn('Catalog reference sources',p.locator('#inspector').inner_text())
                self.assertIn('unconfirmed',p.locator('#inspector').inner_text())
                self.assertIn(node['parent_id'],{n['node_id'] for n in declarations})
            p.locator('[data-topology-source]').first.click()
            p.wait_for_function('()=>window.showpsisi.getUiState().settled && window.showpsisi.getUiState().topology.locator_resolution?.precision === "container"')
            self.assertIn('exact field position is unavailable',p.locator('#topology-locator-status').inner_text())
            p.locator('[data-view="hex"]').click()
            self.assertGreater(p.locator('.source-byte').count(),0)
            self.assertEqual(p.evaluate('window.showpsisi.getDetail().id'),node['evidence'][0]['section_id'])
            p.locator('#topology-back').click()
        p.locator('#search').fill('')
        p.screenshot(path=str(self.artifacts/'topology-satellite-candidates-dark.png'))
        p.locator('#theme-toggle').click()
        p.screenshot(path=str(self.artifacts/'topology-satellite-candidates-light.png'))

    def test_topology_comparison_side_keeps_workspace_cutoff(self):
        from topology_fixture import parts, sdt
        self.topology_source(sections=parts()+[sdt(services=((100,'Later topology'),),version=2)])
        p=self.page;p.locator('[data-tab="Changes"]').click()
        p.locator('#compare-from').fill('3');p.locator('#compare-to').fill('4');p.locator('#run-comparison').click()
        p.wait_for_function('()=>window.showpsisi.getComparison() && window.showpsisi.getUiState().settled')
        before=p.evaluate('window.showpsisi.getState().selected_packet')
        p.locator('[data-comparison-topology$=":A"]').first.click()
        p.wait_for_function('()=>window.showpsisi.getTopology()?.at_packet===3 && window.showpsisi.getUiState().settled')
        self.assertIn('Comparison A',p.locator('.topology-context').inner_text())
        self.select_topology_service();p.locator('[data-topology-source]').first.click()
        p.wait_for_function('()=>window.showpsisi.getUiState().settled')
        self.assertFalse(p.locator('#topology-show-table').is_enabled())
        self.assertEqual(p.evaluate('window.showpsisi.getState().selected_packet'),before)
        p.locator('#topology-back').click();p.locator('#topology-back').click()
        self.assertEqual(p.evaluate('window.showpsisi.getUiState().tab'),'Changes')
        self.assertIsNotNone(p.evaluate('window.showpsisi.getComparison()'))
        self.assertEqual(p.evaluate('window.showpsisi.getState().selected_packet'),before)

    def test_workbench_all_table_history_counts_and_inspector_views(self):
        from explorer_fixture import explorer_fixture
        path=self.output/'workbench.ts';path.write_bytes(explorer_fixture())
        p=self.page;p.locator('#standards').select_option('dvb');self.analyze(path)
        state=p.evaluate('window.showpsisi.getState()')
        p.locator('[data-tab="Tables"]').click()
        self.assertIn('7 tables · 7 sections · 2 bad CRC hidden',p.locator('#result-count').inner_text())
        p.locator('#show-bad-crc').check()
        self.assertIn('7 tables · 9 sections',p.locator('#result-count').inner_text())
        p.locator('#search').fill('SDT 0x0011')
        self.assertEqual(p.locator('.table-branch').count(),2)
        p.locator('#search').fill('')
        for tid in sorted({h['table_id'] for h in state['table_history']}):
            row=next(r for r in state['tables'] if r['table_id']==tid)
            p.evaluate('id=>window.showpsisi.inspect(id)',row['id'])
            p.wait_for_function('id=>window.showpsisi.getUiState().settled && window.showpsisi.getDetail().id===id',arg=row['id'])
            history=p.evaluate('window.showpsisi.getUiState().history.entries')
            self.assertTrue(history)
            self.assertTrue(all(h['pid']==row['pid'] and h['table_id']==tid for h in history))
            p.locator('[data-scope="section"]').click()
            detail=p.evaluate('window.showpsisi.getDetail()')
            p.locator('[data-view="decoded"]').click()
            self.assertEqual(p.locator('.evidence').inner_text(),detail['section_native_text'] or 'Native section display unavailable. Raw bytes remain in Hex.')
            p.locator('[data-view="xml"]').click()
            if detail.get('section_tsduck_xml'):
                self.assertEqual(p.locator('.evidence').inner_text(),detail['section_tsduck_xml'])
            p.locator('[data-view="references"]').click()
            p.locator('[data-view="tree"]').click()
        p.locator('#history-scope').select_option('all')
        self.assertEqual(p.evaluate('window.showpsisi.getUiState().history.entries'),state['table_history'])
        target=next((i,h) for i,h in enumerate(state['table_history']) if h['table_id']==2)
        p.locator('[data-history="'+str(target[0])+'"]').click()
        p.wait_for_function('packet=>window.showpsisi.getUiState().settled && window.showpsisi.getState().selected_packet===packet',arg=target[1]['at_packet'])
        self.assertEqual(p.evaluate('window.showpsisi.getDetail().id'),target[1]['id'])
        self.assertEqual(path.read_bytes(),explorer_fixture())

    def test_explorer_counts_shared_pid_keyboard_and_family_filter(self):
        from explorer_fixture import explorer_fixture
        source = self.output / 'explorer.ts'; source.write_bytes(explorer_fixture())
        p = self.page
        p.locator('#standards').select_option('dvb')
        self.analyze(source)
        state = p.evaluate('window.showpsisi.getState()')
        self.assertEqual(len(state['table_groups']), 7)
        self.assertEqual(len(state['tables']), 9)
        def navigation():
            return p.locator('#sidebar .explorer-row').evaluate_all('(els)=>els.map(e=>({pid:Number(e.dataset.pid),name:e.dataset.filter,count:Number(e.dataset.count)}))')
        from collections import Counter
        counts = Counter((g['pid'], g['name']) for g in state['table_groups'])
        expected = [{'pid':-1,'name':'All tables','count':7}] + [dict(pid=pid,name=name,count=count) for (pid,name),count in sorted(counts.items())]
        self.assertEqual(navigation(), expected)
        self.assertEqual(p.locator('#sidebar button').count(), len(expected), 'One navigation list only')
        self.assertEqual(p.locator('#sidebar .active').count(), 0, 'Services is not a table filter selection')
        sdt = p.locator('.pid-row[data-pid="17"][data-filter="SDT"]')
        sdt.click()
        self.assertEqual(p.evaluate('window.showpsisi.getUiState().table_filter'), {'pid':17,'name':'SDT','count_unit':'logical_tables'})
        self.assertEqual(p.locator('#table-family').input_value(), 'SDT')
        self.assertNotIn('BAT', p.locator('#list').inner_text())
        p.keyboard.press('Home'); p.keyboard.press('ArrowDown'); p.keyboard.press('ArrowDown')
        self.assertEqual(p.evaluate('document.activeElement.dataset.filter'), 'BAT')
        self.assertTrue(sdt.get_attribute('aria-pressed') == 'true', 'Moving focus must not change the selection')
        p.keyboard.press('Enter')
        self.assertEqual(p.locator('#sidebar .active').get_attribute('data-filter'), 'BAT')
        self.assertEqual(p.locator('.table-branch').count(), 1)
        p.keyboard.press('End'); p.keyboard.press('Space')
        self.assertEqual(p.locator('#sidebar .active').get_attribute('data-pid'), '257')
        p.keyboard.press('Tab')
        self.assertFalse(p.evaluate('document.querySelector("#sidebar").contains(document.activeElement)'))
        p.locator('#table-family').select_option('PMT')
        self.assertEqual(p.locator('.table-branch').count(), 2)
        self.assertEqual(p.locator('#sidebar .active').count(), 0)
        self.assertEqual(p.evaluate('window.showpsisi.getUiState().table_filter.pid'), -1)
        p.locator('#table-family').select_option('Private / other')
        self.assertEqual(p.locator('.table-branch').count(), 1)
        self.assertIn('0x80', p.locator('#list').inner_text())
        p.locator('#table-family').select_option('NIT')
        self.assertTrue(p.locator('#list .empty').is_visible())
        p.locator('#sidebar .all-tables').click()
        self.assertEqual(p.locator('#table-family').input_value(), '')
        p.locator('#show-bad-crc').check()
        self.assertEqual(navigation(), expected, 'CRC visibility must not change the evidence totals')
        p.locator('#search').fill('SDT')
        self.assertEqual(navigation(), expected, 'Search must not change the evidence totals')
        p.locator('#search').fill('')
        p.evaluate('window.showpsisi.snapshot(0)')
        p.wait_for_function('()=>window.showpsisi.getState().selected_packet===0 && window.showpsisi.getUiState().settled')
        self.assertEqual(navigation(), [{'pid':-1,'name':'All tables','count':1},{'pid':0,'name':'PAT','count':1}])
        p.evaluate('window.showpsisi.snapshot(-1)')
        p.wait_for_function('()=>window.showpsisi.getState().selected_packet===null && window.showpsisi.getUiState().settled')
        self.assertEqual(navigation(), expected)
        p.locator('[data-tab="Services"]').click()
        self.assertEqual(p.locator('#sidebar .active').count(), 0)
        self.assertEqual(source.read_bytes(), explorer_fixture())
        p.screenshot(path=str(self.artifacts/'explorer-parity.png'))

    def test_satellite_candidates_wire_sources_and_manual_lookup(self):
        from test_satellite_metadata import satellite_fixture
        path=self.output/'satellite.ts';path.write_bytes(satellite_fixture())
        self.page.locator('#standards').select_option('dvb')
        self.analyze(path)
        self.page.locator('[data-tab="Tables"]').click()
        self.page.locator('#table-group-toggle').click()
        self.page.locator('.record').first.click()
        self.page.wait_for_function('() => window.showpsisi.getDetail()?.table_id === 0x40')
        self.page.locator('[data-view="metadata"]').click()
        panel=self.page.locator('.metadata-panel')
        self.assertIn('HOTBIRD 13F',panel.inner_text())
        self.assertIn('HOTBIRD 13G',panel.inner_text())
        self.assertIn('11538000000 Hz',panel.inner_text())
        self.assertIn('not checked',panel.inner_text())
        self.page.locator('.metadata-card details summary').first.click()
        self.assertIn('raw_descriptor_hex',panel.inner_text())
        self.assertIn('section_offset',panel.inner_text())
        self.page.locator('#satellite-position').fill('122')
        self.page.locator('#satellite-query').click()
        self.page.wait_for_function('() => document.querySelector("#satellite-result").textContent.includes("AsiaSat 9")')
        self.assertEqual(self.page.locator('#satellite-result thead th').all_inner_texts(),['Key','Value','Source'])
        self.assertEqual(self.page.locator('#satellite-result tr:has(th[title="confirmed_satellite"]) .lookup-value').inner_text(),'null')
        self.assertIn('not verified',self.page.locator('#satellite-result').inner_text())
        self.assertFalse(self.page.locator('.satellite-lookup-evidence').evaluate('(el)=>el.open'))
        self.page.locator('.satellite-lookup-evidence summary').click()
        evidence=json.loads(self.page.locator('#satellite-evidence').inner_text())
        self.assertIsNone(evidence['confirmed_satellite'])
        self.assertEqual(evidence['candidates'][0]['status'],'candidate')
        self.page.locator('#satellite-position').fill('5')
        self.page.locator('#satellite-direction').select_option('W')
        self.page.locator('#satellite-query').click()
        self.page.wait_for_function('() => document.querySelector("#satellite-result").textContent.includes("5 WEST B")')
        self.page.locator('#satellite-direction').select_option('E')
        self.page.locator('#satellite-query').click()
        self.page.wait_for_function('() => document.querySelector("#satellite-result").textContent.includes("no_catalog_match")')
        self.page.locator('#satellite-position').fill('181')
        self.page.locator('#satellite-query').click()
        self.assertIn('0 to 180',self.page.locator('#satellite-result').inner_text())
        self.assertEqual(self.page.locator('#satellite-evidence').inner_text(),'')
        self.assertEqual(path.read_bytes(),satellite_fixture())
        self.page.screenshot(path=str(self.artifacts/'satellite-candidates.png'))

    def test_signal_metadata_language_encoding_and_id_lookup(self):
        self.open_scan_options()
        from test_signal_metadata import metadata_fixture
        path=self.output/'metadata.ts';path.write_bytes(metadata_fixture())
        self.page.locator('#standards').select_option('dvb')
        self.page.locator('#default-charset').fill('ISO-8859-1')
        self.analyze(path)
        self.page.locator('[data-tab="EPG"]').click()
        self.page.locator('.record').first.click()
        self.page.wait_for_function('() => window.showpsisi.getDetail()?.table_id === 0x4e')
        self.page.locator('[data-view="metadata"]').click()
        panel=self.page.locator('.metadata-panel')
        self.assertIn('wire_selector',panel.inner_text())
        self.assertIn('First second',panel.inner_text())
        self.page.locator('#epg-language').select_option('zho')
        self.assertIn('新闻',self.page.locator('#list').inner_text())
        self.assertIn('incomplete',panel.inner_text())
        self.assertIn('No complete extended text',panel.inner_text())
        self.page.locator('#identifier-lookup > summary').click()
        self.page.locator('#identifier-kind').select_option('ca_system_id')
        self.page.locator('#identifier-value').fill('0x0500')
        self.page.locator('#identifier-query').click()
        self.page.wait_for_function('() => document.querySelector("#identifier-result").textContent.includes("Viaccess")')
        self.assertIn('not verified',self.page.locator('#identifier-result').inner_text())
        self.assertEqual(self.page.locator('#identifier-result thead th').all_inner_texts(),['Key','Value','Source'])
        self.assertFalse(self.page.locator('#identifier-raw').evaluate('(el)=>el.open'))
        self.page.locator('#epg-language').select_option('')
        self.assertEqual(self.page.locator('#identifier-kind').input_value(),'ca_system_id')
        self.assertEqual(self.page.locator('#identifier-value').input_value(),'0x0500')
        self.assertIn('Viaccess',self.page.locator('#identifier-result').inner_text())
        self.page.locator('.metadata-card details summary').first.click()
        self.assertIn('section_id',panel.inner_text())
        self.assertEqual(path.read_bytes(),metadata_fixture())

    @classmethod
    def setUpClass(cls):
        from playwright.sync_api import sync_playwright
        cls.tmp=tempfile.TemporaryDirectory(prefix='showpsisi-browser-')
        cls.addClassCleanup(cls.tmp.cleanup)
        cls.output=Path(cls.tmp.name)
        cls.sample=cls.output/'lab.ts'
        subprocess.run([sys.executable,str(ROOT/'scripts/make_fixture.py'),'--mib','12','--output',str(cls.sample)],check=True,stdout=subprocess.DEVNULL,cwd=ROOT)
        cls.empty=cls.output/'empty.ts'
        # A real TS containing only null packets: valid input with no SI tables.
        cls.empty.write_bytes((bytes([0x47,0x1f,0xff,0x10])+b'\xff'*184)*100)
        cls.original_hash=hashlib.sha256(cls.sample.read_bytes()).hexdigest()
        cls.playwright=sync_playwright().start()
        cls.addClassCleanup(cls.playwright.stop)
        executable=os.environ.get('PLAYWRIGHT_CHROMIUM_EXECUTABLE') or shutil.which('chromium') or shutil.which('chromium-browser')
        cls.browser=cls.playwright.chromium.launch(headless=True,chromium_sandbox=True,**({'executable_path':executable} if executable else {}))
        cls.addClassCleanup(cls.browser.close)
        cls.artifacts=ROOT/'artifacts/web-ui-tests'
        cls.artifacts.mkdir(parents=True,exist_ok=True)

    def setUp(self):
        self.checkpoint=None
        if self._testMethodName.startswith('test_cancel_'):
            normal=Path(os.environ.get('SHOWPSISI_CORE',ROOT/'build/bin/showpsisi-core'))
            helper=Path(os.environ.get('SHOWPSISI_TEST_CORE',normal.with_name(normal.stem+'-test'+normal.suffix)))
            if not helper.is_file():
                self.skipTest('Build SHOWPSISI_BUILD_CANCELLATION_TESTS=ON or set SHOWPSISI_TEST_CORE')
            self.checkpoint=self.output/self._testMethodName
            stage='before_analysis' if 'before_start' in self._testMethodName else 'before_complete' if 'near_completion' in self._testMethodName else 'after_progress'
            number='2' if 'stale' in self._testMethodName else '1'
            with patch.dict(os.environ,SHOWPSISI_TEST_GATE=str(self.checkpoint),SHOWPSISI_TEST_STAGE=stage,SHOWPSISI_TEST_ANALYSIS_NUMBER=number):
                if 'failure_after_progress' in self._testMethodName:
                    with patch.dict(os.environ,SHOWPSISI_TEST_FAIL_AT_GATE='1'):
                        self.bridge=Bridge(self.output,self.sample,executable=str(helper))
                else:
                    self.bridge=Bridge(self.output,self.sample,executable=str(helper))
        else:
            self.bridge=Bridge(self.output,self.sample)
        self.addCleanup(self.bridge.close)
        self.server=Server(self.bridge)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.page=self.browser.new_page(viewport={'width':1440,'height':1000},device_scale_factor=1)
        self.page_errors=[]
        self.page.on('pageerror',lambda error:self.page_errors.append(str(error)))
        self.page.goto(self.server.url)
        self.page.wait_for_function('() => window.showpsisi && document.querySelector("#source").value.length > 0')

    def tearDown(self):
        self.page.screenshot(path=str(self.artifacts/(self._testMethodName+'.png')),full_page=True)
        self.page.close()
        self.assertEqual(self.page_errors,[],'Browser JavaScript raised an exception')

    def open_scan_options(self):
        if self.page.locator('#scan-options').is_hidden():
            self.page.locator('#scan-options-toggle').click()

    def analyze(self,path=None):
        self.page.locator('#source').fill(str(path or self.sample))
        self.page.locator('#source').press('Enter')
        self.page.wait_for_function('() => window.showpsisi.getState().complete === true')
        self.page.wait_for_function('() => !document.querySelector("#scan").disabled')

    def call(self,method,params=None):
        return self.page.evaluate('([method,params])=>window.showpsisi.call(method,params)',[method,params or {}])

    def wait_checkpoint(self):
        deadline=time.monotonic()+15
        ready=Path(str(self.checkpoint)+'.ready')
        while not ready.exists():
            if time.monotonic()>deadline:
                self.fail('Native cancellation helper did not reach checkpoint: '+str(self.checkpoint))
            self.page.wait_for_timeout(20)
        return json.loads(ready.read_text())

    def gate_native_messages(self):
        # Only the test transport is wrapped. Every payload below originated
        # from this test's real native child; holding a terminal result lets us
        # assert the pending UI without racing the scheduler or adding sleeps.
        self.page.add_init_script('''
          let native;
          const gate=window.testGate={methods:[],held:[],received:[],requests:[],byId:new Map(),progress:[],listener:null};
          gate.release=method=>{
            const selected=gate.held.filter(item=>!method||item.method===method);
            gate.held=gate.held.filter(item=>!selected.includes(item));
            for(const item of selected)item.deliver(item.event);
          };
          Object.defineProperty(window,'__TAURI__',{configurable:true,get:()=>native,set:value=>{
            native=value;
            const invoke=value.core.invoke;
            value.core.invoke=(command,args={})=>{
              if(command==='request'){
                gate.requests.push(args.message);
                gate.byId.set(args.message.id,args.message.method);
              }
              return invoke(command,args);
            };
            const listen=value.event.listen;
            value.event.listen=(name,deliver)=>listen(name,event=>{
              gate.listener=deliver;
              const message=event.payload;
              if(message.event==='progress')gate.progress.push(event);
              const method=message.event ? message.event : gate.byId.get(message.id);
              gate.received.push({method,message});
              if(gate.methods.includes(method))gate.held.push({method,event,deliver});
              else deliver(event);
            });
          }});
        ''')
        self.page.reload()
        self.page.wait_for_function('() => window.showpsisi && document.querySelector("#source").value.length > 0')

    def test_cancel_progress_waits_for_terminal_then_rescans(self):
        self.gate_native_messages()
        pid=self.bridge.proc.pid
        self.page.evaluate('window.testGate.methods=["analyze"]')
        self.page.locator('#scan').click()
        self.wait_checkpoint()
        self.page.wait_for_function('() => window.testGate.progress.length > 0')
        before_cancel=self.page.evaluate('window.showpsisi.getState()')
        self.page.evaluate('''() => {
          const id=window.testGate.progress[0].payload.request_id;
          window.testGate.listener({payload:{event:'unrelated',request_id:id,state:{source:'foreign-event'}}});
          window.testGate.listener({payload:{event:'progress',request_id:id,state:['malformed-state']}});
          window.testGate.listener({payload:{event:'progress',request_id:'another-request',state:{source:'foreign-request'}}});
        }''')
        self.assertEqual(self.page.evaluate('window.showpsisi.getState()'),before_cancel)
        cancel=self.page.locator('#cancel-scan')
        self.assertTrue(cancel.is_visible())
        cancel.focus();cancel.press('Enter')
        self.page.wait_for_function('() => window.testGate.held.some(item=>item.event.payload.error?.code==="analysis_cancelled")')
        self.assertTrue(cancel.is_disabled())
        self.assertEqual(cancel.inner_text(),'Cancelling…')
        self.assertTrue(self.page.locator('#scan').is_disabled())
        self.assertTrue(self.page.locator('#source').is_disabled())
        self.assertEqual(self.page.evaluate('window.showpsisi.getState()'),{})
        self.assertEqual(self.page.evaluate('window.showpsisi.getDetail()'),{})
        # Repeated activation cannot emit a second cancellation, and late
        # real progress cannot resurrect partial evidence while cancelling.
        self.page.evaluate('''() => {
          window.showpsisi.cancelScan();
          for(const event of window.testGate.progress)window.testGate.listener(event);
          window.showpsisi.scan();
        }''')
        self.assertEqual(self.page.evaluate('window.testGate.requests.filter(request=>request.method==="cancel_analysis").length'),1)
        self.assertEqual(self.page.evaluate('window.testGate.requests.filter(request=>request.method==="analyze").length'),1)
        self.assertEqual(self.page.evaluate('window.showpsisi.getState()'),{})
        for width in (900,761,520):
            self.page.set_viewport_size({'width':width,'height':1000})
            self.assertLessEqual(self.page.evaluate('document.documentElement.scrollWidth'),width+1)
            self.assertTrue(cancel.is_visible())
        self.page.screenshot(path=str(self.artifacts/'cancellation-pending-narrow.png'),full_page=True)
        self.page.evaluate('window.testGate.release("analyze")')
        self.page.wait_for_function('() => !document.querySelector("#scan").disabled')
        state=self.page.evaluate('window.showpsisi.getState()')
        self.assertEqual(state['analysis_status'],'cancelled')
        self.assertFalse(state['complete'])
        self.assertEqual(state['source'],str(self.sample))
        self.assertEqual(state['services'],[])
        self.assertEqual(state['tables'],[])
        self.assertEqual(state['history'],[])
        self.assertIn('Analysis cancelled',self.page.locator('#notice').inner_text())
        self.assertFalse(self.page.locator('#notice').evaluate('(element)=>element.classList.contains("error")'))
        self.assertTrue(self.page.locator('#status-warning').is_visible())
        self.assertIn('Analysis cancelled',self.page.locator('#warning-message').get_attribute('title'))
        self.assertIn('×1',self.page.locator('#warning-message').inner_text())
        self.assertTrue(self.page.locator('#scan').evaluate('(element)=>element===document.activeElement'))
        self.assertFalse(cancel.is_visible())
        self.assertTrue(self.page.locator('#latest').is_disabled())
        self.assertTrue(self.page.locator('#compare-snapshots').is_disabled())
        self.assertNotIn('DISCONNECTED',self.page.locator('#runtime').inner_text())
        self.call('capabilities')
        self.assertEqual(self.bridge.proc.pid,pid)
        self.assertIsNone(self.bridge.proc.poll())
        self.page.evaluate('window.testGate.methods=[]')
        self.page.locator('#scan').press('Enter')
        self.page.wait_for_function('() => window.showpsisi.getState().complete && !document.querySelector("#scan").disabled')
        self.page.wait_for_function('() => window.showpsisi.getDetail().name === "SDT"')
        complete=self.page.evaluate('window.showpsisi.getState()')
        self.assertEqual(len(complete['services']),6)
        self.page.evaluate('''() => {for(const event of window.testGate.progress.filter(item=>item.payload.request_id===window.testGate.progress[0].payload.request_id))window.testGate.listener(event);}''')
        self.assertEqual(self.page.evaluate('window.showpsisi.getState()'),complete)
        self.assertEqual(hashlib.sha256(self.sample.read_bytes()).hexdigest(),self.original_hash)

    def test_cancel_before_start(self):
        self.page.locator('#scan').click()
        self.wait_checkpoint()
        self.page.locator('#cancel-scan').click()
        self.page.wait_for_function('() => !document.querySelector("#scan").disabled')
        self.assertEqual(self.page.evaluate('window.showpsisi.getState().analysis_status'),'cancelled')
        self.assertFalse(self.page.locator('#cancel-scan').is_visible())
        self.analyze()
        self.assertEqual(len(self.page.evaluate('window.showpsisi.getState().services')),6)

    def test_cancel_transport_failure_stays_pending_and_can_retry(self):
        failed=[]
        def interrupt_cancel(route):
            body=route.request.post_data_json
            if not failed and body.get('args',{}).get('message',{}).get('method')=='cancel_analysis':
                failed.append(True)
                route.abort('failed')
            else:
                route.continue_()
        self.page.route('**/__bridge/invoke',interrupt_cancel)
        self.page.locator('#scan').click()
        self.wait_checkpoint()
        self.page.locator('#cancel-scan').click()
        self.page.wait_for_function('() => document.querySelector("#notice").textContent.includes("Cancellation was not confirmed")')
        self.assertEqual(len(failed),1)
        self.assertTrue(self.page.locator('#scan').is_disabled())
        self.assertFalse(self.page.locator('#cancel-scan').is_disabled())
        self.assertNotIn('DISCONNECTED',self.page.locator('#runtime').inner_text())
        self.page.locator('#cancel-scan').click()
        self.page.wait_for_function('() => window.showpsisi.getState().analysis_status === "cancelled" && !document.querySelector("#scan").disabled')
        self.assertFalse(self.page.locator('#notice').evaluate('(element)=>element.classList.contains("error")'))
        self.analyze()
        self.assertEqual(len(self.page.evaluate('window.showpsisi.getState().services')),6)

    def test_cancel_near_completion(self):
        self.page.locator('#scan').click()
        self.wait_checkpoint()
        self.page.locator('#cancel-scan').click()
        self.page.wait_for_function('() => !document.querySelector("#scan").disabled')
        state=self.page.evaluate('window.showpsisi.getState()')
        self.assertEqual(state['analysis_status'],'cancelled')
        self.assertEqual(state['services'],[])
        self.assertEqual(state['tables'],[])
        self.assertEqual(state['history'],[])
        self.analyze()
        self.assertEqual(len(self.page.evaluate('window.showpsisi.getState().services')),6)

    def test_cancel_failure_after_progress_clears_partial_evidence(self):
        self.gate_native_messages()
        self.page.locator('#scan').click()
        self.wait_checkpoint()
        self.page.wait_for_function('() => window.showpsisi.getState().tables?.length > 0')
        Path(str(self.checkpoint)+'.release').touch()
        self.page.wait_for_function('() => !document.querySelector("#scan").disabled')
        state=self.page.evaluate('window.showpsisi.getState()')
        self.assertEqual(state['analysis_status'],'failed')
        self.assertFalse(state['complete'])
        self.assertFalse(state.get('tables'))
        self.assertFalse(state.get('services'))
        self.assertEqual(self.page.evaluate('window.showpsisi.getDetail()'),{})
        self.assertIsNone(self.page.evaluate('window.showpsisi.getComparison()'))
        self.assertTrue(self.page.locator('#notice').evaluate('(element)=>element.classList.contains("error")'))
        self.assertIn('Analysis failed',self.page.locator('#list').inner_text())
        self.assertTrue(self.page.locator('#compare-snapshots').is_disabled())
        self.assertTrue(self.page.locator('#latest').is_disabled())
        self.page.evaluate('''() => {for(const event of window.testGate.progress)window.testGate.listener(event)}''')
        self.assertEqual(self.page.evaluate('window.showpsisi.getState()'),state)
        self.assertNotIn('DISCONNECTED',self.page.locator('#runtime').inner_text())
        self.analyze()
        self.page.wait_for_function('() => window.showpsisi.getDetail().name === "SDT"')
        self.assertEqual(len(self.page.evaluate('window.showpsisi.getState().services')),6)

    def test_cancel_stale_read_and_comparison_responses(self):
        self.gate_native_messages()
        self.analyze()
        self.page.wait_for_function('() => window.showpsisi.getDetail().name === "SDT"')
        before=self.page.evaluate('window.showpsisi.getState()')
        service=before['services'][0]
        self.page.evaluate('window.testGate.methods=["inspect","query","diff_snapshots"]')
        self.page.locator('#compare-snapshots').click()
        self.page.locator('#run-comparison').click()
        self.page.wait_for_function('() => window.testGate.held.some(item=>item.method==="diff_snapshots")')
        self.page.locator('[data-tab="Services"]').click()
        self.assertEqual(self.page.evaluate('window.showpsisi.getDetail().name'),'SDT')
        self.page.evaluate('packet=>{window.showpsisi.snapshot(packet)}',before['history'][0]['last_packet'])
        self.page.wait_for_function('() => window.testGate.held.some(item=>item.method==="query")')
        self.page.evaluate('service=>{window.showpsisi.inspect(service.source_id,service.id)}',service)
        self.page.wait_for_function('() => window.testGate.held.some(item=>item.method==="inspect")')
        self.page.locator('[data-tab="Changes"]').click()
        self.page.locator('#scan').click()
        self.wait_checkpoint()
        self.page.locator('#cancel-scan').click()
        self.page.wait_for_function('() => window.showpsisi.getState().analysis_status === "cancelled" && !document.querySelector("#scan").disabled')
        self.assertEqual(self.page.evaluate('window.showpsisi.getDetail()'),{})
        self.assertIsNone(self.page.evaluate('window.showpsisi.getComparison()'))
        # Restoring either comparison side cannot resurrect the pre-scan
        # workspace, even before delayed responses arrive.
        self.page.locator('[data-tab="Changes"]').click()
        self.page.locator('[data-tab="Services"]').click()
        self.assertEqual(self.page.evaluate('window.showpsisi.getDetail()'),{})
        self.page.evaluate('window.testGate.methods=[]')
        self.analyze()
        self.page.wait_for_function('() => window.showpsisi.getDetail().name === "SDT"')
        current=self.page.evaluate('window.showpsisi.getState()')
        detail=self.page.evaluate('window.showpsisi.getDetail()')
        self.page.evaluate('window.testGate.release()')
        self.call('capabilities')
        self.assertEqual(self.page.evaluate('window.showpsisi.getState()'),current)
        self.assertEqual(self.page.evaluate('window.showpsisi.getDetail()'),detail)
        self.assertIsNone(self.page.evaluate('window.showpsisi.getComparison()'))
        self.assertNotIn('Loading',self.page.locator('#inspector').inner_text())

    def test_cancel_stale_preview_cannot_restore_edit_token(self):
        self.gate_native_messages()
        self.analyze()
        self.page.wait_for_function('() => window.showpsisi.getDetail().name === "SDT"')
        self.page.evaluate('window.testGate.methods=["preview_rename"]')
        self.page.locator('#edit').click()
        self.page.locator('#rename').fill('Obsolete preview')
        self.page.locator('#preview').click()
        self.page.wait_for_function('() => window.testGate.held.some(item=>item.method==="preview_rename")')
        # Invoke the actual scan handler while an edit is pending. A new scan
        # must close the dialog and invalidate its target, including its finally.
        self.page.evaluate('() => {window.showpsisi.scan()}')
        self.wait_checkpoint()
        self.assertFalse(self.page.locator('#edit-dialog').is_visible())
        self.page.locator('#cancel-scan').click()
        self.page.wait_for_function('() => window.showpsisi.getState().analysis_status === "cancelled" && !document.querySelector("#scan").disabled')
        self.page.evaluate('window.testGate.methods=[]')
        self.analyze()
        self.page.wait_for_function('() => window.showpsisi.getDetail().name === "SDT"')
        self.page.locator('#edit').click()
        self.page.locator('#rename').fill('Current edit')
        self.page.evaluate('window.testGate.release("preview_rename")')
        self.call('capabilities')
        self.assertEqual(self.page.locator('#diff').inner_text(),'')
        self.assertTrue(self.page.locator('#export').is_disabled())
        self.assertFalse(self.page.locator('#preview').is_disabled())
        self.page.locator('#preview').click()
        self.page.wait_for_function('() => !document.querySelector("#export").disabled')
        self.assertIn('Current edit',self.page.locator('#diff').inner_text())
        self.assertNotIn('Obsolete preview',self.page.locator('#diff').inner_text())
        self.page.locator('#close-edit').click()

    def test_completion_racing_cancel_keeps_terminal_success(self):
        self.gate_native_messages()
        self.page.evaluate('window.testGate.methods=["analyze"]')
        self.page.locator('#scan').click()
        self.page.wait_for_function('() => window.testGate.held.some(item=>item.method==="analyze" && item.event.payload.result?.complete)')
        self.page.locator('#cancel-scan').click()
        self.page.wait_for_function('() => window.testGate.received.some(item=>item.method==="cancel_analysis")')
        ack=self.page.evaluate('window.testGate.received.find(item=>item.method==="cancel_analysis").message.result')
        self.assertFalse(ack['requested'])
        self.assertEqual(ack['reason'],'not_running')
        self.assertTrue(self.page.locator('#scan').is_disabled())
        self.assertTrue(self.page.locator('#cancel-scan').is_disabled())
        self.page.evaluate('window.testGate.release("analyze")')
        self.page.wait_for_function('() => window.showpsisi.getState().complete && !document.querySelector("#scan").disabled')
        self.page.wait_for_function('() => window.showpsisi.getDetail().name === "SDT"')
        self.assertEqual(len(self.page.evaluate('window.showpsisi.getState().services')),6)
        self.assertIn('completed before cancellation',self.page.locator('#notice').inner_text())
        self.assertFalse(self.page.locator('#cancel-scan').is_visible())
        # A new, uncancelled analysis receives terminal + late progress in the
        # same event-loop batch. Promise continuations have not run yet: pending
        # membership, rather than busy alone, must reject the stale frame.
        self.page.locator('#scan').click()
        self.page.wait_for_function('() => window.testGate.held.some(item=>item.method==="analyze" && item.event.payload.result?.complete)')
        self.assertTrue(self.page.evaluate('''() => {
          const before=JSON.stringify(window.showpsisi.getState());
          const request=window.testGate.requests.filter(item=>item.method==='analyze').at(-1);
          window.testGate.release('analyze');
          window.testGate.listener({payload:{event:'progress',request_id:request.id,state:{source:'late-after-terminal'}}});
          return JSON.stringify(window.showpsisi.getState())===before;
        }'''))
        self.page.wait_for_function('() => window.showpsisi.getState().complete && !document.querySelector("#scan").disabled')
        self.assertEqual(len(self.page.evaluate('window.showpsisi.getState().services')),6)

    def test_real_analysis_and_selection(self):
        self.analyze()
        state=self.page.evaluate('window.showpsisi.getState()')
        self.assertEqual(len(state['services']),6)
        self.assertEqual(state['crc_errors'],2)
        self.assertEqual(state['services'][0]['name'],'Sports UHD')
        self.page.wait_for_function('() => window.showpsisi.getDetail().name === "SDT"')
        self.assertIn('Sports UHD',self.page.locator('#list').inner_text())
        self.assertIn('SDT',self.page.locator('#inspector').inner_text())
        self.assertGreater(len(self.page.evaluate('window.showpsisi.getDetail().raw_hex')),0)

    def test_empty_and_read_failure(self):
        self.assertIn('Open',self.page.locator('#list').inner_text())
        self.analyze(self.empty)
        state=self.page.evaluate('window.showpsisi.getState()')
        self.assertEqual(state['services'],[])
        self.assertEqual(state['tables'],[])
        self.page.locator('#source').fill(str(self.output/'missing.ts'))
        self.page.locator('#scan').click()
        self.page.wait_for_function('() => !document.querySelector("#scan").disabled')
        self.assertRegex(self.page.locator('#notice').inner_text().lower(),r'open|read|exist|file|source')
        self.assertEqual(self.page.evaluate('window.showpsisi.getDetail()'),{})

    def test_native_picker_is_explicitly_unsupported(self):
        self.page.locator('#browse').click()
        self.page.wait_for_function('() => document.querySelector("#notice").textContent.includes("Native file dialogs")')
        self.assertIn('local TS file path',self.page.locator('#notice').inner_text())

    def test_message_banner_history_expiry_and_keyboard_close(self):
        self.page.locator('#source').fill(str(self.output/'missing-message-source.ts'))
        self.page.locator('#scan').click()
        self.page.wait_for_function('() => window.showpsisi.getState().analysis_status === "failed" && !document.querySelector("#scan").disabled')
        error=self.page.locator('#notice').inner_text()
        self.assertEqual(self.page.locator('#notice').get_attribute('aria-live'),'assertive')
        self.assertEqual(self.page.locator('#error-message').inner_text(),error)
        self.assertTrue(self.page.locator('#error-banner').is_visible())
        self.page.locator('#reset-layout').click()
        self.assertEqual(self.page.locator('#notice').inner_text(),'Default layout restored')
        self.assertEqual(self.page.locator('#notice').get_attribute('aria-live'),'polite')
        self.assertEqual(self.page.locator('#error-message').inner_text(),error)
        self.page.wait_for_function('() => getComputedStyle(document.querySelector("#notice")).visibility === "hidden"',timeout=6000)
        self.assertEqual(self.page.locator('#notice').text_content(),'Default layout restored')
        self.page.locator('#messages').focus();self.page.keyboard.press('Enter')
        self.assertTrue(self.page.locator('#messages-dialog').is_visible())
        self.assertIn(error,self.page.locator('#message-list').inner_text())
        self.assertEqual(self.page.locator('#message-list .message-level').first.inner_text(),'info')
        self.assertEqual(self.page.locator('#message-list .message-level.error').count(),1)
        self.assertTrue(self.page.locator('#message-list time').first.get_attribute('datetime'))
        self.page.keyboard.press('Escape')
        self.assertFalse(self.page.locator('#messages-dialog').is_visible())
        self.assertEqual(self.page.evaluate('document.activeElement.id'),'messages')
        self.page.locator('#dismiss-error').click()
        self.assertFalse(self.page.locator('#error-banner').is_visible())
        self.page.locator('#messages').click()
        self.assertIn(error,self.page.locator('#message-list').inner_text())
        self.page.locator('#close-messages').click()
        self.page.locator('#save-diagnostics').click()
        self.page.wait_for_function('() => document.querySelector("#error-message").textContent.startsWith("Diagnostics failed:")')
        self.assertTrue(self.page.locator('#error-banner').is_visible())
        self.assertEqual(self.page.locator('#notice').get_attribute('aria-live'),'assertive')
        self.page.evaluate('() => {for(let i=0;i<55;i++)document.querySelector("#reset-layout").click();}')
        self.page.locator('#messages').click()
        self.assertEqual(self.page.locator('#message-list li').count(),50)
        self.assertEqual(self.page.locator('#message-list .message-level.error').count(),0)

    def test_edit_format_save_intent_and_real_exports(self):
        """Inject only Save choices; every preview/export remains a real engine call.

        This verifies browser dispatch, not native file-dialog interaction.
        """
        self.analyze()
        self.page.wait_for_function('() => window.showpsisi.getDetail().name === "SDT"')
        self.page.evaluate("""() => {
          const invoke = window.__TAURI__.core.invoke;
          window.testSave = {options:[], resolve:null};
          window.__TAURI__.core.invoke = (command,args) => {
            if (command !== 'plugin:dialog|save') return invoke(command,args);
            window.testSave.options.push(args.options);
            return new Promise(resolve => {window.testSave.resolve=resolve;});
          };
        }""")
        def preview(name):
            self.page.locator('#rename').fill(name)
            self.page.locator('#preview').click()
            self.page.wait_for_function('() => !document.querySelector("#export").disabled')
        def save_choice(choice):
            self.page.locator('#export').click()
            self.page.wait_for_function('() => !!window.testSave.resolve')
            self.page.evaluate('choice=>{const resolve=window.testSave.resolve;window.testSave.resolve=null;resolve(choice);}',choice)
        self.page.locator('#edit').click()
        self.page.locator('#edit-service').select_option('102')
        self.assertEqual(self.page.locator('#rename').input_value(),'Culture HD')
        preview('Browser parity edit')
        save_choice(None)
        self.page.wait_for_function('() => !document.querySelector("#export").disabled')
        self.assertTrue(self.page.locator('#edit-dialog').is_visible())
        self.page.locator('#export').click()
        self.page.wait_for_function('() => !!window.testSave.resolve')
        self.page.locator('#rename').fill('Changed while Save was pending')
        stale=self.output/'artifacts/stale-save.ts'
        self.page.evaluate('path=>{const resolve=window.testSave.resolve;window.testSave.resolve=null;resolve(path);}',str(stale))
        self.page.wait_for_function('() => document.querySelector("#diff").textContent.includes("preview changed")')
        self.assertFalse(stale.exists())
        self.assertTrue(self.page.locator('#export').is_disabled())
        preview('Browser parity edit')
        self.page.locator('#export-format').select_option('bin')
        save_choice(str(self.output/'artifacts/wrong.ts'))
        self.page.wait_for_function('() => document.querySelector("#diff").textContent.includes("Use a .bin")')
        self.assertFalse((self.output/'artifacts/wrong.ts').exists())
        for format_ in ('bin','ts'):
            with self.subTest(format=format_):
                if not self.page.locator('#edit-dialog').is_visible():
                    self.page.locator('#edit').click()
                    self.page.locator('#edit-service').select_option('102')
                    preview('Browser parity edit')
                self.page.locator('#export-format').select_option(format_)
                output=self.output/('artifacts/parity-export.'+format_)
                save_choice(str(output))
                self.page.wait_for_function('() => !document.querySelector("#edit-dialog").open')
                options=self.page.evaluate('window.testSave.options.at(-1)')
                self.assertEqual(options['defaultPath'],'edited-si.'+format_)
                self.assertEqual(options['filters'][0]['extensions'],[format_])
                manifest=json.loads(Path(str(output)+'.manifest.json').read_text())
                self.assertEqual(manifest['format'],format_)
                self.assertEqual(manifest['edit']['service_id'],102)
                self.assertEqual(manifest['edit']['after'],'Browser parity edit')
                raw=output.read_bytes()
                self.assertEqual(len(raw),manifest['bytes'])
                if format_=='bin':
                    from make_fixture import crc
                    for section in manifest['sections']:
                        part=raw[section['bin_offset']:section['bin_offset']+section['bytes']]
                        self.assertEqual(((part[1]&15)<<8|part[2])+3,len(part))
                        if part[1]&0x80 or part[0]==0x73:
                            self.assertEqual(crc(part),0)
                else:
                    from core_client import Core
                    core=Core()
                    try: parsed=core.call('analyze',{'path':str(output)})
                    finally: core.close()
                    self.assertEqual(next(service['name'] for service in parsed['services'] if service['id']==102),'Browser parity edit')
                    self.assertEqual(parsed['crc_errors'],0)
                identities={path:(path.read_bytes(),path.stat().st_mtime_ns) for path in (output,Path(str(output)+'.manifest.json'))}
                self.page.locator('#edit').click()
                self.page.locator('#edit-service').select_option('102')
                preview('Browser parity edit')
                save_choice(str(output))
                self.page.wait_for_function('() => document.querySelector("#diff").textContent.includes("already exists")')
                self.assertFalse(self.page.locator('#export').is_disabled())
                for path,identity in identities.items():
                    self.assertEqual((path.read_bytes(),path.stat().st_mtime_ns),identity)
                self.page.locator('#close-edit').click()
        self.assertEqual(hashlib.sha256(self.sample.read_bytes()).hexdigest(),self.original_hash)

    def test_use_comparison_snapshot_preserves_side_and_edit_cutoff(self):
        self.analyze()
        self.page.wait_for_function('() => window.showpsisi.getDetail().name === "SDT"')
        old=self.page.evaluate('window.showpsisi.getState()')
        self.page.locator('#compare-snapshots').click()
        self.page.locator('#compare-from').fill(str(old['history'][0]['last_packet']))
        self.page.locator('#compare-to').fill(str(old['packets']-1))
        self.page.locator('#run-comparison').click()
        self.page.wait_for_function('() => !!window.showpsisi.getComparison()')
        result=self.page.evaluate('window.showpsisi.getComparison()')
        index=next(i for i,c in enumerate(result['changes']) if c['kind']=='services' and c['identity']['service_id']==103)
        before=result['changes'][index]['before']
        # Every distinct source keeps its side's exact cutoff without moving the workspace.
        for evidence_index,evidence in enumerate(before['evidence']):
            self.page.locator('[data-comparison-evidence="'+str(index)+':A:'+str(evidence_index)+'"]').click()
            self.page.wait_for_function('id=>window.showpsisi.getUiState().settled && window.showpsisi.getDetail().id===id',arg=evidence['id'])
            detail=self.page.evaluate('window.showpsisi.getDetail()')
            self.assertEqual(detail['pid'],evidence['pid'])
            self.assertEqual(detail['native_table_at_packet'],before['at_packet'])
            self.assertEqual(self.page.evaluate('window.showpsisi.getState().selected_packet'),old['selected_packet'])
        self.page.locator('[data-use-comparison="'+str(index)+':A"]').click()
        self.page.wait_for_function('packet=>window.showpsisi.getUiState().settled && window.showpsisi.getState().selected_packet===packet',arg=before['at_packet'])
        self.assertEqual(self.page.evaluate('window.showpsisi.getUiState().tab'),'Services')
        self.assertEqual(self.page.evaluate('window.showpsisi.getUiState().selected_service'),103)
        self.assertEqual(self.page.evaluate('window.showpsisi.getDetail().native_table_at_packet'),before['at_packet'])
        self.page.locator('#edit').click()
        self.assertEqual(self.page.locator('#edit-service').input_value(),'103')
        self.assertEqual(self.page.locator('#rename').input_value(),'Sports HD')
        self.page.locator('#rename').fill('Historical parity edit')
        self.page.locator('#preview').click()
        self.page.wait_for_function('() => !document.querySelector("#export").disabled')
        self.assertIn('version 1 → 2',self.page.locator('#diff').inner_text())
        self.assertEqual(hashlib.sha256(self.sample.read_bytes()).hexdigest(),self.original_hash)

    def test_preview_export_reparse_and_no_overwrite(self):
        self.analyze()
        self.page.wait_for_function('() => window.showpsisi.getDetail().name === "SDT"')
        self.page.locator('#edit').click()
        self.assertTrue(self.page.locator('#export').is_disabled())
        self.page.locator('#rename').fill('Browser verified service')
        self.page.locator('#preview').click()
        self.page.wait_for_function('() => !document.querySelector("#export").disabled')
        self.page.locator('#rename').fill('Changed after preview')
        self.assertTrue(self.page.locator('#export').is_disabled())
        self.page.locator('#rename').fill('Browser verified service')
        self.page.locator('#preview').click()
        self.page.wait_for_function('() => !document.querySelector("#export").disabled')
        self.page.locator('#export').click()
        self.page.wait_for_function('() => document.querySelector("#diff").textContent.includes("Native file dialogs")')
        self.page.locator('#close-edit').click()
        # Save dialog is honestly unsupported. Verify export using the same real
        # JSONL API, without claiming the native save dialog was exercised.
        service=self.page.evaluate('window.showpsisi.getState().services[0]')
        preview=self.call('preview_rename',{'id':service['source_id'],'service_id':service['id'],'name':'Browser verified service'})
        output=self.output/'artifacts/browser-verified.ts'
        self.call('export',{'path':str(output),'preview_token':preview['token']})
        manifest=json.loads(Path(str(output)+'.manifest.json').read_text())
        self.assertTrue(manifest)
        self.assertEqual(hashlib.sha256(self.sample.read_bytes()).hexdigest(),self.original_hash)
        parsed=self.call('analyze',{'path':str(output)})
        self.assertIn('Browser verified service',[service['name'] for service in parsed['services']])
        self.assertEqual(parsed['crc_errors'],0)
        error=self.page.evaluate('async path=>{try{await window.showpsisi.call("export",{path});return "unexpected success"}catch(error){return String(error)}}',str(output))
        self.assertIn('already exists',error)
        blocked=self.page.evaluate('async path=>{try{await window.showpsisi.call("export",{path});return "unexpected success"}catch(error){return String(error)}}',str(self.sample))
        self.assertIn('validation artifacts directory',blocked)
        self.assertEqual(hashlib.sha256(self.sample.read_bytes()).hexdigest(),self.original_hash)

    def test_tree_composite_focus_states_and_keyboard_contract(self):
        self.analyze()
        self.page.wait_for_function('() => window.showpsisi.getDetail().name === "SDT"')
        tree = self.page.locator('#tree-area')
        self.assertEqual(tree.get_attribute('role'), 'tree')
        root = tree.locator('.tree-node[data-path="section"]')
        root.focus()
        root.press('ArrowLeft')
        self.page.wait_for_function('() => document.activeElement.getAttribute("aria-expanded") === "false"')
        self.assertEqual(tree.locator('[tabindex="0"]').count(), 1)
        root.press('ArrowRight')
        self.page.wait_for_function('() => document.activeElement.getAttribute("aria-expanded") === "true"')
        root.press('ArrowRight')
        self.assertEqual(self.page.locator(':focus').get_attribute('aria-level'), '2')
        self.page.keyboard.press('ArrowLeft')
        self.assertTrue(root.evaluate('(el) => el === document.activeElement'))
        for _ in range(3):
            root.press('Space')
            self.assertEqual(root.get_attribute('aria-expanded'), 'false')
            root.press('Enter')
            self.assertEqual(root.get_attribute('aria-expanded'), 'true')
        child = root.locator(':scope > .tree-children > .tree-node').first
        was_expanded = child.get_attribute('aria-expanded')
        child.locator(':scope > .tree-row').click()
        self.assertNotEqual(child.get_attribute('aria-expanded'), was_expanded)
        self.assertEqual(root.get_attribute('aria-expanded'), 'true')
        leaf = child.locator('.tree-leaf').first
        leaf.click()
        self.assertTrue(leaf.evaluate('(el) => el === document.activeElement'))
        self.assertEqual(child.get_attribute('aria-expanded'), 'true')
        self.assertEqual(root.get_attribute('aria-expanded'), 'true')
        self.assertEqual(tree.locator('[tabindex="0"]').count(), 1)
        root.focus()
        root.press('End')
        last = tree.locator('[role="treeitem"]').evaluate_all('(items) => items.filter(el => el.checkVisibility()).at(-1).dataset.nodePath')
        self.assertEqual(self.page.locator(':focus').get_attribute('data-node-path'), last)
        self.page.keyboard.press('Home')
        self.assertTrue(root.evaluate('(el) => el === document.activeElement'))
        self.page.keyboard.press('ArrowDown')
        focused = self.page.locator(':focus').get_attribute('data-node-path')
        self.assertNotEqual(focused, root.get_attribute('data-node-path'))
        self.page.keyboard.press('ArrowUp')
        self.assertTrue(root.evaluate('(el) => el === document.activeElement'))
        self.page.keyboard.press('Tab')
        self.assertFalse(tree.evaluate('(el) => el.contains(document.activeElement)'))
        self.page.keyboard.press('Shift+Tab')
        self.assertTrue(root.evaluate('(el) => el === document.activeElement'))
        self.assertEqual(root.locator(':scope > .tree-row').evaluate('(el) => getComputedStyle(el).outlineWidth'), '2px')
        self.page.locator('#tree-search').fill('service_name')
        self.page.locator('#tree-search').press('Enter')
        self.assertTrue(tree.evaluate('(el) => el.contains(document.activeElement)'))
        self.assertEqual(tree.locator('[tabindex="0"]').count(), 1)
        # No keyboard focus may be trapped on a hidden descendant after folding.
        tree.locator('[tabindex="0"]').press('Home')
        self.page.keyboard.press('ArrowLeft')
        self.assertTrue(self.page.locator(':focus').is_visible())
        self.page.locator('#tree-search').fill('NO_FIELD_MATCH_7129')
        self.assertEqual(tree.locator('[tabindex="0"]').count(), 0)
        self.page.locator('#tree-search').press('Enter')
        self.assertTrue(self.page.locator('#tree-search').evaluate('(el) => el === document.activeElement'))
        self.page.locator('#tree-search').press('Escape')
        self.assertEqual(tree.locator('[tabindex="0"]').count(), 1)
        self.assertEqual(tree.locator('.tree-leaf[aria-expanded]').count(), 0)
        # No native summary role overrides: plain treeitems own nested groups.
        self.assertEqual(tree.locator('details,summary,[aria-owns]').count(), 0)
        for item in tree.locator('.tree-node').all():
            self.assertEqual(item.locator(':scope > .tree-children').get_attribute('role'), 'group')
            self.assertTrue(item.get_attribute('aria-label'))
        session = self.page.context.new_cdp_session(self.page)
        ax = session.send('Accessibility.getFullAXTree')['nodes']
        session.detach()
        exposed = [item for item in ax if not item.get('ignored')]
        self.assertTrue(any(item.get('role', {}).get('value') == 'tree' for item in exposed))
        root_ax = next(item for item in exposed if item.get('role', {}).get('value') == 'treeitem'
                       and item.get('name', {}).get('value') == root.get_attribute('aria-label'))
        self.assertTrue(any(prop['name'] == 'expanded' for prop in root_ax.get('properties', [])))
        indexed = {item['nodeId']: item for item in ax}
        self.assertTrue(any(indexed[child].get('role', {}).get('value') == 'group' for child in root_ax['childIds']))
        self.page.locator('#tree-search').press('Enter')
        self.page.screenshot(path=str(self.artifacts/'tree-keyboard-focus.png'))

    def test_record_search_keyboard_and_tree(self):
        self.analyze()
        self.page.wait_for_function('() => window.showpsisi.getDetail().name === "SDT"')
        self.page.keyboard.press('Control+k')
        self.assertTrue(self.page.locator('#search').evaluate('(element)=>element===document.activeElement'))
        self.page.locator('#search').fill('Sports UHD')
        self.assertEqual(self.page.locator('#list [role="option"]').count(),1)
        self.page.locator('#search').fill('NO_SUCH_SERVICE_9817')
        self.assertIn('No matching records',self.page.locator('#list').inner_text())
        self.page.locator('#search').fill('')
        rows=self.page.locator('#list [role="option"]')
        rows.first.focus();rows.first.press('ArrowDown')
        self.page.keyboard.press('Enter')
        self.page.wait_for_function('() => document.querySelectorAll("#list [aria-selected=true]").length===1 && !document.querySelector("#inspector .loading")')
        self.assertEqual(self.page.locator('#list [aria-selected="true"]').get_attribute('data-key'),rows.nth(1).get_attribute('data-key'))
        self.page.locator('#tree-area .tree-node[data-path="section"]').wait_for()
        root=self.page.locator('#tree-area .tree-node[data-path="section"]')
        root.focus()
        self.page.keyboard.press('ArrowLeft')
        self.assertFalse(root.evaluate('(element)=>element.getAttribute("aria-expanded")==="true"'))
        self.page.keyboard.press('ArrowRight')
        self.assertTrue(root.evaluate('(element)=>element.getAttribute("aria-expanded")==="true"'))
        self.page.locator('#tree-search').fill('descriptor_tag')
        self.assertIn('descriptor_tag',self.page.locator('#tree-area').inner_text())
        self.page.locator('#tree-search').fill('NO_SUCH_FIELD_9817')
        self.assertIn('No matching fields',self.page.locator('#tree-area').inner_text())
        self.page.locator('#tree-search').fill('')
        self.page.locator('[data-view="hex"]').click()
        self.assertTrue(self.page.locator('[data-view="hex"]').evaluate('(element)=>element===document.activeElement'))
        self.assertTrue(self.page.locator('[aria-label="Section hex dump"]').inner_text().strip())
        self.page.locator('[data-view="xml"]').click()
        self.assertIn('SDT',self.page.locator('[aria-label="TSDuck XML"]').inner_text())

    def test_backend_exit_settles_pending_and_dead_startup(self):
        import signal
        if not hasattr(signal,'SIGSTOP'):
            self.skipTest('Deterministic in-flight process pause requires POSIX SIGSTOP')
        # Pause only this test's owned child, guaranteeing real requests are in
        # flight before killing it. No fake bridge responses or other PIDs.
        self.bridge.proc.send_signal(signal.SIGSTOP)
        self.page.evaluate('() => {window.lifecycleResult=null;window.showpsisi.call("capabilities").then(()=>window.lifecycleResult="unexpected success",error=>window.lifecycleResult=String(error));}')
        self.page.locator('#scan').click()
        self.page.wait_for_function('() => document.querySelector("#scan").disabled')
        self.bridge.proc.kill()
        self.bridge.proc.wait(timeout=5)
        self.page.wait_for_function('() => window.lifecycleResult !== null')
        self.assertRegex(self.page.evaluate('window.lifecycleResult').lower(),r'backend|stopped|disconnected')
        self.page.wait_for_function('() => /stopped|disconnected|unavailable/i.test(document.querySelector("#notice").textContent)')
        self.assertTrue(self.page.locator('#scan').is_disabled())
        self.assertNotIn('Scanning',self.page.locator('#scan').inner_text())
        self.assertNotIn('Analyzing',self.page.locator('#scan').inner_text())
        self.assertEqual(self.page.evaluate('window.showpsisi.getState()'),{})
        retry=self.page.locator('#retry-inspect')
        self.assertTrue(retry.count()==0 or retry.is_disabled(),'Disconnected backend must not offer an active retry')
        self.page.screenshot(path=str(self.artifacts/'backend-exit.png'),full_page=True)
        self.page.reload()
        self.page.wait_for_function('() => /stopped|disconnected|unavailable/i.test(document.querySelector("#notice").textContent)')
        self.assertTrue(self.page.locator('#scan').is_disabled())
        self.assertRegex(self.page.locator('#runtime').inner_text().lower(),r'disconnected|unavailable|stopped')

    def test_fixed_table_type_palette_has_distinct_symbols_and_colors(self):
        # This tests authored presentation helpers, not fabricated decoder evidence.
        names=['PAT','PMT','CAT','NIT','SDT','BAT','EIT','TDT','TOT','AIT','DSMCC_download_data_message']
        values=self.page.evaluate("""names=>names.map(name=>{
          const host=document.createElement('div');host.className='inspector';
          host.innerHTML='<h2>'+categoryBadge({name})+'</h2>';
          document.body.append(host);const badge=host.querySelector('.table-kind');
          const result={name,category:tableCategory(name),color:getComputedStyle(badge).color,
            background:getComputedStyle(badge).backgroundColor,title:badge.title,text:badge.textContent};
          host.remove();return result;
        })""",names)
        self.assertEqual(len({v['color'] for v in values}),len(names))
        self.assertEqual(len({v['category'][1] for v in values}),len(names))
        for value in values:
            self.assertIn(value['category'][1],value['text'])
            self.assertIn(value['name'],value['title'])
        self.assertEqual(self.page.evaluate("tableCategory('unknown private payload')[0]"),'other')
        self.assertEqual(self.page.evaluate("tableCategory('DSMCC_user_to_network_message')[0]"),'dsmcc')

    def test_section_evidence_crc_groups_arrival_and_scopes(self):
        from make_fixture import section, descriptor, word, crc
        def sdt(extension, number, last, name, bad=False):
            desc=descriptor(0x48,b'\x01\x00'+bytes([len(name)])+name)
            raw=bytearray(section(0x42,extension,1,word(2)+b'\xff'+word(100+number)+b'\xff'+word(0x8000+len(desc))+desc))
            raw[6]=number; raw[7]=last; raw[-4:]=crc(raw[:-4]).to_bytes(4,'big')
            if bad: raw[-1]^=1
            return bytes(raw)
        parts=[sdt(1,0,1,b'A'),sdt(1,1,1,b'B'),sdt(1,1,1,b'Bad B',True),
               sdt(2,0,1,b'Missing sibling'),sdt(3,0,0,b'All bad',True),sdt(1,0,1,b'A')]
        fixture=self.output/'section-evidence.ts'
        fixture.write_bytes(b''.join(bytes([0x47,0x40,0x11,0x10+i,0])+raw+b'\xff'*(183-len(raw)) for i,raw in enumerate(parts)))
        self.analyze(fixture)
        state=self.page.evaluate('window.showpsisi.getState()')
        self.assertEqual({g['validity'] for g in state['table_groups']},{'valid','mixed','all_invalid'})
        self.page.locator('[data-tab="Tables"]').click()
        self.assertEqual(self.page.locator('.table-branch').count(),3)
        self.page.locator('#table-group-toggle').click()
        bad=[r for r in state['tables'] if r['crc']['status']=='invalid']
        self.assertEqual(len(bad),2)
        self.assertFalse(self.page.locator('#show-bad-crc').is_checked())
        self.assertEqual(self.page.locator('#list [role="option"]').count(),len(state['tables'])-2)
        self.assertIn('Bad CRC (2)',self.page.locator('.table-controls').inner_text())
        self.page.locator('#show-bad-crc').check()
        self.assertEqual(self.page.locator('#list [role="option"]').count(),len(state['tables']))
        self.page.locator('#show-bad-crc').uncheck()
        self.page.locator('#table-group-toggle').click()
        branches=self.page.locator('.table-branch')
        self.assertEqual(branches.count(),3)
        for branch in branches.all():
            if branch.locator('[role=option]').count():
                self.assertEqual(branch.locator('[role=option][tabindex="0"]').count(),1)
        self.assertIn('all_invalid',self.page.locator('#list').inner_text())
        mixed=branches.filter(has_text='mixed')
        mixed.locator('summary').click()
        self.assertTrue(mixed.evaluate('(el)=>el.open'))
        mixed.locator('summary').click()
        self.assertFalse(mixed.evaluate('(el)=>el.open'))
        self.page.locator('#table-group-toggle').click()
        row=next(r for r in state['tables'] if r['extension']==1 and r['section']==0)
        self.page.evaluate('id=>window.showpsisi.inspect(id)',row['id'])
        self.page.wait_for_function('id=>window.showpsisi.getDetail().id===id',arg=row['id'])
        detail=self.page.evaluate('window.showpsisi.getDetail()')
        self.page.locator('#identity-toggle').click()
        identity=self.page.locator('.identity-line').inner_text()
        self.assertIn('TID 0x42',identity)
        self.assertIn(detail['crc']['transmitted_hex'],identity)
        self.assertEqual(detail['distribution']['observation_count'],2)
        self.page.locator('#arrival-toggle').click()
        self.assertIn('not PCR',self.page.locator('.arrival').inner_text())
        self.assertGreater(self.page.locator('.section-density span').count(),0)
        self.page.locator('#section-group-toggle').click()
        self.assertIn('mixed',self.page.locator('#section-group').inner_text())
        sibling=next(r for r in state['tables'] if r['extension']==1 and r['section']==1 and r['valid'])
        self.page.locator('#section-choice').select_option(sibling['id'])
        self.page.wait_for_function('id=>window.showpsisi.getDetail().id===id',arg=sibling['id'])
        self.page.locator('#section-choice').select_option(row['id'])
        self.page.wait_for_function('id=>window.showpsisi.getDetail().id===id',arg=row['id'])
        self.page.locator('[data-scope="section"]').click()
        self.page.locator('#tree-search').fill('TSDuck decoded structure')
        self.assertIn('section-local',self.page.locator('#tree-area').inner_text())
        self.page.locator('[data-scope="merged"]').click()
        self.page.locator('[data-view="xml"]').click()
        self.assertGreater(self.page.locator('.xml-tag').count(),0)
        self.assertGreater(self.page.locator('.xml-string').count(),0)
        self.assertEqual(self.page.locator('.evidence').inner_text(),detail['merged']['tsduck_xml'])
        self.page.locator('[data-view="tree"]').click()
        self.page.locator('#tree-search').fill('')
        root=self.page.locator('[data-path="section"]')
        for unused in range(5):
            self.page.locator('#collapse-tree').click()
            self.assertEqual(root.get_attribute('aria-expanded'),'false')
            self.assertEqual(self.page.locator('#tree-area [role="treeitem"]:visible').count(),1)
            root.focus(); root.press('ArrowRight')
            self.assertEqual(root.get_attribute('aria-expanded'),'true')
        for width,height in [(1000,680),(520,1000)]:
            self.page.set_viewport_size({'width':width,'height':height})
            if self.page.locator('#section-group-toggle').get_attribute('aria-expanded') == 'false':
                self.page.locator('#section-group-toggle').click()
            tree=self.page.locator('#tree-area')
            self.assertGreaterEqual(tree.bounding_box()['height'],140)
            tree.scroll_into_view_if_needed()
            self.assertTrue(tree.is_visible())
            self.assertLessEqual(self.page.evaluate('document.documentElement.scrollWidth'),width)
        self.page.set_viewport_size({'width':1440,'height':1000})
        self.page.locator('#inspector').evaluate('(el)=>el.scrollTop=0')
        self.page.screenshot(path=str(self.artifacts/'section-evidence-mixed.png'),full_page=True)
        # All-invalid source must not reveal filtered evidence by auto-selection.
        only_bad=self.output/'only-bad-crc.ts'
        raw=sdt(4,0,0,b'Bad CRC only',True)
        only_bad.write_bytes(bytes([0x47,0x40,0x11,0x10,0])+raw+b'\xff'*(183-len(raw)))
        self.analyze(only_bad)
        self.assertFalse(self.page.evaluate('Boolean(window.showpsisi.getDetail().id)'))
        self.assertEqual(self.page.locator('#list [role="option"]').count(),0)
        self.page.locator('#show-bad-crc').check()
        self.assertEqual(self.page.locator('#list [role="option"]').count(),1)
        self.page.locator('#list [role="option"]').click()
        self.page.wait_for_function('()=>window.showpsisi.getDetail().crc?.status==="invalid"')


    def test_service_media_columns_preserve_classification_and_unknowns(self):
        from test_service_metadata import ServiceMetadataTests
        fixtures=ServiceMetadataTests()
        parts=[fixtures.pat(),fixtures.pmt(),(0x11,fixtures.sdt(last=0)),fixtures.nit()]
        path=self.output/'media-columns.ts'
        path.write_bytes(b''.join(bytes([0x47,0x40|(pid>>8),pid&255,0x10,0])+raw+b'\xff'*(183-len(raw)) for pid,raw in parts))
        self.analyze(path)
        row=self.page.locator('.record.services').first
        self.assertEqual(row.locator('.lcn').inner_text(),'7')
        self.assertEqual(row.locator('.service-type').inner_text(),'Digital TV\n0x01')
        self.assertIn('V 0x0200',row.inner_text())
        self.assertIn('A 0x0201, 0x0202',row.inner_text())
        self.assertNotIn('0x0203',row.locator('.media-pids').inner_text())
        self.page.locator('#theme-toggle').click()
        self.page.screenshot(path=str(self.artifacts/'editor-media-light.png'),full_page=True)
        path=self.output/'unknown-media-columns.ts'
        parts=[fixtures.pat(),(0x11,fixtures.sdt(last=0))]
        path.write_bytes(b''.join(bytes([0x47,0x40|(pid>>8),pid&255,0x10,0])+raw+b'\xff'*(183-len(raw)) for pid,raw in parts))
        self.analyze(path)
        row=self.page.locator('.record.services').first
        self.assertEqual(row.locator('.lcn').inner_text(),'—')
        self.assertEqual(row.locator('.media-pids').get_attribute('title'),'PMT unavailable')
        self.assertEqual(row.locator('.media-pids').inner_text(),'V —\nA —')

    def test_table_card_pagination_keeps_all_sibling_sections(self):
        from make_fixture import section, descriptor, word, crc
        packets=[]
        for extension in range(1,102):
            for number in range(2):
                desc=descriptor(0x48,b'\x01\x00\x01A')
                raw=bytearray(section(0x42,extension,1,word(2)+b'\xff'+word(100+number)+b'\xff'+word(0x8000+len(desc))+desc))
                raw[6]=number;raw[7]=1;raw[-4:]=crc(raw[:-4]).to_bytes(4,'big')
                packets.append(bytes([0x47,0x40,0x11,0x10+(len(packets)%16),0])+raw+b'\xff'*(183-len(raw)))
        fixture=self.output/'table-card-pages.ts';fixture.write_bytes(b''.join(packets))
        self.analyze(fixture)
        self.page.locator('[data-tab="Tables"]').click()
        self.assertEqual(self.page.locator('.table-branch').count(),100)
        self.assertEqual(self.page.locator('.table-branch [role="option"]').count(),200)
        self.assertIn('of 101 tables',self.page.locator('#page-label').inner_text())
        self.page.locator('#next').click()
        self.assertEqual(self.page.locator('.table-branch').count(),1)
        self.assertEqual(self.page.locator('.table-branch [role="option"]').count(),2)
        self.page.locator('.table-branch > summary').click()
        self.assertEqual(self.page.locator('.table-branch [role="option"]:visible').count(),2)
        exact=self.page.locator('.table-branch [role="option"]').last
        expected_id=exact.get_attribute('data-key')
        exact.click()
        self.page.wait_for_function('id=>window.showpsisi.getDetail().id===id',arg=expected_id)
        self.assertEqual(self.page.evaluate('window.showpsisi.getDetail().section'),1)

        self.page.locator('#prev').click()
        self.assertEqual(self.page.locator('.table-branch').count(),100)

    def test_editor_theme_pid_columns_and_arrival_axis(self):
        self.analyze()
        p=self.page
        p.wait_for_function('()=>window.showpsisi.getDetail().id')
        pids=p.locator('.pid-row').evaluate_all('(els)=>els.map(e=>Number(e.dataset.pid))')
        self.assertEqual(pids,sorted(pids))
        self.assertGreater(len(pids),2)
        self.assertIn('TYPE',p.locator('.service-head').inner_text())
        self.assertIn('VIDEO / AUDIO PIDs',p.locator('.service-head').inner_text())
        self.assertEqual(p.locator('.record.services .media-pids').count(),6)
        state=p.evaluate('window.showpsisi.getState()')
        for service, row in zip(state['services'],p.locator('.record.services').all()):
            self.assertEqual(row.locator('.service-type .numeric').inner_text(),f"0x{service['service_type']:02X}")
            for pid in service['audio_pids'] + service['video_pids']:
                self.assertIn(f'0x{pid:04X}',row.locator('.media-pids').inner_text())
        for theme in ('dark','light'):
            if p.locator('html').get_attribute('data-theme') != theme: p.locator('#theme-toggle').click()
            p.screenshot(path=str(self.artifacts/f'editor-services-{theme}.png'),full_page=True)
        p.locator('#theme-toggle').click()
        p.locator('[data-tab="Tables"]').click()
        self.assertGreater(p.locator('.table-branch').count(),0)
        branch=p.locator('.table-branch').first
        branch.locator('summary').focus();branch.locator('summary').press('Enter')
        self.assertTrue(branch.evaluate('(e)=>e.open'))
        row=branch.locator('[role="option"]').first
        row.focus();row.press('Enter')
        p.wait_for_function('()=>!document.querySelector("#inspector .empty")')
        p.locator('#arrival-toggle').click()
        self.assertEqual(p.locator('.arrival .arrival-axis span').count(),5)
        self.assertIn('packet positions',p.locator('.arrival .axis-basis').inner_text())
        self.assertTrue(p.locator('#table-filter-tools #show-bad-crc').is_visible())
        for theme in ('dark','light'):
            if p.locator('html').get_attribute('data-theme') != theme:
                p.locator('#theme-toggle').focus();p.locator('#theme-toggle').press('Enter')
            self.assertEqual(p.locator('html').get_attribute('data-theme'),theme)
            contrasts=p.locator('.btn:not(:disabled), .tabs button.active, .nav.active, .history-point').evaluate_all("""els => {
              const rgb=s=>(s.match(/[0-9.]+/g)||[]).map(Number);
              const lum=c=>c.slice(0,3).map(v=>{v/=255;return v<=.04045?v/12.92:((v+.055)/1.055)**2.4}).reduce((n,v,i)=>n+v*[.2126,.7152,.0722][i],0);
              return els.filter(e=>e.getClientRects().length).map(e=>{
                let node=e,bg;
                while(node){bg=rgb(getComputedStyle(node).backgroundColor);if(bg.length===3||bg[3]>0)break;node=node.parentElement;}
                const fg=lum(rgb(getComputedStyle(e).color)),back=lum(bg||[255,255,255]);
                return {text:e.textContent,ratio:(Math.max(fg,back)+.05)/(Math.min(fg,back)+.05)};
              });
            }""")
            self.assertTrue(all(c['ratio']>=4.5 for c in contrasts),contrasts)
            for width,height in [(1440,900),(1000,680),(520,1000)]:
                p.set_viewport_size({'width':width,'height':height})
                self.assertLessEqual(p.evaluate('document.documentElement.scrollWidth'),width)
                self.assertGreaterEqual(p.locator('#tree-area').bounding_box()['height'],140)
                p.screenshot(path=str(self.artifacts/f'editor-{theme}-{width}.png'),full_page=True)
        p.set_viewport_size({'width':1440,'height':900})
        p.reload()
        self.assertEqual(p.locator('html').get_attribute('data-theme'),'light')
        self.analyze()
        p.locator('.pid-row').first.click()
        pid=int(p.locator('.pid-row.active').get_attribute('data-pid'))
        self.assertTrue(all('PID '+format(pid,'#06X').replace('0X','0x') in x.inner_text() for x in p.locator('.table-branch > summary').all()))
        # Native timing metadata, no fabricated browser state.
        timed=self.call('analyze',{'path':str(self.sample),'bitrate':1504000})
        p.evaluate('()=>window.showpsisi.snapshot(-1)')
        p.wait_for_function('()=>window.showpsisi.getState().timing?.seconds_per_packet===0.001')
        self.assertIn('user supplied',p.locator('#timeline .axis-basis').inner_text())
        self.assertIn('not PCR',p.locator('#timeline .axis-basis').inner_text())
        self.assertTrue(all(x.inner_text().endswith(' s') for x in p.locator('#timeline .arrival-axis span').all()))


    def test_historical_inspection_keeps_native_siblings_at_cutoff(self):
        from make_fixture import section,descriptor,word,crc
        def sdt(number,name):
            desc=descriptor(0x48,b'\x01\x00'+bytes([len(name)])+name)
            raw=bytearray(section(0x42,1,1,word(2)+b'\xff'+word(100+number)+b'\xff'+word(0x8000+len(desc))+desc))
            raw[6]=number;raw[7]=1;raw[-4:]=crc(raw[:-4]).to_bytes(4,'big')
            return bytes(raw)
        parts=[sdt(0,b'A'),sdt(1,b'Old B'),sdt(0,b'A'),sdt(1,b'New B'),sdt(0,b'A')]
        fixture=self.output/'historical-inspection.ts'
        fixture.write_bytes(b''.join(bytes([0x47,0x40,0x11,0x10+i,0])+raw+b'\xff'*(183-len(raw)) for i,raw in enumerate(parts)))
        self.analyze(fixture)
        aid=self.page.evaluate('window.showpsisi.getState().services.find(service=>service.name==="A").source_id')
        self.page.evaluate('id=>window.showpsisi.snapshot(1,id)',aid)
        self.page.wait_for_function('() => window.showpsisi.getDetail().native_table_at_packet === 1')
        detail=self.page.evaluate('window.showpsisi.getDetail()')
        def names(value):
            return [node['children'][0]['attributes']['service_name'] for node in value['native_table']['children'] if node['name']=='service']
        self.assertEqual(names(detail),['A','Old B'])
        old_b_id=next(row['id'] for row in detail['native_table_sources'] if row['section']==1)
        self.assertEqual(detail['count'],1)
        self.assertEqual(detail['last_packet'],0)
        self.assertEqual(detail['occurrences'],[0])
        self.page.locator('#tree-search').fill('Old B')
        self.assertIn('Old B',self.page.locator('#tree-area').inner_text())
        self.assertNotIn('New B',self.page.locator('#tree-area').inner_text())
        self.page.locator('#scope-details-toggle').click()
        for view in ('hex','xml','references','tree'):
            self.page.locator('[data-view="'+view+'"]').click()
            self.assertIn('packet 1',self.page.locator('#native-assembly-evidence').inner_text())
            self.assertEqual(names(self.page.evaluate('window.showpsisi.getDetail()')),['A','Old B'])
        self.page.evaluate('id=>window.showpsisi.snapshot(0,id)',aid)
        self.page.wait_for_function('() => window.showpsisi.getDetail().native_table_at_packet === 0')
        self.assertFalse(self.page.evaluate('window.showpsisi.getDetail().native_table_complete'))
        self.assertNotIn('native_table',self.page.evaluate('window.showpsisi.getDetail()'))
        self.page.evaluate('id=>window.showpsisi.snapshot(-1,id)',aid)
        self.page.wait_for_function('() => window.showpsisi.getDetail().native_table_at_packet === 4')
        self.assertEqual(names(self.page.evaluate('window.showpsisi.getDetail()')),['A','New B'])
        # Inspecting a superseded fragment must never present legacy fallback XML
        # as the current merged generation, even if candidate sibling IDs exist.
        self.page.evaluate('id=>window.showpsisi.snapshot(4,id)',old_b_id)
        self.page.wait_for_function('id=>window.showpsisi.getDetail().id===id',arg=old_b_id)
        superseded=self.page.evaluate('window.showpsisi.getDetail()')
        self.assertFalse(superseded['merged']['complete'])
        self.assertIsNone(superseded['merged']['native_table'])
        self.assertIsNone(superseded['merged']['tsduck_xml'])
        self.page.locator('[data-view="xml"]').click()
        self.assertIn('XML unavailable for this scope',self.page.locator('.evidence').inner_text())
        self.assertNotIn('Old B',self.page.locator('.evidence').inner_text())
        self.assertNotIn('New B',self.page.locator('.evidence').inner_text())

    def test_standards_context_and_invalid_extra_pids(self):
        self.open_scan_options()
        for standard in ('atsc','isdb-japan','dtmb'):
            self.page.locator('#standards').select_option(standard)
            self.page.locator('#extra-pids').fill('0x123, 291')
            self.analyze()
            state=self.page.evaluate('window.showpsisi.getState()')
            self.assertEqual(state['standards_context'],standard)
            self.page.wait_for_function('() => window.showpsisi.getDetail().standards_context === '+json.dumps(standard))
            self.assertIn(standard,self.page.locator('#inspector').inner_text().lower())
        before=self.page.evaluate('window.showpsisi.getState().revision')
        self.page.locator('#extra-pids').fill('8192')
        self.page.locator('#scan').click()
        self.assertIn('between 0 and 8191',self.page.locator('#notice').inner_text())
        self.assertTrue(self.page.locator('#extra-pids').evaluate('(element)=>element===document.activeElement'))
        self.assertEqual(self.page.evaluate('window.showpsisi.getState().revision'),before)
        self.page.locator('#extra-pids').fill('0xNOPE')
        self.page.locator('#scan').click()
        self.assertIn('decimal or hexadecimal',self.page.locator('#notice').inner_text())

    def test_refresh_field_error_comparison_state_and_density_slider(self):
        """UI/UX refresh: adjacent field feedback, comparison empty state and
        the density strip as one keyboard-reachable snapshot control."""
        self.analyze()
        # The reason for a rejected value stays next to the control; the footer
        # live region keeps the same message for the status contract.
        self.open_scan_options()
        self.page.locator('#extra-pids').fill('0xNOPE')
        self.page.locator('#scan').click()
        self.assertIn('decimal or hexadecimal',self.page.locator('#notice').inner_text())
        inline=self.page.locator('#extra-pids-error')
        self.assertTrue(inline.is_visible())
        self.assertIn('decimal or hexadecimal',inline.inner_text())
        field=self.page.locator('#extra-pids')
        self.assertEqual(field.get_attribute('aria-invalid'),'true')
        self.assertEqual(field.get_attribute('aria-describedby'),'extra-pids-error')
        self.assertTrue(field.evaluate('(element)=>element===document.activeElement'))
        gap=self.page.evaluate('''() => {
          const field=document.querySelector("#extra-pids").getBoundingClientRect();
          const reason=document.querySelector("#extra-pids-error").getBoundingClientRect();
          return reason.top-field.bottom;
        }''')
        self.assertLess(gap,60,'Field reason must stay beside the field, not only in the footer')
        self.page.locator('#extra-pids').fill('0x30, 100')
        self.assertTrue(self.page.locator('#extra-pids-error').is_hidden())

        # Comparison mode replaces the record list, so its inspector must not
        # ask for a record that is not on screen.
        self.page.locator('[data-tab="Changes"]').click()
        inspector=self.page.locator('#inspector').inner_text()
        self.assertIn('Compare two observed states',inspector)
        self.assertNotIn('Select a service, table, programme or issue',inspector)
        self.page.locator('[data-tab="Services"]').click()

        # One slider entry point, ticks, a painted fill, invalid marks that stay
        # inside their own bin, and column alignment for the tables grid.
        density=self.page.locator('#density')
        self.assertEqual(density.get_attribute('role'),'slider')
        self.assertEqual(density.get_attribute('tabindex'),'0')
        self.assertEqual(self.page.locator('#density .bin').count(),80)
        self.assertEqual(self.page.locator('#density .axis-basis').inner_text(),
                         'Zero-based packet positions · no measured time available')
        self.assertEqual(self.page.locator('#density .arrival-axis span').count(),5)
        fill=self.page.evaluate('''() => {
          const bins=[...document.querySelectorAll("#density .bin")];
          const state=window.showpsisi.getState();
          const index=bins.findIndex((_,i)=>(state.density?.[i]?.count||0)>0);
          const bin=bins[index],style=getComputedStyle(bin);
          return {index,background:style.backgroundColor,opacity:Number(style.opacity),
                  fill:getComputedStyle(document.documentElement).getPropertyValue("--density-fill").trim()};
        }''')
        self.assertGreaterEqual(fill['index'],0)
        self.assertEqual(fill['background'],'rgb(111, 157, 215)','A populated bin must paint the fill token')
        self.assertGreater(fill['opacity'],0.2)
        self.assertEqual(fill['fill'],'#6f9dd7')
        containment=self.page.evaluate('''() => [...document.querySelectorAll(".bin-invalid")].map((bar)=>{
          const parent=bar.parentElement.getBoundingClientRect(),box=bar.getBoundingClientRect();
          return {parentWidth:parent.width,width:box.width,left:box.left,right:box.right,
                  parentLeft:parent.left,parentRight:parent.right,height:box.height};
        })''')
        self.assertTrue(containment,'Expected at least one bin to show its invalid share')
        for bar in containment:
            self.assertGreaterEqual(bar['left'],bar['parentLeft']-0.5,'Invalid mark escaped its bin')
            self.assertLessEqual(bar['right'],bar['parentRight']+0.5,'Invalid mark escaped its bin')
            self.assertLessEqual(bar['width'],bar['parentWidth']+0.5,'Invalid mark spans the whole strip')
            self.assertGreaterEqual(bar['height'],3)

        # Clicking a bin moves the snapshot; repeated keys must each advance,
        # End must reach the declared maximum and focus must survive the
        # re-render each query causes.
        box=self.page.locator('#density .bin').nth(40).bounding_box()
        self.page.mouse.click(box['x']+box['width']/2,box['y']+box['height']/2)
        self.page.wait_for_function('() => window.showpsisi.getState().selected_packet !== null')
        packets=self.page.evaluate('window.showpsisi.getState().packets')
        steps=[self.page.evaluate('window.showpsisi.getState().selected_packet')]
        self.page.locator('#density').focus()
        for _ in range(3):
            self.page.keyboard.press('ArrowRight')
            self.page.wait_for_function('(previous) => window.showpsisi.getState().selected_packet > previous',arg=steps[-1],timeout=8000)
            steps.append(self.page.evaluate('window.showpsisi.getState().selected_packet'))
        self.assertEqual(len(set(steps)),len(steps),steps)
        self.assertEqual(steps,sorted(steps),steps)
        self.assertEqual(self.page.evaluate('document.activeElement.id'),'density','Slider lost focus after re-render')
        self.page.keyboard.press('End')
        self.page.wait_for_function('(max) => window.showpsisi.getState().selected_packet === max',arg=packets-1,timeout=8000)
        self.assertEqual(self.page.evaluate('window.showpsisi.getState().selected_packet'),packets-1)
        self.page.wait_for_function('() => window.showpsisi.getUiState().settled === true',timeout=8000)
        self.page.keyboard.press('Home')
        self.page.wait_for_function('() => window.showpsisi.getState().selected_packet === 0',timeout=8000)
        self.page.wait_for_function('() => window.showpsisi.getUiState().settled === true',timeout=8000)

        self.page.locator('[data-tab="Tables"]').click()
        # The latest workbench presents logical table cards, then expandable
        # section rows; the obsolete flat-table column header no longer applies.
        self.assertGreater(self.page.locator('.table-branch').count(), 0)
        card = self.page.locator('.table-branch').first
        card.locator('summary').first.click()
        self.assertTrue(card.locator('[role="listbox"]').is_visible())
        self.assertGreater(card.locator('.record.tables .table-kind').count(), 0)

    def test_new_protocol_tables_without_service_projection(self):
        self.open_scan_options()
        manifest=json.loads((ROOT/'tests/fixtures/tsduck345/manifest.json').read_text(encoding='utf-8'))
        cases=(('ATSC_AEIT','AEIT','Aggregate Event Information Table',None),
               ('DSMCC_DDB','DSMCC_download_data_message','DSM-CC Download Data Message',None),
               ('DTMB_DRM_PMT','PMT','Program Map Table',None),
               ('DSMCC_DII','DSMCC_user_to_network_message','DSM-CC User-to-Network Message','auto'))
        for name,xml_name,explanation,override in cases:
            with self.subTest(fixture=name):
                fixture=manifest['fixtures'][name]
                standard=override or fixture['standard']
                pid=fixture['pid'];raw=bytes.fromhex(fixture['hex'])
                packets=[]
                for repeat in range(3):
                    remainder=raw;first=True;cc=len(packets)&15
                    while remainder:
                        size=183 if first else 184
                        payload,remainder=remainder[:size],remainder[size:]
                        packets.append(bytes([0x47,(pid>>8)|(0x40 if first else 0),pid&255,0x10|cc])+
                                       (b'\0' if first else b'')+payload+b'\xff'*(size-len(payload)))
                        first=False;cc=(cc+1)&15
                source=self.output/(name+'.ts');source.write_bytes(b''.join(packets))
                self.page.locator('[data-tab="Services"]').click()
                self.page.locator('#standards').select_option(standard)
                self.page.locator('#extra-pids').fill(str(pid))
                self.analyze(source)
                state=self.page.evaluate('window.showpsisi.getState()')
                self.assertEqual(state['standards_context'],standard)
                self.assertEqual(state['services'],[])
                self.assertTrue(state['tables'])
                self.assertEqual(self.page.locator('#tabs [aria-selected="true"]').inner_text(),'Services')
                self.assertIn('Open Tables for native signalling fields',self.page.locator('#list').inner_text())
                self.page.wait_for_function('name => window.showpsisi.getDetail().native_table?.name === name',arg=xml_name)
                detail=self.page.evaluate('window.showpsisi.getDetail()')
                self.assertIn(explanation,self.page.locator('.inspector-heading h2').get_attribute('title'))
                if name == 'DSMCC_DII':
                    self.assertTrue(detail['native_xml_guarded'])
                    if self.page.locator('#inspector-warning-toggle').get_attribute('aria-expanded') == 'false':
                        self.page.locator('#inspector-warning-toggle').click()
                    warnings=self.page.locator('#native-decode-warnings')
                    self.assertIn('namespace is not established',warnings.inner_text())
                    self.assertIn('Original wire bytes remain authoritative',warnings.inner_text())
                    xml_button=self.page.locator('[data-view="xml"]')
                    self.assertEqual(xml_button.inner_text(),'Guarded SDK XML')
                    xml_button.click()
                    self.assertIn('<generic_descriptor',self.page.locator('.evidence').inner_text())
                    self.assertEqual(self.page.locator('.evidence').get_attribute('aria-label'),'Guarded SDK XML')
                    self.page.locator('[data-view="hex"]').click()
                    self.assertIn(' '.join(fixture['hex'][i:i+2].upper() for i in range(0,32,2)),self.page.locator('.evidence').inner_text())
                    self.assertTrue(warnings.is_visible())
                    self.page.locator('[data-view="tree"]').click()
                for target in ('EPG','Services'):
                    self.page.locator('[data-tab="'+target+'"]').click()
                    self.assertIn('an empty projection does not mean decoding failed',self.page.locator('#list').inner_text())
                    self.assertEqual(self.page.evaluate('window.showpsisi.getDetail().id'),detail['id'])
                self.page.locator('[data-tab="Tables"]').click()
                label={'DSMCC_download_data_message':'DSM-CC Data','DSMCC_user_to_network_message':'DSM-CC U-N'}.get(xml_name,xml_name)
                self.assertIn(label,self.page.locator('.inspector-heading h2').inner_text())
                self.assertIn(label,self.page.locator('#list .table-kind').first.inner_text())
                self.assertIn(explanation,self.page.locator('#list .table-kind').first.get_attribute('title'))
                if label != xml_name:
                    self.assertIn(xml_name,self.page.locator('#list .table-kind').first.get_attribute('title'))
                    self.assertIn(xml_name,self.page.locator('.inspector-heading h2').get_attribute('title'))
                self.assertEqual(self.page.locator('[data-filter="'+xml_name+'"] .family-label').inner_text(),label)
                self.page.evaluate('id => window.showpsisi.snapshot(-1,id)',detail['id'])
                self.page.wait_for_function('id => window.showpsisi.getDetail().id === id',arg=detail['id'])
                self.assertEqual(self.page.locator('#tabs [aria-selected="true"]').inner_text(),'Tables')
                self.assertEqual(self.page.evaluate('window.showpsisi.getDetail().raw_hex'),fixture['hex'].upper())
                self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(),hashlib.sha256(b''.join(packets)).hexdigest())
                if name == 'DSMCC_DII':
                    self.page.locator('#tree-search').fill('module')
                    self.assertIn('module_id',self.page.locator('#tree-area').inner_text())
                    self.assertIn('generic_descriptor',self.page.locator('#tree-area').inner_text())
                    self.page.screenshot(path=str(self.artifacts/'tsduck345-dsmcc-guarded-inspector.png'),full_page=True)

    def test_titlebar_controls_fit_and_input_label_remains_readable(self):
        self.analyze()
        p=self.page
        # DejaVu Sans reproduces the 527px title bar from Linux CI at a
        # 520px viewport. The default font can hide the selector label while
        # still passing a page-overflow check, so verify intrinsic width too.
        for font in ('system-ui','DejaVu Sans, sans-serif'):
            p.locator('.titlebar').evaluate('(element,font)=>element.style.fontFamily=font',font)
            for theme in ('dark','light'):
                if p.locator('html').get_attribute('data-theme')!=theme:
                    p.locator('#theme-toggle').click()
                for kind in ('ts','dvbi'):
                    p.locator('#input-kind').select_option(kind)
                    self.assertEqual(p.locator('#app').get_attribute('data-input-kind'),kind)
                    for width in (520,521,760,761,900,1100,1440):
                        with self.subTest(font=font,theme=theme,kind=kind,width=width):
                            p.set_viewport_size({'width':width,'height':1000})
                            self.assertLessEqual(p.evaluate('document.documentElement.scrollWidth'),width)
                            geometry=p.locator('.titlebar').evaluate('''header=>{
                              const bounds=header.getBoundingClientRect();
                              const controls=[...header.querySelectorAll('button,select')]
                                .filter(e=>e.getClientRects().length).map(e=>{
                                  const r=e.getBoundingClientRect();
                                  return {id:e.id,left:r.left,right:r.right,top:r.top,bottom:r.bottom,
                                    reachable:e.contains(document.elementFromPoint(r.x+r.width/2,r.y+r.height/2))};
                                });
                              const select=header.querySelector('#input-kind'),natural=select.cloneNode(true);
                              natural.removeAttribute('id');
                              natural.style.cssText='position:fixed;visibility:hidden;width:max-content;max-width:none';
                              natural.style.font=getComputedStyle(select).font;
                              document.body.append(natural);
                              const naturalWidth=natural.getBoundingClientRect().width;natural.remove();
                              return {bounds:bounds.toJSON(),controls,naturalWidth,
                                selectWidth:select.getBoundingClientRect().width};
                            }''')
                            self.assertGreaterEqual(geometry['selectWidth'],geometry['naturalWidth']-1,geometry)
                            for control in geometry['controls']:
                                self.assertGreaterEqual(control['left'],0,control)
                                self.assertLessEqual(control['right'],width,control)
                                self.assertGreaterEqual(control['top'],geometry['bounds']['top'],control)
                                self.assertLessEqual(control['bottom'],geometry['bounds']['bottom'],control)
                                self.assertTrue(control['reachable'],control)
                            if width==520:
                                p.screenshot(path=str(self.artifacts/f'titlebar-{kind}-{theme}-{font.split(",")[0]}.png'),full_page=True)
        p.locator('#input-kind').select_option('ts')
        p.set_viewport_size({'width':520,'height':1000})
        p.locator('#reset-layout').click()
        self.assertIsNone(p.evaluate('localStorage.getItem("showpsisi.workbench.layout.v1")'))

    def test_references_and_responsive_tree(self):
        self.page.locator('#standards').select_option('dvb')
        self.analyze()
        self.page.wait_for_function('() => window.showpsisi.getDetail().name === "SDT"')
        self.page.locator('[data-view="references"]').click()
        links=self.page.locator('[data-reference]')
        self.assertGreater(links.count(),0,'DVB SDT should have mapped standards references')
        for link in links.all():
            url=link.get_attribute('href')
            from urllib.parse import urlsplit
            parsed=urlsplit(url)
            self.assertEqual(parsed.scheme,'https')
            self.assertTrue(parsed.hostname)
            self.assertIsNone(parsed.username)
            self.assertIn('noopener',link.get_attribute('rel'))
        # Inspect URLs only. Do not click or open an external site.
        self.page.screenshot(path=str(self.artifacts/'references.png'),full_page=True)
        self.page.locator('[data-view="tree"]').click()
        for width in (1100,900,520):
            self.page.set_viewport_size({'width':width,'height':1000})
            self.assertLessEqual(self.page.evaluate('document.documentElement.scrollWidth'),width+1,'Unexpected horizontal viewport overflow')
            self.page.locator('#tree-search').fill('descriptor')
            self.assertIn('descriptor',self.page.locator('#tree-area').inner_text().lower())
            oversized=self.page.locator('#tree-area .node-label').evaluate_all('(elements)=>elements.filter(e=>e.getBoundingClientRect().width>e.closest("#tree-area").clientWidth).map(e=>e.textContent)')
            self.assertEqual(oversized,[],'Descriptor labels exceed inspector width')
            self.page.screenshot(path=str(self.artifacts/('responsive-'+str(width)+'.png')),full_page=True)
        self.page.set_viewport_size({'width':1440,'height':1000})
        self.page.locator('#tree-search').fill('')

    def test_reference_failure_and_manual_clipboard_fallback(self):
        # Exercise native-command UI errors against the real browser transport's
        # explicit unsupported-command response. This runtime-label override is
        # fault injection, not a claim of native browser-launch verification.
        def native_label(route):
            if route.request.post_data_json.get('command')=='environment':
                response=route.fetch()
                value=response.json();value['runtime']='native-command-failure-test'
                route.fulfill(response=response,json=value)
            else:
                route.continue_()
        self.page.add_init_script("""
          let transport;
          Object.defineProperty(window,'__TAURI__',{configurable:true,get:()=>transport,set:value=>{
            transport=value;
            const listen=value.event.listen;
            value.event.listen=(name,callback)=>name==='core-close-blocked'
              ? Promise.resolve(()=>{}) : listen(name,callback);
          }});
        """)
        self.page.route('**/__bridge/invoke',native_label)
        self.page.reload()
        self.page.wait_for_function('() => window.showpsisi && document.querySelector("#source").value.length > 0')
        self.page.locator('#standards').select_option('dvb')
        self.analyze()
        self.page.wait_for_function('() => window.showpsisi.getDetail().name === "SDT"')
        self.page.locator('[data-view="references"]').click()
        reference=self.page.locator('.reference').first
        field=reference.locator('.reference-url')
        url=reference.locator('[data-reference]').get_attribute('href')
        page_count=len(self.page.context.pages)
        reference.locator('[data-reference]').click()
        self.page.wait_for_function('() => document.querySelector(".reference-status").textContent.includes("Could not open reference")')
        self.assertIn('Unsupported bridge command',reference.locator('.reference-status').inner_text())
        self.assertEqual(len(self.page.context.pages),page_count)
        self.assertIsNone(reference.locator('[data-reference]').get_attribute('aria-busy'))
        self.page.evaluate('''() => {
          window.actualTestClipboard = navigator.clipboard;
          Object.defineProperty(navigator,"clipboard",{configurable:true,value:{writeText:async()=>{throw new DOMException("Clipboard permission unavailable","NotAllowedError")}}});
        }''')
        reference.locator('[data-copy-reference]').click()
        self.page.wait_for_function('() => document.querySelector(".reference-status").textContent.includes("URL is selected")')
        self.assertEqual(field.input_value(),url)
        self.assertTrue(field.evaluate('(element)=>element.readOnly'))
        self.assertEqual(field.evaluate('(element)=>[element.selectionStart,element.selectionEnd]'),[0,len(url)])
        self.assertTrue(field.evaluate('(element)=>element===document.activeElement'))
        self.assertFalse(reference.locator('[data-copy-reference]').is_disabled())
        self.page.screenshot(path=str(self.artifacts/'reference-manual-copy.png'),full_page=True)
        # The next Copy succeeds using Chromium's actual clipboard API. No
        # external URL is opened, and the old failure status must disappear.
        self.page.context.grant_permissions(['clipboard-read','clipboard-write'])
        self.page.evaluate('Object.defineProperty(navigator,"clipboard",{configurable:true,value:window.actualTestClipboard})')
        reference.locator('[data-copy-reference]').click()
        self.page.wait_for_function('() => document.querySelector(".reference-status").textContent === "Reference URL copied"')
        self.assertEqual(self.page.evaluate('navigator.clipboard.readText()'),url)
        self.assertFalse(reference.locator('.reference-status').evaluate('(element)=>element.classList.contains("bad")'))
        self.assertFalse(self.page.locator('#notice').evaluate('(element)=>element.classList.contains("error")'))
        self.page.locator('[data-view="tree"]').click()
        self.assertGreater(self.page.locator('#tree-area').count(),0)
        self.page.locator('#about').click()
        self.page.locator('[data-project-link]').last.click()
        self.page.wait_for_function('() => document.querySelector("#about-feedback").textContent.includes("Copy this address")')
        self.assertIn('https://github.com/znbsf/ShowPsiSi/releases',self.page.locator('#about-feedback').inner_text())
        self.assertEqual(len(self.page.context.pages),page_count)
        self.page.locator('#close-about').click()

    def test_inspector_summary_disclosures_persist_and_reset(self):
        self.page.set_viewport_size({'width':1440,'height':900})
        self.analyze()
        p=self.page
        p.wait_for_function('() => window.showpsisi.getDetail().name === "SDT"')
        toggles=['identity-toggle','crc-toggle','arrival-toggle','section-group-toggle','scope-details-toggle']
        for element in toggles:
            self.assertEqual(p.locator('#'+element).get_attribute('aria-expanded'),'false')
        self.assertGreaterEqual(p.locator('#tree-area').bounding_box()['height'],p.locator('#inspector').bounding_box()['height']*0.65)
        # Space/Enter operate real buttons without replacing the focused control.
        p.locator('#identity-toggle').focus();p.keyboard.press('Space')
        self.assertTrue(p.locator('.identity-line').is_visible())
        self.assertEqual(p.evaluate('document.activeElement.id'),'identity-toggle')
        p.locator('#crc-toggle').focus();p.keyboard.press('Enter')
        for element in toggles[2:]:
            p.locator('#'+element).click()
        if p.locator('#inspector-warning-toggle').count():
            p.locator('#inspector-warning-toggle').click()
            self.assertTrue(p.locator('#native-decode-warnings').is_visible())
        expected=p.evaluate('JSON.parse(localStorage.getItem("showpsisi.workbench.layout.v1")).inspectorDetails')
        self.assertTrue(all(expected[key] for key in ('identity','crc','arrival','sections','scope')))
        p.locator('[data-view="hex"]').click()
        p.locator('[data-view="tree"]').click()
        for element in toggles:
            self.assertEqual(p.locator('#'+element).get_attribute('aria-expanded'),'true')
        p.reload()
        p.wait_for_function('() => window.showpsisi && document.querySelector("#source").value.length > 0')
        self.analyze()
        p.wait_for_function('() => window.showpsisi.getDetail().name === "SDT"')
        for element in toggles:
            self.assertEqual(p.locator('#'+element).get_attribute('aria-expanded'),'true')
        p.locator('#reset-layout').click()
        for element in toggles:
            self.assertEqual(p.locator('#'+element).get_attribute('aria-expanded'),'false')
        self.assertFalse(p.locator('#inspector-details').is_visible())
        self.assertIsNone(p.evaluate('localStorage.getItem("showpsisi.workbench.layout.v1")'))

    def test_layout_persists_clamps_and_resets(self):
        self.analyze()
        self.page.wait_for_function('() => window.showpsisi.getDetail().name === "SDT"')
        left=self.page.locator('#split-left')
        right=self.page.locator('#split-right')
        self.assertEqual(left.get_attribute('aria-valuenow'),'178')
        for handle in (left,right):
            width=handle.get_attribute('aria-valuenow')
            handle.focus();handle.press('Alt+ArrowLeft');handle.press('Alt+ArrowRight')
            self.assertEqual(handle.get_attribute('aria-valuenow'),width,'Alt+arrows navigate; plain arrows resize the focused divider')
        left.focus();left.press('ArrowRight')
        self.assertEqual(left.get_attribute('aria-valuenow'),'194')
        box=right.bounding_box()
        self.page.mouse.move(box['x']+2,box['y']+40)
        self.page.mouse.down();self.page.mouse.move(box['x']-78,box['y']+40);self.page.mouse.up()
        self.assertEqual(right.get_attribute('aria-valuenow'),'600')
        stored=self.page.evaluate('JSON.parse(localStorage.getItem("showpsisi.workbench.layout.v1"))')
        self.assertEqual(stored,{'version':1,'widths':{'explorer':194,'inspector':600}})
        self.page.reload()
        self.page.wait_for_function('() => window.showpsisi && document.querySelector("#source").value.length > 0')
        self.assertEqual(left.get_attribute('aria-valuenow'),'194')
        self.assertEqual(right.get_attribute('aria-valuenow'),'600')
        for width in (900,761,520,1100):
            self.page.set_viewport_size({'width':width,'height':1000})
            self.page.wait_for_timeout(50)
            self.assertLessEqual(self.page.evaluate('document.documentElement.scrollWidth'),width+1)
            if width>760:
                self.assertGreaterEqual(self.page.locator('#panes .center').bounding_box()['width'],220)
                self.assertGreaterEqual(self.page.locator('#inspector').bounding_box()['width'],300)
        self.page.set_viewport_size({'width':1440,'height':1000})
        self.page.wait_for_function('() => document.querySelector("#split-right").getAttribute("aria-valuenow") === "600"')
        right.focus();right.press('Home')
        self.assertEqual(right.get_attribute('aria-valuenow'),'300')
        right.press('End')
        self.assertLessEqual(int(right.get_attribute('aria-valuenow')),780)
        self.page.locator('#reset-layout').click()
        self.assertEqual(left.get_attribute('aria-valuenow'),'178')
        self.assertEqual(right.get_attribute('aria-valuenow'),'520')
        self.assertIsNone(self.page.evaluate('localStorage.getItem("showpsisi.workbench.layout.v1")'))
        self.assertFalse(self.page.locator('body').evaluate('(element)=>element.classList.contains("resizing-panes")'))

    def test_layout_invalid_and_unavailable_storage_remains_usable(self):
        for raw in ('{broken', '{"version":1,"widths":{"inspector":"wide"}}', '{"version":99,"widths":{"explorer":240}}'):
            self.page.evaluate('raw=>localStorage.setItem("showpsisi.workbench.layout.v1",raw)',raw)
            self.page.reload()
            self.page.wait_for_function('() => window.showpsisi && document.querySelector("#source").value.length > 0')
            self.assertEqual(self.page.locator('#split-left').get_attribute('aria-valuenow'),'178')
            self.assertEqual(self.page.locator('#split-right').get_attribute('aria-valuenow'),'520')
            self.assertIn('defaults restored',self.page.locator('#layout-status').inner_text())
        self.page.evaluate('localStorage.setItem("showpsisi.workbench.layout.v1",JSON.stringify({version:1,widths:{explorer:-1000,inspector:100000}}))')
        self.page.reload()
        self.page.wait_for_function('() => window.showpsisi && document.querySelector("#source").value.length > 0')
        self.assertEqual(self.page.locator('#split-left').get_attribute('aria-valuenow'),'140')
        self.assertEqual(self.page.locator('#split-right').get_attribute('aria-valuenow'),'780')
        self.page.add_init_script('Object.defineProperty(window,"localStorage",{get(){throw new DOMException("Blocked by test policy","SecurityError")}})')
        self.page.reload()
        self.page.wait_for_function('() => window.showpsisi && document.querySelector("#source").value.length > 0')
        self.analyze()
        self.page.locator('#split-left').focus();self.page.keyboard.press('ArrowRight')
        self.assertEqual(self.page.locator('#split-left').get_attribute('aria-valuenow'),'194')
        self.assertIn('session only',self.page.locator('#layout-status').inner_text())
        self.page.locator('#split-left').press('ArrowRight')
        self.assertIn('×2',self.page.locator('#warning-message').inner_text())
        self.page.locator('#reset-layout').click()
        self.assertEqual(self.page.locator('#split-left').get_attribute('aria-valuenow'),'178')
        self.assertEqual(len(self.page.evaluate('window.showpsisi.getState().services')),6)
        self.assertTrue(self.page.locator('#status-warning').is_visible())
        self.page.locator('#dismiss-warning').click()
        self.assertFalse(self.page.locator('#status-warning').is_visible())

    def test_comparison_history_evidence_and_restored_snapshot(self):
        self.analyze()
        self.page.wait_for_function('() => window.showpsisi.getDetail().name === "SDT"')
        history=self.page.evaluate('window.showpsisi.getState().history')
        self.page.evaluate('entry=>window.showpsisi.snapshot(entry.last_packet,entry.id)',history[1])
        self.page.wait_for_function('packet=>window.showpsisi.getDetail().native_table_at_packet === packet',arg=history[1]['last_packet'])
        old_state=self.page.evaluate('window.showpsisi.getState()')
        old_detail=self.page.evaluate('window.showpsisi.getDetail()')
        self.page.locator('#compare-snapshots').click()
        self.page.locator('[data-preset="from"]').select_option(str(history[0]['last_packet']))
        self.page.locator('[data-preset="to"]').select_option(str(history[2]['last_packet']))
        self.page.locator('#run-comparison').click()
        self.page.wait_for_function('() => window.showpsisi.getComparison() !== null')
        result=self.page.evaluate('window.showpsisi.getComparison()')
        self.assertGreater(result['summary']['tables']['changed'],0)
        self.assertGreater(result['summary']['services']['changed'],0)
        self.assertIn('Sports UHD',self.page.locator('#list').inner_text())
        self.assertIn('Sports HD',self.page.locator('#list').inner_text())
        # Every evidence request uses the selected side cutoff, never the normal
        # workspace cutoff or a later sibling section.
        service_index=next(i for i,c in enumerate(result['changes']) if c['kind']=='services')
        failed=[]
        def interrupt_inspect(route):
            body=route.request.post_data_json
            if not failed and body.get('command')=='request' and body.get('args',{}).get('message',{}).get('method')=='inspect':
                failed.append(True)
                route.abort('failed')
            else:
                route.continue_()
        self.page.route('**/__bridge/invoke',interrupt_inspect)
        self.page.locator('[data-comparison-evidence="'+str(service_index)+':A:0"]').click()
        self.page.locator('#retry-inspect').wait_for()
        self.page.unroute('**/__bridge/invoke',interrupt_inspect)
        self.assertIn('Comparison A',self.page.locator('#inspector').inner_text())
        self.page.locator('#retry-inspect').click()
        self.page.wait_for_function('packet=>window.showpsisi.getDetail().native_table_at_packet === packet',arg=result['from_packet'])
        self.assertEqual(len(failed),1)
        self.assertNotIn('Failed to fetch',self.page.locator('#notice').inner_text())
        self.assertFalse(self.page.locator('#notice').evaluate('(element)=>element.classList.contains("error")'))
        for side,packet in [('A',result['from_packet']),('B',result['to_packet'])]:
            evidence=self.page.locator('[data-comparison-evidence="'+str(service_index)+':'+side+':0"]')
            evidence.click()
            self.page.wait_for_function('packet=>window.showpsisi.getDetail().native_table_at_packet === packet',arg=packet)
            self.assertIn('Comparison '+side,self.page.locator('#inspector').inner_text())
            self.assertEqual(self.page.evaluate('window.showpsisi.getState().selected_packet'),old_state['selected_packet'])
            self.assertTrue(self.page.locator('#edit').is_disabled())
            self.assertTrue(evidence.evaluate('(element)=>element===document.activeElement'))
        self.page.locator("#list").evaluate("element=>element.scrollTop=0")
        self.page.screenshot(path=str(self.artifacts/'snapshot-comparison.png'),full_page=True)
        self.page.locator('[data-tab="Services"]').click()
        self.assertEqual(self.page.evaluate('window.showpsisi.getState().selected_packet'),old_state['selected_packet'])
        self.assertEqual(self.page.evaluate('window.showpsisi.getDetail()'),old_detail)
        self.assertNotIn('Comparison B',self.page.locator('#inspector').inner_text())
        self.page.locator('[data-tab="Changes"]').click()
        self.page.locator('#swap-comparison').click()
        self.assertIsNone(self.page.evaluate('window.showpsisi.getComparison()'))
        self.page.locator('#run-comparison').click()
        self.page.wait_for_function('() => window.showpsisi.getComparison() !== null')
        reverse=self.page.evaluate('window.showpsisi.getComparison()')
        self.assertEqual(reverse['from_packet'],result['to_packet'])
        self.assertEqual(reverse['to_packet'],result['from_packet'])
        self.page.locator('#compare-kind').select_option('services')
        self.page.locator('#run-comparison').click()
        self.page.wait_for_function('() => window.showpsisi.getComparison() !== null')
        self.assertTrue(all(c['kind']=='services' for c in self.page.evaluate('window.showpsisi.getComparison().changes')))
        self.page.locator('#compare-from').fill('-1')
        self.page.locator('#run-comparison').click()
        self.assertIn('whole packet number',self.page.locator('#list').inner_text())
        self.assertTrue(self.page.locator('#compare-from').evaluate('(element)=>element===document.activeElement'))
        self.page.locator('#compare-from').fill(str(result['to_packet']))
        self.page.locator('#compare-to').fill(str(result['to_packet']))
        self.page.locator('#run-comparison').click()
        self.page.wait_for_function('() => window.showpsisi.getComparison() !== null')
        self.assertIn('No observed changes',self.page.locator('#list').inner_text())
        self.page.keyboard.press('Control+k')
        self.assertTrue(self.page.locator('#search').evaluate('(element)=>element===document.activeElement'))
        self.assertEqual(self.page.evaluate('window.showpsisi.getDetail()'),old_detail)

    def test_comparison_pagination_and_empty_sides(self):
        from make_fixture import section,descriptor,word
        packets=[bytes([0x47,0x1f,0xff,0x10])+b'\xff'*184]
        for index in range(120):
            name=('Service '+str(index)).encode()
            desc=descriptor(0x48,b'\x01\x00'+bytes([len(name)])+name)
            raw=section(0x42,index+1,1,word(2)+b'\xff'+word(100)+b'\xff'+word(0x8000+len(desc))+desc)
            packets.append(bytes([0x47,0x40,0x11,0x10+(index%16),0])+raw+b'\xff'*(183-len(raw)))
        fixture=self.output/'many-changes.ts'
        fixture.write_bytes(b''.join(packets))
        self.analyze(fixture)
        self.page.locator('#compare-snapshots').click()
        self.page.locator('#compare-from').fill('0')
        self.page.locator('#compare-to').fill('120')
        self.page.locator('#run-comparison').click()
        self.page.wait_for_function('() => window.showpsisi.getComparison() !== null')
        result=self.page.evaluate('window.showpsisi.getComparison()')
        self.assertEqual(result['total_changes'],240)
        self.assertEqual(len(result['changes']),100)
        self.assertTrue(all(change['before'] is None for change in result['changes']))
        self.assertIn('No observed record',self.page.locator('#list').inner_text())
        self.assertTrue(self.page.locator('#prev').is_disabled())
        self.page.locator('[data-comparison-evidence]').first.click()
        self.page.wait_for_function('() => window.showpsisi.getDetail().native_table_at_packet === 120')
        self.assertEqual(self.page.locator('[data-comparison-evidence][aria-pressed="true"]').count(),1)
        self.page.locator('#next').click()
        self.page.wait_for_function('() => window.showpsisi.getComparison()?.offset === 100')
        self.assertIn('101–200 of 240',self.page.locator('#page-label').inner_text())
        self.assertEqual(self.page.locator('[data-comparison-evidence][aria-pressed="true"]').count(),0,'Pagination must not select an unrelated evidence row at the same local index')
        self.page.locator('#next').click()
        self.page.wait_for_function('() => window.showpsisi.getComparison()?.offset === 200')
        self.assertTrue(self.page.locator('#next').is_disabled())
        self.assertEqual(self.page.locator('.comparison-change').count(),40)
        self.page.locator('#prev').click()
        self.page.wait_for_function('() => window.showpsisi.getComparison()?.offset === 100')
        self.page.locator('#compare-kind').select_option('services')
        self.page.locator('#run-comparison').click()
        self.page.wait_for_function('() => window.showpsisi.getComparison()?.kind === "services"')
        self.assertEqual(self.page.evaluate('window.showpsisi.getComparison().offset'),0)
        for width in (900,761,520):
            self.page.set_viewport_size({'width':width,'height':1000})
            self.assertLessEqual(self.page.evaluate('document.documentElement.scrollWidth'),width+1)
            self.assertTrue(self.page.locator('#run-comparison').is_visible())
        self.page.set_viewport_size({'width':1440,'height':1000})

    def test_comparison_ignores_stale_results_and_settles_backend_exit(self):
        import signal
        if not hasattr(signal,'SIGSTOP'):
            self.skipTest('Deterministic in-flight process pause requires POSIX SIGSTOP')
        self.analyze()
        self.page.wait_for_function('() => window.showpsisi.getDetail().name === "SDT"')
        old_detail=self.page.evaluate('window.showpsisi.getDetail()')
        self.page.locator('#compare-snapshots').click()
        self.bridge.proc.send_signal(signal.SIGSTOP)
        self.page.locator('#run-comparison').click()
        self.assertTrue(self.page.locator('#run-comparison').is_disabled())
        self.page.locator('#compare-from').fill('0')
        self.bridge.proc.send_signal(signal.SIGCONT)
        self.call('capabilities')  # Native serial reply barrier, not a timed sleep.
        self.assertIsNone(self.page.evaluate('window.showpsisi.getComparison()'))
        self.page.locator('#run-comparison').click()
        self.page.wait_for_function('() => window.showpsisi.getComparison()?.from_packet === 0')
        self.bridge.proc.send_signal(signal.SIGSTOP)
        self.page.locator('#run-comparison').click()
        self.page.locator('[data-tab="Services"]').click()
        self.assertEqual(self.page.evaluate('window.showpsisi.getDetail()'),old_detail)
        self.bridge.proc.send_signal(signal.SIGCONT)
        self.call('capabilities')
        self.assertEqual(self.page.evaluate('window.showpsisi.getDetail()'),old_detail)
        self.page.locator('[data-tab="Changes"]').click()
        self.bridge.proc.send_signal(signal.SIGSTOP)
        self.page.locator('#run-comparison').click()
        self.bridge.proc.kill();self.bridge.proc.wait(timeout=5)
        self.page.wait_for_function('() => document.querySelector("#runtime").textContent.includes("DISCONNECTED")')
        self.assertTrue(self.page.locator('#run-comparison').is_disabled())
        self.assertNotIn('Comparing…',self.page.locator('#run-comparison').inner_text())
        self.assertRegex(self.page.locator('#list').inner_text().lower(),r'stopped|disconnected')
        self.page.locator('[data-tab="Services"]').click()
        self.assertEqual(self.page.evaluate('window.showpsisi.getDetail()'),old_detail)

    def test_bridge_rejects_unauthorized_requests(self):
        request=Request(self.server.url+'/__bridge/invoke',data=b'{"command":"environment"}',headers={'Content-Type':'application/json'})
        with self.assertRaises(HTTPError) as error:urlopen(request)
        self.assertEqual(error.exception.code,403)
        request=Request(self.server.url+'/',headers={'Host':'untrusted.example'})
        with self.assertRaises(HTTPError) as error:urlopen(request)
        self.assertEqual(error.exception.code,403)
        with urlopen(self.server.url+'/app.js') as response:
            self.assertEqual(response.read(),(ROOT/'ui/tauri/web/app.js').read_bytes())

if __name__=='__main__':unittest.main(verbosity=2)
