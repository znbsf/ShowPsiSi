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
    color: "#181818"
    font.family: "Segoe UI"
    font.pixelSize: 12
    palette.window: "#1f1f1f"
    palette.windowText: "#cccccc"
    palette.base: "#181818"
    palette.text: "#cccccc"
    palette.button: "#252526"
    palette.buttonText: "#cccccc"
    palette.highlight: "#007acc"
    palette.highlightedText: "white"
    palette.mid: "#454545"
    property color ink: "#cccccc"
    property color muted: "#969696"
    property color blue: "#3794ff"
    property color addedColor: "#b5cea8"
    property color removedColor: "#f48771"
    property color changedColor: "#dcdcaa"
    property var savedLayout: core.loadLayout()
    property bool layoutReady: false
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
    property string selected: ""
    property int selectedService: -1
    property string filter: ""
    property var preview: ({})
    property string notice: ""
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
    property var tableRows: (analysisState.tables || []).filter(function (t) {
        return !filter || t.name === filter;
    })
    property var tableFamilies: ["All tables"].concat((analysisState.tables || []).map(function (t) {
        return t.name;
    }).filter(function (name, index, all) {
        return all.indexOf(name) === index;
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
                TDT: "Time and Date Table"
            })[key] || key;
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
            let closed = !expandAll && (hidden[path] === undefined ? (path.endsWith("/meta") || /^service\/[^/]+\/fields$/.test(path)) : !!hidden[path]);
            result.push({
                path: path,
                label: label,
                value: branch ? (Array.isArray(value) ? value.length + " entries" : "") : valueText(label, value),
                depth: depth,
                branch: branch,
                closed: closed,
                kind: typeof value
            });
            if (branch && !closed)
                Object.keys(value).forEach(function (k) {
                    node(path + "/" + k, Array.isArray(value) ? "[" + k + "]" : k, value[k], depth + 1);
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
            valid: section.valid
        }, 0);
        function sdkNode(path, value, depth, initiallyClosed) {
            if (!value || !value.name)
                return;
            let attributes = value.attributes || {};
            let identity = attributes.service_id || attributes.program_number || attributes.event_id || attributes.elementary_PID || attributes.tag || "";
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
        if (section.native_table)
            sdkNode("native", section.native_table, 0, false);
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
                label: d.name + " · " + hex(d.tag, 2),
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
                    malformed: !!d.malformed
                }, depth + 1);
                node(path + "/fields", "Decoded fields", d.fields || {}, depth + 1);
                if (d.native)
                    sdkNode(path + "/native", d.native, depth + 1, true);
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
        let value = { version: 1, explorer: explorerPane.width, inspector: inspectorPane.width, timeline: timelinePane.height };
        if (!core.saveLayout(value))
            notice = "Layout could not be saved. The current layout remains usable.";
    }
    function resetLayout() {
        explorerPane.SplitView.preferredWidth = 180;
        inspectorPane.SplitView.preferredWidth = 520;
        timelinePane.SplitView.preferredHeight = 105;
        notice = core.resetLayout() ? "Default layout restored" : "Layout reset for this session; preferences could not be saved.";
    }
    function resizeInspector(delta) {
        inspectorPane.SplitView.preferredWidth = Math.max(330, Math.min(workspace.width - explorerPane.width - 322, inspectorPane.width + delta));
        layoutSaveTimer.restart();
    }
    function resizeTimeline(delta) {
        timelinePane.SplitView.preferredHeight = Math.max(105, Math.min(350, verticalWorkspace.height - 306, timelinePane.height + delta));
        layoutSaveTimer.restart();
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
        filter = "";
        recordSearch.clear();
        treeSearch.clear();
        tab = "Services";
        notice = "Scanning source…";
        core.send("analyze", {
            path: source.text.trim(),
            standards: standardChoice.currentValue,
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
        let firstTable = (analysisState.tables || [])[0];
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
    function rowTitle(row) {
        if (tab === "Changes")
            return changeTitle(row);
        return tab === "Services" ? (row.logical_channel_number === null ? "—" : row.logical_channel_number) + "  " + (row.name || "Unnamed service") : tab === "Tables" ? row.name + " · PID " + hex(row.pid) + (row.valid === false ? " · INVALID" : "") : tab === "EPG" ? row.title || "Untitled event" : row.code + (row.aggregate ? " · aggregate" : " · PID " + hex(row.pid));
    }
    function rowSubtitle(row) {
        if (tab === "Changes")
            return (row.changed_fields || []).join(", ") || "Presence changed · select to inspect source evidence";
        return tab === "Services" ? (row.provider || "No provider") + " · SID " + hex(row.id) + " · PMT " + hex(row.pmt_pid) + (row.group ? " · " + row.group : "") : tab === "Tables" ? "v" + row.version + " · section " + row.section + "/" + row.last_section + " · " + row.bytes + " B · " + num(row.count) + " observations" : tab === "EPG" ? "SID " + hex(row.service_id) + " · " + row.start + " UTC · " + row.duration_seconds / 60 + " min" : row.detail;
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
            color: "#252526"
            border.color: "#454545"
            radius: 2
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
            color: !control.enabled ? "#252526" : control.primary ? (control.hovered ? "#1684bb" : "#007acc") : (control.hovered ? "#333333" : "#252526")
            border.color: control.activeFocus ? blue : "#454545"
        }
    }
    component NavItem: ItemDelegate {
        id: nav
        implicitHeight: 29
        focusPolicy: Qt.StrongFocus
        contentItem: PlainLabel {
            text: nav.text
            color: nav.highlighted ? "#ffffff" : ink
            verticalAlignment: Text.AlignVCenter
            elide: Text.ElideRight
            font.pixelSize: 11
        }
        background: Rectangle {
            color: nav.highlighted ? "#37373d" : nav.hovered ? "#2a2d2e" : "transparent"
            border.color: nav.activeFocus ? blue : "transparent"
        }
    }
    component Card: Rectangle {
        color: "#1f1f1f"
        border.color: "#333333"
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
            if (method === "cancel_analysis") return;
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
            if (core.env("SHOWPSISI_SCREENSHOT"))
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
                searchChecks = {
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
        interval: 100
        onTriggered: saveDialog.accept()
    }
    Timer {
        id: exportTestTimer
        interval: 150
        repeat: true
        property int step: 0
        property var checks: ({})
        property string savedPreview: ""
        property string savedState: ""
        function choose(path) {
            core.click("export");
            let testIntent = saveIntent;
            saveDialog.close();
            saveIntent = testIntent;
            saveDialog.currentFolder = core.fileUrl(core.env("SHOWPSISI_EXPORT_TEST_DIR"));
            saveDialog.selectedFile = core.fileUrl(path);
            saveDialog.open();
            exportAcceptTimer.start();
        }
        onTriggered: {
            let directory = core.env("SHOWPSISI_EXPORT_TEST_DIR");
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
                checks.remembered_folder = core.localPath(lastExportFolder) === directory;
                choose(directory + "/chosen λ.ts");
                step++;
            } else if (step === 5) {
                if (exporting) return;
                checks.existing_output_refused = exportFeedback.includes("already exists") && JSON.stringify(preview) === savedPreview;
                choose(directory + "/manifest-only.ts");
                step++;
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
                core.testResult(JSON.stringify({checks: checks, passed: Object.values(checks).every(Boolean)}));
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
        interval: 100
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
        onTriggered: {
            let mode = core.env("SHOWPSISI_SCRIPT");
            if (phase === 0) {
                originalInspector = inspectorPane.width;
                originalTimeline = timelinePane.height;
                if (mode === "layout-set") {
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
            if (phase === 1 && mode === "layout-set") {
                dragged = inspectorPane.width > originalInspector + 30 && timelinePane.height > originalTimeline + 20;
                core.key("Alt+Left");
                core.key("Alt+Up");
                phase++;
                return;
            }
            core.testResult(JSON.stringify({
                passed: recordPane.width >= 310 && inspectorPane.width >= 330 && explorerPane.width >= 150 && timelinePane.height >= 105 && workspace.height >= 300 && (mode !== "layout-set" || dragged),
                explorer: explorerPane.width, inspector: inspectorPane.width, timeline: timelinePane.height,
                records: recordPane.width, workspace: workspace.width, dragged: dragged,
                saved: core.loadLayout(),
                invalid_rejected: !core.saveLayout({version:1,explorer:-1,inspector:520,timeline:105}) && !core.saveLayout({version:99,explorer:180,inspector:520,timeline:105})
            }));
            if (core.env("SHOWPSISI_SCREENSHOT")) core.capture(core.env("SHOWPSISI_SCREENSHOT"));
            stop();
        }
    }
    Timer {
        id: comparisonTestTimer
        interval: 200
        repeat: true
        property real phase: 0
        property var checks: ({})
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
                core.click("useComparisonSnapshot");
                phase++;
            } else if (phase === 9) {
                checks.explicit_use_snapshot = tab === "Services" && analysisState.selected_packet === changedService.after.at_packet && detail.native_table_at_packet === changedService.after.at_packet;
                scan();
                phase++;
            } else {
                checks.rescan_clears = !comparison.source && !selectedChange && !fromPacket.text && !toPacket.text;
                core.testResult(JSON.stringify({passed:Object.keys(checks).every(function (key) { return checks[key]; }),checks:checks}));
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
    // Native integration exercises the same controls and bridge as the workbench.
    Timer {
        id: lifecycleTestTimer
        interval: 100
        repeat: true
        property int phase: 0
        property int settledTicks: 0
        property int waitingTicks: 0
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
                if (core.busy) {
                    ++waitingTicks;
                    if (mode === "lifecycle-stale" || mode === "lifecycle-complete-race")
                        checks.ack_did_not_settle = waitingTicks >= 2 && core.cancelling && analysisState.source.indexOf("poison") < 0;
                    return;
                }
                if (++settledTicks < 5) return; // Let deliberately late fixture frames arrive.
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
    Component.onCompleted: {
        core.mark("ui_ready");
        if (core.env("SHOWPSISI_TEST_SIZE") === "compact") {
            width = 1000;
            height = 680;
        }
        Qt.callLater(function () { layoutReady = true; });
        let requestedStandard = core.env("SHOWPSISI_STANDARDS");
        if (requestedStandard) {
            let choice = standardChoice.indexOfValue(requestedStandard);
            if (choice >= 0)
                standardChoice.currentIndex = choice;
        }
        if (core.env("SHOWPSISI_AUTO") === "1")
            autoTimer.start();
        if (core.env("SHOWPSISI_SCRIPT") === "plaintext")
            plainTextTimer.start();
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
    }
    onClosing: if (layoutSaveTimer.running) rememberLayout()

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
        }
        onRejected: {
            core.mark("export_dialog_cancelled");
            saveIntent = {};
            exportButton.forceActiveFocus();
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
        color: "#181818"
        border.color: "#333333"
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
            ComboBox {
                id: standardChoice
                objectName: "standards"
                Layout.preferredWidth: 136
                implicitHeight: 30
                enabled: backendReady
                textRole: "label"
                valueRole: "value"
                model: [
                    {
                        label: "Auto standards",
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
                    }
                ]
                Accessible.name: "Broadcast standard context for next scan"
                SafeTip {
                    visible: anchorControl.hovered
                    text: "Select the broadcast context for the next analysis. Auto uses TSDuck detection; explicit context resolves reused table identifiers."
                }
            }
            TextField {
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
            TextField {
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
            color: "#f48771"
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
                color: issues.length ? "#cca700" : muted
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
            onResizingChanged: if (!resizing) layoutSaveTimer.restart()
            handle: Rectangle {
                objectName: "timelineDivider"
                implicitHeight: 6
                color: SplitHandle.pressed ? blue : SplitHandle.hovered ? "#555555" : "#252526"
            }
        SplitView {
            id: workspace
            SplitView.fillHeight: true
            SplitView.minimumHeight: tab === "Changes" ? 380 : 300
            orientation: Qt.Horizontal
            onResizingChanged: if (!resizing) layoutSaveTimer.restart()
            handle: Rectangle {
                objectName: x < workspace.width / 3 ? "explorerDivider" : "inspectorDivider"
                implicitWidth: 6
                color: SplitHandle.pressed ? blue : SplitHandle.hovered ? "#555555" : "#252526"
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
                        model: tableFamilies
                        ScrollBar.vertical: ScrollBar {}
                        delegate: NavItem {
                            required property string modelData
                            width: ListView.view.width
                            height: 29
                            text: modelData + "  " + (modelData === "All tables" ? (analysisState.tables || []).length : (analysisState.tables || []).filter(function (table) {
                                    return table.name === modelData;
                                }).length)
                            highlighted: tab === "Tables" && (filter === modelData || (!filter && modelData === "All tables"))
                            onClicked: {
                                filter = modelData === "All tables" ? "" : modelData;
                                tab = "Tables";
                            }
                            SafeTip {
                                visible: anchorControl.hovered
                                text: explanation(modelData)
                            }
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
                    TextField {
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
                            TextField {
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
                            TextField {
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
                            ComboBox {
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
                    PlainLabel {
                        text: (tab === "Tables" ? (filter || "All tables") : tab) + " · " + rows.length + (recordSearch.text.trim() ? " / " + unfilteredRows.length : "")
                        Layout.margins: 10
                        color: muted
                        font.pixelSize: 11
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
                        Keys.onSpacePressed: if (currentIndex >= 0)
                            activate(rows[currentIndex])
                        delegate: ItemDelegate {
                            id: recordDelegate
                            required property var modelData
                            required property int index
                            objectName: tab === "Services" ? "service_" + modelData.id : tab === "Issues" ? "issue_" + modelData.code : "record_" + index
                            width: ListView.view.width
                            height: tab === "Issues" ? 88 : 58
                            focusPolicy: Qt.StrongFocus
                            highlighted: tab === "Changes" ? !!selectedChange && selectedChange.key === modelData.key && selectedChange.kind === modelData.kind : tab === "Services" ? selected === modelData.source_id && selectedService === modelData.id : selected === (modelData.source_id || modelData.id)
                            background: Rectangle {
                                color: recordDelegate.highlighted ? "#04395e" : recordDelegate.hovered ? "#2a2d2e" : "transparent"
                                border.color: recordDelegate.activeFocus ? blue : "transparent"
                            }
                            contentItem: Column {
                                spacing: 5
                                PlainLabel {
                                    text: rowTitle(modelData)
                                    width: parent.width
                                    color: tab === "Changes" ? (modelData.change === "added" ? addedColor : modelData.change === "removed" ? removedColor : changedColor) : modelData.valid === false ? removedColor : tab === "Issues" ? "#cca700" : ink
                                    elide: Text.ElideRight
                                    font.pixelSize: 12
                                }
                                PlainLabel {
                                    text: rowSubtitle(modelData)
                                    width: parent.width
                                    color: muted
                                    font.pixelSize: 11
                                    elide: Text.ElideRight
                                    maximumLineCount: tab === "Issues" ? 3 : 1
                                    wrapMode: tab === "Issues" ? Text.Wrap : Text.NoWrap
                                }
                            }
                            onClicked: {
                                recordList.currentIndex = index;
                                activate(modelData);
                            }
                            SafeTip {
                                visible: anchorControl.hovered
                                text: (tab === "Services" ? "LCN: Logical channel number · SID: Service identifier · PMT: Program Map Table\n" : "") + rowTitle(modelData) + "\n" + rowSubtitle(modelData)
                            }
                        }
                        PlainLabel {
                            anchors.centerIn: parent
                            width: parent.width - 40
                            horizontalAlignment: Text.AlignHCenter
                            wrapMode: Text.Wrap
                            visible: rows.length === 0
                            text: core.availability === "starting" ? "Starting backend…" : !core.available ? "Backend disconnected. Restart the application to continue." : core.cancelling ? "Cancelling scan… Waiting for the worker to stop." : core.busy ? "Scanning source…" : analysisState.analysis_status === "cancelled" ? "Scan cancelled. Analyze a source to start again." : core.comparing && tab === "Changes" ? "Comparing observed snapshots…" : core.error ? "Unable to load data. See the error below." : !analysisState.source ? "Open a transport stream to inspect PSI / SI tables." : recordSearch.text.trim() ? "No records match this search. Press Escape in the search box to clear it." : tab === "Changes" ? comparison.source ? "No changes between these cutoffs in this category." : "Set A and B to investigate a version change." : "No " + tab.toLowerCase() + " in this view."
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
                    anchors.fill: parent
                    anchors.margins: 10
                    spacing: compactInspector ? 5 : 8
                    RowLayout {
                        Layout.fillWidth: true
                        TinyLabel {
                            text: "SECTION INSPECTOR"
                            Layout.fillWidth: true
                        }
                        PlainLabel {
                            text: core.inspecting ? "LOADING…" : detail.valid === false ? "INVALID" : "RAW + DECODED"
                            color: detail.valid === false ? "#f48771" : muted
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
                            maximumLineCount: compactInspector ? 2 : 3
                            wrapMode: Text.WrapAnywhere
                            elide: Text.ElideRight
                            font.pixelSize: 11
                            color: changedColor
                            SafeTip { visible: changeHover.hovered; text: changeFields(selectedChange) }
                            HoverHandler { id: changeHover }
                        }
                    }
                    PlainLabel {
                        text: detail.name ? detail.name + " · " + explanation(detail.name) : "Select a section"
                        Layout.fillWidth: true
                        elide: Text.ElideRight
                        color: ink
                        font.weight: Font.DemiBold
                    }
                    PlainLabel {
                        text: detail.pid !== undefined ? "Packet identifier " + hex(detail.pid) + " · version " + detail.version + " · " + detail.bytes + " B · " + num(detail.count) + " repeats" : "Select a row to view fields and source bytes"
                        color: muted
                        font.pixelSize: 11
                        Layout.fillWidth: true
                        elide: Text.ElideRight
                    }
                    PlainLabel {
                        text: detail.native_decode_status ? "TSDuck: " + detail.native_decode_status + (detail.native_table_complete === false ? " · section fragment" : "") : ""
                        visible: !!text && !compactInspector
                        Layout.fillWidth: true
                        wrapMode: Text.Wrap
                        color: muted
                        font.pixelSize: 11
                    }
                    PlainLabel {
                        objectName: "inspectionCutoff"
                        visible: detail.native_table_at_packet !== undefined && detail.native_table_at_packet !== null
                        text: "Assembly cutoff · packet " + num(detail.native_table_at_packet)
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
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 0
                        Repeater {
                            model: ["Structure", "Hex", "XML"]
                            NavItem {
                                required property string modelData
                                objectName: "inspector_" + modelData
                                text: modelData
                                highlighted: inspectorView === modelData
                                onClicked: inspectorView = modelData
                            }
                        }
                        Item {
                            Layout.fillWidth: true
                        }
                    }
                    TextField {
                        id: treeSearch
                        objectName: "treeSearch"
                        visible: inspectorView === "Structure"
                        Layout.fillWidth: true
                        implicitHeight: 30
                        placeholderText: "Find a field…  Ctrl+Shift+K"
                        placeholderTextColor: muted
                        selectByMouse: true
                        Accessible.name: "Search inspector fields and values with ancestor context"
                        Keys.onEscapePressed: clear()
                        onAccepted: {
                            tree.forceActiveFocus();
                            if (treeRows.length)
                                tree.currentIndex = 0;
                        }
                    }
                    PlainLabel {
                        visible: inspectorView === "Structure" && !!treeSearch.text.trim()
                        text: treeRows.length ? "Matching fields with ancestor context · clear to restore collapsed groups" : "No fields or values match this search."
                        Layout.fillWidth: true
                        wrapMode: Text.Wrap
                        color: muted
                        font.pixelSize: 11
                    }
                    ListView {
                        id: tree
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
                            if (r && r.branch && r.closed)
                                toggle(r.path);
                        }
                        Keys.onLeftPressed: {
                            let r = treeRows[currentIndex];
                            if (r && r.branch && !r.closed && !treeSearch.text.trim())
                                toggle(r.path);
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
                                toggle(r.path);
                        }
                        delegate: NavItem {
                            required property var modelData
                            required property int index
                            highlighted: tree.currentIndex === index && tree.activeFocus
                            width: ListView.view.width
                            height: 30
                            leftPadding: 4 + modelData.depth * 13
                            focusPolicy: Qt.StrongFocus
                            contentItem: RowLayout {
                                spacing: 5
                                PlainLabel {
                                    text: modelData.branch ? (modelData.closed ? "▸" : "▾") : "·"
                                    color: muted
                                    Layout.preferredWidth: 10
                                }
                                PlainLabel {
                                    text: modelData.label
                                    color: modelData.branch ? "#4ec9b0" : ink
                                    font.pixelSize: 11
                                    elide: Text.ElideMiddle
                                    Layout.fillWidth: true
                                }
                                PlainLabel {
                                    text: modelData.value
                                    color: modelData.kind === "number" ? "#b5cea8" : modelData.kind === "string" ? "#ce9178" : muted
                                    font.family: "monospace"
                                    font.pixelSize: 11
                                    elide: Text.ElideRight
                                    Layout.maximumWidth: Math.max(90, tree.width * 0.48)
                                }
                            }
                            onClicked: {
                                tree.currentIndex = index;
                                if (modelData.branch)
                                    toggle(modelData.path);
                            }
                            SafeTip {
                                visible: anchorControl.hovered
                                text: modelData.label + (modelData.value ? ": " + modelData.value : "")
                            }
                        }
                    }
                    TinyLabel {
                        text: "SECTION HEX · BYTE OFFSET"
                        visible: inspectorView === "Hex"
                    }
                    ScrollView {
                        visible: inspectorView === "Hex"
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        clip: true
                        TextArea {
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
                            textFormat: TextEdit.PlainText
                            text: detail.tsduck_xml || "No TSDuck XML is available for this section. Raw evidence remains in Hex."
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
        Card {
            id: timelinePane
            SplitView.preferredHeight: savedLayout.timeline
            SplitView.minimumHeight: 105
            SplitView.maximumHeight: 350
            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 9
                spacing: 5
                RowLayout {
                    Layout.fillWidth: true
                    TinyLabel {
                        text: "SECTION OCCURRENCES · RED = INVALID"
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
                Row {
                    Layout.fillWidth: true
                    height: 20
                    spacing: 2
                    Repeater {
                        model: analysisState.density || []
                        Rectangle {
                            required property var modelData
                            width: Math.max(1, (parent.width - ((analysisState.density || []).length - 1) * 2) / Math.max(1, (analysisState.density || []).length))
                            height: 20
                            color: modelData.bad ? "#f48771" : "#3794ff"
                            opacity: modelData.count ? 0.35 + Math.min(0.65, modelData.count / 50) : 0.12
                            SafeTip {
                                visible: binHover.hovered
                                text: modelData.count + " sections / " + modelData.bad + " invalid"
                            }
                            HoverHandler {
                                id: binHover
                            }
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
            color: core.error ? "#5a1d1d" : "#181818"
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
            TextField {
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
            ComboBox {
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
                        color: formatOption.highlighted ? "#37373d" : "#252526"
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
