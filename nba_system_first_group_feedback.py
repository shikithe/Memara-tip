#!/usr/bin/env python3
"""Emit one readiness feedback for group 1 only after all ten daily BetSharp lists exist.
Never replace publication feedback or change bets.
"""
import json
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parent
OUT=ROOT/"collector-output"
SAR=ZoneInfo("Europe/Sarajevo")

def load(p):
    return json.loads(p.read_text(encoding="utf-8"))

def main():
    today=datetime.now(SAR).date().isoformat()
    source_path=OUT/"betsharp-nba-daily.json"
    if not source_path.exists():
        raise SystemExit("Not ready: missing BetSharp capture")
    source=load(source_path)
    offers=source.get("offers")
    if (source.get("status")!="ok" or source.get("game_date_et")!=today
        or not isinstance(offers,list) or len(offers)<20
        or source.get("player_count")!=len(offers)):
        raise SystemExit("Not ready: daily BetSharp capture invalid/stale")
    ledger=load(ROOT/"nba-sistem.json")
    cycle=next((c for c in ledger.get("cycles",[]) if c.get("date")==today),None)
    if cycle and cycle.get("tickets"):
        print("Already publishing today's NBA ten-cycle; preserve publication feedback")
        return
    feedback_path=OUT/"nba-system-feedback.json"
    if feedback_path.exists():
        existing=load(feedback_path)
        if existing.get("date")==today and existing.get("state") in (
            "ready_for_first_ai_scout","ready_for_next_ai_scout","all_10_published"):
            print("Today's feedback already exists; preserve it")
            return
    base,rem=divmod(len(offers),10)
    offset=0
    for n in range(1,11):
        p=OUT/"nba-system-lists"/today/f"list-{n:02d}.json"
        if not p.exists():
            raise SystemExit(f"Not ready: missing {p}")
        group=load(p)
        size=base+int(n<=rem)
        if not (group.get("date")==today and group.get("list_number")==n
            and group.get("total_lists")==10 and group.get("total_offers")==len(offers)
            and group.get("captured_at_utc")==source.get("collected_at_utc")
            and group.get("original_positions")==[offset+1,offset+size]
            and group.get("group_size")==size and group.get("status")=="awaiting_scout"
            and group.get("offers")==[
                {**o,"original_offer_position":offset+i+1}
                for i,o in enumerate(offers[offset:offset+size])
            ]):
            raise SystemExit(f"Not ready: list {n} mismatch with canonical BetSharp")
        offset+=size
    payload={
      "schema_version":1,"date":today,"cycle_id":f"nba-{today}",
      "last_published_group":0,"published_ticket_ids":[],
      "next_group":1,"state":"ready_for_first_ai_scout",
      "trigger_source":"github_verified_ten_lists",
      "total_lists":10,"total_offers":len(offers),
      "captured_at_utc":source["collected_at_utc"],
      "updated_at_utc":datetime.now(timezone.utc).isoformat(),
      "note":"Readiness signal for scheduled ChatGPT AI Scout; not a direct ChatGPT wake-up. Preserve later publication feedback."
    }
    feedback_path.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(payload,ensure_ascii=False))

if __name__=="__main__":
    main()
