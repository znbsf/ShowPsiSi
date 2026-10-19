/* Independent local XML workspace. The engine owns XML parsing and semantics. */
"use strict";
function createDvbiWorkspace({call,invoke,status,changed}) {
  const q=s=>document.querySelector(s),escape=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const json=value=>escape(JSON.stringify(value,null,2));
  let state={active:false,metadata:null,snapshot:null,selected:'',focused:'',search:'',expanded:{},limits:{},detail:null,ref:null,resolution:null,view:'structure',history:[],loading:false,importing:false,error:'',inspectError:'',epoch:0,inspectEpoch:0,sourceLimit:100};
  const host=document.createElement('section');host.id='dvbi-workspace';host.setAttribute('aria-label','Local DVB-I XML workspace');host.hidden=true;
  host.innerHTML=`<div class="sourcebar"><label for="dvbi-source">XML SOURCE</label><input id="dvbi-source" placeholder="Local UTF-8 ServiceList XML path" spellcheck="false"><button class="btn" id="dvbi-browse">Open XML…</button><button class="btn primary" id="dvbi-import">Import XML</button></div><div class="dvbi-profile">ETSI TS 103 770 V1.2.1 · local, read-only evidence · no network fetching, playback or schema certification</div><p id="dvbi-message" role="status" aria-live="polite"></p><div class="dvbi-panes"><nav class="sidebar" aria-label="XML document explorer" id="dvbi-document"></nav><section class="center" aria-label="DVB-I semantic objects"><div class="panel-title">SERVICE LIST OBJECTS</div><div class="searchbar"><input type="search" id="dvbi-search" aria-label="Search loaded XML objects" placeholder="Search loaded objects…"><span id="dvbi-count"></span></div><p id="dvbi-loaded-note" class="meta"></p><div class="list" id="dvbi-list" role="tree" aria-label="DVB-I objects"></div></section><aside class="inspector" id="dvbi-inspector" aria-label="XML evidence inspector"></aside></div><footer id="dvbi-footer"></footer>`;
  q('#app > footer').before(host);
  const node=()=>state.snapshot?.nodes.find(n=>n.node_id===state.selected);
  function locked(){const s=status();return state.importing || !!s.busy || !!s.error;}
  function update() {
    const s=status();q('#dvbi-import').disabled=locked();q('#dvbi-browse').disabled=locked();q('#dvbi-source').disabled=locked();
    q('#dvbi-import').textContent=state.importing?'Importing…':'Import XML';
    q('#dvbi-message').textContent=s.error || state.error || (state.importing?'Importing local XML; asynchronous cancellation is unavailable.':state.loading?'Loading document objects…':'');
    q('#input-kind').disabled=state.importing || !!s.busy;
    q('#dvbi-footer').textContent=s.error?'Backend disconnected · cached XML evidence only':state.metadata?'Local XML · document revision '+state.metadata.document_revision+' · '+state.metadata.status+' · source read-only':'Local XML · no document imported';
    host.setAttribute('aria-busy',String(state.importing || state.loading));
    if(s.error)host.querySelectorAll('[data-dvbi-ref],[data-dvbi-child],#dvbi-root,#dvbi-more,#dvbi-source-prev,#dvbi-source-next,#dvbi-child-prev,#dvbi-child-next,#dvbi-retry').forEach(e=>e.disabled=true);
    changed();
  }
  function activate(active) {
    if((state.importing || status().busy) && active!==state.active){q('#input-kind').value=state.active?'dvbi':'ts';return;}
    state.active=active;host.hidden=!active;q('#app').dataset.inputKind=active?'dvbi':'ts';
    q('.workspace-name').textContent=active?'Local DVB-I XML workbench':'Transport stream workbench';
    if(active){render();q('#dvbi-source').focus();}update();
  }
  async function importFile() {
    if(locked())return;
    const path=q('#dvbi-source').value.trim();if(!path){state.error='Enter a local XML file path.';update();return;}
    state.importing=true;state.error='';const epoch=++state.epoch;state.loading=false;++state.inspectEpoch;state.inspectLoading=false;update();
    try {
      const metadata=await call('import_dvbi',{path,profile:'etsi-ts-103770-v1.2.1',...(state.metadata?{expected_document_revision:state.metadata.document_revision}:{})});
      if(epoch!==state.epoch)return;
      const error=workbench.validateDvbi(metadata);if(error)throw new Error(error);
      // Import is transactional in the engine. After success the old revision is
      // no longer current, even if the following read fails.
      Object.assign(state,{metadata,snapshot:null,selected:'',focused:'',search:'',expanded:{},limits:{},detail:null,ref:null,resolution:null,history:[],inspectError:'',sourceLimit:100});
      q('#dvbi-search').value='';render();await loadPage(false);
    } catch(error){if(epoch===state.epoch)state.error=String(error);}
    finally{if(epoch===state.epoch){state.importing=false;render();}}
  }
  async function loadPage(more) {
    if(state.loading || !state.metadata || status().error)return;
    const epoch=state.epoch,metadata=state.metadata;state.loading=true;state.error='';update();
    try {
      const page=await call('query_dvbi',{document_revision:metadata.document_revision,offset:more?state.snapshot?.page?.next_offset:0,limit:500});
      if(epoch!==state.epoch)return;
      const error=workbench.validateDvbi(page,metadata.document_revision,metadata.source.sha256);if(error)throw new Error(error);
      state.snapshot=workbench.mergeDvbi(more?state.snapshot:null,page);
    } catch(error){if(epoch===state.epoch)state.error=String(error);}
    finally{if(epoch===state.epoch){state.loading=false;render();}}
  }
  function renderDocument() {
    const m=state.metadata,d=state.detail,e=d?.element;
    q('#dvbi-document').innerHTML=`<div class="panel-title">XML DOCUMENT</div>${m?`<div class="dvbi-document-summary"><strong>Coverage: ${escape(m.status)}</strong><p>${escape(m.source.path)}</p><p>Revision ${m.document_revision} · ${m.source.bytes} original bytes</p><details><summary>Source identity and coverage</summary><pre>${json({sha256:m.source.sha256,namespace:m.namespace,profile:m.profile,coverage:m.coverage,parser:m.parser})}</pre></details><details><summary>Diagnostics (${m.diagnostics?.length || 0})</summary><pre>${json(m.diagnostics || [])}</pre>${m.diagnostics_omitted?`<p>${m.diagnostics_omitted} additional diagnostics omitted by engine</p>`:''}</details><button class="btn small" id="dvbi-root" ${locked()?'disabled':''}>Inspect XML root</button>${e?`<h3>Element navigation</h3><p>${escape(e.path)}</p>${e.parent_id?`<button class="btn small" data-dvbi-child="${escape(e.parent_id)}">↑ Parent element</button>`:''}<p>${d.child_page?.total?(d.child_page.offset+1):0}–${Math.min((d.child_page?.offset || 0)+(d.child_summaries?.length || 0),d.child_page?.total || 0)} / ${d.child_page?.total || 0} children</p><div class="dvbi-children">${(d.child_summaries || []).map(c=>`<button class="btn topology-source" data-dvbi-child="${escape(c.element_id)}" title="${escape(c.path)}"><strong>${escape(c.qualified_name)}</strong><span>${escape(c.namespace)} · line ${c.line}${c.has_children?' · children':''}</span></button>`).join('')}</div><div class="metadata-query"><button class="btn small" id="dvbi-child-prev" ${d.child_page?.offset>0?'':'disabled'}>Previous children</button><button class="btn small" id="dvbi-child-next" ${d.child_page?.has_more?'':'disabled'}>Next children</button></div>`:''}</div>`:'<div class="empty"><p>Import a local ServiceList document. Unsupported namespaces retain original XML evidence.</p></div>'}`;
    q('#dvbi-root')?.addEventListener('click',()=>inspectElement('e0',null));
    host.querySelectorAll('[data-dvbi-child]').forEach(b=>b.onclick=()=>inspectElement(b.dataset.dvbiChild,null));
    q('#dvbi-child-prev')?.addEventListener('click',()=>inspectElement(e.element_id,state.ref,{child_offset:Math.max(0,d.child_page.offset-100)},false));
    q('#dvbi-child-next')?.addEventListener('click',()=>inspectElement(e.element_id,state.ref,{child_offset:d.child_page.next_offset},false));
  }
  function renderRows() {
    const list=q('#dvbi-list'),scroll=list.scrollTop,hadFocus=list.contains(document.activeElement),snapshot=state.snapshot || {},model=workbench.dvbiRows(snapshot,state.search,state.expanded,state.limits);
    q('#dvbi-count').textContent=state.search?model.matched+' loaded matches':(snapshot.nodes?.length || 0)+' / '+(state.metadata?.counts.nodes || 0)+' loaded';
    q('#dvbi-loaded-note').textContent=snapshot.page?.has_more?'Search covers loaded objects only. Load more to search remaining objects.':'Semantic hierarchy supplied by the native XML projection.';
    const visible=model.rows.filter(r=>!r.more);if(!visible.some(r=>r.node.node_id===state.focused))state.focused=visible[0]?.node.node_id || '';
    list.innerHTML=model.rows.map(r=>r.more?`<button class="btn small" data-dvbi-branch-more="${escape(r.parent_id || '$roots')}">Show more children (${r.remaining} remaining)</button>`:`<div class="topology-row ${r.node.node_id===state.selected?'selected':''}" role="treeitem" tabindex="${r.node.node_id===state.focused?0:-1}" aria-level="${r.depth}" ${r.has_children?`aria-expanded="${r.expanded}"`:''} aria-selected="${r.node.node_id===state.selected}" data-dvbi-node="${escape(r.node.node_id)}" data-parent="${escape(r.parent_id || '')}" style="--level:${r.depth}"><span class="topology-disclosure" data-dvbi-fold="${escape(r.node.node_id)}">${r.has_children?(r.expanded?'▾':'▸'):'·'}</span><span class="topology-object"><strong>${escape(r.node.label)}</strong><small title="${escape(workbench.topologyIdentityDetails(r.node))}">${escape(workbench.dvbiIdentity(r.node))}</small></span><span class="topology-state">${escape(workbench.topologyStatus(r.node))}</span></div>`).join('') || '<div class="empty"><p>No matching semantic objects. Raw XML remains available from the document explorer.</p></div>';
    if(snapshot.page?.has_more)list.insertAdjacentHTML('beforeend',`<button class="btn" id="dvbi-more" ${state.loading || locked()?'disabled':''}>Load next objects (${snapshot.nodes.length} / ${snapshot.page.total})</button>`);
    if(state.metadata && !state.snapshot)list.insertAdjacentHTML('beforeend',`<button class="btn" id="dvbi-retry" ${state.loading || locked()?'disabled':''}>Retry document query</button>`);
    q('#dvbi-more')?.addEventListener('click',()=>loadPage(true));q('#dvbi-retry')?.addEventListener('click',()=>loadPage(false));
    list.querySelectorAll('[data-dvbi-branch-more]').forEach(b=>b.onclick=()=>{const key=b.dataset.dvbiBranchMore;state.limits[key]=(state.limits[key] || 100)+100;renderRows();});
    const items=[...list.querySelectorAll('[data-dvbi-node]')],focus=id=>{const el=items.find(b=>b.dataset.dvbiNode===id);if(el){state.focused=id;items.forEach(b=>b.tabIndex=b===el?0:-1);el.focus({preventScroll:true});el.scrollIntoView({block:'nearest'});}},fold=(id,value)=>{state.expanded[id]=value;renderRows();};
    items.forEach(el=>{
      const id=el.dataset.dvbiNode;
      el.onfocus=()=>{state.focused=id;items.forEach(b=>b.tabIndex=b===el?0:-1);};
      el.onclick=event=>{state.focused=id;if(event.target.closest('[data-dvbi-fold]') && el.hasAttribute('aria-expanded')){fold(id,el.getAttribute('aria-expanded')!=='true');return;}select(id);};
      el.onkeydown=event=>{const i=items.indexOf(el),branch=el.hasAttribute('aria-expanded'),open=el.getAttribute('aria-expanded')==='true';if(['ArrowUp','ArrowDown','ArrowLeft','ArrowRight','Home','End','Enter',' '].includes(event.key))event.preventDefault();
        if(event.key==='ArrowDown' || event.key==='ArrowUp')focus(items[Math.max(0,Math.min(items.length-1,i+(event.key==='ArrowDown'?1:-1)))].dataset.dvbiNode);
        else if(event.key==='Home' || event.key==='End')focus(items[event.key==='Home'?0:items.length-1].dataset.dvbiNode);
        else if(event.key==='ArrowRight' && branch){if(!open)fold(id,true);else focus(items[i+1]?.dataset.dvbiNode);}
        else if(event.key==='ArrowLeft'){if(branch && open)fold(id,false);else focus(el.dataset.parent);}
        else if(event.key==='Enter' || event.key===' ')select(id);
      };
    });list.scrollTop=scroll;if(hadFocus)focus(state.focused);
  }
  function select(id) {++state.inspectEpoch;state.inspectLoading=false;state.selected=id;state.ref=null;state.detail=null;state.resolution=null;state.inspectError='';state.history=[];state.sourceLimit=100;renderDocument();renderRows();renderInspector();}
  function remember() {state.history.push({detail:state.detail,ref:state.ref,resolution:state.resolution,view:state.view,scroll:q('#dvbi-inspector').scrollTop,focus:document.activeElement.id});if(state.history.length>100)state.history.shift();}
  async function inspectElement(id,ref,params={},save=true) {
    if(locked() || !state.metadata)return;
    if(ref && (ref.document_revision!==state.metadata.document_revision || ref.source_sha256!==state.metadata.source.sha256)){state.inspectError='Source belongs to a different document revision or hash.';renderInspector();return;}
    if(save)remember();const epoch=++state.inspectEpoch,documentEpoch=state.epoch,metadata=state.metadata;state.lastInspect={id,ref,params};state.ref=ref;state.resolution=null;state.inspectLoading=true;state.inspectError='';state.detail=null;renderInspector();
    try {
      const d=await call('inspect_dvbi',{document_revision:metadata.document_revision,element_id:id,source_offset:ref?.original_byte_offset ?? 0,source_limit:4096,child_limit:100,...params});
      if(epoch!==state.inspectEpoch || documentEpoch!==state.epoch)return;
      const error=workbench.validateDvbi(d,metadata.document_revision,metadata.source.sha256);if(error)throw new Error(error);
      if(d.element?.element_id!==id)throw new Error('XML element identity does not match the requested source.');
      const resolution=workbench.resolveDvbiEvidence(ref || d.element.evidence,d);if(resolution.status==='mismatch')throw new Error(resolution.message);
      state.detail=d;state.resolution=resolution;
    } catch(error){if(epoch===state.inspectEpoch)state.inspectError=String(error);}
    finally{if(epoch===state.inspectEpoch && documentEpoch===state.epoch){state.inspectLoading=false;renderDocument();renderInspector();update();}}
  }
  function renderInspector() {
    const panel=q('#dvbi-inspector'),n=node(),d=state.detail,e=d?.element,ref=state.ref;
    let body='';
    if(state.inspectLoading || state.inspectError)body=`<div class="empty"><h3>${state.inspectLoading?'Loading XML evidence…':'Unable to inspect XML evidence'}</h3><p role="status">${escape(state.inspectError)}</p>${state.inspectError && state.lastInspect && !locked()?'<button class="btn" id="dvbi-retry-inspect">Retry source inspection</button>':''}</div>`;
    else if(d) {
      const source=d.original_source || {},resolution=state.resolution;
      let evidence='';
      if(state.view==='structure')evidence=`<div class="dvbi-element"><h3>${escape(e.qualified_name)}</h3><p class="meta">${escape(e.namespace)}<br>${escape(e.path)}<br>Line ${e.line}, column ${e.column} · element start</p><p id="dvbi-locator-status" role="status">${escape(resolution.message)}</p><dl class="topology-definition">${(e.attributes || []).map((a,i)=>`<div ${resolution.precision==='attribute' && resolution.attribute_index===i?'data-dvbi-highlight="attribute"':''}><dt title="${escape('Q{'+a.namespace+'}'+a.local_name)}">${escape(a.qualified_name)}</dt><dd>${escape(a.value)}</dd></div>`).join('')}</dl><h3>XML-normalized direct text</h3><pre>${escape(e.text)}</pre><p class="meta">${escape(e.text_encoding)}</p><p>Navigate children and parent in the document explorer.</p></div>`;
      else if(state.view==='text')evidence=`<p class="meta">Original UTF-8 file bytes decoded by the engine, not XML reserialization. HTML display normalizes line breaks; Hex retains exact original bytes. Byte page ${source.text_offset}–${(source.text_offset || 0)+(source.text_length || 0)}; starts on line ${source.text_start_line}. Highlight marks the element start only.</p><pre class="evidence" tabindex="0">${Number.isSafeInteger(source.element_start_character) && source.element_start_character>=0?escape(source.text.slice(0,source.element_start_character))+'<mark class="source-byte" data-dvbi-highlight="element-start">'+escape(source.text.slice(source.element_start_character,source.element_start_character+1))+'</mark>'+escape(source.text.slice(source.element_start_character+1)):escape(source.text)}</pre>`;
      else if(state.view==='hex')evidence=`<p class="meta">Original file byte page ${source.offset}–${source.offset+source.length} / ${source.total}. This is not an element or attribute byte span.</p><pre class="evidence" tabindex="0">${escape((source.data || '').match(/.{1,32}/g)?.map((line,i)=>(source.offset+i*16).toString(16).toUpperCase().padStart(8,'0')+'  '+line.match(/.{1,2}/g).join(' ')).join('\n') || '')}</pre>`;
      else evidence=`<pre class="evidence" tabindex="0">${json({element:e,reference:ref,resolution,source:{...source,data:undefined,text:undefined}})}</pre>`;
      body=`<h2 class="dvbi-heading">${escape(e.qualified_name)}</h2><p class="meta">Document revision ${d.document_revision} · ${escape(d.source.sha256)}</p><div class="view-tabs" role="group" aria-label="XML evidence view">${[['structure','Structure'],['text','Original XML'],['hex','Original hex'],['metadata','Metadata']].map(([key,label])=>`<button data-dvbi-view="${key}" aria-pressed="${state.view===key}" class="${state.view===key?'active':''}">${label}</button>`).join('')}</div>${evidence}${['text','hex'].includes(state.view)?`<div class="metadata-query"><button class="btn" id="dvbi-source-prev" ${source.offset>0?'':'disabled'}>Previous bytes</button><button class="btn" id="dvbi-source-next" ${source.has_more?'':'disabled'}>Next bytes</button><button class="btn" id="dvbi-element-start" ${Number.isSafeInteger(e.original_byte_offset)?'':'disabled'}>Element start</button></div>`:''}`;
    } else if(n) {
      const refs=workbench.dvbiEvidence(n);
      body=`<h2 class="dvbi-heading">${escape(n.label)}</h2><p class="meta">${escape(n.object_type)} · ${escape(workbench.topologyStatus(n))}</p><div class="dvbi-object"><h3>Identity</h3><pre>${json(n.identity)}</pre><h3>Source references (${refs.length})</h3>${refs.slice(0,state.sourceLimit).map((r,i)=>`<button class="btn topology-source" id="dvbi-ref-${i}" data-dvbi-ref="${i}" ${locked()?'disabled':''}><strong>${escape(r.precision)} · ${escape(r.attribute_name || r.element_id)}</strong><span>${escape(r.path)}</span><span>Line ${r.line}, column ${r.column} · containing element start</span></button>`).join('') || '<p>No source references supplied.</p>'}${refs.length>state.sourceLimit?`<button class="btn" id="dvbi-more-refs">Show next source references (${state.sourceLimit} / ${refs.length})</button>`:''}<h3>Unknowns and conflicts</h3><pre>${json(n.unresolved_reasons || [])}</pre><details><summary>All announced attributes</summary><pre>${json(n.attributes)}</pre></details><p class="meta">Announced metadata does not establish reception, URL availability, a TS association or playable media.</p></div>`;
    } else body='<div class="empty"><h3>Select a service-list object</h3><p>Arrow keys move focus; Enter selects. Sources retain exact XML element, revision and hash identity.</p></div>';
    panel.innerHTML=`<div class="panel-title">XML EVIDENCE INSPECTOR</div>${state.history.length?'<div class="topology-actions"><button class="btn small" id="dvbi-back">← Back</button></div>':''}${body}`;
    q('#dvbi-retry-inspect')?.addEventListener('click',()=>{const last=state.lastInspect;inspectElement(last.id,last.ref,last.params,false);});
    q('#dvbi-back')?.addEventListener('click',()=>{const prev=state.history.pop();++state.inspectEpoch;state.inspectLoading=false;state.inspectError='';Object.assign(state,{detail:prev.detail,ref:prev.ref,resolution:prev.resolution,view:prev.view});renderDocument();renderInspector();panel.scrollTop=prev.scroll;document.getElementById(prev.focus)?.focus({preventScroll:true});});
    panel.querySelectorAll('[data-dvbi-ref]').forEach(b=>b.onclick=()=>{const r=workbench.dvbiEvidence(node())[Number(b.dataset.dvbiRef)];state.view='structure';inspectElement(r.element_id,r);});
    q('#dvbi-more-refs')?.addEventListener('click',()=>{state.sourceLimit+=100;const scroll=panel.scrollTop;renderInspector();panel.scrollTop=scroll;});
    panel.querySelectorAll('[data-dvbi-view]').forEach(b=>b.onclick=()=>{state.view=b.dataset.dvbiView;renderInspector();panel.querySelector('[data-dvbi-view="'+state.view+'"]').focus();});
    q('#dvbi-source-prev')?.addEventListener('click',()=>inspectElement(e.element_id,ref,{source_offset:Math.max(0,d.original_source.offset-4096)},false));
    q('#dvbi-source-next')?.addEventListener('click',()=>inspectElement(e.element_id,ref,{source_offset:d.original_source.next_offset},false));
    q('#dvbi-element-start')?.addEventListener('click',()=>inspectElement(e.element_id,ref,{source_offset:e.original_byte_offset},false));
  }
  function render(){renderDocument();renderRows();renderInspector();update();}
  q('#dvbi-import').onclick=importFile;q('#dvbi-source').onkeydown=e=>{if(e.key==='Enter')importFile();};
  q('#dvbi-browse').onclick=async()=>{try{const path=await invoke('plugin:dialog|open',{options:{multiple:false,directory:false,filters:[{name:'DVB-I XML',extensions:['xml']}]}});if(path)q('#dvbi-source').value=path;}catch(error){state.error=String(error);update();}};
  q('#dvbi-search').oninput=e=>{state.search=e.target.value;renderRows();};
  return {activate,update,importFile,getState:()=>({active:state.active,metadata:state.metadata,selected:state.selected,focused:state.focused,search:state.search,view:state.view,ref:state.ref,resolution:state.resolution,loading:state.loading,importing:state.importing,inspectLoading:state.inspectLoading,error:state.error,inspectError:state.inspectError,loaded_nodes:state.snapshot?.nodes.length || 0,page:state.snapshot?.page,return_depth:state.history.length}),getSnapshot:()=>state.snapshot,getDetail:()=>state.detail};
}
