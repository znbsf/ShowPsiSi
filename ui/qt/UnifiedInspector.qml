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
    property real hexFraction:0.40
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
        if(activeRange){hexOpen=true;hexRows.positionViewAtIndex(Math.floor(activeRange.offset/10),ListView.Contain);}
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
            reveal(root);limits=expanded;var fieldOpen=Object.assign({},fieldClosed);Object.keys(fieldOpen).forEach(function(k){if(path===k || path.indexOf(k+'/')===0)delete fieldOpen[k];});fieldClosed=fieldOpen;selectedPath=path;var rowIndex=fieldRows.findIndex(function(f){return f.nodePath===path && f.name===best.field.name && f.bit_offset===best.field.bit_offset && f.bit_length===best.field.bit_length;});selectField(rowIndex);
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
    property var fieldRows: root ? [{name:'Section['+((Number(detail.section)||0)+1)+'/'+((Number(detail.last_section)||0)+1)+']',value:'',help:'',depth:0,groupPath:root.path,rootRow:true}].concat(fieldClosed[root.path]?[]:Model.inspector.fieldTable(root,fieldClosed,1)) : []
    property var openFamilies: ({})
    function familyOpen(name){return openFamilies[name]===undefined ? name==='Programs' || name==='PSI Packets' || family!=='All tables' : openFamilies[name];}
    property var navigation: {
        var out=[],groups={};
        records.slice(page*100,(page+1)*100).forEach(function(r){if(!groups[r.name])groups[r.name]=[];groups[r.name].push(r);});
        var programs=records.filter(function(r){return r.name==='PMT';}).slice().sort(function(a,b){return ('Program '+a.extension).localeCompare('Program '+b.extension);});
        if(programs.length){
            out.push({kind:'family',key:'family:Programs',name:'Programs',label:'Programs',depth:0});
            if(view.familyOpen('Programs'))programs.forEach(function(r){out.push({kind:'record',key:'program:'+r.id,label:'Program '+r.extension+' ['+Model.inspector.hex(r.extension)+']',record:r,program:true,depth:1});});
        }
        var order=['PAT','PMT','SDT','CAT','EIT','TDT','TOT','NIT','BAT'];
        out.push({kind:'family',key:'family:PSI Packets',name:'PSI Packets',label:'PSI Packets',depth:0});
        if(view.familyOpen('PSI Packets'))Object.keys(groups).sort(function(a,b){var x=order.indexOf(a),y=order.indexOf(b);return (x<0?99:x)-(y<0?99:y) || a.localeCompare(b);}).forEach(function(name){
            out.push({kind:'family',key:'family:'+name,label:name,name:name,depth:1});
            if(!view.familyOpen(name))return;
            groups[name].forEach(function(r){
                out.push({kind:'record',key:r.id,label:Model.inspector.title(r),record:r,depth:2});
                if(r.id===detail.id && root)out.push({kind:'node',key:r.id+':section',label:'Section['+((Number(r.section)||0)+1)+'/'+((Number(r.last_section)||0)+1)+']',node:root,depth:3});
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
            fieldClosed:fieldClosed,fieldIndex:selectedFieldIndex,fieldScroll:fieldList.contentY,hexFraction:hexFraction,hexScroll:hexRows.contentY,hexOpen:hexOpen,scroll:nav.contentY,focusKey:navigation[nav.currentIndex] ? navigation[nav.currentIndex].key : ""};
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
            fieldClosed=saved.fieldClosed || {};hexFraction=saved.hexFraction || 0.40;hexOpen=saved.hexOpen===undefined?true:saved.hexOpen;
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
        if(index<0)index=navigation.findIndex(function(r){return r.key==='program:'+detail.id;});
        if(index>=0){nav.currentIndex=index;nav.positionViewAtIndex(index,navigation[index].program?ListView.Contain:selectedPath==='section'?ListView.Center:ListView.Contain);}
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
    function focusSearch(){searchVisible=true;search.forceActiveFocus();search.selectAll();}
    function findRecord(name){return records.find(function(r){return r.name===name;});}

    property bool searchVisible:false
    readonly property color classicPaper:'#ffffff'
    readonly property color classicFace:'#efefef'
    readonly property color classicInk:'#000000'
    readonly property color classicSelection:'#ffff00'
    readonly property color classicValue:'#ff0000'
    readonly property string classicFont:'Courier New'
    readonly property string sourceName:String(view.state.source || 'Transport stream').split('\\').pop().split('/').pop()
    readonly property var sourcePacket:view.detail.source_packet || {}
    readonly property string packetRaw:sourcePacket.raw_hex || ''
    function fieldValue(value){return String(value || '').replace(/^0x0+([0-9A-F])/,'0x$1').replace(' [','[');}
    function packetSelected(offset){return sourcePacket.section_offset!==null && sourcePacket.section_offset!==undefined && offset>=sourcePacket.section_offset && offset<sourcePacket.section_offset+sourcePacket.section_bytes && byteSelected(offset-sourcePacket.section_offset);}
    function packetClick(offset){if(sourcePacket.section_offset!==null && sourcePacket.section_offset!==undefined && offset>=sourcePacket.section_offset && offset<sourcePacket.section_offset+sourcePacket.section_bytes)selectByte(offset-sourcePacket.section_offset);else {selectedFieldIndex=-1;selectedByte=-1;}}
    component ClassicButton:Button {
        implicitHeight:23;implicitWidth:Math.max(44,contentItem.implicitWidth+14)
        contentItem:TextLabel {text:parent.text;font.family:'Tahoma';font.pixelSize:11;horizontalAlignment:Text.AlignHCenter;verticalAlignment:Text.AlignVCenter;color:parent.enabled?'black':'#808080'}
        background:Rectangle {color:parent.down?'#d4d0c8':'#efefef';border.color:parent.activeFocus?'#404040':'#808080';Rectangle {anchors.fill:parent;anchors.margins:1;color:'transparent';border.color:'#ffffff'}}
    }
    palette.window:classicFace
    palette.base:classicPaper
    palette.text:classicInk
    palette.mid:'#808080'
    palette.windowText:classicInk
    palette.button:classicFace
    palette.buttonText:classicInk
    palette.highlight:classicSelection
    palette.highlightedText:classicInk
    orientation:Qt.Horizontal
    handle:Rectangle {implicitWidth:5;color:'#c0c0c0';border.color:'#808080';border.width:1}
    component TextLabel:Label {color:view.classicInk;textFormat:Text.PlainText;font.family:view.classicFont;font.pixelSize:14;renderType:Text.NativeRendering}
    component Icon:Image {property string kind:'field';source:Model.inspector.icon(kind);width:16;height:16;sourceSize:Qt.size(16,16);smooth:false}
    component Branch:Item {
        id:branch
        onDepthChanged:branchPaint.requestPaint()
        property int depth:0
        property bool expandable:false
        property bool expanded:false
        Canvas {
            id:branchPaint
            anchors.fill:parent
            onWidthChanged:requestPaint()
            onHeightChanged:requestPaint()
            onPaint:{var c=getContext('2d');c.clearRect(0,0,width,height);c.fillStyle='#a0a0a0';for(var level=0;level<parent.depth;level++){var x=level*16+7;for(var y=0;y<height;y+=3)c.fillRect(x,y,1,1);}for(var xx=Math.max(0,(parent.depth-1)*16+7);xx<width;xx+=3)c.fillRect(xx,Math.floor(height/2),1,1);}
        }
        Rectangle {visible:parent.expandable;anchors.right:parent.right;anchors.verticalCenter:parent.verticalCenter;width:9;height:9;color:'white';border.color:'#808080'
            Rectangle {x:2;y:4;width:5;height:1;color:'#555555'}
            Rectangle {visible:!parent.parent.expanded;x:4;y:2;width:1;height:5;color:'#555555'}
        }
    }
    Rectangle {
        color:classicPaper;border.color:'#808080'
        SplitView.preferredWidth:view.width*0.265;SplitView.minimumWidth:220;SplitView.maximumWidth:view.width*0.6
        ColumnLayout {
            anchors.fill:parent;anchors.margins:2;spacing:1
            RowLayout {Layout.fillWidth:true;spacing:4
                Branch {Layout.preferredWidth:12;Layout.preferredHeight:20;expandable:true;expanded:true}
                Icon {kind:'file'}
                TextLabel {text:view.sourceName;Layout.fillWidth:true;elide:Text.ElideRight;font.pixelSize:13}
            }
            ListView {
                id:nav;objectName:'unifiedTree';Layout.fillWidth:true;Layout.fillHeight:true;clip:true;reuseItems:true
                model:view.navigation;activeFocusOnTab:true
                ScrollBar.vertical:ScrollBar{policy:ScrollBar.AsNeeded}
                Keys.onReturnPressed:view.activate(view.navigation[currentIndex])
                Keys.onSpacePressed:view.fold(view.navigation[currentIndex])
                Keys.onRightPressed:{var r=view.navigation[currentIndex];if(r && r.kind==='family'){if(!view.familyOpen(r.name))view.fold(r);else currentIndex=Math.min(count-1,currentIndex+1);}else if(r && r.kind==='record')view.activate(r);else if(r && view.closed[r.node.path])view.fold(r);else currentIndex=Math.min(count-1,currentIndex+1);}
                Keys.onLeftPressed:{var r=view.navigation[currentIndex];if(r && r.kind==='family' && view.familyOpen(r.name))view.fold(r);else if(r && r.kind==='node' && r.node.children.length && !view.closed[r.node.path])view.fold(r);else if(r){for(var i=currentIndex-1;i>=0;--i)if(view.navigation[i].depth<r.depth){currentIndex=i;break;}}}
                Keys.onPressed:function(e){if(e.key===Qt.Key_Home){currentIndex=0;e.accepted=true;}else if(e.key===Qt.Key_End){currentIndex=count-1;e.accepted=true;}}
                onCurrentIndexChanged:positionViewAtIndex(currentIndex,ListView.Contain)
                delegate:ItemDelegate {
                    required property var modelData
                    required property int index
                    objectName:'unifiedRow:'+index;width:nav.width;height:21;padding:0
                    highlighted:modelData.kind==='node'?modelData.node.path===view.selectedPath:modelData.kind==='record' && modelData.record.id===view.detail.id
                    background:Rectangle {color:'white'}
                    contentItem:Row {
                        spacing:3
                        Branch {depth:modelData.depth+1;width:(modelData.depth+1)*16;height:21;expandable:modelData.kind==='family' || (modelData.kind==='node' && modelData.node.children.length>0);expanded:modelData.kind==='family'?view.familyOpen(modelData.name):modelData.kind==='node' && !view.closed[modelData.node.path]}
                        Icon {anchors.verticalCenter:parent.verticalCenter;kind:modelData.kind==='family'?(modelData.name==='Programs'?'programs':modelData.name==='PSI Packets'?'psi':modelData.name):modelData.program?'program':modelData.kind==='record'?modelData.record.name:modelData.node.label.toLowerCase().indexOf('descriptor')>=0?'descriptor':'field'}
                        Rectangle {width:Math.min(nav.width-(modelData.depth+1)*16-26,navText.implicitWidth+4);height:19;anchors.verticalCenter:parent.verticalCenter;color:'white';border.width:parent.parent.highlighted?1:0;border.color:'#c00000'
                            TextLabel {id:navText;anchors.fill:parent;anchors.leftMargin:2;verticalAlignment:Text.AlignVCenter;text:modelData.label;font.pixelSize:13;elide:Text.ElideRight}
                        }
                    }
                    onClicked:{nav.currentIndex=index;nav.forceActiveFocus();view.activate(modelData);}
                    onDoubleClicked:if(modelData.kind==='node')view.fold(modelData)
                    ToolTip {visible:parent.hovered;text:modelData.label}
                    Accessible.name:modelData.label
                }
            }
            RowLayout {Layout.fillWidth:true;spacing:2
                ClassicButton {objectName:'unifiedBack';text:'Back';implicitHeight:23;enabled:view.history.length>0 && host.backendReady;onClicked:view.back()}
                ComboBox {Layout.fillWidth:true;implicitHeight:23;font.pixelSize:11;model:host.tableFamilies;currentIndex:Math.max(0,host.tableFamilies.indexOf(view.family));onActivated:view.changeFilter(currentText,view.query)}
                ClassicButton {text:'Find';implicitHeight:23;onClicked:view.focusSearch()}
            }
            TextField {id:search;objectName:'unifiedSearch';visible:view.searchVisible;Layout.fillWidth:true;implicitHeight:24;color:'black';placeholderTextColor:'#606060';placeholderText:'Find table / PID';text:view.query;onTextEdited:view.changeFilter(view.family,text);selectByMouse:true}
            ClassicButton {text:'PID '+Model.inspector.hex(view.pidFilter)+' ×';visible:view.pidFilter>=0;implicitHeight:23;onClicked:view.filterPid(-1);Accessible.name:'Clear numeric PID filter'}
            RowLayout {visible:view.records.length>100;Layout.fillWidth:true;spacing:2
                ClassicButton {objectName:'unifiedPrevious';text:'Previous';implicitHeight:23;enabled:page>0;onClicked:page--}
                TextLabel {text:(page+1)+' / '+Math.max(1,Math.ceil(records.length/100));Layout.fillWidth:true;horizontalAlignment:Text.AlignHCenter;font.pixelSize:12}
                ClassicButton {objectName:'unifiedNext';text:'Next';implicitHeight:23;enabled:(page+1)*100<records.length;onClicked:page++}
            }
        }
    }
    Rectangle {
        color:classicFace;border.color:'#808080'
        SplitView.fillWidth:true;SplitView.minimumWidth:550
        ColumnLayout {
            anchors.fill:parent;anchors.margins:3;spacing:2
            Rectangle {
                Layout.fillWidth:true;implicitHeight:28;border.color:'#8197a8'
                gradient:Gradient {GradientStop {position:0;color:'#e6eef4'}GradientStop {position:1;color:'#b5cadb'}}
                RowLayout {anchors.fill:parent;anchors.margins:3;spacing:5
                    Icon {kind:view.detail.name || 'psi'}
                    TextLabel {objectName:'unifiedTitle';Layout.fillWidth:true;font.family:'Tahoma';font.pixelSize:13;elide:Text.ElideRight
                        text:detail.id?view.sourceName+' - '+detail.name+' : '+(detail.name==='PMT'?'Program ':'')+Model.inspector.hex(detail.extension || 0)+' PID['+Model.inspector.hex(detail.pid)+']'+(Model.inspector.shortSyntax(detail)?'':' Version '+detail.version)+(detail.name==='PMT'?' PCR_PID['+Model.inspector.hex((detail.fields || {}).pcr_pid || 0)+']':''):'Open a transport stream'
                    }
                    ClassicButton {objectName:'unifiedHex';text:hexOpen?'Hex −':'Hex +';implicitHeight:21;checkable:true;checked:hexOpen;onClicked:hexOpen=checked;font.pixelSize:10}
                }
            }
            // The original field table is dense and unstriped, with a tree in
            // the Field column, red values and a solid yellow selection.
            Rectangle {
                Layout.fillWidth:true;implicitHeight:23;color:classicFace;border.color:'#a0a0a0'
                Row {anchors.fill:parent
                    Repeater {model:[{name:'Field',ratio:0.37},{name:'Bits',ratio:0.12},{name:'Value',ratio:0.12},{name:'Comment',ratio:0.39}]
                        delegate:Rectangle {required property var modelData;width:parent.width*modelData.ratio;height:parent.height;color:'transparent';border.color:'#b0b0b0';TextLabel {anchors.fill:parent;anchors.leftMargin:6;verticalAlignment:Text.AlignVCenter;text:modelData.name}}
                    }
                }
            }
            ListView {
                id:fieldList;objectName:'unifiedFields';Layout.fillWidth:true;Layout.fillHeight:true;Layout.minimumHeight:120
                clip:true;model:view.fieldRows;reuseItems:true;activeFocusOnTab:true
                ScrollBar.vertical:ScrollBar{}
                Keys.onUpPressed:{view.selectField(Math.max(0,view.selectedFieldIndex-1));positionViewAtIndex(currentIndex,ListView.Contain);}
                Keys.onDownPressed:{view.selectField(Math.min(count-1,view.selectedFieldIndex+1));positionViewAtIndex(currentIndex,ListView.Contain);}
                Keys.onPressed:function(e){if(e.key===Qt.Key_Home){view.selectField(0);positionViewAtBeginning();e.accepted=true;}else if(e.key===Qt.Key_End){view.selectField(count-1);positionViewAtEnd();e.accepted=true;}}
                delegate:ItemDelegate {
                    required property var modelData
                    required property int index
                    objectName:'siField:'+index;width:fieldList.width;height:20;padding:0
                    highlighted:index===view.selectedFieldIndex
                    background:Rectangle {color:parent.highlighted?view.classicSelection:view.classicPaper;Rectangle {anchors.bottom:parent.bottom;width:parent.width;height:1;color:'#ededed'}}
                    onClicked:{fieldList.forceActiveFocus();view.selectField(index);}
                    Accessible.name:modelData.name+', '+(modelData.bit_length===undefined?'bit range unknown':modelData.bit_length+' bits')+', '+modelData.value
                    contentItem:Row {
                        Item {width:fieldList.width*0.37;height:20;clip:true
                            Row {anchors.fill:parent;spacing:3
                                Branch {depth:modelData.depth || 0;width:12+(modelData.depth || 0)*16;height:20;expandable:!!modelData.groupPath;expanded:!view.fieldClosed[modelData.groupPath]}
                                Icon {anchors.verticalCenter:parent.verticalCenter;kind:'field'}
                                TextLabel {height:20;verticalAlignment:Text.AlignVCenter;text:modelData.name}
                            }
                        }
                        TextLabel {width:fieldList.width*0.12;height:20;leftPadding:6;verticalAlignment:Text.AlignVCenter;text:modelData.groupPath?'':modelData.bit_length===undefined?'—':String(modelData.bit_length)}
                        TextLabel {width:fieldList.width*0.12;height:20;leftPadding:6;verticalAlignment:Text.AlignVCenter;text:view.fieldValue(modelData.value);color:view.classicValue;elide:Text.ElideRight}
                        TextLabel {width:fieldList.width*0.39;height:20;leftPadding:6;verticalAlignment:Text.AlignVCenter;text:modelData.help || '';elide:Text.ElideRight}
                    }
                    ToolTip {visible:parent.hovered;text:modelData.name+'  '+modelData.value+(modelData.help?'  '+modelData.help:'')}
                }
                Rectangle {z:-1;anchors.fill:parent;color:'white'}
            }
            Rectangle {objectName:'siPaneDivider';Layout.fillWidth:true;implicitHeight:5;color:'#d0d0d0';border.color:'#ffffff'
                MouseArea {id:splitGrip;anchors.fill:parent;cursorShape:Qt.SizeVerCursor;property real startY:0;property real startFraction:0
                    onPressed:function(mouse){startY=mapToItem(view,mouse.x,mouse.y).y;startFraction=view.hexFraction;}
                    onPositionChanged:function(mouse){if(pressed)view.hexFraction=Math.max(0.20,Math.min(0.65,startFraction-(mapToItem(view,mouse.x,mouse.y).y-startY)/view.height));}
                }
            }
            RowLayout {
                visible:hexOpen;Layout.fillWidth:true;Layout.preferredHeight:view.height*view.hexFraction;Layout.minimumHeight:Math.min(200,view.height*view.hexFraction);Layout.maximumHeight:view.height*view.hexFraction;spacing:4
                ColumnLayout {
                    Layout.fillWidth:true;Layout.preferredWidth:1;Layout.fillHeight:true;spacing:1
                    Rectangle {Layout.fillWidth:true;implicitHeight:25;color:classicFace;border.color:'#ffffff'
                        TextLabel {anchors.fill:parent;horizontalAlignment:Text.AlignHCenter;verticalAlignment:Text.AlignVCenter;font.family:'Tahoma';font.pixelSize:12;text:'Section No '+(detail.section || 0)+' : Source Packet '+(view.sourcePacket.packet_index===undefined?'—':view.sourcePacket.packet_index)}
                    }
                    Flickable {
                        id:packetBytes;objectName:'siPacketHex';Layout.fillWidth:true;Layout.fillHeight:true;contentWidth:Math.max(width,390);contentHeight:height;clip:true;flickableDirection:Flickable.HorizontalFlick
                        ScrollBar.horizontal:ScrollBar{}
                        Rectangle {width:packetBytes.contentWidth;height:packetBytes.height;color:'#d4d4d4'}
                        ListView {
                            objectName:'siPacketRows';width:packetBytes.contentWidth;height:packetBytes.height;clip:true;model:Math.ceil(view.packetRaw.length/20);reuseItems:true
                            ScrollBar.vertical:ScrollBar{}
                            delegate:Row {
                                id:packetLine;required property int index;height:18;spacing:0
                                TextLabel {width:42;height:18;text:(packetLine.index*10).toString(16).toUpperCase().padStart(4,'0');color:'#ff0000'}
                                Repeater {model:10
                                    delegate:Rectangle {required property int index;property int offset:packetLine.index*10+index;width:24;height:18;color:view.packetSelected(offset)?'#ffff00':'transparent'
                                        TextLabel {anchors.centerIn:parent;text:view.packetRaw.slice(parent.offset*2,parent.offset*2+2);color:parent.offset<4?'#ff0000':'#0000ff'}
                                        MouseArea {anchors.fill:parent;enabled:parent.offset<view.packetRaw.length/2;onClicked:view.packetClick(parent.offset)}
                                    }
                                }
                                Rectangle {width:100;height:18;color:'#c0d8c8'
                                    TextLabel {anchors.fill:parent;leftPadding:2;text:{var out='';for(var i=0;i<10;i++){var b=view.packetRaw.slice((packetLine.index*10+i)*2,(packetLine.index*10+i)*2+2);if(!b)break;var n=parseInt(b,16);out+=n>=32&&n<=126?String.fromCharCode(n):'.';}return out;}}
                                }
                            }
                        }
                        TextLabel {visible:!view.packetRaw;anchors.fill:parent;anchors.margins:8;wrapMode:Text.Wrap;text:view.sourcePacket.status==='source_changed'?'Source file changed. Analyze again to view its original packet.':'Original packet unavailable for this section.'}
                    }
                }
                ColumnLayout {
                    Layout.fillWidth:true;Layout.preferredWidth:1;Layout.fillHeight:true;spacing:1
                    Rectangle {Layout.fillWidth:true;implicitHeight:25;color:classicFace;border.color:'#ffffff'
                        TextLabel {anchors.fill:parent;horizontalAlignment:Text.AlignHCenter;verticalAlignment:Text.AlignVCenter;font.family:'Tahoma';font.pixelSize:12;text:'Section No '+(detail.section || 0)+' : Section '+((detail.section || 0)+1)+' of '+((detail.last_section || 0)+1)}
                    }
                    Flickable {
                        id:bytes;objectName:'unifiedHexBytes';Layout.fillWidth:true;Layout.fillHeight:true
                        contentWidth:Math.max(width,390);contentHeight:height;clip:true;flickableDirection:Flickable.HorizontalFlick
                        property string text:{var lines=[];for(var i=0;i<view.rawHex.length;i+=20)lines.push((i/2).toString(16).padStart(4,'0')+'  '+(view.rawHex.slice(i,i+20).match(/../g)||[]).join(' '));return lines.join('\n');}
                        ScrollBar.horizontal:ScrollBar{}
                        Rectangle {width:bytes.contentWidth;height:bytes.height;color:'#d4d4d4'}
                        ListView {
                            id:hexRows;objectName:'siHexRows';width:bytes.contentWidth;height:bytes.height;model:Math.ceil(view.rawHex.length/20);clip:true;reuseItems:true;activeFocusOnTab:true
                            ScrollBar.vertical:ScrollBar{}
                            function move(delta){var next=Math.max(0,Math.min(view.rawHex.length/2-1,(view.selectedByte<0?0:view.selectedByte)+delta));view.selectByte(next);positionViewAtIndex(Math.floor(next/10),ListView.Contain);}
                            Keys.onLeftPressed:move(-1)
                            Keys.onRightPressed:move(1)
                            Keys.onUpPressed:move(-10)
                            Keys.onDownPressed:move(10)
                            delegate:Row {
                                id:hexLine;required property int index;height:18;spacing:0
                                TextLabel {width:42;height:18;text:(hexLine.index*10).toString(16).toUpperCase().padStart(4,'0');color:'#ff0000'}
                                Repeater {model:10
                                    delegate:Rectangle {
                                        required property int index
                                        property int offset:hexLine.index*10+index
                                        objectName:'siByte:'+offset;width:24;height:18;color:view.byteSelected(offset)?view.classicSelection:'transparent'
                                        border.width:offset===view.selectedByte?1:0;border.color:'#800000'
                                        TextLabel {anchors.centerIn:parent;text:view.byteText(parent.offset);color:parent.offset<3?'#ff0000':'#0000ff'}
                                        MouseArea {anchors.fill:parent;enabled:parent.offset<view.rawHex.length/2;onClicked:{hexRows.forceActiveFocus();view.selectByte(parent.offset);}}
                                        Accessible.role:Accessible.Button
                                        Accessible.name:'Byte '+offset+' '+view.byteText(offset)
                                        Accessible.onPressAction:view.selectByte(offset)
                                    }
                                }
                                Rectangle {width:100;height:18;color:'#c0d8c8'
                                    TextLabel {anchors.fill:parent;leftPadding:2;text:{var out='';for(var i=0;i<10;i++){var b=view.byteText(hexLine.index*10+i);if(!b)break;var n=parseInt(b,16);out+=n>=32&&n<=126?String.fromCharCode(n):'.';}return out;}}
                                }
                            }
                        }
                    }
                }
            }
            TextLabel {
                objectName:'siRange';Layout.fillWidth:true;font.family:'Tahoma';font.pixelSize:11;elide:Text.ElideRight
                text:view.selectedField && view.selectedField.bit_offset!==undefined ? view.selectedField.name+' : '+view.selectedField.bit_length+' bits  (bit '+view.selectedField.bit_offset+'–'+(view.selectedField.bit_offset+view.selectedField.bit_length-1)+')' : view.selectedField?'Exact bit range unavailable':detail.id?'PID '+Model.inspector.hex(detail.pid)+'   '+detail.bytes+' bytes   CRC '+((detail.crc || {}).status || 'unavailable'):'Ready'
            }
        }
    }
}
