import QtQuick
import QtQuick.Controls
import QtTest
import "../../ui/qt"
Item {
    width:1280;height:800
    QtObject {
        id:host
        property var analysisState: ({})
        property bool lightTheme:false
        property bool transportQueryReady:true
        property color ink:lightTheme?"#202733":"#dce1e9"
        property color muted:lightTheme?"#566171":"#abb4c2"
        property color panel:lightTheme?"#ffffff":"#181a1e"
        property color surface:lightTheme?"#f5f6f8":"#121418"
        property color raised:lightTheme?"#eef0f3":"#2a2e37"
        property color controlBorder:lightTheme?"#6f7b8a":"#778496"
        property color blue:lightTheme?"#155fbe":"#78acfa"
        property color selectionSurface:lightTheme?"#dceafd":"#173951"
        property color hoverSurface:lightTheme?"#e5e9ef":"#333944"
        property color removedColor:"#ff8b98"
    }
    TransportSummary {
        id:summary;anchors.fill:parent;host:host
        onPageRequested:function(offset,sort,descending,errorsOnly) {
            requests.push({offset:offset,sort:sort,descending:descending,errorsOnly:errorsOnly});
        }
        onEntryActivated:function(entry){selectedEntry=entry;selectedPid=entry.pid;}
    }
    property var evidence: ({})
    property var requests:[]
    property int selectedPid:-1
    property var selectedEntry: null
    TestCase {
        name:"TransportSummaryRealEngineEvidence"
        when:windowShown
        function initTestCase() {
            var xhr=new XMLHttpRequest();xhr.open("GET",Qt.resolvedUrl("../../artifacts/transport-summary/engine-evidence.json"),false);xhr.send();
            evidence=JSON.parse(xhr.responseText);
            host.analysisState=evidence.state;
        }
        function init() {
            host.lightTheme=false;summary.parent.width=1280;host.analysisState=evidence.state;summary.returnContext=null;
            tryCompare(summary,"sourceIdentity",(evidence.state.source || "")+":"+evidence.state.analysis_revision+":true");
            host.transportQueryReady=true;summary.visible=true;
            findChild(summary,"transportSummaryTabs").currentIndex=0;
            summary.sort="pid";summary.descending=false;summary.loading=false;summary.page={};
            summary.request(0);summary.receive(evidence.summary);requests=[];
            tryCompare(findChild(summary,"transportSummary:totalPackets"),"text","32");
        }
        function activeCell(index,prefix) {
            var row=findChild(summary,"transportPidList").itemAtIndex(index);
            return row?findChild(row,prefix+index):null;
        }
        function columnsReady() {
            if(summary.errorPage)return true;
            var firstPackets=activeCell(0,"transportPackets:");
            var firstRate=activeCell(0,"transportRate:");
            if(!firstPackets || !firstRate)return false;
            var px=firstPackets.mapToItem(summary,0,0).x,rx=firstRate.mapToItem(summary,0,0).x;
            return [0,1,2].every(function(index){
                var packets=activeCell(index,"transportPackets:");
                var rate=activeCell(index,"transportRate:");
                return packets && rate && Math.abs(packets.mapToItem(summary,0,0).x-px)<=1 && Math.abs(rate.mapToItem(summary,0,0).x-rx)<=1 && rx>=px+packets.width+4;
            });
        }
        function capture(name) {
            verify(waitForPolish(summary));verify(waitForRendering(summary));tryVerify(columnsReady);
            var path=Qt.resolvedUrl("../../artifacts/transport-summary/"+name+".png").toString().replace(/^file:\/\/\//,Qt.platform.os==="windows"?"":"/");
            path=decodeURIComponent(path);
            var done=false,saved=false;
            verify(summary.grabToImage(function(image){saved=image.saveToFile(path);done=true;}));
            tryVerify(function(){return done;},5000);verify(saved);
        }
        function test_capture_summary() {capture("summary");}
        function test_capture_errors() {
            findChild(summary,"transportSummaryTabs").currentIndex=1;summary.receive(evidence.errors);
            capture("errors");
        }
        function test_compact_counter_layout() {
            summary.parent.width=720;
            tryVerify(function(){return findChild(summary,"transportPidList").height>120;});
            tryVerify(function(){return ["fileSize","totalPackets","bitrate","errors","duration","packetSize"].every(function(key){
                var field=findChild(summary,"transportSummary:"+key);
                var position=field.mapToItem(summary,0,0);
                return position.x>=0 && position.x+field.width<=summary.width;
            });},5000);
        }
        function test_page_two_return_preserves_context() {
            host.analysisState=evidence.pagingState;
            summary.loading=false;summary.request(100);summary.receive(evidence.pagingSecond);
            var list=findChild(summary,"transportPidList");
            tryVerify(function(){return list.contentHeight>list.height+100;});
            list.currentIndex=4;list.contentY=80;
            summary.activate(summary.visibleRows[4]);requests=[];
            summary.visible=false;summary.visible=true;
            compare(requests.length,0);compare(summary.page.offset,100);
            tryCompare(list,"currentIndex",4);tryCompare(list,"contentY",80);
        }
        function test_diagnostics_keep_exact_identity_and_aggregates_do_not_navigate() {
            host.analysisState=evidence.diagnosticState;
            findChild(summary,"transportSummaryTabs").currentIndex=1;
            summary.loading=false;summary.request(0);summary.receive(evidence.diagnosticErrors);
            var exact=summary.visibleRows.find(function(row){return !!row.id && !row.aggregate;});
            var aggregate=summary.visibleRows.find(function(row){return row.aggregate;});
            verify(!!exact);verify(!!aggregate);verify(aggregate.pid===null);
            summary.activate(exact);compare(selectedEntry.id,exact.id);
            selectedEntry=null;summary.activate(aggregate);compare(selectedEntry,null);
            verify(summary.error.indexOf("no exact")>=0);
        }
        function test_bad_sync_only_is_visible_without_fake_pid() {
            host.analysisState=evidence.syncState;
            findChild(summary,"transportSummaryTabs").currentIndex=1;
            summary.loading=false;summary.request(0);summary.receive(evidence.syncErrors);
            compare(summary.page.total,0);compare(summary.visibleRows.length,1);
            verify(summary.visibleRows[0].aggregate);verify(summary.visibleRows[0].pid===null);
            selectedEntry=null;summary.activate(summary.visibleRows[0]);compare(selectedEntry,null);
        }
        function test_columns_align_and_selected_row_is_readable() {
            var list=findChild(summary,"transportPidList");
            list.currentIndex=0;
            tryVerify(function(){return !!list.itemAtIndex(2);});
            verify(waitForPolish(summary));verify(waitForRendering(summary));
            var firstPackets=activeCell(0,"transportPackets:").mapToItem(summary,0,0).x;
            var firstRate=activeCell(0,"transportRate:").mapToItem(summary,0,0).x;
            tryVerify(function(){return [0,1,2].every(function(index){
                var packets=activeCell(index,"transportPackets:");
                var rate=activeCell(index,"transportRate:");
                return packets && rate && Math.abs(packets.mapToItem(summary,0,0).x-firstPackets)<=1 &&
                    Math.abs(rate.mapToItem(summary,0,0).x-firstRate)<=1;
            });});
            verify(Qt.colorEqual(list.itemAtIndex(0).background.color,host.selectionSurface));
            verify(!Qt.colorEqual(list.itemAtIndex(0).background.color,host.ink));
        }
        function test_light_theme_readable_selection() {
            host.lightTheme=true;
            var list=findChild(summary,"transportPidList");list.currentIndex=0;list.forceActiveFocus();
            verify(waitForPolish(summary));verify(waitForRendering(summary));
            verify(Qt.colorEqual(list.itemAtIndex(0).background.color,host.selectionSurface));
            verify(Qt.colorEqual(findChild(summary,"transportSummary:packetSize").color,host.ink));
            capture("summary-light");
        }
        function test_supplied_rate_duration_display() {
            host.analysisState=evidence.rateState;
            summary.loading=false;summary.request(0);summary.receive(evidence.ratePage);
            tryCompare(findChild(summary,"transportSummary:duration"),"text","00:00:00.032 (supplied rate)");
            tryCompare(findChild(summary,"transportSummary:bitrate"),"text","1,504,000 bps (supplied)");
        }
        function test_partial_observed_count_and_scope_are_visible() {
            host.analysisState=evidence.partialState;
            summary.loading=false;summary.request(0);summary.receive(evidence.partialPage);
            tryCompare(findChild(summary,"transportSummary:totalPackets"),"text","16");
            tryVerify(function(){return findChild(summary,"transportSummaryScope").text.indexOf("PARTIAL observed windows")>=0;});
            verify(evidence.partialState.packets>16);
        }
        function test_counters_and_pid_keyboard() {
            compare(findChild(summary,"transportSummary:totalPackets").text,"32");
            tryCompare(findChild(summary,"transportSummary:packetSize"),"text","188 bytes");
            compare(findChild(summary,"transportSummary:bitrate").text,"Unknown");
            compare(findChild(summary,"transportSummary:duration").text,"Unknown");
            compare(summary.visibleRows.length,3);
            var list=findChild(summary,"transportPidList");
            list.forceActiveFocus();keyClick(Qt.Key_Home);keyClick(Qt.Key_Return);
            compare(selectedPid,256);
            keyClick(Qt.Key_End);keyClick(Qt.Key_Return);compare(selectedPid,8191);
            summary.nextRegion();verify(findChild(summary,"transportSummaryTabs").currentItem.activeFocus);
            summary.nextRegion();verify(list.activeFocus);
        }
        function test_error_tab_real_transport_row() {
            var tabs=findChild(summary,"transportSummaryTabs");
            tabs.currentIndex=1;
            compare(requests.length,1);verify(requests[0].errorsOnly);
            verify(Qt.colorEqual(tabs.currentItem.background.color,host.selectionSurface));
            summary.receive(evidence.errors);
            compare(summary.visibleRows.length,1);
            compare(summary.visibleRows[0].pid,256);
            verify(summary.visibleRows[0].message.indexOf("TEI: 1")>=0);
            tryVerify(function(){return findChild(summary,"transportSummary:errors").text.indexOf("1 transport")>=0;});
        }
        function test_stale_revision_and_page_are_not_accepted() {
            summary.loading=false;summary.request(0);
            var stale=Object.assign({},evidence.summary,{analysis_revision:evidence.summary.analysis_revision+1});
            summary.receive(stale);verify(summary.loading);
            stale=Object.assign({},evidence.summary,{offset:100});
            summary.receive(stale);verify(summary.loading);
            summary.receive(evidence.summary);verify(!summary.loading);
        }
        function test_queries_wait_for_backend_ready() {
            host.transportQueryReady=false;summary.loading=false;summary.page={};requests=[];
            summary.request(0);compare(requests.length,0);
            host.transportQueryReady=true;compare(requests.length,1);
            summary.receive(evidence.summary);verify(!summary.loading);
        }
        function test_supplied_sort_and_empty_error_state() {
            summary.sort="packets";summary.descending=true;summary.loading=false;summary.request(0);
            summary.receive(evidence.sorted);compare(summary.page.sort,"packets");compare(summary.visibleRows[0].pid,256);
            host.analysisState=evidence.emptyState;
            tryCompare(summary,"sourceIdentity",evidence.emptyState.source+":"+evidence.emptyState.analysis_revision+":true");
            var tabs=findChild(summary,"transportSummaryTabs");tabs.currentIndex=1;
            summary.loading=false;summary.request(0);summary.receive(evidence.emptyErrors);
            compare(summary.visibleRows.length,0);verify(!summary.loading);
        }
    }
}
