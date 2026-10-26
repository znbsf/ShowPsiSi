// Render presentation for engine-owned Teletext semantic cells and capture identities.
var teletextModel={
 colours:['#000000','#ff0000','#00ff00','#ffff00','#0000ff','#ff00ff','#00ffff','#ffffff'],
 pids:function(state){var pids=[];(state.media_streams||[]).forEach(function(s){if((s.teletext_signalling||[]).length&&pids.indexOf(s.pid)<0)pids.push(s.pid);});return pids;},
 hex:function(n,width){return n===null||n===undefined?'Unknown':Number(n).toString(16).toUpperCase().padStart(width||3,'0');},
 glyph:function(cell){if(!cell.source_present)return '';if(!cell.geometry_known)return '□';if(cell.kind===3)return String.fromCodePoint(cell.unicode);if(cell.kind===4)return '█';if(cell.kind===1)return '�';if(cell.kind===6)return '□';return '';},
 visible:function(cell,result,reveal,flash){return !(result.header_flags||{}).inhibit_display&&!(cell.row===0&&(result.header_flags||{}).suppress_header)&&(!cell.conceal||reveal)&&(!cell.flash||flash);},
 source:function(result,cell){return cell?(result.rows||[]).find(function(r){return r.source_unit===cell.source_unit;})||null:null;},
 title:function(result){return 'PID 0x'+this.hex(result.pid,4)+' | page '+this.hex(result.page_hex)+' / subpage '+this.hex(result.subcode,4)+' | capture '+((result.capture_index||0)+1)+' / '+(result.captures||[]).length+' | header epoch '+(result.header_epoch||0);},
 details:function(result,cell){return JSON.stringify({identity:this.title(result),cell:cell,source:this.source(result,cell),profile:result.profile,render_national:result.render_national,header_flags:result.header_flags,header_slot_policy:result.header_slot_policy,extensions:result.extensions,body_layout_complete:result.body_layout_complete,body_issues:result.body_issues,scan:result.scan,invalid_units:result.invalid_units,parity_errors:result.parity_errors,corrected_bits:result.corrected_bits,capture_evictions:result.capture_evictions,page_store_evictions:result.page_store_evictions,scope:result.scope},null,2);}
};
if(typeof module!=='undefined')module.exports=teletextModel;
