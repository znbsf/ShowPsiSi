import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../tauri/web/inspector-model.js" as Model

SplitView {
    id: view
    required property var host
    property var organization: ({})
    property string organizationStatus: ""
    property var state: host.analysisState
    // Inspect clears the backend payload while the next response is in flight.
    // Keep the last presentation until a replacement arrives, without changing
    // the backend's stale-result/failed-inspection contract.
    property var incomingDetail: host.detail
    property bool inspectionPending: host.coreInspecting
    property var detail: ({})
    onIncomingDetailChanged: if(incomingDetail.id || !inspectionPending)detail=incomingDetail
    onInspectionPendingChanged: if(!inspectionPending)Qt.callLater(function(){if(!inspectionPending){if(!incomingDetail.id){detail=incomingDetail;pendingNode=null;}else completeNodeSelection();}})
    Component.onCompleted: {detail=incomingDetail;syncNavigation();}
    property var root: Model.inspector.structure(detail)
    property var tableTrees: ({})
    property var treeOrder: []
    property var expandedRecords: ({})
    property var treeClosed: ({})
    property var treeLimits: ({})
    property var pendingNode: null
    onRootChanged: {
        if(root && detail.id){
            var trees=Object.assign({},tableTrees);trees[detail.id]=root;
            var order=treeOrder.filter(function(id){return id!==detail.id;});order.push(detail.id);
            while(order.length>64){var expired=order.shift();delete trees[expired];}
            tableTrees=trees;treeOrder=order;
            Qt.callLater(completeNodeSelection);
        }
    }
    function completeNodeSelection(){
        if(!pendingNode || pendingNode.id!==detail.id || inspectionPending)return;
        var path=pendingNode.path;pendingNode=null;focusNode(path);
    }
    function focusNode(path){
        var node=Model.inspector.find(root,path);if(!node)return;
        var opened=Object.assign({},fieldClosed);
        Object.keys(opened).forEach(function(k){if(path===k || path.indexOf(k+'/')===0)delete opened[k];});fieldClosed=opened;
        selectedPath=path;selectedByte=-1;
        var index=fieldRows.findIndex(function(r){return r.groupPath===path;});
        selectedFieldIndex=index;fieldList.currentIndex=index;
        if(index>=0)fieldList.positionViewAtIndex(index,ListView.Beginning);
        if(activeRange){hexOpen=true;hexRows.positionViewAtIndex(Math.floor(activeRange.offset/10),ListView.Contain);}
    }
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
        : selectedField || selectedPath==='section' ? null : Model.inspector.wireRange(selectedNode)
    property string rawHex: (detail.raw_hex || '').replace(/\s/g,'')
    function selectField(index) {
        var row=fieldRows[index];
        if(row && row.groupPath){
            var scroll=fieldList.contentY;
            selectedPath=row.groupPath;var next=Object.assign({},fieldClosed);next[row.groupPath]=!next[row.groupPath];fieldClosed=next;
            selectedFieldIndex=index;selectedByte=-1;fieldList.currentIndex=index;
            fieldList.forceLayout();
            fieldList.contentY=Math.max(fieldList.originY,Math.min(scroll,fieldList.originY+Math.max(0,fieldList.contentHeight-fieldList.height)));
            return;
        }
        selectedFieldIndex=index;selectedByte=-1;fieldList.currentIndex=index;
        if(activeRange){hexOpen=true;hexRows.positionViewAtIndex(Math.floor(activeRange.offset/10),ListView.Contain);}
    }
    function focusField(index) {
        var row=fieldRows[index];if(!row)return;
        if(row.groupPath){selectedPath=row.groupPath;selectedFieldIndex=index;selectedByte=-1;fieldList.currentIndex=index;}
        else selectField(index);
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
    function familyOpen(name){return openFamilies[name]===undefined ? name==='Programs' || name==='PSI Packets' || name.indexOf('network:')===0 || family!=='All tables' : openFamilies[name];}
    property var navigation: {
        var out=[],groups={};
        records.slice(page*100,(page+1)*100).forEach(function(r){if(!groups[r.name])groups[r.name]=[];groups[r.name].push(r);});
        var programRows=Model.inspector.programTree(state, (state.tables || []).filter(function(r){return (pidFilter<0 || Number(r.pid)===pidFilter) && (family==='All tables' || r.name===family);}), organization, openFamilies, query.toLowerCase());
        if(programRows.length){
            out.push({kind:'family',key:'family:Programs',name:'Programs',label:'Programs',depth:0});
            if(view.familyOpen('Programs'))programRows.forEach(function(row){out.push(row);if(row.kind==='record' && expandedRecords[row.key])out=out.concat(Model.inspector.tableNavigation(tableTrees[row.record.id],row.record,row.key,treeClosed,treeLimits,row.depth+1));});
        }
        var order=['PAT','PMT','SDT','CAT','EIT','TDT','TOT','NIT','BAT'];
        out.push({kind:'family',key:'family:PSI Packets',name:'PSI Packets',label:'PSI Packets',depth:0});
        if(view.familyOpen('PSI Packets'))Object.keys(groups).sort(function(a,b){var x=order.indexOf(a),y=order.indexOf(b);return (x<0?99:x)-(y<0?99:y) || a.localeCompare(b);}).forEach(function(name){
            out.push({kind:'family',key:'family:'+name,label:name,name:name,depth:1});
            if(!view.familyOpen(name))return;
            groups[name].forEach(function(r){
                out.push({kind:'record',key:r.id,label:Model.inspector.navigationTitle(r,tableTrees[r.id]),record:r,depth:2});
                if(expandedRecords[r.id])out=out.concat(Model.inspector.tableNavigation(tableTrees[r.id],r,r.id,treeClosed,treeLimits,3));
            });
        });return out;
    }
    onRecordsChanged: page=Math.min(page,Math.max(0,Math.ceil(records.length/100)-1))
    onFamilyChanged: page=0
    onQueryChanged: page=0
    FontMetrics {id:navigationMetrics;font.family:view.classicFont;font.pixelSize:13}
    readonly property real navigationWidth: navigation.reduce(function(width,row){return Math.max(width,(row.depth+1)*16+30+navigationMetrics.advanceWidth(row.label));},0)
    property bool syncingNavigation:false
    ListModel {id:navigationModel;dynamicRoles:true}
    onNavigationChanged: syncNavigation()
    function syncNavigation() {
        if(!nav || !navigationModel)return;
        // Update keyed rows in place: a new detail must not reset the ListView.
        var oldIndex=nav.currentIndex,focusKey=oldIndex>=0 && oldIndex<navigationModel.count?navigationModel.get(oldIndex).rowData.key:'';
        var top=nav.indexAt(1,nav.contentY+1),anchor=top>=0?navigationModel.get(top).rowData.key:'',offset=top>=0?nav.contentY-top*21:0;
        var oldY=nav.contentY;
        syncingNavigation=true;
        for(var i=0;i<navigation.length;i++){
            if(i>=navigationModel.count)navigationModel.append({rowData:navigation[i]});
            else if(navigationModel.get(i).rowData.key===navigation[i].key)navigationModel.setProperty(i,'rowData',navigation[i]);
            else {
                var found=-1;for(var j=i+1;j<navigationModel.count;j++)if(navigationModel.get(j).rowData.key===navigation[i].key){found=j;break;}
                if(found>=0){navigationModel.move(found,i,1);navigationModel.setProperty(i,'rowData',navigation[i]);}
                else navigationModel.insert(i,{rowData:navigation[i]});
            }
        }
        if(navigationModel.count>navigation.length)navigationModel.remove(navigation.length,navigationModel.count-navigation.length);
        nav.forceLayout();
        var focused=navigation.findIndex(function(row){return row.key===focusKey;});
        nav.currentIndex=focused>=0?focused:Math.min(oldIndex,navigation.length-1);
        var anchored=navigation.findIndex(function(row){return row.key===anchor;});
        nav.contentY=Math.max(nav.originY,Math.min(anchored>=0?anchored*21+offset:oldY,nav.originY+Math.max(0,nav.contentHeight-nav.height)));
        syncingNavigation=false;
        if(pendingRestore)Qt.callLater(revealSelection);
    }
    onSelectedPathChanged: {selectedFieldIndex=-1;selectedByte=-1;}
    function captureContext() {
        return {expandedRecords:expandedRecords,treeClosed:treeClosed,treeLimits:treeLimits,openFamilies:openFamilies,id:detail.id,path:selectedPath,closed:closed,limits:limits,page:page,family:family,query:query,pidFilter:pidFilter,
            fieldClosed:fieldClosed,fieldIndex:selectedFieldIndex,field:selectedField?{nodePath:selectedField.nodePath,name:selectedField.name,bit_offset:selectedField.bit_offset,bit_length:selectedField.bit_length}:null,fieldColumns:fieldColumnWidths.slice(),fieldScroll:fieldList.contentY,fieldX:fieldList.contentX,hexFraction:hexFraction,hexScroll:hexRows.contentY,hexX:bytes.contentX,packetScroll:packetRows.contentY,packetX:packetBytes.contentX,hexOpen:hexOpen,scroll:nav.contentY,navX:nav.contentX,focusKey:navigation[nav.currentIndex] ? navigation[nav.currentIndex].key : ""};
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
            if(saved.fieldColumns)fieldColumnWidths=saved.fieldColumns.slice();
            selectedFieldIndex=saved.field ? fieldRows.findIndex(function(f){return !f.groupPath && f.nodePath===saved.field.nodePath && f.name===saved.field.name && f.bit_offset===saved.field.bit_offset && f.bit_length===saved.field.bit_length;}) : saved.fieldIndex===undefined?-1:saved.fieldIndex;
            fieldList.contentY=saved.fieldScroll || 0;fieldList.contentX=saved.fieldX || 0;hexRows.contentY=saved.hexScroll || 0;bytes.contentX=saved.hexX || 0;
            packetRows.contentY=saved.packetScroll || 0;packetBytes.contentX=saved.packetX || 0;nav.contentX=saved.navX || 0;
            var focused=navigation.findIndex(function(row){return row.key===saved.focusKey;});
            if(focused>=0)nav.currentIndex=focused;
            nav.contentY=Math.max(nav.originY,Math.min(saved.scroll,nav.originY+Math.max(0,nav.contentHeight-nav.height)));
            return;
        }
        var key=detail.id+':'+selectedPath;
        var index=navigation.findIndex(function(r){return r.key===key;});
        if(index<0)index=navigation.findIndex(function(r){return r.key===detail.id;});
        if(index<0)index=navigation.findIndex(function(r){return r.record && r.record.id===detail.id;});
        if(index>=0){nav.currentIndex=index;nav.positionViewAtIndex(index,ListView.Contain);}
    }
    property string sourceIdentity: (state.source || '')+':'+(state.analysis_revision || '')
    onSourceIdentityChanged: {tableTrees={};treeOrder=[];expandedRecords={};treeClosed={};treeLimits={};pendingNode=null;history=[];navigationOrigin={};selectionFilter={};pendingRestore=null;pidFilter=-1;selectedPath='section';openFamilies={};closed={};fieldClosed={};limits={};page=0;}
    function selectRecord(r,rowKey,nodePath,expand) {
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
        if(expand!==false){
            if(!familyOpen(r.name)){var opened=Object.assign({},openFamilies);opened[r.name]=true;openFamilies=opened;}
            var expanded=Object.assign({},expandedRecords);expanded[rowKey || r.id]=true;expandedRecords=expanded;
        }
        pendingNode=nodePath?{id:r.id,path:nodePath}:null;
        selectedPath='section';if(r.id!==detail.id)host.inspect(r.id,-1);else if(nodePath)completeNodeSelection();
    }
    function back() {
        if(!history.length || !host.backendReady || host.coreInspecting)return;
        var h=history[history.length-1];history=history.slice(0,-1);restoring=true;
        navigationOrigin={};selectionFilter={id:h.id,page:h.page,family:h.family,query:h.query,pidFilter:h.pidFilter};pendingRestore=h;
        pendingNode=null;expandedRecords=h.expandedRecords || {};treeClosed=h.treeClosed || {};treeLimits=h.treeLimits || {};
        openFamilies=h.openFamilies || {};pidFilter=h.pidFilter===undefined?-1:h.pidFilter;family=h.family;query=h.query;page=h.page;closed=h.closed;limits=h.limits;host.inspect(h.id,-1);selectedPath=h.path;restoring=false;
        Qt.callLater(revealSelection);
    }
    function activate(row) {
        if(!row || row.kind==='info')return;
        if(row.kind==='family'){if(row.sourceRecord)selectRecord(row.sourceRecord,undefined,undefined,false);return;}
        if(row.kind==='record'){selectRecord(row.record,row.key,undefined,false);return;}
        if(row.kind==='more'){var next=Object.assign({},treeLimits);next[row.limitKey]=(next[row.limitKey] || 100)+100;treeLimits=next;return;}
        if(row.record.id!==detail.id)selectRecord(row.record,row.ownerKey,row.node.path);
        else focusNode(row.node.path);
    }
    function expandable(row){return !!row && (row.kind==='family' || row.kind==='record' || !!row.expandable);}
    function rowOpen(row){
        if(row.kind==='record')return !!expandedRecords[row.key] && (!!tableTrees[row.record.id] || inspectionPending && selectionFilter.id===row.record.id);
        if(row.kind==='node')return !treeClosed[row.key];
        if(row.kind!=='family')return false;
        return openFamilies[row.name]===undefined && row.defaultOpen!==undefined?row.defaultOpen:familyOpen(row.name);
    }
    function fold(row) {
        if(!row || !expandable(row))return;
        if(row.kind==='family'){var families=Object.assign({},openFamilies);families[row.name]=!rowOpen(row);openFamilies=families;return;}
        if(row.kind==='record'){
            var wasOpen=rowOpen(row),expanded=Object.assign({},expandedRecords);expanded[row.key]=!wasOpen;expandedRecords=expanded;
            // The first click of a double-click may already have started inspect.
            // Remember expansion immediately so the arriving tree opens once.
            if(!wasOpen && !tableTrees[row.record.id] && !inspectionPending)selectRecord(row.record,row.key);
            return;
        }
        var next=Object.assign({},treeClosed);next[row.key]=!next[row.key];treeClosed=next;
    }
    function focusNavigation(){nav.forceActiveFocus();}
    function nextRegion(){if(nav.activeFocus)fieldList.forceActiveFocus();else if(fieldList.activeFocus && hexOpen)hexRows.forceActiveFocus();else nav.forceActiveFocus();}
    function focusSearch(){searchVisible=true;search.forceActiveFocus();search.selectAll();}
    function findRecord(name){return records.find(function(r){return r.name===name;});}

    property var fieldColumnWidths: [-1,-1,-1,-1]
    function fieldColumnWidth(index){var ratios=[0.37,0.12,0.12,0.39],minimum=[120,48,64,120];return fieldColumnWidths[index]>0?fieldColumnWidths[index]:Math.max(minimum[index],fieldList.width*ratios[index]);}
    function resizeFieldColumn(index,width){var next=fieldColumnWidths.slice();next[index]=Math.max([120,48,64,120][index],width);fieldColumnWidths=next;}
    function fitFieldColumn(index){
        var width=columnMetrics.advanceWidth(['Field','Bits','Value','Comment'][index])+20;
        fieldRows.forEach(function(row){var text=index===0?row.name:index===1?(row.bit_length===undefined?'':String(row.bit_length)):index===2?fieldValue(row.value):row.help || '';width=Math.max(width,columnMetrics.advanceWidth(String(text))+20+(index===0?35+(row.depth || 0)*16:0));});
        resizeFieldColumn(index,width);
    }
    FontMetrics {id:columnMetrics;font.family:view.classicFont;font.pixelSize:14}
    readonly property real fieldTableWidth:fieldColumnWidth(0)+fieldColumnWidth(1)+fieldColumnWidth(2)+fieldColumnWidth(3)
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
                model:navigationModel;activeFocusOnTab:true
                contentWidth:Math.max(width,view.navigationWidth);flickableDirection:Flickable.AutoFlickDirection
                ScrollBar.horizontal:ScrollBar{policy:ScrollBar.AsNeeded}
                ScrollBar.vertical:ScrollBar{policy:ScrollBar.AsNeeded}
                Keys.onReturnPressed:view.activate(view.navigation[currentIndex])
                Keys.onSpacePressed:view.fold(view.navigation[currentIndex])
                Keys.onRightPressed:{var r=view.navigation[currentIndex];if(view.expandable(r) && !view.rowOpen(r))view.fold(r);else currentIndex=Math.min(count-1,currentIndex+1);}
                Keys.onLeftPressed:{var r=view.navigation[currentIndex];if(view.expandable(r) && view.rowOpen(r))view.fold(r);else if(r){for(var i=currentIndex-1;i>=0;--i)if(view.navigation[i].depth<r.depth){currentIndex=i;break;}}}
                Keys.onPressed:function(e){if(e.key===Qt.Key_Home){currentIndex=0;e.accepted=true;}else if(e.key===Qt.Key_End){currentIndex=count-1;e.accepted=true;}}
                onCurrentIndexChanged:if(!view.syncingNavigation)positionViewAtIndex(currentIndex,ListView.Contain)
                delegate:ItemDelegate {
                    required property var rowData
                    required property int index
                    property var modelData:rowData
                    objectName:'unifiedRow:'+index;width:nav.contentWidth;height:21;padding:0
                    Keys.onSpacePressed:view.fold(modelData)
                    Keys.onReturnPressed:view.activate(modelData)
                    highlighted:modelData.kind==='node'?modelData.record.id===view.detail.id && modelData.node.path===view.selectedPath:modelData.kind==='record' && modelData.record.id===view.detail.id && view.selectedPath==='section'
                    background:Rectangle {color:'white'}
                    contentItem:Row {
                        spacing:3
                        Branch {depth:modelData.depth+1;width:(modelData.depth+1)*16;height:21;expandable:view.expandable(modelData);expanded:view.rowOpen(modelData)
                            MouseArea {anchors.right:parent.right;width:14;height:parent.height;enabled:parent.expandable;onClicked:{nav.currentIndex=index;nav.forceActiveFocus();view.fold(modelData);}}
                        }
                        Icon {anchors.verticalCenter:parent.verticalCenter;kind:modelData.icon || (modelData.kind==='family'?(modelData.name==='Programs'?'programs':modelData.name==='PSI Packets'?'psi':modelData.name):modelData.program?'program':modelData.kind==='record'?modelData.record.name:modelData.node.label.toLowerCase().indexOf('descriptor')>=0?'descriptor':'field')}
                        Rectangle {width:Math.min(nav.contentWidth-(modelData.depth+1)*16-26,navText.implicitWidth+4);height:19;anchors.verticalCenter:parent.verticalCenter;color:'white';border.width:parent.parent.highlighted?1:0;border.color:'#c00000'
                            TextLabel {id:navText;anchors.fill:parent;anchors.leftMargin:2;verticalAlignment:Text.AlignVCenter;text:modelData.label;font.pixelSize:13;elide:Text.ElideRight}
                        }
                    }
                    onClicked:{nav.currentIndex=index;nav.forceActiveFocus();view.activate(modelData);}
                    onDoubleClicked:view.fold(modelData)
                    ToolTip {visible:parent.hovered;text:modelData.label+(modelData.hint?'\n'+modelData.hint:'')}
                    Accessible.name:modelData.label
                }
            }
            TextLabel {visible:!!view.organizationStatus;text:view.organizationStatus;Layout.fillWidth:true;font.pixelSize:11;elide:Text.ElideRight}
            RowLayout {Layout.fillWidth:true;spacing:2
                ClassicButton {objectName:'unifiedBack';text:'Back';implicitHeight:23;enabled:view.history.length>0 && host.backendReady;onClicked:view.back()}
                ComboBox {Layout.fillWidth:true;implicitHeight:23;font.pixelSize:11;model:host.tableFamilies;currentIndex:Math.max(0,host.tableFamilies.indexOf(view.family));onActivated:view.changeFilter(currentText,view.query)}
                ClassicButton {text:'Find';implicitHeight:23;onClicked:view.focusSearch()}
            }
            TextField {id:search;objectName:'unifiedSearch';visible:view.searchVisible;Layout.fillWidth:true;implicitHeight:24;color:'black';placeholderTextColor:'#606060';placeholderText:'Find program / LCN / TP / PID';text:view.query;onTextEdited:view.changeFilter(view.family,text);selectByMouse:true}
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
                Layout.fillWidth:true;implicitHeight:23;color:classicFace;border.color:'#a0a0a0';clip:true
                Row {x:-fieldList.contentX;width:view.fieldTableWidth;height:parent.height
                    Repeater {model:['Field','Bits','Value','Comment']
                        delegate:Rectangle {
                            required property string modelData
                            required property int index
                            objectName:'siColumnHeader:'+index
                            width:view.fieldColumnWidth(index);height:23;color:'transparent';border.color:'#b0b0b0'
                            TextLabel {anchors.fill:parent;anchors.leftMargin:6;verticalAlignment:Text.AlignVCenter;text:modelData;elide:Text.ElideRight}
                            MouseArea {
                                objectName:'siColumnGrip:'+index
                                anchors.right:parent.right;anchors.top:parent.top;anchors.bottom:parent.bottom;width:7;cursorShape:Qt.SplitHCursor;preventStealing:true
                                property real startX:0
                                property real startWidth:0
                                onPressed:function(mouse){startX=mapToItem(view,mouse.x,mouse.y).x;startWidth=view.fieldColumnWidth(index);}
                                onPositionChanged:function(mouse){if(pressed)view.resizeFieldColumn(index,startWidth+mapToItem(view,mouse.x,mouse.y).x-startX);}
                                onDoubleClicked:view.fitFieldColumn(index)
                            }
                        }
                    }
                }
            }
            ListView {
                id:fieldList;objectName:'unifiedFields';Layout.fillWidth:true;Layout.fillHeight:true;Layout.minimumHeight:120
                clip:true;model:view.fieldRows;reuseItems:true;activeFocusOnTab:true;enabled:!view.inspectionPending
                contentWidth:view.fieldTableWidth;flickableDirection:Flickable.AutoFlickDirection
                ScrollBar.horizontal:ScrollBar{policy:ScrollBar.AsNeeded}
                ScrollBar.vertical:ScrollBar{}
                Keys.onReturnPressed:view.selectField(currentIndex)
                Keys.onSpacePressed:view.selectField(currentIndex)
                Keys.onUpPressed:{view.focusField(Math.max(0,view.selectedFieldIndex-1));positionViewAtIndex(currentIndex,ListView.Contain);}
                Keys.onDownPressed:{view.focusField(Math.min(count-1,view.selectedFieldIndex+1));positionViewAtIndex(currentIndex,ListView.Contain);}
                Keys.onPressed:function(e){if(e.key===Qt.Key_Home){view.focusField(0);positionViewAtBeginning();e.accepted=true;}else if(e.key===Qt.Key_End){view.focusField(count-1);positionViewAtEnd();e.accepted=true;}}
                delegate:ItemDelegate {
                    required property var modelData
                    required property int index
                    objectName:'siField:'+index;width:view.fieldTableWidth;height:20;padding:0
                    Keys.onSpacePressed:view.selectField(index)
                    Keys.onReturnPressed:view.selectField(index)
                    highlighted:index===view.selectedFieldIndex
                    background:Rectangle {color:parent.highlighted?view.classicSelection:view.classicPaper;Rectangle {anchors.bottom:parent.bottom;width:parent.width;height:1;color:'#ededed'}}
                    onClicked:{fieldList.forceActiveFocus();view.focusField(index);}
                    onDoubleClicked:if(modelData.groupPath)view.selectField(index)
                    Accessible.name:modelData.name+', '+(modelData.bit_length===undefined?'bit range unknown':modelData.bit_length+' bits')+', '+modelData.value
                    contentItem:Row {
                        Item {width:view.fieldColumnWidth(0);height:20;clip:true
                            Row {anchors.fill:parent;spacing:3
                                Branch {depth:modelData.depth || 0;width:12+(modelData.depth || 0)*16;height:20;expandable:!!modelData.groupPath;expanded:!view.fieldClosed[modelData.groupPath]
                                    MouseArea {anchors.right:parent.right;width:12;height:parent.height;enabled:parent.expandable;onClicked:{fieldList.forceActiveFocus();view.selectField(index);}}
                                }
                                Icon {anchors.verticalCenter:parent.verticalCenter;kind:'field'}
                                TextLabel {height:20;verticalAlignment:Text.AlignVCenter;text:modelData.name}
                            }
                        }
                        TextLabel {width:view.fieldColumnWidth(1);height:20;leftPadding:6;verticalAlignment:Text.AlignVCenter;text:modelData.groupPath?'':modelData.bit_length===undefined?'—':String(modelData.bit_length)}
                        TextLabel {width:view.fieldColumnWidth(2);height:20;leftPadding:6;verticalAlignment:Text.AlignVCenter;text:view.fieldValue(modelData.value);color:view.classicValue;elide:Text.ElideRight}
                        TextLabel {width:view.fieldColumnWidth(3);height:20;leftPadding:6;verticalAlignment:Text.AlignVCenter;text:modelData.help || '';elide:Text.ElideRight}
                    }
                    ToolTip {visible:parent.hovered;text:modelData.name+'  '+modelData.value+(modelData.help?'  '+modelData.help:'')}
                }
                Rectangle {z:-1;anchors.fill:parent;color:'white'}
                Item {
                    parent:fieldList;anchors.fill:parent;clip:true;z:2
                    Repeater {model:4
                        Rectangle {
                            required property int index
                            objectName:'siColumnLine:'+index
                            x:{var edge=0;for(var i=0;i<=index;i++)edge+=view.fieldColumnWidth(i);return edge-fieldList.contentX-1;}
                            width:1;height:parent.height;color:'#b0b0b0'
                        }
                    }
                }
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
                            id:packetRows;objectName:'siPacketRows';width:packetBytes.contentWidth;height:packetBytes.height;clip:true;model:Math.ceil(view.packetRaw.length/20);reuseItems:true
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
                text:view.selectedField && view.selectedField.bit_offset!==undefined ? view.selectedField.name+' : '+view.selectedField.bit_length+' bits  (bit '+view.selectedField.bit_offset+'–'+(view.selectedField.bit_offset+view.selectedField.bit_length-1)+')' : view.selectedField?'Exact bit range unavailable':view.selectedPath!=='section' && !view.activeRange?'Exact byte range unavailable for this decoded node':detail.id?'PID '+Model.inspector.hex(detail.pid)+'   '+detail.bytes+' bytes   CRC '+((detail.crc || {}).status || 'unavailable'):'Ready'
            }
        }
    }
}
