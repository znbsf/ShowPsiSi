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
    property var analysisState: core.state
    property var detail: core.detail
    property string tab: "Services"
    property string inspectorView: "Structure"
    property string selected: ""
    property int selectedService: -1
    property string filter: ""
    property var preview: ({})
    property string notice: ""
    property string artifactDir: core.env("SHOWPSISI_ARTIFACT_DIR") || core.root + "/artifacts"
    property string snapshotTarget: ""
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
    property var unfilteredRows: tab === "Services" ? serviceRows : tab === "Tables" ? tableRows : tab === "EPG" ? eventRows : issues
    property var rows: unfilteredRows.filter(function (row) {
        return matchesRecord(row, recordSearch.text);
    })
    property bool selectionHidden: !!selected && !rows.some(function (row) {
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
    function inspect(id, sid) {
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
        if (analysisState.selected_packet !== undefined && analysisState.selected_packet !== null)
            params.at_packet = analysisState.selected_packet;
        core.send("inspect", params);
    }
    function scan() {
        if (core.busy || !source.text.trim() || extraPidsValue === null)
            return;
        inspected = false;
        selected = "";
        selectedService = -1;
        preview = {};
        filter = "";
        recordSearch.clear();
        treeSearch.clear();
        tab = "Services";
        notice = "";
        core.send("analyze", {
            path: source.text.trim(),
            standards: standardChoice.currentValue,
            extra_pids: extraPidsValue
        });
    }
    function snapshot(packet, id) {
        snapshotTarget = id || "";
        selected = "";
        selectedService = -1;
        preview = {};
        core.send("query", packet < 0 ? {} : {
            at_packet: packet
        });
        notice = packet < 0 ? "Latest observed state" : "Snapshot at packet " + num(packet);
    }
    function defaultInspect() {
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
        inspect(tab === "Services" || tab === "EPG" ? row.source_id : row.id, tab === "Services" ? row.id : undefined);
    }
    function rowTitle(row) {
        return tab === "Services" ? (row.logical_channel_number === null ? "—" : row.logical_channel_number) + "  " + (row.name || "Unnamed service") : tab === "Tables" ? row.name + " · PID " + hex(row.pid) + (row.valid === false ? " · INVALID" : "") : tab === "EPG" ? row.title || "Untitled event" : row.code + (row.aggregate ? " · aggregate" : " · PID " + hex(row.pid));
    }
    function rowSubtitle(row) {
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
            color: control.primary ? (control.hovered ? "#1684bb" : "#007acc") : (control.hovered ? "#333333" : "#252526")
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
        function onResponse(method, result) {
            if (result.message) {
                notice = result.message;
                return;
            }
            if (method === "analyze") {
                defaultInspect();
                inspected = true;
                notice = "Scan complete · source unchanged";
            }
            if (method === "query") {
                if (snapshotTarget)
                    inspect(snapshotTarget);
                else
                    defaultInspect();
                snapshotTarget = "";
            }
            if (method === "preview_rename") {
                preview = result;
                notice = "Preview ready · no source changes";
            }
            if (method === "export")
                notice = "Exported " + num(result.bytes) + " bytes + manifest";
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
        id: plainTextTimer
        interval: 200
        repeat: true
        property bool hoveredRecord: false
        onTriggered: {
            if (!analysisState.complete || core.inspecting || !detail.id || !serviceRows.length)
                return;
            if (!hoveredRecord) {
                notice = serviceRows[0].name;
                core.hover("service_" + serviceRows[0].id);
                statusTooltip.open();
                hoveredRecord = true;
                return;
            }
            let report = core.textSafetyReport("<img");
            report.literal_name = serviceRows[0].name.indexOf("<b>name</b>") >= 0;
            report.passed = report.literal_name && report.matched_text_items >= 3 && report.tooltip_text_items >= 1 && report.unsafe_text_items === 0;
            core.capture(core.env("SHOWPSISI_SCREENSHOT"));
            core.testResult(JSON.stringify(report));
            stop();
        }
    }
    Timer {
        id: autoTimer
        interval: Math.max(1, autoDelay)
        onTriggered: scan()
    }
    Component.onCompleted: {
        core.mark("ui_ready");
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
    }

    Shortcut {
        sequence: "Ctrl+K"
        onActivated: {
            recordSearch.forceActiveFocus();
            recordSearch.selectAll();
        }
    }
    Shortcut {
        sequence: "Ctrl+O"
        onActivated: fileDialog.open()
    }
    Shortcut {
        sequence: "Ctrl+Return"
        onActivated: scan()
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
                text: (analysisState.detected_standards || "LOCAL") + " · Qt Quick"
                color: muted
                font.pixelSize: 11
            }
            Action {
                objectName: "agentApi"
                text: "Agent API"
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
                enabled: !core.busy
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
                enabled: !core.busy
                Accessible.name: "Additional packet identifiers, comma separated"
                SafeTip {
                    visible: anchorControl.hovered
                    text: "Optional extra packet identifiers, decimal or hexadecimal, from 0 to 8191."
                }
                onAccepted: scan()
            }
            TextField {
                id: source
                Layout.fillWidth: true
                text: core.sample
                selectByMouse: true
                implicitHeight: 30
                Accessible.name: "Transport stream source path"
                onAccepted: scan()
            }
            Action {
                text: "Open…"
                onClicked: fileDialog.open()
                SafeTip {
                    visible: anchorControl.hovered
                    text: "Open transport stream (Ctrl+O)"
                }
            }
            Action {
                text: core.busy ? "Scanning…" : "Analyze"
                primary: true
                enabled: !core.busy && source.text.trim().length > 0 && extraPidsValue !== null
                onClicked: scan()
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
            Layout.fillWidth: true
            Layout.fillHeight: true
            orientation: Qt.Horizontal
            Card {
                SplitView.preferredWidth: 180
                SplitView.minimumWidth: 150
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
                SplitView.fillWidth: true
                SplitView.minimumWidth: 310
                ColumnLayout {
                    anchors.fill: parent
                    spacing: 0
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 0
                        Repeater {
                            model: ["Services", "Tables", "EPG", "Issues"]
                            NavItem {
                                required property string modelData
                                objectName: "tab_" + modelData
                                text: modelData
                                implicitHeight: 35
                                highlighted: tab === modelData
                                focusPolicy: Qt.StrongFocus
                                onClicked: tab = modelData
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
                        placeholderText: "Search names, PID or SID…  Ctrl+K"
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
                        ScrollBar.vertical: ScrollBar {}
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
                            highlighted: tab === "Services" ? selected === modelData.source_id && selectedService === modelData.id : selected === (modelData.source_id || modelData.id)
                            background: Rectangle {
                                color: recordDelegate.highlighted ? "#04395e" : recordDelegate.hovered ? "#2a2d2e" : "transparent"
                                border.color: recordDelegate.activeFocus ? blue : "transparent"
                            }
                            contentItem: Column {
                                spacing: 5
                                PlainLabel {
                                    text: rowTitle(modelData)
                                    width: parent.width
                                    color: modelData.valid === false ? "#f48771" : tab === "Issues" ? "#cca700" : ink
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
                            text: core.busy ? "Scanning source…" : core.error ? "Unable to load data. See the error below." : !analysisState.source ? "Open a transport stream to inspect PSI / SI tables." : recordSearch.text.trim() ? "No records match this search. Press Escape in the search box to clear it." : "No " + tab.toLowerCase() + " in this view."
                            color: muted
                        }
                    }
                }
            }
            Card {
                SplitView.preferredWidth: 520
                SplitView.minimumWidth: 330
                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 10
                    spacing: 8
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
                        visible: !!text
                        Layout.fillWidth: true
                        wrapMode: Text.Wrap
                        color: muted
                        font.pixelSize: 11
                    }
                    PlainLabel {
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
                            text: detail.inspection_scope ? detail.inspection_scope.native_table : "Native table assembly evidence cutoff"
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
                        placeholderText: "Find a field or value…"
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
                        text: "Rename service…"
                        Layout.fillWidth: true
                        enabled: !core.busy && !!analysisState.complete && !core.inspecting && detail.name === "SDT" && detail.valid && !!chosenService()
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
            Layout.fillWidth: true
            height: 105
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
                        objectName: "latest"
                        text: "Latest"
                        implicitHeight: 24
                        enabled: !core.busy && !!analysisState.source
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
                                enabled: !core.busy
                                onClicked: snapshot(modelData.last_packet, modelData.id)
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
                    text: core.error || notice || "Ready · all processing stays on this machine"
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
                selectByMouse: true
                onTextChanged: preview = {}
                Accessible.name: "New service name"
            }
            Action {
                objectName: "preview"
                text: "Preview change"
                primary: true
                enabled: renameName.text.trim().length > 0 && !!chosenService()
                onClicked: {
                    preview = {};
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
            Action {
                objectName: "export"
                text: "Export SI-only TS + manifest"
                enabled: !!preview.token && preview.after === renameName.text
                onClicked: {
                    let p = {
                        path: artifactDir + "/qt-export-" + Date.now() + ".ts",
                        format: "ts",
                        preview_token: preview.token
                    };
                    if (analysisState.selected_packet !== null && analysisState.selected_packet !== undefined)
                        p.at_packet = analysisState.selected_packet;
                    core.send("export", p);
                }
            }
            PlainLabel {
                text: "Exports a new signaling-only file in artifacts. The source is unchanged."
                Layout.fillWidth: true
                wrapMode: Text.Wrap
                color: muted
                font.pixelSize: 11
            }
        }
    }
}
