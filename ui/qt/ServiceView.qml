import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../tauri/web/service-model.js" as Shared
Pane {
 id:view
 property Item focusOrigin:null
 function nextRegion(back){if(rows.activeFocus&&focusOrigin)focusOrigin.forceActiveFocus();else rows.forceActiveFocus();}
 required property var host
 property var initialService:null
 property var services:host.analysisState.services||[]
 property int serviceIndex:0
 property string tab:'Service'
 property var result:({})
 property var expected:({})
 property bool loading:false
 property string error:''
 readonly property var displayedRows:Shared.serviceModel.rows(result,tab)
 signal requested(var params)
 signal sectionActivated(string id,string path,real cutoff)
 padding:6;background:Rectangle{color:'#efefef'}
 function request(offset){var s=services[serviceIndex];if(!s)return;var state=host.analysisState;var params={analysis_revision:state.analysis_revision||state.revision,original_network_id:s.onid,transport_stream_id:s.ts_id,service_id:s.id,event_offset:offset,event_limit:100};if(state.selected_packet!=null)params.at_packet=state.selected_packet;expected=params;loading=true;error='';requested(params);}
 function receive(value){
  if(value.message){var request=value.request||{};if(request.original_network_id!==expected.original_network_id||request.transport_stream_id!==expected.transport_stream_id||request.service_id!==expected.service_id)return;loading=false;error=value.message;return;}
  var i=value.identity||{};if(value.analysis_revision!==expected.analysis_revision||value.source!==host.analysisState.source||i.original_network_id!==expected.original_network_id||i.transport_stream_id!==expected.transport_stream_id||i.service_id!==expected.service_id||value.event_offset!==expected.event_offset)return;
  result=value;loading=false;error='';
 }
 function snapshot(){return {identity:result.identity,tab:tab,loading:loading,error:error,result:result,selected:rows.currentIndex};}
 Component.onCompleted:{if(initialService){var index=services.findIndex(function(s){return s.onid===initialService.onid&&s.ts_id===initialService.ts_id&&s.id===initialService.id;});if(index>=0)serviceIndex=index;}request(0);}
 ColumnLayout {
  anchors.fill:parent;spacing:4
  RowLayout {Layout.fillWidth:true
   Label{text:'Service';color:'#000'}
   ComboBox {Layout.fillWidth:true;currentIndex:view.serviceIndex;model:view.services.map(function(s){return (s.name||'Program')+' — ONID '+Shared.serviceModel.hex(s.onid)+' TSID '+Shared.serviceModel.hex(s.ts_id)+' SID '+Shared.serviceModel.hex(s.id);});onActivated:{view.serviceIndex=currentIndex;view.result={};view.request(0);}}
   Button{text:'Refresh';enabled:!view.loading&&view.services.length>0;onClicked:view.request(view.expected.event_offset||0)}
  }
  TabBar {Layout.fillWidth:true
   Repeater {model:Shared.serviceModel.tabs
    delegate:TabButton{required property string modelData;text:modelData;onClicked:view.tab=modelData}
   }
  }
  Label{Layout.fillWidth:true;wrapMode:Text.WordWrap;color:'#000';font.pixelSize:11;text:(view.result.scope||(!view.services.length?'No complete actual SDT service identity observed':'Choose a service'))+(view.result.identity?' | ONID '+Shared.serviceModel.hex(view.result.identity.original_network_id)+' TSID '+Shared.serviceModel.hex(view.result.identity.transport_stream_id)+' SID '+Shared.serviceModel.hex(view.result.identity.service_id)+' | analysis '+view.result.analysis_revision+' | cutoff packet '+view.result.at_packet:'')}
  RowLayout {Layout.fillWidth:true
   Repeater{model:Shared.serviceModel.columns(view.tab)
    delegate:Label{required property string modelData;text:modelData;color:'#000';font.pixelSize:11;Layout.fillWidth:true;Layout.preferredWidth:1}
   }
  }
  ListView {
   id:rows;Layout.fillWidth:true;Layout.fillHeight:true;clip:true;activeFocusOnTab:true;model:view.displayedRows;ScrollBar.vertical:ScrollBar{}
   function activate(){var row=model[currentIndex];if(row&&row.source_id)view.sectionActivated(row.source_id,row.path||'section',view.result.at_packet);}
   Keys.onReturnPressed:activate()
   delegate:ItemDelegate {
    required property var modelData;required property int index;width:rows.width;height:28;padding:3
    background:Rectangle{color:rows.currentIndex===index?'#dceafd':'#fff';border.color:'#ddd'}
    contentItem:RowLayout {spacing:6
     Repeater{model:modelData.values
      delegate:Label{required property var modelData;text:modelData;color:'#000';font.family:'Tahoma';font.pixelSize:12;elide:Text.ElideRight;Layout.fillWidth:true;Layout.preferredWidth:1;ToolTip.visible:hover.hovered;ToolTip.text:text;HoverHandler{id:hover}}
     }
    }
    onClicked:{rows.currentIndex=index;rows.forceActiveFocus();}
    onDoubleClicked:{rows.currentIndex=index;rows.activate();}
   }
   Label{visible:!rows.count&&!view.loading;anchors.centerIn:parent;width:parent.width-20;wrapMode:Text.WordWrap;color:'#000';text:view.tab==='Applications'?'No declared application carriage observed; execution is not evaluated.':'No matching observed '+view.tab+' rows at this cutoff.'}
  }
  RowLayout{visible:view.tab==='EPG';Layout.fillWidth:true
   Button{text:'Previous';enabled:!view.loading&&view.result.event_offset>0;onClicked:view.request(Math.max(0,view.result.event_offset-100))}
   Label{color:'#000';text:(view.result.event_offset||0)+' / '+(view.result.event_total||0)+' events'}
   Button{text:'Next';enabled:!view.loading&&view.result.event_next_offset!=null;onClicked:view.request(view.result.event_next_offset)}
  }
  Label{Layout.fillWidth:true;wrapMode:Text.WordWrap;color:'#000';font.pixelSize:11;text:view.error||(view.loading?'Loading scoped service…':(view.result.warnings||[]).join('; '))}
  Label{Layout.fillWidth:true;wrapMode:Text.WordWrap;color:'#000';font.pixelSize:11;text:'Double-click / Enter: exact source section. Close it to return here.'}
 }
}
