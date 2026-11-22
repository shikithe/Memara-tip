"""Local Sarajevo A/B sensor phase boundaries and publication feedback."""
import json
from datetime import datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo

TZ=ZoneInfo("Europe/Sarajevo")

def phase(now, preparation=None):
    clock=now.astimezone(TZ).time().replace(tzinfo=None)
    if time(10,0) <= clock < time(13,0):
        if isinstance(preparation, dict) and preparation.get("date")==now.astimezone(TZ).date().isoformat() and preparation.get("feedback")=="TOP10_CONFIRMED_WAIT_PUBLICATION":
            return "standby"
        return "technical"
    if time(13,0) <= clock <= time(23,59,59):
        return "publication"
    return "idle"

def publication_feedback(verification, now):
    if verification["both_published"]:
        return {"date":verification["date"],"feedback":"A_B_PUBLISHED","status":"complete",
                "missing":[],"next_action":"stop_today",
                "checked_at_sarajevo":now.astimezone(TZ).isoformat()}
    return {"date":verification["date"],"feedback":"A_B_PUBLICATION_MISSING",
            "status":"needs_ai_analyst_or_publisher",
            "missing":verification["missing"],"next_action":"inspector_publication_recovery",
            "checked_at_sarajevo":now.astimezone(TZ).isoformat(),
            "note":"This is a GitHub signal; it does not directly start a ChatGPT automation."}

def main():
    now=datetime.now(TZ)
    current=phase(now)
    print("AB_SENSOR_PHASE",current,now.isoformat())
    return current

if __name__=="__main__":
    main()
