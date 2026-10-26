// Presentation of already scoped query_service responses. No SID/PID joins here.
var serviceModel={
 tabs:['Service','ES','EPG','Applications'],
 text:function(v){return v===null||v===undefined?'Unknown':String(v);},
 hex:function(v,width){return v===null||v===undefined?'Unknown':'0x'+Number(v).toString(16).toUpperCase().padStart(width||4,'0');},
 columns:function(tab){return tab==='ES'?['PID','Type','Classification','Source']:tab==='EPG'?['Start UTC','Event','Duration (s)','Title']:tab==='Applications'?['Organization','Application','Carriage / resolution','Source']:['Field','Value'];},
 rows:function(result,tab){var self=this,s=result.service||{},i=result.identity||{};
  if(tab==='ES')return (result.components||[]).map(function(c){return {key:c.source_id+':'+c.structure_path,values:[self.hex(c.pid),self.hex(c.type,2),c.is_video?'Video':c.is_audio?'Audio':'Data / unspecified',c.classification_basis],source_id:c.source_id,path:c.structure_path};});
  if(tab==='EPG')return (result.events||[]).map(function(e){return {key:e.source_id+':'+e.id+':'+e.start,values:[e.start,self.hex(e.id),self.text(e.duration_seconds),e.title],source_id:e.source_id,path:'section'};});
  if(tab==='Applications')return (result.applications||[]).map(function(a){var o=a.object||{},identity=o.identity||{};return {key:o.node_id,values:[self.hex(identity.organization_id,8),self.hex(identity.application_id),a.carriage_status+' / '+o.resolution_status,'AIT PID '+self.hex(a.pid)+'; nonexclusive signalling'],source_id:a.source_id,path:'section'};});
  return [['Name',s.name],['Provider',s.provider],['ONID',self.hex(i.original_network_id)],['TSID',self.hex(i.transport_stream_id)],['SID',self.hex(i.service_id)],['LCN',s.logical_channel_number],['LCN status',s.lcn_status],['PMT PID',self.hex(s.pmt_pid)],['Media',s.media_status]].map(function(pair){return {key:pair[0],values:[pair[0],self.text(pair[1])],source_id:pair[0]==='PMT PID'?result.pmt_source_id:s.source_id,path:'section'};});
 }
};
if(typeof module!=='undefined')module.exports=serviceModel;
