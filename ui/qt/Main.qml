import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Dialogs

ApplicationWindow {
    id: win
    width: 1380; height: 900; minimumWidth: 1100; minimumHeight: 700
    visible: true; title: "ShowPsiSi — Qt Quick"; color: "#f5f7fb"
    font.family: "Segoe UI"; font.pixelSize: 13
    property var analysisState: core.state
    property var detail: core.detail
    property string tab: "Services"
    property string selected: ""
    property int selectedService: -1
    property string filter: ""
    property var preview: ({})
    property string notice: ""
    property int autoDelay: Number(core.env("SHOWPSISI_AUTO_DELAY_MS") || 0)
    property bool inspected: false
    property int testStep: 0
    onTestStepChanged: core.mark("test_step_"+testStep)
    property var tableRows: (analysisState.tables || []).filter(function(t){return filter==="" || t.name===filter})
    property var serviceRows: analysisState.services || []
    property var eventRows: (analysisState.events || []).slice(0,80)
    property var issues: analysisState.diagnostics || []
    property color ink: "#19243a"
    property color muted: "#7c879b"
    property color blue: "#365ff4"
    function num(n) { return Number(n || 0).toLocaleString(Qt.locale("en_US"), "f", 0) }
    function hex(n) {return "0x"+Number(n).toString(16).toUpperCase().padStart(4,"0")}
    function inspect(id,sid) {if(!id){notice="Aggregate demux diagnostic; packet locations are not yet indexed";return}selected=id;selectedService=sid===undefined?-1:sid;core.send("inspect",{id:id})}
    function scan() {inspected=false;selected="";filter="";tab="Services";core.send("analyze",{path:source.text})}
    function snapshot(packet) {core.send("query",packet<0?{}:{at_packet:packet});notice=packet<0?"Latest observed state":"Snapshot at packet "+num(packet)}
    function defaultInspect() {let first=(analysisState.services||[])[0];if(first){inspect(first.source_id,first.id);return}let rows=analysisState.tables || [];if(rows.length)inspect(rows[0].id)}
    function chosenService() {return (detail.services||[]).find(function(s){return s.id===selectedService})||(detail.services||[])[0]}
    component TinyLabel: Label { color: muted; font.pixelSize: 11; font.letterSpacing: 1.1 }
    component Action: Button {
        id: control; property bool primary: false
        implicitHeight: 36; leftPadding: 16; rightPadding: 16
        contentItem: Label { text: control.text;color: control.primary?"white":ink;horizontalAlignment: Text.AlignHCenter;verticalAlignment: Text.AlignVCenter;font.weight: Font.DemiBold;opacity:control.enabled?1:0.4 }
        background: Rectangle {radius:7;color:control.primary?blue:(control.hovered?"#edf1fa":"white");border.color:control.primary?blue:"#dfe5ef"}
    }
    component Card: Rectangle { color:"white";radius:12;border.color:"#e4e9f1" }
    Connections {target:core
        function onResponse(method,result) {
            if(method==="analyze" && !result.message){defaultInspect();inspected=true;notice="Scan complete · source unchanged"}
            if(method==="preview_rename"){preview=result;notice=result.message || ("Preview: "+result.before+" → "+result.after+" · v"+result.old_version+" → v"+result.new_version)}
            if(method==="export"){notice=result.message || ("Exported "+num(result.bytes)+" bytes + manifest")}
            if(method==="capabilities"){apiText.text=JSON.stringify(result, null, 2);apiDialog.open()}
        }
        function onCompletedPaint(){if(core.env("SHOWPSISI_SCREENSHOT"))captureTimer.start()}
    }
    Timer {id:captureTimer;interval:500;onTriggered:{core.capture(core.env("SHOWPSISI_SCREENSHOT"));if(core.env("SHOWPSISI_SCRIPT")==="smoke")smokeTimer.start()}}
    Timer {id:smokeTimer;interval:250;repeat:true;onTriggered:{
        if(testStep===0){if(!core.click("history_v1"))return;testStep++}
        else if(testStep===1){if(serviceRows[0]?.name!=="World News")return;core.click("tab_Issues");testStep++}
        else if(testStep===2){if(!core.click("issue_crc32"))return;testStep++}
        else if(testStep===3){if(detail.valid!==false)return;core.capture(core.root+"/artifacts/qt-issues.png");core.click("latest");core.click("tab_Services");testStep++}
        else if(testStep===4){if(serviceRows[0]?.name!=="Sports UHD")return;if(!core.click("service_103"))return;testStep++}
        else if(testStep===5){if(detail.version!==3)return;core.click("rename");testStep++}
        else if(testStep===6){renameName.text="UI verified rename";core.click("preview");testStep++}
        else if(testStep===7){if(!preview.token)return;core.capture(core.root+"/artifacts/qt-edit.png");core.click("export");testStep++}
        else if(testStep===8){if(notice.indexOf("Exported")!==0)return;renameDialog.close();core.click("agentApi");testStep++}
        else if(testStep===9){if(!apiDialog.visible||apiText.text.indexOf("preview_rename")<0)return;apiDialog.close();core.testResult(JSON.stringify({checks:["history changes channel name/order","CRC raw evidence","rename preview","signal-only export","API schema discovery"],passed:true,services:serviceRows.length,observations:analysisState.observations}));stop()}
    }}
    Timer {id:autoTimer;interval:Math.max(1,autoDelay);onTriggered:scan()}
    Component.onCompleted: {core.mark("ui_ready");if(core.env("SHOWPSISI_AUTO")==="1")autoTimer.start()}
    FileDialog {id:fileDialog;title:"Open transport stream";nameFilters:["Transport streams (*.ts *.mts *.m2ts)","All files (*)"];onAccepted:{source.text=core.localPath(selectedFile);scan()}}
    Dialog {id:apiDialog;title:"Agent tools · the same native backend";width:800;height:600;anchors.centerIn:parent;modal:true;standardButtons:Dialog.Close
        ScrollView {anchors.fill:parent;TextArea{id:apiText;readOnly:true;wrapMode:TextEdit.Wrap;font.family:"Cascadia Mono";font.pixelSize:12}}
    }
    header: Rectangle {height:78;color:"white";border.color:"#e4e9f1"
        RowLayout {anchors.fill:parent;anchors.leftMargin:26;anchors.rightMargin:26;spacing:15
            Rectangle {width:40;height:40;radius:11;color:blue;Label{anchors.centerIn:parent;text:"≋";color:"white";font.pixelSize:31}}
            Column {spacing:2;Label{text:"ShowPsiSi";font.pixelSize:21;font.weight:Font.DemiBold;color:ink}TinyLabel{text:"TRANSPORT STREAM WORKBENCH";font.pixelSize:9}}
            Rectangle {width:1;height:27;color:"#e2e7f0";Layout.leftMargin:12;Layout.rightMargin:12}
            Label {text:"Qt Quick";color:muted;font.pixelSize:12}
            Item {Layout.fillWidth:true}
            Rectangle {width:90;height:28;radius:14;color:"#eaf6f0";Label{anchors.centerIn:parent;text:"●  LOCAL";color:"#228269";font.pixelSize:10;font.bold:true}}
            Action {objectName:"agentApi";text:"Agent API";onClicked:core.send("capabilities",{})}
        }
    }
    ColumnLayout {anchors.fill:parent;anchors.margins:22;spacing:17
        RowLayout {Layout.fillWidth:true;spacing:10
            Column {spacing:5;Label{text:"Signal explorer";font.pixelSize:27;font.weight:Font.DemiBold;color:ink}Label{text:"Inspect tables. Follow changes. Build test signals.";color:muted;font.pixelSize:12}}
            Item{Layout.fillWidth:true}
            TextField {id:source;Layout.preferredWidth:360;text:core.sample;selectByMouse:true;color:ink;font.pixelSize:11;implicitHeight:36;background:Rectangle{radius:7;color:"white";border.color:"#dfe5ef"}}
            Action {text:"Browse";onClicked:fileDialog.open()}
            Action {text:core.busy?"Scanning…":"Analyze";primary:true;enabled:!core.busy;onClicked:scan()}
        }
        RowLayout {Layout.fillWidth:true;spacing:12
            Repeater {model:[{label:"SERVICES",value:serviceRows.length,note:"Actual transport stream"},{label:"SECTION OBSERVATIONS",value:num(analysisState.observations),note:(analysisState.tables||[]).length+" distinct payloads"},{label:"VALIDATION ISSUES",value:issues.length,note:num(analysisState.crc_errors)+" CRC failures"},{label:"BACKEND SCAN",value:analysisState.metrics?Number(analysisState.metrics.scan_ms).toFixed(1)+" ms":"—",note:analysisState.complete?"Complete · incremental results":"Waiting for a source"}]
                Card {required property var modelData;Layout.fillWidth:true;height:91
                    Column {anchors.left:parent.left;anchors.leftMargin:18;anchors.verticalCenter:parent.verticalCenter;spacing:5
                        TinyLabel{text:modelData.label;font.pixelSize:9}
                        Label{text:modelData.value;color:ink;font.pixelSize:24;font.weight:Font.DemiBold}
                        Label{text:modelData.note;color:muted;font.pixelSize:10}
                    }
                }
            }
        }
        RowLayout {Layout.fillWidth:true;Layout.fillHeight:true;spacing:14
            Card {Layout.preferredWidth:210;Layout.fillHeight:true
                ColumnLayout {anchors.fill:parent;anchors.margins:14;spacing:3
                    TinyLabel{text:"TABLE LIBRARY";Layout.bottomMargin:5}
                    Repeater {model:["All tables","PAT","PMT","SDT","EIT","NIT","CAT","Private / other"]
                        Rectangle {required property string modelData;Layout.fillWidth:true;height:28;radius:6;color:(filter===modelData || (filter===""&&modelData==="All tables"))?"#edf1ff":"transparent"
                            RowLayout{anchors.fill:parent;anchors.leftMargin:10;anchors.rightMargin:10;Label{text:"›";color:muted}Label{text:modelData;color:ink;font.pixelSize:12;Layout.fillWidth:true}Label{text:(analysisState.tables||[]).filter(function(t){return modelData==="All tables"||t.name===modelData}).length;color:muted;font.pixelSize:11}}
                            MouseArea{anchors.fill:parent;cursorShape:Qt.PointingHandCursor;onClicked:{filter=modelData==="All tables"?"":modelData;tab="Tables"}}
                        }
                    }
                    Item{Layout.fillHeight:true}
                    Rectangle{Layout.fillWidth:true;height:78;radius:7;color:"#f5f7fb"
                        Column{anchors.fill:parent;anchors.margins:11;spacing:6;TinyLabel{text:"EXTENSION ACTIVE";font.pixelSize:8}Label{text:"Private descriptors";color:ink;font.pixelSize:11}Label{text:analysisState.extension_id||"showpsisi.demo.operator";width:170;elide:Text.ElideRight;color:muted;font.pixelSize:9}Label{text:"PDS scoped · raw preserved";color:blue;font.pixelSize:9}}
                    }
                }
            }
            Card {Layout.fillWidth:true;Layout.fillHeight:true
                ColumnLayout {anchors.fill:parent;anchors.margins:18;spacing:13
                    RowLayout {Layout.fillWidth:true;spacing:20
                        Repeater {model:["Services","Tables","EPG","Issues"]
                            Label {required property string modelData;objectName:"tab_"+modelData;text:modelData+(modelData==="Issues"&&issues.length?"  "+issues.length:"");color:tab===modelData?blue:muted;font.weight:Font.DemiBold;font.pixelSize:12;bottomPadding:9
                                Rectangle{anchors.bottom:parent.bottom;width:parent.width;height:2;color:tab===modelData?blue:"transparent"}
                                MouseArea{anchors.fill:parent;cursorShape:Qt.PointingHandCursor;onClicked:tab=modelData}
                            }
                        }
                        Item{Layout.fillWidth:true}
                    }
                    RowLayout {visible:tab==="Services";Layout.fillWidth:true;TinyLabel{text:"LCN";Layout.preferredWidth:40;font.pixelSize:9}TinyLabel{text:"SERVICE / PROVIDER";Layout.fillWidth:true;font.pixelSize:9}TinyLabel{text:"PMT";Layout.preferredWidth:65;font.pixelSize:9}TinyLabel{text:"GROUP";Layout.preferredWidth:98;font.pixelSize:9}}
                    ListView {visible:tab==="Services";Layout.fillWidth:true;Layout.fillHeight:true;clip:true;spacing:6;model:serviceRows;ScrollBar.vertical:ScrollBar{}
                        delegate:Rectangle{required property var modelData;objectName:"service_"+modelData.id;width:ListView.view.width;height:57;radius:7;color:selected===modelData.source_id?"#f0f4ff":"#fafbfd"
                            RowLayout{anchors.fill:parent;anchors.margins:9;spacing:9
                                Label{text:modelData.logical_channel_number===null?"—":String(modelData.logical_channel_number).padStart(2,"0");color:blue;font.weight:Font.DemiBold;font.pixelSize:13;Layout.preferredWidth:30}
                                Column{Layout.fillWidth:true;spacing:5;Label{text:modelData.name;color:ink;font.weight:Font.DemiBold;font.pixelSize:12}Label{text:(modelData.provider||"No provider")+" · SID "+modelData.id;color:muted;font.pixelSize:10}}
                                Label{text:modelData.pmt_pid===null?"—":hex(modelData.pmt_pid);color:muted;font.pixelSize:10;Layout.preferredWidth:65}
                                Label{text:modelData.group;color:"#647391";font.pixelSize:10;Layout.preferredWidth:98}
                            }
                            MouseArea{anchors.fill:parent;cursorShape:Qt.PointingHandCursor;onClicked:inspect(modelData.source_id,modelData.id)}
                        }
                    }
                    ListView {visible:tab==="Tables";Layout.fillWidth:true;Layout.fillHeight:true;clip:true;spacing:5;model:tableRows;ScrollBar.vertical:ScrollBar{}
                        delegate:Rectangle{required property var modelData;width:ListView.view.width;height:51;radius:7;color:selected===modelData.id?"#edf1ff":"#fafbfd"
                            RowLayout{anchors.fill:parent;anchors.margins:10;Column{Layout.fillWidth:true;spacing:4;Label{text:modelData.name+"  /  "+hex(modelData.pid);font.weight:Font.DemiBold;color:ink;font.pixelSize:12}Label{text:"v"+modelData.version+" · section "+modelData.section+"/"+modelData.last_section+" · "+modelData.bytes+" bytes";color:muted;font.pixelSize:10}}Label{text:num(modelData.count)+"×";color:muted}Label{text:modelData.valid?"●":"!";color:modelData.valid?"#37a285":"#da6952"}}
                            MouseArea{anchors.fill:parent;onClicked:inspect(modelData.id);cursorShape:Qt.PointingHandCursor}
                        }
                    }
                    ListView {visible:tab==="EPG";Layout.fillWidth:true;Layout.fillHeight:true;clip:true;spacing:7;model:eventRows;ScrollBar.vertical:ScrollBar{}
                        delegate:Rectangle{required property var modelData;width:ListView.view.width;height:62;radius:8;color:"#edf3ff"
                            Column{anchors.fill:parent;anchors.margins:11;spacing:6;Label{text:modelData.title;color:ink;font.weight:Font.DemiBold}Label{text:"SID "+modelData.service_id+" · "+modelData.start+" UTC · "+modelData.duration_seconds/60+" min";color:muted;font.pixelSize:10}}
                            MouseArea{anchors.fill:parent;onClicked:inspect(modelData.source_id)}
                        }
                    }
                    ListView {visible:tab==="Issues";Layout.fillWidth:true;Layout.fillHeight:true;clip:true;spacing:8;model:issues;ScrollBar.vertical:ScrollBar{}
                        delegate:Rectangle{required property var modelData;objectName:"issue_"+modelData.code;width:ListView.view.width;height:76;radius:8;color:"#fff4ef"
                            Column{anchors.fill:parent;anchors.margins:10;spacing:5;Label{text:modelData.code+(modelData.aggregate?" · aggregate":" · PID "+hex(modelData.pid));color:"#ba5944";font.weight:Font.DemiBold}Label{text:modelData.detail;width:parent.width;wrapMode:Text.Wrap;color:muted;font.pixelSize:10}Label{text:(modelData.aggregate?"All monitored SI PIDs":"packet "+num(modelData.packet))+" · "+modelData.count+" observations";color:muted;font.pixelSize:10}}
                            MouseArea{anchors.fill:parent;onClicked:inspect(modelData.id)}
                        }
                    }
                    Label {visible:!analysisState.source;text:"Open a transport stream to start exploring.";color:muted;Layout.alignment:Qt.AlignHCenter}
                }
            }
            Card {Layout.preferredWidth:300;Layout.fillHeight:true
                ColumnLayout {anchors.fill:parent;anchors.margins:17;spacing:11
                    RowLayout{Layout.fillWidth:true;TinyLabel{text:"SECTION INSPECTOR";Layout.fillWidth:true}Label{text:detail.valid===false?"INVALID":"RAW + DECODED";color:detail.valid===false?"#cd664d":blue;font.pixelSize:8;font.bold:true}}
                    Label{text:detail.name?detail.name+" · version "+detail.version:"Select a section";color:ink;font.pixelSize:19;font.weight:Font.DemiBold}
                    Label{text:detail.pid!==undefined?"PID "+hex(detail.pid)+" · "+detail.bytes+" bytes · "+num(detail.count)+" repeats":"Fields retain their source evidence";color:muted;font.pixelSize:10}
                    ScrollView {Layout.fillWidth:true;Layout.fillHeight:true;clip:true
                        Column {width:265;spacing:9
                            Repeater {model:(detail.descriptors||[]).filter(function(d){return selectedService<0||d.service_id===selectedService||d.service_id<0})
                                Rectangle {required property var modelData;width:265;height:descriptorColumn.implicitHeight+18;radius:7;color:"#f6f8fc"
                                    Column{id:descriptorColumn;anchors.left:parent.left;anchors.right:parent.right;anchors.top:parent.top;anchors.margins:9;spacing:5
                                        Label{text:"↳ "+modelData.name;width:247;wrapMode:Text.WrapAnywhere;color:modelData.extension?blue:ink;font.pixelSize:10;font.weight:Font.DemiBold}
                                        Label{text:"tag "+hex(modelData.tag)+" · "+modelData.length+" bytes · @"+modelData.offset;color:muted;font.pixelSize:9}
                                        Label{text:Object.keys(modelData.fields).map(function(k){return k+": "+modelData.fields[k]}).join("\n");width:247;wrapMode:Text.WrapAnywhere;color:"#62718a";font.family:"Cascadia Mono";font.pixelSize:9;visible:Object.keys(modelData.fields).length>0}
                                        Label{text:modelData.raw;width:247;wrapMode:Text.WrapAnywhere;color:muted;font.family:"Cascadia Mono";font.pixelSize:9;visible:Object.keys(modelData.fields).length===0}
                                    }
                                }
                            }
                            TinyLabel{text:"SECTION HEX";font.pixelSize:9;topPadding:7}
                            Label{text:(detail.raw_hex||"").match(/.{1,32}/g)?.join("\n")||"";width:265;wrapMode:Text.WrapAnywhere;font.family:"Cascadia Mono";font.pixelSize:10;color:muted}
                        }
                    }
                    Label{text:detail.first_packet!==undefined?"Evidence · packet "+num(detail.first_packet):"";color:muted;font.pixelSize:10}
                    Action{objectName:"rename";text:"Rename service…";Layout.fillWidth:true;enabled:detail.name==="SDT"&&detail.valid;onClicked:{preview={};renameName.text=chosenService()?.name||"";renameDialog.open()}}
                }
            }
        }
        Card {Layout.fillWidth:true;height:134
            ColumnLayout{anchors.fill:parent;anchors.margins:16;spacing:9
                RowLayout{Layout.fillWidth:true;TinyLabel{text:"OCCURRENCE DENSITY";Layout.fillWidth:true}Label{text:"Packet position · 80 bins · red = invalid sections";color:muted;font.pixelSize:10}Action{objectName:"latest";text:"Latest";implicitHeight:25;onClicked:snapshot(-1)}}
                Row{Layout.fillWidth:true;Layout.fillHeight:true;spacing:3
                    Repeater{model:analysisState.density||[]
                        Rectangle{required property var modelData;width:(parent.width-79*3)/80;height:35;radius:2;color:modelData.bad?"#ed937d":"#88a1ff";opacity:modelData.count?0.35+Math.min(0.65,modelData.count/50):0.12;anchors.bottom:parent.bottom
                            ToolTip.visible:binMouse.containsMouse;ToolTip.text:modelData.count+" sections / "+modelData.bad+" invalid"
                            MouseArea{id:binMouse;anchors.fill:parent;hoverEnabled:true}
                        }
                    }
                }
                RowLayout{Layout.fillWidth:true;Label{text:"0";color:muted;font.pixelSize:9}Row{spacing:8;Repeater{model:analysisState.history||[];Action{required property var modelData;objectName:"history_v"+modelData.version;text:modelData.label+"  @ "+num(modelData.first_packet);implicitHeight:26;onClicked:{snapshot(modelData.last_packet);inspect(modelData.id)}}}}Item{Layout.fillWidth:true}Label{text:num(analysisState.packets)+" packets";color:muted;font.pixelSize:9}}
            }
        }
        RowLayout {Layout.fillWidth:true;Label{text:core.error||notice||"Ready · all processing stays on this machine";color:core.error?"#bd5c49":muted;font.pixelSize:10;Layout.fillWidth:true;elide:Text.ElideMiddle}Label{text:"C++ / TSDuck 3.39  ·  Qt 6.7";color:muted;font.pixelSize:10}}
    }
    Dialog {id:renameDialog;title:"Preview a service edit";anchors.centerIn:parent;width:500;modal:true;standardButtons:Dialog.Close
        ColumnLayout{anchors.fill:parent;spacing:12
            Label{text:"Single-section SDT · new version and CRC generated";color:muted;font.pixelSize:11}
            TextField{id:renameName;Layout.fillWidth:true;placeholderText:"New service name"}
            Action{objectName:"preview";text:"Preview change";primary:true;enabled:renameName.text.length>0;onClicked:core.send("preview_rename",{id:selected,service_id:chosenService().id,name:renameName.text})}
            Label{text:preview.token?preview.before+" → "+preview.after:"";Layout.fillWidth:true;wrapMode:Text.Wrap;color:ink}
            Action{objectName:"export";text:"Export SI-only TS + manifest";enabled:!!preview.token;onClicked:{let p={path:core.root+"/artifacts/qt-export-"+Date.now()+".ts",format:"ts",preview_token:preview.token};if(analysisState.selected_packet!==null)p.at_packet=analysisState.selected_packet;core.send("export",p)}}
        }
    }
}
