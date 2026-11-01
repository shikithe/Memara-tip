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
    # GitHub owns the publication write. A separate independently reviewed AI selection
    # is required; raw bookmaker consensus is not itself a reliable prediction.
    approval=ROOT/"memarasix-1455-approved.json"
    if not approval.exists():
        return audit("No independently reviewed A/B/C selection file; never auto-bet from market odds alone",
                     {"fresh_bookmaker_matches":len(bymatch),"eligible_market_quotes":len(candidates),
                      "required_file":approval.name})
    approved=load(approval)
    if approved.get("date")!=local.date().isoformat() or not approved.get("tickets"):
        return audit("Approval file has wrong date or no tickets")
    selected=[]
    used=set()
    for ticket in approved["tickets"]:
        tid=ticket.get("id")
        if tid not in ("A","B","C") or tid in {t["id"] for t in selected}:
            return audit("Unknown or repeated ticket ID")
        legs=ticket.get("matches",[])
        if not legs:
            return audit("Approved ticket has no matches")
        verified=[]
        for leg in legs:
            fid=leg.get("fixture_id")
            if fid in used:
                return audit("Repeated fixture across tickets")
            possible=[c for c in candidates if c["fixture_id"]==fid and c["pick"]==leg.get("pick")
                      and c["bookmaker"]==leg.get("bookmaker")]
            if not possible:
                return audit("Approved leg not supported by fresh verified bookmaker quotes",{"fixture_id":fid})
            c=possible[0]
            if abs(float(leg.get("odd",0))-c["odd"])>0.01:
                return audit("Approved odds differ from verified bookmaker quote",{"fixture_id":fid})
            if tid=="B" and c["pick"]!="3+":
                return audit("Ticket B requires Over 2.5")
            used.add(fid)
            verified.append(c)
        total=1.0
        for c in verified: total*=c["odd"]
        if tid in ("A","B") and not 2.0<=total<=3.0:
            return audit("A/B combined odds outside 2–3",{"ticket":tid,"odds":total})
        if tid=="C" and total<10.0:
            return audit("C combined odds below 10",{"odds":total})
        selected.append({"id":tid,"matches":verified,"odds":round(total,2),
                         "analysis":ticket.get("analysis","Independently reviewed ListaSix selection"),
                         "label":{"A":"GLAVNI TIKET","B":"GOLOVI","C":"KEŠ KOLICA"}[tid]})
    bank=float(data.get("bank_before",data.get("bank_after",0)))
    if bank<=0: return audit("Invalid bank")
    budget=round(bank*.1,2)
    shares={"A":.65,"B":.25,"C":.10}
    ids={t["id"] for t in selected}
    if ids=={"A","B"}: shares={"A":.70,"B":.30}
    stakes={}
    for t in selected:
        stakes[t["id"]]=round(budget*shares[t["id"]],2)
        t["stake"]=stakes[t["id"]]
        t["status"]="objavljen"
        t["payout"]=0
    spent=round(sum(stakes.values()),2)
    if spent>budget: return audit("Allocation exceeds daily budget")
    data.update({"date":local.date().isoformat(),"published":local.strftime("%d.%m.%Y. u %H:%M (Europe/Sarajevo)"),
      "published_at_utc":now.isoformat(),"publication_type":"verified_github_1455",
      "daily_budget":budget,"daily_stake":spent,"bank_after_stakes":round(bank-spent,2),
      "bank_after":round(bank-spent,2),"tickets":selected,"settled":False,"provisional":False,
      "odds_verified":True,"analysis_status":"GitHub published independently reviewed and quote-validated ListaSix picks",
      "selection_method":"Independently reviewed selections with verified bookmaker quotes"})
    tmp=ROOT/"data.json.tmp"
    tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    tmp.replace(ROOT/"data.json")
    result={"timestamp_utc":now.isoformat(),"status":"published","tickets":[t["id"] for t in selected],
            "daily_stake":spent,"bank_after_stakes":data["bank_after_stakes"]}
    Path("memarasix-1455-audit.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(result,ensure_ascii=False))
    return 0
if __name__=="__main__":
    sys.exit(main())
