#!/usr/bin/env python3
"""Reproducible read-only audit of supported fixtures lost to kickoff timing."""
import json
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

SUPPORTED = {39:"Premier League",40:"Championship",78:"Bundesliga",140:"La Liga",135:"Serie A",61:"Ligue 1",94:"Primeira Liga",88:"Eredivisie",71:"Brazil Serie A",2:"Champions League"}
root=Path("collector-output")
pref=json.loads((root/"fixture-prefilter.json").read_text(encoding="utf-8"))
stats=json.loads((root/"statistics-filter.json").read_text(encoding="utf-8"))
rows={r["fixture_id"]:r for r in stats["fixtures"]}
as_of=datetime.fromisoformat(pref["evaluated_at_utc"].replace("Z","+00:00"))
date=pref.get("date") or as_of.date().isoformat()
day_start=datetime.fromisoformat(date+"T00:00:00+00:00")
output=[]
for f in pref["fixtures"]:
    if f.get("league_id") not in SUPPORTED: continue
    kickoff=datetime.fromisoformat(f["start_utc"].replace("Z","+00:00"))
    if kickoff.date().isoformat()!=date: continue
    report=rows.get(f["fixture_id"],{})
    output.append({"fixture_id":f["fixture_id"],"league_id":f["league_id"],"league":f["league"],"home":f["home"],"away":f["away"],"kickoff_utc":f["start_utc"],"current_decision":f["decision"],"current_reason":report.get("reason"),"eligible_at_day_start":kickoff>day_start+timedelta(minutes=5),"eligible_at_actual_run":kickoff>as_of+timedelta(minutes=5)})
counts=Counter(r["current_reason"] for r in output)
by_league=Counter(r["league"] for r in output)
summary={"date":date,"evaluated_at_utc":as_of.isoformat(),"supported_fixtures_in_snapshot":len(output),"eligible_at_day_start":sum(r["eligible_at_day_start"] for r in output),"eligible_at_actual_run":sum(r["eligible_at_actual_run"] for r in output),"rejected_due_to_time":sum(r["current_reason"]=="prefilter_rejected" and not r["eligible_at_actual_run"] for r in output),"covered":counts["sufficient_history"],"reasons":dict(counts),"by_league":dict(by_league),"caution":"Day-start eligibility is a timing counterfactual, not proof that historical coverage or identity would pass. Snapshot may omit fixtures; compare with independent feed separately."}
dest=root/"coverage-timing-audit.json"
dest.write_text(json.dumps({"summary":summary,"fixtures":output},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print("TIMING AUDIT",json.dumps(summary,ensure_ascii=False))
for r in output: print("SUPPORTED FIXTURE",json.dumps(r,ensure_ascii=False))
