#!/usr/bin/env python3
"""Independent A/B readiness report. No NBA dependency, no bets or bank writes."""
import json
from pathlib import Path
from datetime import datetime,timezone,timedelta
from zoneinfo import ZoneInfo
OUT=Path("collector-output/ab-readiness.json")
def main():
    now=datetime.now(timezone.utc); today=now.astimezone(ZoneInfo("Europe/Sarajevo")).date().isoformat()
    reasons=[]; fixtures=[]
    try:
        feed=json.loads(Path("collector-feed.json").read_text())
        stamp=datetime.fromisoformat(feed["generated_at_utc"].replace("Z","+00:00"))
        if feed.get("date")!=today: reasons.append("feed_not_today")
        if stamp>now+timedelta(minutes=5) or now-stamp>timedelta(hours=6):reasons.append("feed_stale")
        fixtures=[f for f in feed.get("football_candidates",[]) if f.get("status")=="pre" and f.get("home") and f.get("away") and datetime.fromisoformat(f["start_utc"].replace("Z","+00:00"))>now+timedelta(minutes=10)]
        if len(fixtures)<4:reasons.append("fewer_than_four_future_football_matches")
    except (OSError,ValueError,KeyError,TypeError,AttributeError):
        reasons.append("missing_or_invalid_collector_feed")
    # A/B may proceed without NBA or C; this report is not independent verification of bookmaker odds.
    reasons.append("verified_current_1x2_and_over25_odds_and_team_evidence_required")
    result={"date":today,"generated_at_utc":now.isoformat(),"module":"football_A_B_only","nba_dependency":False,"c_dependency":False,"candidate_count":len(fixtures),"publication_allowed":False,"reasons":reasons,"bank_modified":False}
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps(result,ensure_ascii=False))
if __name__=="__main__":main()
