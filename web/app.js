"use strict";
/* Rental Housing Law Navigator - static front end. Reads data/app_data.json (made by 07_export_web.py). */
const $ = (s, r = document) => r.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const flat = (s) => String(s ?? "").replace(/\s+/g, " ").trim();

const T = {
  en: {
    title: "Rental Housing Law Navigator",
    sub: "Which rules apply at an address, on a date - with sources. CA, NJ and MA corpus.",
    kicker: "RENTAL LAW / CA · NJ · MA", hero: "What rules shape this address?",
    disc: "Prototype for research and demonstration. NOT legal advice or a compliance certification. Built from public law text that has not been reviewed by counsel.",
    tabs: { lookup: "Address lookup", changes: "Change tests", how: "How it works" },
    address: "Address", asof: "As-of date", ph: "Type a street, city or ID (e.g. Clinton St)",
    examples: "Try:", none: "Pick an address to see which rules apply.",
    facts: "Building facts", legal: "Legal city (Census)", mailing: "Mailing city", county: "County", built: "Year built", units: "Units", use: "Assessor use",
    missing: "missing", range: "range only", resolvedBy: "Resolved by",
    layers: "Jurisdiction layers", addressBase: "Address base", addressDetails: "Property facts anchor every lookup.", state: "State", county: "County", city: "City", future: "Pending & future",
    nocounty: "none in corpus", stackhint: "Click a layer to filter the list",
    results: "Rules for this address", showAll: "Show all layers", considered: "Considered but NOT in force",
    jurisdiction: "Jurisdiction", allJurisdictions: "All jurisdictions", exportJSON: "JSON", exportCSV: "CSV",
    layerDetails: "Selected layer", openAudit: "View source audit", closeAudit: "Close audit", emptyLayer: "No rules in this layer for this address and date.",
    auditEyebrow: "SOURCE RECORD", layerAddress: "Property base",
    cat: { rent_increase_limits: "Rent increase limits", just_cause_eviction: "Just-cause eviction", security_deposits: "Security deposits",
      application_screening_fees: "Application & screening fees", screening_restrictions: "Screening restrictions", algorithmic_rent_setting: "Algorithmic rent-setting" },
    res: { applies: "Applies", superseded: "Superseded", unknown: "Unknown", not_yet_effective: "Not yet effective", pending: "Pending bill", failed: "Failed" },
    conflict: "Conflict - human review", audit: "Audit: source, quote & reasoning", source: "Source", retrieved: "Retrieved", asOfL: "As-of date", effective: "Effective date",
    citation: "Citation", quote: "Quoted text", reasoning: "Reasoning", confidence: "Confidence", also: "Also stated in", conflictNote: "Conflict note",
    boundary: "Reasoning boundary: this answer uses only the public parcel facts shown above (year built, unit count, assessor use description) and the legal city from the Census Geocoder. Owner type, tenancy dates, rent levels, certificate-of-occupancy dates and exemption filings are not in the data, so rules that depend on them are reported as Unknown rather than guessed.",
    tchanges: "Supplied change tests", affected: "affected addresses", conflicts: "flagged for human review", pass: "PASS", fail: "CHECK", showAddr: "Show affected addresses", open: "Open",
    how: "How it works", dl: "Download submission files", noRules: "No rules apply or the data is missing.",
    ex: { sf: "San Francisco, pre-1979", hob: "Hoboken", bos: "Boston", ber: "Berkeley (no year)", la: "Los Angeles RSO-age" },
    chips: { today: "Today", beforeT1: "Before AB 325", afterT1: "After AB 325", fair: "FAIR Act in effect" },
    foot: "Sources: public state/municipal law text, Census Geocoder, public assessor data. Every answer cites its source text and retrieval date.",
  },
};

const COLORS = { applies: "var(--ok)", superseded: "var(--sup)", unknown: "var(--unk)", not_yet_effective: "var(--nye)", pending: "var(--pend)", failed: "var(--flag)" };
const S = { data: null, asOf: "2026-10-01", addr: null, level: null, jurisdiction: "", auditId: null, tab: "lookup" };
const t = () => T.en;

