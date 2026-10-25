#!/usr/bin/env python3
"""MemaraSix optional stats collectors. No betting selections, odds or bank edits.

Secrets: API_FOOTBALL_KEY, BALLDONTLIE_API_KEY; supplied only through Actions.
Rate-limited, strictly bounded calls; historical stats are not pregame forecasts.
"""
import argparse
import json
import os
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

FOOTBALL = "https://v3.football.api-sports.io"
NBA = "https://api.balldontlie.io/v1"

def get(url, headers):
    req = Request(url, headers={**headers, "Accept":"application/json", "User-Agent":"MemaraSix-stats/1.0"})
    with urlopen(req, timeout=25) as response:
        return json.load(response)

def norm(s):
    return " ".join(unicodedata.normalize("NFKD", str(s)).encode("ascii","ignore").decode().lower().split())

def football(date, key, limit=40):
    """One date fixtures query; optionally up to 2 team stats queries per match."""
    doc = get(FOOTBALL+"/fixtures?"+urlencode({"date":date}), {"x-apisports-key":key})
    matches=[]
    for game in doc.get("response", []):
        status = ((game.get("fixture") or {}).get("status") or {}).get("short")
        if status not in ("NS","TBD"):
            continue
        league = game.get("league") or {}
        teams = game.get("teams") or {}
        home, away = teams.get("home") or {}, teams.get("away") or {}
        if not all((league.get("id"),league.get("season"),home.get("id"),away.get("id"))):continue
        matches.append({"fixture_id":game["fixture"]["id"],"league_id":league["id"],"league_name":league.get("name"),
                        "season":league["season"],"start_utc":game["fixture"].get("date"),
                        "home_team_id":home["id"],"away_team_id":away["id"],
                        "home":home.get("name"),"away":away.get("name")})
    # Prefer fixtures already discovered by the collector, if IDs/names align.
    try:
        feed=json.loads(Path("collector-feed.json").read_text(encoding="utf-8"))
        if feed.get("date")==date:
            wanted_ids={str(x.get("id")) for x in feed.get("football_candidates",[]) if x.get("id")}
            wanted_names={(norm(x.get("home")),norm(x.get("away"))) for x in feed.get("football_candidates",[])}
            matches.sort(key=lambda x:(
                not (str(x["fixture_id"]) in wanted_ids or (norm(x["home"]),norm(x["away"])) in wanted_names),
                x.get("start_utc") or ""))
    except (OSError,ValueError,TypeError):
        pass
    matches=matches[:limit]
    for item in matches:
        for side in ("home","away"):
            try:
                stats=get(FOOTBALL+"/teams/statistics?"+urlencode({
                    "league":item["league_id"],"season":item["season"],
                    "team":item[side+"_team_id"],"date":date}),
                    {"x-apisports-key":key}).get("response") or {}
                goals=stats.get("goals") or {}
                fixtures=stats.get("fixtures") or {}
                item[side+"_stats"]={"played":((fixtures.get("played") or {}).get("total")),
                    "goals_for_avg":((goals.get("for") or {}).get("average") or {}).get("total"),
                    "goals_against_avg":((goals.get("against") or {}).get("average") or {}).get("total"),
                    "form":stats.get("form"),"source":"API-Football"}
            except (HTTPError,URLError,ValueError,KeyError,TypeError):
                item[side+"_stats"]={"status":"unavailable"}
    return {"status":"ok","scope":"bounded free-tier research; collector candidates prioritized",
            "fixture_count":len(matches),"fixtures":matches,"source":"API-Football",
            "is_model_prediction":False}

def nba_players(names, key, season, limit=4):
    """Resolve player IDs, get recent completed-game stats with limited calls."""
    result=[]
    for name in names[:limit]:
        player_result={"requested_name":name,"status":"unavailable"}
        try:
            response=get(NBA+"/players?"+urlencode({"search":name.split()[-1],"per_page":50}),
                         {"Authorization":key}).get("data",[])
            exact=[p for p in response if norm(p.get("first_name","")+" "+p.get("last_name",""))==norm(name)]
            if len(exact)!=1:
                player_result["reason"]="player id ambiguous or not found"
                result.append(player_result)
                continue
            p=exact[0]
            payload=get(NBA+"/stats?"+urlencode({"player_ids[]":p["id"],"seasons[]":season,"per_page":100}),
                        {"Authorization":key})
            rows=[]
            for item in payload.get("data",[]):
                game=item.get("game") or {}
                if game.get("status_state")!="final":continue
                if game.get("date") is None:continue
                rows.append({"date":game["date"],"points":item.get("pts"),
                             "minutes":item.get("min"),"game_id":game.get("id")})
            rows.sort(key=lambda x:x["date"],reverse=True)
            rows=rows[:10]
            values=[float(x["points"]) for x in rows if isinstance(x["points"],(int,float))]
            player_result={"requested_name":name,"player_id":p["id"],
                "player":p.get("first_name","")+" "+p.get("last_name",""),
                "status":"ok" if values else "no_stats",
                "sample_count":len(values),
                "points_last_10_avg":round(sum(values)/len(values),2) if values else None,
                "recent_games":rows,
                "source":"BALLDONTLIE","coverage_note":"First API page only; may omit latest games unless paginated. No projection."}
        except HTTPError as exc:
            player_result["reason"]="HTTP "+str(exc.code)+" (check account tier, limits or key)"
        except (URLError,KeyError,ValueError,TypeError):
            player_result["reason"]="API unavailable or malformed response"
        result.append(player_result)
    return {"status":"ok","season":season,"players":result,"source":"BALLDONTLIE",
            "is_model_prediction":False}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--date",required=True)
    p.add_argument("--output",default="collector-output/statistics-research.json")
    p.add_argument("--football-limit",type=int,default=40)
    p.add_argument("--nba-limit",type=int,default=4)
    a=p.parse_args()
    result={"date":a.date,"generated_at_utc":datetime.now(timezone.utc).isoformat(),
            "analysis_status":"data_only_not_predictions","football":{"status":"not_configured"},
            "nba":{"status":"not_configured"},"ticket_publication_allowed":False}
    football_key=os.environ.get("API_FOOTBALL_KEY")
    nba_key=os.environ.get("BALLDONTLIE_API_KEY")
    if football_key:
        try:result["football"]=football(a.date,football_key,max(0,min(a.football_limit,40)))
        except HTTPError as exc:result["football"]={"status":"http_error","code":exc.code}
        except (URLError,ValueError,TypeError,KeyError):result["football"]={"status":"source_error"}
    if nba_key:
        try:
            watch=json.loads(Path("collector/nba_players_watchlist.json").read_text(encoding="utf-8"))
            names=[row["name"] for row in watch.get("players",[]) if row.get("name")]
            season=int(a.date[:4]) if int(a.date[5:7])>=10 else int(a.date[:4])-1
            result["nba"]=nba_players(names,nba_key,season,max(0,min(a.nba_limit,6)))
        except (OSError,ValueError,TypeError,KeyError):result["nba"]={"status":"source_error"}
    dest=Path(a.output);dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("STATS_SYNC",json.dumps({"date":a.date,"football":result["football"].get("status"),
                                      "nba":result["nba"].get("status")}))
if __name__=="__main__":main()
