import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../tauri/web/packet-model.js" as Shared
Pane {
 id:view
 required property var host
 property bool timing:false
 property var page:({})
 property bool loading:false
 property string error:''
 property var expected:({})
 readonly property var clock:timing?(page.summary||{}):((host.analysisState.transport_summary||{}).timing||{})
 signal requested(string method,var params)
 signal packetActivated(int pid,real index)
 padding:6;background:Rectangle{color:'#efefef'}
 function request(offset){loading=true;error='';expected={analysis_revision:host.analysisState.analysis_revision||host.analysisState.revision,offset:offset};var args={analysis_revision:expected.analysis_revision,offset:offset,limit:100};if(!timing){args.sort='packets';args.descending=true;}requested(timing?'query_timing':'query_transport',args);}
 function receive(method,result){if(method!==(timing?'query_timing':'query_transport'))return;if(result.message){loading=false;error=result.message;return;}if(result.analysis_revision!==expected.analysis_revision||result.source!==host.analysisState.source||result.offset!==expected.offset||(!timing&&(result.sort!=='packets'||!result.descending)))return;page=result;loading=false;}
 function number(n){return n===null||n===undefined?'Unknown':Number(n).toLocaleString(Qt.locale('en_US'),'f',3).replace(/\.000$/,'');}
 function snapshot(){return {timing:timing,loading:loading,error:error,total:page.total,rows:page.items||[],summary:page.summary||{}};}
 Component.onCompleted:request(0)
 ColumnLayout {
  anchors.fill:parent;spacing:4
  TabBar {Layout.fillWidth:true;currentIndex:view.timing?1:0
   TabButton{text:'Bitrate';onClicked:if(view.timing){view.timing=false;view.page={};view.request(0);}}
   TabButton{text:'Timing';onClicked:if(!view.timing){view.timing=true;view.page={};view.request(0);}}
  }
  Label {Layout.fillWidth:true;wrapMode:Text.WordWrap;color:'#000';font.pixelSize:11;text:(host.analysisState.transport_summary||{}).rate_basis+'\nMeasured '+view.number(view.clock.measured_bitrate_bps)+' bps | PCR PID '+(view.clock.primary_pcr_pid==null?'Unknown':Shared.packetModel.hex(view.clock.primary_pcr_pid,4))+' | trusted duration '+view.number(view.clock.measured_duration_seconds)+' s\nCC errors '+view.number(view.clock.continuity_error_packets)+' | PCR jumps '+view.number(view.clock.pcr_jumps)+' | discontinuities '+view.number(view.clock.pcr_discontinuities)+' | wraps '+view.number(view.clock.pcr_wraps)+' | invalid PCR '+view.number(view.clock.invalid_pcr_fields)}
  Label {Layout.fillWidth:true;wrapMode:Text.WordWrap;color:'#000';font.pixelSize:11;text:(view.clock.measurement_scope||'')+' '+(view.clock.duration_scope||'')+(view.clock.samples_truncated?' Raw samples limited to first 4096; counters cover all observations.':'')}
  RowLayout {Layout.fillWidth:true
   Repeater {model:view.timing?['PID','Packet','PCR (27 MHz ticks)','Delta (ticks)','Status']:['PID','#of packets','PacketRate (%)','Bitrate (bps)','Share']
    delegate:Label{required property string modelData;text:modelData;color:'#000';font.pixelSize:11;Layout.fillWidth:true;Layout.preferredWidth:1}
   }
  }
  ListView {
   id:rows;Layout.fillWidth:true;Layout.fillHeight:true;clip:true;model:view.page.items||[];activeFocusOnTab:true;ScrollBar.vertical:ScrollBar{}
   function activate(){var row=model[currentIndex];if(row)view.packetActivated(row.pid,view.timing?row.packet_index:row.first_packet);}
   Keys.onReturnPressed:activate()
   delegate:ItemDelegate {
    required property var modelData;required property int index;width:rows.width;height:29;padding:3
    background:Rectangle{color:rows.currentIndex===index?'#dceafd':'#fff';border.color:'#ddd'}
    contentItem:RowLayout {spacing:4
     Repeater {model:view.timing?[Shared.packetModel.hex(modelData.pid,4),String(modelData.packet_index),String(modelData.pcr_27mhz),view.number(modelData.delta_27mhz),modelData.status]:[Shared.packetModel.hex(modelData.pid,4),view.number(modelData.packets),view.number(modelData.packet_fraction*100),view.number(modelData.bitrate_bps),'']
      delegate:Label{required property var modelData;text:modelData;color:'#000';font.family:'Tahoma';font.pixelSize:11;elide:Text.ElideRight;Layout.fillWidth:true;Layout.preferredWidth:1}
     }
    }
    Rectangle{visible:!view.timing;anchors.right:parent.right;anchors.rightMargin:4;anchors.verticalCenter:parent.verticalCenter;width:parent.width*.19;height:16;color:'#e0e0e0';Rectangle{width:parent.width*Math.max(0,Math.min(1,modelData.packet_fraction));height:parent.height;color:'#00a000'}}
    onClicked:{rows.currentIndex=index;rows.forceActiveFocus();}
    onDoubleClicked:{rows.currentIndex=index;rows.activate();}
   }
   Label{visible:!rows.count&&!view.loading;anchors.centerIn:parent;text:view.timing?'No observed PCR samples. Rate Unknown.':'No observed PID rows.';color:'#000'}
  }
  RowLayout {Layout.fillWidth:true
   Button{text:'Previous';enabled:!view.loading&&view.page.offset>0;onClicked:view.request(Math.max(0,view.page.offset-100))}
   Label{color:'#000';text:(view.page.total?Number(view.page.offset)+1:0)+'–'+(Number(view.page.offset||0)+(view.page.items||[]).length)+' / '+(view.page.total||0)}
   Button{text:'Next';enabled:!view.loading&&view.page.next_offset!==null&&view.page.next_offset!==undefined;onClicked:view.request(view.page.next_offset)}
   Button{text:'Refresh';enabled:!view.loading;onClicked:view.request(view.page.offset||0)}
  }
  Label{Layout.fillWidth:true;color:'#000';wrapMode:Text.WordWrap;font.pixelSize:11;text:view.error||(view.loading?'Loading…':'Double-click / Enter: original source packet')}
 }
}
