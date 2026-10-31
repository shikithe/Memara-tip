#!/usr/bin/env python3
"""Read-only ESPN coverage audit; never publishes or changes bankroll."""
import argparse
import json
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

LEAGUES = ("eng.1","esp.1","ger.1","ita.1","fra.1","ned.1",
           "eng.2","ger.2","ita.2","fra.2","por.1","bel.1",
           "tur.1","sco.1","uefa.champions","uefa.europa",
           "uefa.europa.conf","usa.1","bra.1","arg.1")
BASE = "https://site.api.espn.com/apis/site/v2/sports/soccer"

def fetch(url):
    with urlopen(Request(url,headers={"User-Agent":"MemaraSix-Audit/1.0","Accept":"application/json"}),timeout=10) as response:
        raw=response.read(4*1024*1024+1)
    if len(raw)>4*1024*1024:
        raise ValueError("oversize_response")
    return json.loads(raw)

def stat_names(node):
    found=set()
    def walk(x):
        if isinstance(x,dict):
            for k,v in x.items():
                key=k.lower().replace("_","").replace(" ","")
                if key in ("name","type","label") and isinstance(v,str):
                    found.add(v.lower().replace("_","").replace(" ",""))
                elif key not in ("name","type","label"):
                    found.add(key)
                walk(v)
        elif isinstance(x,list):
            for v in x:walk(v)
    walk(node)
    return found

def audit_league(league,asof,sample=3,delay=0.25):
    result={"league":league,"days_scanned":0,"finished_found":0,"sampled":0,
            "summary_success":0,"stats":0,"shots":0,"possession":0,"lineups":0,"xg":0,
            "errors":[],"examples":[]}
    events={}
    for offset in range(14):
        day=(asof-timedelta(days=offset)).strftime("%Y%m%d")
        try:
            payload=fetch(f"{BASE}/{league}/scoreboard?"+urlencode({"dates":day,"limit":500}))
            result["days_scanned"]+=1
            for event in payload.get("events",[]):
                if (event.get("status") or {}).get("type",{}).get("state")=="post":
                    events[str(event["id"])]=event
        except Exception as exc:
            result["errors"].append(f"scoreboard {day}: {type(exc).__name__}: {str(exc)[:100]}")
            if offset==0 and isinstance(exc,OSError):break
        if len(events)>=sample:break
        time.sleep(delay)
    result["finished_found"]=len(events)
    for event in list(events.values())[:sample]:
        eid=str(event["id"])
        detail={"event_id":eid,"name":event.get("name")}
        try:
            payload=fetch(f"{BASE}/{league}/summary?event={eid}")
            result["summary_success"]+=1
            box=payload.get("boxscore") or {}
            names=stat_names({"boxscore":box,"rosters":payload.get("rosters"),"header":payload.get("header")})
            flags={
                "stats":bool(box.get("teams") or box.get("players")),
                "shots":any("shot" in name for name in names),
                "possession":any("possession" in name for name in names),
                "lineups":bool(payload.get("rosters")) or any("lineup" in name for name in names),
                "xg":any("expectedgoal" in name or name=="xg" for name in names)
            }
            for key,value in flags.items():result[key]+=int(value)
            detail["flags"]=flags
        except Exception as exc:
            detail["error"]=f"{type(exc).__name__}: {str(exc)[:100]}"
            result["errors"].append(f"summary {eid}: {detail['error']}")
        result["sampled"]+=1
        result["examples"].append(detail)
        time.sleep(delay)
    return result

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--date",default=date.today().isoformat())
    p.add_argument("--sample",type=int,default=3)
    p.add_argument("--delay",type=float,default=0.25)
    p.add_argument("--leagues",nargs="*",default=list(LEAGUES))
    p.add_argument("--output",default="ai-lab/output/espn-audit.json")
    a=p.parse_args()
    if not 1<=a.sample<=10:p.error("sample must be between 1 and 10")
    rows=[audit_league(league,date.fromisoformat(a.date),a.sample,max(a.delay,0.1)) for league in a.leagues]
    report={"generated_at":datetime.now(timezone.utc).isoformat(),"read_only":True,"leagues":rows}
    target=Path(a.output)
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(f"Audited {len(rows)} leagues; successful summaries {sum(x['summary_success'] for x in rows)}")
if __name__=="__main__":
    main()
