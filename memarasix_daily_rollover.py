#!/usr/bin/env python3
"""Archive a completed prior-day virtual ticket and reset the live landing page.

Safe to rerun. Never archive an unfinished ticket or erase today's publication.
Archive retains full ticket, outcomes and bank accounting.
"""
import json
import os
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

def rollover(live, archive, today):
    if not isinstance(archive,list):
        raise ValueError("archive.json must contain a list")
    day=live.get("date")
    if not isinstance(day,str) or day >= today:
        return live,archive,False
    if not live.get("settled",False):
        print("PENDING_SETTLEMENT: keep prior publication intact until results are settled")
        return live,archive,False
    records=deepcopy(archive)
    # Empty waiting days are carried forward, not added to ticket history.
    if live.get("tickets"):
        found=next((i for i,x in enumerate(records) if x.get("date")==day),None)
        if found is None:
            records.append(deepcopy(live))
        else:
            records[found]=deepcopy(live)
    records.sort(key=lambda x:x.get("date",""))
    bank=live.get("bank_after")
    if not isinstance(bank,(int,float)) or isinstance(bank,bool) or bank < 0:
        raise ValueError("Invalid settled bank")
    empty={
      "date":today,
      "published":"Čeka objavu: 13:00 vikendom / 15:30 radnim danima",
      "publication_type":"awaiting_daily_publication",
      "bank_before":bank,
      "daily_stake":0,
      "bank_after":bank,
      "bank_after_stakes":bank,
      "provisional":False,
      "settled":True,
      "odds_verified":False,
      "tickets":[],
      "total_payout":0,
      "net_change":0,
      "analysis_status":"Prethodni tiket je u arhivi. Današnji tiketi još nisu objavljeni.",
      "selection_method":"Manual ChatGPT analysis from collector; no Python selection filter"
    }
    return empty,records,True

def main():
    live_path=Path("data.json")
    archive_path=Path("archive.json")
    live=json.loads(live_path.read_text(encoding="utf-8"))
    archive=json.loads(archive_path.read_text(encoding="utf-8"))
    today=datetime.now(ZoneInfo("Europe/Sarajevo")).date().isoformat()
    new_live,new_archive,changed=rollover(live,archive,today)
    if changed:
        archive_path.write_text(json.dumps(new_archive,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        live_path.write_text(json.dumps(new_live,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"today":today,"prior_date":live.get("date"),"rolled_over":changed,
                      "archived_days":len(new_archive)},ensure_ascii=False))
if __name__=="__main__":
    main()