/* ------------------------------------------------------------------ data helpers */
function prep() {
  const d = S.data;
  d.rulesById = Object.fromEntries(d.rules.map((r) => [r.team_rule_id, r]));
  d.addrById = Object.fromEntries(d.addresses.map((a) => [a.id, a]));
  d.snapDates = d.snapshots.map((s) => s.date);
}
function snapshotFor(date) {
  let pick = 0;
  d_loop: for (let i = 0; i < S.data.snapDates.length; i++) { if (S.data.snapDates[i] <= date) pick = i; else break d_loop; }
  return S.data.snapshots[pick];
}
function entriesFor(aid, date) {
  const d = S.data, cur = { ...(d.base[aid] || {}) };
  const diff = snapshotFor(date).diff[aid] || {};
  for (const [rid, v] of Object.entries(diff)) { if (v === null) delete cur[rid]; else cur[rid] = v; }
  return Object.entries(cur).map(([rid, v]) => ({ rid, result: v[0], flag: !!v[1], conf: v[2], why: d.strings[v[3]], rule: d.rulesById[rid] }));
}
const ruleTitle = (r) => r.title;
const ruleReq = (r) => r.requirement;
const fmtConf = (c) => (c >= 0.8 ? "high" : c >= 0.6 ? "medium" : "low") + ` (${Math.round(c * 100)}%)`;

/* ------------------------------------------------------------------ rendering: lookup */
function renderStatic() {
  document.documentElement.lang = "en";
  $("#t-title").textContent = t().title; $("#t-sub").textContent = t().sub;
  $("#t-kicker").textContent = t().kicker; $("#t-hero").textContent = t().hero;
  $("#disclaimer").textContent = t().disc; $("#foot").textContent = t().foot;
  for (const k of ["lookup", "changes", "how"]) $("#tab-" + k).textContent = t().tabs[k];
  $("#l-address").textContent = t().address; $("#l-asof").textContent = t().asof; $("#q").placeholder = t().ph;
  document.title = t().title;
  renderExamples(); renderDateChips();
  if (S.auditId) renderAuditPanel(S.auditId);
}
function pickExample(pred) { return S.data.addresses.find(pred); }
function renderExamples() {
  const ex = [
    ["sf", pickExample((a) => a.legal_city === "San Francisco, CA" && a.year_built && a.year_built < 1978 && a.units)],
    ["hob", pickExample((a) => a.legal_city === "Hoboken, NJ")],
    ["bos", pickExample((a) => a.legal_city === "Boston, MA")],
    ["ber", pickExample((a) => a.legal_city === "Berkeley, CA" && !a.year_built)],
    ["la", pickExample((a) => a.legal_city === "Los Angeles, CA" && a.year_built && a.year_built < 1978 && a.units)],
  ].filter((e) => e[1]);
  $("#examples").innerHTML = `<span class="muted" style="font-size:12.5px;align-self:center">${esc(t().examples)}</span>` +
    ex.map(([k, a]) => `<button class="chip" data-addr="${a.id}">${esc(t().ex[k])}</button>`).join("");
}
function renderDateChips() {
  const chips = [["today", "2026-10-01"], ["beforeT1", "2025-12-31"], ["afterT1", "2026-01-02"], ["fair", "2027-07-02"]];
  $("#datechips").innerHTML = chips.map(([k, d]) => `<button class="chip ${S.asOf === d ? "on" : ""}" data-date="${d}">${esc(t().chips[k])}</button>`).join("");
  $("#asof").value = S.asOf;
}
function levelOf(e) { return e.result === "pending" || e.result === "not_yet_effective" ? "future" : e.rule.level; }

