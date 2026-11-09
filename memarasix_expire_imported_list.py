#!/usr/bin/env python3
"""Expire ONLY previous-day ListaSix imports in MemaraSix after 08:55 Sarajevo.

Never edit AI approvals, published tickets, bank, archives, or research.
Repository-dispatch payload is a request, not proof: independently validate
the Sarajevo calendar day and the committed import date before deleting.
"""
import argparse
import json
from datetime import datetime, time, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

SAR = ZoneInfo("Europe/Sarajevo")
IMPORTED = (
    "listasix-data/active-list.json",
    "listasix-data/history-h2h.json",
    "listasix-data/sync-receipt.json",
)
ACK = "listasix-data/expiry-receipt.json"


def run(root, when, requested_day):
    local = when.astimezone(SAR)
    today = local.date().isoformat()
    if requested_day != today:
        raise ValueError("Expiry event date must match current Sarajevo date")
    if local.time() < time(8, 55):
        raise ValueError("Do not expire before 08:55 Sarajevo")
    folder = root / "listasix-data"
    folder.mkdir(exist_ok=True)
    # Preserve any imported current-day files even if yesterday's sync-receipt is
    # still present. A partially synchronized current-day dataset is not a
    # reason to destroy today's offer.
    active = folder / "active-list.json"
    if active.exists():
        try:
            obj = json.loads(active.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            raise ValueError("Unreadable active list; fail closed")
        if obj.get("date") == today:
            print("MEMARASIX_CURRENT_DAY_LIST_PRESERVED")
            state = "current_day_preserved"
        elif obj.get("date", "") > today:
            raise ValueError("Refuse to delete a future-dated active list")
        else:
            state = "expired_previous_day"
    else:
        state = "no_active_list"
    if state == "expired_previous_day":
        removed = []
        for filename in IMPORTED:
            p = root / filename
            if p.exists():
                p.unlink()
                removed.append(filename)
        print("MEMARASIX_OLD_LIST_REMOVED", ",".join(removed))
    elif state == "no_active_list":
        # If the active-list has already disappeared, clean up any stale
        # companions. Do not remove newly created current-day imports.
        for filename in IMPORTED[1:]:
            p = root / filename
            if not p.exists():
                continue
            try:
                doc = json.loads(p.read_text(encoding="utf-8"))
            except (OSError, ValueError, TypeError):
                raise ValueError("Unreadable imported companion; fail closed")
            if doc.get("date") == today:
                raise ValueError("Current-day companion exists without active list")
            if doc.get("date", "") > today:
                raise ValueError("Refuse to delete future-dated companion")
            p.unlink()
    # Retain one audit ACK to make the upstream cron idempotent.
    ack = {
        "date": today,
        "status": state,
        "completed_at_utc": when.astimezone(timezone.utc).isoformat(),
        "source": "shikithe/Slavojka:listaSix-expiry-cron",
        "protected": ["data.json", "memarasix-1455-approved.json", "archives"],
    }
    target = root / ACK
    if target.exists():
        try:
            previous = json.loads(target.read_text(encoding="utf-8"))
            if previous.get("date") == today:
                print("MEMARASIX_EXPIRY_ALREADY_CONFIRMED", today, state)
                return False
        except (OSError, ValueError, TypeError):
            pass
    target.write_text(json.dumps(ack, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("MEMARASIX_EXPIRY_CONFIRMED", today, state)
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-date", required=True)
    args = parser.parse_args()
    run(Path("."), datetime.now(timezone.utc), args.expected_date)


if __name__ == "__main__":
    main()
