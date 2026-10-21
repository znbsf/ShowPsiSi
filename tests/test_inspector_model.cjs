const assert=require('node:assert/strict');
const fs=require('node:fs');
const model=require('../ui/qt/InspectorModel.js');
const evidence=JSON.parse(fs.readFileSync('artifacts/unified-inspector/engine-evidence.json','utf8'));
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
const otherSource=Object.assign({},pat,{section_native_table:undefined,native_table_complete:true,native_table_sources:[{id:'other-section'}]});
assert.equal(model.structure(otherSource).children[0].label,'Decoded fields');checks++;
const multipleSources=Object.assign({},otherSource,{native_table_sources:[{id:pat.id},{id:'another-section'}]});
assert.equal(model.structure(multipleSources).children[0].label,'Decoded fields');checks++;
const ambiguousNames={services:[{id:101,ts_id:pat.extension,onid:1,name:'A'},{id:101,ts_id:pat.extension,onid:2,name:'B'}]};
assert.match(model.summary(pat,ambiguousNames),/ambiguous service identity/);checks++;
console.log(JSON.stringify({passed:true,checks}));
