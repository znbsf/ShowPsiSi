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
const tip = (key) => `title="${esc(glossary[key] || key)}"`;
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
  activeAnalyze = null;
let aggregateDiagnostic = null;
let backendFailure = "";
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
<header class="titlebar"><span class="app-mark" aria-hidden="true">≋</span><strong>ShowPsiSi</strong><span class="title-separator">/</span><span class="workspace-name">Transport stream workbench</span><span class="spacer"></span><span class="runtime" id="runtime">Connecting backend</span><button class="btn quiet" id="api">Agent API</button></header>
<div class="sourcebar"><label for="source">SOURCE</label><input id="source" placeholder="Open a local .ts, .mts or .m2ts file" spellcheck="false"><select id="standards" aria-label="Signalling standards context" title="Explicit native decoder context; auto uses detected signalling, not RF delivery system"><option value="auto">Standards: Auto</option><option value="dvb">DVB</option><option value="atsc">ATSC</option><option value="isdb">ISDB</option><option value="isdb-japan">ISDB Japan</option><option value="isdb-brazil">ISDB Brazil</option><option value="scte">SCTE</option></select><input id="extra-pids" placeholder="Extra PIDs (optional)" aria-label="Additional monitored PIDs, decimal or hexadecimal, comma separated" title="Additional monitored PIDs, decimal or hexadecimal, separated by commas"><button class="btn" id="browse">Open file…</button><button class="btn primary" id="scan">Analyze</button></div>
<div class="stats" id="stats"></div>
<main class="panes" id="panes"><nav class="sidebar" aria-label="Table library"><div class="panel-title">EXPLORER <span class="muted" title="Program Specific Information / Service Information">PSI / SI</span></div><div id="sidebar"></div><div class="extension" id="extension"></div><div class="sidebar-help">Ctrl / ⌘ K <span>Search records</span><br>↑ ↓ <span>Navigate records</span><br>← → <span>Expand tree</span></div></nav><div class="splitter" id="split-left" role="separator" aria-label="Resize explorer" aria-orientation="vertical" tabindex="0"></div><section class="center" aria-label="Stream records"><div class="tabs" id="tabs" role="tablist" aria-label="Record type"></div><div class="searchbar"><span aria-hidden="true">⌕</span><input id="search" type="search" placeholder="Search services, IDs, providers…" aria-label="Search records"><span id="result-count"></span></div><div id="service-head"></div><div class="list" id="list" role="listbox" aria-label="Stream records"></div><div class="pagination"><span id="page-label"></span><span class="spacer"></span><button class="btn small" id="prev" aria-label="Previous page">←</button><button class="btn small" id="next" aria-label="Next page">→</button></div></section><div class="splitter" id="split-right" role="separator" aria-label="Resize inspector" aria-orientation="vertical" tabindex="0"></div><aside class="inspector" aria-label="Section inspector" id="inspector"></aside></main>
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
  $("#status-dot").classList.toggle("error", error);
  $("#notice").classList.toggle("error", error);
}
function disableBackendActions() {
  if (!backendFailure) return;
  document
    .querySelectorAll(
      "#scan,#browse,#api,#source,#standards,#extra-pids,#edit,#preview,#export,#latest,[data-history]",
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
  loadingDetail = false;
  activeAnalyze = null;
  ++inspectEpoch;
  ++queryEpoch;
  for (const job of pending.values()) {
    clearTimeout(job.timer);
    job.reject(new Error(backendFailure));
  }
  pending.clear();
  preview = {};
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
      ["inspect", "query", "capabilities"].includes(method) &&
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
  busy = true;
  ++queryEpoch;
  selectionReset();
  data = {};
  preview = {};
  filter = "";
  page = 0;
  historyPage = 0;
  firstPaint = false;
  completePaint = false;
  render();
  notice("Analyzing stream… incremental results appear below");
  try {
    data = await call("analyze", {
      path,
      standards: $("#standards").value,
      ...(extraPids.length ? { extra_pids: [...new Set(extraPids)] } : {}),
    });
    render();
    defaultInspect();
    notice(
      "Analysis complete · " +
        num(data.packets) +
        " packets · source unchanged",
    );
  } catch (error) {
    notice(String(error), true);
  } finally {
    busy = false;
    activeAnalyze = null;
    render();
  }
}
async function inspect(id, sid = -1, key = "") {
  if (backendFailure) return;
  if (!id) {
    notice("Aggregate diagnostic: packet locations are not indexed.");
    return;
  }
  aggregateDiagnostic = null;
  const epoch = ++inspectEpoch;
  const atPacket = data.selected_packet;
  selected = id;
  selectedService = sid;
  selectedKey = key || id;
  detail = {};
  loadingDetail = true;
  detailError = "";
  openNodes.clear();
  treeSearch = "";
  renderInspector();
  renderList();
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
      busy ? "Analyzing…" : data.complete ? "Complete" : "No source",
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
      return `<button class="nav ${filter === (t === "All tables" ? "" : t) ? "active" : ""}" data-filter="${esc(t)}" ${tip(t)}><span class="table-icon" aria-hidden="true">${t === "All tables" ? "▦" : "◇"}</span><span class="family-label">${esc(t)}</span><span class="count">${num(count)}</span></button>`;
    })
    .join("");
  $("#sidebar")
    .querySelectorAll("button")
    .forEach(
      (el) =>
        (el.onclick = () => {
          filter = el.dataset.filter === "All tables" ? "" : el.dataset.filter;
          tab = "Tables";
          page = 0;
          render();
        }),
    );
  $("#extension").innerHTML =
    `<div class="panel-title">DESCRIPTOR EXTENSION</div><strong>${esc(data.extension_id || "No extension reported")}</strong><p>Schema extensions use their declared scope. Native decoding follows the table context; raw evidence is retained.</p>`;
  $("#tabs").innerHTML = ["Services", "Tables", "EPG", "Issues"]
    .map(
      (t) =>
        `<button role="tab" aria-selected="${tab === t}" tabindex="${tab === t ? 0 : -1}" class="${tab === t ? "active" : ""}" data-tab="${t}" ${tip(t)}>${t}${t === "Issues" && data.diagnostics?.length ? ` <span class="tab-count">${num(data.diagnostics.length)}</span>` : ""}</button>`,
    )
    .join("");
  $("#tabs")
    .querySelectorAll("button")
    .forEach((el) => {
      el.onclick = () => {
        tab = el.dataset.tab;
        page = 0;
        render();
      };
      el.onkeydown = (e) => {
        if (["ArrowLeft", "ArrowRight"].includes(e.key)) {
          e.preventDefault();
          const buttons = [...$("#tabs").children];
          const next =
            buttons[
              (buttons.indexOf(el) + (e.key === "ArrowRight" ? 1 : 3)) % 4
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
    data.selected_packet != null
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
        body = `<span class="table-kind" ${tip(r.name)}>${esc(r.name)}</span><div class="record-name"><strong>PID <span class="numeric">${hex(r.pid)}</span></strong><small>Version ${r.version} · section ${r.section}/${r.last_section} · ${num(r.bytes)} B</small></div><span class="numeric muted">${num(r.count)}×</span><span class="${r.valid ? "ok" : "bad"}" title="${r.valid ? "Valid section" : "Invalid section"}">${r.valid ? "●" : "⚠"}</span>`;
      if (tab === "EPG")
        body = `<div class="record-name"><strong>${esc(r.title)}</strong><small>SID ${hex(r.service_id)} · ${esc(r.start)} UTC · ${num(r.duration_seconds / 60)} min</small></div><span class="muted numeric">${hex(r.id)}</span>`;
      if (tab === "Issues")
        body = `<span class="bad">⚠</span><div class="record-name"><strong>${esc(r.code)}</strong><small>${esc(r.detail)}</small><small>${r.aggregate ? "Aggregate across monitored SI PIDs" : "PID " + hex(r.pid) + " · packet " + num(r.packet)} · ${num(r.count)} observations</small></div>`;
      return `<div role="option" aria-selected="${selectedKey === key}" tabindex="${selectedKey === key || (!selectedKey && i === 0) ? 0 : -1}" class="record ${tab.toLowerCase()} ${selectedKey === key ? "selected" : ""}" data-row="${i}" data-key="${esc(key)}">${body}</div>`;
    })
    .join("");
  if (!rows.length)
    $("#list").innerHTML =
      `<div class="empty"><span class="empty-icon">${busy ? "◌" : data.source ? "⌕" : "▦"}</span><h3>${busy ? "Reading transport stream…" : !data.source ? "Explore your transport stream" : search ? "No matching records" : "No " + tab.toLowerCase() + " in this state"}</h3><p>${!data.source ? "Open a TS file to inspect PSI/SI tables, decoded fields and their original bytes." : search ? "Try another name, decimal identifier or hexadecimal value." : "Choose another table family or packet snapshot."}</p></div>`;
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
function drawNode(node, parent = "", index = 0, ancestorMatch = false) {
  const path = parent ? parent + "/" + (node.id ?? index) : node.id;
  const needle = treeSearch.trim().toLowerCase();
  const selfMatch = (node.label + " " + (node.value ?? ""))
    .toLowerCase()
    .includes(needle);
  if (needle && !ancestorMatch && !nodeMatches(node, needle)) return "";
  if (++treeNodesRendered > 2500) return "";
  const label = `<span class="node-label ${node.tone || ""}" title="${esc(fieldHelp[node.label] || node.label)}">${highlightedTreeText(node.label)}</span>${node.value !== undefined ? `<span class="node-value">${highlightedTreeText(node.value)}</span>` : ""}`;
  if (!node.children)
    return `<div class="tree-leaf" tabindex="0">${label}</div>`;
  const opened = !!needle || openNodes.has(path);
  return `<details class="tree-node" data-path="${esc(path)}" ${opened ? "open" : ""}><summary>${label}<span class="node-count">${num(node.children.length)}</span></summary><div class="tree-children">${node.children.length ? node.children.map((child, i) => drawNode(child, path, i, ancestorMatch || (!!needle && selfMatch))).join("") : '<div class="tree-empty">No decoded fields</div>'}</div></details>`;
}
function renderTree() {
  const area = $("#tree-area");
  if (!area) return;
  treeNodesRendered = 0;
  area.innerHTML =
    drawNode(sectionTree()) ||
    '<p class="tree-empty">No matching fields or values.</p>';
  if (treeNodesRendered > 2500)
    area.insertAdjacentHTML(
      "beforeend",
      '<p class="tree-empty">Tree display limited to 2,500 nodes. Narrow the field search; full evidence remains available in raw/XML views and the Agent API.</p>',
    );
  area.querySelectorAll("details").forEach((el) =>
    el.addEventListener("toggle", () => {
      if (!treeSearch) {
        if (el.open) openNodes.add(el.dataset.path);
        else openNodes.delete(el.dataset.path);
      }
    }),
  );
  area.onkeydown = (e) => {
    const target = e.target;
    if (
      ![
        "ArrowRight",
        "ArrowLeft",
        "ArrowUp",
        "ArrowDown",
        "Home",
        "End",
      ].includes(e.key)
    )
      return;
    const focusable = [...area.querySelectorAll("summary,.tree-leaf")].filter(
      (el) => el.getClientRects().length,
    );
    const index = focusable.indexOf(target);
    if (index < 0) return;
    e.preventDefault();
    if (e.key === "ArrowRight") {
      if (target.tagName === "SUMMARY") {
        if (!target.parentElement.open) target.parentElement.open = true;
        else focusable[index + 1]?.focus();
      }
    } else if (e.key === "ArrowLeft") {
      if (target.tagName === "SUMMARY" && target.parentElement.open)
        target.parentElement.open = false;
      else
        target.parentElement
          .closest(".tree-children")
          ?.parentElement.querySelector("summary")
          ?.focus();
    } else
      focusable[
        e.key === "Home"
          ? 0
          : e.key === "End"
            ? focusable.length - 1
            : Math.max(
                0,
                Math.min(
                  focusable.length - 1,
                  index + (e.key === "ArrowDown" ? 1 : -1),
                ),
              )
      ]?.focus();
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
          `<section class="reference"><a data-reference href="${esc(ref.url)}" target="_blank" rel="noopener noreferrer">${esc(ref.title || ref.id || "Specification")} <span class="external-label">Open</span></a><p class="meta">${esc(ref.version || "")} · ${esc(ref.scope || "standard-level")}</p>${ref.access ? `<p>${esc(ref.access)}</p>` : ""}${ref.notes ? `<p>${esc(ref.notes)}</p>` : ""}<div class="reference-url">${esc(ref.url)}</div><button class="btn small" data-copy-reference="${esc(ref.url)}">Copy URL</button></section>`,
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
    panel.innerHTML = `<div class="panel-title">SECTION INSPECTOR</div><div class="empty"><span class="empty-icon">${loadingDetail ? "◌" : detailError ? "⚠" : "⌘"}</span><h3>${loadingDetail ? "Loading section…" : detailError ? "Unable to inspect section" : "Inspect the signal"}</h3><p>${esc(detailError || "Select a service, table, programme or issue to explore its source section.")}</p>${detailError && !backendFailure ? '<button class="btn" id="retry-inspect">Retry</button>' : ""}</div>`;
    $("#retry-inspect")?.addEventListener("click", () =>
      inspect(selected, selectedService, selectedKey),
    );
    return;
  }
  panel.innerHTML = `<div class="panel-title">SECTION INSPECTOR <span class="${detail.valid ? "ok" : "bad"}">${detail.valid ? "VALID" : "INVALID"}</span></div><div class="inspector-heading"><h2 ${tip(detail.name)}>${esc(detail.name)} <span>/ v${detail.version}</span></h2><span class="numeric">${hex(detail.pid)} PID</span></div><p class="meta">Section ${detail.section}/${detail.last_section} · ${num(detail.bytes)} bytes · ${num(detail.count)} observations${reportedStandards(detail) ? " · " + esc(reportedStandards(detail)) : ""}${selectedService >= 0 ? " · SID " + hex(selectedService) : ""}</p>${detail.native_table_at_packet != null ? `<p class="meta native-evidence" id="native-assembly-evidence">Native assembly cutoff: packet ${num(detail.native_table_at_packet)}${detail.native_decode_status ? " · " + esc(detail.native_decode_status) : ""}</p>` : ""}<div class="view-tabs" role="group" aria-label="Evidence view">${["tree", "hex", "xml", "references"].map((v) => `<button class="${view === v ? "active" : ""}" data-view="${v}" aria-pressed="${view === v}">${v === "tree" ? "Structure" : v === "hex" ? "Hex bytes" : v === "xml" ? "TSDuck XML" : "References"}</button>`).join("")}</div>${view === "tree" ? '<div class="tree-toolbar"><input type="search" id="tree-search" placeholder="Find field or value…" aria-label="Search section structure"><button class="btn small" id="expand-tree" title="Expand all displayed nodes">＋</button><button class="btn small" id="collapse-tree" title="Collapse all nodes">−</button></div><div class="tree-area" id="tree-area" aria-label="Section structure"></div>' : view === "references" ? referencePanel() : `<pre class="evidence" tabindex="0" aria-label="${view === "hex" ? "Section hex dump" : "TSDuck XML"}">${esc(view === "hex" ? hexDump(detail.raw_hex) : detail.tsduck_xml || "XML unavailable for this section. Raw bytes remain available.")}</pre>`}<div class="inspector-footer"><span class="meta">Evidence starts at packet ${num(detail.first_packet)}</span><button class="btn" id="edit" ${detail.table_id === 0x42 && detail.valid && detail.services?.length && !busy && !backendFailure ? "" : "disabled"}>Rename service…</button></div>`;
  panel.querySelectorAll("[data-view]").forEach(
    (el) =>
      (el.onclick = () => {
        view = el.dataset.view;
        renderInspector();
      }),
  );
  if (view === "tree") {
    $("#tree-search").value = treeSearch;
    $("#tree-search").oninput = (e) => {
      treeSearch = e.target.value;
      renderTree();
    };
    renderTree();
    $("#expand-tree").onclick = () => {
      $("#tree-area")
        .querySelectorAll("details")
        .forEach((el) => {
          el.open = true;
          openNodes.add(el.dataset.path);
        });
    };
    $("#collapse-tree").onclick = () => {
      openNodes.clear();
      treeSearch = "";
      $("#tree-search").value = "";
      renderTree();
    };
  }
  panel.querySelectorAll("[data-reference]").forEach(
    (el) =>
      (el.onclick = async (event) => {
        if (env.runtime === "cloud-browser") return;
        event.preventDefault();
        try {
          await invoke("open_reference", { url: el.href });
        } catch (error) {
          notice(
            "Could not open reference: " + String(error) + ". Use Copy URL.",
            true,
          );
        }
      }),
  );
  panel.querySelectorAll("[data-copy-reference]").forEach(
    (el) =>
      (el.onclick = async () => {
        try {
          await navigator.clipboard.writeText(el.dataset.copyReference);
          notice("Reference URL copied");
        } catch (error) {
          notice(
            "Clipboard unavailable. Select and copy the URL shown under the reference.",
            true,
          );
        }
      }),
  );
  $("#edit").onclick = openEdit;
}
function renderTimeline() {
  $("#timeline").innerHTML =
    `<div class="timeline-top"><span class="panel-title">OCCURRENCE DENSITY</span><span class="meta">80 packet-position bins <span class="legend-valid">■</span> sections <span class="bad">■</span> invalid</span><span class="spacer"></span><button class="btn small" id="latest" ${busy || backendFailure || !data.source ? "disabled" : ""}>Latest state</button></div><div class="bins">${(data.density || Array.from({ length: 80 }, () => ({ count: 0, bad: 0 }))).map((b) => `<div class="bin ${b.bad ? "invalid" : ""}" style="--density:${b.count ? 0.3 + Math.min(0.7, b.count / 50) : 0.08}" title="${num(b.count)} sections · ${num(b.bad)} invalid"></div>`).join("")}</div><div class="history"><span class="meta">0</span>${(
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
  if (backendFailure) return;
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
  if (backendFailure || !editTarget) return;
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
    $("#preview").disabled = !!backendFailure;
  }
};
$("#export").onclick = async () => {
  if (backendFailure || !preview.token || !editTarget) return;
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
    notice(
      "Exported " + num(result.bytes) + " bytes + manifest · " + result.path,
    );
    $("#edit-dialog").close();
  } catch (error) {
    $("#diff").textContent = String(error);
    $("#export").disabled = !!backendFailure;
  }
};
$("#scan").onclick = scan;
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
$("#prev").onclick = () => {
  page--;
  renderList();
  $("#list").scrollTop = 0;
};
$("#next").onclick = () => {
  page++;
  renderList();
  $("#list").scrollTop = 0;
};
document.addEventListener("keydown", (e) => {
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
    e.preventDefault();
    $("#search").focus();
    $("#search").select();
  }
});
function splitter(id, property, min, max, direction) {
  const el = $(id);
  const width = () =>
    parseFloat(getComputedStyle($("#panes")).getPropertyValue(property));
  const set = (value) => {
    const bounded = Math.max(min, Math.min(max, value));
    $("#panes").style.setProperty(property, bounded + "px");
    el.setAttribute("aria-valuenow", Math.round(bounded));
  };
  el.setAttribute("aria-valuemin", min);
  el.setAttribute("aria-valuemax", max);
  el.setAttribute("aria-valuenow", width());
  el.onpointerdown = (e) => {
    const start = e.clientX,
      initial = width();
    el.setPointerCapture(e.pointerId);
    el.onpointermove = (move) =>
      set(initial + (move.clientX - start) * direction);
    el.onpointerup = () => {
      el.onpointermove = null;
    };
  };
  el.onkeydown = (e) => {
    if (["ArrowLeft", "ArrowRight"].includes(e.key)) {
      e.preventDefault();
      set(width() + (e.key === "ArrowRight" ? 16 : -16) * direction);
    }
  };
}
splitter("#split-left", "--explorer-width", 140, 300, 1);
splitter("#split-right", "--inspector-width", 300, 780, -1);
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
      if (busy && msg.request_id === activeAnalyze && msg.state) {
        data = msg.state;
        render();
      }
      return;
    }
    const job = pending.get(msg.id);
    if (!job) return;
    pending.delete(msg.id);
    clearTimeout(job.timer);
    if (msg.error) job.reject(new Error(msg.error.message));
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
  snapshot,
  inspect,
  call,
  getState: () => data,
  getDetail: () => detail,
};
boot().catch((error) => {
  disconnectBackend("Backend connection failed: " + String(error));
});