function renderResult() {
  const root = $("#result");
  const a = S.addr && S.data.addrById[S.addr];
  if (!a) { root.innerHTML = `<div class="card empty-note">${esc(t().none)}</div>`; return; }
  const entries = entriesFor(a.id, S.asOf);
  const counts = { state: {}, county: {}, city: {}, future: {} };
  entries.forEach((e) => { const l = levelOf(e); counts[l][e.result] = (counts[l][e.result] || 0) + 1; });
  const shown = entries.filter((e) => (!S.level || S.level === "address" || levelOf(e) === S.level)
    && (!S.jurisdiction || e.rule.jurisdiction === S.jurisdiction));
  const byCat = {};
  shown.forEach((e) => (byCat[e.rule.category] ||= []).push(e));
  const cats = Object.keys(t().cat).filter((c) => byCat[c]);

  const conf = a.method === "census_geocoder" ? "Census Geocoder" : a.method === "source_dataset_fallback" ? "city parcel dataset (fallback)" : "unresolved";
  const facts = `
    <div class="card facts">
      <h2>${esc(a.street)}</h2>
      <dl>
        <dt>${esc(t().legal)}</dt><dd>${esc(a.legal_city || "-")}</dd>
        <dt>${esc(t().mailing)}</dt><dd>${esc(a.postal_city)}${a.legal_city && a.legal_city.split(",")[0] !== a.postal_city ? " ⚠" : ""}</dd>
        <dt>${esc(t().county)}</dt><dd>${esc(a.county || "-")}</dd>
        <dt>${esc(t().built)}</dt><dd>${a.year_built ? a.year_built : `<span class="muted">${esc(t().missing)}</span>`}</dd>
        <dt>${esc(t().units)}</dt><dd>${a.units ? a.units : a.units_hint ? `<span class="muted">${esc(t().range)}</span>` : `<span class="muted">${esc(t().missing)}</span>`}</dd>
        <dt>${esc(t().use)}</dt><dd>${esc(a.use_description || "-")}</dd>
        <dt>${esc(t().resolvedBy)}</dt><dd>${esc(conf)}</dd>
      </dl>
      ${a.note ? `<div class="warnbox">${esc(a.note)}</div>` : ""}
      ${stackHtml(counts, entries, a)}
    </div>`;

  const body = cats.length ? cats.map((c) => `
    <div class="cat"><h3>${esc(t().cat[c])}</h3>${byCat[c].map(ruleCard).join("")}</div>`).join("")
    : `<div class="card empty-note">${esc(t().noRules)}</div>`;

  const failed = S.data.rules.filter((r) => r.status === "failed" && (r.jurisdiction === a.state || r.jurisdiction === a.legal_city));
  const failedHtml = failed.length ? `<div class="cat"><h3>${esc(t().considered)}</h3>${failed.map((r) => ruleCard({ rid: r.team_rule_id, result: "failed", flag: false, conf: r.confidence ?? 0.7, rule: r,
    why: "Ballot question / proposal that did not become law. It is shown so you can see it was considered; it imposes nothing here." })).join("")}</div>` : "";

  const jurisdictions = [...new Set(entries.map((e) => e.rule.jurisdiction))].sort();
  root.innerHTML = `<div class="grid">${facts}<div>
      <div class="results-head">
        <strong>${esc(t().results)} <span class="muted">· ${esc(S.asOf)}</span></strong>
        <div class="results-tools">
          <label class="filter-label" for="jurisdiction-filter">${esc(t().jurisdiction)}</label>
          <select id="jurisdiction-filter" aria-label="${esc(t().jurisdiction)}">
            <option value="">${esc(t().allJurisdictions)}</option>
            ${jurisdictions.map((j) => `<option value="${esc(j)}" ${S.jurisdiction === j ? "selected" : ""}>${esc(j)}</option>`).join("")}
          </select>
          <button class="export-btn" data-export="json" title="Export visible rules as JSON"><span aria-hidden="true">↓</span> ${esc(t().exportJSON)}</button>
          <button class="export-btn" data-export="csv" title="Export visible rules as CSV"><span aria-hidden="true">↓</span> ${esc(t().exportCSV)}</button>
          ${S.level || S.jurisdiction ? `<button class="reset-filter" data-level="">${esc(t().showAll)}</button>` : ""}
        </div>
      </div>
      ${body}${failedHtml}</div></div>`;
  if (S.auditId) renderAuditPanel(S.auditId);
}

function ruleCard(e) {
  const r = e.rule, future = e.result === "not_yet_effective" || e.result === "pending";
  return `<article class="rule ${future ? "future" : ""} ${e.result === "pending" ? "pending" : ""}" style="--bc:${COLORS[e.result]}">
    <header><h4>${esc(ruleTitle(r))}</h4>
      <div class="rule-actions"><div class="badges"><span class="badge b-${e.result}">${esc(t().res[e.result])}</span>${e.flag ? `<span class="badge flag">⚑ ${esc(t().conflict)}</span>` : ""}</div>
      <button class="audit-trigger" data-audit="${esc(e.rid || r.team_rule_id)}">${esc(t().openAudit)}</button></div></header>
    <div class="cite">${esc(r.jurisdiction)} · ${esc(r.citation)}${r.key_value ? " · " + esc(r.key_value) : ""}</div>
    <p>${esc(ruleReq(r))}</p></article>`;
}

