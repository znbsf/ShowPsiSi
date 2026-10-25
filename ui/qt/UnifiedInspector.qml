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
    property var navigationOrigin: ({})
    property var selectionFilter: ({})
    property var pendingRestore: null
    onDetailChanged: if(detail.id && detail.id!==selectionFilter.id)selectionFilter={id:detail.id,page:page,family:family,query:query,pidFilter:pidFilter}
    property int page: 0
    property string family: "All tables"
    property string query: ""
    property int pidFilter: -1
    property bool hexOpen: true
    property int selectedFieldIndex: -1
    property int selectedByte: -1
    property var selectedField: fieldRows[selectedFieldIndex] && !fieldRows[selectedFieldIndex].groupPath ? fieldRows[selectedFieldIndex] : null
    property var activeRange: selectedField && selectedField.bit_offset!==undefined
        ? {offset:Math.floor(selectedField.bit_offset/8),length:Math.ceil((selectedField.bit_offset%8+selectedField.bit_length)/8)}
        : selectedField ? null : selectedNode && selectedNode.range ? selectedNode.range : null
    property string rawHex: (detail.raw_hex || '').replace(/\s/g,'')
    function selectField(index) {
        var row=fieldRows[index];
        if(row && row.groupPath){var next=Object.assign({},fieldClosed);next[row.groupPath]=!next[row.groupPath];fieldClosed=next;selectedFieldIndex=-1;return;}
        selectedFieldIndex=index;selectedByte=-1;fieldList.currentIndex=index;
        if(activeRange){hexOpen=true;hexRows.positionViewAtIndex(Math.floor(activeRange.offset/16),ListView.Contain);}
    }
    function selectByte(offset) {
        var best=null;
        function visit(n){
            if(!n)return;
            (n.fields || []).forEach(function(f,i){
                if(f.bit_offset!==undefined && f.bit_offset<(offset+1)*8 && f.bit_offset+f.bit_length>offset*8 && (!best || f.bit_length<best.field.bit_length || (f.bit_length===best.field.bit_length && best.field.name==='payload' && f.name!=='payload')))best={node:n,field:f,index:i};
            });
            (n.children || []).forEach(visit);
        }
        visit(root);
        if(best){
            var opened=Object.assign({},closed),path=best.node.path;
            Object.keys(opened).forEach(function(k){if(path===k || path.indexOf(k+'/')===0)delete opened[k];});closed=opened;
            // Make a match beyond the first bounded child page visible as well.
            var expanded=Object.assign({},limits);
            function reveal(n){if(!n)return;var cs=n.children || [];for(var i=0;i<cs.length;i++)if(path===cs[i].path || path.indexOf(cs[i].path+'/')===0){expanded[n.path]=Math.max(expanded[n.path] || 100,i+1);reveal(cs[i]);break;}}
            reveal(root);limits=expanded;selectedPath=path;var rowIndex=fieldRows.findIndex(function(f){return f.nodePath===path && f.name===best.field.name && f.bit_offset===best.field.bit_offset && f.bit_length===best.field.bit_length;});selectField(rowIndex);
            fieldList.positionViewAtIndex(selectedFieldIndex,ListView.Contain);
        }else selectedFieldIndex=-1;
        selectedByte=offset;
    }
    function byteSelected(offset){return activeRange && offset>=activeRange.offset && offset<activeRange.offset+activeRange.length;}
    function byteText(offset){return rawHex.slice(offset*2,offset*2+2).toUpperCase();}
    onFieldRowsChanged: {selectedFieldIndex=-1;selectedByte=-1;}

    property var records: (state.tables || []).filter(function(r){return (pidFilter<0 || Number(r.pid)===pidFilter) && (family==="All tables" || r.name===family) && (!query || Model.inspector.title(r).toLowerCase().indexOf(query.toLowerCase())>=0);}).slice().sort(function(a,b){return a.pid-b.pid || a.table_id-b.table_id || a.first_packet-b.first_packet;})
    property var nodes: Model.inspector.flatten(root,closed,0,limits)
    property var selectedNode: Model.inspector.find(root,selectedPath) || root
    property var fieldClosed: ({})
    property var fieldRows: Model.inspector.fieldTable(selectedNode,fieldClosed,0)
    property var openFamilies: ({})
    function familyOpen(name){return openFamilies[name]===undefined ? name===detail.name || family!=='All tables' : openFamilies[name];}
    property var navigation: {
        var out=[],groups={};
        records.slice(page*100,(page+1)*100).forEach(function(r){if(!groups[r.name])groups[r.name]=[];groups[r.name].push(r);});
        var order=['PAT','PMT','SDT','CAT','EIT','TDT','TOT','NIT','BAT'];
        Object.keys(groups).sort(function(a,b){var x=order.indexOf(a),y=order.indexOf(b);return (x<0?99:x)-(y<0?99:y) || a.localeCompare(b);}).forEach(function(name){
            out.push({kind:'family',key:'family:'+name,label:name+' · '+groups[name].length,name:name,depth:0});
            if(!view.familyOpen(name))return;
            groups[name].forEach(function(r){
                out.push({kind:'record',key:r.id,label:Model.inspector.title(r),record:r,depth:1});
                if(r.id===detail.id)nodes.forEach(function(n){out.push({kind:'node',key:r.id+':'+n.path,label:n.label,node:n,depth:n.depth+2});});
            });
        });return out;
    }
    onRecordsChanged: page=Math.min(page,Math.max(0,Math.ceil(records.length/100)-1))
    onFamilyChanged: page=0
    onQueryChanged: page=0
    onNavigationChanged: Qt.callLater(revealSelection)
    onSelectedPathChanged: {selectedFieldIndex=-1;selectedByte=-1;Qt.callLater(revealSelection);}
    function captureContext() {
        return {openFamilies:openFamilies,id:detail.id,path:selectedPath,closed:closed,limits:limits,page:page,family:family,query:query,pidFilter:pidFilter,
            fieldClosed:fieldClosed,fieldIndex:selectedFieldIndex,fieldScroll:fieldList.contentY,hexScroll:hexRows.contentY,hexOpen:hexOpen,scroll:nav.contentY,focusKey:navigation[nav.currentIndex] ? navigation[nav.currentIndex].key : ""};
    }
    function filterPid(pid) {
        if(detail.id && !navigationOrigin.id)navigationOrigin=captureContext();
        pidFilter=pid;family='All tables';query='';page=0;
    }
    function changeFilter(nextFamily,nextQuery) {
        if(nextFamily===family && nextQuery===query)return;
        if(detail.id && !navigationOrigin.id)navigationOrigin=captureContext();
        family=nextFamily;query=nextQuery;
    }
    function revealSelection() {
        if(pendingRestore) {
            if(detail.id!==pendingRestore.id)return;
            var saved=pendingRestore;pendingRestore=null;
            fieldClosed=saved.fieldClosed || {};hexOpen=saved.hexOpen===undefined?true:saved.hexOpen;
            selectedFieldIndex=saved.fieldIndex===undefined?-1:saved.fieldIndex;
            fieldList.contentY=saved.fieldScroll || 0;hexRows.contentY=saved.hexScroll || 0;
            var focused=navigation.findIndex(function(row){return row.key===saved.focusKey;});
            if(focused>=0)nav.currentIndex=focused;
            nav.contentY=Math.max(nav.originY,Math.min(saved.scroll,nav.originY+Math.max(0,nav.contentHeight-nav.height)));
            return;
        }
        var key=detail.id+':'+selectedPath;
        var index=navigation.findIndex(function(r){return r.key===key;});
        if(index<0)index=navigation.findIndex(function(r){return r.key===detail.id;});
        if(index>=0){nav.currentIndex=index;nav.positionViewAtIndex(index,selectedPath==='section'?ListView.Center:ListView.Contain);}
    }
    property string sourceIdentity: (state.source || '')+':'+(state.analysis_revision || '')
    onSourceIdentityChanged: {history=[];navigationOrigin={};selectionFilter={};pendingRestore=null;pidFilter=-1;selectedPath='section';openFamilies={};closed={};fieldClosed={};limits={};page=0;}
    function selectRecord(r) {
        if(!r || !host.backendReady || host.coreInspecting)return;
        if(detail.id && r.id!==detail.id && !restoring) {
            var saved=navigationOrigin.id===detail.id ? Object.assign({},navigationOrigin) : captureContext();
            if(!navigationOrigin.id && selectionFilter.id===detail.id) {
                saved.page=selectionFilter.page;saved.family=selectionFilter.family;saved.query=selectionFilter.query;saved.pidFilter=selectionFilter.pidFilter;
            }
            history=history.concat([saved]).slice(-100);
        }
        navigationOrigin={};pendingRestore=null;
        selectionFilter={id:r.id,page:page,family:family,query:query,pidFilter:pidFilter};
        var opened=Object.assign({},openFamilies);opened[r.name]=true;openFamilies=opened;
        selectedPath='section';host.inspect(r.id,-1);
    }
    function back() {
        if(!history.length || !host.backendReady || host.coreInspecting)return;
        var h=history[history.length-1];history=history.slice(0,-1);restoring=true;
        navigationOrigin={};selectionFilter={id:h.id,page:h.page,family:h.family,query:h.query,pidFilter:h.pidFilter};pendingRestore=h;
        openFamilies=h.openFamilies || {};pidFilter=h.pidFilter===undefined?-1:h.pidFilter;family=h.family;query=h.query;page=h.page;closed=h.closed;limits=h.limits;host.inspect(h.id,-1);selectedPath=h.path;restoring=false;
        Qt.callLater(revealSelection);
    }
    function activate(row) {
        if(!row)return;
        if(row.kind==='family'){fold(row);return;}
        if(row.kind==='record'){selectRecord(row.record);return;}
        if(row.node.more){var next=Object.assign({},limits);next[row.node.more]=(next[row.node.more] || 100)+100;limits=next;return;}
        selectedPath=row.node.path;
    }
    function fold(row) {
        if(row && row.kind==='family'){var families=Object.assign({},openFamilies);families[row.name]=!familyOpen(row.name);openFamilies=families;return;}
        if(!row || row.kind!=='node' || !row.node.children.length)return;
        var next=Object.assign({},closed);next[row.node.path]=!next[row.node.path];closed=next;
    }
    function focusNavigation(){nav.forceActiveFocus();}
    function nextRegion(){if(nav.activeFocus)fieldList.forceActiveFocus();else if(fieldList.activeFocus && hexOpen)hexRows.forceActiveFocus();else nav.forceActiveFocus();}
    function focusSearch(){search.forceActiveFocus();search.selectAll();}
    function findRecord(name){return records.find(function(r){return r.name===name;});}
    palette.window:host.panel
    palette.base:host.surface
    palette.text:host.ink
    palette.mid:host.muted
    palette.windowText:host.ink
    palette.button:host.surface
    palette.buttonText:host.ink
    palette.highlight:host.selectionSurface
    palette.highlightedText:host.ink
    orientation: Qt.Horizontal
    handle: Rectangle { implicitWidth:6;color:SplitHandle.hovered?host.blue:host.dividerColor }
    component TextLabel: Label { color:host.ink; textFormat:Text.PlainText; font.pixelSize:12 }
    Rectangle {
        color:host.panel
        SplitView.preferredWidth:330
        SplitView.minimumWidth:280
        SplitView.maximumWidth:view.width*0.6
        ColumnLayout {
            anchors.fill:parent;anchors.margins:8;spacing:6
            RowLayout {
                Layout.fillWidth:true
                TextLabel { text:'PSI / SI TABLES';font.bold:true;Layout.fillWidth:true }
                Button {objectName:'unifiedBack';text:'← Back';enabled:view.history.length>0 && host.backendReady;onClicked:view.back()}
            }
            ComboBox {Layout.fillWidth:true;indicator:TextLabel {text:'▾';color:host.muted;x:parent.width-width-10;y:(parent.height-height)/2}
                model:host.tableFamilies;currentIndex:Math.max(0,host.tableFamilies.indexOf(view.family));onActivated:view.changeFilter(currentText,view.query)}
            TextField {id:search;objectName:'unifiedSearch';color:host.ink;placeholderTextColor:host.muted;Layout.fillWidth:true;placeholderText:'Find table, PID, version or UTC time';text:view.query;onTextEdited:view.changeFilter(view.family,text);selectByMouse:true}
            Button {text:'PID '+Model.inspector.hex(view.pidFilter)+' ×';visible:view.pidFilter>=0;onClicked:view.filterPid(-1);Accessible.name:'Clear numeric PID filter'}
            TextLabel {text:records.length+' distinct payloads · repeated arrivals counted as ×';color:host.muted;Layout.fillWidth:true;wrapMode:Text.Wrap}
            ListView {
                id:nav;objectName:'unifiedTree';Layout.fillWidth:true;Layout.fillHeight:true;clip:true;reuseItems:true
                model:view.navigation;activeFocusOnTab:true
                ScrollBar.vertical:ScrollBar{}
                Keys.onReturnPressed:view.activate(view.navigation[currentIndex])
                Keys.onSpacePressed:view.fold(view.navigation[currentIndex])
                Keys.onRightPressed: {var r=view.navigation[currentIndex];if(r && r.kind==='family'){if(!view.familyOpen(r.name))view.fold(r);else currentIndex=Math.min(count-1,currentIndex+1);}else if(r && r.kind==='record')view.activate(r);else if(r && view.closed[r.node.path])view.fold(r);else currentIndex=Math.min(count-1,currentIndex+1);}
                Keys.onLeftPressed: {var r=view.navigation[currentIndex];if(r && r.kind==='family' && view.familyOpen(r.name))view.fold(r);else if(r && r.kind==='node' && r.node.children.length && !view.closed[r.node.path])view.fold(r);else if(r){for(var i=currentIndex-1;i>=0;--i)if(view.navigation[i].depth<r.depth){currentIndex=i;break;}}}
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
                    contentItem:TextLabel {text:(modelData.kind==='family'?(view.familyOpen(modelData.name)?'▾ ':'▸ '):modelData.kind==='record'?'▸ ':modelData.node.children.length?(view.closed[modelData.node.path]?'▸ ':'▾ '):'  ')+modelData.label;elide:Text.ElideRight;verticalAlignment:Text.AlignVCenter;color:modelData.kind==='record' && modelData.record.valid===false?host.removedColor:host.ink}
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
        SplitView.fillWidth:true;SplitView.minimumWidth:500
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
                Layout.fillWidth:true;spacing:8
                TextLabel {text:'Field';Layout.preferredWidth:fieldList.width*0.30-8;color:host.muted}
                TextLabel {text:'Bits';Layout.preferredWidth:44;color:host.muted}
                TextLabel {text:'Value';Layout.preferredWidth:fieldList.width*0.26-8;color:host.muted}
                TextLabel {text:'Comment';Layout.fillWidth:true;color:host.muted}
            }
            ListView {
                id:fieldList;objectName:'unifiedFields';Layout.fillWidth:true;Layout.fillHeight:true;Layout.minimumHeight:110
                clip:true;model:view.fieldRows;reuseItems:true;activeFocusOnTab:true
                ScrollBar.vertical:ScrollBar{}
                Keys.onUpPressed: {view.selectField(Math.max(0,view.selectedFieldIndex-1));positionViewAtIndex(currentIndex,ListView.Contain);}
                Keys.onDownPressed: {view.selectField(Math.min(count-1,view.selectedFieldIndex+1));positionViewAtIndex(currentIndex,ListView.Contain);}
                Keys.onPressed:function(event){
                    if(event.key===Qt.Key_Home){view.selectField(0);positionViewAtBeginning();event.accepted=true;}
                    else if(event.key===Qt.Key_End){view.selectField(count-1);positionViewAtEnd();event.accepted=true;}
                }
                delegate: ItemDelegate {
                    required property var modelData
                    required property int index
                    objectName:'siField:'+index
                    width:fieldList.width;height:Math.max(28,fieldCells.implicitHeight+8);padding:4
                    highlighted:index===view.selectedFieldIndex
                    background:Rectangle {color:parent.highlighted?host.selectionSurface:index%2?host.surface:'transparent';border.width:parent.highlighted?1:0;border.color:host.blue}
                    onClicked:{fieldList.forceActiveFocus();view.selectField(index);}
                    Accessible.name:modelData.name+', '+(modelData.bit_length===undefined?'bit range unknown':modelData.bit_length+' bits')+', '+modelData.value
                    contentItem:RowLayout {
                        id:fieldCells;spacing:8
                        TextLabel {text:(modelData.groupPath?(view.fieldClosed[modelData.groupPath]?'▸ ':'▾ '):'')+modelData.name;leftPadding:Math.min(4,modelData.depth || 0)*12;Layout.preferredWidth:fieldList.width*0.30-8;wrapMode:Text.WrapAnywhere;font.bold:!!modelData.groupPath}
                        TextLabel {text:modelData.groupPath?'':modelData.bit_length===undefined?'—':String(modelData.bit_length);Layout.preferredWidth:44;color:host.muted}
                        TextLabel {text:modelData.value;Layout.preferredWidth:fieldList.width*0.26-8;wrapMode:Text.WrapAnywhere;color:host.blue;font.family:'Consolas'}
                        TextLabel {text:modelData.help || (modelData.groupPath?'':modelData.bit_length===undefined?'Decoded attribute · exact bit range unavailable':'');Layout.fillWidth:true;wrapMode:Text.Wrap;color:host.muted}
                    }
                }
            }
            TextLabel {visible:!!selectedNode && !fieldRows.length;text:'Select a child in the structure tree to inspect its fields.';color:host.muted;Layout.fillWidth:true}
            TextLabel {
                objectName:'siRange';visible:hexOpen;Layout.fillWidth:true;wrapMode:Text.Wrap;color:host.muted
                text:'SECTION HEX · '+(view.selectedField && view.selectedField.bit_offset!==undefined
                    ? view.selectedField.name+' · bit '+view.selectedField.bit_offset+'–'+(view.selectedField.bit_offset+view.selectedField.bit_length-1)+' (MSB first)'
                    : view.selectedField?'Exact bit range unavailable':view.selectedByte>=0?'Byte '+view.selectedByte:'Select a field or byte')
            }
            Flickable {
                id:bytes;objectName:'unifiedHexBytes';visible:hexOpen
                Layout.fillWidth:true;Layout.preferredHeight:Math.min(240,view.height*0.34)
                contentWidth:Math.max(width,680);contentHeight:height;clip:true;flickableDirection:Flickable.HorizontalFlick
                property string text: {var lines=[];for(var i=0;i<view.rawHex.length;i+=32)lines.push((i/2).toString(16).padStart(4,'0')+'  '+(view.rawHex.slice(i,i+32).match(/../g)||[]).join(' '));return lines.join('\n');}
                ScrollBar.horizontal:ScrollBar{}
                Rectangle {width:bytes.contentWidth;height:bytes.height;color:host.surface}
                ListView {
                    id:hexRows;objectName:'siHexRows';width:bytes.contentWidth;height:bytes.height
                    model:Math.ceil(view.rawHex.length/32);clip:true;reuseItems:true;activeFocusOnTab:true
                    ScrollBar.vertical:ScrollBar{}
                    function move(delta){var next=Math.max(0,Math.min(view.rawHex.length/2-1,(view.selectedByte<0?0:view.selectedByte)+delta));view.selectByte(next);positionViewAtIndex(Math.floor(next/16),ListView.Contain);}
                    Keys.onLeftPressed:move(-1)
                    Keys.onRightPressed:move(1)
                    Keys.onUpPressed:move(-16)
                    Keys.onDownPressed:move(16)
                    delegate:Row {
                        id:hexLine;required property int index;height:24;spacing:2
                        TextLabel {width:56;height:24;verticalAlignment:Text.AlignVCenter;text:(hexLine.index*16).toString(16).toUpperCase().padStart(4,'0');font.family:'Consolas';color:host.muted}
                        Repeater {
                            model:16
                            delegate:Rectangle {
                                required property int index
                                property int offset:hexLine.index*16+index
                                objectName:'siByte:'+offset
                                width:25;height:24
                                color:view.byteSelected(offset)?host.selectionSurface:'transparent'
                                border.width:offset===view.selectedByte?1:0;border.color:host.blue
                                TextLabel {anchors.centerIn:parent;text:view.byteText(parent.offset);font.family:'Consolas';color:view.byteSelected(parent.offset)?host.blue:host.ink}
                                MouseArea {anchors.fill:parent;enabled:parent.offset<view.rawHex.length/2;onClicked:{hexRows.forceActiveFocus();view.selectByte(parent.offset);}}
                                Accessible.role:Accessible.Button
                                Accessible.name:'Byte '+offset+' '+view.byteText(offset)
                                Accessible.onPressAction:view.selectByte(offset)
                            }
                        }
                        TextLabel {
                            width:150;height:24;verticalAlignment:Text.AlignVCenter;font.family:'Consolas';color:host.muted
                            text:{var out='';for(var i=0;i<16;i++){var b=view.byteText(hexLine.index*16+i);if(!b)break;var n=parseInt(b,16);out+=n>=32 && n<=126?String.fromCharCode(n):'.';}return out;}
                        }
                    }
                }
            }
        }
    }
}
