import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../tauri/web/carousel-model.js" as Shared
Pane {
 id:view
 required property var host
 property string initialSource:''
 property var sources:Shared.carouselModel.sources(host.analysisState)
 property string sourceId:''
 property var result:({})
 property var query:({})
 property var expected:({})
 property var history:[]
 property string tab:'Modules'
 property string contentView:'Summary'
 property bool loading:false
 property string error:''
 property string filter:''
 property int sortColumn:-1
 property bool descending:false
 property Item focusOrigin:null
 readonly property var displayedRows:Shared.carouselModel.filtered(Shared.carouselModel.rows(result,tab,history.map(function(h){return Shared.carouselModel.identity(Object.assign({source_id:sourceId},h.query));}).concat(Shared.carouselModel.identity(Object.assign({source_id:sourceId},query)))),filter,sortColumn,descending)
 readonly property var contentPage:result.content||result.module_page||null
 signal requested(var params)
 signal sectionActivated(string id,string path,real cutoff)
 padding:6;background:Rectangle{color:'#efefef'}
 function nextRegion(back){if(rows.activeFocus&&focusOrigin)focusOrigin.forceActiveFocus();else rows.forceActiveFocus();}
 function request(q){if(!sourceId)return;query=q||{};var state=host.analysisState;expected=Object.assign({analysis_revision:state.analysis_revision||state.revision,source_id:sourceId,limit:4096},query);if(state.selected_packet!=null)expected.at_packet=state.selected_packet;loading=true;error='';result={};requested(expected);}
 function receive(value){if(!loading)return;var identity=value.request||value;if(identity.source_id!==expected.source_id)return;if(value.message){loading=false;error=value.message;return;}if(value.analysis_revision!==expected.analysis_revision||value.source!==host.analysisState.source)return;if(value.module_id!==expected.module_id||value.announcement_epoch_order!==expected.announcement_epoch_order)return;if(expected.object_offset!==undefined&&(!value.object||value.object.offset!==expected.object_offset)&&value.content_status!=='unavailable_incomplete_module')return;var page=value.content||value.module_page;if(page&&page.offset!==(expected.offset||0))return;result=value;if(value.object){var actual=Object.assign({},query,{object_offset:value.object.offset});delete actual.object_key_hex;query=actual;}loading=false;error='';}
 function save(){return {query:query,result:result,tab:tab,contentView:contentView,index:rows.currentIndex,y:rows.contentY};}
 function open(row){if(!row||!row.query)return;var h=history.slice();h.push(save());if(h.length>32)h.shift();history=h;if(tab==='Modules')tab='BIOP List';request(row.query);}
 function back(){if(!history.length)return;var h=history.slice(),old=h.pop();history=h;loading=false;expected={};query=old.query;result=old.result;tab=old.tab;contentView=old.contentView;rows.currentIndex=old.index;Qt.callLater(function(){rows.contentY=old.y;});error='';}
 function snapshot(){return {source_id:sourceId,query:query,result:result,tab:tab,view:contentView,error:error,loading:loading,history:history.length};}
 Component.onCompleted:{sourceId=sources.some(function(s){return s.id===initialSource;})?initialSource:(sources[0]||{}).id||'';request({});}
 ColumnLayout {
  anchors.fill:parent;spacing:4
  RowLayout {Layout.fillWidth:true
   ComboBox {implicitHeight:24;font.family:'Tahoma';font.pixelSize:12;Layout.fillWidth:true;model:view.sources.map(function(s){return 'PID '+Shared.carouselModel.hex(s.pid)+' '+s.name+' '+s.id;});currentIndex:Math.max(0,view.sources.findIndex(function(s){return s.id===view.sourceId;}));onActivated:{view.sourceId=view.sources[currentIndex].id;view.history=[];view.tab='Modules';view.request({});}}
   ComboBox{implicitHeight:24;font.pixelSize:12;visible:!!view.result.gateway&&(view.result.gateway.download_candidates||[]).length>1;model:view.result.gateway?view.result.gateway.download_candidates.map(function(d){return Shared.carouselModel.hex(d);}):[];onActivated:{view.history=[];view.request({download_id:view.result.gateway.download_candidates[currentIndex]});}}
   ClassicButton{text:'Back';enabled:view.history.length>0;onClicked:view.back()}
   ClassicButton{text:'Refresh';enabled:!view.loading&&!!view.sourceId;onClicked:view.request(view.query)}
   ClassicButton{text:'Cancel';enabled:view.loading;onClicked:{view.loading=false;view.expected={};view.error='View request cancelled; bounded backend read may finish';}}
  }
  RowLayout{Layout.fillWidth:true
   Repeater{model:Shared.carouselModel.tabs;delegate:ClassicButton{required property string modelData;text:modelData;checkable:true;checked:view.tab===modelData;onClicked:{view.tab=modelData;view.filter='';view.sortColumn=-1;if(modelData==='OC Files'&&view.result.module_id===undefined&&!view.result.inventory)view.request(Object.assign({},view.query,{inventory:true}));}}}
  }
  RowLayout{Layout.fillWidth:true
   TextField{implicitHeight:24;font.pixelSize:12;Layout.fillWidth:true;placeholderText:'Filter loaded rows';text:view.filter;onTextEdited:view.filter=text}
   TextField{implicitHeight:24;font.pixelSize:12;id:findText;Layout.fillWidth:true;placeholderText:'Find in loaded content';onAccepted:findButton.clicked()}
   ClassicButton{id:findButton;text:'Find next';onClicked:{var from=contentArea.selectionEnd,index=contentArea.text.indexOf(findText.text,from);if(index<0)index=contentArea.text.indexOf(findText.text);if(findText.text&&index>=0){contentArea.forceActiveFocus();contentArea.select(index,index+findText.text.length);}else view.error='Text not found in loaded content';}}
  }
  Label{Layout.fillWidth:true;color:'#000';font.pixelSize:11;wrapMode:Text.WordWrap;text:view.result.source_id?Shared.carouselModel.title(view.result):'Choose an observed DSM-CC section'}
  ClassicGrid {
   id:rows;Layout.fillWidth:true;Layout.fillHeight:true;Layout.preferredHeight:170
   model:view.displayedRows;columns:Shared.carouselModel.headings(view.result,view.tab)
   onActivated:function(row){view.open(row);}
   onColumnClicked:function(index){view.descending=view.sortColumn===index?!view.descending:false;view.sortColumn=index;}
   emptyText:view.loading?'Loading…':!view.sources.length?'No observed DSM-CC source':'No matching objects. Check module status and diagnostics below.'
  }
  RowLayout{Layout.fillWidth:true
   Repeater{model:Shared.carouselModel.views;delegate:ClassicButton{required property string modelData;text:modelData;checkable:true;checked:view.contentView===modelData;onClicked:view.contentView=modelData}}
  }
  ScrollView{Layout.fillWidth:true;Layout.fillHeight:true;Layout.preferredHeight:190;clip:true
   TextArea{id:contentArea;readOnly:true;selectByMouse:true;text:Shared.carouselModel.body(view.result,view.contentView);font.family:'Consolas';font.pixelSize:12;color:'#000';wrapMode:TextEdit.NoWrap;background:Rectangle{color:'#fff';border.color:'#aaa'}}
  }
  RowLayout{Layout.fillWidth:true
   ClassicButton{text:'Previous bytes';enabled:!view.loading&&view.contentPage&&view.contentPage.offset>0;onClicked:view.request(Object.assign({},view.query,{offset:Math.max(0,view.contentPage.offset-4096)}))}
   Label{Layout.fillWidth:true;color:'#000';text:view.contentPage?view.contentPage.offset+'–'+(view.contentPage.offset+view.contentPage.length)+' / '+view.contentPage.total_bytes+' bytes; '+(view.contentPage.layer||'module'):'Select a module or object'}
   ClassicButton{text:'Next bytes';enabled:!view.loading&&view.contentPage&&view.contentPage.next_offset!=null;onClicked:view.request(Object.assign({},view.query,{offset:view.contentPage.next_offset}))}
  }
  Label{Layout.fillWidth:true;wrapMode:Text.WordWrap;font.pixelSize:11;color:'#000';text:view.error||(view.loading?'Loading bounded carousel evidence…':[view.result.content_status,view.result.biop?view.result.biop.error:'',view.result.scope].filter(function(s){return !!s;}).join('; ')||'No content selected')}
  ScrollView{Layout.fillWidth:true;Layout.preferredHeight:Math.min(52,sourceFlow.implicitHeight);clip:true
   Flow{id:sourceFlow;width:parent.width;spacing:3
   Repeater{model:(view.result.modules||[]).filter(function(m){return m.module_id===view.result.module_id;}).reduce(function(all,m){return all.concat(m.sources);},[]);delegate:ClassicButton{required property var modelData;text:modelData.role+' packet '+modelData.completion_packet;onClicked:view.sectionActivated(modelData.source_id,'section',view.result.at_packet)}}
  }
   }
}
}
