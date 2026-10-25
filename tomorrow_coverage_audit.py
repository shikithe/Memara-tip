#!/usr/bin/env python3
"""Read-only next-day football-data.org schedule and statistical coverage audit."""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics_filter import build_index, stats

CODES=("PL","ELC","BL1","PD","SA","FL1","PPL","DED","BSA","CL")
ROOT=Path("collector-output")
def run():
    now=datetime.now(timezone.utc)
    target=(now+timedelta(days=1)).date().isoformat()
    results=[]
    status={}
    for code in CODES:
        path=ROOT/"football-data-cache"/(code+"-current.json")
        if not path.exists():
            status[code]="cache_missing"
            continue
        data=json.loads(path.read_text(encoding="utf-8"))
        teams,finished,matches=build_index(data,now)
        status[code]="ok"
        for m in matches:
            if not str(m.get("utcDate","")).startswith(target): continue
            h=m.get("homeTeam") or {}
            a=m.get("awayTeam") or {}
            hs=stats(h.get("id"),finished,"home") if h.get("id") else None
            aws=stats(a.get("id"),finished,"away") if a.get("id") else None
            ht=stats(h.get("id"),finished) if h.get("id") else None
            at=stats(a.get("id"),finished) if a.get("id") else None
            sufficient=bool(ht and at and hs and aws and ht["played"]>=5 and at["played"]>=5 and hs["played"]>=2 and aws["played"]>=2)
            results.append({"competition":code,"fixture_id_football_data":m.get("id"),"home":h.get("name"),"away":a.get("name"),"kickoff_utc":m.get("utcDate"),"status":m.get("status"),"home_last5":ht,"away_last5":at,"home_split":hs,"away_split":aws,"sufficient_history":sufficient,"api_football_identity_verified":False})
    summary={"target_utc_date":target,"evaluated_at_utc":now.isoformat(),"fixtures_in_football_data":len(results),"sufficient_history":sum(x["sufficient_history"] for x in results),"not_sufficient":sum(not x["sufficient_history"] for x in results),"competition_cache_status":status,"limitation":"Only football-data.org schedule and history verified; API-Football fixture ID matching requires a refreshed API-Football feed for the target date."}
    ROOT.mkdir(exist_ok=True)
    (ROOT/"tomorrow-coverage-audit.json").write_text(json.dumps({"summary":summary,"fixtures":results},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("TOMORROW COVERAGE SUMMARY",json.dumps(summary,ensure_ascii=False))
    for r in results: print("TOMORROW FIXTURE",json.dumps({"competition":r["competition"],"home":r["home"],"away":r["away"],"kickoff_utc":r["kickoff_utc"],"sufficient_history":r["sufficient_history"],"home_total":r["home_last5"]["played"] if r["home_last5"] else None,"away_total":r["away_last5"]["played"] if r["away_last5"] else None,"home_home":r["home_split"]["played"] if r["home_split"] else None,"away_away":r["away_split"]["played"] if r["away_split"] else None},ensure_ascii=False))
if __name__=="__main__":run()
