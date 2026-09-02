const palette = ["#1f9d67", "#2563eb", "#c9831b", "#e65c4f", "#7c5ce4", "#0f9aa8", "#d16b9a", "#64748b"];

class APIError extends Error {
  constructor(message, status = 0) { super(message); this.status = status; this.name = "APIError"; }
}

class AashanAPI {
  constructor() { this.base = window.location.origin; }

  async request(path, options = {}) {
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), options.timeout ?? 15000);
    try {
      const response = await fetch(this.base + path, { ...options, signal: controller.signal });
      const text = await response.text();
      let body = {};
      try { body = text ? JSON.parse(text) : {}; } catch { body = { detail: text }; }
      if (!response.ok) {
        const detail = typeof body.detail === "string" ? body.detail : body.detail?.message || body.message;
        throw new APIError(detail || `Request failed (${response.status})`, response.status);
      }
      return body;
    } catch (error) {
      if (error.name === "AbortError") throw new APIError("The request timed out. Check that the Aashan API is reachable.");
      if (error instanceof APIError) throw error;
      throw new APIError("Aashan API is unavailable. Start FastAPI, then refresh this page.");
    } finally { window.clearTimeout(timeout); }
  }

  get(path) { return this.request(path); }
  post(path, body) { return this.request(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body ?? {}) }); }
  upload(path, file) { const form = new FormData(); form.append("file", file, file.name); return this.request(path, { method: "POST", body: form, timeout: 30000 }); }
  health() { return this.get("/health"); }
  summary() { return this.get("/api/dashboard/summary"); }
  categories() { return this.get("/api/dashboard/categories"); }
  monthly() { return this.get("/api/dashboard/monthly"); }
  patterns() { return this.get("/api/dashboard/patterns"); }
  anomalies() { return this.get("/api/dashboard/anomalies"); }
  privacy() { return this.get("/api/dashboard/privacy"); }
  budgets() { return this.get("/api/budgets"); }
  budgetStatus() { return this.get("/api/budgets/status"); }
  saveBudgets(budgets) { return this.post("/api/budgets", { budgets }); }
  queryInsight(question) { return this.post("/api/insights/query", { question }); }
  demoRun() { return this.post("/api/demo/run"); }
  ingestCSV(file) { return this.upload("/api/ingest/csv", file); }
  createConsent(payload) { return this.post("/api/aa/consent", payload); }
  createMockConsent(payload) { return this.post("/api/aa/mock/consent", payload); }
  consentStatus(id) { return this.get(`/api/aa/consent/${encodeURIComponent(id)}`); }
  approveMockConsent(id) { return this.post(`/api/aa/mock/approve?consent_id=${encodeURIComponent(id)}`); }
  fetchMockData(id) { return this.post(`/api/aa/mock/fetch?consent_id=${encodeURIComponent(id)}`); }
  createSession(id) { return this.post(`/api/aa/consent/${encodeURIComponent(id)}/session`, { format: "json" }); }
}

const api = new AashanAPI();
const state = {
  active: window.location.hash.slice(1) || "overview",
  loading: true,
  data: {},
  errors: [],
  toast: "",
  modal: null,
  consent: null,
  insightAnswer: "",
};

const viewMeta = {
  overview: ["Overview", "A calm read of your financial picture, built from aggregate data."],
  transactions: ["Transactions", "Understand your processed activity without retaining raw banking descriptions."],
  accounts: ["Accounts", "Connect a provider or import a statement with privacy controls in view."],
  budgets: ["Budgets", "Set category limits and keep month-to-date spending visible."],
  insights: ["Insights", "Spending patterns and explainable observations from Aashan’s pipeline."],
  goals: ["Goals", "A place for savings targets when the goals API is enabled."],
  privacy: ["Privacy", "See what Aashan retains, what it forgets, and how consent moves."],
  settings: ["Settings", "Product preferences and account controls as backend capabilities arrive."],
};
const navItems = [
  ["overview", "⌂", "Overview"], ["transactions", "≡", "Transactions"], ["accounts", "◉", "Accounts"], ["budgets", "▤", "Budgets"],
  ["insights", "✦", "Insights"], ["goals", "○", "Goals"], ["privacy", "◇", "Privacy"], ["settings", "⚙", "Settings"],
];

