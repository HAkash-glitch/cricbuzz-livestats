"""CRUD: players, per-format career stats, and matches — all via validated forms."""
from datetime import date

import streamlit as st

import config
from services import crud_service as svc
from utils import db_connection as db
from utils.ui import show_error

st.title("🛠️ CRUD Operations")
st.caption("Every change is validated and committed in a transaction. Queries on the SQL page reflect it immediately.")

teams = svc.list_teams()
team_map = dict(zip(teams.team_name, teams.team_id))
tab_p, tab_s, tab_m = st.tabs(["Players", "Career stats", "Matches"])


def safe(action, ok_msg: str):
    """Run a write; show friendly errors instead of tracebacks."""
    try:
        result = action()
        st.cache_data.clear()
        if result is False:
            st.warning("Nothing changed — that record was not found.")
        else:
            st.success(ok_msg)
        return result
    except svc.ValidationError as exc:
        st.warning(str(exc))
    except db.DatabaseError as exc:
        show_error(exc, "Database error")


with tab_p:
    op = st.radio("Operation", ["Read", "Create", "Update", "Delete"], horizontal=True, key="pop")
    if op == "Read":
        f1, f2, f3 = st.columns(3)
        search = f1.text_input("Search name")
        team = f2.selectbox("Team", ["All"] + list(team_map))
        role = f3.selectbox("Role", ["All"] + list(config.PLAYING_ROLES))
        df = svc.list_players(search, team_map.get(team), None if role == "All" else role)
        st.caption(f"{len(df)} player(s)")
        st.dataframe(df, hide_index=True, width="stretch")
    elif op == "Create":
        with st.form("create_player", clear_on_submit=True):
            name = st.text_input("Full name *")
            c1, c2 = st.columns(2)
            team = c1.selectbox("Team *", list(team_map))
            role = c2.selectbox("Role *", config.PLAYING_ROLES)
            bat = c1.selectbox("Batting style", ["", "Right-hand bat", "Left-hand bat"])
            bowl = c2.text_input("Bowling style", placeholder="e.g. Right-arm fast")
            dob = st.date_input("Date of birth", value=date(1995, 1, 1), min_value=date(1940, 1, 1),
                                max_value=date.today())
            if st.form_submit_button("Add player", type="primary"):
                pid = safe(lambda: svc.create_player(svc.PlayerInput(name, team_map[team], role, bat, bowl,
                                                                     dob.isoformat())), "Player added.")
                if pid:
                    st.caption(f"New player id: {pid}")
    else:
        df = svc.list_players()
        if df.empty:
            st.info("No players.")
        else:
            pick = st.selectbox("Player", df.player_id, format_func=lambda i: f"{df.set_index('player_id').loc[i, 'full_name']} "
                                f"(#{i}, {df.set_index('player_id').loc[i, 'team_name']})")
            cur = svc.get_player(int(pick))
            if op == "Update":
                with st.form("update_player"):
                    name = st.text_input("Full name", cur["full_name"])
                    c1, c2 = st.columns(2)
                    tnames = list(team_map)
                    team = c1.selectbox("Team", tnames, index=list(team_map.values()).index(cur["team_id"]))
                    role = c2.selectbox("Role", config.PLAYING_ROLES, index=config.PLAYING_ROLES.index(cur["playing_role"]))
                    bat = c1.text_input("Batting style", cur["batting_style"] or "")
                    bowl = c2.text_input("Bowling style", cur["bowling_style"] or "")
                    dob = st.text_input("Date of birth (YYYY-MM-DD)", cur["date_of_birth"] or "")
                    if st.form_submit_button("Save changes", type="primary"):
                        safe(lambda: svc.update_player(int(pick), svc.PlayerInput(
                            name, team_map[team], role, bat, bowl, dob or None)), "Player updated.")
            else:
                st.warning(f"Deleting **{cur['full_name']}** also removes their stats rows (cascade).")
                if st.checkbox("I understand — delete this player") and st.button("Delete player", type="primary"):
                    safe(lambda: svc.delete_player(int(pick)), "Player deleted.")

with tab_s:
    df = svc.list_players()
    pid = st.selectbox("Player", df.player_id, key="sp", format_func=lambda i: df.set_index("player_id").loc[i, "full_name"])
    st.dataframe(svc.get_career_stats(int(pid)), hide_index=True, width="stretch")
    st.markdown("**Add or update a format line**")
    with st.form("stat_form"):
        fmt = st.selectbox("Format", config.FORMATS)
        a, b, c, d = st.columns(4)
        matches = a.number_input("Matches", 0, 1000, 0)
        innings = b.number_input("Innings", 0, 2000, 0)
        runs = c.number_input("Runs", 0, 40000, 0)
        hs = d.number_input("Highest score", 0, 500, 0)
        bavg = a.number_input("Batting avg", 0.0, 200.0, 0.0)
        sr = b.number_input("Strike rate", 0.0, 400.0, 0.0)
        c100 = c.number_input("100s", 0, 100, 0)
        c50 = d.number_input("50s", 0, 300, 0)
        wk = a.number_input("Wickets", 0, 1500, 0)
        bowlavg = b.number_input("Bowling avg", 0.0, 200.0, 0.0)
        econ = c.number_input("Economy", 0.0, 20.0, 0.0)
        ct = d.number_input("Catches", 0, 500, 0)
        if st.form_submit_button("Save stats", type="primary"):
            safe(lambda: svc.upsert_career_stat(svc.CareerStatInput(
                int(pid), fmt, matches, innings, runs, hs, bavg or None, sr or None, c100, c50, wk,
                bowlavg or None, econ or None, ct, 0)), "Stats saved.")
    del_fmt = st.selectbox("Delete a format line", config.FORMATS, key="df")
    if st.button("Delete that format's stats"):
        safe(lambda: svc.delete_career_stat(int(pid), del_fmt), "Deleted.")

with tab_m:
    st.dataframe(svc.list_matches(30), hide_index=True, width="stretch")
    venues = svc.list_venues()
    vmap = dict(zip(venues.label, venues.venue_id))
    with st.expander("➕ Add a match"):
        with st.form("add_match", clear_on_submit=True):
            desc = st.text_input("Description", placeholder="e.g. 1st ODI")
            fmt = st.selectbox("Format", config.FORMATS, key="mf")
            c1, c2 = st.columns(2)
            t1 = c1.selectbox("Team 1", list(team_map), key="t1")
            t2 = c2.selectbox("Team 2", list(team_map), index=1, key="t2")
            ven = st.selectbox("Venue", list(vmap))
            when = st.date_input("Date", value=date.today())
            if st.form_submit_button("Add match", type="primary"):
                safe(lambda: svc.create_match(desc, fmt, team_map[t1], team_map[t2], vmap[ven], when.isoformat()),
                     "Match added.")
    with st.expander("✏️ Record a result"):
        mid = st.number_input("Match id", 1, 10**7, 1)
        w = st.selectbox("Winner", ["No result"] + list(team_map))
        m1, m2 = st.columns(2)
        margin = m1.number_input("Margin", 0, 1000, 0)
        vt = m2.selectbox("Margin type", ["runs", "wickets"])
        if st.button("Save result"):
            safe(lambda: svc.record_result(int(mid), None if w == "No result" else team_map[w], margin, vt),
                 "Result saved.")
    with st.expander("🗑️ Delete a match"):
        dmid = st.number_input("Match id to delete", 1, 10**7, 1, key="dm")
        if st.checkbox("Confirm delete", key="dmc") and st.button("Delete match"):
            safe(lambda: svc.delete_match(int(dmid)), "Match deleted.")
