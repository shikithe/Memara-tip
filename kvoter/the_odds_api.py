#!/usr/bin/env python3
"""The Odds API v4 adapter: history-h2h -> normalized bookmaker offers.
No API key means no requests and no fabricated odds.
"""
import argparse
import json
import os
import time
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request,urlopen
from kvoter import norm,utc,match,build

LEAGUES={
"eng.1":"soccer_epl","ger.1":"soccer_germany_bundesliga",
"esp.1":"soccer_spain_la_liga","ita.1":"soccer_italy_serie_a",
"fra.1":"soccer_france_ligue_one","ned.1":"soccer_netherlands_eredivisie",
"por.1":"soccer_portugal_primeira_liga","bel.1":"soccer_belgium_first_div",
"sco.1":"soccer_spl","tur.1":"soccer_turkey_super_league",
"bra.1":"soccer_brazil_campeonato","arg.1":"soccer_argentina_primera_division",
"usa.1":"soccer_usa_mls",
}
BASE="https://api.the-odds-api.com/v4"
def request(path,key,params,fetch=None):
    url=BASE+path+"?"+urlencode(dict(params,apiKey=key))
    if fetch: return fetch(url)
    req=Request(url,headers={"User-Agent":"MEMARASIX-Kvoter/1.0"})
    with urlopen(req,timeout=20) as response:
        return json.load(response)

def parse_bookmaker(event,bookmaker,league):
    home,away=event.get("home_team"),event.get("away_team")
    markets={}
    updates=[]
    for market in bookmaker.get("markets",[]):
        kind=market.get("key")
        if kind in ("h2h","h2h_3_way"):
            outcomes={}
            for x in market.get("outcomes",[]):
                name=x.get("name")
                key="home" if norm(name)==norm(home) else "away" if norm(name)==norm(away) else "draw" if norm(name)=="draw" else None
                if key: outcomes[key]=x.get("price")
            if outcomes: markets["1X2"]=outcomes
        elif kind in ("totals","alternate_totals"):
            for x in market.get("outcomes",[]):
                if norm(x.get("name"))!="over": continue
                try: point=float(x.get("point"))
                except (ValueError,TypeError): continue
                if point==1.5: markets["2+"]={"over":x.get("price")}
                if point==2.5: markets["3+"]={"over":x.get("price")}
        elif kind=="btts":
            outcomes={norm(x.get("name")):x.get("price") for x in market.get("outcomes",[]) if norm(x.get("name")) in ("yes","no")}
            if outcomes: markets["BTTS"]=outcomes
        if market.get("last_update"): updates.append(market["last_update"])
    return {"event_id":event.get("id"),"league":league,"home":home,"away":away,
            "start_utc":event.get("commence_time"),"bookmaker":bookmaker.get("key"),
            "updated_at_utc":max(updates) if updates else None,"markets":markets}

def collect(history,key,regions="uk,eu",fetch=None,delay=0):
    fixtures=history.get("fixtures",[])
    leagues=sorted({f.get("league") for f in fixtures if f.get("league") in LEAGUES})
    offers=[]; errors=[]; coverage={}
    for league in leagues:
        sport=LEAGUES[league]
        try:
            # Featured markets are fetched once per league; non-featured by event.
            events=request("/sports/"+sport+"/odds",key,
                           {"regions":regions,"markets":"h2h,totals","oddsFormat":"decimal"},fetch)
            if not isinstance(events,list): raise ValueError("Invalid API response")
            relevant=[e for e in events if any(match(f,{"league":league,"home":e.get("home_team"),"away":e.get("away_team"),"start_utc":e.get("commence_time")}) for f in fixtures if f.get("league")==league)]
            coverage[league]={"api_events":len(events),"matched_events":len(relevant)}
            for event in relevant:
                # Additional markets are charged per event. Request only events we actually match.
                detail=None
                try:
                    detail=request("/sports/"+sport+"/events/"+str(event["id"])+"/odds",key,
                                   {"regions":regions,"markets":"alternate_totals,btts","oddsFormat":"decimal"},fetch)
                except Exception as exc:
                    errors.append({"league":league,"event_id":event.get("id"),"stage":"additional_markets","error":str(exc)[:200]})
                combined={}
                for source in (event,detail):
                    if not isinstance(source,dict): continue
                    for book in source.get("bookmakers",[]):
                        bookkey=book.get("key")
                        if not bookkey: continue
                        combined.setdefault(bookkey,{"key":bookkey,"markets":[]})["markets"].extend(book.get("markets",[]))
                for book in combined.values():
                    offer=parse_bookmaker(event,book,league)
                    if offer["markets"]: offers.append(offer)
                if delay: time.sleep(delay)
        except Exception as exc:
            errors.append({"league":league,"stage":"featured_markets","error":str(exc)[:200]})
        if delay: time.sleep(delay)
    return offers,coverage,errors

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--feed",default="/shared/agent/history-h2h.json")
    p.add_argument("--output",default="/shared/kvoter/odds.json")
    p.add_argument("--regions",default="uk,eu")
    a=p.parse_args()
    history=json.loads(Path(a.feed).read_text(encoding="utf-8"))
    key=os.getenv("THE_ODDS_API_KEY","").strip()
    if key:
        offers,coverage,errors=collect(history,key,a.regions,delay=0.2)
        status="api_fetched"
    else:
        offers,coverage,errors=[],{},[{"stage":"configuration","error":"THE_ODDS_API_KEY not configured"}]
        status="missing_api_key"
    result=build(history,offers,source="the-odds-api-v4")
    result["provider_status"]=status
    result["provider_coverage"]=coverage
    result["provider_errors"]=errors
    result["requested_markets"]=["1X2","2+","3+","BTTS"]
    result["supported_leagues"]=LEAGUES
    out=Path(a.output);out.parent.mkdir(parents=True,exist_ok=True)
    temp=out.with_suffix(".tmp")
    temp.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    os.replace(temp,out)
    print("KVOTER",json.dumps({"total":result["total"],"matched":result["matched"],"provider_status":status,"errors":len(errors)}))
if __name__=="__main__":main()
