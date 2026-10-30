#!/usr/bin/env python3
"""Main MemaraSix lifecycle. Never touches DEMO or Streak Breaker."""
import json
from pathlib import Path
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from settle_virtual_tickets import settle

DATA=Path("data.json"); ARCHIVE=Path("archive.json"); SCORES=Path("live-scores.json")
DONE={"dobitan","izgubljen","preskočen"}
def save(path,value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
def main(now=None):
    now=now or datetime.now(timezone.utc)
    current=json.loads(DATA.read_text(encoding="utf-8"))
    if not current.get("published"): return
    scores=json.loads(SCORES.read_text(encoding="utf-8"))
    # Existing publications use both 'aktivan' and 'objavljen'.
    for t in current.get("tickets",[]):
        if t.get("status")=="aktivan": t["status"]="objavljen"
    current,_=settle(current,scores)
    tickets=current.get("tickets",[])
    if not tickets or not all(t.get("status") in DONE for t in tickets):
        save(DATA,current); return
    current["settled"]=True
    current["provisional"]=False
    # Time starts when the last PLAYED ticket settles, not when skipped ones were published.
    played=[t for t in tickets if t.get("status")!="preskočen"]
    if played:
        timestamps=[]
        for t in played:
            if not t.get("settled_at_utc"):
                save(DATA,current); return
            timestamps.append(datetime.fromisoformat(t["settled_at_utc"].replace("Z","+00:00")))
        last=max(timestamps)
    else:
        # No played tickets: use publication time; never manufacture a settlement.
        raw=current.get("published_at_utc")
        if not raw:
            save(DATA,current); return
        last=datetime.fromisoformat(raw.replace("Z","+00:00"))
    current["all_tickets_closed_at_utc"]=last.isoformat()
    if now<last+timedelta(hours=1):
        save(DATA,current); return
    archive=json.loads(ARCHIVE.read_text(encoding="utf-8"))
    if not isinstance(archive,list): raise ValueError("Archive must be a list")
    same=[x for x in archive if x.get("date")==current["date"]]
    if same:
        if len(same)>1: raise ValueError("Duplicate archive date")
        # Never overwrite a previously archived day.
    else:
        archive.append(current)
        save(ARCHIVE,archive)
    today=now.astimezone(ZoneInfo("Europe/Sarajevo")).date().isoformat()
    if today<=current["date"]:
        # Date may remain today; landing page still shows empty cards.
        today=current["date"]
    bank=current["bank_after"]
    empty={"date":today,"published":None,"bank_before":bank,"bank_after":bank,
           "bank_after_stakes":bank,"daily_stake":0,"total_payout":0,
           "settled":False,"provisional":False,
           "tickets":[{"id":i,"label":label,"status":"preskočen","stake":0,
                       "odds":None,"payout":0,"matches":[]}
             for i,label in [("A","GLAVNI TIKET — ČEKA SE PONUDA"),
                             ("B","GOLOVI — ČEKA SE PONUDA"),
                             ("C","KEŠ KOLICA — ČEKA SE PONUDA")]],
           "analysis_status":"Čeka se ponuda"}
    save(DATA,empty)
if __name__=="__main__": main()
