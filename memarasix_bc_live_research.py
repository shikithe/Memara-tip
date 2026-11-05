#!/usr/bin/env python3
"""Prepare independent B and C research queues from LIVE ListaSix; never auto-approve bets."""
import json
import sys
from datetime import datetime,timezone,timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
from memarasix_1455_publish import remote,dt
from memarasix_verified_quotes import verified_candidates

OUT=Path("collector-output/bc-live-research.json")
def prepare(now=None, fetch=remote):
    now=now or datetime.now(timezone.utc)
    day=now.astimezone(ZoneInfo("Europe/Sarajevo")).date().isoformat()
    offer=fetch("shared/active-list.json")
    history=fetch("shared/agent/history-h2h.json")
    provider=fetch("shared/kvoter/provider-offers.json")
    reconciled=fetch("shared/kvoter/matched_fixtures.json")
    if offer.get("date")!=day or history.get("date")!=day:
        raise ValueError("ListaSix dates are stale or inconsistent")
    if not offer.get("publication_allowed") or dt(offer["expires_at"])<=now:
        raise ValueError("ListaSix offer is expired or not publication allowed")
    if not isinstance(offer.get("fixtures"),list) or not history.get("fixtures"):
        raise ValueError("Missing live fixtures or history")
    # The same approved ESPN<->OddsAPI event identities as the final publisher.
    # Research accepts incomplete team form but flags it; publication still blocks it.
    verified=verified_candidates(offer,history,reconciled,provider,now,dt,min_form=0)
    best={}
    for quote in verified:
        pick=quote["pick"]
        if pick not in ("1","2","2+","3+","GG","NG"):
            continue
        key=(quote["fixture_id"],pick)
        if key not in best or quote["odd"]>best[key]["odd"]:
            best[key]=quote
    reports={"B":[],"C":[]}
    for quote in best.values():
        for ticket in (("B","C") if quote["pick"]=="3+" else ("C",)):
            candidate={
                "fixture_id":quote["fixture_id"],"home":quote["home"],
                "away":quote["away"],"start_utc":quote["start_utc"],
                "market":quote["market_name"],"pick":quote["pick"],
                "odd":quote["odd"],"bookmaker":quote["bookmaker"],
                "quote_updated_utc":quote["odds_verified_at_utc"],
                "recent_form_home_matches":quote["form_home_matches"],
                "recent_form_away_matches":quote["form_away_matches"],
                "analysis_status":"requires_independent_review",
                "verified_absences":False,"verified_expected_value":False}
            reports[ticket].append(candidate)
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
