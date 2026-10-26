import QtQuick
import QtQuick.Controls
FocusScope {
 id:grid
 property var model:[]
 property var columns:[]
 property var columnWidths:[]
 property string emptyText:'No matching rows'
 property alias currentIndex:list.currentIndex
 property alias contentY:list.contentY
 signal activated(var row)
 signal columnClicked(int column)
 signal selected(var row)
 function columnWidth(index){return columnWidths[index]>0?columnWidths[index]:Math.max(90,width/Math.max(1,columns.length));}
 function resizeColumn(index,width){var next=columnWidths.slice();next[index]=Math.max(60,width);columnWidths=next;}
 readonly property real tableWidth:columns.reduce(function(total,_,i){return total+grid.columnWidth(i);},0)
 implicitHeight:180
 clip:true
 Rectangle{anchors.fill:parent;color:'#fff';border.color:'#888'}
 Item {
  id:header;width:parent.width;height:24;clip:true
  Row{x:-list.contentX
   Repeater{model:grid.columns
    delegate:ClassicButton {
     required property string modelData;required property int index
     text:modelData;width:grid.columnWidth(index);height:24;onClicked:grid.columnClicked(index)
     MouseArea{anchors.right:parent.right;anchors.top:parent.top;anchors.bottom:parent.bottom;width:6;cursorShape:Qt.SizeHorCursor
      property real originX:0;property real originWidth:0
      onPressed:function(mouse){originX=mapToItem(grid,mouse.x,0).x;originWidth=grid.columnWidth(index);}
      onPositionChanged:function(mouse){if(pressed)grid.resizeColumn(index,originWidth+mapToItem(grid,mouse.x,0).x-originX);}
     }
    }
   }
  }
 }
 ListView {
  id:list;anchors.left:parent.left;anchors.right:parent.right;anchors.top:header.bottom;anchors.bottom:parent.bottom;clip:true
  model:grid.model;contentWidth:grid.tableWidth;flickableDirection:Flickable.AutoFlickDirection
  focus:true;activeFocusOnTab:true;keyNavigationEnabled:true;highlightMoveDuration:0
  ScrollBar.vertical:ScrollBar{}
  ScrollBar.horizontal:ScrollBar{}
  Keys.onReturnPressed:if(currentIndex>=0)grid.activated(model[currentIndex])
  Keys.onPressed:function(event){if(event.key===Qt.Key_Home){currentIndex=count?0:-1;event.accepted=true;}else if(event.key===Qt.Key_End){currentIndex=count-1;event.accepted=true;}}
  delegate:ItemDelegate {
   id:entry;required property var modelData;required property int index
   width:grid.tableWidth;height:23;padding:0
   background:Rectangle{color:list.currentIndex===entry.index?'#dceafd':'#fff'}
   contentItem:Row {
    Repeater{model:entry.modelData.values
     delegate:Label {
      required property var modelData;required property int index
      width:grid.columnWidth(index);height:23;padding:4;text:modelData;color:'#000';font.family:'Tahoma';font.pixelSize:12;elide:Text.ElideRight
      background:Rectangle{color:'transparent';border.color:'#ddd'}
      ToolTip.visible:hover.hovered;ToolTip.text:text;HoverHandler{id:hover}
     }
    }
   }
   onClicked:{list.currentIndex=index;list.forceActiveFocus();grid.selected(modelData);}
   onDoubleClicked:grid.activated(modelData)
  }
  Label{visible:!list.count;anchors.centerIn:parent;width:parent.width-20;wrapMode:Text.WordWrap;color:'#000';text:grid.emptyText;font.family:'Tahoma';font.pixelSize:12}
 }
}

