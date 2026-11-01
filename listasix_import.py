#!/usr/bin/env python3
"""Import today's ListaSix odds and full ESPN history into isolated MemaraSix files."""
import json
from datetime import datetime,timezone
from pathlib import Path
from urllib.request import Request,urlopen
from zoneinfo import ZoneInfo

BASE="https://raw.githubusercontent.com/shikithe/Slavojka/main/"
OUT=Path("listasix-data")
def load(path):
    req=Request(BASE+path,headers={"User-Agent":"ListaSix-Memara-Importer","Cache-Control":"no-cache"})
    with urlopen(req,timeout=90) as response:
        blob=response.read()
    if len(blob)<100:raise ValueError("Source file unexpectedly empty: "+path)
    return json.loads(blob)
def main():
    offer=load("docs/active-list.json")
    history=load("shared/agent/history-h2h.json")
    now=datetime.now(timezone.utc)
    if not offer.get("fixtures") or not history.get("fixtures") or not history.get("leagues"):
        raise ValueError("Missing odds or full history")
    if offer["date"]!=history["date"]:
        raise ValueError("Different data dates")
    if now>=datetime.fromisoformat(offer["expires_at"]).astimezone(timezone.utc):
        raise ValueError("Expired ListaSix offer")
    ids={f["fixture_id"] for f in history["fixtures"]}
    if any(f["fixture_id"] not in ids for f in offer["fixtures"]):
        raise ValueError("Some offers missing history fixture IDs")
    OUT.mkdir(exist_ok=True)
    for path,obj in [(OUT/"active-list.json",offer),(OUT/"history-h2h.json",history)]:
        tmp=path.with_suffix(".tmp");tmp.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+"\n");tmp.replace(path)
    print("LISTASIX_IMPORTED",len(offer["fixtures"]),"history fixtures",len(history["fixtures"]),"leagues",len(history["leagues"]))
if __name__=="__main__":main()
