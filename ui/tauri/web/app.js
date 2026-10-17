/* Native JSON protocol only. Preview/test transports must be injected explicitly by a harness. */
"use strict";
const $ = (selector) => document.querySelector(selector);
const esc = (value) =>
  String(value ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
const num = (value) => Number(value ?? 0).toLocaleString("en-US");
const hex = (value, width = 4) =>
  value == null
    ? "—"
    : "0x" + Number(value).toString(16).toUpperCase().padStart(width, "0");
const glossary = {
  PAT: "Program Association Table · maps services to PMT PIDs",
  PMT: "Program Map Table · elementary streams and clock reference",
  SDT: "Service Description Table · service names and providers",
  EIT: "Event Information Table · programme schedule",
  NIT: "Network Information Table",
  CAT: "Conditional Access Table",
  BAT: "Bouquet Association Table · service bouquet membership",
  TDT: "Time and Date Table · UTC clock",
  MGT: "Master Guide Table · ATSC PSIP",
  TVCT: "Terrestrial Virtual Channel Table · ATSC PSIP",
  CVCT: "Cable Virtual Channel Table · ATSC PSIP",
  VCT: "Virtual Channel Table · ATSC PSIP",
  STT: "System Time Table · ATSC PSIP",
  RRT: "Rating Region Table · ATSC PSIP",
  ETT: "Extended Text Table · ATSC PSIP",
  BIT: "Broadcaster Information Table · ISDB",
  CDT: "Common Data Table · ISDB",
  SDTT: "Software Download Trigger Table · ISDB",
  LDT: "Linked Description Table · ISDB",
  RST: "Running Status Table",
  AIT: "Application Information Table",
  DIT: "Discontinuity Information Table",
  SIT: "Selection Information Table",
  TOT: "Time Offset Table · UTC and local time offsets",
  PID: "Packet Identifier · 13 bits",
  SID: "Service Identifier · 16 bits",
  LCN: "Logical Channel Number",
  EPG: "Electronic Programme Guide",
  PDS: "Private Data Specifier · 32 bits",
  CRC: "Cyclic Redundancy Check",
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
  LIT: "Local Event Information Table · ISDB",
  NBIT: "Network Board Information Table · ISDB",
  PCAT: "Partial Content Announcement Table · ISDB",
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
};
const known = ["PAT", "PMT", "SDT", "EIT", "NIT", "CAT", "BAT", "TDT", "TOT"];
const fieldHelp = {
  pid: "Packet identifier (13 bits)",
  pmt_pid: "PID carrying the Program Map Table",
  pcr_pid: "PID carrying the Program Clock Reference",
  table_id: "Table identifier (8 bits)",
  extension: "Table ID extension: table-specific 16-bit identifier",
  service_id: "Service identifier (16 bits)",
  transport_stream_id: "Transport stream identifier (16 bits)",
  original_network_id: "Original network identifier (16 bits)",
  private_data_specifier:
    "Private Data Specifier (32 bits): selects private descriptor scope",
  descriptor_tag: "Descriptor identifier (8 bits)",
  native_table_at_packet:
    "Latest packet eligible for native multi-section table assembly; later observations are excluded",
  section_byte_offset:
    "Byte offset within this section, not the transport stream file",
  current: "Whether this table applies now rather than next",
  first_file_offset: "TS packet byte offset; the section may span packets",
  raw_bytes: "Original descriptor bytes including tag and length",
};
const tableLabels = {
  "DSMCC_user_to_network_message": "DSM-CC U-N",
  "DSMCC_download_data_message": "DSM-CC Data",
  "DSMCC_stream_descriptors_table": "DSM-CC SDT",
  "container_table": "DVB Container",
  "splice_information_table": "SCTE-35",
  "cable_emergency_alert_table": "SCTE EAS",
  "discontinuity_information_table": "DIT",
  "selection_information_table": "SIT"
};
const tableLabel = (name) => tableLabels[name] || name;
const tip = (key) => `title="${esc((tableLabels[key] ? key + " · " : "") + (glossary[key] || key))}"`;
let data = {},
  detail = {},
  env = {},
  seq = 0,
  pending = new Map(),
  tab = "Services",
  filter = "",
  search = "",
  page = 0,
  historyPage = 0;
let selected = "",
  selectedService = -1,
  selectedKey = "",
  busy = false,
  loadingDetail = false,
  detailError = "",
  inspectEpoch = 0,
  queryEpoch = 0,
  scanEpoch = 0,
  cancelling = false,
  activeAnalyze = null;
let aggregateDiagnostic = null;
let backendFailure = "";
let comparison = { from: null, to: null, kind: "all", result: null, error: "", loading: false, epoch: 0 };
let savedWorkspace = null, comparisonEvidence = "", inspectionEvidence = null;
let firstPaint = false,
  completePaint = false,
  preview = {},
  editTarget = null,
  treeSearch = "",
  openNodes = new Set(),
  view = "tree";
const PAGE_SIZE = 100;
const native = window.__TAURI__;
const invoke = (...args) =>
  native?.core?.invoke
    ? native.core.invoke(...args)
    : Promise.reject(
        new Error(
          "Native backend unavailable. Open ShowPsiSi using the Tauri application.",
        ),
      );
$("#app").innerHTML = `
<header class="titlebar"><span class="app-mark" aria-hidden="true">≋</span><strong>ShowPsiSi</strong><span class="title-separator">/</span><span class="workspace-name">Transport stream workbench</span><span class="spacer"></span><span class="runtime" id="runtime">Connecting backend</span><span id="layout-status" class="layout-status" role="status"></span><button class="btn quiet" id="reset-layout" title="Restore default pane widths">Reset layout</button><button class="btn quiet" id="api">Agent API</button></header>
<div class="sourcebar"><label for="source">SOURCE</label><input id="source" placeholder="Open a local .ts, .mts or .m2ts file" spellcheck="false"><select id="standards" aria-label="Signalling standards context" title="Explicit native decoder context; auto uses detected signalling, not RF delivery system"><option value="auto">Standards: Auto</option><option value="dvb">DVB</option><option value="atsc">ATSC</option><option value="isdb">ISDB</option><option value="isdb-japan">ISDB Japan</option><option value="isdb-brazil">ISDB Brazil</option><option value="scte">SCTE</option><option value="dtmb">DTMB</option></select><input id="extra-pids" placeholder="Extra PIDs (optional)" aria-label="Additional monitored PIDs, decimal or hexadecimal, comma separated" title="Additional monitored PIDs, decimal or hexadecimal, separated by commas"><button class="btn" id="browse">Open file…</button><button class="btn primary" id="scan">Analyze</button><button class="btn" id="cancel-scan" hidden title="Stop the active analysis; the source file stays unchanged">Cancel</button></div>
<div class="stats" id="stats"></div>
<main class="panes" id="panes"><nav class="sidebar" aria-label="Table library"><div class="panel-title">EXPLORER <span class="muted" title="Program Specific Information / Service Information">PSI / SI</span></div><div id="sidebar"></div><div class="extension" id="extension"></div><div class="sidebar-help">Ctrl / ⌘ K <span>Search records</span><br>↑ ↓ <span>Navigate records</span><br>← → <span>Expand tree</span></div></nav><div class="splitter" id="split-left" aria-controls="sidebar" title="Drag or use arrow keys to resize. Double-click to reset." role="separator" aria-label="Resize explorer" aria-orientation="vertical" tabindex="0"></div><section class="center" aria-label="Stream records"><div class="tabs" id="tabs" role="tablist" aria-label="Record type"></div><div class="searchbar"><span aria-hidden="true">⌕</span><input id="search" type="search" placeholder="Search services, IDs, providers…" aria-label="Search records"><span id="result-count"></span></div><div id="service-head"></div><div class="list" id="list" role="listbox" aria-label="Stream records"></div><div class="pagination"><span id="page-label"></span><span class="spacer"></span><button class="btn small" id="prev" aria-label="Previous page">←</button><button class="btn small" id="next" aria-label="Next page">→</button></div></section><div class="splitter" id="split-right" aria-controls="inspector" title="Drag or use arrow keys to resize. Double-click to reset." role="separator" aria-label="Resize inspector" aria-orientation="vertical" tabindex="0"></div><aside class="inspector" aria-label="Section inspector" id="inspector"></aside></main>
<section class="timeline" aria-label="Section occurrence history" id="timeline"></section>
<footer><span class="status-dot" id="status-dot"></span><span id="notice" role="status" aria-live="polite">Open a stream to begin</span><span id="snapshot-state">LOCAL · SOURCE READ-ONLY</span></footer>
<dialog id="edit-dialog" aria-labelledby="edit-title"><h2 id="edit-title">Rename service</h2><p>Preview an SDT edit. Export creates a new SI-only transport stream and manifest, without media or PCR.</p><label for="edit-service">Service</label><select id="edit-service"></select><label for="rename">New service name</label><input id="rename"><button class="btn primary" id="preview">Preview change</button><p id="diff" role="status"></p><div class="actions"><button class="btn" id="export" disabled>Export SI-only TS + manifest</button><button class="btn" id="close-edit">Close</button></div></dialog>
<dialog id="api-dialog" aria-labelledby="api-title"><h2 id="api-title">Native agent API</h2><pre id="api-text"></pre><button class="btn" id="close-api">Close</button></dialog>`;
function notice(text, error = false) {
  if (backendFailure) {
    text = backendFailure;
    error = true;
  }
  $("#notice").textContent = text;
  $("#notice").title = text;
  $("#notice").setAttribute("aria-live", error ? "assertive" : "polite");
  $("#status-dot").classList.toggle("error", error);
  $("#notice").classList.toggle("error", error);
}
function disableBackendActions() {
  if (!backendFailure) return;
  document
    .querySelectorAll(
      "#scan,#cancel-scan,#browse,#api,#source,#standards,#extra-pids,#edit,#preview,#export,#latest,#compare-snapshots,#run-comparison,#compare-from,#compare-to,#compare-kind,#swap-comparison,[data-preset],[data-comparison-evidence],[data-history]",
    )
    .forEach((element) => {
      element.disabled = true;
    });
  $("#runtime").textContent = "BACKEND DISCONNECTED";
  $("#snapshot-state").textContent = "DISCONNECTED · CACHED DATA ONLY";
}
function disconnectBackend(reason) {
  if (backendFailure) return;
  const exportPending = [...pending.values()].some(
    (job) => job.method === "export",
  );
  backendFailure =
    String(reason || "Native backend stopped. Restart the application.") +
    (exportPending
      ? " An in-flight export may have completed; check its destination before retrying after restart."
      : "");
  busy = false;
  cancelling = false;
  loadingDetail = false;
  activeAnalyze = null;
  ++scanEpoch;
  ++inspectEpoch;
  ++queryEpoch;
  ++comparison.epoch;
  comparison.loading = false;
  comparison.error = backendFailure;
  for (const job of pending.values()) {
    clearTimeout(job.timer);
    job.reject(new Error(backendFailure));
  }
  pending.clear();
  preview = {};
  editTarget = null;
  if (!detail.name) detailError = backendFailure;
  $("#diff").textContent = backendFailure;
  render();
  notice(backendFailure, true);
}
function call(method, params = {}) {
  if (backendFailure) return Promise.reject(new Error(backendFailure));
  const id = ++seq;
  if (method === "analyze") activeAnalyze = id;
  return new Promise((resolve, reject) => {
    // Only idle read requests expire. Analysis may be long-running, and write
    // timeouts would leave ambiguous outcomes. Backend exit rejects every job.
    const canTimeout =
      ["inspect", "query", "diff_snapshots", "capabilities"].includes(method) &&
      !busy &&
      ![...pending.values()].some((job) => job.method === "analyze");
    const timer = canTimeout
      ? setTimeout(() => {
          if (!pending.delete(id)) return;
          reject(
            new Error(
              method +
                " request timed out after 30 seconds. No retry was attempted.",
            ),
          );
        }, 30000)
      : null;
    pending.set(id, { method, resolve, reject, timer });
    invoke("request", { message: { id, method, params } }).catch((error) => {
      clearTimeout(timer);
      pending.delete(id);
      reject(error);
    });
  });
}
function selectionReset() {
  aggregateDiagnostic = null;
  ++inspectEpoch;
  selected = "";
  selectedService = -1;
  selectedKey = "";
  detail = {};
  detailError = "";
  loadingDetail = false;
  openNodes.clear();
}
function resetAnalysisViews() {
  // A saved comparison workspace and an edit token belong to one analysis.
  // Never restore them after a cancellation or a new source revision.
  savedWorkspace = null;
  comparisonEvidence = "";
  inspectionEvidence = null;
  if (tab === "Changes") tab = "Services";
  comparison = { from: null, to: null, kind: "all", result: null, error: "", loading: false, epoch: comparison.epoch + 1 };
  ++queryEpoch;
  selectionReset();
  editTarget = null;
  invalidatePreview();
  $("#preview").disabled = !!backendFailure;
  if ($("#edit-dialog").open) $("#edit-dialog").close();
}
async function cancelScan() {
  if (!busy || cancelling || activeAnalyze === null || backendFailure) return;
  const epoch = scanEpoch, requestId = activeAnalyze;
  cancelling = true;
  resetAnalysisViews();
  data = {};
  render();
  notice("Cancelling analysis… waiting for the engine to stop · source unchanged");
  try {
    const result = await call("cancel_analysis", { request_id: requestId });
    if (epoch !== scanEpoch || activeAnalyze !== requestId) return;
    // Acknowledgment is not the original analysis's terminal result. Keep
    // Analyze disabled even when completion raced the cancellation request.
    if (!result.requested)
      notice("Analysis is finishing… waiting for its result");
  } catch (error) {
    if (epoch !== scanEpoch || activeAnalyze !== requestId) return;
    cancelling = false;
    render();
    notice("Cancellation was not confirmed: " + String(error) + ". Analysis is still pending.", true);
  }
}
async function scan() {
  if (busy || backendFailure) return;
  const path = $("#source").value.trim();
  if (!path) {
    notice("Choose a local transport stream first.", true);
    $("#source").focus();
    return;
  }
  let extraPids = [];
  try {
    extraPids = $("#extra-pids").value.trim()
      ? $("#extra-pids")
          .value.split(",")
          .map((value) => {
            const token = value.trim();
            if (!/^(0x[0-9a-f]+|[0-9]+)$/i.test(token))
              throw new Error(
                "Extra PIDs must be decimal or hexadecimal integers, separated by commas.",
              );
            const pid = Number(token);
            if (pid > 8191)
              throw new Error(
                "Extra PIDs must be between 0 and 8191 (0x1FFF).",
              );
            return pid;
          })
      : [];
  } catch (error) {
    notice(String(error), true);
    $("#extra-pids").focus();
    return;
  }
  const epoch = ++scanEpoch;
  busy = true;
  cancelling = false;
  resetAnalysisViews();
  data = {};
  preview = {};
  filter = "";
  page = 0;
  historyPage = 0;
  firstPaint = false;
  completePaint = false;
  render();
  notice("Analyzing stream… incremental results appear below");
  let succeeded = false;
  try {
    const operation = call("analyze", {
      path,
      standards: $("#standards").value,
      ...(extraPids.length ? { extra_pids: [...new Set(extraPids)] } : {}),
    });
    render();
    const result = await operation;
    if (epoch !== scanEpoch) return;
    data = result;
    succeeded = true;
    render();
    notice(
      (cancelling ? "Analysis completed before cancellation took effect · " : "Analysis complete · ") +
        num(data.packets) +
        " packets · source unchanged",
    );
  } catch (error) {
    if (epoch !== scanEpoch) return;
    if (error.code === "analysis_cancelled") {
      resetAnalysisViews();
      data = error.data?.state || { analysis_status: "cancelled", complete: false };
      notice("Analysis cancelled · source unchanged · ready to analyze again");
    } else {
      resetAnalysisViews();
      data = { source: path, analysis_status: "failed", complete: false };
      notice(String(error), true);
    }
  } finally {
    if (epoch === scanEpoch) {
      const returnFocus = cancelling && (document.activeElement === $("#cancel-scan") || document.activeElement === document.body);
      busy = false;
      cancelling = false;
      activeAnalyze = null;
      render();
      if (succeeded) defaultInspect();
      if (returnFocus && !backendFailure) $("#scan").focus();
    }
  }
}
async function inspect(id, sid = -1, key = "", evidence = null) {
  if (backendFailure || cancelling) return;
  if (!id) {
    notice("Aggregate diagnostic: packet locations are not indexed.");
    return;
  }
  aggregateDiagnostic = null;
  const epoch = ++inspectEpoch;
  const atPacket = evidence ? evidence.atPacket : data.selected_packet;
  comparisonEvidence = evidence?.label || "";
  inspectionEvidence = evidence;
  selected = id;
  selectedService = sid;
  selectedKey = key || id;
  detail = {};
  loadingDetail = true;
  detailError = "";
  openNodes.clear();
  treeSearch = "";
  renderInspector();
  if (tab !== "Changes") renderList();
  else $("#list").querySelectorAll("[data-comparison-evidence]").forEach((button) => button.setAttribute("aria-pressed", String(button.dataset.evidenceKey === selectedKey)));
  try {
    const result = await call("inspect", {
      id,
      ...(atPacket != null ? { at_packet: atPacket } : {}),
    });
    if (epoch !== inspectEpoch) return;
    detail = result;
    openNodes = new Set([
      "section",
      "section/fields",
      "section/services",
      `section/services/${sid}`,
      `section/services/${sid}/descriptors`,
      "section/descriptors",
    ]);
    const primaryDescriptor = (result.descriptors || []).find(
      (d) => d.service_id === sid && d.tag === 0x48,
    );
    if (primaryDescriptor && sid >= 0)
      openNodes.add(
        `section/services/${sid}/descriptors/${primaryDescriptor.offset}`,
      );
    if (comparisonEvidence)
      notice(comparisonEvidence + " · evidence loaded · main snapshot unchanged");
    else if ($("#notice").classList.contains("error"))
      notice("Section loaded · PID " + hex(detail.pid) + " · " + detail.name);
  } catch (error) {
    if (epoch !== inspectEpoch) return;
    detailError = String(error);
    notice(detailError, true);
  } finally {
    if (epoch === inspectEpoch) {
      loadingDetail = false;
      renderInspector();
    }
  }
}
function defaultInspect() {
  const first = data.services?.[0];
  if (first)
    inspect(
      first.source_id,
      first.id,
      "service:" + (first.key ?? [first.onid, first.ts_id, first.id].join(":")),
    );
  else if (data.tables?.[0]) inspect(data.tables[0].id);
}
async function snapshot(packet, id) {
  if (busy || backendFailure) return;
  if (tab === "Changes") changeTab("Services");
  const epoch = ++queryEpoch;
  selectionReset();
  renderInspector();
  notice("Loading packet snapshot…");
  try {
    const result = await call("query", packet < 0 ? {} : { at_packet: packet });
    if (epoch !== queryEpoch) return;
    data = result;
    page = 0;
    render();
    if (id) inspect(id);
    else defaultInspect();
    notice(
      packet < 0
        ? "Latest observed state"
        : "Snapshot through packet " + num(packet),
    );
  } catch (error) {
    if (epoch === queryEpoch) notice(String(error), true);
  }
}
function isOtherTable(t) {
  return !t.name || t.name === "Private / other";
}
function tableFamilies() {
  return [
    ...new Set([
      ...known,
      ...(data.tables || [])
        .map((t) => t.name)
        .filter((name) => name && name !== "Private / other"),
    ]),
  ];
}
function reportedStandards(value) {
  const context =
    value?.detected_standards ??
    value?.standards_context ??
    value?.standards ??
    value?.standard_context ??
    value?.standard;
  return Array.isArray(context)
    ? context.join(" / ")
    : typeof context === "string"
      ? context
      : "";
}
function tableMatches(t) {
  return (
    !filter ||
    (filter === "Private / other" ? isOtherTable(t) : t.name === filter)
  );
}
function render() {
  const stats = [
    ["SERVICES", num(data.services?.length), "in selected state"],
    [
      "SECTIONS",
      num(data.observations),
      num(data.tables?.length) + " distinct payloads",
    ],
    [
      "ISSUES",
      num(data.diagnostics?.length),
      num(data.crc_errors) + " CRC failures",
    ],
    [
      "SCAN",
      data.metrics ? Number(data.metrics.scan_ms).toFixed(1) + " ms" : "—",
      cancelling ? "Cancelling…" : busy ? "Analyzing…" : data.analysis_status === "cancelled" ? "Cancelled" : data.analysis_status === "failed" ? "Failed" : data.complete ? "Complete" : "No source",
    ],
  ];
  $("#stats").innerHTML = stats
    .map(
      ([label, value, sub]) =>
        `<div class="stat"><span>${label}</span><strong>${value}</strong><small>${sub}</small></div>`,
    )
    .join("");
  $("#scan").disabled = busy || !native || !!backendFailure;
  $("#browse").disabled = busy || !native || !!backendFailure;
  $("#scan").textContent = busy ? "Analyzing…" : "Analyze";
  $("#cancel-scan").hidden = !busy;
  $("#cancel-scan").disabled = cancelling || activeAnalyze === null || !!backendFailure;
  $("#cancel-scan").textContent = cancelling ? "Cancelling…" : "Cancel";
  $("#cancel-scan").setAttribute("aria-busy", String(cancelling));
  $("#source").disabled = busy;
  $("#standards").disabled = busy;
  $("#extra-pids").disabled = busy;
  $("#sidebar").innerHTML = [
    "All tables",
    ...tableFamilies(),
    "Private / other",
  ]
    .map((t) => {
      const count = (data.tables || []).filter(
        (r) =>
          t === "All tables" ||
          (t === "Private / other" ? isOtherTable(r) : r.name === t),
      ).length;
      return `<button class="nav ${filter === (t === "All tables" ? "" : t) ? "active" : ""}" data-filter="${esc(t)}" ${tip(t)}><span class="table-icon" aria-hidden="true">${t === "All tables" ? "▦" : "◇"}</span><span class="family-label">${esc(tableLabel(t))}</span><span class="count">${num(count)}</span></button>`;
    })
    .join("");
  $("#sidebar")
    .querySelectorAll("button")
    .forEach(
      (el) =>
        (el.onclick = () => {
          filter = el.dataset.filter === "All tables" ? "" : el.dataset.filter;
          changeTab("Tables");
          page = 0;
          render();
          [...$("#sidebar").querySelectorAll("button")].find((button) => button.dataset.filter === el.dataset.filter)?.focus();
        }),
    );
  $("#extension").innerHTML =
    `<div class="panel-title">DESCRIPTOR EXTENSION</div><strong>${esc(data.extension_id || "No extension reported")}</strong><p>Schema extensions use their declared scope. Native decoding follows the table context; raw evidence is retained.</p>`;
  $("#tabs").innerHTML = ["Services", "Tables", "EPG", "Issues", "Changes"]
    .map(
      (t) =>
        `<button role="tab" aria-selected="${tab === t}" tabindex="${tab === t ? 0 : -1}" class="${tab === t ? "active" : ""}" data-tab="${t}" ${tip(t)}>${t}${t === "Issues" && data.diagnostics?.length ? ` <span class="tab-count">${num(data.diagnostics.length)}</span>` : ""}</button>`,
    )
    .join("");
  $("#tabs")
    .querySelectorAll("button")
    .forEach((el) => {
      el.onclick = () => {
        changeTab(el.dataset.tab);
        page = 0;
        render();
        $('#tabs [aria-selected="true"]').focus();
      };
      el.onkeydown = (e) => {
        if (["ArrowLeft", "ArrowRight"].includes(e.key)) {
          e.preventDefault();
          const buttons = [...$("#tabs").children];
          const next =
            buttons[
              (buttons.indexOf(el) + (e.key === "ArrowRight" ? 1 : buttons.length - 1)) % buttons.length
            ];
          next.click();
          $('#tabs [aria-selected="true"]').focus();
        }
      };
    });
  $("#search").placeholder =
    tab === "Services"
      ? "Search services, providers, SID…"
      : tab === "Tables"
        ? "Search table, PID, version…"
        : tab === "EPG"
          ? "Search programmes, SID, start time…"
          : "Search issue code or evidence…";
  $("#snapshot-state").textContent =
    data.analysis_status === "cancelled"
      ? "CANCELLED · SOURCE UNCHANGED"
      : data.selected_packet != null
      ? "SNAPSHOT @ " + num(data.selected_packet)
      : (reportedStandards(data)
          ? reportedStandards(data) + " · "
          : "LOCAL · ") + "SOURCE READ-ONLY";
  renderList();
  renderInspector();
  renderTimeline();
  disableBackendActions();
  if (data.observations && !firstPaint) {
    firstPaint = true;
    requestAnimationFrame(() =>
      requestAnimationFrame(() =>
        invoke("milestone", { event: "first_paint" }).catch(() => {}),
      ),
    );
  }
  if (data.complete && !completePaint) {
    completePaint = true;
    requestAnimationFrame(() =>
      requestAnimationFrame(() =>
        invoke("milestone", { event: "complete_paint" }).catch(() => {}),
      ),
    );
  }
}
function recordRows() {
  let rows =
    tab === "Services"
      ? data.services || []
      : tab === "Tables"
        ? (data.tables || []).filter(tableMatches)
        : tab === "EPG"
          ? data.events || []
          : data.diagnostics || [];
  if (search.trim()) {
    const needle = search.trim().toLowerCase();
    rows = rows.filter((row) =>
      (
        JSON.stringify(row) +
        " " +
        hex(row.pid) +
        " " +
        hex(row.id) +
        " " +
        hex(row.pmt_pid)
      )
        .toLowerCase()
        .includes(needle),
    );
  }
  return rows;
}
function rowIdentity(r, index) {
  return tab === "Services"
    ? "service:" + (r.key ?? [r.onid, r.ts_id, r.id].join(":"))
    : tab === "EPG"
      ? "event:" + r.source_id + ":" + r.id
      : tab === "Issues"
        ? "issue:" + r.id + ":" + r.code + ":" + r.packet + ":" + index
        : r.id;
}
function renderList() {
  $(".searchbar").hidden = tab === "Changes";
  $("#list").setAttribute("role", tab === "Changes" ? "region" : "listbox");
  $("#list").setAttribute("aria-label", tab === "Changes" ? "Snapshot changes" : "Stream records");
  if (tab === "Changes") {
    renderComparison();
    return;
  }
  const rows = recordRows();
  page = Math.max(0, Math.min(page, Math.ceil(rows.length / PAGE_SIZE) - 1));
  const start = page * PAGE_SIZE;
  $("#result-count").textContent = num(rows.length);
  $("#page-label").textContent = rows.length
    ? `${num(start + 1)}–${num(Math.min(start + PAGE_SIZE, rows.length))} of ${num(rows.length)}`
    : "0 records";
  $("#prev").disabled = page === 0;
  $("#next").disabled = start + PAGE_SIZE >= rows.length;
  $("#service-head").innerHTML =
    tab === "Services"
      ? `<div class="service-head"><span ${tip("LCN")}>LCN</span><span>SERVICE / PROVIDER</span><span ${tip("PMT")}>PMT PID</span><span>GROUP</span></div>`
      : "";
  $("#list").innerHTML = rows
    .slice(start, start + PAGE_SIZE)
    .map((r, i) => {
      const key = rowIdentity(r, start + i);
      let body = "";
      if (tab === "Services")
        body = `<span class="lcn">${r.logical_channel_number ?? "—"}</span><div class="record-name"><strong>${esc(r.name || "Unnamed service")}</strong><small>${esc(r.provider || "No provider")} <span class="muted">· SID ${hex(r.id)}</span></small></div><span class="numeric">${hex(r.pmt_pid)}</span><span class="group">${esc(r.group)}</span>`;
      if (tab === "Tables")
        body = `<span class="table-kind" ${tip(r.name)}>${esc(tableLabel(r.name))}</span><div class="record-name"><strong>PID <span class="numeric">${hex(r.pid)}</span></strong><small>Version ${r.version} · section ${r.section}/${r.last_section} · ${num(r.bytes)} B</small></div><span class="numeric muted">${num(r.count)}×</span><span class="${r.valid ? "ok" : "bad"}" title="${r.valid ? "Valid section" : "Invalid section"}">${r.valid ? "●" : "⚠"}</span>`;
      if (tab === "EPG")
        body = `<div class="record-name"><strong>${esc(r.title)}</strong><small>SID ${hex(r.service_id)} · ${esc(r.start)} UTC · ${num(r.duration_seconds / 60)} min</small></div><span class="muted numeric">${hex(r.id)}</span>`;
      if (tab === "Issues")
        body = `<span class="bad">⚠</span><div class="record-name"><strong>${esc(r.code)}</strong><small>${esc(r.detail)}</small><small>${r.aggregate ? "Aggregate across monitored SI PIDs" : "PID " + hex(r.pid) + " · packet " + num(r.packet)} · ${num(r.count)} observations</small></div>`;
      return `<div role="option" aria-selected="${selectedKey === key}" tabindex="${selectedKey === key || (!selectedKey && i === 0) ? 0 : -1}" class="record ${tab.toLowerCase()} ${selectedKey === key ? "selected" : ""}" data-row="${i}" data-key="${esc(key)}">${body}</div>`;
    })
    .join("");
  if (!rows.length)
    $("#list").innerHTML =
      `<div class="empty"><span class="empty-icon">${busy ? "◌" : data.source ? "⌕" : "▦"}</span><h3>${cancelling ? "Cancelling analysis…" : busy ? "Reading transport stream…" : data.analysis_status === "cancelled" ? "Analysis cancelled" : data.analysis_status === "failed" ? "Analysis failed" : !data.source ? "Explore your transport stream" : search ? "No matching records" : "No " + tab.toLowerCase() + " in this state"}</h3><p>${cancelling ? "Waiting for the engine to stop. The source file stays unchanged." : ["cancelled", "failed"].includes(data.analysis_status) ? "Partial results were cleared. Analyze again when you are ready." : !data.source ? "Open a TS file to inspect PSI/SI tables, decoded fields and their original bytes." : search ? "Try another name, decimal identifier or hexadecimal value." : ["Services", "EPG"].includes(tab) && (data.tables || []).length ? "This view shows derived " + (tab === "Services" ? "services" : "programme events") + ". Open Tables for native signalling fields and raw evidence; an empty projection does not mean decoding failed." : "Choose another table family or packet snapshot."}</p></div>`;
  const visible = rows.slice(start, start + PAGE_SIZE);
  $("#list")
    .querySelectorAll("[data-row]")
    .forEach((el) => {
      const activate = () => {
        const r = visible[Number(el.dataset.row)];
        if (tab === "Issues" && r.aggregate) {
          selectionReset();
          aggregateDiagnostic = r;
          selectedKey = el.dataset.key;
          renderInspector();
          renderList();
          notice("Aggregate diagnostic · packet locations are not indexed");
          return;
        }
        inspect(
          tab === "Services" || tab === "EPG" ? r.source_id : r.id,
          tab === "Services" ? r.id : -1,
          el.dataset.key,
        );
      };
      el.onclick = activate;
      el.onkeydown = (e) => {
        const options = [...$("#list").querySelectorAll('[role="option"]')];
        const index = options.indexOf(el);
        if (["ArrowDown", "ArrowUp", "Home", "End"].includes(e.key)) {
          e.preventDefault();
          const target =
            options[
              e.key === "Home"
                ? 0
                : e.key === "End"
                  ? options.length - 1
                  : Math.max(
                      0,
                      Math.min(
                        options.length - 1,
                        index + (e.key === "ArrowDown" ? 1 : -1),
                      ),
                    )
            ];
          options.forEach((x) => (x.tabIndex = -1));
          target.tabIndex = 0;
          target.focus();
        }
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          activate();
          requestAnimationFrame(() =>
            $('#list [aria-selected="true"]')?.focus(),
          );
        }
      };
    });
  if (!$('#list [tabindex="0"]'))
    $('#list [role="option"]')?.setAttribute("tabindex", "0");
}
function changeTab(next) {
  if (next === tab) return;
  let restoreInspection = false;
  if (next === "Changes") {
    savedWorkspace = { selected, selectedService, selectedKey, detail, detailError,
      aggregateDiagnostic, treeSearch, openNodes: new Set(openNodes), view, inspectionEvidence, wasLoading: loadingDetail };
    ++inspectEpoch;
    loadingDetail = false;
    detail = {};
    detailError = "";
    aggregateDiagnostic = null;
    comparisonEvidence = "";
    if (comparison.from === null && data.complete) {
      comparison.to = data.selected_packet ?? Math.max(0, data.packets - 1);
      comparison.from = data.history?.find((entry) => entry.last_packet < comparison.to)?.last_packet ?? 0;
    }
  } else if (tab === "Changes") {
    ++inspectEpoch;
    loadingDetail = false;
    if (savedWorkspace) {
      restoreInspection = savedWorkspace.wasLoading;
      ({ selected, selectedService, selectedKey, detail, detailError,
        aggregateDiagnostic, treeSearch, openNodes, view, inspectionEvidence } = savedWorkspace);
      savedWorkspace = null;
    }
    comparisonEvidence = "";
  }
  tab = next;
  if (restoreInspection && selected && !backendFailure) inspect(selected, selectedService, selectedKey);
}
function comparisonPresets() {
  const current = data.selected_packet ?? Math.max(0, data.packets - 1);
  return `<option value="">Choose current / history…</option><option value="${current}">Current snapshot · packet ${num(current)}</option><option value="0">Start · packet 0</option><option value="${Math.max(0, data.packets - 1)}">Latest · packet ${num(data.packets - 1)}</option>` +
    (data.history || []).map((entry) => `<option value="${entry.last_packet}">${esc(entry.label)} · through packet ${num(entry.last_packet)}</option>`).join("");
}
function invalidateComparison() {
  ++comparison.epoch;
  comparison.loading = false;
  comparison.result = null;
  comparison.error = "";
  ++inspectEpoch;
  detail = {};
  detailError = "";
  loadingDetail = false;
  comparisonEvidence = "";
  renderInspector();
  renderComparisonResults();
}
function renderComparison() {
  const disabled = busy || backendFailure || !data.complete;
  $("#service-head").innerHTML = `<div class="comparison-controls"><div class="comparison-source" title="${esc(data.source || "No source")}">${esc(data.source || "Analyze a stream to compare its observed states")}</div><div class="comparison-endpoints">${[["from", "A · before"], ["to", "B · after"]].map(([side, label]) => `<div><label for="compare-${side}">${label}</label><input id="compare-${side}" type="number" min="0" max="${Math.max(0, (data.packets || 1) - 1)}" step="1" value="${comparison[side] ?? ""}" aria-label="${label} packet cutoff" ${disabled ? "disabled" : ""}><select data-preset="${side}" aria-label="Choose snapshot ${side === "from" ? "A" : "B"} from history" ${disabled ? "disabled" : ""}>${comparisonPresets()}</select></div>`).join("")}</div><div class="comparison-actions"><button id="swap-comparison" class="btn small" ${disabled ? "disabled" : ""} title="Reverse the comparison direction">Swap A / B</button><label class="sr-only" for="compare-kind">Changed record type</label><select id="compare-kind" ${disabled ? "disabled" : ""}>${[["all", "All changes"], ["tables", "Tables"], ["services", "Services"], ["events", "Events"]].map(([value, label]) => `<option value="${value}" ${comparison.kind === value ? "selected" : ""}>${label}</option>`).join("")}</select><button id="run-comparison" class="btn primary" ${disabled || comparison.loading ? "disabled" : ""}>${comparison.loading ? "Comparing…" : "Compare A → B"}</button></div><p class="meta comparison-help">Inclusive packet cutoffs within this source. Only observed valid current state is compared; missing observations do not prove a broadcast removal.</p></div>`;
  for (const side of ["from", "to"]) {
    $("#compare-" + side).oninput = (event) => {
      comparison[side] = event.target.value === "" ? null : Number(event.target.value);
      invalidateComparison();
    };
    $("#compare-" + side).onkeydown = (event) => {
      if (event.key === "Enter") runComparison();
    };
  }
  $("#service-head").querySelectorAll("[data-preset]").forEach((el) => {
    el.onchange = () => {
      if (el.value === "") return;
      comparison[el.dataset.preset] = Number(el.value);
      $("#compare-" + el.dataset.preset).value = el.value;
      invalidateComparison();
    };
  });
  $("#swap-comparison").onclick = () => {
    [comparison.from, comparison.to] = [comparison.to, comparison.from];
    invalidateComparison();
    renderComparison();
    $("#swap-comparison").focus();
  };
  $("#compare-kind").onchange = (event) => {
    comparison.kind = event.target.value;
    invalidateComparison();
  };
  $("#run-comparison").onclick = () => runComparison();
  renderComparisonResults();
}
function comparisonValue(value) {
  if (value == null) return "—";
  return typeof value === "object" ? JSON.stringify(value) : String(value);
}
function comparisonSide(side, label, change, index) {
  if (!side) return `<div class="comparison-side absent"><h4>${label}</h4><p>No observed record in this state</p></div>`;
  const value = side.value;
  const fields = [...new Set([...(change.changed_fields || []).filter((field) => field !== "payload"), ...(change.kind === "services" ? ["name", "provider", "pmt_pid"] : change.kind === "events" ? ["title", "start", "duration_seconds"] : ["name", "version", "bytes"])])].filter((field) => change.changed_fields?.includes(field) || Object.prototype.hasOwnProperty.call(value, field));
  return `<div class="comparison-side"><h4>${label} <span>packet ${num(side.at_packet)}</span></h4><dl>${fields.map((field) => `<div class="${change.changed_fields?.includes(field) ? "changed-value" : "context-value"}"><dt>${esc(field)}</dt><dd>${esc(Object.prototype.hasOwnProperty.call(value, field) ? fieldValue(field, typeof value[field] === "object" ? comparisonValue(value[field]) : value[field]) : "Not observed in this snapshot")}</dd></div>`).join("")}</dl><div class="comparison-evidence"><span class="meta">Source evidence</span>${(side.evidence || []).map((evidence, evidenceIndex) => `<button class="btn small" aria-pressed="${selectedKey === "comparison:" + side.at_packet + ":" + change.kind + ":" + change.key + ":" + evidenceIndex}" data-evidence-key="${esc("comparison:" + side.at_packet + ":" + change.kind + ":" + change.key + ":" + evidenceIndex)}" data-comparison-evidence="${index}:${label[0]}:${evidenceIndex}" ${backendFailure ? "disabled" : ""} title="Inspect ${esc(evidence.id)} at packet ${side.at_packet}">PID ${hex(evidence.pid)} · v${evidence.version} · section ${evidence.section}</button>`).join("")}</div></div>`;
}
function renderComparisonResults() {
  const result = comparison.result;
  $("#prev").disabled = !result || result.offset === 0 || comparison.loading || !!backendFailure;
  $("#next").disabled = !result || result.next_offset == null || comparison.loading || !!backendFailure;
  $("#run-comparison")?.toggleAttribute("disabled", comparison.loading || busy || !!backendFailure || !data.complete);
  if ($("#run-comparison")) $("#run-comparison").textContent = comparison.loading ? "Comparing…" : "Compare A → B";
  $("#page-label").textContent = result ? result.total_changes ? `${num(result.offset + 1)}–${num(Math.min(result.offset + result.changes.length, result.total_changes))} of ${num(result.total_changes)} changes` : "0 changes" : "Snapshot comparison";
  if (!result) {
    $("#list").innerHTML = `<div class="empty"><span class="empty-icon">${comparison.error ? "⚠" : "⇄"}</span><h3>${comparison.loading ? "Comparing observed states…" : comparison.error ? "Unable to compare" : "What changed between versions?"}</h3><p>${esc(comparison.error || "Choose A and B from the captured version history or the current snapshot, then compare. Original source bytes remain unchanged.")}</p></div>`;
    return;
  }
  const totals = Object.values(result.summary).reduce((counts, item) => ({ added: counts.added + item.added, removed: counts.removed + item.removed, changed: counts.changed + item.changed }), { added: 0, removed: 0, changed: 0 });
  $("#list").innerHTML = `<div class="comparison-summary"><strong>A ${num(result.from_packet)} → B ${num(result.to_packet)}</strong><span>All record types: <span class="ok">${num(totals.added)} added</span> · <span class="bad">${num(totals.removed)} removed</span> · ${num(totals.changed)} changed</span><span class="meta">${result.kind === "all" ? "Showing all kinds" : "Showing " + esc(result.kind)} · ${num(result.total_changes)} changes</span></div>${result.changes.length ? result.changes.map((change, index) => {
    const identity = change.identity, value = change.after?.value || change.before?.value || {};
    const title = change.kind === "services" ? (value.name || "Unnamed service") + " · SID " + hex(identity.service_id)
      : change.kind === "events" ? (value.title || "Untitled event") + " · event " + hex(identity.event_id)
        : (value.name || "Table") + " · PID " + hex(identity.pid) + " · section " + identity.section;
    return `<article class="comparison-change"><header><span class="change-badge ${change.change}">${esc(change.change)}</span><span class="meta">${esc(change.kind)}</span><h3>${esc(title)}</h3></header>${change.changed_fields?.length ? `<p class="changed-fields">Changed: ${change.changed_fields.map(esc).join(", ")}</p>${change.changed_fields.includes("payload") ? '<p class="meta">Raw section payload differs. Open source evidence to inspect its bytes.</p>' : ""}` : ""}<div class="comparison-sides">${comparisonSide(change.before, "A · before", change, index)}${comparisonSide(change.after, "B · after", change, index)}</div></article>`;
  }).join("") : '<div class="empty"><h3>No observed changes</h3><p>The selected record type is unchanged between these cutoffs. Repeated identical sections alone are not changes.</p></div>'}`;
  $("#list").querySelectorAll("[data-comparison-evidence]").forEach((el) => {
    el.onclick = () => {
      const [index, letter, evidenceIndex] = el.dataset.comparisonEvidence.split(":");
      const change = result.changes[Number(index)], side = letter === "A" ? change.before : change.after;
      const evidence = side.evidence[Number(evidenceIndex)];
      inspect(evidence.id, change.kind === "services" && Number(evidenceIndex) === 0 ? change.identity.service_id : -1, el.dataset.evidenceKey,
        { atPacket: side.at_packet, label: "Comparison " + letter + " · packet " + num(side.at_packet) });
    };
  });
}
async function runComparison(offset = 0) {
  if (busy || backendFailure || !data.complete) return;
  for (const side of ["from", "to"]) {
    if (!Number.isSafeInteger(comparison[side]) || comparison[side] < 0 || comparison[side] >= data.packets) {
      comparison.error = "Choose a whole packet number between 0 and " + num(data.packets - 1) + " for " + (side === "from" ? "A" : "B") + ".";
      comparison.result = null;
      renderComparisonResults();
      $("#compare-" + side).focus();
      return;
    }
  }
  const epoch = ++comparison.epoch, revision = data.revision;
  comparison.loading = true;
  comparison.error = "";
  comparison.result = null;
  renderComparisonResults();
  try {
    const result = await call("diff_snapshots", { from_packet: comparison.from, to_packet: comparison.to,
      kind: comparison.kind, offset, limit: PAGE_SIZE });
    if (epoch !== comparison.epoch || revision !== data.revision) return;
    comparison.result = result;
  } catch (error) {
    if (epoch !== comparison.epoch) return;
    comparison.error = String(error);
  } finally {
    if (epoch === comparison.epoch) {
      comparison.loading = false;
      if (tab === "Changes") renderComparisonResults();
    }
  }
}
function fieldValue(key, value) {
  if (value === null) return "—";
  if (typeof value === "boolean") return value ? "true" : "false";
  if (typeof value === "number") {
    const width = /pds|private_data_specifier/.test(key)
      ? 8
      : /tag|table_id|type$/.test(key)
        ? 2
        : /(^id$|_id$|pid$|^pid$|onid|ts_id|^extension$)/.test(key)
          ? 4
          : 0;
    return width ? hex(value, width) + " (" + num(value) + ")" : num(value);
  }
  return String(value);
}
function leaf(label, value, key = label) {
  return { label, value: fieldValue(key, value) };
}
function objectNodes(object) {
  return Object.entries(object || {})
    .filter(([, value]) => value !== undefined)
    .map(([key, value]) =>
      value && typeof value === "object"
        ? {
            label: key,
            children: Array.isArray(value)
              ? value.map((v, i) =>
                  typeof v === "object"
                    ? { label: `[${i}]`, children: objectNodes(v) }
                    : leaf(`[${i}]`, v, key),
                )
              : objectNodes(value),
          }
        : leaf(key, value),
    );
}
function descriptorNode(d, index) {
  return {
    label: d.name || "opaque_descriptor",
    tone: d.malformed ? "bad" : d.extension ? "private" : "",
    value: hex(d.tag, 2) + " · " + d.length + " B · @" + d.offset,
    children: [
      leaf("descriptor_tag", d.tag, "tag"),
      leaf("descriptor_length", d.length),
      leaf("section_byte_offset", d.offset),
      leaf("private_data_specifier", d.pds),
      ...(d.extension ? [leaf("extension", d.extension)] : []),
      ...objectNodes(d.fields),
      ...(d.native
        ? [
            {
              id: "native",
              label: "Native decoded descriptor",
              children: [nativeNode(d.native)],
            },
          ]
        : []),
      leaf("raw_bytes", d.raw),
      ...(d.malformed
        ? [
            leaf(
              "validation",
              "Malformed descriptor: declared length exceeds loop",
            ),
          ]
        : []),
    ],
    id: String(d.offset ?? index),
  };
}
function nativeNode(node) {
  return {
    label: node.name,
    children: [
      ...Object.entries(node.attributes || {}).map(([label, value]) => ({
        label,
        value,
      })),
      ...(node.children || []).map(nativeNode),
      ...(node.text ? [{ label: "text", value: node.text }] : []),
    ],
  };
}
function nativeXmlTree() {
  if (detail.native_table)
    return {
      id: "native",
      label: "TSDuck decoded structure",
      value: detail.native_table_complete
        ? "complete table"
        : "section / partial table",
      children: [nativeNode(detail.native_table)],
    };
  if (!detail.tsduck_xml) return null;
  const document = new DOMParser().parseFromString(
    detail.tsduck_xml,
    "application/xml",
  );
  if (document.querySelector("parsererror"))
    return {
      id: "native",
      label: "TSDuck decoded structure",
      children: [
        leaf(
          "status",
          "XML could not be parsed; original is available in the XML view.",
        ),
      ],
    };
  const convert = (element) => ({
    label: element.tagName,
    children: [
      ...Array.from(element.attributes).map((attribute) => ({
        label: attribute.name,
        value: attribute.value,
      })),
      ...Array.from(element.children).map(convert),
      ...Array.from(element.childNodes)
        .filter((node) => node.nodeType === 3 && node.textContent.trim())
        .map((node) => ({ label: "value", value: node.textContent.trim() })),
    ],
  });
  return {
    id: "native",
    label: "TSDuck decoded structure",
    value: "native semantic fields",
    children: Array.from(document.documentElement?.children || []).map(convert),
  };
}
function sectionTree() {
  const descriptors = detail.descriptors || [];
  const services = detail.services || [];
  const headerKeys = [
    "pid",
    "table_id",
    "extension",
    "version",
    "section",
    "last_section",
    "bytes",
    "valid",
    "current",
    "standards",
    "standard",
    "standard_context",
    "standards_context",
    "native_decode_status",
    "native_table_complete",
    "native_table_at_packet",
  ];
  const header = headerKeys
    .filter((k) => detail[k] !== undefined)
    .map((k) => leaf(k, detail[k]));
  const children = [
    { id: "header", label: "Section header", children: header },
    {
      id: "fields",
      label: "Decoded fields",
      children: objectNodes(detail.fields),
    },
  ];
  if (services.length)
    children.push({
      id: "services",
      label: "Services",
      value:
        selectedService >= 0
          ? "1 of " + num(services.length)
          : num(services.length),
      children: services
        .filter((s) => selectedService < 0 || s.id === selectedService)
        .map((s) => ({
          id: String(s.id),
          label: s.name || "Service",
          value: "SID " + hex(s.id),
          children: [
            {
              id: "fields",
              label: "Service fields",
              children: objectNodes(
                Object.fromEntries(
                  Object.entries(s).filter(([k]) => k !== "source_id"),
                ),
              ),
            },
            {
              id: "descriptors",
              label: "Descriptors",
              children: descriptors
                .filter((d) => d.service_id === s.id)
                .map(descriptorNode),
            },
          ],
        })),
    });
  if (detail.events?.length)
    children.push({
      id: "events",
      label: "Events",
      value: num(detail.events.length),
      children: detail.events.map((e) => ({
        label: e.title || "Event",
        value: hex(e.id),
        children: objectNodes(e),
      })),
    });
  const unowned = services.length
    ? descriptors.filter((d) => !services.some((s) => s.id === d.service_id))
    : descriptors;
  if (unowned.length)
    children.push({
      id: "descriptors",
      label: detail.events?.length
        ? "Section descriptors (event ownership unavailable)"
        : "Descriptors",
      value: num(unowned.length),
      children: unowned.map(descriptorNode),
    });
  const nativeTree = nativeXmlTree();
  if (nativeTree) children.push(nativeTree);
  if (detail.issues?.length)
    children.push({
      id: "issues",
      label: "Validation issues",
      tone: "bad",
      children: objectNodes(detail.issues),
    });
  children.push({
    id: "evidence",
    label: "Source evidence",
    children: objectNodes({
      first_packet: detail.first_packet,
      last_packet: detail.last_packet,
      first_file_offset: detail.first_file_offset,
      offset_note: detail.offset_note,
      native_table_at_packet: detail.native_table_at_packet,
      inspection_scope: detail.inspection_scope,
      occurrence_count: detail.occurrences?.length,
      ...(detail.occurrences?.length
        ? {
            occurrences: detail.occurrences.slice(0, 500),
            ...(detail.occurrences.length > 500
              ? {
                  display_note:
                    "First 500 occurrence packets shown. Full occurrence list is available through the Agent API.",
                }
              : {}),
          }
        : {}),
    }),
  });
  return {
    id: "section",
    label: detail.name + " section",
    value: "v" + detail.version + " · " + (detail.valid ? "valid" : "invalid"),
    children,
  };
}
function nodeMatches(node, needle) {
  return (
    (node.label + " " + (node.value ?? "")).toLowerCase().includes(needle) ||
    node.children?.some((n) => nodeMatches(n, needle))
  );
}
function highlightedTreeText(value) {
  const text = String(value ?? "");
  const needle = treeSearch.trim().toLowerCase();
  if (!needle) return esc(text);
  let result = "",
    start = 0,
    index;
  while ((index = text.toLowerCase().indexOf(needle, start)) >= 0) {
    result +=
      esc(text.slice(start, index)) +
      "<mark>" +
      esc(text.slice(index, index + needle.length)) +
      "</mark>";
    start = index + needle.length;
  }
  return result + esc(text.slice(start));
}
let treeNodesRendered = 0;
function drawNode(node, parent = "", index = 0, ancestorMatch = false, level = 1) {
  const path = parent ? parent + "/" + (node.id ?? index) : node.id;
  const needle = treeSearch.trim().toLowerCase();
  const selfMatch = (node.label + " " + (node.value ?? ""))
    .toLowerCase()
    .includes(needle);
  if (needle && !ancestorMatch && !nodeMatches(node, needle)) return "";
  if (++treeNodesRendered > 2500) return "";
  const accessible = `role="treeitem" tabindex="-1" aria-level="${level}" data-node-path="${esc(path)}" aria-label="${esc(node.label + (node.value !== undefined ? ": " + node.value : ""))}"`;
  const label = `<span class="node-label ${node.tone || ""}" title="${esc(fieldHelp[node.label] || node.label)}">${highlightedTreeText(node.label)}</span>${node.value !== undefined ? `<span class="node-value">${highlightedTreeText(node.value)}</span>` : ""}`;
  if (!node.children)
    return `<div class="tree-leaf" ${accessible}>${label}</div>`;
  const opened = !!needle || openNodes.has(path);
  return `<div class="tree-node" ${accessible} data-path="${esc(path)}" aria-expanded="${opened}"><div class="tree-row">${label}<span class="node-count">${num(node.children.length)}</span></div><div class="tree-children" role="group" ${opened ? "" : "hidden"}>${node.children.length ? node.children.map((child, i) => drawNode(child, path, i, ancestorMatch || (!!needle && selfMatch), level + 1)).join("") : '<div class="tree-empty">No decoded fields</div>'}</div></div>`;
}
function setTreeExpanded(node, expanded) {
  node.setAttribute("aria-expanded", String(expanded));
  node.querySelector(":scope > .tree-children").hidden = !expanded;
  if (!treeSearch) {
    if (expanded) openNodes.add(node.dataset.path);
    else openNodes.delete(node.dataset.path);
  }
}
function focusTreeItem(node) {
  if (!node) return;
  node.focus({ preventScroll: true });
  (node.querySelector(":scope > .tree-row") || node).scrollIntoView({ block: "nearest", inline: "nearest" });
}
function renderTree() {
  const area = $("#tree-area");
  if (!area) return;
  const previousPath = area.querySelector('[tabindex="0"]')?.dataset.nodePath;
  const hadFocus = area.contains(document.activeElement);
  treeNodesRendered = 0;
  area.innerHTML =
    drawNode(sectionTree()) ||
    '<p class="tree-empty">No matching fields or values.</p>';
  if (treeNodesRendered > 2500)
    area.insertAdjacentHTML(
      "beforeend",
      '<p class="tree-empty">Tree display limited to 2,500 nodes. Narrow the field search; full evidence remains available in raw/XML views and the Agent API.</p>',
    );
  const visibleItems = () => [...area.querySelectorAll('[role="treeitem"]')]
    .filter((el) => el.getClientRects().length && !el.closest("[hidden]"));
  function setEntry(target, focus = false) {
    area.querySelectorAll('[role="treeitem"]').forEach((el) => {
      el.tabIndex = el === target ? 0 : -1;
    });
    if (focus) focusTreeItem(target);
  }
  const items = visibleItems();
  setEntry(items.find((el) => el.dataset.nodePath === previousPath) || items[0], hadFocus);
  // focusin bubbles, but onfocusin is not a supported handler property in
  // every engine. Replace the listener on rerender instead of accumulating it.
  if (area.treeFocusHandler) area.removeEventListener("focusin", area.treeFocusHandler);
  area.treeFocusHandler = (event) => {
    if (event.target.matches('[role="treeitem"]')) setEntry(event.target);
  };
  area.addEventListener("focusin", area.treeFocusHandler);
  area.onclick = (event) => {
    const node = event.target.closest('[role="treeitem"]');
    if (!node || !area.contains(node)) return;
    setEntry(node, true);
    if (node.classList.contains("tree-node") && event.target.closest(".tree-row") === node.querySelector(":scope > .tree-row"))
      setTreeExpanded(node, node.getAttribute("aria-expanded") !== "true");
  };
  let typed = "", typedAt = 0;
  area.onkeydown = (e) => {
    const target = e.target;
    if (e.key.length === 1 && e.key !== " " && !e.ctrlKey && !e.metaKey && !e.altKey) {
      const items = visibleItems();
      typed = Date.now() - typedAt < 700 ? typed + e.key.toLowerCase() : e.key.toLowerCase();
      typedAt = Date.now();
      const index = items.indexOf(target);
      const ordered = [...items.slice(index + 1), ...items.slice(0, index + 1)];
      const match = ordered.find((el) => el.getAttribute("aria-label").toLowerCase().startsWith(typed));
      if (match) { e.preventDefault(); focusTreeItem(match); }
      return;
    }
    if (
      ![
        "ArrowRight",
        "ArrowLeft",
        "ArrowUp",
        "ArrowDown",
        "Home",
        "End",
        "Enter",
        " ",
      ].includes(e.key)
    )
      return;
    const focusable = visibleItems();
    const index = focusable.indexOf(target);
    if (index < 0) return;
    e.preventDefault();
    const branch = target.classList.contains("tree-node");
    const expanded = target.getAttribute("aria-expanded") === "true";
    if (e.key === "Enter" || e.key === " ") {
      if (branch) setTreeExpanded(target, !expanded);
    } else if (e.key === "ArrowRight") {
      if (branch) {
        if (!expanded) setTreeExpanded(target, true);
        else focusTreeItem(target.querySelector(":scope > .tree-children > [role=treeitem]"));
      }
    } else if (e.key === "ArrowLeft") {
      if (branch && expanded) setTreeExpanded(target, false);
      else focusTreeItem(target.parentElement.closest('[role="treeitem"]'));
    } else {
      const next = e.key === "Home" ? 0 : e.key === "End" ? focusable.length - 1
        : Math.max(0, Math.min(focusable.length - 1, index + (e.key === "ArrowDown" ? 1 : -1)));
      focusTreeItem(focusable[next]);
    }
  };
}
function hexDump(raw) {
  const bytes = String(raw || "").match(/.{1,2}/g) || [];
  return Array.from({ length: Math.ceil(bytes.length / 16) }, (_, i) => {
    const row = bytes.slice(i * 16, i * 16 + 16);
    return (
      (i * 16).toString(16).toUpperCase().padStart(4, "0") +
      "  " +
      row.join(" ").padEnd(47, " ") +
      "  " +
      row
        .map((x) => {
          const c = parseInt(x, 16);
          return c >= 32 && c < 127 ? String.fromCharCode(c) : ".";
        })
        .join("")
    );
  }).join("\n");
}
function nativeReferences(node) {
  return node
    ? [
        ...(node.references || []),
        ...(node.children || []).flatMap(nativeReferences),
      ]
    : [];
}
function referencePanel() {
  const warnings = (detail.reference_warnings || [])
    .map((warning) => `<p class="bad">${esc(warning)}</p>`)
    .join("");
  const references = [
    ...(detail.references || []),
    ...nativeReferences(detail.native_table),
    ...(detail.descriptors || []).flatMap((d) => [
      ...(d.references || []),
      ...nativeReferences(d.native),
    ]),
  ];
  const seen = new Set();
  const valid = references.filter((ref) => {
    try {
      const url = new URL(ref.url);
      if (
        url.protocol !== "https:" ||
        url.username ||
        url.password ||
        seen.has(url.href)
      )
        return false;
      seen.add(url.href);
      return true;
    } catch {
      return false;
    }
  });
  if (!valid.length)
    return `<div class="empty"><h3>No mapped reference</h3><p>No verified specification link is mapped to this selection yet. Raw evidence and native decoding remain available.</p>${warnings}</div>`;
  return (
    '<div class="references"><p class="meta">Official specification references. Mappings are standard-level, not a claim of clause-level conformance. Access restrictions and revision differences may apply.</p>' +
    warnings +
    valid
      .map(
        (ref) =>
          `<section class="reference"><a data-reference href="${esc(ref.url)}" target="_blank" rel="noopener noreferrer">${esc(ref.title || ref.id || "Specification")} <span class="external-label">Open</span></a><p class="meta">${esc(ref.version || "")} · ${esc(ref.scope || "standard-level")}</p>${ref.access ? `<p>${esc(ref.access)}</p>` : ""}${ref.notes ? `<p>${esc(ref.notes)}</p>` : ""}<textarea class="reference-url" readonly rows="3" spellcheck="false" aria-label="Specification URL">${esc(ref.url)}</textarea><button class="btn small" data-copy-reference="${esc(ref.url)}">Copy URL</button><p class="reference-status" role="status" aria-live="polite" hidden></p></section>`,
      )
      .join("") +
    "</div>"
  );
}
function renderInspector() {
  const panel = $("#inspector");
  if (aggregateDiagnostic) {
    panel.innerHTML = `<div class="panel-title">TRANSPORT DIAGNOSTIC <span class="bad">AGGREGATE</span></div><div class="empty"><span class="empty-icon bad">⚠</span><h3>${esc(aggregateDiagnostic.code)}</h3><p>${esc(aggregateDiagnostic.detail)}</p><p>${num(aggregateDiagnostic.count)} observations across monitored SI PIDs. Individual packet locations are not indexed.</p></div>`;
    return;
  }
  if (loadingDetail || detailError || !detail.name) {
    panel.innerHTML = `<div class="panel-title">SECTION INSPECTOR</div>${comparisonEvidence ? `<p class="comparison-context">${esc(comparisonEvidence)} · main snapshot unchanged</p>` : ""}<div class="empty"><span class="empty-icon">${loadingDetail ? "◌" : detailError ? "⚠" : "⌘"}</span><h3>${loadingDetail ? "Loading section…" : detailError ? "Unable to inspect section" : "Inspect the signal"}</h3><p>${esc(detailError || "Select a service, table, programme or issue to explore its source section.")}</p>${detailError && !backendFailure ? '<button class="btn" id="retry-inspect">Retry</button>' : ""}</div>`;
    $("#retry-inspect")?.addEventListener("click", () =>
      inspect(selected, selectedService, selectedKey, inspectionEvidence),
    );
    return;
  }
  const nativeWarnings = Array.isArray(detail.native_decode_warnings)
    ? detail.native_decode_warnings.filter((warning) => typeof warning === "string")
    : [];
  if (detail.native_xml_guarded)
    nativeWarnings.push("Guarded SDK XML: " + (detail.native_xml_guard_reason || "ambiguous descriptor interpretation") + ". Original wire bytes remain authoritative in Hex bytes.");
  const xmlLabel = detail.native_xml_guarded ? "Guarded SDK XML" : "TSDuck XML";
  panel.innerHTML = `<div class="panel-title">SECTION INSPECTOR <span class="${detail.valid ? "ok" : "bad"}">${detail.valid ? "VALID" : "INVALID"}</span></div>${comparisonEvidence ? `<p class="comparison-context">${esc(comparisonEvidence)} · main snapshot unchanged</p>` : ""}<div class="inspector-heading"><h2 ${tip(detail.name)}>${esc(tableLabel(detail.name))} <span>/ v${detail.version}</span></h2><span class="numeric">${hex(detail.pid)} PID</span></div><p class="meta">Section ${detail.section}/${detail.last_section} · ${num(detail.bytes)} bytes · ${num(detail.count)} observations${reportedStandards(detail) ? " · " + esc(reportedStandards(detail)) : ""}${selectedService >= 0 ? " · SID " + hex(selectedService) : ""}</p>${detail.native_table_at_packet != null ? `<p class="meta native-evidence" id="native-assembly-evidence">Native assembly cutoff: packet ${num(detail.native_table_at_packet)}${detail.native_decode_status ? " · " + esc(detail.native_decode_status) : ""}</p>` : ""}${nativeWarnings.length ? `<p class="meta" id="native-decode-warnings" role="note"><strong class="bad">Decoder note</strong><br><span class="bad">${nativeWarnings.map(esc).join("<br>")}</span></p>` : ""}<div class="view-tabs" role="group" aria-label="Evidence view">${["tree", "hex", "xml", "references"].map((v) => `<button class="${view === v ? "active" : ""}" data-view="${v}" aria-pressed="${view === v}">${v === "tree" ? "Structure" : v === "hex" ? "Hex bytes" : v === "xml" ? xmlLabel : "References"}</button>`).join("")}</div>${view === "tree" ? '<div class="tree-toolbar"><input type="search" id="tree-search" placeholder="Find field or value…" aria-label="Search section structure"><button class="btn small" id="expand-tree" title="Expand all displayed nodes">＋</button><button class="btn small" id="collapse-tree" title="Collapse all nodes">−</button></div><div class="tree-help" id="tree-help">↑ ↓ Navigate · ← → Fold / enter · Home / End · Type to find</div><div class="tree-area" id="tree-area" role="tree" aria-label="Section structure" aria-describedby="tree-help"></div>' : view === "references" ? referencePanel() : `<pre class="evidence" tabindex="0" aria-label="${view === "hex" ? "Section hex dump" : xmlLabel}">${esc(view === "hex" ? hexDump(detail.raw_hex) : detail.tsduck_xml || "XML unavailable for this section. Raw bytes remain available.")}</pre>`}<div class="inspector-footer"><span class="meta">Evidence starts at packet ${num(detail.first_packet)}</span><button class="btn" id="edit" ${detail.table_id === 0x42 && detail.valid && detail.services?.length && !busy && !backendFailure && !comparisonEvidence ? "" : "disabled"}>Rename service…</button></div>`;
  panel.querySelectorAll("[data-view]").forEach(
    (el) =>
      (el.onclick = () => {
        view = el.dataset.view;
        renderInspector();
        $('#inspector [data-view="' + view + '"]').focus();
      }),
  );
  if (view === "tree") {
    $("#tree-search").value = treeSearch;
    $("#tree-search").oninput = (e) => {
      treeSearch = e.target.value;
      renderTree();
    };
    $("#tree-search").onkeydown = (event) => {
      if (event.key === "Enter") {
        event.preventDefault();
        focusTreeItem($('#tree-area [tabindex="0"]'));
      }
      if (event.key === "Escape") {
        event.preventDefault();
        treeSearch = "";
        event.target.value = "";
        renderTree();
      }
    };
    renderTree();
    $("#expand-tree").onclick = () => {
      $("#tree-area")
        .querySelectorAll(".tree-node")
        .forEach((el) => setTreeExpanded(el, true));
    };
    $("#collapse-tree").onclick = () => {
      openNodes.clear();
      treeSearch = "";
      $("#tree-search").value = "";
      renderTree();
    };
  }
  panel.querySelectorAll(".reference").forEach((section) => {
    const link = section.querySelector("[data-reference]");
    const copy = section.querySelector("[data-copy-reference]");
    const field = section.querySelector(".reference-url");
    const status = section.querySelector(".reference-status");
    let action = 0, opening = false;
    const feedback = (message, error, token) => {
      if (token !== action || !section.isConnected) return;
      status.hidden = false;
      status.textContent = message;
      status.classList.toggle("bad", error);
      notice(message, error);
    };
    field.onfocus = () => field.select();
    link.onclick = async (event) => {
      // Browser preview keeps ordinary external-link behavior. Only the native
      // shell submits to an OS URL handler and can report its launch failure.
      if (env.runtime === "cloud-browser") return;
      event.preventDefault();
      if (opening) return;
      const token = ++action;
      opening = true;
      link.setAttribute("aria-disabled", "true");
      link.setAttribute("aria-busy", "true");
      feedback("Submitting reference URL to the system browser…", false, token);
      try {
        await invoke("open_reference", { url: link.href });
        feedback("Reference URL submitted to the system browser. If no window appears, use Copy URL.", false, token);
      } catch (error) {
        feedback("Could not open reference: " + String(error) + ". Use Copy URL or select the URL below.", true, token);
      } finally {
        opening = false;
        link.removeAttribute("aria-disabled");
        link.removeAttribute("aria-busy");
      }
    };
    copy.onclick = async () => {
      const token = ++action;
      copy.disabled = true;
      try {
        await navigator.clipboard.writeText(copy.dataset.copyReference);
        feedback("Reference URL copied", false, token);
      } catch (error) {
        if (token === action && section.isConnected) {
          field.focus();
          field.select();
        }
        feedback("Automatic clipboard access is unavailable. The URL is selected; press Ctrl+C or ⌘C to copy it.", true, token);
      } finally {
        copy.disabled = false;
      }
    };
  });
  $("#edit").onclick = openEdit;
}
function renderTimeline() {
  $("#timeline").innerHTML =
    `<div class="timeline-top"><span class="panel-title">OCCURRENCE DENSITY</span><span class="meta">80 packet-position bins <span class="legend-valid">■</span> sections <span class="bad">■</span> invalid</span><span class="spacer"></span><button class="btn small" id="compare-snapshots" ${busy || backendFailure || !data.complete ? "disabled" : ""}>Compare snapshots</button><button class="btn small" id="latest" ${busy || backendFailure || !data.complete ? "disabled" : ""}>Latest state</button></div><div class="bins">${(data.density || Array.from({ length: 80 }, () => ({ count: 0, bad: 0 }))).map((b) => `<div class="bin ${b.bad ? "invalid" : ""}" style="--density:${b.count ? 0.3 + Math.min(0.7, b.count / 50) : 0.08}" title="${num(b.count)} sections · ${num(b.bad)} invalid"></div>`).join("")}</div><div class="history"><span class="meta">0</span>${(
      data.history || []
    )
      .slice(historyPage * 40, (historyPage + 1) * 40)
      .map(
        (h, i) =>
          `<button class="history-point" data-history="${historyPage * 40 + i}" ${busy || backendFailure ? "disabled" : ""}>${esc(h.label)} <span>@ ${num(h.first_packet)}</span></button>`,
      )
      .join(
        "",
      )}<span class="spacer"></span><span class="meta">${num(data.packets)} packets</span></div>${data.history?.length > 40 ? `<div class="history-pages"><button class="btn small" id="history-prev" ${historyPage === 0 ? "disabled" : ""}>← Earlier</button><span class="meta">Transitions ${num(historyPage * 40 + 1)}–${num(Math.min((historyPage + 1) * 40, data.history.length))} of ${num(data.history.length)}</span><button class="btn small" id="history-next" ${(historyPage + 1) * 40 >= data.history.length ? "disabled" : ""}>Later →</button></div>` : ""}`;
  $("#history-prev")?.addEventListener("click", () => {
    historyPage--;
    renderTimeline();
  });
  $("#history-next")?.addEventListener("click", () => {
    historyPage++;
    renderTimeline();
  });
  $("#latest").onclick = () => snapshot(-1);
  $("#compare-snapshots").onclick = () => { changeTab("Changes"); render(); $("#compare-from").focus(); };
  $("#timeline")
    .querySelectorAll("[data-history]")
    .forEach(
      (el) =>
        (el.onclick = () => {
          const h = data.history[Number(el.dataset.history)];
          snapshot(h.last_packet, h.id);
        }),
    );
}
function openEdit() {
  if (backendFailure || busy || !data.complete) return;
  preview = {};
  editTarget = {
    id: selected,
    services: detail.services || [],
    packet: data.selected_packet,
  };
  $("#export").disabled = true;
  $("#diff").textContent = "";
  $("#edit-service").innerHTML = editTarget.services
    .map(
      (s) =>
        `<option value="${s.id}">${esc(s.name)} · SID ${hex(s.id)}</option>`,
    )
    .join("");
  if (selectedService >= 0) $("#edit-service").value = String(selectedService);
  $("#edit-service").onchange = () => {
    $("#rename").value =
      editTarget.services.find((s) => s.id === Number($("#edit-service").value))
        ?.name || "";
    invalidatePreview();
  };
  $("#edit-service").onchange();
  $("#edit-dialog").showModal();
  $("#rename").focus();
}
function invalidatePreview() {
  preview = {};
  $("#export").disabled = true;
  $("#diff").textContent = "";
}
$("#rename").oninput = invalidatePreview;
$("#preview").onclick = async () => {
  if (backendFailure || busy || !editTarget) return;
  const target = editTarget;
  const name = $("#rename").value;
  const sid = Number($("#edit-service").value);
  invalidatePreview();
  $("#preview").disabled = true;
  try {
    const result = await call("preview_rename", {
      id: target.id,
      service_id: sid,
      name,
    });
    if (
      target !== editTarget ||
      name !== $("#rename").value ||
      sid !== Number($("#edit-service").value)
    )
      return;
    preview = result;
    $("#diff").textContent =
      `${result.before} → ${result.after} · version ${result.old_version} → ${result.new_version}`;
    $("#export").disabled = !!backendFailure;
  } catch (error) {
    if (target === editTarget) $("#diff").textContent = String(error);
  } finally {
    if (target === editTarget) $("#preview").disabled = !!backendFailure;
  }
};
$("#export").onclick = async () => {
  if (backendFailure || busy || !preview.token || !editTarget) return;
  const target = editTarget,
    token = preview.token;
  $("#export").disabled = true;
  try {
    const path = await invoke("plugin:dialog|save", {
      options: {
        defaultPath: "edited-si.ts",
        filters: [{ name: "Transport stream", extensions: ["ts"] }],
      },
    });
    if (!path) {
      if (target === editTarget) $("#export").disabled = !!backendFailure;
      return;
    }
    if (target !== editTarget) return;
    const params = { path, format: "ts", preview_token: token };
    if (target.packet != null) params.at_packet = target.packet;
    const result = await call("export", params);
    if (target !== editTarget) return;
    notice(
      "Exported " + num(result.bytes) + " bytes + manifest · " + result.path,
    );
    $("#edit-dialog").close();
  } catch (error) {
    if (target !== editTarget) return;
    $("#diff").textContent = String(error);
    $("#export").disabled = !!backendFailure;
  }
};
$("#scan").onclick = scan;
$("#cancel-scan").onclick = cancelScan;
$("#source").onkeydown = (e) => {
  if (e.key === "Enter") scan();
};
$("#browse").onclick = async () => {
  if (backendFailure) return;
  try {
    const path = await invoke("plugin:dialog|open", {
      options: {
        multiple: false,
        directory: false,
        filters: [
          { name: "Transport streams", extensions: ["ts", "mts", "m2ts"] },
        ],
      },
    });
    if (typeof path === "string") {
      $("#source").value = path;
      scan();
    }
  } catch (error) {
    notice(String(error), true);
  }
};
$("#api").onclick = async () => {
  $("#api-dialog").showModal();
  $("#api-text").textContent = "Loading capabilities…";
  try {
    $("#api-text").textContent = JSON.stringify(
      await call("capabilities"),
      null,
      2,
    );
  } catch (error) {
    $("#api-text").textContent = String(error);
  }
};
$("#close-api").onclick = () => $("#api-dialog").close();
$("#close-edit").onclick = () => $("#edit-dialog").close();
$("#edit-dialog").addEventListener("close", () => {
  editTarget = null;
  invalidatePreview();
});
$("#search").oninput = (e) => {
  search = e.target.value;
  page = 0;
  renderList();
};
$("#search").onkeydown = (event) => {
  if (event.key === "Escape") {
    event.preventDefault();
    search = "";
    event.target.value = "";
    page = 0;
    renderList();
  }
};
$("#prev").onclick = () => {
  if (tab === "Changes") { runComparison(Math.max(0, (comparison.result?.offset || 0) - PAGE_SIZE)); return; }
  page--;
  renderList();
  $("#list").scrollTop = 0;
};
$("#next").onclick = () => {
  if (tab === "Changes") { runComparison(comparison.result?.next_offset || 0); return; }
  page++;
  renderList();
  $("#list").scrollTop = 0;
};
document.addEventListener("keydown", (e) => {
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
    e.preventDefault();
    if (tab === "Changes") { changeTab("Services"); render(); }
    $("#search").focus();
    $("#search").select();
  }
});
// Persist only explicit size choices. Responsive clamping must not overwrite a
// preferred desktop layout when a user temporarily narrows the window.
const LAYOUT_KEY = "showpsisi.workbench.layout.v1";
const layoutBounds = { explorer: [140, 300], inspector: [300, 780] };
let preferredLayout = {}, layoutStorageAvailable = true;
function layoutStorageWarning(message) {
  $("#layout-status").textContent = message;
  $("#layout-status").title = message;
}
function readLayout() {
  try {
    const raw = window.localStorage.getItem(LAYOUT_KEY);
    if (raw === null) return;
    const saved = JSON.parse(raw);
    if (!saved || saved.version !== 1 || typeof saved.widths !== "object" || !saved.widths || Array.isArray(saved.widths))
      throw new Error("Unrecognized layout");
    const widths = {};
    for (const name of Object.keys(layoutBounds)) {
      if (!(name in saved.widths)) continue;
      const value = saved.widths[name];
      if (typeof value !== "number" || !Number.isFinite(value))
        throw new Error("Invalid pane width");
      widths[name] = Math.max(layoutBounds[name][0], Math.min(layoutBounds[name][1], value));
    }
    preferredLayout = widths;
  } catch (error) {
    preferredLayout = {};
    // Parsing/shape errors recover to defaults; inaccessible storage is also
    // harmless. Do not remove another version or any unrelated application data.
    layoutStorageWarning("Layout defaults restored");
  }
}
function saveLayout(reset = false) {
  try {
    if (reset) window.localStorage.removeItem(LAYOUT_KEY);
    else window.localStorage.setItem(LAYOUT_KEY, JSON.stringify({ version: 1, widths: preferredLayout }));
    layoutStorageAvailable = true;
    layoutStorageWarning("");
  } catch (error) {
    layoutStorageAvailable = false;
    layoutStorageWarning("Layout saved for this session only");
  }
}
function defaultLayout() {
  const width = $("#panes").clientWidth;
  return width >= 1550 ? { explorer: 200, inspector: 540 }
    : width <= 1050 ? { explorer: 145, inspector: 350 }
      : { explorer: 178, inspector: 520 };
}
function availablePaneWidth() {
  const width = $("#panes").clientWidth;
  return width - 8 - (width <= 1050 ? 220 : 260);
}
function currentLayout() {
  const styles = getComputedStyle($("#panes"));
  return { explorer: parseFloat(styles.getPropertyValue("--explorer-width")),
    inspector: parseFloat(styles.getPropertyValue("--inspector-width")) };
}
function applyLayout() {
  const panes = $("#panes"), defaults = defaultLayout();
  let explorer = preferredLayout.explorer ?? defaults.explorer;
  let inspector = preferredLayout.inspector ?? defaults.inspector;
  if (panes.clientWidth > 760) {
    explorer = Math.max(140, Math.min(explorer, availablePaneWidth() - 300));
    inspector = Math.max(300, Math.min(inspector, availablePaneWidth() - explorer));
  }
  panes.style.setProperty("--explorer-width", explorer + "px");
  panes.style.setProperty("--inspector-width", inspector + "px");
  for (const [name, id] of [["explorer", "#split-left"], ["inspector", "#split-right"]]) {
    const other = name === "explorer" ? inspector : explorer;
    const el = $(id), value = name === "explorer" ? explorer : inspector;
    el.setAttribute("aria-valuemin", layoutBounds[name][0]);
    el.setAttribute("aria-valuemax", Math.max(layoutBounds[name][0], Math.min(layoutBounds[name][1], availablePaneWidth() - other)));
    el.setAttribute("aria-valuenow", Math.round(value));
    el.setAttribute("aria-valuetext", Math.round(value) + " pixels");
  }
}
function setPaneWidth(name, value) {
  const other = currentLayout()[name === "explorer" ? "inspector" : "explorer"];
  preferredLayout[name] = Math.max(layoutBounds[name][0],
    Math.min(layoutBounds[name][1], availablePaneWidth() - other, value));
  applyLayout();
}
function splitter(id, name, direction) {
  const el = $(id);
  let drag = null;
  el.onpointerdown = (event) => {
    if (event.button !== 0) return;
    event.preventDefault();
    el.focus();
    drag = { pointerId: event.pointerId, start: event.clientX, initial: currentLayout()[name] };
    el.setPointerCapture(event.pointerId);
    document.body.classList.add("resizing-panes");
  };
  el.onpointermove = (event) => {
    if (drag?.pointerId === event.pointerId)
      setPaneWidth(name, drag.initial + (event.clientX - drag.start) * direction);
  };
  const finish = () => {
    if (!drag) return;
    drag = null;
    document.body.classList.remove("resizing-panes");
    saveLayout();
  };
  el.onpointerup = finish;
  el.onpointercancel = finish;
  el.onlostpointercapture = finish;
  el.ondblclick = () => {
    delete preferredLayout[name];
    applyLayout();
    saveLayout();
  };
  el.onkeydown = (event) => {
    if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
    event.preventDefault();
    const step = event.shiftKey ? 64 : 16;
    const value = event.key === "Home" ? layoutBounds[name][0]
      : event.key === "End" ? layoutBounds[name][1]
        : currentLayout()[name] + (event.key === "ArrowRight" ? step : -step) * direction;
    setPaneWidth(name, value);
    saveLayout();
  };
}
readLayout();
applyLayout();
splitter("#split-left", "explorer", 1);
splitter("#split-right", "inspector", -1);
window.addEventListener("resize", applyLayout);
$("#reset-layout").onclick = () => {
  preferredLayout = {};
  applyLayout();
  saveLayout(true);
  notice(layoutStorageAvailable ? "Default layout restored" : "Default layout restored for this session");
};
async function boot() {
  render();
  if (!native?.event?.listen) {
    disconnectBackend(
      "Native backend unavailable. Launch the Tauri application to analyze real streams.",
    );
    return;
  }
  await native.event.listen("core-message", (event) => {
    const msg = event.payload;
    if (msg.event === "backend_exit") {
      disconnectBackend(msg.error);
      return;
    }
    if (backendFailure) return;
    if (msg.event) {
      if (msg.event === "progress" && busy && !cancelling && msg.request_id === activeAnalyze && pending.get(msg.request_id)?.method === "analyze" && msg.state && typeof msg.state === "object" && !Array.isArray(msg.state)) {
        data = msg.state;
        render();
      }
      return;
    }
    const job = pending.get(msg.id);
    if (!job) return;
    pending.delete(msg.id);
    clearTimeout(job.timer);
    if (msg.error) {
      const error = new Error(msg.error.message);
      error.code = msg.error.code;
      error.data = msg.error.data;
      job.reject(error);
    }
    else job.resolve(msg.result);
  });
  env = await invoke("environment");
  if (env.backend_alive === false)
    disconnectBackend("Native backend stopped. Restart the application.");
  if (backendFailure) return;
  $("#source").value = env.sample || "";
  $("#runtime").textContent =
    env.runtime === "cloud-browser"
      ? "● CLOUD PREVIEW · REAL ENGINE"
      : "● NATIVE BACKEND";
  await invoke("milestone", { event: "ui_ready" });
  if (env.auto === "1") setTimeout(scan, Number(env.delay || 0));
}
window.showpsisi = {
  scan,
  cancelScan,
  snapshot,
  inspect,
  call,
  getState: () => data,
  getDetail: () => detail,
  getComparison: () => comparison.result,
};
boot().catch((error) => {
  disconnectBackend("Backend connection failed: " + String(error));
});
