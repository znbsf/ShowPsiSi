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
let allTableHistory = false, historyIdentity = "";
let showBadCrc = false, evidenceScope = "merged", groupedTables = true;
let inspectorDetails = workbench.inspectorDisclosure();
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
function arrivalAxis(first, last, timing = data.timing, timeline = false) {
  const scale = Number(timing?.seconds_per_packet);
  const timed = scale > 0 && timing?.basis === "user supplied bitrate";
  return `<div class="arrival-axis" aria-label="${timed ? 'Estimated seconds from supplied bitrate, not PCR' : 'Packet positions'}">${[0, .25, .5, .75, 1].map(f => {
    const packet = Math.round(first + (last-first)*f);
    return `<span>${timed ? (packet*scale).toFixed(3)+' s' : '#'+num(packet)}</span>`;
  }).join('')}</div><div class="axis-basis" ${!timed && timeline ? 'title="No PCR/TDT clock is used; positions are packet indices."' : ''}>${timed ? 'Estimated elapsed seconds · user supplied 188-byte TS bitrate · not PCR time' : timeline ? 'Axis: packet index' : 'Zero-based packet positions · no measured time available'}</div>`;
}
function distributionPanel(row) {
  const d = row.distribution;
  if (!d) return '';
  const bins = d.bins || [], max = Math.max(1, ...bins.map(b => b.count));
  return `<div class="arrival" id="arrival-details" data-inspector-content="arrival" ${inspectorDetails.arrival ? "" : "hidden"}><p class="meta">Arrival · first #${num(d.first_packet)} → last #${num(d.last_packet)} · ${num(d.observation_count)}×</p><p class="meta">Packet positions, not PCR time. ${d.first_seconds != null ? `Estimated ${Number(d.first_seconds).toFixed(3)}–${Number(d.last_seconds).toFixed(3)} s · ${esc(d.basis)}` : 'Time unavailable without a bitrate estimate.'}</p><p class="meta">Gaps (packets): min ${d.min_gap_packets == null ? '—' : num(d.min_gap_packets)} · mean ${d.mean_gap_packets == null ? '—' : Number(d.mean_gap_packets).toFixed(1)} · max ${d.max_gap_packets == null ? '—' : num(d.max_gap_packets)}</p><div class="section-density" aria-label="Selected section occurrence density">${bins.map(b => `<span class="${b.bad ? 'invalid' : ''}" style="--height:${b.count ? Math.max(2, 100*b.count/max) : 0}%" title="Packets ${num(b.from_packet)}–${num(b.to_packet)}: ${num(b.count)} observations, ${num(b.bad)} invalid"></span>`).join('')}</div>${arrivalAxis(bins[0]?.from_packet || 0, bins.at(-1)?.to_packet || 0)}</div>`;
}
const tip = (key) => `title="${esc((tableLabels[key] ? key + " · " : "") + (glossary[key] || key))}"`;
let documentMode=false, documentWorkspace=null;
let siView = null, summaryView = null, summaryVisible = false, classicMode = true, candidatePending = false, classicFrame = null, classicConfiguration = false, classicToolbar = true, classicStatus = true, classicTree = true;
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
let pausePending = "", pauseSequence = 0, progressFrame = null, queuedProgress = null;
let resultPages = {}, resultPageEpoch = 0, resultLoading = false;
const resultCollections = ["tables", "table_groups", "services", "events", "diagnostics", "history", "table_history", "density"];
const recentResponses = [];
const messages = [];
let messageTimer = null, activeWarning = null;
const frontendErrors = [];
function recordFrontendError(error) {
  frontendErrors.push({at:new Date().toISOString(),message:String(error?.stack || error).slice(0,2048)});
  if(frontendErrors.length > 20) frontendErrors.shift();
}
window.addEventListener("error", event=>recordFrontendError(event.error || event.message));
window.addEventListener("unhandledrejection", event=>recordFrontendError(event.reason));
let aggregateDiagnostic = null;
let backendFailure = "";
let completedScanOptions = null;
let comparison = { from: null, to: null, kind: "all", filters: [], result: null, error: "", loading: false, epoch: 0 };
let savedWorkspace = null, comparisonEvidence = "", inspectionEvidence = null;
let firstPaint = false,
  completePaint = false,
  preview = {},
  editTarget = null,
  exportPending = false,
  treeSearch = "",
  openNodes = new Set(),
  view = "tree";
// Independent semantic selection, keyboard focus and evidence activation.
let topology = {snapshot:null,family:'all',search:'',expanded:{},limits:{},selected:'',focused:'',active:null,resolution:null,
  loading:false,error:'',stale:false,epoch:0,cutoff:null,label:'',origin:'',workspace:null,history:[],revealed:false,scroll:0};
function workspaceCutoff() { return data.selected_packet ?? Math.max(0,(data.packets || 1)-1); }
function topologyCutoff() { return topology.cutoff ?? workspaceCutoff(); }
function inspectionState() { return {selected,selectedService,selectedKey,detail,detailError,aggregateDiagnostic,treeSearch,openNodes:new Set(openNodes),view,inspectionEvidence,comparisonEvidence,evidenceScope,analysisRevision:data.revision,workspacePacket:workspaceCutoff(),wasLoading:loadingDetail}; }
function restoreInspectionState(saved) {
  ++inspectEpoch; loadingDetail=false;
  if(saved && (saved.analysisRevision===undefined || saved.analysisRevision===data.revision) && (saved.workspacePacket===undefined || saved.workspacePacket===workspaceCutoff())) {
    ({selected,selectedService,selectedKey,detail,detailError,aggregateDiagnostic,treeSearch,openNodes,view,inspectionEvidence}=saved);
    comparisonEvidence=saved.comparisonEvidence || '';evidenceScope=saved.evidenceScope || evidenceScope;
    if(saved.wasLoading && selected) {const epoch=inspectEpoch;queueMicrotask(()=>{if(epoch===inspectEpoch)inspect(selected,selectedService,selectedKey,inspectionEvidence);});}
  } else {selectionReset();inspectionEvidence=null;comparisonEvidence='';}
}
function resetTopology() {
  topology={snapshot:null,family:'all',search:'',expanded:{},limits:{},selected:'',focused:'',active:null,resolution:null,
    loading:false,error:'',stale:false,epoch:topology.epoch+1,cutoff:null,label:'',origin:'',workspace:null,history:[],revealed:false,scroll:0};
}
async function loadTopology(more=false) {
  if(busy || cancelling || backendFailure || !data.complete || topology.loading) return;
  const epoch=++topology.epoch,revision=data.revision,cutoff=topologyCutoff();
  const offset=more ? topology.snapshot?.page?.next_offset : 0;
  if(more && offset==null) return;
  topology.loading=true;topology.error='';topology.stale=!!topology.snapshot && !more;
  renderList();renderInspector();
  try {
    const result=await call('query_topology',{at_packet:cutoff,analysis_revision:revision,offset,limit:500});
    if(epoch!==topology.epoch || revision!==data.revision || cutoff!==topologyCutoff()) return;
    const error=workbench.validateTopology(result,revision,cutoff);if(error)throw new Error(error);
    topology.snapshot=more?workbench.mergeTopology(topology.snapshot,result):result;
    topology.stale=false;
    if(!more) (result.projections || []).forEach(p=>p.roots.forEach(id=>{if(topology.expanded[id]===undefined)topology.expanded[id]=true;}));
    if(topology.selected && !workbench.topologyNodes(topology.snapshot).some(n=>n.node_id===topology.selected)) topology.error='The previous object is not observed in this loaded snapshot. Its name has not been substituted.';
  } catch(error) {
    if(epoch!==topology.epoch)return;
    topology.error=String(error);topology.stale=!!topology.snapshot;
  } finally {
    if(epoch===topology.epoch) {topology.loading=false;if(tab==='Topology'){renderList();renderInspector();}}
  }
}
function topologyNode(id=topology.selected) { return workbench.topologyNodes(topology.snapshot || {}).find(n=>n.node_id===id); }
function topologyRemember() {
  topology.history.push({selected:topology.selected,focused:topology.focused,active:topology.active,resolution:topology.resolution,inspection:inspectionState(),scroll:$('#list').scrollTop,expanded:{...topology.expanded},limits:{...topology.limits},search:topology.search,family:topology.family});
  if(topology.history.length>100)topology.history.shift();
}
function selectTopology(id,remember=true) {
  if(!topologyNode(id))return;
  if(remember && topology.selected && (topology.selected!==id || topology.active))topologyRemember();
  ++inspectEpoch;loadingDetail=false;topology.active=null;topology.resolution=null;topology.selected=id;
  let n=topologyNode(id),seen={};while(n?.parent_id && !seen[n.parent_id]){seen[n.parent_id]=true;topology.expanded[n.parent_id]=true;topology.limits[n.parent_id]=Number.MAX_SAFE_INTEGER;n=topologyNode(n.parent_id);}
  renderList();renderInspector();
}
function topologyBack() {
  if(topology.history.at(-1)?.kind==='selection') {selectionBack();return;}
  if(topology.revealed) {topology.revealed=false;tab='Topology';search=topology.search;$('#search').value=search;render();$('#list').scrollTop=topology.scroll;$('#topology-show-table')?.focus({preventScroll:true});return;}
  if(topology.active) {const ref=topology.active,node=topologyNode(),index=node?workbench.topologyEvidence(node,topology.snapshot.edges).findIndex(item=>item.ref===ref):-1;++inspectEpoch;loadingDetail=false;topology.active=null;topology.resolution=null;renderInspector();if(index>=0)$('#inspector [data-topology-source="'+index+'"]')?.focus({preventScroll:true});return;}
  const previous=topology.history.pop();
  if(previous) {Object.assign(topology,{selected:previous.selected,focused:previous.focused,active:previous.active,resolution:previous.resolution,expanded:previous.expanded,limits:previous.limits,search:previous.search,family:previous.family});search=topology.search;$('#search').value=search;restoreInspectionState(previous.inspection);renderList();renderInspector();$('#list').scrollTop=previous.scroll;}
  else if(topology.origin==='Changes') {changeTab('Changes');render();}
}
// Reference selections share the existing navigation stack and Alt+Left route.
function selectionBack() {
  if(busy || loadingDetail || backendFailure)return;
  const saved=topology.history.pop();if(!saved || saved.kind!=='selection')return;
  if(saved.inspection.analysisRevision!==data.revision || saved.inspection.workspacePacket!==workspaceCutoff())return;
  ({tab,filter,pidFilter,search,page,groupedTables,showBadCrc,explorerFocusKey,historyPage,historyIdentity}=saved);
  Object.assign(topology,saved.topology);
  savedWorkspace=saved.workspace;protocolResolution=saved.protocolResolution;
  restoreInspectionState(saved.inspection);$('#search').value=search;render();
  $('#list').scrollTop=saved.listScroll;$('#inspector').scrollTop=saved.inspectorScroll;
  const row=[...$('#tree-area')?.querySelectorAll('[role="treeitem"]') || []].find(el=>el.dataset.nodePath===saved.path);
  if(row)focusTreeItem(row);else if(!saved.path)$('#list [tabindex="0"]')?.focus({preventScroll:true});if($('#tree-area'))$('#tree-area').scrollTop=saved.treeScroll;
}
async function jumpReference(target,path) {
  if(!target || busy || loadingDetail || backendFailure)return;
  const saved={kind:'selection',inspection:inspectionState(),tab,filter,pidFilter,search,page,groupedTables,showBadCrc,explorerFocusKey,historyPage,historyIdentity,
    workspace:savedWorkspace,protocolResolution,protocolDepth:protocolSourceHistory.length,
    topology:{active:topology.active,resolution:topology.resolution,revealed:topology.revealed,sourceWorkspace:topology.sourceWorkspace},
    listScroll:$('#list').scrollTop,inspectorScroll:$('#inspector').scrollTop,treeScroll:$('#tree-area')?.scrollTop || 0,path};
  changeTab(target.kind==='service'?'Services':'Tables');
  topology.history.push(saved);if(topology.history.length>100)topology.history.shift();
  topology.active=null;topology.resolution=null;topology.revealed=false;
  search='';$('#search').value='';page=0;view='tree';evidenceScope='section';
  let key=target.id;
  if(target.kind==='service') {
    const service=data.services.find(s=>s.id===target.sid && s.source_id===target.id && s.key===target.key);
    key=rowIdentity(service);page=Math.max(0,Math.floor(recordRows().findIndex(s=>rowIdentity(s)===key)/PAGE_SIZE));
  } else {
    selectExplorer({pid:target.pid,name:target.name});groupedTables=false;
    if(data.tables?.find(row=>row.id===target.id)?.crc?.status==='invalid')showBadCrc=true;
    page=Math.max(0,Math.floor(recordRows().findIndex(r=>r.id===target.id)/PAGE_SIZE));
  }
  await inspect(target.id,target.sid,key);
  render();$('#tree-area [role="treeitem"][tabindex="0"]')?.focus({preventScroll:true});
}
async function inspectTopologyEvidence(ref) {
  if(busy || backendFailure || topology.stale || !topology.snapshot)return;
  if(ref.analysis_revision!==data.revision || ref.at_packet!==topology.snapshot.at_packet) {topology.error='Source evidence context differs from this topology snapshot.';renderInspector();return;}
  topology.active=ref;topology.resolution=null;evidenceScope='section';view='tree';
  await inspect(ref.section_id,-1,'topology:'+topology.selected+':'+ref.assertion_key,
    {kind:'topology',atPacket:ref.at_packet,label:(topology.label || 'Topology')+' · packet '+num(ref.at_packet),ref,nodeId:topology.selected});
}
let protocolSourceHistory=[],protocolResolution=null,protocolVisibleSources=[],protocolSourceLimits={};
function activeSourceResolution() { return inspectionEvidence?.kind==='protocol'?protocolResolution:inspectionEvidence?.kind==='topology'?topology.resolution:null; }
async function inspectProtocolSource(item,buttonId) {
  if(!item.available || busy || backendFailure)return;
  if(item.ref.analysis_revision!==data.revision){notice('Source belongs to a stale analysis revision.',true);return;}
  protocolSourceHistory.push({inspection:inspectionState(),offset:protocolCardOffset,key:protocolCardKey,limits:{...protocolSourceLimits},listScroll:$('#list').scrollTop,historyPage,historyIdentity,scroll:$('#inspector').scrollTop,metadataScroll:$('.metadata-panel')?.scrollTop || 0,openDetails:[...$('#inspector').querySelectorAll('details')].map((d,i)=>d.open?i:-1).filter(i=>i>=0),buttonId,resolution:protocolResolution});
  if(protocolSourceHistory.length>100)protocolSourceHistory.shift();
  protocolResolution=null;evidenceScope='section';view='tree';
  await inspect(item.ref.section_id,-1,'protocol:'+item.ref.assertion_key,{kind:'protocol',ref:item.ref,atPacket:item.ref.at_packet,label:'Protocol source · packet '+num(item.ref.at_packet)});
}
function protocolSourceHeader() {
  if(inspectionEvidence?.kind!=='protocol')return '';
  const ref=inspectionEvidence.ref;
  return `<div class="topology-source-context"><button class="btn small" id="protocol-back">← Back to summary</button><details><summary>Protocol source · cutoff #${num(ref.at_packet)} · revision ${num(ref.analysis_revision)}</summary><p class="meta topology-source-id">${esc(ref.section_id)}</p><p>${esc(ref.assertion_key)} · ${esc(ref.locator?.precision || 'section')}</p></details><p id="protocol-locator-status" role="status">${esc(loadingDetail?'Locating source…':detailError || protocolResolution?.message || 'Source resolution pending.')}</p></div>`;
}
function bindProtocolSource() {
  $('#protocol-back')?.addEventListener('click',()=>{
    const saved=protocolSourceHistory.pop();if(!saved)return;
    restoreInspectionState(saved.inspection);protocolResolution=saved.resolution;protocolCardOffset=saved.offset;protocolCardKey=saved.key;protocolSourceLimits=saved.limits;
    // Cross-table evidence changes both the row selection and selected-table history.
    // Restore those rendered panels too, without changing the user's filters or cutoff.
    renderList();$('#list').scrollTop=saved.listScroll;
    historyPage=saved.historyPage;historyIdentity=saved.historyIdentity;renderTimeline();
    renderInspector();$('#inspector').querySelectorAll('details').forEach((d,i)=>d.open=saved.openDetails.includes(i));$('#inspector').scrollTop=saved.scroll;if($('.metadata-panel'))$('.metadata-panel').scrollTop=saved.metadataScroll;document.getElementById(saved.buttonId)?.focus({preventScroll:true});
  });
  document.querySelectorAll('[data-protocol-more]').forEach(button=>button.onclick=()=>{const id=button.dataset.protocolMore,scroll=$('.metadata-panel').scrollTop;protocolSourceLimits[id]=(protocolSourceLimits[id] || 100)+100;renderInspector();const more=document.querySelector('[data-protocol-more="'+id+'"]');more?.closest('details').setAttribute('open','');$('.metadata-panel').scrollTop=scroll;more?.focus({preventScroll:true});});
  document.querySelectorAll('[data-protocol-source]').forEach(button=>button.onclick=()=>inspectProtocolSource(protocolVisibleSources[Number(button.dataset.protocolSource)],button.id));
}
function sourceContextHeader() { return inspectionEvidence?.kind==='protocol'?protocolSourceHeader():topologySourceHeader(); }
function topologySourceHeader() {
  if(!topology.active || !(tab==='Topology' || topology.revealed))return '';
  const ref=topology.active,locator=ref.locator || {},resolution=topology.resolution,sourceId=detail.id || ref.section_id;
  const canReveal=ref.at_packet===workspaceCutoff() && ref.analysis_revision===data.revision && !loadingDetail && !detailError;
  return `<div class="topology-source-context"><div><button class="btn small" id="topology-back">← ${topology.revealed?'Back to Topology':'Back to object'}</button><strong>${esc(ref.assertion_key)}</strong><button class="btn small" id="topology-show-table" ${canReveal?'':'disabled'} title="${canReveal?'Reveal this exact section without changing the snapshot':'Tables reveal requires the same workspace cutoff; source inspection remains available here'}">Show in Tables</button></div><details><summary>Source evidence · cutoff #${num(ref.at_packet)} · revision ${num(ref.analysis_revision)}</summary><p class="meta topology-source-id">Exact section: ${esc(sourceId)}${sourceId!==ref.section_id?'<br>Original assertion: '+esc(ref.section_id):''}</p><p>${esc(locator.display_path || '')} · ${esc(ref.role || '')}<br>Workspace stays at #${num(workspaceCutoff())}${ref.at_packet!==workspaceCutoff()?' · Tables reveal unavailable at a different workspace cutoff.':''}</p></details><p id="topology-locator-status" role="status">${esc(loadingDetail?'Locating exact source…':resolution?.message || detailError || 'Exact section requested; locator resolution pending.')}${evidenceScope==='merged'?' Source anchor applies only to Selected section.':''}</p></div>`;
}
function bindTopologySourceHeader() {
  $('#topology-back')?.addEventListener('click',topologyBack);
  $('#topology-show-table')?.addEventListener('click',()=>{
    if(!topology.active || topology.active.at_packet!==workspaceCutoff())return;
    topology.scroll=$('#list').scrollTop;topology.revealed=true;tab='Tables';filter='';pidFilter=null;search='';$('#search').value='';showBadCrc=true;
    const sourceId=detail.id || topology.active.section_id;
    const model=workbench.tables(data,null,'',true,''),group=model.groups.find(g=>g.section_ids.includes(sourceId));
    if(group){openTableGroups.add(group.id);page=Math.floor(model.groups.indexOf(group)/PAGE_SIZE);}else {groupedTables=false;page=Math.max(0,Math.floor(model.sections.findIndex(r=>r.id===sourceId)/PAGE_SIZE));}
    render();requestAnimationFrame(()=>[...$('#list').querySelectorAll('[data-key]')].find(e=>e.dataset.key===sourceId)?.scrollIntoView({block:'nearest'}));
  });
}
function renderTopologyInspector() {
  const node=topologyNode(),snapshot=topology.snapshot,panel=$('#inspector');
  panel.innerHTML=`<div class="panel-title">OBJECT INSPECTOR <span class="muted">TOPOLOGY</span></div>${topology.history.length || topology.origin==='Changes'?'<div class="topology-actions"><button class="btn small" id="topology-back">← Back</button></div>':''}${topology.error?`<p class="topology-warning" role="status">${esc(topology.stale?'Stale topology · ':'')}${esc(topology.error)}</p>`:''}${node?`<div class="inspector-heading"><h2>${esc(node.label)}</h2></div><p class="meta identity-line">${esc(node.object_type.replace(/_/g,' '))} · ${esc(workbench.topologyStatus(node))}</p><div class="topology-summary"><h3>Identity</h3>${topologyDefinition(node.identity)}<p class="meta">Profile: ${esc(snapshot.interpretation_profile)} · snapshot #${num(snapshot.at_packet)}</p><h3>Relationships</h3>${(snapshot.edges || []).filter(e=>e.from===node.node_id || e.to===node.node_id).map(e=>{const target=topologyNode(e.from===node.node_id?e.to:e.from);return `<div class="topology-relation"><span>${e.from===node.node_id?'→':'←'} ${esc(e.relation)} · ${esc(e.resolution_status)}</span>${target?`<button class="btn small" data-topology-target="${esc(target.node_id)}">${esc(target.label)}</button>`:`<span class="meta">${esc(e.from===node.node_id?e.to:e.from)} · object not loaded</span>`}</div>`;}).join('') || '<p class="meta">No resolved relationships supplied.</p>'}<h3>Sources</h3><div class="topology-sources">${workbench.topologyEvidence(node,snapshot.edges).map((item,i)=>{const ref=item.ref,t=ref.table_identity || {};return `<button class="btn topology-source" data-topology-source="${i}" ${topology.stale || busy || backendFailure?'disabled':''}><strong>${esc(ref.assertion_key)}${item.relation?' · '+esc(item.relation):''}</strong><span>PID ${hex(t.pid)} · TID ${hex(t.table_id,2)} · ${esc(workbench.wireVersionText(t))} · ${esc(workbench.wireSectionText(t))}</span><span>${esc(ref.role || '')} · ${esc(ref.locator?.precision || 'section')} · #${num(ref.at_packet)}</span></button>`;}).join('') || '<p class="meta">No source references supplied for this object.</p>'}</div>${node.unresolved_reasons?.length?`<h3>Unknowns and conflicts</h3><ul>${node.unresolved_reasons.map(r=>`<li>${esc(typeof r==='string'?r:JSON.stringify(r))}</li>`).join('')}</ul>`:''}${(node.reference_sources || []).length?`<details class="topology-attributes"><summary>Catalog reference sources · not wire evidence</summary>${node.reference_sources.map(source=>topologyDefinition(source)).join('')}</details>`:''}${Object.keys(node.attributes || {}).length?`<details class="topology-attributes"><summary>Additional attributes</summary>${topologyDefinition(node.attributes)}</details>`:''}<p class="meta topology-boundary">Signalling observations do not establish physical reception or playable media.</p></div>`:`<div class="empty"><h3>${topology.loading?'Loading topology…':'Select a semantic object'}</h3><p>Select an object to see its identity, relationships and all source evidence. Arrow keys move focus without changing your selection.</p></div>`}`;
  $('#topology-back')?.addEventListener('click',topologyBack);
  panel.querySelectorAll('[data-topology-target]').forEach(el=>el.onclick=()=>selectTopology(el.dataset.topologyTarget));
  const refs=node?workbench.topologyEvidence(node,snapshot.edges):[];
  panel.querySelectorAll('[data-topology-source]').forEach(el=>el.onclick=()=>inspectTopologyEvidence(refs[Number(el.dataset.topologySource)].ref));
}
function topologyDefinition(values) {
  return '<dl class="topology-definition">'+Object.keys(values || {}).map(key=>`<div><dt>${esc(workbench.topologyFieldLabel(key))}</dt><dd>${esc(values[key] && typeof values[key]==='object'?JSON.stringify(values[key]):workbench.value(key,values[key]))}</dd></div>`).join('')+'</dl>';
}
function renderTopology() {
  const snapshot=topology.snapshot || {},nodes=workbench.topologyNodes(snapshot),list=$('#list'),hadFocus=list.contains(document.activeElement),scroll=topology.restoreScroll?topology.scroll:list.scrollTop;topology.restoreScroll=false;
  const model=workbench.topologyRows(snapshot,topology.family,topology.search,topology.expanded,topology.limits);
  const families=snapshot.projections || [],loaded=nodes.length,total=snapshot.counts?.nodes ?? snapshot.page?.total ?? loaded;
  $('#table-filter-tools').innerHTML=families.length>1?`<select id="topology-family" aria-label="Topology view family"><option value="all">All observed families</option>${families.map(p=>`<option value="${esc(p.family)}" ${topology.family===p.family?'selected':''}>${esc(p.label)}</option>`).join('')}</select>`:'';
  $('#topology-family')?.addEventListener('change',e=>{topology.family=e.target.value;renderTopology();});
  $('#result-count').textContent=topology.search?num(model.matched)+' matching loaded objects':num(loaded)+' / '+num(total)+' objects loaded';
  $('#service-head').innerHTML=`<div class="topology-context"><strong>${esc(topology.label || (families.length===1?families[0].label:'Signal topology'))}</strong><span>${snapshot.at_packet!=null?'Observed through packet #'+num(snapshot.at_packet):'Snapshot pending'} · ${esc(snapshot.interpretation_profile || 'context pending')}</span>${topology.label?`<span>Workspace stays at #${num(workspaceCutoff())}</span>`:''}</div>${snapshot.coverage?`<details class="topology-coverage" ${topology.coverageOpen?'open':''}><summary>Coverage · ${esc(snapshot.status)} · ${num(snapshot.counts?.raw_sections)} raw sections retained</summary>${topologyDefinition(snapshot.coverage)}${(snapshot.diagnostics || []).length?`<p>${snapshot.diagnostics.map(d=>esc(typeof d==='string'?d:JSON.stringify(d))).join('<br>')}</p>`:''}</details>`:''}${topology.error?`<p class="topology-warning" role="status">${esc(topology.stale?'Stale · ':'')}${esc(topology.error)} <button class="btn small" id="retry-topology" ${topology.loading || backendFailure?'disabled':''}>Retry</button></p>`:''}${snapshot.page?.has_more?'<p class="meta topology-loaded-note">Search covers loaded objects only. Load more to search the remaining objects; ancestor context is retained.</p>':''}`;
  $('#retry-topology')?.addEventListener('click',()=>loadTopology());
  $('.topology-coverage')?.addEventListener('toggle',e=>{if(e.target.isConnected)topology.coverageOpen=e.target.open;});
  $('#page-label').textContent=(topology.loading?'Loading… · ':'')+num(model.total)+' loaded objects in this view · '+(snapshot.counts?num(snapshot.counts.unresolved)+' unresolved in snapshot':'unresolved count pending');
  $('#prev').disabled=true;$('#next').disabled=true;
  list.setAttribute('role','tree');list.setAttribute('aria-label','Semantic signal topology');list.setAttribute('aria-busy',String(topology.loading));
  const visible=model.rows.filter(r=>!r.more);
  if(!visible.some(r=>r.node.node_id===topology.focused))topology.focused=visible[0]?.node.node_id || '';
  list.innerHTML=model.rows.map(row=>row.more?`<div class="topology-more" style="--level:${row.depth}"><button class="btn small" data-topology-more="${esc(row.parent_id || '$roots')}">Show ${Math.min(100,row.remaining)} more child objects · ${num(row.remaining)} remaining</button></div>`:(()=>{const n=row.node;return `<div role="treeitem" aria-level="${row.depth}" ${row.has_children?`aria-expanded="${row.expanded}"`:''} aria-selected="${topology.selected===n.node_id}" tabindex="${topology.focused===n.node_id?0:-1}" class="topology-row ${topology.selected===n.node_id?'selected':''}" data-topology-node="${esc(n.node_id)}" data-parent="${esc(row.parent_id || '')}" style="--level:${row.depth}" aria-label="${esc(n.label+' · '+workbench.topologyStatus(n))}"><span class="topology-disclosure" data-topology-fold="${esc(n.node_id)}" aria-hidden="true">${row.has_children?(row.expanded?'▾':'▸'):'·'}</span><span class="topology-object"><strong>${esc(n.label)}</strong><small title="${esc(workbench.topologyIdentityDetails(n))}">${esc(workbench.topologyIdentity(n) || n.object_type.replace(/_/g,' '))}</small></span><span class="topology-state">${esc(workbench.topologyStatus(n))}</span><span class="topology-count" title="Source references for this object and related relationships">${num(workbench.topologyEvidence(n,snapshot.edges).length)} sources</span></div>`;})()).join('') || `<div class="empty"><h3>${topology.loading?'Loading semantic objects…':topology.search?'No matching loaded objects':'No semantic relationships in this context'}</h3><p>${busy?'Wait for analysis to complete.':!data.complete?'Analyze a transport stream to begin.':`Retained ${num(snapshot.counts?.raw_sections ?? data.tables?.length)} raw sections. Tables remains available; an empty topology does not mean no signal or decoding failure.`}</p></div>`;
  if(snapshot.page?.has_more)list.insertAdjacentHTML('beforeend',`<div class="topology-load"><button class="btn" id="topology-load-more" ${topology.loading || backendFailure?'disabled':''}>${topology.loading?'Loading…':'Load next objects'} (${num(loaded)} / ${num(total)})</button></div>`);
  $('#topology-load-more')?.addEventListener('click',()=>loadTopology(true));
  list.querySelectorAll('[data-topology-more]').forEach(el=>el.onclick=()=>{const id=el.dataset.topologyMore;topology.limits[id]=(topology.limits[id] || 100)+100;renderTopology();});
  const items=[...list.querySelectorAll('[data-topology-node]')];
  const focus=(id)=>{const el=items.find(e=>e.dataset.topologyNode===id);if(el){topology.focused=id;items.forEach(e=>e.tabIndex=e===el?0:-1);el.focus({preventScroll:true});el.scrollIntoView({block:'nearest'});}};
  const fold=(id,open)=>{topology.expanded[id]=open;renderTopology();};
  items.forEach(el=>{
    const id=el.dataset.topologyNode;
    el.onfocus=()=>{topology.focused=id;items.forEach(e=>e.tabIndex=e===el?0:-1);};
    el.onclick=e=>{if(e.target.closest('[data-topology-fold]') && el.hasAttribute('aria-expanded')){fold(id,el.getAttribute('aria-expanded')!=='true');return;}topology.focused=id;selectTopology(id);[...list.querySelectorAll('[data-topology-node]')].find(e=>e.dataset.topologyNode===id)?.focus();};
    el.onkeydown=e=>{
      const index=items.indexOf(el),expanded=el.getAttribute('aria-expanded')==='true',branch=el.hasAttribute('aria-expanded');
      if(['ArrowUp','ArrowDown','Home','End','ArrowLeft','ArrowRight','Enter',' '].includes(e.key))e.preventDefault();
      if(e.key==='ArrowUp' || e.key==='ArrowDown')focus(items[Math.max(0,Math.min(items.length-1,index+(e.key==='ArrowDown'?1:-1)))].dataset.topologyNode);
      else if(e.key==='Home' || e.key==='End')focus(items[e.key==='Home'?0:items.length-1].dataset.topologyNode);
      else if(e.key==='ArrowRight' && branch){if(!expanded)fold(id,true);else focus(items[index+1]?.dataset.topologyNode);}
      else if(e.key==='ArrowLeft'){if(branch && expanded)fold(id,false);else focus(el.dataset.parent);}
      else if(e.key==='Enter' || e.key===' ')selectTopology(id);
      else if(e.key.length===1 && !e.ctrlKey && !e.metaKey && !e.altKey){const now=Date.now();topology.typed=now-(topology.typedAt || 0)<700?(topology.typed || '')+e.key.toLowerCase():e.key.toLowerCase();topology.typedAt=now;const ordered=items.slice(index+1).concat(items.slice(0,index+1));const found=ordered.find(x=>x.getAttribute('aria-label').toLowerCase().startsWith(topology.typed));if(found){e.preventDefault();focus(found.dataset.topologyNode);}}
    };
  });
  list.scrollTop=scroll;if(hadFocus)focus(topology.focused);
}
function openComparisonTopology(side,label) {
  changeTab('Topology');++topology.epoch;topology.loading=false;topology.cutoff=side.at_packet;topology.label='Comparison '+label;topology.active=null;topology.snapshot=null;topology.selected='';topology.focused='';topology.history=[];render();loadTopology();
}

