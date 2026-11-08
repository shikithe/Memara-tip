#!/usr/bin/env python3
"""Event-driven, verified ListaSix -> MemaraSix data import.

A repository_dispatch event arrives AFTER ListaSix has committed its ready
active-list. This process downloads and validates the actual source snapshot
before atomically preparing active-list, history and a sync receipt. The workflow
commits all three together; source polls GitHub for the receipt as an ACK.
"""
import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

SOURCE_BASE = "https://raw.githubusercontent.com/shikithe/Slavojka/main/"
SAR = ZoneInfo("Europe/Sarajevo")


def parse_dt(value):
    stamp = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if stamp.tzinfo is None:
        raise ValueError("Naive datetime not accepted")
    return stamp.astimezone(timezone.utc)


def canonical_hash(doc):
    raw = json.dumps(doc, sort_keys=True, ensure_ascii=False,
                     separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def download(path):
    req = Request(SOURCE_BASE + path, headers={
        "User-Agent": "MemaraSix-event-driven-sync",
        "Accept": "application/json", "Cache-Control": "no-cache"})
    with urlopen(req, timeout=40) as response:
        payload = response.read(40_000_001)
    if len(payload) > 40_000_000:
        raise ValueError("Source exceeds maximum size")
    return json.loads(payload)


def validate(active, history, now, expected_date=None, expected_sha256=None):
    today = now.astimezone(SAR).date().isoformat()
    if expected_date and expected_date != today:
        raise ValueError("Event carries a stale date")
    if active.get("date") != today or history.get("date") != today:
        raise ValueError("Source active-list/history are not both for today")
    if not active.get("publication_allowed"):
        raise ValueError("ListaSix has not approved publishing this list")
    if parse_dt(active.get("expires_at")) <= now:
        raise ValueError("Source list expired")
    fixtures = active.get("fixtures")
    if not isinstance(fixtures, list) or not fixtures:
        raise ValueError("Empty source active-list")
    ids = [f.get("fixture_id") for f in fixtures if isinstance(f, dict)]
    if len(ids) != len(fixtures) or any(not x for x in ids) or len(set(ids)) != len(ids):
        raise ValueError("Missing/duplicate ESPN fixture IDs")
    if not history.get("fixtures") or not history.get("leagues"):
        raise ValueError("Incomplete same-day history")
    digest = canonical_hash(active)
    if expected_sha256 and digest != expected_sha256:
        raise ValueError("Event hash does not match actual source: retry newer signal")
    return {"date": today, "active_sha256": digest, "fixtures": len(fixtures),
            "source": "shikithe/Slavojka:shared/active-list.json",
            "synced_at_utc": now.isoformat()}


def write_snapshot(root, active, history, receipt):
    path = root / "listasix-data"
    path.mkdir(parents=True, exist_ok=True)
    for name, value in (("active-list.json", active),
                        ("history-h2h.json", history),
                        ("sync-receipt.json", receipt)):
        tmp = path / (name + ".tmp")
        tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n",
                       encoding="utf-8")
        tmp.replace(path / name)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-date", default="")
    parser.add_argument("--expected-sha256", default="")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    now = datetime.now(timezone.utc)
    active = download("shared/active-list.json")
    history = download("shared/agent/history-h2h.json")
    receipt = validate(active, history, now,
                       expected_date=args.expected_date,
                       expected_sha256=args.expected_sha256)
    if not args.dry_run:
        write_snapshot(Path("."), active, history, receipt)
    print("LISTASIX_SYNC_VALIDATED", json.dumps(receipt, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