function auditRecordHtml(e) {
  const r = e.rule;
  return `<dl class="audit-metadata">
      <dt>${esc(t().citation)}</dt><dd>${esc(r.citation)}</dd>
      <dt>${esc(t().source)}</dt><dd>${esc(r.source_doc_id || "")} · <a href="${esc(r.source_url)}" target="_blank" rel="noopener">${esc(r.source_url)}</a></dd>
      <dt>${esc(t().retrieved)}</dt><dd>${esc(r.retrieved_at || "-")}</dd>
      <dt>${esc(t().asOfL)}</dt><dd>${esc(S.asOf)}</dd>
      <dt>${esc(t().effective)}</dt><dd>${esc(r.effective_date || "-")}</dd>
      <dt>${esc(t().confidence)}</dt><dd>${esc(fmtConf(e.conf ?? r.confidence ?? 0.7))}</dd>
      ${(r.corroborating_doc_ids || []).length ? `<dt>${esc(t().also)}</dt><dd>${esc(r.corroborating_doc_ids.join(", "))}</dd>` : ""}
      ${r.conflict_note ? `<dt>${esc(t().conflictNote)}</dt><dd>${esc(r.conflict_note)}</dd>` : ""}
    </dl>
    <p class="drawer-label">${esc(t().quote)}</p><blockquote>${esc(flat(r.quoted_span))}</blockquote>
    <p class="drawer-label">${esc(t().reasoning)}</p><p class="drawer-reasoning">${esc(e.why || r.requirement)}</p>
    <div class="bound">${esc(t().boundary)}</div>`;
}

function renderAuditPanel(ruleId) {
  const rule = S.data.rulesById[ruleId];
  if (!rule) return;
  const entry = S.addr && entriesFor(S.addr, S.asOf).find((item) => item.rid === ruleId);
  const status = entry?.result || (rule.status === "failed" ? "failed" : rule.status === "pending" ? "pending" : rule.status === "not_yet_effective" ? "not_yet_effective" : "unknown");
  const record = entry || { rule, why: rule.requirement, conf: rule.confidence };
  const panel = $("#audit-panel");
  panel.innerHTML = `<div class="drawer-top">
      <div><p class="eyebrow">${esc(t().auditEyebrow)} · ${esc(rule.source_doc_id || "")}</p><h2>${esc(ruleTitle(rule))}</h2></div>
      <button class="drawer-close" data-audit-close aria-label="${esc(t().closeAudit)}" title="${esc(t().closeAudit)}">×</button>
    </div>
    <div class="drawer-status"><span class="badge b-${status}">${esc(t().res[status] || status)}</span><span>${esc(rule.jurisdiction)} · ${esc(rule.citation)}</span></div>
    <p class="drawer-requirement">${esc(ruleReq(rule))}</p>
    ${auditRecordHtml(record)}`;
  panel.setAttribute("aria-label", t().audit);
  panel.setAttribute("aria-hidden", "false");
  panel.inert = false;
  panel.classList.add("open");
  $("#audit-scrim").hidden = false;
  document.body.classList.add("audit-open");
  $(".drawer-close", panel).focus();
}

function closeAudit() {
  const panel = $("#audit-panel");
  panel.classList.remove("open");
  panel.setAttribute("aria-hidden", "true");
  panel.inert = true;
  $("#audit-scrim").hidden = true;
  document.body.classList.remove("audit-open");
  S.auditId = null;
}

