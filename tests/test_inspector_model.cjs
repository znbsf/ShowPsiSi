const assert=require('node:assert/strict');
const fs=require('node:fs');
const model=require('../ui/tauri/web/inspector-model.js');
const evidenceDirectory=process.env.SHOWPSISI_UNIFIED_EVIDENCE_DIR || 'artifacts/unified-inspector';
const evidence=JSON.parse(fs.readFileSync(evidenceDirectory+'/engine-evidence.json','utf8'));
let checks=0;
for(const d of evidence.details){
  const tree=model.structure(d),rows=model.flatten(tree,{},0);
  assert.ok(tree && rows.length);checks++;
  assert.equal(new Set(rows.map(r=>r.path)).size,rows.length);checks++;
  if(d.table_id===0x70 || d.table_id===0x73){
    assert.ok(!/v0|current|next|§/.test(model.title(d)));checks++;
    assert.ok(!tree.fields.some(f=>/version|current|section_number|extension/.test(f.name)));checks++;
    assert.match(model.summary(d,evidence.state),/UTC 2026/);checks++;
  }
  for(const n of rows.filter(r=>r.range)){
    assert.ok(n.range.offset>=0 && n.range.offset+n.range.length<=d.bytes);checks++;
  }
}
const pat=evidence.details.find(d=>d.name==='PAT');
assert.match(model.summary(pat,evidence.state),/101.*0x0100/);checks++;
const large={path:'root',label:'large',fields:[],children:Array.from({length:230},(_,i)=>({path:'root/'+i,label:String(i),fields:[],children:[]}))};
assert.equal(model.flatten(large,{},0,{}).length,102);checks++;
assert.equal(model.flatten(large,{},0,{root:200}).length,202);checks++;
assert.equal(model.flatten(large,{},0,{root:300}).length,231);checks++;
assert.equal(model.flatten(large,{root:true},0,{}).length,1);checks++;
assert.equal(model.find(large,'root/229').label,'229');checks++;
assert.equal(model.find(large,'root/23/missing'),null);checks++;
const otherSource=Object.assign({},pat,{section_native_table:undefined,native_table_complete:true,native_table_sources:[{id:'other-section'}]});
assert.equal(model.find(model.structure(otherSource),'section/decoded').label,'Decoded fields');checks++;
const multipleSources=Object.assign({},otherSource,{native_table_sources:[{id:pat.id},{id:'another-section'}]});
assert.equal(model.find(model.structure(multipleSources),'section/decoded').label,'Decoded fields');checks++;
const ambiguousNames={services:[{id:101,ts_id:pat.extension,onid:1,name:'A'},{id:101,ts_id:pat.extension,onid:2,name:'B'}]};
assert.match(model.summary(pat,ambiguousNames),/ambiguous service identity/);checks++;
const pmt=evidence.details.find(d=>d.name==='PMT' && d.pid===0x100);
const table=model.fieldTable(model.structure(pmt),{},0);
assert.ok(table.findIndex(f=>f.name==='CRC_32')>table.findIndex(f=>f.name==='elementary_PID'));checks++;
assert.ok(table.some(f=>f.name==='component_tag' && f.bit_offset===152));checks++;
const programRows=model.programTree(evidence.state,evidence.state.tables,evidence.topology,{},'');
assert.ok(programRows.some(r=>r.label.includes('Fixture Network')));checks++;
assert.ok(programRows.some(r=>r.label.includes('11727.5 MHz')));checks++;
const named=programRows.find(r=>r.label.includes('LCN 7  News One'));
assert.equal(named.record.pid,0x100);checks++;
const conflict=JSON.parse(JSON.stringify(evidence.state));conflict.services[0].lcn_status='conflict';conflict.services[0].logical_channel_number=null;
assert.ok(model.programTree(conflict,conflict.tables,evidence.topology,{},'').some(r=>r.label.includes('LCN conflict')));checks++;
const duplicated=JSON.parse(JSON.stringify(evidence.state));duplicated.services.push({...duplicated.services[0],onid:99,name:'Another network'});
const ambiguous=model.programTree(duplicated,duplicated.tables,evidence.topology,{},'').filter(r=>r.service);
assert.ok(ambiguous.every(r=>!r.record || r.record.name!=='PMT'));checks++;
assert.ok(model.programTree(evidence.state,evidence.state.tables,{}, {},'news one').some(r=>r.label.includes('News One')));checks++;
const pmtTree=model.structure(pmt),navPmt=model.tableNavigation(pmtTree,pmt,pmt.id,{}, {},3);
const es=navPmt.find(r=>r.node && r.node.path==='section/stream/12');
assert.ok(es.label.includes('PID=0x0101') && es.label.includes('stream_type = 0x1B'));checks++;
const desc=navPmt.find(r=>r.node && r.node.descriptor_offset===17);
assert.equal(desc.depth,es.depth+1);checks++;
assert.equal(navPmt.filter(r=>r.node && r.node.descriptor_offset!==undefined).length,pmt.descriptors.length);checks++;
assert.ok(!navPmt.some(r=>r.node && /\/decoded|section\/descriptors/.test(r.node.path)));checks++;
assert.equal(model.tableNavigation(pmtTree,pmt,pmt.id,{[es.key]:true},{},3).length,1);checks++;
const nit=evidence.details.find(d=>d.name==='NIT'),nitTree=model.structure(nit),navNit=model.tableNavigation(nitTree,nit,nit.id,{}, {},3);
const tp=navNit.find(r=>r.label==='ONID=0x2001 TSID = 0x1001');assert.ok(tp);checks++;
assert.equal(navNit.find(r=>r.node.descriptor_offset===10).depth,tp.depth);checks++;
assert.equal(navNit.find(r=>r.node.descriptor_offset===35).depth,tp.depth+1);checks++;
assert.deepEqual(model.wireRange(tp.node),{offset:29,length:31});checks++;
assert.equal(navNit.find(r=>r.node.descriptor_offset===54).label,'eacem_logical_channel_number_descriptor TAG(0x83)');checks++;
assert.match(navPmt.find(r=>r.node && r.node.descriptor_offset===20).label,/generic_descriptor TAG\(0xE2\)/);checks++;
assert.ok(model.navigationTitle(pmt,pmtTree).includes('PCR_PID[0x0101]'));checks++;
const bounded=model.tableNavigation(large,pat,'bounded',{}, {},3);
assert.equal(bounded.length,101);assert.equal(bounded[100].kind,'more');checks++;
const references=JSON.parse(fs.readFileSync(evidenceDirectory+'/reference-trees.json','utf8'));
let genericCases=0,semanticNodes=0;
for(const c of references){
  const d=c.detail,tree=model.structure(d),rows=model.tableNavigation(tree,d,d.id,{}, {},3);
  assert.ok(rows.length,c.name);checks++;
  assert.equal(new Set(rows.map(r=>r.key)).size,rows.length,c.name);checks++;
  if(!(d.si_structure.children || []).length){
    genericCases++;
    const expected=[];
    function visit(n,path){expected.push({n,path});(n.children || []).forEach((child,i)=>visit(child,path+'/'+i));}
    if(d.native_table.children.length)d.native_table.children.forEach((n,i)=>visit(n,'section/decoded/'+i));else visit(d.native_table,'section/decoded');
    for(const {n,path} of expected){
      const row=rows.find(r=>r.node && r.node.path===path);assert.ok(row,c.name+': '+path);checks++;
      assert.equal(row.node.semanticName,n.name);checks++;
      for(const [name,value] of Object.entries(n.attributes || {})){assert.ok(row.node.fields.some(f=>f.name===name && f.value===String(value)),c.name+': '+name);checks++;}
      assert.equal(model.wireRange(row.node),null,'No invented semantic offsets');checks++;
      semanticNodes++;
    }
  }
}
assert.ok(genericCases>30 && semanticNodes>100);checks++;
const ait=references.find(c=>c.name==='DVB_AIT').detail;
const merged=Object.assign({},ait,{native_table_sources:[{id:ait.id},{id:'another-section'}]});
const mergedRows=model.tableNavigation(model.structure(merged),merged,merged.id,{}, {},3);
assert.ok(mergedRows.some(r=>r.node.path==='section/assembled' && r.label.includes('2 sections')));checks++;
assert.ok(mergedRows.some(r=>r.node.path.startsWith('section/assembled/') && r.node.semanticName==='application'));checks++;
assert.ok(mergedRows.every(r=>model.wireRange(r.node)===null));checks++;
// A new decoder tree must work without editing a table-name switch.
const future=Object.assign({},ait,{native_table:{name:'Future_table',attributes:{},children:[{name:'arbitrary_loop',attributes:{identity:'42'},children:[{name:'nested_leaf',attributes:{value:'kept'},children:[]}]}]}});
assert.ok(model.tableNavigation(model.structure(future),future,future.id,{}, {},3).some(r=>r.node.semanticName==='nested_leaf'));checks++;
console.log(JSON.stringify({passed:true,checks,referenceCases:references.length,genericCases,semanticNodes}));
