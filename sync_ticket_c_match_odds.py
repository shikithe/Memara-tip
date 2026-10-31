#!/usr/bin/env python3
"""Fetch match odds for upcoming ESPN fixtures; research-only, never publishes."""
import argparse,json,os,unicodedata
from datetime import datetime,timezone,timedelta
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request,urlopen
from urllib.error import HTTPError,URLError

BASE="https://api.the-odds-api.com/v4"
def norm(s):
    s=unicodedata.normalize("NFKD",str(s)).encode("ascii","ignore").decode().lower()
    return " ".join(s.replace(".","").replace("-"," ").split())
def stamp(s):
    d=datetime.fromisoformat(str(s).replace("Z","+00:00"))
    if d.tzinfo is None: raise ValueError("timezone required")
    return d.astimezone(timezone.utc)
def get(path,params,key):
    req=Request(BASE+path+"?"+urlencode(params),headers={"x-api-key":key,"Accept":"application/json"})
    with urlopen(req,timeout=30) as r:return json.load(r)
def collect(feed,key,region="eu",max_soccer=None,now=None):
    now=now or datetime.now(timezone.utc)
    fixtures=[]
    for sport,rows in (("football",feed.get("football_candidates",[])),("basketball",feed.get("nba_games",[]))):
        for f in rows:
            try:
                if now<stamp(f["start_utc"])<=now+timedelta(hours=24) and f.get("status")=="pre":
                    fixtures.append((sport,f))
            except (ValueError,KeyError,TypeError):pass
    sports=get("/sports",{},key)
    soccer=[s["key"] for s in sports if s.get("active") and s.get("key","").startswith("soccer_")]
    keys=((soccer if max_soccer is None else soccer[:max_soccer]) if any(s=="football" for s,_ in fixtures) else [])
    if any(s=="basketball" for s,_ in fixtures):keys+=["basketball_nba"]
    offers=[];errors=[];matched=set()
    for sport_key in keys:
        try:
            events=get("/sports/"+sport_key+"/odds",{"regions":region,"markets":"h2h,totals" if sport_key=="basketball_nba" else "totals","oddsFormat":"decimal"},key)
        except (HTTPError,URLError,ValueError) as e:
            errors.append({"sport_key":sport_key,"error":type(e).__name__});continue
        for event in events:
            try:
                start=stamp(event["commence_time"])
                match=[(s,f) for s,f in fixtures if
                       (s=="basketball")==(sport_key=="basketball_nba") and
                       norm(f["home"])==norm(event["home_team"]) and norm(f["away"])==norm(event["away_team"]) and
                       abs((stamp(f["start_utc"])-start).total_seconds())<=3600]
                if len(match)!=1:continue
                sport,fixture=match[0];matched.add(fixture["id"])
                for book in event.get("bookmakers",[]):
                    for market in book.get("markets",[]):
                        updated=market.get("last_update") or book.get("last_update")
                        if not now-timedelta(hours=3)<=stamp(updated)<=now+timedelta(minutes=5):continue
                        for o in market.get("outcomes",[]):
                            name=str(o.get("name",""));point=o.get("point")
                            if sport=="football":
                                if market.get("key")!="totals" or name.lower()!="over" or point not in (1.5,2.5):continue
                                m="goals_2_plus" if point==1.5 else "goals_3_plus"
                            elif market.get("key")=="h2h" and norm(name) in (norm(fixture["home"]),norm(fixture["away"])):
                                m="winner"
                            elif market.get("key")=="totals" and name.lower() in ("over","under") and point is not None:
                                m="total_"+name.lower()
                            else:continue
                            price=float(o["price"])
                            if not 1<price<1000:continue
                            offers.append({"sport":sport,"market":m,"event_id":fixture["id"],"selection":name+(" "+str(point) if point is not None else ""),"odds":price,"start_utc":start.isoformat(),"odds_last_update":updated,"source":"the-odds-api.com","bookmaker":book.get("title"),"verified":True,"independent_event_check":True,"analysis_verified":False,"estimated_edge":None})
            except (ValueError,KeyError,TypeError):continue
    return {"state":"research_only","publication_allowed":False,"generated_at_utc":now.isoformat(),"region":region,"offers":offers,"count":len(offers),"matched_fixtures":len(matched),"queried_sports":keys,"errors":errors,"note":"Unanalysed odds, bookmaker availability in BiH not confirmed"}
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--feed",default="collector-feed.json")
    p.add_argument("--output",default="collector-output/match-odds-snapshot.json")
    p.add_argument("--region",choices=["eu","us","uk","au"],default="eu")
    p.add_argument("--max-soccer",type=int,default=None,help="Optional API budget cap; default checks every active soccer league")
    a=p.parse_args()
    key=os.environ.get("THE_ODDS_API_KEY")
    if not key:p.error("THE_ODDS_API_KEY secret missing")
    data=collect(json.loads(Path(a.feed).read_text()),key,a.region,a.max_soccer)
    dest=Path(a.output);dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n")
    print("Match odds",data["count"],"matched fixtures",data["matched_fixtures"],"errors",len(data["errors"]))
if __name__=="__main__":main()
