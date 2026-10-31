#!/usr/bin/env python3
"""Create research queue for all unknown provider teams; import verified aliases; rerun matching.
Research is external: this script does not pretend to have Google/ChatGPT access.
"""
import argparse,json
from pathlib import Path
from kvoter import build,utc
from team_identity import normalize

def load(path,default):
    p=Path(path)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default

def candidates(history,offers,report,approved):
    known={(e["league"],normalize(n)) for e in approved["teams"] for n in e["names"]}
    pending={}
    unmatched={f["fixture_id"] for f in report["unmatched_fixtures"]}
    fixtures=[f for f in history["fixtures"] if (f.get("fixture_id") or f.get("id")) in unmatched]
    for offer in offers:
        if not isinstance(offer,dict): continue
        league=offer.get("league")
        nearby=[f for f in fixtures if f.get("league")==league and utc(f.get("start_utc")) and utc(offer.get("start_utc")) and abs((utc(f["start_utc"])-utc(offer["start_utc"])).total_seconds())<=5400]
        if not nearby: continue
        for side in ("home","away"):
            name=offer.get(side)
            if not name or (league,normalize(name)) in known: continue
            key=(league,normalize(name))
            entry=pending.setdefault(key,{"league":league,"provider_name":name,"possible_names":[],"status":"research_required","candidate_history_names":[]})
            entry["candidate_history_names"]=sorted(set(entry["candidate_history_names"]+[f.get(side) for f in nearby if f.get(side)]))
    return list(pending.values())

def merge_verified(db,proposals):
    """Only explicit verified identities with source URLs can enter persistent database."""
    for item in proposals:
        if item.get("status")!="verified" or not item.get("sources") or len(item.get("names",[]))<2: continue
        league=item["league"]; names=item["names"]
        if any(not isinstance(n,str) or not normalize(n) for n in names): continue
        existing={ (e["league"],normalize(n)):e["id"] for e in db["teams"] for n in e["names"] }
        ids={existing[(league,normalize(n))] for n in names if (league,normalize(n)) in existing}
        if len(ids)>1: continue
        identity=next(iter(ids),item.get("id"))
        if not identity: continue
        if any((league,normalize(n)) in existing and existing[(league,normalize(n))]!=identity for n in names): continue
        target=next((e for e in db["teams"] if e["id"]==identity and e["league"]==league),None)
        if target: target["names"]=sorted(set(target["names"]+names))
        else: db["teams"].append({"id":identity,"league":league,"names":names,"sources":item["sources"]})
    return db

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--history",default="/shared/agent/history-h2h.json")
    p.add_argument("--offers",default="/shared/kvoter/provider-offers.json")
    p.add_argument("--database",default="/shared/kvoter/team-aliases-approved.json")
    p.add_argument("--proposals",default="/shared/kvoter/verified-alias-proposals.json")
    p.add_argument("--queue",default="/shared/kvoter/team-research-queue.json")
    p.add_argument("--report",default="/shared/kvoter/match-report.json")
    a=p.parse_args()
    history=load(a.history,{"fixtures":[]})
    raw=load(a.offers,{"offers":[]})
    offers=raw.get("offers",[]) if isinstance(raw,dict) else raw
    base=load(Path(__file__).with_name("team_aliases.json"),{"teams":[]})
    db=load(a.database,base)
    db=merge_verified(db,load(a.proposals,[]))
    Path(a.database).parent.mkdir(parents=True,exist_ok=True)
    Path(a.database).write_text(json.dumps(db,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    # team_identity reads the approved database through the explicit environment override.
    import os
    os.environ["KVOTER_ALIASES_PATH"]=str(Path(a.database).resolve())
    report=build(history,offers)
    queue=candidates(history,offers,report,db)
    Path(a.queue).write_text(json.dumps({"teams":queue},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    Path(a.report).write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"matched":report["matched"],"unmatched":report["unavailable"],"research_queue":len(queue)}))
if __name__=="__main__":main()
