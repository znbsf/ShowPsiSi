import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../tauri/web/output-model.js" as Shared
Dialog {
 id:dialog;title:'Save / Copy';modal:true;width:Math.min(660,parent.width-32);anchors.centerIn:parent
 property var sourceState:({})
 property var context:({})
 property var options:[]
 property var selectedOutput:options[choices.currentIndex]||null
 signal saveRequested(var output)
 signal copyRequested(string text)
 function prepare(state,value){sourceState=state;context=value;options=Shared.outputModel.options(state,value);choices.currentIndex=0;copyPreview.text='';open();}
 background:Rectangle{color:'#efefef';border.color:'#808080'}
 contentItem:ColumnLayout {
  spacing:8
  Label{Layout.fillWidth:true;wrapMode:Text.WordWrap;color:'black';text:'Selected source only. Existing output and manifest are refused. PNG/WAV are derived previews.'}
  ComboBox{id:choices;objectName:'outputKind';Layout.fillWidth:true;model:dialog.options;textRole:'label'}
  Label{Layout.fillWidth:true;wrapMode:Text.WrapAnywhere;color:'black';text:dialog.selectedOutput?dialog.selectedOutput.scope:''}
  ScrollView{Layout.fillWidth:true;Layout.preferredHeight:120;TextArea{id:copyPreview;readOnly:true;selectByMouse:true;wrapMode:Text.WrapAnywhere;color:'black'}}
  RowLayout{Layout.fillWidth:true
   ClassicButton{text:'Copy selected field';enabled:!!(dialog.context.view||{}).copyField;onClicked:{copyPreview.text=Shared.outputModel.fieldText(dialog.context.view.copyField,(dialog.context.payload||{}).id||dialog.sourceState.source);dialog.copyRequested(copyPreview.text);}}
   ClassicButton{text:'Copy displayed hex';enabled:!!dialog.rawHex();onClicked:{copyPreview.text=Shared.outputModel.hexText(dialog.rawHex(),'displayed original bytes; a paged view may be partial');dialog.copyRequested(copyPreview.text);}}
   Item{Layout.fillWidth:true}
   ClassicButton{text:'Save…';enabled:!!dialog.selectedOutput;onClicked:{dialog.saveRequested(dialog.selectedOutput);dialog.close();}}
   ClassicButton{text:'Cancel';onClicked:dialog.close()}
  }
 }
 function rawHex(){var v=context.view||{},r=v.result||{};return v.raw_hex||(r.selected||{}).content&&r.selected.content.raw_hex||(r.content||{}).raw_hex||(r.module_page||{}).raw_hex||'';}
}
