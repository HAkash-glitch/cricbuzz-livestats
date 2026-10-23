"""Live Matches: live/recent matches + scorecards from the Cricbuzz API (or demo fixture)."""
import json

import pandas as pd
import streamlit as st

import config
from api.cricbuzz_client import ApiError, CricbuzzClient, parse_match_list, parse_scorecard
from services import sync_service
from utils import db_connection as db
from utils.ui import show_error

st.title("⚡ Live Matches")

live_ok = config.api_configured()
source = st.radio("Data source", ["Cricbuzz API (live)", "Demo fixture"], horizontal=True,
                  index=0 if live_ok else 1, help="Live needs RAPIDAPI_KEY in .env")
use_live = source.startswith("Cricbuzz")
if use_live and not live_ok:
    st.error("No `RAPIDAPI_KEY` configured — switch to the demo fixture or add a key to `.env`.")
    st.stop()

feed = st.segmented_control("Feed", ["Live", "Recent"], default="Live") if use_live else "Live"
client = CricbuzzClient() if use_live else None


@st.cache_data(ttl=30, show_spinner="Fetching matches…")
def load_matches(kind: str, live: bool) -> list[dict]:
    if not live:
        return parse_match_list(json.loads(config.SAMPLE_LIVE_FILE.read_text()))
    c = CricbuzzClient()
    return parse_match_list(c.live_matches() if kind == "Live" else c.recent_matches())


try:
    matches = load_matches(feed or "Live", use_live)
except ApiError as exc:
    show_error(exc, "Could not load matches")
    st.stop()

top = st.columns([4, 1])
top[0].markdown(f'<span class="pill {"" if use_live else "demo"}">{"LIVE API" if use_live else "DEMO DATA"}</span>'
                f" {len(matches)} match(es)", unsafe_allow_html=True)
if top[1].button("🔄 Refresh"):
    load_matches.clear()
    st.rerun()

if not matches:
    st.info("No matches in this feed right now.")
    st.stop()

cols = st.columns(2)
for i, m in enumerate(matches):
    with cols[i % 2]:
        st.markdown(f"""<div class="matchcard">
<span class="pill">{m['format']}</span><span style="color:#8A97AB;font-size:12px">{m['series']} · {m['description']}</span>
<div class="t" style="margin-top:6px">{m['team1']} <span class="sc">{m['team1_score']}</span></div>
<div class="t">{m['team2']} <span class="sc">{m['team2_score']}</span></div>
<div class="st">{m['status'] or ''}</div>
<div style="color:#64748B;font-size:12px;margin-top:4px">📍 {m['venue']}, {m['city']}</div></div>""",
            unsafe_allow_html=True)

st.divider()
st.subheader("Scorecard")
labels = {f"{m['team1_short']} vs {m['team2_short']} — {m['description']}": m for m in matches}
chosen = labels[st.selectbox("Match", list(labels))]

try:
    if use_live:
        card = client.scorecard(chosen["match_id"])
    else:
        card = json.loads((config.BASE_DIR / "data" / "sample_scorecard.json").read_text()) \
            if chosen["match_id"] == 900101 else {}
    innings = parse_scorecard(card)
except ApiError as exc:
    show_error(exc, "Could not load scorecard")
    innings = []

if not innings:
    st.info("No scorecard available for this match yet." if use_live
            else "The demo fixture only includes a scorecard for the 3rd ODI.")
for inn in innings:
    st.markdown(f"**{inn['team']}** — {inn['total']}")
    a, b = st.columns(2)
    a.dataframe(pd.DataFrame(inn["batting"]), hide_index=True, width="stretch")
    b.dataframe(pd.DataFrame(inn["bowling"]), hide_index=True, width="stretch")

if use_live and feed == "Recent":
    st.divider()
    if st.button("💾 Save these matches to the database"):
        try:
            n = sync_service.save_matches(matches)
            st.cache_data.clear()
            st.success(f"Saved {n} match(es) to the database.")
        except db.DatabaseError as exc:
            show_error(exc, "Database error")
