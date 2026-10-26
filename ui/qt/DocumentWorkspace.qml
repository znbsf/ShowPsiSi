import QtQuick
import QtQuick.Controls
import QtQuick.Window
import "../tauri/web/document-model.js" as Model
Item {
 id:workspace
 property var state:Model.documents.create('')
 property var frames:({})
 property Component sectionComponent
 property Component summaryComponent
 property Item navigationOrigin:null
 property Component mediaComponent
 property Component teletextComponent
 property Component carouselComponent
 property Component serviceComponent
 property Component statisticsComponent
 property Component packetComponent
 property Component decodeComponent
 signal changed()
 clip:true
 Rectangle{anchors.fill:parent;color:'#808080'}
 function apply(next){
  state=next;var ids={};next.items.forEach(function(d,i){ids[d.id]=true;var f=frames[d.id];if(!f){f=windowComponent.createObject(workspace,{documentData:d});frames[d.id]=f;}f.documentData=d;f.z=i+1;f.active=d.id===next.active;});
  Object.keys(frames).forEach(function(id){if(!ids[id]){frames[id].destroy();delete frames[id];}});changed();
 }
 function open(kind,key,title,payload,duplicate){apply(Model.documents.open(state,kind,key,title,payload,!!duplicate));activate(state.active);}
 function reset(identity){if(state.identity!==identity)apply(Model.documents.create(identity));}
 function activate(id){apply(Model.documents.activate(state,id));if(frames[id])frames[id].forceActiveFocus();}
 function close(id){apply(Model.documents.close(state,id||state.active));if(state.active)activate(state.active);}
 function cycle(back){apply(Model.documents.cycle(state,back));if(state.active)activate(state.active);}
 function arrange(command){apply(Model.documents.arrange(state,command,width,height));}
 function nextRegion(back){var frame=frames[state.active],item=frame?frame.contentItem:null;if(!item){if(navigationOrigin)navigationOrigin.forceActiveFocus();return;}if(item.nextRegion){item.focusOrigin=navigationOrigin;item.nextRegion(back);return;}var active=workspace.Window.window?workspace.Window.window.activeFocusItem:null,inside=false;for(var p=active;p;p=p.parent)if(p===frame)inside=true;if(inside&&navigationOrigin)navigationOrigin.forceActiveFocus();else item.forceActiveFocus();}
 function carouselAction(action){var f=frames[state.active];if(!f||f.documentData.kind!=='carousel'||!f.contentItem)return false;var item=f.contentItem;if(action.name==='carousel_open'){var n=Number(action.index);if(!Number.isInteger(n)||n<0||n>=item.displayedRows.length)return false;item.open(item.displayedRows[n]);return true;}if(action.name==='carousel_tab'&&['Modules','OC Files','OC Hierarchy','BIOP List'].indexOf(action.value)>=0){item.tab=action.value;return true;}if(action.name==='carousel_view'&&['Summary','Hex','Text','Class Info'].indexOf(action.value)>=0){item.contentView=action.value;return true;}if(action.name==='carousel_back'){item.back();return true;}return false;}
 function teletextAction(action){var f=frames[state.active];if(!f||f.documentData.kind!=='teletext'||!f.contentItem)return false;var item=f.contentItem;if(action.name==='teletext_select'){var n=Number(action.index);if(!Number.isInteger(n)||n<0||n>=960)return false;item.selectCell(n);return true;}if(action.name==='teletext_capture'&&(action.delta===-1||action.delta===1)){item.selectCapture(action.delta);return true;}if(action.name==='teletext_reveal'&&typeof action.value==='boolean'){item.reveal=action.value;return true;}if(action.name==='teletext_query'){if(action.pid!==undefined){var pid=Number(action.pid);if(!Number.isInteger(pid)||pid<0||pid>8190)return false;item.pidText=String(pid);}var q=action.params||{};if(Object.keys(q).some(function(k){return ['page_hex','subcode','capture_index','national'].indexOf(k)<0;}))return false;item.request(q);return true;}return false;}
 function mediaAction(action){var f=frames[state.active];if(!f||f.documentData.kind!=='media'||!f.contentItem)return false;var v=f.contentItem;if(action.name==='media_select'){var index=Number(action.index);if(!v.inventory.some(function(p){return p.index===index;}))return false;v.selectPes(index);return true;}if(action.name==='media_tab'&&['PES','ES','Video','Audio'].indexOf(action.value)>=0){v.setTab(action.value);return true;}if(action.name==='media_decode'&&(v.tab==='Video'||v.tab==='Audio')&&v.selectedIndex>=0){v.decode();return true;}if(action.name==='media_play'){v.play();return true;}if(action.name==='media_pause'){v.pause();return true;}if(action.name==='media_stop'){v.stop();return true;}if(action.name==='media_source'){v.jumpSource();return true;}if(action.name==='media_cursor'){var n=Number(action.index);if(!Number.isInteger(n)||n<0||!v.contentPage||n>=v.contentPage.length)return false;v.selectByte(n);return true;}return false;}
 function outputContext(){var d=state.items.find(function(d){return d.id===state.active;});var f=d?frames[d.id]:null;var item=f?f.contentItem:null;return d?{kind:d.kind,payload:d.payload,view:item&&item.snapshot?item.snapshot():item&&item.captureContext?{copyField:item.selectedField,raw_hex:item.rawHex}: {}}:{};}
 function stopMedia(){Object.keys(frames).forEach(function(id){var f=frames[id];if(f.documentData.kind==='media'&&f.contentItem)f.contentItem.stop(true);});}
 function receiveMedia(method,result){Object.keys(frames).forEach(function(id){var f=frames[id];if(f.documentData.kind==='media'&&f.contentItem)f.contentItem.receive(method,result);});}
 function receiveTeletext(result){Object.keys(frames).forEach(function(id){var frame=frames[id];if(frame.documentData.kind==='teletext'&&frame.contentItem)frame.contentItem.receive(result);});}
 function receiveCarousel(result){Object.keys(frames).forEach(function(id){var frame=frames[id];if(frame.documentData.kind==='carousel'&&frame.contentItem)frame.contentItem.receive(result);});}
 function receiveService(result){Object.keys(frames).forEach(function(id){var frame=frames[id];if(frame.documentData.kind==='service'&&frame.contentItem)frame.contentItem.receive(result);});}
 function focusSection(id,path,cutoff){var found=state.items.find(function(d){return d.kind==='si'&&d.payload.id===id&&d.payload.native_table_at_packet===cutoff;});if(found){activate(found.id);if(frames[found.id].contentItem)frames[found.id].contentItem.focusNode(path||'section');}}
 function receiveStatistics(method,result){Object.keys(frames).forEach(function(id){var frame=frames[id];if(frame.documentData.kind==='statistics'&&frame.contentItem)frame.contentItem.receive(method,result);});}
 function seekPacket(pid,index,offset){var frame=frames[state.active];if(frame&&frame.documentData.kind==='packet'&&frame.contentItem)frame.contentItem.seek(pid,index,offset);}
 function receivePacket(result){Object.keys(frames).forEach(function(id){var frame=frames[id];if(frame.documentData.kind==='packet'&&frame.contentItem)frame.contentItem.receive(result);});}
 function receiveTransport(result){Object.keys(frames).forEach(function(id){var frame=frames[id];if(frame.documentData.kind==='summary'&&frame.contentItem)frame.contentItem.receive(result);});}
 function snapshot(){return {identity:state.identity,active:state.active,items:state.items.map(function(d){return {id:d.id,kind:d.kind,key:d.key,title:d.title,mode:d.mode,x:d.x,y:d.y,width:d.width,height:d.height,source_id:d.payload.id||'',view:frames[d.id]&&frames[d.id].contentItem&&frames[d.id].contentItem.snapshot?frames[d.id].contentItem.snapshot():null};})};}
 Component {
  id:windowComponent
  FocusScope {
   id:frame
   property var documentData
   property bool active:false
   property alias contentItem:content.item
   x:documentData.mode==='maximized'?0:documentData.x
   y:documentData.mode==='maximized'?0:documentData.y
   width:documentData.mode==='maximized'?workspace.width:documentData.mode==='minimized'?200:documentData.width
   height:documentData.mode==='maximized'?workspace.height:documentData.mode==='minimized'?28:documentData.height
   objectName:'document:'+documentData.id
   Rectangle{anchors.fill:parent;color:'#efefef';border.color:'#404040';border.width:2}
   TapHandler{onPressedChanged:if(pressed&&workspace.state.active!==frame.documentData.id)workspace.activate(frame.documentData.id)}
   Rectangle {
    id:titleBar;x:3;y:3;width:parent.width-6;height:24;color:frame.active?'#0a246a':'#8093b5'
    Text{x:4;anchors.verticalCenter:parent.verticalCenter;width:parent.width-86;elide:Text.ElideRight;text:frame.documentData.title;color:'white';font.family:'Tahoma';font.pixelSize:12}
    MouseArea {anchors.fill:parent;acceptedButtons:Qt.LeftButton
     property real startX:0;property real startY:0;property real originX:0;property real originY:0
     onPressed:function(mouse){workspace.activate(frame.documentData.id);startX=mouse.x;startY=mouse.y;originX=frame.x;originY=frame.y;}
     onPositionChanged:function(mouse){if(pressed&&frame.documentData.mode==='normal')workspace.apply(Model.documents.geometry(workspace.state,frame.documentData.id,frame.x+mouse.x-startX,frame.y+mouse.y-startY,frame.width,frame.height));}
     onDoubleClicked:workspace.apply(Model.documents.mode(workspace.state,frame.documentData.id,frame.documentData.mode==='maximized'?'normal':'maximized'))
    }
    Row {anchors.right:parent.right;anchors.verticalCenter:parent.verticalCenter;spacing:1
     Repeater {model:[{name:'Minimize window',text:'_',mode:'minimized'},{name:'Maximize or restore window',text:'□',mode:'maximize'},{name:'Close window',text:'×',mode:'close'}]
      delegate:Button{required property var modelData;width:23;height:20;text:modelData.text;Accessible.name:modelData.name;font.pixelSize:12
       onClicked:{var id=frame.documentData.id;if(modelData.mode==='close')workspace.close(id);else workspace.apply(Model.documents.mode(workspace.state,id,modelData.mode==='maximize'?(frame.documentData.mode==='maximized'?'normal':'maximized'):'minimized'));}
      }
     }
    }
   }
   Loader {
    id:content;x:3;y:28;width:parent.width-6;height:Math.max(0,parent.height-31);visible:frame.documentData.mode!=='minimized'
    property var documentData:frame.documentData
    sourceComponent:documentData.kind==='summary'?workspace.summaryComponent:documentData.kind==='decoded'?workspace.decodeComponent:documentData.kind==='packet'?workspace.packetComponent:documentData.kind==='statistics'?workspace.statisticsComponent:documentData.kind==='media'?workspace.mediaComponent:documentData.kind==='teletext'?workspace.teletextComponent:documentData.kind==='carousel'?workspace.carouselComponent:documentData.kind==='service'?workspace.serviceComponent:workspace.sectionComponent
   }
   MouseArea {width:12;height:12;anchors.right:parent.right;anchors.bottom:parent.bottom;visible:frame.documentData.mode==='normal';cursorShape:Qt.SizeFDiagCursor
    property point start
    property real startWidth:0;property real startHeight:0
    onPressed:function(mouse){start=mapToItem(workspace,mouse.x,mouse.y);startWidth=frame.width;startHeight=frame.height;}
    onPositionChanged:function(mouse){if(pressed){var pos=mapToItem(workspace,mouse.x,mouse.y);workspace.apply(Model.documents.geometry(workspace.state,frame.documentData.id,frame.x,frame.y,startWidth+pos.x-start.x,startHeight+pos.y-start.y));}}
   }
  }
 }
}
