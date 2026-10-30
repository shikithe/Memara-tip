#!/usr/bin/env python3
"""Read-only cross-competition ESPN history and H2H test. Never publishes."""
import argparse
import json
from datetime import datetime,timedelta,timezone
from pathlib import Path
from urllib.parse import urlencode
from espn_statistics import fetch,extract_summary,LEAGUES

ROOT="https://site.api.espn.com/apis/site/v2/sports/soccer"
def norm(s):
    return " ".join(str(s or "").casefold().split())
def participants(e):
    try:
        return [c["team"].get("displayName","") for c in e["competitions"][0]["competitors"]]
    except (KeyError,IndexError,TypeError):
        return []
def final_score(event):
    """Preserve ESPN's home/away final score; never guess unavailable scores."""
    try:
        competitors = event["competitions"][0]["competitors"]
        home = next(c for c in competitors if c.get("homeAway") == "home")
        away = next(c for c in competitors if c.get("homeAway") == "away")
    except (KeyError, IndexError, TypeError, StopIteration):
        return {"home": None, "away": None, "display": None, "available": False}
    def value(c):
        score = c.get("score")
        if isinstance(score, dict):
            score = score.get("displayValue", score.get("value"))
        if score is None or str(score).strip() == "":
            return None
        return str(score)
    hs, aw = value(home), value(away)
    available = hs is not None and aw is not None
    return {"home": hs, "away": aw,
            "display": f"{hs}:{aw}" if available else None,
            "available": available}

def standings_rows(doc):
    """Normalize ESPN standings, including leagues with nested group tables."""
    rows = []
    def walk(node):
        if isinstance(node, dict):
            standings = node.get("standings")
            if isinstance(standings, dict) and isinstance(standings.get("entries"), list):
                for entry in standings["entries"]:
                    team = entry.get("team") or {}
                    stats = {}
                    for stat in entry.get("stats") or []:
                        key = stat.get("name") or stat.get("abbreviation")
                        if key:
                            stats[key] = stat.get("value", stat.get("displayValue"))
                    rows.append({"team_id":str(team.get("id") or ""),
                                 "team":team.get("displayName") or team.get("name"),
                                 "abbreviation":team.get("abbreviation"),
                                 "statistics":stats})
            for key,value in node.items():
                if key != "standings":
                    walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)
    walk(doc)
    return rows

