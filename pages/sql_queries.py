"""SQL Analytics: the 25 practice questions + a read-only custom SQL box."""
import plotly.express as px
import streamlit as st

from services.queries import QUERIES
from utils import db_connection as db
from utils.ui import show_error, style_fig

st.title("🔍 SQL Queries & Analytics")

tab_q, tab_c = st.tabs(["25 practice questions", "Custom SQL (read-only)"])


def auto_chart(df) -> None:
    """Bar chart of the first numeric column per label, when it makes sense."""
    if df.empty or len(df) > 60 or df.shape[1] < 2:
        return
    num = [c for c in df.columns[1:] if df[c].dtype.kind in "if"]
    if df.iloc[:, 0].dtype.kind in "OU" and num:
        fig = px.bar(df, x=df.columns[0], y=num[0], title=f"{num[0]} by {df.columns[0]}")
        st.plotly_chart(style_fig(fig, 340), width="stretch")


with tab_q:
    level = st.segmented_control("Level", ["All", "Beginner", "Intermediate", "Advanced"], default="All")
    pool = [q for q in QUERIES if level in (None, "All") or q["level"] == level]
    options = {f"Q{x['id']}. {x['title']}": x for x in pool}
    q = options[st.selectbox("Question", list(options))]
    st.markdown(f"**{q['level']}** · *{q['concepts']}*")
    st.info(q["question"])
    with st.expander("View SQL", expanded=False):
        st.code(q["sql"], language="sql")
    if q["notes"]:
        st.caption(f"Notes: {q['notes']}")
    try:
        df = db.run_query(q["sql"])
        st.markdown(f"**{len(df):,} row(s)**")
        if df.empty:
            st.warning("The query ran but returned no rows for the current data.")
        else:
            st.dataframe(df, hide_index=True, width="stretch")
            st.download_button("Download CSV", df.to_csv(index=False).encode(), f"q{q['id']}.csv", "text/csv")
            auto_chart(df)
        if q.get("extra"):
            title, sql = q["extra"]
            st.markdown(f"**{title}**")
            st.dataframe(db.run_query(sql), hide_index=True, width="stretch")
    except db.DatabaseError as exc:
        show_error(exc, "Query failed")

with tab_c:
    st.caption("Single `SELECT` / `WITH` statements only; runs on a read-only connection. "
               "Views: `v_match_details`, `v_player_profile`.")
    sql = st.text_area("SQL", "SELECT team_name, COUNT(*) AS players\nFROM v_player_profile\nGROUP BY team_name",
                       height=140)
    if st.button("Run", type="primary"):
        try:
            out = db.run_readonly(sql)
            st.success(f"{len(out)} row(s)")
            st.dataframe(out, hide_index=True, width="stretch")
        except db.DatabaseError as exc:
            show_error(exc, "Query rejected or failed")
    with st.expander("Table reference"):
        st.dataframe(db.run_query("SELECT name, type FROM sqlite_master WHERE type IN ('table','view') "
                                  "AND name NOT LIKE 'sqlite_%' ORDER BY type, name"), hide_index=True)
