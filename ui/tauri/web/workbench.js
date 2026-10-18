// Shared presentation contract. No DOM, Qt, parser or filesystem dependencies.
var workbench = {
  hex: function(n, width) { return '0x' + Number(n || 0).toString(16).padStart(width || 4, '0'); },
  matches: function(row, query) {
    var values = JSON.stringify(row).toLowerCase();
    Object.keys(row).forEach(function(k) { if (typeof row[k] === 'number') values += ' ' + workbench.hex(row[k]) + ' ' + workbench.hex(row[k], 2); });
    return query.toLowerCase().trim().split(/\s+/).filter(Boolean).every(function(term) { return values.indexOf(term) >= 0; });
  },
  scope: function(row, pid, name) {
    return (pid == null || pid < 0 || row.pid === pid) && (!name || (name === 'Private / other' ? !row.name || row.name === name || row.name.indexOf('Unknown / private (') === 0 : row.name === name));
  },
  sort: function(a,b) { return a.pid-b.pid || a.table_id-b.table_id || a.extension-b.extension || a.version-b.version || Number(b.current)-Number(a.current) || a.section-b.section || String(a.id).localeCompare(String(b.id)); },
  tables: function(state, pid, name, bad, query) {
    var all = (state.tables || []).filter(function(r) { return workbench.scope(r,pid,name); }).sort(workbench.sort);
    var groups = (state.table_groups || []).filter(function(g) {
      return workbench.scope(g,pid,name) && (!query.trim() || workbench.matches(g,query) || all.some(function(r) { return g.section_ids.indexOf(r.id)>=0 && workbench.matches(r,query); }));
    }).sort(workbench.sort);
    var ids = {};
    groups.forEach(function(g) { g.section_ids.forEach(function(id) { ids[id]=true; }); });
    var matching = all.filter(function(r) { return ids[r.id]; });
    var sections = matching.filter(function(r) { return bad || r.crc.status !== 'invalid'; });
    return {groups:groups, sections:sections, hidden:matching.length-sections.length,
      count_text:groups.length+' tables · '+sections.length+' sections'+(matching.length>sections.length ? ' · '+(matching.length-sections.length)+' bad CRC hidden' : '')};
  },
  representative: function(group, sections) {
    return sections.find(function(r) {return group.section_ids.indexOf(r.id)>=0 && (group.selected_section_ids || []).indexOf(r.id)>=0;}) || sections.find(function(r) { return group.section_ids.indexOf(r.id)>=0; });
  },
  groupText: function(g) {
    return 'Ext '+workbench.hex(g.extension)+' · v'+g.version+' · '+(g.current?'current':'next')+' · '+g.validity+' · observed '+(g.observed_section_numbers || []).length+'/'+(Number(g.last_section)+1)+' · missing '+((g.missing_section_numbers || []).join(', ') || 'none')+' · selected '+(g.selected_complete?'complete':'incomplete');
  },
  history: function(state, detail, all) {
    return (state.table_history || []).filter(function(h) { return all || (detail && h.pid===detail.pid && h.table_id===detail.table_id && h.extension===detail.extension); });
  },
  historyText: function(h) {
    return h.name+' · PID '+workbench.hex(h.pid)+' · TID '+workbench.hex(h.table_id,2)+' · Ext '+workbench.hex(h.extension)+(h.version == null?' · unversioned':' · v'+h.version)+' · §'+h.section+' · '+(h.current?'current':'next')+(h.valid?'':' · INVALID')+' @ '+h.at_packet;
  }
};


