"""Home: clean landing page with stats and navigation; project info tucked away."""
import streamlit as st

import config
from utils import db_connection as db
from utils.ui import kpi

st.title("🏏 Cricbuzz LiveStats")
st.caption("Real-time cricket insights and SQL-based analytics")

counts = {t: db.table_count(t) for t in ("players", "matches", "venues", "series")}
cols = st.columns(4)
for col, (label, key) in zip(cols, [("Players", "players"), ("Matches", "matches"),
                                    ("Venues", "venues"), ("Series", "series")]):
    col.markdown(kpi(label, f"{counts[key]:,}", "in database"), unsafe_allow_html=True)

st.write("")
if config.api_configured():
    st.success("Live Cricbuzz data is enabled.")
else:
    st.info("Demo mode: sample data is shown. Add `RAPIDAPI_KEY` to `.env` for live data.")

st.subheader("Explore")
cards = [
    ("pages/live_matches.py", "⚡ Live Matches", "Live scores and full scorecards"),
    ("pages/top_stats.py", "🏆 Top Player Stats", "Leaderboards by format, with charts"),
    ("pages/sql_queries.py", "🔍 SQL Analytics", "25 questions, run live on the database"),
    ("pages/crud_operations.py", "🛠️ CRUD Operations", "Add, edit and delete players and matches"),
]
for row in (cards[:2], cards[2:]):
    for col, (page, label, desc) in zip(st.columns(2), row):
        with col.container(border=True):
            st.page_link(page, label=label)
            st.caption(desc)

st.write("")
if config.DOCS_URL:
    st.link_button("📄 Project documentation & folder structure", config.DOCS_URL)
else:
    st.caption("Tip: set `DOCS_URL` in `.env` to your GitHub repo link to show a documentation button here.")
