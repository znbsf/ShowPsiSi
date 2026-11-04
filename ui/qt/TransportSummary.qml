import QtQuick
import QtQuick.Window
import QtQuick.Controls
import QtQuick.Layouts

Pane {
    id: view
    property bool classicStyle:false
    readonly property color dialogInk:classicStyle?'#000':host.ink
    readonly property color dialogMuted:classicStyle?'#000':host.muted
    readonly property color dialogFace:classicStyle?'#efefef':host.panel
    readonly property color dialogPaper:classicStyle?'#fff':(host.surface || host.panel)
    // Overlay the native background, preserving its implicit sizing and focus border.
    component DialogButton:Button {
        id:button;objectName:"transportDialogButton:"+text
        Rectangle {parent:button.background;anchors.fill:parent;anchors.margins:button.activeFocus?2:0;visible:view.classicStyle;color:'#efefef';border.color:button.down?'#808080':'#fff'
            Rectangle {anchors.right:parent.right;width:1;height:parent.height;color:button.down?'#fff':'#808080'}
            Rectangle {anchors.bottom:parent.bottom;height:1;width:parent.width;color:button.down?'#fff':'#808080'}
        }
    }
    component HeaderLabel:Label {
        Rectangle {anchors.fill:parent;anchors.margins:-3;z:-1;visible:view.classicStyle;color:'#efefef';border.color:'#fff'
            Rectangle {anchors.right:parent.right;width:1;height:parent.height;color:'#808080'}
            Rectangle {anchors.bottom:parent.bottom;height:1;width:parent.width;color:'#808080'}
        }
    }
    property Item focusOrigin:null
    required property var host
    property var state: host.analysisState
    property var page: ({})
    property var expected: ({})
    property bool loading: false
    readonly property bool queryReady:host.transportQueryReady && !!state.complete
    onQueryReadyChanged:if(queryReady && visible && !loading && !page.items)request(0)
    property string error: ""
    property var returnContext: null
    property string sort: "pid"
    property bool descending: false
    property string sourceIdentity: (state.source || "")+":"+(state.analysis_revision || state.revision || 0)+":"+!!state.complete
    readonly property var summary: state.transport_summary || ({})
    readonly property bool errorPage: tabs.currentIndex===1
    readonly property var visibleRows: errorPage ? (page.items || []).map(function(row) {
        return {pid:row.pid,packets:row.packets,kind:"pid",message:"TEI: "+row.tei_packets+" · malformed header/adaptation: "+row.malformed_header_packets};
    }).concat((page.aggregate_errors || []).concat(state.diagnostics || []).map(function(row) {
        return {pid:row.aggregate?null:row.pid,id:row.id,aggregate:!!row.aggregate,kind:row.aggregate?"aggregate":"section",
            packets:row.count || 1,message:(row.code || "")+" · "+(row.detail || "")+" · count "+(row.count || 1)};
    })) : page.items || []
    signal pageRequested(int offset,string sort,bool descending,bool errorsOnly)
    signal entryActivated(var entry)
    function rowLabel(row){return row.pid===null || row.pid===undefined?"All / unknown PIDs":hex(row.pid);}
    function activate(row) {
        if(!row)return;
        if(row.aggregate){error="This aggregate has no exact packet or section identity; source navigation is unavailable.";return;}
        returnContext={offset:page.offset,index:rows.currentIndex,scroll:rows.contentY};
        entryActivated(row);
    }
    function nextRegion(backwards){var regions=focusOrigin?[focusOrigin,rows,tabs]:[rows,tabs],active=view.Window.window?view.Window.window.activeFocusItem:null,index=regions.findIndex(function(region){for(var item=active;item;item=item.parent)if(item===region)return true;return false;});var target=regions[(index+(backwards?regions.length-1:1)+regions.length)%regions.length];if(target===tabs&&tabs.currentItem)tabs.currentItem.forceActiveFocus();else target.forceActiveFocus();}
    function restoreContext() {
        if(!returnContext || returnContext.offset!==page.offset)return;
        rows.currentIndex=returnContext.index;
        rows.contentY=Math.max(rows.originY,Math.min(returnContext.scroll,rows.originY+Math.max(0,rows.contentHeight-rows.height)));
    }
    padding:0
    font.family:classicStyle?"Tahoma":"Segoe UI";font.pixelSize:classicStyle?13:12
    background:Rectangle {color:view.dialogFace}
    palette.window:view.dialogFace
    palette.windowText:view.dialogInk
    palette.base:view.dialogPaper
    palette.text:view.dialogInk
    palette.button:classicStyle?'#efefef':(host.raised || host.panel)
    palette.buttonText:view.dialogInk
    palette.light:host.selectionSurface || host.panel
    palette.midlight:host.hoverSurface || host.panel
    palette.dark:host.panel
    palette.brightText:view.dialogInk
    palette.highlight:host.blue || host.muted
    palette.highlightedText:view.dialogInk
    function number(value) {return value===null || value===undefined ? "Unknown" : Number(value).toLocaleString(Qt.locale("en_US"),"f",0);}
    function duration(value,pcr) {
        if(value===null || value===undefined || !isFinite(Number(value)))return "Unknown";
        var milliseconds=Math.round(Number(value)*1000);
        return String(Math.floor(milliseconds/3600000)).padStart(2,"0")+":"+
            String(Math.floor(milliseconds/60000)%60).padStart(2,"0")+":"+
            String(Math.floor(milliseconds/1000)%60).padStart(2,"0")+"."+
            String(milliseconds%1000).padStart(3,"0")+(pcr?" (PCR intervals)":" (supplied rate)");
    }
    function hex(pid){return "0x"+Number(pid).toString(16).toUpperCase().padStart(4,"0");}
    function comment(row) {
        var names=[];
        (state.tables || []).filter(function(record){return record.pid===row.pid;}).forEach(function(record){if(names.indexOf(record.name)<0)names.push(record.name);});
        if(row.pid===8191)names.push("Null packets");
        if(row.scrambled_packets)names.push(number(row.scrambled_packets)+" scrambled");
        return names.join(" · ") || "No retained PSI/SI section";
    }
    function request(offset) {
        if(!visible || !queryReady || loading)return;
        error="";loading=true;
        expected={analysis_revision:state.analysis_revision || state.revision,offset:offset,sort:sort,descending:descending,errors_only:tabs.currentIndex===1};
        pageRequested(offset,sort,descending,expected.errors_only);
    }
    function receive(result) {
        if(result.message){loading=false;error=result.message;return;}
        if(result.analysis_revision!==expected.analysis_revision || result.source!==state.source ||
           result.offset!==expected.offset || result.sort!==expected.sort ||
           result.descending!==expected.descending || result.errors_only!==expected.errors_only)return;
        page=result;loading=false;error="";
    }
    function reject(message){loading=false;error=message;}
    function resetPage() {page={};expected={};returnContext=null;loading=false;error="";if(visible && state.complete)request(0);}
    onSourceIdentityChanged:resetPage()
    onVisibleChanged:if(visible && state.complete && !loading){if(!page.items)request(0);else Qt.callLater(restoreContext);}
    ColumnLayout {
        anchors.fill:parent;anchors.margins:10;spacing:8
        Label {text:view.state.file_name || "Transport stream summary";color:view.dialogInk;font.bold:true;font.pixelSize:view.classicStyle?13:14;Layout.fillWidth:true;elide:Text.ElideMiddle}
        GridLayout {
            columns:view.width>=820?3:view.width>=520?2:1
            Layout.fillWidth:true;columnSpacing:14;rowSpacing:6
            Repeater {
                model:[
                    {id:"fileSize",label:"FileSize",value:view.number(view.state.source_bytes)+" bytes"},
                    {id:"totalPackets",label:"Total Packets",value:view.number(summary.observed_packets)},
                    {id:"bitrate",label:"BitRates",value:(summary.effective_bitrate_bps??summary.configured_bitrate_bps)==null?"Unknown":view.number(summary.effective_bitrate_bps??summary.configured_bitrate_bps)+(summary.pcr_derived?" bps (PCR)":" bps (supplied)")},
                    {id:"errors",label:"Errors",value:view.number(summary.error_packets)+" transport / "+view.number(view.state.crc_errors)+" CRC"},
                    {id:"duration",label:"Duration",value:view.duration(summary.observed_duration_seconds,summary.pcr_derived)},
                    {id:"packetSize",label:"Packet Size",value:view.number(view.state.packet_size)+" bytes"}
                ]
                delegate:RowLayout {
                    required property var modelData
                    Layout.fillWidth:true;spacing:6
                    Label {text:modelData.label;color:view.dialogMuted;Layout.preferredWidth:88}
                    TextField {
                        id:counterValue
                        color:view.dialogInk
                        background:Rectangle {color:view.dialogPaper;border.color:counterValue.activeFocus?(host.blue || host.muted):(host.controlBorder || host.muted);border.width:counterValue.activeFocus?2:1;radius:view.classicStyle?0:2
                            Rectangle {anchors.fill:parent;anchors.margins:counterValue.activeFocus?2:0;visible:view.classicStyle;color:'#fff';border.color:'#808080'
                                Rectangle {anchors.right:parent.right;width:1;height:parent.height;color:'#fff'}
                                Rectangle {anchors.bottom:parent.bottom;height:1;width:parent.width;color:'#fff'}
                            }
                        }
                        objectName:"transportSummary:"+modelData.id
                        text:modelData.value;readOnly:true;selectByMouse:true
                        Layout.fillWidth:true;Layout.minimumWidth:90
                        Accessible.name:modelData.label+": "+text
                    }
                }
            }
        }
        Label {
            objectName:"transportSummaryScope"
            text:"Scan-global · "+view.number(summary.pid_count)+" PIDs · "+(view.state.coverage?.partial?"PARTIAL observed windows":"full scan")+" · historical selection does not change these counters.\n"+
                 "BitRates: "+(summary.rate_basis || "Transport counters require a matching updated engine.")+
                 ". PacketRate is the share of observed packets; Errors excludes continuity, PES and decoder checks."
            color:view.dialogMuted;wrapMode:Text.Wrap;Layout.fillWidth:true;font.pixelSize:view.classicStyle?13:11
        }
        RowLayout {
            Layout.fillWidth:true
            HeaderLabel {text:view.errorPage?"PID / Error Msg":"PID";color:view.dialogMuted;Layout.preferredWidth:90}
            DialogButton {implicitHeight:28;opacity:enabled?1:0.45;text:"#of packets"+(view.sort==="packets"?(view.descending?" ↓":" ↑"):"");visible:!view.errorPage;enabled:!view.loading;Layout.preferredWidth:130;onClicked:{view.descending=view.sort==="packets"?!view.descending:true;view.sort="packets";view.request(0);}}
            HeaderLabel {text:"PacketRate (%)";visible:!view.errorPage;color:view.dialogMuted;Layout.preferredWidth:100;Layout.minimumWidth:100}
            HeaderLabel {text:"Bitrate (bps)";visible:!view.errorPage;color:view.dialogMuted;Layout.preferredWidth:120;Layout.minimumWidth:120}
            HeaderLabel {text:view.errorPage?"Transport errors and retained section diagnostics":"Comment";color:view.dialogMuted;Layout.fillWidth:true}
            DialogButton {implicitHeight:28;opacity:enabled?1:0.45;text:"PID "+(view.sort==="pid"?(view.descending?"↓":"↑"):"");enabled:!view.loading;onClicked:{view.descending=view.sort==="pid"?!view.descending:false;view.sort="pid";view.request(0);}}
        }
        ListView {
            id:rows;objectName:"transportPidList"
            Layout.fillWidth:true;Layout.fillHeight:true;clip:true;reuseItems:true
            model:view.visibleRows;activeFocusOnTab:true
            Rectangle {anchors.fill:parent;z:-1;visible:view.classicStyle;color:'#fff';border.color:'#808080'}
            ScrollBar.vertical:ScrollBar{}
            Rectangle {parent:rows;anchors.fill:parent;z:2;color:"transparent";border.width:rows.activeFocus?2:0;border.color:host.blue || host.muted;enabled:false}
            Keys.onReturnPressed:if(currentIndex>=0 && currentIndex<count)view.activate(model[currentIndex])
            Keys.onPressed:function(event){if(event.key===Qt.Key_Home){currentIndex=0;event.accepted=true;}else if(event.key===Qt.Key_End){currentIndex=count-1;event.accepted=true;}}
            delegate:ItemDelegate {
                id:pidDelegate
                required property var modelData
                required property int index
                objectName:"transportPid:"+modelData.pid
                width:ListView.view?ListView.view.width:0;height:view.errorPage?Math.max(32,errorText.implicitHeight+10):32
                highlighted:rows.currentIndex===index
                Rectangle {parent:pidDelegate.background;anchors.fill:parent;visible:view.classicStyle;color:rows.currentIndex===index?'#ff0':'#fff'}
                Accessible.name:view.rowLabel(modelData)+", "+(view.errorPage?modelData.message:view.number(modelData.packets)+" packets, "+view.comment(modelData))
                onClicked:rows.currentIndex=index
                onDoubleClicked:view.activate(modelData)
                contentItem:RowLayout {
                    spacing:8
                    Label {text:view.rowLabel(modelData);color:view.dialogInk;Layout.preferredWidth:90;Layout.minimumWidth:90;font.family:view.classicStyle?"Tahoma":"Consolas"}
                    Label {objectName:"transportPackets:"+index;text:view.number(modelData.packets);visible:!view.errorPage;color:view.dialogInk;Layout.preferredWidth:130;Layout.minimumWidth:130}
                    Label {objectName:"transportRate:"+index;text:Number(modelData.packet_fraction*100).toFixed(3);visible:!view.errorPage;color:view.dialogInk;Layout.preferredWidth:100;Layout.minimumWidth:100}
                    Label {text:modelData.bitrate_bps===null || modelData.bitrate_bps===undefined?"—":view.number(modelData.bitrate_bps);visible:!view.errorPage;color:view.dialogInk;Layout.preferredWidth:120;Layout.minimumWidth:120}
                    Label {id:errorText;text:view.errorPage?modelData.message:view.comment(modelData);color:view.dialogInk;Layout.fillWidth:true;wrapMode:view.errorPage?Text.Wrap:Text.NoWrap;elide:Text.ElideRight}
                }
            }
            Label {anchors.centerIn:parent;visible:rows.count===0;text:view.loading?"Loading…":!view.state.complete?"Analyze a file to view PID counters.":view.errorPage?"No captured transport errors or retained section diagnostics.":"No PID rows in this page.";color:view.dialogMuted;wrapMode:Text.Wrap;width:Math.min(500,parent.width-20);horizontalAlignment:Text.AlignHCenter}
        }
        Label {visible:!!view.error;text:view.error;color:host.removedColor;wrapMode:Text.Wrap;Layout.fillWidth:true}
        RowLayout {
            Layout.fillWidth:true
            DialogButton {implicitHeight:28;opacity:enabled?1:0.45;text:"Previous";enabled:!view.loading && Number(view.page.offset)>0;onClicked:view.request(Math.max(0,view.page.offset-100))}
            Label {text:view.loading?"Loading…":view.page.total!==undefined?view.number(view.page.total?view.page.offset+1:0)+"–"+view.number(view.page.offset+(view.page.items || []).length)+" / "+view.number(view.page.total)+" PID rows":"";color:view.dialogMuted}
            DialogButton {implicitHeight:28;opacity:enabled?1:0.45;text:"Next";enabled:!view.loading && view.page.next_offset!==null && view.page.next_offset!==undefined;onClicked:view.request(view.page.next_offset)}
            DialogButton {implicitHeight:28;opacity:enabled?1:0.45;text:"Refresh";enabled:!view.loading && !!view.state.complete;onClicked:view.request(Number(view.page.offset || 0))}
            Label {text:"Double-click / Enter: retained sections for this PID";color:view.dialogMuted;Layout.fillWidth:true;elide:Text.ElideRight}
        }
        TabBar {
            id:tabs;objectName:"transportSummaryTabs";Layout.fillWidth:true
            onCurrentIndexChanged:{view.page={};view.returnContext=null;view.loading=false;view.request(0);}
            TabButton {
                id:summaryTab;implicitHeight:28;text:"Summary";Accessible.name:"Transport PID summary";Accessible.checked:summaryTab.checked
                background:Rectangle {color:summaryTab.checked?host.selectionSurface:host.raised;border.width:summaryTab.activeFocus?2:0;border.color:host.blue
                    Rectangle {anchors.fill:parent;anchors.margins:summaryTab.activeFocus?2:0;visible:view.classicStyle;color:'#efefef';border.color:summaryTab.checked?'#808080':'#fff'
                        Rectangle {anchors.right:parent.right;width:1;height:parent.height;color:summaryTab.checked?'#fff':'#808080'}
                        Rectangle {anchors.bottom:parent.bottom;height:1;width:parent.width;color:summaryTab.checked?'#fff':'#808080'}
                    }
                }
                contentItem:Label {text:summaryTab.text;color:view.dialogInk;font.bold:summaryTab.checked;horizontalAlignment:Text.AlignHCenter;verticalAlignment:Text.AlignVCenter}
            }
            TabButton {
                id:errorsTab;implicitHeight:28;text:"Error";Accessible.name:"Transport errors and section diagnostics";Accessible.checked:errorsTab.checked
                background:Rectangle {color:errorsTab.checked?host.selectionSurface:host.raised;border.width:errorsTab.activeFocus?2:0;border.color:host.blue
                    Rectangle {anchors.fill:parent;anchors.margins:errorsTab.activeFocus?2:0;visible:view.classicStyle;color:'#efefef';border.color:errorsTab.checked?'#808080':'#fff'
                        Rectangle {anchors.right:parent.right;width:1;height:parent.height;color:errorsTab.checked?'#fff':'#808080'}
                        Rectangle {anchors.bottom:parent.bottom;height:1;width:parent.width;color:errorsTab.checked?'#fff':'#808080'}
                    }
                }
                contentItem:Label {text:errorsTab.text;color:view.dialogInk;font.bold:errorsTab.checked;horizontalAlignment:Text.AlignHCenter;verticalAlignment:Text.AlignVCenter}
            }
        }
    }
}
