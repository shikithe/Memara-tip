#!/usr/bin/env python3
"""Clear the entire *active NBA offer* before fetching a fresh 24h list.

Only NBA collector/market/research snapshots are touched. Published tickets,
bank, archives, football data and approvals remain immutable.
Commit this cleared state BEFORE the network collector runs: a failed fetch
must never leave yesterday's NBA offers looking usable.
"""
import json
import argparse
import subprocess
from zoneinfo import ZoneInfo
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

def verify(root=Path("."), ref=None, stamp=None, now=None):
    """Require ALL five NBA source files to be empty on the same run stamp.

    When ref is provided, read from the fetched Git ref, not the working tree:
    the collector cannot begin until GitHub main has acknowledged the wipe.
    """
    now=now or datetime.now(timezone.utc)
    expected_date=now.astimezone(ZoneInfo("Europe/Sarajevo")).date()
    stamps=set()
    for name in ACTIVE_SNAPSHOTS:
        path=str(NBA_DIR/name)
        if ref:
            content=subprocess.check_output(["git","show",ref+":"+path],text=True)
        else:
            content=(Path(root)/path).read_text(encoding="utf-8")
        data=json.loads(content)
        if data.get("publication_allowed") is not False:
            raise ValueError(path+" is publishable")
        for key in ("games","players","offers","nba_player_candidates"):
            if data.get(key):
                raise ValueError(path+" still contains "+key)
        if data.get("status") not in (None,"awaiting_daily_refresh"):
            raise ValueError(path+" status is not cleared")
        if data.get("analysis_status") not in (None,"awaiting_daily_refresh","awaiting_valid_odds","not_run"):
            raise ValueError(path+" analysis not cleared")
        mark=str(data.get("cleared_at_utc") or "")
        if not mark: raise ValueError(path+" lacks cleared_at_utc")
        parsed=datetime.fromisoformat(mark.replace("Z","+00:00"))
        if parsed.tzinfo is None or parsed.astimezone(ZoneInfo("Europe/Sarajevo")).date()!=expected_date:
            raise ValueError(path+" cleanup timestamp is not today")
        stamps.add(mark)
    if len(stamps)!=1:
        raise ValueError("NBA files were not cleared in a single cleanup transaction")
    found=next(iter(stamps))
    if stamp and stamp!=found:
        raise ValueError("GitHub cleanup differs from this run's cleanup")
    return found

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--verify",action="store_true")
    p.add_argument("--ref",default=None)
    p.add_argument("--stamp",default=None)
    args=p.parse_args()
    if args.verify:
        print("NBA_CLEANUP_CONFIRMED",verify(ref=args.ref,stamp=args.stamp))
    else:
        for path in clear():print("NBA_PRECOLLECT_CLEAR",path)

if __name__=="__main__": main()

