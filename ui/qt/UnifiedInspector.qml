import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "InspectorModel.js" as Model

SplitView {
    id: view
    required property var host
    property var state: host.analysisState
    property var detail: host.detail
    property var root: Model.inspector.structure(detail)
    property var closed: ({})
    property var limits: ({})
    property string selectedPath: "section"
    property var history: []
    property bool restoring: false
    property int page: 0
    property string family: "All tables"
    property string query: ""
    property bool hexOpen: false
    property var records: (state.tables || []).filter(function(r){return (family==="All tables" || r.name===family) && (!query || Model.inspector.title(r).toLowerCase().indexOf(query.toLowerCase())>=0);}).slice().sort(function(a,b){return a.pid-b.pid || a.table_id-b.table_id || a.first_packet-b.first_packet;})
    property var nodes: Model.inspector.flatten(root,closed,0,limits)
    property var selectedNode: Model.inspector.find(root,selectedPath) || root
    property var fieldRows: selectedNode ? selectedNode.fields : []
    property var navigation: {
        var out=[];
        records.slice(page*100,(page+1)*100).forEach(function(r){
            out.push({kind:'record',key:r.id,label:Model.inspector.title(r),record:r,depth:0});
            if(r.id===detail.id)nodes.forEach(function(n){out.push({kind:'node',key:r.id+':'+n.path,label:n.label,node:n,depth:n.depth+1});});
        });return out;
    }
    onRecordsChanged: page=Math.min(page,Math.max(0,Math.ceil(records.length/100)-1))
    onFamilyChanged: page=0
    onQueryChanged: page=0
    onNavigationChanged: Qt.callLater(revealSelection)
    onSelectedPathChanged: Qt.callLater(revealSelection)
    function revealSelection() {
        var key=detail.id+':'+selectedPath;
        var index=navigation.findIndex(function(r){return r.key===key;});
        if(index<0)index=navigation.findIndex(function(r){return r.key===detail.id;});
        if(index>=0){nav.currentIndex=index;nav.positionViewAtIndex(index,ListView.Contain);}
    }
    property string sourceIdentity: (state.source || '')+':'+(state.analysis_revision || '')
    onSourceIdentityChanged: {history=[];selectedPath='section';closed={};limits={};page=0;}
    function selectRecord(r) {
        if(!r || !host.backendReady || host.coreInspecting)return;
        if(detail.id && r.id!==detail.id && !restoring)history=history.concat([{id:detail.id,path:selectedPath,closed:closed,limits:limits,page:page,family:family,query:query}]).slice(-100);
        selectedPath='section';host.inspect(r.id,-1);
    }
    function back() {
        if(!history.length || !host.backendReady || host.coreInspecting)return;
        var h=history[history.length-1];history=history.slice(0,-1);restoring=true;
        family=h.family;query=h.query;page=h.page;closed=h.closed;limits=h.limits;host.inspect(h.id,-1);selectedPath=h.path;restoring=false;
    }
    function activate(row) {
        if(!row)return;
        if(row.kind==='record'){selectRecord(row.record);return;}
        if(row.node.more){var next=Object.assign({},limits);next[row.node.more]=(next[row.node.more] || 100)+100;limits=next;return;}
        selectedPath=row.node.path;
    }
    function fold(row) {
        if(!row || row.kind!=='node' || !row.node.children.length)return;
        var next=Object.assign({},closed);next[row.node.path]=!next[row.node.path];closed=next;
    }
    function focusNavigation(){nav.forceActiveFocus();}
    function nextRegion(){if(nav.activeFocus)fieldList.forceActiveFocus();else nav.forceActiveFocus();}
    function focusSearch(){search.forceActiveFocus();search.selectAll();}
    function findRecord(name){return records.find(function(r){return r.name===name;});}
    orientation: Qt.Horizontal
    handle: Rectangle { implicitWidth:6;color:SplitHandle.hovered?host.blue:host.dividerColor }
    component TextLabel: Label { color:host.ink; textFormat:Text.PlainText; font.pixelSize:12 }
    Rectangle {
        color:host.panel
        SplitView.preferredWidth:460
        SplitView.minimumWidth:280
        SplitView.maximumWidth:view.width*0.6
        ColumnLayout {
            anchors.fill:parent;anchors.margins:8;spacing:6
            RowLayout {
                Layout.fillWidth:true
                TextLabel { text:'STREAM STRUCTURE';font.bold:true;Layout.fillWidth:true }
                Button {objectName:'unifiedBack';text:'← Back';enabled:view.history.length>0 && host.backendReady;onClicked:view.back()}
            }
            ComboBox {Layout.fillWidth:true;model:host.tableFamilies;currentIndex:Math.max(0,host.tableFamilies.indexOf(view.family));onActivated:view.family=currentText}
            TextField {id:search;Layout.fillWidth:true;placeholderText:'Find table, PID, version or UTC time';text:view.query;onTextEdited:view.query=text;selectByMouse:true}
            TextLabel {text:records.length+' distinct payloads · repeated arrivals counted as ×';color:host.muted;Layout.fillWidth:true;wrapMode:Text.Wrap}
            ListView {
                id:nav;objectName:'unifiedTree';Layout.fillWidth:true;Layout.fillHeight:true;clip:true;reuseItems:true
                model:view.navigation;activeFocusOnTab:true
                ScrollBar.vertical:ScrollBar{}
                Keys.onReturnPressed:view.activate(view.navigation[currentIndex])
                Keys.onSpacePressed:view.fold(view.navigation[currentIndex])
                Keys.onRightPressed: {var r=view.navigation[currentIndex];if(r && r.kind==='record')view.activate(r);else if(r && view.closed[r.node.path])view.fold(r);else currentIndex=Math.min(count-1,currentIndex+1);}
                Keys.onLeftPressed: {var r=view.navigation[currentIndex];if(r && r.kind==='node' && r.node.children.length && !view.closed[r.node.path])view.fold(r);else if(r){for(var i=currentIndex-1;i>=0;--i)if(view.navigation[i].depth<r.depth){currentIndex=i;break;}}}
                Keys.onPressed:function(e){if(e.key===Qt.Key_Home){currentIndex=0;e.accepted=true;}else if(e.key===Qt.Key_End){currentIndex=count-1;e.accepted=true;}}
                onCurrentIndexChanged:positionViewAtIndex(currentIndex,ListView.Contain)
                delegate: ItemDelegate {
                    required property var modelData
                    required property int index
                    objectName:'unifiedRow:'+index
                    width:nav.width;height:30
                    leftPadding:6+modelData.depth*14
                    highlighted:modelData.kind==='node' ? modelData.node.path===view.selectedPath : modelData.key===view.detail.id
                    background:Rectangle {color:parent.highlighted?host.selectionSurface:parent.hovered?host.hoverSurface:'transparent';border.width:nav.activeFocus && nav.currentIndex===index?1:0;border.color:host.blue}
                    contentItem:TextLabel {text:(modelData.kind==='record'?'▸ ':modelData.node.children.length?(view.closed[modelData.node.path]?'▸ ':'▾ '):'  ')+modelData.label;elide:Text.ElideRight;verticalAlignment:Text.AlignVCenter;color:modelData.kind==='record' && modelData.record.valid===false?host.removedColor:host.ink}
                    onClicked:{nav.currentIndex=index;nav.forceActiveFocus();view.activate(modelData);}
                    onDoubleClicked:view.fold(modelData)
                    ToolTip {visible:parent.hovered;contentItem:TextLabel {text:modelData.label;wrapMode:Text.Wrap}}
                    Accessible.name:modelData.label
                }
            }
            RowLayout {
                Layout.fillWidth:true
                Button {objectName:'unifiedPrevious';text:'Previous';enabled:page>0;onClicked:page--}
                TextLabel {text:(page+1)+' / '+Math.max(1,Math.ceil(records.length/100));Layout.fillWidth:true;horizontalAlignment:Text.AlignHCenter}
                Button {objectName:'unifiedNext';text:'Next';enabled:(page+1)*100<records.length;onClicked:page++}
            }
        }
    }
    Rectangle {
        color:host.panel
        SplitView.fillWidth:true;SplitView.minimumWidth:400
        ColumnLayout {
            anchors.fill:parent;anchors.margins:12;spacing:8
            TextLabel {objectName:'unifiedTitle';text:detail.id?Model.inspector.title(detail):'Open a transport stream';font.pixelSize:16;font.bold:true;Layout.fillWidth:true;wrapMode:Text.Wrap}
            TextLabel {objectName:'unifiedSummary';visible:!!detail.id;text:Model.inspector.summary(view.detail,view.state);Layout.fillWidth:true;wrapMode:Text.Wrap;color:host.blue}
            TextLabel {visible:!!detail.id;text:'Exact section · '+detail.bytes+' bytes · CRC '+((detail.crc || {}).status || 'unavailable')+' · packets '+detail.first_packet+'–'+detail.last_packet;Layout.fillWidth:true;wrapMode:Text.Wrap;color:host.muted}
            Rectangle {Layout.fillWidth:true;implicitHeight:1;color:host.dividerColor}
            RowLayout {
                Layout.fillWidth:true
                TextLabel {text:selectedNode?selectedNode.label:'Choose a table on the left';font.bold:true;Layout.fillWidth:true;elide:Text.ElideRight}
                Button {objectName:'unifiedHex';text:hexOpen?'Hide Hex':'Show Hex';checkable:true;checked:hexOpen;onClicked:hexOpen=checked}
            }
            RowLayout {
                Layout.fillWidth:true
                TextLabel {text:'FIELD';Layout.preferredWidth:Math.max(150,fieldList.width*0.30);color:host.muted}
                TextLabel {text:'VALUE';Layout.preferredWidth:Math.max(100,fieldList.width*0.25);color:host.muted}
                TextLabel {text:'EXPLANATION';Layout.fillWidth:true;color:host.muted}
            }
            ListView {
                id:fieldList;objectName:'unifiedFields';Layout.fillWidth:true;Layout.fillHeight:true;clip:true;model:view.fieldRows;reuseItems:true;activeFocusOnTab:true
                ScrollBar.vertical:ScrollBar{}
                delegate:Rectangle {
                    required property var modelData
                    required property int index
                    width:fieldList.width;height:Math.max(34,fieldCells.implicitHeight+10);color:index%2?host.surface:'transparent'
                    RowLayout {
                        id:fieldCells;anchors.left:parent.left;anchors.right:parent.right;anchors.margins:5;anchors.verticalCenter:parent.verticalCenter;spacing:8
                        TextLabel {text:modelData.name;Layout.preferredWidth:Math.max(150,fieldList.width*0.30)-8;wrapMode:Text.WrapAnywhere}
                        TextLabel {text:modelData.value;Layout.preferredWidth:Math.max(100,fieldList.width*0.25)-8;wrapMode:Text.WrapAnywhere;color:host.blue;font.family:'Consolas'}
                        TextLabel {text:modelData.help;Layout.fillWidth:true;wrapMode:Text.Wrap;color:host.muted}
                    }
                }
            }
            TextLabel {visible:!!selectedNode && !fieldRows.length;text:'Select a child in the structure tree to inspect its fields.';color:host.muted;Layout.fillWidth:true}
            TextLabel {visible:hexOpen;text:'SELECTED SECTION HEX · byte offsets'+(selectedNode && selectedNode.range?' · descriptor bytes '+selectedNode.range.offset+'–'+(selectedNode.range.offset+selectedNode.range.length-1):'');color:host.muted;Layout.fillWidth:true}
            ScrollView {
                visible:hexOpen;Layout.fillWidth:true;Layout.preferredHeight:Math.min(190,view.height*0.30);clip:true
                TextArea {
                    id:bytes;objectName:'unifiedHexBytes';readOnly:true;selectByMouse:true;textFormat:TextEdit.PlainText;wrapMode:TextEdit.NoWrap;font.family:'Consolas';font.pixelSize:12;color:host.ink
                    text: {var raw=(detail.raw_hex || '').replace(/\s/g,'');var lines=[];for(var i=0;i<raw.length;i+=32)lines.push((i/2).toString(16).padStart(4,'0')+'  '+(raw.slice(i,i+32).match(/../g)||[]).join(' '));return lines.join('\n');}
                    background:Rectangle{color:host.surface}
                }
            }
        }
    }
}
