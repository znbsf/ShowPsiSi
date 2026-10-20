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
    if(g.versioning_supported===false) return workbench.wireHeaderText(g)+' · '+g.validity+' · '+(g.section_ids || []).length+' exact section observations · map assembly unsupported';
    return 'Ext '+workbench.hex(g.extension)+' · v'+g.version+' · '+(g.current?'current':'next')+' · '+g.validity+' · observed '+(g.observed_section_numbers || []).length+'/'+(Number(g.last_section)+1)+' · missing '+((g.missing_section_numbers || []).join(', ') || 'none')+' · selected '+(g.selected_complete?'complete':'incomplete');
  },
  history: function(state, detail, all) {
    return (state.table_history || []).filter(function(h) { return all || (detail && h.pid===detail.pid && h.table_id===detail.table_id && h.extension===detail.extension); });
  },
  historyText: function(h) {
    if(h.versioning_supported===false || h.extension===null || h.section===null) return h.name+' · PID '+workbench.hex(h.pid)+' · TID '+workbench.hex(h.table_id,2)+' · '+workbench.wireHeaderText(h)+(h.valid?'':' · INVALID')+' @ '+h.at_packet;
    return h.name+' · PID '+workbench.hex(h.pid)+' · TID '+workbench.hex(h.table_id,2)+' · Ext '+workbench.hex(h.extension)+(h.version == null?' · unversioned':' · v'+h.version)+' · §'+h.section+' · '+(h.current?'current':'next')+(h.valid?'':' · INVALID')+' @ '+h.at_packet;
  }
};

// Scan intent is captured by each frontend when the request is sent. PID order
// and duplicate entries do not change the monitored set; invalid input stays distinct.
workbench.scanOptionsKey = function(options) {
  var pids=options.extra_pids;
  return JSON.stringify([options.standards,options.default_charset.trim(),pids===null?null:pids.filter(function(p,i,all){return all.indexOf(p)===i;}).sort(function(a,b){return a-b;})]);
};
workbench.scanOptionsSummary = function(options) {
  var parts=[],pids=options.extra_pids;
  if(options.default_charset.trim())parts.push('charset '+options.default_charset.trim());
  if(pids===null)parts.push('invalid PIDs');
  else {
    pids=pids.filter(function(p,i,all){return all.indexOf(p)===i;});
    pids.slice(0,2).forEach(function(p){parts.push('+PID '+workbench.hex(p));});
    if(pids.length>2)parts.push('+'+(pids.length-2)+' more PIDs');
  }
  return parts.join(' · ');
};
workbench.issueCounts = function(issues) {
  var counts={total:issues.length,errors:0,warnings:0,other:0,hasSeverity:false};
  issues.forEach(function(issue) {
    var severity=typeof issue.severity==='string'?issue.severity.toLowerCase().trim():'';
    if(severity)counts.hasSeverity=true;
    if(severity==='error')counts.errors++;
    else if(severity==='warning')counts.warnings++;
    else counts.other++;
  });
  return counts;
};

