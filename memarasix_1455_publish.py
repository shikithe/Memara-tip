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
    if not ("12:00"<=local.strftime("%H:%M")<="12:30"):
        return audit("Outside daily 12:00–12:30 Sarajevo publication window")
    data=load(ROOT/"data.json")
    if data.get("date")!=local.date().isoformat():
        # Prior settled day remains the bank source until the first daily publication.
        if data.get("date", "")>local.date().isoformat() or not data.get("settled",False):
            return audit("Previous day not settled or data.json date is in the future")
    # Preserve previously published tickets; allow another approved ID the same day.
    same_day=data.get("date")==local.date().isoformat()
    existing=list(data.get("tickets",[])) if same_day else []
    existing_ids={t.get("id") for t in existing}
    # Use current ListaSix data directly; never trust a stale imported local copy.
    try:
        offer=remote("shared/active-list.json")
        history=remote("shared/agent/history-h2h.json")
    except Exception as exc:
        return audit("Current ListaSix data unavailable; stale local copies are forbidden",
                     {"detail":str(exc)[:200]})
    if offer.get("date")!=local.date().isoformat() or history.get("date")!=offer.get("date"):
        return audit("Offer and history dates mismatch or stale")
    if not offer.get("publication_allowed") or dt(offer["expires_at"])<=now:
        return audit("Offer not publication-allowed or expired")
    if not history.get("leagues") or not history.get("fixtures"):
        return audit("History lacks populated leagues/fixtures")
    if not offer.get("fixtures"):
        return audit("Current ListaSix has no valid fixtures")
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
            if stamp>now+timedelta(minutes=5):
                continue
            key=(o["home"].casefold(),o["away"].casefold(),o["start_utc"])
            bymatch.setdefault(key,[]).append(o)
        except (KeyError,ValueError,TypeError):
            continue
    if not bymatch:
        return audit("No usable bookmaker snapshots",{"offers_seen":len(offers)})
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
                  "market_name":market,"odds_verified_at_utc":q["updated_at_utc"],"odds_status":"last_known_snapshot","form_home_matches":h["found"],"form_away_matches":a["found"]})
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
    # A, B and C are independent; reject only the ticket that fails validation.
    approved_ids=[t.get("id") for t in approved["tickets"]]
    if len(approved_ids)!=len(set(approved_ids)):
        return audit("Duplicate approved ticket IDs")
    selected=[]
    rejected={}
    used={leg.get("fixture_id") for t in existing for leg in t.get("matches",[]) if leg.get("fixture_id")}
    used.update((leg.get("home"),leg.get("away"),leg.get("start_utc",leg.get("datetime")))
                for t in existing for leg in t.get("matches",[]) if leg.get("home") and leg.get("away"))
    for ticket in approved["tickets"]:
        tid=ticket.get("id")
        if tid in existing_ids:
            rejected[tid]="Already published today"
            continue
        if tid not in ("A","B","C"):
            rejected[str(tid)]="Unknown ticket ID"
            continue
        legs=ticket.get("matches",[])
        if not legs:
            rejected[tid]="No approved matches"
            continue
        verified=[]
        problem=None
        for leg in legs:
            fid=leg.get("fixture_id")
            possible=[c for c in candidates if c["fixture_id"]==fid and c["pick"]==leg.get("pick")
                      and c["bookmaker"]==leg.get("bookmaker")]
            if not possible:
                problem="No verified matching bookmaker quote"
                break
            c=possible[0]
            signature=(c["home"],c["away"],c["start_utc"])
            if fid in used or signature in used or any(v["fixture_id"]==fid for v in verified):
                problem="Repeated fixture across tickets"
                break
            if abs(float(leg.get("odd",0))-c["odd"])>0.01:
                problem="Approved odds differ from verified quote"
                break
            if tid=="B" and c["pick"]!="3+":
                problem="Ticket B requires Over 2.5"
                break
            verified.append(c)
        if problem:
            rejected[tid]=problem
            continue
        total=1.0
        for c in verified: total*=c["odd"]
        if tid in ("A","B") and not 2.0<=total<=3.0:
            rejected[tid]="A/B combined odds outside 2–3"
            continue
        if tid=="C" and total<10.0:
            rejected[tid]="C combined odds below 10"
            continue
        selected.append({"id":tid,"matches":verified,"odds":round(total,2),
                         "analysis":ticket.get("analysis","Independently reviewed ListaSix selection"),
                         "label":{"A":"GLAVNI TIKET","B":"GOLOVI","C":"KEŠ KOLICA"}[tid]})
        for c in verified:
            used.add(c["fixture_id"])
            used.add((c["home"],c["away"],c["start_utc"]))
    if not selected:
        return audit("No new eligible approved tickets",{"rejected":rejected})
    bank=float(data.get("bank_before",data.get("bank_after",0)) if same_day else data.get("bank_after",0))
    if bank<=0: return audit("Invalid bank")
    budget=round(bank*.1,2)
    shares={"A":.65,"B":.25,"C":.10}
    already_spent=round(sum(float(t.get("stake",0)) for t in existing),2)
    remaining=round(budget-already_spent,2)
    if remaining<0: return audit("Existing stakes exceed daily budget")
    accepted=[]
    spent=0.0
    for t in selected:
        stake=round(budget*shares[t["id"]],2)
        if stake<=0 or round(spent+stake,2)>remaining:
            rejected[t["id"]]="Insufficient remaining daily stake budget"
            continue
        t.update({"stake":stake,"status":"objavljen","payout":0})
        spent=round(spent+stake,2)
        accepted.append(t)
    if not accepted:
        return audit("No approved ticket fits remaining daily budget",{"rejected":rejected})
    balance=round((float(data.get("bank_after",0)) if same_day else bank)-spent,2)
    if balance<0: return audit("Insufficient balance")
    statuses=dict(data.get("pending_ticket_statuses",{})) if same_day else {}
    reasons=dict(data.get("pending_ticket_reasons",{})) if same_day else {}
    for t in accepted:
        statuses[t["id"]]="objavljen"
        reasons[t["id"]]=""
    for tid,reason in rejected.items():
        if tid not in existing_ids:
            statuses[tid]="nije odobren"
            reasons[tid]=reason
    data.update({"date":local.date().isoformat(),
      "published":data.get("published") if existing else local.strftime("%d.%m.%Y. u %H:%M (Europe/Sarajevo)"),
      "published_at_utc":data.get("published_at_utc") if existing else now.isoformat(),
      "publication_type":"independent_verified_github",
      "bank_before":bank,"daily_budget":budget,
      "daily_stake":round(already_spent+spent,2),"bank_after_stakes":balance,
      "bank_after":balance,"tickets":existing+accepted,"settled":False,"provisional":False,
      "pending_ticket_statuses":statuses,"pending_ticket_reasons":reasons,
      "odds_verified":True,"analysis_status":"Independent verified ticket publication",
      "selection_method":"Each approved ticket independently checked"})
    result={"timestamp_utc":now.isoformat(),"status":"published",
            "tickets":[t["id"] for t in accepted],"rejected":rejected,
            "daily_stake_added":spent,"bank_after_stakes":balance}
    Path("memarasix-1455-audit.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(result,ensure_ascii=False))
    tmp=ROOT/"data.json.tmp"
    tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    tmp.replace(ROOT/"data.json")
    return 0
if __name__=="__main__":
    sys.exit(main())
