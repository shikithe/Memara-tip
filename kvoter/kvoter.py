#!/usr/bin/env python3
"""Isolated MEMARASIX odds matcher. Never invent odds, publish, or alter bank."""
import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from difflib import SequenceMatcher

def norm(s):
    return " ".join("".join(c if c.isalnum() else " " for c in str(s or "").casefold()).split())

def utc(s):
    if not s: return None
    try: return datetime.fromisoformat(s.replace("Z","+00:00")).astimezone(timezone.utc)
    except (ValueError,TypeError): return None

def match(fixture, offer, tolerance_minutes=90):
    if norm(fixture.get("league")) != norm(offer.get("league")):
        return False
    t1,t2=utc(fixture.get("start_utc")),utc(offer.get("start_utc"))
    if not t1 or not t2 or abs((t1-t2).total_seconds())>tolerance_minutes*60:
        return False
    # Strict team matching; do not accept fuzzy matches without manual review.
    return norm(fixture.get("home"))==norm(offer.get("home")) and norm(fixture.get("away"))==norm(offer.get("away"))

def build(feed, offers, source="import"):
    fixtures=feed.get("football_candidates",[])
    if not isinstance(fixtures,list) or not isinstance(offers,list):
        raise ValueError("football_candidates and offers must be lists")
    result=[]
    for fixture in fixtures:
        candidates=[o for o in offers if isinstance(o,dict) and match(fixture,o)]
        preferred=sorted(candidates,key=lambda o:(norm(o.get("bookmaker"))!="bet365",str(o.get("bookmaker",""))))
        found=[]
        for offer in preferred:
            markets=offer.get("markets",{})
            if not isinstance(markets,dict) or not markets: continue
            valid={}
            for market,outcomes in markets.items():
                if not isinstance(outcomes,dict): continue
                clean={}
                for selection,price in outcomes.items():
                    try:
                        v=float(price)
                        if 1.0<v<10000: clean[selection]=v
                    except (ValueError,TypeError): pass
                if clean: valid[market]=clean
            if valid:
                found.append({"bookmaker":offer.get("bookmaker"),"markets":valid,
                              "updated_at_utc":offer.get("updated_at_utc"),"source_event_id":offer.get("event_id")})
        result.append({"fixture_id":fixture.get("id"),"league":fixture.get("league"),
                       "home":fixture.get("home"),"away":fixture.get("away"),
                       "start_utc":fixture.get("start_utc"),"start_sarajevo":fixture.get("start_sarajevo"),
                       "status":"matched" if found else "unavailable",
                       "odds":found})
    return {"schema_version":"memarasix-kvoter-v1","generated_at_utc":datetime.now(timezone.utc).isoformat(),
            "source":source,"fixtures":result,"total":len(result),
            "matched":sum(x["status"]=="matched" for x in result),
            "unavailable":sum(x["status"]=="unavailable" for x in result),
            "publication_allowed":False,"bank_modified":False,"tickets_published":False}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--feed",default="/shared/collector-feed.json")
    p.add_argument("--offers",default="/shared/kvoter/provider-offers.json")
    p.add_argument("--output",default="/shared/kvoter/odds.json")
    args=p.parse_args()
    feed=json.loads(Path(args.feed).read_text(encoding="utf-8"))
    offers_path=Path(args.offers)
    offers=json.loads(offers_path.read_text(encoding="utf-8")) if offers_path.exists() else []
    if isinstance(offers,dict): offers=offers.get("offers",[])
    report=build(feed,offers)
    out=Path(args.output);out.parent.mkdir(parents=True,exist_ok=True)
    temp=out.with_suffix(".tmp")
    temp.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    os.replace(temp,out)
    print("KVOTER",json.dumps({"total":report["total"],"matched":report["matched"],"unavailable":report["unavailable"]}))
if __name__=="__main__": main()
