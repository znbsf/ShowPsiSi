import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Dialogs
import QtQml.Models
import "qrc:/shared/workbench.js" as Shared
import "../tauri/web/classic-model.js" as Classic

ApplicationWindow {
    id: win
    width: 1440
    height: 900
    minimumWidth: 1000
    minimumHeight: 680
    visible: true
    title: metadataMode ? "ShowPsiSi · DVB-I metadata inspector" : advancedMode ? "ShowPsiSi · Transport stream inspector" : "ShowPsiSi"+(analysisState.source?" - "+String(analysisState.source).split(/[\\/]/).pop():"")+(transportSummaryVisible?" - Summary":detail.id?" - "+detail.name+" PID "+hex(detail.pid):"")
    property string inputKind: "ts"
    property bool classicToolbarVisible:true
    property bool classicStatusVisible:true
    property bool classicTreeVisible:true
    property bool classicConfigurationVisible:false
    property var classicLocks: ({})
    property bool documentMode:false
    property bool transportSummaryVisible: false
    readonly property bool transportQueryReady: backendReady && !core.busy
    property bool advancedMode: core.env("SHOWPSISI_ADVANCED") === "1" || (!!core.env("SHOWPSISI_SCRIPT") && core.env("SHOWPSISI_SCRIPT") !== "unified-inspector")
    readonly property bool coreInspecting: core.inspecting
    readonly property bool metadataMode: inputKind === "dvbi"
    property bool lightTheme: (!metadataMode && !advancedMode) || core.env("SHOWPSISI_THEME") === "light" || (!core.env("SHOWPSISI_THEME") && core.loadTheme() === "light")
    property color surface: lightTheme ? "#f5f6f8" : "#181a1f"
    property color panel: lightTheme ? "#ffffff" : "#20232a"
    property color raised: lightTheme ? "#eef0f3" : "#2a2e37"
    property color dividerColor: lightTheme ? "#cdd2da" : "#414650"
    property color hoverSurface: lightTheme ? "#e5e9ef" : "#333944"
    property color selectionSurface: lightTheme ? "#dceafd" : "#173951"
    property color ink: lightTheme ? "#202733" : "#dce1e9"
    property color muted: lightTheme ? "#566171" : "#abb4c2"
    property color controlBorder: lightTheme ? "#6f7b8a" : "#778496"
    property color blue: lightTheme ? "#155fbe" : "#78acfa"
    property color warningColor: lightTheme ? "#805900" : "#e2c16d"
    property color errorSurface: lightTheme ? "#fbe3e5" : "#5a1d1d"
    property color errorInk: lightTheme ? "#8f1d2c" : "#ffffff"
    color: surface
    font.family: "Segoe UI"
    font.pixelSize: 12
    palette.window: panel
    palette.windowText: ink
    palette.base: surface
    palette.text: ink
    palette.button: raised
    palette.buttonText: ink
    palette.highlight: blue
    palette.highlightedText: "white"
    palette.mid: dividerColor
    onLightThemeChanged: {
        core.saveTheme(lightTheme ? "light" : "dark");
        core.themeChrome(lightTheme, surface, ink);
        core.highlightXml(xmlEvidence.textDocument, lightTheme);
    }
    // Compact desktop tokens; not mobile target-size defaults.
    readonly property int spaceUnit: 4
    readonly property int fieldFontSize: 12
    readonly property int treeRowHeight: 28
    readonly property int focusWidth: 2
    property color addedColor: lightTheme ? "#326837" : "#b5cea8"
    property color removedColor: lightTheme ? "#b42929" : "#f48771"
    property color changedColor: lightTheme ? "#806000" : "#dcdcaa"
    property var savedLayout: core.loadLayout()
    property var recentFiles: normalizeRecentFiles(Array.from(core.loadRecentFiles()))
    readonly property var recordTabs: ["Services", "Topology", "Tables", "EPG", "Issues", "Changes"]
    readonly property var commandTable: [
        {id:"analyze",description:"Analyze",keys:"Ctrl+Return",reason:function(){return paletteBackendReason() || (!source.text.trim()?"Choose a source first":"");},run:function(){analyzeButton.clicked();}},
        {id:"open",description:"Open…",keys:"Ctrl+O",reason:paletteBackendReason,run:function(){fileDialog.open();}},
        {id:"export",description:"Export…",keys:"",reason:function(){return !analysisState.complete?"Analyze a source before exporting":paletteBackendReason() || editBlockReason() || (selectedChange?"Return to the workbench selection before exporting":"");},run:function(){renameButton.clicked();}},
        {id:"compare",description:"Compare snapshots",keys:"",reason:function(){return paletteBackendReason() || (!analysisState.complete?"Analyze a source before comparing snapshots":"");},run:openComparison},
        {id:"latest",description:"Latest state",keys:"",reason:function(){return paletteBackendReason() || (!analysisState.complete?"Analyze a source to view its latest state":"");},run:function(){snapshot(-1);}},
        {id:"theme",description:"Toggle theme",keys:"",run:function(){themeToggle.clicked();}},
        {id:"layout",description:"Reset layout",keys:"",run:resetLayout},
        {id:"help",description:"Shortcut help",keys:"? / Ctrl+/",run:showShortcutHelp}
    ].concat(recordTabs.map(function(name){return {id:"tab-"+name.toLowerCase(),description:name,keys:"",run:function(){tab=name;Qt.callLater(function(){(tab==="Topology"?topologyList:recordList).forceActiveFocus();});}};}))
    readonly property var shortcutTable: [
        {keys:"↑ ↓ Home End",description:"Move focus in lists and trees"},
        {keys:"Enter / Space",description:"Select the focused item"},
        {keys:"Ctrl+K",description:"Search records"},
        {keys:"Ctrl+Shift+K",description:"Search inspector structure"},
        commandTable.find(function(row){return row.id==="open";}),
        commandTable.find(function(row){return row.id==="analyze";}),
        {keys:"Ctrl+.",description:"Cancel active scan"},
        {keys:"Alt+Left",description:"Back"},
        {keys:"Ctrl+Enter (Structure)",description:"Go to the focused field's reference"},
        {keys:"Ctrl+Alt+← / →",description:"Resize inspector width"},
        {keys:"Ctrl+Alt+↑ / ↓",description:"Resize timeline height"},
        {keys:"F6 / Shift+F6",description:"Next / previous region"},
        commandTable.find(function(row){return row.id==="help";}),
        {keys:"Esc",description:"Close shortcut help"}
    ]
    property var shortcutReturnFocus: null
    property int shortcutReturnRecent: -1
    property var paletteInput: null
    property var paletteReturnFocus: null
    property var searchPreviousFocus: null
    onActiveFocusItemChanged: {let item=win.activeFocusItem;if(item && item!==recordSearch && item!==topologySearch)searchPreviousFocus=item;}
    property int paletteIndex: 0
    readonly property string paletteMode: paletteInput ? paletteInput.text.replace(/^\s+/,"").charAt(0) : ""
    readonly property var paletteTarget: paletteMode==="#" ? Shared.workbench.paletteIdentifier(paletteInput.text.replace(/^\s+/,""),analysisState) : ({})
    readonly property var paletteRows: paletteMode===">" ? commandTable.filter(function(row){return Shared.workbench.commandMatches(row.description,paletteInput.text.replace(/^\s+/,"").slice(1));}).map(function(row){return {id:row.id,description:row.description,keys:row.keys,reason:row.reason?row.reason():"",run:row.run};}) :
        paletteMode==="#" && paletteTarget.target ? [{id:"identifier",description:paletteTarget.label,keys:"Return",help:paletteTarget.help,target:paletteTarget.target,reason:paletteBackendReason() || (core.inspecting?"Wait for the current inspection to finish":"")}] : []
    readonly property string paletteStatus: paletteRows.length+" "+(paletteMode===">"?"commands":"identifier targets")+(paletteRows.length?" available":". "+(paletteMode==="#"?paletteTarget.message:"No matching commands"))
    function paletteBackendReason() {return !core.available?"Backend unavailable":!backendReady?"Wait for the analysis to finish":exporting?"Wait for the export to finish":"";}
    function closePalette(restoreFocus) {
        let input=paletteInput,previous=paletteReturnFocus;paletteInput=null;commandPalette.close();
        if(input)input.text=input.query;
        if(restoreFocus){paletteReturnFocus=null;if(previous && previous.visible && previous.enabled)previous.forceActiveFocus();else (tab==="Topology"?topologyList:recordList).forceActiveFocus();}
    }
    function executePalette() {
        let row=paletteRows[paletteIndex];if(!row || row.reason)return;
        closePalette(true);
        if(row.target)jumpReference({reference:row.target,path:"",palette:true});else row.run();
    }
    function recentPathKey(path) {
        let key=path.replace(/\\/g,"/");
        return /^(?:[a-z]:\/|\/\/)/i.test(key) ? key.toLowerCase() : key;
    }
    function normalizeRecentFiles(paths) {
        let seen={}, result=[];
        if(!Array.isArray(paths))return result;
        paths.forEach(function(path){if(typeof path!=="string" || !path.trim())return;path=path.trim();let key=recentPathKey(path);if(!Object.prototype.hasOwnProperty.call(seen,key)){seen[key]=true;result.push(path);}});
        return result.slice(0,10);
    }
    function saveRecentFiles() {
        if(!core.saveRecentFiles(recentFiles))showMessage("Recent files saved for this session only.","warning");
    }
    function rememberSource(path) {recentFiles=normalizeRecentFiles([path].concat(recentFiles));saveRecentFiles();}
    function chooseSource(path) {
        if(!backendReady || exporting || saveDialog.visible || !path)return;
        inputKind="ts";source.text=path;recentMenu.close();
        Qt.callLater(function(){analyzeButton.forceActiveFocus();});
    }
    function textInputFocused() {
        let item=win.activeFocusItem;
        return !!item && (item instanceof TextInput || item instanceof TextEdit);
    }
    function showShortcutHelp() {
        if(shortcutDialog.visible)return;
        shortcutReturnFocus=win.activeFocusItem;shortcutReturnRecent=recentMenu.visible ? recentMenu.currentIndex : -1;recentMenu.close();shortcutDialog.open();
    }
    property bool layoutReady: false
    // Keyboard requests precede SplitView polish; preserve intent until saved.
    property real pendingInspectorSize: -1
    property real pendingTimelineSize: -1
    property var comparison: ({})
    property var comparisonFilters: []
    property var comparisonCounts: Shared.workbench.comparisonTotals(comparison)
    property var selectedChange: null
    property var comparisonWorkspace: null
    property int comparisonEvidenceIndex: 0
    property var previewIntent: ({})
    property string comparisonSide: "after"
    property string comparisonError: ""
    property bool compactComparison: recordPane.width < 420 || recordPane.height < 520
    property bool compactInspector: inspectorPane.height < 520
    // Build native JS arrays from bounded pages. Repeated traversal of nested
    // QVariant-backed lists otherwise re-converts rows for every derived binding.
    property var analysisState: ({})
    property var hydrationCollections: ({})
    // Each stage retains the complete immutable revision, not a prefix of rows.
    // Existing search/filter bindings stay reactive without publishing all view
    // models in the same GUI event turn.
    property var tableViewState: ({})
    property var explorerViewState: ({})
    property var historyViewState: ({})
    property var recordViewState: ({})
    property bool presentationPending: false
    property int presentationToken: 0
    signal presentationStageFinished(int stage)
    function publishViewStage(state, token, epoch, stage) {
        if(token!==presentationToken)return;
        try {
            core.mark("presentation_stage_"+stage+"_begin");
            if(stage===0)tableViewState=state;
            else if(stage===1)explorerViewState=state;
            else if(stage===2)historyViewState=state;
            else if(stage===3)recordViewState=state;
            else {
                recordList.forceLayout();tree.forceLayout();
                presentationPending=false;
                core.presentationReady(epoch);
                core.mark("presentation_ready");return;
            }
            core.mark("presentation_stage_"+stage+"_end");
            presentationStageFinished(stage);
            Qt.callLater(function(){publishViewStage(state,token,epoch,stage+1);});
        } catch(error) {
            if(token!==presentationToken)return;
            presentationPending=false;core.presentationFailed(epoch,String(error));
        }
    }
    property var scanProgress: core.progress
    readonly property string activeCollection: tab === "Services" ? "services" : tab === "EPG" ? "events" : tab === "Issues" ? "diagnostics" : tab === "Tables" ? "tables" : ""
    readonly property double densitySourcePackets: Number(analysisState.coverage?.source_packets || analysisState.packets || 0)
    readonly property bool partialResults: !!analysisState.coverage?.partial
    readonly property string coverageText: analysisState.coverage ? (partialResults ? "PARTIAL · read-only · " : "Full coverage · ") + num(analysisState.coverage.scanned_packets) + " / " + num(analysisState.coverage.source_packets) + " packets · " + (analysisState.coverage.ranges || []).map(function(r){return "["+num(r.start_packet)+", "+num(r.end_packet)+")";}).join(", ") : ""
    readonly property bool quickOptionsValid: scanMode.currentValue === "full" || (scanMode.currentValue === "range" ? /^\d+$/.test(scanStart.text) && /^\d+$/.test(scanEnd.text) && Number.isSafeInteger(Number(scanStart.text)) && Number.isSafeInteger(Number(scanEnd.text)) && Number(scanEnd.text)>Number(scanStart.text) : /^\d+$/.test(scanBudget.text) && Number.isSafeInteger(Number(scanBudget.text)) && Number(scanBudget.text)>0 && (scanBudgetUnit.currentIndex===1 || Number(scanBudget.text)<=100))
    property bool backendReady: core.available && !presentationPending && !core.busy && !dvbiWorkspace.busy && !protocolRestoring
    property var detail: JSON.parse(core.detailJson)
    property string tab: "Services"
    property string previousTab: "Services"
    onTabChanged: {
        if(previousTab === "Topology" && !!topologyData.analysis_revision && tab !== "Topology" && !topologyTransition && !topologyTablesReveal){let point=topologyNavigationPoint();point.tab="Topology";topologyBackStack=topologyBackStack.concat([point]);}
        previousTab=tab;
        if (tab !== "Changes" && selectedChange && !topologyTransition) {
            restoreComparisonWorkspace();
        }
        if(tab === "Topology" && !topologyTransition && !topologyLoading && (!topologyData.analysis_revision || topologyStale))loadTopology(false);
    }
    // Semantic objects, keyboard focus and raw evidence are independent states.
    property var topologyData: ({})
    property bool topologyLoading: false
    property string topologyError: ""
    property bool topologyFailed: false
    property string topologyFamily: ""
    property string topologySelection: ""
    property string topologyFocus: ""
    property var topologyExpanded: ({})
    property var topologyLimits: ({})
    property var topologyEvidenceRef: null
    onTopologyEvidenceRefChanged: if(!topologyEvidenceRef){hexEvidence.deselect();topologySectionContext=null;}
    property var topologyResolution: ({})
    property var topologySectionContext: null
    property var topologyRequest: ({})
    property var topologyOrigin: null
    property var topologyBackStack: []
    property bool topologyTransition: false
    property bool topologyTablesReveal: false
    property var topologyCutoff: null
    property string topologyScopeLabel: "Current observation"
    property var topologyNode: (topologyData.nodes || []).concat(topologyData.context_nodes || []).find(function(n) { return n.node_id === topologySelection; }) || null
    property var topologyRelations: (topologyData.edges || []).filter(function(e) { return e.from === topologySelection || e.to === topologySelection; })
    property var topologySources: topologyNode ? Shared.workbench.topologyEvidence(topologyNode, topologyData.edges || []) : []
    property var topologyRowModel: Shared.workbench.topologyRows ? Shared.workbench.topologyRows(topologyData, topologyFamily, topologySearch.query, topologyExpanded, topologyLimits) : ({rows:[]})
    property var topologyRows: (topologyRowModel.rows || []).map(function(r){return r.more ? r : Object.assign({},r,{node_id:r.node.node_id,branch:r.has_children,open:r.expanded});})
    property bool topologySummary: tab === "Topology" && !topologyEvidenceRef && !protocolSourceRef
    property bool topologyStale: topologyFailed || !!topologyData.analysis_revision && (topologyData.analysis_revision !== analysisState.analysis_revision || topologyData.at_packet !== (topologyCutoff === null ? currentPacket() : topologyCutoff))
    property bool topologyCanReveal: !!topologyEvidenceRef && topologyEvidenceRef.at_packet === currentPacket() && topologyEvidenceRef.analysis_revision === analysisState.analysis_revision
    function topologyNodeById(id) { return (topologyData.nodes || []).concat(topologyData.context_nodes || []).find(function(n) { return n.node_id === id; }); }
    function topologyStatusText(node) { return node ? Shared.workbench.topologyStatus(node) : ""; }
    function topologyIdentityText(node) { return node ? Shared.workbench.topologyIdentity(node) : ""; }
    function topologyFullIdentityText(node) { return node ? Shared.workbench.topologyIdentityDetails(node) : ""; }
    function topologyCoverageText() {
        let coverage=topologyData.coverage || {};
        return "Profile: " + (typeof topologyData.interpretation_profile==="object" ? JSON.stringify(topologyData.interpretation_profile) : topologyData.interpretation_profile || "not loaded") +
            ((coverage.missing_tables || []).length ? "\nMissing tables: "+coverage.missing_tables.join(", ") : "") +
            ((coverage.unsupported_relations || []).length ? "\nOutside the current semantic coverage:\n"+coverage.unsupported_relations.join("\n") : "") +
            ((topologyData.diagnostics || []).length ? "\nDiagnostics:\n"+JSON.stringify(topologyData.diagnostics,null,2) : "");
    }
    function topologySourceText(ref) {
        let t=ref.table_identity || {}, l=ref.locator || {};
        return (ref.assertion_key || "Source") + " · PID " + hex(t.pid) + " · TID " + hex(t.table_id,2) + " · §" + t.section_number + " · " + (l.precision || "section") + "\n" + (l.display_path || ref.section_id) + "\n" + ref.section_id + " · v" + (t.version === null ? "—" : t.version) + " · " + (t.current ? "current" : "next") + " · cutoff #" + num(ref.at_packet) + " · " + (ref.role || "evidence");
    }
    function clearTopology() {
        topologyData={};topologyLoading=false;topologyError="";topologyFailed=false;topologyFamily="";topologySelection="";topologyFocus="";
        topologyExpanded={};topologyEvidenceRef=null;topologyResolution={};topologySectionContext=null;topologyRequest={};topologyOrigin=null;
        topologyBackStack=[];topologyTablesReveal=false;topologyCutoff=null;topologyScopeLabel="Current observation";
    }
    function loadTopology(append) {
        if (!backendReady || !analysisState.complete || topologyLoading) return;
        let cutoff=topologyCutoff === null ? currentPacket() : topologyCutoff;
        let offset=append && topologyData.page ? topologyData.page.next_offset : 0;
        if(append && (offset === null || offset === undefined))return;
        topologyRequest={revision:analysisState.analysis_revision,cutoff:cutoff,offset:offset};
        topologyLoading=true;topologyError="";
        core.send("query_topology", {analysis_revision:analysisState.analysis_revision,at_packet:cutoff,offset:offset,limit:500});
    }
    function acceptTopology(result) {
        result=JSON.parse(JSON.stringify(result));
        topologyLoading=false;
        if(topologyRequest.revision!==analysisState.analysis_revision || topologyRequest.cutoff!==(topologyCutoff===null?currentPacket():topologyCutoff)){siOrganizationTimer.restart();return;}
        if(result.message){topologyError=result.message;topologyFailed=true;return;}
        let contractError=Shared.workbench.validateTopology(result,topologyRequest.revision,topologyRequest.cutoff);
        if(contractError){topologyError=contractError;topologyFailed=true;return;}
        topologyFailed=false;
        if(topologyRequest.offset){
            let merged=Object.assign({},result);
            ["nodes","context_nodes","edges"].forEach(function(key){
                let id=key === "edges" ? "edge_id" : "node_id", all=(topologyData[key] || []).slice();
                (result[key] || []).forEach(function(value){if(!all.some(function(old){return old[id]===value[id];}))all.push(value);});
                merged[key]=all;
            });
            topologyData=merged;
        }else topologyData=result;
        if(unifiedInspector.visible)siOrganizationTimer.restart();
        let families=result.projections || [];
        if(!families.some(function(p){return p.family===topologyFamily;}))topologyFamily=families.length ? families[0].family : "";
        if(!topologyFocus && topologyRows.length)topologyFocus=topologyRows[0].node_id;
        if(topologySelection && !topologyNode && !(result.page || {}).has_more)topologyError="The previous object is not observed at this cutoff. Choose an available object.";
    }
    // Reuse the engine's paged, revision-bound topology for the classic SI tree.
    Timer {
        id: siOrganizationTimer; interval: 150; repeat: false
        onTriggered: {
            if(!unifiedInspector.visible || !backendReady || !analysisState.complete || topologyLoading)return;
            if(topologyFailed)return;
            if(!topologyData.analysis_revision || topologyStale){topologyCutoff=null;loadTopology(false);}
            else if((topologyData.page || {}).has_more)loadTopology(true);
        }
    }
    onBackendReadyChanged: if(backendReady)siOrganizationTimer.restart()
    function topologyNavigationPoint() {
        return {selection:topologySelection,focus:topologyFocus,expanded:topologyExpanded,search:topologySearch.query,family:topologyFamily,
            evidence:topologyEvidenceRef,sectionContext:topologySectionContext,resolution:topologyResolution,view:inspectorView,scope:evidenceScope,tab:tab,
            scroll:topologyList.contentY,revision:analysisState.analysis_revision,cutoff:topologyData.at_packet};
    }
    function pushTopologyBack() { topologyBackStack=topologyBackStack.concat([topologyNavigationPoint()]); }
    function topologyBack() {
        if(topologyBackStack.length && topologyBackStack[topologyBackStack.length-1].kind==="selection") {selectionBack();return;}
        if(topologyBackStack.length){
            let stack=topologyBackStack.slice(), saved=stack.pop();topologyBackStack=stack;
            if(saved.revision!==analysisState.analysis_revision || saved.cutoff!==topologyData.at_packet){showMessage("The saved object belongs to an older observation. Reload Topology.","warning");return;}
            topologySelection=saved.selection;topologyFocus=saved.focus;topologyExpanded=saved.expanded;topologySearch.text=saved.search;topologyFamily=saved.family;
            topologyTablesReveal=false;topologyTransition=true;tab=saved.tab;topologyTransition=false;topologyEvidenceRef=null;topologyResolution={};
            if(saved.evidence){if(saved.sectionContext){topologyEvidenceRef=saved.evidence;openTopologySibling(saved.sectionContext,false);}else openTopologyEvidence(saved.evidence,false);}
            inspectorView=saved.view;evidenceScope=saved.scope;
            Qt.callLater(function(){topologyList.contentY=saved.scroll;focusTopologyRow(saved.focus);});
            return;
        }
        if(topologyOrigin){
            let origin=topologyOrigin;topologyOrigin=null;topologyCutoff=null;topologyEvidenceRef=null;topologyScopeLabel="Current observation";
            topologyTransition=true;tab="Changes";selectedChange=origin.row;comparisonSide=origin.side;comparisonWorkspace=origin.workspace;topologyTransition=false;
            inspectChange(origin.row,origin.side,origin.index);return;
        }
        if(topologyEvidenceRef){topologyEvidenceRef=null;topologyResolution={};topologyTablesReveal=false;tab="Topology";focusTopologyRow(topologyFocus);}
    }
    function treeFocused() {
        let item=win.activeFocusItem;while(item){if(item===tree)return true;item=item.parent;}return false;
    }
    function jumpReference(row) {
        if(!row || !row.reference || !backendReady || core.inspecting)return;
        let target=row.reference;
        let saved={kind:"selection",id:detail.id,revision:detail.analysis_revision,cutoff:detail.native_table_at_packet,packet:currentPacket(),service:selectedService,
            tab:tab,view:inspectorView,scope:evidenceScope,filter:filter,pid:pidFilter,query:recordSearch.query,page:tablePage,grouped:groupedTables,invalid:showInvalidSections,
            expanded:expandedTables,explorer:explorerFocusKey,recordIndex:recordList.currentIndex,recordScroll:recordList.contentY,
            collapsed:collapsed,search:treeSearch.text,path:row.path,treeScroll:tree.contentY,change:selectedChange,workspace:comparisonWorkspace,
            topologyRef:topologyEvidenceRef,topologyResolution:topologyResolution,sectionContext:topologySectionContext,revealed:topologyTablesReveal,
            protocolRef:protocolSourceRef,protocolOrigin:protocolSourceOrigin,protocolResolution:protocolSourceResolution,offset:protocolCardOffset,palette:!!row.palette};
        topologyBackStack=topologyBackStack.concat([saved]).slice(-100);
        topologyTransition=true;topologyEvidenceRef=null;topologyResolution={};topologyTablesReveal=false;selectedChange=null;
        recordSearch.clear();treeSearch.clear();inspectorView="Structure";evidenceScope="Section";
        if(target.kind==="service")tab="Services";
        else {selectExplorer({pid:target.pid,name:target.name});groupedTables=false;if((analysisState.tables || []).some(function(r){return r.id===target.id && r.crc?.status==="invalid";}))showInvalidSections=true;}
        let rowIndex=target.kind==="service" ? rows.findIndex(function(r){return r.id===target.sid && r.source_id===target.id;}) : rawTableRows.findIndex(function(r){return r.id===target.id;});
        if(target.kind!=="service")tablePage=Math.max(0,Math.floor(rowIndex/100));
        topologyTransition=false;
        // Use the record activation path, including its normal inspection guards.
        let record=target.kind==="service" ? rows[rowIndex] : rawTableRows[rowIndex];
        if(record)activate(record);
        Qt.callLater(function(){recordList.currentIndex=target.kind==="service"?rowIndex:rowIndex%100;recordList.positionViewAtIndex(recordList.currentIndex,ListView.Contain);tree.forceActiveFocus();});
    }
    function selectionBack() {
        if(!backendReady || core.inspecting)return;
        let stack=topologyBackStack.slice(),saved=stack.pop();
        if(!saved || saved.kind!=="selection")return;
        topologyBackStack=stack;
        if(saved.revision!==analysisState.analysis_revision || saved.packet!==currentPacket())return;
        clearProtocolSource();protocolRestoring=true;protocolRestorePending=saved;selected=saved.id;selectedService=saved.service;
        core.send("inspect",{id:saved.id,analysis_revision:saved.revision,at_packet:saved.cutoff});
    }
    function restoreReferenceSelection(saved) {
        topologyTransition=true;tab=saved.tab;selectedChange=saved.change;comparisonWorkspace=saved.workspace;topologyTransition=false;
        filter=saved.filter;pidFilter=saved.pid;recordSearch.text=saved.query;groupedTables=saved.grouped;showInvalidSections=saved.invalid;
        expandedTables=saved.expanded;tablePage=saved.page;explorerFocusKey=saved.explorer;
        topologyEvidenceRef=saved.topologyRef;topologyResolution=saved.topologyResolution;topologySectionContext=saved.sectionContext;topologyTablesReveal=saved.revealed;
        protocolSourceRef=saved.protocolRef;protocolSourceOrigin=saved.protocolOrigin;protocolSourceResolution=saved.protocolResolution;protocolCardOffset=saved.offset;
        inspectorView=saved.view;evidenceScope=saved.scope;collapsed=saved.collapsed;treeSearch.text=saved.search;
        Qt.callLater(function(){
            if(!protocolRestoring || detail.id!==saved.id || detail.analysis_revision!==saved.revision)return;
            recordList.currentIndex=saved.recordIndex;recordList.contentY=saved.recordScroll;
            if(saved.palette)(tab==="Topology"?topologyList:recordList).forceActiveFocus();
            let index=treeRows.findIndex(function(r){return r.path===saved.path;});
            if(index>=0){tree.currentIndex=index;tree.positionViewAtIndex(index,ListView.Contain);tree.forceActiveFocus();tree.contentY=saved.treeScroll;}
            protocolRestoring=false;
        });
    }
    function focusTopologyRow(id) {
        let index=topologyRows.findIndex(function(r){return r.node_id===id;});
        if(index>=0){topologyList.currentIndex=index;topologyFocus=id;topologyList.positionViewAtIndex(index,ListView.Contain);topologyList.forceActiveFocus();}
    }
    function selectTopologyNode(id, remember) {
        clearProtocolSource();
        let node=topologyNodeById(id);if(!node)return;
        if(remember && topologySelection && topologySelection!==id)pushTopologyBack();
        topologySelection=id;topologyFocus=id;topologyEvidenceRef=null;topologyResolution={};topologySectionContext=null;topologyTablesReveal=false;if(!topologyFailed)topologyError="";
        let expanded=Object.assign({},topologyExpanded), parent=node.parent_id, seen={};
        while(parent && !seen[parent]){seen[parent]=true;expanded[parent]=true;let p=topologyNodeById(parent);parent=p ? p.parent_id : null;}
        topologyExpanded=expanded;topologyFamily=node.family;
    }
    function activateTopologyRow(row) {
        if(row.more){let limits=Object.assign({},topologyLimits),key=row.parent_id || "$roots";limits[key]=(limits[key] || 100)+100;topologyLimits=limits;return;}
        selectTopologyNode(row.node_id,true);
    }
    function selectTopologyRelation(edge) {
        let target=edge.from===topologySelection ? edge.to : edge.from;
        if(!topologyNodeById(target)){topologyError="This related object is not loaded. Load more objects to navigate to it.";return;}
        selectTopologyNode(target,true);topologySearch.clear();Qt.callLater(function(){focusTopologyRow(target);});
    }
    function toggleTopologyRow(row) {
        if(!row || !row.branch || topologySearch.query.trim())return;
        let expanded=Object.assign({},topologyExpanded);expanded[row.node_id]=!row.open;topologyExpanded=expanded;
    }
    function openTopologyEvidence(ref, remember) {
        clearProtocolSource();
        if(!backendReady || topologyStale || !ref)return;
        if(ref.analysis_revision!==analysisState.analysis_revision || ref.at_packet!==topologyData.at_packet){topologyError="This source belongs to an older observation. Reload Topology.";return;}
        if(remember!==false)pushTopologyBack();
        topologyEvidenceRef=ref;topologyResolution={};topologySectionContext=null;topologyTablesReveal=false;
        selected=ref.section_id;selectedService=-1;preview={};treeSearch.clear();collapsed={};evidenceScope="Section";inspectorView="Structure";
        core.send("inspect",{id:ref.section_id,analysis_revision:ref.analysis_revision,at_packet:ref.at_packet});
    }
    function openTopologySibling(section, remember) {
        if(!topologyEvidenceRef || !backendReady || topologyStale)return;
        if(remember!==false)pushTopologyBack();
        topologySectionContext=section;topologyResolution={};selected=section.id;selectedService=-1;preview={};
        treeSearch.clear();collapsed={};evidenceScope="Section";inspectorView="Structure";
        core.send("inspect",{id:section.id,analysis_revision:topologyEvidenceRef.analysis_revision,at_packet:topologyEvidenceRef.at_packet});
    }
    function topologyActiveSourceText() {
        if(!topologyEvidenceRef)return "";
        if(!topologySectionContext)return topologySourceText(topologyEvidenceRef);
        let section=topologySectionContext;
        return "Related section · PID "+hex(section.pid)+" · TID "+hex(section.table_id,2)+" · §"+section.section+"\n"+section.id+" · cutoff #"+num(topologyEvidenceRef.at_packet)+"\nOriginal semantic source is retained for Back.";
    }
    function resolveTopologyInspection(result) {
        if(!topologyEvidenceRef)return;
        if(result.message){topologyResolution={status:"error",message:result.message};return;}
        if(topologySectionContext){
            let valid=result.id===topologySectionContext.id && result.analysis_revision===topologyEvidenceRef.analysis_revision && result.native_table_at_packet===topologyEvidenceRef.at_packet;
            topologyResolution={status:valid ? "related_section" : "mismatch",precision:valid ? "section" : "none",path:valid ? "section" : "",message:valid ? "Opened the exact related section at the original evidence cutoff; the original semantic field locator does not apply." : "The returned related section or its observation context does not match."};
        }else topologyResolution=Shared.workbench.resolveTopologyEvidence(topologyEvidenceRef,result);
        if(topologyResolution.path){
            let path=topologyResolution.path.replace(/^section\//,"");
            let open={};let parts=path.split("/");for(let i=1;i<=parts.length;i++)open[parts.slice(0,i).join("/")]=false;collapsed=open;treeSearch.clear();
            topologyRevealTimer.restart();
        }
        highlightTopologyHex();
    }
    // One reason per blocked rename state, in the order a user can resolve them.
    function editBlockReason() {
        if (core.busy) return "Wait for the scan to finish; cached results remain available for browsing";
        if (!backendReady) return "Backend unavailable";
        if (partialResults) return "Quick preview is read-only. Run a full scan before editing or exporting";
        if (!analysisState.complete || core.inspecting) return "Wait for the analysis to finish";
        if (detail.name !== "SDT") return "Rename needs an SDT (Service Description Table) section";
        if (!detail.valid) return "Rename needs a section with a valid CRC";
        if (!chosenService()) return "This SDT section lists no services";
        return "";
    }
    function highlightTopologyHex() {
        let range=activeInspectionResolution.byte_range || activeInspectionResolution.range;
        if(!activeInspectionRef || !range || range.offset_scope!=="section_bytes")return;
        let start=range.offset,end=start+range.length-1;
        if(range.length>0 && end<(detail.raw_hex || "").replace(/\s/g,"").length/2){
            let pos=function(offset){return Math.floor(offset/16)*72+6+(offset%16)*3;};
            Qt.callLater(function(){hexEvidence.select(pos(start),pos(end)+2);});
        }
    }
    function showTopologyInTables() {
        if(!topologyCanReveal)return;
        pushTopologyBack();topologyTablesReveal=true;
        let targetId=topologySectionContext ? topologySectionContext.id : topologyEvidenceRef.section_id;
        let r=(analysisState.tables || []).find(function(row){return row.id===targetId;});
        if(!r){topologyError="The source section is unavailable in this workbench cutoff.";return;}
        filter=r.name || "Private / other";pidFilter=r.pid;recordSearch.clear();showInvalidSections=r.crc?.status==="invalid" || showInvalidSections;
        groupedTables=false;tab="Tables";
        let index=rawTableRows.findIndex(function(row){return row.id===r.id;});tablePage=Math.max(0,Math.floor(index/100));
        Qt.callLater(function(){recordList.currentIndex=index%100;recordList.positionViewAtIndex(recordList.currentIndex,ListView.Contain);});
    }
    function openComparisonTopology() {
        if(!selectedChange || !selectedChange[comparisonSide])return;
        topologyOrigin={row:selectedChange,side:comparisonSide,index:comparisonEvidenceIndex,workspace:comparisonWorkspace};
        topologyCutoff=selectedChange[comparisonSide].at_packet;topologyScopeLabel="Comparison "+(comparisonSide==="before"?"A":"B");
        topologyBackStack=[];topologyEvidenceRef=null;topologySelection="";topologyData={};
        topologyTransition=true;tab="Topology";selectedChange=null;topologyTransition=false;loadTopology(false);
    }
    onInspectorViewChanged: if(inspectorView === "Hex")highlightTopologyHex()
    property string inspectorView: "Structure"
    property string epgLanguage: ""
    property var identifierResult: ({})
    property var satelliteResult: ({})
    function revealMetadataControl(item) {
        if(inspectorView!=="Metadata" || !item)return;
        let scroll=metadataScroll.contentItem,y=item.mapToItem(metadataContent,0,0).y,top=scroll.contentY;
        if(y<top)top=y;
        else if(y+Math.min(item.height,metadataScroll.availableHeight)>top+metadataScroll.availableHeight)top=y+Math.min(item.height,metadataScroll.availableHeight)-metadataScroll.availableHeight;
        scroll.contentY=Math.max(0,Math.min(top,Math.max(0,scroll.contentHeight-metadataScroll.availableHeight)));
    }
    function satelliteText(x) {
        let p=x.raw_parameters || {};
        return "Candidates only · " + (x.status || x.error || "") + "\n" +
            (p.orbital_position_degrees === undefined ? "No orbital position" : p.orbital_position_degrees + "° " + p.direction) +
            " · " + (p.frequency_hz === undefined ? "frequency unspecified" : p.frequency_hz + " Hz") +
            " · " + (p.symbol_rate === undefined ? "symbol rate unspecified" : p.symbol_rate + " sym/s") +
            " · " + (p.polarization || "polarization unspecified") + "\n" +
            (x.candidates || []).map(function(c){return c.name + " · candidate · Δ " + c.orbital_delta_degrees + "°\nSource: " + c.source.publisher + " · reviewed " + c.source.reviewed_at + "\n" + c.source.url;}).join("\n") +
            "\n" + (x.uncertainty || "") + "\nOnly nominal orbital position is compared. Frequency, symbol rate, polarization and modulation are not checked.";
    }
    function eventVariant(event) {
        let variants=event.language_variants || [];
        return variants.find(function(v) {return v.language_code === epgLanguage;}) || variants.find(function(v) {return v.language_code === event.default_language;}) || variants[0] || ({});
    }
    function eventTitle(event) {
        let variant=eventVariant(event);
        return variant.language_code ? (variant.title || "No usable title") : (event.title || "Untitled event");
    }
    property int protocolCardOffset: 0
    property string protocolCardKey: [detail.id,detail.analysis_revision,detail.native_table_at_packet].join(":")
    onProtocolCardKeyChanged: protocolCardOffset=0
    property var protocolCardModel: Shared.workbench.protocolCards(detail,protocolCardOffset,20)
    property var protocolSourceRef: null
    property var protocolSourceOrigin: null
    property var protocolSourceResolution: ({})
    property var protocolRestorePending: null
    property bool protocolRestoring: false
    readonly property var activeInspectionRef: protocolSourceRef || topologyEvidenceRef
    readonly property var activeInspectionResolution: protocolSourceRef ? protocolSourceResolution : topologyResolution
    function clearProtocolSource() {protocolRestoreTimer.stop();protocolRestoring=false;protocolSourceRef=null;protocolSourceOrigin=null;protocolSourceResolution={};protocolRestorePending=null;}
    function openProtocolSource(source, remember, cardIndex, sourceIndex) {
        if(!source || !source.available || !backendReady || core.inspecting)return;
        let ref=source.ref;
        if(ref.analysis_revision!==analysisState.analysis_revision){showMessage("This metadata source belongs to an older analysis.","warning");return;}
        if(remember!==false)protocolSourceOrigin={id:detail.id,revision:detail.analysis_revision,cutoff:detail.native_table_at_packet,service:selectedService,tab:tab,view:inspectorView,scope:evidenceScope,offset:protocolCardOffset,scroll:metadataScroll.contentItem.contentY,search:treeSearch.text,collapsed:collapsed,card:cardIndex,source:sourceIndex};
        protocolSourceRef=ref;protocolSourceResolution={};selected=ref.section_id;selectedService=-1;preview={};
        treeSearch.clear();collapsed={};evidenceScope="Section";inspectorView="Structure";
        core.send("inspect",{id:ref.section_id,analysis_revision:ref.analysis_revision,at_packet:ref.at_packet});
    }
    function protocolSourceBack() {
        let origin=protocolSourceOrigin;
        if(!origin || !backendReady || core.inspecting)return;
        if(origin.revision!==analysisState.analysis_revision){clearProtocolSource();showMessage("The originating metadata belongs to an older analysis.","warning");return;}
        clearProtocolSource();protocolRestoring=true;protocolRestorePending=origin;selected=origin.id;selectedService=origin.service;
        core.send("inspect",{id:origin.id,analysis_revision:origin.revision,at_packet:origin.cutoff});
    }
    function resolveProtocolInspection(result) {
        protocolSourceResolution=result.message?{status:"error",message:result.message}:Shared.workbench.resolveTopologyEvidence(protocolSourceRef,result);
        if(protocolSourceResolution.path){
            let path=protocolSourceResolution.path.replace(/^section\//,"");let open={},parts=path.split("/");
            for(let i=1;i<=parts.length;i++)open[parts.slice(0,i).join("/")]=false;
            collapsed=open;treeSearch.clear();topologyRevealTimer.restart();
        }
        highlightTopologyHex();
    }
    function metadataEntries() {
        let entries=[];
        (detail.satellite_associations || []).forEach(function(x) {
            entries.push({title:"Satellite candidates · " + (x.transport ? "TS " + hex(x.transport.transport_stream_id) + " / ONID " + hex(x.transport.original_network_id) : "section descriptor") + " · offset " + x.wire_source.section_offset,
                text:satelliteText(x), evidence:JSON.stringify(x,null,2)});
        });
        (detail.identifier_lookups || []).forEach(function(x) {
            entries.push({title:x.namespace + " · " + x.raw_hex, text:(x.label || "Unknown") + " · " + x.status + "\n" + x.uncertainty, evidence:JSON.stringify(x,null,2)});
        });
        (detail.text_diagnostics || []).forEach(function(x) {
            entries.push({title:x.field + " · " + (x.language_code || "no language tag"), text:x.status + " · " + (x.effective_charset || "unknown charset") + " · " + x.basis + "\n" + x.decoded_text + "\nSelector: " + (x.selector_hex || "none") + " · section offset " + x.source.section_offset + "\nRaw: " + x.raw_hex + "\n" + (x.warnings || []).join("\n"), evidence:JSON.stringify(x,null,2)});
        });
        (detail.events || []).forEach(function(e) {
            let v=eventVariant(e);
            entries.push({title:"Event " + hex(e.id) + " · " + (v.language_code || "no language") + (epgLanguage && v.language_code !== epgLanguage ? " · fallback" : ""), text:eventTitle(e) + "\nShort: " + (v.short_status || "absent") + "\n" + (v.short_text || "") + "\nExtended: " + (v.extended_status || "absent") + "\n" + (v.extended_text === null || v.extended_text === undefined ? "No complete extended text" : v.extended_text) + "\n" + (v.warnings || []).join("\n"), evidence:JSON.stringify({event_id:e.id,service_id:e.service_id,source_id:e.source_id,variant:v},null,2)});
        });
        return entries.filter(function(x){return x.title.indexOf("Event ")===0;}).concat(entries.filter(function(x){return x.title.indexOf("Event ")!==0;}));
    }
    property var initialInspectorDetails: Shared.workbench.inspectorDisclosure(savedLayout.inspectorDetails)
    property bool identityOpen: initialInspectorDetails.identity
    property bool crcOpen: initialInspectorDetails.crc
    property bool arrivalOpen: initialInspectorDetails.arrival
    property bool sectionGroupOpen: initialInspectorDetails.sections
    property bool scopeOpen: initialInspectorDetails.scope
    property bool warningsOpen: initialInspectorDetails.warnings
    onIdentityOpenChanged: if(layoutReady){layoutSaveTimer.restart();if(identityOpen)revealInspectorDetail(identityDetails);}
    onCrcOpenChanged: if(layoutReady){layoutSaveTimer.restart();if(crcOpen)revealInspectorDetail(crcDetails);}
    onArrivalOpenChanged: if(layoutReady){layoutSaveTimer.restart();if(arrivalOpen)revealInspectorDetail(arrivalDetails);}
    onSectionGroupOpenChanged: if(layoutReady){layoutSaveTimer.restart();if(sectionGroupOpen)revealInspectorDetail(sectionChoice.visible ? sectionChoice : sectionGroupDetails);}
    onScopeOpenChanged: if(layoutReady){layoutSaveTimer.restart();if(scopeOpen)revealInspectorDetail(cutoffDetails);}
    onWarningsOpenChanged: if(layoutReady){layoutSaveTimer.restart();if(warningsOpen)revealInspectorDetail(nativeDecodeWarningLabel);}
    readonly property var inspectorSummary: Shared.workbench.inspectorSummary(detail)
    readonly property var inspectorNotes: Shared.workbench.inspectorWarnings(detail,analysisState)
    property bool showInvalidSections: false
    property string evidenceScope: "Merged"
    property var selectedGroup: (tableViewState.table_groups || []).find(function(g) { return (g.section_ids || []).indexOf(detail.id) >= 0; }) || ({})
    property var siblingSections: (tableViewState.tables || []).filter(function(r) { return (selectedGroup.section_ids || []).indexOf(r.id) >= 0 && (showInvalidSections || r.crc?.status !== "invalid"); })
    property int hiddenInvalidCount: (tableViewState.tables || []).filter(function(r) { return r.crc?.status === "invalid" && tableMatches(r); }).length
    // Fixed table identities, shared with the Web frontend. Never hash unknown names.
    function tableCategory(name) {
        let fixed = {
            PAT:["#78baff","◆","Program association"],
            PMT:["#72dfc0","▲","Program map"],
            CAT:["#ff9f9f","■","Conditional access"],
            NIT:["#d7b2ff","◈","Network information"],
            SDT:["#f1df85","▦","Service description"],
            BAT:["#e9b699","◇","Bouquet association"],
            EIT:["#eea6d7","◷","Event information"],
            TDT:["#9fdb8d","◴","UTC time and date"],
            TOT:["#ffb66e","◶","Time offset"],
            AIT:["#a3e4ec","▤","Application information"]
        };
        if (fixed[name]) return fixed[name];
        if (/^DSMCC/.test(name || "")) return ["#bbb5ff","▥","DSM-CC data"];
        return ["#d5dce7","○","Other signalling"];
    }
    function tableColor(name) {
        let dark = {PAT:"#175eac",PMT:"#147358",CAT:"#b32e39",NIT:"#7946a9",SDT:"#786000",BAT:"#92502c",EIT:"#a33e80",TDT:"#396d27",TOT:"#9c5009",AIT:"#126f7a"};
        return lightTheme ? (dark[name] || (/^DSMCC/.test(name || "") ? "#6551a5" : "#536173")) : tableCategory(name)[0];
    }
    function groupSummary() {
        if (!selectedGroup.validity) return "";
        return (selectedGroup.validity === "all_invalid" ? "ALL INVALID" : selectedGroup.validity === "mixed" ? "MIXED VALID / INVALID" : "VALID") + " · " + (selectedGroup.observed_section_numbers || []).length + " observed sections" + ((selectedGroup.missing_section_numbers || []).length ? " · missing " + selectedGroup.missing_section_numbers.join(", ") : " · none missing") + (selectedGroup.selected_complete ? " · current assembly complete" : " · current assembly incomplete");
    }
    function crcText(section) {
        let crc = section.crc || {};
        return "CRC " + (crc.transmitted_hex || "—") + " · " + (crc.status || "unavailable");
    }
    function arrivalText(section) {
        let d=section.distribution || {};
        if (d.first_packet === undefined) return "";
        return "First #" + num(d.first_packet) + " → last #" + num(d.last_packet) + " · " + num(d.observation_count) + " arrivals";
    }
    function foldAll(fold) {
        treeSearch.clear(); let next={};
        makeTree(detail,selectedService,{},true).forEach(function(row) { if(row.branch) next[row.path]=fold; });
        collapsed=next; tree.currentIndex=0;
    }
    property string selected: ""
    property int selectedService: -1
    property string filter: ""
    property int pidFilter: -1
    property var expandedTables: ({})
    property var preview: ({})
    property string notice: ""
    property string messageLevel: "info"
    property bool messageExpired: false
    property bool updatingMessage: false
    property string warningMessage: ""
    property int warningRepeat: 0
    property string errorMessage: ""
    onNoticeChanged: if (!updatingMessage && notice) showMessage(notice)
    ListModel { id: messagesModel }
    Timer { id: messageTimer; interval: 4000; onTriggered: messageExpired = true }
    function showMessage(text, level) {
        text=String(text || "");if(!text)return;
        level=level || "info";messageTimer.stop();messageExpired=false;messageLevel=level;
        updatingMessage=true;notice=text;updatingMessage=false;
        messagesModel.insert(0,{messageLevel:level,messageTime:Qt.formatTime(new Date(),"HH:mm:ss"),messageText:text});
        if(messagesModel.count>50)messagesModel.remove(50);
        if(level==="warning"){warningRepeat=warningMessage===text ? warningRepeat+1 : 1;warningMessage=text;}
        if(level==="error"){warningMessage="";warningRepeat=0;errorMessage=text;}
        if(level==="info")messageTimer.restart();
    }
    function agentState() {
        let diagnostics = core.diagnostics();
        return JSON.stringify({input_kind:inputKind,dvbi:dvbiWorkspace.state(),settled: !presentationPending && !protocolRestoring && !dvbiWorkspace.busy && !core.busy && !core.inspecting && !core.comparing && !topologyLoading && !topologyRevealTimer.running && diagnostics.pending === 0,
            source: analysisState.source || "", analysis_status: analysisState.analysis_status || "idle",
            scan: {progress:scanProgress,paused:core.paused,pause_pending:core.pausePending,busy:core.busy,presentation: presentationPending,coverage:analysisState.coverage},
            documents:documentWorkspace.snapshot(),document_mode:documentMode,classic_frame:classicState(),unified: {context:unifiedInspector.captureContext(),navigation:unifiedInspector.navigation.map(function(r){return {key:r.key,kind:r.kind,label:r.label,depth:r.depth,record_id:r.record?r.record.id:'',path:r.node?r.node.path:'',expanded:unifiedInspector.expandable(r)&&unifiedInspector.rowOpen(r)};}),services:serviceRows,visible:unifiedInspector.visible,path:unifiedInspector.selectedPath,history:unifiedInspector.history.length,fields:unifiedInspector.fieldRows,records:unifiedInspector.records,nodes:unifiedInspector.nodes.map(function(n){return {path:n.path,label:n.label};}),hex:unifiedInspector.hexOpen},
            selected: selected, selected_service: selectedService, packet: currentPacket(),
            theme: lightTheme ? "light" : "dark", explorer: explorerRows.map(function(row) {return Object.assign({},row,{selected:explorerSelected(row)});}),
            table_filter: {pid:pidFilter,name:filter,count_unit:"logical_tables"},
            records: {groups:tableModel.groups.map(function(g){return g.id;}),sections:rawTableRows.map(function(r){return r.id;}),hidden:tableModel.hidden,count_text:tableModel.count_text,grouped:groupedTables,page:tablePage},
            history: {all:allTableHistory,entries:historyRows,page:historyPage}, evidence_scope:evidenceScope.toLowerCase(), tab: tab, inspector: inspectorView, tree_search: treeSearch.text,
            focused_tree_path: tree.activeFocus && treeRows[tree.currentIndex] ? treeRows[tree.currentIndex].path : "",
            tree: treeRows.slice(0, 2500), tree_limit: 2500, diagnostics: diagnostics,
            topology: {data:topologyData,family:topologyFamily,selected_node:topologySelection,focused_node:topologyFocus,expanded:topologyExpanded,search:topologySearch.query,rows:topologyRows,loading:topologyLoading,stale:topologyStale,error:topologyError,summary:topologySummary,sources:topologySources,active_evidence:topologyEvidenceRef,section_context:topologySectionContext,resolution:topologyResolution,back_depth:topologyBackStack.length,scope:topologyScopeLabel,can_reveal:topologyCanReveal},
            protocol: {scroll:metadataScroll.contentItem.contentY,cards:protocolCardModel,sources:protocolCardModel.cards.map(function(c){return Shared.workbench.protocolCardSources(c);}),active_evidence:protocolSourceRef,resolution:protocolSourceResolution,can_back:!!protocolSourceOrigin},
            comparison_context: {data:comparison,selected:selectedChange,side:comparisonSide,origin:topologyOrigin},
            inspection: {id:detail.id,revision:detail.analysis_revision,cutoff:detail.native_table_at_packet,anchors:detail.evidence_anchors || [],hex_selection:hexEvidence.selectedText},
            source_map: {tree: "ui/qt/Main.qml:makeTree", transport: "ui/qt/main.cpp:Bridge"}});
    }
    function agentAction(action) {
        if(['carousel_open','carousel_tab','carousel_view','carousel_back'].indexOf(action.name)>=0)return JSON.stringify({accepted:documentWorkspace.carouselAction(action)});
        if(action.name==='classic_command' && ['toolbar','status','tree','summary','configuration','index','about','messages','new','decoded','close','cascade','tile','arrange','packets','bitrate','services','carousel'].indexOf(action.value)>=0){classicCommand(action.value);return JSON.stringify({accepted:true});}
        if(action.name==="scan_control" && ["pauseAnalysis","cancelAnalysis","unifiedNext","unifiedPrevious","openSource"].indexOf(action.value)>=0)return JSON.stringify({accepted:core.click(action.value)});
        if(action.name==="scan_mode" && backendReady && ["full","prefix","range","distributed"].indexOf(action.value)>=0){scanMode.currentIndex=scanMode.indexOfValue(action.value);scanBudgetUnit.currentIndex=0;scanBudget.text="10";scanStart.text="0";scanEnd.text="6";return JSON.stringify({accepted:true});}
        if(action.name==="unified_select" && !advancedMode) {let row=unifiedInspector.records.find(function(r){return r.id===action.id;});if(!row)return JSON.stringify({error:"Unknown section"});unifiedInspector.selectRecord(row);return JSON.stringify({accepted:true});}
        if(action.name==="unified_path" && !advancedMode && unifiedInspector.nodes.some(function(n){return n.path===action.path;})){unifiedInspector.focusNode(action.path);return JSON.stringify({accepted:true});}
        if(action.name==="unified_node" && !advancedMode){let row=unifiedInspector.navigation.find(function(r){return r.key===action.key && r.kind==='node';});if(!row)return JSON.stringify({error:"Unknown tree node"});unifiedInspector.activate(row);return JSON.stringify({accepted:true});}
        if(action.name==="unified_back" && !advancedMode){unifiedInspector.back();return JSON.stringify({accepted:true});}
        if(action.name==="unified_hex" && typeof action.value==="boolean"){unifiedInspector.hexOpen=action.value;return JSON.stringify({accepted:true});}
        if(action.name==="open_source" && typeof action.path==="string" && backendReady){source.text=action.path;scan();return JSON.stringify({accepted:true});}
        if(action.name==="cancel_scan" && core.busy){cancelScan();return JSON.stringify({accepted:true});}
        if(action.name==="window_size" && action.width>=1000 && action.width<=1920 && action.height>=680 && action.height<=1200){win.width=action.width;win.height=action.height;return JSON.stringify({accepted:true});}
        if(["select_snapshot","select_record","history_jump","compare_snapshots","rescan"].indexOf(action.name)>=0 && !backendReady)
            return JSON.stringify({accepted:false,error:"Analysis or result presentation is still in progress"});
        if(action.name==="input_kind" && ["ts","dvbi"].indexOf(action.value)>=0 && !dvbiWorkspace.busy && !core.busy){inputKind=action.value;return JSON.stringify({accepted:true});}
        if(action.name.indexOf("dvbi_")===0){inputKind="dvbi";return JSON.stringify(dvbiWorkspace.action(action)?{accepted:true}:{error:"Unsupported DVB-I UI action"});}
        if (action.name === "select_tab" && ["Services", "Topology", "Tables", "EPG", "Issues", "Changes"].indexOf(action.value) >= 0) tab = action.value;
        else if (action.name === "compare_snapshots" && Number.isInteger(action.from) && Number.isInteger(action.to) && action.from>=0 && action.to>=0 && action.from<analysisState.packets && action.to<analysisState.packets) {tab="Changes";fromPacket.text=String(action.from);toPacket.text=String(action.to);compareSnapshots(0);}
        else if (action.name === "comparison_source" && Number.isInteger(action.index) && (comparison.changes || [])[action.index] && ["before","after"].indexOf(action.side)>=0) inspectChange(comparison.changes[action.index],action.side);
        else if (action.name === "comparison_topology" && selectedChange) openComparisonTopology();
        else if (action.name === "topology_select" && topologyNodeById(action.id)) selectTopologyNode(action.id,true);
        else if (action.name === "topology_search" && typeof action.value === "string" && action.value.length<=512) topologySearch.text=action.value;
        else if (action.name === "topology_family" && (topologyData.projections || []).some(function(p){return p.family===action.value;})) topologyFamily=action.value;
        else if (action.name === "topology_toggle" && topologyRows.some(function(r){return r.node_id===action.id;})) toggleTopologyRow(topologyRows.find(function(r){return r.node_id===action.id;}));
        else if (action.name === "topology_focus" && topologyRows.some(function(r){return r.node_id===action.id;})) focusTopologyRow(action.id);
        else if (action.name === "topology_source" && Number.isInteger(action.index) && topologySources[action.index]) openTopologyEvidence(topologySources[action.index].ref);
        else if (action.name === "topology_sibling" && typeof action.id==="string" && siblingSections.some(function(r){return r.id===action.id;})) openTopologySibling(siblingSections.find(function(r){return r.id===action.id;}));
        else if(action.name==="protocol_source" && protocolCardModel.cards[action.card])openProtocolSource(Shared.workbench.protocolCardSources(protocolCardModel.cards[action.card])[action.index],true,action.card,action.index);
        else if(action.name==="protocol_scroll" && Number.isFinite(action.value) && inspectorView==="Metadata")metadataScroll.contentItem.contentY=Math.max(0,Math.min(action.value,metadataScroll.contentItem.contentHeight-metadataScroll.height));
        else if(action.name==="protocol_page_control" && ["Next","Previous"].indexOf(action.value)>=0)core.click("protocol"+action.value);
        else if(action.name==="protocol_back")protocolSourceBack();
        else if(action.name==="protocol_page" && Number.isInteger(action.offset) && action.offset>=0 && action.offset<protocolCardModel.total)protocolCardOffset=action.offset;
        else if (action.name === "topology_back") topologyBack();
        else if (action.name === "topology_tables") showTopologyInTables();
        else if (action.name === "topology_more") loadTopology(true);
        else if (action.name === "topology_reload") loadTopology(false);
        else if (action.name === "topology_key" && ["Up","Down","Left","Right","Home","End","Return","Space","Tab","Ctrl+K","Escape","Alt+Left","F6"].indexOf(action.value)>=0) core.key(action.value);
        else if (action.name === "select_snapshot" && Number.isInteger(action.packet) && action.packet>=-1 && action.packet<Number(analysisState.packets || 0)) snapshot(action.packet);
        else if (action.name === "select_record" && typeof action.id === "string" && (analysisState.tables || []).some(function(r){return r.id===action.id;})) { tab="Tables";inspect(action.id); }
        else if(action.name==="rescan" && !metadataMode)scan();
        else if (action.name === "set_bad_crc" && typeof action.value === "boolean") showInvalidSections=action.value;
        else if (action.name === "set_grouped" && typeof action.value === "boolean") groupedTables=action.value;
        else if (action.name === "search_records" && typeof action.value === "string" && action.value.length<=512) recordSearch.text=action.value;
        else if (action.name === "set_scope" && ["merged","section"].indexOf(action.value)>=0) evidenceScope=action.value==="merged"?"Merged":"Section";
        else if (action.name === "set_view" && ["Structure","Hex","XML","Decoded","Metadata","References"].indexOf(action.value)>=0) inspectorView=action.value;
        else if (action.name === "history_scope" && typeof action.value === "boolean") allTableHistory=action.value;
        else if (action.name === "history_jump" && Number.isInteger(action.index) && action.index>=0 && action.index<historyRows.length) { activateHistory(historyRows[action.index]); }
        else if (action.name === "set_theme" && ["dark", "light"].indexOf(action.value) >= 0) lightTheme = action.value === "light";
        else if (action.name === "search_tree" && typeof action.value === "string" && action.value.length <= 512) treeSearch.text = action.value;
        else if (action.name === "focus_tree" || action.name === "toggle_tree") {
            let index = treeRows.findIndex(function(row) { return row.path === action.path; });
            if (index < 0) return JSON.stringify({error: "Visible tree path not found"});
            if (action.name === "toggle_tree") {
                if (!treeRows[index].branch || treeSearch.text.trim()) return JSON.stringify({error: "Only an unfiltered branch can be toggled"});
                toggle(action.path);
            }
            tree.currentIndex = index;
            tree.positionViewAtIndex(index, ListView.Contain);
            tree.forceActiveFocus();
        } else return JSON.stringify({error: "Unsupported UI action"});
        return JSON.stringify({accepted: true});
    }
    // Only scripted validation uses this explicitly supplied artifact directory.
    property string artifactDir: core.env("SHOWPSISI_ARTIFACT_DIR")
    property var saveIntent: ({})
    property bool exporting: false
    property string exportFeedback: ""
    property url lastExportFolder: core.exportFolder()
    property bool allTableHistory: false
    property int historyPage: 0
    property var historyRows: Shared.workbench.history(historyViewState, detail, allTableHistory)
    property string historyIdentity: [detail.pid,detail.table_id,detail.extension].join(":")
    onHistoryIdentityChanged: historyPage=0
    onAllTableHistoryChanged: historyPage=0
    property string snapshotTarget: ""
    property int snapshotTargetService: -1
    property var collapsed: ({
            header: true
        })
    property var treeRows: treeSearch.text.trim() ? filterTree(makeTree(detail, selectedService, {}, true), treeSearch.text) : makeTree(detail, selectedService, collapsed, false)
    property var serviceRows: recordViewState.services || []
    property bool groupedTables: true
    property int tablePage: 0
    property string tableQuery: recordSearch.query
    onTableQueryChanged: tablePage=0
    property var tableModel: Shared.workbench.tables(tableViewState, pidFilter, filter, showInvalidSections, recordSearch.query)
    property var rawTableRows: tableModel.sections
    property int logicalTableCount: tableModel.groups.length
    property var tableRows: logicalTableRows()
    onFilterChanged: tablePage = 0
    onPidFilterChanged: tablePage = 0
    onShowInvalidSectionsChanged: tablePage = 0
    onGroupedTablesChanged: tablePage = 0
    onTableModelChanged: {
        let total=groupedTables ? tableModel.groups.length : tableModel.sections.length;
        tablePage=Math.min(tablePage,Math.max(0,Math.ceil(total/100)-1));
    }
    function tableMatches(t) { return Shared.workbench.scope(t,pidFilter,filter); }
    function logicalTableRows() {
        const model=tableModel,sections=model.sections;
        const rowIndex=sections.reduce(function(index,row){index[row.id]=row;return index;},{});
        let total=groupedTables ? model.groups.length : sections.length;
        let start=Math.min(tablePage,Math.max(0,Math.ceil(total/100)-1))*100;
        if(!groupedTables) return sections.slice(start,start+100);
        let out=[];
        model.groups.slice(start,start+100).forEach(function(g) {
            let sections=(g.section_ids || []).map(function(id){return rowIndex[id];}).filter(Boolean).sort(Shared.workbench.sort);
            let first=Shared.workbench.representative(g,sections);
            out.push(Object.assign({},first || g,{group:g,logical:true,hiddenEvidence:!first,sectionRecords:sections}));
            if(expandedTables[g.id]) sections.forEach(function(r) {out.push(Object.assign({},r,{exact:true}));});
        });
        return out;
    }
    function toggleTableGroup(row) {
        let next=Object.assign({},expandedTables); next[row.group.id]=!next[row.group.id]; expandedTables=next;
    }
    property var explorerRows: [{pid:-1,name:"All tables",count:(explorerViewState.table_groups || []).length}].concat((explorerViewState.table_groups || []).reduce(function(out,g) {
        let name=g.name || "Private / other";
        let row=out.find(function(r) {return r.pid===g.pid && r.name===name;});
        if(row) row.count++; else out.push({pid:g.pid,name:name,count:1}); return out;
    },[]).sort(function(a,b) {return a.pid-b.pid || (a.name < b.name ? -1 : a.name > b.name ? 1 : 0);}))
    property string explorerFocusKey: JSON.stringify([-1,"All tables"])
    function explorerKey(row) { return JSON.stringify([row.pid,row.name]); }
    function explorerSelected(row) { return tab === "Tables" && pidFilter === row.pid && filter === (row.pid < 0 ? "" : row.name); }
    function selectExplorer(row) {
        filter = row.pid < 0 ? "" : row.name; pidFilter = row.pid;
        explorerFocusKey = explorerKey(row); tab = "Tables";
    }
    function selectTableFamily(name) {
        filter = name; pidFilter = -1; explorerFocusKey = JSON.stringify([-1,"All tables"]);
    }
    onExplorerRowsChanged: {
        if (!explorerRows.some(function(row) {return explorerKey(row) === explorerFocusKey;})) explorerFocusKey = JSON.stringify([-1,"All tables"]);
    }
    property var tableFamilies: ["All tables"].concat(["PAT","PMT","SDT","EIT","NIT","CAT","BAT","TDT","TOT"].concat((tableViewState.tables || []).map(function (t) {
        return t.name;
    })).filter(function (name, index, all) {
        return name && name !== "Private / other" && all.indexOf(name) === index;
    })).concat(["Private / other"])
    property var extraPidsValue: parseExtraPids(extraPids.text)
    property var pendingScanOptions: null
    property var completedScanOptions: null
    property string requestedCoverageKey: JSON.stringify([scanMode.currentValue,scanMode.currentValue==="range" ? [scanStart.text,scanEnd.text] : scanMode.currentValue==="full" ? null : [scanBudgetUnit.currentIndex,scanBudget.text]])
    property string pendingCoverageKey: ""
    property string completedCoverageKey: ""
    property var sourceScanOptions: ({standards:standardChoice.currentValue,default_charset:defaultCharset.text.trim(),extra_pids:extraPidsValue})
    property string scanOptionsSummary: Shared.workbench.scanOptionsSummary(sourceScanOptions)
    property bool scanOptionsChanged: !!analysisState.complete && completedScanOptions !== null && Shared.workbench.scanOptionsKey(sourceScanOptions) !== Shared.workbench.scanOptionsKey(completedScanOptions) || !!analysisState.complete && !!completedCoverageKey && requestedCoverageKey!==completedCoverageKey
    function parseExtraPids(text) {
        let values = text.trim() ? text.trim().split(/[\s,]+/) : [];
        let result = [];
        for (let value of values) {
            if (!/^(?:0x[0-9a-f]+|[0-9]+)$/i.test(value))
                return null;
            let pid = Number(value);
            if (!Number.isInteger(pid) || pid < 0 || pid > 8191)
                return null;
            if (result.indexOf(pid) < 0)
                result.push(pid);
        }
        return result;
    }
    property var specificationLinks: collectReferences(detail)
    function collectReferences(section) {
        let result = [];
        function collect(value) {
            if (!value)
                return;
            ;
            (value.references || []).forEach(function (reference) {
                if (typeof reference.url === "string" && /^https:\/\/[^\/\s@]+(?:\/|$)/.test(reference.url) && !result.some(function (existing) {
                    return existing.url === reference.url;
                }))
                    result.push(reference);
            });
            (value.children || []).forEach(collect);
        }
        collect(section);
        collect(section.native_table);
        (section.descriptors || []).forEach(function (descriptor) {
            collect(descriptor);
            collect(descriptor.native);
        });
        return result;
    }
    property var eventRows: recordViewState.events || []
    property var issues: recordViewState.diagnostics || []
    property var issueCounts: Shared.workbench.issueCounts(issues)
    property var unfilteredRows: tab === "Services" ? serviceRows : tab === "Tables" ? tableRows : tab === "EPG" ? eventRows : tab === "Changes" ? (comparison.changes || []) : issues
    property var rows: unfilteredRows.filter(function (row) {
        return tab === "Tables" ? true : tab === "Changes" ? Shared.workbench.comparisonMatches(row,comparisonFilters) && searchTerms(recordSearch.query).every(function (term) { return JSON.stringify(row).toLowerCase().indexOf(term) >= 0; }) : matchesRecord(row, recordSearch.query);
    })
    property bool selectionHidden: !!selected && !(tab === "Tables" ? rawTableRows : rows).some(function (row) {
        if (tab === "Changes")
            return !!selectedChange && row.kind === selectedChange.kind && row.key === selectedChange.key;
        return tab === "Services" ? row.source_id === selected && row.id === selectedService : (row.source_id || row.id) === selected;
    })
    function searchTerms(text) {
        return text.toLowerCase().trim().split(/\s+/).filter(function (term) {
            return !!term;
        });
    }
    function matchesRecord(row, text) {
        return Shared.workbench.matches(row,text);
    }

    function filterTree(allRows, text) {
        let terms = searchTerms(text), keep = {}, matched = {}, ancestors = [];
        allRows.forEach(function (row, index) {
            while (ancestors.length && allRows[ancestors[ancestors.length - 1]].depth >= row.depth)
                ancestors.pop();
            let value = (row.label + " " + row.value).toLowerCase();
            if (ancestors.some(function(parent) { return !!matched[parent]; }) || terms.every(function (term) {
                return value.indexOf(term) >= 0;
            })) {
                keep[index] = true; matched[index] = true;
                ancestors.forEach(function (parent) {
                    keep[parent] = true;
                });
            }
            ancestors.push(index);
        });
        return allRows.filter(function (row, index) {
            return !!keep[index];
        });
    }
    property int autoDelay: Number(core.env("SHOWPSISI_AUTO_DELAY_MS") || 0)
    property bool inspected: false
    property var searchChecks: ({})
    property bool historyCutoffVerified: false
    property int testStep: 0
    onTestStepChanged: core.mark("test_step_" + testStep)
    function num(n) {
        return Number(n || 0).toLocaleString(Qt.locale("en_US"), "f", 0);
    }
    function hex(n, digits) {
        return n === null || n === undefined ? "—" : "0x" + Number(n).toString(16).toUpperCase().padStart(digits || 4, "0");
    }
    function explanation(key) {
        return ({
                TSDT: "Transport Stream Description Table",
                ATSC_EIT: "Event Information Table · ATSC PSIP",
                AEIT: "Aggregate Event Information Table · ATSC",
                AETT: "Aggregate Extended Text Table · ATSC",
                DET: "Data Event Table · ATSC",
                DST: "Data Service Table · ATSC",
                LTST: "Long Term Service Table · ATSC",
                NRT: "Network Resources Table · ATSC",
                SVCT: "Satellite Virtual Channel Table · ATSC",
                DCCT: "Directed Channel Change Table · ATSC",
                DCCSCT: "Directed Channel Change Selection Code Table · ATSC",
                AMT: "Address Map Table · ISDB",
                DCT: "Download Control Table · ISDB",
                DLT: "Download Table · ISDB",
                ERT: "Event Relation Table · ISDB",
                ITT: "Index Transmission Information Table · ISDB",
                LDT: "Linked Description Table · ISDB",
                LIT: "Local Event Information Table · ISDB",
                NBIT: "Network Board Information Table · ISDB",
                PCAT: "Partial Content Announcement Table · ISDB",
                SDTT: "Software Download Trigger Table · ISDB",
                CIT: "Content Identifier Table · DVB",
                INT: "IP/MAC Notification Table · DVB",
                RCT: "Related Content Table · DVB",
                RNT: "Resolution Provider Notification Table · DVB",
                SAT: "Satellite Access Table · DVB",
                SGT: "Service Guide Table · SES Astra",
                UNT: "Update Notification Table · DVB",
                DFIT: "Downloadable Font Information Table · DVB",
                MPE_FEC: "Multi-Protocol Encapsulation Forward Error Correction · DVB",
                MPE_IFEC: "Multi-Protocol Encapsulation Inter-burst Forward Error Correction · DVB",
                container_table: "Container Table · DVB TV-Anytime",
                DSMCC_download_data_message: "DSM-CC Download Data Message · download data blocks",
                DSMCC_user_to_network_message: "DSM-CC User-to-Network Message · download control",
                DSMCC_stream_descriptors_table: "DSM-CC Stream Descriptors Table",
                cable_emergency_alert_table: "Cable Emergency Alert Table · SCTE",
                discontinuity_information_table: "Discontinuity Information Table · DVB",
                selection_information_table: "Selection Information Table · DVB",
                splice_information_table: "Splice Information Table · SCTE-35",
                DTMB: "Digital Terrestrial Multimedia Broadcasting · signalling context",
                BAT: "Bouquet Association Table",
                RST: "Running Status Table",
                AIT: "Application Information Table",
                VCT: "Virtual Channel Table · ATSC",
                DIT: "Discontinuity Information Table",
                SIT: "Selection Information Table",
                PAT: "Program Association Table",
                PMT: "Program Map Table",
                SDT: "Service Description Table",
                EIT: "Event Information Table",
                NIT: "Network Information Table",
                CAT: "Conditional Access Table",
                EPG: "Electronic Program Guide",
                PID: "Packet identifier",
                SID: "Service identifier",
                LCN: "Logical channel number",
                CRC: "Cyclic redundancy check",
                PDS: "Private data specifier",
                PSI: "Program Specific Information",
                SI: "Service Information",
                ATSC: "Advanced Television Systems Committee",
                DVB: "Digital Video Broadcasting",
                ISDB: "Integrated Services Digital Broadcasting",
                MGT: "Master Guide Table",
                TVCT: "Terrestrial Virtual Channel Table",
                CVCT: "Cable Virtual Channel Table",
                STT: "System Time Table",
                ETT: "Extended Text Table",
                RRT: "Rating Region Table",
                BIT: "Broadcaster Information Table",
                CDT: "Common Data Table",
                TOT: "Time Offset Table",
                TDT: "Time and Date Table",
                "All tables": "Every observed section, grouped by family",
                "Private / other": "Observed sections outside the known PSI / SI families; private meaning is never inferred from a tag alone"
            })[key] || key;
    }
    function tableLabel(name) {
        return ({
            "DSMCC_user_to_network_message": "DSM-CC U-N",
            "DSMCC_download_data_message": "DSM-CC Data",
            "DSMCC_stream_descriptors_table": "DSM-CC SDT",
            "container_table": "DVB Container",
            "splice_information_table": "SCTE-35",
            "cable_emergency_alert_table": "SCTE EAS",
            "discontinuity_information_table": "DIT",
            "selection_information_table": "SIT"
        })[name] || name;
    }
    function isList(value) {
        // QVariantList arrives as a QML sequence, not a JavaScript Array.
        return Array.isArray(value) || (value !== null && typeof value === "object" && Number.isInteger(value.length) && value.length >= 0 && typeof value.forEach === "function" && typeof value.splice === "function");
    }
    function nativeWarningsText() { return inspectorNotes.join("\n"); }
    function valueText(key, value) {
        if (value === null || value === undefined)
            return "—";
        if (typeof value !== "number")
            return String(value);
        if (/private_data_specifier|pds|crc/i.test(key))
            return hex(value, 8) + " (" + value + ")";
        if (/tag|table_id|^type$|stream_type|service_type/.test(key))
            return hex(value, 2) + " (" + value + ")";
        if (/pid|_id$|^id$/.test(key))
            return hex(value, 4) + " (" + value + ")";
        return String(value);
    }
    function makeTree(section, sid, hidden, expandAll) {
        if(!section.id) return [];
        core.mark("tree_model_begin");let result=[];
        function visit(node,parent,depth) {
            let canonical=parent ? parent+"/"+node.id : node.id;
            // Keep stable native diagnostic IDs while rendering the shared tree.
            let path=canonical.replace(/^section\//,"").replace(/^assembly(?=\/|$)/,"provenance");
            let branch=!!node.children;
            let closed=branch && !expandAll && (hidden[path]===undefined ? !Shared.workbench.defaultOpen(canonical) : !!hidden[path]);
            result.push({path:path,label:node.label,value:node.value || "",depth:depth,branch:branch,closed:closed,kind:node.kind || "meta",reference:node.reference || null});
            if(branch && !closed) node.children.forEach(function(child){visit(child,canonical,depth+1);});
        }
        let referenceState=activeInspectionRef && activeInspectionRef.at_packet!==currentPacket() || selectedChange && selectedChange[comparisonSide] && selectedChange[comparisonSide].at_packet!==currentPacket() ? null : analysisState;
        visit(Shared.workbench.structure(section,evidenceScope.toLowerCase(),sid,referenceState),"",0);
        core.mark("tree_model_end");return result;
    }
    function toggle(path) {
        if (treeSearch.text.trim())
            return;
        let next = Object.assign({}, collapsed);
        let row = treeRows.find(function (r) {
            return r.path === path;
        });
        next[path] = row ? !row.closed : !next[path];
        collapsed = next;
    }
    function revealInspectorDetail(item) {
        Qt.callLater(function() {
            let point=item.mapToItem(inspectorDetailsColumn,0,0);
            inspectorDetailsScroll.contentItem.contentY=Math.max(0,Math.min(point.y,Math.max(0,inspectorDetailsScroll.contentHeight-inspectorDetailsScroll.availableHeight)));
        });
    }
    function rememberLayout() {
        if (!layoutReady)
            return;
        let value = { version: 1, explorer: explorerPane.width,
            inspector: pendingInspectorSize >= 0 ? pendingInspectorSize : inspectorPane.width,
            timeline: pendingTimelineSize >= 0 ? pendingTimelineSize : timelinePane.height };
        value.inspectorDetails = {identity:identityOpen,crc:crcOpen,arrival:arrivalOpen,sections:sectionGroupOpen,scope:scopeOpen,warnings:warningsOpen};
        if (!core.saveLayout(value)) {
            showMessage("Layout could not be saved. The current layout remains usable.", "warning");
        } else {
            pendingInspectorSize = -1;
            pendingTimelineSize = -1;
        }
    }
    function resetLayout() {
        identityOpen=false;crcOpen=false;arrivalOpen=false;sectionGroupOpen=false;scopeOpen=false;warningsOpen=false;
        layoutSaveTimer.stop();
        pendingInspectorSize = -1;
        pendingTimelineSize = -1;
        explorerPane.SplitView.preferredWidth = 180;
        inspectorPane.SplitView.preferredWidth = 520;
        timelinePane.SplitView.preferredHeight = 105;
        let saved=core.resetLayout();
        showMessage(saved ? "Default layout restored" : "Layout reset for this session; preferences could not be saved.", saved ? "info" : "warning");
    }
    function resizeInspector(delta) {
        pendingInspectorSize = Math.max(330, Math.min(workspace.width - explorerPane.width - 322,
            (pendingInspectorSize >= 0 ? pendingInspectorSize : inspectorPane.width) + delta));
        inspectorPane.SplitView.preferredWidth = pendingInspectorSize;
        layoutSaveTimer.restart();
    }
    function resizeTimeline(delta) {
        pendingTimelineSize = Math.max(105, Math.min(350, verticalWorkspace.height - 306,
            (pendingTimelineSize >= 0 ? pendingTimelineSize : timelinePane.height) + delta));
        timelinePane.SplitView.preferredHeight = pendingTimelineSize;
        layoutSaveTimer.restart();
    }
    function axisLabel(packet) {
        let rate=analysisState.timing?.seconds_per_packet;
        return rate !== null && rate !== undefined && rate > 0 ? (packet * rate).toFixed(3) + " s" : "#" + num(packet);
    }
    function currentPacket() {
        return analysisState.selected_packet === null || analysisState.selected_packet === undefined ? Math.max(0, Number(analysisState.packets || 1) - 1) : analysisState.selected_packet;
    }
    function openComparison() {
        tab = "Changes";
        if (!fromPacket.text && analysisState.complete) {
            fromPacket.text = String((analysisState.history || []).length ? analysisState.history[0].last_packet : 0);
            toPacket.text = String(currentPacket());
        }
        fromPacket.forceActiveFocus();
    }
    function packetCovered(packet) { return !partialResults || (analysisState.coverage.ranges || []).some(function(r){return packet>=r.start_packet && packet<r.end_packet;}); }
    function validPacket(text) {
        return /^\d+$/.test(text) && Number.isSafeInteger(Number(text)) && Number(text) < Number(analysisState.packets || 0) && packetCovered(Number(text));
    }
    function focusComparisonAction() {
        tab = "Changes";
        Qt.callLater(function() { comparisonRun.highlighted = true; if (comparisonRun.enabled) comparisonRun.forceActiveFocus(); });
    }
    function compareSnapshots(offset) {
        if (!backendReady || core.comparing || !analysisState.complete || !validPacket(fromPacket.text) || !validPacket(toPacket.text))
            return;
        comparison = {};
        if (selectedChange)
            restoreComparisonWorkspace();
        selectedChange = null;
        comparisonError = "";
        recordSearch.clear();
        core.send("diff_snapshots", {from_packet: Number(fromPacket.text), to_packet: Number(toPacket.text), kind: changeKind.currentValue, offset: offset || 0, limit: 100});
    }
    function changeValue(row) {
        return (row.after || row.before || {}).value || {};
    }
    function changeTitle(row) {
        let value = changeValue(row);
        return row.change.toUpperCase() + " · " + row.kind + " · " + (value.name || value.title || (row.kind === "tables" ? "Table " + hex(value.table_id, 2) : "SID " + hex(value.service_id === undefined ? value.id : value.service_id)));
    }
    function changeFields(row, full) {
        return Shared.workbench.comparisonRows(row,{}).map(function(field){return Shared.workbench.comparisonFieldText(field);}).join("\n");
    }
    function changeColor(kind) { return kind === "added" ? addedColor : kind === "removed" ? removedColor : kind === "changed" ? changedColor : muted; }
    function restoreComparisonWorkspace() {
        let saved = comparisonWorkspace;
        comparisonWorkspace = null;
        selectedChange = null;
        if (saved && saved.source === analysisState.source && saved.at === analysisState.selected_packet && saved.id) {
            inspect(saved.id, saved.sid);
            collapsed = saved.collapsed;
            treeSearch.text = saved.search;
            inspectorView = saved.view;
            evidenceScope = saved.scope;
        } else defaultInspect();
    }
    function comparisonPresets() {
        return [{label:"Choose history…",packet:-1}, {label:"Current · #"+num(currentPacket()),packet:currentPacket()},
            {label:"Start · #0",packet:0}, {label:"Latest · #"+num(Number(analysisState.packets || 1)-1),packet:Number(analysisState.packets || 1)-1}]
            .concat((analysisState.table_history || []).map(function(h) {return {label:Shared.workbench.historyText(h),packet:h.at_packet};}));
    }
    function inspectChange(row, sideName, evidenceIndex) {
        if (!backendReady) return;
        topologyEvidenceRef=null;topologyResolution={};
        let side = row && row[sideName];
        if (!side || !(side.evidence || []).length)
            return;
        let index = evidenceIndex === undefined ? 0 : evidenceIndex;
        let evidence = side.evidence[index];
        if (!evidence) return;
        if (!comparisonWorkspace) comparisonWorkspace = {id:selected, sid:selectedService, source:analysisState.source,
            at:analysisState.selected_packet, collapsed:collapsed, search:treeSearch.text, view:inspectorView, scope:evidenceScope};
        selectedChange = row;
        comparisonSide = sideName;
        comparisonEvidenceIndex = index;
        inspect(evidence.id, row.kind === "services" && evidence.table_id === 0x42 ? side.value.id : -1, side.at_packet);
        notice = "Inspecting " + (sideName === "before" ? "A" : "B") + " at packet " + num(side.at_packet) + ". The current workbench snapshot is unchanged.";
    }
    function inspect(id, sid, atPacket) {
        clearProtocolSource();
        if (!backendReady || !analysisState.complete) return;
        if (!id) {
            notice = "Aggregate diagnostic: no individual section is indexed.";
            return;
        }
        if(topologyEvidenceRef && id!==topologyEvidenceRef.section_id){topologyEvidenceRef=null;topologyResolution={};}
        core.mark("inspect_selection_begin");selected = id;
        selectedService = sid === undefined ? -1 : sid;core.mark("inspect_selection_end");
        preview = {};
        collapsed = {
            header: true
        };
        let params = {
            id: id
        };
        if (atPacket !== undefined && atPacket !== null)
            params.at_packet = atPacket;
        else if (analysisState.selected_packet !== undefined && analysisState.selected_packet !== null)
            params.at_packet = analysisState.selected_packet;
        core.mark("inspect_send_begin");core.send("inspect", params);core.mark("inspect_send_end");
    }
    property var pendingServiceSource:null
    function openServiceSource(id,path,cutoff){pendingServiceSource={id:id,path:path,cutoff:cutoff};inspect(id,-1,cutoff);}
    function openCarousel(sourceId){documentMode=true;advancedMode=false;documentWorkspace.open('carousel','carousel@'+analysisState.selected_packet,documentScope()+' - DSM-CC / OC Files',{source_id:sourceId||detail.id,_view_state:JSON.parse(JSON.stringify(analysisState))},false);}
    function openServices(service){documentMode=true;advancedMode=false;var key=service?service.onid+':'+service.ts_id+':'+service.id:'all';documentWorkspace.open('service',key+'@'+analysisState.selected_packet,documentScope()+' - Services / EPG',{service:service,_view_state:JSON.parse(JSON.stringify(analysisState))},false);}
    function documentScope(cutoff){var at=cutoff===undefined?analysisState.selected_packet:cutoff;return String(analysisState.source||'Transport stream').split(/[\\/]/).pop()+' [analysis '+(analysisState.analysis_revision||analysisState.revision||0)+', '+(at==null?'latest':'packet '+at)+']';}
    function openPacket(pid,index){documentMode=true;advancedMode=false;documentWorkspace.open('packet',String(pid),documentScope()+' - Packet Explorer'+(pid<0?'':' PID '+hex(pid)),{pid:pid,index:index||0},false);}
    function openDocument(kind,duplicate){
        var payload=kind==='summary'?{}:JSON.parse(JSON.stringify(detail));if(kind!=='summary'){payload._view_state=JSON.parse(JSON.stringify(analysisState));payload._view_state.selected_packet=detail.native_table_at_packet;}
        var title=documentScope(kind==='summary'?undefined:detail.native_table_at_packet)+' - '+(kind==='summary'?'Summary':kind==='decoded'?'Native Decode':detail.id?detail.name+' PID '+hex(detail.pid):'SI Inspector');
        documentWorkspace.open(kind,kind==='summary'?'summary':(detail.id||'empty')+'@'+detail.native_table_at_packet,title,payload,!!duplicate);
    }
    property string documentIdentity:(analysisState.source||'')+'|'+(analysisState.analysis_revision||analysisState.revision||'')
    onDocumentIdentityChanged:{pendingServiceSource=null;if(documentWorkspace)documentWorkspace.reset(documentIdentity)}
    onDetailChanged:if(documentMode&&detail.id&&!advancedMode&&!metadataMode)Qt.callLater(function(){if(detail.id){openDocument('si');if(pendingServiceSource&&pendingServiceSource.id===detail.id){var source=pendingServiceSource;pendingServiceSource=null;documentWorkspace.focusSection(source.id,source.path,source.cutoff);}}})
    Shortcut {sequence:'Ctrl+F4';enabled:documentMode&&!metadataMode&&!advancedMode;onActivated:documentWorkspace.close()}
    Shortcut {sequence:'Ctrl+Tab';enabled:documentMode&&!metadataMode&&!advancedMode;onActivated:documentWorkspace.cycle(false)}
    Shortcut {sequence:'Ctrl+Shift+Tab';enabled:documentMode&&!metadataMode&&!advancedMode;onActivated:documentWorkspace.cycle(true)}
    function classicState(){return {available:backendReady,busy:core.busy,cancelling:core.cancelling,canPause:core.busy&&!core.loadingResults,paused:core.paused,hasInput:!!(source&&source.text.trim()),complete:!!analysisState.complete,native:true,exporting:exporting||core.exportPending,toolbar:classicToolbarVisible,status:classicStatusVisible,tree:classicTreeVisible,documentCount:documentMode?documentWorkspace.state.items.length:(analysisState.complete?1:0),features:{documents:true,packets:true,bitrate:true,services:true,carousel:true}};}
    function classicCommand(name){
        var state=classicState();if(!Classic.classic.enabled(name,state)){showMessage(Classic.classic.reason(name,state),"warning");return;}
        if(name==='open')fileDialog.open();
        else if(name==='start')scan();
        else if(name==='stop')cancelScan();
        else if(name==='pause')core.pauseAnalysis();
        else if(name==='toolbar')classicToolbarVisible=!classicToolbarVisible;
        else if(name==='status')classicStatusVisible=!classicStatusVisible;
        else if(name==='tree')classicTreeVisible=!classicTreeVisible;
        else if(name==='new'){documentMode=true;openDocument('si',true);}
        else if(name==='decoded'){documentMode=true;openDocument('decoded');}
        else if(name==='packets')openPacket(-1,0);
        else if(name==='carousel')openCarousel();
        else if(name==='services')openServices(null);
        else if(name==='bitrate'){documentMode=true;advancedMode=false;documentWorkspace.open('statistics','statistics',documentScope()+' - Bitrate / Timing',{},false);}
        else if(name==='close')documentWorkspace.close();
        else if(['cascade','tile','arrange'].indexOf(name)>=0)documentWorkspace.arrange(name);
        else if(name==='summary'){if(documentMode)openDocument('summary');transportSummaryVisible=true;advancedMode=false;}
        else if(name==='configuration'){classicConfigurationVisible=!classicConfigurationVisible;if(classicConfigurationVisible)source.forceActiveFocus();}
        else if(name==='advanced'){transportSummaryVisible=false;advancedMode=true;}
        else if(name==='dvbi')inputKind='dvbi';
        else if(name==='about')updateDialog.open();
        else if(name==='index')classicHelpDialog.open();
        else if(name==='messages')messagesDialog.open();
        else if(name==='diagnostics'){var result=uiAgent.saveBundle();showMessage(result,result.indexOf('Diagnostics failed:')===0?'error':'info');}
        else if(name==='exit')win.close();
    }
    Timer {interval:500;running:!metadataMode&&!advancedMode&&classicStatusVisible;repeat:true;onTriggered:classicLocks=core.lockState()}
    Dialog {
        id:classicHelpDialog;title:'ShowPsiSi Help';modal:true;width:Math.min(600,win.width-40);anchors.centerIn:parent;standardButtons:Dialog.Close
        contentItem:Label {text:'Open a transport stream, then choose Analyzer → Start. Programs and PSI Packets lead to table fields and original bytes. Single-click selects; double-click text or click +/− to expand. F6 / Shift+F6 moves between panes. Alt+Left returns. Card Configuration opens source and scan options. Advanced workspace retains editing, topology, history and DVB-I. Disabled commands describe features not yet available.';wrapMode:Text.WordWrap;color:'#000';padding:14}
        background:Rectangle{color:'#efefef';border.color:'#808080'}
    }
    function openExportDialog() {
        if (!exportButton.enabled || saveDialog.visible) return;
        let format = exportFormat.currentValue;
        saveIntent = {token: preview.token, source: analysisState.source, format: format,
                      at: analysisState.selected_packet};
        saveDialog.currentFolder = lastExportFolder;
        saveDialog.selectedFile = core.suggestedExport(lastExportFolder, analysisState.source, format);
        exportFeedback = "";
        saveDialog.open();
    }
    function acceptExportDestination(url) {
        let intent = saveIntent;
        saveIntent = {};
        if (!backendReady || !analysisState.complete || exporting || !intent.token ||
                intent.token !== preview.token || preview.after !== renameName.text || preview.service_id !== editService.currentValue ||
                intent.source !== analysisState.source || intent.at !== analysisState.selected_packet) {
            exportFeedback = "The preview changed. Preview the edit again before exporting.";
            return;
        }
        let destination = core.exportDestination(url, intent.format);
        if (destination.error) {
            exportFeedback = destination.error;
            showMessage(exportFeedback, "error");
            exportButton.forceActiveFocus();
            return;
        }
        let params = {path: destination.path, format: intent.format, preview_token: intent.token};
        if (intent.at !== null && intent.at !== undefined) params.at_packet = intent.at;
        exporting = true;
        exportFeedback = "Writing a new " + intent.format.toUpperCase() + " file and manifest…";
        core.mark("export_requested");
        core.send("export", params);
    }
    function clearWorkspaceIntentions() {
        clearProtocolSource();
        clearTopology();
        inspected = false;
        selected = "";
        selectedService = -1;
        snapshotTarget = "";
        snapshotTargetService = -1;
        preview = {};
        comparison = {};
        selectedChange = null;
        comparisonFilters = [];
        comparisonWorkspace = null;
        previewIntent = {};
        comparisonError = "";
        fromPacket.clear();
        toPacket.clear();
        saveIntent = {};
        saveDialog.close();
        exporting = false;
        exportFeedback = "";
        renameDialog.close();
        specificationDialog.close();
        apiDialog.close();
    }
    function cancelScan() {
        if (!core.available || !core.busy || core.cancelling) return;
        core.cancelAnalysis();
        notice = core.busy ? "Cancelling scan… Waiting for the worker to stop." : "Result loading stopped. Analyze again to load a complete workspace.";
    }
    function scan() {
        if (metadataMode || !backendReady || !source.text.trim() || extraPidsValue === null || !quickOptionsValid)
            return;
        recentMenu.close();
        if(warningMessage.indexOf("Scan cancelled")===0){warningMessage="";warningRepeat=0;}
        notice = "Scanning source…";
        pendingCoverageKey=requestedCoverageKey;
        pendingScanOptions = {standards:standardChoice.currentValue,default_charset:defaultCharset.text.trim(),extra_pids:extraPidsValue.slice()};
        rememberSource(source.text.trim());
        let params={
            path: source.text.trim(),
            standards: pendingScanOptions.standards,
            default_charset: pendingScanOptions.default_charset,
            extra_pids: pendingScanOptions.extra_pids,
            scan_mode: scanMode.currentValue
        };
        if(scanMode.currentValue==="range"){params.start_packet=Number(scanStart.text);params.end_packet=Number(scanEnd.text);}
        if(scanMode.currentValue==="prefix" || scanMode.currentValue==="distributed"){
            params[scanBudgetUnit.currentIndex===0 ? "sample_percent" : "max_packets"]=Number(scanBudget.text);
            if(scanMode.currentValue==="distributed")params.window_count=4;
        }
        core.send("analyze",params);
    }
    function focusNextRegion(backwards) {
        let regions=[sourceBar,explorerPane,recordPane,inspectorPane], current=-1;
        for(let item=win.activeFocusItem;item;item=item.parent){let index=regions.indexOf(item);if(index>=0){current=index;break;}}
        let next=current<0 ? (backwards ? 3 : 0) : (current+(backwards ? -1 : 1)+4)%4;
        if(next===0){if(source.enabled)source.forceActiveFocus();else scanOptionsToggle.forceActiveFocus();}
        else if(next===1)explorerList.forceActiveFocus();
        else if(next===2){if(tab==="Topology")topologyList.forceActiveFocus();else recordList.forceActiveFocus();}
        else if(topologySummary)topologySourcesList.forceActiveFocus();
        else {inspectorView="Structure";tree.forceActiveFocus();}
    }
    function activateHistory(entry) {
        selectExplorer({pid:entry.pid,name:entry.name});
        if(!entry.valid) showInvalidSections=true;
        snapshot(entry.at_packet,entry.id);
    }
    function snapshot(packet, id, sid) {
        if(packet>=0 && !packetCovered(packet)){showMessage("Unscanned interval: reception and table state are unknown here. Run a full scan to inspect it.","warning");return;}
        clearProtocolSource();
        if (!backendReady || !analysisState.complete) return;
        topologyEvidenceRef=null;topologyResolution={};topologyLoading=false;topologyOrigin=null;topologyBackStack=[];topologyCutoff=null;topologyScopeLabel="Current observation";
        selectedChange = null;
        comparisonWorkspace = null;
        previewIntent = {};
        renameDialog.close();
        snapshotTarget = id || "";
        snapshotTargetService = sid === undefined ? -1 : sid;
        selected = "";
        selectedService = -1;
        preview = {};
        core.send("query", packet < 0 ? {} : {
            at_packet: packet
        });
        notice = packet < 0 ? "Latest observed state" : "Snapshot at packet " + num(packet);
    }
    function defaultInspect() {
        if (!backendReady || !analysisState.complete) return;
        if (!advancedMode) {
            let first=(analysisState.tables || []).find(function(r){return r.name==="PAT" && r.valid;}) || (analysisState.tables || [])[0];
            if(first)inspect(first.id,-1);
            return;
        }
        let first = serviceRows[0];
        if (first) {
            inspect(first.source_id, first.id);
            return;
        }
        let firstTable = (analysisState.tables || []).find(function(r) { return showInvalidSections || r.crc?.status !== "invalid"; });
        if (!firstTable && (analysisState.tables || []).length) tab="Tables";
        if (firstTable) {
            if (tab === "Services")
                tab = "Tables";
            inspect(firstTable.id);
        }
    }
    function chosenService() {
        return (detail.services || []).find(function (s) {
            return s.id === selectedService;
        }) || (detail.services || [])[0];
    }
    function activate(row) {
        if (tab === "Tables" && row.logical) {
            toggleTableGroup(row);
            if(row.hiddenEvidence) { notice="Bad-CRC evidence hidden. Enable Bad CRC to inspect."; return; }
        }
        if (tab === "Changes") {
            inspectChange(row, row.after ? "after" : "before");
            return;
        }
        selectedChange = null;
        inspect(tab === "Services" || tab === "EPG" ? row.source_id : row.id, tab === "Services" ? row.id : undefined);
    }
    function pidList(pids,status) { return status === "PMT unavailable" || !pids ? "unknown" : pids.length ? pids.map(function(p) {return hex(p);}).join(", ") : "none"; }
    function rowTitle(row) {
        if (tab === "Changes")
            return changeTitle(row);
        return tab === "Services" ? (row.logical_channel_number === null ? "—" : row.logical_channel_number) + "  " + (row.name || "Unnamed service") : tab === "Tables" ? (row.exact ? Shared.workbench.wireSectionText(row) + " · " : "") + tableLabel(row.name) + " · PID " + hex(row.pid) + " · TID " + hex(row.table_id, 2) + (row.valid === false ? " · INVALID" : "") : tab === "EPG" ? eventTitle(row) : row.code + (row.aggregate ? " · aggregate" : " · PID " + hex(row.pid));
    }
    function rowSubtitle(row) {
        if (tab === "Changes")
            return (row.changed_fields || []).join(", ") || "Presence changed · select to inspect source evidence";
        return tab === "Services" ? "SID " + hex(row.id) + " · PMT " + hex(row.pmt_pid) : tab === "Tables" && row.logical ? Shared.workbench.groupText(row.group) + " · " + arrivalText(row.group) + (row.hiddenEvidence ? " · Bad-CRC evidence hidden" : "") : tab === "Tables" ? Shared.workbench.wireVersionText(row) + " · " + Shared.workbench.wireSectionText(row) + " · " + row.bytes + " B · " + num(row.count) + " observations · " + crcText(row) : tab === "EPG" ? "SID " + hex(row.service_id) + " · " + row.start + " UTC · " + row.duration_seconds / 60 + " min" : (row.detail || "");
    }
    component PlainLabel: Label {
        textFormat: Text.PlainText
    }
    component ComparisonDiff: Column {
        id: diff
        property var change: null
        property var expanded: ({})
        // Compact lists cap each change at a few field lines so a whole row stays visible.
        property int maxRows: 0
        property bool showAll: false
        // Capped lists also keep each field on one elided line; the tooltip carries the full text.
        readonly property bool singleLine: maxRows > 0
        readonly property var allRows: Shared.workbench.comparisonRows(diff.change,diff.expanded)
        readonly property int hiddenRows: maxRows > 0 && !showAll ? Math.max(0, allRows.length - maxRows) : 0
        // Toggling a nested field also selects its change, like the rest of the row.
        signal fieldActivated()
        spacing: 2
        onChangeChanged: { expanded = ({}); showAll = false; }
        function toggleField(path) {
            let next=Object.assign({},expanded);next[path]=!next[path];expanded=next;
            Qt.callLater(function(){for(let i=0;i<diffRows.count;i++){let item=diffRows.itemAt(i);if(item && item.modelData.path===path){item.focusBranch();break;}}});
        }
        Repeater {
            id: diffRows
            model: diff.hiddenRows ? diff.allRows.slice(0, diff.maxRows) : diff.allRows
            delegate: Item {
                required property var modelData
                width: diff.width
                height: branch.visible ? branch.implicitHeight : scalar.implicitHeight
                function focusBranch() { branch.forceActiveFocus(); }
                Action {
                    id: branch
                    visible: modelData.children.length > 0
                    width: parent.width
                    leftPadding: 4 + modelData.depth * 12
                    rightPadding: 4
                    implicitHeight: Math.max(24,contentItem.implicitHeight + 8)
                    checkable: true
                    checked: !!diff.expanded[modelData.path]
                    text: (checked ? "▾ " : "▸ ") + Shared.workbench.comparisonFieldText(modelData)
                    Accessible.name: Shared.workbench.comparisonFieldText(modelData)
                    Accessible.description: Shared.workbench.comparisonHelp(modelData.key) + (checked ? ", expanded" : ", collapsed")
                    contentItem: PlainLabel { text:branch.text; color:changeColor(modelData.change); wrapMode:diff.singleLine ? Text.NoWrap : Text.WrapAnywhere; elide:diff.singleLine ? Text.ElideRight : Text.ElideNone; font.family:"monospace"; font.pixelSize:11 }
                    background: Rectangle { color:branch.hovered ? hoverSurface : "transparent"; border.color:branch.activeFocus ? blue : "transparent"; border.width:branch.activeFocus ? focusWidth : 0; radius:2 }
                    onClicked: { const owner=diff, path=modelData.path; owner.fieldActivated(); owner.toggleField(path); } // toggling rebuilds this delegate
                    SafeTip { visible:anchorHovered; text:(diff.singleLine ? Shared.workbench.comparisonFieldText(modelData) + "
" : "") + Shared.workbench.comparisonHelp(modelData.key) + " · Expand nested A / B fields; array labels are positions" }
                }
                PlainLabel {
                    id: scalar
                    visible: !branch.visible
                    width: parent.width
                    leftPadding: 4 + modelData.depth * 12
                    topPadding: 3
                    bottomPadding: 3
                    text: Shared.workbench.comparisonFieldText(modelData)
                    color: changeColor(modelData.change)
                    wrapMode: diff.singleLine ? Text.NoWrap : Text.WrapAnywhere
                    elide: diff.singleLine ? Text.ElideRight : Text.ElideNone
                    font.family: "monospace"
                    font.pixelSize: 11
                    HoverHandler { id: fieldHover }
                    SafeTip { visible:fieldHover.hovered; text:(diff.singleLine ? scalar.text + "
" : "") + Shared.workbench.comparisonHelp(modelData.key) }
                }
            }
        }
        Action {
            visible: diff.hiddenRows > 0
            width: diff.width
            implicitHeight: 22
            leftPadding: 4
            text: "+" + diff.hiddenRows + (diff.hiddenRows === 1 ? " more field" : " more fields")
            Accessible.name: "Show " + diff.hiddenRows + " more changed fields"
            contentItem: PlainLabel { text:parent.text; color:muted; font.pixelSize:11; verticalAlignment:Text.AlignVCenter }
            onClicked: { const owner=diff; owner.fieldActivated(); owner.showAll=true; }
        }
    }
    component LookupTable: Item {
        id: lookupTable
        property var result: ({})
        property string label: "Lookup result"
        readonly property var presentation: Shared.workbench.lookupResult(result)
        readonly property real keyWidth: width * (presentation.hasSource ? 0.32 : 0.40)
        readonly property real sourceWidth: width * 0.30
        visible: Object.keys(result).length > 0
        Layout.fillWidth: true
        // Width belongs to the containing layout. Do not derive an implicit
        // width from columns whose preferred widths are fractions of this width.
        implicitHeight: lookupContents.implicitHeight
        Accessible.role: Accessible.Table
        Accessible.name: label
        ColumnLayout {
        id: lookupContents
        anchors.left: parent.left
        anchors.right: parent.right
        spacing: 0
        RowLayout {
            Layout.fillWidth: true
            spacing: 8
            PlainLabel { text: "Key"; color: muted; font.bold: true; Layout.preferredWidth: lookupTable.keyWidth; Layout.minimumWidth: 0; Layout.maximumWidth: lookupTable.keyWidth }
            PlainLabel { text: "Value"; color: muted; font.bold: true; Layout.fillWidth: true; Layout.minimumWidth: 0 }
            PlainLabel { text: "Source"; color: muted; font.bold: true; visible: lookupTable.presentation.hasSource; Layout.preferredWidth: lookupTable.sourceWidth; Layout.minimumWidth: 0; Layout.maximumWidth: lookupTable.sourceWidth }
        }
        Repeater {
            model: lookupTable.presentation.rows
            ColumnLayout {
                id: lookupRow
                required property var modelData
                Layout.fillWidth: true
                spacing: 0
                Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: dividerColor }
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8
                    PlainLabel {
                        id: keyCell
                        text: lookupRow.modelData.label
                        Layout.preferredWidth: lookupTable.keyWidth; Layout.minimumWidth: 0; Layout.maximumWidth: lookupTable.keyWidth; Layout.alignment: Qt.AlignTop
                        padding: 4; wrapMode: Text.WrapAnywhere; color: muted; font.pixelSize: 11
                        activeFocusOnTab: true
                        onActiveFocusChanged: if(activeFocus)Qt.callLater(function(){revealMetadataControl(keyCell);})
                        Accessible.name: text
                        Accessible.description: "Raw key: " + lookupRow.modelData.key + (lookupRow.modelData.help ? " · " + lookupRow.modelData.help : "")
                        background: Rectangle { color: surface; border.color: blue; border.width: keyCell.activeFocus ? focusWidth : 0 }
                        HoverHandler { id: keyHover }
                        SafeTip { visible: keyHover.hovered || keyCell.activeFocus; text: keyCell.Accessible.description }
                    }
                    TextArea {
                        id: valueCell
                        text: lookupRow.modelData.value
                        Layout.fillWidth: true; Layout.minimumWidth: 0; Layout.alignment: Qt.AlignTop
                        padding: 4; readOnly: true; selectByMouse: true; activeFocusOnTab: true
                        textFormat: TextEdit.PlainText; wrapMode: TextEdit.WrapAnywhere; font.family: "monospace"; font.pixelSize: 12; color: ink
                        onActiveFocusChanged: if(activeFocus)Qt.callLater(function(){revealMetadataControl(valueCell);})
                        Accessible.name: lookupTable.label + " · " + lookupRow.modelData.label
                        background: Rectangle { color: surface; border.color: blue; border.width: valueCell.activeFocus ? focusWidth : 0 }
                    }
                    TextArea {
                        id: sourceCell
                        visible: lookupTable.presentation.hasSource
                        text: lookupRow.modelData.source || "—"
                        Layout.preferredWidth: lookupTable.sourceWidth; Layout.minimumWidth: 0; Layout.maximumWidth: lookupTable.sourceWidth; Layout.alignment: Qt.AlignTop
                        padding: 4; readOnly: true; selectByMouse: true; activeFocusOnTab: true
                        textFormat: TextEdit.PlainText; wrapMode: TextEdit.WrapAnywhere; font.pixelSize: 11; color: muted
                        onActiveFocusChanged: if(activeFocus)Qt.callLater(function(){revealMetadataControl(sourceCell);})
                        Accessible.name: "Source for " + lookupRow.modelData.label
                        Accessible.description: lookupRow.modelData.sourceTip
                        background: Rectangle { color: surface; border.color: blue; border.width: sourceCell.activeFocus ? focusWidth : 0 }
                        HoverHandler { id: sourceHover }
                        SafeTip { visible: sourceHover.hovered || sourceCell.activeFocus; text: lookupRow.modelData.sourceTip }
                    }
                }
            }
        }
    }
    }
    component SafeTip: ToolTip {
        id: tip
        property var anchorControl: parent
        // Popup.parent can clear before a delegate's bindings are torn down.
        // Keep all parent-derived values safe throughout that detached interval.
        readonly property bool anchorHovered: !!(anchorControl && anchorControl.hovered)
        readonly property string anchorText: anchorControl ? String(anchorControl.text || "") : ""
        contentItem: PlainLabel {
            objectName: "plainTooltipContent"
            text: tip.text
            color: ink
            wrapMode: Text.Wrap
        }
        background: Rectangle {
            color: raised
            border.color: dividerColor
            radius: 2
        }
    }
    component PaletteInput: FieldInput {
        id: paletteField
        // Prefixes leave the normal record/topology filter unchanged.
        property string query: ""
        Accessible.role: Accessible.ComboBox
        Accessible.description: "Search records · > commands · # PID: Packet Identifier / SID: Service Identifier. " + (paletteInput===paletteField ? paletteStatus + ". " + (paletteRows[paletteIndex] ? paletteRows[paletteIndex].description + ". " + paletteRows[paletteIndex].reason : "") : "")
        onTextChanged: {
            if(/^[>#]/.test(text.replace(/^\s+/,""))){
                paletteInput=paletteField;paletteIndex=0;
                Qt.callLater(function(){if(paletteField.activeFocus && paletteInput===paletteField)commandPalette.open();});
            }else {query=text;if(paletteInput===paletteField)closePalette(false);}
        }
        onActiveFocusChanged: {
            if(activeFocus){paletteReturnFocus=searchPreviousFocus;if(/^[>#]/.test(text.replace(/^\s+/,""))){paletteInput=paletteField;commandPalette.open();}}
            else if(paletteInput===paletteField)closePalette(false);
        }
        Keys.onPressed: function(event) {
            if(paletteInput!==paletteField || event.modifiers & (Qt.ControlModifier | Qt.AltModifier | Qt.MetaModifier))return;
            if(event.key===Qt.Key_Up || event.key===Qt.Key_Down){
                event.accepted=true;if(paletteRows.length){paletteIndex=(paletteIndex+(event.key===Qt.Key_Up?-1:1)+paletteRows.length)%paletteRows.length;paletteList.positionViewAtIndex(paletteIndex,ListView.Contain);}
            }else if(event.key===Qt.Key_Return || event.key===Qt.Key_Enter){event.accepted=true;executePalette();}
        }
        Keys.onEscapePressed: function(event) {event.accepted=true;if(paletteInput===paletteField)closePalette(true);else clear();}
        onAccepted: {
            let list=paletteField===topologySearch?topologyList:recordList;
            list.forceActiveFocus();if(list.count)list.currentIndex=0;
        }
        SafeTip { visible:anchorHovered; text:"Search records · > commands · # PID: Packet Identifier / SID: Service Identifier · #table: Table Identifier" }
    }
    component FieldInput: TextField {
        id: fieldInput
        background: Rectangle {
            radius: 2
            color: surface
            border.color: fieldInput.activeFocus ? blue : controlBorder
            border.width: fieldInput.activeFocus ? focusWidth : 1
            opacity: fieldInput.enabled ? 1 : 0.4
        }
    }
    component FieldChoice: ComboBox {
        id: fieldChoice
        implicitHeight: Math.max(28, implicitContentHeight + topPadding + bottomPadding)
        topPadding: 4
        bottomPadding: 4
        leftPadding: 10
        rightPadding: 26
        contentItem: PlainLabel {
            text: fieldChoice.displayText
            font: fieldChoice.font
            color: fieldChoice.enabled ? ink : muted
            verticalAlignment: Text.AlignVCenter
            elide: Text.ElideRight
        }
        indicator: PlainLabel {
            text: "▾"
            color: fieldChoice.enabled ? ink : muted
            font.pixelSize: 16
            width: 22
            horizontalAlignment: Text.AlignHCenter
            anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter
        }
        background: Rectangle {
            radius: 2
            color: raised
            border.color: fieldChoice.activeFocus ? blue : controlBorder
            border.width: fieldChoice.activeFocus ? focusWidth : 1
            opacity: fieldChoice.enabled ? 1 : 0.4
        }
    }
    component TinyLabel: PlainLabel {
        color: muted
        font.pixelSize: 11
        font.letterSpacing: 0.6
    }
    component Action: Button {
        id: control
        property bool primary: false
        implicitHeight: 28
        leftPadding: 10
        rightPadding: 10
        focusPolicy: Qt.StrongFocus
        contentItem: PlainLabel {
            text: control.text
            color: control.primary ? "white" : ink
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
            opacity: control.enabled ? 1 : 0.4
            font.pixelSize: 11
        }
        background: Rectangle {
            radius: 2
            color: !control.enabled ? raised : control.primary ? (control.hovered ? "#086fae" : "#006fb9") : (control.hovered ? hoverSurface : raised)
            border.color: control.activeFocus ? blue : controlBorder
            border.width: control.activeFocus ? focusWidth : 1
        }
    }
    component ComparisonMarker: Slider {
        id: marker
        property bool startMarker: true
        readonly property bool packetValid: validPacket(startMarker ? fromPacket.text : toPacket.text)
        objectName: startMarker ? "comparisonMarkerA" : "comparisonMarkerB"
        from: 0
        to: Math.max(0, Number(analysisState.packets || 1) - 1)
        stepSize: 1
        value: packetValid ? Number(startMarker ? fromPacket.text : toPacket.text) : 0
        visible: !!analysisState.complete && packetValid
        enabled: densityStrip.interactive && !core.comparing
        focusPolicy: Qt.StrongFocus
        activeFocusOnTab: enabled && visible
        width: 20; height: 14; padding: 0; z: 2
        x: (to > 0 ? value / to * densityStrip.width : 0) - width / 2
        y: startMarker ? 0 : 14
        Accessible.role: Accessible.Slider
        Accessible.name: "Comparison " + (startMarker ? "A" : "B") + " packet"
        Accessible.description: "Packet " + value + ". Drag to change the comparison " + (startMarker ? "start" : "end")
        onMoved: densityStrip.moveComparisonMarker(startMarker, value)
        Keys.onPressed: function(event) {
            // Explicit order: density strip, A, B; the strip is the markers' parent.
            const back = event.key === Qt.Key_Backtab || event.key === Qt.Key_Tab && (event.modifiers & Qt.ShiftModifier);
            if (back) { (!startMarker && comparisonMarkerA.visible && comparisonMarkerA.enabled ? comparisonMarkerA : densityStrip).forceActiveFocus(Qt.BacktabFocusReason); event.accepted = true; return; }
            if (event.key === Qt.Key_Tab && startMarker && comparisonMarkerB.visible && comparisonMarkerB.enabled) { comparisonMarkerB.forceActiveFocus(Qt.TabFocusReason); event.accepted = true; return; }
            if ([Qt.Key_Left, Qt.Key_Right, Qt.Key_Home, Qt.Key_End].indexOf(event.key) < 0) return;
            let step = event.modifiers & Qt.ShiftModifier ? 1 : Math.max(1, Math.round(to / Math.max(1, densityStrip.binCount - 1)));
            densityStrip.moveComparisonMarker(startMarker, event.key === Qt.Key_Home ? 0 : event.key === Qt.Key_End ? to : value + (event.key === Qt.Key_Right ? step : -step));
            event.accepted = true;
        }
        handle: null
        background: Rectangle { color: surface; radius: 2; border.color: marker.startMarker ? removedColor : addedColor }
        contentItem: PlainLabel { text: marker.startMarker ? "A" : "B"; color: marker.startMarker ? removedColor : addedColor; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter; font.pixelSize: 11 }
        Rectangle { x: marker.width / 2 - 1; y: marker.startMarker ? 0 : -14; width: 2; height: densityStrip.height; z: -1; color: marker.startMarker ? removedColor : addedColor }
        Rectangle { anchors.fill: parent; anchors.margins: -2; visible: marker.activeFocus; color: "transparent"; border.color: blue; border.width: focusWidth; radius: 2 }
        MouseArea {
            id: markerMouse
            anchors.fill: parent
            acceptedButtons: Qt.LeftButton
            hoverEnabled: true
            preventStealing: true
            cursorShape: Qt.SizeHorCursor
            property real grabOffset: 0
            function moveTo(mouse) {
                let point = mapToItem(densityStrip, mouse.x, mouse.y);
                densityStrip.moveComparisonMarker(marker.startMarker, (point.x - grabOffset) / Math.max(1, densityStrip.width) * marker.to);
            }
            onPressed: function(mouse) { marker.forceActiveFocus(Qt.MouseFocusReason); grabOffset = mapToItem(densityStrip, mouse.x, mouse.y).x - marker.x - marker.width / 2; }
            onPositionChanged: function(mouse) { if (pressed) moveTo(mouse); }
            onReleased: function(mouse) { moveTo(mouse); focusComparisonAction(); }
        }
        SafeTip { visible: markerMouse.containsMouse; text: (marker.startMarker ? "A" : "B") + " · packet " + marker.value + " · drag to change the comparison " + (marker.startMarker ? "start" : "end") }
    }
    component RecentMenuItem: MenuItem {
        id: entry
        implicitHeight: 28
        leftPadding: 8
        rightPadding: 8
        Accessible.name: text
        contentItem: PlainLabel {text:entry.text;color:entry.enabled?ink:muted;elide:Text.ElideMiddle;verticalAlignment:Text.AlignVCenter;font.pixelSize:11}
        background: Rectangle {color:entry.highlighted?hoverSurface:panel;border.color:entry.activeFocus?blue:dividerColor;border.width:entry.activeFocus?focusWidth:0;radius:2}
    }
    component SummaryChip: Action {
        id: chip
        property string help: ""
        property bool disclosure: true
        property var scrollHost: null
        implicitHeight: 26
        leftPadding: 4
        rightPadding: 4
        checkable: true
        Accessible.name: text + (disclosure ? (checked ? ", expanded" : ", collapsed") : "")
        Accessible.description: help
        onActiveFocusChanged: if(activeFocus && scrollHost)scrollHost.reveal(chip)
        background: Rectangle {
            radius: 2
            color: chip.checked ? selectionSurface : chip.hovered ? hoverSurface : panel
            border.color: chip.activeFocus ? blue : chip.checked ? dividerColor : "transparent"
            border.width: chip.activeFocus ? focusWidth : 1
        }
        SafeTip { visible: anchorHovered; text: chip.help }
    }
    component NavItem: ItemDelegate {
        id: nav
        property bool keyboardCurrent: false
        property color foreground: ink
        implicitHeight: 29
        focusPolicy: Qt.StrongFocus
        contentItem: PlainLabel {
            text: nav.text
            color: nav.foreground
            verticalAlignment: Text.AlignVCenter
            elide: Text.ElideRight
            font.pixelSize: 11
        }
        background: Rectangle {
            color: nav.highlighted ? selectionSurface : nav.hovered ? hoverSurface : "transparent"
            border.color: nav.activeFocus || nav.keyboardCurrent ? blue : "transparent"
            border.width: nav.activeFocus || nav.keyboardCurrent ? focusWidth : 0
        }
    }
    component Card: Rectangle {
        color: panel
        border.color: dividerColor
    }
    component StatBadge: Button {
        id: stat
        property string label: ""
        property string value: ""
        property string detailText: ""
        property var counts: null
        // Narrow windows keep the value and counts; secondary detail stays in the accessible name.
        property bool compact: false
        implicitHeight: 28
        topPadding: 3
        bottomPadding: 3
        leftPadding: 4
        rightPadding: 4
        focusPolicy: Qt.StrongFocus
        contentItem: RowLayout {
            spacing: 8
            PlainLabel { text:stat.label; color:muted; font.pixelSize:11 }
            PlainLabel { visible:!stat.counts || !stat.counts.hasSeverity; text:stat.value; color:ink; font.pixelSize:15; font.family:"monospace" }
            PlainLabel { visible:!!stat.counts && stat.counts.hasSeverity; text:stat.counts ? num(stat.counts.errors)+" errors" : ""; color:removedColor; font.pixelSize:11 }
            PlainLabel { visible:!!stat.counts && stat.counts.hasSeverity; text:stat.counts ? num(stat.counts.warnings)+" warnings" : ""; color:warningColor; font.pixelSize:11 }
            PlainLabel { visible:!!stat.counts && stat.counts.hasSeverity && stat.counts.other>0; text:stat.counts ? num(stat.counts.other)+" other" : ""; color:muted; font.pixelSize:11 }
            PlainLabel { visible:!!stat.detailText && !stat.compact; text:stat.detailText; color:muted; font.pixelSize:11 }
        }
        background: Rectangle {
            color:stat.hovered ? hoverSurface : "transparent"
            border.color:stat.activeFocus ? blue : "transparent"
            border.width:stat.activeFocus ? focusWidth : 0
            radius:2
        }
        Keys.onReturnPressed: clicked()
        Keys.onEnterPressed: clicked()
    }
    Connections {
        target: inspectorReferences
        function onModelChanged() { if(referencePersistenceTest.running)referencePersistenceTest.modelChanges++; }
    }
    Timer {
        id: referencePersistenceTest
        property int modelChanges: 0
        property int delegateCreates: 0
        property int delegateDestroys: 0
        property var observations: []
        function observe(label) {
            observations.push({phase:label, modelChanges:modelChanges, delegateCreates:delegateCreates, delegateDestroys:delegateDestroys,
                width:inspectorReferences.width,height:inspectorReferences.height,currentIndex:inspectorReferences.currentIndex,count:inspectorReferences.count,visible:inspectorReferences.visible,
                loadedIdentity:inspectorReferences.loadedIdentity,currentIdentity:inspectorReferences.currentIdentity,
                currentItem:!!inspectorReferences.currentItem,
                selection:inspectorReferences.currentItem ? inspectorReferences.currentItem.urlField.selectedText : null});
        }
        interval: 40; repeat: true
        running: core.env("SHOWPSISI_SCRIPT")==="reference-persistence"
        property int phase: 0
        property var checks: ({})
        property string urlSelection: ""
        property string dialogSelection: ""
        property string hexSelection: ""
        property real savedY: 0
        property string previousId: ""
        onTriggered: {
            if(core.busy || core.inspecting || !analysisState.complete || !detail.id)return;
            if(phase===0){checks.deferred=inspectorReferences.model.length===0 && dialogReferences.model.length===0;inspectorView="References";phase=1;return;}
            if(phase===1){
                if(!inspectorReferences.currentItem)return;
                let field=inspectorReferences.currentItem.urlField;field.select(1,8);urlSelection=field.selectedText;
                savedY=inspectorReferences.contentY;observe("before_hide");inspectorView="Structure";observe("after_hide");phase=2;return;
            }
            if(phase===2){observe("hidden_tick");checks.hidden_retained=!!inspectorReferences.currentItem && inspectorReferences.currentItem.urlField.selectedText===urlSelection;inspectorView="References";phase=3;return;}
            if(phase===3){observe("shown_tick");checks.reference_model_stable=observations.every(function(row){return row.modelChanges===observations[0].modelChanges;});checks.reference_selection=!!urlSelection && !!inspectorReferences.currentItem && inspectorReferences.currentItem.urlField.selectedText===urlSelection;checks.reference_scroll=inspectorReferences.contentY===savedY;specificationDialog.open();phase=4;return;}
            if(phase===4){if(!dialogReferences.currentItem)return;let field=dialogReferences.currentItem.urlField;field.select(1,9);dialogSelection=field.selectedText;specificationDialog.close();phase=5;return;}
            if(phase===5){checks.dialog_hidden_retained=!!dialogReferences.currentItem && dialogReferences.currentItem.urlField.selectedText===dialogSelection;specificationDialog.open();phase=6;return;}
            if(phase===6){checks.dialog_selection=!!dialogSelection && !!dialogReferences.currentItem && dialogReferences.currentItem.urlField.selectedText===dialogSelection;specificationDialog.close();inspectorView="Hex";phase=7;return;}
            if(phase===7){hexEvidence.select(1,8);hexSelection=hexEvidence.selectedText;inspectorView="Structure";phase=8;return;}
            if(phase===8){inspectorView="Hex";phase=9;return;}
            if(phase===9){checks.hex_selection=!!hexSelection && hexEvidence.selectedText===hexSelection;inspectorView="Structure";previousId=detail.id;let row=(analysisState.tables || []).find(function(r){return r.id!==previousId;});checks.other_record=!!row;if(row)inspect(row.id);phase=10;return;}
            if(phase===10){if(detail.id===previousId)return;checks.identity_invalidates=inspectorReferences.model.length===0 && dialogReferences.model.length===0;stop();core.capture(core.env("SHOWPSISI_SCREENSHOT"));core.testResult(JSON.stringify({passed:Object.keys(checks).every(function(k){return checks[k];}),checks:checks,observations:observations}));}
        }
    }
    Connections {
        target: dvbiWorkspace
        function onErrorChanged() { if(dvbiWorkspace.error && !core.error)showMessage(dvbiWorkspace.error,"error"); }
        function onBusyChanged() {
            if(metadataMode && !dvbiWorkspace.error && !core.error)
                showMessage(dvbiWorkspace.busy ? "Loading local document…" : dvbiWorkspace.hasDocument ? "Local document imported · original file unchanged" : "Choose a local XML document");
        }
    }
    Connections {
        target: core
        function onResultLoading(){++presentationToken;presentationPending=false;hydrationCollections={};}
        function onResultPage(collection,json){
            core.mark("page_handler_enter_" + collection);
            const result=JSON.parse(json);
            core.mark("page_parsed_" + collection + "_bytes_" + json.length);
            if(!hydrationCollections[collection])hydrationCollections[collection]=[];
            const rows=hydrationCollections[collection];for(const row of result.items)rows.push(row);
        }
        function onStateChanged(){
            core.mark("state_js_begin");const state=JSON.parse(core.stateJson);
            if(state.response_mode==="compact" && state.complete){
                for(const name of Object.keys(hydrationCollections))state[name]=hydrationCollections[name];
                const truncated=(state.table_groups || []).filter(function(g){return g.member_ids_truncated;});
                if(truncated.length){
                    const members={},selected={},wanted={};for(const group of truncated)wanted[group.id]=true;
                    for(const row of state.tables || []){const key=row.table_group_id;if(!wanted[key])continue;(members[key] || (members[key]=[])).push(row.id);if(row.selected_in_snapshot)(selected[key] || (selected[key]=[])).push(row.id);}
                    for(const group of truncated){group.section_ids=members[group.id] || [];group.selected_section_ids=selected[group.id] || [];group.member_ids_truncated=false;}
                }
            }
            const token=++presentationToken,epoch=core.resultEpoch();
            const staged=state.response_mode==="compact" && !!state.complete;
            presentationPending=staged;
            core.mark("state_js_assembled");analysisState=state;core.mark("state_js_end");
            if(unifiedInspector.visible){topologyFailed=false;siOrganizationTimer.restart();}
            if(staged)Qt.callLater(function(){publishViewStage(state,token,epoch,0);});
            else {tableViewState=state;explorerViewState=state;historyViewState=state;recordViewState=state;}
        }
        function onErrorChanged() { if(core.error)showMessage(core.error, "error"); }
        function onWorkspaceInvalidated() {
            clearWorkspaceIntentions();
            if(core.busy){filter="";pidFilter=-1;expandedTables={};recordSearch.clear();treeSearch.clear();tab="Services";}
        }
        function onAvailabilityChanged() {
            if (core.availability === "disconnected") {
                pendingScanOptions=null;
                autoTimer.stop();
                protocolRestoreTimer.stop();protocolRestoring=false;protocolRestorePending=null;
                fileDialog.close();
                topologyLoading=false;topologyError="Backend disconnected. Restart the application to continue.";
            }
        }
        function onResponse(method, result) {
            if(method=="query_carousel"){documentWorkspace.receiveCarousel(result);return;}
            if(method=="query_service"){documentWorkspace.receiveService(result);return;}
            if(method=="query_timing"){documentWorkspace.receiveStatistics(method,result);return;}
            if(method=="query_packet"){documentWorkspace.receivePacket(result);return;}
            if(method=="query_transport"){transportSummary.receive(result);documentWorkspace.receiveTransport(result);documentWorkspace.receiveStatistics(method,result);return;}
            if(method==="capabilities" && analysisModesTestTimer.running){analysisModesTestTimer.barrier=true;return;}
            if(method === "analyze") {
                if(result.complete && !advancedMode)classicConfigurationVisible=false;
                if(result.complete && pendingScanOptions !== null){completedScanOptions=pendingScanOptions;completedCoverageKey=pendingCoverageKey;}
                pendingScanOptions=null;
            }
            if (method === "query_topology") { acceptTopology(result); return; }
            if(method==="inspect"){
                if(protocolSourceRef)resolveProtocolInspection(result);
                else if(topologyEvidenceRef)resolveTopologyInspection(result);
                if(protocolRestorePending){
                    let origin=protocolRestorePending;protocolRestorePending=null;
                    if(!result.message && result.id===origin.id && result.analysis_revision===origin.revision && result.native_table_at_packet===origin.cutoff){
                        if(origin.kind==="selection")restoreReferenceSelection(origin);
                        else {
                            topologyTransition=true;tab=origin.tab;topologyTransition=false;inspectorView=origin.view;evidenceScope=origin.scope;collapsed=origin.collapsed;treeSearch.text=origin.search;
                            protocolCardOffset=origin.offset;protocolRestoreTimer.origin=origin;protocolRestoreTimer.restart();
                        }
                    }else {protocolRestoring=false;let message=result.message || "The originating metadata context could not be restored.";if(notice!==message || messageLevel!=="error")showMessage(message,"error");}
                }
            }
            if (method === "lookup_identifier") identifierResult=result;
            if (method === "lookup_satellite") satelliteResult=result;
            if (method === "query") comparisonTestTimer.completedQueries++;
            if (method === "pause_analysis" || method === "resume_analysis") {
                core.mark(method + "_ack");return;
            }
            if (method === "cancel_analysis") {
                if (core.env("SHOWPSISI_SCRIPT") === "lifecycle-stale" || core.env("SHOWPSISI_SCRIPT") === "lifecycle-complete-race") {
                    lifecycleTestTimer.checks.ack_did_not_settle = core.busy && core.cancelling && scanProgress.source.indexOf("poison") < 0;
                    core.mark("cancel_ack_observed");
                }
                return;
            }
            if (method === "fixture_late_frames") { lifecycleTestTimer.lateFramesAcknowledged = true; return; }
            if (method === "analyze" && result.data && result.data.state_preserved) {
                if(analysisState.source)source.text=analysisState.source;
                showMessage(result.message + " — previous input and view retained", "error");
                return;
            }
            if (method === "analyze" && result.code === "analysis_cancelled") {
                showMessage("Scan cancelled · source unchanged · analyze again when ready", "warning");
                return;
            }
            if (result.message) {
                if (method === "export") {
                    exporting = false;
                    exportFeedback = result.message;
                    exportButton.forceActiveFocus();
                }
                if(notice!==result.message || messageLevel!=="error")showMessage(result.message, "error");
                if (method === "diff_snapshots")
                    comparisonError = result.message;
                return;
            }
            if (method === "analyze") {
                if (result.cancel_requested) {
                    notice = "Scan finished before cancellation took effect · source unchanged";
                    return;
                }
                core.mark("default_inspect_begin");defaultInspect();core.mark("default_inspect_end");
                inspected = true;
                let truncated=(result.demux || {}).truncated_sections || 0;
                showMessage((partialResults ? "Quick preview complete · partial, read-only · source unchanged" : "Scan complete · source unchanged") + (truncated ? " · " + num(truncated) + " truncated section(s)" : ""), truncated ? "warning" : "info");
            }
            if (method === "query") {
                if (snapshotTarget)
                    inspect(snapshotTarget, snapshotTargetService);
                else
                    defaultInspect();
                snapshotTarget = "";
                snapshotTargetService = -1;
                if(tab === "Topology")loadTopology(false);
            }
            if (method === "diff_snapshots") {
                comparison = result;
                notice = "Compared A → B · " + num(result.total_changes) + " changes · current snapshot unchanged";
                if (tab === "Changes") {
                    recordList.currentIndex = rows.length ? 0 : -1;
                    recordList.forceActiveFocus();
                }
            }
            if (method === "preview_rename") {
                if (!renameDialog.visible || previewIntent.source !== analysisState.source ||
                        previewIntent.at !== analysisState.selected_packet || previewIntent.id !== selected ||
                        result.source_id !== selected || result.service_id !== editService.currentValue ||
                        previewIntent.sid !== editService.currentValue || result.after !== renameName.text ||
                        previewIntent.name !== renameName.text) return;
                preview = result;
                notice = "Preview ready · no source changes";
            }
            if (method === "export") {
                exporting = false;
                lastExportFolder = core.parentFolder(result.path);
                notice = "Exported " + num(result.bytes) + " bytes + manifest";
                exportFeedback = notice + "\n" + result.path;
                exportButton.forceActiveFocus();
            }
            if (method === "capabilities") {
                apiText.text = JSON.stringify(result, null, 2);
                apiDialog.open();
            }
        }
        function onCompletedPaint() {
            if (core.env("SHOWPSISI_SCREENSHOT") && core.env("SHOWPSISI_SCRIPT") !== "refinement")
                captureTimer.start();
        }
    }
    Timer {
        id: protocolRestoreTimer
        property var origin: ({})
        interval:40
        onTriggered:{
            let saved=origin,card=protocolCardRepeater.itemAt(saved.card === undefined?-1:saved.card),button=card?card.sourceControls.itemAt(saved.source === undefined?-1:saved.source):null;
            if(button)button.forceActiveFocus();
            Qt.callLater(function(){metadataScroll.contentItem.contentY=saved.scroll;protocolRestoring=false;});
        }
    }
    Timer {
        id: topologyRevealTimer
        interval: 30
        onTriggered: {
            if(!activeInspectionRef || detail.id!==(protocolSourceRef ? protocolSourceRef.section_id : topologySectionContext ? topologySectionContext.id : topologyEvidenceRef.section_id) || core.inspecting)return;
            let path=(activeInspectionResolution.path || "").replace(/^section\//,"");
            let index=treeRows.findIndex(function(r){return r.path===path;});
            if(index>=0){tree.currentIndex=index;tree.positionViewAtIndex(index,ListView.Center);if(tab==="Topology" || protocolSourceRef)tree.forceActiveFocus();}
        }
    }
    Timer {
        id: captureTimer
        interval: 500
        onTriggered: {
            core.capture(core.env("SHOWPSISI_SCREENSHOT"));
            if (core.env("SHOWPSISI_SCRIPT") === "smoke")
                smokeTimer.start();
        }
    }
    Timer {
        id: smokeTimer
        interval: 250
        repeat: true
        onTriggered: {
            // Metadata may already expose the requested cutoff while compact
            // result pages and the default inspection are still in flight.
            // Drive real controls only once that operation has settled.
            if (!backendReady || core.inspecting)
                return;
            if (testStep === 0) {
                if (!analysisState.history.length)
                    return;
                snapshot(analysisState.history[0].last_packet,analysisState.history[0].id);
                testStep++;
            } else if (testStep === 1) {
                if (serviceRows[0]?.name !== "World News" || core.inspecting || detail.version !== 1)
                    return;
                historyCutoffVerified = detail.native_table_at_packet === analysisState.selected_packet;
                snapshot(-1);
                core.click("tab_Issues");
                testStep++;
            } else if (testStep === 2) {
                if (analysisState.selected_packet !== null && analysisState.selected_packet !== undefined)
                    return;
                if (!core.click("issue_crc32"))
                    return;
                testStep++;
            } else if (testStep === 3) {
                if (detail.valid !== false)
                    return;
                if (inspectorView !== "Hex") {
                    core.click("inspector_Hex");
                    return;
                }
                core.capture(artifactDir + "/qt-issues.png");
                core.click("inspector_Structure");
                core.click("latest");
                core.click("tab_Services");
                testStep++;
            } else if (testStep === 4) {
                if (serviceRows[0]?.name !== "Sports UHD")
                    return;
                if (!core.click("service_103"))
                    return;
                testStep++;
            } else if (testStep === 5) {
                if (detail.version !== 3)
                    return;
                core.click("rename");
                testStep++;
            } else if (testStep === 6) {
                renameName.text = "UI verified rename";
                core.click("preview");
                testStep++;
            } else if (testStep === 7) {
                if (!preview.token)
                    return;
                core.capture(artifactDir + "/qt-edit.png");
                core.click("export");
                // Explicit validation destination; production always uses the picker.
                let testIntent = saveIntent;
                saveDialog.close();
                saveIntent = testIntent;
                saveDialog.currentFolder = core.fileUrl(artifactDir);
                saveDialog.selectedFile = core.fileUrl(artifactDir + "/qt-export-" + Date.now() + ".ts");
                saveDialog.open();
                exportAcceptTimer.start();
                testStep++;
            } else if (testStep === 8) {
                if (notice.indexOf("Exported") !== 0)
                    return;
                renameDialog.close();
                core.click("agentApi");
                testStep++;
            } else if (testStep === 9) {
                if (!apiDialog.visible || apiText.text.indexOf("preview_rename") < 0)
                    return;
                apiDialog.close();
                if (!core.click("specifications"))
                    return;
                testStep++;
            } else if (testStep === 10) {
                if (!specificationDialog.visible)
                    return;
                core.capture(artifactDir + "/qt-specifications.png");
                specificationDialog.close();
                testStep++;
            } else if (testStep === 11) {
                core.key("Ctrl+K");
                let keyboardFocus = recordSearch.activeFocus;
                let originalSelected = selected;
                let originalService = selectedService;
                recordSearch.text = "SPORTS";
                let names = rows.length === 1 && rows[0].id === 103;
                recordSearch.text = "0x0067";
                let identifiers = rows.length === 1 && rows[0].id === 103 && matchesRecord({
                    id: 103
                }, "103");
                recordSearch.text = "no-matching-record-qt-test";
                let empty = rows.length === 0 && selectionHidden && selected === originalSelected && selectedService === originalService;
                core.key("Escape");
                let escapeClears = recordSearch.text === "" && rows.length === serviceRows.length;
                let savedCollapsed = collapsed;
                collapsed = Object.assign({}, collapsed, {
                    native: true
                });
                let collapsedBefore = JSON.stringify(collapsed);
                let treeBefore = treeRows.length;
                treeSearch.text = "Sports UHD";
                let ancestry = treeRows.some(function (row) {
                    return row.path === "native";
                }) && treeRows.some(function (row) {
                    return row.label.indexOf("service_descriptor") === 0;
                }) && treeRows.some(function (row) {
                    return row.label === "service_name" && row.value === "Sports UHD";
                });
                treeSearch.text = "no-matching-field-qt-test";
                let treeEmpty = treeRows.length === 0;
                treeSearch.clear();
                let collapseRestored = JSON.stringify(collapsed) === collapsedBefore && treeRows.length === treeBefore;
                collapsed = savedCollapsed;
                tree.forceActiveFocus();
                core.key("Home");
                let firstIndex = tree.currentIndex;
                core.key("End");
                let endReached = tree.currentIndex === treeRows.length - 1;
                core.key("Home");
                let branchIndex = treeRows.findIndex(function (row) { return row.branch; });
                tree.currentIndex = branchIndex;
                core.key("Left");
                let folded = treeRows[tree.currentIndex].closed;
                core.key("Right");
                let expanded = !treeRows[tree.currentIndex].closed;
                let parentIndex = tree.currentIndex;
                core.key("Right");
                let entered = tree.currentIndex === parentIndex + 1 && treeRows[tree.currentIndex].depth > treeRows[parentIndex].depth;
                core.key("Left");
                let parentReached = tree.currentIndex === parentIndex;
                core.key("Tab");
                let tabExits = !tree.activeFocus;
                collapsed = savedCollapsed;
                searchChecks = {
                    tree_home_end: firstIndex === 0 && endReached,
                    tree_expand_enter_parent: folded && expanded && entered && parentReached,
                    tree_tab_exits: tabExits,
                    record_names: names,
                    identifiers: identifiers,
                    empty_preserves_selection: empty,
                    keyboard_focus: keyboardFocus,
                    escape_clears: escapeClears,
                    tree_ancestry: ancestry,
                    tree_empty: treeEmpty,
                    collapse_restored: collapseRestored
                };
                core.testResult(JSON.stringify({
                    checks: ["history changes channel name/order", "CRC raw evidence", "rename preview", "signal-only export", "API schema discovery"],
                    passed: historyCutoffVerified && Object.keys(searchChecks).every(function (key) {
                        return searchChecks[key];
                    }) && analysisState.standards_context === standardChoice.currentValue && !!detail.native_table && treeRows.some(function (row) {
                        return row.kind === "native";
                    }) && parseExtraPids("0x30, 100").join(",") === "48,100" && parseExtraPids("8192") === null,
                    services: serviceRows.length,
                    observations: analysisState.observations,
                    standards_context: analysisState.standards_context,
                    native_tree: !!detail.native_table,
                    references: specificationLinks.length,
                    search: searchChecks,
                    history_cutoff: historyCutoffVerified
                }));
                stop();
            }
        }
    }
    Timer {
        id: exportAcceptTimer
        interval: exportTestTimer.choiceSequence === 3 && core.env("SHOWPSISI_TEST_EXPORT_ACCEPT_DELAY") ? Number(core.env("SHOWPSISI_TEST_EXPORT_ACCEPT_DELAY")) : 100
        onTriggered: saveDialog.accept()
    }
    Timer {
        id: exportTestTimer
        interval: 150
        repeat: true
        property real step: 0
        property int choiceSequence: 0
        property bool choicePending: false
        property var choiceEvidence: []
        function resolvedChoice() {
            if (!choicePending) return;
            choicePending = false;
            choiceEvidence = choiceEvidence.concat([{sequence:choiceSequence, feedback:exportFeedback, exporting:exporting}]);
        }
        property var checks: ({})
        property string savedPreview: ""
        property string savedState: ""
        function choose(path) {
            choiceSequence++;
            core.click("export");
            let testIntent = saveIntent;
            saveDialog.close();
            saveIntent = testIntent;
            saveDialog.currentFolder = core.fileUrl(core.env("SHOWPSISI_EXPORT_TEST_DIR"));
            saveDialog.selectedFile = core.fileUrl(path);
            choicePending = true;
            saveDialog.open();
            exportAcceptTimer.start();
        }
        onTriggered: {
            let directory = core.env("SHOWPSISI_EXPORT_TEST_DIR");
            // Not exporting also describes the interval before dialog acceptance.
            // Wait for this choice's actual resolution, never an elapsed timer gap.
            if (choicePending) return;
            if (step === 0) {
                if (!analysisState.complete || core.inspecting || !detail.native_table) return;
                core.click("rename");
                renameName.text = "Qt destination edit";
                core.click("preview");
                step++;
            } else if (step === 1) {
                if (!preview.token) return;
                savedPreview = JSON.stringify(preview);
                savedState = JSON.stringify(analysisState);
                core.click("export");
                checks.save_mode = saveDialog.visible && saveDialog.fileMode === FileDialog.SaveFile;
                checks.no_replace_prompt = !!(saveDialog.options & FileDialog.DontConfirmOverwrite);
                checks.user_folder = core.localPath(saveDialog.currentFolder) !== core.root;
                checks.source_name = core.localPath(saveDialog.selectedFile).endsWith("lab-edited-si.ts");
                checks.portable_reserved_name = core.localPath(core.suggestedExport(core.fileUrl(directory), "CON.ts", "ts")).endsWith("CON-edited-si.ts");
                checks.safe_name = core.localPath(core.suggestedExport(core.fileUrl(directory), "../<bad>\\name?.ts", "bin")).endsWith("-edited-si.bin") &&
                    !core.localPath(core.suggestedExport(core.fileUrl(directory), "../<bad>\\name?.ts", "bin")).includes("<");
                saveDialog.selectedFile = core.fileUrl(directory + "/cancelled.ts");
                saveDialog.reject();
                step++;
            } else if (step === 2) {
                checks.cancel_preserves_preview = JSON.stringify(preview) === savedPreview;
                checks.cancel_preserves_state = JSON.stringify(analysisState) === savedState && !exporting;
                checks.cancel_focus = exportButton.activeFocus;
                checks.compact_controls = core.isExposed("export") && core.isExposed("exportFormat");
                choose(directory + "/wrong.bin");
                step++;
            } else if (step === 3) {
                checks.extension_refused = exportFeedback.indexOf("Use a .ts") === 0 && !exporting;
                choose(directory + "/chosen λ.ts");
                step++;
            } else if (step === 4) {
                if (exporting || exportFeedback.indexOf("Exported") !== 0) return;
                checks.ts_success = exportFeedback.includes("chosen λ.ts") && JSON.stringify(preview) === savedPreview;
                checks.remembered_folder = core.localPath(lastExportFolder) === core.localPath(core.fileUrl(directory));
                choose(directory + "/chosen λ.ts");
                step++;
            } else if (step === 5) {
                if (exporting) return;
                checks.existing_output_refused = exportFeedback.includes("already exists") && JSON.stringify(preview) === savedPreview;
                choose(directory + "/chosen λ.ts");
                step = 5.5;
            } else if (step === 5.5) {
                if (exporting) return;
                checks.repeated_output_refused = exportFeedback.includes("already exists") && JSON.stringify(preview) === savedPreview;
                core.click("export");
                saveDialog.reject();
                checks.cancel_after_refusal = !exporting && !Object.keys(saveIntent).length && exportFeedback === "" && JSON.stringify(preview) === savedPreview;
                choose(directory + "/manifest-only.ts");
                step = 6;
            } else if (step === 6) {
                if (exporting) return;
                checks.existing_manifest_refused = exportFeedback.includes("already exists") && JSON.stringify(preview) === savedPreview;
                exportFormat.currentIndex = 1;
                choose(directory + "/raw-sections");
                step++;
            } else if (step === 7) {
                if (exporting || exportFeedback.indexOf("Exported") !== 0) return;
                checks.bin_success = exportFeedback.includes("raw-sections.bin") && JSON.stringify(preview) === savedPreview;
                checks.state_preserved = JSON.stringify(analysisState) === savedState;
                checks.nonlocal_refused = !!core.exportDestination("https://example.com/output.ts", "ts").error;
                core.click("export");
                saveDialog.selectedFile = core.fileUrl(directory + "/stale.bin");
                preview = {};
                saveDialog.accept();
                step++;
            } else if (step === 8) {
                checks.stale_refused = !exporting && exportFeedback.indexOf("The preview changed") === 0;
                renameDialog.close();
                core.click("rename");
                checks.reopen_clears_feedback = exportFeedback === "";
                core.testResult(JSON.stringify({checks: checks, choices:choiceEvidence, passed: Object.values(checks).every(Boolean)}));
                stop();
            }
        }
    }
    Timer {
        id: protocolUpgradeTimer
        interval: 200
        repeat: true
        property real phase: 0
        property var checks: ({})
        property string savedId: ""
        property string savedRaw: ""
        onTriggered: {
            let standard = core.env("SHOWPSISI_PROTOCOL_STANDARD");
            let guarded = core.env("SHOWPSISI_PROTOCOL_GUARDED") === "1";
            if (phase === 0) {
                if (!backendReady) return;
                extraPids.text = core.env("SHOWPSISI_PROTOCOL_PID");
                let index = standardChoice.indexOfValue(standard);
                checks.selector_present = index >= 0 && core.isExposed("standards");
                core.click("standards");
                core.key("Home");
                for (let i = 0; i < index; ++i) core.key("Down");
                core.key("Return");
                checks.selector_value = standardChoice.currentValue === standard;
                checks.analyze_click = core.click("analyzeSource");
                phase++;
                return;
            }
            if (!analysisState.complete || core.busy || core.inspecting || !detail.id) return;
            if (phase === 1) {
                savedId = selected;
                savedRaw = detail.raw_hex;
                checks.context = analysisState.standards_context === standard;
                checks.native_table = detail.native_table?.name === core.env("SHOWPSISI_PROTOCOL_EXPECTED_TABLE");
                checks.services_empty = serviceRows.length === 0 && tableRows.length > 0;
                checks.initial_tables_fallback = tab === "Tables";
                checks.services_click = core.click("tab_Services");
                phase = 1.5;
            } else if (phase === 1.5) {
                checks.services_hint = recordEmptyHint.visible && core.isExposed("recordEmptyHint") && recordEmptyHint.text.indexOf("Open Tables for native signalling fields") >= 0;
                checks.epg_click = core.click("tab_EPG");
                phase = 2;
            } else if (phase === 2) {
                checks.epg_hint = tab === "EPG" && eventRows.length === 0 && recordEmptyHint.visible && recordEmptyHint.text.indexOf("an empty projection does not mean decoding failed") >= 0;
                checks.epg_selection = selected === savedId && detail.raw_hex === savedRaw;
                checks.tables_click = core.click("tab_Tables");
                warningsOpen=guarded;
                phase++;
            } else if (phase === 3) {
                checks.tables_selection = tab === "Tables" && rows.length > 0 && selected === savedId;
                checks.guard_flag = !!detail.native_xml_guarded === guarded;
                checks.warning_visible = guarded ? core.isExposed("nativeDecodeWarnings") && nativeDecodeWarningLabel.text.indexOf("namespace is not established") >= 0 && nativeDecodeWarningLabel.text.indexOf("Original wire bytes remain authoritative") >= 0 : !nativeDecodeWarningLabel.visible;
                checks.xml_label = evidenceViews.itemAt(2).text === (guarded ? "Guarded XML" : "XML");
                checks.xml_click = core.click("inspector_XML");
                phase++;
            } else if (phase === 4) {
                checks.xml_evidence = inspectorView === "XML" && xmlEvidence.text === detail.tsduck_xml && (!guarded || xmlEvidence.text.indexOf("<generic_descriptor") >= 0);
                checks.hex_click = core.click("inspector_Hex");
                phase++;
            } else if (phase === 5) {
                checks.raw_evidence = inspectorView === "Hex" && hexEvidence.text.indexOf(savedRaw.slice(0, 32).match(/.{1,2}/g).join(" ")) >= 0;
                checks.warning_in_hex = !guarded || core.isExposed("nativeDecodeWarnings");
                checks.structure_click = core.click("inspector_Structure");
                snapshot(-1, savedId);
                phase++;
            } else {
                if (selected !== savedId || detail.id !== savedId) return;
                checks.snapshot_preserved = tab === "Tables" && selected === savedId && detail.raw_hex === savedRaw;
                checks.native_tree = treeRows.some(function (row) { return row.kind === "native"; });
                let expanded = makeTree(detail, -1, {}, true);
                checks.array_tree_labels = standard !== "dtmb" || (expanded.some(function (row) { return row.path === "fields/streams" && row.value === "1 entries"; }) && expanded.some(function (row) { return row.path === "fields/streams/0" && row.label === "[0]"; }));
                checks.compact_title = sectionTitle.text.indexOf(tableLabel(detail.name)) === 0 && (!guarded || sectionTitle.text === "DSM-CC U-N");
                checks.exact_title_tooltip = sectionTitleTip.text.indexOf(detail.name) >= 0 && sectionTitleTip.text.indexOf(explanation(detail.name)) >= 0;
                if (core.env("SHOWPSISI_SCREENSHOT")) core.capture(core.env("SHOWPSISI_SCREENSHOT"));
                core.testResult(JSON.stringify({
                    passed: Object.keys(checks).every(function (key) { return checks[key]; }), checks: checks,
                    standards_context: analysisState.standards_context, table_name: detail.native_table?.name,
                    native_xml_guarded: !!detail.native_xml_guarded, raw_hex: detail.raw_hex,
                    selected_id: selected, warning_text: nativeDecodeWarningLabel.text, xml_label: evidenceViews.itemAt(2).text
                }));
                stop();
            }
        }
    }
    Timer {
        id: inspectFailureTimer
        interval: 150
        repeat: true
        property bool requestedFailure: false
        onTriggered: {
            if (!requestedFailure) {
                if (!detail.native_table || core.inspecting)
                    return;
                requestedFailure = true;
                inspect("missing-section-for-native-regression");
                return;
            }
            if (core.inspecting || !core.error)
                return;
            core.testResult(JSON.stringify({
                passed: Object.keys(detail).length === 0 && !detail.native_table && detail.native_table_at_packet === undefined,
                error: core.error
            }));
            stop();
        }
    }
    Timer {
        id: layoutSaveTimer
        interval: core.env("SHOWPSISI_SCRIPT").indexOf("layout-") === 0 && core.env("SHOWPSISI_TEST_LAYOUT_SAVE_DELAY") ? Number(core.env("SHOWPSISI_TEST_LAYOUT_SAVE_DELAY")) : 100
        onTriggered: rememberLayout()
    }
    Timer {
        id: layoutTestTimer
        interval: 250
        repeat: true
        property int phase: 0
        property real originalInspector: 0
        property real originalTimeline: 0
        property bool dragged: false
        property bool navigationKeysDidNotResize: true
        property int acknowledgementAttempts: 0
        onTriggered: {
            let mode = core.env("SHOWPSISI_SCRIPT");
            if (phase === 0) {
                originalInspector = inspectorPane.width;
                originalTimeline = timelinePane.height;
                if (mode === "layout-close") {
                    let expectedInspector = inspectorPane.width + 48;
                    let expectedTimeline = timelinePane.height + 48;
                    core.key("Ctrl+Alt+Left");
                    core.key("Ctrl+Alt+Left");
                    core.key("Ctrl+Alt+Up");
                    core.key("Ctrl+Alt+Up");
                    win.close();
                    let saved = core.loadLayout();
                    core.testResult(JSON.stringify({passed: saved.inspector === expectedInspector && saved.timeline === expectedTimeline,
                        saved:saved, expectedInspector:expectedInspector, expectedTimeline:expectedTimeline}));
                    stop();
                    return;
                }
                if (mode === "layout-key-drag" || mode === "layout-key-reset") {
                    core.key("Ctrl+Alt+Left");
                    core.key("Ctrl+Alt+Up");
                    if (mode === "layout-key-drag") {
                        core.drag("inspectorDivider", -40, 0);
                        core.drag("timelineDivider", 0, -30);
                    } else core.click("resetLayout");
                } else if (mode === "layout-key-constrained") {
                    win.width = 1000;
                    win.height = 680;
                } else if (mode === "layout-set") {
                    core.key("Alt+Left");core.key("Alt+Right");core.key("Alt+Up");core.key("Alt+Down");
                    navigationKeysDidNotResize = pendingInspectorSize < 0 && pendingTimelineSize < 0
                        && inspectorPane.width === originalInspector && timelinePane.height === originalTimeline;
                    core.drag("inspectorDivider", -60, 0);
                    core.drag("timelineDivider", 0, -40);
                } else if (mode === "layout-reset") {
                    core.click("resetLayout");
                } else if (mode === "layout-small") {
                    win.width = 1000;
                    win.height = 680;
                }
                phase++;
                return;
            }
            if (mode === "layout-key-drag" || mode === "layout-key-reset" || mode === "layout-key-constrained") {
                let expectedInspector = inspectorPane.width, expectedTimeline = timelinePane.height;
                let cleared = pendingInspectorSize < 0 && pendingTimelineSize < 0;
                if (mode === "layout-key-reset") { expectedInspector = 520; expectedTimeline = 105; }
                if (mode === "layout-key-constrained") {
                    expectedInspector = Math.max(330, workspace.width - explorerPane.width - 322);
                    expectedTimeline = Math.max(105, Math.min(350, verticalWorkspace.height - 306));
                    for (let index = 0; index < 40; ++index) { core.key("Ctrl+Alt+Left"); core.key("Ctrl+Alt+Up"); }
                    cleared = true;
                }
                win.close();
                let saved = core.loadLayout();
                core.testResult(JSON.stringify({passed: cleared && saved.inspector === expectedInspector && saved.timeline === expectedTimeline,
                    saved:saved, expectedInspector:expectedInspector, expectedTimeline:expectedTimeline, pendingCleared:cleared}));
                stop();
                return;
            }
            if (phase === 1 && mode === "layout-set") {
                dragged = inspectorPane.width > originalInspector + 30 && timelinePane.height > originalTimeline + 20;
                core.key("Ctrl+Alt+Left");
                core.key("Ctrl+Alt+Up");
                phase++;
                return;
            }
            let persisted = core.loadLayout();
            let acknowledged = !layoutSaveTimer.running && Math.abs(persisted.inspector - inspectorPane.width) <= 1
                && Math.abs(persisted.timeline - timelinePane.height) <= 1 && Math.abs(persisted.explorer - explorerPane.width) <= 1;
            if (mode === "layout-set" && !acknowledged && ++acknowledgementAttempts < 20) return;
            if (core.env("SHOWPSISI_SCREENSHOT")) core.capture(core.env("SHOWPSISI_SCREENSHOT"));
            core.testResult(JSON.stringify({
                passed: navigationKeysDidNotResize && (mode !== "layout-set" || acknowledged) && recordPane.width >= 310 && inspectorPane.width >= 330 && explorerPane.width >= 150 && timelinePane.height >= 105 && workspace.height >= 300 && (mode !== "layout-set" || dragged),
                navigationKeysDidNotResize: navigationKeysDidNotResize,
                explorer: explorerPane.width, inspector: inspectorPane.width, timeline: timelinePane.height,
                records: recordPane.width, workspace: workspace.width, dragged: dragged,
                windowWidth: win.width, windowHeight: win.height, savePending: layoutSaveTimer.running,
                persistedAcknowledged: acknowledged, acknowledgementAttempts: acknowledgementAttempts,
                saved: persisted,
                invalid_rejected: !core.saveLayout({version:1,explorer:-1,inspector:520,timeline:105}) && !core.saveLayout({version:99,explorer:180,inspector:520,timeline:105})
            }));
            stop();
        }
    }
    Timer {
        id: operationsParityTestTimer
        interval: 150
        repeat: true
        property real phase: 0
        property var checks: ({})
        property var change: null
        property var initial: null
        property int evidenceIndex: 0
        property var tooltipProbe: null
        property var tooltipOwner: null
        property var statusTooltipOwner: null
        onTriggered: {
            if (!analysisState.complete || core.busy || core.inspecting || core.comparing || core.diagnostics().pending > 0) return;
            if (phase === 0) {
                let service = serviceRows.find(function(s) {return s.id === 101;});
                inspect(service.source_id, service.id);
                phase = 1;
            } else if (phase === 1) {
                let row = tree.itemAtIndex(0);
                if (!row) return;
                tooltipProbe = row.rowTooltip;
                tooltipOwner = tooltipProbe.parent;
                statusTooltipOwner = statusTooltip.parent;
                tooltipProbe.open();
                phase = 1.1;
            } else if (phase === 1.1) {
                if (!tooltipProbe.visible) return;
                checks.tooltip_attached_values = tooltipProbe.anchorControl === tooltipOwner && tooltipProbe.anchorHovered === !!tooltipOwner.hovered && tooltipProbe.visible;
                // Reproduce the Popup parent-detach interval deterministically;
                // delegate retirement order differs between Windows and Linux.
                tooltipProbe.parent = null;
                statusTooltip.parent = null;
                phase = 1.2;
            } else if (phase === 1.2) {
                checks.tooltip_detached_hidden = !tooltipProbe.anchorControl && !tooltipProbe.anchorHovered && !tooltipProbe.visible;
                checks.tooltip_detached_text = statusTooltip.anchorText === "" && statusTooltip.text === "";
                tooltipProbe.parent = tooltipOwner;
                statusTooltip.parent = statusTooltipOwner;
                phase = 1.3;
            } else if (phase === 1.3) {
                checks.tooltip_anchor_rebound = tooltipProbe.anchorControl === tooltipOwner && statusTooltip.anchorControl === statusTooltipOwner && statusTooltip.text === statusTooltipOwner.text;
                core.hover("treeSearch");
                tooltipProbe = null; tooltipOwner = null; statusTooltipOwner = null;
                initial = {id:selected, sid:selectedService, at:analysisState.selected_packet};
                openComparison();
                fromPacket.text = String(analysisState.history[0].last_packet);
                toPacket.text = String(Number(analysisState.packets)-1);
                phase = 1.5;
            } else if (phase === 1.5) {
                // Tab visibility changes before layout polish; click the rendered control.
                if (!core.isExposed("swapComparison")) return;
                let a=fromPacket.text,b=toPacket.text;
                checks.swap_control = core.click("swapComparison") && fromPacket.text === b && toPacket.text === a;
                core.click("swapComparison");
                checks.history_presets = comparisonPresets().some(function(p) {return p.packet === analysisState.table_history[0].at_packet;}) && core.isExposed("comparisonPresetA") && core.isExposed("comparisonPresetB");
                compareSnapshots(0);
                phase = 2;
            } else if (phase === 2) {
                change=(comparison.changes || []).find(function(r) {return r.kind === "services" && r.identity.service_id === 103;});
                checks.service_change_found=!!change;
                if (!change) { core.testResult(JSON.stringify({passed:false,checks:checks}));stop();return; }
                inspectChange(change,"before",0);
                phase = 3;
            } else if (phase === 3) {
                let evidence=change.before.evidence[evidenceIndex];
                checks["evidence_"+evidenceIndex] = detail.id === evidence.id && detail.pid === evidence.pid && detail.native_table_at_packet === change.before.at_packet && analysisState.selected_packet === initial.at;
                evidenceIndex++;
                if (evidenceIndex < change.before.evidence.length) {
                    comparisonSource.currentIndex=evidenceIndex;
                    comparisonSource.activated(evidenceIndex);
                } else {
                    checks.multiple_sources=change.before.evidence.length >= 3;
                    core.click("tab_Services");
                    phase = 4;
                }
            } else if (phase === 4) {
                checks.original_selection_restored = selected === initial.id && selectedService === initial.sid && detail.id === initial.id && analysisState.selected_packet === initial.at && !selectedChange;
                openComparison();inspectChange(change,"before");
                phase = 5;
            } else if (phase === 5) {
                core.click("useComparisonSnapshot");
                phase = 6;
            } else if (phase === 6) {
                checks.applied_cutoff = tab === "Services" && selectedService === 103 && detail.id === change.before.evidence[0].id && detail.native_table_at_packet === change.before.at_packet && analysisState.selected_packet === change.before.at_packet;
                core.click("rename");
                checks.editor_original_target=editService.currentValue === 103 && renameName.text === "Sports HD";
                editService.currentIndex = editService.model.findIndex(function(s) {return s.id === 102;});
                editService.activated(editService.currentIndex);
                checks.editor_switch_target=editService.currentValue === 102 && renameName.text === "Culture HD";
                renameName.text="Discard this delayed preview";
                core.click("preview");
                renameName.text="Historical parity edit";
                phase = 7;
            } else if (phase === 7) {
                checks.stale_reply_discarded=!preview.token && !exportButton.enabled;
                core.click("preview");phase = 8;
            } else if (phase === 8) {
                checks.historical_target_preview=preview.service_id === 102 && preview.old_version === 1 && preview.after === "Historical parity edit" && exportButton.enabled;
                checks.editor_choices_unclipped=[editService,exportFormat].every(function(choice) {return choice.height >= 28 && choice.contentItem.height >= choice.contentItem.implicitHeight;});
                if (core.env("SHOWPSISI_SCREENSHOT")) core.capture(core.env("SHOWPSISI_SCREENSHOT") + ".edit.png");
                editService.currentIndex=0;editService.activated(0);
                checks.service_change_invalidates=!preview.token && !exportButton.enabled;
                renameDialog.close();
                core.testResult(JSON.stringify({passed:Object.keys(checks).every(function(k) {return checks[k];}),checks:checks}));
                stop();
            }
        }
    }
    Timer {
        id: comparisonTestTimer
        interval: 200
        repeat: true
        property real phase: 0
        property var checks: ({})
        property var layoutMetrics: ({})
        property int completedQueries: 0
        property int expectedQueryCompletion: 0
        property var changedService: null
        property var initialPacket: null
        onTriggered: {
            core.mark("comparison_phase_" + phase + "_busy_" + core.busy + "_inspect_" + core.inspecting + "_compare_" + core.comparing + "_queries_" + completedQueries + "_expected_" + expectedQueryCompletion + "_change_" + !!selectedChange);
            if (!analysisState.complete || core.busy || core.inspecting || core.comparing)
                return;
            if (phase === 0) {
                snapshot(analysisState.history[0].last_packet,analysisState.history[0].id);
                phase++;
            } else if (phase === 1) {
                if (detail.version !== 1) return;
                core.click("compareSnapshots");
                core.click("captureA");
                checks.capture_a = Number(fromPacket.text) === analysisState.selected_packet;
                core.click("latest");
                phase++;
            } else if (phase === 2) {
                if (analysisState.selected_packet !== null && analysisState.selected_packet !== undefined) return;
                core.click("captureB");
                checks.capture_b = Number(toPacket.text) === Number(analysisState.packets) - 1;
                initialPacket = analysisState.selected_packet;
                core.click("runComparison");
                checks.pending_controls = core.comparing && !core.click("runComparison") && !core.click("captureA") && !core.click("captureB") && !fromPacket.enabled && !toPacket.enabled;
                phase++;
            } else if (phase === 3) {
                if (!comparison.source) return;
                changedService = (comparison.changes || []).find(function (row) { return row.kind === "services" && (row.changed_fields || []).indexOf("name") >= 0; });
                checks.has_changes = !!changedService && comparison.total_changes > 0;
                if (!changedService) { core.testResult(JSON.stringify({passed:false,checks:checks,comparison:comparison})); stop(); return; }
                checks.controls_exposed = ["fromPacket", "toPacket", "captureA", "captureB", "runComparison"].every(function (name) { return core.isExposed(name); });
                checks.results_focus = recordList.activeFocus;
                checks.results_height = recordList.height >= 100;
                core.key("Ctrl+K");
                recordSearch.text = changedService.after.value.name;
                core.key("Return");
                checks.search_to_results = recordList.activeFocus && recordList.currentIndex === 0;
                core.key("Return");
                checks.keyboard_selection = !!selectedChange && selectedChange.key === changedService.key;
                recordSearch.clear();
                let index = comparison.changes.findIndex(function (row) { return row.kind === changedService.kind && row.key === changedService.key; });
                recordList.positionViewAtIndex(index, ListView.Contain);
                phase = 3.25;
            } else if (phase === 3.25) {
                // Change rows size to their field diffs; position again once the rebuilt rows are laid out.
                recordList.positionViewAtIndex(comparison.changes.findIndex(function (row) { return row.kind === changedService.kind && row.key === changedService.key; }), ListView.Contain);
                phase = 3.5;
            } else if (phase === 3.5) {
                let name = "record_" + comparison.changes.findIndex(function (row) { return row.kind === changedService.kind && row.key === changedService.key; });
                checks.change_row_exposed = core.isExposed(name);
                checks.change_row_click = core.click(name);
                scopeOpen=true;
                core.click("inspectBefore");
                phase = 4;
            } else if (phase === 4) {
                checks.before_cutoff = detail.native_table_at_packet === Number(fromPacket.text);
                checks.before_name = chosenService().name === changedService.before.value.name;
                checks.no_snapshot_mutation = analysisState.selected_packet === initialPacket;
                checks.inspector_controls_exposed = ["inspectBefore", "inspectAfter", "inspectionCutoff", "useComparisonSnapshot"].every(function (name) { return core.isExposed(name); });
                scopeOpen=false;
                core.click("inspectAfter");
                phase++;
            } else if (phase === 5) {
                checks.after_cutoff = detail.native_table_at_packet === Number(toPacket.text);
                checks.after_name = chosenService().name === changedService.after.value.name;
                checks.tree_height = tree.height >= 90;
                layoutMetrics = {windowWidth: win.width, windowHeight: win.height,
                    inspectorWidth: inspectorPane.width, inspectorHeight: inspectorPane.height,
                    treeHeight: tree.height, timelineHeight: timelinePane.height,
                    compact: compactInspector, titleFont: sectionTitle.font.toString(),
                    searchFont: treeSearch.font.toString(), searchHeight: treeSearch.height,
                    inspectorChildren: Array.from(inspectorColumn.children).filter(function(item) { return item.visible; }).map(function(item) {
                        return {type: item.toString(), x:item.x, y:item.y, width:item.width, height:item.height,
                            implicitHeight:item.implicitHeight, text:item.text || ""};
                    })};
                core.key("Shift+F6");
                checks.inspector_to_results = recordList.activeFocus;
                core.key("F6");
                checks.results_to_tree = tree.activeFocus;
                core.key("Ctrl+Shift+K");
                let treeShortcut = treeSearch.activeFocus;
                core.key("Return");
                checks.tree_search_to_tree = treeShortcut && tree.activeFocus;
                if (core.env("SHOWPSISI_SCREENSHOT")) core.capture(core.env("SHOWPSISI_SCREENSHOT"));
                core.click("tab_Services");
                checks.exit_preserves_snapshot = !selectedChange && analysisState.selected_packet === initialPacket;
                core.click("tab_Changes");
                toPacket.text = fromPacket.text;
                toPacket.forceActiveFocus();
                core.key("Return");
                checks.cutoff_enter_compares = core.comparing;core.mark("comparison_cutoff_enter_" + core.comparing);
                phase++;
            } else if (phase === 6) {
                if (!comparison.source) return;
                checks.same_cutoff_empty = comparison.total_changes === 0 && rows.length === 0;
                fromPacket.text = "-1";
                checks.invalid_cutoff = !core.click("runComparison") && !comparison.source;
                fromPacket.text = String(Number(analysisState.packets) - 1);
                toPacket.text = String((analysisState.history || [])[0].last_packet);
                core.click("runComparison");
                phase++;
            } else if (phase === 7) {
                if (!comparison.source) return;
                checks.reverse = comparison.from_packet > comparison.to_packet && comparison.total_changes > 0;
                changedService = comparison.changes.find(function (row) { return row.kind === "services" && (row.changed_fields || []).indexOf("name") >= 0; });
                recordList.positionViewAtIndex(comparison.changes.findIndex(function (row) { return row.kind === changedService.kind && row.key === changedService.key; }), ListView.Contain);
                phase = 7.5;
            } else if (phase === 7.5) {
                // Variable-height virtualized rows need a polished, exposed
                // delegate, not merely an allocated/recycled objectName.
                const index=comparison.changes.findIndex(function (row) { return row.kind === changedService.kind && row.key === changedService.key; });
                recordList.forceLayout();recordList.positionViewAtIndex(index,ListView.Contain);
                const target="record_" + index;
                if(!core.isExposed(target))return;
                checks.reverse_row_click=core.click(target);
                phase = 7.75;
            } else if (phase === 7.75) {
                checks.reverse_selection=!!selectedChange && selectedChange.kind===changedService.kind && selectedChange.key===changedService.key;
                if(!checks.reverse_row_click || !checks.reverse_selection){core.testResult(JSON.stringify({passed:false,checks:checks}));stop();return;}
                phase=8;
            } else if (phase === 8) {
                if(!core.isExposed("useComparisonSnapshot"))return;
                expectedQueryCompletion = completedQueries + 1;
                core.mark("comparison_use_snapshot_requested");
                checks.use_snapshot_click=core.click("useComparisonSnapshot");
                if(!checks.use_snapshot_click){core.testResult(JSON.stringify({passed:false,checks:checks}));stop();return;}
                phase++;
            } else if (phase === 9) {
                if (completedQueries < expectedQueryCompletion) {
                    core.mark("comparison_query_waiting");
                    return;
                }
                checks.explicit_use_snapshot = tab === "Services" && analysisState.selected_packet === changedService.after.at_packet && detail.native_table_at_packet === changedService.after.at_packet;
                scan();
                phase++;
            } else {
                checks.rescan_clears = !comparison.source && !selectedChange && !fromPacket.text && !toPacket.text;
                core.testResult(JSON.stringify({passed:Object.keys(checks).every(function (key) { return checks[key]; }),checks:checks,layout:layoutMetrics}));
                stop();
            }
        }
    }
    Timer {
        id: plainTextTimer
        interval: 200
        repeat: true
        property int phase: 0
        property bool baselinePassed: false
        onTriggered: {
            if (!analysisState.complete || core.inspecting || core.comparing || !detail.id || !serviceRows.length)
                return;
            if (phase === 0) {
                notice = serviceRows[0].name;
                core.hover("service_" + serviceRows[0].id);
                statusTooltip.open();
                phase++;
                return;
            }
            if (phase === 1) {
                let baseline = core.textSafetyReport("<img");
                baselinePassed = baseline.matched_text_items >= 3 && baseline.tooltip_text_items >= 1 && baseline.unsafe_text_items === 0;
                openComparison();
                fromPacket.text = "0";
                toPacket.text = String(Number(analysisState.packets) - 1);
                compareSnapshots(0);
                phase++;
                return;
            }
            if (phase === 2) {
                if (!comparison.source) return;
                let index = comparison.changes.findIndex(function (row) { return row.kind === "services" && String(changeValue(row).name).indexOf("<img") >= 0; });
                if (index < 0) { core.testResult(JSON.stringify({passed:false,comparison_literal:false})); stop(); return; }
                recordList.positionViewAtIndex(index, ListView.Center);
                activate(comparison.changes[index]);
                phase++;
                return;
            }
            if (phase === 3) {
                notice = serviceRows[0].name;
                statusTooltip.open();
                phase++;
                return;
            }
            let report = core.textSafetyReport("<img");
            report.literal_name = serviceRows[0].name.indexOf("<b>name</b>") >= 0;
            report.comparison_literal = !!selectedChange && changeTitle(selectedChange).indexOf("<b>name</b>") >= 0;
            report.passed = baselinePassed && report.comparison_literal && report.literal_name && report.matched_text_items >= 3 && report.tooltip_text_items >= 1 && report.unsafe_text_items === 0;
            core.capture(core.env("SHOWPSISI_SCREENSHOT"));
            core.testResult(JSON.stringify(report));
            stop();
        }
    }
    Timer {
        id: comparisonMarkersTimer
        interval: 100
        repeat: true
        property int phase: 0
        property int marked: -1
        property int waited: 0
        property var checks: ({})
        property var initialPacket: null
        property real expectedA: 0
        property real expectedB: 0
        property real targetPacket: -1
        // A pointer drag resolves to whole pixels; one pixel spans several packets in long captures.
        function nearPacket(text, expected) { return Math.abs(Number(text) - expected) <= Math.ceil((Number(analysisState.packets) - 1) / Math.max(1, densityStrip.width)); }
        function synced() {
            let maximum = Number(analysisState.packets) - 1;
            return comparisonMarkerA.visible && comparisonMarkerB.visible
                && comparisonMarkerA.value === Number(fromPacket.text) && comparisonMarkerB.value === Number(toPacket.text)
                && Math.abs(comparisonMarkerA.x + comparisonMarkerA.width / 2 - densityStrip.width * Number(fromPacket.text) / maximum) < 1
                && Math.abs(comparisonMarkerB.x + comparisonMarkerB.width / 2 - densityStrip.width * Number(toPacket.text) / maximum) < 1;
        }
        function finish() {
            stop();
            core.testResult(JSON.stringify({passed:Object.keys(checks).every(function(key){return checks[key];}),checks:checks,phase:phase}));
        }
        onTriggered: {
            if (marked !== phase) { marked = phase; waited = 0; }
            else if (++waited > 80) { checks["timeout_phase_" + phase] = false; finish(); return; }
            if (!analysisState.complete || core.busy || core.inspecting || core.comparing) return;
            let maximum = Number(analysisState.packets) - 1;
            let step = Math.max(1, Math.round(maximum / Math.max(1, densityStrip.binCount - 1)));
            if (phase === 0) {
                checks.initial_hidden = !comparisonMarkerA.visible && !comparisonMarkerB.visible;
                initialPacket = analysisState.selected_packet;
                openComparison(); fromPacket.text = String(Math.floor(maximum / 5)); toPacket.text = String(Math.floor(maximum * 4 / 5));
                phase = 1; return;
            }
            if (phase === 1) {
                checks.input_sync = synced();
                expectedA = Math.round(maximum * 0.3);
                checks.drag_a = core.drag("comparisonMarkerA", densityStrip.width * (expectedA - Number(fromPacket.text)) / maximum, 0);
                phase = 2; return;
            }
            if (phase === 2) {
                checks.drag_a = checks.drag_a && nearPacket(fromPacket.text, expectedA) && synced();
                checks.compare_focus_a = comparisonRun.activeFocus;
                expectedB = Math.round(maximum * 0.7);
                checks.drag_b = core.drag("comparisonMarkerB", densityStrip.width * (expectedB - Number(toPacket.text)) / maximum, 0);
                phase = 3; return;
            }
            if (phase === 3) {
                checks.drag_b = checks.drag_b && nearPacket(toPacket.text, expectedB) && synced();
                expectedB = Number(toPacket.text);
                checks.compare_focus_b = comparisonRun.activeFocus;
                checks.clamp_a = core.drag("comparisonMarkerA", densityStrip.width * 0.6, 0) && Number(fromPacket.text) === expectedB && Number(toPacket.text) === expectedB;
                checks.clamp_b = core.drag("comparisonMarkerB", -densityStrip.width * 0.6, 0) && Number(toPacket.text) === expectedB && Number(fromPacket.text) === expectedB;
                phase = 4; return;
            }
            if (phase === 4) {
                fromPacket.text = String(step * 2); toPacket.text = String(maximum - step * 2);
                densityStrip.forceActiveFocus(); core.key("Tab"); let aTab = comparisonMarkerA.activeFocus;
                core.key("Tab"); let bTab = comparisonMarkerB.activeFocus;
                core.key("Shift+Tab"); let aBack = comparisonMarkerA.activeFocus;
                core.key("Shift+Tab"); checks.tab_order = aTab && bTab && aBack && densityStrip.activeFocus;
                comparisonMarkerA.forceActiveFocus();
                core.key("Right"); let aBin = Number(fromPacket.text) === step * 3;
                core.key("Shift+Left"); let aPacket = Number(fromPacket.text) === step * 3 - 1;
                core.key("Left"); let aLeft = Number(fromPacket.text) === step * 2 - 1;
                core.key("Home"); let aHome = fromPacket.text === "0";
                core.key("End"); checks.keyboard_a = aBin && aPacket && aLeft && aHome && fromPacket.text === toPacket.text && synced() && comparisonMarkerA.activeFocus;
                comparisonMarkerB.forceActiveFocus();
                core.key("Shift+Right"); let bPacket = Number(toPacket.text) === maximum - step * 2 + 1;
                core.key("Right"); let bBin = Number(toPacket.text) === maximum - step + 1;
                core.key("End"); let bEnd = Number(toPacket.text) === maximum;
                core.key("Home"); core.key("Left");
                checks.keyboard_b = bPacket && bBin && bEnd && toPacket.text === fromPacket.text && synced() && comparisonMarkerB.activeFocus;
                phase = 5; return;
            }
            if (phase === 5) {
                fromPacket.text = "1.5"; let fractional = !comparisonMarkerA.visible;
                fromPacket.text = "-1"; let negative = !comparisonMarkerA.visible;
                fromPacket.text = String(maximum + 1); let overflow = !comparisonMarkerA.visible;
                fromPacket.clear(); densityStrip.forceActiveFocus(); core.key("Tab"); let onlyB = comparisonMarkerB.activeFocus;
                core.key("Shift+Tab"); let fromB = densityStrip.activeFocus;
                toPacket.clear(); densityStrip.forceActiveFocus(); core.key("Tab");
                checks.partial_tab_order = onlyB && fromB && !densityStrip.activeFocus;
                checks.invalid_hidden = fractional && negative && overflow && !comparisonMarkerA.visible && !comparisonMarkerB.visible;
                fromPacket.text = String(Math.floor(maximum / 5)); toPacket.text = String(Math.floor(maximum * 4 / 5)); tab = "Services";
                phase = 6; return;
            }
            if (phase === 6) {
                checks.retained_markers = synced();
                expectedA = Math.round(maximum * 0.3);
                checks.retained_drag = core.drag("comparisonMarkerA", densityStrip.width * (expectedA - Number(fromPacket.text)) / maximum, 0);
                phase = 7; return;
            }
            if (phase === 7) {
                checks.retained_drag = checks.retained_drag && nearPacket(fromPacket.text, expectedA) && synced() && tab === "Changes" && comparisonRun.activeFocus;
                checks.no_auto_requests = analysisState.selected_packet === initialPacket && !comparison.source && !core.comparing;
                let bin = Math.floor(densityStrip.binCount / 2); targetPacket = densityStrip.packetAtBin(bin);
                checks.density_snapshot = core.click("densityBin" + bin);
                phase = 8; return;
            }
            if (phase === 8) {
                if (analysisState.selected_packet !== targetPacket) return;
                checks.density_snapshot = checks.density_snapshot && densityCursor.visible;
                checks.snapshot_sync = synced();
                finish();
            }
        }
    }
    // UI/UX refresh self-check: family order, record column headers and the
    // density cursor / bin selection, exercised through the real application.
    Timer {
        id: refreshTestTimer
        interval: 200
        repeat: true
        property int phase: 0
        property int waited: 0
        property int marked: -1
        property int targetBin: 0
        property int targetPacket: -1
        property real cursorXAtSnapshot: -1
        property var checks: ({})
        function finish() {
            core.testResult(JSON.stringify({
                passed: Object.keys(checks).every(function (key) {
                    return checks[key];
                }),
                checks: checks,
                phase: phase,
                families: tableFamilies,
                service_columns_width: serviceColumnHeader.width,
                record_list_width: recordList.width,
                density_cursor_x: cursorXAtSnapshot,
                selected_packet: analysisState.selected_packet,
                target_packet: targetPacket
            }));
            stop();
        }
        onTriggered: {
            if (marked !== phase) {
                marked = phase;
                waited = 0;
                core.mark("refresh_phase_" + phase);
            } else if (++waited > 50) {
                // Bounded wait: a stuck phase reports failure instead of hanging.
                checks["timeout_phase_" + phase] = false;
                finish();
                return;
            }
            if (!analysisState.complete)
                return;
            if (phase < 3 && (!serviceRows.length || core.busy || core.inspecting || core.comparing))
                return;
            if (phase === 0) {
                tab = "Services";
                phase++;
                return;
            }
            if (phase === 1) {
                checks.pid_order = explorerRows.length > 1 && explorerRows[0].pid === -1 && explorerRows.every(function(row, i) { return i === 0 || row.pid >= explorerRows[i-1].pid; });
                checks.service_columns = serviceColumnHeader.visible && serviceColumnHeader.width > 0 && serviceColumnHeader.height > 0;
                tab = "Tables";
                phase++;
                return;
            }
            if (phase === 2) {
                checks.logical_tables = tableRows.length > 0 && tableRows.every(function(row) { return row.logical && row.group && row.sectionRecords.length > 0; });
                pidFilter = explorerRows[1].pid;
                phase++;
                return;
            }
            if (phase === 3) {
                checks.pid_filter = tableRows.length > 0 && tableRows.every(function(row) { return row.pid === pidFilter; });
                pidFilter = -1;
                filter = "";
                tab = "Services";
                checks.bin_positions = densityStrip.binCount > 1 && densityStrip.packetAtBin(0) === 0 && densityStrip.packetAtBin(densityStrip.binCount - 1) === Number(analysisState.packets) - 1;
                targetBin = Math.floor(densityStrip.binCount / 2);
                targetPacket = densityStrip.packetAtBin(targetBin);
                checks.bin_click = core.click("densityBin" + targetBin);
                phase++;
                return;
            }
            if (phase === 4) {
                if (!backendReady || core.inspecting) return;
                if (Number(analysisState.selected_packet) !== targetPacket)
                    return;
                checks.bin_click_snapshot = Number(analysisState.selected_packet) === targetPacket;
                checks.density_cursor = densityCursor.visible && densityCursor.x >= 0 && densityCursor.x <= densityStrip.width;
                cursorXAtSnapshot = densityCursor.x;
                core.capture(core.env("SHOWPSISI_SCREENSHOT") + ".cursor.png");
                snapshot(-1);
                phase++;
                return;
            }
            if (phase === 5) {
                if (analysisState.selected_packet !== null && analysisState.selected_packet !== undefined)
                    return;
                checks.latest_restored = true;
                core.capture(core.env("SHOWPSISI_SCREENSHOT"));
                finish();
            }
        }
    }
    Timer {
        id: workbenchPagingTimer
        interval:100; repeat:true
        property int phase:0
        property int ticks:0
        property string target:""
        property var checks:({})
        onTriggered: {
            if(++ticks>150) {stop();core.testResult(JSON.stringify({passed:false,phase:phase,checks:checks}));return;}
            if(!analysisState.complete || core.busy || core.inspecting) return;
            if(phase===0) {tab="Tables";phase=10;return;}
            if(phase===10) {checks.first=logicalTableCount===101 && tableRows.length===100;checks.next_click=core.click("tableNext");phase=1;return;}
            if(phase===1) {checks.last=tablePage===1 && tableRows.length===1;target=tableRows[0].id;recordList.currentIndex=0;recordList.forceActiveFocus();core.key("Return");phase=2;return;}
            if(phase===2) {checks.selected=detail.id===target && historyRows.length===1;snapshot(0);phase=3;return;}
            // Wait for the requested snapshot response; the tick limit still reports a missing clamp.
            if(phase===3 && analysisState.selected_packet!==0 && ticks<140) return;
            if(phase===3) {checks.clamped=analysisState.selected_packet===0 && tablePage===0 && logicalTableCount===1 && tableRows.length===1;core.capture(core.env("SHOWPSISI_SCREENSHOT"));stop();core.testResult(JSON.stringify({passed:Object.keys(checks).every(function(k){return checks[k];}),checks:checks}));}
        }
    }
    // Script-only driver: real sample, actual controls and core-backed selection.
    Timer {
        id: referenceJumpsTimer
        interval:100; repeat:true
        property int phase:0
        property int ticks:0
        property string path:""
        property string target:""
        property string origin:""
        property var checks:({})
        function finish() {stop();core.testResult(JSON.stringify({passed:phase===9 && Object.keys(checks).every(function(k){return checks[k];}),phase:phase,checks:checks}));}
        function restored() {return detail.id===origin && selected===origin && selectedService===-1 && tab==="Tables" && filter==="PAT" && pidFilter===0 && groupedTables && evidenceScope==="Merged" && inspectorView==="Structure" && treeSearch.text==="pmt_pid";}
        function focusedRow() {let index=treeRows.findIndex(function(r){return r.path===path;});tree.currentIndex=index;tree.positionViewAtIndex(index,ListView.Center);tree.forceActiveFocus();}
        onTriggered: {
            if(++ticks>180){finish();return;}
            if(!analysisState.complete || !backendReady || core.inspecting || protocolRestoring)return;
            if(phase===0){checks.pat_explorer=core.click("explorerRow:0:PAT");phase=1;return;}
            if(phase===1){checks.pat_record=core.click("record_0");phase=2;return;}
            if(phase===2){
                if(detail.name!=="PAT")return;
                origin=detail.id;inspectorView="Structure";evidenceScope="Merged";treeSearch.text="pmt_pid";
                let row=treeRows.find(function(r){return r.label==="pmt_pid" && r.reference && r.reference.pid===0x100;});
                checks.pat_link=!!row && row.reference.label==="Go to PMT · PID 0x0100 (256)";
                if(!row){finish();return;}path=row.path;target=row.reference.id;focusedRow();phase=21;return;
            }
            // The filtered tree is laid out after this tick; position the row again before a pointer click.
            if(phase===21){focusedRow();phase=3;return;}
            if(phase===3){checks.reference_exposed=core.isExposed("reference:"+path);checks.click_control=core.click("reference:"+path);phase=4;return;}
            if(phase===4){
                checks.click_jump=detail.id===target && selected===target && detail.name==="PMT" && detail.pid===0x100 && tab==="Tables" && !groupedTables && pidFilter===0x100;
                tree.forceActiveFocus();core.key("Alt+Left");phase=5;return;
            }
            if(phase===5){checks.click_back=restored();focusedRow();core.key("Ctrl+Return");phase=6;return;}
            if(phase===6){checks.keyboard_jump=detail.id===target && selected===target && detail.name==="PMT";core.key("Alt+Left");phase=7;return;}
            if(phase===7){checks.keyboard_back=restored();focusedRow();core.key("Tab");checks.tab_reachable=!!win.activeFocusItem && win.activeFocusItem.objectName==="reference:"+path;core.key("Return");phase=8;return;}
            if(phase===8){checks.tab_jump=detail.id===target && selected===target;core.key("Alt+Left");phase=80;return;}
            if(phase===80){checks.tab_back=restored();tab="Services";phase=81;return;}
            if(phase===81){checks.service_click=core.click("service_101");phase=82;return;}
            if(phase===82){
                if(detail.name!=="SDT")return;
                treeSearch.text="logical_channel_number";
                let privateRows=treeRows.filter(function(r){return r.label==="logical_channel_number" && r.path.indexOf("descriptors/")>=0;});
                checks.private_no_link=privateRows.length>0 && privateRows.every(function(r){return !r.reference;});tab="EPG";phase=83;return;
            }
            if(phase===83){checks.event_click=core.click("record_0");phase=84;return;}
            if(phase===84){
                if(detail.name!=="EIT")return;
                origin=detail.id;treeSearch.text="service_id";
                let row=treeRows.find(function(r){return r.reference && r.reference.kind==="service";});
                checks.service_link=!!row;if(!row){finish();return;}path=row.path;target=row.reference.id;focusedRow();phase=85;return;
            }
            if(phase===85){checks.service_jump_control=core.click("reference:"+path);phase=86;return;}
            if(phase===86){checks.service_jump=tab==="Services" && selected===target && selectedService===101 && detail.name==="SDT";core.key("Alt+Left");phase=87;return;}
            if(phase===87){checks.service_back=tab==="EPG" && detail.id===origin && selected===origin && selectedService===-1 && treeSearch.text==="service_id";phase=9;finish();}
        }
    }
    Timer {
        id: commandPaletteTimer
        interval: 100
        repeat: true
        property int phase: 0
        property int ticks: 0
        property bool oldTheme: false
        property string origin: ""
        property int originService: -1
        property var checks: ({})
        function finish() {stop();core.testResult(JSON.stringify({passed:phase===10 && Object.keys(checks).every(function(k){return checks[k];}),phase:phase,checks:checks}));}
        onTriggered: {
            if(++ticks>180){checks.timeout=false;finish();return;}
            if(!backendReady || core.inspecting || protocolRestoring)return;
            if(phase===0){source.forceActiveFocus();core.key("Ctrl+K");recordSearch.text=">export";phase=1;return;}
            if(phase===1){
                checks.export_disabled=commandPalette.visible && paletteRows.length===1 && !!paletteRows[0].reason;
                core.key("Return");checks.export_guard=!renameDialog.visible && !core.busy;
                core.key("Escape");checks.export_escape=source.activeFocus && recordSearch.text==="";
                scan();phase=2;return;
            }
            if(!analysisState.complete)return;
            if(phase===2){
                origin=detail.id;originService=selectedService;oldTheme=lightTheme;
                source.forceActiveFocus();core.key("Ctrl+K");checks.search_focus=recordSearch.activeFocus;
                recordSearch.text="Sports UHD";checks.plain_filter=rows.length===1 && rows[0].id===103;
                recordSearch.text=">ThEmE";phase=3;return;
            }
            if(phase===3){checks.theme_suggestion=commandPalette.visible && paletteRows.length===1 && paletteRows[0].id==="theme" && rows.length===1;core.key("Return");phase=4;return;}
            if(phase===4){
                checks.theme_command=lightTheme!==oldTheme && recordSearch.text==="Sports UHD" && source.activeFocus;
                core.key("Ctrl+K");recordSearch.text="#0x0000";phase=5;return;
            }
            if(phase===5){checks.pid_suggestion=commandPalette.visible && paletteRows.length===1 && paletteRows[0].description==="PID 0x0000 (0)";core.key("Return");phase=6;return;}
            if(phase===6){checks.pid_jump=detail.name==="PAT" && detail.pid===0 && tab==="Tables" && pidFilter===0 && selected===detail.id;core.key("Alt+Left");phase=7;return;}
            if(phase===7){checks.pid_back=tab==="Services" && detail.id===origin && selectedService===originService && recordSearch.text==="Sports UHD";core.key("Ctrl+K");recordSearch.text="#pid 8190";phase=8;return;}
            if(phase===8){
                core.mark("palette_unknown_"+JSON.stringify({visible:commandPalette.visible,rows:paletteRows.length,target:paletteTarget,input:paletteInput ? paletteInput.text : null,search:recordSearch.text,origin:origin,selected:selected,detail:detail.id}));
                checks.unknown_pid=commandPalette.visible && !paletteRows.length && paletteTarget.message==="No PID 0x1FFE in this stream";
                core.key("Return");checks.unknown_unchanged=selected===origin && detail.id===origin;
                core.key("Escape");checks.escape_focus=!commandPalette.visible && recordList.activeFocus && recordSearch.text==="Sports UHD";
                core.key("Ctrl+K");recordSearch.text="Sports UHD";core.key("Return");phase=9;return;
            }
            if(phase===9){checks.plain_search=recordList.activeFocus && recordList.currentIndex===0 && rows.length===1 && rows[0].id===103;phase=10;finish();}
        }
    }
    // Real shared-PID wire fixture, actual mouse/key delivery, no fabricated state.
    Timer {
        id: explorerParityTimer
        interval: 150
        repeat: true
        property int phase: 0
        property int ticks: 0
        property var checks: ({})
        function chooseFamily(keys) {
            checks["family_click_"+phase] = core.click("tableFamilyFilter");
            core.key("Home"); keys.forEach(function(key) {core.key(key);}); core.key("Return");
        }
        function finish() {
            core.capture(core.env("SHOWPSISI_SCREENSHOT"));
            core.testResult(JSON.stringify({passed:Object.keys(checks).every(function(key) {return checks[key];}),checks:checks,phase:phase,explorer:explorerRows}));
            stop();
        }
        onTriggered: {
            if (++ticks > 180) {checks.timeout=false; finish(); return;}
            if (!analysisState.complete || core.busy || core.inspecting || core.comparing) return;
            if (phase === 0) {
                checks.logical_counts = explorerRows[0].count === 7 && analysisState.tables.length === 9 && explorerRows.find(function(r){return r.name==="SDT";}).count === 2;
                checks.shared_pid_types = explorerRows.filter(function(r){return r.pid===17;}).length === 3;
                checks.no_service_highlight = !explorerRows.some(explorerSelected);
                checks.click_sdt = core.click("explorerRow:17:SDT");
            } else if (phase === 1) {
                checks.sdt_scope = pidFilter === 17 && filter === "SDT" && rawTableRows.length === 2;
                core.key("Home"); core.key("Down"); core.key("Down");
                checks.focus_does_not_select = filter === "SDT" && explorerRows[explorerList.currentIndex].name === "BAT";
                core.key("Return");
            } else if (phase === 2) {
                checks.enter_selects_type = filter === "BAT" && pidFilter === 17 && rawTableRows.length === 1;
                core.key("End"); core.key("Space");
            } else if (phase === 3) {
                checks.space_selects_pid = filter === "PMT" && pidFilter === 257 && rawTableRows.length === 1;
                chooseFamily(["Down","Down"]);
            } else if (phase === 4) {
                checks.family_all_pids = filter === "PMT" && pidFilter === -1 && rawTableRows.length === 2 && !explorerRows.some(explorerSelected);
                chooseFamily(["End"]);
            } else if (phase === 5) {
                checks.private_available = filter === "Private / other" && rawTableRows.length === 1;
                chooseFamily(["Down","Down","Down","Down","Down"]);
            } else if (phase === 6) {
                checks.empty_type_available = filter === "NIT" && rawTableRows.length === 0;
                checks.all_click = core.click("explorerRow:-1:All tables");
                checks.bad_crc_click = core.click("toggleInvalidSections");
            } else if (phase === 7) {
                checks.all_resets_scope = filter === "" && pidFilter === -1 && explorerSelected(explorerRows[0]);
                checks.bad_crc_preserves_counts = showInvalidSections && rawTableRows.length === 9 && explorerRows[0].count === 7;
                snapshot(0);
            } else if (phase === 8) {
                if (analysisState.selected_packet !== 0) return;
                checks.snapshot_counts = explorerRows[0].count === 1 && explorerRows.length === 2;
                snapshot(-1);
            } else {
                if (analysisState.selected_packet !== null && analysisState.selected_packet !== undefined) return;
                checks.latest_counts = explorerRows[0].count === 7;
                tab = "Services";
                checks.tab_highlight = !explorerRows.some(explorerSelected);
                finish(); return;
            }
            phase++;
        }
    }
    // Native integration exercises the same controls and bridge as the workbench.
    Timer {
        id: lifecycleTestTimer
        interval: 100
        repeat: true
        property int phase: 0
        property int settledTicks: 0
        property bool lateFramesRequested: false
        property bool lateFramesAcknowledged: false
        property var checks: ({})
        function finish() {
            let passed = Object.keys(checks).length > 0 && Object.keys(checks).every(function (name) { return !!checks[name]; });
            if (core.env("SHOWPSISI_SCREENSHOT")) core.capture(core.env("SHOWPSISI_SCREENSHOT"));
            core.testResult(JSON.stringify({passed:passed,checks:checks,state:analysisState,notice:notice,error:core.error,availability:core.availability}));
            stop();
        }
        function cleanIntentions() {
            return selected === "" && selectedService === -1 && !selectedChange && !Object.keys(comparison).length &&
                !Object.keys(preview).length && snapshotTarget === "" && snapshotTargetService === -1 &&
                !Object.keys(detail).length && !core.inspecting && !core.comparing && !renameDialog.visible;
        }
        onTriggered: {
            let mode = core.env("SHOWPSISI_SCRIPT");
            if (mode.indexOf("lifecycle-death") === 0 || mode === "lifecycle-startup") {
                if (phase === 0 && mode === "lifecycle-death") {
                    if (!analysisState.complete || !detail.native_table || core.inspecting) return;
                    core.click("rename");
                    renameName.text = "Backend lifecycle preview";
                    core.click("preview");
                    phase = 1;
                    return;
                }
                if (phase === 1 && mode === "lifecycle-death") {
                    if (!preview.token) return;
                    checks.had_evidence_and_preview = !!detail.native_table && !!analysisState.complete && !!preview.token;
                    core.mark("backend_death_ready");phase = 2;return;
                }
                if (phase === 0 && mode === "lifecycle-death-active") {
                    if (!core.busy || !scanProgress.observations) return;
                    checks.was_scanning = !scanProgress.complete;
                    core.mark("backend_death_ready");phase = 2;return;
                }
                if (core.availability !== "disconnected") return;
                checks.disconnected = !core.available && !core.busy && !core.cancelling;
                checks.no_cached_evidence = !Object.keys(analysisState).length && cleanIntentions();
                checks.actions_disabled = !core.click("analyzeSource") && !core.click("agentApi") && !core.click("rename") && !core.click("preview") && !core.click("export") && !core.click("latest") && !core.click("runComparison") && !core.click("openSource");
                checks.restart_guidance = core.error.indexOf("Restart the application") >= 0;
                core.key("Ctrl+Return");
                if (++settledTicks >= 4) { checks.no_replay = !core.busy && !core.available; finish(); }
                return;
            }
            if (phase === 0 && (mode === "lifecycle-stale" || mode === "lifecycle-complete-race")) {
                if (!analysisState.complete || !core.inspecting) return;
                checks.pending_old_inspect = true;
                checks.legacy_presentation_ready = !presentationPending;
                checks.legacy_table_state_ready = tableViewState===analysisState;
                checks.legacy_record_state_ready = recordViewState===analysisState;
                checks.legacy_services_ready = serviceRows===analysisState.services;
                // The adversarial legacy fixture intentionally omits table_groups.
                checks.legacy_tables_ready = JSON.stringify(rawTableRows)===JSON.stringify(Shared.workbench.tables(analysisState,pidFilter,filter,showInvalidSections,recordSearch.query).sections);
                core.mark("legacy_rows_" + rawTableRows.length + "_source_" + (analysisState.tables || []).length);
                scan();phase = 1;return;
            }
            if (phase <= 1) {
                if (!core.busy || !scanProgress.observations) return;
                checks.accepted_progress = scanProgress.source.indexOf("poison") < 0 && !detail.id;
                if (core.env("SHOWPSISI_SCREENSHOT")) core.capture(core.env("SHOWPSISI_SCREENSHOT") + ".scanning.png");
                // These pending UI intentions must not survive a cancellation.
                snapshotTarget = "old-pending-section";snapshotTargetService = 101;
                selected = "old-selection";selectedService = 101;
                preview = {token:"old-preview"};comparison = {source:"old-comparison"};
                selectedChange = {key:"old-change"};
                checks.cancel_exposed = core.isExposed("cancelAnalysis");
                cancelButton.forceActiveFocus();
                core.key("Space");
                checks.cancelling = core.busy && core.cancelling;
                checks.cleared_intentions = cleanIntentions();
                checks.no_parallel_scan = !core.click("analyzeSource") && !core.click("cancelAnalysis");
                core.key("Ctrl+Return");
                checks.shortcut_locked = core.busy && core.cancelling;
                core.mark("cancel_control_checked");
                phase = 2;return;
            }
            if (phase === 2) {
                if (core.busy) return;
                if (mode === "lifecycle-stale" || mode === "lifecycle-complete-race") {
                    if (!lateFramesRequested) {
                        lateFramesRequested = true;
                        core.send("fixture_late_frames");
                    }
                    if (!lateFramesAcknowledged) return;
                }
                if (mode === "lifecycle-complete-race") {
                    checks.honest_completion_race = !!analysisState.complete && analysisState.analysis_status === "complete";
                    checks.no_auto_inspect = cleanIntentions();
                    checks.no_false_cancellation = notice.indexOf("Scan finished before cancellation took effect") === 0 && !inspected;
                } else {
                    checks.cancelled = analysisState.analysis_status === "cancelled" && !analysisState.complete;
                    checks.empty_evidence = !serviceRows.length && !(analysisState.tables || []).length && !issues.length && cleanIntentions();
                    checks.no_false_completion = notice.indexOf("Scan cancelled") === 0 && !inspected;
                }
                checks.not_disconnected = core.available && !core.cancelling && !core.error;
                core.mark("cancelled_state_checked");
                if (core.env("SHOWPSISI_SCREENSHOT")) core.capture(core.env("SHOWPSISI_SCREENSHOT") + ".cancelled.png");
                checks.can_rescan = core.click("analyzeSource");
                phase = 3;return;
            }
            if (phase === 3) {
                if (core.busy || core.inspecting || !analysisState.complete || !detail.id) return;
                checks.rescan_completed = analysisState.source.indexOf("poison") < 0 && (mode === "lifecycle-stale" || mode === "lifecycle-complete-race" || serviceRows.length === 6);
                checks.inspected_new_scan = !!detail.id && detail.id !== "poison" && inspected;
                checks.normal_completion = notice.indexOf("Scan complete") === 0 && !core.error;
                finish();
            }
        }
    }
    Timer {
        id: autoTimer
        interval: Math.max(1, autoDelay)
        onTriggered: {
            if (core.availability === "starting") restart();
            else scan();
        }
    }
    Timer {
        id: allBadEvidenceTestTimer
        interval: 50
        repeat: true
        property int phase: 0
        property double deadline: Date.now()+20000
        property var checks: ({})
        onTriggered: {
            if(Date.now()>deadline) {stop();core.testResult(JSON.stringify({passed:false,phase:phase,checks:checks,error:core.error}));return;}
            if(!analysisState.complete || core.busy || core.inspecting) return;
            if(phase===0) {
                checks.hidden_default=tableRows.length===1 && tableRows[0].hiddenEvidence && rawTableRows.length===0 && !detail.id && hiddenInvalidCount===1 && tab==="Tables";
                checks.toggle_visible=core.click("toggleInvalidSections");phase=1;return;
            }
            if(phase===1) {
                if(tableRows.length!==1) return;
                activate(tableRows[0]);phase=2;return;
            }
            if(phase===2) {
                if(!detail.id) return;
                checks.all_invalid=detail.crc.status==="invalid" && selectedGroup.validity==="all_invalid";
                checks.missing_distinct=selectedGroup.missing_section_numbers.length===1 && selectedGroup.missing_section_numbers[0]===1;
                core.capture(core.env("SHOWPSISI_SCREENSHOT"));stop();core.testResult(JSON.stringify({passed:Object.keys(checks).every(function(k){return checks[k];}),checks:checks}));
            }
        }
    }
    Timer {
        id: supersededEvidenceTestTimer
        interval: 50
        repeat: true
        property int phase: 0
        property double deadline: Date.now()+20000
        property string target: ""
        property var checks: ({})
        onTriggered: {
            if(Date.now()>deadline) {stop();core.testResult(JSON.stringify({passed:false,phase:phase,checks:checks,error:core.error}));return;}
            if(!analysisState.complete || core.busy || core.inspecting || !detail.id) return;
            if(phase===0) {
                target=analysisState.tables.find(function(r) {return r.version===1 && r.section===0;}).id;
                tab="Tables";evidenceScope="Merged";inspect(target,-1,3);phase=1;return;
            }
            if(phase===1) {
                if(detail.id!==target) return;
                checks.superseded=detail.merged.complete===false && detail.merged.tsduck_xml===null;
                checks.no_old_native=treeRows.every(function(r) {return r.path.indexOf("native/")!==0;}) && !detail.merged.native_table;
                inspectorView="XML";phase=2;return;
            }
            if(phase===2) {
                checks.no_xml_leak=xmlEvidence.text.indexOf("<SDT")<0;
                checks.exact_section_available=!!detail.section_native_text && detail.version===1;
                inspect(target,-1,1);phase=3;return;
            }
            if(phase===3) {
                if(detail.native_table_at_packet!==1) return;
                checks.historical_complete=detail.merged.complete===true && detail.native_table_sources.length===2 && detail.native_table_sources.every(function(r) {return r.version===1;});
                inspectorView="Structure";phase=4;return;
            }
            if(phase===4) {
                checks.historical_native=treeRows.some(function(r) {return r.path==="native";});
                let sibling=siblingSections.find(function(r) {return r.version===1 && r.section===1;});
                target=sibling.id;inspect(target,-1,1);phase=5;return;
            }
            if(phase===5) {
                if(detail.id!==target) return;
                checks.sibling_exact=detail.section===1 && detail.identity.section_number===1 && detail.native_table_sources.length===2;
                core.capture(core.env("SHOWPSISI_SCREENSHOT"));stop();core.testResult(JSON.stringify({passed:Object.keys(checks).every(function(k){return checks[k];}),checks:checks}));
            }
        }
    }
    Timer {
        id: sectionEvidenceTestTimer
        interval: 50
        repeat: true
        property int phase: 0
        property double deadline: Date.now() + 20000
        property var checks: ({})
        property string target: ""
        property int expandedCount: 0
        onTriggered: {
            if (Date.now() > deadline) {
                stop(); core.testResult(JSON.stringify({passed:false,phase:phase,checks:checks,error:core.error})); return;
            }
            if (!analysisState.complete || core.busy || core.inspecting || !detail.id) return;
            if (phase === 0) {
                tab="Tables"; filter=""; selectedService=-1; sectionGroupOpen=true;
                checks.hidden_crc = hiddenInvalidCount > 0 && tableRows.every(function(r) { return r.crc?.status !== "invalid"; });
                target=(analysisState.tables || []).find(function(r) { return r.section === 0 && r.valid; }).id;
                inspect(target,-1); phase=1; return;
            }
            if (phase === 1) {
                if (detail.id !== target) return;
                checks.headers = detail.crc?.transmitted_hex?.length === 8 && detail.identity?.section_number === 0;
                checks.arrivals = detail.distribution?.observation_count >= 2 && detail.distribution?.first_packet === 0 && detail.distribution?.last_packet > 0;
                checks.merged_sources = detail.merged?.complete === true && detail.native_table_sources.length === 2 && selectedGroup.validity === "mixed";
                checks.sources_visible = siblingSections.length === 2;
                // The section choice becomes visible with this detail; check exposure after its layout pass.
                phase=11; return;
            }
            if (phase === 11) {
                checks.scope_control = core.isExposed("evidenceScope") && core.isExposed("sectionChoice");
                checks.toggle_click = core.click("toggleInvalidSections"); phase=2; return;
            }
            if (phase === 2) {
                if (!showInvalidSections || siblingSections.length !== 3) return;
                checks.reveals_bad = rawTableRows.some(function(r) { return r.crc?.status === "invalid"; }) && tableRows.some(function(r) { return r.group?.validity === "mixed"; });
                core.click("expandAllSections"); phase=3; return;
            }
            if (phase === 3) {
                expandedCount=treeRows.length;
                checks.expanded = treeRows.some(function(r) { return r.depth > 2; }) && treeRows.every(function(r) { return !r.branch || !r.closed; });
                tree.positionViewAtIndex(treeRows.findIndex(function(r) { return r.path === "native"; }), ListView.Beginning); phase=29; return;
            }
            if (phase === 29) {
                checks.native_mouse_fold = core.click("tree:native"); phase=30; return;
            }
            if (phase === 30) {
                let nativeRow=treeRows.find(function(r) {return r.path === "native";});
                checks.native_folded = nativeRow?.closed === true;
                tree.positionViewAtIndex(treeRows.findIndex(function(r) { return r.path === "native"; }), ListView.Beginning); phase=301; return;
            }
            if (phase === 301) {
                checks.native_mouse_unfold = core.click("tree:native"); phase=31; return;
            }
            if (phase === 31) {
                let index=treeRows.findIndex(function(r) {return r.path === "native";});
                checks.native_unfolded = !treeRows[index].closed;
                tree.currentIndex=index;tree.forceActiveFocus();core.key("Left");phase=32;return;
            }
            if (phase === 32) {
                checks.native_key_folded = treeRows.find(function(r) { return r.path === "native"; }).closed;
                core.key("Right");phase=33;return;
            }
            if (phase === 33) {
                checks.native_key_unfolded = !treeRows[tree.currentIndex].closed;
                core.key("Right");phase=34;return;
            }
            if (phase === 34) {
                checks.native_key_child = treeRows[tree.currentIndex].depth > 0;
                core.click("collapseAllSections");phase=4;return;
            }
            if (phase === 4) {
                checks.collapsed = treeRows.length < expandedCount && treeRows.every(function(r) { return r.depth === 0 && (!r.branch || r.closed); });
                checks.section_scope_click=core.click("sectionScope"); collapsed={header:false}; phase=5; return;
            }
            if (phase === 5) {
                checks.section_scope = !treeRows.some(function(r) { return r.path.indexOf("native/")===0 || r.path === "provenance"; }) && !!detail.section_native_text;
                // Show XML first; a newly visible view is laid out before the next scripted click.
                inspectorView="XML"; phase=51; return;
            }
            if (phase === 51) {
                checks.merged_scope_click=core.click("mergedScope"); phase=6; return;
            }
            if (phase === 6) {
                checks.xml_plain = xmlEvidence.textFormat === TextEdit.PlainText && xmlEvidence.text === detail.tsduck_xml;
                checks.xml_highlighter = core.xmlHighlightActive(xmlEvidence.textDocument);
                core.capture(core.env("SHOWPSISI_SCREENSHOT") + ".xml.png");
                inspectorView="Structure"; evidenceScope="Merged"; collapsed={header:true,native:false,provenance:false,fields:true}; tree.positionViewAtBeginning(); phase=7; return;
            }
            if (phase === 7) {
                core.capture(core.env("SHOWPSISI_SCREENSHOT"));
                stop(); core.testResult(JSON.stringify({passed:Object.keys(checks).every(function(k) { return checks[k]; }),checks:checks,tree_height:tree.height,selected:detail.id}));
            }
        }
    }
    Timer {
        id: refinementTestTimer
        interval: 80
        repeat: true
        property int phase: 0
        property var checks: ({})
        property bool initialLight: false
        property int initialTableCount: 0
        property double deadline: Date.now()+20000
        onTriggered: {
            if(Date.now()>deadline) {stop();core.testResult(JSON.stringify({passed:false,phase:phase,checks:checks,error:core.error}));return;}
            if(!analysisState.complete || core.busy || core.inspecting || !detail.id) return;
            if(phase===0) {
                initialLight=lightTheme; initialTableCount=logicalTableCount;
                checks.numeric_pid_order=explorerRows.every(function(r,i) {return i===0 || explorerRows[i-1].pid<=r.pid;});
                checks.grouped=tableRows.every(function(r) {return r.logical;}) && tableRows.length<=rawTableRows.length;
                checks.packet_axis=analysisState.timing.seconds_per_packet > 0 ? axisLabel(1).endsWith(" s") : axisLabel(1)==="#1";
                checks.service_columns=serviceRows.every(function(r) {return r.service_type!==undefined && r.service_type_name!==undefined && r.video_pids!==undefined && r.audio_pids!==undefined;});
                if(core.env("SHOWPSISI_EXPECT_MEDIA")==="1") checks.media_evidence=serviceRows[0].video_pids.join(",")==="512" && serviceRows[0].audio_pids.join(",")==="513,514" && !!serviceRows[0].service_type_name;
                tab="Tables";phase=10;return;
            }
            if(phase===10) {recordList.currentIndex=0;recordList.forceActiveFocus();core.key("Space");phase=1;return;}
            if(phase===1) {
                checks.expanded_exact=tableRows.some(function(r) {return r.exact;});
                checks.stable_logical_count=logicalTableCount===initialTableCount && recordCountLabel.text.indexOf(initialTableCount + " tables · " + rawTableRows.length + " sections")===0;
                recordList.currentIndex=1;core.key("Return");phase=2;return;
            }
            if(phase===2) {
                checks.exact_selection=detail.id===rows[1].id;
                checks.theme_click=core.click("themeToggle");phase=3;return;
            }
            if(phase===3) {
                checks.theme_changed=lightTheme!==initialLight && core.loadTheme()===(lightTheme?"light":"dark");
                core.click("themeToggle"); inspectorView="XML";phase=4;return;
            }
            if(phase===4) {
                checks.xml_highlight=core.xmlHighlightActive(xmlEvidence.textDocument);
                core.capture(core.env("SHOWPSISI_SCREENSHOT")+".xml.png");
                inspectorView="Structure";tab="Services";defaultInspect();phase=5;return;
            }
            if(phase===5) {
                checks.theme_restored=lightTheme===initialLight;
                recordSearch.forceActiveFocus();core.key("Ctrl+A");core.key("Escape");
                checks.input_focus=recordSearch.activeFocus;
                checks.tree_minimum=tree.height>=90;
                core.capture(core.env("SHOWPSISI_SCREENSHOT"));stop();core.testResult(JSON.stringify({passed:Object.keys(checks).every(function(k){return checks[k];}),checks:checks,theme:lightTheme?"light":"dark",tree_height:tree.height}));
            }
        }
    }
    Timer {
        id: protocolCardsTestTimer
        interval: 100
        repeat: true
        property int phase: 0
        property var checks: ({})
        property double deadline: Date.now()+20000
        onTriggered: {
            if(Date.now()>deadline){stop();core.testResult(JSON.stringify({passed:false,phase:phase,checks:checks,error:core.error}));return;}
            if(!analysisState.complete || core.busy || core.inspecting)return;
            if(phase===0){let row=(analysisState.tables || []).find(function(x){return x.table_id===0x74;});if(!row)return;inspect(row.id,-1);phase=1;return;}
            if(phase===1){if(detail.table_id!==0x74)return;checks.metadata_tab=core.click("inspector_Metadata");phase=2;return;}
            if(phase===2){checks.cards=protocolCardModel.total>40 && protocolCardModel.cards.length===20;checks.evidence=protocolCardModel.cards.some(function(x){return JSON.stringify(x.evidence).indexOf("section_id")>=0;});checks.next=core.click("protocolNext");phase=3;return;}
            if(phase===3){checks.second_page=protocolCardModel.offset===20 && protocolCardModel.has_previous;checks.previous=core.click("protocolPrevious");phase=4;return;}
            if(phase===4){checks.first_page=protocolCardModel.offset===0;checks.unexecuted=protocolCardModel.cards[0].text.indexOf("not executed")>=0;core.capture(core.env("SHOWPSISI_SCREENSHOT"));phase=5;return;}
            if(phase===5){stop();core.testResult(JSON.stringify({passed:Object.keys(checks).every(function(k){return checks[k];}),checks:checks,total:protocolCardModel.total,theme:lightTheme?"light":"dark"}));}
        }
    }
    Timer {
        id: metadataTestTimer
        interval: 80
        repeat: true
        property int phase: 0
        property var checks: ({})
        property double deadline: Date.now()+20000
        onTriggered: {
            if(Date.now()>deadline){stop();core.testResult(JSON.stringify({passed:false,phase:phase,checks:checks,error:core.error}));return;}
            if(!analysisState.complete || core.busy || core.inspecting || !detail.id)return;
            if(phase===0){checks.epg_tab=core.click("tab_EPG");phase=1;return;}
            if(phase===1){recordList.currentIndex=0;recordList.forceActiveFocus();core.key("Return");phase=2;return;}
            if(phase===2){
                if(detail.table_id!==0x4e)return;
                checks.metadata_tab=core.click("inspector_Metadata");phase=3;return;
            }
            if(phase===3){
                checks.encoding=detail.text_diagnostics.some(function(x){return x.basis==="wire_selector" && x.selector_hex==="15";});
                checks.english=metadataEntries().some(function(x){return x.text.indexOf("First second")>=0;});
                if(!core.isExposed("epgLanguage")){revealMetadataControl(epgLanguageChoice);return;}
                checks.language_control=core.click("epgLanguage");core.key("End");core.key("Return");phase=4;return;
            }
            if(phase===4){
                checks.chinese=epgLanguage==="zho" && rowTitle(rows[0])==="新闻";
                checks.incomplete=metadataEntries().some(function(x){return x.text.indexOf("incomplete")>=0 && x.text.indexOf("No complete extended text")>=0;});
                identifierKind.currentIndex=3;identifierValue.text="0x0500";
                if(!core.isExposed("identifierQuery")){revealMetadataControl(identifierQuery);return;}
                checks.lookup_click=core.click("identifierQuery");phase=5;return;
            }
            if(phase===5){
                if(!identifierResult.status)return;
                checks.lookup=identifierResult.label.indexOf("Viaccess")>=0 && identifierResult.raw_hex==="0x0500" && !!identifierResult.source && !!identifierResult.uncertainty;
                checks.sources=metadataEntries().some(function(x){return x.evidence.indexOf("section_id")>=0 && x.evidence.indexOf("raw_hex")>=0;});
                core.capture(core.env("SHOWPSISI_SCREENSHOT"));stop();core.testResult(JSON.stringify({passed:Object.keys(checks).every(function(k){return checks[k];}),checks:checks}));
            }
        }
    }
    Timer {
        id: satelliteTestTimer
        interval: 100
        repeat: true
        property int phase: 0
        property var checks: ({})
        property double deadline: Date.now()+20000
        onTriggered: {
            if(Date.now()>deadline){stop();core.testResult(JSON.stringify({passed:false,phase:phase,checks:checks,error:core.error}));return;}
            if(!analysisState.complete || core.busy || core.inspecting || !detail.id)return;
            if(phase===0){checks.table_tab=core.click("tab_Tables");phase=1;return;}
            if(phase===1){recordList.currentIndex=0;recordList.forceActiveFocus();core.key("Return");phase=2;return;}
            if(phase===2){
                if(detail.table_id!==0x40)return;
                checks.metadata_tab=core.click("inspector_Metadata");phase=3;return;
            }
            if(phase===3){
                let x=(detail.satellite_associations || [])[0];
                checks.wire=!!x && x.raw_parameters.frequency_hz===11538000000 && x.wire_source.section_id===detail.id && !!x.raw_descriptor_hex;
                checks.colocated=!!x && x.candidates.length===2 && x.confirmed_satellite===null;
                checks.presentation=metadataEntries().some(function(e){return e.text.indexOf("HOTBIRD 13F")>=0 && e.text.indexOf("not checked")>=0 && e.evidence.indexOf("reviewed_at")>=0;});
                if(!core.isExposed("satelliteQuery")){revealMetadataControl(satelliteQuery);return;}
                satellitePosition.text="122";checks.lookup_click=core.click("satelliteQuery");phase=4;return;
            }
            if(phase===4){
                if(!satelliteResult.status)return;
                checks.single= satelliteResult.candidates.length===1 && satelliteResult.candidates[0].name==="AsiaSat 9" && satelliteResult.confirmed_satellite===null;
                satellitePosition.text="5";satelliteDirection.currentIndex=1;checks.west_click=core.click("satelliteQuery");phase=5;return;
            }
            if(phase===5){
                if(!satelliteResult.status)return;
                checks.west=satelliteResult.candidates.length===1 && satelliteResult.candidates[0].name==="EUTELSAT 5 WEST B";
                satelliteDirection.currentIndex=0;checks.no_match_click=core.click("satelliteQuery");phase=6;return;
            }
            if(phase===6){
                if(!satelliteResult.status)return;
                checks.no_match=satelliteResult.status==="no_catalog_match" && satelliteResult.candidates.length===0;
                satellitePosition.text="181";checks.invalid_click=core.click("satelliteQuery");phase=7;return;
            }
            if(phase===7){
                checks.invalid=!!satelliteResult.error && !satelliteResult.candidates;
                core.capture(core.env("SHOWPSISI_SCREENSHOT"));stop();core.testResult(JSON.stringify({passed:Object.keys(checks).every(function(k){return checks[k];}),checks:checks}));
            }
        }
    }
    Connections {
        target: win
        function onPresentationStageFinished(stage) {
            const mode=core.env("SHOWPSISI_SCRIPT");
            if(stage!==0 || !analysisModesTestTimer.running || analysisModesTestTimer.presentationIntercepted ||
               (mode!=="analysis-presentation-cancel" && mode!=="analysis-presentation-error"))return;
            analysisModesTestTimer.presentationIntercepted=true;
            const token=presentationToken,epoch=core.resultEpoch();
            Qt.callLater(function(){
                if(token!==presentationToken)return;
                const checks=analysisModesTestTimer.checks;
                checks.pending_guard=presentationPending && core.busy && !backendReady && !JSON.parse(agentState()).settled;
                checks.action_rejected=JSON.parse(agentAction({name:"rescan"})).accepted===false;
                if(mode==="analysis-presentation-cancel")core.cancelAnalysis();
                else core.presentationFailed(epoch,"Injected presentation failure");
                core.mark("presentation_interrupted_checked");
                analysisModesTestTimer.phase=2;
            });
        }
    }
    // Deterministic native integration harness. Positive evidence comes from the
    // separately built real engine; the Python driver releases its file gate.
    Timer {
        id: analysisModesTestTimer
        interval:10; repeat:true
        property int phase:0
        property int ticks:0
        property int pausedTicks:0
        property int progressUpdates:0
        property bool barrier:false
        property bool presentationIntercepted:false
        property double previousTick:0
        property double maxGap:0
        property double frozenPackets:0
        property var checks:({})
        function finish(){
            checks.responsive=maxGap<500;
            core.capture(core.env("SHOWPSISI_SCREENSHOT"));
            stop();core.testResult(JSON.stringify({passed:Object.keys(checks).every(function(k){return !!checks[k];}),checks:checks,max_gui_gap_ms:maxGap,ticks:ticks,progress_updates:progressUpdates,state:{complete:analysisState.complete,analysis_status:analysisState.analysis_status,coverage:analysisState.coverage,result_counts:analysisState.result_counts,table_count:(analysisState.tables || []).length},progress:scanProgress,phase:phase}));
        }
        onTriggered: {core.mark("analysis_driver_begin");step();core.mark("analysis_driver_end");}
        function step(){
            const mode=core.env("SHOWPSISI_SCRIPT");
            if(phase===0){
                if(!backendReady)return;
                if(mode==="analysis-preview"){
                    scanOptionsToggle.checked=true;
                    scanMode.currentIndex=Number(core.env("SHOWPSISI_QUICK_INDEX") || 1);
                    scanBudgetUnit.currentIndex=core.env("SHOWPSISI_QUICK_PERCENT")==="1" ? 0 : 1;scanBudget.text=scanBudgetUnit.currentIndex===0 ? "10" : "20000";scanStart.text="1000";scanEnd.text="21000";
                }
                previousTick=Date.now();scan();phase=1;return;
            }
            const now=Date.now();if(now-previousTick>100)core.mark("ui_gap_phase_"+phase+"_ms_"+(now-previousTick));maxGap=Math.max(maxGap,now-previousTick);previousTick=now;ticks++;
            if(mode==="analysis-invalid-page"){
                if(phase===1){
                    if(core.busy || !core.error)return;
                    checks.invalid_page_rejected=(core.error.indexOf("Invalid result page")===0 || core.error==="Injected continuation page failure") && !analysisState.complete && !(analysisState.tables || []).length && core.available;
                    checks.no_resurrection=Object.keys(core.remainingPages).length===0 && Object.keys(hydrationCollections).length===0;core.loadMore("tables");checks.no_resurrection=checks.no_resurrection && !analysisState.complete;
                    checks.recoverable=core.click("analyzeSource");phase=2;return;
                }
                if(core.busy||core.inspecting||!analysisState.complete)return;
                checks.rescan_complete=!!analysisState.tables.length;finish();return;
            }
            if(mode==="analysis-presentation-cancel" || mode==="analysis-presentation-error"){
                if(phase===1)return;
                if(phase===2){
                    if(core.busy || presentationPending)return;
                    checks.invalidated=!analysisState.complete && !(analysisState.tables || []).length && !tableViewState.complete && !recordViewState.complete;
                    checks.outcome=mode==="analysis-presentation-cancel" ? analysisState.analysis_status==="loading_cancelled" : core.error.indexOf("Result presentation failed:")===0;
                    checks.rescan=core.click("analyzeSource");phase=3;return;
                }
                if(core.busy || core.inspecting || presentationPending || !analysisState.complete)return;
                checks.recovered=tableViewState===analysisState && explorerViewState===analysisState && historyViewState===analysisState && recordViewState===analysisState && !!analysisState.tables.length;
                finish();return;
            }
            if(mode==="analysis-hydration-cancel"){
                if(phase===1){
                    if(!core.loadingResults)return;
                    checks.stop_loading=core.click("cancelAnalysis") && !core.busy && analysisState.analysis_status==="loading_cancelled";
                    core.mark("cancel_hydration_checked");core.send("capabilities");phase=2;return;
                }
                if(phase===2){
                    if(!barrier)return;
                    checks.no_late_resurrection=!core.busy && !analysisState.complete && !(analysisState.tables || []).length;
                    checks.rescan=core.click("analyzeSource");phase=3;return;
                }
                if(core.busy||core.inspecting||!analysisState.complete)return;
                checks.new_complete=!!analysisState.tables.length;finish();return;
            }
            if(mode==="analysis-pause-resume"||mode==="analysis-pause-cancel"){
                if(phase===1){
                    if(!core.busy||!scanProgress.observations)return;
                    checks.pause_control=core.click("pauseAnalysis");
                    checks.pause_pending=core.pausePending && core.busy && !core.cancelling;
                    core.mark("pause_command_checked");phase=2;return;
                }
                if(phase===2){
                    if(!core.paused)return;
                    frozenPackets=Number(scanProgress.packets);checks.authoritative_paused=scanProgress.analysis_status==="paused" && core.busy;
                    const old=lightTheme;lightTheme=!old;
                    checks.local_theme=lightTheme!==old;tab="Tables";
                    checks.no_inspection=!backendReady && editBlockReason().indexOf("Wait")===0;
                    checks.action_rejected=JSON.parse(agentAction({name:"rescan"})).accepted===false;
                    core.mark("paused_state_checked");phase=3;return;
                }
                if(phase===3){
                    if(++pausedTicks<20)return;
                    checks.frozen=Number(scanProgress.packets)===frozenPackets && core.paused && core.busy;
                    if(mode==="analysis-pause-cancel")checks.cancel_control=core.click("cancelAnalysis");
                    else checks.resume_control=core.click("pauseAnalysis");
                    phase=4;return;
                }
                if(phase===4){
                    if(core.busy)return;
                    checks.settled=!core.paused && !core.cancelling;
                    if(mode==="analysis-pause-cancel"){
                        checks.cancelled=analysisState.analysis_status==="cancelled" && !(analysisState.tables || []).length;
                        checks.rescan_control=core.click("analyzeSource");phase=5;return;
                    }
                    checks.resumed_complete=analysisState.complete && !!analysisState.tables.length;
                    phase=6;
                }
                if(phase===5){if(core.busy||!analysisState.complete)return;checks.rescan_complete=!!analysisState.tables.length;phase=6;}
                if(phase===6){if(core.inspecting)return;finish();}return;
            }
            if(core.busy||core.inspecting||!analysisState.complete)return;
            checks.compact=analysisState.response_mode==="compact";
            checks.full_hydration=Object.keys(analysisState.result_counts).every(function(k){return (analysisState[k] || []).length===analysisState.result_counts[k];});
            if(mode==="analysis-preview"){
                checks.partial=partialResults && analysisState.coverage.scanned_packets<analysisState.coverage.source_packets;
                checks.readonly=editBlockReason().indexOf("read-only")>=0 && !core.click("rename");
                checks.coverage=coverageText.indexOf("PARTIAL")===0 && coverageText.indexOf("[")>=0;
                checks.inspection=!!detail.id && !!detail.raw_hex;
                checks.full_density_extent=densityStrip.packetAtBin(densityStrip.binCount-1)===densitySourcePackets-1;
                let gap=analysisState.coverage.ranges[0].end_packet;
                let before=analysisState.selected_packet;snapshot(gap);
                checks.unknown_gap_blocked=analysisState.selected_packet===before && !validPacket(String(gap)) && notice.indexOf("Unscanned interval")===0;
            }else {
                checks.all_records=(analysisState.tables || []).length===Number(core.env("SHOWPSISI_EXPECT_TABLES"));
                checks.bounded_view=recordList.count<=100;
            }
            finish();
        }
    }
    Connections {target:core;function onProgressChanged(){if(analysisModesTestTimer.running)analysisModesTestTimer.progressUpdates++;}}

    Component.onCompleted: {
        if(core.error)showMessage(core.error,"error");
        core.mark("ui_ready");
        if (core.env("SHOWPSISI_TEST_SIZE") === "compact") {
            width = 1000;
            height = 680;
        }
        Qt.callLater(function () { layoutReady = true; core.themeChrome(lightTheme, surface, ink); });
        let requestedStandard = core.env("SHOWPSISI_STANDARDS");
        if (requestedStandard) {
            let choice = standardChoice.indexOfValue(requestedStandard);
            if (choice >= 0)
                standardChoice.currentIndex = choice;
        }
        if (core.env("SHOWPSISI_AUTO") === "1")
            autoTimer.start();
        if (core.env("SHOWPSISI_SCRIPT") === "refinement") refinementTestTimer.start();
        if (core.env("SHOWPSISI_SCRIPT") === "signal-metadata") metadataTestTimer.start();
        if (core.env("SHOWPSISI_SCRIPT") === "protocol-cards") protocolCardsTestTimer.start();
        if (core.env("SHOWPSISI_SCRIPT") === "satellite-metadata") satelliteTestTimer.start();
        if (core.env("SHOWPSISI_SCRIPT") === "section-allbad")
            allBadEvidenceTestTimer.start();
        if (core.env("SHOWPSISI_SCRIPT") === "section-superseded")
            supersededEvidenceTestTimer.start();
        if (core.env("SHOWPSISI_SCRIPT") === "section-evidence")
            sectionEvidenceTestTimer.start();
        if (core.env("SHOWPSISI_SCRIPT") === "plaintext")
            plainTextTimer.start();
        if (core.env("SHOWPSISI_SCRIPT") === "protocol-upgrade")
            protocolUpgradeTimer.start();
        if (core.env("SHOWPSISI_SCRIPT") === "inspect-error")
            inspectFailureTimer.start();
        if (core.env("SHOWPSISI_SCRIPT") === "export-destination")
            exportTestTimer.start();
        if (core.env("SHOWPSISI_SCRIPT").indexOf("layout-") === 0)
            layoutTestTimer.start();
        if (core.env("SHOWPSISI_SCRIPT") === "operations-parity")
            operationsParityTestTimer.start();
        if (core.env("SHOWPSISI_SCRIPT") === "comparison")
            comparisonTestTimer.start();
        if (core.env("SHOWPSISI_SCRIPT") === "comparison-markers") comparisonMarkersTimer.start();
        if (core.env("SHOWPSISI_SCRIPT").indexOf("analysis-") === 0) analysisModesTestTimer.start();
        if (core.env("SHOWPSISI_SCRIPT").indexOf("lifecycle-") === 0)
            lifecycleTestTimer.start();
        if (core.env("SHOWPSISI_SCRIPT") === "refresh")
            refreshTestTimer.start();
        if (core.env("SHOWPSISI_SCRIPT") === "workbench-paging") workbenchPagingTimer.start();
        if (core.env("SHOWPSISI_SCRIPT") === "reference-jumps") referenceJumpsTimer.start();
        if (core.env("SHOWPSISI_SCRIPT") === "command-palette") commandPaletteTimer.start();
        if (core.env("SHOWPSISI_SCRIPT") === "explorer-parity")
            explorerParityTimer.start();
    }
    onClosing: function(close) {
        if (dvbiWorkspace.busy) {close.accepted=false;showMessage("A bounded metadata operation is still finishing. Wait before closing.", "warning");return;}
        if (core.exportPending) {
            close.accepted = false;
            showMessage("An export is still writing. Wait for its result before closing ShowPsiSi.", "warning");
            return;
        }
        if (layoutSaveTimer.running || pendingInspectorSize >= 0 || pendingTimelineSize >= 0) rememberLayout();
    }
    UpdateDialog {
        id: updateDialog
        workBusy: dvbiWorkspace.busy || core.busy || core.inspecting || core.comparing || topologyLoading || core.exportPending || exporting || saveDialog.visible
        lightTheme: win.lightTheme
    }

    Popup {
        id: commandPalette
        objectName: "commandPalette"
        parent: paletteInput || recordPane
        y: parent ? parent.height : 0
        width: parent ? parent.width : 300
        padding: 1
        focus: false
        closePolicy: Popup.NoAutoClose
        background: Rectangle { color:panel; border.color:controlBorder; radius:3 }
        contentItem: Column {
            ListView {
                id: paletteList
                objectName: "paletteList"
                width: parent.width
                height: Math.min(8,paletteRows.length)*32
                clip: true
                model: paletteRows
                currentIndex: paletteIndex
                boundsBehavior: Flickable.StopAtBounds
                Accessible.role: Accessible.List
                Accessible.name: "Commands and identifier targets · " + paletteStatus
                ScrollBar.vertical: ScrollBar {}
                delegate: ItemDelegate {
                    required property var modelData
                    required property int index
                    width: ListView.view.width
                    height: 32
                    padding: 8
                    focusPolicy: Qt.NoFocus
                    enabled: !modelData.reason
                    Accessible.role: Accessible.ListItem
                    Accessible.name: modelData.description + (modelData.keys ? " · " + modelData.keys : "")
                    Accessible.description: modelData.reason || modelData.help || "Execute command"
                    Accessible.selectable: true
                    Accessible.selected: index===paletteIndex
                    contentItem: RowLayout {
                        PlainLabel { text:modelData.description; color:modelData.reason?muted:ink; elide:Text.ElideRight; Layout.fillWidth:true }
                        PlainLabel { text:modelData.keys || "—"; color:muted; font.pixelSize:11; Layout.alignment:Qt.AlignRight }
                    }
                    background: Rectangle { color:index===paletteIndex?selectionSurface:panel; border.color:blue; border.width:index===paletteIndex?focusWidth:0 }
                    onClicked: {paletteIndex=index;executePalette();}
                    SafeTip { visible:anchorHovered || !!modelData.reason && index===paletteIndex && commandPalette.visible; text:modelData.reason || modelData.help || (modelData.id==="export"?"Open the SDT (Service Description Table) preview and export workflow":modelData.description) }
                }
            }
            PlainLabel {
                objectName: "paletteStatus"
                width: parent.width
                padding: 8
                text: paletteStatus
                wrapMode: Text.Wrap
                color: muted
                Accessible.role: Accessible.StaticText
                Accessible.name: text
            }
        }
    }
    Shortcut { sequence:"?"; enabled:!shortcutDialog.visible && !textInputFocused(); onActivated:showShortcutHelp() }
    Shortcut { sequence:"Ctrl+/"; enabled:!shortcutDialog.visible; onActivated:showShortcutHelp() }
    Shortcut {
        sequence: "Ctrl+K"
        enabled: !shortcutDialog.visible
        onActivated: {
            if(metadataMode){dvbiWorkspace.focusSearch();return;}
            transportSummaryVisible=false;
            if(!advancedMode){unifiedInspector.focusSearch();return;}
            let field=tab==="Topology"?topologySearch:recordSearch;
            if(win.activeFocusItem!==field)paletteReturnFocus=win.activeFocusItem;
            field.forceActiveFocus();field.selectAll();
        }
    }
    Shortcut { sequence: "Alt+Left"; enabled:!shortcutDialog.visible; onActivated: { if(metadataMode){dvbiWorkspace.back();return;} if(transportSummaryVisible){transportSummaryVisible=false;return;} if(!advancedMode){unifiedInspector.back();return;} if(protocolSourceOrigin)protocolSourceBack();else if(topologyBackStack.length || topologyOrigin || topologyEvidenceRef)topologyBack(); } }
    // Alt+Left/Right are reserved for navigation; pane sizing has its own chord.
    Shortcut { sequence: "Ctrl+Alt+Left"; enabled: advancedMode && !metadataMode && !shortcutDialog.visible; onActivated: resizeInspector(24) }
    Shortcut { sequence: "Ctrl+Alt+Right"; enabled: advancedMode && !metadataMode && !shortcutDialog.visible; onActivated: resizeInspector(-24) }
    Shortcut { sequence: "Ctrl+Alt+Up"; enabled: advancedMode && !metadataMode && !shortcutDialog.visible; onActivated: resizeTimeline(24) }
    Shortcut { sequence: "Ctrl+Alt+Down"; enabled: advancedMode && !metadataMode && !shortcutDialog.visible; onActivated: resizeTimeline(-24) }
    Shortcut {
        sequence: "F6"
        enabled: !shortcutDialog.visible
        onActivated: {
            if(metadataMode){dvbiWorkspace.focusNext();return;}
            if(documentMode&&!advancedMode){documentWorkspace.nextRegion(false);return;}
            if(transportSummaryVisible){transportSummary.nextRegion(false);return;}
            if(!advancedMode){unifiedInspector.nextRegion(false);return;}
            focusNextRegion(false);
        }
    }
    Shortcut { sequence:"Shift+F6"; enabled:!metadataMode && !shortcutDialog.visible; onActivated:documentMode&&!advancedMode?documentWorkspace.nextRegion(true):transportSummaryVisible?transportSummary.nextRegion(true):advancedMode?focusNextRegion(true):unifiedInspector.nextRegion(true) }
    Shortcut {
        sequence: "Ctrl+Shift+K"
        enabled: !shortcutDialog.visible
        onActivated: {
            if(metadataMode){dvbiWorkspace.focusSearch();return;}
            transportSummaryVisible=false;
            if(!advancedMode){unifiedInspector.focusSearch();return;}
            inspectorView = "Structure";
            treeSearch.forceActiveFocus();
            treeSearch.selectAll();
        }
    }
    Shortcut {
        sequence: "Ctrl+O"
        enabled: backendReady && !shortcutDialog.visible
        onActivated: metadataMode ? dvbiWorkspace.openDialog() : fileDialog.open()
    }
    Shortcut {
        sequence: "Ctrl+Return"
        enabled: !shortcutDialog.visible
        onActivated: metadataMode ? dvbiWorkspace.importDocument(dvbiWorkspace.pathValue()) : inspectorView==="Structure" && treeFocused() && !!treeRows[tree.currentIndex]?.reference ? jumpReference(treeRows[tree.currentIndex]) : scan()
    }
    Shortcut {
        sequence: "Ctrl+."
        enabled: core.available && core.busy && !core.cancelling && !shortcutDialog.visible
        onActivated: cancelScan()
    }
    FileDialog {
        id: fileDialog
        title: "Open transport stream"
        nameFilters: ["Transport streams (*.ts *.mts *.m2ts)", "All files (*)"]
        onAccepted: {
            source.text = core.localPath(selectedFile);
            if(advancedMode)scan();else {classicConfigurationVisible=true;showMessage("Ready — choose Start to analyze the selected transport stream","info");}
        }
    }
    FileDialog {
        id: saveDialog
        title: "Save new SI-only " + (saveIntent.format || "ts").toUpperCase() + " · existing files are refused"
        fileMode: FileDialog.SaveFile
        nameFilters: saveIntent.format === "bin" ? ["Raw SI sections (*.bin)"] : ["SI-only transport stream (*.ts)"]
        defaultSuffix: saveIntent.format || "ts"
        // Qt Quick Dialogs 6.7 supports this flag. A Replace confirmation would
        // promise an overwrite which the engine deliberately never permits.
        options: FileDialog.DontConfirmOverwrite
        onAccepted: {
            core.mark("export_dialog_accepted");
            acceptExportDestination(selectedFile);
            exportTestTimer.resolvedChoice();
        }
        onRejected: {
            core.mark("export_dialog_cancelled");
            saveIntent = {};
            exportButton.forceActiveFocus();
            exportTestTimer.resolvedChoice();
        }
    }
    Dialog {
        id: apiDialog
        title: "Agent API · native backend"
        width: Math.min(800, win.width - 80)
        height: win.height - 140
        anchors.centerIn: parent
        modal: true
        standardButtons: Dialog.Close
        ScrollView {
            anchors.fill: parent
            TextArea {
                id: apiText
                textFormat: TextEdit.PlainText
                readOnly: true
                selectByMouse: true
                wrapMode: TextEdit.Wrap
                font.family: "monospace"
                font.pixelSize: 12
            }
        }
    }
    header: Column {
        width:parent.width
        spacing:0
        ClassicFrame {host:win;visible:!metadataMode&&!advancedMode;width:parent.width;onCommand:function(name){win.classicCommand(name);}}
        Rectangle {
        width:parent.width
        visible:metadataMode || advancedMode
        height: visible?42:0
        color: surface
        border.color: dividerColor
        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: 14
            anchors.rightMargin: 14
            spacing: 12
            PlainLabel {
                text: "ShowPsiSi"
                font.weight: Font.DemiBold
                color: ink
            }
            FieldChoice {
                objectName: "inputKind"
                Layout.preferredWidth: 175
                model: [{label:"TS capture",value:"ts"},{label:"DVB-I XML",value:"dvbi"}]
                textRole:"label"; valueRole:"value"; currentIndex:metadataMode?1:0
                enabled:backendReady && !exporting && !saveDialog.visible
                Accessible.name:"Input kind; TS capture and independent DVB-I XML document"
                onActivated:inputKind=currentValue
            }
            PlainLabel {
                text: "PSI / SI INSPECTOR"
                visible: win.width >= 1400 && !metadataMode
                color: muted
                font.pixelSize: 11
                SafeTip {
                    visible: headerHover.hovered
                    text: "Program Specific Information / Service Information"
                }
                HoverHandler {
                    id: headerHover
                }
            }
            Item {
                Layout.fillWidth: true
            }
            PlainLabel {
                text: (core.availability === "disconnected" ? "DISCONNECTED" : core.cancelling ? "CANCELLING" : core.busy ? "SCANNING" : analysisState.analysis_status === "cancelled" ? "CANCELLED" : (metadataMode ? (dvbiWorkspace.busy ? "LOADING XML" : "DVB-I DOCUMENT") : analysisState.detected_standards || "LOCAL")) + " · Qt Quick"
                color: muted
                font.pixelSize: 11
            }
            Action {
                id: themeToggle
                objectName: "themeToggle"
                text: lightTheme ? "Dark" : "Light"
                Accessible.name: "Switch to " + (lightTheme ? "dark" : "light") + " theme"
                onClicked: lightTheme = !lightTheme
            }
            Action {
                objectName: "resetLayout"
                visible: advancedMode
                text: "Reset layout"
                onClicked: resetLayout()
                SafeTip {
                    visible: anchorHovered
                    text: "Drag the dividers to resize. Ctrl+Alt+Left/Right resizes the inspector; Ctrl+Alt+Up/Down resizes the timeline. Alt+Left navigates back. Changes are saved on this computer."
                }
            }
            Action {
                objectName: "aboutUpdatesButton"
                text: "About / Updates"
                onClicked: updateDialog.open()
            }
            Action {
                objectName:"transportSummaryButton"
                visible:!metadataMode
                text:transportSummaryVisible ? "Return to inspector" : "Summary / PID"
                onClicked:transportSummaryVisible=!transportSummaryVisible
            }
            Action {
                objectName: "workspaceMode"
                text: advancedMode ? "Inspector" : "Advanced workspace"
                onClicked: {transportSummaryVisible=false;advancedMode = !advancedMode;}
            }
            Action {
                objectName: "agentApi"
                visible: advancedMode
                text: "Agent API"
                enabled: backendReady
                onClicked: core.send("capabilities", {})
            }
            Action {
                objectName: "saveDiagnostics"
                visible: advancedMode
                text: "Save diagnostics"
                enabled: !core.busy && !core.inspecting && !core.comparing
                onClicked: {let result=uiAgent.saveBundle();showMessage(result,result.indexOf("Diagnostics failed:")===0 ? "error" : "info");}
                SafeTip { visible: anchorHovered; text: "Save a real screenshot and structured UI state for debugging. Includes source paths and visible stream metadata." }
            }
        }
    }
    }
    ColumnLayout {
        anchors.fill: parent
        spacing: 0
        Rectangle {
            objectName: "errorBanner"
            visible: !metadataMode && !!errorMessage
            Layout.fillWidth: true
            implicitHeight: errorBannerRow.implicitHeight + 12
            color: errorSurface
            Accessible.role: Accessible.AlertMessage
            Accessible.name: "Error: " + errorMessage
            RowLayout {
                id: errorBannerRow
                anchors.fill: parent
                anchors.margins: 6
                spacing: 8
                PlainLabel {
                    Layout.fillWidth: true
                    text: errorMessage
                    color: errorInk
                    wrapMode: Text.WrapAnywhere
                    maximumLineCount: 3
                    elide: Text.ElideRight
                    SafeTip { visible: errorHover.hovered; text: anchorText }
                    HoverHandler { id: errorHover }
                }
                Action {
                    objectName: "dismissError"
                    text: "Dismiss"
                    Accessible.name: "Dismiss error message"
                    onClicked: {errorMessage="";messagesButton.forceActiveFocus();}
                }
            }
        }
        ColumnLayout {
            id: sourceBar
            visible: !metadataMode && (advancedMode || classicConfigurationVisible)
            Layout.fillWidth: true
            Layout.margins: 10
            spacing: 6
            RowLayout {
                Layout.fillWidth: true
                spacing: 8
                PlainLabel {
                    text: "SOURCE"
                    color: muted
                    font.pixelSize: 11
                }
                FieldInput {
                    id: source
                    enabled: backendReady
                    Layout.fillWidth: true
                    text: core.sample
                    selectByMouse: true
                    implicitHeight: 30
                    Accessible.name: "Transport stream source path"
                    onAccepted: scan()
                }
                Action {
                    objectName: "openSource"
                    text: "Open…"
                    Accessible.name: "Open transport stream"
                    enabled: backendReady
                    onClicked: fileDialog.open()
                    SafeTip {
                        visible: anchorHovered
                        text: "Open transport stream (Ctrl+O)"
                    }
                }
                Action {
                    id: recentButton
                    objectName: "recentFiles"
                    text: "Recent ▾"
                    enabled: backendReady
                    Accessible.name: "Recent transport streams"
                    Accessible.description: "Choose a recent source without analyzing it"
                    onClicked: recentMenu.open()
                    Menu {
                        id: recentMenu
                        y: recentButton.height
                        width: 320
                        padding: 4
                        background: Rectangle {color:panel;border.color:dividerColor;radius:4}
                        Instantiator {
                            model: recentFiles
                            delegate: RecentMenuItem {
                                required property string modelData
                                text: modelData.split(/[\\/]/).pop()
                                Accessible.description: modelData
                                onTriggered: chooseSource(modelData)
                                SafeTip {visible:anchorHovered; text:anchorControl ? anchorControl.modelData : ""}
                            }
                            onObjectAdded: function(index, object) {recentMenu.insertItem(index,object);}
                            onObjectRemoved: function(index, object) {recentMenu.removeItem(object);}
                        }
                        RecentMenuItem {text:"No recent files";enabled:false;visible:recentFiles.length===0;height:visible?implicitHeight:0}
                        MenuSeparator {visible:recentFiles.length>0;contentItem:Rectangle {implicitHeight:1;color:dividerColor}}
                        RecentMenuItem {
                            text: "Clear recent"
                            enabled: recentFiles.length>0
                            onTriggered: {recentFiles=[];saveRecentFiles();recentButton.forceActiveFocus();}
                        }
                    }
                    SafeTip {visible:anchorHovered;text:"Recently analyzed sources · choosing a file does not start analysis"}
                }
                FieldChoice {
                    id: standardChoice
                    objectName: "standards"
                    Layout.preferredWidth: 136
                    implicitHeight: 30
                    enabled: backendReady
                    textRole: "label"
                    valueRole: "value"
                    model: [
                        {
                            label: "Standards: Auto",
                            value: "auto"
                        },
                        {
                            label: "DVB",
                            value: "dvb"
                        },
                        {
                            label: "ATSC",
                            value: "atsc"
                        },
                        {
                            label: "ISDB",
                            value: "isdb"
                        },
                        {
                            label: "ISDB Japan",
                            value: "isdb-japan"
                        },
                        {
                            label: "ISDB Brazil",
                            value: "isdb-brazil"
                        },
                        {
                            label: "SCTE",
                            value: "scte"
                        },
                        {
                            label: "DTMB",
                            value: "dtmb"
                        },
                        {label:"J.94 System B",value:"j94-system-b"}
                    ]
                    Accessible.name: "Broadcast standard context for next scan"
                    SafeTip {
                        visible: anchorHovered
                        text: "Select the broadcast context for the next analysis. Auto uses TSDuck detection; explicit context resolves reused table identifiers."
                    }
                }
                Action {
                    id: scanOptionsToggle
                    objectName: "scanOptionsToggle"
                    checkable: true
                    text: "Scan options " + (checked ? "▾" : "▸") + (!checked && scanOptionsSummary ? " · " + scanOptionsSummary : "")
                    Layout.minimumWidth: 118
                    Layout.maximumWidth: 280
                    Layout.preferredWidth: Math.min(implicitWidth, 280)
                    Accessible.name: "Scan options"
                    Accessible.description: (checked ? "Expanded" : "Collapsed") + " · Default charset and extra packet identifiers for the next scan" + (scanOptionsSummary ? " · " + scanOptionsSummary : "")
                    contentItem: PlainLabel { text:scanOptionsToggle.text; color:ink; elide:Text.ElideRight; verticalAlignment:Text.AlignVCenter; horizontalAlignment:Text.AlignHCenter; font.pixelSize:11 }
                    SafeTip { visible:anchorHovered; text:"Default charset and extra Packet Identifiers (PIDs) for the next scan" + (scanOptionsSummary ? " · " + scanOptionsSummary : "") }
                }
                Action {
                    id: analyzeButton
                    objectName: "analyzeSource"
                    text: "Analyze"
                    Accessible.name: "Analyze transport stream"
                    Accessible.description: scanOptionsChanged ? "Options changed — re-analyze to apply" : ""
                    primary: true
                    visible: !core.busy
                    enabled: backendReady && source.text.trim().length > 0 && extraPidsValue !== null && quickOptionsValid
                    onClicked: scan()
                }
                Action {
                    id: pauseButton
                    objectName: "pauseAnalysis"
                    text: core.pausePending ? "Waiting…" : core.paused ? "Resume" : "Pause"
                    visible: core.busy && !core.loadingResults
                    enabled: core.available && !core.cancelling && !core.pausePending
                    onClicked: core.pauseAnalysis()
                    Accessible.name: core.paused ? "Resume active scan" : "Pause active scan"
                    SafeTip { visible:anchorHovered; text:"Pause keeps this scan in memory. Resume continues at the same position. Cancel discards it. Closing the app cannot resume this scan later." }
                }
                Action {
                    id: cancelButton
                    objectName: "cancelAnalysis"
                    text: core.loadingResults ? "Stop loading" : core.cancelling ? "Cancelling…" : "Cancel"
                    visible: core.busy
                    enabled: core.available && !core.cancelling
                    onClicked: cancelScan()
                    Accessible.name: core.cancelling ? "Waiting for scan cancellation" : "Cancel active scan"
                    SafeTip { visible: anchorHovered; text: "Cancel this scan (Ctrl+.). Wait for it to stop before analyzing again." }
                }
            }
            PlainLabel {
                objectName: "scanOptionsChanged"
                visible: scanOptionsChanged
                Layout.alignment: Qt.AlignRight
                text: "Options changed — re-analyze to apply"
                color: muted
                font.pixelSize: 11
            }
            RowLayout {
                visible: scanOptionsToggle.checked
                Layout.fillWidth: true
                spacing: 8
                PlainLabel { text:"Default charset"; color:muted; font.pixelSize:11 }
                FieldInput {
                    id: defaultCharset
                    objectName: "defaultCharset"
                    Layout.fillWidth: true
                    implicitHeight: 30
                    placeholderText: "Default charset (optional)"
                    placeholderTextColor: muted
                    selectByMouse: true
                    enabled: backendReady
                    Accessible.name: "Default input charset for next scan"
                    onAccepted: scan()
                    SafeTip { visible: anchorHovered; text: "Optional TSDuck character set, e.g. ISO-8859-5 or UTF-8. Digital Video Broadcasting (DVB) selectors take precedence unless a RAW character set is chosen. Original bytes are preserved." }
                }
                PlainLabel { text:"Extra PIDs"; color:muted; font.pixelSize:11 }
                FieldInput {
                    id: extraPids
                    objectName: "extraPids"
                    Layout.fillWidth: true
                    implicitHeight: 30
                    placeholderText: "Extra PIDs: 0x30, 100"
                    placeholderTextColor: muted
                    selectByMouse: true
                    enabled: backendReady
                    Accessible.name: "Additional packet identifiers, comma separated"
                    SafeTip {
                        visible: anchorHovered
                        text: "Optional extra Packet Identifiers (PIDs), decimal or hexadecimal, from 0 to 8191."
                    }
                    onAccepted: scan()
                }
            }
            Flow {
                visible: scanOptionsToggle.checked
                Layout.fillWidth: true
                Layout.preferredHeight: visible ? implicitHeight : 0
                spacing: 8
                FieldChoice {
                    id: scanMode; objectName:"scanMode"; width:205; enabled:backendReady
                    textRole:"label"; valueRole:"value"
                    model:[{label:"Full scan",value:"full"},{label:"Quick: prefix",value:"prefix"},{label:"Quick: packet interval",value:"range"},{label:"Quick: 4 large windows",value:"distributed"}]
                    Accessible.name:"Scan coverage mode"
                }
                FieldChoice { id:scanBudgetUnit; objectName:"scanBudgetUnit"; width:135; model:["% of file","packets"]; enabled:backendReady; visible:scanMode.currentValue==="prefix" || scanMode.currentValue==="distributed"; onActivated:scanBudget.text=currentIndex===0 ? "10" : "250000"; Accessible.name:"Quick scan budget unit" }
                FieldInput { id:scanBudget; objectName:"scanBudget"; width:100; text:"10"; enabled:backendReady; visible:scanMode.currentValue==="prefix" || scanMode.currentValue==="distributed"; placeholderText:"Packet budget"; Accessible.name:scanBudgetUnit.currentIndex===0 ? "Quick scan percent of file" : "Quick scan packet budget"; SafeTip { visible:anchorHovered; text:"Scan 10% for one tenth of the file, or set a packet budget. Distributed mode uses four contiguous windows, not many random HDD reads." } }
                PlainLabel { text:"Start (inclusive)"; color:muted; visible:scanMode.currentValue==="range" }
                FieldInput { id:scanStart; objectName:"scanStart"; width:125; text:"0"; enabled:backendReady; visible:scanMode.currentValue==="range"; placeholderText:"Start packet"; Accessible.name:"First packet, inclusive" }
                PlainLabel { text:"End (exclusive)"; color:muted; visible:scanMode.currentValue==="range" }
                FieldInput { id:scanEnd; objectName:"scanEnd"; width:125; text:"250000"; enabled:backendReady; visible:scanMode.currentValue==="range"; placeholderText:"End packet"; Accessible.name:"End packet, exclusive" }
                PlainLabel { text:scanMode.currentValue==="full" ? "All packets; editing available after completion" : "Packet indexes · preview is read-only, not a complete recording"; color:muted; font.pixelSize:11 }
            }
            PlainLabel { visible:!quickOptionsValid; text:"Enter whole packet indexes; end must exceed start, and budget must be positive."; color:removedColor; font.pixelSize:11 }
            PlainLabel {
                visible: extraPidsValue === null
                text: "Extra PIDs must be decimal or 0x-prefixed hexadecimal values from 0 to 8191."
                color: removedColor
                font.pixelSize: 11
            }
        }
        ProgressBar {
            Layout.fillWidth: true
            Layout.preferredHeight: 2
            visible: core.busy
            indeterminate: scanProgress.progress_fraction === undefined || core.loadingResults
            value: Number(scanProgress.progress_fraction || 0)
        }
        PlainLabel {
            objectName:"scanStatus"
            visible:core.busy || !!coverageText
            Layout.fillWidth:true; Layout.leftMargin:12; Layout.rightMargin:12
            wrapMode:Text.Wrap; font.pixelSize:11; color:partialResults ? changedColor : muted
            text:core.loadingResults ? "Scan 100% · loading result pages · " + num(scanProgress.loaded_items) + " records…" : core.busy ? (core.cancelling ? "Cancelling…" : core.paused ? "Paused · Resume continues this session" : scanProgress.analysis_status === "finalizing" ? "Scan 100% · finalizing evidence…" : "Scanning · "+Math.floor(Number(scanProgress.progress_fraction || 0)*100)+"%") + " · " + num(scanProgress.coverage?.scanned_packets || scanProgress.packets) + " packets · New inspection, comparison and export wait until completion. Cached records can still be browsed." : coverageText
        }
        RowLayout {
            visible: !metadataMode && advancedMode
            Layout.fillWidth: true
            Layout.leftMargin: 12
            Layout.rightMargin: 12
            Layout.bottomMargin: 8
            // The stats row must never set a minimum width wider than a compact window.
            readonly property bool compactStats: win.width < 1180
            spacing: compactStats ? 12 : 20
            StatBadge {
                objectName: "statsServices"
                compact: parent.compactStats
                label: "SERVICES"
                value: num(serviceRows.length)
                Accessible.name: "Show Services · " + value + " services"
                onClicked: tab="Services"
            }
            StatBadge {
                objectName: "statsSections"
                compact: parent.compactStats
                label: "SECTIONS"
                value: num(analysisState.observations)
                detailText: num((analysisState.tables || []).length) + " distinct payloads"
                Accessible.name: "Show Tables · " + value + " section observations · " + detailText
                onClicked: tab="Tables"
            }
            StatBadge {
                objectName: "statsIssues"
                compact: parent.compactStats
                label: "ISSUES"
                value: num(issues.length)
                counts: issueCounts
                detailText: num(analysisState.crc_errors) + " CRC failures"
                Accessible.name: "Show Issues · " + (issueCounts.hasSeverity ? issueCounts.errors + " errors · " + issueCounts.warnings + " warnings" + (issueCounts.other ? " · " + issueCounts.other + " other" : "") : value + " issues") + " · " + detailText
                onClicked: tab="Issues"
                SafeTip { visible:anchorHovered; text:"CRC: Cyclic Redundancy Check. A failed CRC means the section bytes were damaged or truncated." }
            }
            Item {
                Layout.fillWidth: true
            }
            PlainLabel {
                text: analysisState.metrics ? Number(analysisState.metrics.scan_ms).toFixed(1) + " ms scan" : "Awaiting source"
                Layout.minimumWidth: 0
                elide: Text.ElideRight
                color: muted
                font.pixelSize: 11
            }
        }
        DvbiWorkspace {
            id: dvbiWorkspace
            host:win
            visible:metadataMode
            Layout.fillWidth:true
            Layout.fillHeight:true
        }
        UnifiedInspector {
            id: unifiedInspector
            focusOrigin:sourceBar.visible?sourceBar:null
            onCarouselRequested:function(sourceId){win.openCarousel(sourceId);}
            onServiceRequested:function(service){win.openServices(service);}
            onPacketRequested:function(pid){win.openPacket(pid,0);}
            treeVisible:win.classicTreeVisible
            externalVisible:win.transportSummaryVisible||win.documentMode
            host: win
            organization: !topologyStale && topologyData.analysis_revision===analysisState.analysis_revision ? topologyData : ({})
            organizationStatus: topologyLoading ? "Loading networks / TP..." : topologyError ? "Network organization unavailable" : (topologyData.page || {}).has_more ? "Loading more networks / TP..." : ""
            onVisibleChanged: if(visible)siOrganizationTimer.restart()
            visible: !metadataMode && !advancedMode
            Layout.fillWidth: true
            Layout.fillHeight: true
        }
        DocumentWorkspace {
            id:documentWorkspace
            navigationOrigin:unifiedInspector.navigationItem
            parent:unifiedInspector.externalContainer;anchors.fill:parent
            visible:documentMode&&!advancedMode&&!metadataMode
            sectionComponent:Component {
                UnifiedInspector {
                    id:childInspector;treeVisible:false
                    onPacketRequested:function(pid){win.openPacket(pid,0);}
                    host:QtObject {
                        property var analysisState:detail._view_state||win.analysisState
                        property var detail:childInspector.parent.documentData.payload
                        property bool coreInspecting:false
                        property bool backendReady:win.backendReady
                        function inspect(id){win.inspect(id);}
                        property var tableFamilies:win.tableFamilies
                    }
                }
            }
            summaryComponent:Component {
                TransportSummary {
                    host:win
                    onPageRequested:function(offset,sort,descending,errorsOnly){if(!core.busy)core.send('query_transport',{analysis_revision:analysisState.analysis_revision||analysisState.revision,offset:offset,limit:100,sort:sort,descending:descending,errors_only:errorsOnly});}
                    onEntryActivated:function(entry){var record=(analysisState.tables||[]).find(function(row){return row.pid===entry.pid;});if(record)win.inspect(record.id);}
                    Component.onCompleted:if(!core.busy&&analysisState.complete)request(0)
                }
            }
            carouselComponent:Component {
                CarouselView {
                    id:carouselDocument
                    initialSource:parent.documentData.payload.source_id||''
                    host:QtObject{property var analysisState:carouselDocument.parent.documentData.payload._view_state;property bool backendReady:win.backendReady}
                    onRequested:function(params){if(!core.busy)core.send('query_carousel',params);else receive({request:params,message:'Wait for current analysis to finish'});}
                    onSectionActivated:function(id,path,cutoff){win.openServiceSource(id,path,cutoff);}
                }
            }
            serviceComponent:Component {
                ServiceView {
                    id:serviceDocument
                    initialService:parent.documentData.payload.service
                    host:QtObject{property var analysisState:serviceDocument.parent.documentData.payload._view_state;property bool backendReady:win.backendReady}
                    onRequested:function(params){if(!core.busy)core.send('query_service',params);else receive({request:params,message:'Wait for current analysis to finish'});}
                    onSectionActivated:function(id,path,cutoff){win.openServiceSource(id,path,cutoff);}
                }
            }
            statisticsComponent:Component {
                StatisticsView {
                    host:win
                    onRequested:function(method,params){if(!core.busy)core.send(method,params);else receive(method,{message:'Wait for current analysis to finish'});}
                    onPacketActivated:function(pid,index){win.openPacket(pid,index);}
                }
            }
            packetComponent:Component {
                PacketExplorer {
                    id:packetDocument;host:win
                    initialPid:parent.documentData.payload.pid
                    initialIndex:parent.documentData.payload.index
                    onRequested:function(params){if(!core.busy)core.send('query_packet',params);else receive({request:params,code:'busy',message:'Wait for current analysis to finish'});}
                    onSectionActivated:function(id){win.inspect(id);}
                }
            }
            decodeComponent:Component {
                ScrollView {
                    id:decodedDocument
                    TextArea {readOnly:true;selectByMouse:true;wrapMode:TextEdit.NoWrap;font.family:'Courier New';font.pixelSize:13;color:'#000';background:Rectangle{color:'#fff'}text:decodedDocument.parent.documentData.payload.section_native_text||decodedDocument.parent.documentData.payload.native_text||decodedDocument.parent.documentData.payload.raw_hex||'No selected table'}
                }
            }
        }
        TransportSummary {
            id:transportSummary
            parent:unifiedInspector.externalContainer
            anchors.fill:parent
            focusOrigin:sourceBar.visible?sourceBar:null
            host:win
            visible:!metadataMode && transportSummaryVisible && !documentMode
            onPageRequested:function(offset,sort,descending,errorsOnly){
                if(core.busy){reject("Wait for the current operation, then Refresh.");return;}
                core.send("query_transport",{analysis_revision:analysisState.analysis_revision || analysisState.revision,offset:offset,limit:100,sort:sort,descending:descending,errors_only:errorsOnly});
            }
            onEntryActivated:function(entry){
                if(entry.aggregate || entry.pid===null || entry.pid===undefined){showMessage("No exact packet/section identity is retained for this aggregate.","warning");return;}
                let record=(analysisState.tables || []).find(function(row){return entry.id ? row.id===entry.id : row.pid===entry.pid;});
                if(!record){showMessage(entry.id ? "The exact diagnostic section is unavailable in this result." : "PID "+hex(entry.pid)+" has no retained PSI/SI section. PES/media views are not implemented yet.","warning");return;}
                transportSummaryVisible=false;advancedMode=false;unifiedInspector.filterPid(entry.pid);unifiedInspector.selectRecord(record);
            }
        }
        SplitView {
            id: verticalWorkspace
            visible: !metadataMode && advancedMode && !transportSummaryVisible
            Layout.fillWidth: true
            Layout.fillHeight: true
            orientation: Qt.Vertical
            onResizingChanged: {
                if (resizing) pendingTimelineSize = -1;
                else layoutSaveTimer.restart();
            }
            handle: Rectangle {
                objectName: "timelineDivider"
                implicitHeight: 6
                color: SplitHandle.pressed ? blue : SplitHandle.hovered ? controlBorder : raised
            }
        SplitView {
            id: workspace
            SplitView.fillHeight: true
            SplitView.minimumHeight: tab === "Changes" ? 380 : 300
            orientation: Qt.Horizontal
            onResizingChanged: {
                if (resizing) pendingInspectorSize = -1;
                else layoutSaveTimer.restart();
            }
            handle: Rectangle {
                objectName: x < workspace.width / 3 ? "explorerDivider" : "inspectorDivider"
                implicitWidth: 6
                color: SplitHandle.pressed ? blue : SplitHandle.hovered ? controlBorder : raised
            }
            Card {
                id: explorerPane
                SplitView.preferredWidth: savedLayout.explorer
                SplitView.minimumWidth: 150
                SplitView.maximumWidth: 480
                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 8
                    spacing: 2
                    TinyLabel {
                        text: "EXPLORER"
                        Layout.margins: 7
                    }
                    PlainLabel {
                        text: "PID · TABLE TYPE · #"
                        color: muted
                        Layout.margins: 7
                        SafeTip { visible: explorerHeaderHover.hovered; text: "Logical tables, including hidden bad-CRC evidence. Repeated arrivals and section payloads do not increase this count." }
                        HoverHandler { id: explorerHeaderHover }
                    }
                    ListView {
                        id: explorerList
                        objectName: "explorerList"
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        clip: true
                        model: explorerRows
                        activeFocusOnTab: true
                        keyNavigationEnabled: false
                        currentIndex: Math.max(0, explorerRows.findIndex(function(row) {return explorerKey(row) === explorerFocusKey;}))
                        onCurrentIndexChanged: if (activeFocus) positionViewAtIndex(currentIndex, ListView.Contain)
                        Keys.onPressed: function(event) {
                            let next = currentIndex;
                            if (event.key === Qt.Key_Home) next = 0;
                            else if (event.key === Qt.Key_End) next = count - 1;
                            else if (event.key === Qt.Key_Up) next = Math.max(0, next - 1);
                            else if (event.key === Qt.Key_Down) next = Math.min(count - 1, next + 1);
                            else if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter || event.key === Qt.Key_Space) {selectExplorer(explorerRows[currentIndex]); event.accepted=true; return;}
                            else return;
                            explorerFocusKey = explorerKey(explorerRows[next]); event.accepted = true;
                        }
                        ScrollBar.vertical: ScrollBar {}
                        delegate: NavItem {
                            required property var modelData
                            required property int index
                            objectName: "explorerRow:" + modelData.pid + ":" + modelData.name
                            focusPolicy: Qt.NoFocus
                            keyboardCurrent: explorerList.activeFocus && explorerList.currentIndex === index
                            Accessible.name: (modelData.pid < 0 ? "All tables" : "PID " + hex(modelData.pid) + " " + tableLabel(modelData.name)) + " · " + modelData.count + " logical tables"
                            width: ListView.view.width
                            height: 32
                            highlighted: explorerSelected(modelData)
                            contentItem: RowLayout {
                                spacing: 6
                                PlainLabel { objectName: "explorerIcon:" + modelData.pid + ":" + modelData.name; text: modelData.pid < 0 ? "≡" : tableCategory(modelData.name)[1]; color: tableColor(modelData.name); Layout.preferredWidth: 16; horizontalAlignment: Text.AlignHCenter }
                                PlainLabel { visible:modelData.pid >= 0; text: hex(modelData.pid); color: muted; font.family:"monospace"; font.pixelSize:11; Layout.preferredWidth: 49 }
                                PlainLabel { objectName: "explorerLabel:" + modelData.pid + ":" + modelData.name; text: tableLabel(modelData.name); color: modelData.pid < 0 ? ink : tableColor(modelData.name); Layout.fillWidth:true; elide:Text.ElideRight; font.pixelSize:11 }
                                PlainLabel { text: modelData.count; color:muted; font.pixelSize:10; Layout.preferredWidth:18; horizontalAlignment:Text.AlignRight }
                            }
                            onClicked: {
                                selectExplorer(modelData); explorerList.forceActiveFocus();
                            }
                            SafeTip { visible:anchorHovered; text: (modelData.pid < 0 ? "All tables" : "PID " + hex(modelData.pid) + " · " + modelData.name) + " · " + modelData.count + " logical tables, including hidden bad-CRC evidence" }
                        }
                    }
                    Action {
                        id: keyboardShortcuts
                        objectName: "keyboardShortcuts"
                        text: "Keyboard shortcuts " + (checked ? "▾" : "▸")
                        checkable: true
                        Layout.fillWidth: true
                        Accessible.name: "Keyboard shortcuts"
                    }
                    PlainLabel {
                        visible: keyboardShortcuts.checked
                        text: shortcutTable.map(function(row){return row.keys+" · "+row.description;}).join("\n") + "\nSource → Explorer → Records → Inspector"
                        color: muted
                        font.pixelSize: 11
                        Layout.fillWidth: true
                        wrapMode: Text.Wrap
                    }
                    TinyLabel {
                        text: "EXTENSION"
                        Layout.margins: 7
                    }
                    PlainLabel {
                        text: analysisState.extension_id || "No extension reported"
                        color: muted
                        font.pixelSize: 11
                        Layout.fillWidth: true
                        wrapMode: Text.WrapAnywhere
                        Layout.margins: 7
                    }
                    PlainLabel {
                        text: "Private data specifier scoped"
                        color: muted
                        font.pixelSize: 11
                        Layout.margins: 7
                    }
                }
            }
            Card {
                id: recordPane
                SplitView.fillWidth: true
                SplitView.minimumWidth: 310
                ColumnLayout {
                    anchors.fill: parent
                    spacing: 0
                    RowLayout {
                        Layout.fillWidth:true
                        visible:!!activeCollection && core.remainingPages[activeCollection] !== undefined
                        PlainLabel { Layout.fillWidth:true; text:"Showing " + num((analysisState[activeCollection] || []).length) + " of " + num(analysisState.result_counts?.[activeCollection]) + " · search/filter applies to loaded records"; color:muted; font.pixelSize:11; wrapMode:Text.Wrap }
                        Action { objectName:"loadMoreResults"; text:"Load next 50"; enabled:backendReady; onClicked:{core.loadMore(activeCollection);if(activeCollection==="tables")core.loadMore("table_groups");} }
                    }
                    Flow {
                        Layout.fillWidth: true
                        Layout.preferredHeight: implicitHeight
                        spacing: 0
                        Repeater {
                            model: recordTabs
                            NavItem {
                                required property string modelData
                                objectName: "tab_" + modelData
                                leftPadding: 5
                                rightPadding: 5
                                text: modelData
                                implicitHeight: 35
                                highlighted: tab === modelData
                                focusPolicy: Qt.StrongFocus
                                onClicked: {
                                    if (modelData === "Changes") openComparison();
                                    else {
                                        tab = modelData;
                                        if (selectedChange) { selectedChange = null; defaultInspect(); }
                                    }
                                }
                                SafeTip {
                                    visible: anchorHovered
                                    text: explanation(modelData)
                                }
                            }
                        }
                    }
                    RowLayout {
                        visible: topologyBackStack.length>0 || !!topologyOrigin || !!topologyEvidenceRef
                        Layout.fillWidth:true
                        Layout.leftMargin:8
                        Action {objectName:"topologyBack";text:"← Back";onClicked:topologyBack()}
                        PlainLabel {text:topologyBackStack.length && topologyBackStack[topologyBackStack.length-1].kind==="selection" ? "Reference jump · Alt+Left to return" : topologyTablesReveal ? "Topology source · current workbench cutoff unchanged" : topologyScopeLabel;Layout.fillWidth:true;elide:Text.ElideRight;color:muted;font.pixelSize:11}
                    }
                    ColumnLayout {
                        id: topologyPanel
                        visible: tab === "Topology"
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        spacing: 4
                        RowLayout {
                            Layout.fillWidth: true
                            Layout.margins: 8
                            FieldChoice {
                                id: topologyFamilyChoice
                                objectName: "topologyFamily"
                                visible: (topologyData.projections || []).length > 1
                                Layout.fillWidth: true
                                implicitHeight: 28
                                model: topologyData.projections || []
                                textRole: "label"
                                valueRole: "family"
                                currentIndex: Math.max(0, (topologyData.projections || []).findIndex(function(p){return p.family===topologyFamily;}))
                                onActivated: {topologyFamily=currentValue;topologyFocus="";}
                                Accessible.name: "Topology view family, without changing the decoding profile"
                                SafeTip { visible: anchorHovered; text: "Filters derived objects only. The scan interpretation profile is unchanged." }
                            }
                            PlainLabel {
                                visible: (topologyData.projections || []).length <= 1
                                text: (topologyData.projections || []).length ? topologyData.projections[0].label : "Signal topology"
                                Layout.fillWidth: true
                                color: ink
                                elide: Text.ElideRight
                            }
                            Action { objectName:"topologyRetry"; text:topologyLoading ? "Loading…" : "Reload"; enabled:backendReady && !!analysisState.complete && !topologyLoading; onClicked:loadTopology(false) }
                        }
                        PaletteInput {
                            id: topologySearch
                            objectName: "topologySearch"
                            Layout.fillWidth: true
                            Layout.leftMargin: 8
                            Layout.rightMargin: 8
                            implicitHeight: 30
                            placeholderText: "Search records · > commands · # PID/SID"
                            placeholderTextColor: muted
                            Accessible.name: "Search loaded topology objects" + (paletteInput===topologySearch ? " · " + paletteStatus : "")
                            selectByMouse: true
                        }
                        PlainLabel {
                            objectName: "topologyContext"
                            Layout.fillWidth: true
                            Layout.leftMargin: 8
                            Layout.rightMargin: 8
                            font.pixelSize: 11
                            wrapMode: Text.Wrap
                            color: muted
                            text: topologyScopeLabel + " · observed through packet #" + num(topologyData.at_packet === undefined ? currentPacket() : topologyData.at_packet) + "\n" + (topologyData.nodes || []).length + " / " + ((topologyData.page || {}).total || 0) + " objects loaded" + (topologySearch.query.trim() ? " · search covers loaded objects only" : "") + " · ↑ ↓ focus · Enter select"
                        }
                        PlainLabel {
                            objectName:"topologyStatus"
                            visible: !!topologyError || topologyStale || topologyLoading
                            Layout.fillWidth: true
                            Layout.leftMargin: 8
                            Layout.rightMargin: 8
                            wrapMode: Text.Wrap
                            color: topologyError ? removedColor : warningColor
                            text: topologyLoading ? "Loading objects at this cutoff…" : topologyError || "Stale observation. Reload to inspect the current cutoff."
                            Accessible.name: text
                        }
                        PlainLabel {
                            visible: !!topologySelection && !topologyRows.some(function(r){return r.node_id===topologySelection;})
                            Layout.fillWidth: true
                            Layout.leftMargin: 8
                            Layout.rightMargin: 8
                            wrapMode: Text.Wrap
                            color: muted
                            text: "Selected object is retained; its row is hidden by the current search or collapsed branch."
                        }
                        RowLayout {
                            Layout.fillWidth: true
                            Layout.leftMargin: 8
                            Layout.rightMargin: 8
                            TinyLabel { text: "OBJECT / IDENTITY"; Layout.fillWidth:true }
                            TinyLabel { text: "STATE"; Layout.preferredWidth:100 }
                            TinyLabel { text: "SOURCES"; Layout.preferredWidth:54; horizontalAlignment:Text.AlignRight }
                        }
                        ListView {
                            id: topologyList
                            objectName: "topologyTree"
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            clip: true
                            model: topologyRows
                            reuseItems: true
                            activeFocusOnTab: true
                            keyNavigationEnabled: true
                            boundsBehavior: Flickable.StopAtBounds
                            Accessible.role: Accessible.Tree
                            Accessible.name: "Signal topology objects"
                            Accessible.description: "Arrow keys move focus. Left and right collapse or expand. Enter and Space select an object. Tab moves to other controls."
                            ScrollBar.vertical: ScrollBar {}
                            onCurrentIndexChanged: {let row=topologyRows[currentIndex];if(row && !row.more)topologyFocus=row.node_id;}
                            Keys.onReturnPressed: {let row=topologyRows[currentIndex];if(row)activateTopologyRow(row);}
                            Keys.onSpacePressed: {let row=topologyRows[currentIndex];if(row)activateTopologyRow(row);}
                            Keys.onRightPressed: {
                                let row=topologyRows[currentIndex];if(!row || row.more)return;
                                if(row.branch && !row.open)toggleTopologyRow(row);
                                else if(currentIndex+1<count && topologyRows[currentIndex+1].depth>row.depth)currentIndex++;
                            }
                            Keys.onLeftPressed: {
                                let row=topologyRows[currentIndex];if(!row)return;
                                if(row.branch && row.open && !topologySearch.query.trim())toggleTopologyRow(row);
                                else for(let i=currentIndex-1;i>=0;--i)if(topologyRows[i].depth<row.depth){currentIndex=i;break;}
                            }
                            Keys.onPressed: function(event){if(event.key===Qt.Key_Home || event.key===Qt.Key_End){if(count)currentIndex=event.key===Qt.Key_Home?0:count-1;event.accepted=true;}}
                            delegate: NavItem {
                                id: topologyDelegate
                                required property var modelData
                                required property int index
                                objectName: "topologyNode:" + (modelData.node_id || ("more:"+index))
                                width: ListView.view.width
                                height: treeRowHeight
                                focusPolicy: Qt.NoFocus
                                leftPadding: 6 + modelData.depth*14
                                rightPadding: 8
                                highlighted: !modelData.more && topologySelection === modelData.node_id
                                keyboardCurrent: topologyList.activeFocus && topologyList.currentIndex === index
                                Accessible.role: Accessible.TreeItem
                                Accessible.name: modelData.more ? "Show " + modelData.remaining + " more objects" : modelData.node.label + ". " + topologyIdentityText(modelData.node) + ". " + topologyStatusText(modelData.node) + ". " + (modelData.node.evidence || []).length + " sources."
                                Accessible.description: "Level " + (modelData.depth+1) + (modelData.branch ? (modelData.open ? ", expanded" : ", collapsed") : "")
                                Accessible.selected: highlighted
                                Accessible.focusable: true
                                Accessible.focused: keyboardCurrent
                                Accessible.onPressAction: clicked()
                                contentItem: RowLayout {
                                    spacing: 5
                                    PlainLabel {
                                        text: modelData.more ? "+" : modelData.branch ? (modelData.open ? "▾" : "▸") : "·"
                                        color:muted
                                        Layout.preferredWidth:12
                                        Layout.fillHeight:true
                                        verticalAlignment:Text.AlignVCenter
                                        MouseArea { anchors.fill:parent; enabled:!!modelData.branch; onClicked:{topologyList.currentIndex=index;topologyList.forceActiveFocus();toggleTopologyRow(modelData);} }
                                    }
                                    PlainLabel {
                                        text: modelData.more ? "Show more · " + modelData.remaining + " remaining" : modelData.node.label + (topologyIdentityText(modelData.node) ? " · " + topologyIdentityText(modelData.node) : "")
                                        color: ink
                                        Layout.fillWidth: true
                                        Layout.minimumWidth: 0
                                        elide: Text.ElideRight
                                    }
                                    PlainLabel { visible:!modelData.more; text:topologyStatusText(modelData.node); color:muted; Layout.preferredWidth:100; elide:Text.ElideRight; font.pixelSize:10 }
                                    PlainLabel { visible:!modelData.more; text:modelData.more ? "" : String((modelData.node.evidence || []).length); color:muted; Layout.preferredWidth:40; horizontalAlignment:Text.AlignRight }
                                }
                                onClicked: {topologyList.currentIndex=index;topologyList.forceActiveFocus();activateTopologyRow(modelData);}
                                SafeTip { visible:anchorHovered; text:modelData.more ? "Reveal the next group of loaded objects" : modelData.node.label+"\n"+topologyFullIdentityText(modelData.node)+"\n"+topologyStatusText(modelData.node)+"\n"+(modelData.node.unresolved_reasons || []).join("\n") }
                            }
                            PlainLabel {
                                anchors.centerIn: parent
                                width: parent.width-30
                                horizontalAlignment: Text.AlignHCenter
                                wrapMode: Text.Wrap
                                visible: !topologyRows.length && !topologyLoading
                                text: !analysisState.complete ? "Analyze a source to derive semantic objects." : topologyError ? "Topology is unavailable. Raw evidence remains in Tables." : topologySearch.query.trim() ? "No loaded objects match. Clear search or load more objects." : "Retained " + ((topologyData.counts || {}).raw_sections || (analysisState.tables || []).length) + " raw sections. No semantic relationships can be established in this context. Open Tables for the original evidence."
                                color:muted
                            }
                        }
                        Action {
                            objectName:"topologyLoadMore"
                            visible: !!(topologyData.page || {}).has_more
                            text: topologyLoading ? "Loading…" : "Load more objects · " + ((topologyData.page || {}).total-(topologyData.nodes || []).length) + " remaining"
                            Layout.fillWidth:true
                            Layout.margins:8
                            enabled:backendReady && !topologyLoading && !topologyStale
                            onClicked:loadTopology(true)
                        }
                    }
                    PaletteInput {
                        id: recordSearch
                        visible: tab !== "Topology"
                        objectName: "recordSearch"
                        Layout.fillWidth: true
                        Layout.leftMargin: 8
                        Layout.rightMargin: 8
                        Layout.topMargin: 8
                        implicitHeight: 30
                        placeholderText: "Search records · > commands · # PID/SID"
                        placeholderTextColor: muted
                        selectByMouse: true
                        Accessible.name: "Search records by name, packet identifier or service identifier" + (paletteInput===recordSearch ? " · " + paletteStatus : "")
                    }
                    RowLayout {
                        visible: tab === "Tables"
                        Layout.fillWidth: true
                        Layout.leftMargin: 8
                        Layout.rightMargin: 8
                        PlainLabel { text: "Type"; color: muted }
                        FieldChoice {
                            id: tableFamilyChoice
                            objectName: "tableFamilyFilter"
                            Accessible.name: "Table type across all PIDs"
                            Layout.fillWidth: true
                            implicitHeight: 28
                            model: tableFamilies.map(function(name, index) {return {label:index === 0 ? "All types" : tableLabel(name),value:index === 0 ? "" : name};})
                            textRole: "label"
                            valueRole: "value"
                            currentIndex: Math.max(0, tableFamilies.indexOf(filter || "All tables"))
                            onActivated: selectTableFamily(currentValue)
                        }
                    }
                    ColumnLayout {
                        visible: tab === "Changes"
                        Layout.fillWidth: true
                        Layout.margins: 8
                        spacing: 4
                        RowLayout {
                            Layout.fillWidth: true
                            PlainLabel { text: "A"; color: muted; Layout.preferredWidth: 14 }
                            FieldInput {
                                id: fromPacket
                                objectName: "fromPacket"
                                Layout.fillWidth: true
                                implicitHeight: 28
                                placeholderText: "Packet cutoff"
                                enabled: backendReady && !core.comparing
                                selectByMouse: true
                                onTextChanged: { comparison = {}; comparisonFilters = []; comparisonRun.highlighted = false; }
                                Accessible.name: "Snapshot A inclusive packet cutoff"
                                onAccepted: compareSnapshots(0)
                                Keys.onEscapePressed: recordList.forceActiveFocus()
                            }
                            Action {
                                objectName: "captureA"
                                text: "Use current"
                                enabled: backendReady && !!analysisState.complete && !core.comparing
                                onClicked: { fromPacket.text = String(currentPacket()); comparison = {}; }
                                SafeTip { visible: anchorHovered; text: "Set A to the selected history snapshot, or the final packet in Latest view." }
                            }
                        }
                        RowLayout {
                            Layout.fillWidth: true
                            PlainLabel { text: "B"; color: muted; Layout.preferredWidth: 14 }
                            FieldInput {
                                id: toPacket
                                objectName: "toPacket"
                                Layout.fillWidth: true
                                implicitHeight: 28
                                placeholderText: "Packet cutoff"
                                enabled: backendReady && !core.comparing
                                selectByMouse: true
                                onTextChanged: { comparison = {}; comparisonFilters = []; comparisonRun.highlighted = false; }
                                Accessible.name: "Snapshot B inclusive packet cutoff"
                                onAccepted: compareSnapshots(0)
                                Keys.onEscapePressed: recordList.forceActiveFocus()
                            }
                            Action {
                                objectName: "captureB"
                                text: "Use current"
                                enabled: backendReady && !!analysisState.complete && !core.comparing
                                onClicked: { toPacket.text = String(currentPacket()); comparison = {}; }
                                SafeTip { visible: anchorHovered; text: "Set B to the selected history snapshot, or the final packet in Latest view." }
                            }
                        }
                        RowLayout {
                            Layout.fillWidth: true
                            Repeater {
                                model: ["A", "B"]
                                FieldChoice {
                                    required property string modelData
                                    objectName: "comparisonPreset" + modelData
                                    Layout.fillWidth: true
                                    Layout.preferredWidth: 1
                                    implicitHeight: 28
                                    textRole: "label"
                                    model: tab === "Changes" ? comparisonPresets() : []
                                    enabled: backendReady && !!analysisState.complete && !core.comparing
                                    Accessible.name: "Snapshot " + modelData + " from history"
                                    displayText: modelData + " · History…"
                                    onActivated: {
                                        let choice = model[currentIndex];
                                        if (choice && choice.packet >= 0) {
                                            if (modelData === "A") fromPacket.text = String(choice.packet);
                                            else toPacket.text = String(choice.packet);
                                        }
                                        currentIndex = 0;
                                    }
                                }
                            }
                        }
                        RowLayout {
                            Layout.fillWidth: true
                            FieldChoice {
                                id: changeKind
                                objectName: "changeKind"
                                Layout.fillWidth: true
                                implicitHeight: 28
                                textRole: "label"
                                valueRole: "value"
                                model: [{label:"All changes",value:"all"},{label:"Services",value:"services"},{label:"Tables",value:"tables"},{label:"Events",value:"events"}]
                                enabled: backendReady && !core.comparing
                                onActivated: { comparison = {}; comparisonFilters = []; }
                                Accessible.name: "Snapshot change category"
                            }
                            Action {
                                objectName: "swapComparison"
                                text: "Swap A/B"
                                enabled: backendReady && !!analysisState.complete && !core.comparing
                                onClicked: { let before = fromPacket.text; fromPacket.text = toPacket.text; toPacket.text = before; }
                            }
                            Action {
                                id: comparisonRun
                                objectName: "runComparison"
                                text: core.comparing ? "Comparing…" : "Compare"
                                primary: true
                                enabled: backendReady && !core.comparing && !!analysisState.complete && validPacket(fromPacket.text) && validPacket(toPacket.text)
                                onClicked: { highlighted = false; compareSnapshots(0); }
                                onActiveFocusChanged: if (activeFocus) highlighted = false
                                Rectangle { anchors.fill: parent; anchors.margins: -2; visible: comparisonRun.highlighted; color: "transparent"; border.color: blue; border.width: focusWidth; radius: 2 }
                            }
                        }
                        PlainLabel {
                            // Compact panes show the loaded A → B context inline with the filter chips.
                            visible: !compactComparison || !!comparisonError || !comparison.summary
                            Layout.fillWidth: true
                            wrapMode: Text.Wrap
                            font.pixelSize: 11
                            color: comparisonError ? removedColor : muted
                            text: comparisonError || (!analysisState.complete ? "Analyze a source first." : !validPacket(fromPacket.text) || !validPacket(toPacket.text) ? "Enter whole packet indexes from 0 to " + num(Number(analysisState.packets) - 1) + "." : comparison.source ? "A " + num(comparison.from_packet) + " → B " + num(comparison.to_packet) + " · " + num(comparison.total_changes) + " changes" : "Choose A and B, then Compare. Observed valid-current state only.")
                            SafeTip { visible: comparisonContextHover.hovered; text: (comparison.source || "") + "\nObserved valid-current state. Absence does not prove a service stopped broadcasting.\n" + Object.keys(comparison.scope || {}).map(function (key) { return key + ": " + comparison.scope[key]; }).join("\n") }
                            HoverHandler { id: comparisonContextHover }
                        }
                        PlainLabel {
                            visible: !!comparison.source && !compactComparison
                            text: comparison.source || ""
                            Layout.fillWidth: true
                            elide: Text.ElideMiddle
                            font.pixelSize: 11
                            color: muted
                            SafeTip { visible: sourceHover.hovered; text: comparison.source || "" }
                            HoverHandler { id: sourceHover }
                        }
                        Flow {
                            visible: !!comparison.summary
                            Layout.fillWidth: true
                            spacing: 4
                            Repeater {
                                model: ["added","removed","changed"]
                                SummaryChip {
                                    id: changeFilter
                                    required property string modelData
                                    objectName: "comparisonFilter_" + modelData
                                    implicitHeight: 24
                                    disclosure: false
                                    text: (modelData === "added" ? "+" : modelData === "removed" ? "−" : "~") + num(comparisonCounts[modelData]) + (compactComparison ? "" : " " + modelData)
                                    checked: comparisonFilters.indexOf(modelData) >= 0
                                    Accessible.name: num(comparisonCounts[modelData]) + " " + modelData + " changes on this page"
                                    help: "A " + num(comparison.from_packet) + " → B " + num(comparison.to_packet) + " · toggle " + modelData + " changes on this page. No active filters shows all changes."
                                    contentItem: PlainLabel { text:changeFilter.text; color:changeColor(changeFilter.modelData); horizontalAlignment:Text.AlignHCenter; verticalAlignment:Text.AlignVCenter; font.pixelSize:11 }
                                    onClicked: {
                                        comparisonFilters = comparisonFilters.indexOf(modelData)>=0 ? comparisonFilters.filter(function(kind){return kind!==modelData;}) : comparisonFilters.concat([modelData]);
                                        recordList.currentIndex = rows.length ? 0 : -1;
                                    }
                                }
                            }
                        }
                        PlainLabel {
                            visible: !!comparison.summary && (comparisonFilters.length > 0 || comparison.total_changes > 100)
                            Layout.fillWidth: true
                            font.pixelSize: 11
                            color: muted
                            wrapMode: Text.Wrap
                            text: rows.length + " shown · filters apply to this page"
                        }
                        PlainLabel {
                            visible: !!comparison.source && !compactComparison
                            Layout.fillWidth: true
                            wrapMode: Text.Wrap
                            font.pixelSize: 11
                            color: muted
                            text: "Observed valid-current state. Absence does not prove a service stopped broadcasting."
                            SafeTip { visible: scopeHover.hovered; text: Object.keys(comparison.scope || {}).map(function (key) { return key + ": " + comparison.scope[key]; }).join("\n") }
                            HoverHandler { id: scopeHover }
                        }
                        RowLayout {
                            visible: !!comparison.source && comparison.total_changes > 100
                            Layout.fillWidth: true
                            Action { text: "Previous"; enabled: backendReady && !core.comparing && Number(comparison.offset) > 0; onClicked: compareSnapshots(Math.max(0, comparison.offset - 100)) }
                            PlainLabel { text: (Number(comparison.offset || 0) + 1) + "–" + Math.min(Number(comparison.offset || 0) + 100, Number(comparison.total_changes || 0)); color: muted; Layout.fillWidth: true; horizontalAlignment: Text.AlignHCenter }
                            Action { text: "Next"; enabled: backendReady && !core.comparing && comparison.next_offset !== null && comparison.next_offset !== undefined; onClicked: compareSnapshots(comparison.next_offset) }
                        }
                    }
                    RowLayout {
                        // Compact comparison chips already carry the counts; an empty row would take spare height.
                        visible: !(tab === "Changes" && compactComparison && !!comparison.summary)
                        Layout.fillWidth: true
                        Layout.leftMargin: 10
                        Layout.rightMargin: 8
                        PlainLabel {
                            id: recordCountLabel
                            visible: tab !== "Topology"
                            text: tab === "Tables" ? tableModel.count_text : tab + " · " + rows.length + (recordSearch.query.trim() ? " / " + unfilteredRows.length : "")
                            Layout.fillWidth: true
                            Layout.minimumWidth: 0
                            elide: Text.ElideRight
                            color: muted
                            font.pixelSize: 11
                        }
                        Action { visible: tab === "Tables"; objectName:"tableGroupToggle"; text: groupedTables ? "Sections" : "Tables"; implicitHeight:24; onClicked:groupedTables=!groupedTables }
                        Action {
                            objectName: "toggleInvalidSections"
                            visible: tab === "Tables"
                            implicitHeight: 24
                            text: (showInvalidSections ? "✓ " : "") + "Bad CRC · " + hiddenInvalidCount
                            onClicked: showInvalidSections = !showInvalidSections
                            SafeTip { visible:anchorHovered; text:"Include CRC-invalid evidence in table groups and exact sections" }
                        }
                    }
                    RowLayout {
                        visible: tab === "Tables"
                        Layout.fillWidth:true
                        readonly property int total: groupedTables ? logicalTableCount : rawTableRows.length
                        Action { objectName:"tablePrevious"; text:"Previous"; enabled:tablePage>0; onClicked:tablePage-- }
                        PlainLabel { text: parent.total ? (Math.min(tablePage,Math.max(0,Math.ceil(parent.total/100)-1))*100+1)+"–"+Math.min((tablePage+1)*100,parent.total)+" of "+parent.total+(groupedTables?" tables":" sections") : "0 records"; color:muted; Layout.fillWidth:true }
                        Action { objectName:"tableNext"; text:"Next"; enabled:(tablePage+1)*100<parent.total; onClicked:tablePage++ }
                    }
                    PlainLabel {
                        visible: tab !== "Topology" && selectionHidden && (tab === "Tables" || !!recordSearch.query.trim())
                        text: "Selected evidence is retained; its record is hidden by this filter."
                        Layout.fillWidth: true
                        Layout.leftMargin: 10
                        Layout.rightMargin: 10
                        wrapMode: Text.Wrap
                        color: muted
                        font.pixelSize: 11
                    }
                    RowLayout {
                        id: serviceColumnHeader
                        visible: tab === "Services"
                        Layout.fillWidth: true
                        Layout.leftMargin: 10
                        Layout.rightMargin: 10
                        spacing: 8
                        TinyLabel { text: "LCN"; Layout.preferredWidth: 38; horizontalAlignment:Text.AlignHCenter }
                        TinyLabel { text: "SERVICE / STREAM DETAILS"; Layout.fillWidth:true }
                    }
                    ListView {
                        id: recordList
                        // Keep publication work proportional to visible rows. The full
                        // model remains available for search, paging and keyboard use.
                        cacheBuffer: 0
                        visible: tab !== "Topology"
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        model: rows
                        clip: true
                        reuseItems: true
                        keyNavigationEnabled: true
                        activeFocusOnTab: true
                        boundsBehavior: Flickable.StopAtBounds
                        ScrollBar.vertical: ScrollBar { policy: tab === "Changes" ? ScrollBar.AlwaysOn : ScrollBar.AsNeeded }
                        Keys.onReturnPressed: if (currentIndex >= 0)
                            activate(rows[currentIndex])
                        Keys.onSpacePressed: if (currentIndex >= 0) {
                            let row=rows[currentIndex]; if(tab === "Tables" && row.logical) toggleTableGroup(row); else activate(row);
                        }
                        delegate: ItemDelegate {
                            id: recordDelegate
                            required property var modelData
                            required property int index
                            objectName: tab === "Services" ? "service_" + modelData.id : tab === "Issues" ? "issue_" + modelData.code : "record_" + index
                            width: ListView.view.width
                            height: tab === "Changes" ? Math.max(58,contentItem.implicitHeight + topPadding + bottomPadding) : tab === "Issues" ? 88 : tab === "Services" ? 72 : modelData.logical ? 100 : 58
                            focusPolicy: Qt.StrongFocus
                            Keys.onSpacePressed: { if(tab === "Tables" && modelData.logical) toggleTableGroup(modelData); else activate(modelData); }
                            Keys.onRightPressed: { if(tab === "Tables" && modelData.logical && !expandedTables[modelData.group.id]) toggleTableGroup(modelData); }
                            Keys.onLeftPressed: { if(tab === "Tables" && modelData.logical && expandedTables[modelData.group.id]) toggleTableGroup(modelData); }
                            leftPadding: 12
                            rightPadding: 12
                            topPadding: 8
                            bottomPadding: 8
                            highlighted: tab === "Changes" ? !!selectedChange && selectedChange.key === modelData.key && selectedChange.kind === modelData.kind : tab === "Services" ? selected === modelData.source_id && selectedService === modelData.id : selected === (modelData.source_id || modelData.id)
                            background: Rectangle {
                                color: recordDelegate.highlighted ? selectionSurface : recordDelegate.hovered ? hoverSurface : "transparent"
                                border.color: recordDelegate.activeFocus ? blue : "transparent"
                            }
                            contentItem: ColumnLayout {
                                spacing: 6
                                RowLayout {
                                    Layout.fillWidth: true
                                    spacing: 8
                                    Item {
                                        Layout.preferredWidth: tab === "Services" ? 38 : 20
                                        Layout.fillHeight: true
                                        PlainLabel {
                                            anchors.top: parent.top; anchors.horizontalCenter: parent.horizontalCenter
                                            text: tab === "Services" ? (modelData.logical_channel_number === null || modelData.logical_channel_number === undefined ? "—" : modelData.logical_channel_number) : tab === "Tables" ? (modelData.logical ? (expandedTables[modelData.group.id] ? "▾" : "▸") : "·") : ""
                                            color: tab === "Tables" ? tableColor(modelData.name) : muted
                                            font.family: "monospace"
                                        }
                                        MouseArea { anchors.fill:parent; enabled:tab === "Tables" && !!modelData.logical; onClicked:toggleTableGroup(modelData) }
                                    }
                                    Column {
                                        Layout.fillWidth: true
                                        spacing: 5
                                        PlainLabel {
                                            text: tab === "Services" ? (modelData.name || "Unnamed service") : rowTitle(modelData)
                                            width: parent.width
                                            color: tab === "Tables" ? tableColor(modelData.name) : tab === "Changes" ? (modelData.change === "added" ? addedColor : modelData.change === "removed" ? removedColor : changedColor) : modelData.valid === false ? removedColor : tab === "Issues" ? warningColor : ink
                                            elide: Text.ElideRight
                                            font.pixelSize: 12
                                        }
                                        PlainLabel {
                                            // Field diffs below already name each changed field.
                                            visible: tab !== "Changes" || !(modelData.changed_fields || []).length
                                            text: rowSubtitle(modelData)
                                            width: parent.width; color: muted; font.pixelSize: 11
                                            elide: Text.ElideRight
                                            wrapMode: Text.Wrap
                                            maximumLineCount: tab === "Issues" || modelData.logical ? 3 : 1
                                        }
                                        // Type and media PIDs share one line; the tooltip keeps the full text.
                                        PlainLabel {
                                            visible: tab === "Services"
                                            text: "Type " + hex(modelData.service_type, 2) + " · " + (modelData.service_type_name || "Unknown service type") + " · V " + pidList(modelData.video_pids, modelData.media_status) + " · A " + pidList(modelData.audio_pids, modelData.media_status)
                                            width: parent.width; color: muted; font.pixelSize:11; elide:Text.ElideRight
                                        }
                                    }
                                }
                                ComparisonDiff {
                                    visible: tab === "Changes"
                                    Layout.fillWidth: true
                                    change: visible ? recordDelegate.modelData : null
                                    maxRows: compactComparison ? 3 : 0
                                    onFieldActivated: {
                                        recordList.currentIndex = recordDelegate.index;
                                        if (!recordDelegate.highlighted) activate(recordDelegate.modelData);
                                    }
                                }
                            }
                            onClicked: {
                                recordList.currentIndex = index;
                                activate(modelData);
                            }
                            SafeTip {
                                visible: anchorHovered
                                text: (tab === "Services" ? "LCN: Logical channel number (" + (modelData.lcn_status || "unknown") + ") · SID: Service identifier · PMT: Program Map Table\nProvider: " + (modelData.provider || "unknown") + " · Group: " + (modelData.group || "unknown") + "\n" : "") + (tab === "Tables" ? modelData.name + " · " + explanation(modelData.name) + "\n" : "") + rowTitle(modelData) + "\n" + rowSubtitle(modelData) + (tab === "Services" ? "\nType " + hex(modelData.service_type, 2) + " · " + (modelData.service_type_name || "Unknown service type") + "\nVideo PIDs: " + pidList(modelData.video_pids,modelData.media_status) + " · Audio PIDs: " + pidList(modelData.audio_pids,modelData.media_status) : "")
                            }
                        }
                        PlainLabel {
                            id: recordEmptyHint
                            objectName: "recordEmptyHint"
                            anchors.centerIn: parent
                            width: parent.width - 40
                            horizontalAlignment: Text.AlignHCenter
                            wrapMode: Text.Wrap
                            visible: rows.length === 0
                            text: core.availability === "starting" ? "Starting backend…" : !core.available ? "Backend disconnected. Restart the application to continue." : core.cancelling ? "Cancelling scan… Waiting for the worker to stop." : core.busy ? "Scanning source…" : analysisState.analysis_status === "cancelled" ? "Scan cancelled. Analyze a source to start again." : core.comparing && tab === "Changes" ? "Comparing observed snapshots…" : core.error ? "Unable to load data. See the error below." : !analysisState.source ? "Open a transport stream to inspect PSI / SI tables." : recordSearch.query.trim() ? "No records match this search. Press Escape in the search box to clear it." : tab === "Changes" ? comparisonFilters.length ? "No matching changes on this page. Toggle the filters or use Previous / Next." : comparison.source ? "No changes between these cutoffs in this category." : "Set A and B to investigate a version change." : (tab === "Services" || tab === "EPG") && (analysisState.tables || []).length ? "No derived " + (tab === "Services" ? "services" : "programme events") + " in this view. Open Tables for native signalling fields and raw evidence; an empty projection does not mean decoding failed." : "No " + tab.toLowerCase() + " in this view."
                            color: muted
                        }
                    }
                }
            }
            Card {
                id: inspectorPane
                SplitView.preferredWidth: savedLayout.inspector
                SplitView.minimumWidth: 330
                SplitView.maximumWidth: 1600
                ColumnLayout {
                    id: topologySummaryColumn
                    visible: topologySummary
                    anchors.fill: parent
                    anchors.margins: 10
                    spacing: 6
                    TinyLabel { text:"OBJECT SUMMARY"; Layout.fillWidth:true }
                    ScrollView {
                        id: topologySummaryScroll
                        Layout.fillWidth:true
                        Layout.preferredHeight: Math.min(compactInspector ? 160 : 240, inspectorPane.height*0.42)
                        clip:true
                        contentWidth:availableWidth
                        TextArea {
                            objectName:"topologySummaryText"
                            readOnly:true
                            selectByMouse:true
                            textFormat:TextEdit.PlainText
                            wrapMode:TextEdit.Wrap
                            color:ink
                            font.pixelSize:12
                            text: !topologyNode ? "Select a semantic object to see its identity, claims and all source references. Arrow keys move focus without changing the selected object.\n\n" + topologyCoverageText() : topologyNode.label + "\n" + topologyFullIdentityText(topologyNode) + "\n" + topologyStatusText(topologyNode) + "\nObservation: " + topologyNode.observation_status + " · Resolution: " + topologyNode.resolution_status + "\n" + topologyNode.object_type + " · " + topologyNode.family + ((topologyNode.reference_sources || []).length ? "\n\nCatalog provenance (external reference, not captured section evidence):\n"+JSON.stringify(topologyNode.reference_sources,null,2) : "") + "\n\n" + Object.keys(topologyNode.attributes || {}).map(function(k){let v=topologyNode.attributes[k];return k+": "+(v!==null && typeof v==="object" ? JSON.stringify(v) : Shared.workbench.value(k,v));}).join("\n") + (Object.keys(topologyNode.attribute_conflicts || {}).length ? "\n\nConflicting assertions:\n"+JSON.stringify(topologyNode.attribute_conflicts,null,2) : "") + ((topologyNode.unresolved_reasons || []).length ? "\n\nUnresolved:\n"+topologyNode.unresolved_reasons.join("\n") : "")
                        }
                    }
                    PlainLabel { visible:!!topologyNode; text:"Relations · "+topologyRelations.length+"\n"+(topologyData.coverage ? "Only implemented, evidence-backed relations are shown." : ""); color:muted; Layout.fillWidth:true; wrapMode:Text.Wrap; font.pixelSize:11; HoverHandler {id:topologyCoverageHover} SafeTip {visible:topologyCoverageHover.hovered;text:topologyCoverageText()} }
                    ListView {
                        id: topologyRelationsList
                        visible:topologyRelations.length>0
                        Layout.fillWidth:true
                        Layout.preferredHeight:Math.min(compactInspector ? 72 : 100,topologyRelations.length*36)
                        clip:true
                        model:topologyRelations
                        activeFocusOnTab:true
                        keyNavigationEnabled:true
                        ScrollBar.vertical:ScrollBar {}
                        Keys.onReturnPressed: {let edge=topologyRelations[currentIndex];if(edge)selectTopologyRelation(edge);}
                        delegate: NavItem {
                            required property var modelData
                            required property int index
                            readonly property string targetId: modelData.from===topologySelection ? modelData.to : modelData.from
                            readonly property var targetNode: topologyNodeById(targetId)
                            width:ListView.view.width
                            height:36
                            text:(modelData.from===topologySelection ? modelData.relation.replace(/_/g," ")+" → " : "← "+modelData.relation.replace(/_/g," ")+" · ")+(targetNode ? targetNode.label : targetId)+" · "+modelData.resolution_status
                            keyboardCurrent:topologyRelationsList.activeFocus && topologyRelationsList.currentIndex===index
                            focusPolicy:Qt.NoFocus
                            Accessible.name:text
                            onClicked:selectTopologyRelation(modelData)
                            SafeTip { visible:anchorHovered; text:anchorText+"\n"+(modelData.evidence || []).length+" relationship sources" }
                        }
                    }
                    TinyLabel { text:"ALL SOURCES · "+topologySources.length; Layout.fillWidth:true }
                    ListView {
                        id: topologySourcesList
                        objectName:"topologySources"
                        Layout.fillWidth:true
                        Layout.fillHeight:true
                        clip:true
                        model:topologySources
                        activeFocusOnTab:true
                        keyNavigationEnabled:true
                        reuseItems:true
                        ScrollBar.vertical:ScrollBar {}
                        Accessible.role:Accessible.List
                        Accessible.name:"All object and relationship source references"
                        Keys.onReturnPressed: {let item=topologySources[currentIndex];if(item)openTopologyEvidence(item.ref);}
                        Keys.onSpacePressed: {let item=topologySources[currentIndex];if(item)openTopologyEvidence(item.ref);}
                        delegate: NavItem {
                            required property var modelData
                            required property int index
                            objectName:"topologySource:"+index
                            width:ListView.view.width
                            height:74
                            enabled:backendReady && !topologyStale
                            keyboardCurrent:topologySourcesList.activeFocus && topologySourcesList.currentIndex===index
                            focusPolicy:Qt.NoFocus
                            text:(modelData.relation ? modelData.relation+" · " : "")+topologySourceText(modelData.ref)
                            contentItem:PlainLabel { text:parent.text; color:ink; wrapMode:Text.Wrap; elide:Text.ElideRight; maximumLineCount:4; font.pixelSize:11 }
                            Accessible.name:text
                            onClicked:{topologySourcesList.currentIndex=index;openTopologyEvidence(modelData.ref);}
                            SafeTip {visible:anchorHovered;text:anchorText}
                        }
                    }
                    PlainLabel { visible:!!topologyNode && !topologySources.length; text:"No source references are available for this object."; color:muted; Layout.fillWidth:true; wrapMode:Text.Wrap }
                }
                ColumnLayout {
                    id: inspectorColumn
                    visible: !topologySummary
                    anchors.fill: parent
                    anchors.margins: 10
                    spacing: spaceUnit
                    TinyLabel { visible:core.inspecting || !detail.id; text:core.inspecting ? "LOADING SECTION…" : "Select a section"; Layout.fillWidth:true }
                    ColumnLayout {
                        visible: !!topologyEvidenceRef && !protocolSourceRef
                        Layout.fillWidth:true
                        spacing:4
                        RowLayout {
                            Layout.fillWidth:true
                            Action { objectName:"topologyReturnObject"; text:"← Object"; onClicked:topologyBack() }
                            Action { objectName:"topologyShowTables"; text:"Show in Tables"; enabled:topologyCanReveal; onClicked:showTopologyInTables(); SafeTip {visible:anchorHovered;text:topologyCanReveal ? "Reveal this exact section in Tables without changing the workbench cutoff" : "This source has a different cutoff. Inspect it here; use an explicit snapshot change to show it in Tables."} }
                            Item {Layout.fillWidth:true}
                            Action { objectName:"topologyRetrySource"; text:"Retry"; enabled:backendReady && !core.inspecting && !topologyStale; onClicked:openTopologyEvidence(topologyEvidenceRef,false) }
                        }
                        PlainLabel {
                            objectName:"topologyEvidenceContext"
                            Layout.fillWidth:true
                            wrapMode:Text.Wrap
                            maximumLineCount:compactInspector ? 3 : 5
                            elide:Text.ElideRight
                            color:muted
                            font.pixelSize:11
                            text:topologyActiveSourceText()
                            HoverHandler {id:topologyEvidenceHover}
                            SafeTip {visible:topologyEvidenceHover.hovered;text:anchorText}
                        }
                        PlainLabel {
                            objectName:"topologyPrecision"
                            Layout.fillWidth:true
                            wrapMode:Text.Wrap
                            color:topologyResolution.status==="resolved" ? blue : warningColor
                            font.pixelSize:11
                            text:core.inspecting ? "Loading exact section…" : topologyResolution.message || "Resolving the requested source locator…"
                        }
                    }
                    ColumnLayout {
                        visible:!!protocolSourceRef
                        Layout.fillWidth:true
                        RowLayout {
                            Action {objectName:"protocolSourceBack";text:"← Metadata";enabled:backendReady && !core.inspecting;onClicked:protocolSourceBack()}
                            Action {objectName:"protocolSourceRetry";text:"Retry source";enabled:backendReady && !core.inspecting;onClicked:openProtocolSource({ref:protocolSourceRef,available:true},false)}
                            Item {Layout.fillWidth:true}
                        }
                        PlainLabel {Layout.fillWidth:true;wrapMode:Text.Wrap;font.pixelSize:11;color:muted;text:protocolSourceRef?"Metadata source · "+protocolSourceRef.section_id+" · revision "+protocolSourceRef.analysis_revision+" · cutoff #"+protocolSourceRef.at_packet:""}
                        PlainLabel {objectName:"protocolSourcePrecision";Layout.fillWidth:true;wrapMode:Text.Wrap;font.pixelSize:11;color:protocolSourceResolution.status==="resolved"?blue:warningColor;text:core.inspecting?"Loading exact source…":protocolSourceResolution.message || "Resolving source precision…"}
                    }
                    ColumnLayout {
                        visible: !!selectedChange
                        Layout.fillWidth: true
                        spacing: 4
                        RowLayout {
                            Layout.fillWidth: true
                            SummaryChip {
                                objectName: "inspectBefore"
                                text: compactInspector ? "A" : "A · Before"
                                Accessible.name: "A · Before"
                                disclosure: false
                                checked: comparisonSide === "before"
                                enabled: backendReady && !!selectedChange && !!selectedChange.before
                                help: "Inspect source evidence at snapshot A; the workbench snapshot stays unchanged"
                                onClicked: inspectChange(selectedChange, "before")
                            }
                            SummaryChip {
                                objectName: "inspectAfter"
                                text: compactInspector ? "B" : "B · After"
                                Accessible.name: "B · After"
                                disclosure: false
                                checked: comparisonSide === "after"
                                enabled: backendReady && !!selectedChange && !!selectedChange.after
                                help: "Inspect source evidence at snapshot B; the workbench snapshot stays unchanged"
                                onClicked: inspectChange(selectedChange, "after")
                            }
                            Item { Layout.fillWidth: true }
                            Action {
                                objectName: "useComparisonSnapshot"
                                text: "Use snapshot"
                                primary: true
                                Accessible.name: "Use snapshot " + (comparisonSide === "before" ? "A" : "B")
                                enabled: backendReady && !!selectedChange && !!selectedChange[comparisonSide] && (selectedChange[comparisonSide].evidence || []).length > 0 && !core.inspecting
                                onClicked: {
                                    let row = selectedChange, side = row[comparisonSide];
                                    selectedChange = null;
                                    comparisonWorkspace = null;
                                    tab = row.kind === "services" ? "Services" : row.kind === "events" ? "EPG" : "Tables";
                                    recordSearch.clear();
                                    snapshot(side.at_packet, side.evidence[0].id, row.kind === "services" ? side.value.id : -1);
                                }
                                SafeTip { visible: anchorHovered; text: "Switch the workbench to this cutoff. Editing and export will then use this snapshot." }
                            }
                        }
                        RowLayout {
                            Layout.fillWidth: true
                            PlainLabel { text:"Source"; color:muted; font.pixelSize:11 }
                            FieldChoice {
                                id: comparisonSource
                                objectName: "comparisonSource"
                                Layout.fillWidth: true
                                Layout.minimumWidth: 65
                                implicitHeight: 26
                                textRole: "label"
                                model: selectedChange && selectedChange[comparisonSide] ? (selectedChange[comparisonSide].evidence || []).map(function(e) {return {label:e.name + " · PID " + hex(e.pid) + " · §" + e.section + " · " + e.id};}) : []
                                currentIndex: comparisonEvidenceIndex
                                enabled: backendReady && count > 0
                                Accessible.name: "Comparison source evidence"
                                onActivated: inspectChange(selectedChange, comparisonSide, currentIndex)
                                SafeTip { visible: anchorHovered; text: "PID: Packet Identifier · " + comparisonSource.currentText }
                            }
                            Action {
                                objectName:"comparisonTopology"
                                text:"Topology"
                                Accessible.name:"Topology at the selected comparison cutoff"
                                implicitHeight:26
                                enabled:backendReady && !!selectedChange && !core.inspecting
                                onClicked:openComparisonTopology()
                                SafeTip {visible:anchorHovered;text:"Inspect semantic objects at this comparison cutoff without changing the workbench snapshot"}
                            }
                        }
                        PlainLabel {
                            text: changeFields(selectedChange) || "Section presence changed between A and B. Inspect the available side."
                            Layout.fillWidth: true
                            maximumLineCount: compactInspector ? 1 : 3
                            wrapMode: Text.WrapAnywhere
                            elide: Text.ElideRight
                            font.pixelSize: 11
                            color: changeColor(selectedChange ? selectedChange.change : "context")
                            SafeTip { visible: changeHover.hovered; text: changeFields(selectedChange, true) }
                            HoverHandler { id: changeHover }
                        }
                    }
                    RowLayout {
                        objectName: "inspectorSummary"
                        visible: !!detail.id
                        Layout.fillWidth: true
                        Layout.preferredHeight: 32
                        // The chip Flickable fills this row; never let the row take the field tree's height.
                        Layout.maximumHeight: 32
                        spacing: 2
                        SummaryChip { objectName:"standardsProfileToggle"; text:inspectorSummary.profile; checked:identityOpen; help:inspectorSummary.profileHelp; onClicked:identityOpen=!identityOpen }
                        Flickable {
                            id: summaryChips
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            contentWidth: summaryChipRow.implicitWidth
                            contentHeight: height
                            flickableDirection: Flickable.HorizontalFlick
                            boundsBehavior: Flickable.StopAtBounds
                            clip: true
                            function reveal(item) {
                                let point=item.mapToItem(contentItem,0,0);
                                contentX=Math.max(0,Math.min(Math.max(0,contentWidth-width),Math.max(point.x+item.width-width,Math.min(contentX,point.x))));
                            }
                            ScrollBar.horizontal: ScrollBar { height:4 }
                            Row {
                                id: summaryChipRow
                                spacing: 2
                                SummaryChip {
                                    id: identityChip
                                    objectName: "identityToggle"
                                    text: tableLabel(detail.name)
                                    checked: identityOpen
                                    help: detail.name + " · " + explanation(detail.name) + " · section identity and validity"
                                    scrollHost: summaryChips
                                    onClicked: identityOpen=!identityOpen
                                    contentItem: PlainLabel {
                                        id: sectionTitle
                                        text: identityChip.text
                                        color: tableColor(detail.name)
                                        font.weight: Font.DemiBold
                                        font.pixelSize: 11
                                        verticalAlignment: Text.AlignVCenter
                                        SafeTip { id:sectionTitleTip; visible:sectionTitleHover.hovered; text:detail.name + " · " + explanation(detail.name) }
                                        HoverHandler { id:sectionTitleHover }
                                    }
                                }
                                PlainLabel { visible:detail.valid===false; text:"INVALID"; color:removedColor; font.pixelSize:11; anchors.verticalCenter:parent.verticalCenter }
                                SummaryChip { objectName:"pidSummaryToggle"; text:"PID " + hex(detail.pid); checked:identityOpen; help:"PID: Packet Identifier (13 bits) · TID: Table Identifier " + hex(detail.table_id,2) + (selectedService>=0 ? " · SID: Service Identifier " + hex(selectedService) : ""); scrollHost:summaryChips; onClicked:identityOpen=!identityOpen }
                                SummaryChip { objectName:"versionSummaryToggle"; text:inspectorSummary.version; checked:identityOpen; help:"Wire version and current/next state"; scrollHost:summaryChips; onClicked:identityOpen=!identityOpen }
                                SummaryChip { objectName:"sectionGroupToggle"; text:inspectorSummary.section; checked:sectionGroupOpen; help:"Original section evidence and capture-wide table coverage"; scrollHost:summaryChips; onClicked:sectionGroupOpen=!sectionGroupOpen }
                                SummaryChip {
                                    id: crcChip
                                    objectName:"crcToggle"; text:inspectorSummary.crc; checked:crcOpen; help:"CRC: Cyclic Redundancy Check · " + (detail.crc?.status || "unavailable"); scrollHost:summaryChips; onClicked:crcOpen=!crcOpen
                                    contentItem: PlainLabel { text:crcChip.text; color:detail.crc?.status==="invalid" ? removedColor : detail.crc?.status==="valid" ? addedColor : muted; font.pixelSize:11; verticalAlignment:Text.AlignVCenter }
                                }
                                SummaryChip { objectName:"arrivalToggle"; visible:!!detail.distribution; text:num(detail.distribution?.observation_count) + " arrivals"; checked:arrivalOpen; help:"Arrival distribution in packet positions; elapsed seconds only from a supplied bitrate"; scrollHost:summaryChips; onClicked:arrivalOpen=!arrivalOpen }
                                SummaryChip { objectName:"previousOccurrences"; visible:Number(detail.occurrence_offset || 0)>0; text:"Previous arrivals"; help:"View the preceding 50 occurrence positions"; scrollHost:summaryChips; onClicked:core.inspectOccurrences(Math.max(0,Number(detail.occurrence_offset)-50)) }
                                SummaryChip { objectName:"nextOccurrences"; visible:detail.occurrence_next_offset !== undefined && detail.occurrence_next_offset !== null; text:"Next arrivals · "+num(Number(detail.occurrence_offset || 0)+(detail.occurrences || []).length)+" / "+num(detail.occurrence_total); help:"View the next 50 occurrence positions. Distribution above covers all observed arrivals."; scrollHost:summaryChips; onClicked:core.inspectOccurrences(Number(detail.occurrence_next_offset)) }
                            }
                        }
                        Row {
                            objectName: "evidenceScope"
                            spacing: 0
                            ButtonGroup { id:inspectorScopeGroup }
                            SummaryChip { ButtonGroup.group:inspectorScopeGroup; objectName:"sectionScope"; text:"Section"; checked:evidenceScope==="Section"; disclosure:false; help:"Section: fields and bytes of this exact section"; Accessible.name:"Selected section evidence"; onClicked:evidenceScope="Section" }
                            SummaryChip { ButtonGroup.group:inspectorScopeGroup; objectName:"mergedScope"; text:"Merged"; checked:evidenceScope==="Merged"; disclosure:false; help:"Merged: SDK (Software Development Kit) tree and XML of the complete table"; Accessible.name:"Merged table evidence"; onClicked:evidenceScope="Merged" }
                            SummaryChip { objectName:"scopeDetailsToggle"; text:"ⓘ"; checked:scopeOpen; help:"Decode scope details and native assembly cutoff"; Accessible.name:"Decode scope details, " + (scopeOpen ? "expanded" : "collapsed"); onClicked:scopeOpen=!scopeOpen }
                        }
                    }
                    SummaryChip {
                        id: inspectorWarningChip
                        objectName: "inspectorWarningToggle"
                        visible: !!detail.id && inspectorNotes.length>0
                        Layout.fillWidth: true
                        implicitHeight: 24
                        checked: warningsOpen
                        text: "⚠ " + inspectorNotes.length + (inspectorNotes.length===1 ? " note" : " notes") + (warningsOpen ? " ▾" : " ▸")
                        help: "Expand truncation and decoder notes"
                        onClicked: warningsOpen=!warningsOpen
                        contentItem: PlainLabel { text:inspectorWarningChip.text; color:warningColor; font.pixelSize:11; verticalAlignment:Text.AlignVCenter }
                    }
                    ScrollView {
                        id: inspectorDetailsScroll
                        objectName: "inspectorDetails"
                        visible: !!detail.id && (identityOpen || crcOpen || arrivalOpen && !!detail.distribution || sectionGroupOpen || scopeOpen || warningsOpen && inspectorNotes.length>0)
                        Layout.fillWidth: true
                        Layout.preferredHeight: Math.min(inspectorDetailsColumn.implicitHeight, Math.max(72,inspectorPane.height*0.28))
                        contentWidth: availableWidth
                        clip: true
                        ColumnLayout {
                            id: inspectorDetailsColumn
                            width: inspectorDetailsScroll.availableWidth
                            spacing: 4
                            PlainLabel {
                                id: identityDetails
                                objectName: "sectionIdentity"
                                visible: identityOpen
                                text: (detail.valid ? "VALID" : "INVALID") + " · PID " + hex(detail.pid) + " · TID " + hex(detail.table_id,2) + " · " + Shared.workbench.wireHeaderText(detail) + " · " + detail.bytes + " B" + (selectedService>=0 ? " · SID " + hex(selectedService) : "")
                                Layout.fillWidth: true
                                wrapMode: Text.Wrap
                                color: muted
                                font.pixelSize: 11
                            }
                            PlainLabel {
                                id: crcDetails
                                objectName: "sectionCrc"
                                text: crcText(detail) + ((detail.crc || {}).calculated_hex ? " · expected " + detail.crc.calculated_hex : "")
                                visible: crcOpen
                                Layout.fillWidth: true
                                wrapMode: Text.Wrap
                                color: detail.valid === false ? removedColor : muted
                                font.family: "monospace"
                                font.pixelSize: 11
                            }
                            PlainLabel {
                                id: arrivalDetails
                                objectName: "sectionArrivals"
                                text: arrivalText(detail)
                                visible: arrivalOpen && !!text
                                Layout.fillWidth: true
                                wrapMode: Text.Wrap
                                color: muted
                                font.pixelSize: 11
                            }
                            PlainLabel {
                                visible: arrivalOpen && !!detail.distribution
                                Layout.fillWidth: true
                                wrapMode: Text.Wrap
                                color: muted
                                font.pixelSize: 11
                                text: "Packet-position distribution; not wall-clock timing. " + ((detail.distribution || {}).basis || "") + "\nGap packets min / mean / max: " + detail.distribution?.min_gap_packets + " / " + detail.distribution?.mean_gap_packets + " / " + detail.distribution?.max_gap_packets + (detail.distribution?.first_seconds !== null && detail.distribution?.first_seconds !== undefined ? "\nSeconds from supplied bitrate: " + detail.distribution.first_seconds + " → " + detail.distribution.last_seconds : "\nSeconds unavailable without a bitrate. No PCR-derived clock.")
                            }
                            Row {
                                visible: !!detail.distribution && arrivalOpen
                                Layout.fillWidth: true
                                Layout.preferredHeight: 12
                                spacing: 1
                                Repeater {
                                    model: arrivalOpen ? (detail.distribution?.bins || []) : []
                                    Rectangle {
                                        required property var modelData
                                        width: Math.max(1, (inspectorDetailsColumn.width - 2) / Math.max(1, detail.distribution.bins.length) - 1)
                                        height: 12
                                        color: modelData.bad ? removedColor : tableColor(detail.name)
                                        opacity: modelData.count ? 0.35 + Math.min(0.65, modelData.count / Math.max(1, detail.distribution.observation_count) * 8) : 0.08
                                        HoverHandler { id:arrivalBinHover }
                                        SafeTip { visible:arrivalBinHover.hovered; text:"Packets " + modelData.from_packet + "–" + modelData.to_packet + ": " + modelData.count + " arrivals; " + modelData.bad + " invalid" }
                                    }
                                }
                            }
                            FieldChoice {
                                id: sectionChoice
                                objectName: "sectionChoice"
                                visible: sectionGroupOpen && !!selectedGroup.id
                                Layout.fillWidth: true
                                implicitHeight: 28
                                model: siblingSections.map(function(r) { return Shared.workbench.wireSectionText(r) + " · " + crcText(r) + " · #" + r.first_packet; })
                                currentIndex: siblingSections.findIndex(function(r) { return r.id === detail.id; })
                                onActivated: { let r=siblingSections[currentIndex]; if(r){if(topologyEvidenceRef)openTopologySibling(r);else inspect(r.id,-1,detail.native_table_at_packet);} }
                                Accessible.name: "Select original section evidence"
                            }
                            PlainLabel {
                                id: sectionGroupDetails
                                objectName: "sectionCoverage"
                                text: groupSummary() || Shared.workbench.wireHeaderText(detail) + " · No capture-wide group available at this cutoff."
                                visible: sectionGroupOpen
                                Layout.fillWidth: true
                                wrapMode: Text.Wrap
                                font.pixelSize: 11
                                color: selectedGroup.validity === "valid" ? muted : changedColor
                            }
                            Action { visible:sectionGroupOpen && !!selectedGroup.id; text:(showInvalidSections?"Hide":"Show")+" bad CRC sections"; implicitHeight:24; onClicked:showInvalidSections=!showInvalidSections }
                            PlainLabel {
                                id: cutoffDetails
                                objectName: "inspectionCutoff"
                                visible: scopeOpen && detail.native_table_at_packet !== undefined && detail.native_table_at_packet !== null
                                text: (detail.merged?.complete ? "Merged assembly" : "No complete merged assembly") + " · cutoff #" + num(detail.native_table_at_packet)
                                Layout.fillWidth: true
                                wrapMode: Text.Wrap
                                color: muted
                                font.pixelSize: 11
                            }
                            PlainLabel {
                                visible: scopeOpen
                                Layout.fillWidth: true
                                wrapMode: Text.Wrap
                                color: muted
                                font.pixelSize: 11
                                text: "Section: fields and bytes of this exact section. Merged: SDK tree and XML of the complete table.\n" + (detail.inspection_scope ? detail.inspection_scope.native_table : "Native table assembly evidence cutoff") + "\nTSDuck: " + (detail.native_decode_status || "not available") + "\nFirst evidence packet: " + num(detail.first_packet)
                            }
                            PlainLabel {
                                id: nativeDecodeWarningLabel
                                objectName: "nativeDecodeWarnings"
                                text: nativeWarningsText()
                                visible: !!text && warningsOpen
                                Layout.fillWidth: true
                                wrapMode: Text.Wrap
                                color: warningColor
                                font.pixelSize: 11
                            }
                        }
                    }
                    Flow {
                        Layout.fillWidth: true
                        Layout.preferredHeight: implicitHeight
                        spacing: 0
                        Repeater {
                            id: evidenceViews
                            model: ["Structure", "Hex", "XML", "Decoded", "Metadata", "References"]
                            NavItem {
                                required property string modelData
                                objectName: "inspector_" + modelData
                                leftPadding: 6
                                rightPadding: 6
                                text: modelData === "XML" && detail.native_xml_guarded ? "Guarded XML" : modelData
                                highlighted: inspectorView === modelData
                                onClicked: inspectorView = modelData
                            }
                        }
                    }
                    RowLayout {
                        visible: inspectorView === "Structure"
                        Layout.fillWidth: true
                        spacing: 4
                        FieldInput {
                            id: treeSearch
                            objectName: "treeSearch"
                            Layout.fillWidth: true
                            implicitHeight: 30
                            placeholderText: "Find field… Ctrl+Shift+K"
                            placeholderTextColor: muted
                            selectByMouse: true
                            Accessible.name: "Search inspector fields and values with ancestor context"
                            Keys.onEscapePressed: clear()
                            onAccepted: { tree.forceActiveFocus(); if (treeRows.length) tree.currentIndex=0; }
                        }
                        Action { objectName: "expandAllSections"; text: "+"; Accessible.name: "Expand all fields"; onClicked: foldAll(false); SafeTip { visible: anchorHovered; text: "Expand all fields" } }
                        Action { objectName: "collapseAllSections"; text: "−"; Accessible.name: "Collapse all fields"; onClicked: foldAll(true); SafeTip { visible: anchorHovered; text: "Collapse all fields" } }
                    }
                    PlainLabel {
                        visible: inspectorView === "Structure" && !!treeSearch.text.trim()
                        text: treeRows.length ? "Matching fields with ancestor context · clear to restore collapsed groups" : "No fields or values match this search."
                        Layout.fillWidth: true
                        wrapMode: Text.Wrap
                        color: muted
                        font.pixelSize: 11
                    }
                    PlainLabel {
                        visible: inspectorView === "Structure" && !compactInspector
                        Layout.fillWidth: true
                        text: (evidenceScope === "Merged" ? "Merged native + selected raw" : "Selected section") + " · ↑ ↓ / ← → · Home / End"
                        color: muted
                        font.pixelSize: 11
                        wrapMode: Text.Wrap
                    }
                    ListView {
                        id: tree
                        cacheBuffer: 0
                        objectName: "fieldTree"
                        Accessible.role: Accessible.List
                        Accessible.name: "Decoded PSI / SI fields"
                        Accessible.description: "Hierarchical fields. Use arrow keys to navigate and expand, Home and End to jump. Control Enter follows a reference; Alt Left returns. Search with Control Shift K."
                        onCountChanged: {
                            if (count && (currentIndex < 0 || currentIndex >= count)) currentIndex = 0;
                        }
                        visible: inspectorView === "Structure"
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        clip: true
                        model: treeRows
                        reuseItems: true
                        activeFocusOnTab: true
                        keyNavigationEnabled: true
                        ScrollBar.vertical: ScrollBar {}
                        Keys.onRightPressed: function(event) {
                            if(event.modifiers & Qt.AltModifier){event.accepted=false;return;}
                            let r = treeRows[currentIndex];
                            if (r && r.branch) {
                                if (r.closed) win.toggle(r.path);
                                else if (currentIndex + 1 < treeRows.length && treeRows[currentIndex + 1].depth > r.depth)
                                    currentIndex++;
                            }
                        }
                        Keys.onPressed: function(event) {
                            if (event.key === Qt.Key_Home || event.key === Qt.Key_End) {
                                if (count) currentIndex = event.key === Qt.Key_Home ? 0 : count - 1;
                                event.accepted = true;
                            }
                        }
                        Keys.onLeftPressed: function(event) {
                            if(event.modifiers & Qt.AltModifier){event.accepted=false;return;}
                            let r = treeRows[currentIndex];
                            if (r && r.branch && !r.closed && !treeSearch.text.trim())
                                win.toggle(r.path);
                            else if (r) {
                                for (let i = currentIndex - 1; i >= 0; --i)
                                    if (treeRows[i].depth < r.depth) {
                                        currentIndex = i;
                                        break;
                                    }
                            }
                        }
                        Keys.onReturnPressed: function(event) {
                            let r = treeRows[currentIndex];
                            if(event.modifiers & Qt.ControlModifier){jumpReference(r);event.accepted=true;return;}
                            if (r && r.branch)
                                win.toggle(r.path);
                        }
                        delegate: NavItem {
                            required property var modelData
                            required property int index
                            property alias rowTooltip: treeTooltip
                            objectName: "tree:" + modelData.path
                            highlighted: tree.currentIndex === index || !!activeInspectionRef && modelData.path === (activeInspectionResolution.path || "").replace(/^section\//,"")
                            keyboardCurrent: tree.currentIndex === index && tree.activeFocus
                            Accessible.role: Accessible.ListItem
                            Accessible.name: modelData.label + (modelData.value ? ": " + modelData.value : "")
                            Accessible.description: "Level " + (modelData.depth + 1) + (modelData.branch ? (modelData.closed ? ", collapsed" : ", expanded") : "")
                            Accessible.focusable: true
                            Accessible.focused: keyboardCurrent
                            Accessible.onPressAction: clicked()
                            width: ListView.view.width
                            height: treeRowHeight
                            leftPadding: spaceUnit + modelData.depth * 16
                            focusPolicy: Qt.NoFocus
                            contentItem: RowLayout {
                                spacing: 5
                                PlainLabel {
                                    text: modelData.branch ? (modelData.closed ? "▸" : "▾") : "·"
                                    objectName: "treeGlyph:" + modelData.path
                                    color: muted
                                    Layout.preferredWidth: 10
                                }
                                PlainLabel {
                                    text: modelData.label
                                    objectName: "treeLabel:" + modelData.path
                                    color: modelData.branch ? (lightTheme ? "#147358" : "#4ec9b0") : ink
                                    font.pixelSize: fieldFontSize
                                    elide: Text.ElideMiddle
                                    Layout.fillWidth: true
                                }
                                PlainLabel {
                                    text: modelData.value
                                    objectName: "treeValue:" + modelData.path
                                    color: modelData.kind === "number" ? addedColor : modelData.kind === "string" ? (lightTheme ? "#955021" : "#d6a089") : muted
                                    font.family: "monospace"
                                    font.pixelSize: fieldFontSize
                                    elide: Text.ElideRight
                                    Layout.maximumWidth: Math.max(90, tree.width * 0.48)
                                }
                                Loader {
                                    // A nonexistent reference must not allocate a
                                    // hidden button, background, label and tooltip.
                                    active: !!modelData.reference
                                    visible: active
                                    asynchronous: false
                                    Layout.preferredWidth: 22
                                    Layout.preferredHeight: 24
                                    sourceComponent: Action {
                                    id: referenceJump
                                    objectName: "reference:" + modelData.path
                                    visible: !!modelData.reference
                                    enabled: backendReady && !core.inspecting
                                    anchors.fill: parent
                                    leftPadding: 0; rightPadding: 0
                                    activeFocusOnTab: tree.currentIndex===index
                                    text: "→"
                                    Accessible.name: modelData.reference ? modelData.reference.label : "Reference unavailable"
                                    Accessible.description: modelData.reference ? modelData.reference.help + " · Ctrl+Enter; Alt+Left returns" : ""
                                    onActiveFocusChanged: if(activeFocus)tree.currentIndex=index
                                    onClicked: jumpReference(modelData)
                                    Keys.onReturnPressed: clicked()
                                    Keys.onEnterPressed: clicked()
                                    contentItem: PlainLabel {text:referenceJump.text;color:referenceJump.hovered || referenceJump.activeFocus ? blue : muted;horizontalAlignment:Text.AlignHCenter;verticalAlignment:Text.AlignVCenter}
                                    background: Rectangle {color:"transparent";radius:2;border.color:referenceJump.activeFocus ? blue : "transparent";border.width:referenceJump.activeFocus ? focusWidth : 0}
                                    SafeTip {visible:anchorHovered;text:modelData.reference ? modelData.reference.label + " · " + modelData.reference.help + " · Ctrl+Enter" : ""}
                                }
                                }
                            }
                            onClicked: {
                                tree.currentIndex = index;
                                tree.forceActiveFocus();
                                if (modelData.branch)
                                    win.toggle(modelData.path);
                            }
                            SafeTip {
                                id: treeTooltip
                                visible: anchorHovered
                                text: modelData.label + (modelData.value ? ": " + modelData.value : "")
                            }
                        }
                    }
                    TinyLabel {
                        text: "SELECTED SECTION HEX · BYTE OFFSET"
                        visible: inspectorView === "Hex"
                    }
                    ScrollView {
                        visible: inspectorView === "Hex"
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        clip: true
                        TextArea {
                            id: hexEvidence
                            persistentSelection: true
                            textFormat: TextEdit.PlainText
                            readOnly: true
                            selectByMouse: true
                            wrapMode: TextEdit.NoWrap
                            font.family: "monospace"
                            font.pixelSize: 11
                            color: muted
                            text: {
                                let raw = (detail.raw_hex || "").replace(/\s/g, "");
                                let lines = [];
                                // Fixed 72-character lines (offset, 16 bytes, ASCII) keep
                                // highlightTopologyHex() character positions exact.
                                for (let i = 0; i < raw.length; i += 32) {
                                    let bytes = raw.slice(i, i + 32).match(/.{1,2}/g) || [];
                                    let ascii = bytes.map(function(b) { let c = parseInt(b, 16); return c >= 32 && c < 127 ? String.fromCharCode(c) : "."; }).join("");
                                    lines.push((i / 2).toString(16).toUpperCase().padStart(4, "0") + "  " + bytes.join(" ").padEnd(47, " ") + "  " + ascii);
                                }
                                return lines.join("\n");
                            }
                        }
                    }
                    ScrollView {
                        visible: inspectorView === "XML"
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        clip: true
                        TextArea {
                            id: xmlEvidence
                            textFormat: TextEdit.PlainText
                            text: inspectorView !== "XML" ? "" : (evidenceScope === "Section" ? detail.section_tsduck_xml : detail.merged?.tsduck_xml) || "No standalone native XML is available for this section. Exact section fields and bytes remain in Structure and Hex."
                            Component.onCompleted: core.highlightXml(textDocument, lightTheme)
                            readOnly: true
                            selectByMouse: true
                            wrapMode: TextEdit.NoWrap
                            font.family: "monospace"
                            font.pixelSize: 11
                        }
                    }
                    ScrollView {
                        id: metadataScroll
                        visible: inspectorView === "Metadata"
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        clip: true
                        contentWidth: availableWidth
                        ColumnLayout {
                            id: metadataContent
                            width: metadataScroll.availableWidth
                            spacing: 8
                            PlainLabel { text: "Section metadata"; Layout.fillWidth: true; font.bold: true; font.pixelSize: 13; color: ink }
                            PlainLabel {
                                text: "Changes with the selected section. Reference labels do not verify current ownership."
                                Layout.fillWidth: true
                                wrapMode: Text.Wrap
                                color: muted
                            }
                            RowLayout {
                                visible: protocolCardModel.total > 0
                                Layout.fillWidth: true
                                Action { objectName: "protocolPrevious"; text: "Previous cards"; enabled: protocolCardModel.has_previous; onClicked: {protocolCardOffset=Math.max(0,protocolCardModel.offset-20);forceActiveFocus();} }
                                PlainLabel { objectName: "protocolCardCount"; text: (protocolCardModel.offset+1)+"–"+Math.min(protocolCardModel.offset+20,protocolCardModel.total)+" / "+protocolCardModel.total; Layout.fillWidth: true; wrapMode: Text.Wrap; color: muted }
                                Action { objectName: "protocolNext"; text: "Next cards"; enabled: protocolCardModel.has_more; onClicked: {protocolCardOffset=protocolCardModel.offset+20;forceActiveFocus();} }
                            }
                            Repeater {
                                id: protocolCardRepeater
                                model: inspectorView === "Metadata" ? protocolCardModel.cards : []
                                ColumnLayout {
                                    id: protocolCard
                                    required property int index
                                    property alias sourceControls: protocolSourceRepeater
                                    required property var modelData
                                    Layout.fillWidth: true
                                    spacing: 4
                                    PlainLabel { text: modelData.title; Layout.fillWidth: true; wrapMode: Text.Wrap; font.bold: true; color: blue }
                                    TextArea { text: modelData.text; Layout.fillWidth: true; readOnly: true; selectByMouse: true; textFormat: TextEdit.PlainText; wrapMode: TextEdit.WrapAnywhere }
                                    Repeater {
                                        id: protocolSourceRepeater
                                        model:Shared.workbench.protocolCardSources(modelData)
                                        Action {required property var modelData;required property int index;objectName:"protocolSource_"+protocolCard.index+"_"+index;Layout.fillWidth:true;text:"Open source · "+modelData.label;enabled:modelData.available && backendReady && !core.inspecting;Accessible.name:text;onClicked:openProtocolSource(modelData,true,protocolCard.index,index);SafeTip {visible:anchorHovered;text:modelData.available?"Exact source context. Locator precision: "+modelData.precision:"Source identity, revision or cutoff is unavailable."}}
                                    }
                                    Action { id: protocolEvidenceToggle; text: checked ? "Hide original values and source" : "Original values and source"; checkable: true; Layout.fillWidth: true }
                                    TextArea { visible: protocolEvidenceToggle.checked; text: protocolEvidenceToggle.checked ? JSON.stringify(modelData.evidence,null,2) : ""; Layout.fillWidth: true; readOnly: true; selectByMouse: true; textFormat: TextEdit.PlainText; wrapMode: TextEdit.WrapAnywhere }
                                }
                            }
                            PlainLabel { text: "Multilingual EPG"; Layout.fillWidth: true; font.bold: true; color: ink }
                            FieldChoice {
                                id: epgLanguageChoice
                                objectName: "epgLanguage"
                                Layout.fillWidth: true
                                implicitHeight: 30
                                model: ["Default"].concat((detail.events || []).reduce(function(all,e) { (e.language_variants || []).forEach(function(v) {if(all.indexOf(v.language_code)<0)all.push(v.language_code);});return all;}, []).sort())
                                currentIndex: Math.max(0, model.indexOf(epgLanguage || "Default"))
                                onActivated: epgLanguage=currentIndex === 0 ? "" : currentText
                                Accessible.name: "Preferred EPG language"
                                onActiveFocusChanged: if(activeFocus)Qt.callLater(function(){revealMetadataControl(epgLanguageChoice);})
                                SafeTip { visible: anchorHovered; text: "Preferred Electronic Programme Guide language; unavailable languages explicitly fall back." }
                            }
                            PlainLabel { text: detail.text_diagnostic_scope || "Analyze a stream to inspect metadata."; Layout.fillWidth: true; wrapMode: Text.Wrap; color: muted }
                            Repeater {
                                model: inspectorView === "Metadata" ? metadataEntries() : []
                                ColumnLayout {
                                    required property var modelData
                                    Layout.fillWidth: true
                                    spacing: 4
                                    PlainLabel { text: modelData.title; Layout.fillWidth: true; wrapMode: Text.Wrap; font.bold: true; color: blue }
                                    TextArea { text: modelData.text; Layout.fillWidth: true; readOnly: true; selectByMouse: true; textFormat: TextEdit.PlainText; wrapMode: TextEdit.WrapAnywhere }
                                    Action { id: evidenceToggle; text: checked ? "Hide original values and source" : "Original values and source"; checkable: true; Layout.fillWidth: true }
                                    TextArea { visible: evidenceToggle.checked; text: evidenceToggle.checked ? modelData.evidence : ""; Layout.fillWidth: true; readOnly: true; selectByMouse: true; textFormat: TextEdit.PlainText; wrapMode: TextEdit.WrapAnywhere }
                                }
                            }
                            Rectangle { Layout.fillWidth: true; Layout.topMargin: 12; Layout.bottomMargin: 8; implicitHeight: 1; color: dividerColor }
                            PlainLabel { text: "Lookup"; Layout.fillWidth: true; font.bold: true; font.pixelSize: 13; color: ink }
                            PlainLabel { text: "Not tied to the selected section"; Layout.fillWidth: true; color: muted }
                            PlainLabel { text: "Identifier lookup"; Layout.fillWidth: true; font.bold: true; color: ink }
                            FieldChoice {
                                id: identifierKind
                                objectName: "identifierKind"
                                Layout.fillWidth: true
                                implicitHeight: 30
                                model: Shared.workbench.identifierNamespaces
                                textRole: "label"
                                valueRole: "value"
                                Accessible.name: "Identifier namespace"
                                onActiveFocusChanged: if(activeFocus)Qt.callLater(function(){revealMetadataControl(identifierKind);})
                                SafeTip { visible: anchorHovered; text: (Shared.workbench.identifierNamespaces[identifierKind.currentIndex] || {}).help + " · " + identifierKind.currentValue }
                            }
                            RowLayout {
                                Layout.fillWidth: true
                                FieldInput { id: identifierValue; objectName: "identifierValue"; Layout.fillWidth: true; placeholderText: "ID: decimal or 0x hexadecimal"; Accessible.name: "Identifier value"; onActiveFocusChanged: if(activeFocus)Qt.callLater(function(){revealMetadataControl(identifierValue);}) }
                                Action {
                                    id: identifierQuery
                                    objectName: "identifierQuery"
                                    text: "Look up"
                                    Accessible.name: "Look up identifier"
                                    onActiveFocusChanged: if(activeFocus)Qt.callLater(function(){revealMetadataControl(identifierQuery);})
                                    enabled: backendReady
                                    onClicked: {
                                        let value=identifierValue.text.trim();
                                        identifierResult={};identifierEvidence.checked=false;
                                        if(!/^(?:0x[0-9a-f]+|[0-9]+)$/i.test(value) || !Number.isSafeInteger(Number(value))) {identifierResult={error:"Enter a whole decimal or hexadecimal ID"};return;}
                                        core.send("lookup_identifier",{namespace:identifierKind.currentValue,value:Number(value),standards:analysisState.standards_context || "auto"});
                                    }
                                }
                            }
                            PlainLabel { text: "Uses the analyzed standard context; choose an explicit standard and rescan if context is required."; Layout.fillWidth: true; wrapMode: Text.Wrap; color: muted }
                            LookupTable { objectName: "identifierResult"; result: identifierResult; label: "Identifier lookup result" }
                            Action {
                                id: identifierEvidence
                                visible: Object.keys(identifierResult).length > 0
                                text: "Raw"
                                checkable: true
                                Layout.fillWidth: true
                                Accessible.name: "Raw identifier lookup JSON, " + (checked ? "expanded" : "collapsed")
                                onActiveFocusChanged: if(activeFocus)Qt.callLater(function(){revealMetadataControl(identifierEvidence);})
                                SafeTip { visible: anchorHovered; text: "Original JavaScript Object Notation (JSON), including all values and source evidence." }
                            }
                            TextArea {
                                id: identifierRawText
                                visible: identifierEvidence.checked && Object.keys(identifierResult).length > 0
                                Layout.fillWidth: true
                                readOnly: true
                                selectByMouse: true
                                textFormat: TextEdit.PlainText
                                wrapMode: TextEdit.WrapAnywhere
                                text: JSON.stringify(identifierResult,null,2)
                                font.family: "monospace"
                                activeFocusOnTab: true
                                Accessible.name: "Original identifier lookup JSON"
                                onActiveFocusChanged: if(activeFocus)Qt.callLater(function(){revealMetadataControl(identifierRawText);})
                            }
                            PlainLabel { text: "Satellite lookup"; Layout.fillWidth: true; wrapMode: Text.Wrap; font.bold: true; color: ink }
                            PlainLabel { text: "Nominal GEO slot only. An incomplete reference snapshot; never a confirmed satellite."; Layout.fillWidth: true; wrapMode: Text.Wrap; color: muted }
                            RowLayout {
                                Layout.fillWidth: true
                                FieldInput { id: satellitePosition; objectName: "satellitePosition"; Layout.fillWidth: true; placeholderText: "Degrees: 13.0"; Accessible.name: "Orbital position in degrees"; onActiveFocusChanged: if(activeFocus)Qt.callLater(function(){revealMetadataControl(satellitePosition);}) }
                                FieldChoice { id: satelliteDirection; objectName: "satelliteDirection"; model: ["E","W"]; implicitWidth: 65; Accessible.name: "Orbital direction"; onActiveFocusChanged: if(activeFocus)Qt.callLater(function(){revealMetadataControl(satelliteDirection);}); SafeTip { visible: anchorHovered; text: "East or west of the prime meridian · nominal geostationary Earth orbit (GEO) slot" } }
                                Action {
                                    id: satelliteQuery
                                    objectName: "satelliteQuery"
                                    text: "Candidates"
                                    Accessible.name: "Look up satellite candidates"
                                    onActiveFocusChanged: if(activeFocus)Qt.callLater(function(){revealMetadataControl(satelliteQuery);})
                                    enabled: backendReady
                                    onClicked: {
                                        let value=satellitePosition.text.trim();
                                        satelliteResult={};satelliteEvidence.checked=false;
                                        if(!/^(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)$/.test(value) || Number(value)>180) {satelliteResult={error:"Enter degrees from 0 to 180"};return;}
                                        core.send("lookup_satellite",{orbital_position_degrees:Number(value),direction:satelliteDirection.currentText});
                                    }
                                }
                            }
                            LookupTable { objectName: "satelliteResult"; result: satelliteResult; label: "Satellite lookup result" }
                            Action { id: satelliteEvidence; visible: Object.keys(satelliteResult).length > 0; text: "Raw"; checkable: true; Layout.fillWidth: true; Accessible.name: "Raw satellite lookup JSON, " + (checked ? "expanded" : "collapsed"); onActiveFocusChanged: if(activeFocus)Qt.callLater(function(){revealMetadataControl(satelliteEvidence);}); SafeTip { visible: anchorHovered; text: "Original JavaScript Object Notation (JSON), including all values and source evidence." } }
                            TextArea { id: satelliteRawText; visible: satelliteEvidence.checked && Object.keys(satelliteResult).length > 0; text: JSON.stringify(satelliteResult,null,2); Layout.fillWidth: true; readOnly: true; selectByMouse: true; activeFocusOnTab: true; textFormat: TextEdit.PlainText; wrapMode: TextEdit.WrapAnywhere; font.family: "monospace"; Accessible.name: "Original satellite lookup JSON"; onActiveFocusChanged: if(activeFocus)Qt.callLater(function(){revealMetadataControl(satelliteRawText);}) }
                        }
                    }
                    ListView {
                        id: inspectorReferences
                        visible: inspectorView === "References"
                        Layout.fillWidth:true; Layout.fillHeight:true; clip:true
                        property string currentIdentity: win.protocolCardKey
                        property string loadedIdentity: ""
                        onVisibleChanged: if(visible)loadedIdentity=currentIdentity
                        onCurrentIdentityChanged: if(visible)loadedIdentity=currentIdentity
                        // Expose only the latched evidence identity. Visibility must not
                        // bypass activation or reassign the model on same-detail tab changes.
                        model:loadedIdentity===currentIdentity ? specificationLinks : []; spacing:12; ScrollBar.vertical:ScrollBar {}
                        delegate:Column {
                            Component.onCompleted: if(referencePersistenceTest.running)referencePersistenceTest.delegateCreates++
                            Component.onDestruction: if(referencePersistenceTest && referencePersistenceTest.running)referencePersistenceTest.delegateDestroys++
                            required property var modelData
                            property alias urlField: referenceUrl
                            width:ListView.view.width; spacing:6
                            PlainLabel { text:modelData.title || modelData.id; color:ink; width:parent.width; wrapMode:Text.Wrap; font.bold:true }
                            PlainLabel { text:[modelData.version,modelData.scope,modelData.access,modelData.notes].filter(Boolean).join(" · "); color:muted; width:parent.width; wrapMode:Text.Wrap }
                            TextArea { id:referenceUrl; text:modelData.url; width:parent.width; readOnly:true; selectByMouse:true; wrapMode:TextEdit.WrapAnywhere; textFormat:TextEdit.PlainText }
                            Row {
                                Action { text:"Open official source"; onClicked:if(!Qt.openUrlExternally(modelData.url)) notice="The official source could not be opened by the system browser." }
                                Action { text:"Copy URL"; onClicked:{referenceUrl.selectAll();referenceUrl.copy();} }
                            }
                        }
                        PlainLabel { visible:specificationLinks.length===0; text:"No verified specification link"; color:muted }
                    }
                    ScrollView {
                        visible: inspectorView === "Decoded"
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        clip: true
                        TextArea {
                            objectName: "sectionNativeText"
                            textFormat: TextEdit.PlainText
                            text: inspectorView !== "Decoded" ? "" : detail.section_native_text || "Native section display unavailable. Raw bytes remain in Hex."
                            readOnly: true
                            selectByMouse: true
                            wrapMode: TextEdit.NoWrap
                            font.family: "monospace"
                            font.pixelSize: 11
                        }
                    }
                    PlainLabel {
                        text: detail.first_packet !== undefined ? "Evidence · packet " + num(detail.first_packet) + " · offsets refer to raw section bytes" : ""
                        visible: !compactInspector
                        color: muted
                        font.pixelSize: 11
                        Layout.fillWidth: true
                        elide: Text.ElideRight
                    }
                    GridLayout {
                        Layout.fillWidth: true
                        columns: 2
                        columnSpacing: spaceUnit * 2
                        rowSpacing: spaceUnit
                        Action {
                            objectName: "specifications"
                            text: specificationLinks.length ? "Official specifications… (" + specificationLinks.length + ")" : "No verified specification link"
                            Layout.fillWidth: true
                            enabled: specificationLinks.length > 0
                            onClicked: specificationDialog.open()
                        }
                        Action {
                            id: renameButton
                            objectName: "rename"
                            visible: !selectedChange
                            text: "Rename service…"
                            Layout.fillWidth: true
                            enabled: backendReady && !editBlockReason() && !selectedChange && !!analysisState.complete && !core.inspecting && detail.name === "SDT" && detail.valid && !!chosenService()
                            onClicked: {
                                preview = {};
                                editService.currentIndex = Math.max(0, (detail.services || []).findIndex(function(service) {return service.id === selectedService;}));
                                renameName.text = ((detail.services || [])[editService.currentIndex] || {}).name || "";
                                renameDialog.open();
                            }
                        }
                    }
                    PlainLabel {
                        objectName: "renameBlockedReason"
                        visible: !selectedChange && !!detail.name && text !== ""
                        text: editBlockReason()
                        color: muted
                        font.pixelSize: 11
                        Layout.fillWidth: true
                        wrapMode: Text.Wrap
                    }
                }
            }
        }
        Card {
            id: timelinePane
            SplitView.preferredHeight: savedLayout.timeline
            SplitView.minimumHeight: 105
            SplitView.maximumHeight: 350
            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 6
                spacing: 2
                RowLayout {
                    Layout.fillWidth: true
                    TinyLabel {
                        objectName: "timelineAxisLabel"
                        text: "ALL ARRIVALS · " + (analysisState.timing?.seconds_per_packet > 0 ? "SECONDS · SUPPLIED BITRATE" : "Axis: packet index")
                        Layout.fillWidth: true
                        HoverHandler { id: timelineAxisHover }
                        SafeTip { visible:timelineAxisHover.hovered; text:analysisState.timing?.seconds_per_packet > 0 ? "Estimated elapsed seconds from the supplied bitrate; not PCR time" : "No PCR/TDT clock is used; positions are packet indices." }
                    }
                    FieldChoice { objectName:"historyScope"; Layout.preferredWidth:180; Layout.minimumWidth:180; model:["Selected table history","All table history"]; currentIndex:allTableHistory?1:0; onActivated:allTableHistory=currentIndex===1; implicitHeight:24 }
                    PlainLabel { text:historyRows.length+" transitions"; color:muted; Layout.fillWidth:true; elide:Text.ElideRight }
                    Action { objectName:"loadMoreHistory"; text:"Load history"; visible:core.remainingPages.table_history !== undefined; enabled:backendReady; onClicked:core.loadMore("table_history") }
                    Action { objectName:"historyPrevious"; text:"Previous"; enabled:historyPage>0; onClicked:historyPage-- }
                    Action { objectName:"historyNext"; text:"Next"; enabled:(historyPage+1)*40<historyRows.length; onClicked:historyPage++ }
                    PlainLabel {
                        text: analysisState.selected_packet === null || analysisState.selected_packet === undefined ? "Latest observed state" : "Snapshot @ " + num(analysisState.selected_packet)
                        color: muted
                        font.pixelSize: 11
                    }
                    Action {
                        objectName: "compareSnapshots"
                        text: "Compare A / B"
                        implicitHeight: 24
                        enabled: backendReady && !!analysisState.complete
                        onClicked: openComparison()
                    }
                    Action {
                        objectName: "latest"
                        text: "Latest"
                        implicitHeight: 24
                        enabled: backendReady && !!analysisState.complete
                        onClicked: snapshot(-1)
                    }
                }
                Item {
                    id: densityStrip
                    Layout.fillWidth: true
                    Layout.leftMargin: 8
                    Layout.rightMargin: 8
                    height: 28
                    readonly property int binCount: (analysisState.density || []).length
                    readonly property real binWidth: Math.max(1, (width - Math.max(0, binCount - 1) * 2) / Math.max(1, binCount))
                    readonly property bool interactive: backendReady && !!analysisState.complete
                    // Keyboard parity with the Web slider: arrows step one bin,
                    // Page keys step a tenth, Home/End jump to the ends.
                    objectName: "densityStrip"
                    activeFocusOnTab: interactive
                    KeyNavigation.tab: comparisonMarkerA.visible && comparisonMarkerA.enabled ? comparisonMarkerA : comparisonMarkerB.visible && comparisonMarkerB.enabled ? comparisonMarkerB : null
                    Accessible.role: Accessible.Slider
                    Accessible.name: "Section occurrence density; arrow keys load a packet position"
                    function stepBin(delta) {
                        if (!interactive || !binCount) return;
                        let current = binForPacket(analysisState.selected_packet);
                        snapshot(packetAtBin(Math.max(0, Math.min(binCount - 1, current + delta))));
                    }
                    Keys.onLeftPressed: stepBin(-1)
                    Keys.onRightPressed: stepBin(1)
                    Keys.onPressed: function(event) {
                        if (event.key === Qt.Key_Home) { stepBin(-binCount); event.accepted = true; }
                        else if (event.key === Qt.Key_End) { stepBin(binCount); event.accepted = true; }
                        else if (event.key === Qt.Key_PageUp) { stepBin(-Math.max(1, Math.round(binCount / 10))); event.accepted = true; }
                        else if (event.key === Qt.Key_PageDown) { stepBin(Math.max(1, Math.round(binCount / 10))); event.accepted = true; }
                    }
                    Rectangle {
                        anchors.fill: parent
                        anchors.margins: -3
                        color: "transparent"
                        visible: densityStrip.activeFocus
                        border.color: blue
                        border.width: focusWidth
                        radius: 2
                    }
                    function packetAtBin(index) {
                        let packets = densitySourcePackets;
                        if (!packets) return 0;
                        return Math.max(0, Math.min(packets - 1, Math.round(index * (packets - 1) / Math.max(1, binCount - 1))));
                    }
                    function binForPacket(packet) {
                        let packets = densitySourcePackets;
                        if (!binCount) return -1;
                        if (packet === null || packet === undefined || packets <= 1) return binCount - 1;
                        return Math.max(0, Math.min(binCount - 1, Math.round(packet / (packets - 1) * (binCount - 1))));
                    }
                    function moveComparisonMarker(start, packet) {
                        if (!interactive || core.comparing) return;
                        let other = start ? toPacket.text : fromPacket.text;
                        let lower = !start && validPacket(other) ? Number(other) : 0;
                        let upper = start && validPacket(other) ? Number(other) : Number(analysisState.packets) - 1;
                        let input = start ? fromPacket : toPacket;
                        input.text = String(Math.max(lower, Math.min(upper, Math.round(packet))));
                    }
                    Row {
                        anchors.fill: parent
                        spacing: 2
                        Repeater {
                            // Reuse the bounded density visuals across state replacements.
                            // Hidden spare slots avoid rebuilding all 80 controls at scan completion.
                            model: Math.max(80,(analysisState.density || []).length)
                            Rectangle {
                                readonly property var binData: (analysisState.density || [])[index] || ({count:0,bad:0})
                                visible: index < (analysisState.density || []).length
                                required property int index
                                objectName: "densityBin" + index
                                width: densityStrip.binWidth
                                height: densityStrip.height
                                readonly property bool unscanned: !packetCovered(densityStrip.packetAtBin(index))
                                color: unscanned ? dividerColor : binData.bad && binData.count && binData.bad >= binData.count ? removedColor : blue
                                opacity: unscanned ? 0.8 : binData.count ? 0.35 + Math.min(0.65, binData.count / 50) : 0.12
                                // Partially invalid bins keep the section colour and
                                // add the invalid share instead of hiding the count.
                                Rectangle {
                                    visible: binData.bad > 0 && !(binData.count && binData.bad >= binData.count)
                                    anchors.left: parent.left
                                    anchors.right: parent.right
                                    anchors.bottom: parent.bottom
                                    // A single invalid section in a dense bin is
                                    // unreadable as a true proportion, so the
                                    // share keeps a visible minimum height.
                                    height: Math.max(3, parent.height * Math.min(1, binData.bad / Math.max(1, binData.count)))
                                    color: removedColor
                                    opacity: 0.95
                                }
                                SafeTip {
                                    visible: binHover.hovered
                                    text: unscanned ? "Unscanned interval · unknown, not zero reception" : "Bin " + (index + 1) + " · " + binData.count + " sections / " + binData.bad + " invalid" + (densityStrip.interactive ? " · click to load this position" : "")
                                }
                                HoverHandler {
                                    id: binHover
                                }
                                TapHandler {
                                    enabled: densityStrip.interactive
                                    onTapped: snapshot(densityStrip.packetAtBin(index))
                                }
                            }
                        }
                    }
                    Rectangle {
                        id: densityCursor
                        visible: densityStrip.binCount > 0 && analysisState.selected_packet !== null && analysisState.selected_packet !== undefined
                        width: 2
                        height: parent.height
                        color: ink
                        border.color: surface
                        x: {
                            let index = densityStrip.binForPacket(analysisState.selected_packet);
                            if (index < 0) return 0;
                            return Math.max(0, index * (densityStrip.binWidth + 2) + densityStrip.binWidth / 2 - 1);
                        }
                    }
                    ComparisonMarker { id: comparisonMarkerA; startMarker: true; KeyNavigation.tab: comparisonMarkerB.visible && comparisonMarkerB.enabled ? comparisonMarkerB : null; KeyNavigation.backtab: densityStrip }
                    ComparisonMarker { id: comparisonMarkerB; startMarker: false; KeyNavigation.backtab: comparisonMarkerA.visible && comparisonMarkerA.enabled ? comparisonMarkerA : densityStrip }
                }
                RowLayout {
                    objectName: "arrivalAxis"
                    Layout.fillWidth: true
                    Repeater {
                        model: [0,0.25,0.5,0.75,1]
                        PlainLabel {
                            required property real modelData
                            Layout.fillWidth: true
                            horizontalAlignment: modelData === 0 ? Text.AlignLeft : modelData === 1 ? Text.AlignRight : Text.AlignHCenter
                            text: axisLabel(Math.round(Math.max(0, densitySourcePackets-1) * modelData))
                            color: muted; font.family:"monospace"; font.pixelSize:10
                        }
                    }
                }
                ScrollView {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    clip: true
                    ScrollBar.vertical.policy: ScrollBar.AlwaysOff
                    Row {
                        spacing: 6
                        Repeater {
                            model: historyRows.slice(historyPage*40,(historyPage+1)*40)
                            Action {
                                required property var modelData
                                objectName: "table_history_" + modelData.event_id
                                text: Shared.workbench.historyText(modelData)
                                implicitHeight: 24
                                enabled: backendReady
                                onClicked: activateHistory(modelData)
                            }
                        }
                    }
                }
            }
        }
        }
        Rectangle {
            id: statusFooter
            visible:metadataMode || advancedMode || classicStatusVisible
            readonly property bool errorStatus: metadataMode ? !!dvbiWorkspace.error : messageLevel === "error"
            Layout.fillWidth: true
            height: 28
            color: errorStatus ? errorSurface : surface
            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 10
                anchors.rightMargin: 10
                PlainLabel {
                    objectName: "statusMessage"
                    text: metadataMode ? (dvbiWorkspace.error || (dvbiWorkspace.busy ? "Loading local document…" : dvbiWorkspace.hasDocument ? "Local document imported · original file unchanged" : "Choose a local XML document")) : notice || (core.availability === "starting" ? "Starting backend…" : "Ready · all processing stays on this machine")
                    color: statusFooter.errorStatus ? errorInk : !metadataMode && messageLevel === "warning" ? warningColor : muted
                    opacity: !metadataMode && advancedMode && messageLevel === "info" && messageExpired ? 0 : 1
                    Accessible.ignored: !metadataMode && advancedMode && messageLevel === "info" && messageExpired
                    font.pixelSize: 11
                    Layout.fillWidth: true
                    elide: Text.ElideMiddle
                    SafeTip {
                        id: statusTooltip
                        visible: statusHover.hovered
                        text: anchorText
                    }
                    HoverHandler {
                        id: statusHover
                    }
                }
                RowLayout {
                    visible: !metadataMode && !!warningMessage
                    Layout.maximumWidth: win.width * 0.4
                    PlainLabel {
                        Layout.fillWidth: true
                        text: "⚠ " + (notice === warningMessage ? "" : warningMessage + " ") + "×" + warningRepeat
                        color: warningColor
                        font.pixelSize: 11
                        elide: Text.ElideRight
                        Accessible.name: "Warning: " + warningMessage + " · " + warningRepeat + " occurrences"
                        SafeTip { visible: warningHover.hovered; text: win.warningMessage + " · " + warningRepeat + " occurrences" }
                        HoverHandler { id: warningHover }
                    }
                    Action {
                        objectName: "dismissWarning"
                        text: "Dismiss"
                        implicitHeight: 22
                        Accessible.name: "Dismiss warning message"
                        onClicked: {if(notice===warningMessage){messageLevel="info";messageExpired=true;}warningMessage="";warningRepeat=0;messagesButton.forceActiveFocus();}
                    }
                }
                PlainLabel {
                    visible:metadataMode || advancedMode
                    text: metadataMode ? "Independent document · C++ / Expat" : num(analysisState.packets) + " packets · C++ / TSDuck"
                    color: statusFooter.errorStatus ? errorInk : muted
                    font.pixelSize: 11
                }
                Repeater {
                    model:!metadataMode&&!advancedMode?["ShowPsiSi",Qt.application.version,classicLocks.num?"NUM":"",classicLocks.scroll?"SCRL":""]:[]
                    delegate:Rectangle {
                        required property var modelData
                        implicitWidth:Math.max(38,classicStatusText.implicitWidth+14);implicitHeight:22;color:'#efefef';border.color:'#a0a0a0'
                        Text {id:classicStatusText;anchors.centerIn:parent;text:String(modelData);font.family:'Tahoma';font.pixelSize:11;color:'#000'}
                    }
                }
                Action {
                    id: messagesButton
                    objectName: "messagesButton"
                    visible: !metadataMode && advancedMode
                    text: "Messages"
                    implicitHeight: 22
                    Accessible.name: "Messages · " + messagesModel.count + " recent messages"
                    onClicked: messagesDialog.open()
                }
            }
        }
    }
    DropArea {
        objectName: "sourceDropArea"
        anchors.fill: parent
        z: 10
        enabled: backendReady && !exporting && !saveDialog.visible && !renameDialog.visible && !apiDialog.visible && !specificationDialog.visible && !messagesDialog.visible && !shortcutDialog.visible && !updateDialog.visible
        onEntered: function(drag) {drag.accepted=drag.hasUrls && drag.urls.length===1 && !!core.localPath(drag.urls[0]);if(drag.accepted)drag.action=Qt.CopyAction;}
        onDropped: function(drop) {
            let path=drop.hasUrls && drop.urls.length===1 ? core.localPath(drop.urls[0]) : "";
            if(!path){drop.accepted=false;return;}
            chooseSource(path);drop.accept(Qt.CopyAction);
        }
    }
    Dialog {
        id: shortcutDialog
        objectName: "shortcutHelp"
        title: "Keyboard shortcuts"
        anchors.centerIn: parent
        width: Math.min(640,win.width-80)
        height: Math.min(540,win.height-100)
        modal: true
        focus: true
        closePolicy: Popup.CloseOnEscape
        background: Rectangle {color:panel;border.color:dividerColor;radius:4}
        onOpened: closeShortcutHelp.forceActiveFocus()
        onClosed: {
            let item=shortcutReturnFocus;shortcutReturnFocus=null;
            if(shortcutReturnRecent>=0){let index=shortcutReturnRecent;shortcutReturnRecent=-1;recentMenu.open();recentMenu.currentIndex=index;let entry=recentMenu.itemAt(index);if(entry)entry.forceActiveFocus();}
            else if(item && item.visible && item.enabled)item.forceActiveFocus();
            else if(analyzeButton.visible && analyzeButton.enabled)analyzeButton.forceActiveFocus();
            else messagesButton.forceActiveFocus();
        }
        contentItem: ScrollView {
            id: shortcutScroll
            clip: true
            contentWidth: availableWidth
            ColumnLayout {
                width: shortcutScroll.availableWidth
                spacing: 0
                Repeater {
                    model: shortcutTable
                    delegate: RowLayout {
                        required property var modelData
                        Layout.fillWidth: true
                        spacing: 12
                        PlainLabel {text:modelData.keys;color:ink;font.family:"monospace";Layout.preferredWidth:210;Layout.topMargin:8;Layout.bottomMargin:8}
                        PlainLabel {text:modelData.description;color:muted;wrapMode:Text.Wrap;Layout.fillWidth:true}
                    }
                }
            }
        }
        footer: DialogButtonBox {
            background: Rectangle {color:panel}
            Action {id:closeShortcutHelp;text:"Close";Accessible.name:"Close shortcut help";DialogButtonBox.buttonRole:DialogButtonBox.RejectRole;onClicked:shortcutDialog.close()}
        }
    }
    Dialog {
        id: messagesDialog
        objectName: "messagesDialog"
        title: "Messages"
        anchors.centerIn: parent
        width: Math.min(720, win.width - 80)
        height: Math.min(460, win.height - 100)
        modal: true
        focus: true
        closePolicy: Popup.CloseOnEscape
        standardButtons: Dialog.Close
        onClosed: messagesButton.forceActiveFocus()
        ListView {
            id: messageList
            anchors.fill: parent
            clip: true
            model: messagesModel
            focus: true
            activeFocusOnTab: true
            Accessible.role: Accessible.List
            Accessible.name: "Last 50 messages, newest first"
            ScrollBar.vertical: ScrollBar {}
            delegate: Rectangle {
                id: messageEntry
                required property string messageLevel
                required property string messageTime
                required property string messageText
                width: messageList.width
                height: messageRow.implicitHeight + 16
                color: panel
                border.color: messageList.activeFocus && ListView.isCurrentItem ? blue : dividerColor
                border.width: messageList.activeFocus && ListView.isCurrentItem ? focusWidth : 1
                Accessible.role: Accessible.ListItem
                Accessible.name: messageEntry.messageLevel + " · " + messageEntry.messageTime + " · " + messageEntry.messageText
                RowLayout {
                    id: messageRow
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.top: parent.top
                    anchors.margins: 8
                    spacing: 8
                    PlainLabel {
                        text: messageEntry.messageLevel
                        color: messageEntry.messageLevel === "error" ? errorInk : messageEntry.messageLevel === "warning" ? warningColor : muted
                        padding: 3
                        background: Rectangle {color: messageEntry.messageLevel === "error" ? errorSurface : panel}
                        Layout.alignment: Qt.AlignTop
                    }
                    PlainLabel {text: messageEntry.messageTime;color: muted;Layout.alignment: Qt.AlignTop}
                    PlainLabel {text: messageEntry.messageText;color: ink;wrapMode: Text.WrapAnywhere;Layout.fillWidth: true}
                }
            }
            PlainLabel {anchors.centerIn: parent;visible: messagesModel.count === 0;text: "No messages yet.";color: muted}
        }
    }
    Dialog {
        id: specificationDialog
        title: "Official specification references"
        anchors.centerIn: parent
        width: Math.min(720, win.width - 80)
        height: Math.min(560, win.height - 100)
        modal: true
        standardButtons: Dialog.Close
        ColumnLayout {
            anchors.fill: parent
            PlainLabel {
                text: "Standard-level references. Exact clauses are not inferred."
                color: muted
                Layout.fillWidth: true
                wrapMode: Text.Wrap
            }
            ListView {
                id: dialogReferences
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                spacing: 10
                property string currentIdentity: win.protocolCardKey
                property string loadedIdentity: ""
                property bool dialogOpen: specificationDialog.visible
                onDialogOpenChanged: if(dialogOpen)loadedIdentity=currentIdentity
                onCurrentIdentityChanged: if(dialogOpen)loadedIdentity=currentIdentity
                model: loadedIdentity===currentIdentity ? specificationLinks : []
                ScrollBar.vertical: ScrollBar {}
                delegate: Column {
                    property alias urlField: dialogReferenceUrl
                    required property var modelData
                    width: ListView.view.width - 14
                    spacing: 6
                    PlainLabel {
                        text: modelData.title || modelData.id
                        textFormat: Text.PlainText
                        color: ink
                        width: parent.width
                        wrapMode: Text.Wrap
                        font.bold: true
                    }
                    PlainLabel {
                        text: [modelData.version, modelData.scope, modelData.access].filter(function (v) {
                            return !!v;
                        }).join(" · ")
                        textFormat: Text.PlainText
                        color: muted
                        width: parent.width
                        wrapMode: Text.Wrap
                        font.pixelSize: 11
                    }
                    PlainLabel {
                        text: modelData.notes || ""
                        textFormat: Text.PlainText
                        color: muted
                        width: parent.width
                        wrapMode: Text.Wrap
                        font.pixelSize: 11
                        visible: !!text
                    }
                    TextArea {
                        id: dialogReferenceUrl
                        textFormat: TextEdit.PlainText
                        text: modelData.url
                        readOnly: true
                        selectByMouse: true
                        wrapMode: TextEdit.WrapAnywhere
                        width: parent.width
                        font.pixelSize: 11
                    }
                    Action {
                        text: "Open official HTTPS source"
                        onClicked: {
                            if (!Qt.openUrlExternally(modelData.url))
                                notice = "The official source could not be opened by the system browser.";
                        }
                    }
                }
            }
        }
    }
    Dialog {
        id: renameDialog
        title: "Preview service edit"
        onAboutToShow: exportFeedback = ""
        onClosed: { preview = {}; previewIntent = {}; }
        anchors.centerIn: parent
        width: 500
        modal: true
        standardButtons: Dialog.Close
        ColumnLayout {
            anchors.fill: parent
            spacing: 12
            PlainLabel {
                text: "Single-section SDT · new version and CRC generated"
                color: muted
                font.pixelSize: 11
            }
            FieldChoice {
                id: editService
                objectName: "editService"
                Layout.fillWidth: true
                enabled: !exporting && !saveDialog.visible
                textRole: "label"
                valueRole: "id"
                model: (detail.services || []).map(function(service) {return {id:service.id, label:(service.name || "Unnamed service") + " · SID " + hex(service.id), name:service.name};})
                Accessible.name: "Service to rename"
                onActivated: {
                    preview = {}; previewIntent = {};
                    renameName.text = (model[currentIndex] || {}).name || "";
                    exportFeedback = "";
                }
            }
            FieldInput {
                id: renameName
                Layout.fillWidth: true
                placeholderText: "New service name"
                enabled: !exporting
                selectByMouse: true
                onTextChanged: { preview = {}; previewIntent = {}; }
                Accessible.name: "New service name"
            }
            Action {
                objectName: "preview"
                text: "Preview change"
                primary: true
                enabled: backendReady && !!analysisState.complete && renameName.text.trim().length > 0 && editService.currentIndex >= 0 && !exporting && !saveDialog.visible
                onClicked: {
                    preview = {};
                    exportFeedback = "";
                    previewIntent = {id:selected, sid:editService.currentValue, name:renameName.text,
                        source:analysisState.source, at:analysisState.selected_packet};
                    core.send("preview_rename", {
                        id: selected,
                        service_id: editService.currentValue,
                        name: renameName.text
                    });
                }
            }
            PlainLabel {
                text: preview.token ? preview.before + " → " + preview.after + " · version " + preview.old_version + " → " + preview.new_version : "Preview the edit before exporting."
                Layout.fillWidth: true
                wrapMode: Text.Wrap
                color: ink
            }
            FieldChoice {
                id: exportFormat
                objectName: "exportFormat"
                Layout.fillWidth: true
                enabled: !exporting && !saveDialog.visible
                textRole: "label"
                valueRole: "value"
                model: [{label: "TS · SI-only transport stream (.ts)", value: "ts"},
                        {label: "BIN · raw SI sections (.bin)", value: "bin"}]
                Accessible.name: "Export format"
                delegate: ItemDelegate {
                    id: formatOption
                    width: exportFormat.width
                    height: 32
                    highlighted: exportFormat.highlightedIndex === index
                    contentItem: PlainLabel {
                        text: modelData.label
                        color: ink
                        verticalAlignment: Text.AlignVCenter
                    }
                    background: Rectangle {
                        color: formatOption.highlighted ? selectionSurface : raised
                        border.color: formatOption.activeFocus ? blue : "transparent"
                    }
                }
            }
            Action {
                id: exportButton
                objectName: "export"
                text: exporting ? "Exporting…" : "Save SI-only " + (exportFormat.currentValue || "ts").toUpperCase() + " + manifest…"
                enabled: backendReady && !!analysisState.complete && !!preview.token && preview.after === renameName.text && preview.service_id === editService.currentValue && !exporting && !saveDialog.visible
                onClicked: openExportDialog()
            }
            PlainLabel {
                text: exportFormat.currentValue === "bin"
                    ? "Raw sections without packet framing, PID or timing. Keep the adjacent manifest for PID and source evidence."
                    : "Signaling-only TS: no audio, video or PCR; snapshot repetition does not retain original timing."
                Layout.fillWidth: true
                wrapMode: Text.Wrap
                color: muted
                font.pixelSize: 11
            }
            PlainLabel {
                text: "Choose a new output path. Existing output or manifest files are refused. The source is unchanged."
                Layout.fillWidth: true
                wrapMode: Text.Wrap
                color: muted
                font.pixelSize: 11
            }
            PlainLabel {
                objectName: "exportFeedback"
                text: exportFeedback
                visible: !!text
                Layout.fillWidth: true
                Layout.maximumHeight: 100
                wrapMode: Text.WrapAnywhere
                elide: Text.ElideRight
                color: ink
            }
        }
    }
}
