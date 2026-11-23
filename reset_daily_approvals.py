#!/usr/bin/env python3
"""Clear obsolete AI approval INPUTS, not live tickets or archive."""
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

APPROVALS = ("memarasix-football-ai-approved.json", "memarasix-1455-approved.json")
TZ = ZoneInfo("Europe/Sarajevo")

def reset(root, today):
    changed = []
    for name in APPROVALS:
        path = root / name
        if not path.exists():
            continue
        doc = json.loads(path.read_text(encoding="utf-8"))
        if doc.get("date") == today:
            continue
        empty = {"date": today, "publication_allowed": False,
                 "approval_source": "awaiting_new_ai_analysis",
                 "state": "waiting_for_today_approval", "tickets": []}
        path.write_text(json.dumps(empty, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
        changed.append(name)
    return changed

if __name__ == "__main__":
    today = datetime.now(TZ).date().isoformat()
    print("RESET_STALE_APPROVAL_INPUTS", reset(Path("."),today))
