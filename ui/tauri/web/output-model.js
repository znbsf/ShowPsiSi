/* Identical output choices and copy formatting for Qt and Tauri. */
var outputModel={
 options:function(state,context){
  var base={analysis_revision:state.analysis_revision||state.revision},out=[],v=context.view||{},p=context.payload||{};
  if(state.selected_packet!==null&&state.selected_packet!==undefined)base.at_packet=state.selected_packet;
  function add(kind,label,ext,args){out.push({kind:kind,label:label,extension:ext,params:Object.assign({},base,args||{},{kind:kind})});}
  if(context.kind==='si'&&p.id)add('section','Original selected section (including CRC where present)','bin',{source_id:p.id,at_packet:p.native_table_at_packet});
  if(context.kind==='packet'&&v.index!==null&&v.index!==undefined){add('packet','Original 188-byte TS packet','bin',{packet_index:v.index});add('packet_frame','Original packet frame including prefix/parity','bin',{packet_index:v.index});}
  if(context.kind==='media'){
   if(v.selected!==null&&v.selected>=0&&v.result&&v.result.selected){var q=Object.assign({},v.query,{pes_index:v.selected});add('pes','Original selected complete PES','pes',q);add('es','Collected ES payload of selected PES','es',q);}
   if(v.preview&&v.preview.preview_token){if(v.preview.kind==='video')add('png','Current decoded preview frame (derived)','png',{preview_token:v.preview.preview_token,frame_index:v.frame_index});if(v.preview.kind==='audio')add('wav','Decoded PCM preview (derived, mono 48000 Hz)','wav',{preview_token:v.preview.preview_token});}
  }
  if(context.kind==='carousel'&&v.result&&v.result.biop){var r=v.result,q={source_id:v.source_id,at_packet:r.at_packet,download_id:r.download_id,module_id:r.module_id,module_version:r.module_version,announcement_epoch_order:r.announcement_epoch_order};add('module','Complete assembled module (no decompression)','bin',q);if(r.object)add('object',r.object.type==='fil'?'Original file content':'Selected BIOP object content / envelope','bin',Object.assign({},q,{object_offset:r.object.offset}));}
  if(state.complete)add('report','Analysis summary with coverage (JSON)','json');
  return out;
 },
 fieldText:function(field,source){if(!field)return '';return 'Source\t'+source+'\nField\tBits\tValue\tComment\n'+[field.name,field.bit_length===undefined?'Unknown':field.bit_length+' bits',field.value===undefined?'':field.value,field.help||field.comment||field.description||''].map(function(v){return (typeof v==='object'?JSON.stringify(v):String(v)).replace(/[\t\r\n]/g,' ');}).join('\t');},
 hexText:function(raw,label){return raw?'Layer: '+label+'\n'+String(raw).replace(/(..)/g,'$1 ').trim():'';}
};

var scanSettings={
 validate:function(v){
  if(!v||['auto','dvb','atsc','isdb','isdb-japan','isdb-brazil','scte','dtmb'].indexOf(v.standards)<0||['full','prefix','range','distributed'].indexOf(v.scan_mode)<0||['percent','packets'].indexOf(v.budget_unit)<0)return 'Unknown standards or scan mode';
  if(typeof v.default_charset!=='string'||v.default_charset.length>128||/[\x00-\x1f]/.test(v.default_charset))return 'Charset must be at most 128 printable characters';
  if(!Array.isArray(v.extra_pids)||v.extra_pids.length>64||v.extra_pids.some(function(n){return !Number.isSafeInteger(n)||n<0||n>8191;}))return 'Extra PIDs must be 0..8191, at most 64 entries';
  if(['prefix','distributed'].indexOf(v.scan_mode)>=0){var n=v.budget_unit==='percent'?v.sample_percent:v.max_packets;if(!Number.isSafeInteger(n)||n<1||(v.budget_unit==='percent'&&n>100))return 'Choose 1..100 percent or a positive packet budget';}
  if(v.scan_mode==='range'&&(!Number.isSafeInteger(v.start_packet)||!Number.isSafeInteger(v.end_packet)||v.start_packet<0||v.end_packet<=v.start_packet))return 'End packet (exclusive) must exceed start packet (inclusive)';
  if(v.scan_mode==='distributed'&&(!Number.isSafeInteger(v.window_count)||v.window_count<1||v.window_count>16))return 'Choose 1..16 contiguous windows';return '';
 }
};