workbench.value = function(key, value) {
  if(value == null) return '—';
  if(typeof value !== 'number') return String(value);
  if(/private_data_specifier|pds|crc/i.test(key)) return workbench.hex(value,8)+' ('+value+')';
  if(/tag|table_id|^type$|stream_type|service_type/.test(key)) return workbench.hex(value,2)+' ('+value+')';
  if(/pid|_id$|^id$/.test(key)) return workbench.hex(value)+' ('+value+')';
  return String(value);
};
workbench.objectNode = function(id, label, value) {
  if(value !== null && typeof value === 'object') {
    var list=Array.isArray(value) || (Number.isInteger(value.length) && typeof value.forEach==='function');
    return {id:id,label:label,value:list?value.length+' entries':'',children:Object.keys(value).map(function(k) {return workbench.objectNode(k,list?'['+k+']':k,value[k]);})};
  }
  return {id:id,label:label,value:workbench.value(label,value),kind:typeof value};
};
workbench.sdkNode = function(node, sid) {
  var children=[];
  var attributes=Object.keys(node.attributes || {}).map(function(k) {var v=node.attributes[k];return {id:k,label:k,value:String(v),kind:/^(?:0x[0-9a-f]+|[0-9]+)$/i.test(String(v))?'number':'string'};});
  if(attributes.length) children.push({id:'attributes',label:'Attributes',children:attributes});
  (node.children || []).forEach(function(child,i) {
    if(sid>=0 && child.name==='service' && Number((child.attributes || {}).service_id)!==sid) return;
    var n=workbench.sdkNode(child,sid);n.id='child'+i;children.push(n);
  });
  if(node.text) children.push({id:'text',label:'Text',value:node.text,kind:'string'});
  return {id:'table',label:node.name,kind:'native',children:children};
};
workbench.descriptorNode = function(d) {
  var meta=Object.assign({},d);delete meta.raw;delete meta.native;delete meta.fields;delete meta.extension;
  meta.descriptor_tag=meta.tag;delete meta.tag;
  var children=[workbench.objectNode('meta','Descriptor header',meta)];
  if(Object.keys(d.fields || {}).length) children.push(workbench.objectNode('fields','Application decoded fields',d.fields));
  if(d.native) {var n=workbench.sdkNode(d.native,-1);n.id='native';children.push(n);}
  if(d.extension) children.push(workbench.objectNode('extension','Extension',d.extension));
  children.push({id:'raw',label:'Raw bytes',value:d.raw || '',kind:'string'});
  return {id:String(d.offset),label:(d.native_decoded || d.extension?'◆ ':'? ')+(d.name || 'opaque_descriptor')+' · '+workbench.hex(d.tag,2),tone:d.malformed || (d.decode_status && d.decode_status!=='decoded')?'bad':d.extension?'private':'',value:d.length+' B @ '+d.offset,children:children};
};
workbench.structure = function(detail, scope, sid) {
  var header={};
  ['pid','table_id','extension','version','current','section','last_section','bytes','valid','crc','detected_standards'].forEach(function(k) {if(detail[k]!==undefined) header[k]=detail[k];});
  var children=[workbench.objectNode('header','Section header',header)];
  var sdk=scope==='section'?detail.section_native_table:(detail.merged || {}).native_table;
  children.push({id:'native',label:'TSDuck decoded structure · '+(scope==='section'?'selected section':'merged table'),value:sdk?'SDK evidence':scope==='section'?'No standalone SDK structure; section-local display in Decoded':'No complete selected generation; no merged decode',children:sdk?[workbench.sdkNode(sdk,sid)]:[]});
  if(scope==='merged' && (detail.native_table_sources || []).length) children.push(workbench.objectNode('assembly',detail.merged && detail.merged.complete?'Merged table source sections':'Candidate sections · no completed merge',detail.native_table_sources));
  children.push(workbench.objectNode('fields','Application decoded fields',detail.fields || {}));
  var services=(detail.services || []).filter(function(s){return sid<0 || s.id===sid;});
  if(services.length) children.push({id:'services',label:'Services',children:services.map(function(s) {return {id:String(s.id),label:s.name || 'Service',value:'SID '+workbench.hex(s.id),children:[workbench.objectNode('fields','Service fields',s),{id:'descriptors',label:'Descriptors',children:(detail.descriptors || []).filter(function(d){return d.service_id===s.id;}).map(workbench.descriptorNode)}]};})});
  if((detail.events || []).length) children.push(workbench.objectNode('events','Events',detail.events));
  var descriptors=(detail.descriptors || []).filter(function(d){return !(detail.services || []).some(function(s){return s.id===d.service_id;});});
  if(descriptors.length) children.push({id:'descriptors',label:(detail.events || []).length?'Section descriptors (event ownership unavailable)':'Descriptors',children:descriptors.map(workbench.descriptorNode)});
  if(detail.distribution) children.push(workbench.objectNode('arrivals','Arrival distribution · packet positions',detail.distribution));
  if((detail.descriptors || []).length) children.push(workbench.objectNode('audit','Descriptor decode audit · selected section',{
    scope:'Application-indexed descriptor loops; native-only loops may contain additional descriptors',
    native_decoded:detail.descriptors.filter(function(d){return d.native_decoded;}).length,
    extension_decoded:detail.descriptors.filter(function(d){return !!d.extension;}).length,
    unresolved:detail.descriptors.filter(function(d){return !d.native_decoded && !d.extension;}).length,
    warnings:detail.descriptors.filter(function(d){return d.malformed || d.native_decode_warning;})}));
  if((detail.issues || []).length) children.push(workbench.objectNode('issues','Validation issues',detail.issues));
  children.push(workbench.objectNode('evidence','Source evidence',{first_packet:detail.first_packet,last_packet:detail.last_packet,first_file_offset:detail.first_file_offset,offset_note:detail.offset_note,native_table_at_packet:detail.native_table_at_packet,inspection_scope:detail.inspection_scope,identity:detail.identity,occurrences:(detail.occurrences || []).slice(0,500),display_note:(detail.occurrences || []).length>500?'First 500 occurrences; full list available through Agent API':'All indexed occurrences'}));
  return {id:'section',label:detail.name+' section',value:'v'+detail.version+' · '+(detail.valid?'valid':'invalid'),children:children};
};
workbench.defaultOpen = function(path) {
  return path==='section' || /^section\/(native|fields|services|descriptors)(?:$|\/)/.test(path) && !/\/(meta|attributes)$/.test(path);
};
