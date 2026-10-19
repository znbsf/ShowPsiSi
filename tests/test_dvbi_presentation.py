"""Shared DVB-I UI helpers over real native XML import/query/inspect output."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from core_client import Core
from dvbi_fixture import fixture, many_services, PROFILE

class DvbiPresentationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.core=Core();self.addCleanup(self.core.close)

    def js(self,expression,value):
        script="const fs=require('fs'),vm=require('vm');let c={};vm.createContext(c);vm.runInContext(fs.readFileSync(process.argv[1],'utf8'),c);const v=JSON.parse(fs.readFileSync(0,'utf8'));console.log(JSON.stringify(("+expression+")(v,c.workbench)));"
        result=subprocess.run(['node','-e',script,str(ROOT/'ui/tauri/web/workbench.js')],input=json.dumps(value),text=True,capture_output=True,timeout=10,check=True)
        return json.loads(result.stdout)

    def imported(self,raw=None):
        path=Path(self.tmp.name)/'document.xml';path.write_bytes(raw if raw is not None else fixture())
        self.core.call('import_dvbi',{'path':str(path),'profile':PROFILE})
        return self.core.call('query_dvbi',{'limit':500})

    def evidence(self):
        snapshot=self.imported()
        node=snapshot['nodes'][0]
        refs=self.js('(n,w)=>w.dvbiEvidence(n)',node)
        ref=next(r for r in refs if r['precision']=='attribute')
        detail=self.core.call('inspect_dvbi',{'document_revision':snapshot['document_revision'],'element_id':ref['element_id']})
        return {'snapshot':snapshot,'node':node,'refs':refs,'ref':ref,'detail':detail}

    def test_real_document_and_ancestor_preserving_rows(self):
        snapshot=self.imported()
        result=self.js('(s,w)=>{let expanded={};s.nodes.forEach(n=>expanded[n.node_id]=true);return {error:w.validateDvbi(s,s.document_revision,s.source.sha256),rows:w.dvbiRows(s,"",expanded,{})};}',snapshot)
        self.assertEqual(result['error'],'')
        self.assertEqual(len(result['rows']['rows']),snapshot['counts']['nodes'])
        for row in result['rows']['rows']:
            self.assertNotIn('pid',row['node']['identity'])
        rows=self.js('(s,w)=>w.dvbiRows(s,"broadband",{},{}).rows',snapshot)
        ids={r['node']['node_id'] for r in rows}
        self.assertTrue(rows)
        for row in rows:
            if row['parent_id']:self.assertIn(row['parent_id'],ids)

    def test_paged_merge_rejects_changed_document(self):
        snapshot=self.imported(many_services(510))
        page=self.core.call('query_dvbi',{'offset':500,'limit':500,'document_revision':snapshot['document_revision']})
        merged=self.js('(v,w)=>w.mergeDvbi(v.first,v.next)',{'first':snapshot,'next':page})
        self.assertEqual(len(merged['nodes']),merged['counts']['nodes'])
        self.assertEqual(len({n['node_id'] for n in merged['nodes']}),len(merged['nodes']))
        page['source']['sha256']='different'
        self.assertIn('hash',self.js('(v,w)=>{try{w.mergeDvbi(v.first,v.next);return "accepted";}catch(e){return e.message;}}',{'first':snapshot,'next':page}))

    def test_all_sources_include_unknown_extensions_and_attribute_precision(self):
        value=self.evidence()
        self.assertTrue(any('FutureFeature' in ref['path'] for ref in value['refs']))
        self.assertEqual(len({(r['path'],r['element_id']) for r in value['refs']}),len(value['refs']))
        result=self.js('(v,w)=>w.resolveDvbiEvidence(v.ref,v.detail)',value)
        self.assertEqual(result['status'],'resolved');self.assertEqual(result['precision'],'attribute')
        self.assertGreaterEqual(result['attribute_index'],0)
        self.assertEqual(result['line_precision'],'element_start')
        self.assertNotIn('byte_range',result)
        value['detail']['element']['attributes']=[]
        fallback=self.js('(v,w)=>w.resolveDvbiEvidence(v.ref,v.detail)',value)
        self.assertEqual((fallback['status'],fallback['precision']),('fallback','element'))

    def test_revision_hash_element_and_path_mismatch_are_rejected(self):
        original=self.evidence()
        for key,value in [('document_revision',99),('source_sha256','wrong'),('element_id','other'),('path','wrong'),('line',999)]:
            with self.subTest(key=key):
                changed=copy.deepcopy(original);changed['ref'][key]=value
                result=self.js('(v,w)=>w.resolveDvbiEvidence(v.ref,v.detail)',changed)
                self.assertEqual(result['status'],'mismatch');self.assertIsNone(result['original_byte_offset'])

    def test_unsupported_namespace_does_not_gain_semantic_nodes(self):
        snapshot=self.imported(fixture(namespace='urn:unknown:edition'))
        self.assertEqual(snapshot['status'],'unsupported')
        self.assertEqual(self.js('(s,w)=>w.dvbiRows(s,"",{},{}).rows',snapshot),[])
        self.assertEqual(self.js('(s,w)=>w.validateDvbi(s)',snapshot),'')
