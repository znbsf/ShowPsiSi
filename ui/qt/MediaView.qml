import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../tauri/web/media-model.js" as Shared
Pane {
 id:view
 required property var host
 property int initialPid:-1
 property string initialTab:'PES'
 property var sourceState:({})
 property real sourceRevision:0
 property string sourcePath:''
 property var pids:Shared.mediaModel.pids(sourceState)
 property int pid:-1
 property string tab:'PES'
 property real start:0
 property int scanLimit:65536
 property var result:({})
 property var inventory:[]
 property int pageOffset:0
 property int selectedIndex:-1
 property int cursor:0
 property var preview:({})
 property int frameIndex:0
 property bool loading:false
 property bool decoding:false
 property bool cancelling:false
 property string error:''
 property string requestToken:''
 property var expectedQuery:({})
 property var expectedDecode:({})
 property string audioExpected:''
 property bool audioPending:false
 property var audioState:({})
 property Item focusOrigin:null
 readonly property var displayedRows:Shared.mediaModel.rows(inventory)
 readonly property var contentPage:result.selected?result.selected.content:null
 readonly property var sourceByte:Shared.mediaModel.sourceAt(result,cursor)
 readonly property var frame:preview.kind==='video'?(preview.frames||[])[frameIndex]||null:null
 signal requested(string method,var params)
 signal packetActivated(int pid,real index,int byteOffset)
 padding:6;background:Rectangle{color:'#efefef'}
 function base(){var p={analysis_revision:sourceRevision,pid:pid,start_packet:start,scan_limit:scanLimit};if(sourceState.selected_packet!=null)p.at_packet=sourceState.selected_packet;return p;}
 function nextRegion(back){if(records.activeFocus&&focusOrigin)focusOrigin.forceActiveFocus();else records.forceActiveFocus();}
 function read(q,replaceRows){if(pid<0)return;expectedQuery=Object.assign(base(),{pes_offset:pageOffset,pes_limit:100},q||{});expectedQuery._replace_rows=!!replaceRows;var p=Object.assign({},expectedQuery);delete p._replace_rows;loading=true;error='';requested('query_pes',p);}
 function receive(method,value){
  if(method==='query_pes'){
   if(!loading)return;var q=value.request||{};if(value.message){if(q.pid!==expectedQuery.pid||q.pes_index!==expectedQuery.pes_index)return;loading=false;error=value.message;return;}
   if(value.analysis_revision!==sourceRevision||value.source!==sourcePath||value.pid!==expectedQuery.pid||value.pes_offset!==expectedQuery.pes_offset||!value.scan||value.scan.start_packet!==expectedQuery.start_packet)return;
   if(expectedQuery.pes_index!==undefined){if(!value.selected||value.selected.index!==expectedQuery.pes_index||value.selected.content.offset!==(expectedQuery.offset||0)||value.selected.content.layer!==(expectedQuery.layer==='es'?'collected_es_payload':'original_pes'))return;}else if(value.selected)return;
   result=value;if(expectedQuery._replace_rows)inventory=value.pes;cursor=0;loading=false;error='';return;
  }
  if(method==='decode_media'){
   var request=value.request||value;if(request.request_token!==requestToken)return;
   if(value.message){decoding=false;cancelling=false;error=value.message;return;}
   if(value.analysis_revision!==sourceRevision||value.source!==sourcePath||value.pid!==pid||value.from_pes_index!==selectedIndex)return;
   preview=value;frameIndex=0;decoding=false;cancelling=false;error='';return;
  }
  if(method==='audio_control'){
   var aq=value.request||{};if(aq.client_token!==audioExpected)return;audioPending=false;
   if(value.message){error=value.message;return;}if(value.preview_token!==preview.preview_token)return;audioState=value;if(!value.matching_preview)error='Preview superseded; decode this source again';if(!value.playing&&!value.paused)audioTimer.stop();
  }
 }
 function audio(action){if(!preview.preview_token||(action==='status'&&audioPending))return;audioExpected='audio-'+Date.now()+'-'+Math.random().toString(16).slice(2);audioPending=true;requested('audio_control',{analysis_revision:sourceRevision,preview_token:preview.preview_token,action:action,client_token:audioExpected});}
 function stop(preservePosition){videoTimer.stop();audioTimer.stop();if(!preservePosition)frameIndex=0;if(preview.preview_token)audio('stop');if(decoding&&!cancelling){cancelling=true;requested('cancel_media',{analysis_revision:sourceRevision,request_token:requestToken});}audioState={};}
 function selectByte(value){cursor=Math.max(0,Math.min((contentPage?contentPage.length:1)-1,value));rawText.cursorPosition=cursor*3;}
 function jumpSource(){if(sourceByte)packetActivated(pid,sourceByte.packet_index,sourceByte.packet_offset);}
 function setInput(next,from,limit){pidInput.text=String(next);startInput.text=String(from);limitInput.text=String(limit);loadInputs();}
 function selectPes(index){if(selectedIndex!==index){stop();preview={};}selectedIndex=index;read({pes_index:index,layer:tab==='ES'?'es':'pes'},false);}
 function changePage(offset){stop();preview={};selectedIndex=-1;pageOffset=offset;inventory=[];result={};read({},true);}
 function loadInputs(){var next=Number(pidInput.text),from=Number(startInput.text),limit=Number(limitInput.text);if(!Number.isInteger(next)||next<0||next>8190||!Number.isInteger(from)||from<0||!Number.isInteger(limit)||limit<1||limit>262144){error='Choose PID 0..8190 and a bounded packet range';return;}stop();preview={};pid=next;start=from;scanLimit=limit;selectedIndex=-1;pageOffset=0;inventory=[];result={};read({},true);}
 function decode(){if(selectedIndex<0||decoding)return;stop();preview={};frameIndex=0;requestToken='media-'+Date.now()+'-'+Math.random().toString(16).slice(2);expectedDecode=Object.assign(base(),{from_pes_index:selectedIndex,kind:tab.toLowerCase(),format:formatInput.currentText,request_token:requestToken});decoding=true;cancelling=false;error='';requested('decode_media',expectedDecode);}
 function pause(){if(videoTimer.running)videoTimer.stop();else audio('pause');}
 function play(){if(tab==='Video'&&preview.kind==='video'){if(frameIndex+1>=preview.frames.length)frameIndex=0;videoTimer.start();}else if(tab==='Audio'&&preview.kind==='audio'){audio(audioState.paused?'resume':'play');audioTimer.start();}}
 function setTab(next){stop();tab=next;if(selectedIndex>=0&&(tab==='PES'||tab==='ES'))read({pes_index:selectedIndex,layer:tab.toLowerCase()},false);}
 function snapshot(){return {pid:pid,result:result,tab:tab,selected:selectedIndex,cursor:cursor,preview:Shared.mediaModel.snapshotPreview(preview),frame_index:frameIndex,frame_image_status:videoImage.status,frame_width:videoImage.sourceSize.width,frame_height:videoImage.sourceSize.height,playing:videoTimer.running||!!audioState.playing,paused:!!audioState.paused,decoding:decoding,cancelling:cancelling,error:error,loading:loading};}
 Component.onCompleted:{sourceState=JSON.parse(JSON.stringify(host.analysisState));sourceRevision=sourceState.analysis_revision||sourceState.revision;sourcePath=sourceState.source;pid=initialPid>=0?initialPid:pids.length?pids[0].pid:-1;pidInput.text=pid<0?'':String(pid);tab=initialTab;if(pid>=0)read({},true);}
 Component.onDestruction:stop()
 Timer{id:videoTimer;interval:100;repeat:true;onTriggered:{if(view.frameIndex+1<(view.preview.frames||[]).length)view.frameIndex++;else stop();}}
 Timer{id:audioTimer;interval:200;repeat:true;onTriggered:view.audio('status')}
 ScrollView {
  id:mediaScroll
  anchors.fill:parent;clip:true;contentWidth:availableWidth;contentHeight:Math.max(500,availableHeight)
  ColumnLayout {
   width:mediaScroll.availableWidth;height:Math.max(500,mediaScroll.availableHeight);spacing:4
   Flow{Layout.fillWidth:true;spacing:4
    Label{text:'PID';color:'#000';height:24;verticalAlignment:Text.AlignVCenter}
    TextField{id:pidInput;width:80;implicitHeight:24;font.pixelSize:12;placeholderText:'0x0031';onAccepted:view.loadInputs()}
    ComboBox{width:180;implicitHeight:24;font.pixelSize:12;model:view.pids.map(function(p){return Shared.mediaModel.hex(p.pid)+' '+p.codecs.join('/')+' Programs '+p.programs.join(',');});onActivated:pidInput.text=String(view.pids[currentIndex].pid)}
    Label{text:'Start packet';color:'#000';height:24;verticalAlignment:Text.AlignVCenter}
    TextField{id:startInput;width:80;implicitHeight:24;text:'0';font.pixelSize:12}
    Label{text:'Scan packets';color:'#000';height:24;verticalAlignment:Text.AlignVCenter}
    TextField{id:limitInput;width:80;implicitHeight:24;text:'65536';font.pixelSize:12}
    ClassicButton{text:'Load / scan';enabled:!view.loading&&!view.decoding;onClicked:view.loadInputs()}
    ClassicButton{text:'Cancel decode';enabled:view.decoding&&!view.cancelling;onClicked:view.stop()}
   }
   RowLayout{Layout.fillWidth:true
    Repeater{model:Shared.mediaModel.tabs;delegate:ClassicButton{required property string modelData;text:modelData;checkable:true;checked:view.tab===modelData;onClicked:view.setTab(modelData)}}
   }
   ClassicGrid{id:records;Layout.fillWidth:true;Layout.fillHeight:true;Layout.preferredHeight:135;Layout.minimumHeight:65;model:view.displayedRows;columns:Shared.mediaModel.columns;onSelected:function(row){view.selectPes(row.pes.index);}onActivated:function(row){view.selectPes(row.pes.index);}emptyText:view.loading?'Loading original PES…':'No complete PES observed in this bounded scan range'}
   Flow{Layout.fillWidth:true;spacing:4
    ClassicButton{text:'Previous PES page';enabled:!view.loading&&view.pageOffset>0;onClicked:view.changePage(Math.max(0,view.pageOffset-100))}
    Label{text:view.pageOffset+'–'+(view.pageOffset+view.inventory.length)+' / '+(view.result.pes_total||0)+' PES';height:24;verticalAlignment:Text.AlignVCenter;color:'#000';font.pixelSize:12}
    ClassicButton{text:'Next PES page';enabled:!view.loading&&view.result.pes_next_offset!=null;onClicked:view.changePage(view.result.pes_next_offset)}
    ComboBox{id:formatInput;width:120;implicitHeight:24;font.pixelSize:12;model:Shared.mediaModel.formats}
    ClassicButton{text:'Decode selected source';enabled:!view.loading&&!view.decoding&&view.selectedIndex>=0&&(view.tab==='Video'||view.tab==='Audio')&&!!view.result.decoder&&view.result.decoder.available;onClicked:view.decode()}
    ClassicButton{text:'Play';enabled:!view.decoding&&(view.tab==='Video'&&view.preview.kind==='video'&&view.preview.frame_count>0||view.tab==='Audio'&&view.preview.kind==='audio'&&!!view.preview.pcm);onClicked:view.play()}
    ClassicButton{text:'Pause';enabled:videoTimer.running||!!view.audioState.playing;onClicked:view.pause()}
    ClassicButton{text:'Stop';enabled:videoTimer.running||!!view.audioState.playing||!!view.audioState.paused||view.audioPending;onClicked:view.stop()}
   }
   Label{Layout.fillWidth:true;text:Shared.mediaModel.location(view.result);wrapMode:Text.WordWrap;color:'#000';font.pixelSize:12}
   SplitView{Layout.fillWidth:true;Layout.fillHeight:true;Layout.preferredHeight:200;Layout.minimumHeight:120;orientation:Qt.Horizontal
    Item{SplitView.preferredWidth:430;SplitView.minimumWidth:200
     ColumnLayout{anchors.fill:parent;spacing:3
      ScrollView{visible:view.tab==='PES'||view.tab==='ES';Layout.fillWidth:true;Layout.fillHeight:true;clip:true
       TextArea{id:rawText;readOnly:true;selectByMouse:true;text:Shared.mediaModel.raw(view.result);color:'#000';font.family:'Consolas';font.pixelSize:12;wrapMode:TextEdit.NoWrap;onCursorPositionChanged:view.cursor=Math.max(0,Math.min((view.contentPage?view.contentPage.length:1)-1,Math.floor(cursorPosition/3)));background:Rectangle{color:'#fff';border.color:'#aaa'}}
      }
      Flow{visible:view.tab==='PES'||view.tab==='ES';Layout.fillWidth:true;spacing:3
       ClassicButton{text:'Previous bytes';enabled:!view.loading&&!!view.contentPage&&view.contentPage.offset>0;onClicked:view.read({pes_index:view.selectedIndex,layer:view.tab.toLowerCase(),offset:Math.max(0,view.contentPage.offset-4096)},false)}
       ClassicButton{text:'Next bytes';enabled:!view.loading&&!!view.contentPage&&view.contentPage.next_offset!=null;onClicked:view.read({pes_index:view.selectedIndex,layer:view.tab.toLowerCase(),offset:view.contentPage.next_offset},false)}
       ClassicButton{text:'Selected byte source packet';enabled:!!view.sourceByte;onClicked:view.jumpSource()}
      }
      Rectangle{visible:view.tab==='Video';Layout.fillWidth:true;Layout.fillHeight:true;color:view.frame?'#000':'#efefef'
       Image{id:videoImage;anchors.fill:parent;source:view.frame?'data:image/png;base64,'+view.frame.data_base64:'';fillMode:Image.PreserveAspectFit;cache:false}
       Label{anchors.centerIn:parent;visible:!view.frame;text:'Decode the explicitly selected PES source to show real video';width:parent.width-20;wrapMode:Text.WordWrap;color:'#000';font.pixelSize:12}
      }
      Canvas{id:wave;visible:view.tab==='Audio';Layout.fillWidth:true;Layout.fillHeight:true
       onWidthChanged:requestPaint();onHeightChanged:requestPaint();onVisibleChanged:requestPaint()
       Connections{target:view;function onPreviewChanged(){wave.requestPaint();}}
       onPaint:{var ctx=getContext('2d');ctx.reset();ctx.fillStyle='#000';ctx.fillRect(0,0,width,height);var bins=view.preview.pcm?view.preview.pcm.waveform:[];ctx.strokeStyle='#00dd44';ctx.beginPath();bins.forEach(function(bin,i){var x=(i+.5)*width/bins.length;ctx.moveTo(x,height/2-bin.max/32768*height/2);ctx.lineTo(x,height/2-bin.min/32768*height/2);});ctx.stroke();}
      }
      Label{visible:view.tab==='Video'||view.tab==='Audio';Layout.fillWidth:true;wrapMode:Text.WordWrap;color:'#000';font.pixelSize:11;text:view.preview.kind===view.tab.toLowerCase()?(view.preview.timing_basis||view.preview.pcm.scope||view.preview.scope):'Decode the explicitly selected PES source. PCM is mono 48000 Hz, amplitude ±32768.'}
     }
    }
    ScrollView{SplitView.fillWidth:true;SplitView.minimumWidth:160;clip:true
     TextArea{readOnly:true;selectByMouse:true;text:Shared.mediaModel.details(view.result,view.preview);color:'#000';font.family:'Consolas';font.pixelSize:11;wrapMode:TextEdit.NoWrap;background:Rectangle{color:'#fff';border.color:'#aaa'}}
    }
   }
   Label{Layout.fillWidth:true;wrapMode:Text.WordWrap;color:'#000';font.pixelSize:11;text:view.error||(view.cancelling?'Cancelling the matching decoder…':view.decoding?'Decoding bounded selected ES…':view.loading?'Reading original PES…':((view.tab==='Video'||view.tab==='Audio')&&(!view.result.decoder||!view.result.decoder.available)?'Configure the pinned external decoder before decoding; original PES/ES remains readable.':view.result.scope||'Select a PID, then a PES source.'))}
  }
 }
}
