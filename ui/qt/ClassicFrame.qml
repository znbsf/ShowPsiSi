import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQml.Models
import "../tauri/web/classic-model.js" as Shared

Column {
    id: frame
    required property var host
    property var state: host.classicState()
    signal command(string name)
    width:parent?parent.width:1000
    height:visible?implicitHeight:0
    spacing:0
    MenuBar {
        id: menuBar
        objectName:"classicMenuBar"
        width:parent.width;height:25
        font.family:"Tahoma";font.pixelSize:12
        background:Rectangle {color:'#efefef';border.color:'#a0a0a0'}
        Instantiator {
            model:Shared.classic.menus(frame.state)
            delegate:Menu {
                id: menu
                required property var modelData
                title:"&"+modelData.title
                font.family:'Tahoma';font.pixelSize:12
                background:Rectangle{color:'#efefef';border.color:'#808080'}
                Instantiator {
                    model:menu.modelData.items
                    delegate:MenuItem {
                        required property var modelData
                        objectName:'classicCommand:'+modelData.id
                        text:modelData.text||''
                        enabled:!modelData.separator && !!modelData.enabled
                        checkable:!!modelData.checkable;checked:!!modelData.checked
                        implicitHeight:modelData.separator?7:25
                        Accessible.description:modelData.reason||''
                        contentItem:Item {
                            implicitWidth:230;implicitHeight:parent.implicitHeight
                            Rectangle{visible:!!modelData.separator;x:8;width:parent.width-16;anchors.verticalCenter:parent.verticalCenter;height:1;color:'#aaa'}
                            Text{visible:!modelData.separator;x:4;anchors.verticalCenter:parent.verticalCenter;text:modelData.checked?'✓':'';color:'#000';font.family:'Tahoma';font.pixelSize:12}
                            Text{visible:!modelData.separator;x:25;anchors.verticalCenter:parent.verticalCenter;text:modelData.text||'';color:modelData.enabled?'#000':'#808080';font.family:'Tahoma';font.pixelSize:12}
                            Text{visible:!modelData.separator;anchors.right:parent.right;anchors.verticalCenter:parent.verticalCenter;text:modelData.shortcut||'';color:modelData.enabled?'#000':'#808080';font.family:'Tahoma';font.pixelSize:12}
                        }
                        onTriggered:frame.command(modelData.id)
                        ToolTip.visible:hovered&&!!modelData.reason
                        ToolTip.text:modelData.reason||''
                    }
                    onObjectAdded:function(index,object){menu.insertItem(index,object);}
                    onObjectRemoved:function(index,object){menu.removeItem(object);}
                }
            }
            onObjectAdded:function(index,object){menuBar.insertMenu(index,object);}
            onObjectRemoved:function(index,object){menuBar.removeMenu(object);}
        }
    }
    Rectangle {
        visible:frame.state.toolbar
        width:parent.width;height:visible?31:0
        color:'#efefef';border.color:'#a0a0a0'
        Row {
            anchors.left:parent.left;anchors.leftMargin:6;anchors.verticalCenter:parent.verticalCenter;spacing:2
            Repeater {
                model:Shared.classic.toolbar
                delegate:Item {
                    required property var modelData
                    width:modelData.separator?8:26;height:25
                    Rectangle {visible:!!modelData.separator;width:1;height:20;color:'#aaa';anchors.centerIn:parent}
                    ToolButton {
                        visible:!modelData.separator;anchors.fill:parent
                        objectName:'classicTool:'+modelData.id
                        enabled:Shared.classic.enabled(modelData.id,frame.state)
                        checkable:modelData.id==='tree';checked:Shared.classic.checked(modelData.id,frame.state)
                        Accessible.name:Shared.classic.labels[modelData.id]||''
                        Accessible.description:Shared.classic.reason(modelData.id,frame.state)
                        background:Rectangle{color:parent.down?'#d0d0d0':parent.hovered?'#fff':'#efefef';border.color:parent.checked||parent.hovered?'#808080':'transparent'}
                        contentItem:Item {
                            Item {width:16;height:15;anchors.centerIn:parent;clip:true;opacity:parent.parent.enabled?1:0.35
                                Image{source:'../tauri/web/assets/toolbar128.bmp';x:-Number(modelData.slot||0)*16;width:112;height:15;smooth:false}
                            }
                        }
                        onClicked:frame.command(modelData.id)
                        ToolTip.visible:hovered;ToolTip.text:Shared.classic.reason(modelData.id,frame.state)||Shared.classic.labels[modelData.id]||''
                    }
                }
            }
        }
    }
}
