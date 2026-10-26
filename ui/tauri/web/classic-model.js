// Original menu order and toolbar command mapping. Presentation only.
var classic = {
 toolbar:[{id:'open',slot:0},{id:'save',slot:1},{separator:true},{id:'start',slot:2},{id:'stop',slot:3},{id:'pause',slot:4},{separator:true},{id:'tree',slot:5},{id:'print',slot:6}],
 labels:{decoded:'Native Decode',new:'New',open:'Open…',close:'Close',save:'Save…',print:'Print…',printSetup:'Print Setup…',exit:'Exit',toolbar:'Toolbar',status:'Status Bar',tree:'View TS Tree',summary:'View Summary',bitrate:'View Bitrate',configuration:'Card Configuration',packets:'Packet Explorer',diagnostics:'Bug Report',start:'Start',stop:'Stop',pause:'Pause',cascade:'Cascade',tile:'Tile',arrange:'Arrange Icons',index:'Index',about:'About ShowPsiSi',advanced:'Advanced workspace',dvbi:'DVB-I XML document',messages:'Message history'},
 shortcuts:{new:'Ctrl+N',open:'Ctrl+O',close:'Ctrl+F4',save:'Ctrl+S',print:'Ctrl+P'},
 checked:function(id,s){return id==='toolbar'?s.toolbar:id==='status'?s.status:id==='tree'?s.tree:false;},
 enabled:function(id,s){
  var f=s.features||{};
  if(['toolbar','status','tree','index','about','messages'].indexOf(id)>=0)return true;
  if(id==='exit')return !!s.native && !s.exporting;
  if(id==='stop')return !!s.busy && !s.cancelling;
  if(id==='pause')return !!s.busy && !!s.canPause && !s.cancelling;
  if(s.busy||s.exporting||!s.available)return false;
  if(['configuration','open','advanced','dvbi'].indexOf(id)>=0)return true;
  if(id==='start')return !!s.hasInput;
  if(id==='diagnostics')return !!s.native;
  if(id==='summary')return !!s.complete;
  if(id==='packets')return !!s.complete && !!f.packets;
  if(id==='bitrate')return !!s.complete && !!f.bitrate;
  if(id==='save')return !!s.complete && !!f.save;
  if(id==='decoded')return !!s.complete&&!!f.documents;
  if(id==='new')return !!s.complete&&!!f.documents;
  if(id==='close')return !!f.documents && s.documentCount>0;
  if(['cascade','tile','arrange'].indexOf(id)>=0)return !!f.documents && s.documentCount>0;
  return false;
 },
 reason:function(id,s){if(this.enabled(id,s))return '';if(s.busy)return 'Wait for the current analysis or result loading to finish';if(s.exporting)return 'Wait for the active export to finish';if(id==='start'&&!s.hasInput)return 'Open a transport stream first';if(['summary','packets','bitrate','save'].indexOf(id)>=0&&!s.complete)return 'Analyze a source first';if(id==='exit'||id==='diagnostics')return 'Native application command; unavailable in the browser preview';return 'This command is not yet available for the current view';},
 menus:function(s){var self=this,make=function(id){if(id==='-')return {separator:true};return {id:id,text:id==='pause'&&s.paused?'Resume':self.labels[id],shortcut:self.shortcuts[id]||'',enabled:self.enabled(id,s),checked:self.checked(id,s),checkable:['toolbar','status','tree'].indexOf(id)>=0,reason:self.reason(id,s)};};
  var groups=[['File',['new','open','close','save','-','print','printSetup','-','exit']],['View',['toolbar','status','tree','-','summary','bitrate','decoded','-','advanced','dvbi']],['Analyzer',['configuration','packets','diagnostics','-','start','stop','pause']]];
  if(s.documentCount>0)groups.push(['Window',['cascade','tile','arrange']]);groups.push(['Help',['index','about','-','messages']]);
  return groups.map(function(g){return {title:g[0],items:g[1].map(make)};});
 }
};
if(typeof module!=='undefined')module.exports=classic;
