#!/usr/bin/env python3
"""Feedback emitted exclusively after NBA system publisher commits next ticket.
No betting or AI selection is done here.
"""
import json
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

LEDGER = Path("nba-sistem.json")
OUT = Path("collector-output/nba-system-feedback.json")

def main():
    ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
    today = datetime.now(ZoneInfo("Europe/Sarajevo")).date().isoformat()
    cycle = next((c for c in ledger.get("cycles", []) if c.get("date") == today), None)
    if cycle is None:
        raise SystemExit("No cycle for local date, no feedback")
    published = [str(t["id"]) for t in cycle.get("tickets", [])]
    if published != [str(n) for n in range(1, len(published) + 1)]:
        raise SystemExit("Non-sequential ledger: refusing feedback")
    if not 1 <= len(published) <= 10:
        raise SystemExit("No valid published group, refusing feedback")
    next_group = len(published) + 1 if len(published) < 10 else None
    payload = {
        "schema_version": 1,
        "date": today,
        "cycle_id": cycle["id"],
        "last_published_group": len(published),
        "published_ticket_ids": published,
        "next_group": next_group,
        "state": "ready_for_next_ai_scout" if next_group else "all_10_published",
        "trigger_source": "github_confirmed_nba_system_ledger",
        "updated_at_utc": datetime.now(timezone.utc).isoformat(),
        "note": "AI must validate game start, frozen offer and all players in next group. A GitHub feedback file cannot directly wake ChatGPT."
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False))

if __name__ == "__main__":
    main()