const PAGE_SIZE = 100;
const recordTabs = ["Services", "Topology", "Tables", "EPG", "Issues", "Changes"];
const commandTable = [
  {id:"analyze",description:"Analyze",keys:"Ctrl Enter",reason:()=>paletteBackendReason() || (!$("#source").value.trim()?"Choose a source first":""),run:()=>$("#scan").click()},
  {id:"open",description:"Open…",keys:"Ctrl O",reason:()=>paletteBackendReason(),run:()=>$("#browse").click()},
  {id:"export",description:"Export…",keys:"",reason:()=>!data.complete?"Analyze a source before exporting":paletteBackendReason() || editBlockReason(),run:()=>$("#edit")?.click()},
  {id:"compare",description:"Compare snapshots",keys:"",reason:()=>paletteBackendReason() || (!data.complete?"Analyze a source before comparing snapshots":""),run:()=>$("#compare-snapshots")?.click()},
  {id:"latest",description:"Latest state",keys:"",reason:()=>paletteBackendReason() || (!data.complete?"Analyze a source to view its latest state":""),run:()=>snapshot(-1)},
  {id:"theme",description:"Toggle theme",keys:"",run:()=>$("#theme-toggle").click()},
  {id:"layout",description:"Reset layout",keys:"",run:()=>$("#reset-layout").click()},
  {id:"help",description:"Shortcut help",keys:"? / Ctrl+/",run:showShortcutHelp},
  ...recordTabs.map(next=>({id:"tab-"+next.toLowerCase(),description:next,keys:"",run:()=>{$('#tabs [data-tab="'+next+'"]').click();}}))
];
const shortcutTable = [
  {keys:"↑ ↓ Home End",description:"Move focus in lists and trees"},
  {keys:"Enter / Space",description:"Select the focused item"},
  {keys:"Ctrl K",description:"Search records"},
  commandTable.find(row=>row.id==="open"),
  commandTable.find(row=>row.id==="analyze"),
  {keys:"Ctrl+.",description:"Cancel active scan"},
  {keys:"F6 / Shift+F6",description:"Next / previous region"},
  {keys:"Alt ←",description:"Back"},
  {keys:"Ctrl+Enter (Structure)",description:"Go to the focused field's reference"},
  {keys:"← → on divider",description:"Resize focused pane"},
  commandTable.find(row=>row.id==="help"),
  {keys:"Esc",description:"Close shortcut help"}
];
const shortcutRows = () => shortcutTable.map(row => `<div class="shortcut-row"><kbd>${esc(row.keys)}</kbd><span>${esc(row.description)}</span></div>`).join("");
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
<header class="titlebar"><span class="app-mark" aria-hidden="true">≋</span><strong>ShowPsiSi</strong><span class="title-separator">/</span><select id="input-kind" aria-label="Input kind"><option value="ts">Transport stream</option><option value="dvbi">DVB-I XML</option></select><span class="workspace-name">Transport stream workbench</span><span class="spacer"></span><span class="runtime" id="runtime">Connecting backend</span><span id="layout-status" class="layout-status" role="status"></span><span class="toolbar-group" role="group" aria-label="View"><button class="btn quiet" id="theme-toggle" aria-label="Switch color theme">Light theme</button><button class="btn quiet" id="reset-layout" title="Restore default pane widths. Focus a divider and use arrow keys to resize; Alt+Left navigates back.">Reset layout</button></span><span class="toolbar-group tertiary" role="group" aria-label="Help and diagnostics"><button class="btn quiet" id="about">About</button><button class="btn quiet" id="api" title="Show the local JSONL agent API description">Agent API</button><button class="btn quiet" id="save-diagnostics" title="Save screenshot and UI state, including visible metadata and source paths">Save diagnostics</button></span></header>
<div class="sourcebar" role="region" aria-label="Scan source and options" tabindex="-1"><div class="source-input"><label for="source">SOURCE</label><input id="source" placeholder="Open a local .ts, .mts or .m2ts file" spellcheck="false"><button class="btn" id="browse" aria-label="Open transport stream" title="Open transport stream (Ctrl+O)">Open…</button><div class="recent-files"><button class="btn" id="recent" aria-label="Recent transport streams" aria-haspopup="menu" aria-expanded="false" aria-controls="recent-menu" title="Choose a recently analyzed source without starting analysis">Recent ▾</button><div id="recent-menu" role="menu" aria-label="Recent transport streams" tabindex="-1" hidden></div></div></div><select id="standards" aria-label="Signalling standards context" title="Explicit native decoder context; auto uses detected signalling, not RF delivery system"><option value="auto">Standards: Auto</option><option value="dvb">DVB</option><option value="atsc">ATSC</option><option value="isdb">ISDB</option><option value="isdb-japan">ISDB Japan</option><option value="isdb-brazil">ISDB Brazil</option><option value="scte">SCTE</option><option value="j94-system-b">J.94 (2016) System B</option><option value="dtmb">DTMB</option></select><button class="btn" id="scan-options-toggle" aria-expanded="false" aria-controls="scan-options" aria-label="Scan options"><span>Scan options <span id="scan-options-arrow" aria-hidden="true">▸</span></span><span id="scan-options-summary" hidden></span></button><div class="scan-actions"><button class="btn primary" id="scan">Analyze</button><button class="btn" id="pause-scan" hidden title="Pause without discarding evidence; Resume continues the same scan">Pause</button><button class="btn" id="cancel-scan" hidden title="Cancel active analysis (Ctrl+.); the source file stays unchanged">Cancel</button></div><p id="scan-options-changed" role="status" hidden>Options changed — re-analyze to apply</p><div class="scan-options-fields" id="scan-options" role="group" aria-label="Options for the next scan" hidden><label for="scan-mode">Analysis mode</label><select id="scan-mode" aria-label="Analysis mode"><option value="full">Full scan</option><option value="prefix">Quick preview · prefix</option><option value="range">Quick preview · packet range</option><option value="distributed">Quick preview · distributed windows</option></select><label for="scan-budget-unit">Preview budget</label><select id="scan-budget-unit" aria-label="Preview budget unit"><option value="percent">Percent of source</option><option value="packets">Packet count</option></select><label for="scan-percent">Percent (1–100)</label><input id="scan-percent" type="number" min="1" max="100" step="1" value="10"><label for="scan-budget">Packet budget</label><input id="scan-budget" type="number" min="1" step="1" value="250000"><label for="scan-start">Start packet (inclusive)</label><input id="scan-start" type="number" min="0" step="1" value="0"><label for="scan-end">End packet (exclusive)</label><input id="scan-end" type="number" min="1" step="1" value="250000"><label for="scan-windows">Contiguous windows</label><input id="scan-windows" type="number" min="1" max="16" step="1" value="4"><p class="meta">Preview results are partial and read-only. Distributed mode reads a few large contiguous windows to limit seeks on a mechanical disk.</p><label for="default-charset">Default charset</label><input id="default-charset" placeholder="Default charset" aria-label="Default input charset" title="Optional TSDuck character set for the next scan, e.g. ISO-8859-5 or UTF-8. Digital Video Broadcasting (DVB) selectors take precedence unless a RAW character set is chosen."><label for="extra-pids" title="Additional Packet Identifiers">Extra PIDs</label><input id="extra-pids" placeholder="Extra PIDs (optional)" aria-label="Additional monitored packet identifiers (PIDs), decimal or hexadecimal, comma separated" aria-describedby="extra-pids-error" title="Additional monitored Packet Identifiers (PIDs), decimal or hexadecimal, separated by commas"></div></div>
<div class="sourcebar-feedback" id="source-feedback"><p class="field-error" id="extra-pids-error" hidden></p></div>
<p id="scan-status" class="meta" role="status" hidden></p><p id="scan-coverage" class="meta" hidden></p><div id="result-pages" class="meta" hidden></div><div class="scan-progress" id="scan-progress" role="progressbar" aria-label="Analysis in progress" aria-valuetext="Analyzing" hidden></div>
<div class="stats" id="stats"></div>
<div id="error-banner" role="region" aria-label="Error message" hidden><span id="error-message" tabindex="0" aria-label="Error details"></span><button class="btn small" id="dismiss-error" aria-label="Dismiss error message">Dismiss</button></div>
<main class="panes" id="panes"><nav class="sidebar" aria-label="Table library" tabindex="-1"><div class="panel-title">EXPLORER <span class="muted" title="Program Specific Information / Service Information">PSI / SI</span></div><div id="sidebar"></div><div class="extension" id="extension"></div><details class="sidebar-help"><summary title="Show shortcut help with ? or Ctrl+/">Keyboard shortcuts</summary>${shortcutRows()}</details></nav><div class="splitter" id="split-left" aria-controls="sidebar" title="Drag or use arrow keys to resize. Double-click to reset." role="separator" aria-label="Resize explorer" aria-orientation="vertical" tabindex="0"></div><section class="center" aria-label="Stream records" tabindex="-1"><div class="tabs" id="tabs" role="tablist" aria-label="Record type"></div><div class="searchbar"><span aria-hidden="true">⌕</span><input id="search" type="search" placeholder="Search records · &gt; commands · # PID/SID" aria-label="Search records" role="combobox" aria-autocomplete="list" aria-haspopup="listbox" aria-expanded="false" aria-controls="palette-list" title="Search records · &gt; commands · # PID: Packet Identifier / SID: Service Identifier"><div id="command-palette" hidden><div id="palette-list" role="listbox" aria-label="Commands and identifier targets"></div><p id="palette-empty" class="muted"></p></div><span id="palette-status" class="sr-only" role="status" aria-live="polite" aria-atomic="true"></span><span id="result-count"></span><div id="table-filter-tools" class="table-controls"></div></div><div id="service-head"></div><div class="list" id="list" role="listbox" aria-label="Stream records"></div><div class="pagination"><span id="page-label"></span><span class="spacer"></span><button class="btn small" id="prev" aria-label="Previous page">←</button><button class="btn small" id="next" aria-label="Next page">→</button></div></section><div class="splitter" id="split-right" aria-controls="inspector" title="Drag or use arrow keys to resize. Double-click to reset." role="separator" aria-label="Resize inspector" aria-orientation="vertical" tabindex="0"></div><aside class="inspector" aria-label="Section inspector" id="inspector" tabindex="-1"></aside></main>
<section class="timeline" aria-label="Section occurrence history" id="timeline"></section>
<footer><span class="status-dot" id="status-dot" aria-hidden="true"></span><span id="notice" role="status" aria-live="polite" aria-atomic="true">Open a stream to begin</span><span id="status-warning" hidden><span id="warning-message"></span><button class="btn small" id="dismiss-warning" aria-label="Dismiss warning message">Dismiss</button></span><span id="snapshot-state">LOCAL · SOURCE READ-ONLY</span><button class="btn small" id="messages" aria-label="Messages" aria-haspopup="dialog" aria-controls="messages-dialog" aria-expanded="false">Messages</button></footer>
<dialog id="shortcuts-dialog" aria-labelledby="shortcuts-title"><h2 id="shortcuts-title">Keyboard shortcuts</h2><div class="shortcut-list">${shortcutRows()}</div><div class="actions"><button class="btn" id="close-shortcuts" aria-label="Close shortcut help">Close</button></div></dialog>
<dialog id="messages-dialog" aria-labelledby="messages-title"><h2 id="messages-title">Messages</h2><p id="messages-empty">No messages yet.</p><ol id="message-list" tabindex="0" aria-label="Last 50 messages, newest first"></ol><div class="actions"><button class="btn" id="close-messages" aria-label="Close message history">Close</button></div></dialog>
<dialog id="edit-dialog" aria-labelledby="edit-title"><h2 id="edit-title">Rename service</h2><p>Preview an SDT edit. Export creates a new SI-only TS or raw-section BIN and manifest. TS has no media or PCR; BIN needs its adjacent manifest for PID and source evidence.</p><label for="edit-service">Service</label><select id="edit-service"></select><label for="rename">New service name</label><input id="rename"><button class="btn primary" id="preview">Preview change</button><p id="diff" role="status"></p><label for="export-format">Export format</label><select id="export-format"><option value="ts">TS · SI-only transport stream (.ts)</option><option value="bin">BIN · raw SI sections (.bin)</option></select><div class="actions"><button class="btn" id="export" disabled>Save SI-only TS + manifest…</button><button class="btn" id="close-edit">Close</button></div></dialog>
<dialog id="about-dialog" aria-labelledby="about-title"><h2 id="about-title">About ShowPsiSi</h2><p>Qt and Tauri workbenches share the C++ / TSDuck signal engine.</p><p>Windows installer updates are available in the Qt edition; this frontend opens the official release page.</p><p><a data-project-link href="https://github.com/znbsf/ShowPsiSi" target="_blank" rel="noopener noreferrer">Official source repository</a></p><p><a data-project-link href="https://github.com/znbsf/ShowPsiSi/releases" target="_blank" rel="noopener noreferrer">Official releases and downloads</a></p><p id="about-feedback" role="status"></p><button class="btn" id="close-about">Close</button></dialog>
<dialog id="api-dialog" aria-labelledby="api-title"><h2 id="api-title">Native agent API</h2><pre id="api-text"></pre><button class="btn" id="close-api">Close</button></dialog>`;
let lastDvbiMessage = "";
const dvbiWorkspace=createDvbiWorkspace({call,invoke,status:()=>({busy:busy || exportPending,error:backendFailure}),changed:()=>{
  const state=dvbiWorkspace.getState(), error=state.error || state.inspectError;
  const text=error || (state.importing ? "Loading local document…" : state.loading ? "Loading document objects…" : state.metadata ? "Local document imported · original file unchanged" : "Choose a local XML document");
  if(state.active && text!==lastDvbiMessage){lastDvbiMessage=text;notice(text,error ? "error" : "info");}
  if(!state.active)applyLayout();
}});
$('#input-kind').onchange=e=>dvbiWorkspace.activate(e.target.value==='dvbi');
const RECENT_FILES_KEY = "showpsisi.workbench.recent.v1";
function recentPathKey(path) {
  const key=path.replace(/\\/g,"/");
  return /^(?:[a-z]:\/|\/\/)/i.test(key) ? key.toLowerCase() : key;
}
function normalizeRecentFiles(paths) {
  const seen=new Set();
  return (Array.isArray(paths)?paths:[]).filter(path=>typeof path==="string" && path.trim()).map(path=>path.trim()).filter(path=>{
    const key=recentPathKey(path);if(seen.has(key))return false;seen.add(key);return true;
  }).slice(0,10);
}
let recentFiles=[];
try {recentFiles=normalizeRecentFiles(JSON.parse(localStorage.getItem(RECENT_FILES_KEY)));} catch (_) {}
function saveRecentFiles() {
  try {localStorage.setItem(RECENT_FILES_KEY,JSON.stringify(recentFiles));}
  catch (_) {notice("Recent files saved for this session only.","warning");}
}
function renderRecentFiles() {
  $("#recent-menu").innerHTML=recentFiles.map((path,index)=>`<button type="button" role="menuitem" tabindex="-1" data-recent="${index}" title="${esc(path)}" aria-label="${esc(path)}">${esc(path.split(/[\\/]/).pop())}</button>`).join("") +
    (recentFiles.length?'':'<span class="recent-empty">No recent files</span>') + `<button type="button" role="menuitem" tabindex="-1" id="clear-recent" aria-label="Clear recent files" ${recentFiles.length?'':'disabled'}>Clear recent</button>`;
}
function closeRecentFiles(focus=false) {
  $("#recent-menu").hidden=true;$("#recent").setAttribute("aria-expanded","false");
  if(focus)$("#recent").focus();
}
function openRecentFiles(last=false) {
  renderRecentFiles();$("#recent-menu").hidden=false;$("#recent").setAttribute("aria-expanded","true");
  const items=[...$("#recent-menu").querySelectorAll('button:not(:disabled)')];
  (items[last?items.length-1:0] || $("#recent-menu")).focus();
}
function chooseSource(path) {
  if(busy || exportPending || backendFailure || dvbiWorkspace.getState().importing || document.querySelector("dialog[open]"))return;
  $("#input-kind").value="ts";dvbiWorkspace.activate(false);$("#source").value=path;
  closeRecentFiles();$("#scan").focus();
}
$("#recent").onclick=()=>$("#recent-menu").hidden?openRecentFiles():closeRecentFiles(true);
$("#recent").onkeydown=event=>{if(event.key==='ArrowDown' || event.key==='ArrowUp'){event.preventDefault();openRecentFiles(event.key==='ArrowUp');}};
$("#recent-menu").onclick=event=>{
  const item=event.target.closest('button');if(!item || item.disabled)return;
  if(item.id==='clear-recent'){recentFiles=[];saveRecentFiles();renderRecentFiles();closeRecentFiles(true);}
  else if(item.dataset.recent!==undefined)chooseSource(recentFiles[Number(item.dataset.recent)]);
};
$("#recent-menu").onkeydown=event=>{
  const items=[...$("#recent-menu").querySelectorAll('button:not(:disabled)')],index=items.indexOf(document.activeElement);
  if(['ArrowDown','ArrowUp','Home','End'].includes(event.key)){
    event.preventDefault();event.stopPropagation();
    const next=event.key==='Home'?0:event.key==='End'?items.length-1:(index+(event.key==='ArrowUp'?-1:1)+items.length)%items.length;
    items[next]?.focus();
  } else if(event.key==='Escape'){event.preventDefault();event.stopPropagation();closeRecentFiles(true);}
  else if(event.key==='Tab'){event.preventDefault();closeRecentFiles();$(event.shiftKey?'#browse':'#standards').focus();}
};
document.addEventListener("pointerdown",event=>{if(!event.target.closest('.recent-files'))closeRecentFiles();});
document.addEventListener("focusin",event=>{if(!event.target.closest('.recent-files'))closeRecentFiles();});
renderRecentFiles();
let shortcutReturnFocus=null, shortcutReturnRecent=null;
function showShortcutHelp() {
  if(document.querySelector("dialog[open]"))return;
  shortcutReturnFocus=document.activeElement;
  shortcutReturnRecent=$("#recent-menu").contains(shortcutReturnFocus) ? shortcutReturnFocus.dataset.recent ?? shortcutReturnFocus.id : null;
  closeRecentFiles();$("#shortcuts-dialog").showModal();$("#close-shortcuts").focus();
}
$("#close-shortcuts").onclick=()=>$("#shortcuts-dialog").close();
$("#shortcuts-dialog").addEventListener("keydown",event=>{if(event.key==="Tab"){event.preventDefault();$("#close-shortcuts").focus();}});
$("#shortcuts-dialog").addEventListener("close",()=>{
  const previous=shortcutReturnFocus;shortcutReturnFocus=null;
  if(shortcutReturnRecent!==null){
    const item=shortcutReturnRecent;shortcutReturnRecent=null;openRecentFiles();
    (item==="clear-recent"?$("#clear-recent"):$('[data-recent="'+item+'"]'))?.focus();
  } else if(previous?.isConnected && !previous.disabled)previous.focus({preventScroll:true});
  else ($("#scan").disabled?$("#messages"):$("#scan")).focus();
});
document.addEventListener("keydown",event=>{
  if(event.isComposing || event.defaultPrevented || document.querySelector("dialog[open]"))return;
  const textInput=event.target.isContentEditable || event.target.closest?.('textarea,[role="textbox"]') || event.target.matches?.('input') && !['button','checkbox','color','file','hidden','image','radio','range','reset','submit'].includes(event.target.type);
  const help=event.key==='?' && !event.ctrlKey && !event.metaKey && !event.altKey && !textInput;
  const chord=(event.ctrlKey || event.metaKey) && !event.altKey && !event.shiftKey && (event.key==='/' || event.code==='Slash');
  if(help || chord){event.preventDefault();event.stopPropagation();showShortcutHelp();}
},true);
let nativeFileDrop=false, stopFileDrop=null;
function acceptDroppedPaths(paths) {
  if(!Array.isArray(paths) || paths.length!==1){notice("Drop one local file at a time.");return;}
  const path=paths[0];
  if(typeof path!=="string" || !/^(?:[a-z]:[\\/]|\\\\|\/)/i.test(path)){notice("The platform did not provide a local file path. Use Open… to choose a source.");return;}
  chooseSource(path);
}
document.addEventListener("dragover",event=>{
  if(!event.dataTransfer || ![...event.dataTransfer.types].includes('Files'))return;
  event.preventDefault();event.dataTransfer.dropEffect='copy';
});
document.addEventListener("drop",event=>{
  if(!event.dataTransfer || ![...event.dataTransfer.types].includes('Files'))return;
  event.preventDefault();
  const files=[...event.dataTransfer.files];
  if(env.runtime!=='cloud-browser' && files.length && files.every(file=>typeof file.path==='string' && file.path))acceptDroppedPaths(files.map(file=>file.path));
  else if(!nativeFileDrop)notice("File drop is supported in the desktop app only. Use Open… or enter a local source path.");
});
async function listenForFileDrop() {
  if(env.runtime==='cloud-browser')return;
  try {
    const current=native?.webviewWindow?.getCurrentWebviewWindow?.();
    if(!current?.onDragDropEvent)return;
    stopFileDrop=await current.onDragDropEvent(event=>{if(event.payload.type==='drop')acceptDroppedPaths(event.payload.paths);});
    nativeFileDrop=true;
  } catch (_) {notice("File drop is unavailable. Use Open… to choose a local source.");}
}
window.addEventListener("pagehide",()=>{stopFileDrop?.();stopFileDrop=null;nativeFileDrop=false;});
let theme = "light";
try { theme = localStorage.getItem("showpsisi.theme") === "dark" ? "dark" : "light"; } catch (_) {}
function applyTheme() {
  const effective=classicMode&&$("#input-kind")?.value==="ts"?"light":theme;
  document.documentElement.dataset.theme = effective;
  $("#theme-toggle").textContent = theme === "dark" ? "Light theme" : "Dark theme";
  $("#theme-toggle").setAttribute("aria-pressed", String(theme === "light"));
  document.querySelector('meta[name="color-scheme"]').content = effective;
}
applyTheme();
$("#theme-toggle").onclick = () => {
  theme = theme === "dark" ? "light" : "dark";
  try { localStorage.setItem("showpsisi.theme", theme); } catch (_) {}
  applyTheme();
};
function renderMessages() {
  if (!$("#messages-dialog").open) return;
  const list = $("#message-list"), scroll = list.scrollTop;
  $("#messages-empty").hidden = !!messages.length;
  list.innerHTML = messages.slice().reverse().map(message => `<li><span class="message-level ${message.level}">${message.level}</span><time datetime="${message.at}" title="${message.at}">${esc(new Date(message.at).toLocaleTimeString())}</time><span>${esc(message.text)}</span></li>`).join("");
  list.scrollTop = scroll;
}
function renderWarning() {
  $("#status-warning").hidden = !activeWarning;
  if (!activeWarning) return;
  const text = "⚠ " + activeWarning.text + " ×" + activeWarning.count;
  $("#warning-message").textContent = $("#notice").textContent === activeWarning.text ? "⚠ ×" + activeWarning.count : text;
  $("#warning-message").title = text;
  $("#warning-message").setAttribute("aria-label", text);
}
function notice(text, level = "info") {
  // Retain boolean callers while giving persistent notices an explicit level.
  level = level === true ? "error" : level === false ? "info" : level;
  text = String(text || "");
  if (!text) return;
  clearTimeout(messageTimer);
  messages.push({level, at:new Date().toISOString(), text});
  if (messages.length > 50) messages.shift();
  if (level === "warning") activeWarning = {text, count:activeWarning?.text === text ? activeWarning.count + 1 : 1};
  if (level === "error") {
    activeWarning = null;
    $("#error-message").textContent = text;
    $("#error-banner").hidden = false;
  }
  const line = $("#notice"), dot = $("#status-dot");
  line.setAttribute("aria-live", level === "error" ? "assertive" : "polite");
  line.classList.remove("info-expired");
  line.classList.toggle("error", level === "error");
  line.classList.toggle("warning", level === "warning");
  line.textContent = line.title = text;
  dot.hidden = false;
  dot.classList.toggle("error", level === "error");
  dot.classList.toggle("warning", level === "warning");
  if (level === "info") messageTimer = setTimeout(() => {line.classList.add("info-expired");dot.hidden = true;}, 4000);
  renderWarning();
  renderMessages();
}
$("#dismiss-error").onclick = () => {$("#error-banner").hidden = true;if(document.activeElement === $("#dismiss-error"))$("#messages").focus();};
$("#dismiss-warning").onclick = () => {
  if($("#notice").textContent===activeWarning?.text){$("#notice").classList.add("info-expired");$("#notice").classList.remove("warning");$("#status-dot").hidden=true;}
  activeWarning=null;renderWarning();$("#messages").focus();
};
$("#messages").onclick = () => {$("#messages-dialog").showModal();$("#messages").setAttribute("aria-expanded", "true");renderMessages();$("#close-messages").focus();};
$("#close-messages").onclick = () => $("#messages-dialog").close();
$("#messages-dialog").addEventListener("close", () => {$("#messages").setAttribute("aria-expanded", "false");$("#messages").focus();});
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
function parseExtraPids(text) {
  return text.trim() ? text.split(",").map(value => {
    const token = value.trim();
    if (!/^(0x[0-9a-f]+|[0-9]+)$/i.test(token))
      throw new Error("Extra PIDs must be decimal or hexadecimal integers, separated by commas.");
    const pid = Number(token);
    if (pid > 8191) throw new Error("Extra PIDs must be between 0 and 8191 (0x1FFF).");
    return pid;
  }) : [];
}
function currentScanOptions() {
  let pids = null;
  try { pids = [...new Set(parseExtraPids($("#extra-pids").value))]; } catch (_) {}
  return {standards:$("#standards").value,default_charset:$("#default-charset").value.trim(),extra_pids:pids,scan_mode:$("#scan-mode").value,budget_unit:$("#scan-budget-unit").value,sample_percent:Number($("#scan-percent").value),max_packets:Number($("#scan-budget").value),start_packet:Number($("#scan-start").value),end_packet:Number($("#scan-end").value),window_count:Number($("#scan-windows").value)};
}
function scanIntentKey(options) {
  return JSON.stringify([workbench.scanOptionsKey(options),options.scan_mode,
    ["prefix","distributed"].includes(options.scan_mode) ? [options.budget_unit, options.budget_unit === "percent" ? options.sample_percent : options.max_packets] : null,
    options.scan_mode === "range" ? [options.start_packet,options.end_packet] : null,
    options.scan_mode === "distributed" ? options.window_count : null]);
}
function updateScanOptions() {
  const options = currentScanOptions(), toggle = $("#scan-options-toggle"), summary = $("#scan-options-summary");
  for (const [id,hidden] of [["scan-budget",options.budget_unit === "percent"],["scan-percent",options.budget_unit !== "percent"]]) {
    $("#"+id).hidden = hidden; $('label[for="'+id+'"]').hidden = hidden;
  }
  const text = [workbench.scanOptionsSummary(options), options.scan_mode !== "full" ? options.scan_mode + " preview" + (["prefix","distributed"].includes(options.scan_mode) ? " · " + (options.budget_unit === "percent" ? options.sample_percent + "%" : num(options.max_packets) + " packets") : "") : ""].filter(Boolean).join(" · ");
  summary.textContent = text;
  summary.hidden = !$("#scan-options").hidden || !text;
  toggle.title = "Default charset and extra packet identifiers (PIDs) for the next scan" + (text ? " · " + text : "");
  const changed = data.complete && completedScanOptions && scanIntentKey(options) !== scanIntentKey(completedScanOptions);
  $("#scan-options-changed").hidden = !changed;
  if (changed) $("#scan").setAttribute("aria-describedby", "scan-options-changed");
  else $("#scan").removeAttribute("aria-describedby");
}
function setScanOptionsOpen(open) {
  $("#scan-options").hidden = !open;
  $("#scan-options-toggle").setAttribute("aria-expanded", String(open));
  $("#scan-options-arrow").textContent = open ? "▾" : "▸";
  updateScanOptions();
}
$("#scan-options-toggle").onclick = () => setScanOptionsOpen($("#scan-options").hidden);
$("#standards").addEventListener("change", updateScanOptions);
$("#default-charset").addEventListener("input", updateScanOptions);
$("#extra-pids").addEventListener("input", updateScanOptions);
for (const id of ["scan-mode","scan-budget-unit","scan-percent","scan-budget","scan-start","scan-end","scan-windows"]) $("#"+id).addEventListener("change", updateScanOptions);
function disableBackendActions() {
  if (!backendFailure) return;
  document
    .querySelectorAll(
      "#scan,#pause-scan,#cancel-scan,#browse,#recent,#api,#source,#standards,#default-charset,#extra-pids,#edit,#preview,#export,#latest,#compare-snapshots,#run-comparison,#compare-from,#compare-to,#compare-kind,#swap-comparison,[data-preset],[data-comparison-evidence],[data-history]",
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
  clearProgress(); pausePending = ""; ++resultPageEpoch; resultLoading = false;
  busy = false;
  cancelling = false;
  loadingDetail = false;
  activeAnalyze = null;
  ++scanEpoch;
  ++inspectEpoch;
  ++queryEpoch;
  ++topology.epoch;topology.loading=false;topology.stale=!!topology.snapshot;topology.error=backendFailure;
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
      ["inspect", "query", "query_transport", "query_topology", "query_dvbi", "inspect_dvbi", "diff_snapshots", "capabilities"].includes(method) &&
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
  resetTopology();
  savedWorkspace = null;
  comparisonEvidence = "";
  inspectionEvidence = null;
  if (tab === "Changes") tab = "Services";
  comparison = { from: null, to: null, kind: "all", filters: [], result: null, error: "", loading: false, epoch: comparison.epoch + 1 };
  ++queryEpoch;
  ++resultPageEpoch; resultPages = {}; resultLoading = false;
  clearProgress(); pausePending = ""; ++pauseSequence;
  selectionReset();
  editTarget = null;
  invalidatePreview();
  $("#preview").disabled = !!backendFailure;
  if ($("#edit-dialog").open) $("#edit-dialog").close();
}
// Progress is deliberately a tiny DOM update, never a workbench/tree rebuild.
// Keep only the newest frame for the active generation; terminal and cancel
// clear the scheduled frame before replacing evidence.
function clearProgress() {
  if (progressFrame !== null) cancelAnimationFrame(progressFrame);
  progressFrame = null; queuedProgress = null;
}
function queueProgress(state) {
  queuedProgress = {state, epoch:scanEpoch, requestId:activeAnalyze};
  if (progressFrame !== null) return;
  progressFrame = requestAnimationFrame(() => {
    progressFrame = null;
    const update = queuedProgress; queuedProgress = null;
    if (!update || update.epoch !== scanEpoch || update.requestId !== activeAnalyze || !busy || cancelling || backendFailure) return;
    if(candidatePending){candidatePending=false;resetAnalysisViews();filter="";pidFilter=null;page=0;historyPage=0;}
    data = update.state;
    if ((pausePending === "pause" && data.analysis_status === "paused") ||
        (pausePending === "resume" && ["analyzing","finalizing"].includes(data.analysis_status))) pausePending = "";
    renderScanProgress();
  });
}
function renderScanProgress() {
  const paused = data.analysis_status === "paused", button = $("#pause-scan");
  button.hidden = !busy || activeAnalyze === null;
  button.disabled = cancelling || !!pausePending || activeAnalyze === null || !!backendFailure;
  button.textContent = pausePending === "pause" ? "Pausing…" : pausePending === "resume" ? "Resuming…" : paused ? "Resume" : "Pause";
  button.setAttribute("aria-busy", String(!!pausePending));
  if (resultLoading && activeAnalyze === null) {
    $("#cancel-scan").hidden = false; $("#cancel-scan").disabled = false; $("#cancel-scan").textContent = "Stop loading";
  }
  const status = cancelling ? "Cancelling analysis" : pausePending === "pause" ? "Pause requested; waiting for a safe checkpoint" : pausePending === "resume" ? "Resume requested" : paused ? "Paused · evidence retained · Resume continues this scan · detailed inspection after completion" : resultLoading ? "Loading bounded evidence pages" : busy ? "Analyzing" : "";
  const fraction = Number(data.progress_fraction);
  const progress = $("#scan-progress");
  progress.hidden = !busy;
  progress.setAttribute("aria-valuetext", status);
  if (Number.isFinite(fraction)) {progress.setAttribute("aria-valuemin","0");progress.setAttribute("aria-valuemax","100");progress.setAttribute("aria-valuenow",String(Math.round(Math.max(0,Math.min(1,fraction))*100)));}
  else progress.removeAttribute("aria-valuenow");
  $("#scan-status").hidden = !busy;
  $("#scan-status").textContent = status + (busy ? " · " + num(data.coverage?.scanned_packets ?? data.packets) + " packets" + (Number.isFinite(fraction) ? " · " + (100*fraction).toFixed(1) + "%" : "") : "");
  const coverage = data.coverage;
  $("#scan-coverage").hidden = !coverage;
  if (coverage) $("#scan-coverage").textContent = (coverage.partial ? "PARTIAL PREVIEW · READ-ONLY · " : "Coverage · ") + coverage.mode + " · " + num(coverage.scanned_packets) + " / " + num(coverage.source_packets) + " packets · " + (data.complete ? "observed" : "planned") + " ranges [start, end): " + (coverage.ranges || []).map(r => "[" + num(r.start_packet) + ", " + num(r.end_packet) + ")").join("; ") + (coverage.partial ? " · Unread gaps are unknown, not absent. Full scan required to edit/export." : "");
}
async function pauseScan() {
  if (!busy || cancelling || pausePending || activeAnalyze === null || backendFailure) return;
  const epoch = scanEpoch, requestId = activeAnalyze;
  const controlSequence = ++pauseSequence;
  const action = data.analysis_status === "paused" ? "resume" : "pause";
  pausePending = action; renderScanProgress();
  try {
    const result = await call(action + "_analysis", {request_id:requestId});
    if (epoch !== scanEpoch || requestId !== activeAnalyze || controlSequence !== pauseSequence) return;
    if (!result.requested) {pausePending = "";notice("Analysis is finishing; waiting for its terminal result");}
    // ACK is not a reached pause checkpoint. Owner progress is authoritative.
  } catch (error) {
    if (epoch !== scanEpoch || requestId !== activeAnalyze || controlSequence !== pauseSequence) return;
    pausePending = ""; notice("Could not confirm " + action + ": " + String(error), true);
  }
  renderScanProgress();
}
async function hydrateResult(result, valid) {
  const epoch = ++resultPageEpoch;
  resultPages = {};
  if (result.response_mode !== "compact") return;
  resultLoading = true;
  renderScanProgress();
  try {
    for (const collection of resultCollections) {
      result[collection] = [];
      let offset = 0, expectedTotal = null;
      if (result.result_counts?.[collection] === 0) continue;
      do {
        if (!valid() || epoch !== resultPageEpoch || backendFailure) return;
        const response = await call("query_result", {analysis_revision:result.revision,collection,offset,limit:200,...(result.selected_packet != null ? {at_packet:result.selected_packet} : {})});
        if (!valid() || epoch !== resultPageEpoch || backendFailure) return;
        if (response.analysis_revision !== result.revision || response.collection !== collection || (response.at_packet ?? null) !== (result.selected_packet ?? null) || !Array.isArray(response.items) ||
            (response.next_offset != null && (!Number.isSafeInteger(response.next_offset) || response.next_offset <= offset))) throw new Error("Result page identity or cursor mismatch");
        if (!Number.isSafeInteger(response.total) || response.total < 0 || (expectedTotal !== null && response.total !== expectedTotal) ||
            offset + response.items.length > response.total || (response.next_offset != null && response.next_offset !== offset + response.items.length) ||
            (response.next_offset == null && offset + response.items.length !== response.total)) throw new Error("Result page count mismatch");
        expectedTotal = response.total;
        result[collection].push(...response.items);
        result.result_counts[collection] = response.total;
        resultPages[collection] = {offset:0,next:response.next_offset,total:response.total,count:result[collection].length};
        offset = response.next_offset;
        renderResultPages();
        // Decode and consume bounded batches, yielding input between each. Full
        // hydration preserves global search/count/history semantics; this is not
        // an on-disk index or an overall memory bound for captured evidence.
        await new Promise(resolve => setTimeout(resolve,0));
      } while (offset != null);
    }
    const memberships = new Map();
    for (const row of result.tables || []) {
      if (!row.table_group_id) continue;
      if (!memberships.has(row.table_group_id)) memberships.set(row.table_group_id,{all:[],selected:[]});
      const members = memberships.get(row.table_group_id); members.all.push(row.id);
      if (row.selected_in_snapshot) members.selected.push(row.id);
    }
    for (const group of result.table_groups || []) {
      if (!group.member_ids_truncated) continue;
      const members = memberships.get(group.id);
      if (members) {group.section_ids = members.all;group.selected_section_ids = members.selected;group.member_ids_truncated = false;}
    }
  } finally {if (epoch === resultPageEpoch) {resultLoading = false;renderResultPages();}}
}
function renderResultPages() {
  const host = $("#result-pages");
  host.hidden = !resultLoading;
  if (!resultLoading) return;
  host.textContent = "Loading evidence in bounded pages · " + Object.entries(resultPages).map(([key,p]) => key + " " + num(p.count) + "/" + num(p.total)).join(" · ") + ". Search and complete counts become available after loading.";
}

async function cancelScan() {
  if (resultLoading && activeAnalyze === null) {
    const source = data.source;
    ++scanEpoch; resetAnalysisViews(); busy = false; cancelling = false;
    data = {source,complete:false,analysis_status:"loading_cancelled"};
    render(); notice("Result loading stopped · incomplete displayed evidence cleared · source unchanged", "warning");
    $("#scan").focus(); return;
  }
  if (!busy || cancelling || activeAnalyze === null || backendFailure) return;
  const epoch = scanEpoch, requestId = activeAnalyze, wasPaused = data.analysis_status === "paused";
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
    if (wasPaused) data.analysis_status = "paused";
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
    extraPids = parseExtraPids($("#extra-pids").value);
  } catch (error) {
    setScanOptionsOpen(true);
    setExtraPidsError(String(error));
    notice(String(error), true);
    $("#extra-pids").focus();
    return;
  }
  setExtraPidsError("");
  const options = currentScanOptions();
  const integer = (value, min) => Number.isSafeInteger(value) && value >= min;
  if ((["prefix","distributed"].includes(options.scan_mode) && (options.budget_unit === "percent" ? (!integer(options.sample_percent,1) || options.sample_percent > 100) : !integer(options.max_packets, 1))) ||
      (options.scan_mode === "range" && (!integer(options.start_packet,0) || !integer(options.end_packet,1) || options.end_packet <= options.start_packet)) ||
      (options.scan_mode === "distributed" && (!integer(options.window_count,1) || options.window_count > 16))) {
    notice("Choose 1–100 percent or a positive integer packet budget, an increasing packet range, and 1–16 windows.", true); return;
  }
  const epoch = ++scanEpoch;
  busy = true;
  cancelling = false;
  candidatePending = true;
  firstPaint = false;
  completePaint = false;
  render();
  notice("Analyzing stream… progress updates stay lightweight; evidence loads in bounded pages");
  let succeeded = false;
  try {
    recentFiles=normalizeRecentFiles([path,...recentFiles]);saveRecentFiles();closeRecentFiles();renderRecentFiles();
    const operation = call("analyze", {
      path,
      response_mode: "compact", scan_mode: options.scan_mode,
      ...(["prefix","distributed"].includes(options.scan_mode) ? (options.budget_unit === "percent" ? {sample_percent:options.sample_percent} : {max_packets:options.max_packets}) : {}),
      ...(options.scan_mode === "range" ? {start_packet:options.start_packet,end_packet:options.end_packet} : {}),
      ...(options.scan_mode === "distributed" ? {window_count:options.window_count} : {}),
      standards: options.standards,
      default_charset: options.default_charset,
      ...(options.extra_pids.length ? { extra_pids: options.extra_pids } : {}),
    });
    render();
    const result = await operation;
    if (epoch !== scanEpoch) return;
    if(candidatePending){candidatePending=false;resetAnalysisViews();filter="";pidFilter=null;page=0;historyPage=0;}
    clearProgress(); activeAnalyze = null; pausePending = "";
    data = {...result,complete:false,analysis_status:"loading_results"};
    await hydrateResult(result, () => epoch === scanEpoch);
    if (epoch !== scanEpoch) return;
    data = result;
    if (result.complete) completedScanOptions = options;
    succeeded = true;
    notice(
      (cancelling ? "Analysis completed before cancellation took effect · " : "Analysis complete · ") +
        num(data.packets) +
        " packets · source unchanged" + (data.demux?.truncated_sections ? " · " + num(data.demux.truncated_sections) + " truncated section(s)" : ""),
      data.demux?.truncated_sections ? "warning" : "info",
    );
  } catch (error) {
    if (epoch !== scanEpoch) return;
    if (error.data?.state_preserved && candidatePending && data.source) {
      if(data.source)$("#source").value=data.source;
      notice(String(error) + " — previous input and view retained", true);
    } else if (error.code === "analysis_cancelled") {
      resetAnalysisViews();
      data = error.data?.state || { analysis_status: "cancelled", complete: false };
      notice("Analysis cancelled · source unchanged · ready to analyze again", "warning");
    } else {
      resetAnalysisViews();
      data = { source: path, analysis_status: "failed", complete: false };
      notice(String(error), true);
    }
  } finally {
    if (epoch === scanEpoch) {
      const returnFocus = cancelling && (document.activeElement === $("#cancel-scan") || document.activeElement === document.body);
      clearProgress(); pausePending = ""; candidatePending = false;
      busy = false;
      cancelling = false;
      activeAnalyze = null;
      render();
      if (succeeded) {if(classicMode){classicConfiguration=false;syncSiMode();}if(tab==='Topology')loadTopology();else defaultInspect();}
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
      id, occurrence_offset:0, occurrence_limit:200,
      ...(atPacket != null ? { at_packet: atPacket } : {}),
      ...(['topology','protocol'].includes(evidence?.kind) ? {analysis_revision:evidence.ref.analysis_revision} : evidence?.kind==='service'?{analysis_revision:evidence.revision}:{}),
    });
    if (epoch !== inspectEpoch) return;
    if(evidence?.kind==='service'&&(result.id!==id||result.analysis_revision!==evidence.revision||result.native_table_at_packet!==evidence.atPacket))throw Error('Service source context mismatch');
    if(evidence?.kind==='topology') {
      if(evidence.nodeId!==topology.selected || evidence.ref!==topology.active || evidence.ref.analysis_revision!==data.revision) return;
      if(id===evidence.ref.section_id) {
        topology.resolution=workbench.resolveTopologyEvidence(evidence.ref,result);
        if(topology.resolution.status==='mismatch') throw new Error(topology.resolution.message);
      } else {
        if(result.id!==id || result.analysis_revision!==evidence.ref.analysis_revision || result.native_table_at_packet!==evidence.atPacket)throw new Error('Source-section context does not match the requested evidence.');
        topology.resolution={status:'fallback',precision:'section',anchor_index:-1,path:'section',byte_range:null,message:'Another section in this source group is open. The original assertion anchor applies to '+evidence.ref.section_id+'.'};
      }
    }
    if(evidence?.kind==='protocol') {
      if(evidence.ref.analysis_revision!==data.revision)return;
      if(id===evidence.ref.section_id)protocolResolution=workbench.resolveTopologyEvidence(evidence.ref,result);
      else if(result.id===id && result.analysis_revision===evidence.ref.analysis_revision && result.native_table_at_packet===evidence.atPacket)protocolResolution={status:'fallback',precision:'section',path:'section',byte_range:null,message:'Another exact section in this source group is open; the original assertion is in '+evidence.ref.section_id+'.'};
      else throw new Error('Protocol source context does not match the requested evidence.');
      if(protocolResolution.status==='mismatch')throw new Error(protocolResolution.message);
    }
    detail = result;
    openNodes = new Set();
    const visit=(node,parent='')=>{const path=parent?parent+'/'+node.id:node.id;if(workbench.defaultOpen(path)) openNodes.add(path);(node.children || []).forEach(child=>visit(child,path));};
    visit(sectionTree());
    if(activeSourceResolution()?.path) {
      const parts=activeSourceResolution().path.split('/');for(let i=1;i<=parts.length;i++)openNodes.add(parts.slice(0,i).join('/'));
    }
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
      if(evidence?.kind==='topology' && document.activeElement===document.body) {const target=$('#tree-area [data-source-highlight]') || $('#topology-back');if(target){target.tabIndex=0;target.focus({preventScroll:true});}}
      const identity=[detail.pid,detail.table_id,detail.extension].join(":");
      if(identity!==historyIdentity) historyPage=0;
      historyIdentity=identity; renderTimeline();
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
function activateHistory(entry) {
  selectExplorer({pid:entry.pid,name:entry.name});
  if(!entry.valid) showBadCrc=true;
  snapshot(entry.at_packet,entry.id);
}
function packetWasObserved(packet) {
  return !data.coverage?.partial || (data.coverage.ranges || []).some(range => packet >= range.start_packet && packet < range.end_packet);
}
async function snapshot(packet, id, sid = -1) {
  clearTimeout(pendingSnapshotTimer);
  pendingSnapshotTimer = null;
  if (busy || backendFailure) return;
  if (packet >= 0 && !packetWasObserved(packet)) {notice("That packet was not scanned. The gap is unknown; choose an observed range or run a full scan.", "warning");return;}
  if (tab === "Changes") changeTab("Services");
  const epoch = ++queryEpoch;
  editTarget = null;
  invalidatePreview();
  if ($("#edit-dialog").open) $("#edit-dialog").close();
  selectionReset();
  ++topology.epoch;topology.loading=false;topology.active=null;topology.cutoff=null;topology.label='';topology.history=[];topology.snapshot=null;topology.workspace=null;topology.sourceWorkspace=null;
  renderInspector();
  notice("Loading packet snapshot…");
  try {
    const result = await call("query", {response_mode:"compact", ...(packet < 0 ? {} : {at_packet:packet})});
    if (epoch !== queryEpoch) return;
    // Publish the new cutoff only with its hydrated evidence and rendered
    // slider. Early metadata would let the next key reuse an old slider step.
    data = {...result,selected_packet:data.selected_packet,complete:false,analysis_status:"loading_results"};
    await hydrateResult(result, () => epoch === queryEpoch);
    if (epoch !== queryEpoch) return;
    data = result;
    page = 0;
    render();
    if (id) inspect(id, sid);
    else if(tab==='Topology')loadTopology();
    else defaultInspect();
    notice(
      packet < 0
        ? "Latest observed state"
        : "Snapshot through packet " + num(packet),
    );
  } catch (error) {
    if (epoch === queryEpoch) {
      if (data.analysis_status === "loading_results") {
        const source = data.source;
        resetAnalysisViews(); data = {source,complete:false,analysis_status:"failed"}; render();
      }
      notice(String(error), true);
    }
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
  syncSiMode(); siView?.update(); summaryView?.update(); syncDocuments();
  renderScanProgress(); renderResultPages();
  dvbiWorkspace?.update();
  updateScanOptions();
  const issues = workbench.issueCounts(data.diagnostics || []);
  const issueLabel = issues.hasSeverity ? issues.errors + " errors · " + issues.warnings + " warnings" + (issues.other ? " · " + issues.other + " other" : "") : issues.total + " issues";
  const stats = [
    ["SERVICES", num(data.services?.length), "in selected state", "Services"],
    [
      "SECTIONS",
      num(data.observations),
      num(data.tables?.length) + " distinct payloads",
      "Tables",
    ],
    [
      "ISSUES",
      issues.hasSeverity ? `<span class="issue-errors">${num(issues.errors)} errors</span><span class="issue-warnings">${num(issues.warnings)} warnings</span>${issues.other ? `<span class="issue-other">${num(issues.other)} other</span>` : ""}` : num(issues.total),
      num(data.crc_errors) + " CRC failures",
      "Issues",
    ],
    [
      "SCAN",
      data.metrics ? Number(data.metrics.scan_ms).toFixed(1) + " ms" : "—",
      cancelling ? "Cancelling…" : busy ? "Analyzing…" : ["cancelled","loading_cancelled"].includes(data.analysis_status) ? "Cancelled" : data.analysis_status === "failed" ? "Failed" : data.complete ? "Complete" : "No source",
    ],
  ];
  $("#stats").innerHTML = stats
    .map(
      ([label, value, sub, target]) =>
        `<${target ? `button type="button" class="stat" data-stat-tab="${target}" aria-label="Show ${target} · ${target === 'Issues' ? issueLabel : value + ' ' + label.toLowerCase()} · ${sub}" title="Show ${target}${target === 'Issues' ? ' · CRC: Cyclic Redundancy Check failures' : ''}"` : 'div class="stat"'}><span>${label}</span><strong${target === 'Issues' ? ' class="issue-counts"' : ''}>${value}</strong><small>${sub}</small></${target ? "button" : "div"}>`,
    )
    .join("");
  // Stats double as shortcuts to the tab that lists what they count.
  $("#stats").querySelectorAll("[data-stat-tab]").forEach((el) => {
    el.onclick = () => [...document.querySelectorAll("#tabs [data-tab]")].find((t) => t.dataset.tab === el.dataset.statTab)?.click();
  });
  $("#scan").disabled = busy || !native || !!backendFailure;
  $("#browse").disabled = busy || !native || !!backendFailure;
  $("#recent").disabled = busy || !native || !!backendFailure;
  $("#scan").textContent = busy ? (resultLoading ? "Loading…" : data.analysis_status === "paused" ? "Paused" : "Analyzing…") : "Analyze";
  $("#cancel-scan").hidden = !busy && !resultLoading;
  $("#cancel-scan").disabled = cancelling || (activeAnalyze === null && !resultLoading) || !!backendFailure;
  $("#cancel-scan").textContent = cancelling ? "Cancelling…" : resultLoading ? "Stop loading" : "Cancel";
  $("#cancel-scan").setAttribute("aria-busy", String(cancelling));
  renderScanProgress();
  for (const id of ["scan-mode","scan-budget-unit","scan-percent","scan-budget","scan-start","scan-end","scan-windows"]) $("#"+id).disabled = busy;
  $("#source").disabled = busy;
  $("#standards").disabled = busy;
  $("#extra-pids").disabled = busy;
  $("#default-charset").disabled = busy;
  renderExplorer();
  $("#extension").innerHTML =
    `<div class="panel-title">DESCRIPTOR EXTENSION</div><strong>${esc(data.extension_id || "No extension reported")}</strong><p>Schema extensions use their declared scope. Native decoding follows the table context; raw evidence is retained.</p>`;
  $("#tabs").innerHTML = recordTabs
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
        $('#tabs [aria-selected="true"]').scrollIntoView({block:'nearest',inline:'nearest'});
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
        $('#tabs [aria-selected="true"]').scrollIntoView({block:'nearest',inline:'nearest'});
        }
      };
    });
  $("#search").placeholder = "Search records · > commands · # PID/SID";
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
function recordRows(tableModel = null) {
  if (tab === "Tables") return (tableModel || workbench.tables(data,pidFilter,filter,showBadCrc,search)).sections;
  let rows =
    tab === "Services"
      ? data.services || []
      : tab === "Tables"
        ? (data.tables || []).filter(tableMatches).filter(r => showBadCrc || !isBadCrc(r))
        : tab === "EPG"
          ? data.events || []
          : data.diagnostics || [];
  rows = rows.filter(row=>workbench.matches(row,search));
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
function navigateRecords(event,current) {
  if(!['ArrowUp','ArrowDown','Home','End'].includes(event.key)) return;
  event.preventDefault();
  const items=[...$('#list').querySelectorAll('summary,[role="option"]')].filter(el=>el.getClientRects().length);
  const i=items.indexOf(current);
  const target=items[event.key==='Home'?0:event.key==='End'?items.length-1:Math.max(0,Math.min(items.length-1,i+(event.key==='ArrowDown'?1:-1)))];
  items.forEach(el=>el.tabIndex=-1); if(target) {target.tabIndex=0;target.focus();}
}
function renderList() {
  $("#list").setAttribute('aria-busy','false');
  $("#list").onscroll = () => { $("#service-head").scrollLeft = $("#list").scrollLeft; };
  $("#panes .searchbar").hidden = tab === "Changes";
  $("#list").setAttribute("role", tab === "Changes" ? "region" : "listbox");
  $("#list").setAttribute("aria-label", tab === "Changes" ? "Snapshot changes" : "Stream records");
  if (tab === "Changes") {
    renderComparison();
    return;
  }
  if (tab === "Topology") { renderTopology(); return; }
  const tableModel = tab === "Tables" ? workbench.tables(data,pidFilter,filter,showBadCrc,search) : {groups:[],sections:[]};
  const rows = recordRows(tableModel);
  const groups = tab === "Tables" && groupedTables ? tableModel.groups : [];
  const total = tab === "Tables" && groupedTables ? groups.length : rows.length;
  page = Math.max(0, Math.min(page, Math.ceil(total / PAGE_SIZE) - 1));
  const start = page * PAGE_SIZE;
  $("#result-count").textContent = tab === "Tables" ? tableModel.count_text : num(total);
  $("#page-label").textContent = total ? `${num(start + 1)}–${num(Math.min(start + PAGE_SIZE, total))} of ${num(total)} ${tab === "Tables" && groupedTables ? "tables" : "records"}` : "0 records";
  $("#prev").disabled = page === 0;
  $("#next").disabled = start + PAGE_SIZE >= total;
  $("#service-head").innerHTML = tab === "Services" ? `<div class="service-head"><span ${tip("LCN")}>LCN</span><span>SERVICE / PROVIDER</span><span>TYPE</span><span ${tip("PMT")}>PMT PID</span><span>VIDEO / AUDIO PIDs</span></div>` : (tab === "Tables" && selected && !rows.some(r=>r.id===selected) ? '<p class="meta selection-hidden">Selected evidence is retained; its record is hidden by this filter.</p>' : "");
  $("#table-filter-tools").innerHTML = tab === "Tables" ? `<label class="family-filter">Type <select id="table-family" aria-label="Table type across all PIDs"><option value="">All types</option>${[...tableFamilies(), "Private / other"].map(name => `<option value="${esc(name)}" ${filter === name ? "selected" : ""}>${esc(tableLabel(name))}</option>`).join("")}</select></label><label title="Include invalid CRC sections. Issues always retains all evidence."><input id="show-bad-crc" type="checkbox" ${showBadCrc ? 'checked' : ''}> Bad CRC (${num((data.tables || []).filter(tableMatches).filter(isBadCrc).length)})</label><button class="btn small" id="table-group-toggle" aria-pressed="${groupedTables}" title="Switch between logical tables and individual sections">${groupedTables ? "Sections" : "Tables"}</button>` : "";
  $("#table-family")?.addEventListener("change", event => {
    filter = event.target.value; pidFilter = null; page = 0;
    explorerFocusKey = JSON.stringify([-1,"All tables"]);
    render(); $("#table-family")?.focus();
  });
  $("#table-group-toggle")?.addEventListener("click", () => { groupedTables = !groupedTables; page = 0; renderList(); });
  $("#show-bad-crc")?.addEventListener("change", e => { showBadCrc = e.target.checked; page = 0; renderList(); });
  const displayedGroups = groups.slice(start,start+PAGE_SIZE);
  const displayedIds = new Set(displayedGroups.flatMap(group => group.section_ids));
  const visibleRows = tab === "Tables" && groupedTables ? rows.filter(row => displayedIds.has(row.id)) : rows.slice(start,start+PAGE_SIZE);
  $("#list").innerHTML = visibleRows
    .map((r, i) => {
      const key = rowIdentity(r, start + i);
      let body = "";
      if (tab === "Services")
        body = `<span class="lcn" title="LCN: ${esc(r.lcn_status || 'unknown')}${esc((r.lcn_candidates || []).map(c => ` · ${c.number} (${c.namespace}; ${c.source_id})`).join(''))}">${r.logical_channel_number ?? (r.lcn_status === 'conflict' ? 'Conflict' : '—')}</span><div class="record-name"><strong>${esc(r.name || "Unnamed service")}</strong><small>${esc(r.provider || "No provider")} · SID ${hex(r.id)}</small><small>${esc(r.group || '')}</small></div><span class="service-type" title="${esc(r.service_type_name || 'Service type unavailable')}">${esc((r.service_type_name || 'Unknown').replace('Digital television service', 'Digital TV').replace('Digital radio sound service', 'Digital radio'))}<small class="numeric">${hex(r.service_type ?? r.type, 2)}</small></span><span class="numeric">${hex(r.pmt_pid)}</span><span class="numeric media-pids" title="${esc(r.media_status || 'PMT unavailable')}"><span>V ${r.video_pids?.length ? r.video_pids.map(p => hex(p)).join(', ') : r.media_status === 'decoded PMT' ? 'none' : '—'}</span><span>A ${r.audio_pids?.length ? r.audio_pids.map(p => hex(p)).join(', ') : r.media_status === 'decoded PMT' ? 'none' : '—'}</span></span>`;
      if (tab === "Tables")
        body = `${categoryBadge(r)}<div class="record-name"><strong>PID <span class="numeric">${hex(r.pid)}</span> · TID <span class="numeric">${hex(r.table_id, 2)}</span></strong><small>${esc(workbench.wireVersionText(r))} · ${esc(workbench.wireSectionText(r))} · ${num(r.bytes)} B</small><small>CRC ${esc(r.crc?.transmitted_hex || r.crc?.status || "unavailable")} · #${num(r.first_packet)} → #${num(r.last_packet)}</small></div><span class="numeric muted">${num(r.count)}×</span><span class="${r.valid ? "ok" : "bad"}" title="${r.valid ? "Valid section" : "Invalid section"}">${r.valid ? "●" : "⚠"}</span>`;
      if (tab === "EPG")
        body = `<div class="record-name"><strong>${esc(eventTitle(r))}</strong><small>SID ${hex(r.service_id)} · ${esc(r.start)} UTC · ${num(r.duration_seconds / 60)} min</small></div><span class="muted numeric">${hex(r.id)}</span>`;
      if (tab === "Issues")
        body = `<span class="bad">⚠</span><div class="record-name"><strong>${esc(r.code)}</strong><small>${esc(r.detail)}</small><small>${r.aggregate ? "Aggregate across monitored SI PIDs" : "PID " + hex(r.pid) + " · packet " + num(r.packet)} · ${num(r.count)} observations</small></div>`;
      return `<div role="option" aria-selected="${selectedKey === key}" tabindex="${selectedKey === key || (!selectedKey && i === 0) ? 0 : -1}" class="record ${tab.toLowerCase()} ${selectedKey === key ? "selected" : ""}" data-row="${i}" data-key="${esc(key)}">${body}</div>`;
    })
    .join("");
  if (!rows.length)
    $("#list").innerHTML =
      `<div class="empty"><span class="empty-icon">${busy ? "◌" : data.source ? "⌕" : "▦"}</span><h3>${cancelling ? "Cancelling analysis…" : busy ? "Reading transport stream…" : data.analysis_status === "loading_cancelled" ? "Result loading stopped" : data.analysis_status === "cancelled" ? "Analysis cancelled" : data.analysis_status === "failed" ? "Analysis failed" : !data.source ? "Explore your transport stream" : search ? "No matching records" : "No " + tab.toLowerCase() + " in this state"}</h3><p>${cancelling ? "Waiting for the engine to stop. The source file stays unchanged." : ["cancelled", "loading_cancelled", "failed"].includes(data.analysis_status) ? "Partial results were cleared. Analyze again when you are ready." : !data.source ? "Open a TS file to inspect PSI/SI tables, decoded fields and their original bytes." : search ? "Try another name, decimal identifier or hexadecimal value." : ["Services", "EPG"].includes(tab) && (data.tables || []).length ? "This view shows derived " + (tab === "Services" ? "services" : "programme events") + ". Open Tables for native signalling fields and raw evidence; an empty projection does not mean decoding failed." : "Choose another table family or packet snapshot."}</p></div>`;
  const visible = visibleRows;
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
      el.onclick = () => { const key=el.dataset.key;activate();requestAnimationFrame(()=>[...$('#list').querySelectorAll('[data-key]')].find(row=>row.dataset.key===key)?.focus()); };
      el.onkeydown = (e) => {
        navigateRecords(e,el);
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

      const branch = document.createElement("details");
      branch.className = "table-branch";
      branch.open = openTableGroups.has(g.id);
      branch.innerHTML = `<summary data-group-id="${esc(g.id)}" aria-label="${esc(g.name)} table: select and expand"><button class="group-fold" tabindex="-1" aria-label="Expand or collapse table" type="button">${branch.open ? "▾" : "▸"}</button>${categoryBadge(g)} <span>PID ${hex(g.pid)} · TID ${hex(g.table_id,2)}<small>${esc(workbench.groupText(g))}</small><small>${num(g.distribution?.observation_count)} observations · packets #${num(g.distribution?.first_packet)}–#${num(g.distribution?.last_packet)}</small></span></summary><div role="listbox" aria-label="Source sections"></div>`;
      const summary=branch.querySelector('summary');
      summary.onclick=event=>{
        if(event.target.closest('.group-fold')) return;
        const row=workbench.representative(g,rows);
        if(row) { branch.open ? openTableGroups.delete(g.id) : openTableGroups.add(g.id); event.preventDefault(); inspect(row.id); requestAnimationFrame(()=>[...list.querySelectorAll('summary')].find(el=>el.dataset.groupId===g.id)?.focus()); } else notice('Bad-CRC evidence hidden. Enable Bad CRC to inspect.');
      };
      summary.onkeydown=event=>{
        if(event.key===' ' || event.key==='ArrowLeft' || event.key==='ArrowRight') {
          event.preventDefault(); branch.open=event.key===' ' ? !branch.open : event.key==='ArrowRight';
        }
        navigateRecords(event,summary);
      };
      branch.querySelector('.group-fold').onclick=event=>{event.preventDefault();event.stopPropagation();branch.open=!branch.open;};
      const holder = branch.querySelector('[role="listbox"]');
      for (const row of groupRows) holder.append(row);
      if (!holder.querySelector('[tabindex="0"]') && groupRows.length) groupRows[0].tabIndex = 0;
      if (!groupRows.length) holder.innerHTML = '<p class="meta">Bad-CRC evidence hidden. Enable Show bad CRC to inspect.</p>';
      branch.ontoggle = () => { branch.open ? openTableGroups.add(g.id) : openTableGroups.delete(g.id); branch.querySelector(".group-fold").textContent=branch.open?"▾":"▸"; };
      list.append(branch);
    }
  }
  if (!$('#list [tabindex="0"]'))
    $('#list [role="option"]')?.setAttribute("tabindex", "0");
}
function changeTab(next) {
  if (next === tab) return;
  const previousTab=tab;
  if(previousTab==='Topology') {
    topology.scroll=$('#list').scrollTop;
    topology.sourceWorkspace=inspectionState();
    restoreInspectionState(topology.workspace);
    search=topology.recordSearch || '';$('#search').value=search;
    if(topology.origin==='Changes') {
      if(next==='Changes') {tab=next;return;}
      if(savedWorkspace) {restoreInspectionState(savedWorkspace);savedWorkspace=null;}
    }
  }
  if(next==='Topology') {
    topology.workspace=inspectionState();topology.origin=previousTab;topology.recordSearch=search;++inspectEpoch;loadingDetail=false;
    if(previousTab!=='Changes') {topology.cutoff=null;topology.label='';}
    search=topology.search;$('#search').value=search;topology.restoreScroll=true;
    if(topology.active && topology.sourceWorkspace)restoreInspectionState(topology.sourceWorkspace);
    tab=next;
    if(!topology.snapshot || topology.snapshot.analysis_revision!==data.revision || topology.snapshot.at_packet!==topologyCutoff()) {
      ++topology.epoch;topology.loading=false;topology.active=null;topology.snapshot=null;queueMicrotask(()=>loadTopology());
    }
    return;
  }
  topology.revealed=false;
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
    if (comparison.from === null && comparison.to === null && data.complete) {
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
    (data.table_history || []).map((entry) => `<option value="${entry.last_packet}">${esc(workbench.historyText(entry))} · through packet ${num(entry.last_packet)}</option>`).join("");
}
function invalidateComparison() {
  ++comparison.epoch;
  comparison.loading = false;
  comparison.result = null;
  comparison.error = "";
  comparison.filters = [];
  updateComparisonMarkers();
  if (tab !== "Changes") return;
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
// Keep keys and scalar values literal; containers disclose their field rows.
function readableValue(value, key = "", present = true) {
  return workbench.comparisonValue(key, value, present);
}
function comparisonDiff(change) {
  function field(node) {
    const text = `<span title="${esc(workbench.comparisonHelp(node.key))}">${esc(node.label)}</span>: ${node.note ? esc(node.note) : `${esc(readableValue(node.before, node.key, node.hasBefore))} → ${esc(readableValue(node.after, node.key, node.hasAfter))}`}`;
    return node.children.length ? `<details class="comparison-field diff-${node.change}"><summary aria-label="${esc(workbench.comparisonFieldText(node))}">${text}</summary><div class="comparison-children">${node.children.map(field).join("")}</div></details>` : `<div class="comparison-field diff-${node.change}">${text}</div>`;
  }
  return `<div class="comparison-diff" role="group" aria-label="Field changes from A to B">${workbench.comparisonFields(change).map(field).join("")}</div>`;
}
function comparisonSide(side, label, change, index) {
  if (!side) return `<div class="comparison-side absent"><h4>${label}</h4><p>No observed record in this state</p></div>`;
  return `<div class="comparison-side"><h4>${label} <span>packet ${num(side.at_packet)}</span></h4><button class="btn primary small" data-use-comparison="${index}:${label[0]}" ${busy || backendFailure || !side.evidence?.length ? "disabled" : ""} aria-label="Use snapshot ${label[0]} at packet ${side.at_packet}" title="Move the workbench to packet ${side.at_packet}; edits and exports will use this cutoff">Use snapshot</button><div class="comparison-evidence" role="group" aria-label="Source actions for snapshot ${label[0]}"><span class="meta">Source</span><button class="btn small" data-comparison-topology="${index}:${label[0]}" ${busy || backendFailure?'disabled':''}>Topology at ${label[0]}</button>${(side.evidence || []).map((evidence, evidenceIndex) => `<button class="btn small" aria-pressed="${selectedKey === "comparison:" + side.at_packet + ":" + change.kind + ":" + change.key + ":" + evidenceIndex}" data-evidence-key="${esc("comparison:" + side.at_packet + ":" + change.kind + ":" + change.key + ":" + evidenceIndex)}" data-comparison-evidence="${index}:${label[0]}:${evidenceIndex}" ${backendFailure ? "disabled" : ""} title="PID: Packet Identifier · inspect ${esc(evidence.id)} at packet ${side.at_packet}">PID ${hex(evidence.pid)} · ${esc(workbench.wireVersionText(evidence))} · ${esc(workbench.wireSectionText(evidence))}</button>`).join("")}</div></div>`;
}
function renderComparisonResults() {
  updateComparisonMarkers();
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
  const totals = workbench.comparisonTotals(result), filters = comparison.filters;
  const changes = result.changes.map((change, index) => ({change, index})).filter(({change}) => workbench.comparisonMatches(change, filters));
  $("#list").innerHTML = `<div class="comparison-summary"><strong>A ${num(result.from_packet)} → B ${num(result.to_packet)}</strong><div class="comparison-filters" role="group" aria-label="Filter changes on this page">${[["added", "+"], ["removed", "−"], ["changed", "~"]].map(([kind, sign]) => `<button class="btn small diff-${kind}" data-change-filter="${kind}" aria-pressed="${filters.includes(kind)}" title="Toggle ${kind} changes on this page; no active filters shows all changes">${sign}${num(totals[kind])} ${kind}</button>`).join('<span aria-hidden="true">·</span>')}</div><span class="meta">${result.kind === "all" ? "All record types" : esc(result.kind)} · ${num(result.total_changes)} changes · ${num(changes.length)} shown on this page</span></div>${changes.length ? changes.map(({change, index}) => {
    const identity = change.identity, value = change.after?.value || change.before?.value || {};
    const title = change.kind === "services" ? (value.name || "Unnamed service") + " · SID " + hex(identity.service_id)
      : change.kind === "events" ? (value.title || "Untitled event") + " · event " + hex(identity.event_id)
        : (value.name || "Table") + " · PID " + hex(identity.pid) + " · section " + identity.section;
    return `<article class="comparison-change"><header><span class="change-badge ${change.change}">${esc(change.change)}</span><span class="meta">${esc(change.kind)}</span><h3>${esc(title)}</h3></header>${comparisonDiff(change)}<div class="comparison-sides">${comparisonSide(change.before, "A · before", change, index)}${comparisonSide(change.after, "B · after", change, index)}</div><details class="comparison-raw"><summary aria-label="Raw comparison record for ${esc(title)}">Raw</summary><pre>${esc(JSON.stringify(change, null, 2))}</pre></details></article>`;
  }).join("") : filters.length && result.changes.length ? '<div class="empty"><h3>No matching changes on this page</h3><p>Toggle the filters to show all changes, or use Previous / Next to visit another page.</p></div>' : '<div class="empty"><h3>No observed changes</h3><p>The selected record type is unchanged between these cutoffs. Repeated identical sections alone are not changes.</p></div>'}`;
  $("#list").querySelectorAll("[data-change-filter]").forEach((el) => el.onclick = () => {
    const kind = el.dataset.changeFilter;
    comparison.filters = filters.includes(kind) ? filters.filter((item) => item !== kind) : [...filters, kind];
    renderComparisonResults();
    $(`[data-change-filter="${kind}"]`).focus();
  });
  $('#list').querySelectorAll('[data-comparison-topology]').forEach(el=>el.onclick=()=>{const [index,letter]=el.dataset.comparisonTopology.split(':');const change=result.changes[Number(index)];openComparisonTopology(letter==='A'?change.before:change.after,letter);});
  $("#list").querySelectorAll("[data-use-comparison]").forEach((el) => {
    el.onclick = () => {
      if (busy || backendFailure || result !== comparison.result) return;
      const [index, letter] = el.dataset.useComparison.split(":");
      const change = result.changes[Number(index)], side = letter === "A" ? change.before : change.after;
      if (!side?.evidence?.length) return;
      changeTab(change.kind === "services" ? "Services" : change.kind === "events" ? "EPG" : "Tables");
      search = "";
      $("#search").value = "";
      snapshot(side.at_packet, side.evidence[0].id, change.kind === "services" ? change.identity.service_id : -1);
    };
  });
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
      updateComparisonMarkers();
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
function sectionTree() { return workbench.structure(detail,evidenceScope,selectedService,inspectionEvidence && inspectionEvidence.atPacket!==workspaceCutoff()?null:data); }
function nodeMatches(node, needle) {
  return (
    needle.split(/\s+/).every(term=>(node.label + " " + (node.value ?? "")).toLowerCase().includes(term)) ||
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
let treeNodesRendered = 0, treeReferences = new Map();
function drawNode(node, parent = "", index = 0, ancestorMatch = false, level = 1) {
  const path = parent ? parent + "/" + (node.id ?? index) : node.id;
  const needle = treeSearch.trim().toLowerCase();
  const selfMatch = needle.split(/\s+/).every(term => (node.label + " " + (node.value ?? "")).toLowerCase().includes(term));
  if (needle && !ancestorMatch && !nodeMatches(node, needle)) return "";
  if (++treeNodesRendered > 2500) return "";
  const resolution=activeSourceResolution();
  const located=evidenceScope==='section' && resolution?.status==='resolved' && resolution.path===path;
  const accessible = `${located?'data-source-highlight="true" ':''}role="treeitem" tabindex="-1" aria-level="${level}" data-node-path="${esc(path)}" aria-label="${esc(node.label + (node.value !== undefined ? ": " + node.value : ""))}"`;
  const kind = ["number", "string", "boolean"].includes(node.kind) ? node.kind : "meta";
  const label = `<span class="node-label ${node.tone || ""}" title="${esc(fieldHelp[node.label] || node.label)}">${highlightedTreeText(node.label)}</span>${node.value !== undefined ? `<span class="node-value" data-value-kind="${kind}">${highlightedTreeText(node.value)}</span>` : ""}`;
  if (!node.children) {
    if(node.reference)treeReferences.set(path,node.reference);
    const jump=node.reference?`<button type="button" class="reference-jump" data-reference-path="${esc(path)}" tabindex="-1" aria-label="${esc(node.reference.label)}" title="${esc(node.reference.label+' · '+node.reference.help+' · Ctrl+Enter')}">→</button>`:'';
    return `<div class="tree-leaf${jump?' has-reference':''}" ${accessible}>${label}${jump}</div>`;
  }
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
  treeReferences = new Map();
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
      const jump=el.querySelector(':scope > .reference-jump');if(jump)jump.tabIndex=el===target?0:-1;
    });
    if (focus) focusTreeItem(target);
  }
  const items = visibleItems();
  setEntry(items.find((el) => el.dataset.nodePath === previousPath) || items[0], hadFocus);
  // focusin bubbles, but onfocusin is not a supported handler property in
  // every engine. Replace the listener on rerender instead of accumulating it.
  if (area.treeFocusHandler) area.removeEventListener("focusin", area.treeFocusHandler);
  area.treeFocusHandler = (event) => {
    const row=event.target.closest('[role="treeitem"]');if(row)setEntry(row);
  };
  area.addEventListener("focusin", area.treeFocusHandler);
  area.onclick = (event) => {
    const jump=event.target.closest('[data-reference-path]');
    if(jump){jumpReference(treeReferences.get(jump.dataset.referencePath),jump.dataset.referencePath);return;}
    const node = event.target.closest('[role="treeitem"]');
    if (!node || !area.contains(node)) return;
    setEntry(node, true);
    if (node.classList.contains("tree-node") && event.target.closest(".tree-row") === node.querySelector(":scope > .tree-row"))
      setTreeExpanded(node, node.getAttribute("aria-expanded") !== "true");
  };
  let typed = "", typedAt = 0;
  area.onkeydown = (e) => {
    // Modified arrows belong to workbench Back, never to tree folding.
    if(e.altKey)return;
    const row=e.target.closest('[role="treeitem"]');
    if(e.ctrlKey && !e.metaKey && !e.shiftKey && e.key==='Enter' && row) {
      e.preventDefault();e.stopPropagation();jumpReference(treeReferences.get(row.dataset.nodePath),row.dataset.nodePath);return;
    }
    if(e.target.closest('[data-reference-path]'))return;
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
function topologyHexDump(raw) {
  const resolution=activeSourceResolution();
  const range=evidenceScope==='section' && resolution?.status==='resolved'?resolution.byte_range:null;
  if(!range)return esc(hexDump(raw));
  const bytes=String(raw || '').match(/.{1,2}/g) || [];
  return Array.from({length:Math.ceil(bytes.length/16)},(_,row)=>{
    const start=row*16,slice=bytes.slice(start,start+16);
    return start.toString(16).toUpperCase().padStart(4,'0')+'  '+slice.map((byte,index)=>{const offset=start+index;return offset>=range.offset && offset<range.offset+range.length?'<mark class="source-byte">'+esc(byte)+'</mark>':esc(byte);}).join(' ')+' '.repeat((16-slice.length)*3)+'  '+esc(slice.map(byte=>{const c=parseInt(byte,16);return c>=32 && c<127?String.fromCharCode(c):'.';}).join(''));
  }).join('\n');
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
  if (!group) return `<div class="section-group" id="section-group" data-inspector-content="sections" ${inspectorDetails.sections ? '' : 'hidden'}><p class="meta">${esc(workbench.wireHeaderText(detail))} · No capture-wide group available at this cutoff.</p></div>`;
  const sources = (data.tables || []).filter(r => group.section_ids.includes(r.id));
  const hidden = sources.filter(isBadCrc).length;
  if(group.versioning_supported===false)return `<div class="section-group" id="section-group" data-inspector-content="sections" ${inspectorDetails.sections?'':'hidden'}><p class="meta">Exact section evidence · ${esc(group.validity)} · map assembly unsupported</p><p class="meta">${esc(group.coverage_scope || group.coverage_model || detail.header_semantics)}</p><p class="meta">${esc(workbench.wireHeaderText(group))}</p><select id="section-choice" aria-label="Select original section evidence">${sources.map(r=>`<option value="${esc(r.id)}" ${r.id===detail.id?'selected':''}>${esc(r.name)} · CRC ${esc(r.crc?.status || 'unavailable')} · #${num(r.first_packet)}</option>`).join('')}</select></div>`;
  return `<div class="section-group" id="section-group" data-inspector-content="sections" ${inspectorDetails.sections ? "" : "hidden"}><p class="meta">▦ Table sections · ${esc(group.validity)} · ${group.selected_complete ? 'complete selection' : 'incomplete selection'}</p><p class="meta">Capture-wide version coverage; selected completeness is generation-safe.</p><p class="meta">Observed: ${(group.observed_section_numbers || []).join(', ') || 'none'} · Missing: ${(group.missing_section_numbers || []).join(', ') || 'none'} · Missing valid: ${(group.missing_valid_section_numbers || []).join(', ') || 'none'} · Selected missing: ${(group.selected_missing_section_numbers || []).join(', ') || 'none'} · Bad CRC: ${hidden}${showBadCrc ? '' : ' hidden'}</p><div class="section-links"><select id="section-choice" aria-label="Select original section evidence">${sources.filter(r => showBadCrc || !isBadCrc(r)).map(r => `<option value="${esc(r.id)}" ${r.id === detail.id ? 'selected' : ''}>${esc(workbench.wireSectionText(r))} · CRC ${esc(r.crc?.transmitted_hex || '—')} · ${esc(r.crc?.status || 'unavailable')} · #${r.first_packet}</option>`).join('')}</select></div>${hidden ? `<button class="btn small" id="group-show-bad">${showBadCrc ? 'Hide' : 'Show'} ${hidden} bad CRC section(s)</button>` : ''}</div>`;
}
let epgLanguage = "", identifierResult = null, satelliteResult = null;
const lookupState={namespace:"original_network_id",identifier:"",position:"",direction:"E",identifierOpen:false,identifierRaw:false,satelliteRaw:false,identifierNotice:"Enter a decimal or hexadecimal ID.",satelliteNotice:""};
const lookupFields=[["identifier-kind","namespace","change"],["identifier-value","identifier","input"],["satellite-position","position","input"],["satellite-direction","direction","change"]];
const lookupDisclosures=[["identifier-lookup","identifierOpen"],["identifier-raw","identifierRaw"],["satellite-raw","satelliteRaw"]];
function rememberLookupState(panel) {
  lookupFields.forEach(([id,key])=>{const el=panel.querySelector('#'+id);if(el)lookupState[key]=el.value;});
  lookupDisclosures.forEach(([id,key])=>{const el=panel.querySelector('#'+id);if(el)lookupState[key]=el.open;});
}
function lookupTable(result, label) {
  const model=workbench.lookupResult(result);
  return `<table class="lookup-table${model.hasSource?' with-source':''}" aria-label="${esc(label)}"><thead><tr><th scope="col">Key</th><th scope="col">Value</th>${model.hasSource?'<th scope="col">Source</th>':''}</tr></thead><tbody>${model.rows.map(row=>`<tr><th scope="row" title="${esc(row.key+(row.help?' · '+row.help:''))}">${esc(row.label)}</th><td class="lookup-value">${esc(row.value)}</td>${model.hasSource?`<td class="lookup-source" title="${esc(row.sourceTip)}">${esc(row.source || '—')}</td>`:''}</tr>`).join('')}</tbody></table>`;
}
function lookupOutput(kind) {
  const result=kind==='identifier'?identifierResult:satelliteResult;
  return result?lookupTable(result,kind==='identifier'?'Identifier lookup result':'Satellite lookup result'):`<p class="meta">${esc(lookupState[kind+'Notice'])}</p>`;
}
function refreshLookupResult(kind) {
  const result=kind==='identifier'?identifierResult:satelliteResult,output=$('#'+kind+'-result');
  if(!output)return;
  output.innerHTML=lookupOutput(kind);
  $('#'+kind+'-evidence').textContent=result?JSON.stringify(result,null,2):'';
  const raw=$('#'+kind+'-raw');raw.hidden=!result;raw.open=lookupState[kind+'Raw'];
}
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
let protocolCardOffset=0, protocolCardKey='';
function metadataPanel() {
  const card = (title, body, extra = null) => `<article class="metadata-card"><strong>${esc(title)}</strong><pre>${esc(body)}</pre>${extra ? `<details><summary>Original values and source evidence</summary><pre>${esc(JSON.stringify(extra, null, 2))}</pre></details>` : ""}</article>`;
  const key=[detail.id,detail.analysis_revision,detail.native_table_at_packet].join(':');
  if(key!==protocolCardKey){protocolCardKey=key;protocolCardOffset=0;protocolSourceLimits={};}
  const protocols=workbench.protocolCards(detail,protocolCardOffset,20);protocolCardOffset=protocols.offset;
  protocolVisibleSources=[];
  const protocolHtml=protocols.total?`<section aria-label="Protocol summaries"><h3>Protocol summaries</h3><p class="meta">${protocols.offset+1}–${Math.min(protocols.offset+protocols.limit,protocols.total)} of ${protocols.total} cards · original evidence retained</p><div class="metadata-query"><button class="btn small" id="protocol-previous" ${protocols.has_previous?'':'disabled'}>Previous cards</button><button class="btn small" id="protocol-next" ${protocols.has_more?'':'disabled'}>Next cards</button></div>${protocols.cards.map((x,cardIndex)=>{const refs=workbench.protocolCardSources(x),limit=protocolSourceLimits[protocolCardOffset+cardIndex] || 100;return `<div class="protocol-card">`+card(x.title,x.text,x.evidence)+(refs.length?`<details class="protocol-sources"><summary>Source references (${refs.length})</summary>${refs.slice(0,limit).map((item,i)=>{const index=protocolVisibleSources.push(item)-1;return `<button class="btn topology-source" id="protocol-source-${cardIndex}-${i}" data-protocol-source="${index}" ${item.available && !busy && !backendFailure?'':'disabled'}><strong>${esc(item.label)}</strong><span>${esc(item.precision)} · cutoff #${num(item.ref.at_packet)} · revision ${num(item.ref.analysis_revision)}</span><span>${esc(item.ref.section_id || 'Source identity unavailable')}</span></button>`;}).join('')}${refs.length>limit?`<button class="btn" data-protocol-more="${protocolCardOffset+cardIndex}">Show more sources (${limit} / ${refs.length})</button>`:''}</details>`:'')+'</div>';}).join('')}</section>`:'';
  const events = detail.events || [], languages = [...new Set(events.flatMap(e => (e.language_variants || []).map(v => v.language_code)))].sort();
  return `<div class="metadata-panel" aria-label="Signal metadata"><section class="metadata-group" aria-label="Section metadata"><h2>Section metadata</h2><p class="meta">Changes with the selected section. Reference labels are not verified current operator ownership. Original bytes remain in Hex.</p>
    ${protocolHtml}
    <h3>Satellite associations</h3>
    ${(detail.satellite_associations || []).map(x => card("Satellite candidates · " + (x.transport ? "TS " + hex(x.transport.transport_stream_id) + " / ONID " + hex(x.transport.original_network_id) : "section descriptor") + " · offset " + x.wire_source.section_offset,satelliteText(x),x)).join("") || '<p class="meta">No supported satellite delivery descriptor in this section. S2/S2X-only descriptors do not establish a slot.</p>'}
    <h3 title="Electronic Programme Guide">Multilingual EPG</h3><label for="epg-language">Preferred language</label><select id="epg-language" title="Electronic Programme Guide language"><option value="">Default (language-code order)</option>${languages.map(l => `<option value="${esc(l)}" ${epgLanguage === l ? "selected" : ""}>${esc(l)}</option>`).join("")}</select>
    ${events.map(e => {const v=eventVariant(e);return card(`Event ${hex(e.id)} · ${v.language_code || "no language"}${epgLanguage && v.language_code !== epgLanguage ? " · fallback" : ""}`, `${eventTitle(e)}\nShort: ${v.short_status || "absent"}\n${v.short_text || ""}\nExtended: ${v.extended_status || "absent"}\n${v.extended_text ?? "No complete extended text"}\n${(v.warnings || []).join("\n")}`, {event_id:e.id,service_id:e.service_id,source_id:e.source_id,variant:v});}).join("") || '<p class="meta">No EIT events in this section.</p>'}
    <h3>ID names and sources</h3>${(detail.identifier_lookups || []).map(x => card(`${x.namespace} · ${x.raw_hex}`, `${x.label || "Unknown"} · ${x.status}\n${x.uncertainty}`, x)).join("") || '<p class="meta">No supported identifiers indexed in this section.</p>'}
    <h3>Text encoding diagnostics</h3><p class="meta">${esc(detail.text_diagnostic_scope || "")}</p>${(detail.text_diagnostics || []).map(x => card(`${x.field} · ${x.language_code || "no language tag"}`, `${x.status} · ${x.effective_charset || "unknown charset"} · ${x.basis}\n${x.decoded_text}\nSelector: ${x.selector_hex || "none"} · section offset ${x.source.section_offset}\nRaw: ${x.raw_hex}\n${(x.warnings || []).join("\n")}`, x)).join("") || '<p class="meta">No supported text fields in this section.</p>'}</section>
    <section class="metadata-group metadata-lookup" aria-label="Lookup"><h2>Lookup</h2><p class="meta">Not tied to the selected section</p>
    <details id="identifier-lookup" ${lookupState.identifierOpen?'open':''}><summary title="Look up an identifier (ID) in the SDK (Software Development Kit) registry">Look up an identifier</summary><div class="metadata-query"><select id="identifier-kind" aria-label="Identifier namespace" title="Choose an identifier (ID) namespace">${workbench.identifierNamespaces.map(x=>`<option value="${x.value}" title="${esc(x.help)} · ${x.value}" ${lookupState.namespace===x.value?'selected':''}>${esc(x.label)}</option>`).join('')}</select><input id="identifier-value" value="${esc(lookupState.identifier)}" placeholder="0x0001" aria-label="Identifier value"><button class="btn small" id="identifier-query">Look up</button></div><p class="meta">Uses the analyzed standard context; choose an explicit standard and rescan if context is required.</p><div id="identifier-result" aria-live="polite">${lookupOutput('identifier')}</div><details class="lookup-raw" id="identifier-raw" ${identifierResult?'':'hidden'} ${lookupState.identifierRaw?'open':''}><summary aria-label="Raw identifier lookup JSON" title="Original JSON (JavaScript Object Notation) with all values and source evidence">Raw</summary><pre id="identifier-evidence" tabindex="0" aria-label="Original identifier lookup JSON">${identifierResult?esc(JSON.stringify(identifierResult,null,2)):''}</pre></details></details>
    <h3>Satellite lookup</h3><div class="satellite-query metadata-query"><input id="satellite-position" value="${esc(lookupState.position)}" placeholder="Degrees: 13.0" aria-label="Orbital position in degrees"><select id="satellite-direction" aria-label="Orbital direction" title="East or west of the prime meridian"><option value="E" ${lookupState.direction==='E'?'selected':''}>E</option><option value="W" ${lookupState.direction==='W'?'selected':''}>W</option></select><button class="btn small" id="satellite-query">Candidates</button></div><p class="meta" title="Geostationary Earth orbit">Nominal GEO slot only. An incomplete reference snapshot; never a confirmed satellite.</p><div id="satellite-result" aria-live="polite">${lookupOutput('satellite')}</div><details class="satellite-lookup-evidence lookup-raw" id="satellite-raw" ${satelliteResult?'':'hidden'} ${lookupState.satelliteRaw?'open':''}><summary aria-label="Raw satellite lookup JSON" title="Original JSON (JavaScript Object Notation) with all values and source evidence">Raw</summary><pre id="satellite-evidence" tabindex="0" aria-label="Original satellite lookup JSON">${satelliteResult?esc(JSON.stringify(satelliteResult,null,2)):''}</pre></details>
    </section></div>`;
}
function applyInspectorDetails(panel) {
  const container = panel?.querySelector('#inspector-details');
  if (!container) return;
  const areas = [...panel.querySelectorAll('[data-inspector-content]')];
  areas.forEach(el => { el.hidden = !inspectorDetails[el.dataset.inspectorContent]; });
  panel.querySelectorAll('[data-inspector-detail]').forEach(el => {
    el.setAttribute('aria-expanded', String(inspectorDetails[el.dataset.inspectorDetail]));
  });
  container.hidden = !areas.some(el => !el.hidden);
}
function bindInspectorSummary(panel, scroll) {
  const chips = panel?.querySelector('.inspector-chips');
  if (!chips) return;
  chips.scrollLeft = scroll;
  panel.querySelectorAll('[data-inspector-detail]').forEach(el => {
    el.onclick = () => {
      const key = el.dataset.inspectorDetail;
      inspectorDetails[key] = !inspectorDetails[key];
      applyInspectorDetails(panel);
      const target = panel.querySelector('[data-inspector-content="' + key + '"]');
      const container = panel.querySelector('#inspector-details');
      if (target && container && inspectorDetails[key]) container.scrollTop += target.getBoundingClientRect().top - container.getBoundingClientRect().top;
      saveLayout();
    };
  });
  chips.addEventListener('focusin', event => event.target?.scrollIntoView?.({block:'nearest',inline:'nearest'}));
  applyInspectorDetails(panel);
}
// One reason per blocked state, in the order a user can resolve them.
function editBlockReason() {
  if (backendFailure) return "Backend disconnected";
  if (data.coverage?.partial) return "Partial preview is read-only; run a full scan to edit or export";
  if (busy) return "Wait for the analysis to finish";
  if (comparisonEvidence) return "Unavailable while inspecting comparison evidence; use the snapshot first";
  if (detail.table_id !== 0x42) return "Rename needs an SDT (Service Description Table) section";
  if (!detail.valid) return "Rename needs a section with a valid CRC";
  if (!detail.services?.length) return "This SDT section lists no services";
  return "";
}
function renderInspector() {
  syncSiMode(); siView?.update(); summaryView?.update(); syncDocuments();
  if(palette.mode)renderPalette();
  const panel = $("#inspector");
  if (!panel) return;
  rememberLookupState(panel);
  if (tab === "Topology" && !topology.active) { renderTopologyInspector(); return; }
  const summaryScroll = panel.querySelector(".inspector-chips")?.scrollLeft || 0;
  if (aggregateDiagnostic) {
    panel.innerHTML = `<div class="panel-title">TRANSPORT DIAGNOSTIC <span class="bad">AGGREGATE</span></div><div class="empty"><span class="empty-icon bad">⚠</span><h3>${esc(aggregateDiagnostic.code)}</h3><p>${esc(aggregateDiagnostic.detail)}</p><p>${num(aggregateDiagnostic.count)} observations across monitored SI PIDs. Individual packet locations are not indexed.</p></div>`;
    return;
  }
  if (loadingDetail || detailError || !detail?.name) {
    if (tab === "Changes" && !loadingDetail && !detailError) {
      // Comparison mode replaces the record list, so a "select a record" hint
      // would point at nothing. Describe the workflow that is actually on screen.
      panel.innerHTML = sourceContextHeader()+`<div class="panel-title">SECTION INSPECTOR <span class="muted">COMPARISON</span></div><div class="empty"><span class="empty-icon">⇄</span><h3>Compare two observed states</h3><p>Choose packet cutoffs A and B in the record pane, then compare. Each change lists its own before/after evidence; selecting that evidence inspects the exact section here without moving the workbench snapshot. Use <em>Use snapshot</em> when you deliberately want the workbench to move to that cutoff.</p>${comparison.error ? `<p class="bad">${esc(comparison.error)}</p>` : ""}<p class="meta">Only observed valid current sections are compared. A missing observation is not proof that a service stopped broadcasting.</p></div>`;
      return;
    }
    panel.innerHTML = sourceContextHeader()+`<div class="panel-title">SECTION INSPECTOR</div>${comparisonEvidence && inspectionEvidence?.kind!=='topology' ? `<p class="comparison-context">${esc(comparisonEvidence)} · main snapshot unchanged</p>` : ""}<div class="empty"><span class="empty-icon">${loadingDetail ? "◌" : detailError ? "⚠" : "⌘"}</span><h3>${loadingDetail ? "Loading section…" : detailError ? "Unable to inspect section" : "Inspect the signal"}</h3><p>${esc(detailError || "Select a service, table, programme or issue to explore its source section.")}</p>${detailError && !backendFailure ? '<button class="btn" id="retry-inspect">Retry</button>' : ""}</div>`;
    bindTopologySourceHeader();bindProtocolSource();
    $("#retry-inspect")?.addEventListener("click", () =>
      inspect(selected, selectedService, selectedKey, inspectionEvidence),
    );
    return;
  }
  const nativeWarnings = workbench.inspectorWarnings(detail, data);
  const xmlSource = evidenceScope === "section" ? detail.section_tsduck_xml : detail.merged?.complete ? detail.merged.tsduck_xml : null;
  const xmlLabel = detail.native_xml_guarded ? "Guarded SDK XML" : "TSDuck XML";
  const summary = workbench.inspectorSummary(detail);
  const chip = (key, label, id, title) => `<button class="summary-chip" id="${id}" data-inspector-detail="${key}" aria-expanded="${inspectorDetails[key]}" aria-controls="${key === 'sections' ? 'section-group' : key + '-details'}" aria-label="${esc(title)}" title="${esc(title)}">${label}</button>`;
  panel.innerHTML = sourceContextHeader()+`${comparisonEvidence && inspectionEvidence?.kind!=='topology' ? `<p class="comparison-context">${esc(comparisonEvidence)} · main snapshot unchanged</p>` : ""}<div class="inspector-heading inspector-summary" role="group" aria-label="Section summary">${chip('identity', esc(summary.profile), 'standards-profile-summary-toggle', summary.profileHelp)}<div class="inspector-chips"><h2 ${tip(detail.name)}>${chip('identity', categoryBadge(detail) + (detail.valid ? '' : ' <span class="bad">INVALID</span>'), 'identity-toggle', detail.name + ' · ' + (glossary[detail.name] || detail.name) + ' · section identity and validity')}</h2>${chip('identity', 'PID ' + hex(detail.pid), 'pid-summary-toggle', glossary.PID + ' · TID: Table Identifier ' + hex(detail.table_id, 2) + (selectedService >= 0 ? ' · SID: ' + glossary.SID + ' ' + hex(selectedService) : ''))}${chip('identity', esc(summary.version), 'version-summary-toggle', 'Wire version and current/next state')}${chip('sections', esc(summary.section), 'section-group-toggle', 'Original section evidence and capture-wide table coverage')}${chip('crc', `<span class="${detail.crc?.status === 'invalid' ? 'bad' : detail.crc?.status === 'valid' ? 'ok' : 'muted'}">${esc(summary.crc)}</span>`, 'crc-toggle', glossary.CRC + ': ' + (detail.crc?.status || 'unavailable'))}${detail.distribution ? chip('arrival', num(detail.distribution.observation_count) + ' arrivals', 'arrival-toggle', 'Arrival distribution in packet positions; elapsed seconds only from a supplied bitrate') : ''}</div><div class="scope-tabs" role="group" aria-label="Decode scope" title="Section: fields + bytes · Merged: SDK tree + XML"><button class="btn small" data-scope="section" aria-pressed="${evidenceScope === 'section'}" aria-label="Selected section evidence" title="Section: fields and bytes of this exact section">Section</button><button class="btn small" data-scope="merged" aria-pressed="${evidenceScope === 'merged'}" aria-label="Merged table evidence" title="Merged: SDK (Software Development Kit) tree and XML of the complete table">Merged</button>${chip('scope', 'ⓘ', 'scope-details-toggle', 'Decode scope details and native assembly cutoff')}</div></div>${nativeWarnings.length ? `<button class="inspector-warning summary-chip" id="inspector-warning-toggle" data-inspector-detail="warnings" aria-expanded="${inspectorDetails.warnings}" aria-controls="warnings-details" aria-label="${nativeWarnings.length} truncation and decoder notes" title="Expand truncation and decoder notes"><span aria-hidden="true">⚠</span> ${nativeWarnings.length} ${nativeWarnings.length === 1 ? 'note' : 'notes'}</button>` : ''}<div class="inspector-details" id="inspector-details" hidden><div id="identity-details" data-inspector-content="identity" ${inspectorDetails.identity ? '' : 'hidden'}><p class="meta identity-line">${detail.valid ? 'VALID' : 'INVALID'} · PID ${hex(detail.pid)} · TID ${hex(detail.table_id, 2)} · ${esc(workbench.wireHeaderText(detail))} · CRC ${esc(detail.crc?.transmitted_hex || detail.crc?.status || 'unavailable')} (${esc(detail.crc?.status || 'unavailable')}) · ${num(detail.bytes)} bytes · ${num(detail.count)} observations${reportedStandards(detail) ? ' · ' + esc(reportedStandards(detail)) : ''}${selectedService >= 0 ? ' · SID ' + hex(selectedService) : ''}</p></div><div id="crc-details" data-inspector-content="crc" ${inspectorDetails.crc ? '' : 'hidden'}><p class="meta">Cyclic Redundancy Check: ${esc(detail.crc?.status || 'unavailable')} · transmitted ${esc(detail.crc?.transmitted_hex || '—')} · expected ${esc(detail.crc?.calculated_hex || '—')}</p></div>${distributionPanel(detail)}${sectionGroupPanel()}<div id="scope-details" data-inspector-content="scope" ${inspectorDetails.scope ? '' : 'hidden'}><p class="meta">Section: fields and bytes of this exact section. Merged: SDK tree and XML of the complete table.</p>${detail.native_table_at_packet != null ? `<p class="meta native-evidence" id="native-assembly-evidence">Native assembly cutoff: packet ${num(detail.native_table_at_packet)}${detail.versioning_supported===false?' · exact section only; map assembly unsupported':detail.merged?.complete ? ' · complete merged generation' : ' · incomplete / superseded: merged decode unavailable'}</p>` : ''}<p class="meta">${esc(detail.inspection_scope?.native_table || 'Native table assembly evidence cutoff')} · TSDuck: ${esc(detail.native_decode_status || 'not available')} · First evidence packet: ${num(detail.first_packet)}</p></div>${nativeWarnings.length ? `<div id="warnings-details" data-inspector-content="warnings" ${inspectorDetails.warnings ? '' : 'hidden'}><p class="meta" id="native-decode-warnings" role="note">${nativeWarnings.map(esc).join('<br>')}</p></div>` : ''}</div><div class="view-tabs" role="group" aria-label="Evidence view">${["tree", "hex", "xml", "decoded", "metadata", "references"].map((v) => `<button class="${view === v ? "active" : ""}" data-view="${v}" aria-pressed="${view === v}">${v === "tree" ? "Structure" : v === "hex" ? "Hex bytes" : v === "xml" ? xmlLabel : v === "decoded" ? "Decoded" : v === "metadata" ? "Metadata" : "References"}</button>`).join("")}</div>${view === "tree" ? '<div class="tree-toolbar"><input type="search" id="tree-search" placeholder="Find field or value…" aria-label="Search section structure"><button class="btn small" id="expand-tree" title="Expand all displayed nodes">＋</button><button class="btn small" id="collapse-tree" title="Collapse all nodes">−</button></div><div class="tree-help" id="tree-help">↑ ↓ Navigate · ← → Fold / enter · Home / End · Type to find</div><div class="tree-area" id="tree-area" role="tree" aria-label="Section structure" aria-describedby="tree-help"></div>' : view === "metadata" ? metadataPanel() : view === "references" ? referencePanel() : `<pre class="evidence" tabindex="0" aria-label="${view === "decoded" ? "SDK section display" : view === "hex" ? "Section hex dump" : xmlLabel}">${view === "decoded" ? esc(detail.section_native_text || "Native section display unavailable. Raw bytes remain in Hex.") : view === "hex" ? topologyHexDump(detail.raw_hex) : syntaxXml(xmlSource || "XML unavailable for this scope. Raw bytes remain available.")}</pre>`}<div class="inspector-footer"><span class="meta">Evidence starts at packet ${num(detail.first_packet)}</span><button class="btn" id="edit" ${editBlockReason() ? `disabled title="${esc(editBlockReason())}"` : 'title="Preview and export a renamed service"'}>Rename service…</button></div>`;
  bindTopologySourceHeader();bindProtocolSource();
  $('#protocol-previous')?.addEventListener('click',()=>{protocolCardOffset=Math.max(0,protocolCardOffset-20);renderInspector();($('#protocol-previous')?.disabled?$('#protocol-next'):$('#protocol-previous'))?.focus({preventScroll:true});});
  $('#protocol-next')?.addEventListener('click',()=>{protocolCardOffset+=20;renderInspector();($('#protocol-next')?.disabled?$('#protocol-previous'):$('#protocol-next'))?.focus({preventScroll:true});});
  bindInspectorSummary(panel, summaryScroll);
  panel.querySelectorAll("[data-scope]").forEach(el => el.onclick = () => { evidenceScope = el.dataset.scope; renderInspector(); panel.querySelector('[data-scope="' + evidenceScope + '"]').focus({preventScroll:true}); });
  const sectionChoice = panel.querySelector("#section-choice");
  if (sectionChoice) sectionChoice.onchange = () => inspect(sectionChoice.value, -1, "", inspectionEvidence);
  $("#group-show-bad")?.addEventListener("click", () => { showBadCrc = !showBadCrc; renderList(); renderInspector(); $("#group-show-bad")?.focus({preventScroll:true}); });
  $("#epg-language")?.addEventListener("change", e => { epgLanguage=e.target.value; renderList(); renderInspector(); $("#epg-language")?.focus(); });
  lookupFields.forEach(([id,key,event])=>$('#'+id)?.addEventListener(event,e=>lookupState[key]=e.target.value));
  lookupDisclosures.forEach(([id,key])=>$('#'+id)?.addEventListener('toggle',e=>lookupState[key]=e.target.open));
  $("#identifier-query")?.addEventListener("click", async () => {
    const value=$("#identifier-value").value.trim(),namespace=$("#identifier-kind").value;
    identifierResult=null;lookupState.identifierRaw=false;lookupState.identifierNotice="Looking up identifier…";
    if(!/^(?:0x[0-9a-f]+|[0-9]+)$/i.test(value) || !Number.isSafeInteger(Number(value))){lookupState.identifierNotice="Enter a whole decimal or hexadecimal ID.";refreshLookupResult('identifier');return;}
    refreshLookupResult('identifier');
    try {identifierResult=await call("lookup_identifier",{namespace,value:Number(value),standards:data.standards_context || "auto"});}
    catch(error){lookupState.identifierNotice=String(error);}
    refreshLookupResult('identifier');
  });
  $("#satellite-query")?.addEventListener("click", async () => {
    const value=$("#satellite-position").value.trim(),direction=$("#satellite-direction").value;
    satelliteResult=null;lookupState.satelliteRaw=false;lookupState.satelliteNotice="Looking up candidates…";
    if(!/^(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)$/.test(value) || Number(value)>180){lookupState.satelliteNotice="Enter degrees from 0 to 180.";refreshLookupResult('satellite');return;}
    refreshLookupResult('satellite');
    try {
      satelliteResult=await call("lookup_satellite",{orbital_position_degrees:Number(value),direction});
    } catch(error){lookupState.satelliteNotice=String(error);}
    refreshLookupResult('satellite');
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
    const sourceTarget=$('#tree-area [data-source-highlight]');
    if(sourceTarget && !treeSearch)requestAnimationFrame(()=>sourceTarget.scrollIntoView({block:'nearest'}));
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
function comparisonPacket(side) {
  const packet = comparison[side];
  return Number.isSafeInteger(packet) && packet >= 0 && packet < data.packets ? packet : null;
}
function updateComparisonMarkers() {
  const interactive = data.complete && !busy && !backendFailure && !comparison.loading;
  for (const side of ["from", "to"]) {
    const marker = $(`[data-comparison-marker="${side}"]`), packet = comparisonPacket(side);
    if (!marker) continue;
    marker.hidden = !data.complete || packet === null;
    marker.tabIndex = interactive && !marker.hidden ? 0 : -1;
    marker.setAttribute("aria-disabled", String(!interactive));
    marker.setAttribute("aria-valuemax", Math.max(0, (data.packets || 1) - 1));
    if (packet === null) continue;
    marker.style.left = (data.packets > 1 ? packet / (data.packets - 1) * 100 : 0) + "%";
    marker.setAttribute("aria-valuenow", packet);
    marker.setAttribute("aria-valuetext", "Packet " + packet);
    marker.title = `${side === "from" ? "A" : "B"} · packet ${packet} · drag to change the comparison ${side === "from" ? "start" : "end"}`;
  }
}
function moveComparisonMarker(side, packet) {
  if (!data.complete || busy || backendFailure || comparison.loading) return;
  const other = comparisonPacket(side === "from" ? "to" : "from");
  const lower = side === "to" && other !== null ? other : 0;
  const upper = side === "from" && other !== null ? other : data.packets - 1;
  packet = Math.max(lower, Math.min(upper, Math.round(packet)));
  if (comparison[side] === packet) return;
  comparison[side] = packet;
  const input = $("#compare-" + side);
  if (input) input.value = packet;
  invalidateComparison();
}
function bindComparisonMarkers() {
  $("#density").querySelectorAll("[data-comparison-marker]").forEach(marker => {
    const side = marker.dataset.comparisonMarker;
    let pointer = null, grabOffset = 0;
    const move = event => {
      const box = $("#density").getBoundingClientRect();
      if (box.width) moveComparisonMarker(side, (event.clientX - box.left - grabOffset) / box.width * (data.packets - 1));
    };
    marker.onclick = event => { event.preventDefault(); event.stopPropagation(); };
    marker.onpointerdown = event => {
      event.stopPropagation();
      if (pointer !== null || event.button !== 0 || marker.getAttribute("aria-disabled") === "true") return;
      event.preventDefault();
      const box = $("#density").getBoundingClientRect();
      grabOffset = event.clientX - box.left - comparisonPacket(side) / Math.max(1, data.packets - 1) * box.width;
      pointer = event.pointerId;
      marker.setPointerCapture(pointer);
      marker.focus({ preventScroll: true });
    };
    marker.onpointermove = event => { if (event.pointerId === pointer) move(event); };
    marker.onpointerup = event => {
      if (event.pointerId !== pointer) return;
      event.preventDefault(); event.stopPropagation();
      move(event);
      marker.releasePointerCapture(pointer);
      pointer = null;
      if (tab !== "Changes") { changeTab("Changes"); render(); }
      $("#run-comparison")?.focus({ preventScroll: true });
    };
    marker.onpointercancel = marker.onlostpointercapture = () => { pointer = null; };
    marker.onkeydown = event => {
      if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
      event.preventDefault(); event.stopPropagation();
      const step = event.shiftKey ? 1 : Math.max(1, Math.round((data.packets - 1) / Math.max(1, (data.density || []).length - 1)));
      const packet = comparisonPacket(side);
      if (packet !== null) moveComparisonMarker(side, event.key === "Home" ? 0 : event.key === "End" ? data.packets - 1 : packet + (event.key === "ArrowRight" ? step : -step));
    };
  });
  updateComparisonMarkers();
}
function renderTimeline() {
  const history=workbench.history(data,detail,allTableHistory);
  historyPage=Math.min(historyPage,Math.max(0,Math.ceil(history.length/40)-1));
  const bins = (data.density || []).length || 80;
  const packets = Number(data.coverage?.source_packets || data.packets || 0);
  // A query response re-renders the strip and replaces the focused slider, so
  // remember whether the user was operating it and restore focus afterwards.
  const timelineFocus = $("#density")?.contains(document.activeElement) ? document.activeElement.id : "";
  const dense = data.density || Array.from({ length: bins }, () => ({ count: 0, bad: 0 }));
  const at = data.selected_packet === null || data.selected_packet === undefined ? null : Number(data.selected_packet);
  const cursorPercent = at === null ? null : packets > 1 ? Math.min(100, (at / (packets - 1)) * 100) : 100;
  const interactive = data.complete && !busy && !backendFailure;
  const middle = packets > 1 ? Math.round((packets - 1) / 2) : 0;
  const observedBin = index => {
    if (!data.coverage?.partial) return true;
    const start = Math.floor(index*packets/bins), end = Math.ceil((index+1)*packets/bins);
    return (data.coverage.ranges || []).some(range => range.start_packet <= start && range.end_packet >= end);
  };
  $("#timeline").innerHTML =
    `<div class="timeline-top"><span class="panel-title">ALL TABLE ARRIVALS</span><span class="meta">${num(bins)} packet-position bins${data.coverage?.partial ? " · hatched: unread / partly read (unknown)" : ""} <span class="legend-valid">■</span> sections <span class="neg">■</span> invalid</span><span class="spacer"></span><button class="btn small" id="compare-snapshots" ${busy || backendFailure || !data.complete ? "disabled" : ""}>Compare snapshots</button><button class="btn small" id="latest" ${busy || backendFailure || !data.complete ? "disabled" : ""}>Latest state</button></div><div class="density" id="density" role="slider" tabindex="${interactive ? 0 : -1}" aria-label="Snapshot position in this transport stream" aria-valuemin="0" aria-valuemax="${Math.max(0, packets - 1)}" aria-valuenow="${at === null ? 0 : at}" aria-valuetext="${at === null ? "Latest observed state" : "Snapshot at packet " + num(at)}" ${interactive ? "" : 'aria-disabled="true"'}>${cursorPercent === null ? "" : `<span class="bin-cursor" style="left:${cursorPercent}%" aria-hidden="true"></span>`}${[["from", "a", "A"], ["to", "b", "B"]].map(([side, key, label]) => `<span id="comparison-marker-${key}" class="comparison-marker" data-comparison-marker="${side}" role="slider" tabindex="-1" aria-label="Comparison ${label} packet" aria-valuemin="0" aria-valuemax="0" hidden><span aria-hidden="true">${label}</span></span>`).join("")}<div class="bins">${dense.map((b, index) => `<div class="bin ${observedBin(index) ? "" : "unobserved"} ${b.bad && b.count && b.bad >= b.count ? "invalid" : ""}" data-bin="${index}" style="--density-alpha:${b.count ? 0.35 + Math.min(0.65, b.count / 50) : 0.12}${b.bad && b.count ? `;--invalid:${Math.min(1, b.bad / b.count)}` : ""}" title="Bin ${index + 1}${observedBin(index) ? "" : " · unread/partly read: absence unknown"} · ${num(b.count)} sections · ${num(b.bad)} invalid${interactive ? " · click to load this position" : ""}">${b.bad ? '<span class="bin-invalid" aria-hidden="true"></span>' : ""}</div>`).join("")}</div>${arrivalAxis(0, Math.max(0, packets - 1), data.timing, true)}</div><div class="history-scope"><select id="history-scope" aria-label="Table history scope"><option value="selected" ${allTableHistory?"":"selected"}>Selected table history</option><option value="all" ${allTableHistory?"selected":""}>All table history</option></select><span class="meta">${history.length} section transitions · first completed packet</span></div><div class="history">${history
      .slice(historyPage * 40, (historyPage + 1) * 40)
      .map(
        (h, i) =>
          `<button class="history-point" data-history="${historyPage * 40 + i}" ${busy || backendFailure ? "disabled" : ""}>${esc(workbench.historyText(h))}</button>`,
      )
      .join(
        "",
      )}<span class="spacer"></span><span class="meta">${num(data.packets)} packets</span></div>${history.length > 40 ? `<div class="history-pages"><button class="btn small" id="history-prev" ${historyPage === 0 ? "disabled" : ""}>← Earlier</button><span class="meta">Transitions ${num(historyPage * 40 + 1)}–${num(Math.min((historyPage + 1) * 40, history.length))} of ${num(history.length)}</span><button class="btn small" id="history-next" ${(historyPage + 1) * 40 >= history.length ? "disabled" : ""}>Later →</button></div>` : ""}`;
  $("#history-scope").onchange=event=>{allTableHistory=event.target.value==="all";historyPage=0;renderTimeline();};
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
  bindComparisonMarkers();
  if (timelineFocus) document.getElementById(timelineFocus)?.focus({ preventScroll: true });
  $("#compare-snapshots").onclick = () => { changeTab("Changes"); render(); $("#compare-from").focus(); };
  $("#density").addEventListener("click", (event) => {
    const bin = event.target.closest("[data-bin]");
    if (!bin || !interactive) return;
    snapshotAtBin(Number(bin.dataset.bin), bins, packets, true);
  });
  $("#density").addEventListener("keydown", (event) => {
    if (!interactive || event.target !== event.currentTarget) return;
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
          const h = history[Number(el.dataset.history)];
          activateHistory(h);
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
    source: data.source, revision: data.revision, queryEpoch,
  };
  $("#export").disabled = true;
  $("#export-format").disabled = exportPending;
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
  $("#diff").setAttribute("aria-live", "polite");
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
    $("#export").disabled = !!backendFailure || exportPending;
  } catch (error) {
    if (target === editTarget) {$("#diff").setAttribute("aria-live", "assertive");$("#diff").textContent = String(error);notice(String(error), "error");}
  } finally {
    if (target === editTarget) $("#preview").disabled = !!backendFailure;
  }
};
$("#export-format").onchange = () => {
  $("#export").textContent = "Save SI-only " + $("#export-format").value.toUpperCase() + " + manifest…";
};
function currentEditPreview(target, token) {
  return !!target && target === editTarget && !!token && token === preview.token &&
    target.source === data.source && target.revision === data.revision &&
    target.packet === data.selected_packet && target.queryEpoch === queryEpoch &&
    preview.after === $("#rename").value && preview.service_id === Number($("#edit-service").value);
}
$("#export").onclick = async () => {
  if (backendFailure || busy || exportPending || !preview.token || !editTarget) return;
  const target = editTarget, token = preview.token, format = $("#export-format").value;
  if (!["ts", "bin"].includes(format) || !currentEditPreview(target, token)) return;
  exportPending = true;
  $("#export").disabled = true;
  $("#export-format").disabled = true;
  try {
    let path = await invoke("plugin:dialog|save", {
      options: {
        defaultPath: "edited-si." + format,
        filters: [{ name: format === "bin" ? "Raw SI sections" : "Transport stream", extensions: [format] }],
      },
    });
    if (!path) return;
    if (target !== editTarget) return;
    if (!currentEditPreview(target, token)) {
      $("#diff").textContent = "The preview changed. Preview the edit again before exporting.";
      return;
    }
    const filename = path.split(/[\\/]/).pop();
    if (!filename.includes(".")) path += "." + format;
    else if (!filename.toLowerCase().endsWith("." + format))
      throw new Error("Use a ." + format + " output filename for this format.");
    const params = { path, format, preview_token: token };
    if (target.packet != null) params.at_packet = target.packet;
    const result = await call("export", params);
    if (target !== editTarget) return;
    notice("Exported " + num(result.bytes) + " bytes + manifest · " + result.path);
    $("#edit-dialog").close();
  } catch (error) {
    if (target === editTarget) {$("#diff").setAttribute("aria-live", "assertive");$("#diff").textContent = String(error);notice(String(error), "error");}
  } finally {
    exportPending = false;
    $("#export-format").disabled = false;
    $("#export").disabled = !!backendFailure || !currentEditPreview(editTarget, preview.token);
  }
};
$("#scan").onclick = scan;
$("#cancel-scan").onclick = cancelScan;
$("#pause-scan").onclick = pauseScan;
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
      if(classicMode){classicConfiguration=true;syncSiMode();notice("Ready — choose Start to analyze the selected transport stream");}
      else scan();
    }
  } catch (error) {
    notice(String(error), true);
  }
};
$("#about").onclick = () => $("#about-dialog").showModal();
$("#close-about").onclick = () => $("#about-dialog").close();
$("#about-dialog").querySelectorAll("[data-project-link]").forEach(link => {
  link.onclick = async event => {
    if (env.runtime === "cloud-browser") return;
    event.preventDefault();
    try {
      await invoke("open_reference", {url:link.href});
      $("#about-feedback").textContent = "Submitted to the system browser: " + link.href;
    } catch (error) {
      $("#about-feedback").textContent = "Could not open the system browser. Copy this address: " + link.href + " · " + String(error);
    }
  };
});
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
const palette={mode:"",rows:[],index:0,returnFocus:null};
function paletteBackendReason() {
  return backendFailure || (!native?"Backend unavailable":busy?"Wait for the analysis to finish":exportPending?"Wait for the export to finish":"");
}
function closePalette(restoreFocus=false) {
  palette.mode="";palette.rows=[];palette.index=0;
  $("#command-palette").hidden=true;$("#search").value=search;
  $("#search").setAttribute("aria-expanded","false");$("#search").removeAttribute("aria-activedescendant");$("#palette-status").textContent="";
  if(restoreFocus){
    const previous=palette.returnFocus;palette.returnFocus=null;
    const target=previous?.isConnected?previous:previous?.id?document.getElementById(previous.id):[...$('#list').querySelectorAll('[data-key]')].find(row=>row.dataset.key===previous?.dataset?.key);
    (target && target!==document.body && !target.disabled?target:$(".center")).focus({preventScroll:true});
  }
}
function renderPalette(reset=false) {
  const input=$("#search"),mode=input.value.trimStart()[0];
  if(mode!==">" && mode!=="#"){closePalette();return;}
  palette.mode=mode;
  let message="";
  if(mode===">") {
    palette.rows=commandTable.filter(row=>workbench.commandMatches(row.description,input.value.trimStart().slice(1))).map(row=>({...row,reason:row.reason?.() || ""}));
    message="No matching commands";
  } else {
    const result=workbench.paletteIdentifier(input.value.trimStart(),data);
    palette.rows=result.target?[{id:"identifier",description:result.label,keys:"Return",help:result.help,target:result.target,reason:paletteBackendReason() || (loadingDetail?"Wait for the current inspection to finish":"")}]:[];
    message=result.message;
  }
  palette.index=reset?0:Math.min(palette.index,Math.max(0,palette.rows.length-1));
  $("#palette-list").innerHTML=palette.rows.map((row,index)=>`<div class="palette-option" id="palette-option-${index}" role="option" aria-selected="${index===palette.index}" aria-disabled="${!!row.reason}" data-palette-index="${index}" data-command="${esc(row.id)}" title="${esc(row.reason || row.help || (row.id==='export'?'Open the SDT (Service Description Table) preview and export workflow':row.description))}"><span>${esc(row.description)}</span><kbd>${esc(row.keys || '—')}</kbd></div>`).join("");
  $("#palette-empty").textContent=palette.rows.length?"":message;$("#palette-empty").hidden=!!palette.rows.length;
  $("#command-palette").hidden=false;input.setAttribute("aria-expanded","true");
  if(palette.rows.length){input.setAttribute("aria-activedescendant","palette-option-"+palette.index);$("#palette-option-"+palette.index).scrollIntoView({block:"nearest"});}
  else input.removeAttribute("aria-activedescendant");
  $("#palette-status").textContent=palette.rows.length+" "+(mode===">"?"commands":"identifier targets")+(palette.rows.length?" available":". "+message);
}
function executePalette() {
  renderPalette();
  const row=palette.rows[palette.index];if(!row || row.reason)return;
  closePalette(true);
  if(row.target)jumpReference(row.target,"");else row.run();
}
$("#command-palette").onmousedown=event=>event.preventDefault();
$("#command-palette").onclick=event=>{const row=event.target.closest('[data-palette-index]');if(row){palette.index=Number(row.dataset.paletteIndex);executePalette();}};
$("#search").addEventListener("focus",event=>{if(event.relatedTarget && !$("#command-palette").contains(event.relatedTarget))palette.returnFocus=event.relatedTarget;});
$("#search").addEventListener("blur",()=>{if(palette.mode)closePalette();});
$("#search").oninput = (e) => {
  if(/^[>#]/.test(e.target.value.trimStart())){renderPalette(true);return;}
  const value=e.target.value;closePalette();search=value;$("#search").value=search;
  if(tab === "Topology") topology.search=search;
  page = 0;renderList();
};
$("#search").onkeydown = (event) => {
  if(event.isComposing)return;
  if(palette.mode && ["ArrowUp","ArrowDown","Enter"].includes(event.key) && !event.ctrlKey && !event.metaKey && !event.altKey) {
    event.preventDefault();event.stopPropagation();
    if(event.key==="Enter")executePalette();
    else if(palette.rows.length){palette.index=(palette.index+(event.key==="ArrowUp"?-1:1)+palette.rows.length)%palette.rows.length;renderPalette();}
  } else if (event.key === "Escape") {
    event.preventDefault();event.stopPropagation();
    if(palette.mode){closePalette(true);return;}
    search = "";if(tab === "Topology")topology.search="";
    event.target.value = "";page = 0;renderList();
  } else if(event.key==="Enter" && !event.ctrlKey && !event.metaKey && !event.altKey) {
    event.preventDefault();
    [...$('#list').querySelectorAll('[tabindex="0"], summary, [role="option"]')].find(row=>row.getClientRects().length)?.focus();
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
function focusNextRegion(backwards) {
  const visible = el => el.getClientRects().length && getComputedStyle(el).visibility !== "hidden";
  const regions = [$(".sourcebar"), $(".sidebar"), $(".center"), $("#inspector")].filter(visible);
  const current = regions.findIndex(region => region.contains(document.activeElement));
  const index = current < 0 ? (backwards ? regions.length - 1 : 0) : (current + (backwards ? -1 : 1) + regions.length) % regions.length;
  const region = regions[index];
  if (!region) return;
  const preferred = region.matches(".sidebar") ? region.querySelector('#sidebar [tabindex="0"]')
    : region.matches(".center") ? region.querySelector('#list [tabindex="0"]')
    : region.querySelector('#tree-area [tabindex="0"], .evidence[tabindex="0"], .topology-sources button');
  const candidates = region.matches(".sourcebar") ? [$("#source"), $("#scan-options-toggle")]
    : [preferred, ...region.querySelectorAll('input, button:not([tabindex="-1"]), select, textarea, summary')];
  (candidates.find(el => el && !el.disabled && visible(el)) || region).focus();
}
document.addEventListener("keydown", (e) => {
  if($("#shortcuts-dialog").open)return;
  const workbenchKeys = !document.querySelector("dialog[open]") && !dvbiWorkspace.getState().active;
  if(workbenchKeys && classicMode) {
    if(e.key==='F6') {e.preventDefault();const origin=classicConfiguration?$('.sourcebar[role=region]'):null;if(documentMode)documentWorkspace.nextRegion(e.shiftKey,$('#unified-si>.si-left .si-navigation'));else if(summaryVisible)summaryView.nextRegion(e.shiftKey,origin);else siView.nextRegion(e.shiftKey,origin);return;}
    if(e.altKey&&e.key==='ArrowLeft'){e.preventDefault();if(summaryVisible){summaryVisible=false;syncSiMode();}else siView.back();return;}
    if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='k'){e.preventDefault();const search=$('#unified-si .si-search');search.hidden=false;search.focus();return;}
  }

  if (workbenchKeys && e.key === "F6" && !e.ctrlKey && !e.metaKey && !e.altKey) {
    e.preventDefault();
    focusNextRegion(e.shiftKey);
    return;
  }
  if(e.altKey && !e.ctrlKey && !e.metaKey && !e.shiftKey && !document.querySelector("dialog[open]") && e.key === "ArrowLeft") {
    if(dvbiWorkspace.getState().active){e.preventDefault();$('#dvbi-back')?.click();return;}
    const back=topology.history.at(-1);
    if(back?.kind==='selection' && !(inspectionEvidence?.kind==='protocol' && protocolSourceHistory.length>back.protocolDepth)){e.preventDefault();selectionBack();return;}
    if(inspectionEvidence?.kind==='protocol'){e.preventDefault();$('#protocol-back')?.click();return;}
    if(tab === "Topology" || topology.revealed){e.preventDefault();topologyBack();return;}
    e.preventDefault(); // No back entry: keep navigation inside the workbench.
  }
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
    if(dvbiWorkspace.getState().active){e.preventDefault();$("#dvbi-search").focus();return;}
    e.preventDefault();
    if (tab === "Changes") { changeTab("Services"); render(); }
    $("#search").focus();
    $("#search").select();
  }
  // Match the Qt workbench: Ctrl+O opens a source, Ctrl+Enter analyzes it.
  // Buttons keep their own disabled state; open dialogs keep their keys.
  const shortcut = (e.ctrlKey || e.metaKey) && !e.altKey && !e.shiftKey && workbenchKeys;
  if (shortcut && (e.key === "." || e.code === "Period")) {
    e.preventDefault();
    if (!$("#cancel-scan").hidden && !$("#cancel-scan").disabled) $("#cancel-scan").click();
  } else if (shortcut && e.key.toLowerCase() === "o") {
    e.preventDefault();
    if (!$("#browse").disabled) $("#browse").click();
  } else if (shortcut && e.key === "Enter" && (e.target === document.body || (e.target.closest?.(".sourcebar") && e.target.id !== "source"))) {
    e.preventDefault();
    if (!$("#scan").disabled) $("#scan").click();
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
  if (message) notice(message, "warning");
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
    inspectorDetails = workbench.inspectorDisclosure(saved.inspectorDetails);
  } catch (error) {
    preferredLayout = {};
    inspectorDetails = workbench.inspectorDisclosure();
    // Parsing/shape errors recover to defaults; inaccessible storage is also
    // harmless. Do not remove another version or any unrelated application data.
    layoutStorageWarning("Layout defaults restored");
  }
}
function saveLayout(reset = false) {
  try {
    if (reset) window.localStorage.removeItem(LAYOUT_KEY);
    else {
      const layout = { version: 1, widths: preferredLayout };
      if (Object.values(inspectorDetails).some(Boolean)) layout.inspectorDetails = inspectorDetails;
      window.localStorage.setItem(LAYOUT_KEY, JSON.stringify(layout));
    }
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
  const panes = $("#panes");
  if(!panes.clientWidth)return; // The retained TS workspace is hidden in XML mode.
  const defaults = defaultLayout();
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
    if (event.altKey) return;
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
  inspectorDetails = workbench.inspectorDisclosure();
  renderInspector();
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
    input_kind:dvbiWorkspace.getState().active?"dvbi":"ts",dvbi:dvbiWorkspace.getState(),
    settled:!resultLoading && !dvbiWorkspace.getState().loading && !dvbiWorkspace.getState().importing && !dvbiWorkspace.getState().inspectLoading && !busy && !loadingDetail && !comparison.loading && pending.size === 0 && !pendingSnapshotTimer,
    runtime:{driver:env.driver,user_agent:navigator.userAgent},viewport:{width:innerWidth,height:innerHeight,device_pixel_ratio:devicePixelRatio},
    scan_control:{busy,cancelling,pause_pending:pausePending,request_id:activeAnalyze,coverage:data.coverage,result_loading:resultLoading,result_pages:resultPages},
    source:data.source || "",analysis_status:data.analysis_status || "idle",selected,selected_service:selectedService,packet:data.selected_packet,
    theme:document.documentElement.dataset.theme, explorer:explorerRows().map(row=>{const el=[...document.querySelectorAll(".explorer-row")].find(el=>el.dataset.explorerKey===explorerKey(row));return {...row,selected:explorerSelected(row),color:el ? getComputedStyle(el.querySelector("[data-table-name]")).color : "",glyph:el?.querySelector(".pid-table-icon").textContent};}), table_filter:{pid:pidFilter ?? -1,name:filter,count_unit:"logical_tables"},
    records:(()=>{const m=workbench.tables(data,pidFilter,filter,showBadCrc,search);return {groups:m.groups.map(g=>g.id),sections:m.sections.map(r=>r.id),hidden:m.hidden,count_text:m.count_text,grouped:groupedTables,page};})(),
    history:{all:allTableHistory,entries:workbench.history(data,detail,allTableHistory),page:historyPage},evidence_scope:evidenceScope,
    protocol_source:{resolution:protocolResolution,return_depth:protocolSourceHistory.length},topology:{profile:topology.snapshot?.interpretation_profile,cutoff:topology.snapshot?.at_packet,selected_node:topology.selected,focused_node:topology.focused,expanded_ids:Object.keys(topology.expanded).filter(id=>topology.expanded[id]),search:topology.search,family:topology.family,loaded_nodes:workbench.topologyNodes(topology.snapshot || {}).length,total_nodes:topology.snapshot?.counts?.nodes,loading:topology.loading,stale:topology.stale,error:topology.error,evidence_ref:topology.active,locator_resolution:topology.resolution,return_depth:topology.history.length},inspection_context:inspectionEvidence?.kind || (comparisonEvidence?"comparison":"workspace"),
    documents:documentWorkspace?.snapshot(),document_mode:documentMode,classic_frame:classicState(),unified:siView?.snapshot(),classic_mode:classicMode,tab,inspector:view,tree_search:treeSearch,focused_tree_path:document.activeElement?.dataset.nodePath || "",tree,tree_limit:2500,
    controls:[...document.querySelectorAll("[id]")].slice(0,1000).map(el=>({id:el.id,visible:visible(el),enabled:!el.disabled,focused:el===document.activeElement,
      text:(el.getAttribute("aria-label") || el.value || el.textContent || "").slice(0,512),bounds:bounds(el)})),controls_limit:1000,
    diagnostics:{pending:pending.size,error:backendFailure || detailError,recent_responses:recentResponses.slice(),frontend_errors:frontendErrors.slice()},
    source_map:{tree:"ui/tauri/web/app.js:sectionTree/drawNode",style:"ui/tauri/web/style.css",transport:"ui/tauri/src-tauri/src/main.rs"}};
}
function uiAction(action) {
  if(dvbiWorkspace.getState().active)throw new Error("This action belongs to the transport-stream workspace. Switch input kind before using TS UI actions.");
  if (action.name === "select_tab" && ["Services","Topology","Tables","EPG","Issues","Changes"].includes(action.value)) {
    const target = [...document.querySelectorAll("[data-tab]")].find(el=>el.dataset.tab===action.value);
    if (!target) throw new Error("Tab unavailable"); target.click();
  } else if (action.name === "select_record" && (data.tables || []).some(r=>r.id===action.id)) { changeTab("Tables");inspect(action.id);
  } else if (action.name === "set_bad_crc" && typeof action.value === "boolean") {showBadCrc=action.value;page=0;render();
  } else if (action.name === "set_grouped" && typeof action.value === "boolean") {groupedTables=action.value;page=0;renderList();
  } else if (action.name === "search_records" && typeof action.value === "string" && action.value.length<=512) {search=action.value;if(tab==='Topology')topology.search=search;page=0;$("#search").value=search;renderList();
  } else if (action.name === "set_scope" && ["merged","section"].includes(action.value)) {evidenceScope=action.value;renderInspector();
  } else if (action.name === "set_view" && ["Structure","Hex","XML","Decoded","Metadata","References"].includes(action.value)) {view={Structure:"tree",Hex:"hex",XML:"xml",Decoded:"decoded",Metadata:"metadata",References:"references"}[action.value];renderInspector();
  } else if (action.name === "history_scope" && typeof action.value === "boolean") {allTableHistory=action.value;historyPage=0;renderTimeline();
  } else if (action.name === "history_jump" && Number.isInteger(action.index) && action.index>=0 && action.index<workbench.history(data,detail,allTableHistory).length) {const h=workbench.history(data,detail,allTableHistory)[action.index];activateHistory(h);
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
  catch(error) { notice("Diagnostics failed: " + String(error), "error"); }
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
        queueProgress(msg.state);
      }
      return;
    }
    const job = pending.get(msg.id);
    if (!job) return;
    recentResponses.push({id:msg.id, method:job.method, ok:!msg.error, error:msg.error?.message || "", at:new Date().toISOString()});
    if (recentResponses.length > 40) recentResponses.shift();
    pending.delete(msg.id);
    if (job.method === "analyze") clearProgress();
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
  await listenForFileDrop();
  if (env.runtime !== "cloud-browser") await native.event.listen("core-close-blocked", () => {
    notice("An export is still running. Wait for it to finish before closing.", "warning");
  });
  if (env.agent_enabled) pollUiAgent();
  if (env.backend_alive === false)
    disconnectBackend("Native backend stopped. Restart the application.");
  if (backendFailure) return;
  $("#source").value = env.sample || "";
  classicFrame?.update();
  if($("#classic-version"))$("#classic-version").textContent=env.version||"development";
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
  pauseScan,
  snapshot,
  inspect,
  call,
  getState: () => data,
  getDetail: () => detail,
  getComparison: () => comparison.result,
  getTopology: () => topology.snapshot,
  getDvbi: () => dvbiWorkspace.getSnapshot(),
  getDvbiDetail: () => dvbiWorkspace.getDetail(),
  getUiState: uiState,
};
// The classic core SI view and advanced workbench share the same live engine.
function syncSiMode() {
  const active=classicMode && !dvbiWorkspace.getState().active;
  document.body.classList.toggle('si-mode',active);applyTheme();
  const panel=$('#unified-si');if(panel){panel.hidden=!active;panel.classList.toggle('si-summary-mode',summaryVisible&&!documentMode);panel.classList.toggle('si-document-mode',documentMode);panel.classList.toggle('si-tree-hidden',!classicTree);}
  const documentsPanel=$('#document-workspace');if(documentsPanel)documentsPanel.hidden=!documentMode;
  const summary=$("#transport-si");if(summary)summary.hidden=!active||!summaryVisible||documentMode;
  const summaryButton=$("#summary-toggle");if(summaryButton)summaryButton.textContent=summaryVisible?"Return to inspector":"Summary / PID";
  const button=$('#workspace-toggle');if(button)button.textContent=classicMode?'Advanced workspace':'SI Inspector';
  document.body.classList.toggle('classic-configuration',classicConfiguration);document.body.classList.toggle('classic-no-status',!classicStatus);
  const frame=$('#classic-frame');if(frame)frame.hidden=!active;classicFrame?.update();
  document.title='ShowPsiSi'+(data.source?' - '+String(data.source).split(/[\\/]/).pop():'')+(active?(summaryVisible?' - Summary':detail.id?' - '+detail.name+' PID '+hex(detail.pid):''):'');
}
const siPanel=document.createElement('section');siPanel.id='unified-si';siPanel.setAttribute('aria-label','PSI / SI inspector');$('#panes').before(siPanel);
const workspaceButton=document.createElement('button');workspaceButton.id='workspace-toggle';workspaceButton.className='btn';workspaceButton.textContent='Advanced workspace';$('.titlebar').append(workspaceButton);
workspaceButton.onclick=()=>{summaryVisible=false;classicMode=!classicMode;syncSiMode();siView.update();};
const summaryPanel=document.createElement('section');summaryPanel.id='transport-si';summaryPanel.hidden=true;
const summaryButton=document.createElement('button');summaryButton.id='summary-toggle';summaryButton.className='btn';summaryButton.textContent='Summary / PID';workspaceButton.before(summaryButton);
summaryButton.onclick=()=>{classicMode=true;summaryVisible=!summaryVisible;syncSiMode();summaryView.update();};
summaryView=TransportSi.create(summaryPanel,{state:()=>data,busy:()=>busy||!!backendFailure,call,activate:(record,pid)=>{summaryVisible=false;classicMode=true;syncSiMode();siView.filterPid(pid);siView.selectRecord(record,record.id,null,true,false);}});
siView=UnifiedSi.create(siPanel,{state:()=>data,detail:()=>detail,pending:()=>loadingDetail,busy:()=>busy||!!backendFailure,error:()=>detailError||backendFailure,inspect:id=>inspect(id),carousel:id=>openCarousel(id),topology:()=>topology.stale?null:topology.snapshot,
  service:s=>openServices(s),packet:pid=>openPacket(pid,0),loadTopology:async()=>{await loadTopology();let pages=0;while(topology.snapshot?.page?.has_more&&!topology.error&&pages++<100)await loadTopology(true);}});
siPanel.append(summaryPanel);
const documentsPanel=document.createElement('div');documentsPanel.id='document-workspace';documentsPanel.hidden=true;siPanel.append(documentsPanel);
documentWorkspace=DocumentWorkspace.create(documentsPanel,{
 create:(content,d,v)=>{
  if(d.kind==='si'){
   const panel=document.createElement('section');panel.className='si-document';content.append(panel);let payload=d.payload;
   const ui=UnifiedSi.create(panel,{state:()=>payload._view_state||data,detail:()=>payload,pending:()=>false,busy:()=>busy,error:()=>'',inspect:id=>inspect(id),topology:()=>topology.stale?null:topology.snapshot,loadTopology:async()=>{}});
   v.update=next=>{payload=next.payload;ui.update();};v.snapshot=()=>ui.snapshot();v.focusNode=path=>ui.focusNode(path);v.nextRegion=(back,origin)=>ui.nextRegion(back,origin);v.dispose=()=>ui.dispose();ui.update();
  }else if(d.kind==='carousel'){const state=d.payload._view_state||data;const ui=CarouselView.create(content,{state:()=>state,busy:()=>busy||!!backendFailure,call,section:async(id,path,cutoff)=>{await inspect(id,-1,'carousel:'+id,{kind:'service',atPacket:cutoff,revision:state.analysis_revision||state.revision});if(detail.id===id&&data.source===state.source&&(data.analysis_revision||data.revision)===(state.analysis_revision||state.revision)){openDocument('si');documentWorkspace.focusSection(id,path,cutoff);}}},d.payload.source_id);v.snapshot=()=>ui.snapshot();v.dispose=()=>ui.dispose();
  }else if(d.kind==='service'){const state=d.payload._view_state||data;const ui=ServiceView.create(content,{state:()=>state,busy:()=>busy||!!backendFailure,call,section:async(id,path,cutoff)=>{await inspect(id,-1,'service:'+id,{kind:'service',atPacket:cutoff,label:'Service source at packet '+cutoff,revision:state.analysis_revision||state.revision});if(detail.id===id&&data.source===state.source&&(data.analysis_revision||data.revision)===(state.analysis_revision||state.revision)){openDocument('si');documentWorkspace.focusSection(id,path,cutoff);}}},d.payload.service);v.snapshot=()=>ui.snapshot();v.dispose=()=>ui.dispose();
  }else if(d.kind==='statistics'){const ui=StatisticsView.create(content,{state:()=>data,busy:()=>busy||!!backendFailure,call,packet:(pid,index)=>openPacket(pid,index)});v.snapshot=()=>ui.snapshot();v.dispose=()=>ui.dispose();
  }else if(d.kind==='packet'){const ui=PacketExplorer.create(content,{state:()=>data,busy:()=>busy||!!backendFailure,call,section:id=>inspect(id)},{pid:d.payload.pid,index:d.payload.index});v.snapshot=()=>ui.snapshot();v.dispose=()=>ui.dispose();
  }else if(d.kind==='summary'){
   const panel=document.createElement('section');panel.className='transport-si';content.append(panel);
   const ui=TransportSi.create(panel,{state:()=>data,busy:()=>busy||!!backendFailure,call,activate:(record)=>inspect(record.id)});v.update=()=>ui.update();v.dispose=()=>ui.dispose();ui.update();
  }else{const text=document.createElement('textarea');text.readOnly=true;text.setAttribute('aria-label','Native decoded table');content.append(text);v.update=next=>{const value=next.payload.section_native_text||next.payload.native_text||next.payload.raw_hex||'No selected table';if(text.value!==value)text.value=value;};}
 },changed:state=>{classicFrame?.update();if(documentMode&&classicMode){const active=state.items.find(d=>d.id===state.active);document.title='ShowPsiSi - '+(active?.title||documentScope());}}
});
let documentIdentity='',documentLastDetail='';
function syncDocuments(){
 if(!documentWorkspace)return;const identity=[data.source,data.analysis_revision||data.revision].join('|');
 if(documentIdentity!==identity){documentIdentity=identity;documentWorkspace.reset(identity);documentLastDetail='';}
 if(documentMode&&detail.id&&!loadingDetail&&detail.id+'@'+data.selected_packet!==documentLastDetail){documentLastDetail=detail.id+'@'+data.selected_packet;openDocument('si');}
}
function openCarousel(sourceId){documentMode=true;classicMode=true;documentLastDetail=detail.id+'@'+data.selected_packet;documentWorkspace.open('carousel','carousel@'+data.selected_packet,documentScope()+' - DSM-CC / OC Files',{source_id:sourceId||detail.id,_view_state:structuredClone(data)});syncSiMode();}
function openServices(service){documentMode=true;classicMode=true;documentLastDetail=detail.id+'@'+data.selected_packet;const key=service?service.onid+':'+service.ts_id+':'+service.id:'all';documentWorkspace.open('service',key+'@'+data.selected_packet,documentScope()+' - Services / EPG',{service,_view_state:structuredClone(data)});syncSiMode();}
function documentScope(cutoff){const at=cutoff===undefined?data.selected_packet:cutoff;return String(data.source||'Transport stream').split(/[\\/]/).pop()+' [analysis '+(data.analysis_revision||data.revision||0)+', '+(at==null?'latest':'packet '+at)+']';}
function openPacket(pid,index){documentMode=true;classicMode=true;documentLastDetail=detail.id+'@'+data.selected_packet;documentWorkspace.open('packet',String(pid),documentScope()+' - Packet Explorer'+(pid<0?'':' PID '+hex(pid)),{pid:pid<0?null:pid,index:index||0});syncSiMode();}
function openDocument(kind,duplicate=false){
 if(!documentWorkspace)return;const payload=kind==='summary'?{}:structuredClone(detail),key=kind==='summary'?'summary':(detail.id||'empty')+'@'+detail.native_table_at_packet;if(kind!=='summary'){payload._view_state=structuredClone(data);payload._view_state.selected_packet=detail.native_table_at_packet;}
 const title=documentScope(kind==='summary'?undefined:detail.native_table_at_packet)+' - '+(kind==='summary'?'Summary':kind==='decoded'?'Native Decode':detail.id?detail.name+' PID '+hex(detail.pid):'SI Inspector');
 documentWorkspace.open(kind,key,title,payload,duplicate);documentLastDetail=detail.id+'@'+data.selected_packet;syncSiMode();
}
document.addEventListener('keydown',event=>{if(!documentMode||!classicMode||document.querySelector('dialog[open]'))return;if(event.ctrlKey&&event.key==='F4'){event.preventDefault();documentWorkspace.close();}else if(event.ctrlKey&&event.key==='Tab'){event.preventDefault();documentWorkspace.cycle(event.shiftKey);}});

const framePanel=document.createElement('header');framePanel.id='classic-frame';framePanel.className='classic-frame';$('.titlebar').before(framePanel);
const helpDialog=document.createElement('dialog');helpDialog.id='classic-help';helpDialog.innerHTML='<h2>ShowPsiSi Help</h2><p>Open a transport stream, then choose Analyzer → Start. Programs and PSI Packets lead to fields and original bytes. Click text to select; double-click text or click +/− to expand. F6 / Shift+F6 changes panes. Alt+Left returns. Card Configuration contains source and scan options. Advanced workspace retains topology, editing, history and DVB-I.</p><button class="btn">Close</button>';$('#app').append(helpDialog);helpDialog.querySelector('button').onclick=()=>helpDialog.close();
const footer=$('#app > footer');for(const [id,text] of [['product','ShowPsiSi'],['version','development'],['num',''],['scroll','']]){const cell=document.createElement('span');cell.id='classic-'+id;cell.className='classic-status-part';cell.textContent=text;footer.append(cell);}
function classicState(){return {available:!backendFailure,busy,cancelling,canPause:activeAnalyze!==null&&!resultLoading,paused:data.analysis_status==='paused',hasInput:!!$('#source').value.trim(),complete:!!data.complete,native:!!env.driver&&env.runtime!=='cloud-browser',exporting:exportPending,toolbar:classicToolbar,status:classicStatus,tree:classicTree,documentCount:documentMode?(documentWorkspace?.snapshot().items.length||0):(data.complete?1:0),features:{documents:true,packets:true,bitrate:true,services:true,carousel:true}};}
async function classicCommand(id){const state=classicState();if(!classic.enabled(id,state)){notice(classic.reason(id,state),'warning');return;}
 if(id==='open')await $('#browse').onclick();
 else if(id==='start')scan();else if(id==='stop')cancelScan();else if(id==='pause')pauseScan();
 else if(id==='toolbar')classicToolbar=!classicToolbar;else if(id==='status')classicStatus=!classicStatus;else if(id==='tree')classicTree=!classicTree;
 else if(id==='configuration'){classicConfiguration=!classicConfiguration;syncSiMode();if(classicConfiguration)$('#source').focus();}
 else if(id==='new'){documentMode=true;openDocument('si',true);}
 else if(id==='decoded'){documentMode=true;openDocument('decoded');}
 else if(id==='packets')openPacket(-1,0);
 else if(id==='carousel')openCarousel();
 else if(id==='services')openServices(null);
 else if(id==='bitrate'){documentMode=true;classicMode=true;documentLastDetail=detail.id+'@'+data.selected_packet;documentWorkspace.open('statistics','statistics',documentScope()+' - Bitrate / Timing',{});}
 else if(id==='close')documentWorkspace.close();
 else if(['cascade','tile','arrange'].includes(id))documentWorkspace.arrange(id);
 else if(id==='summary'){if(documentMode)openDocument('summary');summaryVisible=true;classicMode=true;syncSiMode();summaryView.update();}
 else if(id==='advanced')$('#workspace-toggle').click();else if(id==='dvbi'){$('#input-kind').value='dvbi';$('#input-kind').dispatchEvent(new Event('change'));}
 else if(id==='about')$('#about').click();else if(id==='index')helpDialog.showModal();else if(id==='messages')$('#messages').click();
 else if(id==='diagnostics')$('#save-diagnostics').click();else if(id==='exit'){try{await invoke('close_application');}catch(error){notice(String(error),true);}}
 syncSiMode();
}
classicFrame=ClassicFrame.create(framePanel,{state:classicState,command:classicCommand,locks:value=>{$('#classic-num').textContent=value.num?'NUM':'';$('#classic-scroll').textContent=value.scroll?'SCRL':'';}});
$('#source').addEventListener('input',()=>classicFrame.update());
syncSiMode();
boot().catch((error) => {
  disconnectBackend("Backend connection failed: " + String(error));
});