workbench.identifierNamespaces = [
  {value:'original_network_id',label:'Original network ID',help:'Original network identifier'},
  {value:'network_id',label:'Network ID',help:'Network identifier'},
  {value:'bouquet_id',label:'Bouquet ID',help:'Bouquet identifier'},
  {value:'ca_system_id',label:'CA system ID (conditional access)',help:'Conditional access system identifier'},
  {value:'private_data_specifier',label:'Private data specifier',help:'Private descriptor namespace'},
  {value:'registration_id',label:'Registration ID',help:'Registered format identifier'},
  {value:'data_broadcast_id',label:'Data broadcast ID',help:'Data broadcast identifier'},
  {value:'platform_id',label:'Platform ID',help:'Platform identifier'},
  {value:'oui',label:'OUI (organizationally unique identifier)',help:'Organizationally unique identifier'}
];
workbench.lookupLabel = function(key) {
  var acronyms={id:'ID',ids:'IDs',sdk:'SDK',url:'URL',oui:'OUI',ca:'CA',geo:'GEO',hz:'Hz',fec:'FEC',pid:'PID',onid:'ONID',tsid:'TSID'};
  var words=String(key).replace(/([a-z])([A-Z])/g,'$1 $2').replace(/_/g,' ').split(' ');
  return words.map(function(word,i){return acronyms[word.toLowerCase()] || (i===0?word.charAt(0).toUpperCase()+word.slice(1):word);}).join(' ');
};
// Flatten returned JSON without hiding false, null, empty collections or unknown
// flags. Source columns inherit only explicit provenance, never inferred meaning.
workbench.lookupResult = function(result) {
  var rows=[],acronyms={id:'ID: identifier',sdk:'SDK: Software Development Kit',url:'URL: Uniform Resource Locator',oui:'OUI: organizationally unique identifier',ca:'CA: conditional access',geo:'GEO: geostationary Earth orbit',hz:'Hz: hertz',fec:'FEC: forward error correction',pid:'PID: Packet Identifier',onid:'ONID: Original Network Identifier',tsid:'TSID: Transport Stream Identifier'};
  function text(value) { return typeof value==='string'?(value || '""'):JSON.stringify(value); }
  function provenance(value) {
    if(!value || typeof value!=='object')return text(value);
    var identity=value.publisher || value.file || value.path || value.kind || value.section_id || value.url;
    return identity?[identity,value.reviewed_at || value.sdk_version || value.revision].filter(Boolean).join(' · '):JSON.stringify(value);
  }
  function visit(value,path,label,source,sourceTip) {
    if(value!==null && typeof value==='object' && Object.keys(value).length) {
      var keys=Object.keys(value),origins=keys.filter(function(k){return /^(source|sources|provenance|wire_source|catalog)$/.test(k);});
      if(origins.length) {
        source=origins.map(function(k){return provenance(value[k]);}).join('\n');
        sourceTip=origins.map(function(k){return k+': '+JSON.stringify(value[k],null,2);}).join('\n');
      }
      keys.forEach(function(k){
        var array=Array.isArray(value),raw=array?'['+k+']':k,readable=array?raw:workbench.lookupLabel(k);
        visit(value[k],path?(path+(array?'':'.')+raw):raw,label?(label+(array?' ':' › ')+readable):readable,source,sourceTip);
      });
    } else {
      var help=path.split(/[.\[\]_]+/).map(function(k){return acronyms[k.toLowerCase()];}).filter(function(x,i,all){return x && all.indexOf(x)===i;}).join(' · ');
      rows.push({key:path,label:label,help:help,value:text(value),source:source || '',sourceTip:sourceTip || ''});
    }
  }
  if(result!==null && result!==undefined)visit(result,'','', '', '');
  return {rows:rows,hasSource:rows.some(function(row){return !!row.source;})};
};

workbench.wireVersionText = function(row) { return row.versioning_supported===false || row.version===null?'version not carried':row.version===undefined?'version unavailable':'v'+row.version; };
workbench.wireExtensionText = function(row) { return row.versioning_supported===false || row.extension===null?'extension not carried':row.extension===undefined?'extension unavailable':'Ext '+workbench.hex(row.extension); };
workbench.wireCurrentText = function(row) { return row.versioning_supported===false || row.current===null?'current/next not carried':row.current===undefined?'current/next unavailable':row.current?'current':'next'; };
workbench.wireSectionText = function(row) {
  var section=row.section!==undefined?row.section:row.section_number;
  return row.versioning_supported===false || section===null?'section number not carried':section===undefined?'section number unavailable':'§'+section+(row.last_section!=null?'/'+row.last_section:'');
};
workbench.wireHeaderText = function(row) { return [workbench.wireExtensionText(row),workbench.wireVersionText(row),workbench.wireSectionText(row),workbench.wireCurrentText(row)].join(' · '); };

