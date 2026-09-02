from typing import Any, Dict, Optional

import streamlit as st


def metric_card(label: str, value: str, accent: str = "cyan", detail: Optional[str] = None) -> None:
    detail_html = '<div class="metric-detail">%s</div>' % detail if detail else ""
    st.markdown(
        '<div class="metric-card accent-%s"><div class="metric-label">%s</div>'
        '<div class="metric-value">%s</div>%s</div>' % (accent, label, value, detail_html),
        unsafe_allow_html=True,
    )


def section_title(title: str, subtitle: Optional[str] = None) -> None:
    subtitle_html = '<div class="section-subtitle">%s</div>' % subtitle if subtitle else ""
    st.markdown('<div class="section-title">%s</div>%s' % (title, subtitle_html), unsafe_allow_html=True)


def status_pill(label: str, value: str, tone: str = "neutral") -> None:
    st.markdown('<span class="status-pill %s">%s · %s</span>' % (tone, label, value), unsafe_allow_html=True)


def progress_bar(value: float, tone: str = "cyan") -> None:
    bounded = max(0.0, min(100.0, float(value)))
    st.markdown(
        '<div class="progress-track"><div class="progress-fill %s" style="width:%s%%"></div></div>' % (tone, bounded),
        unsafe_allow_html=True,
    )


def empty_state(message: str) -> None:
    st.markdown('<div class="empty-state">%s</div>' % message, unsafe_allow_html=True)


def anomaly_card(anomaly: Dict[str, Any]) -> None:
    amount = float(anomaly.get("amount", 0) or 0)
    category = anomaly.get("category", "Other")
    reason = anomaly.get("reason", "Unusual spending detected.")
    st.markdown(
        '<div class="anomaly-card"><div class="anomaly-top"><span class="severity-dot"></span>'
        '<span class="anomaly-category">%s</span><span class="anomaly-amount">₹%s</span></div>'
        '<div class="anomaly-reason">%s</div><div class="anomaly-label">STATISTICAL ALERT</div></div>'
        % (category, format(amount, ",.2f"), reason),
        unsafe_allow_html=True,
    )
