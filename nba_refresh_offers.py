"""Ensure today's NBA odds snapshot before ESPN statistics. Never use stale data."""
import datetime as dt
import json
import urllib.request
from pathlib import Path
from zoneinfo import ZoneInfo

PATH=Path("collector-output/nba-player-points.json")
URL="https://raw.githubusercontent.com/shikithe/Memara-tip/main/collector-output/nba-player-points.json"
ZONE=ZoneInfo("Europe/Sarajevo")

def fresh(data,now=None):
    stamp=data.get("generated_at_utc")
    if not stamp:return False
    try:
        when=dt.datetime.fromisoformat(stamp.replace("Z","+00:00"))
        if when.tzinfo is None:return False
        today=(now or dt.datetime.now(ZONE)).astimezone(ZONE).date()
        return when.astimezone(ZONE).date()==today and isinstance(data.get("offers"),list)
    except (TypeError,ValueError):return False

def ensure():
    if PATH.exists():
        try:
            local=json.loads(PATH.read_text(encoding="utf-8"))
            if fresh(local):
                print(f"Today's offers already present: {len(local['offers'])}")
                return
        except (ValueError,OSError):pass
    print("Local odds snapshot stale; fetching latest published snapshot from main")
    request=urllib.request.Request(URL,headers={"User-Agent":"MEMARA-NBA-Stats/1.0"})
    with urllib.request.urlopen(request,timeout=25) as response:
        latest=json.load(response)
    if not fresh(latest):
        print("Published odds also stale; fetching live NBA player-points markets")
        from nba_live_odds_collector import run
        run()
        return
    PATH.parent.mkdir(parents=True,exist_ok=True)
    PATH.write_text(json.dumps(latest,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(f"Refreshed today's odds: {len(latest['offers'])} offers")

if __name__=="__main__":ensure()
