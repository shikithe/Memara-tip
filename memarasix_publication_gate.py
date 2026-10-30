#!/usr/bin/env python3
"""Fail-closed publication gate. Never fabricate bets or overwrite bank data.

A separate, independently verified selection publisher is required to write data.json.
"""
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent

def assess(root=ROOT, now=None):
    now = now or datetime.now(ZoneInfo("Europe/Sarajevo"))
    today = now.date().isoformat()
    try:
        data = json.loads((root / "data.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return "BLOCKED: missing or invalid data.json"
    if data.get("date") == today and any(
        t.get("status") == "objavljen" for t in data.get("tickets", [])
    ):
        return "SKIPPED: today's published tickets are immutable"
    try:
        feed = json.loads((root / "collector-feed.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return "BLOCKED: missing or invalid collector-feed.json"
    if feed.get("date") != today:
        return "BLOCKED: stale collector feed"
    return "BLOCKED: no verified bookmaker odds and independent A/B/C publication integration"

def main():
    print(assess())
    # Read-only by design. No write to data.json or archive.json.

if __name__ == "__main__":
    main()
