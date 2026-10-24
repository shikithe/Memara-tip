#!/usr/bin/env python3
"""Free best-effort NBA boxscore stats from unofficial public ESPN endpoints.

No BALLDONTLIE subscription or key. Bounded requests; observed past box scores
only. Never modifies bank, odds, or published tickets.
"""
import argparse, json, os, time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

BASE="https://site.api.espn.com/apis/site/v2/sports/basketball/nba"

def fetch(url):
    with urlopen(Request(url,headers={"Accept":"application/json","User-Agent":"MemaraSix-Research/1.0"}),timeout=20) as r:
        return json.load(r)

def parse_game(summary, event, day):
    rows=[]
    for group in (summary.get("boxscore") or {}).get("players",[]):
        team=(group.get("team") or {}).get("displayName")
        for section in group.get("statistics",[]):
            keys=[str(x).lower() for x in section.get("keys",[])]
            labels=[str(x).lower() for x in section.get("labels",[])]
            pts_idx=next((i for i,x in enumerate(keys) if x in ("points","pts")),None)
            if pts_idx is None: pts_idx=next((i for i,x in enumerate(labels) if x in ("pts","points")),None)
            min_idx=next((i for i,x in enumerate(keys) if x in ("minutes","min")),None)
            if min_idx is None: min_idx=next((i for i,x in enumerate(labels) if x=="min"),None)
            for item in section.get("athletes",[]):
                athlete=item.get("athlete") or {}
                vals=item.get("stats") or []
                try:
                    pts=int(float(vals[pts_idx]))
                    mins=str(vals[min_idx]) if min_idx is not None else None
                except (IndexError,ValueError,TypeError):
                    continue
                if not athlete.get("id") or not athlete.get("displayName"):continue
                rows.append({"player_id":str(athlete["id"]),"player":athlete["displayName"],
                    "team":team,"points":pts,"minutes":mins,"game_id":str(event),
                    "game_date":day})
    return rows

def run(days, max_summaries, watch_file):
    today=datetime.now(timezone.utc)
    watched=json.loads(Path(watch_file).read_text(encoding="utf-8")).get("players",[])
    names={p["name"].lower():p["name"] for p in watched}
    result={"date_utc":today.date().isoformat(),"generated_at_utc":today.isoformat(),
        "provider":"espn-public-unofficial","no_api_key_required":True,
        "limitations":"Unofficial, incomplete and not guaranteed. Historical boxscores only, no injuries or future projections.",
        "status":"ok","requested_summaries":0,"errors":[],"players":[]}
    events=[]
    for age in range(1,days+1):
        day=(today-timedelta(days=age)).strftime("%Y%m%d")
        try:
            doc=fetch(BASE+"/scoreboard?dates="+day)
            for e in doc.get("events",[]):
                state=((e.get("status") or {}).get("type") or {}).get("state")
                if state=="post" and str(e.get("id","")).isdigit():
                    events.append((str(e["id"]),day))
        except (HTTPError,URLError,ValueError,TypeError):
            result["errors"].append("Scoreboard unavailable for "+day)
    # Recent games first, bounded to avoid hammering unofficial endpoints.
    events=list(dict.fromkeys(events))
    history={}
    for event,day in events[:max_summaries]:
        try:
            summary=fetch(BASE+"/summary?event="+event)
            result["requested_summaries"]+=1
            for r in parse_game(summary,event,day):
                key=r["player"].lower()
                if key in names:
                    history.setdefault(key,[]).append(r)
        except (HTTPError,URLError,ValueError,TypeError):
            result["errors"].append("Boxscore unavailable for event "+event)
        time.sleep(.15)
    for key,name in names.items():
        games=history.get(key,[])
        result["players"].append({"player":name,"recent_games":games,
            "games_found":len(games),
            "average_points":round(sum(g["points"] for g in games)/len(games),2) if games else None,
            "status":"historical_sample" if games else "insufficient_coverage",
            "not_a_projection":True})
    result["players_with_stats"]=sum(bool(p["games_found"]) for p in result["players"])
    if result["errors"] and not result["requested_summaries"]:
        result["status"]="source_unavailable"
    return result

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--days",type=int,default=5)
    p.add_argument("--max-summaries",type=int,default=24)
    p.add_argument("--watch",default="collector/nba_players_watchlist.json")
    p.add_argument("--output",default="collector-output/nba-free-statistics.json")
    a=p.parse_args()
    if a.days<1 or a.days>14 or a.max_summaries<1 or a.max_summaries>40:
        p.error("Invalid bounded sampling controls")
    d=run(a.days,a.max_summaries,a.watch)
    dest=Path(a.output);dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(d,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("NBA_FREE_STATS",json.dumps({"status":d["status"],"players_with_stats":d["players_with_stats"],
        "boxscores":d["requested_summaries"],"errors":len(d["errors"])}))
if __name__=="__main__":main()
