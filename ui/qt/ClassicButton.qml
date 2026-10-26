import QtQuick
import QtQuick.Controls
Button {
 id:button
 implicitHeight:24;implicitWidth:Math.max(48,contentItem.implicitWidth+14);padding:3
 font.family:'Tahoma';font.pixelSize:12
 contentItem:Text{text:button.text;font:button.font;color:button.enabled?'#000':'#888';horizontalAlignment:Text.AlignHCenter;verticalAlignment:Text.AlignVCenter;elide:Text.ElideRight}
 background:Rectangle{color:button.down?'#c9d9ec':button.checked?'#dceafd':'#efefef';border.color:button.activeFocus?'#000080':'#888';border.width:button.activeFocus?2:1}
}
