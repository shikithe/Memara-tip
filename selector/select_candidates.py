#!/usr/bin/env python3
"""Independent, read-only fixture selector. No picks, bets, odds or bank writes."""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

def select(feed):
    football = feed.get("football_candidates", [])
    nba = feed.get("nba_games", [])
    if not isinstance(football,list) or not isinstance(nba,list):
        raise ValueError("Invalid feed candidate lists")
    seen=set()
    candidates=[]
    for fixture in football+nba:
        if not isinstance(fixture,dict) or fixture.get("status")!="pre":
            continue
        fixture_id=fixture.get("id")
        if not fixture_id or fixture_id in seen:
            continue
        seen.add(fixture_id)
        # Fixture schedule alone does not support a statistically grounded prediction.
        # All matches remain available; missing analytical evidence is explicitly flagged.
        candidates.append({
            "id":fixture_id,
            "sport":fixture.get("sport"),
            "league":fixture.get("league"),
            "home":fixture.get("home"),
            "away":fixture.get("away"),
            "start_utc":fixture.get("start_utc"),
            "stage":"requires_statistics",
            "selection_status":"unrated",
            "missing_inputs":["recent_form","home_away_splits","expected_goals_or_efficiency",
                              "injuries_and_lineups","verified_market_odds"],
            "eligible_for_publication":False
        })
    candidates.sort(key=lambda f:(f.get("start_utc") or "",f["id"]))
    return {
        "schema_version":"selector-v1",
        "feed_date":feed.get("date"),
        "generated_at_utc":datetime.now(timezone.utc).isoformat(),
        "source_status":feed.get("source_status"),
        "input_count":len(football)+len(nba),
        "candidate_count":len(candidates),
        "rejected_duplicate_or_invalid_count":len(football)+len(nba)-len(candidates),
        "selection_mode":"preserve_all_until_evidence",
        "tickets_published":False,
        "bank_modified":False,
        "candidates":candidates
    }

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--input",required=True)
    p.add_argument("--output",required=True)
    a=p.parse_args()
    result=select(json.loads(Path(a.input).read_text(encoding="utf-8")))
    target=Path(a.output)
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"input":result["input_count"],"candidates":result["candidate_count"],"mode":result["selection_mode"]}))
if __name__=="__main__":
    main()