// Inspector disclosures are layout preferences, independent of selected evidence.
workbench.inspectorDisclosure = function(saved) {
  var state={identity:false,crc:false,arrival:false,sections:false,scope:false,warnings:false};
  Object.keys(state).forEach(function(key) { state[key]=!!saved && saved[key]===true; });
  return state;
};
workbench.inspectorSummary = function(row) {
  row=row || {};
  var status=(row.crc || {}).status,profile=typeof row.standards_context==='string'?row.standards_context:'';
  var profiles={auto:['Auto','Automatic standards detection'],dvb:['DVB','Digital Video Broadcasting'],atsc:['ATSC','Advanced Television Systems Committee'],
    isdb:['ISDB','Integrated Services Digital Broadcasting'],'isdb-japan':['ISDB-Japan','Integrated Services Digital Broadcasting · Japan'],
    'isdb-brazil':['ISDB-Brazil','Integrated Services Digital Broadcasting · Brazil'],dtmb:['DTMB','Digital Terrestrial Multimedia Broadcasting'],
    scte:['SCTE','Society of Cable Telecommunications Engineers'],'j94-system-b':['J.94-B','J.94 (2016) System B']};
  var selected=profiles[profile] || [profile || 'Profile unavailable',profile || 'Not reported by the engine'];
  return {version:workbench.wireVersionText(row),section:workbench.wireSectionText(row).replace('§','sec '),
    crc:'CRC '+(status==='valid'?'✓':status==='invalid'?'✕':status==='not_present'?'—':'?'),
    profile:selected[0],profileHelp:'Engine standards profile: '+selected[1]+'. This is the context used for this evidence; changing scan options requires a new analysis.'};
};
workbench.inspectorWarnings = function(detail, state) {
  detail=detail || {};state=state || {};
  var warnings=[],reported=detail.native_decode_warnings || [];
  if(typeof reported.forEach==='function')reported.forEach(function(warning) { if(typeof warning==='string' && warning)warnings.push(warning); });
  if(detail.native_xml_guarded)warnings.push('Guarded SDK XML: '+(detail.native_xml_guard_reason || 'ambiguous descriptor interpretation')+'. Original wire bytes remain authoritative in Hex bytes.');
  var truncated=(state.demux || {}).truncated_sections;
  if(truncated)warnings.push('Capture-wide demux: '+truncated+' truncated section(s). This count covers the whole capture, not only the selected section.');
  return warnings;
};


