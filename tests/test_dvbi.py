"""Real C++/JSONL/MCP DVB-I import, evidence and hostile-input regressions.

Run with SHOWPSISI_CORE selecting the freshly built native engine. No fake
parser, fixture download, owner-machine path or network service is required.
The local HTTP trap proves that XML references are retained without fetching.
"""
import hashlib
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from core_client import Core, CoreError
from dvbi_fixture import (NAMESPACE, PROFILE, SERVICE_A, SERVICE_B, TYPES_NAMESPACE,
                          document, element, fixture, instance, lcn_table,
                          many_services, service, transport_fixture)


class FetchTrap:
    """An owned loopback listener; any request is a security-test failure."""
    def __enter__(self):
        self.requests = []
        requests = self.requests

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                requests.append(self.path)
                body = b'<Service><UniqueIdentifier>FETCHED-CANARY</UniqueIdentifier></Service>'
                self.send_response(200)
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass

        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f'http://127.0.0.1:{self.server.server_port}'
        return self

    def __exit__(self, *args):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)


class DvbiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='showpsisi-dvbi-')
        self.addCleanup(self.tmp.cleanup)
        self.core = Core()
        self.addCleanup(self.core.close)
        self.path = Path(self.tmp.name) / '节目 XML.xml'

    def call(self, method, params=None, timeout=10):
        return self.core.submit(method, params).result(timeout=timeout)

    def import_xml(self, raw=None, **params):
        self.path.write_bytes(fixture() if raw is None else raw)
        imported = self.call('import_dvbi', {'path': str(self.path), 'profile': PROFILE, **params})
        queried = self.query(document_revision=imported['document_revision'])
        self.assertEqual({key: queried[key] for key in imported}, imported)
        return queried

    def query(self, **params):
        return self.call('query_dvbi', params)

    def inspect(self, revision, **params):
        return self.call('inspect_dvbi', {'document_revision': revision, **params})

    def all_nodes(self, revision=None):
        nodes, offset = [], 0
        while True:
            args = {'offset': offset, 'limit': 500}
            if revision is not None:
                args['document_revision'] = revision
            page = self.query(**args)
            nodes.extend(page['nodes'])
            if not page['page']['has_more']:
                self.assertIsNone(page['page']['next_offset'])
                return nodes
            self.assertGreater(page['page']['next_offset'], offset)
            offset = page['page']['next_offset']

    def original(self, revision, chunk_size=65536):
        offset, parts = 0, []
        while True:
            source = self.inspect(revision, source_offset=offset,
                                  source_limit=chunk_size)['original_source']
            self.assertEqual(source['encoding'], 'hex')
            self.assertEqual(source['offset'], offset)
            part = bytes.fromhex(source['data'])
            self.assertEqual(source['length'], len(part))
            self.assertLessEqual(len(part), chunk_size)
            parts.append(part)
            offset += len(part)
            self.assertEqual(source['has_more'], offset < source['total'])
            if not source['has_more']:
                self.assertEqual(source['total'], offset)
                return b''.join(parts)
            self.assertTrue(part, 'source pagination must make forward progress')

    def rejected_without_replacement(self, raw, message=None):
        before = self.query()
        self.path.write_bytes(raw)
        with self.assertRaises(CoreError) as rejected:
            self.call('import_dvbi', {'path': str(self.path), 'profile': PROFILE}, timeout=8)
        if message:
            self.assertRegex(str(rejected.exception), message)
        after = self.query()
        self.assertEqual(after, before, 'failed replacement must retain the complete prior document')
        return rejected.exception

    def assert_locator(self, locator, state):
        self.assertEqual(locator['document_revision'], state['document_revision'])
        self.assertEqual(locator['source_sha256'], state['source']['sha256'])
        self.assertRegex(locator['element_id'], r'^e\d+$')
        self.assertIn(NAMESPACE, locator['path'])
        self.assertIn(locator['precision'], ('element', 'attribute'))
        self.assertGreaterEqual(locator['line'], 1)
        self.assertGreaterEqual(locator['column'], 1)
        self.assertEqual(locator['line_precision'], 'element_start')
        if locator['precision'] == 'attribute':
            self.assertTrue(locator['attribute_name'])
        for forged in ('pid', 'packet', 'packet_offset', 'section_offset', 'crc', 'crc32'):
            self.assertNotIn(forged, locator)

    def test_import_has_independent_metadata_and_never_claims_reception(self):
        raw = fixture()
        state = self.import_xml(raw)
        self.assertEqual(state['status'], 'partial')
        self.assertEqual(state['profile'], PROFILE)
        self.assertEqual(state['namespace'], NAMESPACE)
        self.assertEqual(state['source']['kind'], 'local_dvbi_xml')
        self.assertEqual(Path(state['source']['path']), self.path)
        self.assertEqual(state['source']['bytes'], len(raw))
        self.assertEqual(state['source']['encoding'], 'UTF-8')
        self.assertEqual(state['source']['sha256'].lower(), hashlib.sha256(raw).hexdigest())
        nodes = self.all_nodes(state['document_revision'])
        self.assertEqual(state['counts']['nodes'], len(nodes))
        self.assertGreaterEqual(state['counts']['elements'], len(nodes))
        self.assertGreater(len(nodes), 2)
        self.assertEqual(len({node['node_id'] for node in nodes}), len(nodes))
        for node in nodes:
            self.assertEqual(node['observation_status'], 'announced_only')
            self.assertIsInstance(node['attributes'], dict)
            self.assertTrue(node['object_type'])
            self.assertTrue(node['resolution_status'])
            self.assertIsInstance(node['unresolved_reasons'], list)
            self.assertTrue(node['evidence'])
            if node['parent_id'] is not None:
                self.assertIn(node['parent_id'], {item['node_id'] for item in nodes})
            for locator in node['evidence']:
                self.assert_locator(locator, state)
            for forged in ('pid', 'packet', 'first_packet', 'last_packet', 'crc_errors', 'crc_valid'):
                self.assertNotIn(forged, node)
        self.assertEqual(self.path.read_bytes(), raw)

    def test_namespace_aliases_have_the_same_semantics_and_expanded_paths(self):
        first = self.import_xml(fixture())
        nodes_a = self.all_nodes()
        second = self.import_xml(fixture(prefix='s'))
        nodes_b = self.all_nodes()
        fields = ('object_type', 'identity', 'label', 'attributes', 'observation_status',
                  'resolution_status', 'unresolved_reasons')
        def normalized(value):
            if isinstance(value, list):
                return [normalized(item) for item in value]
            if isinstance(value, dict):
                return {key: normalized(item) for key, item in value.items()
                        if key not in ('evidence', 'qualified_name')}
            return value
        projection = lambda nodes: [normalized({key: node[key] for key in fields}) for node in nodes]
        self.assertEqual(projection(nodes_a), projection(nodes_b))
        self.assertEqual([[r['path'] for r in n['evidence']] for n in nodes_a],
                         [[r['path'] for r in n['evidence']] for n in nodes_b])
        self.assertEqual(second['document_revision'], first['document_revision'] + 1)
        self.assertNotEqual(first['source']['sha256'], second['source']['sha256'])

    def test_wrong_unknown_and_empty_namespace_are_raw_only(self):
        for namespace in ('urn:example.invalid:not-dvbi',
                          'urn:dvb:metadata:servicediscovery:2020',
                          'urn:dvb:metadata:servicediscovery:2099', ''):
            with self.subTest(namespace=namespace):
                raw = fixture(namespace=namespace)
                state = self.import_xml(raw)
                self.assertEqual(state['status'], 'unsupported')
                self.assertEqual(state['namespace'], namespace)
                self.assertEqual(state['counts']['nodes'], 0)
                self.assertEqual(state['nodes'], [])
                self.assertTrue(state['diagnostics'])
                self.assertEqual(self.original(state['document_revision']), raw)

    def test_wrong_root_in_supported_namespace_does_not_masquerade_as_list(self):
        raw = document(service(), root='ServiceListLookalike')
        state = self.import_xml(raw)
        self.assertEqual(state['status'], 'unsupported')
        self.assertEqual(state['nodes'], [])
        self.assertEqual(self.original(state['document_revision']), raw)

    def test_foreign_same_local_names_are_not_projected_as_dvbi_services(self):
        spoof = ('<ext:Service><ext:UniqueIdentifier>urn:foreign:service</ext:UniqueIdentifier>'
                 '<ext:ServiceName>Foreign service</ext:ServiceName></ext:Service>')
        state = self.import_xml(document(service() + spoof))
        self.assertNotIn('urn:foreign:service', [n['identity'].get('service_id') for n in self.all_nodes()])
        self.assertEqual(self.original(state['document_revision']), document(service() + spoof))

    def test_original_bytes_survive_bom_crlf_comments_and_processing_instruction(self):
        raw = (b'\xef\xbb\xbf' + fixture().replace(b'\n', b'\r\n')
               .replace(b'<ServiceList ', b'<?fixture untouched?>\r\n<!-- preserve me -->\r\n<ServiceList '))
        state = self.import_xml(raw)
        self.assertEqual(state['source']['sha256'].lower(), hashlib.sha256(raw).hexdigest())
        self.assertEqual(self.original(state['document_revision'], chunk_size=137), raw)
        self.assertEqual(self.path.read_bytes(), raw)

    def test_unicode_entity_escaping_and_markup_are_plain_text(self):
        name = '新闻 & <script>alert("literal")</script> 🎬 café'
        raw = document(service(name=name))
        state = self.import_xml(raw)
        self.assertIn(name, [node['label'] for node in self.all_nodes()])
        self.assertEqual(self.original(state['document_revision']), raw)
        numeric = raw.replace('新闻'.encode(), b'&#x65B0;&#38395;')
        self.import_xml(numeric)
        self.assertIn(name, [node['label'] for node in self.all_nodes()])

    def test_services_with_equal_names_keep_distinct_identities_and_instances(self):
        self.import_xml()
        nodes = self.all_nodes()
        a = [n for n in nodes if n['object_type'] == 'service' and n['identity']['service_id'] == SERVICE_A]
        b = [n for n in nodes if n['object_type'] == 'service' and n['identity']['service_id'] == SERVICE_B]
        self.assertEqual(len(a), 1)
        self.assertEqual(len(b), 1)
        self.assertEqual(a[0]['label'], b[0]['label'])
        self.assertNotEqual(a[0]['node_id'], b[0]['node_id'])
        children = [n for n in nodes if n['parent_id'] == a[0]['node_id']]
        self.assertGreaterEqual(len(children), 4, 'all alternative instances must remain visible')
        for delivery in ('DVBTDeliveryParameters', 'DVBSDeliveryParameters',
                         'DVBCDeliveryParameters', 'DASHDeliveryParameters'):
            self.assertIn(delivery, json.dumps(nodes, ensure_ascii=False))
        self.assertIn('新闻 & <测试> 🎬', json.dumps(nodes, ensure_ascii=False))

    def test_duplicate_service_identity_has_explicit_conflict_and_keeps_both(self):
        state = self.import_xml(document(service(name='First') + service(name='Second')))
        duplicates = [n for n in self.all_nodes() if n['object_type'] == 'service' and n['identity']['service_id'] == SERVICE_A]
        self.assertEqual(len(duplicates), 2)
        self.assertEqual({n['label'] for n in duplicates}, {'First', 'Second'})
        self.assertTrue(all('conflict' in n['resolution_status'].lower() for n in duplicates))
        self.assertTrue(state['diagnostics'])

    def test_multiple_identifiers_in_one_service_never_resolve_either_lcn_candidate(self):
        identifiers = element('UniqueIdentifier', SERVICE_A) + element('UniqueIdentifier', SERVICE_B)
        table = lcn_table(((7, SERVICE_A), (8, SERVICE_B)))
        raw = document(service(identifier_xml=identifiers) +
                       '<LCNTableList>' + table + '</LCNTableList>')
        state = self.import_xml(raw)
        nodes = self.all_nodes()
        ambiguous = next(node for node in nodes if node['object_type'] == 'service')
        self.assertIsNone(ambiguous['identity']['service_id'])
        self.assertEqual(ambiguous['resolution_status'], 'conflict')
        self.assertIn(SERVICE_A, json.dumps(ambiguous))
        self.assertIn(SERVICE_B, json.dumps(ambiguous))
        assignments = [node for node in nodes if node['object_type'] == 'lcn_assignment']
        self.assertEqual(len(assignments), 2)
        for assignment in assignments:
            self.assertEqual(assignment['resolution_status'], 'unresolved')
            self.assertEqual(assignment['attributes']['service_nodes'], [])
        self.assertEqual(self.original(state['document_revision']), raw)

    def test_uri_reference_whitespace_normalizes_without_losing_original_attribute(self):
        raw_ref = '  ' + SERVICE_A + '  '
        table = lcn_table(((7, raw_ref),))
        self.import_xml(document(service(' ' + SERVICE_A + ' ') +
                                 '<LCNTableList>' + table + '</LCNTableList>'))
        nodes = self.all_nodes()
        target = next(node for node in nodes if node['object_type'] == 'service')
        assignment = next(node for node in nodes if node['object_type'] == 'lcn_assignment')
        self.assertEqual(target['identity']['service_id'], SERVICE_A)
        self.assertEqual(assignment['identity']['service_ref'], SERVICE_A)
        self.assertEqual(assignment['resolution_status'], 'resolved')
        self.assertEqual(assignment['attributes']['service_nodes'], [target['node_id']])
        attrs = assignment['attributes']['xml_attributes']
        self.assertEqual(next(attr['value'] for attr in attrs if attr['local_name'] == 'serviceRef'), raw_ref)

    def test_missing_identity_is_unresolved_without_name_based_fabrication(self):
        state = self.import_xml(document(service(name='No stable identifier', identifier_xml='')))
        nodes = [n for n in self.all_nodes() if n['label'] == 'No stable identifier']
        self.assertEqual(len(nodes), 1)
        self.assertTrue(nodes[0]['unresolved_reasons'])
        self.assertIsNone(nodes[0]['identity']['service_id'])
        self.assertTrue(state['diagnostics'])

    def test_duplicate_instance_ids_and_default_zero_are_not_silently_collapsed(self):
        for entries in (instance('same') + instance('same', 'DASHDeliveryParameters'),
                        instance(omit_id=True) + instance(omit_id=True)):
            with self.subTest(entries=entries):
                state = self.import_xml(document(service(instances=entries)))
                nodes = self.all_nodes()
                parent = next(n for n in nodes if n['object_type'] == 'service' and n['identity']['service_id'] == SERVICE_A)
                children = [n for n in nodes if n['parent_id'] == parent['node_id']]
                self.assertGreaterEqual(len(children), 2)
                conflicts = [n for n in children if 'conflict' in n['resolution_status'].lower()]
                self.assertGreaterEqual(len(conflicts), 2)
                self.assertTrue(state['diagnostics'])

    def test_regional_and_conflicting_lcn_assignments_are_not_overwritten(self):
        tables = (lcn_table(((7, SERVICE_A), (7, SERVICE_B)), region='north') +
                  lcn_table(((17, SERVICE_A),), region='south'))
        raw = document('<LCNTableList>' + tables + '</LCNTableList>' + service() + service(SERVICE_B))
        state = self.import_xml(raw)
        rendered = json.dumps(self.all_nodes(), ensure_ascii=False)
        for value in ('north', 'south', '17'):
            self.assertIn(value, rendered)
        conflicts = [n for n in self.all_nodes() if n['object_type'] == 'lcn_assignment'
                     and n['resolution_status'] == 'conflict']
        self.assertEqual(len(conflicts), 2)
        self.assertTrue(all(n['unresolved_reasons'] for n in conflicts))
        self.assertEqual(self.original(state['document_revision']), raw)

    def test_nested_regions_keep_parentage_language_and_duplicate_identity_conflicts(self):
        regions = ('<RegionList><Region regionID="north"><RegionName>North</RegionName>'
                   '<Region regionID="city" xml:lang="zh"><RegionName>城區</RegionName>'
                   '<CountryCode>AAA</CountryCode></Region></Region>'
                   '<Region regionID="south"><RegionName>South</RegionName>'
                   '<Region regionID="city"><RegionName>Other city</RegionName></Region>'
                   '</Region></RegionList>')
        state = self.import_xml(document(regions + service(extra='<TargetRegion>city</TargetRegion>')))
        nodes = self.all_nodes()
        by_label = {node['label']: node for node in nodes if node['object_type'] == 'region'}
        self.assertEqual(set(by_label), {'North', 'South', '城區', 'Other city'})
        self.assertEqual(by_label['城區']['parent_id'], by_label['North']['node_id'])
        self.assertEqual(by_label['Other city']['parent_id'], by_label['South']['node_id'])
        self.assertEqual(by_label['城區']['attributes']['names'][0]['language'], 'zh')
        self.assertEqual(by_label['North']['attributes']['names'][0]['language'], 'en')
        for label in ('城區', 'Other city'):
            self.assertEqual(by_label[label]['identity']['region_id'], 'city')
            self.assertEqual(by_label[label]['resolution_status'], 'conflict')
        target = next(node for node in nodes if node['object_type'] == 'service')
        self.assertEqual(target['attributes']['target_regions'][0]['region_ref'], 'city')
        self.assertEqual(self.original(state['document_revision']), document(
            regions + service(extra='<TargetRegion>city</TargetRegion>')))

    def test_lcn_boolean_values_defaults_and_malformed_values_remain_distinct(self):
        for lexical, expected in ((None, True), ('true', True), ('1', True),
                                  ('false', False), ('0', False), (' false ', False),
                                  ('False', None), ('yes', None), ('2', None)):
            with self.subTest(value=lexical):
                flags = '' if lexical is None else f' visible="{lexical}" selectable="{lexical}"'
                body = (f'<LCNTableList><LCNTable><LCN channelNumber="7" '
                        f'serviceRef="{SERVICE_A}"{flags}/></LCNTable></LCNTableList>' + service())
                self.import_xml(document(body))
                item = next(node for node in self.all_nodes() if node['object_type'] == 'lcn_assignment')
                for key in ('visible', 'selectable'):
                    self.assertIs(item['attributes'][key], expected)
                    self.assertEqual(item['attributes'][key + '_origin'],
                                     'schema_default' if lexical is None else 'declared')
                if expected is None:
                    self.assertTrue(any('boolean' in reason for reason in item['unresolved_reasons']))
                table = next(node for node in self.all_nodes() if node['object_type'] == 'lcn_table')
                self.assertIs(table['attributes']['preserveBroadcastLCN'], False)
                self.assertEqual(table['attributes']['preserveBroadcastLCN_origin'], 'schema_default')

    def test_normalized_lcn_numbers_still_conflict_and_keep_lexical_evidence(self):
        table = lcn_table((('007', SERVICE_A), ('+7', SERVICE_B)))
        self.import_xml(document('<LCNTableList>' + table + '</LCNTableList>' +
                                 service() + service(SERVICE_B)))
        assignments = [node for node in self.all_nodes() if node['object_type'] == 'lcn_assignment']
        self.assertEqual([node['attributes']['channel_number'] for node in assignments], [7, 7])
        self.assertEqual([node['identity']['channel_number_raw'] for node in assignments], ['007', '+7'])
        self.assertTrue(all(node['resolution_status'] == 'conflict' for node in assignments))

    def test_missing_lcn_reference_or_ambiguous_service_never_selects_a_name_match(self):
        for services, reference, expected in ((service(), 'urn:missing:service', 'unresolved'),
                                               (service() + service(name='Second'), SERVICE_A, 'conflict')):
            with self.subTest(reference=reference):
                table = lcn_table(((7, reference),))
                self.import_xml(document('<LCNTableList>' + table + '</LCNTableList>' + services))
                item = next(node for node in self.all_nodes() if node['object_type'] == 'lcn_assignment')
                self.assertEqual(item['resolution_status'], expected)
                self.assertEqual(len(item['attributes']['service_nodes']),
                                 0 if expected == 'unresolved' else 2)

    def test_instance_schema_defaults_are_explicit_and_do_not_create_extra_instances(self):
        body = service(instances=instance(omit_id=True).replace(' priority="1"', ''))
        self.import_xml(document(body))
        instances = [node for node in self.all_nodes() if node['object_type'] == 'service_instance']
        self.assertEqual(len(instances), 1)
        self.assertEqual(instances[0]['identity'], {'instance_id': '0', 'id_origin': 'schema_default'})
        self.assertEqual(instances[0]['attributes']['priority'], 0)
        self.assertEqual(instances[0]['attributes']['priority_origin'], 'schema_default')

    def test_diagnostics_cap_reports_omissions_without_losing_raw_or_semantic_nodes(self):
        raw = document(''.join(service(identifier_xml='', name=f'Missing ID {i}') for i in range(180)))
        state = self.import_xml(raw)
        self.assertEqual(len(state['diagnostics']), 100)
        self.assertGreater(state['diagnostics_omitted'], 0)
        self.assertEqual(len([node for node in self.all_nodes() if node['object_type'] == 'service']), 180)
        self.assertEqual(self.original(state['document_revision']), raw)

    def test_pinned_expat_source_manifest_and_runtime_parser_identity(self):
        vendor = ROOT / 'third_party/expat'
        manifest = json.loads((vendor / 'SHOWPSISI_SOURCE.json').read_text(encoding='utf-8'))
        self.assertEqual(manifest['version'], '2.9.0')
        self.assertEqual(manifest['source_sha256'],
                         '1e6371862cc31999b368c3b89b49994f0677e1bab5f1b2b85ae3741f5d803051')
        self.assertEqual(manifest['source'],
                         'https://github.com/libexpat/libexpat/releases/download/R_2_9_0/expat-2.9.0.tar.xz')
        self.assertIn('COPYING', manifest['files_sha256'])
        self.assertIn('lib/xmlparse.c', manifest['files_sha256'])
        for name, expected in manifest['files_sha256'].items():
            with self.subTest(vendored_file=name):
                path = vendor / name
                self.assertTrue(path.resolve().is_relative_to(vendor.resolve()))
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), expected)
        listed = set(manifest['files_sha256']) | {'SHOWPSISI_SOURCE.json'}
        actual = {path.relative_to(vendor).as_posix() for path in vendor.rglob('*') if path.is_file()}
        self.assertEqual(actual, listed, 'unreviewed vendored files must not enter the pinned source subset')
        state = self.import_xml()
        self.assertEqual(state['parser'], {'name': 'Expat', 'version': 'expat_2.9.0', 'static_link': True})

    def test_malformed_numeric_values_have_diagnostics_and_preserved_evidence(self):
        for value in ('-1', '65536', 'not-a-number', '1.5', '99999999999999999999999'):
            with self.subTest(value=value):
                body = service(instances=instance(triplet=(value, 101, 1)))
                raw = document(body)
                state = self.import_xml(raw)
                self.assertEqual(state['status'], 'partial')
                self.assertTrue(any('Invalid DVBTriplet' in reason
                                    for node in self.all_nodes()
                                    for reason in node['unresolved_reasons']))
                self.assertIn(value, json.dumps(self.all_nodes()))
                self.assertEqual(self.original(state['document_revision']), raw)

    def test_pagination_reports_total_and_never_repeats_or_omits_nodes(self):
        state = self.import_xml(many_services(280))
        total = state['counts']['nodes']
        self.assertGreater(total, 200)
        first = self.query()
        self.assertEqual(first['page']['offset'], 0)
        self.assertEqual(first['page']['limit'], 200)
        self.assertEqual(len(first['nodes']), 200)
        self.assertEqual(first['page']['total'], total)
        self.assertTrue(first['page']['has_more'])
        self.assertEqual(first['page']['next_offset'], 200)
        nodes, offset = [], 0
        while offset < total:
            page = self.query(document_revision=state['document_revision'], offset=offset, limit=37)
            self.assertEqual(page['page']['total'], total)
            self.assertEqual(page['page']['offset'], offset)
            self.assertEqual(len(page['nodes']), min(37, total - offset))
            nodes.extend(page['nodes'])
            offset += len(page['nodes'])
        self.assertEqual(nodes, self.all_nodes())
        self.assertEqual(len({n['node_id'] for n in nodes}), total)
        empty = self.query(offset=total + 10)
        self.assertEqual(empty['nodes'], [])
        self.assertFalse(empty['page']['has_more'])
        self.assertIsNone(empty['page']['next_offset'])

    def test_revision_changes_only_on_success_and_old_locators_are_rejected(self):
        first = self.import_xml()
        old_locator = self.all_nodes()[0]['evidence'][0]
        self.rejected_without_replacement(b'<broken')
        second = self.import_xml(document(service(name='New document')),
                                 expected_document_revision=first['document_revision'])
        self.assertEqual(second['document_revision'], first['document_revision'] + 1)
        for method, params in (
            ('query_dvbi', {'document_revision': first['document_revision']}),
            ('inspect_dvbi', {'document_revision': first['document_revision'],
                             'element_id': old_locator['element_id']})):
            with self.subTest(method=method), self.assertRaisesRegex(CoreError, '(?i)stale|revision'):
                self.call(method, params)
        with self.assertRaisesRegex(CoreError, '(?i)stale|revision'):
            self.import_xml(expected_document_revision=first['document_revision'])
        self.assertEqual(self.query(), second)

    def test_same_bytes_reimport_still_advances_document_revision(self):
        first = self.import_xml()
        second = self.import_xml()
        self.assertEqual(second['source']['sha256'], first['source']['sha256'])
        self.assertEqual(second['document_revision'], first['document_revision'] + 1)

    def test_file_change_after_import_cannot_rewrite_retained_source(self):
        raw = fixture()
        state = self.import_xml(raw)
        self.path.write_bytes(document(service(name='Rewritten on disk')))
        self.assertEqual(self.original(state['document_revision']), raw)
        self.assertEqual(self.query()['source']['sha256'], hashlib.sha256(raw).hexdigest())
        self.path.unlink()
        self.assertEqual(self.original(state['document_revision']), raw)

    def test_successful_and_failed_xml_import_keep_existing_ts_session_and_preview(self):
        ts_path = Path(self.tmp.name) / 'captured.ts'
        ts_raw = transport_fixture()
        ts_path.write_bytes(ts_raw)
        state = self.call('analyze', {'path': str(ts_path), 'standards': 'dvb'})
        self.assertTrue(state['services'])
        selected = state['services'][0]
        preview = self.call('preview_rename', {'id': selected['source_id'],
                                             'service_id': selected['id'], 'name': 'Still valid'})
        before = self.call('query')
        self.import_xml()
        self.assertEqual(self.call('query'), before)
        self.rejected_without_replacement(b'<unclosed>')
        self.assertEqual(self.call('query'), before)
        out = Path(self.tmp.name) / 'retained-preview.bin'
        self.call('export', {'path': str(out), 'format': 'bin', 'preview_token': preview['token']})
        self.assertTrue(out.is_file())
        self.assertEqual(ts_path.read_bytes(), ts_raw)

    def test_ts_analysis_does_not_invalidate_independent_xml_evidence(self):
        state = self.import_xml()
        before = self.query()
        path = Path(self.tmp.name) / 'later.ts'
        path.write_bytes(transport_fixture())
        self.call('analyze', {'path': str(path)})
        self.assertEqual(self.query(), before)
        self.assertEqual(self.original(state['document_revision']), fixture())

    def test_inspection_is_revision_bound_and_matches_every_projected_locator(self):
        state = self.import_xml()
        for node in self.all_nodes():
            for locator in node['evidence']:
                detail = self.inspect(state['document_revision'], element_id=locator['element_id'])
                self.assertEqual(detail['document_revision'], state['document_revision'])
                self.assertEqual(detail['source']['sha256'], state['source']['sha256'])
                self.assertEqual(detail['element']['element_id'], locator['element_id'])
                self.assertEqual(detail['element']['line'], locator['line'])
                self.assertEqual(detail['element']['column'], locator['column'])
                if locator['precision'] == 'attribute':
                    self.assertEqual(locator['path'], detail['element']['path'] +
                                     '/@' + locator['attribute_name'])
                    self.assertIn(locator['attribute_name'],
                                  ['Q{' + a['namespace'] + '}' + a['local_name']
                                   for a in detail['element']['attributes']])
                else:
                    self.assertEqual(detail['element']['path'], locator['path'])
                self.assertEqual(bytes.fromhex(detail['original_source']['data']), fixture())
        with self.assertRaises(CoreError):
            self.inspect(state['document_revision'], element_id='e99999999')

    def test_utf16_and_non_utf8_declarations_are_explicitly_rejected(self):
        self.import_xml()
        bad = [fixture().decode().replace('UTF-8', 'UTF-16').encode('utf-16'),
               fixture().replace(b'UTF-8', b'ISO-8859-1'),
               fixture().replace(b'UTF-8', b'windows-1252')]
        for raw in bad:
            with self.subTest(start=raw[:60]):
                self.rejected_without_replacement(raw, '(?i)UTF.?8|encoding')

    def test_invalid_xml_nul_utf8_and_truncation_fail_without_replacement(self):
        self.import_xml()
        for raw in (b'', b'<', b'<x>', b'<x></y>', b'<x/>junk', b'<x/><y/>',
                    b'<x>\x00</x>', b'<x>\xff</x>', b'<x>&unknown;</x>',
                    b'<x duplicate="a" duplicate="b"/>', fixture()[:-20]):
            with self.subTest(raw=raw[:80]):
                self.rejected_without_replacement(raw)

    def test_dtd_internal_entity_and_external_entity_are_fail_closed(self):
        self.import_xml()
        secret = Path(self.tmp.name) / 'entity-canary.txt'
        secret.write_text('PRIVATE-ENTITY-CANARY', encoding='utf-8')
        cases = [b'<!DOCTYPE x><x/>',
                 b'<!DOCTYPE x [<!ENTITY a "expanded">]><x>&a;</x>',
                 (f'<!DOCTYPE x [<!ENTITY steal SYSTEM "{secret.as_uri()}">]>'
                  '<x>&steal;</x>').encode(),
                 b'<!DOCTYPE x [<!ENTITY % p "<!ENTITY a \'expansion\'>">%p;]><x>&a;</x>']
        with FetchTrap() as trap:
            cases.append(f'<!DOCTYPE x SYSTEM "{trap.url}/external.dtd"><x/>'.encode())
            for raw in cases:
                with self.subTest(raw=raw[:80]):
                    error = self.rejected_without_replacement(raw, '(?i)DTD|DOCTYPE|entit')
                    self.assertNotIn('PRIVATE-ENTITY-CANARY', str(error))
            self.assertEqual(trap.requests, [])
        self.assertEqual(secret.read_text(), 'PRIVATE-ENTITY-CANARY')

    def test_xinclude_schema_location_and_media_links_are_never_fetched(self):
        with FetchTrap() as trap:
            media = instance('broadband', 'DASHDeliveryParameters').replace(
                'https://media.example.invalid/alpha.mpd', trap.url + '/media.mpd')
            body = (service(instances=media) + f'<xi:include xmlns:xi="http://www.w3.org/2001/XInclude" '
                    f'href="{trap.url}/include.xml"/>' +
                    f'<ext:URLBase>{trap.url}/base/</ext:URLBase>')
            raw = document(body, attributes={
                'xmlns:xsi': 'http://www.w3.org/2001/XMLSchema-instance',
                'xsi:schemaLocation': f'{NAMESPACE} {trap.url}/schema.xsd'})
            state = self.import_xml(raw)
            self.assertEqual(trap.requests, [])
            self.assertNotIn('FETCHED-CANARY', json.dumps(self.all_nodes()))
            candidates = [delivery for node in self.all_nodes()
                          for delivery in node['attributes'].get('delivery_parameters', [])]
            self.assertEqual(candidates[0]['uris'][0]['value'], trap.url + '/media.mpd')
            self.assertEqual(candidates[0]['uris'][0]['fetch_status'], 'not_fetched')
            self.assertEqual(self.original(state['document_revision']), raw)

    def test_unknown_xml_elements_attributes_and_tree_order_remain_inspectable(self):
        state = self.import_xml()
        root = self.inspect(state['document_revision'])['element']
        self.assertEqual(root['element_id'], 'e0')
        self.assertEqual(root['namespace'], NAMESPACE)
        self.assertEqual(root['local_name'], 'ServiceList')
        pending, visited, elements = ['e0'], set(), []
        while pending:
            identifier = pending.pop(0)
            self.assertNotIn(identifier, visited, 'raw element tree must not contain cycles')
            visited.add(identifier)
            item = self.inspect(state['document_revision'], element_id=identifier)['element']
            self.assertEqual(item['element_id'], identifier)
            elements.append(item)
            pending.extend(item['children'])
        self.assertEqual(len(visited), state['counts']['elements'])
        self.assertEqual(visited, {f'e{i}' for i in range(state['counts']['elements'])})
        extension = next(item for item in elements if item['local_name'] == 'FutureFeature')
        self.assertEqual(extension['namespace'], 'urn:example.invalid:dvbi:extension')
        self.assertEqual(extension['qualified_name'], 'ext:FutureFeature')
        self.assertEqual(extension['text'], 'unknown extension')
        self.assertEqual(extension['attributes'], [{
            'namespace': 'urn:example.invalid:dvbi:extension', 'local_name': 'flag',
            'qualified_name': 'ext:flag', 'value': 'preserve & inspect'}])
        services = [item for item in elements if item['local_name'] == 'Service']
        self.assertEqual(len(services), 2)
        self.assertTrue(services[0]['path'].endswith('}Service[1]'))
        self.assertTrue(services[1]['path'].endswith('}Service[2]'))

    def test_namespace_spoofed_identity_triplets_and_uri_are_never_interpreted(self):
        wrong_id = '<ext:UniqueIdentifier>urn:spoof:identity</ext:UniqueIdentifier>'
        wrong_triplet = instance().replace('<DVBTriplet ', '<ext:DVBTriplet ')
        wrong_uri = instance('broadband', 'DASHDeliveryParameters').replace('types:URI', 'ext:URI')
        raw = document(service(identifier_xml=wrong_id,
                               instances=wrong_triplet + wrong_uri))
        state = self.import_xml(raw)
        nodes = self.all_nodes()
        found = next(node for node in nodes if node['object_type'] == 'service')
        self.assertIsNone(found['identity']['service_id'])
        for node in nodes:
            for delivery in node['attributes'].get('delivery_parameters', []):
                self.assertFalse(delivery.get('broadcast_triplets', []))
                self.assertFalse(delivery.get('uris', []))
        self.assertEqual(self.original(state['document_revision']), raw)

    def test_decimal_triplet_lexical_variants_keep_raw_values_without_ts_join(self):
        state = self.import_xml(document(service(instances=instance(triplet=(' +901 ', '00101', ' +1 ')))))
        nodes = self.all_nodes()
        candidate = next(node for node in nodes if node['object_type'] == 'service_instance')
        triplet = candidate['attributes']['delivery_parameters'][0]['broadcast_triplets'][0]
        self.assertEqual([triplet[key] for key in ('origNetId', 'tsId', 'serviceId')], [901, 101, 1])
        self.assertEqual([triplet[key + '_raw'] for key in ('origNetId', 'tsId', 'serviceId')],
                         [' +901 ', '00101', ' +1 '])
        self.assertEqual(triplet['association_status'], 'not_joined')
        self.assertFalse(any('Invalid DVBTriplet' in reason for node in nodes
                             for reason in node['unresolved_reasons']))

    def test_exact_document_depth_element_attribute_name_and_text_limits_are_accepted(self):
        # Independently exercise each exact inclusive bound; a parser that rejects
        # all large inputs must not satisfy the corresponding negative tests.
        cases = {
            'depth': b'<x>' * 48 + b'</x>' * 48,
            'element': b'<x>' + b'<e/>' * 19999 + b'</x>',
            'attributes': ('<x ' + ' '.join(f'a{i}="v"' for i in range(64)) + '/>').encode(),
            'value': b'<x a="' + b'v' * 65536 + b'"/>',
            'name': b'<' + b'a' * 1024 + b'/>',
            'element_text': b'<x>' + b'a' * 65536 + b'</x>',
            'total_text': b'<x>' + (b'<e>' + b'a' * 32768 + b'</e>') * 64 + b'</x>',
        }
        prefix, suffix = b'<x><!--', b'--></x>'
        cases['bytes'] = prefix + b'a' * (4 * 1024 * 1024 - len(prefix) - len(suffix)) + suffix
        for name, raw in cases.items():
            with self.subTest(limit=name):
                state = self.import_xml(raw)
                self.assertEqual(state['status'], 'unsupported')
                self.assertEqual(state['source']['bytes'], len(raw))
                self.assertEqual(state['source']['sha256'], hashlib.sha256(raw).hexdigest())
                self.assertEqual(self.original(state['document_revision']), raw)

    def test_source_paging_exact_end_and_out_of_range(self):
        raw = fixture()
        state = self.import_xml(raw)
        last = self.inspect(state['document_revision'], source_offset=len(raw), source_limit=65536)
        self.assertEqual(last['original_source']['length'], 0)
        self.assertEqual(last['original_source']['data'], '')
        self.assertFalse(last['original_source']['has_more'])
        with self.assertRaises(CoreError):
            self.inspect(state['document_revision'], source_offset=len(raw) + 1)

    def test_uninitialized_queries_and_stale_first_import_are_rejected(self):
        for method, params in (('query_dvbi', {}), ('inspect_dvbi', {'document_revision': 0})):
            with self.subTest(method=method), self.assertRaises(CoreError):
                self.call(method, params)
        with self.assertRaisesRegex(CoreError, '(?i)stale|revision'):
            self.import_xml(expected_document_revision=1)
        state = self.import_xml(expected_document_revision=0)
        self.assertEqual(state['document_revision'], 1)

    def test_url_is_not_an_implicit_network_import(self):
        self.import_xml()
        before = self.query()
        with FetchTrap() as trap:
            with self.assertRaises(CoreError):
                self.call('import_dvbi', {'path': trap.url + '/list.xml', 'profile': PROFILE})
            self.assertEqual(trap.requests, [])
        self.assertEqual(self.query(), before)

    def test_input_size_limit_rejects_before_replacing_document(self):
        self.import_xml()
        self.rejected_without_replacement(b'<x><!--' + b'x' * (4 * 1024 * 1024) + b'--></x>',
                                          '(?i)size|byte|large|limit')

    def test_depth_element_text_attribute_and_name_limits_are_bounded(self):
        self.import_xml()
        cases = {
            'depth': b'<x>' * 49 + b'</x>' * 49,
            'element': b'<x>' + b'<e/>' * 20000 + b'</x>',
            'text': b'<x>' + (b'<e>' + b'a' * 32768 + b'</e>') * 65 + b'</x>',
            'attributes': ('<x ' + ' '.join(f'a{i}="v"' for i in range(65)) + '/>').encode(),
            'value': b'<x a="' + b'v' * 65537 + b'"/>',
            'name': b'<' + b'a' * 1025 + b'/>',
            'element_text': b'<x>' + b'a' * 65537 + b'</x>',
        }
        for name, raw in cases.items():
            with self.subTest(limit=name):
                started = time.monotonic()
                self.rejected_without_replacement(raw, '(?i)limit|maximum|depth|element|text|attribute|name|value|large')
                self.assertLess(time.monotonic() - started, 8, 'bounded rejection exceeded test watchdog')

    def test_cumulative_expanded_path_budget_is_bounded(self):
        self.import_xml()
        name = b'a' * 512
        raw = (b'<' + name + b'>') * 40 + b'<leaf/>' * 600 + (b'</' + name + b'>') * 40
        self.assertLess(len(raw), 4 * 1024 * 1024)
        self.rejected_without_replacement(raw, '(?i)path|limit|large')

    def test_missing_file_and_directory_are_rejected_without_replacement(self):
        self.import_xml()
        before = self.query()
        for path in (Path(self.tmp.name) / 'missing.xml', Path(self.tmp.name)):
            with self.subTest(path=path), self.assertRaises(CoreError):
                self.call('import_dvbi', {'path': str(path), 'profile': PROFILE}, timeout=5)
            self.assertEqual(self.query(), before)

    def test_embedded_nul_path_cannot_open_a_different_file_than_reported(self):
        self.path.write_bytes(fixture())
        forged_path = str(self.path) + '\x00/unopened.xml'
        with self.assertRaisesRegex(CoreError, '(?i)NUL|path'):
            self.call('import_dvbi', {'path': forged_path, 'profile': PROFILE})
        with self.assertRaises(CoreError):
            self.query()
        self.import_xml()
        before = self.query()
        with self.assertRaisesRegex(CoreError, '(?i)NUL|path'):
            self.call('import_dvbi', {'path': forged_path, 'profile': PROFILE})
        self.assertEqual(self.query(), before)
        self.assertEqual(self.original(before['document_revision']), fixture())

    def test_unc_and_device_namespace_paths_are_rejected_before_os_open(self):
        self.import_xml()
        before = self.query()
        # Loopback names avoid naming any third-party server even if a future
        # regression accidentally reaches the OS instead of this lexical guard.
        paths = ('//127.0.0.1/share/list.xml', '\\\\127.0.0.1\\share\\list.xml',
                 '/\\127.0.0.1/share/list.xml', '\\/127.0.0.1/share/list.xml',
                 '\\\\?\\C:\\list.xml', '\\\\.\\NUL')
        for path in paths:
            with self.subTest(path=path), self.assertRaisesRegex(CoreError, '(?i)UNC|device|local path'):
                self.call('import_dvbi', {'path': path, 'profile': PROFILE}, timeout=3)
            self.assertEqual(self.query(), before)

    # Discover the actual OS-specific handle test, never report a POSIX FIFO
    # as executed on Windows and never relax the strict runner's skip policy.
    if os.name == 'nt':
        def test_windows_nonregular_device_and_owned_pipe_are_refused(self):
            import ctypes
            from ctypes import wintypes
            import uuid
            self.import_xml()
            before = self.query()
            paths = [self.tmp.name] + [str(Path(self.tmp.name) / name) for name in
                     ('NUL', 'NUL.xml', 'CON', 'AUX', 'COM1', 'LPT9', 'COM¹.xml', 'LPT²', 'data.xml:stream')]
            for path in paths:
                with self.subTest(path=path), self.assertRaises(CoreError):
                    self.call('import_dvbi', {'path': path, 'profile': PROFILE}, timeout=3)
                self.assertEqual(self.query(), before)
            kernel = ctypes.WinDLL('kernel32', use_last_error=True)
            kernel.CreateNamedPipeW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                               wintypes.DWORD, wintypes.DWORD, wintypes.DWORD,
                                               wintypes.DWORD, ctypes.c_void_p]
            kernel.CreateNamedPipeW.restype = wintypes.HANDLE
            kernel.CloseHandle.argtypes = [wintypes.HANDLE]
            pipe = '\\\\.' + '\\pipe\\showpsisi-dvbi-' + uuid.uuid4().hex
            handle = kernel.CreateNamedPipeW(pipe, 0x40000001, 0, 1, 4096, 4096, 0, None)
            self.assertNotEqual(handle, ctypes.c_void_p(-1).value, ctypes.get_last_error())
            try:
                with self.assertRaisesRegex(CoreError, '(?i)UNC|device|local path'):
                    self.call('import_dvbi', {'path': pipe, 'profile': PROFILE}, timeout=3)
                self.assertEqual(self.query(), before)
            finally:
                kernel.CloseHandle(handle)
    else:
        def test_fifo_is_rejected_without_blocking_for_writer(self):
            self.import_xml()
            before = self.query()
            fifo = Path(self.tmp.name) / 'unwritten.fifo'
            os.mkfifo(fifo)
            with self.assertRaisesRegex(CoreError, '(?i)regular|file'):
                self.call('import_dvbi', {'path': str(fifo), 'profile': PROFILE}, timeout=3)
            self.assertEqual(self.query(), before)

    def test_schema_requires_profile_revision_and_enforces_pagination_bounds(self):
        tools = {tool['name']: tool for tool in self.call('capabilities')['tools']}
        for method in ('import_dvbi', 'query_dvbi', 'inspect_dvbi'):
            self.assertIn(method, tools)
            self.assertIsInstance(tools[method]['inputSchema'], dict)
        imp = tools['import_dvbi']['inputSchema']
        self.assertIn('path', imp['required'])
        self.assertIn('profile', imp['required'])
        self.assertIn(PROFILE, imp['properties']['profile']['enum'])
        self.assertIn('document_revision', tools['inspect_dvbi']['inputSchema']['required'])
        self.assertEqual(tools['query_dvbi']['inputSchema']['properties']['limit']['maximum'], 500)
        self.assertEqual(tools['inspect_dvbi']['inputSchema']['properties']['source_limit']['maximum'], 65536)
        self.assertTrue(tools['query_dvbi']['annotations']['readOnlyHint'])
        self.assertTrue(tools['inspect_dvbi']['annotations']['readOnlyHint'])
        self.assertTrue(tools['import_dvbi']['annotations']['readOnlyHint'])
        self.path.write_bytes(fixture())
        for params in ({'path': str(self.path)}, {'path': str(self.path), 'profile': 'latest'},
                       {'path': str(self.path), 'profile': PROFILE, 'expected_document_revision': True}):
            with self.subTest(params=params), self.assertRaises(CoreError):
                self.call('import_dvbi', params)
        state = self.import_xml()
        for method, base, key, values in (
            ('query_dvbi', {}, 'offset', [-1, True, '0', 0.5]),
            ('query_dvbi', {}, 'limit', [0, 501, True, '10']),
            ('inspect_dvbi', {'document_revision': state['document_revision']}, 'source_offset', [-1, True]),
            ('inspect_dvbi', {'document_revision': state['document_revision']}, 'source_limit', [0, 65537, True]),
            ('inspect_dvbi', {}, 'document_revision', [True, -1, '1'])):
            for value in values:
                with self.subTest(method=method, key=key, value=value), self.assertRaises(CoreError):
                    self.call(method, {**base, key: value})
        with self.assertRaises(CoreError):
            self.call('inspect_dvbi', {})

    def test_original_byte_offsets_and_utf16_marker_preserve_bom_and_declaration(self):
        raw = b'\xef\xbb\xbf<?xml version="1.0" encoding="UTF-8"?>\r\n<!-- \xf0\x9f\x93\xba -->\r\n' + fixture().split(b'\n', 1)[1]
        state = self.import_xml(raw)
        root = self.inspect(state['document_revision'])
        self.assertEqual(root['element']['original_byte_offset'], raw.index(b'<ServiceList'))
        self.assertEqual(root['element']['byte_offset_precision'], 'element_start')
        original = root['original_source']
        self.assertEqual(original['text'].encode('utf-8'), raw)
        marker = len(raw[:raw.index(b'<ServiceList')].decode('utf-8').encode('utf-16-le')) // 2
        self.assertEqual(original['element_start_character'], marker)
        self.assertEqual(root['element']['evidence']['original_byte_offset'], raw.index(b'<ServiceList'))
        for ref in state['nodes'][0]['evidence']:
            self.assertEqual(raw[ref['original_byte_offset']:ref['original_byte_offset'] + 1], b'<')

    def test_original_text_pages_trim_only_partial_utf8_boundaries(self):
        raw = '<root>α📺中é</root>'.encode('utf-8')
        state = self.import_xml(raw)
        for offset in range(len(raw)):
            for limit in range(1, 7):
                with self.subTest(offset=offset, limit=limit):
                    original = self.inspect(state['document_revision'], source_offset=offset, source_limit=limit)['original_source']
                    self.assertEqual(bytes.fromhex(original['data']), raw[offset:offset + limit])
                    start, length = original['text_offset'], original['text_length']
                    self.assertGreaterEqual(start, offset)
                    self.assertLessEqual(start + length, offset + original['length'])
                    self.assertEqual(original['text'].encode('utf-8'), raw[start:start + length])
                    self.assertNotIn('\ufffd', original['text'])

    def test_child_summaries_are_bounded_and_preserve_unknown_tree_identity(self):
        raw = b'<x xmlns="urn:unknown">' + b''.join(b'<child n="%d"><leaf/></child>' % i for i in range(505)) + b'</x>'
        state = self.import_xml(raw)
        first = self.inspect(state['document_revision'], child_limit=500)
        self.assertEqual(first['child_page']['total'], 505)
        self.assertEqual(len(first['child_summaries']), 500)
        self.assertEqual(first['child_page']['next_offset'], 500)
        last = self.inspect(state['document_revision'], child_offset=500)
        self.assertEqual(len(last['child_summaries']), 5)
        self.assertFalse(last['child_page']['has_more'])
        for child in last['child_summaries']:
            inspected = self.inspect(state['document_revision'], element_id=child['element_id'])
            self.assertEqual(inspected['element']['parent_id'], 'e0')
            self.assertEqual(inspected['element']['original_byte_offset'], child['original_byte_offset'])
            self.assertEqual(inspected['element']['namespace'], 'urn:unknown')
            self.assertTrue(child['has_children'])
        for args in ({'child_offset': -1}, {'child_limit': 0}, {'child_limit': 501}, {'child_offset': True}):
            with self.assertRaises(CoreError):
                self.inspect(state['document_revision'], **args)

    def test_mcp_discovery_import_query_inspect_and_failed_replacement(self):
        self.path.write_bytes(fixture())
        proc = subprocess.Popen([sys.executable, str(ROOT / 'scripts/mcp_server.py')],
                                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                text=True, encoding='utf-8',
                                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        messages = queue.Queue()

        def read():
            for line in proc.stdout:
                try:
                    messages.put(json.loads(line))
                except ValueError as error:
                    messages.put(error)

        reader = threading.Thread(target=read, daemon=True)
        reader.start()
        sequence = 0

        def call(method, params):
            nonlocal sequence
            sequence += 1
            proc.stdin.write(json.dumps({'jsonrpc': '2.0', 'id': sequence,
                                         'method': method, 'params': params}) + '\n')
            proc.stdin.flush()
            response = messages.get(timeout=10)
            self.assertIsInstance(response, dict)
            self.assertEqual(response['id'], sequence)
            self.assertNotIn('error', response)
            return response['result']

        def tool(name, arguments):
            return call('tools/call', {'name': name, 'arguments': arguments})

        try:
            initialized = call('initialize', {'protocolVersion': '2025-06-18', 'capabilities': {},
                                               'clientInfo': {'name': 'dvbi-regression', 'version': '1'}})
            self.assertEqual(initialized['serverInfo']['name'], 'ShowPsiSi')
            listed = {t['name']: t for t in call('tools/list', {})['tools']}
            native = {t['name']: t for t in self.call('capabilities')['tools']}
            for name in ('import_dvbi', 'query_dvbi', 'inspect_dvbi'):
                self.assertEqual(listed[name]['inputSchema'], native[name]['inputSchema'])
            imported = tool('import_dvbi', {'path': str(self.path), 'profile': PROFILE})
            self.assertFalse(imported['isError'])
            state = imported['structuredContent']
            revision = state['document_revision']
            queried = tool('query_dvbi', {'document_revision': revision, 'limit': 1})
            self.assertFalse(queried['isError'])
            self.assertEqual(len(queried['structuredContent']['nodes']), 1)
            locator = queried['structuredContent']['nodes'][0]['evidence'][0]
            inspected = tool('inspect_dvbi', {'document_revision': revision,
                                               'element_id': locator['element_id']})
            self.assertFalse(inspected['isError'])
            self.assertEqual(bytes.fromhex(inspected['structuredContent']['original_source']['data']), fixture())
            self.path.write_bytes(b'<!DOCTYPE x><x/>')
            failed = tool('import_dvbi', {'path': str(self.path), 'profile': PROFILE})
            self.assertTrue(failed['isError'])
            self.assertIn('error', failed['structuredContent'])
            retained = tool('query_dvbi', {'document_revision': revision})
            self.assertFalse(retained['isError'])
            self.assertEqual(retained['structuredContent']['source']['sha256'], state['source']['sha256'])
        finally:
            proc.stdin.close()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=3)
            reader.join(timeout=3)
            stderr = proc.stderr.read()
            proc.stdout.close()
            proc.stderr.close()
        self.assertEqual(proc.returncode, 0, stderr)


if __name__ == '__main__':
    unittest.main()
