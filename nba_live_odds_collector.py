"""Fetch fresh NBA player-points odds; never reuse old offers as fresh."""
import datetime as dt,json,os,urllib.parse,urllib.request
from pathlib import Path
from zoneinfo import ZoneInfo
ZONE=ZoneInfo("Europe/Sarajevo")
ROOT="https://api.the-odds-api.com/v4"
def get(url):
    req=urllib.request.Request(url,headers={"User-Agent":"MEMARA-NBA/1.0","Accept":"application/json"})
    with urllib.request.urlopen(req,timeout=30) as r:return json.load(r)
def run(fetch=get,now=None):
    key=os.environ.get("ODDS_API_KEY")
    if not key:raise RuntimeError("ODDS_API_KEY secret missing; cannot fetch live odds")
    now=now or dt.datetime.now(dt.timezone.utc)
    today=now.astimezone(ZONE).date()
    def api(path,params):
        return fetch(ROOT+path+"?"+urllib.parse.urlencode(dict(params,apiKey=key)))
    events=api("/sports/basketball_nba/events",{})
    # ESPN team roster names to player IDs, using today's scoreboard
    espn={}
    for day in (today,today+dt.timedelta(days=1)):
        scoreboard=fetch("https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates="+day.strftime("%Y%m%d")+"&limit=100")
        for game in scoreboard.get("events",[]):
            for comp in game.get("competitions",[]):
                for side in comp.get("competitors",[]):
                    team=side.get("team",{})
                    tid=team.get("id")
                    if not tid:continue
                    try:
                        roster=fetch(f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/{tid}/roster?season={today.year+1 if today.month>=7 else today.year}")
                        for group in roster.get("athletes",[]):
                            athletes=group.get("items",[]) if isinstance(group,dict) else []
                            for athlete in athletes:
                                if athlete.get("id") and athlete.get("displayName"):
                                    espn[athlete["displayName"].casefold()]=str(athlete["id"])
                    except Exception:continue
    offers=[];errors=[]
    for event in events:
        start=event.get("commence_time","")
        try:
            if dt.datetime.fromisoformat(start.replace("Z","+00:00")).astimezone(ZONE).date()!=today:continue
        except ValueError:continue
        try:
            odds=api(f"/sports/basketball_nba/events/{event['id']}/odds",{"regions":"us","markets":"player_points","oddsFormat":"decimal"})
            for book in odds.get("bookmakers",[]):
                for market in book.get("markets",[]):
                    if market.get("key")!="player_points":continue
                    grouped={}
                    for outcome in market.get("outcomes",[]):
                        name=outcome.get("description")
                        if not name:continue
                        line=outcome.get("point")
                        if line is None:continue
                        pair=grouped.setdefault((name,float(line)),{})
                        if outcome.get("name") in ("Over","Under"):pair[outcome["name"]]=outcome.get("price")
                    for (name,line),prices in grouped.items():
                        pid=espn.get(name.casefold())
                        if not pid:
                            errors.append({"player":name,"reason":"ESPN player ID not resolved"})
                            continue
                        offers.append({"player_id":pid,"player":name,"team":None,"opponent":None,"espn_event_id":None,"odds_event_id":event["id"],"start_utc":start,"points_line":line,"over_odds":prices.get("Over"),"under_odds":prices.get("Under"),"bookmaker":book.get("title"),"bookmaker_key":book.get("key"),"last_update":market.get("last_update"),"source":"the-odds-api.com","status":"unanalysed"})
        except Exception as exc:errors.append({"event":event.get("id"),"reason":str(exc)[:200]})
    if not offers:raise RuntimeError("No fresh player-points offers resolved; refusing empty/stale snapshot")
    result={"generated_at_utc":now.isoformat(),"region":"us","offer_count":len(offers),"offers":offers,"errors":errors,"date":today.isoformat()}
    path=Path("collector-output/nba-player-points.json")
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps({"date":str(today),"offers":len(offers),"unique_players":len(set(o["player_id"] for o in offers)),"errors":len(errors)}))
    return result
if __name__=="__main__":run()
