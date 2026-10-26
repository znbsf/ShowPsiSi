// Display-only mapping of engine-provided packet bytes and ranges.
var packetModel={
 colors:{header:'#ffd5d5',adaptation:'#d8ecff',pointer:'#fff2aa',pes_header:'#ead8ff',payload:'#b5d2bf',unknown:'#eeeeee'},
 headerFields:['sync_byte','transport_error_indicator','payload_unit_start_indicator','transport_priority','PID','transport_scrambling_control','adaptation_field_control','continuity_counter'],
 hex:function(value,width){return '0x'+Number(value).toString(16).toUpperCase().padStart(width||2,'0');},
 bytes:function(result){var raw=result.raw_hex||'',out=[];for(var i=0;i<raw.length/2;i++){var region=(result.regions||[]).find(function(r){return i>=r.offset&&i<r.offset+r.length;});out.push({offset:i,hex:raw.slice(i*2,i*2+2),kind:region?region.kind:'unknown',character:(parseInt(raw.slice(i*2,i*2+2),16)>=32&&parseInt(raw.slice(i*2,i*2+2),16)<127)?String.fromCharCode(parseInt(raw.slice(i*2,i*2+2),16)):'.'});}return out;},
 index:function(value,total){var text=String(value).trim();if(!/^(0x[0-9a-f]+|[0-9]+)$/i.test(text))throw new Error('Enter a non-negative packet index');var n=Number(text);if(!Number.isSafeInteger(n)||n<0||n>=total)throw new Error('Packet index must be in 0..'+(total-1));return n;},
 pid:function(value){var text=String(value).trim();if(!text)return null;var n=this.index(text,8192);return n;}
};
if(typeof module!=='undefined')module.exports=packetModel;
