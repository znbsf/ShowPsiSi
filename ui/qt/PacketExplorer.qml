import QtQuick
import QtQuick.Controls
import QtQuick.Window
import QtQuick.Layouts
import "../tauri/web/packet-model.js" as Shared
Pane {
 id:view
 property Item focusOrigin:null
 function nextRegion(back){var regions=(focusOrigin?[focusOrigin]:[]).concat([indexInput,pidInput,bytes]);var active=view.Window.window?view.Window.window.activeFocusItem:null,index=regions.findIndex(function(n){for(var p=active;p;p=p.parent)if(p===n)return true;return false;});regions[index<0?(back?regions.length-1:0):(index+(back?regions.length-1:1))%regions.length].forceActiveFocus();}
 required property var host
 property int initialPid:-1
 property real initialIndex:0
 property int initialByte:0
 property int wantedByte:0
 property var packet:({})
 property var byteRows:Shared.packetModel.bytes(packet)
 property int cursor:0
 property bool loading:false
 property string feedback:''
 property string tokenPrefix:'packet-'+Date.now()+'-'+Math.floor(Math.random()*1000000)
 property int serial:0
 property string expectedToken:''
 property var pending:({})
 signal requested(var params)
 signal sectionActivated(string id)
 padding:6
 background:Rectangle{color:'#efefef'}
 function total(){return Number((host.analysisState.coverage||{}).source_packets||Math.floor(host.analysisState.source_bytes/host.analysisState.packet_size)||0);}
 function seek(pid,index,offset){pidInput.text=pid<0?'':Shared.packetModel.hex(pid,4);send(index,'forward',offset||0);}
 function send(index,direction,offset){
  wantedByte=offset===undefined?0:Math.max(0,Math.min(187,Number(offset)));
  if(!host.backendReady)return;
  try{var at=Shared.packetModel.index(index,total()),pid=Shared.packetModel.pid(pidInput.text);expectedToken=tokenPrefix+':'+(++serial);var params={analysis_revision:host.analysisState.analysis_revision||host.analysisState.revision,packet_index:at,direction:direction,scan_limit:4096,client_token:expectedToken};if(pid!==null)params.pid=pid;pending=params;loading=true;feedback='Searching original source packets…';requested(params);}
  catch(error){feedback=String(error);loading=false;}
 }
 function receive(result){
  if(!expectedToken||(result.request||{}).client_token!==expectedToken)return;
  if(result.code){loading=false;feedback=result.message;expectedToken='';return;}
  if(result.source!==host.analysisState.source||result.analysis_revision!==(host.analysisState.analysis_revision||host.analysisState.revision)){loading=false;feedback='Packet source identity changed';expectedToken='';return;}
  if(result.found){packet=result;indexInput.text=String(result.packet_index);cursor=wantedByte;loading=false;feedback=(result.issues||[]).join('; ');expectedToken='';return;}
  if(result.next_index===null||result.next_index===undefined){loading=false;feedback='No matching PID before the source boundary';expectedToken='';return;}
  feedback='Searching packet '+result.next_index+'…';var token=expectedToken;Qt.callLater(function(){if(loading&&token===expectedToken)send(result.next_index,pending.direction,wantedByte);});
 }
 function cancel(){++serial;expectedToken='';loading=false;feedback='Search cancelled; previous packet retained';}
 function snapshot(){return {loading:loading,error:feedback,index:packet.packet_index,pid:(packet.header||{}).PID,raw_hex:packet.raw_hex,source:packet.source,revision:packet.analysis_revision,cursor:cursor};}
 Component.onCompleted:{pidInput.text=initialPid<0?'':Shared.packetModel.hex(initialPid,4);indexInput.text=String(initialIndex);send(initialIndex,'forward',initialByte);}
 ColumnLayout {
  anchors.fill:parent;spacing:5
  Flow {
   Layout.fillWidth:true;spacing:3
   Repeater {model:[{text:'<<',name:'First packet',command:'first'},{text:'<',name:'Previous packet',command:'previous'},{text:'>',name:'Next packet',command:'next'},{text:'>>',name:'Last packet',command:'last'}]
    delegate:Button{required property var modelData;text:modelData.text;Accessible.name:modelData.name;enabled:!view.loading;implicitWidth:30;implicitHeight:25
     onClicked:{var c=modelData.command,at=c==='first'?0:c==='last'?view.total()-1:Number(view.packet.packet_index===undefined?indexInput.text:view.packet.packet_index)+(c==='previous'?-1:1);view.send(at,c==='last'||c==='previous'?'backward':'forward');}
    }
   }
   Label{text:'Packet index';color:'#000';height:25;verticalAlignment:Text.AlignVCenter}
   TextField{id:indexInput;objectName:'packetIndex';width:96;height:25;selectByMouse:true;onAccepted:view.send(text,'forward')}
   Label{text:'PID';color:'#000';height:25;verticalAlignment:Text.AlignVCenter}
   TextField{id:pidInput;objectName:'packetPid';placeholderText:'All PIDs';width:92;height:25;selectByMouse:true;onAccepted:view.send(indexInput.text,'forward')}
   Button{text:'Search';enabled:!view.loading;implicitHeight:25;onClicked:view.send(indexInput.text,'forward')}
   Button{text:'Cancel';enabled:view.loading;implicitHeight:25;onClicked:view.cancel()}
  }
  Label {Layout.fillWidth:true;wrapMode:Text.WordWrap;color:'#000';font.family:'Tahoma';font.pixelSize:11;text:packet.found?'Packet '+packet.packet_index+' / '+(packet.source_packets-1)+' | file byte '+packet.file_offset+' | stride '+packet.framing_stride+' | '+(packet.in_analyzed_window?'analyzed window':'outside analyzed windows; raw source only'):''}
  GridLayout {
   Layout.fillWidth:true;columns:view.width>=750?4:2;columnSpacing:5;rowSpacing:2
   Repeater {model:Shared.packetModel.headerFields
    delegate:RowLayout{required property string modelData;Layout.fillWidth:true
     Label{text:modelData;color:'#000';font.family:'Tahoma';font.pixelSize:11;Layout.fillWidth:true}
     TextField {readOnly:true;selectByMouse:true;Layout.preferredWidth:70;implicitHeight:24;font.pixelSize:12;text:(view.packet.header||{})[modelData]===undefined?'':modelData==='PID'||modelData==='sync_byte'?Shared.packetModel.hex(view.packet.header[modelData],modelData==='PID'?4:2):String(view.packet.header[modelData])}
    }
   }
  }
  Flow {Layout.fillWidth:true;spacing:6
   Repeater {model:Object.keys(Shared.packetModel.colors)
    delegate:Rectangle{required property string modelData;width:legend.implicitWidth+8;height:20;color:Shared.packetModel.colors[modelData];Text{id:legend;anchors.centerIn:parent;text:modelData.replace('_',' ');font.family:'Tahoma';font.pixelSize:11;color:'#000'}}
   }
  }
  ScrollView {
   Layout.fillWidth:true;Layout.fillHeight:true;clip:true
   Grid {
    id:bytes;columns:16;spacing:1;focus:true;activeFocusOnTab:true
    Keys.onPressed:function(event){var next=event.key===Qt.Key_Home?0:event.key===Qt.Key_End?187:event.key===Qt.Key_Right?view.cursor+1:event.key===Qt.Key_Left?view.cursor-1:event.key===Qt.Key_Down?view.cursor+16:event.key===Qt.Key_Up?view.cursor-16:-1;if(next>=0){view.cursor=Math.max(0,Math.min(187,next));event.accepted=true;}}
    Repeater {model:view.byteRows
     delegate:Rectangle{required property var modelData;width:31;height:21;color:Shared.packetModel.colors[modelData.kind];border.width:view.cursor===modelData.offset?2:0;border.color:'#000'
      Text{anchors.centerIn:parent;text:modelData.hex;color:'#0000ff';font.family:'Courier New';font.pixelSize:13}
      TapHandler{onTapped:{view.cursor=modelData.offset;bytes.forceActiveFocus();}}
      ToolTip.visible:hover.hovered;ToolTip.text:'Packet byte '+modelData.offset+' | file byte '+(Number(view.packet.file_offset)+modelData.offset)+' | '+modelData.kind
      HoverHandler{id:hover}
     }
    }
   }
  }
  Flow {Layout.fillWidth:true;spacing:4
   Repeater {model:view.packet.section_links||[]
    delegate:Button{required property var modelData;text:modelData.name+' section — packets '+modelData.start_packet+'..'+modelData.end_packet;implicitHeight:25;onClicked:view.sectionActivated(modelData.id)}
   }
  }
  Label {Layout.fillWidth:true;wrapMode:Text.WordWrap;text:view.feedback;color:'#000';font.family:'Tahoma';font.pixelSize:11}
 }
}
