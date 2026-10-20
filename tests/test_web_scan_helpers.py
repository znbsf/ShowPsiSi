"""Shared Web/Qt filtering contracts; no browser or timing-dependent assertions."""
import json
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ScanPresentationTests(unittest.TestCase):
    def test_search_matches_sections_once_and_preserves_group_siblings(self):
        script = r"""
const fs=require('fs'),vm=require('vm');const c={};vm.createContext(c);
vm.runInContext(fs.readFileSync(process.argv[1],'utf8'),c);
const w=c.workbench, original=w.matches;let calls=0;
w.matches=(...args)=>{calls++;return original(...args)};
const state={tables:[],table_groups:[]};
for(let i=0;i<1000;i++) {
  const ids=[];
  for(let j=0;j<2;j++){const id=`${i}-${j}`;ids.push(id);state.tables.push({id,pid:17,table_id:66,extension:i,section:j,name:'SDT',private_label:i===999&&j===1?'needle private': 'other',crc:{status:j?'invalid':'valid'}});}
  state.table_groups.push({id:'group'+i,pid:17,table_id:66,extension:i,name:'SDT',section_ids:ids});
}
const a=w.tables(state,null,'',true,'needle private');const firstCalls=calls;calls=0;
const b=w.tables(state,null,'',false,'needle private');
const d=w.tables(state,18,'',true,'needle private');
process.stdout.write(JSON.stringify({groups:a.groups.map(g=>g.id),all:a.sections.map(r=>r.id),valid:b.sections.map(r=>r.id),hidden:b.hidden,wrongPid:d.groups.length,calls:firstCalls,bound:state.tables.length+state.table_groups.length}));
"""
        run = subprocess.run(['node', '-e', script, str(ROOT/'ui/tauri/web/workbench.js')],
                             check=True, text=True, capture_output=True, timeout=30)
        result = json.loads(run.stdout)
        self.assertEqual(result['groups'], ['group999'])
        self.assertEqual(result['all'], ['999-0', '999-1'])
        self.assertEqual(result['valid'], ['999-0'])
        self.assertEqual(result['hidden'], 1)
        self.assertEqual(result['wrongPid'], 0)
        self.assertLessEqual(result['calls'], result['bound'])


    def test_reference_selection_cache_is_per_structure_and_semantically_identical(self):
        script = r"""
const fs=require('fs'),vm=require('vm'),assert=require('assert');const c={};vm.createContext(c);
vm.runInContext(fs.readFileSync(process.argv[1],'utf8'),c);const w=c.workbench;
const detail={id:'source',name:'PMT',table_id:2,pid:256,extension:101,version:1,section:0,
 valid:true,current:true,analysis_revision:1,native_table_at_packet:90,
 fields:{pcr_pid:257,streams:[{pid:257},{pid:257}]},
 merged:{native_table:{name:'PMT',attributes:{pcr_pid:'257'},children:[{name:'component',attributes:{elementary_pid:'257'}}]}}};
const target={id:'target',name:'SDT',table_id:66,pid:257,extension:1,version:1,section:0,valid:true,current:true,crc:{status:'valid'}};
const state={complete:true,revision:1,selected_packet:null,tables:[detail,target],table_groups:[{selected_section_ids:['source','target']}],services:[]};
const resolver=w.resolveReference;let builds=0;const filter=state.tables.filter;
state.tables.filter=function(fn){builds++;return filter.call(this,fn)};
function tree(cached){w.resolveReference=cached?resolver:function(f,d,s){const plain=Object.assign({},f);delete plain.referenceSelection;return resolver(plain,d,s)};return JSON.stringify(w.structure(detail,'merged',-1,state));}
function compare(){builds=0;const cached=tree(true),count=builds;const plain=tree(false);assert.strictEqual(cached,plain);return {value:JSON.parse(cached),count};}
function refs(node){return (node.reference?[node.reference]:[]).concat(...(node.children||[]).map(refs));}
let result=compare();assert.strictEqual(result.count,1);assert.strictEqual(refs(result.value).length,5);
// Reusing the same mutable state across calls must never reuse old selection.
state.table_groups[0].selected_section_ids=['source'];assert.strictEqual(refs(compare().value).length,0);
state.table_groups[0].selected_section_ids.push('target');target.crc.status='invalid';assert.strictEqual(refs(compare().value).length,0);
target.crc.status='valid';target.current=false;assert.strictEqual(refs(compare().value).length,0);
target.current=true;state.tables.push(Object.assign({},target,{id:'ambiguous',version:2}));state.table_groups[0].selected_section_ids.push('ambiguous');assert.strictEqual(refs(compare().value).length,0);
state.tables.pop();state.table_groups[0].selected_section_ids.pop();assert.strictEqual(refs(compare().value).length,5);
state.revision=2;result=compare();assert.strictEqual(result.count,0);assert.strictEqual(refs(result.value).length,0);
state.revision=1;state.selected_packet=91;result=compare();assert.strictEqual(result.count,0);assert.strictEqual(refs(result.value).length,0);
state.selected_packet=90;assert.strictEqual(refs(compare().value).length,5);
state.complete=false;assert.strictEqual(refs(compare().value).length,0);
process.stdout.write('ok');
"""
        run = subprocess.run(['node', '-e', script, str(ROOT/'ui/tauri/web/workbench.js')],
                             check=True, text=True, capture_output=True, timeout=30)
        self.assertEqual(run.stdout, 'ok')


    def test_empty_transport_service_projection_skips_candidate_traversal(self):
        script = r"""
const fs=require('fs'),vm=require('vm'),assert=require('assert'),c={};vm.createContext(c);
vm.runInContext(fs.readFileSync(process.argv[1],'utf8'),c);const w=c.workbench;
const d={id:'eit',name:'EIT',table_id:78,valid:true,current:true,analysis_revision:1};
const row={id:'sdt',name:'SDT',pid:17,table_id:66,extension:1,version:0,section:0,valid:true,current:true};
const state={complete:true,revision:1,tables:[d,row],table_groups:[{selected_section_ids:['eit','sdt']}],services:[]};
const f={path:'native/EIT/transport_stream_id',value:1,root:{transport_stream_id:1,original_network_id:2}};
let candidateVisits=0;const original=state.tables.filter;
state.tables.filter=function(fn){const result=original.call(this,fn);const filter=result.filter;result.filter=function(predicate){return filter.call(this,r=>{candidateVisits++;return predicate(r)})};return result;};
for(const services of [[],[{id:3,ts_id:9,onid:2,source_id:'sdt'}],[{id:3,ts_id:1,onid:2,source_id:'missing'}]]) {
 state.services=services;candidateVisits=0;assert.strictEqual(w.resolveReference(f,d,state),null);assert.strictEqual(candidateVisits,0);
}
state.services=[{id:3,ts_id:1,onid:2,source_id:'sdt'}];assert.strictEqual(w.resolveReference(f,d,state).id,'sdt');assert.ok(candidateVisits>0);
process.stdout.write('ok');
"""
        run = subprocess.run(['node', '-e', script, str(ROOT/'ui/tauri/web/workbench.js')],
                             check=True, text=True, capture_output=True, timeout=30)
        self.assertEqual(run.stdout, 'ok')


if __name__ == '__main__':
    unittest.main()
