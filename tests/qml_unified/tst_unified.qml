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
        function inspect(id,sid) {detail=captures.find(function(d){return d.id===id;}) || {};}
    }
    UnifiedInspector {id:inspector;anchors.fill:parent;host:host}
    TestCase {
        name:'UnifiedInspectorRealEngineEvidence'
        when:windowShown
        function initTestCase() {
            var xhr=new XMLHttpRequest();xhr.open('GET',Qt.resolvedUrl('../../artifacts/unified-inspector/engine-evidence.json'),false);xhr.send();
            var evidence=JSON.parse(xhr.responseText);host.captures=evidence.details;host.analysisState=evidence.state;inspector.organization=evidence.topology;
            host.inspect(evidence.details[0].id,-1);
        }
        function init() {
            inspector.pidFilter=-1;inspector.family='All tables';inspector.query='';
            inspector.navigationOrigin={};inspector.selectionFilter={};inspector.pendingRestore=null;inspector.history=[];
            inspector.hexFraction=0.40;inspector.openFamilies={};inspector.closed={};inspector.fieldClosed={};inspector.limits={};host.coreInspecting=false;
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
