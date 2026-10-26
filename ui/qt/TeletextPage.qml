import QtQuick
import "../tauri/web/teletext-model.js" as Shared
Item {
 id:page
 property var result:({})
 property int selected:0
 property bool reveal:false
 property bool flash:true
 signal cellActivated(var cell)
 width:480;height:480;focus:true;activeFocusOnTab:true;clip:true
 function select(index){selected=Math.max(0,Math.min((result.cells||[]).length-1,index));}
 Keys.onPressed:function(event){var offsets={};offsets[Qt.Key_Left]=-1;offsets[Qt.Key_Right]=1;offsets[Qt.Key_Up]=-40;offsets[Qt.Key_Down]=40;if(offsets[event.key]){select(selected+offsets[event.key]);event.accepted=true;}else if(event.key===Qt.Key_Home){select(Math.floor(selected/40)*40);event.accepted=true;}else if(event.key===Qt.Key_End){select(Math.floor(selected/40)*40+39);event.accepted=true;}else if(event.key===Qt.Key_Return||event.key===Qt.Key_Enter){if((result.cells||[])[selected])cellActivated(result.cells[selected]);event.accepted=true;}}
 Rectangle{anchors.fill:parent;color:'#000'}
 Repeater{model:page.result.cells||[]
  delegate:Rectangle {
   id:cell
   required property var modelData;required property int index
   x:modelData.column*12;y:modelData.row*20;width:12;height:20;clip:true
   color:Shared.teletextModel.colours[modelData.background]
   property bool painted:Shared.teletextModel.visible(modelData,page.result,page.reveal,page.flash)
   property bool doubleHeight:modelData.role===3||modelData.role===4
   Text{visible:cell.painted&&cell.modelData.kind!==5;text:Shared.teletextModel.glyph(cell.modelData);color:Shared.teletextModel.colours[cell.modelData.foreground];font.family:'Consolas';font.pixelSize:16;width:12;height:20;transform:Scale{yScale:cell.doubleHeight?2:1}
   y:cell.modelData.role===4?-20:0;verticalAlignment:Text.AlignVCenter;horizontalAlignment:Text.AlignHCenter}
   Canvas {
    id:mosaic;anchors.fill:parent;visible:cell.painted&&cell.modelData.kind===5
    onVisibleChanged:requestPaint()
    Connections{target:cell;function onModelDataChanged(){mosaic.requestPaint();}}
    onPaint:{var ctx=getContext('2d');ctx.reset();ctx.clearRect(0,0,width,height);var full=cell.doubleHeight?height*2:height,offset=cell.modelData.role===4?-height:0,gap=cell.modelData.separated?1:0;ctx.fillStyle=Shared.teletextModel.colours[cell.modelData.foreground];for(var bit=0;bit<6;++bit)if((cell.modelData.mosaic_mask>>bit)&1)ctx.fillRect((bit%2)*width/2+gap,Math.floor(bit/2)*full/3+offset+gap,width/2-gap*2,full/3-gap*2);}
   }
   Rectangle{anchors.fill:parent;color:'transparent';border.color:page.selected===cell.index?'#00aaff':'transparent';border.width:1}
   MouseArea{anchors.fill:parent;onClicked:{page.selected=cell.index;page.forceActiveFocus();}onDoubleClicked:page.cellActivated(cell.modelData)}
  }
 }
}
