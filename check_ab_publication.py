#!/usr/bin/env python3
"""Read-only A/B publication verification from MemaraSix website data.json.

Prepared approvals and audit logs are NOT publication evidence.
"""
import json
import argparse
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Europe/Sarajevo")

def check(data, day):
    if not isinstance(data, dict):
        raise ValueError("Invalid website data")
    same_day = data.get("date") == day
    tickets = data.get("tickets", []) if same_day else []
    if not isinstance(tickets, list):
        raise ValueError("tickets must be a list")
    found = {"A": [], "B": []}
    for t in tickets:
        if isinstance(t, dict) and t.get("id") in found:
            found[t["id"]].append(t)
    statuses = {}
    for tid, records in found.items():
        # A ticket counts as published only when the live website's data contains
        # the ticket with selections, and an explicit publication status.
        valid = [t for t in records if isinstance(t.get("matches"), list)
                 and len(t["matches"]) > 0
                 and t.get("status") in ("objavljen", "live", "won", "lost", "dobitan", "gubitan", "zavrsen", "završen")]
        statuses[tid] = {
            "published": bool(valid),
            "matches": len(valid[0]["matches"]) if valid else 0,
            "status": valid[0]["status"] if valid else "not_published",
            "duplicate_entries": len(records) > 1
        }
    both = all(x["published"] for x in statuses.values())
    return {"date": day, "source": "Memara-tip/data.json",
            "both_published": both, "A": statuses["A"], "B": statuses["B"],
            "state": "both_published" if both else "missing_publication",
            "missing": [k for k,v in statuses.items() if not v["published"]]}

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--file", default="data.json")
    p.add_argument("--date", default=datetime.now(TZ).date().isoformat())
    p.add_argument("--output", default="collector-output/ab-publication-check.json")
    args = p.parse_args()
    result = check(json.loads(Path(args.file).read_text(encoding="utf-8")), args.date)
    result["checked_at_sarajevo"] = datetime.now(TZ).isoformat()
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, indent=2, ensure_ascii=False)+"\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
