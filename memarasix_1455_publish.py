#!/usr/bin/env python3
"""One-time GitHub publisher. Fail closed: no invented odds, no stale matches, no overwrites."""
import json, os, sys, urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parent
UTC=timezone.utc
def dt(v):
    return datetime.fromisoformat(v.replace("Z","+00:00")).astimezone(UTC)
def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))
def audit(reason, extra=None):
    result={"timestamp_utc":datetime.now(UTC).isoformat(),"status":"blocked","reason":reason,**(extra or {})}
    Path("memarasix-1455-audit.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(result,ensure_ascii=False))
    return 0
def remote(path):
    url="https://raw.githubusercontent.com/shikithe/Slavojka/main/"+path
    req=urllib.request.Request(url,headers={"User-Agent":"MemaraSix-1455-GitHub-Publisher","Cache-Control":"no-cache"})
    with urllib.request.urlopen(req,timeout=35) as r:
        return json.loads(r.read())
def main():
    now=datetime.now(UTC)
    local=now.astimezone(ZoneInfo("Europe/Sarajevo"))
    if local.date().isoformat()!="2026-11-01" or not ("14:55"<=local.strftime("%H:%M")<="15:20"):
        return audit("Outside authorized one-time 2026-11-01 14:55–15:20 Sarajevo window")
    data=load(ROOT/"data.json")
    if data.get("date")!=local.date().isoformat():
        return audit("data.json date does not match today")
    if any(t.get("status") in ("objavljen","aktivan","dobitan","izgubljen") for t in data.get("tickets",[])):
        return audit("Today's published ticket exists; never overwrite")
    offer=load(ROOT/"listasix-data/active-list.json")
    history=load(ROOT/"listasix-data/history-h2h.json")
    if offer.get("date")!=local.date().isoformat() or history.get("date")!=offer.get("date"):
        return audit("Offer and history dates mismatch or stale")
    if not offer.get("publication_allowed") or dt(offer["expires_at"])<=now:
        return audit("Offer not publication-allowed or expired")
    if not history.get("leagues") or not history.get("fixtures"):
        return audit("History lacks populated leagues/fixtures")
    try:
        provider=remote("shared/kvoter/provider-offers.json")
    except Exception as exc:
        return audit("Cannot independently verify bookmaker offers",{"detail":str(exc)[:200]})
    offers=provider.get("offers",[])
    if not offers:
        return audit("No bookmaker offers")
    bymatch={}
    for o in offers:
        try:
            stamp=dt(o["updated_at_utc"])
            if stamp>now+timedelta(minutes=5) or now-stamp>timedelta(minutes=60):
                continue
            key=(o["home"].casefold(),o["away"].casefold(),o["start_utc"])
            bymatch.setdefault(key,[]).append(o)
        except (KeyError,ValueError,TypeError):
            continue
    if not bymatch:
        return audit("All bookmaker snapshots are older than 60 minutes",{"offers_seen":len(offers)})
    # Validate form coverage; data do not include full scored H2H, so do not claim H2H verified.
    candidates=[]
    for f in offer["fixtures"]:
        try:
            start=dt(f["datetime"])
            if start<=now+timedelta(minutes=20) or start>now+timedelta(hours=18):
                continue
            home,away=[x.strip() for x in f["match"].split(" - ",1)]
            league=f["fixture_id"].split(":")[2]
            teams=history["leagues"].get(league,{}).get("teams",{})
            h,a=teams.get(home,{}),teams.get(away,{})
            if min(h.get("found",0),a.get("found",0))<4:
                continue
            quotes=bymatch.get((home.casefold(),away.casefold(),f["datetime"]),[])
            for market,pick,field in [("1X2","1","home"),("1X2","2","away"),("3+","3+","over")]:
                valid=[]
                for q in quotes:
                    value=q.get("markets",{}).get(market,{}).get(field)
                    if isinstance(value,(int,float)) and 1.25<=value<=3.0:
                        valid.append((float(value),q))
                if len({q["bookmaker"] for _,q in valid})<2:
                    continue
                valid.sort(key=lambda x:x[0])
                median=valid[len(valid)//2][0]
                agreed=[(v,q) for v,q in valid if abs(v-median)/median<=0.08]
                if len({q["bookmaker"] for _,q in agreed})<2:
                    continue
                # Use the first bookmaker quote close to the median, never a synthetic price.
                price,q=min(agreed,key=lambda z:abs(z[0]-median))
                candidates.append({"fixture_id":f["fixture_id"],"home":home,"away":away,"start_utc":f["datetime"],"pick":pick,
                  "odd":price,"odds":price,"bookmaker":q["bookmaker"],"market_source":"The Odds API / "+q["bookmaker"],
                  "market_name":market,"odds_verified_at_utc":q["updated_at_utc"],"form_home_matches":h["found"],"form_away_matches":a["found"]})
        except (KeyError,ValueError,TypeError):
            continue
    # Automated rules-only test: no AI-generated qualitative evidence is present.
    # Publication requires independently reviewed selections; market consensus and match counts alone
    # cannot establish a reliable sporting prediction.
    return audit("No independently reviewed A/B/C selections: GitHub has odds and form coverage but not validated prediction evidence. Publication withheld.",
                 {"fresh_bookmaker_matches":len(bymatch),"eligible_market_quotes":len(candidates),
                  "source":"ListaSix active-list + history-h2h + provider-offers"})
if __name__=="__main__":
    sys.exit(main())
