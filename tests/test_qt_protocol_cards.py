"""Actual compiled Qt protocol metadata, separate from Windows/native acceptance."""
import tempfile
import unittest
from pathlib import Path
import test_qt_ui as qt
from protocol_ui_fixture import protocol_ui_fixture


class QtProtocolCardTests(unittest.TestCase):
    def test_real_metadata_paging_in_both_themes(self):
        for theme in ('dark', 'light'):
            with self.subTest(theme=theme), tempfile.TemporaryDirectory() as td:
                path=Path(td)/'cards.ts';raw=protocol_ui_fixture();path.write_bytes(raw)
                helper=qt.NativeQtTests();helper._testMethodName='protocol-cards-'+theme
                report=helper.run_script('protocol-cards',td,timeout=30,overrides={
                    'SHOWPSISI_SAMPLE':str(path),'SHOWPSISI_STANDARDS':'dvb','SHOWPSISI_THEME':theme})
                self.assertTrue(all(report['checks'].values()),report)
                self.assertGreater(report['total'],40)
                self.assertEqual(path.read_bytes(),raw)



# Source-navigation tests use the same compiled UI and real core as topology.
import test_qt_topology as topology_qt
import test_nordig as nordig
import test_application_summaries as applications
import test_cable_oob as cable
from make_fixture import section, descriptor, word

