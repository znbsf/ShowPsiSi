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
            var evidence=JSON.parse(xhr.responseText);host.captures=evidence.details;host.analysisState=evidence.state;
            host.inspect(evidence.details[0].id,-1);
        }
        function test_navigation_and_fields() {
            verify(inspector.navigation.length>host.captures.length);
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
        function test_capture_review_scenes() {
            inspector.family='All tables';inspector.query='';
            ['PAT','PMT','BAT','TDT','TOT'].forEach(function(name){
                inspector.selectRecord(inspector.findRecord(name));
                inspector.selectedPath=name==='PMT'?'section/descriptors/0/decoded':name==='PAT'?'section/decoded':'section';
                inspector.hexOpen=name==='BAT';
                wait(150);
                var path=Qt.resolvedUrl('../../artifacts/unified-inspector/'+name+'.png').toString().replace(/^file:\/\/\//,'');
                grabImage(inspector).save(path);
            });
        }
    }
}
