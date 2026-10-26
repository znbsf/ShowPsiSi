// Shared presentation. Parsing, decoding, provenance and device control are core-owned.
var mediaModel={
 tabs:['PES','ES','Video','Audio'],columns:['PES','Stream ID','Kind','Source packets','PES bytes','ES bytes','PTS (90 kHz)'],
 formats:['auto','mpegvideo','h264','hevc','mp3','aac','loas','ac3','eac3'],
 hex:function(n,width){return n===null||n===undefined?'Unknown':'0x'+Number(n).toString(16).toUpperCase().padStart(width||4,'0');},
 pids:function(state){var rows=[];(state.media_streams||[]).forEach(function(s){var row=rows.find(function(r){return r.pid===s.pid;});if(!row){row={pid:s.pid,programs:[],codecs:[]};rows.push(row);}if(row.programs.indexOf(s.program_number)<0)row.programs.push(s.program_number);if(row.codecs.indexOf(s.codec||'Unknown')<0)row.codecs.push(s.codec||'Unknown');});return rows;},
 rows:function(pes){var self=this;return (pes||[]).map(function(p){return {key:p.index,values:[String(p.index),self.hex(p.stream_id,2),p.stream_name,p.start_packet+'–'+p.end_packet,String(p.bytes),String(p.es_bytes),p.pts===null?'Unknown':String(p.pts)],pes:p};});},
 raw:function(result){return ((((result.selected||{}).content||{}).raw_hex||'').match(/.{1,32}/g)||[]).map(function(line){return (line.match(/.{2}/g)||[]).join(' ');}).join('\n');},
 sourceAt:function(result,cursor){var s=result.selected||{},c=s.content||{},at=Number(c.pes_offset||0)+cursor;var f=(s.source_fragments||[]).find(function(f){return at>=f.pes_offset&&at<f.pes_offset+f.length;});return f?{packet_index:f.packet_index,packet_offset:f.packet_offset+at-f.pes_offset,pes_offset:at}:null;},
 location:function(result){var s=result.selected,c=s?s.content:null;return 'PID '+this.hex(result.pid)+(s?' / PES '+s.index+' / '+s.start_packet+'–'+s.end_packet+' packets':'')+(c?' / '+c.layer+' bytes '+c.offset+'–'+(c.offset+c.length)+' / '+c.total_bytes:'');},
 snapshotPreview:function(p){if(!p)return {};var out=Object.assign({},p);if(out.frames)out.frames=out.frames.map(function(f){return {index:f.index,sha256:f.sha256,mime:f.mime};});return out;},
 details:function(result,preview){var selected=result.selected?Object.assign({},result.selected):null;if(selected&&selected.content){selected.content=Object.assign({},selected.content);delete selected.content.raw_hex;}return JSON.stringify({source:result.source,analysis_revision:result.analysis_revision,selected:selected,scan:result.scan,scope:result.scope,preview:this.snapshotPreview(preview)},null,2);}
};
if(typeof module!=='undefined')module.exports=mediaModel;