function exportVisible(format) {
  const address = S.data.addrById[S.addr];
  const rows = entriesFor(S.addr, S.asOf).filter((e) => (!S.level || S.level === "address" || levelOf(e) === S.level)
    && (!S.jurisdiction || e.rule.jurisdiction === S.jurisdiction)).map((e) => ({
    address_id: address.id, address: address.street, as_of: S.asOf, result: e.result, explanation: e.why,
    ...e.rule,
  }));
  const columns = ["address_id", "address", "as_of", "team_rule_id", "jurisdiction", "level", "category", "result", "title", "citation", "source_doc_id", "source_url", "requirement", "quoted_span", "retrieved_at", "effective_date", "conflict_flag"];
  const csvValue = (value) => `"${String(value ?? "").replace(/"/g, '""')}"`;
  const content = format === "csv"
    ? [columns.join(","), ...rows.map((row) => columns.map((key) => csvValue(row[key])).join(","))].join("\r\n")
    : JSON.stringify({ address_id: address.id, address: address.street, as_of: S.asOf, rules: rows }, null, 2);
  const blob = new Blob([content], { type: format === "csv" ? "text/csv;charset=utf-8" : "application/json;charset=utf-8" });
  const link = document.createElement("a");
  const fileUrl = URL.createObjectURL(blob);
  link.href = fileUrl;
  link.download = `${address.id}-${S.asOf}-rules.${format}`;
  link.click();
  setTimeout(() => URL.revokeObjectURL(fileUrl), 1000);
}

function selectedLayerHtml(level, entries, address) {
  if (!level) return "";
  if (level === "address") return `<section class="layer-inspector">
    <p class="eyebrow">${esc(t().layerAddress)}</p><h3>${esc(address.street)}</h3>
    <p>${esc(address.legal_city || address.postal_city)} · ${esc(t().addressDetails)}</p></section>`;
  const matching = entries.filter((e) => levelOf(e) === level).sort((a, b) => {
    const rank = { applies: 0, not_yet_effective: 1, pending: 2, unknown: 3, superseded: 4 };
    return rank[a.result] - rank[b.result];
  });
  const entry = matching[0];
  if (!entry) return `<section class="layer-inspector"><p class="eyebrow">${esc(t().layerDetails)}</p><p>${esc(t().emptyLayer)}</p></section>`;
  return `<section class="layer-inspector">
    <p class="eyebrow">${esc(t().layerDetails)} · ${esc(t()[level])}</p>
    <div class="layer-rule-head"><h3>${esc(ruleTitle(entry.rule))}</h3><span class="badge b-${entry.result}">${esc(t().res[entry.result])}</span></div>
    <p class="layer-cite">${esc(entry.rule.jurisdiction)} · ${esc(entry.rule.citation)}</p>
    <p>${esc(ruleReq(entry.rule))}</p>
    <button class="audit-trigger" data-audit="${esc(entry.rid)}">${esc(t().openAudit)}</button></section>`;
}

function stackHtml(counts, entries, address) {
  const layers = [["address", 0, t().addressBase], ["state", 40, t().state], ["county", 80, t().county], ["city", 120, t().city], ["future", 160, t().future]];
  const dom = (c) => ["unknown", "applies", "superseded", "not_yet_effective", "pending"].find((k) => c[k]);
  const slabs = layers.map(([k, z]) => {
    const c = counts[k] || {}, n = k === "address" ? 1 : Object.values(c).reduce((a, b) => a + b, 0), d = dom(c);
    const color = k === "address" ? "#d6ef73" : d ? COLORS[d] : "var(--border)";
    return `<button type="button" class="slab ${n ? "" : "empty"} ${k === "future" ? "future" : ""} ${c.unknown ? "hatch" : ""} ${S.level === k ? "on" : ""}" data-level="${k}" style="--z:${z}px;--c:${color}" title="${esc(t()[k] || k)}" aria-label="${esc(t()[k] || k)} layer, ${n} rules" aria-pressed="${S.level === k}"></button>`;
  }).join("");
  const names = layers.map(([k, z, label], index) => {
    const c = counts[k] || {}, n = Object.values(c).reduce((a, b) => a + b, 0);
    const sub = k === "address" ? (address.legal_city || address.postal_city) : k === "county" ? t().nocounty : n ? Object.entries(c).map(([r, v]) => `${v} ${t().res[r].toLowerCase()}`).join(", ") : "-";
    return `<button type="button" class="layer-label" data-level="${k}" style="top:${47 + (layers.length - 1 - index) * 31}px" aria-pressed="${S.level === k}"><b>${esc(label)}</b><span>${esc(sub)}</span></button>`;
  }).join("");
  return `<div class="stackwrap"><h2 style="margin-bottom:0">${esc(t().layers)}</h2>
    <div class="stack"><div class="plane">${slabs}</div><div class="slabnames">${names}</div></div>
    <div class="hint">${esc(t().stackhint)}</div>${selectedLayerHtml(S.level, entries, address)}</div>`;
}

