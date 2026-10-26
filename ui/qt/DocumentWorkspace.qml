import QtQuick
import QtQuick.Controls
import "../tauri/web/document-model.js" as Model
Item {
 id:workspace
 property var state:Model.documents.create('')
 property var frames:({})
 property Component sectionComponent
 property Component summaryComponent
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
 function receiveStatistics(method,result){Object.keys(frames).forEach(function(id){var frame=frames[id];if(frame.documentData.kind==='statistics'&&frame.contentItem)frame.contentItem.receive(method,result);});}
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
    sourceComponent:documentData.kind==='summary'?workspace.summaryComponent:documentData.kind==='decoded'?workspace.decodeComponent:documentData.kind==='packet'?workspace.packetComponent:documentData.kind==='statistics'?workspace.statisticsComponent:workspace.sectionComponent
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
