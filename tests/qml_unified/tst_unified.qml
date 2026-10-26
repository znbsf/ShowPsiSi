import QtQuick
import QtQuick.Controls
import QtTest
import "../../ui/qt"

Item {
    width:1280;height:800
    QtObject {
        id:host
        property var analysisState: ({})
        property var detail: ({})
        property var captures: []
        property bool backendReady:true
        property bool coreInspecting:false
        property bool deferInspection:false
        property var tableFamilies:['All tables','PAT','PMT','BAT','TDT','TOT']
        property color ink:'#202733'
        property color muted:'#566171'
        property color blue:'#155fbe'
        property color panel:'#ffffff'
        property color surface:'#f5f6f8'
        property color dividerColor:'#cdd2da'
        property color selectionSurface:'#dceafd'
        property color hoverSurface:'#e5e9ef'
        property color removedColor:'#b42929'
        function inspect(id,sid) {if(deferInspection){coreInspecting=true;detail={};return;}detail=captures.find(function(d){return d.id===id;}) || {};}
    }
    UnifiedInspector {id:inspector;anchors.fill:parent;host:host}
    TestCase {
        name:'UnifiedInspectorRealEngineEvidence'
        property var referenceTables:[]
        when:windowShown
        function initTestCase() {
            var xhr=new XMLHttpRequest();xhr.open('GET',Qt.resolvedUrl('../../artifacts/unified-inspector/engine-evidence.json'),false);xhr.send();
            var evidence=JSON.parse(xhr.responseText);
            var refs=new XMLHttpRequest();refs.open('GET',Qt.resolvedUrl('../../artifacts/unified-inspector/reference-trees.json'),false);refs.send();referenceTables=JSON.parse(refs.responseText);
            host.captures=evidence.details;host.analysisState=evidence.state;inspector.organization=evidence.topology;
            host.inspect(evidence.details[0].id,-1);
        }
        function init() {
            inspector.pidFilter=-1;inspector.family='All tables';inspector.query='';
            inspector.navigationOrigin={};inspector.selectionFilter={};inspector.pendingRestore=null;inspector.pendingNode=null;inspector.history=[];
            inspector.expandedRecords={};inspector.treeClosed={};inspector.treeLimits={};
            host.deferInspection=false;inspector.fieldColumnWidths=[-1,-1,-1,-1];inspector.hexFraction=0.40;inspector.openFamilies={};inspector.closed={};inspector.fieldClosed={};inspector.limits={};host.coreInspecting=false;
            inspector.selectRecord(inspector.findRecord('PAT'));inspector.history=[];
        }
        function test_numeric_pid_excludes_extension_collision() {
            inspector.query='0x0100';verify(inspector.records.length>=2);
            inspector.filterPid(0x100);compare(inspector.records.length,1);
            compare(inspector.records[0].pid,0x100);
            verify(host.captures.some(function(record){return record.pid===0x102 && record.extension===0x100;}));
        }
        function test_navigation_and_fields() {
            verify(inspector.navigation.some(function(n){return n.kind==='family' && n.name==='PAT';}));
            verify(inspector.navigation.some(function(n){return n.kind==='node';}));
            var original=host.detail.id;
            inspector.selectRecord(inspector.findRecord('PMT'));
            compare(host.detail.name,'PMT');
            verify(inspector.nodes.some(function(n){return n.label.indexOf('descriptor')>=0;}));
            inspector.back();compare(host.detail.id,original);
            inspector.family='TDT';compare(inspector.records.length,2);
            inspector.selectRecord(inspector.records[0]);
            verify(!inspector.fieldRows.some(function(r){return r.name==='version_number';}));
            inspector.family='All tables';
        }
        function test_bat_hex_and_keyboard() {
            inspector.selectRecord(inspector.findRecord('BAT'));
            inspector.hexOpen=true;
            wait(100);
            var hex=findChild(inspector,'unifiedHexBytes');verify(hex.visible);verify(hex.text.indexOf('0000')===0);
            inspector.focusNavigation();keyClick(Qt.Key_End);
            var nav=findChild(inspector,'unifiedTree');compare(nav.currentIndex,nav.count-1);
            keyClick(Qt.Key_Home);compare(nav.currentIndex,0);
            verify(findChild(inspector,'unifiedFields').width>400);
        }
        function test_pending_inspection_preserves_back_and_limits() {
            inspector.family='All tables';inspector.selectRecord(inspector.findRecord('PAT'));
            inspector.limits={'section/decoded':200};
            inspector.selectRecord(inspector.findRecord('BAT'));
            var before=inspector.history.length;
            host.coreInspecting=true;inspector.back();
            compare(inspector.history.length,before);compare(host.detail.name,'BAT');
            host.coreInspecting=false;inspector.back();
            compare(host.detail.name,'PAT');compare(inspector.limits['section/decoded'],200);
            inspector.selectRecord(null);compare(host.detail.name,'PAT');
        }
        function test_filter_back_restores_visible_context() {
            inspector.family='All tables';inspector.query='';inspector.navigationOrigin={};inspector.history=[];
            inspector.selectRecord(inspector.findRecord('PAT'));
            inspector.selectedPath='section/decoded';inspector.limits={'section/decoded':200};
            var previous=host.detail.id;
            inspector.changeFilter('All tables','PID 0x0100');
            compare(inspector.records.length,1);
            inspector.selectRecord(inspector.records[0]);compare(host.detail.name,'PMT');
            inspector.back();tryCompare(inspector,'query','');
            compare(host.detail.id,previous);compare(inspector.family,'All tables');
            compare(inspector.selectedPath,'section/decoded');compare(inspector.limits['section/decoded'],200);
            verify(inspector.records.some(function(record){return record.id===previous;}));
            tryVerify(function(){return inspector.pendingRestore===null;});
            inspector.changeFilter('BAT','');inspector.selectRecord(inspector.records[0]);
            inspector.back();compare(inspector.family,'All tables');compare(host.detail.id,previous);
        }
        function test_si_field_hex_bidirectional() {
            inspector.selectRecord(inspector.findRecord('PMT'));inspector.selectedPath='section';
            var list=findChild(inspector,'unifiedFields');
            var index=inspector.fieldRows.findIndex(function(f){return f.name==='version_number';});
            verify(index>=0);list.positionViewAtIndex(index,ListView.Contain);wait(100);
            mouseClick(list.itemAtIndex(index));
            compare(inspector.selectedField.name,'version_number');compare(inspector.selectedField.bit_length,5);
            compare(inspector.activeRange.offset,5);compare(inspector.activeRange.length,1);
            verify(inspector.byteSelected(5));verify(!inspector.byteSelected(4));
            // Clicking byte 3 resolves the 16-bit extension and marks both bytes.
            var hex=findChild(inspector,'siHexRows');hex.positionViewAtBeginning();wait(100);
            var cell=findChild(hex.itemAtIndex(0),'siByte:3');verify(cell);mouseClick(cell);
            compare(inspector.selectedField.name,'table_id_extension');compare(inspector.activeRange.length,2);
            verify(inspector.byteSelected(3));verify(inspector.byteSelected(4));
            // A shared byte deterministically selects the smallest matching bit field.
            inspector.selectByte(5);compare(inspector.selectedField.name,'current_next_indicator');
            compare(inspector.selectedField.bit_length,1);
        }
        function test_si_descriptor_and_unknown_range() {
            inspector.selectRecord(inspector.findRecord('PMT'));
            inspector.selectByte(19);compare(inspector.selectedField.name,'component_tag');
            inspector.closed={'section':true};inspector.selectByte(22);
            compare(inspector.selectedField.name,'payload');compare(inspector.selectedField.value,'0x42 [66]');
            verify(inspector.selectedPath.indexOf('/descriptor/20')>=0);
            verify(!inspector.closed.section);compare(inspector.activeRange.offset,22);
            inspector.selectedPath='section/decoded';inspector.selectField(inspector.fieldRows.findIndex(function(f){return f.nodePath==='section/decoded' && !f.groupPath && f.bit_offset===undefined;}));
            compare(inspector.activeRange,null);
            verify(findChild(inspector,'siRange').text.indexOf('unavailable')>=0);
        }
        function test_si_selection_back_and_keyboard() {
            inspector.selectRecord(inspector.findRecord('PMT'));inspector.selectByte(3);
            var path=inspector.selectedPath,index=inspector.selectedFieldIndex;
            inspector.selectRecord(inspector.findRecord('BAT'));
            compare(inspector.selectedFieldIndex,-1);inspector.back();wait(100);
            compare(inspector.selectedPath,path);compare(inspector.selectedFieldIndex,index);
            var list=findChild(inspector,'unifiedFields');list.forceActiveFocus();keyClick(Qt.Key_Down);
            compare(inspector.selectedFieldIndex,index+1);
            inspector.selectRecord(inspector.findRecord('TDT'));
            compare(inspector.selectedFieldIndex,-1);compare(inspector.activeRange,null);
        }
        function test_back_restores_field_identity_columns_and_horizontal_scroll() {
            inspector.selectRecord(inspector.findRecord('PMT'));inspector.selectByte(19);
            var field=inspector.selectedField.name;
            inspector.resizeFieldColumn(0,800);wait(50);
            var list=findChild(inspector,'unifiedFields');list.contentX=30;
            var before=inspector.captureContext();verify(before.fieldX>0);
            inspector.selectRecord(inspector.findRecord('BAT'));inspector.resizeFieldColumn(0,400);
            inspector.back();wait(100);
            compare(inspector.selectedField.name,field);compare(inspector.fieldColumnWidths[0],800);
            compare(list.contentX,before.fieldX);
        }
        function test_si_tree_table_expand_and_focus() {
            inspector.selectRecord(inspector.findRecord('PMT'));
            var index=inspector.fieldRows.findIndex(function(f){return f.groupPath && f.groupPath.indexOf('section/stream/')===0;});
            verify(index>=0);var path=inspector.fieldRows[index].groupPath;
            var before=inspector.fieldRows.length;
            inspector.selectField(index);verify(inspector.fieldClosed[path]);verify(inspector.fieldRows.length<before);
            inspector.selectField(index);compare(inspector.fieldRows.length,before);
            inspector.focusNavigation();inspector.nextRegion();verify(findChild(inspector,'unifiedFields').activeFocus);
            inspector.hexOpen=true;inspector.nextRegion();verify(findChild(inspector,'siHexRows').activeFocus);
            inspector.nextRegion();verify(findChild(inspector,'unifiedTree').activeFocus);
        }
        function test_classic_palette_icons_and_packet_link() {
            inspector.selectRecord(inspector.findRecord('PMT'));inspector.selectByte(3);
            compare(String(inspector.classicPaper),'#ffffff');compare(String(inspector.classicSelection),'#ffff00');compare(String(inspector.classicValue),'#ff0000');
            compare(inspector.sourcePacket.status,'available');compare(inspector.packetRaw.length,376);
            verify(inspector.packetSelected(inspector.sourcePacket.section_offset+3));
            inspector.packetClick(inspector.sourcePacket.section_offset+5);
            compare(inspector.selectedField.name,'current_next_indicator');
            inspector.packetClick(0);compare(inspector.selectedFieldIndex,-1);
            inspector.selectByte(3);wait(100);
            var field=findChild(inspector,'unifiedFields').itemAtIndex(inspector.selectedFieldIndex);
            compare(String(field.background.color),'#ffff00');
            verify(findChild(inspector,'siPacketRows').width>300);
            verify(findChild(inspector,'siPacketRows').height>150);
            verify(inspector.navigation.some(function(r){return r.name==='Programs';}));
            verify(inspector.navigation.some(function(r){return r.name==='PSI Packets';}));
            var divider=findChild(inspector,'siPaneDivider');var before=inspector.hexFraction;
            mouseDrag(divider,divider.width/2,2,0,-40);verify(inspector.hexFraction>before);
            inspector.hexFraction=before;
        }
        function test_named_network_tp_lcn_navigation() {
            inspector.family='All tables';inspector.query='';inspector.openFamilies={};
            var network=inspector.navigation.find(function(r){return r.label.indexOf('Fixture Network')>=0;});verify(!!network);
            var tp=inspector.navigation.find(function(r){return r.label.indexOf('TSID 0x1001 ONID 0x2001')>=0;});verify(!!tp);
            verify(tp.label.indexOf('11727.5 MHz')>=0);
            var service=inspector.navigation.find(function(r){return r.label.indexOf('LCN 7  News One')>=0;});verify(!!service);
            compare(service.record.pid,256);inspector.activate(service);compare(host.detail.name,'PMT');
            inspector.selectByte(3);verify(inspector.activeRange!==null);
            inspector.fold(tp);verify(!inspector.navigation.some(function(r){return r.label.indexOf('News One')>=0;}));
            inspector.fold(tp);verify(inspector.navigation.some(function(r){return r.label.indexOf('News One')>=0;}));
            inspector.changeFilter('All tables','News One');verify(inspector.navigation.some(function(r){return r.label.indexOf('News One')>=0;}));
            inspector.changeFilter('All tables','');
        }
        function test_field_keyboard_navigation_does_not_fold_groups() {
            inspector.selectRecord(inspector.findRecord('PMT'));inspector.fieldClosed={};
            var fields=findChild(inspector,'unifiedFields');fields.forceActiveFocus();
            var count=inspector.fieldRows.length;verify(count>7);
            keyClick(Qt.Key_Home);compare(inspector.fieldRows.length,count);compare(inspector.selectedFieldIndex,0);
            keyClick(Qt.Key_Down);compare(inspector.selectedField.name,'table_id');
            keyClick(Qt.Key_Home);keyClick(Qt.Key_Return);compare(inspector.fieldRows.length,1);
            keyClick(Qt.Key_Down);compare(inspector.fieldRows.length,1);
            keyClick(Qt.Key_Space);compare(inspector.fieldRows.length,count);
            for(var i=0;i<6;i++)keyClick(Qt.Key_Down);
            compare(inspector.selectedField.name,'table_id_extension');compare(inspector.activeRange.offset,3);
        }
        function test_pending_detail_keeps_presentation_and_clears_on_failure() {
            inspector.selectRecord(inspector.findRecord('PMT'));wait(30);
            var old=inspector.detail.id,count=inspector.fieldRows.length,hex=inspector.rawHex;
            host.deferInspection=true;
            inspector.selectRecord(inspector.findRecord('BAT'));wait(50);
            compare(host.detail.id,undefined);compare(inspector.detail.id,old);
            compare(inspector.fieldRows.length,count);compare(inspector.rawHex,hex);
            verify(!findChild(inspector,'unifiedFields').enabled);
            host.detail=host.captures.find(function(d){return d.name==='BAT';});host.coreInspecting=false;
            tryCompare(inspector,'detail',host.detail);verify(inspector.detail.name==='BAT');
            inspector.selectRecord(inspector.findRecord('PAT'));host.coreInspecting=false;
            tryVerify(function(){return !inspector.detail.id;});compare(inspector.fieldRows.length,0);
            host.deferInspection=false;
        }
        function test_scrolled_tree_click_keeps_row_and_delegate() {
            // Bounded synthetic repetition of real engine records stresses a long tree.
            var originalState=host.analysisState;
            try {
                var state=Object.assign({},originalState),pat=inspector.findRecord('PAT'),rows=[];
                for(var i=0;i<80;i++)rows.push(Object.assign({},pat,{id:'scroll:'+i,extension:i}));
                state.tables=rows;host.analysisState=state;inspector.family='PAT';inspector.openFamilies={'PAT':true};wait(50);
                var nav=findChild(inspector,'unifiedTree');
                var index=inspector.navigation.findIndex(function(r){return r.key==='scroll:73';});verify(index>=0);
                nav.positionViewAtIndex(index,ListView.Center);wait(50);
                var clicked=nav.itemAtIndex(index);verify(clicked,'visible index '+index+' count '+nav.count+' scroll '+nav.contentY);var y=clicked.y-nav.contentY;
                host.deferInspection=true;mouseClick(clicked,Math.min(clicked.width/2,nav.width-20),10);wait(50);
                compare(nav.itemAtIndex(index),clicked);verify(Math.abs(clicked.y-nav.contentY-y)<1);
                var incoming=Object.assign({},host.captures[0],{id:'scroll:73'});host.detail=incoming;host.coreInspecting=false;wait(50);
                index=inspector.navigation.findIndex(function(r){return r.key==='scroll:73';});
                compare(nav.itemAtIndex(index),clicked);verify(Math.abs(clicked.y-nav.contentY-y)<1,'Clicked row must stay at its viewport position');
                compare(inspector.navigation[nav.currentIndex].key,'scroll:73');
            } finally {host.deferInspection=false;host.coreInspecting=false;host.analysisState=originalState;}
        }
        function test_drag_field_columns_and_horizontal_scroll() {
            inspector.selectRecord(inspector.findRecord('PMT'));wait(50);
            var list=findChild(inspector,'unifiedFields'),grip=findChild(inspector,'siColumnGrip:0');verify(grip);
            var before=inspector.fieldColumnWidth(0);
            mouseDrag(grip,3,10,100,0);verify(inspector.fieldColumnWidth(0)>before+80);
            compare(findChild(inspector,'siColumnHeader:0').width,inspector.fieldColumnWidth(0));
            var width=inspector.fieldColumnWidth(0);inspector.selectRecord(inspector.findRecord('BAT'));compare(inspector.fieldColumnWidth(0),width);
            verify(list.contentWidth>list.width);list.contentX=60;wait(30);
            verify(findChild(inspector,'siColumnHeader:0').mapToItem(list,0,0).x<0);
            list.contentX=0;var valueGrip=findChild(inspector,'siColumnGrip:2');
            mouseDoubleClickSequence(valueGrip,3,10);verify(inspector.fieldColumnWidths[2]>0);
            inspector.resizeFieldColumn(1,-100);compare(inspector.fieldColumnWidth(1),48);
            list.contentX=0;
        }
        function test_left_tree_wire_loops_and_cached_descriptor_selection() {
            var pmt=inspector.findRecord('PMT'),nit=inspector.findRecord('NIT');
            inspector.selectRecord(pmt);wait(30);
            var stream=inspector.navigation.find(function(r){return r.kind==='node' && r.record.id===pmt.id && r.node.path==='section/stream/12';});verify(stream);
            verify(stream.label.indexOf('PID=0x0101')>=0);verify(stream.label.indexOf('stream_type = 0x1B')>=0);
            var descriptor=inspector.navigation.find(function(r){return r.kind==='node' && r.record.id===pmt.id && r.node.descriptor_offset===17;});verify(descriptor);
            compare(descriptor.depth,stream.depth+1);verify(descriptor.label.indexOf('stream_identifier_descriptor TAG(0x52)')>=0);
            verify(!inspector.navigation.some(function(r){return r.kind==='node' && /\/decoded|section\/descriptors/.test(r.node.path);}));
            inspector.selectRecord(nit);wait(30);
            verify(inspector.navigation.some(function(r){return r.key===descriptor.key;}),'Expanded PMT must survive selection of NIT');
            var transport=inspector.navigation.find(function(r){return r.kind==='node' && r.record.id===nit.id && r.label==='ONID=0x2001 TSID = 0x1001';});verify(transport);
            var networkDescriptor=inspector.navigation.find(function(r){return r.kind==='node' && r.record.id===nit.id && r.node.descriptor_offset===10;});verify(networkDescriptor);
            var delivery=inspector.navigation.find(function(r){return r.kind==='node' && r.record.id===nit.id && r.node.descriptor_offset===35;});verify(delivery);
            compare(networkDescriptor.depth,transport.depth);compare(delivery.depth,transport.depth+1);
            inspector.activate(transport);compare(inspector.selectedPath,transport.node.path);verify(inspector.activeRange.offset===29 && inspector.activeRange.length===31);
            compare(inspector.fieldRows[inspector.selectedFieldIndex].groupPath,transport.node.path);
            var oldWidth=inspector.fieldColumnWidth(0);inspector.resizeFieldColumn(0,oldWidth+40);
            host.deferInspection=true;inspector.activate(descriptor);compare(inspector.detail.id,nit.id);
            host.detail=host.captures.find(function(d){return d.id===pmt.id;});host.coreInspecting=false;
            tryCompare(inspector,'selectedPath',descriptor.node.path);
            compare(inspector.activeRange.offset,17);compare(inspector.activeRange.length,3);
            compare(inspector.fieldRows[inspector.selectedFieldIndex].groupPath,descriptor.node.path);
            compare(inspector.fieldColumnWidth(0),oldWidth+40);
            verify(inspector.navigation.some(function(r){return r.key===delivery.key;}),'NIT must stay expanded after returning to PMT');
            host.deferInspection=false;
        }
        function test_left_tree_expand_controls_and_source_reset() {
            var pmt=inspector.findRecord('PMT');inspector.selectRecord(pmt);wait(30);
            var nav=findChild(inspector,'unifiedTree');
            verify(nav.contentWidth>nav.width,'Long SI labels must remain accessible by horizontal scrolling');nav.contentX=0;
            var stream=inspector.navigation.find(function(r){return r.kind==='node' && r.record.id===pmt.id && r.node.path==='section/stream/12';});verify(stream);
            var index=inspector.navigation.findIndex(function(r){return r.key===stream.key;});nav.positionViewAtIndex(index,ListView.Center);wait(30);
            var row=nav.itemAtIndex(index);verify(row);
            // Click the actual [+/-] box, not a helper that bypasses the delegate.
            mouseClick(row,(stream.depth+1)*16-5,10);wait(30);
            verify(!inspector.navigation.some(function(r){return r.kind==='node' && r.record.id===pmt.id && r.node.descriptor_offset===17;}));
            nav.forceActiveFocus();keyClick(Qt.Key_Right);wait(30);
            verify(inspector.navigation.some(function(r){return r.kind==='node' && r.record.id===pmt.id && r.node.descriptor_offset===17;}));
            var original=host.analysisState;
            host.analysisState=Object.assign({},original,{source:'another-source.ts',analysis_revision:'another'});compare(Object.keys(inspector.tableTrees).length,0);compare(Object.keys(inspector.expandedRecords).length,0);
            host.analysisState=original;host.detail={};host.inspect(pmt.id,-1);
        }
        function test_all_reference_table_trees_and_semantic_selection() {
            var original=host.analysisState,originalCaptures=host.captures,visited=0;
            try {
                for(var i=0;i<referenceTables.length;i++){
                    var sample=referenceTables[i],d=sample.detail;
                    host.analysisState=sample.state;host.detail={};host.captures=[d];host.inspect(d.id,-1);
                    inspector.family='All tables';inspector.selectRecord(sample.state.tables.find(function(r){return r.id===d.id;}));
                    var rows=inspector.navigation.filter(function(r){return r.kind==='node' && r.record.id===d.id;});verify(rows.length>0,sample.name);
                    if(!d.si_structure.children.length){
                        var expected=[];
                        function collect(n,path){expected.push({name:n.name,path:path});(n.children || []).forEach(function(child,index){collect(child,path+'/'+index);});}
                        if(d.native_table.children.length)d.native_table.children.forEach(function(n,index){collect(n,'section/decoded/'+index);});else collect(d.native_table,'section/decoded');
                        for(var j=0;j<expected.length;j++)verify(rows.some(function(r){return r.node.path===expected[j].path && r.node.semanticName===expected[j].name;}),sample.name+': '+expected[j].path);
                        var leaf=rows[rows.length-1];inspector.activate(leaf);
                        compare(inspector.selectedPath,leaf.node.path);compare(inspector.activeRange,null);
                        verify(inspector.selectedFieldIndex>=0,sample.name+' field row');
                        compare(inspector.fieldRows[inspector.selectedFieldIndex].groupPath,leaf.node.path);
                        verify(findChild(inspector,'siRange').text.indexOf('unavailable')>=0);
                        visited++;
                    }
                }
                verify(visited>30);
            } finally {host.captures=originalCaptures;host.analysisState=original;host.detail={};host.inspect(originalCaptures[0].id,-1);}
        }
        function test_mouse_expand_contract_for_left_and_right_trees() {
            inspector.selectRecord(inspector.findRecord('PMT'));wait(30);
            var nav=findChild(inspector,'unifiedTree');nav.contentX=0;
            function item(row){var index=inspector.navigation.findIndex(function(r){return r.key===row.key;});verify(index>=0);nav.positionViewAtIndex(index,ListView.Center);wait(30);var delegate=nav.itemAtIndex(index);verify(delegate);return delegate;}
            function textX(row){return (row.depth+1)*16+35;}
            var family=inspector.navigation.find(function(r){return r.kind==='family' && r.name==='PMT';});
            mouseClick(item(family),textX(family),10);verify(inspector.rowOpen(family),'Single click family text must not collapse');
            mouseDoubleClickSequence(item(family),textX(family),10);verify(!inspector.rowOpen(family),'Double click family text collapses');
            mouseClick(item(family),(family.depth+1)*16-5,10);verify(inspector.rowOpen(family),'Single click + expands');
            var record=inspector.navigation.find(function(r){return r.kind==='record' && !r.program && r.record.id===inspector.detail.id;});verify(record);
            inspector.fold(record);verify(!inspector.rowOpen(record));
            mouseClick(item(record),textX(record),10);verify(!inspector.rowOpen(record),'Single click record text must not expand');
            mouseDoubleClickSequence(item(record),textX(record),10);verify(inspector.rowOpen(record));
            var stream=inspector.navigation.find(function(r){return r.kind==='node' && r.record.id===inspector.detail.id && r.node.path==='section/stream/12';});verify(stream);
            mouseClick(item(stream),textX(stream),10);verify(inspector.rowOpen(stream));
            mouseDoubleClickSequence(item(stream),textX(stream),10);verify(!inspector.rowOpen(stream));
            mouseClick(item(stream),(stream.depth+1)*16-5,10);verify(inspector.rowOpen(stream));
            var fields=findChild(inspector,'unifiedFields');fields.contentX=0;fields.positionViewAtBeginning();wait(30);
            var count=inspector.fieldRows.length,rootRow=fields.itemAtIndex(0);verify(rootRow);
            mouseClick(rootRow,80,10);compare(inspector.fieldRows.length,count,'Single click field group text only selects');
            mouseDoubleClickSequence(rootRow,80,10);compare(inspector.fieldRows.length,1,'Double click field group collapses');
            wait(30);mouseClick(fields.itemAtIndex(0),7,10);compare(inspector.fieldRows.length,count,'Single click field + expands');
        }
        function test_uncached_record_double_click_survives_pending_inspect() {
            var pmt=inspector.findRecord('PMT'),trees=Object.assign({},inspector.tableTrees);delete trees[pmt.id];inspector.tableTrees=trees;
            inspector.openFamilies={'PAT':true,'PMT':true};inspector.expandedRecords={};
            var nav=findChild(inspector,'unifiedTree'),index=inspector.navigation.findIndex(function(r){return r.kind==='record' && r.key===pmt.id;});verify(index>=0);
            nav.contentX=0;nav.positionViewAtIndex(index,ListView.Center);wait(30);
            var row=nav.itemAtIndex(index);verify(row);host.deferInspection=true;
            mouseDoubleClickSequence(row,100,10);verify(host.coreInspecting);verify(inspector.expandedRecords[pmt.id]);
            host.detail=host.captures.find(function(d){return d.id===pmt.id;});host.coreInspecting=false;
            tryVerify(function(){return inspector.navigation.some(function(r){return r.kind==='node' && r.record.id===pmt.id && r.node.path==='section/stream/12';});});
            host.deferInspection=false;
        }
        function test_field_group_fold_preserves_scrolled_viewport() {
            inspector.selectRecord(inspector.findRecord('PMT'));wait(40);
            var fields=findChild(inspector,'unifiedFields');
            var index=inspector.fieldRows.findIndex(function(r){return r.groupPath && r.groupPath.indexOf('/descriptor/')>=0;});
            verify(index>0);fields.positionViewAtIndex(index,ListView.Beginning);wait(30);
            var before=fields.contentY;verify(before>0);
            inspector.selectField(index);wait(30);
            var expected=Math.max(fields.originY,Math.min(before,fields.originY+Math.max(0,fields.contentHeight-fields.height)));
            fuzzyCompare(fields.contentY,expected,1);
            inspector.selectField(index);wait(30);fuzzyCompare(fields.contentY,expected,1);
        }
        function test_field_grid_tracks_header_resize_and_scroll() {
            inspector.selectRecord(inspector.findRecord('PMT'));wait(30);
            var fields=findChild(inspector,'unifiedFields');
            function aligned(){
                for(var i=0;i<4;i++){
                    var line=findChild(inspector,'siColumnLine:'+i),header=findChild(inspector,'siColumnHeader:'+i);
                    verify(line);compare(line.width,1);compare(line.height,fields.height);
                    verify(Math.abs(line.mapToItem(fields,0,0).x-(header.mapToItem(fields,header.width,0).x-1))<1,'column '+i+' alignment');
                    compare(line.mapToItem(fields,0,0).y,0);compare(String(line.color),'#b0b0b0');
                }
            }
            aligned();inspector.resizeFieldColumn(0,inspector.fieldColumnWidth(0)+120);fields.contentX=70;wait(30);aligned();
            fields.positionViewAtEnd();wait(30);aligned();fields.contentX=0;
        }
        function test_capture_review_scenes() {
            inspector.family='All tables';inspector.query='';
            ['PAT','PMT','BAT','TDT','TOT'].forEach(function(name){
                inspector.selectRecord(inspector.findRecord(name));
                inspector.selectedPath='section';
                if(name==='PMT')inspector.selectByte(3);
                inspector.hexOpen=true;
                wait(150);
                var path=Qt.resolvedUrl('../../artifacts/unified-inspector/'+name+'-review2.png').toString().replace(/^file:\/\/\//,Qt.platform.os==='windows'?'':'/');
                path=decodeURIComponent(path);
                var done=false,saved=false;
                verify(inspector.grabToImage(function(result){saved=result.saveToFile(path);done=true;}));
                tryVerify(function(){return done;},5000);
                verify(saved,'Native whole-item screenshot must be saved');
            });
        }
    }
}