class QtProtocolSourceTests(unittest.TestCase):
    application = topology_qt.QtTopologyTests.application
    wait = topology_qt.QtTopologyTests.wait
    action = topology_qt.QtTopologyTests.action

    def test_application_and_nordig_metadata_sources_restore_exact_origin(self):
        pat=section(0,1,0,word(101)+word(0xe100))
        signalling=descriptor(0x6f,word(0x10)+bytes([0xe1]))
        pmt=section(2,101,0,word(0xe201)+word(0xf000)+b'\x05'+word(0xe150)+word(0xf000|len(signalling))+signalling)
        ait=applications.ait([applications.application(identifier=n) for n in range(16)])
        nit=nordig.NorDigTests.nit(nordig.NorDigTests.pds()+descriptor(0x87,nordig.NorDigTests.channel_list()))
        for kind,sections,tid in [('application',[(0,pat),(0x100,pmt),(0x150,ait)],0x74),('nordig',[nit,nordig.NorDigTests.sdt()],0x40)]:
            with self.subTest(kind=kind),self.application(sections=sections) as (directory,ts):
                self.action('history_scope',value=True);state=self.wait(lambda s:s['settled'] and any(r['table_id']==tid for r in s['history']['entries']));target=next(r for r in state['history']['entries'] if r['table_id']==tid)
                self.action('select_record',id=target['id']);self.wait(lambda s:s['settled'] and s['inspection']['id']==target['id'])
                self.action('set_view',value='Metadata');state=self.wait(lambda s:s['inspector']=='Metadata')
                if kind=='application':
                    self.action('protocol_page_control',value='Next');state=self.wait(lambda s:s['protocol']['cards']['offset']==20)
                    self.assertTrue(next(c for c in state['controls'] if c['id']=='protocolNext')['focused'])
                self.action('protocol_scroll',value=120);state=self.wait(lambda s:s['protocol']['scroll']>0)
                sources=state['protocol']['sources'];self.assertTrue(any(sources));origin=state['inspection'];offset=state['protocol']['cards']['offset']
                card=next(i for i,refs in enumerate(sources) if refs)
                for index,source in enumerate(sources[card][:3]):
                    self.assertTrue(source['available'])
                    self.action('protocol_source',card=card,index=index)
                    opened=self.wait(lambda s:s['settled'] and bool(s['protocol']['active_evidence']))
                    ref=source['ref'];self.assertEqual(opened['inspection']['id'],ref['section_id'])
                    self.assertEqual(opened['inspection']['revision'],ref['analysis_revision']);self.assertEqual(opened['inspection']['cutoff'],ref['at_packet'])
                    self.assertEqual(opened['protocol']['resolution']['precision'],'section' if kind=='nordig' else ref['locator']['precision'])
                    self.assertEqual(opened['topology']['selected_node'],state['topology']['selected_node'])
                    self.action('protocol_back');restored=self.wait(lambda s:s['settled'] and s['inspector']=='Metadata' and s['protocol']['cards']['offset']==offset)
                    self.assertEqual(restored['inspection']['id'],origin['id']);self.assertEqual(restored['inspection']['cutoff'],origin['cutoff'])
                    self.assertFalse(restored['protocol']['can_back']);self.assertAlmostEqual(restored['protocol']['scroll'],state['protocol']['scroll'],delta=1)
                    self.assertTrue(next(c for c in restored['controls'] if c['id']==f'protocolSource_{card}_{index}')['focused'])

    def test_nordig_graph_container_sources_are_distinct_and_exact(self):
        lists=nordig.NorDigTests.channel_list(1,entries=((100,7,True),(101,8,True)))+nordig.NorDigTests.channel_list(2,entries=((100,17,True),(101,18,True)))
        nit=nordig.NorDigTests.nit(nordig.NorDigTests.pds()+descriptor(0x87,lists))
        with self.application(sections=[nit,nordig.NorDigTests.sdt()]) as (directory,ts):
            self.action('select_tab',value='Topology');state=self.wait(lambda s:s['settled'] and bool(s['topology']['data'].get('nodes')))
            nodes=[n for n in state['topology']['data']['nodes'] if n['object_type']=='channel_list']
            self.assertEqual(len(nodes),2);seen=set()
            for node in nodes:
                self.action('topology_select',id=node['node_id']);selected=self.wait(lambda s:s['topology']['selected_node']==node['node_id'])
                for index,source in enumerate(selected['topology']['sources']):
                    ref=source['ref']
                    if ref['assertion_key'] not in ('nordig_channel_list','nordig_list_entry') or ref['locator']['container_id'] in seen:continue
                    seen.add(ref['locator']['container_id']);self.action('topology_source',index=index)
                    opened=self.wait(lambda s:s['settled'] and bool(s['topology']['resolution'].get('status')))
                    self.assertEqual(opened['topology']['resolution']['status'],'resolved')
                    self.assertEqual(opened['topology']['resolution']['precision'],'container')
                    self.assertEqual(opened['topology']['resolution']['byte_range'],ref['locator']['byte_range'])
                    self.action('set_view',value='Hex');self.assertTrue(self.wait(lambda s:s['inspector']=='Hex')['inspection']['hex_selection'])
                    self.action('topology_back');self.wait(lambda s:s['topology']['summary'])
            self.assertEqual(len(seen),6)

    def test_simulcast_declaration_exact_field_jumps_and_back_both_themes(self):
        from protocol_ui_fixture import simulcast_ui_parts
        expected = {
            'nordig_private_data_specifier',
            'nordig_replacement_original_network_id',
            'nordig_replacement_transport_stream_id',
            'nordig_replacement_service_id',
            'nordig_replacement_linkage_type',
        }
        for theme in ('dark', 'light'):
            with self.subTest(theme=theme), self.application(sections=simulcast_ui_parts(), theme=theme, compact=True):
                self.action('select_tab', value='Topology')
                state = self.wait(lambda s: s['settled'] and bool(s['topology']['data'].get('nodes')))
                node, = [n for n in state['topology']['data']['nodes']
                         if n['object_type'] == 'simulcast_replacement_reference']
                self.assertEqual(node['resolution_status'], 'resolved')
                self.assertFalse(node['attributes']['receiver_policy_applied'])
                self.action('topology_select', id=node['node_id'])
                state = self.wait(lambda s: s['topology']['selected_node'] == node['node_id'])
                sources = state['topology']['sources']
                seen = set()
                for index, source in enumerate(sources):
                    ref = source['ref']
                    if ref['assertion_key'] not in expected or ref['assertion_key'] in seen:
                        continue
                    seen.add(ref['assertion_key'])
                    self.action('topology_source', index=index)
                    opened = self.wait(lambda s: s['settled'] and bool(s['topology']['resolution'].get('status')))
                    self.assertEqual(opened['inspection']['id'], ref['section_id'])
                    self.assertEqual(opened['inspection']['revision'], ref['analysis_revision'])
                    self.assertEqual(opened['inspection']['cutoff'], ref['at_packet'])
                    self.assertEqual(opened['topology']['resolution']['status'], 'resolved')
                    self.assertEqual(opened['topology']['resolution']['precision'], 'field')
                    self.assertEqual(opened['topology']['resolution']['byte_range'], ref['locator']['byte_range'])
                    self.action('set_view', value='Hex')
                    self.assertTrue(self.wait(lambda s: s['inspector'] == 'Hex')['inspection']['hex_selection'])
                    self.action('topology_back')
                    restored = self.wait(lambda s: s['topology']['summary'])
                    self.assertEqual(restored['topology']['selected_node'], node['node_id'])
                    self.assertEqual(restored['packet'], state['packet'])
                self.assertEqual(seen, expected)

    def test_carriage_card_three_table_sources_restore_origin_both_themes(self):
        from protocol_ui_fixture import carriage_ui_parts
        for theme in ('dark', 'light'):
            with self.subTest(theme=theme), self.application(sections=carriage_ui_parts(), theme=theme, compact=True):
                self.action('history_scope', value=True)
                state = self.wait(lambda s: s['settled'] and any(r['table_id'] == 0x74 for r in s['history']['entries']))
                target = next(r for r in state['history']['entries'] if r['table_id'] == 0x74)
                self.action('select_record', id=target['id'])
                self.wait(lambda s: s['settled'] and s['inspection']['id'] == target['id'])
                self.action('set_view', value='Metadata')
                state = self.wait(lambda s: s['inspector'] == 'Metadata')
                cards = state['protocol']['cards']['cards']
                card = next(i for i, c in enumerate(cards)
                            if c.get('evidence', {}).get('object', {}).get('object_type') == 'application_carriage')
                self.assertIn('application_carriage · resolved', cards[card]['text'])
                self.assertIn('runtime compatibility: not_evaluated', cards[card]['text'])
                sources = state['protocol']['sources'][card]
                self.assertEqual({s['ref']['table_identity']['table_id'] for s in sources}, {0, 2, 0x74})
                origin = state['inspection']
                for index, source in enumerate(sources):
                    ref = source['ref']
                    self.action('protocol_source', card=card, index=index)
                    opened = self.wait(lambda s: s['settled'] and bool(s['protocol']['resolution'].get('status')))
                    self.assertEqual(opened['inspection']['id'], ref['section_id'])
                    self.assertEqual(opened['inspection']['revision'], ref['analysis_revision'])
                    self.assertEqual(opened['inspection']['cutoff'], ref['at_packet'])
                    self.assertEqual(opened['protocol']['resolution']['status'], 'resolved')
                    self.assertEqual(opened['protocol']['resolution']['precision'], ref['locator']['precision'])
                    self.assertEqual(opened['protocol']['resolution']['byte_range'], ref['locator']['byte_range'])
                    self.action('set_view', value='Hex')
                    self.assertTrue(self.wait(lambda s: s['inspector'] == 'Hex')['inspection']['hex_selection'])
                    self.action('protocol_back')
                    restored = self.wait(lambda s: s['settled'] and s['inspector'] == 'Metadata' and not s['protocol']['can_back'])
                    self.assertEqual(restored['inspection']['id'], origin['id'])
                    self.assertEqual(restored['inspection']['cutoff'], origin['cutoff'])
                    self.assertEqual(restored['protocol']['cards']['offset'], state['protocol']['cards']['offset'])
                    self.assertTrue(next(c for c in restored['controls'] if c['id'] == f'protocolSource_{card}_{index}')['focused'])
                # Retain the newly exercised card in the compact visual capture.
                self.action('protocol_scroll', value=100000)
                bottom = self.wait(lambda s: s['protocol']['scroll'] > 0)
                self.action('protocol_scroll', value=max(0, bottom['protocol']['scroll'] - 600))

    def test_j94_explicit_profile_and_short_header_are_visible(self):
        with self.application(profile='j94-system-b',sections=[(0x1ffc,cable.nit())]) as (directory,ts):
            self.action('select_tab',value='Tables');self.action('set_scope',value='section')
            state=self.wait(lambda s:s['settled']);text=' '.join(c.get('text','') for c in state['controls'] if c.get('visible'))
            self.assertIn('version not carried',text);self.assertIn('section number not carried',text);self.assertIn('current/next not carried',text)
            self.assertNotIn('vnull',text);self.assertNotIn('§null',text)

if __name__=='__main__':unittest.main()
