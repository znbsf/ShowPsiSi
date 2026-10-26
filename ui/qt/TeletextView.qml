import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../tauri/web/teletext-model.js" as Shared
Pane {
 id:view
 required property var host
 property int initialPid:-1
 property var pids:Shared.teletextModel.pids(host.analysisState)
 property string pidText:''
 property string startText:'0'
 property string limitText:'65536'
 property var result:({})
 property var query:({})
 property var expected:({})
 property bool loading:false
 property string error:''
 property bool reveal:false
 property bool flash:true
 property Item focusOrigin:null
 readonly property var selectedCell:(result.cells||[])[page.selected]||null
 readonly property var selectedSource:Shared.teletextModel.source(result,selectedCell)
 signal requested(var params)
 signal packetActivated(int pid,real index)
 padding:6;background:Rectangle{color:'#efefef'}
 function nextRegion(back){if(page.activeFocus&&focusOrigin)focusOrigin.forceActiveFocus();else page.forceActiveFocus();}
 function request(q){var pid=Number(pidText),start=Number(startText),limit=Number(limitText);if(!pidText||!Number.isInteger(pid)||pid<0||pid>8190){error='Choose a valid Teletext PID (0..8190)';return;}if(!Number.isInteger(start)||start<0||!Number.isInteger(limit)||limit<1||limit>262144){error='Packet start must be nonnegative; scan limit is 1..262144';return;}query=q||{};var s=host.analysisState;expected=Object.assign({analysis_revision:s.analysis_revision||s.revision,pid:pid,start_packet:start,scan_limit:limit},query);if(s.selected_packet!=null)expected.at_packet=s.selected_packet;result={};loading=true;error='';requested(expected);}
 function receive(value){if(!loading)return;var request=value.request||value;if(request.pid!==expected.pid)return;if(value.message){loading=false;error=value.message;return;}if(value.analysis_revision!==expected.analysis_revision||value.source!==host.analysisState.source||!value.scan||value.scan.start_packet!==expected.start_packet)return;if(expected.page_hex!==undefined&&(value.page_hex!==expected.page_hex||value.subcode!==expected.subcode))return;if(expected.capture_index!==undefined&&value.capture_index!==expected.capture_index)return;result=value;page.selected=0;loading=false;error='';}
 function snapshot(){return {pid:Number(pidText),result:result,query:query,selected:page.selected,reveal:reveal,flash:flash,loading:loading,error:error};}
 function selectCell(index){page.select(index);}
 function selectCapture(delta){request(Object.assign({},query,{page_hex:result.page_hex,subcode:result.subcode,capture_index:result.capture_index+delta}));}
 function activateCell(cell){if(cell&&cell.packet_index!=null)packetActivated(Number(pidText),cell.packet_index);}
 Component.onCompleted:{pidText=initialPid>=0?String(initialPid):pids.length?String(pids[0]):'';if(pidText)request({});}
 ColumnLayout {
  anchors.fill:parent;spacing:4
  RowLayout{Layout.fillWidth:true
   Label{text:'PID';color:'#000';font.pixelSize:12}
   TextField{Layout.preferredWidth:80;implicitHeight:24;font.pixelSize:12;placeholderText:'0x0202';text:view.pidText;onTextEdited:view.pidText=text;onAccepted:view.request({})}
   ComboBox{visible:view.pids.length>0;Layout.preferredWidth:110;implicitHeight:24;font.pixelSize:12;model:view.pids.map(function(p){return '0x'+Shared.teletextModel.hex(p,4);});onActivated:{view.pidText=String(view.pids[currentIndex]);view.request({});}}
   Label{text:'Start packet';color:'#000';font.pixelSize:12}
   TextField{Layout.preferredWidth:85;implicitHeight:24;font.pixelSize:12;text:view.startText;onTextEdited:view.startText=text}
   Label{text:'Scan packets';color:'#000';font.pixelSize:12}
   TextField{Layout.preferredWidth:85;implicitHeight:24;font.pixelSize:12;text:view.limitText;onTextEdited:view.limitText=text}
   ClassicButton{text:'Scan';enabled:!view.loading;onClicked:view.request({})}
   ClassicButton{text:'Next range';enabled:!view.loading&&!!view.result.scan&&view.result.scan.next_start_packet!=null;onClicked:{view.startText=String(view.result.scan.next_start_packet);view.request({});}}
   ClassicButton{text:'Cancel';enabled:view.loading;onClicked:{view.loading=false;view.expected={};view.error='View request cancelled; bounded backend read may finish';}}
  }
  RowLayout{Layout.fillWidth:true
   ComboBox{Layout.fillWidth:true;implicitHeight:24;font.pixelSize:12;enabled:!view.loading;model:(view.result.pages||[]).map(function(p){return 'Page '+Shared.teletextModel.hex(p.page_hex)+' / subpage '+Shared.teletextModel.hex(p.subcode,4);});currentIndex:Math.max(0,(view.result.pages||[]).findIndex(function(p){return p.page_hex===view.result.page_hex&&p.subcode===view.result.subcode;}));onActivated:{var p=view.result.pages[currentIndex];view.request({page_hex:p.page_hex,subcode:p.subcode});}}
   ClassicButton{text:'Previous capture';enabled:!view.loading&&view.result.capture_index>0;onClicked:view.selectCapture(-1)}
   ClassicButton{text:'Next capture';enabled:!view.loading&&view.result.capture_index!==undefined&&view.result.capture_index+1<(view.result.captures||[]).length;onClicked:view.selectCapture(1)}
   CheckBox{text:'Reveal concealed';checked:view.reveal;onToggled:view.reveal=checked;font.pixelSize:12}
   CheckBox{text:'Flash phase on';checked:view.flash;onToggled:view.flash=checked;font.pixelSize:12}
  }
  Label{Layout.fillWidth:true;text:(view.result.cells||[]).length?Shared.teletextModel.title(view.result):'No acquired page';color:'#000';font.pixelSize:12;wrapMode:Text.WordWrap}
  SplitView{Layout.fillWidth:true;Layout.fillHeight:true;orientation:Qt.Horizontal
   ScrollView{SplitView.preferredWidth:490;SplitView.minimumWidth:250;clip:true;contentWidth:480;contentHeight:480
    TeletextPage{id:page;result:view.result;reveal:view.reveal;flash:view.flash;onCellActivated:function(cell){view.activateCell(cell);}}
   }
   ScrollView{SplitView.fillWidth:true;SplitView.minimumWidth:160;clip:true
    TextArea{readOnly:true;selectByMouse:true;text:Shared.teletextModel.details(view.result,view.selectedCell);font.family:'Consolas';font.pixelSize:11;color:'#000';wrapMode:TextEdit.NoWrap;background:Rectangle{color:'#fff';border.color:'#aaa'}}
   }
  }
  Flow{Layout.fillWidth:true;spacing:3
   Repeater{model:view.selectedSource?view.selectedSource.fragments:[];delegate:ClassicButton{required property var modelData;text:'Source packet '+modelData.packet_index+' byte '+modelData.packet_offset;onClicked:view.packetActivated(Number(view.pidText),modelData.packet_index)}}
  }
  Label{Layout.fillWidth:true;wrapMode:Text.WordWrap;font.pixelSize:11;color:'#000';text:view.error||(view.loading?'Reading original PES and captured pages…':view.result.status==='no_acquired_pages'?'No page header acquired in this scan range; choose the declared PID or another range.':view.result.scope||'Choose a declared Teletext PID or enter an explicit PID.')}
 }
}