const html = (value) => String(value ?? "").replace(/[&<>'"]/g, (character) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" }[character]));
const number = (value) => Number(value || 0);
const money = (value) => `₹${Math.round(number(value)).toLocaleString("en-IN")}`;
const moneyExact = (value) => `₹${number(value).toLocaleString("en-IN", { maximumFractionDigits: 2 })}`;
const titleCase = (value) => String(value || "").replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
const dateLabel = (value) => { const date = new Date(value); return Number.isNaN(date.getTime()) ? String(value || "—") : date.toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" }); };
const monthLabel = (value) => { const date = new Date(`${value}-01T00:00:00`); return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleDateString("en-IN", { month: "short", year: "numeric" }); };
const tone = (value) => value === "good" || value === "synced" || value === "active" ? "good" : value === "warn" || value === "pending" ? "warn" : value === "danger" || value === "failed" ? "danger" : "info";
const pill = (label, kind = "neutral") => `<span class="pill ${kind}">${html(label)}</span>`;
const button = (label, action, kind = "primary", extra = "") => `<button type="button" class="button ${kind} ${extra}" data-action="${html(action)}">${html(label)}</button>`;
const card = (title, subtitle, body, extra = "") => `<section class="card ${extra}"><div class="card-header"><div><h2 class="card-title">${html(title)}</h2>${subtitle ? `<p class="card-subtitle">${html(subtitle)}</p>` : ""}</div></div>${body}</section>`;
const notice = (text, kind = "info") => `<div class="notice ${kind}"><span class="notice-icon">${kind === "good" ? "✓" : kind === "warn" ? "!" : kind === "danger" ? "×" : "i"}</span><span>${html(text)}</span></div>`;
const empty = (icon, title, body, action = "") => `<div class="empty"><div class="empty-icon" aria-hidden="true">${icon}</div><div class="empty-title">${html(title)}</div><div class="empty-body">${html(body)}</div>${action}</div>`;
const loading = (message = "Loading your financial picture…") => `<div class="loading"><div class="spinner" aria-hidden="true"></div><span>${html(message)}</span></div>`;

function metric(label, value, detail, accent = "var(--success)") {
  return `<div class="card metric" style="--accent:${accent}"><div class="metric-label">${html(label)}</div><div class="metric-value">${html(value)}</div><div class="metric-detail">${html(detail)}</div></div>`;
}

function categoryEntries(data) { return Object.entries(data?.categories || {}).sort((a, b) => number(b[1]) - number(a[1])); }
function categoryDonut(payload) {
  const entries = categoryEntries(payload);
  if (!entries.length) return empty("◌", "No spending mix yet", "Import a statement or connect an account to see category aggregates.");
  const total = entries.reduce((sum, [, value]) => sum + number(value), 0);
  let cursor = 0;
  const stops = entries.map(([name, value], index) => { const next = cursor + number(value) / total * 100; const stop = `${palette[index % palette.length]} ${cursor.toFixed(2)}% ${next.toFixed(2)}%`; cursor = next; return stop; }).join(", ");
  return `<div class="donut-wrap"><div class="donut" style="--donut:conic-gradient(${stops})" role="img" aria-label="Spending by category"><div class="donut-label"><strong>${money(total)}</strong><span>spending</span></div></div><div class="legend">${entries.slice(0, 6).map(([name, value], index) => `<div class="legend-row"><i class="legend-dot" style="background:${palette[index % palette.length]}"></i><span class="legend-name">${html(name)}</span><span class="legend-value">${Math.round(number(value) / total * 100)}%</span></div>`).join("")}${entries.length > 6 ? `<div class="legend-row"><span class="legend-name">+${entries.length - 6} more</span></div>` : ""}</div></div>`;
}

function monthlyBars(monthly) {
  const entries = Object.entries(monthly || {});
  if (!entries.length) return empty("▥", "No monthly trend yet", "Monthly spending will appear after Aashan processes financial data.");
  const max = Math.max(...entries.map(([, value]) => number(value)), 1);
  return `<div class="bars" role="img" aria-label="Monthly spending bar chart">${entries.slice(-8).map(([month, value]) => `<div class="bar-item"><span class="bar-value">${money(value)}</span><div class="bar" style="height:${Math.max(3, number(value) / max * 165)}px" title="${html(monthLabel(month))}: ${money(value)}"></div><span class="bar-label">${html(monthLabel(month))}</span></div>`).join("")}</div>`;
}

function signals(data) {
  const summary = data.summary || {}, categories = data.categories || {}, monthly = data.monthly?.monthly || {}, patterns = data.patterns || {}, anomalies = data.anomalies?.anomalies || [];
  const entries = categoryEntries(categories);
  const top = entries[0];
  const months = Object.entries(monthly);
  const lead = patterns.weekend_vs_weekday?.weekend > patterns.weekend_vs_weekday?.weekday ? "weekends" : "weekdays";
  const items = [];
  if (top) items.push(["Top category", `${top[0]} is your largest spending category at ${money(top[1])}.`, "↗"]);
  if (months.length) items.push(["Monthly rhythm", `${monthLabel(months.at(-1)[0])} recorded ${money(months.at(-1)[1])} in debit spending.`, "◷"]);
  if (patterns.weekend_vs_weekday) items.push(["Spending pattern", `Your recorded spending is higher on ${lead}.`, "⌁"]);
  items.push(["Anomaly radar", anomalies.length ? `${anomalies.length} unusual spending event${anomalies.length === 1 ? "" : "s"} need a closer look.` : "No unusual spending detected in the current aggregate window.", anomalies.length ? "!" : "✓"]);
  if (summary.transaction_count) items.push(["Privacy boundary", `${summary.transaction_count} records were processed; individual descriptions are not retained.`, "◇"]);
  return `<div class="signal-list">${items.slice(0, 5).map(([title, copy, mark]) => `<div class="signal"><div class="signal-mark">${mark}</div><div><div class="signal-title">${html(title)}</div><div class="signal-copy">${html(copy)}</div></div></div>`).join("")}</div>`;
}

function errorBanner() { return state.errors.length ? notice(`${state.errors.length} data source${state.errors.length === 1 ? "" : "s"} could not be loaded. The available sections remain visible.`, "warn") : ""; }

function overviewView() {
  const d = state.data, s = d.summary || {}, p = d.patterns || {}, categories = d.categories || {}, monthly = d.monthly || {};
  if (state.loading) return loading();
  const hasData = number(s.transaction_count) > 0 || categoryEntries(categories).length;
  const demo = d.health?.mock_mode;
  return `<div class="stack">${errorBanner()}${!hasData ? notice("Your Aashan workspace is ready. Connect an account or import a CSV to create your first privacy-preserving financial snapshot.", "info") : ""}<div class="metrics">${metric("Total spending", money(s.total_spending), "Debit transactions only", "var(--success)")}${metric("Total income", money(s.total_credit), "Credits kept separate", "var(--blue)")}${metric("Net cash flow", money(s.net_cash_flow), s.net_cash_flow >= 0 ? "Positive cash movement" : "Spending is ahead of income", s.net_cash_flow >= 0 ? "var(--success)" : "var(--danger)")}${metric("Records processed", String(s.transaction_count || 0), s.month ? `Latest window · ${monthLabel(s.month)}` : "Aggregate records", "var(--warning)")}</div><div class="grid-2">${card("Where your money went", "Category mix · debit transactions only", categoryDonut(categories))}${card("Monthly rhythm", "Processed spending over time", monthlyBars(monthly.monthly))}</div><div class="grid-2">${card("Financial signals", "Small, explainable observations from the current snapshot", signals(d))}${card("Privacy at a glance", "Aashan keeps intelligence, not raw banking history", `<div class="kv-list"><div class="kv"><span>Raw transactions retained</span><strong>${pill("No", "good")}</strong></div><div class="kv"><span>Aggregate snapshot</span><strong>${pill(d.privacy?.aggregate_data_persisted ? "Available" : "Not yet", d.privacy?.aggregate_data_persisted ? "good" : "neutral")}</strong></div><div class="kv"><span>Latest sync</span><strong>${html(s.month ? monthLabel(s.month) : "Not connected")}</strong></div></div><div class="button-row" style="margin-top:14px">${button("Review privacy", "navigate:privacy", "secondary")}${demo ? button("Run demo data", "demo-run", "soft") : ""}</div>`)} </div></div>`;
}

function transactionsView() {
  const s = state.data.summary || {}, categories = state.data.categories || {}, anomalies = state.data.anomalies?.anomalies || [];
  const entries = categoryEntries(categories);
  return `<div class="stack">${errorBanner()}${notice("Aashan intentionally forgets raw transaction descriptions after normalization, categorization, and aggregation. This view therefore shows privacy-safe intelligence rather than a fabricated transaction ledger.", "good")}<div class="grid-2">${card("Processed activity", "What the current aggregate snapshot can safely show", `<div class="split"><div class="split-item"><span>Debit records</span><strong>${money(s.total_debit)}</strong></div><div class="split-item"><span>Credit records</span><strong>${money(s.total_credit)}</strong></div></div><div class="table-note" style="margin-top:12px">${html(s.transaction_count || 0)} records were processed. Raw dates, narrations, account identifiers, and row-level details are not returned by the backend.</div>`)}${card("Search and filters", "Available when a privacy-safe transaction index exists", empty("⌕", "Row-level search is unavailable", "The current API exposes aggregate-only data. A future privacy-reviewed index can add category/date filters without retaining raw descriptions."))}</div>${card("Category ledger", "Aggregated debit totals · no individual narrations", entries.length ? `<div class="signal-list">${entries.map(([name, value], index) => `<div class="signal"><i class="legend-dot" style="background:${palette[index % palette.length]}"></i><div style="flex:1"><div class="progress-top"><strong>${html(name)}</strong><span>${money(value)}</span></div><div class="track"><div class="fill" style="width:${Math.min(100, number(categories.percentages?.[name] || 0))}%"></div></div></div></div>`).join("")}</div>` : empty("◌", "No category aggregates", "Connect an account or import a CSV to begin."))}${card("Alerts linked to activity", "Anomalies are returned without raw transaction descriptions", anomalies.length ? `<div class="alert-list">${anomalies.map((item) => `<div class="alert"><div class="alert-top">${pill("Review", "danger")}<span class="alert-title">${html(item.category || "Spending")}</span><span class="alert-amount">${moneyExact(item.amount)}</span></div><div class="alert-copy">${html(item.reason || "An amount sits outside the normal spending range.")}</div></div>`).join("")}</div>` : notice("No unusual spending detected in the current aggregate window.", "good"))}</div>`;
}

function consentStatusLabel(consent) {
  if (!consent) return ["Not connected", "neutral"];
  const raw = consent.setu_status || consent.status || "PENDING";
  const value = String(raw).toUpperCase();
  if (["ACTIVE", "APPROVED", "SYNCED", "COMPLETED"].includes(value)) return [value === "ACTIVE" ? "Consent approved" : titleCase(value), "good"];
  if (["REJECTED", "EXPIRED", "FAILED"].includes(value)) return [titleCase(value), "danger"];
  return [titleCase(value), "warn"];
}

function consentPanel() {
  const consent = state.consent, health = state.data.health || {}, [label, kind] = consentStatusLabel(consent);
  if (!consent) return `<div class="stack">${notice(health.mock_mode ? "Local development is in mock mode. The demo path is clearly labeled and never represents a real bank connection." : "Setu credentials remain on the FastAPI server. This browser only receives consent status and a provider URL.", health.mock_mode ? "warn" : "info")}<div class="privacy-flow"><div class="privacy-step current"><strong>01</strong><span>Connect account</span></div><div class="privacy-step"><strong>02</strong><span>Approve consent</span></div><div class="privacy-step"><strong>03</strong><span>Fetch session</span></div><div class="privacy-step"><strong>04</strong><span>Process data</span></div><div class="privacy-step"><strong>05</strong><span>Forget rows</span></div></div><div class="button-row">${button("Connect account", "open-consent", "primary")}${button("Import CSV", "open-import", "secondary")}</div></div>`;
  const mock = consent.mode === "mock";
  const status = String(consent.setu_status || consent.status || "PENDING").toUpperCase();
  let actions = "";
  if (mock && status === "PENDING") actions = button("Approve demo consent", "approve-mock", "primary");
  if (mock && status === "ACTIVE") actions = button("Fetch demo data", "fetch-mock", "primary");
  if (!mock && consent.url) actions += `<a class="button primary" href="${html(consent.url)}" target="_blank" rel="noopener">Open Setu consent</a>`;
  if (!mock && consent.consent_id) actions += button("Refresh status", "refresh-consent", "secondary");
  if (!mock && (status === "ACTIVE" || status === "APPROVED")) actions += button("Create data session", "create-session", "soft");
  if (consent.session_id) actions += button("Refresh dashboard", "refresh", "secondary");
  return `<div class="stack">${consent.error ? notice(consent.error, "danger") : ""}${notice(mock ? "MOCK / DEMO DATA — no real institution is connected." : "Setu credentials and raw FI payloads stay server-side. The browser sees only consent lifecycle metadata.", mock ? "warn" : "good")}<div class="privacy-flow"><div class="privacy-step done"><strong>01</strong><span>Consent created</span></div><div class="privacy-step ${status === "PENDING" ? "current" : "done"}"><strong>02</strong><span>${html(label)}</span></div><div class="privacy-step ${consent.session_id ? "done" : "current"}"><strong>03</strong><span>${consent.session_id ? "Session created" : "Data session"}</span></div><div class="privacy-step ${consent.processed ? "done" : "current"}"><strong>04</strong><span>${consent.processed ? "Processed" : "Awaiting data"}</span></div><div class="privacy-step ${consent.processed ? "done" : "current"}"><strong>05</strong><span>Raw rows forgotten</span></div></div>${card("Connection lifecycle", "Aashan makes each handoff visible", `<div class="kv-list"><div class="kv"><span>Provider</span><strong>${html(mock ? "Mock AA provider" : "Setu Account Aggregator")}</strong></div><div class="kv"><span>Consent status</span><strong>${pill(label, kind)}</strong></div><div class="kv"><span>Consent ID</span><strong>${html(consent.consent_id || consent.id || "—")}</strong></div><div class="kv"><span>Data session</span><strong>${html(consent.session_id || "Not created")}</strong></div><div class="kv"><span>Processing</span><strong>${html(consent.processed ? "Completed · raw rows discarded" : "Waiting for provider notification")}</strong></div></div><div class="button-row" style="margin-top:14px">${actions}</div>`)}</div>`;
}

function accountsView() {
  return `<div class="stack">${errorBanner()}${card("Connect an account", "Real provider lifecycle with server-side credentials", consentPanel())}<div class="grid-2">${card("Connected institutions", "Account inventory is not exposed by the current backend", empty("◉", "No account list available", "Aashan can show consent and processing status today. Institution names, balances, and account types need a privacy-reviewed accounts API before they can be displayed."))}${card("Import a statement", "CSV rows are processed, aggregated, and forgotten", `<div class="table-note">Accepted fields include date, description, amount, mode, and transaction type. The file is sent directly to FastAPI; raw rows are not stored by the dashboard.</div><div style="margin-top:14px">${button("Choose CSV file", "open-import", "secondary")}</div><input id="csv-file" class="sr-only" type="file" accept=".csv,text/csv" />`)}</div></div>`;
}

function budgetsView() {
  const statuses = state.data.budgetStatus?.status || [], configured = state.data.budgets?.budgets || {};
  const rows = statuses.length ? statuses.map((item) => { const used = number(item.percentage_used), statusTone = item.over_budget ? "danger" : used >= 80 ? "warn" : "good"; return `<div class="budget-row"><strong>${html(item.category)}</strong><span class="budget-num">Spent<br><b>${money(item.spent)}</b></span><span class="budget-num">Budget<br><b>${money(item.budget)}</b></span><span class="budget-percent">${Math.round(used)}%</span><div class="budget-progress"><div class="track"><div class="fill ${statusTone === "danger" ? "danger" : statusTone === "warn" ? "warn" : ""}" style="width:${Math.min(100, used)}%"></div></div><span class="progress-meta">${item.over_budget ? `${money(Math.abs(number(item.remaining)))} over` : `${money(item.remaining)} remaining`}</span></div></div>`; }).join("") : empty("▤", "No category budgets yet", "Set your first limit below. Budget status will use the aggregate spending API.");
  const existing = Object.keys(configured).map((category) => `<div class="field"><label for="budget-${html(category)}">${html(category)}</label><input id="budget-${html(category)}" data-budget-category="${html(category)}" type="number" min="0" step="100" value="${number(configured[category])}" /></div>`).join("");
  return `<div class="stack">${errorBanner()}${card("Budget health", "Spending against the limits you configure", rows)}${card("Configure category budgets", "Saving replaces the current category budget set", `<form id="budget-form"><div class="form-grid">${existing || `<div class="field full"><span class="field-help">No categories configured yet. Add one below.</span></div>`}</div><div class="budget-add"><input id="new-budget-category" placeholder="Category, e.g. Food" aria-label="New budget category" /><input id="new-budget-amount" type="number" min="0" step="100" placeholder="Amount in ₹" aria-label="New budget amount" />${button("Add limit", "add-budget", "secondary")}</div><div class="button-row" style="margin-top:14px">${button("Save budgets", "save-budgets", "primary")}</div></form>`)}</div>`;
}

function insightCards() {
  const d = state.data, s = d.summary || {}, categories = d.categories || {}, monthly = d.monthly?.monthly || {}, anomalies = d.anomalies?.anomalies || [], budgetRows = d.budgetStatus?.status || [], entries = categoryEntries(categories), months = Object.entries(monthly);
  const items = [];
  if (entries[0]) items.push(["TOP CATEGORY", `${entries[0][0]} accounts for ${money(entries[0][1])} of spending.`, "good"]);
  if (months.length) { const peak = months.reduce((a, b) => number(a[1]) > number(b[1]) ? a : b); items.push(["PEAK MONTH", `${monthLabel(peak[0])} was your highest-spending month at ${money(peak[1])}.`, "info"]); }
  items.push(["CASH FLOW", s.net_cash_flow >= 0 ? `Income exceeds spending by ${money(s.net_cash_flow)}.` : `Spending exceeds income by ${money(Math.abs(number(s.net_cash_flow))) }.`, s.net_cash_flow >= 0 ? "good" : "danger"]);
  items.push(["ANOMALY RADAR", anomalies.length ? `${anomalies.length} unusual spending event${anomalies.length === 1 ? "" : "s"} detected.` : "No unusual spending detected.", anomalies.length ? "warn" : "good"]);
  const over = budgetRows.filter((row) => row.over_budget).map((row) => row.category);
  items.push(["BUDGET WATCH", over.length ? `Over budget: ${over.join(", ")}.` : "All configured budgets are within limits.", over.length ? "warn" : "good"]);
  return `<div class="grid-2">${items.map(([label, text, kind]) => `<div class="card compact"><div class="eyebrow">${html(label)}</div><p style="margin:10px 0 0;font-size:14px;line-height:1.5;font-weight:700">${html(text)}</p><div style="margin-top:12px">${pill(kind === "danger" ? "Attention" : "Aggregate insight", kind)}</div></div>`).join("")}</div>`;
}

function insightsView() {
  return `<div class="stack">${errorBanner()}${state.loading ? loading() : insightCards()}${card("Ask about your spending", "Answers use aggregate JSON only; raw descriptions never enter this request", `<form id="insight-form"><div class="field"><label for="insight-question">Question</label><input id="insight-question" required maxlength="180" placeholder="What was my highest spending category?" value="" /></div><div class="button-row" style="margin-top:12px">${button("Ask Aashan", "ask-insight", "primary")}</div></form>${state.insightAnswer ? `<div class="notice good" style="margin-top:14px"><span class="notice-icon">✦</span><span>${html(state.insightAnswer)}</span></div>` : ""}`)}${card("How to read these insights", "Explainable by design", `<div class="kv-list"><div class="kv"><span>Source</span><strong>Processed aggregate snapshot</strong></div><div class="kv"><span>Model behavior</span><strong>Deterministic insight provider</strong></div><div class="kv"><span>Raw narration access</span><strong>${pill("Never", "good")}</strong></div></div>`)}</div>`;
}

function goalsView() { return `<div class="stack">${notice("Savings goals are intentionally not simulated. Aashan needs a goals persistence API before targets, contributions, or completion dates can be displayed.", "info")}${card("Savings goals", "Targets, progress, and contribution history", empty("○", "Goals API not enabled", "When a backend goals model is added, this surface is ready to render real progress without inventing balances."))}</div>`; }

function privacyView() {
  const p = state.data.privacy || {};
  return `<div class="stack">${errorBanner()}${notice("Goldfish Memory is a product boundary: raw inputs are temporary, while aggregate intelligence is persisted for the dashboard.", "good")}${card("Processing and forgetting", "The privacy contract behind every import and account sync", `<div class="privacy-flow"><div class="privacy-step done"><strong>01</strong><span>Raw input</span></div><div class="privacy-step done"><strong>02</strong><span>Normalize</span></div><div class="privacy-step done"><strong>03</strong><span>Categorize</span></div><div class="privacy-step done"><strong>04</strong><span>Aggregate</span></div><div class="privacy-step current"><strong>05</strong><span>Forget raw rows</span></div></div>`)}<div class="grid-2">${card("Current database status", "Live response from /api/dashboard/privacy", `<div class="kv-list"><div class="kv"><span>Raw transactions persisted</span><strong>${pill(p.raw_transactions_persisted ? "Yes · review" : "No", p.raw_transactions_persisted ? "danger" : "good")}</strong></div><div class="kv"><span>Raw records in memory</span><strong>${html(p.raw_transaction_count_in_memory ?? 0)}</strong></div><div class="kv"><span>Aggregate data persisted</span><strong>${pill(p.aggregate_data_persisted ? "Yes" : "Not yet", p.aggregate_data_persisted ? "good" : "neutral")}</strong></div><div class="kv"><span>Persisted tables</span><strong>${html((p.persisted_tables || []).join(", ") || "None")}</strong></div></div>`)}${card("What Aashan does not show", "Transparency about unavailable detail is part of privacy", `<div class="signal-list"><div class="signal"><div class="signal-mark">×</div><div><div class="signal-title">No raw descriptions</div><div class="signal-copy">Narrations and SMS text are not returned to the dashboard after processing.</div></div></div><div class="signal"><div class="signal-mark">×</div><div><div class="signal-title">No browser credentials</div><div class="signal-copy">Setu client secrets and tokens remain in backend environment configuration.</div></div></div><div class="signal"><div class="signal-mark">✓</div><div><div class="signal-title">Aggregate learning</div><div class="signal-copy">Categories, monthly totals, anomaly summaries, and budgets remain available.</div></div></div></div>`)}</div></div>`;
}

function settingsView() {
  const h = state.data.health || {};
  return `<div class="stack">${card("Workspace status", "Runtime information from the health endpoint", `<div class="kv-list"><div class="kv"><span>Application</span><strong>${html(h.app || "Aashan")}</strong></div><div class="kv"><span>Environment</span><strong>${html(h.environment || "Unknown")}</strong></div><div class="kv"><span>API status</span><strong>${pill(h.status === "ok" ? "Operational" : "Unavailable", h.status === "ok" ? "good" : "danger")}</strong></div><div class="kv"><span>Data mode</span><strong>${pill(h.mock_mode ? "Mock / demo" : "Setu sandbox", h.mock_mode ? "warn" : "info")}</strong></div></div>`)}${card("Profile and preferences", "Authentication, notifications, and account settings", empty("⚙", "Settings API not enabled", "No profile or notification endpoint exists in the current Aashan backend. This screen stays explicit instead of creating client-only account state."))}${card("Keep your connection safe", "Aashan security defaults", `<div class="signal-list"><div class="signal"><div class="signal-mark">✓</div><div><div class="signal-title">Secrets stay server-side</div><div class="signal-copy">The frontend never receives Setu client credentials or bearer tokens.</div></div></div><div class="signal"><div class="signal-mark">✓</div><div><div class="signal-title">No raw financial storage</div><div class="signal-copy">The browser only receives the aggregate API responses needed for the current view.</div></div></div></div>`)}</div>`;
}

function pageContent() {
  return state.active === "overview" ? overviewView() : state.active === "transactions" ? transactionsView() : state.active === "accounts" ? accountsView() : state.active === "budgets" ? budgetsView() : state.active === "insights" ? insightsView() : state.active === "goals" ? goalsView() : state.active === "privacy" ? privacyView() : settingsView();
}

function renderModal() {
  if (state.modal === "import") return `<div class="modal-backdrop" data-action="close-modal"><div class="modal" role="dialog" aria-modal="true" aria-labelledby="import-title" data-stop><div class="modal-header"><div><h2 id="import-title" class="modal-title">Import a CSV</h2><p class="card-subtitle">Process it through FastAPI; the raw file is not retained by Aashan.</p></div><button class="icon-button" data-action="close-modal" aria-label="Close">×</button></div><div class="table-note">Use columns such as date, description, amount, mode, and transaction_type. Credit rows remain separate from debit spending.</div><div style="margin-top:16px"><input id="modal-csv-file" type="file" accept=".csv,text/csv" aria-label="Choose CSV file" /></div><div class="button-row" style="margin-top:18px">${button("Process file", "process-csv", "primary")}${button("Cancel", "close-modal", "secondary")}</div></div></div>`;
  if (state.modal === "consent") { const demo = state.data.health?.mock_mode; return `<div class="modal-backdrop" data-action="close-modal"><div class="modal" role="dialog" aria-modal="true" aria-labelledby="consent-title" data-stop><div class="modal-header"><div><h2 id="consent-title" class="modal-title">Connect an account</h2><p class="card-subtitle">Choose the consent window Aashan will request.</p></div><button class="icon-button" data-action="close-modal" aria-label="Close">×</button></div><form id="consent-form"><div class="form-grid"><div class="field full"><label for="consent-purpose">Purpose</label><input id="consent-purpose" value="Personal finance spending insights" required /></div><div class="field"><label for="consent-mobile">Mobile number</label><input id="consent-mobile" inputmode="numeric" value="9999999999" required /></div><div class="field"><label for="consent-from">Data from</label><input id="consent-from" type="date" value="2026-06-01" required /></div><div class="field"><label for="consent-to">Data to</label><input id="consent-to" type="date" value="2026-08-31" required /></div></div><p class="field-help" style="margin:14px 0 0">${demo ? "Local mock mode is enabled. You can run the full consent → session → processing demo after creation." : "Setu will open its consent URL in a new tab. Credentials never enter this form."}</p><div class="button-row" style="margin-top:18px">${button(demo ? "Create demo consent" : "Create Setu consent", "submit-consent", "primary")}${button("Cancel", "close-modal", "secondary")}</div></form></div></div>`; }
  return "";
}

function render() {
  const meta = viewMeta[state.active] || viewMeta.overview;
  const health = state.data.health || {};
  document.title = `Aashan · ${meta[0]}`;
  document.querySelector("#app").innerHTML = `<div class="app-shell"><aside class="sidebar"><div class="brand"><div class="brand-mark" aria-hidden="true">A</div><div><div class="brand-name">aashan</div><div class="brand-subtitle">privacy-first finance</div></div></div><div class="nav-label">Workspace</div><nav class="nav" aria-label="Primary navigation">${navItems.map(([id, icon, label]) => `<button class="nav-item ${state.active === id ? "active" : ""}" data-action="navigate:${id}" aria-current="${state.active === id ? "page" : "false"}"><span class="nav-icon" aria-hidden="true">${icon}</span><span>${label}</span></button>`).join("")}</nav><div class="sidebar-footer">${pill(health.status === "ok" ? "API operational" : "API checking", health.status === "ok" ? "good" : "warn")}<p>Goldfish Memory keeps patterns useful and raw rows temporary.</p></div></aside><main class="main"><header class="topbar"><div><div class="eyebrow">AASHAN / ${html(meta[0].toUpperCase())}</div><h1 class="page-title">${html(meta[0])}</h1><p class="page-description">${html(meta[1])}</p></div><div class="top-actions">${button("Import CSV", "open-import", "secondary")}${button("Refresh", "refresh", "primary")}</div></header><div class="content">${pageContent()}</div></main></div>${renderModal()}${state.toast ? `<div class="toast" role="status">${html(state.toast)}</div>` : ""}`;
}

async function refresh() {
  state.loading = true; render();
  const requests = { health: api.health(), summary: api.summary(), categories: api.categories(), monthly: api.monthly(), patterns: api.patterns(), anomalies: api.anomalies(), privacy: api.privacy(), budgets: api.budgets(), budgetStatus: api.budgetStatus() };
  const results = await Promise.all(Object.entries(requests).map(async ([key, promise]) => { try { return [key, await promise, null]; } catch (error) { return [key, {}, error.message]; } }));
  state.data = Object.fromEntries(results.map(([key, value]) => [key, value]));
  state.errors = results.filter(([, , error]) => error).map(([key, , error]) => `${key}: ${error}`);
  state.loading = false; render();
}

function toast(message) { state.toast = message; render(); window.setTimeout(() => { state.toast = ""; render(); }, 3600); }
function readConsentForm() { const value = (id) => document.querySelector(`#${id}`)?.value; return { purpose: value("consent-purpose"), mobile_number: value("consent-mobile"), data_range_from: `${value("consent-from")}T00:00:00Z`, data_range_to: `${value("consent-to")}T23:59:59Z` }; }

async function handleAction(action, element) {
  if (action.startsWith("navigate:")) { window.location.hash = action.slice(9); return; }
  if (action === "close-modal") { state.modal = null; render(); return; }
  if (action === "open-import") { state.modal = "import"; render(); return; }
  if (action === "open-consent") { state.modal = "consent"; render(); return; }
  if (action === "refresh") { await refresh(); toast("Dashboard refreshed from FastAPI."); return; }
  if (action === "demo-run") { try { await api.demoRun(); await refresh(); toast("Demo data processed. Raw rows were discarded."); } catch (error) { toast(error.message); } return; }
  if (action === "process-csv") { const input = document.querySelector("#modal-csv-file") || document.querySelector("#csv-file"); const file = input?.files?.[0]; if (!file) { toast("Choose a CSV file first."); return; } try { await api.ingestCSV(file); state.modal = null; await refresh(); toast("CSV processed. Raw rows were discarded."); } catch (error) { toast(error.message); } return; }
  if (action === "approve-mock") { try { const result = await api.approveMockConsent(state.consent.consent_id); state.consent = { ...state.consent, status: result.status || "ACTIVE" }; render(); toast("Demo consent approved. Create the data session next."); } catch (error) { state.consent.error = error.message; render(); } return; }
  if (action === "fetch-mock") { try { await api.fetchMockData(state.consent.consent_id); state.consent = { ...state.consent, processed: true, session_id: "mock-session", status: "SYNCED" }; await refresh(); toast("Demo data processed and forgotten."); } catch (error) { state.consent.error = error.message; render(); } return; }
  if (action === "refresh-consent") { try { const result = await api.consentStatus(state.consent.consent_id); state.consent = { ...state.consent, ...(result.setu || {}), setu_status: result.setu?.status || result.status }; render(); toast("Consent status refreshed."); } catch (error) { state.consent.error = error.message; render(); } return; }
  if (action === "create-session") { try { const result = await api.createSession(state.consent.consent_id); state.consent = { ...state.consent, session_id: result.session_id, status: "SESSION_CREATED" }; render(); toast("Data session created. Waiting for Setu processing notification."); } catch (error) { state.consent.error = error.message; render(); } return; }
  if (action === "add-budget") { const category = document.querySelector("#new-budget-category")?.value.trim(); const amount = document.querySelector("#new-budget-amount")?.value; if (!category || !amount) { toast("Enter a category and amount first."); return; } const existing = { ...(state.data.budgets?.budgets || {}) }; existing[category] = number(amount); try { await api.saveBudgets(existing); await refresh(); toast(`${category} budget added.`); } catch (error) { toast(error.message); } return; }
  if (action === "save-budgets") { const budgets = {}; document.querySelectorAll("[data-budget-category]").forEach((input) => { budgets[input.dataset.budgetCategory] = number(input.value); }); const category = document.querySelector("#new-budget-category")?.value.trim(); const amount = document.querySelector("#new-budget-amount")?.value; if (category && amount) budgets[category] = number(amount); try { await api.saveBudgets(budgets); await refresh(); toast("Budgets saved."); } catch (error) { toast(error.message); } return; }
  if (action === "ask-insight") { const question = document.querySelector("#insight-question")?.value.trim(); if (!question) return; element.disabled = true; try { const result = await api.queryInsight(question); state.insightAnswer = result.answer || "No answer was returned."; render(); } catch (error) { toast(error.message); } return; }
  if (action === "submit-consent") { const payload = readConsentForm(); state.modal = null; try { const result = state.data.health?.mock_mode ? await api.createMockConsent(payload) : await api.createConsent(payload); state.consent = { mode: state.data.health?.mock_mode ? "mock" : "setu", consent_id: result.consent_id || result.id, url: result.url ? (result.url.startsWith("http") ? result.url : `${window.location.origin}${result.url}`) : "", status: result.setu_status || result.status || "PENDING" }; window.location.hash = "accounts"; render(); toast("Consent created. Continue through the lifecycle card."); } catch (error) { state.consent = { mode: state.data.health?.mock_mode ? "mock" : "setu", error: error.message }; window.location.hash = "accounts"; render(); } return; }
}

document.addEventListener("click", async (event) => { const target = event.target.closest("[data-action]"); if (!target) return; event.preventDefault(); await handleAction(target.dataset.action, target); });
document.addEventListener("submit", async (event) => { event.preventDefault(); const action = event.target.id === "consent-form" ? "submit-consent" : event.target.id === "budget-form" ? "save-budgets" : event.target.id === "insight-form" ? "ask-insight" : ""; if (action) await handleAction(action, event.submitter || event.target); });
document.addEventListener("change", async (event) => { if (event.target.id === "csv-file" && event.target.files?.[0]) { try { await api.ingestCSV(event.target.files[0]); await refresh(); toast("CSV processed. Raw rows were discarded."); } catch (error) { toast(error.message); } } });
window.addEventListener("hashchange", () => { const next = window.location.hash.slice(1); state.active = viewMeta[next] ? next : "overview"; render(); });

render();
refresh();
