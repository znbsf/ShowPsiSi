import assert from 'node:assert/strict';
import fs from 'node:fs';
export async function verifySummaryAndGeneric(p,out,reference){
const checks=[];function check(name,v){assert.ok(v,name);checks.push(name);}
const count=await p.evaluate(()=>document.querySelectorAll('#transport-si tbody tr').length);check('all 88 observed PIDs available',count===88);
await p.click('#transport-si [data-sort="packets"]');await p.waitForFunction(()=>!document.querySelector('#transport-si').innerText.includes('Loading…'));
check('packet sort descending',await p.evaluate(()=>{const counts=[...document.querySelectorAll('#transport-si tbody tr')].map(r=>Number(r.children[1].textContent.replaceAll(',','')));return counts.every((n,i)=>!i||counts[i-1]>=n);}));
await p.click('#transport-si [data-action="error"]');await p.waitForFunction(()=>!document.querySelector('#transport-si').innerText.includes('Loading…'));check('error page retains explicit scope',await p.evaluate(()=>document.querySelector('#transport-si').innerText.includes('Errors excludes continuity, PES and decoder checks')));
await p.click('#transport-si [data-action="summary"]');await p.waitForFunction(()=>document.querySelectorAll('#transport-si tbody tr').length===88);
const row=await p.evaluate(()=>[...document.querySelectorAll('#transport-si tbody tr')].find(r=>r.firstElementChild.textContent==='0x0108').dataset.index);
await p.dblclick('#transport-si tr[data-index="'+row+'"]');await p.waitForFunction(()=>showpsisi.getUiState().unified.visible&&showpsisi.getDetail().pid===264&&showpsisi.getUiState().settled);
check('PID double-click returns to exact SI record',await p.evaluate(()=>showpsisi.getUiState().unified.navigation.filter(r=>r.kind==='record').every(r=>r.record_id.startsWith('264:'))));
await p.fill('#source',reference);await p.click('#scan');await p.waitForFunction(()=>showpsisi.getState().complete&&showpsisi.getUiState().settled,undefined,{timeout:45000});
check('new source clears old network and cache',await p.evaluate(()=>!showpsisi.getUiState().unified.navigation.some(r=>r.label.includes('Mediaset'))&&showpsisi.getUiState().unified.cached<=1));
for(const name of ['AIT','UNT','DSMCC_user_to_network_message','DSMCC_download_data_message']){
 await p.selectOption('.si-nav-tools select',name);
 const record=await p.evaluate(()=>showpsisi.getUiState().unified.navigation.find(r=>r.kind==='record'));
 const selector='.si-nav-row[data-key='+JSON.stringify(record.key)+']';await p.click(selector+' .si-fold');
 await p.waitForFunction(id=>showpsisi.getDetail().id===id&&showpsisi.getUiState().settled,record.record_id);
 const node=await p.evaluate(()=>showpsisi.getUiState().unified.navigation.find(r=>r.kind==='node'&&r.path.startsWith('section/decoded')));check(name+' native hierarchy visible',!!node);
 await p.click('.si-nav-row[data-key='+JSON.stringify(node.key)+'] .si-row-label');
 check(name+' semantic byte scope explicit',await p.evaluate(()=>showpsisi.getUiState().unified.range===null&&document.querySelector('.si-status').textContent.includes('Exact byte range unavailable')&&document.querySelectorAll('.si-hex .si-selected').length===0));
}
await p.screenshot({path:out+'/generic-si.png'});
check('no frontend errors after cross-source navigation',await p.evaluate(()=>showpsisi.getUiState().diagnostics.frontend_errors.length===0));
fs.writeFileSync(out+'/extended-result.json',JSON.stringify({passed:true,checks},null,2));console.log({passed:true,checks:checks.length});

return {passed:true,checks:checks.length};
}