/* ------------------------------------------------------------------ rendering: tests + how */
function renderChanges() {
  const d = S.data, root = $("#view-changes");
  const cards = d.tests.map((tt) => {
    const c = d.changes[tt.test_id] || { affected_address_ids: [], conflict_flag_address_ids: [], notes: "" };
    const rep = d.test_report[tt.test_id] || { pass: false, checks: [] };
    const cities = {};
    c.affected_address_ids.forEach((id) => { const k = d.addrById[id].legal_city || "-"; cities[k] = (cities[k] || 0) + 1; });
    const max = Math.max(1, ...Object.values(cities));
    const date = tt.as_of_after || tt.as_of;
    return `<article class="card test"><h3><span class="tid">${esc(tt.test_id)}</span> ${esc(tt.title)}
        <span class="badge ${rep.pass ? "b-applies" : "b-unknown"}">${esc(rep.pass ? t().pass : t().fail)}</span></h3>
      <p class="muted" style="margin:2px 0 8px">${esc(tt.expected_behavior)}</p>
      <strong>${c.affected_address_ids.length}</strong> ${esc(t().affected)}${c.conflict_flag_address_ids.length ? ` · <strong>${c.conflict_flag_address_ids.length}</strong> ${esc(t().conflicts)}` : ""}
      ${Object.entries(cities).sort().map(([k, v]) => `<div class="bar"><span class="l">${esc(k)}</span><i style="width:${Math.round((v / max) * 160)}px"></i> ${v}</div>`).join("")}
      <ul class="checks">${rep.checks.map((k) => `<li class="${k.ok ? "" : "bad"}">${esc(k.what)}</li>`).join("")}</ul>
      <details><summary class="muted" style="cursor:pointer;margin-top:8px">${esc(t().showAddr)}</summary>
        <div class="addrlist">${c.affected_address_ids.slice(0, 400).map((id) => `<button class="chip" data-addr="${id}" data-date="${date}" data-go="1">${id}</button>`).join("")}</div></details>
    </article>`;
  }).join("");
  root.innerHTML = `<h2 style="margin:0 0 12px">${esc(t().tchanges)} <span class="muted" style="font-weight:400;font-size:14px">· ${esc(S.data.meta.as_of)}</span></h2><div class="tests">${cards}</div>`;
}
function renderHow() {
  const m = S.data.meta;
  $("#view-how").innerHTML = `<div class="card how"><h2>${esc(t().how)}</h2>
    <ol>
      <li><b>Extract.</b> An AI model reads each public law document and writes one structured rule record (category, jurisdiction, requirement, coverage, exemptions, dates, citation). A rule is kept only if its quoted text is found verbatim in the source.</li>
      <li><b>Resolve.</b> The US Census Geocoder turns each address into its legal city and county. The mailing city is not trusted.</li>
      <li><b>Apply.</b> Plain code (not the AI) tests each rule's coverage against the building facts. Missing facts give <i>Unknown</i>, never a guess. A cutoff year equal to the building's year also gives <i>Unknown</i>.</li>
      <li><b>Explain.</b> Every answer shows the rule, citation, quoted source text, retrieval date, as-of date and the facts used.</li>
      <li><b>Track.</b> Change an as-of date to see enacted, not-yet-effective, pending and failed laws separated. Five supplied tests are checked on the <i>Change tests</i> tab.</li>
    </ol>
    <p class="muted">${m.n_rules} rules · ${m.n_addresses} sample addresses · generated ${esc(m.generated)}</p>
    <p class="dl"><b>${esc(t().dl)}:</b> <a href="data/rules.json" download>rules.json</a><a href="data/lookups.json" download>lookups.json</a><a href="data/changes.json" download>changes.json</a></p>
    <details><summary class="muted">Audit log (last entries)</summary><pre>${esc(m.audit_tail.join("\n"))}</pre></details>
  </div>`;
}

