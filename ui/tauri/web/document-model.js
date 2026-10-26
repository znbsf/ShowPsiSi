// View identity and window geometry shared by Qt and Web. No transport decoding.
var documents = {
 create:function(identity){return {identity:identity||'',serial:0,active:'',items:[]};},
 open:function(state,kind,key,title,payload,duplicate){
  var s=this.copy(state),found=!duplicate&&s.items.find(function(d){return d.kind===kind&&d.key===key;});
  if(found){found.title=title;return this.activate(s,found.id);}
  if(s.items.length>=24)throw new Error('Close a document before opening another (24 window limit)');
  var id='document-'+(++s.serial),offset=(s.items.length%8)*24;
  s.items.push({id:id,kind:kind,key:key,title:title,payload:payload||{},x:offset,y:offset,width:640,height:460,mode:'maximized'});s.active=id;return s;
 },
 copy:function(s){return {identity:s.identity,serial:s.serial,active:s.active,items:s.items.map(function(d){return Object.assign({},d);})};},
 activate:function(state,id){var s=this.copy(state),i=s.items.findIndex(function(d){return d.id===id;});if(i<0)return s;var d=s.items.splice(i,1)[0];if(d.mode==='minimized')d.mode=d.previousMode||'normal';s.items.push(d);s.active=id;return s;},
 close:function(state,id){var s=this.copy(state);s.items=s.items.filter(function(d){return d.id!==id;});if(s.active===id)s.active=s.items.length?s.items[s.items.length-1].id:'';return s;},
 cycle:function(state,back){var s=this.copy(state);if(s.items.length<2)return s;return this.activate(s,back?s.items[s.items.length-2].id:s.items[0].id);},
 mode:function(state,id,mode){var s=this.copy(state),d=s.items.find(function(d){return d.id===id;});if(d){d.previousMode=d.mode;d.mode=mode;}if(mode==='minimized'){var previous=s.items.filter(function(v){return v.mode!=='minimized';});s.active=previous.length?previous[previous.length-1].id:'';return s;}return this.activate(s,id);},
 geometry:function(state,id,x,y,w,h){var s=this.copy(state),d=s.items.find(function(d){return d.id===id;});if(d){d.x=Math.max(0,x);d.y=Math.max(0,y);d.width=Math.max(240,w);d.height=Math.max(180,h);}return s;},
 arrange:function(state,command,w,h){var s=this.copy(state),visible=s.items.filter(function(d){return d.mode!=='minimized';}),minimized=s.items.filter(function(d){return d.mode==='minimized';});
  if(command==='arrange'){minimized.forEach(function(d,i){d.x=(i%Math.max(1,Math.floor(w/200)))*200;d.y=Math.max(0,h-28*(1+Math.floor(i/Math.max(1,Math.floor(w/200)))));});return s;}
  var columns=Math.max(1,Math.ceil(Math.sqrt(visible.length))),rows=Math.max(1,Math.ceil(visible.length/columns));
  visible.forEach(function(d,i){d.mode='normal';if(command==='tile'){d.x=(i%columns)*w/columns;d.y=Math.floor(i/columns)*h/rows;d.width=Math.max(240,w/columns);d.height=Math.max(180,h/rows);}else{d.x=(i%8)*24;d.y=(i%8)*24;d.width=Math.max(240,w-24*Math.min(8,visible.length));d.height=Math.max(180,h-24*Math.min(8,visible.length));}});return s;
 }
};
if(typeof module!=='undefined')module.exports=documents;