workbench.value = function(key, value) {
  if(value == null) return '—';
  if(typeof value !== 'number') return String(value);
  if(/private_data_specifier|pds|crc/i.test(key)) return workbench.hex(value,8)+' ('+value+')';
  if(/tag|table_id|^type$|stream_type|service_type/.test(key)) return workbench.hex(value,2)+' ('+value+')';
  if(/pid|_id$|^id$/.test(key)) return workbench.hex(value)+' ('+value+')';
  return String(value);
};
// Comparison presentation follows the engine's changed_fields. Nested rows show
// literal A/B values; array indices are positions, never inferred identities.
workbench.comparisonIsList = function(value) {return Array.isArray(value) || value!==null && typeof value==='object' && Number.isInteger(value.length) && typeof value.forEach==='function';};
workbench.comparisonValue = function(key, value, present) {
  if(present===false)return 'Not observed';
  if(value===null)return 'null';
  if(value===undefined)return 'Not provided';
  if(typeof value==='object')return workbench.comparisonIsList(value)?value.length+' items':Object.keys(value).length+' fields';
  if(typeof value==='number' && Number.isFinite(value)) {
    var width=0,name=String(key).toLowerCase();
    if(/^(private_data_specifier|pds|crc|crc32|registration_id)$/.test(name))width=8;
    else if(/^(oui|platform_id)$/.test(name))width=6;
    else if(/^(tag|descriptor_tag|tag_extension|table_id|type|stream_type|service_type|section|last_section|section_number|last_section_number|version|version_number)$/.test(name))width=2;
    else if(/(^|_)(pid|pids)$/.test(name) || /^(id|service_id|program_number|event_id|network_id|original_network_id|transport_stream_id|onid|ts_id|tsid|extension|bouquet_id|ca_system_id|data_broadcast_id|application_id)$/.test(name))width=4;
    var digits=Math.abs(value).toString(16).toUpperCase();
    if(Number.isInteger(value))digits=digits.padStart(width,'0');
    return (value<0?'-':'')+'0x'+digits+' ('+String(value)+')';
  }
  return typeof value==='string'?JSON.stringify(value):String(value);
};
workbench.comparisonHelp = function(key) {
  if(/^pmt_pid$/i.test(key))return 'PMT: Program Map Table · PID: Packet Identifier';
  if(/^pcr_pid$/i.test(key))return 'PCR: Program Clock Reference · PID: Packet Identifier';
  if(/pid/i.test(key))return 'PID: Packet Identifier';
  if(/lcn|logical_channel_number/i.test(key))return 'LCN: Logical Channel Number';
  if(/pds|private_data_specifier/i.test(key))return 'PDS: Private Data Specifier';
  if(/crc/i.test(key))return 'CRC: Cyclic Redundancy Check';
  if(/onid|original_network_id/i.test(key))return 'ONID: Original Network Identifier';
  if(/ts_?id|transport_stream_id/i.test(key))return 'TSID: Transport Stream Identifier';
  if(/service_id/i.test(key))return 'SID: Service Identifier';
  if(/^oui$/i.test(key))return 'OUI: Organizationally Unique Identifier';
  return key;
};
workbench.comparisonFields = function(change) {
  if(!change)return [];
  var before=change.before && change.before.value || {},after=change.after && change.after.value || {};
  function keys(a,b) {return Object.keys(a).concat(Object.keys(b).filter(function(k){return !Object.prototype.hasOwnProperty.call(a,k);}));}
  function object(value) {return value!==null && typeof value==='object';}
  function node(label,path,a,b,hasA,hasB,valueKey,root) {
    var children=[],role=!hasA?'added':!hasB?'removed':root?'changed':JSON.stringify(a)===JSON.stringify(b)?'context':'changed';
    if(object(a) || object(b)) {
      var left=object(a)?a:{},right=object(b)?b:{},list=workbench.comparisonIsList(a) || workbench.comparisonIsList(b);
      children=keys(left,right).map(function(k){return node(list?'['+k+']':k,path+'/'+k.replace(/~/g,'~0').replace(/\//g,'~1'),left[k],right[k],Object.prototype.hasOwnProperty.call(left,k),Object.prototype.hasOwnProperty.call(right,k),list?valueKey:k,false);});
    }
    return {path:path,label:label,key:valueKey,before:a,after:b,hasBefore:hasA,hasAfter:hasB,change:role,children:children};
  }
  var fields=change.change==='changed'?(change.changed_fields || []):keys(before,after);
  return fields.map(function(key){
    if(key==='payload' && change.kind==='tables')return {path:'/payload',label:'payload',key:key,change:'changed',note:'Raw section bytes changed · inspect A / B in Hex',children:[]};
    return node(key,'/'+key.replace(/~/g,'~0').replace(/\//g,'~1'),before[key],after[key],!!change.before && Object.prototype.hasOwnProperty.call(before,key),!!change.after && Object.prototype.hasOwnProperty.call(after,key),key,true);
  });
};
workbench.comparisonFieldText = function(node) {
  return node.label+': '+(node.note || workbench.comparisonValue(node.key,node.before,node.hasBefore)+' → '+workbench.comparisonValue(node.key,node.after,node.hasAfter));
};
workbench.comparisonRows = function(change,expanded) {
  var rows=[];
  function visit(node,depth) {rows.push(Object.assign({},node,{depth:depth}));if(expanded[node.path])node.children.forEach(function(child){visit(child,depth+1);});}
  workbench.comparisonFields(change).forEach(function(node){visit(node,0);});return rows;
};
workbench.comparisonTotals = function(result) {
  var counts={added:0,removed:0,changed:0};
  Object.keys(result.summary || {}).forEach(function(kind){if(result.kind==='all' || result.kind===kind)Object.keys(counts).forEach(function(key){counts[key]+=result.summary[kind][key] || 0;});});return counts;
};
workbench.comparisonMatches = function(change,filters) {return !filters.length || filters.indexOf(change.change)>=0;};
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
  ['pid','table_id','extension','version','current','section','last_section','versioning_supported','header_semantics','bytes','valid','crc','detected_standards'].forEach(function(k) {if(detail[k]!==undefined) header[k]=detail[k];});
  var children=[workbench.objectNode('header','Section header',header)];
  var sdk=scope==='section'?detail.section_native_table:(detail.merged || {}).native_table;
  children.push({id:'native',label:(detail.application_decoder?'Application decoded structure':'TSDuck decoded structure')+' · '+(scope==='section'?'selected section':'merged table'),value:sdk?(detail.application_decoder?'Application evidence':'SDK evidence'):scope==='section'?'No standalone SDK structure; section-local display in Decoded':'No complete selected generation; no merged decode',children:sdk?[workbench.sdkNode(sdk,sid)]:[]});
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
  return {id:'section',label:detail.name+' section',value:workbench.wireVersionText(detail)+' · '+(detail.valid?'valid':'invalid'),children:children};
};
workbench.defaultOpen = function(path) {
  return path==='section' || /^section\/(native|fields|services|descriptors)(?:$|\/)/.test(path) && !/\/(meta|attributes)$/.test(path);
};

// Pure presentation of engine-owned protocol summaries; no wire parsing or
// transport/list selection. Keep card paging independent of record paging.
workbench.protocolCards = function(detail, offset, limit) {
  detail=detail || {};var items=[];
  var source={section_id:detail.id,analysis_revision:detail.analysis_revision,at_packet:detail.native_table_at_packet,
    table_identity:{pid:detail.pid,table_id:detail.table_id,extension:detail.extension,version:detail.version,section_number:detail.section,current:detail.current}};
  (detail.descriptors || []).forEach(function(d) {
    if(!d.lcn_list_decode_status)return;
    if(d.lcn_list_decode_status!=='decoded') {
      items.push(function(){return {title:'NorDig channel lists · '+d.lcn_list_decode_status,
        text:(d.lcn_list_warnings || []).join('\n'),evidence:Object.assign({},source,{descriptor:d})};});return;
    }
    (d.lcn_lists || []).forEach(function(list) {
      items.push(function(){return {title:'NorDig list '+list.channel_list_id+' · '+list.channel_list_name+' · '+list.country_code,
        text:'DVB signalling · list not selected\n'+(list.services || []).map(function(s) {
          return 'SID '+workbench.hex(s.service_id)+' → LCN '+s.number+' · '+(s.allocation_status || (s.visible?'visible':'hidden'))+(s.duplicate_service?' · duplicate service':'');
        }).join('\n'),evidence:Object.assign({},source,{pid:detail.pid,descriptor_offset:d.offset,pds:d.pds,list:list})};});
    });
  });
  var app=detail.application_signalling;
  if(app) {
    items.push(function(){return {title:'Application signalling · '+app.status,
      text:'Read-only signalling. Applications and firmware are not executed.\n'+(app.diagnostics || []).map(function(x){return typeof x==='string'?x:JSON.stringify(x);}).join('\n'),
      evidence:{schema_version:app.schema_version,analysis_revision:app.analysis_revision,at_packet:app.at_packet,interpretation_profile:app.interpretation_profile,scope:app.scope,unsupported_relations:app.unsupported_relations}};});
    var related=Object.create(null);
    (app.relations || []).forEach(function(r){(related[r.from] || (related[r.from]=[])).push(r);if(r.to!==r.from)(related[r.to] || (related[r.to]=[])).push(r);});
    (app.objects || []).forEach(function(object) {
      var relationships=related[object.node_id] || [];
      items.push(function(){return {title:object.label || object.object_type,
        text:(object.object_type || 'Object')+' · '+(object.resolution_status || 'unresolved')+'\n'+
          Object.keys(object.identity || {}).filter(function(k){return k!=='descriptor_section_id' && !/node_id$/.test(k);}).map(function(k){return k.replace(/_/g,' ')+': '+workbench.value(k,object.identity[k]);}).join('\n')+'\n'+
          Object.keys(object.attributes || {}).map(function(k){var v=object.attributes[k];return k.replace(/_/g,' ')+': '+(v && typeof v==='object'?JSON.stringify(v):String(v));}).join('\n')+'\n'+
          (object.unresolved_reasons || []).map(function(x){return typeof x==='string'?x:JSON.stringify(x);}).join('\n'),
        evidence:{object:object,relations:relationships,analysis_revision:app.analysis_revision,at_packet:app.at_packet}};});
    });
  }
  limit=Math.max(1,Math.min(50,Number.isFinite(limit)?Math.floor(limit):20));
  offset=Math.max(0,Number.isFinite(offset)?Math.floor(offset):0);
  offset=items.length?Math.min(Math.floor(offset/limit)*limit,Math.floor((items.length-1)/limit)*limit):0;
  return {cards:items.slice(offset,offset+limit).map(function(build){return build();}),offset:offset,limit:limit,total:items.length,
    has_previous:offset>0,has_more:offset+limit<items.length};
};

// Source actions use exact engine references. NorDig cards currently carry only
// section provenance; descriptor offsets do not establish a field locator.
workbench.protocolCardSources = function(card) {
  var evidence=card.evidence || {},rows=[],seen=Object.create(null);
  function add(ref,relation) {
    if(!ref || typeof ref!=='object')return;
    var key=JSON.stringify(ref);
    if(seen[key])return;seen[key]=true;
    var available=typeof ref.section_id==='string' && !!ref.section_id && Number.isSafeInteger(ref.analysis_revision) && ref.analysis_revision>0 && Number.isSafeInteger(ref.at_packet) && ref.at_packet>=0;
    rows.push({ref:ref,label:(ref.assertion_key || 'Source section')+(relation?' · '+relation:''),precision:ref.locator && ref.locator.precision || 'section',available:available});
  }
  if(evidence.object) {
    (evidence.object.evidence || []).forEach(function(ref){add(ref,'');});
    (evidence.relations || []).forEach(function(r){(r.evidence || []).forEach(function(ref){add(ref,r.relation);});});
  } else if(evidence.section_id) {
    add({section_id:evidence.section_id,analysis_revision:evidence.analysis_revision,at_packet:evidence.at_packet,table_identity:evidence.table_identity,
      assertion_key:'NorDig channel-list source',role:'section evidence',locator:{precision:'section',field_id:null,container_id:null,byte_range:null,display_path:'Selected section; field locator unavailable',resolution_status:'unresolved'}},'');
  }
  return rows;
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
workbench.topologySearch = function(node, query, excludeXmlRefs) {
  var values=[];
  function visit(value,key) {
    if(excludeXmlRefs && value && typeof value==='object' && value.source_sha256 && value.element_id)return;
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
workbench.topologyRows = function(snapshot,family,query,expanded,limits,excludeXmlRefs) {
  var nodes=workbench.topologyNodes(snapshot || {}),byId={},children={},matches={},include={},rows=[],hidden=0;
  nodes=nodes.filter(function(n){return !family || family==='all' || n.family===family;});
  nodes.forEach(function(n){byId[n.node_id]=n;children[n.node_id]=[];});
  var roots=[];
  nodes.forEach(function(n){if(n.parent_id && byId[n.parent_id]) children[n.parent_id].push(n.node_id);else roots.push(n.node_id);});
  var searching=!!String(query || '').trim();
  nodes.forEach(function(n){matches[n.node_id]=!searching || workbench.topologySearch(n,query,excludeXmlRefs);if(matches[n.node_id]) {var id=n.node_id,visited={};while(id && byId[id] && !visited[id]) {visited[id]=true;include[id]=true;id=byId[id].parent_id;}}});
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

// DVB-I is an independent local XML document session. These helpers compare
// engine-owned identities and present returned data; they do not parse XML.
workbench.validateDvbi = function(snapshot,revision,sha) {
  if(!snapshot || snapshot.schema_version!==1 || !snapshot.source || snapshot.source.kind!=='local_dvbi_xml') return 'Unsupported or incomplete DVB-I document response.';
  if(!Number.isSafeInteger(snapshot.document_revision) || snapshot.document_revision<1 || typeof snapshot.source.sha256!=='string' || !snapshot.source.sha256) return 'DVB-I document identity is missing.';
  if(revision!=null && snapshot.document_revision!==revision) return 'DVB-I document revision changed.';
  if(sha!=null && snapshot.source.sha256!==sha) return 'DVB-I original source hash changed.';
  if(snapshot.nodes!==undefined) {
    if(!Array.isArray(snapshot.nodes))return 'DVB-I node page is invalid.';
    var seen=Object.create(null);
    for(var i=0;i<snapshot.nodes.length;i++){var n=snapshot.nodes[i];if(!n || typeof n.node_id!=='string' || !n.node_id || seen[n.node_id])return 'DVB-I node identity is invalid or repeated.';seen[n.node_id]=true;}
  }
  if(snapshot.page) {var p=snapshot.page;if(!Number.isSafeInteger(p.offset) || p.offset<0 || !Number.isSafeInteger(p.total) || p.total<0 || (p.has_more && (!Number.isSafeInteger(p.next_offset) || p.next_offset<=p.offset)))return 'DVB-I page does not make valid progress.';}
  return '';
};
workbench.mergeDvbi = function(current,page) {
  var error=workbench.validateDvbi(page,current?current.document_revision:null,current?current.source.sha256:null);if(error)throw new Error(error);
  if(!Array.isArray(page.nodes))throw new Error('DVB-I query did not supply an object page.');
  if(current && current.profile!==page.profile)throw new Error('DVB-I profile changed between pages.');
  var result=Object.assign({},page),nodes=Object.create(null),ids=[];
  ((current && current.nodes) || []).concat(page.nodes).forEach(function(node){if(!nodes[node.node_id])ids.push(node.node_id);nodes[node.node_id]=node;});
  result.nodes=ids.map(function(id){return nodes[id];});return result;
};
workbench.dvbiRows = function(snapshot,query,expanded,limits) {
  return workbench.topologyRows(snapshot || {},'all',query,expanded,limits,true);
};
workbench.dvbiIdentity = function(node) {
  node=node || {};var identity=node.identity || {},attributes=node.attributes || {},parts=[];
  var declared=identity.service_id || identity.instance_id || identity.service_ref || identity.list_id;
  if(declared)parts.push(String(declared));
  if(node.object_type==='lcn_table') {
    var regions=(attributes.target_regions || []).map(function(r){return r.region_ref;}).filter(function(r){return r!==null && r!==undefined && r!=='';});
    if(regions.length)parts.push((regions.length===1?'Region ref ':'Region refs ')+regions.slice(0,3).join(', ')+(regions.length>3?' +'+(regions.length-3):''));
    else parts.push('Region not declared');
  }
  if(!declared) {
    var source=(node.evidence || [])[0];
    if(source && source.element_id)parts.push('XML '+source.element_id);
  }
  return parts.join(' · ') || (node.object_type || 'Object').replace(/_/g,' ');
};
workbench.dvbiEvidence = function(node) {
  var refs=[],seen=Object.create(null);
  function visit(value) {
    if(!value || typeof value!=='object')return;
    if(typeof value.element_id==='string' && value.document_revision!=null && typeof value.source_sha256==='string' && typeof value.path==='string') {
      var key=JSON.stringify([value.document_revision,value.source_sha256,value.element_id,value.path,value.precision,value.attribute_name]);
      if(!seen[key]){seen[key]=true;refs.push(value);}return;
    }
    Object.keys(value).forEach(function(key){visit(value[key]);});
  }
  visit(node && node.evidence);visit(node && node.attributes);return refs;
};
workbench.resolveDvbiEvidence = function(ref,detail) {
  function fail(message){return {status:'mismatch',precision:'none',attribute_index:-1,path:'',original_byte_offset:null,message:message};}
  if(!ref || !Number.isSafeInteger(ref.document_revision) || typeof ref.source_sha256!=='string' || !ref.source_sha256)return fail('No complete DVB-I source reference was supplied.');
  var error=workbench.validateDvbi(detail,ref.document_revision,ref.source_sha256);if(error)return fail(error);
  var element=detail.element;
  if(!element || element.element_id!==ref.element_id)return fail('Returned XML element does not match the requested source.');
  if((ref.line!=null && ref.line!==element.line) || (ref.column!=null && ref.column!==element.column))return fail('XML element-start location does not match the source reference.');
  var attribute=-1,precision='element',status='resolved',path=element.path;
  if(ref.precision==='attribute') {
    if(ref.path!==element.path+'/@'+ref.attribute_name)return fail('XML attribute path does not match the source element.');
    attribute=(element.attributes || []).findIndex(function(a){return 'Q{'+a.namespace+'}'+a.local_name===ref.attribute_name;});
    if(attribute>=0){precision='attribute';path=ref.path;}else status='fallback';
  } else if(ref.precision!=='element' || ref.path!==element.path)return fail('XML element path does not match the source reference.');
  var offset=element.original_byte_offset;
  if(!Number.isSafeInteger(offset) || offset<0 || offset>=detail.source.bytes || element.byte_offset_precision!=='element_start')offset=null;
  return {status:status,precision:precision,attribute_index:attribute,path:path,line:element.line,column:element.column,line_precision:'element_start',original_byte_offset:offset,
    message:precision==='attribute'?'Located the XML attribute. Line and byte positions identify the containing element start, not an exact attribute span.':status==='fallback'?'Located the XML element; the requested attribute is unavailable.':'Located the XML element. Original source and XML-normalized values are shown separately.'};
};
