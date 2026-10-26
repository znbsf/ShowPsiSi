const assert=require('node:assert/strict'),fs=require('node:fs'),model=require('../ui/tauri/web/inspector-model.js');
const cases=JSON.parse(fs.readFileSync('artifacts/unified-inspector/service-identity-evidence.json','utf8'));
for(const [name,e] of Object.entries(cases)) {
  const primary=model.summary(e.details.find(d=>d.extension===0x1001),e.state);
  assert.match(primary,/Beta Music/);assert.doesNotMatch(primary,/Other Transport|Other Network|Service 103/);
  assert.match(primary,/Program 103[^\n]*name unknown/);assert.match(primary,/Program 104[^\n]*name unknown/);
  if(name==='ambiguous'){assert.match(primary,/Program 101[^\n]*ambiguous service identity/);assert.doesNotMatch(primary,/Alpha News/);}
  else assert.match(primary,/Program 101[^\n]*Alpha News/);
  const other=model.summary(e.details.find(d=>d.extension===0x1002),e.state);
  assert.match(other,/Other Transport/);assert.doesNotMatch(other,/Alpha News|Beta Music/);
}
console.log('PASS: real SDT name provenance, TSID separation, ONID ambiguity, unknown names');
