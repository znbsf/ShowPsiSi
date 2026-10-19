"""Pure shared presentation checks against actual native topology/inspect results.

Requires Node.js for the same dependency-free JavaScript imported by Qt and Web.
This is not browser/native-window interaction evidence.
"""
import copy
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from core_client import Core
from topology_fixture import parts, write_ts, pat, pmt, sdt, nit


class TopologyPresentationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='showpsisi-topology-ui-')
        self.addCleanup(self.tmp.cleanup)
        self.core = Core()
        self.addCleanup(self.core.close)
        self.node = shutil.which('node') or shutil.which('nodejs')
        if not self.node:
            self.fail('Node.js is required for shared topology presentation tests')

    def js(self, expression, value):
        script = "const fs=require('fs'),vm=require('vm');const c={};vm.createContext(c);vm.runInContext(fs.readFileSync(process.argv[1],'utf8'),c);const input=JSON.parse(fs.readFileSync(0,'utf8'));const w=c.workbench;console.log(JSON.stringify((" + expression + ")(input,w)));"
        process = subprocess.run([self.node, '-e', script, str(ROOT/'ui/tauri/web/workbench.js')], input=json.dumps(value), encoding='utf-8', stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        return json.loads(process.stdout)

    def snapshot(self, profile='dvb', sections=None):
        source = write_ts(Path(self.tmp.name)/'source.ts', sections or parts(profile))
        state = self.core.call('analyze', {'path':str(source), 'standards':profile})
        return self.core.call('query_topology', {'analysis_revision':state['revision'], 'limit':500})

    def evidence(self):
        snapshot = self.snapshot()
        service = next(n for n in snapshot['nodes'] if n['object_type']=='service')
        ref = next(r for r in service['evidence'] if r['assertion_key']=='name')
        detail = self.core.call('inspect', {'id':ref['section_id'], 'at_packet':ref['at_packet']})
        return {'snapshot':snapshot, 'node':service, 'ref':ref, 'detail':detail}

    def test_actual_three_adapter_projection_and_search(self):
        for profile in ('dvb','atsc','isdb-japan','isdb-brazil','isdb'):
            with self.subTest(profile=profile):
                snapshot=self.snapshot(profile)
                result=self.js('(s,w)=>{const expanded={};w.topologyNodes(s).forEach(n=>expanded[n.node_id]=true);return {error:w.validateTopology(s,s.analysis_revision,s.at_packet),rows:w.topologyRows(s,"all","",expanded,{}),identities:s.nodes.map(n=>w.topologyIdentity(n))};}',snapshot)
                self.assertEqual(result['error'],'')
                self.assertEqual(len(result['rows']['rows']),len(snapshot['nodes']))
                self.assertEqual(len({r['node']['node_id'] for r in result['rows']['rows']}),len(snapshot['nodes']))
                self.assertTrue(all('undefined' not in value for value in result['identities']))
        snapshot=self.snapshot()
        result=self.js('(s,w)=>w.topologyRows(s,"all","0x0064",{},{}).rows',snapshot)
        ids={r['node']['node_id'] for r in result}
        self.assertTrue(any('service:' in i for i in ids))
        for row in result:
            if row['parent_id']:
                self.assertIn(row['parent_id'],ids,'Search must retain ancestors')

    def test_exact_field_anchor_and_real_byte_range(self):
        value=self.evidence()
        result=self.js('(v,w)=>w.resolveTopologyEvidence(v.ref,v.detail)',value)
        self.assertEqual(result['status'],'resolved')
        self.assertEqual(result['precision'],'field')
        self.assertEqual(result['byte_range'],value['ref']['locator']['byte_range'])
        raw=bytes.fromhex(value['detail']['raw_hex'])
        span=result['byte_range']
        self.assertEqual(raw[span['offset']:span['offset']+span['length']],b'Topology Lab')
        paths=self.js('(v,w)=>{const paths=[];function visit(n,p){p=p?p+"/"+n.id:n.id;paths.push(p);(n.children||[]).forEach(x=>visit(x,p));}visit(w.structure(v.detail,"section",-1),"");return paths;}',value)
        self.assertIn(result['path'],paths)

    def test_compact_identities_preserve_full_inspector_explanations(self):
        snapshot=self.snapshot()
        service=next(n for n in snapshot['nodes'] if n['object_type']=='service')
        component=next(n for n in snapshot['nodes'] if n['object_type']=='component')
        self.assertEqual(self.js('(n,w)=>w.topologyIdentity(n)',service),'ONID 0x0002 · TSID 0x0001 · SID 0x0064')
        self.assertEqual(self.js('(n,w)=>w.topologyIdentity(n)',component),'PID 0x0200')
        details=self.js('(n,w)=>w.topologyIdentityDetails(n)',component)
        self.assertIn('Packet identifier (PID): 0x0200 (512)',details)
        self.assertIn('Program object reference: '+component['identity']['program_node_id'],details)
        snapshot=self.snapshot('atsc')
        channels=[n for n in snapshot['nodes'] if n['object_type']=='virtual_channel']
        self.assertEqual([self.js('(n,w)=>w.topologyIdentity(n)',n) for n in channels],['CH 7.1','CH 1031'])
        self.assertEqual(self.js('(n,w)=>w.topologyIdentity(n)',{'identity':{'pid':None,'unknown_key':23}}),'')

    def test_missing_field_falls_back_to_container_or_section(self):
        value=self.evidence()
        value['ref']['locator']['field_id']='absent-opaque-field'
        result=self.js('(v,w)=>w.resolveTopologyEvidence(v.ref,v.detail)',value)
        self.assertEqual(result['precision'],'container')
        value['detail']['evidence_anchors']=[]
        result=self.js('(v,w)=>w.resolveTopologyEvidence(v.ref,v.detail)',value)
        self.assertEqual(result['precision'],'section')
        self.assertEqual(result['status'],'fallback')
        self.assertIsNone(result['byte_range'])

    def test_revision_cutoff_section_and_table_mismatch_rejected(self):
        original=self.evidence()
        for key,value in (('id','foreign'),('analysis_revision',999),('native_table_at_packet',999),('pid',999),('section',999)):
            with self.subTest(key=key):
                sample=copy.deepcopy(original);sample['detail'][key]=value
                result=self.js('(v,w)=>w.resolveTopologyEvidence(v.ref,v.detail)',sample)
                self.assertEqual(result['status'],'mismatch')
                self.assertIsNone(result['byte_range'])

    def test_out_of_bounds_or_mismatched_byte_ranges_not_highlighted(self):
        value=self.evidence()
        index=next(i for i,a in enumerate(value['detail']['evidence_anchors']) if a['field_id']==value['ref']['locator']['field_id'])
        value['detail']['evidence_anchors'][index]['byte_range']['offset']=999999
        result=self.js('(v,w)=>w.resolveTopologyEvidence(v.ref,v.detail)',value)
        self.assertEqual(result['precision'],'field')
        self.assertIsNone(result['byte_range'])

    def test_all_incoming_and_outgoing_assertions_remain_available(self):
        value=self.evidence()
        result=self.js('(v,w)=>w.topologyEvidence(v.node,v.snapshot.edges)',value)
        expected=len(value['node']['evidence'])+sum(len(e['evidence']) for e in value['snapshot']['edges'] if value['node']['node_id'] in (e['from'],e['to']))
        self.assertEqual(len(result),expected)
        self.assertTrue(any(r['edge_id'] for r in result))
        self.assertGreater(len({r['ref']['section_id'] for r in result}),1)

    def test_real_pages_merge_without_lost_ancestors_or_duplicates(self):
        snapshot=self.snapshot()
        first=self.core.call('query_topology',{'limit':2})
        second=self.core.call('query_topology',{'offset':2,'limit':2})
        merged=self.js('(v,w)=>w.mergeTopology(v[0],v[1])',[first,second])
        self.assertEqual(len(merged['nodes']),len({n['node_id'] for n in merged['nodes']}))
        ids={n['node_id'] for n in merged['nodes']}
        for node in merged['nodes']:
            if node['parent_id']:self.assertIn(node['parent_id'],ids)
        self.assertLess(len(merged['nodes']),snapshot['counts']['nodes'])
        self.assertTrue(merged['page']['has_more'])

    def test_child_paging_is_explicit_and_search_is_not_mutating(self):
        snapshot=self.snapshot(sections=[pat(programs=()),sdt(services=tuple((100+i,'Service '+str(i)) for i in range(105)))])
        result=self.js('(s,w)=>{const open={};s.nodes.forEach(n=>open[n.node_id]=true);const before=JSON.stringify(open);return {rows:w.topologyRows(s,"all","",open,{}),search:w.topologyRows(s,"all","Service 104",open,{}),unchanged:before===JSON.stringify(open)};}',snapshot)
        self.assertTrue(result['unchanged'])
        self.assertTrue(any(r.get('more') for r in result['rows']['rows']))
        self.assertTrue(any(r.get('node',{}).get('label')=='Service 104' for r in result['search']['rows']))

    def test_stale_snapshot_validation(self):
        snapshot=self.snapshot()
        self.assertIn('revision',self.js('(s,w)=>w.validateTopology(s,s.analysis_revision+1,s.at_packet)',snapshot))
        self.assertIn('cutoff',self.js('(s,w)=>w.validateTopology(s,s.analysis_revision,s.at_packet+1)',snapshot))
