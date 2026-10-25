#!/usr/bin/env python3
"""MemaraSix unified pipeline handoff: coverage -> analyst queue, never bets."""
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path("collector-output")
def load(name):
    return json.loads((ROOT/name).read_text(encoding="utf-8"))
def main():
    fixture=load("statistics-research.json")
    pre=load("fixture-prefilter.json")
    stats=load("statistics-filter.json")
    if fixture.get("date")!=pre.get("date"):
        raise SystemExit("Date mismatch: fixture feed and prefilter")
    source=fixture.get("football") or {}
    if source.get("status")!="ok":
        raise SystemExit("API-Football fixtures unavailable; do not publish")
    if len(source.get("fixtures") or [])!=len(pre.get("fixtures") or []):
        raise SystemExit("Fixture count mismatch")
    if len(stats.get("fixtures") or [])!=len(pre.get("fixtures") or []):
        raise SystemExit("Statistics count mismatch")
    rows=[]
    for x in stats["fixtures"]:
        if x.get("point3")!="covered": continue
        coverage=x.get("coverage") or {}
        rows.append({"fixture_id":x.get("fixture_id"),"league_id":x.get("league_id"),"league":x.get("league"),"home":x.get("home"),"away":x.get("away"),"coverage":coverage,"stage":"awaiting_full_independent_analysis","odds_verified":False,"lineups_verified":False,"injuries_verified":False,"market":None,"recommended_bet":None,"publication_allowed":False})
    report={"date":fixture["date"],"generated_at_utc":datetime.now(timezone.utc).isoformat(),"stage":"statistical_coverage_completed","source_fixture_count":len(source["fixtures"]),"counts":stats["counts"],"reasons":dict(Counter(x.get("reason") for x in stats["fixtures"])),"analyst_queue":rows,"odds_verified":False,"publication_allowed":False,"ticket_publication_allowed":False,"next_steps":["independent team and match analysis","verify lineups and injuries","verify bookmaker odds","risk and bankroll validation","explicit publication gate"]}
    path=ROOT/"unified-analysis-queue.json"
    path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("UNIFIED ANALYST QUEUE",json.dumps({"date":report["date"],"fixtures":report["source_fixture_count"],"covered":len(rows),"publication_allowed":False},ensure_ascii=False))
if __name__=="__main__":main()
