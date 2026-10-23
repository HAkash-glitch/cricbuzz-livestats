"""Top Player Stats: leaderboards by format from the SQL DB, with an optional live API panel."""
import pandas as pd
import plotly.express as px
import streamlit as st

import config
from api.cricbuzz_client import ApiError, CricbuzzClient, parse_top_stats
from utils.ui import ACCENT, cached_query, show_error, style_fig

st.title("🏆 Top Player Stats")

# label -> (value column, SQL ORDER direction, extra WHERE, display label)
BAT = {
    "Most runs": ("runs", "DESC", "", "Runs"),
    "Highest score": ("highest_score", "DESC", "", "Highest score"),
    "Best batting average (min 20 inn.)": ("batting_avg", "DESC", "AND c.innings >= 20", "Average"),
    "Best strike rate (min 500 runs)": ("strike_rate", "DESC", "AND c.runs >= 500", "Strike rate"),
    "Most centuries": ("centuries", "DESC", "", "Centuries"),
}
BOWL = {
    "Most wickets": ("wickets", "DESC", "", "Wickets"),
    "Best economy (min 20 wkts)": ("economy", "ASC", "AND c.wickets >= 20 AND c.economy IS NOT NULL", "Economy"),
    "Best bowling average (min 20 wkts)": ("bowling_avg", "ASC", "AND c.wickets >= 20 AND c.bowling_avg IS NOT NULL",
                                           "Bowling avg"),
}

tab_db, tab_api = st.tabs(["From the database", "From Cricbuzz API"])


def leaderboard(cats: dict, key: str) -> None:
    c1, c2, c3 = st.columns([2, 2, 1])
    fmt = c1.selectbox("Format", config.FORMATS, key=f"{key}_f")
    cat = c2.selectbox("Category", list(cats), key=f"{key}_c")
    n = c3.number_input("Top N", 5, 25, 10, key=f"{key}_n")
    col, order, where, label = cats[cat]
    df = cached_query(
        f"SELECT p.full_name AS Player, t.team_name AS Team, c.matches AS Matches, c.{col} AS {label.replace(' ', '_')} "
        f"FROM player_career_stats c JOIN players p ON p.player_id=c.player_id JOIN teams t ON t.team_id=p.team_id "
        f"WHERE c.match_format=? {where} ORDER BY c.{col} {order} LIMIT ?", (fmt, int(n)))
    if df.empty:
        st.info("No players meet this category's minimum in this format.")
        return
    value_col = label.replace(" ", "_")
    fig = px.bar(df.iloc[::-1], x=value_col, y="Player", orientation="h", text=value_col,
                 title=f"{cat} — {fmt}", color_discrete_sequence=[ACCENT])
    fig.update_traces(textposition="outside", cliponaxis=False)
    st.plotly_chart(style_fig(fig, 60 + 34 * len(df)), width="stretch")
    st.dataframe(df, hide_index=True, width="stretch")


with tab_db:
    st.caption("Career aggregates stored in `player_career_stats`. "
               + ("" if config.api_configured() else "Sample data — simulated."))
    b, w, s = st.tabs(["🏏 Batting", "🎯 Bowling", "📈 Average vs strike rate"])
    with b:
        leaderboard(BAT, "bat")
    with w:
        leaderboard(BOWL, "bowl")
    with s:
        fmt = st.selectbox("Format", config.FORMATS, key="sc_f")
        df = cached_query("SELECT p.full_name AS Player, p.playing_role AS Role, c.batting_avg AS Average, "
                          "c.strike_rate AS Strike_rate, c.runs AS Runs FROM player_career_stats c "
                          "JOIN players p ON p.player_id=c.player_id WHERE c.match_format=? AND c.runs>=300", (fmt,))
        fig = px.scatter(df, x="Average", y="Strike_rate", size="Runs", color="Role", hover_name="Player",
                         title=f"Batting average vs strike rate — {fmt} (bubble = runs)")
        st.plotly_chart(style_fig(fig, 460), width="stretch")

with tab_api:
    if not config.api_configured():
        st.info("Add `RAPIDAPI_KEY` to `.env` to pull live top stats from Cricbuzz.")
    else:
        stat = st.selectbox("Stat", ["mostRuns", "highestScore", "highestAvg", "highestSr", "mostWickets",
                                     "lowestAvg", "bestBowlingInnings", "lowestEcon"])
        if st.button("Fetch from Cricbuzz"):
            try:
                headers, rows = parse_top_stats(CricbuzzClient().top_stats(stat))
                if rows:
                    st.dataframe(pd.DataFrame(rows, columns=headers or None), hide_index=True,
                                 width="stretch")
                else:
                    st.info("The API returned no rows for this stat.")
            except ApiError as exc:
                show_error(exc, "API error")
