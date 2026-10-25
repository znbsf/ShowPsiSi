// Run with an ego-browser Page against scripts/cloud_preview.py and Hotbird input.
// Uses real engine data and actual pointer/keyboard actions, no replacement backend.
import assert from 'node:assert/strict';
import fs from 'node:fs';
export async function verifyClassicSi(page, output) {
 const checks=[];const check=(name,value)=>{assert.ok(value,name);checks.push(name);};
 const ui=()=>page.evaluate(()=>showpsisi.getUiState().unified);
 const nav=key=>'.si-nav-row[data-key='+JSON.stringify(key)+']';
 const select=(key)=>nav(key)+' .si-row-label';
 let state=await ui();
 check('classic view is active',state.visible);
 check('network and TP are organized automatically',state.navigation.some(r=>r.label.includes('Mediaset'))&&state.navigation.some(r=>r.label.includes('11919 MHz')));
 const program=state.navigation.find(r=>r.label.startsWith('TgCom24'));assert.ok(program);
 await page.click(select(program.key));await page.waitForFunction(id=>showpsisi.getDetail().id===id&&showpsisi.getUiState().settled,program.record_id);
 state=await ui();check('single-click record selects without expanding',!state.navigation.find(r=>r.key===program.key).expanded);
 await page.dblclick(select(program.key));await page.waitForFunction(key=>showpsisi.getUiState().unified.navigation.some(r=>r.key===key&&r.expanded),program.key);
 state=await ui();const stream=state.navigation.find(r=>r.record_id===program.record_id&&r.path==='section/stream/17');assert.ok(stream);
 await page.click(select(stream.key));state=await ui();check('single-click internal row keeps branch open',state.navigation.find(r=>r.key===stream.key).expanded);
 const selectedTop=await page.evaluate(key=>document.querySelector('.si-nav-row[data-key='+JSON.stringify(key)+']').getBoundingClientRect().top,stream.key);
 await page.dblclick(select(stream.key));state=await ui();check('double-click internal row collapses',!state.navigation.find(r=>r.key===stream.key).expanded);
 await page.click(nav(stream.key)+' .si-fold');state=await ui();check('single-click plus expands',state.navigation.find(r=>r.key===stream.key).expanded);
 const finalTop=await page.evaluate(key=>document.querySelector('.si-nav-row[data-key='+JSON.stringify(key)+']').getBoundingClientRect().top,stream.key);
 check('left row remains at its clicked position',Math.abs(selectedTop-finalTop)<=1);
 const descriptor=state.navigation.find(r=>r.record_id===program.record_id&&r.path==='section/stream/17/descriptor/22');assert.ok(descriptor);
 await page.click(select(descriptor.key));state=await ui();check('descriptor links exact section bytes',state.range?.offset===22&&state.range?.length===6);
 check('both hex panes highlight selected evidence',await page.evaluate(()=>document.querySelectorAll('.si-packet .si-selected').length===6&&document.querySelectorAll('.si-section .si-selected').length===6));
 const field='.si-field-row[data-path="section/stream/17/descriptor/22"][aria-expanded]';
 const group=field+' .si-field-name';
 const initial=await page.evaluate(selector=>{const e=document.querySelector(selector);return {expanded:e.getAttribute('aria-expanded'),y:e.getBoundingClientRect().top,scroll:document.querySelector('.si-fields').scrollTop};},field);
 await page.click(group);check('field text single-click does not fold',await page.evaluate(selector=>document.querySelector(selector).getAttribute('aria-expanded')==='true',field));
 await page.dblclick(group);check('field text double-click folds',await page.evaluate(selector=>document.querySelector(selector).getAttribute('aria-expanded')==='false',field));
 const collapsed=await page.evaluate(selector=>document.querySelector(selector).getBoundingClientRect().top,field);check('field folding keeps viewport',Math.abs(initial.y-collapsed)<=1);
 await page.click(field+' .si-fold');check('field plus click expands',await page.evaluate(selector=>document.querySelector(selector).getAttribute('aria-expanded')==='true',field));
 const before=(await ui()).columnWidths[0];await page.focus('.si-column-grip[data-column="0"]');await page.press('.si-column-grip[data-column="0"]','ArrowRight');check('keyboard resize changes field column',Math.abs((await ui()).columnWidths[0]-before-16)<1);
 check('field grid aligns with headers',await page.evaluate(()=>{const headers=[...document.querySelectorAll('.si-field-header>div')],cells=[...document.querySelector('.si-field-row').children];return headers.every((h,i)=>Math.abs(h.getBoundingClientRect().right-cells[i].getBoundingClientRect().right)<1&&getComputedStyle(cells[i]).borderRightWidth==='1px');}));
 await page.dblclick('.si-column-grip[data-column="2"]');check('double-click column divider fits content',(await ui()).columnWidths[2]>0);
 await page.click('.si-section [data-byte="23"]');check('hex click locates the smallest proven field',(await ui()).range?.offset===23&&(await ui()).range?.length===1);
 await page.click('#workspace-toggle');check('advanced workbench remains available',await page.evaluate(()=>!document.body.classList.contains('si-mode')&&document.querySelector('#panes').getBoundingClientRect().height>0));
 await page.click('#workspace-toggle');check('return to SI keeps selected owner',(await ui()).selected===program.record_id);
 check('no frontend errors',await page.evaluate(()=>showpsisi.getUiState().diagnostics.frontend_errors.length===0));
 await page.screenshot({path:output+'/classic-si.png'});
 const result={passed:true,checks,scope:'real engine browser UI; native WebView2 is a separate gate',state:await ui()};fs.writeFileSync(output+'/classic-result.json',JSON.stringify(result,null,2));return {passed:true,checks:checks.length};
}
