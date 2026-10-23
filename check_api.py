"""Run `python check_api.py` to test your RapidAPI key and see what Cricbuzz returns."""
import json
import sys

import config
from api.cricbuzz_client import ApiError, CricbuzzClient, parse_match_list

if not config.api_configured():
    sys.exit("No RAPIDAPI_KEY found. Put it in a file named .env (not .env.example) next to app.py.")

client = CricbuzzClient()
print(f"Key found (ends ...{config.RAPIDAPI_KEY[-4:]}), host: {config.RAPIDAPI_HOST}\n")
for name, call in [("live matches", client.live_matches), ("recent matches", client.recent_matches),
                   ("top stats (most runs)", client.top_stats)]:
    try:
        data = call()
    except ApiError as exc:
        print(f"[FAIL] {name}: {exc}")
        continue
    print(f"[OK]   {name}: top-level keys = {list(data)[:6]}")
    if "matches" in name:
        parsed = parse_match_list(data)
        print(f"       parsed {len(parsed)} match(es)", f"e.g. {parsed[0]['team1']} vs {parsed[0]['team2']}" if parsed else "")
        if not parsed:
            print("       raw sample:", json.dumps(data)[:300])
    else:
        print("       raw sample:", json.dumps(data)[:300])
