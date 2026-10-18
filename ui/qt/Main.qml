import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Dialogs

ApplicationWindow {
    id: win
    width: 1440
    height: 900
    minimumWidth: 1000
    minimumHeight: 680
    visible: true
    title: "ShowPsiSi · Transport stream inspector"
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
    property string comparisonSide: "after"
    property string comparisonError: ""
    property bool compactComparison: recordPane.width < 420 || recordPane.height < 520
    property bool compactInspector: inspectorPane.height < 520
    property var analysisState: core.state
    property bool backendReady: core.available && !core.busy
    property var detail: core.detail
    property string tab: "Services"
    onTabChanged: {
        if (tab !== "Changes" && selectedChange) {
            selectedChange = null;
            defaultInspect();
        }
    }
    property string inspectorView: "Structure"
    property string epgLanguage: ""
    property var identifierResult: ({})
    function eventVariant(event) {
        let variants=event.language_variants || [];
        return variants.find(function(v) {return v.language_code === epgLanguage;}) || variants.find(function(v) {return v.language_code === event.default_language;}) || variants[0] || ({});
    }
    function eventTitle(event) {
        let variant=eventVariant(event);
        return variant.language_code ? (variant.title || "No usable title") : (event.title || "Untitled event");
    }
    function metadataEntries() {
        let entries=[];
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
        return entries.sort(function(a,b) {return Number(b.title.indexOf("Event ")===0)-Number(a.title.indexOf("Event ")===0);});
    }
    property bool showInvalidSections: false
    property string evidenceScope: "Merged"
    property var selectedGroup: (analysisState.table_groups || []).find(function(g) { return (g.section_ids || []).indexOf(detail.id) >= 0; }) || ({})
    property var siblingSections: (analysisState.tables || []).filter(function(r) { return (selectedGroup.section_ids || []).indexOf(r.id) >= 0 && (showInvalidSections || r.crc?.status !== "invalid"); })
    property int hiddenInvalidCount: (analysisState.tables || []).filter(function(r) { return r.crc?.status === "invalid" && (!filter || r.name === filter) && (pidFilter < 0 || r.pid === pidFilter); }).length
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
    function agentState() {
        let diagnostics = core.diagnostics();
        return JSON.stringify({settled: !core.busy && !core.inspecting && !core.comparing && diagnostics.pending === 0,
            source: analysisState.source || "", analysis_status: analysisState.analysis_status || "idle",
            selected: selected, selected_service: selectedService, packet: currentPacket(),
            theme: lightTheme ? "light" : "dark", explorer: explorerRows, tab: tab, inspector: inspectorView, tree_search: treeSearch.text,
            focused_tree_path: tree.activeFocus && treeRows[tree.currentIndex] ? treeRows[tree.currentIndex].path : "",
            tree: treeRows.slice(0, 2500), tree_limit: 2500, diagnostics: diagnostics,
            source_map: {tree: "ui/qt/Main.qml:makeTree", transport: "ui/qt/main.cpp:Bridge"}});
    }
    function agentAction(action) {
        if (action.name === "select_tab" && ["Services", "Tables", "EPG", "Issues", "Changes"].indexOf(action.value) >= 0) tab = action.value;
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
    property string snapshotTarget: ""
    property int snapshotTargetService: -1
    property var collapsed: ({
            header: true
        })
    property var treeRows: treeSearch.text.trim() ? filterTree(makeTree(detail, selectedService, {}, true), treeSearch.text) : makeTree(detail, selectedService, collapsed, false)
    property var serviceRows: analysisState.services || []
    property var rawTableRows: (analysisState.tables || []).filter(function (t) {
        return (!filter || t.name === filter) && (pidFilter < 0 || t.pid === pidFilter) && (showInvalidSections || t.crc?.status !== "invalid");
    })
    property var tableRows: logicalTableRows()
    property int logicalTableCount: tableRows.filter(function(r) {return r.logical;}).length
    function logicalTableRows() {
        let out=[];
        (analysisState.table_groups || []).forEach(function(g) {
            let sections=rawTableRows.filter(function(r) {return g.section_ids.indexOf(r.id)>=0;});
            if (!sections.length) return;
            let first=sections.find(function(r) {return (g.selected_section_ids || []).indexOf(r.id)>=0;}) || sections[0];
            let row=Object.assign({},first,{group:g,logical:true,sectionRecords:sections});
            out.push(row);
            if(expandedTables[g.id]) sections.forEach(function(r) {out.push(Object.assign({},r,{exact:true}));});
        });
        return out.length ? out : rawTableRows;
    }
    function toggleTableGroup(row) {
        let next=Object.assign({},expandedTables); next[row.group.id]=!next[row.group.id]; expandedTables=next;
    }
    property var explorerRows: [{pid:-1,name:"All tables",count:(analysisState.table_groups || []).length}].concat((analysisState.table_groups || []).reduce(function(out,g) {
        let row=out.find(function(r) {return r.pid===g.pid && r.name===g.name;});
        if(row) row.count++; else out.push({pid:g.pid,name:g.name,count:1}); return out;
    },[]).sort(function(a,b) {return a.pid-b.pid || a.name.localeCompare(b.name);}))
    property var tableFamilies: ["All tables"].concat((analysisState.tables || []).map(function (t) {
        return t.name;
    }).filter(function (name, index, all) {
        return name && all.indexOf(name) === index;
    }).sort())
    property var extraPidsValue: parseExtraPids(extraPids.text)
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
    property var unfilteredRows: tab === "Services" ? serviceRows : tab === "Tables" ? tableRows : tab === "EPG" ? eventRows : tab === "Changes" ? (comparison.changes || []) : issues
    property var rows: unfilteredRows.filter(function (row) {
        return tab === "Changes" ? searchTerms(recordSearch.text).every(function (term) { return JSON.stringify(row).toLowerCase().indexOf(term) >= 0; }) : matchesRecord(row, recordSearch.text);
    })
    property bool selectionHidden: !!selected && !rows.some(function (row) {
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
        let terms = searchTerms(text);
        if (!terms.length)
            return true;
        let values = Object.keys(row).map(function (key) {
            let value = row[key];
            return typeof value === "number" ? String(value) + " " + hex(value) + " 0x" + value.toString(16) : typeof value === "string" ? value : "";
        }).join(" ").toLowerCase();
        return terms.every(function (term) {
            return values.indexOf(term) >= 0;
        });
    }
    function filterTree(allRows, text) {
        let terms = searchTerms(text), keep = {}, ancestors = [];
        allRows.forEach(function (row, index) {
            while (ancestors.length && allRows[ancestors[ancestors.length - 1]].depth >= row.depth)
                ancestors.pop();
            let value = (row.label + " " + row.value).toLowerCase();
            if (terms.every(function (term) {
                return value.indexOf(term) >= 0;
            })) {
                keep[index] = true;
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
        let result = [];
        function node(path, label, value, depth) {
            let branch = value !== null && typeof value === "object";
            let closed = !expandAll && (hidden[path] === undefined ? (path === "arrivals" || path === "descriptor_audit" || path.endsWith("/meta") || /^service\/[^/]+\/fields$/.test(path)) : !!hidden[path]);
            result.push({
                path: path,
                label: label,
                value: branch ? (isList(value) ? value.length + " entries" : "") : valueText(label, value),
                depth: depth,
                branch: branch,
                closed: closed,
                kind: typeof value
            });
            if (branch && !closed)
                Object.keys(value).forEach(function (k) {
                    node(path + "/" + k, isList(value) ? "[" + k + "]" : k, value[k], depth + 1);
                });
        }
        if (!section.id)
            return result;
        node("header", "Section header", {
            table_id: section.table_id,
            pid: section.pid,
            version: section.version,
            section: section.section,
            last_section: section.last_section,
            bytes: section.bytes,
            valid: section.valid,
            crc: section.crc || {},
            extension: section.extension,
            current_next: section.current
        }, 0);
        function sdkNode(path, value, depth, initiallyClosed) {
            if (!value || !value.name)
                return;
            let attributes = value.attributes || {};
            let identity = attributes.service_id || attributes.program_number || attributes.event_id || attributes.elementary_pid || attributes.elementary_PID || attributes.tag || "";
            let service = (section.services || []).find(function (item) {
                return Number(attributes.service_id) === item.id;
            });
            let closed = !expandAll && (hidden[path] === undefined ? initiallyClosed : !!hidden[path]);
            result.push({
                path: path,
                label: value.name + (identity ? " · " + identity : "") + (service && service.name ? " · " + service.name : ""),
                value: path === "native" && sid >= 0 ? "TSDuck · selected service" : "TSDuck",
                depth: depth,
                branch: true,
                closed: closed,
                kind: "native"
            });
            if (closed)
                return;
            let keys = Object.keys(attributes);
            let descriptor = /descriptor$/.test(value.name);
            let attributePath = path + "/attributes";
            let attributesClosed = !expandAll && (hidden[attributePath] === undefined ? !descriptor : !!hidden[attributePath]);
            if (keys.length)
                result.push({
                    path: attributePath,
                    label: "Attributes",
                    value: keys.length + " fields",
                    depth: depth + 1,
                    branch: true,
                    closed: attributesClosed,
                    kind: "native"
                });
            if (!attributesClosed)
                keys.forEach(function (key) {
                    let text = attributes[key];
                    result.push({
                        path: attributePath + "/" + key,
                        label: key,
                        value: text,
                        depth: depth + 2,
                        branch: false,
                        closed: false,
                        kind: /^(?:0x[0-9a-f]+|[0-9]+)$/i.test(text) ? "number" : "string"
                    });
                });
            if (value.text)
                node(path + "/text", "Text", value.text, depth + 1);
            (value.children || []).forEach(function (child, index) {
                let selectedChild = child.name === "service" && child.attributes && Number(child.attributes.service_id) === sid;
                if (path === "native" && sid >= 0 && child.name === "service" && !selectedChild)
                    return;
                sdkNode(path + "/child/" + index, child, depth + 1, !(selectedChild || child.name === "service_descriptor"));
            });
        }
        if (evidenceScope === "Merged" && section.merged?.native_table)
            sdkNode("native", section.merged.native_table, 0, false);
        if (evidenceScope === "Merged" && (section.native_table_sources || []).length) {
            let sources={};
            section.native_table_sources.forEach(function(source) {
                sources["Section " + source.section + "/" + source.last_section + " · " + crcText(source)]={
                    id:source.id,pid:source.pid,table_id:source.table_id,version:source.version,
                    first_packet:source.first_packet,last_packet:source.last_packet,observations:source.count,
                    crc:source.crc
                };
            });
            node("provenance", section.merged?.complete ? "Merged source sections · exact evidence" : "Candidate source sections · no complete merge", sources, 0);
        }
        if (evidenceScope === "Section" && section.section_native_table)
            sdkNode("native", section.section_native_table, 0, false);
        if (evidenceScope === "Section" && section.section_native_text)
            node("native_section_text", "SDK section display · see Decoded tab", "Exact original section; no merged siblings", 0);
        node("fields", "Application decoded fields", section.fields || {}, 0);
        let services = (section.services || []).filter(function (s) {
            return sid < 0 || s.id === sid;
        });
        services.forEach(function (s) {
            let path = "service/" + s.id;
            result.push({
                path: path,
                label: "Service " + hex(s.id) + " · " + (s.name || "Unnamed"),
                value: "",
                depth: 0,
                branch: true,
                closed: !expandAll && !!hidden[path],
                kind: "object"
            });
            if (expandAll || !hidden[path]) {
                node(path + "/fields", "Service fields", s, 1);
                (section.descriptors || []).filter(function (d) {
                    return d.service_id === s.id;
                }).forEach(function (d) {
                    descriptor(path, d, 1);
                });
            }
        });
        function descriptor(parent, d, depth) {
            let path = parent + "/descriptor/" + d.offset;
            result.push({
                path: path,
                label: (d.native_decoded || d.extension ? "◆ " : "? ") + d.name + " · " + hex(d.tag, 2),
                value: d.length + " B @ " + d.offset,
                depth: depth,
                branch: true,
                closed: !expandAll && !!hidden[path],
                kind: "descriptor"
            });
            if (expandAll || !hidden[path]) {
                node(path + "/meta", "Descriptor header", {
                    tag: d.tag,
                    length: d.length,
                    offset: d.offset,
                    pds: d.pds,
                    malformed: !!d.malformed,
                    native_decoded: !!d.native_decoded,
                    registration_ids: d.registration_ids || [],
                    decode_note: d.native_decode_warning || (d.native_decoded ? "Native decoded" : d.extension ? "Configured extension" : "Unknown semantics; raw bytes preserved")
                }, depth + 1);
                if (Object.keys(d.fields || {}).length)
                    node(path + "/fields", "Application decoded fields", d.fields, depth + 1);
                if (d.native)
                    sdkNode(path + "/native", d.native, depth + 1, false);
                node(path + "/raw", "Raw bytes", d.raw || "", depth + 1);
            }
        }
        (section.descriptors || []).filter(function (d) {
            return !services.some(function (s) {
                return s.id === d.service_id;
            }) && (sid < 0 || d.service_id < 0);
        }).forEach(function (d) {
            descriptor("section", d, 0);
        });
        if (section.distribution)
            node("arrivals", "Arrival distribution · packet positions", section.distribution, 0);
        if ((section.descriptors || []).length) {
            let descriptors=section.descriptors || [];
            node("descriptor_audit", "Descriptor decode audit · selected section", {
                scope:"Application-indexed descriptor loops; native-only table loops may contain additional descriptors",
                native_decoded:descriptors.filter(function(d) {return d.native_decoded;}).length,
                extension_decoded:descriptors.filter(function(d) {return !!d.extension;}).length,
                generic_or_unresolved:descriptors.filter(function(d) {return !d.native_decoded && !d.extension;}).length,
                warnings:descriptors.filter(function(d) {return !!d.native_decode_warning;}).map(function(d) {return hex(d.tag,2) + ": " + d.native_decode_warning;})
            },0);
        }
        if ((section.events || []).length)
            node("events", "Events", section.events, 0);
        if ((section.issues || []).length)
            node("issues", "Validation issues", section.issues, 0);
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
            notice = "Layout could not be saved. The current layout remains usable.";
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
        notice = core.resetLayout() ? "Default layout restored" : "Layout reset for this session; preferences could not be saved.";
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
            defaultInspect();
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
    function changeFields(row) {
        if (!row)
            return "";
        return (row.changed_fields || []).map(function (field) {
            if (field === "payload" && row.kind === "tables")
                return "Raw section bytes changed · compare A / B in Hex";
            let before = row.before ? row.before.value[field] : undefined;
            let after = row.after ? row.after.value[field] : undefined;
            let render = function (value) { return value === undefined ? "—" : typeof value === "object" ? JSON.stringify(value) : valueText(field, value); };
            return field + ": " + render(before) + " → " + render(after);
        }).join("\n");
    }
    function inspectChange(row, sideName) {
        if (!backendReady) return;
        let side = row && row[sideName];
        if (!side || !(side.evidence || []).length)
            return;
        selectedChange = row;
        comparisonSide = sideName;
        inspect(side.evidence[0].id, row.kind === "services" ? side.value.id : -1, side.at_packet);
        notice = "Inspecting " + (sideName === "before" ? "A" : "B") + " at packet " + num(side.at_packet) + ". The current workbench snapshot is unchanged.";
    }
    function inspect(id, sid, atPacket) {
        if (!backendReady || !analysisState.complete) return;
        if (!id) {
            notice = "Aggregate diagnostic: no individual section is indexed.";
            return;
        }
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
                intent.token !== preview.token || preview.after !== renameName.text ||
                intent.source !== analysisState.source || intent.at !== analysisState.selected_packet) {
            exportFeedback = "The preview changed. Preview the edit again before exporting.";
            return;
        }
        let destination = core.exportDestination(url, intent.format);
        if (destination.error) {
            exportFeedback = destination.error;
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
        inspected = false;
        selected = "";
        selectedService = -1;
        snapshotTarget = "";
        snapshotTargetService = -1;
        preview = {};
        comparison = {};
        selectedChange = null;
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
        if (!backendReady || !source.text.trim() || extraPidsValue === null)
            return;
        clearWorkspaceIntentions();
        filter = ""; pidFilter = -1; expandedTables = {};
        recordSearch.clear();
        treeSearch.clear();
        tab = "Services";
        notice = "Scanning source…";
        core.send("analyze", {
            path: source.text.trim(),
            standards: standardChoice.currentValue,
            default_charset: defaultCharset.text.trim(),
            extra_pids: extraPidsValue
        });
    }
    function snapshot(packet, id, sid) {
        if (!backendReady || !analysisState.complete) return;
        selectedChange = null;
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
        return tab === "Services" ? (row.logical_channel_number === null ? "—" : row.logical_channel_number) + "  " + (row.name || "Unnamed service") : tab === "Tables" ? (row.exact ? "Section " + row.section + " · " : "") + tableLabel(row.name) + " · PID " + hex(row.pid) + " · TID " + hex(row.table_id, 2) + (row.valid === false ? " · INVALID" : "") : tab === "EPG" ? eventTitle(row) : row.code + (row.aggregate ? " · aggregate" : " · PID " + hex(row.pid));
    }
    function rowSubtitle(row) {
        if (tab === "Changes")
            return (row.changed_fields || []).join(", ") || "Presence changed · select to inspect source evidence";
        return tab === "Services" ? "SID " + hex(row.id) + " · PMT " + hex(row.pmt_pid) : tab === "Tables" && row.logical ? "ext " + hex(row.extension) + " · v" + row.version + " · " + row.group.observed_section_numbers.length + " sections · " + (row.group.selected_complete ? "complete assembly" : "incomplete assembly") + " · " + row.group.validity : tab === "Tables" ? "v" + row.version + " · section " + row.section + "/" + row.last_section + " · " + row.bytes + " B · " + num(row.count) + " observations · " + crcText(row) : tab === "EPG" ? "SID " + hex(row.service_id) + " · " + row.start + " UTC · " + row.duration_seconds / 60 + " min" : row.detail;
    }
    component PlainLabel: Label {
        textFormat: Text.PlainText
    }
    component SafeTip: ToolTip {
        id: tip
        property var anchorControl: parent
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
    Connections {
        target: core
        function onWorkspaceInvalidated() { clearWorkspaceIntentions(); }
        function onAvailabilityChanged() {
            if (core.availability === "disconnected") {
                autoTimer.stop();
                fileDialog.close();
                notice = "Backend disconnected. Restart the application to continue.";
            }
        }
        function onResponse(method, result) {
            if (method === "lookup_identifier") identifierResult=result;
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
                notice = "Scan cancelled · source unchanged · analyze again when ready";
                return;
            }
            if (result.message) {
                if (method === "export") {
                    exporting = false;
                    exportFeedback = result.message;
                    exportButton.forceActiveFocus();
                }
                notice = result.message;
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
                notice = "Scan complete · source unchanged";
            }
            if (method === "query") {
                if (snapshotTarget)
                    inspect(snapshotTarget, snapshotTargetService);
                else
                    defaultInspect();
                snapshotTarget = "";
                snapshotTargetService = -1;
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
                if (!core.click("history_v1"))
                    return;
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
        property int acknowledgementAttempts: 0
        onTriggered: {
            let mode = core.env("SHOWPSISI_SCRIPT");
            if (phase === 0) {
                originalInspector = inspectorPane.width;
                originalTimeline = timelinePane.height;
                if (mode === "layout-close") {
                    let expectedInspector = inspectorPane.width + 48;
                    let expectedTimeline = timelinePane.height + 48;
                    core.key("Alt+Left");
                    core.key("Alt+Left");
                    core.key("Alt+Up");
                    core.key("Alt+Up");
                    win.close();
                    let saved = core.loadLayout();
                    core.testResult(JSON.stringify({passed: saved.inspector === expectedInspector && saved.timeline === expectedTimeline,
                        saved:saved, expectedInspector:expectedInspector, expectedTimeline:expectedTimeline}));
                    stop();
                    return;
                }
                if (mode === "layout-key-drag" || mode === "layout-key-reset") {
                    core.key("Alt+Left");
                    core.key("Alt+Up");
                    if (mode === "layout-key-drag") {
                        core.drag("inspectorDivider", -40, 0);
                        core.drag("timelineDivider", 0, -30);
                    } else core.click("resetLayout");
                } else if (mode === "layout-key-constrained") {
                    win.width = 1000;
                    win.height = 680;
                } else if (mode === "layout-set") {
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
                    for (let index = 0; index < 40; ++index) { core.key("Alt+Left"); core.key("Alt+Up"); }
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
                core.key("Alt+Left");
                core.key("Alt+Up");
                phase++;
                return;
            }
            let persisted = core.loadLayout();
            let acknowledged = !layoutSaveTimer.running && Math.abs(persisted.inspector - inspectorPane.width) <= 1
                && Math.abs(persisted.timeline - timelinePane.height) <= 1 && Math.abs(persisted.explorer - explorerPane.width) <= 1;
            if (mode === "layout-set" && !acknowledged && ++acknowledgementAttempts < 20) return;
            if (core.env("SHOWPSISI_SCREENSHOT")) core.capture(core.env("SHOWPSISI_SCREENSHOT"));
            core.testResult(JSON.stringify({
                passed: (mode !== "layout-set" || acknowledged) && recordPane.width >= 310 && inspectorPane.width >= 330 && explorerPane.width >= 150 && timelinePane.height >= 105 && workspace.height >= 300 && (mode !== "layout-set" || dragged),
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
                core.click("history_v1");
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
                core.key("F6");
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
                checks.hidden_default=tableRows.length===0 && !detail.id && hiddenInvalidCount===1 && tab==="Tables";
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
                checks.no_old_native=treeRows.every(function(r) {return r.path!=="native";});
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
                tab="Tables"; filter=""; selectedService=-1;
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
                evidenceScope="Section"; collapsed={header:false}; phase=5; return;
            }
            if (phase === 5) {
                checks.section_scope = !treeRows.some(function(r) { return r.path === "native" || r.path === "provenance"; }) && !!detail.section_native_text;
                inspectorView="XML"; evidenceScope="Merged"; phase=6; return;
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
    Component.onCompleted: {
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
        if (core.env("SHOWPSISI_SCRIPT") === "comparison")
            comparisonTestTimer.start();
        if (core.env("SHOWPSISI_SCRIPT").indexOf("lifecycle-") === 0)
            lifecycleTestTimer.start();
        if (core.env("SHOWPSISI_SCRIPT") === "refresh")
            refreshTestTimer.start();
    }
    onClosing: if (layoutSaveTimer.running || pendingInspectorSize >= 0 || pendingTimelineSize >= 0) rememberLayout()

    Shortcut {
        sequence: "Ctrl+K"
        onActivated: {
            recordSearch.forceActiveFocus();
            recordSearch.selectAll();
        }
    }
    Shortcut { sequence: "Alt+Left"; onActivated: resizeInspector(24) }
    Shortcut { sequence: "Alt+Right"; onActivated: resizeInspector(-24) }
    Shortcut { sequence: "Alt+Up"; onActivated: resizeTimeline(24) }
    Shortcut { sequence: "Alt+Down"; onActivated: resizeTimeline(-24) }
    Shortcut {
        sequence: "F6"
        onActivated: {
            if (recordList.activeFocus || recordSearch.activeFocus) {
                inspectorView = "Structure";
                tree.forceActiveFocus();
            } else recordList.forceActiveFocus();
        }
    }
    Shortcut {
        sequence: "Ctrl+Shift+K"
        onActivated: {
            inspectorView = "Structure";
            treeSearch.forceActiveFocus();
            treeSearch.selectAll();
        }
    }
    Shortcut {
        sequence: "Ctrl+O"
        enabled: backendReady
        onActivated: fileDialog.open()
    }
    Shortcut {
        sequence: "Ctrl+Return"
        onActivated: scan()
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
            PlainLabel {
                text: "PSI / SI INSPECTOR"
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
                text: (core.availability === "disconnected" ? "DISCONNECTED" : core.cancelling ? "CANCELLING" : core.busy ? "SCANNING" : analysisState.analysis_status === "cancelled" ? "CANCELLED" : analysisState.detected_standards || "LOCAL") + " · Qt Quick"
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
                    visible: anchorControl.hovered
                    text: "Drag the dividers to resize. Alt+Left/Right resizes the inspector; Alt+Up/Down resizes the timeline. Changes are saved on this computer."
                }
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
                onClicked: notice = uiAgent.saveBundle()
                SafeTip { visible: anchorControl.hovered; text: "Save a real screenshot and structured UI state for debugging. Includes source paths and visible stream metadata." }
            }
        }
    }
    ColumnLayout {
        anchors.fill: parent
        spacing: 0
        RowLayout {
            Layout.fillWidth: true
            Layout.margins: 10
            spacing: 8
            PlainLabel {
                text: "SOURCE"
                color: muted
                font.pixelSize: 11
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
                    }
                ]
                Accessible.name: "Broadcast standard context for next scan"
                SafeTip {
                    visible: anchorControl.hovered
                    text: "Select the broadcast context for the next analysis. Auto uses TSDuck detection; explicit context resolves reused table identifiers."
                }
            }
            FieldInput {
                id: extraPids
                objectName: "extraPids"
                Layout.preferredWidth: 160
                implicitHeight: 30
                placeholderText: "Extra PIDs: 0x30, 100"
                placeholderTextColor: muted
                selectByMouse: true
                enabled: backendReady
                Accessible.name: "Additional packet identifiers, comma separated"
                SafeTip {
                    visible: anchorControl.hovered
                    text: "Optional extra packet identifiers, decimal or hexadecimal, from 0 to 8191."
                }
                onAccepted: scan()
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
                enabled: backendReady
                onClicked: fileDialog.open()
                SafeTip {
                    visible: anchorControl.hovered
                    text: "Open transport stream (Ctrl+O)"
                }
            }
            Action {
                objectName: "analyzeSource"
                text: "Analyze"
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
                SafeTip { visible: anchorControl.hovered; text: "Cancel this scan (Ctrl+.). Wait for it to stop before analyzing again." }
            }
        }
        PlainLabel {
            Layout.leftMargin: 12
            visible: extraPidsValue === null
            text: "Extra PIDs must be decimal or 0x-prefixed hexadecimal values from 0 to 8191."
            color: removedColor
            font.pixelSize: 11
        }
        ProgressBar {
            Layout.fillWidth: true
            Layout.preferredHeight: 2
            visible: core.busy
            indeterminate: true
        }
        RowLayout {
            Layout.fillWidth: true
            Layout.leftMargin: 12
            Layout.rightMargin: 12
            Layout.bottomMargin: 8
            spacing: 20
            PlainLabel {
                text: serviceRows.length + " services"
                color: ink
                font.pixelSize: 11
            }
            PlainLabel {
                text: num(analysisState.observations) + " section observations"
                color: muted
                font.pixelSize: 11
            }
            PlainLabel {
                text: issues.length + " issues · " + num(analysisState.crc_errors) + " cyclic redundancy check failures"
                color: issues.length ? warningColor : muted
                font.pixelSize: 11
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
        SplitView {
            id: verticalWorkspace
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
                        text: (analysisState.standards_context || "auto").toUpperCase() + " · tables"
                        color: ink
                        Layout.margins: 7
                    }
                    ListView {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        clip: true
                        model: explorerRows
                        ScrollBar.vertical: ScrollBar {}
                        delegate: NavItem {
                            required property var modelData
                            width: ListView.view.width
                            height: 32
                            highlighted: tab === "Tables" && pidFilter === modelData.pid && (filter === modelData.name || modelData.pid < 0)
                            contentItem: RowLayout {
                                spacing: 6
                                PlainLabel { objectName: "explorerIcon:" + modelData.pid + ":" + modelData.name; text: modelData.pid < 0 ? "≡" : tableCategory(modelData.name)[1]; color: tableColor(modelData.name); Layout.preferredWidth: 16; horizontalAlignment: Text.AlignHCenter }
                                PlainLabel { visible:modelData.pid >= 0; text: hex(modelData.pid); color: muted; font.family:"monospace"; font.pixelSize:11; Layout.preferredWidth: 49 }
                                PlainLabel { objectName: "explorerLabel:" + modelData.pid + ":" + modelData.name; text: tableLabel(modelData.name); color: modelData.pid < 0 ? ink : tableColor(modelData.name); Layout.fillWidth:true; elide:Text.ElideRight; font.pixelSize:11 }
                                PlainLabel { text: modelData.count; color:muted; font.pixelSize:10; Layout.preferredWidth:18; horizontalAlignment:Text.AlignRight }
                            }
                            onClicked: {
                                filter = modelData.pid < 0 ? "" : modelData.name;
                                pidFilter = modelData.pid; tab = "Tables";
                            }
                            SafeTip { visible:anchorControl.hovered; text: "PID " + hex(modelData.pid) + " · " + modelData.name + " · " + explanation(modelData.name) }
                        }
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
                        Layout.fillWidth: true
                        spacing: 0
                        Repeater {
                            model: ["Services", "Tables", "EPG", "Issues", "Changes"]
                            NavItem {
                                required property string modelData
                                objectName: "tab_" + modelData
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
                                    visible: anchorControl.hovered
                                    text: explanation(modelData)
                                }
                            }
                        }
                        Item {
                            Layout.fillWidth: true
                        }
                    }
                    FieldInput {
                        id: recordSearch
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
                                SafeTip { visible: anchorControl.hovered; text: "Set A to the selected history snapshot, or the final packet in Latest view." }
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
                                SafeTip { visible: anchorControl.hovered; text: "Set B to the selected history snapshot, or the final packet in Latest view." }
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
                            SafeTip { visible: comparisonSummaryHover.hovered; text: anchorControl.text }
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
                            text: tab === "Tables" ? logicalTableCount + " tables · " + rawTableRows.length + " sections" + (recordSearch.text.trim() ? " · " + rows.length + " matching rows" : "") : tab + " · " + rows.length + (recordSearch.text.trim() ? " / " + unfilteredRows.length : "")
                            Layout.fillWidth: true
                            Layout.minimumWidth: 0
                            elide: Text.ElideRight
                            color: muted
                            font.pixelSize: 11
                        }
                        Action {
                            objectName: "toggleInvalidSections"
                            visible: tab === "Tables"
                            implicitHeight: 24
                            text: (showInvalidSections ? "✓ " : "") + "Bad CRC · " + hiddenInvalidCount
                            onClicked: showInvalidSections = !showInvalidSections
                            SafeTip { visible:anchorControl.hovered; text:"Include CRC-invalid evidence in table groups and exact sections" }
                        }
                    }
                    PlainLabel {
                        visible: selectionHidden && !!recordSearch.text.trim()
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
                            height: tab === "Issues" ? 88 : tab === "Services" ? 94 : 58
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
                                        maximumLineCount: tab === "Issues" ? 3 : 1
                                        wrapMode: tab === "Issues" ? Text.Wrap : Text.NoWrap
                                    }
                                    PlainLabel {
                                        visible: tab === "Services"
                                        text: "Type " + hex(modelData.service_type, 2) + " · " + (modelData.service_type_name || "Unknown service type")
                                        width: parent.width; color: muted; font.pixelSize:11; elide:Text.ElideRight
                                    }
                                    PlainLabel {
                                        visible: tab === "Services"
                                        text: "V " + pidList(modelData.video_pids, modelData.media_status) + " · A " + pidList(modelData.audio_pids, modelData.media_status)
                                        width: parent.width; color: muted; font.family:"monospace"; font.pixelSize:10; elide:Text.ElideRight
                                    }
                                }
                            }
                            onClicked: {
                                recordList.currentIndex = index;
                                activate(modelData);
                            }
                            SafeTip {
                                visible: anchorControl.hovered
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
                    id: inspectorColumn
                    anchors.fill: parent
                    anchors.margins: 10
                    spacing: spaceUnit
                    RowLayout {
                        Layout.fillWidth: true
                        TinyLabel {
                            text: "SECTION INSPECTOR"
                            Layout.fillWidth: true
                        }
                        PlainLabel {
                            text: core.inspecting ? "LOADING…" : detail.valid === false ? "INVALID" : "RAW + DECODED"
                            color: detail.valid === false ? removedColor : muted
                            font.pixelSize: 11
                        }
                    }
                    ColumnLayout {
                        visible: !!selectedChange
                        Layout.fillWidth: true
                        spacing: 5
                        RowLayout {
                            Layout.fillWidth: true
                            Action {
                                objectName: "inspectBefore"
                                text: "A · Before"
                                primary: comparisonSide === "before"
                                enabled: backendReady && !!selectedChange && !!selectedChange.before
                                onClicked: inspectChange(selectedChange, "before")
                            }
                            Action {
                                objectName: "inspectAfter"
                                text: "B · After"
                                primary: comparisonSide === "after"
                                enabled: backendReady && !!selectedChange && !!selectedChange.after
                                onClicked: inspectChange(selectedChange, "after")
                            }
                            Item { Layout.fillWidth: true }
                            Action {
                                objectName: "useComparisonSnapshot"
                                text: "Use snapshot"
                                enabled: backendReady && !!selectedChange && !core.inspecting
                                onClicked: {
                                    let row = selectedChange, side = row[comparisonSide];
                                    tab = row.kind === "services" ? "Services" : row.kind === "events" ? "EPG" : "Tables";
                                    recordSearch.clear();
                                    snapshot(side.at_packet, side.evidence[0].id, row.kind === "services" ? side.value.id : -1);
                                }
                                SafeTip { visible: anchorControl.hovered; text: "Switch the workbench to this cutoff. Editing and export will then use this snapshot." }
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
                            SafeTip { visible: changeHover.hovered; text: changeFields(selectedChange) }
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
                        text: detail.pid !== undefined ? "PID " + hex(detail.pid) + " · TID " + hex(detail.table_id, 2) + " · v" + detail.version + " · section " + detail.section + "/" + detail.last_section + " · " + detail.bytes + " B" : "Select a row to view fields and source bytes"
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
                        visible: !!detail.distribution && !compactInspector
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
                        visible: siblingSections.length > 1
                        Layout.fillWidth: true
                        spacing: 4
                        FieldChoice {
                            id: sectionChoice
                            objectName: "sectionChoice"
                            Layout.fillWidth: true
                            implicitHeight: 28
                            model: siblingSections.map(function(r) { return "Section " + r.section + "/" + r.last_section + " · " + crcText(r) + " · #" + r.first_packet; })
                            currentIndex: siblingSections.findIndex(function(r) { return r.id === detail.id; })
                            onActivated: { let r=siblingSections[currentIndex]; if(r) inspect(r.id, -1, detail.native_table_at_packet); }
                            Accessible.name: "Select original section evidence"
                        }
                    }
                    PlainLabel {
                        objectName: "sectionCoverage"
                        text: groupSummary()
                        visible: !!text && !compactInspector
                        Layout.fillWidth: true
                        wrapMode: Text.Wrap
                        font.pixelSize: 11
                        color: selectedGroup.validity === "valid" ? muted : changedColor
                    }
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
                            model: ["Structure", "Hex", "XML", "Decoded", "Metadata"]
                            NavItem {
                                required property string modelData
                                objectName: "inspector_" + modelData
                                text: modelData === "XML" && detail.native_xml_guarded ? "Guarded XML" : modelData
                                highlighted: inspectorView === modelData
                                onClicked: inspectorView = modelData
                            }
                        }
                        FieldChoice {
                            objectName: "evidenceScope"
                            model: ["Merged", "Section"]
                            implicitHeight: 28
                            width: 100
                            currentIndex: evidenceScope === "Merged" ? 0 : 1
                            onActivated: { evidenceScope=currentText; collapsed={header:false}; }
                            Accessible.name: "Merged table or individual section evidence"
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
                        Action { objectName: "expandAllSections"; text: "+"; Accessible.name: "Expand all fields"; onClicked: foldAll(false); SafeTip { visible: anchorControl.hovered; text: "Expand all fields" } }
                        Action { objectName: "collapseAllSections"; text: "−"; Accessible.name: "Collapse all fields"; onClicked: foldAll(true); SafeTip { visible: anchorControl.hovered; text: "Collapse all fields" } }
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
                            objectName: "tree:" + modelData.path
                            highlighted: tree.currentIndex === index
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
                                visible: anchorControl.hovered
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
                                for (let i = 0; i < raw.length; i += 32) {
                                    let bytes = raw.slice(i, i + 32).match(/.{1,2}/g) || [];
                                    lines.push((i / 2).toString(16).toUpperCase().padStart(4, "0") + "  " + bytes.join(" "));
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
                            FieldInput {
                                id: defaultCharset
                                objectName: "defaultCharset"
                                Layout.fillWidth: true
                                placeholderText: "Next scan default charset (e.g. UTF-8)"
                                enabled: backendReady
                                Accessible.name: "Default input charset for next scan"
                                SafeTip { visible: anchorControl.hovered; text: "Optional SDK charset. DVB charsets honor explicit selectors; RAW charsets ignore them. Original bytes are preserved." }
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
                                renameName.text = chosenService().name || "";
                                renameDialog.open();
                            }
                        }
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
                        text: "ARRIVALS · " + (analysisState.timing?.seconds_per_packet > 0 ? "SECONDS · SUPPLIED BITRATE" : "PACKET INDEX · NO CLOCK")
                        Layout.fillWidth: true
                    }
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
                                color: modelData.bad && modelData.count && modelData.bad >= modelData.count ? removedColor : "#3794ff"
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
                        border.color: "#181818"
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
                            model: analysisState.history || []
                            Action {
                                required property var modelData
                                objectName: "history_v" + modelData.version
                                text: modelData.label + " @ " + num(modelData.first_packet)
                                implicitHeight: 24
                                enabled: backendReady
                                onClicked: snapshot(modelData.last_packet, modelData.id)
                            }
                        }
                    }
                }
            }
        }
        }
        Rectangle {
            Layout.fillWidth: true
            height: 26
            color: core.error ? "#5a1d1d" : surface
            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 10
                anchors.rightMargin: 10
                PlainLabel {
                    text: core.error || (core.availability === "starting" ? "Starting backend…" : notice) || "Ready · all processing stays on this machine"
                    color: core.error ? "#ffffff" : muted
                    font.pixelSize: 11
                    Layout.fillWidth: true
                    elide: Text.ElideMiddle
                    SafeTip {
                        id: statusTooltip
                        visible: statusHover.hovered
                        text: anchorControl.text
                    }
                    HoverHandler {
                        id: statusHover
                    }
                }
                PlainLabel {
                    text: num(analysisState.packets) + " packets · C++ / TSDuck"
                    color: muted
                    font.pixelSize: 11
                }
            }
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
            FieldInput {
                id: renameName
                Layout.fillWidth: true
                placeholderText: "New service name"
                enabled: !exporting
                selectByMouse: true
                onTextChanged: preview = {}
                Accessible.name: "New service name"
            }
            Action {
                objectName: "preview"
                text: "Preview change"
                primary: true
                enabled: backendReady && !!analysisState.complete && renameName.text.trim().length > 0 && !!chosenService() && !exporting
                onClicked: {
                    preview = {};
                    exportFeedback = "";
                    core.send("preview_rename", {
                        id: selected,
                        service_id: chosenService().id,
                        name: renameName.text
                    });
                }
            }
            PlainLabel {
                text: preview.token ? preview.before + " → " + preview.after : "Preview the edit before exporting."
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
                enabled: backendReady && !!analysisState.complete && !!preview.token && preview.after === renameName.text && !exporting
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
