"""Cricbuzz LiveStats - Streamlit entry point (router + one-time DB bootstrap)."""
import streamlit as st

from utils.ui import ensure_database, setup_page

st.set_page_config(page_title="Cricbuzz LiveStats", page_icon="🏏", layout="wide")
setup_page()
ensure_database()

navigation = st.navigation([
    st.Page("pages/home.py", title="Home", icon="🏠", default=True),
    st.Page("pages/live_matches.py", title="Live Matches", icon="⚡"),
    st.Page("pages/top_stats.py", title="Top Player Stats", icon="🏆"),
    st.Page("pages/sql_queries.py", title="SQL Analytics", icon="🔍"),
    st.Page("pages/crud_operations.py", title="CRUD Operations", icon="🛠️"),
])
navigation.run()
