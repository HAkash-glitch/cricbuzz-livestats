"""Shared Streamlit helpers: theme CSS, DB bootstrap, cached lookups, chart styling."""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import config
from utils import db_connection as db

ACCENT, GOLD, TEAL_DIM = "#14B8A6", "#E8A33D", "#0F766E"
CAT = ["#14B8A6", "#E8A33D", "#7C8CF8", "#F0616D"]  # distinct, colour-blind-safe order

CSS = """
<style>
.block-container{padding-top:2rem;max-width:1280px}
.kpi{background:#131C2E;border:1px solid #1F2C42;border-radius:14px;padding:14px 16px}
.kpi .l{font-size:11px;letter-spacing:.09em;text-transform:uppercase;color:#64748B;font-weight:700}
.kpi .v{font-size:28px;font-weight:800;letter-spacing:-.02em;font-variant-numeric:tabular-nums;color:#E5E7EB}
.kpi .s{font-size:12px;color:#8A97AB}
.matchcard{background:#131C2E;border:1px solid #1F2C42;border-radius:14px;padding:14px 16px;margin-bottom:10px}
.matchcard .t{font-weight:700;font-size:16px}
.matchcard .sc{font-variant-numeric:tabular-nums;color:#E5E7EB;font-size:14px}
.matchcard .st{color:#E8A33D;font-size:13px;margin-top:6px}
.pill{display:inline-block;padding:2px 9px;border-radius:99px;font-size:11px;font-weight:700;
      background:rgba(20,184,166,.15);color:#14B8A6;border:1px solid rgba(20,184,166,.4);margin-right:6px}
.pill.demo{background:rgba(232,163,61,.14);color:#E8A33D;border-color:rgba(232,163,61,.4)}
</style>
"""


def setup_page() -> None:
    """Inject CSS (call at the top of every page)."""
    st.markdown(CSS, unsafe_allow_html=True)


def kpi(label: str, value: str, sub: str = "") -> str:
    return f'<div class="kpi"><div class="l">{label}</div><div class="v">{value}</div><div class="s">{sub}</div></div>'


def ensure_database() -> None:
    """Create + seed the sample DB the first time the app starts."""
    if not config.DB_PATH.exists() or _is_empty():
        from services import seed_data
        with st.spinner("First run: building the sample database..."):
            seed_data.build()
        st.cache_data.clear()


def _is_empty() -> bool:
    try:
        return db.table_count("matches") == 0
    except db.DatabaseError:
        return True


@st.cache_data(ttl=60, show_spinner=False)
def cached_query(sql: str, params: tuple = ()) -> pd.DataFrame:
    """Cached read; writes elsewhere call st.cache_data.clear()."""
    return db.run_query(sql, list(params))


def style_fig(fig: go.Figure, height: int = 380) -> go.Figure:
    """Apply the dark theme to a plotly figure."""
    fig.update_layout(
        height=height, margin=dict(l=10, r=10, t=40, b=10), colorway=CAT,
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(color="#E5E7EB"),
        legend=dict(orientation="h", y=-0.2),
    )
    fig.update_xaxes(gridcolor="#1B2740", zerolinecolor="#1B2740")
    fig.update_yaxes(gridcolor="#1B2740", zerolinecolor="#1B2740")
    return fig


def show_error(exc: Exception, where: str) -> None:
    """Uniform, non-crashing error display."""
    st.error(f"{where}: {exc}")
