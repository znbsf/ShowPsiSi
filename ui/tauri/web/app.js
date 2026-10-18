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
// Fixed table-type identities; semantic families remain in explanatory tooltips.
function tableCategory(row) {
  const name = row.name || row;
  const fixed = {
    PAT: ["pat", "◆", "Core PSI"], PMT: ["pmt", "▲", "Core PSI"], CAT: ["cat", "■", "Core PSI"],
    NIT: ["nit", "◈", "Services / network"], SDT: ["sdt", "▦", "Services / network"], BAT: ["bat", "◇", "Services / network"],
    EIT: ["eit", "◷", "Schedule"], TDT: ["tdt", "◴", "Clock"], TOT: ["tot", "◶", "Clock"], AIT: ["ait", "▤", "Data / application"]
  };
  if (fixed[name]) return fixed[name];
  if (/^DSMCC/.test(name)) return ["dsmcc", "▥", "Data / application"];
  if (/EIT|ETT|AEIT|AETT/.test(name)) return ["schedule", "◷", "Schedule"];
  if (["TDT", "TOT", "STT"].includes(name)) return ["clock", "◴", "Clock"];
  if (/DSMCC|INT|UNT|DLT|DCT|AIT|DFIT/.test(name)) return ["data", "▤", "Data / application"];
  if (/VCT|MGT|RRT|DCCT|DCCSCT/.test(name)) return ["atsc", "◈", "ATSC signalling"];
  return ["other", "○", "Other signalling"];
}
function categoryBadge(row) {
  const [tone, symbol, label] = tableCategory(row);
  return `<span class="table-kind category-${tone}" title="${esc(label + " · " + (row.name || row) + " · " + (glossary[row.name || row] || ""))}">${symbol} ${esc(tableLabel(row.name || row))}</span>`;
}
const isBadCrc = (row) => row.crc?.status === "invalid";
let showBadCrc = false, evidenceScope = "merged", groupedTables = true, sectionGroupOpen = false;
const openTableGroups = new Set();
function syntaxXml(xml) {
  // Tokenize original text, then escape each token. Never interpret SDK XML as HTML.
  return String(xml || "").split(/(<!--[\s\S]*?-->|<[^>]*>)/g).map((part) => {
    if (part.startsWith("<!--")) return `<span class="xml-comment">${esc(part)}</span>`;
    if (!part.startsWith("<")) return esc(part);
    return '<span class="xml-tag">' + part.split(/("[^"]*"|'[^']*')/g).map((token, i) =>
      i % 2 ? `<span class="xml-string">${esc(token)}</span>` : esc(token).replace(/([\w:.-]+)(=)/g, '<span class="xml-attribute">$1</span>$2')).join("") + '</span>';
  }).join("");
}
function arrivalAxis(first, last, timing = data.timing) {
  const scale = Number(timing?.seconds_per_packet);
  const timed = scale > 0 && timing?.basis === "user supplied bitrate";
  return `<div class="arrival-axis" aria-label="${timed ? 'Estimated seconds from supplied bitrate, not PCR' : 'Packet positions'}">${[0, .25, .5, .75, 1].map(f => {
    const packet = Math.round(first + (last-first)*f);
    return `<span>${timed ? (packet*scale).toFixed(3)+' s' : '#'+num(packet)}</span>`;
  }).join('')}</div><div class="axis-basis">${timed ? 'Estimated elapsed seconds · user supplied 188-byte TS bitrate · not PCR time' : 'Zero-based packet positions · no measured time available'}</div>`;
}
function distributionPanel(row) {
  const d = row.distribution;
  if (!d) return '';
  const bins = d.bins || [], max = Math.max(1, ...bins.map(b => b.count));
  return `<details class="arrival"><summary>Arrival · first #${num(d.first_packet)} → last #${num(d.last_packet)} · ${num(d.observation_count)}×</summary><p class="meta">Packet positions, not PCR time. ${d.first_seconds != null ? `Estimated ${Number(d.first_seconds).toFixed(3)}–${Number(d.last_seconds).toFixed(3)} s · ${esc(d.basis)}` : 'Time unavailable without a bitrate estimate.'}</p><p class="meta">Gaps (packets): min ${d.min_gap_packets == null ? '—' : num(d.min_gap_packets)} · mean ${d.mean_gap_packets == null ? '—' : Number(d.mean_gap_packets).toFixed(1)} · max ${d.max_gap_packets == null ? '—' : num(d.max_gap_packets)}</p><div class="section-density" aria-label="Selected section occurrence density">${bins.map(b => `<span class="${b.bad ? 'invalid' : ''}" style="--height:${b.count ? Math.max(2, 100*b.count/max) : 0}%" title="Packets ${num(b.from_packet)}–${num(b.to_packet)}: ${num(b.count)} observations, ${num(b.bad)} invalid"></span>`).join('')}</div>${arrivalAxis(bins[0]?.from_packet || 0, bins.at(-1)?.to_packet || 0)}</details>`;
}
const tip = (key) => `title="${esc((tableLabels[key] ? key + " · " : "") + (glossary[key] || key))}"`;
let data = {},
  detail = {},
  env = {},
  seq = 0,
  pending = new Map(),
  tab = "Services",
  filter = "",
  pidFilter = null,
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
const recentResponses = [];
const frontendErrors = [];
function recordFrontendError(error) {
  frontendErrors.push({at:new Date().toISOString(),message:String(error?.stack || error).slice(0,2048)});
  if(frontendErrors.length > 20) frontendErrors.shift();
}
window.addEventListener("error", event=>recordFrontendError(event.error || event.message));
window.addEventListener("unhandledrejection", event=>recordFrontendError(event.reason));
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
<header class="titlebar"><span class="app-mark" aria-hidden="true">≋</span><strong>ShowPsiSi</strong><span class="title-separator">/</span><span class="workspace-name">Transport stream workbench</span><span class="spacer"></span><span class="runtime" id="runtime">Connecting backend</span><span id="layout-status" class="layout-status" role="status"></span><button class="btn quiet" id="reset-layout" title="Restore default pane widths">Reset layout</button><button class="btn quiet" id="theme-toggle" aria-label="Switch color theme">Light theme</button><button class="btn quiet" id="api">Agent API</button><button class="btn quiet" id="save-diagnostics" title="Save screenshot and UI state, including visible metadata and source paths">Save diagnostics</button></header>
<div class="sourcebar"><label for="source">SOURCE</label><input id="source" placeholder="Open a local .ts, .mts or .m2ts file" spellcheck="false"><select id="standards" aria-label="Signalling standards context" title="Explicit native decoder context; auto uses detected signalling, not RF delivery system"><option value="auto">Standards: Auto</option><option value="dvb">DVB</option><option value="atsc">ATSC</option><option value="isdb">ISDB</option><option value="isdb-japan">ISDB Japan</option><option value="isdb-brazil">ISDB Brazil</option><option value="scte">SCTE</option><option value="dtmb">DTMB</option></select><input id="default-charset" placeholder="Default charset" aria-label="Default input charset" title="Optional SDK charset for the next scan, e.g. ISO-8859-15 or UTF-8. Explicit DVB selectors take precedence."><input id="extra-pids" placeholder="Extra PIDs (optional)" aria-label="Additional monitored PIDs, decimal or hexadecimal, comma separated" aria-describedby="extra-pids-error" title="Additional monitored PIDs, decimal or hexadecimal, separated by commas"><button class="btn" id="browse">Open file…</button><button class="btn primary" id="scan">Analyze</button><button class="btn" id="cancel-scan" hidden title="Stop the active analysis; the source file stays unchanged">Cancel</button></div>
<div class="sourcebar-feedback" id="source-feedback"><p class="field-error" id="extra-pids-error" hidden></p></div>
<div class="scan-progress" id="scan-progress" role="progressbar" aria-label="Analysis in progress" aria-valuetext="Analyzing" hidden></div>
<div class="stats" id="stats"></div>
<main class="panes" id="panes"><nav class="sidebar" aria-label="Table library"><div class="panel-title">EXPLORER <span class="muted" title="Program Specific Information / Service Information">PSI / SI</span></div><div id="sidebar"></div><div class="extension" id="extension"></div><div class="sidebar-help">↑ ↓ Home End <span>Move focus</span><br>Enter / Space <span>Select</span><br>Ctrl / ⌘ K <span>Search records</span></div></nav><div class="splitter" id="split-left" aria-controls="sidebar" title="Drag or use arrow keys to resize. Double-click to reset." role="separator" aria-label="Resize explorer" aria-orientation="vertical" tabindex="0"></div><section class="center" aria-label="Stream records"><div class="tabs" id="tabs" role="tablist" aria-label="Record type"></div><div class="searchbar"><span aria-hidden="true">⌕</span><input id="search" type="search" placeholder="Search services, IDs, providers…" aria-label="Search records"><span id="result-count"></span><div id="table-filter-tools" class="table-controls"></div></div><div id="service-head"></div><div class="list" id="list" role="listbox" aria-label="Stream records"></div><div class="pagination"><span id="page-label"></span><span class="spacer"></span><button class="btn small" id="prev" aria-label="Previous page">←</button><button class="btn small" id="next" aria-label="Next page">→</button></div></section><div class="splitter" id="split-right" aria-controls="inspector" title="Drag or use arrow keys to resize. Double-click to reset." role="separator" aria-label="Resize inspector" aria-orientation="vertical" tabindex="0"></div><aside class="inspector" aria-label="Section inspector" id="inspector"></aside></main>
<section class="timeline" aria-label="Section occurrence history" id="timeline"></section>
<footer><span class="status-dot" id="status-dot"></span><span id="notice" role="status" aria-live="polite">Open a stream to begin</span><span id="snapshot-state">LOCAL · SOURCE READ-ONLY</span></footer>
<dialog id="edit-dialog" aria-labelledby="edit-title"><h2 id="edit-title">Rename service</h2><p>Preview an SDT edit. Export creates a new SI-only transport stream and manifest, without media or PCR.</p><label for="edit-service">Service</label><select id="edit-service"></select><label for="rename">New service name</label><input id="rename"><button class="btn primary" id="preview">Preview change</button><p id="diff" role="status"></p><div class="actions"><button class="btn" id="export" disabled>Export SI-only TS + manifest</button><button class="btn" id="close-edit">Close</button></div></dialog>
<dialog id="api-dialog" aria-labelledby="api-title"><h2 id="api-title">Native agent API</h2><pre id="api-text"></pre><button class="btn" id="close-api">Close</button></dialog>`;
let theme = "dark";
try { theme = localStorage.getItem("showpsisi.theme") === "light" ? "light" : "dark"; } catch (_) {}
function applyTheme() {
  document.documentElement.dataset.theme = theme;
  $("#theme-toggle").textContent = theme === "dark" ? "Light theme" : "Dark theme";
  $("#theme-toggle").setAttribute("aria-pressed", String(theme === "light"));
  document.querySelector('meta[name="color-scheme"]').content = theme;
}
applyTheme();
$("#theme-toggle").onclick = () => {
  theme = theme === "dark" ? "light" : "dark";
  try { localStorage.setItem("showpsisi.theme", theme); } catch (_) {}
  applyTheme();
};
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
// Field-scoped validation feedback. The footer live region still carries the
// announcement; this element keeps the reason next to the control that failed.
function setExtraPidsError(message) {
  const field = $("#extra-pids");
  const error = $("#extra-pids-error");
  field.setAttribute("aria-invalid", message ? "true" : "false");
  error.textContent = message || "";
  error.hidden = !message;
  $("#source-feedback").hidden = !message;
}
$("#extra-pids").addEventListener("input", () => setExtraPidsError(""));
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
    setExtraPidsError(String(error));
    notice(String(error), true);
    $("#extra-pids").focus();
    return;
  }
  setExtraPidsError("");
  const epoch = ++scanEpoch;
  busy = true;
  cancelling = false;
  resetAnalysisViews();
  data = {};
  preview = {};
  filter = "";
  pidFilter = null;
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
      default_charset: $("#default-charset").value.trim(),
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
  else {
    const visible = (data.tables || []).find(row => showBadCrc || !isBadCrc(row));
    if (visible) inspect(visible.id);
    else { selectionReset(); renderInspector(); }
  }
}
async function snapshot(packet, id) {
  clearTimeout(pendingSnapshotTimer);
  pendingSnapshotTimer = null;
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
  return !t.name || t.name === "Private / other" || t.name.startsWith("Unknown / private (");
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
    (pidFilter === null || Number(t.pid) === pidFilter) && (!filter ||
    (filter === "Private / other" ? isOtherTable(t) : t.name === filter))
  );
}
// Navigation counts engine logical groups, never distinct payloads or arrivals.
function explorerRows() {
  const groups = data.table_groups || [];
  const rows = [];
  for (const g of groups) {
    const name = g.name || "Private / other";
    const row = rows.find(r => r.pid === g.pid && r.name === name);
    if (row) row.count++;
    else rows.push({pid:g.pid, name, count:1});
  }
  rows.sort((a,b) => a.pid-b.pid || (a.name < b.name ? -1 : a.name > b.name ? 1 : 0));
  return [{pid:-1,name:"All tables",count:groups.length}, ...rows];
}
let explorerFocusKey = JSON.stringify([-1,"All tables"]);
const explorerKey = row => JSON.stringify([row.pid,row.name]);
function explorerSelected(row) {
  return tab === "Tables" && (pidFilter ?? -1) === row.pid && filter === (row.pid < 0 ? "" : row.name);
}
function selectExplorer(row) {
  pidFilter = row.pid < 0 ? null : row.pid;
  filter = row.pid < 0 ? "" : row.name;
  explorerFocusKey = explorerKey(row);
  changeTab("Tables"); page = 0; render();
  [...$("#sidebar").querySelectorAll("button")].find(el => el.dataset.explorerKey === explorerFocusKey)?.focus();
}
function renderExplorer() {
  const rows = explorerRows();
  const restoreFocus = $("#sidebar").contains(document.activeElement);
  if (!rows.some(row => explorerKey(row) === explorerFocusKey)) explorerFocusKey = explorerKey(rows[0]);
  $("#sidebar").innerHTML = '<div class="pid-head" title="Logical tables, including hidden bad-CRC evidence. Repeated arrivals and section payloads do not increase this count."><span aria-hidden="true"></span><span>PID</span><span>TABLE TYPE</span><span>#</span></div>' + rows.map(row => {
    const all = row.pid < 0, category = tableCategory(row.name);
    return `<button class="nav explorer-row ${all ? 'all-tables' : 'pid-row'} ${explorerSelected(row) ? 'active' : ''}" data-pid="${row.pid}" data-filter="${esc(row.name)}" data-explorer-key="${esc(explorerKey(row))}" data-count="${row.count}" aria-pressed="${explorerSelected(row)}" tabindex="${explorerKey(row) === explorerFocusKey ? 0 : -1}" title="${all ? 'All tables' : 'PID ' + hex(row.pid) + ' · ' + esc(row.name)} · ${row.count} logical tables, including hidden bad-CRC evidence"><span class="pid-table-icon category-${category[0]}" aria-hidden="true">${all ? '≡' : category[1]}</span>${all ? '' : `<span class="numeric">${hex(row.pid)}</span>`}<span class="family-label category-${category[0]}" data-table-name="${esc(row.name)}">${esc(tableLabel(row.name))}</span><span class="count">${num(row.count)}</span></button>`;
  }).join('');
  const buttons = [...$("#sidebar").querySelectorAll("button")];
  buttons.forEach((el, index) => {
    el.onclick = () => selectExplorer(rows[index]);
    el.onfocus = () => { explorerFocusKey = el.dataset.explorerKey; buttons.forEach(b => b.tabIndex = b === el ? 0 : -1); };
    el.onkeydown = event => {
      if (!["ArrowDown","ArrowUp","Home","End"].includes(event.key)) return;
      event.preventDefault();
      const next = event.key === "Home" ? 0 : event.key === "End" ? buttons.length-1 : Math.max(0,Math.min(buttons.length-1,index+(event.key === "ArrowDown" ? 1 : -1)));
      buttons[next].focus();
    };
  });
  if (restoreFocus) buttons.find(el => el.dataset.explorerKey === explorerFocusKey)?.focus();
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
  $("#scan-progress").hidden = !busy;
  $("#scan-progress").setAttribute(
    "aria-valuetext",
    cancelling ? "Cancelling analysis" : busy ? "Analyzing transport stream" : "Idle",
  );
  $("#source").disabled = busy;
  $("#standards").disabled = busy;
  $("#extra-pids").disabled = busy;
  $("#default-charset").disabled = busy;
  renderExplorer();
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
        ? (data.tables || []).filter(tableMatches).filter(r => showBadCrc || !isBadCrc(r))
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
        hex(row.pmt_pid) + " " + hex(row.table_id, 2)
      )
        .toLowerCase()
        .includes(needle),
    );
  }
  return tab === "Tables" ? [...rows].sort((a,b) => a.pid-b.pid || a.table_id-b.table_id || a.extension-b.extension || a.version-b.version || a.section-b.section) : rows;
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
  $("#list").onscroll = () => { $("#service-head").scrollLeft = $("#list").scrollLeft; };
  $(".searchbar").hidden = tab === "Changes";
  $("#list").setAttribute("role", tab === "Changes" ? "region" : "listbox");
  $("#list").setAttribute("aria-label", tab === "Changes" ? "Snapshot changes" : "Stream records");
  if (tab === "Changes") {
    renderComparison();
    return;
  }
  const rows = recordRows();
  const groups = tab === "Tables" && groupedTables ? (data.table_groups || []).filter(g => tableMatches(g) && (!search.trim() || g.section_ids.some(id => rows.some(r => r.id === id)))).sort((a,b) => a.pid-b.pid || a.table_id-b.table_id || a.extension-b.extension || a.version-b.version) : [];
  const total = tab === "Tables" && groupedTables ? groups.length : rows.length;
  page = Math.max(0, Math.min(page, Math.ceil(total / PAGE_SIZE) - 1));
  const start = page * PAGE_SIZE;
  $("#result-count").textContent = num(total);
  $("#page-label").textContent = total ? `${num(start + 1)}–${num(Math.min(start + PAGE_SIZE, total))} of ${num(total)} ${tab === "Tables" && groupedTables ? "tables" : "records"}` : "0 records";
  $("#prev").disabled = page === 0;
  $("#next").disabled = start + PAGE_SIZE >= total;
  $("#service-head").innerHTML = tab === "Services" ? `<div class="service-head"><span ${tip("LCN")}>LCN</span><span>SERVICE / PROVIDER</span><span>TYPE</span><span ${tip("PMT")}>PMT PID</span><span>VIDEO / AUDIO PIDs</span></div>` : "";
  $("#table-filter-tools").innerHTML = tab === "Tables" ? `<label class="family-filter">Type <select id="table-family" aria-label="Table type across all PIDs"><option value="">All types</option>${[...tableFamilies(), "Private / other"].map(name => `<option value="${esc(name)}" ${filter === name ? "selected" : ""}>${esc(tableLabel(name))}</option>`).join("")}</select></label><label title="Include invalid CRC sections. Issues always retains all evidence."><input id="show-bad-crc" type="checkbox" ${showBadCrc ? 'checked' : ''}> Bad CRC (${num((data.tables || []).filter(tableMatches).filter(isBadCrc).length)})</label><button class="btn small" id="table-group-toggle" aria-pressed="${groupedTables}" title="Switch between logical tables and individual sections">${groupedTables ? "Sections" : "Tables"}</button>` : "";
  $("#table-family")?.addEventListener("change", event => {
    filter = event.target.value; pidFilter = null; page = 0;
    explorerFocusKey = JSON.stringify([-1,"All tables"]);
    render(); $("#table-family")?.focus();
  });
  $("#table-group-toggle")?.addEventListener("click", () => { groupedTables = !groupedTables; page = 0; renderList(); });
  $("#show-bad-crc")?.addEventListener("change", e => { showBadCrc = e.target.checked; page = 0; renderList(); });
  $("#list").innerHTML = rows
    .slice(tab === "Tables" && groupedTables ? 0 : start, tab === "Tables" && groupedTables ? rows.length : start + PAGE_SIZE)
    .map((r, i) => {
      const key = rowIdentity(r, start + i);
      let body = "";
      if (tab === "Services")
        body = `<span class="lcn" title="LCN: ${esc(r.lcn_status || 'unknown')}${esc((r.lcn_candidates || []).map(c => ` · ${c.number} (${c.namespace}; ${c.source_id})`).join(''))}">${r.logical_channel_number ?? (r.lcn_status === 'conflict' ? 'Conflict' : '—')}</span><div class="record-name"><strong>${esc(r.name || "Unnamed service")}</strong><small>${esc(r.provider || "No provider")} · SID ${hex(r.id)}</small><small>${esc(r.group || '')}</small></div><span class="service-type" title="${esc(r.service_type_name || 'Service type unavailable')}">${esc((r.service_type_name || 'Unknown').replace('Digital television service', 'Digital TV').replace('Digital radio sound service', 'Digital radio'))}<small class="numeric">${hex(r.service_type ?? r.type, 2)}</small></span><span class="numeric">${hex(r.pmt_pid)}</span><span class="numeric media-pids" title="${esc(r.media_status || 'PMT unavailable')}"><span>V ${r.video_pids?.length ? r.video_pids.map(p => hex(p)).join(', ') : r.media_status === 'decoded PMT' ? 'none' : '—'}</span><span>A ${r.audio_pids?.length ? r.audio_pids.map(p => hex(p)).join(', ') : r.media_status === 'decoded PMT' ? 'none' : '—'}</span></span>`;
      if (tab === "Tables")
        body = `${categoryBadge(r)}<div class="record-name"><strong>PID <span class="numeric">${hex(r.pid)}</span> · TID <span class="numeric">${hex(r.table_id, 2)}</span></strong><small>Version ${r.version} · section ${r.section}/${r.last_section} · ${num(r.bytes)} B</small><small>CRC ${esc(r.crc?.transmitted_hex || r.crc?.status || "unavailable")} · #${num(r.first_packet)} → #${num(r.last_packet)}</small></div><span class="numeric muted">${num(r.count)}×</span><span class="${r.valid ? "ok" : "bad"}" title="${r.valid ? "Valid section" : "Invalid section"}">${r.valid ? "●" : "⚠"}</span>`;
      if (tab === "EPG")
        body = `<div class="record-name"><strong>${esc(eventTitle(r))}</strong><small>SID ${hex(r.service_id)} · ${esc(r.start)} UTC · ${num(r.duration_seconds / 60)} min</small></div><span class="muted numeric">${hex(r.id)}</span>`;
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
        const options = [...$("#list").querySelectorAll('[role="option"]')].filter(el => el.getClientRects().length);
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
  if (tab === "Tables" && groupedTables && groups.length) {
    const list = $("#list");
    list.setAttribute("role", "region");
    list.setAttribute("aria-label", "Table groups and source sections");
    const nodes = new Map([...list.querySelectorAll("[data-key]")].map(el => [el.dataset.key, el]));
    list.replaceChildren();
    for (const g of groups.slice(start, start + PAGE_SIZE)) {
      const groupRows = g.section_ids.map(id => nodes.get(id)).filter(Boolean);
      // Preserve all-invalid group evidence even when its bad-CRC rows are hidden.
      if (!groupRows.length && (showBadCrc || g.validity !== "all_invalid")) continue;
      const branch = document.createElement("details");
      branch.className = "table-branch";
      branch.open = openTableGroups.has(g.id);
      branch.innerHTML = `<summary>${categoryBadge(g)} <span>PID ${hex(g.pid)} · TID ${hex(g.table_id,2)} · Ext ${hex(g.extension)} · v${g.version} · ${g.current ? "current" : "next"}<small>${esc(g.validity)} · observed ${g.observed_section_numbers?.length || 0}/${Number(g.last_section)+1} · missing ${(g.missing_section_numbers || []).join(', ') || 'none'} · selected ${g.selected_complete ? 'complete' : 'incomplete'}</small><small>${num(g.distribution?.observation_count)} observations · packets #${num(g.distribution?.first_packet)}–#${num(g.distribution?.last_packet)}</small></span></summary><div role="listbox" aria-label="Source sections"></div>`;
      const holder = branch.querySelector('[role="listbox"]');
      for (const row of groupRows) holder.append(row);
      if (!holder.querySelector('[tabindex="0"]') && groupRows.length) groupRows[0].tabIndex = 0;
      if (!groupRows.length) holder.innerHTML = '<p class="meta">Bad-CRC evidence hidden. Enable Show bad CRC to inspect.</p>';
      branch.ontoggle = () => branch.open ? openTableGroups.add(g.id) : openTableGroups.delete(g.id);
      list.append(branch);
    }
  }
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
  return { label, value: fieldValue(key, value), kind: typeof value };
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
    tone: d.malformed || (d.decode_status && d.decode_status !== "decoded") ? "bad" : d.extension ? "private" : "",
    value: hex(d.tag, 2) + " · " + d.length + " B · @" + d.offset,
    children: [
      leaf("descriptor_tag", d.tag, "tag"),
      leaf("decode_status", d.decode_status || "not reported"),
      leaf("decode_scope", d.decode_scope || "not reported"),
      leaf("decoder_registered", d.decoder_registered ?? null),
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
        kind: /^(?:0x[0-9a-f]+|[0-9]+)$/i.test(String(value)) ? "number" : "string",
      })),
      ...(node.children || []).map(nativeNode),
      ...(node.text ? [{ label: "text", value: node.text, kind: "string" }] : []),
    ],
  };
}
function nativeXmlTree() {
  if (evidenceScope === "section") return {id:"native",label:"TSDuck decoded structure",value:"SDK table decoding is available in Merged table; fields and bytes here are section-local",children:[]};
  const merged = detail.merged;
  return {id:"native",label:"TSDuck decoded structure · merged table",
    value: merged?.complete && merged.native_table ? "complete selected generation" : "No complete selected generation; no merged decode",
    children: merged?.complete && merged.native_table ? [nativeNode(merged.native_table)] : []};
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
    "crc",
    "native_table_complete",
    "native_table_at_packet",
  ];
  const header = headerKeys
    .filter((k) => detail[k] !== undefined)
    .flatMap((k) => typeof detail[k] === "object" ? [{id:k,label:k,children:objectNodes(detail[k])}] : [leaf(k, detail[k])]);
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
  if (detail.native_table_sources?.length) children.push({id:"assembly",label:detail.merged?.complete ? "Merged table source sections" : "Candidate sections · no completed merge",value: detail.merged?.complete ? "complete" : "partial / superseded", children: detail.native_table_sources.map((source, i) => ({id:source.id || i,label:`Section ${source.section ?? source.section_number ?? i}`, children:objectNodes(source)}))});
  const audit = (detail.descriptors || []).filter(d => d.malformed || (d.decode_status && d.decode_status !== "decoded"));
  if (audit.length) children.push({id:"audit",label:"Descriptor audit · unresolved / malformed",value:num(audit.length),tone:"bad",children:audit.map(descriptorNode)});
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
      identity: detail.identity,
      distribution: detail.distribution,
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
  const kind = ["number", "string", "boolean"].includes(node.kind) ? node.kind : "meta";
  const label = `<span class="node-label ${node.tone || ""}" title="${esc(fieldHelp[node.label] || node.label)}">${highlightedTreeText(node.label)}</span>${node.value !== undefined ? `<span class="node-value" data-value-kind="${kind}">${highlightedTreeText(node.value)}</span>` : ""}`;
  if (!node.children)
    return `<div class="tree-leaf" ${accessible}>${label}</div>`;
  const opened = !!needle || openNodes.has(path);
  return `<div class="tree-node" ${accessible} data-path="${esc(path)}" aria-expanded="${opened}"><div class="tree-row">${label}<span class="node-count">${num(node.children.length)}</span></div><div class="tree-children" role="group" ${opened ? "" : "hidden"}>${!opened ? "" : node.children.length ? node.children.map((child, i) => drawNode(child, path, i, ancestorMatch || (!!needle && selfMatch), level + 1)).join("") : '<div class="tree-empty">No decoded fields</div>'}</div></div>`;
}
function setTreeExpanded(node, expanded) {
  if (!expanded && node.contains(document.activeElement) && document.activeElement !== node) focusTreeItem(node);
  if (!expanded && node.querySelector(':scope > .tree-children [tabindex="0"]')) {
    node.querySelectorAll('[tabindex="0"]').forEach(el => el.tabIndex = -1);
    node.tabIndex = 0;
  }
  node.setAttribute("aria-expanded", String(expanded));
  node.querySelector(":scope > .tree-children").hidden = !expanded;
  if (!treeSearch) {
    if (expanded) openNodes.add(node.dataset.path);
    else openNodes.delete(node.dataset.path);
    renderTree();
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
function sectionGroupPanel() {
  const group = (data.table_groups || []).find(g => (g.section_ids || []).includes(detail.id));
  if (!group || (group.last_section === 0 && group.section_ids.length === 1)) return '';
  const sources = (data.tables || []).filter(r => group.section_ids.includes(r.id));
  const hidden = sources.filter(isBadCrc).length;
  return `<details class="section-group" id="section-group" ${sectionGroupOpen ? "open" : ""}><summary>▦ Table sections · ${esc(group.validity)} · ${group.selected_complete ? 'complete selection' : 'incomplete selection'}</summary><p class="meta">Capture-wide version coverage; selected completeness is generation-safe.</p><p class="meta">Observed: ${(group.observed_section_numbers || []).join(', ') || 'none'} · Missing: ${(group.missing_section_numbers || []).join(', ') || 'none'} · Missing valid: ${(group.missing_valid_section_numbers || []).join(', ') || 'none'} · Selected missing: ${(group.selected_missing_section_numbers || []).join(', ') || 'none'} · Bad CRC: ${hidden}${showBadCrc ? '' : ' hidden'}</p><div class="section-links">${sources.filter(r => showBadCrc || !isBadCrc(r)).map(r => `<button class="btn small" data-section-id="${esc(r.id)}" aria-pressed="${r.id === detail.id}">§ ${r.section} · v${r.version} · ${r.valid ? 'valid' : 'invalid'} · CRC ${esc(r.crc?.transmitted_hex || r.crc?.status || 'unavailable')}</button>`).join('')}</div>${hidden ? `<button class="btn small" id="group-show-bad">${showBadCrc ? 'Hide' : 'Show'} ${hidden} bad CRC section(s)</button>` : ''}</details>`;
}
let epgLanguage = "", identifierResult = null, satelliteResult = null;
function satelliteText(x) {
  const p=x.raw_parameters || {};
  return "Candidates only · " + (x.status || x.error || "") + "\n" +
    (p.orbital_position_degrees === undefined ? "No orbital position" : p.orbital_position_degrees + "° " + p.direction) +
    " · " + (p.frequency_hz === undefined ? "frequency unspecified" : p.frequency_hz + " Hz") +
    " · " + (p.symbol_rate === undefined ? "symbol rate unspecified" : p.symbol_rate + " sym/s") +
    " · " + (p.polarization || "polarization unspecified") + "\n" +
    (x.candidates || []).map(c => c.name + " · candidate · Δ " + c.orbital_delta_degrees + "°\nSource: " + c.source.publisher + " · reviewed " + c.source.reviewed_at + "\n" + c.source.url).join("\n") +
    "\n" + (x.uncertainty || "") + "\nOnly nominal orbital position is compared. Frequency, symbol rate, polarization and modulation are not checked.";
}
function eventVariant(event) {
  const variants = event.language_variants || [];
  return variants.find(v => v.language_code === epgLanguage) || variants.find(v => v.language_code === event.default_language) || variants[0] || {};
}
function eventTitle(event) {
  const variant = eventVariant(event);
  return variant.language_code ? (variant.title || "No usable title") : (event.title || "Untitled event");
}
function metadataPanel() {
  const card = (title, body, extra = null) => `<article class="metadata-card"><strong>${esc(title)}</strong><pre>${esc(body)}</pre>${extra ? `<details><summary>Original values and source evidence</summary><pre>${esc(JSON.stringify(extra, null, 2))}</pre></details>` : ""}</article>`;
  const events = detail.events || [], languages = [...new Set(events.flatMap(e => (e.language_variants || []).map(v => v.language_code)))].sort();
  return `<div class="metadata-panel" aria-label="Signal metadata"><p class="meta">Selected section only. Reference labels are not verified current operator ownership. Original bytes remain in Hex.</p>
    <details><summary>Look up an identifier</summary><div class="metadata-query"><select id="identifier-kind" aria-label="Identifier namespace">${["original_network_id","network_id","bouquet_id","ca_system_id","private_data_specifier","registration_id","data_broadcast_id","platform_id","oui"].map(k => `<option>${k}</option>`).join("")}</select><input id="identifier-value" placeholder="0x0001" aria-label="Identifier value"><button class="btn small" id="identifier-query">Look up</button></div><p class="meta">Uses the analyzed standard context; choose an explicit standard and rescan if context is required.</p><pre id="identifier-result">${esc(identifierResult ? JSON.stringify(identifierResult,null,2) : "Enter a decimal or hexadecimal ID.")}</pre></details>
    <h3>Satellite candidates</h3><div class="satellite-query metadata-query"><input id="satellite-position" placeholder="Degrees: 13.0" aria-label="Orbital position in degrees"><select id="satellite-direction" aria-label="Orbital direction"><option>E</option><option>W</option></select><button class="btn small" id="satellite-query">Candidates</button></div><p class="meta">Nominal GEO slot only. An incomplete reference snapshot; never a confirmed satellite.</p><pre id="satellite-result">${satelliteResult ? esc(satelliteText(satelliteResult)) : ""}</pre><details class="satellite-lookup-evidence"><summary>Satellite lookup evidence</summary><pre id="satellite-evidence">${satelliteResult ? esc(JSON.stringify(satelliteResult,null,2)) : ""}</pre></details>
    ${(detail.satellite_associations || []).map(x => card("Satellite candidates · " + (x.transport ? "TS " + hex(x.transport.transport_stream_id) + " / ONID " + hex(x.transport.original_network_id) : "section descriptor") + " · offset " + x.wire_source.section_offset,satelliteText(x),x)).join("") || '<p class="meta">No supported satellite delivery descriptor in this section. S2/S2X-only descriptors do not establish a slot.</p>'}
    <h3>Multilingual EPG</h3><label for="epg-language">Preferred language</label><select id="epg-language"><option value="">Default (language-code order)</option>${languages.map(l => `<option value="${esc(l)}" ${epgLanguage === l ? "selected" : ""}>${esc(l)}</option>`).join("")}</select>
    ${events.map(e => {const v=eventVariant(e);return card(`Event ${hex(e.id)} · ${v.language_code || "no language"}${epgLanguage && v.language_code !== epgLanguage ? " · fallback" : ""}`, `${eventTitle(e)}\nShort: ${v.short_status || "absent"}\n${v.short_text || ""}\nExtended: ${v.extended_status || "absent"}\n${v.extended_text ?? "No complete extended text"}\n${(v.warnings || []).join("\n")}`, {event_id:e.id,service_id:e.service_id,source_id:e.source_id,variant:v});}).join("") || '<p class="meta">No EIT events in this section.</p>'}
    <h3>ID names and sources</h3>${(detail.identifier_lookups || []).map(x => card(`${x.namespace} · ${x.raw_hex}`, `${x.label || "Unknown"} · ${x.status}\n${x.uncertainty}`, x)).join("") || '<p class="meta">No supported identifiers indexed in this section.</p>'}
    <h3>Text encoding diagnostics</h3><p class="meta">${esc(detail.text_diagnostic_scope || "")}</p>${(detail.text_diagnostics || []).map(x => card(`${x.field} · ${x.language_code || "no language tag"}`, `${x.status} · ${x.effective_charset || "unknown charset"} · ${x.basis}\n${x.decoded_text}\nSelector: ${x.selector_hex || "none"} · section offset ${x.source.section_offset}\nRaw: ${x.raw_hex}\n${(x.warnings || []).join("\n")}`, x)).join("") || '<p class="meta">No supported text fields in this section.</p>'}</div>`;
}
function renderInspector() {
  const panel = $("#inspector");
  if (aggregateDiagnostic) {
    panel.innerHTML = `<div class="panel-title">TRANSPORT DIAGNOSTIC <span class="bad">AGGREGATE</span></div><div class="empty"><span class="empty-icon bad">⚠</span><h3>${esc(aggregateDiagnostic.code)}</h3><p>${esc(aggregateDiagnostic.detail)}</p><p>${num(aggregateDiagnostic.count)} observations across monitored SI PIDs. Individual packet locations are not indexed.</p></div>`;
    return;
  }
  if (loadingDetail || detailError || !detail.name) {
    if (tab === "Changes" && !loadingDetail && !detailError) {
      // Comparison mode replaces the record list, so a "select a record" hint
      // would point at nothing. Describe the workflow that is actually on screen.
      panel.innerHTML = `<div class="panel-title">SECTION INSPECTOR <span class="muted">COMPARISON</span></div><div class="empty"><span class="empty-icon">⇄</span><h3>Compare two observed states</h3><p>Choose packet cutoffs A and B in the record pane, then compare. Each change lists its own before/after evidence; selecting that evidence inspects the exact section here without moving the workbench snapshot. Use <em>Use snapshot</em> when you deliberately want the workbench to move to that cutoff.</p>${comparison.error ? `<p class="bad">${esc(comparison.error)}</p>` : ""}<p class="meta">Only observed valid current sections are compared. A missing observation is not proof that a service stopped broadcasting.</p></div>`;
      return;
    }
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
  const xmlSource = evidenceScope === "merged" && detail.merged?.complete ? detail.merged.tsduck_xml : null;
  const xmlLabel = detail.native_xml_guarded ? "Guarded SDK XML" : "TSDuck XML";
  panel.innerHTML = `<div class="panel-title">SECTION INSPECTOR <span class="${detail.valid ? "ok" : "bad"}">${detail.valid ? "VALID" : "INVALID"}</span></div>${comparisonEvidence ? `<p class="comparison-context">${esc(comparisonEvidence)} · main snapshot unchanged</p>` : ""}<div class="inspector-heading"><h2 ${tip(detail.name)}>${categoryBadge(detail)} <span>/ v${detail.version}</span></h2><span class="numeric">${hex(detail.pid)} PID</span></div><p class="meta identity-line">TID ${hex(detail.table_id, 2)} · CRC ${esc(detail.crc?.transmitted_hex || detail.crc?.status || "unavailable")} (${esc(detail.crc?.status || "unavailable")}) · Section ${detail.section}/${detail.last_section} · ${num(detail.bytes)} bytes · ${num(detail.count)} observations${reportedStandards(detail) ? " · " + esc(reportedStandards(detail)) : ""}${selectedService >= 0 ? " · SID " + hex(selectedService) : ""}</p>${detail.native_table_at_packet != null ? `<p class="meta native-evidence" id="native-assembly-evidence">Native assembly cutoff: packet ${num(detail.native_table_at_packet)}${detail.merged?.complete ? " · complete merged generation" : " · incomplete / superseded: merged decode unavailable"}</p>` : ""}${nativeWarnings.length ? `<p class="meta" id="native-decode-warnings" role="note"><strong class="bad">Decoder note</strong><br><span class="bad">${nativeWarnings.map(esc).join("<br>")}</span></p>` : ""}${distributionPanel(detail)}${sectionGroupPanel()}<div class="scope-tabs" role="group" aria-label="Decode scope"><button class="btn small" data-scope="section" aria-pressed="${evidenceScope === "section"}">Selected section</button><button class="btn small" data-scope="merged" aria-pressed="${evidenceScope === "merged"}">Merged table</button><span class="meta">Section: fields + bytes · Merged: SDK tree + XML</span></div><div class="view-tabs" role="group" aria-label="Evidence view">${["tree", "hex", "xml", "metadata", "references"].map((v) => `<button class="${view === v ? "active" : ""}" data-view="${v}" aria-pressed="${view === v}">${v === "tree" ? "Structure" : v === "hex" ? "Hex bytes" : v === "xml" ? xmlLabel : v === "metadata" ? "Metadata" : "References"}</button>`).join("")}</div>${view === "tree" ? '<div class="tree-toolbar"><input type="search" id="tree-search" placeholder="Find field or value…" aria-label="Search section structure"><button class="btn small" id="expand-tree" title="Expand all displayed nodes">＋</button><button class="btn small" id="collapse-tree" title="Collapse all nodes">−</button></div><div class="tree-help" id="tree-help">↑ ↓ Navigate · ← → Fold / enter · Home / End · Type to find</div><div class="tree-area" id="tree-area" role="tree" aria-label="Section structure" aria-describedby="tree-help"></div>' : view === "metadata" ? metadataPanel() : view === "references" ? referencePanel() : `<pre class="evidence" tabindex="0" aria-label="${view === "hex" ? "Section hex dump" : xmlLabel}">${view === "hex" ? esc(hexDump(detail.raw_hex)) : syntaxXml(xmlSource || "XML unavailable for this scope. Raw bytes remain available.")}</pre>`}<div class="inspector-footer"><span class="meta">Evidence starts at packet ${num(detail.first_packet)}</span><button class="btn" id="edit" ${detail.table_id === 0x42 && detail.valid && detail.services?.length && !busy && !backendFailure && !comparisonEvidence ? "" : "disabled"}>Rename service…</button></div>`;
  $("#section-group")?.addEventListener("toggle", event => { if (event.target.isConnected) sectionGroupOpen = event.target.open; });
  panel.querySelectorAll("[data-scope]").forEach(el => el.onclick = () => { evidenceScope = el.dataset.scope; renderInspector(); });
  panel.querySelectorAll("[data-section-id]").forEach(el => el.onclick = () => inspect(el.dataset.sectionId));
  $("#group-show-bad")?.addEventListener("click", () => { showBadCrc = !showBadCrc; renderList(); renderInspector(); $("#section-group").open = true; });
  $("#epg-language")?.addEventListener("change", e => { epgLanguage=e.target.value; renderList(); renderInspector(); $("#epg-language")?.focus(); });
  $("#identifier-query")?.addEventListener("click", async () => {
    const value=$("#identifier-value").value.trim(), output=$("#identifier-result");
    if(!/^(?:0x[0-9a-f]+|[0-9]+)$/i.test(value) || !Number.isSafeInteger(Number(value))){output.textContent="Enter a whole decimal or hexadecimal ID.";return;}
    try {identifierResult=await call("lookup_identifier",{namespace:$("#identifier-kind").value,value:Number(value),standards:detail.standards_context || "auto"});output.textContent=JSON.stringify(identifierResult,null,2);}
    catch(error){output.textContent=String(error);}
  });
  $("#satellite-query")?.addEventListener("click", async () => {
    const value=$("#satellite-position").value.trim(), output=$("#satellite-result"), evidence=$("#satellite-evidence");
    satelliteResult=null; evidence.textContent="";
    if(!/^(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)$/.test(value) || Number(value)>180){output.textContent="Enter degrees from 0 to 180.";return;}
    output.textContent="Looking up candidates…";
    try {
      const result=await call("lookup_satellite",{orbital_position_degrees:Number(value),direction:$("#satellite-direction").value});
      if(!output.isConnected)return;
      satelliteResult=result; output.textContent=satelliteText(result);evidence.textContent=JSON.stringify(result,null,2);
    } catch(error){output.textContent=String(error);}
  });
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
      const expand = (node, parent = "", index = 0) => {
        const path = parent ? parent + "/" + (node.id ?? index) : node.id;
        if (node.children) { openNodes.add(path); node.children.forEach((child, i) => expand(child, path, i)); }
      };
      expand(sectionTree());
      renderTree();
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
function packetForBin(index, bins, packets) {
  if (packets <= 1 || bins < 2) return 0;
  return Math.max(
    0,
    Math.min(packets - 1, Math.round((index * (packets - 1)) / (bins - 1))),
  );
}
function binForPacket(packet, bins, packets) {
  if (packets <= 1 || bins < 2) return 0;
  return Math.max(
    0,
    Math.min(bins - 1, Math.round((packet * (bins - 1)) / (packets - 1))),
  );
}
let pendingSnapshotTimer = null;
function snapshotAtBin(bin, bins, packets, immediate) {
  const target = packetForBin(bin, bins, packets);
  if (immediate) {
    clearTimeout(pendingSnapshotTimer);
    pendingSnapshotTimer = null;
    snapshot(target);
    return;
  }
  // Key auto-repeat coalesces; the last requested position wins.
  clearTimeout(pendingSnapshotTimer);
  pendingSnapshotTimer = setTimeout(() => {
    pendingSnapshotTimer = null;
    snapshot(target);
  }, 140);
}
function renderTimeline() {
  const bins = (data.density || []).length || 80;
  const packets = Number(data.packets || 0);
  // A query response re-renders the strip and replaces the focused slider, so
  // remember whether the user was operating it and restore focus afterwards.
  const sliderHadFocus = document.activeElement?.id === "density";
  const dense = data.density || Array.from({ length: bins }, () => ({ count: 0, bad: 0 }));
  const at = data.selected_packet === null || data.selected_packet === undefined ? null : Number(data.selected_packet);
  const cursorPercent = at === null ? null : packets > 1 ? Math.min(100, (at / (packets - 1)) * 100) : 100;
  const interactive = data.complete && !busy && !backendFailure;
  const middle = packets > 1 ? Math.round((packets - 1) / 2) : 0;
  $("#timeline").innerHTML =
    `<div class="timeline-top"><span class="panel-title">OCCURRENCE DENSITY</span><span class="meta">${num(bins)} packet-position bins <span class="legend-valid">■</span> sections <span class="neg">■</span> invalid</span><span class="spacer"></span><button class="btn small" id="compare-snapshots" ${busy || backendFailure || !data.complete ? "disabled" : ""}>Compare snapshots</button><button class="btn small" id="latest" ${busy || backendFailure || !data.complete ? "disabled" : ""}>Latest state</button></div><div class="density" id="density" role="slider" tabindex="${interactive ? 0 : -1}" aria-label="Snapshot position in this transport stream" aria-valuemin="0" aria-valuemax="${Math.max(0, packets - 1)}" aria-valuenow="${at === null ? 0 : at}" aria-valuetext="${at === null ? "Latest observed state" : "Snapshot at packet " + num(at)}" ${interactive ? "" : 'aria-disabled="true"'}>${cursorPercent === null ? "" : `<span class="bin-cursor" style="left:${cursorPercent}%" aria-hidden="true"></span>`}<div class="bins">${dense.map((b, index) => `<div class="bin ${b.bad && b.count && b.bad >= b.count ? "invalid" : ""}" data-bin="${index}" style="--density-alpha:${b.count ? 0.35 + Math.min(0.65, b.count / 50) : 0.12}${b.bad && b.count ? `;--invalid:${Math.min(1, b.bad / b.count)}` : ""}" title="Bin ${index + 1} · ${num(b.count)} sections · ${num(b.bad)} invalid${interactive ? " · click to load this position" : ""}">${b.bad ? '<span class="bin-invalid" aria-hidden="true"></span>' : ""}</div>`).join("")}</div>${arrivalAxis(0, Math.max(0, packets - 1))}</div><div class="history"><span class="meta">0</span>${(
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
  // Align the cursor with the real bin geometry; the percentage is the fallback
  // used before layout or while the strip is hidden.
  const cursor = $("#density .bin-cursor");
  const binElements = [...document.querySelectorAll("#density .bin")];
  if (cursor && at !== null && binElements.length && packets > 1) {
    const element = binElements[binForPacket(at, bins, packets)];
    if (element && element.offsetWidth)
      cursor.style.left = element.offsetLeft + element.offsetWidth / 2 + "px";
  }
  if (sliderHadFocus) $("#density")?.focus({ preventScroll: true });
  $("#compare-snapshots").onclick = () => { changeTab("Changes"); render(); $("#compare-from").focus(); };
  $("#density").addEventListener("click", (event) => {
    const bin = event.target.closest("[data-bin]");
    if (!bin || !interactive) return;
    snapshotAtBin(Number(bin.dataset.bin), bins, packets, true);
  });
  $("#density").addEventListener("keydown", (event) => {
    if (!interactive) return;
    const keys = ["ArrowLeft", "ArrowRight", "Home", "End"];
    if (!keys.includes(event.key)) return;
    event.preventDefault();
    // Same mapping as the cursor and bin clicks, so one step always moves by at
    // least one packet and End reaches the declared maximum.
    const current = at === null ? bins - 1 : binForPacket(at, bins, packets);
    const next = event.key === "Home" ? 0 : event.key === "End" ? bins - 1
      : Math.max(0, Math.min(bins - 1, current + (event.key === "ArrowRight" ? 1 : -1)));
    snapshotAtBin(next, bins, packets, false);
  });
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
// Stable IDs and semantic tree paths are the UI debugging contract. Never
// accept arbitrary JavaScript, shell commands, edit/export actions or selectors.
function uiState() {
  const bounds = (el) => { const r = el.getBoundingClientRect(); return {x:r.x,y:r.y,width:r.width,height:r.height}; };
  const visible = (el) => !!el.getClientRects().length && !el.closest("[hidden]") && getComputedStyle(el).visibility !== "hidden";
  const tree = [...document.querySelectorAll("#tree-area [data-node-path]")].filter(visible).slice(0,2500).map(el => {
    const row = el.querySelector(":scope > .tree-row") || el;
    const label = row.querySelector(".node-label"), value = row.querySelector(".node-value");
    return {path:el.dataset.nodePath,label:label?.textContent,value:value?.textContent || "",kind:value?.dataset.valueKind || "meta",
      branch:el.classList.contains("tree-node"),closed:el.getAttribute("aria-expanded") === "false",bounds:bounds(row),
      label_color:label ? getComputedStyle(label).color : "", value_color:value ? getComputedStyle(value).color : "",
      glyph:getComputedStyle(row,"::before").content,glyph_color:getComputedStyle(row,"::before").color};
  });
  return {schema_version:1,frontend:env.runtime === "cloud-browser" ? "web" : "tauri",captured_at:new Date().toISOString(),
    settled:!busy && !loadingDetail && !comparison.loading && pending.size === 0 && !pendingSnapshotTimer,
    runtime:{driver:env.driver,user_agent:navigator.userAgent},viewport:{width:innerWidth,height:innerHeight,device_pixel_ratio:devicePixelRatio},
    source:data.source || "",analysis_status:data.analysis_status || "idle",selected,selected_service:selectedService,packet:data.selected_packet,
    theme, explorer:explorerRows().map(row=>{const el=[...document.querySelectorAll(".explorer-row")].find(el=>el.dataset.explorerKey===explorerKey(row));return {...row,selected:explorerSelected(row),color:el ? getComputedStyle(el.querySelector("[data-table-name]")).color : "",glyph:el?.querySelector(".pid-table-icon").textContent};}), table_filter:{pid:pidFilter ?? -1,name:filter,count_unit:"logical_tables"},
    tab,inspector:view,tree_search:treeSearch,focused_tree_path:document.activeElement?.dataset.nodePath || "",tree,tree_limit:2500,
    controls:[...document.querySelectorAll("[id]")].slice(0,1000).map(el=>({id:el.id,visible:visible(el),enabled:!el.disabled,focused:el===document.activeElement,
      text:(el.getAttribute("aria-label") || el.value || el.textContent || "").slice(0,512),bounds:bounds(el)})),controls_limit:1000,
    diagnostics:{pending:pending.size,error:backendFailure || detailError,recent_responses:recentResponses.slice(),frontend_errors:frontendErrors.slice()},
    source_map:{tree:"ui/tauri/web/app.js:sectionTree/drawNode",style:"ui/tauri/web/style.css",transport:"ui/tauri/src-tauri/src/main.rs"}};
}
function uiAction(action) {
  if (action.name === "select_tab" && ["Services","Tables","EPG","Issues","Changes"].includes(action.value)) {
    const target = [...document.querySelectorAll("[data-tab]")].find(el=>el.dataset.tab===action.value);
    if (!target) throw new Error("Tab unavailable"); target.click();
  } else if (action.name === "set_theme" && ["dark","light"].includes(action.value)) {
    if (theme !== action.value) $("#theme-toggle").click();
  } else if (action.name === "search_tree" && typeof action.value === "string" && action.value.length <= 512) {
    treeSearch=action.value; const field=$("#tree-search"); if(field) field.value=treeSearch; renderTree();
  } else if (["focus_tree","toggle_tree"].includes(action.name)) {
    const target=[...document.querySelectorAll("#tree-area [data-node-path]")].find(el=>el.dataset.nodePath===action.path && el.getClientRects().length && !el.closest("[hidden]"));
    if (!target) throw new Error("Visible tree path not found");
    if(action.name === "toggle_tree") {
      if(!target.classList.contains("tree-node") || treeSearch.trim()) throw new Error("Only an unfiltered branch can be toggled");
      setTreeExpanded(target,target.getAttribute("aria-expanded")!=="true");
    }
    document.querySelectorAll('#tree-area [tabindex="0"]').forEach(el=>el.tabIndex=-1);
    target.tabIndex=0;focusTreeItem(target);
  } else throw new Error("Unsupported UI action");
  return {accepted:true};
}
async function captureUi() {
  if (env.runtime === "cloud-browser") throw new Error("Browser preview: use the browser screenshot tool together with showpsisi.getUiState(); native screenshot export requires the desktop app.");
  // Paint the latest local navigation before capturing the actual WebView pixels.
  await new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));
  return invoke("save_diagnostics",{state:uiState()});
}
$("#save-diagnostics").onclick=async()=>{
  try { const result=await captureUi(); notice("Diagnostics saved: " + result.directory); }
  catch(error) { notice("Diagnostics failed: " + String(error)); }
};
async function pollUiAgent() {
  try {
    const request=await invoke("agent_next");
    if(request) {
      let result;
      try { result=request.method==="snapshot" ? uiState() : request.method==="capture" ? await captureUi() : uiAction(request.params || {}); }
      catch(error) { result={error:String(error)}; }
      await invoke("agent_reply",{id:request.id,result});
    }
  } catch(error) { console.error("UI agent transport stopped",error); return; }
  setTimeout(pollUiAgent,100);
}
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
    recentResponses.push({id:msg.id, method:job.method, ok:!msg.error, error:msg.error?.message || "", at:new Date().toISOString()});
    if (recentResponses.length > 40) recentResponses.shift();
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
  if (env.agent_enabled) pollUiAgent();
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
  getUiState: uiState,
};
boot().catch((error) => {
  disconnectBackend("Backend connection failed: " + String(error));
});
