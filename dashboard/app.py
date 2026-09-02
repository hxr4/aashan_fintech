from typing import Any, Dict, List
from datetime import datetime

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from dashboard.api_client import (
    APIClientError,
    create_consent,
    create_mock_consent,
    fetch_anomalies,
    fetch_budgets,
    fetch_categories,
    fetch_consent_status,
    fetch_monthly,
    fetch_patterns,
    fetch_privacy,
    fetch_summary,
    upload_csv,
)
from dashboard.components import anomaly_card, empty_state, metric_card, progress_bar, section_title, status_pill


API_URL = "http://localhost:8000"

st.set_page_config(page_title="Aashan · Privacy-first finance", page_icon="🐟", layout="wide", initial_sidebar_state="expanded")


def inject_styles() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Manrope:wght@400;500;600;700;800&display=swap');
        :root { --bg:#080b13; --panel:#101521; --panel2:#141c2b; --line:#223047; --text:#f4f7fb; --muted:#8e9bb0; --cyan:#2de2e6; --violet:#9b7bff; --lime:#b9f227; --red:#ff6584; }
        .stApp { background: radial-gradient(circle at 80% -10%, #162440 0%, var(--bg) 38%); color:var(--text); font-family:'Manrope', sans-serif; }
        [data-testid="stHeader"] { background:transparent; }
        [data-testid="stSidebar"] { background:#0b101b; border-right:1px solid var(--line); }
        [data-testid="stSidebar"] * { font-family:'Manrope', sans-serif; }
        .block-container { max-width:1440px; padding:2rem 3rem 4rem; }
        h1,h2,h3,p { font-family:'Manrope', sans-serif; }
        .hero { display:flex; align-items:flex-end; justify-content:space-between; gap:2rem; margin:0 0 2rem; }
        .eyebrow { color:var(--cyan); font-family:'DM Mono', monospace; font-size:.72rem; letter-spacing:.18em; text-transform:uppercase; margin-bottom:.55rem; }
        .hero-title { font-size:2.55rem; line-height:1; font-weight:800; letter-spacing:-.06em; }
        .hero-subtitle { color:var(--muted); margin-top:.65rem; font-size:1rem; }
        .hero-orb { width:92px; height:92px; border:1px solid #2de2e655; border-radius:50%; display:flex; align-items:center; justify-content:center; color:var(--cyan); font-size:2.6rem; box-shadow:0 0 45px #2de2e622, inset 0 0 30px #2de2e612; }
        .metric-card { background:linear-gradient(145deg,#121a29,#0d131f); border:1px solid var(--line); border-radius:16px; padding:1.1rem 1.2rem 1.15rem; min-height:104px; box-shadow:0 12px 30px #00000022; position:relative; overflow:hidden; }
        .metric-card:after { content:''; position:absolute; left:0; bottom:0; width:38%; height:2px; background:var(--cyan); box-shadow:0 0 18px var(--cyan); }
        .accent-violet:after { background:var(--violet); box-shadow:0 0 18px var(--violet); } .accent-lime:after { background:var(--lime); box-shadow:0 0 18px var(--lime); } .accent-red:after { background:var(--red); box-shadow:0 0 18px var(--red); }
        .metric-label { color:var(--muted); text-transform:uppercase; letter-spacing:.1em; font-size:.66rem; font-family:'DM Mono',monospace; }
        .metric-value { color:var(--text); font-size:1.65rem; font-weight:800; letter-spacing:-.04em; margin-top:.55rem; }
        .metric-detail { color:var(--muted); font-size:.72rem; margin-top:.15rem; }
        .section-title { font-size:1.12rem; font-weight:800; letter-spacing:-.02em; margin:1.7rem 0 .35rem; }
        .section-subtitle { color:var(--muted); font-size:.82rem; margin-bottom:.8rem; }
        .status-pill { display:inline-block; border:1px solid var(--line); color:var(--muted); border-radius:999px; padding:.38rem .65rem; font-family:'DM Mono',monospace; font-size:.68rem; }
        .status-pill.good { color:var(--lime); border-color:#b9f22755; } .status-pill.warn { color:#ffd166; border-color:#ffd16655; }
        .progress-track { height:7px; border-radius:999px; background:#202b3e; overflow:hidden; margin:.6rem 0 .35rem; } .progress-fill { height:100%; border-radius:999px; background:var(--cyan); box-shadow:0 0 14px #2de2e688; } .progress-fill.warn { background:#ffd166; box-shadow:0 0 14px #ffd16688; } .progress-fill.danger { background:var(--red); box-shadow:0 0 14px #ff658488; }
        .anomaly-card { background:#171521; border:1px solid #ff658455; border-left:3px solid var(--red); border-radius:14px; padding:1rem 1.1rem; margin:.4rem 0 .8rem; } .anomaly-top { display:flex; align-items:center; gap:.5rem; } .severity-dot { width:8px; height:8px; border-radius:50%; background:var(--red); box-shadow:0 0 12px var(--red); } .anomaly-category { font-weight:800; } .anomaly-amount { margin-left:auto; color:#ffd2da; font-family:'DM Mono',monospace; } .anomaly-reason { color:var(--muted); font-size:.8rem; margin-top:.7rem; } .anomaly-label { color:var(--red); font-family:'DM Mono',monospace; font-size:.58rem; letter-spacing:.12em; margin-top:.8rem; }
        .empty-state { border:1px dashed var(--line); border-radius:14px; padding:1.1rem; color:var(--muted); background:#0e1522; }
        .privacy-flow { display:grid; grid-template-columns:repeat(5,1fr); gap:.5rem; margin:1rem 0 1.5rem; } .privacy-step { background:#101824; border:1px solid var(--line); border-radius:12px; padding:.85rem .7rem; text-align:center; color:var(--muted); font-size:.72rem; } .privacy-step strong { display:block; color:var(--cyan); font-family:'DM Mono',monospace; font-size:.6rem; margin-bottom:.35rem; }
        .import-card { background:linear-gradient(145deg,#111c2d,#10141f); border:1px solid #2de2e633; border-radius:18px; padding:1.4rem; }
        div[data-testid="stMetric"] { background:#101824; border:1px solid var(--line); border-radius:14px; padding:1rem; }
        div[data-testid="stMetricLabel"] p { color:var(--muted); }
        .stButton > button { border:1px solid #2de2e666; border-radius:10px; background:#122536; color:var(--text); font-weight:700; }
        .stButton > button:hover { border-color:var(--cyan); color:var(--cyan); }
        </style>
        """,
        unsafe_allow_html=True,
    )


def money(value: Any) -> str:
    return "₹{:,.0f}".format(float(value or 0))


def load_data() -> Dict[str, Any]:
    loaders = {
        "summary": fetch_summary,
        "categories": fetch_categories,
        "monthly": fetch_monthly,
        "patterns": fetch_patterns,
        "anomalies": fetch_anomalies,
        "privacy": fetch_privacy,
        "budgets": fetch_budgets,
    }
    data: Dict[str, Any] = {}
    errors: List[str] = []
    for key, loader in loaders.items():
        try:
            data[key] = loader(API_URL)
        except APIClientError as exc:
            errors.append(str(exc))
    data["errors"] = errors
    return data


def chart_layout(fig: go.Figure, height: int = 310) -> go.Figure:
    fig.update_layout(
        height=height,
        margin=dict(l=8, r=8, t=26, b=8),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Manrope", color="#dce5f2"),
        legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(size=11)),
        hoverlabel=dict(bgcolor="#111b2b", font_color="#f4f7fb"),
    )
    fig.update_xaxes(showgrid=False, zeroline=False, color="#8e9bb0")
    fig.update_yaxes(showgrid=True, gridcolor="#223047", zeroline=False, color="#8e9bb0")
    return fig


def category_donut(categories: Dict[str, Any]) -> go.Figure:
    frame = pd.DataFrame({"category": list(categories.keys()), "amount": list(categories.values())})
    fig = px.pie(frame, names="category", values="amount", hole=.68, color_discrete_sequence=["#2de2e6", "#9b7bff", "#b9f227", "#ffcf5c", "#ff6584", "#62a0ff", "#e98cff", "#65d6a6"])
    fig.update_traces(textposition="outside", textinfo="label", marker=dict(line=dict(color="#101521", width=3)))
    return chart_layout(fig, 350)


def monthly_chart(monthly: Dict[str, Any]) -> go.Figure:
    month_keys = list(monthly.keys())
    month_labels = []
    for month_key in month_keys:
        try:
            month_labels.append(datetime.strptime(str(month_key), "%Y-%m").strftime("%b %Y"))
        except ValueError:
            month_labels.append(str(month_key))
    frame = pd.DataFrame({"month": month_labels, "spending": list(monthly.values())})
    fig = px.bar(frame, x="month", y="spending", color_discrete_sequence=["#2de2e6"])
    fig.update_traces(marker_line_width=0)
    # API month keys are YYYY-MM categories, never timestamps. Explicitly set
    # a categorical axis so Plotly cannot interpret them as datetimes.
    fig.update_xaxes(type="category", categoryorder="array", categoryarray=month_labels)
    return chart_layout(fig, 300)


def quick_read_text(summary: Dict[str, Any], category_payload: Dict[str, Any]) -> str:
    """Build the overview copy from debit-only categories and income totals."""
    categories = category_payload.get("categories", {})
    spending = float(summary.get("total_spending", 0) or 0)
    income = float(summary.get("total_credit", 0) or 0)
    net = float(summary.get("net_cash_flow", income - spending) or 0)

    if categories:
        top_category, top_amount = max(categories.items(), key=lambda item: float(item[1] or 0))
        spending_sentence = "%s is your largest spending category at %s." % (top_category, money(top_amount))
    else:
        spending_sentence = "No debit spending categories are available yet."

    if net > 0:
        cash_sentence = "Income of %s exceeds spending by %s." % (money(income), money(net))
    elif net < 0:
        cash_sentence = "Spending exceeds income by %s." % money(abs(net))
    else:
        cash_sentence = "Income and spending are balanced."
    return "%s %s" % (spending_sentence, cash_sentence)


def render_sidebar() -> str:
    with st.sidebar:
        st.markdown('<div class="eyebrow">AASHAN / FINANCE OS</div>', unsafe_allow_html=True)
        st.markdown("## 🐟 Aashan")
        st.caption("Privacy-first personal finance")
        st.divider()
        page = st.radio("Navigate", ["Overview", "Spending", "Budgets", "Anomalies", "AI Insights", "Import", "Privacy"], label_visibility="collapsed")
        st.divider()
        if st.button("↻  Refresh data", use_container_width=True):
            st.session_state["data"] = load_data()
            st.rerun()
        st.markdown("<br>", unsafe_allow_html=True)
        status_pill("API", "localhost:8000", "good" if not st.session_state.get("data", {}).get("errors") else "warn")
    return page


def render_header(page: str) -> None:
    st.markdown(
        '<div class="hero"><div><div class="eyebrow">%s / LIVE AGGREGATES</div><div class="hero-title">%s</div><div class="hero-subtitle">Privacy-first personal finance · aggregate intelligence with Goldfish Memory.</div></div><div class="hero-orb">🐟</div></div>'
        % (page.upper(), page),
        unsafe_allow_html=True,
    )


def render_overview(data: Dict[str, Any]) -> None:
    summary, categories, monthly, patterns = data.get("summary", {}), data.get("categories", {}), data.get("monthly", {}), data.get("patterns", {})
    income = summary.get("total_credit", 0)
    spending = summary.get("total_spending", 0)
    net = summary.get("net_cash_flow", income - spending)
    cols = st.columns(5)
    for col, label, value, accent in zip(cols, ["Total spending", "Total income", "Net cash flow", "Avg daily spend", "Transactions"], [money(spending), money(income), money(net), money(patterns.get("average_daily_spending", 0)), str(summary.get("transaction_count", 0))], ["cyan", "lime", "violet", "cyan", "lime"]):
        with col:
            metric_card(label, value, accent)
    st.markdown("<br>", unsafe_allow_html=True)
    if not categories.get("categories"):
        empty_state("No aggregate spending data yet. Import a CSV to populate the dashboard.")
        return
    left, right = st.columns([1, 1.35])
    with left:
        section_title("Where your money went", "Category mix · debit transactions only")
        st.plotly_chart(category_donut(categories.get("categories", {})), use_container_width=True, config={"displayModeBar": False})
    with right:
        section_title("Monthly rhythm", "Spending trend from processed aggregates")
        st.plotly_chart(monthly_chart(monthly.get("monthly", {})), use_container_width=True, config={"displayModeBar": False})
    st.markdown('<div class="import-card"><div class="eyebrow">QUICK READ</div>%s</div>' % quick_read_text(summary, categories), unsafe_allow_html=True)


def render_spending(data: Dict[str, Any]) -> None:
    categories = data.get("categories", {}).get("categories", {})
    percentages = data.get("categories", {}).get("percentages", {})
    monthly = data.get("monthly", {}).get("monthly", {})
    patterns = data.get("patterns", {})
    section_title("Spending intelligence", "A clean view of your aggregate behavior")
    if not categories:
        empty_state("No spending aggregates available.")
        return
    ranking = pd.DataFrame({"category": list(categories.keys()), "amount": list(categories.values())}).sort_values("amount")
    fig = px.bar(ranking, x="amount", y="category", orientation="h", text_auto=".0f", color="amount", color_continuous_scale=["#182a41", "#2de2e6"])
    fig.update_coloraxes(showscale=False)
    st.plotly_chart(chart_layout(fig, 360), use_container_width=True, config={"displayModeBar": False})
    c1, c2 = st.columns(2)
    with c1:
        section_title("Category share")
        pct = pd.DataFrame({"category": list(percentages.keys()), "share": list(percentages.values())})
        fig = px.bar(pct.sort_values("share"), x="share", y="category", orientation="h", text_auto=".1f", color_discrete_sequence=["#9b7bff"])
        st.plotly_chart(chart_layout(fig, 300), use_container_width=True, config={"displayModeBar": False})
    with c2:
        section_title("Monthly trend")
        st.plotly_chart(monthly_chart(monthly), use_container_width=True, config={"displayModeBar": False})
    c3, c4 = st.columns(2)
    with c3:
        section_title("Weekday vs weekend")
        weekend = patterns.get("weekend_vs_weekday", {})
        fig = px.bar(pd.DataFrame({"day type": list(weekend.keys()), "spending": list(weekend.values())}), x="day type", y="spending", color="day type", color_discrete_sequence=["#2de2e6", "#b9f227"])
        st.plotly_chart(chart_layout(fig, 280), use_container_width=True, config={"displayModeBar": False})
    with c4:
        section_title("Daily pattern")
        daily = patterns.get("daily", {})
        fig = px.line(pd.DataFrame({"date": list(daily.keys()), "spending": list(daily.values())}), x="date", y="spending", markers=True, color_discrete_sequence=["#ffcf5c"])
        st.plotly_chart(chart_layout(fig, 280), use_container_width=True, config={"displayModeBar": False})


def render_budgets(data: Dict[str, Any]) -> None:
    section_title("Budget control", "Configured limits against processed debit aggregates")
    statuses = data.get("budgets", {}).get("status", [])
    if not statuses:
        empty_state("No budgets configured yet. Configure category budgets through the backend API.")
        return
    for row in statuses:
        used = float(row.get("percentage_used", 0) or 0)
        over = bool(row.get("over_budget"))
        cols = st.columns([1.5, 1, 1, 1.3, 2])
        cols[0].markdown("**%s**" % row.get("category", "Other"))
        cols[1].markdown("Spent  **%s**" % money(row.get("spent", 0)))
        cols[2].markdown("Budget  **%s**" % money(row.get("budget", 0)))
        cols[3].markdown("Remaining  **%s**" % money(row.get("remaining", 0)))
        with cols[4]:
            st.markdown("**%s%%** %s" % (round(used), "· OVER" if over else ""))
            progress_bar(used, "danger" if over else "warn" if used >= 80 else "cyan")
        if over:
            st.warning("%s is over budget by %s." % (row.get("category", "This category"), money(abs(float(row.get("remaining", 0) or 0)))))
        st.markdown("<hr style='border-color:#1c2a3d; margin:.35rem 0 1rem'>", unsafe_allow_html=True)


def render_anomalies(data: Dict[str, Any]) -> None:
    anomalies = data.get("anomalies", {}).get("anomalies", [])
    section_title("Anomaly radar", "Statistical alerts without exposing transaction narrations")
    if not anomalies:
        st.success("No unusual spending detected in the current aggregate window.")
        return
    st.markdown("<span class='status-pill warn'>%d alerts detected</span>" % len(anomalies), unsafe_allow_html=True)
    for anomaly in anomalies:
        anomaly_card(anomaly)


def render_insights(data: Dict[str, Any]) -> None:
    section_title("AI Insights", "Deterministic aggregate insights · no LLM connected")
    summary, categories, monthly, patterns = data.get("summary", {}), data.get("categories", {}), data.get("monthly", {}), data.get("patterns", {})
    category_values = categories.get("categories", {})
    month_values = monthly.get("monthly", {})
    budget_rows = data.get("budgets", {}).get("status", [])
    anomalies = data.get("anomalies", {}).get("anomalies", [])
    insights = []
    if category_values:
        top = max(category_values, key=category_values.get)
        insights.append(("TOP CATEGORY", "%s accounts for %s of spending." % (top, money(category_values[top]))))
    if month_values:
        peak = max(month_values, key=month_values.get)
        insights.append(("PEAK MONTH", "%s was your highest-spending month at %s." % (peak, money(month_values[peak]))))
    weekend = patterns.get("weekend_vs_weekday", {})
    if weekend:
        lead = "weekends" if weekend.get("weekend", 0) > weekend.get("weekday", 0) else "weekdays"
        insights.append(("SPENDING RHYTHM", "You spend more on %s." % lead))
    insights.append(("UNUSUAL SPENDING", "%d statistical alert(s) are currently open." % len(anomalies)))
    over = [row.get("category") for row in budget_rows if row.get("over_budget")]
    insights.append(("BUDGET WATCH", "Over budget: %s." % ", ".join(over) if over else "All configured budgets are within limits."))
    for label, text in insights:
        st.markdown('<div class="import-card" style="margin:.55rem 0"><div class="eyebrow">%s</div><div style="font-size:1.05rem">%s</div></div>' % (label, text), unsafe_allow_html=True)


def render_import(data: Dict[str, Any]) -> None:
    section_title("Bring in your data", "The backend processes it, aggregates it, and forgets the raw rows")
    left, right = st.columns(2)
    with left:
        st.markdown('<div class="import-card">', unsafe_allow_html=True)
        st.markdown("### CSV upload")
        st.caption("Send a CSV to FastAPI. Streamlit never reads SQLite directly.")
        file = st.file_uploader("Choose a CSV", type=["csv"], label_visibility="collapsed")
        if file and st.button("Process CSV", use_container_width=True):
            with st.spinner("Processing and aggregating…"):
                try:
                    result = upload_csv(file.getvalue(), file.name, API_URL)
                    st.session_state["last_import"] = result
                    st.session_state["data"] = load_data()
                    st.success("CSV processed. Raw rows were discarded after aggregation.")
                except APIClientError as exc:
                    st.error(str(exc))
        st.markdown('</div>', unsafe_allow_html=True)
    with right:
        st.markdown('<div class="import-card">', unsafe_allow_html=True)
        st.markdown("### Account Aggregator / Setu")
        st.caption("Aashan includes a Setu AA sandbox adapter. Connection consent is handled by FastAPI.")
        if st.button("Connect Account", use_container_width=True):
            try:
                consent = create_consent(API_URL)
                st.session_state["setu_consent"] = consent
                st.success("Setu consent created. Open the consent flow to continue.")
            except APIClientError as exc:
                st.error(str(exc))
        consent = st.session_state.get("setu_consent")
        if consent:
            st.caption("Consent ID: %s" % consent.get("consent_id", "pending"))
            if consent.get("url"):
                st.link_button("Open Setu consent flow", consent["url"], use_container_width=True)
            if st.button("Refresh account status and dashboard", use_container_width=True):
                try:
                    if consent.get("consent_id"):
                        status = fetch_consent_status(consent["consent_id"], API_URL)
                        st.session_state["setu_consent_status"] = status
                    st.session_state["data"] = load_data()
                    st.rerun()
                except APIClientError as exc:
                    st.error(str(exc))
        if st.session_state.get("setu_consent_status"):
            status = st.session_state["setu_consent_status"]
            st.caption("Setu status: %s · Data fetched: %s" % (status.get("setu", {}).get("status", "unknown"), status.get("data_fetched", False)))
        if st.button("Use mock AA fallback", use_container_width=True):
            try:
                mock_consent = create_mock_consent(API_URL)
                st.success("Mock consent created. Continue in the fallback flow.")
                st.code(mock_consent.get("url", "Consent created"), language=None)
            except APIClientError as exc:
                st.error(str(exc))
        st.markdown('</div>', unsafe_allow_html=True)
    if st.session_state.get("last_import"):
        result = st.session_state["last_import"]
        aggregate = result.get("aggregate", {})
        section_title("Latest processing result")
        cols = st.columns(4)
        for col, label, value in zip(cols, ["Rows processed", "Spending", "Income", "Net cash flow"], [result.get("rows_processed", 0), money(aggregate.get("total_spending", 0)), money(aggregate.get("total_credit", 0)), money(aggregate.get("net_cash_flow", 0))]):
            with col:
                metric_card(label, str(value), "cyan")
        st.caption("Categories and aggregates are now available on the dashboard pages. Raw descriptions are not shown.")


def render_privacy(data: Dict[str, Any]) -> None:
    privacy = data.get("privacy", {})
    section_title("Goldfish Memory", "The system learns patterns, not permanent transaction history")
    st.markdown('<div class="privacy-flow"><div class="privacy-step"><strong>01</strong>RAW TRANSACTIONS</div><div class="privacy-step"><strong>02</strong>PROCESSING</div><div class="privacy-step"><strong>03</strong>NLP CATEGORIZATION</div><div class="privacy-step"><strong>04</strong>AGGREGATION</div><div class="privacy-step"><strong>05</strong>RAW DATA FORGOTTEN</div></div>', unsafe_allow_html=True)
    cols = st.columns(3)
    with cols[0]:
        status_pill("Raw transactions persisted", str(bool(privacy.get("raw_transactions_persisted", False))).lower(), "good" if not privacy.get("raw_transactions_persisted", False) else "warn")
    with cols[1]:
        status_pill("Aggregate data persisted", str(bool(privacy.get("aggregate_data_persisted", False))).lower(), "good" if privacy.get("aggregate_data_persisted", False) else "warn")
    with cols[2]:
        status_pill("Raw descriptions exposed to AI", "false", "good")
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown('<div class="import-card"><div class="eyebrow">PRIVACY CONTRACT</div><h3>Goldfish Memory 🐟</h3><p style="color:#8e9bb0">Raw financial rows are temporary inputs. Aashan normalizes, categorizes, aggregates, and deletes them. Dashboard and insight surfaces receive aggregate JSON only.</p><p style="color:#8e9bb0">In-memory raw count: <b style="color:#2de2e6">%s</b> · persisted tables are aggregate-only.</p></div>' % privacy.get("raw_transaction_count_in_memory", 0), unsafe_allow_html=True)


def main() -> None:
    inject_styles()
    if "data" not in st.session_state:
        with st.spinner("Syncing aggregate intelligence…"):
            st.session_state["data"] = load_data()
    data = st.session_state["data"]
    page = render_sidebar()
    errors = data.get("errors", [])
    if errors:
        st.error("FastAPI connection issue: %s" % errors[0])
        st.caption("Start the backend with: uvicorn app.main:app --reload --port 8000")
    render_header(page)
    renderers = {"Overview": render_overview, "Spending": render_spending, "Budgets": render_budgets, "Anomalies": render_anomalies, "AI Insights": render_insights, "Import": render_import, "Privacy": render_privacy}
    renderers[page](data)


main()
