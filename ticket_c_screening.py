#!/usr/bin/env python3
"""Research-only C ticket candidate screening; never publishes or stakes."""
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT=Path("collector-output")
def load(name):
    p=ROOT/name
    return json.loads(p.read_text()) if p.exists() else {}
def main():
    now=datetime.now(timezone.utc)
    today=now.astimezone(ZoneInfo("Europe/Sarajevo")).date().isoformat()
    odds=load("nba-player-points.json")
    stats=load("nba-free-statistics.json")
    feed=json.loads(Path("collector-feed.json").read_text())
    by_id={str(p.get("player_id")):p for p in stats.get("players",[])}
    candidates=[]
    for o in odds.get("offers",[]):
        try:
            start=datetime.fromisoformat(o["start_utc"].replace("Z","+00:00"))
            updated=datetime.fromisoformat(o["last_update"].replace("Z","+00:00"))
            over=float(o["over_odds"]);under=float(o["under_odds"])
            if start<=now or start>now+timedelta(hours=24):continue
            if updated>now+timedelta(minutes=5):continue
            odds_revalidation_required=(now-updated).total_seconds()>3*3600
            if not (1.75<=over<=1.90 or 1.75<=under<=1.90):continue
            p=by_id.get(str(o.get("player_id")),{})
            n=len(p.get("recent_games",[]))
            if n<5:continue
            candidates.append({"player":o["player"],"game":o.get("espn_event_id"),"line":o["points_line"],"over_odds":over,"under_odds":under,"bookmaker":o.get("bookmaker"),"sample_games":n,"historical_average":p.get("average_points"),"start_utc":o["start_utc"],"status":"needs_odds_revalidation_and_injury_minutes_market_verification" if odds_revalidation_required else "needs_injury_minutes_and_market_verification","odds_revalidation_required":odds_revalidation_required})
        except (KeyError,ValueError,TypeError):continue
    candidates.sort(key=lambda x:(-x["sample_games"],x["player"]))
    out={"date":today,"generated_at_utc":now.isoformat(),"state":"research_only","publication_allowed":False,"football_candidates":len(feed.get("football_candidates",[])) if feed.get("date")==today else 0,"nba_player_candidates":candidates[:30],"count":len(candidates),"warnings":["Foreign bookmaker odds are not Mozzart BiH odds","Injuries, minutes, opponent defense and market availability require independent confirmation","No automatic ticket C publication or bank changes"]}
    ROOT.mkdir(exist_ok=True)
    (ROOT/"ticket-c-research.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
    print("C candidates",len(candidates))
if __name__=="__main__":main()
