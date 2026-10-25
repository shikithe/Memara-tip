#!/usr/bin/env python3
"""Rate-limited TheSportsDB season research; never promotes betting candidates."""
import json,os,time,urllib.parse,urllib.request,urllib.error,argparse
from collections import defaultdict
from pathlib import Path
def norm(s):
 import re,unicodedata
 return " ".join(re.sub("[^a-z0-9]+"," ",unicodedata.normalize("NFKD",str(s or "")).encode("ascii","ignore").decode().lower()).split())
def main():
 p=argparse.ArgumentParser()
 p.add_argument("--input",default="collector-output/safe-fixtures.json")
 p.add_argument("--interval",type=float,default=5)
 p.add_argument("--max-calls",type=int,default=20)
 p.add_argument("--max-countries",type=int,default=8)
 p.add_argument("--max-seasons",type=int,default=4)
 a=p.parse_args()
 if a.interval<3 or not 1<=a.max_calls<=25:p.error("unsafe rate settings")
 fixtures=json.loads(Path(a.input).read_text())["football"]["fixtures"]
 countries=defaultdict(dict)
 for f in fixtures:
  if f.get("league_country") and f.get("league_id"):
   countries[f["league_country"]][f["league_id"]]={"name":f.get("league_name"),"season":f.get("season")}
 ordered=sorted(countries,key=lambda c:-sum(f.get("league_country")==c for f in fixtures))
 key=os.getenv("THESPORTSDB_API_KEY") or "123"
 report={"source":"TheSportsDB","mode":"read_only","results":[],"errors":[],"calls":0,"newly_covered":0,"publication_allowed":False}
 last=None
 def fetch(endpoint,params):
  nonlocal last
  for attempt in range(3):
   if report["calls"]>=a.max_calls:raise RuntimeError("budget_exhausted")
   if last is not None:time.sleep(max(0,a.interval-(time.monotonic()-last)))
   url="https://www.thesportsdb.com/api/v1/json/"+urllib.parse.quote(key,safe="")+"/"+endpoint+"?"+urllib.parse.urlencode(params)
   last=time.monotonic()
   report["calls"]+=1
   try:
    with urllib.request.urlopen(urllib.request.Request(url,headers={"User-Agent":"MemaraSix-Research/2.0"}),timeout=25) as response:return json.load(response)
   except urllib.error.HTTPError as exc:
    if exc.code==429 and attempt<2 and report["calls"]<a.max_calls:
     try:delay=max(60,min(180,int(exc.headers.get("Retry-After","65"))))
     except (TypeError,ValueError):delay=65
     print("RATE LIMITED; WAIT",delay,flush=True)
     time.sleep(delay)
     continue
    raise
  raise RuntimeError("retry_exhausted")
 seasons=0
 for country in ordered[:a.max_countries]:
  try:
   catalog=fetch("search_all_leagues.php",{"c":country,"s":"Soccer"}).get("countries") or []
  except (urllib.error.HTTPError,urllib.error.URLError,RuntimeError,ValueError) as exc:
   code=getattr(exc,"code",None)
   report["errors"].append({"country":country,"code":code,"type":type(exc).__name__})
   print("PROVIDER ERROR",country,code,flush=True)
   if code in (401,403,429) or isinstance(exc,RuntimeError):break
   continue
  for league_id,info in countries[country].items():
   matches=[x for x in catalog if norm(x.get("strLeague"))==norm(info["name"]) and norm(x.get("strCountry"))==norm(country)]
   item={"country":country,"api_football_id":league_id,"league":info["name"],"status":"unverified","candidates":len(matches)}
   if len(matches)==1:
    item["provider_league_id"]=matches[0].get("idLeague")
    item["status"]="exact_name_candidate"
    season=matches[0].get("strCurrentSeason")
    if season and item["provider_league_id"] and seasons<a.max_seasons:
     try:
      events=fetch("eventsseason.php",{"id":item["provider_league_id"],"s":season}).get("events") or []
      item.update(season=season,returned_events=len(events),completed_events=sum(e.get("intHomeScore") is not None and e.get("intAwayScore") is not None for e in events),status="season_data_unverified_completeness")
      seasons+=1
     except (urllib.error.HTTPError,urllib.error.URLError,RuntimeError,ValueError) as exc:
      item["season_error"]=str(exc)
   report["results"].append(item)
   print("LEAGUE",json.dumps(item,ensure_ascii=False),flush=True)
 report["season_queries"]=seasons
 report["status"]="partial_with_provider_errors" if report["errors"] else "research_complete"
 dest=Path("collector-output/thesportsdb-safe-stats.json")
 dest.parent.mkdir(parents=True,exist_ok=True)
 dest.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
 print("SAFE STATS SUMMARY",json.dumps({"calls":report["calls"],"seasons":seasons,"leagues":len(report["results"]),"errors":report["errors"],"newly_covered":0}),flush=True)
if __name__=="__main__":main()
