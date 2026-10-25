#!/usr/bin/env python3
"""Read-only audit: last five completed matchdays per free football-data.org competition."""
import json,os,time,urllib.request,urllib.error
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path
CODES={"CL":"Champions League","PPL":"Primeira Liga","PL":"Premier League","DED":"Eredivisie","BL1":"Bundesliga","FL1":"Ligue 1","SA":"Serie A Italy","PD":"La Liga","ELC":"Championship","BSA":"Serie A Brazil","WC":"World Cup","EC":"European Championship"}
token=os.environ.get("FOOTBALL_DATA_TOKEN")
if not token:raise SystemExit("FOOTBALL_DATA_TOKEN secret missing")
out={"as_of_utc":datetime.now(timezone.utc).isoformat(),"source":"football-data.org v4","requested_competitions":list(CODES),"publication_allowed":False,"competitions":{}}
last=0
for code,name in CODES.items():
 wait=max(0,7.0-(time.monotonic()-last))
 if wait:time.sleep(wait)
 req=urllib.request.Request("https://api.football-data.org/v4/competitions/"+code+"/matches",headers={"X-Auth-Token":token,"User-Agent":"MemaraSix/1.0"})
 last=time.monotonic()
 try:
  with urllib.request.urlopen(req,timeout=40) as resp:
   data=json.load(resp)
   remaining=resp.headers.get("X-Requests-Available-Minute")
  cache=Path("collector-output/football-data-cache");cache.mkdir(parents=True,exist_ok=True)
  (cache/(code+"-current.json")).write_text(json.dumps(data,ensure_ascii=False),encoding="utf-8")
  finished=[m for m in data.get("matches",[]) if m.get("status")=="FINISHED" and (m.get("score") or {}).get("fullTime",{}).get("home") is not None]
  rounds=sorted({m["matchday"] for m in finished if isinstance(m.get("matchday"),int)})
  if rounds:
   selected=[m for m in finished if m.get("matchday") in rounds[-5:]]
   selection="last_five_completed_matchdays"
  else:
   dates=sorted({m.get("utcDate","")[:10] for m in finished if m.get("utcDate")})
   selected=[m for m in finished if m.get("utcDate","")[:10] in dates[-5:]]
   selection="last_five_completed_dates_no_matchday"
  out["competitions"][code]={"name":name,"status":"ok","selection":selection,"matchdays":rounds[-5:],"matches_returned":len(data.get("matches",[])),"finished_in_season":len(finished),"selected_matches":len(selected),"requests_remaining_header":remaining,"matches":[{"id":m.get("id"),"date":m.get("utcDate"),"matchday":m.get("matchday"),"home":(m.get("homeTeam") or {}).get("name"),"away":(m.get("awayTeam") or {}).get("name"),"score":(m.get("score") or {}).get("fullTime")} for m in selected]}
  print(f"{code}: {len(selected)} matches; {selection}; remaining={remaining}",flush=True)
 except urllib.error.HTTPError as exc:
  out["competitions"][code]={"name":name,"status":"http_error","http_status":exc.code}
  print(f"{code}: HTTP {exc.code}",flush=True)
  if exc.code==429:
   print("Rate limited: stopping to avoid further requests",flush=True)
   break
 except (urllib.error.URLError,TimeoutError,ValueError) as exc:
  out["competitions"][code]={"name":name,"status":"error","type":type(exc).__name__}
  print(f"{code}: {type(exc).__name__}",flush=True)
dest=Path("collector-output/football-data-last5-rounds.json")
dest.parent.mkdir(exist_ok=True)
dest.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
print("LAST5 SUMMARY",json.dumps({"requested":len(CODES),"successful":sum(x["status"]=="ok" for x in out["competitions"].values()),"total_selected_matches":sum(x.get("selected_matches",0) for x in out["competitions"].values()),"errors":{k:v.get("http_status",v.get("type")) for k,v in out["competitions"].items() if v["status"]!="ok"}}),flush=True)
