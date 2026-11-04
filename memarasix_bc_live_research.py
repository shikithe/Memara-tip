#!/usr/bin/env python3
"""Prepare independent B and C research queues from LIVE ListaSix; never auto-approve bets."""
import json
import sys
from datetime import datetime,timezone,timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
from memarasix_1455_publish import remote,dt

OUT=Path("collector-output/bc-live-research.json")
def prepare(now=None, fetch=remote):
    now=now or datetime.now(timezone.utc)
    day=now.astimezone(ZoneInfo("Europe/Sarajevo")).date().isoformat()
    offer=fetch("shared/active-list.json")
    history=fetch("shared/agent/history-h2h.json")
    provider=fetch("shared/kvoter/provider-offers.json")
    if offer.get("date")!=day or history.get("date")!=day:
        raise ValueError("ListaSix dates are stale or inconsistent")
    if not offer.get("publication_allowed") or dt(offer["expires_at"])<=now:
        raise ValueError("ListaSix offer is expired or not publication allowed")
    if not isinstance(offer.get("fixtures"),list) or not history.get("fixtures"):
        raise ValueError("Missing live fixtures or history")
    reports={"B":[],"C":[]}
    offers=provider.get("offers",[])
    for fixture in offer["fixtures"]:
        try:
            start=dt(fixture["datetime"])
            if not now+timedelta(minutes=20)<start<now+timedelta(hours=24):
                continue
            home,away=fixture["match"].split(" - ",1)
            league=fixture["fixture_id"].split(":")[2]
            teams=history.get("leagues",{}).get(league,{}).get("teams",{})
            h=teams.get(home,{}).get("found",0)
            a=teams.get(away,{}).get("found",0)
            quotes=[x for x in offers if x.get("home","").casefold()==home.casefold()
                     and x.get("away","").casefold()==away.casefold()
                     and abs((dt(x["start_utc"])-start).total_seconds())<=300
                     and dt(x["updated_at_utc"])<=now+timedelta(minutes=5)]
            markets=[("3+","over","3+","B"),("3+","over","3+","C"),
                     ("2+","over","2+","C"),("BTTS","yes","BTTS","C"),
                     ("1X2","home","1","C"),("1X2","away","2","C")]
            for market,key,pick,ticket in markets:
                valid=[(float(x["markets"][market][key]),x) for x in quotes
                       if isinstance(x.get("markets",{}).get(market,{}).get(key),(int,float))
                       and 1.01<float(x["markets"][market][key])<10.0]
                if not valid:continue
                value,q=max(valid,key=lambda x:x[0])
                reports[ticket].append({"fixture_id":fixture["fixture_id"],"home":home,
                    "away":away,"start_utc":fixture["datetime"],"market":market,
                    "pick":pick,"odd":value,"bookmaker":q["bookmaker"],
                    "quote_updated_utc":q["updated_at_utc"],
                    "recent_form_home_matches":h,"recent_form_away_matches":a,
                    "analysis_status":"requires_independent_review",
                    "verified_absences":False,"verified_expected_value":False})
        except (KeyError,ValueError,TypeError):
            continue
    return {"date":day,"generated_at_utc":now.isoformat(),
            "source":"live ListaSix","state":"research_only","publication_allowed":False,
            "B":{"market":"3+ (over 2.5)","target_combined_odds":"2-3","candidates":reports["B"]},
            "C":{"market":"football plus independently validated NBA if available",
                 "minimum_combined_odds":10,"candidates":reports["C"],
                 "nba_status":"requires separate fresh NBA feed and verified markets"},
            "warnings":["Odds alone do not constitute a good analysis",
                        "Review form, injuries, lineup, style and expected value before approving",
                        "Never publish directly from this research file"]}
def main():
    try:
        result=prepare()
    except Exception as exc:
        result={"generated_at_utc":datetime.now(timezone.utc).isoformat(),
                "state":"blocked","publication_allowed":False,
                "reason":str(exc),"B":{"candidates":[]},"C":{"candidates":[]}}
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"state":result["state"],"B":len(result["B"]["candidates"]),
                      "C":len(result["C"]["candidates"])},ensure_ascii=False))
    return 0 if result["state"]=="research_only" else 1
if __name__=="__main__":sys.exit(main())
