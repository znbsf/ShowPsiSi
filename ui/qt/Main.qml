import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Dialogs
import "qrc:/shared/workbench.js" as Shared

ApplicationWindow {
    id: win
    width: 1440
    height: 900
    minimumWidth: 1000
    minimumHeight: 680
    visible: true
    title: metadataMode ? "ShowPsiSi · DVB-I metadata inspector" : "ShowPsiSi · Transport stream inspector"
    property string inputKind: "ts"
    readonly property bool metadataMode: inputKind === "dvbi"
    property bool lightTheme: core.env("SHOWPSISI_THEME") === "light" || (!core.env("SHOWPSISI_THEME") && core.loadTheme() === "light")
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
    property bool layoutReady: false
    // Keyboard requests precede SplitView polish; preserve intent until saved.
    property real pendingInspectorSize: -1
    property real pendingTimelineSize: -1
    property var comparison: ({})
    property var selectedChange: null
    property var comparisonWorkspace: null
    property int comparisonEvidenceIndex: 0
    property var previewIntent: ({})
    property string comparisonSide: "after"
    property string comparisonError: ""
    property bool compactComparison: recordPane.width < 420 || recordPane.height < 520
    property bool compactInspector: inspectorPane.height < 520
    property var analysisState: core.state
    property bool backendReady: core.available && !core.busy && !dvbiWorkspace.busy && !protocolRestoring
    property var detail: core.detail
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
    property var topologyRowModel: Shared.workbench.topologyRows ? Shared.workbench.topologyRows(topologyData, topologyFamily, topologySearch.text, topologyExpanded, topologyLimits) : ({rows:[]})
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
        let families=result.projections || [];
        if(!families.some(function(p){return p.family===topologyFamily;}))topologyFamily=families.length ? families[0].family : "";
        if(!topologyFocus && topologyRows.length)topologyFocus=topologyRows[0].node_id;
        if(topologySelection && !topologyNode && !(result.page || {}).has_more)topologyError="The previous object is not observed at this cutoff. Choose an available object.";
    }
    function topologyNavigationPoint() {
        return {selection:topologySelection,focus:topologyFocus,expanded:topologyExpanded,search:topologySearch.text,family:topologyFamily,
            evidence:topologyEvidenceRef,sectionContext:topologySectionContext,resolution:topologyResolution,view:inspectorView,scope:evidenceScope,tab:tab,
            scroll:topologyList.contentY,revision:analysisState.analysis_revision,cutoff:topologyData.at_packet};
    }
    function pushTopologyBack() { topologyBackStack=topologyBackStack.concat([topologyNavigationPoint()]); }
    function topologyBack() {
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
        if(!row || !row.branch || topologySearch.text.trim())return;
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
        if (!backendReady) return "Backend unavailable";
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
    property bool arrivalOpen: false
    property bool sectionGroupOpen: false
    property bool showInvalidSections: false
    property string evidenceScope: "Merged"
    property var selectedGroup: (analysisState.table_groups || []).find(function(g) { return (g.section_ids || []).indexOf(detail.id) >= 0; }) || ({})
    property var siblingSections: (analysisState.tables || []).filter(function(r) { return (selectedGroup.section_ids || []).indexOf(r.id) >= 0 && (showInvalidSections || r.crc?.status !== "invalid"); })
    property int hiddenInvalidCount: (analysisState.tables || []).filter(function(r) { return r.crc?.status === "invalid" && tableMatches(r); }).length
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
        return JSON.stringify({input_kind:inputKind,dvbi:dvbiWorkspace.state(),settled: !protocolRestoring && !dvbiWorkspace.busy && !core.busy && !core.inspecting && !core.comparing && !topologyLoading && !topologyRevealTimer.running && diagnostics.pending === 0,
            source: analysisState.source || "", analysis_status: analysisState.analysis_status || "idle",
            selected: selected, selected_service: selectedService, packet: currentPacket(),
            theme: lightTheme ? "light" : "dark", explorer: explorerRows.map(function(row) {return Object.assign({},row,{selected:explorerSelected(row)});}),
            table_filter: {pid:pidFilter,name:filter,count_unit:"logical_tables"},
            records: {groups:tableModel.groups.map(function(g){return g.id;}),sections:rawTableRows.map(function(r){return r.id;}),hidden:tableModel.hidden,count_text:tableModel.count_text,grouped:groupedTables,page:tablePage},
            history: {all:allTableHistory,entries:historyRows,page:historyPage}, evidence_scope:evidenceScope.toLowerCase(), tab: tab, inspector: inspectorView, tree_search: treeSearch.text,
            focused_tree_path: tree.activeFocus && treeRows[tree.currentIndex] ? treeRows[tree.currentIndex].path : "",
            tree: treeRows.slice(0, 2500), tree_limit: 2500, diagnostics: diagnostics,
            topology: {data:topologyData,family:topologyFamily,selected_node:topologySelection,focused_node:topologyFocus,expanded:topologyExpanded,search:topologySearch.text,rows:topologyRows,loading:topologyLoading,stale:topologyStale,error:topologyError,summary:topologySummary,sources:topologySources,active_evidence:topologyEvidenceRef,section_context:topologySectionContext,resolution:topologyResolution,back_depth:topologyBackStack.length,scope:topologyScopeLabel,can_reveal:topologyCanReveal},
            protocol: {scroll:metadataScroll.contentItem.contentY,cards:protocolCardModel,sources:protocolCardModel.cards.map(function(c){return Shared.workbench.protocolCardSources(c);}),active_evidence:protocolSourceRef,resolution:protocolSourceResolution,can_back:!!protocolSourceOrigin},
            comparison_context: {data:comparison,selected:selectedChange,side:comparisonSide,origin:topologyOrigin},
            inspection: {id:detail.id,revision:detail.analysis_revision,cutoff:detail.native_table_at_packet,anchors:detail.evidence_anchors || [],hex_selection:hexEvidence.selectedText},
            source_map: {tree: "ui/qt/Main.qml:makeTree", transport: "ui/qt/main.cpp:Bridge"}});
    }
    function agentAction(action) {
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
    property var historyRows: Shared.workbench.history(analysisState, detail, allTableHistory)
    property string historyIdentity: [detail.pid,detail.table_id,detail.extension].join(":")
    onHistoryIdentityChanged: historyPage=0
    onAllTableHistoryChanged: historyPage=0
    property string snapshotTarget: ""
    property int snapshotTargetService: -1
    property var collapsed: ({
            header: true
        })
    property var treeRows: treeSearch.text.trim() ? filterTree(makeTree(detail, selectedService, {}, true), treeSearch.text) : makeTree(detail, selectedService, collapsed, false)
    property var serviceRows: analysisState.services || []
    property bool groupedTables: true
    property int tablePage: 0
    property string tableQuery: recordSearch.text
    onTableQueryChanged: tablePage=0
    property var tableModel: Shared.workbench.tables(analysisState, pidFilter, filter, showInvalidSections, recordSearch.text)
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
        let total=groupedTables ? tableModel.groups.length : rawTableRows.length;
        let start=Math.min(tablePage,Math.max(0,Math.ceil(total/100)-1))*100;
        if(!groupedTables) return rawTableRows.slice(start,start+100);
        let out=[];
        tableModel.groups.slice(start,start+100).forEach(function(g) {
            let sections=rawTableRows.filter(function(r) {return g.section_ids.indexOf(r.id)>=0;});
            let first=Shared.workbench.representative(g,sections);
            out.push(Object.assign({},first || g,{group:g,logical:true,hiddenEvidence:!first,sectionRecords:sections}));
            if(expandedTables[g.id]) sections.forEach(function(r) {out.push(Object.assign({},r,{exact:true}));});
        });
        return out;
    }
    function toggleTableGroup(row) {
        let next=Object.assign({},expandedTables); next[row.group.id]=!next[row.group.id]; expandedTables=next;
    }
    property var explorerRows: [{pid:-1,name:"All tables",count:(analysisState.table_groups || []).length}].concat((analysisState.table_groups || []).reduce(function(out,g) {
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
    property var tableFamilies: ["All tables"].concat(["PAT","PMT","SDT","EIT","NIT","CAT","BAT","TDT","TOT"].concat((analysisState.tables || []).map(function (t) {
        return t.name;
    })).filter(function (name, index, all) {
        return name && name !== "Private / other" && all.indexOf(name) === index;
    })).concat(["Private / other"])
    property var extraPidsValue: parseExtraPids(extraPids.text)
    property var pendingScanOptions: null
    property var completedScanOptions: null
    property var sourceScanOptions: ({standards:standardChoice.currentValue,default_charset:defaultCharset.text.trim(),extra_pids:extraPidsValue})
    property string scanOptionsSummary: Shared.workbench.scanOptionsSummary(sourceScanOptions)
    property bool scanOptionsChanged: !!analysisState.complete && completedScanOptions !== null && Shared.workbench.scanOptionsKey(sourceScanOptions) !== Shared.workbench.scanOptionsKey(completedScanOptions)
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
    property var eventRows: analysisState.events || []
    property var issues: analysisState.diagnostics || []
    property var issueCounts: Shared.workbench.issueCounts(issues)
    property var unfilteredRows: tab === "Services" ? serviceRows : tab === "Tables" ? tableRows : tab === "EPG" ? eventRows : tab === "Changes" ? (comparison.changes || []) : issues
    property var rows: unfilteredRows.filter(function (row) {
        return tab === "Tables" ? true : tab === "Changes" ? searchTerms(recordSearch.text).every(function (term) { return JSON.stringify(row).toLowerCase().indexOf(term) >= 0; }) : matchesRecord(row, recordSearch.text);
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
    function nativeWarningsText() {
        let warnings = [], reported = detail.native_decode_warnings || [];
        for (let i = 0; isList(reported) && i < reported.length; ++i)
            if (typeof reported[i] === "string") warnings.push(reported[i]);
        if (detail.native_xml_guarded)
            warnings.push("Guarded SDK XML: " + (detail.native_xml_guard_reason || "ambiguous descriptor interpretation") + ". Original wire bytes remain authoritative in Hex.");
        return warnings.join("\n");
    }
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
        let result=[];
        function visit(node,parent,depth) {
            let canonical=parent ? parent+"/"+node.id : node.id;
            // Keep stable native diagnostic IDs while rendering the shared tree.
            let path=canonical.replace(/^section\//,"").replace(/^assembly(?=\/|$)/,"provenance");
            let branch=!!node.children;
            let closed=branch && !expandAll && (hidden[path]===undefined ? !Shared.workbench.defaultOpen(canonical) : !!hidden[path]);
            result.push({path:path,label:node.label,value:node.value || "",depth:depth,branch:branch,closed:closed,kind:node.kind || "meta"});
            if(branch && !closed) node.children.forEach(function(child){visit(child,canonical,depth+1);});
        }
        visit(Shared.workbench.structure(section,evidenceScope.toLowerCase(),sid),"",0);
        return result;
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
    function rememberLayout() {
        if (!layoutReady)
            return;
        let value = { version: 1, explorer: explorerPane.width,
            inspector: pendingInspectorSize >= 0 ? pendingInspectorSize : inspectorPane.width,
            timeline: pendingTimelineSize >= 0 ? pendingTimelineSize : timelinePane.height };
        if (!core.saveLayout(value)) {
            showMessage("Layout could not be saved. The current layout remains usable.", "warning");
        } else {
            pendingInspectorSize = -1;
            pendingTimelineSize = -1;
        }
    }
    function resetLayout() {
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
    function validPacket(text) {
        return /^\d+$/.test(text) && Number.isSafeInteger(Number(text)) && Number(text) < Number(analysisState.packets || 0);
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
        if (!row)
            return "";
        return (row.changed_fields || []).map(function (field) {
            if (field === "payload" && row.kind === "tables")
                return "Raw section bytes changed · compare A / B in Hex";
            let before = row.before ? row.before.value[field] : undefined;
            let after = row.after ? row.after.value[field] : undefined;
            let render = function (value) {
                if (value === undefined) return "—";
                if (value !== null && typeof value === "object" && !full)
                    return Array.isArray(value) ? value.length + " entries" : "structured metadata";
                return typeof value === "object" ? JSON.stringify(value) : valueText(field, value);
            };
            return field + ": " + render(before) + " → " + render(after);
        }).join("\n");
    }
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
        selected = id;
        selectedService = sid === undefined ? -1 : sid;
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
        core.send("inspect", params);
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
        notice = "Cancelling scan… Waiting for the worker to stop.";
    }
    function scan() {
        if (metadataMode || !backendReady || !source.text.trim() || extraPidsValue === null)
            return;
        clearWorkspaceIntentions();
        filter = ""; pidFilter = -1; expandedTables = {};
        recordSearch.clear();
        treeSearch.clear();
        tab = "Services";
        notice = "Scanning source…";
        pendingScanOptions = {standards:standardChoice.currentValue,default_charset:defaultCharset.text.trim(),extra_pids:extraPidsValue.slice()};
        core.send("analyze", {
            path: source.text.trim(),
            standards: pendingScanOptions.standards,
            default_charset: pendingScanOptions.default_charset,
            extra_pids: pendingScanOptions.extra_pids
        });
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
        return tab === "Services" ? "SID " + hex(row.id) + " · PMT " + hex(row.pmt_pid) : tab === "Tables" && row.logical ? Shared.workbench.groupText(row.group) + " · " + arrivalText(row.group) + (row.hiddenEvidence ? " · Bad-CRC evidence hidden" : "") : tab === "Tables" ? Shared.workbench.wireVersionText(row) + " · " + Shared.workbench.wireSectionText(row) + " · " + row.bytes + " B · " + num(row.count) + " observations · " + crcText(row) : tab === "EPG" ? "SID " + hex(row.service_id) + " · " + row.start + " UTC · " + row.duration_seconds / 60 + " min" : row.detail;
    }
    component PlainLabel: Label {
        textFormat: Text.PlainText
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
            PlainLabel { visible:!!stat.detailText; text:stat.detailText; color:muted; font.pixelSize:11 }
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
        target: dvbiWorkspace
        function onErrorChanged() { if(dvbiWorkspace.error && !core.error)showMessage(dvbiWorkspace.error,"error"); }
        function onBusyChanged() {
            if(metadataMode && !dvbiWorkspace.error && !core.error)
                showMessage(dvbiWorkspace.busy ? "Loading local document…" : dvbiWorkspace.hasDocument ? "Local document imported · original file unchanged" : "Choose a local XML document");
        }
    }
    Connections {
        target: core
        function onErrorChanged() { if(core.error)showMessage(core.error, "error"); }
        function onWorkspaceInvalidated() { clearWorkspaceIntentions(); }
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
            if(method === "analyze") {
                if(result.complete && pendingScanOptions !== null)completedScanOptions=pendingScanOptions;
                pendingScanOptions=null;
            }
            if (method === "query_topology") { acceptTopology(result); return; }
            if(method==="inspect"){
                if(protocolSourceRef)resolveProtocolInspection(result);
                else if(topologyEvidenceRef)resolveTopologyInspection(result);
                if(protocolRestorePending){
                    let origin=protocolRestorePending;protocolRestorePending=null;
                    if(!result.message && result.id===origin.id && result.analysis_revision===origin.revision && result.native_table_at_packet===origin.cutoff){
                        topologyTransition=true;tab=origin.tab;topologyTransition=false;inspectorView=origin.view;evidenceScope=origin.scope;collapsed=origin.collapsed;treeSearch.text=origin.search;
                        protocolCardOffset=origin.offset;protocolRestoreTimer.origin=origin;protocolRestoreTimer.restart();
                    }else {protocolRestoring=false;let message=result.message || "The originating metadata context could not be restored.";if(notice!==message || messageLevel!=="error")showMessage(message,"error");}
                }
            }
            if (method === "lookup_identifier") identifierResult=result;
            if (method === "lookup_satellite") satelliteResult=result;
            if (method === "query") comparisonTestTimer.completedQueries++;
            if (method === "cancel_analysis") {
                if (core.env("SHOWPSISI_SCRIPT") === "lifecycle-stale" || core.env("SHOWPSISI_SCRIPT") === "lifecycle-complete-race") {
                    lifecycleTestTimer.checks.ack_did_not_settle = core.busy && core.cancelling && analysisState.source.indexOf("poison") < 0;
                    core.mark("cancel_ack_observed");
                }
                return;
            }
            if (method === "fixture_late_frames") { lifecycleTestTimer.lateFramesAcknowledged = true; return; }
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
                defaultInspect();
                inspected = true;
                let truncated=(result.demux || {}).truncated_sections || 0;
                showMessage("Scan complete · source unchanged" + (truncated ? " · " + num(truncated) + " truncated section(s)" : ""), truncated ? "warning" : "info");
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
                phase = 3.5;
            } else if (phase === 3.5) {
                let name = "record_" + comparison.changes.findIndex(function (row) { return row.kind === changedService.kind && row.key === changedService.key; });
                checks.change_row_exposed = core.isExposed(name);
                checks.change_row_click = core.click(name);
                core.click("inspectBefore");
                phase = 4;
            } else if (phase === 4) {
                checks.before_cutoff = detail.native_table_at_packet === Number(fromPacket.text);
                checks.before_name = chosenService().name === changedService.before.value.name;
                checks.no_snapshot_mutation = analysisState.selected_packet === initialPacket;
                checks.inspector_controls_exposed = ["inspectBefore", "inspectAfter", "inspectionCutoff", "useComparisonSnapshot"].every(function (name) { return core.isExposed(name); });
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
                checks.cutoff_enter_compares = core.comparing;
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
                core.click("record_" + comparison.changes.findIndex(function (row) { return row.kind === changedService.kind && row.key === changedService.key; }));
                phase = 8;
            } else if (phase === 8) {
                expectedQueryCompletion = completedQueries + 1;
                core.mark("comparison_use_snapshot_requested");
                core.click("useComparisonSnapshot");
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
            if(phase===3) {checks.clamped=analysisState.selected_packet===0 && tablePage===0 && logicalTableCount===1 && tableRows.length===1;core.capture(core.env("SHOWPSISI_SCREENSHOT"));stop();core.testResult(JSON.stringify({passed:Object.keys(checks).every(function(k){return checks[k];}),checks:checks}));}
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
                    if (!core.busy || !analysisState.observations) return;
                    checks.was_scanning = !analysisState.complete;
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
                scan();phase = 1;return;
            }
            if (phase <= 1) {
                if (!core.busy || !analysisState.observations) return;
                checks.accepted_progress = analysisState.source.indexOf("poison") < 0 && !detail.id;
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
                inspectorView="XML"; checks.merged_scope_click=core.click("mergedScope"); phase=6; return;
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
                checks.language_control=core.click("epgLanguage");core.key("End");core.key("Return");phase=4;return;
            }
            if(phase===4){
                checks.chinese=epgLanguage==="zho" && rowTitle(rows[0])==="新闻";
                checks.incomplete=metadataEntries().some(function(x){return x.text.indexOf("incomplete")>=0 && x.text.indexOf("No complete extended text")>=0;});
                identifierKind.currentIndex=3;identifierValue.text="0x0500";
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
        if (core.env("SHOWPSISI_SCRIPT").indexOf("lifecycle-") === 0)
            lifecycleTestTimer.start();
        if (core.env("SHOWPSISI_SCRIPT") === "refresh")
            refreshTestTimer.start();
        if (core.env("SHOWPSISI_SCRIPT") === "workbench-paging") workbenchPagingTimer.start();
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

    Shortcut {
        sequence: "Ctrl+K"
        onActivated: {
            if(metadataMode){dvbiWorkspace.focusSearch();return;}
            if(tab === "Topology"){topologySearch.forceActiveFocus();topologySearch.selectAll();}
            else {recordSearch.forceActiveFocus();recordSearch.selectAll();}
        }
    }
    Shortcut { sequence: "Alt+Left"; onActivated: { if(metadataMode){dvbiWorkspace.back();return;} if(protocolSourceOrigin)protocolSourceBack();else if(topologyBackStack.length || topologyOrigin || topologyEvidenceRef)topologyBack(); } }
    // Alt+Left/Right are reserved for navigation; pane sizing has its own chord.
    Shortcut { sequence: "Ctrl+Alt+Left"; enabled: !metadataMode; onActivated: resizeInspector(24) }
    Shortcut { sequence: "Ctrl+Alt+Right"; enabled: !metadataMode; onActivated: resizeInspector(-24) }
    Shortcut { sequence: "Ctrl+Alt+Up"; enabled: !metadataMode; onActivated: resizeTimeline(24) }
    Shortcut { sequence: "Ctrl+Alt+Down"; enabled: !metadataMode; onActivated: resizeTimeline(-24) }
    Shortcut {
        sequence: "F6"
        onActivated: {
            if(metadataMode){dvbiWorkspace.focusNext();return;}
            focusNextRegion(false);
        }
    }
    Shortcut { sequence:"Shift+F6"; enabled:!metadataMode; onActivated:focusNextRegion(true) }
    Shortcut {
        sequence: "Ctrl+Shift+K"
        onActivated: {
            if(metadataMode){dvbiWorkspace.focusSearch();return;}
            inspectorView = "Structure";
            treeSearch.forceActiveFocus();
            treeSearch.selectAll();
        }
    }
    Shortcut {
        sequence: "Ctrl+O"
        enabled: backendReady
        onActivated: metadataMode ? dvbiWorkspace.openDialog() : fileDialog.open()
    }
    Shortcut {
        sequence: "Ctrl+Return"
        onActivated: metadataMode ? dvbiWorkspace.importDocument(dvbiWorkspace.pathValue()) : scan()
    }
    Shortcut {
        sequence: "Ctrl+."
        enabled: core.available && core.busy && !core.cancelling
        onActivated: cancelScan()
    }
    FileDialog {
        id: fileDialog
        title: "Open transport stream"
        nameFilters: ["Transport streams (*.ts *.mts *.m2ts)", "All files (*)"]
        onAccepted: {
            source.text = core.localPath(selectedFile);
            scan();
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
    header: Rectangle {
        height: 42
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
                objectName: "themeToggle"
                text: lightTheme ? "Dark" : "Light"
                Accessible.name: "Switch to " + (lightTheme ? "dark" : "light") + " theme"
                onClicked: lightTheme = !lightTheme
            }
            Action {
                objectName: "resetLayout"
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
                objectName: "agentApi"
                text: "Agent API"
                enabled: backendReady
                onClicked: core.send("capabilities", {})
            }
            Action {
                objectName: "saveDiagnostics"
                text: "Save diagnostics"
                enabled: !core.busy && !core.inspecting && !core.comparing
                onClicked: {let result=uiAgent.saveBundle();showMessage(result,result.indexOf("Diagnostics failed:")===0 ? "error" : "info");}
                SafeTip { visible: anchorHovered; text: "Save a real screenshot and structured UI state for debugging. Includes source paths and visible stream metadata." }
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
            visible: !metadataMode
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
                    objectName: "analyzeSource"
                    text: "Analyze"
                    Accessible.name: "Analyze transport stream"
                    Accessible.description: scanOptionsChanged ? "Options changed — re-analyze to apply" : ""
                    primary: true
                    visible: !core.busy
                    enabled: backendReady && source.text.trim().length > 0 && extraPidsValue !== null
                    onClicked: scan()
                }
                Action {
                    id: cancelButton
                    objectName: "cancelAnalysis"
                    text: core.cancelling ? "Cancelling…" : "Cancel"
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
            indeterminate: true
        }
        RowLayout {
            visible: !metadataMode
            Layout.fillWidth: true
            Layout.leftMargin: 12
            Layout.rightMargin: 12
            Layout.bottomMargin: 8
            spacing: 20
            StatBadge {
                objectName: "statsServices"
                label: "SERVICES"
                value: num(serviceRows.length)
                Accessible.name: "Show Services · " + value + " services"
                onClicked: tab="Services"
            }
            StatBadge {
                objectName: "statsSections"
                label: "SECTIONS"
                value: num(analysisState.observations)
                detailText: num((analysisState.tables || []).length) + " distinct payloads"
                Accessible.name: "Show Tables · " + value + " section observations · " + detailText
                onClicked: tab="Tables"
            }
            StatBadge {
                objectName: "statsIssues"
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
        SplitView {
            id: verticalWorkspace
            visible: !metadataMode
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
                        text: "↑ ↓ Home End · focus\nEnter / Space · select\nCtrl+K · search records\nCtrl+O · open file\nCtrl+Return · analyze\nCtrl+. · cancel scan\nAlt+Left · back\nCtrl+Alt+←/→ · inspector width\nCtrl+Alt+↑/↓ · timeline height\nF6 / Shift+F6 · next / previous region\nSource → Explorer → Records → Inspector"
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
                    Flow {
                        Layout.fillWidth: true
                        Layout.preferredHeight: implicitHeight
                        spacing: 0
                        Repeater {
                            model: ["Services", "Topology", "Tables", "EPG", "Issues", "Changes"]
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
                        PlainLabel {text:topologyTablesReveal ? "Topology source · current workbench cutoff unchanged" : topologyScopeLabel;Layout.fillWidth:true;elide:Text.ElideRight;color:muted;font.pixelSize:11}
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
                        FieldInput {
                            id: topologySearch
                            objectName: "topologySearch"
                            Layout.fillWidth: true
                            Layout.leftMargin: 8
                            Layout.rightMargin: 8
                            implicitHeight: 30
                            placeholderText: "Find objects, IDs, types or states… Ctrl+K"
                            placeholderTextColor: muted
                            Accessible.name: "Search loaded topology objects, names, decimal or hexadecimal identities, types and states"
                            selectByMouse: true
                            Keys.onEscapePressed: clear()
                            onAccepted: {topologyList.forceActiveFocus();if(topologyRows.length)topologyList.currentIndex=0;}
                        }
                        PlainLabel {
                            objectName: "topologyContext"
                            Layout.fillWidth: true
                            Layout.leftMargin: 8
                            Layout.rightMargin: 8
                            font.pixelSize: 11
                            wrapMode: Text.Wrap
                            color: muted
                            text: topologyScopeLabel + " · observed through packet #" + num(topologyData.at_packet === undefined ? currentPacket() : topologyData.at_packet) + "\n" + (topologyData.nodes || []).length + " / " + ((topologyData.page || {}).total || 0) + " objects loaded" + (topologySearch.text.trim() ? " · search covers loaded objects only" : "") + " · ↑ ↓ focus · Enter select"
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
                                if(row.branch && row.open && !topologySearch.text.trim())toggleTopologyRow(row);
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
                                text: !analysisState.complete ? "Analyze a source to derive semantic objects." : topologyError ? "Topology is unavailable. Raw evidence remains in Tables." : topologySearch.text.trim() ? "No loaded objects match. Clear search or load more objects." : "Retained " + ((topologyData.counts || {}).raw_sections || (analysisState.tables || []).length) + " raw sections. No semantic relationships can be established in this context. Open Tables for the original evidence."
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
                    FieldInput {
                        id: recordSearch
                        visible: tab !== "Topology"
                        objectName: "recordSearch"
                        Layout.fillWidth: true
                        Layout.leftMargin: 8
                        Layout.rightMargin: 8
                        Layout.topMargin: 8
                        implicitHeight: 30
                        placeholderText: tab === "Changes" ? "Search this change page…  Ctrl+K" : "Search names, PID or SID…  Ctrl+K"
                        placeholderTextColor: muted
                        selectByMouse: true
                        Accessible.name: "Search records by name, packet identifier or service identifier"
                        Keys.onEscapePressed: clear()
                        onAccepted: {
                            recordList.forceActiveFocus();
                            if (rows.length)
                                recordList.currentIndex = 0;
                        }
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
                        spacing: 6
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
                                onTextChanged: comparison = {}
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
                                onTextChanged: comparison = {}
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
                                    model: comparisonPresets()
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
                                onActivated: comparison = {}
                                Accessible.name: "Snapshot change category"
                            }
                            Action {
                                objectName: "swapComparison"
                                text: "Swap A/B"
                                enabled: backendReady && !!analysisState.complete && !core.comparing
                                onClicked: { let before = fromPacket.text; fromPacket.text = toPacket.text; toPacket.text = before; }
                            }
                            Action {
                                objectName: "runComparison"
                                text: core.comparing ? "Comparing…" : "Compare"
                                primary: true
                                enabled: backendReady && !core.comparing && !!analysisState.complete && validPacket(fromPacket.text) && validPacket(toPacket.text)
                                onClicked: compareSnapshots(0)
                            }
                        }
                        PlainLabel {
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
                        PlainLabel {
                            visible: !!comparison.summary
                            Layout.fillWidth: true
                            wrapMode: compactComparison ? Text.NoWrap : Text.Wrap
                            elide: Text.ElideRight
                            font.pixelSize: 11
                            color: changedColor
                            text: Object.keys(comparison.summary || {}).map(function (kind) { let count = comparison.summary[kind]; return kind + ": +" + count.added + " / −" + count.removed + " / ~" + count.changed; }).join("  ·  ")
                            SafeTip { visible: comparisonSummaryHover.hovered; text: anchorText }
                            HoverHandler { id: comparisonSummaryHover }
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
                        Layout.fillWidth: true
                        Layout.leftMargin: 10
                        Layout.rightMargin: 8
                        PlainLabel {
                            id: recordCountLabel
                            visible: tab !== "Topology"
                            text: tab === "Tables" ? tableModel.count_text : tab + " · " + rows.length + (recordSearch.text.trim() ? " / " + unfilteredRows.length : "")
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
                        visible: tab !== "Topology" && selectionHidden && (tab === "Tables" || !!recordSearch.text.trim())
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
                            height: tab === "Issues" ? 88 : tab === "Services" ? 72 : modelData.logical ? 100 : 58
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
                            contentItem: RowLayout {
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
                            text: core.availability === "starting" ? "Starting backend…" : !core.available ? "Backend disconnected. Restart the application to continue." : core.cancelling ? "Cancelling scan… Waiting for the worker to stop." : core.busy ? "Scanning source…" : analysisState.analysis_status === "cancelled" ? "Scan cancelled. Analyze a source to start again." : core.comparing && tab === "Changes" ? "Comparing observed snapshots…" : core.error ? "Unable to load data. See the error below." : !analysisState.source ? "Open a transport stream to inspect PSI / SI tables." : recordSearch.text.trim() ? "No records match this search. Press Escape in the search box to clear it." : tab === "Changes" ? comparison.source ? "No changes between these cutoffs in this category." : "Set A and B to investigate a version change." : (tab === "Services" || tab === "EPG") && (analysisState.tables || []).length ? "No derived " + (tab === "Services" ? "services" : "programme events") + " in this view. Open Tables for native signalling fields and raw evidence; an empty projection does not mean decoding failed." : "No " + tab.toLowerCase() + " in this view."
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
                    RowLayout {
                        Layout.fillWidth: true
                        TinyLabel {
                            text: activeInspectionRef ? "SOURCE EVIDENCE" : "SECTION INSPECTOR"
                            Layout.fillWidth: true
                        }
                        Action { text:(arrivalOpen?"▾ ":"▸ ")+"Arrival"; objectName:"arrivalToggle"; visible:!!detail.id; implicitHeight:20; onClicked:arrivalOpen=!arrivalOpen }
                        Action { text:(sectionGroupOpen?"▾ ":"▸ ")+"Sections"; objectName:"sectionGroupToggle"; visible:(selectedGroup.section_ids || []).length>1 || selectedGroup.last_section>0; implicitHeight:20; onClicked:sectionGroupOpen=!sectionGroupOpen }
                        PlainLabel {
                            text: core.inspecting ? "LOADING…" : detail.valid === false ? "INVALID" : "RAW + DECODED"
                            color: detail.valid === false ? removedColor : muted
                            font.pixelSize: 11
                        }
                    }
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
                        spacing: 5
                        RowLayout {
                            Layout.fillWidth: true
                            Action {
                                objectName: "inspectBefore"
                                text: compactInspector ? "A" : "A · Before"
                                Accessible.name: "A · Before"
                                primary: comparisonSide === "before"
                                enabled: backendReady && !!selectedChange && !!selectedChange.before
                                onClicked: inspectChange(selectedChange, "before")
                            }
                            Action {
                                objectName: "inspectAfter"
                                text: compactInspector ? "B" : "B · After"
                                Accessible.name: "B · After"
                                primary: comparisonSide === "after"
                                enabled: backendReady && !!selectedChange && !!selectedChange.after
                                onClicked: inspectChange(selectedChange, "after")
                            }
                            FieldChoice {
                                id: comparisonSource
                                objectName: "comparisonSource"
                                Layout.fillWidth: true
                                Layout.minimumWidth: 65
                                implicitHeight: 28
                                textRole: "label"
                                model: selectedChange && selectedChange[comparisonSide] ? (selectedChange[comparisonSide].evidence || []).map(function(e) {return {label:e.name + " · PID " + hex(e.pid) + " · §" + e.section + " · " + e.id};}) : []
                                currentIndex: comparisonEvidenceIndex
                                enabled: backendReady && count > 0
                                Accessible.name: "Comparison source evidence"
                                onActivated: inspectChange(selectedChange, comparisonSide, currentIndex)
                                SafeTip { visible: anchorHovered; text: comparisonSource.currentText }
                            }
                            Action {
                                objectName:"comparisonTopology"
                                text:compactInspector ? "Tree" : "Topology"
                                Accessible.name:"Topology at the selected comparison cutoff"
                                enabled:backendReady && !!selectedChange && !core.inspecting
                                onClicked:openComparisonTopology()
                                SafeTip {visible:anchorHovered;text:"Inspect semantic objects at this comparison cutoff without changing the workbench snapshot"}
                            }
                            Action {
                                objectName: "useComparisonSnapshot"
                                text: "Use snapshot"
                                enabled: backendReady && !!selectedChange && !core.inspecting
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
                        PlainLabel {
                            text: changeFields(selectedChange) || "Section presence changed between A and B. Inspect the available side."
                            Layout.fillWidth: true
                            maximumLineCount: compactInspector ? 1 : 3
                            wrapMode: Text.WrapAnywhere
                            elide: Text.ElideRight
                            font.pixelSize: 11
                            color: changedColor
                            SafeTip { visible: changeHover.hovered; text: changeFields(selectedChange, true) }
                            HoverHandler { id: changeHover }
                        }
                    }
                    PlainLabel {
                        id: sectionTitle
                        text: detail.name ? tableLabel(detail.name) + (tableLabel(detail.name) === detail.name ? " · " + explanation(detail.name) : "") : "Select a section"
                        SafeTip { id: sectionTitleTip; visible: sectionTitleHover.hovered; text: detail.name + " · " + explanation(detail.name) }
                        HoverHandler { id: sectionTitleHover }
                        Layout.fillWidth: true
                        elide: Text.ElideRight
                        color: tableColor(detail.name)
                        font.weight: Font.DemiBold
                    }
                    PlainLabel {
                        text: detail.pid !== undefined ? "PID " + hex(detail.pid) + " · TID " + hex(detail.table_id, 2) + " · " + Shared.workbench.wireHeaderText(detail) + " · " + detail.bytes + " B" : "Select a row to view fields and source bytes"
                        color: muted
                        font.pixelSize: 11
                        Layout.fillWidth: true
                        elide: Text.ElideRight
                    }
                    PlainLabel {
                        objectName: "sectionCrc"
                        text: crcText(detail) + ((detail.crc || {}).calculated_hex ? " · expected " + detail.crc.calculated_hex : "")
                        visible: !!detail.id
                        Layout.fillWidth: true
                        color: detail.valid === false ? removedColor : muted
                        font.family: "monospace"
                        font.pixelSize: 11
                        elide: Text.ElideRight
                    }
                    PlainLabel {
                        objectName: "sectionArrivals"
                        text: arrivalText(detail)
                        visible: !!text
                        Layout.fillWidth: true
                        color: muted
                        font.pixelSize: 11
                        elide: Text.ElideRight
                        HoverHandler { id: arrivalsHover }
                        SafeTip { visible: arrivalsHover.hovered; text: "Packet-position distribution; not wall-clock timing. " + ((detail.distribution || {}).basis || "") + "\nGap packets min / mean / max: " + detail.distribution?.min_gap_packets + " / " + detail.distribution?.mean_gap_packets + " / " + detail.distribution?.max_gap_packets + (detail.distribution?.first_seconds !== null && detail.distribution?.first_seconds !== undefined ? "\nSeconds from supplied bitrate: " + detail.distribution.first_seconds + " → " + detail.distribution.last_seconds : "\nSeconds unavailable without a bitrate. No PCR-derived clock.") }
                    }
                    Row {
                        visible: !!detail.distribution && arrivalOpen
                        Layout.fillWidth: true
                        Layout.preferredHeight: 12
                        spacing: 1
                        Repeater {
                            model: detail.distribution?.bins || []
                            Rectangle {
                                required property var modelData
                                width: Math.max(1, (inspectorPane.width - 22) / Math.max(1, detail.distribution.bins.length) - 1)
                                height: 12
                                color: modelData.bad ? removedColor : tableColor(detail.name)
                                opacity: modelData.count ? 0.35 + Math.min(0.65, modelData.count / Math.max(1, detail.distribution.observation_count) * 8) : 0.08
                                HoverHandler { id: arrivalBinHover }
                                SafeTip { visible: arrivalBinHover.hovered; text: "Packets " + modelData.from_packet + "–" + modelData.to_packet + ": " + modelData.count + " arrivals; " + modelData.bad + " invalid" }
                            }
                        }
                    }

                    RowLayout {
                        visible: sectionGroupOpen && !!selectedGroup.id
                        Layout.fillWidth: true
                        spacing: 4
                        FieldChoice {
                            id: sectionChoice
                            objectName: "sectionChoice"
                            Layout.fillWidth: true
                            implicitHeight: 28
                            model: siblingSections.map(function(r) { return Shared.workbench.wireSectionText(r) + " · " + crcText(r) + " · #" + r.first_packet; })
                            currentIndex: siblingSections.findIndex(function(r) { return r.id === detail.id; })
                            onActivated: { let r=siblingSections[currentIndex]; if(r){if(topologyEvidenceRef)openTopologySibling(r);else inspect(r.id, -1, detail.native_table_at_packet);} }
                            Accessible.name: "Select original section evidence"
                        }
                    }
                    PlainLabel {
                        objectName: "sectionCoverage"
                        text: groupSummary()
                        visible: !!text && sectionGroupOpen
                        Layout.fillWidth: true
                        wrapMode: Text.Wrap
                        font.pixelSize: 11
                        color: selectedGroup.validity === "valid" ? muted : changedColor
                    }
                    Action { visible:sectionGroupOpen && !!selectedGroup.id; text:(showInvalidSections?"Hide":"Show")+" bad CRC sections"; implicitHeight:24; onClicked:showInvalidSections=!showInvalidSections }
                    PlainLabel {
                        objectName: "inspectionCutoff"
                        visible: detail.native_table_at_packet !== undefined && detail.native_table_at_packet !== null
                        text: (detail.merged?.complete ? "Merged assembly" : "No complete merged assembly") + " · cutoff #" + num(detail.native_table_at_packet)
                        Layout.fillWidth: true
                        elide: Text.ElideRight
                        color: muted
                        font.pixelSize: 11
                        HoverHandler {
                            id: cutoffHover
                        }
                        SafeTip {
                            visible: cutoffHover.hovered
                            text: (detail.inspection_scope ? detail.inspection_scope.native_table : "Native table assembly evidence cutoff") + "\nTSDuck: " + (detail.native_decode_status || "not available") + "\nFirst evidence packet: " + num(detail.first_packet)
                        }
                    }
                    PlainLabel {
                        id: nativeDecodeWarningLabel
                        objectName: "nativeDecodeWarnings"
                        text: nativeWarningsText()
                        visible: !!text
                        Layout.fillWidth: true
                        wrapMode: Text.Wrap
                        color: warningColor
                        font.pixelSize: 11
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
                        Row {
                            objectName: "evidenceScope"
                            width: 100
                            height: 28
                            Action {
                                objectName: "sectionScope"
                                text: "Section"; width: 50; height: 28
                                highlighted: evidenceScope === "Section"
                                onClicked: evidenceScope = "Section"
                                Accessible.name: "Selected section evidence"
                            }
                            Action {
                                objectName: "mergedScope"
                                text: "Merged"; width: 50; height: 28
                                highlighted: evidenceScope === "Merged"
                                onClicked: evidenceScope = "Merged"
                                Accessible.name: "Merged table evidence"
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
                        objectName: "fieldTree"
                        Accessible.role: Accessible.List
                        Accessible.name: "Decoded PSI / SI fields"
                        Accessible.description: "Hierarchical fields. Use arrow keys to navigate and expand, Home and End to jump. Search with Control Shift K."
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
                        Keys.onRightPressed: {
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
                        Keys.onLeftPressed: {
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
                        Keys.onReturnPressed: {
                            let r = treeRows[currentIndex];
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
                            text: (evidenceScope === "Section" ? detail.section_tsduck_xml : detail.merged?.tsduck_xml) || "No standalone native XML is available for this section. Exact section fields and bytes remain in Structure and Hex."
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
                            width: metadataScroll.availableWidth
                            spacing: 8
                            PlainLabel {
                                text: "Selected section: ID names, text encoding and multilingual EPG. Reference labels do not verify current ownership."
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
                                model: protocolCardModel.cards
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
                                    TextArea { visible: protocolEvidenceToggle.checked; text: JSON.stringify(modelData.evidence,null,2); Layout.fillWidth: true; readOnly: true; selectByMouse: true; textFormat: TextEdit.PlainText; wrapMode: TextEdit.WrapAnywhere }
                                }
                            }
                            FieldChoice {
                                id: epgLanguageChoice
                                objectName: "epgLanguage"
                                Layout.fillWidth: true
                                implicitHeight: 30
                                model: ["Default"].concat((detail.events || []).reduce(function(all,e) { (e.language_variants || []).forEach(function(v) {if(all.indexOf(v.language_code)<0)all.push(v.language_code);});return all;}, []).sort())
                                currentIndex: Math.max(0, model.indexOf(epgLanguage || "Default"))
                                onActivated: epgLanguage=currentIndex === 0 ? "" : currentText
                                Accessible.name: "Preferred EPG language"
                            }
                            FieldChoice {
                                id: identifierKind
                                objectName: "identifierKind"
                                Layout.fillWidth: true
                                implicitHeight: 30
                                model: ["original_network_id","network_id","bouquet_id","ca_system_id","private_data_specifier","registration_id","data_broadcast_id","platform_id","oui"]
                                Accessible.name: "Identifier namespace"
                            }
                            RowLayout {
                                Layout.fillWidth: true
                                FieldInput { id: identifierValue; objectName: "identifierValue"; Layout.fillWidth: true; placeholderText: "ID: decimal or 0x hexadecimal"; Accessible.name: "Identifier value" }
                                Action {
                                    objectName: "identifierQuery"
                                    text: "Look up"
                                    enabled: backendReady
                                    onClicked: {
                                        let value=identifierValue.text.trim();
                                        if(!/^(?:0x[0-9a-f]+|[0-9]+)$/i.test(value) || !Number.isSafeInteger(Number(value))) {identifierResult={error:"Enter a whole decimal or hexadecimal ID"};return;}
                                        core.send("lookup_identifier",{namespace:identifierKind.currentText,value:Number(value),standards:detail.standards_context || standardChoice.currentValue});
                                    }
                                }
                            }
                            Action {
                                id: identifierEvidence
                                visible: Object.keys(identifierResult).length > 0
                                text: checked ? "Hide lookup evidence" : "Show lookup evidence"
                                checkable: true
                                Layout.fillWidth: true
                            }
                            PlainLabel {
                                visible: Object.keys(identifierResult).length > 0
                                text: (identifierResult.label || identifierResult.error || identifierResult.status || "") + " · " + (identifierResult.raw_hex || "") + "\n" + (identifierResult.uncertainty || "")
                                Layout.fillWidth: true
                                wrapMode: Text.Wrap
                            }
                            TextArea {
                                visible: identifierEvidence.checked && Object.keys(identifierResult).length > 0
                                Layout.fillWidth: true
                                readOnly: true
                                selectByMouse: true
                                textFormat: TextEdit.PlainText
                                wrapMode: TextEdit.WrapAnywhere
                                text: JSON.stringify(identifierResult,null,2)
                            }
                            PlainLabel { text: "Satellite candidates · nominal GEO slot"; Layout.fillWidth: true; wrapMode: Text.Wrap; font.bold: true; color: blue }
                            RowLayout {
                                Layout.fillWidth: true
                                FieldInput { id: satellitePosition; objectName: "satellitePosition"; Layout.fillWidth: true; placeholderText: "Degrees: 13.0"; Accessible.name: "Orbital position in degrees" }
                                FieldChoice { id: satelliteDirection; objectName: "satelliteDirection"; model: ["E","W"]; implicitWidth: 65; Accessible.name: "Orbital direction" }
                                Action {
                                    objectName: "satelliteQuery"
                                    text: "Candidates"
                                    enabled: backendReady
                                    onClicked: {
                                        let value=satellitePosition.text.trim();
                                        satelliteResult={};
                                        if(!/^(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)$/.test(value) || Number(value)>180) {satelliteResult={error:"Enter degrees from 0 to 180"};return;}
                                        core.send("lookup_satellite",{orbital_position_degrees:Number(value),direction:satelliteDirection.currentText});
                                    }
                                }
                            }
                            TextArea { objectName: "satelliteResult"; visible: Object.keys(satelliteResult).length > 0; text: satelliteText(satelliteResult); Layout.fillWidth: true; readOnly: true; selectByMouse: true; textFormat: TextEdit.PlainText; wrapMode: TextEdit.WrapAnywhere }
                            Action { id: satelliteEvidence; visible: Object.keys(satelliteResult).length > 0; text: checked ? "Hide satellite lookup evidence" : "Satellite lookup evidence"; checkable: true; Layout.fillWidth: true }
                            TextArea { visible: satelliteEvidence.checked && Object.keys(satelliteResult).length > 0; text: JSON.stringify(satelliteResult,null,2); Layout.fillWidth: true; readOnly: true; selectByMouse: true; textFormat: TextEdit.PlainText; wrapMode: TextEdit.WrapAnywhere }
                            PlainLabel { text: detail.text_diagnostic_scope || "Analyze a stream to inspect metadata."; Layout.fillWidth: true; wrapMode: Text.Wrap; color: muted }
                            Repeater {
                                model: metadataEntries()
                                ColumnLayout {
                                    required property var modelData
                                    Layout.fillWidth: true
                                    spacing: 4
                                    PlainLabel { text: modelData.title; Layout.fillWidth: true; wrapMode: Text.Wrap; font.bold: true; color: blue }
                                    TextArea { text: modelData.text; Layout.fillWidth: true; readOnly: true; selectByMouse: true; textFormat: TextEdit.PlainText; wrapMode: TextEdit.WrapAnywhere }
                                    Action { id: evidenceToggle; text: checked ? "Hide original values and source" : "Original values and source"; checkable: true; Layout.fillWidth: true }
                                    TextArea { visible: evidenceToggle.checked; text: modelData.evidence; Layout.fillWidth: true; readOnly: true; selectByMouse: true; textFormat: TextEdit.PlainText; wrapMode: TextEdit.WrapAnywhere }
                                }
                            }
                        }
                    }
                    ListView {
                        visible: inspectorView === "References"
                        Layout.fillWidth:true; Layout.fillHeight:true; clip:true
                        model:specificationLinks; spacing:12; ScrollBar.vertical:ScrollBar {}
                        delegate:Column {
                            required property var modelData
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
                            text: detail.section_native_text || "Native section display unavailable. Raw bytes remain in Hex."
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
                        columns: compactInspector ? 2 : 1
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
                            objectName: "rename"
                            visible: !selectedChange
                            text: "Rename service…"
                            Layout.fillWidth: true
                            enabled: backendReady && !selectedChange && !!analysisState.complete && !core.inspecting && detail.name === "SDT" && detail.valid && !!chosenService()
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
                        text: "ALL ARRIVALS · " + (analysisState.timing?.seconds_per_packet > 0 ? "SECONDS · SUPPLIED BITRATE" : "PACKET INDEX · NO CLOCK")
                        Layout.fillWidth: true
                    }
                    FieldChoice { objectName:"historyScope"; Layout.preferredWidth:180; Layout.minimumWidth:180; model:["Selected table history","All table history"]; currentIndex:allTableHistory?1:0; onActivated:allTableHistory=currentIndex===1; implicitHeight:24 }
                    PlainLabel { text:historyRows.length+" transitions"; color:muted; Layout.fillWidth:true; elide:Text.ElideRight }
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
                    height: 20
                    readonly property int binCount: (analysisState.density || []).length
                    readonly property real binWidth: Math.max(1, (width - Math.max(0, binCount - 1) * 2) / Math.max(1, binCount))
                    readonly property bool interactive: backendReady && !!analysisState.complete
                    // Keyboard parity with the Web slider: arrows step one bin,
                    // Page keys step a tenth, Home/End jump to the ends.
                    objectName: "densityStrip"
                    activeFocusOnTab: interactive
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
                        let packets = Number(analysisState.packets || 0);
                        if (!packets) return 0;
                        return Math.max(0, Math.min(packets - 1, Math.round(index * (packets - 1) / Math.max(1, binCount - 1))));
                    }
                    function binForPacket(packet) {
                        let packets = Number(analysisState.packets || 0);
                        if (!binCount) return -1;
                        if (packet === null || packet === undefined || packets <= 1) return binCount - 1;
                        return Math.max(0, Math.min(binCount - 1, Math.round(packet / (packets - 1) * (binCount - 1))));
                    }
                    Row {
                        anchors.fill: parent
                        spacing: 2
                        Repeater {
                            model: analysisState.density || []
                            Rectangle {
                                required property var modelData
                                required property int index
                                objectName: "densityBin" + index
                                width: densityStrip.binWidth
                                height: 20
                                color: modelData.bad && modelData.count && modelData.bad >= modelData.count ? removedColor : blue
                                opacity: modelData.count ? 0.35 + Math.min(0.65, modelData.count / 50) : 0.12
                                // Partially invalid bins keep the section colour and
                                // add the invalid share instead of hiding the count.
                                Rectangle {
                                    visible: modelData.bad > 0 && !(modelData.count && modelData.bad >= modelData.count)
                                    anchors.left: parent.left
                                    anchors.right: parent.right
                                    anchors.bottom: parent.bottom
                                    // A single invalid section in a dense bin is
                                    // unreadable as a true proportion, so the
                                    // share keeps a visible minimum height.
                                    height: Math.max(3, parent.height * Math.min(1, modelData.bad / Math.max(1, modelData.count)))
                                    color: removedColor
                                    opacity: 0.95
                                }
                                SafeTip {
                                    visible: binHover.hovered
                                    text: "Bin " + (index + 1) + " · " + modelData.count + " sections / " + modelData.bad + " invalid" + (densityStrip.interactive ? " · click to load this position" : "")
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
                            text: axisLabel(Math.round(Math.max(0, Number(analysisState.packets || 1)-1) * modelData))
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
                    opacity: !metadataMode && messageLevel === "info" && messageExpired ? 0 : 1
                    Accessible.ignored: !metadataMode && messageLevel === "info" && messageExpired
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
                    text: metadataMode ? "Independent document · C++ / Expat" : num(analysisState.packets) + " packets · C++ / TSDuck"
                    color: statusFooter.errorStatus ? errorInk : muted
                    font.pixelSize: 11
                }
                Action {
                    id: messagesButton
                    objectName: "messagesButton"
                    visible: !metadataMode
                    text: "Messages"
                    implicitHeight: 22
                    Accessible.name: "Messages · " + messagesModel.count + " recent messages"
                    onClicked: messagesDialog.open()
                }
            }
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
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                spacing: 10
                model: specificationLinks
                ScrollBar.vertical: ScrollBar {}
                delegate: Column {
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
