#!/usr/bin/env python3
"""Clear the entire *active NBA offer* before fetching a fresh 24h list.

Only NBA collector/market/research snapshots are touched. Published tickets,
bank, archives, football data and approvals remain immutable.
Commit this cleared state BEFORE the network collector runs: a failed fetch
must never leave yesterday's NBA offers looking usable.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

NBA_DIR=Path("collector-output")
ACTIVE_SNAPSHOTS=(
    "nba-next-24h.json",
    "nba-player-points.json",
    "nba-analysis-ready.json",
    "ticket-c-research.json",
    "nba-free-statistics.json",
)

def clear(root=Path("."), now=None):
    now=now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("Timezone-aware timestamp required")
    stamp=now.astimezone(timezone.utc).isoformat()
    states={
        "nba-next-24h.json":{
            "schema_version":"1.0","source":"espn-public-unofficial",
            "collected_at_utc":None,"window_start_utc":None,"window_end_utc":None,
            "timezone_display":"Europe/Sarajevo","games":[],"players":[],
            "game_count":0,"player_candidate_count":0,"limitations":[],
            "status":"awaiting_daily_refresh","errors":[],"publication_allowed":False,
            "cleared_at_utc":stamp
        },
        "nba-player-points.json":{
            "generated_at_utc":None,"fixture_snapshot_utc":None,
            "region":"us","offer_count":0,"offers":[],
            "status":"awaiting_daily_refresh","analysis_status":"not_run",
            "publication_allowed":False,"cleared_at_utc":stamp
        },
        "nba-analysis-ready.json":{
            "schema_version":"1.0","generated_at_utc":stamp,
            "fixture_snapshot_utc":None,"odds_snapshot_utc":None,
            "game_count":0,"player_candidate_count":0,"matched_offer_count":0,
            "offers":[],"odds_status":"awaiting_daily_refresh",
            "analysis_status":"awaiting_valid_odds","publication_allowed":False,
            "cleared_at_utc":stamp
        },
        "ticket-c-research.json":{
            "generated_at_utc":stamp,"state":"awaiting_daily_refresh",
            "publication_allowed":False,"nba_player_candidates":[],
            "count":0,"cleared_at_utc":stamp
        },
        "nba-free-statistics.json":{
            "generated_at_utc":stamp,"status":"awaiting_daily_refresh",
            "players":[],"errors":[],"target_player_count":0,
            "publication_allowed":False,"cleared_at_utc":stamp
        }
    }
    directory=Path(root)/NBA_DIR
    directory.mkdir(parents=True,exist_ok=True)
    for name in ACTIVE_SNAPSHOTS:
        target=directory/name
        target.write_text(json.dumps(states[name],ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return [str(NBA_DIR/name) for name in ACTIVE_SNAPSHOTS]

if __name__=="__main__":
    for path in clear():print("NBA_PRECOLLECT_CLEAR",path)