def select(feed,request=fetch,days=30,limit=5,leagues=LEAGUES,now=None,h2h_years=3):
    now=now or datetime.now(timezone.utc)
    pairs=[f for f in feed.get("football_candidates",[]) if f.get("status")=="pre" and f.get("sport")=="football" and f.get("home") and f.get("away")]
    names={norm(n) for f in pairs for n in (f["home"],f["away"])}
    errors=[];events={};source_leagues=set(leagues)
    source_leagues.update(f["league"] for f in pairs if f.get("league"))
    # ESPN league endpoints are independent. Scan all configured competitions,
    # retain only matches involving today's teams, dedupe by event ID.
    for league in sorted(source_leagues):
        for offset in range(1,days+1):
            date=(now-timedelta(days=offset)).strftime("%Y%m%d")
            url=f"{ROOT}/{league}/scoreboard?"+urlencode({"dates":date,"limit":500})
            try:
                doc=request(url)
                for e in doc.get("events",[]):
                    if (e.get("status") or {}).get("type",{}).get("state")!="post":
                        continue
                    if not ({norm(n) for n in participants(e)} & names):
                        continue
                    event_id=str(e.get("id") or "")
                    if event_id:
                        events.setdefault(event_id,{"event":e,"league":league})
            except Exception as exc:
                errors.append({"league":league,"date":date,"error":str(exc)})
    # H2H is independent of the 30-day team-form window.
    # ESPN scoreboard supports league-specific season requests, but completeness
    # varies; inspect the returned events and never invent missing meetings.
    h2h_events=dict(events)
    active_leagues={f.get("league") for f in pairs if f.get("league")}
    active_leagues.update(l for l in source_leagues if l.startswith("uefa."))
    oldest=now-timedelta(days=365*h2h_years+1)
    for league in sorted(active_leagues):
        for year in range(oldest.year,now.year+1):
            url=f"{ROOT}/{league}/scoreboard?"+urlencode({"dates":str(year),"limit":500})
            try:
                doc=request(url)
                for e in doc.get("events",[]):
                    if (e.get("status") or {}).get("type",{}).get("state")!="post":
                        continue
                    try:
                        when=datetime.fromisoformat(e["date"].replace("Z","+00:00"))
                    except (ValueError,KeyError,TypeError):
                        continue
                    if not oldest<=when<=now:
                        continue
                    teams={norm(n) for n in participants(e)}
                    if not any({norm(f["home"]),norm(f["away"])}.issubset(teams) for f in pairs):
                        continue
                    event_id=str(e.get("id") or "")
                    if event_id:
                        h2h_events.setdefault(event_id,{"event":e,"league":league})
            except Exception as exc:
                errors.append({"league":league,"season":year,"error":str(exc)})
    # Fetch standings once per league, independently of historical match requests.
    league_standings={}
    for league in sorted({f.get("league") for f in pairs if f.get("league")}):
        url=f"https://site.api.espn.com/apis/v2/sports/soccer/{league}/standings"
        try:
            league_standings[league]=standings_rows(request(url))
        except Exception as exc:
            league_standings[league]=[]
            errors.append({"league":league,"source":"standings","error":str(exc)})
    def team_standing(league,name):
        return next((entry for entry in league_standings.get(league,[])
                     if norm(entry.get("team"))==norm(name)),None)
    summaries={}
    def row(item):
        e=item["event"];event_id=str(e["id"])
        if event_id not in summaries:
            url=f"{ROOT}/{item['league']}/summary?"+urlencode({"event":event_id})
            try:
                summaries[event_id]=extract_summary(request(url))
            except Exception as exc:
                errors.append({"league":item["league"],"event_id":event_id,"error":str(exc)})
                summaries[event_id]={"available":False,"team_statistics":[]}
        return {"event_id":event_id,"date":e.get("date"),"competition":item["league"],
                "participants":participants(e),"final_score":final_score(e),"statistics":summaries[event_id]}
    result=[]
    for f in pairs:
        home,away=norm(f["home"]),norm(f["away"])
        ranked=sorted(events.values(),key=lambda v:v["event"].get("date",""),reverse=True)
        def involving(team):
            return [x for x in ranked if team in {norm(n) for n in participants(x["event"])}][:limit]
        h2h=[x for x in sorted(h2h_events.values(),key=lambda v:v["event"].get("date",""),reverse=True) if {home,away}.issubset({norm(n) for n in participants(x["event"])})][:limit]
        result.append({"fixture_id":f.get("id"),"home":f["home"],"away":f["away"],
                       "home_history":[row(x) for x in involving(home)],
                       "away_history":[row(x) for x in involving(away)],
                       "h2h":[row(x) for x in h2h],
                       "target_per_group":limit,
                       "start_utc":f.get("start_utc"),"start_sarajevo":f.get("start_sarajevo"),
                       "league":f.get("league"),
                       "home_standing":team_standing(f.get("league"),f["home"]),
                       "away_standing":team_standing(f.get("league"),f["away"])})
    return {"schema_version":"agent-cross-competition-v1","generated_at_utc":now.isoformat(),
            "scan_days":days,"h2h_years":h2h_years,"h2h_lookup":"ESPN season scoreboard best-effort; may be incomplete","scanned_leagues":sorted(source_leagues),
            "scope_note":"ESPN-recorded matches in configured competitions only; cups outside these endpoints may be absent.",
            "league_standings":league_standings,"fixtures":result,"errors":errors,"publication_allowed":False,"bank_modified":False}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--input",required=True);p.add_argument("--output",required=True)
    p.add_argument("--days",type=int,default=30)
    p.add_argument("--h2h-years",type=int,default=3)
    args=p.parse_args()
    if not 1<=args.days<=365: p.error("days must be 1..365")
    if not 1<=args.h2h_years<=10: p.error("h2h-years must be 1..10")
    result=select(json.loads(Path(args.input).read_text(encoding="utf-8")),days=args.days,h2h_years=args.h2h_years)
    out=Path(args.output);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    for x in result["fixtures"]:
        print(x["home"],"-",x["away"],"home=",len(x["home_history"]),"away=",len(x["away_history"]),"h2h=",len(x["h2h"]))
    print("ERRORS",len(result["errors"]))
if __name__=="__main__":main()
