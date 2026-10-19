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
  if((detail.evidence_anchors || []).length) children.splice(1,0,{id:'anchors',label:'Source evidence anchors · exact section',children:detail.evidence_anchors.map(function(anchor,i){return {id:String(i),label:anchor.label || anchor.display_path || anchor.field_id || anchor.container_id || 'Source anchor',value:anchor.value==null?(anchor.byte_range?'Section bytes '+anchor.byte_range.offset+'–'+(anchor.byte_range.offset+anchor.byte_range.length-1):'No byte range supplied'):workbench.value(anchor.label || '',anchor.value),children:[workbench.objectNode('locator','Engine source locator',anchor)]};})});
  return {id:'section',label:detail.name+' section',value:'v'+detail.version+' · '+(detail.valid?'valid':'invalid'),children:children};
};
workbench.defaultOpen = function(path) {
  return path==='section' || /^section\/(native|fields|services|descriptors)(?:$|\/)/.test(path) && !/\/(meta|attributes)$/.test(path);
};

// Topology is an engine-owned semantic projection. These helpers only format
// returned objects and compare opaque evidence identities; they never join
// protocol fields, parse XML or infer standards from names/table identifiers.
workbench.topologyStatus = function(node) {
  var labels={observed_here:'Observed here',announced_only:'Announced only',incomplete:'Incomplete',conflict:'Conflict',unresolved:'Unresolved',resolved:'Resolved'};
  var status=node.observation_status || node.resolution_status || 'unresolved',resolution=node.resolution_status;
  var text=labels[status] || String(status);
  if(resolution && resolution!=='resolved' && resolution!==status) text=(labels[resolution] || String(resolution))+' · '+text;
  return text;
};
workbench.topologyIdentity = function(node) {
  var identity=node.identity || {},parts=[];
  var fields=[['network_id','NID'],['original_network_id','ONID'],['transport_stream_id','TSID'],['service_id','SID'],['bouquet_id','BID'],['program_number','Program'],['pid','PID'],['table_id','TID'],['atsc_source_id','Source ID'],['component_tag','Tag']];
  fields.forEach(function(field){var value=identity[field[0]];if(value!=null)parts.push(field[1]+' '+(typeof value==='number'?workbench.hex(value,field[0]==='table_id' || field[0]==='component_tag'?2:4):String(value)));});
  var channel=identity.channel_number;
  if(channel && channel.format==='two_part' && channel.major!=null && channel.minor!=null)parts.unshift('CH '+channel.major+'.'+channel.minor);
  else if(channel && channel.format==='one_part' && channel.one_part!=null)parts.unshift('CH '+channel.one_part);
  // Opaque graph links and unrecognized identities remain in the full inspector,
  // not the narrow row. This is formatting, not a new protocol identity join.
  return parts.join(' · ');
};
workbench.topologyFieldLabel = function(key) {
  var labels={network_id:'Network ID (NID)',original_network_id:'Original network ID (ONID)',transport_stream_id:'Transport stream ID (TSID)',service_id:'Service ID (SID)',bouquet_id:'Bouquet ID (BID)',program_number:'MPEG program number',pid:'Packet identifier (PID)',table_id:'Table ID (TID)',atsc_source_id:'ATSC programme source ID',component_tag:'Component tag',channel_number:'Virtual channel number',program_node_id:'Program object reference',vct_context:'VCT context reference'};
  return labels[key] || key.replace(/_/g,' ');
};
workbench.topologyIdentityDetails = function(node) {
  return Object.keys(node.identity || {}).map(function(key){var value=node.identity[key];return workbench.topologyFieldLabel(key)+': '+(value && typeof value==='object'?JSON.stringify(value):workbench.value(key,value));}).join('\n');
};
workbench.topologySearch = function(node, query) {
  var values=[];
  function visit(value,key) {
    if(value && typeof value==='object') Object.keys(value).forEach(function(k){visit(value[k],k);});
    else if(value!=null) values.push(String(value),typeof value==='number'?workbench.hex(value):'',typeof value==='number'?workbench.hex(value,2):'');
  }
  visit({label:node.label,type:node.object_type,identity:node.identity,attributes:node.attributes,status:workbench.topologyStatus(node)},'');
  var text=values.join(' ').toLowerCase();
  return String(query || '').trim().toLowerCase().split(/\s+/).filter(Boolean).every(function(term){return text.indexOf(term)>=0;});
};
workbench.topologyNodes = function(snapshot) {
  var nodes=[],seen={};
  (snapshot.context_nodes || []).concat(snapshot.nodes || []).forEach(function(node){if(!seen[node.node_id]) {seen[node.node_id]=true;nodes.push(node);}});
  return nodes;
};
workbench.validateTopology = function(snapshot,revision,cutoff) {
  if(!snapshot || snapshot.schema_version!==1 || !Array.isArray(snapshot.nodes) || !Array.isArray(snapshot.projections)) return 'Unsupported or incomplete topology response.';
  if(snapshot.analysis_revision!==revision) return 'Topology belongs to a different analysis revision.';
  if(snapshot.at_packet!==cutoff) return 'Topology cutoff does not match the requested snapshot.';
  var seen={};
  for(var i=0;i<snapshot.nodes.length;i++) {var n=snapshot.nodes[i];if(!n || typeof n.node_id!=='string' || !n.node_id || seen[n.node_id]) return 'Topology contains an invalid or repeated object identity.';seen[n.node_id]=true;}
  return '';
};
workbench.mergeTopology = function(current,page) {
  if(!current) return page;
  if(current.analysis_revision!==page.analysis_revision || current.at_packet!==page.at_packet || current.interpretation_profile!==page.interpretation_profile) throw new Error('Topology page context changed. Reload this snapshot.');
  var result=Object.assign({},page),nodes={},edges={};
  workbench.topologyNodes(current).concat(workbench.topologyNodes(page)).forEach(function(n){nodes[n.node_id]=n;});
  (current.edges || []).concat(page.edges || []).forEach(function(e){edges[e.edge_id]=e;});
  result.nodes=Object.keys(nodes).map(function(id){return nodes[id];});result.context_nodes=[];
  result.edges=Object.keys(edges).map(function(id){return edges[id];});
  return result;
};
workbench.topologyRows = function(snapshot,family,query,expanded,limits) {
  var nodes=workbench.topologyNodes(snapshot || {}),byId={},children={},matches={},include={},rows=[],hidden=0;
  nodes=nodes.filter(function(n){return !family || family==='all' || n.family===family;});
  nodes.forEach(function(n){byId[n.node_id]=n;children[n.node_id]=[];});
  var roots=[];
  nodes.forEach(function(n){if(n.parent_id && byId[n.parent_id]) children[n.parent_id].push(n.node_id);else roots.push(n.node_id);});
  var searching=!!String(query || '').trim();
  nodes.forEach(function(n){matches[n.node_id]=!searching || workbench.topologySearch(n,query);if(matches[n.node_id]) {var id=n.node_id,visited={};while(id && byId[id] && !visited[id]) {visited[id]=true;include[id]=true;id=byId[id].parent_id;}}});
  var seen={};
  function visit(ids,depth,parent,ancestorMatch) {
    var available=ids.filter(function(id){return !searching || include[id] || ancestorMatch;});
    var limit=limits && limits[parent || '$roots'] || 100;
    available.slice(0,limit).forEach(function(id){
      if(seen[id]) return;seen[id]=true;
      var node=byId[id],branch=children[id].length>0,open=searching || !!(expanded && expanded[id]);
      rows.push({node:node,depth:depth,parent_id:parent,has_children:branch,expanded:branch && open,match:matches[id],child_count:children[id].length});
      if(open) visit(children[id],depth+1,id,ancestorMatch || (searching && matches[id]));
    });
    if(available.length>limit) {hidden+=available.length-limit;rows.push({more:true,parent_id:parent,depth:depth,remaining:available.length-limit});}
  }
  visit(roots,1,null,false);
  return {rows:rows,total:nodes.length,matched:nodes.filter(function(n){return matches[n.node_id];}).length,hidden:hidden};
};
workbench.topologyEvidence = function(node,edges) {
  var refs=[],seen={};
  function add(ref,edge) {
    var key=JSON.stringify([ref.section_id,ref.assertion_key,ref.role,ref.locator,edge ? edge.edge_id : '']);
    if(seen[key])return;seen[key]=true;
    refs.push({ref:ref,edge_id:edge ? edge.edge_id : null,relation:edge ? edge.relation : null,target:edge ? (edge.from===node.node_id?edge.to:edge.from) : null});
  }
  (node.evidence || []).forEach(function(ref){add(ref,null);});
  (edges || []).filter(function(e){return e.from===node.node_id || e.to===node.node_id;}).forEach(function(e){(e.evidence || []).forEach(function(ref){add(ref,e);});});
  return refs;
};
workbench.resolveTopologyEvidence = function(ref,detail) {
  function fail(message){return {status:'mismatch',precision:'none',message:message,anchor_index:-1,byte_range:null};}
  if(!ref || !detail || detail.id!==ref.section_id) return fail('Returned section does not match the requested evidence.');
  if(detail.analysis_revision!==ref.analysis_revision) return fail('Evidence belongs to a different analysis revision.');
  if(detail.native_table_at_packet!==ref.at_packet) return fail('Evidence cutoff does not match the topology snapshot.');
  var identity=ref.table_identity || {},keys={pid:'pid',table_id:'table_id',extension:'extension',version:'version',section_number:'section',current:'current'};
  for(var key in keys) if(identity[key]!=null && identity[key]!==detail[keys[key]]) return fail('Returned table identity does not match '+key+'.');
  var locator=ref.locator || {},anchors=detail.evidence_anchors || [],index=-1,precision='section';
  if(locator.precision==='field' && locator.field_id) {index=anchors.findIndex(function(a){return a.field_id===locator.field_id && a.precision==='field' && a.resolution_status==='resolved';});if(index>=0)precision='field';}
  if(index<0 && locator.container_id) {index=anchors.findIndex(function(a){return a.container_id===locator.container_id && a.precision==='container' && a.resolution_status==='resolved';});if(index>=0)precision='container';}
  var range=index>=0?anchors[index].byte_range:null;
  if(range && (range.offset_scope!=='section_bytes' || !Number.isSafeInteger(range.offset) || !Number.isSafeInteger(range.length) || range.offset<0 || range.length<1 || range.offset+range.length>String(detail.raw_hex || '').length/2)) range=null;
  if(range && precision===locator.precision && locator.byte_range && (range.offset!==locator.byte_range.offset || range.length!==locator.byte_range.length || range.offset_scope!==locator.byte_range.offset_scope)) range=null;
  return {status:index>=0?'resolved':'fallback',precision:precision,anchor_index:index,path:index>=0?'section/anchors/'+index:'section',byte_range:range,
    message:precision==='field'?'Exact source field located'+(range?' · section byte range available.':' · byte range not provided.'):
      precision==='container'?'Located the source container; exact field position is unavailable.':'Located the exact section; a supported field/container anchor was not provided.'};
};