/* ------------------------------------------------------------------ events */
function setTab(tab) {
  S.tab = tab;
  document.querySelectorAll(".tab").forEach((b) => {
    const selected = b.dataset.tab === tab;
    b.classList.toggle("on", selected);
    b.setAttribute("aria-selected", String(selected));
  });
  ["lookup", "changes", "how"].forEach((k) => ($("#view-" + k).hidden = k !== tab));
  if (tab === "changes") renderChanges(); if (tab === "how") renderHow();
}
function openAudit(ruleId) {
  S.auditId = ruleId;
  renderAuditPanel(ruleId);
}
function setAddr(id, date) {
  closeAudit();
  S.addr = id; S.level = null; S.jurisdiction = ""; if (date) S.asOf = date;
  const a = S.data.addrById[id]; $("#q").value = a ? `${a.street}, ${a.legal_city || a.postal_city}` : "";
  renderDateChips(); renderResult();
}
function suggest(q) {
  const ul = $("#suggest"); q = q.trim().toLowerCase();
  if (!q) { ul.hidden = true; return; }
  const hits = S.data.addresses.filter((a) => `${a.street} ${a.postal_city} ${a.legal_city || ""} ${a.id}`.toLowerCase().includes(q)).slice(0, 8);
  ul.innerHTML = hits.map((a) => `<li data-addr="${a.id}"><span>${esc(a.street)}</span><small>${esc(a.legal_city || a.postal_city)} · ${a.id}</small></li>`).join("");
  ul.hidden = !hits.length;
}
document.addEventListener("click", (ev) => {
  const el = ev.target.closest("[data-addr],[data-date],[data-level],[data-audit],[data-audit-close],[data-export],.tab");
  if (!el) { $("#suggest").hidden = true; return; }
  if (el.hasAttribute("data-audit-close")) { closeAudit(); return; }
  if (el.dataset.audit) { openAudit(el.dataset.audit); return; }
  if (el.dataset.export) { exportVisible(el.dataset.export); return; }
  if (el.classList.contains("tab")) { setTab(el.dataset.tab); return; }
  if (el.dataset.addr) { $("#suggest").hidden = true; if (el.dataset.go) setTab("lookup"); setAddr(el.dataset.addr, el.dataset.date); return; }
  if (el.dataset.date) { S.asOf = el.dataset.date; renderDateChips(); renderResult(); return; }
  if (el.dataset.level !== undefined) {
    S.level = S.level === el.dataset.level || !el.dataset.level ? null : el.dataset.level;
    if (!el.dataset.level) S.jurisdiction = "";
    renderResult();
    if (S.level && S.level !== "address") {
      const rank = { applies: 0, not_yet_effective: 1, pending: 2, unknown: 3, superseded: 4 };
      const entry = entriesFor(S.addr, S.asOf).filter((item) => levelOf(item) === S.level)
        .sort((a, b) => rank[a.result] - rank[b.result])[0];
      if (entry) openAudit(entry.rid); else closeAudit();
    } else closeAudit();
  }
});
document.addEventListener("change", (ev) => {
  if (ev.target.id === "jurisdiction-filter") { S.jurisdiction = ev.target.value; renderResult(); }
});
$("#audit-scrim").addEventListener("click", closeAudit);
document.addEventListener("keydown", (ev) => { if (ev.key === "Escape" && S.auditId) closeAudit(); });
$("#q").addEventListener("input", (e) => suggest(e.target.value));
$("#q").addEventListener("focus", (e) => suggest(e.target.value));
$("#asof").addEventListener("change", (e) => { if (e.target.value) { S.asOf = e.target.value; renderDateChips(); renderResult(); } });

(async function init() {
  try {
    const r = await fetch("data/app_data.json"); S.data = await r.json();
  } catch (e) {
    $("#result").innerHTML = `<div class="card empty-note">Could not load data/app_data.json. If you opened index.html directly from disk, serve the folder instead: <code>python -m http.server 8000 --directory web</code></div>`;
    return;
  }
  prep(); S.asOf = S.data.meta.as_of; renderStatic();
  const ex = S.data.addresses.find((a) => a.legal_city === "Hoboken, NJ") || S.data.addresses[0];
  setAddr(ex.id);
})();
